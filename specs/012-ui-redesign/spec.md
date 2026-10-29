# Feature Specification: UI Redesign from First Customer Feedback

**Feature Branch**: `012-ui-redesign`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "UI redesign from first customer feedback ("text too small, important buttons not
prominent")". The brief, given on 2026-10-29, had five parts:

- Step 0: an inventory of today's UI elements.
- Step 1: the layout (no sidebar, a header with "Advanced", tabs for a file and a single line, a primary check
  button, base font size 18).
- Step 2: the results (three count cards, a sorted list built with columns and expanders, an open row in five
  blocks, the shipper questions, export additions).
- Step 3: polish.
- Rules: no change to classification, routing, CN-8/TARIC or store logic; existing store methods for every clerk
  action; the password gate and the demo notice unchanged; existing tests green; new UI tests.

## Reference and precedence

- **Layout and labels**: `docs/design/012-wireframe-final.png`, the final picture. `docs/design/012-wireframe-v4.png`
  is the brief's earlier picture, kept for history.
- **Behaviour**: the brief and the Step 0 decisions D1 to D19 below.
- **Conflicts**: where the final picture and the brief differ, the final picture wins. Each difference and its
  resolution is listed in "Brief and final picture".
- **Native Streamlit only** (D3): no custom CSS and no custom HTML.

## Clarifications

### Session 2026-10-29 (Step 0 decisions)

- **D1**: the brief's "Import into" slot holds the existing Origin setting, with the caption "duty and measures for
  goods from this country · change → re-applied, no model call". No entry country and no ruling weighting.
- **D2**: there is no rewrite step. The second description column shows what a red line needs, from its flag, and
  the current description on other lines. The edit field is the existing "update the description" field, prefilled
  with the current text.
- **D3**: native elements only (`st.badge`, `st.container(border=True)` with `st.metric`, `st.progress`). No CSS and
  no custom HTML.
- **D4**: the UI Design Contract in the constitution is amended first. The draft is in plan.md, and the author runs
  `/speckit-constitution` before any Step 1 code.
- **D5**: changing the HS-6 radio changes only what is displayed, with no model call and no store write. "Accept"
  records the choice through the existing decision method, as the clerk's, and the CN-8 and TARIC steps then run as
  today.
- **D6**: block 4 shows the existing CN-8 or subdivision pick form when the line waits for one, and the decided code
  otherwise.
- **D7**: "Other HS-6 code…" is a fourth radio option, with its code field.
- **D8**: "Accept all K ready" stays in the counts row. The row checkboxes and "Accept K selected" are removed.
- **D9**: the sample is a button in the upload area.
- **D10**: one status line under the check button covers checking, elapsed time, queued re-checks and job messages.
  A line still being checked shows "Checking…" and does not open.
- **D11**: 50 lines per page.
- **D12**: the CSV download, with a small JSON download beside it. The audit trail stays in Advanced.
- **D13**: the export gains one column, `clerk_changed`. This is the only change in `agent/store.py`.
- **D14**: a single line joins the open shipment, or opens one, as today, and its row opens.
- **D15**: photos (JPG, PNG) stay supported. The upload text names them.
- **D16**: no VAT figure and no certificate claim. Block 4 shows "Requirements: none" or the requirement measures.
- **D17**: the Admin sections move from the sidebar to a segmented control at the top of the Admin page.
- **D18**: the shipper questions show the draft, and each red line's update field with "Re-check this line". A whole
  pasted reply stays in Advanced › Ask the agent.
- **D19**:
  - the candidate rationale is a caption under the radio;
  - the precedent popover and the "history only" marker stay;
  - the detailed status (for example "Pick: CN-8") is the badge's tooltip;
  - the line number comes first in the row;
  - the full code is in block 4;
  - the re-check caption has no cost figure;
  - the draft's EN/中文 switch keeps today's default, EN.

### Session 2026-10-29 (after the Step 0 review)

