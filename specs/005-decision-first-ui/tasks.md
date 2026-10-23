---

description: "Task list for the decision-first clerk workflow (UI redesign)"
---

# Tasks: Decision-First Clerk Workflow (UI Redesign)

**Input**: Design documents from `/specs/005-decision-first-ui/`

**Prerequisites**:
- plan.md (required) and spec.md (required for user stories);
- research.md (R-01 to R-18), data-model.md and quickstart.md;
- contracts/: ui.md, view.md and backend.md;
- `.specify/memory/constitution.md` (v1.3.0).

**Tests**: REQUIRED.
- **Why**:
  - the constitution (Principle VII) requires tests first for guardrail code: the clerk's edit (caps, lock, audit) and
    the single-line re-check;
  - the spec asks for a test of every status-mapping row (SC-004), of both emails (SC-006) and of each behaviour listed
    in SC-007, and for measured response times (SC-002).
- **Order**: every test task is written first and must fail before its implementation task starts.
- **Offline**: no network and no key.
  - `FakeRawClient` (through `agent.llm.set_client_factory`) and `ScriptedChatModel` (through `set_chat_model_factory`)
    replace the model.
  - The pages are tested with `streamlit.testing.v1.AppTest`.
- **Baseline**: 710 tests are collected before this feature, with 4 live tests deselected.
  - The 683 that do not import the UI package must pass unchanged at every checkpoint (SC-007).
  - Of the 27 that import it, 13 are deleted with the modules they test, and the new tests replace them:
    tests/unit/test_review_table.py (9) and tests/unit/test_sidebar_caption.py (4).
  - The other 14 stay unchanged: tests/adversarial/test_fencing_coverage.py (7), tests/integration/test_upload_flow.py (3)
    and tests/unit/test_message_classification.py (4).

**Organization**: tasks are grouped by user story, so each story is an independently testable increment. The shared
foundation is the view module's status mapping, the test harness and the job runner.
- **US1**: see the decision each line needs (the MVP).
- **US2**: pick a code in place, and "Change" on green rows.
- **US3**: ask the shipper, update and re-check, with the backend addition.
- **US4**: accept the ready lines and export.
- **US5**: the shipper email.
- **US6**: the origin.
- **US7**: the Admin page.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1 … US7)
- Include exact file paths in descriptions

## Path Conventions

- **Layout**: the single project at the repository root: `app.py`, `agent/`, `tools/`, `rag/`, `ui/`, `tests/`.
- **Imports**:
  - `ui/view.py`, `ui/shipper_email.py` and `ui/actions.py` never import Streamlit;
  - the UI never calls the model or the retrieval itself, only `agent/` functions inside background jobs;
  - the worker thread never calls Streamlit.
- **CRLF files**: `app.py`, `ui/chat.py` and `ui/upload.py` use CRLF, as do `ui/detail.py` and `ui/review.py` until
  T016 deletes them. Every new file uses LF. Keep each file's line endings.
- **Browser checks**: the Streamlit server never reloads `ui/*.py`; restart it before any browser check.
- **Exact texts**: every text the pages show comes from contracts/view.md and contracts/ui.md, and the tests assert
  those texts.
