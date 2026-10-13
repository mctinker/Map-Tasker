"""clock: the one place MapTasker asks what time it is.

Every datetime MapTasker makes is timezone-aware and in the local timezone.  Aware, because an
aware datetime compared with a naive one raises TypeError -- and a naive one compared with
another naive one quietly assumes both mean the same timezone, which is wrong across a daylight
saving change or on a machine whose timezone was changed.  Local, because these times are shown
to the user and put into file names, where UTC would read as the wrong hour.

The timestamps MapTasker writes into file names (timeline snapshots, saved reports) carry no
offset.  They are read back as local wall-clock time through parse_local, which is how they were
written, so files written before these were aware still read correctly.
"""

#! /usr/bin/env python3

#                                                                                      #
# clock: timezone-aware local datetimes for the whole program                          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

from datetime import UTC, date, datetime, time


def now() -> datetime:
    """The current local time, timezone-aware."""
    return datetime.now().astimezone()


def aware(moment: datetime) -> datetime:
    """`moment` as an aware datetime in local time.

    A naive one is taken to be local wall-clock time already; an aware one in another timezone
    is converted, so its wall-clock time is right for a name stamped with it (see parse_local).
    """
    return moment.astimezone()


def from_timestamp(seconds: float) -> datetime:
    """A POSIX timestamp (a file's mtime, say) as local time, timezone-aware."""
    return datetime.fromtimestamp(seconds, tz=UTC).astimezone()


def start_of(day: date) -> datetime:
    """Local midnight at the start of `day`, timezone-aware."""
    return aware(datetime.combine(day, time.min))


def parse_local(text: str, stamp_format: str) -> datetime:
    """A timestamp written without an offset, read back as the local time it was written in.

    Raises ValueError, as datetime.strptime does, when `text` does not match `stamp_format`.
    """
    return datetime.strptime(text, stamp_format).astimezone()
