"""TARIC snapshot file `data/taric.jsonl`: record types, line format, header reader and the read-only TaricStore with
`lookup_taric` (feature 002).

One JSON object per line, distinguished by `kind`: the snapshot record first, then the code records, then the measure
records (contracts/snapshot-file.md). TARIC is used only for digits 9-10 and measures; it is never embedded or indexed.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, fields, replace
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from agent.config import TARIC_SCHEMA

log = logging.getLogger(__name__)


class TaricFileError(Exception):
    """Malformed line, missing snapshot record or unsupported schema."""


@dataclass(frozen=True, slots=True)
class TaricSnapshotRecord:
    schema: int
    snapshot_date: str
    batch_id: str
    export_id: str
    source_files: tuple[str, ...]
    loaded_at: str
    goods_records: int
    measure_records: int
    cn8_mismatches: int


@dataclass(frozen=True, slots=True)
class TaricCodeRecord:
    code: str                    # string, 10 digits
    cn8: str                     # `code[:8]`
    description: str             # `""` when digits 9-10 are `00`
    valid_from: str
    valid_to: str | None
    declarable: bool
    parent: str | None


@dataclass(frozen=True, slots=True)
class TaricMeasureRecord:
    sid: int                     # int > 0
    code: str
    measure_type: str
    measure_type_label: str
    trade_movement: str          # `import`, `export` or `both`
    geo_area: str
    additional_code: str | None  # string or null
    duty: str
    regulation_id: str
    regulation_ref: str
    valid_from: str
    valid_to: str | None


TaricRecord = TaricSnapshotRecord | TaricCodeRecord | TaricMeasureRecord
_KIND_OF = {TaricSnapshotRecord: "snapshot", TaricCodeRecord: "goods_nomenclature", TaricMeasureRecord: "measure"}
_CLASS_OF = {kind: cls for cls, kind in _KIND_OF.items()}


def record_to_line(record: TaricRecord) -> str:
    """One JSON line without newline: `kind` first, then the fields in contract order, non-ASCII as-is."""
    data: dict[str, Any] = {"kind": _KIND_OF[type(record)]}
    for f in fields(record):
        value = getattr(record, f.name)
        data[f.name] = list(value) if isinstance(value, tuple) else value
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def line_to_record(line: str) -> TaricRecord:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TaricFileError(f"not a JSON line ({exc})") from exc
    if not isinstance(data, dict):
        raise TaricFileError("a line is not a JSON object")
    cls = _CLASS_OF.get(data.pop("kind", None))
    if cls is None:
        raise TaricFileError("a line has no known record kind")
    names = {f.name for f in fields(cls)}
    if set(data) != names:
        raise TaricFileError(f"a {_KIND_OF[cls]} record has the keys {sorted(data)}, expected {sorted(names)}")
    if cls is TaricSnapshotRecord:
        data["source_files"] = tuple(data["source_files"])
    return cls(**data)


def read_snapshot_header(path: Path | str) -> dict[str, Any] | None:
    """The snapshot record on the first line, or None when the file is absent; reads nothing else."""
    try:
        with Path(path).open(encoding="utf-8") as f:
            first = f.readline()
    except FileNotFoundError:
        return None
    _checked_header(line_to_record(first))
    return json.loads(first)


def _checked_header(record: TaricRecord) -> TaricSnapshotRecord:
    if not isinstance(record, TaricSnapshotRecord):
        raise TaricFileError("the first line is not the snapshot record")
    if record.schema != TARIC_SCHEMA:
        raise TaricFileError(f"schema {record.schema} is not supported (expected {TARIC_SCHEMA})")
    return record


# --------------------------------------------------------------------------- read side (contracts/taric-store.md)
_CN8 = re.compile(r"[0-9]{8}")
_SPACES_AND_DOTS = re.compile(r"[\s.]")
_IMPORT = frozenset({"import", "both"})             # research R-07: an origin lookup answers an import question
ERGA_OMNES = "1011"
_SHARED = ("code", "measure_type", "measure_type_label", "trade_movement", "geo_area", "additional_code", "duty",
           "regulation_id", "regulation_ref", "valid_from", "valid_to")   # strings repeated across measures


@dataclass(frozen=True, slots=True)
class TaricSnapshotInfo:
    snapshot_date: date
    batch_id: str
    loaded_at: str
    goods_records: int
    measure_records: int
    cn8_mismatches: int


@dataclass(frozen=True, slots=True)
class TaricMeasure:
    sid: int
    recorded_on: str             # the code the measure is recorded against: the subdivision or an ancestor
    measure_type: str
    measure_type_label: str
    geo_area: str
    additional_code: str | None
    duty: str
    regulation_id: str
    regulation_ref: str
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True, slots=True)
class TaricSubdivision:
    code: str
    description: str
    valid_from: date
    valid_to: date | None
    measures: tuple[TaricMeasure, ...]


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _interned(m: TaricMeasureRecord) -> TaricMeasureRecord:
    return replace(m, **{f: sys.intern(v) for f in _SHARED if (v := getattr(m, f)) is not None})


class TaricStore:
    """The snapshot in memory (research R-10): declarable codes by CN-8, measures by code, parents by code.
    Loaded once per process; no method changes it (FR-020)."""

    def __init__(self, header: TaricSnapshotRecord, codes: Iterable[TaricCodeRecord],
                 measures: Iterable[TaricMeasureRecord]) -> None:
        self._snapshot = TaricSnapshotInfo(date.fromisoformat(header.snapshot_date), header.batch_id, header.loaded_at,
                                           header.goods_records, header.measure_records, header.cn8_mismatches)
        self._parent: dict[str, str | None] = {}
        self._declarable: dict[str, list[TaricCodeRecord]] = {}
        for c in codes:
            self._parent[c.code] = c.parent
            if c.declarable:
                self._declarable.setdefault(c.cn8, []).append(c)
        for subdivisions in self._declarable.values():
            subdivisions.sort(key=lambda c: c.code)
        self._measures: dict[str, list[TaricMeasureRecord]] = {}
        for m in measures:
            self._measures.setdefault(m.code, []).append(m)

    @classmethod
    def from_jsonl(cls, path: Path | str) -> "TaricStore":
        """Reads every line once: FileNotFoundError when absent, TaricFileError when malformed or of another schema."""
        header: TaricSnapshotRecord | None = None
        codes: list[TaricCodeRecord] = []
        measures: list[TaricMeasureRecord] = []
        try:
            with Path(path).open(encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    try:
                        record = line_to_record(line)
                    except TaricFileError as exc:
                        raise TaricFileError(f"line {n}: {exc}") from exc
                    if n == 1:
                        header = _checked_header(record)
                    elif isinstance(record, TaricCodeRecord):
                        codes.append(record)
                    elif isinstance(record, TaricMeasureRecord):
                        measures.append(_interned(record))
                    else:
                        raise TaricFileError(f"line {n}: a second snapshot record")
        except UnicodeDecodeError as exc:
            raise TaricFileError(f"not UTF-8 text ({exc})") from exc
        if header is None:
            raise TaricFileError("the file is empty")
        return cls(header, codes, measures)

    @property
    def snapshot(self) -> TaricSnapshotInfo:
        return self._snapshot

    def lookup_taric(self, cn8: str, origin: str = "CN") -> list[TaricSubdivision]:
        """The subdivisions of a CN-8 on the snapshot date, each with the import measures for the origin and erga omnes
        recorded on it or on any code above it (FR-017, FR-018); [] when TARIC has no subdivision (FR-019)."""
        code8 = _SPACES_AND_DOTS.sub("", cn8 or "")
        if not _CN8.fullmatch(code8):
            raise ValueError(f"not an 8-digit CN code: {cn8!r}")
        area = (origin or "").strip().upper()
        if not area.isalnum():
            raise ValueError(f"not a geographical area id: {origin!r}")
        return [self._subdivision(c, area) for c in self._declarable.get(code8, ())]

    def _subdivision(self, c: TaricCodeRecord, area: str) -> TaricSubdivision:
        found: list[TaricMeasureRecord] = []
        code: str | None = c.code
        seen: set[str] = set()
        while code is not None and code not in seen:                      # the subdivision, then its parent chain
            seen.add(code)
            found += [m for m in self._measures.get(code, ()) if m.geo_area in (area, ERGA_OMNES) and m.trade_movement in _IMPORT]
            code = self._parent.get(code)
        found.sort(key=lambda m: (m.measure_type, m.geo_area, m.additional_code or "", m.sid))
        return TaricSubdivision(c.code, c.description, date.fromisoformat(c.valid_from), _day(c.valid_to), tuple(
            TaricMeasure(m.sid, m.code, m.measure_type, m.measure_type_label, m.geo_area, m.additional_code, m.duty,
                         m.regulation_id, m.regulation_ref, date.fromisoformat(m.valid_from), _day(m.valid_to))
            for m in found))


def open_taric_store(path: Path | str) -> TaricStore | None:
    """The store for the app, or None with the reason logged when the file is absent, unreadable or of another schema;
    the app then starts without TARIC (FR-024)."""
    try:
        return TaricStore.from_jsonl(path)
    except (OSError, TaricFileError) as exc:
        log.warning("TARIC not loaded from %s: %s", path, exc)
        return None
