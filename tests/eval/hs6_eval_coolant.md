# HS-6 evaluation report: the coolant set (feature 014a)

- **Set**: `tests/eval/hs6_eval_coolant_set.json`, 8 lines (built 2026-11-18): docs/backlog.md item 10 (user test on two metal-working coolants), the author's German line and the plain line of clarification 5.
- **Method**: each line, as typed, goes through the 120-line set's path: the description check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes (threshold 85, ask floor 50); no leakage guard, as no line is a ruling; ruling validity on the set's build date. `python tests/eval/hs6_eval.py --set coolant --repeat 3`.
- **Right**: a line with an expected HS-6 when its top-1 is that code; a line expecting "ask the shipper" when its route is ask_shipper, whatever codes it shows. **Majority**: a line's most frequent top-1, or route for a line expecting "ask the shipper" (a tie goes to the earliest run). **In top 3**: the lines with an expected HS-6 only. **Wrong, auto-accepted**: auto-accepted and not right. **No ruling voted**: the vote gate's no_rulings lines.

| Iteration | Run on | Tag | Runs | Query expansion | Right per run | Majority right | In top 3 per run | Auto-accepted per run | Wrong, auto-accepted per run | No ruling voted per run | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-18 | 014a-baseline | 3 | off | 6 / 6 / 6 of 8 | 6/8 | 4 / 4 / 4 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | $0.0339 (€0.0311), 63 s |

## Iteration 1 (014a-baseline, google/gemini-2.5-flash, query expansion off, 2026-11-18)

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

Model: google/gemini-2.5-flash. Line-by-line results of the latest run: `tests/eval/hs6_eval_coolant.json`; each run also keeps its own, `tests/eval/hs6_eval_coolant_<tag>_….json`.
