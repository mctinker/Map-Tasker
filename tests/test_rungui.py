"""Starting the window's web server: choosing a port, saving settings on the way out and reporting a failure to start."""

from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from maptasker.src import rungui
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems, RunState

from tests.doubles import fake_state


# ##################################################################################
# A port
# ##################################################################################
def test_the_default_port_is_used_when_it_is_free(monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]
    monkeypatch.setattr(rungui, "DEFAULT_PORT", free)
    monkeypatch.setattr(rungui, "LAST_FALLBACK_PORT", free + 5)
    assert rungui.get_open_port() == free


def test_the_next_port_up_is_used_when_the_default_is_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second MapTasker is started while the first is still running."""
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        busy = taken.getsockname()[1]
        monkeypatch.setattr(rungui, "DEFAULT_PORT", busy)
        monkeypatch.setattr(rungui, "LAST_FALLBACK_PORT", busy + 20)
        found = rungui.get_open_port()
    assert found != busy
    assert busy < found <= busy + 20


def test_when_every_port_is_taken_the_default_is_handed_back_to_report_the_clash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logged: list[str] = []
    monkeypatch.setattr(rungui.logger, "error", logged.append)

    class Refusing:
        def __enter__(self) -> Refusing:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def bind(self, _address: tuple) -> None:
            raise OSError("in use")

    monkeypatch.setattr(rungui.socket, "socket", lambda *_a, **_k: Refusing())
    assert rungui.get_open_port() == rungui.DEFAULT_PORT
    assert logged


# ##################################################################################
# Numbers typed into the window
# ##################################################################################
@pytest.mark.parametrize(
    ("typed", "expected"),
    [("7", 7), (" 12 ", 12), (3, 3), ("seven", 4), ("", 4), (None, 4), ("1.5", 4)],
)
def test_a_number_is_read_or_the_default_is_used(typed: object, expected: int) -> None:
    assert rungui.convert_to_integer(typed, 4) == expected


# ##################################################################################
# Saving the settings on the way out
# ##################################################################################
@pytest.fixture
def saving(monkeypatch: pytest.MonkeyPatch) -> dict:
    """capture_gui_state and the settings file replaced; the once-only guard reset."""
    record: dict = {"captured": [], "saved": []}
    monkeypatch.setitem(rungui._settings_saved, "done", False)
    monkeypatch.setattr(rungui, "capture_gui_state", lambda gui, data, state: record["captured"].append(gui))
    monkeypatch.setattr(
        rungui,
        "save_restore_args",
        lambda arguments, colors, to_save, state: record["saved"].append((arguments, colors, to_save)) or (0, ""),
    )
    return record


def _run() -> RunState:
    return fake_state(
        colors_to_use={"c": "x"},
        ai={},
        program_arguments=SimpleNamespace(display_detail_level="3", indent="x", ai_apikey=""),
    )


def test_no_window_means_nothing_to_save(saving: dict) -> None:
    rungui.save_gui_settings(None, _run())
    assert saving["saved"] == []


def test_the_windows_values_are_saved_with_numbers_made_numeric(saving: dict) -> None:
    state = _run()
    gui = SimpleNamespace()

    rungui.save_gui_settings(gui, state)

    assert saving["captured"] == [gui]
    assert state.program_arguments.display_detail_level == 3
    assert state.program_arguments.indent == 4  # "x" is not a number, so the default
    assert saving["saved"][0][2] is True


def test_the_ai_key_is_kept_out_of_the_settings_file(saving: dict) -> None:
    state = _run()
    rungui.save_gui_settings(SimpleNamespace(ai_apikey="sk-secret"), state)
    assert state.ai["api_key"] == "sk-secret"
    assert state.program_arguments.ai_apikey == "HIDDEN"


def test_saving_twice_saves_once(saving: dict) -> None:
    """The shutdown hook and the code after ui.run() both ask; only the first does anything."""
    gui = SimpleNamespace()
    rungui.save_gui_settings(gui, _run())
    rungui.save_gui_settings(gui, _run())
    assert len(saving["saved"]) == 1


def test_a_run_with_no_colours_yet_starts_from_the_defaults(saving: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _run()
    state.colors_to_use = {}
    fresh = SimpleNamespace(display_detail_level="2", indent="2", ai_apikey="")
    monkeypatch.setattr(rungui, "initialize_runtime_arguments", lambda: fresh)

    rungui.save_gui_settings(SimpleNamespace(), state)

    assert state.program_arguments is fresh


# ##################################################################################
# Starting the server
# ##################################################################################
def test_the_server_is_started_on_the_loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    started: dict = {}
    monkeypatch.setattr(rungui.ui, "run", lambda **kwargs: started.update(kwargs))
    monkeypatch.setattr(rungui, "get_open_port", lambda: 8081)

    rungui._run_server(PrimeItems, "/assets")

    assert started["host"] == "127.0.0.1"
    assert started["port"] == 8081
    assert started["reload"] is False


def test_a_port_already_in_use_ends_the_run_with_a_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(**_kwargs: Any) -> None:
        raise OSError("[Errno 48] Address already in use")

    monkeypatch.setattr(rungui.ui, "run", refuse)

    with pytest.raises(MapTaskerError) as raised:
        rungui._run_server(PrimeItems, "/assets")

    assert raised.value.exit_code == 0, "said as it stands, and the process ends quietly"
    assert "Address already in use" in raised.value.message


def test_any_other_failure_to_start_is_only_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []

    def refuse(**_kwargs: Any) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(rungui.ui, "run", refuse)
    monkeypatch.setattr(rungui.logger, "error", logged.append)

    rungui._run_server(PrimeItems, "/assets")  # returns instead of raising

    assert "permission denied" in logged[0]


def test_ctrl_c_is_a_normal_way_to_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupt(**_kwargs: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(rungui.ui, "run", interrupt)
    rungui._run_server(PrimeItems, "/assets")  # returns instead of raising


# ##################################################################################
# Watching what the browser is sent
# ##################################################################################
async def _emit_through_the_interceptor(monkeypatch: pytest.MonkeyPatch, state: RunState) -> list[tuple]:
    sent: list[tuple] = []

    async def original(event: str, data: object = None, room: object = None, **kwargs: Any) -> None:
        sent.append((event, data, room))

    monkeypatch.setattr(rungui.core.sio, "emit", original)
    rungui._intercept_socket_emit(state)
    await rungui.core.sio.emit("update", data={"x": 1}, room="r")
    return sent


def test_everything_still_reaches_the_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    state = fake_state(mygui=None)
    sent = asyncio.run(_emit_through_the_interceptor(monkeypatch, state))
    assert sent == [("update", {"x": 1}, "r")]


def test_a_changed_window_has_its_state_captured_once(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    captured: list[object] = []
    monkeypatch.setattr(rungui, "capture_gui_state", lambda gui, data, state: captured.append(data))
    gui = SimpleNamespace(event=True)
    state = fake_state(mygui=gui)

    async def twice() -> list[tuple]:
        sent = await _emit_through_the_interceptor(monkeypatch, state)
        await rungui.core.sio.emit("update", data={"x": 2}, room="r")
        return sent

    sent = asyncio.run(twice())

    assert captured == [{"x": 1}]  # the flag was reset, so the second message did not capture again
    assert gui.event is False
    assert len(sent) == 2


def test_the_icons_are_found_whatever_the_install_path_is_called() -> None:
    """The path used to be built by replacing "src" in it, which also hit a folder named src higher up."""
    icons = rungui._icons_dir()
    assert icons.endswith(("maptasker/assets/icons", "maptasker\\assets\\icons"))
    assert Path(icons).is_dir()


# ##################################################################################
# The pages the window lives on
# ##################################################################################
@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """rungui's @ui.page functions, kept where a test can call them (the decorator hands the function back)."""
    registered: dict[str, Any] = {}

    def page(path: str, **_options: Any) -> Any:
        def register(function: Any) -> Any:
            registered[path] = function
            return function

        return register

    monkeypatch.setattr(rungui.ui, "page", page)
    return registered


