# Data Model: CN-8 and TARIC-10 Classification

This feature extends feature 001's line model ([001 data-model](../001-packing-list-check/data-model.md)) and reads
feature 003's TARIC snapshot through `lookup_taric` unchanged. Sections not named here are unchanged. Field patterns
follow constitution v1.2.0 Principle I:
- HS-6 codes stay `^\d{4}\.\d{2}$` (`CODE_PATTERN`, unchanged);
- CN-8 codes are `^\d{8}$`;
- TARIC-10 codes are `^\d{10}$`.

## 1. Shipment (001 §1), one field added

| Field | Type | Rule |
|---|---|---|
| taric_origin | string | the goods' country of origin for TARIC, `^[A-Z]{2}$` after upper-casing; `"CN"` by default (FR-017). Distinct from the existing `origin`, the route's origin port parsed from the invoice |

## 2. Candidate and Decision (001 §5), fields added

| Entity | Field | Type | Rule |
|---|---|---|---|
| Candidate | cn8 | string or null, `^\d{8}$` | the CN-8 chosen for this HS-6 candidate; only the decided HS-6 candidate carries one |
| Candidate | taric10 | string or null, `^\d{10}$` | the suggested TARIC subdivision, when one is highlighted (FR-009) |
| Decision | decided_cn8 | string or null, `^\d{8}$` | set only by the clerk's CN-8 confirmation; must be one of the decided HS-6's CN-8 lines (FR-002) |
| Decision | decided_taric10 | string or null, `^\d{10}$` | set only by the clerk's TARIC-10 confirmation; must be one of the snapshot's subdivisions for the written CN-8 (FR-012) |

`Decision`'s existing rule ("an accepted decision needs a decided_code") stays. A confirmation on an auto-accepted line
creates `Decision(route=accepted, decided_code=<the auto-decided HS-6>, chosen_how=auto)` with the confirmed code
(research R-09).

## 3. CN-8 Choice (new; `LineVersion.cn8`)

| Field | Type | Rule |
|---|---|---|
| hs6 | string, `CODE_PATTERN` | the decided HS-6 it was chosen under |
| options | list of (cn8, label path) | the CN 2026 CN-8 lines under `hs6`, in code order (research R-01) |
| cn8 | string or null, `^\d{8}$` | the chosen CN-8; must be in `options`; null when the deciding attribute is missing |
| confidence | int 0–100 | 100 for a single CN-8 line (no choice); otherwise the validated model estimate |
| evidence | string | the words of the line text that decide |
| rationale | string | one or two sentences a clerk can check |
| deciding_attribute | string | what separates the options, for example "material" |
| question | string or null | "Ask the shipper for: <deciding_attribute>" when the attribute is not visible; this is the routing input (§6) |
| precedent | Precedent or null | a valid EBTI ruling sent in this run whose code starts with `cn8` |
| written_by | `rule`, `clerk` or null | `rule` when `confidence` ≥ the shipment threshold (or a single line); `clerk` after a confirmation; null while it is a suggestion |
| error | string or null | why the step failed for this line: invalid output after one retry, or an API error. There is then no CN-8 and no question. The line routes to review with the error, as feature 001's failed status does (§6), and the clerk can still choose the CN-8 |

## 4. TARIC Outcome (new; `LineVersion.taric`)

| Field | Type | Rule |
|---|---|---|
| origin | string | the shipment's `taric_origin` used for the lookup |
| snapshot_date | date or null | from the loaded snapshot; null when none is loaded |
| rule | `auto_completed`, `choose`, `trade_defence`, `not_available`, `not_loaded` | exactly one, computed by `taric_rule` (research R-06) |
| subdivisions | list of string, `^\d{10}$` | the codes `lookup_taric` returned for the CN-8 and origin, in code order |
| trade_defence | list of string | the subdivisions whose measures include type 551, 552, 553, 554, 555 or 570 |
| suggestion | (code, confidence) or null | only for `choose`, only when the separating attribute is stated; never written (FR-009) |
| taric10 | string or null, `^\d{10}$` | the written code; one of `subdivisions` |
| written_by | `rule`, `clerk` or null | `rule` only for `auto_completed` with a written CN-8; `clerk` after a confirmation |
| question | string or null | what the clerk asked the shipper instead of confirming a subdivision (FR-009). The route comes from the clerk's ask-shipper decision (feature 001), not from this field |

Measures are not stored. Every display looks them up again with `lookup_taric(cn8, origin)`, so what the clerk sees
always equals the snapshot (FR-013, SC-004).

**Measure groups** (FR-014, research R-07), assigned by a fixed table on the measure type:

| Group | Measure types |
|---|---|
| duties | 103, 105, 106, 107, 112, 115, 117, 119, 122, 123, 141, 142, 143, 145, 146, 147, 488, 489, 490, 651, 652, 653, 654, 695, 696 |
| trade defence | 551, 552, 553, 554, 555, 561, 564, 565, 570 |
| requirements | every other type |

## 5. Audit records (001 §8), change kinds added

| Change kind | Recorded when | `note` carries |
|---|---|---|
| cn8_written | a CN-8 is written | "written by rule (confidence N ≥ threshold T)", "single CN-8 line" or "confirmed by the clerk"; the CN-8 |
| cn8_question | the deciding attribute is missing | "Ask the shipper for: <attribute>" |
| taric_written | a TARIC-10 is written | "auto-completed, single TARIC subdivision, snapshot <date>" or "confirmed by the clerk"; the origin |
| taric_pending | the rule leaves the TARIC-10 to the clerk | "several subdivisions" or "trade-defence measure <types>"; snapshot date and origin |
| taric_question | the clerk sends the line to the shipper instead of confirming a subdivision | "Ask the shipper for: <question>"; snapshot date and origin |
| taric_not_available | no subdivision, or no snapshot loaded | "TARIC not available" or "TARIC not loaded"; snapshot date and origin |

