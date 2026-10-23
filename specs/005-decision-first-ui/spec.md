# Feature Specification: Decision-First Clerk Workflow (UI Redesign)

**Feature Branch**: `005-decision-first-ui`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description:

```text
UI redesign: decision-first clerk workflow (feature 005)

Context: CargoLint backend (features 002-004) is complete and must not change: routing accept/review/ask, HS-6 top-3, CN-8, TARIC-10 with grouped measures, origin re-apply without model call, clerk confirmations, audit trail, CSV/JSON export. This feature rewrites the ui/ package only. The current Streamlit UI (sidebar, chat, Reference/Shipper/Filing panels) was judged unfriendly by the target user, a customs clerk at a 10-40 person Hamburg forwarder. Wireframes: Claude Docs "CargoLint UI redesign - wireframes" (seven mockups plus a "what disappears" table); the spec must match them.

Target user and goal: the clerk uploads one invoice or packing list, sees every line with a colour-coded status that states the decision needed, resolves yellow and red lines in place, and exports. No chat, no accounts, no persistence beyond the session.

Main page (single page, no sidebar):
- Header: CargoLint, file name and line count, Origin selector (default CN), link "Admin".
- Empty state: drop zone for PDF/CSV/XLSX, "Try the sample invoice" button, "Check one line" text input that adds a single row.
- Summary bar: "N lines checked in T s, A ready, B need a pick, C need the shipper", a segmented green/yellow/red bar, and a button "Accept all A ready" that batch-confirms every green line.
- One table: # | Description | Code | Status | Action. Code is the 10-digit TARIC code with undecided digits shown as underscores (e.g. "9503 00 __ __") and fills in live as pipeline steps complete. Status: green dot "Ready"; yellow dot with the concrete choice ("Pick: 10 or 90", "Pick: 9 options, 3 AD"); red dot with the concrete question ("Ask: electric motor?", "Ask: parts of what?"). Action: "Choose" for yellow, "Update" for red, none for green. Rows may be multi-selected for batch accept.
- Clicking a row expands it in place. Three expanded-row kinds, mapping one-to-one to backend routing:
  (a) review with a clear leader -> choose HS-6/CN-8: top-3 candidates with description, confidence bar, EBTI precedent link; one pre-selected; "Confirm <code>" then TARIC-10 runs on that code and the row becomes Ready or opens kind (b); link "None of these -> ask shipper" moves the line to kind (c).
  (b) CN-8 fixed, several TARIC-10 subdivisions -> choose TARIC-10: table Code | Description | Duty | Anti-dumping | Pick; "Confirm" confirms both TARIC-10 and CN-8; "All measures" expander; EU TARIC link for the selected code.
  (c) ask shipper: question box with the specific question, a "Reason" line (either "candidates too close: 0.41/0.39/0.12" or "ICS2 stop word 'spare parts'"), "Copy question"; description text input pre-filled with the current description; "Re-check line" reruns the full pipeline from the stop-word check; audit records "description updated by clerk" with the original text.
- Under the table: "Export CSV", "Export JSON", "Draft shipper email (C lines)", "+ Check one more line".
- Draft shipper email: opens a text block under the table (not a dialog) containing subject with invoice id, greeting with shipper name if known, one numbered question per red line (line number, original description, the ask text), closing and signature placeholders. EN and Chinese versions via a toggle; both are string templates, no model call. "Copy email" copies the whole text.
- Origin change: re-applies TARIC rules to all lines without a model call and shows a toast "Origin US - TARIC rules re-applied to N lines, no model call".

Admin page (Streamlit multipage, left nav), for the evaluator and the forwarder admin, not the clerk:
- Rules: auto-accept threshold slider (default 0.70), hybrid retrieval toggle, "stricter routing for new shippers" toggle. Threshold changes never touch clerk-confirmed codes.
- Data: EBTI ruling count, TARIC snapshot date, model name; placeholder for future refresh.
- Cost: per-session token and euro totals.
- Quality: latest eval table (CN-8 eval, SC-002 validation, HS-6 top-3), audit log export.
- Ask the agent: the existing chat, kept only here.

What disappears from the main page: sidebar, chat, Reference, Shipper, Filing panels, threshold slider, cost panel, raw confidence numbers in the table. Confidence appears only inside expanded rows.

Non-functional requirements:
- NFR-1 Expand row, confirm, batch accept, origin change, draft email and export never call the model and complete within 1 s on the 12-line sample. Only Re-check and the initial upload call the model.
- NFR-2 A first-time clerk completes the 12-line sample from upload to export in under 5 minutes without documentation (measured in a scripted walkthrough test and reported in the eval report).
- NFR-3 All backend tests (currently 710) keep passing unchanged; UI tests cover the three expanded-row kinds, batch accept, draft email content for EN and ZH, origin toast, and the underscore code rendering.
- NFR-4 Existing CLI and export schema (21 columns plus cn8, taric10) unchanged.

Out of scope: user accounts, persistence across sessions, shipper memory, sending email, non-Streamlit front end.
```

## Clarifications

### Session 2026-10-23

- Q: Which default for the auto-accept threshold, 0.70 (the brief) or 85 % (the constitution and the code)? → A: Keep
  85 %, adjustable from 60 to 99. Only the slider moves, to the Admin page. Confidences stay percentages everywhere,
  where the wireframes show decimals.
- Q: Does this feature build "stricter routing for new shippers"? → A: No. It is left for a later feature, so the Admin
  page shows no such switch.
- Q: Confirming an HS-6 needs the CN-8 step, and confirming a CN-8 runs the TARIC suggestion; both call the model.
  Which rule wins over NFR-1? → A: The click returns at once and never waits for the model. The CN-8 step and the
  TARIC suggestion run in the background after it, as today, and the code fills in.
