# Evaluation report: feature 017, the after-runs of 2026-11-23

The three sets after the change (the Chinese examples in `JUDGEMENT_SYSTEM`, coolant-9 in the coolant set; branch
`017-coolant-vague-chinese-examples` at 99da930), three runs each, Gemini 2.5 Flash with reasoning off, query expansion
off, customs wording off, threshold 85, floor 0.40, every chapter (the store of the full extract of 2026-11-18,
123,531 rulings), the precedent override off in the recorded measures and replayed on from the same rows. Run in
the author's stages (spec clarification 5): the coolant set, then the outside set, then the 120-line set, each
stage read before the next; no stage missed, so nothing was re-run and no revision round was asked for (tasks T018
and T019 were not triggered).

| Set | After-run file | Iteration | Baseline | Cost by the tally |
|---|---|---|---|---|
| 120-line | `tests/eval/hs6_eval_017-after_en_expansion-off_wording-off.json` | 22 | iteration 21 (`hs6_eval_014a-rule-a.json`) | $0.5328, 399 s |
| coolant (nine lines) | `tests/eval/hs6_eval_coolant_017-after_en_expansion-off_wording-off.json` | 10 | iteration 9 (`hs6_eval_coolant_014a-rule-a.json`) | $0.0395, 52 s |
| outside | `tests/eval/hs6_eval_outside_017-after_en_expansion-off_wording-off.json` | 3 | iteration 1 (`hs6_eval_outside_014a-a_en_expansion-off_wording-off.json`) | $0.0521, 46 s |

