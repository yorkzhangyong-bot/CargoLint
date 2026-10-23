# Research: TARIC Lookup Completeness for Country Groups and Exclusions (Phase 0)

All figures come from read-only runs on 2026-10-23 against the real extract in `data/raw/taric/` (export id
`3dc153a8-7542-4d91-8157-b7784f72797b`) and the schema-1 snapshot `data/taric.jsonl` that feature 002 wrote from it.
"D" is the snapshot date, 2026-10-01. The probe scripts ran outside the repository and changed nothing in it.

## R-01 Group memberships

**Decision**: the loader records, for every EU geographical area valid on D, the groups it belongs to on D.

- **Source**: `geographicalAreaMembership` elements inside the *member's* `geographicalArea` record. Each names its group
  by SID (`SIDGeographicalAreaGroup`) and has its own `dateStart` and optional `dateEnd`. The group's id comes from the
  EU `geographicalArea` record with that SID.
- **Kept**: memberships that are EU (`national="0"`) and valid on D (start on or before D, end empty or not before D),
  between two EU areas valid on D (FR-001).
- **Stored**: on the member's area record, as the sorted list of group ids (`member_of`, data-model §2).
- **Transitive resolution** (FR-005): the lookup follows `member_of` from the origin, and from every group reached, until
  nothing new is found; a set of visited areas ends any cycle.
- **Parent groups**: the `SIDParentGroup` attribute is not used. On D seven groups name a parent group (3500, 3100 → 1008;
  2007, 2006 → 1030; 5008, 2000, 1098 → 1011), and in every case all their members are already explicit members of the
  parent, so following it would add nothing.
- **Inconsistent data**: a kept membership whose group SID names no EU area stops the load with the member and the SID
  named, like an unknown measure type in feature 002 (data-model §5). None occurs on D.

**Evidence (D)**:

| Item | Count |
|---|---|
| Geographical area records / EU / EU valid on D | 408 / 360 / 314 |
| Memberships of EU areas valid on D, kept | 2,805, held by 246 members |
| Memberships of those areas not kept (national, ended or not yet started) | 2,184 |
| Memberships naming an unknown group, or a group not valid on D | 0 |
| Memberships held by national areas | 0 |
| Groups that are members of another group | 0 |

**Rationale**: the file nests memberships under the member, so storing them on the member keeps one line per area and
makes the origin's own groups one dictionary read. Nesting does not occur on D, but the author asked for transitive
resolution, and it costs one loop.

**Alternatives considered**:
- One record per membership: about 2,800 more lines with nothing gained.
- Following `SIDParentGroup` as well: adds nothing on D (see above) and is not in the author's rule.

## R-02 Area names

**Decision**: each stored area carries the English (`languageId="EN"`) text of its description period valid on D; the
latest period wins if more than one is valid, as feature 002 does for code descriptions. An area without such a text
gets `""` (spec edge case). Texts are kept exactly as published, typos included: 4002 reads "All third coutries".

**Evidence (D)**: all 314 EU areas valid on D have an English name valid on D, and none has two valid description
periods. Examples: `1008` "All third countries", `1011` "ERGA OMNES", `5009` "Countries subject to safeguard duties -
GOES, Laminations and Cores".

**Rationale**: clarification Q2. The file is already read, and the schema changes anyway.

## R-03 Measure exclusions

**Decision**: the loader records, for every kept measure, the ids of its EU excluded areas (FR-002), sorted and without
duplicates; a measure without exclusions gets an empty list.

- **Source**: `measureExcludedGeographicalArea` elements inside `measure`, with `geographicalAreaId`, `SIDGeographicalArea`
  and `national`. The id is used directly.
- **No dates**: the element has none, so an exclusion applies for as long as its measure (spec assumption).
- **No check of the ids**: an excluded area that is not stored, for example one that ended before D, can never be in an
  origin's set of applicable areas, so it never matters.

**Evidence**: the Measure file holds 248,862 exclusion elements. 62,250 EU measures have at least one, and 10,581 of the
161,959 measures in the snapshot do.

## R-04 The lookup rule and its effect for China

**Decision** (FR-005, FR-006, FR-007): for an origin O, the applicable areas are O, every group reached from O through
`member_of`, and `1011`. A measure is returned when all of the following hold:
- its geographical area is applicable;
- none of its excluded areas is applicable;
- its trade movement is import or both;
- its type is not 566.

