# Contract: Precedent Override at the HS-6

The interface of feature 008 for the code, the clerk's screen and the evals. Data: [../data-model.md](../data-model.md).

## 1. Routing (`agent/routing.py`)

`hs6_gate(confidence, threshold, vote, override_min=None) -> tuple[bool, Hs6Gate]`. `override_min` None is the switch
off. With `OVERRIDE_MIN` = 4 and five rulings voting:

| Case | Switch off | Switch on |
|---|---|---|
| no eligible ruling votes (`vote` None) | `(confidence ≥ threshold, no_rulings)` | the same |
| the top candidate is the majority with a share ≥ 0.5 | `(True, vote_agrees)` | the same |
| majority at candidate 2 or 3, 5 of 5 or 4 of 5 | `(False, vote_disagrees)` | `(True, vote_override)` |
| majority at candidate 2 or 3, 3 of 5 | `(False, vote_disagrees)` | the same |
| majority at candidate 2 or 3, 4 of 4 (only four eligible) | `(False, vote_disagrees)` | `(True, vote_override)` |
| majority outside the top three, any count | `(False, vote_disagrees)` | the same; a hint at 4 or more |
| tie | `(False, vote_tie)` | the same |
| the top candidate leads below the share | `(False, vote_share_low)` | the same |

Exactly `OVERRIDE_MIN` agreeing rulings override; one fewer does not (FR-013).

`route_line(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor, cn8_question=None, cn8_error=None,
hs6_vote=None, hs6_override_min=None) -> tuple[Route, str]` applies its existing rules first: status, flags and the
CN-8 question and error. Then the gate decides:
- `vote_override` with `ever_flagged` False gives `(auto_accept, "rulings overrode the model: N of M agree on <code>")`.
- `vote_override` with `ever_flagged` True gives `(review, "ready to accept — rulings overrode the model: N of M agree on
  <code>, but the line was flagged or updated before; click Accept to confirm")`.
- Every other gate value routes as today.

`hs6_auto_decided(...)` takes the same `hs6_override_min` and stays `route_line(...)[0] == auto_accept`.

`hs6_choice(candidates, vote, gate) -> tuple[int | None, str | None]`: `(vote.candidate, that candidate's code)` for
`vote_override`; otherwise `(1, the top code)`; `(None, None)` with no candidate.

N is the rulings at the code and M the rulings that voted, both from `vote.competing`. `<code>` is the HS-6 as stored
(`3926.90`); the screen spaces it (`3926 90`) as it spaces every code.

## 2. Texts on the clerk's screen (`ui/view.py`)

All are plain text in native Streamlit elements.

| Where | When | Text |
|---|---|---|
| table, status column | an overridden line, once its CN-8 and TARIC are settled | as for any auto-accepted line ("Ready"); the code column shows the chosen candidate |
| `a_change`, "Decided:" line, HS-6 part (`_hs6_how`) | gate `vote_override`, no decision | "candidate {rank} chosen, rulings overrode the model: {N} of {M} agree on {code} ({countries}); the model's top candidate was {top}" |
| the same | the clerk accepted it (`chosen_how` auto) | the same text followed by ", accepted by you" |
| `a_cn8`, first line (`explain_a`), the CN-8 rows ("Pick: CN-8", "Confirm: {CN-8}") | gate `vote_override`, the HS-6 decided by the override (`chosen_how` auto) | "The HS-6 is {code}; rulings overrode the model: {N} of {M} agree on {code}; its subheading has {n} CN-8 lines." |
| table, status column | `vote_override` on an ever-flagged line | "Confirm: {chosen code}" |
| `a_hs6`, second line (`explain_a`) | the same | "Candidate {rank}, {code}, is chosen because the rulings overrode the model ({N} of {M} agree on it: {countries}), but {why}, so it needs your confirmation. TARIC runs after your pick." |
| `a_hs6`, pre-selection (`preselect`) | the same | the chosen candidate |
| `a_hs6`, second line | switch on, gate `vote_disagrees`, ≥ `OVERRIDE_MIN` rulings at a code outside the top three | today's "Rulings disagree: …" line followed by " Hint: {N} of {M} nearest rulings agree on {code}, which is not among the candidates." |
| `a_hs6`, second line | majority at candidate 2 or 3 below `OVERRIDE_MIN`, or the switch off | unchanged: "… Precedents support candidate {n}. …" |

`{countries}` is the issuing country of each agreeing ruling, in the vote's order, "?" for an unknown one, joined as
the feature 006 texts join them ("IE, DE, DE, FR"). `{why}` is the existing wording: "this line was flagged before its
update" or "this line was updated from the shipper's reply". The clerk changes an overridden line's HS-6 with
"Change", like any auto-accepted line; the decision is recorded with `chosen_how` top, other candidate or typed, as
today.

## 3. Audit trail (`agent/store.py`)

When the override decides a line, two entries are written:
- a `route_computed` entry, whose note is the route reason;
- a `code_decided` entry by `routing_rule`, with `previous` set to the model's top candidate, `new` to the chosen code,
  and the note "rulings overrode the model: N of M agree on <code>; candidate N chosen".

Each is written once, when the route changes. The audit's JSON export shows both. The CSV and JSON line export keeps
its schema; its `decided_code` is the chosen candidate and its `decided_how` is "auto" (FR-014).

When the clerk changes a line's HS-6 (FR-011), the clerk's `code_decided` entry has `previous` set to the code in force
before the change, which `set_decision` reads from `decided_code(line)`:
- the code the clerk accepted earlier, when they had already accepted one;
- otherwise, on a line the override decided, the chosen candidate, not the model's top candidate;
- otherwise the model's top candidate.

A line without an override is recorded as before feature 008, except when the clerk changes a code they had already
accepted: `previous` is now that earlier code, where it used to be the model's top candidate.

## 4. Evals

**HS-6 eval**:

```bash
python tests/eval/hs6_eval.py --repeat 1 --tag hs6-override --cn8 tests/eval/cn8_eval_iteration12.json
```

- One paid run. Each row carries both states (data-model §8).
- The report adds a "Precedent override" section to the entry. It shows the overrides that fired and how many chose
  the right HS-6, and how often the supported candidate was right. Off against on, it compares the chosen HS-6 right,
  the wrong auto-accepts and the end-to-end estimate against CN-8 iteration 12.
- `tests/eval/cn8_eval_iteration12.json` is the pinned copy of the CN-8 eval's iteration 12, from commit `ce3bf02`.

**End-to-end eval**:

```bash
python tests/eval/e2e_eval.py --repeat 1 --tag e2e-override
```

- One paid run with the switch on, plus one CN-8 call per override line under the model's top candidate.
- The report shows on and off side by side for the entry: right end to end, auto-accepted, wrong auto-accepts,
  review, ask, and the overrides that fired and how many were right. It also lists the lines whose outcome differs
  between the two states.

**Success** (spec SC-001 to SC-003), read from these two reports:
- right end to end on > off, in both evals;
- wrong auto-accepts on ≤ off, in both evals.
