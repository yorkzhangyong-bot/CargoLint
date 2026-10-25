# Feature Specification: CN-8 and TARIC-10 Classification in the Agent and the UI

**Feature Branch**: `004-cn8-taric-classification`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "Extend classification from HS-6 to CN-8 and TARIC-10 in the agent and the UI, using the TARIC snapshot loaded by features 002 and 003. A new tool classify_cn8 takes the decided HS-6 and chooses a CN-8 from the CN 2026 lines under that heading, using EBTI rulings with a cn_code as precedent and the line text as evidence; when the attribute that decides between CN-8 lines is not visible in the line text, the line routes to ask-shipper with a question naming that attribute. The agent then calls the existing lookup_taric(cn8, origin) from rag/taric.py with origin CN by default and the origin editable per invoice in the UI. Rules for the subdivisions it returns: if exactly one subdivision exists, auto-complete it and record “auto-completed, single TARIC subdivision, snapshot <date>“ in the audit trail; if several exist, show all of them with description and measures, the system may rank them and highlight one suggestion with a confidence score when the distinguishing attribute is visible in the line text, but the clerk must confirm or send a question to the shipper, and no subdivision is written without confirmation; if none exist, stop at 8 digits and show “TARIC not available” without guessing “00”. Any subdivision whose measures include an anti-dumping or countervailing measure (types 551, 552, 553, 554) always requires clerk confirmation, even when it is the only subdivision. Measures are shown as returned by lookup_taric, grouped for the clerk into duties (third-country duty and preferences), trade defence (anti-dumping and countervailing with their additional codes and the duty text, including conditional text such as “39.6 % with document D008; otherwise 86.5 %”), and requirements (controls, CBAM, licences), each with the measure type label, the geographical area code and name, and the regulation reference; the snapshot date and a link to EZT-online for the chosen 10-digit code are shown with them. Candidate gains cn8 and taric10, Decision gains decided_cn8 and decided_taric10, and the audit trail records which rule applied. CODE_PATTERN and the HS-6 path are unchanged, so existing HS-6 results and exports are not affected; the export gains CN-8 and, when confirmed, TARIC-10 columns. Out of scope: company names behind additional codes, certificate descriptions, duty calculation, the German national layer, origin rules for preferences, and any change to the loaders. Acceptance: HS-6 results unchanged on the locked test set; CN-8 top-1 at least 50 % on the EBTI-based CN-8 evaluation set; the auto-complete, multi-choice-with-suggestion, not-available and trade-defence-confirmation rules each covered by a test; for the 20 acceptance codes of feature 002, the subdivisions and measures shown in the UI equal lookup_taric’s output."

## Clarifications

### Session 2026-10-23

- Q: Does a pending TARIC-10 confirmation make the line "needs action"? → A: No. The line keeps its HS-6 route; a separate "TARIC-10 to confirm" marker and a count show the pending confirmations.
- Q: Which link should be shown for checking the code, given that EZT-online has no stable per-code links? → A: Both: EZT-online's start page with the 10-digit code and the origin shown next to it for copying, and a direct link to the EU TARIC consultation page for the code and origin.
- Q: Which trade-defence measure types require the clerk's confirmation? → A: 551, 552, 553, 554, 555 and 570: every type under which a trade-defence duty can be collected or must be controlled. 561, 564 and 565 are shown in the trade-defence group but do not force confirmation.
- Q: When the CN-8 step chooses a CN-8, is it written to the line automatically, or does it wait for the clerk? → A: It is written automatically only when its confidence meets the auto-accept threshold (85 % by default); superseded by constitution 1.4.0 (feature 006), under which the CN-8 gate is the vote of the nearest EBTI rulings (FR-001). Below that it stays a suggestion with a "CN-8 to confirm" marker, the line keeps its HS-6 route, and its TARIC-10 can only be written once the CN-8 is.
- Q: With the CN-8 step included, must a check still meet feature 001's time and cost limits? → A: Yes. Feature 001's limits stay unchanged, measured with the CN-8 step included: a 12-line list in under 60 s, a 100-line list within 5 minutes, and under €0.10 for 12 lines plus two follow-up questions.
- Q: How many EBTI rulings should the CN-8 evaluation set hold? → A: 100 rulings, 10 from each of the ten target chapters. Corrected in planning (2026-10-23): the target chapters are twelve, so the set holds 120 rulings, 10 from each, drawn only from subheadings with at least two CN-8 lines, with a target of 60.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose the CN-8 under the decided HS-6 (Priority: P1)

