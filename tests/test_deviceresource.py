"""MapTasker Missing Resources, the phone's half (deviceresource) Unit Tests

No device is involved.  maputil2 reaches the network through one module-level `requests`, so replacing it with a
recorder drives the exchange and asserts what was sent -- and the ORDER of the calls is the design: the paths are
uploaded before the Task runs, and the previous answer is deleted before it runs, because a stale answer read back
and believed is the one failure this must not have.

What no test here can say is whether Tasker's own 'Test File' answers 'true' and 'false' the way the Task expects;
that is why an answer that is neither is kept as "unknown" (None) and never stored, and why an answer list of the
wrong length is refused rather than matched to paths by position.
"""

from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import resrefs
from maptasker.src.core import appinv, maputil2, resstore
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import deviceinv, deviceresource
from maptasker.src.device.devicetask import PAYLOAD_JOINER
from maptasker.src.mapgen import taskerd

if TYPE_CHECKING:
    from pathlib import Path

ADDRESS = ("192.168.0.210", "1821")
DEVICE = "192.168.0.210:1821"

_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><pids/><tids>20</tids></Project>
  <Task sr="task20">
    <id>20</id>
    <nme>Mixed</nme>
    <Action sr="act0" ve="7"><code>417</code><Str sr="arg0" ve="3">Tasker/there.txt</Str></Action>
    <Action sr="act1" ve="7"><code>417</code><Str sr="arg0" ve="3">Tasker/gone.txt</Str></Action>
    <Action sr="act2" ve="7"><code>47</code><Str sr="arg0" ve="3">Panel</Str></Action>
    <Action sr="act3" ve="7"><code>47</code><Str sr="arg0" ve="3">Lost</Str></Action>
    <Action sr="act4" ve="7">
      <code>20</code>
      <App sr="arg0"><appPkg>com.here.app, com.absent.app</appPkg></App>
    </Action>
  </Task>
</TaskerData>
"""


def _load(xml_text: str) -> None:
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file) as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"
    PrimeItems.tasker_arg_specs = specs
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }
    tables["all_profiles_by_name"] = {}
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items() if task["name"]
    }
    PrimeItems.tasker_root_elements = tables


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test here may touch the real MapTasker_Apps.json or MapTasker_Resources.json, or an auth key held by another test."""
    monkeypatch.setattr(appinv, "cache_path", lambda: str(tmp_path / "MapTasker_Apps.json"))
    monkeypatch.setattr(resstore, "cache_path", lambda: str(tmp_path / "MapTasker_Resources.json"))
    monkeypatch.setattr(maputil2, "_auth_keys", {})
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    _load(_FIXTURE_XML)


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content

    def json(self) -> object:
        return json.loads(self.content)


class _FakeDevice:
    """Stands in for maputil2's `requests`: records every call, and answers a path check from a set of paths that exist."""

    def __init__(self, existing: set[str], *, installed: bool = False, answer: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.existing = existing
        self.installed = installed
        self.answer = answer
        self.imported_xml = ""
        self.uploads: list[tuple[str, str]] = []
        self.asked: list[str] = []

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("GET", url))
        if "/api/auth" in url:
            return _FakeResponse(200, b'{"key": "TESTKEY", "authorized": true}')
        if "/api/tasks" in url:
            listed = [{"name": deviceresource.CHECK_TASK_NAME, "running": False}] if self.installed else []
            return _FakeResponse(200, json.dumps(listed).encode())
        if "maptasker_check_out.txt" in url:
            return _FakeResponse(200, self._payload().encode())
        return _FakeResponse(404)

    def _payload(self) -> str:
        if self.answer is not None:
            return self.answer
        results = "".join(f"{'true' if path in self.existing else 'false'}{PAYLOAD_JOINER}" for path in self.asked)
        return f"MAPTASKER-EXISTS 1\nRESULTS\n{results}\nMAPTASKER-END\n"

    def post(self, url: str, **kwargs: object) -> _FakeResponse:
        self.calls.append(("POST", url))
        if "/api/import" in url:
            self.imported_xml = kwargs.get("data", b"").decode()  # type: ignore[union-attr]
            self.installed = True
        elif url.endswith("/upload"):
            (filename, (_, content, _kind)), *_ = kwargs["files"].items()  # type: ignore[union-attr]
            self.uploads.append((filename, content.decode()))
            self.asked = content.decode().split(PAYLOAD_JOINER)
        return _FakeResponse(200, b"{}")

    def delete(self, url: str, **_kwargs: object) -> _FakeResponse:
        self.calls.append(("DELETE", url))
        return _FakeResponse(404)


