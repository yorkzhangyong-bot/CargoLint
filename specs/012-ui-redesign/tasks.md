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

**Hard rule** (2026-10-29): only files under `ui/` and `app.py` change, besides this feature's tests and documents.
Nothing in `agent/`, `tools/`, `rag/`, routing, the store schema or any behaviour changes. A UI change that seems to
need a function change is asked first. The theme file (T010) is the one exception, flagged to the author.

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

- [X] T004 Run `/speckit-constitution` with the 1.8.0 draft in specs/012-ui-redesign/plan.md, which amends the UI
  Design Contract. Run for the author on 2026-10-29, with the counts row and the "HS code" column aligned to the
  spec's later decisions
- [X] T005 The author answers Q1: the default, so block 3 is the vote summary by code, with no store change

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

- [X] T006 [P] [US1] tests/ui/test_main_page.py:
  - the title, the subtitle, and the Origin box: a selectbox over the static ISO list, CN by default, with the D1
    caption;
  - the tabs "Upload file" and "Check a single line";
  - "Check all lines" is primary and full width;
  - "Load sample invoice";
  - a dropped file starts nothing until "Check all lines";
  - the status line.
- [X] T007 [P] [US3] tests/ui/test_main_page.py: "Check this line" starts the typed-line job with the text, and the
  line's row opens when its job ends (a new test of FR-017)
- [X] T008 [P] [US1] tests/ui/test_main_page.py: choosing another Origin in the selectbox shows the re-apply note and
  calls no model (a new test of FR-017)
- [X] T009 [P] [US5] tests/ui/test_admin_page.py and tests/ui/test_app_navigation.py:
  - no sidebar on either page;
  - the Admin section switch;
  - the "Advanced…" link at the bottom of the main page.

### Implementation for Step 1

- [X] T010 [US1] .streamlit/config.toml: `baseFontSize = 18`; the file keeps its CRLF line endings. This is the one
  file outside the hard rule, flagged to the author
- [X] T011 [US1] ui/view.py: `status_line` and the static list of ISO two-letter codes, with no Streamlit import
- [X] T012 [US1] ui/main_page.py: the header with the Origin box (a selectbox over the ISO list, using today's origin
  callback), the tabs, the status line, and the Advanced link at the bottom. Done on 2026-10-29:
  - the TARIC snapshot date stays as a caption in the Origin box (Principle I: the snapshot date is displayed);
  - the queue notes and the job messages moved under the status line (D10);
  - "+ Check one more line" is removed: the single-line tab replaces it;
  - the header no longer names the file; the status line names it while the file is read.
- [X] T013 [US1] ui/upload.py:
  - the uploader and "Load sample invoice" set the pending file;
  - "Check all lines" starts the check through today's `begin` and `start_check`;
  - the replace prompt stays as today; it now follows "Check all lines" in place of the button;
  - a caption "Ready to check: <file>" names the pending file, which the sample button otherwise does not show.
- [X] T014 [US3] ui/main_page.py: the single-line tab and "Check this line", using today's `check_typed_line`; the
  new line's row opens when its job ends. The field and the button are a form, so Enter checks the line too, as
  "Check one line" did; behind a running job the line waits in the queue.
