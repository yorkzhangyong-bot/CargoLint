# Feature 014a: the evaluation report

Rendered by `tests/eval/eval_diff_014a.py` from `tests/eval/hs6_eval_history.json`, `tests/eval/hs6_eval_coolant_history.json` and the logged rows of the runs; no model call. Every run used Gemini 2.5 Flash with reasoning off, query expansion off, threshold 85, ask floor 50 and three independent runs. Majority: a line's most frequent top-1 (for a coolant line expecting "ask the shipper", its route), a tie going to the earliest run.

- Baseline (T006): 120-line iteration 12, coolant iteration 1, on the store of twelve chapters (74,044 rulings) and the code of `main` plus the coolant set.
- After-runs (T044): 120-line iterations 13 (switch off) and 15 (switch on), coolant iterations 2 and 3, on the rebuilt store of every chapter (123,531 rulings in 95 chapters, T043).
- The precedent override: each row's route, and every route and auto-accept count below unless marked, has it off, as the evaluation keeps its history comparable (feature 008), while the app ships with it on (`CARGOLINT_HS6_OVERRIDE`, at OVERRIDE_MIN 5). Section 1 adds the rows with it on from each history entry's `on` block: the same model answers routed with the override on, no model call. In the coolant rows it changes no route and no HS-6, so section 2 stands for both settings.
- Iteration 14 (120 lines, switch on) is not used: the German rewrite of the longest ruling descriptions exceeded its 300-character cap, refused inside the call before the retry, so 6 to 7 lines per run failed. Commit 290b3f5 retries such an answer once; iteration 15 is the re-run (see section 4).
- In the baseline, runs 2 and 3 each lost one line to an OpenRouter rate-limit error (HS-6 step failed).
- Spend: T006 $0.5576 (the evaluation's tally); T043 $0.194 (the refresh's own count, equal to the key's usage over the run); T044 $1.718 by the key's usage, the provider's charge for its five runs, the discarded iteration 14 among them. The evaluation's own tallies for those runs sum to $1.7767: they price tokens from the project's price table and miss one failed rewrite call of 65,521 output tokens.

## 1. The 120-line set

| | Baseline (it. 12) | After, switch off (it. 13) | After, switch on (it. 15) |
|---|---|---|---|
| Majority top-1 | 84/120 | 77/120 | 74/120 |
| Top-1 per run | 83 / 84 / 83 | 76 / 77 / 77 | 76 / 74 / 76 |
| In top 3 per run | 108 / 107 / 105 | 104 / 105 / 105 | 103 / 100 / 99 |
| Auto-accepted per run | 68 / 70 / 67 | 65 / 65 / 65 | 68 / 68 / 71 |
| Wrong, auto-accepted per run | 3 / 4 / 3 | 4 / 4 / 4 | 6 / 8 / 9 |
| Decided without a voting ruling per run | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| HS-6 step failed per run | 0 / 1 / 1 | 0 / 0 / 0 | 3 / 5 / 6 |
| Majority top-1, override on | 87/120 | 80/120 | 79/120 |
| Top-1 per run, override on | 87 / 87 / 87 | 79 / 80 / 80 | 81 / 79 / 79 |
| Auto-accepted per run, override on | 72 / 73 / 71 | 68 / 68 / 68 | 74 / 74 / 77 |
| Wrong, auto-accepted per run, override on | 3 / 4 / 3 | 4 / 4 / 4 | 7 / 9 / 11 |
| Cost (eval tally) | $0.5237 | $0.5249 | $0.5965 |

## 2. The coolant set

| | Baseline (it. 1) | After, switch off (it. 2) | After, switch on (it. 3) |
|---|---|---|---|
| Majority right | 6/8 | 7/8 | 8/8 |
| Right per run | 6 / 6 / 6 | 7 / 7 / 7 | 7 / 8 / 8 |
| In top 3 per run | 4 / 4 / 4 | 6 / 6 / 6 | 6 / 6 / 6 |
| Auto-accepted per run | 0 / 0 / 0 | 3 / 3 / 3 | 3 / 4 / 4 |
| Wrong, auto-accepted per run | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Decided without a voting ruling per run | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| HS-6 step failed per run | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Cost (eval tally) | $0.0339 | $0.0352 | $0.0382 |

Each line's majority outcome (its top-1, or its route for a line expecting "ask the shipper"):

| Line | Text | Expected | Baseline | After, switch off | After, switch on |
|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 3820.00 ✗ | 2710.19 ✓ | 2710.19 ✓ |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | ask_shipper ✓ | ask_shipper ✓ | ask_shipper ✓ |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 ✓ | 3403.99 ✓ | 3403.99 ✓ |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 ✓ | 3403.99 ✓ | 3403.99 ✓ |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum mineral oil content more than 70% by weight | 2710.19 | 2710.19 ✓ | 2710.19 ✓ | 2710.19 ✓ |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral base oil | 3403.99 | 3403.19 ✗ | 3403.99 ✓ | 3403.99 ✓ |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 ✓ | 3403.99 ✓ | 3403.99 ✓ |
| coolant-8 | 冷却液 | ask_shipper | ask_shipper ✓ | review ✗ | ask_shipper ✓ |

## 3. Floor replays (no model call)

The switch-off after-runs' votes rebuilt from their `vote_hits` at higher floors (`--replay FILE --floor X`); exact, as each floor is at or above the runs' 0.40.

| Set | Floor | Auto-accepted per run | Wrong, auto-accepted per run | Without a voting ruling per run |
|---|---|---|---|---|
| 120 lines | 0.40 (the run) | 65 / 65 / 65 | 4 / 4 / 4 | 0 / 0 / 0 |
| 120 lines | 0.45 | 65 / 65 / 65 | 4 / 4 / 4 | 0 / 0 / 0 |
| 120 lines | 0.50 | 65 / 65 / 65 | 4 / 4 / 4 | 0 / 0 / 0 |
| 120 lines | 0.55 | 65 / 65 / 65 | 4 / 4 / 4 | 0 / 0 / 0 |
| coolant | 0.40 (the run) | 3 / 3 / 3 | 0 / 0 / 0 | 0 / 0 / 0 |
| coolant | 0.45 | 3 / 3 / 3 | 0 / 0 / 0 | 0 / 0 / 0 |
| coolant | 0.50 | 4 / 4 / 4 | 0 / 0 / 0 | 0 / 0 / 0 |
| coolant | 0.55 | 4 / 4 / 4 | 0 / 0 / 0 | 1 / 1 / 1 |

No floor change is made: the 120-line set does not move at any of these floors, and the floor stays at 0.40 (the author's decision; no tuning in this feature). The coolant set gains one right auto-accept per run from 0.50.

## 4. The success criteria

- **SC-001** (T043): passed. The rebuild kept every valid ruling of the extract of 2026-11-18, 123,531 in 95 chapters; its counts show the 74,044 unchanged rulings of the twelve chapters reused and the 49,487 new ones embedded, none dropped; $0.194 (17,648,924 tokens), 6,333 s, the store 3,454,915,131 bytes.
- **SC-002**: passed. In the coolant set's after-runs no row has a voting ruling outside its vote chapters (0 switch off, 0 switch on) and none lists a chapter 84 ruling (0 and 0).
- **SC-003**: this report, every number from the history entries and rows above.
- **SC-004**: **failed**. Wrong auto-accepts on the 120-line set, summed over three runs: 12 after (switch off, the shipped default) against 10 in the baseline. The lines (section 5): IEBTIIENEN004-2024-BTI284 -1 (run-to-run variation); IEBTIIENEN004-2024-BTI208 +3 (vote scope). The vote scope's line is auto-accepted wrong in every run where the old vote, on the same rows, would have sent it to review. No fallback to the unscoped vote and no switch for it were added; the author decides. With the precedent override on, as the app ships: 12 against 10, the same verdict.
- **FR-026's criterion** for turning the switch on later: **not met**. Majority top-1 of both sets together: 82 with the switch on (120 lines 74, coolant 8) against 84 with it off (77 and 7); with the precedent override on, 87 against 87, not higher either, and the switch-on after-run then auto-accepts 27 wrong over its three runs against 23 with the override off. The plain 冷却液 routed to ask the shipper in every switch-on run (ask_shipper, ask_shipper, ask_shipper), the second condition, met. The switch stays off (SC-006). With the switch on, some lines still failed their HS-6 step after the fix (3 / 5 / 6 per run; 7 lines: the rewrite of a long ruling description stayed over 300 characters after its retry, and one call ran to 65,521 output tokens); on the 113 lines that never failed, the majority top-1 is 73 with the switch on against 73 with it off.
- **SC-005**: every caption state and citation case is covered offline (`pytest -q`).
- **SC-006**: `CARGOLINT_CUSTOMS_WORDING` is off by default; this report records the off/on comparison.

## 5. Why the 120-line numbers moved (offline analysis)

Every line whose majority outcome or auto-accepts changed between the baseline (it. 12) and the switch-off after-run (it. 13). Proposed: in how many of the three runs the after top-1 was a code the rulings proposed before the ranking. New-chapter codes: the codes the rulings of newly indexed chapters proposed in the after-run. Old vote: the routes the unscoped vote would give the same after-rows. The causes are read as `eval_diff_014a.cause_of` states them.

| Line | Expected | Baseline top-1 (routes) | After top-1 (routes) | Proposed | After top-1's chapter | New-chapter codes proposed | Old vote's routes | Outcome change: cause | Route change: cause |
|---|---|---|---|---|---|---|---|---|---|
| IEBTIIENEN004-2025-BTI245 | 3926.90 | 3926.90 / 3926.90 / 3926.90 (auto / auto / auto) | 3926.90 / 3926.90 / 3926.90 (review / review / review) | 3/3 | one of the twelve | 8108.20, 9019.20 | review / review / review | unchanged | auto 3 → 0: new-chapter rulings in the vote |
| IEBTIIENEN004-2025-BTI258 | 3926.90 | 3926.90 / 3926.90 / 3926.90 (auto / auto / auto) | 3926.90 / 3926.90 / 3926.90 (review / review / review) | 3/3 | one of the twelve | 9019.20, 9033.00 | review / review / review | unchanged | auto 3 → 0: new-chapter rulings in the vote |
| IEBTIIENEN004-2025-BTI463 | 3926.90 | 3926.90 / 3926.90 / 3926.90 (review / review / review) | 4016.99 / 4016.99 / 4016.99 (review / review / review) | 3/3 | newly indexed | 4016.99 | review / review / review | right → wrong: new-chapter proposals | unchanged |
| IEBTIIENEN004-2024-BTI141 | 3926.90 | 3926.90 / 3926.90 / 3926.90 (auto / auto / auto) | 9111.80 / 9111.80 / 9111.80 (review / review / review) | 0/3 | newly indexed | 7007.19, 7616.99, 9113.90 | review / review / review | right → wrong: new-chapter proposals | auto 3 → 0: new-chapter proposals |
| IEBTIIENEN004-2023-BTI572 | 3923.10 | 3923.10 / 3923.10 / 3923.10 (review / review / review) | 8609.00 / 8609.00 / 8609.00 (review / review / review) | 3/3 | newly indexed | 3824.99, 8609.00 | review / review / review | right → wrong: new-chapter proposals | unchanged |
| IEBTIIENEN004-2024-BTI284 | 4202.12 | 4202.32 / 4202.92 / 4202.32 (review / auto / review) | 4202.92 / 4202.92 / 4202.92 (review / review / review) | 3/3 | one of the twelve | 7616.99 | review / review / review | top-1 changed, wrong → wrong: run-to-run variation | auto 1 → 0: run-to-run variation |
| FRBTIFR-BTI-2025-02100 | 4203.29 | 4203.29 / 4203.29 / 6116.10 (auto / auto / review) | 6116.10 / 6116.10 / 6116.10 (review / review / review) | 0/3 | one of the twelve | none | review / review / review | right → wrong: run-to-run variation | auto 2 → 0: run-to-run variation |
| IEBTIIENEN004-2024-BTI208 | 6109.90 | 6109.90 / 6109.90 / 6109.90 (review / review / review) | 6114.30 / 6114.30 / 6114.30 (auto / auto / auto) | 3/3 | one of the twelve | none | review / review / review | right → wrong: new-chapter proposals | auto 0 → 3: vote scope |
| IEBTIIENEN004-2026-BTI23 | 6307.90 | 6307.90 / 6307.90 / 6307.90 (auto / auto / auto) | 5808.90 / 5808.90 / 5808.90 (review / review / review) | 3/3 | newly indexed | 5806.32, 5808.90 | review / review / review | right → wrong: new-chapter proposals | auto 3 → 0: new-chapter proposals |
| IEBTIIENEN004-2024-BTI8 | 6307.90 | 6307.90 / 4602.90 / 4602.90 (auto / review / review) | 4602.90 / 4602.90 / 4602.90 (review / review / review) | 3/3 | newly indexed | 4602.19, 4602.90 | review / review / review | unchanged | auto 1 → 0: run-to-run variation |
| IEBTIIENEN004-2025-BTI301 | 7325.99 | 7325.99 / 7325.99 / 7325.99 (review / review / review) | 9026.90 / 9026.90 / 9026.90 (review / review / review) | 3/3 | newly indexed | 9026.90 | review / review / review | right → wrong: new-chapter proposals | unchanged |
| IEBTIIENEN004-2026-BTI118 | 9503.00 | 9503.00 / 9503.00 / 9503.00 (auto / auto / review) | 9503.00 / 9503.00 / 9503.00 (auto / auto / auto) | 3/3 | one of the twelve | none | auto / auto / review | unchanged | auto 2 → 3: vote scope |
| IEBTIIENEN004-2026-BTI71 | 9619.00 | 6108.21 / 9619.00 / 9619.00 (review / auto / auto) | 9619.00 / 6108.21 / 6108.21 (auto / review / review) | 1/3 | one of the twelve | none | auto / review / review | right → wrong: run-to-run variation | auto 2 → 1: run-to-run variation |
| IEBTIIENEN004-2026-BTI222 | 9609.10 | 9609.90 / 9609.90 / 9609.90 (review / review / review) | 9609.10 / 9609.10 / 9609.10 (auto / auto / auto) | 3/3 | one of the twelve | 4903.00 | auto / auto / auto | wrong → right: new-chapter proposals | auto 0 → 3: new-chapter proposals |

Totals per cause (lines whose majority outcome changed; auto-accepts summed over the three runs, after less before):

| Cause | Majority right → wrong | Majority wrong → right | Wrong auto-accepts | Right auto-accepts |
|---|---|---|---|---|
| new-chapter proposals | 6 | 1 | +0 | -3 |
| new-chapter rulings in the vote | 0 | 0 | +0 | -6 |
| vote scope | 0 | 0 | +3 | +1 |
| run-to-run variation | 2 | 0 | -1 | -4 |
| other | 0 | 0 | +0 | +0 |

The majority top-1 fell from 84 to 77. New-chapter proposals account for 5 of it net (6 lines right → wrong, 1 wrong → right): the candidate proposal now reads the rulings of every chapter, and where rulings of a newly indexed chapter come nearest to a line they propose their codes and the model ranks a code of that chapter, or one their tags favour, first. Run-to-run variation accounts for 2 (lines whose baseline runs already disagreed). Where the top-1 stayed, rulings of the new chapters also entered the vote and turned right auto-accepts into review (the old vote, on the same rows, would have done the same). The vote scope changed the routes of 2 lines (IEBTIIENEN004-2024-BTI208, IEBTIIENEN004-2026-BTI118): one gained a right auto-accept, the other is SC-004's wrong auto-accept, in every run.

### The coolant set, and the plain 冷却液

| Line | Expected | Baseline top-1 (routes) | After top-1 (routes) | Proposed | New-chapter codes proposed | Old vote's routes | Outcome change: cause | Route change: cause |
|---|---|---|---|---|---|---|---|---|
| coolant-1 (冷却液 矿物油含量大于70%) | 2710.19 | 3819.00 / 3820.00 / 3820.00 (ask / ask / ask) | 2710.19 / 2710.19 / 2710.19 (review / review / review) | 3/3 | 2710.19, 3402.50, 3824.99 | review / review / review | wrong → right: new-chapter proposals | ask → review: new-chapter proposals |
| coolant-4 (coolant without mineral base oil, for metal working) | 3403.99 | 3403.99 / 3403.99 / 3403.99 (review / review / review) | 3403.99 / 3403.99 / 3403.99 (auto / auto / auto) | 3/3 | 2710.19, 2710.20, 3403.99 | review / review / review | unchanged | auto 0 → 3: vote scope |
| coolant-5 (金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum mineral oil content more than 70% by weight) | 2710.19 | 2710.19 / 2710.19 / 2710.19 (review / review / review) | 2710.19 / 2710.19 / 2710.19 (auto / auto / auto) | 3/3 | 2710.12, 2710.19, 2710.20, 3403.99 | auto / auto / auto | unchanged | auto 0 → 3: new-chapter rulings in the vote |
| coolant-6 (金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral base oil) | 3403.99 | 3403.19 / 3403.19 / 3403.19 (review / review / review) | 3403.99 / 3403.99 / 3403.99 (review / review / review) | 3/3 | 2710.19, 3403.19, 3403.99 | review / review / review | wrong → right: new-chapter proposals | unchanged |
| coolant-7 (Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl) | 3403.99 | 3403.99 / 3403.99 / 3403.99 (review / review / review) | 3403.99 / 3403.99 / 3403.99 (auto / auto / auto) | 3/3 | 2710.19, 2710.20, 3403.99 | review / review / review | unchanged | auto 0 → 3: vote scope |
| coolant-8 (冷却液) | ask_shipper | 3820.00 / 3820.00 / 3820.00 (ask / ask / ask) | 3820.00 / 3820.00 / 3820.00 (review / review / review) | 0/3 | 3402.50, 3824.99, 8708.99 | review / review / review | right → wrong: new-chapter proposals | ask → review: new-chapter proposals |

The plain 冷却液 (coolant-8) is flagged vague in every run, so no vote routes it: its route is the model's estimate against the ask floor of 50. In the baseline its top-1 3820.00 came at 40 / 40 / 40 (ask the shipper); after, with the rulings of chapter 38 now indexed, the proposal added 3824.99, 3402.50, 8708.99 and the same top-1 came at 50 / 50 / 50, exactly the floor, so the line went to review: a new-chapter proposal acting through the model's estimate, not the vote scope. With the switch on it routed to ask the shipper in every run.

## 6. Decisions left to the author

- SC-004 failed by two wrong auto-accepts: keep the chapter-scoped vote, or change it (the spec forbids a fallback without the author's decision).
- The new chapters lowered the 120-line majority top-1 through the candidate proposal (section 5); the spec keeps the proposal over every chapter (clarification 1).
- FR-026's criterion is not met; the customs-wording switch stays off.
- A rewrite still over its 300 characters after its one retry fails the line's HS-6 step, as FR-025 says; the alternative is a cut at the last word boundary before the switch is ever turned on. Since review round 1 the rewrite's output is capped at 512 tokens, so a runaway answer (65,521 output tokens once) can no longer happen, and every attempt counts in the shipment's cost. Both matter only with the switch on.
