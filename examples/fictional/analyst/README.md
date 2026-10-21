# Analyst demo replay

These are authored scripted model turns, not live recordings. The analyst runs the real tools,
native training intake, grounding checks and recommendation eligibility validation.

Use a freshly reset fictional demo with analysis and reference dates of 19 October 2026.
The loader refuses a different application analysis date. Fixture tests start fresh conversations;
the UI retains its scope's conversation until Start over. Run the two log_event steps in order
in that same conversation.

The response placeholders are `{{draft_ref}}` and `{{review_destination}}`. The scripted
provider binds these exact values from the real draft tool result, because session action keys
and native event IDs are created at runtime. It never substitutes narrative facts or analysis.
The UI also binds the logging tool's source IDs to the actual stored user turns when a
conversation already contains an earlier question. A saved draft is recovered for that
conversation regardless of later source IDs; use Start over to log another event.

- reese_brief: occupational pattern, symptoms, deterministic follow-up and Unknown counts.
- reese_missing: a focused count-gap audit with a different tool sequence.
- jordan_brief: medical guidance relayed from the deterministic rules, separately from ML.
- attention: existing deterministic readiness ordering, without a new score.
- log_event: one clarification, exact user text passed into intake, Unknown preserved in a DRAFT.

Approval remains exclusively in the existing human Review flow. Replay is never labelled Live AI.
