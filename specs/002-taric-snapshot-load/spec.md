# Feature Specification: One-Time TARIC Load for Digits 9 to 10

**Feature Branch**: `002-taric-snapshot-load`

**Created**: 2026-10-22

**Status**: Draft

**Input**: User description: "Feature: One-time TARIC load for digits 9 to 10. Problem. CargoLint today classifies to HS-6 and can see CN-8 lines inside the CN 2026 chunks, but it has no knowledge of TARIC subdivisions (digits 9 and 10) or the measures attached to them. Clerks therefore still have to open EZT-online for the last two digits. This feature loads a complete TARIC snapshot once, so later features can look up subdivisions and measures for a given CN-8 code and origin. Data source. The Swedish Customs Tariff File Distribution (distr.tullverket.se/tulltaxan), which mirrors the full EU TARIC nightly as PGP-encrypted XML. This feature uses only one full extract (the tot file). Daily difference files (dif) are out of scope. Scope of authority. The CN 2026 SKOS data remains the sole authority for digits 1 to 8: retrieval, chunking, validation and display of descriptions at those levels do not change. TARIC data is used only for digits 9 to 10 and for measures. TARIC description text for levels 1 to 8 is ignored. TARIC data is never embedded and never added to any Chroma collection. Storage. Follow the existing repository pattern: a flat file data/taric.jsonl written by the loader, and an in-memory TaricStore class in rag/taric.py modelled on BTIStore, loaded once at startup and read-only at runtime. The file contains three record kinds, distinguished by a kind field. Record kind goods_nomenclature: full 10-digit code, CN-8 prefix, TARIC description text, validity start date, validity end date (may be empty). Record kind measure: 10-digit code, measure type code and label, geographical area code (for example CN for China, 1011 for erga omnes), duty expression as a plain string, regulation reference, validity start and end dates. Record kind snapshot: exactly one record holding the extract date, the source file name, the load timestamp, the number of goods_nomenclature records, the number of measure records, and the number of CN-8 reconciliation mismatches. Loader. A command rag/loader.py --taric <path-to-tot-file> that decrypts with the PGP key named by an environment variable, parses the XML, filters to records valid on the load date, writes data/taric.jsonl, and prints a summary. The loader is idempotent: if data/taric.jsonl already exists and its snapshot date equals the extract date of the input file, the loader skips with a message; --force overwrites the whole file. Rerunning never produces duplicate records. Reconciliation. For every distinct CN-8 prefix found in the TARIC goods_nomenclature records, the loader checks whether that CN-8 exists in NomenclatureIndex (CN 2026). Prefixes that do not exist in CN 2026 are counted and logged with their code; they are still stored. The count is written into the snapshot record. Mismatch handling is logging only; no automatic correction. Lookup. TaricStore exposes lookup_taric(cn8, origin="CN") returning the list of 10-digit subdivisions under that CN-8 that are valid on the snapshot date, each with its TARIC description and the measures applicable to the given origin plus erga omnes measures. An empty list means TARIC has no subdivision for that CN-8. This feature only provides the function; wiring it into the agent graph, the Candidate schema and the UI is Spec 2. UI. One sidebar caption only, showing TARIC snapshot date and the reconciliation mismatch count, or the text TARIC not loaded when data/taric.jsonl is absent. No other UI change. Out of scope. Nightly or scheduled refresh, dif files, change alerts, the German national layer (EZT-online stays the link-out), duty calculation, quota data, agent or UI integration beyond the sidebar caption, and any change to the CN 2026 or BTI Chroma collections. Acceptance criteria. One: for 20 CN-8 codes chosen from the labelled test lines, the subdivisions and China-origin measures returned by lookup_taric match what EZT-online shows on the same date. Two: running the loader twice on the same tot file produces an identical data/taric.jsonl and the second run reports a skip. Three: unit tests run offline against a small fixture XML (no network, no PGP key) and cover parsing, validity filtering, reconciliation counting and lookup_taric for the cases single subdivision, multiple subdivisions and no subdivision. Four: app startup with data/taric.jsonl absent still works and shows TARIC not loaded."

## Clarifications

### Session 2026-10-22

The first five answers are facts the author verified on the real data source. They replace the Input's single-file and decryption wording. The remaining answers are the author's decisions on open points.

