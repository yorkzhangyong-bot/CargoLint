# Research: Precedent Override at the HS-6

Phase 0 of `/speckit-plan` for [spec.md](spec.md). The Technical Context has no open questions: the stack, the HS-6
gate and both evals exist (features 006 and 007). Each decision below was taken by reading the code it changes.

## R-01 Where the rule lives

**Decision**: In `agent/routing.py`, next to the HS-6 gate. `hs6_gate(confidence, threshold, vote, override_min=None)`
returns `(True, Hs6Gate.vote_override)` when all of these hold:
- `override_min` is set, that is, the switch is on;
- `vote` is not None and does not agree;
- `vote.candidate` is 2 or 3;
- the rulings at that candidate number at least `override_min`.

`route_line` and `hs6_auto_decided` pass `override_min` through. For `vote_override`, the route is `auto_accept` with
the reason "rulings overrode the model: N of M agree on <code>": N is the rulings at the code and M the rulings that
voted, both read from `vote.competing` as `_hs6_votes` reads them today. A pure helper,
`hs6_choice(candidates, vote, gate) -> (rank, code)`, gives the chosen candidate:
- rank 1, the top candidate, unless the gate is `vote_override`;
- `vote.candidate` when it is.

The store, the view and both evals use that helper.

**Rationale**: constitution Principle I requires one deterministic routing function, and `Hs6Vote` already carries the
majority, its rulings (`competing`) and the supported candidate (`candidate`). The flagged-line lock, the ever-flagged
rule and the no-ruling fallback are all applied in `route_line` before or around the gate, so they hold for the
override with no new branch.

**Alternatives considered**:
- A post-processing step in the store that swaps the code. Rejected: routing would live in two places.
- Asking the model to re-rank in the light of the rulings. Rejected: the spec says "in code only" (FR-006).
- A new field on `Hs6Vote`. Rejected: the vote is the same with the switch on or off; only the gate's reading of it
  changes.

## R-02 The switch

**Decision**:
- `OVERRIDE_MIN = 4` is a named constant in `agent/config.py`, next to `HS6_VOTE_K`.
- `Settings.hs6_override` reads `CARGOLINT_HS6_OVERRIDE`: "on" turns it on, anything else leaves it off, and it is
  off by default.
- Each shipment keeps the value its routes use, `Shipment.hs6_override_min: int | None`, where None means off.
  `ui.upload.open_shipment` sets it from the settings, as it sets the threshold and the hybrid flag.
- The store passes it to `route_line`.

**Rationale**:
- Routing stays a pure function of the line and its shipment.
- Tests and evals choose the state for each shipment, with no patched globals. The end-to-end eval uses six worker
  threads.
- The value a shipment was routed with stays with it, like the threshold.
- The switch is set when the app starts, as the spec assumes. FR-007 has it off by default.

**Alternatives considered**:
- A module constant that the evals patch. Rejected: global state shared across worker threads, and invisible in the
  shipment.
- A toggle on the Admin page. Rejected: the spec keeps the switch off that page.

## R-03 Decided code, and everything downstream

**Decision**:
- `LineStore.decided_code` returns `hs6_choice(...)`'s code for an auto-decided line. `chosen_how` stays "auto", so
  the export schema keeps its values (FR-014).
- Code that reads the decided code follows with no change: the CN-8 step (`needs_cn8`), the TARIC step, the export
  rows and "Accept all ready".
- Two places that use the top candidate as "the code to accept" use the chosen candidate when the gate is
  `vote_override`. This is the case of an ever-flagged line, which waits for a click:
  - `ui.view._review_text`, "Confirm: {code}";
  - `ui.view.preselect` for `a_hs6`.

**Rationale**: the store is the one source of the decided code (constitution Principle I: what the UI shows is read
from the store). The model's ranking stays shown unchanged (FR-002).

**Alternatives considered**: reordering the candidates so that the chosen one becomes the top. Rejected: the detail
row and the audit would lose the model's own top candidate.

## R-04 Audit trail

**Decision**: when `_recompute` sets a line's gate to `vote_override` and its route changes, the store appends a
`code_decided` record with:
- `actor` = routing rule;
- `previous` = the model's top candidate;
- `new` = the chosen code;
- `note` = "rulings overrode the model: N of M agree on <code>; candidate N chosen".

The `route_computed` record keeps the route reason, as for every route.

**Rationale**:
- FR-009 needs the rank, the code, the model's top candidate and the note.
- `code_decided` already means "a code was decided", and the actor tells the rule from the clerk.
- The audit export keeps its change values.
- `_recompute` records only when the route or its reason changes, so the entry is written once per override.

**Alternatives considered**:
- A new `ChangeKind`. Rejected as unneeded.
- Putting everything in the route reason. Rejected: FR-002 fixes the reason's wording.

## R-05 Texts in the detail row

**Decision**: the texts are fixed in [contracts/override.md](contracts/override.md) §2.
- `_hs6_how` gains the override branch, used in the "Decided:" line of `a_change` rows.
- `explain_a` gains the hint for an `a_hs6` row, when the switch is on and at least OVERRIDE_MIN rulings agree on a
  code outside the top three.
