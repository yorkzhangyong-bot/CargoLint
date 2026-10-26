# Implementation Plan: Precedent Override at the HS-6

**Branch**: `008-hs6-precedent-override` (no git branch yet; the files sit untracked on `main`) | **Date**: 2026-10-26 |
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-hs6-precedent-override/spec.md`, with the author's plan input: the
override is code only, so each eval makes one paid run with the switch on and replays the switch-off result from the
stored model answers and retrieved rulings, with no second paid run. On the end-to-end eval's override lines, the CN-8
step runs under both the top candidate and the chosen candidate. Both evals run at `--repeat 1`. The constitution 1.6.0
amendment and the feature 001 FR-020 correction are tasks, as in feature 006.

## Summary

When the model's top HS-6 candidate fails the ruling vote, but at least `OVERRIDE_MIN` (4) of the 5 nearest eligible
EBTI rulings sit at its second or third candidate, the gate decides that candidate and auto-accepts it. The reason
reads "rulings overrode the model: N of M agree on <code>". A majority of 3 of 5, or agreement on a code outside the
top three, stays review; the latter is shown as a hint.

The rule is one more case of the existing HS-6 gate, in `agent/routing.py`. It sits behind a switch that is off by
default (`CARGOLINT_HS6_OVERRIDE`, `OVERRIDE_MIN`). Each shipment keeps the switch state its routes use. The store's
decided code, the detail row and the audit trail show the chosen candidate. The CN-8 layer is unchanged.

Both evals record the chosen candidate and whether the supported candidate was right. Each derives the switch-off
result from its one paid run, so on and off differ only by the rule.

## Technical Context

**Language/Version**: Python 3.11–3.13 (the project's `.venv`)

**Primary Dependencies**: Streamlit (native elements only), LangChain v1 with OpenRouter (default chat model Gemini 2.5
Flash, reasoning off), Pydantic v2, Chroma with BM25 (`rag/`), pytest

**Storage**: the line store in the Streamlit session, in memory; eval results as JSON files in `tests/eval/`; no
database

**Testing**: pytest, offline by default (fake structured-output backend, offline guard in `tests/conftest.py`); the
live evals are run by hand, only when the author asks

**Target Platform**: the local Streamlit app (Windows in development; any OS with Python 3.11–3.13)

**Project Type**: a single-project web application (Streamlit) with an agent backend and eval scripts

**Performance Goals**: no new model call in the product, since the override is a few comparisons per line. Feature
001's time and cost limits are unchanged. Each eval makes one paid run; the end-to-end eval adds one CN-8 call per
override line.

**Constraints**:
- guardrails in code (Principle I), untrusted input (II), native Streamlit (VI), offline tests (VII);
- the switch is off by default;
- `--repeat 1` for this feature's eval runs;
- each file keeps its line endings (LF, except the CRLF files listed in `CLAUDE.md`).

**Scale/Scope**: shipments up to 200 lines; the 120-line eval set; about six source modules, two evals and eight test
files touched

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution 1.5.0.

| Principle | Check | Status |
|---|---|---|
| I. Guardrails live in code | The override is a pure case of the HS-6 gate in `route_line`, decided by code from the stored vote and candidates. But 1.5.0 auto-accepts an HS-6 only when the model's top candidate is the rulings' majority, and sends a majority at the second or third candidate to review. | **Violation until 1.6.0**: justified below, resolved by task A1 before any routing code |
| II. Untrusted input | No new text reaches the model; the override reads the vote and the candidates the store already holds. | Pass |
| III. Grounded, cited | The override cites the agreeing rulings (N of M, and their issuing countries in the detail row) and only ever chooses one of the model's own candidates, so no new code appears. | Pass |
| IV. Hybrid retrieval | Retrieval and the vote's rulings are unchanged. | Pass |
| V. Typed tools | No new tool; the schemas gain one gate value and one shipment field. | Pass |
| VI. Native UI that shows its work | The detail row and the audit trail show the chosen candidate, the model's top candidate and the note, in plain text. | Pass |
| VII. Test-first, measured | Threshold tests come before the code. Both evals measure on against off from the same answers. | Pass |
| Architecture: the UI reads only the store, routing is one function | The decided code comes from `LineStore.decided_code`, the route from `route_line`. | Pass |

**Post-design re-check** (after research, data model and contracts): unchanged. The design adds no tool, no prompt
and no UI element, and it keeps routing in `route_line`. The one violation, Principle I, is still resolved by task A1,
which runs before the routing code (tasks C3, C4).

## Project Structure

### Documentation (this feature)

```text
specs/008-hs6-precedent-override/
├── spec.md              # /speckit-specify, /speckit-clarify
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── override.md      # Phase 1: routing, texts, audit, evals
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # /speckit-tasks (not created by this command)
```

### Source Code (repository root)

```text
agent/
├── config.py            # OVERRIDE_MIN; Settings.hs6_override (CARGOLINT_HS6_OVERRIDE)
├── schemas.py           # Hs6Gate.vote_override; Shipment.hs6_override_min
├── routing.py           # hs6_gate(override_min), route_line(hs6_override_min), hs6_auto_decided, hs6_choice
└── store.py             # passes the shipment's switch; decided_code; the code_decided audit entry
ui/
├── upload.py            # open_shipment sets hs6_override_min from the settings
└── view.py              # _hs6_how, explain_a (texts and hint), _review_text, preselect
tests/
├── unit/                # test_hs6_override.py (new: routing, store, audit), test_chat_model.py, test_view.py,
│                        # test_hs6_eval.py, test_e2e_eval.py
├── integration/         # test_e2e_eval.py (the override line in its own test)
├── ui/                  # harness.py (an "hs6_override" state), test_main_page.py
└── eval/
    ├── hs6_eval.py      # on and off from one run; "Precedent override" report section
    ├── e2e_eval.py      # switch on; CN-8 under the top candidate on override lines; off replay; on and off report
    └── cn8_eval_iteration12.json   # pinned copy of the CN-8 eval's iteration 12 (commit ce3bf02)
