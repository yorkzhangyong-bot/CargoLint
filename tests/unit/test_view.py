"""The view module (feature 005, contracts/view.md): the status mapping, texts, codes, counts, rows and captions. Pure:
no Streamlit, no model."""
from __future__ import annotations

import re

import pytest

from tests.ui import harness as h
from ui import view

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


@pytest.fixture(scope="module")
def states(kb):
    (cn, cn_nos), (us, us_nos) = h.all_states(kb)
    return {"cn": cn, "cn_nos": cn_nos, "us": us, "us_nos": us_nos}


def status(states, name, activity=None):
    store = states["us"] if name == "ready_taric" else states["cn"]
    nos = states["us_nos"] if name == "ready_taric" else states["cn_nos"]
    return view.line_status(store, store.get_line(nos[name]), activity)


# --------------------------------------------------------------------------- §1 the mapping (SC-004)
LOCK_TAIL = " — update the description and re-check"


@pytest.mark.parametrize("name, text, kind, lock, question", [
    ("failed", "Check failed", "c_failed", "Locked: the check failed — re-check the line", None),
    ("ics2_term", "Ask: what exactly is “spare parts”?", "c", "Locked: ICS2 unacceptable term 'spare parts'" + LOCK_TAIL,
     "“spare parts” is not accepted as a goods description. Please state the exact product name, the material and the "
     "intended use."),
    ("firm_stop_word", "Ask: what exactly is “gift”?", "c", "Locked: firm stop word 'gift'" + LOCK_TAIL,
     "“gift” is not accepted as a goods description. Please state the exact product name, the material and the intended "
     "use."),
    ("vague_close", "Ask: material, product name, use?", "c", "Locked: vague description" + LOCK_TAIL,
     "The description is too general for customs. Please state the exact product name, the material and the intended use."),
    ("vague_review", "Ask: material, product name, use?", "c", "Locked: vague description" + LOCK_TAIL,
     "The description is too general for customs. Please state the exact product name, the material and the intended use."),
    ("unreadable", "Ask: unreadable line", "c", "Locked: the description could not be read" + LOCK_TAIL,
     "We could not read this line of your document. Please state the exact product name, the material and the intended "
     "use."),
    ("cn8_question", "Ask: the toy cars incorporate a motor?", "c",
     "Locked: the CN-8 depends on whether the toy cars incorporate a motor" + LOCK_TAIL,
     "Please confirm whether the toy cars incorporate a motor."),
    ("sent", "Ask: what exactly are the goods?", "c", "Locked: sent to the shipper" + LOCK_TAIL,
     "Please state the exact product name, the material and the intended use."),
    ("taric_question", "Ask: which TARIC subdivision applies?", "c", "Locked: sent to the shipper" + LOCK_TAIL,
     h.TARIC_QUESTION),
])
def test_red_rows(states, name, text, kind, lock, question):
    s = status(states, name)
    assert (s.colour, s.text, s.action, s.kind) == ("red", text, "Update", kind)
    assert s.lock_reason == lock and s.question == question
    assert not s.selectable and not s.accepted


@pytest.mark.parametrize("name, text, kind", [
    ("cn8_error", None, "a_cn8"),                      # row 8: the CN-8 step failed
    ("review", "Pick: 3 candidates", "a_hs6"),
    ("ready_to_accept", "Confirm: 8452 90", "a_hs6"),
    ("no_candidate", "Pick: no candidate", "a_hs6"),
    ("cn8_missing", "Pick: CN-8, 19 lines", "a_cn8"),  # row 10
    ("cn8_pending", "Pick: CN-8, 19 lines", "a_cn8"),  # row 11
    ("taric_missing", "Confirm: 9503 00 95", "a_cn8"),  # row 12
    ("taric_two", "Pick: 10 or 90", "b"),
    ("taric_many", "Pick: 9 options, 3 AD", "b"),
    ("taric_one_td", "Confirm: 7318 15 68 00", "b"),
])
def test_yellow_rows(states, name, text, kind):
    s = status(states, name)
    if name == "cn8_error":
        n = len(states["cn"].index.cn8_lines("6109.10"))
        text = f"Pick: CN-8, {n} lines" if n != 1 else "Pick: CN-8, 1 line"
    assert (s.colour, s.text, s.action, s.kind) == ("yellow", text, "Choose", kind)
    assert s.lock_reason is None and s.question is None and not s.selectable


@pytest.mark.parametrize("name, text, selectable", [
    ("ready", "Ready", True), ("ready_not_loaded", "Ready", True), ("ready_taric", "Ready", True),
    ("accepted", "Accepted", False), ("accepted_taric", "Accepted", False),
])
def test_green_rows(states, name, text, selectable):
    s = status(states, name)
    assert (s.colour, s.text, s.action, s.kind) == ("green", text, "Change", "a_change")
    assert s.selectable is selectable and s.accepted is (text == "Accepted") and s.lock_reason is None


