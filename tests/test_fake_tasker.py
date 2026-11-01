"""The device layer against a Tasker that answers over a real socket (tests/faketasker.py).

Everything here goes through MapTasker's own `requests` calls to 127.0.0.1, so what is checked is the conversation: the
key asked for, the upload and its read-back, the import and its confirmation, the files the helper Tasks leave.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import maputil2
from maptasker.src.device import deviceverify

from tests.faketasker import KEY, FakeTasker

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeTasker]:
    """A phone that is listening, with the waits between retries cut to nothing and no key remembered."""
    monkeypatch.setattr(maputil2, "AUTH_KEY_RETRY_SECONDS", 0)
    monkeypatch.setattr(maputil2, "_UPLOAD_SETTLE_SECONDS", 0)
    maputil2._auth_keys.clear()
    fake = FakeTasker().up()
    yield fake
    fake.down()
    maputil2._auth_keys.clear()


# ##################################################################################
# The key
# ##################################################################################
def test_the_phone_hands_over_its_key(phone: FakeTasker) -> None:
    assert maputil2.get_android_auth_key(phone.address, phone.port) == (0, KEY)


def test_a_phone_that_refuses_at_first_is_asked_again(phone: FakeTasker) -> None:
    phone.refuse_auth = 2

    assert maputil2.get_android_auth_key(phone.address, phone.port) == (0, KEY)
    assert len(phone.seen("GET", "/api/auth")) == 3


def test_a_phone_that_never_authorizes_ends_in_a_message(phone: FakeTasker) -> None:
    phone.refuse_auth = 99

    code, message = maputil2.get_android_auth_key(phone.address, phone.port)

    assert code == 8
    assert "did not authorize" in message
    assert len(phone.seen("GET", "/api/auth")) == maputil2.AUTH_KEY_MAX_ATTEMPTS


def test_the_key_is_asked_for_once_and_held(phone: FakeTasker) -> None:
    assert maputil2.auth_key_for(phone.address, phone.port) == (0, KEY)
    assert maputil2.auth_key_for(phone.address, phone.port) == (0, KEY)

    assert len(phone.seen("GET", "/api/auth")) == 1


def test_a_phone_that_has_gone_away_is_reported_not_raised(phone: FakeTasker) -> None:
    port = phone.port
    phone.down()

    code, message = maputil2.get_android_auth_key(phone.address, port)

    assert code == 8
    assert "Connection error" in message


# ##################################################################################
# Files
# ##################################################################################
def test_a_file_is_read_and_a_missing_one_is_not_found(phone: FakeTasker) -> None:
    phone.files["/Tasker/backup.xml"] = b"<TaskerData/>"

    assert maputil2.http_request(phone.address, phone.port, "/Tasker/backup.xml", "file", "") == (0, b"<TaskerData/>")
    assert maputil2.http_request(phone.address, phone.port, "/Tasker/none.xml", "file", "")[0] == 6
    assert maputil2.read_android_file(phone.address, phone.port, "/Tasker/backup.xml") == (True, b"<TaskerData/>")
    assert maputil2.read_android_file(phone.address, phone.port, "/Tasker/none.xml") == (False, b"")


def test_an_upload_lands_where_it_was_sent_and_reads_back(phone: FakeTasker) -> None:
    assert maputil2.http_upload_request(phone.address, phone.port, "Tasker/tasks", "Opener.tsk.xml", b"<x/>") == (0, "")

    assert phone.files["/Tasker/tasks/Opener.tsk.xml"] == b"<x/>"
    assert maputil2.read_back_uploaded_file(phone.address, phone.port, "/Tasker/tasks/Opener.tsk.xml", b"<x/>") == (
        0,
        b"<x/>",
    )


def test_a_write_still_settling_is_waited_for(phone: FakeTasker) -> None:
    phone.files["/Tasker/late.txt"] = b"here"
    phone.slow_reads["/Tasker/late.txt"] = 2

    assert maputil2.read_back_uploaded_file(phone.address, phone.port, "/Tasker/late.txt", b"here")[0] == 0


def test_a_write_that_never_arrives_is_not_called_confirmed(phone: FakeTasker) -> None:
    code, message = maputil2.read_back_uploaded_file(phone.address, phone.port, "/Tasker/never.txt", b"x")

    assert code == 8
    assert "could not confirm" in str(message)


def test_a_file_is_deleted_and_deleting_nothing_is_fine(phone: FakeTasker) -> None:
    phone.files["/Tasker/old.txt"] = b"stale"

    assert maputil2.http_delete_request(phone.address, phone.port, "/Tasker/old.txt", KEY) == (0, "")
    assert "/Tasker/old.txt" not in phone.files
    assert maputil2.http_delete_request(phone.address, phone.port, "/Tasker/old.txt", KEY) == (0, "")


# ##################################################################################
# Importing and asking what Tasker has
# ##################################################################################
_TASK = b"<TaskerData><Task sr='task1'><id>1</id><nme>Opener</nme></Task></TaskerData>"


def test_an_imported_task_is_there_when_tasker_is_asked(phone: FakeTasker) -> None:
    code, _ = maputil2.request_with_auth_key(
        phone.address,
        phone.port,
        lambda key: maputil2.http_post_request(phone.address, phone.port, "", "api/import", _TASK, key),
    )

    assert code == 0
    assert deviceverify.task_names_on_device(phone.address, phone.port, ["Opener", "Other"]) == (0, "", ["Opener"])


def test_a_key_the_phone_rejects_is_replaced_once(phone: FakeTasker) -> None:
    maputil2.auth_key_for(phone.address, phone.port)
    phone.reject_keys = 1

    code, _ = maputil2.request_with_auth_key(
        phone.address,
        phone.port,
        lambda key: maputil2.http_post_request(phone.address, phone.port, "", "api/import", _TASK, key),
    )

    assert code == 0
    assert len(phone.seen("GET", "/api/auth")) == 2


def test_a_key_rejected_twice_is_reported(phone: FakeTasker) -> None:
    phone.reject_keys = 2

    code, message = maputil2.request_with_auth_key(
        phone.address,
        phone.port,
        lambda key: maputil2.http_post_request(phone.address, phone.port, "", "api/import", _TASK, key),
    )

    assert code == 9
    assert "rejected the API key" in str(message)


def test_profiles_are_confirmed_by_name(phone: FakeTasker) -> None:
    phone.profiles |= {"Morning", "Evening"}

    assert deviceverify.verify_profiles_on_android(phone.address, phone.port, ["Morning", "Night"], KEY) == {"Morning"}
    assert deviceverify.verify_profile_on_android(phone.address, phone.port, "Evening", KEY)
    assert not deviceverify.verify_profile_on_android(phone.address, phone.port, "Night", KEY)


# ##################################################################################
# Running Tasks
# ##################################################################################
def test_running_a_task_hands_back_what_it_returned(phone: FakeTasker) -> None:
    from maptasker.src.device import devicetask

    phone.on_task("Greeter", lambda _fake, body: f"hello {body.get('par1', '')}")

    assert devicetask.run_task_on_android(phone.address, phone.port, "Greeter", KEY, par1="there") == (0, "hello there")


def test_running_a_task_that_returns_nothing_gives_an_empty_answer(phone: FakeTasker) -> None:
    from maptasker.src.device import devicetask

    phone.on_task("Quiet", lambda _fake, _body: None)

    assert devicetask.run_task_on_android(phone.address, phone.port, "Quiet", KEY) == (0, "")


def test_running_a_task_tasker_does_not_have_is_not_found(phone: FakeTasker) -> None:
    from maptasker.src.device import devicetask

    code, message = devicetask.run_task_on_android(phone.address, phone.port, "Nothing", KEY)

    assert code == 6
    assert json.dumps(message)


# ##################################################################################
# The helper Tasks: installed on the phone, run, and read back from the file they leave
# ##################################################################################
@pytest.fixture
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    from maptasker.src.device import devicetask

    monkeypatch.setattr(devicetask, "RESULT_POLL_SECONDS", 0)


_FILES = "MAPTASKER-FILES 1\nFILES\n/storage/emulated/0/Tasker/a.xml|~|/storage/emulated/0/Tasker/.Trash/b.xml\nMAPTASKER-END\n"


def test_the_files_on_the_phone_are_listed_by_installing_and_running_the_helper(
    phone: FakeTasker, quick: None, loaded: None
) -> None:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import devicefiles

    phone.writes(devicefiles.FILE_LIST_TASK_NAME, "/Tasker/maptasker_files.txt", _FILES, installed=False)

    result = devicefiles.get_list_of_files(phone.address, phone.port, "/storage/emulated/0/Tasker", state=PrimeItems)

    assert result == (0, ["/Tasker/a.xml"]), "the trashed one is left out, and the storage root is taken off"
    assert devicefiles.FILE_LIST_TASK_NAME in phone.tasks, "the helper was imported before it was run"
    assert phone.seen("DELETE", "/api/file/Tasker/maptasker_files.txt"), "the last answer was cleared first"


def test_a_helper_already_on_the_phone_is_not_imported_again(phone: FakeTasker, quick: None, loaded: None) -> None:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import devicefiles

    phone.writes(devicefiles.FILE_LIST_TASK_NAME, "/Tasker/maptasker_files.txt", _FILES)

    devicefiles.get_list_of_files(phone.address, phone.port, "/storage/emulated/0/Tasker", state=PrimeItems)

    assert phone.seen("POST", "/api/import") == []


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("not a file list\nMAPTASKER-END\n", "not a MapTasker file list"),
        ("not a file list\n", "never finished being written"),
        ("MAPTASKER-FILES 1\nFILES\n/a.xml\n", "never finished being written"),
        ("MAPTASKER-FILES 1\nFILES\n%lfp_full_path\nMAPTASKER-END\n", "No XML files were found"),
        ("MAPTASKER-FILES 1\nFILES\n/storage/emulated/0/Tasker/.Trash/x.xml\nMAPTASKER-END\n", "Only trashed"),
    ],
)
def test_a_listing_the_phone_gets_wrong_ends_in_a_message(
    phone: FakeTasker, quick: None, loaded: None, monkeypatch: pytest.MonkeyPatch, payload: str, expected: str
) -> None:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import devicefiles

    monkeypatch.setattr(devicefiles, "_FILE_LIST_POLL_ATTEMPTS", 2)
    phone.writes(devicefiles.FILE_LIST_TASK_NAME, "/Tasker/maptasker_files.txt", payload)

    code, message = devicefiles.get_list_of_files(
        phone.address, phone.port, "/storage/emulated/0/Tasker", state=PrimeItems
    )

    assert code == 8
    assert expected in str(message)


def test_a_helper_that_leaves_no_file_is_reported(
    phone: FakeTasker, quick: None, loaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import devicefiles

    monkeypatch.setattr(devicefiles, "_FILE_LIST_POLL_ATTEMPTS", 2)
    phone.on_task(devicefiles.FILE_LIST_TASK_NAME, lambda _fake, _body: None)

    code, message = devicefiles.fetch_file_list_from_device(phone.address, phone.port, state=PrimeItems)

    assert code == 8
    assert "did not produce a file list" in str(message)


# ##################################################################################
# Importing a Profile into Tasker (the phone's own import screen)
# ##################################################################################
_PROFILE = b"<TaskerData><Profile sr='prof1'><id>1</id><nme>Morning</nme></Profile></TaskerData>"


@pytest.fixture
def import_screen(phone: FakeTasker, quick: None, loaded: None, monkeypatch: pytest.MonkeyPatch):
    """A phone whose Open Profile helper is installed and whose user taps Import."""
    from maptasker.src.device import deviceoffer, deviceverify

    route = deviceoffer.OPEN_FILE_ROUTE
    monkeypatch.setattr(deviceoffer, "_OPEN_POLL_ATTEMPTS", 2)
    monkeypatch.setattr(deviceoffer, "CONFIRM_POLL_ATTEMPTS", 2)
    monkeypatch.setattr(deviceverify, "RESULT_POLL_SECONDS", 0)
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    return route


def _open_profile(phone: FakeTasker, *, wait_for_confirmation: bool = True) -> tuple[int, str]:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import deviceoffer

    return deviceoffer.open_profile_on_device(
        _PROFILE, "Morning", phone.address, phone.port, wait_for_confirmation, state=PrimeItems
    )


def test_a_profile_sent_to_the_phone_is_staged_under_its_name_and_confirmed(phone: FakeTasker, import_screen) -> None:
    code, message = _open_profile(phone)

    assert code == 0
    assert "Morning" in message
    assert phone.files["/Tasker/profiles/Morning.prf.xml"] == _PROFILE
    assert phone.profiles == {"Morning"}
    assert import_screen.task_name in phone.tasks, "the helper was installed first"


def test_not_waiting_returns_as_soon_as_the_screen_is_open(phone: FakeTasker, import_screen) -> None:
    code, message = _open_profile(phone, wait_for_confirmation=False)

    assert code == 0
    assert "not imported until it is confirmed" in message


def test_a_profile_the_user_declines_is_reported_as_not_reported_by_tasker(phone: FakeTasker, import_screen) -> None:
    phone.writes(import_screen.task_name, import_screen.read_path, f"{import_screen.header}\nMAPTASKER-END\n")

    code, message = _open_profile(phone)

    assert code == 8
    assert "has not reported" in message
    assert "/Tasker/profiles/Morning.prf.xml" in message, "the user is told where the file is to import it by hand"


def test_a_profile_tasker_already_has_is_not_waited_for(phone: FakeTasker, import_screen) -> None:
    phone.profiles.add("Morning")

    code, message = _open_profile(phone)

    assert code == 0
    assert "already has" in message


def test_a_phone_that_answers_with_another_kinds_result_is_not_believed(phone: FakeTasker, import_screen) -> None:
    phone.writes(import_screen.task_name, import_screen.read_path, "MAPTASKER-OPEN-PROJECT 1\nMAPTASKER-END\n")

    code, message = _open_profile(phone)

    assert code == 8
    assert "not a MapTasker import result" in message


def test_a_helper_that_never_answers_is_reported_with_the_hint(phone: FakeTasker, import_screen) -> None:
    phone.handlers[import_screen.task_name] = lambda _fake, _body: None

    code, message = _open_profile(phone)

    assert code == 8
    assert "could not open" in message


def test_a_stage_that_cannot_be_confirmed_stops_before_the_helper_runs(phone: FakeTasker, import_screen) -> None:
    phone.slow_reads["/Tasker/profiles/Morning.prf.xml"] = 99

    code, message = _open_profile(phone)

    assert code == 8
    assert "could not confirm" in str(message)
    assert phone.seen("POST", "/api/tasks") == [], "nothing was handed to Tasker"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("", "1821", b"<x/>", "Morning"), "IP address and port"),
        (("1.2.3.4", "1821", b"", "Morning"), "no Profile XML"),
        (("1.2.3.4", "1821", b"<x/>", ""), "name is needed"),
    ],
)
def test_a_request_with_something_missing_is_refused_before_the_phone_is_asked(
    arguments: tuple[str, str, bytes, str], expected: str
) -> None:
    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import deviceoffer

    ip, port, xml, name = arguments
    code, message = deviceoffer.open_profile_on_device(xml, name, ip, port, state=PrimeItems)

    assert code == 8
    assert expected in message


def test_a_phone_that_cannot_be_reached_ends_the_offer_with_its_message(phone: FakeTasker, import_screen) -> None:
    port = phone.port
    phone.down()

    from maptasker.src.core.primitem import PrimeItems
    from maptasker.src.device import deviceoffer

    code, message = deviceoffer.open_profile_on_device(_PROFILE, "Morning", phone.address, port, state=PrimeItems)

    assert code == 8
    assert "Connection error" in message


# ##################################################################################
# A key the phone has stopped accepting, on a read
# ##################################################################################
def test_a_read_with_a_key_the_phone_refuses_is_made_again_with_a_fresh_one(phone: FakeTasker) -> None:
    phone.tasks.add("Opener")
    maputil2.auth_key_for(phone.address, phone.port)
    phone.reject_keys = 1

    assert deviceverify.task_names_on_device(phone.address, phone.port, ["Opener"]) == (0, "", ["Opener"])
    assert len(phone.seen("GET", "/api/auth")) == 2


def test_a_key_refused_again_after_the_fresh_one_is_reported_not_chased(phone: FakeTasker) -> None:
    phone.tasks.add("Opener")
    maputil2.auth_key_for(phone.address, phone.port)
    phone.reject_keys = 99

    code, message, names = deviceverify.task_names_on_device(phone.address, phone.port, ["Opener"])

    assert (code, names) == (8, [])
    assert "401" in message
    assert len(phone.seen("GET", "/api/auth")) == 2, "one refresh, and no more"


def test_a_key_that_was_not_the_one_held_is_not_swapped_for_it(phone: FakeTasker) -> None:
    """A caller that brought its own key is told it was refused; the held one is not its to replace."""
    maputil2.auth_key_for(phone.address, phone.port)

    code, _ = maputil2.http_request(phone.address, phone.port, "", "api/tasks", "", "someone-elses-key")

    assert code == 8
    assert len(phone.seen("GET", "/api/auth")) == 1
