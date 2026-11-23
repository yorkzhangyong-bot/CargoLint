# Feature Specification: Chinese Examples for the Vagueness Check

**Feature Branch**: `017-coolant-vague-chinese-examples`

**Created**: 2026-11-23

**Status**: Draft

**Input**: User description: "Backlog item 17 – Chinese descriptions falsely flagged as vague. Problem: A complete
Chinese line such as "金属加工冷却液，不含矿物基础油" gets the right code (3403.99) but is routed to "ask shipper". The flag
comes from the model vagueness check in tools/check_description.py, whose few-shot examples (lines 28–31) are English
only. It does not come from the stop-word list. Change: Add Chinese few-shot examples to the vagueness check, in pairs:
complete lines (state what the goods are, plus use and/or composition) marked not vague; genuinely vague lines (generic
product words only) marked vague. Keep the existing English examples. Equal numbers of vague and complete Chinese
examples. Constraints: Examples must NOT be coolant lines or any line from the eval, coolant or outside sets. Use other
goods, so the eval measures generalisation rather than memorised examples. No coolant-specific or language-specific
logic in product code; the fix is the prompt examples only. No changes to the stop-word list, routing, voting rule (a),
or ASK_FLOOR. Acceptance: 1. Complete Chinese coolant lines (incl. coolant-3 and the live-test line) are no longer
flagged vague. Their route is then decided by the vote as for any other line. 2. coolant-1, coolant-2 and plain "冷却液"
are still flagged vague and go to ask shipper. 3. No regression: 120-line eval stays ≥ 77 correct with ≤ 9 wrong
auto-accepts (SC-004); coolant set stays 8/8; outside set stays ≥ 12/14. 4. offline-suite covers the new examples
without live model calls. Cost: Acceptance 1–3 need live eval runs on OpenRouter: estimate first and get approval under
the 2x rule."

## Background

What the app does today, checked against `public/main` at 1b3a832 on 2026-11-23:

- **The check.** Every line's description goes first through the deterministic rules (the firm stop-word list, the two
  ICS2 lists and their bilingual aliases, matched on the goods name; feature 001's FR-008) and then, when no rule
  matches, through one model judgement. The judgement's prompt states the criterion (a reader can tell what the goods
  are; a precise product name is enough on its own; the material or the use is needed only when the product word alone
  could mean many things) and gives examples: eight acceptable and eight vague lines, all English. A line the judgement
  calls vague is flagged Vague with the judgement's reason, asks the shipper for the material, the product name and the
  use, and, since the vague rule of 2026-11-19 (feature 014a), always routes to ask the shipper.
- **The false flag** (backlog item 17; the live test of 2026-11-20). The line 金属加工冷却液，不含矿物基础油, typed in
  Chinese only (the Chinese half of coolant-6; "the live-test line" below), got the right code 3403.99 and was routed to
  ask the shipper, with a question for the material and the use that the line states. No list under `data/rules/`
  holds 冷却液 and the rules match no coolant line; the flag is the judgement's. In all 15 stored runs of the coolant set
  (Gemini 2.5 Flash, 2026-11-18 and 19) every Chinese-only coolant line was judged vague: coolant-1 冷却液
  矿物油含量大于70%, coolant-2 没有矿物基础油的冷却液, coolant-3 金属加工用的冷却液，不含矿物油 and coolant-8 冷却液. The same facts in
  English or German (coolant-4 to coolant-7) passed in every run. Under feature 001's FR-009 ("the material or use where
  the term alone is generic") coolant-3 and the live-test line should pass; coolant-1 and coolant-2 state a composition
  but not the use, which is what separates an engine coolant (3820.00) from a metal-working one (3403.99 or 2710.19).
