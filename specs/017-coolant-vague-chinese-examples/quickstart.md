# Quickstart: validating feature 017

Two kinds of checks: the offline suite, which anyone can run without a key, and the live after-runs, which spend
OpenRouter credits and run only after the author's approval (spec FR-007). Paths are relative to the feature worktree
`C:\Users\Yong\orca\workspaces\CargoLint\017-coolant-vague-chinese-examples`; the store and environment are plan.md's
"Store and environment for the live steps".

## 1. Environment (once)

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"     # Python 3.11-3.13; .venv is git-ignored
mkdir -p store && cp -r /c/ai/CargoLint/store/{index_meta.json,bm25.pkl,bti_docs.jsonl,chroma,chroma-bti} store/
du -sb store      # expected 3,454,915,131 bytes (the rebuilt store of every chapter, extract of 2026-11-18)
```

The main checkout is read only; nothing under `C:\ai\CargoLint` is written. For the live step, `OPENROUTER_API_KEY` is
an OS environment variable (never printed, never in a file).

## 2. Offline suite (every step of the implementation)

```bash
.venv/Scripts/python -m pytest -q                                   # live tests are deselected; no key, no network
.venv/Scripts/python -m pytest -q tests/unit/test_judgement_examples.py tests/integration/test_check_description.py tests/unit/test_hs6_eval.py
.venv/Scripts/python scripts/check_spec.py specs/017-coolant-vague-chinese-examples
.venv/Scripts/python scripts/check_traceability.py                  # tests-traceability of feature 017 on this branch
```

Expected: green, with the new tests in it (spec FR-005, SC-005), all matching on whitespace-normalised text because
the prompt is a wrapped source string: the Chinese example groups found in the prompt and equal to the spec's lists,
the sixteen English examples present (three are split across source lines today; the sentence is never re-flowed),
the prompt without the Chinese sentence hashing to today's SHA-256
(`3fc8ad1f0ace606cceaa0c25f03ac3b4a4de5b24d0b09a8ce02c7a67902c8f14`), no example a coolant word or an evaluation line,
every example passing the rule check against the shipped lists under `data/rules/`, the coolant set loading and
running nine lines with coolant-9 as the live-test line. Written first, the Chinese-group tests (T004's
acceptable-group test, T010, T011) and the two coolant-set tests (T005, T006) fail on the unchanged prompt and set
file; T004's English-examples and SHA-256 tests and the two path tests of `test_check_description.py` pass today by
design and guard what must not change.

## 3. Live step: the after-runs (after the author's approval of the $0.65 estimate, cap $1.30)

Prerequisites: the approval of tasks T015 (the estimate and the commit permission); the prompt change, coolant-9 and
the tests in the working tree (committed if the approval allowed it); `git status` showing nothing else changed
outside `specs/`; the store copy of §1 in place; none of the six overrides that change what is measured in the
environment, checked by variable name only, never by value (`CARGOLINT_APP_PASSWORD` is a secret):

```bash
env | cut -d= -f1 | grep -iE '^CARGOLINT_(CHAT_MODEL|REASONING|EMBED_MODEL|STRUCTURED_METHOD|HS6_OVERRIDE|EBTI_CHAPTERS)$'   # must print nothing
curl -s https://openrouter.ai/api/v1/key -H "Authorization: Bearer $OPENROUTER_API_KEY" | .venv/Scripts/python -c "import json, sys; print(json.load(sys.stdin)['data']['usage'])"   # the key's usage (USD) before the first paid call; the key only in the header, never printed
.venv/Scripts/python tests/eval/hs6_eval.py --set coolant --repeat 3 --tag 017-after --expansion off --customs-wording off   # stage 1
.venv/Scripts/python tests/eval/hs6_eval.py --set outside --repeat 3 --tag 017-after --expansion off --customs-wording off   # stage 2, only when stage 1 held
.venv/Scripts/python tests/eval/hs6_eval.py --repeat 3 --tag 017-after --expansion off --customs-wording off                 # stage 3, only when stage 2 held
```

The stages are the author's approval of 2026-11-23 (spec clarification 5): read each stage's results before the next
with the snippet below; the outside set runs only when every coolant criterion holds (SC-001, SC-002, coolant-1 to -8
each right on majority, SC-007), the 120-line set only when the outside set is at least 12 of 14 right on majority;
before each stage the tallies so far plus the stage's estimate must stay within $1.30.

The defaults then apply: Gemini 2.5 Flash, reasoning off, the shipped embedding model and structured-output method,
the override on, every chapter. The other `CARGOLINT_*` variables need no check: the command's own `--expansion off`
and `--customs-wording off` override `CARGOLINT_QUERY_EXPANSION` and `CARGOLINT_CUSTOMS_WORDING`; `CARGOLINT_WORKERS`
changes only concurrency; `CARGOLINT_USD_EUR` only the euro tally; and `CARGOLINT_GPG`, `CARGOLINT_GH`,
`CARGOLINT_RELEASE_REPO`, `CARGOLINT_DEMO_STORE_URL`, `CARGOLINT_DEMO_STORE_SHA256`, `CARGOLINT_DEMO_NOTICE`,
`CARGOLINT_TARIC_RELEASE`, `CARGOLINT_EBTI_RELEASE`, `CARGOLINT_EBTI_RULINGS`, `CARGOLINT_OCR_MIN_SCORE` and
`CARGOLINT_APP_PASSWORD` do not affect what is measured.

Each command prints its cost; together about $0.62 by the evaluation's tallies (research R-07). Read the key's
`usage` again after the runs with the same command, and later as it settles: its difference from the value read
before the first paid call is the spend by the key's usage (spec FR-007, SC-006). Each writes its own
results file (`tests/eval/hs6_eval_017-after_en_expansion-off_wording-off.json`,
`tests/eval/hs6_eval_coolant_017-after_en_expansion-off_wording-off.json`,
`tests/eval/hs6_eval_outside_017-after_en_expansion-off_wording-off.json`), overwrites the set's "latest run" file,
appends a history entry (120-line iteration 22, coolant 10, outside 3, unless other runs came first) and re-renders the
set's report. Keep all of them.

Read the results, no model call:

```bash
.venv/Scripts/python - <<'EOF'
import json
after = "tests/eval/hs6_eval_coolant_017-after_en_expansion-off_wording-off.json"
d = json.load(open(after, encoding="utf-8"))
for ref in ("coolant-1", "coolant-2", "coolant-3", "coolant-8", "coolant-9", "coolant-4", "coolant-5", "coolant-6", "coolant-7"):
    print(ref, [(r["flag"], r["route"], r["top1"]) for run in d["runs"] for r in run if r["reference"] == ref])
