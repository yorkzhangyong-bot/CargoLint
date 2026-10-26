"""Pure guardrail functions: routing, the auto-accept lock, code existence and schema validation.

These are plain functions with no model, store or Streamlit dependency (constitution
Principle I). Routing is never a tool and never a model decision.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pydantic import ValidationError

from agent.config import CN8_VOTE_K, CN8_VOTE_SHARE, HS6_VOTE_K, HS6_VOTE_SHARE, THRESHOLD_MAX, THRESHOLD_MIN
from agent.schemas import (CN8_PATTERN, CODE_RE, TARIC10_PATTERN, Candidate, Cn8Gate, FlagKind, Hs6Gate, Hs6Vote, LineStatus,
                           RankOut, Route)

_CN8_RE = re.compile(CN8_PATTERN)
_TARIC10_RE = re.compile(TARIC10_PATTERN)
_PUNCT = re.compile(r"[^\w\s]")
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")   # CJK ideographs
EVIDENCE_FUZZY = 0.90   # feature 006: a quoted fragment may match a run of words of the line at this difflib ratio


class SchemaError(ValueError):
    """A model output did not match the expected schema."""


def _kind(flag_kind: FlagKind | str | None) -> FlagKind | None:
    if flag_kind is None:
        return None
    return FlagKind(flag_kind)


def _status(status: LineStatus | str) -> LineStatus:
    return LineStatus(status)


def route_line(
    flag_kind: FlagKind | str | None,
    top_confidence: int | None,
    status: LineStatus | str,
    ever_flagged: bool,
    threshold: int,
    ask_floor: int,
    cn8_question: str | None = None,
    cn8_error: str | None = None,
    hs6_vote: Hs6Vote | None = None,
    hs6_override_min: int | None = None,
) -> tuple[Route, str]:
    """The routing table from data-model.md §9. Returns (route, plain-language reason).

    Feature 004 (its data-model §6): on a checked, unflagged line, a failed CN-8 step (`cn8_error`) routes to review, like
    a failed check, and an open CN-8 question (`cn8_question`, the missing attribute) routes to ask the shipper.
    Feature 006: after those rules, the nearest rulings' vote (`hs6_vote`) decides the auto-accept through hs6_gate; only
    without an eligible ruling does the confidence meet the threshold, as before. Feature 008: with the switch on
    (`hs6_override_min`, None when off), the precedent override is one more case of that gate."""
    if not (THRESHOLD_MIN <= int(threshold) <= THRESHOLD_MAX):
        raise ValueError(f"threshold must be between {THRESHOLD_MIN} and {THRESHOLD_MAX}, got {threshold}")
    st = _status(status)
    if st == LineStatus.failed:
        return Route.review, "check failed — needs a human look"
    if st == LineStatus.pending:
        return Route.review, "not checked yet"

    kind = _kind(flag_kind)
    conf = top_confidence

    if kind == FlagKind.stop_word:
        return Route.ask_shipper, "stop-word in the description — ask the shipper what the goods actually are"
    if kind == FlagKind.vague:
        if conf is None or conf < ask_floor:
            shown = "no candidate" if conf is None else f"confidence {conf}"
            return Route.ask_shipper, f"vague description and {shown} below the ask floor {ask_floor} — ask the shipper"
        return Route.review, f"vague description; confidence {conf} at or above the ask floor {ask_floor} — needs a human look"

    if kind == FlagKind.ok and cn8_error:
        return Route.review, f"CN-8 step failed: {cn8_error} — needs a human look"
    if kind == FlagKind.ok and cn8_question:
        return Route.ask_shipper, f"the CN-8 depends on {cn8_question}, which the description does not state — ask the shipper"

    # flag ok (or no flag yet)
    if conf is None or conf <= 0:
        return Route.review, "no valid candidate — needs a human look"
    passed, gate = hs6_gate(conf, threshold, hs6_vote, hs6_override_min)
    if gate == Hs6Gate.no_rulings:
        if passed:
            if ever_flagged:
                return Route.review, (
                    f"ready to accept — confidence {conf} at or above the threshold {threshold}, "
                    "but the line was flagged or updated before; click Accept to confirm"
                )
            return Route.auto_accept, f"confidence {conf} at or above the threshold {threshold}"
        return Route.review, f"below threshold ({conf} < {threshold})"
    reason = _hs6_vote_reason(gate, hs6_vote)
    if not passed:
        return Route.review, f"{reason} — needs a human look"
    if ever_flagged:
        return Route.review, f"ready to accept — {reason}, but the line was flagged or updated before; click Accept to confirm"
    return Route.auto_accept, reason


def _votes_text(competing: Sequence[tuple[str, list[str]]]) -> str:
    """The codes the nearest rulings sit at, each with the issuing country of every ruling: "3926.90 (IE, DE)"."""
    return ", ".join(f"{code} ({', '.join(c or '?' for c in countries)})" for code, countries in competing)


def _hs6_vote_reason(gate: Hs6Gate, vote: Hs6Vote) -> str:
    """The route reason, and the audit note, of an HS-6 the vote decided."""
    voted = sum(len(countries) for _, countries in vote.competing)
    at = next(((code, countries) for code, countries in vote.competing if code == vote.majority), None)
    if gate == Hs6Gate.vote_agrees:
        return f"{len(at[1])} of {voted} nearest EBTI rulings at {_votes_text([at])}"
    if gate == Hs6Gate.vote_override:
        return f"rulings overrode the model: {len(at[1])} of {voted} agree on {at[0]}"
    if gate == Hs6Gate.vote_disagrees:
        supported = f", the model's candidate {vote.candidate}" if vote.candidate else ""
        return (f"the nearest EBTI rulings point to {at[0]} ({len(at[1])} of {voted}: "
                f"{', '.join(c or '?' for c in at[1])}){supported}")
    if gate == Hs6Gate.vote_tie:
        return f"the nearest EBTI rulings are split: {_votes_text(vote.competing)}"
    return f"only {len(at[1])} of {voted} nearest EBTI rulings at {at[0]}"


def hs6_auto_decided(flag_kind: FlagKind | str | None, top_confidence: int | None, status: LineStatus | str,
                     ever_flagged: bool, threshold: int, ask_floor: int, hs6_vote: Hs6Vote | None = None,
                     hs6_override_min: int | None = None) -> bool:
    """Feature 004: the HS-6 is decided by rule exactly where feature 001 auto-accepts, whatever the CN-8 step found;
    feature 006: through the vote of the nearest rulings; feature 008: or the precedent override, when switched on."""
    return route_line(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor,
                      hs6_vote=hs6_vote, hs6_override_min=hs6_override_min)[0] == Route.auto_accept


def hs6_choice(candidates: Sequence[Candidate], vote: Hs6Vote | None,
               gate: Hs6Gate | str | None) -> tuple[int | None, str | None]:
    """Feature 008: the candidate an auto-decided HS-6 is, as (rank, code): the one the rulings support when the precedent
    override decided it, otherwise the top one; (None, None) without a candidate."""
    if not candidates:
        return None, None
    if gate == Hs6Gate.vote_override and vote is not None and vote.candidate:
        return vote.candidate, candidates[vote.candidate - 1].code
    return 1, candidates[0].code


@dataclass(frozen=True)
class RulingVote:
    """Feature 006: the vote of the nearest eligible EBTI rulings on a code (a CN-8, or an HS-6), each ruling counted
    once."""

    majority: str | None                        # the code most of them sit at; None on a tie
    majority_share: float                       # its rulings over the rulings that voted
    competing: list[tuple[str, list[str]]]      # every code with a vote and the issuing country of each ruling, most first
    model_is_majority: bool                     # the model's code is the majority
    agrees: bool                                # ... and its share is at least the vote share

    @property
    def majority_cn8(self) -> str | None:
        """The majority, by its CN-8 name."""
        return self.majority


def ruling_vote(nearest: Sequence[tuple[str, str]], model_code: str | None, k: int, share: float) -> RulingVote | None:
    """Feature 006: the vote of the k nearest eligible rulings, given nearest first as (code, issuing country). The
    majority is the code with the most rulings, none on a tie; the model's code agrees when it is the majority with a
    share of at least `share` (exactly the share counts). None when no ruling is eligible."""
    voters = list(nearest[:k])
    if not voters:
        return None
    countries: dict[str, list[str]] = {}
    for code, country in voters:
        countries.setdefault(code, []).append(country)
    top = max(len(c) for c in countries.values())
    leaders = [code for code, c in countries.items() if len(c) == top]
    majority = leaders[0] if len(leaders) == 1 else None
    competing = sorted(countries.items(), key=lambda item: -len(item[1]))   # ties keep the nearest-first order
    is_majority = model_code is not None and model_code == majority
    return RulingVote(majority, round(top / len(voters), 4), competing, is_majority,
                      is_majority and top / len(voters) >= share)


def cn8_ruling_vote(nearest: Sequence[tuple[str, str]], model_cn8: str | None, k: int = CN8_VOTE_K,
                    share: float = CN8_VOTE_SHARE) -> RulingVote | None:
    """Feature 006, constitution 1.4.0: ruling_vote on the CN-8, given nearest first as (CN-8, issuing country)."""
    return ruling_vote(nearest, model_cn8, k, share)


def hs6_ruling_vote(nearest: Sequence[tuple[str, str]], candidates: Sequence[str], k: int = HS6_VOTE_K,
                    share: float = HS6_VOTE_SHARE) -> Hs6Vote | None:
    """Feature 006: ruling_vote on the model's top HS-6, given the rulings nearest first as (HS-6, issuing country) and
    the model's candidates top first; `candidate` is 2 or 3 when the majority is that candidate. None when no ruling is
    eligible."""
    vote = ruling_vote(nearest, candidates[0] if candidates else None, k, share)
    if vote is None:
        return None
    supported = next((n for n, code in enumerate(candidates[:3], start=1) if n > 1 and code == vote.majority), None)
    return Hs6Vote(majority=vote.majority, majority_share=vote.majority_share, competing=vote.competing,
                   model_is_majority=vote.model_is_majority, agrees=vote.agrees, candidate=supported)


def hs6_gate(confidence: int, threshold: int, vote: Hs6Vote | None = None,
             override_min: int | None = None) -> tuple[bool, Hs6Gate]:
    """Whether an HS-6 is auto-accepted, and the rule that decided it (feature 006): the ruling vote decides, as
    cn8_gate's. Only without an eligible ruling does the model estimate meet the threshold, as before (at the threshold
    counts). Feature 008, the precedent override: with the switch on (`override_min`, None when off), a majority at the
    model's candidate 2 or 3 of at least `override_min` rulings decides that candidate (exactly the minimum counts)."""
    if vote is None:
        return int(confidence) >= int(threshold), Hs6Gate.no_rulings
    if vote.agrees:
        return True, Hs6Gate.vote_agrees
    if vote.majority is None:
        return False, Hs6Gate.vote_tie
    if vote.model_is_majority:
        return False, Hs6Gate.vote_share_low
    at_majority = sum(len(countries) for code, countries in vote.competing if code == vote.majority)
    if override_min is not None and vote.candidate and at_majority >= override_min:
        return True, Hs6Gate.vote_override
    return False, Hs6Gate.vote_disagrees


