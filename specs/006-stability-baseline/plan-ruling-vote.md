# Plan: let the EBTI rulings, not model confidence, gate the CN-8 auto-accept (006)

Status: draft for review; nothing is implemented. Branch `006-stability-baseline`, 2026-10-25.

**Why.** The CN-8 step auto-accepts 12–13 wrong lines per run. In 78 of 78 wrong results a ruling at the expected CN-8
was among the rulings sent. On 19 of the 21 lines where the model picked another code, the rulings sent covered both
codes. Confidence was 85 or more in 359 of 360 outputs, so it tells us nothing (`tests/eval/cn8_evidence_diagnosis.md`,
`tests/eval/cn8_wrong_lines.md`).

## 1. Ruling vote by code (as briefed)

- Group the rulings sent by CN-8 after `select_rulings`.
- Weight a ruling 3 when it comes from the entry country (`ENTRY_COUNTRY = "DE"` in `agent/config.py`, later an Admin
  setting). Weight it 1 when another state issued it, XI included, since XI rulings are EBTI rulings issued under EU
  law.
- Commission classification regulations would outrank every ruling, but the knowledge base holds none. They need a data
  source first, which is a separate task.
- A pure function in `agent/routing.py` returns:
  - the majority CN-8, or none on a tie;
  - its share of the total weight;
  - the competing codes with their issuing countries.

**Decision (2026-10-25, after the iteration-10 analysis):** the DE weight was dropped and no `ENTRY_COUNTRY` exists;
the product is not tied to one entry country.
- The weight showed no benefit in `tests/eval/cn8_vote_analysis.md`. For example, 5-nearest at share ≥ 0.5 let through
  15 wrong auto-accept rows either way, and lost 27 right ones unweighted against 30 weighted.
- The eval cannot validate a country weight, because its expected codes come from many issuing states.
- The gate built (constitution 1.4.0) is the unweighted vote of the 5 nearest eligible rulings among the vector hits,
  not of the rulings sent. The model's CN-8 must be the majority at a share of at least 0.5 (`CN8_VOTE_K`,
  `CN8_VOTE_SHARE`).
- `tests/eval/cn8_vote_analysis.py` and its report stay as the record of that decision.

## 2. Routing rule (as briefed)

- **Auto-accept** needs all four: the evidence check passed, no cited ruling conflicts, the model's CN-8 equals the
  majority, and the share is at least *t*.
- **Otherwise review**, with a reason such as "Rulings disagree: DE rulings say 94032080, FR rulings say 94032020".
- **No rulings sent:** today's rule applies.
- **Evidence check fails:** ask the shipper, as now.

## 3. Dry run on iterations 8 and 9 (done; no API call, no code change)

- **Data:** per-line results of iteration 8 (`cn8_eval.json` at 52381ca) and iteration 9 (at 1d65d2e), which log the
  rulings sent. Each ruling's issuing country comes from `store/bti_docs.jsonl`.
- **Always-right lines:** right in all six runs of iterations 8 and 9. There are 83; the earlier 88 counted
  iterations 5 and 6.
- **Wrong auto-accept lines:** majority-wrong lines whose majority route is auto-accept. That is 13 of 29 in
  iteration 8 and 13 of 26 in iteration 9. The others already ask or go to review, so a vote cannot change them.

**A. The vote as briefed** (results given as iteration 8 / iteration 9)

| *t* | Wrong auto-accept rows (today 40 / 37) | Wrong lines blocked | Right auto-accept rows lost (of 271 / 282) | Always-right lines to review (of 83) |
|---|---|---|---|---|
| 0.5 | 4 / 3 | 12 / 12 of 13 | 219 / 230 | 68 |
| 0.6 | 4 / 3 | 12 / 12 of 13 | 228 / 239 | 71 |
| 0.67 | 0 / 0 | 13 / 13 of 13 | 240 / 248 | 74 |
| 0.75 | 0 / 0 | 13 / 13 of 13 | 240 / 248 | 74 |
| 0.9 | 0 / 0 | 13 / 13 of 13 | 249 / 256 | 76 |

The vote blocks almost every error, but at every threshold it also removes about 85 % of the correct auto-accepts. No
threshold fixes this. `select_rulings` sends at most two rulings per CN-8 line, so the rulings sent are chosen to cover
several codes. In iteration 8, 154 of the 324 rows with a CN-8 end in an exact tie, and shares above 0.5 are rare.

