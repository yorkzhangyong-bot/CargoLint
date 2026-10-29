"""What the two pages show about a line, computed from the line store with no model call and no write (feature 005,
contracts/view.md). Pure: no Streamlit import. The pages render what these functions return and never re-derive it.

The module reads the store only through its methods (`effective_route`, `decided_code`, `decided_cn8`,
`decided_taric10`, `cn8_pending`, `taric_pending`, `ready_to_accept`) and the line records it returns. It never names
the TARIC tool: tests/unit/test_taric_store.py forbids that in ui/ and app.py."""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Any

from agent.config import MAX_DESC_CHARS
from agent.routing import cn8_precedent_conflict, hs6_choice, hs6_gate
from agent.schemas import ChosenHow, Cn8Gate, CreatedBy, DecisionRoute, FlagKind, Hs6Gate, TaricRule, WrittenBy
from agent.schemas import LineStatus as CheckStatus
from tools.parsers import split_mixed

STATUS_MAX = 44          # status texts are cut here; lock reasons, questions and reason lines never are
CLOSE_POINTS = 10        # "too close to call": the top two confidences differ by at most this (research R-16)
RULE_LABEL = {"ics2_unacceptable": "ICS2 unacceptable term", "ics2_stop_words": "ICS2 stop word",
              "firm_stop_words": "firm stop word"}
UNLOCK = " — update the description and re-check"
ASK_FACTS = "Please state the exact product name, the material and the intended use."
ASK_FACTS_ZH = "请说明确切的产品名称、材质和用途。"
NOT_8_DIGITS = {TaricRule.not_available: "TARIC not available", TaricRule.not_loaded: "TARIC not loaded"}


@dataclass(frozen=True)
class LineStatus:
    """What the table shows for one line (data-model §1)."""

    colour: str                      # green, yellow, red or grey
    text: str
    action: str | None = None        # Choose, Update, Change or None
    kind: str | None = None          # a_hs6, a_cn8, a_change, b, c, c_failed or None
    selectable: bool = False         # a Ready line: green and not accepted yet, for "Accept all K ready"
    lock_reason: str | None = None   # red lines: "Accept" is disabled with this reason
    question: str | None = None      # red lines with a question: the full English question
    accepted: bool = False


@dataclass(frozen=True)
class CodeDisplay:
    text: str
    note: str | None = None


# --------------------------------------------------------------------------- small helpers
def spaced(code: str | None) -> str:
    """"9503.00" → "9503 00", "87149110" → "8714 91 10", "7318155810" → "7318 15 58 10"."""
    digits = re.sub(r"\D", "", code or "")
    return " ".join(g for g in (digits[:4], digits[4:6], digits[6:8], digits[8:10]) if g)


def cut(text: str, limit: int = STATUS_MAX) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _term_based(flag: Any) -> bool:
    return bool(flag.matched_term and flag.rule_source is not None and flag.rule_source.value != "judgement")


def _rule_label(flag: Any) -> str:
    return RULE_LABEL.get(flag.rule_source.value, "rule") if flag.rule_source is not None else "rule"


def _cn8_options(store: Any, line: Any, hs6: str | None) -> list[tuple[str, str]]:
    """The (CN-8, label path) lines under the HS-6: the CN-8 step's own options, else the nomenclature's."""
    c = line.current.cn8
    if c is not None and c.hs6 == hs6 and c.options:
        return list(c.options)
    return store.index.cn8_lines(hs6) if hs6 and store.index is not None else []


def _cn8_line_count(store: Any, line: Any, hs6: str | None) -> int:
    return len(_cn8_options(store, line, hs6))


# --------------------------------------------------------------------------- §1 next step and status
def _taric_step_missing(store: Any, line: Any, hs6: str | None) -> bool:
    """A CN-8 chosen under the decided HS-6 with no TARIC outcome for the shipment's origin: the same stored fields
    the TARIC tool's own test reads."""
    c, t = line.current.cn8, line.current.taric
    if c is None or not c.cn8 or c.question or c.error or hs6 is None or c.hs6 != hs6:
        return False
    return t is None or t.origin != store.shipment.taric_origin


def next_step(store: Any, line: Any) -> str | None:
    """The step a line still waits for, or None."""
    v = line.current
    if v.status == CheckStatus.pending:
        return "stop-word check" if v.flag is None else "HS-6 step"
    hs6 = store.decided_code(line)[0]
    c = v.cn8
    if hs6 and (c is None or c.hs6 != hs6):
        return "CN-8 step"
    if _taric_step_missing(store, line, hs6):
        return "TARIC step"
    return None


def _accepted(line: Any) -> bool:
    v = line.current
    c, t = v.cn8, v.taric
    return bool(v.decision is not None and v.decision.route == DecisionRoute.accepted and c is not None
                and c.written_by == WrittenBy.clerk and t is not None
                and (t.written_by == WrittenBy.clerk or t.rule in NOT_8_DIGITS))


def _red(text: str, kind: str, lock: str, question: str | None) -> LineStatus:
    return LineStatus("red", cut(text), "Update", kind, lock_reason=lock, question=question)


def _taric_pick_text(t: Any) -> str:
    subs = t.subdivisions
    if len(subs) == 1:
        return f"Confirm: {spaced(subs[0])}"
    if len(subs) == 2:
        return f"Pick: {subs[0][-2:]} or {subs[1][-2:]}"
    k = len(t.trade_defence)
    return f"Pick: {len(subs)} options, {k} AD" if k else f"Pick: {len(subs)} options"


