# Data Model: Retrieval and Evidence (Phase 1)

Additions to existing models in `agent/config.py`, `agent/schemas.py` and `rag/loader.py`, and two new files under
`tests/eval/` and `data/rules/`. Nothing existing is removed or renamed; a line version stored before this feature
reads with the new fields empty.

## 1. Settings (`agent/config.Settings`, read by `load_settings`)

| Setting | Field | Type | Default | Rule |
|---|---|---|---|---|
| `CARGOLINT_EBTI_CHAPTERS` | `ebti_chapters` | string | `all` | `all` in any case (the value is lower-cased, as `CARGOLINT_EBTI_RULINGS` is), or a comma-separated list of chapters `01`–`99` and ascending ranges (`27,34,38`, `61-64`); one-digit chapters are padded (`1` → `01`); anything else raises `ValueError` when the settings are read (FR-006) |
| `CARGOLINT_CUSTOMS_WORDING` | `customs_wording` | bool | `False` (`off`) | `on` or `off`, case-insensitive; anything else raises `ValueError` (FR-024) |

`parse_chapter_setting(value) -> frozenset[str] | None` (pure, in `agent/config.py`): `None` for `all` (`ALL`, `All`,
…), else the two-digit chapters. `rag.loader.parse_chapters` uses it. The refresh's `--chapters`, the loader's
`--bti-chapters` and `rag.bti --chapters` accept the same syntax and default to the setting.

`HS6_VOTE_MIN_SIMILARITY` stays a named constant (0.40 to start). Its value changes only by an edit of the constant,
on the after-runs' evidence and with the author's approval (FR-012); at any value, exactly the floor votes.

## 2. Source version (store metadata and release metadata)

| Chapters | `ebti_source_version` |
|---|---|
| `None` (all) | `full extract of <date>, all chapters` |
| exactly the twelve of `TARGET_CHAPTERS` | `full extract of <date>, chapters 39,42,61-64,73,84,85,94,95,96` (as today) |
| any other set | `full extract of <date>, chapters <sorted, comma-separated>` |

`chapters_spec(None)` returns `all chapters`. The refresh's metadata (`metadata.json`, feature 013 §2) and
`index_meta.json` carry the same string; Admin › Data shows it through the existing `rulings_statement` (FR-008,
FR-010).

## 3. Knowledge base (`rag/loader.KnowledgeBase`)

| Attribute | Type | Rule |
|---|---|---|
| `indexed_chapters` | `frozenset[str]` | the `chapter` of every stored ruling (`BTIStore.records`), computed once at construction (FR-016) |
| `main_language` | `str \| None` | the most frequent `language` of the stored rulings, lower case (`de` for the local store); a tie goes to the alphabetically first code; `None` for a store without rulings (FR-024) |

Both are derived in `KnowledgeBase` itself, so `tests/ui/harness.make_kb` and every test that builds a knowledge base
get them from their own rulings.

## 4. Ruling scope (`agent/schemas.RulingScope`, new)

| Field | Type | Rule |
|---|---|---|
| `chapters` | `list[str]` | the chapters of the model's validated HS-6 candidates, two digits each, sorted, one to three; the second vote searched only these (FR-011, rule (a)) |
| `not_indexed` | `list[str]` | those of `chapters` that are not in `KnowledgeBase.indexed_chapters` when the HS-6 step ran (FR-017) |

Carried as `Classification.ruling_scope: RulingScope | None` and copied by `LineStore.update_classification` to
`LineVersion.ruling_scope`, as `hs6_vote` is; `None` when the line has no valid candidate (no vote) or the step
failed. Block 3 reads it with `hs6_vote` (contracts/ui.md §3).

