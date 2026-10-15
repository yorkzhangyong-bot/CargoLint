# Contract: Streamlit UI

**Feature**: `001-packing-list-check` · **Spec**: [../spec.md](../spec.md) · **Design**: `CargoLint — MVP screens.html` (repo root) · **Constitution**: UI Design Contract (Principle VI)

Native Streamlit only — no custom HTML, CSS or JavaScript. Chips are Streamlit badge directives
(`:orange-badge[Vague]`), the review table is a Streamlit row list (decision in
[../research.md](../research.md) R-08: a `st.dataframe` with fixed pixel columns clips at laptop
widths, a proportional row list wraps instead). Every element below is a spec requirement; adding
elements is free, removing or relocating one needs a spec change.

## Layout

```
┌ sidebar (grouped) ──┬ main ───────────────────────────────────────────────────────┐
│ title + tagline     │ assistant rail (32 %)      │ review column (68 %)           │
│ ▸ Packing list      │ compact welcome / quick     │ header · filter pills          │
│ ▾ Shipment          │ actions, chat input, then   │ row list (needs-action first,  │
│ ▸ Rules             │ the turns newest first with │ paged 25, scrolls after 8)     │
│ ▸ Knowledge base    │ live progress, counts, …    │ detail card for the selection  │
│ tokens · cost       │                             │                                │
│ CSV · JSON          │                             │                                │
└─────────────────────┴─────────────────────────────┴────────────────────────────────┘
```

Screen 1 (start) shows the sidebar and a two-thirds-wide assistant column with the full welcome
message; the review column appears as soon as a shipment has lines — including mid-check, when the
parse step adds them (the live-progress fragment reruns the app when that happens).

## Sidebar

| Element | Widget | Spec | State / event |
|---|---|---|---|
| Title "CargoLint" + tagline | `st.markdown("## …")`, `st.caption` | — | |
| Packing list / invoice | `st.expander` (open until lines exist) → `st.file_uploader(type=[xlsx,csv,pdf,jpg,png])`, 20 MB via `server.maxUploadSize`; disabled while a turn runs | FR-002 | on change → if a shipment is open, store `pending_replacement` and show Replace / Cancel (US2-8); else `begin()` |
| Uploaded file chip | one-line `:material/description: name · size` (name middle-ellipsised, full name as tooltip) + icon-only tertiary remove button | US2 | remove → clears the chip only |
| Shipment: reference | `st.text_input` placeholder `HOL-2026-10-…` | FR-042 | |
| Shipment: shipper | `st.selectbox`: detected name (with past-shipment count), known shippers, "New shipper…" | FR-042, US2-7 | |
| Shipment: filing | `st.selectbox` with the single option "ICS2 house (ENS)" | FR-042 | ATLAS not offered |
| Rules: threshold | `st.expander` (open until lines exist) → `st.slider(60, 99, 85)` | FR-021 | on change → `LineStore.set_threshold` → routes refresh, no re-check |
| Rules: hybrid search | `st.toggle("Hybrid search", value=True)` | FR-018 | applies to the next classification |
| Knowledge base | collapsed `st.expander`: edition, lists, ruling count, updated date, model name | FR-019 | |
| Tokens / cost | two `st.metric`s pinned under a divider (always visible) | FR-040 | updated after every turn |
| Export | `CSV` and `JSON` `st.download_button`s beside the metrics | FR-041 | disabled until a shipment is checked |

## Assistant rail

| Element | Widget | Spec |
|---|---|---|
| Welcome | `st.chat_message("assistant")`: one paragraph + three quick-action cards (`st.container(border=True)`: title, hint, `Go`) + "What I can and cannot do" expander; collapses to a single caption once the shipment has lines | FR-026 |
| Clerk message | `st.chat_message("user")`; pasted lines summarised as `[N descriptions added as lines a–b]` with the raw text as a caption; file as `:material/attach_file: name` | US2 |
| Live progress (running turn) | `@st.fragment(run_every=0.7 s)` polling the background job: `st.status("Checking N lines · <tool>… · T s", state="running")` with one line per finished tool (`✓ tool — summary · s`, `(app)` when the completeness guard ran it) and a `done / N lines classified` bar | FR-027 |
| Finished progress | `st.status("N lines checked · K tools · T s", state="complete")`, collapsed, same step lines | FR-027 |
| Routing metrics | three `st.metric`s (file checks, or ≥ 3 pasted lines) | FR-028 |
| Lines that need you | bullet list from `LineStore`: line no, text, flag chip, what to ask / why | FR-028 |
| Assistant notes | model prose of a check turn inside a collapsed `st.expander` (the cards/counts are the structured summary); other turns inline; errors as `st.error` | FR-028 |
| Per-line result cards | pasted lines and shipper-reply updates: flag chip + rule, top-3 with confidence bar, precedent, route + reason; original zh/en unchanged; confidence caption | FR-012–FR-017 |
| Sources | `st.expander("Sources · N — Nomenclature n · BTI rulings n · …")` grouped by kind | FR-029 |
| Retrieval steps | `st.expander("Retrieval steps · line N")`: original, queries, filter, hits → fused → sent | FR-031 |
| Terms the customs reject | assistant message with a searchable `st.dataframe` of ICS2 terms and firm stop-words | FR-026 |
| Chat input | `st.chat_input` directly under the welcome and **above the history**, disabled while a turn runs; placeholder: start — "Paste descriptions (one per line) or ask a question…"; after — "Ask about any line, or paste the shipper's reply…" | FR-001, FR-036 |
| Turn order | newest turn first (a clerk message and the replies that follow it), chronological inside a turn; the running turn's live progress sits right under the chat input | FR-027 |
| Reply applied notice | "Applied to line N (selected)." prepended when the fallback was used; "Which line is this reply for?" when unresolved | FR-036, FR-037 |

