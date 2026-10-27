# Feature Specification: Cloud Demo

**Feature Branch**: `011-cloud-demo`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Make CargoLint deployable as a demo on Streamlit Community Cloud, following option C of
`docs/deploy/streamlit-cloud-assessment.md` (download a demo store at first start). A script cuts a demo store of about
5,000 rulings from the local full build with no API call and packs it as one archive; the app downloads, verifies and
unpacks it when the store is missing; a password gate from the settings keeps the demo to people with the password;
the missing-key message names the Community Cloud Secrets; the README gains a Demo deployment section."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The author publishes a demo knowledge base (Priority: P1)

The author cuts a demo knowledge base from the local full build with one command, without any model or embedding call,
packs it as one archive and attaches the archive to a GitHub release.

**Why this priority**: without a store a fresh clone cannot start, and the full store (1.8 GB of ruling vectors) does
not fit the cloud's memory (assessment §1 and §3). Nothing else in this feature works without the archive.

**Independent Test**: run the command on a tiny fake full build in a temporary folder. The output holds the six items
with the right counts and the same vectors, the archive holds only `store/…` and `data/taric.jsonl`, and the printed
checksum matches the file.

**Acceptance Scenarios**:

1. **Given** the local full build, **When** the author runs `python -m rag.demo_store --out <dir> --rulings 5000`,
   **Then** `<dir>/store/` holds:
   - the nomenclature index and the BM25 file, copied unchanged;
   - about 5,000 rulings with their existing vectors;
   - an `index_meta.json` with the new ruling count.

   `<dir>/data/taric.jsonl` is the TARIC snapshot, and no model or embedding call is made.
2. **Given** `--zip <path>`, **When** the command finishes, **Then** the archive's entries are `store/…` and
   `data/taric.jsonl`, and the command prints the archive's SHA-256 and size.
3. **Given** an `--out` folder that exists and is not empty, **When** the command runs, **Then** it refuses and writes
   nothing.

---

### User Story 2 - A cold start fetches the demo store (Priority: P1)

On Streamlit Community Cloud the app finds no store, downloads the archive named in its settings, verifies the checksum,
unpacks the archive and opens the knowledge base as before.

**Why this priority**: the cloud's filesystem starts empty after every sleep or reboot, so every cold start needs the
store.

**Independent Test**: point the download at a local file URL with a small archive, in a temporary folder.

**Acceptance Scenarios**:

1. **Given** no `store/index_meta.json` and both `CARGOLINT_DEMO_STORE_URL` and `CARGOLINT_DEMO_STORE_SHA256` set,
   **When** the app starts, **Then** it shows a spinner with a short message, unpacks the archive into the repository
   root and opens the knowledge base.
2. **Given** an archive whose checksum differs from the setting, **When** the app starts, **Then** it stops with an
   error naming the mismatch and unpacks nothing.
3. **Given** an existing `store/index_meta.json`, **When** the app starts, **Then** nothing is downloaded. Local
   development is unchanged.
4. **Given** no URL, **When** the app starts, **Then** nothing is downloaded and the app behaves as today.

---

### User Story 3 - Only people with the password reach the demo (Priority: P2)

A visitor needs the demo password before the app loads anything or spends anything.

**Why this priority**: the demo spends the author's OpenRouter budget. The key's credit limit caps the spend, and the
password keeps the link from being used by anyone who finds it.

**Independent Test**: run the app with a password set, under Streamlit's AppTest, and the knowledge base and model
replaced by fakes.

**Acceptance Scenarios**:

1. **Given** `CARGOLINT_APP_PASSWORD` set, **When** a visitor opens the app, **Then** only a password field shows: no
   knowledge base is loaded and no model is called.
2. **Given** a wrong password, **When** it is entered, **Then** "Wrong password." shows and the app stays locked.
3. **Given** the right password, **When** it is entered, **Then** the app opens as today for the rest of the session.
4. **Given** no password set, **When** the app opens, **Then** there is no gate.
5. **Given** a password set and no API key, **When** the app opens, **Then** the password field shows, not the
   missing-key message.

---

### Edge Cases

- The archive lacks `store/index_meta.json`: it is refused and nothing is unpacked.
- The archive holds a path other than `store/…` and `data/taric.jsonl`: it is refused and nothing is unpacked.
- The unpacking is interrupted: `store/index_meta.json` is unpacked last, so the next start downloads again.
- A URL is set without a checksum: the app stops with an error, since the archive cannot be verified.
- The full build is incomplete (no `index_meta.json`, index, BM25 file, ruling collection, extract, eval set or TARIC
  snapshot): the command names what is missing and writes nothing.
- A ruling without text has no vector in the full build and is never chosen.
- A ruling whose vector is missing from the full collection is dropped and counted, never re-embedded.
- The full build has fewer usable rulings than requested: all of them are taken.
- The preferred HS-6 codes cover far more rulings than the request (the eval set's alone cover 31,451 of 73,899 in the
  full build): they take at most half of it.
