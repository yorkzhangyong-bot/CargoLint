# Contract: the HS-6 evaluation's new options (`tests/eval/hs6_eval.py`)

Live runs need `OPENROUTER_API_KEY` and a store, spend credits, and are run by the author or with the author's
go-ahead (FR-003). A replay makes no model call. Existing options keep their meaning; the 120-line set's files and
history stay comparable with earlier iterations.

## Options

| Option | Values | Meaning |
|---|---|---|
| `--set` | `cn8` (default), `coolant` | `cn8`: the 120 rulings of `cn8_eval_set.json` (or the 30 Chinese lines with `--lang zh`), as today. `coolant`: the eight lines of `hs6_eval_coolant_set.json` (data-model §8); `--lang` does not apply |
| `--customs-wording` | `on`, `off` | the customs-wording switch for this run, over `CARGOLINT_CUSTOMS_WORDING`; kept in the history entry and the per-run file name |
| `--replay FILE --floor X` | a results file, a similarity | recompute every row's vote from its `vote_hits` at floor `X` with the routing functions, no model call; exact for `X` at or above the run's floor; refused for a file without `vote_hits`; the replay's entry goes to the history and report of the set its file names (its summary's `set`, `cn8` when absent), and a coolant replay reads no CN-8 results |

`--replay FILE --override-min N` (feature 008) stays; `--floor` and `--override-min` can be combined in one replay.

## The coolant set's run

- Each line is the set's text as typed, split as the app splits a typed line (`tools.parsers.split_mixed`); its own
  ruling is not excluded (it has none); ruling validity is judged on the set's `built_on` date.
- It goes through the same path as the 120: the description check, the HS-6 step with the context of an unknown
  shipper, the route the store computes (threshold 85, ask floor 50).
- Scoring per row: `right` = `hit` (top-1 is `expected_hs6`) for a coded line, `route == "ask_shipper"` for a line
  with `expected_route`; `in_top3` for coded lines only. Over the runs (spec FR-004): right per run counts `right`; a
  line is right on majority when its most frequent top-1 (a coded line) or route (an `expected_route` line), a tie
  going to the earliest run, is the expected one; a wrong auto-accept is a row routed `auto_accept` that is not
  `right`.
- No cross-layer table (no CN-8 results exist for these lines).
- Files: `tests/eval/hs6_eval_coolant.json` (the latest run's rows),
  `tests/eval/hs6_eval_coolant_<tag>_<lang>_expansion-<on|off>_wording-<on|off>.json` (the `_wording-…` part only once
  `--customs-wording` exists, from tasks Phase 8 on; the baseline's files end in `_expansion-off.json`),
  `tests/eval/hs6_eval_coolant_history.json`, `tests/eval/hs6_eval_coolant.md` (one table: per entry, right per
  run, majority right, each line's majority outcome, routes, wrong auto-accepts, cost).

## Rows (both sets)

New fields, as data-model §9 lists: `vote_chapters`, `not_indexed`, `vote_hits`, `customs_wording`,
`citation_notes`, and for the coolant set `expected_route` and `right`. Existing fields keep their meaning; on runs
made after this feature, `vote` and `gate` are the chapter-scoped vote's.

## History entries

Existing fields plus `set`, `customs_wording` and `floor`; a replay adds `replay: {"of": FILE, "floor": X}` and
reports per run the routes, the auto-accepted and wrong auto-accepted lines, the lines without a voting ruling and the
right auto-accepts, at that floor.

## The runs this feature needs (quickstart.md)

Every run passes `--expansion off` (research R-10), whatever `CARGOLINT_QUERY_EXPANSION` says.

| Step | Command (from the feature worktree, its `.venv`) | Live |
|---|---|---|
| baseline, 120 lines | `python tests/eval/hs6_eval.py --repeat 3 --tag 014a-baseline --expansion off` | yes |
| baseline, coolant | `python tests/eval/hs6_eval.py --set coolant --repeat 3 --tag 014a-baseline --expansion off` | yes |
| after, switch off | the two commands above with `--tag 014a-after --customs-wording off` | yes |
| after, switch on | the two commands above with `--tag 014a-after --customs-wording on` | yes |
| floor replays | `python tests/eval/hs6_eval.py --replay <after-run file> --floor 0.45` (and other floors the author picks, at or above the run's floor) | no |
