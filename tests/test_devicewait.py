"""How long the phone is waited for, and the lists kept for the session (devicewait, devicecache).

On a phone with 83 Projects, 237 Profiles, 62 Scenes and 534 Tasks, a lookup of Profiles outlasted five seconds and
the whole list outlasted thirty; a Task lookup timed out at five while the phone was busy, and "no answer in time" was
read as "not there" -- so a Task that was there was imported again, which Tasker refuses.  The waits follow the
phone's size and the speed it has shown, and what is kept is not asked for twice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import devicecache, devicewait, maputil2
from maptasker.src.device import deviceverify

from tests.faketasker import FakeTasker

if TYPE_CHECKING:
    from collections.abc import Iterator

PHONE = ("192.168.0.59", "1821")


# ##################################################################################
# The waits
# ##################################################################################
def test_a_phone_nothing_is_known_about_is_given_the_measured_base_waits() -> None:
    assert devicewait.wait_for(*PHONE, "file") == 5
    assert devicewait.wait_for(*PHONE, "api/tasks", named=True) == 5
    assert devicewait.wait_for(*PHONE, "api/tasks") == maputil2.LIST_READ_TIMEOUT_SECONDS == 30
    assert devicewait.wait_for(*PHONE, "api/import", method="post") == 15
    assert devicewait.wait_for(*PHONE, "api/file/Tasker/x", method="delete") == 10
    assert devicewait.wait_for(*PHONE, "api/auth") == maputil2._AUTH_TIMEOUT_SECONDS == 30


@pytest.mark.parametrize(
    ("route", "method", "named", "kind"),
    [
        ("api/auth", "get", False, devicewait.AUTH),
        ("/api/profiles/", "get", True, devicewait.LOOKUP),
        ("api/scenes", "get", False, devicewait.LIST),
        ("api/tasks", "post", False, devicewait.RUN),
        ("api/import", "post", False, devicewait.WRITE),
        ("upload", "post", False, devicewait.WRITE),
        ("api/file", "delete", False, devicewait.DELETE),
        ("file", "get", False, devicewait.READ),
    ],
)
def test_each_request_is_the_kind_its_route_and_method_say(route: str, method: str, named: bool, kind: str) -> None:
    assert devicewait.kind_of(route, method, named=named)[0] == kind


def test_a_large_configuration_is_given_time_for_all_of_it() -> None:
    """The user's phone: filtered lookups of Profiles took more than five seconds, the whole list more than thirty."""
    for objects, count in (("profiles", 237), ("scenes", 62), ("tasks", 534)):
        devicewait.assume_size(objects, count)

    assert devicewait.wait_for(*PHONE, "api/profiles", named=True) > 30
    assert devicewait.wait_for(*PHONE, "api/profiles") > 30
    assert devicewait.wait_for(*PHONE, "api/tasks", named=True) > 5
    assert devicewait.wait_for(*PHONE, "api/file/x", method="delete") == 10, "a delete does not grow with it"


def test_no_wait_is_longer_than_the_limit() -> None:
    devicewait.assume_size("profiles", 1_000_000)

    assert devicewait.wait_for(*PHONE, "api/profiles") == devicewait.MAX_WAIT_SECONDS


def test_the_key_request_waits_on_a_person_and_is_never_scaled() -> None:
    devicewait.record(*PHONE, "api/auth", 100.0, timed_out=True)
    devicewait.assume_size("profiles", 5000)

    assert devicewait.wait_for(*PHONE, "api/auth") == 30


def test_what_a_phone_reported_outranks_what_was_loaded() -> None:
    devicewait.assume_size("profiles", 5000)
    devicewait.note_size(*PHONE, "profiles", 10)

    assert devicewait.size_of(*PHONE, "profiles") == 10
    assert devicewait.size_of("10.0.0.9", "1821", "profiles") == 5000, "another phone has only the loaded backup"
    assert devicewait.wait_for(*PHONE, "api/profiles") == 30


