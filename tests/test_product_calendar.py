"""Recorded dates determine marks; current readiness remains separate from the calendar."""

from datetime import date, timedelta

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext
from blastbridge.product import store
from blastbridge.product.calendar_view import (
    DEMO_STORY_DATE,
    calendar_form_values,
    can_record_on,
    month_weeks,
    next_action,
    organization_marks,
    person_marks,
)
from blastbridge.product.models import (
    CrewPosition,
    EventStatus,
    HistoryEntry,
    IntakeSource,
    TrainingEvent,
)
from blastbridge.product.patterns import assess_pattern, fit_pattern_model, load_reference
from blastbridge.product.readiness import ReadinessAssessment, ReadinessStatus, assess_readiness
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE, DEMO_SYMPTOMS
from blastbridge.product.symptoms import (
    DangerSign,
    FunctionalImpact,
    Persistence,
    Symptom,
    SymptomReport,
    SymptomReportDraft,
    SymptomSource,
    TemporalRelationship,
)


def assessment(person_id, status):
    return ReadinessAssessment(
        person_id=person_id,
        analysis_as_of=DEMO_STORY_DATE,
        ml_pattern=None,
        symptom_followup_status=None,
        urgent_status=status is ReadinessStatus.URGENT_EVALUATION,
        data_quality_notes=(),
        overall_readiness_status=status,
        evidence_lines=(),
    )


def test_training_dates_are_neutral_regardless_of_current_readiness():
    events = [
        TrainingEvent(
            event_id=event_id,
            draft=draft,
            revision=1,
            intake_source=IntakeSource.MANUAL,
            status=status,
        )
        for (event_id, draft), status in zip(
            DEMO_EVENTS[:3],
            (
                EventStatus.APPROVED,
                EventStatus.DRAFT,
                EventStatus.REJECTED,
            ),
            strict=True,
        )
    ]
    assessments = {
        "FIC-001": assessment("FIC-001", ReadinessStatus.REVIEW_PRIORITY),
        "FIC-002": assessment("FIC-002", ReadinessStatus.MEDICAL_FOLLOWUP_RECOMMENDED),
    }
    assert all(
        item.overall_readiness_status is not ReadinessStatus.ROUTINE_MONITORING
        for item in assessments.values()
    )
    marks = organization_marks(events, [], DEMO_STORY_DATE)
    assert set(marks) == {events[0].draft.event_date}
    mark = marks[events[0].draft.event_date]
    assert mark.training == 1 and mark.symptom == 0
    assert not mark.attention and not mark.urgent
    assert mark.people == frozenset(
        member.person_id for crew in events[0].draft.crews for member in crew.members
    )


def test_person_marks_separate_records_and_report_guidance():
    training_day = date(2026, 10, 1)
    entry = HistoryEntry(
        event_id="EVT-FICTIONAL",
        intake_source=IntakeSource.MANUAL,
        event_date=training_day,
        event_type=EventType.WEAPON_FIRING,
        training_context=TrainingContext.QUALIFICATION,
        weapon_name="Fictional demo system",
        weapon_system_id="m142-himars",
        location_unit=None,
        crew_name="Fictional crew",
        position=CrewPosition.CHIEF,
        participation_role=ParticipationRole.SECTION_CHIEF,
        physical_event_count=None,
    )
    reports = [
        SymptomReport(
            report_id=f"SYM-FICTIONAL-{offset}",
            confirmed_at="2026-10-19T00:00:00+00:00",
            draft=SymptomReportDraft(
                person_id="FIC-001",
                report_date=training_day + timedelta(days=offset),
                source=SymptomSource.SELF_REPORTED,
                symptoms=(Symptom.HEADACHES,),
                danger_signs=(DangerSign.REPEATED_VOMITING,) if offset == 2 else (),
                temporal_relationship=TemporalRelationship.NOT_LINKED_TO_EVENT,
                persistence=Persistence.RESOLVED if offset == 3 else Persistence.STILL_PRESENT,
                functional_impact=FunctionalImpact.YES,
            ),
        )
        for offset in (1, 2, 3)
    ]
    marks = person_marks([entry], reports, DEMO_STORY_DATE)
    assert marks[training_day].training == 1 and marks[training_day].symptom == 0
    suggested = marks[training_day + timedelta(days=1)]
    assert suggested.symptom == 1 and not suggested.attention and not suggested.urgent
    urgent = marks[training_day + timedelta(days=2)]
    assert urgent.symptom == 1 and urgent.urgent and not urgent.attention
    resolved = marks[training_day + timedelta(days=3)]
    assert resolved.symptom == 1 and not resolved.attention and not resolved.urgent
    earlier_marks = person_marks([entry], reports, training_day)
    assert all(
        mark.symptom == 1 and not mark.attention and not mark.urgent
        for day, mark in earlier_marks.items()
        if day > training_day
    )
    event_id, draft = DEMO_EVENTS[0]
    event = TrainingEvent(
        event_id=event_id,
        draft=draft.model_copy(update={"event_date": training_day}),
        revision=1,
        intake_source=IntakeSource.MANUAL,
        status=EventStatus.APPROVED,
    )
    organization = organization_marks([event], reports, DEMO_STORY_DATE)
    danger_day = training_day + timedelta(days=2)
    assert set(organization) == {training_day, danger_day}
    assert not organization[training_day].attention and not organization[training_day].urgent
    assert organization[danger_day].urgent and organization[danger_day].training == 0
    assert not organization[danger_day].attention
    assert set(organization_marks([event], reports, training_day)) == {training_day}


