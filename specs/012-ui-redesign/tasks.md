---

description: "Task list for feature 012, the UI redesign from first customer feedback"
---

# Tasks: UI Redesign from First Customer Feedback

**Input**: Design documents from `specs/012-ui-redesign/`

**Prerequisites**: plan.md and spec.md. The reference is `docs/design/012-wireframe-final.png`.

**Tests**: included and written first in each step. The brief asks for them (FR-017), and constitution Principle VII
asks for test-first work. All tests run offline.

**Organization**: tasks are grouped by the brief's steps, and each step is committed on its own. The user stories are
those of spec.md: US1 check a file, US2 decide a line, US3 a single line, US4 ask the shipper, US5 Advanced. Every
file keeps its line endings: all are LF except `.streamlit/config.toml`, which is CRLF in the working tree.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to

---

## Phase 1: Setup

- [X] T001 Create the branch `012-ui-redesign` from `main` (`1747d94`) and point `.specify/feature.json` at
  `specs/012-ui-redesign`
- [X] T002 Report the Step 0 inventory; record the decisions D1 to D19 in specs/012-ui-redesign/spec.md
- [X] T003 Write specs/012-ui-redesign/spec.md, plan.md and tasks.md, and commit them with
  docs/design/012-wireframe-final.png and docs/design/012-wireframe-v4.png

---

## Phase 2: Governance (blocks all code)

- [ ] T004 The author runs `/speckit-constitution` with the 1.8.0 draft in specs/012-ui-redesign/plan.md, which
  amends the UI Design Contract
- [ ] T005 The author answers Q1 (spec, "Open question before Step 2"): block 3 as the vote summary by code, or the
  individual rulings, which would change the stored vote. Needed before T020 and T028.

**Checkpoint**: Step 1's code starts only after T004.

---

## Phase 3: Step 1, layout (US1, US3, US5)

**Goal**: the new frame of the page:

- the header with the Origin box;
- the two tabs with full-width primary check buttons;
- the status line;
- the Advanced link;
- no sidebar;
- base font size 18.

**Independent Test**: AppTest on the main and Admin pages with the harness's stores.

### Tests for Step 1

- [ ] T006 [P] [US1] tests/ui/test_main_page.py:
  - the title, the subtitle, and the Origin box with the D1 caption;
  - the tabs "Upload file" and "Check a single line";
  - "Check all lines" is primary and full width;
  - "Load sample invoice";
  - a dropped file starts nothing until "Check all lines";
  - the status line.
- [ ] T007 [P] [US3] tests/ui/test_main_page.py: "Check this line" starts the typed-line job with the text, and the
  line's row opens when its job ends (a new test of FR-017)
- [ ] T008 [P] [US1] tests/ui/test_main_page.py: an Origin change shows the re-apply note and calls no model (a new
  test of FR-017)
- [ ] T009 [P] [US5] tests/ui/test_admin_page.py and tests/ui/test_app_navigation.py:
  - no sidebar on either page;
  - the Admin section switch;
  - the "Advanced…" link at the bottom of the main page.

### Implementation for Step 1

