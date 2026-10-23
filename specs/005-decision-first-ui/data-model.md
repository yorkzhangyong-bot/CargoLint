# Data Model: Decision-First Clerk Workflow (UI Redesign)

This feature stores nothing new about a line except the version the clerk's edit creates (§2). Everything the pages
show is derived from the line store on each render (§1), and a few session values hold the page state (§3). The line
model of features 001 to 004 is otherwise unchanged.

## 1. Derived view records (`ui/view.py`, `ui/shipper_email.py`, never stored)

### LineStatus

What the table shows for one line, computed by `line_status(store, line, activity)` (contracts/view.md §1).

| Field | Type | Rule |
|---|---|---|
| colour | `green`, `yellow`, `red` or `grey` | the first matching row of the mapping; grey while a job still covers the line's next step |
| text | string | "Ready", "Accepted", "Pick: …", "Confirm: …", "Ask: …", "Check failed", "Running {step}…", "Queued: {step}" or "Not checked yet" |
| action | `Choose`, `Update`, `Change` or none | Choose for yellow, Update for red, Change for green, none for grey |
| kind | `a_hs6`, `a_cn8`, `a_change`, `b`, `c`, `c_failed` or none | the expanded row it opens; `a_change` is kind (a) on a green line's decided codes |
| selectable | bool | Ready lines only: the Accept checkbox is enabled |
| lock_reason | string or null | red lines only: "Locked: {what blocks} — {what unlocks}" (FR-011); the Accept checkbox is shown disabled |
| question | string or null | red lines with a question: the full English question for kind (c) and the email |
| accepted | bool | green and confirmed by the clerk: the HS-6 accepted by the clerk, the CN-8 written by the clerk, and the TARIC-10 written by the clerk or not available |

### CodeDisplay

| Field | Type | Rule |
|---|---|---|
| text | string | "dddd dd dd dd" with the decided digits and underscores ("9503 00 __ __"); "dddd dd dd" when the line stops at 8 digits |
| note | string or null | "TARIC not available" or "TARIC not loaded" when the line stops at 8 digits |

Only codes the store returns as decided count: `decided_code`, `decided_cn8` and `decided_taric10`. A suggestion
never fills a digit.

### Summary

| Field | Type | Rule |
|---|---|---|
| lines | int | every line of the shipment |
| seconds | float | the summed time of the shipment's check runs that ran the description check (research R-10) |
| ready, pick, ask | int | green lines; yellow lines; red lines with a question |
| failed, running | int | "Check failed" lines; grey lines (shown only when above 0, research R-10) |
| to_accept | int | green lines not yet Accepted ("Accept all K ready") |

### Kind (a) and kind (b) rows

| Record | Fields |
|---|---|
| CandidateRow (kind a) | code (HS-6, its single CN-8 line, or a CN-8), description, confidence (0–100) or none, precedent or none ("no close precedent") |
| SubdivisionRow (kind b) | code, description, duty, anti_dumping ("{rate} % AD", a range, "AD: {specific duty}", "control" or "none"), has_trade_defence, suggested |

### EmailDraft

| Field | Type | Rule |
|---|---|---|
| lang | `en` or `zh` | the toggle |
| subject | string | the invoice id and the number of lines that need more detail |
| body | string | greeting, introduction, numbered questions, closing and sign-off placeholders, in the chosen language; only model-written questions may stay English |
| line_nos | list of int | the red lines with a question, in file order |
| text | string | the subject, a blank line and the body: what "Copy email" copies |

## 2. Backend addition: the version the clerk's edit creates (accepted on 2026-10-23)

| Element | Change |
|---|---|
| `CreatedBy` | gains `clerk` |
| `LineStore.update_description(line_no, text_zh, text_en) -> LineVersion` | adds a new current version created by the clerk; the earlier versions stay (append-only, Principle V); refuses an empty or over-cap text |
| Audit record | change `version_added`, actor `clerk`, previous = the replaced version's text, new = the new text, note "description updated by clerk" (or "re-checked by clerk, description unchanged") |
| `LineStore.add_version` | maps a version created by the clerk to the actor `clerk` and the record above; other versions keep today's record |
| Lock | unchanged rule: a line that was ever flagged, or a shipper-reply version, needs the clerk's click; a clerk version alone does not lock a never-flagged line |

The re-check that follows is an agent-level function, `recheck_line(store, kb, line_no)` (contracts/backend.md §2). It
writes only through the existing store methods.

## 3. Page state (session only)

| Key | Holds |
|---|---|
| `selected_line_no` | the open row's line number, or null; the Admin chat reads it as the selected line, as today |
| `accept_{line_no}` | the Accept checkbox of a Ready row |
| `pick_{line_no}_{version_no}_{kind}` | the code picked in an open row of kind (a) or (b) |
| `change_level_{line_no}_{version_no}` | the form "Change" shows on a green row: HS-6, CN-8 or TARIC-10 |
| `email_open`, `email_lang` | whether the email block is open, and EN or 中文 |
| `more_line_open` | whether the "+ Check one more line" field is shown |
| `origin_field` | the header's origin text: the shipment's `taric_origin`, or the origin the next shipment starts with |
| `job`, `job_queue` | the running background job and the waiting entries; job kinds `check`, `reply`, `question`, `finer_codes` and new `recheck` |
| `threshold`, `hybrid` | the Admin › Rules values; a new shipment starts with them, as today |
| `session_usage` | the session's tokens and cost from replaced shipments (Admin › Cost) |
| `chat` | the agent chat's messages, shown only on the Admin page |
| `admin_section` | the Admin page's current section |
| `uploaded_file`, `pending_replacement`, `last_upload_id` | today's upload state |

Nothing persists beyond the session (constitution, out of scope).
