# Run 013 — knowledge base refresh

Status: COMPLETE - feature PR #4 merged into main (merge commit ca12d65). Review round 2 PASS; offline suite 1497 passed, 4 live deselected; CI offline-suite green. Agentic QA skipped by the owner (no secrets added); QA onboarding is separate task task_aea26e57b1dc for before feature 015.
Run: run_f581322468ed
Feature worktree: <worktree>/013-knowledge-base-refresh
Branch: 013-knowledge-base-refresh
Default branch: main
PR target: main
Spec PR: https://github.com/yorkzhangyong-bot/CargoLint/pull/3 (MERGED, merge commit 0476527; commits fd4ad29 and 26035ec, specs only)
Feature PR: https://github.com/yorkzhangyong-bot/CargoLint/pull/4 (MERGED, merge commit ca12d65; implementation commits a12114c..db2c672)

Clarifications settled in spec.md: TARIC warning 40 days against snapshot date (7-day rule dropped); only new/changed EBTI rulings embedded; app resolves newest release with optional pin; EBTI store size is the CARGOLINT_EBTI_RULINGS setting, 5000 by default for the demo and `all` for a production store (--rulings overrides).

Review: three read-only rounds; all HIGH/MEDIUM findings resolved. Accepted as implementation notes: empty embedding_usage under --full-embed, plus the round-3 nits.

Next: none for feature 013. Author's live steps remain in quickstart.md (first real TARIC/EBTI runs, --as-of eval comparison, demo secrets switch, release check).