def _device(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> _FakeDevice:
    fake = _FakeDevice(**kwargs)  # type: ignore[arg-type]
    monkeypatch.setattr(maputil2, "requests", fake)
    return fake


# ##################################################################################
# The helper Task.
# ##################################################################################


def test_the_helper_task_reads_splits_loops_tests_and_writes() -> None:
    built = deviceresource.build_check_task(state=PrimeItems)
    assert not isinstance(built, str), built

    actions = built.task_element.findall("Action")
    codes = [action.findtext("code") for action in actions]

    # Read File, Variable Split, Variable Set, For, Variable Set, Test File, Variable Set, End For, then the file.
    assert codes == ["417", "590", "547", "39", "547", "342", "547", "40", "410", "410", "410", "410"]
    test_file = actions[5]
    assert test_file.find("Int[@sr='arg0']").attrib["val"] == "5", "Test File's Exists is option 5 of its Type"
    assert test_file.findtext("Str[@sr='arg1']") == "%mtres_path"
    assert test_file.find("Int[@sr='arg4']").attrib["val"] == "1", "Use Global Namespace, as real backups have it"
    assert actions[3].findtext("Str[@sr='arg1']") == "%mtres_in()"
    assert actions[0].findtext("Str[@sr='arg0']") == "Tasker/maptasker_check_in.txt"


def test_the_helper_task_writes_a_file_whose_first_write_truncates() -> None:
    built = deviceresource.build_check_task(state=PrimeItems)
    writes = [action for action in built.task_element.findall("Action") if action.findtext("code") == "410"]

    appends = [write.find("Int[@sr='arg2']").attrib["val"] for write in writes]
    assert appends == ["0", "1", "1", "1"]
    assert [write.findtext("Str[@sr='arg1']") for write in writes][-1] == "MAPTASKER-END"


# ##################################################################################
# Reading the answer.
# ##################################################################################


def _payload(*answers: str, header: str = "MAPTASKER-EXISTS 1", end: bool = True) -> str:
    line = "".join(f"{answer}{PAYLOAD_JOINER}" for answer in answers)
    return f"{header}\nRESULTS\n{line}\n" + ("MAPTASKER-END\n" if end else "")


def test_answers_are_matched_to_paths_by_position() -> None:
    answers, error = deviceresource.parse_check_payload(_payload("true", "false", "true"), ["a", "b", "c"])

    assert error == ""
    assert answers == {"a": True, "b": False, "c": True}


def test_an_answer_tasker_could_not_give_is_unknown_not_missing() -> None:
    """'unknown' is what the Task seeds the answer with, so a Test File that failed leaves it."""
    answers, _ = deviceresource.parse_check_payload(_payload("true", "unknown"), ["a", "b"])

    assert answers == {"a": True, "b": None}


def test_a_list_of_the_wrong_length_is_refused_not_zipped() -> None:
    """An answer attached to the wrong path looks exactly like a right one."""
    answers, error = deviceresource.parse_check_payload(_payload("true"), ["a", "b"])

    assert answers == {}
    assert "answered 1 of the 2 paths" in error


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        (_payload("true", header="SOMETHING ELSE"), "not a MapTasker path check"),
        (_payload("true", end=False), "incomplete"),
        ("", "not a MapTasker path check"),
    ],
)
def test_a_file_that_is_not_the_answer_is_refused(text: str, complaint: str) -> None:
    answers, error = deviceresource.parse_check_payload(text, ["a"])

    assert answers == {}
    assert complaint in error


# ##################################################################################
# The exchange.
# ##################################################################################


