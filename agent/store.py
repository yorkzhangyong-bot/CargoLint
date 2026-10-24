"""The line store: the only module that reads or writes line data.

Backed by any mutable mapping (a plain dict in tests, `st.session_state` in the app). Every
mutation recomputes routes with the pure routing function and appends an audit record.
No Streamlit import here (constitution, Architecture invariants).
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable, MutableMapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, MAX_DESC_CHARS, THRESHOLD_MAX, THRESHOLD_MIN
from agent.routing import (
    can_accept,
    cn8_precedent_conflict,
    cn8_written_by_rule,
    effective_route_of,
    hs6_auto_decided,
    route_line,
    validate_cn8,
    validate_code,
    validate_taric10,
)
from agent.schemas import (
    ORIGIN_PATTERN,
    Actor,
    ChangeKind,
    ChosenHow,
    Classification,
    Cn8Choice,
    CreatedBy,
    Decision,
    DecisionRecord,
    DecisionRoute,
    DescriptionCheck,
    Line,
    LineStatus,
    LineVersion,
    ParsedLine,
    Precedent,
    ShipperRef,
    Shipment,
    Source,
    SourceFile,
    SourceKind,
    TaricOutcome,
    TaricRule,
    Usage,
    WrittenBy,
)
from agent.taric_rules import code_to_write


class LockedError(Exception):
    """Accept is locked while the current version is flagged (FR-022)."""


class UnknownCodeError(Exception):
    """A decided code is malformed or not in the nomenclature (FR-013, FR-023)."""


class NoShipmentError(Exception):
    pass


ACCEPTED_ROUTES = ("auto_accept", "accepted")


class LineStore:
    def __init__(
        self,
        backend: MutableMapping[str, Any] | None = None,
        index: Any = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._b: MutableMapping[str, Any] = backend if backend is not None else {}
        self.index = index
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------ shipment
    @property
    def shipment(self) -> Shipment:
        s = self._b.get("shipment")
        if s is None:
            raise NoShipmentError("no shipment loaded")
        return s

    def has_shipment(self) -> bool:
        return self._b.get("shipment") is not None

    def new_shipment(
        self,
        source: SourceFile | None = None,
        reference: str = "",
        shipper: ShipperRef | None = None,
        threshold: int = DEFAULT_THRESHOLD,
        hybrid: bool = True,
        ask_floor: int = ASK_FLOOR,
        origin: str | None = None,
        destination: str | None = None,
        mode: str | None = None,
    ) -> Shipment:
        s = Shipment(
            id=uuid4().hex[:12], reference=reference, shipper=shipper or ShipperRef(), threshold=threshold,
            ask_floor=ask_floor, hybrid_search=hybrid, source=source, origin=origin, destination=destination,
            mode=mode, created_at=self._clock(),
        )
        self._b["shipment"] = s
        self._b["files"] = {}
        self._b["replies"] = {}
        return s

    # ------------------------------------------------------------------ lines
    @property
    def lines(self) -> list[Line]:
        return self.shipment.lines

    def get_line(self, line_no: int) -> Line:
        for line in self.shipment.lines:
            if line.line_no == line_no:
                return line
        raise KeyError(f"line {line_no} not found")

    def add_lines(self, parsed: list[ParsedLine], created_by: CreatedBy) -> list[Line]:
        s = self.shipment
        added: list[Line] = []
        for p in parsed:
            line_no = len(s.lines) + 1
            v = LineVersion(
                version_no=1, created_at=self._clock(), created_by=created_by, text_zh=p.text_zh, text_en=p.text_en,
                truncated=p.truncated, unreadable=p.unreadable,
            )
            if p.unreadable:
                v.status = LineStatus.checked  # nothing to classify; never guessed (FR-004)
            line = Line(line_no=line_no, source_ref=p.source_ref or f"line {line_no}", qty=p.qty, weight_kg=p.weight_kg,
                        volume_cbm=p.volume_cbm, value=p.value, versions=[v])
            s.lines.append(line)
            self._recompute(line, Actor.routing_rule)
            added.append(line)
        return added

    def update_check(self, line_no: int, check: DescriptionCheck) -> None:
        line = self.get_line(line_no)
        v = line.current
        if check.status == LineStatus.failed:
            v.status = LineStatus.failed
            v.error_reason = check.error_reason or "description check failed"
            self._recompute(line, Actor.system, ChangeKind.line_failed)
            return
        v.flag = check.flag
        if check.flag is not None and check.flag.pure_stop_word:
            v.status = LineStatus.checked
            v.candidates = []
        if check.flag is not None and check.flag.rule_source is not None and check.flag.matched_term:
            kind = SourceKind.firm_rule if check.flag.rule_source.value == "firm_stop_words" else SourceKind.ics2_rule
            prefix = {"firm_stop_words": "firm", "ics2_unacceptable": "ics2", "ics2_stop_words": "ics2sw"}.get(
                check.flag.rule_source.value, "rule")
            sid = f"{prefix}:{check.flag.matched_term}"
            if all(src.id != sid for src in v.sources):
                v.sources.append(Source(id=sid, kind=kind, title=f"{check.flag.source_doc or check.flag.rule_source.value} — "
                                                               f"\"{check.flag.matched_term}\"", excerpt=check.flag.reason))
        self._recompute(line, Actor.routing_rule)

    def update_classification(self, line_no: int, cls: Classification) -> None:
        line = self.get_line(line_no)
        v = line.current
        if cls.status == LineStatus.failed:
            v.status = LineStatus.failed
            v.error_reason = cls.error_reason or "classification failed"
            v.candidates = []
            self._recompute(line, Actor.system, ChangeKind.line_failed)
            return
        v.candidates = list(cls.candidates)
        v.no_valid_candidate = cls.no_valid_candidate
        v.retrieval_trace = cls.retrieval_trace
        existing = {s.id for s in v.sources}
        v.sources.extend(s for s in cls.sources if s.id not in existing)
        v.status = LineStatus.checked
        v.error_reason = None
        self._recompute(line, Actor.routing_rule)

    def update_precedents(self, line_no: int, by_code: dict[str, list[Precedent]]) -> None:
        line = self.get_line(line_no)
        v = line.current
        for c in v.candidates:
            hits = by_code.get(c.code) or []
            c.precedent = hits[0] if hits else None
            if c.precedent is not None:
                sid = f"bti:{c.precedent.reference}"
                if all(s.id != sid for s in v.sources):
                    v.sources.append(Source(id=sid, kind=SourceKind.bti,
                                            title=f"BTI {c.precedent.member_state} {c.precedent.reference} → {c.precedent.code}",
                                            excerpt=c.precedent.description[:300]))
        v.precedents_checked = True

    def mark_failed(self, line_no: int, reason: str) -> None:
        line = self.get_line(line_no)
        v = line.current
        v.status = LineStatus.failed
        v.error_reason = reason
        self._recompute(line, Actor.system, ChangeKind.line_failed)

    def add_version(self, line_no: int, version: LineVersion) -> LineVersion:
        line = self.get_line(line_no)
        previous_route = self.effective_route(line)
        previous_text = line.current.display_text
        version.version_no = len(line.versions) + 1
        version.decision = None
        if version.created_at is None:
            version.created_at = self._clock()
        line.versions.append(version)
        if version.created_by == CreatedBy.clerk:   # feature 005 (contracts/backend.md §1): the clerk's edit
            note = ("re-checked by clerk, description unchanged" if version.display_text == previous_text
                    else "description updated by clerk")
            self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=version.version_no,
                                       change=ChangeKind.version_added, previous=previous_text, new=version.display_text,
                                       actor=Actor.clerk, note=note))
        else:
            change = ChangeKind.reply_applied if version.created_by == CreatedBy.shipper_reply else ChangeKind.version_added
            actor = Actor.shipper_reply if version.created_by == CreatedBy.shipper_reply else Actor.system
            self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=version.version_no, change=change,
                                       previous=previous_route, new=None, actor=actor, note=version.contradiction_note))
        self._recompute(line, Actor.routing_rule)
        return version

    def update_description(self, line_no: int, text_zh: str, text_en: str) -> LineVersion:
        """Feature 005 (FR-017): the clerk's edit of a line's description, as a new current version created by the clerk.
        The earlier versions stay (Principle V); `agent.recheck_line` checks the new one. The edit is untrusted text,
        capped like a file (Principle II): an empty or over-cap text, or an unknown line, changes nothing."""
        zh, en = (text_zh or "").strip(), (text_en or "").strip()
        if not zh and not en:
            raise ValueError("write the goods description")
        for language, text in (("Chinese", zh), ("English", en)):
            if len(text) > MAX_DESC_CHARS:
                raise ValueError(f"the {language} text is over {MAX_DESC_CHARS} characters")
        self.get_line(line_no)
        return self.add_version(line_no, LineVersion(created_by=CreatedBy.clerk, text_zh=zh, text_en=en))

    # ------------------------------------------------------------------ decisions
    def set_decision(self, line_no: int, decision: Decision) -> Decision:
        line = self.get_line(line_no)
        v = line.current
        previous = self.effective_route(line)
        if decision.route == DecisionRoute.accepted:
            if v.flag is None or not can_accept(v.flag.kind):
                raise LockedError(f"line {line_no} is flagged ({v.flag.kind.value if v.flag else 'unchecked'}); "
                                  "accept is locked until the description is updated and re-checked")
            if not validate_code(decision.decided_code, self.index):
                raise UnknownCodeError(f"code {decision.decided_code!r} is not in the loaded nomenclature")
            codes = [c.code for c in v.candidates]
            how = ChosenHow.top if codes and decision.decided_code == codes[0] else (
                ChosenHow.other_candidate if decision.decided_code in codes else ChosenHow.typed)
            decision = decision.model_copy(update={"chosen_how": how, "at": self._clock()})
            if v.cn8 is not None and v.cn8.hs6 != decision.decided_code:   # feature 004: a new HS-6 starts the CN-8 again
                v.cn8, v.taric = None, None
                for c in v.candidates:
                    c.cn8, c.taric10 = None, None
            else:   # the same HS-6 again: the clerk's own CN-8 and TARIC-10 confirmations come back with it
                kept = {}
                if v.cn8 is not None and v.cn8.written_by == WrittenBy.clerk:
                    kept["decided_cn8"] = v.cn8.cn8
                if v.taric is not None and v.taric.written_by == WrittenBy.clerk:
                    kept["decided_taric10"] = v.taric.taric10
                decision = decision.model_copy(update=kept)
        else:
            decision = decision.model_copy(update={"decided_code": None, "chosen_how": None, "at": self._clock()})
        v.decision = decision
        self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=v.version_no,
                                   change=ChangeKind.clerk_decision, previous=previous, new=decision.route.value,
                                   actor=Actor.clerk))
        if decision.route == DecisionRoute.accepted:
            self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=v.version_no,
                                       change=ChangeKind.code_decided, previous=v.top_code, new=decision.decided_code,
                                       actor=Actor.clerk, note=decision.chosen_how.value if decision.chosen_how else None))
            self._reevaluate_cn8(line, self.shipment.threshold, Actor.routing_rule)   # feature 004: the HS-6 is decided
            self._reapply_taric(line, Actor.routing_rule)                             # again; re-read its CN-8 and TARIC-10
        return decision

    def accept_lock_reason(self, line: Line) -> str | None:
        """Why Accept is unavailable for this line, or None when the clerk may accept it (FR-022/FR-023)."""
        v = line.current
        if v.status != LineStatus.checked:
            return "the line has not been checked successfully"
        if v.flag is None or not can_accept(v.flag.kind):
            kind = v.flag.kind.value.replace("_", "-") if v.flag else "unchecked"
            below = (f"Below the {self.shipment.threshold}% threshold and " if (v.top_confidence or 0) < self.shipment.threshold else "")
            return f"{below}flagged ({kind}), so auto-accept is locked until the description is updated and re-checked"
        return None

    def set_shipper(self, name: str, known: bool = False, past_shipment_count: int = 0) -> None:
        self.shipment.shipper = ShipperRef(name=name or "New shipper", known=known, past_shipment_count=past_shipment_count)

    def clear_decision(self, line_no: int) -> None:
        line = self.get_line(line_no)
        line.current.decision = None
        self._recompute(line, Actor.routing_rule)

    # ------------------------------------------------------------------ settings
    def set_threshold(self, value: int) -> None:
        value = int(value)
        if not (THRESHOLD_MIN <= value <= THRESHOLD_MAX):
            raise ValueError(f"threshold must be between {THRESHOLD_MIN} and {THRESHOLD_MAX}")
        s = self.shipment
        s.threshold = value
        for line in s.lines:
            v = line.current
            if v.decision is not None or v.flag is None or v.flag.kind.value != "ok":
                continue
            self._recompute(line, Actor.threshold_change, ChangeKind.threshold_recomputed)
        for line in s.lines:   # feature 004: CN-8 codes the clerk has not confirmed follow the threshold too, and with them
            self._reevaluate_cn8(line, value)   # any TARIC-10 auto-completed from them
            self._reapply_taric(line, Actor.threshold_change)

    def set_hybrid(self, value: bool) -> None:
        self.shipment.hybrid_search = bool(value)

    def set_taric_origin(self, code: str | None) -> str:
        """Feature 004 (FR-017): the goods' origin for TARIC, two letters after upper-casing. Anything else raises
        ValueError and the previous origin stays. The agent's apply_taric_origin re-applies the rules after it."""
        value = (code or "").strip().upper()
        if re.fullmatch(ORIGIN_PATTERN, value) is None:
            raise ValueError(f"the origin must be two letters, such as CN or US, not {code!r}")
        self.shipment.taric_origin = value
        return value

    def recompute_routes(self) -> None:
        for line in self.shipment.lines:
            self._recompute(line, Actor.routing_rule)

    def finalize_check(self) -> dict[str, int]:
        for line in self.shipment.lines:
            v = line.current
            if v.status == LineStatus.pending:
                v.status = LineStatus.failed
                v.error_reason = v.error_reason or "not checked — a step did not run"
                self._recompute(line, Actor.system, ChangeKind.line_failed)
        return self.counts()

    def _recompute(self, line: Line, actor: Actor, change: ChangeKind = ChangeKind.route_computed) -> None:
        s = self.shipment
        v = line.current
        kind = v.flag.kind if v.flag is not None else None
        needs_click = line.ever_flagged or v.created_by == CreatedBy.shipper_reply  # never auto-accept after an update (FR-022)
        c = v.cn8
        route, reason = route_line(kind, v.top_confidence, v.status, needs_click, s.threshold, s.ask_floor,
                                   cn8_question=c.deciding_attribute if c is not None and c.question else None,
                                   cn8_error=c.error if c is not None and c.error else None)
        if v.unreadable and v.status == LineStatus.checked and not v.candidates:
            reason = "unreadable description — needs a human look"
        changed = route != v.computed_route or reason != v.route_reason
        previous = v.computed_route.value
        v.computed_route = route
        v.route_reason = reason
        if changed:
            self.record(DecisionRecord(at=self._clock(), line_no=line.line_no, version_no=v.version_no, change=change,
                                       previous=previous, new=route.value, actor=actor, note=reason))
        self._reevaluate_cn8(line, s.threshold, actor)   # feature 004: an HS-6 decided again re-reads its CN-8 and TARIC-10
        self._reapply_taric(line, actor)

    # ------------------------------------------------------------------ derived
    def effective_route(self, line: Line) -> str:
        return effective_route_of(line.current)

    def needs_action(self, line: Line) -> bool:
        return self.effective_route(line) not in ACCEPTED_ROUTES

    def ready_to_accept(self, line: Line) -> bool:
        v = line.current
        return (
            line.ever_flagged and v.decision is None and v.status == LineStatus.checked and v.flag is not None
            and v.flag.kind.value == "ok" and v.top_confidence is not None and v.top_confidence >= self.shipment.threshold
        )

    def decided_code(self, line: Line) -> tuple[str | None, str | None]:
        v = line.current
        if v.decision is not None and v.decision.route == DecisionRoute.accepted:
            return v.decision.decided_code, (v.decision.chosen_how.value if v.decision.chosen_how else None)
        if v.decision is None and v.candidates and self._hs6_auto_decided(line):
            return v.candidates[0].code, ChosenHow.auto.value
        return None, None

    def _hs6_auto_decided(self, line: Line) -> bool:
        s, v = self.shipment, line.current
        needs_click = line.ever_flagged or v.created_by == CreatedBy.shipper_reply
        return hs6_auto_decided(v.flag.kind if v.flag is not None else None, v.top_confidence, v.status, needs_click,
                                s.threshold, s.ask_floor)

    # ------------------------------------------------------------------ feature 004: the CN-8 choice
    def set_cn8_result(self, line_no: int, choice: Cn8Choice) -> None:
        """Store the CN-8 step's result on the current version, record it and recompute the route (data-model §3, §5)."""
        line = self.get_line(line_no)
        v = line.current
        v.cn8, v.taric = choice, None   # a new CN-8 result: the TARIC step runs again for it
        for c in v.candidates:   # only the decided HS-6 candidate carries a CN-8
            c.cn8, c.taric10 = (choice.cn8 if c.code == choice.hs6 else None), None
        if choice.question:
            self._record_code(line, ChangeKind.cn8_question, None, Actor.routing_rule, choice.question)
        elif choice.cn8 and choice.written_by == WrittenBy.rule:
            note = ("single CN-8 line" if len(choice.options) == 1
                    else f"written by rule (confidence {choice.confidence} ≥ threshold {self.shipment.threshold})")
            self._record_code(line, ChangeKind.cn8_written, choice.cn8, Actor.routing_rule, note)
        elif choice.cn8 and choice.written_by is None and not choice.error:   # FR-020: a suggestion is an outcome too
            p = choice.precedent
            if cn8_precedent_conflict(choice.cn8, p.code if p else None):
                note = f"to confirm: the cited ruling {p.reference} classifies under {p.code[:8]}, not {choice.cn8}"
            elif choice.confidence < self.shipment.threshold:
                note = f"to confirm: confidence {choice.confidence} < threshold {self.shipment.threshold}"
            else:
                note = "to confirm"
            self._record_code(line, ChangeKind.cn8_pending, choice.cn8, Actor.routing_rule, note)
        self._recompute(line, Actor.routing_rule)

    def confirm_cn8(self, line_no: int, cn8: str) -> None:
        """The clerk writes a CN-8. It closes an open question or a failed step. On an auto-accepted line it records
        the clerk's acceptance of the auto HS-6 (research R-09)."""
        line = self.get_line(line_no)
        v = line.current
        hs6, how = self.decided_code(line)
        if not hs6:
            raise LockedError(f"line {line_no}: the HS-6 is not decided, so a CN-8 cannot be confirmed yet")
        same = v.cn8 is not None and v.cn8.hs6 == hs6
        options = v.cn8.options if same else (self.index.cn8_lines(hs6) if self.index is not None else [])
        if not validate_cn8(cn8, options):
            raise UnknownCodeError(f"CN-8 {cn8!r} is not a CN 2026 line under {hs6}")
        previous_cn8 = v.cn8.cn8 if same else None
        previous_route = self.effective_route(line)
        base = v.cn8 if same else Cn8Choice(hs6=hs6, options=options)
        update = {"cn8": cn8, "written_by": WrittenBy.clerk, "question": None, "error": None}
        if previous_cn8 != cn8:   # the model's estimate, evidence and ruling were about another code, or none
            update |= {"confidence": 0, "evidence": "", "rationale": "", "precedent": None}
        v.cn8 = base.model_copy(update=update)
        if previous_cn8 != cn8:   # another CN-8: its TARIC outcome no longer applies; the TARIC step runs again
            v.taric = None
        for c in v.candidates:
            c.cn8 = cn8 if c.code == hs6 else None
            c.taric10 = c.taric10 if v.taric is not None else None
        if v.decision is None:
            v.decision = Decision(route=DecisionRoute.accepted, decided_code=hs6, chosen_how=ChosenHow(how or "auto"),
                                  decided_cn8=cn8, at=self._clock())
            self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=v.version_no, change=ChangeKind.clerk_decision,
                                       previous=previous_route, new=DecisionRoute.accepted.value, actor=Actor.clerk,
                                       note="CN-8 confirmed on an auto-accepted line"))
        else:
            v.decision = v.decision.model_copy(update={"decided_cn8": cn8})
        self._record_code(line, ChangeKind.cn8_written, cn8, Actor.clerk, "confirmed by the clerk", previous=previous_cn8)
        self._reapply_taric(line, Actor.routing_rule)   # a single subdivision is written now that the CN-8 is
        self._recompute(line, Actor.clerk)

    def decided_cn8(self, line: Line) -> str | None:
        """The written CN-8 while the HS-6 is decided (data-model §6, top-down); None otherwise."""
        hs6, _ = self.decided_code(line)
        c = line.current.cn8
        if not hs6 or c is None or c.hs6 != hs6 or not c.cn8 or c.written_by is None or c.question or c.error:
            return None
        return c.cn8

    def cn8_pending(self, line: Line) -> bool:
        """A CN-8 suggestion waiting for the clerk: chosen, not written, no open question, no failure."""
        hs6, _ = self.decided_code(line)
        c = line.current.cn8
        return bool(hs6 and c is not None and c.hs6 == hs6 and c.cn8 and c.written_by is None and not c.question
                    and not c.error)

    def _reevaluate_cn8(self, line: Line, threshold: int, actor: Actor = Actor.threshold_change) -> None:
        """Re-apply the threshold write rule to a CN-8 the clerk has not confirmed, only while its HS-6 is decided and
        the choice was made under that HS-6. Otherwise decided_cn8 does not return it, so nothing changes and nothing is
        recorded; the choice is re-evaluated once the HS-6 is decided again."""
        c = line.current.cn8
        if c is None or not c.cn8 or c.written_by == WrittenBy.clerk or c.question or c.error:
            return
        if c.hs6 != self.decided_code(line)[0]:
            return
        written = cn8_written_by_rule(c.confidence, threshold, len(c.options) == 1,
                                      precedent_conflict=cn8_precedent_conflict(c.cn8, c.precedent.code if c.precedent else None))
        if written and c.written_by is None:
            line.current.cn8 = c.model_copy(update={"written_by": WrittenBy.rule})
            self._record_code(line, ChangeKind.cn8_written, c.cn8, actor,
                              f"written by rule (confidence {c.confidence} ≥ threshold {threshold})")
        elif not written and c.written_by == WrittenBy.rule:
            line.current.cn8 = c.model_copy(update={"written_by": None})
            self._record_code(line, ChangeKind.threshold_recomputed, None, actor,
                              f"CN-8 {c.cn8} back to a suggestion (confidence {c.confidence} < threshold {threshold})",
                              previous=c.cn8)

    def _record_code(self, line: Line, change: ChangeKind, new: str | None, actor: Actor, note: str,
                     previous: str | None = None) -> None:
        self.record(DecisionRecord(at=self._clock(), line_no=line.line_no, version_no=line.current.version_no, change=change,
                                   previous=previous, new=new, actor=actor, note=note))

    # ------------------------------------------------------------------ feature 004: the TARIC outcome
    def set_taric_result(self, line_no: int, outcome: TaricOutcome) -> None:
        """Store the TARIC step's outcome for the shipment's origin and record which rule applied (data-model §4, §5).
        What is written is re-derived here with `code_to_write`. A TARIC-10 the clerk confirmed, or a question sent to
        the shipper, stays while the subdivisions are the same: they do not depend on the origin (FR-018)."""
        line = self.get_line(line_no)
        v = line.current
        prev = v.taric
        same = prev is not None and prev.subdivisions == outcome.subdivisions
        if same and prev.written_by == WrittenBy.clerk:
            outcome = outcome.model_copy(update={"taric10": prev.taric10, "written_by": WrittenBy.clerk, "question": None})
        else:
            code = code_to_write(outcome.rule, outcome.subdivisions, self.decided_cn8(line) is not None)
            outcome = outcome.model_copy(update={"taric10": code, "written_by": WrittenBy.rule if code else None,
                                                 "question": prev.question if same else None})
        v.taric = outcome
        hs6 = v.cn8.hs6 if v.cn8 is not None else None
        for c in v.candidates:   # the highlighted subdivision rides on the decided HS-6 candidate; it is never written
            c.taric10 = outcome.suggestion.code if outcome.suggestion is not None and c.code == hs6 else None
        change, note = self._taric_rule_note(outcome)
        if outcome.written_by == WrittenBy.clerk:
            change, note = ChangeKind.taric_written, f"confirmed by the clerk, kept; {note}"
        previous = prev.taric10 if prev is not None and prev.taric10 != outcome.taric10 else None
        self._record_code(line, change, outcome.taric10, Actor.routing_rule, note, previous=previous)

    @staticmethod
    def _taric_where(t: TaricOutcome) -> str:
        return (f"snapshot {t.snapshot_date}; " if t.snapshot_date else "") + f"origin {t.origin}"

    def _taric_rule_note(self, t: TaricOutcome) -> tuple[ChangeKind, str]:
        """The audit kind and note for the rule that applied (data-model §5)."""
        where = self._taric_where(t)
        if t.rule == TaricRule.auto_completed:
            if t.taric10:
                return ChangeKind.taric_written, f"auto-completed, single TARIC subdivision, {where}"
            return ChangeKind.taric_pending, f"single TARIC subdivision, written once the CN-8 is written; {where}"
        if t.rule == TaricRule.trade_defence:
            return ChangeKind.taric_pending, f"trade-defence measure {', '.join(t.trade_defence_types)}; {where}"
        if t.rule == TaricRule.choose:
            return ChangeKind.taric_pending, f"several subdivisions ({len(t.subdivisions)}); {where}"
        text = "TARIC not available" if t.rule == TaricRule.not_available else "TARIC not loaded"
        return ChangeKind.taric_not_available, f"{text}; {where}"

    def confirm_taric10(self, line_no: int, code: str) -> None:
        """The clerk writes a TARIC-10 among the subdivisions (FR-012). It needs a decided HS-6 and a written CN-8, and
        it confirms that CN-8 too, so a threshold change no longer touches it: two audit entries, or one when the
        clerk had confirmed the CN-8 already. On an auto-accepted line it records the clerk's acceptance of the auto
        HS-6 (research R-09)."""
        line = self.get_line(line_no)
        v = line.current
        hs6, how = self.decided_code(line)
        if not hs6:
            raise LockedError(f"line {line_no}: the HS-6 is not decided, so a TARIC-10 cannot be confirmed yet")
        cn8 = self.decided_cn8(line)
        if cn8 is None:
            raise LockedError(f"line {line_no}: the CN-8 is not written, so a TARIC-10 cannot be confirmed yet")
        t = v.taric
        if t is None or not validate_taric10(code, t.subdivisions):
            raise UnknownCodeError(f"TARIC-10 {code!r} is not a subdivision of CN-8 {cn8} in the loaded snapshot")
        previous_route = self.effective_route(line)
        confirms_cn8 = v.cn8.written_by != WrittenBy.clerk
        if confirms_cn8:   # the TARIC-10 confirms the CN-8 it sits under
            v.cn8 = v.cn8.model_copy(update={"written_by": WrittenBy.clerk})
        v.taric = t.model_copy(update={"taric10": code, "written_by": WrittenBy.clerk, "question": None})
        if v.decision is None:
            v.decision = Decision(route=DecisionRoute.accepted, decided_code=hs6, chosen_how=ChosenHow(how or "auto"),
                                  decided_cn8=cn8, decided_taric10=code, at=self._clock())
            self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=v.version_no, change=ChangeKind.clerk_decision,
                                       previous=previous_route, new=DecisionRoute.accepted.value, actor=Actor.clerk,
                                       note="TARIC-10 confirmed on an auto-accepted line"))
        else:
            v.decision = v.decision.model_copy(update={"decided_cn8": cn8, "decided_taric10": code})
        if confirms_cn8:
            self._record_code(line, ChangeKind.cn8_written, cn8, Actor.clerk, f"confirmed by the clerk with TARIC-10 {code}")
        self._record_code(line, ChangeKind.taric_written, code, Actor.clerk, f"confirmed by the clerk; {self._taric_where(t)}",
                          previous=t.taric10)
        self._recompute(line, Actor.clerk)

    def ask_shipper_for_taric(self, line_no: int, question: str) -> None:
        """Instead of confirming a subdivision, the clerk sends the line to the shipper (FR-009): feature 001's
        ask-shipper decision, with the question stored on the outcome. Nothing is written."""
        line = self.get_line(line_no)
        question = (question or "").strip()
        if not question:
            raise ValueError("write what to ask the shipper")
        t = line.current.taric
        if t is None or t.rule not in (TaricRule.choose, TaricRule.trade_defence):
            raise ValueError(f"line {line_no}: no TARIC subdivision is left to the clerk")
        self.set_decision(line_no, Decision(route=DecisionRoute.ask_shipper))
        line.current.taric = t.model_copy(update={"question": question})
        self._record_code(line, ChangeKind.taric_question, None, Actor.clerk,
                          f"Ask the shipper for: {question}; {self._taric_where(t)}")

    def decided_taric10(self, line: Line) -> str | None:
        """The written TARIC-10 while the CN-8 is written and decided (data-model §6, top-down); None otherwise."""
        t = line.current.taric
        if self.decided_cn8(line) is None or t is None or not t.taric10 or t.written_by is None:
            return None
        return t.taric10

    def taric_pending(self, line: Line) -> bool:
        """A TARIC-10 left to the clerk: a written CN-8, rule choose or trade defence, nothing written, no question sent."""
        t = line.current.taric
        return bool(t is not None and self.decided_cn8(line) is not None and t.rule in (TaricRule.choose, TaricRule.trade_defence)
                    and not t.taric10 and not t.question)

    def _reapply_taric(self, line: Line, actor: Actor) -> None:
        """Re-apply `code_to_write` after the CN-8's written state changed; a clerk-confirmed TARIC-10 stays. Like the
        CN-8, nothing changes while the HS-6 is undecided or the CN-8 choice was made under another HS-6."""
        t, c = line.current.taric, line.current.cn8
        if t is None or t.written_by == WrittenBy.clerk or c is None or c.hs6 != self.decided_code(line)[0]:
            return
        code = code_to_write(t.rule, t.subdivisions, self.decided_cn8(line) is not None)
        if code == t.taric10:
            return
        line.current.taric = t.model_copy(update={"taric10": code, "written_by": WrittenBy.rule if code else None})
        where = self._taric_where(t)
        if code:
            self._record_code(line, ChangeKind.taric_written, code, actor, f"auto-completed, single TARIC subdivision, {where}")
        else:
            self._record_code(line, ChangeKind.threshold_recomputed, None, actor,
                              f"TARIC-10 {t.taric10} withdrawn: its CN-8 is no longer written; {where}", previous=t.taric10)

    def counts(self) -> dict[str, int]:
        c = {"auto_accept": 0, "review": 0, "ask_shipper": 0, "needs_action": 0, "accepted": 0}
        for line in self.shipment.lines:
            r = self.effective_route(line)
            if r == "auto_accept":
                c["auto_accept"] += 1
                c["accepted"] += 1
            elif r == "accepted":
                c["accepted"] += 1
            elif r == "review":
                c["review"] += 1
                c["needs_action"] += 1
            else:
                c["ask_shipper"] += 1
                c["needs_action"] += 1
        c["cn8_to_confirm"] = sum(1 for line in self.shipment.lines if self.cn8_pending(line))   # feature 004
        c["taric_to_confirm"] = sum(1 for line in self.shipment.lines if self.taric_pending(line))
        return c

    # ------------------------------------------------------------------ audit / usage / registries
    def record(self, rec: DecisionRecord) -> None:
        self.shipment.audit.append(rec)

    def add_usage(self, usage: Usage) -> None:
        self.shipment.usage.add(usage)

    def register_file(self, data: bytes, name: str) -> str:
        files = self._b.setdefault("files", {})
        ref = f"f{len(files) + 1}"
        files[ref] = (data, name)
        return ref

    def get_file(self, ref: str) -> tuple[bytes, str]:
        return self._b.get("files", {})[ref]

    def register_reply(self, text: str) -> str:
        replies = self._b.setdefault("replies", {})
        ref = f"r{len(replies) + 1}"
        replies[ref] = text
        return ref

    def get_reply(self, ref: str) -> str:
        return self._b.get("replies", {})[ref]

    # ------------------------------------------------------------------ export (contracts/export.md)
    def export_rows(self) -> list[dict[str, Any]]:
        rows = []
        for line in self.shipment.lines:
            v = line.current
            code, how = self.decided_code(line)
            cands = v.candidates[:3]
            row: dict[str, Any] = {
                "line_no": line.line_no, "text_zh": v.text_zh, "text_en": v.text_en, "qty": line.qty or "",
                "flag": v.flag.kind.value if v.flag else "",
                "flag_rule": (f"{v.flag.rule_source.value}:{v.flag.matched_term}" if v.flag and v.flag.rule_source and v.flag.matched_term
                              else ("judgement" if v.flag and v.flag.rule_source else "")),
            }
            for i in range(3):
                row[f"hs6_{i + 1}"] = cands[i].code if i < len(cands) else ""
                row[f"conf_{i + 1}"] = cands[i].confidence if i < len(cands) else ""
            row["precedent_1"] = cands[0].precedent.reference if cands and cands[0].precedent else ""
            row["route"] = self.effective_route(line)
            row["route_set_by"] = "clerk" if v.decision is not None else "routing_rule"
            row["decided_code"] = code or ""
            row["decided_how"] = how or ""
            row["version_no"] = v.version_no
            last = v.decision.at if v.decision is not None and v.decision.at > v.created_at else v.created_at
            row["last_change"] = last.isoformat()
            row["status"] = v.status.value
            notes = [n for n in (v.error_reason, v.contradiction_note, "truncated" if v.truncated else None,
                                 "unreadable" if v.unreadable else None) if n]
            row["note"] = "; ".join(notes)
            row["cn8"] = self.decided_cn8(line) or ""          # feature 004: written codes only, top-down (FR-022)
            row["taric10"] = self.decided_taric10(line) or ""
            rows.append(row)
        return rows

    CSV_COLUMNS = ["line_no", "text_zh", "text_en", "qty", "flag", "flag_rule", "hs6_1", "conf_1", "hs6_2", "conf_2",
                   "hs6_3", "conf_3", "precedent_1", "route", "route_set_by", "decided_code", "decided_how",
                   "version_no", "last_change", "status", "note", "cn8", "taric10"]

    def to_csv_bytes(self) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=self.CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in self.export_rows():
            writer.writerow(row)
        return ("﻿" + buf.getvalue()).encode("utf-8")

    def to_json_bytes(self, knowledge_base_updated: str | None = None) -> bytes:
        s = self.shipment
        lines = []
        for line, row in zip(s.lines, self.export_rows()):
            v = line.current
            lines.append({
                "line_no": line.line_no, "text_zh": v.text_zh, "text_en": v.text_en, "qty": line.qty,
                "flag": {"kind": row["flag"], "rule": row["flag_rule"] or None, "ask_for": list(v.flag.ask_for) if v.flag else []},
                "candidates": [{"code": c.code, "subheading_text": c.subheading_text, "confidence": c.confidence,
                                "history_only": c.history_only, "precedent": c.precedent.reference if c.precedent else None}
                               for c in v.candidates],
                "route": row["route"], "route_set_by": row["route_set_by"],
                "decided_code": row["decided_code"] or None, "decided_how": row["decided_how"] or None,
                "version_no": v.version_no, "last_change": row["last_change"], "status": row["status"],
                "note": row["note"] or None, "cn8": row["cn8"] or None, "taric10": row["taric10"] or None,
            })
        payload = {
            "shipment": {"id": s.id, "reference": s.reference, "shipper": s.shipper.name, "threshold": s.threshold,
                         "exported_at": self._clock().isoformat(), "knowledge_base_updated": knowledge_base_updated,
                         "usage": {"total_tokens": s.usage.total_tokens, "cost_eur": round(s.usage.cost_eur, 4)}},
            "lines": lines,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    def export_filename(self, ext: str) -> str:
        s = self.shipment
        stem = (s.reference or s.id).replace(" ", "_").replace("/", "-")
        return f"cargolint_{stem}_{self._clock().strftime('%Y%m%d-%H%M')}.{ext}"
