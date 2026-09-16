"""Android device requests (maputil2) Unit Tests

Every request to the Android device blocks until the device answers or times out, and the GUI
runs on a single event loop -- so a request made there freezes the whole window.  The GUI
hands them to run.io_bound instead.  maputil2 logs any request that arrives on a running event
loop, naming the caller that should have handed it off; these tests pin down when it does and
when it does not.  No device is involved: requests.get answers 404 at once.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import threading
from types import SimpleNamespace

import pytest
import requests
from maptasker.src import maputil2

_WARNING = "made on the GUI event loop"


@pytest.fixture(autouse=True)
def no_device(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Every GET answers 404 straight away, and MapTasker's warnings are captured."""
    monkeypatch.setattr(
        maputil2.requests,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=404, content=b""),
    )
    caplog.set_level(logging.WARNING, logger="MapTasker")


def _read_the_device() -> tuple:
    """What a Save To Android does first: ask whether its destination is already there."""
    return maputil2.read_android_file("192.168.0.210", "1821", "/Tasker/tasks/Opener.tsk.xml")


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if _WARNING in record.getMessage()]


def test_a_request_made_on_the_event_loop_is_logged_with_its_caller(caplog: pytest.LogCaptureFixture) -> None:
    """The message names the request and the first caller outside maputil2 -- the line to fix."""

    async def handler() -> tuple:
        return _read_the_device()

    assert asyncio.run(handler()) == (False, b"")

    [message] = _warnings(caplog)
    assert "/Tasker/tasks/Opener.tsk.xml" in message
    assert "test_device_requests.py" in message
    assert "_read_the_device" in message


def test_a_request_handed_to_a_worker_thread_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """What run.io_bound does: the request runs on a thread with no event loop of its own."""

    async def handler() -> tuple:
        return await asyncio.to_thread(_read_the_device)

    assert asyncio.run(handler()) == (False, b"")
    assert _warnings(caplog) == []


def test_a_request_with_no_event_loop_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    """The command line has no event loop, so blocking is simply how it works."""
    assert _read_the_device() == (False, b"")
    assert _warnings(caplog) == []


# --------------------------------------------------------------------------------------
# One way of failing.  Every request to the device goes through maputil2._device_call, so
# every one reports a bad URL, a refused connection, a timeout and any other request error
# in the same words -- and each still reads its statuses the way its endpoint means them.
# --------------------------------------------------------------------------------------
_REQUESTS = {
    "get": lambda: maputil2.http_request("192.168.0.210", "1821", "/Tasker/x.xml", "file", ""),
    "post": lambda: maputil2.http_post_request("192.168.0.210", "1821", "", "api/import", "", b"<Task/>", "KEY"),
    "upload": lambda: maputil2.http_upload_request("192.168.0.210", "1821", "Tasker/tasks", "x.tsk.xml", b"<Task/>"),
    "delete": lambda: maputil2.http_delete_request("192.168.0.210", "1821", "/Tasker/x.txt", "KEY"),
}


class _Failing:
    """A `requests` whose every method raises the one error it was given."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def _fail(self, *_args: object, **_kwargs: object) -> None:
        raise self.error

    get = post = delete = _fail


@pytest.mark.parametrize("request_kind", sorted(_REQUESTS))
@pytest.mark.parametrize(
    ("error", "says"),
    [
        (requests.exceptions.InvalidSchema("no"), "Invalid url!"),
        (requests.exceptions.ConnectionError("no"), "Connection error!"),
        (requests.exceptions.Timeout("no"), "Timeout error."),
        (requests.exceptions.TooManyRedirects("round and round"), "error: round and round"),
    ],
)
def test_every_request_fails_in_the_same_words(
    monkeypatch: pytest.MonkeyPatch, request_kind: str, error: Exception, says: str
) -> None:
    """Code 8, the URL it was asking for, and what went wrong."""
    monkeypatch.setattr(maputil2, "requests", _Failing(error))

    return_code, message = _REQUESTS[request_kind]()

    assert return_code == 8
    assert message.startswith("Request failed for url: http://192.168.0.210:1821/")
    assert says in message


@pytest.mark.parametrize(
    ("request_kind", "status", "return_code"),
    [
        ("get", 200, 0),
        ("get", 404, 6),
        ("get", 500, 8),
        ("post", 200, 0),
        ("post", 401, 9),  # the key was rejected: callers fetch a fresh one and try again
        ("post", 404, 6),
        ("post", 500, 8),
        ("upload", 200, 0),
        ("upload", 404, 8),
        ("delete", 200, 0),
        ("delete", 404, 0),  # nothing there is what a delete wanted
        ("delete", 500, 8),
    ],
)
def test_each_endpoint_reads_its_statuses_its_own_way(
    monkeypatch: pytest.MonkeyPatch, request_kind: str, status: int, return_code: int
) -> None:
    """The shared request is only the asking; what an answer means stays with each endpoint."""
    answer = SimpleNamespace(status_code=status, content=b"<Task/>")
    reply = lambda *_args, **_kwargs: answer  # noqa: E731
    monkeypatch.setattr(maputil2, "requests", SimpleNamespace(get=reply, post=reply, delete=reply))

    assert _REQUESTS[request_kind]()[0] == return_code


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (requests.exceptions.InvalidSchema("no"), False),
        (requests.exceptions.ConnectionError("no"), True),
        (requests.exceptions.Timeout("no"), True),
    ],
)
def test_only_a_malformed_url_is_not_worth_asking_for_a_key_again(
    monkeypatch: pytest.MonkeyPatch, error: Exception, retryable: bool
) -> None:
    """get_android_auth_key retries a failure unless asking again could not possibly help."""
    monkeypatch.setattr(maputil2, "requests", _Failing(error))

    assert maputil2._request_android_auth_key("http://192.168.0.210:1821/api/auth")[2] is retryable


# --------------------------------------------------------------------------------------
# One way of waiting.  Every retry and poll against the device paces itself with
# maputil2.spaced_attempts: the auth key, the upload read-back, and deviceinv's two polls.
# --------------------------------------------------------------------------------------
@pytest.fixture
def slept(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Every wait, recorded instead of taken."""
    waits: list[float] = []
    monkeypatch.setattr(maputil2.time, "sleep", waits.append)
    return waits


