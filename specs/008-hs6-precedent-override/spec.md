# Feature Specification: Precedent Override at the HS-6

**Feature Branch**: `008-hs6-precedent-override`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Precedent override at HS-6. Today the ruling vote can only confirm or reject the model's top-1 HS-6. Add a rule, in code only: when the top-1 fails the gate but 4 or 5 of the 5 nearest eligible rulings agree on the model's candidate 2 or 3, choose that candidate and auto-accept with the note "rulings overrode the model: N of 5 agree on <code>". 3 of 5 stays review. If the rulings agree on a code outside the top-3, stay review and show it as a hint. Behind a config switch (HS6_OVERRIDE, OVERRIDE_MIN=4) so the evals compare on and off. The detail row and audit trail must show which candidate was chosen and that the override fired. Evals must record the chosen candidate index and whether candidate 2/3 was right. Success: measured on the HS-6 eval and the end-to-end eval against iteration 12 and e2e-stopword-fix, more right end to end, no increase in wrong auto-accepts. HS-6 only; CN-8 unchanged. Constitution Principle I to 1.6.0."

## Clarifications

### Session 2026-10-26

- Q: Against what do SC-002 and SC-003 measure the override: the historical runs, or the switch off? → A: SC-002 and
  SC-003 compare a single eval run with the switch on against a single run with the switch off made from the same
  stored model answers, not against the historical three-run figures. Wrong auto-accepts must not be higher on than
  off; right end to end must be higher. The historical 7 and 74 stay in the spec as context only.
- Q: Should SC-001 (the end-to-end eval gets more lines right end to end) also compare a single run with the switch
  on against a single run with the switch off made from the same stored model answers, with run `e2e-stopword-fix`'s
  68 of 120 kept as context only? → A: Yes: switch on against switch off from the same stored model answers; 68 of
  120 as context only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-accept the candidate the rulings agree on (Priority: P1)

Today the five nearest EBTI rulings can only confirm or reject the model's top HS-6 candidate. When most of them sit
at the model's second or third candidate, the line goes to review with "Precedents support candidate N", and the clerk
picks that candidate by hand. With this story, when at least four of the five agree on the model's second or third
candidate, the assistant chooses that candidate itself and auto-accepts the line, saying that the rulings overrode the
model. Three of five is not enough: the line stays in review, as today.

**Why this priority**: the HS-6 gate sends many lines to review that the model nearly had right. In the end-to-end
eval of feature 007, only 14 of the 44 to 46 lines the gate sent to review were right at the top candidate their row
pre-selects. Strong agreement of the rulings on another of the model's candidates is evidence that code can act on,
and every line auto-accepted rightly saves the clerk a pick.

**Independent Test**: Check lines whose five nearest eligible rulings sit 5, 4 and 3 of 5 at the model's second or
third candidate, with the switch on and off, and compare the decided code, the route and the note.

**Acceptance Scenarios**:

1. **Given** an unflagged line whose top candidate fails the HS-6 gate, **When** 4 of its 5 nearest eligible rulings
   sit at its second candidate and the switch is on, **Then** the second candidate becomes the decided HS-6, the line
   is auto-accepted, and the note reads "rulings overrode the model: 4 of 5 agree on <code>".
2. **Given** an unflagged line whose 5 nearest eligible rulings all sit at its third candidate, **When** it is checked
   with the switch on, **Then** the third candidate is decided and auto-accepted with "5 of 5".
3. **Given** a line whose nearest rulings sit 3 of 5 at its second candidate, **When** it is checked, **Then** it stays
   in review and names the candidate the rulings support, as today.
4. **Given** a vague or stop-word line whose 5 nearest rulings sit at its second candidate, **When** it is checked,
   **Then** it is not auto-accepted.
5. **Given** the switch is off, **When** any line is checked, **Then** its route, decided code and note are the ones
   the HS-6 gate gives today.
6. **Given** an overridden line, **When** the CN-8 step runs, **Then** it runs on the chosen candidate, exactly as on
   any decided HS-6.

---

### User Story 2 - See which candidate was chosen, and why (Priority: P1)

