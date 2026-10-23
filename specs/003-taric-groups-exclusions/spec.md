# Feature Specification: TARIC Lookup Completeness for Country Groups and Exclusions

**Feature Branch**: `003-taric-groups-exclusions`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Feature: TARIC lookup completeness for country groups and exclusions (Spec 1b, extends feature 002). Background. Feature 002 loads the Swedish Customs TARIC snapshot and offers lookup_taric(cn8, origin) returning the TARIC subdivisions of a CN-8 with the import measures recorded for the origin itself and for erga omnes (1011). The SC-001 acceptance against EZT-online on 2026-10-22 confirmed two gaps: measures recorded for country groups that contain the origin are not returned (on every live 7318 15 fastener code EZT-online shows group 1008 measures: import control 763 and CBAM 775; on 3926 90 97 veterinary control 410), and erga omnes measures that exclude the origin are returned as if they applied. Research R-13 sized the gap on the 2026-10-01 snapshot: 1,549 import measures for 15 EU groups containing China are missed, and 1,238 erga omnes measures excluding China are wrongly returned. The same acceptance found that measure type 566 (anti-dumping/countervailing statistic) exists in TARIC but is not shown by EZT-online. T037 measured app startup at 9.6 to 10.1 s with the snapshot, against the constitution’s 10 s limit. All data needed is in the six files already read. User story 1, group measures (priority P1). As the lookup caller, I want measures recorded for any country group that contains the origin on the snapshot date to be returned alongside the origin’s own and erga omnes measures, so that controls and CBAM obligations recorded on groups such as 1008 reach the clerk. Group membership comes from the GeographicalArea file (membership records with their own validity dates); only memberships valid on the snapshot date count. Groups may be nested; membership is resolved transitively. Each returned measure keeps its own geo_area, so the caller can see whether it came from CN, from a group, or from 1011. Acceptance: on the 2026-10-01 snapshot, lookup_taric(“73181520”, “CN”) returns the 1008 measures 763 and 775; lookup_taric(“39269097”, “CN”) returns 410 on the relevant subdivision; the 15 groups containing CN are listed in the snapshot header or a research note with their membership counts. User story 2, exclusions (priority P1). As the lookup caller, I want a measure that lists the origin, or any group containing the origin, in its excluded geographical areas to be left out, so that erga omnes or group measures that do not apply to China are not shown as if they did. Exclusions come from the measure’s excluded-area records in the Measure file. Acceptance: the 1,238 erga omnes measures excluding China are no longer returned for origin CN; a measure excluding a group that contains CN is also left out; at least one live code where EZT-online shows a Länderausschluss is checked by hand. User story 3, display filter for statistic measures (priority P2). As the lookup caller, I want measure type 566 excluded from lookup results, so that results match what EZT-online shows the clerk. The records stay in the snapshot file; only the lookup filters them. Acceptance: the six SC-001 codes that previously showed 566 no longer do; the snapshot file is unchanged by this story. User story 4, startup time (priority P2). As the app user, I want the TARIC store to load fast enough that app startup stays clearly under the constitution’s 10 s limit, so that Spec 2 has room to add its own work. Acceptance: on the author’s machine, startup with the snapshot is at most 2 s slower than without it, measured as in T037, and the full offline suite still passes. Functional requirements. The loader must record group memberships valid on the snapshot date and each measure’s excluded areas in the snapshot file; the snapshot schema version is bumped and the loader rewrites the file on the next --taric run even with the same extract, with a logged reason. The lookup must resolve the set of areas applying to an origin as: the origin, every group containing it transitively on the snapshot date, and 1011. A measure is returned when its geo_area is in that set and none of its excluded areas is in that set. Export-only measures and type 566 are never returned. Parent-chain inheritance from feature 002 is unchanged. lookup_taric keeps its signature. The acceptance aid tests/eval/taric_acceptance.py is re-run for the same 20 codes; the 1008 rows previously marked “known gap” must now match, and any new mismatch is reported, not hidden. Out of scope. Company names behind additional codes (needs the AdditionalCode file), certificate descriptions such as D008 (needs the Certificate file), full temporary stops, Spec 2’s agent and UI work, any change to the CN 2026 or EBTI indexes. Constraints. Same constitution rules as feature 002: no new network access, no secrets, tests before code, the loader driven by the six files only, the CN 2026 index untouched. Keep the existing 391 tests passing."

## Clarifications

### Session 2026-10-23

- Q: Can the 2 s startup target be met by loading the TARIC data after the app has started, or must the load at app start itself become faster? → A: The load at app start becomes faster. The TARIC data is still loaded once when the app starts, as feature 002 requires (its FR-020); it is not loaded in the background or on first use.
- Q: Should the snapshot also record each geographical area's English name, so a group measure can be shown as "1008 All third countries" instead of the bare code? → A: Yes. The snapshot records the English name valid on the snapshot date for every geographical area, and each returned measure carries its area's name next to the code.
- Q: Should the load summary also report how many group memberships, area names and measure exclusions the new snapshot holds? → A: Yes. The summary adds three counts: memberships kept, area names kept, and measures that exclude at least one area. Everything else in it stays as in feature 002.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Return measures for country groups that contain the origin (Priority: P1)

