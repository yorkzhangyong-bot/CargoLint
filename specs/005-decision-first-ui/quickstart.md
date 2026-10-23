# Quickstart: validating the decision-first clerk workflow

How to show that feature 005 works, offline first and then in the browser. Expected texts and behaviour are defined in
[contracts/ui.md](contracts/ui.md), [contracts/view.md](contracts/view.md) and
[contracts/backend.md](contracts/backend.md); this guide does not repeat them.

## Prerequisites

- Python 3.11–3.13 with the project's `.venv`, and `pip install -e ".[dev]"`. No new dependency.
- For the browser and the live runs:
  - the local knowledge base (`python -m rag.loader --demo`);
  - the TARIC snapshot (`python -m rag.loader --taric`), to see kind (b);
  - `OPENROUTER_API_KEY` in the environment.
- The offline tests need neither the key nor the knowledge base.

## 1. Offline tests

```bash
pytest -q
```

Expected:
- **The tests of features 001 to 004**: the 683 that do not import the UI package pass unchanged (SC-007).
- **The 27 UI-coupled tests**:
  - 13 in `tests/unit/test_review_table.py` and `tests/unit/test_sidebar_caption.py` are replaced;
  - 14 are kept and pass unchanged: `tests/adversarial/test_fencing_coverage.py`,
    `tests/integration/test_upload_flow.py` and `tests/unit/test_message_classification.py`.
- **The new tests pass**:

| File | Shows |
|---|---|
| `tests/unit/test_view.py` | every row of the Line status table, every short text and lock reason, code display, counts, split bar, kind (a) and (b) rows, origin toast, Markdown escaping (SC-003, SC-004) |
| `tests/unit/test_shipper_email.py` | both drafts for the sample: exactly the red lines, numbered; no English template text in the Chinese draft (SC-006) |
| `tests/unit/test_actions.py` | batch and selected acceptance: only Ready lines, each confirmed by the clerk |
| `tests/unit/test_store.py` (`TestClerkEdit`) | the clerk version, its audit record, the caps and the lock (contracts/backend.md §1) |
| `tests/integration/test_recheck.py` | the single-line re-check and its failures (contracts/backend.md §2) |
| `tests/ui/test_main_page.py` | the page, offline with `AppTest` and a seeded store: empty state, the three kinds, "Change" on a green row, batch accept, both emails, origin toast, underscore codes, the disabled Accept control on every kind of red row, nothing from FR-002 on the page |
| `tests/ui/test_admin_page.py` | the five sections; a threshold change re-routes unconfirmed lines only; the audit export |
| `tests/ui/test_app_navigation.py` | `app.py` with the loader patched: hidden navigation, the two page links, and the missing-key message without `.env` |
| `tests/ui/test_response_time.py` | each SC-002 action on the 12-line sample: under 1 s and zero model calls |

## 2. Scripted walkthrough (SC-001)

```bash
python -m tests.eval.walkthrough            # offline, with recorded model outputs
python -m tests.eval.walkthrough --live     # the real model; spends credits, run only when asked
```

The script drives the main page with `AppTest`, as a clerk would:
- open the sample;
- accept the ready lines;
- choose and confirm each yellow line;
- for each red line, copy the question, write the scripted answer and re-check;
- draft the email in both languages;
- export CSV and JSON.

It writes `tests/eval/walkthrough.json`: each action, its response time, the action count and the total time.
- **Pass**: the total stays under 300 s, and every non-check action stays under 1 s.
- **Report**: the evaluation report quotes the action count and the times.
- **Limit**: the script cannot measure a first-time clerk's reading time. The author's own timed run in the browser
  (§3) covers that.

## 3. In the browser

Restart the server before each check. The running server does not reload edits to `ui/*.py`.

```bash
streamlit run app.py        # http://localhost:8501
```

| Story | Do | See |
|---|---|---|
| US1 | Open the page | The header with the origin field at CN and "Admin ⚙"; the drop zone; "Try the sample invoice"; "Check one line"; the empty table. No sidebar. |
| US1 | Choose "Try the sample invoice" | Grey rows with their running step; codes filling in group by group; then the summary sentence, the split bar and "Accept all K ready". |
| US2 | "Choose" on a "Pick: N candidates" line | Kind (a) under the row: two explanation lines, three candidates with bars and precedent, the leader picked. "Confirm" returns at once; the row goes grey, then green or yellow "Pick: …". |
| US2 | "Change" on a green line | Kind (a) with the decided codes and who decided them, and the decided HS-6 picked. The switch offers CN-8, and TARIC-10 when the CN-8 has several subdivisions. "Confirm" stays disabled until another code is picked. Confirming a new HS-6 or CN-8 sends the row grey, then green or yellow; a new TARIC-10 keeps it green, with no model call. |
| US2 | "Choose" on a TARIC line | Kind (b): Duty and Anti-dumping columns, "All measures", "Open in EU TARIC ↗". "Confirm" turns the row green. |
| US3 | "Update" on a red line | Kind (c): the question with its copy button, the reason, the description field with the original in its help, and "Re-check line". The row shows its disabled Accept control and lock reason. |
| US3 | Edit the description and choose "Re-check line" | Only that row goes grey and comes back. Admin › Quality › "Export audit trail" lists "description updated by clerk". |
| US4 | "Accept all K ready", then "Export CSV" | The statuses read "Accepted". The CSV has the 23 columns of feature 004. |
| US5 | "Draft shipper email (C lines)", then 中文 | The text block under the table; the Chinese template text; the copy button copies all of it. |
| US6 | Set the origin to US | The toast "Origin US — TARIC rules re-applied to N lines, no model call". |
| US7 | "Admin ⚙" | Rules, Data, Cost, Quality and Ask the agent in the left navigation; "← Back to shipment" returns. |

Check by eye what `AppTest` cannot show:
- the copy buttons on the code blocks;
- the dot colours and the split bar;
- the Chinese glyphs;
- no sidebar on the main page;
- the layout against the wireframe screenshots.
