# Contract: the two pages

The clerk-facing elements of feature 005, with what each one shows and does. Texts are exact; `{…}` marks a value from
[view.md](view.md).
- Every element is a native Streamlit component; the plan uses no custom HTML, CSS or JavaScript (Principle VI).
- The store is read and written only through `agent/store.py`.
- The model is reached only through background jobs that call `agent/` functions (§6).

## 1. Navigation (`app.py`)

- **Loading**: `app.py` loads the knowledge base and the store as today.
- **Pages**: it then runs `st.navigation([main, admin], position="hidden")`. `main` and `admin` are `st.Page`s built
  from functions that call `ui.main_page.render(store, kb, admin)` and `ui.admin.render(store, kb, main)`.
  - `main` is the default page, titled "CargoLint".
  - `admin` has `url_path="admin"` and the title "CargoLint · Admin".
- **Links**: the pages link to each other with `st.page_link`: "Admin ⚙" in the main header, "← Back to shipment" on
  the Admin page. No page list is shown anywhere.
- **Missing key**: without `OPENROUTER_API_KEY`, the page stops with "OPENROUTER_API_KEY is not set. Set it as an
  operating-system environment variable and restart CargoLint."
  - Today's message also names a `.env` file. CLAUDE.md keeps the key as an operating-system environment variable.
  - `agent/config.py` still loads a `.env` when one is present; that stays unchanged.
- **Sidebar**: the main page writes nothing to `st.sidebar`, so it has no sidebar (FR-001). The Admin page's left
  navigation is its sidebar (§8).
- **Values kept across pages**: widgets whose value must survive a page switch use `persist_state="session"`
  (Streamlit 1.65; research R-19). These are the origin field, the threshold, the hybrid switch and the Admin section.

## 2. Main page: header and starting a check (`ui/main_page.py`, `ui/upload.py`)

**Header**, one row of columns:
- "CargoLint";
- once a file is open, "{file name} · {N} lines", with the file name escaped (`view.md_escape`); a typed line shows
  "Typed lines · {N} lines";
- **the origin field**:
  - an `st.text_input` labelled "Origin", two characters, upper-cased, with `persist_state="session"`;
  - its value starts as the shipment's origin, else CN, set in session state before the field renders. Streamlit
    would otherwise start it empty;
  - its help: "The goods' country of origin for TARIC, two letters; CN by default";
  - under it, the caption `view.snapshot_caption(kb)`: "TARIC snapshot {date}", or "TARIC not loaded". This shows the
    snapshot date for every TARIC-10 in the table (Principle I).
- **"Open another file"**: once a shipment has lines, the drop zone and "Try the sample invoice" collapse into the
  header. An `st.popover("Open another file")` (key `open_file_button`) holds them, with the replacement question,
  so nothing pushes the table down.
  - It is disabled while any job runs, with the help "Wait for the running check".
- "Admin ⚙", the link.

**Changing the origin**:
- With a shipment open, it calls `agent.apply_taric_origin(store, kb, value)` and shows
  `st.toast(view.origin_toast(message))`. There is no model call (FR-022).
- A refused value shows "Origin not changed: {reason}", and the field returns to the shipment's origin.
- With no shipment open, a valid value is kept. An invalid one shows "Origin not changed: {reason}", and the field
  returns to the kept origin, CN by default.
- Every new shipment starts with the kept origin (`upload.open_shipment`, below).

**Empty state**: shown when there is no shipment, or one with no lines. Its controls are disabled while any job runs.
- **Drop zone**: an `st.file_uploader` labelled "Drop a packing list or invoice here", accepting XLSX, CSV, PDF, JPG
  and PNG.
  - Its caption reads "XLSX · CSV · PDF · JPG · PNG — up to 20 MB, one file per shipment".
  - Caps are checked first, as today (`check_caps`), and a refused file shows the parser's message.
- **"Try the sample invoice"**: opens the bundled 12-line sample, with reference "HOL-2026-10-0472".
- **"Check one line"**: an `st.text_input` with the placeholder "Type a goods description and press Enter, e.g.
  bicycle frames, aluminium" and at most `MAX_DESC_CHARS` characters. Enter checks it as a one-line shipment.