def test_grey_rows(states, kb):
    assert (status(states, "pending").colour, status(states, "pending").text) == ("grey", "Not checked yet")
    running = status(states, "pending", "running")
    assert (running.colour, running.text, running.action, running.kind) == ("grey", "Running stop-word check…", None, None)
    assert status(states, "cn8_missing", "running").text == "Running CN-8 step…"
    assert status(states, "cn8_missing", "queued").text == "Queued: CN-8 step"
    assert status(states, "taric_missing", "running").text == "Running TARIC step…"
    assert status(states, "ics2_term", "recheck_queued").text == "Queued: re-check"
    store = h._store()
    n = h._clear(store, kb, "Ceramic coffee mugs")           # checked but not classified: the HS-6 step is next
    assert view.line_status(store, store.get_line(n), "running").text == "Running HS-6 step…"


def test_a_running_job_on_a_line_with_nothing_left_shows_its_own_status(states):
    assert status(states, "ready", "running").text == "Ready"
    assert status(states, "ics2_term", "running").colour == "red"


def test_row_8_needs_the_failed_choice_under_the_decided_hs6(kb):
    store, nos = h.store_with("cn8_error", kb=kb)
    store.set_threshold(99)                                   # 94 % < 99: the HS-6 is no longer decided
    s = view.line_status(store, store.get_line(nos["cn8_error"]))
    assert (s.colour, s.text, s.kind) == ("yellow", "Pick: 1 candidate", "a_hs6")


def test_value_domains_and_no_generic_texts(states):
    names = list(states["cn_nos"]) + ["ready_taric"]
    for name in names:
        for activity in (None, "running", "queued", "recheck_queued"):
            s = status(states, name, activity)
            assert s.kind in ("a_hs6", "a_cn8", "a_change", "b", "c", "c_failed", None)
            assert s.action in ("Choose", "Update", "Change", None)
            assert s.colour in ("green", "yellow", "red", "grey")
            assert s.text not in ("Review", "Needs action") and "to confirm" not in s.text   # SC-003
            assert len(s.text) <= view.STATUS_MAX


def test_no_generic_texts_on_the_sample():
    store = h.sample_store()
    for line in store.lines:
        s = view.line_status(store, line)
        assert s.text not in ("Review", "Needs action") and "to confirm" not in s.text


def test_long_status_texts_are_cut_but_lock_reasons_are_not(kb):
    store = h._store()
    n = h._clear(store, kb, "Plastic toy cars", "塑料玩具车")
    h._classify(store, n, [("9503.00", 93)])
    attribute = "whether the goods are made of steel, aluminium, plastics or several of these materials"
    h._cn8(store, n, "9503.00", None, attribute=attribute, question=f"Ask the shipper for: {attribute}")
    s = view.line_status(store, store.get_line(n))
    assert len(s.text) == view.STATUS_MAX and s.text.endswith("…")
    assert s.lock_reason == f"Locked: the CN-8 depends on {attribute}" + LOCK_TAIL


# --------------------------------------------------------------------------- next_step
def test_next_step(states, kb):
    cn, nos = states["cn"], states["cn_nos"]
    assert view.next_step(cn, cn.get_line(nos["pending"])) == "stop-word check"
    assert view.next_step(cn, cn.get_line(nos["cn8_missing"])) == "CN-8 step"
    assert view.next_step(cn, cn.get_line(nos["taric_missing"])) == "TARIC step"
    assert view.next_step(cn, cn.get_line(nos["ready"])) is None
    store = h._store()
    n = h._clear(store, kb, "Ceramic coffee mugs")
    assert view.next_step(store, store.get_line(n)) == "HS-6 step"
    other, onos = h.store_with("taric_two", kb=kb)
    other.shipment.taric_origin = "US"                        # an outcome for another origin: the TARIC step is next
    assert view.next_step(other, other.get_line(onos["taric_two"])) == "TARIC step"


# --------------------------------------------------------------------------- §3 code display
@pytest.mark.parametrize("name, text, note", [
    ("pending", "____ __ __ __", None),
    ("cn8_missing", "9503 00 __ __", None),
    ("cn8_pending", "9503 00 __ __", None),                   # a CN-8 suggestion fills no digit
    ("taric_missing", "9503 00 95 __", None),
    ("taric_two", "7318 15 58 __", None),                     # a TARIC-10 to pick fills no digit
    ("accepted_taric", "7318 15 58 10", None),
    ("ready", "9617 00 00", "TARIC not available"),
    ("ready_not_loaded", "9617 00 00", "TARIC not loaded"),
])
def test_code_display(states, name, text, note):
    cn, nos = states["cn"], states["cn_nos"]
    d = view.code_display(cn, cn.get_line(nos[name]))
    assert (d.text, d.note) == (text, note)


# --------------------------------------------------------------------------- §8 escaping and splitting
def test_md_escape():
    assert view.md_escape("[click](https://x.test)") == r"\[click\]\(https\://x\.test\)"
    assert view.md_escape("*bold* _it_ `code`") == r"\*bold\* \_it\_ \`code\`"
    assert view.md_escape("不锈钢保温杯") == "不锈钢保温杯"


