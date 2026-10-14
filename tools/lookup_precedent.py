"""Tool 4 — lookup_precedent: current BTI rulings for candidate codes (FR-015)."""
from __future__ import annotations

import json
from datetime import date

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.schemas import LookupPrecedentOutput
from rag.bti import BTIStore
from tools import register
from tools.common import get_context


def lookup_precedents(codes: list[str], bti: BTIStore, as_of: date, limit: int = 3) -> LookupPrecedentOutput:
    seen: list[str] = []
    for c in codes:
        if c and c not in seen:
            seen.append(c)
    by_code = {c: bti.lookup(c, as_of, limit=limit) for c in seen}
    return LookupPrecedentOutput(by_code={c: v for c, v in by_code.items() if v},
                                 none_found=[c for c, v in by_code.items() if not v])


class LookupArgs(BaseModel):
    line_nos: list[int] | None = Field(default=None, description="Lines whose candidate codes should be looked up; omit for all")
    all_pending: bool = Field(default=False, description="Look up every line that has candidates but no precedent check yet")


@tool("lookup_precedent", args_schema=LookupArgs)
def lookup_precedent_tool(line_nos: list[int] | None = None, all_pending: bool = False) -> str:
    """Find current European Binding Tariff Information (BTI) rulings for the suggested HS-6 codes of the given
    lines. Expired rulings are excluded. Call after classify_hs6."""
    ctx = get_context()
    store = ctx.store
    targets = [l for l in store.lines if (not line_nos or l.line_no in line_nos)
               and (not all_pending or (l.current.candidates and not l.current.precedents_checked))]
    codes = [c.code for l in targets for c in l.current.candidates]
    out = lookup_precedents(codes, ctx.kb.bti, date.today())
    matched = 0
    for line in targets:
        store.update_precedents(line.line_no, out.by_code)
        matched += sum(1 for c in line.current.candidates if c.precedent is not None)
    payload = {"summary": f"{matched} BTI rulings matched" + (f", none for {len(out.none_found)} codes" if out.none_found else ""),
               "by_code": {c: [p.reference for p in v] for c, v in out.by_code.items()}, "none_found": out.none_found}
    return json.dumps(payload, ensure_ascii=False)


register(lookup_precedent_tool)
