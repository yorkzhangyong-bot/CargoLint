# CargoLint — Project Introduction

**Course:** Turing College · AI Engineering · Sprint 2 project "Building Applications with AI" (LangChain, RAG, tool calling, Streamlit)
**Author:** Yong Zhang
**Status:** MVP scope agreed, design screens and architecture diagram done, implementation next

---

## 1. One-liner

CargoLint catches cargo descriptions that EU customs will reject before a forwarder files them, and suggests HS-6 codes with reasoning and precedent. Think of it as a linter for packing lists.

## 2. The problem

A customs/export clerk at a Hamburg freight forwarder or consolidator files ICS2 house declarations (ENS) for China→EU sea freight. The packing lists they receive from Chinese shippers are full of descriptions such as 配件 / Parts, 礼品 / Gift, 电子产品 / Electronic products. The EU ICS2 rules explicitly list such terms as unacceptable, and a declaration carrying them is rejected or held, which costs the forwarder time, demurrage and credibility with the carrier. The clerk then has to chase the shipper by WeChat or e-mail, usually in Chinese, and re-file.

Today this is done by eye, line by line, with Excel and experience. General chatbots such as ChatGPT can answer "which HS code is a vacuum flask", but they will not check a whole packing list, refuse to guess when the description is too vague, remember what this shipper sent last time, or leave an audit trail a customs auditor can follow.

## 3. Target customer

Customs/export clerk at a 10–40-person Hamburg forwarder or consolidator filing ICS2 house declarations for China→EU sea freight, ideally a Chinese-run firm. The Hamburg forwarders' association VHSp has 318 member firms.

## 4. What the MVP does

The clerk uploads a packing list or invoice (xlsx, csv, pdf, photo; Chinese, English or mixed) or pastes lines into a chat. For every line CargoLint:

- flags vague descriptions and stop-words, citing the rule it matched;
- suggests the top-3 HS-6 subheadings with a confidence score, reasoning, and a precedent BTI ruling where one exists;
- routes the line to one of three outcomes: auto-accept (above a configurable threshold, default 85%), human review, or ask the shipper.

Results appear in a review table next to the chat, needs-action lines first, with a detail panel for the selected line. The clerk can ask follow-up questions about any line ("why only 31%?") and, when the shipper replies, paste the answer into the chat; only that line is re-checked and the table refreshes. Results export to CSV/JSON. Token usage and cost per shipment are shown in the sidebar.

Two screens make up the MVP: a start screen (sidebar uploader, shipment fields, rules, welcome message with quick actions) and the post-check screen (chat with tool-call status, routing metrics and sources on the left; review table and line detail on the right).

### Explicitly out of scope for the MVP

- Drafting the bilingual query to the shipper (the bot tells the clerk what to ask; the clerk writes the message).
- Line version history UI (versions are stored, but only the current version is shown).
- CN-8 and TARIC-10 codes, duty rates, anti-dumping measures.
- Sending anything to the shipper or to a customs system.

## 5. Mapping to the course requirements

### Core requirements

| Requirement | How CargoLint meets it |
|---|---|
| Knowledge base relevant to the domain | Full HS 2022 / EU Combined Nomenclature text (one chunk per subheading, with chapter/heading metadata) plus EU BTI rulings for the target chapters, the ICS2 unacceptable-terms list and a firm stop-word list |
| Standard retrieval with embeddings, chunking, similarity search | Structure-based chunking (one subheading per chunk), embeddings in a local Chroma store, cosine similarity |
| Advanced RAG with query translation and structured retrieval | Every line is searched with its raw text in any language, as the embedding model is multilingual (feature 009 dropped the Chinese→English translation, which showed no gain); multi-query expansion with HyDE is one switch, `CARGOLINT_QUERY_EXPANSION`, off by default after the feature 009 evals; metadata filter by chapter; hybrid BM25 + vector retrieval fused with reciprocal rank fusion |
| At least 3 tool calls relevant to the domain | 5 tools: `parse_packing_list`, `check_description`, `classify_hs6`, `lookup_precedent`, `apply_shipper_reply` |
| Domain-specific prompts, responses and security | Customs-specific system prompt; descriptions passed as fenced data; schema-validated outputs; routing enforced in code |
| LangChain with OpenRouter (OpenAI-compatible SDK) | LangChain v1 agent; LLM and embeddings called through OpenRouter |
| Error handling and input validation | File type/size/row caps, description length caps, graceful failures per line, retries on API errors |
| Intuitive UI showing context, sources, tool results, progress | Streamlit: `st.chat_message`, `st.status` for tool progress, `st.expander` for sources and retrieval steps, `st.dataframe` for the review table, `st.metric` for routing counts |