@pytest.mark.parametrize("text, parts", [
    ("不锈钢保温杯 / Stainless steel vacuum flask", ("不锈钢保温杯", "Stainless steel vacuum flask")),
    ("Brake pads for bicycles, steel", ("", "Brake pads for bicycles, steel")),
    ("刹车片", ("刹车片", "")),
])
def test_split_description(text, parts):
    assert view.split_description(text) == parts


# --------------------------------------------------------------------------- §4 summary, bar and captions (US1, T007)
def statuses_of(store):
    return {line.line_no: view.line_status(store, line) for line in store.lines}


def test_summary_counts(states):
    cn = states["cn"]
    s = view.summary(cn, statuses_of(cn))
    st = statuses_of(cn).values()
    assert s.lines == len(cn.lines)
    assert s.ready == sum(1 for x in st if x.colour == "green")
    assert s.pick == sum(1 for x in st if x.colour == "yellow")
    assert s.ask == sum(1 for x in st if x.colour == "red" and x.text != "Check failed")
    assert s.failed == sum(1 for x in st if x.text == "Check failed") == 1
    assert s.running == sum(1 for x in st if x.colour == "grey") == 1
    assert s.to_accept == sum(1 for x in st if x.colour == "green" and not x.accepted)


def test_summary_text():
    S = view.Summary
    assert view.summary_text(S(lines=12, seconds=19.2, ready=6, pick=2, ask=4)) == \
        "12 lines checked in 19 s · 6 ready · 2 need a pick · 4 need the shipper"
    assert view.summary_text(S(lines=12, seconds=19, ready=6, pick=2, ask=2, failed=1, running=2)) == \
        "12 lines checked in 19 s · 6 ready · 2 need a pick · 2 need the shipper · 1 check failed · 2 updating"
    assert view.summary_text(S(lines=1, seconds=3, ready=0, pick=1, ask=1)) == \
        "1 line checked in 3 s · 0 ready · 1 needs a pick · 1 needs the shipper"


def test_seconds_count_only_check_runs():
    from agent.schemas import CheckRun, CheckStep

    store = h._store()
    store.shipment.check_runs += [
        CheckRun(id="a", elapsed_s=12.4, steps=[CheckStep(tool="check_description"), CheckStep(tool="classify_hs6")]),
        CheckRun(id="b", elapsed_s=3.1, steps=[CheckStep(tool="check_description", run_by="app")]),
        CheckRun(id="c", elapsed_s=8.0, steps=[CheckStep(tool="lookup_precedent")]),      # a chat question: not a check
    ]
    assert view.summary(store, {}).seconds == pytest.approx(15.5)


@pytest.mark.parametrize("counts", [(6, 2, 4, 0, 0), (1, 6, 5, 0, 0), (0, 0, 12, 0, 0), (10, 1, 0, 1, 0), (3, 3, 3, 1, 2)])
def test_split_bar(counts):
    ready, pick, ask, failed, running = counts
    s = view.Summary(lines=sum(counts), seconds=0, ready=ready, pick=pick, ask=ask, failed=failed, running=running)
    bar = view.split_bar(s)
    parts = re.findall(r":(green|yellow|red|gray)\[(█+)\]", bar)
    assert sum(len(b) for _, b in parts) == 60
    expected = [c for c, n in (("green", ready), ("yellow", pick), ("red", ask + failed), ("gray", running)) if n]
    assert [c for c, _ in parts] == expected                     # in order, empty parts left out, none below one block


def test_invoice_id(states):
    store = h._store()
    assert view.invoice_id(store) == "INV-TEST"
    store.shipment.reference = ""
    assert view.invoice_id(store) == store.shipment.id


def taric_kb(mismatches=105, loaded=True):
    from datetime import date
    from types import SimpleNamespace

    snapshot = SimpleNamespace(snapshot_date=date(2026, 10, 1), cn8_mismatches=mismatches)
    return SimpleNamespace(taric=SimpleNamespace(snapshot=snapshot) if loaded else None)


@pytest.mark.parametrize("count, text", [
    (105, "TARIC snapshot: 2026-10-01 · 105 CN-8 mismatches · Swedish Customs Tariff File Distribution"),
    (1, "TARIC snapshot: 2026-10-01 · 1 CN-8 mismatch · Swedish Customs Tariff File Distribution"),
    (0, "TARIC snapshot: 2026-10-01 · 0 CN-8 mismatches · Swedish Customs Tariff File Distribution"),
])
def test_taric_statement_keeps_the_mismatch_count(count, text):         # replaces tests/unit/test_sidebar_caption.py
    assert view.taric_statement(taric_kb(count)) == text


