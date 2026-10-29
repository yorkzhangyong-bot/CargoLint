# CargoLint

A linter for packing lists. Before a Hamburg freight forwarder files an ICS2 house declaration (ENS)
for China→EU sea freight, CargoLint flags cargo descriptions that EU customs will reject, suggests the
top-3 HS-6 subheadings with confidence, reasoning and a BTI precedent, and routes every line to
**auto-accept**, **human review** or **ask the shipper**. The clerk works one list, sorted by what needs attention:
picks a code in the open line for the lines to review, drafts the email to the shipper for the red ones, updates a
line with the shipper's answer and re-checks it, accepts the ready lines and downloads CSV/JSON. For a decided HS-6
it also chooses the CN-8 and completes the TARIC-10 by fixed rules from a local TARIC snapshot.

Built for Turing College · AI Engineering · Sprint 2 ("Building Applications with AI": LangChain,
RAG, tool calling, Streamlit). Author: Yong Zhang. Spec-driven: see `specs/001-packing-list-check/`
and `.specify/memory/constitution.md`.

## Quick start

```bash
python -m venv .venv && .venv\Scripts\activate          # Windows; Python 3.11–3.13
pip install -e ".[dev]"
set OPENROUTER_API_KEY=sk-or-...                           # or put it in .env (see .env.example)
python -m rag.loader --demo                               # builds the knowledge base (≈ 10 min, ≈ $0.02)
python -m rag.loader                                      # full EBTI rulings index for precedent-driven retrieval (74k rulings, ≈ 90 min, ≈ $0.3, 1.8 GB on disk)
python -m rag.loader --taric                              # one-time TARIC snapshot for digits 9–10 and measures (needs gpg, see below)
pytest -q                                                 # 950 offline tests, no key needed
streamlit run app.py
```

The loader downloads the EU Combined Nomenclature 2026 (SKOS, 171 MB), the two ICS2 documents and
— once, for the BTI subset — the EBTI full extract (397 MB), then embeds ≈ 5,600 nomenclature chunks
and the 192-ruling demo subset through OpenRouter. `python -m rag.bti --make-demo` regenerates the demo
subset; `python -m rag.loader --bti-chapters 39,42,61-64,73,84,85,94,95,96` builds the full
73,899-ruling subset and its own vector index (`store/chroma-bti`), which the precedent leg of the classifier
searches (see below). Data provenance and licences: `data/SOURCES.md`.

## TARIC snapshot (digits 9 to 10 and measures)

CargoLint can hold one EU TARIC snapshot for the last two digits of a code and the measures on it (features
002 and 003, `specs/002-taric-snapshot-load/` and `specs/003-taric-groups-exclusions/`). TARIC is used only for
digits 9 to 10 and measures: CN 2026 stays the only source for digits 1 to 8, and TARIC is never embedded or
indexed. The lookup (`TaricStore.lookup_taric(cn8, origin="CN")` in `rag/taric.py`) feeds the TARIC-10 step
described in [CN-8 and TARIC-10](#cn-8-and-taric-10).

1. Download the six object files of one batch (GoodsNomenclature, Measure, MeasureType, GeographicalArea,
   DutyExpression and Regulation) from https://distr.tullverket.se/tulltaxan/xml/tot/ into `data/raw/taric/`,
   keeping their original names (`ObjectName_batchId_YYMMDD.xml.gz.pgp`).
2. Make gpg available: it ships with Git for Windows (`usr/bin/gpg.exe`); otherwise put it on `PATH` or set
   `CARGOLINT_GPG` to its full path.
3. Run `python -m rag.loader --taric` (or `--taric <folder>`). The loader verifies every file against the
   pinned Swedish Customs key (`data/Tulltaxan_Fildistribution.asc`, fingerprint
   `4101 60CE 25CE C2FF 3227 84E7 302A C3C1 D0E3 E1C9`), keeps the records valid on the snapshot date and
   writes `data/taric.jsonl` (git-ignored). Running it again on the same extract changes nothing; add
   `--force` to rewrite the file. A snapshot written in an older format is rewritten even for the same extract,
   and the run says why. A refused extract writes nothing and leaves the previous snapshot as it was.
   It never touches the search indexes.

Admin › Data shows `TARIC snapshot: <date> · <n> CN-8 mismatches · Swedish Customs Tariff File Distribution`,
and the main page header `TARIC snapshot <date>`; both read `TARIC not loaded` when there is no snapshot, and the
app works the same either way. Mismatches are CN-8 prefixes
that CN 2026 does not have (special codes in chapters 98 and 99), listed in
`store/logs/taric-cn8-mismatches-<date>.txt`.

Two rules shape the data: only EU records are kept (the Swedish national records in the export are dropped),
and a lookup for an origin returns only import measures, those for the origin itself, for every EU country
group that contains it (for example 1008, all third countries) and erga omnes, recorded on the code or on any
level above it. A measure that excludes the origin, or a group that contains it, is left out, and the
anti-dumping/countervailing statistic (measure type 566), which EZT-online does not show, is never returned.
Each measure carries the English name of its area, so `1008` reads "All third countries".

Measured on 2026-10-23 with the 2026-10-01 extract (a 29.3 MB snapshot): a full load takes 24 to 32 s (SC-006 of
feature 002 allows 30 minutes). With the snapshot the knowledge base opens 0.7 to 0.9 s later at app start, 5.5 to
5.6 s against 4.6 to 4.9 s without it (feature 003 allows 2 s more); the store alone loads in about 0.5 s, and a
lookup takes under 1 ms. For China, the 2026-10-01 snapshot gives 1,512 group measures that used to be missing,
and leaves out 1,238 erga omnes measures and 37 group measures that exclude China.

## CN-8 and TARIC-10

Once a line's HS-6 is decided, auto-accepted or accepted by the clerk, two more steps run (feature 004,
`specs/004-cn8-taric-classification/`):

