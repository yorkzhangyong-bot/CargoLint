# CargoLint: Technical Overview for the Project Review

**Project**: CargoLint, a linter for packing lists · **Course**: Turing College, AI Engineering, Sprint 2 "Building Applications with AI" · **Author**: Yong Zhang · **State on 2026-10-15**: MVP complete, all 72 planned tasks done, 231 offline tests passing, pushed to `main`.

This document explains what was built, how it is designed, the technical details behind each part, and how the implementation maps to the Sprint 2 requirements. Sections 9 and 10 are a review checklist: the questions a reviewer is likely to ask, with the answers and the evidence. Pointers into the repository are given as `path:function` so each claim can be checked.

---

## 1. What CargoLint does

A customs clerk at a Hamburg freight forwarder files ICS2 entry summary declarations (ENS) for China to EU sea freight. The packing lists from Chinese shippers are full of descriptions such as 配件 / Parts, 礼品 / Gift or 电子产品 / Electronic products. The EU lists exactly these terms as unacceptable, and a declaration carrying them is rejected or held.

CargoLint takes the packing list (XLSX, CSV, PDF or photo, or lines pasted into a chat) and, for every line:

1. **flags** the description as OK, Vague or Stop-word, citing the rule that matched;
2. **suggests** the top-3 HS-6 subheadings with a confidence, a short reasoning, the sources it relied on and a Binding Tariff Information (BTI) ruling as precedent where one exists;
3. **routes** the line to auto-accept, human review or ask the shipper, by a rule in code against a threshold the clerk controls.

The clerk works a review list with a detail card, accepts lines and chooses the decided code, asks follow-up questions about any line, pastes the shipper's reply to re-check one line, and exports CSV/JSON. Tokens and cost per shipment are shown in the sidebar.

CargoLint advises; the clerk decides. Nothing is ever sent to a shipper or to a customs system.

---

## 2. Architecture

### 2.1 Layers and the dependency rule

```
 Streamlit UI            app.py, ui/ (sidebar, upload, chat, jobs, replies, review, detail)
      │   settings as parameters; reads lines, routes, counts from the store
      ▼
 agent/                  agent.py (LangChain agent, callbacks, completeness guard)
                         prompts.py (system prompt, fence(), context block)
                         routing.py (route_line, can_accept, is_contradiction, validate_code)
                         store.py (LineStore: shipment, lines, versions, decisions, audit, usage, export)
                         llm.py (the single OpenRouter client factory: chat model, structured calls, retries, cost)
      │   five tools, called with references (line numbers, file ref, reply ref)
      ▼
 tools/                  parse_packing_list, check_description, classify_hs6, lookup_precedent, apply_shipper_reply
                         parsers.py (XLSX/CSV/PDF, header detection, ZH/EN split, caps), ocr.py (RapidOCR)
      │
      ▼
 rag/ + data/ + store/   loader.py (CLI), nomenclature.py (SKOS → HS-6 chunks), bti.py (EBTI extract),
                         rules.py (ICS2 PDFs → term lists), embeddings.py, retriever.py (BM25 + Chroma + RRF),
                         translate.py (ZH→EN query expansion)
                         data/ processed JSONL and rule lists · store/ Chroma, BM25 pickle, BTI document store

 External service: OpenRouter only (chat model openai/gpt-4o-mini, embeddings qwen/qwen3-embedding-8b).
```

Dependencies point one way: `app.py`/`ui/` → `agent/` → `tools/` → `rag/`. Nothing under `agent/`, `tools/` or `rag/` imports Streamlit, so the whole domain is importable and testable without a browser session. Two chokepoints enforce the invariants:

- `agent/llm.py` is the only place that creates model or embedding clients. Retries, usage capture, cost and the test stubs live there.
- `agent/store.py` (`LineStore`) is the only module that reads or writes line data. The session-state backing can be swapped for SQLite later without touching tools or UI.

Code size: `agent/` 1,700 lines, `tools/` 1,150, `rag/` 1,430, `ui/` 1,025, `tests/` 2,900.

### 2.2 The two screens

**Start screen**: a grouped sidebar (uploader with 20 MB limit; shipment reference, shipper, filing type; threshold slider 60 to 99, default 85; hybrid-search switch; knowledge-base caption; tokens, cost and export) and a welcome message with three quick actions (try one description, use the 12-line sample, which terms does customs reject) plus a "What I can and cannot do" panel.

**After a check**: the assistant rail on the left (32 %) with the chat box, live progress, routing metrics, the lines that need action and what to ask, sources and retrieval steps; the review column on the right (68 %) with filter pills, the row list (needs-action first, 25 per page) and the detail card for the selected line (top-3 candidates with BTI popovers, route pills, the Accept popover with the decided-code control, why the line was flagged, how to update it).

Native Streamlit only: no custom HTML, CSS or JavaScript. Theme in `.streamlit/config.toml`.