def cn8_gate(confidence: int, threshold: int, single_line: bool, precedent_conflict: bool = False,
             vote: RulingVote | None = None) -> tuple[bool, Cn8Gate]:
    """Whether a CN-8 is written by rule, and the rule that decided it (constitution 1.4.0): the only CN-8 line is
    written; a cited ruling at another CN-8 keeps it to confirm (feature 004, iteration 2); otherwise the ruling vote
    decides. Only without an eligible ruling does the model estimate meet the threshold, as feature 004 did (at the
    threshold counts)."""
    if single_line:
        return True, Cn8Gate.single_line
    if precedent_conflict:
        return False, Cn8Gate.precedent_conflict
    if vote is None:
        return int(confidence) >= int(threshold), Cn8Gate.no_rulings
    if vote.agrees:
        return True, Cn8Gate.vote_agrees
    if vote.majority is None:
        return False, Cn8Gate.vote_tie
    return False, (Cn8Gate.vote_share_low if vote.model_is_majority else Cn8Gate.vote_disagrees)


def cn8_written_by_rule(confidence: int, threshold: int, single_line: bool, precedent_conflict: bool = False,
                        vote: RulingVote | None = None) -> bool:
    """Whether cn8_gate writes the CN-8."""
    return cn8_gate(confidence, threshold, single_line, precedent_conflict, vote)[0]


