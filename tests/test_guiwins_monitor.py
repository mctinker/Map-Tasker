"""The Live Run Monitor dialog: starting, the log, the lights in the Diagram, the comparison and stopping.

What is read from the device and what a stream of samples means are test_devicemonitor's and test_livemon's.  What is tested
here is the dialog around them: that Start installs the helper before it claims to be monitoring, that what the device
reports turns into log lines and into lights in every open Diagram, that Stop puts them out, that a device that keeps
failing ends the monitoring, and that the comparison and the saved log say what the monitor saw.  The dialog is the real
one, on a page of NiceGUI's in-process user simulation; the device is a script.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import diffload, livemon
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import devicemonitor
from maptasker.src.gui import guiwins_monitor
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_livemon import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

_built: dict = {}
_jumps: list[object] = []
_scripts: list[str] = []
_windows: list[devicemonitor.Window] = []
_asked: list[int] = []
_opened: list[set[str]] = []

MORNING = datetime(2026, 10, 19, 6, 30).timestamp() * 1000  # noqa: DTZ001


def _window(*looks: tuple[float, str, str, str]) -> devicemonitor.Window:
    text = "".join(
        livemon.FIELD_SEPARATOR.join(str(int(field)) if isinstance(field, float) else field for field in look)
        + livemon.SAMPLE_SEPARATOR
        for look in looks
    )
    return devicemonitor.Window(ok=True, text=text, seconds=0.1)


@pytest.fixture(autouse=True)
def _configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture loaded, a scripted device, one fake Diagram open, and no settings file written."""
    _built.clear()
    _jumps.clear()
    _scripts.clear()
    _windows.clear()
    _asked.clear()
    _opened.clear()
    _load(_FIXTURE_XML)

    def sample_window(_ip: str, _port: str, samples: int, *, state: object) -> devicemonitor.Window:  # noqa: ARG001
        _asked.append(samples)
        time.sleep(0.02)
        return _windows.pop(0) if len(_windows) > 1 else _windows[0]

    async def run_javascript(script: str, timeout: float = 5) -> dict[str, int]:  # noqa: ARG001
        _scripts.append(script)
        return {"nodes": 5, "lit": 1}

    # Two windows: the main page, which has no Diagram, and another tab that has one.
    main_page = SimpleNamespace(run_javascript=_no_diagram)
    diagram = SimpleNamespace(run_javascript=run_javascript)
    _built["windows"] = [main_page, diagram]
    monkeypatch.setattr(devicemonitor, "install_monitor", lambda *_a, **_k: (0, ""))
    monkeypatch.setattr(devicemonitor, "sample_window", sample_window)
    monkeypatch.setattr(guiwins_monitor, "_clients", lambda: _built["windows"])
    monkeypatch.setattr(guiwins_monitor, "remember_android_address", lambda *_a, **_k: None)
    monkeypatch.setattr(guiwins_monitor, "remember_android_address_fields", lambda *_a, **_k: None)


async def _no_diagram(script: str, timeout: float = 5) -> dict[str, int]:  # noqa: ARG001
    """A window with no Diagram in it: it has no named objects to light."""
    return {"nodes": 0, "lit": 0}


def _gui() -> SimpleNamespace:
    return SimpleNamespace(state=PrimeItems, android_last_ipaddr="192.0.2.1", android_last_port="1821")


async def _open_diagram(projects: set[str]) -> None:
    _opened.append(projects)


def _page() -> None:
    def make_jump(target: object) -> Callable:
        async def go() -> None:
            _jumps.append(target)

        return go

    _built["dialog"] = guiwins_monitor.build_monitor_dialog(_gui(), make_jump, _open_diagram)  # type: ignore[arg-type]
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            try:
                yield user
            finally:
                monitor = getattr(_built.get("dialog"), "monitor", None)
                if monitor is not None:
                    monitor.running = False
                    if monitor.worker is not None:
                        monitor.worker.cancel()
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, text: str) -> ui.button:
    (element,) = [e for e in user.find(kind=ui.button).elements if e.text == text]
    return element


def _press(user: User, text: str) -> None:
    UserInteraction(user, {_button(user, text)}, None).click()


def _elements(user: User, kind: type) -> list:
    """Every element of a kind, or none: finding what is not there is an assertion in the simulation."""
    try:
        return list(user.find(kind=kind).elements)
    except AssertionError:
        return []


def _texts(user: User) -> list[str]:
    return [e.text for e in _elements(user, ui.label)] + [e.text for e in _elements(user, ui.link)]


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(100):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


def _script(*looks: tuple[float, str, str, str]) -> None:
    _windows.append(_window(*looks))


@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file has been loaded")


@pytest.mark.asyncio
async def test_it_opens_stopped_with_the_address_the_other_android_dialogs_use() -> None:
    async with _open() as user:
        values = {e.props.get("label", ""): e.value for e in user.find(kind=ui.input).elements}

        assert values["Android IP Address"] == "192.0.2.1"
        assert "Not monitoring." in _texts(user)
        assert not _button(user, "Stop").enabled