Today the clerk gets a decided HS-6 subheading for each line and nothing finer. With this story, as soon as a line's HS-6 is decided, the assistant chooses one of the CN 2026 eight-digit lines under that subheading. It uses EBTI rulings at eight digits or more as precedent and the line text as evidence. It shows the chosen CN-8 with a confidence, the words in the line text that decided it, and the ruling behind it. When the line text does not show the attribute that separates the CN-8 lines, such as material, alloy or use, the assistant does not guess. It routes the line to ask the shipper, naming that attribute.

**Why this priority**: every later step depends on the CN-8. The TARIC subdivisions, the measures and the export columns are all looked up from it.

**Independent Test**: Decide the HS-6 of lines whose text does or does not show the separating attribute, and check the chosen CN-8, its evidence and precedent, or the ask-shipper route with the named attribute.

**Acceptance Scenarios**:

1. **Given** a line whose HS-6 is decided and whose text shows the attribute that separates the CN-8 lines under it, **When** the CN-8 step runs, **Then** one CN-8 under that HS-6 is chosen and shown with its confidence (0–100), the evidence from the line text, and the ruling cited as precedent (reference, description and validity), or "no ruling". It is written to the line when the CN-8 gate agrees (since constitution 1.4.0, feature 006: the evidence check passed, no cited ruling sits at another CN-8, and the CN-8 is the majority of the five nearest eligible EBTI rulings, each counted once, with a share of at least 0.5; with no eligible ruling, its confidence against the auto-accept threshold).
2. **Given** a line whose text does not show that attribute, **When** the CN-8 step runs, **Then** no CN-8 is decided and the line routes to ask the shipper with a question naming the missing attribute.
3. **Given** a decided HS-6 with a single CN-8 line in CN 2026, **When** the CN-8 step runs, **Then** that CN-8 is taken without a model judgement.
4. **Given** a line whose HS-6 is not decided, for example a flagged line or one in review, **When** the check runs, **Then** no CN-8 step runs for it until its HS-6 is decided.
5. **Given** a line with a CN-8, **When** the clerk decides a different HS-6, **Then** the CN-8 step runs again for that line only, and the earlier CN-8 and TARIC-10 no longer apply to the new version.
6. **Given** any outcome of the CN-8 step, **When** a CN-8 is shown, **Then** it exists in CN 2026 under the decided HS-6; any other code is discarded and never shown.
7. **Given** a chosen CN-8 that the CN-8 gate does not accept (the nearest rulings disagree, or, with no eligible ruling, its confidence is below the auto-accept threshold), **When** the CN-8 step ends, **Then** it stays a suggestion with a "CN-8 to confirm" marker, the line keeps its HS-6 route, and no TARIC-10 is written. **When** the clerk confirms the CN-8, **Then** it is written, and the TARIC rules apply to it.

---

### User Story 2 - Complete the TARIC-10 by fixed rules (Priority: P1)

For the chosen CN-8, the assistant looks up the TARIC subdivisions for the invoice's origin, China by default, in the loaded TARIC snapshot. It applies one of four rules, never a model's judgement alone:

| Rule | When | What happens |
|---|---|---|
| Auto-complete | exactly one subdivision | the subdivision is written without a click |
| Choose | several subdivisions | the clerk confirms one, possibly helped by a suggestion |
| Not available | no subdivision | the line stays at 8 digits |
| Trade defence | any subdivision with a trade-defence duty that can be collected or must be controlled (types 551 to 555 and 570) | the clerk must confirm, even when it is the only subdivision |

The audit trail records which rule applied.

**Why this priority**: the tenth digit decides which measures apply, including anti-dumping duties of up to 86.5 % on Chinese fasteners. A wrong silent choice costs the importer money and the forwarder its credibility.

**Independent Test**: Run the TARIC step on CN-8 codes with one subdivision, several subdivisions, none, and a single subdivision carrying anti-dumping measures, and check what is written, what waits for confirmation and what the audit trail says.

**Acceptance Scenarios**:

1. **Given** a written CN-8 with exactly one TARIC subdivision and no measure of type 551, 552, 553, 554, 555 or 570 for the origin, **When** the TARIC step runs, **Then** that subdivision is written as the line's TARIC-10, and the audit trail records "auto-completed, single TARIC subdivision, snapshot <date>".
2. **Given** a CN-8 with several subdivisions, **When** the TARIC step runs, **Then** all of them are shown with their descriptions and measures, and no TARIC-10 is written. When the line text shows the attribute that separates them, one may be highlighted as a suggestion with a confidence score.
3. **Given** several subdivisions are shown, **When** the clerk confirms one, **Then** it is written as the TARIC-10 and the audit trail records the clerk's confirmation. **When** the clerk instead chooses to ask the shipper, **Then** the line routes to ask the shipper with what to ask, and no TARIC-10 is written.
4. **Given** a CN-8 for which TARIC has no subdivision on the snapshot date, **When** the TARIC step runs, **Then** the line stops at 8 digits and shows "TARIC not available"; no code ending in 00 is guessed.
5. **Given** a CN-8 whose only subdivision carries a measure of type 551, 552, 553, 554, 555 or 570 for the origin, **When** the TARIC step runs, **Then** nothing is written until the clerk confirms it, and the audit trail records that the trade-defence rule applied.
6. **Given** a TARIC-10 confirmation is pending for a line, **When** the review table is shown, **Then** the line keeps its HS-6 route and shows a "TARIC-10 to confirm" marker. The number of lines waiting for a TARIC-10 confirmation is shown next to the routing counts, as a count of confirmations, not as a route.

---

### User Story 3 - See the measures, grouped for the clerk (Priority: P1)

For each subdivision the assistant shows the measures exactly as the snapshot returns them for the origin. They are grouped into three groups:
- duties: the third-country duty, suspensions, quotas and preferences;
- trade defence: anti-dumping and countervailing measures with their additional codes and duty text, including conditional text such as "39.6 % with document D008; otherwise 86.5 %";
- requirements: controls, CBAM, licences and other obligations.

Each measure shows its type label, its geographical area code and name, and its regulation reference. The snapshot date and two links for checking the code are shown with them: EZT-online's start page and the EU TARIC consultation page.

**Why this priority**: the clerk confirms a subdivision because of its measures; without them the confirmation rules of User Story 2 cannot be followed.

**Independent Test**: For the 20 acceptance codes of feature 002, compare what the screen shows for each subdivision with the snapshot lookup for the same CN-8 and origin.

**Acceptance Scenarios**:

1. **Given** the 2026-10-01 snapshot and origin China, **When** 7318 15 58 10 is shown, **Then** the trade-defence group lists each anti-dumping measure with its additional code and duty text, including "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %", and the requirements group lists import control 763 and CBAM 775 for 1008, All third countries.
2. **Given** any of the 20 acceptance codes of feature 002, **When** its subdivisions are shown, **Then** the subdivisions and measures equal the snapshot lookup's output for that CN-8 and origin. No measure is added, dropped or altered; each appears in exactly one group.
3. **Given** a shown subdivision, **When** the clerk looks at its measures, **Then** the snapshot date is shown with them, and two links. One opens EZT-online's start page, with the 10-digit code and the origin shown next to it for copying, since EZT-online works in sessions and has no stable per-code links. The other opens the EU TARIC consultation page directly for the code and origin.
4. **Given** a conditional duty, **When** it is shown, **Then** it appears as text and is never evaluated; the clerk decides which rate applies.

---

### User Story 4 - Set the origin per invoice (Priority: P2)

The TARIC origin, the country the goods come from, is China by default and can be changed for each invoice in the UI. Changing it looks up the TARIC subdivisions and measures again for every line that has a CN-8, without any model call, and applies the rules of User Story 2 again.

**Why this priority**: most shipments come from China, but measures differ by origin. Anti-dumping duties in particular apply only to the named origins.

**Independent Test**: Check an invoice with origin China, change the origin to another country, and compare the measures and the confirmation rules before and after.

**Acceptance Scenarios**:

1. **Given** a new invoice, **When** it is checked, **Then** the TARIC origin is China.
2. **Given** a checked invoice, **When** the clerk changes the origin, **Then** every line with a CN-8 shows the subdivisions and measures for the new origin.
3. **Given** a TARIC-10 that was auto-completed, **When** the new origin brings an anti-dumping or countervailing measure to it, **Then** it waits for the clerk's confirmation again. A TARIC-10 the clerk already confirmed stays confirmed.
4. **Given** an origin that is not a two-letter country code, **When** the clerk enters it, **Then** it is refused with a clear message, and the previous origin stays.

