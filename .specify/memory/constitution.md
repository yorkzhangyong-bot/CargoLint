# CargoLint Constitution

## Core Principles

### I. Guardrails Live in Code, Not in the Prompt (NON-NEGOTIABLE)

- Routing to `auto_accept`, `review` or `ask_shipper` MUST be computed by one deterministic
  function from the line's flag, the HS-6 gate below, whether the attribute that decides its CN-8
  is missing from the line text, and the CN-8 gate below. Routing MUST NOT be a tool, a model
  decision, or logic that exists only in the UI.
- At both layers the automatic decision MUST come from code-computed agreement with the k nearest
  eligible EBTI rulings, each counted once: the model's code (at the HS-6, its top candidate or,
  with the precedent override, its second or third) equals the rulings' majority code (the first
  six digits for the HS-6, eight for the CN-8) with a share at or above the vote threshold. A
  ruling is eligible when it is valid on the day and coded to the loaded
  nomenclature; for the HS-6 it MUST also be at least as similar to the line as the similarity
  floor. k, the share and the floor are named configuration constants. Behaviour at exactly the
  vote threshold and exactly the floor MUST be fixed in the spec and covered by a test.
- An unflagged line's HS-6 MUST be auto-accepted only when the HS-6 gate passes. The rulings'
  majority either confirms the model's top candidate or, with the precedent override switched on
  (`HS6_OVERRIDE`), overrides it to the model's second or third candidate when at least
  `OVERRIDE_MIN` (default 4) of the 5 nearest eligible rulings sit there. That candidate becomes
  the decided code, with the reason "rulings overrode the model: N of M agree on <code>", M being
  the rulings that voted (5 unless fewer are eligible). Three of five, or agreement on a code
  outside the model's top three, stays `review`; with the override switched on, a code outside
  the top three is shown as a hint, never chosen. `OVERRIDE_MIN` is a named configuration
  constant; behaviour at exactly `OVERRIDE_MIN` MUST be fixed in the spec and covered by a test.
  Otherwise the line goes to `review` with the competing rulings and their issuing countries as
  the reason, naming the model's candidate the rulings support when it is the second or third. A
  flagged (vague or stop-word) line MUST NOT be routed to `auto_accept`.
- A CN-8 MUST be written by rule only when the model's quote passed the evidence check, no cited
  ruling sits at another CN-8, and the CN-8 gate passes. Otherwise it stays a suggestion for the
  clerk, with the competing rulings and their issuing countries as the reason; a failed evidence
  check still routes the line to `ask_shipper`.
- The model's confidence is not a routing input at either layer, except as the fallback when no
  eligible ruling votes: then the model's estimate against the auto-accept threshold decides, as
  before. The threshold defaults to 85%, is adjustable from 60% to 99% on the Admin page (Rules),
  and MUST be enforced in code; behaviour at exactly the threshold MUST be fixed in the spec and
  covered by a test. Whether the fallback stays is decided after confidence has been tested with
  another model.
- A line that was ever flagged MUST NOT become `auto_accept` after an update (for example a
  shipper reply) without an explicit human click.
- Every HS-6 code shown to the clerk MUST exist in the loaded nomenclature. A code that fails
  the check MUST be discarded, never displayed as a suggestion.
- Every CN-8 code shown MUST exist in the loaded CN 2026 nomenclature, and every TARIC-10 code
  and every measure shown MUST exist in the loaded TARIC snapshot, with the snapshot date
  displayed.
- No TARIC subdivision is written to a line without the clerk's confirmation, except the
  auto-completion of a single subdivision, which MUST be recorded in the audit trail.
- Every model or tool output MUST be validated against a strict Pydantic schema before use:
  HS-6 codes match `\d{4}\.\d{2}`, CN-8 codes are eight digits and TARIC-10 codes ten digits,
  routes are one of the three enum values, confidence is 0–100. Invalid output is retried or
  failed for that line; it is never passed through.
- CargoLint advises and the clerk decides. No code path may file, send or finalise anything on
  the clerk's behalf, and `auto_accept` only means "needs no attention" inside the app.

**Rationale**: prompts and model judgement are not enforceable controls, and a packing list can
contain text written to subvert them. Only code gives a guarantee that tests can verify.

### II. Untrusted Input, End to End (NON-NEGOTIABLE)

