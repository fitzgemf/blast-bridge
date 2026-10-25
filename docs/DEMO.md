# BlastBridge live demo — presenter run sheet

Five minutes, one laptop, fictional data only. Every step below has a recovery move.

## 30 minutes before

1. Start the app in **presentation mode** from the repository root (Python 3.12 venv active):

   ```powershell
   $env:BLASTBRIDGE_DEMO_MODE = "replay"      # suggested Ask requests use recorded, instant responses
   $env:ANTHROPIC_API_KEY = "<key>"           # optional: enables the live photo/text moment
   streamlit run app/streamlit_app.py
   ```

   Presentation mode keeps the scripted Ask requests and the bundled demo board deterministic and instant,
   even with a key set (both are labelled as recorded demo responses in the app). Free-typed questions and
   any other uploaded photo use live AI when a key is present.
2. Open `http://localhost:8501`, then **Home → Demo / Advanced → Reset to demo state** (tick the
   confirmation). This restores the fictional fixtures and the 19 Oct 2026 demo date.
3. Browser zoom 110–125 % for the projector; close other tabs; turn off notifications.
4. Dry-run steps 1–7 once, then **Reset again — required**: rehearsing step 6 (approve) and step 7
   ("Create training draft") changes the data, and the scripted duplicate request only works on fresh demo data.
5. Keep the backup recording open in another window (see *If everything fails*).

## The story (say this first, 20 seconds)

> Blast overpressure from routine weapons training is a recognised occupational concern, but the
> records of who was exposed, when, and how often are scattered across range logs, whiteboards and
> memory. BlastBridge turns those records into a reviewable occupational history, surfaces people
> whose patterns or reported symptoms deserve attention, and never lets AI make the decision.
> Exposure is not injury, and BlastBridge never diagnoses.

## Click path

| # | Time | Click | Say | If it goes wrong |
|---|---|---|---|---|
| 1 | 0:20 | **Home**. Point at **Needs attention**. | "Two people need a human look today, for different reasons. Amber is deterministic medical follow-up; violet is an occupational-pattern review signal. They are never merged into a score." | — |
| 2 | 0:50 | **Jordan Pike** → amber band → **View Follow-up** | "This guidance comes from fixed TBICoE/CDC rules, not the model. The AI cannot write medical text." | Nav bar always works: **People → Jordan Pike**. |
| 3 | 1:30 | **People → Reese Calder → Summarize Reese for review** | "The analyst used BlastBridge's own tools. Every section of this Review brief is grounded." | If a notice appears, click **Use demo date (19 Oct 2026)** and click the request again. |
| 4 | 2:10 | Click a record citation, then the **Unknown count** citation, then **Occupational pattern assessment** | "Click any citation and you see the structured source, not AI prose. Unknown stays Unknown — never zero. The pattern model compares dates against a fictional HIMARS scenario reference; it's a review signal, not a risk score." | Citations open inline; nothing navigates away. |
| 5 | 3:00 | **Log training event → Upload / photograph record** → `examples/fictional/intake/demo_range_board.jpg` → **Create proposal** | "A phone photo of a handwritten range record. This is Claude Vision's recorded read of it — I'll do a live one in a minute. BlastBridge resolves names against the roster and the weapon against the catalog. Launcher 2 was written as '?' — it stays Unknown." | In presentation mode the bundled board always uses its recorded read (works offline). Or use **Describe / paste → Use demo replay**. |
| 6 | 3:40 | At **Review event** → **Approve event** | "Nothing is recorded until a human approves. One decision: approve, edit, save for later, or discard." | **Save for later** sends it to **Review** (badge count goes up). |
| 7 | 4:10 | **Home → Find possible duplicate records → Compare sources** | "Two separately recorded drafts look like the same range day. The Evidence map shows why: shared people, which record supports which fact, and that the reconstruction still needs human review." | If it says it couldn't produce a grounded answer, the data was changed by a rehearsal: **Home → Demo / Advanced → Reset to demo state**, then repeat. If the map is slow, the comparison table below carries the same facts. |
| 8 | 4:40 | (Close) | "AI proposes; deterministic rules and people decide; everything is traceable." | — |

## Optional live moment: photograph a handwritten board (+60 s)

Only with a working key and network, and **not** in place of step 5 (keep the bundled board as the safe path).

1. Before going on stage, hand-write a small *fictional* board on paper or a whiteboard, e.g.
   `2026-10-19 · Demo Range North · HIMARS · Live-fire qualification`, `Launcher 1 — 6` with
   Chief Avery Kestrel / Gunner Jordan Pike / Driver Riley Marsh, and `Launcher 2 — ?` with Casey Thorne /
   Morgan Vale / Taylor Brook. Use only names from the fictional roster (People page).
2. On stage, photograph it with the phone, transfer it (AirDrop/cable), and upload it at
   **Log training event → Upload / photograph record → Create proposal** (about 10 s).
   Say: "Any real range log works the same way — names only resolve if they are written and on the roster."
3. Phone tips: iPhone saves HEIC by default — set *Settings → Camera → Formats → Most Compatible* (JPEG) the
   day before, or upload a screenshot of the photo. Large photos (up to 20 MB) are rotated and resized
   automatically. If the live read fails, say "here's the recorded one" and upload the bundled board.

## Likely judge questions

- **Does it diagnose TBI or predict injury?** No. It records occupational activity and applies fixed,
  published follow-up rules to human-confirmed reports. No injury probabilities or risk scores.
- **How do you stop the AI from making things up?** Bounded tool calls; names must resolve through the
  roster tool and weapons through the catalog; exact counts need explicit text; a Python grounding
  gate validates every proposal; analyst citations must reference evidence the tools actually
  returned; medical text is application-owned; a human approves every record.
- **How do you know the AI works?** Three live evaluations on fictional data, committed in the repo:
  text intake 12/12, photo intake 8/8 (including a prompt-injection instruction written on the board,
  which did not change any count), and the analyst 5/5 grounded with every citation
  resolving. On two analyst requests the medical-content guard withheld the model's wording and showed
  deterministic text instead — the boundary working as designed.
- **What is the ML?** An IsolationForest fitted at runtime on an SME-informed *fictional* HIMARS
  scenario reference, comparing event-day cadence features. Only "atypical elevated" cadence raises
  a review signal; symptoms and physical-event counts are excluded from the model.
- **What about the photo — could it be tricked?** Image text is treated as data, never instructions;
  the transcription is labelled "check against image", the image stays beside the decision, and a
  human approves. Uploads are size/type checked and never stored.
- **Is any of this real data?** No. All people, units and events are invented. Uploading real
  personnel, medical or operational records is explicitly out of scope.
- **What would production need?** Authentication and roles, an accredited data store, validated
  references from real (approved) data, clinical governance of the follow-up rules, and audit logging.

## If everything fails

- Network down: presentation mode needs no network for steps 1–4, 6–7, and the bundled photo replays offline.
- App crashed: `Ctrl+C`, run the start command again, Reset to demo state, resume at the current step.
- Laptop failure: play the backup recording `docs/demo/blastbridge-demo.webm` and narrate over it.
