"""The main page with AppTest (feature 005, contracts/ui.md §2 to §7): offline, a seeded store, jobs recorded instead
of run, model calls counted."""
from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest

from agent.schemas import CreatedBy, Decision, DecisionRoute, TaricSuggestion, Usage
from tests.ui import harness as h
from ui import view
from ui.jobs import Job

pytestmark = pytest.mark.integration


def plain(text: str) -> str:
    """Markdown escapes removed, to compare rendered text with contract texts."""
    return re.sub(r"\\(.)", r"\1", text or "")


def texts(at) -> list[str]:
    out = [m.value for m in at.markdown] + [c.value for c in at.caption]
    out += [e.value for kind in ("info", "warning", "error", "success") for e in getattr(at, kind)]
    return [plain(t) for t in out]


@pytest.fixture(scope="module")
def kb():
    return h.make_kb()


@pytest.fixture
def recorder(monkeypatch):
    return h.JobRecorder().install(monkeypatch)


def empty_store():
    from agent.store import LineStore

    return LineStore(backend={}, index=h.small_index())


# --------------------------------------------------------------------------- US1: the empty state (FR-001, FR-003)
def test_empty_state(kb, recorder):
    at = h.app(empty_store(), kb).run()
    assert not at.exception
    assert any("CargoLint" in t for t in texts(at))
    assert at.text_input(key="origin_field").value == "CN"
    up = at.file_uploader[0]
    assert up.label == "Drop a packing list or invoice here" and not up.disabled
    assert "XLSX · CSV · PDF · JPG · PNG — up to 20 MB, one file per shipment" in texts(at)
    assert at.button(key="sample_empty").label == "Try the sample invoice"
    one = at.text_input(key="check_one_line")
    assert one.placeholder == "Type a goods description and press Enter, e.g. bicycle frames, aluminium"
    assert one.max_chars == 300
    assert "No lines yet — drop a file or type one description" in texts(at)
    assert [n.proto.label for n in at.get("page_link")] == ["Admin ⚙"]


def test_nothing_from_fr002_on_the_main_page(kb, recorder):
    (store, _), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    assert not at.exception
    assert len(at.sidebar.children) == 0 and not at.chat_input and not at.slider
    assert not any(re.search(r"\b(Tokens|Cost)\b", t) for t in texts(at))
    assert not at.get("progress")                                    # no confidence bars in the table
    rows = [plain(b.label) for b in at.button if b.key and re.fullmatch(r"(open|act)_\d+", b.key)]
    assert not any("%" in r for r in rows)


# --------------------------------------------------------------------------- US1: the table (FR-007 to FR-011)
def test_rows_codes_statuses_and_actions(kb, recorder):
    (store, nos), _ = h.all_states(kb)
    extra = h._add(store, "Ceramic coffee mugs")                    # line 26: a second page of 25 rows
    h._check(store, kb, extra)
    h._classify(store, extra, [])                                    # the fake judge: vague, so a red row with a button
    at = h.app(store, kb).run()
    assert not at.exception
    assert at.segmented_control(key="table_page").options == ["1", "2"]
    keys = [b.key for b in at.button if b.key and re.fullmatch(r"open_\d+", b.key)]
    order = [int(k.split("_")[1]) for k in keys]
    assert order == sorted(order)                                    # file order
    page = texts(at)
    for name, n in nos.items():
        line = store.get_line(n)
        s = view.line_status(store, line)
        code = view.code_display(store, line)
        assert f"`{code.text}`" in page, name
        assert f"{s.dot} {s.text}" in page, name
        if s.action:
            assert at.button(key=f"act_{n}").label == s.action, name
        else:
            assert not [b for b in at.button if b.key == f"act_{n}"], name
    assert not [b for b in at.button if b.key == f"open_{nos['pending']}"]                  # grey rows do not open
    assert not [b for b in at.button if b.key == f"open_{extra}"]                           # on page 2
    store2, _ = h.store_with("ready", kb=kb)
    weird = h._add(store2, "[click](https://x.test)")
    h._check(store2, kb, weird)
    h._classify(store2, weird, [])                                   # the fake judge: vague, so a red row
    at2 = h.app(store2, kb).run()
    assert at2.button(key=f"open_{weird}").label == r"\[click\]\(https\://x\.test\)"    # escaped, never a link


def test_opening_and_closing_a_row(kb, recorder):
    store, nos = h.store_with("review", "ready", kb=kb)
    at = h.app(store, kb).run()
    at.button(key=f"open_{nos['review']}").click().run()
    assert at.session_state["selected_line_no"] == nos["review"]
    assert at.button(key=f"close_{nos['review']}").label == "▲ close"
    at.button(key=f"act_{nos['review']}").click().run()              # choosing it again closes it
    assert at.session_state["selected_line_no"] is None
    assert not [b for b in at.button if b.key == f"close_{nos['review']}"]


# --------------------------------------------------------------------------- US1: live check and summary (FR-004, FR-005)
def running_check(**kw) -> Job:
    job = Job(kind="check", message="Check", is_check=True, **kw)
    job.done = False
    return job