def test_the_wait_comes_between_attempts_never_after_the_last(slept: list[float]) -> None:
    """Three attempts, two waits: nothing follows the last attempt, so nothing waits for it."""
    assert list(maputil2.spaced_attempts(3, 0.5)) == [1, 2, 3]
    assert slept == [0.5, 0.5]


def test_a_final_answer_ends_the_waiting(slept: list[float]) -> None:
    """Breaking out -- the answer came, or never can -- asks for no further attempt, so no further wait."""
    for attempt in maputil2.spaced_attempts(5, 2.0):
        if attempt == 2:
            break
    assert slept == [2.0]


@pytest.mark.parametrize("attempts", [0, 1])
def test_no_attempts_or_one_never_waits(slept: list[float], attempts: int) -> None:
    """A single try has nothing to wait between."""
    assert len(list(maputil2.spaced_attempts(attempts, 1.0))) == attempts
    assert slept == []


# --------------------------------------------------------------------------------------
# One key per device.  maputil2 holds the API key each device hands over, so a device is
# asked -- and prompts its user -- once, and a key it rejects is replaced in one place.
# --------------------------------------------------------------------------------------
_DEVICE = ("192.168.0.210", "1821")


class _KeyDevice:
    """Issues KEY1, KEY2, ... from /api/auth; an import succeeds only with the key it `accepts`."""

    def __init__(self, accepts: str = "KEY1", refuses_auth: bool = False) -> None:
        self.accepts = accepts
        self.refuses_auth = refuses_auth
        self.issued = 0
        self.imported_with: list[str] = []

    def get(self, url: str, **_kwargs: object) -> SimpleNamespace:
        if "/api/auth" not in url:
            return SimpleNamespace(status_code=404, content=b"")
        if self.refuses_auth:
            return SimpleNamespace(status_code=500, content=b"{}", json=dict)
        self.issued += 1
        body = {"key": f"KEY{self.issued}", "authorized": True}
        return SimpleNamespace(status_code=200, content=json.dumps(body).encode(), json=lambda: body)

    def post(self, url: str, **kwargs: object) -> SimpleNamespace:
        key = (kwargs.get("headers") or {}).get("Authorization", "")
        self.imported_with.append(key)
        return SimpleNamespace(status_code=200 if key == self.accepts else 401, content=b"{}")


def _keyed_import() -> tuple[int, object]:
    return maputil2.request_with_auth_key(
        *_DEVICE,
        lambda key: maputil2.http_post_request(*_DEVICE, "", "api/import", "", b"<Task/>", key),
    )


@pytest.fixture
def key_device(monkeypatch: pytest.MonkeyPatch) -> _KeyDevice:
    """A device of its own, nothing held for it, and no waiting between key requests."""
    device = _KeyDevice()
    monkeypatch.setattr(maputil2, "requests", device)
    monkeypatch.setattr(maputil2, "_auth_keys", {})
    monkeypatch.setattr(maputil2.time, "sleep", lambda _seconds: None)
    return device


