# Data Model: CargoLint MVP

**Feature**: `001-packing-list-check` · **Spec**: [spec.md](spec.md) · **Date**: 2026-10-14

All entities are plain Pydantic models (v2). In the MVP they live in `st.session_state` behind one
line-store module (constitution, Architecture invariants); nothing here assumes a database.
Field names are the canonical names used by the tools, the line store and the export.

## 1. Shipment

One checked packing list. Created on upload, on "use the sample", or on the first pasted
description; replaced (after confirmation) by the next upload.

| Field | Type | Rules |
|---|---|---|
| `id` | str (UUID) | session-unique |
| `reference` | str | clerk-entered, may be empty; shown in the table header |
| `shipper` | `ShipperRef` | `{name, known: bool, past_shipment_count: int}`; `known=False` → "New shipper" |
| `filing_type` | enum | `ics2_house_ens` only (ATLAS out of scope) |
| `threshold` | int | 60–99, default 85; the value in force for routing |
| `ask_floor` | int | 0–100, default 50; configuration, not a sidebar control |
| `hybrid_search` | bool | default `True`; `False` = baseline (vector-only) retrieval for comparison |
| `source` | `SourceFile \| None` | `{name, size_bytes, kind: xlsx\|csv\|pdf\|jpg\|png}`; `None` for pasted lines |
| `origin`, `destination`, `mode` | str \| None | header line "Shanghai → Hamburg · LCL"; from file if detectable, else blank |
| `created_at` | datetime | |
| `usage` | `Usage` | running totals, reset per shipment |
| `lines` | list[`Line`] | ≤ 200 (FR-006); ordered by `line_no` |
| `audit` | list[`DecisionRecord`] | append-only (FR-025) |
| `check_runs` | list[`CheckRun`] | one per "check" request: steps with one-line results, elapsed time |

## 2. Line

One item row. Identity is `line_no` (1-based position in the file, or order of pasting); unique
within a shipment. Versions are append-only; `current` is the last version.

| Field | Type | Rules |
|---|---|---|
| `line_no` | int | ≥ 1, unique per shipment |
| `source_ref` | str | e.g. `sheet "装箱单" row 7`, `page 2 row 3`, `pasted line 2` |
| `qty` | str \| None | as filed, e.g. `14 CTN` |
| `weight_kg`, `volume_cbm` | float \| None | optional columns |
| `value` | `Money \| None` | `{amount: Decimal, currency: str}` |
| `versions` | list[`LineVersion`] | ≥ 1, `version_no` consecutive from 1 |
| `ever_flagged` | bool (derived) | `any(v.flag.kind != "ok" for v in versions)` — drives the auto-accept lock (FR-022) |

Derived helpers (pure functions in the line store): `current`, `effective_route`
(= `decision.route` if a decision exists, else `computed_route`), `needs_action`
(= effective route ≠ accepted), `ready_to_accept` (= `ever_flagged` and current flag is `ok`
and top confidence ≥ threshold and no decision yet).

## 3. LineVersion

The state of a line after each update. v1 comes from the file/paste/sample; v2+ from shipper
replies (FR-036, FR-039).

| Field | Type | Rules |
|---|---|---|
| `version_no` | int | consecutive |
| `created_at` | datetime | |
| `created_by` | enum | `file \| paste \| sample \| shipper_reply` |
| `text_zh`, `text_en` | str | as filed; one may be empty; each ≤ 300 chars after truncation (FR-006) |
| `truncated` | bool | set when the cap was applied |
| `unreadable` | bool | OCR text below the confidence cut-off (FR-004) → `status=checked`, no candidates, route review |
| `reply_text` | str \| None | the pasted shipper reply (v2+ only), stored verbatim as data |
| `extracted` | `Extracted \| None` | `{material, part_name, use}` from the reply (FR-036); strings may be empty |
| `flag` | `Flag` | see §4 |
| `candidates` | list[`Candidate`] | 0–3, sorted by confidence desc; empty for pure stop-word, unreadable, failed, no-valid-candidate |
| `no_valid_candidate` | bool | all suggested codes failed the existence check (FR-013) |
| `precedents_checked` | bool | `lookup_precedent` ran for this version |
| `retrieval_trace` | `RetrievalTrace \| None` | see §7 |
| `sources` | list[`Source`] | everything cited in this version (FR-029) |
| `status` | enum | `pending \| checked \| failed` |
| `error_reason` | str \| None | plain-language, set when `failed` (FR-048) |
| `computed_route` | enum | `auto_accept \| review \| ask_shipper` — output of `route_line` (FR-020), never model-set |
| `route_reason` | str | e.g. `below threshold (72 < 85)`, `stop-word "gift"`, `ready to accept — click to confirm` |
| `decision` | `Decision \| None` | the clerk's choice, see §5 |
| `contradiction_note` | str \| None | set by the fixed chapter rule (FR-038), v2+ only |

