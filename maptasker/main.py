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
from maptasker.src.mapit import mapit_all


def main() -> int:
    """Kick off the main program, and return its exit code.

    The console script entry point (see pyproject.toml) and `python -m maptasker.main`
    both arrive here.
    """
    return mapit_all()


if __name__ == "__main__":
    main()