Turns run in a worker thread (`ui/jobs.py`); the script thread only polls. The worker never calls
Streamlit; the UI reads everything from the `LineStore`.

## Review column

| Element | Widget | Spec |
|---|---|---|
| Header | `Review · <reference>` and `origin → destination · mode · N lines · needs-action first` (or `k still checking`) | FR-034 |
| Filters | `st.segmented_control`: All N · Needs action N · Accepted N (pending lines count in neither) | FR-034 |
| Row list | `@st.fragment(run_every=1 s while a turn runs)`; header captions + bordered `st.container` (scrolls at 420 px once more than 8 rows); one `st.columns` row per line: No., description (zh line / en line · qty), flag chip, `st.progress` with `code · conf %` (or `checking…` / `no code`), route chip, open button (primary for the selected line); needs-action rows first, then line order; 25 rows per page with a page pill row | FR-033, FR-024 |
| Selection | open button → `selected_line_no` → app rerun; the list follows the selection when the detail card's navigation changes it | FR-035, FR-036 fallback |

Chips: Flag `OK` grey, `Vague` orange, `Stop-word` red, `Failed` red; Route `Auto-accept` /
`Accepted` green, `Review` orange, `Ask shipper` blue (colours from the design canvas).

## Detail card (selected line)

| Element | Widget | Spec |
|---|---|---|
| Line header | `Line N · qty · weight · value` + `◀` / `Next ▶` buttons cycling through needs-action lines | FR-035 |
| Description | zh · en, flag chip, route chip, version badge `v2 · updated 12:58` | FR-035, FR-039 |
| Top-3 candidates | one row per candidate: mono code, subheading (tooltip for the full text), confidence bar; rationale caption; `BTI <state>` popover with reference, validity, description, reasoning, link, or "no precedent" | FR-035, FR-015 |
| Route control | `st.pills`: Human review · Ask the shipper; **Accept… popover disabled with the lock reason while flagged**; accepted lines show `Accepted · code` | FR-023, FR-022 |
| Decided code | inside the Accept… popover: `st.radio` over the top-3 (top preselected) + "Other HS-6 code…" `st.text_input`; typed code validated by `validate_code`, error inline; Confirm button | FR-023 (Q1) |
| Lock / ready message | "🔒 Below the 85% threshold and flagged …" / "Ready to accept — open Accept… to confirm the code" | FR-022 |
| Contradiction note | `st.warning` when present | FR-038 |
| Extracted facts | caption `material · part · use` after a shipper reply | FR-037 |
| Why it was flagged | `st.warning`: reason, rule + matched term, what to ask | FR-010, FR-011 |
| Updating this line | hint text with an example reply | FR-036 |
| Confidence caption | "Confidence is a model estimate, not a calibrated probability" | FR-017 |

## Theme

`.streamlit/config.toml`: `[theme]` light base, `primaryColor = "#1D4FB8"`, `baseFontSize = 14`,
`baseRadius = "medium"`, `borderColor`; `[theme.sidebar]` background and text colours;
`[client] toolbarMode = "minimal"`; Streamlit's bundled fonts plus the browser's CJK fallback so
Chinese renders (FR-032).

## Behavioural guarantees visible in the UI

- No route, count or code shown in the UI comes from model prose; all are read from the line store.
- Accept is never enabled for a flagged line; a previously flagged line shows "ready to accept"
  and still needs the click.
- Threshold changes never trigger model calls and never turn a computed route into a decision.
- Uploads and quick actions are disabled while a turn runs; one turn at a time per session.
- Secrets never appear in the UI; the KB caption never claims coverage the loader did not build.
