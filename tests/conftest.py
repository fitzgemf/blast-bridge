from copy import deepcopy

import pytest


@pytest.fixture
def payloads():
    report_source = {
        "source_id": "report-1",
        "source_type": "retrospective_self_report",
        "citation": "Unit-test report, not participant data",
    }
    reported = {"kind": "self_reported", "sources": [report_source]}
    measured = {
        "kind": "measured",
        "sources": [
            {
                "source_id": "sensor-1",
                "source_type": "sensor",
                "citation": "Unit-test sensor, not a field measurement",
            }
        ],
    }
    synthetic = {
        "kind": "synthetic",
        "sources": [
            {
                "source_id": "synthetic-1",
                "source_type": "synthetic",
                "citation": "Unit-test fixture only",
            }
        ],
    }
    pressure = {"value": 1.0, "unit": "kPa", "provenance": measured}
    impulse = {"value": 0.5, "unit": "Pa*s", "provenance": measured}
    return deepcopy(
        {
            "source": report_source,
            "reported": reported,
            "measured": measured,
            "synthetic": synthetic,
            "pressure": pressure,
            "impulse": impulse,
            "member": {
                "member_id": "member-1",
                "branch": "army",
                "component": "active",
                "service_start": "2020-01-01",
                "service_end": "2025-12-31",
                "provenance": reported,
            },
            "assignment": {
                "assignment_id": "assignment-1",
                "member_id": "member-1",
                "mos": "test-specialty",
                "start_date": "2021-01-01",
                "end_date": "2024-12-31",
                "weapon_system_ids": ["test-weapon"],
                "provenance": reported,
            },
            "weapon": {
                "weapon_system_id": "test-weapon",
                "name": "Unit-test system",
                "family": "other",
                "source": {
                    "source_id": "catalog-test",
                    "source_type": "assumption",
                    "citation": "Test taxonomy",
                },
            },
            "event": {
                "exposure_id": "event-1",
                "member_id": "member-1",
                "assignment_id": "assignment-1",
                "timestamp": "2023-06-01T10:00:00-04:00",
                "weapon_system_id": "test-weapon",
                "rounds": {"value": 2, "provenance": reported},
                "sensor_availability": "available",
                "peak_pressure": pressure,
                "impulse": impulse,
                "provenance": reported,
            },
            "reading": {
                "reading_id": "reading-1",
                "member_id": "member-1",
                "exposure_id": "event-1",
                "timestamp": "2023-06-01T10:00:00-04:00",
                "sensor_type": "unit-test sensor",
                "peak_pressure": pressure,
                "impulse": impulse,
                "provenance": measured,
            },
            "symptoms": {
                "report_id": "report-1",
                "member_id": "member-1",
                "exposure_id": "event-1",
                "timestamp": "2026-01-01T10:00:00-04:00",
                "headache": True,
                "severity": "mild",
                "provenance": reported,
            },
        }
    )
