# Feature 006: stable, evidence-gated classification in CargoLint

*Report for the Turing College capstone review, covering work done on 25 and 26 October 2026. Every number cites its
source. File names without a path are in `tests/eval/`. "Constitution" means the amendment log in
`.specify/memory/constitution.md`.*

## 1. Summary

CargoLint helps a customs clerk classify packing-list lines. It suggests a six-digit HS code (HS-6), then an eight-digit
CN code (CN-8), and routes each line to auto-accept, clerk review or a question to the shipper. Feature 006 began as
measurement only, asking two questions: are the results stable from run to run, and can the system tell when it is
right? It ended by changing how the system decides to auto-accept a code.

Results on a fixed set of 120 EBTI rulings, with majority-of-three answers:

- **End to end:** lines with the right final CN-8 rose from 56 to 74 of 120 (constitution, 1.5.0; baseline in
  `hs6_eval.md`, iteration 1).
- **Wrong HS-6 auto-accepts:** down from 43, 48 and 46 per run to 5, 4 and 4 (`hs6_eval.md`, iterations 1 and 4).
- **The auto-accept rule:** it no longer trusts the model's own confidence. Code checks whether the five nearest EBTI
  rulings agree with the model, at both code levels (constitution, 1.4.0 and 1.5.0).
- **The default chat model:** moved from gpt-4o-mini to Gemini 2.5 Flash after a five-model comparison
  (`hs6_eval.md`; commit ce3bf02).

## 2. The pipeline in RAG terms

CargoLint is a retrieval-augmented generation (RAG) system with one addition: a gate between the answer and its
acceptance.

- **Retriever.** A vector search finds the EBTI rulings (binding classification decisions by EU customs
  authorities) whose goods descriptions are nearest to the line. At the HS-6 step a keyword-and-vector search over the
  nomenclature adds candidates.
- **Generator.** A chat model receives the line, the candidates and the nearest rulings. It returns a code, a
  confidence and a rationale as structured JSON.
- **Gate.** Code, not the model, decides the route: auto-accept, review or ask the shipper.

Three standard measures frame the findings:

- **Recall** asks whether the correct code is among what was retrieved. At the CN-8 step, a ruling at the expected
  CN-8 was among the rulings sent in every wrong result from iteration 7 to 12, for example 72 of 72 in iteration 11
  (`cn8_eval.md`). At the HS-6 step, the correct code was among the candidates shown in 124 of 151 wrong results
  (`hs6_eval.md`, iteration 1). Retrieval was rarely the problem.
- **Precision** asks whether the nearest eligible ruling is right; eligible means valid on the day and not the line's
  own ruling. It was right at the CN-8 for 106 of 120 lines in every run of iteration 11 (computed from
  `cn8_eval_iteration11.json`). It was right at the HS-6 for 82 of 120 in every baseline run (computed from
  `hs6_eval.json` at commit 46bed5c).
- **Faithfulness** asks whether the answer rests on the input. At the CN-8 step the model quotes the words that decide
  the code, and code checks the quote is really in the line: the evidence check. In iteration 9 it accepted 334 of 360
  quotes (commit 1d65d2e).

## 3. Method

- **Eval set.** 120 valid EBTI rulings, ten from each of twelve chapters, fixed before any tuning (`cn8_eval.md`). Each
  ruling's goods description becomes a line, and its own code is the answer. The HS-6 answer is the first six digits of
  the CN-8, so no new labels were needed (`hs6_eval.md`). The CN-8 eval starts from the correct HS-6; the HS-6 eval
  starts from the raw description.
- **Repeated runs.** From iteration 5 every line is classified three times, independently (`cn8_eval.md`). Reports
  give each run, a majority answer (the most frequent code; a tie goes to the earliest run) and the lines with the same
  answer in all runs.
- **Logged settings.** Each history entry records model, temperature, seed, tag and threshold, and since the model
  comparison the reasoning setting (`cn8_eval_history.json`, `hs6_eval_history.json`).