The clerk must be able to tell an overridden line from an ordinary auto-accept. The line's detail row shows which of
the model's candidates was chosen and that the rulings overrode the model, and the audit trail records the override.
The clerk can change the code like that of any other auto-accepted line.

**Why this priority**: an automatic decision that goes against the model's own ranking must be visible and traceable,
or the clerk cannot trust it (constitution Principles I and VI).

**Independent Test**: Open the detail row and the audit trail of an overridden line and of an ordinary auto-accepted
line, and compare them.

**Acceptance Scenarios**:

1. **Given** an overridden line, **When** the clerk opens its detail row, **Then** it shows that candidate 2 or 3 was
   chosen, its code, the model's top candidate, and the note "rulings overrode the model: N of 5 agree on <code>".
2. **Given** an overridden line, **When** the audit trail is exported, **Then** it holds an entry that records the
   override, the chosen candidate's rank and code, and the note.
3. **Given** an overridden line, **When** the clerk changes its HS-6, **Then** the clerk's code is decided and
   recorded as for any auto-accepted line.

---

### User Story 3 - A hint when the rulings agree on a code the model did not propose (Priority: P2)

With the switch on, when at least four of the five nearest rulings agree on an HS-6 that is not among the model's
three candidates, the line stays in review: the model never ranked that code, so the assistant does not choose it. The
detail row shows the code as a hint, with how many rulings agree, so that the clerk can weigh it. With the switch off,
the row is as today, with no hint.

**Why this priority**: it helps the clerk's pick, but it is information, not an automatic decision.

**Independent Test**: Check a line whose nearest rulings sit 4 of 5 at a code outside the model's top three, with
the switch on and off, and check its route, the hint, and that nothing is chosen.

**Acceptance Scenarios**:

1. **Given** the switch is on and a line whose nearest rulings sit 4 of 5 at a code outside its top three, **When** it
   is checked, **Then** it stays in review and the detail row shows the hint "4 of 5 nearest rulings agree on <code>,
   which is not among the candidates".
2. **Given** that hint, **When** the clerk wants the code, **Then** they enter it as any other code of their own; the
   assistant never chooses, pre-selects or auto-accepts it.
3. **Given** the switch is off, **When** the same line is checked, **Then** it stays in review with no hint.

---

### User Story 4 - Measure the override on and off (Priority: P2)

The author needs to know whether the override helps before the switch is turned on. The HS-6 eval and the end-to-end
eval record, for every line, which candidate was chosen, whether the override fired, and whether the candidate the
rulings supported was right; their reports compare the switch on and off, both made from the same stored model
answers, so that the comparison shows the rule and not the run-to-run variation of the model.

**Why this priority**: the rule must earn its place by measurement (constitution Principle VII).

**Independent Test**: Run each eval with the switch on and off on the fixed 120-ruling set and compare the recorded
fields and totals.

**Acceptance Scenarios**:

1. **Given** an eval run, **When** a line is classified, **Then** its record holds the chosen candidate's rank (1, 2,
   3, or none), whether the override fired, and, when the rulings supported candidate 2 or 3, whether that candidate
   was right.
2. **Given** an eval run, **When** it ends, **Then** its report gives the switch state, the overrides that fired and
   how many chose the right HS-6, the lines right end to end, and the wrong auto-accepts.
3. **Given** one run's stored model answers, **When** the eval makes its switch-off and switch-on results from them,
   **Then** the two results differ only on the lines where the override fired, and in what follows from them.

---

### Edge Cases

- Fewer than five eligible rulings vote, because some sit below the similarity floor: the override still needs
  OVERRIDE_MIN agreeing rulings, and the note gives the number that voted ("4 of 4").
- Exactly OVERRIDE_MIN agreeing rulings (4 of 5) override; one fewer (3 of 5) does not.
- The rulings' majority is the model's top candidate but below the vote share, or the rulings are split: no override;
  the line goes to review as today.
- No eligible ruling votes: the confidence fallback decides as today; no override.
- A line that was ever flagged, or updated by a shipper reply: the override never auto-accepts it; like a line whose
  top candidate passes the gate, it stays in review until the clerk confirms.
