# Traceability: feature 014a

The requirements of [spec.md](spec.md), or the parts of them, that no offline test can check: evaluation results,
live steps, documents and the constitution (docs/qa-platform.md, "Traceability"). The tests reference what they cover
as `014a/FR-###` or `014a/SC-###`. An evaluation result names its evaluation file and its report section.

- 014a/FR-003: the order of the work is tasks.md's phases 2 to 9; the history entries show it (the 014a-baseline
  entries of tests/eval/hs6_eval_history.json and tests/eval/hs6_eval_coolant_history.json come before the
  014a-after entries), and the live steps ran with the author's go-ahead.
- 014a/FR-004: the evaluation report, specs/014a-retrieval-evidence/eval-diff.md sections 1 to 4, with its numbers
  from the history entries; its tables are rendered by tests/eval/eval_diff_014a.py (tested in
  tests/unit/test_eval_diff_014a.py).
- 014a/FR-009: the rebuild of the local store is a live step (T043): the refresh counts in store/index_meta.json,
  reported in eval-diff.md; the reuse of the previous store's vectors is tested in
  tests/integration/test_refresh_ebti.py.
- 014a/FR-010: Admin › Data's statement is tested (tests/unit/test_view.py); the README's chapters are documentation
  (README.md).
- 014a/FR-026: the switch's default is tested (tests/unit/test_settings.py); the off/on comparison and the criterion
  for the author's later decision are evaluation results, eval-diff.md sections 1, 2 and 4.
- 014a/FR-028: documentation: docs/backlog.md, entry 1 marked done.
- 014a/FR-029: documentation: README.md and .env.example.
- 014a/FR-030: a working rule: tasks.md's test tasks came before their implementation tasks; the offline suite runs
  without a key or a network (`pytest -q`, the offline-suite job of .github/workflows/tests.yml).
- 014a/FR-031: the constitution, .specify/memory/constitution.md, version 1.11.0 with its amendment-log entry.
- 014a/FR-032: the outside set is evaluation data that the author approves, with its near-duplicate check, before
  any paid run (T062); its loading and its leave-one-out get offline tests in tests/unit/test_hs6_eval.py (T061).
- 014a/FR-033: option (c) is evaluation-only; its result is docs/reports/014a-regression-analysis.md section 5
  (T066), and the option gets offline tests in tests/unit/test_hs6_eval.py (T063).
- 014a/SC-001: the rebuild's counts, the refresh block of store/index_meta.json, reported in eval-diff.md.
- 014a/SC-002: checked on the coolant set's after-run rows: eval-diff.md section 4.
- 014a/SC-003: eval-diff.md sections 1 and 2, from the history entries.
- 014a/SC-004: judged under rule (a) on the exact replay of the after-runs' rows, docs/reports/014a-regression-analysis.md
  section 5 (T066), rendered by tests/eval/regression_014a.py; judged first on the chapter-filtered vote in
  eval-diff.md section 4 (failed).
- 014a/SC-006: the switch's default is tested (tests/unit/test_settings.py); the comparison is in eval-diff.md
  sections 1, 2 and 4.
- 014a/SC-007: documentation: docs/backlog.md, entry 1.
- 014a/SC-008: the constitution, .specify/memory/constitution.md.
