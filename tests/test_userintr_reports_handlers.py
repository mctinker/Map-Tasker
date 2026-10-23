"""The report handlers: what each report button does before, around and after the report itself.

The reports are healthck's, taskflow's, varxref's, xmldiff's and timecomp's, and each has tests of its own.  Here
it is only the button: that nothing is asked of a configuration that is not there, that a report is saved and
then shown, that a clean result is said out loud and a dirty one points at where to click, and the ways each
stops early -- a comparison file that is the loaded one, a period with no history, a phone that does not answer.

The window is a mock and the report builders, the text view and the NiceGUI calls are replaced by recorders.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import userintr_reports
from maptasker.src.gui.userintr import MapTaskerEventHandlers

_LOADED = {"all_tasks": {"1": {"name": "Task"}}, "all_projects": {}, "all_profiles": {}}


def _handlers(*, loaded: bool = True) -> MapTaskerEventHandlers:
    window = MagicMock()
    window.state = RunState()
    window.state.tasker_root_elements = (
        dict(_LOADED) if loaded else {"all_tasks": {}, "all_projects": {}, "all_profiles": {}}
    )
    return MapTaskerEventHandlers(window)


def _said(handlers: MapTaskerEventHandlers) -> list[tuple[str, str]]:
    return [(c.args[0], c.args[1]) for c in _gui(handlers).display_message_box.call_args_list]


def _gui(handlers: MapTaskerEventHandlers) -> MagicMock:
    """The window the handlers were given, which is a mock in these tests."""
    return cast("MagicMock", handlers.gui)


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Everything the buttons reach for outside themselves, replaced and recorded."""
    record = SimpleNamespace(
        notified=[],
        views=[],
        dialogs=[],
        remembered=[],
        saved_args=[],
        saved_as="/out/report.txt",
        counts={"ERROR": 0, "WARNING": 0},
        rows=[],
    )

    def notify(message: str, **kw: Any) -> None:
        record.notified.append((message, kw.get("type")))

    ui = MagicMock()
    ui.notify = notify
    monkeypatch.setattr(userintr_reports, "ui", ui)

    def text_view(gui: object, title: str, the_data: object) -> str:
        record.views.append((title, the_data))
        return "view"

    monkeypatch.setattr(userintr_reports, "NiceGuiTextView", text_view)
    monkeypatch.setattr(userintr_reports.mapjump, "html_report", lambda rows: f"<html {len(rows)} rows>")
    monkeypatch.setattr(
        userintr_reports, "remember_setting", lambda gui, name, value: record.remembered.append((name, value))
    )
    monkeypatch.setattr(userintr_reports, "save_restore_args", lambda *a, **k: record.saved_args.append(k))
    monkeypatch.setattr(
        userintr_reports, "build_health_check_dialog", lambda run, save, gui, state: record.dialogs.append((run, save))
    )
    monkeypatch.setattr(userintr_reports, "ERROR", "ERROR")
    monkeypatch.setattr(userintr_reports, "WARNING", "WARNING")
    return record


# ##################################################################################
# Health Check
# ##################################################################################
def test_health_check_with_nothing_loaded_asks_for_a_file(seen: SimpleNamespace) -> None:
    handlers = _handlers(loaded=False)

    handlers.reports.health_check_event()

    assert _said(handlers) == [("No XML file has been loaded.  Get an XML file first.", "Red")]
    assert seen.dialogs == []


def test_health_check_asks_which_categories_before_scanning(seen: SimpleNamespace) -> None:
    handlers = _handlers()

    handlers.reports.health_check_event()

    assert seen.dialogs == [(handlers.reports.run_health_check_for, handlers.reports.save_health_check_skip)]


def test_the_categories_ticked_off_are_kept_in_the_window_and_the_settings_file(seen: SimpleNamespace) -> None:
    handlers = _handlers()

    handlers.reports.save_health_check_skip(["unused-variable"])

    assert seen.remembered == [("health_check_skip", ["unused-variable"])]
    assert seen.saved_args and seen.saved_args[0]["to_save"] is True


