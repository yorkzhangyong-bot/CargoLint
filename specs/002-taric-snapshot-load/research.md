# Research: One-Time TARIC Load for Digits 9 to 10 (Phase 0)

All figures come from read-only runs on 2026-10-22 against the real extract in `data/raw/taric/`. Its signatures are dated
2026-10-01, and its export id is `3dc153a8-7542-4d91-8157-b7784f72797b`. "D" is the snapshot date, 2026-10-01.

## R-01 The extract file set

**Decision**: the loader reads exactly one batch from the load folder (`data/raw/taric/` by default).

- **Files read**: the six object files whose names match
  `^(GoodsNomenclature|Measure|MeasureType|GeographicalArea|DutyExpression|Regulation)_(?P<batch>[^_]+)_(?P<yymmdd>\d{6})\.xml\.gz\.pgp$`.
- **Snapshot date**: YYMMDD becomes 20YY-MM-DD.
- **Consistency checks**:
  - the six names must share one batch and one date (FR-003);
  - the six XML documents must carry the same `<id>` export id, a free extra check;
  - each object appears exactly once (FR-004).
- **Everything else is ignored**: other object files, other extensions and the unpacked `.xml` copies.

**Rationale**: these are the author's verified facts about the distribution (spec, Clarifications). The export id is identical in all six files of the batch on disk, so cross-checking it costs nothing and catches mixed batches even if names are edited.

**Observation**: the local copies first lacked batch and date in their names. The author renamed them on 2026-10-22, and they now read `ObjectName_3dc153a8-7542-4d91-8157-b7784f72797b_261001.xml.gz.pgp`. The batch ID in the names equals the export id inside the files. The unpacked `*.xml` copies in the folder are ignored.

| Object | Signed size | Unpacked size |
|---|---|---|
| Measure | 29.3 MB | 804 MB |
| GoodsNomenclature | 3.5 MB | 36.7 MB |
| Regulation | 0.48 MB | 5.9 MB |
| GeographicalArea | 54 KB | 0.82 MB |
| MeasureType | 11 KB | 0.11 MB |
| DutyExpression | 2.8 KB | 22.8 KB |

**Alternatives considered**:
- Reading the batch and date from the XML: the date is not in the XML; the header only states `queryDateStart` 2014-01-01.
- Trusting any six files in the folder: rejected by FR-003 and FR-004.

## R-02 Signature verification

**Decision**: verify with the GnuPG command-line tool in a throwaway home folder, against the pinned project copy of the key.

- **Key**: `data/Tulltaxan_Fildistribution.asc`, pinned to fingerprint `410160CE25CEC2FF322784E7302AC3C1D0E3E1C9`. Its long key ID is 302AC3C1D0E3E1C9.
- **Order of steps**:
  1. Check the key copy with `--import-options show-only`. Its primary fingerprint must equal the pin; otherwise stop before any file is read (exit 2).
  2. Import it into a temporary home and verify each file.
- **No file paths are passed to gpg**:
  - gpg runs with `cwd` set to the temporary folder and `--homedir .`;
  - key and signed file go in on stdin;
  - the payload comes back on stdout (`--output - --decrypt`);
  - status lines go to stderr (`--status-fd 2`).
- **Acceptance rule**: exit code 0 and exactly one `VALIDSIG` whose primary-key fingerprint equals the pin. Any `BADSIG`, `ERRSIG`, `NO_PUBKEY`, `EXPKEYSIG` or `REVKEYSIG` fails the file.
- **Payload handling**: the payload is used only after the check passes. gpg writes one-pass-signed content before it has checked the signature, so output from a failed run must be discarded.
- **Finding gpg**:
  1. the `CARGOLINT_GPG` environment variable;
  2. `PATH`;
  3. Git for Windows' `usr\bin\gpg.exe`.

