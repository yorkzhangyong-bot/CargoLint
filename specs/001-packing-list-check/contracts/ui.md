# Contract: Streamlit UI

**Feature**: `001-packing-list-check` · **Spec**: [../spec.md](../spec.md) · **Design**: `CargoLint — MVP screens.html` (repo root) · **Constitution**: UI Design Contract (Principle VI)

Native Streamlit only; custom HTML/CSS is limited to the flag/route chips if `st.dataframe`
cannot colour cells (decision recorded in [../research.md](../research.md)). Every element below
is a spec requirement; adding elements is free, removing or relocating one needs a spec change.

## Layout

```
┌ sidebar ───────────┬ main ───────────────────────────────────────────────────────┐
│ title + tagline    │  chat column (≈ 45 %)        │ review column (≈ 55 %)        │
│ uploader           │  messages, progress block,   │ header, filters, table,       │
│ shipment fields    │  metrics, sources, trace     │ detail panel for selection    │
│ rules              │  chat input                  │                               │
│ KB caption         │                              │                               │
│ tokens / cost      │                              │                               │
│ export             │                              │                               │
└────────────────────┴──────────────────────────────┴───────────────────────────────┘
```

Screen 1 (start) is the same layout with an empty review column hidden and the welcome message
in the chat column.

## Sidebar

| Element | Widget | Spec | State / event |
|---|---|---|---|
| Title "CargoLint" + tagline | `st.title`, `st.caption` | — | |
| Uploader | `st.file_uploader(type=[xlsx,csv,pdf,jpg,png])`, 20 MB via `server.maxUploadSize` | FR-002 | on change → if a shipment is open, store `pending_replacement` and show confirm/cancel (US2-8); else parse |
| Uploaded file chip | `st.caption` + remove button | US2 | remove → clears `pending_replacement` only |
| Shipment: reference | `st.text_input` placeholder `HOL-2026-10-…` | FR-042 | |
| Shipment: shipper | `st.selectbox` options: detected name (with past-shipment count), known shippers, "New shipper…" | FR-042, US2-7 | |
| Shipment: filing | `st.selectbox` with the single option "ICS2 house (ENS)" | FR-042 | ATLAS not offered |
| Rules: threshold | `st.slider(60, 99, 85)` | FR-021 | on change → `LineStore.set_threshold` → counts/table refresh, no re-check |
| Rules: hybrid search | `st.toggle("Hybrid search", value=True)` | FR-018 | applies to the next classification |
| KB caption | `st.caption` built from loaded data: edition, lists, ruling count, updated date | FR-019 | |
| Tokens / cost | `st.metric("Tokens this shipment")`, `st.metric("Cost")` in EUR | FR-040 | updated after every model call |
| Export | two `st.download_button`s (CSV, JSON) | FR-041 | disabled until a shipment is checked |

## Chat column

| Element | Widget | Spec |
|---|---|---|
| Welcome message with three quick actions | `st.chat_message("assistant")` + three `st.button`s | FR-026 |
| "What I can and cannot do" | `st.expander` under the welcome message | FR-026 |
| Clerk message with file chip | `st.chat_message("user")` | US2 |
| Progress block | `st.status("Checking…")` updated per tool event; final label `N lines checked · K tools · T s`; one line per tool with its summary | FR-027 |
| Routing metrics | three `st.metric`s: Auto-accept / Human review / Ask the shipper | FR-028 |
| Summary of lines needing action | assistant text, counts taken from `LineStore.counts()` | FR-028 |
| Per-line result cards (pasted lines only, ≤ 50) | one `st.container(border=True)` per line: flag chip + rule, top-3 with confidence bar, precedent or "no precedent found", route, what to ask; original zh/en text shown unchanged; confidence caption | FR-012–FR-017 |
| Sources | `st.expander("Sources · N")` listing `Source.title` per item | FR-029 |
| Retrieval steps | `st.expander("Retrieval steps")`: original, queries, filter, hits → fused → sent | FR-031 |
| Follow-up answers | assistant messages; only from stored results | FR-030 |
| Chat input | `st.chat_input` placeholder: start — "Paste descriptions (one per line) or ask a classification question…"; after check — "Ask about any line, or paste the shipper's reply…" | FR-001, FR-036 |
| Reply applied notice | assistant text "Applied to line N (selected)" when the fallback was used; question "Which line?" when `needs_line` | FR-036, FR-037 |

From US2 on, every line (pasted or uploaded) also appears in the review table; the cards remain
the chat-side summary for pasted lines.

## Review column

| Element | Widget | Spec |
|---|---|---|
| Header | `Review · <reference>` and `origin → destination · mode · N lines · needs-action first` | FR-034 |
| Filters | `st.pills` / `st.segmented_control`: All N · Needs action N · Accepted N | FR-034 |
| Table | `st.dataframe(..., on_select="rerun", selection_mode="single-row")`; columns `#`, Description as filed (zh / en · qty), Flag, HS-6, Confidence (`ProgressColumn` 0–100), Route; needs-action rows first, then line order | FR-033, FR-024 |
| Selection | selected row → `selected_line_no` | FR-035, FR-036 fallback |

Chips: Flag `OK` grey, `Vague` amber, `Stop-word` red; Route `Auto-accept` green, `Review`
amber, `Ask shipper` blue (colours from the design canvas). Rendered as text labels if cell
colouring is not available natively.

## Detail panel (selected line)

| Element | Widget | Spec |
|---|---|---|
| Line header | `Line N · qty · weight · value` | FR-035 |
| Description | zh · en, version badge `v2 · updated 12:58` | FR-035, FR-039 |
| Top-3 candidates | code, subheading text, confidence (bar), rationale, precedent reference/validity or "no precedent found" | FR-035, FR-015 |
| Route control | `st.radio` / `st.segmented_control`: Accept · Human review · Ask the shipper; **Accept disabled with reason while flagged** | FR-023, FR-022 |
| Decided code | shown when accepting: `st.radio` over the top-3 (top preselected) + `st.text_input("Other HS-6 code")`; typed code validated by `validate_code`, error shown inline; confirm button | FR-023 (Q1) |
| Lock / ready message | "Below the 85% threshold and flagged, so auto-accept is locked" / "Ready to accept — click Accept to confirm" | FR-022 |
| Contradiction note | `st.warning` when present | FR-038 |
| Why it was flagged | text: rule + what to ask | FR-010, FR-011 |
| Updating this line | hint text with example reply | FR-036 |
| Confidence caption | "Confidence is a model estimate, not a calibrated probability" | FR-017 |

## Theme

`.streamlit/config.toml` `[theme]`: `primaryColor = "#1D4FB8"`, light base, Source Sans 3 /
Source Code Pro (Streamlit defaults) and a CJK-capable fallback font so Chinese renders (FR-032).
Exact option names per [../research.md](../research.md).

## Behavioural guarantees visible in the UI

- No route, count or code shown in the UI comes from model prose; all are read from the line store.
- Accept is never enabled for a flagged line; a previously flagged line shows "ready to accept"
  and still needs the click.
- Threshold changes never trigger model calls.
- Secrets never appear in the UI; the KB caption never claims coverage the loader did not build.
