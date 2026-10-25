# CN-8 vote analysis: the nearest EBTI rulings as the auto-accept gate

Data: iteration 10 (tag "nearest-hits-logging"), 3 runs of 120 lines; nearest-hits logging: deterministic retrieval order and query embeddings cached per line text (bd7f97d, order fixed in a4ec6c7); logs the top-40 vector hits; 3 runs, the row shows run 1. Offline replay of `tests/eval/cn8_eval.json` by `tests/eval/cn8_vote_analysis.py`; no API call. Definitions: `specs/006-stability-baseline/plan-ruling-vote.md` section 3 and the script's docstring.

- Rulings sent and vector hits identical in every run: 120 of 120 lines.
- Today: 38 wrong auto-accept rows (13 / 13 / 12 per run) and 289 right ones; 13 wrong auto-accept lines of 23 lines wrong in the majority result; 94 always-right lines, 94 of them auto-accepted today.
- Target: at most 3 wrong auto-accept rows in every run and at most 10% (28.9) of the 289 right auto-accept rows lost. Variants that meet it are in bold.

| Variant | Wrong auto-accept rows (per run) | Wrong lines blocked | Right auto-accept rows lost | Always-right lines sent to review |
|---|---|---|---|---|
| today: model confidence ≥ 85 | 38 (13 / 13 / 12) | — | — | — |
| nearest-1 | 38 → 21 (7 / 7 / 7) | 6 of 13 | 15 of 289 (5.2%) | 5 of 94 |
| 3-nearest vote, weighted, share ≥ 0.5 | 38 → 18 (6 / 6 / 6) | 7 of 13 | 36 of 289 (12.5%) | 12 of 94 |
| 3-nearest vote, weighted, share ≥ 0.6 | 38 → 18 (6 / 6 / 6) | 7 of 13 | 39 of 289 (13.5%) | 13 of 94 |
| 3-nearest vote, weighted, share ≥ 0.67 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 48 of 289 (16.6%) | 16 of 94 |
| 5-nearest vote, weighted, share ≥ 0.5 | 38 → 15 (5 / 5 / 5) | 8 of 13 | 30 of 289 (10.4%) | 10 of 94 |
| 5-nearest vote, weighted, share ≥ 0.6 | 38 → 15 (5 / 5 / 5) | 8 of 13 | 36 of 289 (12.5%) | 12 of 94 |
| 5-nearest vote, weighted, share ≥ 0.67 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 42 of 289 (14.5%) | 14 of 94 |
| 10-nearest vote, weighted, share ≥ 0.5 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 39 of 289 (13.5%) | 13 of 94 |
| 10-nearest vote, weighted, share ≥ 0.6 | 38 → 6 (2 / 2 / 2) | 11 of 13 | 48 of 289 (16.6%) | 16 of 94 |
| 10-nearest vote, weighted, share ≥ 0.67 | 38 → 6 (2 / 2 / 2) | 11 of 13 | 57 of 289 (19.7%) | 19 of 94 |
| 20-nearest vote, weighted, share ≥ 0.5 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 39 of 289 (13.5%) | 13 of 94 |
| 20-nearest vote, weighted, share ≥ 0.6 | 38 → 6 (2 / 2 / 2) | 11 of 13 | 56 of 289 (19.4%) | 18 of 94 |
| 20-nearest vote, weighted, share ≥ 0.67 | 38 → 3 (1 / 1 / 1) | 12 of 13 | 65 of 289 (22.5%) | 21 of 94 |
| 3-nearest vote, unweighted, share ≥ 0.5 | 38 → 21 (7 / 7 / 7) | 6 of 13 | 30 of 289 (10.4%) | 10 of 94 |
| 3-nearest vote, unweighted, share ≥ 0.6 | 38 → 21 (7 / 7 / 7) | 6 of 13 | 30 of 289 (10.4%) | 10 of 94 |
| 3-nearest vote, unweighted, share ≥ 0.67 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 57 of 289 (19.7%) | 19 of 94 |
| 5-nearest vote, unweighted, share ≥ 0.5 | 38 → 15 (5 / 5 / 5) | 8 of 13 | 27 of 289 (9.3%) | 9 of 94 |
| 5-nearest vote, unweighted, share ≥ 0.6 | 38 → 15 (5 / 5 / 5) | 8 of 13 | 27 of 289 (9.3%) | 9 of 94 |
| 5-nearest vote, unweighted, share ≥ 0.67 | 38 → 12 (4 / 4 / 4) | 9 of 13 | 45 of 289 (15.6%) | 15 of 94 |
| 10-nearest vote, unweighted, share ≥ 0.5 | 38 → 12 (4 / 4 / 4) | 9 of 13 | 48 of 289 (16.6%) | 16 of 94 |
| 10-nearest vote, unweighted, share ≥ 0.6 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 51 of 289 (17.6%) | 17 of 94 |
| 10-nearest vote, unweighted, share ≥ 0.67 | 38 → 6 (2 / 2 / 2) | 11 of 13 | 60 of 289 (20.8%) | 20 of 94 |
| 20-nearest vote, unweighted, share ≥ 0.5 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 42 of 289 (14.5%) | 14 of 94 |
| 20-nearest vote, unweighted, share ≥ 0.6 | 38 → 9 (3 / 3 / 3) | 10 of 13 | 50 of 289 (17.3%) | 16 of 94 |
| 20-nearest vote, unweighted, share ≥ 0.67 | 38 → 3 (1 / 1 / 1) | 12 of 13 | 68 of 289 (23.5%) | 22 of 94 |

## The wrong lines the best variant still lets through

Best variant: **5-nearest vote, unweighted, share ≥ 0.5**, because no variant meets the target; it has the fewest wrong auto-accept rows among those losing at most 10 %.

| Line | Auto-accepted wrong in runs | Model's CN-8 | Expected | Nearest eligible hit (country) |
|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI227 | 3 of 3 | 42029291 | 42029298 | 42029298 (IE) |
| XIBTI505066180 | 3 of 3 | 63079098 | 63079010 | 63079098 (XI) |
| IEBTIIENEN004-2026-BTI255 | 3 of 3 | 84213925 | 84213985 | 84213925 (IE) |
| IEBTIIENEN004-2026-BTI60 | 3 of 3 | 85389091 | 85389099 | 85389091 (IE) |
| IEBTIIENEN004-2025-BTI38 | 3 of 3 | 95030049 | 95030041 | 95030049 (BE) |
