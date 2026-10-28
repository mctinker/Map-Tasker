"""Starting the window's web server: choosing a port, saving settings on the way out and reporting a failure to start."""

from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