- The model returns fewer than three candidates: only the candidates it returned can be chosen.
- The clerk moves the auto-accept threshold on the Admin page: overrides do not change, as they do not use the
  model's confidence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: With the switch on, an unflagged line whose top HS-6 candidate fails the HS-6 gate MUST be auto-accepted
  with the model's second or third candidate when at least OVERRIDE_MIN (default 5, see FR-007) of the 5 nearest
  eligible EBTI rulings sit at that candidate's HS-6. These are the rulings the HS-6 gate counts: valid on the day,
  coded to the loaded nomenclature, at or above the similarity floor, each counted once.
- **FR-002**: The chosen candidate MUST become the line's decided HS-6; the model's ranking of its candidates is kept
  and shown unchanged. The route reason MUST read "rulings overrode the model: N of M agree on <code>", where N is
  the number of agreeing rulings and M the number that voted, 5 unless fewer were eligible.
- **FR-003**: When fewer than OVERRIDE_MIN of the voting rulings sit at the model's second or third candidate (for
  example 3 of 5), the line MUST stay in review and name the candidate the rulings support, as today.
- **FR-004**: With the switch on, when at least OVERRIDE_MIN of the voting rulings sit at an HS-6 outside the model's
  three candidates, the line MUST stay in review, and its detail row MUST show that code as a hint with the agreement
  ("N of M nearest rulings agree on <code>, which is not among the candidates"). The assistant MUST NOT choose,
  pre-select or auto-accept that code. With the switch off, no hint is shown.
- **FR-005**: The override MUST NOT apply to a flagged line, MUST NOT auto-accept a line that was ever flagged or
  updated by a shipper reply without the clerk's click, and MUST NOT apply when the top candidate passes the gate or
  when no eligible ruling votes.
- **FR-006**: The override MUST be computed in code from the line's candidates and the ruling vote, like the rest of
  the routing; it MUST NOT be a model decision, and no prompt changes.
- **FR-007**: A configuration switch, HS6_OVERRIDE, MUST turn the override on and off, and OVERRIDE_MIN MUST set the
  agreeing rulings it needs. The switch was off by default until the evals met SC-001 to SC-003; they met them at
  OVERRIDE_MIN 5 and not at 4, so the switch ships on with OVERRIDE_MIN 5, all five nearest eligible rulings (T027).
  With the switch off, every route, decided code and note MUST be the ones the HS-6 gate gives without the override.
- **FR-008**: The detail row of an overridden line MUST show which candidate was chosen (its rank, 2 or 3, and its
  code), the model's top candidate, and the note, and the line's code in the table MUST be the chosen candidate's.
- **FR-009**: The audit trail MUST record each override: the chosen candidate's rank and code, the model's top
  candidate, and the note.
- **FR-010**: The CN-8 and TARIC steps MUST run on the chosen candidate as on any decided HS-6. The CN-8 gate, the
  TARIC rules, the vote parameters (5 rulings, the vote share, the similarity floor) and the confidence fallback are
  unchanged.
- **FR-011**: The clerk MUST be able to change an overridden line's HS-6 as on any auto-accepted line; the clerk's
  code then wins and is recorded as the clerk's decision.
- **FR-012**: The HS-6 eval and the end-to-end eval MUST record, per line, the chosen candidate's rank (1, 2, 3, or
  none), whether the override fired, and whether the candidate the rulings supported (2 or 3) was right. Per run they
  MUST report the switch state, the overrides that fired and how many chose the right HS-6, the lines right end to
  end, and the wrong auto-accepts. The HS-6 eval's accuracy and its end-to-end estimate MUST use the decided HS-6
  (the chosen candidate) rather than the top candidate alone. Each eval MUST store a run's model answers so that its
  switch-off and switch-on results are made from the same answers, including, for a line whose HS-6 the switch
  changes, the answers the later steps need for either HS-6.
- **FR-013**: The behaviour at exactly OVERRIDE_MIN agreeing rulings MUST be fixed (4 of 5 overrides, 3 of 5 does not)
  and covered by a test, as the constitution requires for every threshold.
- **FR-014**: The export schema MUST stay unchanged; an overridden line exports the chosen candidate as its decided
  code.

### Key Entities *(include if feature involves data)*

- **Precedent override**: the decision, on one line's HS-6, to take the model's second or third candidate instead of
  its top one. It holds the chosen candidate's rank and code, the model's top candidate, the agreeing rulings (N of
  M) and the note.
