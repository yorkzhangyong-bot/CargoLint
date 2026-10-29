"""The main page with AppTest (feature 005, contracts/ui.md §2 to §7; feature 012's frame: the header with the Origin
box, the two input tabs, the status line and the Advanced link): offline, a seeded store, jobs recorded instead of run,
model calls counted."""
from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest

from agent.config import get_settings
from agent.schemas import CreatedBy, Decision, DecisionRoute, TaricSuggestion, Usage
from tests.ui import harness as h
from ui import view
from ui.jobs import Job

pytestmark = pytest.mark.integration

WAIT = "Wait for the running check"


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


@pytest.fixture
def widths(monkeypatch):
    """The width each keyed button is drawn with, which AppTest does not keep: key → width."""
    import streamlit
    from streamlit.delta_generator import DeltaGenerator

    seen: dict = {}
    for name in ("button", "form_submit_button", "download_button"):
        def on_module(label, *args, _fn=getattr(streamlit, name), **kwargs):
            seen[kwargs.get("key")] = kwargs.get("width", "content")
            return _fn(label, *args, **kwargs)

        def on_container(self, label, *args, _fn=getattr(DeltaGenerator, name), **kwargs):
            seen[kwargs.get("key")] = kwargs.get("width", "content")
            return _fn(self, label, *args, **kwargs)
        monkeypatch.setattr(streamlit, name, on_module)
        monkeypatch.setattr(DeltaGenerator, name, on_container)
    return seen


@pytest.fixture
def layout(monkeypatch):
    """The layout arguments AppTest does not keep: each keyed container's keyword arguments, and each st.columns call's
    spec, gap and vertical alignment, in order."""
    import streamlit
    from streamlit.delta_generator import DeltaGenerator

    seen: dict = {"container": {}, "columns": []}

    def record(name, args, kwargs):
        if name == "container" and kwargs.get("key"):
            seen["container"][kwargs["key"]] = kwargs
        elif name == "columns":
            seen["columns"].append((args[0], kwargs.get("gap", "small"), kwargs.get("vertical_alignment", "top")))

    for name in ("container", "columns"):
        def on_module(*args, _fn=getattr(streamlit, name), _name=name, **kwargs):
            record(_name, args, kwargs)
            return _fn(*args, **kwargs)

        def on_container(self, *args, _fn=getattr(DeltaGenerator, name), _name=name, **kwargs):
            record(_name, args, kwargs)
            return _fn(self, *args, **kwargs)
        monkeypatch.setattr(streamlit, name, on_module)
        monkeypatch.setattr(DeltaGenerator, name, on_container)
    return seen


# --------------------------------------------------------------------------- feature 012, Step 1: the frame (FR-002 to FR-007)
NOTHING_TO_CHECK = "Drop a file or load the sample invoice first"


def test_the_page_frame(kb, recorder, widths):
    at = h.app(empty_store(), kb).run()
    assert not at.exception
    assert "### CargoLint" in [m.value for m in at.markdown]
    page = texts(at)
    assert "Check invoice and packing-list lines before customs declaration" in page
    origin = at.selectbox(key="origin_field")                        # FR-003: ISO codes only, CN by default
    assert (origin.label, origin.value, origin.options) == ("Origin", "CN", list(view.ORIGIN_CODES))
    assert "Duty and measures follow this country. Changing it re-applies them without a new model call." in page
    assert view.snapshot_caption(kb) in page                         # Principle I: the snapshot date stays displayed
    assert [t.label for t in at.tabs] == ["Upload file", "Check a single line"]
    upload_tab, line_tab = at.tabs
    assert len(at.file_uploader) == len(upload_tab.file_uploader) == 1
    up = upload_tab.file_uploader[0]
    assert up.label == "Drag and drop a PDF, Excel, CSV or photo (jpg/png) here, or browse files" and not up.disabled
    assert "about 1 minute for 30 lines" in page
    assert [(b.key, b.label) for b in upload_tab.button] == [("sample", "Load sample invoice"),
                                                             ("check_all", "Check all lines")]
    check = at.button(key="check_all")
    assert check.proto.type == "primary" and check.disabled and check.help == NOTHING_TO_CHECK
    field = line_tab.text_input(key="single_line")
    assert (field.label, field.max_chars, field.disabled) == ("Goods description, in English or Chinese", 300, False)
    assert field.placeholder == "e.g. bicycle frames, aluminium"
    assert [(b.key, b.label, b.proto.type) for b in line_tab.button] == [("check_line", "Check this line", "primary")]
    assert widths["check_all"] == widths["check_line"] == "stretch"                       # SC-001
    assert not any(t.startswith(("Checked ", "Checking ")) for t in page)                  # no status line yet
    assert len(at.sidebar.children) == 0
    assert not at.get("page_link")                                   # no link to the Admin page (the author's check)


def test_nothing_from_fr002_on_the_main_page(kb, recorder):
    (store, _), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    assert not at.exception
    assert len(at.sidebar.children) == 0 and not at.chat_input and not at.slider
    assert not any(re.search(r"\b(Tokens|Cost)\b", t) for t in texts(at))
    assert not at.get("progress")                                    # no confidence bars in the table
    rows = [plain(b.label) for b in at.button if b.key and re.fullmatch(r"(open|act)_\d+", b.key)]
    assert not any("%" in r for r in rows)


# --------------------------------------------------------------------------- feature 012, Step 2: the list (FR-009, FR-010)
HEADERS = ("#", "Status", "Description", "Need / description", "HS code", "Conf.")
LIST_HEAD = "**Lines (sorted: ask shipper → review → ready)** · Page {} of {}"


def keyed(node, key):
    """The keyed container `key` under `node`; AppTest keeps the key at the end of the block's id."""
    for child in getattr(node, "children", {}).values():
        if child.type == "flex_container" and child.proto.id.endswith(f"-{key}"):
            return child
        found = keyed(child, key)
        if found is not None:
            return found
    return None


def row_of(at, n) -> SimpleNamespace:
    """Line n's row: the line number, the badge and its tooltip, the need or current description, the HS code and its
    note, Conf., and the description's open button."""
    block = keyed(at.main, f"line_{n}")
    assert block is not None, f"no row for line {n}"
    md = list(block.markdown)
    badge = next(m for m in md if "-badge[" in m.value)
    rest = [plain(m.value) for m in md if m is not badge]
    captions = [plain(c.value) for c in block.caption]               # the need or current description, then the note
    return SimpleNamespace(no=rest[0], badge=badge.value, help=plain(badge.proto.help), need=captions[0], code=rest[-2],
                           conf=rest[-1], note=captions[1:], open=[b for b in block.button if b.key == f"open_{n}"])


def cells_of(at, n) -> tuple:
    r = row_of(at, n)
    return r.no, r.badge, r.help, r.need, r.code, r.conf, r.note