- **Q1**: the default. Block 3 shows the vote summary by code, with no store change.
- **HS codes** keep their dotted form ("9405.40").
- **Origin**: an `st.selectbox` over a static list of ISO two-letter codes only, default CN, with type-to-filter, and
  no store change.
- **Count cards**: an `st.container(border=True)` each, with the number in coloured markdown (`:green`, `:orange`,
  `:red`), not `st.metric`.
- **List column**: labelled "HS code". It shows the HS-6 candidate before a decision and the decided 8- or 10-digit
  code after, as today, so an auto-accepted Ready line shows its 10 digits directly.
- **Hard rule**: this feature changes only files under `ui/` and `app.py`. It does not modify `agent/`, `tools/`,
  `rag/`, routing, the store schema, or any behaviour. A UI change that seems to need a function change is asked
  first.

### Session 2026-10-29 (after the Step 1 review)

- **FR-013 confirmed**: `clerk_changed` is built in `ui/`, from the store's export rows and the line versions;
  `agent/store.py` does not change.
- **Origin list**: TARIC's six country codes outside ISO join the list (XC, XI, XK, XL, XS, XU), so every TARIC
  origin can be chosen; Serbia, for one, is XS in TARIC.
- **Status line**: it names the file, "Checked N lines of <file name> in T s · model: <chat model>".
- **Constitution**: the four remaining "summary bar" and "decision table" mentions wait for a 1.8.1 amendment at the
  end of Step 3, when the wording is final.

### Session 2026-10-29 (after the Step 2 review)

- **`clerk_changed`**: true only for the clerk's real overrides: an HS-6 other than the model's top candidate (another
  candidate or a typed code), or an edited description. Accepting a Ready line as it is, confirming its codes or
  asking the shipper is false.
- **Status line**: it keeps the model's name.
- **Shipper email draft**: the asking lines' update fields fold into an expander under the draft.

## Brief and final picture

Where they differ, this feature follows the final picture.

| Element | Brief | Final picture, followed |
|---|---|---|
| Top of the page | a line "CargoLint · Demo · nothing you upload is stored · not customs advice · Advanced", then the title "Check goods descriptions for EU customs" and a sentence | title "CargoLint" with the subtitle "Check invoice and packing-list lines before customs declaration"; the Origin box on the right. The demo notice (unchanged, `CARGOLINT_DEMO_NOTICE`) carries the demo message |
| Advanced | small link at the top right | a link at the bottom: "Advanced: Ask the agent · paste shipper reply · audit trail · Admin" |
| Tabs | "Packing list file", "Single line" | "Upload file", "Check a single line" |
| Primary button | "Check packing list" | "Check all lines"; "Check this line" in the single-line tab |
| Sample | — | "Load sample invoice" in the upload area |
| Count cards | Accept, Review, Ask shipper | "Ready to accept", "Needs review", "Ask shipper", the counts coloured green, orange and red |
| Counts row buttons | "Download results" (primary) | "Accept all K ready", "Download CSV", and a small "JSON" |
| List | Route · Original line · Rewrite · Code · n of 5 | # · Status · Description · Need / description · HS code · Conf., under the heading "Lines (sorted: ask shipper → review → ready)" with "Page x of y" |
| Badges | Accept, Review, Ask shipper | Ready (and Accepted), Review, Ask shipper |
| Open row | five numbered blocks | "Line n · <description>", blocks 1 to 4 numbered, the two decision buttons unnumbered |
| Block 2 label | "code · description · confidence · n of 5 rulings" | "<code> <description> — <confidence>%" with a bar; the ruling count is in block 3 |
| Block 3 | "Official rulings for the selected code" | "Similar rulings (5 nearest, EBTI)", ending "n of 5 agree with <code>" |
| Block 4 | "Full EU tariff code" | "Tariff (Origin XX)": "CN-8: … TARIC: …", "Third-country duty …", "Requirements: …" |
| Decision buttons | "Accept <code>" green, "Ask shipper" red outline | "Accept" (primary) and "Ask shipper" (secondary) |
| Shipper questions | "Next step: n questions…" and the button "Open shipper questions" | the section "Shipper email draft · EN \| 中文" under the list; the count is its caption |
| HS code in the row | "9405.21 · 3 of 5" | the picture's "940540" is a sketch. The column "HS code" shows the dotted HS-6 ("9405.40") before a decision and today's 8- or 10-digit display after it |
| Origin control | "Import into" selectbox (D1: the Origin setting instead) | a dropdown, as drawn: an `st.selectbox` over a static list of ISO two-letter codes and TARIC's six country codes outside ISO, default CN |

