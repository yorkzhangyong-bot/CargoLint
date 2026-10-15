# Research: CargoLint MVP (Phase 0)

**Feature**: `001-packing-list-check` · **Date**: 2026-10-14 · **Plan**: [plan.md](plan.md)

Each entry resolves an unknown from the Technical Context or fixes a technology choice the
constitution leaves open. Facts were verified against vendor documentation and PyPI on
2026-10-14 by four research agents; URLs are listed per entry. Prices are USD per 1M tokens.

## R-01 Agent framework and structured output

- **Decision**: LangChain 1.4.5 — `from langchain.agents import create_agent` with
  `system_prompt`, tools defined with `from langchain.tools import tool` and
  `@tool(args_schema=<Pydantic model>)`. The agent's own replies are prose. Model calls *inside*
  tools (vagueness judgement, translation/expansion, candidate ranking, reply extraction) use
  `model.with_structured_output(Schema, method="json_schema")` with
  `extra_body={"provider": {"require_parameters": True}}`; every result is re-validated by the
  same Pydantic schema in code (FR-044) regardless of the provider's strictness.
  `CARGOLINT_STRUCTURED_METHOD=function_calling` is the fallback for models without native JSON
  schema. `parallel_tool_calls=False` so tool callbacks run in Streamlit's script thread.
- **Rationale**: `create_agent` replaced `langgraph.prebuilt.create_react_agent` in v1; the
  `langchain-classic` package holds the legacy chains and retrievers, which we do not need.
  Strict JSON schema is supported by the default model through OpenRouter; Pydantic
  re-validation keeps Principle I independent of provider behaviour.
- **Alternatives**: `ToolStrategy`/`ProviderStrategy` for a structured *agent* response (not
  needed — the agent writes prose; all structured data comes from tools); `langchain-openrouter`
  `ChatOpenRouter` (adds a dependency; no embeddings class).
- **Sources**: reference.langchain.com/python/langchain/agents/create_agent;
  docs.langchain.com/oss/python/langchain/structured-output; …/langchain/tools;
  …/releases/langchain-v1.

## R-02 Chat model and provider access

- **Decision**: `langchain-openai` 1.7.1 `ChatOpenAI(model=CARGOLINT_CHAT_MODEL,
  base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY,
  default_headers={"HTTP-Referer": …, "X-OpenRouter-Title": "CargoLint"}, stream_usage=True,
  use_responses_api=False, max_retries=3)`. Default model `openai/gpt-4o-mini` (0.15 in /
  0.60 out; supports `tools` and `structured_outputs`). Provider-specific options go in
  `extra_body`.
- **Rationale**: a 12-line shipment with two follow-ups is ~14k input + ~2.5k output tokens ≈
  $0.004–0.012, far under the €0.10 target (SC-010). `use_responses_api` and `stream_usage` must
  be set explicitly when `base_url` is not OpenAI.
- **Alternatives**: `google/gemini-2.5-flash-lite` (0.10/0.40), `deepseek/deepseek-v3.2`
  (0.26/0.80), `qwen/qwen3-235b-a22b-2507` (0.09/0.55) — all list both capabilities; switch by
  env var. Avoid `~latest` aliases for reproducibility.
- **Sources**: openrouter.ai/docs/features/structured-outputs; …/guides/features/tool-calling;
  …/features/provider-routing; reference.langchain.com/python/langchain-openai/chat_models/base/ChatOpenAI.

## R-03 Embeddings

- **Decision**: OpenRouter `POST /api/v1/embeddings` with `qwen/qwen3-embedding-8b` (0.01/1M,
  32k context, native Chinese/English). Implemented as a ~30-line
  `langchain_core.embeddings.Embeddings` subclass in `rag/embeddings.py` over the `openai` SDK so
  we can pass `input_type` (`search_document` for indexing, `search_query` for queries), pin
  `provider: {order: [...], allow_fallbacks: false}`, batch inputs, and read `usage.cost`. The
  model id and vector dimension are stored in the Chroma collection metadata; the retriever
  refuses to query a collection built with a different model.
