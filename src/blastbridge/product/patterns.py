"""Compare recorded HIMARS cadence with an SME-informed fictional scenario reference."""

from __future__ import annotations

import csv
import json
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from .models import HistoryEntry

if TYPE_CHECKING:
    from sklearn.ensemble import IsolationForest

FEATURE_NAMES = (
    "events_30d",
    "events_90d",
    "events_365d",
    "days_since_previous_event",
    "max_events_14d",
    "recent_vs_earlier_cadence",
)
FEATURE_LABELS = {
    "events_30d": "Occupational events in prior 30 days",
    "events_90d": "Occupational events in prior 90 days",
    "events_365d": "Occupational events in prior 365 days",
    "days_since_previous_event": "Days since previous occupational event",
    "max_events_14d": "Most occupational events within any 14-day period (prior 365 days)",
    "recent_vs_earlier_cadence": "Recent cadence minus earlier cadence (events per 30 days)",
}
DAYS_CAP = 730
ANOMALY_PERCENTILE = 5.0
ELEVATION_QUANTILE = 0.95
ELEVATION_FEATURES = (
    "events_30d",
    "events_90d",
    "events_365d",
    "max_events_14d",
    "recent_vs_earlier_cadence",
)
MODEL_PARAMS = {"n_estimators": 100, "random_state": 20261019}
BASELINE_DIR = Path(__file__).resolve().parents[3] / "examples/fictional/ml-baseline"
REFERENCE_DIR = Path(__file__).resolve().parents[3] / "examples/fictional/ml-reference-himars"
REFERENCE_LABEL = "SME-informed prototype HIMARS scenario reference"
HIMARS_SCOPE = {"m142-himars"}
COVERAGE_RULE = (
    "A comparison requires HIMARS-scope records beginning at least 365 days before analysis_as_of "
    "and at least one HIMARS event day in (analysis_as_of - 365 days, analysis_as_of]. "
    "This is an analytic coverage rule, not a medical threshold."
)
DELIBERATELY_EXCLUDED = {
    "unknown-count fraction": (
        "The prototype HIMARS scenario reference models dates only, with no count missingness. "
        "Unknown activity counts are reported as data-quality notes instead."
    ),
    "distinct weapon families": (
        "The prototype HIMARS scenario reference covers HIMARS only, so the feature is constant."
    ),
    "physical-event counts": (
        "Not comparable across weapon families; the prototype reference contains dates only."
    ),
    "symptoms, medical and demographic fields": "Excluded by design.",
}
PATTERN_DISCLAIMER = (
    "This compares recorded HIMARS occupational cadence with an SME-informed prototype "
    "HIMARS scenario reference. "
    "It is not a medical risk score."
)
CONTEXT_NOTE = (
    "These values provide context for the pattern result. They are not medical risk factors "
    "and do not establish injury."
)
DIFFERING_HEADING = "Features that differ from the prototype HIMARS scenario reference"
BASELINE_LABEL = "FICTIONAL SIMULATION BASELINE — NOT CLINICAL DATA"
ELEVATION_RULE_TEXT = (
    "Prototype interpretation rule: an atypical comparison is 'elevated' only when at least "
    "one recent-activity feature (30/90/365-day events, most events in 14 days, "
    "recent-minus-earlier cadence) exceeds the 95th percentile of the SME-informed prototype "
    "HIMARS scenario reference. Not clinical."
)
REDUCED_TEXT = (
    "Recorded occupational activity is atypical in a lower/reduced direction relative to the "
    "SME-informed prototype HIMARS scenario reference."
)
OBSERVATION_NOTE = "This is an occupational-pattern observation, not a medical risk result."