**Evidence**:
- **The key**: DSA primary key `302AC3C1D0E3E1C9`, "Taric Fildistribution", created 1999-12-22, no expiry. Its ElGamal subkey, used for encryption, is not involved.
- **The files**: each file is a ZIP-compressed packet. It holds a one-pass signature, a literal packet named `krypt.xml.gz` (the gzip) and a DSA/SHA-1 signature made 2026-10-01.
- **What passed**:
  - gpg 2.4.9 verified `DutyExpression` and `MeasureType` (`GOODSIG`, `VALIDSIG` with the pinned fingerprint);
  - the payloads, once unzipped, are byte-identical to the unpacked copies.
- **What failed as expected**: a copy with one flipped byte ended with exit 2, no `VALIDSIG` and an empty payload.
- **The Windows path problem**: Git for Windows' gpg treats `C:\...` and `C:/...` arguments as relative paths. For example, `--homedir C:\Users\…` became `/c/ai/CargoLint/C:\Users\…`. Hence the no-path invocation above, which works with Git's gpg and with a native Windows gpg alike.

**Alternatives considered**:
- **PGPy (pure Python)**: unmaintained since 2022 and not verified on Python 3.13.
- **pysequoia**: Sequoia's standard policy rejects SHA-1 data signatures, and every file here is DSA/SHA-1 signed.
- **A hand-written OpenPGP packet parser with `cryptography`**: security-sensitive code with no advantage over a mature verifier.
- **Passing Windows paths to gpg**: breaks with Git's gpg (above).

## R-03 XML format and streaming parse

**Decision**: parse each payload as a stream with `lxml.etree.iterparse` over `gzip.GzipFile(fileobj=BytesIO(payload))`.

- **Records**: filter with `tag=` on the record element and free each element after use, so the 804 MB measure XML is never on disk or fully in memory.
- **Parser options**: `resolve_entities=False`, `no_network=True` and `load_dtd=False` (Principle II).
- **Size limits**: the research scans used `huge_tree=True`. The loader keeps lxml's default limits unless the real files need otherwise. **Outcome (T021, 2026-10-22)**: all six files of the 2026-10-01 extract, including the 804 MB measure XML, parse with lxml's default limits (lxml 6.1.3, libxml2 2.11.9), so `huge_tree` stays off.

**Format, an Arctic Group export**:
- **Namespace and root**: `http://www.arcticgroup.se/tariff/arctictariff/export`. The root `<export>` holds `<id>` (the export id), `<exportType>` (for example `MeasureObject`), `<parameters><queryDateStart>2014-01-01</queryDateStart></parameters>` and `<items>`.
- **Values**: record values are attributes in the export namespace; English and Swedish texts are child elements with `languageId`.

| Object | Record element | Child elements used |
|---|---|---|
| GoodsNomenclature | `goodsNomenclature` (code, `productLineSuffix`, `SID`, dates, `national`) | `goodsNomenclatureIndent` (`quantityIndents`, `dateStart`); `goodsNomenclatureDescriptionPeriod` (dates) with `goodsNomenclatureDescription` (`description`, `languageId`) |
| Measure | `measure` (`SID`, `goodsNomenclatureCode`, `measureType`, `geographicalAreaId`, `additionalCodeType`, `additionalCodeId`, `regulationId`, `regulationRoleType`, dates, `national`) | `measureComponent` (`dutyExpressionId`, `dutyAmount`, `monetaryUnitCode`, `measurementUnitCode`, `measurementUnitQualifierCode`); `measurePartialTemporaryStop` (dates). Not read: conditions, exclusions, footnotes |
| MeasureType | `measureType` (code, `tradeMovementCode`) | `measureTypeDescription` (EN) |
| GeographicalArea | `geographicalArea` (`geographicalAreaId`, `SID`) | not needed beyond the id (memberships not used, see R-13) |
| DutyExpression | `dutyExpression` (`dutyExpressionId`, applicability codes) | `dutyExpressionDescription` (EN) |
| Regulation | `baseRegulation`, `modificationRegulation`, `fullTemporaryStopRegulation` (id, OJ id and page, publication date, effective end date) | none |

