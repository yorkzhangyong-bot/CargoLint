# End-to-end evaluation report (feature 007)

- **Set**: `tests/eval/cn8_eval_set.json`, the CN-8 eval's 120 EBTI rulings (built 2026-10-23); a line's correct HS-6 and CN-8 are its ruling's.
- **Method**: each ruling's goods description is a row of an uploaded file, cut at 300 characters as the product's parser cuts it, and the lines run the upload's steps through the line store: the description check, the HS-6 step and its vote gate, the CN-8 step and its vote gate for the lines whose HS-6 the gate decided, and the routes (threshold 85, ask floor 50). A line's own ruling is never a precedent and never votes (leave-one-out); ruling validity on the set's build date. Then the clerk confirms the HS-6 each line in review opens with (the top candidate) and the CN-8 step runs on it. A flagged line stays locked. TARIC is not run. `python tests/eval/e2e_eval.py --repeat 3`.
- **Right end to end**: the line's CN-8 pick, written by rule or to confirm, is the ruling's CN-8. **Auto-accepted**: the HS-6 decided by the gate and the CN-8 written by rule; a CN-8 left to confirm counts as review. **Wrong auto-accepts**: auto-accepted with a wrong CN-8. The other lines went wrong at the **HS-6 step** (a wrong HS-6, or none: flagged, failed, no candidate) or at the **CN-8 step** (a wrong CN-8, a question to the shipper, a failure).

| Iteration | Run on | Tag | Model | Runs | Right end to end per run | Majority | Auto-accepted per run | Wrong auto-accepts per run | Review per run | Ask per run | Cost, time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-26 | e2e-baseline | google/gemini-2.5-flash | 3 | 64 / 64 / 65 of 120 | 64/120 | 53 / 52 / 53 | 8 / 7 / 7 | 55 / 56 / 55 | 12 / 12 / 12 | $0.7920 (€0.7286), 263 s |
| 2 | 2026-10-26 | e2e-stopword-fix | google/gemini-2.5-flash | 1 | 68 of 120 | 68/120 | 56 | 7 | 57 | 7 | $0.2674 (€0.2460), 134 s |

## Iteration 1 (e2e-baseline, google/gemini-2.5-flash, 2026-10-26)

| Run | Right end to end | Auto-accepted | Wrong auto-accepts | Review | Ask the shipper | From the HS-6 step (wrong / flagged / failed / no candidate) | From the CN-8 step (wrong / question / failed) | Time (upload, in all) | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 64/120 | 53 | 8 | 55 | 12 | 46 (36 / 10 / 0 / 0) | 10 (2 / 8 / 0) | 84 s, 100 s | €0.2431 |
| 2 | 64/120 | 52 | 7 | 56 | 12 | 47 (37 / 10 / 0 / 0) | 9 (1 / 8 / 0) | 73 s, 82 s | €0.2418 |
| 3 | 65/120 | 53 | 7 | 55 | 12 | 46 (36 / 10 / 0 / 0) | 9 (1 / 8 / 0) | 73 s, 81 s | €0.2437 |

Majority (the most frequent CN-8 pick of each line; a tie goes to the earliest run): 64 of 120 right end to end; of the 56 others, 47 went wrong at the HS-6 step and 9 at the CN-8 step.

By layer, per run: the HS-6 top-1 right in 81 / 80 / 80 of 120; a wrong HS-6 decided by the gate in 8 / 7 / 7; the CN-8 right where the HS-6 it ran on was right in 64 of 74 / 64 of 73 / 65 of 74.

Cut at 300 characters: 71 of 120 lines. Right end to end per run: 37 / 37 / 37 of the cut lines, 27 / 27 / 28 of the other 49.

Same CN-8 pick in all runs: 114/120; same route: 118/120. Right auto-accepts per run: 45 / 45 / 46.

