"""Each helper Task MapTasker puts on the phone, run against a phone whose helper writes the answer file it should.

tests/test_fake_tasker.py covers the conversation (key, upload, import, run).  This covers what each helper is FOR:
the object lists, a fresh backup to compare ids with, the installed applications, the paths that exist, opening Tasker.
Every one is the same exchange -- install if missing, clear the last answer, run, poll, parse -- so each is tried with
a good answer and with the answers a phone really gives that are not: none at all, one that is not ours, one cut short.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import maputil2
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import (
    devicecheck,
    deviceinv,
    deviceoffer,
    deviceresource,
    devicetask,
    deviceverify,
)

from tests.faketasker import FakeTasker

if TYPE_CHECKING:
    from collections.abc import Iterator

END = "MAPTASKER-END\n"
JOIN = devicetask.PAYLOAD_JOINER


@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch, loaded: None) -> Iterator[FakeTasker]:
    """A listening phone, with every wait cut to nothing and every poll cut to a few tries."""
    monkeypatch.setattr(maputil2, "AUTH_KEY_RETRY_SECONDS", 0)
    monkeypatch.setattr(maputil2, "_UPLOAD_SETTLE_SECONDS", 0)
    monkeypatch.setattr(devicetask, "RESULT_POLL_SECONDS", 0)
    for module, name in (
        (devicetask, "_OBJECT_LIST_POLL_ATTEMPTS"),
        (devicecheck, "_ID_CHECK_POLL_ATTEMPTS"),
        (deviceinv, "_RESULT_POLL_ATTEMPTS"),
        (deviceresource, "_POLL_ATTEMPTS"),
        (deviceoffer, "_OPEN_POLL_ATTEMPTS"),
    ):
        monkeypatch.setattr(module, name, 2)
    maputil2._auth_keys.clear()
    fake = FakeTasker().up()
    yield fake
    fake.down()
    maputil2._auth_keys.clear()


# ##################################################################################
# Every Project, Profile, Scene and Task Tasker has
# ##################################################################################
def _objects(projects: str = "Home", profiles: str = "", scenes: str = "", tasks: str = "Opener") -> str:
    return f"MAPTASKER-OBJECTS 1\nPROJECTS\n{projects}\nPROFILES\n{profiles}\nSCENES\n{scenes}\nTASKS\n{tasks}\n{END}"


def test_the_objects_tasker_has_are_listed_by_kind(phone: FakeTasker) -> None:
    phone.writes(
        devicetask.OBJECT_LIST_TASK_NAME,
        "/Tasker/maptasker_objects.txt",
        _objects(f"Home{JOIN}Work", f"Morning{JOIN}Night", "%mtscenes", f"Opener{JOIN}Closer"),
        installed=False,
    )

    code, message, names = devicetask.fetch_tasker_object_names(phone.address, phone.port, state=PrimeItems)

    assert (code, message) == (0, "")
    assert names == {
        "Project": ["Home", "Work"],
        "Profile": ["Morning", "Night"],
        "Scene": [],
        "Task": ["Opener", "Closer"],
    }
    assert devicetask.OBJECT_LIST_TASK_NAME in phone.tasks


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("not an object list\n" + END, "not a MapTasker object list"),
        ("MAPTASKER-OBJECTS 1\nPROJECTS\nHome\n", "never finished being written"),
        (_objects(projects="%mtprojects"), "did not report any Projects"),
        (_objects(tasks="%mttasks"), "did not report any Tasks"),
        ("MAPTASKER-OBJECTS 1\nPROJECTS\nHome\n" + END, "has no Profiles section"),
    ],
)
def test_an_object_list_the_phone_gets_wrong_ends_in_a_message(phone: FakeTasker, answer: str, expected: str) -> None:
    phone.writes(devicetask.OBJECT_LIST_TASK_NAME, "/Tasker/maptasker_objects.txt", answer)

    code, message, names = devicetask.fetch_tasker_object_names(phone.address, phone.port, state=PrimeItems)

    assert code == 8 and names == {}
    assert expected in message


def test_a_phone_that_never_writes_the_object_list_is_reported(phone: FakeTasker) -> None:
    phone.on_task(devicetask.OBJECT_LIST_TASK_NAME, lambda _fake, _body: None)

    code, message, _ = devicetask.fetch_tasker_object_names(phone.address, phone.port, state=PrimeItems)

    assert code == 8
    assert "did not produce an object list" in message


def test_an_object_list_asked_with_no_address_is_refused_before_the_phone_is_asked(phone: FakeTasker) -> None:
    code, message, _ = devicetask.fetch_tasker_object_names("", "", state=PrimeItems)

    assert code == 8
    assert "address and port" in message
    assert phone.requests == []


def _run(phone: FakeTasker, name: str, **keywords: object) -> devicetask.TaskRunResult:
    return devicetask.run_task_for_result(phone.address, phone.port, name, state=PrimeItems, **keywords)  # type: ignore[arg-type]


def test_a_task_is_run_for_its_result(phone: FakeTasker) -> None:
    phone.on_task("Greeter", lambda _fake, body: f"hello {body.get('par1', '')} {body.get('par2', '')}".strip())

    result = _run(phone, "Greeter", par1="there", par2="you")

    assert (result.ok, result.output, result.error) == (True, "hello there you", "")
    assert result.seconds >= 0


def test_a_name_the_phones_handler_cannot_find_is_run_through_the_runner_helper(phone: FakeTasker) -> None:
    """'$Taskaroo' is a regular expression to the handler; the runner helper is told the name in a variable instead."""
    phone.writes(devicetask.OBJECT_LIST_TASK_NAME, "/Tasker/maptasker_objects.txt", _objects(tasks="$Taskaroo"))
    phone.on_task(devicetask.RUN_TASK_HELPER_NAME, lambda _fake, body: f"ran {body['variables']['mt_run_task']}")

    result = _run(phone, "$Taskaroo")

    assert (result.ok, result.output) == (True, "ran $Taskaroo")


def test_such_a_name_the_phone_does_not_list_is_said_to_be_missing_without_running_the_helper(
    phone: FakeTasker,
) -> None:
    phone.writes(devicetask.OBJECT_LIST_TASK_NAME, "/Tasker/maptasker_objects.txt", _objects(tasks="Other"))
    phone.on_task(devicetask.RUN_TASK_HELPER_NAME, lambda _fake, _body: pytest.fail("a helper run on a missing Task"))

    result = _run(phone, "$Taskaroo")

    assert result.ok is False and "has no Task named '$Taskaroo'" in result.error


def test_the_runner_helper_is_not_run_when_the_phone_cannot_say_what_it_has(phone: FakeTasker) -> None:
    phone.writes(devicetask.OBJECT_LIST_TASK_NAME, "/Tasker/maptasker_objects.txt", "junk\n" + END)

    result = _run(phone, "$Taskaroo")

    assert result.ok is False and result.error.startswith("Could not check that Tasker has '$Taskaroo'")


def test_a_task_the_phone_does_not_have_is_said_to_be_missing_and_where_to_put_it(phone: FakeTasker) -> None:
    result = _run(phone, "Nothing Like It")

    assert result.ok is False
    assert "has no Task named 'Nothing Like It'" in result.error
    assert "Save To Android" in result.error


def test_a_task_that_outlasts_the_wait_is_said_to_be_possibly_still_running(
    phone: FakeTasker, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    phone.on_task("Slow", lambda _fake, _body: time.sleep(0.5))

    result = _run(phone, "Slow", timeout=0.05)

    assert result.ok is False
    assert "still" in result.error.lower()


def test_no_task_name_is_not_a_run(phone: FakeTasker) -> None:
    assert _run(phone, "  ").error == "There is no Task name to run."
    assert phone.requests == []


# ##################################################################################
# A fresh backup made on the phone, to compare ids with
# ##################################################################################
_DEVICE_BACKUP = (
    b"<TaskerData><Project sr='proj0'><name>Home</name><id>p1</id></Project>"
    b"<Task sr='task5'><id>5</id><nme>Opener</nme></Task></TaskerData>"
)


def _backup_helper(
    phone: FakeTasker, *, header: str = "MAPTASKER-BACKUP 1", backup: bytes | None = _DEVICE_BACKUP
) -> None:
    def helper(fake: FakeTasker, _body: dict) -> None:
        if backup is not None:
            fake.files["/Tasker/maptasker_idcheck.xml"] = backup
        fake.files["/Tasker/maptasker_idcheck.txt"] = f"{header}\n{END}".encode()

    phone.handlers[devicecheck.ID_CHECK_TASK_NAME] = helper


def test_a_fresh_backup_is_read_from_the_phone_and_then_removed_from_it(phone: FakeTasker) -> None:
    _backup_helper(phone)

    code, message, content = devicecheck.fetch_device_backup(phone.address, phone.port, state=PrimeItems)

    assert (code, message, content) == (0, "", _DEVICE_BACKUP)
    assert "/Tasker/maptasker_idcheck.xml" not in phone.files, "a copy of the configuration is not left behind"


def test_the_backup_is_removed_from_the_phone_even_when_it_cannot_be_downloaded(phone: FakeTasker) -> None:
    _backup_helper(phone, backup=None)

    code, _message, content = devicecheck.fetch_device_backup(phone.address, phone.port, state=PrimeItems)

    assert code == 6 and content == b""
    assert phone.seen("DELETE", "/api/file/Tasker/maptasker_idcheck.xml")


def test_a_backup_result_that_is_not_ours_is_not_believed(phone: FakeTasker) -> None:
    _backup_helper(phone, header="SOMETHING-ELSE")

    code, message, _ = devicecheck.fetch_device_backup(phone.address, phone.port, state=PrimeItems)

    assert code == 8
    assert "not a MapTasker backup result" in message


def test_a_phone_that_never_makes_the_backup_is_reported(phone: FakeTasker) -> None:
    phone.on_task(devicecheck.ID_CHECK_TASK_NAME, lambda _fake, _body: None)

    code, message, _ = devicecheck.fetch_device_backup(phone.address, phone.port, state=PrimeItems)

    assert code == 8
    assert "did not produce a backup" in message


def test_ids_and_names_are_compared_with_the_phones_own_backup(phone: FakeTasker) -> None:
    _backup_helper(phone)
    sent = (
        "<TaskerData><Project sr='proj0'><name>Home</name><id>other</id></Project>"
        "<Task sr='task5'><id>5</id><nme>Different</nme></Task></TaskerData>"
    )

    check, findings, problem = devicecheck.check_against_device_backup(
        phone.address, phone.port, sent, state=PrimeItems
    )

    assert problem == ""
    assert check is not None and check.present == {"Project": ["Home"], "Task": []}
    assert [(finding.kind, finding.object_id, finding.is_clash) for finding in findings] == [
        ("Project", "other", False),
        ("Task", "5", True),
    ], "Home is on the phone under another id, and id 5 is there on a Task of another name"


def test_a_phone_backup_that_is_not_tasker_xml_is_reported_as_unreadable(phone: FakeTasker) -> None:
    _backup_helper(phone, backup=b"<html/>")

    check, findings, problem = devicecheck.check_against_device_backup(
        phone.address, phone.port, "<TaskerData/>", state=PrimeItems
    )

    assert (check, findings) == (None, [])
    assert "could not be read" in problem


def test_nothing_to_compare_asks_the_phone_nothing(phone: FakeTasker) -> None:
    check, findings, problem = devicecheck.check_against_device_backup(
        phone.address, phone.port, "<<not xml", state=PrimeItems
    )

    assert (findings, problem) == ([], "")
    assert check is not None
    assert phone.requests == []


# ##################################################################################
# The applications installed on the phone
# ##################################################################################
_APPS = f"MAPTASKER-APPS 1\nPACKAGES\ncom.a{JOIN}com.b\nLABELS\nAlpha{JOIN}Beta\nACTIVITIES\n.A{JOIN}.B\n{END}"


def test_the_installed_applications_are_fetched_and_remembered(
    phone: FakeTasker, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored: list[tuple[str, list]] = []
    monkeypatch.setattr(deviceinv, "store_fetched_apps", lambda key, entries: stored.append((key, entries)) or "")
    phone.writes(deviceinv.HELPER_TASK_NAME, "/Tasker/maptasker_apps.txt", _APPS, installed=False)

    code, message = deviceinv.fetch_apps_from_device(phone.address, phone.port, state=PrimeItems)

    assert code == 0
    assert "2 applications fetched" in message and "(2 with names)" in message
    [(key, entries)] = stored
    assert key == f"{phone.address}:{phone.port}"
    assert [(entry.pkg, entry.label, entry.cls) for entry in entries] == [
        ("com.a", "Alpha", ".A"),
        ("com.b", "Beta", ".B"),
    ]


def test_applications_that_could_not_be_saved_for_next_time_say_so(
    phone: FakeTasker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deviceinv, "store_fetched_apps", lambda key, entries: "the disk is full")
    phone.writes(deviceinv.HELPER_TASK_NAME, "/Tasker/maptasker_apps.txt", _APPS)

    code, message = deviceinv.fetch_apps_from_device(phone.address, phone.port, state=PrimeItems)

    assert code == 0
    assert "could not be saved for next time: the disk is full" in message


def test_packages_with_no_names_are_said_to_be_package_names_only(
    phone: FakeTasker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deviceinv, "store_fetched_apps", lambda key, entries: "")
    phone.writes(deviceinv.HELPER_TASK_NAME, "/Tasker/maptasker_apps.txt", f"MAPTASKER-APPS 1\nPACKAGES\ncom.a\n{END}")

    assert "(package names only)" in deviceinv.fetch_apps_from_device(phone.address, phone.port, state=PrimeItems)[1]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("rubbish\n" + END, "not a MapTasker application list"),
        ("MAPTASKER-APPS 1\nPACKAGES\n%mtapps_pkg\n" + END, "no applications"),
    ],
)
def test_an_application_list_the_phone_gets_wrong_ends_in_a_message(
    phone: FakeTasker, answer: str, expected: str
) -> None:
    phone.writes(deviceinv.HELPER_TASK_NAME, "/Tasker/maptasker_apps.txt", answer)

    code, message = deviceinv.fetch_apps_from_device(phone.address, phone.port, state=PrimeItems)

    assert code == 8
    assert expected in message


def test_fetching_applications_with_no_address_asks_nothing(phone: FakeTasker) -> None:
    assert deviceinv.fetch_apps_from_device(" ", "", state=PrimeItems)[0] == 8
    assert phone.requests == []


# ##################################################################################
# Which paths exist on the phone
# ##################################################################################
def _exists_helper(phone: FakeTasker, answers: str) -> None:
    phone.writes(
        deviceresource.CHECK_TASK_NAME,
        "/Tasker/maptasker_check_out.txt",
        f"MAPTASKER-EXISTS 1\nRESULTS\n{answers}\n{END}",
        installed=False,
    )


def test_each_path_is_reported_present_absent_or_unknown(phone: FakeTasker) -> None:
    _exists_helper(phone, JOIN.join(["true", "false", "maybe"]))

    code, answers = deviceresource.check_paths_on_device(
        phone.address, phone.port, ["/a", "/b", "/c", "/a"], state=PrimeItems
    )

    assert code == 0
    assert answers == {"/a": True, "/b": False, "/c": None}, "a path asked twice is asked once"
    assert phone.files["/Tasker/maptasker_check_in.txt"] == JOIN.join(["/a", "/b", "/c"]).encode()


def test_no_paths_ask_the_phone_nothing(phone: FakeTasker) -> None:
    assert deviceresource.check_paths_on_device(phone.address, phone.port, [], state=PrimeItems) == (0, {})
    assert phone.requests == []


def test_fewer_answers_than_paths_are_refused_rather_than_matched_wrongly(phone: FakeTasker) -> None:
    _exists_helper(phone, "true")

    code, message = deviceresource.check_paths_on_device(phone.address, phone.port, ["/a", "/b"], state=PrimeItems)

    assert code == 8
    assert "answered 1 of the 2 paths" in str(message)


def test_a_path_check_that_is_not_ours_is_not_believed(phone: FakeTasker) -> None:
    phone.writes(deviceresource.CHECK_TASK_NAME, "/Tasker/maptasker_check_out.txt", "junk\n" + END)

    code, message = deviceresource.check_paths_on_device(phone.address, phone.port, ["/a"], state=PrimeItems)

    assert code == 8
    assert "not a MapTasker path check" in str(message)


# ##################################################################################
# A phone that cannot be asked at all
# ##################################################################################
@pytest.mark.parametrize(
    "ask",
    [
        lambda p: devicetask.fetch_tasker_object_names(p.address, p.port, state=PrimeItems)[0],
        lambda p: devicecheck.fetch_device_backup(p.address, p.port, state=PrimeItems)[0],
        lambda p: deviceinv.fetch_apps_from_device(p.address, p.port, state=PrimeItems)[0],
        lambda p: deviceresource.check_paths_on_device(p.address, p.port, ["/a"], state=PrimeItems)[0],
        lambda p: deviceverify.fetch_task_names_from_device(p.address, p.port)[0],
    ],
    ids=["objects", "backup", "apps", "paths", "task names"],
)
def test_a_phone_that_will_not_authorize_ends_every_helper_exchange_with_a_code(phone: FakeTasker, ask) -> None:
    phone.refuse_auth = 99

    assert ask(phone) == 8
    assert phone.seen("POST", "/api/import") == [], "no helper is put on a phone that has not authorized"
