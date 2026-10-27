---

description: "Task list for feature 011, the cloud demo"
---

# Tasks: Cloud Demo

**Input**: Design documents from `specs/011-cloud-demo/`

**Prerequisites**: plan.md, spec.md. The background, measurements and platform facts are in
`docs/deploy/streamlit-cloud-assessment.md`.

**Tests**: included and written first, offline. Constitution Principle VII asks this for guardrail code: the password
gate and the checksum check.

**Organization**: tasks are grouped by user story (US1 to US3 of spec.md). This list records the work as done on
2026-10-27, so every task is checked. Every file named here is LF.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to

---

## Phase 1: Setup

- [X] T001 Create the branch `011-cloud-demo` from `main` (`b03ee39`) and point `.specify/feature.json` at
  `specs/011-cloud-demo`
- [X] T002 Write specs/011-cloud-demo/spec.md and specs/011-cloud-demo/plan.md
- [X] T003 [P] Add docs/deploy/streamlit-cloud-assessment.md to the repository; it is option C's background

---

## Phase 2: Foundational

- [X] T004 Add `app_password` (`CARGOLINT_APP_PASSWORD`), `demo_store_url` (`CARGOLINT_DEMO_STORE_URL`) and
  `demo_store_sha256` (`CARGOLINT_DEMO_STORE_SHA256`) to `Settings` in agent/config.py. They are empty by default, and
  the password is kept out of `repr`.

**Checkpoint**: with the three settings unset, nothing changes.

---

## Phase 3: User Story 1 - The author publishes a demo knowledge base (Priority: P1) 🎯 MVP

**Goal**: one command cuts a demo store from the local full build with no API call, and packs it as one archive.

**Independent Test**: the cut on a tiny fake full build in a temporary folder.

### Tests for User Story 1

- [X] T005 [P] [US1] Selection tests in tests/unit/test_demo_store.py, class `TestSelection`:
  - the preferred codes are the eval set's and every sample file's;
  - preferred codes take at most half, one per code in turn;
  - each preferred code gets at least five when the budget allows;
  - the rest is spread over the chapters, one code in turn;
  - the choice does not depend on record order;
  - rulings without text are never chosen;
  - a request larger than the pool takes everything.
- [X] T006 [P] [US1] Cut and archive tests in tests/unit/test_demo_store.py, class `TestCut`, on a fake full build with
  a real Chroma collection of 8-dimensional vectors:
  - the indexes are copied, and the chosen rulings keep their vectors in a cosine collection;
  - the samples' codes are preferred;
  - a ruling without a vector is dropped and counted;
  - an incomplete build and a folder that is not empty are refused;
  - the archive holds only `store/…` and `data/taric.jsonl`, and its checksum is reported.

### Implementation for User Story 1

- [X] T007 [US1] `preferred_codes`, `select_rulings`, `copy_vectors`, `cut_demo_store` and `pack` in rag/demo_store.py.
  The xlsx sample's codes come from data/samples/sample_lines.json. `SAMPLE_VARIANT_HS6` holds the hand-classified codes
  of sample_invoice_ningbo.csv and sample_packing_list_foshan.pdf, which store none.
- [X] T008 [US1] The command `python -m rag.demo_store --out <dir> --rulings 5000 [--zip <path>]` in rag/demo_store.py

**Checkpoint**: User Story 1 works on its own; the cut of the real store is the author's step.

---

## Phase 4: User Story 2 - A cold start fetches the demo store (Priority: P1)

**Goal**: when the store is missing, the app downloads, verifies and unpacks the archive before opening the knowledge
base.

**Independent Test**: `file:` URLs to small archives in temporary folders.

### Tests for User Story 2

- [X] T009 [P] [US2] Fetch tests in tests/unit/test_demo_store.py, class `TestFetch`:
  - a good checksum unpacks the archive, whatever the checksum's case;
  - a wrong or missing checksum unpacks nothing;
  - an archive without `store/index_meta.json` is refused;
  - an archive with unexpected paths is refused;
  - an unreachable archive gives a clear error;
  - nothing is fetched without a URL, or when a store exists.
- [X] T010 [P] [US2] App test in tests/ui/test_app_navigation.py: a demo store that fails its checksum stops the app
  with "Demo knowledge base: …" and opens no knowledge base.

### Implementation for User Story 2

- [X] T011 [US2] `demo_store_needed` and `fetch_demo_store` in rag/demo_store.py. The archive goes to a temporary file
  and its SHA-256 is checked before anything is unpacked. Only `store/…` and `data/taric.jsonl` are allowed, and
  `store/index_meta.json` is unpacked last.
- [X] T012 [US2] `load_kb()` in app.py fetches the store with a spinner when it is missing; `main()` stops on
  `DemoStoreError`.

**Checkpoint**: User Stories 1 and 2 together make a fresh clone start on the cloud.

---

## Phase 5: User Story 3 - Only people with the password reach the demo (Priority: P2)

**Goal**: without the demo password, nothing loads and nothing is spent.

**Independent Test**: AppTest with fake settings and a fake knowledge base.

### Tests for User Story 3

- [X] T013 [US3] App tests in tests/ui/test_app_navigation.py:
  - there is no gate without a password;
  - nothing loads until the password is entered;
  - a wrong password keeps the app locked;
  - the right password opens the app;
  - the gate comes before the missing-key message;
  - the missing-key message is the new one.

### Implementation for User Story 3

- [X] T014 [US3] `password_ok()` in app.py, called first in `main()`. It compares with `hmac.compare_digest` and shows
  "Wrong password." on a wrong entry.
- [X] T015 [US3] The missing-key message in app.py also names the app's Secrets settings on Streamlit Community Cloud.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T016 [P] README.md: the "Demo deployment" section, and `demo_store` in the repository layout
- [X] T017 Run the selection, read only, on the full build's extract for the per-code counts (spec SC-007). Of 5,000
  rulings, 2,500 sit under the 73 preferred codes. That is 39 or 40 per code, or all a code has. Earphones 8518.30 and
  electronic apparatus 8543.70 get 39 each.
- [X] T018 `pytest -q`, offline: 1242 passed, 4 deselected in 139.60s

---

## Not in this feature: the author's steps

- Cut the real demo store with `python -m rag.demo_store --out <dir> --rulings 5000 --zip <archive>`, and publish the
  archive as a release asset.
- Deploy on Community Cloud with Python 3.13 and the secrets of the README, then check SC-001.
- Decide whether the TARIC snapshot may be redistributed (assessment §4.3).

## Dependencies & Execution Order

- T004 comes before T007, T011, T012 and T014.
- Each story's tests (T005, T006, T009, T010, T013) come before its implementation.
- T007 comes before T008, and T011 before T012. T016 to T018 come last.