- A sample code outside the indexed EBTI chapters has no ruling to take: bicycle frames 8714.91, O-rings 4016.93,
  kitchen scissors 8213.00 and watch straps 9113.90.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `python -m rag.demo_store --out <dir> --rulings N` MUST build a demo store from the local full build
  without any model or embedding call. It MUST:
  - copy `store/chroma/` and `store/bm25.pkl` unchanged;
  - choose about N rulings from `data/bti_subset.jsonl` (FR-002);
  - write `store/bti_docs.jsonl` for them;
  - build `store/chroma-bti/` (collection `bti`, cosine space) from their existing vectors, read out of the full
    collection;
  - write `store/index_meta.json` with the source's fields and the new ruling count;
  - copy `data/taric.jsonl`.
- **FR-002**: The choice MUST be deterministic and MUST take only rulings with embedded text, in two parts:
  - **preferred codes**: up to half of N from the preferred HS-6 codes, one ruling per code in turn, so that every code
    gets the same number. The preferred codes are those of `tests/eval/cn8_eval_set.json` and every code the sample
    files are expected to produce:
    - for `sample_packing_list.xlsx`, `data/samples/sample_lines.json`;
    - for `sample_invoice_ningbo.csv` and `sample_packing_list_foshan.pdf`, which store no codes, a list classified by
      hand in `rag/demo_store.py`;
  - **the rest**: spread evenly over the chapters, one ruling per HS-6 code in turn, the most common codes first. The
    preferred codes' remaining rulings come only when a chapter has no others left.
- **FR-003**: A chosen ruling whose vector is missing from the full collection MUST be dropped and counted, never
  re-embedded.
- **FR-004**: The command MUST refuse an `--out` folder that exists and is not empty, so it can never overwrite a store.
- **FR-005**: `--zip <path>` MUST pack the demo store into one archive whose entries are `store/…` and
  `data/taric.jsonl`, and print its SHA-256 and size.
- **FR-006**: The settings MUST read `CARGOLINT_APP_PASSWORD`, `CARGOLINT_DEMO_STORE_URL` and
  `CARGOLINT_DEMO_STORE_SHA256` from the environment, empty by default. An empty password means no gate; an empty URL
  means no download.
- **FR-007**: When `store/index_meta.json` is missing and the URL is set, the app MUST, once per server process before
  it opens the knowledge base:
  - download the archive to a temporary file;
  - verify its SHA-256 against the setting before unpacking anything;
  - unpack it into the repository root, `store/index_meta.json` last.

  A spinner with a short message MUST show during the download.
- **FR-008**: The app MUST stop with a clear error, and unpack nothing, when:
  - the checksum is missing;
  - the checksum differs;
  - the archive lacks `store/index_meta.json`;
  - the archive holds any path other than `store/…` and `data/taric.jsonl`.
- **FR-009**: When a password is set, the app MUST show only a password field until the session has entered it, before
  the missing-key check and before loading the knowledge base. It MUST compare with `hmac.compare_digest`. A wrong
  password shows "Wrong password." and keeps the app locked; the right one opens it for the session.
- **FR-010**: The missing-key message MUST also name the app's Secrets settings on Streamlit Community Cloud.
- **FR-011**: The README MUST gain a "Demo deployment" section covering:
  - cutting and zipping the demo store;
  - the release asset;
  - the secrets;
  - Python 3.13;
  - memory;
  - sessions lost on sleep.

### Key Entities *(include if feature involves data)*

- **Demo store**: `store/` (`index_meta.json`, `bm25.pkl`, `chroma/`, `chroma-bti/`, `bti_docs.jsonl`) and
  `data/taric.jsonl`, cut from the full build. The nomenclature index is the full one; the ruling index is reduced.
- **Demo archive**: one zip of the demo store with those paths, identified by its SHA-256.
- **Demo password**: one shared secret per deployment. It is not an account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a fresh clone, with only the API key and the three settings, the app opens the knowledge base on its
  first start without a manual step. This is verified on the first deployment.
- **SC-002**: Cutting the demo store makes no OpenRouter call. An offline test covers this, under the suite's guard.
- **SC-003**: A wrong or missing checksum, or an archive with an unexpected path, unpacks nothing. Offline tests cover
  this.
- **SC-004**: Without the password, no knowledge base is loaded and no model is called. An offline test covers this.
- **SC-005**: With none of the three settings set, local behaviour is unchanged and the offline suite passes.
- **SC-006**: With about 5,000 rulings the demo stays within about 1 GB of memory: an estimated 550–600 MB at rest and
  900 MB while a scan or photo is read (assessment §3).
- **SC-007**: With 5,000 rulings, every sample code with at least five rulings in the full build gets at least five in
  the demo store. Earphones 8518.30 and electronic apparatus 8543.70 get 39 each, by the selection run on the full
  build's extract.

## Assumptions

- The local full build exists: `store/` with the full `chroma-bti`, `data/bti_subset.jsonl` and `data/taric.jsonl`.
- The archive is published as a GitHub release asset. Whether the TARIC snapshot may be redistributed is the author's
  call (assessment §4.3).
- A shared password is enough for a demo whose risk is API spend. The OpenRouter key's credit limit caps that spend;
  it is set at OpenRouter and not enforced in code.
- Accounts and multi-user access stay out of scope (constitution). The gate is one shared password, not an account
  system.
- Platform facts are as recorded in `docs/deploy/streamlit-cloud-assessment.md`.
