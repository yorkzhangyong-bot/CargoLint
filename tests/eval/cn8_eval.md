# CN-8 evaluation report (feature 004, SC-002)

- **Set**: `tests/eval/cn8_eval_set.json`, fixed before any tuning: 120 valid EBTI rulings, 10 from each of the 12 target chapters, all under subheadings with at least two CN 2026 CN-8 lines (built 2026-10-23, seed 2026).
- **Method**: each ruling's goods description is the line text and its HS-6 the decided HS-6; its own ruling is never a precedent; auto-accept threshold 85; `python tests/eval/cn8_eval.py`.
- **Top-1** counts the chosen CN-8, written by rule or to confirm; a question or a failure is a miss. The target is 60 of 120.

| Iteration | Run on | Change | Top-1 | Written by rule | Written, wrong | To confirm | Asked the shipper | Failures | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-23 | US1 as built (commit 1bfbdc7) | 100/120 | 119 | 19 | 0 | 1 | 0 | $0.0360 (€0.0331), 171 s |
| 2 | 2026-10-23 | evidence must be words of the line, else ask the shipper; a cited ruling at another CN-8 keeps it to confirm; 85+ needs that evidence and an agreeing precedent (else capped at 84); prompt bands 85-98 / 70-84 | 83/120 | 92 | 11 | 3 | 25 | 0 | $0.0388 (€0.0357), 104 s |
| 3 | 2026-10-23 | evidence: every quoted word occurs in the line after normalising both sides (case, punctuation, spacing); only a conflicting ruling keeps the CN-8 to confirm, no ruling leaves the threshold rule alone (no cap at 84, prompt band 85-98 without the ruling clause) | 91/120 | 103 | 12 | 3 | 14 | 0 | $0.0379 (€0.0348), 126 s |
| 4 | 2026-10-23 | T060 validation run: no change to the CN-8 step since iteration 3 (tuning closed); shows run-to-run variation | 93/120 | 107 | 14 | 1 | 12 | 0 | $0.0380 (€0.0349), 106 s |
| 5 | 2026-10-25 | stability baseline: 3 independent runs, temperature 0.0, seed none; the row shows run 1 | 92/120 | 107 | 15 | 1 | 12 | 0 | $0.1139 (€0.1048), 304 s |
| 6 | 2026-10-25 | stability baseline: 3 independent runs, temperature 0.0, seed 42; the row shows run 1 | 91/120 | 104 | 13 | 2 | 14 | 0 | $0.1135 (€0.1045), 254 s |
| 7 | 2026-10-25 | prompt-evidence-v2: three-level attribute rule in the CN-8 prompt (stated, one plain step from stated facts, else ask the shipper); confidence rules unchanged; 3 runs, the row shows run 1 | 91/120 | 103 | 12 | 4 | 13 | 0 | $0.1198 (€0.1102), 220 s |
| 8 | 2026-10-25 | evidence diagnosis: the prompt and settings of iteration 7, re-run to log the raw CN-8 output, the evidence check and the route; 3 runs, the row shows run 1 | 92/120 | 106 | 14 | 2 | 12 | 0 | $0.1198 (€0.1102), 259 s |

## Top-1 per chapter

| Iteration | 39 | 42 | 61 | 62 | 63 | 64 | 73 | 84 | 85 | 94 | 95 | 96 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10/10 | 6/10 | 9/10 | 10/10 | 9/10 | 8/10 | 9/10 | 9/10 | 7/10 | 7/10 | 9/10 | 7/10 |
| 2 | 7/10 | 5/10 | 7/10 | 7/10 | 9/10 | 7/10 | 6/10 | 8/10 | 5/10 | 7/10 | 8/10 | 7/10 |
| 3 | 9/10 | 7/10 | 7/10 | 9/10 | 9/10 | 7/10 | 7/10 | 8/10 | 7/10 | 7/10 | 8/10 | 6/10 |
| 4 | 10/10 | 6/10 | 8/10 | 9/10 | 9/10 | 6/10 | 7/10 | 8/10 | 7/10 | 7/10 | 9/10 | 7/10 |
| 5 | 10/10 | 6/10 | 8/10 | 9/10 | 9/10 | 8/10 | 6/10 | 8/10 | 6/10 | 7/10 | 9/10 | 6/10 |
| 6 | 9/10 | 6/10 | 8/10 | 9/10 | 9/10 | 8/10 | 6/10 | 8/10 | 7/10 | 7/10 | 8/10 | 6/10 |
| 7 | 9/10 | 6/10 | 7/10 | 8/10 | 8/10 | 8/10 | 8/10 | 8/10 | 6/10 | 7/10 | 8/10 | 8/10 |
| 8 | 9/10 | 6/10 | 8/10 | 8/10 | 8/10 | 8/10 | 7/10 | 8/10 | 6/10 | 7/10 | 9/10 | 8/10 |