- **The shipped numbers** (rule (a) and the vague rule; Gemini 2.5 Flash with reasoning off, query expansion off,
  customs wording off, threshold 85, floor 0.40, three runs; the precedent override off, as the evaluation keeps its
  history; `specs/014a-retrieval-evidence/eval-diff.md` and `docs/reports/014a-regression-analysis.md`, section 5):
  the 120-line set, iteration 21: majority top-1 77 of 120, wrong auto-accepts 3 / 3 / 3 per run and 3 lines by
  majority per line (IEBTIIENEN004-2024-BTI356, MTBTI2024-002 and MTBTI2025-011, each auto-accepted with a wrong top-1
  in all three runs; with the override on, majority top-1 80 and the same 3 lines); the coolant set, iteration 9: 8 of
  8 right, wrong auto-accepts 0 / 0 / 0 and none by majority per line; the outside set, iteration 1: 12 of 14, wrong
  auto-accepts 0 / 1 / 1 (the bike U-lock FRBTIFR-BTI-2026-00308 in every case) and 1 by majority per line (that line,
  in 2 of its 3 runs); the override on changes neither typed set. The per-line counts were computed offline from the
  stored rows on 2026-11-23 (clarification of the same day). Each evaluation row keeps the line's flag and route per
  run, so a flag is measured by the same runs that measure the codes.
- **Chinese lines in the evaluation.** The 120-line set has none (its 30 Chinese renderings are a separate file run only
  with `--lang zh`); the coolant set has four Chinese-only and two bilingual lines; the outside set has none.

## Clarifications

### Session 2026-11-23

- Q: How should the live-test line (the Chinese-only half of coolant-6) be measured for Acceptance 1? → A: Add it to
  the coolant set as coolant-9, expected 3403.99: the same paid runs record its flag and route per run next to
  coolant-3, in the tracked set and report rather than a one-off check. SC-004 keeps "8 of 8" for the original eight
  lines; coolant-9 is reported alongside them, not folded into that count, as a new regression guard this feature adds.
- Q: Must the flag criteria hold in every one of the three runs, or on the majority of runs? → A: Every run, for both
  Acceptance 1 (SC-001) and Acceptance 2 (SC-002): the requirement's wording is unconditional, and all 15 stored runs
  were unanimous on these lines before the fix, so a flip in one run of three after the change is new behaviour to
  report, not scoring noise. The majority-of-three convention stays for the top-1 counts of Acceptance 3 (SC-003,
  SC-004), as today.
- Q: If the first paid after-runs fail Acceptance 1 or 2, may the examples be revised once and the three sets re-run
  within the 2x margin of the approved estimate, or must the feature stop after the first failure? → A: One revision
  round within the 2x margin, under the same constraints (prompt examples only, goods outside the sets, equal pairs);
  a second failure stops the feature and reports to the author. Staying inside a budget the author pre-approved needs
  no fresh ask, as the 2x rule has worked throughout the project; one round keeps the extra work bounded. (Superseded
  the same day by the staged approval, the fifth entry.)
