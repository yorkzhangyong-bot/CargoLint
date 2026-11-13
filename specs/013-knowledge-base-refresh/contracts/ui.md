# Contract: what the clerk sees

Native Streamlit only; no CSS change (constitution 1.10.0). Every text below is built in `ui/view.py` from the
knowledge base object, which reads its dates from `data/taric.jsonl`, `store/index_meta.json` and the release files.

## The Origin box (main page header, `ui/main_page.py::_header`)

Inside the right-hand sub-container, under the Origin caption:

| Element | Text | Rule |
|---|---|---|
| `st.caption` | `TARIC snapshot 2026-11-02 · EBTI rulings 2026-11-01` | `view.snapshot_caption(kb)`; "TARIC not loaded" replaces the first part when `kb.taric` is None; "EBTI rulings built 2026-10-16" when the store has no extract date; "EBTI rulings: date unknown" when it has neither |
| `st.warning` | `TARIC snapshot is 41 days old (limit 40 days).` | `view.freshness_warning(kb, today)`; shown only when it returns a text |
| | `EBTI rulings are 46 days old (limit 45 days).` | |
| | `TARIC snapshot is 41 days old (limit 40 days). EBTI rulings are 46 days old (limit 45 days).` | both old: one warning, TARIC first |
| | `EBTI rulings: age unknown (no date recorded).` | no date at all: neither an extract nor a build date |
| | `EBTI rulings: age unknown (recorded date 2027-01-01 cannot be used).` | an unparsable date, or one in the future, shown as recorded |

At exactly the limit there is no warning. The ages are whole days between `today` and the date.

## A TARIC release that could not be fetched (`app.py::main`)

| Element | Text | Rule |
|---|---|---|
| `st.error` above the page | `Knowledge base release: taric: taric-2026-11-02: the archive's SHA-256 is …, not …; taric-2026-10-01: the archive could not be downloaded: …` | one per entry of `kb.fetch_failures`, rendered on every run of the page; the Origin box then reads "TARIC not loaded" and the app works without TARIC as today |

An EBTI release that could not be fetched stops the app with the same message shape (`ebti: …`) and no page.

## Admin › Data (`ui/admin.py::_data`)

| Line | Text | Rule |
|---|---|---|
| EBTI rulings | `EBTI rulings: 5,000 · extract 2026-11-01 · full extract of 2026-11-01, chapters 39,42,61-64,73,84,85,94,95,96` | `view.rulings_statement(kb)`; `built 2026-10-16` in place of the extract part when the store has no extract date |
| TARIC | `TARIC snapshot: 2026-11-02 · 105 CN-8 mismatches · Swedish Customs Tariff File Distribution · batch e14b8e06-…` | `view.taric_statement(kb)` gains the batch id when present; "TARIC not loaded" unchanged |
| Releases | `Releases in use: ebti-2026-11-01 (fetched 2026-11-13), taric-2026-11-02 (fetched 2026-11-13)` | `view.release_statement(kb)`; only when at least one release file exists; a kind without one reads `local` |
| Model | unchanged | |
| Knowledge base | `view.kb_statement(kb)` unchanged in form; its `updated <date>` becomes the rulings' extract date when present | |
| Refresh (later) | unchanged, disabled | |

## Tests

- `tests/unit/test_view.py`: every text above on small fakes with chosen dates and `today`.
- `tests/ui/test_main_page.py`: the caption and the warning rendered in the Origin box (`at.warning`), on
  `harness.make_kb(meta=…, taric=…)` with a fixed `today` through `view.freshness_warning`'s parameter.
- `tests/ui/test_admin_page.py`: the Data lines, with and without release files.
- `tests/ui/test_app_navigation.py`: an EBTI fetch that fails stops the app with its message; a TARIC fetch that
  fails shows the `st.error` and opens the page with "TARIC not loaded".
- `tests/unit/test_native_ui.py`: unchanged and still green.
