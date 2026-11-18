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

The heading and the list of codes with their issuing countries are unchanged; the voters now come from the
candidates' chapters only. The caption under the list (or alone, when nothing voted) replaces both
"No ruling was within the similarity floor." and, in case (c), "0 of m agree with <code>":

| Case | When (line version) | Caption |
|---|---|---|
| (a) | no vote, and no chapter of `ruling_scope.chapters` is indexed | `No rulings indexed for chapter 34.` / `No rulings indexed for chapters 27, 34 and 38.` |
| (b) | no vote, and at least one of them is indexed | `No relevant rulings found.` then, if some are not indexed, ` No rulings indexed for chapter 38.` |
| (c) | a vote, and the chosen code's chapter is in `ruling_scope.not_indexed` (a candidate's chapter, or the searched chapter of a code typed under "Other HS-6 code…") | `No rulings indexed for chapter 38.` |
| (d) | a vote, and the chosen code's chapter was searched and is indexed | `n of m agree with <code>` (unchanged wording) |
| (e) | a vote, and the chosen code was typed under "Other HS-6 code…" and its chapter was not searched | no caption |
| (f) | no `ruling_scope` (no valid candidate, or the step failed) | no caption (today's "No ruling was within the similarity floor." is not shown) |

Chapter lists are two-digit chapters in ascending order, joined with ", " and a final " and ". The explanation line
under the list (why the line waits for the clerk) keeps its wording; with no vote it is the existing threshold text.

## 4. Admin › Ask the agent, Retrieval steps

The existing "Queries" line lists the rewrite after the queries, only when the line has one (FR-025):

```text
- Queries (expansion off): <the queries as today> · rulings only, in German: <rewrite>
```

No other line of the expander changes.

## 5. Admin › Data

Unchanged statements; the EBTI line's source version now reads `full extract of <date>, all chapters` for a store
built with all chapters (contracts/settings-and-scripts.md §3).