### 2.3 Runtime flow of a check

```
clerk uploads a file ──► ui/upload.begin(): new_shipment(), register_file() → file_ref, pending check
chat: "Check the packing list." ──► ui/jobs.start(): worker thread runs agent.run_turn()
run_turn():
   build_context() from the store + code-built request "FILE REFERENCE: f1 (pass it to parse_packing_list)"
   create_agent(ChatOpenAI via OpenRouter, five tools, SYSTEM_PROMPT).invoke(...)
      model → parse_packing_list(file_ref)      lines v1 land in the store (status pending)
      model → check_description(all_pending)    flag + rule per line         ── UI: rows fill in live
      model → classify_hs6(all_pending)         translate → retrieve → rank → validate codes
      model → lookup_precedent(all_pending)     current BTI rulings per candidate code
   _finalize(): runs any step the model skipped ("run by the app"), fails what is still pending
   store.route_line() per line (deterministic) → counts
TurnResult(text, check_run, counts, usage) ──► ui/chat._finish_job(): assistant message with
   counts, needs-action list, line cards, sources, retrieval trace; the model's prose collapsed
```

The UI thread only polls. The worker never calls Streamlit; every number on screen is read from the store.

### 2.4 Data model (the core entities)

All entities are Pydantic v2 models in `agent/schemas.py`:

| Entity | Holds |
|---|---|
| `Shipment` | reference, shipper, threshold, hybrid flag, source file, usage totals, `lines`, append-only `audit`, `check_runs` |
| `Line` | `line_no`, qty / weight / value as filed, `versions` (append-only), derived `current` and `ever_flagged` |
| `LineVersion` | text_zh / text_en, `flag`, up to 3 `candidates`, `retrieval_trace`, `sources`, `status` (pending / checked / failed), `computed_route` + reason, the clerk's `decision`, contradiction note, reply text and `extracted` facts for v2+ |
| `Flag` | kind (ok / vague / stop_word), rule source, matched term, reason, `ask_for`, `pure_stop_word` |
| `Candidate` | code (validated), subheading text from the index, confidence 0 to 100, rationale, `history_only`, precedent |
| `Decision` | route (accepted / review / ask_shipper), decided code, how it was chosen, timestamp |
| `DecisionRecord` | one audit entry per mutation: what changed, previous and new value, actor (routing rule, threshold change, clerk, shipper reply, system) |
| `Usage` | tokens, calls, cost in USD and EUR, summed per shipment |

Full field tables: `specs/001-packing-list-check/data-model.md`.

---

## 3. Design decisions and why

| Decision | Why | Trade-off accepted |
|---|---|---|
| **Guardrails live in code, not in the prompt** (routing, threshold, accept lock, code existence, schema validation) | Prompts are not enforceable controls, and a packing list can contain text written to subvert them. Only code gives a guarantee a test can verify. | The model's role is narrower: it classifies and explains, it never decides. |
| **Untrusted input end to end**: every description, OCR text and shipper reply is fenced as `<data line="N">…</data>`; tools take references, not text | The shipper writes the document the system reads. The model should never see untrusted text as instruction, and never re-type it into tool arguments. | A fencing step at every model-call site, enforced by a static test. |
| **One chunk per HS-6 subheading** with chapter / heading metadata | Mirrors how the nomenclature is organised; the subheading is exactly the thing being suggested. CN-8 lines are folded into their HS-6 chunk. | 5,612 chunks instead of the 10k first estimated; no CN-8 suggestions (out of scope anyway). |
| **Hybrid retrieval** (BM25 + vectors, reciprocal rank fusion) with a vector-only baseline switch | HS code numbers and exact product terms retrieve poorly with vectors alone. Measured: hybrid wins the exact-term lines. | Two indexes to build and keep in sync; the index metadata guard refuses mismatched embedding models. |
| **Exactly five single-purpose, schema-typed tools**, batched over line numbers | Testable without a model or Streamlit; a 12-line check is 4 tool calls, not 40. | A second orchestration path (the completeness guard) is needed because an LLM loop cannot guarantee it called every tool. |
| **Completeness guard** in code after every check | Every line must end checked or failed with a computed route, even when the model skips a step. | Steps run by the app are labelled "(run by the app)" in the progress block, which is honest but visible. |
| **Append-only versions and audit log** | A customs auditor can follow what changed, when, and why. Replies create v2, v3, … | No delete; "withdrawn" would be a new version state (roadmap). |
| **Background worker thread + Streamlit fragments** for the UI | A check takes 20 to 130 s; the page must stay live and show each tool step and each row as it fills. | Streamlit-specific threading care: the worker never touches Streamlit; the UI polls a job object. |
| **Row list instead of `st.dataframe`** | Fixed-pixel dataframe columns clipped Confidence and Route at laptop widths; proportional columns wrap. | Sorting and search are lost; filters, needs-action-first order and paging cover up to 200 lines. |
| **Session-state line store** behind one module | Enough for one user and one shipment in the MVP; the interface is the only contract. | Nothing persists across restarts (named weakness). |
| **Spec-driven build** with GitHub Spec Kit (constitution → spec → clarify → plan → tasks → analyze → implement) | The guardrails are requirements, so they were written down and tested before the code; the analyze step catches constitution conflicts. | More documents to keep in sync (constitution, spec, plan, contracts, research). |