def _normalise(text: str) -> str:
    """Lower case, accents and punctuation stripped, whitespace and line breaks collapsed."""
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", (text or "").lower()) if not unicodedata.combining(ch))
    return " ".join(_PUNCT.sub(" ", plain).split())


def _found(fragment: str, line: str) -> bool:
    """The fragment is a phrase of the line. Chinese has no spaces, so a Chinese fragment may sit inside a longer word."""
    if _CJK.search(fragment):
        return fragment in line
    return f" {fragment} " in f" {line} "


def _near(fragment: str, line: str) -> bool:
    """A run of whole words of the line matches the fragment at a difflib ratio of EVIDENCE_FUZZY or more. Whole words,
    so a short word never matches inside a longer one; only runs of about the fragment's length can reach the ratio."""
    if _CJK.search(fragment):
        return False
    words, size = line.split(), len(fragment)
    for start in range(len(words)):
        run = ""
        for word in words[start:]:
            run = f"{run} {word}" if run else word
            if len(run) > size * 1.25:
                break
            if len(run) >= size * 0.8:
                m = SequenceMatcher(None, fragment, run, autojunk=False)
                if m.quick_ratio() >= EVIDENCE_FUZZY and m.ratio() >= EVIDENCE_FUZZY:
                    return True
    return False