def _review_text(store: Any, line: Any) -> str:
    v = line.current
    if store.ready_to_accept(line):   # feature 008: the candidate the precedent override chose, or the top one
        return f"Confirm: {spaced(hs6_choice(v.candidates, v.hs6_vote, v.hs6_gate)[1])}"
    n = len(v.candidates[:3])
    return "Pick: no candidate" if n == 0 else f"Pick: {_plural(n, 'candidate')}"


def line_status(store: Any, line: Any, activity: str | None = None) -> LineStatus:
    """The colour, text, action and kind of one line: the first matching row of contracts/view.md §1."""
    v = line.current
    if activity == "recheck_queued":
        return LineStatus("grey", "Queued: re-check")
    step = next_step(store, line)
    if activity and step:
        return LineStatus("grey", cut(f"Running {step}…" if activity == "running" else f"Queued: {step}"))
    if v.status == CheckStatus.failed:
        return _red("Check failed", "c_failed", "Locked: the check failed — re-check the line", None)
    if v.status == CheckStatus.pending:
        return LineStatus("grey", "Not checked yet")
    route = store.effective_route(line)
    hs6 = store.decided_code(line)[0]
    c, t = v.cn8, v.taric
    question_en = question(store, line, "en")
    if v.flag is not None and v.flag.kind != FlagKind.ok:                                   # row 4
        if _term_based(v.flag):
            term = v.flag.matched_term
            return _red(f"Ask: what exactly is “{term}”?", "c", f"Locked: {_rule_label(v.flag)} '{term}'{UNLOCK}", question_en)
        facts = ", ".join(a.replace("_", " ") for a in v.flag.ask_for) or "material, product name, use"
        return _red(f"Ask: {facts}?", "c", "Locked: vague description" + UNLOCK, question_en)
    if v.unreadable:                                                                         # row 5
        return _red("Ask: unreadable line", "c", "Locked: the description could not be read" + UNLOCK, question_en)
    if route == "ask_shipper" and c is not None and c.question:                              # row 6
        attribute = c.deciding_attribute or "an attribute the description does not state"
        short = re.sub(r"^whether\s+", "", attribute)
        return _red(f"Ask: {short}?", "c", f"Locked: the CN-8 depends on {attribute}{UNLOCK}", question_en)
    if route == "ask_shipper":                                                               # row 7
        text = "Ask: which TARIC subdivision applies?" if t is not None and t.question else "Ask: what exactly are the goods?"
        return _red(text, "c", "Locked: sent to the shipper" + UNLOCK, question_en)
    if c is not None and c.error and hs6 and c.hs6 == hs6:                                   # row 8
        return LineStatus("yellow", cut(f"Pick: CN-8, {_plural(_cn8_line_count(store, line, hs6), 'line')}"), "Choose", "a_cn8")
    if route == "review":                                                                    # row 9
        return LineStatus("yellow", cut(_review_text(store, line)), "Choose", "a_hs6")
    if step == "CN-8 step" or store.cn8_pending(line):                                       # rows 10, 11
        return LineStatus("yellow", cut(f"Pick: CN-8, {_plural(_cn8_line_count(store, line, hs6), 'line')}"), "Choose", "a_cn8")
    if step == "TARIC step":                                                                 # row 12
        return LineStatus("yellow", cut(f"Confirm: {spaced(c.cn8)}"), "Choose", "a_cn8")
    if store.taric_pending(line):                                                            # row 13
        return LineStatus("yellow", cut(_taric_pick_text(t)), "Choose", "b")
    accepted = _accepted(line)                                                               # row 14
    return LineStatus("green", "Accepted" if accepted else "Ready", "Change", "a_change", selectable=not accepted,
                      accepted=accepted)


# --------------------------------------------------------------------------- §7.3 questions
def _subdivision_text(code: str, description: str, zh: bool) -> str:
    if description:
        return description
    if code.endswith("00"):
        return "整个 CN-8" if zh else "the whole CN-8"
    return "无说明" if zh else "no description"


def _taric_question_zh(store: Any, line: Any, kb: Any) -> str:
    from agent.agent import line_taric_view

    view = line_taric_view(store, kb, line.line_no) if kb is not None else None
    texts = {sv.code: sv.description for sv in (view.subdivisions if view is not None else ())}
    codes = line.current.taric.subdivisions
    items = "；".join(f"{spaced(c)}（{_subdivision_text(c, texts.get(c, ''), True)}）" for c in codes)
    return f"请说明以下哪一个 TARIC 细分适用：{items}。"


def question(store: Any, line: Any, lang: str = "en", kb: Any = None) -> str | None:
    """The full question of a red line, in English or Chinese (contracts/view.md §7.3); None when it has none."""
    v = line.current
    if v.status != CheckStatus.checked:
        return None
    zh = lang == "zh"
    flag = v.flag
    if flag is not None and flag.kind != FlagKind.ok:
        if _term_based(flag):
            term = flag.matched_term
            return f"“{term}”不能作为货物描述。{ASK_FACTS_ZH}" if zh else f"“{term}” is not accepted as a goods description. {ASK_FACTS}"
        return "该描述过于笼统，无法用于海关申报。" + ASK_FACTS_ZH if zh else "The description is too general for customs. " + ASK_FACTS
    if v.unreadable:
        return "我们无法读取您单据中的这一行。" + ASK_FACTS_ZH if zh else "We could not read this line of your document. " + ASK_FACTS
    route = store.effective_route(line)
    if route != "ask_shipper":
        return None
    c, t = v.cn8, v.taric
    if c is not None and c.question:
        attribute = c.deciding_attribute or "the attribute the description does not state"
        return f"请确认以下信息：{attribute}" if zh else f"Please confirm {attribute}."
    if t is not None and t.question:
        return _taric_question_zh(store, line, kb) if zh else t.question
    return ASK_FACTS_ZH if zh else ASK_FACTS