- The ready-to-accept text names the chosen candidate.

All are plain strings in native Streamlit elements (constitution Principle VI).

**Rationale**: these are the functions that word the HS-6 decision and the review reason today (`ui/view.py`).

**Alternatives considered**: a separate badge or column. Rejected: it needs no new UI element, and the table's
code column already shows the decided code.

**Flagged, not changed**: feature 005's `contracts/view.md` §5 still lists the texts from before feature 006 ("HS-6 …
auto-accepted at {conf} %"); feature 006 did not update it. This feature's contract is the reference for the new texts.
Bringing 005's contract up to date is outside this feature.

## R-06 The hint follows the switch

**Decision**: the hint for a code outside the top three is shown only when the switch is on, at the same OVERRIDE_MIN.

**Rationale**:
- With the switch off, the clerk sees exactly today's product (FR-007).
- The hint is part of the same rule, so the evals' on and off results differ only by this feature.
- The spec assumes the same OVERRIDE_MIN.

**Alternatives considered**: showing the hint always. Rejected: a switch-off run would no longer equal today's
behaviour.

## R-07 HS-6 eval: on and off from one paid run

**Decision**: `tests/eval/hs6_eval.py` classifies every line once (one paid run, `--repeat 1` for this feature). Each
row already keeps the top three candidates with their confidences, the vote and the 40 nearest rulings. The eval
computes the gate, the route, the chosen candidate and the hit twice from the same row, once with `override_min=None`
(off) and once with `OVERRIDE_MIN` (on).

Each row gains:
- the vote's rulings per code;
- the on result;
- the supported candidate's rank and whether it is right.

The run summary and the history entry keep both states. Accuracy uses the chosen HS-6 (FR-012). The cross-layer
end-to-end estimate is computed for both states against CN-8 iteration 12, pinned as
`tests/eval/cn8_eval_iteration12.json`: a copy of `tests/eval/cn8_eval.json` as committed in `ce3bf02`, Gemini 2.5
Flash, 3 runs. It is passed with `--cn8`; the eval's default stays iteration 11.

**Rationale**:
- The author's plan input: the override is code only, so the switch-off result is replayed from the stored answers
  and rulings, with no second paid run.
- The comparison then shows the rule, not the model's run-to-run spread, which SC-002 and SC-003 require.

**Alternatives considered**: two paid runs, one with the switch off and one with it on. Rejected by the author: they
cost double, and run-to-run noise of about two lines would blur the result.

## R-08 End-to-end eval: on and off from one paid run

**Decision**: `tests/eval/e2e_eval.py` makes one paid run (`--repeat 1`). It opens its shipment with
`hs6_override_min=OVERRIDE_MIN`, so the upload's steps route with the switch on.

After the upload's steps, the eval runs the CN-8 step a second time for every line whose gate is `vote_override`,
under the model's top candidate:
- it uses the same leakage guard and the set's date;
- it does not write the result to the store;
- the row stores both CN-8 answers.

The switch-off result is replayed for each line:
- **An override line**: its HS-6 goes to review, the clerk confirms the top candidate the row pre-selects, its CN-8 is
  the stored answer under the top candidate, and its final route is review.
- **Every other line**: identical in both states.

The rows keep both states. The measures run on each, and the report shows them side by side, with the overrides that
fired and how many chose the right HS-6.

**Rationale**:
- This is the author's plan input: the switch-off replay must be complete.
- It costs one extra CN-8 call per override line and no other model call.

**Alternatives considered**: replaying the CN-8 step on demand later. Rejected: the CN-8 answers must come from the
same run, or noise reappears.

## R-09 Tests first

**Decision**: offline tests come before the code (constitution Principle VII for guardrail code). They cover:
- the exact threshold: 4 of 5 overrides, 3 of 5 does not, 4 of 4 overrides when fewer rulings vote, and 5 of 5
  overrides;
- no override on a flagged line, on a tie, on a share below the threshold, with no eligible ruling, or when the top
  candidate agrees;
- an ever-flagged line, which becomes ready to accept with the chosen candidate;
- the switch off: every gate case equals today's;
- the hint, only outside the top three and at OVERRIDE_MIN or more;
- the store: decided code, audit record, and the CN-8 step on the chosen candidate;
- the view texts;
- both evals: on and off rows derived from one stored run.

**Rationale**: routing is guardrail code, and the constitution requires every threshold's exact behaviour to be fixed
in the spec and tested (FR-013).

## R-10 Governance and documentation, as in feature 006

**Decision**:
- **Before the routing code**: the author runs `/speckit-constitution` with the 1.6.0 amendment drafted in
  [plan.md](plan.md).
- **In the same change as the code**, correct feature 001:
  - its vocabulary ("decided code");
  - FR-020 ("An auto-accepted line's decided code is its top candidate");
  - its data-model §9 footnote ¹. It describes the same gate, so it is corrected with FR-020.
- **After the eval runs**: the README's routing summary and its end-to-end paragraph.

**Rationale**:
- Spec dependency: constitution 1.5.0 forbids auto-accepting a candidate the rulings support when it is the second or
  third.
- Feature 006 handled its amendment, then the matching spec corrections, the same way.
