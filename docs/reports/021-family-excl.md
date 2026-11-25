# Re-baseline: family exclusion (backlog items 20 and 21)

Run: iteration 23, tag `021-family-excl`. The 120-line set (`cn8_eval_set.json`), 3 independent runs,
`--family-exclusion` on, model `google/gemini-2.5-flash`, temperature 0.0, seed none, query expansion off,
customs wording off. Compared against the 017-after baseline (iteration 22), the same configuration with
family exclusion off.

The precedent override (feature 008) is computed within each run, so every per-line figure is reported twice:
override **off** / override **on**. "Before" and "after" below mean family exclusion off (017-after) and on
(this run).

## The new honest baseline, not a regression

The 017-after numbers were inflated by sibling leakage: for near-duplicate families, a line's sibling ruling
sat among its nearest precedents and supplied the answer, so several lines looked right only because a
near-duplicate pointed at the code. Hiding a family's own rulings from retrieval removes that borrowed signal,
and the lower figures are the honest baseline, not a regression:

| Metric | 017-after (exclusion off) | This run (exclusion on) |
|---|---|---|
| Per-line majority right, override off / on | 78 / 80 | **75 / 78** |
| Family metric (97 units), override off / on | 61.2167 / 62.7167 | **59.7167 / 61.7167** |
| Wrong auto-accepts (by majority), override off / on | 3 / 3 | **2 / 2** |

The one clear win is a wrong auto-accept that disappears: `IEBTIIENEN004-2024-BTI356` (irish-shoes, coded
6405.20 while its four near-duplicate siblings are 6404.19) was being pushed to the sibling's wrong code
6404.19 and auto-accepted; with its siblings hidden it is no longer wrongly auto-accepted. The remaining two
wrong auto-accepts (`MTBTI2024-002`, `MTBTI2025-011`) are unchanged.

## Summary

| Metric | 017-after (exclusion off) | This run (exclusion on) |
|---|---|---|
| Per-line majority right, override off / on | 78 / 80 | 75 / 78 |
| Family metric (97 units), override off / on | 61.2167 / 62.7167 | 59.7167 / 61.7167 |
| Chapter accuracy (majority), override off / on | 98 / 99 | 95 / 97 |
| Heading accuracy (majority), override off / on | 86 / 88 | 83 / 86 |
| Wrong by level (override off): chapter / heading / subheading | 22 / 12 / 8 | 25 / 12 / 8 |
| Wrong auto-accepts (by majority), override off / on | 3 / 3 | 2 / 2 |
| Cost (USD) | $0.5328 | $0.5306 |

Per-run, override off: top-1 78/77/78 before, 75/74/75 after; chapter 98/96/98 before, 94/93/95 after;
heading 86/85/86 before, 83/82/83 after; wrong auto-accepts 3/3/2 before, 1/2/2 after.

## Family metric, per family (override off)

Each family counts once, scored as the fraction of its lines right by majority; 85 standalone lines plus
12 families = 97 units.

| Family | Before (exclusion off) | After (exclusion on) |
|---|---|---|
| swedish-armrest-covers | 1.0000 | 1.0000 |
| irish-shoes | 0.8000 | 0.8000 |
| bikini-tops | 0.2500 | 0.2500 |
| baskets | 0.0000 | 0.0000 |
| period-pants | 0.5000 | 0.0000 |
| pet-beds | 1.0000 | 1.0000 |
| monitors-27 | 1.0000 | 1.0000 |
| sports-bras | 1.0000 | 1.0000 |
| masks | 1.0000 | 0.0000 |
| sandals | 1.0000 | 1.0000 |
| backpacks | 0.6667 | 0.6667 |
| single-use-assemblies | 1.0000 | 1.0000 |
| Standalone lines | 52 | 52 |

The family metric moves 61.2167 → 59.7167 (override off), entirely from two families whose sibling precedents
had been supplying the correct code: **masks** (1.0 → 0.0, both members now wrong) and **period-pants**
(0.5 → 0.0). No family gains.

## Retrieval misses by family (backlog item 21's list)