## Stability (repeated runs)

Each line classified N times, independently. Same CN-8: the top-1 is identical in all runs. Same decision: written by rule (auto_accept), to confirm or failed (review), or a question (ask_shipper) in all runs. Majority: the most frequent top-1 taken as the answer (a tie goes to the earliest run). The rows above show run 1 of these entries.

| Iteration | Run on | Tag | Temperature | Seed | Runs | Top-1 per run | Majority top-1 | Same CN-8 | Same decision | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 2026-10-25 | baseline-stability | 0.0 | none | 3 | 92 / 92 / 94 of 120 | 93/120 | 91.7% | 90.8% | $0.1139 (€0.1048) |
| 6 | 2026-10-25 | baseline-stability | 0.0 | 42 | 3 | 91 / 92 / 90 of 120 | 90/120 | 95.0% | 93.3% | $0.1135 (€0.1045) |
| 7 | 2026-10-25 | prompt-evidence-v2 | 0.0 | none | 3 | 91 / 94 / 91 of 120 | 92/120 | 90.8% | 91.7% | $0.1198 (€0.1102) |
| 8 | 2026-10-25 | evidence-diagnosis | 0.0 | none | 3 | 92 / 89 / 91 of 120 | 91/120 | 91.7% | 90.0% | $0.1198 (€0.1102) |

Iteration 5: 10 lines whose top-1 differed between runs (chosen CN-8, confidence, decision per run):

- IEBTIIENEN004-2025-BTI351 (HS-6 3925.90, expected 39259010): 39259010 (85, auto_accept) · 39259010 (85, auto_accept) · no code (0, ask_shipper)
- DEBTI23122/26-1 (HS-6 6116.10, expected 61161080): 61161080 (85, auto_accept) · 61161020 (85, auto_accept) · 61161080 (85, auto_accept)
- IEBTIIENEN004-2024-BTI122 (HS-6 6402.99, expected 64029939): 64029931 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- DEBTI16524/26-1 (HS-6 6402.99, expected 64029998): 64029998 (85, auto_accept) · no code (0, ask_shipper) · 64029998 (85, auto_accept)
- IEBTIIENEN004-2025-BTI77 (HS-6 7318.15, expected 73181552): 73181535 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI69 (HS-6 7318.14, expected 73181499): no code (0, ask_shipper) · 73181499 (85, auto_accept) · 73181499 (85, auto_accept)
- IEBTIIENEN004-2025-BTI26 (HS-6 8471.60, expected 84716070): no code (0, ask_shipper) · no code (0, ask_shipper) · 84716070 (85, auto_accept)
- IEBTIIENEN004-2026-BTI72 (HS-6 9619.00, expected 96190050): 96190040 (85, review) · 96190040 (85, review) · 96190050 (85, auto_accept)
- IEBTIIENEN004-2026-BTI222 (HS-6 9609.10, expected 96091090): no code (0, ask_shipper) · no code (0, ask_shipper) · 96091010 (85, auto_accept)
- DEBTI47340/24-1 (HS-6 9603.90, expected 96039099): 96039091 (85, auto_accept) · 96039099 (85, auto_accept) · 96039091 (85, review)

Iteration 6: 6 lines whose top-1 differed between runs (chosen CN-8, confidence, decision per run):

- DEBTI16524/26-1 (HS-6 6402.99, expected 64029998): 64029998 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI26 (HS-6 8471.60, expected 84716070): no code (0, ask_shipper) · 84716070 (85, auto_accept) · no code (0, ask_shipper)
- IEBTIIENEN004-2026-BTI60 (HS-6 8538.90, expected 85389099): no code (0, ask_shipper) · 85389091 (85, auto_accept) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI38 (HS-6 9503.00, expected 95030041): 95030049 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI393 (HS-6 9503.00, expected 95030049): no code (0, ask_shipper) · 95030049 (85, auto_accept) · no code (0, ask_shipper)
- IEBTIIENEN004-2026-BTI222 (HS-6 9609.10, expected 96091090): 96091010 (85, auto_accept) · 96091010 (85, auto_accept) · no code (0, ask_shipper)

