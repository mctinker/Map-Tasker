"""The Map, Diagram, Misc and Tree buttons: getting the run ready, building, opening the window, and the ways it stops.

What a Map or a Diagram contains is mapgen's.  Here it is what pressing the button does around the build: the
state every build starts from, which view the name picks, the Map's two checks after the build (a halt, an error
code), the view limit's truncation notice, the Diagram's, Tree's and Misc's own early exits, Clear, and the
rebuild a clicked report finding falls back to -- with the settings it went past put back afterwards.

The window is a mock; the builders, the popout and the worker thread the build runs on are replaced by recorders.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from maptasker.src.core import mapjump
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import userintr, userintr_prebuild
from maptasker.src.gui.userintr import MapTaskerEventHandlers


def _handlers(**window: Any) -> MapTaskerEventHandlers:
    gui = MagicMock()
    gui.state = RunState()
    gui.state.output_lines = SimpleNamespace(output_lines=["a line"])
    gui.view_limit = 10000
    gui.open_view_in_new_window = False
    for name, value in window.items():
        setattr(gui, name, value)
    return MapTaskerEventHandlers(gui)


def _said(handlers: MapTaskerEventHandlers) -> list[tuple[str, str]]:
    return [(c.args[0], c.args[1]) for c in _gui(handlers).display_message_box.call_args_list]


def _gui(handlers: MapTaskerEventHandlers) -> MagicMock:
    """The window the handlers were given, which is a mock in these tests."""
    return cast("MagicMock", handlers.gui)


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(
        notified=[], popped=[], built=[], outlined=[], front=[], cleared=[], banners=[], raises=None, js=[]
    )
    ui = MagicMock()
    ui.notify = lambda message, **kw: record.notified.append((message, kw.get("type")))
    ui.run_javascript = record.js.append
    monkeypatch.setattr(userintr, "ui", ui)
    monkeypatch.setattr(userintr, "_open_popout_window", lambda path, new: record.popped.append((path, new)))
    monkeypatch.setattr(userintr, "_busy_banner", lambda message: record.banners.append(message) or "banner")
    monkeypatch.setattr(userintr, "_clear_busy_banner", lambda banner: record.banners.append(("cleared", banner)))
    monkeypatch.setattr(userintr, "clear_error", lambda: record.cleared.append(True))
    monkeypatch.setattr(userintr, "current_config", lambda: "config")
    monkeypatch.setattr(userintr, "output_the_front_matter", lambda config, state: record.front.append(config))
    monkeypatch.setattr(userintr, "output_path", lambda name, state: f"/out/{name}")

    def build_html(name: str, state: object) -> int:
        record.built.append(name)
        if record.raises is not None:
            raise record.raises
        return 0

    def outline(state: object) -> None:
        record.outlined.append(True)

    async def io_bound(function: Any, *args: object, **kwargs: object) -> object:
        return function(*args, **kwargs)

    monkeypatch.setattr(userintr, "build_html", build_html)
    monkeypatch.setattr(userintr, "outline_the_configuration", outline)
    monkeypatch.setattr(userintr.run, "io_bound", io_bound)
    return record


# ##################################################################################
# Which view
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("view", "called"),
    [
        ("map", "_view_map"),
        ("diagram", "_view_diagram"),
        ("misc", "_view_misc"),
        ("tree", "_view_tree"),
        ("x", "_view_invalid"),
    ],
)
async def test_the_name_picks_the_view(seen: SimpleNamespace, view: str, called: str) -> None:
    handlers = _handlers()
    chosen: list[str] = []

    def sync(name: str):
        return lambda *a, **k: chosen.append(name)

    def asynchronous(name: str):
        async def stand_in(*a: object, **k: object) -> None:
            chosen.append(name)

        return stand_in

    handlers._view_map = asynchronous("_view_map")  # type: ignore[method-assign]
    handlers._view_diagram = asynchronous("_view_diagram")  # type: ignore[method-assign]
    for name in ("_view_misc", "_view_tree", "_view_invalid"):
        setattr(handlers, name, sync(name))

    await handlers._show_the_view(view, "Title", "")

    assert chosen == [called]


# ##################################################################################
# The state every build starts from
# ##################################################################################
def test_a_build_starts_from_the_windows_settings_with_the_overrides_on_top(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[object] = []
    reset: list[tuple[str, ...]] = []
    monkeypatch.setattr(userintr, "capture_gui_state", lambda gui, data, state: captured.append(data))
    monkeypatch.setattr(userintr, "reset_attributes", lambda *names: reset.append(names))
    handlers = _handlers(view_limit=2500)
    handlers.state.found_named_items = {"single_task_found": True}

    handlers.get_ready_to_build({"display_detail_level": 4})

    assert handlers.state.view_limit == 2500
    assert captured == [{}]
    assert handlers.state.program_arguments.display_detail_level == 4, (
        "the overrides go on after the capture overwrites"
    )
    assert not any(handlers.state.found_named_items.values()), "no single item is already 'found' from the last run"
    assert reset, "the directory, totals and anchors left by the last build are emptied"


def test_a_window_with_no_view_limit_yet_builds_with_the_default(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(userintr, "capture_gui_state", lambda *a, **k: None)
    monkeypatch.setattr(userintr, "reset_attributes", lambda *names: None)
    gui = MagicMock(spec=["state"])
    gui.state = RunState()
    handlers = MapTaskerEventHandlers(gui)

    handlers.get_ready_to_build(None)

    assert handlers.state.view_limit == userintr.VIEW_LIMIT_DEFAULT


# ##################################################################################
# Map
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_the_map_asks_for_a_file(seen: SimpleNamespace) -> None:
    handlers = _handlers()

    await handlers._view_map("Map View", "")

    assert _said(handlers) == [("No XML data loaded! Please select a valid XML file first.", "Orange")]
    assert seen.built == []


def _loaded(handlers: MapTaskerEventHandlers, lines: int = 5) -> None:
    handlers.state.xml_root = object()  # type: ignore[assignment]
    handlers.state.map_output_line_count = lines
    handlers.state.error_code = 0


@pytest.mark.asyncio
async def test_a_map_is_built_opened_with_its_jump_and_scope_and_the_banner_comes_down(seen: SimpleNamespace) -> None:
    handlers = _handlers()
    _loaded(handlers)
    handlers.state.program_arguments.single_project_name = "Home"

    await handlers._view_map("Map View", "T7")

    assert seen.built == [""] and seen.front == ["config"]
    assert seen.popped == [("/popout/map?goto=T7&scope=Home", False)]
    assert handlers.state.output_lines.output_lines == [], "the memory is freed once the Map is on its way"
    assert ("Map View opened in a new browser window.", "Green") in _said(handlers)
    assert ("Map saved to /out/MapTasker.html", "Green") in _said(handlers)
    assert seen.banners[-1] == ("cleared", "banner")


@pytest.mark.asyncio
async def test_a_map_longer_than_the_view_limit_says_it_was_truncated(seen: SimpleNamespace) -> None:
    handlers = _handlers(view_limit=3)
    _loaded(handlers, lines=50)

    await handlers._view_map("Map View", "")

    assert ("Map view truncated 50 lines to 3 lines due to view limit.", "Orange") in _said(handlers)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "message", "colour"),
    [
        (6, "Map view creation skipped: No valid XML source found or action canceled.", "Orange"),
        (12, "Map processing halted with system code: 12", "Red"),
    ],
)
async def test_a_build_that_halts_says_why_and_still_clears_the_banner(
    seen: SimpleNamespace, code: int, message: str, colour: str
) -> None:
    seen.raises = MapTaskerError("stop", code)
    handlers = _handlers()
    _loaded(handlers)

    await handlers._view_map("Map View", "")

    assert _said(handlers) == [(message, colour)]
    assert seen.popped == []
    assert seen.banners[-1] == ("cleared", "banner")


@pytest.mark.asyncio
async def test_a_build_that_finishes_with_an_error_code_reports_it_and_clears_it(seen: SimpleNamespace) -> None:
    handlers = _handlers()
    _loaded(handlers)
    handlers.state.error_code = 4
    handlers.state.error_msg = "bad action"

    await handlers._view_map("Map View", "")

    assert _said(handlers) == [("Map processing error: bad action", "Orange")]
    assert seen.popped == []
    assert len(seen.cleared) == 2, "cleared before the build, and again once the error has been reported"


# ##################################################################################
# Diagram
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_the_diagram_asks_for_a_file(seen: SimpleNamespace) -> None:
    handlers = _handlers()
    handlers.state.tasker_root_elements = {"all_projects": {}, "all_profiles": {}}

    await handlers._view_diagram()

    assert _said(handlers) == [("No XML data loaded! Please select a valid XML file first.", "Orange")]
    assert seen.outlined == []


def _diagram_ready(handlers: MapTaskerEventHandlers, monkeypatch: pytest.MonkeyPatch) -> None:
    handlers.state.tasker_root_elements = {"all_projects": {"1": {}}, "all_profiles": {}}
    handlers.state.error_code = 0
    handlers.state.diagram_limit_msg = ""
    monkeypatch.setattr(userintr.mapjump, "current_scope", lambda state: SimpleNamespace(phrase="Task Wake Up"))


@pytest.mark.asyncio
async def test_a_diagram_is_outlined_and_opened_with_what_it_was_built_for(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    _diagram_ready(handlers, monkeypatch)

    await handlers._view_diagram()

    assert seen.outlined == [True]
    assert seen.popped == [("/popout/diagram?built_for=Task+Wake+Up", False)]
    assert ("Diagram View opened in a new browser window.", "Green") in _said(handlers)


@pytest.mark.asyncio
async def test_a_diagram_cut_short_at_the_view_limit_says_so(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    _diagram_ready(handlers, monkeypatch)
    handlers.state.diagram_limit_msg = "Stopped at line 5000."

    await handlers._view_diagram()

    assert ("Stopped at line 5000.", "Orange") in _said(handlers)


@pytest.mark.asyncio
async def test_a_diagram_whose_outline_failed_does_not_reopen_the_stale_one(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    _diagram_ready(handlers, monkeypatch)
    handlers.state.error_code = 2
    handlers.state.error_msg = "view limit"

    await handlers._view_diagram()

    assert _said(handlers) == [
        ("The 'Diagram' view is running in the background.  Please stand by...", "Green"),
        ("Diagram processing error: view limit", "Orange"),
    ]
    assert seen.popped == []


# ##################################################################################
# Misc, Tree and the view that is not one
# ##################################################################################
def test_misc_opens_a_text_view_that_finds_its_own_content(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    made: list[tuple[str, list[object]]] = []
    monkeypatch.setattr(
        userintr, "NiceGuiTextView", lambda gui, title, the_data: made.append((title, the_data)) or "view"
    )
    handlers = _handlers()

    handlers._view_misc()

    assert made == [("Misc View", [])] and handlers.gui.textview == "view"


def test_a_tree_of_projects_opens_a_tree_view(seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[object] = []
    monkeypatch.setattr(userintr, "NiceGuiTreeView", lambda gui, title, items: made.append((title, items)) or "tree")
    handlers = _handlers()
    _gui(handlers).build_the_tree.return_value = [{"id": "Home"}]

    handlers._view_tree()

    assert made == [("Tree View", [{"id": "Home"}])] and handlers.gui.textview == "tree"


def test_a_tree_with_no_projects_says_so(seen: SimpleNamespace) -> None:
    handlers = _handlers()
    _gui(handlers).build_the_tree.return_value = []

    handlers._view_tree()

    assert _said(handlers) == [("No Project(s) Found in XML!", "Red")]


def test_a_view_that_is_not_one_is_said_to_be_invalid(seen: SimpleNamespace) -> None:
    handlers = _handlers()

    handlers._view_invalid()

    assert _said(handlers) == [("Invalid view type specified. Use 'map', 'diagram', or 'tree'.", "Red")]
    assert seen.notified[0][1] == "warning"


# ##################################################################################
# Clear
# ##################################################################################
def test_clear_empties_the_window_forgets_the_views_and_closes_the_popouts(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    forgotten: list[object] = []
    monkeypatch.setattr(userintr, "forget_views", forgotten.append)
    monkeypatch.setattr(userintr.mapjump, "close_popouts_js", lambda: "close()")
    handlers = _handlers()

    handlers.clear_view_event()

    _gui(handlers).content_container.clear.assert_called_once()
    assert forgotten == [handlers.gui]
    assert seen.js == ["close()"]
    assert seen.notified == [("View cleared.", "info")]


def test_clear_with_no_content_container_still_closes_the_popouts(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(userintr, "forget_views", lambda gui: None)
    monkeypatch.setattr(userintr.mapjump, "close_popouts_js", lambda: "close()")
    handlers = _handlers(content_container=None)

    handlers.clear_view_event()

    assert seen.js == ["close()"]


# ##################################################################################
# view_event, the whole press
# ##################################################################################
@pytest.mark.asyncio
async def test_a_press_prepares_marks_the_event_and_counts_the_view_while_it_is_built(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers = _handlers()
    ready = MagicMock()
    handlers.get_ready_to_build = ready  # type: ignore[method-assign]
    during: list[int] = []

    async def show(view: str, title: str, goto: str) -> None:
        during.append(userintr_prebuild._building.views)
        assert (view, title, goto) == ("map", "Map View", "T9")

    handlers._show_the_view = show  # type: ignore[method-assign]

    await handlers.view_event("map", goto="T9", overrides={"x": 1})

    assert handlers.gui.event is True
    ready.assert_called_once_with({"x": 1})
    assert during == [1]


# ##################################################################################
# The rebuild a clicked finding falls back to
# ##################################################################################
class _Held:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_exc: object) -> None:
        return None


@pytest.mark.asyncio
async def test_a_jump_builds_the_owning_projects_map_at_the_needed_level_and_puts_the_settings_back(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = mapjump.Target(kind=mapjump.TASK, key="7", name="Wake Up")
    monkeypatch.setattr(userintr.mapjump, "minimum_detail_level", lambda t: 5)
    monkeypatch.setattr(userintr.mapjump, "scope_for", lambda t: "Home")
    monkeypatch.setattr(userintr.mapjump, "needs_taskernet", lambda t: True)
    monkeypatch.setattr(userintr, "held_overrides", lambda overrides, state: _Held())
    handlers = _handlers()
    handlers.state.program_arguments.display_detail_level = 2
    handlers.state.program_arguments.single_project_name = "Mine"
    handlers.state.program_arguments.taskernet = False
    seen_during: dict[str, object] = {}

    async def view_event(view: str, goto: str = "", overrides: dict | None = None) -> None:
        seen_during.update(view=view, goto=goto, **(overrides or {}))
        handlers.state.program_arguments.update(overrides or {})

    handlers.view_event = view_event  # type: ignore[method-assign]

    await handlers.rebuild_map_for_jump(target)

    assert seen_during["view"] == "map" and seen_during["goto"] == target.token()
    assert seen_during["display_detail_level"] == 5 and seen_during["single_project_name"] == "Home"
    assert seen_during["taskernet"] is True
    assert handlers.state.program_arguments.display_detail_level == 2, "the user's own settings are put straight back"
    assert handlers.state.program_arguments.single_project_name == "Mine"
    assert handlers.state.program_arguments.taskernet is False
    message = seen.notified[0][0]
    assert "Project 'Home'" in message and "detail level 5" in message and "TaskerNet information" in message


@pytest.mark.asyncio
async def test_a_jump_for_an_object_in_no_project_builds_the_whole_file_and_says_which_settings_it_went_past(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = mapjump.Target(kind=mapjump.PROFILE, key="3", name="Orphan")
    monkeypatch.setattr(userintr.mapjump, "minimum_detail_level", lambda t: 3)
    monkeypatch.setattr(userintr.mapjump, "scope_for", lambda t: "")
    monkeypatch.setattr(userintr.mapjump, "needs_taskernet", lambda t: False)
    monkeypatch.setattr(userintr, "held_overrides", lambda overrides, state: _Held())
    handlers = _handlers()
    handlers.state.program_arguments.display_detail_level = 3
    handlers.state.program_arguments.single_project_name = "Mine"
    handlers.view_event = AsyncMock()  # type: ignore[method-assign]

    await handlers.rebuild_map_for_jump(target)

    message = seen.notified[0][0]
    assert "whole file" in message and "detail level" not in message, "the level was already enough"


@pytest.mark.asyncio
async def test_a_jump_from_a_user_already_on_that_project_and_level_is_told_nothing_extra(
    seen: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = mapjump.Target(kind=mapjump.TASK, key="7", name="Wake Up")
    monkeypatch.setattr(userintr.mapjump, "minimum_detail_level", lambda t: 3)
    monkeypatch.setattr(userintr.mapjump, "scope_for", lambda t: "Home")
    monkeypatch.setattr(userintr.mapjump, "needs_taskernet", lambda t: False)
    monkeypatch.setattr(userintr, "held_overrides", lambda overrides, state: _Held())
    handlers = _handlers()
    pa = handlers.state.program_arguments
    pa.display_detail_level, pa.single_project_name = 3, "Home"
    for key in userintr.SELECTION_KEYS:
        if key != "single_project_name":
            pa[key] = ""
    handlers.view_event = AsyncMock()  # type: ignore[method-assign]

    await handlers.rebuild_map_for_jump(target)

    message = seen.notified[0][0]
    assert message.endswith("(id 7) ...") and "detail level" not in message and "Project 'Home'" not in message