def test_month_weeks_are_sunday_first_and_future_days_cannot_record():
    weeks = month_weeks(2026, 10)
    assert weeks[0] == [
        None,
        None,
        None,
        None,
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
    ]
    assert month_weeks(2026, 11)[0][0] == date(2026, 11, 1)
    assert month_weeks(2026, 11)[-1] == [
        date(2026, 11, 29),
        date(2026, 11, 30),
        None,
        None,
        None,
        None,
        None,
    ]
    assert can_record_on(DEMO_STORY_DATE, DEMO_STORY_DATE)
    assert can_record_on(DEMO_STORY_DATE - timedelta(days=1), DEMO_STORY_DATE)
    assert not can_record_on(DEMO_STORY_DATE + timedelta(days=1), DEMO_STORY_DATE)


def test_demo_reset_reproduces_calendar_and_readiness():
    rows, metadata = load_reference()
    model = fit_pattern_model(rows, metadata)
    conn = store.connect(":memory:")
    try:
        store.init_db(conn)
        snapshots = []
        for _ in range(2):
            store.reset_demo(conn, DEMO_PEOPLE, DEMO_EVENTS, DEMO_SYMPTOMS)
            assert len(store.list_events(conn, EventStatus.APPROVED, limit=-1)) == 12
            assessments = {}
            for person in DEMO_PEOPLE:
                entries = store.member_history(conn, person.person_id)
                reports = store.list_symptom_reports(conn, person.person_id)
                pattern = assess_pattern(
                    model,
                    entries,
                    DEMO_STORY_DATE,
                )
                assessments[person.person_id] = assess_readiness(
                    person.person_id,
                    entries,
                    reports,
                    pattern,
                    DEMO_STORY_DATE,
                )
            snapshots.append(
                (
                    organization_marks(
                        store.list_events(conn, EventStatus.APPROVED, limit=-1),
                        store.list_symptom_reports(conn),
                        DEMO_STORY_DATE,
                    ),
                    {
                        person_id: item.overall_readiness_status
                        for person_id, item in assessments.items()
                    },
                )
            )
        assert snapshots[0] == snapshots[1]
        assert set(snapshots[0][1]) == {person.person_id for person in DEMO_PEOPLE}
    finally:
        conn.close()


def test_contextual_entry_prefills_only_and_still_requires_approval():
    conn = store.connect(":memory:")
    try:
        store.init_db(conn)
        store.seed_people(conn, DEMO_PEOPLE)
        before = tuple(conn.iterdump())
        values = calendar_form_values(DEMO_STORY_DATE)
        assert values["f_date"] == DEMO_STORY_DATE
        assert tuple(conn.iterdump()) == before
        draft = DEMO_EVENTS[0][1].model_copy(update={"event_date": values["f_date"]})
        event_id = store.save_draft(conn, draft)
        assert store.get_event(conn, event_id).status is EventStatus.DRAFT
        assert store.member_history(conn, "FIC-001") == []
        store.approve_event(conn, event_id, 1)
        assert store.member_history(conn, "FIC-001")[0].event_date == DEMO_STORY_DATE
    finally:
        conn.close()


def test_every_readiness_status_has_a_bounded_next_action():
    for status in ReadinessStatus:
        sentence = next_action(status)
        assert sentence
        assert not any(
            term in sentence.casefold() for term in ("normal", "safe", "low risk", "probability")
        )