- Q: What does the full extract look like? → A: Not one file but a set of per-object files under xml/tot/ on the distribution, named ObjectName_batchId_YYMMDD.xml.gz.pgp.
- Q: Which files does the loader read? → A: Six object files from one folder (by default data/raw/taric/): GoodsNomenclature, Measure, MeasureType, GeographicalArea, DutyExpression and Regulation. All other object files are ignored.
- Q: How are the files protected? → A: They are PGP signed, not encrypted. The loader verifies each signature with the Swedish Customs public key (key ID 302AC3C1D0E3E1C9), strips the signature, unpacks the gzip and parses the XML. No private key is needed anywhere.
- Q: Where does the snapshot date come from? → A: From the YYMMDD in the file names. The loader fails if the six files have different batch IDs.
- Q: Which goods records count, and which description is used? → A: Only GoodsNomenclature records with product-line suffix 80 are codes; records with other suffixes are grouping lines and are skipped. Descriptions come only from the goodsNomenclatureDescription element with languageId EN.
- Q: Is a suffix-80 code that has child codes a declarable subdivision? → A: No. It is a parent: it is never returned as a subdivision and is excluded from reconciliation counting.
- Q: Besides measures for the origin itself and erga omnes, how complete must the lookup's measures be? → A: Each measure also carries the additional code recorded on it, so company-specific anti-dumping rates can be told apart. Measures for country groups that contain the origin, and erga omnes measures that exclude it, are not covered.
- Q: Which date decides whether a code or measure is valid, when loading and when looking up? → A: The snapshot date in the file names, for both. The load date is recorded but does not affect validity.
- Q: Where does the loader take the Swedish Customs public key from? → A: From a copy kept in the project. The loader uses it only if its key ID is 302AC3C1D0E3E1C9 and refuses any other key.
- Q: How do the automated checks cover the signature check? → A: Both ways. The small fixture files are signed with a throwaway test key kept with the fixtures, and a good file, a tampered file and a file signed by another key are tested. One small real signed file from Swedish Customs, also kept with the fixtures, is verified against the project's copy of the real key. Neither needs network access or any secret.
- Q: Does each measure record keep TARIC's own identifier for that measure? → A: Yes. No two measure records share one, which is how duplicate measures are detected.
- Q: Which throwaway key material may be kept with the test fixtures? → A: Only the throwaway public keys and the signed fixture files. The fixture generator creates the key pairs in a temporary gpg home, signs there and deletes the home, so no secret key is ever stored in the repository.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load a TARIC snapshot from one full extract (Priority: P1)

The operator downloads the per-object files of one full extract (one batch) from the Swedish Customs tariff file distribution into the load folder and runs one load command. The command reads the six object files it needs and ignores the rest. For each file it verifies the Swedish Customs signature, removes it, unpacks the file and reads it. It keeps the codes and measures valid on the snapshot date and writes the TARIC snapshot file: the codes with their English TARIC descriptions, the measures and one snapshot record. It checks the CN-8 prefix of every declarable code against the CN 2026 nomenclature and ends with a summary.

**Why this priority**: Without the snapshot there is nothing to look up; every later TARIC feature depends on it.

**Independent Test**: Run the command on a folder holding one batch, then compare the summary with the snapshot file: exactly one snapshot record, the counts it states, and a few spot-checked codes and measures.

**Acceptance Scenarios**:

1. **Given** the six object files of one batch in the load folder, **When** the operator runs the load command, **Then** the snapshot file holds the codes and measures valid on the snapshot date plus exactly one snapshot record, and the summary shows the snapshot date, the batch, the six file names, the number of code and measure records and the number of CN-8 mismatches.
2. **Given** the load folder also holds other object files, **When** the command runs, **Then** it reads only the six it needs and ignores the others.
3. **Given** goods records whose product-line suffix is not 80, **When** the extract is loaded, **Then** they are skipped as grouping lines.
4. **Given** the extract contains codes or measures that ended before the snapshot date or start after it, **When** it is loaded, **Then** none of them is in the snapshot file.
5. **Given** declarable codes whose CN-8 prefix the CN 2026 nomenclature does not have, **When** the extract is loaded, **Then** each such prefix is logged with its code and counted in the snapshot record, and its codes and measures are still stored. Parent codes are never counted.
6. **Given** a file whose signature does not verify, a missing public-key copy or one with another fingerprint, a missing object file, two files for the same object, files from different batches, or a file that cannot be read, **When** the command runs, **Then** it stops with a plain message naming the file and the problem, writes nothing and leaves any existing snapshot file unchanged.

---

### User Story 2 - Re-run the load safely (Priority: P2)

Running the command again on the same extract changes nothing and says so. An extract with another snapshot date replaces the snapshot. The operator can force a complete rewrite. No run ever leaves duplicate records.