**Timing**: the goods file parsed in 0.9 s and the measure file in 25.9 s (Python 3.13, lxml), so SC-006's 30 minutes holds with a wide margin.

**Alternatives considered**:
- Unpacking to disk first: rejected, because it means an extra 804 MB temporary file.
- `xml.etree` (stdlib): slower, and lxml is already a dependency.

## R-04 Validity on the snapshot date

**Decision**: a record is valid when `dateStart` ≤ D and `dateEnd` is missing or ≥ D, with D the snapshot date (clarified 2026-10-22).

- **Goods**:
  - the record's own dates;
  - the indent from the latest `goodsNomenclatureIndent` starting on or before D;
  - the description from the English text of the latest description period valid on D.
- **Measures**:
  - the measure's own dates;
  - not in force when a `measurePartialTemporaryStop` covers D (301 measures on D);
  - a measure without an end date also ends at its generating regulation's effective end date (`effectiveEndDate`, from the base or modification regulation). On D this ends 103,738 measures that the export leaves open-ended, for example the 2013 anti-dumping duties on solar panels from China, whose regulation ended in 2017 (measured in T021).
- **The `stoppedFlag` is not used on its own**: 2,956 measures carry it, but their stop records mostly lie in the past (for example 2014-01-20 to 2014-04-22).

**Rationale**: one reference date keeps the snapshot consistent with itself and makes "match EZT-online for the snapshot date" well defined.

**Known limitation**: the regulations file holds 37 full-temporary-stop regulations, 28 of them open-ended, dated 1995 to 2025. Each links to the regulations it stops through `fullTemporaryStopRegulationAction` (31 stopped regulations in all), so a stop could be applied to the measures of those regulations. Full stops are not applied: 22 of them cover D, but no measure in force on D belongs to a regulation they stop, so on the 2026-10-01 extract applying them would change nothing. (An earlier count of 68 regulations also counted the action lines.)

## R-05 EU records only

**Decision**: keep only records whose `national` attribute is `0`.

**Evidence**: the Swedish export mixes in Swedish national data:
- 23,457 national measures, for example measure type `SEALK` (Swedish alcohol tax in SEK), with negative SIDs and regulation `22156ALK`;
- one national goods record.

**Rationale**: CargoLint serves imports into Germany. Swedish national data is neither EU TARIC nor German, and the German national layer is out of scope, with EZT-online as the link-out. The author confirmed this on 2026-10-22, and it is recorded in the spec's assumptions.

**Alternatives considered**: keeping national records with a flag, rejected because it invites misuse.

## R-06 Declarable codes and parents from indents

**Decision**: work out the hierarchy per chapter.

- **Walk**: sort the valid records (suffix 80 and grouping lines) by (code, suffix) and walk them with an indent stack. Chapter records, whose codes end in eight zeros, act as roots at indent −1, so headings at indent 0 become their children.
- **Parent**: the nearest enclosing suffix-80 record. Grouping lines take part in the walk but are never parents and are not stored.
- **Declarable**: a suffix-80 record with nothing beneath it.
- **Stored fields**: each code record stores `declarable` and `parent`. These two derived fields are not in the author's field list. FR-008, FR-017 and FR-018 need them, and computing them once at load keeps lookups simple.

**Evidence (D)**:
- Of 25,866 EU goods records valid on D, 22,361 have suffix 80 and 16,742 are declarable.
- Of the declarable codes, 9,572 have digits 9 and 10 other than 00.
- Every one of the 9,791 CN 2026 CN-8 codes has at least one declarable TARIC code.
- CN-8 7318 15 58 yields 7318155810, 7318155860 and 7318155890, the "multiple subdivisions" case.

**Alternatives considered**: a prefix-only rule, rejected because it cannot see TARIC-level nesting and treats chapters and headings wrongly.