def test_the_next_wait_is_a_multiple_of_how_long_the_phone_just_took() -> None:
    devicewait.record(*PHONE, "api/tasks", 20.0)
    devicewait.record(*PHONE, "api/tasks", 12.0)

    assert devicewait.wait_for(*PHONE, "api/tasks") == 60.0
    assert devicewait.wait_for(*PHONE, "api/tasks", named=True) == 5, "a lookup is its own kind"
    assert devicewait.wait_for("10.0.0.9", "1821", "api/tasks") == 30, "and another phone is its own"


def test_a_request_that_gave_up_makes_the_next_of_its_kind_wait_twice_as_long() -> None:
    devicewait.record(*PHONE, "api/tasks", 5.0, named=True, timed_out=True)
    assert devicewait.wait_for(*PHONE, "api/tasks", named=True) == 10.0

    devicewait.record(*PHONE, "api/tasks", 10.0, named=True, timed_out=True)
    assert devicewait.wait_for(*PHONE, "api/tasks", named=True) == 20.0

    devicewait.record(*PHONE, "api/tasks", 4.0, named=True)
    assert devicewait.wait_for(*PHONE, "api/tasks", named=True) == 12.0, "answered at last: three times that"


def test_a_wait_of_ten_seconds_or_more_is_worth_telling_the_person() -> None:
    assert devicewait.long_wait(*PHONE, "file") is None
    assert devicewait.long_wait(*PHONE, "api/tasks") == 30


# ##################################################################################
# The waits reach the requests, against a phone that is slow
# ##################################################################################
@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeTasker]:
    """A listening phone, and waits short enough for a test: a lookup waits 0.3 seconds to begin with.

    The margins below are wide on purpose: a loaded CI runner (macOS, once) took longer than fifty milliseconds to
    answer a request that was meant to arrive inside its wait.  An answer is never early, so the failing side of each
    test is exact; it is the succeeding side that needs room.
    """
    monkeypatch.setattr(maputil2, "AUTH_KEY_RETRY_SECONDS", 0)
    monkeypatch.setitem(devicewait.BASE_WAIT_SECONDS, devicewait.LOOKUP, 0.3)
    maputil2._auth_keys.clear()
    fake = FakeTasker().up()
    yield fake
    fake.down()
    maputil2._auth_keys.clear()


def test_a_phone_that_is_slow_is_waited_for_longer_each_time_it_is_not_waited_long_enough(phone: FakeTasker) -> None:
    phone.tasks = {"Wake Up"}
    phone.list_seconds = 0.7

    asked = [deviceverify.task_names_on_device(phone.address, phone.port, ["Wake Up"]) for _ in range(3)]

    assert [code for code, _, _ in asked] == [8, 8, 0], "waits of 0.3, 0.6 and 1.2 seconds against an answer in 0.7"
    assert "Timeout error" in asked[0][1]
    assert "Waited 0.3 seconds" in asked[0][1]
    assert "will wait 0.6 seconds" in asked[0][1]
    assert asked[2][2] == ["Wake Up"]


def test_a_phone_that_has_answered_slowly_is_not_waited_for_in_vain_again(phone: FakeTasker) -> None:
    phone.tasks = {"Wake Up"}
    phone.list_seconds = 0.4

    first = deviceverify.task_names_on_device(phone.address, phone.port, ["Wake Up"])
    assert first[0] == 8, "0.4 seconds against a wait of 0.3"
    assert deviceverify.task_names_on_device(phone.address, phone.port, ["Wake Up"])[0] == 0
    assert devicewait.wait_for(phone.address, phone.port, "api/tasks", named=True) >= 3 * 0.4


# ##################################################################################
# What is kept for the session
# ##################################################################################
def test_an_answer_is_asked_for_once_and_kept() -> None:
    asked: list[int] = []

    def load() -> tuple[int, str, list[str]]:
        asked.append(1)
        return 0, "", ["a"]

    first = devicecache.cached(*PHONE, "names", load)
    second = devicecache.cached(*PHONE, "names", load)

    assert first == second == (0, "", ["a"])
    assert len(asked) == 1


def test_an_answer_that_failed_is_not_kept() -> None:
    answers = iter([(8, "unreachable", []), (0, "", ["a"])])

    assert devicecache.cached(*PHONE, "names", lambda: next(answers)) == (8, "unreachable", [])
    assert devicecache.cached(*PHONE, "names", lambda: next(answers)) == (0, "", ["a"])