**B. Other uses of the same rulings** (*t* = 0.6 where a share applies)

| Variant | Wrong auto-accept rows | Lines blocked | Right rows lost | Always-right lines to review |
|---|---|---|---|---|
| Veto only: today's gate, unless a clear majority names another code | 36 / 31 | 1 / 2 of 13 | 47 / 50 | 15 of 83 |
| The nearest ruling sent is at the model's CN-8 | 21 / 21 | 6 / 6 of 13 | 20 / 21 | 7 of 83 |
| Country vote over the 3 nearest rulings sent | 18 / 12 | 7 / 9 of 13 | 67 / 72 | 20 / 21 of 83 |

**Recommendation.**
- Do not build the vote over the rulings sent.
- First take one more measurement, eval-only: one live run, about $0.11. Log the uncapped nearest rulings, i.e. the
  top 40 vector hits that `select_rulings` already computes, with distance and country.
- Then repeat this table for a k-nearest vote (k = 3, 5, 10) and for the nearest-ruling rule.
- Choose the gate against a target. Proposal: at most 3 wrong auto-accept rows per run, while losing at most 10 % of
  the correct ones.
- **Caveat on the DE weight:** the expected code comes from whichever state issued the test ruling (IE, XI, FR and
  others), so this eval cannot validate the weight. That needs test lines from DE rulings.

## 4. A code-computed gate instead of model confidence

- **Inputs:** the evidence check (exact, fuzzy or failed); ruling agreement, using the signal chosen in §3; and later,
  agreement across N runs.
- **CN-8 auto-accept** = evidence passed, no conflicting cited ruling, and the ruling agreement holds.
- **Model confidence** stays in the output and the UI as "model estimate" only. HS-6 routing keeps the 85 % Admin
  threshold.
- **Constitution:** Principle I requires routing from "its confidence against the threshold", with a test at exactly
  the threshold. It needs an amendment through `/speckit-constitution`: the CN-8 gate becomes code-computed agreement,
  and the Admin threshold then governs HS-6 only. The feature 004 written-by-rule requirement changes with it.
- **Files:**
  - `agent/routing.py`: the agreement function and the CN-8 gate, replacing the confidence test in
    `cn8_written_by_rule`.
  - `tools/classify_cn8.py`: computed after `select_rulings` and stored on the choice.
  - `agent/schemas.py`: `Cn8Choice` gains the majority, the share, the competing codes and the gate reason.
  - `agent/config.py`: `ENTRY_COUNTRY` and the share threshold.
  - `agent/store.py`: `_reevaluate_cn8` and its audit notes, which follow the confidence threshold today.
  - `ui/view.py`: the CN-8 reason text (lines 423–427).
  - Tests: unit routing, integration `classify_cn8`, the store tests, and `tests/eval/cn8_eval.py`.
  - Later, `ui/admin.py` for the entry country.

## 5. Eval

Add to each line and run of `tests/eval/cn8_eval.py`:
- `majority_cn8`, `majority_share`, `model_agrees_with_majority`;
- `vote_route`, the route the new gate would give;
- `nearest_hits` for §3: the uncapped vector hits with reference, CN-8, distance and country.

Save iterations 8 and 9 as `cn8_eval_iteration8.json` and `cn8_eval_iteration9.json`, as iteration 5 was, so the dry
run can be repeated from the repository.

## 6. Retrieval determinism (a separate small step)

- **The problem:** the rulings sent, or their order, differed between runs for 27 of 120 lines.
- **Why a stable sort alone won't fix it:** sorting by (score, reference) helps only when scores tie exactly. The likely
  cause is that the query embedding varies slightly from call to call, which reorders near-equal distances.
- **Proposal:**
  - rank by (distance rounded to 4 decimals, reference);
  - cache the query embedding for each normalised line text within a session;
  - log distances in one run to confirm the cause;
  - add a unit test in which jittered distances give the same order.

## Open decisions

1. The gate signal: the nearest ruling, a k-nearest vote (after the logging run), or no ruling gate at all.
2. The target in §3.
3. The weights: 3 for DE, 1 for XI. This eval cannot test them.
4. Whether to do the determinism step first, so that the measurements are repeatable.