## Q1, resolved: block 3 detail

The final picture lists each of the five nearest rulings with its country, year, short description, code, ✓ or ✗,
and a link. The line stores only the vote's summary: each HS-6 with the issuing countries of its rulings.

The author chose the default, with no store change. Block 3 lists each HS-6 among the nearest rulings with ✓ or ✗ and
its countries ("✓ 9405.40 · DE, NL, IE"), then "n of 5 agree with <code>". Each candidate's precedent ruling and its
"Open ruling ↗" link are added.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check a file and see at once what needs attention (Priority: P1)

The clerk uploads a packing list or loads the sample, presses the prominent "Check all lines", and sees three count
cards and a list sorted so that the lines needing the shipper come first.

**Why this priority**: it answers the feedback directly: larger text, and the important buttons the most prominent.

**Independent Test**: the page under AppTest with a seeded store: the cards' counts, the order of the rows, the
badges, the primary full-width check button, and no sidebar.

**Acceptance Scenarios**:

1. **Given** an uploaded file, **When** the clerk presses "Check all lines", **Then** the check runs as today and
   the status line shows "Checking N lines… T s", then "Checked N lines in T s · model: <model>".
2. **Given** a checked shipment, **When** the page renders, **Then**:
   - the cards show the Ready-to-accept, Needs-review and Ask-shipper counts;
   - the rows run Ask shipper, then Review, then Ready, then Accepted;
   - each row shows #, a badge, the description, the need or current description, the HS-6 and the confidence.
3. **Given** more than 50 lines, **When** the page renders, **Then** the list is paged at 50 lines with "Page x of
   y".
4. **Given** an open shipment, **When** another file is dropped, **Then** the existing replace prompt asks first.

---

### User Story 2 - Decide a line in its open row (Priority: P1)

The clerk opens a line and works through its blocks: the description, the HS-6 candidates, the similar rulings, the
tariff, then "Accept" or "Ask shipper".

**Why this priority**: this is the clerk's decision, and every action must go through the existing store methods
and audit log.

**Independent Test**: AppTest on seeded lines of each kind (HS-6 to choose, CN-8 to pick, subdivision to pick,
ready, accepted, ask).

**Acceptance Scenarios**:

1. **Given** a line to review, **When** the clerk picks the second candidate, **Then** blocks 3 and 4 and the row's
   HS-6 and Conf. cells show that code, with no model call and no store write.
2. **Given** that choice, **When** the clerk presses "Accept", **Then**:
   - the decision is recorded through the existing method, as the clerk's, with its audit entry;
   - the CN-8 and TARIC steps run as today;
   - the export shows the chosen code, `route_set_by` "clerk" and `clerk_changed` true.
3. **Given** an edited description, **When** the clerk presses "Re-check this line", **Then** only that line is
   checked again, through the existing re-check, and only its row changes.
4. **Given** a line waiting for a CN-8 or subdivision pick, **When** it is open, **Then** block 4 shows the existing
   pick form and "Accept" confirms the pick.
5. **Given** any open line, **When** the clerk presses "Ask shipper", **Then** the line turns red and joins the
   shipper email draft.