- Q: The clerk's description edit needs a line version created by the clerk, a backend addition the brief rules out.
  → A: Accepted, as a small additive backend change, together with `agent.recheck_line` and the background job kind
  `recheck` that re-check the edited line.
- Q: 27 of today's 710 tests import the current UI package. → A: Replace the 13 that test removed modules with tests of
  the new UI. Keep the 14 that test functions that stay: the reply hook, message classification and the upload
  helpers.
- Q: How Chinese is the Chinese email? → A: All template text is Chinese: subject, greeting, introduction, numbering,
  closing and sign-off. Only a question written by the model may stay English.
- Q: Are green rows read-only? → A: No. Each green row has a "Change" action that opens kind (a), and a code the
  clerk chooses there follows the same confirm flow as a review line. The clerk signs the declaration and must be able
  to override an auto-accepted code.
- Q: Can "Change" re-pick the TARIC-10? → A: Yes. When the line's CN-8 has several TARIC-10 subdivisions, "Change"
  can open kind (b) directly to re-pick the subdivision, with no model call.
- Q: Where does the summary count failed checks and lines still being checked? → A: Apart from the three counts, as
  " · F check failed" and " · R updating", each shown only when above 0.
- Q: When are a vague line's candidates "too close to call"? → A: When the top two confidences differ by at most 10
  points. The rule only changes what kind (c) says; routing never reads it.
- The first draft's decisions on colours, batch acceptance, close candidates and measures stand (see Assumptions).

### Session 2026-10-24

- Q: Can the clerk type an HS-6 code that is not a candidate? → A: Yes. Kind (a) and "Change" offer "Other HS-6
  code…", checked against the loaded nomenclature, as in feature 001.
- Q: Can kind (b) send the line to the shipper instead of picking a subdivision? → A: Yes: "None of these → ask
  shipper", as feature 004 allows.
- Q: How does the clerk open another file once lines exist? → A: "Open another file" in the header, disabled while a
  check runs.
- Q: How is the five-minute target of SC-001 measured? → A: The scripted walkthrough records machine time only. The
  clerk's time is the author's own timed run in the browser, recorded in quickstart.md.
- Q: Which English may the Chinese email still contain? → A: Only data: the shipper's descriptions and name, the
  invoice id, quoted terms, TARIC codes and texts, and model-written questions. The acronyms ICS2 and TARIC stay.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check an invoice and see the decision each line needs (Priority: P1)

The clerk opens CargoLint and drops an invoice or packing list, tries the bundled sample, or types one line. Every
line appears in one table, and its code fills in digit group by digit group as the checks finish. When the check
ends, a summary says how many lines are ready, how many need a pick and how many need the shipper. Every line's
status names the decision in a few words.

**Why this priority**: it replaces the screen the target user judged unfriendly. Nothing else in this feature can
be reached without it, and on its own it already tells the clerk where to look.

**Independent Test**: open the 12-line sample. The table lists the 12 lines in file order. Each has a code in the
"dddd dd dd dd" layout, with undecided digits as underscores, and a green, yellow or red status whose text names
the decision. The summary counts match the statuses. The main page shows no side panel, chat, threshold, cost or
raw confidence numbers.

**Acceptance Scenarios**:

1. **Given** no invoice is open, **When** the clerk opens the page, **Then** it shows:
   - the header with "CargoLint", the origin field reading CN, and "Admin ⚙";
   - a drop zone "Drop a packing list or invoice here", with the formats and "Try the sample invoice";
   - a "Check one line" input;
   - the table's headers over "No lines yet — drop a file or type one description".
2. **Given** the sample is being checked, **When** a line is still in progress, **Then** its status shows a grey
   dashed dot and the step running ("Running TARIC step…"). Its code fills in as each step finishes, for example
   "9503 00 __ __" once the HS-6 is decided.
3. **Given** the check has ended, **When** the clerk reads the summary, **Then** it reads like "12 lines checked in
   19 s · 6 ready · 2 need a pick · 4 need the shipper". These counts are an example; they depend on the model and
   the TARIC snapshot. A bar split into green, yellow and red follows, in the same proportions, with "Accept all K
   ready".
4. **Given** a line whose CN-8 is written and whose nine TARIC-10 subdivisions include three under anti-dumping
   duty, **When** the clerk reads its row, **Then** the code reads "8714 91 10 __", the status shows a yellow dot
   and "Pick: 9 options, 3 AD", and the action reads "Choose".
5. **Given** a line with an open CN-8 question about a motor, **When** the clerk reads its row, **Then** the code
   reads "9503 00 __ __", the status shows a red dot and "Ask: the toy cars incorporate a motor?", and the action
   reads "Update". A line flagged by the ICS2 term "spare parts" reads "____ __ __ __" and "Ask: what exactly is
   “spare parts”?".
6. **Given** an invoice is open, **When** the clerk chooses "Open another file", **Then** the drop zone and "Try the
   sample invoice" appear. While a check runs they are disabled, and opening a file asks before it replaces the open
   invoice.

---

### User Story 2 - Resolve a yellow line, or change a green one, by picking a code in place (Priority: P1)

The clerk chooses "Choose" on a yellow line. The row expands under itself (with "▲ close") and offers the choice the
line needs:
- the HS-6 or the CN-8, from the top candidates with their confidence, reasoning and EBTI precedent, or a typed HS-6
  code;
- or the TARIC-10, from the subdivisions with their duty and any anti-dumping duty.

One option is pre-selected, and one "Confirm <code>" settles it. "Change" on a green line opens the same HS-6 or CN-8
choice, or the TARIC-10 choice when the CN-8 has several subdivisions, so the clerk can override a code that was
accepted automatically.

