"""Version-one research schemas. No physiological thresholds or injury inference."""

from datetime import date
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    model_validator,
)

from .enums import (
    BodyPosition,
    Branch,
    Component,
    Context,
    DataKind,
    Environment,
    EventType,
    ImpulseUnit,
    MedicalEvaluationStatus,
    Participation,
    PressureUnit,
    SensorAvailability,
    SensorQuality,
    SourceType,
    SymptomSeverity,
    Tier1Status,
    WeaponFamily,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
Count = Annotated[int, Field(ge=0, strict=True)]
Angle = Annotated[float, Field(ge=0, lt=360, allow_inf_nan=False, strict=True)]


class ResearchModel(BaseModel):
    """Immutable validated records; nested collections are tuples."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class DataSource(ResearchModel):
    source_id: Text
    source_type: SourceType
    citation: Text
    confidence: Confidence | None = None
    notes: Text | None = None


class Provenance(ResearchModel):
    """Evidence lineage. Confidence is a research annotation, not injury probability."""

    kind: DataKind
    sources: tuple[DataSource, ...] = Field(min_length=1)
    confidence: Confidence | None = None
    method: Text | None = None

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        types = {source.source_type for source in self.sources}
        if len({source.source_id for source in self.sources}) != len(self.sources):
            raise ValueError("source IDs must be unique within provenance")
        if self.kind == DataKind.SYNTHETIC:
            if SourceType.SYNTHETIC not in types:
                raise ValueError("synthetic observations require a synthetic source")
        elif SourceType.SYNTHETIC in types:
            raise ValueError("synthetic sources cannot support non-synthetic observations")
        if self.kind == DataKind.ESTIMATED and (self.confidence is None or self.method is None):
            raise ValueError("estimates require confidence and a method")
        if self.kind == DataKind.MEASURED and SourceType.SENSOR not in types:
            raise ValueError("measured observations require a sensor source")
        if self.kind == DataKind.SELF_REPORTED and not types.intersection(
            {SourceType.CONTEMPORANEOUS_SELF_REPORT, SourceType.RETROSPECTIVE_SELF_REPORT}
        ):
            raise ValueError("self-reported observations require a self-report source")
        if self.kind == DataKind.DOCUMENTED and not types.intersection(
            {SourceType.OFFICIAL, SourceType.PEER_REVIEWED}
        ):
            raise ValueError("documented observations require an official or peer-reviewed source")
        return self


class Evidence[T](ResearchModel):
    """A value with its own provenance, allowing mixed evidence within real records."""

    value: T
    provenance: Provenance


def check_synthetic_boundary(parent: Provenance, children: list[Provenance]) -> None:
    synthetic = parent.kind == DataKind.SYNTHETIC
    if any((child.kind == DataKind.SYNTHETIC) != synthetic for child in children):
        raise ValueError("synthetic and real observations cannot be mixed in a record")


class ServiceMember(ResearchModel):
    member_id: Text
    branch: Branch
    component: Component
    service_start: date
    service_end: date | None = None
    provenance: Provenance
    age_at_service_start_years: Count | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.service_end is not None and self.service_end < self.service_start:
            raise ValueError("service_end must be on or after service_start")
        return self


class Assignment(ResearchModel):
    assignment_id: Text
    member_id: Text
    mos: Text | None = None
    unit_type: Text | None = None
    start_date: date
    end_date: date | None = None
    weapon_system_ids: tuple[Text, ...] = ()
    platform: Text | None = None
    role: Text | None = None
    instructor_status: StrictBool | None = None
    context: Context = Context.UNKNOWN
    branch: Branch | None = None
    component: Component | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class WeaponSystem(ResearchModel):
    weapon_system_id: Text
    name: Text
    family: WeaponFamily
    caliber: Text | None = None
    branches: tuple[Branch, ...] = ()
    dod_tier1_status: Tier1Status = Tier1Status.UNKNOWN
    tier1_source: DataSource | None = None
    description: Text | None = None
    source: DataSource

    @model_validator(mode="after")
    def validate_tier1(self) -> Self:
        if self.dod_tier1_status != Tier1Status.UNKNOWN and (
            self.tier1_source is None or self.tier1_source.source_type != SourceType.OFFICIAL
        ):
            raise ValueError("a known DoD Tier-1 status requires an official source")
        return self


class Pressure(ResearchModel):
    value: NonNegative
    unit: PressureUnit
    provenance: Provenance


class Impulse(ResearchModel):
    value: NonNegative
    unit: ImpulseUnit
    provenance: Provenance


class ExposureEvent(ResearchModel):
    exposure_id: Text
    member_id: Text
    assignment_id: Text | None = None
    timestamp: AwareDatetime
    weapon_system_id: Text
    ammunition: Text | None = None
    event_type: EventType = EventType.UNKNOWN
    rounds: Evidence[Count] | None = None
    firing_events: Evidence[Count] | None = None
    participation: Participation = Participation.UNKNOWN
    crew_role: Text | None = None
    body_position: BodyPosition = BodyPosition.UNKNOWN
    distance_m: Evidence[NonNegative] | None = None
    orientation_degrees: Evidence[Angle] | None = None
    orientation_reference: Text | None = None
    environment: Environment = Environment.UNKNOWN
    ppe: tuple[Text, ...] | None = None
    sensor_availability: SensorAvailability = SensorAvailability.UNKNOWN
    peak_pressure: Pressure | None = None
    impulse: Impulse | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_observations(self) -> Self:
        observations = (
            self.rounds,
            self.firing_events,
            self.distance_m,
            self.orientation_degrees,
            self.peak_pressure,
            self.impulse,
        )
        check_synthetic_boundary(
            self.provenance, [item.provenance for item in observations if item is not None]
        )
        if self.orientation_degrees is not None and self.orientation_reference is None:
            raise ValueError("orientation requires a reference frame")
        quantities = [q for q in (self.peak_pressure, self.impulse) if q is not None]
        if quantities and self.sensor_availability != SensorAvailability.AVAILABLE:
            raise ValueError("event pressure/impulse require sensor availability")
        expected = (
            DataKind.SYNTHETIC if self.provenance.kind == DataKind.SYNTHETIC else DataKind.MEASURED
        )
        if any(q.provenance.kind != expected for q in quantities):
            raise ValueError("event pressure/impulse must be measured (or explicitly synthetic)")
        return self


class SensorReading(ResearchModel):
    reading_id: Text
    member_id: Text
    exposure_id: Text | None = None
    timestamp: AwareDatetime
    sensor_type: Text
    sensor_position: Text | None = None
    peak_pressure: Pressure | None = None
    impulse: Impulse | None = None
    quality: SensorQuality = SensorQuality.UNREVIEWED
    provenance: Provenance

    @model_validator(mode="after")
    def validate_measurements(self) -> Self:
        quantities = [q for q in (self.peak_pressure, self.impulse) if q is not None]
        if not quantities:
            raise ValueError("a sensor reading requires pressure or impulse")
        if self.provenance.kind not in {DataKind.MEASURED, DataKind.SYNTHETIC}:
            raise ValueError("sensor readings must be measured or synthetic")
        if any(q.provenance.kind != self.provenance.kind for q in quantities):
            raise ValueError("sensor quantities must match the reading evidence kind")
        return self


class SymptomReport(ResearchModel):
    report_id: Text
    member_id: Text
    timestamp: AwareDatetime
    exposure_id: Text | None = None
    headache: StrictBool | None = None
    tinnitus: StrictBool | None = None
    dizziness: StrictBool | None = None
    concentration_difficulty: StrictBool | None = None
    memory_difficulty: StrictBool | None = None
    sleep_disturbance: StrictBool | None = None
    balance_issues: StrictBool | None = None
    severity: SymptomSeverity = SymptomSeverity.UNKNOWN
    duration_hours: Evidence[NonNegative] | None = None
    medical_evaluation_status: MedicalEvaluationStatus = MedicalEvaluationStatus.UNKNOWN
    provenance: Provenance

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.provenance.kind not in {DataKind.SELF_REPORTED, DataKind.SYNTHETIC}:
            raise ValueError("symptom reports must be self-reported or synthetic")
        if self.duration_hours is not None:
            check_synthetic_boundary(self.provenance, [self.duration_hours.provenance])
        symptoms = (
            self.headache,
            self.tinnitus,
            self.dizziness,
            self.concentration_difficulty,
            self.memory_difficulty,
            self.sleep_disturbance,
            self.balance_issues,
        )
        if self.severity == SymptomSeverity.NONE and any(s is True for s in symptoms):
            raise ValueError("severity none conflicts with a reported symptom")
        if self.severity in {
            SymptomSeverity.MILD,
            SymptomSeverity.MODERATE,
            SymptomSeverity.SEVERE,
        } and all(s is False for s in symptoms):
            raise ValueError("positive severity conflicts with all symptoms absent")
        return self