---

### User Story 3 - Check a single line (Priority: P2)

The clerk types one description, in English or Chinese, in the second tab and presses "Check this line".

**Why this priority**: a frequent quick check, not the main flow.

**Independent Test**: AppTest: the tab's field and button, and the typed-line job started with that text.

**Acceptance Scenarios**:

1. **Given** the single-line tab, **When** the clerk types a description and presses "Check this line", **Then**
   the line joins the open shipment (or opens one) through the existing typed-line path.
2. **Given** that line's check has ended, **When** the page renders, **Then** its row is open.

---

### User Story 4 - Ask the shipper (Priority: P2)

Under the list, the clerk finds the email draft for every red line, in English or Chinese, and each red line's
update field for the shipper's answer.

**Why this priority**: it closes the loop for the lines that cannot be decided.

**Independent Test**: AppTest: a red line's question in the draft; "Ask shipper" on a row adds it.

**Acceptance Scenarios**:

1. **Given** red lines, **When** the page renders, **Then** the section "Shipper email draft · EN | 中文" shows the
   existing draft, its count, and each red line's update field with "Re-check this line".
2. **Given** a line not yet red, **When** the clerk presses "Ask shipper" in its row, **Then** the draft includes
   it.

---

### User Story 5 - Advanced settings without the sidebar (Priority: P3)

The operator follows "Advanced" at the bottom of the page to the Admin page.

**Why this priority**: operator and evaluator use, not the clerk's daily work.

**Independent Test**: AppTest of the Admin page: no sidebar, and the section switch.

**Acceptance Scenarios**:

1. **Given** the main page, **When** the operator follows "Advanced…", **Then** the Admin page opens, behind the same
   password gate.
2. **Given** the Admin page, **When** it renders, **Then** a segmented control switches between Rules, Data, Cost,
   Quality and Ask the agent, and there is no sidebar.

---

### Edge Cases

- **A line still being checked**: it shows "Checking…" (grey) and does not open.
- **A failed check**: it shows Ask shipper with "check failed" as its need, and it can be re-checked.
- **An accepted line**: "Accept" is replaced by a disabled "Accepted".
- **No rulings voted**: block 3 says no ruling was within the similarity floor.
- **No TARIC snapshot**: block 4 says "TARIC not loaded".
- **A radio choice that is not the line's HS-6**: block 4 lists the CN-8 lines under it from the nomenclature, with
  "CN-8 and TARIC-10 follow when you accept this code".
- **A single line or re-check while a job runs**: it waits behind the job, as today, and the status line shows the
  queue.
- **An Origin change with no shipment open**: the origin is kept for the next shipment, as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The theme MUST use `baseFontSize = 18`. The primary colour stays `#1D4FB8`, the canvas accent and a
  strong blue. Theme changes go only in `.streamlit/config.toml`.
- **FR-002**: No page MUST use the sidebar. The Admin sections move to a segmented control at the top of the Admin
  page (D17).
- **FR-003**: The header MUST show:
  - the title "CargoLint";
  - the subtitle "Check invoice and packing-list lines before customs declaration";
  - on the right, a bordered Origin box.

  The Origin box holds an `st.selectbox` over a static list of ISO two-letter codes and TARIC's six country codes
  outside ISO (XC Ceuta, XI Northern Ireland, XK Kosovo, XL Melilla, XS Serbia, XU the United Kingdom without
  Northern Ireland), defined in `ui/` (CN by default, the kept value otherwise, type-to-filter), with the caption "duty and measures for goods from this country · change
  → re-applied, no model call". A change MUST go through today's origin callback, which calls the existing origin
  re-application and shows its toast (D1). There is no store change.
