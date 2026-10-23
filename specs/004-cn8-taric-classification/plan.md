# Implementation Plan: CN-8 and TARIC-10 Classification in the Agent and the UI

**Branch**: `004-cn8-taric-classification` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-cn8-taric-classification/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Once a line's HS-6 is decided, two new agent tools take it to ten digits:
- **`classify_cn8`** chooses one of the CN 2026 eight-digit lines under the HS-6. It shows a confidence, the deciding words of the line text, and an EBTI ruling at that CN-8 as precedent. When the text does not show the attribute that separates the lines, it decides nothing, and the line routes to ask the shipper, naming the attribute.
- **`lookup_taric`** calls feature 003's `lookup_taric(cn8, origin)` unchanged and applies one of five rules in code:
  - auto-complete a single subdivision;
  - let the clerk choose among several;
  - require confirmation where a trade-defence measure applies;
  - stop at 8 digits when TARIC has nothing;
  - say "TARIC not loaded".

The clerk then:
- sees the subdivisions with their measures in three groups, with the snapshot date and two links;
- confirms what the rules leave open;
- exports two new columns.

The HS-6 path, `CODE_PATTERN` and the loaders do not change.

Technical approach, from [research.md](research.md):
- **CN-8 options (R-01)**: read from the CN 2026 chunk text. 67 % of subheadings have a single CN-8 line, which is taken without a model call.
- **Precedent (R-02)**: valid EBTI rulings under the HS-6, nearest to the line text. They come from the existing BTI vectors filtered by subheading, at most 2 per CN-8 line and 8 in all.
- **Judgement (R-03)**: one structured call `Cn8Out` per line with several CN-8 lines.
  - Code checks the code, the citation and the attribute.
  - The CN-8 is written only at or above the auto-accept threshold (clarification Q4).
- **Routing (R-04)**: `route_line` gains the CN-8 question as its one new input (constitution v1.2.0). `hs6_auto_decided` keeps the decided HS-6 and its export values unchanged.
- **TARIC rules (R-06, R-07)**: a pure module `agent/taric_rules.py` holds the rule, the write decision, the confirm set (551–555 and 570) and the measure-group table.
- **Origin (R-10)**: `Shipment.taric_origin`, CN by default. A change re-applies the rules without a model call.
- **Export (R-11)**: `cn8` and `taric10` appended after `note`.
- **Evaluation (R-12)**: a seeded EBTI sample over subheadings with at least two CN-8 lines, scored leave-one-out.

## Technical Context

**Language/Version**: Python 3.13 (project range `>=3.11,<3.14`)

**Primary Dependencies**: unchanged, and no new package:
- LangChain v1 (`create_agent`, tools);
- the OpenAI-compatible SDK through OpenRouter, for chat and embeddings;
- Pydantic, Streamlit 1.65, Chroma and `rank_bm25`.

**Storage**:
- **Line store**: the session-state line store gains a CN-8 choice and a TARIC outcome per line version, and an origin per shipment ([data-model.md](data-model.md)). Measures are never stored; they are looked up whenever they are shown.
- **Read-only**: `data/nomenclature_2026.jsonl`, `store/bti_docs.jsonl`, `store/chroma-bti` and `data/taric.jsonl`. No loader or index changes.
- **New output**: `tests/eval/cn8_eval.json`, written by the evaluation script.

**Testing**: pytest, offline, with tests first for the guardrails (R-15).
- **Model calls**: `FakeRawClient` with recorded `Cn8Out` and `SubdivisionOut` outputs.
- **TARIC**: feature 003's `tests/fixtures/taric/snapshot_small.jsonl`, extended with a CN-8 without subdivisions and a single subdivision carrying 555 or 570.
- **Scripts**:
  - `run_eval.py`, `cn8_eval.py` (new), the budget test and the scale check need the key and spend credits;
  - `taric_ui_parity.py` (new) needs no key.

