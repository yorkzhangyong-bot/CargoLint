# Implementation Plan: UI Redesign from First Customer Feedback

**Branch**: `012-ui-redesign` | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)

**Input**: the feature specification, the final picture `docs/design/012-wireframe-final.png`, and the Step 0
decisions D1 to D19 (spec, Clarifications).

## Summary

The main page is rebuilt in native Streamlit elements:

- the title with the Origin box;
- two input tabs with full-width primary check buttons;
- a status line;
- three bordered count metrics with "Accept all K ready" and the downloads;
- a list sorted ask shipper → review → ready, its rows built from columns, with the open line in an expander in four
  blocks plus "Accept" and "Ask shipper";
- the shipper email draft;
- no link to the Admin page, which keeps its own address (after the author's check of the UI).

The Admin page loses the sidebar. The base font size goes to 18.

Classification, routing, the CN-8 and TARIC steps and the store's logic do not change. Every clerk action calls an
existing store method. Only files under `ui/` and `app.py` change (the hard rule of 2026-10-29), besides tests,
documents and the theme file. The work comes in three steps, each committed on its own: layout, results, polish. The
constitution's UI Design Contract is amended first (D4).

## Technical Context

**Language/Version**: Python 3.11–3.13, Streamlit 1.65.0

**Primary Dependencies**: Streamlit native elements only, checked against the installed 1.65:

- `st.badge` (colour, `help`);
- `st.selectbox` (type-to-filter);
- `st.radio`;
- `st.tabs`;
- `st.expander` (`key`, `on_change`);
- `st.segmented_control`;
- `st.progress`;
- `st.download_button(type="tertiary")`;
- `st.container(border=True, horizontal=True)`;
- `st.page_link`.

**Storage**: unchanged. The line store lives in the Streamlit session.

**Testing**: pytest with Streamlit's AppTest on the seeded stores of `tests/ui/harness.py`, offline. A static test
checks that no custom HTML, JavaScript or components exist, and CSS only in `ui/theme.py` (constitution 1.10.0).

**Target Platform**: the local app and the Community Cloud demo (feature 011)

**Project Type**: the existing single Streamlit project

**Performance Goals**: clerk actions on the 12-line sample return within 1 s, as today
(`tests/ui/test_response_time.py`).

**Constraints**:
- only files under `ui/` and `app.py` change, besides tests, documents and the theme file (the hard rule); no change
  to classification, routing, the CN-8 and TARIC steps or the store;
- native Streamlit, with one layout-only CSS block in `ui/theme.py` (constitution 1.10.0);
- the password gate and the demo notice unchanged;
- each file keeps its line endings (`.streamlit/config.toml` is CRLF in the working tree).

**Scale/Scope**:
- `ui/main_page.py`, `ui/upload.py`, `ui/table.py`, `ui/expand.py`, `ui/view.py` and `ui/admin.py`;
- the theme;
- `tests/ui`: 72 tests today, 47 of them in `test_main_page.py`, many of which are rewritten to the new layout.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution 1.7.0.

| Principle | Check | Status |
|---|---|---|
| I. Guardrails live in code | Routes, the threshold, the flagged-line lock and code validation are unchanged. The UI calls the existing store methods: `set_decision`, `confirm_cn8`, `confirm_taric10`, `ask_shipper_for_taric`, the batch accept, the re-check. | Pass |
| II. Untrusted input | The edited description goes through the existing re-check path; nothing new reaches the model. | Pass |
| III. Grounded, cited | Block 3 shows the vote's rulings by code and issuing country, the agreeing share, and the candidates' precedents with links. | Pass |
| IV. Hybrid retrieval | Unchanged. | Pass |
| V. Typed tools | Unchanged. | Pass |
| VI. A native UI that shows its work | Native elements only. The open line shows the candidates, the reason, the rulings and the tariff. | Pass |
| VII. Test-first | Each step's UI tests come before its code; the suite stays offline. | Pass |
| Architecture: the UI reads only the store; logic testable without Streamlit | New texts and orderings go in `ui/view.py`, which imports no Streamlit. | Pass |
| UI Design Contract (inventory of the two pages) | The redesign moves or removes listed elements: the header link, the summary bar, the table's columns, the status dots, the two exports, "+ Check one more line", and the Admin left navigation. "Removing or relocating a listed element needs a spec change", and the inventory is in the constitution. | **Fails until 1.8.0**: draft below; the author runs `/speckit-constitution` before the Step 1 code (task T004) |
| Out of scope | No accounts, no persistence beyond the session. | Pass |

**Post-design re-check**: unchanged. Only the UI Design Contract row fails, until the amendment is adopted.

## Project Structure

### Documentation (this feature)

```text
specs/012-ui-redesign/
├── spec.md              # the specification, with the Step 0 decisions and the brief/picture table
├── plan.md              # this file: the design decisions below take the place of research.md
└── tasks.md             # the task list, by step
docs/design/
├── 012-wireframe-final.png   # the reference
└── 012-wireframe-v4.png      # the brief's earlier picture
```

### Source Code (repository root)

```text
.streamlit/config.toml   # Step 1: baseFontSize 18 (the file stays CRLF)
ui/
├── main_page.py         # Steps 1–3: header and Origin box, tabs, status line, counts row, draft section
├── upload.py            # Step 1: the uploader in the upload tab, "Load sample invoice", "Check all lines" starts the check
├── table.py             # Step 2: rows from st.columns, sort groups, 50 per page, the open line in an st.expander
├── expand.py            # Step 2: blocks 1–4 and the decision buttons, built on today's forms
├── view.py              # Steps 1–2: status line, badge, sort group, need text, row cells, block texts (no Streamlit)
└── admin.py             # Step 1: a segmented control instead of the sidebar radio
tests/
├── ui/                  # the rewritten layout tests and the five new tests of FR-017
└── unit/                # test_view.py additions; test_native_ui.py (Step 3, static)
README.md                # Step 3: "What the clerk sees"
```

**Structure Decision**: the existing modules keep their roles. `main_page` lays out the page, `table` the list,
`expand` the open line, and `view` every text and order. No new module is needed.

## Design decisions

1. **Tabs.** `st.tabs(["Upload file", "Check a single line"])`, each tab with its own full-width primary button. The
   button inside the active tab is the visible one, so no tab state is needed to label it.
2. **Upload, then check.**
   - A dropped file is validated as today and kept in the session as the pending file. A checked shipment that is
     already open triggers the existing replace prompt first.
   - "Load sample invoice" makes the bundled sample the pending file.
   - "Check all lines" starts the check through the existing `upload.begin` and `runner.start_check`.
3. **Single line.** A text field and "Check this line" call the existing `runner.check_typed_line`. When the line's
   job ends, `selected_line_no` is set to it, so its row opens.
4. **Status line.** A new `view.status_line` builds "Checked N lines of <file name> in T s" from `view.summary`
   and the shipment's file; the model's name is a caption on the Admin page (after the author's check). The checking
   state, the queue and the job messages come from today's runner functions.
5. **Origin box.** `st.container(border=True)` on the right of the title holds an `st.selectbox` over a static list of
   ISO two-letter codes and TARIC's six country codes outside ISO (XC, XI, XK, XL, XS, XU) in `ui/view.py`, which
   filters as the clerk types; the default is CN. Its callback is today's
   origin callback, which calls `apply_taric_origin` and shows the toast. The caption, "Duty and measures follow this
   country. Changing it re-applies them without a new model call.", and the snapshot date sit beside the selectbox
   in the same box (the author's polish; D1 worded the caption before). There is no store change.
6. **Counts row.** One horizontal container holds:
   - three `st.container(border=True)` cards, each with its label and its count in coloured markdown: `:green[…]` for
     Ready to accept (`Summary.to_accept`), `:orange[…]` for Needs review (`Summary.pick`), `:red[…]` for Ask shipper
     (`Summary.ask`);
   - "Accept all K ready", calling `actions.accept_ready`;
   - "Download CSV", using the store's export; the tertiary "JSON" was removed after the author's check of the UI.
7. **Sort and pages.**
   - A new `view.sort_group(status)` orders the groups Ask shipper, Review, Ready, Accepted, Checking; within a group,
     lines keep file order.
   - 50 lines per page.
   - "Page x of y" uses today's page switch.
   - After the author's check: the caption "Click a line to open it." above the columns, and a narrow first column
     with a ▸ button (▾ while open) on the same state as the description's click.
8. **Row cells.** A new `view.row_cells(store, line, status)` returns:
   - **the badge**: label, colour and tooltip (today's status text);
   - **the description**: as filed, the first version's text;
   - **the need or current text**: a red line's need from its flag's `ask_for` (for example "needs goods name,
     material and use"), "check failed" for a failed check, or the TARIC question's attribute; other lines get the
     current description;
   - **the HS code**: before a CN-8 or TARIC-10 is decided, the HS-6 (decided or top candidate) in dotted form; after
     it, today's `view.code_display` text (4-2-2-2 groups, or the 8 digits and why);
   - **the confidence**: the HS-6 candidate's.
9. **Open line.** `st.expander(f"Line {n} · {text}", expanded=True, key=…)` under the selected row only, with today's
   `selected_line_no` as the open line. Collapsing it clears the selection through `on_change`.
10. **Block 1.**
    - A caption with the original text and the stop-word result: the flag's rule and term, or "none found". When a
      red line's reason states that result, the caption shows only the original, so the result shows once.
    - A text field prefilled with the current description, keyed by line and version.
    - "Re-check this line", which uses today's `view.split_description`, `view.edit_problem` and
      `runner.start_recheck`, as the "Re-check line" button does now.
11. **Block 2.**
    - `st.radio` over today's `view.hs6_rows` and "Other HS-6 code…", preset by `view.preselect`. The selection is
      held in the session, keyed by line and version; nothing is written to the store.
    - Beside the radio, one `st.progress` per candidate.
    - Under it, "Why: <rationale>", today's precedent popover, and the "history only" marker in the label.
12. **Block 3.**
    - From `line.current.hs6_vote.competing`, each HS-6 with ✓ (equal to the selected code) or ✗ and its countries.
    - "n of 5 agree with <code>", from today's `view._hs6_votes`.
    - The vote and override sentences of `view.explain_a`.
    - The candidates' precedents with "Open ruling ↗".

    Q1: the author chose this default; the individual rulings are not stored.
13. **Block 4.**
    - **When the selected code is the line's HS-6**: today's `line_taric_view` fills a bordered box. It holds "CN-8:
      … TARIC: …", the third-country duty (`view._duty`), "Requirements: none" or the requirement measures' types,
      then today's "All measures" and links.
    - **When the line waits for a pick** (kind `a_cn8` or `b`): today's pick rows, without their own confirm buttons.
    - **For a decided line**: today's "Change the code at" control.
    - **For another radio choice**: the CN-8 lines under it from `view._cn8_options`, and the note "CN-8 and TARIC-10
      follow when you accept this code".
14. **Decision buttons.** One "Accept" and one "Ask shipper", whose callbacks are today's, chosen by the line's kind:
    - HS-6: `set_decision` with route accepted and the selected code, then `runner.queue_finer_codes`;
    - CN-8: `confirm_cn8`, then the TARIC step when it is next;
    - TARIC-10: `confirm_taric10`;
    - Ready: `actions.accept_ready(store, [n])`;
    - Accepted: a disabled "Accepted";
    - Ask shipper: `set_decision` with route ask_shipper, or `ask_shipper_for_taric` at the subdivision step.

    A refusal shows "Not confirmed: <reason>", as today.
15. **Shipper email draft.** Under the list, when `Summary.ask` is above zero:
    - the heading "Shipper email draft · EN | 中文", with today's language switch (default EN);
    - the caption "n questions ready for the shipper";
    - today's `shipper_email.draft` in `st.code`;
    - no update fields: an asking line is updated in its open row (after the author's check of the UI).
16. **`clerk_changed` (FR-013, confirmed after Step 1, narrowed after Step 2, widened to the finer codes after Step 3).**
    True only for the clerk's overrides:
    - the export row's `decided_how` is "other_candidate" or "typed" (an HS-6 other than the top candidate);
    - a CN-8 written by the clerk differs from the one the model offered: the line keeps only the clerk's code, so the
      offer is the CN-8 step's last audit record (`cn8_written` or `cn8_pending`, not by the clerk) for the line's
      version under the decided HS-6; none offered is no override;
    - a TARIC-10 written by the clerk differs from the outcome's suggestion, which stays on the line; no suggestion is
      no override;
    - a version of the line was created by the clerk's edit (`CreatedBy.clerk`).

    Accepting a Ready line as it is, confirming its codes or asking the shipper is false. `view.export_csv` adds it to
    the store's export rows in `ui/`; `agent/store.py` does not change.
17. **Admin page.** `st.segmented_control("Section", SECTIONS, key="admin_section", default="Rules", required=True)`
    at the top of the page, keeping today's session persistence, instead of `st.sidebar.radio`. After the author's
    check, a caption under the intro names the model: "Model: <chat model> via OpenRouter".
18. **No Advanced link** (after the author's check of the UI). The main page links nowhere; the Admin page keeps its
    own address, `/admin`, and its "← Back to shipment".
19. **Theme.** `baseFontSize` goes from 14 to 18. `primaryColor` stays `#1D4FB8`, the canvas accent. The
    `[theme.sidebar]` table stays: it is harmless, and touching it would be cosmetic only.
20. **The native-only check.** A static test reads `app.py` and `ui/*.py` and fails on `unsafe_allow_html`,
    `st.html(` or `components.`. Since constitution 1.10.0, `ui/theme.py` may hold one `<style>` block, whose CSS
    properties the test checks; CSS anywhere else fails.
21. **The layout CSS** (constitution 1.10.0). `ui/theme.py` holds the one `<style>` block, which the header injects
    inside a container with no gap: 1rem above the title, less padding in the Origin block and the upload box, a
    tab's content closer to its tab, and count cards of about 90 px with no padding above the count.

## Draft for task T004: constitution 1.8.0 (UI Design Contract)

Version 1.7.0 → 1.8.0, MINOR: the UI Design Contract's inventory changes materially, and no principle changes.

- **Opening paragraph.** Replace "Since v1.3.0 the layout of the two pages follows feature 005
  (`specs/005-decision-first-ui/`) and its wireframes ("CargoLint UI redesign — wireframes"), which replace the
  canvas's two screens." with: "Since v1.8.0 the layout of the two pages follows feature 012
  (`specs/012-ui-redesign/`) and its final picture (`docs/design/012-wireframe-final.png`), which replace feature
  005's layout."
- **Styling.** Replace the bullet with:

  > Styling: native Streamlit theme with the canvas accent (`#1D4FB8`) and a base font size of 18; Source Sans 3 for
  > text, Source Code Pro for codes and numbers, a CJK-capable font for Chinese; no custom HTML or CSS. Each line's
  > status is a coloured badge: green "Ready" or "Accepted", orange "Review", red "Ask shipper", grey "Checking…"; the
  > decision it needs ("Pick: …", "Confirm: …", "Ask: …") is the badge's tooltip. Confidence is a percentage in the
  > line's row and a bar beside each candidate in the open line; the CN-8's is labelled "model estimate". "Needs
  > action" means any orange or red line.

- **Main page.** Replace the "Main page, with no sidebar" bullet and its items with:

  > Main page, with no sidebar:
  >
  > - Header: "CargoLint", the subtitle, and the Origin box. The Origin is two letters, CN by default; a change
  >   re-applies the TARIC rules without a model call and shows a toast.
  > - Input, in two tabs:
  >   - "Upload file": a drop zone (20 MB limit, XLSX/CSV/PDF/JPG/PNG), "Load sample invoice" (the bundled sample of
  >     12 lines), and the full-width primary "Check all lines";
  >   - "Check a single line": one description and the full-width primary "Check this line".
  >
  >   A status line follows: lines checked, time and model, or the progress and the queue while a job runs.
  > - Counts row, after a check: "Ready to accept", "Needs review" and "Ask shipper" as bordered cards with coloured
  >   counts; "Accept all K ready" for batch acceptance of the green lines; "Download CSV" and a small "JSON".
  > - The list, sorted ask shipper → review → ready, 50 lines per page: # · Status · Description as filed · Need /
  >   description · HS code · Conf. A line opens under its row with:
  >   - 1, Description: the original and the stop-word check, the editable description, and "Re-check this line";
  >   - 2, HS-6 candidates: the model's three and "Other HS-6 code…", with confidence bars and the reason;
  >   - 3, Similar rulings: for the HS-6, the nearest rulings behind the vote with their issuing countries and the
  >     share that agrees. When the precedent override decided the line, it shows which candidate was chosen, with
  >     the issuing countries of the rulings that agree; with the override switched on, a code outside the top three
  >     is shown as a hint. The candidates' precedents come with their links;
  >   - 4, Tariff: the CN-8 and TARIC-10, the third-country duty, the requirements, all measures and the EU TARIC
  >     link. The CN-8 or subdivision choice appears here while it is open, with the nearest rulings behind the CN-8
  >     vote, and so does the change of a decided code at CN-8 or TARIC-10;
  >   - then "Accept" and "Ask shipper".
  > - Under the list: the shipper email draft (templates in English or Chinese, copy only) with each red line's
  >   update field and "Re-check this line"; then the "Advanced" link to the Admin page.

- **Admin page.** Replace "reached from the header link, with a left navigation:" with "reached from the "Advanced"
  link at the bottom of the main page, with a section switch at the top:". The five sections stay as they are.
- **Amendment log, 1.8.0 (2026-10-29)**:

  > UI Design Contract follows feature 012, after the first customer feedback ("text too small, important buttons not
  > prominent"):
  > - base font size 18;
  > - tabs for a file and a single line, with full-width primary check buttons;
  > - count cards and batch acceptance;
  > - a list sorted by what needs attention, with status badges, and an open line in four blocks plus Accept and Ask
  >   shipper;
  > - the shipper email draft under the list;
  > - the Admin page reached from "Advanced", its sections in a switch instead of a sidebar.
  >
  > Native Streamlit only, as before.

## Implementation outline

Each step: write its tests first, then the code; run `pytest -q`; commit. The steps are never merged by this feature.

**Step 1, layout** (after T004)
- Tests:
  - the header and the Origin box with its caption;
  - the two tabs and their full-width primary buttons;
  - no sidebar on either page;
  - the Admin section switch;
  - the status line;
  - the single-line tab;
  - an Origin change showing the re-apply note;
  - the Advanced link.
- Code: the theme; `main_page` (header, tabs, status line, Advanced link); `upload` (check on the button); `admin`
  (segmented control); `view.status_line`.
- Rewrite the existing tests of the header, the drop zone and the Admin navigation to the new layout.

**Step 2, results**
- Tests:
  - the cards' counts;
  - the sort order and the 50-line pages;
  - the row cells;
  - the open line's blocks for each kind;
  - a radio choice then "Accept" updating the export;
  - a re-check changing one row;
  - "Ask shipper" adding the line to the draft;
  - the draft section;
  - `clerk_changed` in both exports.
- Code: `view` helpers; `table`; `expand`; `main_page` (counts row, draft section); the downloads' column in `ui/`, if
  the author confirms FR-013.
- Rewrite the existing table, row, summary and export tests.

**Step 3, polish (native)**
- The confidence bars beside the candidates.
- The card and container spacing.
- The static native-only test.
- The README's "What the clerk sees".

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| UI Design Contract (1.7.0) moved and removed elements | the customer feedback asks for larger text and more prominent actions, which the 005 layout cannot give without moving elements | keeping the 005 inventory would keep the layout the clerk found hard to use; the author amends the contract to 1.8.0 (T004) before the code |