- **FR-004**: The input area MUST have two tabs, "Upload file" and "Check a single line".
- **FR-005**: The upload tab MUST hold:
  - the native uploader, labelled "Drag and drop a PDF, Excel, CSV or photo (jpg/png) here, or browse files", with
    the caption "about 1 minute for 30 lines" (D15);
  - "Load sample invoice" (D9);
  - the existing replace prompt;
  - a full-width primary "Check all lines".

  A dropped file no longer starts the check by itself: "Check all lines" starts it, through the existing check.
- **FR-006**: The single-line tab MUST hold a text field for one description, English or Chinese, and a full-width
  primary "Check this line" that uses the existing typed-line path (D14). When the line's check ends, its row is
  open.
- **FR-007**: A status line under the check button MUST show:
  - "Checked N lines of <file name> in T s · model: <chat model>", without "of <file name>" when no file was read;
  - while a job runs, "Checking N lines… T s";
  - the queued re-checks and the job messages (D10).
- **FR-008**: The counts row MUST show:
  - three cards, each an `st.container(border=True)` with its label and its count in coloured markdown: "Ready to
    accept" (`:green`, green lines not yet accepted), "Needs review" (`:orange`, yellow lines) and "Ask shipper"
    (`:red`, red lines). Not `st.metric`;
  - "Accept all K ready", the existing batch accept (D8);
  - "Download CSV", with a small "JSON" download (D12).

  The row checkboxes and "Accept K selected" are removed.
- **FR-009**: The list MUST carry the heading "Lines (sorted: ask shipper → review → ready)" and "Page x of y". It
  shows 50 lines per page (D11), ordered Ask shipper, Review, Ready, Accepted, then Checking, and in file order within
  each group.
- **FR-010**: Each list row MUST be built with `st.columns`, in this order:
  - **#**: the line number;
  - **Status**: an `st.badge`, green "Ready" or "Accepted", orange "Review", red "Ask shipper", grey "Checking…", with
    the detailed status as its tooltip;
  - **Description**: the line as filed; clicking it opens the row;
  - **Need / description**: on a red line, what it needs, from its flag; on other lines, the current description,
    which differs from the filed one after the clerk edited it (D2);
  - **HS code**: before a decision, the HS-6 candidate in dotted form ("9405.40"). Once a CN-8 or TARIC-10 is
    decided, today's code display: 4-2-2-2 groups, undecided digits as underscores, or the 8 digits and why the line
    stops there. So an auto-accepted Ready line shows its 10 digits directly. "—" when there is no candidate;
  - **Conf.**: the HS-6 candidate's confidence, else "—".

  A line still being checked does not open.
- **FR-011**: The open line MUST render in an `st.expander` "Line n · <description>" under its row, one line open at
  a time, with these blocks in order:
  - **1 Description**: the caption "Original: <filed text> · Stop-word check: <result>"; a text field prefilled with
    the current description; "Re-check this line" with the caption "runs the model again" (no cost figure). The
    re-check is the existing per-line re-check, the shipper-reply path, and changes only that line.
  - **2 HS-6 candidates**:
    - a radio over the model's three candidates, "<code> <description> — <confidence>%", and "Other HS-6 code…" with
      its code field (D7);
    - preset to the decided code, else the top candidate;
    - a confidence bar (`st.progress`) beside each candidate;
    - the caption "Why: <the selected candidate's rationale>";
    - the precedent popover and the "history only" marker (D19).

    Changing the radio updates blocks 3 and 4 and the row's HS-6 and Conf. cells, with no model call and no store
    write (D5).
  - **3 Similar rulings (5 nearest, EBTI)**: Q1's default: each HS-6 among the nearest rulings with ✓ (the selected
    code) or ✗ and its countries, "n of 5 agree with <code>", and each candidate's precedent ruling with "Open ruling
    ↗" where it has a link.
  - **4 Tariff (Origin XX)**: a bordered box with "CN-8: … TARIC: …", "Third-country duty …" and "Requirements: none"
    or the requirement measures (D16), then "All measures", "EZT-online ↗" and "Open in EU TARIC ↗".
    - When the line waits for a CN-8 or subdivision pick, the existing pick form appears here (D6).
    - "Change the code at" keeps the existing change at CN-8 or TARIC-10 for decided lines.
    - For a radio choice that is not the line's HS-6, it lists the CN-8 lines under it and says "CN-8 and TARIC-10
      follow when you accept this code".
  - **Decision**: "Accept" (primary) and "Ask shipper" (secondary), through the existing store methods and audit log:
    - the selected HS-6: the decision method, as the clerk's, then the CN-8 and TARIC steps as today;
    - a pick in block 4: the CN-8 or TARIC-10 confirmation;
    - a Ready line: the existing batch accept for that line;
    - an accepted line: a disabled "Accepted";
    - "Ask shipper": the decision method with route ask_shipper, or the TARIC question at the subdivision step.
