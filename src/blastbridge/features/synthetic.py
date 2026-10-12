"""Non-medical future feature contracts; no feature calculations are implemented."""

from blastbridge.simulation.models import FeatureContract, FeatureName

FEATURE_CONTRACTS = (
    FeatureContract(
        name=FeatureName.CAREER_DURATION,
        unit="days",
        source_tables=("synthetic_members",),
        definition="Elapsed calendar days between service start and end.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.ASSIGNMENT_DURATION,
        unit="days",
        source_tables=("synthetic_assignments",),
        definition="Elapsed calendar days between assignment start and end.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.TOTAL_FIRING_EVENTS,
        unit="events",
        source_tables=("synthetic_firing_events",),
        definition="Count distinct physical firing-event identities.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.PARTICIPANT_EXPOSURE_EVENTS,
        unit="person-event records",
        source_tables=("synthetic_participant_exposures",),
        definition="Count a member's event associations; never rename as unit rounds.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.EVENTS_LAST_7D,
        unit="events",
        source_tables=("synthetic_firing_events",),
        definition="Physical event count in an explicitly defined trailing seven-day window.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.EVENTS_LAST_30D,
        unit="events",
        source_tables=("synthetic_firing_events",),
        definition="Physical event count in an explicitly defined trailing thirty-day window.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.EVENTS_LAST_365D,
        unit="events",
        source_tables=("synthetic_firing_events",),
        definition="Physical event count in an explicitly defined trailing 365-day window.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.TIME_SINCE_LAST_EVENT,
        unit="seconds",
        source_tables=("synthetic_firing_events",),
        definition="Elapsed time from a supplied reference instant to latest event.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.WEAPON_FAMILY_COUNTS,
        unit="events by family",
        source_tables=("synthetic_firing_events",),
        definition="Distinct physical firing-event counts grouped by declared family.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.ROLE_SPECIFIC_COUNTS,
        unit="person-event records by role",
        source_tables=("synthetic_participant_exposures",),
        definition="Participant-event record counts grouped by participant role.",
        medical_or_injury_inference=False,
    ),
    FeatureContract(
        name=FeatureName.TRAINING_DENSITY,
        unit="events per explicitly declared interval",
        source_tables=("synthetic_training_periods", "synthetic_firing_events"),
        definition="Physical event count divided by an explicitly declared training interval.",
        medical_or_injury_inference=False,
    ),
)