def test_captions_without_a_snapshot():
    assert view.taric_statement(taric_kb(loaded=False)) == "TARIC not loaded"
    assert view.snapshot_caption(taric_kb(loaded=False)) == "TARIC not loaded"
    assert view.snapshot_caption(taric_kb()) == "TARIC snapshot 2026-10-01"


def test_kb_statement(kb):
    text = view.kb_statement(kb)
    assert text.startswith("HS 2022 / CN ") and "BTI rulings" in text and text.endswith("updated 2026-10-15")


def test_button_labels():
    assert view.accept_all_label(6) == "Accept all 6 ready"
    assert view.accept_selected_label(2) == "Accept 2 selected"
    assert [view.email_label(n) for n in (4, 1, 0)] == ["Draft shipper email (4 lines)", "Draft shipper email (1 line)",
                                                        "Draft shipper email (0 lines)"]


# --------------------------------------------------------------------------- §5 kind (a) rows (US2, T017)
def line_of(states, name):
    store = states["us"] if name == "ready_taric" else states["cn"]
    nos = states["us_nos"] if name == "ready_taric" else states["cn_nos"]
    return store, store.get_line(nos[name])


def one_line(kb, text, cands, **kw):
    store = h._store()
    n = h._clear(store, kb, text)
    h._classify(store, n, cands, **kw)
    return store, n


def test_hs6_rows(states, kb):
    store, line = line_of(states, "ics2_term")
    rows = view.hs6_rows(store, line)
    assert [r.value for r in rows] == ["8714.91", "8487.90", "8452.90"]                   # stored order
    assert [r.code for r in rows] == ["8714 91", "8487 90 00", "8452 90 00"]              # a single CN-8 line shows that line
    assert [r.confidence for r in rows] == [41, 39, 12]
    assert [r.history_only for r in rows] == [False, False, True]
    assert rows[0].description == ("Parts and accessories of vehicles of headings 8711 to 8713 › Frames and forks, and "
                                   "parts thereof, of bicycles")                     # the heading, then the subheading
    assert rows[0].description == " › ".join(store.index.label_path("8714.91"))
    assert rows[0].rationale == "matches the subheading 8714.91"
    assert rows[0].precedent.reference == "DE-871491-01" and rows[1].precedent is None
    store2, n = one_line(kb, "Stainless steel vacuum flask, 500 ml", [("9617.00", 80)], rationale="x" * 200)
    row = view.hs6_rows(store2, store2.get_line(n))[0]
    assert row.code == "9617 00 00" and len(row.rationale) > 150                         # the full text, for the help
    assert len(view.cut(row.rationale, 150)) == 150


def test_cn8_rows_show_the_whole_label_path(states):
    store, line = line_of(states, "cn8_pending")
    rows = view.cn8_rows(store, line)
    assert len(rows) == 19 and [r.value for r in rows] == sorted(r.value for r in rows)
    by = {r.value: r for r in rows}
    assert by["95030075"].code == "9503 00 75"
    assert by["95030075"].description == "Other toys and models, incorporating a motor › Of plastics"
    assert by["95030095"].description == "Other › Other › Of plastics"
    assert by["95030010"].description == "Tricycles, scooters, pedal cars and similar wheeled toys; dolls' carriages"
    assert by["95030095"].confidence == 70                                               # the chosen model estimate
    assert all(r.confidence is None and r.precedent is None for v, r in by.items() if v != "95030095")


def test_cn8_rows_confidence_and_precedent_only_on_a_chosen_estimate(states, kb):
    from agent.schemas import Cn8Choice, Precedent

    store, n = one_line(kb, "Plastic toy figures", [("9503.00", 92)])
    ruling = Precedent(reference="DE-TOY-0001", member_state="DE", code="9503009590")
    store.set_cn8_result(n, Cn8Choice(hs6="9503.00", options=store.index.cn8_lines("9503.00"), cn8="95030095",
                                      confidence=70, precedent=ruling))
    rows = {r.value: r for r in view.cn8_rows(store, store.get_line(n))}
    assert rows["95030095"].precedent.reference == "DE-TOY-0001"
    assert [v for v, r in rows.items() if r.precedent is not None or r.confidence is not None] == ["95030095"]
    store.confirm_cn8(n, "95030075")                                                     # the clerk's choice: no estimate
    assert all(r.confidence is None and r.precedent is None for r in view.cn8_rows(store, store.get_line(n)))
    s2, line2 = line_of(states, "ready")                                                 # a single CN-8 line: no estimate
    assert [(r.code, r.confidence) for r in view.cn8_rows(s2, line2)] == [("9617 00 00", None)]