- **FR-012**: When at least one line asks, a section under the list MUST show:
  - the heading "Shipper email draft · EN | 中文", with the existing language switch (default EN);
  - the caption "n questions ready for the shipper";
  - the existing draft in a code block, with its copy button;
  - folded in an expander under it, each asking line's update field with "Re-check this line" (D18).

  A line routed to the shipper from its row appears in the draft.
- **FR-013**: The CSV and JSON downloads MUST add one column, `clerk_changed`, built in `ui/` from the store's export
  rows and the line versions; `agent/store.py` does not change. It is true only for the clerk's overrides: an HS-6
  other than the model's top candidate (`decided_how` "other_candidate" or "typed"), or a version of the line created
  by the clerk's edit. Accepting a line as it is, confirming its codes or asking the shipper leaves it false. The
  edited description, the chosen code and the final route are the existing text, `decided_code` and `route`
  columns.
- **FR-014**: The bottom of the main page MUST hold a page link "Advanced: Ask the agent · paste shipper reply ·
  audit trail · Admin" to the Admin page, behind the password gate like every page.
- **FR-015**: Unchanged: the password gate, the demo notice, classification, routing, the CN-8 and TARIC steps, and
  the store's logic. Every clerk action uses an existing store method.

  Only files under `ui/` and `app.py` change (the hard rule), besides this feature's tests and documents. The theme in
  `.streamlit/config.toml` (FR-001) is the one exception, flagged to the author.
- **FR-016**: Native Streamlit only: no `unsafe_allow_html`, no `st.html`, no components and no custom CSS in
  `app.py` or `ui/`.
- **FR-017**: All existing tests MUST pass. UI tests of moved or removed elements are rewritten to the new layout
  with the same intent. New UI tests cover:
  - the single-line tab;
  - a radio choice then "Accept" updating the export;
  - a re-check updating one row only;
  - an Origin change showing the re-apply note;
  - "Ask shipper" adding the line to the draft.

### Key Entities *(include if feature involves data)*

- **Line status**: unchanged (`ui/view.py`). The badge, the sort group and the counts are read from it.
- **Export row**: today's columns; the UI's downloads add `clerk_changed` (FR-013).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The check button of each tab is primary and full width, and "Accept" is primary.
- **SC-002**: The base font size is 18 (theme).
- **SC-003**: No page has a sidebar (UI tests on both pages).
- **SC-004**: No custom HTML or CSS: a static test finds none in `app.py` and `ui/`.
- **SC-005**: The offline suite passes, with the five new UI tests of FR-017.
- **SC-006**: Every clerk action goes through an existing store method, and no file under `agent/`, `tools/` or `rag/`
  changes.
- **SC-007**: Clerk actions on the 12-line sample still return within 1 s (`tests/ui/test_response_time.py`).

## Assumptions

- The author adopts the constitution amendment drafted in plan.md (UI Design Contract, 1.8.0) before the Step 1
  code (D4).
- The demo notice and the password gate keep their place and behaviour.
- Feature 005's UI contract stays as history; this spec describes the main page from 012 on.