- **Unchanged files**: `agent/routing.py`, `agent/taric_rules.py`, `agent/prompts.py`, every module in `tools/` and
  `rag/`, and `ui/replies.py` are not edited. The only backend edits are T027 and T028 (contracts/backend.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the baseline and the page-test harness that every story's tests use.

- [ ] T001 Run `pytest -q` before any change and confirm 710 passed with 4 deselected. T052 compares against it.
- [ ] T002 [P] Create tests/ui/__init__.py (empty) and tests/ui/harness.py:
  - **`make_kb(taric=True)`**: a `KnowledgeBase` like the `kb` fixture of tests/integration/test_agent_check_flow.py:
    - the small index (tests/fixtures/cn2026_excerpt.jsonl), with BM25 and in-memory vectors over `FakeEmbeddings(dim=16)`;
    - a `BTIStore` of two synthetic rulings, one under 9503.00 and one under 8714.91;
    - the rules of tests/fixtures/rules, and `meta` with `built_at` "2026-10-15T00:00:00";
    - `taric=TaricStore.from_jsonl(tests/fixtures/taric/snapshot_small.jsonl)`, or None.
  - **`store_with(*states, origin="CN")`**: a `LineStore` on the small index, with the reference "INV-TEST" and one line
    per named state.
    - **How**: only through store methods (`add_lines`, `add_version`, `update_check`, `update_classification`,
      `update_precedents`, `set_decision`, `set_cn8_result`, `confirm_cn8`, `set_taric_result`, `confirm_taric10`,
      `mark_failed`), never by assigning fields. Each state's text is fixed, so tests can read it.
    - **Pending, failed and red**:
      - `pending` and `failed`;
      - `stop_word`: the ICS2 stop word "spare parts";
      - `vague_close` (41/39/12, below the ask floor), `vague_apart` (40/10/5) and `vague_review` (62, at or above the
        ask floor);
      - `cn8_question`: 9503.00, "whether the toy cars incorporate a motor";
      - `sent`: the clerk's ask-shipper decision; `taric_question`.
    - **Yellow**:
      - `cn8_error`;
      - `review` (58 %);
      - `ready_to_accept`: a flagged version, then a shipper-reply version OK at 91 %;
      - `no_candidate`, `unreadable`;
      - `cn8_missing`: the HS-6 decided, no CN-8 choice;
      - `cn8_pending`: a suggestion below the threshold;
      - `taric_missing`: a written CN-8 with no TARIC outcome;
      - `taric_two`: 7318 15 58 for CN;
      - `taric_many`: a stored outcome with 9 subdivisions, 3 under trade defence;
      - `taric_one_td`: 7318 15 68 for CN, a control measure.
    - **Green**:
      - `ready`: 9617.00 auto-accepted, a single CN-8 line, TARIC not available;
      - `ready_taric`: 7318 15 68 with origin US, a single subdivision auto-completed;
      - `ready_not_loaded`;
      - `accepted`: `ready` after the clerk's `confirm_cn8`;
      - `accepted_taric`: `taric_two` after the clerk's `confirm_taric10` of 7318 15 58 10, so its CN-8 has two
        subdivisions.
  - **`sample_store(kb)`**: the 12-line sample checked offline, as tests/integration/test_upload_flow.py does:
    - the sample workbook registered;
    - `ScriptedChatModel` scripting the six tool calls;
    - the recorded outputs of tests/fixtures/recorded.
  - **`JobRecorder`**: replaces `ui.jobs.start` (monkeypatch), so a test records each `Job` without a thread.
    - `.keep_running()` leaves the last job running, for the "Running …" texts.
    - `.run(store, kb)` runs a recorded job inline with the fake client when a test needs its effect.
  - **`ModelGuard`**: installs a counting `FakeRawClient` (the recorded outputs) and a `ScriptedChatModel`. `.calls` counts
    both, and the factories are restored on exit.
  - **`page(name, store, kb)`**: an `AppTest.from_function` script with `default_timeout=10`. It renders
    `ui.main_page.render(store, kb, None)` or `ui.admin.render(store, kb, None)` with the harness's current objects. The
    other page is None, so no `st.page_link` is rendered; tests/ui/test_app_navigation.py checks the links.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the status mapping every page renders (contracts/view.md §1 to §3), and the job runner both pages use
(contracts/ui.md §6).

**CRITICAL**: no user story work can begin until this phase is complete.

### Tests for the foundation (write FIRST, ensure they FAIL)

- [ ] T003 [P] Create tests/unit/test_view.py with the status mapping (contracts/view.md §1 to §3, §8):
  - **Mapping (SC-004)**: one test per row of §1, on the harness states. Each asserts the colour, text, action, kind,
    `selectable`, `lock_reason` and `question`:
    - **rows 1 and 3**: `activity="running"` gives "Running stop-word check…", "Running HS-6 step…", "Running CN-8 step…"
      and "Running TARIC step…"; `"queued"` gives "Queued: CN-8 step"; a pending line with no activity reads "Not checked
      yet";
    - **rows 2 and 4 to 6**: red, "Update", kind `c` or `c_failed`, with the texts and lock reasons of §2.1;
    - **rows 7 to 12**: yellow, "Choose", with the texts of §2.2:
      - kind `a_cn8`: "Pick: CN-8, 19 lines" and "Confirm: 9503 00 95" (the TARIC step missing);
      - kind `a_hs6`: "Pick: 3 candidates", "Confirm: 9503 00" (ready to accept), "Pick: no candidate" and "Pick:
        unreadable line";
      - kind `b`: "Pick: 10 or 90", "Pick: 9 options, 3 AD" and "Confirm: 7318 15 68 00";
    - **row 13**: green, "Ready" (selectable) or "Accepted", the action "Change" and the kind `a_change`;
    - a running activity on a line with nothing left to run shows the line's own status;
    - the kind is one of "`a_hs6`, `a_cn8`, `a_change`, `b`, `c`, `c_failed` or none", and the action one of "`Choose`,
      `Update`, `Change` or none" (data-model §1).
  - **SC-003**: no status text equals "Review" or "Needs action", or contains "to confirm".
  - **Short texts**: at most 44 characters; a long CN-8 attribute is cut with "…".
  - **`next_step`**: each of its four answers, and None.
  - **`code_display`** (FR-008):
    - "____ __ __ __", "9503 00 __ __", "8714 91 10 __" and "7318 15 58 10";
    - "9617 00 00" with the note "TARIC not available", and the same with "TARIC not loaded";
    - a CN-8 or TARIC-10 suggestion fills no digit.
  - **`md_escape`**: "[click](https://x.test)" and "*bold* _it_ `code`" come back with every Markdown character
    escaped; Chinese text is unchanged.
  - **`split_description`**: "不锈钢保温杯 / Stainless steel vacuum flask" gives both parts; English only gives
    ("", text); Chinese only gives (text, "").
- [ ] T004 [P] Create tests/unit/test_runner.py for the runner's pure parts (contracts/ui.md §6), with no Streamlit
  session:
  - **`activity(job, queue, line_no)`**:
    - a running `check` covers every line;
    - a running `finer_codes` covers its line only;
    - a queued `finer_codes` entry gives "queued";
    - no job and an empty queue give None.
  - **`fail_pending(store, job)`**:
    - a `check` job with an error calls `finalize_check`, so every pending line reads failed with "not checked — a step
      did not run";
    - a `finer_codes` error changes nothing in the store;
    - a job without an error changes nothing.

### Implementation for the foundation

- [ ] T005 Create ui/view.py, with no Streamlit import, holding the foundation of contracts/view.md:
  - `LineStatus` and `CodeDisplay` as frozen dataclasses (data-model §1);
  - `next_step`, `line_status`, and the red, yellow and running texts of §2 with the lock reasons;
  - `question(store, line, lang)`, with the English and Chinese texts of §7.3;
  - `code_display`;
  - `md_escape`;
  - `split_description`, with `tools.parsers.split_mixed`, as ui/chat.py's `_zh` and `_en` do;
  - the spaced-code helper.

  It reads the store only through the methods named at the top of contracts/view.md, and through
  `tools.lookup_taric.needs_taric`. T003 passes.
- [ ] T006 Create ui/runner.py, and adapt ui/jobs.py, ui/chat.py (CRLF) and ui/detail.py (CRLF) (contracts/ui.md §6,
  research R-15):
  - **Move** `queue_finer_codes`, `_start_queued_finer_codes` and `_finish_job` from ui/chat.py to ui/runner.py, as
    `queue_finer_codes`, `start_next` and `finish`. `finish` still adds the chat record of each check, reply and
    question, with its steps, sources and notes.
  - **Queue**: `job_queue` replaces `finer_codes_queue`. Its entries are `("finer_codes", line_no, taric_only)` and, from
    T014, `("check", text)`.
  - **Add**:
    - `start_check(store, kb, *, file_ref=None, line_nos=None)`;
    - `activity` and `fail_pending` (T004);
    - in `finish`, a call to `fail_pending`, and one `st.error`: "The check did not finish: {error}", or "Line {n}:
      {step} did not finish: {error}".
  - **Keep in ui/chat.py**: `_start`, `handle_message` and `classify_message`, unchanged. Its live turn calls
    `runner.finish`. tests/adversarial/test_fencing_coverage.py reads `_start`'s history line.
  - **Keep the old UI running until T015**: ui/detail.py imports `queue_finer_codes` from ui.runner.
  - **ui/jobs.py** stays free of Streamlit.

  T004 passes, and the 14 kept UI tests pass unchanged.

**Checkpoint**: `pytest -q` green (710 + the new tests); the old UI still runs.

---

## Phase 3: User Story 1 - Check an invoice and see the decision each line needs (Priority: P1) 🎯 MVP

**Goal**: the main page:
- the header and the empty state;
- a check of a file, the sample or one typed line;
- the table, whose codes and statuses fill in live;
- the summary bar.

It covers FR-001 to FR-013 without the expanded content, "+ Check one more line" (FR-018) and FR-029 for these actions.

**Independent Test**: T007 to T009 pass; then the two US1 rows of quickstart §3 in the browser.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [ ] T007 [P] [US1] Add summary tests to tests/unit/test_view.py (contracts/view.md §4, §8):
  - **`summary`** on a store holding every mapping state: ready, pick, ask, failed, running, to_accept.
  - **`summary_text`**:
    - "12 lines checked in 19 s · 6 ready · 2 need a pick · 4 need the shipper";
    - " · 1 check failed" and " · 2 updating", only when above 0;
    - the singular forms "1 line checked", "1 needs a pick" and "1 needs the shipper".
  - **`seconds`**: the sum over the check runs whose steps include `check_description`. A run without it, such as a chat
    question, adds nothing.
  - **`split_bar`**: 60 blocks; green, yellow, red (ask and failed), grey in that order; each non-zero count at least
    one block; empty parts left out.
  - **`invoice_id`**: the reference, else the shipment id.
  - **`snapshot_caption(kb)`**: "TARIC snapshot {date}", or "TARIC not loaded".
  - **`kb_statement(kb)`**: today's knowledge-base caption, with "updated 2026-10-15".

  These replace tests/unit/test_sidebar_caption.py.
- [ ] T008 [P] [US1] Create tests/ui/test_main_page.py with the US1 tests (AppTest through tests/ui/harness.py, with
  `JobRecorder` and `ModelGuard`):
  - **Empty state** (FR-001, FR-003):
    - "CargoLint", and the origin field reading "CN";
    - the drop zone, labelled "Drop a packing list or invoice here", with the caption "XLSX · CSV · PDF · JPG · PNG — up
      to 20 MB, one file per shipment";
    - "Try the sample invoice";
    - "Check one line", with its placeholder and `max_chars` 300;
    - "No lines yet — drop a file or type one description".
  - **Nothing from FR-002**: no sidebar element, no chat input, no slider, no "Tokens" or "Cost" text, and no progress
    bar or "%" in a table row.
  - **The table** (FR-007 to FR-011), on `store_with` of every mapping state:
    - rows in file order;
    - the code as inline code, with its note;
    - the dot and the status text;
    - "Choose", "Update" or "Change", and no action on grey rows;
    - descriptions escaped.
  - **Opening a row** (FR-013):
    - the description or the action sets `selected_line_no`;
    - the bordered container with "▲ close" renders under that row, and choosing it again closes it;
    - a grey row does not open.
  - **Live check** (FR-004): while a recorded check job runs, every pending line reads "Running stop-word check…" with a
    grey dot, and the summary reads "Checking 12 lines… · {n} s".
  - **Summary** (FR-005): the sentence and the bar once the check has finished.
  - **Starting checks**:
    - "Try the sample invoice" starts one `check` job with the sample's file reference and the reference
      "HOL-2026-10-0472", and empties the chat;
    - "Check one line" adds one `CreatedBy.paste` line to a new shipment and starts its check;
    - while a job runs, a typed line waits ("Waits for the running check") and is added only when its check starts;
    - "+ Check one more line" shows its field and adds the line to the open shipment.
  - **Replacing**: with lines open, the sample asks "A checked shipment is open. Replace it with
    sample_packing_list.xlsx? Results, counts and cost reset." "Replace" adds the old shipment's usage to
    `session_usage`.
  - **Model calls**: none, in any of these actions.
- [ ] T009 [P] [US1] Create tests/ui/test_app_navigation.py, with `AppTest.from_file("app.py")`. Patch
  `rag.loader.open_knowledge_base` to return `make_kb()`, and `agent.config.get_settings` to return settings with a test
  key:
  - the default page is the main page, with a `page_link` node "Admin ⚙";
  - the navigation is hidden: no page list;
  - without a key, the page shows "OPENROUTER_API_KEY is not set. Set it as an operating-system environment variable
    and restart CargoLint." and stops. The text does not contain ".env" (contracts/ui.md §1).

### Implementation for User Story 1

- [ ] T010 [P] [US1] Add the following to ui/view.py:
  - `Summary` (data-model §1), `summary`, `summary_text`, `split_bar`, `invoice_id` and `snapshot_caption`, with the
    button labels of contracts/view.md §4;
  - `kb_statement(kb)`, moved from `kb_caption` in ui/sidebar.py.

  T007 passes.
- [ ] T011 [P] [US1] Rewrite ui/upload.py (CRLF) for the main page (contracts/ui.md §2):
  - **Elements**:
    - the drop zone with its label and caption, the caps checked first with `check_caps` as today;
    - "Try the sample invoice";
    - the replacement question with "Replace" and "Cancel".
  - **`begin(store, data, name, reference=None)`**:
    1. add the old shipment's usage to `session_usage`;
    2. open a shipment with the Admin `threshold` and `hybrid` values, and as reference `SAMPLE_REFERENCE` for the
       sample, else the file name without its extension;
    3. register the file, and start the check with `runner.start_check(file_ref=…)`;
    4. empty `chat`, and set `selected_line_no` to None.
  - **Remove**:
    - the shipment fields: reference, shipper and filing type (FR-002);
    - the compatibility `render`;
    - the `ui.review` import.
  - **Keep** `needs_confirmation`, `start_shipment_from_parsed` and `busy`; tests/integration/test_upload_flow.py uses
    them.
- [ ] T012 [P] [US1] Create ui/table.py (contracts/ui.md §4):
  - **Headers**: "✓ · # · Description · Code · Status · Action".
  - **Rows**: one `st.columns` row per line, from `view.line_status` (with `runner.activity`) and `view.code_display`:
    - the ✓ cell is empty for now (T031, T035);
    - the description is an escaped tertiary button, or plain text on grey rows;
    - the code is inline code, with its note as a caption;
    - the dot and the status text;
    - the action button.
  - **Paging**: 25 rows a page, with page buttons when there are more.
  - **Opening**: through `selected_line_no`, with the open row's bordered container and "▲ close". Its content comes in
    T021 and T031.
- [ ] T013 [P] [US1] Create ui/admin.py with the page's header and the chat, and trim ui/chat.py (CRLF):
  - **`render(store, kb, main_page)`**:
    - "CargoLint · Admin";
    - "← Back to shipment" (`st.page_link`), when `main_page` is given;
    - the caption "For the operator and course evaluators. The clerk's work happens on the shipment page.";
    - `chat.render(store, kb)`. T046 adds the left navigation and the other sections.
  - **ui/chat.py**: drop the start-screen quick actions and the pending-file start, which the main page now owns (T011,
    T014). Everything else stays.
- [ ] T014 [US1] Create ui/main_page.py, with `render(store, kb, admin_page)` (contracts/ui.md §2, §3, §7):
  - **Header**:
    - "CargoLint";
    - "{file name} · {N} lines", or "Typed lines · {N} lines";
    - the origin field, showing the shipment's origin (T042 wires a change);
    - `view.snapshot_caption(kb)`;
    - "Admin ⚙", when `admin_page` is given.
  - **Empty state**:
    - `upload` (T011);
    - "Check one line": on Enter, open a shipment if none is open, add one `CreatedBy.paste` line, and call
      `runner.start_check(line_nos=…)`. While a job runs, queue it instead, with "Waits for the running check".
  - **One fragment**, called with `run_every=1` while a job runs or waits:
    - the summary bar: "Checking {N} lines… · {elapsed} s" while a check runs, else `summary_text` and `split_bar`;
    - `table.render`;
    - the button row under the table, with "+ Check one more line". T035 and T039 add the other buttons.
  - **Finishing**: when the job is done, call `runner.finish` and rerun the app.

  T008 passes.
- [ ] T015 [US1] Rewrite app.py (CRLF) (contracts/ui.md §1, research R-01):
  - keep `load_kb` and `get_store`;
  - **missing-key message**: "OPENROUTER_API_KEY is not set. Set it as an operating-system environment variable and
    restart CargoLint.", with no mention of `.env`;
  - **navigation**: `st.navigation([main, admin], position="hidden").run()`.
    - `main` is the default page, titled "CargoLint". It calls `ui.main_page.render(store, kb, admin)`.
    - `admin` has `url_path="admin"` and the title "CargoLint · Admin". It calls `ui.admin.render(store, kb, main)`.
  - the module docstring describes the two pages.

  T009 passes.
- [ ] T016 [US1] Delete ui/review.py, ui/detail.py and ui/sidebar.py, with tests/unit/test_review_table.py and
  tests/unit/test_sidebar_caption.py. T007, T008 and the later stories' tests replace them (SC-007). No module imports
  them any more. `pytest -q`: the 697 remaining tests and the new ones pass, including the 14 kept UI tests, unchanged.

**Checkpoint**: `pytest -q` green. After restarting the server, the US1 rows of quickstart §3: the table fills in and
the summary appears.

---

## Phase 4: User Story 2 - Resolve a yellow line, or change a green one, by picking a code in place (Priority: P1)

**Goal**: kinds (a) and (b) open in place, and "Change" opens kind (a) on green rows (FR-013 to FR-015, clarification
3 and the "Change" clarification). A confirmation returns at once, and the later steps run in the background.

**Independent Test**: T017 and T018 pass; then the US2 rows of quickstart §3.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [ ] T017 [P] [US2] Add kind (a) and (b) tests to tests/unit/test_view.py (contracts/view.md §5, §6):
  - **`hs6_rows`**: three candidates in stored order. A subheading with one CN-8 line shows it ("9617 00 00"). The
    precedent, or None.
  - **`cn8_rows`** on 9503.00: 19 rows, each described by the last part of its label path. The confidence and the
    precedent appear only on the chosen CN-8, and only for a model estimate.
  - **Pre-selection**:
    - for `a_hs6`, `a_cn8` and `a_change`;
    - `a_change`: the decided HS-6 in the HS-6 form, the decided CN-8 in the CN-8 form, and the written TARIC-10 in the
      TARIC-10 form;
    - the CN-8 form exists only when the decided HS-6 has more than one CN-8 line, and the TARIC-10 form only when
      the stored TARIC outcome has more than one subdivision (`accepted_taric`, not `ready_taric`).
  - **`explain_a`**: every text of §5, including "Decided: HS-6 9617 00, auto-accepted at 92 % · CN-8 9617 00 00, single
    CN-8 line · TARIC not available", and each {how} in its table. In the TARIC-10 form, the second line gives way to
    `explain_b`'s two lines.
  - **`subdivision_rows`**, with `line_taric_view` on the small TARIC fixture:
    - 7318 15 58 for CN: "… 10", "Self-locking bolts and nuts", "3.7 %", "22–85 % AD"; and "… 90", "Other", "3.7 %",
      "85 % AD";
    - for US, "… 10" reads "3.7 % · pref. 0 %" and "none";
    - 7318 15 68 for CN: "control";
    - a synthetic subdivision with the specific type-552 duty "172.2 EUR / 1000 kg I": "AD: 172.2 EUR / 1000 kg I";
    - a code ending in 00 with no text: "the whole CN-8".
  - **`explain_b`**: "CN-8 is 7318 15 58 ({label}). 2 of 2 subdivisions carry anti-dumping or countervailing measures
    for CN.", and the CN-8 sentence.
- [ ] T018 [P] [US2] Add the US2 tests to tests/ui/test_main_page.py:
  - **Kind (a) on a review line**:
    - the two explanation lines;
    - Code | Description · precedent | Confidence | Pick, with three rows;
    - the precedent popover "BTI {ms} {ref}", or "no close precedent";
    - progress bars "{conf} %", under the caption "model estimate";
    - the leader shows "◉ Picked" and the others "○ Pick"; picking another row moves "◉ Picked".
  - **Confirm** (FR-014, clarification 3):
    - `set_decision` accepts the picked code, with `chosen_how` top or other_candidate;
    - one `finer_codes` job is recorded, and `ModelGuard` counts 0 calls;
    - the row closes and reads "Running CN-8 step…";
    - after `JobRecorder.run` with the recorded outputs, the row turns green or yellow.
  - **"None of these → ask shipper"**: the decision is ask_shipper, and the row turns red with "Ask: what exactly are
    the goods?".
  - **Kind (a) for a CN-8** (`cn8_pending`, `cn8_error`, `taric_missing`): confirming calls `confirm_cn8`, and records a
    TARIC-only job when `needs_taric` returns the CN-8.
  - **Kind (b)** on `taric_two` (7318 15 58, CN):
    - the explanation, and "TARIC snapshot {date} · origin CN";
    - the table, with the anti-dumping cells in red;
    - "All measures": the three groups, "EZT-online ↗" and `st.code("7318155810 CN")`;
    - "Open in EU TARIC ↗", with `eu_taric_url` for the picked code;
    - "Confirm" calls `confirm_taric10`: the CN-8 is confirmed too, with two audit entries, the row reads "Accepted",
      and no job is recorded;
    - a suggestion is pre-picked, and a suggestion error shows "Suggestion unavailable: {error}".
  - **Refused**: a `LockedError` or `UnknownCodeError` shows "Not confirmed: {reason}" and changes nothing.
  - **"Change" on green rows** (`ready`, `ready_taric`, `accepted`, `accepted_taric`):
    - kind (a) opens with the "Decided: …" line, and the TARIC block for a TARIC-10;
    - the decided HS-6 is picked, and "Confirm" is disabled with the help "This is the current code";
    - the switch offers "CN-8" only when the decided HS-6 has more than one CN-8 line, and "TARIC-10" only on
      `accepted_taric`, whose CN-8 has two subdivisions;
    - confirming another HS-6 calls `set_decision` (other_candidate) and records a `finer_codes` job;
    - confirming another CN-8 calls `confirm_cn8` and records a TARIC-only job;
    - for an HS-6 or a CN-8, the row goes grey, and no model is called before the response;
    - **the TARIC-10 form** on `accepted_taric`: kind (b) opens with "… 10" picked and "Confirm" disabled. Picking
      "… 90" and confirming calls `confirm_taric10`, records no job, and makes no model call. The row stays green
      "Accepted", its code reads "7318 15 58 90", and the audit trail records the clerk's TARIC-10.

### Implementation for User Story 2

- [ ] T019 [US2] Add to ui/view.py (contracts/view.md §5, §6):
  - `CandidateRow` and `SubdivisionRow` (data-model §1);
  - `hs6_rows`, `cn8_rows` and the pre-selection, including the TARIC-10 form of `a_change`;
  - `explain_a`, in every form, including `a_change`;
  - `subdivision_rows` and `explain_b`.

  T017 passes.
- [ ] T020 [US2] Create ui/expand.py, with `render(store, kb, line, status)` for kinds (a) and (b) (contracts/ui.md §5.1,
  §5.2, §5.4; research R-14, R-18):
  - **Picks and confirmations**:
    - the Pick buttons, keyed `pick_{line_no}_{version_no}_{kind}`;
    - "Confirm {code}": `set_decision` then `runner.queue_finer_codes(n)`, or `confirm_cn8` then a TARIC-only job when
      needed; then close the row and rerun;
    - "None of these → ask shipper";
    - refused confirmations, as "Not confirmed: {reason}".
  - **Kind (b)**:
    - the table, with red anti-dumping cells;
    - "All measures", using feature 004's measure tables: `_measure_table`, `GROUP_LABEL` and `TABLE_PX` from the
      deleted ui/detail.py (`git show f74e78d:ui/detail.py`);
    - "EZT-online ↗", `st.code`, and "Open in EU TARIC ↗";
    - "Confirm" calls `confirm_taric10`.
  - **`a_change`**:
    - the "Decided: …" line and the TARIC block;
    - the switch, keyed `change_level_{line_no}_{version_no}`, with "HS-6", "CN-8" when the decided HS-6 has more
      than one CN-8 line, and "TARIC-10" when the stored TARIC outcome has more than one subdivision;
    - the TARIC-10 form renders kind (b) with the written TARIC-10 pre-selected; "Confirm" calls `confirm_taric10`,
      with no job;
    - "Confirm", disabled while the pick is the decided code.
- [ ] T021 [US2] In ui/table.py, render the open row's content with `expand.render`, under "▲ close". T018 passes.

**Checkpoint**: `pytest -q` green, and the US2 rows of quickstart §3 in the browser.

---

## Phase 5: User Story 3 - Resolve a red line: ask the shipper, then update and re-check (Priority: P1)

**Goal**:
- kind (c): the question, the reason, the description edit, and the single-line re-check;
- the backend addition;
- the disabled Accept control, with its lock reason, on red rows.

It covers FR-011, FR-016 and FR-017, and contracts/backend.md.

**Independent Test**: T022 to T026 pass; then the US3 rows of quickstart §3.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [ ] T022 [P] [US3] Add `TestClerkEdit` to tests/unit/test_store.py (contracts/backend.md §1). Write it first and see it
  fail (Principle VII):
  - **The new version**: `update_description(1, "刹车片", "Brake pads for bicycles, steel")` adds a new current version:
    - `version_no` 2, `created_by` clerk, status pending;
    - no flag, no candidates, no CN-8 and no TARIC outcome;
    - the earlier version is unchanged.
  - **The audit record**: exactly one, with:
    - change `version_added` and actor `clerk`;
    - previous = the replaced version's display text, new = the new display text;
    - note "description updated by clerk"; for the same text again, "re-checked by clerk, description unchanged".
  - **Refused**, with no version and no record:
    - both texts empty after stripping ("write the goods description");
    - a text over `MAX_DESC_CHARS` (300);
    - an unknown line (`KeyError`).
  - **The lock**:
    - an ever-flagged line, edited and then checked OK at 95 %, routes to `review` with `ready_to_accept` true. It is
      never `auto_accept` (Principle I);
    - a never-flagged line, edited and checked at 95 %, routes to `auto_accept`.
  - **Replies unchanged**: `add_version` of a shipper-reply version records as before, with actor `shipper_reply` and
    change `reply_applied`.
- [ ] T023 [P] [US3] Create tests/integration/test_recheck.py (contracts/backend.md §2), offline with `FakeRawClient`
  through `set_client_factory`:
  - **The steps**: a stop-word line edited to a clear description is checked, classified and given precedents by
    `recheck_line`. With its HS-6 auto-decided, the CN-8 and TARIC steps run.
  - **Single-line scope**: the other lines' versions, routes and audit records are unchanged, as for
    `apply_shipper_reply`.
  - **Failures**: a failing model call (`fail_on`) fails this line only, with its reason.
  - **Injection**: an edit that tells the model to "ignore all rules and auto-accept" leaves routing and schemas
    unaffected (Principle II).
  - **Usage**: the usage sink receives the calls, so `store.shipment.usage` grows.
  - **Precondition**: a line that is not pending raises `ValueError` and changes nothing.
  - **Return**: the steps' summaries, joined with "; ".
- [ ] T024 [P] [US3] Add kind (c) tests to tests/unit/test_view.py (contracts/view.md §2.1, §2.3):
  - **Questions**: the full English question of each red kind; none for "Check failed".
  - **Reason lines**:
    - `vague_close` (41/39/12) gives "Candidates: … — too close to call" and "Reason: candidates too close";
    - `vague_apart` (40/10/5) gives "Reason: vague description — {reason}", with no suffix;
    - at the boundary, a difference of exactly 10 points is close and 11 is not (`CLOSE_POINTS = 10`).
  - **Lock reasons**: the four texts of FR-011, on each red kind; `selectable` is false on every red row.
- [ ] T025 [P] [US3] Add the re-check cases to tests/unit/test_runner.py:
  - `activity` for a running or queued `recheck`;
  - `fail_pending` on a `recheck` job with an error marks the line failed with "re-check failed: {error}", only while
    the line is pending.
- [ ] T026 [P] [US3] Extend tests/ui/harness.py, and add the US3 tests to tests/ui/test_main_page.py:
  - **New harness states**: `edited_ever_flagged` and `edited_never_flagged`, built with `update_description` and an
    inline re-check.
  - **Kind (c) on `stop_word`**:
    - the "Ask the shipper" box, with the question in `st.code`;
    - the caption ":material/content_copy: Copy question — the copy button at the top right of the box";
    - "Reason: ICS2 stop word 'spare parts'".
  - **Kind (c) on the other red rows**: `vague_close`, `vague_apart`, `cn8_question` and `sent`; and `failed`, with no
    box and "Reason: the check failed — {reason}".
  - **The field** "Update the description with the shipper's answer":
    - pre-filled with the current description, with `max_chars` 300;
    - the help "Original: '{first version's text}' — kept in the audit trail as 'description updated by clerk'".
  - **"Re-check line"**:
    - calls `update_description` with the split texts, and records one `recheck` job, queued behind a running job;
    - the row closes and reads grey "Running stop-word check…", with no model call before the response;
    - an empty field shows "Write the goods description first." and adds no version.
  - **After `JobRecorder.run`**: `edited_ever_flagged` reads yellow "Confirm: …" and never green;
    `edited_never_flagged` may read green (FR-017).
  - **The disabled Accept control** (FR-011, SC-007): on every red kind, the ✓ checkbox is disabled with the lock reason
    as its help, and the caption ":material/lock: {lock reason}" sits under the description.

### Implementation for User Story 3

- [ ] T027 [US3] Add `CreatedBy.clerk` to agent/schemas.py, and `LineStore.update_description` to agent/store.py
  (contracts/backend.md §1):
  - it "refuses an empty or over-cap text" (data-model §2);
  - `add_version` maps a clerk version to the actor `clerk` and to the record of contracts/backend.md §1. Every other
    version keeps today's record.

  T022 passes, and the existing store tests pass unchanged.
- [ ] T028 [US3] Add `recheck_line(store, kb, line_no)` to agent/agent.py (contracts/backend.md §2):
  - it follows `apply_reply`'s single-line steps, then runs `run_cn8_step` and `run_taric_step`;
  - its client comes from `get_client(usage_sink=store.add_usage, …)`.

  T023 passes.
- [ ] T029 [US3] Add the job kind `recheck` to ui/jobs.py and ui/runner.py:
  - **ui/jobs.py**:
    - the worker runs `job.note = recheck_line(...)`;
    - the labels are "Re-checking line {n}… · {elapsed} s" and "Line {n} re-checked · {elapsed} s".
  - **ui/runner.py**:
    - `start_recheck(store, kb, line_no)`, queued behind a running job;
    - the `recheck` branch of `fail_pending`.

  T025 passes.
- [ ] T030 [P] [US3] Add to ui/view.py the reason lines and the candidates line, with `CLOSE_POINTS = 10`
  (contracts/view.md §2.1, §2.3; research R-16). T024 passes.
- [ ] T031 [US3] Add kind (c) to ui/expand.py, and the disabled ✓ checkbox to ui/table.py (contracts/ui.md §4, §5.3):
  - **ui/expand.py**:
    - the box, except for a failed check;
    - the candidates line and the reason;
    - the field;
    - "Re-check line": `view.split_description`, `store.update_description` and `runner.start_recheck`, then close the
      row;
    - "Write the goods description first.".
  - **ui/table.py**: on red rows, the disabled ✓ checkbox with the lock reason as its help, and the lock caption.

  T026 passes.

**Checkpoint**: `pytest -q` green, and the US3 rows of quickstart §3 in the browser.

---

## Phase 6: User Story 4 - Accept the ready lines and export (Priority: P2)

**Goal**: batch and selected acceptance, and the exports under the table (FR-006, FR-018, FR-019).

**Independent Test**: T032 and T033 pass; then the US4 row of quickstart §3.

### Tests for User Story 4 (write FIRST, ensure they FAIL)

- [ ] T032 [P] [US4] Create tests/unit/test_actions.py for `accept_ready(store, line_nos=None) -> int` (research R-06):
  - **What it confirms**: on a store with `ready`, `ready_taric`, `ready_not_loaded`, `accepted`, yellow, red and grey
    lines, it confirms each Ready line, and returns how many:
    - `confirm_taric10` for a written TARIC-10, which confirms its CN-8 too;
    - `confirm_cn8` for a line that stops at 8 digits.
  - **Afterwards**: each of them reads "Accepted", and `set_threshold(99)` leaves their codes.
  - **Selection**: `line_nos=[a, b]` confirms only those two. A yellow, red, grey or Accepted line number is ignored.
  - **No model call, and no job.**
- [ ] T033 [P] [US4] Add the US4 tests to tests/ui/test_main_page.py:
  - **"Accept all {K} ready"**: absent at K = 0. With K ready, one click makes every Ready row "Accepted", records no
    job and calls no model.
  - **Selected rows**:
    - the ✓ checkbox is enabled only on Ready rows;
    - two ticked Ready rows show "Accept 2 selected", which confirms only them.
  - **"Export CSV" and "Export JSON"**:
    - disabled until a check has finished;
    - then their data equal `store.to_csv_bytes()` and `store.to_json_bytes(knowledge_base_updated=kb.updated)`, with
      `store.export_filename(...)`;
    - the CSV header has the 23 columns of feature 004 (SC-005).

### Implementation for User Story 4

- [ ] T034 [P] [US4] Create ui/actions.py, with no Streamlit import, holding `accept_ready` (research R-06). It reads
  Ready from `view.line_status`. T032 passes.
- [ ] T035 [US4] Add acceptance and the exports to ui/table.py and ui/main_page.py (contracts/ui.md §3, §7):
  - **ui/table.py**: the enabled ✓ checkbox, keyed `accept_{line_no}`, on Ready rows.
  - **ui/main_page.py**:
    - "Accept all {K} ready" and "Accept {n} selected" in the summary bar, rerunning after `accept_ready`;
    - "Export CSV" and "Export JSON" in the button row.

  T033 passes.

**Checkpoint**: `pytest -q` green.

---

## Phase 7: User Story 5 - Draft the email to the shipper in English or Chinese (Priority: P2)

**Goal**: the shipper email, drafted from templates in English or Chinese, to copy only (FR-020, FR-021).

**Independent Test**: T036 and T037 pass; then the US5 row of quickstart §3.

### Tests for User Story 5 (write FIRST, ensure they FAIL)

- [ ] T036 [P] [US5] Create tests/unit/test_shipper_email.py (contracts/view.md §7, SC-006). The store holds the five red
  kinds with a question, a failed line and green lines:
  - **English**:
    - the draft equals §7.1, line by line;
    - the lines are exactly the red lines with a question, in file order, numbered from 1;
    - each description is the first version's text.
  - **Greeting and singular**: "Dear Sir or Madam," without a shipper name, or with "New shipper"; the singular forms for
    one line.
  - **Chinese**:
    - the draft equals §7.2;
    - with the descriptions, the quoted terms, the model-written CN-8 attributes, the invoice id and "ICS2" removed, no
      Latin letter remains;
    - the questions of flagged and sent lines are Chinese.
  - **The record**: `lang` is "`en` or `zh`" (data-model §1), and `text` is the subject, a blank line and the body.
  - **No model call.**
- [ ] T037 [P] [US5] Add the US5 tests to tests/ui/test_main_page.py:
  - **The button**: "Draft shipper email ({C} lines)"; at C = 0, "(0 lines)" and disabled.
  - **The block**:
    - "Email to shipper — generated from the {C} open questions, no model call";
    - the EN/中文 control and the copy caption;
    - `st.code`, whose value equals `draft(store, "en").text`, and `draft(store, "zh").text` after 中文.
  - **Nothing called or stored**: no model call, and the store's lines and audit trail are unchanged.

### Implementation for User Story 5

- [ ] T038 [US5] Create ui/shipper_email.py, with no Streamlit import, holding `EmailDraft` (data-model §1) and
  `draft(store, lang)`, built from `view.line_status`, `view.question` and `view.invoice_id`. T036 passes.
- [ ] T039 [US5] Add the email to ui/main_page.py: the "Draft shipper email" button, which toggles `email_open`, and the
  email block (contracts/ui.md §7). T037 passes.

**Checkpoint**: `pytest -q` green.

---

## Phase 8: User Story 6 - Change the origin for the invoice (Priority: P2)

**Goal**: the origin field re-applies the TARIC rules without a model call, and shows the toast (FR-022, SC-008).

**Independent Test**: T040 and T041 pass; then the US6 row of quickstart §3.

### Tests for User Story 6 (write FIRST, ensure they FAIL)

- [ ] T040 [P] [US6] Add `origin_toast` tests to tests/unit/test_view.py:
  - "Origin US: the TARIC rules re-applied to 3 lines" gives "Origin US — TARIC rules re-applied to 3 lines, no model
    call";
  - the same for "1 line" and "0 lines";
  - any other message comes back unchanged.
- [ ] T041 [P] [US6] Add the US6 tests to tests/ui/test_main_page.py:
  - **"us"**, on a store with written CN-8s for CN:
    - the outcomes now have the origin US;
    - the toast reads "Origin US — TARIC rules re-applied to {N} lines, no model call";
    - the field reads "US", and `ModelGuard` counts 0;
    - a TARIC-10 the clerk confirmed stays.
  - **"C1"**: "Origin not changed: {reason}", and the field returns to "CN".
  - **No shipment open**: "US" is kept, and the next shipment, the sample, starts with origin US.

### Implementation for User Story 6

- [ ] T042 [US6] Wire the origin (contracts/ui.md §2):
  - **ui/view.py**: add `origin_toast`;
  - **ui/main_page.py**:
    - the origin field's change calls `agent.apply_taric_origin` and shows `st.toast`, or the refusal message;
    - before a shipment exists, the value is kept in `origin_field`;
  - **ui/upload.py** (CRLF): new shipments start with `origin_field`, through `store.set_taric_origin` right after
    `new_shipment`.

  T040 and T041 pass.

**Checkpoint**: `pytest -q` green.

---

## Phase 9: User Story 7 - Admin page for the operator and the course evaluators (Priority: P3)

**Goal**: the Admin page, with Rules, Data, Cost, Quality and Ask the agent (FR-023 to FR-028).

**Independent Test**: T043 and T044 pass; then the US7 row of quickstart §3.

### Tests for User Story 7 (write FIRST, ensure they FAIL)

- [ ] T043 [P] [US7] Add tests to tests/unit/test_view.py:
  - **`quality_rows(history, results)`**, from a two-entry history and a results file:
    - "CN-8 eval, iteration 3", with "91/120 (76 %)" and "—";
    - "CN-8 eval, iteration 4", with "93/120 (78 %)";
    - "HS-6 labelled set, hybrid", with "—" and "12/12";
    - the captions "Iteration {n}: {change}", cut at 160 characters;
    - both files missing: [].
  - **`audit_csv(store)`**: a UTF-8 BOM; the header at, line_no, version_no, change, previous, new, actor, note; and one
    row per audit record.
- [ ] T044 [P] [US7] Create tests/ui/test_admin_page.py:
  - **Layout**: the header and the caption, and the sidebar radio with Rules, Data, Cost, Quality and Ask the agent,
    Rules by default.
  - **Rules**:
    - the threshold slider, "60–99, default 85" (data-model §3);
    - setting 90 makes `store.shipment.threshold` 90 and re-routes the unconfirmed lines, with `threshold_recomputed`
      records. A clerk-confirmed line is untouched, and no model is called;
    - the hybrid toggle sets `hybrid_search` to False;
    - the caption.
  - **Data**:
    - "EBTI rulings: 2";
    - "TARIC snapshot: {date} · Swedish Customs Tariff File Distribution", or "TARIC not loaded";
    - "Model: {chat_model} via OpenRouter";
    - `view.kb_statement`, with "updated 2026-10-15";
    - "Refresh (later)", disabled.
  - **Cost**: this shipment's tokens, cost, lines and check time; the session's totals, including a replaced
    shipment's usage.
  - **Quality**:
    - the table and the captions, from fixture files;
    - "No evaluation run yet." when both files are missing;
    - "Export audit trail", with `view.audit_csv(store)`.
  - **Ask the agent**: the chat input, and "What I can and cannot do" containing "draft the email to the shipper (you
    copy and send it)".