- **The table**: its headers over "No lines yet — drop a file or type one description".

While a file check runs and no line exists yet, the page shows "Checking {file name}…" instead of the empty state.
"Check one line" never queues: it is disabled while a job runs. Only "+ Check one more line" queues (§7).

**Opening a file or the sample** (`upload.begin`):
- If a shipment with lines is open, the replacement question comes first, as today: "A checked shipment is open.
  Replace it with {name}? Results, counts and cost reset.", with "Replace" and "Cancel".
- Otherwise:
  1. open the new shipment with `upload.open_shipment(store, reference)`. The reference is the bundled reference for
     the sample, or the file name without its extension;
  2. register the file, and start a **check** job with that file reference (§6).
- The chat transcript is cleared, as today, because it belongs to the shipment.

**Every new shipment** opens through `upload.open_shipment(store, reference="")`. It adds the old shipment's usage
to `session_usage`, and starts the new shipment with the Admin threshold and hybrid values and the kept origin.
Uploads, the sample, "Check one line" and the Admin chat's `_ensure_shipment` all use it.

## 3. Summary bar (`ui/main_page.py`)

Shown once a shipment has lines.
- **While a check job runs**: "Checking {N} lines… · {elapsed} s", over the split bar of the lines finished so far.
- **After it**:
  - `view.summary_text`, then `view.split_bar` on its own line;
  - "Accept all {K} ready" (primary), only when K > 0;
  - "Accept {n} selected", only when n Ready rows are ticked.
- Both buttons call `ui.actions.accept_ready(store, line_nos)` and rerun the page. No model call, and no job.

## 4. The decision table (`ui/table.py`)

- **Headers**: ✓ · # · Description · Code · Status · Action. The ✓ column is the Accept control (FR-006, FR-011).
- **Rows**: the lines in file order, in pages of 25, with page buttons under the table when there is more than one
  page.
- **Live refresh**:
  - the summary, the table and the blocks under it render in one `st.fragment`;
  - it is called with `run_every=1` while a job runs or waits, so codes and statuses fill in from the store every
    second;
  - when the job ends, the page finishes it (§6) and reruns the app.

Each row is an `st.columns` row built from `view.line_status` and `view.code_display`:

| Column | Content |
|---|---|
| ✓ | Ready: an enabled `st.checkbox` (key `accept_{line_no}`), collapsed label. Red: the same checkbox, disabled, with the lock reason as its help. Otherwise empty. |
| # | the line number |
| Description | the current version's Chinese and English text, escaped (`view.md_escape`), as a tertiary `st.button` that opens the row; grey rows show plain text. Red rows add a caption under it: ":material/lock: {lock reason}" (FR-011). |
| Code | `code_display.text` as inline code; its note as a caption |
| Status | the dot and the status text |
| Action | "Choose" (yellow), "Update" (red) or "Change" (green), an `st.button` that opens the row; empty for grey rows |

**Opening a row**:
- Choosing the description or the action sets `selected_line_no` to that line; choosing it again closes the row.
- The open row's content renders right under it, in a bordered `st.container`, with "▲ close" at its top right.
- Only one row is open at a time, and grey rows do not open.
- The Admin chat reads `selected_line_no` as its selected line, as today.

## 5. Expanded rows (`ui/expand.py`)

**At the top of every expanded row**:
- the line's contradiction note, as `st.warning`, when it has one;
- for a shipper-reply version, the extracted fields: "From the shipper's reply — material: {…} · part: {…} · use: {…}".
  Both are today's detail card behaviour (FR-013).

**The HS-6 candidates block** of [view.md](view.md) §5 appears in every expanded row of a line with candidates
(Principle III).

**The Pick column**:
- one button per row: "◉ Picked" (primary) on the picked row, "○ Pick" (tertiary) on the others;
- the pick is kept in `pick_{line_no}_{version_no}_{kind}_{form}`, pre-set as [view.md](view.md) §5 and §6 say
  (research R-14);
- `{form}` is `hs6`, `cn8` or `taric10`.

### 5.1 Kind (a): choose the HS-6 or the CN-8

