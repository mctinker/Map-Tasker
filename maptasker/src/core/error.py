#! /usr/bin/env python3
"""Error handling module for MapTasker."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from maptasker.src.core import console
from maptasker.src.core.sysconst import ERROR_FILE, Colors, logger

if TYPE_CHECKING:
    from maptasker.src.core.mtexcept import MapTaskerError
    from maptasker.src.core.primitem import RunState


def record_error(error: MapTaskerError, state: RunState) -> int:
    """Log an error that stopped a build, and leave it where the window will find it.

    The library modules do not report their errors; they raise MapTaskerError and leave it to
    whoever started the work to decide what a failure means there.  This is the report, for the
    places where the answer is "tell the user, and carry on" -- the window's own loads and builds:

      * it is logged (on the terminal only where there is someone watching one: a debug run
        outside the GUI, or code 5, the Task or Profile that was asked for and is not there);
      * in the GUI, it is written to ERROR_FILE, which the window reads on the next run, and set
        on the run state (error_code, error_msg, error_show_code) for the caller that looks.

    It never raises.  Code 0 is a deliberate stop rather than a failure, and is not recorded.

    Args:
        error: what the library raised.
        state: the run state the error is recorded on.

    Returns:
        int: the error's code, which is what the loading functions hand back to their callers.
    """
    code = error.exit_code
    if not 0 < code < 100:
        return code
    message = error.message or str(error)

    final_error_message = f"{Colors.Red}MapTasker error: {message}"
    if (state.program_arguments and state.program_arguments.debug and not state.program_arguments.gui) or code == 5:
        console.error(final_error_message)
    else:
        logger.debug(final_error_message)

    if state.program_arguments and state.program_arguments.gui:
        # Written for userintr, to display on entry or on a rerun.
        with open(ERROR_FILE, "w", encoding="utf-8") as error_file:
            error_file.write(f"{message}\n")
            if error.show_code:
                error_file.write(f"{code}\n")
        state.error_code = code
        state.error_msg = message
        state.error_show_code = error.show_code
    return code


def report_error(error: MapTaskerError, state: RunState) -> int:
    """The edge of a load or a build that has a window to go back to: record the error, or let it go on up.

    In the GUI a failed load is a message in the window and a window that is still there, so the error
    is recorded and its code returned, for the callers that branch on one.  Anywhere else -- a run with
    no window, or a stop that is not a failure (code 0, a deliberate shutdown) -- there is nobody to
    go back to, and it goes on up to the top of the process.

    Args:
        error: what the library raised.
        state: the run state the error is recorded on.

    Returns:
        int: the error's code, when it was recorded.

    Raises:
        MapTaskerError: the same error, when there is no window or it was not a failure.
    """
    code = record_error(error, state)
    if code == 0 or not (state.program_arguments and state.program_arguments.gui):
        raise error
    return code


def rutroh_error(message: str) -> None:
    """
    Prints or logs an error message.
    Args:
        message (str): The error message to print
    Returns:
        None: Does not return anything
    """
    console.debug(f"Rutroh! {message}")


def close_logfile() -> None:
    """Close the log file(s)"""
    # The FileHandler lives on the ROOT logger, not on "MapTasker": maputil2.setup_logging() installs
    # it via logging.basicConfig(), and our logger simply propagates up to it.  Iterating
    # logger.handlers here would walk an empty list and close nothing at all.
    for target in (logger, logging.root):
        for handler in target.handlers[:]:  # Iterate over a copy to avoid issues during modification
            handler.close()  # Close the stream associated with the handler
            target.removeHandler(handler)  # Remove the handler from the logger