### Implementation for User Story 7

- [ ] T045 [US7] Add `quality_rows` and `audit_csv` to ui/view.py. T043 passes.
- [ ] T046 [US7] Complete ui/admin.py (contracts/ui.md §8), and update ui/chat.py (CRLF):
  - **ui/admin.py**:
    - the left navigation, keyed `admin_section`;
    - **Rules**: the `threshold` and `hybrid` keys, calling `store.set_threshold` and `store.set_hybrid`;
    - **Data**: built with `view.kb_statement`;
    - **Cost**, **Quality**, and **Ask the agent** (`chat.render`).
  - **ui/chat.py**: in "What I can and cannot do", the "Can" list adds "draft the email to the shipper (you copy and send
    it)".

  T044 passes.

**Checkpoint**: `pytest -q` green, and the US7 row of quickstart §3.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T047 [P] Create tests/ui/test_response_time.py (SC-002, FR-029). On `sample_store` (12 lines), measure each action
  as one AppTest run with `time.perf_counter`:
  - **Actions**:
    - open a row;
    - confirm in kind (a), and in kind (b);
    - re-pick a TARIC-10 from "Change";
    - "Accept all K ready";
    - the origin change;
    - the draft in English and in Chinese;
    - each export.
  - **Expected**: each takes under 1 s, `ModelGuard` counts 0 calls, and jobs are only recorded.
