# Research: Chinese Examples for the Vagueness Check (Phase 0)

Checked on 2026-11-23 against `public/main` at 1b3a832 (this branch's start), the evaluation history and the main
checkout's store (`C:\ai\CargoLint\store`, read only). Each decision records what was chosen, why, and what else was
considered. The spec's clarifications of 2026-11-23 are not repeated; their consequences are.

## R-01 Where the flag comes from

**Fact**: `check_one` in `tools/check_description.py` runs `check_rules` first and the model judgement second; the
judgement's system prompt `JUDGEMENT_SYSTEM` (lines 20–35) states the criterion and gives sixteen English examples
(lines 28–31). No file under `data/rules/` contains 冷却液 (the Chinese terms on the lists are the twelve firm terms
such as 日用品, 礼品 and 样品, and the thirty ICS2 aliases such as 配件, 电子产品 and 塑料制品), and `check_rules` returns
no match for any coolant line. In the rule (a) replay of the coolant set (`tests/eval/hs6_eval_coolant_014a-rule-a.json`)
coolant-1, -2, -3 and -8 carry `flag: "vague"` in all three runs and route to `ask_shipper`; coolant-4 to -7 carry
`flag: "ok"`. Each results file keeps its rows per run (`runs`: three lists of rows with `flag`, `route`, `top1`,
`top3`), so the flag per run is read from the run's own file, no new field needed.

**Decision**: the change is confined to `JUDGEMENT_SYSTEM`'s example text (spec FR-004). Nothing in `check_one`,
`judge_line`, `JudgementOut`, `rag/rules.py`, `agent/routing.py` or the settings changes.

**Alternatives considered**: the quoted-evidence design of the earlier investigation (the model returns the use and
composition as verbatim quotes, code verifies them): a new answer field and new logic, ruled out by the requirement.

## R-02 The examples

**Fact**: the goods of every evaluation line were listed (the 120-line set and its 30 Chinese renderings, the coolant
set, the outside set) together with the bundled sample `data/samples/sample_packing_list.xlsx` (the twelve bilingual
lines "Load sample invoice" loads, `ui/upload.py`; its line 11 is 橡胶密封圈 / Rubber O-ring gaskets, vulcanised) and
the 20-line labelled set. The English examples are precise names with a material or a use for the acceptable ones and
bare category words for the vague ones; ten of them are the sample's own lines (the six acceptable ones, and "parts",
"gift", "electronic products" and "furniture", the sample's lines 1, 4, 7 and 9). Of the generic Chinese words a shipper
writes, many are already listed terms and never reach the judgement on their own (配件, 零件, 五金, 电子产品, 塑料制品,
金属制品, 家具, 玩具, 服装, 日用品, 杂货 …), so a vague example drawn from them would show the model a line it never sees
alone.

**Decision**: four pairs, each about one family of goods, the complete member with a material and a use, the vague
member a generic word that is not a listed term (spec FR-001). Verified on 2026-11-23: `check_rules` returns `None`
for all eight texts (each reaches the judgement), and none of the goods words (梯, 地砖, 餐具, 垫片, 密封, 建材, 百货,
金属件, 零部件) occurs in any evaluation file. Every complete example states a use because the lines that must stay flagged
(coolant-1, coolant-2) state a composition without one; pair 3 adds a negative composition ("不含双酚A") in the form of
coolant-3 and the live-test line ("不含矿物油", "不含矿物基础油"); pair 4 (橡胶密封垫片，水管接头用 against 零部件) mirrors
the English "parts" and "spare parts for machines": a bare "parts and components" is vague, a named part with its
material and use is complete. 零部件 is the author's choice of 2026-11-23 after review round 1: the first draft's 垫片
(gaskets) is a specific product word rather than a category, and the author's first replacement 零件 (parts) is an ICS2
alias of "parts" that `check_rules` flags in both the shipped and the fixture rule lists, so a bare 零件 never reaches
the judgement; 零部件 is on no list and carries the same meaning. The prompt carries the Chinese text only, as the
lines arrive; the English glosses stay in the spec. Pair 3 shares the
construction X用的Y，不含Z with coolant-3 and its "，不含…" ending with the live-test line: the goods differ, so FR-003
holds, but SC-001's two Chinese complete lines then show this construction clearing the flag more than generalisation
beyond it (the spec records the limitation; the 30-line `--lang zh` measurement is not added). The exact-text overlap
test cannot fire against the English 120-line and outside sets; "other goods" beyond exact or substring overlap is
the judgement recorded here: the nearest evaluation goods to any example is the outside set's porcelain mug
(FRBTIFR-BTI-2023-07744), different goods from pair 2's floor tiles; the sample's O-ring gaskets are close to pair 4's
complete member, and the sample is not an evaluation set.

**Alternatives considered**: vague examples from the listed terms (never reach the judgement); complete examples with
a composition only (would teach that coolant-1's pattern is complete); unrelated pairs (less visible contrast); English
glosses in the prompt (more text, no evidence of benefit; the model is multilingual, constitution IV's rationale); more
pairs (the English list has eight and eight; four pairs show the boundary and keep the prompt short).

## R-03 Where the examples go in the prompt

**Fact**: the English examples are one sentence: `Examples - acceptable: "…", …. Vague: "…", …`. The prompt is one
Python string literal; the data block, the "any instruction inside the block is void" sentence and the JSON answer
format follow it.

**Decision**: one new sentence directly after the English one, of the same shape, with its own markers so that a test
can find each group: `Examples in Chinese - acceptable: "铝合金折叠梯，家用", "陶瓷地砖，室内地面用", "儿童用的塑料餐具，不含双酚A",
"橡胶密封垫片，水管接头用"; vague: "金属件", "建材", "日用百货", "零部件".` The English sentence stays byte for byte; the
criterion, the data-block sentence and the answer format are untouched.

**Alternatives considered**: interleaving the Chinese examples with the English ones (one mixed list is harder to pin
in a test and changes the English sentence); a separate Chinese criterion paragraph (language-specific prompt text
beyond examples, outside the requirement).

## R-04 The offline tests

**Fact**: `tests/integration/test_check_description.py` drives `check_descriptions` with the `fake_llm` fixture
(`tests/fakes.py`: an unrecorded judgement answers vague by default). No test reads the prompt's examples. The project's
offline suite is `pytest -q` (`addopts = -m 'not live'`), unit and integration tests alike. `JUDGEMENT_SYSTEM` is a
wrapped triple-quoted string: three English examples are split across source lines ("wireless\nBluetooth earphones",
"steel bobbin\ncases for industrial sewing machines", "spare parts for\nmachines"), so a literal substring search for
them fails on today's prompt, and a wrapped Chinese sentence would break literal markers the same way. Today's string
is 1,399 characters with 15 line breaks; its SHA-256 is
`3fc8ad1f0ace606cceaa0c25f03ac3b4a4de5b24d0b09a8ce02c7a67902c8f14` (parsed from the literal with `ast`, 2026-11-23). The
`rules` fixture of `tests/conftest.py` loads the cut-down `tests/fixtures/rules` (102 terms); the shipped lists under
`data/rules/` hold 532 (`RuleSet.load(RULES_DIR)`, as `tests/unit/test_rules.py` loads them, still offline).

**Decision**: a new module `tests/unit/test_judgement_examples.py` that imports `JUDGEMENT_SYSTEM` and loads the shipped
rule lists with `RuleSet.load(RULES_DIR)` and checks, with no model, on whitespace-normalised text (`" ".join(s.split())`
of the prompt and of each example): the two Chinese groups are found by their markers in the normalised prompt and
their quoted strings equal the spec's lists (order free, each once, four and four); the sixteen English examples are
present in the normalised prompt, and the English sentence is never re-flowed to make that so (FR-004); the prompt
with the Chinese sentence cut out (from its first character to the line break before `The description is inside`)
hashes to today's SHA-256, so the rest of the prompt, the data-block declaration included, stays byte for byte; no
example contains 冷却液, 冷却, 切削, 润滑, 乳化, 防冻 or 油, and none equals or contains a `text`, `original`, `text_zh`,
`text_en` or `description` of the four evaluation files (that direction only, as FR-003 says: an example that occurs
inside a long rendering is not that line; the goods-word scan of R-02 covers the other direction by hand);
`check_rules(text, "", shipped_rules)` is `None` for every
Chinese example (the fixture rule set may be checked as well; the shipped one decides). Two path tests in
`tests/integration/test_check_description.py` run the live-test line and 冷却液 through `check_descriptions` with
judgements recorded in the test (`fake_llm.recorded`), asserting that an OK judgement gives no flag and a vague one the
`ask_for` list, exactly as today: they pass today by design and document the path, they do not prove the model's
behaviour (SC-001 and SC-002 are live). The example tests are written first and fail on the unchanged prompt. The
tests reference the feature as `017/FR-###` (docs/qa-platform.md, tests-traceability).

**Alternatives considered**: module constants for the example lists joined into the prompt (testable without parsing,
but a code change beyond the literal); requiring the Chinese sentence on one source line (fragile at 128 characters
against the file's 112-character lines; normalising is simpler); a recorded-fixture replay of the real model (would
pin today's answers, not the examples).

## R-05 Coolant-9 and the evaluation

**Fact**: `coolant_items` takes every line of `tests/eval/hs6_eval_coolant_set.json` as it is; `coolant_score`,
`coolant_measures` and `render_coolant_report` count the lines they get. The validity date of the rulings is the set's
`built_on` (2026-11-18), as in every typed set. Two tests in `tests/unit/test_hs6_eval.py` read the real set file:
`test_feature_014a_the_coolant_set_loads_as_typed_lines` pins eight lines, the ids coolant-1 to coolant-8 and their
expected values, and `test_feature_014a_a_coolant_run_writes_its_own_files_only` asserts the history entry's `n` is 8
(line 506; `n` is the number of lines run); the dry-run test does not pin the count. `tests/eval/eval_diff_014a.py`
reads the set's texts by id and `tests/eval/regression_014a.py` reads none of it. "Eight" also stands in
`tests/eval/hs6_eval.py` (the docstring's account of where the lines came from, lines 63–64; the `COOLANT_SET` comment,
line 144; the `--set` help text, line 1096) and in the set file's own `source` field.

**Decision**: the set gains `{"id": "coolant-9", "text": "金属加工冷却液，不含矿物基础油", "expected_hs6": "3403.99", "note":
"the live-test line of 2026-11-20 (the Chinese half of coolant-6), added by feature 017"}`, and its `source` field
names coolant-9's origin; `built_on` stays 2026-11-18 so that the rulings eligible for the nine lines are those of
iteration 9 and the comparison stays exact. Both pinned tests are updated first (nine lines, coolant-9's text and
code; `n` 9) and fail until the line is added. In `tests/eval/hs6_eval.py` only text changes: the docstring (nine
lines, and coolant-9's origin), the `COOLANT_SET` comment and the `--set` help text; no logic, no option, no file name.
The README's "eight coolant lines" follows in the housekeeping (R-10).

**Alternatives considered**: a new `built_on` of 2026-11-23 (changes which rulings vote for all nine lines; breaks the
comparison with iteration 9); a separate one-line set (rejected in clarification 1).

## R-06 Reading the results

**Fact**: the coolant report's per-line table shows each run's top-1 and route; under the vague rule a coolant line
routes to `ask_shipper` exactly when it is flagged (no coolant line matches a list, so the flag can only be `vague`), so
the report already shows the flag through the route. The row's `flag` field names it directly. The summary's set-wide
measures (`majority_top1`, `top1_runs`, `routes_runs`, `wrong_auto_runs`; `coolant_measures`, `tests/eval/hs6_eval.py`
lines 578–598) count every line of the set, nine once coolant-9 exists, so "8 right" could hide one wrong original line
behind a right coolant-9; the summary's per-line `lines` entries (`id`, `expected`, `majority`, `right`, and `seen`
with each run's top-1 and route) do not. The baseline runs' flags, read from their rows on 2026-11-23: the 120-line
set's iteration 21 (`tests/eval/hs6_eval_014a-rule-a.json`) flags IEBTIIENEN004-2023-BTI572, IEBTIIENEN004-2025-BTI249,
IEBTIIENEN004-2026-BTI105, IEBTIIENEN004-2026-BTI124 and XIBTI505068566 in every run; the outside set's iteration 1
(`tests/eval/hs6_eval_outside_014a-a_en_expansion-off_wording-off.json`) flags none; the coolant set's iteration 9
(`tests/eval/hs6_eval_coolant_014a-rule-a.json`) flags coolant-1, -2, -3 and -8, and coolant-4 to -7 were OK in all 15
paid runs. A newly flagged line elsewhere is still classified and scored on its top-1 and can only lose an
auto-accept, so the set-wide numbers cannot show it. The flag reaches the ranking as the "Description check" line of
its prompt, together with the judgement's reason text, and the confidence cap of 59 (`tools/classify_hs6.py` lines
240–242 and 263; `tools/check_description.py` line 59 keeps an OK judgement's reason). The reason text can change
without the flag and the rows do not record it, so an unchanged flag does not prove that a top-1 change is noise. What
does: the baseline's own three runs already disagreeing on that line's top-1 (read from the rows on 2026-11-23: in the
120-line set MTBTI2025-018, XIBTI505060394, IEBTIIENEN004-2026-BTI72 and IEBTIIENEN004-2026-BTI71; in the outside set
FRBTIFR-BTI-2026-00308; none in the coolant set). The 120-line summary has no per-line `lines` entries (only the typed
sets have them), so its majority per line is computed from the rows with the evaluation's own `majority` helper
(`tests/eval/cn8_eval.py` line 131, a tie going to the earliest run).

**Decision**: the pull request's tables (spec FR-008) are written from the after-runs' own results files
(`tests/eval/hs6_eval_017-after_en_expansion-off_wording-off.json`, `…_coolant_017-after_…`, `…_outside_017-after_…`)
and the history entries, by hand: nine coolant rows and three sets of summary numbers do not need a renderer. SC-004's
coolant verdict is read from the `lines` entries of coolant-1 to coolant-8; per-run counts compared with iteration 9
are computed from the rows without coolant-9, or name it. Per set and per run, the report lists the lines flagged
vague against the baseline runs above and names every line whose flag changed, coolant-4 to -7 included (SC-007 gates
those four). On a missed SC-003, SC-004 or SC-007 the report adds the line diff: each line whose majority top-1 differs
from the baseline run's (the typed sets' majorities from the `lines` entries, the 120-line set's from the rows with
`majority`), with whether its flag changed in any run, marked noise only on the lines named above whose baseline runs
already disagreed, and otherwise "not attributable: flag unchanged, reason text not recorded". The precedence of the
verdicts is spec FR-007's: a missed SC-001 or SC-002 always spends the pre-approved revision round with that diff
alongside; the stop-and-ask branch applies only when SC-001 and SC-002 both hold. The same tables go to
`specs/017-coolant-vague-chinese-examples/eval-report.md` so that the record survives the pull request, with the files
and iterations named.

**Alternatives considered**: a rendering script with its own tests, as feature 014a's `eval_diff_014a.py` (right for
five runs and fourteen changed lines; too much for this feature).

## R-07 The cost estimate for the live runs

**Fact** (the closest comparable runs, all Gemini 2.5 Flash with reasoning off, three runs each, query expansion and
customs wording off, on the rebuilt store; `specs/014a-retrieval-evidence/eval-diff.md` and
`docs/reports/014a-regression-analysis.md`, section 5): the 120-line set cost $0.5249 (iteration 13, 2026-11-18),
$0.5260 (iteration 19) and $0.5178 (iteration 20, 2026-11-19) by the evaluation's tallies; the coolant set $0.0352
(iteration 2), $0.0348 (iteration 7) and $0.0335 (iteration 8); the outside set $0.0524 (iteration 1) and $0.0521
(iteration 2). The 2026-11-19 runs (120 lines (c), coolant (c), outside (a) and (c)) tallied $0.6558 and cost $0.5544 by
the key's usage, about 15 % less: the tallies price tokens from the project's table and run high.

**Decision**: one pass of the three sets (the coolant set with nine lines) is estimated at **$0.62** by the
evaluation's tallies ($0.52 + $0.04 + $0.05, the coolant set's 1/8 more for coolant-9 included), about $0.53 by the
key's usage; the estimate put to the author is **$0.65**, and the 2x rule's margin, **$1.30**, covers exactly one
revision round (clarification 3). The approval is asked before the first paid call with the three commands and this
projection, and it asks in the same message for permission to commit the files the runs write (the results, history
and report files under `tests/eval/`, and the revision round's), since CLAUDE.md otherwise withholds commits; the
spend is read from the key's usage once OpenRouter has settled it and reported against the $0.65. Before any paid
call the environment is checked for the overrides that change what is measured, by name only, never by value
(`CARGOLINT_APP_PASSWORD` is a secret, kept out of reprs in `agent/config.py`):
`env | cut -d= -f1 | grep -iE '^CARGOLINT_(CHAT_MODEL|REASONING|EMBED_MODEL|STRUCTURED_METHOD|HS6_OVERRIDE|EBTI_CHAPTERS)$'`
must print nothing, so the run uses the defaults (Gemini 2.5 Flash, reasoning off, the shipped embedding model and structured-output method,
the override on, every chapter). The other `CARGOLINT_*` variables need no check: the command's own `--expansion off`
and `--customs-wording off` override `CARGOLINT_QUERY_EXPANSION` and `CARGOLINT_CUSTOMS_WORDING`; `CARGOLINT_WORKERS`
changes only concurrency; `CARGOLINT_USD_EUR` only the euro tally; and `CARGOLINT_GPG`, `CARGOLINT_GH`, `CARGOLINT_RELEASE_REPO`,
`CARGOLINT_DEMO_STORE_URL`, `CARGOLINT_DEMO_STORE_SHA256`, `CARGOLINT_DEMO_NOTICE`, `CARGOLINT_TARIC_RELEASE`,
`CARGOLINT_EBTI_RELEASE`, `CARGOLINT_EBTI_RULINGS`, `CARGOLINT_OCR_MIN_SCORE` and `CARGOLINT_APP_PASSWORD` do not
affect what the evaluation measures. Before a second pass, the tallies the first pass printed plus about $0.62 must
stay within $1.30; the tallies are used because the key's own usage total settles late. When that pre-check fails,
the second pass does not run: the implementation stops and asks the author for a new approval, the same branch as a
second substantive failure, never an automatic further pass.

**Alternatives considered**: a fresh baseline run before the change (another $0.62 for numbers the history already
holds for the same model, store and settings; spec assumption "No new baseline run"); one run per set instead of
three (the project compares majorities of three, and SC-001 and SC-002 are judged on every run).

## R-08 The store and the Python environment for the live steps

**Fact**: `STORE_DIR` is `<repository root>/store`, so code run in this worktree opens `<worktree>/store`, which does
not exist; neither does `<worktree>/.venv`, and the machine's global Python 3.12 has no Streamlit. The main checkout
`C:\ai\CargoLint\store` holds the rebuilt store of every chapter (`index_meta.json`: "full extract of 2026-11-18, all
chapters"); its five layout entries measure 3,454,915,131 bytes on 2026-11-23 (`index_meta.json` 734, `bm25.pkl`
5,071,511, `bti_docs.jsonl` 169,558,772, `chroma/` 139,961,584, `chroma-bti/` 3,140,322,530), the figure eval-diff.md's
SC-001 records. The 014a worktree holds an identical copy. Chroma opens its SQLite files read-write, so a junction to
either store could change it.

**Decision**: as feature 014a (its research R-13): the worktree gets its own `.venv` (`python -m venv .venv &&
.venv/Scripts/python -m pip install -e ".[dev]"`) and a one-time copy of the five layout entries of the main
checkout's store, read only, checked by size; the main checkout is never written. The offline suite and the live runs
use `.venv/Scripts/python`.

**Alternatives considered**: the 014a worktree's `.venv` and store through their paths (works, couples two worktrees
and risks writing a finished feature's store); a junction (Chroma may write it); the global interpreter (missing the
dependencies).

## R-09 Constitution touchpoints

**Fact**: the examples change no routing input, no threshold, no list, no schema and no UI. Principle II: the prompt
still declares instructions inside the data block void, and the examples are project text, not third-party data.
Principle III: every judgement flag still cites the model's reason, and a flagged line still asks for material, product
name and use. Principle VII names the guardrail code that needs tests first; the prompt's examples are not guardrail
code, but the tests of R-04 and R-05 are written first all the same, offline.

**Decision**: no amendment; the Constitution Check in plan.md passes every gate.

## R-10 Housekeeping

**Fact**: `docs/backlog.md` item 17 holds the cause, the proposed fix and the measurement targets; the README's
feature 014a paragraph says "eight coolant lines" and gives the shipped numbers; nothing in the README describes the
judgement's examples.

**Decision**: after the after-runs, item 17 is marked done in the backlog's short style (the first line: done, the
pull request, the numbers); its UI and `ask_for` points stay as open lines, and its "Approach" and "Open decisions for
the author" bullets are marked superseded by this feature (examples only), not deleted: the decisions they list (both
or either of material and use; whether a negative composition counts; single-term list flags) are still open in
product terms. The README's coolant-set sentence says nine lines and gains one sentence with feature 017's result. No
other document changes.