def test_a_device_is_asked_for_its_key_once(key_device: _KeyDevice) -> None:
    """Every request after the first uses the key the device already gave."""
    assert _keyed_import()[0] == 0
    assert _keyed_import()[0] == 0

    assert key_device.issued == 1
    assert key_device.imported_with == ["KEY1", "KEY1"]
    assert maputil2.held_auth_key(*_DEVICE) == "KEY1"


def test_a_rejected_key_is_replaced_and_the_request_made_once_more(key_device: _KeyDevice) -> None:
    """A held key the device no longer takes is swapped for a fresh one, which is then held."""
    maputil2._auth_keys[maputil2.device_address(*_DEVICE)] = "EXPIRED"

    assert _keyed_import()[0] == 0

    assert key_device.imported_with == ["EXPIRED", "KEY1"]
    assert maputil2.held_auth_key(*_DEVICE) == "KEY1"


def test_a_key_refused_twice_is_reported_not_chased(key_device: _KeyDevice) -> None:
    """One refresh: each one is another prompt on the device."""
    key_device.accepts = "NOTHING IT WILL ISSUE"

    assert _keyed_import()[0] == 9

    assert key_device.issued == 2
    assert key_device.imported_with == ["KEY1", "KEY2"]


def test_nothing_is_sent_when_no_key_can_be_had(key_device: _KeyDevice) -> None:
    """The failure to get a key is what comes back, and nothing goes out without one."""
    key_device.refuses_auth = True

    return_code, message = _keyed_import()

    assert return_code == 8
    assert "status code 500" in str(message)
    assert key_device.imported_with == []
    assert maputil2.held_auth_key(*_DEVICE) == ""


def test_a_failed_refresh_keeps_the_key_that_was_held(key_device: _KeyDevice) -> None:
    """Nothing better is known, so nothing is thrown away."""
    maputil2._auth_keys[maputil2.device_address(*_DEVICE)] = "EXPIRED"
    key_device.refuses_auth = True

    assert _keyed_import()[0] == 8
    assert maputil2.held_auth_key(*_DEVICE) == "EXPIRED"


def test_the_held_key_is_read_without_asking_the_device(key_device: _KeyDevice) -> None:
    """held_auth_key is safe on the GUI's event loop: it never makes a request."""
    assert maputil2.held_auth_key(" 192.168.0.210 ", "1821 ") == ""
    assert key_device.issued == 0
    assert maputil2.device_address(" 192.168.0.210 ", "1821 ") == "192.168.0.210:1821"


# --------------------------------------------------------------------------------------
# One connection per exchange.  A maputil2.DeviceClient carries every request to its device
# over one requests.Session for as long as an exchange lasts, and closes it at the end.
# --------------------------------------------------------------------------------------
class _Session:
    def __init__(self, transport: "_Transport") -> None:
        self.transport = transport
        self.closed = False
        self.closes = 0

    def get(self, url: str, **_kwargs: object) -> SimpleNamespace:
        self.transport.sent.append(("session", url))
        return SimpleNamespace(status_code=404, content=b"")

    def close(self) -> None:
        self.closed = True
        self.closes += 1


class _Transport:
    """A `requests` that records which way each request went: directly, or over a session."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.sessions: list[_Session] = []

    def get(self, url: str, **_kwargs: object) -> SimpleNamespace:
        self.sent.append(("direct", url))
        return SimpleNamespace(status_code=404, content=b"")

    def Session(self) -> _Session:  # noqa: N802 -- stands in for requests.Session
        session = _Session(self)
        self.sessions.append(session)
        return session


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> _Transport:
    fake = _Transport()
    monkeypatch.setattr(maputil2, "requests", fake)
    return fake


def _read(ip_address: str = "192.168.0.210", ip_port: str = "1821") -> tuple:
    return maputil2.http_request(ip_address, ip_port, "/Tasker/x.xml", "file", "")


def _ways(transport: _Transport) -> list[str]:
    return [way for way, _url in transport.sent]


def test_inside_an_exchange_its_device_is_reached_over_one_session(transport: _Transport) -> None:
    """Before and after, and for any other device, each request is made the way it always was."""
    _read()
    with maputil2.DeviceClient("192.168.0.210", "1821"):
        _read()
        _read()
        _read("192.168.0.99")  # a different device
    _read()

    assert _ways(transport) == ["direct", "session", "session", "direct", "direct"]
    assert len(transport.sessions) == 1
    assert transport.sessions[0].closed


def test_the_session_is_closed_even_when_the_exchange_fails(transport: _Transport) -> None:
    """Nothing stays open for the device to drop, and nothing after it uses a closed session."""
    with pytest.raises(RuntimeError), maputil2.DeviceClient("192.168.0.210", "1821"):
        raise RuntimeError("the device went away")
    _read()

    assert transport.sessions[0].closed
    assert _ways(transport) == ["direct"]


def test_an_exchange_within_an_exchange_keeps_the_outer_connection(transport: _Transport) -> None:
    """A save that uploads inside an import is still one exchange -- the address as typed, spaces and all."""
    with maputil2.DeviceClient("192.168.0.210", "1821"):
        with maputil2.DeviceClient(" 192.168.0.210 ", "1821"):
            _read()
        _read()

    assert len(transport.sessions) == 1
    assert _ways(transport) == ["session", "session"]


def test_a_decorated_function_is_one_exchange_with_the_device_it_is_given(transport: _Transport) -> None:
    """The device is read from the call, however its address and port are passed."""

    @maputil2.over_one_connection
    def read_twice(label: str, ip_address: str, ip_port: str) -> str:
        _read(ip_address, ip_port)
        _read(ip_address, ip_port)
        return label

    assert read_twice("done", ip_port="1821", ip_address="192.168.0.210") == "done"
    assert read_twice.__name__ == "read_twice"
    assert len(transport.sessions) == 1
    assert transport.sessions[0].closed
    assert _ways(transport) == ["session", "session"]


def test_an_exchange_never_sends_a_request_down_a_used_connection(transport: _Transport) -> None:
    """Tasker's server drops the connection after every response without saying so, and the next
    request down it fails with 'Connection reset by peer' -- which is how an api/import after the
    file write reported a connection error.  Each request's connection is closed once answered."""
    with maputil2.DeviceClient("192.168.0.210", "1821"):
        _read()
        _read()
        _read()

    assert _ways(transport) == ["session"] * 3
    assert transport.sessions[0].closes >= 3


