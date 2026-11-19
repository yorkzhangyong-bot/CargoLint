# Contract: what the clerk reads (feature 014a)

Every text below comes from `ui/view.py` and is rendered in `ui/expand.py` with native Streamlit elements
(`st.caption`, `st.markdown`), escaped with `md_escape` where it holds stored text. No element is added, removed or
moved except the block 1 caption of §1, wanted by the author and display only (clarification 5 and the author's
confirmation after spec review round 1). No CSS (constitution 1.10.0).
All values come from the line version in the line store, never from model prose read at render time.

## 1. Block 1, Description: the customs wording searched

Shown under the description's captions when `line.current.customs_wording` is set (the switch was on when the line's
HS-6 step ran):

```text
Rulings also searched in customs wording (<language name>): <rewrite>
```

Example: `Rulings also searched in customs wording (German): Kühlschmierstoff für die Metallbearbeitung, ohne
Mineralöl`. Nothing is shown when the field is empty. The caption is display only, wanted by the author: it changes
neither the routing nor the CSV export. The editable description, "Original: …" and the CSV keep the raw text.

## 2. Block 2, HS-6 candidates: citation notes

For the chosen candidate, after `Why: <reasoning>` and in the same caption, one sentence per note, in stored order:

| Note kind | Text |
|---|---|
| `other_code` | `Cited ruling <reference> classifies under <ruling HS-6>, not <candidate code>.` |
| `not_retrieved` | `Cited ruling <reference> was not retrieved for this line; it is not a source.` |

Example: `Why: Coolants for metal working are lubricating preparations … Cited ruling DEBTI1234/22 classifies under
8419.89, not 3403.99.` A candidate without notes reads as today. The candidates' order, confidence bars and labels do
not change. The CSV and JSON exports do not carry the notes (014b owns reasons in the CSV).

## 3. Block 3, Similar rulings (5 nearest, EBTI)

Rule (a), the author's decision of 2026-11-19: the heading and the list of codes with their issuing countries show
the deciding vote, the 5 nearest eligible rulings over every indexed chapter (`hs6_vote`), as before feature 014a.
The vote of the candidates' chapters (`hs6_scoped_vote`) is not listed. Under the list (or alone, when nothing voted),
`view.rulings_captions(line, chosen)` gives the captions, each in its own `st.caption`, in this order:

| Order | When (line version) | Caption |
|---|---|---|
| 1 | `hs6_vote` is set and a code is chosen (a candidate, or a code typed under "Other HS-6 code…") | `n of m agree with <code>`, the wording before feature 014a: `3 of 5 agree with 3403.99` |
| 1 | `hs6_vote` is `None` and the line has a candidate: the deciding vote has no voter | `No relevant rulings found.` |
| 2 | `hs6_gate` is `scoped_veto`: the vote of the candidates' chapters sent the line to review | `Sent to review by the rulings of the candidates' chapter 61: 3 of 5 at 6110.30.` / `Sent to review by the rulings of the candidates' chapters 34 and 38: 3 of 5 at 3403.19.`; on a tie, `Sent to review by the rulings of the candidates' chapters 34 and 38: split, 2 at 3403.99, 2 at 3403.19 and 1 at 2710.19.` |
| 3 | `ruling_scope.not_indexed` is not empty: a candidate's chapter holds no ruling in the store | `No rulings indexed for chapter 38.` / `No rulings indexed for chapters 27, 34 and 38.` |

Before a code is chosen there is no agreement caption; a line without a candidate (no valid candidate, or the step
failed) shows no caption. "No ruling was within the similarity floor." is not shown. The veto caption names the
candidates' chapters that hold rulings (those the second vote read) and the second vote's majority with its share, or
every code with its rulings on a tie; it reads the stored gate, so it holds as long as the line keeps it. Chapter lists
are two-digit chapters in ascending order, joined with ", " and a final " and ". The explanation line under the list
(why the line waits for the clerk) keeps its wording; for a veto it reads `Rulings of the candidates' chapters
disagree: model <code>, their nearest rulings <codes with countries>. TARIC runs after your pick.`

## 4. Admin › Ask the agent, Retrieval steps

The existing "Queries" line lists the rewrite after the queries, only when the line has one (FR-025):

```text
- Queries (expansion off): <the queries as today> · rulings only, in German: <rewrite>
```

No other line of the expander changes.

## 5. Admin › Data

Unchanged statements; the EBTI line's source version now reads `full extract of <date>, all chapters` for a store
built with all chapters (contracts/settings-and-scripts.md §3).