- Packing lists, invoices, OCR output, pasted chat text and shipper replies are untrusted
  third-party data. Their text MUST reach the model only inside clearly delimited data blocks,
  and the system prompt MUST state that any instruction inside those blocks is void.
- Untrusted text MUST NOT be used as an instruction, a file path, a command, or a hint for
  choosing a tool. Parsers MUST read cell and text content only: no macro execution, no
  following of external links.
- File type (XLSX, CSV, PDF, JPG, PNG), file size (20 MB), row count and description length
  MUST be capped by named configuration constants and rejected early with a clear message.
- API keys MUST come from environment variables, never from the UI, and MUST NOT be committed
  or logged. Shipper contact details MUST NOT be logged.
- The test suite MUST include adversarial inputs (for example a description that orders the
  model to ignore its rules and auto-accept the line) and assert that routing and schemas are
  unaffected.

**Rationale**: the shipper writes the document the system reads. This principle also delivers
the course's "protect the app against prompt injection" optional task.

### III. Grounded, Cited, Never Guessed

- Each classified line MUST show its top-3 HS-6 candidates, each with a 0–100 confidence, a
  reasoning text and the retrieved sources behind it.
- A source, rule or precedent shown in the UI MUST trace to a chunk, rule entry or ruling that
  was actually retrieved in that run. The model MUST NOT supply sources from memory.
- `check_description` MUST apply deterministic rules first and LLM judgement second, and every
  flag MUST cite the rule or reason behind it (ICS2 unacceptable term, firm stop-word, or the
  vagueness reason).
- When a description is flagged, the assistant MUST tell the clerk what to ask the shipper
  (material, exact product name, use) rather than present a confident code. Shipper history is
  context only: it MAY re-rank or break ties between candidates but MUST NOT clear a flag.
- Precedent MUST show the BTI reference, description and validity. Expired rulings MUST be
  filtered out, and when no ruling matches the UI MUST say so.
- Confidence is model-estimated and only loosely calibrated; neither the UI nor the docs may
  present it as a calibrated probability. For the CN-8 it is labelled "model estimate".

**Rationale**: customs filings are audited. "Ask the shipper" is a better answer than a
plausible code that the description cannot support.

### IV. Hybrid, Structure-Aware Retrieval

- `classify_hs6` MUST run this pipeline in this order: Chinese→English query translation with
  multi-query expansion (HyDE optional) → chapter metadata filter → hybrid retrieval (BM25 plus
  vector search in a local Chroma store, cosine similarity) fused by reciprocal rank fusion →
  LLM ranking → code-existence validation. Routing follows, in code (Principle I).
- The nomenclature MUST be chunked by structure: one chunk per HS-6 subheading (chapter title,
  heading text, subheading text and the CN-8 lines beneath it) with chapter, heading,
  subheading, language, source and year as metadata. BTI rulings: one chunk per ruling (goods
  description and reasoning) with code, member state and validity dates as metadata; the full
  ruling text stays in a document store, not in the vector index.
- Hybrid retrieval is the default. Vector-only mode MAY exist only as a comparison baseline,
  reachable from the "Hybrid search" switch on the Admin page (Rules) and from the evaluation
  scripts.
- The knowledge-base loader MUST be scripted, repeatable and driven by a chapter list, so that
  adding chapters means re-running it with a longer list, not changing code.
- The Admin page (Data) MUST state truthfully what the knowledge base covers and when it was last
  updated.

**Rationale**: HS code numbers and exact product terms retrieve poorly with vectors alone,
Chinese input needs translation, and one chunk per subheading mirrors how the nomenclature is
organised.

### V. Single-Purpose, Schema-Typed Tools

- The agent exposes a small set of single-purpose tools. Each feature's plan lists the tools it
  adds or changes, with a one-line justification for every addition.
- Every tool MUST do one job, declare Pydantic input and output schemas, and wrap plain Python
  functions that can be tested without an LLM and without a running Streamlit session.
- A failure on one line MUST NOT abort the shipment. The line is surfaced as needing action
  with the failure reason; it is never silently dropped or auto-accepted. Transient API errors
  MUST be retried a bounded number of times before the line is failed.
- `apply_shipper_reply` MUST re-run check, classify and precedent for the referenced line only,
  and store the result as a new line version.
- Line versions and the audit log are append-only. Each route decision and each human click is
  recorded with time, line, previous and new value, and the rule or user action responsible.
  The MVP UI shows only the current version.

