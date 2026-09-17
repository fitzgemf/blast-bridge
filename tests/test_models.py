import math

import pytest
from pydantic import ValidationError

from blastbridge.models import (
    Assignment,
    DataSource,
    ExposureEvent,
    Impulse,
    Pressure,
    Provenance,
    SensorReading,
    ServiceMember,
    SymptomReport,
    WeaponSystem,
)
from blastbridge.models.enums import SourceType

MODELS = [
    (DataSource, "source"),
    (ServiceMember, "member"),
    (Assignment, "assignment"),
    (WeaponSystem, "weapon"),
    (ExposureEvent, "event"),
    (SensorReading, "reading"),
    (SymptomReport, "symptoms"),
]


@pytest.mark.parametrize(("model", "key"), MODELS)
def test_valid_models_json_round_trip_and_schema(model, key, payloads):
    record = model.model_validate(payloads[key])
    assert model.model_validate_json(record.model_dump_json()) == record
    assert model.model_json_schema()["type"] == "object"


@pytest.mark.parametrize(("model", "key"), MODELS)
def test_extra_fields_rejected(model, key, payloads):
    with pytest.raises(ValidationError, match="Extra inputs"):
        model.model_validate({**payloads[key], "unexpected_field": "x"})


@pytest.mark.parametrize("source_type", list(SourceType))
def test_all_source_types_supported(source_type):
    assert (
        DataSource(
            source_id="source", source_type=source_type, citation="Test reference"
        ).source_type
        == source_type
    )


@pytest.mark.parametrize("bad", [-1.0, 1.01, math.inf, -math.inf, math.nan, True, "0.5"])
def test_confidence_rejected(bad, payloads):
    with pytest.raises(ValidationError):
        DataSource.model_validate({**payloads["source"], "confidence": bad})
    with pytest.raises(ValidationError):
        Provenance.model_validate({**payloads["reported"], "confidence": bad})


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_confidence_boundaries(value, payloads):
    assert (
        DataSource.model_validate({**payloads["source"], "confidence": value}).confidence == value
    )


@pytest.mark.parametrize("field", ["rounds", "firing_events"])
@pytest.mark.parametrize("bad", [-1, 1.5, True, "3"])
def test_invalid_counts(field, bad, payloads):
    payloads["event"][field] = {"value": bad, "provenance": payloads["reported"]}
    with pytest.raises(ValidationError):
        ExposureEvent.model_validate(payloads["event"])


@pytest.mark.parametrize("field", ["rounds", "firing_events"])
def test_zero_count_is_allowed(field, payloads):
    payloads["event"][field] = {"value": 0, "provenance": payloads["reported"]}
    assert getattr(ExposureEvent.model_validate(payloads["event"]), field).value == 0


@pytest.mark.parametrize(("model", "key"), [(Pressure, "pressure"), (Impulse, "impulse")])
@pytest.mark.parametrize("bad", [-0.1, math.nan, math.inf, True, "1"])
def test_invalid_measurements(model, key, bad, payloads):
    with pytest.raises(ValidationError):
        model.model_validate({**payloads[key], "value": bad})


@pytest.mark.parametrize(
    ("model", "key", "unit"),
    [
        (Pressure, "pressure", "Pa*s"),
        (Impulse, "impulse", "kPa"),
    ],
)
def test_unit_dimensions_are_separate(model, key, unit, payloads):
    with pytest.raises(ValidationError):
        model.model_validate({**payloads[key], "unit": unit})


@pytest.mark.parametrize(
    ("model", "key", "field", "value"),
    [
        (ServiceMember, "member", "service_end", "2019-01-01"),
        (Assignment, "assignment", "end_date", "2020-01-01"),
        (ServiceMember, "member", "age_at_service_start_years", -1),
        (ServiceMember, "member", "member_id", " "),
        (Assignment, "assignment", "instructor_status", "yes"),
        (SymptomReport, "symptoms", "headache", "false"),
    ],
)
def test_invalid_record_fields(model, key, field, value, payloads):
    with pytest.raises(ValidationError):
        model.model_validate({**payloads[key], field: value})


@pytest.mark.parametrize(
    ("model", "key"),
    [
        (ExposureEvent, "event"),
        (SensorReading, "reading"),
        (SymptomReport, "symptoms"),
    ],
)
def test_timezone_required(model, key, payloads):
    with pytest.raises(ValidationError):
        model.model_validate({**payloads[key], "timestamp": "2023-06-01T10:00:00"})


@pytest.mark.parametrize("missing", ["confidence", "method", "sources"])
def test_estimates_require_lineage(missing, payloads):
    data = {**payloads["reported"], "kind": "estimated", "confidence": 0.5, "method": "Test"}
    del data[missing]
    with pytest.raises(ValidationError):
        Provenance.model_validate(data)


def test_mixed_real_evidence_is_preserved(payloads):
    estimated = {
        **payloads["reported"],
        "kind": "estimated",
        "confidence": 0.5,
        "method": "Illustrative distance estimation method",
    }
    payloads["event"]["distance_m"] = {"value": 10.0, "provenance": estimated}
    event = ExposureEvent.model_validate(payloads["event"])
    assert event.rounds.provenance.kind == "self_reported"
    assert event.distance_m.provenance.kind == "estimated"
    assert event.peak_pressure.provenance.kind == "measured"