def test_a_running_check_shows_grey_rows_and_the_checking_summary(kb, recorder):
    store = h._store()
    for text in ("Ceramic coffee mugs", "Wooden chopsticks", "Plastic toy figures"):
        h._add(store, text)
    at = h.app(store, kb)
    at.session_state["job"] = running_check()
    at.run()
    assert not at.exception
    page = texts(at)
    assert sum(1 for t in page if t == ":gray[◌] Running stop-word check…") == 3
    assert any(re.fullmatch(r"\*\*Checking 3 lines… · \d+ s\*\*", t) for t in page)


def test_reading_a_file_shows_checking_its_name(kb, recorder):
    store = h._store()                                               # a shipment, no line yet: the parse step runs
    at = h.app(store, kb)
    at.session_state["job"] = running_check(file_ref="f1")
    at.session_state["uploaded_file"] = {"name": "sample_packing_list.xlsx", "size": 10, "ref": "f1"}
    at.run()
    assert "Checking sample_packing_list.xlsx…" in texts(at)
    assert not at.file_uploader


def test_the_empty_state_is_disabled_while_any_job_runs(kb, recorder):
    at = h.app(empty_store(), kb)
    job = Job(kind="question", message="Which terms?", is_check=False)
    job.done = False
    at.session_state["job"] = job
    at.run()
    assert at.file_uploader[0].disabled and at.button(key="sample_empty").disabled
    assert at.text_input(key="check_one_line").disabled


def test_summary_after_a_check(kb, recorder):
    (store, _), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    statuses = {l.line_no: view.line_status(store, l) for l in store.lines}
    s = view.summary(store, statuses)
    page = texts(at)
    assert view.summary_text(s) in page and view.split_bar(s) in page


def test_the_header_names_the_file_escaped(kb, recorder):
    store, _ = h.store_with("ready", "review", kb=kb)
    at = h.app(store, kb)
    at.session_state["uploaded_file"] = {"name": "inv_[1].xlsx", "size": 10, "ref": "f1"}
    at.run()
    assert any(m.value == r"inv\_\[1\]\.xlsx · 2 lines" for m in at.markdown)
    store2, _ = h.store_with("ready", kb=kb)
    at2 = h.app(store2, kb).run()
    assert any(plain(m.value) == "Typed lines · 1 line" for m in at2.markdown)


# --------------------------------------------------------------------------- US1: starting checks
def test_try_the_sample_invoice(kb, recorder):
    store = empty_store()
    at = h.app(store, kb)
    at.session_state["chat"] = [{"role": "user", "content": "old"}]
    with h.ModelGuard() as guard:
        at.run()
        at.button(key="sample_empty").click().run()
    assert not at.exception
    assert [j.kind for j in recorder.jobs] == ["check"] and recorder.jobs[0].file_ref
    assert store.shipment.reference == h.SAMPLE_REFERENCE
    assert [m["content"] for m in at.session_state["chat"] if m["role"] == "user"] == [f"Check the packing list for {h.SAMPLE_REFERENCE}."]
    assert guard.calls == 0


def test_check_one_line(kb, recorder):
    store = empty_store()
    at = h.app(store, kb).run()
    at.text_input(key="check_one_line").set_value("Ceramic coffee mugs").run()
    assert not at.exception
    assert len(store.lines) == 1 and store.lines[0].current.created_by == CreatedBy.paste
    assert store.lines[0].current.text_en == "Ceramic coffee mugs"
    assert [j.kind for j in recorder.jobs] == ["check"] and recorder.jobs[0].new_line_nos == [1]