---

### User Story 5 - Export and audit the finer codes without touching HS-6 (Priority: P2)

The export gains a CN-8 column and a TARIC-10 column. Each is filled only once the code is written. The CN-8 is written by the CN-8 gate (since constitution 1.4.0 the ruling vote) or the clerk's confirmation, and the TARIC-10 by auto-completion or the clerk's confirmation. The HS-6 results, columns and routing stay as they are. The audit trail records each CN-8 and TARIC-10 outcome with the rule that applied and who acted.

**Why this priority**: the export is how the clerk's work leaves the app. Keeping HS-6 unchanged protects the ICS2 filing data that the MVP was built for.

**Independent Test**: Export a checked invoice before and after this feature and compare the HS-6 columns; check the new columns and the audit entries.

**Acceptance Scenarios**:

1. **Given** a checked invoice, **When** it is exported to CSV or JSON, **Then** the existing columns and values are unchanged, and a CN-8 and a TARIC-10 column are added. The one exception is the route, and who set it, of a line re-routed by FR-003, by a failed CN-8 step or by a clerk action.
2. **Given** a line whose CN-8 or TARIC-10 waits for confirmation, or whose TARIC-10 is not available, **When** it is exported, **Then** the column of each code not yet written is empty.
3. **Given** any CN-8 or TARIC-10 outcome, **When** the audit trail is read, **Then** it shows the time, the line and version, the rule that applied, the snapshot date and the origin. The rules are: CN-8 written by the CN-8 gate (the ruling vote, or the threshold rule when no eligible ruling exists), auto-completed, confirmed by the clerk, sent to ask the shipper, not available, and trade-defence confirmation.

---

### Edge Cases

- **Decided HS-6 with a single CN-8 line** (CN-8 ending in 00): taken without a model judgement (User Story 1, scenario 3).
- **CN-8 without a TARIC subdivision**: "TARIC not available"; the line stops at 8 digits (FR-010). On the 2026-10-01 snapshot every CN-8 line of CN 2026 has at least one subdivision, so this rule is proven by fixture tests only. Feature 002's 105 CN-8 mismatches are TARIC codes that CN 2026 lacks, which the CN-8 step never chooses.
- **No TARIC snapshot loaded**: the CN-8 step still runs from CN 2026; the TARIC step shows "TARIC not loaded" and the line stops at 8 digits.
- **CN-8 step failure** (invalid model output after one retry, or an API error): the line routes to review with the error shown, as a failed check does (constitution Principle V). The clerk can still choose the CN-8.
- **TARIC suggestion failure** (invalid model output after one retry, an API error or a timeout): the rule and the subdivisions are unchanged, the suggestion is shown as unavailable with the error, nothing is written, and the route is unchanged.
- **Trade defence recorded at the CN-8 level or above**: it applies to every subdivision beneath, so each of them needs confirmation.
- **Shipper reply**: re-runs the CN-8 and TARIC steps for that line only, after its HS-6 is decided again.
- **HS-6 changed by the clerk after a TARIC-10 was written**: the new version starts without a CN-8 and TARIC-10; the CN-8 step runs again.
- **Origin changed after confirmations**: confirmed TARIC-10 codes stay, since subdivision codes do not depend on origin. Auto-completed ones are re-evaluated, and the measures shown change.
- **Auto-accept threshold changed in the sidebar**: CN-8 codes the clerk has not confirmed are re-evaluated against the CN-8 gate, just as routes are; since constitution 1.4.0 the threshold only affects a CN-8 without an eligible ruling, whose gate falls back to its confidence. A CN-8 that falls below it becomes a suggestion again, together with any TARIC-10 auto-completed from it. Confirming a TARIC-10 also confirms the CN-8 it sits under, recorded as two audit entries (the CN-8, then the TARIC-10), so a threshold change never touches a CN-8 the clerk confirmed, directly or with its TARIC-10.
- **Origin unknown to TARIC** (a valid two-letter code that belongs to no group): only its own measures and erga omnes measures apply, as feature 003 defines.
- **EBTI ruling coded to fewer than 8 digits**: not a CN-8 precedent.
- **Expired EBTI ruling**: filtered out, as for HS-6 precedent (constitution Principle III).
- **Preference measure for a group containing the origin**: shown like any measure; whether the goods qualify is not judged (origin rules are out of scope).

## Requirements *(mandatory)*

### Functional Requirements

