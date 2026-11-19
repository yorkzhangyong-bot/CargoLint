# Traceability: feature 014a

The requirements of [spec.md](spec.md), or the parts of them, that no offline test can check: evaluation results,
live steps, documents and the constitution (docs/qa-platform.md, "Traceability"). The tests reference what they cover
as `014a/FR-###` or `014a/SC-###`. An evaluation result names its evaluation file and its report section.

- 014a/FR-003: the order of the work is tasks.md's phases 2 to 9; the history entries show it (the 014a-baseline
  entries of tests/eval/hs6_eval_history.json and tests/eval/hs6_eval_coolant_history.json come before the
  014a-after entries). The author's approval of each paid step (T006, T043, T044, the ablation of
  docs/reports/014a-regression-analysis.md section 2, and T065), with their amounts, is listed by the coordinator in
  the feature pull request's description.
- 014a/FR-004: the evaluation report, specs/014a-retrieval-evidence/eval-diff.md sections 1 to 4, with its numbers
  from the history entries; its tables are rendered by tests/eval/eval_diff_014a.py (tested in
  tests/unit/test_eval_diff_014a.py).
- 014a/FR-009: the rebuild of the local store is a live step (T043); its counts (the unchanged rulings of the
  twelve chapters reused, the new ones embedded, none dropped) are in eval-diff.md section 4 (SC-001); the reuse of
  the previous store's vectors is tested in tests/integration/test_refresh_ebti.py.
- 014a/FR-010: Admin › Data's statement is tested (tests/unit/test_view.py); the README's chapters are documentation
  (README.md).
- 014a/FR-026: the switch's default is tested (tests/unit/test_settings.py); the off/on comparison and the criterion
  for the author's later decision are evaluation results, eval-diff.md sections 1, 2 and 4.
- 014a/FR-028: documentation: docs/backlog.md, entry 1 marked done.
- 014a/FR-029: documentation: README.md and .env.example.
- 014a/FR-030: what the history can show. The tests were committed together with the code they cover (bd6ac5a,
  2605e0f, e130021 and the evaluation commits), so the history cannot show their order. Seen failing on the code
  before the change, where that was done: the block 3 caption tests of tests/unit/test_view.py
  (test_feature_014a_block3_captions_under_rule_a, test_feature_014a_the_veto_caption_names_one_chapter_in_the_singular,
  test_feature_014a_a_vote_stored_before_the_scope_keeps_its_agreement_caption) and of tests/ui/test_main_page.py
  (test_an_hs6_to_choose, test_feature_014a_block3_shows_the_deciding_vote_and_the_chapters_veto), before 2605e0f; the
  vague rule's tests of tests/unit/test_routing.py (test_vague_always_goes_to_ask_shipper,
  test_vague_never_auto_accepts_whatever_the_threshold_and_the_vote), before e130021; the outside set's, option (c)'s,
  the vetoed gate reason's and the replay exactness's tests of tests/unit/test_hs6_eval.py, before their code; and the
  boundary tests of review round 1 (0a75257), each checked to fail on a mutated guardrail (`>` for `>=` at the veto's
  share check and at the vote's share, the floor's `<` as `<=` or moved up by 1e-3, ready_to_accept without the second
  vote, route_line skipping the veto on a line flagged before). No tests-first claim is made beyond these. The offline
  suite runs without a key or a network (`pytest -q`, the offline-suite job of .github/workflows/tests.yml).
- 014a/FR-031: the constitution, .specify/memory/constitution.md, version 1.11.0 with its amendment-log entry.
- 014a/FR-032: the outside set is evaluation data: its near-duplicate check (per line, the top similarity and its
  reference before and after the rewrite, the source ruling's rank, and the flags) and the author's approval of
  2026-11-19 are in docs/reports/014a-regression-analysis.md section 5.1, from the committed record
  tests/eval/hs6_eval_outside_neardup.json (T062); its loading and its leave-one-out are tested in
  tests/unit/test_hs6_eval.py (T061).
- 014a/FR-033: option (c) is evaluation-only; its result is docs/reports/014a-regression-analysis.md section 5
  (T066), and the option gets offline tests in tests/unit/test_hs6_eval.py (T063).
- 014a/SC-001: the rebuild's counts, eval-diff.md section 4 (SC-001: 123,531 rulings in 95 chapters, the 74,044
  unchanged rulings of the twelve chapters reused, the 49,487 new ones embedded, none dropped).
- 014a/SC-002: checked on the coolant set's after-run rows: eval-diff.md section 4.
- 014a/SC-003: eval-diff.md sections 1 and 2, from the history entries.
- 014a/SC-004: judged under rule (a) on the exact replay of the after-runs' rows, docs/reports/014a-regression-analysis.md
  section 5 (T066), rendered by tests/eval/regression_014a.py; judged first on the chapter-filtered vote in
  eval-diff.md section 4 (failed).
- 014a/SC-006: the switch's default is tested (tests/unit/test_settings.py); the comparison is in eval-diff.md
  sections 1, 2 and 4.
- 014a/SC-007: documentation: docs/backlog.md, entry 1.
- 014a/SC-008: the constitution, .specify/memory/constitution.md.
