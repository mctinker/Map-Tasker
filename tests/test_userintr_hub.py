"""The handlers the groups share: the dialogs that rebuild on every press, saving the whole file, Undo and Redo, and the small ones.

Each of Refactor, Fix Findings, Restore, TaskerNet Updates, What Fires When, the Live Monitor, Missing Resources,
the Trend Dashboard and the Task Stepper is built fresh on every press, and has the same shape: take down the one
from last time, build the new one, remember it on the window and open it -- or, when the builder has nothing to
show, remember nothing.  That shape, and the jump and refresh closures each hands its dialog, are tested once
here for all nine.  The dialogs themselves are guiwins_*'s.

The window is a mock and the dialog builders, the browser and the update machinery are replaced by recorders.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from maptasker.src.core import mapjump
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import userintr
from maptasker.src.gui.userintr import MapTaskerEventHandlers


def _handlers(**window: Any) -> MapTaskerEventHandlers:
    gui = MagicMock()
    gui.state = RunState()
    for name, value in window.items():
        setattr(gui, name, value)
    return MapTaskerEventHandlers(gui)


def _gui(handlers: MapTaskerEventHandlers) -> MagicMock:
    """The window the handlers were given, which is a mock in these tests."""
    return cast("MagicMock", handlers.gui)


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(notified=[], jumped=[], refreshed=[], new_window=[])
    ui = MagicMock()
    ui.notify = lambda message, **kw: record.notified.append((message, kw.get("type")))
    monkeypatch.setattr(userintr, "ui", ui)

    async def go_to_target(gui: object, target: object) -> None:
        record.jumped.append(target)

    class _NewWindow:
        def __enter__(self) -> None:
            record.new_window.append("in")

        def __exit__(self, *_exc: object) -> None:
            record.new_window.append("out")

    monkeypatch.setattr(userintr, "go_to_target", go_to_target)
    monkeypatch.setattr(userintr, "opening_view_in_a_new_window", lambda gui: _NewWindow())
    monkeypatch.setattr(userintr, "refresh_tasker_object_pulldowns", lambda gui: record.refreshed.append(gui))
    return record


# ##################################################################################
# The dialogs built fresh on every press
# ##################################################################################
# (event, builder, window attribute, where make_jump sits among the builder's positional arguments,
#  where the refresh closure sits or None)
_LAUNCHERS = [
    ("refactor_event", "build_refactor_dialog", "refactor_dialog", 1, 2),
    ("fix_findings_event", "build_fix_dialog", "fix_dialog", 1, 2),
    ("restore_history_event", "build_restore_dialog", "restore_dialog", 0, 1),
    ("taskernet_updates_event", "build_tnupdate_dialog", "tnupdate_dialog", 0, 1),
    ("fire_simulator_event", "build_firesim_dialog", "firesim_dialog", 0, None),
    ("missing_resources_event", "build_resources_dialog", "resources_dialog", 1, None),
    ("task_stepper_event", "build_taskstep_dialog", "taskstep_dialog", 0, None),
]


@pytest.mark.parametrize(("event", "builder", "attribute", "jump_at", "refresh_at"), _LAUNCHERS)
def test_a_press_builds_a_fresh_dialog_remembers_it_and_opens_it(
    seen: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    builder: str,
    attribute: str,
    jump_at: int,
    refresh_at: int | None,
) -> None:
    dialog = MagicMock()
    build = MagicMock(return_value=dialog)
    monkeypatch.setattr(userintr, builder, build)
    handlers = _handlers()

    getattr(handlers, event)()

    build.assert_called_once()
    assert getattr(handlers.gui, attribute) is dialog
    dialog.open.assert_called_once()


@pytest.mark.parametrize(("event", "builder", "attribute", "jump_at", "refresh_at"), _LAUNCHERS)
def test_the_dialog_from_the_last_press_is_taken_down_first(
    seen: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    builder: str,
    attribute: str,
    jump_at: int,
    refresh_at: int | None,
) -> None:
    old = MagicMock()
    monkeypatch.setattr(userintr, builder, MagicMock(return_value=MagicMock()))
    handlers = _handlers(**{attribute: old})

    getattr(handlers, event)()

    old.delete.assert_called_once()
    assert getattr(handlers.gui, attribute) is not old


@pytest.mark.parametrize(("event", "builder", "attribute", "jump_at", "refresh_at"), _LAUNCHERS)
def test_a_dialog_whose_page_has_gone_is_one_more_dialog_already_gone(
    seen: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    builder: str,
    attribute: str,
    jump_at: int,
    refresh_at: int | None,
) -> None:
    old = MagicMock()
    old.delete.side_effect = RuntimeError("the client has been deleted")
    monkeypatch.setattr(userintr, builder, MagicMock(return_value=MagicMock()))
    handlers = _handlers(**{attribute: old})

    getattr(handlers, event)()  # must not raise

    assert getattr(handlers.gui, attribute) is not old


@pytest.mark.parametrize(("event", "builder", "attribute", "jump_at", "refresh_at"), _LAUNCHERS)
def test_a_builder_with_nothing_to_show_leaves_nothing_remembered(
    seen: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    builder: str,
    attribute: str,
    jump_at: int,
    refresh_at: int | None,
) -> None:
    monkeypatch.setattr(userintr, builder, MagicMock(return_value=None))
    handlers = _handlers()

    getattr(handlers, event)()

    assert getattr(handlers.gui, attribute) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("event", "builder", "attribute", "jump_at", "refresh_at"), _LAUNCHERS)
async def test_a_row_click_opens_what_it_names_in_a_window_of_its_own_and_keeps_the_dialog(
    seen: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    builder: str,
    attribute: str,
    jump_at: int,
    refresh_at: int | None,
) -> None:
    build = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(userintr, builder, build)
    getattr(_handlers(), event)()
    make_jump = build.call_args.args[jump_at]
    target = mapjump.Target(kind=mapjump.TASK, key="1", name="Wake Up")

    await make_jump(target)()

    assert seen.jumped == [target]
    assert seen.new_window == ["in", "out"], "the jump is made inside the new-window context, not the dialog's tab"


@pytest.mark.asyncio
@pytest.mark.parametrize(("event", "builder", "attribute", "jump_at", "refresh_at"), [x for x in _LAUNCHERS if x[4]])
async def test_applying_something_refreshes_the_pulldowns_and_nothing_else(
    seen: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    builder: str,
    attribute: str,
    jump_at: int,
    refresh_at: int,
) -> None:
    build = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(userintr, builder, build)
    handlers = _handlers()
    getattr(handlers, event)()

    await build.call_args.args[refresh_at]()

    assert seen.refreshed == [handlers.gui]


def test_the_edit_dialogs_are_handed_the_hubs_whole_file_save(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(userintr, "build_restore_dialog", build)
    handlers = _handlers()

    handlers.restore_history_event()

    assert build.call_args.args[2] == handlers.save_whole_configuration


def test_the_task_stepper_opens_on_the_task_it_was_asked_about(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    build = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(userintr, "build_taskstep_dialog", build)
    handlers = _handlers()

    handlers.task_stepper_event("Wake Up")

    assert build.call_args.args[2] == "Wake Up"


def test_the_trend_dashboard_is_built_for_the_run_and_remembered(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = MagicMock()
    build = MagicMock(return_value=dialog)
    monkeypatch.setattr(userintr, "build_trend_dialog", build)
    old = MagicMock()
    handlers = _handlers(trend_dialog=old)

    handlers.trend_dashboard_event()

    build.assert_called_once_with(handlers.state)
    old.delete.assert_called_once()
    assert handlers.gui.trend_dialog is dialog
    dialog.open.assert_called_once()


@pytest.mark.asyncio
async def test_the_live_monitor_stops_the_last_one_before_it_takes_it_down(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    monitor = MagicMock()
    monitor.stop_monitoring = AsyncMock(side_effect=lambda: order.append("stopped"))
    old = MagicMock(monitor=monitor)
    old.delete.side_effect = lambda: order.append("deleted")
    dialog = MagicMock()
    build = MagicMock(return_value=dialog)
    monkeypatch.setattr(userintr, "build_monitor_dialog", build)
    handlers = _handlers(monitor_dialog=old)

    await handlers.live_monitor_event()

    assert order == ["stopped", "deleted"], "a monitor is never left asking the phone with nothing on screen to stop it"
    assert handlers.gui.monitor_dialog is dialog
    dialog.open.assert_called_once()
    assert build.call_args.args[2] == handlers.bring_up_the_diagram_for_the_monitor


@pytest.mark.asyncio
async def test_a_live_monitor_with_nothing_to_watch_remembers_nothing(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(userintr, "build_monitor_dialog", MagicMock(return_value=None))
    handlers = _handlers(monitor_dialog=None)

    await handlers.live_monitor_event()

    assert handlers.gui.monitor_dialog is None


@pytest.mark.asyncio
async def test_the_monitors_diagram_is_built_for_what_has_fired_and_the_selection_put_back(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    handlers.state.program_arguments.single_project_name = "Mine"
    built: list[dict[str, object]] = []

    async def view_event(view_type: str, overrides: dict[str, object] | None = None) -> None:
        built.append({"view": view_type, **(overrides or {})})
        handlers.state.program_arguments.single_project_name = "changed during the build"

    handlers.view_event = view_event  # type: ignore[method-assign]
    monkeypatch.setattr(userintr.livemon, "diagram_scope", lambda projects: "Home")

    class _Held:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(userintr, "held_overrides", lambda overrides, state: _Held())

    await handlers.bring_up_the_diagram_for_the_monitor({"Home"})

    assert built[0]["view"] == "diagram" and built[0]["single_project_name"] == "Home"
    assert handlers.state.program_arguments.single_project_name == "Mine"
    assert "Project 'Home'" in seen.notified[0][0]


@pytest.mark.asyncio
async def test_with_several_projects_the_monitors_diagram_covers_the_whole_configuration(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    handlers.view_event = AsyncMock()  # type: ignore[method-assign]
    monkeypatch.setattr(userintr.livemon, "diagram_scope", lambda projects: "")
    monkeypatch.setattr(userintr, "held_overrides", MagicMock())

    await handlers.bring_up_the_diagram_for_the_monitor({"A", "B"})

    assert "the whole configuration" in seen.notified[0][0]
    awaited = cast("AsyncMock", handlers.view_event).await_args
    assert awaited is not None and awaited.kwargs["overrides"]["single_project_name"] == ""


# ##################################################################################
# Saving the whole file from a dialog
# ##################################################################################
@pytest.fixture
def save(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(written=(True, "/work/backup_2026.xml"), loaded=(True, ""), notice=MagicMock())

    async def notice() -> MagicMock:
        return record.notice

    monkeypatch.setattr(userintr, "show_save_in_progress_notice", notice)
    monkeypatch.setattr(userintr, "write_full_backup_to_current_file", lambda state: record.written)
    monkeypatch.setattr(userintr, "reload_saved_copy_and_refresh", lambda gui, path: record.loaded)
    return record


@pytest.mark.asyncio
async def test_a_saved_and_switched_file_says_so_and_asks_for_the_list_to_be_rebuilt(
    seen: SimpleNamespace, save: SimpleNamespace
) -> None:
    assert await _handlers().save_whole_configuration() is True

    assert "Saved a copy to /work/backup_2026.xml and loaded it." in seen.notified[0][0]
    assert seen.notified[0][1] == "positive"
    save.notice.dismiss.assert_called_once()


@pytest.mark.asyncio
async def test_a_copy_that_would_not_load_still_asks_for_a_rebuild_but_warns(
    seen: SimpleNamespace, save: SimpleNamespace
) -> None:
    save.loaded = (False, "bad xml")

    assert await _handlers().save_whole_configuration() is True

    assert "but it could not be loaded: bad xml" in seen.notified[0][0]
    assert seen.notified[0][1] == "warning"


@pytest.mark.asyncio
async def test_a_file_that_was_not_written_changes_nothing_and_asks_for_no_rebuild(
    seen: SimpleNamespace, save: SimpleNamespace
) -> None:
    save.written = (False, "disk full")

    assert await _handlers().save_whole_configuration() is False

    assert seen.notified == [("Could not save to current file: disk full", "negative")]
    save.notice.dismiss.assert_called_once()


@pytest.mark.asyncio
async def test_the_spinner_comes_down_even_when_the_write_raises(
    seen: SimpleNamespace, save: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(state: object) -> tuple[bool, str]:
        raise OSError("no space")

    monkeypatch.setattr(userintr, "write_full_backup_to_current_file", boom)

    with pytest.raises(OSError, match="no space"):
        await _handlers().save_whole_configuration()

    save.notice.dismiss.assert_called_once()


# ##################################################################################
# Undo and Redo
# ##################################################################################
@pytest.fixture
def history(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(result=(True, "Add Task 'A'"), calls=[], reset=[], labels=[], still_there=True)
    monkeypatch.setattr(userintr.sessundo, "undo", lambda state: record.calls.append("undo") or record.result)
    monkeypatch.setattr(userintr.sessundo, "redo", lambda state: record.calls.append("redo") or record.result)
    monkeypatch.setattr(userintr, "_single_selection_still_exists", lambda gui: record.still_there)
    monkeypatch.setattr(userintr, "reset_single_item_selection", lambda gui: record.reset.append(gui))
    monkeypatch.setattr(userintr, "display_selected_object_labels", lambda gui: record.labels.append(gui))
    return record


@pytest.mark.parametrize(
    ("event", "walked", "said"), [("undo_edit_event", "undo", "Undid"), ("redo_edit_event", "redo", "Redid")]
)
def test_undo_and_redo_walk_the_history_refresh_the_pulldowns_and_say_which(
    seen: SimpleNamespace, history: SimpleNamespace, event: str, walked: str, said: str
) -> None:
    handlers = _handlers()

    getattr(handlers, event)()

    assert history.calls == [walked]
    assert seen.refreshed == [handlers.gui]
    assert history.reset == [], "a step that left the selection standing does not clear it"
    assert seen.notified == [(f"{said}: Add Task 'A'", "positive")]


def test_a_step_that_took_the_selected_item_away_clears_the_selection_and_repaints_the_labels(
    seen: SimpleNamespace, history: SimpleNamespace
) -> None:
    history.still_there = False
    handlers = _handlers()

    handlers.undo_edit_event()

    assert history.reset == [handlers.gui] and history.labels == [handlers.gui]


def test_nothing_to_undo_is_a_warning_and_nothing_is_refreshed(seen: SimpleNamespace, history: SimpleNamespace) -> None:
    history.result = (False, "Nothing to undo.")

    _handlers().undo_edit_event()

    assert seen.notified == [("Nothing to undo.", "warning")]
    assert seen.refreshed == []


# ##################################################################################
# The Task Flow chart
# ##################################################################################
@pytest.fixture
def flow(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(
        scope=SimpleNamespace(label="Task", name="Wake Up", tasks={"7", "3"}),
        analysis="FLOW",
        chart_file="/out/flow.html",
        popped=[],
        charted=[],
    )
    monkeypatch.setattr(userintr.mapjump, "current_scope", lambda state: record.scope)
    monkeypatch.setattr(
        userintr, "analyze_task_flow", lambda task_id, state: record.charted.append(task_id) or record.analysis
    )
    monkeypatch.setattr(userintr, "flowchart", lambda flow_, state: ["row"])
    monkeypatch.setattr(userintr, "write_flowchart", lambda rows, state: record.chart_file)
    monkeypatch.setattr(
        userintr, "_open_popout_window", lambda path, new_window: record.popped.append((path, new_window))
    )
    return record


def test_without_a_single_task_chosen_the_chart_is_only_a_hint(seen: SimpleNamespace, flow: SimpleNamespace) -> None:
    flow.scope = SimpleNamespace(label="Project", name="Home", tasks=set())

    _handlers().draw_task_flowchart(MagicMock())

    assert seen.notified[0][1] == "info" and "Choose a single Task" in seen.notified[0][0]
    assert flow.popped == []


def test_a_task_that_cannot_be_found_is_said_not_charted(seen: SimpleNamespace, flow: SimpleNamespace) -> None:
    flow.analysis = None
    gui = MagicMock()

    _handlers().draw_task_flowchart(gui)

    assert gui.display_message_box.call_args.args == ("Could not find Task 'Wake Up'.", "Orange")
    assert flow.popped == []


def test_two_tasks_with_one_name_draw_the_first_and_say_so(seen: SimpleNamespace, flow: SimpleNamespace) -> None:
    gui = MagicMock(open_view_in_new_window=True)

    _handlers().draw_task_flowchart(gui)

    assert flow.charted == ["3"], "the lowest id of the two"
    assert any("More than one Task is named 'Wake Up'" in message for message, _ in seen.notified)
    assert flow.popped == [("/popout/flow", True)]
    shown = [c.args[0] for c in gui.display_message_box.call_args_list]
    assert "Flowchart saved as /out/flow.html" in shown
    assert "Task Flow View opened in a new browser window." in shown


def test_a_chart_that_could_not_be_written_is_still_opened_from_the_run_state(
    seen: SimpleNamespace, flow: SimpleNamespace
) -> None:
    flow.scope = SimpleNamespace(label="Task", name="Wake Up", tasks={"7"})
    flow.chart_file = ""
    gui = MagicMock(spec=["display_message_box"])

    _handlers().draw_task_flowchart(gui)

    assert flow.popped == [("/popout/flow", False)]
    assert [c.args[0] for c in gui.display_message_box.call_args_list] == [
        "Task Flow View opened in a new browser window."
    ]


# ##################################################################################
# Clearing search highlights
# ##################################################################################
def test_clear_unhighlights_every_open_view(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[str] = []
    userintr.ui.run_javascript = ran.append
    monkeypatch.setattr(userintr.assettext, "render", lambda name, **values: f"js:{values['SCROLL_AREA_ID']}")
    full = SimpleNamespace(
        search_input=MagicMock(), invalidate_search_cache=MagicMock(), scroll_area=SimpleNamespace(id=5)
    )
    bare = SimpleNamespace()
    monkeypatch.setattr(userintr, "live_views", lambda gui: [full, bare])

    _handlers().clear_event()

    full.search_input.set_value.assert_called_once_with("")
    full.invalidate_search_cache.assert_called_once()
    assert ran == ["js:5"]
    assert [m for m, _ in seen.notified] == ["Cleared the search highlights."] * 2


# ##################################################################################
# Upgrading
# ##################################################################################
@pytest.fixture
def upgrade(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(result=(True, ""), changelog=[], reloaded=[])
    monkeypatch.setattr(userintr, "update_maptasker", lambda: record.result)
    monkeypatch.setattr(userintr, "create_changelog", lambda: record.changelog.append(True))
    monkeypatch.setattr(userintr, "reload_gui", lambda gui: record.reloaded.append(gui))
    return record


def test_a_successful_upgrade_writes_the_changelog_and_restarts(
    seen: SimpleNamespace, upgrade: SimpleNamespace
) -> None:
    handlers = _handlers()

    handlers.upgrade_event()

    assert upgrade.changelog == [True] and upgrade.reloaded == [handlers.gui]
    assert _gui(handlers).display_message_box.call_args.args == ("Program updated.  Restarting...", "Green")


def test_a_failed_upgrade_says_so_with_the_installers_last_lines_and_stays_put(
    seen: SimpleNamespace, upgrade: SimpleNamespace
) -> None:
    upgrade.result = (False, "line1\nline2\nline3\nline4")
    handlers = _handlers()

    handlers.upgrade_event()

    said = [c.args[0] for c in _gui(handlers).display_message_box.call_args_list]
    assert said[0].startswith("The update failed")
    assert said[1] == "line2\nline3\nline4"
    assert "pip install --upgrade maptasker" in said[2]
    assert upgrade.reloaded == [] and upgrade.changelog == []


def test_a_failed_upgrade_with_no_output_does_not_print_an_empty_box(
    seen: SimpleNamespace, upgrade: SimpleNamespace
) -> None:
    upgrade.result = (False, "")
    handlers = _handlers()

    handlers.upgrade_event()

    assert _gui(handlers).display_message_box.call_count == 2


# ##################################################################################
# The browser pages
# ##################################################################################
@pytest.mark.parametrize("event", ["coffee_event", "report_issue_event"])
def test_a_browser_that_cannot_open_the_page_says_so(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, event: str
) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise userintr.webbrowser.Error("no browser")

    monkeypatch.setattr(userintr.webbrowser, "open", refuse)
    handlers = _handlers()

    getattr(handlers, event)()

    assert _gui(handlers).display_message_box.call_args.args == (
        "Error: Failed to open output in browser: your browser is not supported.",
        "Red",
    )


def test_reporting_an_issue_opens_the_issues_page_and_says_what_to_do_there(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(userintr.webbrowser, "open", lambda url, new=0: opened.append(url))
    handlers = _handlers()

    handlers.report_issue_event()

    assert opened == ["https://github.com/mctinker/Map-Tasker/issues"]
    assert "Go to your browser and create a new issue" in _gui(handlers).display_message_box.call_args.args[0]


def test_the_coffee_button_opens_the_support_page(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(userintr.webbrowser, "open", lambda url, new=0: opened.append(url))

    _handlers().coffee_event()

    assert opened == ["https://www.buymeacoffee.com/mctinker"]


# ##################################################################################
# Help and What's New
# ##################################################################################
@pytest.fixture
def popups(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(userintr, "create_popup_window", lambda title, text, **kw: shown.append((title, text)))
    monkeypatch.setattr(userintr, "get_changelog_file", lambda url, marker, count: ["## 15.0.2", "- Fixed: something"])
    return shown


@pytest.mark.parametrize(
    ("query", "title"),
    [
        ("viewlimit", "View Limit Help"),
        ("view", "Views Help"),
        ("ai", "Ai Analyze Help"),
        ("listfile", "List Android Files Help"),
        ("apikey", "API Key Help"),
    ],
)
def test_each_help_button_opens_its_own_screen(popups: list[tuple[str, str]], query: str, title: str) -> None:
    _handlers().query_event(query)

    assert popups[0][0] == title and popups[0][1]


def test_the_main_help_screen_carries_the_changelog_after_the_help(popups: list[tuple[str, str]]) -> None:
    _handlers().query_event("HELP")

    assert popups[0][1].endswith("## 15.0.2\n- Fixed: something")


def test_an_unknown_query_says_there_is_no_help(popups: list[tuple[str, str]]) -> None:
    _handlers().query_event("nonsense")

    assert popups == [("", "No help available for this query.")]


def test_whats_new_lists_the_latest_versions_and_says_how_many(popups: list[tuple[str, str]]) -> None:
    _handlers().whatsnew_event()

    assert popups[0][0] == "What's New?"
    assert popups[0][1].startswith("## 15.0.2\n- Fixed: something")
    assert "End of changelog. The latest 10 versions displayed." in popups[0][1]


def test_whats_new_with_no_changelog_says_it_could_not_be_read(
    popups: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(userintr, "get_changelog_file", lambda url, marker, count: [])

    _handlers().whatsnew_event()

    assert popups == [("What's New?", "An error occurred reading the changelog file.")]