**Why this priority**: yellow lines need the clerk's judgement most often, and today each one takes several panels
and clicks.

**Independent Test**: on a store holding a review line, a CN-8 to confirm and a TARIC-10 to confirm, each line
expands into its kind (a) or (b). Confirming the pre-selected option writes the code and changes the status. No
other line changes. A green line's "Change" opens kind (a) with its decided HS-6 pre-selected, and confirming
another code runs its later steps again. Its TARIC-10 option opens kind (b), and confirming another subdivision calls
no model.

**Acceptance Scenarios**:

1. **Given** a line routed to review whose top candidate leads, **When** the clerk expands it, **Then** it shows:
   - a sentence on what decides the code, from the stored rationale;
   - "Top candidate leads (58 %) but is under the 85 % auto-accept threshold, so you decide. TARIC runs after your
     pick.";
   - a table Code | Description · precedent | Confidence | Pick. It lists the top three candidates, each with its
     reasoning, its EBTI precedent link or "no close precedent", and a confidence bar, with the leader pre-selected.
     A last row, "Other HS-6 code…", takes a typed code;
   - "Confirm <code>", the note "then TARIC-10 runs on this code", and "None of these → ask shipper".
2. **Given** kind (a) is open, **When** the clerk confirms a code, **Then** the click returns at once. The CN-8 and
   TARIC steps run in the background, the code fills in, and the row turns green or offers kind (b).
3. **Given** kind (a) is open, **When** the clerk chooses "None of these → ask shipper", **Then** the line turns red
   and offers kind (c).
4. **Given** a line with several TARIC-10 subdivisions, **When** the clerk expands it, **Then** it shows:
   - "CN-8 is 8714 91 10 (Frames). 3 of 9 subdivisions carry anti-dumping or countervailing measures for CN.";
   - "Your pick confirms both the CN-8 and the TARIC-10.", with the CN-8's confidence and precedent link;
   - a table Code | Description | Duty | Anti-dumping | Pick, with anti-dumping rates in red and "none" otherwise;
   - "Confirm <code>", "None of these → ask shipper", an "All measures" expander and "Open in EU TARIC ↗" for the
     selected code.
5. **Given** kind (b) is open, **When** the clerk confirms a subdivision, **Then** the TARIC-10 and the CN-8 it sits
   under are both confirmed by the clerk, and the row turns green.
6. **Given** a green line, **When** the clerk chooses "Change", **Then** kind (a) opens under the row with:
   - the decided codes and who decided them, and for a TARIC-10 its duty, anti-dumping duty and measures;
   - the top candidates with the decided HS-6 pre-selected;
   - a switch to the CN-8 lines under it and, when the CN-8 has several TARIC-10 subdivisions, to kind (b).
7. **Given** kind (a) opened by "Change", **When** the clerk confirms another HS-6 or CN-8, **Then** the same flow as
   for a review line follows: the click returns at once, the later steps run in the background, and the row turns
   green or offers kind (b). The code already decided cannot be confirmed again there; the Accept control does that.
8. **Given** "Change" on a green line whose CN-8 has several subdivisions, **When** the clerk switches to TARIC-10,
   **Then** kind (b) opens with the written TARIC-10 pre-selected. Confirming another subdivision takes effect at once,
   with no model call, and the row stays green with the new code.
9. **Given** kind (a) or "Change", **When** the clerk types an HS-6 code into "Other HS-6 code…" and confirms it,
   **Then** a code that exists in the loaded nomenclature is confirmed like a candidate, recorded as typed. Any other
   code is refused with its reason, and nothing changes.
10. **Given** kind (b), **When** the clerk chooses "None of these → ask shipper", **Then** the line turns red with
    "Ask: which TARIC subdivision applies?". The email asks the shipper which of the listed subdivisions applies.

---

### User Story 3 - Resolve a red line: ask the shipper, then update and re-check (Priority: P1)

The clerk chooses "Update" on a red line. The row shows the question to ask the shipper, why it arises, and "Copy
question". When the shipper answers, the clerk writes the answer into the description in the same row and re-checks
that line only.

**Why this priority**: red lines block filing. The clerk must be able to ask the shipper and act on the answer
without leaving the table. This replaces the chat input and the "Lines that need you" panel.

**Independent Test**: a store holds a line flagged by an ICS2 term, a line with a firm stop word, a vague line, an
unreadable line and a line with an open CN-8 question. Each expands into kind (c) with its question and reason. Editing a description and choosing "Re-check line" re-checks
that line alone, and the audit trail records "description updated by clerk" with the original text.

**Acceptance Scenarios**:

1. **Given** a line flagged by the ICS2 unacceptable term "spare parts", **When** the clerk expands it, **Then** the
   "Ask the shipper" box shows the question and "Copy question", and the reason reads "Reason: ICS2 unacceptable
   term 'spare parts'".
2. **Given** a line flagged as vague by the judgement, with close candidates, **When** the clerk expands it,
   **Then** it shows "Candidates: <code> (41 %) · <code> (39 %) · <code> (12 %) — too close to call" and "Reason:
   candidates too close".
3. **Given** a line with an open CN-8 question, **When** the clerk expands it, **Then** the question names the
   attribute, and the reason says the CN-8 depends on it.
4. **Given** kind (c) is open, **When** the clerk types the shipper's answer into "Update the description with the
   shipper's answer" and chooses "Re-check line", **Then**:
   - only that line is checked again, from the stop-word check onwards;
   - the audit trail records "description updated by clerk" with the original text, which the field's hint names;
   - the row collapses and shows its new code and status;
   - while another check runs, the re-check waits, and the edit is stored only when it starts.