---

## 4. Technical details by subsystem

### 4.1 Knowledge base (`rag/loader.py`, `rag/nomenclature.py`, `rag/bti.py`, `rag/rules.py`)

`python -m rag.loader --demo` downloads, parses, chunks, embeds and persists everything, and writes `data/SOURCES.md` with URL, version, retrieval date and licence per dataset.

| Dataset | Source | Processing | Result |
|---|---|---|---|
| EU Combined Nomenclature 2026 (= HS 2022 six-digit structure + EU eight-digit codes) | Publications Office SKOS RDF/XML, 167 MB, CC BY 4.0 | streamed with `lxml.iterparse`; one chunk per HS-6 = chapter title + heading text + subheading text + self-explanatory notes + its CN-8 lines; metadata chapter, heading, subheading, language, source, edition year | 5,612 chunks (`data/nomenclature_2026.jsonl`, committed) |
| EBTI rulings | official full extract, 397 MB, 23 yearly CSVs | rows with valid status, validity end ≥ today, chapters 39, 42, 61–64, 73, 84, 85, 94, 95, 96; HS-6 derived from the first six digits; `NAME_AND_ADDRESS` dropped at load | demo subset 192 rulings (committed); full subset 73,899 rulings as a loader option |
| ICS2 guidance on acceptable goods descriptions v4.10, and the ICS2 stop-word list (CIRCABC, in force 2026-08-03) | official PDFs | tables extracted with pdfplumber into JSON term lists | roughly 480 terms across the two lists |
| Firm stop-word list, shipper history, sample packing list | hand-written synthetic demo data | | 32 terms; 3 shippers with past codes; 12 sample lines |

Embeddings: `qwen/qwen3-embedding-8b` through OpenRouter (4,096 dimensions, native Chinese and English), via a small `langchain_core.embeddings.Embeddings` subclass that batches inputs and records usage. Vectors persist in Chroma (`store/chroma`, cosine space); the BM25 index is a pickle; the model name and dimension are written to `store/index_meta.json`, and the retriever refuses to open an index built with a different model.

### 4.2 Retrieval (`rag/retriever.py`, `rag/translate.py`)

Per line, in this order:

1. **Query translation and expansion** (`translate_and_expand`): one structured call turns the Chinese or mixed description into a literal English translation plus up to four expansions (synonyms, product category, material) and an optional HyDE-style sentence written in the style of a subheading. English-only text skips the call. Results are cached per description.
2. **Embedding**: all queries of a line are embedded in one request and reused.
3. **Hybrid search** (`HybridRetriever.search`): for each query, cosine search in Chroma (top 2k) and BM25 over `rank_bm25` (top 4k, filtered to 2k). The BM25 tokenizer keeps HS codes in both `9617.00` and `961700` forms and treats CJK runs as tokens. All rankings are fused with **reciprocal rank fusion** (k = 60) and the top k = 6 chunks are kept, each tagged with its vector and BM25 ranks for the trace.
4. **Shipper history boost**: when the shipper has past filings, a second search restricted to those chapters is fused in as a soft boost, and the past codes' own chunks are added, marked "(filed before by this shipper)". The trace shows this as the metadata filter with its reason.
5. **Vector-only baseline**: the sidebar switch sets `mode="vector_only"`, which skips BM25 and fusion. This is the comparison baseline required by the course.

Every classification stores a `RetrievalTrace` (original text, queries, filter, BM25 hits, vector hits, fused count, chunks sent to the model, mode) which the UI shows in the Retrieval-steps expander.

### 4.3 Classification (`tools/classify_hs6.py`)

The fused chunks, the fenced description, the flag result, any facts confirmed by the shipper and the shipper's past codes go to the chat model with a strict JSON schema: up to three `{code, confidence, rationale, history_only}`. Then, in code:

- `validate_classification` re-validates the output with Pydantic (unknown fields dropped, confidence must be an integer 0 to 100).
- `validate_code` drops any code that is not `####.##` **or not present in the nomenclature index**. Subheading text and chapter come from the index, never from the model. If nothing survives, the line is "no valid candidate".
- A vague-flagged line's confidence is capped at 59 in code, so a generic description can never look near-certain whatever the model says.
- `history_only` candidates are labelled and a "Shipper's past filings" source is added, so the UI can say the support came from history, not from the text.

### 4.4 Description check (`tools/check_description.py`, `rag/rules.py`)

