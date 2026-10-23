"""TARIC snapshot file `data/taric.jsonl`: record types, line format, header reader and the read-only TaricStore with
`lookup_taric` (features 002 and 003).

Schema 2: line 1 is the snapshot record as a JSON object; every other line is a JSON array whose first element is the
kind and whose other elements are the fields in contract order. Area records come first, then the code records, then
the measure records (specs/003-taric-groups-exclusions/contracts/snapshot-file.md). TARIC is used only for digits 9-10
and measures; it is never embedded or indexed.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from typing import Any

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
class TaricAreaRecord:
    geo_area: str                # the area id, for example `CN`, `1008`, `1011`; unique in the file
    name: str                    # English text of the description period valid on D; `""` when none
    member_of: tuple[str, ...]   # the groups this area belongs to on D, sorted; `()` when none


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
    excluded_areas: tuple[str, ...] = ()   # excluded area ids, sorted, no duplicates; stored as given (feature 003)


TaricRecord = TaricSnapshotRecord | TaricAreaRecord | TaricCodeRecord | TaricMeasureRecord
_KIND_OF = {TaricSnapshotRecord: "snapshot", TaricAreaRecord: "geographical_area", TaricCodeRecord: "goods_nomenclature",
            TaricMeasureRecord: "measure"}
_CLASS_OF = {kind: cls for cls, kind in _KIND_OF.items()}
_FIELDS = {cls: tuple(f.name for f in fields(cls)) for cls in _KIND_OF}
_LISTS = frozenset({"source_files", "member_of", "excluded_areas"})       # JSON arrays in the file, tuples in memory


def record_to_line(record: TaricRecord) -> str:
    """One JSON line without newline, non-ASCII as-is: the snapshot record as an object with `kind` first, every other
    record as `[kind, field, …]` in contract order."""
    kind = _KIND_OF[type(record)]
    values = [list(v) if isinstance(v, tuple) else v for v in (getattr(record, n) for n in _FIELDS[type(record)])]
    data: Any = ({"kind": kind, **dict(zip(_FIELDS[TaricSnapshotRecord], values))} if isinstance(record, TaricSnapshotRecord)
                 else [kind, *values])
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def line_to_record(line: str) -> TaricRecord:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TaricFileError(f"not a JSON line ({exc})") from exc
    if isinstance(data, dict):
        if data.pop("kind", None) != "snapshot":
            raise TaricFileError("only the snapshot record is a JSON object")
        cls, values = TaricSnapshotRecord, data
        if set(values) != set(_FIELDS[cls]):
            raise TaricFileError(f"the snapshot record has the keys {sorted(values)}, expected {sorted(_FIELDS[cls])}")
    elif isinstance(data, list) and data and isinstance(data[0], str) and data[0] in _CLASS_OF and data[0] != "snapshot":
        cls = _CLASS_OF[data[0]]
        if len(data) != len(_FIELDS[cls]) + 1:
            raise TaricFileError(f"a {data[0]} record has {len(data) - 1} fields, expected {len(_FIELDS[cls])}")
        values = dict(zip(_FIELDS[cls], data[1:]))
    else:
        raise TaricFileError("a line has no known record kind")
    for name in _LISTS.intersection(values):
        if not isinstance(values[name], list):
            raise TaricFileError(f"a {_KIND_OF[cls]} record's {name} is not a list")
        values[name] = tuple(values[name])
    return cls(**values)


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
ERGA_OMNES = "1011"
_NOT_SHOWN = frozenset({"566"})                     # anti-dumping/countervailing statistic: not shown by EZT-online (003, FR-007)
_WIDTH = {_KIND_OF[c]: len(_FIELDS[c]) + 1 for c in (TaricAreaRecord, TaricCodeRecord, TaricMeasureRecord)}
# A measure held in memory (feature 003, research R-07): (sid, measure_type, label, geo_area, additional_code, duty,
# regulation_id, regulation_ref, valid_from, valid_to, excluded_areas); the code it is recorded on is its key.
_SID, _TYPE, _LABEL, _GEO, _ADDL, _DUTY, _REG, _REF, _FROM, _TO, _EXCLUDED = range(11)


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
    geo_area: str                # the measure's own area: the origin, a group containing it, or 1011
    geo_area_name: str           # English name of geo_area valid on the snapshot date; "" when none (feature 003, FR-008)
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


def _refused(line: str, n: int) -> TaricFileError:
    """The error for a line the fast reader does not accept, worded by the strict one."""
    try:
        line_to_record(line)
    except TaricFileError as exc:
        return TaricFileError(f"line {n}: {exc}")
    return TaricFileError(f"line {n}: a second snapshot record")


class TaricStore:
    """The snapshot in memory (research R-10): declarable codes by CN-8, measures by code, parents by code, and each
    area's name and groups (feature 003). Loaded once per process; no method changes it (FR-020)."""

    def __init__(self, header: TaricSnapshotRecord, names: dict[str, str], member_of: dict[str, tuple[str, ...]],
                 parents: dict[str, str | None], declarable: dict[str, list[tuple[str, str, str, str | None]]],
                 measures: dict[str, list[tuple]]) -> None:
        self._snapshot = TaricSnapshotInfo(date.fromisoformat(header.snapshot_date), header.batch_id, header.loaded_at,
                                           header.goods_records, header.measure_records, header.cn8_mismatches)
        self._names = names                 # area id → English name
        self._member_of = member_of         # area id → the groups it belongs to
        self._parent = parents              # code → parent code
        self._declarable = declarable       # CN-8 → (code, description, valid_from, valid_to), in code order
        self._measures = measures           # code → the measures recorded on it, as _SID … _EXCLUDED tuples

    @classmethod
    def from_jsonl(cls, path: Path | str) -> "TaricStore":
        """Reads every line once: FileNotFoundError when absent, TaricFileError when malformed or of another schema.
        Each line is decoded once and kept as tuples of shared strings (feature 003, research R-07). Export-only and
        type-566 measures stay in the file but not in memory: no lookup returns them, and this is the only place they
        are filtered (research R-07, FR-007)."""
        names: dict[str, str] = {}
        member_of: dict[str, tuple[str, ...]] = {}
        parents: dict[str, str | None] = {}
        declarable: dict[str, list[tuple[str, str, str, str | None]]] = {}
        measures: dict[str, list[tuple]] = {}
        shared = {}.setdefault                                            # one object per repeated value
        try:
            with Path(path).open(encoding="utf-8") as f:
                first = f.readline()
                if not first:
                    raise TaricFileError("the file is empty")
                try:
                    record = line_to_record(first)
                except TaricFileError as exc:
                    raise TaricFileError(f"line 1: {exc}") from exc
                header = _checked_header(record)
                for n, line in enumerate(f, 2):
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        raise _refused(line, n) from None
                    kind = r[0] if type(r) is list and r else None
                    if kind == "measure" and len(r) == _WIDTH["measure"] and type(r[13]) is list:
                        if r[5] == "export" or r[3] in _NOT_SHOWN:
                            continue
                        measures.setdefault(r[2], []).append((
                            r[1], shared(r[3], r[3]), shared(r[4], r[4]), shared(r[6], r[6]), shared(r[7], r[7]),
                            shared(r[8], r[8]), shared(r[9], r[9]), shared(r[10], r[10]), shared(r[11], r[11]),
                            shared(r[12], r[12]), tuple(r[13]) if r[13] else ()))
                    elif kind == "goods_nomenclature" and len(r) == _WIDTH["goods_nomenclature"]:
                        parents[r[1]] = r[7]
                        if r[6]:
                            declarable.setdefault(r[2], []).append((r[1], r[3], r[4], r[5]))
                    elif kind == "geographical_area" and len(r) == _WIDTH["geographical_area"] and type(r[3]) is list:
                        names[r[1]] = r[2]
                        member_of[r[1]] = tuple(r[3])
                    else:
                        raise _refused(line, n)
        except UnicodeDecodeError as exc:
            raise TaricFileError(f"not UTF-8 text ({exc})") from exc
        for subdivisions in declarable.values():
            subdivisions.sort()
        return cls(header, names, member_of, parents, declarable, measures)

    @property
    def snapshot(self) -> TaricSnapshotInfo:
        return self._snapshot

    def lookup_taric(self, cn8: str, origin: str = "CN") -> list[TaricSubdivision]:
        """The subdivisions of a CN-8 on the snapshot date, each with the import measures recorded on it or on any code
        above it for the origin, any group containing the origin, or erga omnes (FR-017, FR-018; feature 003, FR-005,
        FR-006, FR-008); [] when TARIC has no subdivision (FR-019)."""
        code8 = _SPACES_AND_DOTS.sub("", cn8 or "")
        if not _CN8.fullmatch(code8):
            raise ValueError(f"not an 8-digit CN code: {cn8!r}")
        area = (origin or "").strip().upper()
        if not area.isalnum():
            raise ValueError(f"not a geographical area id: {origin!r}")
        applicable = self._applicable(area)
        return [self._subdivision(c, applicable) for c in self._declarable.get(code8, ())]

    def _applicable(self, origin: str) -> set[str]:
        """The origin, 1011, and every group reached from the origin through the memberships, each visited once."""
        found, todo = {origin, ERGA_OMNES}, [origin]
        while todo:
            for group in self._member_of.get(todo.pop(), ()):
                if group not in found:
                    found.add(group)
                    todo.append(group)
        return found

    def _subdivision(self, c: tuple[str, str, str, str | None], applicable: set[str]) -> TaricSubdivision:
        code, description, valid_from, valid_to = c
        found: list[tuple[str, tuple]] = []                               # (the code it is recorded on, measure)
        node: str | None = code
        seen: set[str] = set()
        while node is not None and node not in seen:                      # the subdivision, then its parent chain
            seen.add(node)
            found += [(node, m) for m in self._measures.get(node, ())
                      if m[_GEO] in applicable and applicable.isdisjoint(m[_EXCLUDED])]      # feature 003, FR-006
            node = self._parent.get(node)
        found.sort(key=lambda t: (t[1][_TYPE], t[1][_GEO], t[1][_ADDL] or "", t[1][_SID]))
        return TaricSubdivision(code, description, date.fromisoformat(valid_from), _day(valid_to), tuple(
            TaricMeasure(m[_SID], on, m[_TYPE], m[_LABEL], m[_GEO], self._names.get(m[_GEO], ""), m[_ADDL], m[_DUTY],
                         m[_REG], m[_REF], date.fromisoformat(m[_FROM]), _day(m[_TO]))
            for on, m in found))


def open_taric_store(path: Path | str) -> TaricStore | None:
    """The store for the app, or None with the reason logged when the file is absent, unreadable or of another schema;
    the app then starts without TARIC (FR-024)."""
    try:
        return TaricStore.from_jsonl(path)
    except (OSError, TaricFileError) as exc:
        log.warning("TARIC not loaded from %s: %s", path, exc)
        return None
