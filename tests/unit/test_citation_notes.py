"""Feature 014a, User Story 5: the rulings a candidate's reasoning cites are checked against the rulings retrieved for the
line in that run, at six digits: a retrieved ruling at another HS-6 gets an "other code" note with that HS-6, a reference
not retrieved (known to the store or not) a "not retrieved" note; references are compared without regard to case,
spaces or punctuation, by equality of their normal forms (spec FR-020, FR-021; data-model §5)."""
from __future__ import annotations

import pytest

from agent.schemas import CitationNote
from rag.bti import BTIStore
from tools.classify_hs6 import citation_notes

pytestmark = pytest.mark.unit

STORE = BTIStore([{"reference": ref, "code": code, "chapter": code[:2], "member_state": ref[:2]} for ref, code in (
    ("DEBTI1234/22", "8419.89"), ("FRBTI0099/23", "3403.99"), ("NLBTI5555/24", "2710.19"), ("DEBTI1/25-1", "3403.19"),
    ("DEBTI12510/23", "3403.99"), ("MTBTI2024 - 001", "3403.99"))])


def other(reference: str, hs6: str) -> CitationNote:
    return CitationNote(reference=reference, kind="other_code", ruling_hs6=hs6)


def missing(reference: str) -> CitationNote:
    return CitationNote(reference=reference, kind="not_retrieved", ruling_hs6=None)


def test_a_retrieved_ruling_at_another_hs6_gets_its_real_hs6():
    notes = citation_notes("Coolants for metal working, like DEBTI1234/22.", "3403.99", {"DEBTI1234/22"}, STORE)
    assert notes == [other("DEBTI1234/22", "8419.89")]


def test_a_retrieved_ruling_at_the_candidates_code_gets_no_note():
    assert citation_notes("FRBTI0099/23 classifies such fluids here.", "3403.99", {"FRBTI0099/23"}, STORE) == []


def test_a_stored_ruling_not_retrieved_is_not_a_source():
    assert citation_notes("See NLBTI5555/24.", "3403.99", {"DEBTI1234/22"}, STORE) == [missing("NLBTI5555/24")]


def test_an_unknown_reference_is_not_retrieved_and_kept_as_written():
    assert citation_notes("As in ITBTI7777/21 for coolants.", "3403.99", set(), STORE) == [missing("ITBTI7777/21")]


def test_case_and_spaces_do_not_matter():
    notes = citation_notes("cf. debti 1234/22", "3403.99", {"DEBTI1234/22"}, STORE)
    assert notes == [other("DEBTI1234/22", "8419.89")]                                  # the reference as stored


def test_a_short_reference_never_matches_inside_a_longer_one():
    notes = citation_notes("DEBTI12510/23 is close.", "3403.99", {"DEBTI1/25-1"}, STORE)
    assert notes == [missing("DEBTI12510/23")]                                          # not DEBTI1/25-1 at 3403.19
    assert citation_notes("DEBTI1/25-1 is close.", "3403.99", {"DEBTI12510/23"}, STORE) == [missing("DEBTI1/25-1")]


def test_trailing_punctuation_is_dropped_and_a_space_is_kept_only_before_a_digit():
    assert citation_notes("(see DEBTI1234/22.)", "3403.99", {"DEBTI1234/22"}, STORE) == [other("DEBTI1234/22", "8419.89")]
    assert citation_notes("DEBTI1234/22 and NLBTI5555/24, both", "8419.89", {"DEBTI1234/22"}, STORE) == [
        missing("NLBTI5555/24")]                                                         # "DEBTI1234/22 and" ends at the space


def test_a_word_with_bti_inside_is_no_citation():
    assert citation_notes("A subtitle printed on the label; no EBTI ruling cited.", "3403.99", set(), STORE) == []


def test_notes_follow_the_order_of_first_occurrence_each_reference_once():
    text = "NLBTI5555/24 first, then DEBTI1234/22, and NLBTI5555/24 again."
    assert citation_notes(text, "3403.99", {"DEBTI1234/22"}, STORE) == [missing("NLBTI5555/24"), other("DEBTI1234/22", "8419.89")]


def test_an_excluded_ruling_counts_as_not_retrieved():
    retrieved = {"FRBTI0099/23", "DEBTI1234/22"} - {"FRBTI0099/23"}                    # an evaluation's own ruling
    assert citation_notes("FRBTI0099/23 matches.", "3403.99", retrieved, STORE) == [missing("FRBTI0099/23")]


def test_a_retrieved_reference_written_as_stored_is_found_even_off_the_pattern():
    notes = citation_notes("Ruling MTBTI2024 - 001 covers it.", "2710.19", {"MTBTI2024 - 001"}, STORE)
    assert notes == [other("MTBTI2024 - 001", "3403.99")]                               # no note for "MTBTI2024" alone


# --------------------------------------------------------------------------- review finding 5: shared forms, odd references
TWINS = BTIStore([{"reference": ref, "code": code, "chapter": code[:2], "member_state": ref[:2]} for ref, code in (
    ("GRBTIDEC-036-2025", "2102.20"), ("GRBTIDEC-036/2025", "2304.00"), ("NLBTI2025 - 0691", "0701.90"),
    ("DEBTI1234/22", "8419.89"), ("SEBTITV-2025- 15834", "6307.90"))])                 # as in the store of 2026-11-18


def test_a_reference_written_exactly_is_the_one_meant_although_its_normal_form_is_shared():
    only_dash = {"GRBTIDEC-036-2025"}                                                   # the slash one: another ruling
    assert citation_notes("See GRBTIDEC-036/2025.", "2102.20", only_dash, TWINS) == [missing("GRBTIDEC-036/2025")]
    both = {"GRBTIDEC-036-2025", "GRBTIDEC-036/2025"}
    assert citation_notes("See GRBTIDEC-036/2025.", "2102.20", both, TWINS) == [other("GRBTIDEC-036/2025", "2304.00")]
    assert citation_notes("See grbtidec-036-2025.", "2304.00", both, TWINS) == [other("GRBTIDEC-036-2025", "2102.20")]


def test_a_shared_form_written_neither_way_gets_no_note_when_one_of_its_rulings_was_retrieved():
    assert citation_notes("See GRBTIDEC-036.2025.", "2102.20", {"GRBTIDEC-036-2025"}, TWINS) == []
    assert citation_notes("See GRBTIDEC-036.2025.", "2102.20", set(), TWINS) == [missing("GRBTIDEC-036.2025")]


def test_a_stored_reference_off_the_pattern_is_named_whole_when_not_retrieved():
    assert citation_notes("As NLBTI2025 - 0691 shows.", "0701.90", set(), TWINS) == [missing("NLBTI2025 - 0691")]


def test_a_reference_never_runs_on_into_a_following_number():
    assert citation_notes("DEBTI1234/22 2 rulings agree.", "8419.89", set(), TWINS) == [missing("DEBTI1234/22")]
    assert citation_notes("cf. debti 1234/22", "3403.99", set(), TWINS) == [missing("DEBTI1234/22")]   # a space after BTI
    assert citation_notes("SEBTITV-2025- 15834 too", "6307.90", set(), TWINS) == [missing("SEBTITV-2025- 15834")]