specs/001-packing-list-check/
├── spec.md              # vocabulary "decided code", FR-020
└── data-model.md        # §9 footnote 1
.specify/memory/constitution.md    # 1.6.0, via /speckit-constitution (task A1)
README.md                          # routing summary and the end-to-end paragraph, after the runs
```

**Structure Decision**: the existing single project. The rule joins the HS-6 gate in `agent/routing.py`; the store,
the upload and the view change only where they read the gate or the decided code; and the two evals from features
006 and 007 gain the on and off records.

## Implementation outline

These are the task groups `/speckit-tasks` expands. Paid runs happen only when the author asks.

**A. Governance (as in feature 006)**
- **A1**: before any routing code, the author runs `/speckit-constitution` with the draft below.
- **A2**: in the same change as the code, correct feature 001:
  - its vocabulary, "decided code";
  - FR-020, "An auto-accepted line's decided code is its top candidate";
  - its data-model §9 footnote ¹, which describes the same gate.
  Each gets: "…or, when the precedent override (feature 008, switched on) decided it, the second or third candidate on
  which at least OVERRIDE_MIN of the five nearest eligible rulings agree."

**B. Tests first (offline)**
- **B1**: routing (`tests/unit/test_hs6_override.py`). Every row of contracts §1, the exact threshold (4 of 5, 3 of
  5, 4 of 4), a model that returned fewer than three candidates, and the switch off equal to today for every gate
  case.
- **B2**: store (`tests/unit/test_hs6_override.py`, classes `TestStore` and `TestAudit`), covering:
  - the shipment field and its bound against `HS6_VOTE_K`;
  - the decided code, and the export row;
  - a threshold move;
  - both audit entries, written once;
  - a clerk's change, with the audit entry's `previous`;
  - ready to accept on an ever-flagged line;
  - the CN-8 step run on the chosen candidate.
- **B3**: view (`test_view.py`): the texts and the hint of contracts §2, the pre-selection and "Confirm: {code}".
- **B4**: a page test (`tests/ui/`) with an overridden line seeded: green, the chosen code, the "Decided:" line.
- **B5**: evals (`test_hs6_eval.py`, `test_e2e_eval.py`, `tests/integration/test_e2e_eval.py`): the on and off fields
  derived from one stored run; on an override line, the off replay uses the CN-8 answer under the top candidate. The
  end-to-end integration test puts the override line in a test of its own and leaves the five-line test unchanged.

**C. Code**
- **C1**: `OVERRIDE_MIN` and `Settings.hs6_override`.
- **C2**: the schema additions.
- **C3**: `hs6_gate`, `route_line`, `hs6_auto_decided` and `hs6_choice`.
- **C4**: the store.
- **C5**: `open_shipment`.
- **C6**: the view.

**D. Evals**
- **D1**: pin `tests/eval/cn8_eval_iteration12.json`.
- **D2**: the HS-6 eval's on and off fields, measures and report section.
- **D3**: the end-to-end eval's shipment with the switch on, the extra CN-8 call per override line, the off replay,
  and the measures and report.

**E. Runs and documentation (paid runs only when asked)**
- **E1**: `hs6_eval.py --repeat 1 --tag hs6-override --cn8 tests/eval/cn8_eval_iteration12.json`.
- **E2**: `e2e_eval.py --repeat 1 --tag e2e-override`.
- **E3**: the README's routing summary and end-to-end paragraph, with the results.
- **E4**: the switch decision against SC-001 to SC-003 (FR-007).

### Draft for task A1: constitution 1.6.0 (Principle I)

Your summary of the amendment, worded for the constitution:

- Replace the third bullet of Principle I with:
  "An unflagged line's HS-6 MUST be auto-accepted only when the HS-6 gate passes. The rulings' majority either
  confirms the model's top candidate or, with the precedent override switched on (`HS6_OVERRIDE`), overrides it to the
  model's second or third candidate when at least `OVERRIDE_MIN` (default 4) of the 5 nearest eligible rulings sit
  there. That candidate becomes the decided code, with the reason "rulings overrode the model: N of M agree on
  <code>", M being the rulings that voted (5 unless fewer are eligible). Three of five, or agreement on a code outside
  the model's top three, stays `review`, and a code outside the
  top three is shown as a hint, never chosen. `OVERRIDE_MIN` is a named configuration constant; behaviour at exactly
  `OVERRIDE_MIN` MUST be fixed in the spec and covered by a test. Otherwise the line goes to `review` with the
  competing rulings and their issuing countries as the reason, naming the model's candidate the rulings support when
  it is the second or third. A flagged (vague or stop-word) line MUST NOT be routed to `auto_accept`."
- In the second bullet, after "the model's code equals the rulings' majority code", add "(at the HS-6, its top
  candidate or, with the precedent override, its second or third)".
- Amendment log, 1.6.0: "Principle I: the precedent override at the HS-6 (feature 008). With `HS6_OVERRIDE` on, at
  least `OVERRIDE_MIN` (4) of the 5 nearest eligible rulings at the model's second or third candidate decide that
  candidate and auto-accept it with the note "rulings overrode the model: N of M agree on <code>"; 3 of 5, or
  agreement outside the top three, stays review. The switch ships off until the HS-6 and end-to-end evals, each
  comparing the switch on and off on the same stored model answers, show more lines right end to end and no more
  wrong auto-accepts."

Suggested companion changes, your call (1.5.0 made the same kind of change):
- In Principle VII, extend "the HS-6 and CN-8 ruling-vote gates" with "and the precedent override".
- In the UI Design Contract, kind (a): "and, when the precedent override decided the line, which candidate was chosen,
  with the issuing countries of the rulings that agree; a code outside the top three is shown as a hint."

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Principle I (1.5.0) allows the HS-6 auto-accept only for a top candidate that the rulings' majority confirms. | The feature's purpose (FR-001): when 4 or 5 of 5 rulings agree on the model's second or third candidate, the clerk should not have to pick it by hand. | Keeping today's rule leaves that pick to the clerk on every such line. The amendment (1.6.0, task A1) runs before the routing code, as 1.4.0 and 1.5.0 did in feature 006. |
