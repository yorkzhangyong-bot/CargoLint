"""Tool 6 — classify_cn8: the CN 2026 eight-digit line under each decided HS-6, with confidence, evidence and an EBTI
ruling as precedent, or the attribute to ask the shipper about (feature 004, contracts/tools.md §1.6).

The model judges; code checks the code, the citation and the attribute, and the threshold rule decides whether the CN-8
is written (constitution Principle I). A failure stays on its line, which routes to review (Principle V)."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, NamedTuple

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from agent.llm import StructuredCaller
from agent.prompts import CN8_SYSTEM, cn8_user
from agent.routing import RulingVote, cn8_gate, cn8_precedent_conflict, cn8_ruling_vote, evidence_match, validate_cn8
from agent.schemas import Cn8Choice, Cn8Gate, Cn8Input, Cn8Line, Cn8Out, Cn8Result, Precedent, VoteCode, WrittenBy
from rag.retriever import stable_order
from tools import register
from tools.common import get_context, run_per_line

log = logging.getLogger(__name__)

RULINGS_PER_CN8 = 2    # research R-02: at most 2 rulings per CN-8 line …
RULINGS_MAX = 8        # … and 8 in all
VECTOR_K = 40          # ruling hits considered when the BTI vectors are loaded
CN8_RETRIES = 1        # one retry on invalid output, then the line's step fails


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


class Rulings(NamedTuple):
    """What select_rulings finds for a line."""

    sent: list[Precedent]       # shown to the model: at most 2 per CN-8 line and 8 in all
    nearest: list[Precedent]    # feature 006: the eligible rulings among the vector hits, nearest first; they vote


def select_rulings(text: str, hs6: str, options: list[tuple[str, str]], kb: Any, as_of: date,
                   exclude_refs: frozenset[str] = frozenset()) -> Rulings:
    """Valid rulings under the HS-6 at one of its CN-8 lines: nearest to the line text when the BTI vectors are loaded,
    else the newest, round-robin across the CN-8 lines; at most 2 per CN-8 line and 8 in all (research R-02). Those of
    them among the vector hits, nearest first, are the ones that vote on the CN-8 (feature 006); without vectors none
    does."""
    allowed = {code for code, _ in options}
    pool = {cn8: [p for p in ps if p.reference not in exclude_refs]
            for cn8, ps in kb.bti.by_cn8(hs6, as_of).items() if cn8 in allowed}
    pool = {cn8: ps for cn8, ps in pool.items() if ps}
    if not pool:
        return Rulings([], [])
    vectors = getattr(kb, "bti_vectors", None)
    nearest: list[Precedent] = []
    if vectors is not None:
        vec = vectors.embed_query_cached(text)   # feature 006: one embedding request per line text, then from the cache
        hits = vectors.search_by_vector(vec, VECTOR_K, None, where={"code": hs6})
        rank = {doc_id.removeprefix("bti:"): i for i, doc_id in enumerate(stable_order(hits))}
        ordered = sorted((p for ps in pool.values() for p in ps), key=lambda p: rank.get(p.reference, len(rank)))
        nearest = [p for p in ordered if p.reference in rank]
    else:
        ordered = [ps[depth] for depth in range(RULINGS_PER_CN8) for cn8, ps in sorted(pool.items()) if depth < len(ps)]
    chosen: list[Precedent] = []
    per_cn8: dict[str, int] = {}
    for p in ordered:
        cn8 = p.code[:8]
        if per_cn8.get(cn8, 0) >= RULINGS_PER_CN8:
            continue
        chosen.append(p)
        per_cn8[cn8] = per_cn8.get(cn8, 0) + 1
        if len(chosen) == RULINGS_MAX:
            break
    return Rulings(chosen, nearest)


def _vote_fields(vote: RulingVote | None) -> dict[str, Any]:
    """The vote as Cn8Choice keeps it; nothing when no ruling voted."""
    if vote is None:
        return {}
    return {"majority_cn8": vote.majority_cn8, "majority_share": vote.majority_share,
            "competing": [VoteCode(cn8=cn8, countries=countries) for cn8, countries in vote.competing]}


def choose_cn8(line: Any, hs6: str, kb: Any, client: StructuredCaller | None, threshold: int, as_of: date,
               exclude_refs: frozenset[str] = frozenset()) -> Cn8Choice:
    """The CN-8 step for one line. `line` has line_no, text_zh, text_en and optionally extracted. Model and schema
    failures come back as a choice with `error`; they never raise."""
    options = kb.index.cn8_lines(hs6)
    if len(options) == 1:   # FR-004: nothing to judge
        return Cn8Choice(hs6=hs6, options=options, cn8=options[0][0], confidence=100, written_by=WrittenBy.rule,
                         rationale="the only CN-8 line under this subheading", gate_reason=Cn8Gate.single_line)
    if not options:
        return Cn8Choice(hs6=hs6, options=[], error=f"no CN-8 lines found under {hs6} in CN 2026")
    text = " / ".join(t for t in (line.text_zh, line.text_en) if t)
    found = select_rulings(text, hs6, options, kb, as_of, exclude_refs)
    rulings = found.sent
    try:
        if client is None:
            raise RuntimeError("no model client available")
        out = client.call(Cn8Out, CN8_SYSTEM, cn8_user(line, hs6, kb.index.subheading_text(hs6), options, rulings),
                          max_retries=CN8_RETRIES)
    except Exception as exc:  # noqa: BLE001 - the line routes to review with the error (Principle V)
        log.warning("CN-8 step failed for line %s: %s", line.line_no, type(exc).__name__)
        return Cn8Choice(hs6=hs6, options=options, error=_error(exc))
    vote = cn8_ruling_vote([(p.code[:8], p.member_state) for p in found.nearest], out.cn8)   # constitution 1.4.0
    voted = _vote_fields(vote)
    attribute = out.deciding_attribute.strip()
    ex = getattr(line, "extracted", None)
    words = text if ex is None else f"{text} / {ex.material} {ex.part_name} {ex.use}"   # what the shipper confirmed counts too
    rule = evidence_match(out.evidence, words) if out.attribute_visible and out.cn8 is not None else None
    if rule is None:
        # FR-003: decide nothing and ask the shipper; without words of the line as evidence the attribute is not visible
        attribute = attribute or "the attribute that separates the CN-8 lines"
        return Cn8Choice(hs6=hs6, options=options, deciding_attribute=attribute, question=f"Ask the shipper for: {attribute}",
                         evidence=out.evidence, rationale=out.rationale, **voted)
    if not validate_cn8(out.cn8, options):              # FR-002: discarded, never shown
        return Cn8Choice(hs6=hs6, options=options, deciding_attribute=attribute,
                         error=f"the model chose {out.cn8}, which is not a CN-8 line of {hs6}", **voted)
    precedent = {p.reference: p for p in rulings}.get(out.precedent or "")   # a citation counts only if it was sent
    conflict = cn8_precedent_conflict(out.cn8, precedent.code if precedent else None)   # no ruling is no conflict
    written, gate = cn8_gate(out.confidence, threshold, single_line=False, precedent_conflict=conflict, vote=vote)
    return Cn8Choice(hs6=hs6, options=options, cn8=out.cn8, confidence=out.confidence, evidence=out.evidence,
                     evidence_rule=rule, rationale=out.rationale, deciding_attribute=attribute, precedent=precedent,
                     written_by=WrittenBy.rule if written else None, gate_reason=gate, **voted)


def classify_cn8_lines(inp: Cn8Input, kb: Any, client: StructuredCaller | None, exclude_refs: frozenset[str] = frozenset(),
                       workers: int = 4) -> list[Cn8Result]:
    def one(line: Cn8Line) -> Cn8Result:
        choice = choose_cn8(line, line.hs6, kb, client, inp.threshold, inp.as_of, exclude_refs)
        return Cn8Result(line_no=line.line_no, choice=choice, status="failed" if choice.error else "checked",
                         error_reason=choice.error)

    def on_error(line: Cn8Line, exc: BaseException) -> Cn8Result:   # e.g. the per-line timeout
        choice = Cn8Choice(hs6=line.hs6, options=kb.index.cn8_lines(line.hs6), error=_error(exc))
        return Cn8Result(line_no=line.line_no, choice=choice, status="failed", error_reason=choice.error)

    return run_per_line(inp.lines, one, on_error, workers=workers)


def needs_cn8(store: Any, line: Any) -> str | None:
    """The decided HS-6 of a line that still needs the CN-8 step, else None. A choice for the same HS-6 stays, unless
    its step failed."""
    hs6, _ = store.decided_code(line)
    if not hs6:
        return None
    c = line.current.cn8
    if c is not None and c.hs6 == hs6 and c.error is None:
        return None
    return hs6


def run_cn8_step(store: Any, kb: Any, client: StructuredCaller | None, line_nos: list[int] | None = None,
                 workers: int = 4) -> list[Cn8Result]:
    """Run the step for the given lines (or every line that needs it) and write the results through the store."""
    lines = []
    for line in store.lines:
        if line_nos and line.line_no not in line_nos:
            continue
        hs6 = needs_cn8(store, line)
        if hs6 is None:
            continue
        v = line.current
        lines.append(Cn8Line(line_no=line.line_no, text_zh=v.text_zh, text_en=v.text_en, extracted=v.extracted, hs6=hs6))
    if not lines:
        return []
    inp = Cn8Input(lines=lines, as_of=date.today(), threshold=store.shipment.threshold)
    results = classify_cn8_lines(inp, kb, client, workers=workers)
    for r in results:
        store.set_cn8_result(r.line_no, r.choice)
    return results


def summarize(results: list[Cn8Result]) -> str:
    if not results:
        return "No line needed a CN-8"
    written = sum(1 for r in results if r.choice.cn8 and r.choice.written_by)
    suggested = sum(1 for r in results if r.choice.cn8 and not r.choice.written_by)
    asked = sum(1 for r in results if r.choice.question)
    failed = sum(1 for r in results if r.choice.error)
    parts = [f"{written} written"] + ([f"{suggested} to confirm"] if suggested else []) \
        + ([f"{asked} to ask the shipper"] if asked else []) + ([f"{failed} failed"] if failed else [])
    return f"CN-8 for {len(results)} line{'s' if len(results) != 1 else ''}: " + ", ".join(parts)


class Cn8Args(BaseModel):
    line_nos: list[int] | None = Field(default=None, description="Line numbers; omit for every line with a decided HS-6 "
                                                                 "and no CN-8 choice yet")


@tool("classify_cn8", args_schema=Cn8Args)
def classify_cn8_tool(line_nos: list[int] | None = None) -> str:
    """Choose the CN 2026 eight-digit code under each decided HS-6 subheading, with confidence, evidence and an EBTI
    ruling as precedent, or name the attribute to ask the shipper about. Call after lookup_precedent."""
    ctx = get_context()
    results = run_cn8_step(ctx.store, ctx.kb, ctx.client, line_nos, workers=ctx.workers or 4)
    payload = {
        "summary": summarize(results),
        "lines": [{"line_no": r.line_no, "cn8": r.choice.cn8, "written": bool(r.choice.written_by), "question": r.choice.question,
                   "error": r.choice.error} for r in results],
    }
    return json.dumps(payload, ensure_ascii=False)


register(classify_cn8_tool)
