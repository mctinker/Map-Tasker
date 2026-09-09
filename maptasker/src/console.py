#! /usr/bin/env python3
"""The program's console channel: one place every message to the user goes through."""

#                                                                                      #
# console: route a library module's output through logging, and to the terminal        #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#                                                                                      #
from __future__ import annotations

import contextlib
import logging
import sys
from typing import TYPE_CHECKING

from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Iterator

# Whether anything written here reaches a terminal.  The log is written either way --
# muting silences the console, never the record.  Off by default: MapTasker normally IS
# the program and its console output is the point.  Turned on by an embedder, or by a
# test that would otherwise scribble over pytest's own output.
_muted = False


def mute() -> None:
    """Stop writing to the terminal.  Logging carries on unchanged."""
    global _muted  # noqa: PLW0603
    _muted = True


def unmute() -> None:
    """Resume writing to the terminal."""
    global _muted  # noqa: PLW0603
    _muted = False


def is_muted() -> bool:
    """Whether console output is currently suppressed.

    Returns:
        bool: True when only the log is being written.
    """
    return _muted


@contextlib.contextmanager
def muted() -> Iterator[None]:
    """Silence the console for the duration of a block, then put it back as it was.

    Restores the previous state rather than unconditionally unmuting, so nesting this
    inside an already-muted embedder does not hand the terminal back on the way out.

    Yields:
        None
    """
    global _muted  # noqa: PLW0603
    previous = _muted
    _muted = True
    try:
        yield
    finally:
        _muted = previous


def _in_debug_mode() -> bool:
    """Whether the user asked for debug output on this run.

    Read off PrimeItems rather than cached, because the flag is set partway through
    start-up and this module is imported long before that.  Imported inside the function
    for the same reason it is imported late elsewhere in this project: primitem pulls in
    a good deal of the package, and console sits underneath most of it.

    Returns:
        bool: True when the "debug" runtime argument is on.
    """
    with contextlib.suppress(Exception):
        from maptasker.src.primitem import PrimeItems  # noqa: PLC0415

        return bool(PrimeItems.program_arguments and PrimeItems.program_arguments.get("debug"))
    return False


def _emit(message: str, level: int, stream: object, end: str, flush: bool) -> None:
    """Log a message, and put it on the terminal unless the console is muted."""
    logger.log(level, message)
    if _muted:
        return
    print(message, file=stream, end=end, flush=flush)


def say(message: str = "", *, end: str = "\n", flush: bool = False) -> None:
    """Ordinary console output: the thing the user ran MapTasker to be told.

    Args:
        message: the text to show.
        end: line terminator, as for print().
        flush: force the stream out now.
    """
    _emit(message, logging.INFO, sys.stdout, end, flush)


def warn(message: str) -> None:
    """Something is off but the run continues.  Goes to stdout, as the colours do.

    Args:
        message: the text to show.
    """
    _emit(message, logging.WARNING, sys.stdout, "\n", False)


def error(message: str) -> None:
    """Something failed.  Goes to stderr so it survives a redirected stdout.

    Args:
        message: the text to show.
    """
    _emit(message, logging.ERROR, sys.stderr, "\n", False)


def debug(message: str) -> None:
    """Developer diagnostics: always logged, shown only when debug mode is on.

    This is what most of the bare print() calls in this package used to be -- a message
    of interest to whoever was working on MapTasker that day, and noise to everybody
    else.  Sending them here keeps them in the log, where they are useful after the
    fact, without putting them on a user's terminal.

    Args:
        message: the text to log.
    """
    logger.debug(message)
    if not _muted and _in_debug_mode():
        print(message)  # noqa: T201  the console sink itself