Deterministic rules first, model judgement second:

1. a firm stop-word match → **Stop-word**, citing the term;
2. a match in either ICS2 list → **Vague**, citing the document and term;
3. otherwise one structured judgement call (`{vague, missing: [material | product_name | use], reason}`) → **Vague** or **OK**.

Matches are whole-word for English and substring on CJK runs for Chinese. `is_pure_stop_word` detects descriptions with no product information left after removing the stop-word term (for example "Gift"), which then get no candidates at all. Every flag carries `ask_for`, the information the clerk should request from the shipper.

### 4.5 Routing and the accept lock (`agent/routing.py`, `agent/store.py`)

`route_line(flag, top_confidence, status, ever_flagged, threshold, ask_floor)` is a pure function:

| Flag | Confidence | Route |
|---|---|---|
| stop-word | any | ask the shipper |
| vague | below the ask floor (50) or no candidate | ask the shipper |
| vague | at or above the ask floor | human review |
| OK | at or above the threshold, never flagged | auto-accept |
| OK | at or above the threshold, but flagged or updated before | human review, shown as "ready to accept" |
| OK | below the threshold, or no valid candidate | human review |
| any | failed or still pending | human review |

The threshold is 60 to 99 (default 85); moving the slider recomputes undecided lines instantly with no model call and writes audit entries. The clerk's choice (`Decision`) overrides the computed route; `LineStore.set_decision` refuses `accepted` while the current flag is not OK (`LockedError`) and refuses a typed code that fails `validate_code` (`UnknownCodeError`). A line that was ever flagged, or updated by a reply, is never auto-accepted again: it needs the clerk's click.

### 4.6 The agent loop (`agent/agent.py`, `agent/prompts.py`)

- LangChain v1 `create_agent` with `ChatOpenAI` pointed at OpenRouter and the five tools; up to 8 tool calls per clerk message.
- For every message the app builds a **context block** from the store (counts, the lines needing action, the selected line in full and, when the question is about terms, the rule lists with their source) and a short code-built request such as `Check lines 1–3`, `FILE REFERENCE: f1` or `Apply reply r1 to line 1`. Pasted descriptions and replies never enter the agent's message history; only references and code-built summaries do.
- The system prompt fixes the tool order for a check, declares fenced blocks to be third-party data, forbids stating any route, count or code that is not in a tool result, and requires that every flagged line names what to ask the shipper. It also tells the model that confidence is an estimate.
- Tool start / end / error callbacks (`ProgressCallbackHandler`) feed the live progress block; `UsageMetadataCallbackHandler` collects tokens per call, which `agent/llm.py` turns into cost.
- After a check request, the **completeness guard** (`_finalize`) runs `check_description`, `classify_hs6` and `lookup_precedent` directly for any line the model left behind, then fails whatever is still pending. In practice `gpt-4o-mini` sometimes skips `lookup_precedent`; the guard makes the result complete and the step is shown as "run by the app".

### 4.7 Shipper replies (`tools/apply_shipper_reply.py`, `ui/replies.py`)

The target line is the line number named in the clerk's message, else the line selected in the review list (the app then says which line it used), else the app asks. The reply is stored as data (`register_reply`), one structured call extracts `{material, part_name, use}` from the fenced text, a new `LineVersion` is appended, and check, classify and precedent run **for that line only**. A fixed chapter rule flags contradictions: if the new top candidate's chapter is not among the previous version's candidate chapters, the version gets a note naming both codes and goes to review. A reply to an accepted line clears the decision.

### 4.8 Parsing and OCR (`tools/parsers.py`, `tools/ocr.py`, `tools/parse_packing_list.py`)

XLSX and CSV are read with pandas (all sheets, CSV tried as UTF-8 then GBK). The header row is the first row with at least two matches from a bilingual alias table (description / 品名 / 货物描述, qty / 数量, weight / 毛重, cbm / 体积, value / 金额). Total rows and empty descriptions are skipped. Mixed cells are split on `/`, newline, parentheses or the CJK-to-Latin boundary. The shipper is detected by alias match in the first 15 rows. PDF pages with fewer than 20 extractable characters are rendered at 200 dpi and passed to RapidOCR (Chinese + English, pip-only, no system binary); lines whose mean OCR score is below 0.6 are marked unreadable and routed to review rather than guessed. All caps (20 MB, 200 lines, 300 characters per description, 50 pasted lines) are enforced before any model call. Workbooks open data-only, `.xlsm` is rejected, no link inside a file is followed.

### 4.9 Security measures

