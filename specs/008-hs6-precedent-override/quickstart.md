# Quickstart: validating the precedent override

How to show that feature 008 works, in order. The rule is in [contracts/override.md](contracts/override.md) and the
records in [data-model.md](data-model.md).

## 0. Before the code

The author runs `/speckit-constitution` with the 1.6.0 amendment drafted in [plan.md](plan.md). Constitution 1.5.0
does not allow the override.

## 1. Offline (no key, no credits)

```bash
pytest -q
```

Expected: the whole suite passes, including the new tests:
- the gate at the threshold: 4 of 5 and 4 of 4 override, 3 of 5 does not;
- no override for a flagged line, a tie, a share below 0.5, no eligible ruling, or a top candidate that already
  agrees;
- an ever-flagged line becomes ready to accept the chosen candidate;
- with the switch off, every gate case equals today's;
- the hint appears only for a code outside the top three, at 4 or more;
- in the store: the decided code, the audit entries, and the CN-8 step on the chosen candidate;
- the view texts;
- in both evals, the switch-on and switch-off results derived from one stored run.

## 2. The switch in the app

```bash
streamlit run app.py                            # default: switch off, the product as today
CARGOLINT_HS6_OVERRIDE=on streamlit run app.py  # switch on (set the variable as your shell sets one)
```

With the switch on, a line whose five nearest rulings sit at least 4 of 5 at its second or third candidate behaves as
follows (the page tests in `tests/ui/` seed such a line; the 12-line sample may not have one):
- it is green;
- its code is that candidate;
- its "Decided:" line reads "candidate N chosen, rulings overrode the model: N of M agree on <code> (<countries>);
  the model's top candidate was <top>".

With 4 of 5 rulings at a code outside the top three, the line stays yellow and its explanation ends with the hint.

## 3. The HS-6 eval (live: spends credits, run only when the author asks)

```bash
python tests/eval/hs6_eval.py --repeat 1 --tag hs6-override --cn8 tests/eval/cn8_eval_iteration12.json
```

This is one paid run. Read the entry's "Precedent override" section in `tests/eval/hs6_eval.md`:
- **SC-002**: wrong auto-accepts on ≤ off.
- **SC-003**: the end-to-end estimate against CN-8 iteration 12, on > off.
- **SC-006**: the overrides that fired, and how many chose the right HS-6.

## 4. The end-to-end eval (live)

```bash
python tests/eval/e2e_eval.py --repeat 1 --tag e2e-override
```

This is one paid run with the switch on, plus one CN-8 call per override line. In `tests/eval/e2e_eval.md`, the entry's
on and off columns give:
- **SC-001**: right end to end, on > off.
- **SC-002**: wrong auto-accepts, on ≤ off.
- **SC-004**: every override line's route reason in `tests/eval/e2e_eval.json` holds the note, and its record holds the
  chosen rank.

For context only: run `e2e-stopword-fix` had 68 of 120 right and 7 wrong auto-accepts, and constitution 1.5.0 records
the HS-6 estimate as 74 of 120.

## 5. Decide the switch

When both evals meet SC-001 to SC-003, the author turns the switch on (FR-007). Otherwise it stays off, and the reports
record why.