- **CN-8** (`tools/classify_cn8.py`, tool 6). With a single CN 2026 line under the HS-6, that line is taken
  without a model call. Otherwise one structured call chooses among the CN-8 lines. It cites the words of the
  description that decide (the evidence) and an EBTI ruling as precedent. Code checks the code against the CN-8
  lines, every quoted word against the description, and the cited ruling against the rulings sent.
  - When the deciding attribute is not in the text, the line routes to **ask the shipper** with a question naming
    it; for the sample's "Plastic toy cars" that is whether a motor is fitted.
  - The CN-8 is written when its quote passed the evidence check, the cited ruling does not sit at another CN-8,
    and it is the majority of the 5 nearest eligible EBTI rulings, each counted once, at a share of at least 0.5
    (constitution 1.4.0, feature 006). Otherwise it waits as "CN-8 to confirm", with the rulings and their issuing
    countries as the reason. The model's confidence is shown as a "model estimate" and only decides when no ruling
    can vote.
- **TARIC-10** (`tools/lookup_taric.py`, tool 7). The CN-8 is looked up in the snapshot for the invoice's origin:
  CN by default, set per invoice in the Origin field of the main page. Exactly one rule applies, in code
  (`agent/taric_rules.py`):

| Rule | When | What happens |
|---|---|---|
| Auto-completed | one subdivision, without a trade-defence measure | written once the CN-8 is written; the audit trail reads "auto-completed, single TARIC subdivision, snapshot <date>" |
| Choose | several subdivisions | all are shown, one may be highlighted as a suggestion with a confidence when the line states the separating attribute, and nothing is written until the clerk confirms one or asks the shipper |
| Trade defence | a subdivision carries measure type 551 to 555 or 570 (anti-dumping or countervailing) | the clerk confirms, even when it is the only subdivision |
| Not available | TARIC has no subdivision for the CN-8 | the line stops at 8 digits, without guessing "00" |
| Not loaded | no snapshot | "TARIC not loaded" |

When the clerk picks a TARIC-10, "All measures" shows the measures of the picked subdivision exactly as the lookup
returns them, in three groups:
- **duties**: third-country duty, preferences, quotas and additional duties;
- **trade defence**: anti-dumping and countervailing measures with their additional codes and conditional duty text,
  such as "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %";
- **requirements**: controls, CBAM, licences and units.

Beside them are the snapshot date, "Open in EU TARIC ↗" to the consultation page for the code, origin and date,
and "EZT-online ↗" to its start page, with the code and origin to copy. Changing the origin re-applies the rules
without a model call, and codes the clerk confirmed stay. The CSV and JSON exports gain `cn8` and `taric10`, filled
only with written codes; every existing column keeps its value.

## What the clerk sees

Two pages, native Streamlit only, laid out by feature 012 (`specs/012-ui-redesign/`) after the first customer feedback:
"text too small, important buttons not prominent". The base font size is 18. The main page is the clerk's, with no
sidebar and no chat. The Admin page holds the rules, the data, the cost, the quality and the agent chat, for the
operator and the course evaluators.

**The main page**, top to bottom:
- **Header**: "CargoLint" and the Origin box, a dropdown of the ISO country codes and TARIC's six own codes (XC, XI,
  XK, XL, XS, XU), CN by default, with the TARIC snapshot date. Changing the origin re-applies the TARIC rules to every
  line without a model call, and a toast says so.
- **Two tabs**:
  - "Upload file": a drop zone (PDF, Excel, CSV or a photo, up to 20 MB) and "Load sample invoice". The file waits
    for the full-width "Check all lines"; with a checked shipment open, it asks before replacing it.
  - "Check a single line": one description, in English or Chinese, and "Check this line" (Enter works too). The line
    joins the open shipment, and its row opens when its check ends.
- **Status line**: "Checked 12 lines of sample_packing_list.xlsx in 41 s · model: google/gemini-2.5-flash", or
  "Checking 12 lines… 8 s" while the agent turn runs in a worker thread and the list fills in every second. Queued
  lines and job messages follow it.
- **Counts**: three cards, "Ready to accept" (green), "Needs review" (orange) and "Ask shipper" (red), then "Accept
  all K ready", "Download CSV" and a small "JSON". The downloads add `clerk_changed`, true where the clerk chose an
  HS-6 other than the model's top candidate or edited the description.
