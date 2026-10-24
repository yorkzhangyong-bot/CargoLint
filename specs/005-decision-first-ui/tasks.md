---

description: "Task list for the decision-first clerk workflow (UI redesign)"
---

# Tasks: Decision-First Clerk Workflow (UI Redesign)

**Input**: Design documents from `/specs/005-decision-first-ui/`

**Prerequisites**:
- plan.md (required) and spec.md (required for user stories);
- research.md (R-01 to R-21), data-model.md and quickstart.md;
- contracts/: ui.md, view.md and backend.md;
- `.specify/memory/constitution.md` (v1.3.0).

**Tests**: REQUIRED.
- **Why**:
  - the constitution (Principle VII) requires tests first for guardrail code: the clerk's edit (caps, lock, audit),
    the single-line re-check and the queued re-check;
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
- **US2**: pick a code in place, type an HS-6 code, and "Change" on green rows.
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
  - no file in `ui/`, and not `app.py`, names the TARIC tool: tests/unit/test_taric_store.py forbids it;
  - the worker thread never calls Streamlit.
- **Line endings**: `app.py` uses CRLF. Every other file named here, and every new file, uses LF. Keep each file's line
  endings.
- **Browser checks**: the Streamlit server never reloads `ui/*.py`; restart it before any browser check.
- **Exact texts**: every text the pages show comes from contracts/view.md and contracts/ui.md, and the tests assert
  those texts.