def test_only_a_function_that_names_its_device_can_be_an_exchange() -> None:
    """Without an ip_address and an ip_port there is no device to hold a connection to."""
    with pytest.raises(TypeError, match="names no device"):
        maputil2.over_one_connection(lambda task_name: task_name)


def test_an_exchange_belongs_to_the_thread_running_it(transport: _Transport) -> None:
    """Another worker's requests never ride on this thread's session."""
    with maputil2.DeviceClient("192.168.0.210", "1821"):
        worker = threading.Thread(target=_read)
        worker.start()
        worker.join()

    assert _ways(transport) == ["direct"]


@pytest.mark.parametrize(
    "function",
    [
        "deviceinv.await_import",
        "deviceinv.check_tasker_for_existing",
        "deviceinv.fetch_apps_from_device",
        "deviceinv.fetch_device_backup",
        "deviceinv.fetch_file_list_from_device",
        "deviceinv.fetch_task_names_from_device",
        "deviceinv.fetch_tasker_object_names",
        "deviceinv.import_is_confirmable",
        "deviceinv.import_profile_to_device",
        "deviceinv.offer_to_tasker",
        "deviceinv.open_tasker_on_device",
        "deviceinv.task_names_on_device",
        "taskedit.save_task_to_android",
        "taskedit.save_task_to_android_directory",
        "editcommon.EditorKind.upload_and_verify",
    ],
)
def test_each_exchange_with_a_device_holds_one_connection(function: str) -> None:
    """The functions that make many requests to one device are each one exchange (over_one_connection)."""
    module_name, _, attribute = function.partition(".")
    target = importlib.import_module(f"maptasker.src.{module_name}")
    for part in attribute.split("."):
        target = getattr(target, part)
    assert hasattr(target, "__wrapped__"), f"{function} is not wrapped by maputil2.over_one_connection"


@pytest.mark.parametrize(
    ("names", "query"),
    [
        (["WhatsApp Notification"], "?name=WhatsApp%20Notification"),
        (["$NewTask"], "?name=%24NewTask"),
        # quote() leaves '/' alone, and the server's name match stops at it.
        (["CHECK / READ"], "?name=CHECK%20%2F%20READ"),
        (["Sonos & Off"], "?name=Sonos%20%26%20Off"),
        (["拼图🧩"], "?name=%E6%8B%BC%E5%9B%BE%F0%9F%A7%A9"),
        (["a_b-c", "Two"], "?name=a_b-c&name=Two"),
    ],
)
def test_a_tasker_name_filter_carries_every_character_the_server_can_match(names: list[str], query: str) -> None:
    """Only [A-Za-z0-9_-] goes as itself; the server's handler matches [\\w%+-]+ and decodes afterwards."""
    assert maputil2.tasker_name_query(names) == query


@pytest.mark.parametrize("name", ["Updater - .check", "home~dir"])
def test_a_name_with_a_dot_or_tilde_cannot_be_filtered_on(name: str) -> None:
    """The server decodes '%2E' and '%7E' before matching, so the filter would ask about a shorter name."""
    assert maputil2.tasker_name_query(["Fine", name]) is None
