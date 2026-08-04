"""Process runtime program arguments"""

#! /usr/bin/env python3

#                                                                                      #
# progargs: process program runtime arguments for MapTasker                            #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import os

from maptasker.src.primitem import PrimeItems
from maptasker.src.runcli import process_cli
from maptasker.src.sysconst import DEBUG_PROGRAM


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

    # Make sure we don't have too much
    if (
        (PrimeItems.program_arguments["single_project_name"] and PrimeItems.program_arguments["single_profile_name"])
        or (PrimeItems.program_arguments["single_project_name"] and PrimeItems.program_arguments["single_task_name"])
        or (PrimeItems.program_arguments["single_profile_name"] and PrimeItems.program_arguments["single_task_name"])
    ):
        # More than one single item wasd specified in saved file.  Set all to blank
        PrimeItems.program_arguments["single_task_name"] = ""
        PrimeItems.program_arguments["single_project_name"] = ""
        PrimeItems.program_arguments["single_profile_name"] = ""

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
