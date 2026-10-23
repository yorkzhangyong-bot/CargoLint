# Implementation Plan: Decision-First Clerk Workflow (UI Redesign)

**Branch**: `005-decision-first-ui` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-decision-first-ui/spec.md`

## Summary

The clerk gets one main page:
- a header with the origin field;
- the upload, or a single typed line;
- a summary bar with batch acceptance;
- one decision table whose rows open in place into one of three kinds: (a) pick the HS-6 or CN-8, (b) pick the
  TARIC-10, (c) ask the shipper, then update and re-check;
- exports, and a template-built shipper email in English or Chinese.

A green row is never read-only: its "Change" action opens kind (a) on the decided codes. The clerk signs the
declaration and can override an automatically accepted code, which then follows the confirm flow of a review line.

Everything the clerk does not need moves to an Admin page: rules, data, cost, quality and the agent chat.

The approach:
- **The `ui/` package is rewritten** around a pure view module (`ui/view.py`). It maps each stored line to a colour,
  a status text naming the decision, an action and an expanded-row kind, in one fixed order of precedence. The pages
  only render what it returns.
- **Every clerk action is a store method call** that returns at once. Model work runs only in background jobs: a
  check, a re-check, and the CN-8 and TARIC steps after a confirmation. One runner serves both pages.
- **The backend gains the accepted addition only**: a line version created by the clerk's edit
  (`CreatedBy.clerk`, `LineStore.update_description`), and `agent.recheck_line`. The latter re-checks that one line
  with the existing tool functions and no agent turn.

The detail is in [research.md](research.md) R-01 to R-18, [data-model.md](data-model.md) and the
[contracts](contracts/).

## Technical Context

**Language/Version**: Python 3.11–3.13 (the project's `.venv` runs 3.13)

**Primary Dependencies**:
- Streamlit 1.65, installed: `st.navigation(position="hidden")`, `st.Page`, `st.page_link`, `st.fragment(run_every)`,
  `st.toast`, `st.segmented_control`, `st.popover`, `st.code`, and Markdown colours including yellow;
- LangChain v1 and OpenRouter through the existing client factory;
- Pydantic.

No new dependency.

**Storage**: the session-state `LineStore`, unchanged except for the addition in
[contracts/backend.md](contracts/backend.md). Nothing persists beyond the session.

**Testing**:
- pytest, offline by default;
- `streamlit.testing.v1.AppTest` for the pages, with a seeded store, a fake knowledge base and the job starter
  replaced;
- `FakeRawClient` and the recorded model outputs for the re-check and the walkthrough;
- the `live` marker for the live walkthrough.

**Target Platform**: a local Streamlit server (`streamlit run app.py`) in a desktop browser.

**Project Type**: single project; a Streamlit web app over the existing `agent/`, `tools/` and `rag/` packages.

**Performance Goals**:
- Each SC-002 action responds within 1 s on the 12-line sample and makes no model call: expanding a row, confirming,
  batch accepting, the origin change, the email draft and each export.
- The table refreshes from the store every second while a job runs.
- The scripted walkthrough of the sample stays under 5 minutes.

**Constraints**:
- Native Streamlit only (Principle VI).
- No route computed in the UI (Principle I).
- The backend is frozen apart from the accepted addition.
- Typed descriptions are capped at `MAX_DESC_CHARS` (300).
- `app.py`, `ui/chat.py` and `ui/upload.py` keep their CRLF line endings; the new files use LF.

**Scale/Scope**:
- one shipment per session, up to `MAX_LINES` (200) lines, in pages of 25 rows;
- two pages; eight new UI modules and four changed ones (`app.py`, `upload.py`, `chat.py`, `jobs.py`); in the
  backend, one enum value and two functions;
- 27 UI-coupled tests: 13 replaced, 14 kept.

No item is left as NEEDS CLARIFICATION. Two spec gaps found in planning were accepted by the author on 2026-10-23
and are now in the spec:
- R-10: failed and running lines are counted apart in the summary (FR-005);
- R-16: candidates are "too close to call" within 10 points (FR-016).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution v1.3.0.

| Principle | Gate | Before research | After design |
|---|---|---|---|
| I. Guardrails in code | The UI computes no route: colours, texts and kinds come from the stored route, flag, CN-8 and TARIC states in a fixed precedence (view.md §1). The threshold keeps 85 % and 60–99, set on Admin › Rules through `store.set_threshold`. A re-checked line that was ever flagged needs the clerk's click (backend.md §1 test). Codes are written only by the store's confirmations or rules; batch acceptance uses `confirm_taric10` and `confirm_cn8`. The TARIC snapshot date shows in the header and in kind (b). The email is never sent. The clerk can override an automatically accepted code with "Change", and the new code follows the review flow (R-18). | PASS | PASS |
| II. Untrusted input | Typed lines and edits reach the model only through the existing fenced check and classify prompts, which `recheck_line` reuses. They are capped by `MAX_DESC_CHARS` in the field and in `update_description`, and escaped before any Markdown (R-17). An adversarial re-check test is planned. No key is read or shown by the UI. | PASS | PASS |
| III. Grounded, cited | Kind (a), kind (c) of a vague line and the green summary show the top-3 candidates with confidence, rationale and the BTI precedent: reference, description and validity, or "no close precedent". Confidence is labelled a model estimate. Sources and retrieval steps stay on Admin › Ask the agent, where v1.3.0 places them. Flagged lines ask for the material, the exact product name and the use. "Too close to call" is said only when the confidences show it (R-16). | PASS | PASS |
| IV. Hybrid retrieval | Retrieval is unchanged. The hybrid switch is on Admin › Rules. Admin › Data states the knowledge base's coverage and last update (`kb_caption`). | PASS | PASS |
| V. Single-purpose tools | No tool is added or changed; the seven stay. `recheck_line` is an agent function, like `after_hs6_decision`: it runs the existing tool functions for one line, and a failure fails that line only. Versions and the audit trail stay append-only. The clerk's edit is one audit record, and every click goes through a store method that records it. | PASS | PASS |
| VI. Native UI that shows its work | Only native components are used; no custom HTML, CSS or JavaScript, so nothing needs justifying. The main page has no sidebar, and shows per-line progress, the routing counts, the evidence in expanded rows and the exports. The Admin page holds the sources and steps, cost and the knowledge-base statement. Red rows show the Accept control disabled with the lock reason. Green rows add the action "Change"; the UI Design Contract lists a minimum inventory, so an added action needs no amendment. The table is read from the store. Chinese and English are shown together; the email may be Chinese. "What I can and cannot do" is updated. | PASS | PASS |
| VII. Test-first | Tests come first for `update_description` (caps, lock, audit) and `recheck_line` (single-line scope, failures, injection), and for the status mapping (SC-004) before the pages. All new tests run offline with fakes; the live walkthrough is marked `live`. | PASS | PASS |

**Scope (out of scope for the MVP)**:
- no version-history UI: kind (c) shows only the original text as a hint, as FR-016 requires;
- no ATLAS flow, nothing sent, no persistence.

PASS before and after design.

**Architecture invariants**:
- The UI calls `agent/` functions: `run_turn`, `after_hs6_decision`, `recheck_line`, `apply_taric_origin` and
  `line_taric_view`.
- Like today's UI, it also uses pure helpers from `tools/`: `check_caps`, `load_into_store`, `split_mixed` and
  `needs_taric`. It never calls the model or the retrieval itself.
- Line data goes only through `agent/store.py`.

PASS.

## Project Structure

### Documentation (this feature)

```text
specs/005-decision-first-ui/
├── spec.md              # the feature specification (committed)
├── plan.md              # this file
├── research.md          # Phase 0: R-01 to R-18
├── data-model.md        # Phase 1: derived view records, the backend addition, page state
├── quickstart.md        # Phase 1: how to validate the feature
├── contracts/
│   ├── ui.md            # the two pages: elements, actions, jobs, model calls per action
│   ├── view.md          # the status mapping, exact texts, codes, counts, rows and email templates
│   └── backend.md       # CreatedBy.clerk, update_description, recheck_line, the recheck job
├── checklists/
│   └── requirements.md  # spec quality checklist (16/16)
└── tasks.md             # Phase 2 output (/speckit-tasks; not created here)
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
├── expand.py                # new: kinds (a), (b), (c); kind (a) also opens from "Change" on a green row
├── view.py                  # new, pure: status mapping, codes, texts, counts, rows, toast, escaping, audit CSV
├── shipper_email.py         # new, pure: the English and Chinese templates
├── actions.py               # new, pure: batch and selected acceptance
├── runner.py                # new: starting, queueing and finishing jobs for both pages
├── admin.py                 # new: Rules, Data, Cost, Quality, Ask the agent
├── upload.py                # changed (CRLF): drop zone, sample, replacement; begin starts the check
├── chat.py                  # changed (CRLF): the Admin chat; job finishing moves to runner.py
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
│   ├── test_store.py        # changed: TestClerkEdit
│   ├── test_review_table.py   # removed (replaced)
│   └── test_sidebar_caption.py  # removed (replaced; taric_caption moves to view.py)
├── integration/
│   └── test_recheck.py      # new
├── ui/                      # new: harness.py, test_main_page.py, test_admin_page.py,
│                            #      test_app_navigation.py, test_response_time.py
└── eval/
    └── walkthrough.py       # new: the scripted walkthrough, writes walkthrough.json
README.md                    # changed: the new pages, the walkthrough result
CLAUDE.md                    # changed: the CRLF list loses ui/detail.py and ui/review.py
```

**Structure Decision**: the single-project layout stays.
- **The UI is split by page and by role**: one module per page section, plus two pure modules (`view.py`,
  `shipper_email.py`) and `actions.py`. These hold every rule the pages show or apply, so they are tested without
  Streamlit.
- **Code that moves**:
  - from `ui/detail.py`: the measure tables move to `ui/expand.py`;
  - from `ui/sidebar.py`: `kb_caption` moves to `ui/admin.py`, and `taric_caption` to `ui/view.py`;
  - from `ui/chat.py`: `queue_finer_codes` and `_finish_job` move to `ui/runner.py`.
- **`ui/chat.py` keeps** `classify_message`, `_start`, `handle_message` and the transcript rendering. Five of the
  14 kept tests import or read them. It drops the start-screen quick actions and the pending-file start, which the main
  page now owns.

## Complexity Tracking

None. The Constitution Check has no violation to justify.