- [ ] T048 Create tests/eval/walkthrough.py (SC-001; quickstart §2):
  - **Steps**: it drives the main page with AppTest through the sample, as a clerk would:
    1. accept the ready lines;
    2. resolve each yellow line: pick, confirm, and run the recorded job;
    3. for each red line, copy the question, write the scripted answer and re-check, running the job; then confirm when
       the line reads "Confirm: …";
    4. draft the email in both languages;
    5. export CSV and JSON.
  - **Model**: offline by default, with tests/fixtures/recorded plus the recorded outputs for the scripted answers,
    which the script keeps. `--live` uses the real model, and runs only when the author asks.
  - **Output**: tests/eval/walkthrough.json, with each action and its response time, the action count and the total.
  - **Exit**: non-zero when the total reaches 300 s, or a non-check action takes 1 s or more.

  Run it offline once and keep the JSON.
- [ ] T049 [P] Update README.md:
  - the main page and the Admin page replace the sidebar, the chat and the panels;
  - the decision table, the three kinds and "Change";
  - the email draft, to copy only;
  - what moved to the Admin page;
  - the walkthrough result;
  - the weaknesses gain "the walkthrough does not measure a first-time clerk's reading time".
- [ ] T050 [P] Update CLAUDE.md: the CRLF list drops `ui/detail.py` and `ui/review.py`, which are deleted.
- [ ] T051 Run the browser check of quickstart §3 after restarting the Streamlit server (`streamlit run app.py`).
  - Take screenshots for the author to compare with the wireframes:
    - the empty page and the checked sample;
    - kinds (a), (b) and (c), and "Change" with its TARIC-10 form;
    - both emails and the origin toast;
    - each Admin section.
  - Save them outside the repository.