eight = [l for l in d["summary"]["lines"] if l["id"] != "coolant-9"]          # SC-004: the original eight, per line
print("original eight right:", sum(l["right"] for l in eight), "of", len(eight), [(l["id"], l["majority"]) for l in eight if not l["right"]])
for k, run in enumerate(d["runs"], 1):                                           # per-run counts without coolant-9
    rows = [r for r in run if r["reference"] != "coolant-9"]
    print(f"run {k}: auto {sum(r['route'] == 'auto_accept' for r in rows)}, wrong auto {sum(r['route'] == 'auto_accept' and not r['right'] for r in rows)}")
def on_rows(run):                                                                # the override on: each row's `on` block
    return [{**r, "top1": r["on"]["chosen"], "hit": r["on"]["hit"], "route": r["on"]["route"]} for r in run]
def right(r):                                                                    # a coded line on its top-1, an "ask" line on its route
    return r["route"] == r["expected_route"] if r.get("expected_route") else r["hit"]
def wrong(r):                                                                    # auto-accepted and wrong
    return r["route"] == "auto_accept" and not right(r)
def per_line(runs):                                                              # SC-003's count: at least 2 of the 3 runs
    return sorted(seen[0]["reference"] for seen in zip(*runs) if sum(wrong(r) for r in seen) >= 2)
for path in ("tests/eval/hs6_eval_017-after_en_expansion-off_wording-off.json", after,
             "tests/eval/hs6_eval_outside_017-after_en_expansion-off_wording-off.json"):
    runs = [[r for r in run if r["reference"] != "coolant-9"] for run in json.load(open(path, encoding="utf-8"))["runs"]]
    for switch, rs in (("off", runs), ("on", [on_rows(run) for run in runs])):      # majority per line, then per run
        print(path, switch, "wrong auto by majority per line:", per_line(rs), "| per run: right", [sum(right(r) for r in run) for run in rs],
              "auto", [sum(r["route"] == "auto_accept" for r in run) for run in rs], "wrong auto", [sum(wrong(r) for r in run) for run in rs])
baselines = {"tests/eval/hs6_eval_017-after_en_expansion-off_wording-off.json": "tests/eval/hs6_eval_014a-rule-a.json",
             after: "tests/eval/hs6_eval_coolant_014a-rule-a.json",
             "tests/eval/hs6_eval_outside_017-after_en_expansion-off_wording-off.json": "tests/eval/hs6_eval_outside_014a-a_en_expansion-off_wording-off.json"}
