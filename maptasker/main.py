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
    """
    if sys.argv[1:] == VERSION_ONLY:
        try:
            display_version()
        except MapTaskerError as error:
            return error.exit_code
        return 0

    # Imported here, and only here, because that is the point: nothing above this line may
    # need the program.
    from maptasker.src.mapit import mapit_all  # noqa: PLC0415

    return mapit_all()


if __name__ == "__main__":
    # sys.exit() rather than a bare main(): the return value was being discarded, so
    # `python -m maptasker.main` reported success no matter how the run actually ended.
    sys.exit(main())
