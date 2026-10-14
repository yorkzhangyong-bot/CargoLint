# Implementation Plan: CargoLint MVP — Packing-List Description Check and HS-6 Suggestion

**Branch**: `001-packing-list-check` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-packing-list-check/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

A customs clerk uploads or pastes a China→EU packing list; for every line CargoLint flags vague
and stop-word descriptions with the rule that matched, suggests the top-3 HS-6 subheadings with
confidence, reasoning, sources and a BTI precedent, and routes the line (auto-accept / human
review / ask the shipper) by a deterministic rule against a sidebar threshold. The clerk works
a review table with a detail panel, decides a code when accepting, asks follow-up questions,
pastes shipper replies that re-check one line, and exports CSV/JSON with tokens and cost shown.

Technical approach: a Streamlit 1.65 app whose chat column drives a LangChain 1.4 agent (model
via OpenRouter) with exactly five schema-typed tools; a local knowledge base (CN 2026 chunked
per HS-6 subheading, EBTI rulings for ten chapters, ICS2 and firm rule lists) queried by hybrid
retrieval (own BM25 over `rank_bm25` + Chroma vectors with Qwen3 embeddings, fused by RRF);
guardrails (routing, lock, code existence, schema validation, data fencing) implemented as pure
Python functions with mandatory offline tests. Design artifacts: [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Python 3.11 (3.12 allowed; `>=3.11,<3.13`)

**Primary Dependencies**: Streamlit 1.65.0; LangChain 1.4.5 (+ langchain-core 1.6.10,
langgraph 1.2.15, langchain-openai 1.7.1, openai 3.31.0); langchain-chroma 1.1.0 / chromadb
1.5.9; rank_bm25 0.2.2; pydantic 2; pandas + openpyxl; pdfplumber 0.11.10; rapidocr 3.10.0 +
onnxruntime 1.31.0; lxml; python-dotenv. Full pins in [research.md §R-17](research.md).

**Storage**: `st.session_state` line store (MVP); Chroma persisted in `store/chroma`; BM25
pickle in `store/bm25.pkl`; BTI document store `store/bti_docs.jsonl`; processed data as JSONL/
JSON in `data/`; raw downloads git-ignored in `data/raw/`.

**Testing**: pytest (markers `unit`, `integration`, `adversarial`, `live`); offline by default
with a fake client factory and recorded structured outputs; `live` needs `OPENROUTER_API_KEY`;
`tests/eval/run_eval.py` for the labelled set; RAGAs as a stretch extra.

**Target Platform**: local desktop — Windows 11 developer machine, Streamlit in the browser;
no deployment in the MVP.

**Project Type**: single Python project: Streamlit web app + importable domain packages.

**Performance Goals**: 12-line list checked in < 60 s; 100-line list in < 5 min; first progress
step visible < 2 s; threshold changes instant (no model calls) — spec SC-005, FR-021.

**Constraints**: offline unit tests (no keys); cost < €0.10 per 12-line shipment + 2 follow-ups;
caps 20 MB / 200 lines / 300 chars / 50 pasted lines; every displayed or decided code must exist
in the nomenclature; routing and lock in code only; secrets from environment only.

**Scale/Scope**: single user, one shipment per session; ~5.6k nomenclature chunks + ≤ 50k ruling
chunks; 5 tools; 2 screens; 20–25 h build budget.

No NEEDS CLARIFICATION remain — every unknown was resolved in [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Gate | Pre-research | Post-design evidence |
|---|---|---|---|---|
| I | Guardrails live in code | Routing, threshold, lock, code existence and schema validation are pure functions, never prompt text or model output | PASS (spec FR-020–023, FR-044) | `agent/routing.py` (`route_line`, `is_contradiction`, `validate_code`), `agent/schemas.py` re-validation of every structured output; `LineStore.set_decision` enforces the lock — [contracts/tools.md §2–3](contracts/tools.md) |
| II | Untrusted input end to end | Fencing, caps, no instructions from data, secrets from env, no contact logging, adversarial tests | PASS (FR-043–047) | `fence()` in `agent/prompts.py`; caps in `tools/parsers.py` before any model call; `NAME_AND_ADDRESS` dropped at BTI load; `.env` only; `tests/adversarial/` — R-07, R-12, R-16 |
| III | Grounded, cited, never guessed | Sources only from retrieved chunks; subheading text from index; precedent validity filtered; history-only flagged; confidence labelled an estimate | PASS (FR-010–017, FR-029) | `Candidate.subheading_text`/`chapter` filled from the index, `Source` ids stable; `lookup_precedent` filters `valid_to`; `history_only` field; caption in detail panel — data-model §5–6, contracts/ui.md |
| IV | Hybrid, structure-aware retrieval | Pipeline order; one chunk per HS-6 with metadata; hybrid default with vector-only baseline; scripted loader; truthful KB caption | PASS (FR-018–019) | `rag/retriever.py` (BM25 + Chroma + RRF), `rag/translate.py`, `rag/nomenclature.py` (SKOS → chunks), `rag/loader.py` CLI with chapter list; caption generated from index metadata — R-03, R-04, R-11 |
| V | Single-purpose, schema-typed tools | Exactly five tools; Pydantic I/O; testable without model/Streamlit; per-line isolation; append-only versions | PASS (spec §Tools) | Five tools in `tools/` with `args_schema`; batch inputs keep the count at five; thread pool with per-line try/except; `LineStore.add_version` append-only + audit — contracts/tools.md §1, §3 |
| VI | Native Streamlit UI that shows its work | Native widgets; progress/sources/trace/metrics/export; table from store; locks visible; tokens and cost; English UI with Chinese glyphs | PASS (FR-026–035, FR-040) | contracts/ui.md maps every element to a 1.65 widget; Styler/`st.badge` for chips, no custom HTML planned — R-08, R-09 |
| VII | Test-first and measured | Guardrail tests written first and offline; labelled set before `classify_hs6`; error scenarios covered | PASS (SC-001–011) | R-16 test layout; tasks must put `tests/unit/test_routing.py`, `test_validate.py`, `test_fence.py`, `test_parsers.py`, `test_rules.py`, `test_rrf.py`, `test_bti_filter.py`, `test_store.py` and the labelled set before the code they cover |
| — | Technology stack (constitution §Technology stack) | Stack as listed; deviations recorded | PASS | **One deviation**: RapidOCR instead of Tesseract/PaddleOCR → Complexity Tracking #1 |
| — | Out of scope | No ATLAS, no shipper messaging, no history UI, no CN-8/TARIC, no sending, no persistence | PASS | Filing selectbox has one option; no network calls except OpenRouter and the loader downloads |
| — | Build order and code organisation | Intro sequence; `app.py`/`agent`/`tools`/`rag`/`data`/`store`/`tests` | PASS | Project Structure below adds `ui/` (Streamlit fragments only) — see Structure Decision |
| — | Data and privacy | Each dataset recorded with source, version, retrieval date, licence; demo data labelled; no real contact data | PASS | `data/SOURCES.md` written by the loader; `shippers.json` and `bti_demo.jsonl` labelled synthetic/demo — R-11–R-13 |

**Post-design re-check (after Phase 1)**: all gates still PASS. The only item needing a
justification is the OCR engine (Complexity Tracking #1); the completeness guard (#2) is a
small second orchestration path added deliberately to satisfy FR-048.

## Project Structure

### Documentation (this feature)

```text
specs/001-packing-list-check/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── tools.md         # five tools, pure guardrail functions, line store, agent contract
│   ├── export.md        # CSV / JSON export format
│   └── ui.md            # Streamlit element contract per screen
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app.py                       # Streamlit entry point: layout, session bootstrap, routes events to ui/
.streamlit/config.toml       # theme (#1D4FB8), server.maxUploadSize = 20
pyproject.toml               # pinned dependencies (research R-17), pytest markers
.env.example                 # OPENROUTER_API_KEY, CARGOLINT_CHAT_MODEL, CARGOLINT_EMBED_MODEL, CARGOLINT_USD_EUR, CARGOLINT_WORKERS, CARGOLINT_OCR_MIN_SCORE
README.md                    # how RAG works here, tool loop, security, error scenarios, KB rebuild, tests, weaknesses, data attribution

agent/
├── schemas.py               # Pydantic models from data-model.md (Shipment, Line, LineVersion, Candidate, …) + tool I/O models
├── routing.py               # route_line, is_contradiction, validate_code, lock rules (pure)
├── prompts.py               # system prompt, fence(), context-block builder (counts, needs-action lines, selected line, rule lists on demand)
├── llm.py                   # client factory (ChatOpenAI + embeddings client), usage + cost recording, price table refresh, retry policy
├── agent.py                 # create_agent wiring, progress/usage callbacks, completeness guard
└── store.py                 # LineStore (session-state backing + in-memory backing for tests), audit, export rows

tools/
├── parse_packing_list.py    # tool wrapper over parsers.py / ocr.py
├── check_description.py     # rules first, judgement second (batch)
├── classify_hs6.py          # translate → filter → hybrid retrieve → rank → validate codes (batch)
├── lookup_precedent.py      # BTI document-store lookup, validity filter
├── apply_shipper_reply.py   # target resolution, extraction, single-line re-check, contradiction rule
├── parsers.py               # xlsx/csv/pdf readers, header detection, ZH/EN split, caps, shipper detection
└── ocr.py                   # RapidOCR wrapper, scanned-page detection

rag/
├── loader.py                # CLI: download → parse → chunk → embed → persist; writes data/SOURCES.md
├── nomenclature.py          # SKOS RDF (CN 2026) → HS-6 chunks
├── bti.py                   # EBTI full extract → chapter/validity-filtered JSONL + document store
├── rules.py                 # ICS2 PDFs → JSON term lists; firm list and shipper loaders
├── embeddings.py            # OpenRouter embeddings (Embeddings subclass), model/dimension metadata
├── retriever.py             # BM25Index, Chroma wrapper, rrf(), HybridRetriever with trace
└── translate.py             # ZH→EN translation, multi-query expansion, optional HyDE

ui/
├── sidebar.py               # uploader, shipment fields, rules, KB caption, tokens/cost, export
├── chat.py                  # messages, st.status progress, metrics, sources/trace expanders, chat input handling
├── review.py                # review table (st.dataframe + Styler + ProgressColumn), filters, selection
└── detail.py                # detail panel: candidates, route control, decided-code control, lock/ready/contradiction notes

data/
├── raw/                     # git-ignored downloads: ESTAT-CN2026.rdf, DDS2-EBTI_Full.zip, ICS2 PDFs
├── nomenclature_2026.jsonl  # ~5.6k HS-6 chunks (committed)
├── bti_subset.jsonl         # filtered rulings (git-ignored); bti_demo.jsonl (~200, committed)
├── rules/                   # ics2_unacceptable_terms.json, ics2_stop_words.json, firm_stop_words.json
├── shippers.json            # synthetic shipper history (no contact details)
├── samples/                 # sample_lines.json (the 12 design lines) + generated sample_packing_list.xlsx
├── labelled/lines_20.jsonl  # 5 vague, 3 stop-word, 12 clear lines with known codes
├── model_prices.json        # USD per 1M tokens, as_of date
└── SOURCES.md               # provenance: URL, version, retrieval date, licence per dataset

store/                       # git-ignored: chroma/, bm25.pkl, bti_docs.jsonl, index_meta.json

tests/
├── unit/                    # routing, validate, fence, parsers, rules, rrf, bti filter, store, contradiction, reply scope, cost calc
├── integration/             # each tool with the fake client; agent loop with fake model; completeness guard; export
├── adversarial/             # prompt-injection fixtures through check/classify/apply_reply
├── live/                    # needs key: embeddings smoke, structured output, cost reconciliation (/generation)
├── eval/run_eval.py         # labelled set: flag accuracy, top-1/top-3 hybrid vs vector-only, cost
└── fixtures/                # recorded structured outputs, adversarial.jsonl, sample files
```

**Structure Decision**: single project laid out as the constitution prescribes (`app.py`,
`agent/`, `tools/`, `rag/`, `data/`, `store/`, `tests/`, `README.md`) plus a `ui/` package that
holds only Streamlit rendering code imported by `app.py`. Dependencies point one way:
`app.py`/`ui/` → `agent/` → `tools/` → `rag/`, parsers and rule data; `agent/store.py` is the only
module that reads or writes line data; `agent/llm.py` is the only module that creates model or
embedding clients. Nothing under `agent/`, `tools/` or `rag/` imports Streamlit, so the domain
is importable and testable without a session (constitution, Architecture invariants).

## Design notes (how the pieces fit)

- **Check request flow**: clerk message (with upload) → `agent.invoke` with callbacks → tools
  `parse_packing_list` → `check_description` → `classify_hs6` → `lookup_precedent` write into
  the `LineStore`; the store calls `route_line` after each write → `finalize_check()` runs any
  missing step directly and returns counts → `ui/chat.py` renders the agent's prose plus
  metrics/sources/trace from the store, never from prose (contracts/tools.md §4).
- **Grounded follow-ups**: `agent/prompts.py` builds a context block from the store for each
  message — counts, needs-action lines, the selected line's full result (candidates, trace,
  sources) and, when the message mentions terms/reject/stop words, the rule lists with their
  source. The "Which terms does customs reject?" quick action is answered by code from
  `data/rules/*.json`.
- **Shipper reply**: `apply_shipper_reply` resolves the target (named line → selected line →
  ask), extracts `{material, part_name, use}` with a structured call on the fenced reply,
  re-runs the three tools for the new version, applies `is_contradiction`, and the store
  recomputes the route under the lock (`ready to accept` for previously flagged lines).
- **Decided code**: `ui/detail.py` shows the top-3 radio (top preselected) and a text input;
  `LineStore.set_decision` validates with `validate_code` against the nomenclature index and
  raises `UnknownCodeError` → inline error, no state change (FR-023, Q1).
- **Threshold slider**: `LineStore.set_threshold` → `recompute_routes()` for undecided `ok`
  lines only; no model call; audit entries with `actor=threshold_change` (FR-021, FR-025).
- **Knowledge base**: `python -m rag.loader` downloads CN 2026 SKOS, the EBTI full extract and
  the two ICS2 PDFs into `data/raw/`, writes the processed JSONL/JSON, embeds with
  `qwen/qwen3-embedding-8b` into Chroma, builds the BM25 pickle, records model/dimension in
  `store/index_meta.json` and provenance in `data/SOURCES.md`; `--chapters` and
  `--bti-chapters` control coverage; `--demo` builds only the demo subset for tests.
- **Cost**: `agent/llm.py` sums `usage_metadata` × `data/model_prices.json` → USD → EUR
  (`CARGOLINT_USD_EUR`), stored on the shipment and shown by `ui/sidebar.py` (R-06).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| OCR engine RapidOCR instead of the constitution's "Tesseract or PaddleOCR" (R-10) | pip-only install (~45 MB), Chinese + English by default, no system binary and no first-run model download; OCR is the lowest-priority input path in a 20–25 h budget, so install friction matters more than peak accuracy | Tesseract needs the UB Mannheim system installer and language packs and is weak on phone photos; PaddleOCR needs the 105 MB paddlepaddle wheel, PaddleX dependencies and model downloads on first run. Both remain pluggable behind `tools/ocr.py`. Suggest amending the constitution's stack line to "RapidOCR (Tesseract/PaddleOCR optional)" at the next revision |
| Completeness guard: a second, code-driven orchestration path (`finalize_check`) that runs tool steps the agent skipped | FR-048 and SC-003 require every line to end `checked` or `failed` with a computed route; an LLM-driven tool loop cannot guarantee it called all four tools | Trusting the agent alone leaves lines `pending` on a skipped call; making the whole check a fixed code pipeline would remove the agent's tool-calling loop that the course requires. The guard is ~40 lines and reuses the tool functions |