`actor` is `routing_rule` for rule outcomes and `clerk` for confirmations. Records stay append-only (Principle V).

## 6. Routing and the effective route (001 §9, changed)

**Routing** is `route_line(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor, cn8_question,
cn8_error)`. The two new inputs apply only to a checked line whose flag is OK and whose HS-6 is decided. A failed CN-8
step is passed like feature 001's failed status (Principle V):

| Condition | Route | Reason |
|---|---|---|
| `cn8_question` set | `ask_shipper` | "the CN-8 depends on <attribute>, which the description does not state — ask the shipper" |
| `cn8_error` set | `review` | "CN-8 step failed: <error> — needs a human look" |
| otherwise | as in feature 001 | unchanged |

**HS-6 decided**: the clerk has accepted an HS-6, or, with no clerk decision, `hs6_auto_decided(flag_kind,
top_confidence, status, ever_flagged, threshold, ask_floor)` is true. That helper is true exactly when `route_line`
without a CN-8 question or error returns `auto_accept`, the condition feature 001 auto-accepts on. It does not depend
on the CN-8 question or a CN-8 failure, so `decided_code()` and the HS-6 export columns keep their values (FR-021).

**Effective route** precedence:
1. an open CN-8 question gives the computed `ask_shipper`, and a failed CN-8 step the computed `review`, even over a
   clerk's HS-6 acceptance;
2. otherwise, as before: the clerk's decision, or the computed route. A clerk's review or ask-shipper choice therefore
   still applies while a CN-8 question is open or a CN-8 step has failed.

**Written codes are top-down**: the export and the counts read the CN-8 only while the line's HS-6 is decided, and the
TARIC-10 only while its CN-8 is. A clerk who sends a line to review or to the shipper empties its decided HS-6, as in
feature 001, and with it the CN-8 and TARIC-10 columns. The stored choices stay on the version, so accepting the same
HS-6 again brings them back.

**Pending confirmations** never change a route (clarifications Q1 and Q4). They are counted separately:
- `cn8_to_confirm`: lines with a decided HS-6 whose CN-8 is a suggestion: chosen but not written, with no open question and no failure;
- `taric_to_confirm`: lines with a written CN-8 whose rule is `choose` or `trade_defence`, whose TARIC-10 is not written,
  and which the clerk has not sent to the shipper.

## 7. State transitions (new)

```text
HS-6 decided ──► CN-8 step
   ├─ single CN-8 line ──────────────► CN-8 written (rule) ──► TARIC step
   ├─ attribute missing ─────────────► question open (route ask_shipper)
   │       └─ clerk chooses a CN-8 / shipper reply re-runs ─► CN-8 written (clerk) or a new choice
   ├─ confidence ≥ threshold ────────► CN-8 written (rule) ──► TARIC step
   ├─ confidence < threshold ────────► CN-8 to confirm ──clerk confirms──► CN-8 written (clerk) ──► TARIC step
   └─ step fails ────────────────────► review with the error ──clerk chooses a CN-8──► CN-8 written (clerk)

TARIC step (lookup for CN-8 and origin; no model call except the subdivision suggestion)
   ├─ not_loaded / not_available ────► stops at 8 digits (shown as such)
   ├─ auto_completed ── CN-8 written ► TARIC-10 written (rule) + audit text
   ├─ choose ────────────────────────► TARIC-10 to confirm ──clerk confirms──► written (clerk) | ask the shipper
   └─ trade_defence ─────────────────► TARIC-10 to confirm ──clerk confirms──► written (clerk) | ask the shipper

Threshold change  ─► unconfirmed CN-8 re-evaluated; a TARIC-10 written from a CN-8 that drops below is withdrawn
Origin change     ─► TARIC step again for every line with a CN-8; clerk-confirmed TARIC-10 codes stay
HS-6 changed      ─► new line version or decision: CN-8 and TARIC cleared, CN-8 step again
Sent to review or the shipper by the clerk ─► choices kept on the version; HS-6, CN-8 and TARIC-10 export columns empty
Shipper reply     ─► new version: check, classify, precedent; CN-8 and TARIC once the clerk accepts its HS-6
```

## 8. Export (001 export contract, columns added)

| Column (CSV, appended after `note`) | JSON (per line) | Value |
|---|---|---|
| `cn8` | `"cn8"` | the written CN-8 (by rule or clerk) while the HS-6 is decided (§6), else empty or null |
| `taric10` | `"taric10"` | the written TARIC-10 (auto-completed or clerk) while the CN-8 is written and decided, else empty or null |

Every existing column keeps its position and its value.

## 9. CN-8 Evaluation Set (new, evaluation only)

The set has 120 EBTI rulings, 10 from each of the 12 target chapters (research R-12), seeded and fixed before tuning. A
ruling is eligible when:
- it is valid;
- it sits under a subheading with at least two CN-8 lines;
- its `cn_code[:8]` is a CN 2026 line under its HS-6.

Each ruling is scored as follows:
- **Input**: its goods description is the line text and its HS-6 is the decided HS-6.
- **Leave-one-out**: its own reference is never a precedent.
- **Top-1**: the chosen CN-8, written or suggested. An ask-shipper outcome counts as a miss.
