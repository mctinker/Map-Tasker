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
import platform
import sys

from nicegui import app

from maptasker.src import console
from maptasker.src.actionc import load_arg_specs
from maptasker.src.error import exit_program
from maptasker.src.lineout import LineOut
from maptasker.src.maputil2 import log_startup_values
from maptasker.src.mtexcept import MapTaskerError
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.progargs import get_program_arguments
from maptasker.src.proginit import (
    check_versions,
    get_data_and_output_intro,
    rebuild_action_tables,
    setup_colors,
)
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


def _install_async_exception_handler() -> None:
    """Route NiceGUI's background-task crashes to handle_async_exceptions (runs as a startup handler)."""
    asyncio.get_running_loop().set_exception_handler(handle_async_exceptions)


# Perform maptasker program initialization functions
def start_up() -> None:
    # Get any arguments passed to program
    """
    Initializes the program startup.
    Args:
        None
    Returns:
        None
    Processing Logic:
        - Gets any arguments passed to the program
        - Migrates any old argument files to a new format
        - Gets runtime arguments from the command line or GUI
        - Gets the list of available fonts
        - Gets a map of colors to use
        - Gets key program elements and outputs intro text
        - Logs startup values if debug mode is enabled
    """
    # If debug mode, fire-up the log.
    if "-d" in sys.argv or "-debug" in sys.argv:
        console.say("Debug turned on via startup argument")
        log_startup_values()
    logger.info(f"sys.argv{sys.argv!s}")

    # Get the OS so we know which directory slash to use (/ or \)
    if platform.system() == "Windows":
        PrimeItems.slash = "\\"
        PrimeItems.windows_system = True
    else:
        PrimeItems.slash = "/"
        PrimeItems.windows_system = False

    # Validate the runtime version of python
    check_versions()

    load_arg_specs()

    # NOTE: FOR DEVELOPMENT ONLY!!! 'build_all = True' ONLY WITH A NEW UPDATE OF TASKER!
    # It rebuilds tables from the network and a backup xml and then exits, so shipping it
    # as True would end every user's startup.  tests/test_build_all.py asserts it is False.
    build_all = False
    if build_all:
        rebuild_action_tables()
        exit_program(0)
    # END OF DEVELOPMENT CODE

    # Get runtime arguments (from CLI or GUI)
    get_program_arguments()

    # Force GUI mode
    PrimeItems.program_arguments["gui"] = True

    # Get our map of colors if we don't have them.
    if not PrimeItems.colors_to_use:
        PrimeItems.colors_to_use = setup_colors()

    # Display a popup window telling user we are analyzing
    if PrimeItems.program_arguments["doing_diagram"]:
        PrimeItems.program_arguments["doing_diagram"] = False

    # Get the XML data and output the front matter
    if PrimeItems.file_to_get or PrimeItems.program_arguments["file"]:
        _ = get_data_and_output_intro(True)  # Force the front matter to be created.


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

    # Attach the handler to NiceGUI's event loop once that loop is running.  There is no loop yet
    # at this point -- ui.run() makes its own later -- and asyncio.get_event_loop() raises
    # "There is no current event loop" here under Python 3.14 instead of creating a spare one.
    if not app.is_started:
        app.on_startup(_install_async_exception_handler)

    # Get colors to use, runtime arguments etc...all of our primary items we need
    # throughout
    start_up()

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