- **Fencing**: `fence()` wraps untrusted text in `<data line="N">…</data>` and neutralises angle brackets inside, so text can never close the block early. Every model-call site (`check_description`, `classify_hs6`, `apply_shipper_reply`, `translate`) fences its input; `tests/adversarial/test_fencing_coverage.py` checks this statically with the `ast` module and also asserts that only documented hosts appear in the code.
- **Schema validation** of every structured output with Pydantic, two retries that feed the validation error back, then the line fails. Invalid output is never passed through.
- **Code existence** for every suggested and every typed code; the **accept lock** while a line is flagged; **routing and the threshold in code**.
- **Caps** before any model call; **secrets** from the environment only (`OPENROUTER_API_KEY`), never from the UI, never logged; shipper contact details dropped from the BTI data; nothing is sent anywhere except OpenRouter.
- **Adversarial tests**: 12 injection fixtures (descriptions that order the model to ignore its rules, auto-accept the line, or change other lines) run through the tools; none changes a flag, candidate or route of any other line (SC-007).
- Residual risk, stated in the README: the clerk's own typed message is trusted as an instruction.

### 4.10 Cost and usage (`agent/llm.py`)

Every chat and embedding call records tokens through the single client factory. Cost = tokens × `data/model_prices.json` (USD per million tokens, with an `as_of` date, refreshable from the OpenRouter models endpoint) × the configured USD/EUR rate. Totals are stored on the shipment and shown as two sidebar metrics. The live test reconciles the computed cost against OpenRouter's own accounting for one call.

### 4.11 Error handling

| Scenario | Behaviour | Test |
|---|---|---|
| Scanned PDF or photo with poor OCR | unreadable lines routed to review, never guessed | `tests/integration/test_error_scenarios.py` |
| Mixed-language cells | split on `/`, newline, parentheses or the CJK boundary | `tests/unit/test_parsers.py` |
| Model suggests a code that does not exist | dropped by the existence check; "no valid candidate" if none survives | `tests/integration/test_classify_hs6.py` |
| Model returns the wrong schema | two retries with feedback, then the line fails with the reason | `tests/integration/test_classify_hs6.py` |
| Shipper reply contradicts the file | new version routed to review with a note naming both codes | `tests/unit/test_apply_reply.py` |
| API failure or rate limit | SDK retries with back-off; HTTP 402 (no credits) is not retried; only that line fails | `test_error_scenarios.py`, `test_check_description.py` |
| Unsupported, oversize, empty or header-less file | rejected before processing with a message naming the limit | `test_parsers.py`, `test_parse_packing_list.py` |
| Agent skips a tool | completeness guard runs the missing step | `tests/integration/test_agent_check_flow.py` |

A failure on one line never aborts the shipment; the line is surfaced as needing action with the reason.

### 4.12 The UI (`app.py`, `ui/`)

Streamlit 1.65, native widgets only. Each turn runs in a worker thread (`ui/jobs.py`); a `@st.fragment(run_every=0.7)` polls the job and renders an `st.status` with one line per finished tool and a "n / N lines classified" bar; the review list re-renders every second while a turn runs and appears as soon as the parse step adds lines. Chips are Streamlit badge directives; confidence is `st.progress` with the code in its label; the Accept control is a popover with a radio over the top-3 plus an "Other HS-6 code" input validated against the nomenclature; route pills are keyed by line, version and current route so a threshold change never silently becomes a clerk decision. Every route, count and code on screen is read from the store, never from model prose. The element-by-element contract is `specs/001-packing-list-check/contracts/ui.md`.

---

## 5. Testing and evaluation

### 5.1 Test suite

| Marker | Count | What it covers | Needs a key |
|---|---|---|---|
| unit | 170 | routing table and threshold boundary, accept lock, code validation, fencing, parsers and caps, rule matching, RRF, BTI validity filter, line store and audit, reply scope, cost arithmetic, export, review-table rows | no |
| integration | 40 | each tool with the fake client, the agent loop with a fake model, the completeness guard, the upload flow, follow-ups, the named error scenarios | no |
| adversarial | 21 | 12 injection fixtures through the tools; static fencing-coverage and host checks | no |
| live | 4 | OpenRouter embeddings, structured output, cost reconciliation, the budget test | yes |

`pytest -q` runs the 231 offline tests in about 3 seconds. Model calls are replaced by a fake structured-output backend that replays recorded outputs (`tests/fixtures/recorded/`); embeddings by a deterministic fake. Guardrail tests were written before the code they cover (constitution Principle VII).

### 5.2 Measured results

Labelled set: 20 lines (5 vague, 3 stop-word, 12 clear with known codes), `python tests/eval/run_eval.py`, 2026-10-14, `openai/gpt-4o-mini` + `qwen/qwen3-embedding-8b`:

| Mode | Flag accuracy | Top-1 | Top-3 | Flagged lines auto-accepted | Time |
|---|---|---|---|---|---|
| Hybrid (BM25 + vectors, RRF) | 20 / 20 | 10 / 12 | 11 / 12 | 0 | 87 s |
| Vector-only baseline | 20 / 20 | 9 / 12 | 10 / 12 | 0 | 65 s |