- **Unchanged files**: `agent/routing.py`, `agent/taric_rules.py`, `agent/prompts.py`, every module in `tools/` and
  `rag/`, and `ui/replies.py` are not edited. The only backend edits are T027 and T028 (contracts/backend.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the baseline, the sample TARIC fixture and the page-test harness that every story's tests use.

- [X] T001 Run `pytest -q` before any change and confirm 710 passed with 4 deselected. T052 compares against it.
- [X] T002 [P] Build the test infrastructure: the sample TARIC fixture, and the page-test harness in tests/ui/__init__.py
  (empty) and tests/ui/harness.py:
  - **The sample TARIC fixture** (research R-13):
    - tests/fixtures/make_taric_sample.py reads data/taric.jsonl. It writes tests/fixtures/taric/snapshot_sample.jsonl
      in schema 2. The file holds, in this order:
      - the snapshot record;
      - every geographical_area record, which the lookup needs for country groups and area names;
      - for each CN-8 below, its goods_nomenclature records with their ancestors, and all their measures;
    - the CN-8 codes are every CN-8 under the HS-6 codes among the sample's candidates, after the offline check and
      the walkthrough's answers. Among them are 6109 10 00, 8518 30 00, 4016 93 00, 3926 90 97, 8714 91 10,
      9503 00 95 and 9617 00 00;
    - the fixture is committed, so the tests need no data/taric.jsonl. Feature 004's small fixture stays as it is.
  - **`make_kb(taric="small")`**: a `KnowledgeBase` like the `kb` fixture of tests/integration/test_agent_check_flow.py:
    - the small index (tests/fixtures/cn2026_excerpt.jsonl), with BM25 and in-memory vectors over `FakeEmbeddings(dim=16)`;
    - a `BTIStore` of two synthetic rulings, one under 9503.00 and one under 8714.91;
    - the rules of tests/fixtures/rules, and `meta` with `built_at` "2026-10-15T00:00:00";
    - `taric`: the small fixture ("small"), the sample fixture ("sample") or none (None).
  - **`store_with(*states, origin="CN")`**: a `LineStore` on the small index, with the reference "INV-TEST" and one line
    per named state.
    - **How**: only through store methods, never by assigning fields. They are `add_lines`, `add_version`,
      `update_check`, `update_classification`, `update_precedents`, `set_decision`, `set_cn8_result`, `confirm_cn8`,
      `set_taric_result`, `confirm_taric10`, `ask_shipper_for_taric` and `mark_failed`.
    - **Flags**: they come from `check_descriptions` on the state's text with the fake client, so the rule engine sets
      them as the app does; no flag is built by hand. Each state's text is fixed, so tests can read it.
    - **Recordings**: the fake client judges any unrecorded text as vague and ranks it with no candidate. So the
      harness keeps its own recorded outputs for its texts: an OK judgement for each clear text, and candidates for
      each text that needs them, including "Spare parts".
    - **Pending, failed and red**:
      - `pending` and `failed`;
      - `ics2_term`: "Spare parts", flagged vague with the ICS2 unacceptable term "spare parts";
      - `firm_stop_word`: "Gift", flagged as a stop word from the firm list;
      - `vague_close` (41/39/12) and `vague_apart` (40/10/5): a text no rule matches, flagged vague by the judgement,
        below the ask floor;
      - `vague_review`: flagged vague, 55, at or above the ask floor (vague confidence is capped at 59);
      - `unreadable`: a parsed line marked unreadable;
      - `cn8_question`: 9503.00, "whether the toy cars incorporate a motor";
      - `sent`: the clerk's ask-shipper decision;
      - `taric_question`: `taric_two` sent to the shipper with `ask_shipper_for_taric` and the question of
        contracts/view.md §7.3.
    - **Yellow**:
      - `cn8_error`;
      - `review` (58 %);
      - `ready_to_accept`: a flagged version, then a shipper-reply version OK at 91 %;
      - `no_candidate`;
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
    - **Two origins**: `ready_taric` needs origin US. `all_states()` returns a CN store with every other state and a US
      store with `ready_taric`.
  - **`sample_store(kb)`**: the 12-line sample checked offline, as tests/integration/test_upload_flow.py does:
    - the sample workbook registered;
    - `ScriptedChatModel` scripting the six tool calls;
    - the recorded outputs of tests/fixtures/recorded;
    - `make_kb(taric="sample")`, so its lines reach kind (b).
  - **`JobRecorder`**: replaces `ui.jobs.start` (monkeypatch), so a test records each `Job` without a thread.
    - `.keep_running()` leaves the last job running, for the "Running …" texts.
    - `.run(store, kb)` runs a recorded job inline with the fake client when a test needs its effect.
  - **`ModelGuard`**: installs a counting `FakeRawClient` (the recorded outputs) and a `ScriptedChatModel`. `.calls` counts
    both, and the factories are restored on exit.
  - **`app(store, kb)`**: an `AppTest.from_function` script with `default_timeout=10`.
    - It builds `st.navigation` like `app.py`'s (two pages, hidden) with the harness's current objects.
    - `st.session_state["_harness_page"]` ("main" or "admin") chooses the default page. A test can therefore switch pages
      between runs and see both links.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the status mapping every page renders (contracts/view.md §1 to §3), and the job runner both pages use
(contracts/ui.md §6).

**CRITICAL**: no user story work can begin until this phase is complete.

### Tests for the foundation (write FIRST, ensure they FAIL)

- [X] T003 [P] Create tests/unit/test_view.py with the status mapping (contracts/view.md §1 to §3, §8):
  - **Mapping (SC-004)**: one test per row of §1, on the harness states. Each asserts the colour, text, action, kind,
    `selectable`, `lock_reason` and `question`:
    - **rows 1 and 3**:
      - `activity="running"` gives "Running stop-word check…", "Running HS-6 step…", "Running CN-8 step…" and "Running
        TARIC step…";
      - `"queued"` gives "Queued: CN-8 step", and `"recheck_queued"` gives "Queued: re-check";
      - a pending line with no activity reads "Not checked yet";
    - **rows 2 and 4 to 7**: red, "Update", kind `c` or `c_failed`, with the texts and lock reasons of §2.1:
      - `ics2_term`: "Ask: what exactly is “spare parts”?" and "Locked: ICS2 unacceptable term 'spare parts' — update
        the description and re-check";
      - `firm_stop_word`: "Locked: firm stop word 'gift' — …";
      - `unreadable`: "Ask: unreadable line" and "Locked: the description could not be read — update the description and
        re-check";
      - `taric_question`: "Ask: which TARIC subdivision applies?";
      - a judgement flag reads "Ask: material, product name, use?";
    - **rows 8 to 13**: yellow, "Choose", with the texts of §2.2:
      - kind `a_cn8`: "Pick: CN-8, 19 lines" and "Confirm: 9503 00 95" (the TARIC step missing);
      - kind `a_hs6`: "Pick: 3 candidates", "Confirm: 9503 00" (ready to accept) and "Pick: no candidate";
      - kind `b`: "Pick: 10 or 90", "Pick: 9 options, 3 AD" and "Confirm: 7318 15 68 00";
    - **row 14**: green, "Ready" (selectable) or "Accepted", the action "Change" and the kind `a_change`;
    - **no step left**: a running activity on a line with nothing left to run shows the line's own status;
    - **row 8**: it needs the failed CN-8 choice to sit under the decided HS-6. A failed choice under an HS-6 that a
      threshold raise left undecided gives row 9 instead;
    - **values**: the kind is one of "`a_hs6`, `a_cn8`, `a_change`, `b`, `c`, `c_failed` or none", and the action one
      of "`Choose`, `Update`, `Change` or none" (data-model §1).
  - **SC-003**: no status text equals "Review" or "Needs action", or contains "to confirm". This holds on the harness
    states and on every line of `sample_store`.
  - **Lengths**: status texts are at most 44 characters, and a long CN-8 attribute is cut with "…". Lock reasons,
    questions and reason lines are never cut.
  - **`next_step`**: each of its four answers, and None. "TARIC step" is read from the stored CN-8 choice and TARIC
    outcome, including an outcome for another origin.
  - **`code_display`** (FR-008):
    - "____ __ __ __", "9503 00 __ __", "8714 91 10 __" and "7318 15 58 10";
    - "9617 00 00" with the note "TARIC not available", and the same with "TARIC not loaded";
    - a CN-8 or TARIC-10 suggestion fills no digit.
  - **`md_escape`**: "[click](https://x.test)" and "*bold* _it_ `code`" come back with every Markdown character
    escaped; Chinese text is unchanged.
  - **`split_description`**: "不锈钢保温杯 / Stainless steel vacuum flask" gives both parts; English only gives
    ("", text); Chinese only gives (text, "").
- [X] T004 [P] Create tests/unit/test_runner.py for the runner's pure parts (contracts/ui.md §6), with no Streamlit
  session:
  - **`activity(job, queue, line_no)`**:
    - a running `check` covers every line;
    - a running `finer_codes` or `reply` job covers its line only;
    - a queued `finer_codes` entry gives "queued";
    - no job and an empty queue give None.
  - **`fail_pending(store, job)`**:
    - a `check` job with an error calls `finalize_check`, so every pending line reads failed with "not checked — a step
      did not run";
    - a `finer_codes` error changes nothing in the store;
    - a job without an error changes nothing.

### Implementation for the foundation

- [X] T005 Create ui/view.py, with no Streamlit import, holding the foundation of contracts/view.md:
  - `LineStatus` and `CodeDisplay` as frozen dataclasses (data-model §1);
  - `next_step`, with the TARIC step read from the stored CN-8 choice and TARIC outcome. Never import or name the TARIC
    tool;
  - `line_status`, including the unreadable row, with the red, yellow and running texts of §2 and the lock reasons.
    Only status texts are cut at 44 characters;
  - `question(store, line, lang, kb)`, with the English and Chinese texts of §7.3. For a TARIC question, the English
    text is the stored question, and the Chinese one lists the subdivisions through `line_taric_view`;
  - `edit_problem(zh, en)`, the click-time check of contracts/view.md §8;
  - `code_display`, `md_escape` and the spaced-code helper;
  - `split_description`, with `tools.parsers.split_mixed`, as ui/chat.py's `_zh` and `_en` do.

  It reads the store only through the methods named at the top of contracts/view.md. T003 passes, and
  tests/unit/test_taric_store.py still passes.
- [X] T006 Create ui/runner.py, and adapt ui/jobs.py, ui/chat.py and ui/detail.py (contracts/ui.md §6, research R-15):
  - **Move** `queue_finer_codes`, `_start_queued_finer_codes` and `_finish_job` from ui/chat.py to ui/runner.py, as
    `queue_finer_codes`, `start_next` and `finish`.
    - `finish` still adds the chat record of each check, reply and question, with its steps, sources and notes.
    - `finish` never changes `selected_line_no`, so no row opens by itself, and the import of
      `ui.review.reset_selection` goes.
  - **Queue**: `job_queue` replaces `finer_codes_queue`. Its entries are `("finer_codes", line_no, taric_only)` and, from
    T014, `("check", text)`. Each touches the store only when its job starts.
  - **Add**:
    - `start_check(store, kb, *, file_ref=None, line_nos=None)`;
    - `activity`, which covers a reply job's line too, and `fail_pending` (T004);
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
- the header, "Open another file" and the empty state;
- a check of a file, the sample or one typed line;
- the table, whose codes and statuses fill in live;
- the summary bar.

It covers FR-001 to FR-013 without the expanded content, "+ Check one more line" (FR-018) and FR-029 for these actions.

**Independent Test**: T007 to T009 pass; then the US1 rows of quickstart §3 in the browser.

### Tests for User Story 1 (write FIRST, ensure they FAIL)

- [X] T007 [P] [US1] Add summary and caption tests to tests/unit/test_view.py (contracts/view.md §4, §8):
  - **`summary`** on `all_states()`: ready, pick, ask, failed, running, to_accept.
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
  - **`taric_statement(kb)`**: "TARIC snapshot: 2026-10-01 · 105 CN-8 mismatches · Swedish Customs Tariff File
    Distribution", "1 CN-8 mismatch", "0 CN-8 mismatches", and "TARIC not loaded" (feature 002 FR-024).
  - **`kb_statement(kb)`**: today's knowledge-base caption, with "updated 2026-10-15".

  These replace tests/unit/test_sidebar_caption.py.
- [X] T008 [P] [US1] Create tests/ui/test_main_page.py with the US1 tests (AppTest through `harness.app`, with
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
  - **The table** (FR-007 to FR-011), on `all_states()`:
    - rows in file order;
    - the code as inline code, with its note;
    - the dot and the status text;
    - "Choose", "Update" or "Change", and no action on grey rows;
    - descriptions escaped.
  - **Opening a row** (FR-013):
    - the description or the action sets `selected_line_no`;
    - the bordered container with "▲ close" renders under that row, and choosing it again closes it;
    - a grey row does not open.
  - **Live check** (FR-004):
    - while a recorded check job runs, every pending line reads "Running stop-word check…" with a grey dot, and the
      summary reads "Checking 12 lines… · {n} s";
    - while a file is read, before any line exists, the page reads "Checking sample_packing_list.xlsx…" instead of the
      empty state;
    - the drop zone, the sample button and "Check one line" are disabled while any job runs. With no lines and a
      non-check job running, the empty state shows, disabled.
  - **Summary** (FR-005): the sentence and the bar once the check has finished.
  - **The header**: "{file name} · {N} lines", with a file name such as "inv_[1].xlsx" shown escaped.
  - **Starting checks**:
    - "Try the sample invoice" starts one `check` job with the sample's file reference and the reference
      "HOL-2026-10-0472", and empties the chat;
    - "Check one line" adds one `CreatedBy.paste` line to a new shipment and starts its check;
    - "+ Check one more line" (button `more_line_button`) shows its field and adds the line to the open shipment;
    - while a job runs, its line waits ("Waits for the running check") and is added only when its check starts.
  - **"Open another file"**:
    - once lines exist, its button (`open_file_button`) shows the drop zone and "Try the sample invoice"; it is
      disabled while any job runs;
    - the sample asks "A checked shipment is open. Replace it with sample_packing_list.xlsx? Results, counts and cost
      reset.";
    - "Replace" adds the old shipment's usage to `session_usage`.
  - **Model calls**: none, in any of these actions.
- [X] T009 [P] [US1] Create tests/ui/test_app_navigation.py:
  - **`AppTest.from_file("app.py")`**, with `rag.loader.open_knowledge_base` patched to return `make_kb()`, and
    `agent.config.get_settings` patched to return settings with a test key:
    - the default page is the main page, with a `page_link` node "Admin ⚙";
    - the navigation is hidden: no page list;
    - without a key, the page shows "OPENROUTER_API_KEY is not set. Set it as an operating-system environment variable
      and restart CargoLint." and stops. The text does not contain ".env" (contracts/ui.md §1).
  - **`harness.app`**: with "admin" chosen, the Admin page renders "← Back to shipment"; with "main" chosen again, the
    main page renders "Admin ⚙".

### Implementation for User Story 1

- [X] T010 [P] [US1] Add to ui/view.py:
  - `Summary` (data-model §1), `summary`, `summary_text`, `split_bar` and `invoice_id`, with the button labels of
    contracts/view.md §4;
  - `snapshot_caption(kb)`;
  - `taric_statement(kb)`, moved from `taric_caption` in ui/sidebar.py with its mismatch count;
  - `kb_statement(kb)`, moved from `kb_caption` in ui/sidebar.py.

  T007 passes.
- [X] T011 [P] [US1] Rewrite ui/upload.py for the main page (contracts/ui.md §2):
  - **Elements**:
    - the drop zone with its label and caption, the caps checked first with `check_caps` as today;
    - "Try the sample invoice";
    - the replacement question with "Replace" and "Cancel";
    - all of them disabled while any job runs, so they work both in the empty state and under "Open another file".
  - **`open_shipment(store, reference="")`**: the one way a new shipment opens (contracts/ui.md §2):
    - it adds the old shipment's usage to `session_usage`;
    - it opens the shipment with the Admin `threshold` and `hybrid` values (85 and on when missing) and the kept
      origin.
  - **`begin(store, data, name, reference=None)`**:
    1. `open_shipment`, with `SAMPLE_REFERENCE` for the sample, else the file name without its extension;
    2. register the file, and start the check with `runner.start_check(file_ref=…)`;
    3. empty `chat`, and set `selected_line_no` to None.
  - **Remove**:
    - the shipment fields: reference, shipper and filing type (FR-002);
    - the compatibility `render`;
    - the `ui.review` import.
  - **Keep** `needs_confirmation`, `start_shipment_from_parsed` and `busy`; tests/integration/test_upload_flow.py uses
    them.
- [X] T012 [P] [US1] Create ui/table.py (contracts/ui.md §4):
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
- [X] T013 [P] [US1] Create ui/admin.py with the page's header and the chat, and trim ui/chat.py:
  - **`render(store, kb, main_page)`**:
    - "CargoLint · Admin";
    - "← Back to shipment" (`st.page_link`), when `main_page` is given;
    - the caption "For the operator and course evaluators. The clerk's work happens on the shipment page.";
    - `chat.render(store, kb)`. T046 adds the left navigation and the other sections.
  - **ui/chat.py** (contracts/ui.md §8):
    - drop the quick actions that check a description or open the sample, and the pending-file start. The main page now
      owns them (T011, T014);
    - keep the quick action "Which terms does customs reject?";
    - show "What I can and cannot do" at all times, not only before a check;
    - its live turn no longer reads `layout_has_lines`, and reruns through `runner.finish`;
    - its `_ensure_shipment` opens shipments through `upload.open_shipment`.

    Everything else stays.
- [X] T014 [US1] Create ui/main_page.py, with `render(store, kb, admin_page)` (contracts/ui.md §2, §3, §7):
  - **Header**:
    - "CargoLint";
    - "{file name} · {N} lines" with the file name escaped, or "Typed lines · {N} lines";
    - the origin field, with `persist_state="session"`, showing the shipment's origin (T042 wires a change);
    - `view.snapshot_caption(kb)`;
    - "Open another file", once lines exist: a button (key `open_file_button`), disabled while any job runs, that
      toggles the flag `open_file` and shows `upload`'s drop zone and sample button;
    - "Admin ⚙", when `admin_page` is given.
  - **Empty state**: shown with no lines. While a file check runs, "Checking {file name}…" shows instead. Its
    controls are disabled while any job runs.
    - `upload` (T011);
    - "Check one line": on Enter, open a shipment with `upload.open_shipment` if none is open, add one
      `CreatedBy.paste` line, and call `runner.start_check(line_nos=…)`. It never queues.
  - **One fragment**, called with `run_every=1` while a job runs or waits:
    - the summary bar: "Checking {N} lines… · {elapsed} s" while a check runs, else `summary_text` and `split_bar`;
    - `table.render`;
    - the button row under the table, with "+ Check one more line" (button `more_line_button`, flag
      `more_line_open`), which queues its line while a job runs. T035 and T039 add the other buttons.
  - **Finishing**: when the job is done, call `runner.finish` and rerun the app.

  T008 passes.
- [X] T015 [US1] Rewrite app.py (CRLF) (contracts/ui.md §1, research R-01):
  - keep `load_kb` and `get_store`;
  - **missing-key message**: "OPENROUTER_API_KEY is not set. Set it as an operating-system environment variable and
    restart CargoLint.", with no mention of `.env`;
  - **navigation**: `st.navigation([main, admin], position="hidden").run()`.
    - `main` is the default page, titled "CargoLint". It calls `ui.main_page.render(store, kb, admin)`.
    - `admin` has `url_path="admin"` and the title "CargoLint · Admin". It calls `ui.admin.render(store, kb, main)`.
  - drop `layout_has_lines`;
  - the module docstring describes the two pages.

  T009 passes.
- [X] T016 [US1] Delete ui/review.py, ui/detail.py and ui/sidebar.py, with tests/unit/test_review_table.py and
  tests/unit/test_sidebar_caption.py.
  - T007, T008 and the later stories' tests replace them (SC-007).
  - No module imports them any more.
  - `pytest -q`: the 697 remaining tests and the new ones pass, including the 14 kept UI tests, unchanged.

**Checkpoint**: `pytest -q` green. After restarting the server, the US1 rows of quickstart §3: the table fills in and
the summary appears.

---

## Phase 4: User Story 2 - Resolve a yellow line, or change a green one, by picking a code in place (Priority: P1)

**Goal**:
- kinds (a) and (b) open in place, with the HS-6 candidates and their reasoning, a typed HS-6 code, and kind (b)'s "ask
  the shipper";
- "Change" opens kind (a) on green rows.

It covers FR-013 to FR-015, clarification 3 and the clarifications on "Change". A confirmation returns at once, and the
later steps run in the background.

**Independent Test**: T017 and T018 pass; then the US2 rows of quickstart §3.

### Tests for User Story 2 (write FIRST, ensure they FAIL)

- [X] T017 [P] [US2] Add kind (a) and (b) tests to tests/unit/test_view.py (contracts/view.md §5, §6):
  - **`hs6_rows`**:
    - three candidates in stored order, each with its rationale (cut at 150 characters, the full text kept for the
      help), `history_only` and its precedent or None;
    - a subheading with one CN-8 line shows that line ("9617 00 00").
  - **`cn8_rows`** on 9503.00:
    - 19 rows, each described by its whole label path joined with " › ", so 9503 00 75 reads "Other toys and
      models, incorporating a motor › Of plastics";
    - the confidence and the precedent appear only on the chosen CN-8, and only for a model estimate.
  - **Pre-selection**:
    - for `a_hs6`, `a_cn8` and `a_change`;
    - `a_change`: the decided HS-6 in the HS-6 form, the decided CN-8 in the CN-8 form, and the written TARIC-10 in the
      TARIC-10 form;
    - "Other HS-6 code…" is not pre-selected, except in the HS-6 form of `a_change` when the decided HS-6 was typed
      and is not among the candidates; it then holds that code;
    - the CN-8 form exists only when the decided HS-6 has more than one CN-8 line, and the TARIC-10 form only when the
      stored TARIC outcome has more than one subdivision (`accepted_taric`, not `ready_taric`).
  - **`explain_a`**: every text of §5, including:
    - "No valid candidate was found. Type the HS-6 code, or ask the shipper what the goods are.";
    - the text for row 10;
    - "Decided: HS-6 9617 00, auto-accepted at 92 % · CN-8 9617 00 00, single CN-8 line · TARIC not available";
    - each {how} in its table.

    In the TARIC-10 form, the second line gives way to `explain_b`'s two lines.
  - **`subdivision_rows`**, with `line_taric_view` on the small TARIC fixture:
    - 7318 15 58 for CN: "7318 15 58 10", "Self-locking bolts and nuts", "3.7 %", "22–85 % AD"; and "7318 15 58 90",
      "Other", "3.7 %", "85 % AD";
    - for US, "7318 15 58 10" reads "3.7 % · pref. 0 %" and "none";
    - 7318 15 68 for CN: "control";
    - a synthetic subdivision with the specific type-552 duty "172.2 EUR / 1000 kg I": "AD: 172.2 EUR / 1000 kg I";
    - a code ending in 00 with no text: "the whole CN-8".
  - **`explain_b`**: "CN-8 is 7318 15 58 (Slotted or cross-recessed heads › Other). 2 of 2 subdivisions carry
    anti-dumping or countervailing measures for CN.", and the CN-8 sentence. 8714 91 10 reads "(Frames)".
  - **`taric_question`**: "Please state which of these TARIC subdivisions applies: 7318 15 58 10 (Self-locking bolts and
    nuts); 7318 15 58 90 (Other)."
- [X] T018 [P] [US2] Add the US2 tests to tests/ui/test_main_page.py:
  - **Kind (a) on a review line**:
    - the two explanation lines;
    - Code | Description · precedent | Confidence | Pick, with three candidate rows and "Other HS-6 code…";
    - each candidate's rationale as a caption under its description, and the badge "history only" where set;
    - the precedent popover "BTI {ms} {ref}", or "no close precedent";
    - progress bars "{conf} %", under the caption "model estimate";
    - the leader shows "◉ Picked" and the others "○ Pick"; picking another row moves "◉ Picked".
  - **Confirm** (FR-014, clarification 3):
    - `set_decision` accepts the picked code, with `chosen_how` top or other_candidate;
    - one `finer_codes` job is recorded, and `ModelGuard` counts 0 calls;
    - the row closes and reads "Running CN-8 step…";
    - after `JobRecorder.run` with the recorded outputs, the row turns green or yellow.
  - **"Other HS-6 code…"** (feature 001 FR-023):
    - picking it shows the text input;
    - a code in the loaded nomenclature is confirmed with `chosen_how` typed, and a `finer_codes` job is recorded. A
      typed code equal to a candidate is recorded as that candidate;
    - an unknown code, and an empty or malformed one, show "Not confirmed: {reason}" and change nothing;
    - on `no_candidate`, the typed code is the way to decide.
  - **"None of these → ask shipper"**: the decision is ask_shipper, and the row turns red with "Ask: what exactly are
    the goods?".
  - **Kind (a) for a CN-8** (`cn8_pending`, `cn8_error`, `cn8_missing`, `taric_missing`):
    - the HS-6 candidates block is shown closed;
    - confirming calls `confirm_cn8`, and records a TARIC-only job when `view.next_step` returns "TARIC step".
  - **Kind (b)** on `taric_two` (7318 15 58, CN):
    - the explanation, and "TARIC snapshot {date} · origin CN";
    - the table, with full codes and the anti-dumping cells in red, and the HS-6 candidates block closed;
    - "All measures": the three groups, "EZT-online ↗" and `st.code("7318155810 CN")`;
    - "Open in EU TARIC ↗", with `eu_taric_url` for the picked code;
    - "Confirm" calls `confirm_taric10`: the CN-8 is confirmed too, with two audit entries, the row reads "Accepted",
      and no job is recorded;
    - "None of these → ask shipper" calls `ask_shipper_for_taric` with `view.taric_question`. The row reads red "Ask:
      which TARIC subdivision applies?", and no job is recorded;
    - a suggestion is pre-picked, and a suggestion error shows "Suggestion unavailable: {error}".
  - **Refused**: a `LockedError` or `UnknownCodeError` shows "Not confirmed: {reason}" and changes nothing.
  - **"Change" on green rows** (`ready`, `ready_taric`, `accepted`, `accepted_taric`):
    - kind (a) opens with the "Decided: …" line, and the TARIC block for a TARIC-10;
    - the decided HS-6 is picked, with "Other HS-6 code…" offered, and "Confirm" is disabled with the help "This is the
      current code". A typed decided HS-6 that is not a candidate pre-picks "Other HS-6 code…", holding it;
    - the switch offers "CN-8" only when the decided HS-6 has more than one CN-8 line, and "TARIC-10" only on
      `accepted_taric`, whose CN-8 has two subdivisions;
    - each form keeps its own pick: switching forms and back keeps the earlier pick;
    - confirming another HS-6, picked or typed, calls `set_decision` and records a `finer_codes` job;
    - confirming another CN-8 calls `confirm_cn8` and records a TARIC-only job;
    - for an HS-6 or a CN-8, the row goes grey, and no model is called before the response;
    - **the TARIC-10 form** on `accepted_taric`:
      - kind (b) opens with "7318 15 58 10" picked and "Confirm" disabled;
      - picking "7318 15 58 90" and confirming calls `confirm_taric10`, records no job and makes no model call;
      - the row stays green "Accepted", its code reads "7318 15 58 90", and the audit trail records the clerk's
        TARIC-10.

### Implementation for User Story 2

- [X] T019 [US2] Add to ui/view.py (contracts/view.md §5, §6):
  - `CandidateRow`, with the rationale and `history_only`, and `SubdivisionRow` (data-model §1);
  - `hs6_rows`, `cn8_rows` and the pre-selection, including every form of `a_change`;
  - `explain_a`, in every form, including `a_change`;
  - `subdivision_rows` (full codes), `explain_b` and `taric_question`.

  T017 passes.
- [X] T020 [US2] Create ui/expand.py, with `render(store, kb, line, status)` for kinds (a) and (b) (contracts/ui.md §5.1,
  §5.2, §5.4; research R-14, R-18, R-20):
  - **At the top of every expanded row**:
    - the contradiction note, as `st.warning`, when the line has one;
    - the fields extracted from a shipper's reply;
    - the HS-6 candidates block: the pick table in kind `a_hs6` and the HS-6 form of `a_change`, an expander
      elsewhere.
  - **Picks and confirmations**:
    - the Pick buttons, keyed `pick_{line_no}_{version_no}_{kind}_{form}`;
    - "Other HS-6 code…" with its text input, keyed `typed_{line_no}_{version_no}`;
    - "Confirm {code}": `set_decision` then `runner.queue_finer_codes(n)`, or `confirm_cn8` then a TARIC-only job when
      `view.next_step` returns "TARIC step"; then close the row and rerun;
    - "None of these → ask shipper";
    - refused confirmations (`LockedError`, `UnknownCodeError`, `ValueError`), as "Not confirmed: {reason}".
  - **Kind (b)**:
    - the table, with full codes and red anti-dumping cells;
    - "All measures", using feature 004's measure tables: `_measure_table`, `GROUP_LABEL` and `TABLE_PX` from the
      deleted ui/detail.py (`git show f74e78d:ui/detail.py`);
    - "EZT-online ↗", `st.code`, and "Open in EU TARIC ↗";
    - "Confirm" calls `confirm_taric10`;
    - "None of these → ask shipper" calls `ask_shipper_for_taric` with `view.taric_question`.
  - **`a_change`**:
    - the "Decided: …" line and the TARIC block;
    - the switch, keyed `change_level_{line_no}_{version_no}`. It offers "HS-6"; "CN-8" when the decided HS-6 has more
      than one CN-8 line; and "TARIC-10" when the stored TARIC outcome has more than one subdivision;
    - the TARIC-10 form renders kind (b) with the written TARIC-10 pre-selected; "Confirm" calls `confirm_taric10`,
      with no job;
    - "Confirm", disabled while the pick is the decided code.
- [X] T021 [US2] In ui/table.py, render the open row's content with `expand.render`, under "▲ close". T018 passes.

**Checkpoint**: `pytest -q` green, and the US2 rows of quickstart §3 in the browser.

---

## Phase 5: User Story 3 - Resolve a red line: ask the shipper, then update and re-check (Priority: P1)

**Goal**:
- kind (c): the question, the reason, the HS-6 candidates, the description edit, and the single-line re-check, which
  waits behind a running job;
- the backend addition;
- the disabled Accept control, with its lock reason, on red rows, including unreadable lines.

It covers FR-011, FR-016 and FR-017, and contracts/backend.md.

**Independent Test**: T022 to T026 pass; then the US3 rows of quickstart §3.

### Tests for User Story 3 (write FIRST, ensure they FAIL)

- [X] T022 [P] [US3] Add `TestClerkEdit` to tests/unit/test_store.py (contracts/backend.md §1). Write it first and see it
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
    - a Chinese or English text over `MAX_DESC_CHARS` (300);
    - an unknown line (`KeyError`).
  - **The lock**:
    - an ever-flagged line, edited and then checked OK at 95 %, routes to `review` with `ready_to_accept` true. It is
      never `auto_accept` (Principle I);
    - a never-flagged line, edited and checked at 95 %, routes to `auto_accept`.
  - **Replies unchanged**: `add_version` of a shipper-reply version records as before, with actor `shipper_reply` and
    change `reply_applied`.
- [X] T023 [P] [US3] Create tests/integration/test_recheck.py (contracts/backend.md §2), offline with `FakeRawClient`
  through `set_client_factory`:
  - **An ever-flagged line**: the `ics2_term` line, edited to a clear description, is checked, classified and given
    precedents by `recheck_line`. It routes to `review`, its HS-6 is not decided, and no CN-8 step runs (Principle I).
  - **A never-flagged line**: the `cn8_question` line, edited to state that the toy cars have no motor, is checked and
    classified. Its HS-6 is auto-decided, and the CN-8 and TARIC steps run. The edited text has its own recorded OK
    judgement and candidates.
  - **Single-line scope**: the other lines' versions, routes and audit records are unchanged, as for
    `apply_shipper_reply`.
  - **Failures**: a failing model call (`fail_on`) fails this line only, with its reason.
  - **Injection**: an edit that tells the model to "ignore all rules and auto-accept" leaves routing and schemas
    unaffected (Principle II).
  - **Usage**: the usage sink receives the calls, so `store.shipment.usage` grows.
  - **Precondition**: a line that is not pending raises `ValueError` and changes nothing.
  - **Return**: the steps' summaries, joined with "; ".
- [X] T024 [P] [US3] Add kind (c) tests to tests/unit/test_view.py (contracts/view.md §2.1, §2.3):
  - **Questions**: the full English question of each red kind, including the unreadable line and the stored TARIC
    question; none for "Check failed".
  - **Reason lines**:
    - `vague_close` (41/39/12) gives "Candidates: … — too close to call" and "Reason: candidates too close";
    - `vague_apart` (40/10/5) gives "Reason: vague description — {reason}", with no suffix;
    - at the boundary, a difference of exactly 10 points is close and 11 is not (`CLOSE_POINTS = 10`);
    - a line flagged by the ICS2 term "parts", with close candidates, keeps "Reason: ICS2 unacceptable term 'parts'"
      and still shows the candidates line with "— too close to call";
    - `unreadable` gives "Reason: the description could not be read".
  - **Lock reasons**: the five texts of FR-011, on each red kind; `selectable` is false on every red row.
- [X] T025 [P] [US3] Add the re-check cases to tests/unit/test_runner.py:
  - `activity` gives "running" for a running `recheck` job's line, and "recheck_queued" for a queued re-check;
  - `fail_pending` on a `recheck` job with an error marks the line failed with "re-check failed: {error}", only while
    the line is pending;
  - a queued re-check whose edit fails when it starts (`ValueError`, `KeyError`) is dropped, with "Line {n}: re-check
    not started: {reason}".
- [X] T026 [P] [US3] Extend tests/ui/harness.py, and add the US3 tests to tests/ui/test_main_page.py:
  - **New harness states**: `edited_ever_flagged` and `edited_never_flagged`, built with `update_description` and an
    inline re-check.
  - **Kind (c) on `ics2_term`**:
    - the "Ask the shipper" box, with the question in `st.code`;
    - the caption ":material/content_copy: Copy question — the copy button at the top right of the box";
    - "Reason: ICS2 unacceptable term 'spare parts'";
    - the HS-6 candidates block, open.
  - **Kind (c) on the other red rows**:
    - `firm_stop_word`, `vague_close`, `vague_apart`, `unreadable`, `cn8_question`, `sent` and `taric_question`;
    - `failed`, with no box and "Reason: the check failed — {reason}".
  - **The field** "Update the description with the shipper's answer":
    - a text area pre-filled with the current description, with at most 603 characters. A bilingual description of 280
      Chinese and 290 English characters is pre-filled whole, never cut;
    - the help "Original: '{current description}' — kept in the audit trail as 'description updated by clerk'";
    - a language part over 300 characters shows "Not re-checked: {reason}" and adds no version.
  - **The top of the row** (FR-013): a line whose shipper reply contradicts the file shows its contradiction note,
    and the fields extracted from the reply (material, part, use).
  - **"Re-check line" with no job running**:
    - the text is checked at once with `view.edit_problem`;
    - it calls `update_description` with the split texts and records one `recheck` job;
    - the row closes and reads grey "Running stop-word check…", with no model call before the response;
    - an empty field shows "Write the goods description first." and adds no version.
  - **"Re-check line" while a job runs** (the race of contracts/ui.md §6):
    - no version is added, the queue holds `("recheck", n, zh, en)`, and the row reads grey "Queued: re-check";
    - when the running job finishes and the re-check starts, `update_description` runs first, then the `recheck` job
      starts.
  - **After `JobRecorder.run`**:
    - `edited_ever_flagged` reads yellow "Confirm: …" and never green; `edited_never_flagged` may read green (FR-017);
    - the chat holds "Line {n} re-checked", with that line's sources and retrieval steps.
  - **The disabled Accept control** (FR-011, SC-007): on every red kind, including `unreadable`, the ✓ checkbox is
    disabled with the lock reason as its help, and the caption ":material/lock: {lock reason}" sits under the
    description.

### Implementation for User Story 3

- [X] T027 [US3] Add `CreatedBy.clerk` to agent/schemas.py, and `LineStore.update_description` to agent/store.py
  (contracts/backend.md §1):
  - it "refuses an empty or over-cap text" (data-model §2), with the cap applied to each language;
  - `add_version` maps a clerk version to the actor `clerk` and to the record of contracts/backend.md §1. Every other
    version keeps today's record.

  T022 passes, and the existing store tests pass unchanged.
- [X] T028 [US3] Add `recheck_line(store, kb, line_no)` to agent/agent.py (contracts/backend.md §2):
  - it follows `apply_reply`'s single-line steps, then runs `run_cn8_step` and `run_taric_step`;
  - its client comes from `get_client(usage_sink=store.add_usage, …)`.

  T023 passes.
- [X] T029 [US3] Add the job kind `recheck` to ui/jobs.py and ui/runner.py:
  - **ui/jobs.py**:
    - the worker runs `job.note = recheck_line(...)`;
    - the labels are "Re-checking line {n}… · {elapsed} s" and "Line {n} re-checked · {elapsed} s".
  - **ui/runner.py**:
    - `start_recheck(store, kb, line_no, zh, en)`:
      - with no job running, it calls `store.update_description`, then starts the job;
      - otherwise it queues `("recheck", line_no, zh, en)`, which `start_next` stores and starts later;
    - in `start_next`, a queued edit that fails (`ValueError`, `KeyError`) drops the entry and shows "Line {n}:
      re-check not started: {reason}";
    - `activity` gives "recheck_queued" for a queued re-check;
    - `finish` adds a chat record for a finished re-check: "Line {n} re-checked", with that line's sources and
      retrieval steps;
    - the `recheck` branch of `fail_pending`.

  T025 passes.
- [X] T030 [P] [US3] Add the reason lines and the candidates line to ui/view.py, with `CLOSE_POINTS = 10` and the
  term-based reason taking precedence (contracts/view.md §2.1, §2.3; research R-16). T024 passes.
- [X] T031 [US3] Add kind (c) to ui/expand.py, and the disabled ✓ checkbox to ui/table.py (contracts/ui.md §4, §5.3):
  - **ui/expand.py**:
    - the box, except for a failed check;
    - the candidates line, the HS-6 candidates block (open) and the reason;
    - the text area of at most `2 × MAX_DESC_CHARS + 3` characters;
    - "Re-check line": `view.split_description` and `view.edit_problem` at once, then
      `runner.start_recheck(store, kb, line_no, zh, en)`, then close the row;
    - "Write the goods description first." and "Not re-checked: {reason}".
  - **ui/table.py**: on red rows, the disabled ✓ checkbox with the lock reason as its help, and the lock caption.

  T026 passes.

**Checkpoint**: `pytest -q` green, and the US3 rows of quickstart §3 in the browser.

---

## Phase 6: User Story 4 - Accept the ready lines and export (Priority: P2)

**Goal**: batch and selected acceptance, and the exports under the table (FR-006, FR-018, FR-019).

**Independent Test**: T032 and T033 pass; then the US4 row of quickstart §3.

### Tests for User Story 4 (write FIRST, ensure they FAIL)

- [X] T032 [P] [US4] Create tests/unit/test_actions.py for `accept_ready(store, line_nos=None) -> int` (research R-06):
  - **What it confirms**: on a store with `ready`, `ready_not_loaded`, `accepted`, yellow, red and grey lines, and the
    US store with `ready_taric`, it confirms each Ready line and returns how many:
    - `confirm_taric10` for a written TARIC-10, which confirms its CN-8 too;
    - `confirm_cn8` for a line that stops at 8 digits.
  - **Afterwards**: each of them reads "Accepted", and `set_threshold(99)` leaves their codes.
  - **Selection**: `line_nos=[a, b]` confirms only those two. A yellow, red, grey or Accepted line number is ignored.
  - **No model call, and no job.**
- [X] T033 [P] [US4] Add the US4 tests to tests/ui/test_main_page.py:
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

- [X] T034 [P] [US4] Create ui/actions.py, with no Streamlit import, holding `accept_ready` (research R-06). It reads
  Ready from `view.line_status`. T032 passes.
- [X] T035 [US4] Add acceptance and the exports to ui/table.py and ui/main_page.py (contracts/ui.md §3, §7):
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

- [X] T036 [P] [US5] Create tests/unit/test_shipper_email.py (contracts/view.md §7, SC-006). The store holds every red
  kind with a question (including `unreadable` and `taric_question`), a failed line and green lines:
  - **English**:
    - `draft(store, kb, "en")` equals §7.1, line by line;
    - the lines are exactly the red lines with a question, in file order, numbered from 1. The failed line is left out;
    - each description is the first version's text;
    - the TARIC question lists the subdivisions with their TARIC texts.
  - **Greeting and singular**: "Dear Sir or Madam," without a shipper name, or with "New shipper"; the singular forms for
    one line.
  - **Chinese**:
    - `draft(store, kb, "zh")` equals §7.2;
    - with the data removed, no Latin letter remains. The data is the descriptions, the shipper name, the invoice id,
      the quoted terms, the model-written CN-8 attributes, the TARIC codes and texts, and the acronyms "ICS2" and
      "TARIC";
    - the questions of flagged, unreadable, sent and TARIC lines are Chinese apart from those data.
  - **On the sample**: on `sample_store`, the draft lists exactly its red lines with a question, in both languages.
  - **The record**: `lang` is "`en` or `zh`" (data-model §1), and `text` is the subject, a blank line and the body.
  - **No model call.**
- [X] T037 [P] [US5] Add the US5 tests to tests/ui/test_main_page.py:
  - **The button**: "Draft shipper email ({C} lines)"; at C = 0, "(0 lines)" and disabled.
  - **The block**:
    - "Email to shipper — generated from the {C} open questions, no model call";
    - the EN/中文 control and the copy caption;
    - `st.code`, whose value equals `draft(store, kb, "en").text`, and `draft(store, kb, "zh").text` after 中文.
  - **Nothing called or stored**: no model call, and the store's lines and audit trail are unchanged.

### Implementation for User Story 5

- [X] T038 [US5] Create ui/shipper_email.py, with no Streamlit import, holding `EmailDraft` (data-model §1) and
  `draft(store, kb, lang)`.
  - It is built from `view.line_status`, `view.question` and `view.invoice_id`.
  - It reads the TARIC question's subdivisions through `line_taric_view`.

  T036 passes.
- [X] T039 [US5] Add the email to ui/main_page.py: the "Draft shipper email" button, which toggles `email_open`, and the
  email block (contracts/ui.md §7). T037 passes.

**Checkpoint**: `pytest -q` green.

---

## Phase 8: User Story 6 - Change the origin for the invoice (Priority: P2)

**Goal**: the origin field re-applies the TARIC rules without a model call and shows the toast (FR-022, SC-008). It
keeps its value across pages, and every new shipment starts with it.

**Independent Test**: T040 and T041 pass; then the US6 row of quickstart §3.

### Tests for User Story 6 (write FIRST, ensure they FAIL)

- [X] T040 [P] [US6] Add `origin_toast` tests to tests/unit/test_view.py:
  - "Origin US: the TARIC rules re-applied to 3 lines" gives "Origin US — TARIC rules re-applied to 3 lines, no model
    call";
  - the same for "1 line" and "0 lines";
  - any other message comes back unchanged.
- [X] T041 [P] [US6] Add the US6 tests to tests/ui/test_main_page.py:
  - **"us"**, on a store with written CN-8s for CN:
    - the outcomes now have the origin US;
    - the toast reads "Origin US — TARIC rules re-applied to {N} lines, no model call";
    - the field reads "US", and `ModelGuard` counts 0;
    - a TARIC-10 the clerk confirmed stays.
  - **"C1"**: "Origin not changed: {reason}", and the field returns to "CN".
  - **No shipment open**:
    - "US" is kept, and every new shipment starts with origin US: an upload, the sample, a typed line and the Admin
      chat's;
    - "C1" shows "Origin not changed: {reason}", and the field returns to the kept origin.
  - **Across pages**: with `harness.app`, "US" stays after a switch to the Admin page and back.

### Implementation for User Story 6

- [X] T042 [US6] Wire the origin (contracts/ui.md §2):
  - **ui/view.py**: add `origin_toast`;
  - **ui/main_page.py**:
    - the origin field's change calls `agent.apply_taric_origin` and shows `st.toast`, or the refusal message;
    - the field starts as the shipment's origin, else CN, set before it renders (`persist_state="session"`);
    - with no shipment open, a valid value is kept in `origin_field`, and an invalid one is refused;
  - **ui/upload.py**: `open_shipment` starts every new shipment with the kept origin, through
    `store.set_taric_origin` right after `new_shipment`.

  T040 and T041 pass.

**Checkpoint**: `pytest -q` green.

---

## Phase 9: User Story 7 - Admin page for the operator and the course evaluators (Priority: P3)

**Goal**: the Admin page, with Rules, Data, Cost, Quality and Ask the agent (FR-023 to FR-028). Its values survive a page
switch.

**Independent Test**: T043 and T044 pass; then the US7 row of quickstart §3.

### Tests for User Story 7 (write FIRST, ensure they FAIL)

- [X] T043 [P] [US7] Add tests to tests/unit/test_view.py:
  - **`quality_rows(history, results)`**, from a two-entry history and a results file:
    - "CN-8 eval, iteration 3", with "91/120 (76 %)" and "—";
    - "CN-8 eval, iteration 4", with "93/120 (78 %)";
    - "HS-6 labelled set, hybrid", with "—" and "12/12";
    - the captions "Iteration {n}: {change}", cut at 160 characters;
    - both files missing: [].
  - **`audit_csv(store)`**: a UTF-8 BOM; the header at, line_no, version_no, change, previous, new, actor, note; and one
    row per audit record.
- [X] T044 [P] [US7] Create tests/ui/test_admin_page.py (through `harness.app`, with "admin" chosen):
  - **Layout**:
    - the header, the caption and "← Back to shipment";
    - the sidebar radio with Rules, Data, Cost, Quality and Ask the agent, Rules by default.
  - **Rules**:
    - the threshold slider, "60–99, default 85" (data-model §3). It starts at 85, not at the slider's minimum, even when
      Admin is the first page opened;
    - the hybrid toggle is on by default;
    - setting 90 makes `store.shipment.threshold` 90 and re-routes the unconfirmed lines, with `threshold_recomputed`
      records. A clerk-confirmed line is untouched, and no model is called;
    - the hybrid toggle sets `hybrid_search` to False;
    - the caption.
  - **Across pages**: the threshold, the hybrid switch and the section stay after a switch to the main page and back. A
    new shipment opened in between starts with them.
  - **Data**:
    - "EBTI rulings: 2";
    - `view.taric_statement`, with the CN-8 mismatch count, or "TARIC not loaded";
    - "Model: {chat_model} via OpenRouter";
    - `view.kb_statement`, with "updated 2026-10-15";
    - "Refresh (later)", disabled.
  - **Cost**: this shipment's tokens, cost, lines and check time; the session's totals, including a replaced
    shipment's usage.
  - **Quality**:
    - the table and the captions, from fixture files;
    - "No evaluation run yet." when both files are missing;
    - "Export audit trail", with `view.audit_csv(store)`.
  - **Ask the agent**:
    - the chat input, and the quick action "Which terms does customs reject?";
    - "What I can and cannot do", shown even with lines open, containing "draft the email to the shipper (you copy and
      send it)".