- The two lines of `view.explain_a`.
- **The table**: Code | Description · precedent | Confidence | Pick.
  - Code is inline code.
  - Description is the escaped text, with the candidate's rationale as a caption under it (full text in its help) and
    the badge "history only" where set.
  - The precedent beside it is an `st.popover("BTI {member state} {reference}")`. It shows the reference, the code,
    the member state, the validity and the description, with "Open ruling ↗" when the ruling has a link. Without one,
    the caption reads "no close precedent" (Principle III).
  - Confidence is `st.progress(conf / 100, text="{conf} %")`, with the column caption "model estimate"
    (Principle III).
  - In the CN-8 form, the table lists every CN-8 line under the decided HS-6. Only the chosen one carries a confidence
    and a precedent (FR-014).
- **"Other HS-6 code…"**: the last Pick row of the HS-6 form.
  - Picking it shows an `st.text_input`, with the placeholder "e.g. 8452.90" and at most 7 characters, key
    `typed_{line_no}_{version_no}`.
  - "Confirm" sends the typed code to the store (feature 001 FR-023).
- **"Confirm {picked code}"** (primary), with the caption "then TARIC-10 runs on this code":
  - the HS-6 form: `store.set_decision(n, Decision(route=accepted, decided_code=…))`, then queue a **finer_codes** job
    for the line;
  - the CN-8 form: `store.confirm_cn8(n, cn8)`, then queue a **finer_codes** job with `taric_only=True` when
    `view.next_step` returns "TARIC step";
  - in both cases, close the row and rerun. The click never waits for the model (clarification 3).
- **"None of these → ask shipper"** (tertiary): `store.set_decision(n, Decision(route=ask_shipper))`; the row turns
  red.
- **A refused confirmation** shows "Not confirmed: {reason}" and changes nothing. This covers `LockedError`,
  `UnknownCodeError`, and a `ValueError` for an empty or malformed typed code.

### 5.2 Kind (b): choose the TARIC-10

- The two lines of `view.explain_b`, with the CN-8's precedent popover when it has one, and the caption "TARIC
  snapshot {date} · origin {XX}".
- When the suggestion failed: the caption "Suggestion unavailable: {error}".
- **The table**: Code | Description | Duty | Anti-dumping | Pick, from `view.subdivision_rows(agent.line_taric_view(…))`.
  The code is the full spaced code, and the anti-dumping cell is `:red[…]` unless it reads "none".
- **"Confirm {picked code}"** (primary): `store.confirm_taric10(n, code)`, which confirms the CN-8 too (feature 004).
  The row closes and turns green. No job.
- **"None of these → ask shipper"** (tertiary): `store.ask_shipper_for_taric(n, view.taric_question(view))` (feature
  004 FR-009). The row turns red, with "Ask: which TARIC subdivision applies?". No job.
- **"All measures"**: an `st.expander` for the picked subdivision, with:
  - its three groups as today's measure tables: Duties, Trade defence, Requirements;
  - "EZT-online ↗" (`st.link_button`);
  - `st.code("{code} {origin}")`.
- **"Open in EU TARIC ↗"**: `st.link_button` to `eu_taric_url(code, origin, snapshot_date)` for the picked code.

### 5.3 Kind (c): ask the shipper, then update and re-check

- **"Ask the shipper"** (not for a failed check): a bordered container with:
  - the full question in `st.code(question, language=None, wrap_lines=True)`;
  - the caption ":material/content_copy: Copy question — the copy button at the top right of the box" (research R-08).
- **For a line flagged as vague by judgement**: the candidates line of [view.md](view.md) §2.3. A line flagged by an
  ICS2 term or a stop word has none: its reason names the term. Every line with candidates also has the HS-6
  candidates block, open.
- **The reason line**.
- **"Update the description with the shipper's answer"**:
  - an `st.text_area`, pre-filled with the current description, so that a long bilingual text is never cut;
  - at most `2 × MAX_DESC_CHARS + 3` characters, the store's limit of 300 per language applying after the split;
  - its help reads "Original: '{current description}' — kept in the audit trail as 'description updated by clerk'".
    This is the text the audit records as `previous`.
