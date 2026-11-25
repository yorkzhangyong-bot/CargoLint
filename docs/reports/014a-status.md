# Run 014a — retrieval and evidence

Status: COMPLETE - feature PR #10 merged into main as ffcf0ca (2026-11-19T13:41:29Z) after the author's approve.
Spec PR #7 (d277093), QA onboarding PR #8 (c6b1ed6), feature PR #10 (ffcf0ca). Remaining steps are the author's
(see "After the merge" below). Implementation: T001-T052 ticked, 11 commits dc5ffa0..3a28948 (not
pushed).
Run: run_ece0ea0e1ebe
Feature worktree: <worktree>/014a-retrieval-evidence
Branch: 014a-retrieval-evidence (from main 939852f)
Default branch: main
PR target: main
Spec PR: https://github.com/yorkzhangyong-bot/CargoLint/pull/7 (MERGED as d277093 at 2026-11-18T17:56:27Z;
commits e2c5356 and 990ef06, specs only)
Feature PR: none yet
Stop point: after the spec PR is open (the author's instruction: stop for human review after the spec).

## Log

- 2026-11-18 Stage 1: Run created; feature worktree and branch created from main 939852f. The spec is written in the
  feature worktree, as in run 013, so the main checkout and its uncommitted changes stay untouched.
- 2026-11-18 Stage 2: spec worker dispatched (claude, fable) in the feature worktree; it stopped at once on the
  Fable usage limit, before writing anything. The author chose opus for the spec writer and sonnet for the spec
  reviewer. Retried on opus (task task_bf5488a5b721, dispatch ctx_8f69daa7ac56).
- 2026-11-18 Clarify Q1 (which ruling searches get the chapter filter): answered A by the coordinator from the
  backlog wording ("the nearest rulings ... the model's HS-6 candidates"): the 5-nearest vote and block 3 are
  limited to the chapters of the model's candidates; the candidate proposal keeps searching all indexed chapters;
  SC-004 (no more wrong auto-accepts than the baseline) measures the reduced cross-chapter check. Open to the
  author's review.
- 2026-11-18 Clarify Q2 ("relevant" ruling): answered A by the coordinator: relevant = eligible to vote within the
  candidates' chapters (valid on the day, loaded subheading, similarity >= 0.40, exactly 0.40 counts); "No relevant
  rulings found" exactly when no ruling votes, so block 3 never contradicts routing. The worker must check three
  possible constitution 1.10.0 conflicts in the plan and raise any amendment instead of making it: Principle I
  eligibility vs the chapter-limited vote, Principle IV raw-text-first and no-translation rule vs the customs-wording
  rewrite, and the twelve chapters named under "Knowledge-base sources".
- 2026-11-18 Clarify Q3 (precedent mismatch: drop or flag): answered A (flag) by the coordinator, one of the two
  options the requirement allows: reasoning stays verbatim; a code-written note in block 2 names a cited ruling's
  real HS-6, or says it was not retrieved and is not a source; stored per candidate on the line version; no
  routing effect; CSV unchanged. Plan must check Principle III and the block 2 contract wording.
- 2026-11-18 Clarify Q4 and Q5 (customs wording): the author answered in the worker's chat and to the coordinator
  (option 1): own switch, off by default and left off in this feature; any input language rewritten into German
  (the store's main language) and used for the EBTI ruling searches only (raw text + rewrite, hits merged); the
  nomenclature search, every model prompt, the description and the CSV keep the raw text; the rewrite is stored on
  the line version and shown as a caption in block 1 (author-requested UI addition); the PR reports off vs on; a
  later default change is the author's decision (criterion: HS-6 accuracy improves and plain 冷却液 still routes to
  ask shipper). Optional reviewed glossary file before the model. Vote floor 0.40 to start, tuned with the eval only
  with the author's approval. Eval set: the six coolant lines plus the author's German line (Kühlschmierstoff ...
  ohne Mineralöl -> 3403.99) and plain 冷却液 -> ask shipper (8 lines). Clarify closed at 5 clarifications.
- 2026-11-18 Plan Q-A (store and Python environment): answered B by the coordinator from "Rebuild the local store":
  the worktree gets its own .venv and a read-only copy of the main store for the baseline; the rebuild
  (refresh_ebti --no-publish --rulings all --previous) and the after-runs happen in the worktree; the last task
  replaces the main checkout's store/ only after the author's go-ahead at that step, keeping the old store as a backup,
  with the app stopped first. No release is published in this feature. (This reply did not reach the worker:
  its question had closed. The author answered A in the worker's chat instead, see below.)
- 2026-11-18 Plan Q-A and Q-B: the author answered both in the worker's chat. A: the worktree gets its own .venv
  and a one-time copy of the main store (3,350,384,841 bytes); the main checkout is never written. B: Principle IV
  is not amended (the rewrite stays off); "Knowledge-base sources" is amended in this feature via
  /speckit-constitution (FR-031, T050; the version level, MINOR 1.11.0 or PATCH, is for the author to confirm).
  Also: the rewrite is a separate call from query expansion; the CN-8 ruling search stays unchanged (R-16); every
  014a eval run uses --expansion off.
- 2026-11-18 Stage 2 done (worker_done msg_68013bd6d717): specs/014a-retrieval-evidence/ with spec.md (FR-001 to
  FR-031, SC-001 to SC-008), plan.md, research.md (R-01 to R-16), data-model.md, quickstart.md, four contracts,
  checklists/requirements.md and tasks.md (52 tasks); all LF, uncommitted. Open points for the author: the
  amendment level; the plain 冷却液 eval line and the block 1 rewrite caption.
- 2026-11-18 Stage 3: spec review round 1 dispatched (claude, sonnet, read-only; task task_96164e6cfa43,
  dispatch ctx_8cf796ba10ba).
- 2026-11-18 The author settled the open points: (1) the constitution amendment is MINOR, 1.11.0; (2) the plain
  冷却液 eval line stays (expected: ask shipper); (3) the block 1 caption showing the rewritten text is wanted,
  display only, with no change to routing or the CSV. To be written into the spec files with the review fixes.
- 2026-11-18 Spec review round 1: FAIL (0 HIGH, 1 MEDIUM, 5 LOW). Coverage complete (31 FR and 8 SC to tasks,
  52 tasks to FRs), eval order right, no constitution conflict beyond the ordered amendment. MEDIUM: SC-004 did not
  say which after-runs (rewrite switch off or on) it compares. LOW: replay caveat in data-model S9, glossary entry
  without a main-language rendering (FR-027), SC-005 task range, SC-007 "PR #4", "ALL" case in T007. All six and
  the author's three confirmations sent to the spec worker (follow-up task task_5cb55c9ca277, dispatch
  ctx_53dfbc767c08).
- 2026-11-18 Round 1 fixes done: all six findings fixed (the any-case "all" rule also made explicit in FR-006,
  data-model, R-03 and the settings contract); confirmations recorded as three spec.md Clarifications (MINOR 1.11.0
  throughout, PATCH kept only as the rejected alternative; plain 冷却液 line in FR-001; caption display only in
  FR-025 and contracts/ui.md). Still T001-T052, coverage complete, LF, only the spec folder changed.
- 2026-11-18 Spec review round 2 dispatched to the same reviewer (task task_88ffffd4d734, dispatch
  ctx_d2cbd35c9edd).
- 2026-11-18 Spec review round 2: FAIL (0 HIGH, 2 new MEDIUM from the round-1 edits; all six round-1 findings fixed,
  the three confirmations clean, coverage unchanged and complete). A: data-model §9's vote_hits row and T041 still
  say a replay can apply "any floor", against the new caveat. B: FR-030 and T032 have no test for FR-027's new rule
  (a reviewed glossary entry without a main-language rendering is not applied). Both sent to the spec worker with a
  grep-every-copy instruction (task task_db41bf1d9e16, dispatch ctx_90635112c754). Round 3 is the last before
  escalating to the author.
- 2026-11-18 Round 2 fixes done: A and B fixed in every copy across spec, tasks, data-model, research, quickstart
  and two contracts (grep evidence in worker_done). Still T001-T052, coverage complete, LF, only the spec folder.
- 2026-11-18 Spec review round 3 (last) dispatched to the same reviewer (task task_601a284d3592, dispatch
  ctx_33a339eeebb8).
- 2026-11-18 Spec review round 3: PASS (no HIGH or MEDIUM; A and B fixed everywhere, round-1 fixes and the
  confirmations hold, coverage complete). One unscored style note: research.md R-07 says a lower floor "is not
  replayed" where the contract only says such a replay is inexact.
- 2026-11-18 Committed the 11 spec files as e2c5356 on 014a-retrieval-evidence, pushed to public, opened spec-only
  PR #7 against main. No review request: there is no CODEOWNERS and the owner is the PR author (as for PR #3).
  Implementation task task_c369cec5be74 created and blocked by gate gate_19bdb02f801b ("Say merged when it is
  merged"). Run stopped here for the author's review, as instructed.
- Next, after "merged": merge public/main into the feature branch, then dispatch the implementation worker
  (Stage 4: speckit-analyze, fix MEDIUM and above, then speckit-implement; LIVE tasks T006, T043 and T044 wait for
  the author's go-ahead).
- 2026-11-18 The author's pre-merge review of PR #7:
  1. CN-8 ruling search (tools/classify_cn8.py:96): already covered, no change: spec.md FR-013 (~L472) and FR-025
     (~L538) and research.md R-16 (~L305): neither the chapter filter nor the rewrite applies there.
  2. research.md R-07 to state the contract's rule for replays below the run's floor (they run, are not exact, and
     are no evidence for a new value): sent to the spec worker (task task_0da168d17193, dispatch ctx_c00fc171653a);
     the coordinator commits and pushes it to PR #7.
  3. Implementation model: fable; if Fable is still limited, opus.
  4. LIVE runs T006, T043 and T044 approved up to their estimates, plus the rebuild per 100,000 rulings embedded;
     ask the author again only if a run would exceed twice its estimate. The
     implementation brief still has the worker ask the coordinator before each LIVE task; the coordinator approves
     within that rule.
- 2026-11-18 R-07 aligned: a replay can use any floor but is exact, and evidence for a new value, only at or above
  the run's floor (contract unchanged). Four round-2 statements that read as a refusal below the floor follow the
  same rule (FR-005, data-model.md section 9 row, T041, Phase 8 goal). Committed as 990ef06 and pushed; PR #7 now
  has two commits (e2c5356, 990ef06), open and mergeable. Waiting for "merged".
- 2026-11-18 The author said "merged": PR #7 merged as d277093 (17:56 UTC). Gate gate_19bdb02f801b resolved; the
  feature branch fast-forwarded to d277093 in the worktree.
- 2026-11-18 Stage 4: implementation worker dispatched on fable (ctx_46901745f67b); it stopped at once on the Fable
  limit with no change to the worktree. Stopped and released; retried on opus as the author directed (dispatch
  ctx_03409c0d9f78).
- 2026-11-18 Analyze: 1 HIGH and 6 MEDIUM fixed in the spec files as dc5ffa0 (spec changes after PR #7, for the
  feature PR's spec-change line): I1 the coolant set moved to tests/eval/hs6_eval_coolant_set.json (it shared a path
  with its results); I2 no block 3 caption for a line without a valid candidate; I3 caption (c) covers any chosen
  code in an unindexed chapter; A1 the coolant set's top-1, majority outcome and wrong auto-accept defined; I4
  eval-diff.md named as the report; U1 a floor replay writes its set's history; U2 a citation token contains a
  digit. No author decision changed. T001-T005 done, pytest -q green (1497 passed at the start).
- 2026-11-18 T006 (LIVE baseline): go given within the author's approval (120 lines x 3 and 8 coolant
  lines x 3, --expansion off, Gemini 2.5 Flash, store copy of 74,044 rulings in twelve chapters); stop and ask if
  it heads past twice the estimate.
- 2026-11-18 T006 baseline done: 120-line HS-6 majority 84/120 (top-1 83/84/83, wrong auto-accepts
  3/4/3); coolant set majority 6/8. Since then US2-US6 and Phase 8 committed (6f6d4a6, a174c0c, 482c755, 9133b2f,
  27bdc46, 0563129); pytest -q 1640 passed.
- 2026-11-18 T043 (LIVE rebuild): the 2026-11-18 extract holds 123,531 valid rulings in 95 chapters; the 74,044 of
  the twelve chapters are unchanged and reused, 49,487 are new (0 changed, 0 dropped). Go given within the author's
  approval: about 1 to 1.5 hours, about 5 GB in build/, --no-publish, worktree only; stop
  and ask if it heads past twice the estimate. T044 (after-runs) may follow without another ask if the rebuild is clean
  and its projection stays within twice the estimate.
- 2026-11-18 T043 done cleanly: 123,531 rulings in 95 chapters, 74,044 reused, 49,487 embedded, 0 dropped; 6,333 s;
  store 3,454,915,131 bytes (archive 1.72 GB); swapped in within the worktree (the
  baseline store kept as build/store-baseline).
- 2026-11-18 T044, 3 of 4 commands:
  - 120 lines, switch off: majority 77/120 (baseline 84), top-1 76/77/77, wrong auto-accepts 4/4/4 = 12 (baseline
    10): SC-004 FAILS. Reported with no fallback; the author decides.
  - Coolant set, switch off: majority 7/8 (baseline 6/8), 3 auto-accepts per run, 0 wrong; but plain 冷却液 now routes
    to review (vague, top-1 3820.00 at confidence 50, the ask floor) where the baseline asked the shipper (40).
  - 120 lines, switch on: majority 74/120, wrong auto-accepts 9/8/8, but 6-7 lines per run failed: the German
    rewrite of the 7 longest ruling descriptions (460-1,135 characters) exceeded WordingOut's 300-character cap, and
    the SDK raised the validation error inside the call, so FR-025's retry never ran. Without them: on 74/113, off
    73/113.
  - Coordinator's answer: fix rag/translate.py (state the limit in the rewrite prompt, one bounded retry when over
    the cap, tests first), re-run both switch-on runs (within the approved limit). No tuning to chase SC-004.
    eval-diff.md gets an offline per-line analysis of every changed line (top-1,
    ruling-proposed candidate and its chapter, vote scope) and of plain 冷却液, with totals per cause.
- 2026-11-18 Stage 4 done (worker_done; report build/logs/014a-worker-report.md in the worktree). T001-T052 ticked
  (checked: 0 unticked); 11 commits dc5ffa0..3a28948, not pushed; pytest -q 1651 passed, 4 deselected; all touched
  files LF. Spend: within the approvals.
  - Eval (Gemini 2.5 Flash, 3 runs each): 120 lines majority 84 baseline / 77 switch off / 74 switch on; wrong
    auto-accepts 10 / 12 / 23; coolant majority 6/8 / 7/8 / 8/8 with 0 wrong; HS-6 step failures with the switch on
    3/5/6 per run (long lines after the retry).
  - SC-004 FAILED (BTI208 +3 through the vote scope, BTI284 -1 run-to-run); no fallback, no tuning. FR-026 not met
    (82 vs 84 over both sets), the switch stays off. Floor replays 0.45/0.50/0.55 left the 120 lines unchanged; the
    floor stays 0.40.
  - Line analysis (eval-diff.md section 5): new-chapter proposals 5 net, run-to-run 2; new-chapter rulings in the vote
    turned 6 right auto-accepts into review; the vote scope moved 2 lines (BTI208, BTI118); plain 冷却液 went to
    review (confidence 40 -> 50 after chapter-38 proposals).
  - Open points for the author: SC-004 and the proposal over every chapter; the rewrite has no max_tokens (one call
    ran to 65,521 output tokens) and long lines still fail; the manual UI check of quickstart section 9 (T052 handed
    to the author); replacing the main checkout's store; stale lines in CLAUDE.md, CargoLint_Project_Intro.md
    section 10 and the README; about 27 MB of eval JSON committed in e17553a; LANGUAGE_NAMES in agent/config.py; the
    citation check matching verbatim references.
- 2026-11-18 Stage 5: code review round 1 dispatched (claude, opus, read-only; diff d277093..HEAD).
- 2026-11-19 Code review round 1: FAIL (3 MEDIUM, 6 LOW); pytest -q 1651 passed. Confirmed against the spec: the
  scoped vote, the 0.40 boundary, the six caption states from stored rulings, the six-digit citation check, the
  rewrite's scope and data-block fencing, the switch default, the amendment; the report states SC-004 and FR-026
  correctly; no key in the diff. MEDIUM: (1) the rewrite call has no max_tokens; (2) a refused rewrite skips usage
  recording (FR-025 cost) and the retry with feedback; (3) the loader's subset reuse labels a twelve-chapter subset
  "all chapters". LOW: (4) a long rewrite still fails the line (conforms to FR-025; left to the author); (5)
  reference collisions and truncated citation notes; (6) the rewrite cache has no lock; (7) eval-diff.md omits that
  the eval runs with the precedent override off while the app ships with it on (override on: wrong auto-accepts
  10 -> 12 -> 27, majority 87 -> 80 -> 79); (8) 10.4 MB+ of derived floor-replay files committed; (9) CLAUDE.md:27
  stale loader line. Fix task sent to the implementation worker with all nine (4: no code change, open point; 2:
  retry then fail the line, no word-boundary cut; 3: stop and ask for --force, no silent re-cut; no model calls).
- 2026-11-19 Round 1 code fixes done: seven commits 728d478..eceaaa3 (findings 1, 2, 6 / 3 / 5 / 8 / 7 / 9 / a
  length-stop log line; 4 left to the author); pytest -q 1664 passed; no model call. Rewrite capped at 512 tokens,
  length stop counted and retried once, 300-character check after the recorded call; the loader exits 2 for a subset
  cut for other chapters; citations resolve exact references first and skip ambiguous shared forms; override-on rows
  confirmed (wrong auto-accepts 10 -> 12 -> 27, majority 87 -> 80 -> 79). Spec changes: data-model sections 5 and 6,
  research R-09 and R-10, contracts/settings-and-scripts.md, eval-diff.md. Incident: the first loader test
  overwrote the worktree's store/bti_docs.jsonl; restored from the T043 archive (CRC-checked) and guarded. The
  coordinator checked that no file in the main checkout's store/ changed since the run began.
- 2026-11-19 Code review round 2 dispatched to the same reviewer (fix diff 3a28948..HEAD, test isolation check).
- 2026-11-19 Code review round 2: FAIL (1 new MEDIUM, 4 LOW); pytest -q 1664 passed. Round-1 findings 1, 2, 5, 6, 7
  fixed with tests that fail on the old code, 8 and 9 fixed, 4 open for the author, 3 partly fixed. Test isolation
  clean: store/ byte-identical to the T043 archive before and after a full run; nothing changed in the main
  checkout. New: N1 MEDIUM a subset without a sidecar (the main checkout's, cut 2026-10-14) is still reused under the
  all-chapter default, against the README and contract; N2 a not-retrieved reference runs past a sentence end; N3
  WordingOut's docstring (sent to the model) carries developer notes; N4 eval-diff.md overstates the offline-tested
  cap; N5 the loader's store_dir is bound at import (the incident's trap). All five sent to the implementation
  worker (task task_85c42d0a24d4, dispatch ctx_6ba283b3f550); N1 makes the loader stop with exit 2 for a sidecar-less
  subset, as the contract says. Code review round 3 is the last before escalating.
- 2026-11-19 Round 2 code fixes done: four commits eceaaa3..86570b9 (3227eb7 N1+N5, ef0bf3a N2, ef18f40 N3, 86570b9
  N4); pytest -q 1668 passed; store/ unchanged on every run; no model call. A sidecar-less subset now stops the loader
  (exit 2, "rerun with --force"); store_dir resolved at call time; WordingOut's model-facing description is
  byte-identical to 290b3f5 (the evaluated switch-on runs). Spec changes: contracts/settings-and-scripts.md,
  data-model section 5, research R-09, eval-diff.md. Note for the author: after the merge, the main checkout's
  sidecar-less subset stops `python -m rag.loader`; --force means a full re-embed (about 2.5 h), so copying the
  rebuilt store is the cheaper way to switch.
- 2026-11-19 Code review round 3 (last) dispatched to the same reviewer (diff eceaaa3..HEAD).
- 2026-11-19 Code review round 3: PASS (N1-N5 fixed, each code fix with a test that fails on the old code; pytest -q
  1668 passed; store/ byte-identical to the T043 archive before and after; nothing changed in the main checkout).
  Two LOW documentation points: R1 the loader's stop message understated --force (it deletes both Chroma
  collections and re-embeds everything, about 2.5 h); fixed in 68c80f7 (message and README name
  `refresh_ebti.py --no-publish --rulings all --previous store` as the way to keep the vectors), diff read by the
  coordinator, pytest -q 1668 passed. R2: the feature PR's spec-change line will say that 014a supersedes the last
  sentence of 013 FR-018 (subsets cut before 013).