**Target Platform**: the Windows 11 developer machine; the Streamlit app at http://localhost:8501.

**Project Type**: single Python project, as in features 001 to 003.

**Performance Goals**: feature 001's limits, with the new steps included (SC-008, clarification Q5):
- a 12-line list in under 60 s, and a 100-line list within 5 minutes;
- under €0.10 for 12 lines plus two follow-up questions.

The steps add, all run concurrently per line (R-13):
- at most one structured call and one embedding request per decided line with several CN-8 lines;
- one small call per CN-8 with several subdivisions.

A TARIC lookup takes under 1 ms, so origin and threshold changes run synchronously.

**Constraints**:
- `CODE_PATTERN`, the HS-6 pipeline, its results and the existing export columns are unchanged (FR-021).
- No loader change; TARIC is never embedded or indexed.
- Untrusted text reaches the model only fenced.
- Native Streamlit only. `ui/chat.py`, `ui/detail.py` and `ui/review.py` keep their CRLF line endings.

**Scale/Scope**:
- **Nomenclature**: 5,612 HS-6 subheadings and 9,791 CN-8 lines. 1,835 subheadings have two or more CN-8 lines.
- **Precedent**: 73,899 valid EBTI rulings, all coded to at least 8 digits.
- **TARIC**: 80 import measure types. A subdivision can carry about 94 anti-dumping rows for China (7318 15 58).
- **Lines**: the measured sizes are 12 and 100 lines (SC-008).

No NEEDS CLARIFICATION remain; [research.md](research.md) resolves R-01 to R-17. The author settled the four points
raised in planning on 2026-10-23; they are listed after the Constitution Check.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.2.1 (2026-10-23).

