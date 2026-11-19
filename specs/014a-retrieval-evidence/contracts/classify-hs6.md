# Contract: `classify_hs6` after feature 014a

The tool's name, arguments (`line_nos`, `all_pending`), JSON summary and registration are unchanged; it stays one of
the seven tools (constitution V), and no tool is added. Below is `classify_one` per line, in order; steps marked
*new* or *changed* are this feature's. Everything else is feature 006/008/009 behaviour.

1. A pure stop word: no candidates, as today.
2. **Queries** (as today): the raw text, then what the shipper confirmed, then, with query expansion on, its queries.
3. *New* — **customs wording**, only with `ClassifyContext.customs_wording` on and `kb.main_language` set: one cached
   model call (`rag.translate.customs_wording`) returns a `CustomsWording` in the store's main language, with the
   reviewed glossary entries that match the line and have a rendering in the store's main language applied before the
   call. A failure raises, and the line fails with the reason, as a failed expansion does.
4. **Embedding** (changed): the queries and, when present, the rewrite, in one request.
5. **Nomenclature search** (as today): hybrid, with the queries' vectors only (never the rewrite's), the shipper
   history's soft chapter boost, and the history chunks.
6. **Candidate proposal** (changed input): per vector of the queries and the rewrite, the 12 nearest rulings over every
   indexed chapter; fused by rank; up to three codes join the candidate chunks with their precedent tags. These hits
   also feed the gate's vote (step 9, rule (a)).
7. **Ranking** (unchanged prompt, unchanged input: the raw description), schema validation, code-existence validation,
   the vague confidence cap.
8. *New* — **search of the candidates' chapters**: when there is at least one valid candidate, `chapters` = the
   candidates' chapters; per vector of the queries and the rewrite, the 12 nearest rulings with `chapter_filter =
   chapters`; `RulingScope(chapters, not_indexed = chapters − kb.indexed_chapters)`.
9. **Votes** (rule (a), the author's decision of 2026-11-19; same rules for both): `hs6_voters` (each ruling once at
   its best similarity, floor `HS6_VOTE_MIN_SIMILARITY` inclusive, valid on the day, coded to a loaded subheading, not
   excluded), then `hs6_ruling_vote` with the candidates (k 5, share 0.5): over the proposal's hits for the gate's vote
   (`hs6_vote`, every chapter), and over step 8's hits for the second vote (`hs6_scoped_vote`).
10. *New* — **citation check**: for each candidate, `citation_notes(rationale, code, retrieved, kb.bti)` where
    `retrieved` is the proposal's and the vote search's rulings, less `exclude_refs`; stored on the candidate.
11. **Result**: `Classification` with, in addition to today's fields, `ruling_scope`, `hs6_scoped_vote`,
    `customs_wording` and the candidates' `citation_notes`; `RetrievalTrace.customs_wording` for the Retrieval steps.

Routing is computed afterwards by the store (`route_line`, `hs6_gate`): the gate's vote decides the auto-accept as
before this feature, and `hs6_scoped_vote` can only send a line the gate would accept to review (`Hs6Gate.scoped_veto`)
when it has voters and does not agree on the decided code. None of the other new fields is a routing input.

**With query expansion on**, its queries are among "the queries" of steps 2 to 9 as today: they search the nomenclature
and the rulings. The rewrite is then one more vector in the two ruling searches, up to nine in all: one ranking among
up to nine in the proposal's fusion, while in the vote any vector can bring a ruling into the five nearest. The
feature's evaluation runs keep expansion off so the rewrite is measured alone (research R-10).

**Not changed**: the CN-8 step's ruling search (`tools/classify_cn8.py`) keeps the raw text and its scope, the decided
HS-6, with no chapter filter and no rewrite (research R-16).

## Context (`ClassifyContext`)

| Field | Default | Note |
|---|---|---|
| `customs_wording` | `Settings.customs_wording` (off) | an evaluation run sets it per run (`--customs-wording`) |

`exclude_refs` (evaluations) applies to the proposal, the vote search and the "retrieved" set of the citation check.

## Functions (pure, offline-testable)

| Function | Module | Contract |
|---|---|---|
| `parse_chapter_setting(value)` | `agent/config.py` | `None` for `all`; the set of two-digit chapters; `ValueError` otherwise |
| `hs6_voters(hits, …)` | `tools/classify_hs6.py` | unchanged signature and rule; it receives the proposal's hits (the gate's vote) and the scoped hits (the second vote) |
| `hs6_gate(confidence, threshold, vote, override_min, scoped_vote)` | `agent/routing.py` | rule (a): the unfiltered gate; `scoped_veto` when it passed and the second vote has voters and does not agree |
| `ruling_scope(candidates, indexed)` | `tools/classify_hs6.py` | the sorted chapters and the unindexed ones |
| `citation_notes(rationale, code, retrieved, store)` | `tools/classify_hs6.py` | the notes in order of first occurrence, each reference once |
| `customs_wording(client, line, language, glossary)` | `rag/translate.py` | `CustomsWording`; cached; the line inside `fence(...)` |
| `glossary_matches(text, glossary, language)` | `rag/translate.py` | the reviewed entries with a rendering for `language` whose term occurs (CJK anywhere; other terms as whole words, case and accents ignored); a reviewed entry with no rendering for `language` is not applied |
| `main_language(records)`, `indexed_chapters(records)` | `rag/bti.py` | from the stored rulings |
| `rulings_captions(line, chosen)` | `ui/view.py` | the captions of contracts/ui.md §3, in order (an empty list for none) |