## R-07 Origin means import: trade movement filter

**Decision**: each measure record stores the trade movement of its measure type (`import`, `export` or `both`, from `tradeMovementCode` 0, 1 or 2). A lookup for an origin returns only `import` and `both` measures.

**Evidence (D)**:
- MeasureType defines 110 EU import types, 42 export types and 6 that cover both.
- Erga omnes measures in the snapshot: 22,165 import, 1,674 both and 179 export-only. Without the filter, the export-only ones would appear in every China lookup.

**Rationale**: "the measures that apply to goods from that origin" (FR-018) is an import question; EZT-online's import view shows no export controls. The author confirmed this reading on 2026-10-22, and it is recorded in the spec's assumptions.

**Alternatives considered**: dropping export measures at load, rejected because FR-005 keeps every measure valid on D, and storing the movement keeps the snapshot complete.

## R-08 Duty expression text, labels and regulation references

**Decision**: the duty text is the measure's components in ascending `dutyExpressionId` order, joined by spaces. Each component is a prefix, an amount and a unit:

- **Prefix**: comes from the expression. 01: none; 02: "−"; 04, 19, 20: "+"; 15: "MIN"; 17, 35: "MAX".
- **Amount**: trailing zeros are dropped, so 22.0 becomes 22.
- **Percentage**: "%" when there is no monetary unit, for example `22 %`.
- **Specific duty**: `{amount} {currency} / {unit}`. The unit labels are DTN = 100 kg, KGM = kg, TNE = 1000 kg, LTR = l, HLT = hl, MTQ = m³, MTK = m² and NAR = p/st; an unknown unit or qualifier code is kept as the code.
- **Components without an amount** use the short forms of their English description, for example `+ EA` for "+ agricultural component".
- **Conditional duties** follow the components, as display text that is never evaluated. Each measure condition that carries a duty becomes a clause, in sequence order:
  - with a document: `<duty> with <condition in words> <document code>`, for example `39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %`. Condition A reads "anti-dumping/countervailing document"; B and C read "certificate, licence or document". The document code (certificate type and code, such as D008) stays a code, because the Certificate object file is not read;
  - with a price threshold above zero: `<duty> if <price in words> is at least <threshold>`; V is the import price (entry prices), F the net free-at-frontier price, L the CIF price and M the declared price;
  - otherwise, the fallback: `otherwise <duty>`, placed last. A threshold of zero counts as the fallback;
  - action 11 reads `the difference to <duty>` (the difference to a minimum price), for example `0 EUR / 1000 kg if the net free-at-frontier price is at least 1316 EUR / 1000 kg; otherwise the difference to 1316 EUR / 1000 kg`;
  - conditions without a duty, such as licence requirements, add nothing. Clauses are joined by "; ".
- **Measures without components or conditional duties**, such as import controls, get an empty duty text.
- **Evidence (D)**: 17,292 measures carry their duty only in conditions, chiefly 13,734 definitive anti-dumping (552) and 2,576 countervailing (554) measures, where the company-specific rate applies with the commercial invoice (document D008). After this rule no anti-dumping or countervailing measure in the snapshot has an empty duty text (T028 follow-up, 2026-10-22).
- **Known gap**: duty expression 36 ("minus % CIF") has no prefix, so the 5 conditions that use it (type 652, eggs) read like `105.846 EUR / 100 kg 50 %`.

**Other fields**:
- **Measure type label**: the English `measureTypeDescription`.
- **Regulation id**: taken from the measure.
- **Regulation reference**: `OJ {officialJournalId}, p. {journalPage} ({datePublished})` from the base, modification or full-stop regulation with that id. When the regulation record lacks those fields it is empty.
- **Geographical areas**: stored by id only (CN, 1011, …).

**Rationale**: the rendering is deterministic, unit-testable and comparable by value with EZT-online. The MeasurementUnit object file is not among the six read, hence the small built-in unit table.