- **"Re-check line"** (primary), with the caption "All steps run again for this line, from the stop-word check.":
  - **Checked at once**: the text is split with `view.split_description` and checked with `view.edit_problem(zh,
    en)`. An empty text shows "Write the goods description first."; a language part over 300 characters shows
    "Not re-checked: {reason}". Either changes nothing.
  - **Then** `runner.start_recheck(store, kb, n, zh, en)` runs, and the row closes:
    - **no job running**: it calls `store.update_description(n, zh, en)` (contracts/backend.md §1) and starts a
      **recheck** job;
    - **a job running** (any kind): it queues `(recheck, line_no, zh, en)` and shows "Waits for the running check".
      The edit is stored only when the re-check starts (§6), so no new version appears while a worker reads the
      store.
- **Results**: the row shows grey "Queued: re-check" while it waits, "Running stop-word check…" once it starts,
  then its new status.

### 5.4 Kind (a) on a green row: "Change"

A green row is never read-only. "Change", or the row's description, opens kind (a) on the decided codes, so the clerk
can override a code that was accepted automatically (spec clarifications). When the CN-8 has several subdivisions, the
switch also opens kind (b), to re-pick the TARIC-10.
- **The decided codes**: the first line of `view.explain_a(…, "a_change")`, with who decided each code.
- **For a line with a TARIC-10**:
  - "TARIC snapshot {date} · origin {XX}";
  - the written subdivision's description, duty and anti-dumping cells;
  - "All measures" and "Open in EU TARIC ↗", as in kind (b).
- **The switch**: `st.segmented_control`, keyed `change_level_{line_no}_{version_no}`, with these options:
  - "HS-6", the default;
  - "CN-8", when the decided HS-6 has more than one CN-8 line;
  - "TARIC-10", when the stored TARIC outcome has more than one subdivision.

  It is shown when it has more than one option.
- **The table of the chosen form**:
  - HS-6: as in §5.1, with "Other HS-6 code…". The decided HS-6 is pre-selected; when it was typed and is not among
    the candidates, "Other HS-6 code…" is pre-selected, holding it;
  - CN-8: as in §5.1, with the decided CN-8 pre-selected;
  - TARIC-10: kind (b) as in §5.2, with the written TARIC-10 pre-selected.
- **"Confirm {picked code}"**: disabled while the pick is the decided code, with the help "This is the current code".
  Another code follows §5.1 or §5.2 exactly:
  - an HS-6, picked or typed: `set_decision`, then a `finer_codes` job; the row goes grey, then green or yellow;
  - a CN-8: `confirm_cn8`, then a TARIC-only job when needed; the row goes grey, then green or yellow;
  - a TARIC-10: `confirm_taric10`, with no model call and no job; the row stays green with the new code.
- **"None of these → ask shipper"**: as in §5.1, or as in §5.2 in the TARIC-10 form.

## 6. Background jobs (`ui/runner.py`, `ui/jobs.py`)

- **One job runs at a time** (`job`, as today). Others wait in `job_queue`, which replaces `finer_codes_queue`.
- **Job kinds**:
  - `check`: an agent turn, for an upload, the sample or typed lines;
  - `finer_codes`: `agent.after_hs6_decision`;
  - `recheck`: `agent.recheck_line`, new;
  - `question` and `reply`: from the Admin chat.
- **Queued entries**: each waits as data, and touches the store only when its job starts, so nothing new appears while
  a worker reads the store:
  - a re-check waits as `(recheck, line_no, zh, en)`. When it starts, the runner calls `store.update_description`,
    then starts the job. If storing the edit fails then (`ValueError` or `KeyError`), the entry is dropped, and the
    page shows "Line {n}: re-check not started: {reason}";
  - a typed line waits as text, with the caption "Waits for the running check". Its line is added when its check
    starts;
  - a `finer_codes` entry waits as `(finer_codes, line_no, taric_only)`.
- **Coverage**, for `view.line_status`'s `activity`:
  - a running check covers every line;
  - a running `finer_codes`, `recheck` or `reply` job covers its line;
  - a queued `finer_codes` entry makes its line `"queued"`, and a queued re-check makes it `"recheck_queued"`.