class _Window:
    """What the root page makes of the window class: built with the run, nothing more."""

    built: ClassVar[list[RunState]] = []

    def __init__(self, state: RunState) -> None:
        self.built.append(state)


@pytest.fixture
def root_page(monkeypatch: pytest.MonkeyPatch, pages: dict[str, Any]):
    _Window.built = []
    notes: list[tuple[str, dict]] = []
    reapplied: list[tuple[str, str]] = []
    monkeypatch.setattr(rungui, "live_selection", lambda state: ("Project", "Home"))
    monkeypatch.setattr(rungui, "reapply_selection", lambda gui, kind, name: reapplied.append((kind, name)))
    monkeypatch.setattr(rungui.ui, "notify", lambda message, **options: notes.append((message, options)))
    shared: dict[str, Any] = {}
    lock = {"is_built": False}
    run = fake_state()
    rungui._register_root_page(run, shared, lock, _Window)  # type: ignore[arg-type]
    return SimpleNamespace(
        visit=pages["/"], shared=shared, lock=lock, notes=notes, reapplied=reapplied, built=_Window.built, run=run
    )


def test_the_first_visit_builds_the_window_and_says_nothing(root_page: SimpleNamespace) -> None:
    root_page.visit()

    assert root_page.built == [root_page.run]
    assert root_page.lock["is_built"] is True
    assert root_page.notes == []
    assert root_page.reapplied == []