#### CN-8

- **FR-001**: When a line's HS-6 is decided, the system MUST choose a CN-8 from the CN 2026 eight-digit lines under that HS-6. EBTI rulings coded to eight digits or more under that HS-6 serve as precedent, and the line text as evidence. An HS-6 is decided when the routing rule auto-accepts the line, or when the clerk accepts or chooses an HS-6.
  - The chosen CN-8 MUST be written to the line only when the CN-8 gate agrees (since constitution 1.4.0, feature 006: the evidence check passed, no cited ruling sits at another CN-8, and the CN-8 is the majority of the five nearest eligible EBTI rulings, each counted once, with a share of at least 0.5; with no eligible ruling, its confidence against the auto-accept threshold), a rule enforced in code, or when the clerk confirms it.
  - Until then it stays a suggestion with a "CN-8 to confirm" marker, the line keeps its HS-6 route, and no TARIC-10 is written.
  - The number of lines waiting for a CN-8 confirmation MUST be shown next to the routing counts, like the TARIC-10 count (FR-009), as confirmations, not as routes.
- **FR-002**: Every CN-8 shown or written MUST exist in CN 2026 under the decided HS-6; any other code MUST be discarded and never shown.
- **FR-003**: When the attribute that decides between the CN-8 lines is not visible in the line text, the system MUST NOT decide a CN-8. It MUST route the line to ask the shipper with a question naming that attribute. This input MUST become part of the one deterministic routing function (constitution Principle I).
- **FR-004**: When the decided HS-6 has a single CN-8 line, the system MUST take that CN-8 without a model judgement.
- **FR-005**: A chosen CN-8 MUST be shown with:
  - its confidence (0–100);
  - the evidence from the line text;
  - the ruling cited as precedent, with its reference, description and validity, or "no ruling".

  Expired rulings MUST be filtered out (Principle III).
- **FR-006**: When the clerk decides a different HS-6, or a shipper reply updates the line, the CN-8 step and the TARIC step MUST run again for that line only.

#### TARIC-10

- **FR-007**: For a chosen CN-8, the system MUST look up its TARIC subdivisions and measures in the loaded snapshot for the invoice's origin. It MUST apply exactly one of the rules FR-008 to FR-011, decided in code, and record which one in the audit trail.
- **FR-008**: Exactly one subdivision, no measure of type 551, 552, 553, 554, 555 or 570 for the origin, and a written CN-8: the system MUST write it as the TARIC-10 without confirmation. The audit trail MUST record "auto-completed, single TARIC subdivision, snapshot <date>".
- **FR-009**: Several subdivisions: the system MUST show all of them with their descriptions and measures.
  - It MAY rank them and highlight one suggestion with a confidence score (0–100), but only when the attribute that separates them is visible in the line text.
  - It MUST NOT write a TARIC-10 until the clerk confirms one.
  - The clerk MAY instead route the line to ask the shipper, naming what to ask.
  - While no TARIC-10 is written, the line MUST keep its HS-6 route and show a "TARIC-10 to confirm" marker. The number of lines with that marker MUST be shown next to the routing counts, as a count of confirmations, not as a route.
- **FR-010**: No subdivision: the system MUST stop at 8 digits and show "TARIC not available". When no snapshot is loaded, it MUST show "TARIC not loaded". It MUST NOT guess a code ending in 00.
- **FR-011**: Any subdivision whose measures include type 551, 552, 553, 554, 555 or 570 MUST require the clerk's confirmation, even when it is the only subdivision. These are the types under which a trade-defence duty can be collected or must be controlled. Until the clerk confirms, the line keeps its HS-6 route and shows the "TARIC-10 to confirm" marker (FR-009). Types 561, 564 and 565 are shown with the other trade-defence measures but do not by themselves require confirmation.
- **FR-012**: A TARIC-10 MUST only ever be written if it is one of the subdivisions the snapshot returns for the chosen CN-8.

#### Measures shown

- **FR-013**: Measures MUST be shown exactly as the snapshot lookup returns them for the subdivision and origin: none added, dropped or altered.
- **FR-014**: Each measure MUST appear in exactly one group. Duties covers the third-country duty, suspensions, quotas and preferences. Trade defence covers the anti-dumping and countervailing types 551 to 555, 561, 564, 565 and 570. Requirements covers controls, CBAM, licences and every other type.
- **FR-015**: Each measure MUST show:
  - its type label;
  - its geographical area code and name;
  - its regulation reference;
  - for trade defence, its additional code and duty text.

  Conditional duty text MUST be shown as text and never evaluated.