@pytest.mark.parametrize("name, kind, form, expected", [
    ("review", "a_hs6", "hs6", ("9405.21", "")),
    ("ready_to_accept", "a_hs6", "hs6", ("8452.90", "")),
    ("no_candidate", "a_hs6", "hs6", (None, "")),                                       # "Other HS-6 code…" is never pre-picked
    ("cn8_pending", "a_cn8", "cn8", ("95030095", "")),
    ("taric_missing", "a_cn8", "cn8", ("95030095", "")),
    ("cn8_missing", "a_cn8", "cn8", ("95030010", "")),
    ("cn8_error", "a_cn8", "cn8", ("61091000", "")),
    ("ready", "a_change", "hs6", ("9617.00", "")),
    ("ready_taric", "a_change", "cn8", ("73181568", "")),
    ("accepted_taric", "a_change", "hs6", ("7318.15", "")),
    ("accepted_taric", "a_change", "cn8", ("73181558", "")),
    ("accepted_taric", "a_change", "taric10", ("7318155810", "")),
    ("taric_two", "b", "taric10", ("7318155810", "")),
])
def test_preselect(states, name, kind, form, expected):
    store, line = line_of(states, name)
    assert view.preselect(store, line, kind, form) == expected


def test_preselect_a_typed_hs6_holds_it_in_other(kb):
    from agent.schemas import Decision, DecisionRoute

    store, n = one_line(kb, "LED desk lamp, USB powered", [("9405.21", 58), ("8543.70", 20)])
    store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code="9617.00"))
    assert view.preselect(store, store.get_line(n), "a_change", "hs6") == (view.OTHER, "9617.00")
    store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code="8543.70"))   # a typed candidate is that one
    assert view.preselect(store, store.get_line(n), "a_change", "hs6") == ("8543.70", "")


def test_preselect_b_takes_the_suggestion(kb):
    from agent.schemas import TaricSuggestion

    store, nos = h.store_with("taric_two", kb=kb)
    n = nos["taric_two"]
    t = store.get_line(n).current.taric
    store.set_taric_result(n, t.model_copy(update={"suggestion": TaricSuggestion(code="7318155890", confidence=70)}))
    assert view.preselect(store, store.get_line(n), "b", "taric10") == ("7318155890", "")


@pytest.mark.parametrize("name, forms", [
    ("ready", ["HS-6"]),                                       # 9617 00: one CN-8 line; TARIC not available
    ("accepted", ["HS-6"]),
    ("ready_taric", ["HS-6", "CN-8"]),                         # 7318 15: 12 CN-8 lines; one subdivision
    ("accepted_taric", ["HS-6", "CN-8", "TARIC-10"]),          # 7318 15 58: two subdivisions
])
def test_change_forms(states, name, forms):
    store, line = line_of(states, name)
    assert view.change_forms(store, line) == forms


@pytest.mark.parametrize("name, kind, first, second", [
    ("review", "a_hs6", "matches the subheading 9405.21",
     "Top candidate leads (58 %) but is under the 85 % auto-accept threshold, so you decide. TARIC runs after your pick."),
    ("ready_to_accept", "a_hs6", "matches the subheading 8452.90",
     "Top candidate leads (91 %), but this line was flagged before its update, so it needs your confirmation. TARIC runs "
     "after your pick."),
    ("no_candidate", "a_hs6", "", "No valid candidate was found. Type the HS-6 code, or ask the shipper what the goods are."),
    ("cn8_pending", "a_cn8", "The HS-6 is 9503 00; its subheading has 19 CN-8 lines.",
     "CN-8 to confirm: no ruling vote, and its model estimate (70 %) is under the 85 % threshold. TARIC runs after your "
     "pick."),
    ("cn8_error", "a_cn8", "The HS-6 is 6109 10; its subheading has 1 CN-8 line.",
     "The CN-8 step failed: invalid output after one retry. Pick the CN-8."),
    ("cn8_missing", "a_cn8", "The HS-6 is 9503 00; its subheading has 19 CN-8 lines.",
     "No CN-8 was chosen for this HS-6 yet; the CN-8 step did not run, for example after a threshold change. Pick the "
     "CN-8."),
    ("taric_missing", "a_cn8", "The HS-6 is 9503 00; its subheading has 19 CN-8 lines.",
     "The TARIC step did not finish for this CN-8. Confirm it to look up TARIC again."),
    ("ready", "a_change", "Decided: HS-6 9617 00, auto-accepted at 92 % · CN-8 9617 00 00, single CN-8 line · TARIC not "
     "available", "Pick another code to override it. The later steps run again after your pick."),
    ("accepted", "a_change", "Decided: HS-6 9617 00, auto-accepted at 92 %, accepted by you · CN-8 9617 00 00, confirmed "
     "by you · TARIC not available", "Pick another code to override it. The later steps run again after your pick."),
    ("ready_taric", "a_change", "Decided: HS-6 7318 15, auto-accepted at 92 % · CN-8 7318 15 68, written by rule at a model "
     "estimate of 95 % · "
     "TARIC-10 7318 15 68 00, auto-completed", "Pick another code to override it. The later steps run again after your pick."),
    ("accepted_taric", "a_change", "Decided: HS-6 7318 15, auto-accepted at 92 %, accepted by you · CN-8 7318 15 58, "
     "confirmed by you · TARIC-10 7318 15 58 10, confirmed by you",
     "Pick another code to override it. The later steps run again after your pick."),
    ("ready_not_loaded", "a_change", "Decided: HS-6 9617 00, auto-accepted at 92 % · CN-8 9617 00 00, single CN-8 line · "
     "TARIC not loaded", "Pick another code to override it. The later steps run again after your pick."),
])
def test_explain_a(states, name, kind, first, second):
    store, line = line_of(states, name)
    assert view.explain_a(store, line, kind) == (first, second)