Invalid answers (retried at most 2 times): run 1: 0 retried, 0 calls still invalid, 0 lines failed; run 2: 0 retried, 0 calls still invalid, 0 lines failed; run 3: 0 retried, 0 calls still invalid, 0 lines failed.

### Wrong auto-accepts (8 lines)

- IEBTIIENEN004-2024-BTI284 (expected 42021291): run 1: 42029219 under 4202.92, wrong HS-6
- DEBTI36175/25-1 (expected 61161020): runs 1, 2, 3: 61169200 under 6116.92, wrong HS-6
- IEBTIIENEN004-2024-BTI356 (expected 64052091): runs 1, 2, 3: 64041910 under 6404.19, wrong HS-6
- IEBTIIENEN004-2026-BTI68 (expected 84798997): runs 1, 2, 3: 84198998 under 8419.89, wrong HS-6
- IEBTIIENEN004-2026-BTI105 (expected 84749090): runs 1, 2, 3: 39269097 under 3926.90, wrong HS-6
- MTBTI2024-002 (expected 84248970): runs 1, 2, 3: 84798997 under 8479.89, wrong HS-6
- MTBTI2025-011 (expected 94054231): runs 1, 2, 3: 94051140 under 9405.11, wrong HS-6
- IEBTIIENEN004-2025-BTI38 (expected 95030041): runs 1, 2, 3: 95030049 under 9503.00, wrong CN-8

### Lines wrong in every run (55)

- IEBTIIENEN004-2025-BTI245 (expected 39269097): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- XIBTI505068468 (expected 39269097): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2025-BTI258 (expected 39269097): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2023-BTI572 (expected 39231090): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2024-BTI284 (expected 42021291): 42029219 (auto_accept, wrong HS-6) · 42023210 (review, wrong HS-6) · 42023210 (review, wrong HS-6)
- IEBTIIENEN004-2024-BTI145 (expected 42029291): 42022290 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI449 (expected 42029219): 42021250 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI264 (expected 42029291): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2025-BTI227 (expected 42029298): 42022290 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI261 (expected 42029219): 42021250 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI132 (expected 61023090): 61013090 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI208 (expected 61099020): 61143000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI90 (expected 61013090): 61043300 (review, wrong HS-6) in every run
- DEBTI45301/24-1 (expected 61102099): no CN-8 (ask_shipper, CN-8 question) in every run
- DEBTI36175/25-1 (expected 61161020): 61169200 (auto_accept, wrong HS-6) in every run
- DEBTI23122/26-1 (expected 61161080): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2026-BTI106 (expected 62121090): no CN-8 (review, wrong HS-6) · no CN-8 (review, wrong HS-6) · 61124190 (review, wrong HS-6)
- IEBTIIENEN004-2026-BTI108 (expected 62121090): no CN-8 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI107 (expected 62121090): no CN-8 (review, wrong HS-6) in every run
- DEBTI7623/25-1 (expected 62024010): no CN-8 (review, wrong HS-6) · no CN-8 (review, wrong HS-6) · 62043390 (review, wrong HS-6)
- DEBTI43065/25-1 (expected 62101098): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2026-BTI228 (expected 63079098): 33042000 (review, wrong HS-6) in every run
- SEBTITV-2026-01096 (expected 63079010): 95030041 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI7 (expected 63079098): 46029000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI5 (expected 63079098): 46021990 (review, wrong HS-6) in every run
- XIBTI505066180 (expected 63079010): 87082190 (review, wrong HS-6) in every run
- MTBTI2025-017 (expected 63079098): 63059000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI356 (expected 64052091): 64041910 (auto_accept, wrong HS-6) in every run
- DEBTI16524/26-1 (expected 64029998): 64041910 (review, wrong HS-6) in every run
- DEBTI37155/24-1 (expected 64029190): 64029998 (review, wrong HS-6) in every run
- XIBTI505060394 (expected 73269098): 73101000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI77 (expected 73181552): no CN-8 (review, CN-8 question) in every run
- IEBTIIENEN004-2024-BTI92 (expected 73209090): no CN-8 (review, CN-8 question) in every run
- IEBTIIENEN004-2026-BTI279 (expected 73181542): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2024-BTI96 (expected 73269098): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI378 (expected 73170020): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI331 (expected 73089098): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2025-BTI173 (expected 73269098): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI301 (expected 73259990): 85389099 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI19 (expected 84151010): 84152000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI249 (expected 84213925): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2025-BTI293 (expected 84249080): 73072910 (review, wrong HS-6) · 84818099 (review, wrong HS-6) · 84818099 (review, wrong HS-6)
- IEBTIIENEN004-2026-BTI68 (expected 84798997): 84198998 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI124 (expected 84314980): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2026-BTI105 (expected 84749090): 39269097 (auto_accept, wrong HS-6) in every run
- MTBTI2024-002 (expected 84248970): 84798997 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI60 (expected 85389099): no CN-8 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI336 (expected 85389099): 39259010 (review, wrong HS-6) in every run
- XIBTI505068566 (expected 85044083): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2023-BTI561 (expected 85371098): 85363030 (review, wrong HS-6) in every run
- MTBTI2025-011 (expected 94054231): 94051140 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI38 (expected 95030041): 95030049 (auto_accept, wrong CN-8) in every run
- IEBTIIENEN004-2026-BTI72 (expected 96190050): 96190040 (review, wrong CN-8) · 61082200 (review, wrong HS-6) · 61082200 (review, wrong HS-6)
- IEBTIIENEN004-2026-BTI71 (expected 96190050): 61082100 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI222 (expected 96091090): 96099090 (review, wrong HS-6) in every run