Sorting, inheritance along the parent chain and input checks stay as in feature 002.

**Evidence for O = CN on D**, counted over the whole snapshot (import or both):

| Item | Measures |
|---|---|
| Returned by feature 002's rule (CN or 1011) | 40,914 |
| Recorded for the 15 groups besides 1011 that contain China (R-13 of feature 002) | 1,549 |
| … of which exclude China, so stay out | 37 (tariff quotas 122 on 5009, 1008, 2500 and 5007; additional duties 696 on 5007) |
| Erga omnes measures that exclude China, now left out | 1,238 (566: 881; 122: 161; 552: 127; 713: 24; 564: 20; 554: 20; 415: 3; 464: 2) |
| Type 566 measures that apply to China without an exclusion, now filtered | 75 (70 erga omnes, 5 for CN) |
| Measures excluding a group that contains China | 0 |
| Returned by the new rule | 41,113 = 40,914 + 1,512 − 1,238 − 75 |

**Consequences for acceptance**:
- No measure on D excludes a group containing China. The spec's US2 scenario 2 and the second half of SC-002 are
  therefore proven by fixture tests only; the real snapshot has no instance.
- The 37 group measures that exclude China are real examples of the exclusion rule applied to a group measure, for
  example tariff quota 122 for group 1008 on 0703 20 00 00.

## R-05 Groups containing China on D (FR-010)

**Decision**: the list lives in this research note, not in the snapshot record. The snapshot record stays independent of
any origin, and the loader summary reports the generic counts (clarification Q3).

