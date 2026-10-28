"""Pre-Build The Map: the handlers that build the Map ahead of time, and how a press of the button treats one.

Nothing here needs a browser.  What is asserted is when a build is started (and when it is not), what is
done with the Map it makes, and that a press of Map or Diagram while one is under way waits for it
before it touches the run state the two share.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maptasker.src.gui import userintr_prebuild
from maptasker.src.gui.userintr import MapTaskerEventHandlers
from maptasker.src.gui.userintr_prebuild import PrebuildEventHandlers, _building


def _state(**changes: Any) -> SimpleNamespace:
    """A run state with a loaded configuration and nothing in the way."""
    state = SimpleNamespace(
        program_arguments=SimpleNamespace(ai_analyze=False, rerun=False),
        tasker_root_elements={"all_projects": {}, "all_profiles": {}, "all_tasks": {"20": {"name": "Task"}}},
        xml_root=object(),
        error_code=0,
        output_lines=SimpleNamespace(output_lines=["leftover"]),
    )
    for name, value in changes.items():
        setattr(state, name, value)
    return state


class _Handlers(PrebuildEventHandlers):
    """The pre-build handlers with a window that has the box ticked, and the preparation stubbed."""

    def __init__(self, state: SimpleNamespace, *, ticked: bool = True) -> None:
        self.prepared: list[object] = []
        hub = SimpleNamespace(
            state=state,
            gui=SimpleNamespace(prebuild_map=ticked),
            get_ready_to_build=self.prepared.append,
            prebuild=self,
        )
        super().__init__(hub)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _nothing_building() -> Iterator[None]:
    """What the handlers agree on is the program's, so each test starts with nothing under way."""
    _building.task = _building.built_for = _building.seen = None
    _building.views = 0
    yield
    _building.task = _building.built_for = _building.seen = None
    _building.views = 0


@pytest.fixture
def seen() -> Iterator[SimpleNamespace]:
    """Everything the build touches, replaced and recorded.  `edits` is what the undo history reports."""
    record = SimpleNamespace(built=[], settled=[], forgotten=[], cleared=[], edits=[("one", 1)], build=None)

    async def io_bound(function, *args, **kwargs):
        return function(*args, **kwargs)

    def build_html(file_to_get: str, state: object) -> int:
        record.built.append(file_to_get)
        if record.build is not None:
            record.build()
        return 0

    with (
        patch.object(userintr_prebuild, "build_html", build_html),
        patch.object(userintr_prebuild, "output_the_front_matter", MagicMock()),
        patch.object(userintr_prebuild, "current_config", MagicMock()),
        patch.object(userintr_prebuild, "output_path", lambda name, state: f"/out/{name}"),
        patch.object(userintr_prebuild, "clear_error", lambda *_a, **_k: record.cleared.append(True)),
        patch.object(userintr_prebuild.run, "io_bound", io_bound),
        patch.object(userintr_prebuild.sessundo, "history", lambda state: list(record.edits)),
        patch.object(userintr_prebuild.mapcache, "digests", lambda state: ("config", "settings")),
        patch.object(
            userintr_prebuild.mapcache,
            "settle",
            lambda path, now: record.settled.append((path, now)) or True,
        ),
        patch.object(userintr_prebuild.mapcache, "forget", lambda: record.forgotten.append(True)),
    ):
        yield record


async def _look_until_started(handlers: _Handlers) -> None:
    """Look twice, which is what it takes, and let the build run to its end."""
    handlers.prebuild_tick()
    handlers.prebuild_tick()
    if _building.task is not None:
        await _building.task


# ##################################################################################
# When a build is started
# ##################################################################################
@pytest.mark.asyncio
async def test_a_loaded_configuration_is_built_for_on_the_second_look(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state())

    handlers.prebuild_tick()
    assert _building.task is None, "a configuration was built for the moment it was seen"

    handlers.prebuild_tick()
    assert _building.task is not None
    await _building.task
    assert seen.built == [""]


@pytest.mark.asyncio
async def test_nothing_is_built_with_the_box_unticked(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state(), ticked=False)

    await _look_until_started(handlers)

    assert _building.task is None
    assert seen.built == []


@pytest.mark.asyncio
async def test_nothing_is_built_before_a_file_is_loaded(seen: SimpleNamespace) -> None:
    for state in (
        _state(xml_root=None),
        _state(tasker_root_elements={"all_projects": {}, "all_profiles": {}, "all_tasks": {}}),
    ):
        handlers = _Handlers(state)

        await _look_until_started(handlers)

        assert _building.task is None
    assert seen.built == []


@pytest.mark.asyncio
@pytest.mark.parametrize("argument", ["ai_analyze", "rerun"])
async def test_nothing_is_built_while_the_run_is_about_something_else(seen: SimpleNamespace, argument: str) -> None:
    state = _state()
    setattr(state.program_arguments, argument, True)
    handlers = _Handlers(state)

    await _look_until_started(handlers)

    assert _building.task is None