A later feature (Spec 2) asks the lookup for a CN-8 code and an origin, China by default. Today the lookup returns only the measures recorded for the origin itself and for erga omnes, so obligations recorded for a country group that contains the origin never reach the clerk, such as the import control and the CBAM measure recorded for group 1008, all third countries. With this story the lookup also returns the measures of every country group that contains the origin on the snapshot date, directly or through another group. Each returned measure keeps its own geographical area code and carries the area's English name, so the caller can tell a measure for the origin from a group measure or an erga omnes one, and the clerk can see what a group code stands for.

**Why this priority**: The acceptance check against EZT-online confirmed the gap on live codes: import control 763 and CBAM 775 for group 1008 on every 7318 15 fastener code checked, and veterinary control 410 for group 1008 under 3926 90 97. Spec 2 must not show measures to the clerk while obligations like these are missing.

**Independent Test**: With the 2026-10-01 snapshot loaded, look up 7318 15 20 and 3926 90 97 for China and check that the group 1008 measures appear, each shown with geographical area 1008 and its name, All third countries.

**Acceptance Scenarios**:

1. **Given** the 2026-10-01 snapshot, **When** 7318 15 20 is looked up for China, **Then** the result includes import control 763 and CBAM 775 recorded for group 1008, each shown with geographical area 1008 and the name All third countries.
2. **Given** the same snapshot, **When** 3926 90 97 is looked up for China, **Then** veterinary control 410 for group 1008 appears on the subdivisions it applies to.
3. **Given** a group whose membership of the origin ended before the snapshot date or starts after it, **When** a code carrying a measure for that group is looked up, **Then** that measure is not returned.
4. **Given** the origin is a member of group A and group A is a member of group B on the snapshot date, **When** a code carrying a measure for group B is looked up, **Then** the measure is returned.
5. **Given** a measure recorded for a group that does not contain the origin, **When** its code is looked up, **Then** the measure is not returned.
6. **Given** the 2026-10-01 snapshot, **When** the author asks which groups contain China on the snapshot date, **Then** the 15 groups besides erga omnes, 16 with 1011, are listed, each with its number of members.

---

### User Story 2 - Leave out measures that exclude the origin (Priority: P1)

Some erga omnes and group measures name areas they do not apply to. Today such a measure is returned for China even when China, or a group that contains China, is among its excluded areas. With this story the lookup leaves such a measure out, so a measure that does not apply to China is never shown as if it did.

**Why this priority**: On the 2026-10-01 snapshot, 1,238 erga omnes measures that apply to imports exclude China, and the lookup currently returns every one of them as if it applied (feature 002, research R-13).

**Independent Test**: Take an erga omnes measure that excludes China in the snapshot, look up its code for China and for an origin it does not exclude, and compare the two results.

**Acceptance Scenarios**:

1. **Given** an erga omnes measure that lists China among its excluded areas, **When** its code is looked up for China, **Then** the measure is not returned; **When** the same code is looked up for an origin the measure does not exclude, **Then** it is returned.
2. **Given** a test fixture with a measure that excludes a group containing China, **When** its code is looked up for China, **Then** the measure is not returned. This case is proven by fixtures only: no measure on the 2026-10-01 snapshot excludes a group that contains China.
3. **Given** the 2026-10-01 snapshot, **When** codes are looked up for China, **Then** none of the 1,238 erga omnes measures that exclude China is returned.
4. **Given** a live code for which EZT-online shows a country exclusion (Länderausschluss) affecting China, **When** the author compares it by hand, **Then** CargoLint and EZT-online agree.

---

### User Story 3 - Hide statistic measures from lookup results (Priority: P2)

Measure type 566, the anti-dumping/countervailing statistic, exists in TARIC, but EZT-online does not show it to the clerk. With this story the lookup leaves it out. The records stay in the snapshot file; only the lookup filters them.

**Why this priority**: In the acceptance check the lookup returned type 566 on six of the 20 codes, and EZT-online showed it on none. Results should match what the clerk sees in EZT-online. The gap is cosmetic rather than a missing obligation, hence P2.

**Independent Test**: Look up 2710 19 11 for China, where type 566 applies to China without an exclusion, and check that no 566 measure appears, while the snapshot file still holds the 566 records.

**Note**: on the 2026-10-01 snapshot, the type 566 measures on the six acceptance codes are erga omnes measures that exclude China, so the exclusion rule of User Story 2 removes them as well. The 566 filter itself is demonstrated with 2710 19 11, where type 566 applies to China without an exclusion.

