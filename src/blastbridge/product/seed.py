"""FICTIONAL demo roster. These people do not exist; names and units are invented."""

from datetime import date

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import TrainingContext

from .models import Crew, CrewMember, CrewPosition, IntakeSource, Person, TrainingEventDraft
from .symptoms import (
    FunctionalImpact,
    Persistence,
    Symptom,
    SymptomReportDraft,
    SymptomSource,
    TemporalRelationship,
)

_UNIT = "Demo Rocket Battery"

_ROSTER = (
    ("Avery Kestrel", "KESTREL", "1st Section", CrewPosition.CHIEF),
    ("Jordan Pike", "PIKE", "1st Section", CrewPosition.GUNNER),
    ("Riley Marsh", "MARSH", "1st Section", CrewPosition.DRIVER),
    ("Sam Okafor-Lind", "LINDY", "1st Section", CrewPosition.GUNNER),
    ("Casey Thorne", "THORNE", "2nd Section", CrewPosition.CHIEF),
    ("Morgan Vale", "VALE", "2nd Section", CrewPosition.GUNNER),
    ("Taylor Brook", "BROOK", "2nd Section", CrewPosition.DRIVER),
    ("Devon Ashby", "ASHBY", "2nd Section", CrewPosition.DRIVER),
    ("Quinn Halloway", "HALO", "3rd Section", CrewPosition.CHIEF),
    ("Reese Calder", "CALDER", "3rd Section", CrewPosition.GUNNER),
    ("Emerson Tull", "TULL", "3rd Section", CrewPosition.DRIVER),
    ("Harper Yoon", "YOON", "3rd Section", CrewPosition.GUNNER),
)

DEMO_PEOPLE = tuple(
    Person(
        person_id=f"FIC-{i:03d}",
        display_name=name,
        callsign=callsign,
        unit=_UNIT,
        section=section,
        home_position=position,
    )
    for i, (name, callsign, section, position) in enumerate(_ROSTER, start=1)
)


def _demo_draft(
    day: str,
    context: TrainingContext,
    crews: tuple[tuple[str, tuple[int, int, int], int | None], ...],
    weapon: str = "m142-himars",
    south: bool = False,
) -> TrainingEventDraft:
    return TrainingEventDraft(
        event_date=date.fromisoformat(day),
        event_type=EventType.WEAPON_FIRING,
        training_context=context,
        weapon_system_id=weapon,
        weapon_name="M270 MLRS" if weapon == "m270-mlrs" else "M142 HIMARS",
        location_unit=f"Demo Range {'South' if south else 'North'}",
        crews=tuple(
            Crew(
                crew_name=name,
                members=tuple(
                    CrewMember(person_id=f"FIC-{person:03d}", position=position)
                    for person, position in zip(
                        people,
                        (CrewPosition.CHIEF, CrewPosition.GUNNER, CrewPosition.DRIVER),
                        strict=True,
                    )
                ),
                physical_event_count=count,
            )
            for name, people, count in crews
        ),
    )


_SHARED_SOURCE_ONE = _demo_draft(
    "2026-10-17", TrainingContext.HOME_STATION, (("Launcher 1", (1, 2, 3), 6),)
)
_SHARED_SOURCE_TWO = TrainingEventDraft.model_validate(
    {
        **_SHARED_SOURCE_ONE.model_dump(),
        "crews": (
            Crew(
                crew_name="Launcher 1",
                members=_SHARED_SOURCE_ONE.crews[0].members[:2],
                physical_event_count=None,
            ),
            _demo_draft(
                "2026-10-17", TrainingContext.HOME_STATION, (("Launcher 2", (5, 6, 7), None),)
            ).crews[0],
        ),
    }
)
DEMO_SOURCE_DRAFTS: tuple[tuple[str, TrainingEventDraft, IntakeSource], ...] = (
    ("EVT-DEMO-S1", _SHARED_SOURCE_ONE, IntakeSource.MANUAL),
    ("EVT-DEMO-S2", _SHARED_SOURCE_TWO, IntakeSource.AI_REPLAY),
)


