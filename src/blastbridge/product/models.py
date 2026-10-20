"""Thin product records. Exposure is not injury; an unknown count is None, never zero."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from blastbridge.models.enums import EventType
from blastbridge.models.training_tempo import ParticipationRole, TrainingContext

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# A known count of physical launches/firing events. Unknown is None, so zero is not a stand-in.
PhysicalCount = Annotated[int, Field(ge=1, le=999, strict=True)]


class ProductModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class EventStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class IntakeSource(StrEnum):
    MANUAL = "manual"
    AI_LIVE = "ai_live"
    AI_REPLAY = "ai_replay"


def provenance_text(source: IntakeSource, status: EventStatus) -> str:
    if status is EventStatus.REJECTED:
        return "Rejected — not part of personnel history"
    if status is EventStatus.APPROVED:
        return {
            IntakeSource.MANUAL: "Organizational record — manually entered",
            IntakeSource.AI_LIVE: "Organizational record — AI-assisted, human approved",
            IntakeSource.AI_REPLAY: "Organizational record — validated demo replay, human approved",
        }[source]
    return {
        IntakeSource.MANUAL: "Draft — manually entered, awaiting human approval",
        IntakeSource.AI_LIVE: "Draft — AI-assisted, awaiting human approval",
        IntakeSource.AI_REPLAY: "Draft — validated demo replay, awaiting human approval",
    }[source]


class CrewPosition(StrEnum):
    CHIEF = "chief"
    GUNNER = "gunner"
    DRIVER = "driver"

    @property
    def label(self) -> str:
        return _POSITION_LABELS[self]

    @property
    def participation_role(self) -> ParticipationRole:
        return _POSITION_ROLES[self]


_POSITION_LABELS = {
    CrewPosition.CHIEF: "Launcher chief",
    CrewPosition.GUNNER: "Gunner",
    CrewPosition.DRIVER: "Driver",
}
_POSITION_ROLES = {
    CrewPosition.CHIEF: ParticipationRole.SECTION_CHIEF,
    CrewPosition.GUNNER: ParticipationRole.WEAPON_OPERATOR,
    CrewPosition.DRIVER: ParticipationRole.CREW_MEMBER,
}


class Person(ProductModel):
    person_id: Text
    display_name: Text
    callsign: Text
    unit: Text
    section: Text
    home_position: CrewPosition


class CrewMember(ProductModel):
    person_id: Text
    position: CrewPosition


class Crew(ProductModel):
    crew_name: Text
    members: tuple[CrewMember, ...] = Field(min_length=1)
    # One launch is one physical event, shared by every member of the crew.
    physical_event_count: PhysicalCount | None

    @model_validator(mode="after")
    def unique_members(self) -> Self:
        ids = [m.person_id for m in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("a person can hold only one position in a crew")
        return self


class TrainingEventDraft(ProductModel):
    event_date: date
    event_type: EventType
    training_context: TrainingContext
    weapon_system_id: Text
    weapon_name: Text
    location_unit: Text | None = None
    crews: tuple[Crew, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_participants(self) -> Self:
        names = [c.crew_name for c in self.crews]
        if len(names) != len(set(names)):
            raise ValueError("crew names must be unique within an event")
        ids = [m.person_id for c in self.crews for m in c.members]
        if len(ids) != len(set(ids)):
            raise ValueError("a person can appear in only one crew per event")
        return self

    @property
    def participant_count(self) -> int:
        return sum(len(c.members) for c in self.crews)

    @property
    def known_physical_event_count(self) -> int:
        return sum(c.physical_event_count for c in self.crews if c.physical_event_count is not None)

    @property
    def unknown_crew_count(self) -> int:
        return sum(c.physical_event_count is None for c in self.crews)

    @property
    def physical_event_count(self) -> int | None:
        """Total physical launches; unknown if any crew's count is unknown."""
        counts = [c.physical_event_count for c in self.crews]
        return None if any(n is None for n in counts) else sum(n for n in counts if n is not None)

    @property
    def association_count(self) -> int | None:
        """Participant-event links. These are not additional launches."""
        counts = [c.physical_event_count for c in self.crews]
        if any(n is None for n in counts):
            return None
        return sum(len(c.members) * n for c, n in zip(self.crews, counts, strict=True) if n)


class TrainingEvent(ProductModel):
    event_id: Text
    status: EventStatus
    intake_source: IntakeSource
    revision: Annotated[int, Field(ge=1, strict=True)]
    draft: TrainingEventDraft


class HistoryEntry(ProductModel):
    event_id: Text
    intake_source: IntakeSource
    event_date: date
    event_type: EventType
    training_context: TrainingContext
    weapon_name: Text
    location_unit: Text | None
    crew_name: Text
    position: CrewPosition
    participation_role: ParticipationRole
    physical_event_count: PhysicalCount | None
