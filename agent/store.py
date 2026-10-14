"""The line store: the only module that reads or writes line data.

Backed by any mutable mapping (a plain dict in tests, `st.session_state` in the app). Every
mutation recomputes routes with the pure routing function and appends an audit record.
No Streamlit import here (constitution, Architecture invariants).
"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, MutableMapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agent.config import ASK_FLOOR, DEFAULT_THRESHOLD, THRESHOLD_MAX, THRESHOLD_MIN
from agent.routing import can_accept, route_line, validate_code
from agent.schemas import (
    Actor,
    ChangeKind,
    ChosenHow,
    Classification,
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
    Route,
    ShipperRef,
    Shipment,
    Source,
    SourceFile,
    SourceKind,
    Usage,
)


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
        version.version_no = len(line.versions) + 1
        version.decision = None
        if version.created_at is None:
            version.created_at = self._clock()
        line.versions.append(version)
        change = ChangeKind.reply_applied if version.created_by == CreatedBy.shipper_reply else ChangeKind.version_added
        actor = Actor.shipper_reply if version.created_by == CreatedBy.shipper_reply else Actor.system
        self.record(DecisionRecord(at=self._clock(), line_no=line_no, version_no=version.version_no, change=change,
                                   previous=previous_route, new=None, actor=actor, note=version.contradiction_note))
        self._recompute(line, Actor.routing_rule)
        return version

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

    def set_hybrid(self, value: bool) -> None:
        self.shipment.hybrid_search = bool(value)

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
        route, reason = route_line(kind, v.top_confidence, v.status, needs_click, s.threshold, s.ask_floor)
        if v.unreadable and v.status == LineStatus.checked and not v.candidates:
            reason = "unreadable description — needs a human look"
        changed = route != v.computed_route or reason != v.route_reason
        previous = v.computed_route.value
        v.computed_route = route
        v.route_reason = reason
        if changed:
            self.record(DecisionRecord(at=self._clock(), line_no=line.line_no, version_no=v.version_no, change=change,
                                       previous=previous, new=route.value, actor=actor, note=reason))

    # ------------------------------------------------------------------ derived
    def effective_route(self, line: Line) -> str:
        v = line.current
        return v.decision.route.value if v.decision is not None else v.computed_route.value

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
        if v.decision is None and v.computed_route == Route.auto_accept and v.candidates:
            return v.candidates[0].code, ChosenHow.auto.value
        return None, None

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
            rows.append(row)
        return rows

    CSV_COLUMNS = ["line_no", "text_zh", "text_en", "qty", "flag", "flag_rule", "hs6_1", "conf_1", "hs6_2", "conf_2",
                   "hs6_3", "conf_3", "precedent_1", "route", "route_set_by", "decided_code", "decided_how",
                   "version_no", "last_change", "status", "note"]

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
                "note": row["note"] or None,
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