def test_a_refresh_rebuilds_the_window_and_puts_the_selection_back(root_page: SimpleNamespace) -> None:
    root_page.visit()
    first = root_page.shared["user_input"]

    root_page.visit()

    assert root_page.shared["user_input"] is not first
    assert root_page.reapplied == [("Project", "Home")]
    [(message, options)] = root_page.notes
    assert message == "This window was rebuilt from your saved settings. Still showing Project: Home."
    assert options["position"] == "bottom"


def test_a_refresh_with_nothing_selected_says_only_that_it_was_rebuilt(
    root_page: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rungui, "live_selection", lambda state: ("", ""))
    root_page.visit()

    root_page.visit()

    assert root_page.notes[0][0] == "This window was rebuilt from your saved settings."


@pytest.fixture
def popout(monkeypatch: pytest.MonkeyPatch, pages: dict[str, Any]):
    views: list[dict[str, Any]] = []
    labels: list[str] = []
    monkeypatch.setattr(
        rungui.ui, "label", lambda text="": SimpleNamespace(classes=lambda *_a, **_k: labels.append(text))
    )
    monkeypatch.setattr(rungui.ui, "page_title", lambda title: labels.append(f"title:{title}"))
    monkeypatch.setattr(rungui.ui, "query", lambda _q: SimpleNamespace(classes=lambda *_a, **_k: None))
    monkeypatch.setattr(rungui.ui, "column", lambda: SimpleNamespace(classes=lambda *_a, **_k: "the column"))
    monkeypatch.setattr(rungui.ui, "dark_mode", lambda value=None: labels.append(f"dark:{value}"))
    monkeypatch.setattr(rungui, "inject_shared_head_styles", lambda state: None)
    monkeypatch.setattr(rungui, "register_finding_clicks", lambda gui: None)
    monkeypatch.setattr(rungui, "NiceGuiTextView", lambda gui, **kwargs: views.append(kwargs) or "the view")
    run = fake_state(mygui=SimpleNamespace(textview=None), taskflow_rows=[])
    rungui._register_popout_page(run)
    return SimpleNamespace(open=pages["/popout/{view_type}"], views=views, labels=labels, run=run)