@pytest.mark.asyncio
async def test_what_the_device_reports_becomes_log_lines_and_the_lists_of_what_is_on() -> None:
    _script((MORNING, "Morning", "Dawn", "90"), (MORNING + 200, "Morning", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any("Task started: Morning" in text for text in _texts(user)))

        text = _texts(user)
        assert any("Profile became active: Dawn" in line for line in text)
        assert "Morning" in text, "in the list of what is running now"
        assert "Dawn" in text, "in the list of what is active now"
        assert any(line.startswith("Monitoring 192.0.2.1") for line in text)
        assert _button(user, "Stop").enabled


@pytest.mark.asyncio
async def test_the_number_of_looks_asked_for_is_what_the_field_says() -> None:
    _script((MORNING, "", "", "90"))
    async with _open() as user:
        (field,) = [e for e in user.find(kind=ui.number).elements if e.props.get("label") == "Looks per request"]
        field.set_value(4)
        _press(user, "Start")
        await _until(lambda: _asked)

        assert _asked[0] == 4


@pytest.mark.asyncio
async def test_every_open_diagram_is_told_to_light_what_is_on() -> None:
    _script((MORNING, "Morning", "Dawn,Twin", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any('"mt-task-20"' in script for script in _scripts))

        script = next(script for script in _scripts if '"mt-task-20"' in script)
        assert "document.getElementById" in script and 'const containerId = "";' in script, "the whole page"
        assert '"mt-profile-100"' in script
        assert '"mt-profile-102"' in script and '"mt-profile-103"' in script, "both Profiles of the name"


@pytest.mark.asyncio
async def test_with_light_up_the_diagram_cleared_nothing_is_sent_to_it() -> None:
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        (box,) = [e for e in user.find(kind=ui.checkbox).elements if "Light up" in e.text]
        box.set_value(False)
        _press(user, "Start")
        await _until(lambda: any("Task started: Morning" in text for text in _texts(user)))

        assert _scripts == []


@pytest.mark.asyncio
async def test_stop_puts_the_lights_out_and_the_monitor_stops_asking() -> None:
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any('"mt-task-20"' in script for script in _scripts))

        _press(user, "Stop")
        await _until(lambda: "Stopped." in _texts(user))
        asked = len(_asked)
        await asyncio.sleep(0.3)

        assert "const lit = {};" in _scripts[-1]
        assert len(_asked) == asked, "no more windows were asked for"
        assert _button(user, "Start").enabled
        assert not _button(user, "Stop").enabled


@pytest.mark.asyncio
async def test_when_no_diagram_is_open_in_any_window_the_monitor_says_so() -> None:
    _script((MORNING, "Morning", "", "90"))
    _built["windows"] = [SimpleNamespace(run_javascript=_no_diagram)]
    async with _open() as user:
        _press(user, "Start")

        await user.should_see("No Diagram is open.  Use Open Diagram, and its Profiles and Tasks will light up.")


@pytest.mark.asyncio
async def test_a_diagram_open_in_another_window_is_lit_and_nothing_is_said_against_it() -> None:
    """The Diagram is in a tab of its own, which the app's own list of views may not hold."""
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any('"mt-profile-100"' in script for script in _scripts))

        assert not any("No Diagram is open" in text or "none of these" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_diagram_that_has_none_of_them_to_light_is_said_to_be_the_wrong_one() -> None:
    _script((MORNING, "Morning", "", "90"))

    async def nothing_lit(script: str, timeout: float = 5) -> dict[str, int]:  # noqa: ARG001
        return {"nodes": 40, "lit": 0}

    _built["windows"] = [SimpleNamespace(run_javascript=nothing_lit)]
    async with _open() as user:
        _press(user, "Start")

        await user.should_see("The Diagram on screen has none of these to light.")


@pytest.mark.asyncio
async def test_a_window_that_does_not_answer_is_one_more_window_with_nothing_to_light() -> None:
    _script((MORNING, "Morning", "Dawn", "90"))

    async def hung(script: str, timeout: float = 5) -> dict[str, int]:  # noqa: ARG001
        raise TimeoutError

    _built["windows"] = [SimpleNamespace(run_javascript=hung), _built["windows"][1]]
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any('"mt-task-20"' in script for script in _scripts))

        assert not any("No Diagram is open" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_device_that_will_not_install_the_helper_is_never_called_monitoring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(devicemonitor, "install_monitor", lambda *_a, **_k: (8, "Tasker is not answering"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: user.notify.contains("Tasker is not answering"))

        assert "Could not start." in _texts(user)
        assert _asked == []
        assert _button(user, "Start").enabled


@pytest.mark.asyncio
async def test_a_device_that_keeps_failing_ends_the_monitoring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiwins_monitor, "_RETRY_SECONDS", 0.01)
    calls: list[int] = []

    def failing(*_a: object, **_k: object) -> devicemonitor.Window:
        calls.append(1)
        return devicemonitor.Window(ok=False, error="Connection error")

    monkeypatch.setattr(devicemonitor, "sample_window", failing)
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: user.notify.contains("Connection error"))
        await _until(lambda: "Stopped." in _texts(user))

        assert len(calls) == guiwins_monitor._FAILURES_ALLOWED  # noqa: SLF001
        assert _button(user, "Start").enabled