- Q: How is Acceptance 3 ("no regression") decided across the three runs, for the wrong auto-accepts in particular? →
  A: By majority per line for the 120-line, coolant and outside sets, with the per-run numbers reported alongside so
  that the variance is visible (the author's decision of 2026-11-23). The top-1 counts of SC-003 and SC-004 were
  already majority per line; SC-003's wrong auto-accepts, summed over the three runs until now (at most 9), are
  counted per line: a line counts when it is auto-accepted with a wrong top-1 in at least 2 of its 3 runs, and the
  after-run passes when that count is at most the baseline's, computed the same way from the stored rows of
  iteration 21: 3 lines with the override off (IEBTIIENEN004-2024-BTI356, MTBTI2024-002 and MTBTI2025-011, each in
  all three runs) and the same 3 with it on. SC-004's pass/fail stays; its wrong auto-accepts are reported per run and
  as the per-line majority count. SC-001, SC-002 and SC-007 are flag criteria judged in every run, not Acceptance 3
  scores, and are unchanged. For each set the report carries a per-run table (right, auto-accepted and wrong
  auto-accepted per run, the override off and on) next to the majority-per-line results that decide pass or fail.
- Q: In what order do the paid after-runs go, and what happens on a miss? → A: The author's staged approval of
  2026-11-23, given at the approval step: the coolant set first (three runs); the outside set and the 120-line set
  only if every coolant criterion holds (SC-001, SC-002, the original eight each right on majority, which is
  SC-004's coolant half, and SC-007); the outside set next, then the 120-line set, and the 120-line set only if the
  outside set is at least 12 of 14 right on majority (SC-004). Judged by majority per line, with the per-run numbers
  in the report, under the $1.30 cap over everything, the tallies checked before each stage. On any miss the
  implementation stops and reports per line (flag, route and top-1 per run, against the baseline) before spending
  more: this replaces the automatic revision round of the third entry; no revision round runs without the author's
  go-ahead. The commit of the results follows the stage reached: all three sets run, the result files, history
  entries, re-rendered reports, eval-report.md and the backlog and README edits; a stop before that, the result files
  and report of the sets that ran, the backlog and README outcome edits left for later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A complete Chinese line is not sent back to the shipper (Priority: P1)

The clerk checks a Chinese-only line that names the goods and states their use and composition, such as the live-test
line or coolant-3. The line is not flagged vague. Its route comes from the ruling vote, as for any other unflagged
line, and the clerk sees the code with its rulings instead of a question for the shipper that the line already
answers.

**Why this priority**: every false flag costs a shipper round-trip and contradicts the check's own criterion; the
Hamburg clerk's input is mostly Chinese.

**Independent Test**: the live-test line and coolant-3 through the check with the configured model, three times: no
vague flag in any run, the route per run equal to the vote's.

**Acceptance Scenarios**:

1. **Given** the live-test line 金属加工冷却液，不含矿物基础油, **When** it is checked, **Then** its flag is OK and its route
   is the vote's (auto-accept or human review), never ask the shipper on account of a vague flag.
2. **Given** coolant-3 金属加工用的冷却液，不含矿物油, **When** it is checked, **Then** its flag is OK, its top candidate
   stays 3403.99 and its route is the vote's.
3. **Given** the bilingual coolant-6 (the live-test line with its English half), **When** it is checked, **Then** it is
   judged as today: OK, 3403.99.

---

### User Story 2 - A genuinely vague Chinese line still asks the shipper (Priority: P1)

A Chinese line that only names a generic product, or names one with several meanings without saying what it is for,
stays flagged vague and routes to ask the shipper: 冷却液 alone, 没有矿物基础油的冷却液 (coolant-2) and 冷却液
矿物油含量大于70% (coolant-1).

**Why this priority**: the fix must not buy the complete lines by letting vague ones through; a vague line that reaches
review or auto-accept without a question is the worse error (constitution Principle III).

**Independent Test**: the three lines through the check with the configured model, three times: flagged vague and
routed to ask the shipper in every run.

**Acceptance Scenarios**:

1. **Given** 冷却液 (coolant-8), **When** it is checked, **Then** it is flagged vague and routed to ask the shipper.
2. **Given** coolant-2 没有矿物基础油的冷却液, **When** it is checked, **Then** it is flagged vague and routed to ask the
   shipper.
3. **Given** coolant-1 冷却液 矿物油含量大于70%, **When** it is checked, **Then** it is flagged vague and routed to ask the
   shipper, with its top candidate still 2710.19.

---

### User Story 3 - The change is measured before it ships (Priority: P2)

The author sees, before the merge, that the three evaluation sets have not regressed, that the cost was estimated and
approved before any paid run, and that the offline suite pins the examples so that a later edit cannot drop, move or
duplicate one unnoticed.

**Why this priority**: a prompt change is measured, never assumed (constitution Principle VII); the evaluation spends
credits and needs the author's approval.

**Independent Test**: the offline suite passes without an API key; the after-runs of the three sets are compared with
the shipped numbers in the pull request.

**Acceptance Scenarios**:

1. **Given** the examples in place, **When** the offline suite runs without an API key, **Then** the tests that cover
   the examples pass and no model is called.
2. **Given** the approved estimate, **When** the three sets run three times each, **Then** the results meet SC-003 and
   SC-004 and the spend stays within the approval.
3. **Given** the staged runs (the coolant set, then the outside set, then the 120-line set; clarification of
   2026-11-23), **When** a stage misses any of its criteria (the coolant set: SC-001, SC-002, SC-004's coolant half or
   SC-007; the outside set: SC-004; the 120-line set: SC-003), **Then** nothing more is run: the report carries the
   miss per line (flag, route and top-1 per run against the baseline) and the line diff (which lines changed their
   top-1 against the baseline, and whether each one's vague flag changed too), and the author decides whether a
   revision round is spent or the feature stops (FR-007).
4. **Given** the after-runs' rows, **When** the report is written, **Then** it lists, per set and per run, the lines
   flagged vague against the baseline runs, and names every line whose flag changed, coolant-4 to coolant-7 included.

---

### Edge Cases

- A bilingual line (Chinese and English halves) is judged on both texts in one data block, as today; no change is
  expected (coolant-5 and coolant-6 pass today).
- A Chinese line that states a composition but not the use, for a product word with several meanings (coolant-1,
  coolant-2), stays vague. Every complete example therefore states a use; none relies on a composition alone.
- A Chinese line whose goods name is a listed term (配件, 电子产品, 日用品) is flagged by the deterministic rule before any
  judgement, as today; the examples change no list.
- A line equal to one of the examples is judged like any other line: the examples are prompt text, not a rule.
- The judgement flips between runs on a coolant line: flags are recorded per run, and SC-001 and SC-002 are judged on
  every run, not on a majority.
- A line elsewhere is newly judged vague (an English line of the 120-line set, an outside line, or coolant-4 to -7):
  it is still classified and scored on its top-1, so it loses at most an auto-accept and can never add a wrong one;
  SC-003 and SC-004 cannot see it. FR-008's flag comparison against the baseline runs makes it visible, and SC-007
  gates it for coolant-4 to -7.
- A line's top-1 changes while its flag did not: a top-1 change counts as run-to-run noise only on a line whose three
  baseline runs already disagreed among themselves (120-line set: MTBTI2025-018, XIBTI505060394,
  IEBTIIENEN004-2026-BTI72, IEBTIIENEN004-2026-BTI71; outside set: FRBTIFR-BTI-2026-00308; none in the coolant set).
  Any other top-1 change on a line whose flag did not change is reported as "not attributable: flag unchanged, reason
  text not recorded": an OK judgement's reason text reaches the ranking prompt and can change without the flag, and
  the evaluation rows do not record it. The report says which case each line is (FR-007).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The vagueness judgement's examples MUST include Chinese lines in equal numbers of complete and vague ones,
  in four pairs about one family of goods each. The complete member names the goods and states their use and their
  material or composition; the vague member is a bare generic category term, which may connote a broad class of goods
  or a material (金属件, as the English "hardware" does) without itself stating a specific composition or use. The
  pairs are:

  | Pair | Complete, marked acceptable | Vague, marked vague |
  |---|---|---|
  | 1 | 铝合金折叠梯，家用 (aluminium-alloy folding ladders, household use) | 金属件 (metal pieces) |
  | 2 | 陶瓷地砖，室内地面用 (ceramic floor tiles, for indoor floors) | 建材 (building materials) |
  | 3 | 儿童用的塑料餐具，不含双酚A (plastic tableware for children, free of bisphenol A) | 日用百货 (daily-use merchandise) |
  | 4 | 橡胶密封垫片，水管接头用 (rubber sealing gaskets, for pipe joints) | 零部件 (parts and components) |

  The English glosses are for the reader of this document; the prompt carries the Chinese text only.
- **FR-002**: The sixteen English examples in the prompt today MUST stay, word for word and as laid out in the source
  (three of them are split across source lines; the sentence is not re-flowed): acceptable "stainless steel vacuum
  flask", "cotton T-shirts, knitted", "plastic toy cars", "wireless Bluetooth earphones", "silicone mobile phone
  cases", "plastic storage boxes for household use", "steel bobbin cases for industrial sewing machines", "aluminium
  alloy bicycle frames"; vague "parts", "spare parts for machines", "electronic products", "furniture", "hardware",
  "gift", "accessories", "XK-200". Everything in the prompt other than the new Chinese sentence MUST stay byte for
  byte, the declaration that instructions inside the data block are void included.
- **FR-003**: No Chinese example of FR-001 MAY be a coolant line (none contains 冷却液, 冷却, 切削, 润滑, 乳化, 防冻 or 油, or otherwise names a
  coolant, lubricant or cutting fluid), nor equal or contain a line of the 120-line evaluation set or its Chinese
  renderings, of the coolant set or of the outside set (their texts, original forms and Chinese and English halves).
  Every Chinese example of FR-001 MUST pass the deterministic rule check against the shipped rule lists under
  `data/rules/` (no firm, ICS2 or alias term matches its goods name), so that each is a line the judgement would
  actually see. The English examples are fixed by FR-002 as they stand and are outside these checks: five of the
  vague ones ("parts", "spare parts for machines", "electronic products", "gift", "accessories") are listed terms the
  rules flag before any judgement, as research R-02 records for the generic words. The exact-text
  check cannot fire against the English 120-line and outside sets, so "other goods" beyond exact or substring overlap
  is a judgement made when the examples are chosen and recorded in research R-02, not something a test enforces. The
  pairs of FR-001 were checked against all four files, the shipped rule lists and the test fixtures' rule lists on
  2026-11-23.
- **FR-004**: The change to the product MUST be the prompt's examples only: no new logic in the check (no language
  detection, no coolant or chemical rule, no change to the judgement's answer or to what a flagged line asks for), no
  change to the stop-word or ICS2 lists or their aliases, to routing, to rule (a), to the vague rule or to ASK_FLOOR.
- **FR-005**: Offline tests, with no model call, MUST pin the examples, matching on whitespace-normalised text (the
  prompt is a wrapped source string, so neither the English examples nor the Chinese sentence's markers may be sought
  as literal substrings): each Chinese example of FR-001 present exactly once, the complete ones in the acceptable
  group and the vague ones in the vague group, in equal numbers; every English example of FR-002 present; the prompt
  without the Chinese sentence equal, byte for byte, to today's prompt (a stored SHA-256 of today's string); no
  Chinese example containing a coolant word of FR-003 and none equal to or containing a text of the four evaluation
  files (FR-003's direction); every Chinese example passing the rule check of FR-003 against the shipped rule lists.
- **FR-006**: After the change, the three evaluation sets MUST be run three times each with the configured chat model
  and the project's evaluation settings (reasoning off, query expansion off, customs wording off, threshold 85, floor
  0.40, the precedent override off in the recorded measures and replayed on), on the rebuilt store of every chapter,
  each row recording the line's flag and route per run. The live-test line MUST be measured in the same runs as a ninth
  line of the coolant set, coolant-9, expected 3403.99 (clarification of 2026-11-23); it is reported alongside the
  original eight lines and not counted in their 8 of 8.
- **FR-007**: Before the first paid run the cost MUST be estimated from the closest comparable runs (the 120-line,
  coolant and outside runs of 2026-11-19) and approved by the author under the 2x rule; the spend MUST be read from the
  key's usage and reported against the approval. The runs are staged (the author's approval of 2026-11-23): the
  coolant set first, three runs; the outside set only if every coolant criterion holds (SC-001, SC-002, the original
  eight each right on majority, SC-007); the 120-line set only if the outside set is at least 12 of 14 right on
  majority; the $1.30 cap holds over everything and the tallies are checked before each stage. On any miss the
  implementation MUST stop and report per line (flag, route and top-1 per run, against the baseline) before spending
  more; no revision round runs without the author's go-ahead. With it, the examples MAY be revised once, under
  FR-001's rules (four pairs; complete = goods + use + material; vague = a bare generic category term), with FR-001's
  table updated and FR-002 to FR-004 unchanged, and the sets re-run in the same stages within the cap; a second
  failure stops the feature and the author decides. The report carries the line diff with every miss. The line diff
  lists every line whose majority top-1 differs from the baseline run's and whether
  its vague flag changed in any run; a top-1 change counts as run-to-run noise only on a line whose three baseline
  runs already disagreed among themselves (120-line set: MTBTI2025-018, XIBTI505060394, IEBTIIENEN004-2026-BTI72,
  IEBTIIENEN004-2026-BTI71; outside set: FRBTIFR-BTI-2026-00308; none in the coolant set), and any other top-1 change
  on a line whose flag did not change is reported as "not attributable: flag unchanged, reason text not recorded".
- **FR-008**: The pull request MUST report, per set, the comparison with the shipped numbers of the Background: the
  results by majority per line that decide pass or fail (majority top-1, and the wrong auto-accepts counted per line
  by majority as SC-003 counts them) with, next to them, a per-run table of right, auto-accepted and wrong
  auto-accepted per run, each with the precedent override off and on, so that the variance is visible (clarification
  of 2026-11-23); the coolant set's counts without coolant-9, or naming it, coolant-9 kept separate from the original
  eight; and, for coolant-1, -2, -3, -8 and the live-test line, the flag and route per run.
  It MUST also list, per set and per run, the lines flagged vague, against the baseline runs (the 120-line set's
  iteration 21: IEBTIIENEN004-2023-BTI572, IEBTIIENEN004-2025-BTI249, IEBTIIENEN004-2026-BTI105,
  IEBTIIENEN004-2026-BTI124 and XIBTI505068566 in every run; the outside set's iteration 1: none; the coolant set's
  iteration 9: coolant-1, -2, -3 and -8, with coolant-4 to -7 OK in all 15 paid runs), and name every line whose flag
  changed in any run, coolant-4 to -7 included. Backlog item 17 MUST record the outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the after-runs, coolant-3 and the live-test line (coolant-9) have the flag OK in every one of the three
  runs (a failed judgement does not count), and each one's route in every run is the vote's (auto-accept or human
  review), never ask the shipper.
- **SC-002**: In the after-runs, coolant-1, coolant-2 and coolant-8 (冷却液) are flagged vague in every run and routed to
  ask the shipper in every run.
- **SC-003**: The 120-line set's majority top-1 is at least 77 of 120, and its wrong auto-accepts counted per line by
  majority (a line counts when it is auto-accepted with a wrong top-1 in at least 2 of its 3 runs) are at most the
  baseline's count computed the same way from the rows of iteration 21: 3 lines (IEBTIIENEN004-2024-BTI356,
  MTBTI2024-002 and MTBTI2025-011, each in all three runs). Pass or fail is judged with the precedent override off, as
  today, against 77 and 3; the override-on numbers (majority top-1 80 and the same 3 lines today) are computed the same
  way from each row's override-on block and reported alongside. The wrong auto-accepts per run (3 / 3 / 3 today, off
  and on) are reported next to the count and never summed into a criterion (clarification of 2026-11-23). This is the
  requirement's Acceptance 3, whose "(SC-004)" names feature 014a's SC-004 (wrong auto-accepts not above the
  baseline's), not this specification's SC-004.
- **SC-004**: The coolant set's original eight lines are each right on majority, read from the run summary's per-line
  entries (`lines`: `id`, `majority`, `right`) for coolant-1 to coolant-8, not from the set-wide counts, which include
  coolant-9 once it exists (coolant-9 is reported alongside them under SC-001, never in their count); the outside set
  is at least 12 of 14 right on majority. Their wrong auto-accepts are reported, not judged: per run against today's
  0 / 0 / 0 and 0 / 1 / 1, and as the per-line majority count of SC-003 against today's 0 and 1
  (FRBTIFR-BTI-2026-00308, in 2 of its 3 runs), with the override off and on; the coolant set's computed without
  coolant-9 or naming it.
- **SC-005**: The offline suite passes without an API key with the tests of FR-005 in it, and no test of this feature
  calls a model.
- **SC-006**: The paid runs' spend is within twice the approved estimate, and the approval precedes the first paid call.
- **SC-007**: In the after-runs, coolant-4, coolant-5, coolant-6 and coolant-7 keep the flag OK in every run, as in all
  15 paid runs before the change.

## Assumptions

- **Four pairs.** The English list has eight and eight; the Chinese list needs to show the boundary, not cover goods.
  Each pair shares a family of goods so that the contrast is visible, and the goods (ladders, floor tiles, children's
  tableware, gaskets) lie outside every evaluation set. The bundled sample that "Load sample invoice" loads is
  `data/samples/sample_packing_list.xlsx` (twelve bilingual lines); its line 11, 橡胶密封圈 / Rubber O-ring gaskets,
  vulcanised, is close to pair 4's complete member. That is no breach of FR-003: the sample is not an evaluation set,
  and the English examples already come from it (vacuum flask, T-shirts, toy cars, earphones, phone cases, bicycle
  frames).
- **Every complete example states a use** and all four also a material; pair 3 adds a negative composition in the form
  of coolant-3 and the live-test line ("不含…"). None relies on a composition alone, because the lines that must stay
  flagged (coolant-1, coolant-2) state a composition without a use. Pair 4 mirrors the English "parts" and "spare parts
  for machines": a bare 零部件 (parts and components) is vague, a named part with its material and use (rubber sealing
  gaskets for pipe joints) is complete. The author chose 零部件 on 2026-11-23 after review round 1: 垫片 (gaskets), the
  first draft, is a specific product word rather than a category, and 零件 (parts) is an ICS2 alias of "parts" that the
  deterministic rule flags before any judgement, so it would never reach the model on its own (FR-003).