**Why this priority**: The load is run by hand and may be repeated; repeating it must never corrupt or duplicate the snapshot.

**Independent Test**: Run the command twice on the same folder and compare the snapshot file before and after the second run; then run it with the force option and compare the records.

**Acceptance Scenarios**:

1. **Given** a snapshot file whose snapshot date equals the date in the six file names, **When** the command runs without force, **Then** it reports a skip and the snapshot file is byte-for-byte unchanged.
2. **Given** an existing snapshot, **When** the command runs with force on the same extract, **Then** the whole file is rewritten with the same records in the same order, differing only in the load time, and no record appears twice.
3. **Given** an existing snapshot, **When** the command runs on an extract with another snapshot date, **Then** the whole file is replaced by the new snapshot and the summary names both the previous and the new snapshot date.

---

### User Story 3 - Look up the subdivisions and measures of a CN-8 code (Priority: P3)

A later feature (Spec 2) asks for a CN-8 code and an origin, China by default, and gets the 10-digit subdivisions under that CN-8 that are valid on the snapshot date. Each comes with its TARIC description and the measures that apply to goods from that origin: measures for the origin itself and erga omnes measures, including those recorded against a higher level of the code. Each measure shows its additional code when it has one. This feature delivers the lookup only; it is not yet connected to the assistant, the suggestion data or the screen.

**Why this priority**: The lookup is the reason for loading the data, and it can be tested on its own before Spec 2 builds on it.

**Independent Test**: With a snapshot loaded from the sample extract, look up a CN-8 that TARIC does not subdivide, one that it subdivides and one that TARIC does not have, and compare the returned subdivisions and measures with the sample.

**Acceptance Scenarios**:

1. **Given** a CN-8 that TARIC does not subdivide, **When** it is looked up, **Then** the result is a single subdivision, the CN-8's own code ending in 00, with the measures that apply to it.
2. **Given** a CN-8 that TARIC subdivides, **When** it is looked up, **Then** the result lists every declarable code beneath it that is valid on the snapshot date, each with its TARIC description and its applicable measures; the CN-8's own code ending in 00 is then a parent and is not listed.
3. **Given** a CN-8 that TARIC does not have on the snapshot date, **When** it is looked up, **Then** the result is an empty list.
4. **Given** a measure recorded against the CN-8, subheading, heading or chapter above a subdivision, **When** that subdivision is looked up, **Then** the measure is among its applicable measures.
5. **Given** measures for China, for erga omnes and for another country, **When** a subdivision is looked up for China, **Then** the China and erga omnes measures are returned and the other country's are not.
6. **Given** several anti-dumping measures for China on one subdivision, each with its own additional code, **When** it is looked up, **Then** every one of them is returned with its additional code.

---

### User Story 4 - See whether TARIC is loaded (Priority: P4)

The sidebar shows one caption: the TARIC snapshot date and the number of CN-8 mismatches, or "TARIC not loaded" when there is no snapshot. The app works the same with or without the snapshot.

**Why this priority**: The clerk and the operator need to see which TARIC data the app holds, if any; the caption is the only visible part of this feature.

**Independent Test**: Start the app without the snapshot file and check the caption and that a check still runs; then load a snapshot, restart the app and check that the caption shows its date and mismatch count.

**Acceptance Scenarios**:

1. **Given** a loaded snapshot, **When** the app starts, **Then** the sidebar caption shows the snapshot date and the CN-8 mismatch count.
2. **Given** no snapshot file, **When** the app starts, **Then** it starts normally, the caption reads "TARIC not loaded", and all existing functions work as before.

---

### Edge Cases

- The six files do not share one batch ID, or no single snapshot date can be read from their names: the command stops without writing.
- One of the six object files is missing, or the folder holds two files for the same object (for example from two batches): the command stops and names the files, because it cannot tell which batch to load.
- The project's copy of the public key is missing or carries another fingerprint: the command stops before reading any file.
- Swedish Customs replaces its signing key: signatures stop verifying until the project's copy and the pinned fingerprint are updated on purpose.
- The load runs days after the snapshot date: validity still follows the snapshot date, so the result is the same as loading on the file date.
- An extract older than the existing snapshot is loaded: it replaces the snapshot like any other date, and the summary names both dates.
- A code or measure has no end date: it counts as open-ended.
- The extract holds two measures with the same TARIC measure identifier: if they are identical, one is kept; if they differ, the load stops and names the identifier.
- Goods records with a product-line suffix other than 80 are grouping lines: they are skipped, and their text is added to no description.
- A TARIC subdivision has no English description: it is kept with an empty description.
- A subdivision has no measure for the origin or erga omnes: it is returned with an empty list of measures.
- Several anti-dumping rates for China apply to one subdivision, one per additional code: each is returned with its additional code, but the company it stands for is not named.
- A measure is recorded for a country group that contains China, or an erga omnes measure excludes China: the lookup does not handle this. The group measure is not returned, and the erga omnes measure is returned as if it applied.
- A lookup receives a code that is not 8 digits: it is rejected as invalid input, never answered with an empty result.
- The snapshot file exists but cannot be read when the app starts: the app starts, the caption reads "TARIC not loaded" and the reason is logged.
- A load fails half-way: the previous snapshot file stays exactly as it was.

