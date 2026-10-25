# Implementation Plan: Decision-First Clerk Workflow (UI Redesign)

**Branch**: `005-decision-first-ui` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-decision-first-ui/spec.md`

## Summary

The clerk gets one main page:
- a header with the origin field and "Open another file";
- the upload, or a single typed line;
- a summary bar with batch acceptance;
- one decision table whose rows open in place into one of three kinds:
  - (a) pick the HS-6 or the CN-8, or type an HS-6 code;
  - (b) pick the TARIC-10, or ask the shipper;
  - (c) ask the shipper, then update and re-check;
- exports, and a template-built shipper email in English or Chinese.

Every expanded row of a classified line shows its top-3 HS-6 candidates, each with its own reasoning (Principle III).

A green row is never read-only: its "Change" action opens kind (a) on the decided codes. When the CN-8 has several
subdivisions, it can also open kind (b) to re-pick the TARIC-10. The clerk signs the declaration and can override an
automatically accepted code. The new code then follows the confirm flow of a review line, and a new TARIC-10 calls no
model.

Everything the clerk does not need moves to an Admin page: rules, data, cost, quality and the agent chat.

The approach:
- **The `ui/` package is rewritten** around a pure view module (`ui/view.py`). It maps each stored line to a colour,
  a status text naming the decision, an action and an expanded-row kind, in one fixed order of precedence. The pages
  only render what it returns.
- **Every clerk action is a store method call** that returns at once. Model work runs only in background jobs: a
  check, a re-check, and the CN-8 and TARIC steps after a confirmation. One runner serves both pages, and a queued
  job touches the store only when it starts.
- **The backend gains the accepted addition only**: a line version created by the clerk's edit
  (`CreatedBy.clerk`, `LineStore.update_description`), `agent.recheck_line` and the job kind `recheck`. The re-check
  covers that one line, with the existing tool functions and no agent turn.

The detail is in [research.md](research.md) R-01 to R-21, [data-model.md](data-model.md) and the
[contracts](contracts/).

## Technical Context

**Language/Version**: Python 3.11–3.13 (the project's `.venv` runs 3.13)

**Primary Dependencies**:
- Streamlit 1.65, installed, providing:
  - `st.navigation(position="hidden")`, `st.Page` and `st.page_link`;
  - `st.fragment(run_every)`, `st.toast`, `st.segmented_control`, `st.popover` and `st.code`;
  - `persist_state="session"` on widgets, and Markdown colours including yellow;
- LangChain v1 and OpenRouter through the existing client factory;
- Pydantic.

No new dependency.

**Storage**: the session-state `LineStore`, unchanged except for the addition in
[contracts/backend.md](contracts/backend.md). Nothing persists beyond the session.

**Testing**:
- pytest, offline by default;
- `streamlit.testing.v1.AppTest` for the pages, through a harness:
  - a seeded store whose flags come from the real rule engine;
  - a fake knowledge base;
  - a navigation like `app.py`'s;
  - the job starter replaced;
- `FakeRawClient` and the recorded model outputs for the re-check and the walkthrough;
- a sample TARIC fixture, tests/fixtures/taric/snapshot_sample.jsonl, built from data/taric.jsonl for the sample's
  CN-8 codes;
- the `live` marker for the live walkthrough.

**Target Platform**: a local Streamlit server (`streamlit run app.py`) in a desktop browser.

**Project Type**: single project; a Streamlit web app over the existing `agent/`, `tools/` and `rag/` packages.

**Performance Goals**:
- **Response**: each SC-002 action responds within 1 s on the 12-line sample and makes no model call. These are
  expanding a row, confirming, batch accepting, the origin change, the email draft and each export.
- **Refresh**: the table re-reads the store every second while a job runs.
- **The clerk's time**: the author's own timed run of the sample in the browser stays under 5 minutes, recorded in
  quickstart.md. The scripted walkthrough records machine time.

**Constraints**:
- Native Streamlit only (Principle VI).
- No route computed in the UI (Principle I).
- The backend is frozen apart from the accepted addition.
- Typed descriptions are capped at `MAX_DESC_CHARS` (300): "Check one line" and "+ Check one more line" cap the whole
  entry; the kind (c) field takes up to 603 characters, and the store caps each language at 300.
- No file in `ui/`, and not `app.py`, names the TARIC tool; tests/unit/test_taric_store.py checks this.
- `app.py` keeps its CRLF line endings. Every other file edited here, and every new file, uses LF.

**Scale/Scope**:
- one shipment per session, up to `MAX_LINES` (200) lines, in pages of 25 rows;
- two pages; eight new UI modules and four changed ones (`app.py`, `upload.py`, `chat.py`, `jobs.py`); in the
  backend, one enum value and two functions;
- 27 UI-coupled tests: 13 replaced, 14 kept.

No item is left as NEEDS CLARIFICATION.
- **Two spec gaps found in planning** were accepted by the author on 2026-10-23 and are now in the spec:
  - R-10: failed and running lines are counted apart in the summary (FR-005);
  - R-16: candidates are "too close to call" within 10 points (FR-016).
- **The analysis of 2026-10-24** led to the author's decisions in the spec's Clarifications (Session 2026-10-24):
  - the typed HS-6 code;
  - kind (b)'s "ask the shipper";
  - "Open another file";
  - the 14 kept tests;
  - the named re-check pieces;
  - how SC-001 is measured.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution v1.3.0.

| Principle | Gate | Before research | After design |
|---|---|---|---|
| I. Guardrails in code | The UI computes no route: colours, texts and kinds come from the stored route, flag, CN-8 and TARIC states in a fixed precedence (view.md §1). The threshold keeps 85 % and 60–99, set on Admin › Rules through `store.set_threshold`. A re-checked line that was ever flagged needs the clerk's click (backend.md §1 test). Codes are written only by the store's confirmations or rules. Batch acceptance uses `confirm_taric10` and `confirm_cn8`, and a typed HS-6 code is checked by the store against the loaded nomenclature. The TARIC snapshot date shows in the header and in kind (b). The email is never sent. The clerk can override an automatically accepted code with "Change", and the new code follows the review flow (R-18). | PASS | PASS |
| II. Untrusted input | Typed lines and edits reach the model only through the existing fenced check and classify prompts, which `recheck_line` reuses. They are capped by `MAX_DESC_CHARS` per language, in the fields and in `update_description`. They are escaped before any Markdown, as is the uploaded file name (R-17). An adversarial re-check test is planned. No key is read or shown by the UI. | PASS | PASS |
| III. Grounded, cited | Every expanded row of a line with candidates shows its top-3 HS-6 candidates (R-20). Each has its confidence, its own reasoning and its BTI precedent (reference, description and validity, or "no close precedent"). They form the pick table, or an "HS-6 candidates" block. Confidence is labelled a model estimate. Sources and retrieval steps stay on Admin › Ask the agent, where v1.3.0 places them, with a record for each re-check. Flagged lines ask for the material, the exact product name and the use. A re-check queued behind a running check stores its edit only when it starts, so no version skips the description check (R-15). "Too close to call" is said only when the confidences show it (R-16). | PASS | PASS |
| IV. Hybrid retrieval | Retrieval is unchanged. The hybrid switch is on Admin › Rules. Admin › Data states the knowledge base's coverage and last update (`view.kb_statement`). | PASS | PASS |
| V. Single-purpose tools | No tool is added or changed; the seven stay. `recheck_line` is an agent function, like `after_hs6_decision`: it runs the existing tool functions for one line, and a failure fails that line only. Versions and the audit trail stay append-only. The clerk's edit is one audit record, and every click goes through a store method that records it. A finished re-check adds a chat record with its sources and steps. | PASS | PASS |
| VI. Native UI that shows its work | Only native components are used, with no custom HTML, CSS or JavaScript, so nothing needs justifying. The main page has no sidebar, and shows per-line progress, the summary counts, the evidence in expanded rows and the exports. The Admin page holds the sources and steps, cost and the knowledge-base statement. Every locked Accept is shown disabled with its reason: red rows, including unreadable lines. Green rows add the action "Change"; the UI Design Contract lists a minimum inventory, so an added action needs no amendment. The summary's colour counts are the contract's own summary sentence. A later PATCH amendment can align the wording of Principle VI ("routing counts") and of the contract ("Choose" or "Update"). The table is read from the store. Chinese and English are shown together; the email may be Chinese. "What I can and cannot do" is updated and shown at all times. | PASS | PASS |
| VII. Test-first | Tests come first for `update_description` (caps, lock, audit) and `recheck_line` (single-line scope, failures, injection). They also come first for the queued re-check (no version before its job starts) and for the status mapping (SC-004), including the unreadable lock, before the pages. All new tests run offline with fakes; the live walkthrough is marked `live`. | PASS | PASS |

**Follow-ups for the author** are not violations, so they need no Complexity Tracking. A PATCH amendment can update
the constitution's wording after this feature:
- the UI Design Contract's Action column: "Choose" or "Update", plus "Change";
- Principle VI's "routing counts": the summary's decision counts;
- the sample's "6 needing action": the count under the new mapping, which depends on the TARIC snapshot.

**Scope (out of scope for the MVP)**: PASS before and after design.
- no version-history UI: kind (c) shows only the text being replaced, as a hint, as FR-016 requires;
- no ATLAS flow, nothing sent, no persistence.

**Architecture invariants**: PASS.
- The UI calls `agent/` functions: `run_turn`, `after_hs6_decision`, `recheck_line`, `apply_taric_origin` and
  `line_taric_view`.
- Like today's UI, it also uses pure helpers from `tools/`: `check_caps`, `load_into_store` and `split_mixed`.
- No file in `ui/`, and not `app.py`, names the TARIC tool. The UI never calls the model or the retrieval itself.
- Line data goes only through `agent/store.py`.

## Project Structure

### Documentation (this feature)

```text
specs/005-decision-first-ui/
├── spec.md              # the feature specification
├── plan.md              # this file
├── research.md          # Phase 0: R-01 to R-21
├── data-model.md        # Phase 1: derived view records, the backend addition, page state
├── quickstart.md        # Phase 1: how to validate the feature, and the author's timed run
├── contracts/
│   ├── ui.md            # the two pages: elements, actions, jobs, model calls per action
│   ├── view.md          # the status mapping, exact texts, codes, counts, rows and email templates
│   └── backend.md       # CreatedBy.clerk, update_description, recheck_line, the recheck job
├── checklists/
│   └── requirements.md  # spec quality checklist (16/16)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
app.py                       # changed (CRLF): st.navigation(position="hidden") over the two pages; the
                             #   missing-key message no longer names a .env file