## 4. Flag

| Field | Type | Rules |
|---|---|---|
| `kind` | enum | `ok \| vague \| stop_word` (FR-007) |
| `rule_source` | enum \| None | `firm_stop_words \| ics2_unacceptable \| ics2_stop_words \| judgement`; `None` when `ok` |
| `matched_term` | str \| None | the term that matched (FR-010) |
| `reason` | str | for `judgement`: what is missing (material, product name, use) |
| `ask_for` | list[str] | non-empty when flagged (FR-011): subset of `material`, `product_name`, `use`, plus free text |
| `pure_stop_word` | bool | no product information remains after removing stop-word terms → no candidates (FR-012) |

Precedence: firm stop-word match → `stop_word`; else a match in either ICS2 list (guidance unacceptable terms or Common Repository stop words) → `vague`; else judgement →
`vague` or `ok` (FR-008, FR-009). Rule matches are whole-term, case-insensitive, Chinese or English.

## 5. Candidate, Decision, Precedent

**Candidate** (FR-012 … FR-017)

| Field | Type | Rules |
|---|---|---|
| `code` | str | `^\d{4}\.\d{2}$` and present in the nomenclature index (FR-013, FR-044) |
| `subheading_text` | str | from the nomenclature chunk, not from the model |
| `chapter` | str | first two digits of `code`; used by the contradiction rule |
| `confidence` | int | 0–100 (FR-044); displayed as an estimate (FR-017) |
| `rationale` | str | model reasoning; must mention when support is history-only |
| `history_only` | bool | supported by shipper history, not by the description text (FR-016) |
| `source_ids` | list[str] | ids of `Source` entries backing this candidate |
| `precedent` | `Precedent \| None` | current BTI ruling for this code, if any (FR-015) |

**Decision** — recorded when the clerk acts in the route control (FR-023, clarification Q1)

| Field | Type | Rules |
|---|---|---|
| `route` | enum | `accepted \| review \| ask_shipper` |
| `decided_code` | str \| None | required when `route=accepted`; `^\d{4}\.\d{2}$`, must exist in the nomenclature |
| `chosen_how` | enum \| None | `top \| other_candidate \| typed`; `auto` is used for system auto-accept, never for a clerk decision |
| `by` | literal `clerk` | |
| `at` | datetime | |

Invariants: `route=accepted` is rejected while the current flag is not `ok` (FR-022/023). For an
auto-accepted line without a decision, the decided code is the top candidate with
`chosen_how=auto` (FR-020).

**Precedent** (one BTI ruling; FR-015)

| Field | Type | Rules |
|---|---|---|
| `reference` | str | e.g. `DEBTI…`; unique |
| `member_state` | str | ISO-2 |
| `code` | str | HS-6 of the ruling's CN code (first 6 digits) |
| `description`, `reasoning` | str | |
| `valid_from`, `valid_to` | date, date \| None | shown only if `valid_to` is `None` or ≥ today |
| `url` | str \| None | |

## 6. Source and RuleEntry

**Source** — anything cited in a result (FR-029). `id` is stable so a customs auditor can look it up.

| Field | Type | Values |
|---|---|---|
| `id` | str | `hs:9617.00`, `bti:DE1234/25`, `ics2:parts`, `ics2sw:gift`, `firm:gift` |
| `kind` | enum | `nomenclature \| bti \| ics2_rule \| firm_rule \| shipper_history` |
| `title` | str | e.g. `HS 2022 chapter 96, subheading 9617.00 — Vacuum flasks` |
| `excerpt` | str | ≤ 300 chars of the retrieved text |

**RuleEntry** — one term in a rule list (data files, loaded at start)

| Field | Type | Rules |
|---|---|---|
| `list` | enum | `ics2_unacceptable \| ics2_stop_words \| firm_stop_words` |
| `term` | str | lower-cased; Chinese terms matched as substrings on CJK runs, English as whole words |
| `lang` | enum | `zh \| en` |
| `source_doc`, `source_date` | str | shown in the knowledge-base caption (FR-019) |

## 7. Retrieval and knowledge-base records

**RetrievalTrace** (FR-031; one per `classify_hs6` call)

| Field | Type |
|---|---|
| `original` | str (text as sent, both languages) |
| `queries` | list[str] (translation + expansions, optionally one HyDE passage) |
| `chapter_filter` | list[str] \| None, with `filter_reason` (shipper history / consignee / none) |
| `bm25_hits`, `vector_hits` | int |
| `fused` | int (after RRF) |
| `sent_to_model` | int (chunks in the ranking prompt) |
| `precedent_codes` | list[str] (≤ 3 HS-6 codes proposed by matching BTI rulings, FR-051) |
| `precedent_chunks` | int (of those, chunks added that plain retrieval had not returned) |
| `mode` | `hybrid \| vector_only` |