def test_the_paths_are_uploaded_before_the_task_runs_and_the_old_answer_is_deleted_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _device(monkeypatch, existing={"Tasker/there.txt"})

    code, result = deviceresource.check_paths_on_device(
        *ADDRESS, ["Tasker/there.txt", "Tasker/gone.txt"], state=PrimeItems
    )

    assert (code, result) == (0, {"Tasker/there.txt": True, "Tasker/gone.txt": False})
    steps = [(verb, url.split("1821", 1)[1]) for verb, url in fake.calls]
    upload = steps.index(("POST", "/upload"))
    delete = next(i for i, (verb, path) in enumerate(steps) if verb == "DELETE" and "maptasker_check_out" in path)
    run = steps.index(("POST", "/api/tasks"))
    read = next(i for i, (verb, path) in enumerate(steps) if verb == "GET" and "maptasker_check_out" in path)
    assert upload < run
    assert delete < run < read


def test_the_paths_travel_in_a_file_the_task_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _device(monkeypatch, existing=set())

    deviceresource.check_paths_on_device(*ADDRESS, ["a b/c.txt", "d.txt"], state=PrimeItems)

    assert fake.uploads == [("maptasker_check_in.txt", f"a b/c.txt{PAYLOAD_JOINER}d.txt")]


def test_a_path_used_in_many_places_is_asked_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _device(monkeypatch, existing={"a"})

    _, result = deviceresource.check_paths_on_device(*ADDRESS, ["a", "a", "b", "a"], state=PrimeItems)

    assert fake.uploads[0][1] == f"a{PAYLOAD_JOINER}b"
    assert result == {"a": True, "b": False}


