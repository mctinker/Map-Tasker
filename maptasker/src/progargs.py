"""Process runtime program arguments"""

#! /usr/bin/env python3

#                                                                                      #
# progargs: process program runtime arguments for MapTasker                            #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import os

from maptasker.src.primitem import SINGLE_ITEM_SELECTORS, PrimeItems, clear_single_items
from maptasker.src.runcli import process_cli
from maptasker.src.sysconst import DEBUG_PROGRAM, VIEW_LIMIT_DEFAULT

# The "Unlimited" the GUI's View Limit dropdown offers, as a number of lines.
VIEW_LIMIT_UNLIMITED = 9999999


# Settle on the view limit for this run.
def resolve_view_limit(view_limit: object) -> int:
    """Turn the view limit held in the runtime arguments into a number of output lines.

    Args:
        view_limit (object): the value the runtime arguments hold, which is normally a
            number of lines but can be the GUI dropdown's own "Unlimited".

    Returns:
        int: the number of lines to cut the Map off at.
    """
    if view_limit == "Unlimited":
        return VIEW_LIMIT_UNLIMITED
    try:
        return int(view_limit)
    except (TypeError, ValueError):
        # Nothing usable (an empty or hand-edited settings file): the default stands.
        return VIEW_LIMIT_DEFAULT


# Get the program arguments (e.g. python mapit.py -x)
def get_program_arguments() -> None:
    """
    Process program arguments, from the GUI or the command line.
    Args:
        DEBUG_PROGRAM: Whether program is in debug mode
    Returns:
        None: No return value
    - Hand off to process_cli, which reads the runtime options and, when the GUI applies,
      runs it (see runcli.process_cli for how that choice is made)
    - Blank the single Project/Profile/Task names if more than one was restored
    - Override debug argument to True if in debug mode
    - Carry the view limit over to where the Map build reads it
    - Fall back to backup.xml if the file named in the arguments does not exist"""
    # Process the command line runtime options.  This will call the GUI if the GUI is being used,
    # and will call the CLI processing if not.  This is where we will get all of our runtime arguments
    # from the user.
    #
    # process_cli() owns that choice entirely, and starts the GUI itself when it applies --
    # it is the branch that can also honour -v and capture what the GUI returns.  There used
    # to be a second, unconditional 'if GUI: process_gui(True)' right here, so a GUI session
    # was started twice per run: process_cli's call blocked until the window was closed, and
    # this one immediately opened another.  It also discarded process_gui's return value,
    # unlike process_cli, which assigns it back into program_arguments and colors_to_use.
    #
    # Setting program_arguments["gui"] here was pointless for the same reason: process_cli
    # begins by replacing program_arguments wholesale via initialize_runtime_arguments(),
    # so anything written before that call is discarded.  config.GUI is read there instead.
    process_cli()

    # Make sure we don't have too much: more than one single item specified in the saved file
    # clears them all.  Every kind counts, Scene included -- .get, since a settings file from
    # before single Scenes existed has no key for one.
    if sum(bool(PrimeItems.program_arguments.get(name_key)) for name_key, _, _ in SINGLE_ITEM_SELECTORS) > 1:
        clear_single_items()

    # The Map build reads the view limit from PrimeItems.view_limit (bildhtml.write_out_the_file),
    # not from the runtime arguments, so hand the value over.  The GUI sets it again from its
    # own "View Limit" setting before each build (userintr.MapTaskerEventHandlers.view_event); this
    # gives a command-line run -- which has no GUI to do that -- the limit it asked for.
    PrimeItems.view_limit = resolve_view_limit(PrimeItems.program_arguments.get("view_limit"))

    # Are we in development mode?  If so, override debug argument
    if DEBUG_PROGRAM:
        PrimeItems.program_arguments["debug"] = True

    # If the file specified in the arguments doesn't exist, use backup.xml
    if (
        "file" in PrimeItems.program_arguments
        and PrimeItems.program_arguments["file"]
        and not os.path.exists(PrimeItems.program_arguments["file"])
    ):
        PrimeItems.program_arguments["file"] = "backup.xml"
