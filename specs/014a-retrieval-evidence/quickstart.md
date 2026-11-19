# Quickstart: validating feature 014a

Two kinds of checks: the offline suite, which anyone can run without a key, and the author's live steps, which spend
OpenRouter credits and follow the order of FR-003. Paths are relative to the feature worktree; the store and
environment arrangement is plan.md's "Store and environment for the live steps".

## 1. Environment (once)

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"     # Python 3.11-3.13; .venv is git-ignored
```

For the live steps, `OPENROUTER_API_KEY` is an OS environment variable (never printed, never in a file), and
`<worktree>/store` holds the store the step needs (plan.md). Before the baseline, copy the five layout entries of the
main checkout's store into the worktree, reading the main checkout only:

```bash
mkdir -p store && cp -r /c/ai/CargoLint/store/{index_meta.json,bm25.pkl,bti_docs.jsonl,chroma,chroma-bti} store/
du -sb store      # expected about 3,350,384,841 bytes (3.35 GB), as measured on 2026-11-18
```

## 2. Offline suite (every step of the implementation)

```bash
.venv/Scripts/python -m pytest -q          # live tests are deselected by default; no key, no network
```

Expected: green. The new tests cover the settings, the chapter-scoped vote and its floor boundary, the indexed
chapters, block 3's captions, the citation notes, the customs wording (switch, scope, merge, cache, language, glossary,
injection fixture), the coolant set's scoring and the floor replay (spec FR-030).

Dry runs of the evaluation need a store but make no model call only with `--replay`; a plain `--dry-run` still calls
the model for its lines, so it is a live step too.

## 3. Live step 1: the baseline (before any product code changes)

Prerequisite: the coolant set and `--set coolant` are committed (tasks Phase 2); `<worktree>/store` is the copy of
the current local store (twelve chapters, extract of 2026-11-18).

```bash
.venv/Scripts/python tests/eval/hs6_eval.py --repeat 3 --tag 014a-baseline --expansion off
.venv/Scripts/python tests/eval/hs6_eval.py --set coolant --repeat 3 --tag 014a-baseline --expansion off
```

Expected: two history entries tagged `014a-baseline`; the 120-line majority top-1 near earlier Gemini runs (82–83 of
120, single runs vary by a few lines); about $0.55 in all.

## 4. Live step 2: the rebuild (after the implementation)

```bash
.venv/Scripts/python scripts/refresh_ebti.py --no-publish --rulings all --previous <copy of the current store> --out build/ebti-<date>
```

Watch the log before the embedding starts: "extract … N valid rulings in M chapters" and "chose N rulings: K kept, …".
Expected: every chapter with valid rulings present; `reused` equal to the unchanged rulings of the twelve chapters;
`embedded` = the new and changed rulings only (SC-001); about $0.36 per 100,000 embedded rulings. Then the rebuilt
`build/ebti-<date>/store` becomes `<worktree>/store` (plan.md).

## 5. Live step 3: the after-runs

```bash
.venv/Scripts/python tests/eval/hs6_eval.py --repeat 3 --tag 014a-after --expansion off --customs-wording off
.venv/Scripts/python tests/eval/hs6_eval.py --set coolant --repeat 3 --tag 014a-after --expansion off --customs-wording off
.venv/Scripts/python tests/eval/hs6_eval.py --repeat 3 --tag 014a-after --expansion off --customs-wording on
.venv/Scripts/python tests/eval/hs6_eval.py --set coolant --repeat 3 --tag 014a-after --expansion off --customs-wording on
```

Check on the rows: no coolant line has a voter outside its `vote_chapters`, none shows a chapter 84 ruling (SC-002);
`冷却液` routes to `ask_shipper` in every run with the switch on (FR-026).

## 6. Floor replays (no model call)

```bash
.venv/Scripts/python tests/eval/hs6_eval.py --replay tests/eval/hs6_eval_014a-after_en_expansion-off_wording-off.json --floor 0.45
```

Repeat for the floors the author wants to see, at or above the run's floor of 0.40 (for example 0.45, 0.50, 0.55): a
replay is exact only there, since a lower floor could need rulings beyond those the run searched. Each adds a replay
entry with the routes, auto-accepts, wrong auto-accepts and lines without a voter at that floor.

## 7. The pull request's comparison (FR-004)

From `hs6_eval_history.json` and `hs6_eval_coolant_history.json`: one table per set, baseline against after (switch
off) against after (switch on): majority top-1, top-1 per run, in top 3 per run, auto-accepted and wrong auto-accepted
per run, lines decided without a voting ruling per run; the coolant set's per-line majority outcomes; the floor
replays; SC-004 (the wrong auto-accepts summed over the three switch-off after-runs, the shipped default, against the
three baseline runs) stated as passed or failed with its lines, the switch-on runs reported separately; FR-026's two
conditions stated with their numbers.

## 8. Constitution (FR-031)

After `/speckit-constitution` has run with the approved wording: `.specify/memory/constitution.md` reads "EBTI rulings
for all chapters; the chapter list is a setting, default all" under "Knowledge-base sources", its version line is
bumped to 1.11.0 (MINOR, confirmed by the author) with today's last-amended date, the amendment log has the entry, and
Principle IV is unchanged.

## 9. Manual UI check (author)

Restart Streamlit after the change (the server does not reload `ui/*.py`), open a coolant line:

- block 3 lists the deciding vote's rulings (over every chapter, rule (a)) with the captions of contracts/ui.md §3;
- on the twelve-chapter store (the baseline copy), a coolant line whose candidates are 2710.19, 3403.99 and 3820.00
  reads "No rulings indexed for chapters 27, 34 and 38.";
- with the switch on, block 1 shows the customs wording; the CSV download is unchanged;
- a candidate whose reasoning cites another code's ruling shows the note after "Why: …".
