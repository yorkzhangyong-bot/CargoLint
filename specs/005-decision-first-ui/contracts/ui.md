# Contract: the two pages

The clerk-facing elements of feature 005, with what each one shows and does. Texts are exact; `{…}` marks a value from
[view.md](view.md). Every element is a native Streamlit component; the plan uses no custom HTML, CSS or JavaScript
(Principle VI). The store is read and written only through `agent/store.py`, and the model is reached only through
background jobs that call `agent/` functions (§6).

## 1. Navigation (`app.py`)

- `app.py` loads the knowledge base and the store as today. It then runs
  `st.navigation([main, admin], position="hidden")`, where `main` and `admin` are `st.Page`s built from functions
  that call `ui.main_page.render(store, kb, admin)` and `ui.admin.render(store, kb, main)`.
- `main` is the default page, titled "CargoLint". `admin` has `url_path="admin"` and the title "CargoLint · Admin".
- The pages link to each other with `st.page_link`: "Admin ⚙" in the main header, "← Back to shipment" on the Admin
  page. No page list is shown anywhere.
- Without `OPENROUTER_API_KEY`, the page stops with "OPENROUTER_API_KEY is not set. Set it as an operating-system
  environment variable and restart CargoLint." Today's message also names a `.env` file, which the project does not
  use.
- The main page writes nothing to `st.sidebar`, so it has no sidebar (FR-001). The Admin page's left navigation is its
  sidebar (§8).

## 2. Main page: header and starting a check (`ui/main_page.py`, `ui/upload.py`)

**Header**, one row of columns:
- "CargoLint";
- once a file is open, "{file name} · {N} lines" (a typed line shows "Typed lines · {N} lines");
- **the origin field**: an `st.text_input` labelled "Origin", with two characters, upper-cased, and the help "The goods'
  country of origin for TARIC, two letters; CN by default". Under it, a caption: "TARIC snapshot {date}", or "TARIC not
  loaded". This displays the snapshot date for every TARIC-10 in the table (Principle I).
- "Admin ⚙", the link.

**Changing the origin**:
- With a shipment open, it calls `agent.apply_taric_origin(store, kb, value)` and shows
  `st.toast(view.origin_toast(message))`. There is no model call (FR-022).
- A refused value shows "Origin not changed: {reason}" and the field returns to the shipment's origin.
- With no shipment open, the value is kept, and the next shipment starts with it (`store.set_taric_origin` right after
  `new_shipment`).

**Empty state** (no shipment, or one with no lines):
- **Drop zone**: an `st.file_uploader` labelled "Drop a packing list or invoice here", accepting XLSX, CSV, PDF, JPG
  and PNG. Its caption reads "XLSX · CSV · PDF · JPG · PNG — up to 20 MB, one file per shipment". Caps are checked
  first, as today (`check_caps`), and a refused file shows the parser's message.
- **"Try the sample invoice"**: opens the bundled 12-line sample, with reference "HOL-2026-10-0472".
- **"Check one line"**: an `st.text_input` with the placeholder "Type a goods description and press Enter, e.g.
  bicycle frames, aluminium" and at most `MAX_DESC_CHARS` characters. Enter checks it as a one-line shipment.
- **The table**: its headers over "No lines yet — drop a file or type one description".

**Opening a file or the sample** (`upload.begin`):
- If a shipment with lines is open, the replacement question is asked first, as today: "A checked shipment is open.
  Replace it with {name}? Results, counts and cost reset." with "Replace" and "Cancel".
- Otherwise:
  - add the old shipment's usage to `session_usage`;
  - open a new shipment with the Admin threshold and hybrid setting, and the reference: the bundled reference for the
    sample, or the file name without its extension;
  - register the file and start a **check** job with that file reference (§6).
- The chat transcript is cleared, as today, because it belongs to the shipment.

## 3. Summary bar (`ui/main_page.py`)

Shown once a shipment has lines.
- **While a check job runs**: "Checking {N} lines… · {elapsed} s", over the split bar of the lines finished so far.
- **After it**:
  - `view.summary_text`, then `view.split_bar` on its own line;
  - "Accept all {K} ready" (primary), only when K > 0;
  - "Accept {n} selected", only when n Ready rows are ticked.
- Both buttons call `ui.actions.accept_ready(store, line_nos)` and rerun the page. No model call, and no job.