# --------------------------------------------------------------------------- §2.1, §2.3 kind (c): reasons and candidates
def _close(candidates: list) -> bool:
    return len(candidates) >= 2 and candidates[0].confidence - candidates[1].confidence <= CLOSE_POINTS


def reason_line(store: Any, line: Any) -> str | None:
    """Why a red line waits for the shipper (contracts/view.md §2.1); a term-based flag always wins."""
    v = line.current
    if v.status == CheckStatus.failed:
        return f"Reason: the check failed — {v.error_reason}"
    flag = v.flag
    if flag is not None and flag.kind != FlagKind.ok:
        if _term_based(flag):
            return f"Reason: {_rule_label(flag)} '{flag.matched_term}'"
        return "Reason: candidates too close" if _close(v.candidates) else f"Reason: vague description — {flag.reason}"
    if v.unreadable:
        return "Reason: the description could not be read"
    if store.effective_route(line) != "ask_shipper":
        return None
    c = v.cn8
    if c is not None and c.question:
        attribute = c.deciding_attribute or "an attribute the description does not state"
        return f"Reason: the CN-8 depends on {attribute}, which the description does not state"
    return "Reason: you sent this line to the shipper"


# --------------------------------------------------------------------------- §3 code display
def code_display(store: Any, line: Any) -> CodeDisplay:
    """The decided digits in 4-2-2-2 groups with underscores, or the 8 digits and why the line stops there."""
    t10, cn8, hs6 = store.decided_taric10(line), store.decided_cn8(line), store.decided_code(line)[0]
    t = line.current.taric
    if cn8 and not t10 and t is not None and t.rule in NOT_8_DIGITS and t.origin == store.shipment.taric_origin:
        return CodeDisplay(spaced(cn8), NOT_8_DIGITS[t.rule])
    digits = (t10 or cn8 or (hs6 or "").replace(".", "")).ljust(10, "_")
    return CodeDisplay(f"{digits[:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}")


# --------------------------------------------------------------------------- §5 kind (a) rows and the HS-6 candidates block
OTHER = "other"                  # the pick of "Other HS-6 code…"
FORMS = {"HS-6": "hs6", "CN-8": "cn8", "TARIC-10": "taric10"}
CHANGE_NOTE = "Pick another code to override it. The later steps run again after your pick."


@dataclass(frozen=True)
class CandidateRow:
    """One row of kind (a) or of the HS-6 candidates block (data-model §1)."""

    code: str                        # shown: "8518 30", its single CN-8 line "9617 00 00", or a CN-8 "9503 00 75"
    value: str                       # what the store takes: the HS-6 "8518.30" or the CN-8 "95030075"
    description: str
    confidence: int | None = None
    rationale: str | None = None
    history_only: bool = False
    precedent: Any = None


def _path(path: str) -> list[str]:
    return [p.strip() for p in (path or "").split(" > ") if p.strip()]


def hs6_rows(store: Any, line: Any) -> list[CandidateRow]:
    """Up to three candidates in stored order, each described by its heading and subheading labels; a subheading with
    one CN-8 line shows that line."""
    rows = []
    for c in line.current.candidates[:3]:
        lines = store.index.cn8_lines(c.code) if store.index is not None else []
        path = store.index.label_path(c.code) if store.index is not None else []
        rows.append(CandidateRow(spaced(lines[0][0] if len(lines) == 1 else c.code), c.code,
                                 " › ".join(path) or c.subheading_text, c.confidence, c.rationale or None,
                                 c.history_only, c.precedent))
    return rows


def cn8_rows(store: Any, line: Any) -> list[CandidateRow]:
    """Every CN-8 line under the decided HS-6 with its whole label path; only the chosen CN-8 carries a confidence, a
    rationale and a precedent, and only when it is a model estimate."""
    hs6 = store.decided_code(line)[0]
    c = line.current.cn8
    options = _cn8_options(store, line, hs6)
    estimate = c is not None and c.hs6 == hs6 and bool(c.cn8) and c.confidence > 0 and len(options) > 1
    rows = []
    for code, path in options:
        chosen = estimate and code == c.cn8
        rows.append(CandidateRow(spaced(code), code, " › ".join(_path(path)), c.confidence if chosen else None,
                                 (c.rationale or None) if chosen else None, False, c.precedent if chosen else None))
    return rows


def change_forms(store: Any, line: Any) -> list[str]:
    """The levels "Change the code at" offers on a decided line (feature 012; the HS-6 changes through the candidates):
    CN-8 when the decided HS-6 has more than one CN-8 line; TARIC-10 when the stored TARIC outcome has more than one
    subdivision."""
    forms = []
    hs6 = store.decided_code(line)[0]
    if hs6 and len(_cn8_options(store, line, hs6)) > 1:
        forms.append("CN-8")
    t = line.current.taric
    if store.decided_cn8(line) and t is not None and len(t.subdivisions) > 1:
        forms.append("TARIC-10")
    return forms


