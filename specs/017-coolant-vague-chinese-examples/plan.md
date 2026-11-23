# Implementation Plan: Chinese Examples for the Vagueness Check

**Branch**: `017-coolant-vague-chinese-examples` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-coolant-vague-chinese-examples/spec.md`, with its clarifications of
2026-11-23 (coolant-9, flags judged on every run, one revision round). The facts behind each decision are in
[research.md](research.md).

## Summary

The vagueness judgement's prompt gains one sentence of Chinese examples; nothing else in the product changes.

- **The prompt** (`tools/check_description.py`, `JUDGEMENT_SYSTEM`): one new sentence after the English examples, of
  the same shape, with the four pairs of spec FR-001: acceptable 铝合金折叠梯，家用, 陶瓷地砖，室内地面用,
  儿童用的塑料餐具，不含双酚A, 橡胶密封垫片，水管接头用; vague 金属件, 建材, 日用百货, 零部件. The English sentence, the
  criterion, the data-block declaration and the answer format stay byte for byte (research R-02, R-03).
- **Tests first, offline** (spec FR-005): a new `tests/unit/test_judgement_examples.py` pins, on whitespace-normalised
  text, the two Chinese groups and the English examples (three of which are split across source lines today), pins
  the rest of the prompt byte for byte through a stored SHA-256 of today's string, and checks the coolant-word and
  evaluation-line exclusions and the rule check against the shipped rule lists (`RuleSet.load(RULES_DIR)`); two path
  tests in `tests/integration/test_check_description.py` run the live-test line and 冷却液 through the check with
  judgements recorded in the test (they pass today by design); the two coolant-set tests of
  `tests/unit/test_hs6_eval.py` are updated to nine lines (research R-04, R-05).
- **Coolant-9** (spec FR-006, clarification 1): `tests/eval/hs6_eval_coolant_set.json` gains the live-test line,
  expected 3403.99, and its `source` field names it; `built_on` stays 2026-11-18; in `tests/eval/hs6_eval.py` only the
  docstring, the `COOLANT_SET` comment and the `--set` help text change (research R-05).
- **The after-runs** (spec FR-006, FR-007): the 120-line, coolant and outside sets, three runs each, with the
  configured model and the evaluation's settings, after the author's approval of the $0.65 estimate (below) and with
  none of the six overrides T016 checks by name in the environment. The flags of coolant-1, -2, -3, -8 and -9 are read
  per run from the runs' own files; SC-004's coolant verdict from the summary's per-line entries of coolant-1 to -8;
  every set's vague flags per run are compared with the baseline runs (research R-06). A missed SC-001 or SC-002
  spends the one revision round, whatever SC-003, SC-004 and SC-007 show; with SC-001 and SC-002 holding, a missed
  SC-003, SC-004 or SC-007 stops with a line diff for the author (spec FR-007).
- **The record** (spec FR-008): `eval-report.md` in this folder and the pull request carry the comparison with the
  shipped numbers and the flag comparison; backlog item 17 is marked done, its superseded bullets marked, not
  deleted; the README's coolant-set sentence says nine lines (research R-10).

## Technical Context

**Language/Version**: Python 3.11–3.13 (a `.venv` in the feature worktree, see "Store and environment").

**Primary Dependencies**: no new package. The judgement runs through the OpenRouter client of `agent/llm.py`
(`StructuredCaller`, `JudgementOut`) with the configured chat model, Gemini 2.5 Flash with reasoning off; the
evaluation through `tests/eval/hs6_eval.py` as shipped.

**Storage**: unchanged. `tests/eval/hs6_eval_coolant_set.json` gains one line; the after-runs write their results,
history and report files under `tests/eval/` as every run does.

**Testing**: pytest, offline (`pytest -q`; live tests deselected). The new tests read the prompt string (parsed on
whitespace-normalised text, and hashed without the Chinese sentence), the shipped rule lists under `data/rules/`
(`RuleSet.load(RULES_DIR)`, as `tests/unit/test_rules.py` does) and the four evaluation files, and drive
`check_descriptions` with the `fake_llm` fixture; no test calls a model.

**Target Platform**: the author's laptop (Windows) for the live step; Streamlit Community Cloud runs the same prompt
unchanged otherwise.

**Project Type**: the existing single Streamlit project with its evaluation scripts.

**Performance Goals**: the judgement's system prompt grows by about 60 Chinese characters (about 100 tokens) per
call; no measurable change in time or cost per line.

**Constraints**: prompt examples only (spec FR-004); no stop-word, routing, rule (a), vague-rule or ASK_FLOOR change;
offline tests; the paid runs only after approval, estimate $0.65, 2x margin $1.30, one revision round at most.

**Scale/Scope**: one prompt string, one JSON line, three test files, one report, two documentation edits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Checked against constitution 1.11.0. No
amendment: no principle, guardrail or scope text is touched.

| Principle | Check | Status |
|---|---|---|
| I. Guardrails live in code | No routing input, threshold, gate, lock, code validation or schema changes. A vague flag still comes from the judgement and still routes to ask the shipper by code (the vague rule, feature 001's FR-020). The examples are prompt text, which this principle says is not an enforceable control: no guarantee is claimed for them; the after-runs measure their effect (SC-001 to SC-004), and the flagged-line lock and the vote decide routes as before. | Pass |
| II. Untrusted input | The line still reaches the judgement only inside `fence(...)`, and the prompt's declaration that instructions inside the data block are void is unchanged. The examples are project text outside the block, not third-party data. The prompt-injection fixtures of `tests/adversarial/` run unchanged. | Pass |
| III. Grounded, cited | Deterministic rules first and the judgement second, unchanged; every judgement flag still cites the model's reason, and a flagged line still asks for the material, the product name and the use. A complete Chinese line that now passes shows its candidates with their retrieved rulings, as an English one does. | Pass |
| IV. Hybrid retrieval | Untouched: no query, chunk, store or retrieval change. No language gets a path of its own: the examples sit in the one check every line goes through, and the judgement still reads the line as typed. | Pass |
| V. Typed tools | No tool added; `check_description`'s input and output schemas, `JudgementOut` included, are unchanged; `check_one` and `judge_line` are untouched and stay testable without a model. | Pass |
| VI. Native UI | No UI change. | Pass |
| VII. Test-first | The prompt's examples are not guardrail code, but the tests of spec FR-005 are written first and seen failing where they can fail (the Chinese-group tests on the unchanged prompt, the two coolant-set tests on the eight-line file); the English-examples, SHA-256 and path tests pass today by design and guard what must not change. All run offline. The after-runs are a separate, explicitly approved live step (FR-006, FR-007). | Pass |
| Architecture | Dependencies keep their direction (`ui` → `agent` → `tools` → `rag`); the change is inside `tools/`; the evaluation reads the tool as before. | Pass |
| Technology stack | No new package. | Pass |
| Out of scope for the MVP | Nothing is sent to a shipper or customs; no accounts; no persistence beyond the session. | Pass |

**Post-design re-check**: unchanged after Phase 1 ([data-model.md](data-model.md), [quickstart.md](quickstart.md); no
contracts, as no interface changes). The design adds no dependency, no tool, no routing input and no setting.

## Store and environment for the live steps

Research R-08: this worktree has no `store/` and no `.venv`, and the global Python has no Streamlit. As feature 014a:

- `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"` in the worktree (`.venv/` is git-ignored).
- A one-time copy of the five layout entries of the main checkout's store, read only:
  `mkdir -p store && cp -r /c/ai/CargoLint/store/{index_meta.json,bm25.pkl,bti_docs.jsonl,chroma,chroma-bti} store/`;
  `du -sb store` should read 3,454,915,131 bytes, the rebuilt store of every chapter (`index_meta.json`: "full extract
  of 2026-11-18, all chapters"). No junction (Chroma opens its SQLite files read-write). Nothing under
  `C:\ai\CargoLint` is written.
- `OPENROUTER_API_KEY` is an OS environment variable, never printed or written.

## Live evaluation: cost estimate and approval

Spec FR-007 and research R-07. The closest comparable runs are the 2026-11-18 and 19 runs of feature 014a on the
rebuilt store, Gemini 2.5 Flash with reasoning off, three runs each, query expansion and customs wording off
(`specs/014a-retrieval-evidence/eval-diff.md`; `docs/reports/014a-regression-analysis.md`, section 5):

| Set | Comparable runs (the evaluation's tallies) | This feature, one pass |
|---|---|---|
| 120-line, 3 runs | iteration 20 (2026-11-19) $0.5178; iteration 13 $0.5249; iteration 19 $0.5260 | $0.52 |
| coolant, 3 runs, 9 lines | iteration 8 $0.0335 and iteration 2 $0.0352 for 8 lines, times 9/8 | $0.04 |
| outside, 3 runs | iteration 1 $0.0524; iteration 2 $0.0521 | $0.05 |
| **One pass** | the four runs of 2026-11-19 tallied $0.6558 and cost $0.5544 by the key's usage | **$0.62** by the tallies, about $0.53 by the key's usage |

- **Estimate put to the author: $0.65** for one pass of the three commands of quickstart.md §3. The 2x rule's margin,
  **$1.30**, covers exactly one revision round (clarification 3); a third pass, or a second pass that the budget
  pre-check below rejects, needs a new approval from the author, and neither runs automatically.
- **Procedure**: the implementation asks the author, through the coordinator, before the first paid call, with the three
  commands and this table, and asks in the same message for permission to commit the files the runs write (the
  results, history and report files under `tests/eval/`, and a revision round's); nothing paid runs before the answer,
  and without that permission the tree stays uncommitted. Before any paid call the environment is checked for the
  overrides that change what is measured, by variable name only, never by value (`CARGOLINT_APP_PASSWORD` is a secret,
  kept out of reprs in `agent/config.py`):
  `env | cut -d= -f1 | grep -iE '^CARGOLINT_(CHAT_MODEL|REASONING|EMBED_MODEL|STRUCTURED_METHOD|HS6_OVERRIDE|EBTI_CHAPTERS)$'`
  must print nothing, so the run uses the defaults (Gemini 2.5 Flash, reasoning off, the shipped embedding model and structured-output
  method, the override on, every chapter). The other `CARGOLINT_*` variables need no check: the command's own
  `--expansion off` and `--customs-wording off` override `CARGOLINT_QUERY_EXPANSION` and `CARGOLINT_CUSTOMS_WORDING`;
  `CARGOLINT_WORKERS` changes only concurrency; `CARGOLINT_USD_EUR` only the euro tally; and `CARGOLINT_GPG`,
  `CARGOLINT_GH`, `CARGOLINT_RELEASE_REPO`, `CARGOLINT_DEMO_STORE_URL`, `CARGOLINT_DEMO_STORE_SHA256`,
  `CARGOLINT_DEMO_NOTICE`, `CARGOLINT_TARIC_RELEASE`, `CARGOLINT_EBTI_RELEASE`, `CARGOLINT_EBTI_RULINGS`,
  `CARGOLINT_OCR_MIN_SCORE` and `CARGOLINT_APP_PASSWORD` do not affect what the evaluation measures. Before a second
  pass, the tallies the first pass printed plus about $0.62 must stay within the $1.30 cap (the key's own usage total
  settles late); when they do not, the second pass does not run, and the implementation stops and asks the author for
  a new approval, the same branch as a second substantive failure. After the runs, the spend is read
  from the key's usage once OpenRouter has settled it and reported against the $0.65 in `eval-report.md` and the pull
  request, with the approval and its amount (as feature 014a's pull request did).
- **Reading the results**: the flags and routes per run of coolant-1, -2, -3, -8 and -9 from the coolant run's own
  file (quickstart.md §3); SC-004's coolant verdict from the summary's per-line `lines` entries of coolant-1 to
  coolant-8 (`id`, `majority`, `right`), never from the set-wide counts, which include coolant-9; per-run counts
  compared with iteration 9 computed from the rows without coolant-9, or naming it; the summaries' majority top-1,
  top-1 per run, auto-accepted and wrong auto-accepted per run for the three sets, the override off and from the `on`
  block; per set and per run the lines flagged vague against the baseline runs (120-line iteration 21: five named
  lines in every run; outside iteration 1: none; coolant iteration 9: coolant-1, -2, -3, -8), naming every line whose
  flag changed, coolant-4 to -7 included (SC-007). No model call and no new script (research R-06).
- **Precedence of the verdicts** (clarification 3 read as given: the pre-approved revision round covers Acceptance 1
  and 2, SC-001 and SC-002, and nothing else): a missed SC-001 or SC-002 always spends the pre-approved revision round,
  whatever the state of SC-003, SC-004 and SC-007, and the report carries the SC-003/SC-004 line diff alongside it so
  that the author sees both; the stop-and-ask branch (the line diff, then the author decides whether to spend the
  round or stop) applies only when SC-001 and SC-002 both hold and SC-003, SC-004 or SC-007 misses, SC-007 alone
  included; a missed SC-007 never spends the round by itself (spec FR-007). Nothing is re-run on the stop-and-ask
  branch before the author's answer.
- **The line diff**: each line whose majority top-1 differs from the baseline run's (the typed sets' majorities from
  the summary's `lines` entries; the 120-line set's computed from the rows with the evaluation's own `majority`
  helper, `tests/eval/cn8_eval.py` line 131, a tie going to the earliest run) and whether its vague flag changed in
  any run. A top-1 change counts as run-to-run noise only on a line whose three baseline runs already disagreed among
  themselves (120-line set: MTBTI2025-018, XIBTI505060394, IEBTIIENEN004-2026-BTI72, IEBTIIENEN004-2026-BTI71; outside
  set: FRBTIFR-BTI-2026-00308; none in the coolant set). Any other top-1 change on a line whose flag did not change is
  reported as "not attributable: flag unchanged, reason text not recorded": an OK judgement's reason text reaches the
  ranking prompt with the flag (`tools/classify_hs6.py` lines 240–242; `tools/check_description.py` line 59) and can
  change without it, and the rows do not record it (research R-06).

## Project Structure

### Documentation (this feature)

```text
specs/017-coolant-vague-chinese-examples/
├── spec.md                  # the specification, with its clarifications of 2026-11-23
├── plan.md                  # this file
├── research.md              # Phase 0: R-01 to R-10
├── data-model.md            # Phase 1: the example pair, coolant-9, the evaluation rows read
├── quickstart.md            # Phase 1: the offline suite, the live step, the record
├── checklists/requirements.md
├── tasks.md                 # /speckit-tasks
├── traceability.md          # the requirements no offline test can check (FR-006 to FR-008, SC-001 to SC-004, SC-006, SC-007)
└── eval-report.md           # after the after-runs: the tables of FR-008
```

No `contracts/`: the tool's schemas, the evaluation's command line and the UI are unchanged.

### Source Code (repository root)

```text
tools/check_description.py                     # JUDGEMENT_SYSTEM: one new sentence (research R-03); nothing else
tests/unit/test_judgement_examples.py          # new: the examples and the rest of the prompt pinned offline (research R-04)
tests/integration/test_check_description.py    # two path tests with judgements recorded in the test (research R-04)
tests/unit/test_hs6_eval.py                    # the two coolant-set tests: nine lines, coolant-9, n 9 (research R-05)
tests/eval/hs6_eval_coolant_set.json           # coolant-9 and its source field (data-model.md §2)
tests/eval/hs6_eval.py                         # text only: the docstring, the COOLANT_SET comment, the --set help ("nine")
tests/eval/hs6_eval*.json, *_history.json, *.md  # written by the after-runs (kept, as every run's are)
docs/backlog.md, README.md                     # housekeeping (research R-10)
```

**Structure Decision**: the existing layout; no new module outside `tests/`. Every file above is LF in this worktree
(`git ls-files --eol`, 2026-11-23); new files are UTF-8 without a byte-order mark, LF.

## Order of the work

1. Environment (§ "Store and environment"); the offline suite green on the unchanged branch.
2. Tests first: `tests/unit/test_judgement_examples.py` (the groups, the English examples, the SHA-256 of the rest),
   the two nine-line coolant-set tests, seen failing; the two path tests, which pass today by design.
3. The prompt sentence and coolant-9; the suite green; `scripts/check_spec.py` and `scripts/check_traceability.py`
   clean (`traceability.md` for the live requirements).
4. The approval of the $0.65 estimate with the commit permission; the environment check; then the three after-runs
   (quickstart.md §3); the results read; a missed SC-001 or SC-002 spends the one revision round; with SC-001 and
   SC-002 holding, a missed SC-003, SC-004 or SC-007 goes to the author with the line diff before anything is re-run;
   at most one revision round, within the $1.30 cap.
5. `eval-report.md`, backlog item 17, the README sentence; the pull request with the tables, the approval and both
   traceability lines.

## Complexity Tracking

None: no Constitution Check gate is violated, and no exception is taken.
