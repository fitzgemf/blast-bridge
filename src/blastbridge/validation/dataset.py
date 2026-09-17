"""Cross-record checks, separate from the individual record schemas."""

from typing import Self

from pydantic import model_validator

from blastbridge.models import (
    Assignment,
    ExposureEvent,
    SensorReading,
    ServiceMember,
    SymptomReport,
    WeaponSystem,
)
from blastbridge.models.core import ResearchModel, check_synthetic_boundary
from blastbridge.models.enums import DataKind, SensorAvailability


def unique_index[T](rows: tuple[T, ...], id_field: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for row in rows:
        key = getattr(row, id_field)
        if key in result:
            raise ValueError(f"duplicate {id_field}: {key}")
        result[key] = row
    return result


class ResearchDataset(ResearchModel):
    """Closed, in-memory validation batch; referenced records must be included."""

    members: tuple[ServiceMember, ...] = ()
    assignments: tuple[Assignment, ...] = ()
    weapons: tuple[WeaponSystem, ...] = ()
    exposures: tuple[ExposureEvent, ...] = ()
    sensor_readings: tuple[SensorReading, ...] = ()
    symptom_reports: tuple[SymptomReport, ...] = ()

    @model_validator(mode="after")
    def validate_links(self) -> Self:
        members = unique_index(self.members, "member_id")
        assignments = unique_index(self.assignments, "assignment_id")
        weapons = unique_index(self.weapons, "weapon_system_id")
        exposures = unique_index(self.exposures, "exposure_id")
        unique_index(self.sensor_readings, "reading_id")
        unique_index(self.symptom_reports, "report_id")

        member_kinds = {m.provenance.kind == DataKind.SYNTHETIC for m in self.members}
        if len(member_kinds) > 1:
            raise ValueError("synthetic and real members require separate datasets")

        for assignment in self.assignments:
            member = members.get(assignment.member_id)
            if member is None:
                raise ValueError("assignment references an unknown member")
            check_synthetic_boundary(member.provenance, [assignment.provenance])
            if assignment.start_date < member.service_start:
                raise ValueError("assignment starts before service")
            if member.service_end is not None and (
                assignment.start_date > member.service_end
                or assignment.end_date is None
                or assignment.end_date > member.service_end
            ):
                raise ValueError("assignment exceeds a completed service period")
            if any(weapon_id not in weapons for weapon_id in assignment.weapon_system_ids):
                raise ValueError("assignment references an unknown weapon")

        for event in self.exposures:
            member = members.get(event.member_id)
            if member is None:
                raise ValueError("exposure references an unknown member")
            check_synthetic_boundary(member.provenance, [event.provenance])
            event_date = event.timestamp.date()
            if event_date < member.service_start or (
                member.service_end is not None and event_date > member.service_end
            ):
                raise ValueError("occupational exposure falls outside service dates")
            if event.weapon_system_id not in weapons:
                raise ValueError("exposure references an unknown weapon")
            if event.assignment_id is not None:
                linked_assignment = assignments.get(event.assignment_id)
                if linked_assignment is None or linked_assignment.member_id != event.member_id:
                    raise ValueError("exposure assignment is missing or belongs to another member")
                if event_date < linked_assignment.start_date or (
                    linked_assignment.end_date is not None
                    and event_date > linked_assignment.end_date
                ):
                    raise ValueError("exposure falls outside assignment dates")

        observations: tuple[SensorReading | SymptomReport, ...] = (
            *self.sensor_readings,
            *self.symptom_reports,
        )
        for observation in observations:
            member = members.get(observation.member_id)
            if member is None:
                raise ValueError("observation references an unknown member")
            check_synthetic_boundary(member.provenance, [observation.provenance])
            if observation.exposure_id is not None:
                linked_event = exposures.get(observation.exposure_id)
                if linked_event is None or linked_event.member_id != observation.member_id:
                    raise ValueError("linked exposure is missing or belongs to another member")
                if (
                    isinstance(observation, SensorReading)
                    and linked_event.sensor_availability != SensorAvailability.AVAILABLE
                ):
                    raise ValueError("linked sensor reading requires sensor availability")
        return self