## Iteration 2 (e2e-stopword-fix, google/gemini-2.5-flash, 2026-10-26)

| Run | Right end to end | Auto-accepted | Wrong auto-accepts | Review | Ask the shipper | From the HS-6 step (wrong / flagged / failed / no candidate) | From the CN-8 step (wrong / question / failed) | Time (upload, in all) | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 68/120 | 56 | 7 | 57 | 7 | 42 (34 / 8 / 0 / 0) | 10 (3 / 7 / 0) | 117 s, 134 s | €0.2460 |

Majority (the most frequent CN-8 pick of each line; a tie goes to the earliest run): 68 of 120 right end to end; of the 52 others, 42 went wrong at the HS-6 step and 10 at the CN-8 step.

By layer, per run: the HS-6 top-1 right in 82 of 120; a wrong HS-6 decided by the gate in 7; the CN-8 right where the HS-6 it ran on was right in 68 of 78.

Cut at 300 characters: 71 of 120 lines. Right end to end per run: 40 of the cut lines, 28 of the other 49.

Same CN-8 pick in all runs: 120/120; same route: 120/120. Right auto-accepts per run: 49.

Invalid answers (retried at most 2 times): run 1: 0 retried, 0 calls still invalid, 0 lines failed.

### Wrong auto-accepts (7 lines)

- XIBTI505068468 (expected 39269097): run 1: 73218100 under 7321.81, wrong HS-6
- DEBTI36175/25-1 (expected 61161020): run 1: 61169200 under 6116.92, wrong HS-6
- IEBTIIENEN004-2024-BTI356 (expected 64052091): run 1: 64041910 under 6404.19, wrong HS-6
- IEBTIIENEN004-2026-BTI68 (expected 84798997): run 1: 84198998 under 8419.89, wrong HS-6
- MTBTI2024-002 (expected 84248970): run 1: 84798997 under 8479.89, wrong HS-6
- MTBTI2025-011 (expected 94054231): run 1: 94051140 under 9405.11, wrong HS-6
- IEBTIIENEN004-2025-BTI38 (expected 95030041): run 1: 95030049 under 9503.00, wrong CN-8

### Lines wrong in every run (52)

