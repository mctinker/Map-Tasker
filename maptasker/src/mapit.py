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
This is the main coordinator module that imports all the other components and
executes the key steps to take the Tasker backup and produce the visual map output.
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
import sys

import maptasker.src.proginit as initialize
from maptasker.src import projects
from maptasker.src.getputer import save_restore_args
from maptasker.src.globalvr import get_variables
from maptasker.src.lineout import LineOut
from maptasker.src.mapai import map_ai
from maptasker.src.maputils import (
    exit_program,
    restart_program_subprocess,
)
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import (
    DISPLAY_DETAIL_LEVEL_all_variables,
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


# Re-launch our program via the "rerun" feature.
def restart_program() -> None:
    # Restart our program
    # sys.executable = the path of the python interpreter and use it to execute ourselves again.
    """Restarts the program.
    Parameters:
        - None
    Returns:
        - None
    Processing Logic:
        - Call ourselves and exit after the last call."""

    # _ = mapit_all("")
    restart_program_subprocess()
    exit_program(0)  # This should never be called.


# Handle "rerun" request
def do_rerun() -> None:
    """
    Re-runs the program with a new file
    Args:
        None: No arguments required
    Returns:
        None: Function does not return anything
    Re-runs the program with a new file by:
    - Freeing up memory
    - Rerunning the program with the new file
    """

    # Get rid of everything.
    clean_up_memory()

    # Now do it!  Rerun the program.
    restart_program()


########################################################################################
#                                                                                      #
#   Main Program Starts Here                                                           #
#                                                                                      #
########################################################################################
def mapit_all(file_to_get: str) -> int:
    # Initialize variables and get the backup xml file
    """
    Maps all Projects, Profiles, Tasks and Scenes in a Tasker backup file

    Args:
        file_to_get (str): The Tasker backup file to process

    Returns:
        int: 0

    Processes Projects and their Profiles:


        - Initialize everything

        - Gets all Project and Profile variables
        - Processes each Project and its associated Profiles
        - Stores details of single selected Project, Profile or Task

    Checks for single selected item and processes accordingly.
    Processes unique situations like Tasks not in Profiles and Projects without Profiles/Tasks.
    Cleans up memory after completing processing.
    If coming from the GUI, then PrimeItems may already be primed with data.
    """

    # # Save our mapview and doing_diagram flags since 'initialize_everything' would otherwise wipe them out.
    # try:
    #     save_map = PrimeItems.program_arguments["guiview"]
    # except (KeyError, TypeError):
    #     save_map = False
    # try:
    #     save_diagram = PrimeItems.program_arguments["doing_diagram"]
    # except (KeyError, TypeError):
    #     save_diagram = False

    (
        found_tasks,
        projects_without_profiles,
        projects_with_no_tasks,
    ) = initialize_everything()

    # FIX Move into a separate program to generate the output html file.
    # Let the userr know we are in debug mode.
    if PrimeItems.program_arguments["debug"]:
        print(">>>  MapTasker is in debug mode.  <<<")

    PrimeItems.program_arguments["guiview"] = save_map
    PrimeItems.program_arguments["doing_diagram"] = save_diagram

    if PrimeItems.error_code > 0:
        # We have a error.  Spit it out and exit.
        exit_program(PrimeItems.error_code)

    # Set up file to read if it is passed in (via rerun)
    if file_to_get:
        PrimeItems.file_to_get = file_to_get
    else:
        # No file.  Just return to gui
        return 0

    # Get all Tasker variables
    if PrimeItems.program_arguments["display_detail_level"] >= DISPLAY_DETAIL_LEVEL_all_variables:
        get_variables()

    # Process all Projects and their Profiles
    found_tasks = projects.process_projects_and_their_profiles(
        found_tasks,
        projects_without_profiles,
    )

    # Do special handling: wrap up back matter and print the output.
    final_processing(found_tasks, projects_without_profiles, projects_with_no_tasks)

    # Handle Ai Analysis
    if PrimeItems.program_arguments["ai_analyze"]:
        map_ai()
        PrimeItems.program_arguments["rerun"] = True

    # Save our runtime settings for next time.  Make sure we don't save the rerun state as True
    save_rerun_state = PrimeItems.program_arguments["rerun"]
    PrimeItems.program_arguments["rerun"] = False
    _, _ = save_restore_args(
        PrimeItems.program_arguments,
        PrimeItems.colors_to_use,
        to_save=True,
    )
    PrimeItems.program_arguments["rerun"] = save_rerun_state

    # Do a little cleanup by clearing output lines
    PrimeItems.output_lines.output_lines.clear()

    # Rerun this program if "Rerun" was selected from GUI
    # First get the filename as a string.
    if PrimeItems.program_arguments["rerun"]:
        do_rerun()

    return 0