**Acceptance Scenarios**:

1. **Given** the six acceptance codes that previously showed measure type 566, **When** they are looked up for China, **Then** no 566 measure is returned.
2. **Given** the snapshot file, **When** this story is in place, **Then** the file still holds the 566 records; this story itself changes no file content.

---

### User Story 4 - Keep app startup fast with the snapshot (Priority: P2)

As the app user, I want the TARIC snapshot to load faster at app start, so that it adds little to startup and Spec 2 has room to add its own work without making the app slow to open. The data is still loaded once when the app starts, as in feature 002.

**Why this priority**: Feature 002's validation (T037) measured startup at 9.6 to 10.1 s with the snapshot against 5.2 to 5.9 s without it, an increase of 4.3 to 4.4 s. That is within feature 002's allowance of 10 s more, but it leaves the absolute startup close to 10 s before Spec 2 adds anything.

**Independent Test**: Measure the knowledge-base load time at app start with and without the snapshot file, as feature 002's T037 did (its quickstart scenario I), and compare the times.

**Acceptance Scenarios**:

1. **Given** the snapshot written by this feature, **When** the knowledge-base load time at app start is measured with and without it as in T037, **Then** the load with the snapshot is at most 2 s slower, and the TARIC data is fully loaded once the knowledge base is open.
2. **Given** this feature's changes, **When** the full offline test suite runs, **Then** every test passes.

---

### Edge Cases

- A membership whose start date is after the snapshot date, or whose end date is before it, does not count.
- An origin that belongs to a group both directly and through another group: the group counts once, and its measures are returned once.
- Group memberships that form a cycle (group A in group B and B in A) end the resolution without looping; this should not occur in TARIC data.
- An origin that is not a member of any group, for example an area unknown to TARIC: only the measures for the origin itself and erga omnes apply, minus those that exclude the origin.
- A measure that excludes an area other than the origin or a group containing it is still returned.
- A measure recorded for a group that contains the origin and that also excludes the origin is left out: the exclusion wins.
- Erga omnes appears in the membership data as a group that contains the origin: it is in the set of applicable areas either way, and its measures are not returned twice.
- A geographical area with no English name valid on the snapshot date: its measures carry an empty name, and the code is still shown.
- A preference measure recorded for a group that contains the origin is returned like any other measure; whether the goods qualify for the preference, for example by proof of origin, is not judged.
- A snapshot file written by feature 002 in the previous format: the next load run rewrites it even for the same extract and logs why; until then the app reads it as not loaded ("TARIC not loaded").
- Export-only measures stay out of every result, as in feature 002.

## Requirements *(mandatory)*

### Functional Requirements

#### Loading

- **FR-001**: The load command MUST record in the snapshot file every country-group membership that is valid on the snapshot date, as its group and its member, and the English name of every geographical area as valid on the snapshot date. A membership or name is valid when it starts on or before the snapshot date and its end date is empty or not before it.
- **FR-002**: The load command MUST record, for every measure kept, the geographical areas that the measure excludes, as listed for that measure in the Measure file.
- **FR-003**: The snapshot file format version MUST increase. A snapshot file in the previous format MUST be rewritten by the next load run even when the extract's date equals the snapshot's, and the run MUST log why it rewrites the file.
- **FR-004**: The load summary MUST also report three counts: the memberships kept, the area names kept, and the measures that exclude at least one area. Everything else the load command does in feature 002 MUST stay unchanged: the six files read, the signature check, the EU-only and validity rules, the dropped measures, the reconciliation and the rest of the summary.

#### Lookup

- **FR-005**: For an origin, the lookup MUST resolve the set of applicable areas on the snapshot date: the origin itself, every country group that contains the origin directly or through other groups, and erga omnes (1011).
- **FR-006**: The lookup MUST return a measure when its geographical area is in the origin's set of applicable areas and none of its excluded areas is in that set.
- **FR-007**: Export-only measures and measures of type 566 MUST never be returned. Their records stay in the snapshot file.
- **FR-008**: Each returned measure MUST keep its own geographical area code and carry that area's English name valid on the snapshot date, so a measure for the origin, a group measure and an erga omnes measure can be told apart.
- **FR-009**: Inheritance of measures from the codes above each subdivision, the input rules, the result order and the form of the lookup's inputs and results MUST stay as in feature 002, except that each returned measure gains its area's name (FR-008).
- **FR-010**: The country groups that contain China on the snapshot date MUST be listed with the number of members of each. Planning settled where: in a research note (research R-05), not in the snapshot record.

#### Startup

- **FR-011**: With the snapshot written by this feature, opening the knowledge base at app start MUST take at most 2 s longer than without the snapshot, measured as in feature 002's T037. The TARIC data MUST still be loaded once when the app starts, as feature 002 requires (its FR-020); the target is met by a faster load, not by loading in the background or on first use.