### Optional tasks chosen (target: 2 medium + 1 hard for maximum points)

- Medium — Protect the app against prompt injection (the packing list is untrusted external input; see §9).
- Medium — Calculate and display token usage and costs (sidebar metric per shipment).
- Hard — Hybrid search (BM25 + embeddings with RRF; needed because HS code numbers and exact product terms retrieve poorly with vectors alone).
- Bonus, inherent in the design — Multi-language support (Chinese/English input, English nomenclature).
- Stretch — RAG evaluation with RAGAs on 20–30 hand-labelled lines (Hard).
- Easy extras that fall out naturally — source citations, visualisation of the RAG process, conversation export.

### Evaluation criteria to be ready for

Explain how RAG works in this pipeline (raw-text queries → hybrid retrieval → ranking → validation); explain the tool-calling loop; show clean code organisation; name the error scenarios (scanned PDF with bad OCR, mixed-language cells, code that does not exist, model returning the wrong schema, shipper reply that contradicts the file); and give an honest list of weaknesses and improvements (§12).

## 6. Architecture

```
Clerk inputs            Streamlit UI                 LangChain agent (LLM via OpenRouter)
───────────             ───────────                  ────────────────────────────────────
packing list/invoice ─▶ sidebar (upload, rules) ──▶  agent: fenced inputs, schema output, routing
chat message ─────────▶ chat (status, sources) ◀──▶  │
                        review table + detail ◀──┐   ├─ parse_packing_list  → file parsers (openpyxl, pdfplumber + OCR)
                                                 │   ├─ check_description   → rule lists (ICS2 terms, firm stop-words)
                                                 │   ├─ classify_hs6        → RAG (ZH→EN, BM25 + vectors, Chroma)
                                                 │   ├─ lookup_precedent    → BTI rulings (local, by subheading)
                                                 └── └─ apply_shipper_reply → line store (versions, routes, audit)

Guardrails live in code, not in the prompt: threshold enforced by code · suggested code must exist in the
nomenclature · a flagged line needs a human click after an update · file limits · token and cost per shipment
```

The same diagram, as a design artboard, sits on the CargoLint design canvas next to the two screen mockups.

## 7. Tech stack

- Python 3.11+, Streamlit (UI), LangChain v1 (agent and tools), OpenRouter via the OpenAI-compatible SDK (chat model and embeddings).
- Chroma (vector store, persisted locally) and `rank_bm25` (keyword index), fused by reciprocal rank fusion.
- openpyxl / pandas for spreadsheets; pdfplumber for text PDFs; Tesseract or PaddleOCR for scanned PDFs and photos (Chinese + English).
- Pydantic for tool input/output schemas; `st.session_state` for the line store in the MVP (SQLite later).
- pytest for unit tests; RAGAs for the retrieval evaluation (stretch).
- Code editor: VS Code. Repository: the GitHub repo provided by the course.

## 8. Tools (function calling)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `parse_packing_list` | uploaded file | structured lines: zh, en, qty, weight, volume, row ref | detects header row, splits mixed ZH/EN cells, skips total rows, enforces caps |
| `check_description` | one line | flag (ok / vague / stop-word) + matched rule + reason | deterministic match first, LLM judgement second |
| `classify_hs6` | one line + shipper context | top-3 subheadings with confidence, rationale, retrieved chunks | runs the RAG pipeline; every returned code is verified to exist |
| `lookup_precedent` | candidate codes | matching BTI rulings (ref, description, validity) | filters expired rulings |
| `apply_shipper_reply` | pasted reply + line ref | new line version with extracted material / part / use | re-runs check, classify and precedent for that line only |

Routing is not a tool and not a model decision: a function in code reads the flag and confidence against the threshold and writes `auto_accept`, `review` or `ask_shipper`.

## 9. Security measures

The packing list is a document written by a third party, so it is treated as untrusted input end to end. Parsed descriptions reach the model only inside clearly delimited data blocks, with a system prompt stating that any instruction inside those blocks is void. Tool outputs are validated against a strict schema: codes must match `\d{4}\.\d{2}` and exist in the nomenclature, routes must be one of three enum values, confidence must be 0–100. File type, size and row count are capped, as is description length. The auto-accept threshold is enforced in code, and a line that was ever flagged cannot be auto-accepted after an update without an explicit human click. Shipper contact details are not logged. API keys come from environment variables, never from the UI.

## 10. Knowledge base and data sources

**Decision:** index the full nomenclature (cheap, and avoids having no candidate for an unexpected product) plus BTI rulings for the target chapters, with the loader written so that adding chapters is just re-running it with a longer chapter list.