| # | Principle | Gate | Pre-research | Post-design evidence |
|---|---|---|---|---|
| I | Guardrails live in code | One routing function from the flag, the confidence against the threshold, and the missing CN-8 attribute. CN-8, TARIC-10 and measures exist in their sources, with the snapshot date shown. No subdivision is written without confirmation, except the single auto-complete with an audit entry. Schemas are validated | PASS | **Routing**: `route_line` gains `cn8_question`; the store passes it, and nothing else routes (data-model §6). **Rules**: `cn8_written_by_rule`, `taric_rule` and `code_to_write` are pure functions; the threshold and the confirm set are compared in code, never in the prompt. **Existence**: `validate_cn8` checks the CN 2026 lines under the decided HS-6, and `validate_taric10` the snapshot's subdivisions. Measures are looked up, never stored or generated. **Schemas**: `Cn8Out` and `SubdivisionOut` are strict, with one retry. **Stricter than required**: trade-defence measures always need confirmation (FR-011). Nothing is filed or sent (FR-023) |
| II | Untrusted input, end to end | Text fenced; never an instruction, path or tool hint | PASS | **Fencing**: both new calls fence the line text with `fence()`, and send ruling excerpts and subdivision descriptions as data. **Origin**: a validated two-letter code. **Adversarial test**: a new fixture orders the model to pick a CN-8 and to write a TARIC-10; the test asserts that validation and the rules are unaffected |
| III | Grounded, cited, never guessed | Precedent traced to a ruling retrieved in the run; expired rulings filtered; "no ruling" stated; confidence not presented as calibrated | PASS | **Citations**: a cited ruling must be among those sent (R-03). **Validity**: `BTIStore.by_cn8` applies the validity filter. **Confidence**: the card captions it "model estimate". **Measures**: they and both links come from the official sources, with the snapshot date. A missing attribute leads to a question, not a code (FR-003) |
| IV | Hybrid, structure-aware retrieval | `classify_hs6` pipeline unchanged; TARIC never embedded; scripted loader; truthful sidebar | PASS | The HS-6 pipeline is untouched (FR-021). The CN-8 precedent search reuses the existing BTI vectors with a subheading filter, so there is no new index and no loader change. The knowledge-base caption is unchanged |
| V | Single-purpose, schema-typed tools | Each added tool listed with a justification; Pydantic schemas; plain functions; per-line isolation; a reply re-runs one line; append-only audit | PASS | **Tools**: the two that constitution v1.2.0 names, `classify_cn8` and `lookup_taric`, justified in [contracts/tools.md](contracts/tools.md). Both wrap plain functions run through `run_per_line`. **Replies**: `apply_shipper_reply` also runs both steps, for the referenced line only. **Audit**: six change kinds are added, append-only |
| VI | Native Streamlit UI | Native components; guardrails visible; review table from the store; panel statement true | PASS | **Components**: `st.metric`, `st.expander`, `st.dataframe`, `st.radio`, `st.button`, `st.link_button`, `st.code`, `st.popover` and `st.badge`; no custom HTML, CSS or JavaScript. **Guardrails**: confirm buttons are disabled, with the reason. **Store**: counts and markers are read from it. **Panel**: the "What I can and cannot do" text gains CN-8 and TARIC ([contracts/ui.md](contracts/ui.md)) |
| VII | Test-first and measured | Guardrail tests written first and seen to fail, offline; live checks separate | PASS | **Failing tests first** (R-15) for: `route_line` with the question; `hs6_auto_decided`; the five TARIC rules and `code_to_write`; the group table; both validators; the threshold rule; the store transitions; the export columns. **Live**: the CN-8 evaluation and the budget and scale checks are separate runs |
| — | Technology stack | Stack as listed; deviations recorded | PASS | No new dependency. Feature 002's GnuPG deviation is unchanged and not used here |
| — | Out of scope | Nothing sent; no ATLAS flow; the UI implies nothing more | PASS | "Ask the shipper" sets a route and a question for the clerk. Duty calculation, company names, certificates, the German layer and origin rules are not built |
| — | Data and privacy | Every dataset recorded; no shipper data | PASS | No new dataset. The evaluation set is a seeded sample of the recorded EBTI build |
| — | Code organisation | `app.py` → `agent/` → `tools/` → `rag/` | PASS | New modules are `agent/taric_rules.py`, `tools/classify_cn8.py` and `tools/lookup_taric.py`. The UI calls `agent` functions only (`after_hs6_decision`, `apply_taric_origin`), never the model or retrieval |
| — | UI design contract | No listed element removed or moved | PASS | **Added**: a detail section, two metrics after the routing metrics, and row markers. The columns and the route-based filter stay. **Sample**: since v1.2.1, Screen 1 describes it as "12 lines with 6 needing action" (decision 3) |

**Post-design re-check (after Phase 1)**: all gates still PASS; no deviation. The author settled the four findings of
planning on 2026-10-23:
1. **Evaluation set (R-12)**: 120 rulings, 10 from each of the 12 target chapters, drawn only from subheadings with at least two CN-8 lines; the target is 60. The spec's SC-002, Key Entities and Assumptions say so.
2. **"TARIC not available" (R-16)**: every CN 2026 CN-8 line has at least one subdivision on 2026-10-01, so the rule is proven by fixture tests only. The spec's edge case says so.
3. **The sample (R-17)**: six of its twelve lines need action, because "Plastic toy cars" routes to ask the shipper about a motor.
   - The quick-action hint, the expected routes and the counts in the offline flow test are updated.
   - The constitution is amended to v1.2.1 for Screen 1.
4. **The route column after clerk actions (R-09, data-model §6)**: as designed.
   - Confirming a CN-8 or TARIC-10 on an auto-accepted line makes the route read accepted, set by the clerk.
   - Sending a line to the shipper from the TARIC section empties its decided HS-6, CN-8 and TARIC-10 export columns, as feature 001 does for any ask-shipper decision.

## Project Structure

### Documentation (this feature)

