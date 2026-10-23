# Contract: UI changes for CN-8 and TARIC-10

Changes feature 001's [ui.md](../../001-packing-list-check/contracts/ui.md). The UI stays native Streamlit
(Principle VI): no custom HTML, CSS or JavaScript. Nothing listed in the constitution's UI design contract is removed or
moved. The files `ui/chat.py`, `ui/detail.py` and `ui/review.py` are CRLF and keep their line endings.

## Sidebar: Shipment expander (`ui/sidebar.py`)

| Element | Behaviour |
|---|---|
| "Origin (TARIC)" text input, 2 characters | defaults to `CN`; on change calls the agent's `apply_taric_origin`; a value that is not two letters shows an error and keeps the previous origin (FR-017, FR-018) |

## Routing counts (`ui/chat.py`, `_render_counts`)

After the three route metrics (Auto-accept, Human review, Ask the shipper), two metrics labelled as confirmations
follow: "CN-8 to confirm" and "TARIC-10 to confirm". They never change the route counts (clarifications Q1 and Q4).

## Review table (`ui/review.py`)

The columns are unchanged. A line waiting for a confirmation shows a badge in its route cell: `CN-8 to confirm` or
`TARIC-10 to confirm`. A line whose route is ask-shipper because of an open CN-8 question shows that route, with its
reason in the detail card. The "Needs action" filter stays route-based.

## Detail card (`ui/detail.py`): new section "CN-8 and TARIC-10"

The section sits under the route control. It is shown once the line's current version has a CN-8 step result; before
that it reads "Decide the HS-6 first."

**CN-8**:
- the code (spaced as `7318 15 58`) with its label path from CN 2026;
- a confidence bar with the caption "model estimate";
- the evidence as a caption;
- the EBTI ruling in a popover: reference, member state, validity, description, "Open ruling".
- **State**, exactly one of:
  - **written**: "Written by rule (confidence N ≥ T)", "Single CN-8 line" or "Confirmed by you";
  - **to confirm**: a radio of all CN-8 lines with the chosen one preselected, and a "Confirm CN-8" button;
  - **question open**: the warning "Ask the shipper for: <attribute>", plus the same radio and button for the clerk who knows the answer.

**TARIC-10**, once a CN-8 exists:
- **Caption**: "TARIC snapshot <date> · origin <code>", or "TARIC not loaded".
- **Rule note**:
  - "Auto-completed: single TARIC subdivision";
  - "Choose a subdivision";
  - "Trade-defence measures: confirm the subdivision";
  - "TARIC not available — the line stops at 8 digits".
- **One expander per subdivision**, holding:
  - its code and description;
  - a "Suggested · N %" badge on the highlighted one;
  - a "Trade defence" badge where types 551–555 or 570 apply;
  - three tables, Duties, Trade defence and Requirements. Each row shows type label, area code and name, additional code (trade defence only), duty text and regulation reference. They are `st.dataframe` tables of fixed height, because a group can be long: each subdivision of 7318 15 58 has about 94 anti-dumping rows for China, one per additional code.
- **Controls** when the rule leaves the code to the clerk:
  - a radio of the subdivisions and a "Confirm TARIC-10" button;
  - an "Ask the shipper" action: a text input for what to ask, prefilled from the subdivision descriptions, and a button that calls `ask_shipper_for_taric`. Afterwards the card shows "Sent to the shipper: <question>".
- **Guardrails shown** (Principle VI): "Confirm CN-8" and "Confirm TARIC-10" are disabled, with the reason, while the HS-6 is not decided; "Confirm TARIC-10" also while the CN-8 is not written.
- **Links** for the chosen or suggested 10-digit code:
  - a link button "EU TARIC" to the consultation page for the code, origin and snapshot date;
  - a link button "EZT-online" to the start page;
  - the code and origin in a copyable code block.

The measures shown come from `taric_view` over `lookup_taric`'s output: no measure is added, dropped or altered, and
each appears in exactly one group (FR-013, FR-014). Conditional duty text is shown as text.

## "What I can and cannot do" panel (`ui/chat.py`)

The text stays true to Principles I to III (Principle VI):
- **Can** gains: choose the CN-8 under a decided HS-6, and show the TARIC subdivisions and measures from the loaded snapshot.
- **Cannot** gains: write a TARIC subdivision without your confirmation, except a single one without trade-defence measures; calculate duties.

## Progress

The CN-8 and TARIC steps appear in the check's `st.status` like the other tools. Steps run by the app are labelled as
such. After the clerk accepts an HS-6, a caption "Choosing the CN-8…" shows while the background job runs.
