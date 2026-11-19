# HS-6 evaluation report: the outside set (feature 014a)

- **Set**: `tests/eval/hs6_eval_outside_set.json`, 14 lines (built 2026-11-19): one EBTI ruling per line, valid on 2026-11-19 in the rebuilt store (extract of 2026-11-18), each outside the twelve chapters of the old store; the line's id is the ruling's reference, which the run keeps out; `original` renders the ruling's goods description closely in English, `text` is the rewrite in plain shipper wording after the near-duplicate check (feature 014a, 2026-11-19).
- **Method**: each line, as typed, goes through the 120-line set's path: the description check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes (threshold 85, ask floor 50); each line's source ruling is kept out (leave-one-out), its id being that ruling's reference; ruling validity on the set's build date. `python tests/eval/hs6_eval.py --set outside --repeat 3`.
- **Right**: a line with an expected HS-6 when its top-1 is that code; a line expecting "ask the shipper" when its route is ask_shipper, whatever codes it shows. **Majority**: a line's most frequent top-1, or route for a line expecting "ask the shipper" (a tie goes to the earliest run). **In top 3**: the lines with an expected HS-6 only. **Wrong, auto-accepted**: auto-accepted and not right. **No ruling voted**: the vote gate's no_rulings lines.

| Iteration | Run on | Tag | Runs | Query expansion | Customs wording | Floor | Right per run | Majority right | In top 3 per run | Auto-accepted per run | Wrong, auto-accepted per run | No ruling voted per run | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-11-19 | 014a-a | 3 | off | off | 0.4 | 12 / 12 / 12 of 14 | 12/14 | 13 / 13 / 13 | 7 / 8 / 8 | 0 / 1 / 1 | 0 / 0 / 0 | $0.0524 (€0.0483), 38 s |
| 2 | 2026-11-19 | 014a-c | 3 | off | off | 0.4 | 11 / 11 / 11 of 14 | 11/14 | 12 / 12 / 12 | 7 / 7 / 7 | 1 / 1 / 1 | 0 / 0 / 0 | $0.0521 (€0.0479), 40 s |

## Iteration 1 (014a-a, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-19)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| FRBTIFR-BTI-2025-03111 | Green tea, unfermented, in 100 g retail bags packed in boxes | 0902.10 | 0902.10 (review) | 0902.10 (review) | 0902.10 (review) | 0902.10 | yes |
| IEBTIIENEN004-2026-BTI266 | Chilli seasoning powder blend for flavouring chicken produc… | 2103.90 | 2103.90 (auto_accept) | 2103.90 (auto_accept) | 2103.90 (auto_accept) | 2103.90 | yes |
| FRBTIFR-BTI-2025-02159 | Scented paraffin candles in yellow glass jars, 2 pcs per set | 3406.00 | 3406.00 (auto_accept) | 3406.00 (auto_accept) | 3406.00 (auto_accept) | 3406.00 | yes |
| FRBTIFR-BTI-2024-07964 | Nitrile rubber gloves for food handling, five-finger, wrist… | 4015.19 | 4015.19 (auto_accept) | 4015.19 (auto_accept) | 4015.19 (auto_accept) | 4015.19 | yes |
| FRBTIFR-BTI-2025-03050 | Bamboo chopping boards with handle hole, single or in sets | 4419.11 | 4419.11 (review) | 4419.11 (review) | 4419.11 (review) | 4419.11 | yes |
| CZBTI47/137431/2026-300000-ZI/01 | Single-use paper coffee cups, plastic lined inside, for hot… | 4823.69 | 4823.69 (review) | 4823.69 (review) | 4823.69 (review) | 4823.69 | yes |
| FRBTIFR-BTI-2023-07744 | Porcelain mugs with handle, coloured, for custom printing | 6911.10 | 6911.10 (auto_accept) | 6911.10 (auto_accept) | 6911.10 (auto_accept) | 6911.10 | yes |
| ESBTIESBTI2024SOL802 | Glass tumblers 15 cm, machine made, not tempered, logo prin… | 7013.37 | 7013.37 (auto_accept) | 7013.37 (auto_accept) | 7013.37 (auto_accept) | 7013.37 | yes |
| FRBTIFR-BTI-2025-02298 | Cast aluminium frying pans, ceramic coated, bakelite handle… | 7615.10 | 7615.10 (auto_accept) | 7615.10 (auto_accept) | 7615.10 (auto_accept) | 7615.10 | yes |
| FRBTIFR-BTI-2026-02793 | Stainless steel table knives, fixed blade, 12 pcs per box | 8211.91 | 8211.91 (review) | 8211.91 (review) | 8211.91 (review) | 8211.91 | yes |
| FRBTIFR-BTI-2026-00308 | Bike U-lock, steel, with 2 keys | 8301.10 | 8301.50 (review) | 8301.40 (auto_accept) | 8301.40 (auto_accept) | 8301.40 | no |
| DEBTI7642/26-2 | Foldable baby stroller frames, aluminium and plastic, 4 whe… | 8715.00 | 8715.00 (review) | 8715.00 (review) | 8715.00 (review) | 8715.00 | yes |
| FRBTIFR-BTI-2024-01963 | Sunglasses with plastic lenses, UV protection | 9004.10 | 9004.10 (auto_accept) | 9004.10 (auto_accept) | 9004.10 (auto_accept) | 9004.10 | yes |
| DEBTI19155/25-1 | Quartz wrist watches, analogue dial, stainless steel or all… | 9102.11 | 9102.99 (review) | 9102.99 (review) | 9102.99 (review) | 9102.99 | no |