**Rationale**: small typed tools are testable and easy to explain, per-line isolation keeps one
bad cell, scan or reply from spoiling a shipment, and an append-only trail is what a customs
auditor can follow.

### VI. A Native Streamlit UI That Shows Its Work

- The UI MUST be built from native Streamlit components in the visual language of the design
  canvas. Custom components or CSS are allowed only where no native component works, and the
  plan MUST say where and why.
- The UI MUST show context, sources, tool results and progress, split between two pages:
  - the main page, which has no sidebar: progress while a check runs (each line's code fills in
    and its running step shows), the routing counts in the summary bar, the evidence behind each
    decision in the expanded row (candidates, confidence, EBTI precedent, TARIC measures), and
    the CSV and JSON export under the table;
  - the Admin page: sources and retrieval steps (Ask the agent), per-shipment tokens and cost
    (Cost), and the knowledge-base statement (Data).
- The decision table MUST be rendered from the line store, each line with a status that names the
  decision it needs. It MUST NOT be reconstructed from model prose.
- Code-enforced guardrails MUST be visible: where auto-accept is locked for a line, the control
  is shown disabled with the reason.
- Token usage and cost per shipment MUST be calculated and shown on the Admin page (Cost).
- Chinese and English text are shown together, UI and assistant text are in English, and Chinese
  glyphs MUST render correctly. The shipper email draft MAY be in Chinese.
- The in-app "What I can and cannot do" statement MUST stay true to Principles I–III.
- The main page and the Admin page, with their minimum elements, are listed under "UI Design
  Contract".

**Rationale**: the clerk must see why a line was flagged, which tool ran and where an answer
came from, in a layout that feels native to Streamlit.

### VII. Test-First and Measured (NON-NEGOTIABLE for guardrail code)

- Tests MUST be written first and seen to fail for the deterministic code that carries the
  guardrails: routing and threshold enforcement, the HS-6 and CN-8 ruling-vote gates and the
  precedent override, with the HS-6 similarity floor and the fallback when no ruling votes, the
  flagged-line lock,
  code-existence validation, schema validators, rule matching, file parsing and caps,
  reciprocal rank fusion, BTI expiry filtering, the single-line scope of `apply_shipper_reply`,
  and the prompt-injection fixtures. These tests are mandatory deliverables and override the
  "tests are optional" default of the tasks template.
- Unit tests MUST run offline without API keys; model and embedding calls are stubbed or
  replayed from recorded fixtures. Live-model checks are a separate, explicitly marked run.
- A hand-labelled set of 20 lines (5 vague, 3 stop-words, 12 clear lines with known codes) MUST
  exist before `classify_hs6` is built. It is used to measure top-1 and top-3 hit rate and to
  compare vector-only with hybrid retrieval. A RAGAs evaluation on 20–30 lines is a stretch goal.
- Each named error scenario MUST be covered by a test or a documented manual check: scanned PDF
  with bad OCR, mixed-language cells, a code that does not exist, a model returning the wrong
  schema, a shipper reply that contradicts the file, an API failure with retry, and an
  unsupported or oversize file.

**Rationale**: LLM applications regress silently. The guardrails are the product's safety net,
so their tests must not depend on a model.

## Product Scope, Architecture & Technology Constraints

### Product and course context

CargoLint is a linter for packing lists. Before a forwarder files an ICS2 house declaration (ENS)
for China→EU sea freight, it flags descriptions that customs will reject, suggests HS-6
subheadings with confidence, reasoning and precedent, and routes each line to auto-accept, human
review or ask the shipper. The user is a customs/export clerk at a 10–40-person Hamburg
forwarder or consolidator, working with Chinese, English or mixed input.

The project is the Turing College AI Engineering Sprint 2 assignment, so its requirements are
constraints. All MUST be met: a domain knowledge base; standard retrieval (embeddings, chunking,
similarity search); advanced RAG (query translation, structured retrieval); at least three
domain tools; domain-specific prompts, responses and security; LangChain with OpenRouter; error
handling and input validation; and an intuitive UI that shows context, sources, tool results and
progress. The chosen optional tasks (target: two medium and one hard) are prompt-injection
protection, token and cost display, and hybrid search. Multi-language support is inherent in the
design, and RAGAs evaluation is a stretch.

### Out of scope for the MVP

These MUST NOT be built, and the UI MUST NOT imply they exist:

