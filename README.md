# BlastBridge

AI-assisted occupational blast-exposure records and review for military training.

**[▶ Watch the two-minute demo](docs/demo/blastbridge-demo.webm)**

Training blast exposure is usually written down in pieces: a range board, a crew list, a notebook
page. BlastBridge turns those records into reviewed, longitudinal histories. Claude reads a typed
note or a photo of a handwritten record and proposes a structured event; a human approves it. Over
time each person's training history, occupational-pattern signals and symptom follow-up come
together in one review workflow, without being merged into a single score.

**Exposure is not injury.** BlastBridge records training activity and supports human review.
It does not diagnose TBI, predict injury, assign medical probabilities or determine medical clearance.
A symptom report after an event is a temporal association, not evidence of causation.
All people and records in this prototype are fictional.

## What it does

- **Training intake:** Claude structures text or a photographed training record using roster and
  weapon-catalog tools. Unknown stays Unknown. Text, photo and manual entry all end at one
  **Review event** decision: Approve event, Edit, Save for later or Discard.
- **Longitudinal history:** approved records connect dates, people, crews and roles in organization
  and person calendars. Drafts and rejected records stay out of personnel history.
- **Occupational-pattern comparison:** IsolationForest compares recorded HIMARS event-day cadence
  with an SME-informed HIMARS scenario reference. Elevated atypical activity is a review signal only;
  symptoms and physical-event counts are excluded from the model.
- **Symptom follow-up:** human-confirmed structured reports feed deterministic TBICoE/CDC guidance
  rules, separate from the occupational-pattern model. Guidance is not a diagnosis.
- **Ask BlastBridge:** a bounded analyst uses application tools to produce an evidence-cited
  **Review brief**. Numbered citations open the structured source evidence behind each statement.
- **Evidence Intelligence:** possible duplicate records get field comparisons and an **Evidence map**.
  Reconstructions preserve conflicts and Unknowns and need a human decision before entering history.

## Screenshots

| Home | Review event | Photo intake |
| --- | --- | --- |
| ![Home](docs/screenshots/home.png) | ![Review event](docs/screenshots/review-event.png) | ![Photo intake](docs/screenshots/photo-intake.png) |

| Review brief | Evidence map | Person follow-up |
| --- | --- | --- |
| ![Review brief](docs/screenshots/review-brief.png) | ![Evidence map](docs/screenshots/evidence-map.png) | ![Person follow-up](docs/screenshots/person-followup.png) |

## How the AI is kept honest

Tool and model-call budgets are bounded. Roster and catalog lookups plus a Python grounding gate
constrain intake: a name, count or location that is not in the source record cannot enter a draft
unchallenged. Analyst references are validated against the evidence its tools returned. Medical
text comes from application-owned deterministic guidance, never from the model. Humans approve
training events and confirm symptom reports. Provenance distinguishes manual, live-AI and replayed
input. No AI confidence percentages or injury probabilities are shown.

Every Ask BlastBridge answer opens an **Agent trace**: each tool call with its subject, status and
evidence count, the grounding verdict (including when the medical-content guard withheld model
wording), and run totals, with raw tool I/O one level deeper.

## AI evaluation

Each intake path and five analyst requests have live evaluations, including adversarial cases.
Reports are committed and can be rerun with an API key.

| Path | Live result | What it checks | Report |
| --- | --- | --- | --- |
| Text intake | 12/12 | golden record, aliases, explicit Unknown, missing roles, invented weapon, future date, approximate counts, name/ID mismatch, medical language in a training record | [report](examples/fictional/intake/eval_report_live.md) |
| Photo intake (Claude Vision) | 8/8 | clear board, "several" stays unset, off-roster name, invented weapon, **prompt injection written on the board** (the instruction did not change any count), unreadable photo, sideways phone photo (EXIF), future date | [report](examples/fictional/intake/eval_report_image_live.md) |
| Ask BlastBridge analyst | 5/5 | every response grounded in tool-returned evidence, every Review-brief citation resolves; on 2/5 the medical-content guard withheld model wording and showed deterministic text | [report](examples/fictional/analyst/eval_report_live.md) |

Pass criteria are fixed in the scripts before running; failures are reported, not tuned away.

## Architecture

| Location | Responsibility |
| --- | --- |
| `app/` | Streamlit UI, navigation, calendars and human decisions |
| `src/blastbridge/product/agent.py`, `image_intake.py` | Shared bounded intake and photo-of-record envelope |
| `analyst.py`, `analyst_tools.py` | Ask BlastBridge, evidence tools and grounding |
| `briefing.py` | Code-owned citation labels and captured-evidence source cards |
| `evidence.py`, `evidence_graph.py` | Deterministic comparisons/reconstruction and read-only provenance map |
| `readiness.py`, `followup.py`, `symptoms.py` | Deterministic states and confirmed symptom guidance |
| `patterns.py` | Occupational cadence comparison with the scenario reference |
| `review_flow.py`, `store.py` | Save/approve fail-safe, revision protections and SQLite persistence |
| `data/`, `examples/fictional/` | Versioned public references, fictional scenarios and replays |

Module names after the first product row are relative to `src/blastbridge/product/`.
[PRODUCT.md](PRODUCT.md) documents model assumptions, coverage and reference limitations.

## Run it locally

Requires **Python 3.12**. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[app]"
streamlit run app/streamlit_app.py
```

The app runs offline: without an API key, the suggested analyst requests, the example text record
and the [sample photo](examples/fictional/intake/demo_range_board.jpg) use recorded AI responses,
labelled as such on screen. For live Claude, set `ANTHROPIC_API_KEY` in the environment before
starting Streamlit. Records are stored in a local SQLite database (`BLASTBRIDGE_DB` overrides the path).

Tests and checks: `pip install -e ".[dev,app]"`, then `pytest`, `ruff check .`, `mypy`.

## Research foundation

The product sits on typed, cited research datasets built first: 18 weapon/category records and
11 official sources (V0.1), 40 training-tempo evidence records from 31 sources (V0.2), and a
prior/uncertainty design (V0.3). Every field keeps its source and scope; unknown quantities are
`None`, never zero; there are no invented weapon defaults, dose formulas or physiological thresholds.
See [research/notes/](research/notes/) and [data governance](research/notes/data-governance.md).
The IsolationForest model and fictional histories are demonstration components, not an empirical
population model or clinical validation.