- **Cost.** A three-run CN-8 eval with gpt-4o-mini cost $0.08 to $0.11 on OpenRouter (commits a19b765, 48af6da, 52381ca,
  1d65d2e, 77131bd, f846a56). Three-run HS-6 evals cost $0.12 to $0.48, depending on the model (commit ce3bf02).
- **Offline tests versus live evals.** The automated suite runs without API keys (constitution, Principle VII) and
  stood at 1,102 tests at the end (commit ce3bf02). Live evals cost money.
- **Caveat.** Every figure holds on this eval set: long, formal ruling texts, not short real packing-list lines.

## 4. Timeline of findings

**4.1 The results moved with no code change.** Iterations 3 to 6 ran the same CN-8 step four times. Top-1 was 91, then
93, then 92/92/94, then 91/92/90 with a fixed seed (`cn8_eval.md`). The model already ran at temperature 0 (commit
a19b765), and the seed did not make it deterministic. In the first three-run baseline, 10 lines changed answer, and 7 of
them flipped between a code and a question to the shipper (commit a19b765).

**4.2 The root cause was the code's own check.** Logging the raw answers (iteration 8) showed that the evidence check,
not the model, produced all 36 asks to the shipper. In 24 the quote came from a code label or a ruling in the prompt,
and in 28 of the 36 the model's code was right (commits 52381ca, 1d65d2e). Confidence was 85 in 320 answers, 95 in 39
and 75 in one (commit 52381ca). At 85 or more in 359 of 360, it carried no information
(`specs/006-stability-baseline/plan-ruling-vote.md`). The fix gave the goods text its own block, allowed quotes only
from it, and made the check tolerate accents, line breaks and near matches. Majority accuracy rose from 91 to 94, and
asks fell from 12/13/11 to 7/10/9 per run (commit 1d65d2e).

**4.3 Deterministic retrieval, and a bug the eval caught.** The rulings sent, or their order, differed between runs for
27 of 120 lines (`plan-ruling-vote.md`). Ranking by rounded distance and caching each line's query embedding made all
three runs send identical rulings on all 120 lines (commit 77131bd). The first version sorted backwards, sending the
farthest ruling first. The offline tests passed (commit bd7f97d), but the live eval caught it: majority accuracy fell
from 94 to 89, and wrong auto-accepts rose from 37 to 60. The run was discarded, and the fix came with a regression test
(`cn8_eval.md`; commit a4ec6c7).

**4.4 Letting the rulings vote: the CN-8 gate.** An offline replay compared gates built from the nearest rulings. None
met the target of at most three wrong auto-accepts per run with at most 10% of right ones lost
(`cn8_vote_analysis.md`). The chosen variant, an unweighted vote of the five nearest eligible rulings with a share of at
least 0.5, cut wrong auto-accept rows from 38 to 15 over three runs and lost 9.3% of the right ones. Built into the
product (constitution 1.4.0), iteration 11 had 5/5/5 wrong auto-accepts per run instead of 13/13/12. Majority accuracy
stayed at 97, and 28 right auto-accepts (9.7%) moved to review (commit f846a56).

**4.5 The HS-6 baseline, and a leak in the test.** Measured alone for the first time, the HS-6 step scored 69 of 120 on
majority, with 43/48/46 wrong auto-accepts per run. Of the 64 lines that ended wrong, 51 went wrong at this step
(`hs6_eval.md`, iteration 1). First, a leak had to be closed. Each eval line is a real ruling's text, and that ruling
was the line's nearest neighbour in 110 of 120 lines (`hs6_eval.md`), so the model would have seen its own answer. An
exclusion list now keeps the line's own ruling out of the precedents and the vote, and a test shows the leak without it
(commit 46bed5c).