## 4. The decision table (`ui/table.py`)

- **Headers**: ✓ · # · Description · Code · Status · Action.
- **Rows**: the lines in file order, in pages of 25, with page buttons under the table when there is more than one
  page.
- **Live refresh**: the summary, the table and the blocks under it render in one `st.fragment`. It is called with
  `run_every=1` while a job runs or waits, so codes and statuses fill in from the store every second. When the job
  ends, the page finishes it (§6) and reruns the app.

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
- Only one row is open at a time. Grey rows do not open.
- The Admin chat reads `selected_line_no` as its selected line, as today.

## 5. Expanded rows (`ui/expand.py`)

A **Pick** column is one button per row: "◉ Picked" (primary) on the picked row, "○ Pick" (tertiary) on the others. The
pick is kept in `pick_{line_no}_{version_no}_{kind}`, pre-set as [view.md](view.md) §5 and §6 say (research R-14).

### 5.1 Kind (a): choose the HS-6 or the CN-8

- The two lines of `view.explain_a`.
- A table: Code | Description · precedent | Confidence | Pick.
  - Code is inline code.
  - Description is the escaped text. The precedent beside it is an `st.popover("BTI {member state} {reference}")`
    showing the reference, the code, the member state, the validity and the description, with "Open ruling ↗" when the
    ruling has a link; otherwise the caption "no close precedent" (Principle III).
  - Confidence is `st.progress(conf / 100, text="{conf} %")`, with the column caption "model estimate"
    (Principle III).
- "Confirm {picked code}" (primary), with the caption "then TARIC-10 runs on this code":
  - kind `a_hs6`: `store.set_decision(n, Decision(route=accepted, decided_code=…))`, then queue a **finer_codes** job
    for the line;
  - kind `a_cn8`: `store.confirm_cn8(n, cn8)`, then queue a **finer_codes** job with `taric_only=True` when
    `needs_taric` returns the CN-8;
  - in both cases, close the row and rerun. The click never waits for the model (clarification 3).
- "None of these → ask shipper" (tertiary): `store.set_decision(n, Decision(route=ask_shipper))`; the row turns red.
- A refused confirmation (`LockedError`, `UnknownCodeError`) shows "Not confirmed: {reason}" and changes nothing.

### 5.2 Kind (b): choose the TARIC-10

- The two lines of `view.explain_b`, with the CN-8's precedent popover when it has one, and the caption "TARIC
  snapshot {date} · origin {XX}".
- When the suggestion failed: the caption "Suggestion unavailable: {error}".
- A table: Code | Description | Duty | Anti-dumping | Pick, from `view.subdivision_rows(agent.line_taric_view(…))`.
  The anti-dumping cell is `:red[…]` unless it reads "none".
- "Confirm {picked code}" (primary): `store.confirm_taric10(n, code)`, which confirms the CN-8 too (feature 004). The
  row closes and turns green. No job.
- **"All measures"**: an `st.expander` for the picked subdivision:
  - its three groups as today's measure tables: Duties, Trade defence, Requirements;
  - "EZT-online ↗" (`st.link_button`);
  - `st.code("{code} {origin}")`.
- "Open in EU TARIC ↗": `st.link_button` to `eu_taric_url(code, origin, snapshot_date)` for the picked code.

### 5.3 Kind (c): ask the shipper, then update and re-check

- **"Ask the shipper"** (not for a failed check): a bordered container with:
  - the full question in `st.code(question, language=None, wrap_lines=True)`;
  - the caption ":material/content_copy: Copy question — the copy button at the top right of the box" (research R-08).
- **For a flagged vague line**: the candidates line of [view.md](view.md) §2.3.
- **The reason line**.
- **"Update the description with the shipper's answer"**: an `st.text_input`, pre-filled with the current description
  and limited to `MAX_DESC_CHARS`. Its help reads "Original: '{first version's text}' — kept in the audit trail as
  'description updated by clerk'".
- **"Re-check line"** (primary), with the caption "All steps run again for this line, from the stop-word check.":
  - split the text with `view.split_description` and call `store.update_description(n, zh, en)` (contracts/backend.md
    §1);
  - start a **recheck** job for the line, or queue it behind a running job (§6);
  - close the row.
  The row shows grey "Running stop-word check…" and then its new status. An empty field shows "Write the goods
  description first." and changes nothing.