def test_explain_a_a_ruling_against_the_cn8(kb):
    from agent.schemas import Cn8Choice, Precedent

    store, n = one_line(kb, "Plastic toy figures", [("9503.00", 92)])
    ruling = Precedent(reference="DE-TOY-0001", member_state="DE", code="9503007590")
    store.set_cn8_result(n, Cn8Choice(hs6="9503.00", options=store.index.cn8_lines("9503.00"), cn8="95030095",
                                      confidence=95, precedent=ruling))
    assert view.explain_a(store, store.get_line(n), "a_cn8")[1] == \
        "CN-8 to confirm: the cited ruling DE-TOY-0001 classifies under 9503 00 75, not this CN-8."


def _voted_toys(kb, cn8, gate, written_by=None, majority="95030075"):
    """A toy line whose five nearest rulings voted: three at 9503 00 75 (XI, IE, FR), two at 9503 00 95 (DE, FR)."""
    from agent.schemas import Cn8Choice, VoteCode

    store, n = one_line(kb, "Plastic toy figures", [("9503.00", 92)])
    store.set_cn8_result(n, Cn8Choice(hs6="9503.00", options=store.index.cn8_lines("9503.00"), cn8=cn8, confidence=95,
                                      written_by=written_by, gate_reason=gate, majority_cn8=majority, majority_share=0.6,
                                      competing=[VoteCode(cn8="95030075", countries=["XI", "IE", "FR"]),
                                                 VoteCode(cn8="95030095", countries=["DE", "FR"])]))
    return store, store.get_line(n)


@pytest.mark.parametrize("gate, majority, text", [
    ("vote_disagrees", "95030075", "Rulings disagree: model 9503 00 95, nearest rulings 9503 00 75 (XI, IE, FR), 9503 00 95 "
     "(DE, FR). TARIC runs after your pick."),
    ("vote_tie", None, "Rulings split: model 9503 00 95, nearest rulings 9503 00 75 (XI, IE, FR), 9503 00 95 (DE, FR). "
     "TARIC runs after your pick."),
    ("vote_share_low", "95030095", "Rulings too spread: model 9503 00 95 has 2 of 5 nearest rulings; 9503 00 75 (XI, IE, "
     "FR), 9503 00 95 (DE, FR). TARIC runs after your pick.")])
def test_feature_006_the_reason_names_the_nearest_rulings_and_their_countries(kb, gate, majority, text):
    from agent.schemas import Cn8Gate

    store, line = _voted_toys(kb, "95030095", Cn8Gate(gate), majority=majority)
    assert view.explain_a(store, line, "a_cn8")[1] == text


def test_feature_006_a_cn8_the_vote_wrote_says_how_many_rulings_agree(kb):
    from agent.schemas import Cn8Gate, WrittenBy

    store, line = _voted_toys(kb, "95030075", Cn8Gate.vote_agrees, WrittenBy.rule)
    assert view.explain_a(store, line, "a_change")[0].startswith(
        "Decided: HS-6 9503 00, auto-accepted at 92 % · CN-8 9503 00 75, written by rule, 3 of 5 nearest rulings agree")


@pytest.mark.parametrize("code, how", [("9405.21", "confirmed by you"), ("8543.70", "chosen by you"),
                                       ("9617.00", "typed by you")])
def test_explain_a_who_decided_the_hs6(kb, code, how):
    from agent.schemas import Decision, DecisionRoute

    store, n = one_line(kb, "LED desk lamp, USB powered", [("9405.21", 58), ("8543.70", 20)])
    store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code=code))
    assert view.explain_a(store, store.get_line(n), "a_change")[0].startswith(f"Decided: HS-6 {view.spaced(code)}, {how}")


# --------------------------------------------------------------------------- §6 kind (b) rows (US2, T017)
def taric_view_of(store, kb, n):
    from agent.agent import line_taric_view

    return line_taric_view(store, kb, n)


def cells(rows):
    return [(r.code, r.description, r.duty, r.anti_dumping) for r in rows]


