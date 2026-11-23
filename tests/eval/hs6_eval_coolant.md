# HS-6 evaluation report: the coolant set (feature 014a)

- **Set**: `tests/eval/hs6_eval_coolant_set.json`, 9 lines (built 2026-11-18): docs/backlog.md item 10 (user test on two metal-working coolants), the author's German line and the plain line of clarification 5; coolant-9: the live-test line of 2026-11-20, feature 017.
- **Method**: each line, as typed, goes through the 120-line set's path: the description check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes (threshold 85; a vague line goes to ask the shipper, before the vague rule of 2026-11-19 only below the ask floor of 50); no leakage guard, as no line is a ruling; ruling validity on the set's build date. `python tests/eval/hs6_eval.py --set coolant --repeat 3`.
- **Right**: a line with an expected HS-6 when its top-1 is that code; a line expecting "ask the shipper" when its route is ask_shipper, whatever codes it shows. **Majority**: a line's most frequent top-1, or route for a line expecting "ask the shipper" (a tie goes to the earliest run). **In top 3**: the lines with an expected HS-6 only. **Wrong, auto-accepted**: auto-accepted and not right. **No ruling voted**: the vote gate's no_rulings lines. **Vetoed**: the lines the vote of the candidates' chapters sent to review (rule (a)).

| Iteration | Run on | Tag | Runs | Query expansion | Customs wording | Floor | Right per run | Majority right | In top 3 per run | Auto-accepted per run | Wrong, auto-accepted per run | No ruling voted per run | Vetoed per run | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-18 | 014a-baseline | 3 | off | - | - | 6 / 6 / 6 of 8 | 6/8 | 4 / 4 / 4 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0339 (€0.0311), 63 s |
| 2 | 2026-11-18 | 014a-after | 3 | off | off | 0.4 | 7 / 7 / 7 of 8 | 7/8 | 6 / 6 / 6 | 3 / 3 / 3 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0352 (€0.0324), 36 s |
| 3 | 2026-11-18 | 014a-after | 3 | off | on | 0.4 | 7 / 8 / 8 of 8 | 8/8 | 6 / 6 / 6 | 3 / 4 / 4 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0382 (€0.0352), 38 s |
| 4 | 2026-11-18 | 014a-after-floor0.45 | 3 | off | off | 0.45 | 7 / 7 / 7 of 8 | 7/8 | 6 / 6 / 6 | 3 / 3 / 3 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0000 (€0.0000), 0 s |
| 5 | 2026-11-18 | 014a-after-floor0.50 | 3 | off | off | 0.5 | 7 / 7 / 7 of 8 | 7/8 | 6 / 6 / 6 | 4 / 4 / 4 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0000 (€0.0000), 0 s |
| 6 | 2026-11-18 | 014a-after-floor0.55 | 3 | off | off | 0.55 | 7 / 7 / 7 of 8 | 7/8 | 6 / 6 / 6 | 4 / 4 / 4 | 0 / 0 / 0 | 1 / 1 / 1 | 0 / 0 / 0 | $0.0000 (€0.0000), 0 s |
| 7 | 2026-11-19 | 014a-ablation | 3 | off | off | 0.4 | 7 / 6 / 6 of 8 | 6/8 | 6 / 6 / 6 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0348 (€0.0320), 43 s |
| 8 | 2026-11-19 | 014a-c | 3 | off | off | 0.4 | 7 / 7 / 6 of 8 | 7/8 | 5 / 5 / 5 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0335 (€0.0308), 30 s |
| 9 | 2026-11-19 | 014a-rule-a | 3 | off | off | 0.4 | 8 / 8 / 8 of 8 | 8/8 | 6 / 6 / 6 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0000 (€0.0000), 0 s |
| 10 | 2026-11-23 | 017-after | 3 | off | off | 0.4 | 9 / 9 / 9 of 9 | 9/9 | 7 / 7 / 7 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0395 (€0.0363), 52 s |

## Iteration 1 (014a-baseline, google/gemini-2.5-flash, query expansion off, customs wording -, 2026-11-18)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 3819.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 | no |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.19 (review) | 3403.19 (review) | 3403.19 (review) | 3403.19 | no |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |

## Iteration 2 (014a-after, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-18)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (review) | 3820.00 (review) | 3820.00 (review) | review | no |

## Iteration 3 (014a-after, google/gemini-2.5-flash, query expansion off, customs wording on, 2026-11-18)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.19 (review) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |

## Iteration 4 (014a-after-floor0.45, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-18)

Replay of iteration 2 (014a-after) at floor 0.45, from its vote_hits: no model call.

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (review) | 3820.00 (review) | 3820.00 (review) | review | no |

## Iteration 5 (014a-after-floor0.50, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-18)

Replay of iteration 2 (014a-after) at floor 0.5, from its vote_hits: no model call.

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (review) | 3820.00 (review) | 3820.00 (review) | review | no |

## Iteration 6 (014a-after-floor0.55, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-18)

Replay of iteration 2 (014a-after) at floor 0.55, from its vote_hits: no model call.

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 (auto_accept) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (review) | 3820.00 (review) | 3820.00 (review) | review | no |

## Iteration 7 (014a-ablation, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-19)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (review) | 2710.19 (review) | 2710.19 (review) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (review) | 3403.19 (review) | 3403.19 (review) | 3403.19 | no |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (review) | 3820.00 (review) | 3820.00 (review) | review | no |

## Iteration 8 (014a-c, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-19)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 | no |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (ask_shipper) | 3403.99 (ask_shipper) | 3403.99 (ask_shipper) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.19 (review) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |

## Iteration 9 (014a-rule-a, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-19)

Replay of iteration 2 (014a-after) at floor 0.4, from its vote_hits: no model call.

Note: rule (a) and the vague rule (2026-11-19): the exact replay of coolant iteration 2's rows by the product's routing functions

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (ask_shipper) | 2710.19 (ask_shipper) | 2710.19 (ask_shipper) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (ask_shipper) | 3403.99 (ask_shipper) | 3403.99 (ask_shipper) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |

## Iteration 10 (017-after, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-23)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| coolant-1 | 冷却液 矿物油含量大于70% | 2710.19 | 2710.19 (ask_shipper) | 2710.19 (ask_shipper) | 2710.19 (ask_shipper) | 2710.19 | yes |
| coolant-2 | 没有矿物基础油的冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-3 | 金属加工用的冷却液，不含矿物油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-4 | coolant without mineral base oil, for metal working | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-5 | 金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum miner… | 2710.19 | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 (auto_accept) | 2710.19 | yes |
| coolant-6 | 金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral ba… | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-7 | Kühlschmierstoff für die Metallbearbeitung, ohne Mineralöl | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |
| coolant-8 | 冷却液 | ask_shipper | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | 3820.00 (ask_shipper) | ask_shipper | yes |
| coolant-9 | 金属加工冷却液，不含矿物基础油 | 3403.99 | 3403.99 (review) | 3403.99 (review) | 3403.99 (review) | 3403.99 | yes |

Model: google/gemini-2.5-flash. Line-by-line results of the latest run, iteration 10 (017-after): `tests/eval/hs6_eval_coolant.json`; each run also keeps its own, `tests/eval/hs6_eval_coolant_<tag>_….json`.