def preselect(store: Any, line: Any, kind: str, form: str) -> tuple[str | None, str]:
    """The pick a form opens with, and the code "Other HS-6 code…" holds (contracts/view.md §5, §6)."""
    v = line.current
    if form == "hs6":
        codes = [c.code for c in v.candidates[:3]]
        if kind == "a_change":
            hs6 = store.decided_code(line)[0]
            return (hs6, "") if hs6 in codes else (OTHER, hs6 or "")
        return hs6_choice(v.candidates, v.hs6_vote, v.hs6_gate)[1], ""   # feature 008: the override's candidate, or the top
    if kind == "a_change":
        return (store.decided_cn8(line) if form == "cn8" else store.decided_taric10(line)), ""
    if form == "cn8":
        hs6 = store.decided_code(line)[0]
        c = v.cn8
        if c is not None and c.hs6 == hs6 and c.cn8:
            return c.cn8, ""
        options = _cn8_options(store, line, hs6)
        return (options[0][0] if options else None), ""
    t = v.taric
    if t is None or not t.subdivisions:
        return None, ""
    return (t.suggestion.code if t.suggestion is not None else t.subdivisions[0]), ""


def _hs6_how(line: Any) -> str:
    v = line.current
    conf, d = v.top_confidence, v.decision
    if v.hs6_gate == Hs6Gate.vote_agrees:   # feature 006: the nearest rulings decided, not the estimate
        n, m = _hs6_votes(v.hs6_vote, v.hs6_vote.majority)
        auto = f"auto-accepted, {n} of {m} nearest rulings agree"
    elif v.hs6_gate == Hs6Gate.vote_override:   # feature 008: the nearest rulings chose the model's candidate 2 or 3
        rank, code = hs6_choice(v.candidates, v.hs6_vote, v.hs6_gate)
        n, m = _hs6_votes(v.hs6_vote, code)
        auto = (f"candidate {rank} chosen, rulings overrode the model: {n} of {m} agree on {spaced(code)} "
                f"({_hs6_countries(v.hs6_vote, code)}); the model's top candidate was {spaced(v.top_code)}")
    else:
        auto = f"auto-accepted at {conf} %"
    if d is None:
        return auto
    return {ChosenHow.auto: f"{auto}, accepted by you", ChosenHow.top: "confirmed by you",
            ChosenHow.other_candidate: "chosen by you", ChosenHow.typed: "typed by you"}[d.chosen_how]


def _hs6_votes(vote: Any, code: str | None) -> tuple[int, int]:
    """Feature 006: the nearest rulings at the HS-6, and the rulings that voted."""
    return (sum(len(countries) for c, countries in vote.competing if c == code),
            sum(len(countries) for _, countries in vote.competing))


def _hs6_rulings(vote: Any) -> str:
    """Feature 006: the HS-6 codes the nearest rulings sit at, with the issuing country of every ruling."""
    return ", ".join(f"{spaced(c)} ({', '.join(k or '?' for k in countries)})" for c, countries in vote.competing)


def _hs6_countries(vote: Any, code: str | None) -> str:
    """Feature 008: the issuing country of every nearest ruling at the HS-6, joined as _hs6_rulings joins them."""
    return ", ".join(k or "?" for c, countries in vote.competing if c == code for k in countries)


def _votes(c: Any, cn8: str | None) -> tuple[int, int]:
    """Feature 006: the nearest rulings at the CN-8, and the rulings that voted."""
    return sum(len(v.countries) for v in c.competing if v.cn8 == cn8), sum(len(v.countries) for v in c.competing)


def _rulings(c: Any) -> str:
    """Feature 006: the CN-8 lines the nearest rulings sit at, with the issuing country of every ruling, so the clerk
    can weigh them: "9403 20 80 (XI, IE, FR), 9403 20 20 (DE, FR)"."""
    return ", ".join(f"{spaced(v.cn8)} ({', '.join(k or '?' for k in v.countries)})" for v in c.competing)


def _decided(store: Any, line: Any) -> str:
    v = line.current
    parts = [f"HS-6 {spaced(store.decided_code(line)[0])}, {_hs6_how(line)}"]
    cn8, c = store.decided_cn8(line), v.cn8
    if cn8:
        n, m = _votes(c, cn8)
        how = ("confirmed by you" if c.written_by == WrittenBy.clerk else
               "single CN-8 line" if len(c.options) == 1 else
               f"written by rule, {n} of {m} nearest rulings agree" if c.gate_reason == Cn8Gate.vote_agrees else
               f"written by rule at a model estimate of {c.confidence} %")
        parts.append(f"CN-8 {spaced(cn8)}, {how}")
    t10, t = store.decided_taric10(line), v.taric
    if t10:
        parts.append(f"TARIC-10 {spaced(t10)}, {'confirmed by you' if t.written_by == WrittenBy.clerk else 'auto-completed'}")
    elif cn8 and t is not None and t.rule in NOT_8_DIGITS:
        parts.append(NOT_8_DIGITS[t.rule])
    return "Decided: " + " · ".join(parts)