```text
specs/004-cn8-taric-classification/
├── spec.md              # Feature specification (with clarifications)
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output: R-01 … R-17
├── data-model.md        # Phase 1 output: the CN-8 choice, the TARIC outcome, routing, audit, export
├── quickstart.md        # Phase 1 output: scenarios A–H and the browser check
├── contracts/
│   ├── tools.md         # classify_cn8, lookup_taric, guardrail functions, line store, agent (changes to 001's)
│   ├── ui.md            # sidebar origin, counts, row markers, the detail section (changes to 001's)
│   └── export.md        # cn8 and taric10 columns (changes to 001's)
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
agent/
├── routing.py                 # route_line(..., cn8_question); hs6_auto_decided; cn8_written_by_rule; validate_cn8; validate_taric10
├── taric_rules.py             # NEW, pure: TRADE_DEFENCE_CONFIRM, taric_rule, code_to_write, measure_group, taric_view,
│                              # eu_taric_url, EZT_ONLINE_URL
├── schemas.py                 # Candidate.cn8/taric10; Decision.decided_cn8/decided_taric10; Cn8Choice; TaricOutcome;
│                              # LineVersion.cn8/taric; Shipment.taric_origin; Cn8Out; SubdivisionOut; six ChangeKind values
├── store.py                   # set_cn8_result, confirm_cn8, set_taric_result, confirm_taric10, ask_shipper_for_taric,
│                              # set_taric_origin; decided_code via hs6_auto_decided; decided_cn8/decided_taric10; counts;
│                              # set_threshold; effective_route; export columns
├── prompts.py                 # tool order 6-7; CN-8 and subdivision prompts; build_context gains CN-8 and TARIC
└── agent.py                   # _finalize runs the two steps; after_hs6_decision; apply_taric_origin
tools/
├── __init__.py                # load_all lists seven modules
├── classify_cn8.py            # NEW: choose_cn8 (plain function) and the classify_cn8 tool
├── lookup_taric.py            # NEW: the lookup_taric tool over kb.taric
└── apply_shipper_reply.py     # also runs the CN-8 and TARIC steps for the referenced line
rag/                           # read-only helpers; no loader change
├── nomenclature.py            # NomenclatureIndex.cn8_lines(hs6)
├── bti.py                     # BTIStore.by_cn8(hs6, as_of)
└── retriever.py               # ChromaVectorSearch.search_by_vector gains an optional where filter
ui/
├── sidebar.py                 # "Origin (TARIC)" in the Shipment expander
├── chat.py                    # CRLF: the two confirmation metrics; the "What I can and cannot do" text;
│                              # the sample hint "12 Yiwu consolidation lines, 6 problematic"
├── review.py                  # CRLF: marker badges in the route cell
├── detail.py                  # CRLF: the "CN-8 and TARIC-10" section
└── jobs.py                    # after_hs6_decision as a background job
data/samples/sample_lines.json # expected routes updated to what FR-003 produces (decision 3)
tests/
├── fakes.py                   # default_for Cn8Out and SubdivisionOut
├── fixtures/
│   ├── recorded/              # recorded Cn8Out and SubdivisionOut outputs
│   ├── adversarial.jsonl      # a description ordering the model to pick a CN-8 and write a TARIC-10
│   └── taric/snapshot_small.jsonl   # a CN-8 without subdivisions; a single subdivision with 555 or 570
├── unit/
│   ├── test_taric_rules.py    # NEW: the five rules, code_to_write, groups, taric_view parity, links
│   ├── test_routing.py        # cn8_question, hs6_auto_decided, the threshold write rule
│   ├── test_validate.py       # validate_cn8, validate_taric10
│   ├── test_store.py          # confirmations, questions, origin, threshold, effective route, counts, audit
│   ├── test_export.py         # existing columns unchanged; cn8 and taric10 top-down
│   └── test_apply_reply.py    # the reply runs both steps for its line only
├── integration/
│   ├── test_classify_cn8.py   # NEW: options, precedent, validation, question, written or suggested
│   ├── test_lookup_taric.py   # NEW: rules on the fixture snapshot, suggestion only for several subdivisions
│   ├── test_agent_check_flow.py   # tool order 6-7 and the completeness guard
│   └── test_upload_flow.py    # the sample's counts: 6 needing action, plus the two confirmation counts
├── adversarial/test_injection.py  # the new fixture
└── eval/
    ├── cn8_eval.py            # NEW: SC-002 (live)
    └── taric_ui_parity.py     # NEW: SC-004 on the 20 acceptance codes (no key)
README.md, CLAUDE.md           # at implementation: seven tools, the CN-8 and TARIC section, weaknesses
```