Hybrid wins the exact-term lines, for example `7318.15` stainless steel hexagon bolts, which vector-only puts at `7318.19`. Both modes miss silicone phone cases (`3923.10` packaging cases instead of `3926.90`). The whole evaluation cost €0.016.

Retrieval alone (`python tests/eval/ragas_eval.py`, RAGAs-style context metrics against the reference chunk, k = 6, 12 clear lines): context recall 92 % in both modes, context precision (MRR) 0.81 hybrid / 0.82 vector-only, chapter hit 100 %. The phone-case miss is a retrieval miss (the right chunk is never among the six), so the fix is better query expansion, not better ranking.

Scale (`python tests/eval/scale_check.py`, 100 generated lines, 6 workers): first progress step after 1.6 s, all 100 lines checked in 130 s, none failed, €0.05; a 201-line file is rejected before any model call.

Budget (`pytest -m live`): the 12-line sample plus two follow-up questions = 40.6k tokens, 36 calls, €0.007. In the current UI the 12-line sample checks in 20 to 40 s.

The spec's eleven success criteria: SC-001, 002, 003, 005, 007, 010 and 011 are evidenced by the numbers above; SC-004 (every displayed and decided code exists), SC-008 (every flagged line names what to ask) and SC-009 (a reply changes exactly one line) are covered by unit and integration tests; SC-006 (a new clerk finds the needs-action lines within two minutes) is a manual check of the sample run.

---

## 6. Mapping to the Sprint 2 requirements

### 6.1 Core requirements

| Requirement | Implementation | Evidence |
|---|---|---|
| Knowledge base relevant to the domain | EU Combined Nomenclature 2026 (5,612 HS-6 chunks), EBTI rulings (192 demo, 73,899 full option), the two ICS2 term lists, a firm stop-word list, synthetic shipper history; `rag/loader.py` builds it from the official sources and writes `data/SOURCES.md` | `python -m rag.loader --demo`; `tests/unit/test_loader.py`; knowledge-base caption in the sidebar |
| Standard retrieval: embeddings, chunking, similarity search | one chunk per subheading with metadata (`rag/nomenclature.py:build_chunks`); `qwen/qwen3-embedding-8b` vectors in Chroma, cosine similarity (`rag/retriever.py:ChromaVectorSearch`) | `tests/unit/test_retriever.py`; retrieval-only recall 92 % |
| Advanced RAG: query translation and structured retrieval | ZH→EN translation with multi-query expansion and HyDE (`rag/translate.py`); chapter metadata filter used as the shipper-history boost; per-line retrieval trace | Retrieval-steps expander in the UI; `tests/integration/test_classify_hs6.py` |
| At least 3 domain tools | 5 tools: `parse_packing_list`, `check_description`, `classify_hs6`, `lookup_precedent`, `apply_shipper_reply`, each with a Pydantic args schema, taking references | `tools/`; `tests/integration/test_agent_check_flow.py` shows the loop calling them in order |
| Domain-specific prompts, responses and security | customs-clerk system prompt (`agent/prompts.py:SYSTEM_PROMPT`); ranking, judgement, translation and extraction prompts with examples; fenced data blocks; schema-validated outputs; routing in code | `tests/adversarial/`; section 4.9 |
| LangChain with OpenRouter | LangChain 1.4 `create_agent`; `ChatOpenAI` with the OpenRouter base URL; embeddings through the OpenRouter embeddings endpoint; one client factory (`agent/llm.py`) | `tests/live/test_openrouter.py` |
| Error handling and input validation | file type / size / row / description caps; per-line isolation with bounded retries; schema retries; unreadable OCR; completeness guard; 402 handled explicitly | section 4.11 table, 8 scenarios with tests |
| Intuitive UI showing context, sources, tool results and progress | `st.chat_message` rail with `st.status` per tool, routing `st.metric`s, Sources and Retrieval-steps expanders; review list and detail card from the store; tokens and cost; CSV / JSON export | `ui/`; `specs/001-packing-list-check/contracts/ui.md` |

### 6.2 Optional tasks

| Task | Level | Implementation | Evidence |
|---|---|---|---|
| Protect the app against prompt injection | medium | fencing at every model-call site, references instead of text in tool arguments, pasted text kept out of the agent history, schema validation, routing in code | 12 adversarial fixtures and the static fencing-coverage test, all passing (SC-007) |
| Calculate and display token usage and cost | medium | usage captured per call, priced from `data/model_prices.json`, converted to EUR, shown as sidebar metrics and included in the JSON export | live reconciliation test; €0.007 for the sample plus two follow-ups |
| Hybrid search | hard | BM25 + vector search fused by reciprocal rank fusion, with a vector-only baseline switch and a measured comparison | hybrid top-1 10/12 vs vector-only 9/12 |
| Multi-language support | bonus, inherent | Chinese, English and mixed input; ZH→EN query translation; bilingual header detection; rule terms in both languages; Chinese glyphs rendered | sample list and labelled set are bilingual |
| RAG evaluation with RAGAs | stretch | `tests/eval/ragas_eval.py` computes the RAGAs context-recall and context-precision ideas deterministically against ground-truth chunk ids. The `ragas` library itself is not used (no LLM judge). | retrieval results table above |
| Source citations | easy | every candidate carries source ids; Sources expander grouped by kind (nomenclature, BTI, ICS2 rule, firm rule, shipper history) | FR-029 |
| Visualisation of the RAG process | easy | Retrieval-steps expander: original text → queries → filter → BM25 and vector hits → fused → sent to the model | FR-031 |
| Export | easy | results export to CSV (UTF-8 with BOM for Excel) and JSON. Note: this is the results export, not a chat transcript export | `tests/unit/test_export.py` |