- **Finishing**: `runner.finish(store, kb)` runs on the script thread when the job is done. It moves today's
  `_finish_job` here, with three changes:
  - **Chat records**: it adds the chat record of each check, reply and question, with its steps, sources and Assistant
    notes, for Admin › Ask the agent. A finished re-check also adds a record: "Line {n} re-checked", with that line's
    sources and retrieval steps, as a reply does today.
  - **Selection**: it never changes `selected_line_no`, so no row opens by itself. The old import of
    `ui.review.reset_selection` goes.
  - **Next job**: it starts the next queued entry and reruns the app.
- **A job that ends with an error** fails what it left pending, through the store (Principle V):
  - a check job calls `store.finalize_check()`;
  - a re-check calls `store.mark_failed(line_no, "re-check failed: {error}")` if the line is still pending;
  - a `finer_codes` error leaves the line yellow (view.md §1, rows 10 and 12);
  - the page shows `st.error` once: "Line {n}: {step} did not finish: {error}", or "The check did not finish:
    {error}".
- **Threads**: the worker thread never calls Streamlit (as today).

## 7. Under the table (`ui/main_page.py`, `ui/shipper_email.py`)

One row of buttons:
- **"Export CSV"**: `st.download_button` with `store.to_csv_bytes()` and `store.export_filename("csv")`;
- **"Export JSON"**: `st.download_button` with `store.to_json_bytes(knowledge_base_updated=kb.updated)` and
  `store.export_filename("json")`;
- **"Draft shipper email ({C} lines)"**: a button (key `email_button`) that toggles the flag `email_open`; disabled
  when C is 0;
- **"+ Check one more line"**: a button (key `more_line_button`) that toggles the flag `more_line_open`.

Each button keeps its own key, and the flags are plain session values.

The exports are disabled until a check has finished. Their bytes are unchanged from feature 004 (FR-019).

**The email block** (`email_open`), under the button row, in a bordered container (FR-020, FR-021):
- the title "Email to shipper — generated from the {C} open questions, no model call";
- `st.segmented_control` with "EN" and "中文" (key `email_lang`, default EN);
- the caption ":material/content_copy: Copy email — the copy button at the top right of the text";
- `st.code(shipper_email.draft(store, kb, lang).text, language=None, wrap_lines=True)`.

Nothing is sent, and the draft is not stored.

**One more line** (`more_line_open`): an `st.text_input` "Type a goods description and press Enter", with at most
`MAX_DESC_CHARS` characters. Enter adds the line to the open shipment as a typed line (`CreatedBy.paste`) and starts a
check job for it, or queues it (§6).

## 8. Admin page (`ui/admin.py`)

**Header**:
- "CargoLint · Admin", with "← Back to shipment" (`st.page_link`);
- the caption "For the operator and course evaluators. The clerk's work happens on the shipment page."

**Left navigation**: `st.sidebar.radio` over Rules, Data, Cost, Quality and Ask the agent. Its key is `admin_section`,
with `persist_state="session"`, and Rules is the default.

**Rules**:
- **Threshold**: `st.slider("Auto-accept threshold", 60, 99, key="threshold", format="%d %%",
  persist_state="session")`.
  - Before it renders, a missing `threshold` is set in session state: the shipment's threshold, else 85. The slider
    would otherwise start at 60.
  - Its change calls `store.set_threshold`.
  - Caption: "Re-routes every unconfirmed line, no model call; clerk-confirmed lines are never touched."
- **Hybrid search**: `st.toggle("Hybrid search (BM25 and vectors)", key="hybrid", persist_state="session")`.
  - Before it renders, a missing `hybrid` is set: the shipment's setting, else on.
  - Its change calls `store.set_hybrid`.
- New shipments start with both values, which survive a page switch.

**Data**:
- "EBTI rulings: {len(kb.bti):,}";
- `view.taric_statement(kb)`: "TARIC snapshot: {date} · {n} CN-8 mismatches · Swedish Customs Tariff File
  Distribution", or "TARIC not loaded" (feature 002 FR-024);