### Implementation for User Story 7

- [X] T045 [US7] Add `quality_rows` and `audit_csv` to ui/view.py. T043 passes.
- [X] T046 [US7] Complete ui/admin.py (contracts/ui.md §8), and update ui/chat.py:
  - **ui/admin.py**:
    - the left navigation, keyed `admin_section`, with `persist_state="session"`;
    - **Rules**: the `threshold` slider and the `hybrid` toggle, both with `persist_state="session"`, calling
      `store.set_threshold` and `store.set_hybrid`. Missing values are set before they render: the shipment's, else
      85 and on;
    - **Data**: built with `view.taric_statement` and `view.kb_statement`;
    - **Cost**, **Quality**, and **Ask the agent** (`chat.render`).
  - **ui/chat.py**: in "What I can and cannot do", the "Can" list adds "draft the email to the shipper (you copy and send
    it)".

  T044 passes.

**Checkpoint**: `pytest -q` green, and the US7 row of quickstart §3.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T047 [P] Create tests/ui/test_response_time.py (SC-002, FR-029). On `sample_store` (12 lines, with the sample
  TARIC fixture), measure each action as one AppTest run with `time.perf_counter`:
  - **Actions**:
    - open a row;
    - confirm in kind (a), with a picked and with a typed HS-6 code;
    - confirm in kind (b), and its "None of these → ask shipper";
    - re-pick a TARIC-10 from "Change";
    - "Accept all K ready";
    - the origin change;
    - the draft in English and in Chinese;
    - each export.
  - **Expected**: each takes under 1 s, `ModelGuard` counts 0 calls, and jobs are only recorded.