**Alternatives considered**:
- Storing raw components only: rejected, because FR-009 asks for the duty as text built from its components.
- Evaluating conditions, that is, choosing the rate that applies: rejected. The text shows every conditional rate; the clerk, or a later feature, decides which applies.

## R-09 Reconciliation against CN 2026

**Decision**: the CN 2026 CN-8 set comes from the nomenclature chunk texts, through a new `NomenclatureIndex.cn8_codes()`. Each CN-8 appears there as a line `CN dddd dd dd — …`.

- **Compared**: the CN-8 prefixes of declarable codes only, so parents are excluded (FR-011).
- **Logged**: each mismatching prefix goes to `store/logs/taric-cn8-mismatches-<snapshot date>.txt`, one per line with one TARIC code under it. The summary names that file.

**Evidence (D)**:
- The CN 2026 chunks hold 9,791 CN-8 codes, and the declarable TARIC codes span 9,896 CN-8 prefixes.
- 105 prefixes are not in CN 2026: 96 in chapter 98 (special codes such as 9880 01 00, complete industrial plants) and 9 in chapter 99.

**Alternatives considered**: re-parsing the CN 2026 RDF. It is 171 MB, git-ignored, and may be missing on another machine, whereas the jsonl is committed.

## R-10 Snapshot file, determinism and startup cost

**Decision**: `data/taric.jsonl` is UTF-8 with LF line endings and one JSON object per line.

- **Order**: line 1 is the snapshot record, then code records sorted by code, then measure records sorted by (code, measure SID). Keys always appear in the same order.
- **Write**: to `data/taric.jsonl.tmp`, then `os.replace`, so a failed run leaves the old file untouched (FR-013).
- **Skip check**: reads only the first line (FR-014).
- **Git**: the file is added to `.gitignore`. It is regenerated from the downloaded files and measured 57.3 MB on the 2026-10-01 extract (1 + 22,361 + 161,959 lines).
- **In memory**: `TaricStore` keeps compact records (dataclasses with `__slots__`, repeated strings interned), indexed by CN-8 for declarable codes and by code for measures.

