"""Main entry point for maptasker"""

#! /usr/bin/env python3

#                                                                                       #
# Main: MapTasker entry point                                                           #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#                                                                                       #
# Nothing in this module runs at import time beyond the import below, and that is worth #
# saying because it is a change: importing it used to insert the project root into      #
# sys.path and then a bundled overrides directory at position 0, which is a change to   #
# how EVERY import in the interpreter resolves -- including imports belonging to        #
# programs that have nothing to do with MapTasker -- made by a package on the strength  #
# of having been installed.  Neither is needed.  Hatchling installs the package, so     #
# `maptasker` and `python -m maptasker.main` both find it through the normal import     #
# machinery, and the overrides directory carried a patched customtkinter that the move  #
# to NiceGUI retired.                                                                   #
#                                                                                       #
import sys

from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.reportflags import wants_report
from maptasker.src.core.versiondisplay import display_version

# What asking for the version is, and the only thing that gets the short way (see main()).
VERSION_ONLY = ["-v"]


def main() -> int:
    """Kick off the main program, and return its exit code.

    The console script entry point (see pyproject.toml) and `python -m maptasker.main`
    both arrive here.  The generated console script does sys.exit(main()), so returning
    the code is all that is needed there; the __main__ block below does it by hand.

    'maptasker -v', with nothing else on the line, says the version and stops BEFORE the
    program is imported: importing it brings in the web framework, the Tasker analysis and
    every window, which is about half a second for a reply that is two lines long.  Anything
    else on the command line -- '-v -d' included -- takes the full route, as it always did.

    A report (-healthcheck, -compare ...) is run without importing the program either: it has
    no window, so it has no use for the web framework the program imports at start-up.
    """
    if sys.argv[1:] == VERSION_ONLY:
        try:
            display_version()
        except MapTaskerError as error:
            return error.exit_code
        return 0

    # A report has no window, and the program's own import brings in the web framework the window is built on
    # (a third of a second): so a report is run from the reports' module, and only the rest imports the program.
    # Nothing above this point may need either.
    if wants_report(sys.argv[1:]):
        from maptasker.src.clireports import run  # noqa: PLC0415

        return run(sys.argv[1:])

    from maptasker.src.mapit import mapit_all  # noqa: PLC0415

    return mapit_all()


if __name__ == "__main__":
    # sys.exit() rather than a bare main(): the return value was being discarded, so
    # `python -m maptasker.main` reported success no matter how the run actually ended.
    sys.exit(main())