- 2026-11-19 Stage 6: CargoLint is not onboarded onto the agentic QA platform (no caller workflows, no secrets; the
  013 onboarding task task_aea26e57b1dc still open). The author chose to onboard first, with: engine opencode +
  DeepSeek (secret DEEPSEEK_API_KEY); the workflows start the app (`streamlit run app.py`, localhost:8501, demo
  store fetched at start); a dedicated low-quota OpenRouter key passed only in APP_ENV; the worker applies the
  Actions PR permission and the three labels with gh. Onboarding also adds a Kestrel-style traceability job (spec-only
  vs implementation PRs; Spec-PR and spec-change rules), the Playwright setup with a smoke test, and a README section.
  Branch qa-onboarding (worktree <worktree>/qa-onboarding, from public/main d277093),
  its own PR, merged by the author; generate can only run from main, so its first run is 014a's QA stage.
- 2026-11-19 Onboarding ready locally (d2e7db8, not pushed; pytest -q 1525 passed on the main-based branch). Repo
  setting "Allow GitHub Actions to create and approve pull requests" now on (default token permission unchanged:
  read); labels auto-heal, auto-generate, ready-for-tests created. Coordinator chose option B: app_start_command sets
  OPENROUTER_API_KEY to a non-secret placeholder when unset, so the agents' app (started without APP_ENV) loads the
  page and knowledge base (line checks fail with 401, nothing spent) while the test runs keep the real key from
  APP_ENV. Waiting for the author: confirm DEEPSEEK_API_KEY (repo secret added 2026-11-19 07:56 UTC) is the dedicated
  low-quota key, and add the repository secret CI_APP_OPENROUTER_API_KEY. Note for 014a: the new traceability job
  will require the feature PR to trace all 39 FR/SC of the 014a spec (014a/FR-### tokens in tests, a FEATURE = "014a"
  marker, or specs/014a-retrieval-evidence/traceability.md) and to carry "Spec-PR: #7".