@pytest.mark.parametrize("kind", ["measured", "documented", "synthetic"])
def test_invalid_source_kind_combinations(kind, payloads):
    with pytest.raises(ValidationError):
        Provenance.model_validate({**payloads["reported"], "kind": kind})


def test_real_kind_cannot_hide_synthetic_source(payloads):
    with pytest.raises(ValidationError):
        Provenance.model_validate(
            {**payloads["synthetic"], "kind": "estimated", "confidence": 0.5, "method": "Test"}
        )


def test_synthetic_field_cannot_enter_real_record(payloads):
    payloads["event"]["rounds"]["provenance"] = payloads["synthetic"]
    with pytest.raises(ValidationError, match="synthetic and real"):
        ExposureEvent.model_validate(payloads["event"])


def test_empty_sources_and_duplicate_sources_fail(payloads):
    for sources in [[], [payloads["source"], payloads["source"]]]:
        with pytest.raises(ValidationError):
            Provenance.model_validate({**payloads["reported"], "sources": sources})


def test_estimated_pressure_cannot_be_reported_as_measured(payloads):
    payloads["event"]["peak_pressure"]["provenance"] = {
        **payloads["reported"],
        "kind": "estimated",
        "confidence": 0.5,
        "method": "Test",
    }
    with pytest.raises(ValidationError, match="must be measured"):
        ExposureEvent.model_validate(payloads["event"])


@pytest.mark.parametrize("availability", ["unknown", "unavailable"])
def test_pressure_requires_available_sensor(availability, payloads):
    with pytest.raises(ValidationError):
        ExposureEvent.model_validate({**payloads["event"], "sensor_availability": availability})


def test_sensor_reading_needs_a_measurement(payloads):
    with pytest.raises(ValidationError):
        SensorReading.model_validate(
            {**payloads["reading"], "peak_pressure": None, "impulse": None}
        )


def test_sensor_reading_rejects_reported_quantity(payloads):
    payloads["reading"]["peak_pressure"]["provenance"] = payloads["reported"]
    with pytest.raises(ValidationError):
        SensorReading.model_validate(payloads["reading"])


@pytest.mark.parametrize("angle", [-1, 360, math.nan])
def test_orientation_range(angle, payloads):
    payloads["event"]["orientation_degrees"] = {
        "value": angle,
        "provenance": payloads["reported"],
    }
    payloads["event"]["orientation_reference"] = "0 degrees faces source"
    with pytest.raises(ValidationError):
        ExposureEvent.model_validate(payloads["event"])


def test_orientation_requires_reference(payloads):
    payloads["event"]["orientation_degrees"] = {
        "value": 0.0,
        "provenance": payloads["reported"],
    }
    with pytest.raises(ValidationError, match="reference frame"):
        ExposureEvent.model_validate(payloads["event"])


def test_negative_distance_and_duration(payloads):
    for model, key, field in [
        (ExposureEvent, "event", "distance_m"),
        (SymptomReport, "symptoms", "duration_hours"),
    ]:
        with pytest.raises(ValidationError):
            model.model_validate(
                {
                    **payloads[key],
                    field: {"value": -1.0, "provenance": payloads["reported"]},
                }
            )


def test_symptom_unknown_is_distinct_from_absent(payloads):
    record = SymptomReport.model_validate({**payloads["symptoms"], "tinnitus": False})
    assert record.tinnitus is False
    assert record.dizziness is None


def test_contradictory_symptom_severity(payloads):
    with pytest.raises(ValidationError):
        SymptomReport.model_validate({**payloads["symptoms"], "severity": "none"})


def test_symptoms_require_self_report(payloads):
    with pytest.raises(ValidationError):
        SymptomReport.model_validate({**payloads["symptoms"], "provenance": payloads["measured"]})


@pytest.mark.parametrize("status", ["yes", "no"])
def test_known_tier1_requires_official_source(status, payloads):
    with pytest.raises(ValidationError):
        WeaponSystem.model_validate({**payloads["weapon"], "dod_tier1_status": status})
    record = WeaponSystem.model_validate(
        {
            **payloads["weapon"],
            "dod_tier1_status": status,
            "tier1_source": {
                "source_id": "test-policy",
                "source_type": "official",
                "citation": "Test policy fixture; not a real Tier-1 assertion",
            },
        }
    )
    assert record.dod_tier1_status == status


def test_records_are_frozen(payloads):
    record = ServiceMember.model_validate(payloads["member"])
    with pytest.raises(ValidationError, match="frozen"):
        record.member_id = "changed"


def test_generic_evidence_cannot_bypass_count_constraints(payloads):
    from blastbridge.models import Evidence

    payloads["event"]["rounds"] = Evidence[int](
        value=-1, provenance=Provenance.model_validate(payloads["reported"])
    )
    with pytest.raises(ValidationError):
        ExposureEvent.model_validate(payloads["event"])


def test_zero_measurement_and_unknown_counts_remain_distinct(payloads):
    payloads["event"]["rounds"] = None
    payloads["event"]["peak_pressure"]["value"] = 0.0
    event = ExposureEvent.model_validate(payloads["event"])
    assert event.rounds is None
    assert event.peak_pressure.value == 0.0
