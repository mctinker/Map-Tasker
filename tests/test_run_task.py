"""Run a Task on the Android device (deviceinv.run_task_for_result) Unit Tests

No device is involved: maputil2's `requests` is replaced by a fake that answers the Tasker HTTP
Server Example's 'POST Task' handler the way it does on a device -- 200 with the Task's return
value, '%return' when the Task set none, and a bare 400 for a Task it cannot find.  "Cannot
find" is the handler's own regular-expression match, copied, which is what makes a name like
'$Taskaroo' unfindable on a device that has it.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import pytest
import requests
from maptasker.src import deviceinv, maputil2

from tests.test_deviceinv import _FIXTURE_XML, _load

_DEVICE = ("192.168.0.210", "1821")


class _Response:
    """The parts of a requests.Response MapTasker reads."""

    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content

    def json(self) -> object:
        return json.loads(self.content)


class _FakeDevice:
    """maputil2's `requests`, for a device holding the Tasks named in `tasks` with their return values."""

    exceptions = requests.exceptions

    def __init__(self, tasks: dict[str, str], *, timeout: bool = False, reject_keys: int = 0) -> None:
        self.tasks = tasks
        self.timeout = timeout
        self.reject_keys = reject_keys
        self.run_bodies: list[dict] = []
        self.run_timeouts: list[float] = []
        self.keys_issued = 0
        self.imported: list[str] = []

    def _objects_payload(self) -> str:
        """What the object-list helper writes: 'Test Tasker' lists every Task by its real name."""
        tasks = "|~|".join(self.tasks)
        return f"MAPTASKER-OBJECTS 1\nPROJECTS\nBase\nPROFILES\n%mtprofiles\nSCENES\n%mtscenes\nTASKS\n{tasks}\nMAPTASKER-END\n"

    def _found(self, pattern: str) -> bool:
        """The handler's %tasks(#?~R<pattern>): a name is 'there' only if the pattern matches it."""
        try:
            return any(re.search(pattern, name) for name in self.tasks)
        except re.error:
            return False

    def get(self, url: str, **_kwargs: object) -> _Response:
        if "/api/auth" in url:
            self.keys_issued += 1
            auth = {"key": f"KEY{self.keys_issued}", "authorized": True}
            return _Response(200, json.dumps(auth).encode())
        if "/api/tasks" in url:
            if "name=" not in url:
                # The whole list, built the handler's way: each name tested as a pattern against
                # the Task list, and the ones that fail left out -- '$Taskaroo' among them.
                listed = [name for name in self.tasks if self._found(name)]
                return _Response(200, json.dumps([{"name": name, "running": False} for name in listed]).encode())
            wanted = unquote(url.split("name=", 1)[1])
            listed = [{"name": wanted, "running": False}] if self._found(wanted) else []
            return _Response(200, json.dumps(listed).encode())
        if "maptasker_objects.txt" in url:
            return _Response(200, self._objects_payload().encode())
        return _Response(404)

    def delete(self, _url: str, **_kwargs: object) -> _Response:
        return _Response(404)

    def post(self, url: str, data: bytes = b"", timeout: float = 0, **_kwargs: object) -> _Response:
        if url.endswith("/api/import"):
            name = ET.fromstring(data).findtext(".//nme")  # noqa: S314  (built by the code under test)
            self.imported.append(name)
            self.tasks[name] = ""
            return _Response(200, b"{}")

        assert url.endswith("/api/tasks")
        body = json.loads(data)
        self.run_bodies.append(body)
        self.run_timeouts.append(timeout)
        if self.reject_keys:
            self.reject_keys -= 1
            return _Response(401)
        if self.timeout:
            raise requests.exceptions.Timeout
        if not self._found(f"^{body['name']}$"):
            return _Response(400)
        name = body["name"]
        if name == deviceinv.RUN_TASK_HELPER_NAME:
            # What its 'Perform Task' runs; its 'Return' of an unset result sends the variable's name.
            name = body["variables"]["mt_run_task"]
            return _Response(200, f"{self.tasks[name] or '%mt_run_result'}\n".encode())
        return _Response(200, f"{self.tasks[name]}\n".encode())