| Dataset | Content | Size (approx.) | Where to get it |
|---|---|---|---|
| EU Combined Nomenclature 2026 (contains the full HS 2022 six-digit structure plus EU eight-digit codes) | Commission Implementing Regulation (EU) 2025/1926, Annex I | ~5,600 HS-6 subheadings, ~9,500 CN-8 codes → ~10k chunks, ~60 MB of vectors | https://taxation-customs.ec.europa.eu/news/commission-publishes-2026-version-combined-nomenclature-2025-10-31_en (regulation text on EUR-Lex) |
| EBTI — European Binding Tariff Information | public classification decisions: goods description, reasoning, code, validity dates | tens of thousands of rulings for chapters 39, 42, 61–64, 73, 84, 85, 94, 95, 96 (export by code range); several hundred thousand EU-wide | https://ec.europa.eu/taxation_customs/dds2/ebti |
| ICS2 guidance on acceptable goods descriptions | the unacceptable-terms list and the information a description must contain | one PDF | https://info-aduaneiro.portaldasfinancas.gov.pt/pt/informacao_aduaneira/ICS2/Documents/guidance_acceptable_goods_description_V4.10_MAR2021_EN.pdf |
| ICS2 updated stop-word list | current list of banned terms | one page | https://tulli.fi/en/-/ics2-safety-and-security-declarations-on-entry-updated-list-of-stop-words-in-goods-descriptions-1 |
| Firm stop-word list | the forwarder's own banned terms (32 in the demo) | one JSON file | written by hand for the demo |
| Shipper history | past shipments per shipper (codes filed) | small JSON | synthetic demo data |

Chunking: one chunk per subheading, text = chapter title + heading text + subheading text (+ CN-8 lines under it), metadata = chapter, heading, subheading, language, source, year. BTI rulings: one chunk per ruling, text = goods description + reasoning, metadata = code, member state, validity start/end. Ruling text is kept in a document store; the vector index stores only the embedding and metadata.

Embedding cost estimate: 10k nomenclature chunks + ~50k rulings × ~300 tokens ≈ 18M tokens, roughly €0.50–€2 with a small embedding model via OpenRouter, or free with a local multilingual model (bge-m3) at the cost of a few hours on CPU.

## 11. Implementation plan (20–25 hours)

1. Build a 20-line labelled test set (5 vague, 3 stop-words, 12 clear lines with known codes). (1 h)
2. Loader: download the CN regulation, parse to subheading chunks, embed, persist in Chroma; build the BM25 index. (3 h)
3. `classify_hs6` end to end: query translation → hybrid retrieval → LLM ranking → code validation. Measure on the test set. (5 h)
4. `check_description` and routing rules; BTI export for target chapters and `lookup_precedent`. (3 h)
5. Streamlit app: sidebar, chat, `st.status` tool progress, review table, detail panel, sources expander. (5 h)
6. `parse_packing_list` (xlsx/csv first, then pdf/OCR) and `apply_shipper_reply`. (3 h)
7. Security pass (fencing, schema validation, caps), token/cost display, export, README, tests. (3 h)
8. Stretch: RAGAs evaluation; comparison of vector-only vs hybrid retrieval for the review. (2 h)

Suggested repository layout:

```
cargolint/
  app.py                 # Streamlit entry point
  agent/                 # LangChain agent, prompts, routing rules
  tools/                 # parse_packing_list.py, check_description.py, classify_hs6.py, lookup_precedent.py, apply_shipper_reply.py
  rag/                   # loader.py (nomenclature + BTI), retriever.py (hybrid), translate.py
  data/                  # raw downloads, rule lists, shipper history, labelled test set
  store/                 # Chroma persistence, BM25 pickle
  tests/
  README.md
```

## 12. Known limitations and next steps

Confidence scores are model-estimated, calibrated only loosely against the test set; a proper calibration needs more labelled data. Chinese product slang and brand-specific terms will still miss sometimes; the hybrid index helps but does not solve it. BTI coverage is limited to the exported chapters and must be refreshed as rulings expire. OCR on phone photos is the weakest input path. The MVP keeps state in the Streamlit session, so nothing persists across restarts.

Roadmap after the MVP, in order of customer value: drafted bilingual shipper queries with send tracking; line version history and audit export; CN-8 classification (same pipeline, one more level); TARIC-10 lookup as a deterministic tool (duty rate, anti-dumping measures, certificates) for import declarations; SQLite persistence and multi-user access.

## 13. Design assets

The CargoLint design canvas contains the start screen, the post-check chat + review-table screen, and the architecture diagram, all drawn in Streamlit's visual language so the mockups match what the app will look like.
