"""The TARIC rules as pure functions (feature 004, research R-06): which rule applies to a CN-8's subdivisions and what
may be written. No model, store or Streamlit import (constitution Principle I); covered by tests written first."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from agent.schemas import TaricRule

TRADE_DEFENCE_CONFIRM = frozenset({"551", "552", "553", "554", "555", "570"})   # clarification Q3: always the clerk's call


def confirm_types(subdivision: Any) -> list[str]:
    """The measure types of one subdivision that require the clerk's confirmation, sorted, each once."""
    return sorted({m.measure_type for m in subdivision.measures if m.measure_type in TRADE_DEFENCE_CONFIRM})


def taric_rule(subdivisions: Sequence[Any], snapshot_loaded: bool) -> TaricRule:
    """Exactly one rule, from the subdivisions `lookup_taric` returned for the CN-8 and origin (FR-007 to FR-011)."""
    if not snapshot_loaded:
        return TaricRule.not_loaded
    if not subdivisions:
        return TaricRule.not_available
    if any(confirm_types(s) for s in subdivisions):
        return TaricRule.trade_defence
    if len(subdivisions) == 1:
        return TaricRule.auto_completed
    return TaricRule.choose


def code_to_write(rule: TaricRule, subdivisions: Sequence[Any], cn8_written: bool) -> str | None:
    """The TARIC-10 written by rule: the single subdivision, only for `auto_completed` and a written CN-8 (FR-008,
    clarification Q4). `subdivisions` are lookup results or the codes of a stored outcome."""
    if rule != TaricRule.auto_completed or not cn8_written or len(subdivisions) != 1:
        return None
    only = subdivisions[0]
    return only if isinstance(only, str) else only.code


# --------------------------------------------------------------------------- US3: measure groups, the view, the links
DUTIES = frozenset({"103", "105", "106", "107", "112", "115", "117", "119", "122", "123", "141", "142", "143", "145", "146",
                    "147", "488", "489", "490", "651", "652", "653", "654", "695", "696"})
TRADE_DEFENCE = frozenset({"551", "552", "553", "554", "555", "561", "564", "565", "570"})
MEASURE_GROUPS = {"duties": DUTIES, "trade_defence": TRADE_DEFENCE}   # research R-07; every other type is a requirement
GROUPS = ("duties", "trade_defence", "requirements")
EU_TARIC_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp"
EZT_ONLINE_URL = "https://auskunft.ezt-online.de/ezto/Welcome.do"


def measure_group(measure_type: str) -> str:
    """The clerk's group for a measure type, from the fixed table (FR-014); an unknown type is a requirement."""
    for group, types in MEASURE_GROUPS.items():
        if measure_type in types:
            return group
    return "requirements"


@dataclass(frozen=True)
class SubdivisionView:
    code: str
    description: str
    confirm_types: tuple[str, ...]                 # 551-555 or 570 found: the "Trade defence" badge
    groups: dict[str, tuple[Any, ...]]             # GROUPS → the measures as returned, in their returned order

    @property
    def trade_defence(self) -> bool:
        return bool(self.confirm_types)


@dataclass(frozen=True)
class TaricView:
    origin: str
    snapshot_date: date | None
    rule: TaricRule | None
    suggestion: Any                                # TaricSuggestion or None
    suggestion_error: str | None
    taric10: str | None
    subdivisions: tuple[SubdivisionView, ...]


def taric_view(subdivisions: Sequence[Any], origin: str, snapshot_date: date | None, outcome: Any) -> TaricView:
    """What the detail card shows (FR-013, FR-014): the subdivisions `lookup_taric` returned, each with its measures in
    the three groups. Grouping only: no measure is added, dropped or altered. `outcome` is the line's stored
    TaricOutcome for this origin, or None before the TARIC step has run; the rule is then the lookup's (shown only)."""
    views = tuple(SubdivisionView(s.code, s.description, tuple(confirm_types(s)),
                                  {g: tuple(m for m in s.measures if measure_group(m.measure_type) == g) for g in GROUPS})
                  for s in subdivisions)
    rule = outcome.rule if outcome is not None else taric_rule(subdivisions, snapshot_loaded=snapshot_date is not None)
    return TaricView(origin, snapshot_date, rule,
                     outcome.suggestion if outcome is not None else None,
                     outcome.suggestion_error if outcome is not None else None,
                     outcome.taric10 if outcome is not None else None, views)


def eu_taric_url(code: str, origin: str, snapshot_date: date) -> str:
    """The EU TARIC consultation page for the code, origin and snapshot date (research R-08)."""
    return f"{EU_TARIC_URL}?Lang=en&Taric={code}&Area={origin}&SimDate={snapshot_date:%Y%m%d}&LangDescr=en"
