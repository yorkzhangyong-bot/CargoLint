# Implementation Plan: Cloud Demo

**Branch**: `011-cloud-demo` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-cloud-demo/spec.md`. Background, measurements and platform facts are
in `docs/deploy/streamlit-cloud-assessment.md`; this feature implements its option C.

## Summary

A new module, `rag/demo_store.py`, does two jobs:

- **Cut and pack** (a command-line tool): it cuts a demo knowledge base out of the local full build without any API
  call. It copies the nomenclature index and BM25 file, chooses about 5,000 rulings, copies their existing vectors into
  a new ruling collection, and packs the result with the TARIC snapshot as one archive.
- **Fetch** (for the app): when the store is missing it downloads that archive, verifies it and unpacks it.

`app.py` calls the fetch step inside `load_kb()`, before opening the knowledge base, and gains a password gate at the
start of `main()`. `agent/config.py` reads three new settings. All three are off by default, so local behaviour is
unchanged.

## Technical Context

**Language/Version**: Python 3.11–3.13 (the project's `.venv`; Python 3.13 on Community Cloud)

**Primary Dependencies**: Streamlit (native elements only), chromadb 1.5.9 (already a dependency); standard library
`urllib.request`, `zipfile`, `hashlib`, `hmac`, `tempfile`. No new package.

**Storage**: `store/` and `data/taric.jsonl` as today. On the cloud they are unpacked from the archive at every cold
start, since the filesystem is ephemeral.

**Testing**: pytest, offline. The download is tested with `file:` URLs to small archives in temporary folders. The cut
is tested on a tiny fake full build, with a real Chroma collection of 8-dimensional vectors. The gate is tested through
AppTest with fake settings and a fake knowledge base.

**Target Platform**: Streamlit Community Cloud (Debian 11, Python 3.13, 690 MB–2.7 GB of memory), and the local app as
today

**Project Type**: the existing single Streamlit project

**Performance Goals**: a cold start downloads an archive of an estimated 130 MB, and the script prints the real size.
At about 5,000 rulings the app needs an estimated 550–600 MB at rest and 900 MB while reading a scan or photo
(assessment §3).

**Constraints**:
- no model or embedding call to cut the store;
- the checksum is verified before anything is unpacked;
- nothing changes when the three settings are unset;
- each file keeps its line endings.

**Scale/Scope**: one new module, three settings, about 30 lines in `app.py`, two test files, the README

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution 1.7.0.

| Principle | Check | Status |
|---|---|---|
| I. Guardrails live in code | The gate and the checksum check are code. No route, threshold or lock changes. | Pass |
| II. Untrusted input | The archive is the author's own, and it is verified by SHA-256 before unpacking. Unpacking only writes `store/…` and `data/taric.jsonl`. The API key still comes from an environment variable: Community Cloud's root-level secrets reach `os.environ` before the app runs. The demo password is entered in the UI, but it is not an API key. | Pass |
| III. Grounded, cited | The rulings keep their texts and references, so precedents stay cited. The demo's index is smaller, so fewer rulings can vote; the assessment and the README say so. | Pass |
| IV. Hybrid retrieval | BM25 and the nomenclature vectors are unchanged; the ruling index is a subset with the same vectors. | Pass |
| V. Typed tools | No tool changes. | Pass |
| VI. Native UI that shows its work | The gate uses `st.text_input` and `st.error`; the download uses `st.spinner` and `st.error`. No custom HTML. | Pass |
| VII. Test-first | The gate and the download tests come before the code; the suite stays offline. | Pass |
| Architecture: domain logic testable without Streamlit | The cut, pack and fetch steps live in `rag/demo_store.py`, which imports no Streamlit; `app.py` only calls them. | Pass |
| Out of scope: accounts and multi-user access | One shared password per deployment is not an account system; no user is stored. | Pass |

**Post-design re-check**: unchanged. The design adds no dependency and no tool, and it does not change routing.

## Project Structure

### Documentation (this feature)

```text
specs/011-cloud-demo/
├── spec.md              # the feature specification
└── plan.md              # this file; the design decisions below take the place of research.md
```

### Source Code (repository root)

```text
rag/
└── demo_store.py        # new: select_rulings, cut_demo_store, pack, demo_store_needed, fetch_demo_store, CLI
agent/
└── config.py            # Settings.app_password, demo_store_url, demo_store_sha256
app.py                   # password gate; demo store fetch in load_kb(); missing-key message
tests/
├── unit/
│   └── test_demo_store.py         # new: selection, cut, pack, fetch
└── ui/
    └── test_app_navigation.py     # gate and fetch-error tests; the new missing-key message