- **FR-016**: The snapshot date MUST be shown with the measures, together with two links for the chosen 10-digit code:
  - EZT-online's start page, with the code and the origin shown next to it for copying;
  - the EU TARIC consultation page for the code and origin.

#### Origin

- **FR-017**: Each invoice MUST have a TARIC origin: the goods' country of origin as a two-letter code, China (CN) by default, editable by the clerk in the UI. Anything else MUST be refused with a message, keeping the previous origin.
- **FR-018**: Changing the origin MUST look up the subdivisions and measures again for every line with a CN-8, without any model call, and apply FR-008 to FR-011 again. TARIC-10 codes already confirmed by the clerk stay.

#### Records, export and the HS-6 path

- **FR-019**: Each line version MUST keep its suggested and decided CN-8 and TARIC-10 next to its HS-6.
- **FR-020**: The audit trail MUST record every CN-8 and TARIC-10 outcome with:
  - the time, the line and version;
  - the rule that applied, and the actor (the rule or the clerk);
  - the snapshot date and the origin.
- **FR-021**: The HS-6 path MUST stay unchanged: candidates, confidence, flags, HS-6 routing, the HS-6 code format, results and existing export columns. The one exception is the route, and who set it, of a line re-routed by FR-003, by a failed CN-8 step or by a clerk action.
- **FR-022**: The CSV and JSON exports MUST gain a CN-8 and a TARIC-10 column, each filled only when its code is written. The CN-8 is written by the CN-8 gate or the clerk's confirmation, and the TARIC-10 by auto-completion or the clerk's confirmation.
- **FR-023**: Nothing MUST be sent to a shipper or a customs system. "Asking the shipper" means routing the line to ask-shipper with the question for the clerk (constitution, out of scope).

### Key Entities

- **CN-8 Choice**: for one line version, the chosen CN-8 with its confidence, evidence and EBTI precedent, and whether it is written or awaiting the clerk's confirmation. When the separating attribute is not visible, it instead holds the attribute to ask the shipper about.
- **TARIC Outcome**: for one line version and origin:
  - the rule that applied (auto-completed, choose among several, trade-defence confirmation, not available, not loaded), and whether a confirmation is pending;
  - the subdivisions with their grouped measures;
  - the optional suggestion with its confidence;
  - the written TARIC-10, if any;
  - the snapshot date.
- **Invoice Origin**: the goods' country of origin for TARIC, per invoice, CN by default. It is distinct from the shipping route's origin port shown in the review header.
- **Measure Group**: duties, trade defence or requirements; each measure belongs to exactly one.
- **Candidate and Decision**: they gain a suggested CN-8 and TARIC-10, and the decided CN-8 and TARIC-10, next to the unchanged HS-6 fields.
- **Audit Record**: gains the rule applied for CN-8 and TARIC-10 outcomes, the snapshot date and the origin.
- **CN-8 Evaluation Set**: 120 lines with a known CN-8 taken from EBTI rulings, 10 from each of the 12 target chapters, all under subheadings with at least two CN-8 lines, used to measure the CN-8 choice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the 20-line labelled set, HS-6 results are unchanged against the last recorded run (2026-10-16, hybrid):
  - all 20 flags correct;
  - no flagged line auto-accepted;
  - HS-6 top-1 at least 10 of 12;
  - top-3 12 of 12.
- **SC-002**: On the EBTI-based CN-8 evaluation set (120 rulings, 10 from each of the 12 target chapters, all under subheadings with at least two CN-8 lines), the chosen CN-8 equals the ruling's CN-8 for at least 60 of the 120.
- **SC-003**: The auto-complete, choose-with-suggestion, not-available and trade-defence-confirmation rules are each covered by an automated test that passes offline.
- **SC-004**: For the 20 acceptance codes of feature 002, the subdivisions and measures shown equal the snapshot lookup's output for the same CN-8 and origin: 20 of 20.
- **SC-005**: Across the tests and the bundled sample, nothing is written without the clerk's confirmation where a rule requires it:
  - zero TARIC-10 codes when several subdivisions exist, a measure of type 551 to 555 or 570 applies, or the CN-8 is not yet written;
  - zero CN-8 codes written by rule that the CN-8 gate does not accept (since constitution 1.4.0, feature 006).