agent/
├── schemas.py               # changed: CreatedBy.clerk
├── store.py                 # changed: update_description; add_version maps a clerk version
└── agent.py                 # changed: recheck_line
ui/
├── main_page.py             # new: header, empty state, summary bar, buttons under the table, email block
├── table.py                 # new: rows, paging, opening a row, the live fragment
├── expand.py                # new: kinds (a), (b), (c) and the HS-6 candidates block; kinds (a) and (b) also open
│                            #   from "Change" on a green row
├── view.py                  # new, pure: status mapping, codes, texts, counts, rows, captions, toast, escaping,
│                            #   audit CSV
├── shipper_email.py         # new, pure: the English and Chinese templates
├── actions.py               # new, pure: batch and selected acceptance
├── runner.py                # new: starting, queueing and finishing jobs for both pages
├── admin.py                 # new: Rules, Data, Cost, Quality, Ask the agent
├── upload.py                # changed: drop zone, sample, replacement, "Open another file"; begin starts the check
├── chat.py                  # changed: the Admin chat; job finishing moves to runner.py
├── jobs.py                  # changed: job kind recheck
├── replies.py               # unchanged
├── review.py                # removed
├── detail.py                # removed
└── sidebar.py               # removed
tests/
├── unit/
│   ├── test_view.py         # new
│   ├── test_shipper_email.py  # new
│   ├── test_actions.py      # new
│   ├── test_runner.py       # new
│   ├── test_store.py        # changed: TestClerkEdit
│   ├── test_review_table.py   # removed (replaced)
│   └── test_sidebar_caption.py  # removed (replaced; taric_caption becomes view.taric_statement)
├── integration/
│   └── test_recheck.py      # new
├── fixtures/
│   ├── make_taric_sample.py # new: writes the sample TARIC fixture from data/taric.jsonl
│   └── taric/
│       └── snapshot_sample.jsonl  # new: the sample's CN-8 codes, with their subdivisions and measures
├── ui/                      # new: harness.py, test_main_page.py, test_admin_page.py,
│                            #      test_app_navigation.py, test_response_time.py
└── eval/
    └── walkthrough.py       # new: the scripted walkthrough, writes walkthrough.json
README.md                    # changed: the new pages, the walkthrough result, the timed run
CLAUDE.md                    # changed: the CRLF list names only the files that still use CRLF
```

**Structure Decision**: the single-project layout stays.
- **The UI is split by page and by role**: one module per page section, plus two pure modules (`view.py`,
  `shipper_email.py`) and `actions.py`. These hold every rule the pages show or apply, so they are tested without
  Streamlit.
- **Code that moves**:
  - from `ui/detail.py`: the measure tables go to `ui/expand.py`, taken from git history once the file is deleted;
  - from `ui/sidebar.py`: `kb_caption` becomes `view.kb_statement`, and `taric_caption` becomes
    `view.taric_statement`, which keeps its CN-8 mismatch count;
  - from `ui/chat.py`: `queue_finer_codes` and `_finish_job` move to `ui/runner.py`.
- **`ui/chat.py` keeps** `classify_message`, `_start`, `handle_message` and the transcript rendering. Five of the 14
  kept tests import or read them.
  - It drops the quick actions that check a description or open the sample, and the pending-file start; the main
    page now owns these.
  - The terms quick action stays, and "What I can and cannot do" is shown at all times.

## Complexity Tracking

None. The Constitution Check has no violation to justify.