## Requirements *(mandatory)*

### Functional Requirements

#### Loading

- **FR-001**: One operator command MUST read a full TARIC extract from a folder (by default the project's raw TARIC folder) and write the TARIC snapshot file without any further input. It MUST read exactly six object files (goods nomenclature, measures, measure types, geographical areas, duty expressions and regulations) and ignore every other object file in the folder.
- **FR-002**: Before a file is read, the command MUST verify its signature against the Swedish Customs public key (fingerprint 410160CE25CEC2FF322784E7302AC3C1D0E3E1C9, key ID 302AC3C1D0E3E1C9), then remove the signature and unpack the content. The key MUST be a copy kept in the project, used only if its fingerprint is 410160CE25CEC2FF322784E7302AC3C1D0E3E1C9; a missing copy or one with another fingerprint MUST stop the run before any file is read, and verification MUST need no network access. A file whose signature does not verify MUST stop the run without writing. No private key or other secret is involved.
- **FR-003**: The snapshot date MUST be the date in the six file names. When the six files do not share one batch ID, or no single snapshot date can be read from their names, the command MUST stop without writing.
- **FR-004**: When one of the six object files is missing, or the folder holds more than one file for the same object, the command MUST stop without writing and name the files concerned.
- **FR-005**: The snapshot MUST keep only EU records: national records that the distributing customs authority adds to its export, such as Swedish alcohol taxes, MUST be dropped. Of the EU records, it MUST keep only codes and measures valid on the snapshot date: a record is valid when its start date is on or before the snapshot date and its end date is empty or not before it. The load date is recorded but does not affect validity, and lookups use the same snapshot date (FR-017).
- **FR-006**: Only goods records with product-line suffix 80 MUST be kept as codes; records with any other suffix are grouping lines and MUST be skipped. For every code kept, the snapshot MUST hold the full 10-digit code, its CN-8 prefix, its TARIC description and its validity dates.
- **FR-007**: The TARIC description MUST come only from the English (EN) goods-nomenclature description. Only codes whose digits 9 and 10 are not 00 carry one; TARIC description text for digits 1 to 8 MUST NOT be stored or used.
- **FR-008**: A code MUST count as declarable when no other kept code lies beneath it in the code hierarchy. A code with codes beneath it, such as the own code of a CN-8 that TARIC subdivides, is a parent: it is never a subdivision.
- **FR-009**: For every measure kept, whatever level of the code it is recorded against, the snapshot MUST hold TARIC's measure identifier, the 10-digit code, the measure type code and label, whether the measure type applies to import, export or both, the geographical area code (for example CN for China, 1011 for erga omnes), the additional code when the measure carries one, the duty expression as text, the regulation reference and the validity dates. The duty text MUST be built from the measure's duty components in a fixed order, for example "22 %" or "4.2 EUR / 100 kg".
- **FR-010**: The snapshot file MUST hold exactly one snapshot record with the file format version, the snapshot date, the batch ID, the export id that the six files share, the six source file names, the load time, the number of code records (every stored suffix-80 code, parents included), the number of measure records and the number of CN-8 mismatches.
- **FR-011**: For every distinct CN-8 prefix among the declarable codes, the command MUST check whether the CN 2026 nomenclature has that CN-8; parent codes MUST be excluded from this count. Each prefix that CN 2026 lacks MUST be logged with its code and counted, and its codes and measures MUST still be stored; nothing is corrected automatically.
- **FR-012**: At the end the command MUST print a summary with the snapshot date, the batch ID, the six file names, the counts of code and measure records, the mismatch count with where the mismatching codes are logged, and, when a snapshot is replaced, the previous snapshot date.
- **FR-013**: A run that fails at any step MUST leave the existing snapshot file, if any, unchanged.

#### Re-running

- **FR-014**: When a snapshot file exists whose snapshot date equals the date in the six file names, the command MUST report a skip and leave the file unchanged, unless the operator asks for a forced rewrite.
- **FR-015**: A forced rewrite MUST replace the whole file. For the same extract it MUST produce the same records in the same order, differing only in the load time.
- **FR-016**: A run MUST never produce duplicate records: no two code records may share a 10-digit code, and no two measure records may share a TARIC measure identifier.

#### Lookup

- **FR-017**: The system MUST provide a lookup that takes a CN-8 code and an origin, China by default, and returns the subdivisions under that CN-8 that are valid on the snapshot date: the CN-8's own code ending in 00 when TARIC does not subdivide it, otherwise the declarable codes beneath it.
- **FR-018**: Each returned subdivision MUST carry its TARIC description and the measures that apply to it on the snapshot date: those whose geographical area is the origin itself or erga omnes (1011), whose measure type applies to imports (import, or both import and export), recorded against the subdivision or against any higher level of its code (CN-8, subheading, heading, chapter). Export-only measures MUST never be returned. Each measure MUST carry its additional code when it has one, so that company-specific anti-dumping rates can be told apart. Measures for country groups that contain the origin, and erga omnes measures that exclude it, are not covered.
- **FR-019**: An empty result MUST mean that TARIC has no subdivision for that CN-8 on the snapshot date. A code that is not 8 digits after removing spaces and dots MUST be rejected as invalid input, never answered with an empty result.
- **FR-020**: The snapshot MUST be loaded once when the app starts and MUST stay read-only while the app runs.
- **FR-021**: This feature MUST NOT connect the lookup to the assistant, the suggestion data or the screen; that is Spec 2.

#### Authority of CN 2026

- **FR-022**: The CN 2026 nomenclature MUST remain the only source for retrieval, chunking, validation and descriptions at digits 1 to 8.
- **FR-023**: TARIC data MUST never be embedded or added to any search index, and the CN 2026 and BTI search indexes MUST NOT change.

#### Sidebar

- **FR-024**: The sidebar MUST show one caption with the TARIC snapshot date and the CN-8 mismatch count, or "TARIC not loaded" when the snapshot file is absent or cannot be read. The app MUST start and work as before when the snapshot file is absent or cannot be read, and no other screen element changes.

#### Records

- **FR-025**: The TARIC snapshot MUST be recorded in the project's data-source register with its source, snapshot date and retrieval date, like the other datasets, also on a machine where the knowledge base's search indexes have never been built.

### Key Entities

- **Extract File Set**: the per-object files of one full extract. Each is signed by Swedish Customs, and its name carries the object name, the batch ID and the snapshot date. Six of them are read.
- **TARIC Snapshot**: the one snapshot record of the snapshot file: file format version, snapshot date, batch ID, export id, the six source file names, load time, the counts of code and measure records, and the CN-8 mismatch count.
- **TARIC Code**: a goods record with product-line suffix 80: the 10-digit code, its CN-8 prefix, its English TARIC description (only for digits 9 and 10) and its validity dates. It is declarable when no other code lies beneath it, and then it is a subdivision of its CN-8; otherwise it is a parent.
- **Measure**: a rule recorded against a 10-digit code at any level of the hierarchy, identified by TARIC's measure identifier: measure type code and label, the trade movement of its type (import, export or both), geographical area code, additional code when present, duty expression as text, regulation reference and validity dates. It applies to the code it is recorded against and to every code beneath it.
- **CN-8 Mismatch**: the CN-8 prefix of a declarable code that the CN 2026 nomenclature does not have. It is logged and counted, and its records are still stored.
- **Lookup Result**: for one CN-8 and one origin, the subdivisions valid on the snapshot date, each with its description and applicable measures; empty when TARIC has no subdivision for that CN-8.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 20 CN-8 codes chosen beneath the labelled test lines' subheadings, the subdivisions and China-origin measures returned by the lookup, including the additional code of each anti-dumping measure, match EZT-online for the snapshot date: 20 of 20.
- **SC-002**: Running the load twice on the same extract leaves an identical snapshot file, and the second run reports a skip: 100%.
- **SC-003**: The automated checks pass without network access and without any secret key. Against a small sample extract signed with a throwaway test key, they cover reading, validity filtering, mismatch counting and lookups for a CN-8 with a single subdivision, with several subdivisions and with none. They also cover the signature check: a correctly signed file is accepted, a tampered file and a file signed by another key are refused, and one small real Swedish Customs file verifies against the project's copy of the real key.
- **SC-004**: With no snapshot file, the app starts, shows "TARIC not loaded" and checks a packing list as before.
- **SC-005**: Loading a snapshot leaves the CN 2026 and BTI search indexes identical to how they were before.
- **SC-006**: A full load finishes in under 30 minutes on the author's machine.
- **SC-007**: With a snapshot present, app startup takes at most 10 seconds longer than without one, and a lookup answers in under 1 second.

## Assumptions

- The operator downloads the per-object files of one batch by hand. The Swedish Customs public key, published on the distribution page, is kept as a copy in the project; it is public, so keeping it in the repository is safe, and no secret is needed to load the extract.
- "Single subdivision" means a CN-8 that TARIC does not subdivide (one code, the CN-8's own code ending in 00); "multiple subdivisions" means a CN-8 that TARIC subdivides; "no subdivision" means a CN-8 that TARIC does not have on the snapshot date.
- Measures apply downwards: a measure recorded against a CN-8, subheading, heading or chapter applies to every subdivision beneath it, as in the published tariff.
- Lookups answer an import question, so export-only measures such as export controls are never returned (FR-018). Confirmed by the author on 2026-10-22.
- The loader keeps EU records only, dropping the Swedish national records in the Swedish Customs export (FR-005). Confirmed by the author on 2026-10-22.
- Known limitation: measures for country groups that contain the origin, and erga omnes measures that exclude it, are not handled; the company behind an additional code is not named; and full temporary stops are not applied (research R-04: the extract holds 37, dated 1995 to 2025; they do link to the regulations they stop, but none of them stops a measure in force on the 2026-10-01 extract). If one of the 20 codes for SC-001 is affected, the comparison shows a mismatch for it, and the author decides whether to pick another code or extend the lookup in a later feature.
- Known limitation: Meursing agricultural components and sugar and flour additional duties are not represented, so composite agricultural goods show the base duty only. The loader drops these Meursing-table measures (measure types 672, 673 and 674, which carry no goods code) and logs their count (research R-14). Decided by the author on 2026-10-22.
- The labelled test set holds HS-6 codes. The author picks the 20 CN-8 codes for SC-001 beneath those subheadings, including codes with anti-dumping measures, and records the EZT-online result for each by hand; EZT-online offers no machine access.
- The CN 2026 nomenclature lists its CN-8 codes inside the subheading texts; the reconciliation reads them from the `CN dddd dd dd` lines of those texts (research R-09).
- The snapshot file is not kept in the repository. The loader regenerates it from the signed extract, it runs to about 56 MB (2026-10-01 extract), and it is listed in .gitignore.
- Constitution v1.1.0 puts CN-8 and TARIC-10 in scope. This feature adds no assistant tool; the lookup is a function that Spec 2 will connect. Principle I's code rules still speak only of HS-6 codes, which matters once Spec 2 shows TARIC codes.
- Design constraints set by the author, carried into planning:
  - The snapshot file is `data/taric.jsonl`, one record per line, with the kinds goods_nomenclature, measure and snapshot distinguished by a kind field. The measure record also holds TARIC's measure identifier, the trade movement of its measure type and, when the measure carries one, the additional code.
  - An in-memory `TaricStore` in `rag/taric.py`, modelled on the existing ruling store `BTIStore`, is loaded once at startup and read-only at runtime.
  - The load command is `rag/loader.py --taric [directory]`, reading `data/raw/taric/` by default, with `--force` for a forced rewrite.
  - Input files are named `ObjectName_batchId_YYMMDD.xml.gz.pgp`. Signatures are verified against a copy of the public key kept in the project, pinned to fingerprint 410160CE25CEC2FF322784E7302AC3C1D0E3E1C9 (key ID 302AC3C1D0E3E1C9), and no private key is needed anywhere.
  - The lookup is `lookup_taric(cn8, origin="CN")` on the store.
  - Unit tests run against a small fixture extract with no network and no secret key. The fixture files are signed with a throwaway test key created in a temporary gpg home; only its public key and the signed files are kept with the fixtures, never a secret key. One small real signed Swedish Customs file is kept to verify against the project's copy of the real key.
- Out of scope: nightly or scheduled refresh; daily difference files; change alerts; the German national layer (EZT-online stays the link-out); duty calculation; quota data; assistant or screen integration beyond the sidebar caption; any change to the CN 2026 or BTI search indexes.
