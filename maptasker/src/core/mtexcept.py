#! /usr/bin/env python3
"""The exception a library module raises instead of ending the process."""

#                                                                                      #
# mtexcept: the one exception that means "MapTasker cannot carry on"                   #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#                                                                                      #
# Deliberately imports NOTHING from maptasker.  Every module that can fail needs to be #
# able to raise this, including the ones sysconst and primitem are built out of, so it #
# has to sit below all of them in the import graph.                                    #
#                                                                                      #
from __future__ import annotations


class MapTaskerError(Exception):
    """MapTasker cannot carry on.  Carries the code the *process* should end on.

    Raised by library modules in place of sys.exit().  The difference matters more than
    it looks: sys.exit() raises SystemExit, which inherits from BaseException, so it
    sails through every `except Exception` in the call stack and ends the interpreter.
    In a library that is only ever correct when the library IS the program.

    It is not, here.  The same modules are called with a live NiceGUI event loop
    underneath them -- where a SystemExit raised inside a `run.io_bound` worker or a
    button handler tears down the server rather than the one operation that failed --
    and from the test suite, where it ends the test run rather than the test.

    So the modules raise this instead, and the entry points (mapit.mapit_all for the
    process, MapTaskerEventHandlers.view_event for a GUI build) decide what "cannot
    carry on" means in their context: an exit status in the first case, a message box
    and a still-running window in the second.

    Attributes:
        message: what to tell the user.  May be empty for a plain "stop now".
        exit_code: what the process should exit with if this reaches the top.  0 is a
            legitimate value -- a clean, deliberate shutdown is still a request to stop
            unwinding, and the GUI's own "Exit" button is exactly that.
    """

    def __init__(self, message: str = "", exit_code: int = 1) -> None:
        """Record what went wrong and what the process should exit with.

        Args:
            message: the human-readable reason.  Defaults to a generic one built from
                the code, so str(error) is never empty.
            exit_code: the process exit status this maps to.
        """
        super().__init__(message or f"MapTasker stopped with code {exit_code}.")
        self.message = message
        self.exit_code = exit_code