## Iteration 2 (014a-c, google/gemini-2.5-flash, query expansion off, customs wording off, 2026-11-19)

| Line | Text | Expected | Run 1 | Run 2 | Run 3 | Majority | Right |
|---|---|---|---|---|---|---|---|
| FRBTIFR-BTI-2025-03111 | Green tea, unfermented, in 100 g retail bags packed in boxes | 0902.10 | 0902.10 (review) | 0902.10 (review) | 0902.10 (review) | 0902.10 | yes |
| IEBTIIENEN004-2026-BTI266 | Chilli seasoning powder blend for flavouring chicken produc… | 2103.90 | 0904.22 (review) | 0904.22 (review) | 0904.22 (review) | 0904.22 | no |
| FRBTIFR-BTI-2025-02159 | Scented paraffin candles in yellow glass jars, 2 pcs per set | 3406.00 | 3406.00 (auto_accept) | 3406.00 (auto_accept) | 3406.00 (auto_accept) | 3406.00 | yes |
| FRBTIFR-BTI-2024-07964 | Nitrile rubber gloves for food handling, five-finger, wrist… | 4015.19 | 4015.19 (auto_accept) | 4015.19 (auto_accept) | 4015.19 (auto_accept) | 4015.19 | yes |
| FRBTIFR-BTI-2025-03050 | Bamboo chopping boards with handle hole, single or in sets | 4419.11 | 4419.11 (review) | 4419.11 (review) | 4419.11 (review) | 4419.11 | yes |
| CZBTI47/137431/2026-300000-ZI/01 | Single-use paper coffee cups, plastic lined inside, for hot… | 4823.69 | 4823.69 (review) | 4823.69 (review) | 4823.69 (review) | 4823.69 | yes |
| FRBTIFR-BTI-2023-07744 | Porcelain mugs with handle, coloured, for custom printing | 6911.10 | 6911.10 (auto_accept) | 6911.10 (auto_accept) | 6911.10 (auto_accept) | 6911.10 | yes |
| ESBTIESBTI2024SOL802 | Glass tumblers 15 cm, machine made, not tempered, logo prin… | 7013.37 | 7013.37 (auto_accept) | 7013.37 (auto_accept) | 7013.37 (auto_accept) | 7013.37 | yes |
| FRBTIFR-BTI-2025-02298 | Cast aluminium frying pans, ceramic coated, bakelite handle… | 7615.10 | 7615.10 (auto_accept) | 7615.10 (auto_accept) | 7615.10 (auto_accept) | 7615.10 | yes |
| FRBTIFR-BTI-2026-02793 | Stainless steel table knives, fixed blade, 12 pcs per box | 8211.91 | 8211.91 (review) | 8211.91 (review) | 8211.91 (review) | 8211.91 | yes |
| FRBTIFR-BTI-2026-00308 | Bike U-lock, steel, with 2 keys | 8301.10 | 8301.40 (auto_accept) | 8301.40 (auto_accept) | 8301.40 (auto_accept) | 8301.40 | no |
| DEBTI7642/26-2 | Foldable baby stroller frames, aluminium and plastic, 4 whe… | 8715.00 | 8715.00 (review) | 8715.00 (review) | 8715.00 (review) | 8715.00 | yes |
| FRBTIFR-BTI-2024-01963 | Sunglasses with plastic lenses, UV protection | 9004.10 | 9004.10 (auto_accept) | 9004.10 (auto_accept) | 9004.10 (auto_accept) | 9004.10 | yes |
| DEBTI19155/25-1 | Quartz wrist watches, analogue dial, stainless steel or all… | 9102.11 | 9102.99 (review) | 9102.99 (review) | 9102.99 (review) | 9102.99 | no |

Model: google/gemini-2.5-flash. Line-by-line results of the latest run: `tests/eval/hs6_eval_outside.json`; each run also keeps its own, `tests/eval/hs6_eval_outside_<tag>_….json`.