@pytest.mark.asyncio
async def test_nothing_is_built_while_a_view_is_being_built_for_the_user(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state())
    _building.views = 1

    await _look_until_started(handlers)
    assert _building.task is None

    _building.views = 0
    await _look_until_started(handlers)
    assert seen.built == [""], "the view finishing did not let the build go ahead"


@pytest.mark.asyncio
async def test_a_load_that_changes_under_the_looks_is_waited_out(seen: SimpleNamespace) -> None:
    """Seen twice means the same one twice: a different configuration starts the count again."""
    state = _state()
    handlers = _Handlers(state)

    handlers.prebuild_tick()
    state.xml_root = object()
    handlers.prebuild_tick()
    assert _building.task is None

    handlers.prebuild_tick()
    assert _building.task is not None
    await _building.task


@pytest.mark.asyncio
async def test_a_configuration_is_built_for_once_and_a_new_one_again(seen: SimpleNamespace) -> None:
    state = _state()
    handlers = _Handlers(state)
    await _look_until_started(handlers)

    await _look_until_started(handlers)
    assert seen.built == [""], "the same configuration was built for twice"

    state.xml_root = object()  # Another file, or an Undo.
    await _look_until_started(handlers)
    assert seen.built == ["", ""]


@pytest.mark.asyncio
async def test_ticking_the_box_after_the_file_is_loaded_builds_then(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state(), ticked=False)
    await _look_until_started(handlers)
    assert seen.built == []

    handlers.gui.prebuild_map = True
    await _look_until_started(handlers)

    assert seen.built == [""]


@pytest.mark.asyncio
async def test_ticking_the_box_again_builds_the_same_configuration_again(seen: SimpleNamespace) -> None:
    """A setting changed since means the Map built before is not the one a press would take."""
    handlers = _Handlers(_state())
    await _look_until_started(handlers)
    assert seen.built == [""]

    handlers.gui.prebuild_map = False
    await _look_until_started(handlers)
    assert seen.built == [""], "unticking the box built something"

    handlers.gui.prebuild_map = True
    await _look_until_started(handlers)
    assert seen.built == ["", ""]


@pytest.mark.asyncio
async def test_two_windows_that_disagree_about_the_box_do_not_build_in_circles(seen: SimpleNamespace) -> None:
    state = _state()
    ticked, unticked = _Handlers(state, ticked=True), _Handlers(state, ticked=False)

    for _ in range(4):
        await _look_until_started(ticked)
        await _look_until_started(unticked)

    assert seen.built == [""]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item", ["single_project_name", "single_profile_name", "single_task_name", "single_scene_name"]
)
async def test_choosing_a_single_item_builds_again(seen: SimpleNamespace, item: str) -> None:
    handlers = _Handlers(_state())
    await _look_until_started(handlers)
    assert seen.built == [""]

    setattr(handlers.gui, item, "Home")
    await _look_until_started(handlers)

    assert seen.built == ["", ""]


@pytest.mark.asyncio
async def test_going_back_to_nothing_selected_builds_again(seen: SimpleNamespace) -> None:
    """The cache holds one Map, and the Map of one Project is not the Map of the whole file."""
    handlers = _Handlers(_state())
    await _look_until_started(handlers)
    handlers.gui.single_project_name = "Home"
    await _look_until_started(handlers)

    handlers.gui.single_project_name = ""
    await _look_until_started(handlers)

    assert seen.built == ["", "", ""]


@pytest.mark.asyncio
async def test_the_same_selection_is_built_for_once(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state())
    handlers.gui.single_task_name = "Wake Up"

    await _look_until_started(handlers)
    await _look_until_started(handlers)
    await _look_until_started(handlers)

    assert seen.built == [""]


@pytest.mark.asyncio
async def test_a_selection_still_being_made_is_waited_out(seen: SimpleNamespace) -> None:
    """Seen twice means the same selection twice: one that changes under the looks starts the count again."""
    handlers = _Handlers(_state())
    await _look_until_started(handlers)
    seen.built.clear()

    handlers.gui.single_project_name = "Home"
    handlers.prebuild_tick()
    handlers.gui.single_project_name = "Away"
    handlers.prebuild_tick()
    assert _building.task is None or _building.task.done()
    assert seen.built == []

    handlers.prebuild_tick()
    assert _building.task is not None
    await _building.task
    assert seen.built == [""]


@pytest.mark.asyncio
async def test_nothing_is_built_for_a_selection_made_with_the_box_unticked(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state(), ticked=False)
    handlers.gui.single_project_name = "Home"

    await _look_until_started(handlers)

    assert seen.built == []