**Relevant ruling** (FR-015, revised on 2026-11-19): a ruling returned by the unfiltered search (the candidate
proposal's) that `hs6_voters` keeps: valid on the day, coded to a subheading of the loaded nomenclature, not excluded,
and with a best similarity of at least `HS6_VOTE_MIN_SIMILARITY`. "No relevant rulings found" holds exactly when
`hs6_vote` is `None` on a line with a candidate.

## 4a. The two votes and the gate (rule (a), 2026-11-19)

| Field | Type | Rule |
|---|---|---|
| `hs6_vote` | `Hs6Vote \| None` | the gate's vote: the 5 nearest eligible rulings over every indexed chapter, from the candidate proposal's hits; it decides the auto-accept (constitution 1.5.0) |
| `hs6_scoped_vote` | `Hs6Vote \| None` | the vote of the candidates' chapters, from the search within `ruling_scope.chapters`; `None` without a voter there; it can only stop an auto-accept |
| `hs6_gate` | `Hs6Gate \| None` | as before, plus `scoped_veto`: the gate passed, but `hs6_scoped_vote` has voters and does not agree on the decided code (the override's candidate, else the top one; its majority at the share or above) |

`Classification` and `LineVersion` carry both votes; `LineStore.update_classification` copies `hs6_scoped_vote` as it
copies `hs6_vote`, and `_recompute`, `ready_to_accept` and the decided code read both. A line version stored before
rule (a) has no `hs6_scoped_vote` and routes on `hs6_vote` alone.

## 5. Citation note (`agent/schemas.CitationNote`, new)

| Field | Type | Rule |
|---|---|---|
| `reference` | string | the ruling reference as stored (`DEBTI1234/22`), or as written in the reasoning when the store does not know it or its normal form names several stored rulings |
| `kind` | `"other_code"` or `"not_retrieved"` | `other_code`: retrieved for the line in that run, its stored HS-6 differs from the candidate's code; `not_retrieved`: not among the rulings retrieved for the line in that run, known to the store or not (FR-021) |
| `ruling_hs6` | `####.##` or `None` | the stored HS-6 for `other_code`; `None` for `not_retrieved` |

Carried as `Candidate.citation_notes: list[CitationNote]` (default empty), in the order the references first occur in
the reasoning, each reference once. **Retrieved for the line in that run**: the rulings of the proposal's and the
vote's searches of that HS-6 step, less an evaluation's excluded references. **Matching**: the reasoning's reference
tokens are found by the pattern "two letters, `BTI` in any case, then letters, digits, `/`, `.` and `-`, a space
allowed only before a digit and only right after `BTI` or `-`", as in stored references (so neither a following number
nor a sentence end joins a reference), with trailing punctuation dropped; a token without a digit is no reference (a
word such as "subtitle" fits the pattern, while every stored reference contains a digit). The retrieved references,
and the stored references the pattern does not fit whole (8 of the 123,531 of 2026-11-18, such as `NLBTI2025 - 0691`),
are also found as written. A cited reference written exactly, case aside, is the one meant; otherwise it is compared
by its normal form (upper case, spaces and punctuation removed), which must be equal, never a prefix (the shortest
stored reference, `DEBTI1/25-1`, has a normal form of nine characters and is a prefix of longer ones). Every reference
is kept per normal form, as distinct references can share one (`GRBTIDEC-036-2025` at 2102.20, `GRBTIDEC-036/2025` at
2304.00): when the form names several rulings and one of them was retrieved, no note is made, as none could say which
ruling is meant; when none was, the note names the reference as written (review round 1). Never a routing input; not
in the CSV or JSON export (FR-023).

## 6. Customs wording (`agent/schemas.CustomsWording`, new; `WordingOut`, new model output)

`WordingOut` (the model's answer, validated like every model output): `text: str`, non-empty after stripping; the
call's output is capped at 512 tokens (`WORDING_MAX_TOKENS`), and an answer that reaches the cap is an invalid answer
with its one retry. The 300-character limit (`WORDING_MAX_CHARS`) is checked after the recorded call, not in the schema
the provider sees, so every attempt counts in the shipment's cost: an answer over it is retried once with feedback,
then fails the line's HS-6 step with the reason (FR-025; review round 1).

| `CustomsWording` field | Type | Rule |
|---|---|---|
| `text` | string | the validated rewrite |
| `language` | string | the target language code (`KnowledgeBase.main_language` when the call was made) |
| `glossary_terms` | `list[str]` | the reviewed glossary terms applied to this line, in the order found |

Carried as `Classification.customs_wording` and `LineVersion.customs_wording` (`None` when the switch was off or the
store has no main language). `RetrievalTrace` gains `customs_wording: str | None` so the Retrieval steps can list it,
marked "rulings only". The rewrite is never written to `text_zh`, `text_en`, the CSV or the JSON export (FR-025).

Cache (`rag/translate.py`, like the expansion's): key = the line's display text, what the shipper confirmed, the target
language and the applied glossary renderings; at most 512 entries, least recently used out.

## 7. Glossary file (`data/rules/customs_glossary.json`, optional, absent by default)

```json
{
  "source": "CargoLint customs glossary, reviewed by the author",
  "version": "YYYY-MM-DD",
  "entries": [
    {"term": "冷却液", "renderings": {"de": "Kühlflüssigkeit"}, "reviewed_by": "<name>", "reviewed_on": "YYYY-MM-DD"}
  ]
}
```

| Field | Rule |
|---|---|
| `term` | as shippers write it; a term with a CJK character matches anywhere in the line's text, any other term only as whole words, ignoring case and accents (FR-027) |
| `renderings` | language code → the fixed customs wording; only the store's main language is used, and an entry with no key for it is not applied, even when reviewed (FR-027) |
| `reviewed_by`, `reviewed_on` | both present and non-empty, `reviewed_on` an ISO date: the entry is applied; otherwise it is ignored |

Read once per process by `rag/rules.py` (a missing file is no glossary; a malformed file is refused with its path when
the knowledge base opens). The glossary is project data, never third-party data; its entries reach the rewrite's prompt
as fixed renderings outside the line's data block. `data/SOURCES.md` lists the file when it exists (constitution: data
and privacy). The example entry above shows the format only; this feature ships no entries.

## 8. Coolant set (`tests/eval/hs6_eval_coolant_set.json`, new)

```json
{
  "built_on": "2026-11-18",
  "source": "docs/backlog.md item 10 (user test on two metal-working coolants), the author's German line and the plain line of clarification 5",
  "lines": [
    {"id": "coolant-1", "text": "冷却液 矿物油含量大于70%", "expected_hs6": "2710.19", "note": ""},
    {"id": "coolant-2", "text": "没有矿物基础油的冷却液", "expected_route": "ask_shipper", "note": "3820.00 if engine coolant, 3403.99 if metal-working"}
  ]
}
```

Eight lines (FR-001), in the backlog's order, then the German line, then `冷却液`. A line has exactly one of
`expected_hs6` (`####.##`) and `expected_route` (`ask_shipper`). `built_on` is the day the rulings' validity is judged
on for this set. The fifth line's note keeps "CN 2710 19 91", not scored. The file is written with LF line endings and
UTF-8 without a byte-order mark.

## 8a. Outside set (`tests/eval/hs6_eval_outside_set.json`, new, 2026-11-19)

The coolant set's format, with every line coded (`expected_hs6`) and sourced: `source` names an EBTI ruling valid on
`built_on` (its reference, which the line's run excludes, leave-one-out) or another verifiable source; `original`
keeps a source text the line was rewritten from (FR-032); `chapter` is the expected HS-6's chapter, outside the twelve
of the old store. The near-duplicate check's similarities are reported to the author, not stored in the file.

## 9. Evaluation rows and history entries (`tests/eval/hs6_eval.py`)

New row fields (both sets; FR-005):

| Field | Type | Meaning |
|---|---|---|
| `vote` | object | the gate's vote (since rule (a), 2026-11-19, the unfiltered one; in rows written before, the then-only chapter-filtered vote) |
| `scoped_vote` | object or `null` | rule (a)'s second vote, the candidates' chapters; absent in rows written before |
| `nearest_hits` | list | the 40 nearest rulings over every chapter, from a log search (for replaying the gate's vote) |
| `vote_chapters` | `list[str]` | `ruling_scope.chapters` |
| `not_indexed` | `list[str]` | `ruling_scope.not_indexed` |
| `vote_hits` | list of `{reference, hs6, similarity, eligible}` | the scoped search's rulings, each once at its best similarity, nearest first; `eligible` ignores the floor (valid, coded, not excluded), so a replay can apply any floor; it is exact, and evidence for a new value, only at or above the run's floor (see the replay paragraph below) |
| `customs_wording` | string or `null` | the rewrite searched with |
| `citation_notes` | list | per candidate code, its notes |
| `expected_route` | string or `null` | the coolant set's "ask the shipper" lines |
| `right` | bool | `hit` for a coded line; route `ask_shipper` for an "ask the shipper" line (the coolant set's score) |

New history-entry fields: `set` (`cn8` for the 120 or 30 lines, `coolant`, `outside`), `customs_wording` (`on`/`off`), `floor`
(the `HS6_VOTE_MIN_SIMILARITY` of the run or replay), `replay` (`{"of": <results file>, "floor": X}` for a floor
replay). A replay from the logged `vote_hits` is exact only for floors at or above the run's floor: the run searched
the 12 nearest rulings per query vector, so a lower floor could need rulings beyond those searched (research R-07,
contracts/eval-cli.md). The coolant set's runs go to `hs6_eval_coolant.json`, `hs6_eval_coolant_<tag>_…json`,
`hs6_eval_coolant_history.json` and `hs6_eval_coolant.md`; the 120-line set's files keep their names and meaning.

## 10. What block 3 reads (contracts/ui.md §3, rule (a))

The list: `hs6_vote`'s codes with their rulings' countries. The captions, in this order, one `st.caption` each:

| Order | Reads | Caption |
|---|---|---|
| 1 | `hs6_vote` set, a code chosen | "n of m agree with <code>" (before this feature's wording, a typed code included) |
| 1 | `hs6_vote` `None`, a candidate | "No relevant rulings found." |
| 2 | `hs6_gate == scoped_veto` | "Sent to review by the rulings of the candidates' chapter(s) NN (and MM): n of m at <code>." or "...: split, n at <code>, n at <code> and n at <code>." (`hs6_scoped_vote`; the chapters of `ruling_scope.chapters` not in `not_indexed`) |
| 3 | `ruling_scope.not_indexed` not empty | "No rulings indexed for chapter NN." / "chapters NN, MM and LL." |

No caption without a candidate (no valid candidate, or the step failed).