- **SC-006**: Zero CN-8 or TARIC-10 codes are shown that do not exist in CN 2026 under the decided HS-6, or among the snapshot's subdivisions for that CN-8.
- **SC-007**: The full offline test suite passes without network access or secrets: the 432 existing tests and the tests this feature adds.
- **SC-008**: Feature 001's time and cost limits still hold with the CN-8 step included (its SC-005 and SC-010):
  - a 12-line list is checked end to end in under 60 seconds;
  - a 100-line list is checked within 5 minutes;
  - checking a 12-line shipment plus two follow-up questions costs under €0.10.

## Assumptions

- **The locked test set** is the 20-line hand-labelled set (constitution Principle VII). "Unchanged" means its flag results and HS-6 hits are at least those of the last recorded run (SC-001). The offline tests with recorded model outputs for the HS-6 path pass as they are.
- **The EBTI-based CN-8 evaluation set**:
  - It is drawn from valid EBTI rulings in the 12 target chapters (39, 42, 61 to 64, 73, 84, 85, 94, 95 and 96) whose code has at least 8 digits, and fixed before any tuning.
  - Only rulings under subheadings with at least two CN-8 lines are drawn, since a single CN-8 line is taken without a judgement (FR-004).
  - Each ruling's goods description is the line text, and its HS-6 is given as the decided HS-6.
  - Its own ruling is never available as precedent when it is classified.
  - It holds 120 rulings, 10 from each of the 12 target chapters.
- **When the CN-8 step runs**: during the check for auto-accepted lines, and right after the clerk accepts or chooses an HS-6 for the others.
- **The TARIC origin** is the goods' country of origin as used by TARIC (a two-letter geographical area id). An invoice is one shipment in the MVP, so the origin is set per shipment.
- **Measure types are assigned to the three groups** by a fixed table settled in planning. A type the table does not name appears under requirements, so no measure is ever hidden.
- **Where codes are shown**: the review table keeps its columns. The CN-8, TARIC-10, subdivisions and measures are shown in the selected line's detail. The "TARIC-10 to confirm" marker shows on the line's row. The UI stays native Streamlit (Principle VI).
- **The "Needs action" filter stays route-based** (constitution UI contract). Lines that wait only for a TARIC-10 confirmation are found by their marker and count, not by the filter.
- **The EU TARIC consultation link**: planning verifies that the page offers a stable link for a code and origin.
- **The bundled sample**: with the CN-8 step, "Plastic toy cars" routes to ask the shipper, because whether a motor is fitted decides its CN-8 and the text does not say.
  - So 6 of the sample's 12 lines need action, instead of the 5 of feature 001's FR-005.
  - The quick-action hint and the sample's expected routes are updated.
  - The constitution's Screen 1 text says 6 since v1.2.1.
- **Constitution v1.2.1 (amended 2026-10-23) covers this feature**:
  - Principle I requires every CN-8 shown to exist in CN 2026, and every TARIC-10 and every measure shown to exist in the loaded TARIC snapshot, with the snapshot date displayed.
  - Principle I allows no subdivision to be written without the clerk's confirmation, except a single subdivision auto-completed with an audit entry. This spec is stricter: trade-defence measures always need confirmation (FR-011).
  - Principle I's schema rule names the code format for each level: HS-6 unchanged, CN-8 eight digits, TARIC-10 ten digits.
  - Principle I's routing function takes the line's flag, its confidence against the threshold, and whether the attribute that decides its CN-8 is missing from the line text (FR-003). Since constitution 1.4.0 the threshold governs the HS-6 only, and the CN-8 gate is the ruling vote (feature 006).
  - The architecture lists seven tools, including `classify_cn8` and `lookup_taric`.
  - Screen 1 describes the bundled sample as 12 lines with 6 needing action (v1.2.1).
- **Design constraints set by the author, carried into planning**:
  - a new tool `classify_cn8`;
  - the existing `lookup_taric(cn8, origin)` reused unchanged, with origin CN by default;
  - `Candidate` gains `cn8` and `taric10`, and `Decision` gains `decided_cn8` and `decided_taric10`;
  - `CODE_PATTERN` and the HS-6 path unchanged;
  - no change to the loaders.
- **Out of scope**:
  - company names behind additional codes;
  - certificate descriptions;
  - duty calculation;
  - the German national layer;
  - origin rules for preferences;
  - any change to the loaders.
