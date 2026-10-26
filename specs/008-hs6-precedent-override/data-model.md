# Data Model: Precedent Override at the HS-6

Phase 1 of `/speckit-plan`. It extends feature 001's data model (`specs/001-packing-list-check/data-model.md`) and
feature 006's vote. Decisions: [research.md](research.md).

## 1. Configuration

| Name | Where | Type | Default | Rule |
|---|---|---|---|---|
| `OVERRIDE_MIN` | `agent/config.py`, next to `HS6_VOTE_K` | int | 4 | a named configuration constant, 1 ≤ `OVERRIDE_MIN` ≤ `HS6_VOTE_K` (5) |
| `hs6_override` | `Settings`, from `CARGOLINT_HS6_OVERRIDE` | bool | False | "on" turns it on; read when the app starts, as every setting |

## 2. Shipment

| Field | Type | Default | Rule |
|---|---|---|---|
| `hs6_override_min` | int or None | None | None: the switch is off. Otherwise the agreeing rulings the override needs, 1 to `HS6_VOTE_K`. `ui.upload.open_shipment` sets `OVERRIDE_MIN` when `Settings.hs6_override` is on, as it sets `threshold` and `hybrid_search`; tests and evals pass it to `LineStore.new_shipment`. |

The store passes it to `route_line` on every recompute, as it passes `threshold` and `ask_floor`.

## 3. Hs6Gate (enum)

One new value:

| Value | Meaning |
|---|---|
| `vote_override` | the rulings' majority is the model's candidate 2 or 3, with at least the shipment's `hs6_override_min` rulings; that candidate is decided |

The other values keep their meaning. With the switch off, `vote_override` never occurs.

## 4. Derived, not stored

| Derived value | From | Rule |
|---|---|---|
| chosen candidate (rank, code) | `hs6_choice(candidates, vote, gate)` | `(vote.candidate, candidates[vote.candidate - 1].code)` when the gate is `vote_override`; otherwise `(1, candidates[0].code)`; `(None, None)` without candidates |
| N, M | `vote.competing` | N: the rulings at the chosen code (or at the hint's code); M: the rulings that voted, 5 unless fewer were eligible |
| hint (code, N, M) | the vote and the candidates | only with the switch on: the gate is `vote_disagrees`, `vote.majority` is not among the top three candidates, and N ≥ `hs6_override_min` |

`LineVersion` gains no field. `hs6_vote`, `hs6_gate`, `computed_route` and `route_reason` already carry everything;
`route_reason` holds the override's wording (contracts §2).

## 5. Decided code

`LineStore.decided_code(line)` returns the chosen candidate's code and `"auto"` for an auto-decided line. A clerk's
decision still wins and is returned as before. Everything downstream reads this method: `needs_cn8`, the TARIC step,
the export rows and the batch accept.

## 6. Audit record

When `_recompute` turns a line's gate to `vote_override` and its route changes, the store writes one extra record:

| Field | Value |
|---|---|
| `change` | `code_decided` |
| `actor` | `routing_rule` |
| `previous` | the model's top candidate |
| `new` | the chosen code |
| `note` | "rulings overrode the model: N of M agree on <code>; candidate N chosen" |

The `route_computed` record carries the route reason, as for every route.

When the clerk later changes the line's HS-6, the clerk's `code_decided` record has `previous` = the code in force
before the change, which is the chosen candidate. `set_decision` uses `decided_code(line)` when a code is decided and
falls back to the top candidate otherwise, so every line without an override is recorded as today.

## 7. Routing table

This extends feature 001's data-model §9 for an unflagged, checked line. Flagged, failed, unreadable and
no-candidate lines route as before; the override never applies to them.

| HS-6 gate | `ever_flagged` | Switch | Route | Decided HS-6 |
|---|---|---|---|---|
| the top candidate passes (vote agrees; or, with no eligible ruling, confidence ≥ threshold) | False | any | auto_accept | top candidate |
| the top candidate passes | True | any | review (ready to accept) | none until the clerk confirms |
| majority at candidate 2 or 3 with ≥ `OVERRIDE_MIN` rulings | False | on | auto_accept, reason "rulings overrode the model: N of M agree on <code>" | that candidate |
| the same | True | on | review (ready to accept that candidate) | none until the clerk confirms |
| majority at candidate 2 or 3 with fewer rulings (3 of 5) | any | any | review, "Precedents support candidate N" | none |
| ≥ `OVERRIDE_MIN` rulings at a code outside the top three | any | on | review, with the hint | none |
| majority at candidate 2 or 3, or outside the top three | any | off | review, as today | none |
| tie; top candidate below the share; no ruling and below the threshold | any | any | review | none |

## 8. Eval records

Both evals make one paid run and derive the other switch state from the same stored answers. Each run is
`--repeat 1` for this feature.

**HS-6 eval** (`tests/eval/hs6_eval.json`, `hs6_eval_<tag>.json`). A row's existing fields keep today's rule, the switch
off, so the history stays comparable with iterations 1 to 6. New fields:

| Field | Content |
|---|---|
| `vote.counts` | `[[code, rulings], …]`, most first: lets the switch be replayed at any `OVERRIDE_MIN` |
| `supported` | `{"rank": 2, 3 or null, "right": bool or null}`: the candidate the rulings' majority supports, and whether it is the correct HS-6 |
| `on` | `{"gate", "route", "rank", "chosen", "hit"}`: the same row with the switch on |

The run summary and history entry add `override_min` and an `on` block holding the same measures computed on the chosen
HS-6: chosen right, wrong auto-accepts, routes, the end-to-end estimate against CN-8 iteration 12. They also add the
overrides that fired and how many were right.

**End-to-end eval** (`tests/eval/e2e_eval.json`, `e2e_eval_<tag>.json`). Every run is made with the switch on: the
row's existing fields hold that state, and the summary records `override_min`. New fields:

| Field | Content |
|---|---|
| `override` | `{"fired": bool, "rank", "code", "n", "m"}` |
| `supported` | as in the HS-6 eval |
| `cn8_top1` | on an override line, the CN-8 step's answer under the model's top candidate: `cn8`, `written`, `question`, `error`, `gate` |
| `off` | the row replayed with the switch off: `hs6`, `hs6_by`, `cn8`, `written`, `question`, `cn8_error`, `cn8_gate`, `route`, `hit`, `written_hit`, `origin`. On an override line, the HS-6 goes to review, the clerk confirms the top candidate, the CN-8 is `cn8_top1` and the route is review; on every other line it equals the row. |

The run summary and history entry hold the measures for both states, the overrides that fired and how many were right,
and the lines whose outcome differs between the two states.

## 9. Validation rules

- `hs6_override_min` is None or 1 ≤ `hs6_override_min` ≤ `HS6_VOTE_K`. The upper bound is checked against the
  `HS6_VOTE_K` constant, not a literal 5, so it follows the constant if k changes.
- A chosen candidate is always one of the model's candidates, so it already passed the nomenclature check
  (constitution Principle I). The override never introduces a code.
- `rank` is 1, 2 or 3. `vote.candidate` is set only when the majority equals the model's second or third candidate.