5. **Given** a re-checked line that was ever flagged, **When** its new check comes back OK above the threshold,
   **Then** it shows yellow "Confirm: <code>" until the clerk confirms it; it never turns green by itself.
   **Given** a re-checked line that was never flagged, **When** the same happens, **Then** it may turn green, for
   example "9503 00 95 00 · Ready".
6. **Given** a red line, **When** the clerk looks at its row, **Then** the Accept control is shown disabled, with the
   lock reason next to it, for example "Locked: ICS2 unacceptable term 'spare parts' — update the description and
   re-check".
7. **Given** an unreadable line, **When** the clerk expands it, **Then** it shows red "Ask: unreadable line", the
   reason "the description could not be read", the description field and "Re-check line". The Accept control is
   disabled, with its lock reason.

---

### User Story 4 - Accept the ready lines and export (Priority: P2)

The clerk accepts every green line in one action, or ticks a few, and exports the results as CSV or JSON in today's
format.

**Why this priority**: it closes the workflow, but exporting already works without it.

**Independent Test**: on the sample, "Accept all K ready" turns every Ready line into Accepted in one action. The
exported CSV keeps the 21 existing columns plus `cn8` and `taric10`.

**Acceptance Scenarios**:

1. **Given** K green lines the clerk has not confirmed, **When** the clerk chooses "Accept all K ready", **Then**
   each of them is confirmed by the clerk, and threshold changes no longer touch their codes.
2. **Given** the clerk ticks two green lines, **When** they accept the selection, **Then** only those two are
   confirmed.
3. **Given** a checked invoice, **When** the clerk chooses "Export CSV" or "Export JSON" under the table, **Then**
   the file follows feature 004's format.

---

### User Story 5 - Draft the email to the shipper in English or Chinese (Priority: P2)

The clerk chooses "Draft shipper email (C lines)". A text block opens under the table with one numbered question per
red line with a question, in English or in Chinese. The clerk copies it into their own mail program. The answers come back through
Update → Re-check.

**Why this priority**: it saves typing for every invoice with red lines. The clerk still sends the email themselves.

**Independent Test**: on the sample, the draft lists exactly the red lines with a question, numbered, each with its
line number,
original description and question, in English and in Chinese. No model is called.

**Acceptance Scenarios**:

1. **Given** C red lines, **When** the clerk opens the draft, **Then** a text block under the table shows "Email to
   shipper — generated from the C open questions, no model call", an "EN | 中文" toggle, "Copy email", and:
   - a subject such as "Invoice <id> — C lines need more detail before customs filing";
   - a greeting with the shipper's name when it is known;
   - an introduction;
   - C numbered questions in the form "Line 5 “Toy cars” — <question>";
   - a closing and sign-off placeholders for the clerk's and the forwarder's names.
2. **Given** the draft is open, **When** the clerk switches to 中文, **Then** every template part is Chinese. English
   stays only in data: descriptions, names, the invoice id, quoted terms, TARIC codes and texts, and model-written
   questions.
3. **Given** the draft is open, **When** the clerk chooses "Copy email", **Then** the whole text is copied, and
   nothing is sent.

---

### User Story 6 - Change the origin for the invoice (Priority: P2)

The goods come from somewhere other than China. The clerk sets the origin in the header, and the TARIC rules are
re-applied to every line at once, without a model call.

**Why this priority**: it is needed for any non-Chinese invoice. It is a header control on top of feature 004's
behaviour.

**Independent Test**: on a store with written CN-8 codes, setting US shows the toast "Origin US — TARIC rules
re-applied to N lines, no model call", and the statuses follow the US rules.

**Acceptance Scenarios**:

1. **Given** an open invoice with origin CN, **When** the clerk sets US, **Then** the toast reads "Origin US — TARIC
   rules re-applied to N lines, no model call", and no model is called.
2. **Given** a TARIC-10 the clerk confirmed, **When** the origin changes, **Then** that code stays (feature 004).

---

### User Story 7 - Admin page for the operator and the course evaluators (Priority: P3)

Everything the clerk never needs moves to an Admin page behind the "Admin ⚙" link: the rules, data versions, cost,
the evaluation table, the audit export and the agent chat.

**Why this priority**: the clerk does not need these. The evaluator and the forwarder's operator do, and the course
requires them to be visible.

**Independent Test**: the Admin page shows its five sections with today's values. A threshold change there
re-routes the unconfirmed lines without a model call and leaves clerk-confirmed codes alone.

**Acceptance Scenarios**:

1. **Given** the Admin page, **When** it opens, **Then** it shows the header "CargoLint · Admin" with "← Back to
   shipment", and a left navigation: Rules, Data, Cost, Quality, Ask the agent.
2. **Given** Rules, **When** the operator moves the threshold, **Then** every unconfirmed line is re-routed without a
   model call, and clerk-confirmed lines are never touched.
3. **Given** Quality, **When** it opens, **Then** it shows the latest evaluation runs (Run | CN-8 exact | HS-6 top-3)
   and offers "Export audit trail".

---

### Edge Cases

- **A flagged line routed to review** (vague, confidence at or above the ask floor): its accept is locked until the
  description is updated and re-checked (constitution Principle I). So it shows red with "Update", never a yellow
  pick.
- **A re-checked line that was ever flagged**: it never turns green by itself. It shows yellow "Confirm: <code>"
  until the clerk confirms (Principle I).
- **An automatically accepted code the clerk disagrees with**: "Change" on the green row opens kind (a). A new HS-6 or
  CN-8 runs the later steps again, as for a review line. A new TARIC-10 among several subdivisions is confirmed in
  kind (b), with no model call.
- **An unreadable line** (a scan that could not be read): it shows red "Ask: unreadable line", because the store
  refuses to accept a line without a description check. The clerk types what it says, or asks the shipper.
