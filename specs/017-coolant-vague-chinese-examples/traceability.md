# Traceability: feature 017

The requirements of [spec.md](spec.md), or the parts of them, that no offline test can check: evaluation results, the
author's approval and documentation (docs/qa-platform.md, "Traceability"). The tests reference what they cover as
`017/FR-###` or `017/SC-###`: tests/unit/test_judgement_examples.py (FR-001, FR-002, FR-003, FR-004, FR-005, SC-005),
tests/integration/test_check_description.py (FR-004, the two path tests) and tests/unit/test_hs6_eval.py (FR-006, the
nine-line coolant set). An evaluation result names its results file and its section of
[eval-report.md](eval-report.md), written after the after-runs (tasks T020).

- 017/FR-006: the after-runs are a live step (T016): the three sets three times each with the configured model and the
  evaluation's settings, after the author's approval. Their rows, with each line's flag and route per run, are the
  results files tests/eval/hs6_eval_017-after_en_expansion-off_wording-off.json,
  tests/eval/hs6_eval_coolant_017-after_en_expansion-off_wording-off.json and
  tests/eval/hs6_eval_outside_017-after_en_expansion-off_wording-off.json, read in eval-report.md sections 1 to 3.
  What is offline is tested: coolant-9 loads and runs as the ninth line (tests/unit/test_hs6_eval.py, 017/FR-006).
- 017/FR-007: the estimate, the approval and the spend are the author's decision and OpenRouter's record: the
  approval with its date and amount, and the spend by the key's usage against the $0.65, are in eval-report.md
  section 5 and in the pull request's description. The staged order, the stop on any miss and a revision round only
  with the author's go-ahead are the author's process (the staged approval of 2026-11-23); eval-report.md section 4
  records the stage reached and which branch applied.
- 017/FR-008: documentation: eval-report.md (the tables of every set, the flags per run against the baseline runs,
  the verdicts), the pull request's description, docs/backlog.md item 17 and README.md.
- 017/SC-001: evaluation result: the coolant run's rows for coolant-3 and coolant-9 in every run, eval-report.md
  section 2.
- 017/SC-002: evaluation result: the coolant run's rows for coolant-1, coolant-2 and coolant-8 in every run,
  eval-report.md section 2.
- 017/SC-003: evaluation result: the 120-line run's summary (majority top-1) and its rows (the wrong auto-accepts by
  majority per line, the override off and on) against iteration 21's, eval-report.md section 1.
- 017/SC-004: evaluation result: the coolant summary's per-line entries of coolant-1 to coolant-8 and the outside
  set's per-line entries, with the wrong auto-accepts per run and by majority per line, eval-report.md sections 2
  and 3.
- 017/SC-006: the spend against the approval, from OpenRouter's record of the key's usage: eval-report.md section 5.
- 017/SC-007: evaluation result: the coolant run's rows for coolant-4 to coolant-7 in every run, eval-report.md
  section 2.