@pytest.fixture
def device(monkeypatch: pytest.MonkeyPatch) -> _FakeDevice:
    _load(_FIXTURE_XML)  # the helper Task is built with taskedit, which needs Tasker's argument specs
    fake = _FakeDevice(
        {"Returns Text": "hello world", "Returns Nothing": "%return", "Echo": "", "$Taskaroo": "roo", "(Silent)": ""},
    )
    monkeypatch.setattr(maputil2, "requests", fake)
    monkeypatch.setattr(maputil2, "_auth_keys", {})
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)
    return fake


def test_a_task_that_returns_a_value_reports_it(device: _FakeDevice) -> None:
    result = deviceinv.run_task_for_result(*_DEVICE, "Returns Text")
    assert result.ok, result.error
    assert result.output == "hello world"
    assert device.run_bodies == [{"name": "Returns Text"}]


def test_a_task_that_returns_nothing_reports_no_value(device: _FakeDevice) -> None:
    """The handler sends '%return' for an unset return value -- that is not the Task's output."""
    result = deviceinv.run_task_for_result(*_DEVICE, "Returns Nothing")
    assert result.ok, result.error
    assert result.output == ""


def test_par1_and_par2_are_sent_only_when_given(device: _FakeDevice) -> None:
    deviceinv.run_task_for_result(*_DEVICE, "Echo", par1="one", par2="two")
    deviceinv.run_task_for_result(*_DEVICE, "Echo", par2="two")
    assert device.run_bodies == [{"name": "Echo", "par1": "one", "par2": "two"}, {"name": "Echo", "par2": "two"}]


def test_the_run_waits_longer_than_a_write(device: _FakeDevice) -> None:
    """api/tasks answers only once the Task has finished, so the run gets its own, longer timeout."""
    deviceinv.run_task_for_result(*_DEVICE, "Echo")
    assert device.run_timeouts == [deviceinv.RUN_TASK_TIMEOUT_SECONDS]


def test_a_task_the_device_does_not_have_is_named_as_missing(device: _FakeDevice) -> None:
    result = deviceinv.run_task_for_result(*_DEVICE, "Only In The Editor")
    assert not result.ok
    assert "no Task named 'Only In The Editor'" in result.error
    assert "Save To Android" in result.error


def test_a_run_that_outlasts_the_timeout_says_it_may_still_be_running(device: _FakeDevice) -> None:
    device.timeout = True
    result = deviceinv.run_task_for_result(*_DEVICE, "Returns Text", timeout=5)
    assert not result.ok
    assert "did not answer within 5 seconds" in result.error
    assert "may still be running" in result.error


def test_a_rejected_key_is_replaced_and_the_run_retried_once(device: _FakeDevice) -> None:
    device.reject_keys = 1
    result = deviceinv.run_task_for_result(*_DEVICE, "Returns Text")
    assert result.ok, result.error
    assert device.keys_issued == 2
    assert len(device.run_bodies) == 2


def test_no_task_name_is_refused_without_touching_the_device(device: _FakeDevice) -> None:
    result = deviceinv.run_task_for_result(*_DEVICE, "   ")
    assert not result.ok
    assert device.run_bodies == []
    assert device.keys_issued == 0


def test_only_the_handlers_own_newline_is_removed() -> None:
    assert deviceinv.task_return_value(b"  indented \n\n") == "  indented \n"
    assert deviceinv.task_return_value(b"%return\n") == ""


# --------------------------------------------------------------------------------------
# Names the handler reads as regular expressions
# --------------------------------------------------------------------------------------