@pytest.mark.asyncio
async def test_a_selection_changed_during_the_build_is_not_vouched_for(seen: SimpleNamespace) -> None:
    """The build reads the selection as it goes, so what it made is neither Map."""
    handlers = _Handlers(_state())
    seen.build = lambda: setattr(handlers.gui, "single_project_name", "Home")

    await _look_until_started(handlers)

    assert seen.settled == []
    assert seen.forgotten == [True]


@pytest.mark.asyncio
async def test_the_selection_changed_during_a_build_is_built_for_afterwards(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state())
    seen.build = lambda: setattr(handlers.gui, "single_project_name", "Home")
    await _look_until_started(handlers)
    seen.build = None

    await _look_until_started(handlers)

    assert seen.built == ["", ""]
    assert len(seen.settled) == 1, "the Map for the selection it ended on was not handed to the press"


# ##################################################################################
# What is done with what it built
# ##################################################################################
@pytest.mark.asyncio
async def test_a_build_prepares_as_a_press_does_and_hands_the_press_its_map(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state())

    await _look_until_started(handlers)

    assert handlers.prepared == [None, None], "prepared once before the build and once for the settings after"
    assert seen.settled == [("/out/MapTasker.html", ("config", "settings"))]
    assert seen.forgotten == []


@pytest.mark.asyncio
async def test_the_output_lines_are_not_left_behind(seen: SimpleNamespace) -> None:
    state = _state()
    handlers = _Handlers(state)

    await _look_until_started(handlers)

    assert state.output_lines.output_lines == []


@pytest.mark.asyncio
async def test_a_map_is_not_vouched_for_when_the_configuration_was_edited_meanwhile(seen: SimpleNamespace) -> None:
    handlers = _Handlers(_state())
    seen.build = lambda: seen.edits.append(("Rename a Task", 2))

    await _look_until_started(handlers)

    assert seen.settled == []
    assert seen.forgotten == [True]


@pytest.mark.asyncio
async def test_a_map_is_not_vouched_for_when_another_file_was_loaded_meanwhile(seen: SimpleNamespace) -> None:
    state = _state()
    handlers = _Handlers(state)
    seen.build = lambda: setattr(state, "xml_root", object())

    await _look_until_started(handlers)

    assert seen.settled == []
    assert seen.forgotten == [True]


@pytest.mark.asyncio
async def test_a_map_is_not_vouched_for_when_another_file_was_read_in_meanwhile(seen: SimpleNamespace) -> None:
    """Reading a second file borrows the tables and the output lines the build is reading."""
    handlers = _Handlers(_state())
    windows = [0]
    seen.build = lambda: windows.__setitem__(0, windows[0] + 1)

    with patch.object(userintr_prebuild.diffload, "isolation_windows", lambda: windows[0]):
        await _look_until_started(handlers)

    assert seen.settled == []
    assert seen.forgotten == [True]


@pytest.mark.asyncio
async def test_a_build_that_reported_an_error_is_dropped(seen: SimpleNamespace) -> None:
    state = _state()
    handlers = _Handlers(state)
    seen.build = lambda: setattr(state, "error_code", 3)

    await _look_until_started(handlers)

    assert seen.cleared == [True]
    assert seen.settled == []
    assert seen.forgotten == [True]


@pytest.mark.asyncio
async def test_a_build_that_raised_is_dropped_and_says_nothing(seen: SimpleNamespace) -> None:
    state = _state()
    handlers = _Handlers(state)

    def fail() -> None:
        raise RuntimeError("the configuration changed under the build")

    seen.build = fail

    await _look_until_started(handlers)

    assert seen.settled == []
    assert seen.forgotten == [True]
    assert state.output_lines.output_lines == []
    assert not handlers.prebuild_running()


# ##################################################################################
# A press while it is building
# ##################################################################################
@pytest.mark.asyncio
async def test_waiting_for_a_build_that_is_not_there_returns_at_once() -> None:
    handlers = _Handlers(_state())

    await asyncio.wait_for(handlers.wait_for_prebuild(), timeout=1)

    assert not handlers.prebuild_running()


@pytest.mark.asyncio
async def test_a_wait_that_is_given_up_does_not_stop_the_build() -> None:
    handlers = _Handlers(_state())
    release = asyncio.Event()

    async def slow() -> None:
        await release.wait()

    _building.task = asyncio.create_task(slow())
    waiter = asyncio.create_task(handlers.wait_for_prebuild())
    await asyncio.sleep(0)
    waiter.cancel()
    await asyncio.sleep(0)

    assert handlers.prebuild_running(), "giving up the wait cancelled the build"
    release.set()
    await _building.task