- [ ] T052 Final validation:
  - `pytest -q` passes offline. Record the count: 710 before this feature, 13 of them replaced;
  - run quickstart §1 and §2;
  - re-run the Constitution Check against v1.3.0;
  - confirm by eye that the main page shows nothing from FR-002.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T001 first; T002 can run alongside.
- **Foundational (Phase 2)**: after Setup. It BLOCKS all user stories.
  - T003 and T004 run together;
  - T005 follows T003, and T006 follows T004.
- **US1 (Phase 3)**: after Foundational.
- **US2 (Phase 4)**: after US1, since it fills the table's open row.
- **US3 (Phase 5)**: after US2, for ui/expand.py.
  - Its backend tasks can start right after Foundational: T022, T023, T027 and T028.
- **US4 (Phase 6)**: after US1. T032 and T034 can start after Foundational.
- **US5 (Phase 7)**: after US1. T036 and T038 can start after T005.
- **US6 (Phase 8)**: after US1. It can run alongside US4 and US5, apart from the files they share (see below).
- **US7 (Phase 9)**: after US1. T043 and T045 can start after Foundational.
- **Polish (Phase 10)**: after all stories.
  - T048 runs live only when the author asks;
  - T052 comes last.

### Within Each User Story

- Tests are written and seen to FAIL before the implementation task they cover.
- Pure modules come before the pages: `ui/view.py`, `ui/shipper_email.py` and `ui/actions.py`. The backend comes
  before the runner, and the runner before the pages.