A retrieval miss is a line whose majority top-1 is wrong and whose correct HS-6 was never among the candidates
shown to the model in any of the three runs (`expected_sent` false in all three). After 017 there were 13,
all standalone lines; family exclusion leaves those 13 untouched and adds four within families, for **17**
total:

| Family | Line | Correct HS-6 |
|---|---|---|
| baskets | IEBTIIENEN004-2024-BTI5 | 6307.90 |
| baskets | IEBTIIENEN004-2024-BTI7 | 6307.90 |
| masks | IEBTIIENEN004-2025-BTI245 | 3926.90 |
| masks | IEBTIIENEN004-2025-BTI258 | 3926.90 |
| (standalone) | IEBTIIENEN004-2023-BTI561 | 8537.10 |
| (standalone) | IEBTIIENEN004-2024-BTI132 | 6102.30 |
| (standalone) | IEBTIIENEN004-2024-BTI133 | 3926.90 |
| (standalone) | IEBTIIENEN004-2024-BTI141 | 3926.90 |
| (standalone) | IEBTIIENEN004-2024-BTI208 | 6109.90 |
| (standalone) | IEBTIIENEN004-2024-BTI90 | 6101.30 |
| (standalone) | IEBTIIENEN004-2025-BTI293 | 8424.90 |
| (standalone) | IEBTIIENEN004-2026-BTI105 | 8474.90 |
| (standalone) | IEBTIIENEN004-2026-BTI124 | 8431.49 |
| (standalone) | IEBTIIENEN004-2026-BTI228 | 6307.90 |
| (standalone) | MTBTI2024-002 | 8424.89 |
| (standalone) | XIBTI505068468 | 3926.90 |
| (standalone) | XIBTI505068566 | 8504.40 |

The 13 standalone misses are byte-for-byte the same lines as after 017; family exclusion neither fixes nor
adds any standalone miss.

### Retrieval vs judgement in the four affected families

For each wrong line, "retrieval" means the right code was absent from the candidates (a retrieval miss, above);
"judgement" means the right code was present among the candidates but not chosen.

- **masks** (2 members, both wrong): retrieval — `BTI245`, `BTI258`. The correct 3926.90 was only ever shown
  by the sibling, so hiding it removes the answer.
- **period-pants** (2 members, both wrong): judgement — `BTI72` (9619.00 → 6108.22), `BTI71` (9619.00 →
  6108.21). The right code was present; the model chose the wrong chapter 61.
- **baskets** (3 members, all wrong): retrieval — `BTI5`, `BTI7` (6307.90 absent, model chooses 4602.90);
  judgement — `BTI8` (6307.90 present, still 4602.90).
- **bikini-tops** (4 members): judgement — `BTI106`, `BTI108`, `BTI107` (all 6212.10 → 6112.41, right code
  present); `BTI89` right.

Overall, of the 45 wrong lines, 17 are retrieval and 28 are judgement.

## Per-level accuracy and wrong-by-level

Chapter accuracy moves 98 → 95 (override off) and heading 86 → 83. The 42 wrong lines of the baseline become
45; the extra misses are chapter-level (22 → 25), while heading (12) and subheading (8) misses are unchanged.
The worst-chapter pattern noted in backlog item 20 (chapters 39 and 63) is unchanged.

## Cost

$0.5306 (€0.4882), 455 s, 1,166,365 tokens over 1,077 calls. Within the approved hard cap of $1.06.

## Reading

Family exclusion removes the sibling signal that had been inflating the 017-after result, so 75/78 per line
and 59.7167/61.7167 family units replace 78/80 and 61.2167/62.7167 as the honest baseline. The sibling leakage
item 21 targeted is real but small: it costs one wrong auto-accept (BTI356, fixed) and a few lines that were
right only because a sibling told them so (masks), while the larger error surface — the 13 standalone retrieval
misses and the judgement errors in period-pants, baskets and bikini-tops — is untouched by family exclusion.
That remaining error surface is the input to items 22 (note-text) and 23 (override revisit).