@pytest.mark.asyncio
async def test_a_log_line_that_names_an_object_is_a_link_into_the_map() -> None:
    _script((MORNING, "Morning", "", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any("Task started: Morning" in e.text for e in _elements(user, ui.link)))

        link = next(e for e in _elements(user, ui.link) if "Task started: Morning" in e.text)
        UserInteraction(user, {link}, None).click()
        await _until(lambda: _jumps)

        assert _jumps[0].key == "20"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_name_not_in_the_backup_is_logged_and_marked_so_and_is_not_a_link() -> None:
    _script((MORNING, "Stranger", "", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any("Stranger" in text for text in _texts(user)))

        assert any("(not in this backup)" in e.text for e in _elements(user, ui.label))
        assert not any("Stranger" in e.text and "Task started" in e.text for e in _elements(user, ui.link))


@pytest.mark.asyncio
async def test_compare_before_anything_is_seen_says_to_start_first() -> None:
    async with _open() as user:
        _press(user, "Compare With What Fires When")

        assert user.notify.contains("Start the monitor first.")


@pytest.mark.asyncio
async def test_compare_shows_where_the_device_and_the_prediction_disagree() -> None:
    _script((MORNING, "", "Dusk", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any("Profile became active: Dusk" in text for text in _texts(user)))
        _press(user, "Compare With What Fires When")

        await user.should_see("Device against What Fires When")
        text = _texts(user)
        assert any(line.startswith("ACTIVE, PREDICTED INACTIVE: Dusk") for line in text)
        assert any(line.startswith("INACTIVE, PREDICTED ACTIVE: Dawn") for line in text)
        assert any("battery 90%" in line for line in text)


@pytest.mark.asyncio
async def test_save_log_writes_what_was_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[tuple[str, str]] = []
    monkeypatch.setattr(
        diffload,
        "write_comparison_report",
        lambda text, name, *, state: written.append((name, text)) or "/tmp/MapTasker_Monitor.txt",  # noqa: ARG005, S108
    )
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any("Task started: Morning" in text for text in _texts(user)))
        _press(user, "Save Log")
        await _until(lambda: written)

        assert written[0][0] == livemon.MONITOR_FILE
        assert "Task started: Morning" in written[0][1]
        assert user.notify.contains("Log saved as")


@pytest.mark.asyncio
async def test_save_log_with_nothing_logged_says_so() -> None:
    async with _open() as user:
        _press(user, "Save Log")
        await _until(lambda: user.notify.contains("There is nothing in the log yet."))


@pytest.mark.asyncio
async def test_close_stops_the_monitoring() -> None:
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: _asked)

        _press(user, "Close")
        await asyncio.sleep(0.2)
        asked = len(_asked)
        await asyncio.sleep(0.3)

        assert _built["dialog"].monitor.running is False
        assert len(_asked) == asked


@pytest.mark.asyncio
async def test_the_dialog_is_docked_where_it_does_not_cover_the_diagram_button() -> None:
    async with _open() as user:
        props = _built["dialog"].props

        assert props.get("seamless") is True
        assert props.get("position") == "left", "the right-hand panel holds the Diagram button"
        assert user is not None


@pytest.mark.asyncio
async def test_open_diagram_opens_the_diagram_without_closing_the_monitor() -> None:
    async with _open() as user:
        _press(user, "Open Diagram")
        await _until(lambda: _opened)

        assert _built["dialog"].value is True


@pytest.mark.asyncio
async def test_before_anything_has_fired_the_diagram_is_asked_for_with_no_projects() -> None:
    async with _open() as user:
        _press(user, "Open Diagram")
        await _until(lambda: _opened)

        assert _opened == [set()]


@pytest.mark.asyncio
async def test_after_things_have_fired_the_diagram_is_told_which_projects_they_belong_to() -> None:
    _script((MORNING, "Morning,Away Task", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any("Task started: Morning" in text for text in _texts(user)))
        _press(user, "Open Diagram")
        await _until(lambda: _opened)

        assert _opened[0] == {"Home", "Away"}


@pytest.mark.asyncio
async def test_what_has_just_started_is_what_the_diagram_is_told_to_scroll_to() -> None:
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        _press(user, "Start")
        await _until(lambda: any('"mt-task-20"' in script for script in _scripts))

        script = next(script for script in _scripts if '"mt-task-20"' in script)
        assert 'for (const anchor of ["mt-profile-100", "mt-task-20"])' in script


@pytest.mark.asyncio
async def test_with_scrolling_turned_off_the_diagram_is_lit_and_left_where_it_is() -> None:
    _script((MORNING, "Morning", "Dawn", "90"))
    async with _open() as user:
        (box,) = [e for e in user.find(kind=ui.checkbox).elements if "Scroll the Diagram" in e.text]
        box.set_value(False)
        _press(user, "Start")
        await _until(lambda: any('"mt-task-20"' in script for script in _scripts))

        script = next(script for script in _scripts if '"mt-task-20"' in script)
        assert "for (const anchor of [])" in script