### 5.4 Kind (a) on a green row: "Change"

A green row is never read-only. "Change", or the row's description, opens kind (a) on the decided codes, so the
clerk can override a code that was accepted automatically (spec clarification).
- **The decided codes**: the first line of `view.explain_a(…, "a_change")`, with who decided each code.
- **For a line with a TARIC-10**:
  - "TARIC snapshot {date} · origin {XX}";
  - the written subdivision's description, duty and anti-dumping cells;
  - "All measures" and "Open in EU TARIC ↗", as in kind (b).
- **The switch**: `st.segmented_control` with "HS-6" (the default) and "CN-8". It is shown only when the decided
  HS-6 has more than one CN-8 line.
- **The table of the chosen form**, as in §5.1, with the decided code pre-selected and the top candidate's rationale
  above it (Principle III).
- **"Confirm {picked code}"**: disabled while the pick is the decided code, with the help "This is the current code".
  Another code follows §5.1 exactly:
  - an HS-6: `set_decision`, then a `finer_codes` job;
  - a CN-8: `confirm_cn8`, then a TARIC-only job when needed.
  The row goes grey, then green or yellow.
- **"None of these → ask shipper"**: as in §5.1.

## 6. Background jobs (`ui/runner.py`, `ui/jobs.py`)

- **One job runs at a time** (`job`, as today). Others wait in `job_queue`, which replaces `finer_codes_queue`.
- **Job kinds**:
  - `check`: an agent turn, for an upload, the sample or typed lines;
  - `finer_codes`: `agent.after_hs6_decision`;
  - `recheck`: `agent.recheck_line`, new;
  - `question` and `reply`: from the Admin chat.
- **Queued entries**:
  - a re-check waits as `(recheck, line_no)`; its description edit is already stored;
  - a typed line waiting behind a running job is kept as text, with the caption "Waits for the running check". Its
    line is added to the store when its check starts, so no line is added while a worker reads the store.
- **Coverage**, for `view.line_status`'s `activity`:
  - a running check covers every line;
  - a running `finer_codes` or `recheck` job covers its line;
  - a queued entry makes its line `"queued"`.
- **Finishing**: `runner.finish(store, kb)` runs on the script thread when the job is done. It moves today's
  `_finish_job` here: the chat record of each check, reply and question, with its steps, sources and Assistant notes,
  for Admin › Ask the agent. Then it starts the next queued entry and reruns the app.
- **A job that ends with an error** fails what it left pending, through the store (Principle V):
  - a check job calls `store.finalize_check()`;
  - a re-check calls `store.mark_failed(line_no, "re-check failed: {error}")` if the line is still pending;
  - a `finer_codes` error leaves the line yellow (view.md §1, rows 9 and 11);
  - the page shows `st.error` once: "Line {n}: {step} did not finish: {error}", or "The check did not finish:
    {error}".
- The worker thread never calls Streamlit (as today).

## 7. Under the table (`ui/main_page.py`, `ui/shipper_email.py`)

One row of buttons:
- **"Export CSV"**: `st.download_button` with `store.to_csv_bytes()` and `store.export_filename("csv")`;
- **"Export JSON"**: `st.download_button` with `store.to_json_bytes(knowledge_base_updated=kb.updated)` and
  `store.export_filename("json")`;
- **"Draft shipper email ({C} lines)"**: toggles `email_open`; disabled when C is 0;
- **"+ Check one more line"**: toggles `more_line_open`.

The exports are disabled until a check has finished. Their bytes are unchanged from feature 004 (FR-019).

**The email block** (`email_open`), under the button row, in a bordered container (FR-020, FR-021):
- the title "Email to shipper — generated from the {C} open questions, no model call";
- `st.segmented_control` with "EN" and "中文" (key `email_lang`, default EN);
- the caption ":material/content_copy: Copy email — the copy button at the top right of the text";
- `st.code(shipper_email.draft(store, lang).text, language=None, wrap_lines=True)`.

Nothing is sent, and the draft is not stored.

**One more line** (`more_line_open`): an `st.text_input` "Type a goods description and press Enter", with at most
`MAX_DESC_CHARS` characters. Enter adds the line to the open shipment as a typed line (`CreatedBy.paste`) and starts a
check job for it, or queues it (§6).

## 8. Admin page (`ui/admin.py`)