README.md                          # "Demo deployment"
```

**Structure Decision**: the cut and the fetch share one module, because they share the archive layout: `store/…` and
`data/taric.jsonl`. The fetch path imports only the standard library and `agent.config`. chromadb and the ruling store
load only when cutting.

## Design decisions

1. **Which rulings.** The preferred HS-6 codes are the eval set's 56 and every code the three sample files are
   expected to produce, 73 in all. The xlsx sample's codes come from `data/samples/sample_lines.json`. The csv and pdf
   samples store no codes, so theirs are classified by hand in `rag/demo_store.py`: each checked against CN 2026 and
   against the code most matching EBTI rulings carry. The eval codes alone cover 31,451 of the 73,899 rulings, so
   "every ruling of those codes" cannot fit in 5,000.
   - The preferred codes take at most half of the request, one ruling per code in turn. For 5,000 that is 39 or 40
     each for the 69 codes with rulings, or all a code has when fewer. Earphones 8518.30 and electronic apparatus
     8543.70 get 39 each.
   - The other half is dealt round-robin over the chapters. Within a chapter it goes one ruling per HS-6 code in turn,
     most common codes first.
   - The preferred codes' remaining rulings come last.

   This keeps the eval and sample goods close to their evaluated behaviour, and leaves room for other goods. Each
   code's rulings are shuffled with a fixed seed, so the same build gives the same demo store.
2. **Vectors.** They are read from the full `bti` collection with `get(ids=…, include=["embeddings", "documents",
   "metadatas"])`, in batches, and added to a new collection created as `langchain_chroma` creates it: name `bti`,
   `{"hnsw:space": "cosine"}`, no embedding function. Both clients are closed afterwards, which releases the SQLite
   files on Windows before zipping.
3. **Which rulings to keep.** Only rulings whose vector was found go into `bti_docs.jsonl` and the count in
   `index_meta.json`, so the two can never disagree.
4. **Download.** `urllib.request` reads `https:` and `file:` URLs, so tests need no server. The archive streams to a
   temporary file while its SHA-256 is computed.
   - The comparison is case-insensitive.
   - A missing checksum is an error, because an unverifiable archive is never unpacked.
5. **Unpack.** Every entry is checked before any is written: only `store/…` and `data/taric.jsonl` are allowed, with no
   `..` parts. `store/index_meta.json` is written last. The app treats that file as "the store exists", so an
   interrupted unpack is retried at the next start.
6. **Once per process.** The fetch runs inside `load_kb()`, which `st.cache_resource` runs once per process, so two
   sessions starting together cannot unpack at the same time. Errors are not cached, so a failed start retries at the
   next visit.
7. **Gate.** It runs before the key check and before `load_kb()`, compares bytes with `hmac.compare_digest`, and
   remembers success in `st.session_state`, which is per browser session.

## Implementation outline

**A. Tests first (offline)**
- **A1** `tests/unit/test_demo_store.py`:
  - selection: eval codes capped at half and taken in turn, chapters in turn, determinism, rulings without text never
    chosen, a request larger than the pool;
  - the cut on a fake full build: copied files, the same vectors, counts, a ruling without a vector, refusal of an
    incomplete build and of a non-empty folder;
  - the archive's entries and checksum;
  - the fetch: good checksum, bad checksum, missing checksum, missing `index_meta.json`, an unexpected path, nothing
    fetched when the store exists or no URL is set.
- **A2** `tests/ui/test_app_navigation.py`:
  - the gate: off when unset, a wrong password stops before the knowledge base, the right one opens the app, the gate
    comes before the key check;
  - a checksum error stops the app with its message;
  - the new missing-key message.

**B. Code**
- **B1** `agent/config.py`: the three settings.
- **B2** `rag/demo_store.py`.
- **B3** `app.py`: the gate, the fetch in `load_kb()` and the message.

**C. Documentation**
- **C1** The README's "Demo deployment" section.

**D. Verification**
- **D1** `pytest -q`, offline.
- **D2** Not in this feature's runs: cutting the real store and deploying are the author's steps.

## Complexity Tracking

None. No principle is violated and no dependency is added.
