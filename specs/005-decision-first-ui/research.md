# Research: Decision-First Clerk Workflow (UI Redesign)

Phase 0 of `/speckit-plan` for feature 005. Each item records a decision, why it was taken, and what else was
considered. The Technical Context of [plan.md](plan.md) has no open NEEDS CLARIFICATION items. Streamlit facts were
checked against the installed version 1.65 and its bundled reference docs on 2026-10-23.

## R-01 Two pages, and no sidebar on the main page

**Decision**:
- `app.py` builds `st.navigation([main, admin], position="hidden")` from two `st.Page`s. The pages link to each
  other with `st.page_link`: "Admin ⚙" in the main page's header, and "← Back to shipment" on the Admin page.
- The main page puts nothing in `st.sidebar`, so no sidebar shows there.
- The Admin page's left navigation is an `st.sidebar` radio of its five sections. The sidebar therefore exists on
  that page only.

**Rationale**: the hidden navigation leaves no page list in a sidebar. The Admin sidebar is the native way to draw the
wireframe's left navigation, and it leaves the full width to the agent chat.

**Alternatives considered**:
- `position="sidebar"`: puts a sidebar on the main page, which FR-001 forbids.
- A `st.columns([1, 4])` navigation column on the Admin page: squeezes the chat.
- `st.tabs`: horizontal, unlike the wireframe.

## R-02 The decision table: a row list with rows that open in place