- a line version-history UI (versions are stored, only the current version is shown);
- any "Import declaration (ATLAS)" flow: ICS2 house (ENS) is the only supported filing type;
- sending anything to a shipper or to a customs system;
- persistence beyond the Streamlit session, accounts and multi-user access (SQLite is roadmap).

Drafting an email to the shipper is in scope since v1.3.0: the app fills fixed string templates,
in English or Chinese, with the open questions, without a model call, and the clerk copies the
text into their own mail program. Sending it stays out of scope.

### Architecture

Flow: clerk inputs (packing list or invoice as xlsx, csv, pdf or photo; one typed line; an
updated description; questions in the Admin page's chat) → Streamlit UI (main page: header,
upload, summary bar and decision table with expanded rows; Admin page: Rules, Data, Cost,
Quality, Ask the agent) → LangChain agent with its LLM via OpenRouter → seven tools → data.
Admin settings reach the agent as explicit parameters; the agent writes per-line results and
versions to the line store; the decision table reads from it.

| Tool | Backed by |
|------|-----------|
| `parse_packing_list` | file parsers: openpyxl/pandas, pdfplumber and OCR, ZH/EN split, caps |
| `check_description` | rule lists: ICS2 unacceptable terms, firm stop-words, vagueness check |
| `classify_hs6` | RAG: ZH→EN translation, BM25 and embeddings fused by RRF, Chroma |
| `classify_cn8` | CN 2026 eight-digit lines under the decided HS-6; BTI rulings with a CN code as precedent |
| `lookup_precedent` | BTI rulings, local, indexed by subheading |
| `lookup_taric` | TARIC snapshot: subdivisions and measures for a CN-8 and an origin |
| `apply_shipper_reply` | line store: versions, routes, audit log (`st.session_state` in MVP) |

Invariants:

- Dependencies point one way: `app.py` (UI) → `agent/` → `tools/` → `rag/`, parsers, rule lists
  and the line store. The UI MUST NOT call the model or retrieval directly, and domain logic
  MUST be importable and testable without Streamlit.
- All chat and embedding calls MUST go through one OpenRouter-configured client factory that
  records token usage, so retries, cost display and test stubs live in one place.
- Line data MUST be read and written only through one line-store module, so the session-state
  backing can later be replaced by SQLite without touching tools or UI.
- The system prompt is customs-specific and lives in `agent/` as a named template. Guardrails
  (Principles I and II) live in `agent/` and `tools/` code, not in prompt text.

### Technology stack

Fixed for the MVP; a deviation needs a Complexity Tracking entry. Python 3.11+; Streamlit;
LangChain v1 (agent and tools); OpenRouter through the OpenAI-compatible SDK for chat and
embeddings; Chroma (persisted locally) and `rank_bm25`; openpyxl and pandas; pdfplumber;
Tesseract or PaddleOCR (Chinese and English) for scans and photos; Pydantic; pytest; RAGAs
(stretch).

### Knowledge-base sources

EU Combined Nomenclature 2026 (Commission Implementing Regulation (EU) 2025/1926, Annex I: the
full HS 2022 six-digit structure plus EU eight-digit codes); EBTI rulings for chapters 39, 42,
61–64, 73, 84, 85, 94, 95 and 96; the ICS2 guidance on acceptable goods descriptions and the
updated ICS2 stop-word list; the firm stop-word list (hand-written, 32 terms in the demo);
shipper history (synthetic demo data); the EU TARIC from the Swedish Customs Tariff File
Distribution (distr.tullverket.se/tulltaxan), used only for digits 9 to 10 and measures, never
embedded or indexed. Download locations are listed in the intro, section 10.

### UI Design Contract

The design canvas `CargoLint — MVP screens.html` (repository root) is the source of truth for
styling in Streamlit's visual language. Since v1.3.0 the layout of the two pages follows feature
005 (`specs/005-decision-first-ui/`) and its wireframes ("CargoLint UI redesign — wireframes"),
which replace the canvas's two screens. `CargoLint_Project_Intro.md` is the source of truth for
scope and behaviour. A conflict between them MUST be resolved in the spec, not silently in code.
The inventory below is the minimum: cosmetic changes need no amendment, but removing or relocating
a listed element needs a spec change.

