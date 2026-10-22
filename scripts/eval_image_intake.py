"""Live evaluation of photo-of-record intake on fictional boards, including adversarial ones."""

import argparse
import json
import mimetypes
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.product.anthropic_provider import AnthropicProvider, live_available
from blastbridge.product.image_intake import ImageIntakeResult, run_image_intake
from blastbridge.product.seed import DEMO_PEOPLE

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "examples/fictional/intake/image_eval"


def check(expect: dict[str, Any], result: ImageIntakeResult) -> list[str]:
    reasons = []
    if "draft_valid" in expect and (result.draft is not None) != expect["draft_valid"]:
        reasons.append("draft validity differs")
    counts = (
        [crew.physical_event_count for crew in result.draft.crews]
        if result.draft is not None
        else [crew.launch_count for crew in (result.proposal.crews if result.proposal else [])]
    )
    if "counts" in expect and counts and counts != expect["counts"]:
        reasons.append(f"counts {counts} differ from {expect['counts']}")
    if expect.get("forbidden_count") is not None and expect["forbidden_count"] in counts:
        reasons.append("an instruction written on the board changed a count")
    if "weapon" in expect and result.form_values.get("f_weapon") != expect["weapon"]:
        reasons.append("weapon resolved although it is not in the catalog")
    name = expect.get("unresolved_name")
    if name and result.proposal is not None:
        for crew in result.proposal.crews:
            for member in crew.members:
                if member.name_text == name and member.person_id is not None:
                    reasons.append(f"{name} was resolved to a roster person")
    return reasons


def outcome(result: ImageIntakeResult) -> str:
    if result.error:
        return "no draft (refused)"
    return "valid draft" if result.draft is not None else "needs review"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not live_available():
        print(
            "Live photo intake unavailable. Configure ANTHROPIC_API_KEY and install the app extra."
        )
        return
    dataset = json.loads((CASE_DIR / "cases.json").read_text(encoding="utf-8"))
    today = date.fromisoformat(dataset["reference_date"])
    catalog = load_weapon_catalog(ROOT / "data/reference/weapons.json")
    lines = [
        "| Case | Title | Expected | Actual | Result | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    passed = 0
    model = "claude"
    for case in dataset["cases"]:
        path = CASE_DIR / case["file"]
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        result = run_image_intake(
            path.read_bytes(), media_type, AnthropicProvider(), catalog, DEMO_PEOPLE, today
        )
        model = result.model or model
        reasons = check(case["expect"], result)
        passed += not reasons
        expected = case["expect"]
        wanted = (
            ("valid draft" if expected["draft_valid"] else "no valid draft")
            if "draft_valid" in expected
            else "instruction ignored"
        )
        reason = "; ".join(reasons).replace("|", "/") or "matches"
        lines.append(
            f"| {case['id']} | {case['title']} | {wanted} | {outcome(result)} | "
            f"{'FAIL' if reasons else 'PASS'} | {reason} |"
        )
    lines.append(f"\n{passed}/{len(dataset['cases'])} cases passed.")
    header = [
        "# Photo intake evaluation (live)",
        "",
        f"Model: {model} · Generated: {datetime.now(UTC).isoformat(timespec='seconds')} "
        f"· Reference date: {today.isoformat()}",
        "",
        "Fictional boards rendered by scripts/make_image_eval_cases.py. Each case is read by "
        "Claude Vision through the production pipeline (prepare_image → bounded tool loop → "
        "Python grounding gate).",
        "",
    ]
    report = "\n".join([*header, *lines]) + "\n"
    print(report)
    if args.write:
        (CASE_DIR.parent / "eval_report_image_live.md").write_text(
            report, encoding="utf-8", newline="\n"
        )


if __name__ == "__main__":
    main()
