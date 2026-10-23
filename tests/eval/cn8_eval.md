# CN-8 evaluation report (feature 004, SC-002)

- **Set**: `tests/eval/cn8_eval_set.json`, fixed before any tuning: 120 valid EBTI rulings, 10 from each of the 12 target chapters, all under subheadings with at least two CN 2026 CN-8 lines (built 2026-10-23, seed 2026).
- **Method**: each ruling's goods description is the line text and its HS-6 the decided HS-6; its own ruling is never a precedent; auto-accept threshold 85; `python tests/eval/cn8_eval.py`.
- **Top-1** counts the chosen CN-8, written by rule or to confirm; a question or a failure is a miss. The target is 60 of 120.

| Iteration | Run on | Change | Top-1 | Written by rule | Written, wrong | To confirm | Asked the shipper | Failures | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-23 | US1 as built (commit 1bfbdc7) | 100/120 | 119 | 19 | 0 | 1 | 0 | $0.0360 (€0.0331), 171 s |
| 2 | 2026-10-23 | evidence must be words of the line, else ask the shipper; a cited ruling at another CN-8 keeps it to confirm; 85+ needs that evidence and an agreeing precedent (else capped at 84); prompt bands 85-98 / 70-84 | 83/120 | 92 | 11 | 3 | 25 | 0 | $0.0388 (€0.0357), 104 s |
| 3 | 2026-10-23 | evidence: every quoted word occurs in the line after normalising both sides (case, punctuation, spacing); only a conflicting ruling keeps the CN-8 to confirm, no ruling leaves the threshold rule alone (no cap at 84, prompt band 85-98 without the ruling clause) | 91/120 | 103 | 12 | 3 | 14 | 0 | $0.0379 (€0.0348), 126 s |

## Top-1 per chapter

| Iteration | 39 | 42 | 61 | 62 | 63 | 64 | 73 | 84 | 85 | 94 | 95 | 96 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10/10 | 6/10 | 9/10 | 10/10 | 9/10 | 8/10 | 9/10 | 9/10 | 7/10 | 7/10 | 9/10 | 7/10 |
| 2 | 7/10 | 5/10 | 7/10 | 7/10 | 9/10 | 7/10 | 6/10 | 8/10 | 5/10 | 7/10 | 8/10 | 7/10 |
| 3 | 9/10 | 7/10 | 7/10 | 9/10 | 9/10 | 7/10 | 7/10 | 8/10 | 7/10 | 7/10 | 8/10 | 6/10 |

Model: openai/gpt-4o-mini. Line-by-line results of the latest run: `tests/eval/cn8_eval.json`; earlier runs are in the git history of that file.
