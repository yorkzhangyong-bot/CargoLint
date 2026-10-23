"""Pure guardrail functions: routing, the auto-accept lock, code existence and schema validation.

These are plain functions with no model, store or Streamlit dependency (constitution
Principle I). Routing is never a tool and never a model decision.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from agent.config import THRESHOLD_MAX, THRESHOLD_MIN
from agent.schemas import CN8_PATTERN, CODE_RE, Candidate, FlagKind, LineStatus, RankOut, Route

_CN8_RE = re.compile(CN8_PATTERN)


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
) -> tuple[Route, str]:
    """The routing table from data-model.md §9. Returns (route, plain-language reason).

    Feature 004 (its data-model §6): on a checked, unflagged line, a failed CN-8 step (`cn8_error`) routes to review, like
    a failed check, and an open CN-8 question (`cn8_question`, the missing attribute) routes to ask the shipper."""
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
    if conf >= threshold:
        if ever_flagged:
            return Route.review, (
                f"ready to accept — confidence {conf} at or above the threshold {threshold}, "
                "but the line was flagged or updated before; click Accept to confirm"
            )
        return Route.auto_accept, f"confidence {conf} at or above the threshold {threshold}"
    return Route.review, f"below threshold ({conf} < {threshold})"


def hs6_auto_decided(flag_kind: FlagKind | str | None, top_confidence: int | None, status: LineStatus | str,
                     ever_flagged: bool, threshold: int, ask_floor: int) -> bool:
    """Feature 004: the HS-6 is decided by rule exactly where feature 001 auto-accepts, whatever the CN-8 step found."""
    return route_line(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor)[0] == Route.auto_accept


def cn8_written_by_rule(confidence: int, threshold: int, single_line: bool) -> bool:
    """Feature 004, clarification Q4: a CN-8 is written by rule when it is the only line, or its confidence meets the
    auto-accept threshold (at the threshold counts, as for HS-6 auto-accept)."""
    return bool(single_line) or int(confidence) >= int(threshold)


def validate_cn8(code: Any, options: list[tuple[str, str]]) -> bool:
    """Feature 004, FR-002: an eight-digit code that is one of the decided HS-6's CN 2026 lines."""
    if not isinstance(code, str) or _CN8_RE.match(code) is None:
        return False
    return code in {c for c, _ in options}


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