#### Acceptance and scope

- **FR-012**: Feature 002's acceptance aid MUST be re-run for the same 20 codes. The group 1008 rows previously marked as the known gap MUST now match EZT-online, and every new mismatch MUST be reported, not hidden.
- **FR-013**: This feature MUST NOT change the CN 2026 or EBTI search indexes, MUST read only the six object files of feature 002, and MUST need no network access during the load and no secret.

### Key Entities

- **Group Membership**: a geographical area belonging to a country group. The source gives each membership its own validity dates; only memberships valid on the snapshot date are kept. A member can itself be a group.
- **Applicable Area Set**: for one origin on the snapshot date, the origin, every group that contains it directly or through other groups, and erga omnes. It decides which measures apply to goods from that origin.
- **Measure Exclusion**: a geographical area that a measure explicitly does not apply to. A measure gains the list of its excluded areas.
- **Area Name**: the English name of a geographical area valid on the snapshot date, for example "All third countries" for 1008. The GeographicalArea file gives each name its own validity period.
- **Lookup Result** (from feature 002): the subdivisions of a CN-8 with their applicable measures, now including group measures, each measure with its area's name, and leaving out measures that exclude the origin and measures of type 566.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the 2026-10-01 snapshot, the lookup for China returns import control 763 and CBAM 775 for group 1008 on 7318 15 20, and veterinary control 410 for group 1008 under 3926 90 97, each named All third countries.
- **SC-002**: On the 2026-10-01 snapshot, none of the 1,238 erga omnes measures that exclude China is returned for China. A measure that excludes a group containing China is left out, proven by fixture tests only, since the 2026-10-01 snapshot holds no such measure.
- **SC-003**: In the re-run of feature 002's acceptance for the same 20 codes, the group 1008 rows match EZT-online on every code where they appear, no type 566 measure is returned, and every remaining mismatch is listed.
- **SC-004**: On the author's machine, the knowledge base opens at app start at most 2 s later with the snapshot than without it, measured as in T037.
- **SC-005**: The full offline test suite passes without network access or secrets: the 391 existing tests and the tests this feature adds. Existing tests that encode schema 1 or the old lookup rule are updated, never dropped, and the test count before and after is recorded.
- **SC-006**: The author's hand check of at least one live code with a country exclusion affecting China agrees with EZT-online.

### Acceptance findings (2026-10-23)

- **SC-006, hand check passed (task T030)**: for 7307 93 11 91, EZT-online shows China's own 552 at 58.6 % with origin CN and no erga omnes 552; with origin US the erga omnes 552 appears with its Länderausschluss listing CN, KR, MY, RU and TW. CargoLint's lookup returns the same: China's own 552 at 58.6 % for CN, and the erga omnes 552 at 58.6 % for US.

## Assumptions

- "Membership counts" means the number of members of each group on the snapshot date.
- Only EU membership and name records count; Swedish national records in the export are dropped, as in feature 002's EU-only rule. Names are taken in English only, as feature 002 does for code descriptions.
- A measure's excluded areas apply for as long as the measure itself is valid; they carry no dates of their own.
- The figures of 1,512 net group measures and 1,238 wrongly returned erga omnes measures count measures for import or both directions in the 2026-10-01 snapshot. The 1,238 come from feature 002's research R-13, recounted after the full load (T021); the 1,512 are the group measures that apply to China once the 37 that exclude China are left out (research R-04).
- The 10 s figure in the description is feature 002's SC-007, which allows startup with the snapshot to be at most 10 s longer than without it; the constitution sets no startup limit. T037 measured an increase of 4.3 to 4.4 s, and this feature tightens the allowance to 2 s.
- This feature supersedes three parts of feature 002: the last sentence of its FR-018 and the matching known limitation (country groups and exclusions), the acceptance finding on measure type 566, and the known limitation on startup time. Feature 002's other known limitations remain: full temporary stops, unnamed additional-code companies and the Meursing table.
- Design constraints set by the author, carried into planning:
  - The snapshot schema version is bumped, and the loader rewrites the file on the next `--taric` run even with the same extract, with a logged reason.
  - `lookup_taric(cn8, origin)` keeps its signature, and parent-chain inheritance is unchanged.
  - The acceptance aid `tests/eval/taric_acceptance.py` is re-run for the same 20 codes.
  - Tests are written before code, the loader is driven by the six files only, the CN 2026 index stays untouched, and the existing 391 tests keep passing; tests that encode schema 1 or the old lookup rule are updated, never dropped.
- Out of scope: company names behind additional codes (they need the AdditionalCode file); certificate descriptions such as D008 (they need the Certificate file); full temporary stops; Spec 2's agent and UI work; any change to the CN 2026 or EBTI indexes.
