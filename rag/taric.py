"""TARIC snapshot file `data/taric.jsonl`: record types, line format and header reader (feature 002).

One JSON object per line, distinguished by `kind`: the snapshot record first, then the code records, then the measure
records (contracts/snapshot-file.md). TARIC is used only for digits 9-10 and measures; it is never embedded or indexed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from agent.config import TARIC_SCHEMA


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
    record = line_to_record(first)
    if not isinstance(record, TaricSnapshotRecord):
        raise TaricFileError("the first line is not the snapshot record")
    if record.schema != TARIC_SCHEMA:
        raise TaricFileError(f"schema {record.schema} is not supported (expected {TARIC_SCHEMA})")
    return json.loads(first)
