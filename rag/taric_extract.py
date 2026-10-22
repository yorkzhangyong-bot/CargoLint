"""TARIC extract → snapshot (feature 002): file set, streaming parse, EU-only and validity filters, code hierarchy,
duty text, CN-8 reconciliation and the atomic write (research R-01 to R-10).

The six object files of one batch are verified (rag.pgp), unpacked in memory and parsed as streams, so the 800 MB
measure XML never sits on disk or in memory. Everything is judged on the snapshot date D from the file names.
"""
from __future__ import annotations

import gzip
import io
import os
import re
import zlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from lxml import etree

from agent.config import TARIC_OBJECTS, TARIC_SCHEMA
from rag.pgp import SignatureError, check_key_copy, verify_signed
from rag.taric import TaricCodeRecord, TaricMeasureRecord, TaricSnapshotRecord, record_to_line

NS = "{http://www.arcticgroup.se/tariff/arctictariff/export}"
_FILE = re.compile(rf"^(?P<object>{'|'.join(TARIC_OBJECTS)})_(?P<batch>[^_]+)_(?P<yymmdd>\d{{6}})\.xml\.gz\.pgp$")
_MOVEMENT = {"0": "import", "1": "export", "2": "both"}
# duty text (research R-08): prefixes by duty expression, short forms of components without an amount, unit labels
_PREFIX = {"01": "", "02": "−", "04": "+", "19": "+", "20": "+", "15": "MIN", "17": "MAX", "35": "MAX"}
_SHORT = {"12": "+ EA", "14": "+ EAR", "21": "+ ADSZ", "25": "+ ADSZR", "27": "+ ADFM", "29": "+ ADFMR"}
_UNITS = {"DTN": "100 kg", "KGM": "kg", "TNE": "1000 kg", "LTR": "l", "HLT": "hl", "MTQ": "m³", "MTK": "m²", "NAR": "p/st"}
_REGULATIONS = {  # record element: (id attribute, role type attribute), as measures name their regulation
    "baseRegulation": ("regulationId", "regulationRoleType"),
    "modificationRegulation": ("modificationRegulationId", "modificationRegulationRoleType"),
    "fullTemporaryStopRegulation": ("ftsRegulationId", "ftsRegulationRoleType"),
}
_UNREADABLE = (OSError, EOFError, zlib.error, etree.XMLSyntaxError)
# measures no lookup can use, dropped and counted (research R-14): the Meursing table has no goods code
MEURSING_TYPES = frozenset({"672", "673", "674"})
DROPPED_MEURSING = "Meursing table, measure types 672, 673, 674"
DROPPED_NATIONAL_CODE = "on a code held only as a national record"


class ExtractError(Exception):
    """The extract is refused: file set, signature, export id, unreadable file or inconsistent data."""


@dataclass(frozen=True)
class ExtractFile:
    object: str
    batch_id: str
    snapshot_date: date
    path: Path


@dataclass(frozen=True)
class ExtractSet:
    batch_id: str
    snapshot_date: date
    files: tuple[ExtractFile, ...]          # one per object, in TARIC_OBJECTS order


@dataclass(frozen=True)
class Regulation:
    ref: str                                # "OJ {journal}, p. {page} ({published})", or "" without those fields
    effective_end: str | None               # base and modification regulations only (research R-04)


@dataclass
class Snapshot:
    header: TaricSnapshotRecord
    codes: list[TaricCodeRecord]
    measures: list[TaricMeasureRecord]
    mismatches: list[tuple[str, str]]       # (CN-8 prefix that CN 2026 lacks, first declarable code under it)
    log_path: Path
    geo_areas: frozenset[str]
    dropped: dict[str, int]                 # measures dropped by reason (research R-14)