def test_subdivision_rows_for_cn_and_us(kb):
    store, nos = h.store_with("taric_two", "taric_one_td", kb=kb)
    rows = view.subdivision_rows(taric_view_of(store, kb, nos["taric_two"]))
    assert cells(rows) == [("7318 15 58 10", "Self-locking bolts and nuts", "3.7 %", "22–85 % AD"),
                           ("7318 15 58 90", "Other", "3.7 %", "85 % AD")]
    assert [r.value for r in rows] == ["7318155810", "7318155890"]
    assert all(r.has_trade_defence and not r.suggested for r in rows)
    one = view.subdivision_rows(taric_view_of(store, kb, nos["taric_one_td"]))
    assert [(r.anti_dumping, r.has_trade_defence) for r in one] == [("control", True)]
    us, us_nos = h.store_with("taric_two", origin="US", kb=kb)
    us_rows = view.subdivision_rows(taric_view_of(us, kb, us_nos["taric_two"]))
    assert cells(us_rows)[0] == ("7318 15 58 10", "Self-locking bolts and nuts", "3.7 % · pref. 0 %", "none")
    assert not any(r.has_trade_defence for r in us_rows)


def test_subdivision_rows_specific_duties_and_the_whole_cn8():
    from datetime import date
    from types import SimpleNamespace

    from agent.taric_rules import SubdivisionView, TaricView

    def m(kind, duty):
        return SimpleNamespace(measure_type=kind, duty=duty)

    subs = (SubdivisionView("8714911021", "Frames of steel", ("552",),
                            {"duties": (m("103", "4.7 %"),), "trade_defence": (m("552", "172.2 EUR / 1000 kg I"),),
                             "requirements": ()}),
            SubdivisionView("8714911000", "", (), {"duties": (), "trade_defence": (), "requirements": ()}),
            SubdivisionView("8714911035", "", ("552",),
                            {"duties": (), "trade_defence": (m("552", "48.50 %"), m("552", "48.5 %")), "requirements": ()}))
    tv = TaricView("CN", date(2026, 10, 1), None, SimpleNamespace(code="8714911000", confidence=60), None, None, subs)
    rows = view.subdivision_rows(tv)
    assert rows[0].anti_dumping == "AD: 172.2 EUR / 1000 kg I"
    assert (rows[1].description, rows[1].duty, rows[1].anti_dumping) == ("the whole CN-8", "—", "none")
    assert rows[2].description == "no description" and rows[2].anti_dumping == "48.5 % AD"   # one rate, zeros dropped
    assert [r.suggested for r in rows] == [False, True, False]


def test_explain_b(kb):
    store, nos = h.store_with("taric_two", "accepted_taric", "taric_many", kb=kb)
    line = store.get_line(nos["taric_two"])
    assert view.explain_b(store, line, taric_view_of(store, kb, line.line_no)) == (
        "CN-8 is 7318 15 58 (Slotted or cross-recessed heads › Other). 2 of 2 subdivisions carry anti-dumping or "
        "countervailing measures for CN.",
        "Your pick confirms both the CN-8 and the TARIC-10. CN-8 written by rule at 95 %.")
    accepted = store.get_line(nos["accepted_taric"])
    assert view.explain_b(store, accepted, taric_view_of(store, kb, accepted.line_no))[1] == \
        "Your pick confirms both the CN-8 and the TARIC-10. CN-8 confirmed by you."
    frames = store.get_line(nos["taric_many"])
    assert view.explain_b(store, frames, taric_view_of(store, kb, frames.line_no))[0].startswith("CN-8 is 8714 91 10 (Frames).")
    kb2 = h.make_kb("sample")                                                            # 8518 30: one CN-8 line
    s2, n2 = one_line(kb2, "Wireless Bluetooth earphones", [("8518.30", 92)])
    h._cn8(s2, n2, "8518.30", "85183000", conf=100)
    h._taric(s2, kb2, n2)
    line2 = s2.get_line(n2)
    assert view.explain_b(s2, line2, taric_view_of(s2, kb2, n2))[1] == \
        "Your pick confirms both the CN-8 and the TARIC-10. Single CN-8 line."


def test_taric_question(kb):
    store, nos = h.store_with("taric_two", kb=kb)
    assert view.taric_question(taric_view_of(store, kb, nos["taric_two"])) == h.TARIC_QUESTION


# --------------------------------------------------------------------------- §2.1, §2.3 kind (c): reasons and candidates (US3, T024)
RED = ("failed", "ics2_term", "firm_stop_word", "vague_close", "vague_apart", "vague_review", "unreadable", "cn8_question",
       "sent", "taric_question")


@pytest.mark.parametrize("name, reason", [
    ("ics2_term", "Reason: ICS2 unacceptable term 'spare parts'"),
    ("firm_stop_word", "Reason: firm stop word 'gift'"),
    ("vague_close", "Reason: candidates too close"),
    ("vague_apart", "Reason: vague description — generic term, no material, product name or use"),
    ("unreadable", "Reason: the description could not be read"),
    ("cn8_question", "Reason: the CN-8 depends on whether the toy cars incorporate a motor, which the description does "
                     "not state"),
    ("sent", "Reason: you sent this line to the shipper"),
    ("taric_question", "Reason: you sent this line to the shipper"),
    ("failed", "Reason: the check failed — TimeoutError: the model did not answer"),
])
def test_reason_lines(states, name, reason):
    store, line = line_of(states, name)
    assert view.reason_line(store, line) == reason