def expected_cells(store, n, selected=None) -> tuple:
    """What view.row_cells says line n's row shows (FR-010)."""
    line = store.get_line(n)
    s = view.line_status(store, line)
    c = view.row_cells(store, line, s, selected)
    return (str(n), f":{c.colour}-badge[**{c.badge}**]", s.text, c.need, f"`{c.code}`" if c.code != "—" else "—", c.conf,
            [c.note] if c.note else [])


def open_order(at) -> list[int]:
    return [int(b.key[5:]) for b in at.button if b.key and re.fullmatch(r"open_\d+", b.key)]


def line_rows(at) -> list:
    return [e for e in at.expander if e.label.startswith("Line ")]


def test_the_list_sorted_with_its_rows(kb, recorder):
    (store, nos), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    assert not at.exception
    page = texts(at)
    assert LIST_HEAD.format(1, 1) in page and all(f"**{name}**" in page for name in HEADERS)
    statuses = {l.line_no: view.line_status(store, l) for l in store.lines}
    order = sorted(statuses, key=lambda n: (view.sort_group(statuses[n]), n))   # ask shipper, review, ready, accepted
    assert open_order(at) == [n for n in order if statuses[n].colour != "grey"]  # grey rows do not open
    for name, n in nos.items():
        assert cells_of(at, n) == expected_cells(store, n), name
        assert bool(row_of(at, n).open) is (statuses[n].colour != "grey"), name
    store2, _ = h.store_with("ready", kb=kb)
    weird = h._add(store2, "[click](https://x.test)")
    h._check(store2, kb, weird)
    h._classify(store2, weird, [])                                   # the fake judge: vague, so a red row
    at2 = h.app(store2, kb).run()
    assert at2.button(key=f"open_{weird}").label == r"\[click\]\(https\://x\.test\)"    # escaped, never a link


def test_fifty_lines_a_page(kb, recorder):
    store = h._store()
    for i in range(51):
        h._add(store, f"Ceramic coffee mugs, lot {i + 1}")
    at = h.app(store, kb).run()
    assert at.segmented_control(key="table_page").options == ["1", "2"]
    assert LIST_HEAD.format(1, 2) in texts(at)
    assert keyed(at.main, "line_50") is not None and keyed(at.main, "line_51") is None
    at.segmented_control(key="table_page").set_value(2).run()
    assert LIST_HEAD.format(2, 2) in texts(at)
    assert keyed(at.main, "line_51") is not None and keyed(at.main, "line_1") is None
    at.segmented_control(key="table_page").set_value(1).run()
    at.session_state["selected_line_no"] = 51                        # a line that opens by itself shows its page
    at.session_state["show_open_line"] = True
    at.run()
    assert LIST_HEAD.format(2, 2) in texts(at)


def test_opening_and_closing_a_line(kb, recorder):
    store, nos = h.store_with("review", "ready", kb=kb)
    n, m = nos["review"], nos["ready"]
    at = h.app(store, kb).run()
    at.button(key=f"open_{n}").click().run()
    assert at.session_state["selected_line_no"] == n
    assert [plain(e.label) for e in line_rows(at)] == [f"Line {n} · {store.get_line(n).current.display_text}"]
    at.button(key=f"open_{m}").click().run()                         # one line open at a time
    assert [plain(e.label) for e in line_rows(at)] == [f"Line {m} · {store.get_line(m).current.display_text}"]
    at.button(key=f"open_{m}").click().run()                         # its description again closes it
    assert at.session_state["selected_line_no"] is None and not line_rows(at)


def test_the_toggle_opens_and_closes_a_line(kb, recorder):           # the author: open rows are obvious
    store, nos = h.store_with("review", "ready", kb=kb)
    n, m = nos["review"], nos["ready"]
    at = h.app(store, kb).run()
    page = texts(at)
    assert page.index("Click a line to open it.") > page.index(LIST_HEAD.format(1, 1))    # above the table
    assert [at.button(key=f"toggle_{k}").label for k in (n, m)] == ["▸", "▸"]
    at.button(key=f"toggle_{n}").click().run()                       # the description's state: one line open
    assert at.session_state["selected_line_no"] == n and len(line_rows(at)) == 1
    assert [at.button(key=f"toggle_{k}").label for k in (n, m)] == ["▾", "▸"]
    at.button(key=f"open_{m}").click().run()                         # the description opens another line
    assert [at.button(key=f"toggle_{k}").label for k in (n, m)] == ["▸", "▾"]
    at.button(key=f"toggle_{m}").click().run()                       # and its toggle closes it
    assert at.session_state["selected_line_no"] is None and not line_rows(at)
    assert [at.button(key=f"toggle_{k}").label for k in (n, m)] == ["▸", "▸"]


# --------------------------------------------------------------------------- US1: live check, status line and counts (FR-007, FR-008)
def running_check(**kw) -> Job:
    job = Job(kind="check", message="Check", is_check=True, **kw)
    job.done = False
    return job


def test_a_running_check_shows_grey_rows_and_the_checking_status(kb, recorder):
    store = h._store()
    for text in ("Ceramic coffee mugs", "Wooden chopsticks", "Plastic toy figures"):
        h._add(store, text)
    at = h.app(store, kb)
    at.session_state["job"] = running_check()
    at.run()
    assert not at.exception
    for n in (1, 2, 3):
        r = row_of(at, n)
        assert (r.badge, r.help, r.open) == (":gray-badge[**Checking…**]", "Running stop-word check…", []), n
    assert any(re.fullmatch(r"Checking 3 lines… \d+ s", t) for t in texts(at))         # the status line (FR-007)
    assert not [b for b in at.button if b.key == "accept_all"]
    assert not [b for b in at.button if b.key and b.key.startswith("toggle_")]          # a grey line does not open


def test_reading_a_file_shows_its_name_escaped(kb, recorder):
    store = h._store()                                               # a shipment, no line yet: the parse step runs
    at = h.app(store, kb)
    at.session_state["job"] = running_check(file_ref="f1")
    at.session_state["uploaded_file"] = {"name": "inv_[1].xlsx", "size": 10, "ref": "f1"}
    at.run()
    status = [c.value for c in at.caption if plain(c.value).startswith("Checking ")]
    assert len(status) == 1 and re.fullmatch(r"Checking inv_\[1\]\.xlsx… \d+ s", plain(status[0]))
    assert r"inv\_\[1\]\.xlsx" in status[0]                         # escaped, never Markdown
    assert at.file_uploader[0].disabled                              # no second file while the first is read


def test_the_upload_tab_waits_while_any_job_runs(kb, recorder):
    at = h.app(empty_store(), kb)
    job = Job(kind="question", message="Which terms?", is_check=False)
    job.done = False
    at.session_state["job"] = job
    at.run()
    assert at.file_uploader[0].disabled and at.button(key="sample").disabled
    assert at.button(key="check_all").disabled and at.button(key="check_all").help == WAIT
    assert not at.text_input(key="single_line").disabled and not at.button(key="check_line").disabled   # it queues