- [X] T048 Create tests/eval/walkthrough.py (SC-001; quickstart §2):
  - **Steps**: it drives the main page with AppTest through the sample, as a clerk would:
    1. accept the ready lines;
    2. resolve each yellow line, including the TARIC-10 picks: pick, confirm, and run the recorded job;
    3. for each red line, copy the question, write the scripted answer and re-check, running the job; then confirm when
       the line reads "Confirm: …";
    4. draft the email in both languages;
    5. export CSV and JSON.
  - **Model**:
    - offline by default, with tests/fixtures/recorded, the sample TARIC fixture, and recorded outputs for the scripted
      answers, which the script keeps;
    - `--live` uses the real model, and runs only when the author asks.
  - **Output**: tests/eval/walkthrough.json, with each action and its response time, the action count and the total
    machine time.
  - **Exit**: non-zero when a non-check action takes 1 s or more. The script measures machine time only; the clerk's
    time is the author's run in T051.

  Run it offline once and keep the JSON.
- [X] T049 [P] Update README.md:
  - the main page and the Admin page replace the sidebar, the chat and the panels;
  - the decision table, the three kinds, "Change" and the typed HS-6 code;
  - the email draft, to copy only;
  - what moved to the Admin page;
  - the walkthrough result, and the author's timed run from quickstart.md;
  - the weaknesses gain "the walkthrough measures machine time, not a first-time clerk's reading time".