def _event_handlers() -> MapTaskerEventHandlers:
    """The real event handlers over a mock window, with everything view_event does after the wait stubbed."""
    window = MagicMock()
    window.state = _state()
    handlers = MapTaskerEventHandlers(window)
    handlers.get_ready_to_build = MagicMock()  # type: ignore[method-assign]
    handlers._show_the_view = AsyncMock()  # type: ignore[method-assign]
    return handlers


@pytest.mark.asyncio
async def test_a_press_waits_for_the_build_before_it_touches_the_run_state() -> None:
    handlers = _event_handlers()
    release = asyncio.Event()
    order: list[str] = []

    async def prebuilding() -> None:
        await release.wait()
        order.append("the build finished")

    _building.task = asyncio.create_task(prebuilding())
    handlers.get_ready_to_build.side_effect = lambda _overrides: order.append("the press prepared")  # type: ignore[attr-defined]

    with patch("maptasker.src.gui.userintr._busy_banner", return_value=None):
        press = asyncio.create_task(handlers.view_event("map"))
        await asyncio.sleep(0.01)
        assert order == [], "the press went ahead while the build was under way"
        release.set()
        await press

    assert order == ["the build finished", "the press prepared"]
    handlers._show_the_view.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_press_with_no_build_under_way_does_not_wait_or_put_up_a_banner() -> None:
    handlers = _event_handlers()

    with patch("maptasker.src.gui.userintr._busy_banner") as banner:
        await asyncio.wait_for(handlers.view_event("map"), timeout=1)

    banner.assert_not_called()
    handlers.get_ready_to_build.assert_called_once_with(None)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_view_being_built_is_counted_for_exactly_as_long_as_it_takes() -> None:
    handlers = _event_handlers()
    during: list[int] = []

    async def show(*_args: Any) -> None:
        during.append(_building.views)

    handlers._show_the_view = show  # type: ignore[method-assign]

    await handlers.view_event("map")

    assert during == [1]
    assert _building.views == 0


@pytest.mark.asyncio
async def test_the_count_comes_down_when_the_view_fails() -> None:
    handlers = _event_handlers()
    handlers._show_the_view = AsyncMock(side_effect=RuntimeError("no"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await handlers.view_event("map")

    assert _building.views == 0


# ##################################################################################
# The setting
# ##################################################################################
def test_the_setting_is_saved_and_off_by_default() -> None:
    from maptasker.src.core.initparg import ProgramArguments
    from maptasker.src.core.sysconst import ARGUMENT_NAMES

    assert "prebuild_map" in ARGUMENT_NAMES
    assert ProgramArguments().prebuild_map is False


# ##################################################################################
# Every browser tab has handlers of its own, and they share one run state
# ##################################################################################
@pytest.mark.asyncio
async def test_a_second_set_of_handlers_does_not_build_while_the_first_is_building(seen: SimpleNamespace) -> None:
    state = _state()
    first, second = _Handlers(state), _Handlers(state)
    release = asyncio.Event()
    seen.build = None

    async def io_bound(function, *args, **kwargs):
        await release.wait()
        return function(*args, **kwargs)

    with patch.object(userintr_prebuild.run, "io_bound", io_bound):
        first.prebuild_tick()
        first.prebuild_tick()
        await asyncio.sleep(0)
        assert first.prebuild_running()
        assert second.prebuild_running(), "the other window did not see the build under way"

        second.prebuild_tick()
        second.prebuild_tick()
        started = _building.task
        release.set()
        await started

    assert seen.built == [""], "two windows built the Map at once"


@pytest.mark.asyncio
async def test_a_view_built_in_one_window_holds_off_the_build_in_another(seen: SimpleNamespace) -> None:
    state = _state()
    pressing, idle = _event_handlers(), _Handlers(state)

    with pressing.prebuild.view_in_progress():
        await _look_until_started(idle)
        assert _building.task is None

    await _look_until_started(idle)
    assert seen.built == [""]


@pytest.mark.asyncio
async def test_a_press_in_one_window_waits_for_a_build_started_by_another(seen: SimpleNamespace) -> None:
    other = _Handlers(_state())
    handlers = _event_handlers()
    release = asyncio.Event()
    order: list[str] = []

    async def io_bound(function, *args, **kwargs):
        await release.wait()
        order.append("the build finished")
        return function(*args, **kwargs)

    handlers.get_ready_to_build.side_effect = lambda _overrides: order.append("the press prepared")  # type: ignore[attr-defined]
    with (
        patch.object(userintr_prebuild.run, "io_bound", io_bound),
        patch("maptasker.src.gui.userintr._busy_banner", return_value=None),
    ):
        other.prebuild_tick()
        other.prebuild_tick()
        await asyncio.sleep(0)
        press = asyncio.create_task(handlers.view_event("map"))
        await asyncio.sleep(0.01)
        assert "the press prepared" not in order
        release.set()
        await press

    assert order.index("the build finished") < order.index("the press prepared")
