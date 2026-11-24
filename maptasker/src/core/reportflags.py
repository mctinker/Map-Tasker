"""reportflags: which command lines ask for a report rather than for the window -- decided without loading either."""

#! /usr/bin/env python3

#                                                                                        #
# reportflags: the one question main.py has to answer before it knows what to import.     #
#                                                                                        #
# A report (-healthcheck, -compare ...) runs with no window, so it has no use for the web   #
# framework the window is built on, and importing that costs about a third of a second.    #
# Deciding "is this a report?" therefore has to be possible without importing the reports   #
# themselves, let alone the program: this module is that decision and nothing else.         #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
from __future__ import annotations

# The commands that make a run a report.  The reports themselves, and what each takes, are in clireports.
REPORT_FLAGS = ("healthcheck", "compare", "changes_since", "trend", "export", "text", "watch")


def wants_report(argv: list[str]) -> bool:
    """Whether the command line asks for one of these reports rather than for the GUI.

    Args:
        argv (list[str]): the command line, without the program's own name.

    Returns:
        bool: True if any argument is one of the REPORT_FLAGS (with one or two dashes, and
            with or without an "=value").
    """
    flags = {f"-{name}" for name in REPORT_FLAGS} | {f"--{name}" for name in REPORT_FLAGS}
    return any(argument.split("=", 1)[0] in flags for argument in argv)