for new, old in baselines.items():                                              # vague flags per run against the baseline
    flagged = lambda p: [sorted(r["reference"] for r in run if r["flag"] != "ok") for run in json.load(open(p, encoding="utf-8"))["runs"]]
    before, now = flagged(old), flagged(new)
    print(new, "flagged per run:", now, "| changed:", sorted({x for a, b in zip(before, now) for x in set(a) ^ set(b)}))
EOF
```

Expected (spec SC-001, SC-002, SC-007): coolant-3 and coolant-9 `ok` in every run with route `review` or
`auto_accept`; coolant-1, coolant-2 and coolant-8 `vague` with route `ask_shipper` in every run; coolant-4 to -7 `ok`
in every run. Expected for the summaries and the rows (SC-003, SC-004): the 120-line `majority_top1` at least 77 and
its wrong auto-accepts counted per line by majority (the snippet's `per_line`: a line counts when it is auto-accepted
with a wrong top-1 in at least 2 of its 3 runs) at most 3, the baseline's count with the override off
(IEBTIIENEN004-2024-BTI356, MTBTI2024-002, MTBTI2025-011; the override-on count, 3 today, and the per-run counts are
reported alongside, never summed into a criterion: the author's decision of 2026-11-23); the original eight coolant
lines each `right` in the summary's `lines` entries (never the set-wide `majority_top1`, which counts coolant-9); the
outside set at least 12 of 14 right, both sets' per-line counts reported against 0 and 1. The flag comparison names
every line whose flag changed against the baseline runs
(120 lines: the same five lines flagged in every run; outside: none; coolant: coolant-1, -2, -3, -8 before).

On any miss in any stage (the coolant set: SC-001, SC-002, the original eight each right on majority, SC-007; the
outside set: SC-004; the 120-line set: SC-003): stop; nothing more is run, and no revision round runs without the
author's go-ahead (the staged approval of 2026-11-23, which replaces the automatic revision round of clarification
3). Report the miss per line (flag, route and top-1 per run against the baseline) and write the line diff (each line
whose majority top-1 differs from the baseline run's, with its top-1 per run and whether its flag changed in any run;
the typed sets' majorities from the summary's `lines` entries, the 120-line set's from the rows with the evaluation's
own `majority` helper; a top-1 change is noise only on a line whose three baseline runs already disagreed, 120-line
set MTBTI2025-018, XIBTI505060394, IEBTIIENEN004-2026-BTI72 and IEBTIIENEN004-2026-BTI71, outside set
FRBTIFR-BTI-2026-00308, none in the coolant set; any other top-1 change on a line whose flag did not change is "not
attributable: flag unchanged, reason text not recorded"; for SC-007 the coolant-4 to -7 flags per run) and send it to
the author, who decides whether a revision round is spent or the feature stops (spec FR-007, tasks T018).

With the author's go-ahead for the round: revise the examples once under spec FR-001's rules, update FR-001's table
and the test's lists, run the offline suite, check that the tallies so far plus about $0.62 for all three sets stay
within the $1.30 cap (when they do not: the second pass does not run; stop and ask the author for a new approval,
never an automatic further pass), repeat the environment check (names only) and the commands in the same stages with
`--tag 017-after-2`, then read the results again (tasks T019). A second failure stops the feature: report, and the
author decides.

## 4. The record

- `specs/017-coolant-vague-chinese-examples/eval-report.md`: the tables of spec FR-008 (per set: the results by
  majority per line that decide pass or fail, majority top-1 and the wrong auto-accepts counted per line by majority,
  with a per-run table of right, auto-accepted and wrong auto-accepted per run next to them, the override off and on,
  and the cost; the coolant set's counts without coolant-9, coolant-9 in its own row; the coolant lines' flag, route
  and top-1 per run, coolant-4 to -7 included; the vague flags per set and
  per run against the baseline with every changed line named; the line diff of §3 when one was written), with the
  results files, iterations, the approval and the spend by the key's usage against the $0.65 approval.
- `docs/backlog.md` item 17 marked done with the numbers, its "Approach" and "Open decisions for the author" bullets
  marked superseded, not deleted; the README's coolant-set sentence (nine lines) and one sentence with the result
  (research R-10).
- The pull request body: the same tables, the approval with its amount and the commit permission, and the two lines
  `scripts/check_traceability.py` requires of this implementation pull request, which changes `tools/` and always adds
  `traceability.md` and `eval-report.md` under `specs/`: `Spec-PR: #<n>` (the merged spec pull request) and
  `spec-change: <reason>`. There is no exemption for the feature's own folder (docs/qa-platform.md, "Traceability").