- [X] T015 [US5] ui/admin.py: a segmented control instead of `st.sidebar.radio`
- [X] T016 tests/ui/*: rewrite the existing tests of the header, the drop zone, the summary's place and the Admin
  navigation to the new layout, keeping each test's intent. tests/eval/walkthrough.py opens the sample with "Load
  sample invoice" and "Check all lines" (offline run: 58 clerk actions, all 12 lines accepted, no failure).
- [X] T017 Run `pytest -q`, then commit "feat(012): step 1, layout"

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

- [X] T018 [P] [US1] tests/unit/test_view.py: `sort_group`, `row_cells` (badge, need text, current text, HS code,
  Conf.) and the counts. The HS code is the dotted HS-6 before a decision and today's 8- or 10-digit display after it.
  Also, from the Step 1 review: the Origin list with TARIC's six codes outside ISO, and the status line naming the
  file
- [X] T019 [P] [US1] tests/ui/test_main_page.py:
  - the counts row: three bordered cards with coloured counts, "Accept all K ready", "Download CSV" and "JSON";
  - the list order and the 50-line pages;
  - the row cells.
- [X] T020 [P] [US2] tests/ui/test_main_page.py: the open line's blocks for each kind: an HS-6 to choose, a CN-8 to
  pick, a subdivision to pick, ready, accepted, and ask
- [X] T021 [P] [US2] tests/ui/test_main_page.py: a radio choice then "Accept" updates the export: `decided_code`,
  `route_set_by` "clerk" and `clerk_changed` true (a new test of FR-017)
- [X] T022 [P] [US2] tests/ui/test_main_page.py: "Re-check this line" on an edited description re-checks that line
  only and changes only its row (a new test of FR-017)
- [X] T023 [P] [US4] tests/ui/test_main_page.py: "Ask shipper" on a row adds the line to the draft; the draft section
  shows its count and each red line's update field (a new test of FR-017)
- [X] T024 [P] tests/unit: `clerk_changed` in the CSV and the JSON downloads (FR-013, confirmed after Step 1)

### Implementation for Step 2

- [X] T025 [US1] ui/view.py: `sort_group`, `row_cells`, the need text and the block texts, with no Streamlit import;
  the six TARIC-only Origin codes; the file name in the status line
- [X] T026 [US1] ui/main_page.py: the counts row: three `st.container(border=True)` cards with the counts in `:green`,
  `:orange` and `:red` markdown, then "Accept all K ready", "Download CSV" and "JSON"
- [X] T027 [US1] ui/table.py: rows from `st.columns` with `st.badge` and the "HS code" column; the sort; 50 lines per
  page; the open line in an `st.expander`. Each row is a keyed container (`line_{n}`); the need or current description
  is a caption, as in the picture; a line that opens by itself shows its page
- [X] T028 [US2] ui/expand.py: blocks 1 to 4 and the decision buttons on today's callbacks (D5, D6, D7, Q1). Done on
  2026-10-29:
  - "Change the code at" offers CN-8 and TARIC-10 only; the HS-6 changes through block 2 (`view.change_forms` follows);
  - a candidate's label is its subheading's, after its heading's when it alone says little ("Other"), cut at 100
    characters;
  - a red line's reason and question (with its copy button) are in block 1; "Accept" shows its lock reason, and "Ask
    shipper" is disabled because the line asks already.
- [X] T029 [US4] ui/main_page.py: the shipper email draft section with each red line's update field (D18): each line
  with a question in the draft, its field fitted to its text
- [X] T030 `clerk_changed` in the UI's downloads (ui/view.py, ui/main_page.py), built from the store's export rows and
  the line versions; `agent/store.py` is not changed (FR-013, confirmed by the author after Step 1). Narrowed after
  Step 2 to the clerk's overrides only (done in Step 3); after Step 3, a CN-8 or TARIC-10 other than the model's
  offer counts too, read from the audit trail and the TARIC suggestion
- [X] T031 tests/ui/*: rewrite the existing table, row, summary, email and export tests to the new layout, keeping
  each test's intent. "Accept n selected" is gone with its test (D8). tests/ui/test_response_time.py and
  tests/eval/walkthrough.py use "Accept" and "Ask shipper" (offline walkthrough: 57 clerk actions, all 12 lines
  accepted, no failure). `view.summary_text`, `split_bar`, `accept_selected_label`, `email_label`,
  `candidates_line` and the status dots went with the elements they served, with their unit tests
- [X] T032 Run `pytest -q`, then commit "feat(012): step 2, results"

**Checkpoint**: the clerk can check, read and decide every line on the new page.

---

## Phase 5: Step 3, polish (native)

- [X] T033 [P] ui/expand.py: confidence bars beside the candidates (`st.progress`). The bars stand in a column beside
  the radio, 7 px apart, so each sits beside its option at base font 18; a candidate's label is cut to fit one line
- [X] T034 [P] ui/main_page.py and ui/table.py: card and container spacing (`st.container` gaps, `st.divider`). Done
  on 2026-10-29: the rows sit 4.5 px apart (gap "xxsmall"), as close as in the picture; `st.divider` between rows was
  tried and dropped, as its margins put the rows 109 px apart. Also: bold badge labels, the asking lines' update
  fields folded under the draft (Step 2 review), and an arrow before the Advanced link. After the author's check:
  the small "JSON" sits beside "Download CSV", so both downloads are level with "Accept all K ready"
- [X] T035 [P] tests/unit/test_native_ui.py: no `unsafe_allow_html`, `st.html` or components in app.py and ui/
  (SC-004)
- [X] T036 README.md: "What the clerk sees" for the new layout
- [X] T037 Run `pytest -q`, including tests/ui/test_response_time.py (SC-007), then commit "feat(012): step 3,
  polish". On 2026-10-29: 1275 passed, 4 deselected
- [X] T038 Constitution 1.8.1 (PATCH), at the end of Step 3 when the wording is final: the four remaining "summary bar"
  and "decision table" mentions follow the 012 layout (`/speckit-constitution`). Run on 2026-10-29: Principle VI (the
  count cards, the list of lines, and the same bullet's "export under the table", now the downloads beside the
  cards) and the Architecture flow
- [X] T039 After the author's check of the UI (2026-10-29): "Download CSV" level with "Accept all K ready"; no JSON
  download anywhere in the app (`view.export_json` gone); no "Advanced" link on the main page, the Admin page keeping
  `/admin`; no update fields under the email draft (the expander "Shipper's answers…" is gone; block 1 of the open
  row keeps the field). ui/main_page.py, ui/expand.py, ui/view.py, app.py, the tests, feature 001's FR-041 and
  README.md; constitution 1.9.0 (`/speckit-constitution`)

---

## Dependencies & Execution Order

- T004 comes before any code (T010 onwards). T005 came before T020 and T028. T038 closes Step 3; T039 follows the
  author's check of the UI.
- Within each step, the tests come before the code.
- Step 1 comes before Step 2, and Step 2 before Step 3. Each step ends with its own commit. Nothing is merged.
