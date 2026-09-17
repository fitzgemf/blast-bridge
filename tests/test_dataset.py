from copy import deepcopy

import pytest
from pydantic import ValidationError

from blastbridge.validation import ResearchDataset


def batch(payloads):
    return {
        "members": [payloads["member"]],
        "assignments": [payloads["assignment"]],
        "weapons": [payloads["weapon"]],
        "exposures": [payloads["event"]],
        "sensor_readings": [payloads["reading"]],
        "symptom_reports": [payloads["symptoms"]],
    }


def test_linked_dataset_and_post_service_symptoms(payloads):
    data = ResearchDataset.model_validate(batch(payloads))
    assert len(data.exposures) == 1
    assert data.symptom_reports[0].timestamp.date() > data.members[0].service_end
    assert ResearchDataset.model_validate_json(data.model_dump_json()) == data


@pytest.mark.parametrize(
    "collection",
    [
        "members",
        "assignments",
        "weapons",
        "exposures",
        "sensor_readings",
        "symptom_reports",
    ],
)
def test_duplicate_ids(collection, payloads):
    data = batch(payloads)
    data[collection].append(deepcopy(data[collection][0]))
    with pytest.raises(ValidationError, match="duplicate"):
        ResearchDataset.model_validate(data)


@pytest.mark.parametrize(
    ("key", "field", "value"),
    [
        ("assignment", "member_id", "missing"),
        ("assignment", "weapon_system_ids", ["missing"]),
        ("assignment", "start_date", "2019-01-01"),
        ("assignment", "end_date", "2026-01-01"),
        ("assignment", "end_date", None),
        ("event", "member_id", "missing"),
        ("event", "weapon_system_id", "missing"),
        ("event", "assignment_id", "missing"),
        ("event", "timestamp", "2019-01-01T00:00:00Z"),
        ("event", "timestamp", "2020-06-01T00:00:00Z"),
        ("reading", "member_id", "missing"),
        ("reading", "exposure_id", "missing"),
        ("symptoms", "member_id", "missing"),
        ("symptoms", "exposure_id", "missing"),
    ],
)
def test_invalid_links_and_dates(key, field, value, payloads):
    payloads[key][field] = value
    with pytest.raises(ValidationError):
        ResearchDataset.model_validate(batch(payloads))


@pytest.mark.parametrize(
    ("collection", "field"),
    [
        ("exposures", "assignment_id"),
        ("sensor_readings", "exposure_id"),
        ("symptom_reports", "exposure_id"),
    ],
)
def test_cross_member_links(collection, field, payloads):
    data = batch(payloads)
    data["members"].append({**payloads["member"], "member_id": "member-2"})
    data[collection][0]["member_id"] = "member-2"
    assert data[collection][0][field] is not None
    with pytest.raises(ValidationError, match="another member"):
        ResearchDataset.model_validate(data)


def test_synthetic_assignment_cannot_link_to_real_member(payloads):
    payloads["assignment"]["provenance"] = payloads["synthetic"]
    with pytest.raises(ValidationError, match="synthetic and real"):
        ResearchDataset.model_validate(batch(payloads))


def test_linked_sensor_requires_availability(payloads):
    payloads["event"].update(peak_pressure=None, impulse=None, sensor_availability="unavailable")
    with pytest.raises(ValidationError, match="sensor availability"):
        ResearchDataset.model_validate(batch(payloads))


def test_empty_dataset_is_valid():
    assert ResearchDataset().members == ()


def test_real_and_synthetic_members_require_separate_batches(payloads):
    data = batch(payloads)
    data["members"].append(
        {
            **payloads["member"],
            "member_id": "synthetic-member",
            "provenance": payloads["synthetic"],
        }
    )
    with pytest.raises(ValidationError, match="separate datasets"):
        ResearchDataset.model_validate(data)


def test_explicit_synthetic_schema_records_are_supported(payloads):
    # Validation fixtures only: this is not a career generator or research dataset.
    data = batch(payloads)
    for collection in ("members", "assignments", "exposures", "sensor_readings", "symptom_reports"):
        for record in data[collection]:
            record["provenance"] = payloads["synthetic"]
            for field in ("rounds", "peak_pressure", "impulse"):
                if field in record:
                    record[field]["provenance"] = payloads["synthetic"]
    assert ResearchDataset.model_validate(data).members[0].provenance.kind == "synthetic"
