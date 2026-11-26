# Note-text upper bound (item 22, part A) and the reasoning test plan (part B)

Run: iteration 24, tag `022-notes`. 5 lines (3 treatments, 2 controls), 3 independent runs,
`--family-exclusion` on, notes file `tests/eval/hs6_note_texts.json`, model `google/gemini-2.5-flash`,
temperature 0.0, seed none, query expansion off, customs wording off. Compared per line against iteration 23
(`021-family-excl`), the same configuration without notes.

Cost: **$0.0244** (45 calls, 53,580 tokens: 49,596 prompt / 3,984 completion), inside the approved $0.06 cap.

## What was tested

Two notes, quoted from EU sources: paper-yarn baskets (Commission Implementing Regulation (EU) 2019/927) and
pet toys (CN Explanatory Note to heading 9503, the exclusion of articles intended exclusively for animals).
Each note's deciding text is appended to the ranking request, for the listed treatment and control lines only,
and only to the `RankOut` call. The injection is covered by
`test_note_injection_applies_to_the_listed_lines_only`; the run artifact does not store prompts, so that unit
test is the evidence that the text reached the model.

The five unique lines are three treatments and two controls; `BTI23` is a control in both notes.

## Result, per line

| Line | Role | Before (iteration 23) | After (iteration 24) | Right |
|---|---|---|---|---|
| `IEBTIIENEN004-2024-BTI8` | treatment, baskets | 4602.90 | **6307.90** | wrong → right |
| `SEBTITV-2026-01096` | treatment, pet toys | 9503.00 | 9503.00 | wrong → wrong |
| `CZBTI47/152108/2024-580000-04/01` | treatment, pet toys | 9503.00 | 9503.00 | wrong → wrong |
| `IEBTIIENEN004-2026-BTI23` | control (both notes) | 6307.90 | 6307.90 | right → right |
| `IEBTIIENEN004-2025-BTI38` | control, pet toys | 9503.00 | 9503.00 | right → right |

Top-1 3/5 in all three runs, top-3 5/5, no wrong auto-accepts, no run-to-run variance (same five results
every run, confidence 95 on every line).

## Finding

- **Baskets flip.** The one basket treatment moved from 4602.90 to 6307.90. The note's deciding step is a
  chapter-note exclusion (Note 1 to Chapter 46: textile yarn is not plaiting material), which the model can
  apply directly once it is given.
- **Pet toys hold wrong.** Both treatments stayed at 9503.00, confidence 95, with the note stating that
  heading 9503 does not include articles intended exclusively for animals. The note is phrased as an exclusion
  against the candidate the model already prefers, and it did not move the choice.
- **Controls stable.** Both controls stayed right, so the injection did not cost anything on lines that were
  already correct.

Limits: n=5, one treatment per note, zero variance. This is an upper-bound probe on two specific notes, not an
estimate of what note text does across the set. The baskets claim rests on a single line: `BTI5` and `BTI7` are
the same family with the same error and were not in the note's treatment list.

Also worth noting: the two pet-toy lines are plush/stuffed toys, and 6307.90 against 9503.00 is contestable in
the rulings themselves. The note gives the EU's answer, but the model's answer is not absurd, which may be why
the note does not move it.

## Part B: the reasoning test (plan only, not run)

**Design (eval only, no production change).** `rag/retriever.py:precedent_codes` gains two optional parameters,
`excerpt_from: str = "description"` and `excerpt_chars: int = 200`, so every existing call keeps today's
behaviour. `tests/eval/hs6_eval.py` wraps `classify_tool.precedent_codes` the same way `--proposal-scope`
already does, and a new `--precedent-excerpt reasoning` flag sets the source to `rec["reasoning"]`. The
production path never passes the flag.

**Cap: 600 characters.** Reasoning is short: mean 250 characters (≈62 tokens), median 111, p90 670, p99 1680,
max 3435 across the 73,899 rulings in `data/bti_subset.jsonl`. Today's description excerpt averages 198
characters (≈50 tokens). At a 600-character cap the reasoning excerpt averages 199 characters (≈50 tokens),
so the prompt does not grow, and 88% of rulings are kept whole. The cap exists to bound the tail, not to save
tokens: uncapped reasoning would add only ≈13 tokens per precedent.

**Caveat to decide before running.** `reasoning` is the ruling's legal-basis string
(`CLASSIFICATION_JUSTIFICATION`), for example `AV 1 / AV 6 Anm 1 Kap 62 / Anm 9 Abs 1 Kap 62 / ...`, in the
ruling's own language. It is not prose reasoning. Replacing the goods description with it is a trade rather
than an obvious gain. If the budget allows, run a third arm, `description + reasoning`, capped at 600, so the
result says which of the two signals carries the effect.

**Lines.** The 28 judgement errors from iteration 23 (the 021 report's definition: the right code was among
the candidates and was not chosen) plus 15 correct controls from the same chapters: 43 lines, 3 runs.

**Estimate.** Iteration 23 cost $0.5306 for 120 lines × 3 runs, or $0.001474 per line-run. 43 × 3 = 129
line-runs gives **$0.19**. Prompt growth at the 600-character cap is ≈0 (≈+$0.002 worst case, ≈+$0.002 if left
uncapped). Under the 2× rule, approve up to **$0.40**.

Not run. No spend beyond part A.