| Group | Members on D | English name valid on D |
|---|---|---|
| 1005 | 211 | Statistical surveillance |
| 1008 | 217 | All third countries |
| 1011 | 218 | ERGA OMNES |
| 1030 | 151 | GSP (General System of Preferences) - Eligible countries |
| 2500 | 139 | Member countries of WTO |
| 3100 | 174 | Countries - export restriction protective equipment R 2020/568 |
| 3200 | 100 | Countries - export restrictions - SARS-related coronaviruses (SARS-CoV species) |
| 3300 | 100 | Countries - export restrictions - SARS-related coronaviruses (SARS-CoV species |
| 4002 | 197 | Phytosanitary - All third coutries, excluding: AL, AD, AM, AZ, BY, BA, FO, GE, IS, LI, MD, ME, MK, NO, SM, XS, CH, TR, UA, GB, ex RU |
| 4003 | 14 | Phytosanitary – BY CA CN IL JP KP KR KZ MN RU SH TW UA US |
| 4011 | 41 | Phytosanitary – AE AF BD BH BN BT CN ID IN IQ IR JO JP KG KH KP KR KW KZ LA LB LK MM MN MV MY NP OM PH PK QA SA SG SY TH TJ TL TM UZ VN YE |
| 4013 | 6 | Phytosanitary -  CN, KR, KP, RU, TW, VN |
| 5001 | 105 | Countries subject to safeguard measures |
| 5005 | 104 | Countries subject to safeguard measures |
| 5007 | 103 | Countries subject to safeguard duties - ferro-alloying elements |
| 5009 | 97 | Countries subject to safeguard duties - GOES, Laminations and Cores |

China is a direct member of all of them: the 15 groups besides erga omnes, 16 with 1011, which the rule includes for every origin anyway. Only
eight of them carry import measures on D (1008: 1,346; 4002: 41; 5009: 41; 2500: 32; 4011: 30; 4003: 26; 4013: 25;
5007: 8). By type: veterinary control 410 (443), tariff quotas 122 (437) and 123 (71), plant control 415 (122), import
control 763 (122), declaration of subheading 481 (80), CBAM 775 (79), mercury control 748 (65), cultural goods control
734 (61) and a few others. None is a preference, so the spec's preference edge case does not arise for China on D.
The acceptance aid's list `CHINA_GROUPS` matches this table.

**Rationale**: the acceptance asks for the list once, as evidence. A header field holding one origin's groups would
make the generic snapshot record origin-specific and need a schema field for a one-time check.

## R-06 Measure type 566

**Decision**: the lookup never returns type 566 (FR-007). The records stay in the snapshot file and in its
`measure_records` count; the store does not keep them in memory, because no lookup can return them (R-07).

**Evidence (D)**:
- The file holds 968 type-566 records.
- The six acceptance codes that showed 566 are 3924 90 00, 7318 15 42, 7318 15 58, 7318 15 68, 7318 15 82 and
  7318 15 95. On all six, the 566 measures are erga omnes measures that exclude China, so the exclusion rule (R-04)
  already removes them.
- The type filter matters for the 75 type-566 measures that do apply to China, for example on 2710 19 11 10 (one for
  1011, one for CN). That code is the independent check for US3 (quickstart scenario F).

## R-07 Startup time (US4, FR-011, clarification Q1)

**Decision**: keep loading the snapshot once at app start, and make it cheaper in three ways:
1. **A positional line format** for the bulk records (R-08).
2. **A lean read path**:
   - the store keeps measures as tuples of interned strings;
   - it builds the frozen `TaricMeasure` and `TaricSubdivision` results, and parses their dates, only when a lookup returns them;
   - it never builds record dataclasses while reading.
3. **No unusable measures in memory**: export-only measures (18,093 on D) and type-566 measures (968) stay in the file but are not kept, since no lookup can return them.

**Evidence**: the store load alone, today's file:

| Step | Time |
|---|---|
| Read the 184,321 lines | 0.10 s |
| `json.loads` of every line | 0.58 s |
| `TaricStore.from_jsonl` today: two frozen dataclasses per measure, a key-set check per line, `dataclasses.replace` to intern | 2.24 s |
| Lean read path on the same lines | 0.77 s |

**Evidence**: knowledge-base load at app start, measured like T037: a fresh process per run timing `open_knowledge_base`, with the snapshot path patched away for "without". Three alternating rounds:

| Variant | Opening time | Increase over "without" |
|---|---|---|
| without the snapshot | 3.87–4.01 s | — |
| today's store | 6.22–6.72 s | +2.35 to +2.71 s |
| lean read path, keyed objects (today's layout) | 4.72–5.17 s | +0.85 to +1.16 s |
| lean read path, positional arrays | 4.53–4.78 s | +0.66 to +0.80 s |
| positional arrays with the garbage collector paused | 4.47–4.66 s | +0.60 to +0.70 s |

The machine was less loaded than during T037, which measured +4.3 to +4.4 s for today's store; the first run after the
file cache was cold took 20.8 s for reasons outside TARIC. The chosen design leaves about 1.2 s of the 2 s allowance
for slower days and for the new area and exclusion data.

**Alternatives considered**:
- **Keep keyed objects, lean read path only**: about +1.0 s today, which might pass on a busy day as T037's was, with
  little room left; the file stays 57 MB.
- **Pausing the garbage collector during the read**: about 0.1 s more, at the price of changing interpreter-wide state
  from library code.
- **A pickle or marshal cache**: fastest, but unpickling a file executes code from disk, marshal is tied to the Python
  version, and a second file must be kept in step with the first.
- **orjson**: a new dependency for the part (`json.loads`) that is no longer the bottleneck.
- **Loading in the background or on first use**: ruled out by clarification Q1.
- **SQLite**: out of scope by the constitution ("SQLite is roadmap") and feature 002's design constraint.

## R-08 Snapshot file, schema 2

**Decision**:
- **Header**: line 1 stays the keyed snapshot record, with `schema` 2. Its fields are unchanged, so `read_snapshot_header`, the data-source register row and the sidebar caption keep working unchanged.
- **Other lines**: positional JSON arrays whose first element names the kind, in this order:
  - `geographical_area` records by id;
  - `goods_nomenclature` records by code;
  - `measure` records by (code, SID).
- **Positions**: listed in [contracts/snapshot-file.md](contracts/snapshot-file.md).
- **Size**: the positional layout shrinks today's 57.3 MB file to 27.3 MB, before the area and exclusion data; about 28 MB is expected.

**Old files** (FR-003):
- **Loader**: `read_snapshot_header` already refuses another schema with `TaricFileError`, so the skip check already falls through and the load rewrites the file, even for the same extract. The loader now also logs the reason: `taric: data/taric.jsonl will be rewritten: schema 1 is not supported (expected 2)`.
- **App**: before that run, the app refuses the old file as feature 002 does for any other schema: the reason is logged, `kb.taric` is `None`, and the caption reads "TARIC not loaded" (spec edge case).

**Rationale**: the header is read on its own by three consumers and gains nothing from being positional; the bulk lines
are where the time goes (R-07). Keeping the kind tag as the first element keeps the file self-describing line by line.

## R-09 Acceptance re-run (FR-012, SC-003, SC-006)

**Decision**: update `tests/eval/taric_acceptance.py` and re-run it for the same 20 codes, against the EZT-online rows
stored on 2026-10-22 in `tests/eval/taric_acceptance_ezt.json` (offline, no new fetch). Changes:
- **The known gap is gone**: `load_raw`, `group_gap` and the "not returned, group gap" lines go, since the lookup now returns group measures; the raw-file reader would not read the positional format anyway.
- **Every area is compared**: the EZT-online comparison runs for each geographical area found on either side, CN, 1011, 1008 and any other, so a new mismatch shows up instead of being hidden (FR-012). The fixed "1008 rows" column becomes a regular comparison.
- **Names shown**: each measure line shows the area's name next to its code.
- **Real-data checks**: a `--counts` option prints, for the snapshot:
  - the groups containing the origin, with member counts (R-05);
  - the erga omnes measures that exclude the origin, and how many the lookup returns, which must be 0 (SC-002);
  - the type-566 records in the file, and how many the lookup returns, which must be 0 (US3).
- **Output**: the re-run rewrites `tests/eval/taric_acceptance.md`. Its Finding column is empty today, so nothing written by hand is lost; feature 002's version stays in git history (merge `87de5f3`).

**Expected result**, from the rule prototype on D and the stored rows:
- **1008 rows match**:
  - 3926 90 97 gains veterinary control 410 on all 14 subdivisions, and EZT-online lists 1008/410 on all 14;
  - 7318 15 20, 42, 58, 68, 82 and 95 gain 763 and 775 on every subdivision, matching the stored 1008 rows.
- **566 is gone** from the six codes (R-06).
- **No other group** carries a measure on the 20 codes.
- **The stored rows** hold 1,597 rows: CN 1,313, 1011 238, 1008 46.

**Hand check (SC-006)**: erga omnes measures that exclude China, which EZT-online lists with a country exclusion (Länderausschluss):
- 7307 93 11 91: definitive anti-dumping 552, 58.6 %, excluding CN, KR, MY, RU and TW;
- 8427 90 00 11: 552, 70.8 %, excluding CN only;
- 7301 10 00 00: tariff quota 122, excluding AE, CN, GB, IS, LI and NO.

For origin CN, neither EZT-online nor CargoLint should list the measure; for an origin it does not exclude, such as US, both should.

## R-10 Test strategy (Principle VII)

**Decision**: tests first, offline, against hand-made fixtures; the real snapshot is used only by the acceptance aid and the timing script.
- **Fixture extract** (`make_taric_fixtures.py`, regenerated and signed with fresh throwaway keys):
  - **Areas**:
    - names with an ended and a current English description period;
    - an area with a Swedish description only, so its name is empty;
    - an area that ended before D, which is not stored;
    - a national area, which is not stored.
  - **Memberships**:
    - valid on D, ended before D and starting after D;
    - a national membership;
    - a group that is a member of another group.
  - **Measures with exclusions**: including a national exclusion element, which is ignored.
  - **`expected.json`**: gains the three summary counts.
- **Hand-written store fixture** (`snapshot_small.jsonl`, rewritten in schema 2):
  - **Areas**: CN and US in 1008 and 1011; CN in a group nested inside another group; an area without a name.
  - **Measures**:
    - for 1008;
    - for the nested outer group;
    - an erga omnes measure excluding CN;
    - an erga omnes measure excluding a group that contains CN;
    - a 1008 measure excluding CN;
    - a type-566 measure;
    - feature 002's measures for CN, US and 1011.
- **What the tests prove**:
  - **Format**: schema-2 round trip and positions; malformed arrays, wrong widths and unknown kinds are refused; schema 1 is refused.
  - **Extract**: names valid on D; membership filtering and group mapping; exclusions read (EU only, sorted).
  - **Store**: transitive groups, the exclusion rule both ways, 566 and export-only filtered, names on measures, an empty name, origin without groups, no duplicates when 1011 also appears as a group.
  - **Loader**: an old-schema file is rewritten without `--force`, and the reason is logged; the summary shows the three counts.
- **Timing (SC-004)**: measured by hand with `tests/eval/kb_load_time.py`, which commits T037's method; it is not a unit test because it depends on the machine.