# --------------------------------------------------------------------------- file set
def discover_extract(folder: Path) -> ExtractSet:
    """The six object files of one batch in `folder` (research R-01, FR-003, FR-004); other files are ignored."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ExtractError(f"the folder {folder} does not exist")
    found: dict[str, list[ExtractFile]] = {}
    for path in sorted(folder.iterdir()):
        m = _FILE.match(path.name)
        if m and path.is_file():
            found.setdefault(m["object"], []).append(ExtractFile(m["object"], m["batch"], _file_date(m["yymmdd"], path.name), path))
    missing = [o for o in TARIC_OBJECTS if o not in found]
    if missing:
        raise ExtractError(f"object file missing in {folder}: {', '.join(missing)}")
    twice = [f.path.name for o in TARIC_OBJECTS if len(found[o]) > 1 for f in found[o]]
    if twice:
        raise ExtractError(f"more than one file for the same object: {', '.join(twice)}")
    files = tuple(found[o][0] for o in TARIC_OBJECTS)
    if len({f.batch_id for f in files}) > 1 or len({f.snapshot_date for f in files}) > 1:
        raise ExtractError(f"the files are not from one batch and date: {', '.join(f.path.name for f in files)}")
    return ExtractSet(files[0].batch_id, files[0].snapshot_date, files)


def _file_date(yymmdd: str, file_name: str) -> date:
    try:
        return date(2000 + int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:]))
    except ValueError as exc:
        raise ExtractError(f"{file_name}: the name holds no valid date") from exc


# --------------------------------------------------------------------------- streaming parse
def _records(payload: bytes, *tags: str) -> Iterator[Any]:
    """The record elements of one gzipped export document, each freed after use (research R-03)."""
    source = gzip.GzipFile(fileobj=io.BytesIO(payload))
    for _event, el in etree.iterparse(source, events=("end",), tag=[NS + t for t in tags], resolve_entities=False,
                                       no_network=True, load_dtd=False):
        yield el
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]


def _a(el: Any, name: str) -> str | None:
    return el.get(NS + name)


def _valid(start: str | None, end: str | None, day: str) -> bool:
    return (start is None or start <= day) and (end is None or end >= day)


def _english(el: Any, child: str) -> str:
    return next((_a(d, "description") or "" for d in el.iterfind(NS + child) if _a(d, "languageId") == "EN"), "")


def _read(label: str, parse: Callable[..., Any], *args: Any) -> Any:
    """Run one parser; any refusal or unreadable content names the file."""
    try:
        return parse(*args)
    except ExtractError as exc:
        raise ExtractError(f"{label}: {exc}") from exc
    except _UNREADABLE as exc:
        raise ExtractError(f"{label}: cannot be unpacked or read ({exc})") from exc


def _export_id(payload: bytes) -> str:
    for el in _records(payload, "id"):
        return (el.text or "").strip()
    return ""


def check_export_ids(payloads: dict[str, bytes]) -> str:
    """The one export id that all documents carry (research R-01); payloads are keyed by the name to report."""
    ids = {label: _read(label, _export_id, payload) for label, payload in payloads.items()}
    if "" in ids.values() or len(set(ids.values())) != 1:
        raise ExtractError(f"the export ids differ: {', '.join(f'{label} {i or None}' for label, i in ids.items())}")
    return next(iter(ids.values()))


# --------------------------------------------------------------------------- reference objects
def parse_measure_types(payload: bytes) -> dict[str, tuple[str, str]]:
    """EU measure types: code → (English label, trade movement import / export / both) (research R-07)."""
    types: dict[str, tuple[str, str]] = {}
    for el in _records(payload, "measureType"):
        if _a(el, "national") != "0":
            continue
        code, movement = _a(el, "measureType"), _MOVEMENT.get(_a(el, "tradeMovementCode") or "")
        if movement is None:
            raise ExtractError(f"measure type {code} has the unknown trade movement code {_a(el, 'tradeMovementCode')}")
        types[code] = (_english(el, "measureTypeDescription"), movement)
    return types


def parse_duty_expressions(payload: bytes) -> dict[str, str]:
    """EU duty expressions: id → English description, with plain spaces."""
    return {_a(el, "dutyExpressionId"): _english(el, "dutyExpressionDescription").replace("\xa0", " ")
            for el in _records(payload, "dutyExpression") if _a(el, "national") == "0"}


def parse_regulations(payload: bytes) -> dict[tuple[str, str | None], Regulation]:
    """EU regulations by (id, role type): OJ reference (research R-08) and effective end date (research R-04)."""
    regs: dict[tuple[str, str | None], Regulation] = {}
    for el in _records(payload, *_REGULATIONS):
        if _a(el, "national") != "0":
            continue
        tag = etree.QName(el).localname
        id_attr, role_attr = _REGULATIONS[tag]
        journal, page, published = _a(el, "officialJournalId"), _a(el, "journalPage"), _a(el, "datePublished")
        ref = f"OJ {journal}, p. {page} ({published})" if journal and page and published else ""
        end = None if tag == "fullTemporaryStopRegulation" else _a(el, "effectiveEndDate")
        regs.setdefault((_a(el, id_attr) or "", _a(el, role_attr)), Regulation(ref, end))
    return regs


def parse_geographical_areas(payload: bytes) -> frozenset[str]:
    return frozenset(_a(el, "geographicalAreaId") or "" for el in _records(payload, "geographicalArea") if _a(el, "national") == "0")


# --------------------------------------------------------------------------- goods and hierarchy
def _description(el: Any, day: str) -> str:
    """English text of the latest description period valid on D."""
    periods = [(_a(p, "dateStart") or "", p) for p in el.iterfind(NS + "goodsNomenclatureDescriptionPeriod")
               if _valid(_a(p, "dateStart"), _a(p, "dateEnd"), day)]
    return _english(max(periods, key=lambda t: t[0])[1], "goodsNomenclatureDescription") if periods else ""


def parse_goods(payload: bytes, d: date) -> list[TaricCodeRecord]:
    """Suffix-80 EU codes valid on D, in code order, with `declarable` and `parent` from the indents (research R-04, R-06)."""
    day = d.isoformat()
    lines: list[tuple[str, str, int, str, str, str | None]] = []   # every valid EU record, grouping lines included
    for el in _records(payload, "goodsNomenclature"):
        start, end = _a(el, "dateStart"), _a(el, "dateEnd")
        if _a(el, "national") != "0" or not _valid(start, end, day):
            continue
        code, suffix = _a(el, "goodsNomenclatureCode") or "", _a(el, "productLineSuffix") or ""
        indents = [(_a(i, "dateStart") or "", _a(i, "quantityIndents") or "") for i in el.iterfind(NS + "goodsNomenclatureIndent")
                   if (_a(i, "dateStart") or "") <= day]
        if not indents:
            raise ExtractError(f"goods code {code} has no indent valid on {day}")
        text = _description(el, day) if suffix == "80" and code[8:] != "00" else ""   # FR-007: digits 9-10 only
        lines.append((code, suffix, int(max(indents)[1]), text, start or "", end))
    lines.sort(key=lambda t: (t[0], t[1]))

    stored: list[tuple[str, str, str, str | None, str | None]] = []
    with_children: set[tuple[str, str]] = set()
    stack: list[tuple[int, str, str]] = []                          # (level, code, suffix) of the open ancestors
    chapter = None
    for code, suffix, indent, text, start, end in lines:
        if code[:2] != chapter:
            chapter, stack = code[:2], []
        level = -1 if code.endswith("00000000") else indent          # chapters are roots, headings (indent 0) their children
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            with_children.add(stack[-1][1:])
        parent = next((c for _, c, s in reversed(stack) if s == "80"), None)   # grouping lines are never parents
        stack.append((level, code, suffix))
        if suffix == "80":
            if stored and stored[-1][0] == code:
                raise ExtractError(f"goods code {code} appears twice with suffix 80 on {day}")
            stored.append((code, text, start, end, parent))
    return [TaricCodeRecord(code=c, cn8=c[:8], description=text, valid_from=start, valid_to=end,
                            declarable=(c, "80") not in with_children, parent=parent)
            for c, text, start, end, parent in stored]


def national_only_codes(payload: bytes) -> frozenset[str]:
    """Codes that the goods file holds only as national records, at any date (research R-14)."""
    eu: set[str] = set()
    national: set[str] = set()
    for el in _records(payload, "goodsNomenclature"):
        (eu if _a(el, "national") == "0" else national).add(_a(el, "goodsNomenclatureCode") or "")
    return frozenset(national - eu)


# --------------------------------------------------------------------------- measures and duty text
def _number(amount: str) -> str:
    try:
        return format(Decimal(amount).normalize(), "f")             # trailing zeros dropped: 22.0 → 22, 4.20 → 4.2
    except InvalidOperation as exc:
        raise ExtractError(f"the duty amount {amount!r} is not a number") from exc


def render_duty(components: Iterable[tuple[str | None, ...]], expressions: dict[str, str]) -> str:
    """Duty text from (expression, amount, currency, unit, qualifier) components in ascending expression order (research R-08)."""
    parts: list[str] = []
    for expr, amount, money, unit, qualifier in sorted(components, key=lambda c: c[0] or ""):
        unit_text = " ".join(x for x in (_UNITS.get(unit, unit) if unit else None, qualifier) if x)
        if amount is None:
            parts.append(unit_text or _SHORT.get(expr or "") or expressions.get(expr or "", expr or ""))
            continue
        value = f"{_number(amount)} {money}" if money else f"{_number(amount)} %"
        if money and unit_text:
            value += f" / {unit_text}"
        parts.append(f"{_PREFIX.get(expr or '', '')} {value}".strip())
    return " ".join(parts)


def parse_measures(payload: bytes, d: date, types: dict[str, tuple[str, str]], expressions: dict[str, str],
                   regulations: dict[tuple[str, str | None], Regulation]) -> list[TaricMeasureRecord]:
    """EU measures in force on D, in (code, SID) order (research R-04, R-05, R-07, R-08)."""
    day = d.isoformat()
    kept: dict[int, TaricMeasureRecord] = {}
    for el in _records(payload, "measure"):
        start, end = _a(el, "dateStart"), _a(el, "dateEnd")
        if _a(el, "national") != "0" or not _valid(start, end, day):
            continue
        if any(_valid(_a(s, "dateStart"), _a(s, "dateEnd"), day) for s in el.iterfind(NS + "measurePartialTemporaryStop")):
            continue
        reg_id = _a(el, "regulationId") or ""
        reg = regulations.get((reg_id, _a(el, "regulationRoleType")))
        if end is None and reg is not None and reg.effective_end is not None and reg.effective_end < day:
            continue                                                 # open-ended measure of a regulation that has ended
        sid, mtype = int(_a(el, "SID") or 0), _a(el, "measureType") or ""
        if mtype not in types:
            raise ExtractError(f"measure {sid} has the measure type {mtype}, which MeasureType does not define")
        label, movement = types[mtype]
        addl = _a(el, "additionalCodeId")
        components = [(_a(c, "dutyExpressionId"), _a(c, "dutyAmount"), _a(c, "monetaryUnitCode"), _a(c, "measurementUnitCode"),
                       _a(c, "measurementUnitQualifierCode")) for c in el.iterfind(NS + "measureComponent")]
        record = TaricMeasureRecord(
            sid=sid, code=_a(el, "goodsNomenclatureCode") or "", measure_type=mtype, measure_type_label=label,
            trade_movement=movement, geo_area=_a(el, "geographicalAreaId") or "",
            additional_code=f"{_a(el, 'additionalCodeType') or ''}{addl}" if addl else None,
            duty=render_duty(components, expressions), regulation_id=reg_id, regulation_ref=reg.ref if reg else "",
            valid_from=start or "", valid_to=end)
        if kept.setdefault(sid, record) != record:
            raise ExtractError(f"measure SID {sid} appears twice with different content")
    return sorted(kept.values(), key=lambda m: (m.code, m.sid))


# --------------------------------------------------------------------------- reconciliation, snapshot, write
def reconcile(codes: Iterable[TaricCodeRecord], cn2026_cn8: frozenset[str]) -> list[tuple[str, str]]:
    """CN-8 prefixes of declarable codes that CN 2026 lacks, each with its first declarable code; parents never count (FR-011)."""
    first: dict[str, str] = {}
    for c in codes:
        if c.declarable and c.cn8 not in cn2026_cn8:
            first[c.cn8] = min(first.get(c.cn8, c.code), c.code)
    return sorted(first.items())


def write_mismatch_log(mismatches: list[tuple[str, str]], log_dir: Path, snapshot_date: date) -> Path:
    path = Path(log_dir) / f"taric-cn8-mismatches-{snapshot_date.isoformat()}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(f"{cn8} {code}\n" for cn8, code in mismatches)
    return path


def build_snapshot(extract: ExtractSet, payloads: dict[str, bytes], cn2026_cn8: frozenset[str], log_dir: Path) -> Snapshot:
    """Parse verified payloads (keyed by object) into the snapshot; writes only the mismatch log (FR-011)."""
    names = {f.object: f.path.name for f in extract.files}
    export_id = check_export_ids({names[o]: payloads[o] for o in TARIC_OBJECTS})
    d = extract.snapshot_date
    types = _read(names["MeasureType"], parse_measure_types, payloads["MeasureType"])
    expressions = _read(names["DutyExpression"], parse_duty_expressions, payloads["DutyExpression"])
    regulations = _read(names["Regulation"], parse_regulations, payloads["Regulation"])
    areas = _read(names["GeographicalArea"], parse_geographical_areas, payloads["GeographicalArea"])
    codes = _read(names["GoodsNomenclature"], parse_goods, payloads["GoodsNomenclature"], d)
    measures = _read(names["Measure"], parse_measures, payloads["Measure"], d, types, expressions, regulations)
    national_only = _read(names["GoodsNomenclature"], national_only_codes, payloads["GoodsNomenclature"])
    dropped = {DROPPED_MEURSING: sum(m.measure_type in MEURSING_TYPES for m in measures),
               DROPPED_NATIONAL_CODE: sum(m.measure_type not in MEURSING_TYPES and m.code in national_only for m in measures)}
    measures = [m for m in measures if m.measure_type not in MEURSING_TYPES and m.code not in national_only]
    mismatches = reconcile(codes, cn2026_cn8)
    log_path = write_mismatch_log(mismatches, log_dir, d)
    header = TaricSnapshotRecord(
        schema=TARIC_SCHEMA, snapshot_date=d.isoformat(), batch_id=extract.batch_id, export_id=export_id,
        source_files=tuple(f.path.name for f in extract.files), loaded_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        goods_records=len(codes), measure_records=len(measures), cn8_mismatches=len(mismatches))
    return Snapshot(header, codes, measures, mismatches, log_path, areas, dropped)


def load_extract(extract: ExtractSet, key_path: Path, fingerprint: str, cn2026_cn8: frozenset[str], log_dir: Path) -> Snapshot:
    """Check the key copy, verify all six signatures against the pinned key, then parse (contracts/loader-cli.md steps 5-8)."""
    check_key_copy(key_path, fingerprint)
    payloads: dict[str, bytes] = {}
    for f in extract.files:
        try:
            payloads[f.object] = verify_signed(f.path.read_bytes(), key_path, fingerprint)
        except SignatureError as exc:
            raise ExtractError(f"{f.path.name}: {exc}") from exc
    return build_snapshot(extract, payloads, cn2026_cn8, log_dir)


def write_snapshot(snapshot: Snapshot, path: Path) -> None:
    """Snapshot record, codes by code, measures by (code, SID); UTF-8 with LF, written to `<path>.tmp` and swapped in,
    so a failed write leaves the previous file untouched (FR-013, FR-015)."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            f.write(record_to_line(snapshot.header) + "\n")
            f.writelines(record_to_line(r) + "\n" for r in sorted(snapshot.codes, key=lambda r: r.code))
            f.writelines(record_to_line(r) + "\n" for r in sorted(snapshot.measures, key=lambda r: (r.code, r.sid)))
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
