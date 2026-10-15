# CargoLint

A linter for packing lists. Before a Hamburg freight forwarder files an ICS2 house declaration (ENS)
for China→EU sea freight, CargoLint flags cargo descriptions that EU customs will reject, suggests the
top-3 HS-6 subheadings with confidence, reasoning and a BTI precedent, and routes every line to
**auto-accept**, **human review** or **ask the shipper**. The clerk works a review table, decides a
code when accepting, pastes the shipper's reply to re-check one line, and exports CSV/JSON.

Built for Turing College · AI Engineering · Sprint 2 ("Building Applications with AI": LangChain,
RAG, tool calling, Streamlit). Author: Yong Zhang. Spec-driven: see `specs/001-packing-list-check/`
and `.specify/memory/constitution.md`.

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate          # Windows; Python 3.11–3.13
pip install -e ".[dev]"
set OPENROUTER_API_KEY=sk-or-...                           # or put it in .env (see .env.example)
python -m rag.loader --demo                               # builds the knowledge base (≈ 10 min, ≈ $0.02)
pytest -q                                                 # 229 offline tests, no key needed
streamlit run app.py
```

The loader downloads the EU Combined Nomenclature 2026 (SKOS, 171 MB), the two ICS2 documents and
— once, for the BTI subset — the EBTI full extract (397 MB), then embeds ≈ 5,600 nomenclature chunks
and the 192-ruling demo subset through OpenRouter. `python -m rag.bti --make-demo` regenerates the demo
subset; `python -m rag.loader --bti-chapters 39,42,61-64,73,84,85,94,95,96` builds the full
73,899-ruling subset. Data provenance and licences: `data/SOURCES.md`.

## What the clerk sees

**Start screen**: a grouped sidebar — uploader (XLSX/CSV/PDF/JPG/PNG, 20 MB), shipment reference and
shipper (detected from the file or chosen), the auto-accept threshold (60–99, default 85) and the
hybrid-search switch, a knowledge-base caption, and tokens, cost and the CSV/JSON exports pinned at the
bottom; a welcome message with three quick-action cards and a "What I can and cannot do" panel.

**While a check runs**: the agent turn runs in a worker thread, so the page stays live. The assistant
rail shows each tool step as it finishes (`parse_packing_list` → `check_description` → `classify_hs6`
→ `lookup_precedent`) with the current tool and elapsed time, and the review list appears as soon as
the file is parsed, filling in flags, codes and routes line by line.

**After a check**: routing counts, the lines that need attention and what to ask the shipper, the
model's notes (collapsed), a Sources expander grouped by kind and a Retrieval-steps expander; the
review list orders every line needs-action first (description · flag · HS-6 with confidence · route),
25 per page, and the detail card beneath it shows the top-3 candidates with a BTI precedent popover,
the route pills, an Accept popover with the decided-code control, why the line was flagged and how to
update it, plus previous/next buttons that cycle through the lines needing action. The layout is
native Streamlit only (no custom HTML or CSS); the review list uses proportional columns so nothing is
clipped at laptop widths.

## How RAG works in this pipeline

1. **Knowledge base** (`rag/loader.py`). The CN 2026 SKOS file is parsed with `lxml.iterparse`
   (`rag/nomenclature.py`) into **one chunk per HS-6 subheading**: chapter title + heading text +
   subheading text + the self-explanatory text + its CN-8 lines with their dash-group path, with
   `chapter`, `heading`, `subheading`, `language`, `source`, `edition_year` as metadata. BTI rulings
   are one chunk each (goods description + reasoning; metadata code, chapter, member state, validity),
   with holder names and addresses dropped at load time. The ICS2 lists are extracted from the official
   PDFs (`rag/rules.py`).
2. **Query translation and expansion** (`rag/translate.py`): a structured call turns the Chinese or
   mixed description into one literal English translation plus up to four expansions (synonyms,
   product category, material) and an optional HyDE-style sentence. English-only text skips the call.
3. **Hybrid retrieval** (`rag/retriever.py`): BM25 over `rank_bm25` with a tokenizer that keeps HS
   codes in both `9617.00` and `961700` forms, plus cosine search in a persisted Chroma collection
   (`qwen/qwen3-embedding-8b`, 4096 dimensions), fused by **reciprocal rank fusion** (k = 60). When
   the shipper has a filing history, a second search restricted to those chapters is fused in as a soft
   boost (the trace shows it as the metadata filter). The sidebar switch turns BM25 off for the
   vector-only baseline.
4. **Ranking** (`tools/classify_hs6.py`): the fused chunks, the fenced description, the flag result
   and the shipper's past codes go to the chat model, which returns up to three candidates with
   confidence and rationale as strict JSON.
5. **Validation in code**: every returned code must match `^\d{4}\.\d{2}$` **and exist in the
   nomenclature index**; unknown codes are dropped, subheading text and chapter are filled from the
   index, never from the model. If nothing survives, the line is "no valid candidate".
6. **Routing in code** (`agent/routing.py`): stop-word → ask the shipper; vague → ask the shipper below
   the ask floor (50) else review; OK → auto-accept at or above the threshold else review; a line that
   was ever flagged, or updated by a shipper reply, is never auto-accepted — it becomes "ready to
   accept" and needs the clerk's click.

## The tool-calling loop

`agent/agent.py` builds a LangChain v1 agent (`create_agent`) with exactly five tools. For every clerk
message the app builds a **context block** from the line store (counts, needs-action lines, the
selected line in full, the rule lists when the question is about terms) and a short code-built request
(`Check lines 1–3`, `Apply reply r1 to line 1`, `FILE REFERENCE: f1`). Tools take **references**
(`line_nos`, `file_ref`, `reply_ref`) and read the texts from the store themselves, so the model never
re-types untrusted text into tool arguments. Tool start/end callbacks drive the `st.status` progress
block; `UsageMetadataCallbackHandler` collects tokens. After a check request a **completeness guard**
runs any step the agent skipped and fails whatever is still pending, so every line ends `checked` or
`failed` with a computed route. Routes, counts and decided codes shown anywhere in the UI are read from
the store, never from the model's prose.

## Security measures

- **Untrusted text is data.** Descriptions, OCR text, pasted lines and shipper replies reach a model
  only inside `<data line="N">…</data>` blocks (angle brackets inside are neutralised), under a system
  prompt that declares instructions in such blocks void. Pasted content never enters the agent's
  message history — only references and code-built summaries do. `tests/adversarial/` runs 12
  injection fixtures through the tools and a static check that every model-call site fences its input.
- **Schema validation** of every structured output (Pydantic), with two retries that feed the
  validation error back, then the line fails — never passed through.
- **Code existence** for every suggested *and every typed* code; the **lock** on Accept while a line
  is flagged; **routing and the threshold in code**, never in the prompt.
- **Caps** before any model call: 20 MB per file, 200 lines per shipment, 300 characters per
  description, 50 pasted lines per message. Workbooks open data-only without VBA; `.xlsm` is rejected;
  no link inside a file is followed.
- **Secrets** come from the environment only; shipper contact details are dropped from the BTI data
  and never logged; nothing is ever sent to a shipper or a customs system.
- Residual risk: the clerk's own typed message is trusted as an instruction.

## Error scenarios and how they are handled

| Scenario | Behaviour | Test |
|---|---|---|
| Scanned PDF or photo with poor OCR | lines below the OCR cut-off are marked *unreadable* and routed to review, never guessed | `test_error_scenarios.py` |
| Mixed-language cells | split on `/`, newline, parentheses or the CJK↔Latin boundary | `test_parsers.py` |
| Model suggests a code that does not exist | dropped by the existence check; "no valid candidate" if none survives | `test_classify_hs6.py` |
| Model returns the wrong schema | two retries with feedback, then the line fails with the reason | `test_classify_hs6.py` |
| Shipper reply contradicts the file | new version routed to review with a note naming both codes (fixed chapter rule) | `test_apply_reply.py` |
| API failure / rate limit | SDK retries with back-off; 402 is not retried; only that line fails | `test_error_scenarios.py`, `test_check_description.py` |
| Unsupported or oversize file, empty or header-less file | rejected before processing with a message naming the limit | `test_parsers.py`, `test_parse_packing_list.py` |
| Agent skips a tool | the completeness guard runs the missing step (shown as "run by the app") | `test_agent_check_flow.py` |

## Tests and evaluation

- `pytest -q` — unit, integration and adversarial tests, offline, with a fake structured-output backend
  that replays recorded outputs (`tests/fixtures/recorded/`, regenerate with
  `python tests/fixtures/make_recorded.py`).
- `pytest -m live` — three OpenRouter smoke tests (embeddings, structured output, price-table cost vs
  OpenRouter accounting) and the budget test (sample shipment + two follow-ups < €0.10).
- `python tests/eval/run_eval.py --sample` — the 20-line labelled set (5 vague, 3 stop-word, 12 clear
  with known codes) in both retrieval modes plus the 12-line sample.

Labelled-set results, 2026-10-14, `openai/gpt-4o-mini` + `qwen/qwen3-embedding-8b`:

| Mode | Flag accuracy | Top-1 | Top-3 | Flagged lines auto-accepted | Time |
|---|---|---|---|---|---|
| Hybrid (BM25 + vectors, RRF) | 20/20 | 10/12 | 11/12 | 0 | 87 s |
| Vector-only baseline | 20/20 | 9/12 | 10/12 | 0 | 65 s |

Hybrid wins the exact-term lines (e.g. `7318.15` stainless steel hexagon bolts, which vector-only
puts at `7318.19`). Both modes miss silicone mobile phone cases (`3923.10` packaging cases instead of
`3926.90`). The whole evaluation (both modes and the sample) cost €0.016. Sample routes matched the
design illustration on 10/12 lines; the other two are legitimate model confidences (LED desk lamp
95 → auto-accept, bare "Furniture" 40 → ask the shipper).

Retrieval alone (`python tests/eval/ragas_eval.py`, RAGAs-style context metrics against the reference
chunk, no LLM judge), k = 6, 12 clear lines: context recall 92 % in both modes, context precision
(MRR) 0.81 hybrid / 0.82 vector-only, chapter hit 100 %. The phone-case miss is a retrieval miss —
the `3926.90` chunk is never among the six candidates — so better query expansion ("protective
cover"), not better ranking, is the fix.

Scale (`python tests/eval/scale_check.py`, 100 generated lines, six workers): first progress step
after 1.6 s, all 100 lines checked in 130 s, none failed, €0.05; a 201-line file is rejected whole
before any model call. (The first run took 484 s because every expansion query was embedded with its
own API call; the queries of a line are now embedded in one request and reused by the history boost.)

Live budget (`pytest -m live`): the 12-line sample plus two follow-up questions = 40.6k tokens,
36 calls, €0.007.

Manual checks (not automated): moving the threshold slider re-routes lines instantly without a model
call; uploading a second file while a shipment is open asks for confirmation; the CSV/JSON downloads
open with Chinese text intact.

## Known weaknesses and next steps

- Confidence is model-estimated and only loosely calibrated against 20 labelled lines; it must not be
  read as a probability.
- Chinese product slang and brand-only names still miss; the hybrid index helps but does not solve it.
- Classification confusions remain where the nomenclature itself is subtle (protective phone cases vs
  packaging cases; aluminium bicycle frames landed in aluminium structures `7610.90` instead of
  `8714.91` in one live run) — and the model occasionally auto-accepts such a wrong code at high
  confidence, which is why the threshold is adjustable and the audit trail exists.
- `gpt-4o-mini` sometimes skips `lookup_precedent`; the completeness guard runs it, so results are
  complete, but the progress block then shows the step as "run by the app".
- BTI coverage: the demo subset holds 192 rulings (all German-language) for the ten target chapters;
  the full subset (73,899 valid rulings) is a loader option. Rulings must be refreshed as they expire.
- OCR on phone photos is the weakest input path (RapidOCR, PP-OCR models); quantities and values are
  not read from photos.
- State lives in the Streamlit session: nothing persists across restarts; one user, one shipment.
- The chat model is reached through OpenRouter; a 402 (credits) stops checks with a clear message.

Roadmap, in order of customer value: drafted bilingual shipper queries with send tracking; line version
history and audit export; CN-8 classification; TARIC-10 lookup (duty, anti-dumping, certificates);
SQLite persistence and multi-user access.

## Repository layout

```
app.py          Streamlit entry point        ui/        sidebar, upload, chat, jobs (worker turns), replies, review, detail
agent/          config, schemas, routing, prompts, llm (client factory + cost), agent (loop + guard), store
tools/          the five tools, parsers, ocr, common (context + per-line runner)
rag/            loader (CLI), nomenclature (SKOS), bti (EBTI), rules (ICS2 PDFs), embeddings, retriever, translate
data/           processed knowledge base, rule lists, shipper history (synthetic), sample list, labelled set, SOURCES.md
store/          Chroma vectors, BM25 pickle, BTI document store (git-ignored; rebuilt by the loader)
tests/          unit, integration, adversarial, live, eval (run_eval.py, make_big_list.py), fixtures
```

## Data attribution

EU Combined Nomenclature 2026 (Publications Office / Eurostat) and the EBTI public extract are reused
under the Commission reuse policy (Decision 2011/833/EU, CC BY 4.0) — © European Union. ICS2 guidance
documents © European Commission. Shipper history, the firm stop-word list and the sample packing list are
synthetic demo data.
