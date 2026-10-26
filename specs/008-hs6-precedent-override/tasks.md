---

description: "Task list for feature 008, the precedent override at the HS-6"
---

# Tasks: Precedent Override at the HS-6

**Input**: Design documents from `specs/008-hs6-precedent-override/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/override.md, quickstart.md

**Tests**: included and written first. The spec fixes the threshold behaviour (FR-013), and constitution Principle VII
requires test-first for guardrail code; routing is guardrail code. Each test task's new tests MUST fail before the task
that implements them.

**Organization**: tasks are grouped by user story, each independently testable. Paid eval runs (T021, T022) happen
only when the author asks. Every file keeps its line endings; all files named here are LF.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1 to US4 of spec.md)

---

## Phase 1: Setup

**Purpose**: the governance step and the pinned eval input that later phases need

- [ ] T001 The author runs `/speckit-constitution` with the 1.6.0 draft in specs/008-hs6-precedent-override/plan.md
  ("Draft for task A1"), amending Principle I in .specify/memory/constitution.md. No routing code (T006 onwards) is
  written before this lands: constitution 1.5.0 does not allow the override.
- [ ] T002 [P] Pin CN-8 iteration 12 for the HS-6 eval: copy tests/eval/cn8_eval.json byte for byte to
  tests/eval/cn8_eval_iteration12.json. That file is the CN-8 eval's iteration 12, Gemini 2.5 Flash, 3 runs, committed
  in `ce3bf02`. Check that `summary.iteration` is 12 and that `runs` has 3 entries.

---

## Phase 2: Foundational

**Purpose**: the switch, the schema additions and the rule itself, which every story needs

**CRITICAL**: no user story work starts until T006 is done.

- [ ] T003 [P] Write the routing tests first, in a new file tests/unit/test_hs6_override.py, following the `vote(...)`
  helper pattern of tests/unit/test_hs6_gate.py:
  - **`hs6_gate(confidence, threshold, vote, override_min)`**: every row of
    specs/008-hs6-precedent-override/contracts/override.md §1. 5 of 5 and 4 of 5 at candidate 2 or 3 give
    `(True, Hs6Gate.vote_override)` with `override_min=4`, and `(False, vote_disagrees)` with None. 3 of 5 gives
    `vote_disagrees` in both. 4 of 4, with only four eligible rulings, gives `vote_override`. 4 of 5 outside the top
    three gives `vote_disagrees`. A tie, a share below 0.5, no eligible ruling and an agreeing top candidate are
    unchanged.
  - **Switch off**: with `override_min=None`, every case equals today's `hs6_gate(confidence, threshold, vote)`.
  - **`route_line(..., hs6_vote=..., hs6_override_min=4)`**:
    - `vote_override` with ever_flagged False gives `(auto_accept, "rulings overrode the model: 4 of 5 agree on
      3926.90")`.
    - With ever_flagged True it gives `(review, "ready to accept — rulings overrode the model: 4 of 5 agree on
      3926.90, but the line was flagged or updated before; click Accept to confirm")`.
    - A vague or stop-word line with the same vote routes as today, never `auto_accept`.
  - **`hs6_auto_decided`**: passes `hs6_override_min` through.
  - **`hs6_choice(candidates, vote, gate)`**: returns `(2, candidates[1].code)` for `vote_override`, `(1,
    candidates[0].code)` otherwise, and `(None, None)` with no candidate.
  - **Fewer than three candidates** (the spec's edge case). With only two candidates, 4 of 5 rulings at the second
    give `vote_override`, and `hs6_choice` returns rank 2. 4 of 5 at a code the model did not return count as outside
    its candidates: `vote_disagrees`, no override.
- [ ] T004 [P] Add the switch in agent/config.py:
  - `OVERRIDE_MIN = 4` next to `HS6_VOTE_K`, with a comment: "feature 008: the rulings at the model's candidate 2 or 3
    that override its top HS-6; 1 ≤ OVERRIDE_MIN ≤ HS6_VOTE_K".
  - `Settings.hs6_override: bool = False`, read where the other `CARGOLINT_*` variables are read:
    `hs6_override=(e.get("CARGOLINT_HS6_OVERRIDE") or "off") == "on"`.
  - In tests/unit/test_chat_model.py, test the default off and "on", calling `get_settings.cache_clear()` around the
    monkeypatched environment.
- [ ] T005 [P] Extend agent/schemas.py:
  - `Hs6Gate.vote_override = "vote_override"`, with the comment "the majority is the model's candidate 2 or 3 with at
    least the shipment's hs6_override_min rulings; that candidate is decided".
  - `Shipment.hs6_override_min: int | None = Field(default=None, ge=1)`, to the data-model §2 rule: "None: the switch
    is off. Otherwise the agreeing rulings the override needs, 1 to HS6_VOTE_K".
  - A `field_validator` that rejects a value above `HS6_VOTE_K`, imported from agent/config.py. config.py imports
    nothing from the project, so there is no import cycle. The bound is checked against the constant, not a literal 5
    (data-model §9).
  - Tests in tests/unit/test_hs6_override.py: None and 4 are accepted; 0 and `HS6_VOTE_K + 1` are rejected with a
    pydantic `ValidationError`.
- [ ] T006 Implement the rule in agent/routing.py, exactly as contracts/override.md §1 states, until T003 passes:
  - `hs6_gate(..., override_min=None)`, with N from `vote.competing`;
  - `route_line(..., hs6_override_min=None)`, with both reason texts;
  - `hs6_auto_decided(..., hs6_override_min=None)`;
  - the new `hs6_choice(candidates, vote, gate)`.

  Every existing branch of `route_line` keeps its order: status, flags, CN-8 question and error, then the gate.
  Depends on T001, T003 and T005.

**Checkpoint**: the rule exists and is tested; with the switch off nothing changes.

---

## Phase 3: User Story 1 - Auto-accept the candidate the rulings agree on (Priority: P1) MVP

**Goal**: with the switch on, a line whose rulings agree 4 or 5 of 5 on the model's candidate 2 or 3 is
auto-accepted with that candidate as its decided HS-6, and the CN-8 step runs on it.

**Independent Test**: on a store opened with `hs6_override_min=4`, route lines with 5, 4 and 3 of 5 rulings at
candidate 2, a flagged line and an ever-flagged line, and check the routes, the decided codes and the CN-8 step's HS-6.
Repeat with the switch off.

- [ ] T007 [P] [US1] Write the store tests first in tests/unit/test_hs6_override.py (class `TestStore`), reusing
  `voted_line`-style setup from tests/unit/test_hs6_gate.py:
  - **Switch on**: `LineStore.new_shipment(hs6_override_min=4)` routes an unflagged line with 4 of 5 rulings at
    candidate 2 to `auto_accept`. Its `route_reason` is "rulings overrode the model: 4 of 5 agree on <code>", and
    `decided_code(line)` returns `(candidate 2's code, "auto")`.
  - **Switch off**: `hs6_override_min=None` gives `review` and `(None, None)`.
  - **Below the minimum**: 3 of 5 gives `review`.
  - **Flagged line**: never `auto_accept`.
  - **Ever-flagged line**: one updated through a shipper-reply version gives `review`, and `ready_to_accept(line)` is
    True.
  - **CN-8 step**: `tools.classify_cn8.run_cn8_step(store, kb, client, [n])` runs on the chosen candidate. The stored
    `v.cn8.hs6` equals candidate 2's code. Use the fake client pattern of
    tests/integration/test_classify_cn8.py.
  - **Export** (FR-014): `store.export_rows()` gives the overridden line `decided_code` = candidate 2's code and
    `decided_how` = "auto". The CSV columns are unchanged (`LineStore.CSV_COLUMNS`).
  - **Threshold moves** (the spec's edge case): after `set_threshold(60)` and `set_threshold(99)`, the overridden line
    is still `auto_accept`, with the same decided code.
  - **Fewer than three candidates**: a line with only two candidates and 4 of 5 rulings at the second is decided with
    the second.
- [ ] T008 [US1] Implement the store part in agent/store.py until T007 passes:
  - `new_shipment(..., hs6_override_min: int | None = None)` stores the value on the Shipment.
  - `_recompute`, `_hs6_auto_decided` and `ready_to_accept` pass `self.shipment.hs6_override_min` to `route_line`,
    `hs6_auto_decided` and `hs6_gate`.
  - `v.hs6_gate` is set from the same call.
  - `decided_code` returns the code `hs6_choice(v.candidates, v.hs6_vote, v.hs6_gate)` gives for an auto-decided line;
    a clerk's decision still wins.

  Depends on T006.
- [ ] T009 [US1] Set the switch when a shipment opens, in ui/upload.py `open_shipment`: pass
  `hs6_override_min=OVERRIDE_MIN if get_settings().hs6_override else None` to `store.new_shipment`. Test it in
  tests/ui/test_main_page.py through the harness: with `CARGOLINT_HS6_OVERRIDE=on` (monkeypatched, with
  `get_settings.cache_clear()`), a newly opened shipment has `hs6_override_min` 4, and by default None. Depends on T008.

**Checkpoint**: US1 works on its own: overridden lines are decided and their CN-8 step runs on the chosen candidate.

---

## Phase 4: User Story 2 - See which candidate was chosen, and why (Priority: P1)

**Goal**: the detail row and the audit trail show the chosen candidate, the model's top candidate and the note.

**Independent Test**: on an overridden line, read the "Decided:" line, the ready-to-accept texts of an ever-flagged
one, and the audit entries; compare them with an ordinary auto-accepted line.

- [ ] T010 [P] [US2] Write the audit tests first in tests/unit/test_hs6_override.py (class `TestAudit`). When the
  override decides a line, `store.shipment.audit` holds two entries:
  - a `route_computed` entry whose note is the route reason;
  - a `code_decided` entry with `actor` routing_rule, `previous` = the top candidate, `new` = the chosen code, and the
    note "rulings overrode the model: 4 of 5 agree on <code>; candidate 2 chosen".

  Each entry appears exactly once, still after a later recompute such as `set_threshold(80)`.

  **A clerk's change** (FR-011): on the overridden line, call `store.set_decision(n, Decision(route=accepted,
  decided_code=<the model's top candidate>))`. Then `decided_code` returns the clerk's code with `chosen_how` top. The
  clerk's new `code_decided` entry (actor clerk) has `previous` = candidate 2's code, the code in force before the
  change, not the model's top candidate, and `new` = the clerk's code (contracts §3).
- [ ] T011 [P] [US2] Write the view tests first in tests/unit/test_view.py, with the texts exactly as in
  contracts/override.md §2:
  - **"Decided:" line**: `explain_a(store, line, "a_change")[0]` holds "candidate 2 chosen, rulings overrode the model:
    4 of 5 agree on <spaced code> (IE, DE, DE, FR); the model's top candidate was <spaced top>". The countries are those
    of the agreeing rulings in the vote. After `confirm_cn8` it ends with ", accepted by you".
  - **Ever-flagged override line**:
    - `line_status(store, line).text` is "Confirm: <spaced chosen code>";
    - `explain_a(store, line, "a_hs6")[1]` is "Candidate 2, <spaced code>, is chosen because the rulings overrode the
      model (4 of 5 agree on it: IE, DE, DE, FR), but this line was flagged before its update, so it needs your
      confirmation. TARIC runs after your pick.";
    - `preselect(store, line, "a_hs6", "hs6")[0]` is the chosen code.
  - **Code column**: shows the chosen candidate.
- [ ] T012 [US2] Write the audit entries in agent/store.py, until T010 passes:
  - in `_recompute`, when the gate becomes `vote_override` and the route changed, append the `code_decided`
    `DecisionRecord` of data-model §6;
  - in `set_decision`, the clerk's `code_decided` entry takes `previous` from `self.decided_code(line)[0]` when a code
    is decided, and from `v.top_code` otherwise (contracts §3). Every line without an override is recorded as today.

  Depends on T008.
- [ ] T013 [US2] Implement the texts in ui/view.py, until T011 passes:
  - the `vote_override` branch of `_hs6_how`, with the agreeing rulings' issuing countries taken from
    `v.hs6_vote.competing` and joined as `_hs6_rulings` joins them;
  - `_review_text` and `preselect` (form "hs6", kind other than `a_change`) use `hs6_choice(...)` when the gate is
    `vote_override`;
  - the ready-to-accept branch of `explain_a` (`a_hs6`, gate passed) gets the override wording.

  All texts are plain strings (constitution Principle VI). Depends on T008.
- [ ] T014 [US2] Add a page test with an overridden line:
  - in tests/ui/harness.py, a `build_state` state "hs6_override": three candidates; an `Hs6Vote` with 4 of 5 rulings
    at candidate 2 (`candidate=2`); a store opened with `hs6_override_min=4`; and the CN-8 and TARIC helpers, so the
    line is Ready;
  - in tests/ui/test_main_page.py, a test of the seeded line:
    - the row is green and the code column shows candidate 2's code;
    - the expanded row's "Decided:" line holds the override text;
    - the store's audit trail holds the override's `code_decided` entry with the note (spec SC-004).

  Depends on T012 and T013.

**Checkpoint**: US1 and US2 together: overrides are decided, visible and audited.

---

## Phase 5: User Story 3 - A hint when the rulings agree on a code the model did not propose (Priority: P2)

**Goal**: with the switch on, 4 or more of 5 rulings at a code outside the top three leave the line in review, with a
hint that names the code.

**Independent Test**: a line whose rulings sit 4 of 5 outside the top three gets the hint, stays in review and keeps
the top candidate pre-selected; 3 of 5 and the switch off show no hint.

- [ ] T015 [P] [US3] Write the tests first in tests/unit/test_view.py, with the switch on and gate `vote_disagrees`:
  - **4 of 5 at a code outside the top three**: `explain_a(store, line, "a_hs6")[1]` is today's "Rulings disagree: …"
    line followed by " Hint: 4 of 5 nearest rulings agree on <spaced code>, which is not among the candidates.". The
    route stays `review`, and `preselect` stays the top candidate.
  - **No hint**: with 3 of 5 outside, and with the switch off.
  - **Unchanged**: a majority at candidate 2 with 3 of 5 still reads "… Precedents support candidate 2. …".
- [ ] T016 [US3] Implement the hint in ui/view.py `explain_a`, in the `a_hs6`, `vote_disagrees` branch. It reads
  `store.shipment.hs6_override_min` and the counts from `_hs6_votes`, until T015 passes. Depends on T013, which edits
  the same file.

**Checkpoint**: US3 works; the screen with the switch off equals today's.

---

## Phase 6: User Story 4 - Measure the override on and off (Priority: P2)

**Goal**: both evals record the chosen candidate, whether the override fired and whether the supported candidate was
right. Each derives the switch-off result from its one paid run.

**Independent Test**: offline, a stored run yields both states, and on override lines only the override fields and
what follows from them differ; the reports show on against off.

- [ ] T017 [P] [US4] Write the HS-6 eval tests first in tests/unit/test_hs6_eval.py:
  - **Row fields**: a row with `top3`, `vote.counts` and `vote.candidate` gets `supported = {"rank": 2, "right":
    candidate 2 == expected}` and `on = {"gate": "vote_override", "route": "auto_accept", "rank": 2, "chosen":
    candidate 2's code, "hit": …}` when 4 of 5 rulings sit at candidate 2. The row's existing fields stay the
    switch-off result.
  - **Measures**: per state, the chosen HS-6 right, the wrong auto-accepts, the overrides that fired and how many were
    right, and the cross-layer end-to-end estimate on the chosen HS-6.
  - **Report**: `render_report` shows a "Precedent override" section with off against on.
- [ ] T018 [US4] Implement in tests/eval/hs6_eval.py, until T017 passes:
  - the row fields `vote.counts`, `supported` and `on`, computed with the routing functions at `OVERRIDE_MIN`
    (data-model §8);
  - the `on` measures, and `cross_layer` on the chosen HS-6;
  - the history entry's `override_min`, its `on` block, and the override counts;
  - the report section;
  - a docstring paragraph for feature 008.

  The paid run stays one run; nothing calls the model twice. Depends on T006.
- [ ] T019 [P] [US4] Write the end-to-end eval tests first:
  - **Unit test**, in tests/unit/test_e2e_eval.py. The switch-off replay of an override row sets `hs6` to the top
    candidate by the clerk, `cn8` to `cn8_top1`'s code, and the route to `review`, with hit and origin recomputed. A
    row without an override is identical in both states. The measures and report show on against off, and the lines
    that differ.
  - **Integration test**, in tests/integration/test_e2e_eval.py, as a test of its own with its own one-line fake set,
    rulings and recorded answers. The existing five-line test and its expectations (2 right, the route counts) stay
    unchanged. The line's top candidate is 9503.00 (95), and its candidate 2, 3926.90 (60), holds 4 of its 5 nearest
    rulings. With the switch on, `run_once` overrides it to 3926.90 and auto-accepts it. Its `cn8_top1` holds a CN-8
    answer under 9503.00, and its `off` block is review. The line's own ruling never reaches the extra CN-8 prompt.
- [ ] T020 [US4] Implement in tests/eval/e2e_eval.py, until T019 passes:
  - `run_once` opens its shipment with `hs6_override_min=OVERRIDE_MIN`.
  - After the upload's CN-8 step, for every line whose `hs6_gate` is `vote_override`, run the CN-8 step under the top
    candidate, as `cn8_step` does (`classify_cn8_lines` per line, `exclude_refs` and the set's date), without writing
    to the store.
  - `line_row` adds the `override`, `supported`, `cn8_top1` and `off` blocks of data-model §8.
  - The measures run on both states.
  - The history entry and report show on and off, and the lines that differ.
  - Add a docstring paragraph for feature 008.

  Depends on T008.
- [ ] T021 [US4] Paid run, only when the author asks: `python tests/eval/hs6_eval.py --repeat 1 --tag hs6-override
  --cn8 tests/eval/cn8_eval_iteration12.json`. From tests/eval/hs6_eval.md, read SC-002 (wrong auto-accepts, on ≤ off),
  SC-003 (end-to-end estimate, on > off) and SC-006. Depends on T002 and T018.
- [ ] T022 [US4] Paid run, only when the author asks: `python tests/eval/e2e_eval.py --repeat 1 --tag e2e-override`.
  From tests/eval/e2e_eval.md, read SC-001 (right end to end, on > off), SC-002, SC-004 (every override row's route
  reason holds the note) and SC-006. Depends on T020.

**Checkpoint**: all four stories are done; the switch decision has its evidence.

---

## Phase 7: Polish and Cross-Cutting Concerns

- [ ] T023 [P] Correct features 001 and 004, doc only (plan task A2 and the 1.6.0 consistency review). Add the
  override wording of specs/008-hs6-precedent-override/plan.md ("…or, when the precedent override (feature 008,
  switched on) decided it, the second or third candidate on which at least OVERRIDE_MIN of the five nearest eligible
  rulings agree").
  - **specs/001-packing-list-check/spec.md**:
    - the vocabulary paragraph's "decided code";
    - FR-020: add the override case to "OK → auto-accept when the HS-6 gate accepts the top candidate", and make the
      last sentence "An auto-accepted line's decided code is its top candidate, or the candidate the precedent
      override chose";
    - US1 acceptance scenario 3, "whose top candidate the HS-6 gate does not accept …": add to the condition "and,
      with the precedent override switched on, fewer than OVERRIDE_MIN of the rulings sit at its second or third
      candidate";
    - US2 acceptance scenario 5, "(the top candidate is preselected; …)": "(the top candidate is preselected, or, on
      a line the precedent override decided, the candidate it chose; …)".
  - **specs/001-packing-list-check/data-model.md**:
    - footnote ¹ of §9: add the override and the hint, with the switch on;
    - the `ready_to_accept` definition, "the HS-6 gate passes — since constitution 1.5.0 the ruling vote, …": add
      "since 1.6.0 also the precedent override, when switched on";
    - the invariant "the decided code is the top candidate with `chosen_how=auto` (FR-020)": "the top candidate, or
      the candidate the precedent override chose, with `chosen_how=auto` (FR-020)".
  - **specs/004-cn8-taric-classification/data-model.md**, "HS-6 decided": the helper's signature
    `hs6_auto_decided(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor)` gains `hs6_vote`
    (missing since feature 006) and `hs6_override_min` (feature 008).

  Depends on T001.
- [ ] T024 [P] Update feature 005's view contract to the current texts, doc only (the author's addition), in
  specs/005-decision-first-ui/contracts/view.md. Copy every text from ui/view.py as implemented, so that the contract
  equals the code.
  - **§2.2**: "Confirm: {top HS-6}" becomes "Confirm: {decided HS-6}", the chosen candidate when the precedent override
    decided the line.
  - **§5, `explain_a`, second line**: add feature 006's ruling-vote lines.
    - For `a_hs6`:
      - "Rulings disagree: model {top}, nearest rulings {codes with issuing countries}.[ Precedents support candidate
        {n}.] TARIC runs after your pick."
      - "Rulings split: model {top}, nearest rulings {…}. TARIC runs after your pick."
      - "Rulings too spread: model {top} has {n} of {m} nearest rulings; {…}. TARIC runs after your pick."
    - For `a_cn8`: the same three lines with the CN-8.
    - Replace the CN-8 below-threshold line with "CN-8 to confirm: no ruling vote, and its model estimate ({conf} %)
      is under the {threshold} % threshold. TARIC runs after your pick."
  - **§5, `{how}` table**:
    - HS-6: "auto-accepted, {n} of {m} nearest rulings agree" (vote); "auto-accepted at {conf} %" (no ruling vote);
      each with ", accepted by you".
    - CN-8: "written by rule, {n} of {m} nearest rulings agree" (vote); "written by rule at a model estimate of {conf}
      %" (no ruling vote).
  - **The override texts** of specs/008-hs6-precedent-override/contracts/override.md §2: the HS-6 `{how}` "candidate
    {rank} chosen, …", the ready-to-accept line, and the hint.

  Depends on T013 and T016.
- [ ] T025 Update README.md:
  - the routing summary: the precedent override, its switch `CARGOLINT_HS6_OVERRIDE` (off by default) and
    `OVERRIDE_MIN`;
  - the end-to-end paragraph: the on and off results of T021 and T022.

  Depends on T021 and T022.
- [ ] T026 Run `pytest -q` (offline; the suite must pass) and the offline checks of
  specs/008-hs6-precedent-override/quickstart.md §1. Confirm that every edited file kept its line endings (count CR
  bytes with Python, as CLAUDE.md notes).
- [ ] T027 The switch decision (FR-007), by the author. If T021 and T022 meet SC-001 to SC-003, the default is turned
  on (`Settings.hs6_override` default, or `CARGOLINT_HS6_OVERRIDE=on` where the app runs); otherwise it stays off. The
  README records the decision. Depends on T021 and T022.

---

## Dependencies and Execution Order

### Phase dependencies

- **Setup (T001, T002)**: T001 is the author's step and blocks all routing code. T002 is independent.
- **Foundational (T003–T006)**: T006 needs T001, T003 and T005; it blocks every user story.
- **US1 (T007–T009)**: after T006.
- **US2 (T010–T014)**: after T008, from US1. US2 builds on the store's decided code.
- **US3 (T015–T016)**: after T013, which edits the same file.
- **US4 (T017–T022)**:
  - T018 after T006;
  - T020 after T008;
  - the paid runs T021 and T022 only when the author asks.
- **Polish (T023–T027)**:
  - T023 after T001;
  - T024 after T013 and T016;
  - T025 and T027 after the paid runs;
  - T026 last before the commit.

### Within each story

The tests are written first and fail; then the implementation makes them pass. The store comes before the view.

### Parallel opportunities

- T002 alongside T001.
- T003, T004 and T005 together: three different files.
- T007 and T010 both go in tests/unit/test_hs6_override.py, so they are sequential with each other, but each runs
  alongside T011 in test_view.py.
- T017 and T019, the eval tests, together; also alongside US2 and US3 once T008 is done.
- T023 and T024, both doc only, together.

---

## Parallel Example: User Story 4

```bash
# The eval tests, together (different files):
Task: "T017 HS-6 eval on and off tests in tests/unit/test_hs6_eval.py"
Task: "T019 end-to-end eval on and off tests in tests/unit/test_e2e_eval.py and tests/integration/test_e2e_eval.py"

# Then the two eval implementations, together (different files):
Task: "T018 tests/eval/hs6_eval.py"
Task: "T020 tests/eval/e2e_eval.py"
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. T001 (the author's `/speckit-constitution`) and T002.
2. Phase 2: the rule and its tests.
3. Phase 3: the store and the switch. With the switch on, overridden lines are decided and their CN-8 runs.
4. Stop and validate: `pytest -q`. The product is unchanged by default, since the switch is off.

### Incremental delivery

1. US2: the texts and the audit. The override is now visible, so the switch could be tried in the app.
2. US3: the hint.
3. US4: the evals, then the paid runs when the author asks, then the switch decision (T027).
4. Polish: the feature 001 and feature 005 docs, the README, the full suite.

---

## Notes

- [P] tasks use different files and have no unfinished dependency.
- Commit and push only when the author asks (CLAUDE.md).
- The live evals spend credits: T021 and T022 run only on the author's word, each with `--repeat 1`.