**NomenclatureChunk** (Chroma document + BM25 entry; one per HS-6 subheading)

| Field | Type | Rules |
|---|---|---|
| `id` | str | `hs:####.##` |
| `text` | str | chapter title + heading text + subheading text + CN-8 lines beneath it |
| `metadata` | dict | `chapter`, `heading`, `subheading`, `language="en"`, `source`, `edition_year` |

**RulingChunk** (one per BTI ruling; embedding + metadata only — full text in the document store)

| Field | Type | Rules |
|---|---|---|
| `id` | str | `bti:<reference>` |
| `text` | str | goods description + reasoning (embedded) |
| `metadata` | dict | `code` (HS-6), `cn_code`, `member_state`, `valid_from`, `valid_to`, `chapter` |

**ShipperProfile** (synthetic demo data; no contact details — FR-046)

| Field | Type |
|---|---|
| `name`, `aliases` | str, list[str] (used to detect the shipper from file text) |
| `past_shipments` | list[`{reference, date, codes: list[str]}`] |

## 8. Usage, CheckRun, DecisionRecord

**Usage** (FR-040): `prompt_tokens`, `completion_tokens`, `total_tokens` (int), `cost_usd`,
`cost_eur` (Decimal; EUR = USD × configured rate), `calls` (int). Every model and embedding call
adds to the shipment total through the single client factory; a new shipment starts at zero.

**CheckRun** (FR-027): `started_at`, `elapsed_s`, `line_count`, `steps: list[{tool, summary,
started_at, elapsed_s, ok}]`, `tool_calls` (int). Rendered in the chat as the progress block.

**DecisionRecord** (FR-025; append-only audit)

| Field | Type | Values |
|---|---|---|
| `at` | datetime | |
| `line_no`, `version_no` | int | |
| `change` | enum | `route_computed \| threshold_recomputed \| clerk_decision \| code_decided \| reply_applied \| line_failed` |
| `previous`, `new` | str \| None | serialised values |
| `actor` | enum | `routing_rule \| threshold_change \| clerk \| shipper_reply \| system` |
| `note` | str \| None | rule or reason |

## 9. State transitions

**Line route** (effective route = decision ?? computed):

```
                 check complete            threshold slider            clerk route control
 pending ──────► computed_route ◄────────── recompute (only if ────────► decision {accepted|review|ask}
                  (route_line)              flag ok and no decision)      accepted requires flag ok;
                                                                          decided_code validated
       shipper reply ──► new LineVersion ──► re-check ──► route_line ──► if ever_flagged: max "review",
                                                                           route_reason = ready to accept
```

Rules enforced in code (`route_line`, FR-020; lock FR-022):

| flag | top confidence | status | computed_route |
|---|---|---|---|
| stop_word | any | checked | ask_shipper |
| vague | < ask_floor | checked | ask_shipper |
| vague | ≥ ask_floor | checked | review |
| ok | ≥ threshold, `ever_flagged=False` | checked | auto_accept |
| ok | ≥ threshold, `ever_flagged=True` | checked | review (`ready to accept`) |
| ok | < threshold | checked | review |
| any | — | no candidates / unreadable / failed | review |

**Line version**: `v1` (file/paste/sample) → `v2…` (one per applied reply). A reply to an
accepted line creates a new version and clears the decision (back to review). Versions are never
edited or deleted.

**Shipment**: `empty` → `parsed` (lines pending) → `checked` (every line checked or failed) →
replaced by the next upload after confirmation.

**Contradiction rule** (FR-038, pure function): given the previous version's candidates `P` and
the new top candidate `n`: contradiction iff `P` is non-empty and `n.chapter ∉ {c.chapter for c in P}`.
Sets `contradiction_note` = `"Reply moves the line from chapter 96 (9617.00) to chapter 39 (3924.10)"`.

## 10. Session-state layout (MVP persistence)

| Key | Holds |
|---|---|
| `shipment` | the `Shipment` (all lines, versions, audit, usage) |
| `chat` | list of chat messages `{role, content, check_run_id?, sources?, trace?}` |
| `selected_line_no` | int \| None — the review-table selection (reply fallback, FR-036) |
| `pending_replacement` | the uploaded file awaiting confirmation when a shipment is open (US2 scenario 8) |
| `settings` | `{threshold, hybrid_search}` mirrored from the sidebar widgets |

The line store exposes these through one module so the backing can later move to SQLite without
touching tools or UI (constitution, Architecture invariants).