### 6.3 Evaluation criteria the course names

| Criterion | Where to point |
|---|---|
| Explain how RAG works in this pipeline | section 4.2 and 4.3: translation → hybrid retrieval → RRF → ranking → validation; README "How RAG works in this pipeline" |
| Explain the tool-calling loop | section 4.6 and 2.3; `agent/agent.py:run_turn` |
| Clean code organisation | section 2.1: one-way dependencies, two chokepoints, domain importable without Streamlit; `plan.md` project structure |
| Name the error scenarios | section 4.11 |
| Honest list of weaknesses and improvements | section 8 |

---

## 7. How it was built

GitHub Spec Kit, in this order, all artefacts in the repository:

1. **Constitution** (`.specify/memory/constitution.md`, v1.0.0, 2026-10-14): seven principles, five of them non-negotiable for guardrail code; scope, architecture invariants, stack, UI design contract, definition of done.
2. **Specification** (`specs/001-packing-list-check/spec.md`): four user stories by priority (check pasted lines; upload and review; follow-ups and shipper reply; export and cost), 50 functional requirements, 11 measurable success criteria.
3. **Clarify**: four decisions recorded in the spec: the clerk chooses the decided code on accept; a confidence floor of 50 separates "ask the shipper" from "review" for vague lines; 200 lines per shipment with 100 lines in 5 minutes; how a reply's target line is resolved.
4. **Plan** (`plan.md`, `research.md`, `data-model.md`, `contracts/`): 17 research entries with verified versions and sources; a Constitution Check gate per principle; two recorded deviations (RapidOCR instead of Tesseract/PaddleOCR; the completeness guard).
5. **Tasks**: 72 tasks in the intro's build order (labelled set → loader → classify measured on the set → check, routing, precedent → UI → parsers and replies → security pass, cost, export, README, tests). All done.
6. **Analyze** before implementation: consistency check across spec, plan and tasks.
7. **Implement**, then a live-run polish round, a performance round (query embeddings batched: the 100-line check went from 484 s to 130 s) and a UI redesign round driven by the first real use (row list, live progress, grouped sidebar).

Commits on `main`: foundation → tools, agent, knowledge base, chat → replies, follow-ups, cost, export → polish, error-scenario and security tests → performance and evaluation → UI redesign → project CLAUDE.md → uv lock.

---

## 8. Known weaknesses, deviations and next steps

**Weaknesses (also in the README):**

- Confidence is model-estimated and only loosely calibrated against 20 labelled lines; it must not be read as a probability. The UI says so.
- Chinese product slang and brand-only names still miss; hybrid retrieval helps but does not solve it.
- Classification confusions remain where the nomenclature itself is subtle (protective phone cases vs packaging cases; aluminium bicycle frames landed in aluminium structures in one live run), and the model occasionally auto-accepts such a wrong code at high confidence. This is why the threshold is adjustable and the audit trail exists.
- `gpt-4o-mini` sometimes skips `lookup_precedent`; the guard covers it, visibly.
- BTI coverage: the demo subset is 192 German-language rulings for the ten target chapters; the full subset is a loader option. Rulings expire and must be refreshed.
- OCR on phone photos is the weakest input path; quantities and values are not read from photos.
- State lives in the Streamlit session: nothing persists across restarts; one user, one shipment.
- The chat box classifies a message by heuristics; a plain sentence without a question marker is treated as a new line after a check (a known rough edge, not yet changed).

**Deviations from the original plan, all recorded:**

- RapidOCR instead of Tesseract or PaddleOCR (pip-only, Chinese by default); the constitution text still names the old engines and needs a patch.
- The review table is a row list rather than the `st.dataframe` the constitution names, because the dataframe clipped at laptop widths; recorded in `research.md` R-08 and the UI contract.
- 5,612 chunks instead of the 10,000 estimated: CN-8 lines are folded into their HS-6 chunk.
- Python 3.11 to 3.13 (the plan said up to 3.12); 3.13 is what runs the tests.
- The "Stop-word" chip means the firm list; the ICS2 stop-word list feeds the Vague flag, as the spec defines. Customs itself calls the ICS2 list "stop words", so the label may deserve a rename.

