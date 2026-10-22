"""Live evaluation of Ask BlastBridge on the fictional demo requests (grounding and citations)."""

import argparse
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from blastbridge.data.catalog import load_weapon_catalog
from blastbridge.product import store
from blastbridge.product.analyst import AgentContext, Conversation, ask, load_analyst_replay
from blastbridge.product.analyst_tools import AnalystData
from blastbridge.product.anthropic_provider import AnthropicProvider, live_available
from blastbridge.product.briefing import brief_citations
from blastbridge.product.patterns import fit_pattern_model, load_reference
from blastbridge.product.seed import DEMO_EVENTS, DEMO_PEOPLE, DEMO_SOURCE_DRAFTS, DEMO_SYMPTOMS

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples/fictional/analyst/eval_report_live.md"
# Single-step suggested requests; log_event is multi-turn and creates drafts, so it is excluded.
CASES = ("reese_brief", "reese_missing", "jordan_brief", "attention", "shared_event")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not live_available():
        print("Live analyst unavailable. Configure ANTHROPIC_API_KEY and install the app extra.")
        return
    lines = [
        "| Request | Intent | Outcome | Safety guard | Citations resolved | Turns | Time |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    passed = 0
    model = "claude"
    with tempfile.TemporaryDirectory() as folder:
        conn = store.connect(Path(folder) / "eval.sqlite")
        store.init_db(conn)
        store.seed_people(conn, DEMO_PEOPLE)
        store.seed_demo_events(conn, DEMO_EVENTS)
        store.seed_demo_symptoms(conn, DEMO_SYMPTOMS)
        store.seed_demo_drafts(conn, DEMO_SOURCE_DRAFTS)
        data = AnalystData.from_connection(
            conn,
            fit_pattern_model(*load_reference()),
            load_weapon_catalog(ROOT / "data/reference/weapons.json"),
        )
        for name in CASES:
            fixture = load_analyst_replay(name)
            context = AgentContext(
                analysis_as_of=fixture.analysis_as_of,
                reference_date=fixture.reference_date,
                selected_person_id=fixture.selected_person_id,
                page=fixture.page,
            )
            started = time.monotonic()
            run = ask(
                fixture.steps[0].utterance,
                context=context,
                data=data,
                provider=AnthropicProvider(),
                intake_provider=AnthropicProvider(),
                conversation=Conversation(f"eval-{name}"),
                ledger={},
            )
            elapsed = time.monotonic() - started
            model = run.model or model
            response = run.response
            cited = "n/a"
            codes = sorted({item.code for item in run.validation})
            guarded = run.fallback and codes == ["MEDICAL_CONTENT"]
            ok = run.grounded and response is not None and (not run.validation or guarded)
            outcome = "grounded" if run.grounded else "NOT grounded"
            guard = (
                "medical wording withheld; deterministic text shown"
                if guarded
                else (", ".join(codes) if codes else "none needed")
            )
            if response is not None and response.brief is not None:
                citations, _ = brief_citations(response.brief, run.evidence, response.person_id)
                missing = sum(citation.kind == "unavailable" for citation in citations)
                cited = f"{len(citations) - missing}/{len(citations)}"
                ok = ok and missing == 0
            passed += ok
            lines.append(
                f"| {fixture.steps[0].utterance} | {response.intent if response else 'none'} | "
                f"{outcome} | {guard} | {cited} | "
                f"{run.counts.outer_model_turns} | {elapsed:.1f}s |"
            )
        conn.close()
    lines.append(
        f"\n{passed}/{len(CASES)} requests grounded, safe and with every citation resolved."
    )
    header = [
        "# Ask BlastBridge evaluation (live)",
        "",
        f"Model: {model} · Generated: {datetime.now(UTC).isoformat(timespec='seconds')} "
        "· Fictional demo data, analysis date of each scripted request",
        "",
        "Each suggested request runs live through the bounded tool loop. A run passes when the "
        "response is grounded (every evidence reference returned by a tool), has no validation "
        "issues (or only medical wording that the guard withheld and replaced with deterministic "
        "text), and every Review-brief citation resolves to captured structured evidence.",
        "",
    ]
    report = "\n".join([*header, *lines]) + "\n"
    print(report)
    if args.write:
        REPORT.write_text(report, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
