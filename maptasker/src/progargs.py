"""Process runtime program arguments"""

#! /usr/bin/env python3

#                                                                                      #
# progargs: process program runtime arguments for MapTasker                            #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from maptasker.src.config import GUI
from maptasker.src.primitem import PrimeItems
from maptasker.src.runcli import process_cli
from maptasker.src.rungui import process_gui
from maptasker.src.sysconst import DEBUG_PROGRAM


# Get the program arguments (e.g. python mapit.py -x)
def get_program_arguments() -> None:
    # Are we using the GUI?
    """
    Process program arguments from GUI or CLI.
    Args:
        GUI: Whether GUI is being used
        DEBUG_PROGRAM: Whether program is in debug mode
    Returns:
        None: No return value
    - Parse GUI for program arguments and colors if GUI is being used
    - Parse command line if no GUI
    - Override debug argument to True if in debug mode"""
    if GUI:
        PrimeItems.program_arguments["gui"] = True

    # Process the command line runtime options
    process_cli()

    # Do GUI processing if GUI is being used
    if GUI:
        process_gui(True)

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