**Next steps, in order of customer value:** drafted bilingual shipper queries with send tracking; line version history and audit export; CN-8 classification (same pipeline, one more level); TARIC-10 lookup as a deterministic tool (duty rate, anti-dumping, certificates); SQLite persistence and multi-user access. Technical debt first: the constitution patch, the chat-message classification, and a withdrawn-line state if deleting lines is wanted.

---

## 9. Likely review questions and the answers

**Why does the model not decide the route?** Because a route is a control, and a packing list can contain text aimed at the model. `route_line` is a pure function with a test per row of its table; the model only supplies a confidence, which is itself capped in code for vague lines.

**What stops prompt injection?** Four layers: untrusted text reaches the model only inside fenced data blocks under a prompt that voids instructions in them; tools take line numbers, not text, so the model never re-types or alters descriptions; every structured output is re-validated and every code must exist in the nomenclature; routing and the accept lock run in code. Twelve adversarial fixtures and a static test that every model-call site fences prove it.

**What if the model returns a code that does not exist?** It is dropped before display. If no candidate survives, the line is "no valid candidate" and goes to review. The same check runs on codes the clerk types.

**Why hybrid retrieval, and did it help?** HS codes and exact product terms are poor vector queries. On the labelled set hybrid scores 10/12 top-1 against 9/12 for vector-only, winning exactly the exact-term lines. Retrieval-only recall is the same (92 %), so the gain is in ranking the right chunk higher.

**How is a 12-line check only four tool calls?** The tools are batched over line numbers and process lines in a thread pool with per-line isolation. One failed line never aborts the shipment.

**What happens when the model skips a step?** The completeness guard runs it in code and labels it "run by the app". Every line ends checked or failed with a computed route; this is tested.

**How do you know the quality?** A 20-line labelled set built before the classifier, run in both retrieval modes; a retrieval-only evaluation with RAGAs-style metrics; a 100-line scale run; a live budget test. All numbers are in the README and in section 5.

**What does it cost?** About €0.007 for the sample shipment plus two follow-ups; €0.05 for 100 lines; the one-off knowledge-base embedding was about $0.02 for the demo subset. Cost is computed from a price table and reconciled against OpenRouter's accounting.

**Why Streamlit threads and fragments instead of a simple spinner?** A check takes 20 to 130 s; the clerk needs to see each tool step and each row fill in, and to keep the page responsive. The worker never calls Streamlit; the UI polls a job object.

**What would you do next with one more week?** Fix the chat-message classification, add the withdrawn-line state, run the full BTI subset, and calibrate confidence against a larger labelled set.

---

## 10. Five-minute demo script

1. Start screen: point out the sidebar groups, the threshold, the hybrid switch and the knowledge-base caption. Click "Use the sample packing list".
2. While it runs: show the live status (tool by tool), the review list filling in, the "n / 12 lines classified" bar.
3. After the check: the routing metrics, the lines that need action with what to ask, the Sources and Retrieval-steps expanders for line 1.
4. Open line 1 (配件 / Parts): the Vague chip with the ICS2 rule, the capped confidence, the locked Accept control with its reason.
5. Move the threshold slider: routes change instantly, no model call, no decision created.
6. Paste a shipper reply for line 1 ("line 1 is steel bobbin cases for industrial sewing machines"): only line 1 re-checks, v2 appears with the extracted material, part and use, the line becomes "ready to accept" and needs a click.
7. Accept a line via the popover; show the decided-code radio and the typed-code validation.
8. Export CSV and JSON; show the tokens and cost in the sidebar.
9. Ask "Which terms does customs reject?" to show the rule lists with their sources.

---

## 11. Where to look

| Topic | Files |
|---|---|
| Binding rules | `.specify/memory/constitution.md` |
| Requirements and success criteria | `specs/001-packing-list-check/spec.md` |
| Plan, research decisions, data model, contracts | `specs/001-packing-list-check/plan.md`, `research.md`, `data-model.md`, `contracts/tools.md`, `contracts/ui.md`, `contracts/export.md` |
| Agent, prompts, routing, store, client | `agent/agent.py`, `agent/prompts.py`, `agent/routing.py`, `agent/store.py`, `agent/llm.py` |
| Tools | `tools/*.py` |
| Knowledge base and retrieval | `rag/loader.py`, `rag/nomenclature.py`, `rag/bti.py`, `rag/rules.py`, `rag/retriever.py`, `rag/translate.py`, `rag/embeddings.py` |
| UI | `app.py`, `ui/*.py` |
| Tests and evaluation | `tests/unit`, `tests/integration`, `tests/adversarial`, `tests/live`, `tests/eval/run_eval.py`, `ragas_eval.py`, `scale_check.py` |
| Data provenance | `data/SOURCES.md` |
| Results and weaknesses | `README.md` |