def explain_a(store: Any, line: Any, kind: str) -> tuple[str, str]:
    """The two explanation lines of kind (a) (FR-014); for `a_change`, who decided each code."""
    v = line.current
    threshold = store.shipment.threshold
    if kind == "a_change":
        return _decided(store, line), CHANGE_NOTE
    if kind == "a_hs6":
        if not v.candidates:
            return "", "No valid candidate was found. Type the HS-6 code, or ask the shipper what the goods are."
        top = v.candidates[0]
        first = cut(top.rationale, 200)
        passed, gate = hs6_gate(top.confidence, threshold, v.hs6_vote, store.shipment.hs6_override_min)
        if passed:   # the vote or the threshold accepts it, review only because the line was updated (FR-022)
            why = "this line was flagged before its update" if line.ever_flagged else "this line was updated from the shipper's reply"
            if gate == Hs6Gate.vote_override:   # feature 008: the rulings chose the model's candidate 2 or 3
                rank, code = hs6_choice(v.candidates, v.hs6_vote, gate)
                n, m = _hs6_votes(v.hs6_vote, code)
                return first, (f"Candidate {rank}, {spaced(code)}, is chosen because the rulings overrode the model ({n} of "
                               f"{m} agree on it: {_hs6_countries(v.hs6_vote, code)}), but {why}, so it needs your "
                               "confirmation. TARIC runs after your pick.")
            return first, f"Top candidate leads ({top.confidence} %), but {why}, so it needs your confirmation. TARIC runs after your pick."
        after = "TARIC runs after your pick."
        if gate == Hs6Gate.vote_disagrees:   # feature 006: the nearest rulings decide, not the estimate
            support = f" Precedents support candidate {v.hs6_vote.candidate}." if v.hs6_vote.candidate else ""
            text = f"Rulings disagree: model {spaced(top.code)}, nearest rulings {_hs6_rulings(v.hs6_vote)}.{support} {after}"
            override_min = store.shipment.hs6_override_min   # feature 008: a code outside the candidates is a hint only
            n, m = _hs6_votes(v.hs6_vote, v.hs6_vote.majority)
            if override_min is not None and not v.hs6_vote.candidate and n >= override_min:
                text += f" Hint: {n} of {m} nearest rulings agree on {spaced(v.hs6_vote.majority)}, which is not among the candidates."
            return first, text
        if gate == Hs6Gate.vote_tie:
            return first, f"Rulings split: model {spaced(top.code)}, nearest rulings {_hs6_rulings(v.hs6_vote)}. {after}"
        if gate == Hs6Gate.vote_share_low:
            n, m = _hs6_votes(v.hs6_vote, top.code)
            return first, (f"Rulings too spread: model {spaced(top.code)} has {n} of {m} nearest rulings; "
                           f"{_hs6_rulings(v.hs6_vote)}. {after}")
        return first, (f"Top candidate leads ({top.confidence} %) but is under the {threshold} % auto-accept threshold, so "
                       "you decide. TARIC runs after your pick.")
    hs6, how = store.decided_code(line)
    c = v.cn8
    overrode = ""
    if how == ChosenHow.auto.value and v.hs6_gate == Hs6Gate.vote_override:   # feature 008 (FR-008): on the CN-8 rows too
        agree, voted = _hs6_votes(v.hs6_vote, hs6)
        overrode = f" rulings overrode the model: {agree} of {voted} agree on {spaced(hs6)};"
    first = (f"The HS-6 is {spaced(hs6)};{overrode} its subheading has "
             f"{_plural(_cn8_line_count(store, line, hs6), 'CN-8 line')}.")
    step = next_step(store, line)
    if c is not None and c.error and c.hs6 == hs6:
        return first, f"The CN-8 step failed: {c.error}. Pick the CN-8."
    if step == "CN-8 step":
        return first, ("No CN-8 was chosen for this HS-6 yet; the CN-8 step did not run, for example after a threshold "
                       "change. Pick the CN-8.")
    if not store.cn8_pending(line):                    # rows 10 and 11 come before row 12, as in line_status
        return first, "The TARIC step did not finish for this CN-8. Confirm it to look up TARIC again."
    p = c.precedent
    if p is not None and cn8_precedent_conflict(c.cn8, p.code):
        return first, f"CN-8 to confirm: the cited ruling {p.reference} classifies under {spaced(p.code[:8])}, not this CN-8."
    after = "TARIC runs after your pick."
    if c.gate_reason == Cn8Gate.vote_disagrees:          # constitution 1.4.0: the nearest rulings decide, not the estimate
        return first, f"Rulings disagree: model {spaced(c.cn8)}, nearest rulings {_rulings(c)}. {after}"
    if c.gate_reason == Cn8Gate.vote_tie:
        return first, f"Rulings split: model {spaced(c.cn8)}, nearest rulings {_rulings(c)}. {after}"
    if c.gate_reason == Cn8Gate.vote_share_low:
        n, m = _votes(c, c.cn8)
        return first, f"Rulings too spread: model {spaced(c.cn8)} has {n} of {m} nearest rulings; {_rulings(c)}. {after}"
    return first, (f"CN-8 to confirm: no ruling vote, and its model estimate ({c.confidence} %) is under the {threshold} % "
                   f"threshold. {after}")


# --------------------------------------------------------------------------- §6 kind (b) rows
AD_TYPES = frozenset({"551", "552", "553", "554", "555"})
PREFERENCE_TYPES = frozenset({"142", "143", "145", "146"})
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


@dataclass(frozen=True)
class SubdivisionRow:
    """One row of kind (b) (data-model §1)."""

    code: str                        # the full code, spaced: "7318 15 58 10"
    value: str                       # what the store takes: "7318155810"
    description: str
    duty: str
    anti_dumping: str                # "22 % AD", "22–85 % AD", "AD: {specific duty}", "control" or "none"
    has_trade_defence: bool
    suggested: bool


def _duty(sv: Any) -> str:
    duties = sv.groups.get("duties", ())
    base = next((m.duty for m in duties if m.measure_type == "103"), "")
    pref = next((m.duty for m in duties if m.measure_type in PREFERENCE_TYPES), None)
    text = " · ".join(p for p in (base, f"pref. {pref}" if pref is not None else "") if p)
    return cut(text, 40) if text else "—"