def test_an_installed_helper_task_is_not_imported_again(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _device(monkeypatch, existing={"a"}, installed=True)

    deviceresource.check_paths_on_device(*ADDRESS, ["a"], state=PrimeItems)

    assert not any("/api/import" in url for _verb, url in fake.calls)


def test_the_task_imported_is_the_one_meant(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _device(monkeypatch, existing={"a"})

    deviceresource.check_paths_on_device(*ADDRESS, ["a"], state=PrimeItems)

    assert deviceresource.CHECK_TASK_NAME in fake.imported_xml


def test_nothing_to_ask_means_no_conversation_with_the_device(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _device(monkeypatch, existing=set())

    assert deviceresource.check_paths_on_device(*ADDRESS, [], state=PrimeItems) == (0, {})
    assert fake.calls == []


def test_a_device_whose_answer_does_not_line_up_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _device(monkeypatch, existing=set(), answer=_payload("true"))

    code, result = deviceresource.check_paths_on_device(*ADDRESS, ["a", "b"], state=PrimeItems)

    assert code == 8
    assert "answered 1 of the 2" in str(result)


# ##################################################################################
# The whole check.
# ##################################################################################


class _Apps:
    """What the device reports installed, in place of the real fetch."""

    def __init__(self, packages: set[str], *, fail: str = "") -> None:
        self.packages = packages
        self.fail = fail
        self.fetched = 0

    def fetch(self, ip_address: str, ip_port: str, state: object) -> tuple[int, str]:  # noqa: ARG002
        self.fetched += 1
        if self.fail:
            return 8, self.fail
        appinv._store_fetched_apps(  # noqa: SLF001
            f"{ip_address}:{ip_port}",
            [appinv.AppEntry(pkg=package, label="", cls="") for package in sorted(self.packages)],
        )
        return 0, "ok"


def _check(
    monkeypatch: pytest.MonkeyPatch,
    *,
    existing: set[str],
    packages: set[str],
    scenes: list[str],
    apps_fail: str = "",
    scenes_fail: str = "",
    refresh: bool = True,
) -> tuple[deviceresource.Outcome, _Apps]:
    _device(monkeypatch, existing=existing)
    apps = _Apps(packages, fail=apps_fail)
    monkeypatch.setattr(deviceinv, "fetch_apps_from_device", apps.fetch)
    monkeypatch.setattr(
        deviceresource,
        "fetch_tasker_object_names",
        lambda _ip, _port, state: (8, scenes_fail, {}) if scenes_fail else (0, "", {"Scene": scenes}),  # noqa: ARG005
    )
    outcome = deviceresource.check_device(*ADDRESS, resrefs.collect(PrimeItems), refresh_apps=refresh, state=PrimeItems)
    return outcome, apps


def test_a_check_asks_about_files_apps_and_scenes_and_keeps_the_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome, apps = _check(
        monkeypatch,
        existing={"Tasker/there.txt"},
        packages={"com.here.app"},
        scenes=["Panel"],
    )

    assert outcome.errors == []
    assert (outcome.asked, outcome.answered, outcome.missing) == (6, 6, 3)
    assert apps.fetched == 1
    stored = resstore.answers()[DEVICE][1]
    assert stored == {
        ("path", "Tasker/there.txt"): True,
        ("path", "Tasker/gone.txt"): False,
        ("scene", "Panel"): True,
        ("scene", "Lost"): False,
        ("app", "com.here.app"): True,
        ("app", "com.absent.app"): False,
    }


def test_what_the_check_stored_is_what_the_health_check_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    _check(monkeypatch, existing={"Tasker/there.txt"}, packages={"com.here.app"}, scenes=["Panel"])

    wheres = sorted(problem.where for problem in resrefs.lint_problems(PrimeItems))

    assert wheres == ["App com.absent.app", "File 'Tasker/gone.txt'", "Scene 'Lost'"]


def test_the_app_list_already_fetched_is_used_when_not_asked_to_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    appinv._store_fetched_apps(DEVICE, [appinv.AppEntry(pkg="com.here.app", label="", cls="")])  # noqa: SLF001
    outcome, apps = _check(monkeypatch, existing=set(), packages={"com.never.used"}, scenes=["Panel"], refresh=False)

    assert apps.fetched == 0
    assert resstore.answers()[DEVICE][1][("app", "com.here.app")] is True
    assert outcome.errors == []


def test_a_failure_to_fetch_apps_keeps_the_answers_about_files_and_scenes(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome, _ = _check(
        monkeypatch,
        existing={"Tasker/there.txt"},
        packages=set(),
        scenes=["Panel"],
        apps_fail="Tasker said no.",
    )

    assert outcome.errors == ["Apps: Tasker said no."]
    assert outcome.answered == 4
    assert ("app", "com.absent.app") not in resstore.answers()[DEVICE][1]


def test_a_failure_to_list_scenes_keeps_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    outcome, _ = _check(
        monkeypatch,
        existing={"Tasker/there.txt"},
        packages={"com.here.app"},
        scenes=[],
        scenes_fail="no scenes for you",
    )

    assert outcome.errors == ["Scenes: no scenes for you"]
    assert ("scene", "Panel") not in resstore.answers()[DEVICE][1]
    assert outcome.answered == 4


def test_nothing_answered_stores_nothing_so_the_last_good_answers_survive(monkeypatch: pytest.MonkeyPatch) -> None:
    resstore.store(DEVICE, {("path", "Tasker/there.txt"): True})
    monkeypatch.setattr(maputil2, "requests", None)  # any contact with the network would fail loudly
    monkeypatch.setattr(deviceinv, "fetch_apps_from_device", lambda *_a, **_k: (8, "unreachable"))
    monkeypatch.setattr(deviceresource, "check_paths_on_device", lambda *_a, **_k: (8, "unreachable"))
    monkeypatch.setattr(deviceresource, "fetch_tasker_object_names", lambda *_a, **_k: (8, "unreachable", {}))

    outcome = deviceresource.check_device(*ADDRESS, resrefs.collect(PrimeItems), state=PrimeItems)

    assert outcome.answered == 0
    assert len(outcome.errors) == 3
    assert resstore.answers()[DEVICE][1] == {("path", "Tasker/there.txt"): True}


def test_a_check_without_an_address_says_what_is_needed() -> None:
    outcome = deviceresource.check_device("", "", resrefs.collect(PrimeItems), state=PrimeItems)

    assert outcome.errors == ["An Android IP address and port are needed."]
    assert resstore.answers() == {}
