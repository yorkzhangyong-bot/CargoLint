# Contract: the backend addition

The author accepted one additive backend change on 2026-10-23: the line version the clerk's edit creates (FR-017,
FR-030). Nothing else in `agent/`, `tools/` or `rag/` changes behaviour. The routing, the threshold rule, the
flagged-line lock, the code checks, the TARIC write rules, the confirmations, the export and the command-line tools stay
as features 001 to 004 define them. Tests come first for every item below (Principle VII).

## 1. `CreatedBy.clerk` and `LineStore.update_description`

`agent/schemas.py`: `CreatedBy` gains `clerk = "clerk"`.

`agent/store.py`:

```python
def update_description(self, line_no: int, text_zh: str, text_en: str) -> LineVersion:
    """Feature 005 (FR-017): the clerk's edit of a line's description, as a new current version created by the clerk.
    The earlier versions stay (Principle V); `agent.recheck_line` checks the new one."""
```

- **Input**: the two texts are stripped.
  - Both empty: `ValueError("write the goods description")`.
  - Either longer than `MAX_DESC_CHARS`: `ValueError` naming the cap. The edit is untrusted text, capped like a file
    (Principle II).
  - An unknown line: `KeyError`, as `get_line` raises it.
- **Effect**: it appends `LineVersion(created_by=CreatedBy.clerk, text_zh, text_en)` through `add_version`, which
  numbers it, clears its decision and recomputes the route ("not checked yet"). The new version starts pending, with no
  flag, candidates, CN-8 or TARIC outcome.
- **Audit**: exactly one record for the edit.

  | Field | Value |
  |---|---|
  | change | `version_added` |
  | actor | `clerk` |
  | previous | the replaced version's display text |
  | new | the new version's display text |
  | note | "description updated by clerk", or "re-checked by clerk, description unchanged" when the text is the same |

  Then `_recompute` records its own route change as today.
- **`add_version`**: a version created by the clerk maps to the actor `clerk` and the record above. Versions created
  by a file, a paste, the sample or a shipper reply keep today's record, unchanged.
- **The lock is unchanged**: `_recompute` keeps "ever flagged, or a shipper-reply version". So:
  - a line that was ever flagged still needs the clerk's click after a re-check (Principle I);
  - a clerk version of a line never flagged is routed like a first check and may be auto-accepted.
- **The export**: `version_no` and `last_change` follow the new version, as for a reply. The columns and keys do not
  change (FR-019).

**Tests** (`tests/unit/test_store.py`, `TestClerkEdit`, written first):
- the new version, its number, its creator and its pending state;
- the audit record's fields, for both notes;
- the empty and the over-cap edit are refused, with no version and no record;
- an ever-flagged line edited to a clear text and checked at 95 % routes to `review` and is `ready_to_accept`, never
  `auto_accept`;
- a never-flagged line edited and checked at 95 % routes to `auto_accept`;
- today's `add_version` records for a reply are unchanged.

## 2. `agent.recheck_line`

`agent/agent.py`:

```python
def recheck_line(store: Any, kb: Any, line_no: int) -> str:
    """Feature 005 (FR-017): check one line's current version from the stop-word check onwards, with no agent turn,
    then run the CN-8 and TARIC steps when its HS-6 is decided. The same tool functions as `_finalize` and
    `apply_reply`; calls go through the usage-recording client. Returns a one-line summary."""
```

- **Precondition**: the current version is pending, as `update_description` leaves it. Otherwise it raises
  `ValueError` and changes nothing.
  - The UI's runner stores the edit right before it starts this job, never while another job runs
    (contracts/ui.md §6).
  - So a running check cannot classify the new version without its description check.
- **Client**: `get_client(usage_sink=store.add_usage, settings=get_settings())`, as `after_hs6_decision` uses, so the
  shipment's tokens and cost include the re-check.
- **Steps, for this line only**, as `apply_reply` does for a reply's version:
  1. `check_descriptions([text], kb.rules, client, workers=1)` → `store.update_check`;
  2. unless the check failed or found a pure stop word: `classify_lines([text], context_for_shipment(...), kb,
     client, workers=1)` → `store.update_classification`;
  3. when the version has candidates: `lookup_precedents(...)` → `store.update_precedents`;
  4. when `store.decided_code(line)` returns an HS-6: `run_cn8_step(store, kb, client, [line_no], workers=1)`;
  5. when `needs_taric(store, line)` returns a CN-8: `run_taric_step(store, kb, client, [line_no], workers=1)`.
- **Failures**: each step's own error handling fails the line with its reason (Principle V). If the version is still
  pending at the end, `store.mark_failed(line_no, "not checked — a step did not run")`.
- **Scope**: no other line, no check run and no chat record change. The model never chooses which steps run.
- **Return**: the summaries of the steps that ran, from each tool's `summarize`, joined with "; ".

**Tests** (`tests/integration/test_recheck.py`, written first, offline with `FakeRawClient` and a patched
`get_client`):
- **An ever-flagged line**: a line flagged by the ICS2 term "spare parts", edited to a clear description, is
  checked, classified and given precedents. It routes to `review` and its HS-6 is not decided, so no CN-8 step runs
  (Principle I).
- **A never-flagged line**: the open CN-8 question line, edited to state the attribute, is checked and classified.
  Its HS-6 is auto-decided, and the CN-8 and TARIC steps run.
- the other lines' versions, routes and audit records are untouched (single-line scope, as for `apply_shipper_reply`);
- a failing model call fails this line only, with its reason;
- an injected instruction in the edited text leaves the routing and schemas unaffected (Principle II, like the existing
  adversarial fixtures);
- the usage sink receives the calls;
- calling it on a line that is not pending raises and changes nothing.

## 3. Job kind `recheck` (`ui/jobs.py`)

- `Job.kind` gains `recheck`, with `line_no` set. The worker runs `job.note = recheck_line(store, kb, job.line_no)`
  and never calls Streamlit, as for `finer_codes`.
- `running_label`: "Re-checking line {n}… · {elapsed} s". `finish_label`: "Line {n} re-checked · {elapsed} s".
- **On an exception**: `job.error`, which the page turns into a failed line (contracts/ui.md §6).
- **Queued re-checks**: a re-check queued behind another job keeps the edited text in its queue entry. The runner
  calls `update_description` when the job starts.
- **The chat record**: a finished re-check adds one to the Admin chat, with the line's sources and retrieval steps.

## 4. What stays the same

- **`agent/routing.py`**: unchanged. No new route, rule or threshold.
- **The store's other methods**: unchanged. They include `set_decision`, `confirm_cn8`, `confirm_taric10`,
  `set_threshold`, `set_taric_origin`, the export and the `decided_*` and `*_pending` reads.
- **`agent.apply_taric_origin`, `after_hs6_decision` and `line_taric_view`**: unchanged.
- **The seven tools, the prompts, the system prompt and the CLI**: unchanged.
- **The 683 tests of features 001 to 004 that do not import the UI package**: they pass unchanged (SC-007).