def _anti_dumping(sv: Any) -> str:
    measures = sv.groups.get("trade_defence", ())
    ad = [m for m in measures if m.measure_type in AD_TYPES]
    rates = sorted({float(r) for m in ad for r in _PERCENT.findall(m.duty or "")})
    if rates:
        low, high = f"{rates[0]:g}", f"{rates[-1]:g}"
        return f"{low} % AD" if low == high else f"{low}–{high} % AD"
    if ad:
        return cut(f"AD: {ad[0].duty}", 32)
    return "control" if any(m.measure_type == "570" for m in measures) else "none"


def subdivision_rows(taric_view: Any) -> list[SubdivisionRow]:
    """The subdivisions of the agent's `line_taric_view`, never `kb.taric`: duty, anti-dumping and the suggestion."""
    suggested = taric_view.suggestion.code if taric_view.suggestion is not None else None
    return [SubdivisionRow(spaced(sv.code), sv.code, _subdivision_text(sv.code, sv.description, False), _duty(sv),
                           _anti_dumping(sv), sv.trade_defence, sv.code == suggested) for sv in taric_view.subdivisions]


def explain_b(store: Any, line: Any, taric_view: Any) -> tuple[str, str]:
    """The two explanation lines of kind (b)."""
    c = line.current.cn8
    label = " › ".join(_path(dict(c.options).get(c.cn8, ""))[-2:])
    rows = subdivision_rows(taric_view)
    k = sum(1 for r in rows if r.has_trade_defence)
    first = (f"CN-8 is {spaced(c.cn8)} ({label}). {k} of {len(rows)} subdivisions carry anti-dumping or countervailing "
             f"measures for {taric_view.origin}.")
    if c.written_by == WrittenBy.clerk:
        tail = "CN-8 confirmed by you."
    elif len(c.options) == 1:
        tail = "Single CN-8 line."
    else:
        tail = f"CN-8 written by rule at {c.confidence} %."
    return first, f"Your pick confirms both the CN-8 and the TARIC-10. {tail}"


def taric_question(taric_view: Any) -> str:
    """What "None of these → ask shipper" stores in kind (b): the English TARIC question of §7.3."""
    items = "; ".join(f"{spaced(sv.code)} ({_subdivision_text(sv.code, sv.description, False)})"
                      for sv in taric_view.subdivisions)
    return f"Please state which of these TARIC subdivisions applies: {items}."


# --------------------------------------------------------------------------- §8 text helpers
_MD = re.compile(r"([\\*_\[\]()#+\-.!|><~$:`])")


def md_escape(text: str | None) -> str:
    """Escape the Markdown characters of untrusted text before it reaches a label or Markdown (research R-17)."""
    return _MD.sub(r"\\\1", text or "")


def split_description(text: str) -> tuple[str, str]:
    """An edited description split into (Chinese, English), as today's chat splits pasted lines."""
    return split_mixed(text or "")


def edit_problem(zh: str, en: str) -> str | None:
    """Why a clerk's edit cannot be stored, checked when "Re-check line" is clicked; mirrors update_description."""
    zh, en = (zh or "").strip(), (en or "").strip()
    if not zh and not en:
        return "Write the goods description first."
    if len(zh) > MAX_DESC_CHARS:
        return f"the Chinese text is over {MAX_DESC_CHARS} characters"
    if len(en) > MAX_DESC_CHARS:
        return f"the English text is over {MAX_DESC_CHARS} characters"
    return None


# --------------------------------------------------------------------------- §4 summary, bar and labels
@dataclass(frozen=True)
class Summary:
    lines: int
    seconds: float
    ready: int = 0
    pick: int = 0
    ask: int = 0
    failed: int = 0
    running: int = 0
    to_accept: int = 0


def summary(store: Any, statuses: dict[int, LineStatus]) -> Summary:
    """The counts of the summary bar; `statuses` maps line numbers to their LineStatus."""
    values = list(statuses.values())
    seconds = sum(run.elapsed_s for run in store.shipment.check_runs
                  if any(step.tool == "check_description" for step in run.steps)) if store.has_shipment() else 0.0
    return Summary(lines=len(store.lines) if store.has_shipment() else 0, seconds=seconds,
                   ready=sum(1 for s in values if s.colour == "green"),
                   pick=sum(1 for s in values if s.colour == "yellow"),
                   ask=sum(1 for s in values if s.colour == "red" and s.text != "Check failed"),
                   failed=sum(1 for s in values if s.text == "Check failed"),
                   running=sum(1 for s in values if s.colour == "grey"),
                   to_accept=sum(1 for s in values if s.colour == "green" and not s.accepted))


def accept_all_label(k: int) -> str:
    return f"Accept all {k} ready"


def count_cards(s: Summary) -> list[tuple[str, str, int]]:
    """The counts row's three cards (feature 012, FR-008): label, colour and count. A failed check is red too."""
    return [("Ready to accept", "green", s.to_accept), ("Needs review", "orange", s.pick),
            ("Ask shipper", "red", s.ask + s.failed)]


# --------------------------------------------------------------------------- feature 012: the status line and the origins
def status_line(s: Summary, model: str, *, checking: int | None = None, elapsed: float = 0.0,
                file_name: str | None = None) -> str:
    """The line under the check buttons (feature 012, FR-007). While a check runs, `checking` is its line count: its
    lines and time, or the file's name before its lines are read. Otherwise the lines checked, the file they came from,
    their time and the model; "" before the first line."""
    if checking is not None:
        what = _plural(checking, "line") if checking else (file_name or "the file")
        return f"Checking {what}… {elapsed:.0f} s"
    if not s.lines:
        return ""
    source = f" of {file_name}" if file_name else ""
    return f"Checked {_plural(s.lines, 'line')}{source} in {s.seconds:.0f} s · model: {model}"


