"""devicewait: how long to wait for the Android device, and what has been learned about how slow it is.

Every request to the phone waits for an answer for some number of seconds, and the right number is not the same for
every phone.  Tasker answers a request for its Profiles by going through its configuration, so the wait grows with
the configuration: on a phone with 237 Profiles, 62 Scenes and 534 Tasks a filtered lookup of Profiles outlasted
five seconds and the whole list outlasted thirty.  A wait that is too short is worse than a slow one -- "no answer
in time" gets read as "the Task is not there", and a Task that is there is then imported a second time, which
Tasker refuses.  So the waits are decided here, in one place, for every request in maputil2:

  * each KIND of request has a base wait (the numbers that were measured on an idle phone);
  * a list or lookup of Profiles, Scenes or Tasks is given time for the number of them the phone has, when that is
    known -- from an answer the phone gave, or from the backup that is loaded;
  * what the phone has actually taken to answer is remembered for the session, and the next wait is a multiple of
    the slowest recent answer;
  * a request that timed out makes the next one of its kind wait twice as long, up to a limit, so that trying again
    is not trying the same thing that has just failed.

A helper Task is a different wait: MapTasker runs a small Task on the phone and polls for the file it writes, a fixed
number of times.  Those counts were set on an idle phone too, and a Task that walks the whole configuration (the object
list, the ID-check backup) takes longer on a larger one.  poll_attempts gives them the same treatment -- the count a
phone of the reference size needed, more for a bigger configuration, and a multiple of what the phone last took.

Nothing here makes a request or touches the user interface.  The session's memory is process-wide and thread-safe,
since the requests are made from worker threads.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field

# --- The kinds of request ---------------------------------------------------------------
READ = "read"  # a file off the phone: the answer is the file, ready or not
LOOKUP = "lookup"  # api/tasks, api/profiles ... asked about particular names
LIST = "list"  # the same asked for everything
WRITE = "write"  # api/import, upload
RUN = "run"  # running a Task, which answers when the Task has finished
DELETE = "delete"
AUTH = "auth"  # asking for a key, which puts an approval prompt on the phone and waits for a person

# How long each kind of request waits on a phone nothing is known about, in seconds.
BASE_WAIT_SECONDS: dict[str, float] = {
    READ: 5.0,
    LOOKUP: 5.0,
    # Tasker answers GET api/tasks with no name by looking up every Task one at a time: 4.5 seconds for ~500 Tasks on
    # an idle phone, and past 5 whenever the phone was still busy with the request before it.  Thirty is the Tasker
    # HTTP API's own limit for answering a request.
    LIST: 30.0,
    WRITE: 15.0,
    DELETE: 10.0,
    # The key request is not answered until the user has dealt with the prompt on the phone; thirty seconds is how
    # long the Tasker HTTP API's own 'GET Auth' Task is given to answer.  It waits on a person, not on the
    # configuration, so it is never scaled.
    AUTH: 30.0,
    RUN: 60.0,
}

# The longest any request is made to wait.  A phone that has not answered in three minutes has not been slow.
MAX_WAIT_SECONDS = 180.0

# What a list or a lookup costs per object the phone has, in seconds, for a phone nothing has been measured on.  A
# guess made from the two measurements there are: Tasks ~0.009 each on an idle phone, and Profiles more than ~0.13
# each (237 of them took more than thirty seconds).  Doubled by COLD_MARGIN, and replaced by what the phone really
# takes as soon as it has answered once.
SECONDS_PER_OBJECT = {"profiles": 0.3, "scenes": 0.15, "tasks": 0.012, "globals": 0.01}
_COLD_MARGIN = 2.0
# Once the phone has answered, the next wait is this many times the slowest of its recent answers.
_LEARNED_MARGIN = 3.0
_RECENT_ANSWERS = 5

# The configuration the fixed poll counts were set for, in objects (Profiles + Scenes + Tasks).  A guess about where
# they stopped being enough; tools/device_check.py records how long the helper Tasks really take, to replace it.
HELPER_REFERENCE_OBJECTS = 300

# A wait this long is worth telling the person about before it starts.
LONG_WAIT_SECONDS = 10.0

_OBJECT_OF_ROUTE = {
    "api/profiles": "profiles",
    "api/scenes": "scenes",
    "api/tasks": "tasks",
    "api/globals": "globals",
}


@dataclass
class _Seen:
    """What the phone has done for one kind of request."""

    recent: deque[float] = field(default_factory=lambda: deque[float](maxlen=_RECENT_ANSWERS))
    last_timeout: float = 0.0  # the wait the last request gave up after, or 0 if the last one was answered
    timeouts: int = 0


_lock = threading.Lock()
_seen: dict[tuple[str, str], _Seen] = {}
_sizes: dict[str, dict[str, int]] = {}
_assumed: dict[str, int] = {}


def device_key(ip_address: str, ip_port: str) -> str:
    """The key one phone is remembered under."""
    return f"{str(ip_address).strip()}:{str(ip_port).strip()}"


def kind_of(route: str, method: str = "get", *, named: bool = False) -> tuple[str, str]:
    """(the kind of request, the objects its answer lists or "") for a request to this route."""
    path = route.strip("/")
    objects = _OBJECT_OF_ROUTE.get(path, "")
    if path == "api/auth":
        return AUTH, ""
    if method == "delete":
        return DELETE, ""
    if method == "post":
        return (RUN if path == "api/tasks" else WRITE), ""
    if objects:
        return (LOOKUP if named else LIST), objects
    return READ, ""


def _key_of(kind: str, objects: str) -> str:
    return f"{kind}:{objects}"


# --- What the phone has: its size ----------------------------------------------------------
def note_size(ip_address: str, ip_port: str, objects: str, count: int) -> None:
    """Remember how many Profiles, Scenes, Tasks or Globals ("profiles", "scenes" ...) this phone reported."""
    with _lock:
        _sizes.setdefault(device_key(ip_address, ip_port), {})[objects] = max(0, int(count))


def assume_size(objects: str, count: int) -> None:
    """The size of a configuration that is loaded, as the best guess for a phone nothing has been learned from.

    A backup read off the phone is normally the phone's own configuration; for anything else it is only a guess,
    which is why what a phone has really answered always outranks it.
    """
    with _lock:
        _assumed[objects] = max(0, int(count))


def size_of(ip_address: str, ip_port: str, objects: str) -> int:
    """How many of these the phone is known or assumed to have: what it reported, or else what is loaded."""
    with _lock:
        return _sizes.get(device_key(ip_address, ip_port), {}).get(objects, _assumed.get(objects, 0))


# --- How long to wait ----------------------------------------------------------------------
def wait_for(ip_address: str, ip_port: str, route: str, *, method: str = "get", named: bool = False) -> float:
    """Seconds to wait for the phone to answer a request to this route."""
    kind, objects = kind_of(route, method, named=named)
    base = BASE_WAIT_SECONDS[kind]
    if kind == AUTH:
        return base

    candidates = [base]
    if objects in SECONDS_PER_OBJECT:
        candidates.append(SECONDS_PER_OBJECT[objects] * size_of(ip_address, ip_port, objects) * _COLD_MARGIN)
    with _lock:
        seen = _seen.get((device_key(ip_address, ip_port), _key_of(kind, objects)))
        if seen is not None:
            if seen.recent:
                candidates.append(_LEARNED_MARGIN * max(seen.recent))
            if seen.last_timeout:
                candidates.append(2 * seen.last_timeout)
    return min(MAX_WAIT_SECONDS, max(candidates))


def record(
    ip_address: str,
    ip_port: str,
    route: str,
    seconds: float,
    *,
    method: str = "get",
    named: bool = False,
    timed_out: bool = False,
) -> None:
    """Remember how long the phone took to answer a request, or that it gave up after `seconds`."""
    kind, objects = kind_of(route, method, named=named)
    if kind == AUTH:
        return  # it waits on a person, which says nothing about the phone
    with _lock:
        seen = _seen.setdefault((device_key(ip_address, ip_port), _key_of(kind, objects)), _Seen())
        if timed_out:
            seen.last_timeout = seconds
            seen.timeouts += 1
        else:
            seen.recent.append(seconds)
            seen.last_timeout = 0.0


def _helper_key(kind: str) -> str:
    return f"helper:{kind}"


def poll_seconds(ip_address: str, ip_port: str, kind: str, base_attempts: int, interval_seconds: float) -> float:
    """How long to poll for a helper Task's file: its fixed budget, or more when this phone has shown it needs it.

    `kind` names the helper ("object-list", "backup").  Never less than `base_attempts` polls apart; scaled up by how
    far the phone's configuration is past HELPER_REFERENCE_OBJECTS when that is known; and a multiple of the longest
    recent run, or twice the budget of a run that gave up.
    """
    base = base_attempts * interval_seconds
    total = sum(size_of(ip_address, ip_port, objects) for objects in ("profiles", "scenes", "tasks"))
    candidates = [base, base * total / HELPER_REFERENCE_OBJECTS]
    with _lock:
        seen = _seen.get((device_key(ip_address, ip_port), _helper_key(kind)))
        if seen is not None:
            if seen.recent:
                candidates.append(_LEARNED_MARGIN * max(seen.recent))
            if seen.last_timeout:
                candidates.append(2 * seen.last_timeout)
    return min(max(base, MAX_WAIT_SECONDS), max(candidates))


def poll_attempts(ip_address: str, ip_port: str, kind: str, base_attempts: int, interval_seconds: float) -> int:
    """poll_seconds as a number of polls `interval_seconds` apart (a poll with no wait between is not scaled)."""
    if interval_seconds <= 0:
        return base_attempts
    seconds = poll_seconds(ip_address, ip_port, kind, base_attempts, interval_seconds)
    return max(base_attempts, math.ceil(seconds / interval_seconds))


def record_poll(ip_address: str, ip_port: str, kind: str, seconds: float, *, timed_out: bool = False) -> None:
    """Remember how long a helper Task took to write its file, or that it was given up on after `seconds`."""
    with _lock:
        seen = _seen.setdefault((device_key(ip_address, ip_port), _helper_key(kind)), _Seen())
        if timed_out:
            seen.last_timeout = seconds
            seen.timeouts += 1
        else:
            seen.recent.append(seconds)
            seen.last_timeout = 0.0


def longer_than_usual(
    ip_address: str, ip_port: str, route: str, *, method: str = "get", named: bool = False
) -> float | None:
    """The wait for this request when it is more than the base for its kind -- a big phone, or a slow one -- else None.

    For a request that is quick on an ordinary phone, where the base wait is only a ceiling: telling the person about
    every one of those would be telling them about nothing.
    """
    kind, _objects = kind_of(route, method, named=named)
    wait = wait_for(ip_address, ip_port, route, method=method, named=named)
    return wait if wait > BASE_WAIT_SECONDS[kind] else None


def worth_telling(seconds: float) -> float | None:
    """`seconds`, when a wait that long is worth telling the person about before it starts; else None."""
    return seconds if seconds >= LONG_WAIT_SECONDS else None


def long_wait(ip_address: str, ip_port: str, route: str, *, method: str = "get", named: bool = False) -> float | None:
    """The wait a request to this route would be given, when it is long enough to tell the person; else None."""
    wait = wait_for(ip_address, ip_port, route, method=method, named=named)
    return wait if wait >= LONG_WAIT_SECONDS else None


def reset() -> None:
    """Forget everything learned: the start of a session, and of every test."""
    with _lock:
        _seen.clear()
        _sizes.clear()
        _assumed.clear()
