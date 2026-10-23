# Research: CN-8 and TARIC-10 Classification in the Agent and the UI (Phase 0)

All figures come from read-only runs on 2026-10-23 against the built knowledge base:
- `data/nomenclature_2026.jsonl`, CN 2026;
- `store/bti_docs.jsonl`, the full EBTI build with 73,899 valid rulings;
- the schema-2 TARIC snapshot `data/taric.jsonl` of 2026-10-01 (features 002 and 003).

Code references are to the state of `main` at `4574914`.

## R-01 Where the CN-8 choices come from

**Decision**:
- **Source**: the CN-8 lines of a subheading are read from its CN 2026 chunk text, whose lines read `CN dddd dd dd — <path> > <label>`. A new read-only helper `NomenclatureIndex.cn8_lines(hs6)` returns `(cn8, label path)` pairs. The pattern `_CN8_LINE` already parses these lines for feature 002's reconciliation.
- **No loader change**: CN 2026 stays the only source for digits 1 to 8 (feature 002's FR-022).
- **Single CN-8 line**: when a subheading has one CN-8 line, the CN-8 step takes it without a model call (FR-004). It is written by rule at confidence 100, since there is no choice to be wrong about.

**Evidence**: 5,612 HS-6 chunks.
- 3,777 (67 %) have one CN-8 line, always ending in 00.
- 1,009 have 2 lines, 390 have 3, 176 have 4, 84 have 5, and 176 have 6 or more.

So a model judgement is needed for a third of the decided subheadings.

**Alternatives considered**: reading CN-8 lines from the TARIC snapshot. Rejected: TARIC is used only for digits 9 to 10 (constitution, knowledge-base sources).

## R-02 EBTI precedent at eight digits

**Decision**: precedent for the CN-8 choice comes from valid EBTI rulings under the decided HS-6 whose `cn_code[:8]` is one of that subheading's CN-8 lines.
- **Ruling selection**:
  - When the BTI vector collection is loaded (full build), the rulings nearest the line text are chosen with one embedding request per line. The search is restricted to the subheading by the existing `code` metadata, so `ChromaVectorSearch.search_by_vector` gains an optional `where` filter next to its chapter filter.
  - Without vectors (`--demo` build), the newest valid rulings per CN-8 line are used.
  - At most 2 rulings per CN-8 line and 8 in all are sent to the model.
- **New read-only helper**: `BTIStore.by_cn8(hs6, as_of)` groups the valid rulings of a subheading by CN-8.
- **Validity**: expired rulings, and rulings not yet valid, are dropped as for HS-6 precedent (Principle III).
- **What is shown**: the ruling the model cites for the chosen CN-8, with reference, member state, description and validity, and the EBTI link. A citation is accepted only if the ruling was sent to the model in that run (Principle III).

**Evidence**:
- All 73,899 rulings across the 12 target chapters carry a code of 8 digits or more, so every ruling can serve as CN-8 precedent.
- Each BTI vector carries `code` (HS-6) and `cn_code` metadata (`BTIStore.chunk_texts`), so no re-indexing is needed.

**Alternatives considered**:
- **Newest rulings only**: cheaper, but under a large subheading such as 7318.15 the newest rulings rarely resemble the line.
- **A new CN-8-level index**: a loader change, which is out of scope.

## R-03 The CN-8 judgement and its guardrails

**Decision**: `classify_cn8` sends one structured call per line with more than one CN-8 line, through the existing `StructuredCaller`.
- **Inputs**:
  - the fenced line text, including any information the shipper confirmed (`Extracted`);
  - the decided HS-6 and its label;
  - the CN-8 lines with their label paths;
  - the selected rulings, each with its excerpt fenced like data.
- **Output schema `Cn8Out`**:
  - `cn8` (eight digits, or null);
  - `confidence` (0–100);
  - `deciding_attribute` (short text such as "material" or "head type");
  - `attribute_visible` (bool);
  - `evidence` (the words of the line text that decide);
  - `rationale`;
  - `precedent` (a ruling reference or null).
- **Checks in code** (Principle I):
  - the schema is validated, and invalid output is retried once, then the line fails for this step;
  - `cn8` must be one of the subheading's CN-8 lines, or the result is discarded (FR-002);
  - `attribute_visible` false, or no `cn8`, means no CN-8 is decided and the line's CN-8 question becomes "Ask the shipper for: <deciding_attribute>" (FR-003);
  - a cited ruling must be one that was sent.
- **Written or suggested** (clarification Q4): the CN-8 is written when its confidence is at least the shipment's auto-accept threshold. Otherwise it stays a suggestion with the "CN-8 to confirm" marker. Code compares the confidence with the threshold; the prompt does not.
- **Prompt rules**, mirroring `classify_hs6`'s style:
  - choose only from the listed CN-8 lines;
  - judge whether the deciding attribute is stated in the text and never infer it from typical goods;
  - set confidence by the same bands (85–98 when the text states the attribute, 60–84 when it implies it, below 60 when guessing).

**Iteration 2 (2026-10-23, the author's decision after the first evaluation)**: the first run wrote 119 of 120 CN-8
codes by rule, 19 of them wrong, because the model answered 85 almost every time. Three rules now hold in code:
- **Evidence**: it must be words of the line. Every fragment must occur in the line text, ignoring case, quotes and
  spacing. Without such words the attribute counts as not visible, and the step asks the shipper (`evidence_in_line`).
- **Precedent agreement**: a cited ruling whose CN code is at another CN-8 keeps the choice "CN-8 to confirm",
  whatever the confidence or the threshold (`cn8_precedent_conflict`).
- **Bands**: 85 and above needs that evidence and a cited ruling at the chosen CN-8. Anything else is capped at 84
  (`cn8_confidence`). The prompt puts inferred choices at 70-84.

Results of both iterations against the fixed set are in `tests/eval/cn8_eval.md`.

**Alternatives considered**:
- **Choosing the CN-8 inside `classify_hs6`**: changes the HS-6 path, which FR-021 forbids.
- **A rule-based keyword matcher**: CN-8 labels differ by material, dimensions, use and form, so keyword rules miss most of them.

## R-04 Routing with the CN-8 question

**Decision**: the routing function `agent.routing.route_line` gains the input `cn8_question: str | None`, as constitution v1.2.0 Principle I now names, and `cn8_error: str | None`.
- **Failed CN-8 step**: it routes the line to review with the error, as feature 001's failed status does (Principle V). This was the author's decision after `/speckit-analyze` on 2026-10-23.
- **Routing rule**: when it is set on a checked, unflagged line whose HS-6 is decided, the route is `ask_shipper`, with the reason "the CN-8 depends on <attribute>, which the description does not state — ask the shipper". The rest of the routing table is unchanged.
- **Effective route**: `LineStore.effective_route` returns that computed `ask_shipper` while the CN-8 question is open, even over a clerk's HS-6 acceptance, because a later step found information missing. The question closes when:
  - the clerk chooses a CN-8 from the list, or
  - a shipper reply gives a CN-8 the attribute supports.
- **Separating "HS-6 decided" from the route**: today `decided_code()` treats an HS-6 as auto-decided only while the computed route is `auto_accept`. A line routed to ask-shipper for its CN-8 would therefore lose its decided HS-6. A new pure helper, `hs6_auto_decided(...)`, applies the unchanged auto-accept condition to the HS-6 alone: flag OK, confidence at least the threshold, never flagged. `decided_code()` and the CN-8 trigger use it, so the HS-6 decided code and the export's `decided_code` column stay as they were (FR-021).

**Evidence**:
- `route_line` today takes `(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor)` and is the only routing function. `LineStore._recompute` is its only caller.
- `effective_route` prefers a decision's route; `counts()` and the export read `effective_route`.

**Alternatives considered**: a "CN-8 to ask" marker that leaves the route alone. Rejected: the author's description routes the line to ask-shipper, and the constitution was amended for exactly that.

## R-05 When the CN-8 and TARIC steps run

**Decision**:
- **During a check**: the agent calls `classify_cn8`, then `lookup_taric`, after `lookup_precedent`, for lines whose HS-6 is decided. The system prompt's tool order gains steps 6 and 7. The completeness guard (`agent.agent._finalize`) runs whatever the agent skipped, as it already does for the HS-6 steps, marked "run by the app".
- **When the clerk accepts or chooses an HS-6**: the UI starts the same two steps for that line through an agent-level function run as a background job (`ui/jobs.py`), so the click returns at once. The UI never calls the model or retrieval directly (constitution, architecture invariant).
- **Shipper reply**: `apply_shipper_reply` re-runs check, classify and precedent as today. A version created by a reply is never auto-accepted (feature 001), so the CN-8 and TARIC steps run when the clerk accepts its HS-6, for that line only (FR-006, Principle V).
- **Threshold change**:
  - CN-8 codes the clerk has not confirmed are re-evaluated against the new threshold, with no model call. Below it they become suggestions again, and a TARIC-10 written from them is withdrawn.
  - Routes are recomputed as today.
- **Origin change**: only the TARIC step runs again, with no model call (FR-018).

**Rationale**: the CN-8 step's input exists only once the HS-6 is decided (FR-001). Running it in the check for auto-accepted lines keeps the clerk's view complete when the check ends.

## R-06 The TARIC rules as one pure function

**Decision**: a new pure module `agent/taric_rules.py` holds the guardrails of FR-007 to FR-012. It has no model, store or Streamlit import.
- **Constant**: `TRADE_DEFENCE_CONFIRM = {"551", "552", "553", "554", "555", "570"}` (clarification Q3).
- **Function**: `taric_rule(subdivisions, snapshot_loaded) -> rule` returns exactly one rule, from the subdivisions alone:
  - `not_loaded` when no snapshot is loaded;
  - `not_available` when there are no subdivisions;
  - `trade_defence` when any subdivision carries a confirm type for the origin;
  - `auto_completed` when there is exactly one subdivision;
  - `choose` otherwise.
- **Writing**: `code_to_write(rule, subdivisions, cn8_written)` returns the single subdivision only when the rule is `auto_completed` and the CN-8 is written (FR-008, clarification Q4); otherwise it returns none. While the CN-8 waits for confirmation, its "CN-8 to confirm" marker covers the line, and the auto-completion happens when the CN-8 is written.
- **Pending marker**: `choose` and `trade_defence` leave the TARIC-10 unwritten and set the "TARIC-10 to confirm" marker. A clerk confirmation is accepted only for a code among the subdivisions (FR-012).
- **Suggestion among several subdivisions** (FR-009):
  - One structured call `SubdivisionOut` is made only when there are several subdivisions. It receives the fenced line text and the subdivision descriptions, and returns a code, a confidence and whether the separating attribute is stated.
  - A suggestion is highlighted only when the attribute is stated and the code is one of the subdivisions. It is never written.
- **Audit text**: "auto-completed, single TARIC subdivision, snapshot <date>", as FR-008 requires.

**Evidence**:
- `TaricStore.lookup_taric(cn8, origin)` returns the subdivisions and their measures, with export-only and type-566 measures already left out (feature 003).
- The 20 acceptance codes include unsubdivided CN-8s (one subdivision ending 00) and subdivided ones (two to fourteen subdivisions).

## R-07 Measure groups

**Decision**: a fixed table in `agent/taric_rules.py` assigns the 80 import measure types found in the 2026-10-01 snapshot. Any type it does not name goes to requirements (FR-014).

| Group | Types |
|---|---|
| duties | 103, 105, 106, 107, 112, 115, 117, 119, 122, 123, 141, 142, 143, 145, 146, 147 (duties, suspensions, quotas, preferences); 488, 489, 490 (entry-price values); 651, 652, 653, 654, 695, 696 (additional duties) |
| trade defence | 551, 552, 553, 554, 555, 561, 564, 565, 570 |
| requirements | all other types: 109 and 110 (supplementary units), 277 (prohibition), 410 and 415 (veterinary and plant control), 464, 465, 474, 475, 481–484, 495, 496 (declarations and restrictions), 705–770 (import controls), 775 (CBAM) |

**Evidence**: the snapshot holds 80 import measure types once 566 and export-only types are left out. The table covers every type in the duties and trade-defence groups by name; the rest are controls, prohibitions, declarations, units and CBAM.

Re-checked on 2026-10-23 against every measure line of `data/taric.jsonl`:
- **Group sizes**: duties 25 types, trade defence 9, requirements 46.
- **Coverage**: every type the table names occurs in the snapshot.
- **Largest types**: 142 (tariff preference, 72,087 measures), 552 (definitive anti-dumping duty, 18,891) and 103 (third-country duty, 8,848).

## R-08 The two links

**Decision** (clarification of feature 004, Q2):
- **EZT-online**: `https://auskunft.ezt-online.de/ezto/Welcome.do` opens the start page. The 10-digit code and the origin are shown next to it as a copyable code block, since EZT-online has no stable per-code links (feature 002, acceptance aid).
- **EU TARIC consultation**: `https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp?Lang=en&Taric=<code>&Area=<origin>&SimDate=<snapshot date as YYYYMMDD>&LangDescr=en`.

**Evidence (verified 2026-10-23 in a browser)**: the link for 7318155810, CN, 20261001 opens "TARIC measure information" with:
- reference date 01-10-2026 and "Area: China - CN";
- the goods code and its hierarchy;
- measures including anti-dumping, "All third countries" and CBAM.

The measure table is filled by the page's script, so it needs a browser, which the clerk has. `SimDate` pins the view to the snapshot date, so both show the same day.

**Stability evidence (2026-10-23)**:
- **No session**: a request without cookies (`curl`) for the same link returns HTTP 200 with no redirect. The 84 KB page repeats the code 57 times and the date 35 times, and shows "01-10-2026". There is no session id in the URL or in the page's links. The state lives in the query string alone, unlike EZT-online's sessions.
- **The site's own links**: the page's links carry the same parameters, for example `Area=CN&LangDescr=en`.
- **History**: the Wayback Machine holds `measures.jsp` captures from 2011 to 2026. Links with the same parameter names (`Lang`, `Taric`, `Area`, `SimDate`, `LangDescr`) were captured from 2022 to 2026, for example `Lang=en&SimDate=20260105&Area=CN&…&Taric=847150` on 2026-01-05.
- **Limit**: the Commission publishes no guarantee for this format. It is stable in practice, not by contract. If it changes, only `eu_taric_url` changes; the EZT-online start page and the copyable code remain.

## R-09 Data model choices

**Decision**:
- **Author's fields**:
  - `Candidate` gains `cn8` and `taric10`, both optional and pattern-checked (8 and 10 digits). They are the suggestion for the decided HS-6 candidate and are empty on the others.
  - `Decision` gains `decided_cn8` and `decided_taric10`, set only by the clerk's confirmations.
- **Step results** live on the line version:
  - `LineVersion.cn8` holds the CN-8 choice: options, confidence, evidence, question, precedent, and written-by (`rule`, `clerk` or none);
  - `LineVersion.taric` holds the TARIC outcome: origin, snapshot date, rule, subdivision codes, suggestion, and the written code and by whom.
- **Measures are not stored**: they are looked up from the snapshot whenever the line is shown. They therefore always equal the lookup's output (FR-013, SC-004) and cost under 1 ms.
- **Confirming on an auto-accepted line**: there is no `Decision` yet, so the store creates `Decision(route=accepted, decided_code=<the auto HS-6>, chosen_how=auto, decided_cn8=…)`.
  - The HS-6 code and how it was chosen stay as they were.
  - The route reads `accepted`, set by the clerk, instead of `auto_accept`, because the clerk acted on the line.
  - Lines the clerk does not touch keep their export values exactly.
- **Audit**: new change kinds `cn8_written`, `cn8_question`, `taric_written`, `taric_pending` and `taric_not_available`. The note carries the rule text, the snapshot date and the origin (FR-020).

**Alternatives considered**: keeping clerk confirmations outside `Decision`. Rejected: the author's design constraint names `decided_cn8` and `decided_taric10` on `Decision`.

## R-10 Origin per invoice

**Decision**:
- `Shipment` gains `taric_origin: str = "CN"`, validated against `^[A-Z]{2}$` after upper-casing. It is separate from the existing `origin`, which is the route's origin port parsed from the invoice and shown in the review header.
- The sidebar's "Shipment" expander gains a two-character "Origin (TARIC)" field.
- `LineStore.set_taric_origin(code)` refuses anything else with a message. Otherwise it re-runs the TARIC step for every line with a CN-8 and re-applies the rules, with no model call. TARIC-10 codes the clerk confirmed stay (FR-017, FR-018).

**Evidence**: `Shipment.origin` is filled from the parsed file (`tools/parse_packing_list.py`) and rendered as "origin → destination" in `ui/review.py`.

## R-11 Export

**Decision**:
- **CSV**: `CSV_COLUMNS` gains `cn8` and `taric10` at the end, after `note`, so every existing column keeps its position and value. Each is filled only when its code is written (FR-022).
- **JSON**: each line gains `"cn8"` and `"taric10"`, as a code or null.

**Evidence**: `LineStore.CSV_COLUMNS` and `to_json_bytes` (`agent/store.py`); feature 001's `contracts/export.md`.

## R-12 The CN-8 evaluation set (SC-002)

**Decision**: `tests/eval/cn8_eval.py` builds a seeded sample from `store/bti_docs.jsonl` and runs the CN-8 step on it.
- **Twelve target chapters, not ten**: 39, 42, 61, 62, 63, 64, 73, 84, 85, 94, 95 and 96 (`rag/bti.TARGET_CHAPTERS`; the constitution lists "39, 42, 61–64, 73, 84, 85, 94, 95 and 96"). The README's "ten target chapters" has the same mistake.
  - The set keeps 10 rulings from each target chapter: 120 rulings, with the 50 % target at 60 of 120.
  - The author confirmed this on 2026-10-23. The spec's SC-002, Key Entities and Assumptions now say so.
- **Sampling rules**:
  - Only rulings under subheadings with **at least two CN-8 lines**. Two thirds of subheadings have one line and are decided without a model (R-01), so including them would make the 50 % target meaningless.
  - Only rulings whose `cn_code[:8]` is a CN 2026 line under their HS-6.
  - Valid on the evaluation date.
  - English first, then German, then other languages. Chapters 61, 62, 64 and 96 have only 8 English rulings each.
- **Running the evaluation**:
  - Each ruling's goods description is the line text, and its HS-6 is the decided HS-6.
  - Its own reference is excluded from the precedents (leave-one-out).
  - Top-1 is the chosen CN-8, written or suggested. An ask-shipper outcome counts as a miss.
- **Output**: `tests/eval/cn8_eval.json`. It needs `OPENROUTER_API_KEY`, like `run_eval.py`.

## R-13 Time and cost (SC-008)

**Decision**:
- **Calls**: the CN-8 step makes one structured call per decided line with several CN-8 lines, plus one embedding request for the precedent search. The subdivision suggestion makes one small call per CN-8 with several subdivisions. All run through `run_per_line`, which is concurrent and isolated per line.
- **Measuring**: the existing live budget test (`tests/live/test_cost_budget.py`, 12 lines plus two follow-up questions under €0.10) and the scale check (100 lines within 5 minutes) are re-run with the steps included.

**Evidence**: today's 12-line sample check took 23 s and cost €0.008 (feature 003, T032). Eight of its twelve lines were auto-accepted. At most eight CN-8 calls and a few subdivision calls are added, which costs about €0.001–0.003 and a few seconds when run in parallel. That is far inside 60 s and €0.10.

## R-14 UI

**Decision**: native Streamlit only (Principle VI). The files `ui/chat.py`, `ui/detail.py`, `ui/review.py` and `ui/upload.py` are CRLF and keep their line endings.
- **Detail card** (`ui/detail.py`): a "CN-8 and TARIC-10" section under the route control.
  - **CN-8**: the code with its label path, a confidence bar, the evidence and the ruling (popover). Its state is one of:
    - written (by rule or by you);
    - "CN-8 to confirm", with a radio of the CN-8 lines and Confirm;
    - the open question "Ask the shipper for: <attribute>", with the same radio for choosing anyway.
  - **TARIC**:
    - a caption "TARIC snapshot <date> · origin <code>" and the rule that applied;
    - one expander per subdivision, with its description, a suggestion badge with confidence, a trade-defence badge, and the three measure groups as tables;
    - Confirm, or "Ask the shipper";
    - the two links, with the code in a copyable block.
- **Counts** (`ui/chat.py _render_counts`): "CN-8 to confirm" and "TARIC-10 to confirm" are shown as metrics after the three routing metrics, labelled as confirmations.
- **Review rows** (`ui/review.py`): a small badge for each marker in the row's route cell. The columns are unchanged.
- **Sidebar**: "Origin (TARIC)" in the Shipment expander, whose fields `ui/upload.py` renders (`render_shipment_fields`).
- **Parity (SC-004)**: a pure view-model function `taric_view(subdivisions, …)` builds what the card shows from the lookup output.
  - Unit tests on the fixture snapshot prove it neither adds, drops nor alters a measure.
  - `tests/eval/taric_ui_parity.py` checks the 20 acceptance codes against the real snapshot.

## R-15 Test strategy (Principle VII)

**Decision**: tests first, offline, for every guardrail:
- `route_line` with `cn8_question`, and `hs6_auto_decided`;
- `taric_rule` for the four rules and "TARIC not loaded", including a single subdivision with type 555 or 570, and a CN-8 not yet written;
- the measure-group table, including an unknown type going to requirements;
- validation that a CN-8 is among the subheading's lines and a TARIC-10 among the subdivisions;
- the threshold write rule and its re-evaluation;
- the store transitions: confirmations, the question closing, origin change, audit entries, and effective route precedence;
- the export columns;
- the two tools with the fake model client.

Recorded outputs for `Cn8Out` and `SubdivisionOut` are added to `tests/fixtures/recorded/` and to `FakeRawClient.default_for`. TARIC cases use feature 003's `tests/fixtures/taric/snapshot_small.jsonl`, extended where needed. The 432 existing tests stay green, and tests that encode the old behaviour are updated, never dropped.

## R-16 Real-data examples of each rule, and one that has none

**Decision**: the quickstart demonstrates the rules with these CN-8 codes for origin CN on the 2026-10-01 snapshot. The
not-available rule is proven with fixtures only.

| Rule | CN-8 (subdivisions) |
|---|---|
| auto_completed | 7318 15 20 (00); 9503 00 75 (00); 9405 21 40 (00) |
| choose | 3926 90 97 (14); 9503 00 95 (3); 8518 30 00 (2) |
| trade_defence | 7318 15 58 (3, all with trade defence; for origin US the rule becomes choose); 8714 91 10 (9, three with trade defence) |
| not_available | none |

**Evidence**:
- All 9,791 CN-8 lines of CN 2026 have at least one TARIC subdivision for China on 2026-10-01.
- Feature 002's 105 CN-8 mismatches run the other way: they are CN-8 prefixes in TARIC that CN 2026 lacks (`rag/taric_extract.py`, `mismatches`). The CN-8 step chooses only CN 2026 lines, so it can never choose one of them.
- **Spec wording**: the edge case "CN-8 that TARIC lacks (one of the CN-8 mismatches of feature 002)" cannot occur on this snapshot. The rule stays, for later snapshots, and is tested with fixtures, as feature 003 did for group exclusions. At the author's request (2026-10-23), the spec now states it as a rule proven by fixture tests only.

## R-17 Effect on the bundled sample

**Decision** (accepted by the author on 2026-10-23): the sample's text stays unchanged, and 6 of its 12 lines need
action. Four things change with it:
- the expected routes in `data/samples/sample_lines.json`;
- the quick-action hint;
- the offline flow test that pins the sample's counts (`tests/integration/test_upload_flow.py`);
- the constitution's Screen 1 text, amended to v1.2.1.

Feature 001's FR-005 ("12 lines, 5 needing action") stays as that feature's record.

**Evidence**: the sample's seven expected auto-accepts, with their CN-8 lines in CN 2026:
- **One CN-8 line, written by rule**: 9617.00, 6109.10, 4016.93 and 8518.30.
- **Attribute stated**: 8714.91 (frames, front forks, parts) and 3926.90 (drain buckets, face shields, other).
- **"Plastic toy cars"**: 9503.00 has 19 CN-8 lines. "Incorporating a motor" separates 9503 00 75 from 9503 00 95, and the text does not say. The line will probably route to ask the shipper, which would make 6 of 12 lines need action instead of 5.

That count appears in two places:
- the quick action's hint "12 Yiwu consolidation lines, 5 problematic" (`ui/chat.py`);
- the constitution's Screen 1 contract, "12 lines with 5 needing action".

Three TARIC-10 markers are also expected, and they do not change routes:
- 8518 30 00: choose;
- 8714 91 10: trade defence;
- 3926 90 97: choose.