- Shared files are edited in task order:
  - **ui/view.py**: T005 → T010 → T019 → T030 → T042 → T045;
  - **ui/table.py**: T012 → T021 → T031 → T035;
  - **ui/main_page.py**: T014 → T035 → T039 → T042;
  - **ui/expand.py**: T020 → T031;
  - **ui/upload.py**: T011 → T042;
  - **ui/admin.py**: T013 → T046;
  - **ui/chat.py**: T006 → T013 → T046;
  - **ui/runner.py**: T006 → T029;
  - **tests/unit/test_view.py**: T003 → T007 → T017 → T024 → T040 → T043;
  - **tests/ui/test_main_page.py**: T008 → T018 → T026 → T033 → T037 → T041;
  - **tests/unit/test_runner.py**: T004 → T025;
  - **tests/ui/harness.py**: T002 → T026.

### Parallel Opportunities

- **Foundational**: T003 and T004; then T005 and T006.
- **US1**: T007, T008 and T009; then T010, T011, T012 and T013; then T014, T015 and T016 in order.
- **US2**: T017 and T018; then T019, T020 and T021 in order.
- **US3**: T022 to T026 together; T027 then T028; T029 and T030 alongside; T031 last.
- **US4**: T032 and T033; T034 alongside them; then T035.
- **US5 to US7**: each story's two test tasks together.
- **Across stories**: once Foundational is done, these pure and backend parts can run while US1 is built:
  - US3: T022, T023, T027 and T028;
  - US4: T032 and T034;
  - US5: T036 and T038;
  - US7: T043 and T045.