- IEBTIIENEN004-2025-BTI245 (expected 39269097): no CN-8 (review, flagged, waits for the shipper) in every run
- XIBTI505068468 (expected 39269097): 73218100 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2023-BTI572 (expected 39231090): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2024-BTI284 (expected 42021291): 42023210 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI145 (expected 42029291): 42022290 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI449 (expected 42029219): 42021250 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI264 (expected 42029291): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI227 (expected 42029298): 42022290 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI261 (expected 42029219): 42021250 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI132 (expected 61023090): 61121200 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI208 (expected 61099020): 61143000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI90 (expected 61013090): 61043300 (review, wrong HS-6) in every run
- DEBTI45301/24-1 (expected 61102099): no CN-8 (ask_shipper, CN-8 question) in every run
- DEBTI36175/25-1 (expected 61161020): 61169200 (auto_accept, wrong HS-6) in every run
- DEBTI23122/26-1 (expected 61161080): no CN-8 (ask_shipper, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2026-BTI106 (expected 62121090): 61124190 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI108 (expected 62121090): no CN-8 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI107 (expected 62121090): no CN-8 (review, wrong HS-6) in every run
- DEBTI7623/25-1 (expected 62024010): 62043390 (review, wrong HS-6) in every run
- DEBTI43065/25-1 (expected 62101098): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2026-BTI228 (expected 63079098): 33049900 (review, wrong HS-6) in every run
- SEBTITV-2026-01096 (expected 63079010): 95030041 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI7 (expected 63079098): 46029000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI5 (expected 63079098): 46021990 (review, wrong HS-6) in every run
- XIBTI505066180 (expected 63079010): 87082190 (review, wrong HS-6) in every run
- MTBTI2025-017 (expected 63079098): 63059000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2024-BTI356 (expected 64052091): 64041910 (auto_accept, wrong HS-6) in every run
- DEBTI16524/26-1 (expected 64029998): 64041910 (review, wrong HS-6) in every run
- DEBTI37155/24-1 (expected 64029190): 64029998 (review, wrong HS-6) in every run
- XIBTI505060394 (expected 73269098): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2025-BTI77 (expected 73181552): 73181595 (review, wrong CN-8) in every run
- IEBTIIENEN004-2024-BTI92 (expected 73209090): no CN-8 (review, CN-8 question) in every run
- IEBTIIENEN004-2026-BTI279 (expected 73181542): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI378 (expected 73170020): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI173 (expected 73269098): no CN-8 (ask_shipper, CN-8 question) in every run
- IEBTIIENEN004-2025-BTI301 (expected 73259990): 85389099 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI19 (expected 84151010): 84152000 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI249 (expected 84213925): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2025-BTI293 (expected 84249080): 84818099 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI68 (expected 84798997): 84198998 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI124 (expected 84314980): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2026-BTI105 (expected 84749090): no CN-8 (review, flagged, waits for the shipper) in every run
- MTBTI2024-002 (expected 84248970): 84798997 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI60 (expected 85389099): no CN-8 (review, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI336 (expected 85389099): 39259010 (review, wrong HS-6) in every run
- XIBTI505068566 (expected 85044083): no CN-8 (review, flagged, waits for the shipper) in every run
- IEBTIIENEN004-2023-BTI561 (expected 85371098): 85363030 (review, wrong HS-6) in every run
- MTBTI2025-011 (expected 94054231): 94051140 (auto_accept, wrong HS-6) in every run
- IEBTIIENEN004-2025-BTI38 (expected 95030041): 95030049 (auto_accept, wrong CN-8) in every run
- IEBTIIENEN004-2026-BTI72 (expected 96190050): 96190040 (review, wrong CN-8) in every run
- IEBTIIENEN004-2026-BTI71 (expected 96190050): 61082100 (review, wrong HS-6) in every run
- IEBTIIENEN004-2026-BTI222 (expected 96091090): 96099090 (review, wrong HS-6) in every run

Line-by-line results of the latest run: `tests/eval/e2e_eval.json`; each run also keeps its own, `tests/eval/e2e_eval_<tag>.json`.
