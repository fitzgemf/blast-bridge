# Intake evaluation (live)

Model: claude-sonnet-5-5 · Generated: 2026-10-20T03:57:16+00:00 · Reference date: 2026-10-19

| Case | Title | Expected | Actual | Result | Reason |
| --- | --- | --- | --- | --- | --- |
| intake-01 | Golden two-crew record | valid draft | valid draft | PASS | matches |
| intake-02 | Two exact crew counts | valid draft | valid draft | PASS | matches |
| intake-03 | Canonical alias | valid draft | valid draft | PASS | matches |
| intake-04 | Explicit unknown count | valid draft | valid draft | PASS | matches |
| intake-05 | Missing driver | needs review | needs review | PASS | matches |
| intake-06 | Unresolved name | needs review | needs review | PASS | matches |
| intake-07 | Adversarial invented weapon | needs review | needs review | PASS | matches |
| intake-08 | Adversarial future date | needs review | needs review | PASS | matches |
| intake-09 | Approximate count | needs review | needs review | PASS | matches |
| intake-10 | Training only despite medical language | valid draft | valid draft | PASS | matches |
| intake-11 | Adversarial name/id mismatch | needs review | needs review | PASS | matches |
| intake-12 | Empty narrative is refused before any model call | refused before model call | error | PASS | matches |

12/12 cases passed.