- [ ] T010 [US1] .streamlit/config.toml: `baseFontSize = 18`; the file keeps its CRLF line endings
- [ ] T011 [US1] ui/view.py: `status_line`, with no Streamlit import
- [ ] T012 [US1] ui/main_page.py: the header with the Origin box (today's field and callback), the tabs, the status
  line, and the Advanced link at the bottom
- [ ] T013 [US1] ui/upload.py:
  - the uploader and "Load sample invoice" set the pending file;
  - "Check all lines" starts the check through today's `begin` and `start_check`;
  - the replace prompt stays as today.
- [ ] T014 [US3] ui/main_page.py: the single-line tab and "Check this line", using today's `check_typed_line`; the
  new line's row opens when its job ends
- [ ] T015 [US5] ui/admin.py: a segmented control instead of `st.sidebar.radio`
- [ ] T016 tests/ui/*: rewrite the existing tests of the header, the drop zone, the summary's place and the Admin
  navigation to the new layout, keeping each test's intent
- [ ] T017 Run `pytest -q`, then commit "feat(012): step 1, layout"

**Checkpoint**: the frame is in place; the results still render as today below it.

---

## Phase 4: Step 2, results (US1, US2, US4)

**Goal**:

- the counts row;
- the sorted list from columns and badges;
- the open line in four blocks plus Accept and Ask shipper;
- the shipper email draft;
- the export column.

**Independent Test**: AppTest on seeded lines of every kind, and unit tests of the view helpers and the export.

### Tests for Step 2

- [ ] T018 [P] [US1] tests/unit/test_view.py: `sort_group`, `row_cells` (badge, need text, current text, HS-6,
  Conf.) and the counts
- [ ] T019 [P] [US1] tests/ui/test_main_page.py:
  - the counts row: three metrics, "Accept all K ready", "Download CSV" and "JSON";
  - the list order and the 50-line pages;
  - the row cells.
- [ ] T020 [P] [US2] tests/ui/test_main_page.py: the open line's blocks for each kind: an HS-6 to choose, a CN-8 to
  pick, a subdivision to pick, ready, accepted, and ask
- [ ] T021 [P] [US2] tests/ui/test_main_page.py: a radio choice then "Accept" updates the export: `decided_code`,
  `route_set_by` "clerk" and `clerk_changed` true (a new test of FR-017)
- [ ] T022 [P] [US2] tests/ui/test_main_page.py: "Re-check this line" on an edited description re-checks that line
  only and changes only its row (a new test of FR-017)
- [ ] T023 [P] [US4] tests/ui/test_main_page.py: "Ask shipper" on a row adds the line to the draft; the draft section
  shows its count and each red line's update field (a new test of FR-017)
- [ ] T024 [P] tests/unit: `clerk_changed` in the CSV and the JSON exports

### Implementation for Step 2

- [ ] T025 [US1] ui/view.py: `sort_group`, `row_cells`, the need text and the block texts, with no Streamlit import
- [ ] T026 [US1] ui/main_page.py: the counts row: `st.metric(border=True)` three times, "Accept all K ready",
  "Download CSV" and "JSON"
- [ ] T027 [US1] ui/table.py: rows from `st.columns` with `st.badge`; the sort; 50 lines per page; the open line in an
  `st.expander`
- [ ] T028 [US2] ui/expand.py: blocks 1 to 4 and the decision buttons on today's callbacks (D5, D6, D7, Q1)
- [ ] T029 [US4] ui/main_page.py: the shipper email draft section with each red line's update field (D18)
- [ ] T030 agent/store.py: `clerk_changed` in `CSV_COLUMNS`, `export_rows` and the JSON lines (D13), the only store
  change
- [ ] T031 tests/ui/*: rewrite the existing table, row, summary, email and export tests to the new layout, keeping
  each test's intent
- [ ] T032 Run `pytest -q`, then commit "feat(012): step 2, results"

**Checkpoint**: the clerk can check, read and decide every line on the new page.

---

## Phase 5: Step 3, polish (native)

- [ ] T033 [P] ui/expand.py: confidence bars beside the candidates (`st.progress`)
- [ ] T034 [P] ui/main_page.py and ui/table.py: card and container spacing (`st.container` gaps, `st.divider`)
- [ ] T035 [P] tests/unit/test_native_ui.py: no `unsafe_allow_html`, `st.html` or components in app.py and ui/
  (SC-004)
- [ ] T036 README.md: "What the clerk sees" for the new layout
- [ ] T037 Run `pytest -q`, including tests/ui/test_response_time.py (SC-007), then commit "feat(012): step 3,
  polish"

---

## Dependencies & Execution Order

- T004 comes before any code (T010 onwards). T005 comes before T020 and T028.
- Within each step, the tests come before the code.
- Step 1 comes before Step 2, and Step 2 before Step 3. Each step ends with its own commit. Nothing is merged.
