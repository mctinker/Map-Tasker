"""tools/device_check.py: the checks that try MapTasker's device features on a real phone, run here on the fake one.

The fake phone answers the way the real one is meant to, so every check should pass; what is tested is that each check asks
the right thing, reads the answer the right way, notices when the phone does something else, and leaves the phone as it was.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import maputil2
from maptasker.src.device import deviceoffer, deviceserver, devicetask, deviceverify

from tests.faketasker import FakeTasker

if TYPE_CHECKING:
    from collections.abc import Iterator

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "device_check.py"
_spec = importlib.util.spec_from_file_location("device_check", _TOOL)
assert _spec is not None
assert _spec.loader is not None
dc = importlib.util.module_from_spec(_spec)
sys.modules["device_check"] = dc
_spec.loader.exec_module(dc)

END = "MAPTASKER-END\n"
BY_ID = {check.id: check for check in dc.CHECKS}


@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch, loaded: None) -> Iterator[FakeTasker]:
    """A listening phone with the HTTP API and the Http Server Example, every wait cut to nothing."""
    monkeypatch.setattr(maputil2, "AUTH_KEY_RETRY_SECONDS", 0)
    monkeypatch.setattr(maputil2, "_UPLOAD_SETTLE_SECONDS", 0)
    monkeypatch.setattr(devicetask, "RESULT_POLL_SECONDS", 0)
    monkeypatch.setattr(deviceverify, "RESULT_POLL_SECONDS", 0)
    monkeypatch.setattr(deviceoffer, "_OPEN_POLL_ATTEMPTS", 2)
    maputil2._auth_keys.clear()
    fake = FakeTasker().up()
    fake.profiles |= set(deviceserver.SERVER_PROFILES)
    yield fake
    fake.down()
    maputil2._auth_keys.clear()


def _device(phone: FakeTasker, answers: list[int] | None = None, *, backup: bool = True):
    given = iter(answers or [])
    return dc.Device(phone.address, phone.port, lambda _question, _options: next(given, -1), has_backup=backup)


def test_every_check_has_a_unique_id_and_says_what_it_settles() -> None:
    assert len(BY_ID) == len(dc.CHECKS)
    assert all(check.title and check.settles for check in dc.CHECKS)


@pytest.mark.parametrize("name", ["api-key", "file-route", "server-project", "lists", "upload-round-trip"])
def test_the_automatic_checks_pass_on_a_phone_that_works(phone: FakeTasker, name: str) -> None:
    outcome = BY_ID[name].run(_device(phone))

    assert outcome.status == dc.PASS, outcome.detail


def test_the_upload_round_trip_leaves_nothing_on_the_phone(phone: FakeTasker) -> None:
    BY_ID["upload-round-trip"].run(_device(phone))

    assert "/Tasker/maptasker_check.txt" not in phone.files


def test_a_phone_without_the_server_project_fails_that_check(phone: FakeTasker) -> None:
    phone.profiles.clear()

    outcome = BY_ID["server-project"].run(_device(phone))

    assert outcome.status == dc.FAIL
    assert "not both" in outcome.detail


def test_a_phone_that_refuses_the_key_fails_it_with_the_phones_message(phone: FakeTasker) -> None:
    phone.refuse_auth = 100

    outcome = BY_ID["api-key"].run(_device(phone))

    assert outcome.status == dc.FAIL
    assert outcome.detail


def test_the_helper_round_trip_installs_runs_and_reads_a_helper_task(phone: FakeTasker) -> None:
    objects = f"MAPTASKER-OBJECTS 1\nPROJECTS\nHome\nPROFILES\nDawn\nSCENES\n%mtscenes\nTASKS\nMorning\n{END}"
    phone.writes(devicetask.OBJECT_LIST_TASK_NAME, "/Tasker/maptasker_objects.txt", objects, installed=False)

    outcome = BY_ID["helper-round-trip"].run(_device(phone))

    assert outcome.status == dc.PASS, outcome.detail
    assert devicetask.OBJECT_LIST_TASK_NAME in phone.tasks


@pytest.mark.parametrize("name", ["open-with-profile", "open-with-project"])
def test_the_asked_checks_pass_when_tasker_is_what_came_up(phone: FakeTasker, name: str) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE if name.endswith("profile") else deviceoffer.OPEN_PROJECT_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)

    outcome = BY_ID[name].run(_device(phone, [0]))

    assert outcome.status == dc.PASS, outcome.detail


def test_a_chooser_without_tasker_in_it_is_a_failure(phone: FakeTasker) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)

    outcome = BY_ID["open-with-profile"].run(_device(phone, [2]))

    assert outcome.status == dc.FAIL
    assert "NOT in it" in outcome.detail


def test_an_unanswered_question_is_a_skip_not_a_pass(phone: FakeTasker) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)

    assert BY_ID["open-with-profile"].run(_device(phone, [])).status == dc.SKIP


def test_the_staged_file_is_taken_away_again(phone: FakeTasker) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)

    BY_ID["open-with-profile"].run(_device(phone, [0]))

    assert not [path for path in phone.files if dc.CHECK_NAME in path]


def test_the_share_link_check_runs_the_helper_and_reports_what_the_person_saw(phone: FakeTasker) -> None:
    phone.handlers[deviceserver.OPEN_SHARE_TASK_NAME] = lambda _fake, _body: None

    outcome = BY_ID["share-link"].run(_device(phone, [1]))

    assert outcome.status == dc.PASS
    assert outcome.detail == "the browser"
    assert deviceserver.OPEN_SHARE_TASK_NAME in phone.tasks


def test_a_check_that_needs_a_backup_is_skipped_without_one(phone: FakeTasker) -> None:
    results = dc.run_checks(_device(phone, backup=False), [BY_ID["helper-round-trip"], BY_ID["file-route"]])

    assert [(r["id"], r["status"]) for r in results] == [("helper-round-trip", dc.SKIP), ("file-route", dc.PASS)]


def test_a_check_that_breaks_is_a_failed_result_and_the_run_goes_on(phone: FakeTasker) -> None:
    def broken(_device):
        message = "boom"
        raise RuntimeError(message)

    results = dc.run_checks(_device(phone), [dc.Check("broken", "t", "s", broken), BY_ID["file-route"]])

    assert [r["status"] for r in results] == [dc.FAIL, dc.PASS]
    assert "RuntimeError: boom" in results[0]["detail"]


def test_main_keeps_each_run_in_the_results_file(
    phone: FakeTasker, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    kept = tmp_path / "results.json"
    arguments = ["--ip", phone.address, "--port", phone.port, "--only", "api-key,file-route", "--results", str(kept)]

    assert dc.main(arguments) == 0
    assert dc.main(arguments) == 0

    runs = json.loads(kept.read_text(encoding="utf-8"))
    assert len(runs) == 2
    assert [c["id"] for c in runs[0]["checks"]] == ["api-key", "file-route"]
    assert runs[0]["device"] == f"{phone.address}:{phone.port}"
    assert "did not fail" in capsys.readouterr().out


def test_main_exits_1_when_a_check_fails(phone: FakeTasker, tmp_path: Path) -> None:
    phone.profiles.clear()

    status = dc.main(
        ["--ip", phone.address, "--port", phone.port, "--only", "server-project", "--results", str(tmp_path / "r.json")]
    )

    assert status == 1


def test_list_says_what_each_check_settles(capsys: pytest.CaptureFixture[str]) -> None:
    assert dc.main(["--list"]) == 0

    output = capsys.readouterr().out
    assert all(check.id in output and check.settles in output for check in dc.CHECKS)


def test_an_unknown_check_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        dc.main(["--ip", "1.2.3.4", "--only", "nope"])
    assert "no such check" in capsys.readouterr().err


def test_the_import_probe_passes_and_says_what_it_left_to_delete(phone: FakeTasker) -> None:
    outcome = BY_ID["import-probe"].run(_device(phone))

    assert outcome.status == dc.PASS, outcome.detail
    assert "first: accepted; same name, new id: accepted; new name, same id: accepted" in outcome.detail
    assert dc.CHECK_NAME in outcome.detail


def test_the_import_probe_reports_which_repeat_the_phone_refused(phone: FakeTasker) -> None:
    phone.import_script = [200, 400, 200]

    outcome = BY_ID["import-probe"].run(_device(phone))

    assert outcome.status == dc.PASS
    assert "same name, new id: Request failed" in outcome.detail
    assert "new name, same id: accepted" in outcome.detail


def test_a_phone_that_takes_no_import_fails_the_probe(phone: FakeTasker) -> None:
    phone.import_answers = 400

    outcome = BY_ID["import-probe"].run(_device(phone))

    assert outcome.status == dc.FAIL
    assert "first: Request failed" in outcome.detail
