# Backlog item 17 (Chinese vagueness-check examples): run status

Run: run_9166225754c7 (coordinator: this session). Requirement: add Chinese few-shot examples to the vagueness
check in tools/check_description.py so complete Chinese lines (coolant-3, the live-test line) are not falsely
flagged vague, while coolant-1, coolant-2 and plain 冷却液 stay flagged. Prompt examples only; no stop-word, routing,
rule (a) or ASK_FLOOR changes. Full text: the author's message of 2026-11-23 (Problem/Change/Constraints/
Acceptance/Cost).

Branch/worktree: 017-coolant-vague-chinese-examples, from public/main (1b3a832, after PR #13).

Agents/models (requirement-to-pr skill's table): spec fable, spec review opus, implementation fable, code review
opus, QA trigger opencode/deepseek-v4.1-flash-free.

## Log

- 2026-11-23 Run created (run_9166225754c7); worktree/branch created from public/main (1b3a832). Spec worker
  dispatched on fable (task task_b42fce1e5164, dispatch ctx_59990e42f32c): Spec Kit specify -> clarify -> plan ->
  tasks, feature folder to match backlog item 17's existing numbering (017-coolant-vague-chinese-examples, renamed
  if Spec Kit auto-assigns a different number, as 014a was). Told explicitly: this requirement is narrower than the
  earlier investigation's quote-verification idea -- examples only, no code-logic change. plan.md must carry a cost
  estimate for the live eval (120-line + coolant + outside, 3 runs) before any paid run.
- 2026-11-23 Clarify answered (3/3): Q1 coolant-9 = the live-test line in the tracked coolant set; Q2 SC-001/SC-002
  judged on every one of 3 runs, not majority (top-1 scoring keeps the majority convention); Q3 one revision round
  allowed within the 2x margin, a second failure stops and reports. Spec worker done (worker_done,
  task_b42fce1e5164): specs/017-coolant-vague-chinese-examples/ (spec.md 8 FR/6 SC, plan.md, tasks.md 22 tasks
  tests-first with LIVE task T015 gated behind approval task T014, research.md, data-model.md, quickstart.md,
  checklists/requirements.md). Folder number 017 came straight from create-new-feature.ps1 -Number 17, no rename.
  Four Chinese example pairs (complete vs vague): 铝合金折叠梯，家用/金属件; 陶瓷地砖，室内地面用/建材;
  儿童用的塑料餐具，不含双酚A/日用百货; 橡胶密封垫片，水管接头用/垫片 -- all pass the deterministic rule check offline,
  none overlaps the 120-line, coolant or outside eval files. plan.md carries a live-eval cost estimate for one pass
  (120 + coolant incl. coolant-9 + outside, 3 runs each) from the 2026-11-18/19 tallies, with a 2x margin covering
  exactly one revision round. Nothing committed yet. Stage 3 (spec review) dispatched next.
- 2026-11-23 Spec review round 1: FAIL (4 must-fix, 4 should-fix, 8 minor; no HIGH-equivalent blocker on requirement
  coverage, constitution or scope -- plan/tasks touch only tools/check_description.py's prompt and the coolant eval
  set, as required). Confirmed independently by the reviewer: requirement coverage complete, Q1-Q3 recorded
  correctly, no overlap with any eval file, no stop-word/rule-check hit on any of the 8 examples, baselines/costs
  match history, no constitution amendment needed.
  Must-fix: (1) kept-examples test breaks on an existing newline inside the prompt string; (2) a second hard-coded
  "8" in test_hs6_eval.py:506 needs updating to 9 alongside T005; (3) SC-004 as written could pass with one of the
  original 8 coolant lines wrong, hidden behind a right coolant-9 -- must score per-line; (4) the PR always touches
  specs/, so Spec-PR + spec-change are unconditionally required, not conditional.
  Should-fix: (5) rule check should run against the real data/rules, not only the test fixtures; (6) no mechanism
  visible for a NEW false-vague flag elsewhere -- add vague-flag tracking per line/run/set; (7) AUTHOR DECISION --
  pair 4's vague example 垫片 (gasket) is a precise product name, not generic (ICS2 itself accepts "Seals" as
  non-vague), risking teaching the model to flag precise part names; (8) no defined step for an SC-003/004 miss
  (noise vs a real regression).
  Author chose (7): swap 垫片 -> 零件 ("parts/components"), mirroring the English "parts" examples; keep the
  complete half unchanged. Coordinator resolved (14) without the user: document the pair-3/live-line shared
  template as a limitation rather than spending on the optional 30-line --lang zh measurement (outside the approved
  budget, not required by Acceptance).
  All 16 findings sent back to the spec worker (same dispatch ctx_59990e42f32c) for one fix round, with resolutions
  for 7 and 14 included. Re-review follows (round 2 of at most 3 before escalation).