@pytest.mark.parametrize("name, text", [
    ("vague_close", "Candidates: 3924 90 (41 %) · 3924 10 (39 %) · 9403 60 (12 %) — too close to call"),
    ("vague_apart", "Candidates: 3924 90 (40 %) · 3924 10 (10 %) · 9403 60 (5 %)"),
    ("ics2_term", None),                                                              # a term flagged it: its reason says so
    ("firm_stop_word", None),
    ("review", None),                                                                 # not flagged
])
def test_candidates_line(states, name, text):
    store, line = line_of(states, name)
    assert view.candidates_line(line) == text


@pytest.mark.parametrize("second, close", [(31, True), (30, False)])                 # 41 − 31 = 10 is close, 11 is not
def test_too_close_to_call_at_the_boundary(kb, second, close):
    store, n = one_line(kb, "Mixed household articles", [("3924.90", 41), ("3924.10", second)])
    line = store.get_line(n)
    assert view.candidates_line(line).endswith(" — too close to call") is close
    assert (view.reason_line(store, line) == "Reason: candidates too close") is close


def test_a_term_flag_gives_its_reason_and_no_candidates_line(kb):
    from agent.schemas import DescriptionCheck, Flag, FlagKind, LineStatus, RuleSource

    store = h._store()
    n = h._add(store, "Parts")
    store.update_check(n, DescriptionCheck(line_no=n, status=LineStatus.checked, flag=Flag(
        kind=FlagKind.vague, rule_source=RuleSource.ics2_unacceptable, matched_term="parts", reason="ICS2 term",
        ask_for=["material", "product_name", "use"])))
    h._classify(store, n, [("8714.91", 41), ("8487.90", 39)])
    line = store.get_line(n)
    assert view.reason_line(store, line) == "Reason: ICS2 unacceptable term 'parts'"
    assert view.candidates_line(line) is None                                         # close candidates, yet no line


@pytest.mark.parametrize("name", RED)
def test_red_rows_are_never_selectable_and_have_a_question_unless_failed(states, kb, name):
    store, line = line_of(states, name)
    s = view.line_status(store, line)
    assert s.colour == "red" and not s.selectable and s.lock_reason.startswith("Locked: ")
    assert (view.question(store, line, "en", kb) is None) is (name == "failed")
    assert s.question == view.question(store, line, "en")


# --------------------------------------------------------------------------- §8 the origin toast (US6, T040)
@pytest.mark.parametrize("message, toast", [
    ("Origin US: the TARIC rules re-applied to 3 lines", "Origin US — TARIC rules re-applied to 3 lines, no model call"),
    ("Origin US: the TARIC rules re-applied to 1 line", "Origin US — TARIC rules re-applied to 1 line, no model call"),
    ("Origin CN: the TARIC rules re-applied to 0 lines", "Origin CN — TARIC rules re-applied to 0 lines, no model call"),
    ("Something else happened", "Something else happened"),
])
def test_origin_toast(message, toast):
    assert view.origin_toast(message) == toast


# --------------------------------------------------------------------------- §8 Admin › Quality and the audit trail (US7, T043)
HISTORY = [
    {"iteration": 2, "change": "older run", "top1": 80, "n": 120},
    {"iteration": 3, "change": "evidence: every quoted word occurs in the line " + "x" * 200, "top1": 91, "n": 120},
    {"iteration": 4, "change": "T060 validation run", "top1": 93, "n": 120},
]
RESULTS = {"hybrid": {"mode": "hybrid", "clear_lines": 12, "top1": 10, "top3": 12}}


def test_quality_rows():
    assert view.quality_rows(HISTORY, RESULTS) == [
        {"Run": "CN-8 eval, iteration 3", "CN-8 exact": "91/120 (76 %)", "HS-6 top-3": "—"},
        {"Run": "CN-8 eval, iteration 4", "CN-8 exact": "93/120 (78 %)", "HS-6 top-3": "—"},
        {"Run": "HS-6 labelled set, hybrid", "CN-8 exact": "—", "HS-6 top-3": "12/12"},
    ]
    assert view.quality_rows(None, None) == []
    assert [r["Run"] for r in view.quality_rows(None, RESULTS)] == ["HS-6 labelled set, hybrid"]


def test_quality_captions():
    captions = view.quality_captions(HISTORY)
    assert captions[1] == "Iteration 4: T060 validation run"
    assert captions[0].startswith("Iteration 3: evidence: every quoted word") and len(captions[0]) == 160
    assert view.quality_captions(None) == []


def test_audit_csv(states):
    import csv
    import io

    store = states["cn"]
    raw = view.audit_csv(store)
    assert raw.startswith("\ufeff".encode("utf-8"))
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0] == ["at", "line_no", "version_no", "change", "previous", "new", "actor", "note"]
    assert len(rows) == 1 + len(store.shipment.audit)
    first = store.shipment.audit[0]
    assert rows[1][1:4] == [str(first.line_no), str(first.version_no), first.change.value]