**Rationale**: this follows the existing `data/*.jsonl` and `BTIStore` pattern (author's constraint). Byte-identical output for the same extract, apart from the load time, makes SC-002 and FR-015 directly testable.

**Startup**: about 184,000 lines are read once per server process, through `st.cache_resource`. A few seconds are expected; the time is measured against SC-007's 10 s in implementation.

**Alternatives considered**:
- SQLite: excluded by the author's design and the constitution.
- Pickle: opaque and version-fragile.
- Keeping only China and erga omnes measures: rejected, because the lookup takes any origin.

## R-11 Loader command and data-source register

**Decision**: `python -m rag.loader --taric [DIR]` runs only the TARIC load. DIR defaults to `data/raw/taric/`.

- **`--force` in this mode** rewrites only `data/taric.jsonl`.
- **Combining with other options**: `--taric` with `--demo`, `--chapters`, `--bti-chapters` or `--no-embed` is a usage error.
- **Exit codes**:
  - 0: loaded or skipped;
  - 1: the extract was refused or could not be loaded;
  - 2: usage or setup error (bad options, gpg missing, key copy missing or wrong).
- **Data-source register**: `SOURCES` gains a `taric` entry, and `write_sources_md` adds a TARIC row (source, snapshot date and batch, retrieval date from the signed files' modification time) when the snapshot exists. The TARIC mode does not regenerate the whole register. It replaces or inserts only the TARIC row of `data/SOURCES.md`, or creates a minimal register when none exists, and it never reads `store/index_meta.json`. `load_index_meta` raises when the knowledge base was never built (`rag/retriever.py`), so depending on it would break the load on a fresh machine (FR-025).

**Evidence**: today `main()` always runs nomenclature, rules, BTI, indexes and then SOURCES. Its `--force` deletes `store/chroma` and `store/chroma-bti` (`rag/loader.py` around lines 180–183). Without a separate mode, `--taric --force` could wipe both search indexes, against FR-023.

**Licence cell**, confirmed by the author on 2026-10-22: "Swedish Customs Tariff File Distribution, free of charge, no formal licence published; Swedish Customs provides the files without support; underlying data is EU TARIC from the European Commission." The distribution page itself states no licence, terms or fees.

**Alternatives considered**: a separate `python -m rag.taric` entry point, rejected because the author set `rag/loader.py --taric`.

## R-12 Test strategy

**Decision**: `tests/fixtures/make_taric_fixtures.py` writes tiny six-object extracts in the real format into `tests/fixtures/taric/`. They are gzipped and signed like the real files (compressed, one-pass, literal) with a throwaway key that the script creates in a temporary gpg home. Only the throwaway public keys and the signed files are kept. The script deletes the temporary home, so no secret key is ever committed (constitution, definition of done: no secrets in the repository). Nothing outside the tests trusts these public keys. The fixture set also holds:
- a tampered copy;
- a file signed by a second throwaway key;
- one real signed `DutyExpression` file from the 2026-10-01 batch (2.8 KB), verified against `data/Tulltaxan_Fildistribution.asc`.

**What the fixtures cover**:
- a national record;
- a grouping line;
- expired and future records;
- indent nesting, including a subdivided CN-8, an unsubdivided CN-8 and a CN-8 absent from TARIC;
- a measure on an HS-6 parent;
- measures for CN, 1011 and another country, plus an export-only erga omnes measure;
- anti-dumping measures with two additional codes;
- a suspended measure;
- a regulation with an OJ reference;
- an identical duplicate measure SID, and a conflicting one in a separate fixture;
- three Meursing-table measures and an EU measure on a national-only code (R-14).

**How the tests run**:
- **Parser tests** feed plain XML bytes and need no gpg.
- **Signature tests** call gpg and skip with a stated reason when it is missing.
- **The integration test** points all TARIC paths at a temporary folder and makes the index builders raise if they are called (SC-005).

**Rationale**: this satisfies the clarified SC-003 (no network, no secret, the signature check exercised both ways) and Principle VII (offline, tests first).

## R-13 The accepted limitation, sized

**Evidence (D, measures in the snapshot, import or both; recounted after T021)**:
- **Included wrongly**: 1,238 erga omnes measures exclude China, and the lookup will return them as if they applied.
- **Missed**: 1,549 measures for EU country groups that contain China (15 groups besides erga omnes). A further 3,984 group measures are export controls, which R-07 filters out anyway, chiefly dual-use authorisations (type 478, 1,410), waste (751, 719) and CITES (715, 645).
- **Not named**: the companies behind additional codes. That needs the AdditionalCode object file, which is not read.

**Consequence**: a sampled code for SC-001 may show a mismatch. The exclusion lists (in Measure) and the group memberships (in GeographicalArea) are both in the six files already read, so a later extension needs no new file.

## R-14 Measures no lookup can use

**Decision**: the snapshot drops two kinds of EU measure in force on D and logs how many of each it dropped (author's decision, 2026-10-22):
- **Meursing table**: measure types 672, 673 and 674, the agricultural component and the additional duties on sugar and flour. These measures carry no goods code; they are keyed by type-7 additional codes, which the duty of a composite agricultural good refers to through components such as "+ EA".
- **Measures on a code held only as a national record**: the goods file has the code only as a Swedish national record, so no EU code leads to it.

**Evidence (D)**: 23,184 Meursing-table measures, and 1 measure: a third-country duty on 9965000000, a Swedish national code for goods of residents returning from work abroad. Without them, every measure in the snapshot is recorded against a stored code.

**Consequence**: Meursing agricultural components and sugar and flour additional duties are not represented, so composite agricultural goods show the base duty only (spec known limitation).