def test_a_name_the_handler_cannot_match_runs_through_the_helper(device: _FakeDevice) -> None:
    """'$Taskaroo' is on the device, but ^$Taskaroo$ matches nothing -- so the helper runs it."""
    result = deviceinv.run_task_for_result(*_DEVICE, "$Taskaroo", par1="one")
    assert result.ok, result.error
    assert result.output == "roo"
    assert deviceinv.RUN_TASK_HELPER_NAME in device.imported
    helper_runs = [body for body in device.run_bodies if body["name"] == deviceinv.RUN_TASK_HELPER_NAME]
    assert helper_runs == [
        {"name": deviceinv.RUN_TASK_HELPER_NAME, "par1": "one", "variables": {"mt_run_task": "$Taskaroo"}},
    ]


def test_the_http_apis_whole_list_really_leaves_such_a_name_out(device: _FakeDevice) -> None:
    """Why the check goes to the object-list helper: the fake's GET api/tasks, like the device's,
    cannot report '$Taskaroo' however it is asked."""
    return_code, message, names = deviceinv.fetch_task_names_from_device(*_DEVICE)
    assert return_code == 0, message
    assert "$Taskaroo" not in names
    assert "Returns Text" in names


def test_the_helper_is_installed_once(device: _FakeDevice) -> None:
    deviceinv.run_task_for_result(*_DEVICE, "$Taskaroo")
    deviceinv.run_task_for_result(*_DEVICE, "$Taskaroo")
    assert device.imported.count(deviceinv.RUN_TASK_HELPER_NAME) == 1


def test_an_unmatchable_name_the_device_lacks_is_reported_without_running(device: _FakeDevice) -> None:
    """The helper would stop on 'Perform Task' and return nothing, which would read as success."""
    result = deviceinv.run_task_for_result(*_DEVICE, "$Missing")
    assert not result.ok
    assert "no Task named '$Missing'" in result.error
    assert all(body["name"] != deviceinv.RUN_TASK_HELPER_NAME for body in device.run_bodies)


def test_the_helper_returning_nothing_is_no_value(device: _FakeDevice) -> None:
    result = deviceinv.run_task_for_result(*_DEVICE, "(Silent)")
    assert result.ok, result.error
    assert result.output == ""


def test_the_helper_runs_the_named_task_the_way_the_handler_does() -> None:
    """The HTTP Server Example's own 'Perform Task', copied: %priority, a return variable, and
    passthrough -- which is what still delivers %par1 and %par2 to the Task it runs."""
    _load(_FIXTURE_XML)
    built = deviceinv.build_run_task_helper()
    assert not isinstance(built, str), built

    task = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))  # noqa: S314
    perform = task.find("Action[code='130']")
    assert perform.findtext("Str[@sr='arg0']") == "%mt_run_task"
    assert perform.findtext("Int[@sr='arg1']/var") == "%priority"
    assert perform.find("Int[@sr='arg1']").get("val") is None
    assert perform.findtext("Str[@sr='arg4']") == "%mt_run_result"
    assert perform.find("Int[@sr='arg6']").get("val") == "1"
    assert perform.findtext("Str[@sr='arg7']") == "!%mt_run*"
    assert task.findtext("Action[code='126']/Str[@sr='arg0']") == "%mt_run_result"


def test_the_helper_is_a_current_helper_task() -> None:
    """So 'List Helper Tasks' does not offer to delete it."""
    assert deviceinv.RUN_TASK_HELPER_NAME in deviceinv.current_helper_task_names()


@pytest.mark.parametrize("name", ["$Taskaroo", "Wake (Up)", "a+b", "x|y", "Why?"])
def test_a_regex_name_is_not_matchable(name: str) -> None:
    assert not maputil2.tasker_name_matchable(name)


@pytest.mark.parametrize("name", ["Wake Up", "Updater - check", "Sonos & Off", "CHECK / READ"])
def test_an_ordinary_name_is_matchable(name: str) -> None:
    assert maputil2.tasker_name_matchable(name)