- 2026-11-19 Option B committed on qa-onboarding as 068c9a2 (on d2e7db8), not pushed. The onboarding worker is idle
  on purpose until the author confirms the secrets; then the coordinator sends it the go to push and open the PR.
- 2026-11-19 The author confirmed both secrets (DEEPSEEK_API_KEY added 07:56 UTC, the dedicated low-quota key;
  CI_APP_OPENROUTER_API_KEY added 08:43 UTC, a dedicated low-limit OpenRouter key; names checked with gh secret
  list). Go sent to the onboarding worker: push qa-onboarding, open the PR against main, verify test-and-heal,
  traceability, anti-cheat and locator checks on it. A read-only security review of the onboarding diff follows
  before the author merges.
- 2026-11-19 The author held the feature PR: 014a regresses the 120-line eval (84 -> 77, wrong auto-accepts 10 -> 12,
  SC-004 fails). Asked for: (1) a read-only list of every right -> wrong and wrong -> right line between baseline and
  after (rewrite off), each with its cause (new store, chapter-filtered vote, run noise), and BTI208 in detail; (2) one
  ablation, approved within budget: the rebuilt store, the vote's chapter filter off, rewrite off, 3 runs, 120 + 8
  lines; (3) fix proposals to discuss, not implement (for example the filtered vote never auto-accepts alone, or
  auto-accept needs the unfiltered vote to agree); (4) a rule so a line flagged vague always routes to ask the
  shipper. Rewrite default stays off. Branch pushed to public as a backup (990ef06..68c80f7), no PR. Sent to the
  implementation worker with: an eval-only --vote-scope option (no product change), the offline replay of the
  unscoped vote next to the ablation, each proposal's effect estimated offline, the report as
  docs/reports/014a-regression-analysis.md; stop and ask if it heads past the approved budget. Coordinator's note to the author: the chapter
  filter scopes only the vote, which runs after the ranking, so it can change routes but not top-1; the 84 -> 77
  drop can only come from the new store or run noise.