- **The list**, sorted ask shipper → review → ready → accepted, 50 lines a page: # · Status · Description (as filed)
  · Need / description · HS code · Conf.
  - The status is a coloured badge, and its tooltip names the decision it waits for ("Pick: 10 or 90", "Ask: what
    exactly is “spare parts”?").
  - A red line shows what it needs ("needs material, product name and use"); the others show their current
    description.
  - The HS code is the dotted HS-6 ("9405.21") until a CN-8 is decided, then the decided digits with underscores for
    the rest ("6109 10 00 __", "9617 00 00 00").
- **A line opens under its row**, in four blocks:
  1. Description: the original and the stop-word check; on a red line, the reason and the question to copy; the
     description field and "Re-check this line", which stores the clerk's edit as a new version and checks that line
     again from the stop-word check.
  2. HS-6 candidates: the model's three, each with its confidence bar, and "Other HS-6 code…" for a typed code that
     the store checks against the nomenclature, with the reason for the chosen one. The choice changes only what is
     shown until "Accept".
  3. Similar rulings: the HS-6 of the 5 nearest EBTI rulings with their issuing countries, how many agree with the
     chosen code, and the candidates' precedents with "Open ruling ↗".
  4. Tariff for the origin: the CN-8 lines under a newly chosen code; the CN-8 or the subdivision to pick while that
     choice is open; or the decided CN-8 and TARIC-10 with the third-country duty, the requirements, "All measures"
     and "Open in EU TARIC ↗", and "Change the code at" CN-8 or TARIC-10.

  Then "Accept", which decides the chosen HS-6 or confirms the pick while the CN-8 and TARIC steps run in the
  background, and "Ask shipper", which turns the line red. On a red line "Accept" is locked and says why; a line that
  was ever flagged still needs the clerk's click after its update.
- **Shipper email draft**, when a line asks: string templates in English or Chinese, one numbered question per line,
  to copy and send by hand. Nothing is sent, and no model is called. Folded under it, each asking line's field for
  the shipper's answer, with "Re-check this line".
- **"Advanced: Ask the agent · paste shipper reply · audit trail · Admin"** at the bottom opens the Admin page.

**The Admin page**, with its sections in a switch at the top:
- **Rules**: the auto-accept threshold (60–99, default 85), used at either layer only when no eligible ruling votes,
  and hybrid search. Both survive a page switch, and every
  new shipment starts with them.
- **Data**: the EBTI ruling count, the TARIC snapshot with its CN-8 mismatches, the model and the knowledge-base
  statement.
- **Cost**: this shipment's and this session's tokens and euros.
- **Quality**: the latest CN-8 evaluation runs and the HS-6 labelled set, and the audit trail export.
- **Ask the agent**: the chat, with its sources, retrieval steps and notes.

## How RAG works in this pipeline

1. **Knowledge base** (`rag/loader.py`). The CN 2026 SKOS file is parsed with `lxml.iterparse`
   (`rag/nomenclature.py`) into **one chunk per HS-6 subheading**: chapter title + heading text +
   subheading text + the self-explanatory text + its CN-8 lines with their dash-group path, with
   `chapter`, `heading`, `subheading`, `language`, `source`, `edition_year` as metadata. BTI rulings
   are one chunk each (goods description + reasoning; metadata code, chapter, member state, validity),
   with holder names and addresses dropped at load time. The ICS2 lists are extracted from the official
   PDFs (`rag/rules.py`).
2. **Queries** (`rag/translate.py:build_queries`): every line, whatever its language, is searched with
   its raw text as typed, plus what the shipper confirmed (part, material, use) as a second query. Nothing
   is translated (feature 009): the embedding model is multilingual, and a 10-pair bilingual smoke test
   showed no gain from translating. Query expansion is one switch for all languages,
   `CARGOLINT_QUERY_EXPANSION` (off by default): when on, one structured call per line appends up to five
   English queries (synonyms, product category, material) and an optional HyDE-style sentence.
3. **Hybrid retrieval** (`rag/retriever.py`): BM25 over `rank_bm25` with a tokenizer that keeps HS
   codes in both `9617.00` and `961700` forms, plus cosine search in a persisted Chroma collection
   (`qwen/qwen3-embedding-8b`, 4096 dimensions), fused by **reciprocal rank fusion** (k = 60). When
   the shipper has a filing history, a second search restricted to those chapters is fused in as a soft
   boost (the trace shows it as the metadata filter). The Admin › Rules switch turns BM25 off for the
   vector-only baseline.
4. **Precedent leg** (`rag/retriever.py:precedent_codes`): the same query vectors are run against the index of
   EBTI ruling texts (`store/chroma-bti`); the rulings nearest to the queries vote for their HS-6 code with their
   RRF score, and up to three precedent codes join the candidate chunks, each tagged with its best-matching ruling
   (reference, member state, goods description). This is how residual "Other" subheadings such as `3926.90`, whose
   nomenclature text names no product, become reachable from a product description. Precedent codes are marked in
   the retrieval trace and cited as BTI sources; only rulings valid on the day may vote.
5. **Ranking** (`tools/classify_hs6.py`): the fused chunks, the fenced description, the flag result
   and the shipper's past codes go to the chat model, which returns up to three candidates with
   confidence and rationale as strict JSON.
6. **Validation in code**: every returned code must match `^\d{4}\.\d{2}$` **and exist in the
   nomenclature index**; unknown codes are dropped, subheading text and chapter are filled from the
   index, never from the model. If nothing survives, the line is "no valid candidate".
7. **Routing in code** (`agent/routing.py`): stop-word → ask the shipper; vague → ask the shipper below
   the ask floor (50) else review; OK → auto-accept when the HS-6 gate passes, else review. The gate
   (constitution 1.5.0) is the vote of the five nearest eligible EBTI rulings at or above a cosine
   similarity of 0.40: the top candidate passes when it is their majority with a share of at least
   0.5, and the review reason names the rulings, their countries and the candidate they support. The
   precedent override (constitution 1.6.0, feature 008) adds one case: when at least `OVERRIDE_MIN` of
   the five (by default 5, all of them) sit at the model's second or third candidate, that candidate is
   decided and auto-accepted with the note "rulings overrode the model: N of M agree on <code>"; the
   same agreement on a code outside the three candidates is only shown as a hint. It is on by default;
   `CARGOLINT_HS6_OVERRIDE=off` turns it off. Only when no ruling votes does the confidence decide, at
   or above the threshold. A line that was ever flagged, or updated by a shipper reply, is never
   auto-accepted — it becomes "ready to accept" and needs the clerk's click.

## The tool-calling loop

`agent/agent.py` builds a LangChain v1 agent (`create_agent`) with exactly seven tools: `parse_packing_list`,
`check_description`, `classify_hs6`, `lookup_precedent`, `apply_shipper_reply`, `classify_cn8` and `lookup_taric`. For every clerk
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
- `tests/ui/` — both pages through Streamlit's AppTest, on stores seeded in every line state
  (`tests/ui/harness.py`), with background jobs recorded instead of run and model calls counted; every clerk
  action on the 12-line sample returns within 1 s (`tests/ui/test_response_time.py`). A guard in
  `tests/conftest.py` makes any offline test that reaches OpenRouter fail instead of spending credits.
- `python -m tests.eval.walkthrough` — the scripted walkthrough of the 12-line sample (SC-001 of feature 005):
  AppTest drives the main page as a clerk would, with the shipper's answers scripted, and writes
  `tests/eval/walkthrough.json`. Offline on 2026-10-24: 57 clerk actions and 12 background jobs, every action
  under 0.07 s (1.94 s in total), all 12 lines accepted. `--live` uses the real model and runs only when asked.
  The clerk's own time is the author's timed run in the browser, recorded in
  `specs/005-decision-first-ui/quickstart.md` §2: 2 min 9 s from upload to export on 2026-10-24, under the
  5 minutes SC-001 allows.
- `pytest -m live` — three OpenRouter smoke tests (embeddings, structured output, price-table cost vs
  OpenRouter accounting) and the budget test (sample shipment + two follow-ups < €0.10).
- `python tests/eval/run_eval.py --sample` — the 20-line labelled set (5 vague, 3 stop-word, 12 clear
  with known codes) in both retrieval modes plus the 12-line sample. `--no-precedents` switches the precedent leg off for before-and-after comparisons.

Labelled-set results, `openai/gpt-4o-mini` + `qwen/qwen3-embedding-8b`. Baseline 2026-10-14 → with the precedent
leg (FR-051) over the full 73,899-ruling index, 2026-10-16:

| Mode | Flag accuracy | Top-1 (baseline → now) | Top-3 (baseline → now) | Flagged lines auto-accepted | Time |
|---|---|---|---|---|---|
| Hybrid (BM25 + vectors, RRF) | 20/20 | 10/12 → 10/12 | 11/12 → 12/12 | 0 | 32 s |
| Vector-only baseline | 20/20 | 9/12 → 11/12 | 10/12 → 12/12 | 0 | 20 s |

The precedent leg brings every expected code into the top-3 in both modes and fixes the two vector-only top-1
misses (hexagon bolts `7318.15`, leather handbags `4202.21`): a ruling that classifies the same goods outweighs
a near-neighbour subheading. Silicone mobile phone cases are the remaining top-1 miss: `3926.90` is now
proposed with five matching rulings, but the model ranks an Irish ruling for an iPhone protection case
(`4202.32`) or packaging (`3923.10`) above it, and the order flips between runs. That is a ranking problem,
no longer a retrieval problem; it is also a genuine EU debate (the full extract holds 20 phone-cover rulings
under `3926.90` and 17 under `4202.32`/`4202.92`), which the clerk now sees as two cited precedents. A run of
both modes costs €0.016. Sample routes matched the design illustration on 10/12 lines; the other two are
legitimate model confidences (LED desk lamp 95 → auto-accept, bare "Furniture" 40 → ask the shipper).

Retrieval alone (`python tests/eval/ragas_eval.py`, RAGAs-style context metrics against the reference chunk,
no LLM judge; `--no-precedents` measures plain retrieval), k = 6, 12 clear lines: context recall 92 % → 100 %
in both modes once the precedent leg's chunks count, context precision (MRR) 0.82 hybrid / 0.79 vector-only
(baseline 0.81 / 0.82), chapter hit 100 %. The phone-case chunk arrives as the seventh candidate, from the
rulings, never from the nomenclature text itself. A translator prompt asking for "queries of different kinds"
was tried the same day and reverted: it lowered plain-retrieval MRR to 0.65 in both modes without reaching
`3926.90`.

Scale (`python tests/eval/scale_check.py`, 100 generated lines, six workers): first progress step
after 2.2 s (1.6 s in the previous run; the aim is 2 s), all 100 lines checked in 159 s, of which the CN-8 step took
17 s and the TARIC step 9 s, none failed, €0.07; a 201-line file is rejected whole before any model call. (The first run took 484 s because every expansion query was embedded with its
own API call; the queries of a line are now embedded in one request and reused by the history boost.)

Live budget (`pytest -m live`): the 12-line sample plus two follow-up questions, with the CN-8 and TARIC steps =
70.7k tokens, 43 calls, €0.012; the check itself took 45 s (the budget is €0.10 and 60 s).

Manual checks (not automated): moving the Admin › Rules threshold slider re-routes lines instantly without a model
call; uploading a second file while a shipment is open asks for confirmation; the CSV/JSON downloads
open with Chinese text intact.

CN-8 and TARIC-10 (feature 004), measured on 2026-10-23 with the 2026-10-01 TARIC snapshot:

- **CN-8 top-1** (`python tests/eval/cn8_eval.py`, SC-002): 120 valid EBTI rulings, 10 from each of the twelve
  target chapters, fixed before any tuning. Each ruling's goods description is the line and its HS-6 the decided
  HS-6, and its own ruling is never a precedent. The target is 60 of 120. Tuning closed after three iterations;
  the full report is `tests/eval/cn8_eval.md`.

| Run | Top-1 | Written by rule | Written, wrong | To confirm | Asked the shipper | Cost |
|---|---|---|---|---|---|---|
| Iteration 1 (as built) | 100/120 | 119 | 19 | 0 | 1 | €0.033 |
| Iteration 2 (evidence and precedent rules) | 83/120 | 92 | 11 | 3 | 25 | €0.036 |
| Iteration 3 (word-level evidence, conflict-only precedent) | 91/120 | 103 | 12 | 3 | 14 | €0.035 |
| Validation run, no change since iteration 3 | 93/120 | 107 | 14 | 1 | 12 | €0.035 |

  Most wrong CN-8 codes written by rule cite an EBTI ruling that agrees with the wrong line, so no code rule can
  catch them; that is why a written CN-8 stays advice the clerk can overrule.
- **What the clerk sees equals the snapshot** (`python tests/eval/taric_ui_parity.py`, SC-004, no key): for the 20
  acceptance codes of feature 002 and origin China, the subdivisions and measures the page shows (`line_taric_view`, kind (b)
  and its "All measures") equal `lookup_taric`'s output, each measure in exactly one group: 20 of 20.
- **The sample with the CN-8 and TARIC steps** (`python tests/eval/run_eval.py --modes hybrid --sample`): the
  labelled set is unchanged (flags 20/20, HS-6 top-1 10/12, top-3 12/12, no flagged line auto-accepted), and the
  sample reports "SC-005: 0 unconfirmed writes". Of the seven auto-decided sample lines in that run, two were
  auto-completed (vacuum flasks 9617 00 00 00, phone cases 4202 32 10 00), four left the subdivision to the clerk
  (T-shirts 2, toy cars 3, earphones 2, O-rings 3) and one had trade-defence measures (bicycle frames 8714 91 10,
  nine subdivisions, three of them under anti-dumping duty); none was "not available". Routes matched the
  expected ones on 9 of 12 lines. The LED desk lamp asked for its material once its HS-6 came back at 95, the bare
  "Furniture" came back at 40 and went to the shipper, and the toy cars were written as 9503 00 95 instead of
  asking whether a motor is fitted.

**Feature 006 report**: [docs/reports/006-stability-baseline.md](docs/reports/006-stability-baseline.md) tells the
story of feature 006 for the capstone review. It covers how the run-to-run instability was measured, why the
auto-accept decision moved from the model's confidence to a vote of the nearest EBTI rulings at both code levels, and
the five-model comparison behind the switch to Gemini 2.5 Flash. It also states the trade-offs and open items, and
traces every number to the eval reports and commits.

**End-to-end eval** (`python tests/eval/e2e_eval.py`, feature 007): the 120 rulings of the CN-8 eval go through the
upload's own steps as rows of a file, cut at 300 characters as the parser cuts them. Each line takes the description
check, the HS-6 step and the CN-8 step with their vote gates, then the store's routes; a line left in review gets the
HS-6 its row pre-selects, as the clerk's Confirm would give it. With Gemini 2.5 Flash, 68 of 120 lines end with the
right CN-8 (run `e2e-stopword-fix`, 2026-10-26, against 64 on the majority of the three `e2e-baseline` runs); 56 are
auto-accepted, 7 of them wrongly, and 7 go to the shipper. In the baseline the firm stop-word list matched a term
anywhere in the text, as FR-008 originally specified. The rule now matches the goods name only, and FR-008 and FR-009
were corrected with the code: a listed term outside it ("T-shirts in various sizes") no longer locks a line, while a
goods name that is nothing but listed terms ("various goods", "parts") still does. The report is
`tests/eval/e2e_eval.md`.

**Precedent override** (feature 008): the HS-6 eval (run `hs6-override`) and the end-to-end eval (run `e2e-override`)
each made one paid run with the override on and replayed it with the override off from the same stored model answers
and rulings, so the two states differ only by the rule. Each line records whether the override fired, the candidate it
chose and whether the candidate the rulings supported was right. `--replay <results file> --override-min N`
recomputes a stored run at another minimum with no model call (runs `hs6-override-min5` and `e2e-override-min5`).

| HS-6 eval | Off | On at 4 | On at 5 |
|---|---|---|---|
| HS-6 right | 83/120 | 92/120 | 87/120 |
| End-to-end estimate (CN-8 iteration 12) | 74/120 | 82/120 | 77/120 |
| Auto-accepted | 67 | 81 | 71 |
| Wrong auto-accepts | 3 | 6 | 3 |
| Overrides fired (right HS-6) | – | 14 (11) | 4 (4) |

| End-to-end eval | Off | On at 4 | On at 5 |
|---|---|---|---|
| Right end to end | 67/120 | 74/120 | 69/120 |
| Auto-accepted | 57 | 64 | 59 |
| Wrong auto-accepts | 8 | 8 | 8 |
| Overrides fired (right HS-6) | – | 11 (10) | 4 (4) |

Every wrong override was a 4-of-5 one. Two of them are a pair of shoe rulings, IEBTIIENEN004-2024-BTI122 at 6402.99
and IEBTIIENEN004-2024-BTI128 at 6404.19: with each line's own ruling left out, the nearest other rulings point to the
other code, so at 4 of 5 the override turned both right answers wrong. At 5 of 5 every override chose the right HS-6:
end to end 67 → 69 of 120, the estimate 74 → 77, and wrong auto-accepts unchanged in both evals. The override ships on
at 5 of 5. The reports are `tests/eval/hs6_eval.md` and `tests/eval/e2e_eval.md`.

**Query expansion and Chinese input** (feature 009): retrieval no longer translates. Every line, in any language, is
searched with its raw text as typed, plus what the shipper confirmed; query expansion with HyDE stays, behind one
switch for all languages, `CARGOLINT_QUERY_EXPANSION`, off by default (constitution 1.7.0). Both evals take
`--expansion on|off`, which sets query expansion for the run over `CARGOLINT_QUERY_EXPANSION`, and `--lang en|zh`.
`--lang zh` runs 30 of the 120 lines, spread across the 12 chapters, in Chinese (`tests/eval/hs6_eval_zh.json`,
written once by the chat model as a Chinese shipper's packing-list lines and open to correction by hand), with the same
expected codes and the same leakage rule as their English lines. Three paid HS-6 runs with Gemini 2.5 Flash on
2026-10-27 were compared with the English baseline of feature 008, all four read with the precedent override off:

| HS-6 eval | Lines | Expansion | Top-1 right | Auto-accepted | Wrong auto-accepts |
|---|---|---|---|---|---|
| Chinese, run `zh-off` | 30 | off | 17/30 | 9 | 0 |
| Chinese, run `zh-on` | 30 | on | 17/30 | 15 | 2 |
| English, run `hs6-override-min5` (feature 008 baseline, not rerun) | 120 | off | 83/120 | 67 | 3 |
| English, run `en-on` | 120 | on | 81/120 | 64 | 3 |

The decision rule was fixed before the runs: expansion goes default on only if, in both languages, wrong auto-accepts
are no worse and top-1 is better. It fails in both. In Chinese top-1 stays at 17 while wrong auto-accepts rise from 0
to 2; in English top-1 falls from 83 to 81 with wrong auto-accepts unchanged. Expansion stays off. Run-to-run noise on
these evals is about 2 lines, as large as the top-1 and wrong auto-accept differences above. Each run's own results
file names its language and expansion, `tests/eval/hs6_eval_<run>_<lang>_expansion-<on|off>.json` (for example
`hs6_eval_zh-off_zh_expansion-off.json`); the report is `tests/eval/hs6_eval.md`, iterations 9 to 11.

Two changes to the description check were made alongside feature 009. A goods name of several listed terms is locked
only when nothing else in the description identifies the goods (FR-008): "metal box, steel, 30x20 cm" passes, "Toy
cars" alone does not (see the known weaknesses below). And a rule-list entry with no Latin letter and no Chinese
character is skipped, which drops two leftovers of the PDF extraction from the shipped ICS2 list, "1005" and a row of
symbols ending in "12", so a bare number no longer counts as a listed term.

**Eval-set notes**:
- **Cleanup**: six Swedish rulings in `tests/eval/cn8_eval_set.json` are still labelled `en`: SEBTITV-2026-01096,
  SEBTITV-2024-01658, SEBTITV-2024-01665, SEBTITV-2024-01674, SEBTITV-2026-09785 and SEBTITV-2026-09764.
  `tests/eval/make_cn8_eval_set.py` copies the labels from its source (`store/bti_docs.jsonl`), so rerunning it would
  undo the label fixes made by hand (the seven rulings relabelled `fr`, `cs` or `sv` in feature 009).

**Known issues**:
- **Sample line 10, "铝合金自行车架 / Aluminium alloy bicycle frames"** (browser check with the live model, 2026-10-24):
  it is auto-accepted as 9503 00 10 00 (wheeled toys) at 95 %; the correct HS-6 is 8714.91 (frames and forks of
  bicycles).
  - **Mitigation**: the clerk overrides it with "Change", picking 8714.91, or typing it under "Other HS-6 code…"
    when it is not among the three candidates, as in that run. The CN-8 and TARIC steps then run again for the new
    code, and the audit trail records the clerk's decision.
  - The offline recordings classify the line correctly, so the walkthrough and the offline tests do not show it.

## Continuous integration

`.github/workflows/tests.yml` runs the offline suite, `pytest -q`, on GitHub Actions on every push to any branch and on
every pull request to main (Ubuntu, Python 3.13). It needs no API key: the suite runs on fakes, and the four live tests
stay deselected. The paid evals are not part of CI: `tests/eval/hs6_eval.py` and `tests/eval/e2e_eval.py` are run
locally by hand, at about $0.20 (HS-6) and $0.27 (end to end) per run of the 120 lines.

## Demo deployment

A demo runs on Streamlit Community Cloud with a smaller knowledge base that the app downloads at its first start
(feature 011). The measurements and platform limits behind it are in `docs/deploy/streamlit-cloud-assessment.md`.

1. **Cut the demo store** from the local full build, after `python -m rag.loader` and `python -m rag.loader --taric`. No
   API call is made:

   ```bash
   python -m rag.demo_store --out ../cargolint-demo --rulings 5000 --zip ../cargolint-demo.zip
   ```

   The script:
   - copies the nomenclature index and the BM25 file;
   - chooses about 5,000 rulings: half under the HS-6 codes of the CN-8 eval set and of the sample files, the rest
     spread over the chapters;
   - copies their existing vectors;
   - packs `store/…` and `data/taric.jsonl` into one archive.

   It prints the archive's SHA-256 and size, an estimated 130 MB. The folder given to `--out` must be new or empty.
2. **Publish the archive** as a GitHub release asset, for example `gh release create demo-store-1
   ../cargolint-demo.zip`, and copy its download URL. A public release also publishes the TARIC snapshot. The Swedish
   Customs distribution has no formal licence, so check before publishing.
3. **Deploy** the repository on Community Cloud with `app.py` as the entry point. Choose Python 3.13 under Advanced
   settings: Community Cloud installs from `uv.lock`, which requires a Python below 3.14. Enter the secrets at the top
   level and as strings; Streamlit copies such secrets into the environment before the app starts, and the app reads
   them from there:

   ```toml
   OPENROUTER_API_KEY = "sk-or-…"         # a dedicated key with a credit limit set at OpenRouter
   CARGOLINT_APP_PASSWORD = "…"           # the demo password; leave it out for no password
   CARGOLINT_DEMO_STORE_URL = "https://github.com/<owner>/<repo>/releases/download/demo-store-1/cargolint-demo.zip"
   CARGOLINT_DEMO_STORE_SHA256 = "…"      # as printed by the script
   CARGOLINT_WORKERS = "3"
   CARGOLINT_DEMO_NOTICE = "on"           # the "Before you upload" notice: demo only, no personal data, export before leaving
   ANONYMIZED_TELEMETRY = "False"         # no usage pings from Chroma
   ```

   Reboot the app after changing a secret, since the settings are read once per process.

What to expect:
- **Download at every cold start.** At the first start, and after every sleep or reboot, the app downloads the archive
  with a spinner showing. It checks the SHA-256 before unpacking anything, and a wrong checksum stops the app with an
  error. Locally, with a store present or no URL set, nothing is downloaded.
- **Password first.** With a password set, the password field comes before everything else: without the password
  nothing is loaded and no model is called. The key's credit limit caps the spend even if the password spreads.
- **Memory**: an estimated 550–600 MB at rest with 5,000 rulings, and about 900 MB while a scanned PDF or photo is
  read. Community Cloud documents 690 MB to 2.7 GB.
- **Sessions are lost on sleep.** They live in memory only, so a shipment is lost when the browser session ends, when
  the app reboots, and when it sleeps after 12 hours without traffic. Export the CSV, the JSON or the audit trail before
  leaving.
- **More review than in the evaluation.** The demo holds about 5,000 of the 73,899 rulings, so fewer lines find rulings
  that agree with the model than in the evaluation figures above.

## Known weaknesses and next steps

- Confidence is model-estimated and only loosely calibrated against 20 labelled lines; it must not be
  read as a probability.
- Chinese product slang and brand-only names still miss; the hybrid index helps but does not solve it.
- Known limitation of the stop-word rule: a goods name of several listed words, such as "metal box" or "steel rods",
  is locked only when nothing else in the description identifies the goods, so "metal box, steel, 30x20 cm" passes,
  but on its own it is still locked, although the ICS2 guidance accepts names like "steel tubes". A single listed term
  is locked whatever follows it ("Toys, plastic"). Any word after the goods name other than filler counts as
  identifying, a listed one included, while a count of pieces ("20 ctns") does not. On the end-to-end eval set the
  change unlocks one line (XIBTI505060394, "A metal box with a hinged lid …"); no eval run has measured it yet.
- The precedent override runs at 5 of 5. At 4 of 5 it would give 7 more lines right end to end (67 → 74), at the cost
  of 3 more wrong HS-6 codes auto-accepted on the HS-6 eval (3 → 6), among them the shoe pair above. That trade-off is
  left for a later decision.
- Classification confusions remain where the nomenclature itself is subtle (protective phone cases vs
  packaging cases; aluminium bicycle frames landed in aluminium structures `7610.90` instead of
  `8714.91` in one live run, and in wheeled toys `9503.00`, steered by a ruling, in two app runs on 2026-10-23) —
  and the model occasionally auto-accepts such a wrong code at high confidence, which is why the threshold is
  adjustable and the audit trail exists. A wrong HS-6 accepted this way carries through: the CN-8 and the
  TARIC-10 under it can then be written by rule too.
- Precedent votes can point at a neighbouring code: for plastic household storage boxes the rulings vote
  `3926.90`/`3923.10` first and for steel bobbin cases `7326.90`. The model kept the right code in both cases,
  and the tag is presented as evidence, not as a verdict; the clerk sees the ruling and decides.
- The chat model can skip `lookup_precedent` (gpt-4o-mini did, before Gemini 2.5 Flash became the default); the
  completeness guard runs it, so results are
  complete, but the progress block then shows the step as "run by the app".
- BTI coverage: the twelve target chapters only (73,899 valid rulings with the full build, 192 with `--demo`). Rulings
  must be refreshed as they expire, and the full rulings index costs about 1.2 GB of RAM in the app.
- OCR on phone photos is the weakest input path (RapidOCR, PP-OCR models); quantities and values are
  not read from photos.
- State lives in the Streamlit session: nothing persists across restarts; one user, one shipment.
- The chat model, `google/gemini-2.5-flash` by default with thinking off (OpenRouter `reasoning: {enabled: false}`;
  `CARGOLINT_CHAT_MODEL`, and `CARGOLINT_REASONING=model` for a model without that parameter), is reached through
  OpenRouter; a 402 (credits) stops checks with a clear message.
- TARIC snapshot: full temporary stops are not applied; the companies behind additional codes are not
  named; Meursing agricultural components and sugar and flour additional duties are not represented, so
  composite agricultural goods show the base duty only; and conditional duties, such as company-specific
  anti-dumping rates, are shown as text but never evaluated, so the clerk decides which rate applies. The
  snapshot is loaded by hand, with no daily updates.
- CN-8 confidence is a model estimate, like the HS-6 one. A CN-8 written by rule can still be wrong when the cited
  ruling agrees with the wrong line (see the CN-8 evaluation below), so a written CN-8 is advice the clerk can
  overrule like any other. The evidence check proves that the quoted words are in the description, not that they
  state the deciding attribute: "Plastic toy cars" was once written as 9503 00 95 (without a motor) instead of
  asking whether a motor is fitted.
- The walkthrough measures machine time, not a first-time clerk's reading time; that comes from the author's timed
  run in the browser.
- "TARIC not available" is proven by fixture tests only: on the 2026-10-01 snapshot every CN 2026 line has at least
  one subdivision for China.

Roadmap, in order of customer value: sending the drafted shipper email and tracking the replies; a view of each
line's version history; duty calculation from the TARIC measures; SQLite persistence and multi-user access.

## Repository layout

```
app.py          Streamlit entry point        ui/        main_page, table, expand, view, actions, shipper_email, upload, runner, jobs (worker turns), admin, chat, replies
agent/          config, schemas, routing, prompts, llm (client factory + cost), agent (loop + guard), store
tools/          the seven tools, parsers, ocr, common (context + per-line runner)
rag/            loader (CLI), nomenclature (SKOS), bti (EBTI), rules (ICS2 PDFs), embeddings, retriever, translate, taric + taric_extract + pgp (TARIC snapshot), demo_store (hosted demo: cut and fetch)
data/           processed knowledge base, rule lists, shipper history (synthetic), sample lists (xlsx, gbk csv, text pdf, photo), labelled set, SOURCES.md
store/          Chroma vectors (nomenclature in chroma/, rulings in chroma-bti/), BM25 pickle, BTI document store (git-ignored; rebuilt by the loader)
tests/          unit, integration, adversarial, live, eval (run_eval.py, make_big_list.py), fixtures
```

## Data attribution

EU Combined Nomenclature 2026 (Publications Office / Eurostat) and the EBTI public extract are reused
under the Commission reuse policy (Decision 2011/833/EU, CC BY 4.0) — © European Union. ICS2 guidance
documents © European Commission. The TARIC snapshot comes from the Swedish Customs Tariff File Distribution
(free of charge, no formal licence published); the underlying data is EU TARIC from the European Commission.
Shipper history, the firm stop-word list and the sample packing list are
synthetic demo data.

The TARIC snapshot (`data/taric.jsonl`, inside the demo archive) is European Commission tariff data obtained through
Swedish Customs' file distribution service.