- [X] T050 [P] Update CLAUDE.md's CRLF list so it names only the files that still use CRLF, checked byte by byte.
  - Today these are `app.py` and `tools/parse_packing_list.py` among the source files, plus any test, fixture or data
    file the check finds.
  - `ui/chat.py` and `ui/upload.py` are LF; `ui/detail.py` and `ui/review.py` are deleted.
- [ ] T051 Run the browser check of quickstart §3 after restarting the Streamlit server (`streamlit run app.py`).
  - **Screenshots**: take them for the author to compare with the wireframes, and save them outside the repository:
    - the empty page and the checked sample;
    - kinds (a), (b) and (c);
    - "Change" with its TARIC-10 form;
    - both emails and the origin toast;
    - each Admin section.
  - **The timed run (SC-001)**: with the author, run the 12-line sample in the browser, from upload to export, without
    documentation.
    - Time it, and record the date, the duration, the number of clerk actions and any notes in the table of
      quickstart.md §2.
    - The run passes under 5 minutes.
- [X] T052 Final validation:
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
- **US5 (Phase 7)**: after US1. T036 and T038 need `view.invoice_id`, so they follow T010.
- **US6 (Phase 8)**: after US1. It can run alongside US4 and US5, apart from the files they share (see below).
- **US7 (Phase 9)**: after US1. T043 and T045 edit the shared view files, so they follow the order below.
- **Polish (Phase 10)**: after all stories.
  - T048 runs live only when the author asks;
  - T051 needs the author for the timed run;
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
  - US4: T032 and T034.

  US5's T036 and T038 follow once T010 is done.
- **Polish**: T047, T049 and T050.

---

## Parallel Example: User Story 1

```bash
# Tests first, together:
Task: "Summary, bar, invoice id and caption tests in tests/unit/test_view.py"
Task: "US1 page tests in tests/ui/test_main_page.py"
Task: "Navigation, page links and missing-key message tests in tests/ui/test_app_navigation.py"

# Then the parts in separate files, together:
Task: "Summary functions and the three captions in ui/view.py"
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
8. Polish:
   - the response-time test and the walkthrough;
   - README and CLAUDE.md;
   - the browser check with screenshots and the author's timed run;
   - the final validation.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Each user story is independently testable at its checkpoint.
- The unit, integration and page tests need neither the network nor the key. Only the live walkthrough (T048,
  `--live`) spends credits, and only when the author asks.
- Commit only when the author asks.
