"""Report fictional intake cases; deterministic mode makes no network calls."""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.product.agent import (
    GOLDEN_NARRATIVE,
    REPLAY_PATH,
    IntakeResult,
    ProviderTurn,
    ScriptedProvider,
    replay_record,
    run_intake,
)
from blastbridge.product.anthropic_provider import AnthropicProvider, live_available
from blastbridge.product.seed import DEMO_PEOPLE

ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "examples/fictional/intake/eval_cases.json"


def scripted(case: dict[str, Any]) -> ScriptedProvider:
    turns = []
    queries = case.get("stub_tool_queries", [])
    if queries:
        blocks = [
            {"type": "tool_use", "id": f"lookup-{i}", "name": name, "input": {"query": query}}
            for i, (name, query) in enumerate(queries)
        ]
        turns.append(ProviderTurn("tool_use", blocks, blocks, "deterministic-stub"))
    blocks = [{"type": "text", "text": json.dumps(case["stub_proposal"])}]
    turns.append(ProviderTurn("end_turn", blocks, blocks, "deterministic-stub"))
    return ScriptedProvider(turns)


def check(case: dict[str, Any], result: IntakeResult) -> list[str]:
    expected = case["expect"]
    reasons = []
    if result.error:
        reasons.append(result.error)
    if (result.draft is not None) != expected["draft_valid"]:
        reasons.append("draft validity differs")
    if any(issue.blocking for issue in result.issues) != expected["blocking"]:
        reasons.append("blocking issues differ")
    if result.form_values.get("f_weapon") != expected["weapon_system_id"]:
        reasons.append("weapon differs")
    if result.proposal is None:
        reasons.append("no structured proposal")
        return reasons
    if len(result.proposal.crews) != expected["crews"]:
        reasons.append("crew count differs")
    if [crew.count_status for crew in result.proposal.crews] != expected["count_status"]:
        reasons.append("count interpretation differs")
    for i, positions in enumerate(expected["person_ids"]):
        for position, person_id in positions.items():
            if result.form_values.get(f"f_c{i}_{position}") != person_id:
                reasons.append(f"crew {i + 1} {position} differs")
    issue_text = " ".join(issue.message for issue in result.issues).lower()
    for fragment in expected.get("issue_contains", []):
        if fragment.lower() not in issue_text:
            reasons.append(f"missing issue: {fragment}")
    output = json.dumps(result.proposal.model_dump(mode="json")).lower()
    if result.draft:
        output += result.draft.model_dump_json().lower()
    for word in expected.get("forbidden_output_words", []):
        if word in output:
            reasons.append("non-training content in proposal")
    return reasons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["record-golden"])
    parser.add_argument("--mode", choices=["deterministic", "live"], default="deterministic")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    live = args.mode == "live" or args.command == "record-golden"
    if live and not live_available():
        print("Live intake unavailable. Configure ANTHROPIC_API_KEY and install the app extra.")
        return
    dataset = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    catalog = load_weapon_catalog(ROOT / "data/reference/weapons.json")
    if args.command == "record-golden":
        today = date.today()
        result = run_intake(GOLDEN_NARRATIVE, AnthropicProvider(), catalog, DEMO_PEOPLE, today)
        reasons = check(cases[0], result)
        if result.error or result.draft is None or reasons:
            print("Replay not recorded: " + "; ".join(reasons or ["draft is not valid"]))
            return
        REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPLAY_PATH.write_text(
            json.dumps(replay_record(result, today), indent=2) + "\n",
            encoding="utf-8",
        )
        print("Recorded the validated fictional golden replay.")
        return
    today = date.fromisoformat(dataset["reference_date"])
    lines = [
        "| Case | Title | Expected | Actual | Result | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    passed = 0
    for case in cases:
        provider = AnthropicProvider() if live else scripted(case)
        result = run_intake(case["narrative"], provider, catalog, DEMO_PEOPLE, today)
        reasons = check(case, result)
        passed += not reasons
        expected = "valid draft" if case["expect"]["draft_valid"] else "needs review"
        actual = (
            "error"
            if result.error
            else ("valid draft" if result.draft is not None else "needs review")
        )
        reason = "; ".join(reasons).replace("|", "/").replace("\n", " ") or "matches"
        lines.append(
            f"| {case['id']} | {case['title']} | {expected} | {actual} | "
            f"{'FAIL' if reasons else 'PASS'} | {reason} |"
        )
    lines.append(f"\n{passed}/{len(cases)} cases passed.")
    report = "\n".join(lines) + "\n"
    print(report)
    if args.write:
        path = CASE_PATH.parent / f"eval_report_{args.mode}.md"
        path.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