def test_a_fresh_answer_is_asked_for_and_replaces_the_kept_one() -> None:
    answers = iter([(0, "", ["old"]), (0, "", ["new"])])

    devicecache.cached(*PHONE, "names", lambda: next(answers))
    assert devicecache.cached(*PHONE, "names", lambda: next(answers), fresh=True) == (0, "", ["new"])
    assert devicecache.cached(*PHONE, "names", lambda: (_ for _ in ()).throw(AssertionError("asked again"))) == (
        0,
        "",
        ["new"],
    )


def test_an_answer_is_asked_for_again_after_ten_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(devicecache.time, "monotonic", lambda: now[0])
    answers = iter([(0, "", ["old"]), (0, "", ["new"])])
    devicecache.cached(*PHONE, "names", lambda: next(answers))

    now[0] += devicecache.SESSION_SECONDS - 1
    assert devicecache.cached(*PHONE, "names", lambda: next(answers))[2] == ["old"]
    now[0] += 2
    assert devicecache.cached(*PHONE, "names", lambda: next(answers))[2] == ["new"]


def test_one_phones_answers_are_not_another_phones() -> None:
    devicecache.keep(*PHONE, "names", ["mine"])

    assert devicecache.kept("10.0.0.9", "1821", "names") is None
    devicecache.forget(*PHONE)
    assert devicecache.kept(*PHONE, "names") is None


def test_the_whole_task_list_is_asked_of_the_phone_once_per_session(phone: FakeTasker) -> None:
    phone.tasks = {"Wake Up", "Sleep"}

    first = deviceverify.fetch_task_names_from_device(phone.address, phone.port)
    second = deviceverify.fetch_task_names_from_device(phone.address, phone.port)

    assert first == second == (0, "", ["Sleep", "Wake Up"])
    assert len(phone.seen("GET", "/api/tasks")) == 1
    assert devicewait.size_of(phone.address, phone.port, "tasks") == 2, "and the phone's size is learned from it"


def test_asking_for_the_list_fresh_asks_the_phone_again(phone: FakeTasker) -> None:
    phone.tasks = {"Wake Up"}
    deviceverify.fetch_task_names_from_device(phone.address, phone.port)
    phone.tasks.add("Sleep")

    assert deviceverify.fetch_task_names_from_device(phone.address, phone.port)[2] == ["Wake Up"]
    assert deviceverify.fetch_task_names_from_device(phone.address, phone.port, fresh=True)[2] == ["Sleep", "Wake Up"]


def test_an_import_drops_every_list_kept_for_that_phone(phone: FakeTasker) -> None:
    phone.tasks = {"Wake Up"}
    deviceverify.fetch_task_names_from_device(phone.address, phone.port)
    _code, key = maputil2.auth_key_for(phone.address, phone.port)

    maputil2.http_post_request(phone.address, phone.port, "", "api/import", b"<TaskerData/>", key)
    deviceverify.fetch_task_names_from_device(phone.address, phone.port)

    assert len(phone.seen("GET", "/api/tasks")) == 2


def test_a_list_kept_by_one_phone_is_not_handed_to_another(phone: FakeTasker) -> None:
    devicecache.keep("10.9.9.9", "1821", "task names", ["someone else's"])
    phone.tasks = {"Mine"}

    assert deviceverify.fetch_task_names_from_device(phone.address, phone.port)[2] == ["Mine"]


# ##################################################################################
# A person is given time, not a count of tries
# ##################################################################################
def test_waiting_for_an_import_stops_at_the_time_it_was_meant_to_take_however_long_each_ask_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    asked: list[int] = []

    def slow_ask(*_args: object) -> None:
        asked.append(1)
        now[0] += 50.0  # a phone with a large configuration takes this long over one lookup
        return

    monkeypatch.setattr(deviceverify, "verify_names_on_android", slow_ask)
    monkeypatch.setattr(deviceverify.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(deviceverify.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)

    code, message = deviceverify.await_import("1.2.3.4", "1821", ["P"], "Profile", auth_key="K", attempts=60)

    assert code == 8
    assert "has not reported" in message
    assert len(asked) <= 3, "sixty asks of fifty seconds each would be fifty minutes"