def occupational_features(event_days: Iterable[date], analysis_as_of: date) -> tuple[float, ...]:
    """Distinct event days only; windows exclude their lower endpoint and include the upper."""
    days = sorted({day for day in event_days if day <= analysis_as_of})
    totals = [
        len(days) - bisect_right(days, analysis_as_of - timedelta(days=window))
        for window in (30, 90, 365)
    ]
    yearly = [day for day in days if day > analysis_as_of - timedelta(days=365)]
    previous = min((analysis_as_of - days[-1]).days, DAYS_CAP) if days else DAYS_CAP
    most = max(
        (bisect_right(days, day) - bisect_right(days, day - timedelta(days=14)) for day in yearly),
        default=0,
    )
    cadence = totals[1] / 3 - (totals[2] - totals[1]) / 9
    return tuple(float(value) for value in (*totals, previous, most, cadence))


def unknown_count_fraction(entries: Sequence[HistoryEntry], analysis_as_of: date) -> float | None:
    """Data quality only; missing activity counts never enter the feature vector."""
    recent = [
        entry
        for entry in entries
        if analysis_as_of - timedelta(days=365) < entry.event_date <= analysis_as_of
    ]
    if not recent:
        return None
    return sum(entry.physical_event_count is None for entry in recent) / len(recent)


