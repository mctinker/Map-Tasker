"""devicecache: the lists the phone has answered, kept for the session.

Asking the phone for everything it has -- its Tasks by name, its Projects, Profiles, Scenes and Tasks -- is the slow
request (see devicewait), and the same list is wanted again and again: to check a helper Task is installed, to see
whether a name is taken, to list what the program has left behind.  So an answer is kept, per phone, and handed back
for as long as nothing has changed it:

  * any import MapTasker sends to the phone drops everything kept for it (maputil2.http_post_request does that for
    every api/import, whoever sent it), since an import is what changes what the phone has;
  * an answer older than SESSION_SECONDS is asked for again, because the phone's owner changes things there too;
  * a caller that is about to act on the answer and cannot afford a stale one asks for a fresh one.

Nothing here makes a request; the loader a caller hands in does.  Process-wide and thread-safe.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, TypeVar, cast

from maptasker.src.core.devicewait import device_key

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

# How long an answer is trusted.  A session is longer than this; the person at the phone is not still.
SESSION_SECONDS = 600.0

_lock = threading.Lock()
_kept: dict[tuple[str, str], tuple[float, object]] = {}


def kept(ip_address: str, ip_port: str, name: str, *, max_age: float = SESSION_SECONDS) -> object | None:
    """What is kept under this name for this phone, or None if there is nothing or it is too old."""
    with _lock:
        entry = _kept.get((device_key(ip_address, ip_port), name))
    if entry is None or time.monotonic() - entry[0] > max_age:
        return None
    return entry[1]


def keep(ip_address: str, ip_port: str, name: str, value: object) -> None:
    """Keep an answer, replacing any earlier one."""
    with _lock:
        _kept[(device_key(ip_address, ip_port), name)] = (time.monotonic(), value)


def cached(
    ip_address: str,
    ip_port: str,
    name: str,
    load: Callable[[], tuple[int, str, T]],
    *,
    fresh: bool = False,
) -> tuple[int, str, T]:
    """(return code, message, answer) from the cache when it has the answer, else from `load` -- and kept if it worked.

    `load` returns the usual (0, "", answer) or (code, why, empty); only an answer that worked is kept, so a phone
    that could not be asked is asked again next time.  `fresh` skips what is kept (and replaces it).
    """
    if not fresh:
        held = kept(ip_address, ip_port, name)
        if held is not None:
            return 0, "", cast("T", held)
    return_code, message, answer = load()
    if return_code == 0:
        keep(ip_address, ip_port, name, answer)
    return return_code, message, answer


def forget(ip_address: str, ip_port: str) -> None:
    """Drop everything kept for this phone: something has changed what it has."""
    device = device_key(ip_address, ip_port)
    with _lock:
        for key in [key for key in _kept if key[0] == device]:
            del _kept[key]


def reset() -> None:
    """Forget every phone: the start of a session, and of every test."""
    with _lock:
        _kept.clear()