def _health(monkeypatch: pytest.MonkeyPatch, seen: SimpleNamespace, *, rows: list[Any], counts: dict[str, int]) -> list:
    asked: list[Any] = []
    monkeypatch.setattr(
        userintr_reports,
        "run_health_check",
        lambda skip, state: asked.append(skip) or (rows, counts),
    )
    monkeypatch.setattr(userintr_reports, "write_health_check_report", lambda rows, state: seen.saved_as)
    return asked


def test_a_clean_health_check_is_saved_shown_and_said_to_be_clean(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = _health(monkeypatch, seen, rows=[SimpleNamespace(target=None)], counts={"ERROR": 0, "WARNING": 0})
    handlers = _handlers()

    handlers.reports.run_health_check_for(["x"])

    assert asked == [["x"]]
    assert _said(handlers) == [("Health Check saved as /out/report.txt", "Green")]
    assert seen.views == [("Misc View", "<html 1 rows>")]
    assert seen.notified == [("Health Check found no errors or warnings.", "positive")]


def test_a_health_check_with_findings_points_at_where_to_click(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _health(monkeypatch, seen, rows=[SimpleNamespace(target="t")], counts={"ERROR": 1, "WARNING": 0})

    _handlers().reports.run_health_check_for([])

    assert seen.notified == [("Click a finding to see it in the Map view.", "info")]


def test_a_health_check_whose_report_could_not_be_written_says_so(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen.saved_as = ""
    _health(monkeypatch, seen, rows=[], counts={"ERROR": 0, "WARNING": 0})
    handlers = _handlers()

    handlers.reports.run_health_check_for([])

    assert _said(handlers) == [("Health Check report could not be saved.", "Red")]


# ##################################################################################
# Variable Cross-Reference
# ##################################################################################
def test_variable_xref_with_nothing_loaded_asks_for_a_file(seen: SimpleNamespace) -> None:
    handlers = _handlers(loaded=False)

    handlers.reports.variable_xref_event()

    assert "No XML file has been loaded" in _said(handlers)[0][0]
    assert seen.views == []


@pytest.fixture
def xref(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(live=[], suspects=True, shown_rows=[SimpleNamespace(target="t", pieces=None)])
    monkeypatch.setattr(
        userintr_reports,
        "run_variable_xref",
        lambda state, live=None: record.live.append(live) or (["row"], "index"),
    )
    monkeypatch.setattr(userintr_reports, "write_variable_xref_report", lambda rows, state: seen.saved_as)
    monkeypatch.setattr(userintr_reports, "build_report", lambda index, include_index, live, state: record.shown_rows)
    monkeypatch.setattr(userintr_reports, "suspects", lambda index, live: record.suspects)
    return record


def test_variable_xref_is_saved_in_full_and_shown_without_the_index(
    seen: SimpleNamespace, xref: SimpleNamespace
) -> None:
    handlers = _handlers()

    handlers.reports.variable_xref_event()

    assert _said(handlers) == [("Variable Cross-Reference saved as /out/report.txt", "Green")]
    assert seen.views == [("Misc View", "<html 1 rows>")]
    assert seen.notified == [("Click a variable or a place to see it in the Map view.", "info")]


def test_variable_xref_with_no_suspects_says_so(seen: SimpleNamespace, xref: SimpleNamespace) -> None:
    xref.suspects = False

    _handlers().reports.show_variable_xref()

    assert seen.notified == [("Variable Cross-Reference found no suspect variables.", "positive")]


def test_a_variable_xref_that_could_not_be_saved_says_so(seen: SimpleNamespace, xref: SimpleNamespace) -> None:
    seen.saved_as = ""
    handlers = _handlers()

    handlers.reports.show_variable_xref()

    assert _said(handlers) == [("Variable Cross-Reference report could not be saved.", "Red")]


def test_live_variable_xref_with_nothing_loaded_asks_for_a_file(seen: SimpleNamespace) -> None:
    handlers = _handlers(loaded=False)

    handlers.reports.variable_xref_live_event()

    assert "No XML file has been loaded" in _said(handlers)[0][0]


def _live_dialog(monkeypatch: pytest.MonkeyPatch, handlers: MapTaskerEventHandlers) -> SimpleNamespace:
    """Open the live-values dialog and return the Read Live Values button's handler and its widgets."""
    ui = userintr_reports.ui
    inputs: list[MagicMock] = []

    def make_input(*_a: object, **_k: object) -> MagicMock:
        field = MagicMock()
        field.classes.return_value = field
        field.value = ["192.168.1.7", "1821"][len(inputs)]
        inputs.append(field)
        return field

    ui.input = make_input
    clicks: dict[str, Any] = {}
    read_button = MagicMock()

    def button(label: str, on_click: Any = None) -> MagicMock:
        clicks[label] = on_click
        return read_button

    ui.button = button
    monkeypatch.setattr(userintr_reports, "android_address_defaults", lambda gui: ("192.168.1.2", "1821"))
    remembered: list[tuple[str, str]] = []
    monkeypatch.setattr(
        userintr_reports, "remember_android_address", lambda gui, ip, port: remembered.append((ip, port))
    )
    monkeypatch.setattr(userintr_reports, "remember_android_address_fields", lambda *a: None)
    handlers.reports.variable_xref_live_event()
    return SimpleNamespace(
        read=clicks["Read Live Values"], button=read_button.classes.return_value, remembered=remembered
    )


@pytest.mark.asyncio
async def test_reading_live_values_hands_what_the_phone_said_to_the_report(
    seen: SimpleNamespace, xref: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    dialog = _live_dialog(monkeypatch, handlers)

    async def io_bound(function: Any, *args: object) -> object:
        return (0, "ok", {"%X": "1"})

    monkeypatch.setattr(userintr_reports.run, "io_bound", io_bound)

    await dialog.read()

    assert dialog.remembered == [("192.168.1.7", "1821")]
    assert xref.live == [{"%X": "1"}], "the report is built with the live values"
    dialog.button.set_enabled.assert_called_with(True)


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [None, (1, "No answer from the phone.", None)])
async def test_a_phone_that_does_not_answer_builds_no_report(
    seen: SimpleNamespace, xref: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, answer: object
) -> None:
    handlers = _handlers()
    dialog = _live_dialog(monkeypatch, handlers)

    async def io_bound(function: Any, *args: object) -> object:
        return answer

    monkeypatch.setattr(userintr_reports.run, "io_bound", io_bound)

    await dialog.read()

    assert xref.live == []
    assert seen.notified == ([("No answer from the phone.", "negative")] if answer else [])
    dialog.button.set_enabled.assert_called_with(True)


# ##################################################################################
# Task Flow
# ##################################################################################
def test_task_flow_with_nothing_loaded_asks_for_a_file(seen: SimpleNamespace) -> None:
    handlers = _handlers(loaded=False)

    handlers.reports.task_flow_event()

    assert "No XML file has been loaded" in _said(handlers)[0][0]


@pytest.mark.parametrize(
    ("counts", "target", "told"),
    [
        ({"ERROR": 0, "WARNING": 0}, None, ("Task Flow found no control-flow problems.", "positive")),
        ({"ERROR": 2, "WARNING": 0}, "t", ("Click a finding to see it in the Map view.", "info")),
    ],
)
def test_task_flow_saves_shows_and_draws_the_chosen_task(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, counts: dict[str, int], target: object, told: tuple
) -> None:
    rows = [SimpleNamespace(target=target)]
    monkeypatch.setattr(userintr_reports, "run_task_flow_check", lambda state: (rows, counts))
    monkeypatch.setattr(userintr_reports, "write_task_flow_report", lambda rows, state: seen.saved_as)
    handlers = _handlers()
    drawn: list[object] = []
    handlers.draw_task_flowchart = drawn.append  # type: ignore[method-assign]

    handlers.reports.task_flow_event()

    assert _said(handlers) == [("Task Flow report saved as /out/report.txt", "Green")]
    assert seen.views == [("Misc View", "<html 1 rows>")]
    assert drawn == [handlers.gui]
    assert seen.notified == [told]


def test_a_task_flow_report_that_could_not_be_written_says_so(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen.saved_as = ""
    monkeypatch.setattr(userintr_reports, "run_task_flow_check", lambda state: ([], {"ERROR": 0, "WARNING": 0}))
    monkeypatch.setattr(userintr_reports, "write_task_flow_report", lambda rows, state: seen.saved_as)
    handlers = _handlers()
    handlers.draw_task_flowchart = lambda gui: None  # type: ignore[method-assign]

    handlers.reports.task_flow_event()

    assert _said(handlers) == [("Task Flow report could not be saved.", "Red")]


# ##################################################################################
# Compare
# ##################################################################################
@pytest.fixture
def compare(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(
        picked="/other.xml",
        loaded="/work/current.xml",
        loadable=("OTHER", ""),
        counts={"added": 1},
        report="a < b",
        compared=[],
    )

    async def choose(gui: object) -> str:
        return record.picked

    monkeypatch.setattr(userintr_reports, "_choose_comparison_file", choose)
    monkeypatch.setattr(userintr_reports, "loaded_file_path", lambda state: record.loaded)
    monkeypatch.setattr(userintr_reports, "load_for_comparison", lambda path, state: record.loadable)
    monkeypatch.setattr(userintr_reports, "current_configuration", lambda state: "CURRENT")
    monkeypatch.setattr(userintr_reports, "order_by_age", lambda other, current: (other, current))
    monkeypatch.setattr(
        userintr_reports,
        "compare",
        lambda older, newer: record.compared.append((older, newer)) or (record.report, record.counts),
    )
    monkeypatch.setattr(userintr_reports, "write_comparison_report", lambda report, *a, **k: seen.saved_as)
    return record


@pytest.mark.asyncio
async def test_compare_with_nothing_loaded_asks_for_a_file(seen: SimpleNamespace, compare: SimpleNamespace) -> None:
    handlers = _handlers(loaded=False)

    await handlers.reports.compare_files_event()

    assert "No XML file has been loaded" in _said(handlers)[0][0]


@pytest.mark.asyncio
async def test_backing_out_of_the_file_picker_cancels_the_comparison(
    seen: SimpleNamespace, compare: SimpleNamespace
) -> None:
    compare.picked = ""

    await _handlers().reports.compare_files_event()

    assert seen.notified == [("Comparison cancelled.", "warning")]
    assert compare.compared == []


@pytest.mark.asyncio
async def test_the_loaded_file_is_not_compared_with_itself(seen: SimpleNamespace, compare: SimpleNamespace) -> None:
    compare.picked = compare.loaded
    handlers = _handlers()

    await handlers.reports.compare_files_event()

    assert "already loaded" in _said(handlers)[0][0]
    assert compare.compared == []


@pytest.mark.asyncio
async def test_a_file_that_will_not_load_says_why(seen: SimpleNamespace, compare: SimpleNamespace) -> None:
    compare.loadable = (None, "other.xml is not a Tasker backup.")
    handlers = _handlers()

    await handlers.reports.compare_files_event()

    assert _said(handlers) == [("other.xml is not a Tasker backup.", "Red")]


@pytest.mark.asyncio
async def test_a_comparison_is_saved_and_shown_escaped(seen: SimpleNamespace, compare: SimpleNamespace) -> None:
    handlers = _handlers()

    await handlers.reports.compare_files_event()

    assert compare.compared == [("OTHER", "CURRENT")]
    assert _said(handlers) == [("Comparison saved as /out/report.txt", "Green")]
    assert seen.views == [("Misc View", "a &lt; b")], "a '<' in a Task name is shown, not read as markup"
    assert seen.notified == []


@pytest.mark.asyncio
async def test_two_identical_files_are_said_to_hold_the_same_configuration(
    seen: SimpleNamespace, compare: SimpleNamespace
) -> None:
    compare.counts = {"added": 0, "removed": 0}

    await _handlers().reports.compare_files_event()

    assert seen.notified == [("The two files hold the same configuration.", "positive")]


@pytest.mark.asyncio
async def test_a_comparison_that_could_not_be_written_says_so(seen: SimpleNamespace, compare: SimpleNamespace) -> None:
    seen.saved_as = ""
    handlers = _handlers()

    await handlers.reports.compare_files_event()

    assert _said(handlers) == [("Comparison report could not be saved.", "Red")]


# ##################################################################################
# Changes since
# ##################################################################################
@pytest.mark.asyncio
async def test_changes_since_with_nothing_loaded_asks_for_a_file_before_asking_how_far_back(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[object] = []
    monkeypatch.setattr(userintr_reports, "build_changes_since_dialog", asked.append)
    handlers = _handlers(loaded=False)

    await handlers.reports.timeline_event()

    assert asked == []
    assert "No XML file has been loaded" in _said(handlers)[0][0]


@pytest.mark.asyncio
async def test_changes_since_asks_how_far_back(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[object] = []
    monkeypatch.setattr(userintr_reports, "build_changes_since_dialog", asked.append)
    handlers = _handlers()

    await handlers.reports.timeline_event()

    assert asked == [handlers.reports.report_changes_since]


@pytest.fixture
def since(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(
        result=SimpleNamespace(problem="", note="", report="x & y", nothing_changed=False), cutoffs=[]
    )
    monkeypatch.setattr(
        userintr_reports.timeline,
        "cutoff_for",
        lambda period, on_date=None: record.cutoffs.append((period, on_date)) or "cutoff",
    )

    async def io_bound(function: Any, *args: object, **kwargs: object) -> object:
        return record.result

    monkeypatch.setattr(userintr_reports.run, "io_bound", io_bound)
    monkeypatch.setattr(userintr_reports, "write_comparison_report", lambda report, *a, **k: seen.saved_as)
    return record


@pytest.mark.asyncio
async def test_a_cancelled_wait_writes_no_report(seen: SimpleNamespace, since: SimpleNamespace) -> None:
    since.result = None

    await _handlers().reports.report_changes_since("week")

    assert seen.views == []


@pytest.mark.asyncio
async def test_a_period_with_no_history_says_why(seen: SimpleNamespace, since: SimpleNamespace) -> None:
    since.result.problem = "No history goes back that far."
    handlers = _handlers()

    await handlers.reports.report_changes_since("year")

    assert _said(handlers) == [("No history goes back that far.", "Red")]
    assert seen.views == []


@pytest.mark.asyncio
async def test_changes_are_reported_saved_and_shown_escaped_with_any_note_first(
    seen: SimpleNamespace, since: SimpleNamespace
) -> None:
    since.result.note = "History starts later than that."
    handlers = _handlers()

    await handlers.reports.report_changes_since("week")

    assert since.cutoffs == [("week", None)]
    assert seen.notified == [("History starts later than that.", "warning")]
    assert _said(handlers) == [("Timeline saved as /out/report.txt", "Green")]
    assert seen.views == [("Misc View", "x &amp; y")]


@pytest.mark.asyncio
async def test_nothing_changed_over_the_period_is_said_out_loud(seen: SimpleNamespace, since: SimpleNamespace) -> None:
    since.result.nothing_changed = True

    await _handlers().reports.report_changes_since("week")

    assert seen.notified == [("Nothing has changed in your configuration over that period.", "positive")]


@pytest.mark.asyncio
async def test_a_timeline_that_could_not_be_written_says_so(seen: SimpleNamespace, since: SimpleNamespace) -> None:
    seen.saved_as = ""
    handlers = _handlers()

    await handlers.reports.report_changes_since("week")

    assert _said(handlers) == [("Timeline report could not be saved.", "Red")]


# ##################################################################################
# Choosing the file to compare against
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("picked", "expected"),
    [([], ""), (["/a.xml"], "/a.xml"), (("/b.xml",), "/b.xml"), ("/c.xml", "/c.xml")],
)
async def test_the_comparison_file_is_the_first_one_picked(
    monkeypatch: pytest.MonkeyPatch, picked: object, expected: str
) -> None:
    async def picker(directory: str, **kwargs: object) -> object:
        assert kwargs == {"upper_limit": "~", "multiple": False}
        return picked

    class _Picker:
        def __init__(self, directory: str, **kwargs: object) -> None:
            self._answer = picker(directory, **kwargs)

        def __await__(self):
            return self._answer.__await__()

    monkeypatch.setattr(userintr_reports, "LocalFilePicker", _Picker)
    monkeypatch.setattr(userintr_reports, "local_xml_start_directory", lambda gui: "/start")

    assert await userintr_reports._choose_comparison_file(MagicMock()) == expected


# ##################################################################################
# Offering the original a loaded copy was saved from
# ##################################################################################
class _AnswerableDialog:
    """Stands in for ui.dialog(): a context manager that resolves to what the buttons would submit."""

    def __init__(self, answer: object) -> None:
        self.answer = answer
        self.submitted: list[object] = []

    def __enter__(self) -> _AnswerableDialog:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def submit(self, value: object) -> None:
        self.submitted.append(value)

    def __await__(self):
        async def answer() -> object:
            return self.answer

        return answer().__await__()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "expected"),
    [("/saved/from/original.xml", "/saved/from/original.xml"), ("", ""), (None, "")],
)
async def test_a_loaded_copy_offers_the_original_it_was_saved_from(
    monkeypatch: pytest.MonkeyPatch, answer: object, expected: str
) -> None:
    ui = MagicMock()
    dialog = _AnswerableDialog(answer)
    ui.dialog = lambda: dialog
    buttons: dict[str, Any] = {}

    def button(label: str, on_click: Any = None) -> MagicMock:
        buttons[label] = on_click
        shown = MagicMock()
        shown.props.return_value = shown
        shown.classes.return_value = shown
        return shown

    ui.button = button
    monkeypatch.setattr(userintr_reports, "ui", ui)
    monkeypatch.setattr(userintr_reports, "original_of", lambda path: "/saved/from/original.xml")
    monkeypatch.setattr(userintr_reports, "loaded_file_path", lambda state: "/work/copy.xml")

    assert await userintr_reports._choose_comparison_file(MagicMock()) == expected

    assert "Choose another file..." in buttons and "Cancel" in buttons
    buttons["Cancel"]()
    buttons["The original (original.xml)"]()
    assert dialog.submitted == ["", "/saved/from/original.xml"]


@pytest.mark.asyncio
async def test_choosing_another_file_goes_on_to_the_picker(monkeypatch: pytest.MonkeyPatch) -> None:
    dialog = _AnswerableDialog("pick")
    ui = MagicMock()
    ui.dialog = lambda: dialog
    monkeypatch.setattr(userintr_reports, "ui", ui)
    monkeypatch.setattr(userintr_reports, "original_of", lambda path: "/saved/from/original.xml")
    monkeypatch.setattr(userintr_reports, "loaded_file_path", lambda state: "/work/copy.xml")
    monkeypatch.setattr(userintr_reports, "local_xml_start_directory", lambda gui: "/start")

    class _Picker:
        def __init__(self, directory: str, **kwargs: object) -> None:
            self.directory = directory

        def __await__(self):
            async def picked() -> list[str]:
                return ["/elsewhere/other.xml"]

            return picked().__await__()

    monkeypatch.setattr(userintr_reports, "LocalFilePicker", _Picker)

    assert await userintr_reports._choose_comparison_file(MagicMock()) == "/elsewhere/other.xml"