- 2026-11-19 Onboarding PR #8 open, CI green (https://github.com/yorkzhangyong-bot/CargoLint/pull/8): test-and-heal
  smoke test passed (triage/heal skipped, so anti-cheat and the locator check have not run yet); offline-suite 1525
  passed; traceability OK. Callers: playwright, opencode/DeepSeek, tests/e2e-browser, the app on localhost:8501
  started with uv and demo-store-v1, its key only in APP_ENV, a placeholder key for the agents' app; a traceability
  job in tests.yml with 28 unit tests; docs/qa-platform.md and a README section. Setting "Allow GitHub Actions to
  create and approve pull requests" false -> true (default workflow permissions read before and after); labels
  created. Read-only security review of PR #8 dispatched (claude, opus) before the author merges.
- 2026-11-19 PR #8 security review: FAIL (0 HIGH, 3 MEDIUM, 4 LOW); secret plumbing verified correct. MEDIUM: the
  issues: labeled trigger feeds untrusted issue text to agents in a job holding a write token and both keys; the
  callers' @main pin while the platform's protect-main ruleset targets no branch; check_spec.py wrongly fails 4 of 11
  spec folders. LOW: traceability not re-run on PR edits; bot PRs start no CI and protect-main has no required
  checks; anti-cheat does not guard CargoLint's app paths; Streamlit listens on all interfaces. In-repo fixes sent to
  the onboarding worker (task task_72323fb7f880, dispatch ctx_bdbe2a2e3b0d): drop the issues trigger, pin both callers
  to the platform's main SHA, fix the spec check with regression tests, re-run traceability on PR edits, bind
  Streamlit to 127.0.0.1, docs. The author will set two things personally: the platform's protect-main ruleset to
  include the default branch, and (after PR #8 merges) CargoLint's required checks; the coordinator gives the exact
  check names after the merge.
- 2026-11-19 Regression analysis done (worker_done; docs/reports/014a-regression-analysis.md; commits 395ee44
  --vote-scope all eval option and test, 8b11d32 ablation results, ef5a966 report, 7cb55c5 cost line; pytest -q 1671;
  ablation by key usage, within budget). Pushed as backup 68c80f7..7cb55c5, no PR.
  - Store effect (baseline -> ablation, same unscoped vote): majority 84 -> 76, wrong auto-accepts 10 -> 9.
  - Filter effect (unscoped replay on the after-run's rows -> after-run, same answers; replay exact 358/358 and
    360/360): majority unchanged, wrong auto-accepts 9 -> 12 (BTI208 in every run), right +4 (BTI173 x3, BTI118 x1).
  - Noise: one line (76 vs 77).
  - BTI208: a new chapter-58 ruling and a chapter-63 ruling the old index had not returned pushed 6109.90 out of the
    proposal, so the model chose 6114.30 at 95; the chapter-61-only vote gives 6114.30 3 of 5 (auto), the unscoped
    vote 6212.10 2 of 5 (review).
  - Proposals (not implemented): (a) filtered vote may only send to review = (b) both votes agree = the old gate:
    wrong 12 -> 9, 4 right auto-accepts lost, coolant auto-accepts 9 -> 3, no amendment; (c) proposal limited to the
    nomenclature hits' chapters and (d2) stricter new-chapter proposals need a paid run; (d1)
    share 0.8: wrong 12 -> 6, 15 right lost. Vague-always-ask: no amendment, but a feature 001 spec change (FR-020
    and its 2026-10-14 clarification); plain 冷却液 right in every run (coolant after 7 -> 8), 15 vague rows per command
    move from review to ask on the 120 lines, and coolant-1 and coolant-3 would be asked about too.
  - Coordinator's note: every expected code of the 120-line set lies in the original twelve chapters, so that set
    can only show the cost of indexing more chapters, not the benefit; the coolant set shows the benefit.
- 2026-11-19 PR #8 fixes committed locally (307fcdb; pytest -q 1544; actionlint clean): issues trigger dropped and
  spec_path required; platform pinned to e078619 (main 2026-11-16) in both callers; traceability in its own
  traceability.yml (opened, edited, synchronize, reopened; tests.yml back to main's); Streamlit on 127.0.0.1; docs.
  Coordinator answered 1A (keep issues: read: the platform's generate job declares it, nothing reads an issue now)
  and 2A (undefined ids no wording rule can classify are warnings; malformed ids and duplicate definitions still
  fail; old specs not edited; all 11 folders and 014a's pass). Worker pushes; security review round 2 follows.
- 2026-11-19 Platform ruleset read back: protect-main (id 27043130) active, include ~DEFAULT_BRANCH (= main), no
  bypass actors, rules deletion, non_fast_forward, pull_request, required_status_checks; rules/branches/main lists
  all four. The author set it.
- 2026-11-19 The author's decisions for 014a: (1) fix (a): the auto-accept uses the old unfiltered gate; the
  chapter-filtered vote can only send a line to review; (2) block 3 shows the deciding (unfiltered) vote's rulings
  and share again, with a caption when the in-chapter vote sent the line to review; "No rulings indexed for chapter
  NN" stays; cross-chapter rulings may reappear; (3) the vague rule: a line flagged vague always routes to ask the
  shipper; feature 001's FR-020, its clarification and assumption updated, on the spec-change line; (4) 10-15 new
  eval lines outside the twelve chapters, sources noted, shown to the author before any run; (5) then (c) measured
  (eval-only, not implemented), with (a) on the new set as its control, within the approved budget; reported against (a) on all
  sets. Sent to the implementation worker (task task_d65bd68cee0e, dispatch ctx_7d71478c16d2). A code review round
  of the new code follows; the feature PR stays on hold until the author decides on (c).
- 2026-11-19 PR #8 fixes pushed as 91bd943, CI green (Test & heal: app on 127.0.0.1:8501, smoke test passed;
  offline-suite 1544 passed; traceability re-runs on PR edits). Security review round 2 dispatched to the same
  reviewer; it also reports the exact check names to make required on CargoLint's protect-main after the merge.
- 2026-11-19 The author added a check for the new eval lines, before the list is shown: for each line, the 5 nearest
  rulings in the rebuilt store with the top similarity and reference; flag any line above 0.85 or whose source ruling
  is in the store; rewrite flagged lines in plain shipper wording that keeps the facts, and search again. Sent to the
  implementation worker as part of step 5; leave-one-out kept for lines whose source ruling is in the store.
- 2026-11-19 PR #8 security review round 2: PASS (0 HIGH, 0 MEDIUM). All three MEDIUMs and LOW 4 and 7 fixed with tests
  that fail on 068c9a2; the platform's main is protected (ruleset 27043130 active, required checks "Lint and validate"
  and "Fixture tests"); pytest -q 1544. New LOW: N1 a unit-test sample holds the real token 014a/SC-004, which would
  falsely trace SC-004 in the 014a PR, and the scoped regex lacks a lookbehind; N2 the platform's test step has
  continue-on-error, so "qa / Run playwright tests" stays green when browser tests fail (a browser-tests gate job is
  needed for a meaningful required check). Nit: pyyaml missing from the dev extra. Sent to the onboarding worker
  before the merge. Check names for protect-main (as GitHub shows them on PR #8): offline-suite, traceability, and
  the browser-tests gate once added.
- 2026-11-19 PR #8 round-2 notes fixed in 8bab8d5 (made-up labels in samples, lookbehind in traced_ids, a
  browser-tests gate job with permissions {}, pyyaml in the dev extra); CI green; coordinator checked the diff and the
  checks. The author merged PR #8 (c6b1ed6) and set CargoLint's required checks. Read back: protect-main (id
  27043397) active, include ~DEFAULT_BRANCH, no bypass actors, rules deletion, non_fast_forward, pull_request (0
  approvals), required_status_checks offline-suite, traceability, browser-tests (GitHub Actions); strict policy
  (up to date before merging) off. Run 013's onboarding task task_aea26e57b1dc is done by PR #8 but still shows
  "ready": Orca refused the update (consumer_fenced: this coordinator is bound to run_ece0ea0e1ebe), and switching
  runs would drop this run's mail, so it stays open in Orca.
- 2026-11-19 The 014a worker had committed fix (a) (bd6ac5a) and block 3 (2605e0f) and was mid-way through the vague
  rule (uncommitted). Asked it to merge public/main (c6b1ed6) at its next clean commit, finish the spec update, then
  add the traceability mapping (014a/FR tokens or traceability.md for every FR and SC), check it locally with a PR
  body holding "Spec-PR: #7" and a "spec-change:" line, and continue with the new eval lines.
- 2026-11-19 Steps 1-5 done (pushed as backup 7cb55c5..8814d25, no PR): bd6ac5a rule (a); 2605e0f block 3; e130021
  the vague rule; d0cec1f merge of public/main (c6b1ed6, no conflicts; README merged automatically, both sections
  kept; pyyaml in the dev extra); 5c8c1e8 spec updates; 89b8f04 traceability mapping (41 ids = 33 FR + 8 SC, 28 traced
  by 014a/ tokens in tests, 13 in traceability.md; check passes with "Spec-PR: #7" and "spec-change:", fails without:
  negative control); 8814d25 the outside set (tests/eval/hs6_eval_outside_set.json, 14 lines in 14 chapters outside
  the twelve, each from an EBTI ruling valid on 2026-11-19, leave-one-out). pytest -q 1751 passed. Near-duplicate
  check (qwen3-embedding-8b, 6 nearest, one request): all 14 flagged (source ruling in the store) and
  rewritten in plain shipper wording; line 2 was 0.929 before the rewrite; after, top similarities 0.659-0.793 (the
  0.793 is line 2's own source ruling, removed by leave-one-out). Waiting for the author's approval of the 14 lines
  before step 6 (within the approved budget).
- 2026-11-19 The author approved all 14 outside-set lines. Step 6 started: (a) on the outside set, then (c) with (a)
  on the 120-line, coolant and outside sets, 3 runs each, within the approved budget.
- 2026-11-19 Step 6 done (worker report build/worker-report-task_d65bd68cee0e.md; commits e12d071, 402a285
  --proposal-scope nomenclature eval-only, 7a78dbc runs, 8ac9f8f report section 5; pushed as backup
  8814d25..8ac9f8f, no PR; pytest -q 1754; within budget by key usage).
  - Rule (a), exact replay with the vague rule: 120 lines majority 77 (override on 80), wrong auto-accepts 9 against
    the baseline's 10: SC-004 PASSES (also 9 vs 10 with the override on). Coolant 8/8. Outside set 12/14, 2 wrong
    auto-accepts (the bike U-lock: source ruling 8301.10, the model and 4 of 5 nearest rulings 8301.40).
  - Option (c) with (a): 120 lines 64 (on 65), wrong auto-accepts 9; coolant 7/8 (loses coolant-1); outside 11/14
    (loses the chilli seasoning), 3 wrong auto-accepts. Worse than (a) everywhere; stays evaluation-only.
  - Block 3 captions, the vague rule (ask floor no longer routes; ASK_FLOOR kept, retiring it is the author's call),
    feature 001 changes and the spec-change list are in the report. Constitution re-checked: no amendment.
  - OpenRouter spend for 014a so far: within the author's approvals.
- 2026-11-19 The author: drop option (c) (not implemented; the eval-only --proposal-scope option stays, documented as
  rejected); next, a code review of everything since the last review, then the feature PR (Stage 6). The decision on
  (c) is being recorded in spec.md and the report by the implementation worker; the read-only code review follows.
- 2026-11-19 Option (c) recorded as rejected in a83e058 (Clarifications, FR-033, the key entity, report section 5,
  T066); pytest -q 1754; traceability 41/41. Pushed as backup (8ac9f8f..a83e058), no PR. Code review of the
  2026-11-19 changes, round 1, dispatched (claude, opus, read-only; task task_4c52ce25eda4, dispatch ctx_73fa78762272):
  first-parent commits after 68c80f7, the merge's integrity, rule (a), block 3, the vague rule, false or weak traces,
  the eval-only options, spec consistency, security.
- 2026-11-19 Code review of the 2026-11-19 changes, round 1: FAIL (1 MEDIUM, 7 LOW, 0 HIGH). Product code correct:
  rule (a), block 3 captions word for word, the vague rule, the merge (identical to PR #8 hunk for hunk), eval-only
  options inert, traceability 41/41 with every token in a test that checks its requirement; pytest -q 1754. MEDIUM:
  the second vote's share (0.5) and floor (0.40) boundaries and the vetoed ever-flagged path have no tests (a >= to >
  swap at routing.py:231 stays green). LOW: weak traces (near-duplicate numbers only in git-ignored build/; FR-030
  tests-first claim; FR-003 approvals; FR-009/SC-001 cite git-ignored store); stale eval-diff.md and regression
  analysis, eval-diff not reproducible (unscoped_route uses today's vague rule); GATES lacks scoped_veto; floor
  replays marked exact for runs with expansion or customs wording on; feature 001's FR-020 and data-model §9 lack the
  veto; stale texts; one long test line. All eight sent to the implementation worker (task task_a9df04b530d2,
  dispatch ctx_a6adf0cd2f52). FR-003's evidence will be the approvals listed in the feature PR description.
- 2026-11-19 Round 1 fixes done: four commits 0a75257, a09a38e, 1ee578d, 43bd58e; no product behaviour change; the new
  boundary tests each fail on their mutated guardrail (6 mutations); pytest -q 1765; traceability 41/41; check_spec
  passes for 014a and 001. Pre-existing observation left unchanged: a never-flagged shipper reply shows "Pick:", not
  "Confirm:". Pushed as backup; code review round 2 sent to the same reviewer.
- 2026-11-19 Code review round 2: PASS (all eight fixed; mutations confirmed in throwaway copies, 8 of 8 caught;
  five reports re-render byte for byte; pytest -q 1765; traceability 41/41). Four optional LOW nits (FR-003 trace
  wording, R-07 and eval-cli wording, a duplicate helper, a hard-coded sentence) sent to the implementation worker
  (task task_99912d00647f). Feature PR description drafted (Spec-PR: #7; spec-change line; HS-6 accuracy table;
  approvals with amounts for FR-003; open points) and the QA worker's brief written (opencode,
  opencode/deepseek-v4.1-flash-free, current checkout: push, generate on the feature branch with spec_path
  specs/014a-retrieval-evidence/spec.md, open the feature PR, merge the auto-generate PR into the feature branch,
  watch checks).
- 2026-11-19 Nits closed in 0e97165 (docs and eval scripts only; reports unchanged; pytest -q 1765; traceability 41/41
  in PR mode); diff checked by the coordinator (FR-003 names T006, T043, T044, the ablation §2 and T065, matching the PR
  description's approval table). Stage 6: QA worker started (opencode, opencode/deepseek-v4.1-flash-free, current
  checkout; task task_5feee5693a18, dispatch ctx_f70bdefc9970).
- 2026-11-19 Stage 6 result: FAIL (environment). Pushed 0e97165; generate run 44528596501 success, anti-cheat passed;
  auto-generate PR #9 (4 test files under tests/e2e-browser, base the feature branch) merged; feature PR #10 opened
  against main (https://github.com/yorkzhangyong-bot/CargoLint/pull/10, head bac226b, the drafted description with
  "Spec-PR: #7" and "spec-change:"). Checks: offline-suite pass, traceability pass, browser-tests FAIL: 3 of 6
  generated tests, triaged ENV (0 selector drift, 0 real bug): the app's first model call gets OpenRouter 404 "0
  endpoints out of 1 requested are available matching your guardrail restrictions and data policy" with the CI key
  (CI_APP_OPENROUTER_API_KEY); the local key works with the same code (provider require_parameters: true, Gemini 2.5
  Flash, reasoning off). No heal ran, so the locator check did not run. Needs the author: the CI key's guardrail or
  data policy on OpenRouter. Side note: the app shows this 404 as "Temporary problem talking to the model; retrying"
  and cuts the message (pre-existing).
- 2026-11-19 The author replaced CI_APP_OPENROUTER_API_KEY with a new key (low credit limit, no model or data-policy
  restrictions) and asked to re-run the failed browser tests and to add the misleading error to the backlog. A
  re-run of only the failed gate job would not re-run the tests (they run in the qa job, which reports success under
  continue-on-error), so the coordinator re-runs all checks by pushing the backlog commit to PR #10's branch. The
  implementation worker fast-forwards to bac226b (the auto-generate merge) and adds the backlog item (agent/llm.py:78's
  catch-all gives every unclassified provider error the "temporary ... retrying" message); then the coordinator
  pushes and the QA worker watches PR #10's checks.
- 2026-11-19 Backlog item 16 "Clear messages for permanent model errors" committed as fb3b14f (403 already
  non-retryable with a generic text; 404 and 401 fall through to the "temporary" message; ui/jobs.py cuts at 160
  characters). Pushed bac226b..fb3b14f, re-running PR #10's checks with the new key; the QA worker watches them.
- 2026-11-19 Stage 6 PASS on fb3b14f: Test & heal run 44535032647 (6 of 6 browser tests passed: the smoke test and
  five tests generated from the 014a spec covering FR-010, FR-015/017/018, FR-023/025/026, FR-019 and the empty
  description guard; triage, heal and report-defects skipped), offline-suite pass (44535019068, 44535031376),
  traceability pass (44535031614). Anti-cheat passed in the generate run (44528596501); no heal ran, so the locator
  check did not run. Coordinator confirmed: PR #10 mergeable, merge state CLEAN, all required checks green.
- 2026-11-19 Stage 7: final approval gate created on task task_fb3e0270dad0 ("Feature PR #10 is reviewed and green.
  Ready to merge?", options approve or hold).
- 2026-11-19 The author approved. PR #10 merged with a merge commit as ffcf0ca at 13:41:29 UTC; gate gate_6d3bb3e4588d
  resolved, task task_fb3e0270dad0 completed. Totals: within the author's approvals, plus the CI key's test runs.

## After the merge (the author's steps)

- Replace the main checkout's store/ with the rebuilt one (<worktree>/014a-retrieval-evidence/store, 123,531 rulings
  in 95 chapters; the twelve-chapter copy is build/store-baseline there): stop the
  app, keep the old store as a backup, copy the rebuilt one; or run `python scripts/refresh_ebti.py --no-publish
  --rulings all --previous store`. Do not run `python -m rag.loader --force` (full re-embed, about 2.5 h). The
  main checkout's sidecar-less data/bti_subset.jsonl now stops `python -m rag.loader`.
- Keep the 014a worktree until the store is copied; the qa-onboarding worktree can be removed.
- Open points: a demo-store release with every chapter (CARGOLINT_EBTI_RULINGS=5000) is not published; the
  customs-wording switch stays off (an over-length rewrite still fails the line; the 512-token cap is tested offline
  only); no output cap on the other model calls (pre-existing); ASK_FLOOR no longer routes but remains; the outside
  set's bike U-lock label is contested between rulings; a never-flagged shipper reply shows "Pick:" (pre-existing);
  CargoLint_Project_Intro.md §10 still names the twelve chapters; backlog item 16 (permanent model errors).
- Orca: run 013's onboarding task task_aea26e57b1dc still shows "ready" (done by PR #8; this coordinator could not
  update another run's task).

## Follow-ups after the merge

- 2026-11-19 The author replaced the main store (store/ now 123,531 rulings; the old one kept as store-old-74k/) and
  live-tested. New backlog item, high priority before 014b: "金属加工冷却液，不含矿物基础油" gets the right 3403.99 but
  routes to ask the shipper (the stop-word check flags 冷却液 as vague; the vague rule always asks), and the shipper
  question asks for material and use the line already states. Proposal: a stop-word flag clears when the line also
  states the material or composition and the use; the question asks only for what is missing (ties to backlog item
  4); check coolant-1 and coolant-3 too. Also: is "Import control - CITES" on 9004 10 91 00 (origin CN) conditional
  (e.g. tortoiseshell frames) and shown without its condition? A read-only investigation worker (claude, opus, the
  main checkout, no model call) traces both (task task_1679fc08d1c7, dispatch ctx_aa8596ce36f9); the coordinator then
  adds the backlog item(s) through a small docs PR (main requires PRs).
- 2026-11-21 The investigation worker stopped on Claude's weekly limit (reset Nov 21, 5 pm Berlin). At 17:20 UTC the
  limit had reset and the worker was live and working again (resumed in its own chat), so it was left to finish.
- 2026-11-21 Investigation done (report task_1679fc08d1c7-report.md; read-only, no model call).
  - A: no list matches 冷却液 (on none of the four lists; the deterministic check returns no rule for the live line and
    all coolant lines). The flag is the model's vagueness judgement, which flags every Chinese-only coolant line
    (coolant-1, -2, -3, -8 in all 15 Gemini runs) while the same facts in English or German pass (coolant-4 to -7).
    Under today's FR-009 ("material or use") coolant-3 and the live line should pass. The shipper question is a fixed
    template; the judgement's missing list is dropped (tools/check_description.py:55). Block 1 labels the judgement
    "Stop-word check"; the 59 cap turns the reason into "candidates too close". Clearing the judgement flag by a
    defined, quote-verified test is a spec change (FR-009, FR-010); asking only for what is missing changes FR-011 and
    advises a PATCH clarification of Principle III; letting the model clear list flags would need an amendment. Open
    for the author: AND or OR, negative compositions, list flags, the PATCH. A paid eval with Chinese-only lines must
    follow any judgement change.
  - B: the CITES measure (SID 4023124, heading 9004, erga omnes, R2309660) is conditional (C400 or Y900 allowed,
    otherwise not; footnote CD370). The snapshot keeps conditions only with a duty (feature 002 R-08, by design), so
    block 4 shows a bare requirement: 699 CITES measures (33 C400-only for listed species), 1,237 of 16,752 TARIC-10
    codes for origin CN; 15,307 of 17,876 import requirement measures lose their conditions. Fix needs schema 3,
    Certificate and Footnote objects, and changes to feature 004 FR-013 and feature 012 D16; interim: a caption under
    Requirements with the EU TARIC link.
  - Found meanwhile in the author's checkout: PR #11 (backlog-17-coolant-vague, item 17 coolant) and PR #12
    (backlog-18-cites-conditions, also numbered 17, with two errors: C400 is action 29 not 09; 748 is mercury, waste
    is 755); an uncommitted agent/config.py:195 hard-codes chat_model "deepseek/deepseek-v4.1-flash" (bypasses
    CARGOLINT_CHAT_MODEL). The coordinator asks before touching either PR.
- 2026-11-21 Correction: the live test was on 2026-11-20 (PR #11's and #12's texts), not 2026-11-19 as logged above.
  The author approved amending both PRs. Two workers (claude, opus), each in a fresh worktree based on its PR branch
  (pr11-backlog-edit from backlog-17-coolant-vague, pr12-backlog-edit from backlog-18-cites-conditions), edit only
  docs/backlog.md and fast-forward the PR branch on public; the author's checkout is not touched (its local
  backlog-18 branch will be one commit behind until pulled). PR #11 (item 17): language effect, UI label, quote-checked
  approach, open decisions, measurement. PR #12: renumber to 18; C400 is action 29 (09 is the no-document condition);
  748 is mercury, waste 755; text built from the conditions (33 C400-only measures); cause (002 R-08, 004 FR-013, 012
  D16), scale, texts, interim caption. Tasks task_3e8fb259a99e (ctx_7f5e75e2c5e2), task_bb1f20e5cc25
  (ctx_5040b09abc43). After #11 merges, #12 needs main merged (both append after item 16).
- 2026-11-21 PR #11 amended: f5ac53d (five sub-bullets under the author's unchanged paragraph; 6 lines added), pushed
  as a fast-forward c255c79..f5ac53d; diff checked by the coordinator. Note for the author: the kept sentence calls the
  bilingual coolant-6 a false positive, but coolant-6 passes the judgement in all 15 runs (it goes to review by the
  vote), so "and the bilingual coolant-6" may be dropped. PR #12's worker still running.
- 2026-11-21 PR #12 amended: ce399dd (renumbered to 18; C400 and Y900 action 29, the no-document condition action
  09; 748 mercury, 755 waste; text built from each measure's conditions; Cause cites feature 002 R-03 and R-08,
  Scale, Texts, Interim), pushed as a fast-forward 4a8052e..ce399dd; diff checked by the coordinator. Both PRs open
  and mergeable (#11 at f5ac53d, #12 at ce399dd). Merge order: #11 first, then #12 needs main merged (both append
  after item 16); the coordinator does that on request.
- 2026-11-23 The author merged PR #11 (ba001c7) and asked to merge main into PR #12's branch (items 17 then 18), push,
  and report green checks. Sent to the PR #12 worker in its worktree (pr12-backlog-edit at ce399dd): merge
  public/main, keep main's text up to item 17 byte for byte and append item 18, verify the diff against main is item
  18 only, push as a fast-forward, watch PR #12's checks. The author's checkout is not touched.
- 2026-11-23 PR #12 merged with main as e7105d0 (parents ce399dd and ba001c7), pushed ce399dd..e7105d0. Coordinator
  confirmed: the diff against main is docs/backlog.md only, 7 lines added (item 18 and its sub-bullets), nothing
  removed; items 16, 17, 18 in order; offline-suite, traceability and browser-tests pass (runs 45133209459,
  45133209683, 45133210494); PR #12 open, mergeable, merge state CLEAN. Ready for the author to merge.
- 2026-11-23 Read-only hard-coding check (coordinator, git grep on public/main ba001c7; app.py, agent/, tools/, rag/,
  ui/, scripts/; not tests, eval sets, docs or specs): no coolant words (coolant, 冷却液, Kühlschmierstoff, metal-working,
  mineral oil, lubricant) and none of 2710, 3403, 3820, 3819, 3824, 8419, 8414, 8424, 7309. No chapter-number rule in
  routing, retrieval or prompts; TARGET_CHAPTERS (rag/bti.py:21-22) only keeps the old source-version name
  (bti.py:238). HS-code literals are docstring, comment and placeholder examples. One special case: rag/demo_store.py
  (SAMPLE_VARIANT_HS6 :29-52, preferred_codes :79-85 reading tests/eval/cn8_eval_set.json and the samples) gives up to
  half of a bounded store (the 5,000-ruling demo store, via refresh_ebti.py:307) to the eval set's and sample files'
  HS-6 codes; no effect on the full store (n None keeps every ruling). Prompt examples are generic; the vagueness
  judgement's examples are English only (tools/check_description.py:28-31).
- 2026-11-23 PR #12 merged (2f4c4c7); main's backlog has items 1-18. The author's docs PR command (six points): item
  17 drop "and the bilingual coolant-6" and add the cause (the vagueness check's English-only examples,
  tools/check_description.py:28-31) and the fix (Chinese vague and complete examples; eval: complete coolant lines
  pass, plain 冷却液 still asks); mark 014a done (PR #10), in item 1's style; item 14 note (drop the 5,000-ruling limit
  and the eval-code preference in rag/demo_store.py once hosting allows the full store); 014b goal (win back the 7
  lines); item 10 (Chinese versions of some outside lines; bike U-lock contested, 8301.10 or 8301.40); new item 19
  Cleanup (retire ASK_FLOOR; update the twelve-chapter list in CargoLint_Project_Intro.md). Worker (claude, opus) in
  a fresh worktree from public/main, branch docs/backlog-after-014a, opens the PR and watches its checks (task
  task_339084d4db82, dispatch ctx_d9b6a2271bbe).
- 2026-11-23 PR #13 open: https://github.com/yorkzhangyong-bot/CargoLint/pull/13 (17b1722, docs/backlog.md only, +10/-13).
  Coordinator checked: "and the bilingual coolant-6" gone, the sentence singular ("coolant-3 ... is a false
  positive"); items 1-19 once each; 014a done in item 1's style; 014b goal; item 10 outside-set fixes; item 14 note;
  item 19 Cleanup. Checks pass: offline-suite, traceability, browser-tests; open, mergeable, CLEAN. Worker's notes
  (left unchanged, not asked): item 10's six coolant lines already exist since 014a; item 3's "after 014a ships" note
  is now out of date; item 17's new bullet repeats "not a stop-word rule".
- 2026-11-23 PR #13 merged (1b3a832). Backlog items 1-19 all present on main. This closes the 014a run: feature
  (PR #10, ffcf0ca), QA onboarding (PR #8, c6b1ed6), backlog follow-ups 17/18 (PR #11 ba001c7, PR #12 2f4c4c7), and
  this docs PR (#13). Nothing outstanding in Orca for this run; the three worker notes left unchanged (item 10's
  lines already existed, item 3's stale note, item 17's repeated phrase) are the author's call for a future PR.