- **A threshold lowered on Admin › Rules**: a line whose HS-6 becomes decided without the CN-8 step shows yellow "Pick:
  CN-8, <n> lines". No model runs.
- **Failures**:
  - A failed check shows red "Check failed" with "Re-check line" and no question.
  - A failed CN-8 step leaves the HS-6 decided and offers a yellow pick of the CN-8 lines.
  - A model or network failure during a check or re-check fails that line only (Principle V).
- **TARIC not available or not loaded**: the line stops at 8 digits. Its code shows those 8 digits with the reason,
  and the line can be green.
- **Empty counts**: with no green lines, "Accept all" is absent. With no red lines, "Draft shipper email" reads
  "(0 lines)" and cannot be opened.
- **Shipper not known**: the email's greeting is generic.
- **A second file while an invoice is open**: "Open another file" in the header offers the drop zone and the sample.
  The clerk confirms before it replaces the open invoice, as today. "+ Check one more line" adds to the open invoice.
- **A new line or a re-check while a check runs**: it waits until the running check ends. A re-check's edit is stored
  only when it starts.
- **A shipper reply that contradicts the file**: the expanded row shows the contradiction note, as today.
- **Untrusted text**: a description typed into "Check one line" or the description field is data, never an
  instruction (Principle II).
- **Producer names**: the TARIC snapshot names no companies behind additional codes (out of scope since feature
  004). Kind (b) shows the subdivision descriptions as TARIC states them.

## Requirements *(mandatory)*

### Functional Requirements

#### Page and header

- **FR-001**: The clerk's work MUST happen on one main page without a side panel. Its header shows:
  - "CargoLint";
  - once a file is open, its name and line count ("sample_packing_list.xlsx · 12 lines");
  - the origin field (CN by default);
  - once a file is open, "Open another file", disabled while a check runs;
  - the link "Admin ⚙".
- **FR-002**: The main page MUST NOT show any of these:
  - a chat;
  - reference, shipper or filing fields;
  - the auto-accept threshold;
  - tokens or cost;
  - raw confidence numbers in the table.

  Confidence MUST appear only inside an expanded row.

#### Starting a check

- **FR-003**: Before an invoice is open, the page MUST show:
  - a drop zone "Drop a packing list or invoice here", listing the formats and "one file per shipment";
  - "Try the sample invoice", which opens the bundled 12-line sample;
  - a "Check one line" input with the hint "Type a goods description and press Enter, e.g. bicycle frames,
    aluminium", which checks one description as a one-line invoice;
  - the table's headers over "No lines yet — drop a file or type one description".
- **FR-004**: While a check runs, each line still in progress MUST show a grey dashed dot and the step running, and
  its code MUST fill in as its steps finish. While a file is read, before any line exists, the page MUST show
  "Checking <file name>…" instead of the empty state.

#### Summary

- **FR-005**: After a check, a summary MUST read "N lines checked in T s · A ready · B need a pick · C need the
  shipper", with a bar split into green, yellow and red in those proportions. Failed checks and lines still being
  checked are counted apart, as " · F check failed" and " · R updating", each shown only when above 0.
- **FR-006**: "Accept all K ready" MUST confirm, in one action, every green line the clerk has not yet confirmed.
  - K counts those lines, and the action is absent when K is 0.
  - The clerk MAY tick Ready lines and accept only those.
  - Only Ready lines can be selected for acceptance; yellow and red lines are resolved one by one.

#### The table

- **FR-007**: One table MUST list every line in file order, with the columns ✓ | # | Description | Code | Status |
  Action, where ✓ is the Accept control (FR-006, FR-011). Description is the line as filed, Chinese and English
  together.
- **FR-008**: Code MUST show the 10-digit TARIC code as "dddd dd dd dd", with each digit not yet decided shown as an
  underscore. Examples:
  - "____ __ __ __": nothing decided;
  - "9503 00 __ __": the HS-6 decided;
  - "8714 91 10 __": the CN-8 written;
  - "9617 00 00 00": the TARIC-10 written.

  Only digits written by rule or confirmed by the clerk count as decided; a suggestion does not. A line that stops
  at 8 digits MUST show its 8 digits and say why ("TARIC not available" or "TARIC not loaded").