**4.6 The HS-6 vote gate and its similarity floor.** The same five-ruling vote now gates the HS-6. With gpt-4o-mini,
wrong auto-accepts fell to 3/2/2 per run, and 10/11/12 right ones per run went to review (`hs6_eval.md`, iteration 2).
Because a search always returns five rulings, one below a cosine similarity of 0.40 does not vote. The floor sits below
every eval line's nearest ruling (lowest 0.436), so no gated line lacked a voting ruling (commit ce3bf02).

**4.7 Five models on the same harness.** Each model ran the same HS-6 path with the vote gate, with thinking switched
off for every model that offers it (`hs6_eval_history.json`). None of the four newer models returned an invalid
answer; the gpt-4o-mini runs predate that count (`hs6_eval.md`).

| Model | Runs | Top-1 per run | Majority | Wrong auto-accepts per run | Same top-1, all runs | Cost | Ranking score |
|---|---|---|---|---|---|---|---|
| gpt-4o-mini | 3 | 68 / 69 / 70 | 69 | 3 / 2 / 2 | 112 | $0.18 | 0.53 |
| DeepSeek V4 Flash | 3 | 82 / 76 / 78 | 78 | 4 / 6 / 6 | 108 | $0.12 | 0.67 |
| Gemini 2.5 Flash | 3 | 82 / 84 / 82 | 82 | 5 / 4 / 4 | 113 | $0.44 | 0.67 |
| gpt-4.1-mini | 3 | 76 / 75 / 76 | 76 | 4 / 5 / 4 | 111 | $0.48 | 0.62 |
| Claude Haiku 4.5 | 1 | 83 | 83 | 5 | – | $0.63 | 0.68 |

*Sources: `hs6_eval.md`, iterations 2 to 6; commit ce3bf02 (OpenRouter cost); ranking scores computed from the
confidence tables in `hs6_eval.md`, for gpt-4o-mini from `hs6_eval.json` at commit 46bed5c (vague lines capped at 59).*

Every newer model beat gpt-4o-mini. Gemini 2.5 Flash was the most accurate and stable over three runs; Haiku's single
run sits within its range at about four times the cost per run.

**4.8 Confidence calibration.** The ranking score is the chance that a right answer carries a higher confidence than a
wrong one; 0.5 means no information. gpt-4o-mini scores 0.53: it gave its top HS-6 a confidence of 95 on about 100 of
120 lines, right or wrong (constitution, 1.5.0). The other models score 0.62 to 0.68: some signal, not enough to rely
on. Gemini's 98 was right 77 of 79 times, yet most of its answers sat at 95, with 168 right and 100 wrong
(`hs6_eval.md`, iteration 4).

**4.9 An invalid-JSON bug.** Trying other models exposed a quiet failure: a ranking answer that was not valid JSON was
read as "no candidates", with no retry and no error. It is now retried once, then the line fails visibly (commit
ce3bf02).

**4.10 Gemini 2.5 Flash as the default, and CN-8 iteration 12.** Gemini 2.5 Flash became the default with thinking off
(commit ce3bf02). At the CN-8 step it reached 103 of 120 on majority, against 97 for gpt-4o-mini (`cn8_eval.md`), with
3/2/2 evidence-check failures instead of 7/9/7, for $0.26 (commit ce3bf02). With Gemini at both steps, 74 of 120 lines
end right, against 56 at the baseline (constitution, 1.5.0).

| CN-8 iteration | Change | Top-1 per run | Majority | Wrong auto-accepts per run |
|---|---|---|---|---|
| 8 | evidence diagnosis (gpt-4o-mini) | 92 / 89 / 91 | 91 | 14 / 13 / 13 |
| 9 | evidence-source fix | 96 / 93 / 93 | 94 | 12 / 12 / 13 |
| 10 | deterministic retrieval | 95 / 97 / 97 | 97 | 13 / 13 / 12 |
| 11 | five-ruling vote gate | 97 / 95 / 96 | 97 | 5 / 5 / 5 |
| 12 | Gemini 2.5 Flash | 102 / 103 / 103 | 103 | 3 / 3 / 3 |

