#! /usr/bin/env python3


#  $$\      $$\                           $$$$$$$$\                  $$\
#  $$$\    $$$ |                          \__$$  __|                 $$ |
#  $$$$\  $$$$ | $$$$$$\   $$$$$$\           $$ | $$$$$$\   $$$$$$$\ $$ |  $$\  $$$$$$\   $$$$$$\
#  $$\$$\$$ $$ | \____$$\ $$  __$$\          $$ | \____$$\ $$  _____|$$ | $$  |$$  __$$\ $$  __$$\
#  $$ \$$$  $$ | $$$$$$$ |$$ /  $$ |         $$ | $$$$$$$ |\$$$$$$\  $$$$$$  / $$$$$$$$ |$$ |  \__|
#  $$ |\$  /$$ |$$  __$$ |$$ |  $$ |         $$ |$$  __$$ | \____$$\ $$  _$$<  $$   ____|$$ |
#  $$ | \_/ $$ |\$$$$$$$ |$$$$$$$  |         $$ |\$$$$$$$ |$$$$$$$  |$$ | \$$\ \$$$$$$$\ $$ |
#  \__|     \__| \_______|$$  ____/          \__| \_______|\_______/ \__|  \__| \_______|\__|
#                         $$ |
#                         $$ |
#                         \__|

"""
This is the main coordinator module that kicks-off the other components that launch the GUI.
"""

#                                                                                      #
# mapit: Main Program                                                                  #
#            Read the Tasker backup file to build a visual map of its configuration:   #
#            Projects, Profiles, Tasks, Scenes                                         #
#                                                                                      #
# mapitall: Kick-off function                                                          #
#                                                                                      #
# Reference: https://github.com/Taskomater/Tasker-XML-Info                             #
#                                                                                      #
import asyncio
import sys
from venv import logger

import maptasker.src.proginit as initialize
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import (
    debug_file,
)

# print("Tkinter version ", tk.TkVersion)  # Which Tkinter?
# print(tk.Tcl().call("info", "library"))
# print(tk.Tcl().call("info", "patchlevel"))

crash_debug = False


# Handle program error gracefully if not in debug mode
def on_crash(exctype: object, value: str, traceback: list) -> None:
    # Display the crash report if in debug mode
    """
    Handle runtime errors
    Args:
        exctype: Exception type
        value: Exception value
        traceback: Traceback object
    Returns:
        None
    Processing Logic:
        - Display crash report if in debug mode using default excepthook
        - Else print a more graceful error message to stderr
        - Write detailed crash report to debug log file
        - Redirect print/stderr to log for detailed crash information
    """
    if crash_debug:
        if "does not support chat" in value.error:
            PrimeItems.program_arguments["ai_analysis"] = False
            print(value.error)
            return
        # sys.__excepthook__ is the default excepthook that prints the stack trace
        # So we use it directly if we want to see it
        sys.__excepthook__(exctype, value, traceback)
        print(
            "MapTasker encountered a runtime error!  Error can be found in maptasker_debug.log",
        )
        print(
            "]\nGo to https://github.com/mctinker/Map-Tasker/issues to report the problem.\n",
        )
    # Give the user a more graceful error message.
    else:
        # Instead of the stack trace, we print an error message to stderr
        print("\nMapTasker encountered a runtime error!", file=sys.stderr)
        # print("Exception type:", exctype, " value:", value)
        print(f"The error log can be found in {debug_file}.")
        print(
            "Go to https://github.com/mctinker/Map-Tasker/issues to report the problem.\n",
            file=sys.stderr,
        )
        print("\a", end="", flush=True)
        # Redirect print to a debug log
        with open(debug_file, "w") as log:
            # sys.stdout = log
            sys.stderr = log
            sys.__excepthook__(exctype, value, traceback)


def handle_async_exceptions(loop, context) -> None:
    """Custom handler for async loop background crashes."""
    exception = context.get("exception")
    message = context.get("message")

    # Silence the stack trace completely, and route a clean message to your logger
    if exception:
        err_message = f"Async Background Task aborted: {exception}"
        print(err_message)
        logger.error(err_message)
    else:
        err_message = f"Async Loop Error: : {message}"
        print(err_message)
        logger.error(err_message)


# Set up the major variables used within this program, and set up crash routine
def initialize_everything() -> tuple[list, list, list]:
    """
    Set up all the variables and logic in case program craps out
        :return: empty list of primary items used throughout project
    """
    # Reset colors to use if running unit test
    if "-test=yes" in sys.argv:
        PrimeItems.colors_to_use = []

    # Check to see if we might be coming from another program (e.g. run_test.py), and we are not generating a map view.
    # If so, re-initialize PrimeItems since it is still carrying the values from the last test/run.
    if (
        PrimeItems.colors_to_use and (PrimeItems.program_arguments and not PrimeItems.program_arguments["guiview"])
    ) or not PrimeItems.colors_to_use:
        PrimeItemsReset()

    # We have to initialize output_lines here. Otherwise, we'll lose the output class
    # with the upcoming call to start_up.
    PrimeItems.output_lines = LineOut()

    # Attach the handler to the active running Nicegui ui loop
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_async_exceptions)

    # Get colors to use, runtime arguments etc...all of our primary items we need
    # throughout
    initialize.start_up()

    # Set up to catch all crashes gracefully
    if sys.excepthook == sys.excepthook:
        global crash_debug  # noqa: PLW0603
        if PrimeItems.program_arguments["debug"]:
            crash_debug = True
        sys.excepthook = on_crash

    # If debugging, force an ESC so that the full command/path is not displayed in
    #   VsCode terminal window.
    # if PrimeItems.program_arguments["debug"]:
    #     print("\033c")

    return [], [], []


########################################################################################
#                                                                                      #
#   Main Program Starts Here                                                           #
#                                                                                      #
########################################################################################
def mapit_all() -> int:
    # Initialize variables and get the backup xml file
    """
    Maps all Projects, Profiles, Tasks and Scenes in a Tasker backup file

    Args:
        None

    Returns:
        int: 0

    Processes Projects and their Profiles:


        - Initialize everything

        This will eventually call rungui or runcli.
    """

    _, _, _ = initialize_everything()

    # Code drops down here upon exit of the GUI.

    return 0
