# Implementation Plan: Retrieval and Evidence

**Branch**: `014a-retrieval-evidence` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014a-retrieval-evidence/spec.md`, with its clarifications of 2026-11-18
(three from the coordinator, two from the author during clarify, and the author's answers to the plan's questions A
and B). The facts about the store, its languages and the vote are in the spec's Background and in
[research.md](research.md).

## Summary

The feature changes which rulings reach the HS-6 step and how they are shown; the classification prompt stays as it is.

- **Every chapter** (`agent/config.py`, `rag/bti.py`, `rag/refresh_ebti.py`, `rag/loader.py`): the setting
  `CARGOLINT_EBTI_CHAPTERS` (default `all`) drives the refresh, the loader and `rag.bti`; the source version says
  "all chapters". The local store is rebuilt with every chapter by one refresh run that reuses the current store's
  vectors.
- **The vote within the candidates' chapters** (`tools/classify_hs6.py`): after the ranking, a second ruling search
  per query vector with the candidates' chapters as its filter feeds the unchanged `hs6_voters`; the candidate proposal
  keeps searching every chapter. The line records the chapters searched and those not indexed (`RulingScope`), from
  the knowledge base's `indexed_chapters`, counted when it opens.
- **Truthful captions** (`ui/view.py`, `ui/expand.py`): block 3 says "No rulings indexed for chapter NN." or "No
  relevant rulings found." from the line store, in place of "No ruling was within the similarity floor." and the
  misleading "0 of m agree". Relevant means eligible to vote; the floor stays 0.40 until the after-runs' replays say
  otherwise.
- **Citation notes** (`tools/classify_hs6.py`, `ui/view.py`): each candidate's reasoning is scanned for ruling
  references; a retrieved ruling at another HS-6, or a reference not retrieved, gets a note after "Why: …". No routing
  effect, no CSV change.
- **Customs wording** (`rag/translate.py`, `rag/rules.py`): behind `CARGOLINT_CUSTOMS_WORDING` (off, and off when
  this feature merges), one cached model call per line, separate from query expansion, rewrites the line, in any
  language, into customs wording in the store's main language (German), with reviewed glossary renderings applied
  first; the rewrite joins the HS-6 step's two ruling searches only, merged with the raw text's hits; it is stored on
  the line version and shown in block 1. The nomenclature search and the CN-8 step's ruling search keep the raw text
  (research R-16).
- **Measurement first** (`tests/eval/hs6_eval.py`, `tests/eval/hs6_eval_coolant.json`): the eight coolant lines and
  `--set coolant` come before any product change; the baseline runs; after the implementation and the rebuild, the
  after-runs compare the switch off and on; every run has query expansion off; `--replay --floor` tunes the floor
  without model calls; the pull request reports the difference.
- **Constitution**: one amendment in this pull request, through `/speckit-constitution`: "Knowledge-base sources"
  names all chapters and the chapter setting instead of the twelve (MINOR, 1.11.0, confirmed by the author).
  Principle IV is not amended.
- **Housekeeping**: `docs/backlog.md` entry 1 marked done; README and `.env.example`.

## Technical Context

**Language/Version**: Python 3.11–3.13 (a `.venv` in the feature worktree, see "Store and environment")

**Primary Dependencies**: no new package. Chroma (`langchain_chroma`, `chromadb`) for the chapter-filtered search (its
`$in` filter on the `chapter` metadata every ruling vector carries), the OpenRouter client of `agent/llm.py`
(`StructuredCaller`) for the rewrite, Streamlit native elements (`st.caption`, `st.markdown`).

**Storage**: unchanged layout. `store/` (the ruling index, `bti_docs.jsonl`, `index_meta.json` with the new source
version text); `build/ebti-<date>/` for the rebuild (git-ignored); `data/rules/customs_glossary.json`, optional and
absent by default; `tests/eval/hs6_eval_coolant.json` and the coolant set's results, history and report files. The
line store (`st.session_state`) gains `ruling_scope`, `customs_wording` and per-candidate `citation_notes` on the line
version (data-model.md).

**Testing**: pytest, offline (`pytest -q`; live tests deselected). Ruling searches run on `InMemoryVectorSearch` over
small hand-made vectors with `chapter` metadata (the pattern of `tests/integration/test_hs6_vote_gate.py`); model
answers are stubbed or recorded (`tests/fakes.py`); UI captions through AppTest with `tests/ui/harness.make_kb`, a
real `KnowledgeBase` that derives `indexed_chapters` and `main_language` from its rulings; the refresh as feature 013's
tests run it (a tiny extract built in the test, now with rows in several chapters, a tiny previous store,
`FakeEmbeddings`, the fake release service); the evaluation's coolant scoring and floor replay on hand-written rows.
A prompt-injection fixture for the rewrite joins `tests/adversarial/`.

**Target Platform**: the author's laptop (Windows) for the live steps; Streamlit Community Cloud runs the same code
with the demo store (5,000 rulings) and the switch off.

**Project Type**: the existing single Streamlit project with its scripts and evaluation scripts.

**Performance Goals**: the HS-6 step adds one nearest-neighbour query per query vector (milliseconds), and with the
switch on one small model call per new line text (cached). The rebuild embeds only rulings outside the current store:
about 360 tokens, $0.0000036 and 39 KB of index per ruling (research R-02); the count is logged before the embedding.

**Constraints**:
- the ranking prompt, its input and the CN-8 and TARIC steps are unchanged; the raw text stays the input of every
  model prompt but the rewrite's own, the line's description and the CSV export; the CN-8 step's ruling search keeps
  the raw text and its HS-6 scope, with no chapter filter (research R-16);
- the rewrite is its own call, prompt, cache and switch, never merged into query expansion; every evaluation run of
  this feature passes `--expansion off`, so that the rewrite's off/on difference is its effect alone (research R-10);
- the rewrite's switch stays off by default when the feature merges (FR-026);
- routing is unchanged (`route_line`, `hs6_gate`); the new fields are never routing inputs;
- the vote's rules and named constants stay; `HS6_VOTE_MIN_SIMILARITY` changes value only on the after-runs' evidence
  with the author's approval, and exactly the floor counts at any value;
- the main checkout `C:\ai\CargoLint` is never written by this feature's tasks (see "Store and environment");
- every touched file is LF in this worktree (checked with `git ls-files --eol` on 2026-11-18) and stays LF; new files
  are LF, UTF-8 without a byte-order mark;
- native Streamlit only; no CSS (constitution 1.10.0);
- `tests/eval/e2e_eval.py` keeps working: the functions it imports from `hs6_eval.py` keep their names and behaviour.

**Scale/Scope**: two settings and one parser in `agent/config.py`; three models and three fields in
`agent/schemas.py`; one copy line in `agent/store.py`; the vote search, `ruling_scope` and `citation_notes` in
`tools/classify_hs6.py`; the rewrite, its prompt, cache and glossary matching in `rag/translate.py`; the glossary loader
in `rag/rules.py`; `indexed_chapters`/`main_language` helpers in `rag/bti.py` and `KnowledgeBase`; the chapter setting
in `rag/refresh_ebti.py`, `rag/loader.py` (and its exit 2 on a bad setting), `rag/bti.py`; captions and notes in
`ui/view.py`, three call sites in `ui/expand.py`, the queries line in `ui/chat.py`; `--set`, `--customs-wording`,
`--replay --floor` and the new row fields in `tests/eval/hs6_eval.py`; one new eval set; about eight new test files and
additions to six; README, `.env.example`, `docs/backlog.md`, the refresh script's docstring; the constitution's
"Knowledge-base sources" through `/speckit-constitution` (FR-031).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution 1.10.0. The
feature makes one amendment, to "Knowledge-base sources" (FR-031, the author's answer to the plan's question B), and
none to any principle or guardrail.

| Principle | Check | Status |
|---|---|---|
| I. Guardrails live in code | Routing is untouched: the same `route_line`, `hs6_gate`, override, flagged-line lock, code validation and schema validation. The HS-6 vote keeps its definition of an eligible ruling (valid on the day, coded to the loaded nomenclature, at or above the floor) and its named constants; what changes is where its k nearest are searched, the candidates' chapters, a search scope like the CN-8 vote's (searched only under the decided HS-6 since features 004 and 006), not a new eligibility rule. Caveat recorded: the scope comes from the model's own candidates, so rulings of other chapters can no longer stop a wrong chapter; SC-004 measures it, and a failure is reported, not worked around (clarification 1). Exactly the floor counts and is tested; a new floor value comes only from the after-runs with the author's approval. Block 3's captions read the vote and the recorded chapter facts from the line store. | Pass |
| II. Untrusted input | The line reaches the rewrite only inside `fence(...)`, and its system prompt declares instructions inside void; an injection fixture covers it. The rewrite's output is validated (`WordingOut`) and used only as a search query and a displayed, escaped caption: never an instruction, a path or a tool hint. The glossary is a reviewed project file, outside the data block. The key stays an environment variable. | Pass |
| III. Grounded, cited | Every ruling shown still comes from that run's searches; the vote's rulings now come from the candidates' chapters. The citation note marks a reasoning's reference that was not retrieved in that run as "not a source", and one at another code with its real HS-6, so the model's text can no longer pass a ruling off as support. Each ruling's stored code is what votes (the vote never takes a code from the model). "When no ruling matches the UI must say so": the two new captions say why. | Pass |
| IV. Hybrid retrieval | The nomenclature search is unchanged (raw text first, then what the shipper confirmed, expansion as before, hybrid, RRF). The rewrite fits as shipped: it is added after the raw text and only to the ruling searches, the same for every input language, under its own switch, off by default and off when this feature merges, as query expansion is. Turning its default on would put a model-written translation into every line's search by default, against "no … translation step" and "a switch to be measured, not a default"; that is the author's later decision on the after-runs' evidence (FR-026's criterion), with a Principle IV amendment if the change needs one (plan question B); FR-026 keeps the switch off here. The loader stays scripted and chapter-list driven, now with `all` as the default list; Admin › Data states the chapters covered through the source version. | Pass |
| Knowledge-base sources | The text names the twelve chapters, which indexing all chapters makes untrue. Amended in this feature through `/speckit-constitution` (FR-031), as the governance procedure requires: version bump to 1.11.0 (MINOR, confirmed by the author), last-amended date, amendment-log entry, consistency review; the author approved the wording in plan question B. Done after the implementation, before the pull request. | Amendment in scope (FR-031) |
| V. Typed tools | No tool added. `classify_hs6` changes (contracts/classify-hs6.md): the vote's search scope, the optional rewrite, the citation notes; justification: the backlog's retrieval and evidence items, all inside the one tool that retrieves for the HS-6. New pure functions (`parse_chapter_setting`, `ruling_scope`, `citation_notes`, `customs_wording`, `glossary_matches`) are testable without a model or Streamlit; a failed rewrite fails one line, not the shipment. | Pass |
| VI. Native UI | Block 3's caption changes wording; block 2's "Why: …" caption carries the notes; block 1 gains one caption with the rewrite (the author's request, clarification 5); the Admin Retrieval steps' queries line lists the rewrite. All `st.caption`/`st.markdown`, no CSS, no HTML. The UI Design Contract's inventory is a minimum: nothing is removed or moved, so no amendment. Every text is read from the line store. | Pass |
| VII. Test-first | Tests first, seen failing, for the guardrail-carrying and clerk-facing code (FR-030): the settings, the scoped vote and its floor and share boundaries with the leave-one-out exclusion, the relevance boundary, the indexed chapters, each caption state, the citation check, the rewrite's switch, scope, merge, language, cache, glossary and injection fixture, the coolant scoring and the floor replay. All offline. The live steps are the author's and marked as such. | Pass |
| Architecture | Dependencies keep their direction (`ui` → `agent` → `tools` → `rag`); the rewrite lives beside query expansion in `rag/translate.py` and uses the one client factory; line data goes through `LineStore` only. | Pass |
| Technology stack | No new package. | Pass |
| Out of scope for the MVP | Nothing is sent to a shipper or customs; no accounts; no persistence beyond the session. | Pass |

**Post-design re-check**: unchanged after Phase 1 (data-model.md, contracts/, quickstart.md). The design adds no
dependency, no tool and no routing input; the only constitution change is FR-031's amendment of "Knowledge-base
sources", made through the amendment procedure; Principle IV stays as it is because the rewrite ships off.

## Store and environment for the live steps

*The author's answer to the plan's question A (2026-11-18).* Only the main checkout `C:\ai\CargoLint` has a store
(the twelve chapters, 74,044 rulings, extract of 2026-11-18) and a Python environment; the feature worktree has
neither, and `STORE_DIR` is `<worktree>/store` for code run there.

1. The worktree gets its own environment: `python -m venv .venv` and `pip install -e ".[dev]"` (`.venv/` is
   git-ignored).
2. Before the baseline, the five entries of the main checkout's store layout (`index_meta.json`, `bm25.pkl`,
   `bti_docs.jsonl`, `chroma/`, `chroma-bti/`) are copied once into `<worktree>/store`: 3,350,384,841 bytes, about
   3.35 GB (3.12 GiB), measured on 2026-11-18; the old logs and screenshots in that folder are left behind. The copy is
   read once and never written back; a junction is not used, as Chroma opens its files read-write. The disk has 231 GB
   free.
3. The rebuild runs in the worktree from that copy as `--previous`, into `<worktree>/build/ebti-<date>/`, with its own
   extract download into `<worktree>/build/`.
4. For the after-runs, the baseline copy moves to `<worktree>/build/store-baseline/` (kept for the manual UI check on
   twelve chapters) and the rebuilt `store/` takes its place.
5. The main checkout is never written. Replacing its `store/` with the rebuilt one is the author's manual step after
   the merge, outside the tasks.

## Project Structure

### Documentation (this feature)

```text
specs/014a-retrieval-evidence/
├── spec.md                       # the specification, with the clarifications of 2026-11-18
├── plan.md                       # this file
├── research.md                   # Phase 0: facts and decisions
├── data-model.md                 # Phase 1: settings, RulingScope, CitationNote, CustomsWording, files, eval rows
├── quickstart.md                 # Phase 1: offline suite and the author's live steps
├── contracts/
│   ├── classify-hs6.md           # the changed tool: steps, context, pure functions
│   ├── ui.md                     # block 1, 2 and 3 texts, the Retrieval steps line, Admin › Data
│   ├── eval-cli.md               # --set coolant, --customs-wording, --replay --floor, rows and files
│   └── settings-and-scripts.md   # the two settings, the refresh/loader/bti options, the source version
├── checklists/
│   └── requirements.md           # the spec quality checklist
└── tasks.md                      # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
agent/
├── config.py            # CARGOLINT_EBTI_CHAPTERS, CARGOLINT_CUSTOMS_WORDING, parse_chapter_setting
├── schemas.py           # RulingScope, CitationNote, CustomsWording, WordingOut; Candidate.citation_notes;
│                        #   Classification and LineVersion: ruling_scope, customs_wording;
│                        #   RetrievalTrace.customs_wording
└── store.py             # update_classification copies ruling_scope and customs_wording
rag/
├── bti.py               # chapters_spec(None) = "all chapters"; indexed_chapters, main_language helpers;
│                        #   main(): --chapters from the setting, "all" accepted
├── loader.py            # --bti-chapters default from the setting; parse_chapters via the config parser; exit 2 on a
│                        #   bad setting; KnowledgeBase.indexed_chapters and .main_language
├── refresh_ebti.py      # --chapters; the extract filtered by the setting's chapters; source version; log counts
├── rules.py             # load_glossary (optional data/rules/customs_glossary.json, reviewed entries only)
└── translate.py         # customs_wording(): prompt, WordingOut, cache, glossary_matches, language names
tools/
└── classify_hs6.py      # rewrite in the ruling searches only; the scoped vote search; ruling_scope; citation_notes;
                         #   ClassifyContext.customs_wording