# The Origin box's choices (feature 012, FR-003): the ISO 3166-1 alpha-2 codes and TARIC's six country codes outside
# ISO: XC Ceuta, XI Northern Ireland, XK Kosovo, XL Melilla, XS Serbia, XU the United Kingdom without Northern Ireland.
ORIGIN_CODES = tuple("""
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC
    CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD
    GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH
    KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW
    MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC
    SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY
    UZ VA VC VE VG VI VN VU WF WS XC XI XK XL XS XU YE YT ZA ZM ZW
""".split())


# --------------------------------------------------------------------------- feature 012: the list's rows (FR-009, FR-010)
BADGES = {"green": ("Ready", "green"), "yellow": ("Review", "orange"), "red": ("Ask shipper", "red"),
          "grey": ("Checking…", "gray")}
ROW_GROUPS = {"red": 0, "yellow": 1, "green": 2, "grey": 4}   # accepted lines come after the Ready ones, as 3


def sort_group(status: LineStatus) -> int:
    """The list's order (FR-009): ask shipper, review, ready, accepted, then the lines still being checked."""
    return 3 if status.accepted else ROW_GROUPS[status.colour]


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def need_text(store: Any, line: Any) -> str:
    """What a red line needs (FR-010): the facts its flag asks for, the open question, or the failed check."""
    v = line.current
    if v.status == CheckStatus.failed:
        return "check failed"
    if v.flag is not None and v.flag.kind != FlagKind.ok:
        return "needs " + _and([a.replace("_", " ") for a in v.flag.ask_for] or ["material", "product name", "use"])
    if v.unreadable:
        return "needs a readable description"
    c, t = v.cn8, v.taric
    if c is not None and c.question:
        return f"needs: {c.deciding_attribute or 'an attribute the description does not state'}"
    if t is not None and t.question:
        return "needs: which TARIC subdivision applies"
    return "needs: what exactly the goods are"


@dataclass(frozen=True)
class RowCells:
    """One row of the list (FR-010), from the line store."""

    badge: str                       # Ready, Accepted, Review, Ask shipper or Checking…
    colour: str                      # the badge's colour: green, orange, red or gray
    filed: str                       # the line as filed: its first version's text
    need: str                        # a red line's need, else the current description
    code: str                        # the HS code cell, or "—"
    note: str | None                 # why the code stops at 8 digits
    conf: str                        # the HS-6 candidate's confidence, or "—"


def _confidence(line: Any, code: str | None) -> str:
    c = next((c for c in line.current.candidates[:3] if c.code == code), None)
    return f"{c.confidence}%" if c is not None else "—"


def row_cells(store: Any, line: Any, status: LineStatus, selected: str | None = None) -> RowCells:
    """The row's cells. Before a CN-8 is decided, the HS code is the HS-6: the decided one, else the candidate the line
    would take; after it, `code_display`. `selected` is the open line's choice in its candidates (D5): another code is
    shown with its confidence, before anything is written."""
    label, colour = ("Accepted", "green") if status.accepted else BADGES[status.colour]
    v = line.current
    need = need_text(store, line) if status.colour == "red" else v.display_text
    hs6 = store.decided_code(line)[0] or hs6_choice(v.candidates, v.hs6_vote, v.hs6_gate)[1]
    if selected is not None and selected != hs6:
        return RowCells(label, colour, line.versions[0].display_text, need, selected or "—", None,
                        _confidence(line, selected))
    code, note = hs6 or "—", None
    if store.decided_cn8(line):
        d = code_display(store, line)
        code, note = d.text, d.note
    return RowCells(label, colour, line.versions[0].display_text, need, code, note, _confidence(line, hs6))


# --------------------------------------------------------------------------- feature 012: the open line's blocks (FR-011)
def stop_word_result(line: Any) -> str:
    """Block 1: what the stop-word check found."""
    v = line.current
    if v.status == CheckStatus.failed:
        return "the check failed"
    if v.unreadable:
        return "the line could not be read"
    if v.flag is None:
        return "not run yet"
    if v.flag.kind == FlagKind.ok:
        return "none found"
    if _term_based(v.flag):
        return f"{_rule_label(v.flag)} '{v.flag.matched_term}'"
    return "vague description"


def candidate_label(r: CandidateRow) -> str:
    """Block 2's choice for one candidate: the dotted HS-6, its subheading's label (after its heading's when the label
    alone says little, as "Other" does), and its confidence."""
    path = r.description.split(" › ")
    text = path[-1] if len(path) == 1 or len(path[-1]) >= 20 else f"{cut(path[-2], 35)} › {path[-1]}"
    return f"{r.value} {cut(text, 55)} — {r.confidence}%"   # one line, so its confidence bar sits beside it


def vote_lines(vote: Any, code: str | None) -> list[tuple[bool, str, str]]:
    """Block 3 (Q1): each HS-6 among the nearest rulings, whether it is the chosen code, and its rulings' countries."""
    return [(c == code, c, ", ".join(k or "?" for k in countries)) for c, countries in vote.competing]


def agree_text(vote: Any, code: str) -> str:
    n, m = _hs6_votes(vote, code)
    return f"{n} of {m} agree with {code}"