DEMO_EVENTS: tuple[tuple[str, TrainingEventDraft], ...] = (
    # Fictional backfill makes history coverage visible, not evidence about actual training.
    # FIC-004/FIC-008 retain shorter histories; FIC-012 remains outside the HIMARS scope.
    (
        "EVT-DEMO-B1",
        _demo_draft(
            "2025-10-07",
            TrainingContext.HOME_STATION,
            (
                ("Launcher 1", (1, 2, 3), 6),
                ("Launcher 2", (5, 6, 7), 6),
                ("Launcher 3", (9, 10, 11), None),
            ),
        ),
    ),
    (
        "EVT-DEMO-B2",
        _demo_draft(
            "2026-01-21",
            TrainingContext.ANNUAL_TRAINING,
            (
                ("Launcher 2", (5, 6, 8), 8),
                ("Launcher 3", (9, 10, 11), 8),
            ),
        ),
    ),
    (
        "EVT-DEMO-B3",
        _demo_draft(
            "2026-03-10",
            TrainingContext.QUALIFICATION,
            (
                ("Launcher 2", (5, 6, 7), 4),
                ("Launcher 3", (9, 10, 11), 4),
            ),
        ),
    ),
    (
        "EVT-DEMO-01",
        _demo_draft(
            "2026-04-14",
            TrainingContext.QUALIFICATION,
            (
                ("Launcher 1", (1, 2, 3), 6),
                ("Launcher 2", (5, 6, 7), 6),
            ),
        ),
    ),
    (
        "EVT-DEMO-02",
        _demo_draft("2026-05-20", TrainingContext.HOME_STATION, (("Launcher 1", (1, 4, 3), 4),)),
    ),
    (
        "EVT-DEMO-03",
        _demo_draft(
            "2026-06-23",
            TrainingContext.ANNUAL_TRAINING,
            (
                ("Launcher 1", (1, 2, 3), 12),
                ("Launcher 2", (5, 6, 8), 12),
                ("Launcher 3", (9, 10, 11), None),
            ),
        ),
    ),
    (
        "EVT-DEMO-04",
        _demo_draft(
            "2026-07-28",
            TrainingContext.HOME_STATION,
            (("Launcher 3", (9, 12, 11), 2),),
            weapon="m270-mlrs",
            south=True,
        ),
    ),
    (
        "EVT-DEMO-05",
        _demo_draft(
            "2026-08-25",
            TrainingContext.DEPLOYMENT_PREPARATION,
            (
                ("Launcher 1", (2, 4, 3), 8),
                ("Launcher 3", (9, 10, 11), 8),
            ),
            south=True,
        ),
    ),
    (
        "EVT-DEMO-06",
        _demo_draft(
            "2026-09-22",
            TrainingContext.CTC_LARGE_SCALE_EXERCISE,
            (
                ("Launcher 1", (2, 1, 3), 10),
                ("Launcher 2", (5, 6, 7), None),
            ),
        ),
    ),
    # FICTIONAL demo pattern example: EVT-DEMO-C1..C3 were constructed so that Reese Calder
    # (FIC-010) demonstrates an atypical comparison. 'Not tuned' means the model, threshold,
    # reference and gates were left unchanged; the demo history, not the model, was arranged
    # for this example.
    (
        "EVT-DEMO-C1",
        _demo_draft(
            "2026-10-02",
            TrainingContext.QUALIFICATION,
            (("Launcher 3", (9, 10, 11), 6),),
            south=True,
        ),
    ),
    (
        "EVT-DEMO-C2",
        _demo_draft(
            "2026-10-06",
            TrainingContext.QUALIFICATION,
            (("Launcher 3", (5, 10, 8), 4),),
            south=True,
        ),
    ),
    (
        "EVT-DEMO-C3",
        _demo_draft(
            "2026-10-13",
            TrainingContext.QUALIFICATION,
            (("Launcher 3", (1, 10, 7), None),),
            south=True,
        ),
    ),
)

DEMO_SYMPTOMS: tuple[tuple[str, SymptomReportDraft], ...] = (
    (
        "SYM-DEMO-01",
        SymptomReportDraft(
            person_id="FIC-002",
            event_id="EVT-DEMO-06",
            report_date=date(2026, 9, 24),
            source=SymptomSource.SELF_REPORTED,
            symptoms=(Symptom.HEADACHES, Symptom.SLEEP_PROBLEMS),
            temporal_relationship=TemporalRelationship.AFTER_RECORDED_EVENT,
            persistence=Persistence.STILL_PRESENT,
            functional_impact=FunctionalImpact.YES,
            note="Demo report.",
        ),
    ),
    (
        "SYM-DEMO-02",
        SymptomReportDraft(
            person_id="FIC-010",
            event_id="EVT-DEMO-05",
            report_date=date(2026, 8, 27),
            source=SymptomSource.MEDICAL_OR_READINESS_RECORDED,
            symptoms=(Symptom.TINNITUS,),
            temporal_relationship=TemporalRelationship.RELATIONSHIP_UNKNOWN,
            persistence=Persistence.UNKNOWN,
            functional_impact=FunctionalImpact.UNKNOWN,
        ),
    ),
    (
        "SYM-DEMO-03",
        SymptomReportDraft(
            person_id="FIC-006",
            event_id="EVT-DEMO-01",
            report_date=date(2026, 4, 16),
            source=SymptomSource.SELF_REPORTED,
            symptoms=(Symptom.DIZZINESS,),
            temporal_relationship=TemporalRelationship.AFTER_RECORDED_EVENT,
            persistence=Persistence.RESOLVED,
            functional_impact=FunctionalImpact.NO,
        ),
    ),
)