- **Ruling hint**: with the switch on, on a line in review, an HS-6 outside the model's three candidates on which at
  least OVERRIDE_MIN of the voting rulings agree, with that count. It is shown, never chosen.
- **Override switch**: the configuration HS6_OVERRIDE (on by default, or off) and OVERRIDE_MIN (agreeing rulings
  needed, default 5).
- **Eval line record**: the existing per-line record of the HS-6 eval and the end-to-end eval, extended with the
  chosen candidate's rank, whether the override fired, and whether the supported candidate was right.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Right end to end is higher with the switch on than with it off on the end-to-end eval, comparing a
  single run with the switch on against a single run with the switch off made from the same stored model answers. For
  context only: run `e2e-stopword-fix` had 68 of 120 right end to end.
- **SC-002**: Wrong auto-accepts are not higher with the switch on than with it off, on the HS-6 eval and on the
  end-to-end eval, each comparing a single run with the switch on against a single run with the switch off made from
  the same stored model answers. For context only: run `e2e-stopword-fix` had 7 wrong auto-accepts.
- **SC-003**: Right end to end is higher with the switch on than with it off in the HS-6 eval's end-to-end estimate
  against the CN-8 eval's iteration 12, comparing a single run with the switch on against a single run with the
  switch off made from the same stored model answers. For context only: constitution 1.5.0 records that estimate as
  74 of 120 on majority results.
- **SC-004**: Every line the override decides shows the chosen candidate and the note: in the page test, a seeded
  overridden line shows them in its detail row and its audit trail; in every eval run, each overridden line's row
  carries the note in its route reason and the chosen candidate's rank.
- **SC-005**: With the switch off, the routes and decided codes computed from the same model answers and rulings are
  identical to today's.
- **SC-006**: Every eval run reports how many overrides fired and how many of them chose the right HS-6.

## Assumptions

- "5 nearest eligible rulings" are the k nearest eligible EBTI rulings of the HS-6 gate (constitution 1.5.0: k = 5,
  vote share 0.5, similarity floor 0.40). The override uses the same rulings and adds no new search.
- The override does not use the model's confidence: the chosen candidate's own estimate is not a routing input, as
  constitution 1.5.0 states for both layers.
- "The rulings agree on a code outside the top-3" uses the same OVERRIDE_MIN as the override.
- HS6_OVERRIDE ships on, at OVERRIDE_MIN 5, after the evals (T027). Each eval compared the switch on and off from
  the same stored model answers. At 5 they met SC-001 to SC-003: right end to end 67 → 69 of 120, the HS-6 eval's
  end-to-end estimate 74 → 77, wrong auto-accepts unchanged in both evals. At 4 they did not: right end to end
  67 → 74, but wrong auto-accepts on the HS-6 eval 3 → 6. The switch is set when the app starts, not on the Admin
  page; CARGOLINT_HS6_OVERRIDE "off" turns it off.
- "Iteration 12" is the CN-8 eval's iteration 12 (Gemini 2.5 Flash), against which the HS-6 eval computes its
  end-to-end estimate. The historical figures in SC-001 to SC-003 are context, not baselines: run
  `e2e-stopword-fix`'s 68 of 120 right end to end and 7 wrong auto-accepts (of 56 auto-accepted), and the estimate of
  74 of 120 in constitution 1.5.0 (HS-6 iteration 4 with CN-8 iteration 12).
- One eval run differs from the next by about two lines end to end with no change in the code (feature 007), which
  is why SC-001 to SC-003 compare the switch on and off on the same stored model answers.
- Dependency: constitution Principle I must be amended to 1.6.0 before implementation, since 1.5.0 auto-accepts an
  HS-6 only when the model's code equals the rulings' majority and sends a line whose rulings support the second or
  third candidate to review. The amendment goes through `/speckit-constitution`.
- Dependency: feature 001 says an auto-accepted line's decided code is its top candidate (its vocabulary and FR-020).
  With the override that holds only with the switch off, so feature 001 needs the same correction.
- Out of scope: the CN-8 layer, the TARIC rules, the vote parameters, the threshold, the confidence fallback and the
  export schema.