def cn8_lines(store: Any, line: Any, code: str) -> list[tuple[str, str]]:
    """Block 4 before "Accept": the CN-8 lines under the chosen HS-6, spaced, with the last two levels of their labels."""
    return [(spaced(cn8), " › ".join(_path(path)[-2:])) for cn8, path in _cn8_options(store, line, code)]


def requirements_text(sv: Any) -> str:
    """Block 4 (D16): the requirement measures' kinds, or "none"."""
    labels = dict.fromkeys(m.measure_type_label or m.measure_type for m in sv.groups.get("requirements", ()))
    return ", ".join(labels) or "none"


# --------------------------------------------------------------------------- feature 012: the downloads (FR-013)
OVERRIDES = (ChosenHow.other_candidate.value, ChosenHow.typed.value)


def clerk_changed(line: Any, decided_how: str | None) -> bool:
    """The clerk overrode the model: an HS-6 other than the top candidate (another candidate, or a typed code), or a
    description the clerk edited. Accepting a line as it is, confirming its codes or asking the shipper changes nothing
    (the Step 2 review)."""
    return decided_how in OVERRIDES or any(v.created_by == CreatedBy.clerk for v in line.versions)


def export_csv(store: Any) -> bytes:
    """The store's CSV export, column for column, with `clerk_changed` added; the store's own export is unchanged."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[*store.CSV_COLUMNS, "clerk_changed"], extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for line, row in zip(store.lines, store.export_rows()):
        writer.writerow(row | {"clerk_changed": "true" if clerk_changed(line, row["decided_how"]) else "false"})
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def export_json(store: Any, knowledge_base_updated: str | None) -> bytes:
    """The store's JSON export with `clerk_changed` on every line."""
    payload = json.loads(store.to_json_bytes(knowledge_base_updated=knowledge_base_updated))
    for line, item in zip(store.lines, payload["lines"]):
        item["clerk_changed"] = clerk_changed(line, item["decided_how"])
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


# --------------------------------------------------------------------------- §8 captions and other values
def invoice_id(store: Any) -> str:
    """The shipment's reference, else its id: the rule `export_filename` already uses."""
    s = store.shipment
    return s.reference or s.id


_ORIGIN_MESSAGE = re.compile(r"Origin ([A-Z]{2}): the TARIC rules re-applied to (\d+) lines?")


def origin_toast(message: str) -> str:
    """The toast for `agent.apply_taric_origin`'s message, whose format feature 004's tests pin; any other message is
    returned unchanged."""
    m = _ORIGIN_MESSAGE.fullmatch(message)
    if m is None:
        return message
    return f"Origin {m.group(1)} — TARIC rules re-applied to {_plural(int(m.group(2)), 'line')}, no model call"


def snapshot_caption(kb: Any) -> str:
    taric = getattr(kb, "taric", None)
    return f"TARIC snapshot {taric.snapshot.snapshot_date}" if taric is not None else "TARIC not loaded"


def taric_statement(kb: Any) -> str:
    """Admin › Data: the snapshot date, its CN-8 mismatch count (feature 002 FR-024) and its source."""
    taric = getattr(kb, "taric", None)
    if taric is None:
        return "TARIC not loaded"
    snap = taric.snapshot
    n = snap.cn8_mismatches
    return (f"TARIC snapshot: {snap.snapshot_date} · {n:,} CN-8 mismatch{'' if n == 1 else 'es'} · "
            "Swedish Customs Tariff File Distribution")


def quality_rows(history: Any, results: Any) -> list[dict]:
    """Admin › Quality: the last two CN-8 eval runs (tests/eval/cn8_eval_history.json) and the HS-6 labelled set
    (tests/eval/results.json); [] when both files are missing."""
    rows = [{"Run": f"CN-8 eval, iteration {e['iteration']}",
             "CN-8 exact": f"{e['top1']}/{e['n']} ({round(100 * e['top1'] / e['n'])} %)", "HS-6 top-3": "—"}
            for e in (history or [])[-2:]]
    hybrid = (results or {}).get("hybrid")
    if hybrid:
        rows.append({"Run": "HS-6 labelled set, hybrid", "CN-8 exact": "—",
                     "HS-6 top-3": f"{hybrid['top3']}/{hybrid['clear_lines']}"})
    return rows


def quality_captions(history: Any) -> list[str]:
    """One caption per CN-8 eval run of the table: what changed in it, cut at 160 characters."""
    return [cut(f"Iteration {e['iteration']}: {e['change']}", 160) for e in (history or [])[-2:]]


AUDIT_COLUMNS = ["at", "line_no", "version_no", "change", "previous", "new", "actor", "note"]


def audit_csv(store: Any) -> bytes:
    """The shipment's audit trail as UTF-8 CSV with a BOM, one row per record (Admin › Quality)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(AUDIT_COLUMNS)
    for r in store.shipment.audit:
        writer.writerow([r.at.isoformat(), r.line_no, r.version_no, r.change.value, r.previous or "", r.new or "",
                         r.actor.value, r.note or ""])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def kb_statement(kb: Any) -> str:
    """What the knowledge base covers and when it was last updated (Principle IV); today's sidebar caption."""
    facts = kb.rules.caption_facts()
    year = kb.index.edition_year or ""
    return (f"HS 2022 / CN {year} · {len(kb.index):,} subheadings · ICS2 {facts['ics2_terms']} terms · "
            f"firm list {facts['firm_terms']} · {len(kb.bti):,} BTI rulings · updated {kb.updated or 'unknown'}")