def test_the_map_opens_in_a_window_of_its_own_with_where_it_was_built_for(popout: SimpleNamespace) -> None:
    popout.open("map", goto="task:5", scope="Home", built_for="Project 'Home'")

    [view] = popout.views
    assert view["title"] == rungui.POPOUT_TITLES["map"]
    assert view["the_data"] == {}, "a dict is what tells the view it is the Map"
    assert (view["jump_to"], view["map_scope"], view["built_for"]) == ("task:5", "Home", "Project 'Home'")
    assert popout.run.mygui.textview == "the view"


@pytest.mark.parametrize("app_is_dark", [False, True])
def test_a_popped_out_view_is_light_or_dark_as_the_app_is_not_as_the_system_is(
    popout: SimpleNamespace, *, app_is_dark: bool
) -> None:
    """The page is its own document: left alone it follows the operating system, whatever the app was set to."""
    popout.run.mygui.dark_mode = app_is_dark

    popout.open("map")

    assert f"dark:{app_is_dark}" in popout.labels


def test_the_diagram_opens_with_nothing_handed_to_it(popout: SimpleNamespace) -> None:
    popout.open("diagram")

    assert popout.views[0]["the_data"] == []


@pytest.mark.parametrize("view_type", ["nonsense", "flow"])
def test_a_view_that_has_nothing_to_show_says_so_instead_of_opening_empty(
    popout: SimpleNamespace, view_type: str
) -> None:
    """An unknown kind of view, or a Task Flow reopened from a bookmark after the process that drew it has gone."""
    popout.open(view_type)

    assert popout.views == []
    assert any("No data available" in label for label in popout.labels)


def test_a_window_opened_with_no_main_window_behind_it_says_so(popout: SimpleNamespace) -> None:
    popout.run.mygui = None

    popout.open("map")

    assert popout.views == []
    assert any("No data available" in label for label in popout.labels)


# ##################################################################################
# Running the window
# ##################################################################################
def _start(monkeypatch: pytest.MonkeyPatch, *, built: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"saved": [], "ran": 0, "shutdown": []}
    monkeypatch.setattr(rungui, "_register_popout_page", lambda state: None)
    monkeypatch.setattr(rungui, "_intercept_socket_emit", lambda state: None)
    monkeypatch.setattr(rungui, "_icons_dir", lambda: "/icons")
    monkeypatch.setattr(rungui, "_run_server", lambda state, assets: record.__setitem__("ran", record["ran"] + 1))
    monkeypatch.setattr(rungui.app, "on_shutdown", lambda hook: record["shutdown"].append(hook))
    monkeypatch.setattr(rungui, "save_gui_settings", lambda gui, state: record["saved"].append(gui))

    def register(state: Any, shared: dict, lock: dict, window_class: Any) -> None:
        if built:
            shared["user_input"] = "the window"

    monkeypatch.setattr(rungui, "_register_root_page", register)
    return record


def test_closing_the_window_saves_the_settings_and_ends_the_run_with_a_goodbye(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _start(monkeypatch, built=True)
    run = fake_state(program_arguments=SimpleNamespace(gui=False))

    with pytest.raises(MapTaskerError) as ended:
        rungui.process_gui(True, run)

    assert ended.value.exit_code == 0
    assert "Goodbye" in ended.value.message
    assert run.program_arguments.gui is True
    assert record["ran"] == 1
    assert record["saved"] == ["the window"], "saved once more in case the server stopped without its shutdown hook"
    record["shutdown"][0]()
    assert record["saved"] == ["the window", "the window"], "the shutdown hook saves the window the page built"


def test_a_server_stopped_before_anyone_opened_the_window_just_says_goodbye(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _start(monkeypatch, built=False)

    with pytest.raises(MapTaskerError) as ended:
        rungui.process_gui(True, fake_state(program_arguments=SimpleNamespace(gui=False)))

    assert ended.value.exit_code == 0
    assert record["saved"] == [], "no window was built, so there is nothing to save"