**Decision**:
- **Rows**: each line is a row of `st.columns` (✓ · # · Description · Code · Status · Action), as today's review
  list is. It is not an `st.dataframe`. The ✓ column is the Accept control: a checkbox, enabled on Ready rows and
  disabled with the lock reason on red rows (FR-006, FR-011).
- **Opening a row**: `st.session_state["selected_line_no"]` names the open row (the Admin chat reads it as its
  selected line, as today), and its content renders in a bordered
  container right under it, one row at a time, with "▲ close".
- **Order and paging**: rows come in file order, in pages of 25, as today's review list pages them. The 12-line sample
  fits one page.
- **Live refresh**: the summary, the table and the blocks under it sit in one `st.fragment`, called with
  `run_every=1` while a job runs or waits, so it re-reads the store every second (today's pattern). A clerk action
  reruns that fragment; starting or finishing a job reruns the app.

**Rationale**: a row must carry widgets (Choose, Update, a disabled Accept, a selection box) and open under itself;
`st.dataframe` cannot do either.

**Alternatives considered**:
- An `st.expander` per row: its label cannot hold the column layout, and every row's body would render on each rerun.
- A fixed-height scrolling list: an opened row inside it scrolls out of view.

## R-03 Status, code and texts come from one pure view module

**Decision**: a new module `ui/view.py` with no Streamlit import holds every derived display value, and
`ui/shipper_email.py` holds the email templates. They read the line only through the store's existing methods:
- `effective_route`, `decided_code`, `decided_cn8`, `decided_taric10`;
- `cn8_pending`, `taric_pending`, `ready_to_accept`;
- `line.current` with its flag, status, CN-8 choice, TARIC outcome and decision.

They return small frozen dataclasses (`LineStatus`, `CodeDisplay`, `EmailDraft`, …; data-model §1). The mapping
follows the spec's Line status table, in a fixed order of precedence (contracts/view.md §1). No module computes a route;
routes come from `agent/routing.py` through the store (Principle I). The lock reasons of FR-011 are built from the
line's flag, CN-8 question, decision or failure. The store's `accept_lock_reason` covers only flagged and unchecked
lines, and its wording is feature 001's.

**Rationale**:
- One place to test every row of the mapping offline (SC-004), with no running page.
- The UI modules render what `view.py` returns and never re-derive it.

**Alternatives considered**: putting the mapping in `agent/`. It is presentation, not a guardrail, and it would widen
the backend change the author accepted.

## R-04 Short texts without a model

**Decision**: fixed templates fill the "Ask: …", "Pick: …", "Confirm: …" and "Locked: …" texts from stored fields
(contracts/view.md §2):
- **An open CN-8 question**: its attribute, minus a leading "whether ", plus "?". So "whether the toy cars
  incorporate a motor" becomes "Ask: the toy cars incorporate a motor?". The full question is in the expanded row.
- **A flagged line**:
  - with a matched term: "Ask: what exactly is “<term>”?";
  - with a vagueness judgement: "Ask: " plus its missing facts, "material, product, use?".
- **A line the clerk sent to the shipper**: "Ask: what exactly are the goods?".
- **Picks**:
  - "Pick: N candidates" for an HS-6 choice;
  - "Pick: CN-8, N lines" for a CN-8 choice;
  - "Pick: 10 or 90" for two subdivisions;
  - "Pick: N options, K AD" for more, where K counts the subdivisions under trade defence. Without any, it reads
    "Pick: N options";
  - one subdivision under trade defence: "Confirm: <code>".
- **Length**: every short text is cut at 44 characters with "…". contracts/view.md §2 lists every text.

**Rationale**: FR-012 rules out a model call, and the wireframe's examples are illustrations.

**Alternatives considered**: a model-written short question. It costs a call per line and breaks NFR-1.

## R-05 The kind (b) columns, from `line_taric_view`

**Decision**: the subdivision table reads the agent's `line_taric_view` (feature 004), never `kb.taric`:
- **Duty**: the duty text of the subdivision's type-103 measure. When a preference measure applies to the origin
  (types 142, 143, 145 or 146), it adds " · pref. <its duty>" for the first one.
- **Anti-dumping**: drawn from the trade-defence group's anti-dumping and countervailing measures (types 551–555).
  The percentages are read from their duty texts with one regular expression:
  - one distinct rate: "19.2 % AD";
  - several: the lowest–highest range, "22.1–86.5 % AD";
  - measures with no percentage, such as the specific duty "172.2 EUR / 1000 kg I" in the snapshot: "AD: " and the
    first duty text, cut short. A percentage-only reading would show "none" for them, which would be wrong;
  - only a type-570 control: "control";
  - none: "none".
- **Description**: the subdivision's TARIC text; a code ending in 00 reads "the whole CN-8" (feature 004).
- **Pre-selection**: the stored suggestion, if any.

**Rationale**: FR-015 asks for one duty and one anti-dumping cell per subdivision. "All measures" keeps the full rows,
so nothing is lost, and the parity of feature 004 stands.

**Alternatives considered**: showing producer names, as the mockup does. The snapshot has none; they were out of
scope in feature 004.

## R-06 Batch acceptance confirms each green line's codes

**Decision**: `ui/actions.py` (no Streamlit import) provides `accept_ready(store, line_nos=None) -> int`. For each line
that is green and not yet Accepted:
- a written TARIC-10 is confirmed with `store.confirm_taric10(n, code)`, which also confirms its CN-8 (feature 004);
- a line that stops at 8 digits is confirmed with `store.confirm_cn8(n, cn8)`.

The function returns how many lines it confirmed. A line counts as "Accepted" when the clerk's decision accepts its
HS-6, its CN-8 was written by the clerk, and its TARIC-10 was written by the clerk or is not available.

**Rationale**: it uses only feature 004's confirmations, so the export reads "accepted" by the clerk with
`decided_how` "auto", and threshold changes no longer touch those codes.

**Alternatives considered**: a new store method for batch acceptance. It adds backend surface for a loop.

## R-07 The clerk's description edit and the line re-check (the accepted backend addition)

**Decision**:
- `CreatedBy` gains `clerk`.
- `LineStore.update_description(line_no, text_zh, text_en) -> LineVersion` adds a version created by the clerk. Its
  audit record has the change `version_added`, the actor `clerk`, the original text as `previous`, the new text as
  `new`, and the note "description updated by clerk". `add_version` maps a clerk version to the actor `clerk`.
- `agent.recheck_line(store, kb, line_no) -> str` runs, for that line only, what `_finalize` runs for pending
  lines: the description check, the HS-6 classification, the precedent lookup, then the CN-8 and TARIC steps when
  the HS-6 is decided. It goes through the usage-recording client, so the shipment's cost includes it.
- The UI starts it as a background job of kind `recheck`.
- A clerk version is not locked by itself: `_recompute` keeps its rule "ever flagged, or a shipper reply". A line
  that was ever flagged still needs the clerk's click (Principle I). A line never flagged may turn green, as the
  wireframe shows (spec Assumptions).

**Rationale**:
- It is the smallest addition that records the edit as the clerk's.
- It re-checks one line without an agent turn, and no model chooses which tools run.
- It reuses the same tool functions, so behaviour equals the check's.

**Alternatives considered**:
- Running the edit as a shipper reply through `apply_shipper_reply`: it labels the clerk's text as the shipper's and
  locks every such line.
- An agent turn: it costs a model call to pick the tools.

## R-08 Copying the question and the email

**Decision**: the question and the email are shown in `st.code` blocks (`language=None`, lines wrapped). Their native
copy button copies the text. The labels "Copy question" and "Copy email" sit beside the blocks and name that button.

**Rationale**: Streamlit 1.65 has no copy button widget, and Principle VI rules out custom JavaScript.

**Alternatives considered**: a component that writes to the clipboard. It needs custom code.

## R-09 The dots and the split bar, natively

**Decision**:
- **Dots**: coloured Markdown text: `:green[●]`, `:yellow[●]`, `:red[●]`, and `:gray[◌]` for a line still running.
  Streamlit 1.65 lists yellow among its Markdown colours.
- **Split bar**: one Markdown line of 60 block characters ("█"), split between `:green[…]`, `:yellow[…]`, `:red[…]` and
  `:gray[…]` in proportion to the counts. Rounding keeps every non-empty count at least one block wide.
- **Codes**: shown as inline code in the monospace font.

**Rationale**: these are native Markdown features in labels and text (bundled reference, markdown.md). No CSS is
needed.

**Alternatives considered**:
- A stacked horizontal `st.bar_chart`: heavy for one bar, with axes to hide.
- `st.progress`: one colour only.

## R-10 Summary counts and in-progress lines

**Decision**:
- **The three counts**: green lines (A), yellow (B), and red lines with a question (C). The "Draft shipper email"
  count is the same C.
- **Failed lines**: a red "Check failed" line has no question, so it is counted apart. " · F check failed" is added
  only when F > 0.
- **Running lines**: a line still running is counted apart too, with " · R updating" only when R > 0.
- **During a check**: until the check ends, the summary reads "Checking N lines… · T s".
- **The time T**: the summed time of the shipment's check runs that ran the description check. "+ Check one more line"
  adds its time; a re-check and the steps after a confirmation add none.

**Rationale**: FR-005 names three counts. A failed check needs a re-check, not the shipper, and the email lists only
lines with a question.

**Accepted by the author** on 2026-10-23. FR-005 now states the two counts.

## R-11 The email templates

**Decision**: `ui/view.py` builds the draft from fixed templates, in English and Chinese (contracts/view.md §4):
- **Invoice id**: the shipment's reference, which the page sets to the bundled reference for the sample and to the
  file name without its extension for an upload. A typed line has none, so the shipment id stands in, as
  `export_filename` already does.
- **Greeting**: the detected shipper name, unless it is the placeholder "New shipper", in which case the greeting is
  generic.
- **Each question**: built from the line's state:
  - a CN-8 question: the stored attribute, model-written, kept in English in both versions;
  - a flagged line, or one the clerk sent: the standard ask for material, exact product name and use, from the
    template, in Chinese in the Chinese version.
- **Chinese version**: every template part is Chinese, including the sign-off placeholders ("[经办人姓名] —
  [货代公司名称]，汉堡").

**Rationale**: FR-020 and FR-021, and the author's rule that only model-written questions may stay English.

## R-12 The Admin page's sources

**Decision**:
- **Rules**: the threshold slider (60–99, default 85) calls `store.set_threshold`, and the hybrid switch calls
  `store.set_hybrid` (today's callbacks).
- **Data**:
  - the ruling count is `len(kb.bti)`;
  - the TARIC snapshot date comes from `kb.taric.snapshot`, with the source "Swedish Customs Tariff File
    Distribution", or "TARIC not loaded";
  - the model is `settings.chat_model`, "via OpenRouter";
  - the knowledge-base date is `kb.updated`;
  - "Refresh (later)" is a disabled button.

  Reading the snapshot's date is metadata, as today's sidebar caption already does; measures are still read only
  through `line_taric_view`.
- **Cost**:
  - this shipment: cost, line count and the last check's time, from `store.shipment.usage` and `check_runs`;
  - the session: a session-state total, which adds a shipment's usage when it is replaced.
- **Quality**: read from `tests/eval/cn8_eval_history.json` and `tests/eval/results.json` when present.
  - Two rows come from the last two history entries: today, iteration 3 and its validation run (iteration 4). A caption
    gives each one's change text. One more row comes from the hybrid run of the labelled set: the HS-6 top-3.
  - A run measures one of the two columns; the other reads "—".
  - When the files are missing, the section reads "no evaluation run yet".
  - "Export audit trail" downloads a CSV built by `view.audit_csv(store)` from `store.shipment.audit`.
- **Ask the agent**: today's chat (`ui/chat.py`) with its Sources, Retrieval steps and Assistant notes, under an
  expander "What I can and cannot do". Its text gains "draft the email to the shipper (you send it)".

## R-13 Tests

**Decision**:
- **Pure tests** (unit, offline):
  - `tests/unit/test_view.py` covers every row of the Line status table, the codes, the short texts, the lock reasons,
    the counts and the kind (a) and (b) rows;
  - `tests/unit/test_shipper_email.py` covers both emails;
  - `tests/unit/test_actions.py` covers acceptance.
- **Store tests**: `tests/unit/test_store.py` gains the clerk edit and its audit record.
- **Re-check tests**: `tests/integration/test_recheck.py` runs `recheck_line` with `FakeRawClient`.
- **Page tests** (`tests/ui/`): `streamlit.testing.v1.AppTest`, offline. A harness builds stores in each state through
  the store's own methods, with a fake knowledge base. It renders `ui.main_page.render` and `ui.admin.render`, and
  replaces the job starter so no thread or model runs. One test runs `app.py` with the knowledge-base loader patched,
  for the navigation.
- **Walkthrough**: `tests/eval/walkthrough.py` drives the sample as a clerk would and writes each action's response
  time, the action count and the total to `tests/eval/walkthrough.json` (SC-001, SC-002).
- **Model calls**: a test client counts them; the actions in SC-002 must make none.
- **Today's UI tests**: the 13 tests of `ui/review.py` and `ui/sidebar.py` are replaced. The 14 that test kept
  functions stay unchanged: the reply hook, message classification and the upload helpers. One of them reads
  `ui/chat.py`'s source for the history line, so `_start` and `handle_message` keep it.

**Rationale**: Principle VII and SC-002 to SC-007.

## R-14 The Pick column

**Decision**:
- In kinds (a) and (b), each row's Pick cell is a button: "◉ Picked" (primary) on the picked row, "○ Pick" (tertiary)
  on the others.
- The pick is kept per line, version and kind in session state, pre-set to the leader or the suggestion.
- "Confirm {code}" reads it.

**Rationale**: it draws the wireframe's radio column inside a row layout, and `AppTest` can click it.

**Alternatives considered**:
- One `st.radio` beside the table: its options cannot line up with the table's rows.
- `st.dataframe` row selection: `AppTest` cannot drive it.
- A checkbox per row: checkboxes do not exclude each other.

## R-15 One job runner for both pages

**Decision**:
- **`ui/runner.py`** (new, script thread) starts, queues and finishes jobs for both pages.
  - It takes over `queue_finer_codes` and `_finish_job` from `ui/chat.py`. The finished check still adds its chat
    record, so Admin › Ask the agent shows its sources, steps and notes.
  - `ui/jobs.py` stays free of Streamlit and gains the kind `recheck`.
- **The queue**: `job_queue` holds `finer_codes` and `recheck` entries, and typed lines that wait for a running check.
  A waiting line is added to the store only when its check starts, so no line is added while a worker reads the store.
- **A job that ends with an error** fails what it left pending, through the store:
  - a check: `store.finalize_check()`;
  - a re-check: `store.mark_failed`.

  So no line stays grey. A failed `finer_codes` job leaves its line yellow, and confirming the CN-8 again runs the
  missing step.

**Rationale**:
- The main page now starts the checks, and the chat lives on the Admin page; both need the same job slot.
- Today the worker's state is read only by the script thread; the queue keeps it that way.

**Alternatives considered**:
- Keeping the runner in `ui/chat.py`: the main page would depend on the chat module.
- Disabling every action while a job runs: the spec lets a new line wait instead.

## R-16 Close candidates and the Reason line

**Decision**:
- For a flagged vague line, kind (c) lists its candidates with their confidences.
- When the top two confidences differ by at most 10 points (`CLOSE_POINTS`):
  - the candidates line ends with "— too close to call";
  - the reason reads "Reason: candidates too close".
- Otherwise the reason reads "Reason: vague description — {the flag's reason}".
- This is a display rule only; routing never reads it.

**Rationale**: FR-016 and User Story 3 show "too close to call" for close candidates, but the backend has no closeness
rule (spec Assumptions). Saying "too close" for 40 % against 10 % would be untrue.

**Accepted by the author** on 2026-10-23. FR-016 now defines "close" as within 10 points.

## R-17 Untrusted text in labels and Markdown

**Decision**: descriptions, matched terms, the shipper name and model text are escaped with `view.md_escape` before
they reach a button label, a caption or Markdown.

**Rationale**:
- Streamlit renders Markdown in labels. A description such as "[click](https://…)" would otherwise become a link
  (Principle II).
- The email block and the question box use `st.code`, which shows text as it is, so they need no escaping.

**Alternatives considered**: `st.text` for every description. It cannot be a button label.

## R-18 "Change" on a green row (author's decision, 2026-10-23)

**Decision**:
- **The action**: every green row, Ready or Accepted, has the action "Change". It opens kind (a) on the decided codes:
  - the codes and who decided each one;
  - the written TARIC-10's duty, anti-dumping duty and measures;
  - the HS-6 candidates, with a switch to the CN-8 lines under the decided HS-6 when there is more than one.
- **The pick**: the decided code is pre-selected, and "Confirm" stays disabled until the clerk picks another. Accepting
  the current code is what the Accept control does.
- **The flow**: a code the clerk confirms follows kind (a)'s flow for a review or CN-8 line. A new HS-6 runs the CN-8
  and TARIC steps again; a new CN-8 runs the TARIC step again.
- **The TARIC-10**: when the stored TARIC outcome has more than one subdivision, the switch also offers "TARIC-10".
  It opens kind (b) with the written TARIC-10 pre-selected. Confirming another subdivision calls `confirm_taric10`,
  with no model call and no job, and the row stays green. The author added this on 2026-10-23.

**Rationale**: the clerk signs the declaration and must be able to override a code accepted automatically. Reusing
kind (a) and the store's confirmations adds no backend surface.

**Alternatives considered**:
- A read-only green summary, the first plan: it left no way to override an auto-accepted code.
- Re-confirming the same code: on a Ready row it would record the HS-6 alone as the clerk's, and the row would
  still read Ready, because `needs_cn8` keeps the CN-8 chosen under the same HS-6. On an Accepted row it would
  change nothing. Accept already confirms the current codes.