ui/
├── view.py              # rulings_caption (block 3), citation note texts (block 2), customs wording caption (block 1)
├── expand.py            # block 1 caption, block 2 notes, block 3 caption
└── chat.py              # Retrieval steps: the rewrite in the queries line
scripts/refresh_ebti.py  # docstring: --chapters
tests/
├── eval/hs6_eval.py             # --set coolant, --customs-wording, --replay --floor, row fields, coolant files
├── eval/hs6_eval_coolant.json   # new: the eight coolant lines
├── unit/test_settings.py        # + the two settings
├── unit/test_ruling_scope.py    # new: indexed chapters, main language, RulingScope
├── unit/test_citation_notes.py  # new: match, other code, not retrieved, unknown, normal form, order
├── unit/test_customs_wording.py # new: switch, scope, merge, cache, language, glossary, failure
├── unit/test_hs6_eval.py        # + coolant scoring, floor replay, new row fields
├── unit/test_view.py            # + rulings_caption states, note texts, block 1 caption text
├── unit/test_loader.py          # + --bti-chapters default, parse via config, exit 2
├── integration/test_hs6_vote_scope.py   # new: classify_one end to end on in-memory vectors in several chapters
├── integration/test_refresh_ebti.py     # + all chapters by default, --chapters, source version
├── adversarial/                         # + an injection fixture for the rewrite
└── ui/test_main_page.py                 # + block 1/2/3 texts through AppTest (harness.make_kb's rulings)
docs/backlog.md          # entry 1 marked done
README.md, .env.example  # the settings, the vote scope, the captions, the notes, the rewrite, the glossary, the set
.specify/memory/constitution.md   # "Knowledge-base sources" amended through /speckit-constitution (FR-031), 1.11.0
```

**Structure Decision**: the existing single project; logic goes where its kind already lives (settings in `agent/`,
retrieval in `rag/`, the HS-6 step in `tools/`, texts in `ui/view.py`), and the evaluation stays one script with new
options.

## Complexity Tracking

No violation to justify. The one constitution change (FR-031) goes through the amendment procedure with the author's
approval; it is not an exception taken here. Principle IV needs nothing while the rewrite ships off.