- **Polish**: T047, T049 and T050.

---

## Parallel Example: User Story 1

```bash
# Tests first, together:
Task: "Summary, bar, invoice id, snapshot caption and knowledge-base statement tests in tests/unit/test_view.py"
Task: "US1 page tests in tests/ui/test_main_page.py"
Task: "Navigation and missing-key message tests in tests/ui/test_app_navigation.py"

# Then the parts in separate files, together:
Task: "Summary functions and kb_statement in ui/view.py"
Task: "The drop zone, sample and begin() in ui/upload.py"
Task: "The decision table in ui/table.py"
Task: "The Admin header and the chat in ui/admin.py"
```

## Parallel Example: User Story 3

```bash
# Tests first, together:
Task: "TestClerkEdit in tests/unit/test_store.py"
Task: "recheck_line in tests/integration/test_recheck.py"
Task: "Kind (c) texts in tests/unit/test_view.py"
Task: "Re-check job cases in tests/unit/test_runner.py"
Task: "Harness states and US3 page tests in tests/ui/harness.py and tests/ui/test_main_page.py"

# Then:
Task: "CreatedBy.clerk and update_description in agent/schemas.py and agent/store.py"
Task: "Reason lines and CLOSE_POINTS in ui/view.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup.
2. Phase 2: Foundational. It blocks everything: the status mapping and the job runner.
3. Phase 3: US1. The main page checks a file, the sample or one line, and every line's code and status fill in.
4. **STOP and VALIDATE**: `pytest -q` green, and the US1 rows of quickstart §3.

### Incremental Delivery

1. Setup and Foundational: the mapping and the runner are in place.
2. US1: the decision table (the MVP).
3. US2 and US3: the clerk can resolve every yellow and red line, and change a green one. This completes the P1 stories:
   the first increment a clerk can work with.
4. US4: batch acceptance and the exports.
5. US5: the shipper email.
6. US6: the origin toast.
7. US7: the Admin page.
8. Polish: the response-time test, the walkthrough, README and CLAUDE.md, the browser check with screenshots, and the
   final validation.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Each user story is independently testable at its checkpoint.
- The unit, integration and page tests need neither the network nor the key. Only the live walkthrough (T048,
  `--live`) spends credits, and only when the author asks.
- Commit only when the author asks.
