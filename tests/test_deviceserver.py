"""Installing the 'Http Server Example' project, against a phone that has the Tasker HTTP API and not that project.

The phone is tests/faketasker.py.  Its 'file' and 'upload' routes answer here, as the real project's would once it is
installed, so what is checked is that nothing on the way asks for them: the install goes through 'api/...' only.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import maputil2
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import devicehelpers, deviceserver, devicetask, deviceverify

from tests.faketasker import FakeTasker

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch, loaded: None) -> Iterator[FakeTasker]:
    """A listening phone with the HTTP API, every wait cut to nothing."""
    monkeypatch.setattr(maputil2, "AUTH_KEY_RETRY_SECONDS", 0)
    monkeypatch.setattr(maputil2, "_UPLOAD_SETTLE_SECONDS", 0)
    monkeypatch.setattr(devicetask, "RESULT_POLL_SECONDS", 0)
    monkeypatch.setattr(deviceverify, "RESULT_POLL_SECONDS", 0)
    maputil2._auth_keys.clear()
    fake = FakeTasker().up()
    yield fake
    fake.down()
    maputil2._auth_keys.clear()


def _user_taps_import(phone: FakeTasker) -> None:
    """Running the Open Share Task brings up the share, and the user imports the project."""
    phone.handlers[deviceserver.OPEN_SHARE_TASK_NAME] = lambda fake, _body: fake.profiles.update(
        deviceserver.SERVER_PROFILES
    )


def _install(phone: FakeTasker, **keywords: object) -> tuple[int, str]:
    return deviceserver.install_server_example(phone.address, phone.port, attempts=2, state=PrimeItems, **keywords)  # type: ignore[arg-type]


def test_the_task_opens_the_share_and_nothing_else(loaded: None) -> None:
    """ACTION_VIEW on the share's link, with no package or class: an implicit intent for a web link."""
    built = deviceserver.build_open_share_task(state=PrimeItems)
    assert not isinstance(built, str), built

    task_xml = ET.fromstring(ET.tostring(built.task_element, encoding="unicode"))
    actions = task_xml.findall(".//Action")
    assert [action.findtext("code") for action in actions] == ["877"]
    intent = actions[0]
    assert intent.findtext("Str[@sr='arg0']") == "android.intent.action.VIEW"
    assert intent.findtext("Str[@sr='arg3']") == deviceserver.SERVER_SHARE_URL
    assert intent.findtext("Str[@sr='arg7']") == ""
    assert intent.findtext("Str[@sr='arg8']") == ""


def test_the_project_is_installed_by_opening_its_share_and_waiting_for_its_profiles(phone: FakeTasker) -> None:
    _user_taps_import(phone)

    code, message = _install(phone)

    assert (code, message.split(" is now")[0]) == (0, "Project 'Http Server Example'")
    assert deviceserver.OPEN_SHARE_TASK_NAME in phone.tasks
    assert phone.profiles >= set(deviceserver.SERVER_PROFILES)


def test_nothing_on_the_way_asks_for_the_project_that_is_missing(phone: FakeTasker) -> None:
    """No 'file' or 'upload' request: the HTTP API is the only way in, because the project is what is absent."""
    _user_taps_import(phone)

    _install(phone)

    assert phone.seen("GET", "/file/") == []
    assert phone.seen("POST", "/upload") == []
    assert phone.seen("POST", "/api/import") != []


def test_a_project_that_is_already_there_is_left_alone(phone: FakeTasker) -> None:
    phone.profiles |= set(deviceserver.SERVER_PROFILES)

    code, message = _install(phone)

    assert code == 0
    assert "already in Tasker" in message
    assert phone.seen("POST", "/api/import") == []
    assert phone.seen("POST", "/api/tasks") == []


def test_one_missing_profile_is_a_project_that_is_not_there(phone: FakeTasker) -> None:
    phone.profiles.add(deviceserver.SERVER_PROFILES[0])
    _user_taps_import(phone)

    code, _ = _install(phone)

    assert code == 0
    assert phone.seen("POST", "/api/tasks") != []


def test_the_helper_task_is_not_installed_twice(phone: FakeTasker) -> None:
    """api/import refuses a Task of a name Tasker has, so a re-run must not import again."""
    _user_taps_import(phone)
    phone.tasks.add(deviceserver.OPEN_SHARE_TASK_NAME)

    _install(phone)

    assert phone.seen("POST", "/api/import") == []


def test_a_user_who_never_taps_import_is_told_where_the_link_is(phone: FakeTasker) -> None:
    phone.handlers[deviceserver.OPEN_SHARE_TASK_NAME] = lambda _fake, _body: None

    code, message = _install(phone)

    assert code == 8
    assert "has not reported" in message
    assert deviceserver.SERVER_SHARE_URL in message


def test_without_waiting_it_returns_once_the_link_is_opened(phone: FakeTasker) -> None:
    _user_taps_import(phone)

    code, message = _install(phone, wait_for_confirmation=False)

    assert code == 0
    assert "Tap Import" in message
    assert deviceserver.SERVER_SHARE_URL in message


def test_a_device_that_refuses_the_key_is_told_the_api_project_is_what_is_needed(phone: FakeTasker) -> None:
    phone.refuse_auth = 100

    code, message = _install(phone)

    assert code != 0
    assert "Tasker HTTP API" in message
    assert phone.seen("POST", "/api/import") == []


def test_an_address_is_needed() -> None:
    code, message = deviceserver.install_server_example("", "", state=PrimeItems)

    assert code == 8
    assert "address and port" in message


def test_the_helper_is_counted_as_current_so_it_is_never_reported_as_dead(loaded: None) -> None:
    assert deviceserver.OPEN_SHARE_TASK_NAME in devicehelpers.current_helper_task_names(state=PrimeItems)


def test_an_import_refused_because_the_task_is_already_there_counts_as_installed(
    phone: FakeTasker, monkeypatch: pytest.MonkeyPatch, loaded: None
) -> None:
    """A slow phone answers the existence check too late, the import is tried, and Tasker refuses a Task it has (400).
    Asked again with all the time there is, the Task is found: nothing went wrong."""
    asked = iter([False, True])
    monkeypatch.setattr(devicetask, "confirm_task_on_android", lambda *_args, **_kwargs: next(asked))
    phone.import_answers = 400

    code, message = devicetask.install_task_on_android(
        phone.address,
        phone.port,
        "fake-api-key",
        deviceserver.OPEN_SHARE_TASK_NAME,
        lambda: deviceserver.build_open_share_task(state=PrimeItems),
        state=PrimeItems,
    )

    assert (code, message) == (0, "")


def test_an_import_refused_for_another_reason_is_still_an_error(
    phone: FakeTasker, monkeypatch: pytest.MonkeyPatch, loaded: None
) -> None:
    monkeypatch.setattr(devicetask, "confirm_task_on_android", lambda *_args, **_kwargs: False)
    phone.import_answers = 400

    code, message = devicetask.install_task_on_android(
        phone.address,
        phone.port,
        "fake-api-key",
        deviceserver.OPEN_SHARE_TASK_NAME,
        lambda: deviceserver.build_open_share_task(state=PrimeItems),
        state=PrimeItems,
    )

    assert code != 0
    assert "400" in message