def test_the_counts_row(kb, recorder):
    (store, _), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    s = view.summary(store, {l.line_no: view.line_status(store, l) for l in store.lines})
    for key, (label, colour, count) in zip(("count_ready", "count_review", "count_ask"), view.count_cards(s)):
        card = keyed(at.main, key)
        assert card is not None and card.proto.flex_container.border, key                  # a bordered card
        assert [c.value for c in card.caption] == [label] and [x.value for x in card.subheader] == [f":{colour}[{count}]"]
    assert at.button(key="accept_all").label == f"Accept all {s.to_accept} ready"
    assert [(b.key, b.proto.label) for b in at.get("download_button")] == [("export_csv", "Download CSV")]   # no JSON
    assert not at.metric and not any("█" in t for t in texts(at))     # no metric, no split bar
    assert not [c for c in at.checkbox if c.key and c.key.startswith("accept_")]   # D8: no row checkboxes


def test_the_compact_layout(kb, recorder, widths, layout):           # the author's polish after the check of the UI
    from ui import theme

    (store, _), _ = h.all_states(kb)
    at = h.app(store, kb).run()
    assert not at.exception
    boxes = layout["container"]
    styles = [m for m in at.markdown if "<style>" in m.value]                  # constitution 1.10.0: one CSS block
    assert len(styles) == 1 and styles[0].proto.allow_html and theme.CSS in styles[0].value
    assert set(re.findall(r"\.st-key-(\w+)", theme.CSS)) <= set(boxes)        # every key the CSS names is drawn
    assert {"count_ready", "count_review", "count_ask"} <= set(boxes) and 'class*="st-key-count_"' in theme.CSS
    assert (boxes["page"]["width"], boxes["page"]["gap"]) == (1400, "xsmall")      # about 1400 px wide, small gaps
    assert boxes["origin"]["border"] and boxes["origin"]["horizontal"]          # one compact Origin block
    for key in ("count_ready", "count_review", "count_ask"):   # label over number, no gap; no fixed height, no scrollbar
        assert boxes[key]["gap"] is None and boxes[key].get("height", "content") == "content", key
    assert ([2, 2, 2, 1.5, 1.5], "small", "center") in layout["columns"]      # the cards and the buttons, centred
    assert widths["accept_all"] == widths["export_csv"] == "content"           # normal width, not full width
    rows = [c for c in layout["columns"] if c[:2] == ([0.35, 0.4, 1.2, 3, 3, 1.4, 0.8], "xsmall")]   # toggle first
    assert len(rows) == 1 + len(store.lines)                                   # the list's head and each line's row
    assert boxes["lines"]["gap"] == 1                                          # rows 46 px apart


def test_the_status_line_after_a_check(recorder):
    kb = h.make_kb("sample")
    store = h.sample_store(kb)
    at = h.app(store, kb).run()
    statuses = {l.line_no: view.line_status(store, l) for l in store.lines}
    line = view.status_line(view.summary(store, statuses), file_name=store.shipment.source.name)
    assert re.fullmatch(r"Checked 12 lines of sample_packing_list\.xlsx in \d+ s", line)
    assert line in texts(at)
    assert not any(get_settings().chat_model in t for t in texts(at))       # the model shows on the Admin page only


# --------------------------------------------------------------------------- US1, US3: starting checks
def test_load_the_sample_then_check_all_lines(kb, recorder):
    store = empty_store()
    at = h.app(store, kb)
    at.session_state["chat"] = [{"role": "user", "content": "old"}]
    with h.ModelGuard() as guard:
        at.run()
        at.button(key="sample").click().run()
        assert not recorder.jobs and not store.has_shipment()          # loading starts nothing (FR-005)
        assert "Ready to check: sample_packing_list.xlsx" in texts(at) and not at.button(key="check_all").disabled
        at.button(key="check_all").click().run()
    assert not at.exception
    assert [j.kind for j in recorder.jobs] == ["check"] and recorder.jobs[0].file_ref
    assert store.shipment.reference == h.SAMPLE_REFERENCE
    assert [m["content"] for m in at.session_state["chat"] if m["role"] == "user"] == [f"Check the packing list for {h.SAMPLE_REFERENCE}."]
    assert guard.calls == 0
    assert "Ready to check: sample_packing_list.xlsx" not in texts(at)


def test_a_dropped_file_starts_nothing_until_check_all_lines(kb, recorder):
    store = empty_store()
    at = h.app(store, kb).run()
    at.file_uploader[0].upload("inv.csv", b"description\nCeramic coffee mugs\n", "text/csv").run()
    assert not at.exception and not recorder.jobs and not store.has_shipment()
    assert "Ready to check: inv.csv" in texts(at)
    at.button(key="check_all").click().run()
    assert [(j.kind, bool(j.file_ref)) for j in recorder.jobs] == [("check", True)]
    assert at.session_state["uploaded_file"]["name"] == "inv.csv"


def test_check_a_single_line(kb, recorder):
    store = empty_store()
    at = h.app(store, kb).run()
    at.button(key="check_line").click().run()                        # nothing typed
    assert "Write the goods description first." in texts(at) and not recorder.jobs
    recorder.keep_running()
    at.text_input(key="single_line").set_value("Ceramic coffee mugs")
    at.button(key="check_line").click().run()
    assert not at.exception
    assert len(store.lines) == 1 and store.lines[0].current.created_by == CreatedBy.paste
    assert store.lines[0].current.text_en == "Ceramic coffee mugs" and at.text_input(key="single_line").value == ""
    assert [(j.kind, j.new_line_nos) for j in recorder.jobs] == [("check", [1])]
    h._check(store, kb, 1)                                           # the job's work; then it ends
    h._classify(store, 1, [("3924.10", 60), ("3924.90", 20)])
    recorder.jobs[-1].done = True
    at.run()
    assert not at.exception
    assert at.session_state["selected_line_no"] == 1                 # FR-006: its row opens
    assert [plain(e.label) for e in line_rows(at)] == ["Line 1 · Ceramic coffee mugs"]