**Structure Decision**: the layout of features 001 to 003 is kept.
- **New modules**: the two tools, each in its own module as before, and the pure rules module next to `routing.py`.
- **`rag/`**: it gains only read-only helpers.
- **UI**: changes stay in the files that own each element.

## Design notes (how the pieces fit)

- **CN-8 step** (`tools/classify_cn8.py`):
  - `choose_cn8` reads the options from `NomenclatureIndex.cn8_lines`. A single option is written by rule at confidence 100, with no model call.
  - Otherwise it selects rulings with `BTIStore.by_cn8`, ranked by vector similarity when the BTI vectors are loaded, and makes one `Cn8Out` call.
  - It validates the result: the code, the citation, and the attribute. `cn8_written_by_rule` then decides whether the CN-8 is written or suggested.
  - `LineStore.set_cn8_result` stores the choice, records the audit and recomputes the route.
- **Routing and "decided"** (data-model §6):
  - `_recompute` passes the open question to `route_line`.
  - `decided_code()` uses `hs6_auto_decided` when there is no clerk decision, so the HS-6 stays decided while a CN-8 question is open.
  - `effective_route` lets an open CN-8 question override an HS-6 acceptance, but not the clerk's review or ask-shipper choice.
  - Written codes are read top-down.
- **TARIC step** (`tools/lookup_taric.py`):
  - It looks up `kb.taric.lookup_taric(cn8, origin)` and computes `taric_rule`, then `code_to_write`.
  - For several subdivisions it makes one `SubdivisionOut` call; the suggestion is kept only if valid and the attribute is stated.
  - `set_taric_result` records `taric_written`, `taric_pending` or `taric_not_available`.
- **Measures shown**: `taric_view` groups the lookup output by `measure_group` for the card. The parity tests and `taric_ui_parity.py` prove it adds, drops and alters nothing.
- **When the steps run** (R-05):
  - **During a check**: the agent calls them as tools 6 and 7, and `_finalize` runs whatever it skipped.
  - **After the clerk accepts or chooses an HS-6**: the UI starts `after_hs6_decision` as a background job. A CN-8 confirmation runs the TARIC step only.
  - **Shipper reply**: `apply_shipper_reply` runs both for its line.
  - **Origin change**: `apply_taric_origin` re-runs the lookup and the rules for every line with a CN-8, reusing the stored suggestions, with no model call.
  - **Threshold change**: `set_threshold` re-evaluates CN-8 choices the clerk has not confirmed and re-applies `code_to_write`.
- **Changing the HS-6**: when the clerk accepts an HS-6 other than the one the CN-8 was chosen under, `set_decision` clears the CN-8 choice and the TARIC outcome, and the CN-8 step runs again.
- **Export**: `export_rows` appends `cn8` and `taric10` from `decided_cn8` and `decided_taric10`. Every existing key is computed as before.
- **Documentation**, at implementation as the author asked:
  - **`README.md`**: a CN-8 and TARIC section, the evaluation result, and the weaknesses: CN-8 confidence is a model estimate, "not available" is untested on real data, and additional-code companies are not named.
  - **`CLAUDE.md`**: "five typed tools" becomes seven.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None. The GnuPG command-line tool remains the one recorded deviation, justified in feature 002's plan; this feature adds
no other.