Every number below was read from the after-run files and the baseline files with the snippet of quickstart.md §3,
with no model call. "By majority per line" means the line's most frequent top-1 over its three runs (a tie to the
earliest run), and for the wrong auto-accepts a line that is auto-accepted with a wrong top-1 in at least 2 of its 3
runs (spec SC-003, the author's decision of 2026-11-23). No line failed in any run of any set.

## 1. The 120-line set (iteration 22 against iteration 21)

Majority per line, which decides pass or fail (SC-003):

| Measure | Baseline, iteration 21 | After, iteration 22 | Criterion |
|---|---|---|---|
| Majority top-1, override off | 77 of 120 | **78 of 120** | at least 77: pass |
| Wrong auto-accepts by majority per line, override off | 3: IEBTIIENEN004-2024-BTI356, MTBTI2024-002, MTBTI2025-011 | **3: the same three lines** | at most 3: pass |
| Majority top-1, override on | 80 of 120 | 80 of 120 | reported |
| Wrong auto-accepts by majority per line, override on | 3, the same lines | 3, the same lines | reported |

Per run (right, auto-accepted and wrong auto-accepted), the override off and on:

| Run | Right, off | Auto-accepted, off | Wrong auto-accepted, off | Right, on | Auto-accepted, on | Wrong auto-accepted, on |
|---|---|---|---|---|---|---|
| Baseline 1 | 76 | 63 | 3 | 79 | 66 | 3 |
| Baseline 2 | 77 | 63 | 3 | 80 | 66 | 3 |
| Baseline 3 | 77 | 62 | 3 | 80 | 65 | 3 |
| After 1 | 78 | 63 | 3 | 80 | 65 | 3 |
| After 2 | 77 | 64 | 3 | 79 | 66 | 3 |
| After 3 | 78 | 62 | 2 | 80 | 65 | 3 |

The wrong auto-accepts per run are the baseline's three lines in every run, except run 3 with the override off, where
MTBTI2024-002 (a plastic or steel container with a suction pump, 8424.89, the model's 8479.89) went to review. In the
top 3 per run 105 / 104 / 105 (baseline 104 / 105 / 105); the same top-1 in all three runs on 116 lines and the same
route on 118 (baseline 116 and 117). End to end (the HS-6 chosen with the CN-8 of iteration 11): 64 / 63 / 65 per run
with the override off, 66 / 64 / 66 on (baseline 62 / 61 / 63 and 65 / 64 / 66 by the stored cross-layer tables).

**Flags per run against the baseline.** Iteration 21 flagged five lines vague in every run: IEBTIIENEN004-2023-BTI572,
IEBTIIENEN004-2025-BTI249, IEBTIIENEN004-2026-BTI105, IEBTIIENEN004-2026-BTI124 and XIBTI505068566. Iteration 22
flags three in every run: IEBTIIENEN004-2023-BTI572 (a pharmaceutical shipper on an aluminium pallet),
IEBTIIENEN004-2026-BTI105 ("Machine Parts", polyethylene wear strips) and XIBTI505068566 (a transformer). Two lines
changed their flag, both English and in all three runs, from vague to OK: IEBTIIENEN004-2025-BTI249 (a static
single-use assembly for the pharmaceutical industry, 8421.39; its top-1 is unchanged, still wrong) and
IEBTIIENEN004-2026-BTI124 (a straddle-carrier assembly, 8431.49; its route moved from ask the shipper to review and
its top-1 from 7308.90 to 7306.61 in runs 2 and 3, still wrong). No line gained a flag.

**Line diff.** Eight lines changed their majority top-1 against iteration 21 (net +1 right: four lines became right,
two became wrong, two stayed wrong at another code):

| Line | Goods | Expected | Baseline top-1 per run (majority) | After top-1 per run (majority) | Routes after | Flag | Reading |
|---|---|---|---|---|---|---|---|
| FRBTIFR-BTI-2025-02100 | protective work gloves (fr) | 4203.29 | 6116.10 ×3 (6116.10) | 4203.29 ×3 (4203.29), right | auto_accept ×3 | unchanged (OK) | not attributable: flag unchanged, reason text not recorded |
| IEBTIIENEN004-2024-BTI261 | hard plastic protection case for a laptop | 4202.92 | 4202.12 ×3 (4202.12) | 4202.92 ×3 (4202.92), right | review ×3 | unchanged (OK) | not attributable: flag unchanged, reason text not recorded |
| IEBTIIENEN004-2026-BTI23 | grosgrain textile strips with elastic | 6307.90 | 5808.90 ×3 (5808.90) | 6307.90, 5808.90, 6307.90 (6307.90), right | review ×3 | unchanged (OK) | not attributable: flag unchanged, reason text not recorded |
| MTBTI2025-018 | woven polyester cover with rope | 6307.90 | 6306.12, 6307.90, 6307.90 (6307.90) | 6306.12 ×3 (6306.12), wrong | review ×3 | unchanged (OK) | noise: the baseline runs disagreed |
| IEBTIIENEN004-2026-BTI124 | straddle-carrier assembly | 8431.49 | 7308.90 ×3 (7308.90) | 7308.90, 7306.61, 7306.61 (7306.61), wrong | review ×3 (was ask_shipper ×3) | vague to OK in every run | flag changed |
| IEBTIIENEN004-2026-BTI72 | period pants, nylon | 9619.00 | 6108.22, 9619.00, 9619.00 (9619.00) | 6108.22 ×3 (6108.22), wrong | review ×3 (was review, auto_accept, auto_accept) | unchanged (OK) | noise: the baseline runs disagreed |
| IEBTIIENEN004-2026-BTI71 | period pants, cotton | 9619.00 | 9619.00, 6108.21, 6108.21 (6108.21) | 9619.00 ×3 (9619.00), right | auto_accept ×3 (was auto_accept, review, review) | unchanged (OK) | noise: the baseline runs disagreed |
| IEBTIIENEN004-2026-BTI222 | sketching and drawing set | 9609.10 | 9609.10 ×3 (9609.10) | 9609.90 ×3 (9609.90), wrong | review ×3 (was auto_accept ×3) | unchanged (OK) | not attributable: flag unchanged, reason text not recorded |

The three noise lines are three of the four lines whose baseline runs already disagreed among themselves (spec
FR-007); the fourth, XIBTI505060394, kept its majority. The four "not attributable" lines kept their OK flag; an OK
judgement's reason text reaches the ranking prompt and is not recorded in the rows, so the change cannot be tied to the
examples or ruled out as noise. Tokens 1,168,313 over 1,077 calls.

## 2. The coolant set (iteration 10 against iteration 9)

Majority per line (SC-004's coolant half, the original eight; coolant-9 apart, SC-001):

| Measure | Baseline, iteration 9 | After, iteration 10 | Criterion |
|---|---|---|---|
| Original eight right on majority (the summary's `lines` entries) | 8 of 8 | **8 of 8** | 8 of 8: pass |
| Wrong auto-accepts by majority per line, the original eight | 0 | 0 | reported, off and on alike |
| Coolant-9 (the live-test line), majority | not in the set | 3403.99, right | reported with SC-001 |

Per run, the original eight (coolant-9 excluded), the override off; the override on gives the same numbers in every
run (no override fired on any coolant line):

| Run | Right | Auto-accepted | Wrong auto-accepted |
|---|---|---|---|
| Baseline 1, 2, 3 | 8, 8, 8 | 1, 1, 1 (coolant-5) | 0, 0, 0 |
| After 1, 2, 3 | 8, 8, 8 | 1, 1, 1 (coolant-5) | 0, 0, 0 |

With coolant-9 counted: right 9 / 9 / 9, auto-accepted 1 / 1 / 1, wrong auto-accepted 0 / 0 / 0; the set-wide
`majority_top1` is 9 of 9.

Every line, flag, route and top-1 per run (the after-run's three runs were identical on every line; the baseline's
three runs were identical too):

| Line | Text | Expected | Baseline flag, route, top-1 (every run) | After flag, route, top-1 (every run) | Criterion |
|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | vague, ask_shipper, 2710.19 | vague, ask_shipper, 2710.19 | SC-002: vague and ask in every run, pass |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | vague, ask_shipper, 3820.00 | vague, ask_shipper, 3820.00 | SC-002: pass |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | vague, ask_shipper, 3403.99 | **OK, review, 3403.99** | SC-001: OK and the vote's route in every run, pass |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | OK, review, 3403.99 | OK, review, 3403.99 | SC-007: OK in every run, pass |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum mineral oil content more than 70% by weight | 2710.19 | OK, auto_accept, 2710.19 | OK, auto_accept, 2710.19 | SC-007: pass |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral base oil | 3403.99 | OK, review, 3403.99 | OK, review, 3403.99 | SC-007: pass |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | OK, review, 3403.99 | OK, review, 3403.99 | SC-007: pass |
| coolant-8 | 冷却液 | ask_shipper | vague, ask_shipper, 3820.00 | vague, ask_shipper, 3820.00 | SC-002: pass |
| coolant-9 | 金属加工冷却液，不含矿物基础油 (the live-test line of 2026-11-20) | 3403.99 | not in the set | **OK, review, 3403.99** | SC-001: pass |

Coolant-3's and coolant-9's route is the vote's: the gate reads `vote_disagrees` in every run (the five nearest
eligible rulings' majority is 2710.19, at a share of 0.8 for coolant-3 and 0.6 for coolant-9, against the model's
3403.99), so both go to review with the competing rulings as the reason, as coolant-4, -6 and -7 do. The flag
comparison with iteration 9: coolant-1, -2 and -8 flagged in every run before and after; coolant-3 flagged in every
run before and in none after; coolant-4 to -7 OK in every run before and after; coolant-9 OK in every run (new).
Tokens 80,793 over 81 calls.

## 3. The outside set (iteration 3 against iteration 1)

Majority per line (SC-004):

| Measure | Baseline, iteration 1 | After, iteration 3 | Criterion |
|---|---|---|---|
| Right on majority (the summary's `lines` entries) | 12 of 14 | **12 of 14** | at least 12 of 14: pass |
| Wrong auto-accepts by majority per line | 1: FRBTIFR-BTI-2026-00308 | 1: the same line | reported, off and on alike |

Per run, the override off; the override on gives the same numbers in every run:

| Run | Right | Auto-accepted | Wrong auto-accepted |
|---|---|---|---|
| Baseline 1, 2, 3 | 12, 12, 12 | 7, 8, 8 | 0, 1, 1 |
| After 1, 2, 3 | 12, 12, 12 | 8, 8, 8 | 1, 1, 1 |

The two lines wrong on majority are the baseline's two: FRBTIFR-BTI-2026-00308 (the bike U-lock, 8301.10; the
model's 8301.40 in every run, auto-accepted in every run; the baseline's run 1 had 8301.50 in review, so this is one of
the lines whose baseline runs disagreed, run-to-run noise) and DEBTI19155/25-1 (quartz wrist watches, 9102.11; 9102.99 in
every run before and after, review). No line changed its majority top-1 for any other reason. Flags: none in any run
before or after. In the top 3 per run 13 / 13 / 13. Tokens 111,638 over 126 calls.

## 4. The verdicts and the stage reached

| Criterion | Verdict | Evidence |
|---|---|---|
| SC-001 (coolant-3 and coolant-9 OK in every run, the vote's route) | pass | section 2: OK, review (vote disagrees) in all three runs |
| SC-002 (coolant-1, -2, -8 vague and ask the shipper in every run) | pass | section 2 |
| SC-003 (120-line: majority top-1 at least 77; wrong auto-accepts by majority per line at most 3, the override off) | pass | section 1: 78; 3, the same three lines; override on 80 and the same 3 |
| SC-004 (original eight each right on majority; outside at least 12 of 14) | pass | sections 2 and 3: 8 of 8; 12 of 14; wrong auto-accepts reported, 0 and 1 by majority per line, 0 / 0 / 0 and 1 / 1 / 1 per run |
| SC-005 (offline suite without a key, no test calls a model) | pass | `pytest -q`: 1774 passed, 4 live tests deselected (see the final checks of tasks T023) |
| SC-006 (spend within twice the approved estimate; the approval before the first paid call) | pass | section 5 |
| SC-007 (coolant-4 to -7 OK in every run) | pass | section 2 |

The stage reached: all three. No criterion missed in any stage, so the stop-and-report branch and the revision round
(tasks T018, T019) were not used; the line diff of section 1 is the record of what changed, not a decision request.

A first attempt at stage 1 (12:34 UTC) failed on every line in one second with no model call and no spend: the key
of that session carried a zero-data-retention guardrail that excluded the only Google AI Studio endpoint of
google/gemini-2.5-flash (OpenRouter 404, "ZDR violation (guardrail)"), and the key expired at 12:48 UTC. The history
entry, the latest-run file and the report it rewrote were reverted before any paid run; the runs above were made at
13:08 to 13:19 UTC with the valid key after the author fixed it. The evaluation also printed "TARIC not loaded" for the
worktree, which has no `data/taric.jsonl`; the HS-6 evaluation does not read the TARIC snapshot.

## 5. The approval and the spend

- **Approval** (the author, through the coordinator, 2026-11-23, before the first paid call): the $0.65 estimate for
  one pass of the three sets, the $1.30 cap under the 2x rule over everything, in stages (the coolant set, then the
  outside set, then the 120-line set, each only when the stage before held; stop and report on any miss; no revision
  round without the author's go-ahead; the tallies checked before each stage), with permission to commit the result
  files, the history entries, the re-rendered reports, this report and the backlog and README edits once all three
  sets had run (spec clarification 5; tasks T015).
- **The budget pre-checks**: before stage 2, $0.0395 spent plus about $0.05; before stage 3, $0.0916 plus about
  $0.52; both within $1.30.
- **Spend by the evaluation's tallies**: $0.0395 + $0.0521 + $0.5328 = **$0.6244** (the tallies price tokens from the
  project's table and run high, as in feature 014a).
- **Spend by the key's usage** (the `usage` field of OpenRouter's key endpoint, read with the key only in the request
  header): 20.218353054 USD before the first paid call (13:08 UTC) and 20.742832704 USD right after the last run
  (13:19 UTC), a spend of $0.5245; read again at 13:23 UTC once OpenRouter had settled it, 20.748176214 USD, a spend
  of **$0.5298**. Within the $0.65 approval and the $1.30 cap; the approval preceded the first paid call (SC-006).