- 2026-11-23 All 16 round-1 findings applied (worker_done, task_3f26a24b477a): a follow-up clarify swapped pair 4's
  vague member from the author's 零件 to 零部件 ("parts and components"), since 零件 turned out to be an ICS2 alias
  for "parts" and would be caught by the deterministic rule before judgement -- the coordinator resolved this one
  itself (mechanical word-choice, not a new product decision). Final four pairs (complete/vague):
  铝合金折叠梯，家用/金属件; 陶瓷地砖，室内地面用/建材; 儿童用的塑料餐具，不含双酚A/日用百货; 橡胶密封垫片，水管接头用/零部件.
  Worker's own re-check: all eight pass check_rules (None) against data/rules and the fixtures; no overlap, equal or
  substring, with the 236-text pool (cn8_eval_set, hs6_eval_zh, coolant, outside, split zh/en); no coolant word.
  24 tasks (2 LIVE), 8 FR, 7 SC (new SC-007: coolant-4..7 OK in every run). Sent for review round 2 of at most 3;
  told the reviewer to independently re-derive the key claims (zero_bujian's rule-check/overlap status, the stored
  SHA-256 of the unchanged prompt, SC-004's per-line scoring, the LIVE-task budget/env gating) rather than trust the
  worker's description.
- 2026-11-23 Spec review round 2: FAIL, narrow (all 16 round-1 findings confirmed resolved, re-derived independently
  by the reviewer: the prompt's SHA-256, the cut/parse helpers on four future states, 零部件's rule-check and
  overlap status, the SC-004 snippet run on real stand-in files). 3 new must-fix: N1 security -- the env check
  (`env | grep '^CARGOLINT_'`) would print CARGOLINT_APP_PASSWORD's value into a transcript, and blocks on
  unrelated variables; N2/N3 no stated precedence between SC-001/002 (the revision-round trigger), SC-003/004 (the
  no-regression check) and the new SC-007 (coolant-4..7 stay OK) when more than one fails at once, which the
  reviewer notes is the likely case, not a corner case.
  Coordinator resolved N2 and N3 itself, as a faithful reading of clarify Q3 (already on record) rather than a new
  decision: Q3 granted the one revision round for an Acceptance 1/2 (SC-001/002) miss with no condition on
  SC-003/004 also passing, so that miss always spends the round regardless; SC-007 was added after Q3 and was never
  covered by it, so a miss there (alone or with SC-003/004) takes the stop-and-ask branch, not the automatic round.
  N4 (should-fix): the reviewer's own round-1 finding 8 ("unchanged flag = noise") was overstated -- an OK
  judgement's reason text can change even when the flag doesn't, and that text reaches the ranking prompt but isn't
  recorded; narrowed to only call it noise on the 5 lines (4 of 120, 1 of 14 outside) whose baseline runs already
  disagreed. 6 minor alignment fixes. All 10 sent back to the spec worker (review round 3 of at most 3 before
  escalation).
- 2026-11-23 All 10 round-2 findings applied (worker_done, task_067c78919e0b): env check verified directly (prints
  nothing clean, nothing with APP_PASSWORD set, only the bare name with CARGOLINT_CHAT_MODEL set); the precedence
  sentence (N2/N3) appears identically, whitespace-normalised, in all six places (spec.md x2, tasks.md x2,
  quickstart.md, plan.md); check_spec passes (8 FR, 7 SC); LF/no BOM; old problematic texts confirmed gone by scan.
  Sent for review round 3 (last allowed; escalate to the author on any further FAIL). Asked the reviewer for a
  one-paragraph pass summary to use at final sign-off if it passes.
- 2026-11-23 Spec review round 3 (last allowed): FAIL on one mechanical must-fix only -- three orientation
  passages (plan.md Summary, plan.md Order-of-work step 4, tasks.md Dependencies & Execution Order) still stated
  the pre-round-2 precedence rule, contradicting FR-007/T018/T019, which the reviewer confirmed correct and
  complete over all 32 SC-001/002/003/004/007 pass-fail combinations (re-derived independently: the precedence
  sentence is identical, whitespace-normalised, in all 6 places it's stated in full; the env check only ever prints
  one of 6 bare names, never a value, tested with the password set and with near-miss names; the 5-line noise list
  recomputed and matches; N5-N10 all confirmed). Two non-blocking minors taken anyway: stale broader env-rule
  wording in two places, and the env check's grep made case-insensitive (-iE) since Windows folds env-var name
  case and the case-sensitive version could miss a real override). One FYI, no spec change: a `failed` judgement
  (API error, not a real vague/not-vague answer) counts as an SC-001/SC-002 miss under today's wording and so
  spends the revision round automatically; rare (0 of 3,594 stored rows), for the author to know, not act on.
  Reviewer said no further round is needed once this lands; sent to the spec worker bundled with commit + spec-only
  PR instructions (no separate review round 4). Reviewer's pass-summary (for the author's sign-off) is in the
  worker_done message of task_eb742b57de09.