- "Model: {settings.chat_model} via OpenRouter";
- the knowledge-base statement `view.kb_statement(kb)`, which includes "updated {kb.updated}" (Principle IV);
- a disabled "Refresh (later)" button.

**Cost**:
- **This shipment**: tokens, cost in euros, line count and check time, from `store.shipment.usage` and the summary's
  seconds;
- **This session**: total tokens and cost, which are `session_usage` plus this shipment's.

**Quality**:
- **The table**: `st.table(view.quality_rows(...))`, with the columns Run | CN-8 exact | HS-6 top-3.
  - Two rows come from the last two entries of `tests/eval/cn8_eval_history.json`: "CN-8 eval, iteration {n}", with
    "{top1}/{n} ({pct} %)" and "—".
  - One row comes from `tests/eval/results.json`: "HS-6 labelled set, hybrid", with "—" and "{top3}/{clear_lines}".
  - Under the table, one caption per iteration: "Iteration {n}: {change}", cut at 160 characters.
- **No file**: the section reads "No evaluation run yet."
- **"Export audit trail"**: `st.download_button` with `view.audit_csv(store)`.
- **History**: the caption "Full history: tests/eval/cn8_eval_history.json and tests/eval/cn8_eval.md."

**Ask the agent**: `ui.chat.render(store, kb)`, today's chat, unchanged in behaviour (FR-028):
- **Kept**: the transcript, the chat input, and the Sources, Retrieval steps and Assistant notes.
- **"What I can and cannot do"**: an expander shown at all times, not only before a check. Its "Can" list adds "draft
  the email to the shipper (you copy and send it)".
- **The quick action "Which terms does customs reject?"** stays. The quick actions that check a description or open
  the sample move to the main page.
- **New shipments**: its `_ensure_shipment` opens them through `upload.open_shipment`, like every other path.
- **The rerun after a job**: the chat's live turn no longer reads `layout_has_lines`. When a job ends, it reruns the
  app through `runner.finish`, as the main page does.

## 9. Model calls and response time per action

Each action below returns without waiting for a model, within 1 s on the 12-line sample (FR-029, SC-002).

| Action | Store calls | Model calls before the response | Job started or queued |
|---|---|---|---|
| Open or close a row | none | 0 | none |
| Confirm an HS-6, picked or typed (a), also from Change | `set_decision` | 0 | `finer_codes` |
| Confirm a CN-8 (a), also from Change | `confirm_cn8` | 0 | `finer_codes`, TARIC only, when needed |
| None of these → ask shipper (a) | `set_decision` | 0 | none |
| Confirm a TARIC-10 (b), also from Change | `confirm_taric10` | 0 | none |
| None of these → ask shipper (b) | `ask_shipper_for_taric` | 0 | none |
| Accept all K ready, accept selected | `confirm_taric10` or `confirm_cn8`, per line | 0 | none |
| Change the origin | `apply_taric_origin` (agent, no model) | 0 | none |
| Draft the email, switch its language | none | 0 | none |
| Export CSV or JSON | `to_csv_bytes`, `to_json_bytes` | 0 | none |
| Re-check line (c) | `update_description`, when the job starts | 0 | `recheck` |
| Upload, sample, open another file, check one line, one more line | `new_shipment`, `set_taric_origin`, `register_file` or `add_lines` | 0 | `check` |
| Admin threshold or hybrid switch | `set_threshold`, `set_hybrid` | 0 | none |

The model is called only inside jobs: a check, a re-check, the steps after a confirmation, and the Admin page's chat.

## 10. Rules for every element

- **Untrusted text**: the descriptions, matched terms, the shipper name, the uploaded file name and model text. It is
  escaped with `view.md_escape` before it reaches a label or Markdown, and it is never used as a key, a path or an
  instruction (Principle II).
- **Languages**: Chinese and English are shown together; the UI text is English. Only the email draft is in Chinese,
  when 中文 is chosen (Principle VI).
- **Confidence**: it appears only inside an expanded row, as a percentage with a bar, labelled as a model estimate
  (FR-002, Principle III).
- **Nothing from FR-002**: the main page shows no chat, threshold, tokens or cost.