def test_a_single_line_joins_the_open_shipment_or_waits_in_the_queue(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    at = h.app(store, kb).run()
    at.text_input(key="single_line").set_value("Wooden chopsticks")
    at.button(key="check_line").click().run()
    assert len(store.lines) == 2 and store.lines[1].current.text_en == "Wooden chopsticks"
    assert recorder.jobs[-1].new_line_nos == [2]
    recorder.keep_running()                                         # while a job runs, the next line waits
    at.session_state["job"] = running_check()
    at.run()
    at.text_input(key="single_line").set_value("Ceramic dinner plates")
    at.button(key="check_line").click().run()
    assert len(store.lines) == 2
    assert at.session_state["job_queue"] == [("check", "Ceramic dinner plates")]
    page = texts(at)
    assert ":material/schedule: Ceramic dinner plates" in page and "Waits for the running check" in page


def test_a_new_file_on_an_open_shipment_asks_first(kb, recorder):
    store, _ = h.store_with("ready", kb=kb)
    store.add_usage(Usage(total_tokens=1000, cost_eur=0.5, calls=2))
    at = h.app(store, kb).run()
    assert len(at.file_uploader) == 1 and not at.get("popover")      # one drop zone, in the upload tab
    at.button(key="sample").click().run()
    at.button(key="check_all").click().run()
    assert ("A checked shipment is open. Replace it with sample_packing_list.xlsx? Results, counts and cost reset."
            in texts(at))
    assert store.shipment.reference == "INV-TEST" and not recorder.jobs
    at.button(key="replace_yes").click().run()
    assert store.shipment.reference == h.SAMPLE_REFERENCE and at.session_state["session_usage"].total_tokens == 1000
    assert [j.kind for j in recorder.jobs] == ["check"]


# --------------------------------------------------------------------------- US2: the open line, blocks 1 to 4 (FR-011, T020)
BLOCKS = ("**1 Description**", "**2 HS-6 candidates**", "**3 Similar rulings (5 nearest, EBTI)**")


def opened(store, kb, n):
    at = h.app(store, kb).run()
    at.button(key=f"open_{n}").click().run()
    assert not at.exception
    return at


def keys(store, n) -> SimpleNamespace:
    vn = store.get_line(n).current.version_no
    return SimpleNamespace(hs6=f"pick_{n}_{vn}_hs6", typed=f"typed_{n}_{vn}", accept=f"accept_{n}_{vn}",
                           ask=f"ask_{n}_{vn}", area=f"edit_{n}_{vn}", recheck=f"recheck_{n}_{vn}",
                           level=f"change_level_{n}_{vn}", base=f"{n}_{vn}")


def picks(at, pick):
    """The Pick buttons of one form: their value → their label."""
    return {b.key[len(pick) + 1:]: b.label for b in at.button if b.key and b.key.startswith(pick + "_")}


def taric_view_of(store, kb, n):
    from agent.agent import line_taric_view

    return line_taric_view(store, kb, n)


def radio_labels(at, key) -> list[str]:
    return [plain(o) for o in at.radio(key=key).options]


def test_an_hs6_to_choose(kb, recorder):
    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    line = store.get_line(n)
    at = opened(store, kb, n)
    page = texts(at)
    assert all(b in page for b in BLOCKS) and "**4 Tariff (Origin CN)**" in page
    assert f"Original: {line.versions[0].display_text} · Stop-word check: none found" in page
    k = keys(store, n)
    rows = view.hs6_rows(store, line)
    assert at.radio(key=k.hs6).value == "9405.21"                    # the top candidate
    assert radio_labels(at, k.hs6) == [view.candidate_label(r) + (" :gray-badge[history only]" if r.history_only else "")
                                       for r in rows] + ["Other HS-6 code…"]
    assert sum(1 for label in radio_labels(at, k.hs6) if label.endswith(":gray-badge[history only]")) == 1
    assert "Why: matches the subheading 9405.21" in page
    assert "Confidence is a model estimate, not a calibrated probability." in page
    assert [p.proto.value for p in at.get("progress")] == [r.confidence for r in rows]   # a bar beside each candidate
    assert "No ruling was within the similarity floor." in page      # block 3: no ruling voted
    assert view.explain_a(store, line, "a_hs6")[1] in page           # why the clerk decides
    rulings = [plain(p.proto.popover.label) for p in at.get("popover") if p.proto.popover.label.startswith("BTI")]
    assert rulings == ["BTI DE DE-940521-01 · 9405.21"]
    assert all(f"`{c}` {label}" in page for c, label in view.cn8_lines(store, line, "9405.21"))
    assert "CN-8 and TARIC-10 follow when you accept this code." in page
    accept, ask = at.button(key=k.accept), at.button(key=k.ask)
    assert (accept.label, accept.proto.type, accept.disabled) == ("Accept", "primary", False)
    assert (ask.label, ask.proto.type, ask.disabled) == ("Ask shipper", "secondary", False)
    with h.ModelGuard() as guard:
        at.radio(key=k.hs6).set_value("8543.70").run()               # D5: shown only, nothing written
    page = texts(at)
    assert "Why: matches the subheading 8543.70" in page
    assert all(f"`{c}` {label}" in page for c, label in view.cn8_lines(store, line, "8543.70"))
    assert (row_of(at, n).code, row_of(at, n).conf) == ("`8543.70`", "20%")
    assert store.get_line(n).current.decision is None and not recorder.jobs and guard.calls == 0


def test_accept_returns_at_once_and_the_later_steps_run_in_the_background(kb, recorder):
    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    k = keys(store, n)
    recorder.keep_running()
    with h.ModelGuard() as guard:
        at.radio(key=k.hs6).set_value("8543.70").run()
        at.button(key=k.accept).click().run()
    assert not at.exception
    d = store.get_line(n).current.decision
    assert (d.route, d.decided_code, d.chosen_how.value) == (DecisionRoute.accepted, "8543.70", "other_candidate")
    assert [(j.kind, j.line_no, j.taric_only) for j in recorder.jobs] == [("finer_codes", n, False)]
    assert guard.calls == 0 and at.session_state["selected_line_no"] is None and not line_rows(at)
    assert (row_of(at, n).badge, row_of(at, n).help) == (":gray-badge[**Checking…**]", "Running CN-8 step…")
    recorder.run(store, kb)
    at.run()
    s = view.line_status(store, store.get_line(n))
    assert s.colour in ("green", "yellow") and cells_of(at, n) == expected_cells(store, n)


def test_other_hs6_code(kb, recorder):
    store, nos = h.store_with("review", "no_candidate", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    k = keys(store, n)
    assert not [t for t in at.text_input if t.key == k.typed]
    at.radio(key=k.hs6).set_value(view.OTHER).run()
    typed = at.text_input(key=k.typed)
    assert typed.placeholder == "e.g. 8452.90" and typed.max_chars == 7
    for bad in ("", "8452", "9999.99"):                              # empty, malformed, not in the nomenclature
        at.text_input(key=k.typed).set_value(bad).run()
        at.button(key=k.accept).click().run()
        assert any(t.startswith("Not confirmed: ") for t in texts(at)), bad
        assert store.get_line(n).current.decision is None and not recorder.jobs
    at.text_input(key=k.typed).set_value("8543.70").run()           # equal to a candidate: recorded as that candidate
    at.button(key=k.accept).click().run()
    d = store.get_line(n).current.decision
    assert (d.decided_code, d.chosen_how.value) == ("8543.70", "other_candidate")
    assert [j.kind for j in recorder.jobs] == ["finer_codes"]
    m = nos["no_candidate"]                                          # no candidate: typing is the way to decide
    at = opened(store, kb, m)
    k = keys(store, m)
    assert radio_labels(at, k.hs6) == ["Other HS-6 code…"] and at.radio(key=k.hs6).value == view.OTHER
    at.text_input(key=k.typed).set_value("8518.30").run()
    at.button(key=k.accept).click().run()
    d = store.get_line(m).current.decision
    assert (d.decided_code, d.chosen_how.value) == ("8518.30", "typed")
    assert [j.kind for j in recorder.jobs] == ["finer_codes", "finer_codes"]


def test_ask_shipper_on_a_line_to_review(kb, recorder):
    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    with h.ModelGuard() as guard:
        at.button(key=keys(store, n).ask).click().run()
    assert store.get_line(n).current.decision.route == DecisionRoute.ask_shipper
    assert (row_of(at, n).badge, row_of(at, n).help) == (":red-badge[**Ask shipper**]", "Ask: what exactly are the goods?")
    assert line_rows(at) and not recorder.jobs and guard.calls == 0  # the line stays open on its question


@pytest.mark.parametrize("state", ["cn8_pending", "cn8_error", "cn8_missing", "taric_missing"])
def test_a_cn8_to_pick(kb, recorder, state):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    line = store.get_line(n)
    at = opened(store, kb, n)
    assert all(t in texts(at) for t in view.explain_a(store, line, "a_cn8"))
    k = keys(store, n)
    assert at.radio(key=k.hs6).value == store.decided_code(line)[0]
    pick = f"pick_{k.base}_a_cn8_cn8"
    picked, _ = view.preselect(store, line, "a_cn8", "cn8")
    assert picks(at, pick)[picked] == "◉ Picked" and len(picks(at, pick)) == len(view.cn8_rows(store, line))
    estimates = [r for r in view.cn8_rows(store, line) if r.confidence is not None and r.precedent is None]
    assert texts(at).count("no close precedent") == len(estimates)  # the other CN-8 rows show none
    with h.ModelGuard() as guard:
        at.button(key=k.accept).click().run()
    assert store.decided_cn8(store.get_line(n)) == picked
    assert [(j.kind, j.taric_only) for j in recorder.jobs] == [("finer_codes", True)]   # view.next_step: "TARIC step"
    assert guard.calls == 0


def test_a_subdivision_to_pick(kb, recorder):
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
    measures = [e for e in at.expander if e.label == "All measures"]
    assert len(measures) == 1
    assert [plain(m.value) for m in measures[0].markdown] == ["**Duties** · 1", "**Trade defence** · 2", "**Requirements** · 4"]
    links = {b.proto.label: b.proto.url for b in at.get("link_button")}
    assert {"EZT-online ↗", "Open in EU TARIC ↗"} <= set(links)
    assert links["Open in EU TARIC ↗"] == eu_taric_url("7318155810", "CN", date(2026, 10, 1))
    assert [c.value for c in at.code] == ["7318155810 CN"]
    k = keys(store, n)
    at.button(key=f"pick_{k.base}_b_taric10_7318155890").click().run()
    assert {b.proto.label: b.proto.url for b in at.get("link_button")}["Open in EU TARIC ↗"] == \
        eu_taric_url("7318155890", "CN", date(2026, 10, 1))
    with h.ModelGuard() as guard:
        at.button(key=k.accept).click().run()
    line = store.get_line(n)
    assert store.decided_taric10(line) == "7318155890" and line.current.cn8.written_by.value == "clerk"
    clerk = [r.change.value for r in store.shipment.audit if r.line_no == n and r.actor.value == "clerk"]
    assert clerk[-2:] == ["cn8_written", "taric_written"]
    assert row_of(at, n).badge == ":green-badge[**Accepted**]"
    assert not recorder.jobs and guard.calls == 0


def test_ask_shipper_at_the_subdivision_step(kb, recorder):
    store, nos = h.store_with("taric_two", kb=kb)
    n = nos["taric_two"]
    at = opened(store, kb, n)
    with h.ModelGuard() as guard:
        at.button(key=keys(store, n).ask).click().run()
    line = store.get_line(n)
    assert line.current.taric.question == h.TARIC_QUESTION and store.effective_route(line) == "ask_shipper"
    assert (row_of(at, n).badge, row_of(at, n).help) == (":red-badge[**Ask shipper**]", "Ask: which TARIC subdivision applies?")
    assert not recorder.jobs and guard.calls == 0


def test_a_suggested_subdivision(kb, recorder):
    store, nos = h.store_with("taric_two", kb=kb)
    n = nos["taric_two"]
    t = store.get_line(n).current.taric
    store.set_taric_result(n, t.model_copy(update={"suggestion": TaricSuggestion(code="7318155890", confidence=70)}))
    at = opened(store, kb, n)
    assert picks(at, f"pick_{keys(store, n).base}_b_taric10")["7318155890"] == "◉ Picked"
    store.set_taric_result(n, t.model_copy(update={"suggestion_error": "the model did not answer"}))
    at.run()
    assert "Suggestion unavailable: the model did not answer" in texts(at)


def test_refused_confirmations_change_nothing(kb, recorder, monkeypatch):
    from agent.store import LockedError, UnknownCodeError

    store, nos = h.store_with("taric_two", "cn8_pending", kb=kb)
    for state, method, exc in (("taric_two", "confirm_taric10", LockedError("line is locked")),
                               ("cn8_pending", "confirm_cn8", UnknownCodeError("not a CN line"))):
        n = nos[state]

        def refuse(*a, _exc=exc, **kw):
            raise _exc
        monkeypatch.setattr(store, method, refuse)
        before = store.get_line(n).current.model_dump()
        at = opened(store, kb, n)
        at.button(key=keys(store, n).accept).click().run()
        assert f"Not confirmed: {exc}" in texts(at)
        assert store.get_line(n).current.model_dump() == before and not recorder.jobs


@pytest.mark.parametrize("state", ["ready", "ready_taric", "accepted", "accepted_taric"])
def test_a_decided_line_opens_on_its_codes(kb, recorder, state):
    origin = "US" if state == "ready_taric" else "CN"
    store, nos = h.store_with(state, origin=origin, kb=kb)
    n = nos[state]
    line = store.get_line(n)
    at = opened(store, kb, n)
    page = texts(at)
    assert view.explain_a(store, line, "a_change")[0] in page        # "Decided: …", who decided each code
    k = keys(store, n)
    assert at.radio(key=k.hs6).value == store.decided_code(line)[0]
    level = [s for s in at.segmented_control if s.key == k.level]
    assert (level[0].options if level else []) == view.change_forms(store, line)
    accept = at.button(key=k.accept)
    accepted = view.line_status(store, line).accepted
    assert (accept.label, accept.disabled) == (("Accepted", True) if accepted else ("Accept", False))
    cn8, t10 = store.decided_cn8(line), store.decided_taric10(line)
    assert f"**CN-8: {view.spaced(cn8)} · TARIC: {view.spaced(t10) if t10 else '—'}**" in page
    if t10:
        assert f"TARIC snapshot 2026-10-01 · origin {origin}" in page and "All measures" in [e.label for e in at.expander]
        assert any(t.startswith("Third-country duty ") and " · Requirements: " in t for t in page)
    else:
        assert "TARIC not available" in page


def test_accept_on_a_ready_line_accepts_it(kb, recorder):
    store, nos = h.store_with("ready", kb=kb)
    n = nos["ready"]
    at = opened(store, kb, n)
    with h.ModelGuard() as guard:
        at.button(key=keys(store, n).accept).click().run()
    assert view.line_status(store, store.get_line(n)).text == "Accepted" and row_of(at, n).badge == ":green-badge[**Accepted**]"
    assert not line_rows(at) and not recorder.jobs and guard.calls == 0


def test_a_typed_hs6_holds_it_in_other(kb, recorder):
    store, nos = h.store_with("ready", kb=kb)
    n = nos["ready"]
    store.set_decision(n, Decision(route=DecisionRoute.accepted, decided_code="8518.30"))   # not a candidate: typed
    h._cn8(store, n, "8518.30", "85183000", conf=100)
    h._taric(store, kb, n)
    at = opened(store, kb, n)
    k = keys(store, n)
    assert at.radio(key=k.hs6).value == view.OTHER and at.text_input(key=k.typed).value == "8518.30"
    assert cells_of(at, n) == expected_cells(store, n)               # the line's own code: the row stays as it is


def test_change_the_cn8_or_the_hs6_in_the_background(kb, recorder):
    store, nos = h.store_with("ready_taric", origin="US", kb=kb)
    n = nos["ready_taric"]
    at = opened(store, kb, n)
    k = keys(store, n)
    at.segmented_control(key=k.level).set_value("CN-8").run()
    pick = f"pick_{k.base}_a_change_cn8"
    assert picks(at, pick)["73181568"] == "◉ Picked" and at.button(key=k.accept).label == "Accept"
    at.button(key=f"{pick}_73181558").click().run()
    recorder.keep_running()
    with h.ModelGuard() as guard:
        at.button(key=k.accept).click().run()
    assert store.decided_cn8(store.get_line(n)) == "73181558"
    assert [(j.kind, j.taric_only) for j in recorder.jobs] == [("finer_codes", True)] and guard.calls == 0
    assert (row_of(at, n).badge, row_of(at, n).help) == (":gray-badge[**Checking…**]", "Running TARIC step…")
    store2, nos2 = h.store_with("ready", kb=kb)
    m = nos2["ready"]
    at2 = opened(store2, kb, m)
    k2 = keys(store2, m)
    at2.radio(key=k2.hs6).set_value(view.OTHER).run()
    at2.text_input(key=k2.typed).set_value("8518.30").run()
    assert "CN-8 and TARIC-10 follow when you accept this code." in texts(at2)
    with h.ModelGuard() as guard:
        at2.button(key=k2.accept).click().run()
    d = store2.get_line(m).current.decision
    assert (d.decided_code, d.chosen_how.value) == ("8518.30", "typed") and guard.calls == 0
    assert (recorder.jobs[-1].kind, recorder.jobs[-1].taric_only) == ("finer_codes", False)
    assert (row_of(at2, m).badge, row_of(at2, m).help) == (":gray-badge[**Checking…**]", "Running CN-8 step…")


def test_the_change_levels_keep_their_picks(kb, recorder):
    store, nos = h.store_with("accepted_taric", kb=kb)
    n = nos["accepted_taric"]
    at = opened(store, kb, n)
    k = keys(store, n)
    cn8, taric = f"pick_{k.base}_a_change_cn8", f"pick_{k.base}_a_change_taric10"
    at.segmented_control(key=k.level).set_value("CN-8").run()
    at.button(key=f"{cn8}_73181552").click().run()
    at.segmented_control(key=k.level).set_value("TARIC-10").run()
    at.button(key=f"{taric}_7318155890").click().run()
    at.segmented_control(key=k.level).set_value("CN-8").run()
    assert picks(at, cn8)["73181552"] == "◉ Picked"
    at.segmented_control(key=k.level).set_value("TARIC-10").run()
    assert picks(at, taric)["7318155890"] == "◉ Picked"


def test_change_the_taric10(kb, recorder):
    store, nos = h.store_with("accepted_taric", kb=kb)
    n = nos["accepted_taric"]
    at = opened(store, kb, n)
    k = keys(store, n)
    at.segmented_control(key=k.level).set_value("TARIC-10").run()
    pick = f"pick_{k.base}_a_change_taric10"
    assert picks(at, pick)["7318155810"] == "◉ Picked"
    assert (at.button(key=k.accept).label, at.button(key=k.accept).disabled) == ("Accepted", True)
    at.button(key=f"{pick}_7318155890").click().run()
    assert (at.button(key=k.accept).label, at.button(key=k.accept).disabled) == ("Accept", False)
    with h.ModelGuard() as guard:
        at.button(key=k.accept).click().run()
    line = store.get_line(n)
    assert store.decided_taric10(line) == "7318155890" and not recorder.jobs and guard.calls == 0
    assert (row_of(at, n).badge, row_of(at, n).code) == (":green-badge[**Accepted**]", "`7318 15 58 90`")
    assert any(r.change.value == "taric_written" and r.new == "7318155890" and r.actor.value == "clerk"
               for r in store.shipment.audit)


def test_a_radio_choice_then_accept_updates_the_export(kb, recorder):   # FR-017
    import csv
    import io

    store, nos = h.store_with("review", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    k = keys(store, n)
    at.radio(key=k.hs6).set_value("8543.70").run()
    with h.ModelGuard() as guard:
        at.button(key=k.accept).click().run()
    rows = {int(r["line_no"]): r for r in csv.DictReader(io.StringIO(view.export_csv(store).decode("utf-8-sig")))}
    assert (rows[n]["decided_code"], rows[n]["decided_how"], rows[n]["route_set_by"], rows[n]["clerk_changed"]) == \
        ("8543.70", "other_candidate", "clerk", "true")
    assert guard.calls == 0


# --------------------------------------------------------------------------- US2: red lines, the edit and the re-check (T026)
RED = ("failed", "ics2_term", "firm_stop_word", "vague_close", "vague_apart", "unreadable", "cn8_question", "sent",
       "taric_question")


def test_a_red_line_on_an_ics2_term(kb, recorder):
    store, nos = h.store_with("ics2_term", kb=kb)
    n = nos["ics2_term"]
    line = store.get_line(n)
    at = opened(store, kb, n)
    page = texts(at)
    assert "Original: Spare parts" in page and not any("Stop-word check" in t for t in page)   # said once, as the
    assert page.count("Reason: ICS2 unacceptable term 'spare parts'") == 1                     # reason (the author)
    assert view.question(store, line, "en", kb) in [c.value for c in at.code]
    assert ":material/content_copy: Copy question — the copy button at the top right of the box" in page
    assert "runs the model again" in page
    k = keys(store, n)
    s = view.line_status(store, line)
    assert at.button(key=k.accept).disabled and plain(at.button(key=k.accept).help) == s.lock_reason
    assert at.button(key=k.ask).disabled                             # it asks the shipper already


@pytest.mark.parametrize("state", [s for s in RED if s != "ics2_term"])
def test_the_other_red_lines(kb, recorder, state):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    line = store.get_line(n)
    at = opened(store, kb, n)
    assert view.reason_line(store, line) in texts(at)
    original = f"Original: {line.versions[0].display_text or '_(no readable text)_'}"   # the stop-word result once:
    result = f"{original} · Stop-word check: {view.stop_word_result(line)}"   # as the reason or in the caption
    caption = original if view.reason_is_stop_word(line) else result
    assert caption in texts(at) and sum("Stop-word check" in t for t in texts(at)) == (caption != original)
    question = view.question(store, line, "en", kb)
    assert (question in [c.value for c in at.code]) is (state != "failed")
    assert at.text_area(key=keys(store, n).area).value == line.current.display_text


@pytest.mark.parametrize("state", RED)
def test_accept_is_locked_on_red_lines(kb, recorder, state):
    store, nos = h.store_with(state, kb=kb)
    n = nos[state]
    s = view.line_status(store, store.get_line(n))
    at = opened(store, kb, n)
    accept = at.button(key=keys(store, n).accept)
    assert accept.disabled and plain(accept.help) == s.lock_reason


def test_the_description_field_is_never_cut_and_names_the_original(kb, recorder):
    store = h._store()
    n = h._add(store, "B" * 290, "刹" * 280)
    h._check(store, kb, n)
    h._classify(store, n, [])
    original = store.get_line(n).current.display_text
    at = opened(store, kb, n)
    k = keys(store, n)
    area = at.text_area(key=k.area)
    assert area.value == original and area.max_chars == 603
    assert plain(area.help) == f"Original: '{original}' — kept in the audit trail as 'description updated by clerk'"
    at.text_area(key=k.area).set_value("刹" * 301 + " Brake pads").run()
    at.button(key=k.recheck).click().run()
    assert "Not re-checked: the Chinese text is over 300 characters" in texts(at)
    assert store.get_line(n).current.version_no == 1 and not recorder.jobs


def test_the_top_of_the_line_shows_the_contradiction_and_the_reply_fields(kb, recorder):
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
    k = keys(store, n)
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
    assert (row_of(at, n).badge, row_of(at, n).help) == (":gray-badge[**Checking…**]", "Running stop-word check…")


def test_recheck_while_a_job_runs_waits_as_data(kb, recorder):
    store, nos = h.store_with("ics2_term", "review", kb=kb)
    n = nos["ics2_term"]
    at = opened(store, kb, n)
    k = keys(store, n)
    recorder.keep_running()
    running = Job(kind="finer_codes", message="", is_check=False, line_no=nos["review"])
    running.done = False
    at.session_state["job"] = running
    at.text_area(key=k.area).set_value("Brake pads for bicycles, steel").run()
    at.button(key=k.recheck).click().run()
    assert store.get_line(n).current.version_no == 1                 # nothing new while a worker reads the store
    assert at.session_state["job_queue"] == [("recheck", n, "", "Brake pads for bicycles, steel")]
    assert (row_of(at, n).badge, row_of(at, n).help) == (":gray-badge[**Checking…**]", "Queued: re-check")
    assert "Waits for the running check" in texts(at)
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
    k = keys(store, n)
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
    assert cells_of(at, n) == expected_cells(store, n)
    record = at.session_state["chat"][-1]
    assert record["label"].startswith(f"Line {n} re-checked") and record["source_lines"] == [n]
    assert record["trace_from"] == n


def test_a_recheck_changes_only_its_row(kb, recorder):            # FR-017
    store, nos = h.store_with("ics2_term", "review", "ready", kb=kb)
    n = nos["ics2_term"]
    others = (nos["review"], nos["ready"])
    at = opened(store, kb, n)
    before = {m: (cells_of(at, m), store.get_line(m).current.model_dump()) for m in others}
    k = keys(store, n)
    at.text_area(key=k.area).set_value("Brake pads for bicycles, steel").run()
    recorder.keep_running()
    at.button(key=k.recheck).click().run()
    assert [(j.kind, j.line_no) for j in recorder.jobs] == [("recheck", n)]
    recorder.run(store, kb)
    at.run()
    assert {m: (cells_of(at, m), store.get_line(m).current.model_dump()) for m in others} == before
    assert row_of(at, n).badge != ":red-badge[**Ask shipper**]" and cells_of(at, n) == expected_cells(store, n)


def test_the_edited_states(kb, recorder):
    store, nos = h.store_with("edited_ever_flagged", "edited_never_flagged", kb=kb)
    ever = view.line_status(store, store.get_line(nos["edited_ever_flagged"]))
    assert ever.colour == "yellow" and ever.text.startswith("Confirm: ")
    never = view.line_status(store, store.get_line(nos["edited_never_flagged"]))
    assert never.colour in ("green", "yellow")
    at = h.app(store, kb).run()
    assert not at.exception
    for n in nos.values():
        assert cells_of(at, n) == expected_cells(store, n)
    edited = row_of(at, nos["edited_never_flagged"])
    assert edited.need == "Plastic toy cars without a motor"          # the current description, not the filed one


# --------------------------------------------------------------------------- US1: accept the ready lines and download (T033)
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
    assert [row_of(at, nos[s]).badge for s in ("ready", "ready_not_loaded", "accepted")] == [":green-badge[**Accepted**]"] * 3
    assert not [b for b in at.button if b.key == "accept_all"]


def test_the_csv_download(kb, recorder, monkeypatch):
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
    assert exports["Download CSV"]["disabled"]                       # until the check has finished
    check.done = True
    at.run()
    csv = exports["Download CSV"]
    assert not csv["disabled"] and list(exports) == ["Download CSV"]   # the only download: no JSON (the author's check)
    assert csv["data"] == view.export_csv(store)
    header = csv["data"].decode("utf-8-sig").splitlines()[0].split(",")
    assert header == [*store.CSV_COLUMNS, "clerk_changed"] and len(header) == 24   # SC-005 and FR-013
    assert re.fullmatch(r"cargolint_INV-TEST_\d{8}-\d{4}\.csv", csv["file_name"])


# --------------------------------------------------------------------------- US4: the shipper email draft (FR-012, T037)
DRAFT_HEAD = "**Shipper email draft** ·"


def test_no_draft_without_a_question(kb, recorder):
    store, _ = h.store_with("ready", "review", "failed", kb=kb)      # a failed check asks nothing of the shipper
    at = h.app(store, kb).run()
    assert DRAFT_HEAD not in texts(at) and not [s for s in at.segmented_control if s.key == "email_lang"]


def test_the_shipper_email_draft(kb, recorder):
    from ui import shipper_email

    store, nos = h.store_with("ics2_term", "sent", "ready", "failed", kb=kb)
    before = [l.model_dump() for l in store.lines], [r.model_dump() for r in store.shipment.audit]
    at = h.app(store, kb).run()
    with h.ModelGuard() as guard:
        page = texts(at)
        assert DRAFT_HEAD in page and "2 questions ready for the shipper" in page
        assert ":material/content_copy: Copy email — the copy button at the top right of the text" in page
        lang = at.segmented_control(key="email_lang")
        assert (lang.options, lang.value) == (["EN", "中文"], "EN")
        assert [c.value for c in at.code] == [shipper_email.draft(store, kb, "en").text]
        at.segmented_control(key="email_lang").set_value("中文").run()
        assert [c.value for c in at.code] == [shipper_email.draft(store, kb, "zh").text]
        assert not at.text_area and not at.expander                  # no update fields under the draft (the author's check)
    assert guard.calls == 0
    assert ([l.model_dump() for l in store.lines], [r.model_dump() for r in store.shipment.audit]) == before
    n = nos["sent"]                                                  # an asking line is updated in its open row
    at.button(key=f"open_{n}").click().run()
    k = keys(store, n)
    assert at.text_area(key=k.area).value == store.get_line(n).current.display_text
    assert at.button(key=k.recheck).label == "Re-check this line"


def test_ask_shipper_adds_the_line_to_the_draft(kb, recorder):      # FR-017
    from ui import shipper_email

    store, nos = h.store_with("review", "ready", kb=kb)
    n = nos["review"]
    at = opened(store, kb, n)
    assert DRAFT_HEAD not in texts(at)                               # no line asks yet
    with h.ModelGuard() as guard:
        at.button(key=keys(store, n).ask).click().run()
    draft = shipper_email.draft(store, kb, "en")
    assert draft.line_nos == [n] and draft.text in [c.value for c in at.code]
    assert DRAFT_HEAD in texts(at) and "1 question ready for the shipper" in texts(at)
    assert [b.key for b in at.button if b.label == "Re-check this line"] == [keys(store, n).recheck]   # the row's only
    assert not recorder.jobs and guard.calls == 0


# --------------------------------------------------------------------------- US6: the origin (T041; feature 012: the Origin box)
def test_changing_the_origin_reapplies_the_taric_rules(kb, recorder):
    store, nos = h.store_with("taric_two", "accepted_taric", "ready", kb=kb)
    at = h.app(store, kb).run()
    assert at.selectbox(key="origin_field").value == "CN"
    with h.ModelGuard() as guard:
        at.selectbox(key="origin_field").set_value("US").run()
    assert not at.exception
    assert store.shipment.taric_origin == "US" and at.selectbox(key="origin_field").value == "US"
    assert all(store.get_line(n).current.taric.origin == "US" for n in nos.values())
    assert [t.value for t in at.toast] == ["Origin US — TARIC rules re-applied to 3 lines, no model call"]
    assert store.decided_taric10(store.get_line(nos["accepted_taric"])) == "7318155810"   # the clerk's TARIC-10 stays
    assert guard.calls == 0
    assert all(re.fullmatch(r"[A-Z]{2}", c) for c in at.selectbox(key="origin_field").options)   # no invalid origin


def test_with_no_shipment_the_origin_is_kept_for_every_new_shipment(kb, recorder, monkeypatch):
    from types import SimpleNamespace as NS

    from ui import chat, upload

    store = empty_store()
    at = h.app(store, kb).run()
    at.selectbox(key="origin_field").set_value("US").run()
    assert at.selectbox(key="origin_field").value == "US" and not at.toast
    at.text_input(key="single_line").set_value("Ceramic coffee mugs")
    at.button(key="check_line").click().run()                                         # a typed line
    assert store.shipment.taric_origin == "US"
    for start in ("sample", "upload"):
        other = empty_store()
        at = h.app(other, kb).run()
        at.selectbox(key="origin_field").set_value("US").run()
        if start == "sample":
            at.button(key="sample").click().run()
        else:
            at.file_uploader[0].upload("inv.csv", b"description\nCeramic coffee mugs\n", "text/csv").run()
        at.button(key="check_all").click().run()
        assert not at.exception and other.shipment.taric_origin == "US", start
    monkeypatch.setattr(upload, "st", NS(session_state={"origin_field": "US"}))           # the Admin chat's shipments
    admin_store = empty_store()
    chat._ensure_shipment(admin_store)
    assert admin_store.shipment.taric_origin == "US"


def test_the_origin_stays_across_pages(kb, recorder):
    at = h.app(empty_store(), kb).run()                               # no shipment: only the box holds US
    at.selectbox(key="origin_field").set_value("US").run()
    at.session_state["_harness_page"] = "admin"
    at.run()
    at.session_state["_harness_page"] = "main"
    at.run()
    assert at.selectbox(key="origin_field").value == "US"


# --------------------------------------------------------------------------- feature 008: the precedent override
@pytest.mark.parametrize("env, override_min", [(None, 5), ("on", 5), ("off", None), ("false", None)])
def test_a_new_shipment_takes_the_override_switch(kb, recorder, monkeypatch, env, override_min):
    from agent.config import get_settings

    if env is None:
        monkeypatch.delenv("CARGOLINT_HS6_OVERRIDE", raising=False)
    else:
        monkeypatch.setenv("CARGOLINT_HS6_OVERRIDE", env)
    get_settings.cache_clear()
    try:
        store = empty_store()
        at = h.app(store, kb).run()
        at.text_input(key="single_line").set_value("Ceramic coffee mugs")
        at.button(key="check_line").click().run()
        assert not at.exception and store.shipment.hs6_override_min == override_min
    finally:
        get_settings.cache_clear()


def test_an_overridden_line_shows_the_chosen_candidate_and_its_audit_entry(kb, recorder):
    from agent.schemas import ChangeKind

    store, nos = h.store_with("hs6_override", kb=kb, hs6_override_min=4)
    n = nos["hs6_override"]
    line = store.get_line(n)
    s, code = view.line_status(store, line), view.code_display(store, line)
    assert (s.colour, s.text, code.text) == ("green", "Ready", "9405 21 40")      # candidate 2's code, not 8543 70
    r = row_of(h.app(store, kb).run(), n)
    assert (r.badge, r.code, r.conf) == (":green-badge[**Ready**]", "`9405 21 40`", "60%")   # at candidate 2's confidence
    decided = view.explain_a(store, line, "a_change")[0]
    assert decided.startswith("Decided: HS-6 9405 21, candidate 2 chosen, rulings overrode the model: 4 of 5 agree on "
                              "9405 21 (IE, DE, DE, FR); the model's top candidate was 8543 70 · ")
    assert decided in texts(opened(store, kb, n))                                  # the open line says who decided
    assert [(r.previous, r.new, r.note) for r in store.shipment.audit if r.line_no == n and r.change == ChangeKind.code_decided] \
        == [("8543.70", "9405.21", "rulings overrode the model: 4 of 5 agree on 9405.21; candidate 2 chosen")]


def test_an_overridden_line_whose_cn8_is_to_pick_says_the_rulings_overrode_the_model(kb, recorder):
    store, nos = h.store_with("hs6_override_cn8", kb=kb, hs6_override_min=4)
    n = nos["hs6_override_cn8"]
    s = view.line_status(store, store.get_line(n))
    assert (s.colour, s.text, s.kind) == ("yellow", "Pick: CN-8, 3 lines", "a_cn8")
    page = texts(opened(store, kb, n))                                              # the open line holds the CN-8 pick
    assert ("The HS-6 is 9405 21; rulings overrode the model: 4 of 5 agree on 9405 21; its subheading has 3 CN-8 "
            "lines.") in page