- 2026-11-23 Round 3's must-fix and two minors applied (worker_done, task_86eacd76a75e; precedence sentence
  re-confirmed identical in all 6 full-statement places, -iE confirmed in all 4 command locations, check_spec 8
  FR/7 SC). Spec committed as 696e78f (coordinator-verified: diff against its parent touches only the 7 files
  under specs/017-coolant-vague-chinese-examples/, 1412 insertions, nothing else) and pushed; spec-only PR #14
  opened against main (https://github.com/yorkzhangyong-bot/CargoLint/pull/14), not merged. CI at time of writing:
  traceability and qa/Framework-config pass, offline-suite and qa/Run-playwright-tests pending, nothing failed;
  protect-main's required checks are a hard backstop regardless. Spec PR merge gate created (task task_974631bb97da,
  gate gate_90574b9589cc): "Say merged when it is merged."
  Spec review closed PASS (round 3, narrow): the reviewer's own for-the-record pass summary (task_eb742b57de09's
  worker_done) is the citable description of the feature for sign-off purposes. One FYI with no spec change: a
  `failed` judgement (API error, not vague/not-vague) counts as an SC-001/SC-002 miss and so spends the pre-approved
  revision round automatically; rare (0 of 3,594 stored rows historically).
- 2026-11-23 The author merged spec PR #14 (6c53063); gate gate_90574b9589cc resolved, task task_974631bb97da
  completed; feature worktree fast-forwarded 696e78f..6c53063 (clean).
- 2026-11-23 The author's decision on "no regression" (Acceptance 3) with 3 runs per set: majority per line for the
  120-line, coolant and outside sets, per-run numbers reported alongside. The merged spec already decided majority
  per line everywhere except SC-003's 120-line wrong auto-accepts (a three-run sum, at most 9 vs today's 3/3/3).
  Coordinator's definition for that clause: a line counts as a wrong auto-accept when it is auto-accepted with a
  wrong top-1 in at least 2 of its 3 runs; pass when the count is at most the baseline's count computed the same way
  from iteration 21's rows (override off for pass/fail, override on reported). SC-001, SC-002, SC-007 stay
  every-run (flag criteria, not Acceptance 3 scores).
