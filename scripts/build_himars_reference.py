"""Build a deterministic fictional HIMARS date fixture, not a fitted tempo distribution."""

import csv
import hashlib
import io
import json
import random
from datetime import date, timedelta
from typing import Any

import numpy as np

from blastbridge.product.patterns import (
    ANOMALY_PERCENTILE,
    COVERAGE_RULE,
    DAYS_CAP,
    FEATURE_NAMES,
    MODEL_PARAMS,
    REFERENCE_DIR,
    occupational_features,
)

REFERENCE_SEED = 20261020
CAREERS_PER_RATE = 60
RATES = (4, 5)
CAREER_YEARS = 6
STEP_DAYS = 45
FIRST_WINDOW_OFFSET_DAYS = 365
CAREER_START = date(2015, 1, 1)
LABEL = "SME-INFORMED FICTIONAL HIMARS SCENARIO REFERENCE — NOT CLINICAL DATA"
CONSTRUCTION_ROUTE = (
    "A deterministic date-fixture builder is used because V5-2 executes independent "
    "binding_offsets "
    "draws and has no executable evenly_spaced algorithm for career-wide session placement. "
    "The simulation engine is unchanged."
)
ASSUMPTION = "prototype scenario assumption — not evidence"
REVISION_NOTE = (
    "v1 used even spacing with ±20-day jitter; it made max_events_14d constant and the reference "
    "unable to represent clustering, so pre-registered clustered/increase gates failed. "
    "v2 replaces only the placement assumption; gates and the 5th-percentile threshold "
    "are unchanged."
)


def constants() -> dict[str, Any]:
    return {
        "reference_seed": REFERENCE_SEED,
        "careers_per_rate": CAREERS_PER_RATE,
        "rates": list(RATES),
        "career_years": CAREER_YEARS,
        "step_days": STEP_DAYS,
        "first_window_offset_days": FIRST_WINDOW_OFFSET_DAYS,
        "career_start": CAREER_START.isoformat(),
        "career_start_offset_days": [0, 364],
        "year_days": 365,
        "rate_assignment": "each career retains one endpoint rate for all six fictional years",
        "placement": (
            "k distinct days drawn uniformly within each fictional year "
            "(least-informative placement given only a per-year count)"
        ),
        "seed_derivation": (
            "first 8 SHA256 bytes of colon-separated seed:career:year:event; "
            "event=0 for the per-year placement draw, year=event=-1 for the career offset"
        ),
        "unit_mapping": "one fictional period/session equals one fictional occupational event day",
    }


def derived_seed(career: int, year: int, event: int) -> int:
    text = f"{REFERENCE_SEED}:{career}:{year}:{event}"
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def build_careers() -> list[tuple[date, tuple[date, ...]]]:
    """Dates only; rate endpoints are source-bound, placement is a prototype assumption."""
    careers = []
    for rate_index, rate in enumerate(RATES):
        for index in range(CAREERS_PER_RATE):
            career = rate_index * CAREERS_PER_RATE + index
            offset = random.Random(derived_seed(career, -1, -1)).randint(0, 364)
            start = CAREER_START + timedelta(days=offset)
            days = set()
            for year in range(CAREER_YEARS):
                offsets = random.Random(derived_seed(career, year, 0)).sample(range(365), rate)
                for day_offset in offsets:
                    days.add(start + timedelta(days=year * 365 + day_offset))
            careers.append((start, tuple(sorted(days))))
    return careers


def build_reference_rows() -> list[tuple[float, ...]]:
    """Pure construction: identical constants produce identical date-feature rows."""
    rows = []
    for start, days in build_careers():
        for offset in range(FIRST_WINDOW_OFFSET_DAYS, CAREER_YEARS * 365 + 1, STEP_DAYS):
            rows.append(occupational_features(days, start + timedelta(days=offset)))
    return rows


def reference_csv(rows: list[tuple[float, ...]]) -> str:
    handle = io.StringIO(newline="")
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(FEATURE_NAMES)
    writer.writerows([[f"{value:.6f}" for value in row] for row in rows])
    return handle.getvalue()


def reference_fingerprint(csv_bytes: bytes) -> dict[str, str]:
    canonical = json.dumps(constants(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "reference_features_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "builder_constants_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def main() -> None:
    rows = build_reference_rows()
    csv_text = reference_csv(rows)
    values = np.asarray(rows, dtype=np.float64)
    evidence_path = REFERENCE_DIR.parents[2] / "data/reference/training_tempo_evidence.json"
    records = json.loads(evidence_path.read_text(encoding="utf-8"))["records"]
    evidence = next(r for r in records if r["tempo_evidence_id"] == "tempo-sme-active-himars")
    limitations = [
        *evidence["limitations"],
        evidence["notes"],
        evidence["claim"]["uncertainty"],
        evidence["claim"]["estimated_frequency"]["interpretation"],
        evidence["mapping_note"],
        evidence["representativeness_basis"],
        "support level E, source_only, distribution_family none",
    ]
    assumptions = {
        key: {"value": value, "basis": ASSUMPTION}
        for key, value in constants().items()
        if key != "rates"
    }
    assumptions["rates"] = {
        "value": list(RATES),
        "basis": "source-bound endpoints of approximately 4–5 per year; not a fitted distribution",
    }
    yearly_counts = [
        sum(
            start + timedelta(days=y * 365) <= day < start + timedelta(days=(y + 1) * 365)
            for day in days
        )
        for start, days in build_careers()
        for y in range(CAREER_YEARS)
    ]
    metadata = {
        "label": LABEL,
        "construction_route": CONSTRUCTION_ROUTE,
        "revision_note": REVISION_NOTE,
        "evidence_id": "tempo-sme-active-himars",
        "prior_design_id": "design-sme-active-himars",
        "source_wording": evidence["source_wording"],
        "representativeness": evidence["representativeness"],
        "source_limitations": limitations,
        "scenario_assumptions": assumptions,
        "unit_mapping": f"{constants()['unit_mapping']} — {ASSUMPTION}",
        "independent_fictional_careers": len(RATES) * CAREERS_PER_RATE,
        "repeated_analysis_windows": len(rows),
        "observation_note": (
            "Windows are repeated observations of the same fictional careers, "
            "not independent subjects."
        ),
        "sessions_per_career_year": {
            "mean": float(np.mean(yearly_counts)),
            "median": float(np.median(yearly_counts)),
        },
        "zero_share": {
            name: float(np.mean(values[:, i] == 0)) for i, name in enumerate(FEATURE_NAMES[:3])
        },
        "feature_summaries": {
            name: dict(
                zip(
                    ("median", "q25", "q75"),
                    map(float, np.percentile(values[:, i], [50, 25, 75])),
                    strict=True,
                )
            )
            for i, name in enumerate(FEATURE_NAMES)
        },
        "fingerprint": reference_fingerprint(csv_text.encode("utf-8")),
        "model_params": MODEL_PARAMS,
        "anomaly_percentile": ANOMALY_PERCENTILE,
        "threshold_rule": (
            "prototype analytic threshold: 5th percentile of reference score_samples; "
            "not clinical, blast or injury"
        ),
        "sklearn_version_pinned": "1.6.1",
        "coverage_rule": COVERAGE_RULE,
        "feature_names": FEATURE_NAMES,
        "days_cap": DAYS_CAP,
    }
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    (REFERENCE_DIR / "reference_features.csv").write_text(csv_text, encoding="utf-8", newline="\n")
    (REFERENCE_DIR / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {len(rows)} fictional HIMARS scenario reference windows.")


if __name__ == "__main__":
    main()