- Styling: native Streamlit theme with the canvas accent (`#1D4FB8`); Source Sans 3 for text,
  Source Code Pro for codes and numbers, a CJK-capable font for Chinese. Each line's status is a
  coloured dot with the decision it needs: green "Ready" or "Accepted", yellow "Pick: …" or
  "Confirm: …", red "Ask: …". Confidence is a percentage with a bar, shown only inside an expanded
  row; the CN-8's is labelled "model estimate". "Needs action" means any yellow or red line.
- Main page, with no sidebar:
  - Header: CargoLint; the open file's name and line count; the origin field (two letters, CN by
    default; a change re-applies the TARIC rules without a model call and shows a toast); the link
    to the Admin page.
  - Upload, before a file is open: a drop zone (20 MB limit, XLSX/CSV/PDF/JPG/PNG); "Try the sample
    invoice" (the bundled sample of 12 lines, 6 needing action); "Check one line" for a single
    description; and the empty table.
  - Summary bar, after a check: "N lines checked in T s · A ready · B need a pick · C need the
    shipper", a green, yellow and red split bar, and "Accept all K ready" for batch acceptance of
    the green lines.
  - The single decision table: # · Description as filed (Chinese and English) · Code (the 10-digit
    TARIC code, undecided digits as underscores) · Status · Action ("Choose" or "Update"). A line
    expands in place into one of three kinds:
    - (a) choose the HS-6 or CN-8 from the top candidates, with confidence bars and EBTI precedent;
      for the HS-6 and the CN-8, the nearest rulings behind the vote with their issuing countries,
      and for the HS-6 the candidate they support and, when the precedent override decided the
      line, which candidate was chosen, with the issuing countries of the rulings that agree; with
      the override switched on, a code outside the top three is shown as a hint;
    - (b) choose the TARIC-10 subdivision, with duty and anti-dumping columns, all measures and the
      EU TARIC link;
    - (c) ask the shipper: the question, the reason, "Copy question", the description to update and
      "Re-check line".
  - Under the table: "Export CSV", "Export JSON", "Draft shipper email" (a text block from
    templates, English or Chinese, copy only) and "+ Check one more line".
- Admin page, for the operator and course evaluators, reached from the header link, with a left
  navigation:
  - Rules: the auto-accept threshold, used at either layer only when no eligible ruling votes
    (60–99, default 85), and the hybrid-search switch (on by default);
  - Data: the EBTI ruling count, the TARIC snapshot date and source, the model, and the
    knowledge-base last-updated date;
  - Cost: tokens and cost for this shipment and for the session;
  - Quality: the latest evaluation runs and the audit trail export;
  - Ask the agent: the chat, with the Sources, Retrieval steps and Assistant notes of each check,
    and the "What I can and cannot do" statement.

## Development Workflow & Quality Gates