- **Limitation of the measurement.** Pair 3 shares the construction X用的Y，不含Z with coolant-3, and its "，不含…" ending
  with the live-test line. SC-001 measures only these two Chinese complete lines, so a pass shows this construction
  clearing the flag more than it shows generalisation beyond it. The optional measurement of the 30 Chinese
  renderings of the 120-line set (`--lang zh`, about $0.13 for three runs) is not added: it is outside the approved
  budget and not needed to meet the acceptance criteria; the flag comparison of FR-008 covers the sets that are run.
- **The prompt carries the Chinese text without English glosses**, as the lines arrive; the model is multilingual.
- **The examples are not run live themselves** (they would be memorised); the coolant lines and the three sets measure
  them.
- **Coolant-9.** The live-test line joins the coolant set as its ninth line (expected 3403.99) so that SC-001 is
  measured and recorded by the same runs; "8 of 8" in SC-004 refers to the original eight lines (confirmed by the
  author, clarification of 2026-11-23).
- **Per-run flags.** SC-001 and SC-002 hold on all three runs (confirmed by the author, clarification of 2026-11-23);
  the judgement was stable on these lines in all 15 stored runs, so a flip is a finding, not noise to average away.
  The top-1 counts of SC-003 and SC-004 keep the majority of three, and so does SC-003's wrong auto-accept count
  (clarification of 2026-11-23), with the per-run numbers reported alongside.
