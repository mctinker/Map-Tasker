"""MapTasker Live Run Monitor, the phone's half (devicemonitor) Unit Tests

No device is involved.  The helper Task is built and read as XML, and the two calls that would reach the network --
installing it and running it for its return value -- are replaced by recorders, so what is asserted is what would have
been sent: that the Task looks at Tasker's own %TRUN, %PACTIVE and %BATT with the moment, waits between looks, and
returns them; and that asking for a window clamps what it asks and passes the answer through whole.
"""

from __future__ import annotations

from typing import Any

import pytest
from maptasker.src.analysis import livemon
from maptasker.src.core import maputil2
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import devicemonitor
from maptasker.src.device.devicetask import TaskRunResult

from tests.test_deviceresource import _FIXTURE_XML, _load


@pytest.fixture(autouse=True)
def _configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(maputil2, "_auth_keys", {})
    _load(_FIXTURE_XML)


def _action(task: object, code: str, position: int = 0) -> object:
    return [a for a in task.task_element.findall("Action") if a.findtext("code") == code][position]  # type: ignore[attr-defined]


def test_the_helper_task_clears_loops_looks_waits_and_returns() -> None:
    built = devicemonitor.build_monitor_task(state=PrimeItems)
    assert not isinstance(built, str), built

    codes = [action.findtext("code") for action in built.task_element.findall("Action")]

    # Variable Set, For, Variable Set (the look), Wait, End For, Return.
    assert codes == ["547", "39", "547", "30", "40", "126"]


def test_each_look_records_the_moment_what_is_running_what_is_active_and_the_battery() -> None:
    built = devicemonitor.build_monitor_task(state=PrimeItems)

    look = _action(built, "547", 1)

    text = look.findtext("Str[@sr='arg1']")
    assert text == "%TIMEMS|~|%TRUN|~|%PACTIVE|~|%BATT|#|"
    assert look.find("Int[@sr='arg4']").attrib["val"] == "1", "appended, so every look is kept"


def test_the_looks_are_written_in_the_format_the_reader_expects() -> None:
    """The Task and parse_window share their separators; a drift between them would read nothing."""
    built = devicemonitor.build_monitor_task(state=PrimeItems)
    text = _action(built, "547", 1).findtext("Str[@sr='arg1']")

    assert text.count(livemon.FIELD_SEPARATOR) == 3
    assert text.endswith(livemon.SAMPLE_SEPARATOR)
    filled = text.replace("%TIMEMS", "1000").replace("%TRUN", "A,B").replace("%PACTIVE", "P").replace("%BATT", "90")
    (sample,) = livemon.parse_window(filled)
    assert (sample.when_ms, sample.running, sample.active, sample.battery) == (1000, {"A", "B"}, {"P"}, 90)


def test_the_number_of_looks_is_a_parameter_so_the_task_is_installed_once() -> None:
    built = devicemonitor.build_monitor_task(state=PrimeItems)

    assert _action(built, "39").findtext("Str[@sr='arg1']") == "1:%par1"


def test_it_waits_between_looks() -> None:
    built = devicemonitor.build_monitor_task(state=PrimeItems)

    assert _action(built, "30").find("Int[@sr='arg0']").attrib["val"] == str(devicemonitor.SAMPLE_WAIT_MS)


def test_it_returns_the_log_and_stops_there() -> None:
    built = devicemonitor.build_monitor_task(state=PrimeItems)

    action = _action(built, "126")

    assert action.findtext("Str[@sr='arg0']") == "%mtmon_log"
    assert action.find("Int[@sr='arg1']").attrib["val"] == "1"


def test_the_monitors_own_name_is_the_one_to_leave_out_of_what_is_running() -> None:
    assert devicemonitor.MONITOR_TASK_NAME == "MapTasker Monitor v1"


def test_a_window_is_asked_for_with_its_look_count_and_a_timeout_that_covers_the_looks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[dict] = []

    def fake_run(ip: str, port: str, name: str, **kwargs: Any) -> TaskRunResult:
        asked.append({"ip": ip, "port": port, "name": name, **kwargs})
        return TaskRunResult(ok=True, output="1000|~|A|~|P|~|9|#|", seconds=1.5)

    monkeypatch.setattr(devicemonitor, "run_task_for_result", fake_run)

    window = devicemonitor.sample_window("192.168.0.9", "1821", 10, state=PrimeItems)

    assert window.ok
    assert window.text == "1000|~|A|~|P|~|9|#|"
    assert window.seconds == 1.5
    assert asked[0]["name"] == devicemonitor.MONITOR_TASK_NAME
    assert asked[0]["par1"] == "10"
    assert asked[0]["timeout"] > 10 * devicemonitor.SAMPLE_WAIT_MS / 1000


@pytest.mark.parametrize(("asked", "sent"), [(0, "1"), (-5, "1"), (7, "7"), (100000, str(devicemonitor.MAX_SAMPLES))])
def test_the_number_of_looks_is_kept_within_what_the_task_can_take(
    monkeypatch: pytest.MonkeyPatch, asked: int, sent: str
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        devicemonitor,
        "run_task_for_result",
        lambda *_a, **kw: seen.append(kw["par1"]) or TaskRunResult(ok=True, output=""),
    )

    devicemonitor.sample_window("h", "1", asked, state=PrimeItems)

    assert seen == [sent]


def test_a_device_that_does_not_answer_is_an_error_not_an_empty_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        devicemonitor,
        "run_task_for_result",
        lambda *_a, **_k: TaskRunResult(ok=False, error="Connection error", seconds=0.2),
    )

    window = devicemonitor.sample_window("h", "1", 5, state=PrimeItems)

    assert (window.ok, window.error) == (False, "Connection error")


def test_installing_needs_an_address() -> None:
    assert devicemonitor.install_monitor("", "", state=PrimeItems) == (8, "An Android IP address and port are needed.")


def test_installing_puts_the_task_on_the_device_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    installed: list[str] = []
    monkeypatch.setattr(devicemonitor, "auth_key_for", lambda _ip, _port: (0, "KEY"))
    monkeypatch.setattr(
        devicemonitor,
        "install_task_on_android",
        lambda _ip, _port, key, name, builder, state: installed.append(f"{key}:{name}") or (0, ""),
    )

    assert devicemonitor.install_monitor("192.168.0.9", "1821", state=PrimeItems) == (0, "")
    assert installed == ["KEY:MapTasker Monitor v1"]


def test_a_key_that_cannot_be_had_stops_the_install_with_its_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(devicemonitor, "auth_key_for", lambda _ip, _port: (8, "refused"))

    assert devicemonitor.install_monitor("h", "1", state=PrimeItems) == (8, "refused")