- **Rationale**: ~5.6k nomenclature chunks + ≤ 50k ruling chunks × ~400 tokens ≈ 24M tokens ≈
  $0.25 one-off; query embeddings are negligible. A custom class avoids the
  `OpenAIEmbeddings` token-array default (`check_embedding_ctx_length=False` workaround) and a
  reported OpenRouter incompatibility (GH #35204).
- **Alternatives**: `OpenAIEmbeddings(model=…, base_url=…, check_embedding_ctx_length=False,
  encoding_format="float")` (documented for OpenRouter; smoke-test); `baai/bge-m3` on
  OpenRouter (0.01, 8k ctx); local `BAAI/bge-m3` via sentence-transformers (free, ~2 GB torch,
  CPU-minutes) behind the same interface as a later option.
- **Sources**: openrouter.ai/docs/api-reference/embeddings; …/api/api-reference/embeddings/
  submit-an-embedding-request; reference.langchain.com/python/langchain-openai/embeddings/base/OpenAIEmbeddings.

## R-04 Hybrid retrieval components

- **Decision**: own code in `rag/retriever.py`: `BM25Index` over `rank_bm25.BM25Okapi` 0.2.2
  (lower-case, split on non-alphanumerics, keep code tokens such as `9617.00` and `961700`),
  Chroma via `langchain-chroma` 1.1.0 / `chromadb` 1.5.9 persisted in `store/chroma` with
  `collection_metadata={"hnsw:space": "cosine"}`, and a ten-line `rrf(rankings, k=60)`.
  `HybridRetriever.search(queries, chapter_filter, mode)` returns fused chunks with per-source
  ranks for the retrieval trace. `mode="vector_only"` is the baseline for SC-011.
- **Rationale**: `langchain-community` (home of `BM25Retriever`) was sunset on 2026-05-22 and
  archived; `EnsembleRetriever` lives in `langchain-classic`. Both are ~50 lines of code we can
  own and unit-test, and the constitution names `rank_bm25` + RRF explicitly.
- **Alternatives**: `langchain_classic.retrievers.EnsembleRetriever` (RRF built in);
  `bm25s` 0.3.13 (faster, maintained); Chroma's own hybrid search.
- **Sources**: github.com/langchain-ai/langchain-community/issues/674;
  reference.langchain.com/python/langchain-classic/retrievers/ensemble/EnsembleRetriever;
  docs.langchain.com/oss/python/integrations/vectorstores/chroma.

## R-05 Per-tool progress and token capture

- **Decision**: a custom `BaseCallbackHandler` (`on_tool_start`, `on_tool_end`, `on_tool_error`)
  passed as `config={"callbacks": [progress, usage]}` to `agent.invoke(...)`, where `usage` is
  `langchain_core.callbacks.UsageMetadataCallbackHandler`. The progress handler writes to the
  `st.status(..., type="step")` object; per-line work inside batch tools runs in a thread pool
  but never touches Streamlit.
- **Rationale**: fires during a plain `invoke`, needs no graph-node parsing, and keeps UI calls on
  the script thread. Tokens per call come from `AIMessage.usage_metadata`; the handler
  aggregates per model.
- **Alternatives**: `agent.stream(inputs, stream_mode="updates", version="v2")` reading the
  `model` / `tools` node deltas; `agent.stream_events(version="v3")` (beta);
  `get_stream_writer()` for intra-tool progress.
- **Sources**: docs.langchain.com/oss/python/langchain/streaming; …/event-streaming;
  reference.langchain.com/python/langchain-core/callbacks/base/BaseCallbackHandler.

## R-06 Cost calculation

- **Decision**: cost = tokens × prices from `data/model_prices.json` (USD per 1M, with an
  `as_of` date, refreshed by `python -m agent.llm --refresh-prices` from
  `GET /api/v1/models` and `/api/v1/embeddings/models`), converted to EUR with
  `CARGOLINT_USD_EUR` (default 0.92). Embedding calls through the raw SDK also record the exact
  `usage.cost` returned by OpenRouter; the live test reconciles the computed total against
  `GET /api/v1/generation?id=` for one call.
- **Rationale**: OpenRouter always returns `usage.cost` (USD), but `ChatOpenAI` drops non-OpenAI
  fields; a price table makes cost computable offline and testable, and keeps a single code
  path for all calls.
- **Alternatives**: `ChatOpenRouter` from `langchain-openrouter` (may surface `cost`); a
  `/generation` lookup per call (one extra request each).
- **Sources**: openrouter.ai/docs/use-cases/usage-accounting; …/api-reference/get-a-generation;
  …/faq (credits are USD).

## R-07 Retries and error handling against OpenRouter

- **Decision**: SDK `max_retries=3` (exponential back-off honouring `Retry-After` for 429/5xx);
  explicit handling of HTTP 402 (credits exhausted → not retried, clear message), 403
  (moderation/budget), 502/503 (model or provider unavailable → retried then line failed), and
  SSE `finish_reason: "error"` on HTTP 200. Structured-output schema failures retry twice with
  the validation error fed back, then the line is failed (FR-044, FR-048, FR-049).
- **Rationale**: documented OpenRouter error codes; the SDK never retries 402.
- **Alternatives**: `models: [...]` fallback list for model outages (billed per model used);
  `provider.max_price` as a budget guard.
- **Sources**: openrouter.ai/docs/api-reference/errors; …/api-reference/limits.

## R-08 Streamlit APIs (1.65.0)

- **Decision**: pin `streamlit==1.65.0`. Review table: a **row list**, not `st.dataframe` — a
  header row of captions plus a bordered `st.container(height=420 when > 8 rows, gap=None,
  autoscroll=False)` holding one `st.columns([0.42, 3.3, 0.95, 1.5, 1.15, 0.5],
  vertical_alignment="center")` row per line: number, two-line zh / en description with qty,
  flag chip, `st.progress(conf, text="`code` · 95%")`, route chip, icon-only open button
  (`type="primary"` for the selected line). 25 rows per page (`st.segmented_control` pager).
  Chips are badge directives (`:orange-badge[Vague]`). Live updates: the agent turn runs in a
  worker thread (`ui/jobs.py`); the assistant rail polls it with `@st.fragment(run_every=0.7)`
  (object-form `st.status(...)`, never `with`, so leaving the block cannot flip it to
  "complete"), the row list re-renders with `@st.fragment(run_every=1.0)` while a turn runs, and
  the poll fragment calls `st.rerun()` when the turn finishes or when lines first appear (the
  two-column layout is decided on full runs only). Accept: `st.popover("Accept…", disabled=lock)`
  holding `st.radio` over the top-3 + "Other HS-6 code…" input + Confirm. Route: `st.pills`
  keyed by line, version **and current route** so a threshold change never turns a computed route
  into a decision. Filters: `st.segmented_control`; hybrid switch `st.toggle`; counts `st.metric`;
  export `st.download_button(on_click="ignore")`; chat `st.chat_message` / `st.chat_input`;
  `st.file_uploader(type=[…])` plus `[server] maxUploadSize = 20`. `width="stretch"` replaces
  the deprecated `use_container_width=True` everywhere.
- **Rationale**: `st.dataframe` columns are fixed pixels and never shrink, so at the 32 / 68
  split on a 1440 px laptop (≈ 700 px for the review column) the Confidence and Route columns
  clipped behind a horizontal scrollbar — the clerk's main complaint in the first live run.
  Proportional `st.columns` wrap text instead of clipping, allow real chips and a two-line
  description, and keep selection a plain button (no checkbox column). Sorting and search are
  lost; filters, needs-action-first ordering and paging cover the MVP (≤ 200 lines). Verified in
  a real browser at 1440 × 900: nothing clipped, 12 lines in 41 s with live rows.
- **Alternatives**: `st.dataframe` + `ProgressColumn` + `Styler.map` (the first implementation —
  clipped); `st.container(horizontal=True)` flex rows (less predictable widths); custom HTML
  table (ruled out by the constitution).
- **Sources**: docs.streamlit.io/develop/api-reference/layout/st.columns; …/layout/st.container;
  …/execution-flow/st.fragment; …/status/st.status; …/layout/st.popover; …/widgets/st.pills;
  …/text/st.badge; …/widgets/st.file_uploader; …/configuration/config.toml.

## R-09 Theme and Chinese rendering

- **Decision**: `.streamlit/config.toml` `[theme]`: `primaryColor = "#1D4FB8"`, light base,
  `baseFontSize = 14`, `baseRadius = "medium"`, `borderColor = "#E6E6EA"`; `[theme.sidebar]`
  `backgroundColor = "#F4F5F8"` and `textColor = "#1F2430"` (the text colour must be set
  explicitly — an empty value logs a browser warning on every render); `[client]
  toolbarMode = "minimal"`. Default `font`/`codeFont` (Source Sans 3 / Source Code Pro); Chinese
  glyphs fall back to the browser's system CJK font (Microsoft YaHei on Windows). Verified
  visually in quickstart scenario 1 and in the redesign screenshots.
- **Rationale**: `[[theme.fontFaces]]` (self-hosted Noto Sans SC) needs
  `[server] enableStaticServing = true` and static files — polish, not a requirement.
- **Alternatives**: `[[theme.fontFaces]]` with Noto Sans SC subsets; `headingFont` for closer
  fidelity to the canvas.
- **Sources**: docs.streamlit.io/develop/api-reference/configuration/config.toml.

## R-10 OCR engine (constitution deviation — see plan Complexity Tracking)

- **Decision**: RapidOCR 3.10.0 + onnxruntime 1.31.0 (`pip install rapidocr onnxruntime`),
  default `lang_type="ch"` (Chinese + English + digits), behind `tools/ocr.py` with a
  `recognise(image) -> [(text, score, box)]` interface. A page is "scanned" when
  `len((page.extract_text() or "").strip()) < 20` in pdfplumber 0.11.10; it is rendered at
  200 dpi and passed to OCR. Photos go through `PIL.ImageOps.exif_transpose`. A line is
  `unreadable` when its mean OCR score < `CARGOLINT_OCR_MIN_SCORE` (default 0.6) or empty.
  RapidOCR expects BGR ndarrays — pass file paths or convert RGB→BGR.
- **Rationale**: pip-only, ~45 MB, no system binary, no first-run download, Chinese by
  default; OCR is the lowest-priority input path in a 20–25 h budget.
- **Alternatives**: Tesseract 5.5.3 (UB Mannheim installer + `chi_sim`; system install, weak
  on phone photos); PaddleOCR 3.7.0 (best accuracy, but paddlepaddle 3.3.1 wheel 105 MB,
  PaddleX dependencies, model downloads on first run). Both can be plugged into the same
  interface later.
- **Sources**: pypi.org/project/rapidocr; rapidai.github.io/RapidOCRDocs; pypi.org/project/
  onnxruntime; pypi.org/project/pdfplumber; github.com/UB-Mannheim/tesseract/wiki;
  paddleocr.ai/latest/en/version3.x/paddlepaddle_installation.html.

## R-11 Nomenclature source (CN 2026 = HS 2022 + CN-8)

- **Decision**: Publications Office / Eurostat "Combined Nomenclature, 2026" SKOS RDF/XML
  (`ESTAT-CN2026.rdf`, 167 MB, CC BY 4.0; catalogue data.europa.eu/data/datasets/
  combined-nomenclature-2026). `rag/nomenclature.py` streams it with `lxml.etree.iterparse`
  over `skos:Concept` elements and keeps `skos:notation` (e.g. `0101 29`), `xkos:depth`,
  `skos:broader`, `prefLabel@en`, `altLabel@en`, `scopeNote@en` (self-explanatory text) and
  `hiddenLabel` (dash level). HS-6 concepts are the 7-character notations; one chunk per HS-6 =
  chapter title + heading text + subheading text + its CN-8 lines + scope notes, with metadata
  `chapter`, `heading`, `subheading`, `language=en`, `source`, `edition_year=2026`. Output
  `data/nomenclature_2026.jsonl` (~5.6k chunks, committed); the raw RDF is git-ignored.
- **Rationale**: the only confirmed structured source with the full hierarchy and English
  texts; 15,072 concepts parsed by the research agent. The index is therefore ~5.6k chunks, not
  the ~10k estimated in the intro (CN-8 lines are folded into their HS-6 chunk).
- **Alternatives**: Statistics Denmark XLSX mirrors (`CNofftextE_2026`, `CNsetE_2026`;
  lightweight, no level column); AEAT `CN2026_Structure.xlsx` (levels, Spanish text); the OJ
  PDF of Regulation (EU) 2025/1926 via pdfplumber (fallback only — loses dash levels and
  footnotes). No Formex XML was found for CELEX 32025R1926.
- **Sources**: op.europa.eu euvoc download handler (cellar 79c210b8-c4a3-11f0-8da2-01aa75ed71a1);
  showvoc.op.europa.eu dataset ESTAT_Combined_Nomenclature,_2026; dst.dk/ext/udroko.

## R-12 BTI rulings source

- **Decision**: official full extract `DDS2-EBTI_Full.zip` (≈ 397 MB; 23 yearly CSVs
  `EBTI_2004.csv … EBTI_2026.csv`, UTF-8 BOM, quoted multi-line fields; follow the redirect from
  `ebti_export_management.jsp?message=extractFull` on each run). `rag/bti.py` streams the zip,
  keeps rows with `STATUS` valid, `END_DATE_OF_VALIDITY` ≥ today and `NOMENCLATURE_CODE`
  prefix in the target chapters (39, 42, 61–64, 73, 84, 85, 94, 95, 96), derives HS-6 from the
  first six digits, and writes `data/bti_subset.jsonl` (git-ignored) plus a committed
  `data/bti_demo.jsonl` (~200 rulings for tests and the demo). Full text goes to the document
  store (`store/bti_docs.jsonl`); only `DESCRIPTION_OF_GOODS + CLASSIFICATION_JUSTIFICATION`
  is embedded, with metadata `code`, `cn_code`, `member_state`, `language`, `valid_from`,
  `valid_to`, `chapter`. All issuing languages are kept (the embedding model is multilingual);
  `NAME_AND_ADDRESS` is dropped at load time (FR-046). Attribution: CC BY 4.0 (Decision
  2011/833/EU) in the README.
- **Rationale**: no scraping, no login, documented columns; validity filtering in code
  satisfies FR-015.
- **Alternatives**: per-ruling HTML pages (images only there); daily delta files; paid
  monitors.
- **Sources**: ec.europa.eu/taxation_customs/dds2/ebti/ebti_export_management.jsp;
  …/ebti/ebti_details.jsp.

## R-13 ICS2 rule lists and flag mapping

- **Decision**: two documents, both extracted to JSON by `rag/rules.py` with pdfplumber:
  (a) DG TAXUD "Guidance on acceptable and unacceptable terms for the description of goods"
  v4.10 (TAXUD b.1(2021)1688480; ~208 rows Unacceptable | Acceptable) →
  `data/rules/ics2_unacceptable_terms.json`; (b) "Introduction of Stop Words/Phrases in the
  Common Repository" (CIRCABC, 273 rows with category and implementation date; version in
  force 2026-08-03) → `data/rules/ics2_stop_words.json`, goods-description category only.
  In CargoLint's vocabulary **both ICS2 lists feed the Vague flag** (`rule_source =
  ics2_unacceptable`, citing the document and term), and the **firm stop-word list feeds the
  Stop-word flag**, exactly as the spec defines (FR-008, FR-009). The firm demo list
  (`data/rules/firm_stop_words.json`, 32 terms incl. gift/礼品, samples/样品) is written by hand.
- **Rationale**: preserves the spec and the design canvas ("Parts" → Vague with ICS2 source;
  "Gift" → Stop-word from the firm list). Note for the author: customs itself calls the
  CIRCABC list "stop words"; if the UI label "Stop-word" should mean the ICS2 list instead,
  that is a spec change (FR-008/FR-010) — raised in the plan report, not decided here.
- **Alternatives**: Croatian Customs mirror (Aug 2025, 231 rows); tulli.fi page (blocks
  scripts); treating ICS2 stop words as Stop-word flags.
- **Sources**: taxation-customs.ec.europa.eu document ea68a0c7-a2d3-4bc1-9bed-ebc149c920f0;
  circabc.europa.eu/rest/download/e9bb2d8d-c5a5-4997-a78b-f444fbf424ff.

## R-14 File parsing and language splitting

- **Decision**: `pandas.read_excel(sheet_name=None, header=None, engine="openpyxl")` and
  `read_csv` (try `utf-8-sig`, then `gbk`); the header row is the first row with ≥ 2 matches
  from a bilingual alias table (`description/品名/货物描述`, `qty/数量`, `weight/毛重`,
  `cbm/体积`, `value/金额`); rows with empty descriptions or `total/合计` are skipped; mixed
  cells split on `/`, newline, full/half-width parentheses or the CJK↔Latin boundary (regex
  on `\p{Han}` runs). Shipper detection = alias match of `data/shippers.json` names anywhere in
  the first 15 rows. Caps enforced before any model call (FR-002, FR-006).
- **Rationale**: matches the design's sample ("sheet 装箱单, header row 3, 12 lines") and the
  edge cases in the spec; everything is deterministic and unit-testable.
- **Alternatives**: a model call to detect the header row (unnecessary and untrusted).

## R-15 Throughput for 100 lines in 5 minutes (SC-005)

- **Decision**: batch tools process lines with `ThreadPoolExecutor(max_workers=
  CARGOLINT_WORKERS)` (default 4), per-line timeout 60 s, per-line isolation. Per line: one
  judgement call (only when rule lists do not match), one translation/expansion call, one
  query embedding, one ranking call — ≈ 3–5 s sequential, so 100 lines ≈ 100–130 s with 4
  workers. Threshold recomputation and precedent lookup are local.
- **Rationale**: well inside 5 minutes with headroom for retries; the OpenAI SDK client is
  thread-safe.
- **Alternatives**: `asyncio` with the async client (more intrusive in Streamlit); batching
  several lines into one ranking call (cheaper, but weakens per-line isolation and tracing).

## R-16 Testing approach (Principle VII)

- **Decision**: `pytest` with markers `unit`, `integration`, `adversarial`, `live`. Offline
  tests inject a fake client factory returning recorded structured outputs
  (`tests/fixtures/*.json`) and a fake embedding function; `live` tests need
  `OPENROUTER_API_KEY` and are skipped otherwise. The 20-line labelled set
  (`data/labelled/lines_20.jsonl`) and the adversarial set (`tests/fixtures/adversarial.jsonl`,
  ≥ 10 lines) are written before the pipeline. `tests/eval/run_eval.py` reports flag accuracy,
  top-1/top-3 for `hybrid` and `vector_only`, and cost per shipment (SC-001/002/010/011).
  RAGAs (stretch) reuses the same set.
- **Rationale**: guardrail tests must not depend on a model; evaluation must be repeatable.
- **Alternatives**: `langchain_core.language_models.fake.GenericFakeChatModel` for the agent
  loop; VCR-style HTTP recording (pins responses too tightly to prompts).

## R-17 Pinned versions (PyPI, 2026-10-14)

`python>=3.11,<3.13` · `streamlit==1.65.0` · `langchain==1.4.5` · `langchain-core==1.6.10` ·
`langgraph==1.2.15` · `langchain-openai==1.7.1` · `openai==3.31.0` · `langchain-chroma==1.1.0`
· `chromadb==1.5.9` · `rank_bm25==0.2.2` · `pydantic>=2.7,<3` · `pandas>=2.2` ·
`openpyxl>=3.1` · `pdfplumber==0.11.10` · `rapidocr==3.10.0` · `onnxruntime==1.31.0` ·
`pillow>=10` · `lxml>=5` · `python-dotenv>=1` · dev: `pytest>=8`, `pytest-timeout`,
`ragas` (stretch, optional extra). No `langchain-community`, no `langchain-classic`.