- **Spec Kit flow**: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`. Specs describe the clerk's
  workflow and outcomes, not frameworks. `/speckit-analyze` SHOULD be run before implementation
  because it is the only automated check for constitution conflicts across spec, plan and tasks.
- **Priority**: core course requirements first, the chosen optional tasks second, stretch work
  (RAGAs, the vector-only versus hybrid write-up) last. Stretch work MUST NOT displace or delay
  core requirements; the MVP budget is 20–25 hours.
- **Build order**: plans SHOULD follow the intro's sequence: labelled test set; knowledge-base
  loader; `classify_hs6` end to end, measured on the labelled set; `check_description`, routing
  and `lookup_precedent`; Streamlit UI; `parse_packing_list` and `apply_shipper_reply`; security
  pass, cost display, export, README and tests. This measures the riskiest part (retrieval
  quality) before the UI builds on it. A different order needs a recorded reason.
- **Code organisation**: `app.py`, `agent/` (agent, prompts, routing rules), `tools/`, `rag/`
  (loader, retriever, translation), `data/`, `store/`, `tests/` and `README.md`. Public
  functions are type-annotated and Pydantic models define every boundary.
- **Data and privacy**: each dataset in `data/` is recorded with its source, version and
  retrieval date. Demo data is labelled as such, and no real shipper data or contact details
  are committed.
- **Definition of done** for any feature: the Principle VII tests pass offline; the Constitution
  Check is re-run and clean; the UI matches the UI Design Contract for the elements it touches; no
  secrets are in the repository; the README is updated.
- **Evaluation readiness**: the README MUST explain how RAG works in this pipeline (translation
  → hybrid retrieval → ranking → validation), the tool-calling loop, the security measures, the
  named error scenarios, and how to rebuild the knowledge base and run the tests. It MUST also
  give an honest list of weaknesses and next steps: confidence is only loosely calibrated,
  Chinese slang and brand terms still miss, BTI coverage is limited to the exported chapters,
  OCR on phone photos is the weakest input path, and state is lost on restart.

## Governance

This constitution supersedes other practices and the defaults of the Spec Kit templates in this
repository. `CargoLint_Project_Intro.md` supplies background, scope and requirements, the design
canvas supplies styling, and feature 005's wireframes the layout of the two pages; none may
contradict this document.

**Amendment procedure**: every change is made through `/speckit-constitution`, states what
changes and why, bumps the version, updates the last-amended date, and ends with a consistency
review of the dependent artefacts (plan and tasks template defaults, existing specs, plans and
tasks). The project author approves every amendment. Principles I, II and VII, and every item in
"Out of scope for the MVP", can be relaxed only by amendment, never by a plan-level exception.

**Versioning policy**: semantic versioning. MAJOR: a principle or guardrail is removed or
redefined in a backward-incompatible way. MINOR: a principle or section is added, or guidance
is materially expanded. PATCH: clarifications, wording and typo fixes.

**Compliance review**: every plan MUST contain a Constitution Check with one gate per principle
(I–VII), passed before research and re-checked after design. A violation is allowed only when
recorded in Complexity Tracking with the reason and the simpler alternative that was rejected.
A constitution conflict found by `/speckit-analyze` is CRITICAL and blocks implementation until
the spec, plan or tasks change. Each feature is closed against the Definition of done above.

**Keywords**: MUST and MUST NOT are mandatory; SHOULD is a default that needs a recorded reason
to depart from; MAY is optional.

**Amendment log** (earlier amendments are in the git history of this file):

- 1.4.0 (2026-10-25): the CN-8 auto-accept gate moved from the model's confidence to
  code-computed agreement with the five nearest eligible EBTI rulings (Principles I, III and VII,
  and the UI Design Contract). Reason: in feature 006's evaluation the model gave a CN-8
  confidence of 85 or more in 359 of 360 outputs, so the threshold carried no information, while
  the unweighted vote of the five nearest rulings cut wrong auto-accepts from 38 to 15 over three
  runs and lost 9.3 % of the correct ones (`tests/eval/cn8_vote_analysis.md`, iteration 10). The
  Admin threshold now governs the HS-6 step only.
- 1.5.0 (2026-10-26): the HS-6 auto-accept gate moved from the model's confidence to the same
  code-computed agreement with the five nearest eligible EBTI rulings, with a similarity floor of
  0.40 below which a ruling does not vote (Principles I and VII, and the UI Design Contract).
  Reason: in feature 006's HS-6 baseline the model gave its top HS-6 a confidence of 95 on about
  100 of 120 lines, right or wrong, so the threshold auto-accepted 137 wrong HS-6 codes over three
  runs, and 51 of the 64 lines that ended wrong went wrong at the HS-6; the vote gate cut wrong
  auto-accepts to 7 over three runs and lost 33 of 186 correct auto-accepts (17.7 %)
  (`tests/eval/hs6_eval.md`, iterations 1 and 2). The Admin threshold now applies at both layers,
  and only when no eligible ruling votes. The default chat model moved from gpt-4o-mini to Gemini
  2.5 Flash after a five-model comparison on the HS-6 eval (`tests/eval/hs6_eval.md`), and end to
  end rose from 56 to 74 of 120 (majority results, Gemini at both layers: HS-6 iteration 4 with
  CN-8 iteration 12).
- 1.6.0 (2026-10-26): the precedent override at the HS-6 (feature 008; Principles I and VII, and
  the UI Design Contract). With `HS6_OVERRIDE` on, at least `OVERRIDE_MIN` (4) of the 5 nearest
  eligible rulings at the model's second or third candidate decide that candidate and auto-accept
  it with the note "rulings overrode the model: N of M agree on <code>"; 3 of 5, or agreement
  outside the top three, stays review. The switch ships off until the HS-6 and end-to-end evals,
  each comparing the switch on and off on the same stored model answers, show more lines right
  end to end and no more wrong auto-accepts.

**Version**: 1.6.0 | **Ratified**: 2026-10-14 | **Last Amended**: 2026-10-26