**Header**:
- "CargoLint · Admin", with "← Back to shipment" (`st.page_link`);
- the caption "For the operator and course evaluators. The clerk's work happens on the shipment page."

**Left navigation**: `st.sidebar.radio` over Rules, Data, Cost, Quality and Ask the agent (key `admin_section`, Rules
by default).

**Rules**:
- **Threshold**: `st.slider("Auto-accept threshold", 60, 99, key="threshold", format="%d %%")`, default 85. Its change
  calls `store.set_threshold`. Caption: "Re-routes every unconfirmed line, no model call; clerk-confirmed lines are
  never touched."
- **Hybrid search**: `st.toggle("Hybrid search (BM25 and vectors)", key="hybrid")`, on by default. Its change calls
  `store.set_hybrid`.
- New shipments start with both values, as today.

**Data**:
- "EBTI rulings: {len(kb.bti):,}";
- "TARIC snapshot: {date} · Swedish Customs Tariff File Distribution", or "TARIC not loaded";
- "Model: {settings.chat_model} via OpenRouter";
- the knowledge-base statement: today's `kb_caption`, which includes "updated {kb.updated}" (Principle IV);
- a disabled "Refresh (later)" button.

**Cost**:
- **This shipment**: tokens, cost in euros, line count and check time, from `store.shipment.usage` and the summary's
  seconds;
- **This session**: total tokens and cost, which are `session_usage` plus this shipment's.

**Quality**:
- **The table**: `st.table(view.quality_rows(...))` with the columns Run | CN-8 exact | HS-6 top-3.
  - Two rows come from the last two entries of `tests/eval/cn8_eval_history.json`: "CN-8 eval, iteration {n}", with
    "{top1}/{n} ({pct} %)" and "—".
  - One row comes from `tests/eval/results.json`: "HS-6 labelled set, hybrid", with "—" and "{top3}/{clear_lines}".
  - Under the table, one caption per iteration: "Iteration {n}: {change}", cut at 160 characters.
- **No file**: the section reads "No evaluation run yet."
- **"Export audit trail"**: `st.download_button` with `view.audit_csv(store)`.
- The caption "Full history: tests/eval/cn8_eval_history.json and tests/eval/cn8_eval.md."

**Ask the agent**:
- `ui.chat.render(store, kb)`: today's transcript, chat input, Sources, Retrieval steps and Assistant notes;
- the "What I can and cannot do" expander. Its "Can" list adds "draft the email to the shipper (you copy and send it)".

## 9. Model calls and response time per action

Each action in the first group returns without waiting for a model, within 1 s on the 12-line sample (FR-029, SC-002).

| Action | Store calls | Model calls before the response | Job started or queued |
|---|---|---|---|
| Open or close a row | none | 0 | none |
| Confirm an HS-6 (a), also from Change | `set_decision` | 0 | `finer_codes` |
| Confirm a CN-8 (a), also from Change | `confirm_cn8` | 0 | `finer_codes`, TARIC only, when needed |
| None of these → ask shipper (a) | `set_decision` | 0 | none |
| Confirm a TARIC-10 (b) | `confirm_taric10` | 0 | none |
| Accept all K ready, accept selected | `confirm_taric10` or `confirm_cn8`, per line | 0 | none |
| Change the origin | `apply_taric_origin` (agent, no model) | 0 | none |
| Draft the email, switch its language | none | 0 | none |
| Export CSV or JSON | `to_csv_bytes`, `to_json_bytes` | 0 | none |
| Re-check line (c) | `update_description` | 0 | `recheck` |
| Upload, sample, check one line, one more line | `new_shipment`, `register_file` or `add_lines` | 0 | `check` |
| Admin threshold or hybrid switch | `set_threshold`, `set_hybrid` | 0 | none |

The model is called only inside jobs: a check, a re-check, the steps after a confirmation, and the Admin chat.

## 10. Rules for every element

- Untrusted text (descriptions, matched terms, the shipper name, model text) is escaped with `view.md_escape` before it
  reaches a label or Markdown. It is never used as a key, a path or an instruction (Principle II).
- Chinese and English are shown together; the UI text is English. Only the email draft is in Chinese when 中文 is
  chosen (Principle VI).
- Confidence appears only inside an expanded row, as a percentage with a bar, labelled as a model estimate (FR-002,
  Principle III).
- The main page shows no chat, threshold, tokens or cost (FR-002).