*Sources: `cn8_eval.md` (accuracy); commits 1d65d2e, 77131bd, f846a56 and ce3bf02 (wrong auto-accepts).*

## 5. Trade-offs

- **Right answers lost to review.** The CN-8 gate moved 28 right auto-accepts (9.7%) to review (commit f846a56). The
  HS-6 gate moves 10 to 16 right ones per run, depending on the model (`hs6_eval.md`). They cost the clerk time, not
  correctness.
- **The gate's blind spot.** A vote cannot catch an error when the nearest rulings are wrong together. Three lines were
  auto-accepted wrongly by all five models: IEBTIIENEN004-2024-BTI356, MTBTI2024-002 and MTBTI2025-011
  (`hs6_eval_history.json`).
- **Eval-set skew.** 77 of the 120 rulings were issued by Ireland. The descriptions are 103 in English and 17 in
  German, with no Chinese line (`cn8_eval_set.json`). Mixed Chinese and English input is not measured.
- **Doubtful labels.** XIBTI505068468 describes a whole gas space heater but carries 3926.90, a code for articles of
  plastics. Two slipper rulings, IEBTIIENEN004-2024-BTI352 and BTI356, open with the same description yet carry 6404.19
  and 6405.20 (`hs6_eval.md`), so every system gets at least one of them wrong.
- **Real lines sit lower.** Short real packing-list lines scored only 0.51 to 0.73 against their nearest ruling
  (commit ce3bf02), so a floor in that range would leave many without a vote. Re-routing the gpt-4o-mini baseline's
  answers with floors of 0.40, 0.60 and 0.70 hands 0, 4 and 27 lines per run back to the model's confidence. Wrong
  auto-accepts per run are 3/3/2, 6/6/5 and 22/23/23 (computed from `hs6_eval.json` at commit 46bed5c). How the gate
  behaves on real input is not yet measured.

## 6. Open items

- **A true end-to-end eval.** The 74 of 120 combines two separate evals, and the CN-8 eval starts from the correct HS-6
  (`cn8_eval.md`). One run through the system's own HS-6 choice is still to be built.
- **The precedent override.** When the rulings back the model's second or third candidate, the clerk sees "Precedents
  support candidate N", but the system does not switch to it (commit ce3bf02). Whether it should needs measuring.
- **The confidence fallback.** Whether confidence should still decide when no ruling votes is open (constitution,
  1.5.0).
- **A CI quality gate.** A scheduled eval with an accuracy threshold would catch regressions the offline tests miss
  (section 4.3).
- **Eval-set fixes.** Review the doubtful labels, add Chinese and short real lines, and balance the issuing countries.
- **EU hosting.** Production use with customs data would need EU-hosted model endpoints; today the chat model is
  reached through OpenRouter (constitution).

## 7. Lessons for LLM quality engineering

1. Measure the run-to-run spread before trusting a change. At temperature 0 with a fixed seed, the same code still
   moved by several points (`cn8_eval.md`).
2. Log raw model output before your own checks. Here the "model problem" was the code's evidence check (commit
   52381ca).
3. Measure self-reported confidence before routing on it. gpt-4o-mini gave a CN-8 confidence of 85 or more in 359 of
   360 answers (`plan-ruling-vote.md`).
4. Gate on external evidence. Agreement with retrieved precedents cut wrong auto-accepts more than any prompt change
   (`cn8_eval.md`, `hs6_eval.md`).
5. Look for leakage when eval items come from the retrieval corpus. Here each line's own ruling was its nearest
   neighbour in 110 of 120 lines (`hs6_eval.md`).
6. Treat the eval as a regression test for infrastructure too. It caught an inverted sort that the offline tests had
   passed (commits bd7f97d, a4ec6c7).
7. Compare models on one harness with one gate, and report cost and stability as well as accuracy (`hs6_eval.md`).
8. State the scope of every number: these hold on 120 ruling texts, not real packing lists.