- **Staged runs, no automatic revision round.** Clarification 3 of 2026-11-23 allowed one revision round within the
  2x margin on a missed SC-001 or SC-002 without a fresh ask; the author's staged approval of the same day, given at
  the approval step (clarification 5), supersedes it: the coolant set runs first, the outside set only if every
  coolant criterion holds, the 120-line set only if the outside set holds too, and on any miss the implementation
  stops and reports per line before spending more. A revision round (the examples revised once under FR-001's rules,
  FR-001's table updated, FR-002 to FR-004 unchanged, the sets re-run in the same stages within the $1.30 cap) needs
  the author's go-ahead; a second failure stops the feature and the author decides (FR-007).
- **No new baseline run.** The shipped numbers of iterations 21, 9 and 1 are the baseline: the same model, store and
  settings; run-to-run noise of one or two lines on the 120-line set is known, and SC-003's thresholds are absolute
  (77 right and 3 wrong auto-accepts by majority per line, the latter read from the stored rows of iteration 21 without
  a model call).
- **Model, store and settings** are the shipped ones: Gemini 2.5 Flash with reasoning off, the rebuilt store of every
  chapter (123,531 rulings, extract of 2026-11-18), the evaluation flags of FR-006.
- **Out of scope**: the UI points of backlog item 17 (block 1's "Stop-word check" label, the vagueness reason in place
  of "candidates too close"), item 4's line-specific shipper questions, quote verification or any new field in the
  judgement's answer, new Chinese-only lines in the 120-line or outside sets, retiring ASK_FLOOR (item 19), and any
  change to the README beyond what the pull request's numbers require.