- **FR-009**: Status MUST be one of three colours, with text that names the decision:
  - **green**: "Ready" when nothing is left to decide, or "Accepted" once the clerk has confirmed the line;
  - **yellow**: "Pick: …" naming the choice ("Pick: 10 or 90", "Pick: 9 options, 3 AD", "Pick: 3 candidates"), or
    "Confirm: <code>" when a single code is left to confirm. That is a line ready to accept after an update, a single
    subdivision under trade defence, or a CN-8 whose TARIC step did not finish;
  - **red**: "Ask: …" with a short question ("Ask: the toy cars incorporate a motor?", "Ask: what exactly is
    “spare parts”?", "Ask: unreadable line"), or "Check failed".

  A line still being checked shows a grey dashed dot and the running step (FR-004).
- **FR-010**: The colour, text and expanded-row kind MUST derive only from the stored line, through the single mapping
  in Key Entities. The stored line means its route, flag, CN-8 and TARIC-10 states and the clerk's decisions. The
  page MUST NOT compute a route of its own (Principle I).
- **FR-011**: Action MUST read "Choose" for yellow lines, "Update" for red lines and "Change" for green lines.
  In-progress lines show none.
  - On a red row, the Accept control MUST also be shown, disabled, with the lock reason next to it (Principle VI).
  - The reason says what blocks acceptance and what unlocks it, built from the stored line:
    - a flagged description: "Locked: ICS2 unacceptable term 'spare parts' — update the description and re-check";
    - an unreadable line: "Locked: the description could not be read — update the description and re-check";
    - an open CN-8 question: "Locked: the CN-8 depends on <attribute> — update the description and re-check";
    - a line the clerk sent to the shipper: "Locked: sent to the shipper — update the description and
      re-check";
    - a failed check: "Locked: the check failed — re-check the line".
- **FR-012**: The short questions and the pick texts MUST be built from stored results, without a model call:
  - the missing CN-8 attribute;
  - the matched stop word or term with the facts to ask for;
  - the candidate count;
  - the subdivisions' last two digits and their anti-dumping count.

#### Expanded rows

- **FR-013**: Choosing a line's action, or the line itself, MUST expand it in place, under its row, in the kind its
  state maps to, with "▲ close".
  - Every expanded row of a line with candidates MUST show its top-3 HS-6 candidates, each with its confidence, its
    reasoning and its EBTI precedent (Principle III).
  - It MUST show the line's contradiction note, when it has one, and the fields extracted from a shipper's reply, as
    feature 001 does.
- **FR-014**: **Kind (a), choose the HS-6 or the CN-8**:
  - It MUST explain the choice in two lines: what decides the code, from the stored rationale; and that the top
    candidate leads at N % but is under the threshold, so the clerk decides and TARIC runs after the pick.
  - It MUST show a table Code | Description · precedent | Confidence | Pick with up to three HS-6 candidates, the
    leader pre-selected:
    - each has its reasoning, its EBTI precedent link or "no close precedent", and a confidence bar with its
      percentage;
    - an HS-6 whose subheading has one CN-8 line shows that 8-digit code;
    - a last row, "Other HS-6 code…", takes a typed code, which the store checks against the loaded nomenclature
      (feature 001 FR-023).
  - In its CN-8 form, the table MUST list every CN-8 line under the decided HS-6, the chosen one pre-selected. Only the
    model's chosen CN-8 carries a confidence and a precedent.
  - It MUST offer "Confirm <code>" with the note "then TARIC-10 runs on this code". The click records the clerk's
    decision and returns at once, without waiting for the model. The CN-8 step and the TARIC step then run in the
    background, as today (clarification 3), and the line turns green or offers kind (b).
  - "None of these → ask shipper" MUST send the line to the shipper (kind (c)).
  - Opened by "Change" on a green line (clarification), it MUST also show the decided codes and who decided them,
    with the TARIC-10's duty, anti-dumping duty and measures when there is one. The decided HS-6 is pre-selected,
    "Other HS-6 code…" is offered, and a switch offers the CN-8 lines under it, the decided one pre-selected. When the CN-8 has several TARIC-10
    subdivisions, the switch also offers kind (b) (FR-015). A code the clerk confirms there follows the flow above, or
    FR-015's for a TARIC-10. The code already decided cannot be confirmed again there.
- **FR-015**: **Kind (b), choose the TARIC-10**:
  - It MUST explain the choice: the CN-8 with its label, how many of the subdivisions carry anti-dumping or
    countervailing measures for the origin, that the pick confirms both the CN-8 and the TARIC-10, and the CN-8's confidence and precedent link.
  - It MUST show a table Code | Description | Duty | Anti-dumping | Pick:
    - Description comes from the snapshot;
    - Duty is the third-country duty, and any preference, for the origin;
    - Anti-dumping is the anti-dumping or countervailing rate, or the range of rates, for the origin, in red, or
      "none".
  - The model's suggestion, if any, MUST be pre-selected.
  - "Confirm <code>" MUST confirm the TARIC-10 and the CN-8 it sits under (feature 004), and the row turns green.
  - "None of these → ask shipper" MUST send the line to the shipper, with a question that lists the subdivisions
    (feature 004 FR-009).
  - An "All measures" expander MUST show feature 004's grouped measures, with the EZT-online link and the code to
    copy.
  - "Open in EU TARIC ↗" MUST link the selected code.
  - Opened from "Change" on a green line (clarification), it MUST pre-select the written TARIC-10. Confirming another
    subdivision MUST call no model, and the row stays green.
- **FR-016**: **Kind (c), ask the shipper, then update and re-check**:
  - An "Ask the shipper" box MUST show the question, with "Copy question".
  - For a vague line it MUST show the top candidates with their confidences, and its HS-6 candidates (FR-013). When
    the top two differ by at most 10 points, the line ends with "— too close to call" (clarification).
  - A "Reason" line MUST state the stored reason in plain words:
    - the matched ICS2 term or firm stop word, which takes precedence ("Reason: ICS2 unacceptable term 'spare
      parts'", "Reason: firm stop word 'gift'");
    - for a line flagged as vague by the judgement, "Reason: candidates too close" when its candidates are close as
      defined above, otherwise the vagueness reason ("Reason: vague description — <reason>");
    - an unreadable description ("Reason: the description could not be read");
    - the missing CN-8 attribute;
    - or the clerk's own decision to ask.
  - It MUST show "Update the description with the shipper's answer", pre-filled with the current description, with
    the hint "Original: '<text>' — kept in the audit trail as 'description updated by clerk'". <text> is the
    description being replaced. A long bilingual description MUST never be cut.
  - It MUST offer "Re-check line", noting that all steps run again from the stop-word check.
- **FR-017**: "Re-check line" MUST check that line only, from the stop-word check onwards, as a new version created
  by the clerk.
  - The audit trail MUST record "description updated by clerk" with the original text.
  - After the re-check the row collapses and shows its new code and status.
  - While another check runs, the re-check waits, and the edit is stored only when the re-check starts. So a running
    check never classifies the new version without its description check.
  - A line that was ever flagged MUST NOT turn green without the clerk's confirmation (Principle I).

#### Under the table

- **FR-018**: Under the table MUST be "Export CSV", "Export JSON", "Draft shipper email (C lines)" and "+ Check one
  more line".
- **FR-019**: The exports MUST keep feature 004's format: the 21 existing columns plus `cn8` and `taric10`, and the
  same JSON keys. The export file name uses the invoice id (Assumptions).
- **FR-020**: "Draft shipper email" MUST open a text block under the table, not a dialog. It is titled "Email to
  shipper — generated from the C open questions, no model call", with an "EN | 中文" toggle and "Copy email". It
  contains:
  - a subject naming the invoice id and the number of lines that need more detail;
  - a greeting with the shipper's name when known, otherwise a generic greeting;
  - an introduction;
  - one numbered question per red line with a question (a failed check has none), giving the line number, the
    original description and the question;
  - a closing and sign-off placeholders for the clerk's and the forwarder's names.
- **FR-021**: Both language versions MUST come from fixed templates, with no model call. In the Chinese version every
  template part is Chinese, apart from the acronyms ICS2 and TARIC. English stays only in data: descriptions, names,
  the invoice id, quoted terms, TARIC codes and texts, and model-written questions. "Copy email" MUST copy the whole
  text. Nothing is ever sent.

#### Origin

- **FR-022**: Setting the origin in the header MUST re-apply the TARIC rules to every line with a CN-8, without a
  model call (feature 004). It MUST then show the toast "Origin <code> — TARIC rules re-applied to N lines, no model
  call". TARIC-10 codes the clerk confirmed stay. The field keeps its value across pages and before a shipment
  exists, and every new shipment starts with it.

#### Admin page

- **FR-023**: An Admin page, behind "Admin ⚙", MUST show:
  - the header "CargoLint · Admin" with "← Back to shipment";
  - a left navigation: Rules, Data, Cost, Quality, Ask the agent;
  - the note that the page is for the operator and course evaluators.
- **FR-024**: **Rules** MUST hold:
  - the auto-accept threshold, 60 to 99 %, default 85 %, with the note "re-routes every unconfirmed line, no model
    call; clerk-confirmed lines are never touched";
  - the hybrid-retrieval switch (BM25 and vectors).

  Both values MUST survive a switch between the pages, and new shipments start with them. "Stricter routing for new
  shippers" is not part of this feature (clarification 2).
- **FR-025**: **Data** MUST show:
  - the EBTI ruling count;
  - the TARIC snapshot date, its CN-8 mismatch count (feature 002 FR-024) and its source;
  - the model and the service it runs on;
  - a disabled "Refresh (later)" placeholder.
- **FR-026**: **Cost** MUST show this shipment's cost, line count and check time, and the session's total cost and
  tokens.
- **FR-027**: **Quality** MUST show:
  - the latest evaluation runs as a table, Run | CN-8 exact | HS-6 top-3, with the current iteration and the SC-002
    validation run;
  - "Export audit trail";
  - where the full history is kept.
- **FR-028**: **Ask the agent** MUST hold today's chat, unchanged in behaviour, together with:
  - the Sources, Retrieval steps and Assistant notes of each check;
  - the "What I can and cannot do" statement, shown at all times.

  It is the only place the chat appears.

#### Model calls, speed and the unchanged backend

- **FR-029**: Expanding a row, confirming, batch accepting, changing the origin, drafting the email and exporting
  MUST NOT wait for the model. On the 12-line sample, each MUST respond within 1 s. Model calls happen only:
  - in a check (upload, sample, one line);
  - in a re-check;
  - in the background steps that follow a confirm (FR-014);
  - in the Admin page's chat.
- **FR-030**: These MUST behave as features 001 to 004 define them:
  - the routing, the threshold rule and the flagged-line lock;
  - code-existence checks and the TARIC write rules;
  - clerk confirmations and the audit trail;
  - the command-line tools.

  The additions are:
  - the line version created by the clerk's edit;
  - `agent.recheck_line`, which re-checks that one line;
  - the background job kind `recheck`, which runs it (FR-017).

### Key Entities

- **Line status**: what the table shows for a line: colour, text, action and expanded-row kind. It is derived from the
  stored line, never stored itself:

| Stored state of the line | Colour | Status text | Action | Expanded kind |
|---|---|---|---|---|
| Still being checked, or a re-check waiting | grey, dashed | the running step ("Running TARIC step…"), "Queued: re-check" | none | none |
| Not checked yet, with no check running (transient: a failed job fails it) | grey, dashed | "Not checked yet" | none | none |
| Nothing left to decide: the HS-6 decided, the CN-8 written, the TARIC-10 written or not available, nothing pending | green | "Ready", or "Accepted" once the clerk confirmed | Change | (a), on the decided codes; (b) for a TARIC-10 among several subdivisions |
| Not flagged, routed to review below the threshold | yellow | "Pick: <n> candidates" | Choose | (a) HS-6 |
| Ready to accept after an update | yellow | "Confirm: <code>" | Choose | (a) |
| The HS-6 decided; the CN-8 to confirm, the CN-8 step failed, or the HS-6 decided without the CN-8 step | yellow | "Pick: CN-8, <n> lines" | Choose | (a) CN-8 |
| The CN-8 written, but the TARIC step after it did not finish | yellow | "Confirm: <CN-8>" | Choose | (a) CN-8 |
| The CN-8 written, the TARIC-10 to confirm | yellow | "Pick: 10 or 90" / "Pick: 9 options, 3 AD" | Choose | (b) |
| Routed to ask the shipper: stop word, vague below the ask floor, open CN-8 question, or sent by the clerk | red | "Ask: <short question>" | Update; Accept disabled, with the lock reason | (c) |
| Flagged (vague or stop word) and routed to review | red | "Ask: <short question>" | Update; Accept disabled, with the lock reason | (c) |
| Unreadable: the scan could not be read | red | "Ask: unreadable line" | Update; Accept disabled, with the lock reason | (c) |
| Check failed | red | "Check failed" | Update; Accept disabled, with the lock reason | (c), without a question |

- **Code display**: the decided digits of the 10-digit code in groups, with underscores for undecided digits, or the
  8 digits and the reason when the line stops there.
- **Line version created by the clerk**: a new version of a line whose description the clerk updated. It records the
  original text in the audit trail ("description updated by clerk") and is checked like any other version.
- **Shipper email draft**: subject, greeting, introduction, numbered questions, closing and sign-off, in English or
  Chinese, built from templates and the red lines. It is shown and copied, never sent and never stored.
- **Admin settings**: the threshold and the hybrid-retrieval switch, for the session only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The author's own timed run of the 12-line sample in the browser takes under 5 minutes, without
  documentation: upload, resolve every yellow and red line, then export. It is recorded in quickstart.md. A scripted
  walkthrough of the same steps records the action count and the machine time of each step, reported in the
  evaluation report.
- **SC-002**: On the 12-line sample, each of the following responds within 1 s and never waits for the model:
  expanding a row, confirming, batch accepting, changing the origin, drafting the email, and each export. A test
  counts the model calls made before each response.
- **SC-003**: On the sample, every yellow and red status names its choice or question. No line shows a generic
  "Review", "Needs action" or "to confirm".
- **SC-004**: For every row of the Line status table, the colour, text, action and kind shown equal the mapping:
  0 mismatches in the tests.
- **SC-005**: For the same decisions, the CSV and JSON exports are identical to feature 004's.
- **SC-006**: For the sample, the email draft lists exactly the red lines with a question, one numbered question
  each, in English and in Chinese. In the Chinese draft, English appears only in data (FR-021). Tests check both.
- **SC-007**: The 683 tests of features 001 to 004 that do not import today's UI package pass unchanged. Of the 27
  that do, the 13 that test removed modules are replaced by new UI tests. The 14 that test functions that stay pass
  unchanged. The new UI tests cover:
  - the three expanded-row kinds;
  - batch acceptance;
  - the English and Chinese email;
  - the origin toast;
  - the underscore code rendering;
  - the clerk's description edit and its audit entry;
  - the disabled Accept control and its lock reason on every kind of red row;
  - "Change" on a green row and the override that follows, including the TARIC-10 re-pick;
  - the typed HS-6 code, kind (b)'s "None of these → ask shipper", and "Open another file".
- **SC-008**: An origin change re-applies the rules to every line with a CN-8, reports that count, and makes no model
  call.

## Assumptions

- **The wireframes** (Claude Docs, "CargoLint UI redesign — wireframes", read on 2026-10-23) are matched, with these
  deliberate differences:
  - confidences and the threshold show as percentages, and the threshold stays 85 % (clarification 1);
  - the "New shipper: stricter routing" switch is left out (clarification 2);
  - an undecided line's code shows underscores only. The kind (a) mockup shows "8518 __ __ __", but the wireframe's
    own rule is that underscores are what is still undecided;
  - a line whose top candidates are close keeps the colour its stored route gives. The wireframe sends it straight to
    kind (c), but the backend has no closeness rule. A vague line sent to the shipper shows its candidates'
    confidences, and says "too close to call" only when the top two are within 10 points (clarification);
  - the producer names in the kind (b) mockup are placeholders, and the descriptions come from TARIC;
  - after a re-check, a line that was ever flagged needs the clerk's confirmation (Principle I). A line never flagged
    may turn green, as the mockup shows;
  - a red row also shows the Accept control disabled with its lock reason (Principle VI), which the wireframes do not
    draw;
  - a green row offers "Change" (clarification), which the wireframes do not draw;
  - an unreadable line shows red rather than a pick, because its accept is locked (Principle VI).
- **Native components only** (Principle VI): the dots, the split bar and the expandable rows follow the wireframes as
  closely as native components allow, with no custom HTML, CSS or scripts.
- **File types**: the drop zone accepts today's types (XLSX, CSV, PDF, JPG, PNG). The wireframe names the three main
  ones.
- **The invoice id** in the email subject and the export file name is the file name without its extension; the
  sample uses its bundled reference. Today's parser reads no invoice number, and the reference field is removed.
- **The shipper's name** comes from today's detection; without one, the greeting is generic.
- **"Ask: …" texts** are short forms built in code from stored results; the full question is in the expanded row.
- **Batch acceptance** confirms only green lines. It records the clerk's confirmation of their codes, as feature 004
  does for a confirmation on an auto-accepted line, so the export reads "accepted" by the clerk with `decided_how`
  "auto".
- **The origin field** takes a two-letter country code, CN by default.
- **The Admin page** has no access control, since there are no accounts. Its settings last for the session.

## Dependencies

- **Constitution v1.3.0** (amended on 2026-10-23 for this feature) allows this design:
  - drafting a shipper email from string templates, without a model call, is in scope; sending it is not (FR-020,
    FR-021);
  - cost, the sources and retrieval steps, the hybrid-search switch and the knowledge-base statement live on the
    Admin page, and the main page has no sidebar (Principles IV and VI);
  - the threshold keeps its 85 % default and 60–99 range, and is set on Admin › Rules (Principle I);
  - its UI Design Contract describes this spec's main page and Admin page;
  - Principle VI still requires a locked Accept to be shown disabled with its reason (FR-011).
- **One additive backend change, accepted by the author on 2026-10-23** (FR-017, FR-030). It changes no routing, no
  guardrail and no existing behaviour. It consists of:
  - the line version created by the clerk's edit, and its audit entry;
  - `agent.recheck_line`, which re-checks that one line;
  - the background job kind `recheck`, which runs it.