Iteration 7: 11 lines whose top-1 differed between runs (chosen CN-8, confidence, decision per run):

- IEBTIIENEN004-2024-BTI132 (HS-6 6102.30, expected 61023090): no code (0, ask_shipper) · 61023090 (85, auto_accept) · no code (0, ask_shipper)
- IEBTIIENEN004-2026-BTI75 (HS-6 6212.10, expected 62121090): 62121090 (85, auto_accept) · 62121090 (85, auto_accept) · no code (0, ask_shipper)
- DEBTI16524/26-1 (HS-6 6402.99, expected 64029998): no code (0, ask_shipper) · 64029998 (85, auto_accept) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI77 (HS-6 7318.15, expected 73181552): 73181535 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI378 (HS-6 7317.00, expected 73170020): 73170060 (85, auto_accept) · no code (0, ask_shipper) · 73170060 (85, auto_accept)
- XIBTI505059567 (HS-6 8504.40, expected 85044060): no code (0, ask_shipper) · 85044083 (85, auto_accept) · 85044083 (85, auto_accept)
- SEBTITV-2024-01674 (HS-6 9401.99, expected 94019980): 94019980 (95, auto_accept) · 94019980 (95, auto_accept) · no code (0, ask_shipper)
- IEBTIIENEN004-2025-BTI393 (HS-6 9503.00, expected 95030049): no code (0, ask_shipper) · 95030049 (85, auto_accept) · 95030049 (85, auto_accept)
- IEBTIIENEN004-2026-BTI72 (HS-6 9619.00, expected 96190050): 96190040 (85, review) · 96190050 (85, auto_accept) · 96190040 (85, review)
- DEBTI47340/24-1 (HS-6 9603.90, expected 96039099): 96039091 (85, review) · 96039091 (85, review) · 96039099 (85, auto_accept)
- DEBTI59675/24-1 (HS-6 9603.90, expected 96039099): 96039099 (85, auto_accept) · 96039091 (85, auto_accept) · 96039099 (85, auto_accept)

Iteration 8: 10 lines whose top-1 differed between runs (chosen CN-8, confidence, decision per run):

- FRBTIFR-BTI-2025-02100 (HS-6 4203.29, expected 42032910): 42032910 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- IEBTIIENEN004-2026-BTI108 (HS-6 6212.10, expected 62121090): no code (0, ask_shipper) · no code (0, ask_shipper) · 62121090 (85, auto_accept)
- DEBTI7623/25-1 (HS-6 6202.40, expected 62024010): 62024010 (95, auto_accept) · no code (0, ask_shipper) · 62024010 (95, auto_accept)
- DEBTI16524/26-1 (HS-6 6402.99, expected 64029998): no code (0, ask_shipper) · 64029950 (85, review) · 64029950 (85, review)
- IEBTIIENEN004-2025-BTI331 (HS-6 7308.90, expected 73089098): no code (0, ask_shipper) · 73089098 (85, auto_accept) · 73089098 (85, auto_accept)
- IEBTIIENEN004-2026-BTI255 (HS-6 8421.39, expected 84213985): 84213925 (85, auto_accept) · no code (0, ask_shipper) · no code (0, ask_shipper)
- SEBTITV-2024-01674 (HS-6 9401.99, expected 94019980): 94019980 (95, auto_accept) · no code (0, ask_shipper) · 94019980 (95, auto_accept)
- IEBTIIENEN004-2025-BTI38 (HS-6 9503.00, expected 95030041): no code (0, ask_shipper) · 95030049 (85, auto_accept) · 95030049 (85, auto_accept)
- IEBTIIENEN004-2026-BTI72 (HS-6 9619.00, expected 96190050): 96190050 (85, auto_accept) · 96190040 (85, review) · 96190040 (85, review)
- IEBTIIENEN004-2026-BTI222 (HS-6 9609.10, expected 96091090): 96091090 (85, auto_accept) · 96091090 (85, auto_accept) · no code (0, ask_shipper)

## Rulings sent to the model

Wrong results (line × run; a question to the shipper is a miss) in which a ruling at the expected CN-8 was among the rulings sent to the model. Logged since iteration 7.

- Iteration 7: 84 of 84 wrong results (100.0%).
- Iteration 8: 88 of 88 wrong results (100.0%).

Model: openai/gpt-4o-mini. Line-by-line results of the latest run: `tests/eval/cn8_eval.json`; earlier runs are in the git history of that file.