def load_baseline() -> tuple[NDArray[np.float64], dict[str, Any]]:
    """Load the V0.5 sparse demo scenario for secondary stress testing only."""
    with (BASELINE_DIR / "baseline_features.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        if tuple(next(reader, ())) != FEATURE_NAMES:
            raise ValueError(
                "V0.5 sparse demo scenario (secondary stress-test data, not the readiness "
                "reference) feature header does not match"
            )
        rows = np.asarray([[float(value) for value in row] for row in reader], dtype=np.float64)
    metadata = json.loads((BASELINE_DIR / "metadata.json").read_text(encoding="utf-8"))
    return rows, metadata


def load_reference() -> tuple[NDArray[np.float64], dict[str, Any]]:
    with (REFERENCE_DIR / "reference_features.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        if tuple(next(reader, ())) != FEATURE_NAMES:
            raise ValueError("fictional HIMARS scenario reference feature header does not match")
        rows = np.asarray([[float(value) for value in row] for row in reader], dtype=np.float64)
    metadata = json.loads((REFERENCE_DIR / "metadata.json").read_text(encoding="utf-8"))
    return rows, metadata


@dataclass(frozen=True)
class PatternModel:
    forest: IsolationForest
    threshold: float
    summaries: dict[str, dict[str, float]]
    baseline_rows: int
    metadata: dict[str, Any]
    elevation_bounds: dict[str, float]


def fit_pattern_model(rows: NDArray[np.float64], metadata: dict[str, Any]) -> PatternModel:
    from sklearn.ensemble import IsolationForest

    if rows.ndim != 2 or rows.shape[1] != len(FEATURE_NAMES) or rows.shape[0] == 0:
        raise ValueError("fictional HIMARS scenario reference must contain six-feature rows")
    if not np.isfinite(rows).all():
        raise ValueError("fictional HIMARS scenario reference features must be finite")
    forest = IsolationForest(**MODEL_PARAMS)
    forest.fit(rows)
    scores = np.asarray(forest.score_samples(rows), dtype=np.float64)
    quantiles = np.percentile(rows, [50, 25, 75, 5, 95], axis=0)
    summaries = {
        name: {
            key: float(quantiles[q, i])
            for q, key in enumerate(("median", "q25", "q75", "p5", "p95"))
        }
        for i, name in enumerate(FEATURE_NAMES)
    }
    return PatternModel(
        forest=forest,
        threshold=float(np.percentile(scores, ANOMALY_PERCENTILE)),
        summaries=summaries,
        baseline_rows=len(rows),
        metadata=metadata,
        elevation_bounds={
            name: float(np.quantile(rows[:, FEATURE_NAMES.index(name)], ELEVATION_QUANTILE))
            for name in ELEVATION_FEATURES
        },
    )


class PatternStatus(StrEnum):
    PATTERN_NOT_AVAILABLE = "pattern_not_available"
    TYPICAL_RECORDED_PATTERN = "typical_recorded_pattern"
    ATYPICAL_REDUCED_ACTIVITY = "atypical_reduced_activity"
    ATYPICAL_ELEVATED_ACTIVITY = "atypical_elevated_activity"

    @property
    def label(self) -> str:
        return {
            self.TYPICAL_RECORDED_PATTERN: "Typical recorded pattern",
            self.ATYPICAL_REDUCED_ACTIVITY: "Unusual lower activity pattern — informational only",
            self.ATYPICAL_ELEVATED_ACTIVITY: "Atypical elevated occupational cadence",
            self.PATTERN_NOT_AVAILABLE: (
                "Not enough applicable recorded history for this prototype comparison."
            ),
        }[self]


@dataclass(frozen=True)
class FeatureComparison:
    name: str
    label: str
    value: float
    median: float
    q25: float
    q75: float
    outside_central_range: bool


@dataclass(frozen=True)
class PatternResult:
    status: PatternStatus
    score: float | None
    threshold: float | None
    analysis_as_of: date
    comparisons: tuple[FeatureComparison, ...]
    differing: tuple[FeatureComparison, ...]
    anomalous: bool
    elevated_features: tuple[str, ...]
    reason: str | None = None
    excluded_non_scope_records: int = 0


def assess_pattern(
    model: PatternModel | None, entries: Sequence[HistoryEntry], analysis_as_of: date
) -> PatternResult:
    visible = [entry for entry in entries if entry.event_date <= analysis_as_of]
    days = sorted({entry.event_date for entry in visible if entry.weapon_system_id in HIMARS_SCOPE})
    excluded = sum(entry.weapon_system_id not in HIMARS_SCOPE for entry in visible)
    lower = analysis_as_of - timedelta(days=365)
    reason = None
    if model is None:
        reason = "pattern reference unavailable"
    elif not days:
        reason = "outside the HIMARS prototype scope"
    elif days[0] > lower:
        reason = "recorded history shorter than the 365-day comparison window"
    elif not any(day > lower for day in days):
        reason = "no HIMARS record in the prior 365 days"
    if reason is not None:
        return PatternResult(
            status=PatternStatus.PATTERN_NOT_AVAILABLE,
            score=None,
            threshold=None,
            analysis_as_of=analysis_as_of,
            comparisons=(),
            differing=(),
            anomalous=False,
            elevated_features=(),
            reason=reason,
            excluded_non_scope_records=excluded,
        )
    assert model is not None
    features = occupational_features(days, analysis_as_of)
    score = float(model.forest.score_samples(np.asarray([features], dtype=np.float64))[0])
    anomalous = score < model.threshold
    elevated_features = (
        tuple(
            name
            for name in ELEVATION_FEATURES
            if features[FEATURE_NAMES.index(name)] > model.elevation_bounds[name]
        )
        if anomalous
        else ()
    )
    status = PatternStatus.TYPICAL_RECORDED_PATTERN
    if anomalous:
        status = (
            PatternStatus.ATYPICAL_ELEVATED_ACTIVITY
            if elevated_features
            else PatternStatus.ATYPICAL_REDUCED_ACTIVITY
        )
    comparisons = tuple(
        FeatureComparison(
            name=name,
            label=FEATURE_LABELS[name],
            value=value,
            median=model.summaries[name]["median"],
            q25=model.summaries[name]["q25"],
            q75=model.summaries[name]["q75"],
            outside_central_range=(
                value < model.summaries[name]["p5"] or value > model.summaries[name]["p95"]
            ),
        )
        for name, value in zip(FEATURE_NAMES, features, strict=True)
    )
    differing = sorted(
        (comparison for comparison in comparisons if comparison.outside_central_range),
        key=lambda comparison: (
            abs(comparison.value - comparison.median)
            / max(
                model.summaries[comparison.name]["p95"] - model.summaries[comparison.name]["p5"],
                1,
            )
        ),
        reverse=True,
    )[:3]
    return PatternResult(
        status=status,
        score=score,
        threshold=model.threshold,
        analysis_as_of=analysis_as_of,
        comparisons=comparisons,
        differing=tuple(differing),
        anomalous=anomalous,
        elevated_features=elevated_features,
        excluded_non_scope_records=excluded,
    )