def test_one_more_line_and_its_queue(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    at = h.app(store, kb).run()
    at.button(key="more_line_button").click().run()
    at.text_input(key="more_line").set_value("Wooden chopsticks").run()
    assert len(store.lines) == 2 and store.lines[1].current.text_en == "Wooden chopsticks"
    assert recorder.jobs[-1].new_line_nos == [2]
    recorder.keep_running()                                         # while a job runs, the next line waits
    at.session_state["job"] = running_check()
    at.run()
    at.button(key="more_line_button").click().run()
    at.text_input(key="more_line").set_value("Ceramic dinner plates").run()
    assert len(store.lines) == 2
    assert at.session_state["job_queue"] == [("check", "Ceramic dinner plates")]
    assert "Waits for the running check" in texts(at)


def test_open_another_file(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    store.add_usage(Usage(total_tokens=1000, cost_eur=0.5, calls=2))
    at = h.app(store, kb).run()
    assert not at.file_uploader                                       # hidden until asked for
    at.button(key="open_file_button").click().run()
    assert at.file_uploader[0].label == "Drop a packing list or invoice here"
    at.button(key="sample_open").click().run()
    assert ("A checked shipment is open. Replace it with sample_packing_list.xlsx? Results, counts and cost reset."
            in texts(at))
    at.button(key="replace_yes").click().run()
    assert store.shipment.reference == h.SAMPLE_REFERENCE and at.session_state["session_usage"].total_tokens == 1000
    store2, _ = h.store_with("ready", kb=kb)                          # the button shows once lines exist
    at2 = h.app(store2, kb)
    at2.session_state["job"] = running_check()
    at2.run()
    assert at2.button(key="open_file_button").disabled


# --------------------------------------------------------------------------- US2: kinds (a) and (b) in place (T018)
def opened(store, kb, n, action=False):
    at = h.app(store, kb).run()
    at.button(key=f"{'act' if action else 'open'}_{n}").click().run()
    assert not at.exception
    return at


def keys(store, n, kind, form):
    vn = store.get_line(n).current.version_no
    base = f"{n}_{vn}_{kind}_{form}"
    return SimpleNamespace(pick=f"pick_{base}", confirm=f"confirm_{base}", none=f"none_{base}", typed=f"typed_{n}_{vn}",
                           level=f"change_level_{n}_{vn}")


def picks(at, pick):
    """The Pick buttons of one form: their value → their label."""
    return {b.key[len(pick) + 1:]: b.label for b in at.button if b.key and b.key.startswith(pick + "_")}


def taric_view_of(store, kb, n):
    from agent.agent import line_taric_view

    return line_taric_view(store, kb, n)


def candidates_block(at):
    return [e for e in at.expander if e.label == "HS-6 candidates (model estimate)"]


def test_kind_a_on_a_review_line(kb, recorder):
    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    line = store.get_line(n)
    at = opened(store, kb, n)
    page = texts(at)
    assert all(t in page for t in view.explain_a(store, line, "a_hs6"))
    assert all(f"**{t}**" in page for t in ("Code", "Description · precedent", "Confidence", "Pick"))
    assert "model estimate" in page and "Confidence is a model estimate, not a calibrated probability." in page
    for r in view.hs6_rows(store, line):
        assert f"`{r.code}`" in page and r.rationale in page
    assert sum(1 for t in page if ":gray-badge[history only]" in t) == 1
    assert [plain(p.proto.popover.label) for p in at.get("popover")] == ["BTI DE DE-940521-01"]
    assert page.count("no close precedent") == 2
    assert [p.proto.text for p in at.get("progress")] == ["58 %", "20 %", "10 %"]
    k = keys(store, n, "a_hs6", "hs6")
    assert picks(at, k.pick) == {"9405.21": "◉ Picked", "8543.70": "○ Pick", "9403.60": "○ Pick", "other": "○ Pick"}
    assert at.button(key=k.confirm).label == "Confirm 9405 21"
    at.button(key=f"{k.pick}_8543.70").click().run()
    assert picks(at, k.pick)["8543.70"] == "◉ Picked" and picks(at, k.pick)["9405.21"] == "○ Pick"
    assert at.button(key=k.confirm).label == "Confirm 8543 70 00"
    assert "then TARIC-10 runs on this code" in texts(at)


def test_confirm_returns_at_once_and_the_later_steps_run_in_the_background(kb, recorder):
    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    k = keys(store, n, "a_hs6", "hs6")
    recorder.keep_running()
    with h.ModelGuard() as guard:
        at.button(key=f"{k.pick}_8543.70").click().run()
        at.button(key=k.confirm).click().run()
    assert not at.exception
    d = store.get_line(n).current.decision
    assert (d.route, d.decided_code, d.chosen_how.value) == (DecisionRoute.accepted, "8543.70", "other_candidate")
    assert [(j.kind, j.line_no, j.taric_only) for j in recorder.jobs] == [("finer_codes", n, False)]
    assert guard.calls == 0
    assert at.session_state["selected_line_no"] is None
    assert ":gray[◌] Running CN-8 step…" in texts(at)
    recorder.run(store, kb)
    at.run()
    s = view.line_status(store, store.get_line(n))
    assert s.colour in ("green", "yellow") and f"{s.dot} {s.text}" in texts(at)


def test_other_hs6_code(kb, recorder):
    store, nos = h.store_with("review", "no_candidate", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    k = keys(store, n, "a_hs6", "hs6")
    assert not [t for t in at.text_input if t.key == k.typed]
    at.button(key=f"{k.pick}_other").click().run()
    typed = at.text_input(key=k.typed)
    assert typed.placeholder == "e.g. 8452.90" and typed.max_chars == 7
    for bad in ("", "8452", "9999.99"):                              # empty, malformed, not in the nomenclature
        at.text_input(key=k.typed).set_value(bad).run()
        at.button(key=k.confirm).click().run()
        assert any(t.startswith("Not confirmed: ") for t in texts(at)), bad
        assert store.get_line(n).current.decision is None and not recorder.jobs
    at.text_input(key=k.typed).set_value("8543.70").run()           # equal to a candidate: recorded as that candidate
    at.button(key=k.confirm).click().run()
    d = store.get_line(n).current.decision
    assert (d.decided_code, d.chosen_how.value) == ("8543.70", "other_candidate")
    assert [j.kind for j in recorder.jobs] == ["finer_codes"]
    m = nos["no_candidate"]                                          # no candidate: typing is the way to decide
    at = opened(store, kb, m)
    k = keys(store, m, "a_hs6", "hs6")
    assert picks(at, k.pick) == {"other": "○ Pick"}
    at.button(key=f"{k.pick}_other").click().run()
    at.text_input(key=k.typed).set_value("8518.30").run()
    at.button(key=k.confirm).click().run()
    d = store.get_line(m).current.decision
    assert (d.decided_code, d.chosen_how.value) == ("8518.30", "typed")
    assert [j.kind for j in recorder.jobs] == ["finer_codes", "finer_codes"]


def test_none_of_these_asks_the_shipper(kb, recorder):
    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    k = keys(store, n, "a_hs6", "hs6")
    assert at.button(key=k.none).label == "None of these → ask shipper"
    with h.ModelGuard() as guard:
        at.button(key=k.none).click().run()
    assert store.get_line(n).current.decision.route == DecisionRoute.ask_shipper
    assert ":red[●] Ask: what exactly are the goods?" in texts(at)
    assert not recorder.jobs and guard.calls == 0


@pytest.mark.parametrize("state", ["cn8_pending", "cn8_error", "cn8_missing", "taric_missing"])
def test_kind_a_for_a_cn8(kb, recorder, state):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    line = store.get_line(n)
    at = opened(store, kb, n)
    assert all(t in texts(at) for t in view.explain_a(store, line, "a_cn8"))
    block = candidates_block(at)
    assert len(block) == 1 and not block[0].proto.expanded
    k = keys(store, n, "a_cn8", "cn8")
    picked, _ = view.preselect(store, line, "a_cn8", "cn8")
    assert picks(at, k.pick)[picked] == "◉ Picked" and len(picks(at, k.pick)) == len(view.cn8_rows(store, line))
    estimates = [r for r in view.cn8_rows(store, line) if r.confidence is not None and r.precedent is None]
    assert texts(at).count("no close precedent") == len(estimates)                # the other CN-8 rows show none
    with h.ModelGuard() as guard:
        at.button(key=k.confirm).click().run()
    assert store.decided_cn8(store.get_line(n)) == picked
    assert [(j.kind, j.taric_only) for j in recorder.jobs] == [("finer_codes", True)]   # view.next_step: "TARIC step"
    assert guard.calls == 0


def test_kind_b_on_two_subdivisions(kb, recorder):
    from agent.taric_rules import eu_taric_url

    store, nos = h.store_with("taric_two", kb=kb)
    n = nos["taric_two"]
    line = store.get_line(n)
    tv = taric_view_of(store, kb, n)
    at = opened(store, kb, n)
    page = texts(at)
    assert all(t in page for t in view.explain_b(store, line, tv))
    assert "TARIC snapshot 2026-10-01 · origin CN" in page
    assert all(f"**{t}**" in page for t in ("Code", "Description", "Duty", "Anti-dumping", "Pick"))
    for r in view.subdivision_rows(tv):
        assert f"`{r.code}`" in page and r.duty in page and f":red[{r.anti_dumping}]" in page
    block = candidates_block(at)
    assert len(block) == 1 and not block[0].proto.expanded
    measures = [e for e in at.expander if e.label == "All measures"]
    assert len(measures) == 1
    assert [plain(m.value) for m in measures[0].markdown] == ["**Duties** · 1", "**Trade defence** · 2", "**Requirements** · 4"]
    links = {b.proto.label: b.proto.url for b in at.get("link_button")}
    assert {"EZT-online ↗", "Open in EU TARIC ↗"} <= set(links)       # beside the rulings' "Open ruling ↗"
    assert links["Open in EU TARIC ↗"] == eu_taric_url("7318155810", "CN", date(2026, 10, 1))
    assert [c.value for c in at.code] == ["7318155810 CN"]
    k = keys(store, n, "b", "taric10")
    at.button(key=f"{k.pick}_7318155890").click().run()
    assert {b.proto.label: b.proto.url for b in at.get("link_button")}["Open in EU TARIC ↗"] == \
        eu_taric_url("7318155890", "CN", date(2026, 10, 1))
    with h.ModelGuard() as guard:
        at.button(key=k.confirm).click().run()
    line = store.get_line(n)
    assert store.decided_taric10(line) == "7318155890" and line.current.cn8.written_by.value == "clerk"
    clerk = [r.change.value for r in store.shipment.audit if r.line_no == n and r.actor.value == "clerk"]
    assert clerk[-2:] == ["cn8_written", "taric_written"]
    assert ":green[●] Accepted" in texts(at)
    assert not recorder.jobs and guard.calls == 0


def test_kind_b_none_of_these_asks_the_shipper(kb, recorder):
    store, nos = h.store_with("taric_two", kb=kb)
    n = nos["taric_two"]
    at = opened(store, kb, n)
    with h.ModelGuard() as guard:
        at.button(key=keys(store, n, "b", "taric10").none).click().run()
    line = store.get_line(n)
    assert line.current.taric.question == h.TARIC_QUESTION and store.effective_route(line) == "ask_shipper"
    assert ":red[●] Ask: which TARIC subdivision applies?" in texts(at)
    assert not recorder.jobs and guard.calls == 0


def test_kind_b_suggestion(kb, recorder):
    store, nos = h.store_with("taric_two", kb=kb)
    n = nos["taric_two"]
    t = store.get_line(n).current.taric
    store.set_taric_result(n, t.model_copy(update={"suggestion": TaricSuggestion(code="7318155890", confidence=70)}))
    at = opened(store, kb, n)
    assert picks(at, keys(store, n, "b", "taric10").pick)["7318155890"] == "◉ Picked"
    store.set_taric_result(n, t.model_copy(update={"suggestion_error": "the model did not answer"}))
    at.run()
    assert "Suggestion unavailable: the model did not answer" in texts(at)


def test_refused_confirmations_change_nothing(kb, recorder, monkeypatch):
    from agent.store import LockedError, UnknownCodeError

    store, nos = h.store_with("taric_two", "cn8_pending", kb=kb)
    for state, kind, form, method, exc in (("taric_two", "b", "taric10", "confirm_taric10", LockedError("line is locked")),
                                           ("cn8_pending", "a_cn8", "cn8", "confirm_cn8", UnknownCodeError("not a CN line"))):
        n = nos[state]

        def refuse(*a, _exc=exc, **kw):
            raise _exc
        monkeypatch.setattr(store, method, refuse)
        before = store.get_line(n).current.model_dump()
        at = opened(store, kb, n)
        at.button(key=keys(store, n, kind, form).confirm).click().run()
        assert f"Not confirmed: {exc}" in texts(at)
        assert store.get_line(n).current.model_dump() == before and not recorder.jobs


@pytest.mark.parametrize("state", ["ready", "ready_taric", "accepted", "accepted_taric"])
def test_change_opens_kind_a_on_the_decided_codes(kb, recorder, state):
    origin = "US" if state == "ready_taric" else "CN"
    store, nos = h.store_with(state, origin=origin, kb=kb)
    n = nos[state]
    line = store.get_line(n)
    at = opened(store, kb, n, action=True)                           # "Change"
    page = texts(at)
    assert view.explain_a(store, line, "a_change")[0] in page
    k = keys(store, n, "a_change", "hs6")
    hs6 = store.decided_code(line)[0]
    assert picks(at, k.pick)[hs6] == "◉ Picked" and picks(at, k.pick)["other"] == "○ Pick"
    confirm = at.button(key=k.confirm)
    assert confirm.disabled and confirm.help == "This is the current code"
    forms = view.change_forms(store, line)
    level = [s for s in at.segmented_control if s.key == k.level]
    assert (level[0].options if level else ["HS-6"]) == forms
    if store.decided_taric10(line):                                  # the TARIC block
        assert f"TARIC snapshot 2026-10-01 · origin {origin}" in page and "All measures" in [e.label for e in at.expander]


def test_change_on_a_typed_hs6_holds_it_in_other(kb, recorder):
    store, nos = h.store_with("ready", kb=kb)
    n = nos["ready"]
    store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code="8518.30"))   # not a candidate: typed
    h._cn8(store, n, "8518.30", "85183000", conf=100)
    h._taric(store, kb, n)
    at = opened(store, kb, n, action=True)
    k = keys(store, n, "a_change", "hs6")
    assert picks(at, k.pick)["other"] == "◉ Picked" and at.text_input(key=k.typed).value == "8518.30"
    assert at.button(key=k.confirm).disabled


def test_change_confirms_another_hs6_or_cn8_in_the_background(kb, recorder):
    store, nos = h.store_with("ready_taric", origin="US", kb=kb)
    n = nos["ready_taric"]
    at = opened(store, kb, n, action=True)
    k = keys(store, n, "a_change", "cn8")
    at.segmented_control(key=k.level).set_value("CN-8").run()
    assert picks(at, k.pick)["73181568"] == "◉ Picked" and at.button(key=k.confirm).disabled
    assert len(candidates_block(at)) == 1 and not candidates_block(at)[0].proto.expanded
    at.button(key=f"{k.pick}_73181558").click().run()
    recorder.keep_running()
    with h.ModelGuard() as guard:
        at.button(key=k.confirm).click().run()
    assert store.decided_cn8(store.get_line(n)) == "73181558"
    assert [(j.kind, j.taric_only) for j in recorder.jobs] == [("finer_codes", True)] and guard.calls == 0
    assert ":gray[◌] Running TARIC step…" in texts(at)
    store2, nos2 = h.store_with("ready", kb=kb)
    m = nos2["ready"]
    at2 = opened(store2, kb, m, action=True)
    k2 = keys(store2, m, "a_change", "hs6")
    at2.button(key=f"{k2.pick}_other").click().run()
    at2.text_input(key=k2.typed).set_value("8518.30").run()
    with h.ModelGuard() as guard:
        at2.button(key=k2.confirm).click().run()
    d = store2.get_line(m).current.decision
    assert (d.decided_code, d.chosen_how.value) == ("8518.30", "typed") and guard.calls == 0
    assert (recorder.jobs[-1].kind, recorder.jobs[-1].taric_only) == ("finer_codes", False)
    assert ":gray[◌] Running CN-8 step…" in texts(at2)


def test_change_forms_keep_their_picks(kb, recorder):
    store, nos = h.store_with("accepted_taric", kb=kb)
    n = nos["accepted_taric"]
    at = opened(store, kb, n, action=True)
    hs6, cn8 = keys(store, n, "a_change", "hs6"), keys(store, n, "a_change", "cn8")
    at.button(key=f"{hs6.pick}_other").click().run()
    at.segmented_control(key=hs6.level).set_value("CN-8").run()
    at.button(key=f"{cn8.pick}_73181552").click().run()
    at.segmented_control(key=hs6.level).set_value("HS-6").run()
    assert picks(at, hs6.pick)["other"] == "◉ Picked"
    at.segmented_control(key=hs6.level).set_value("CN-8").run()
    assert picks(at, cn8.pick)["73181552"] == "◉ Picked"


def test_change_the_taric10(kb, recorder):
    store, nos = h.store_with("accepted_taric", kb=kb)
    n = nos["accepted_taric"]
    at = opened(store, kb, n, action=True)
    k = keys(store, n, "a_change", "taric10")
    at.segmented_control(key=k.level).set_value("TARIC-10").run()
    assert picks(at, k.pick)["7318155810"] == "◉ Picked" and at.button(key=k.confirm).disabled
    at.button(key=f"{k.pick}_7318155890").click().run()
    with h.ModelGuard() as guard:
        at.button(key=k.confirm).click().run()
    line = store.get_line(n)
    assert store.decided_taric10(line) == "7318155890" and not recorder.jobs and guard.calls == 0
    page = texts(at)
    assert ":green[●] Accepted" in page and "`7318 15 58 90`" in page
    assert any(r.change.value == "taric_written" and r.new == "7318155890" and r.actor.value == "clerk"
               for r in store.shipment.audit)


# --------------------------------------------------------------------------- US3: kind (c), the edit and the re-check (T026)
RED = ("failed", "ics2_term", "firm_stop_word", "vague_close", "vague_apart", "unreadable", "cn8_question", "sent",
       "taric_question")


def edit_keys(store, n):
    vn = store.get_line(n).current.version_no
    return SimpleNamespace(area=f"edit_{n}_{vn}", recheck=f"recheck_{n}_{vn}")


def test_kind_c_on_an_ics2_term(kb, recorder):
    store, nos = h.store_with("ics2_term", kb=kb)
    n = nos["ics2_term"]
    line = store.get_line(n)
    at = opened(store, kb, n)
    page = texts(at)
    assert "**Ask the shipper**" in page
    assert [c.value for c in at.code] == [view.question(store, line, "en", kb)]
    assert ":material/content_copy: Copy question — the copy button at the top right of the box" in page
    assert "Reason: ICS2 unacceptable term 'spare parts'" in page and view.candidates_line(line) in page
    block = candidates_block(at)
    assert len(block) == 1 and block[0].proto.expanded
    assert "All steps run again for this line, from the stop-word check." in page


@pytest.mark.parametrize("state", [s for s in RED if s != "ics2_term"])
def test_kind_c_on_the_other_red_rows(kb, recorder, state):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    line = store.get_line(n)
    at = opened(store, kb, n)
    page = texts(at)
    assert view.reason_line(store, line) in page
    assert [c.value for c in at.code] == ([] if state == "failed" else [view.question(store, line, "en", kb)])
    assert ("**Ask the shipper**" in page) is (state != "failed")
    assert at.text_area(key=edit_keys(store, n).area).value == line.current.display_text
    if line.current.candidates:
        assert candidates_block(at)[0].proto.expanded


def test_the_description_field_is_never_cut_and_names_the_original(kb, recorder):
    store = h._store()
    n = h._add(store, "B" * 290, "刹" * 280)
    h._check(store, kb, n)
    h._classify(store, n, [])
    original = store.get_line(n).current.display_text
    at = opened(store, kb, n)
    k = edit_keys(store, n)
    area = at.text_area(key=k.area)
    assert area.value == original and area.max_chars == 603
    assert plain(area.help) == f"Original: '{original}' — kept in the audit trail as 'description updated by clerk'"
    at.text_area(key=k.area).set_value("刹" * 301 + " Brake pads").run()
    at.button(key=k.recheck).click().run()
    assert "Not re-checked: the Chinese text is over 300 characters" in texts(at)
    assert store.get_line(n).current.version_no == 1 and not recorder.jobs


def test_the_top_of_the_row_shows_the_contradiction_and_the_reply_fields(kb, recorder):
    from agent.schemas import Extracted, LineVersion

    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    store.add_version(n, LineVersion(created_by=CreatedBy.shipper_reply, text_en="Steel bobbin cases for industrial sewing machines",
                                     extracted=Extracted(material="steel", part_name="bobbin case", use="sewing machines"),
                                     contradiction_note="The reply contradicts the file: 8452.90, not 9405.21"))
    h._check(store, kb, n)
    h._classify(store, n, [("8452.90", 91), ("8452.30", 5)])
    at = opened(store, kb, n)
    assert [plain(w.value) for w in at.warning] == ["The reply contradicts the file: 8452.90, not 9405.21"]
    assert "From the shipper's reply — material: steel · part: bobbin case · use: sewing machines" in texts(at)


def test_recheck_with_no_job_running(kb, recorder):
    store, nos = h.store_with("ics2_term", kb=kb)
    n = nos["ics2_term"]
    at = opened(store, kb, n)
    k = edit_keys(store, n)
    recorder.keep_running()
    at.text_area(key=k.area).set_value("  ").run()
    at.button(key=k.recheck).click().run()
    assert "Write the goods description first." in texts(at) and store.get_line(n).current.version_no == 1
    at.text_area(key=k.area).set_value("刹车片 Brake pads for bicycles, steel").run()
    with h.ModelGuard() as guard:
        at.button(key=k.recheck).click().run()
    v = store.get_line(n).current
    assert (v.version_no, v.created_by, v.text_zh, v.text_en) == (2, CreatedBy.clerk, "刹车片", "Brake pads for bicycles, steel")
    assert [(j.kind, j.line_no) for j in recorder.jobs] == [("recheck", n)] and guard.calls == 0
    assert at.session_state["selected_line_no"] is None
    assert ":gray[◌] Running stop-word check…" in texts(at)


def test_recheck_while_a_job_runs_waits_as_data(kb, recorder):
    store, nos = h.store_with("ics2_term", "review", kb=kb)
    n = nos["ics2_term"]
    at = opened(store, kb, n)
    k = edit_keys(store, n)
    recorder.keep_running()
    running = Job(kind="finer_codes", message="", is_check=False, line_no=nos["review"])
    running.done = False
    at.session_state["job"] = running
    at.text_area(key=k.area).set_value("Brake pads for bicycles, steel").run()
    at.button(key=k.recheck).click().run()
    assert store.get_line(n).current.version_no == 1                 # nothing new while a worker reads the store
    assert at.session_state["job_queue"] == [("recheck", n, "", "Brake pads for bicycles, steel")]
    page = texts(at)
    assert ":gray[◌] Queued: re-check" in page and "Waits for the running check" in page
    running.done = True                                              # it finishes: the edit is stored, then the job starts
    at.run()
    v = store.get_line(n).current
    assert (v.version_no, v.created_by) == (2, CreatedBy.clerk)
    assert [(j.kind, j.line_no) for j in recorder.jobs] == [("recheck", n)]


@pytest.mark.parametrize("state, text", [("ics2_term", "Brake pads for bicycles, steel"),
                                         ("cn8_question", "Plastic toy cars without a motor")])
def test_after_the_recheck(kb, recorder, state, text):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    at = opened(store, kb, n)
    k = edit_keys(store, n)
    at.text_area(key=k.area).set_value(text).run()
    recorder.keep_running()
    at.button(key=k.recheck).click().run()
    recorder.run(store, kb)
    at.run()
    s = view.line_status(store, store.get_line(n))
    if state == "ics2_term":                                         # ever flagged: never green (Principle I)
        assert s.colour == "yellow" and s.text.startswith("Confirm: ")
    else:
        assert s.colour in ("green", "yellow")
    assert f"{s.dot} {s.text}" in texts(at)
    record = at.session_state["chat"][-1]
    assert record["label"].startswith(f"Line {n} re-checked") and record["source_lines"] == [n]
    assert record["trace_from"] == n


def test_the_edited_states(kb, recorder):
    store, nos = h.store_with("edited_ever_flagged", "edited_never_flagged", kb=kb)
    ever = view.line_status(store, store.get_line(nos["edited_ever_flagged"]))
    assert ever.colour == "yellow" and ever.text.startswith("Confirm: ")
    never = view.line_status(store, store.get_line(nos["edited_never_flagged"]))
    assert never.colour in ("green", "yellow")
    at = h.app(store, kb).run()
    assert not at.exception and f"{ever.dot} {ever.text}" in texts(at)


@pytest.mark.parametrize("state", RED)
def test_the_accept_control_is_locked_on_red_rows(kb, recorder, state):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    s = view.line_status(store, store.get_line(n))
    at = h.app(store, kb).run()
    box = at.checkbox(key=f"accept_{n}")
    assert box.disabled and plain(box.help) == s.lock_reason
    assert f":material/lock: {s.lock_reason}" in texts(at)


# --------------------------------------------------------------------------- US4: accept the ready lines and export (T033)
def test_accept_all_ready(kb, recorder):
    store, _ = h.store_with("review", "ics2_term", kb=kb)
    at = h.app(store, kb).run()
    assert not [b for b in at.button if b.key == "accept_all"]       # K = 0: absent
    store, nos = h.store_with("ready", "ready_not_loaded", "accepted", "review", kb=kb)
    at = h.app(store, kb).run()
    assert at.button(key="accept_all").label == "Accept all 2 ready"
    with h.ModelGuard() as guard:
        at.button(key="accept_all").click().run()
    assert [view.line_status(store, store.get_line(nos[s])).text for s in ("ready", "ready_not_loaded", "accepted")] == \
        ["Accepted"] * 3
    assert not recorder.jobs and guard.calls == 0
    assert texts(at).count(":green[●] Accepted") == 3 and not [b for b in at.button if b.key == "accept_all"]


def test_accept_selected(kb, recorder):
    (store, _), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    enabled = {int(c.key.split("_")[1]) for c in at.checkbox if c.key.startswith("accept_") and not c.disabled}
    assert enabled == {l.line_no for l in store.lines if view.line_status(store, l).selectable}
    store, nos = h.store_with("ready", "ready_not_loaded", "review", kb=kb)
    third = h.build_state(store, kb, "ready")
    at = h.app(store, kb).run()
    assert not [b for b in at.button if b.key == "accept_selected"]
    at.checkbox(key=f"accept_{nos['ready']}").check().run()
    at.checkbox(key=f"accept_{third}").check().run()
    assert at.button(key="accept_selected").label == "Accept 2 selected"
    with h.ModelGuard() as guard:
        at.button(key="accept_selected").click().run()
    assert [view.line_status(store, store.get_line(n)).text for n in (nos["ready"], third, nos["ready_not_loaded"])] == \
        ["Accepted", "Accepted", "Ready"]
    assert not recorder.jobs and guard.calls == 0


def test_exports(kb, recorder, monkeypatch):
    import json

    from streamlit.delta_generator import DeltaGenerator

    exports = {}
    original = DeltaGenerator.download_button

    def spy(self, label, data, *args, **kwargs):
        exports[label] = dict(kwargs, data=data)
        return original(self, label, data, *args, **kwargs)
    monkeypatch.setattr(DeltaGenerator, "download_button", spy)
    store, _ = h.store_with("ready", "review", "ics2_term", kb=kb)
    at = h.app(store, kb)
    check = running_check()
    at.session_state["job"] = check
    at.run()
    assert exports["Export CSV"]["disabled"] and exports["Export JSON"]["disabled"]   # until the check has finished
    check.done = True
    at.run()
    csv, js = exports["Export CSV"], exports["Export JSON"]
    assert not csv["disabled"] and not js["disabled"]
    assert csv["data"] == store.to_csv_bytes()
    header = csv["data"].decode("utf-8-sig").splitlines()[0].split(",")
    assert header == store.CSV_COLUMNS and len(header) == 23 and header[-2:] == ["cn8", "taric10"]   # SC-005

    def without_time(raw):
        payload = json.loads(raw)
        payload["shipment"].pop("exported_at")
        return payload
    assert without_time(js["data"]) == without_time(store.to_json_bytes(knowledge_base_updated=kb.updated))
    assert json.loads(js["data"])["shipment"]["knowledge_base_updated"] == kb.updated
    for item, ext in ((csv, "csv"), (js, "json")):
        assert re.fullmatch(rf"cargolint_INV-TEST_\d{{8}}-\d{{4}}\.{ext}", item["file_name"])


# --------------------------------------------------------------------------- US5: the shipper email (T037)
def test_the_email_button_with_no_open_question(kb, recorder):
    store, _ = h.store_with("ready", "review", kb=kb)
    at = h.app(store, kb).run()
    button = at.button(key="email_button")
    assert button.label == "Draft shipper email (0 lines)" and button.disabled


def test_the_email_block(kb, recorder):
    from ui import shipper_email

    store, nos = h.store_with("ics2_term", "sent", "ready", "failed", kb=kb)
    before = [l.model_dump() for l in store.lines], [r.model_dump() for r in store.shipment.audit]
    at = h.app(store, kb).run()
    assert at.button(key="email_button").label == "Draft shipper email (2 lines)"
    with h.ModelGuard() as guard:
        at.button(key="email_button").click().run()
        page = texts(at)
        assert "**Email to shipper — generated from the 2 open questions, no model call**" in page
        assert ":material/content_copy: Copy email — the copy button at the top right of the text" in page
        assert at.segmented_control(key="email_lang").options == ["EN", "中文"]
        assert [c.value for c in at.code] == [shipper_email.draft(store, kb, "en").text]
        at.segmented_control(key="email_lang").set_value("中文").run()
        assert [c.value for c in at.code] == [shipper_email.draft(store, kb, "zh").text]
        at.button(key="email_button").click().run()                  # closes it again
        assert not at.code
    assert guard.calls == 0
    assert ([l.model_dump() for l in store.lines], [r.model_dump() for r in store.shipment.audit]) == before


# --------------------------------------------------------------------------- US6: the origin (T041)
REFUSED_C1 = "Origin not changed: the origin must be two letters, such as CN or US, not 'C1'"


def test_changing_the_origin_reapplies_the_taric_rules(kb, recorder):
    store, nos = h.store_with("taric_two", "accepted_taric", "ready", kb=kb)
    at = h.app(store, kb).run()
    with h.ModelGuard() as guard:
        at.text_input(key="origin_field").set_value("us").run()
    assert not at.exception
    assert store.shipment.taric_origin == "US" and at.text_input(key="origin_field").value == "US"
    assert all(store.get_line(n).current.taric.origin == "US" for n in nos.values())
    assert [t.value for t in at.toast] == ["Origin US — TARIC rules re-applied to 3 lines, no model call"]
    assert store.decided_taric10(store.get_line(nos["accepted_taric"])) == "7318155810"   # the clerk's TARIC-10 stays
    assert guard.calls == 0
    at.text_input(key="origin_field").set_value("C1").run()
    assert REFUSED_C1 in texts(at)
    assert at.text_input(key="origin_field").value == "US" and store.shipment.taric_origin == "US"


def test_with_no_shipment_the_origin_is_kept_for_every_new_shipment(kb, recorder, monkeypatch):
    from types import SimpleNamespace as NS

    from ui import chat, upload

    store = empty_store()
    at = h.app(store, kb).run()
    at.text_input(key="origin_field").set_value("us").run()
    assert at.text_input(key="origin_field").value == "US" and not at.toast
    at.text_input(key="origin_field").set_value("C1").run()
    assert REFUSED_C1 in texts(at) and at.text_input(key="origin_field").value == "US"
    at.text_input(key="check_one_line").set_value("Ceramic coffee mugs").run()          # a typed line
    assert store.shipment.taric_origin == "US"
    for start in ("sample", "upload"):
        other = empty_store()
        at = h.app(other, kb).run()
        at.text_input(key="origin_field").set_value("US").run()
        if start == "sample":
            at.button(key="sample_empty").click().run()
        else:
            at.file_uploader[0].upload("inv.csv", b"description\nCeramic coffee mugs\n", "text/csv").run()
        assert not at.exception and other.shipment.taric_origin == "US", start
    monkeypatch.setattr(upload, "st", NS(session_state={"origin_field": "US"}))           # the Admin chat's shipments
    admin_store = empty_store()
    chat._ensure_shipment(admin_store)
    assert admin_store.shipment.taric_origin == "US"


def test_the_origin_stays_across_pages(kb, recorder):
    at = h.app(empty_store(), kb).run()                               # no shipment: only the field holds US
    at.text_input(key="origin_field").set_value("US").run()
    at.session_state["_harness_page"] = "admin"
    at.run()
    at.session_state["_harness_page"] = "main"
    at.run()
    assert at.text_input(key="origin_field").value == "US"