- 2026-11-23 Stage 4: implementation worker dispatched on fable (task task_10db2dc16e50, dispatch ctx_d1cdf6efcaea):
  step 1 the spec change above (own commit; baseline recomputed offline, lines named), step 2 speckit analyze with
  medium+ fixes, step 3 speckit implement; stops at T015 before any paid call and asks with the commands, the
  cost estimate and cap, the names-only env check output, the baselines, and commit permission for result files.
- 2026-11-23 T015 reached (implementation worker's ask): branch at ded6fb7, pytest -q 1774, traceability 15/15;
  commits ea13237 (spec: no regression by majority per line), a8b9598 (spec: analyze fixes), 7a143c2 (US1), 6b76457
  (US2), ded6fb7 (traceability.md). Coordinator verified before asking: the only product change is the 2-line
  Chinese example sentence in tools/check_description.py; tests/eval/hs6_eval.py changed in docstring, one comment
  and help text only (no measurement logic); coolant-9 = 金属加工冷却液，不含矿物基础油, expected 3403.99.
  Recomputed baselines (majority per line): 120-line top-1 77, wrong auto-accepts 3 lines (BTI356, MTBTI2024-002,
  MTBTI2025-011, wrong in all 3 runs; override on: 80, same 3); coolant original eight 8/8; outside 12/14 (1 line
  wrongly auto-accepted by majority, the bike U-lock; reported, not judged). Env check clean (defaults).
- 2026-11-23 The author approved, staged: coolant set first (3 runs); outside and 120-line sets only if the coolant
  criteria pass; on a coolant miss, stop and report before spending more; majority per line with per-run numbers;
  the approved cap overall; commit results when done. Coordinator's readings, relayed to the worker: any coolant criterion
  missing (SC-001, SC-002, SC-004's original eight, SC-007) counts as a coolant miss; outside runs before the
  120-line set and an outside SC-004 miss also stops before the 120-line run; the automatic revision round of
  FR-007 is replaced (no revision round without the author's go-ahead); if the run stops early, commit the results of
  the sets that ran and hold the backlog/README outcome edits; record the staged decision as a spec change.
- 2026-11-23 12:38 UTC BLOCKED on the OpenRouter key, not on the feature. Stage 1 (coolant set) failed on all 9 lines
  in 1 s: OpenRouter 404 "0 endpoints out of 1 requested are available matching your guardrail restrictions and
  data policy ... ZDR violation (guardrail)", configurable at openrouter.ai/workspaces/default/guardrails. 0 model
  calls, nothing spent. With this key google/gemini-2.5-flash has no endpoint (its three public Google AI Studio
  endpoints are not ZDR); qwen/qwen3-embedding-8b is fine. The key was set to expire minutes after this entry and
  had little budget remaining. The worker reverted the files the failed run rewrote (coolant
  results/report/history) and deleted its untracked results file; tree clean at ded6fb7. No model substitution (the
  baselines are Gemini 2.5 Flash). Needed from the author: allow google/gemini-2.5-flash past the ZDR guardrail and
  extend or remove the key's expiry; a new key set as an OS variable needs an Orca restart before workers see it.
  The worker records the staged approval as a spec commit meanwhile and waits.
- 2026-11-23 Staged approval recorded as spec commit 99da930 (clarification 5, FR-007, US3 scenario 3, the
  assumption, T015-T019, quickstart section 3, plan, research R-06/R-07, traceability); check_spec and
  check_traceability clean; tree clean. Key budget was sufficient before any paid call. Worker waiting for the
  coordinator's word that the key is fixed; next step T016
  stage 1 (coolant set). Commits so far: ea13237, a8b9598, 7a143c2, 6b76457, ded6fb7, 99da930 (not pushed).
- 2026-11-23 After the author's "key fixed, Orca restarted": the coordinator's shell key returned 401 "API key
  expired". The OS has two OPENROUTER_API_KEY values: user scope = the old key (expired; identical to the shell's),
  machine scope = a different key (HTTP 200 on /api/v1/key, no expiry, with budget remaining). On
  Windows the user-scope value overrides the machine-scope one, so processes Orca starts (workers included) still
  get the expired key. The author's one test call, made with the machine-scope key: HTTP 200, google/gemini-2.5-flash
  via Google AI Studio, reply "OK" -- the guardrail now allows the model. Coolant stage not started:
  asking the author which key the run should use (keys never printed; compared by equality only).
- 2026-11-23 The author chose to remove the expired key: the coordinator deleted the user-scope OPENROUTER_API_KEY
  (verified 401 "expired" immediately before deleting). Now: user scope unset; machine scope = the valid key
  (HTTP 200 on /api/v1/key). New processes started after an Orca restart get the valid key. Waiting for the author
  to restart Orca; then re-check the key from a fresh shell and reopen the implementation worker
  (dispatch ctx_d1cdf6efcaea) for T016 stage 1 (coolant set).
- 2026-11-23 The author restarted Orca again. Fresh-shell check by the coordinator: the shell's OPENROUTER_API_KEY
  equals the valid machine-scope key, no user-scope override; /api/v1/key HTTP 200, no expiry, budget remaining.
  Implementation worker reopened
  (dispatch ctx_d1cdf6efcaea) to start T016: verify its own key first (stop on anything but 200), then coolant ->
  (all coolant criteria pass) outside -> (>= 12/14) 120-line, stop and report on any miss, the approved cap, a status
  message after each passing stage.
- 2026-11-23 Stage 1 (coolant set, iteration 10, tag 017-after) PASSED all four coolant criteria; worker continued
  to stage 2 (outside) without waiting. Key check from the worker's shell: HTTP 200, no expiry, budget sufficient
  before the first paid call; env check printed nothing. Majority per line: original eight 8/8 right,
  coolant-9 right (3403.99); wrong auto-accepts by majority per line 0 (override off and on). Per run (original
  eight): right 8/8/8, auto-accepted 1/1/1 (coolant-5), wrong auto-accepted 0/0/0, same with override on; all nine
  right 9/9/9. Flags: coolant-3 OK in every run (vague in all 15 runs before), route review (vote 2710.19 at 0.8);
  coolant-9 OK in every run, route review (vote 2710.19 at 0.6); coolant-1, -2, -8 vague and ask_shipper in every
  run; coolant-4..7 OK in every run. Only flag change vs iteration 9: coolant-3 vague -> OK. SC-001, SC-002, SC-007
  and SC-004's coolant half pass (52 s).
- 2026-11-23 Stage 2 (outside set, iteration 3, tag 017-after) PASSED SC-004; worker continued to stage 3 (120-line).
  Majority per line: 12/14 right (baseline 12/14), the same two lines wrong as in iteration 1 (FRBTIFR-BTI-2026-00308
  bike U-lock 8301.40 for 8301.10; DEBTI19155/25-1 watch 9102.99 for 9102.11); wrong auto-accepts by majority per
  line 1, the same U-lock line as the baseline (override off and on). Per run: right 12/12/12 (baseline 12/12/12),
  auto-accepted 8/8/8 (7/8/8), wrong auto-accepted 1/1/1 (0/1/1) -- the U-lock, which baseline run 1 had at 8301.50
  in review, is now 8301.40 and auto-accepted in all three runs; it is one of the 5 baseline-disagreeing (noise)
  lines and its label is contested between rulings (backlog item 10). No flag in any run, none changed.
- 2026-11-23 Stage 3 (120-line set, iteration 22, tag 017-after) PASSED SC-003; all three stages passed; the worker
  is writing eval-report.md and the backlog/README edits and committing. Majority per line, override off: top-1
  78/120 (baseline 77); wrong auto-accepts by majority per line 3, the same three lines as the baseline (BTI356,
  MTBTI2024-002, MTBTI2025-011). Override on: top-1 80 (80), same 3 lines. Per run off: right 78/77/78 (76/77/77),
  auto-accepted 63/64/62 (63/63/62), wrong auto-accepted 3/3/2 (3/3/3; MTBTI2024-002 to review in run 3); on: right
  80/79/80 (79/80/80), auto-accepted 65/66/65 (66/66/65), wrong 3/3/3 (3/3/3). Flags: 3 lines vague in every run
  (BTI572, BTI105, XIBTI505068566) vs 5 in the baseline -- two ENGLISH lines, IEBTIIENEN004-2025-BTI249 and
  IEBTIIENEN004-2026-BTI124, are no longer flagged in any run (BTI124 now routes to review with a different wrong
  top-1; BTI249 keeps its top-1). Line diff: 8 lines changed majority top-1 (3 baseline-disagreeing noise lines;
  BTI124 with its flag; 4 not attributable, flag unchanged: FRBTIFR-BTI-2025-02100, BTI261, BTI23 now right, BTI222
  now wrong). No failed line. Cost: within the approved budget for the three stages.
- 2026-11-23 Stage 4 done (worker_done, task_10db2dc16e50; report in chat-scratch .../feature-017-worker-report.md):
  24 of 24 tasks ticked (checked), branch at c6b3500 (not pushed): ea13237, a8b9598 (analyze: 1 HIGH + 3 MEDIUM
  fixed, 6 LOW listed), 7a143c2, 6b76457, ded6fb7, 99da930, c6b3500 (results, eval-report.md, backlog item 17,
  README). pytest -q 1774; check_spec 8 FR/7 SC; traceability 15/15. All SC pass; T018/T019 not triggered. Cost:
  within the approved budget.
  Spec-change list for the feature PR: SC-003 by majority per line; analyze fixes; staged approval; traceability.md
  and eval-report.md added.
- 2026-11-23 Stage 5: code review round 1 dispatched (claude, opus, read-only; task task_9ca076578f90, dispatch
  ctx_b36992a38f3f): diff 6c53063..c6b3500 against the spec, tests vs mutations, eval-report numbers recomputed,
  committed result files, traceability in PR mode with Spec-PR #14, secrets, line endings, the 6 LOW findings.

- 2026-11-23 Code review round 1: Opus reviewer hit a Claude session limit (resets 17:50 Berlin); stopped. Retried on opencode (Codex had no chat runtime; opencode started in terminal mode, ctx_5f7dc146c612, live, accepted input).

- 2026-11-23 Code review round 1 (coordinator, read-only, after three worker-agent infra failures): PASS. Product change is exactly the one Chinese sentence; all eval-report numbers recomputed from committed files; pytest 1774 passed / 4 deselected. One LOW finding: truncated comment at tests/unit/test_hs6_eval.py:743 ("auto-accepted, so wrong" dropped). Six worker-listed LOW findings are doc nits, none worth fixing (D1 already resolved).

- 2026-11-23 Pushed branch 017-coolant-vague-chinese-examples (696e78f..c6b3500) and opened PR #15: feat(017): Chinese vagueness-check examples (backlog item 17).

- 2026-11-23 PR #15 merged by the author (88248af). Backlog item 17's placeholder for the PR number filled in: main is
  PR-only, so the one-line edit went through PR #16 (ea951b9), merged by the author (b8e8ac7); local main fast-forwarded.

- 2026-11-23 Closed out (new coordinator session): run-use run_9166225754c7 (it was bound to the previous session, so
  task-update gave consumer_fenced), then task_9ca076578f90 blocked -> completed (coordinator review PASS). Every task
  of the run is completed; no worker is live. Left as-is: the feature worktree (like 014a's) and the LOW finding at
  tests/unit/test_hs6_eval.py:743 (still truncated on main).