def evidence_match(evidence: str, line_text: str) -> str | None:
    """Feature 006: the rule that accepts a quote as words of the line, or None. Both sides are normalised (lower case,
    accents and punctuation stripped, whitespace and line breaks collapsed) and the quote is split at ";". "exact":
    every fragment is a phrase of the line; "fuzzy": every fragment is that or matches a run of words of the line at a
    ratio of 90 % or more, and at least one needed the ratio. Only the line is compared, so a quote from a CN-8 label,
    the HS-6 label or a ruling is rejected unless the line says the same. Empty evidence is no evidence."""
    line = _normalise(line_text)
    fragments = [f for f in (_normalise(part) for part in (evidence or "").split(";")) if f]
    if not fragments:
        return None
    rule = "exact"
    for fragment in fragments:
        if _found(fragment, line):
            continue
        if not _near(fragment, line):
            return None
        rule = "fuzzy"
    return rule


def evidence_in_line(evidence: str, line_text: str) -> bool:
    """Whether evidence_match accepts the quote."""
    return evidence_match(evidence, line_text) is not None


def cn8_precedent_conflict(cn8: str | None, precedent_code: str | None) -> bool:
    """Iteration 2: a cited ruling conflicts when its CN code is not at the chosen CN-8."""
    return bool(cn8 and precedent_code and precedent_code[:8] != cn8)


def validate_cn8(code: Any, options: list[tuple[str, str]]) -> bool:
    """Feature 004, FR-002: an eight-digit code that is one of the decided HS-6's CN 2026 lines."""
    if not isinstance(code, str) or _CN8_RE.match(code) is None:
        return False
    return code in {c for c, _ in options}


def validate_taric10(code: Any, subdivisions: list[str]) -> bool:
    """Feature 004, FR-012: a ten-digit code that is one of the snapshot's subdivisions for the written CN-8."""
    if not isinstance(code, str) or _TARIC10_RE.match(code) is None:
        return False
    return code in set(subdivisions)


def effective_route_of(v: Any) -> str:
    """The route the clerk sees for a line version (feature 004, data-model §6): an open CN-8 question or a failed CN-8
    step overrides a clerk's HS-6 acceptance with the computed route; any other clerk decision wins as before."""
    cn8 = getattr(v, "cn8", None)
    cn8_open = cn8 is not None and bool(cn8.question or cn8.error)
    if v.decision is not None and not (cn8_open and v.decision.route.value == "accepted"):
        return v.decision.route.value
    return v.computed_route.value


def can_accept(flag_kind: FlagKind | str | None) -> bool:
    """The lock (FR-022): only an unflagged current version may be accepted."""
    return _kind(flag_kind) == FlagKind.ok


def is_contradiction(previous_candidates: list[Candidate], new_top: Candidate | None) -> tuple[bool, str | None]:
    """FR-038 fixed rule: a reply contradicts the file when the new top candidate's chapter
    differs from every chapter among the previous version's candidates."""
    if not previous_candidates or new_top is None:
        return False, None
    chapters = {c.chapter for c in previous_candidates}
    if new_top.chapter in chapters:
        return False, None
    prev = previous_candidates[0]
    note = (
        f"Reply moves the line from chapter {prev.chapter} ({prev.code}) to chapter "
        f"{new_top.chapter} ({new_top.code}) — the reply may describe different goods than the file"
    )
    return True, note


def validate_code(code: Any, index: Any) -> bool:
    """FR-013 / FR-044: well-formed HS-6 (`####.##`) and present in the loaded nomenclature."""
    if not isinstance(code, str) or CODE_RE.match(code) is None:
        return False
    if index is None:
        return False
    return code in index


def validate_classification(raw: Any) -> RankOut:
    """Strict schema validation of a ranking output (unknown fields are dropped, never trusted)."""
    if isinstance(raw, RankOut):
        return raw
    try:
        return RankOut.model_validate(raw)
    except ValidationError as exc:
        raise SchemaError(str(exc)) from exc
