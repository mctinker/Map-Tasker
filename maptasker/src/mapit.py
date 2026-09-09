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

import maptasker.src.proginit as initialize
from maptasker.src import console
from maptasker.src.lineout import LineOut
from maptasker.src.mtexcept import MapTaskerError
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import (
    debug_file,
    logger,
)

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
            console.error(value.error)
            return
        # sys.__excepthook__ is the default excepthook that prints the stack trace
        # So we use it directly if we want to see it
        sys.__excepthook__(exctype, value, traceback)
        console.error(
            "MapTasker encountered a runtime error!  Error can be found in maptasker_debug.log",
        )
        console.error(
            "Go to https://github.com/mctinker/Map-Tasker/issues to report the problem.\n",
        )
    # Give the user a more graceful error message.
    else:
        # Instead of the stack trace, a plain message.  console.error writes to stderr and
        # logs it, so the same words are in the log file this message points the user at.
        console.error("\nMapTasker encountered a runtime error!")
        console.error(f"The error log can be found in {debug_file}.")
        console.error(
            "Go to https://github.com/mctinker/Map-Tasker/issues to report the problem.\n",
        )
        console.say("\a", end="", flush=True)  # Bell
        # Redirect print to a debug log
        with open(debug_file, "w") as log:
            # sys.stdout = log
            sys.stderr = log
            sys.__excepthook__(exctype, value, traceback)


def handle_async_exceptions(loop, context) -> None:
    """Custom handler for async loop background crashes."""
    exception = context.get("exception")
    message = context.get("message")

    # Silence the stack trace completely, and route a clean message to the log.  These are
    # background-task failures: worth recording every time, worth showing only to whoever
    # is debugging.  console.error logs and shows; console.debug logs and stays quiet.
    err_message = f"Async Background Task aborted: {exception}" if exception else f"Async Loop Error: {message}"
    console.debug(err_message)
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
        int: the status the process should exit with -- 0 when the run finished or was
            shut down cleanly, otherwise the code carried by the MapTaskerError that
            ended it.

    Processes Projects and their Profiles:


        - Initialize everything

        This will eventually call rungui or runcli.
    """
    try:
        _, _, _ = initialize_everything()
    except MapTaskerError as error:
        # The top of the process, and the only place that turns "MapTasker cannot carry
        # on" back into an exit status.  Everything below here raises rather than exits
        # (see maputils.exit_program) precisely so that this decision is made once, here,
        # where it is known that MapTasker really is the whole program.
        #
        # A message is only shown for a genuine failure.  A clean shutdown -- the GUI's
        # Exit button, "-v" having printed the version -- arrives here too, carrying code
        # 0, and has already said whatever it had to say.
        if error.exit_code and error.message:
            console.error(error.message)
        logger.debug(f"mapit_all exiting with code {error.exit_code}: {error.message}")
        return error.exit_code

    # Code drops down here upon exit of the GUI.

    return 0
