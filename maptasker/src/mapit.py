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

# #################################################################################### #
#                                                                                      #
# mapit: Main Program                                                                  #
#            Read the Tasker backup file to build a visual map of its configuration:     #
#            Projects, Profiles, Tasks, Scenes                                          #
#                                                                                      #
# mapitall: Kick-off function                                                           #
#                                                                                      #
# Requirements                                                                         #
#      1- Python version 3.10 or higher                                                #
#      2- Your Tasker backup.xml file, uploaded to your MAC                             #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works  #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# Reference: https://github.com/Taskomater/Tasker-XML-Info                             #
#                                                                                      #
# #################################################################################### #

import contextlib
import copy
import gc
import os
import sys
import webbrowser
from subprocess import run

import psutil

import maptasker.src.proginit as initialize
import maptasker.src.taskuniq as special_tasks
from maptasker.src import projects
from maptasker.src.caveats import display_caveats
from maptasker.src.dirout import output_directory
from maptasker.src.error import error_handler
from maptasker.src.format import format_line
from maptasker.src.getputer import save_restore_args
from maptasker.src.globalvr import get_variables, output_variables
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.sysconst import (
    Colors,
    DISPLAY_DETAIL_LEVEL_everything,
    FormatLine,
    debug_file,
    debug_out,
    logger,
)

# print('Path:', os.getcwd())
# print(
#     "__file__={0:<35} | __name__={1:<25} | __package__={2:<25}".format(
#         __file__, __name__, str(__package__)
#     )
# )
# print(sys.argv)
# This is the one-and-only global variable needed for a special circumstance:
#   ...program crash
#   print("Python version ", sys.version)  # Which Python are we using today?
# print("Tkinter version ", tk.TkVersion)  # Which Tkinter?


crash_debug = False


# ##################################################################################
# Handle program error gracefully if not in debug mode
# ##################################################################################
def on_crash(exctype: str, value: str, traceback: list) -> None:
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
        # sys.__excepthook__ is the default excepthook that prints the stack trace
        # So we use it directly if we want to see it
        sys.__excepthook__(exctype, value, traceback)
        print("MapTasker encountered a runtime error!  Error can be found in maptasker_debug.log")  # noqa: T201
        print("]\nGo to https://github.com/mctinker/Map-Tasker/issues to report the problem.\n")  # noqa: T201
    # Give the user a more graceful error message.
    else:
        # Instead of the stack trace, we print an error message to stderr
        print("\nMapTasker encountered a runtime error!", file=sys.stderr)  # noqa: T201
        # print("Exception type:", exctype, " value:", value)
        print(f"The error log can be found in {debug_file}.")  # noqa: T201
        print(  # noqa: T201
            "Go to https://github.com/mctinker/Map-Tasker/issues to report the problem.\n",
            file=sys.stderr,
        )
        print("\a", end="", flush=True)  # noqa: T201
        # Redirect print to a debug log
        with open(debug_file, "w") as log:
            # sys.stdout = log
            sys.stderr = log
            sys.__excepthook__(exctype, value, traceback)


# ##################################################################################
# Clean up our memory hogs
# ##################################################################################
def clean_up_memory() -> None:
    """
    Clean up our memory hogs
        :return:
    """
    if PrimeItems.xml_tree is not None:
        for elem in PrimeItems.xml_tree.iter():
            elem.clear()
    PrimeItems.tasker_root_elements["all_projects"].clear()
    PrimeItems.tasker_root_elements["all_profiles"].clear()
    PrimeItems.tasker_root_elements["all_tasks"].clear()
    PrimeItems.tasker_root_elements["all_scenes"].clear()
    PrimeItems.tasker_root_elements["all_services"].clear()
    if PrimeItems.directories:
        PrimeItems.directories.clear()
    PrimeItems.directory_items["projects"].clear()
    PrimeItems.directory_items["profiles"].clear()
    if PrimeItems.directory_items["tasks"]:
        PrimeItems.directory_items["tasks"].clear()
    if PrimeItems.directory_items["scenes"]:
        PrimeItems.directory_items["scenes"].clear()
    if PrimeItems.xml_root is not None:
        PrimeItems.xml_root.clear()
    if PrimeItems.output_lines is not None:
        PrimeItems.output_lines.output_lines.clear()
    # Reset all of our primasry items
    PrimeItemsReset()
    PrimeItems.program_arguments = initialize_runtime_arguments

    # Tell python to collect the garbage
    gc.collect()


# ##################################################################################
# write_out_the_file: we have a list of output lines.  Write them out.
# ##################################################################################
def write_out_the_file(my_output_dir: str, my_file_name: str) -> None:
    """
    write_out_the_file: we have a list of output lines.  Write them out.
        :param my_output_dir: directory to output to
        :param my_file_name: name of file to use
        :return: nothing
    """
    logger.info(f"Function Entry: write_out_the_file dir:{my_output_dir}")
    output_file = f"{my_output_dir}{my_file_name}"
    with open(output_file, "w") as out_file:
        # Output the rest that is in our output queue
        for num, item in enumerate(PrimeItems.output_lines.output_lines):
            # Check to see if this is where the directory is to go in the
            # Output directory. if so, output_directory will create it's own list of
            # output lines.
            if "maptasker_directory" in item:
                # Temporarily save our output lines
                temp_lines_out = PrimeItems.output_lines.output_lines
                PrimeItems.output_lines.output_lines = []  # Create a new output queue

                # Do the directory output
                if PrimeItems.program_arguments["directory"]:
                    output_directory()
                # Output the directory line
                for output_line in PrimeItems.output_lines.output_lines:
                    out_file.write(output_line)
                # Restore our regular output
                PrimeItems.output_lines.output_lines = temp_lines_out
                continue

            # Format the output line
            # logger.info(item)
            output_line = format_line(PrimeItems.output_lines, num, item)
            # Continue if we are to ignore this output line.
            if not output_line:
                continue

            # Parse twisty <details>...yield result
            with contextlib.suppress(ValueError):
                details_position = output_line.index("<details>")
                out_file.write(f" {output_line[:details_position]}")
                out_file.write("<details>\r")
                output_line = f"    {output_line[details_position + 9:]}"

            # Write the actual final line out as html
            if output_line.strip():  # Write out if not blank
                logger.info(f"Writing: {output_line}")
                out_file.write(output_line)
            if debug_out:
                logger.debug(f"mapit output line:{output_line}")
                logger.info("Function Exit: write_out_the_file")


# ##################################################################################
# Cleanup memory and let user know there was no match found for Task/Profile
# ##################################################################################
def clean_up_and_exit(
    name: str,
    profile_or_task_name: str,
) -> None:
    """
    Cleanup memory and let user know there was no match found for Task/Profile/Project
        :param name: the name to add to the log/print output
        :param profile_or_task_name: name of the Profile or Task to clean
    """

    # Clear our current list of output lines.
    PrimeItems.output_lines.output_lines.clear()
    # Spit out the error
    error_handler(f'{name} "{profile_or_task_name}" not found!!', 5)
    # Clean up all memory
    clean_up_memory()
    # Exit with code "item" not found.
    sys.exit(5)


# ##################################################################################
# Output grand totals
# ##################################################################################
def output_grand_totals() -> None:
    """
    Output the grand totals of Projects/Profiles/Tasks/Scenes
    """
    grand_total_projects = PrimeItems.grand_totals["projects"]
    grand_total_profiles = PrimeItems.grand_totals["profiles"]
    grand_total_unnamed_tasks = PrimeItems.grand_totals["unnamed_tasks"]
    grand_total_named_tasks = PrimeItems.grand_totals["named_tasks"]
    grand_total_scenes = PrimeItems.grand_totals["scenes"]
    # If doing a directory, then add id to hyperlink to.
    if PrimeItems.program_arguments["directory"]:
        PrimeItems.output_lines.add_line_to_output(
            5,
            '<a id="grand_totals"></a>',
            FormatLine.dont_format_line,
        )

    total_number = "Total number of "
    PrimeItems.output_lines.add_line_to_output(
        1,
        (
            f"<br><hr>Tasker Totals...<br>{total_number}Projects: {grand_total_projects}<br>{total_number}Profiles:  {grand_total_profiles}<br>{total_number}Tasks:"
            f" {grand_total_unnamed_tasks + grand_total_named_tasks} ({grand_total_unnamed_tasks} unnamed,"
            f" {grand_total_named_tasks} named)<br>{total_number}Scenes:"
            f" {grand_total_scenes}<br><br>"
        ),
        ["", "trailing_comments_color", FormatLine.add_end_span],
    )
    PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# ##################################################################################
# Set up the major variables used within this program, and set up crash routine
# ##################################################################################
def initialize_everything() -> dict:
    """
    Set up all the variables and logic in case program craps out
        :return: dictionary of primary items used throughout project, and empty staring
    """

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


# ##################################################################################
# If not doing a single named item, then output unique Project/Profile situations
# ##################################################################################
def process_unique_situations(
    projects_with_no_tasks: list,
    projects_without_profiles: list,
    found_tasks: list,
    single_project_name: str,
    single_profile_name: str,
    single_task_name: str,
) -> None:
    # Don't do anything if we are looking for a specific named item
    """
    Process unique situations
    Args:
        projects_with_no_tasks: list - List of projects with no tasks
        projects_without_profiles: list - List of projects without profiles
        found_tasks: list - List of found tasks
        single_project_name: str - Name of single project to look for
        single_profile_name: str - Name of single profile to look for
        single_task_name: str - Name of single task to look for
    Returns:
        None: Does not return anything
    Processing Logic:
        - Check if looking for a specific named item
        - Get and output tasks not called by any profile
        - Get and output projects that don't have any tasks or profiles
    """
    if single_task_name or single_project_name or single_profile_name:
        return

    # Get and output all Tasks not called by any Profile
    special_tasks.process_tasks_not_called_by_profile(
        projects_with_no_tasks,
        found_tasks,
    )

    # Get and output all Projects that don't have any Tasks or Profiles
    special_tasks.process_missing_tasks_and_profiles(
        projects_with_no_tasks,
        projects_without_profiles,
    )
    return


# ##################################################################################
# Display the output in the default web browser,
# ##################################################################################
def display_output(my_output_dir: str, my_file_name: str) -> None:
    """
    Display the output in the default web browser,
    Args:
        my_output_dir (str): The directory to our current file path.
        my_file_name (str): The name of the file to open.
    """
    logger.debug("MapTasker program ended normally")
    try:
        webbrowser.open(f"file://{my_output_dir}{my_file_name}", new=2)
    except webbrowser.Error:
        error_handler("Error: Failed to open output in browser: your browser is not supported.", 1)
    print("")  # noqa: T201

    # If doing the outline, let 'em know about the map file.
    map_text = (
        "The Configuration Map was saved as MapTasker_Map.txt.  " if PrimeItems.program_arguments["outline"] else ""
    )

    print(f"{Colors.Green}You can find 'MapTasker.html' in the current folder.  {map_text}Program end.")  # noqa: T201
    print("")  # noqa: T201


# ##################################################################################
# Output the configuration outline and map
# ##################################################################################
def process_outline() -> None:
    """
    Output the configuration outline and map
    Args:
        my_output_dir (str): Our current directory for output.
    Returns:
        None: This function does not return anything
    Processing Logic:
    - Call outline_the_configuration() to output the configuration outline
    - Try to open and display the generated map file MapTasker_map.txt using the default text editor
    - If the map file is not found, suppress the error and do not display anything
    """

    """
    Output the configuration outline and map
        Args:
            my_output_dir (str): Our current directory for output.
    """
    # Do the configuration outline and generate the map
    outline_the_configuration()

    # Display the map in the first available text editor
    with contextlib.suppress(FileNotFoundError):
        run(["open", "MapTasker_map.txt"], check=False)  # noqa: S607, S603


# ##################################################################################
# Check if doing a single item and if not found, then clean up and exit
# ##################################################################################
def check_single_item(
    single_project_name: str,
    single_project_found: bool,
    single_profile_name: str,
    single_profile_found: bool,
) -> None:
    """
    Check if doing a single item and if not found, then clean up and exit
        Args:
            single_project_name (str): name of single Project to find, or empty
            single_project_found (bool): True if single Project was found
            single_profile_name (str): name of single Profile to find, or empty
            single_profile_found (bool): True if single Profile was found

        Returns:
            None: nothing
    """
    # If only doing a single named Project and didn't find it, clean up and exit
    if single_project_name and not single_project_found:
        clean_up_and_exit("Project", single_project_name)

    # If only doing a single named Profile and didn't find it, clean up and exit
    if single_profile_name and not single_profile_found:
        clean_up_and_exit("Profile", single_profile_name)


# ##################################################################################
# We've displayed Projects etc.. Now display the back matter
# ##################################################################################
def display_back_matter(
    program_arguments: dict,
    single_project_name: str,
    single_profile_name: str,
    single_task_name: str,
    single_project_found: bool,
    single_profile_found: bool,
    single_task_found: bool,
) -> None:
    # Display global variables
    """
    Displays back matter and finalizes HTML output

    Args:
        program_arguments: Program arguments
        single_project_name: Name of single project to display
        single_profile_name: Name of single profile to display
        single_task_name: Name of single task to display
        single_project_found: Boolean if single project was found
        single_profile_found: Boolean if single profile was found
        single_task_found: Boolean if single task was found

    Returns:
        None

    Processing Logic:
        - Display global variables if detail level is 4
        - Get output directory path
        - Output configuration outline if specified
        - Output grand totals
        - Clean up and exit if single item not found
        - Display program caveats
        - Finalize HTML
        - Write output file
        - Clean up memory
        - Display output file in browser
    """
    if program_arguments["display_detail_level"] == DISPLAY_DETAIL_LEVEL_everything:
        output_variables("Unreferenced Global Variables", "")

    # Get the output directory/folder path
    my_output_dir = os.getcwd()

    # Output the Configuration Outline
    if program_arguments["outline"]:
        process_outline()

    # Output the grand total (Projects/Profiles/Tasks/Scenes)
    output_grand_totals()

    # If doing a single named item and the item was not found, clean up and exit
    if (
        (single_task_name and not single_task_found)
        or (single_profile_name and not single_profile_found)
        or (single_project_name and not single_project_found)
    ):
        clean_up_and_exit("Task", single_task_name)

    # Display the program caveats
    display_caveats()

    # Finalize the HTML
    final_msg = "\n</body>\n</html>"
    PrimeItems.output_lines.add_line_to_output(5, final_msg, FormatLine.dont_format_line)

    #
    logger.debug(f"output directory:{my_output_dir}")
    if my_output_dir is None:
        error_handler(
            f"{Colors.Yellow}MapTasker cancelled.  An error occurred.  Program cancelled.",
            0,
        )
        clean_up_memory()
        sys.exit(2)

    # Finally, write out all of the output that is queued up.
    my_file_name = "/MapTasker.html"
    write_out_the_file(my_output_dir, my_file_name)

    # Display the final results in the default web browser
    display_output(my_output_dir, my_file_name)


# ##################################################################################
# Re-launch our program via the "rerun" feature.
# ##################################################################################
def restart_program() -> None:
    """Restarts the current program, with file objects and descriptors
       cleanup
    """

    try:
        p = psutil.Process(os.getpid())
        for handler in p.get_open_files() + p.connections():
            os.close(handler.fd)
    except Exception as e:
        logger.error(e)

    python = sys.executable
    os.execl(python, python, *sys.argv)


# ##################################################################################
# Handle "rerun" request
# ##################################################################################
def do_rerun() -> None:
    """
    Re-runs the program with a new file
    Args:
        None: No arguments required
    Returns:
        None: Function does not return anything
    Re-runs the program with a new file by:
    - Checking if a file is specified to rerun with
    - Getting the file name
    - Freeing up memory
    - Rerunning the program with the new file
    """
    if PrimeItems.file_to_get:
        file_is_string = isinstance(PrimeItems.file_to_get, str)
        if file_is_string:
            filename = copy.deepcopy(PrimeItems.file_to_get)
        else:
            filename = copy.deepcopy(PrimeItems.file_to_get.name)

        # Free up most of our storage.
        clean_up_memory()

        # Now do it!  Rerun the program.
        with contextlib.suppress(KeyError):
            restart_program()
            # mapit_all(filename)


########################################################################################
#                                                                                      #
#   Main Program Starts Here                                                           #
#                                                                                      #
########################################################################################
"""
-The function 'mapit_all' is the main function of the MapTasker program, which maps the
Tasker environment and generates an HTML output file.



- The function initializes local variables and other necessary stuff.

- It gets colors to use, runtime arguments, found items, and heading by calling the
'start_up' function from the 'proginit' module.

- It prompts the user to locate the Tasker backup XML file to use to map the Tasker
environment.

- It opens and reads the file by calling the 'open_and_get_backup_xml_file' function
from the 'proginit' module.

- It gets all the XML data by calling the 'get_the_xml_data' function from the 'taskerd'
module.

- It checks for a valid Tasker backup XML file.

- It processes Tasker preferences and displays them if the 'display_preferences'
argument is True.

- It processes all projects and their profiles by calling the
'process_projects_and_their_profiles' function from the 'projects' module.

- If a specific project or profile is requested but not found, it exits the program by
calling the 'clean_up_and_exit' function.

- It looks for tasks that are not referenced by profiles and displays a total count.

- It lists any projects without tasks and projects without profiles.

- If a specific task is requested but not found, it exits the program by calling the
'clean_up_and_exit' function.

- It outputs caveats if the 'display_detail_level' argument is greater than or equal
to 3.

- It adds HTML complete code to the output.

- It generates the actual output file and stores it in the current directory.

- It cleans up memory by calling the 'clean_up_memory' function.

- It displays the final output by opening the output file in the default browser.

- It returns the exit code of the program.
"""


def mapit_all(file_to_get: str) -> int:
    # Initialize variables and get the backup xml file
    """
    Maps all Projects, Profiles, Tasks and Scenes in a Tasker backup file

    Args:
        file_to_get (str): The Tasker backup file to process

    Returns:
        int: 0

    Processes Projects and their Profiles:
        - Gets all Project and Profile variables
        - Processes each Project and its associated Profiles
        - Stores details of single selected Project, Profile or Task
    Checks for single selected item and processes accordingly
    Processes unique situations like Tasks not in Profiles and Projects without Profiles/Tasks
    Cleans up memory after completing processing
    """
    (
        found_tasks,
        projects_without_profiles,
        projects_with_no_tasks,
    ) = initialize_everything()

    # Set up file to read if it is passed in (via rerun)
    if file_to_get:
        PrimeItems.file_to_get = file_to_get

    # Get all Tasker variables
    if PrimeItems.program_arguments["display_detail_level"] == DISPLAY_DETAIL_LEVEL_everything:
        get_variables()

    # Process all Projects and their Profiles
    found_tasks = projects.process_projects_and_their_profiles(
        found_tasks,
        projects_without_profiles,
    )

    # Store single item details in local variables
    program_arguments = PrimeItems.program_arguments
    single_project_name = program_arguments["single_project_name"]
    single_profile_name = program_arguments["single_profile_name"]
    single_task_name = program_arguments["single_task_name"]
    single_project_found = PrimeItems.found_named_items["single_project_found"]
    single_profile_found = PrimeItems.found_named_items["single_profile_found"]
    single_task_found = PrimeItems.found_named_items["single_task_found"]

    # See if we are only looking for a single Project/Profile/Task
    check_single_item(
        single_project_name,
        single_project_found,
        single_profile_name,
        single_profile_found,
    )

    # Turn off the directory temporarily so we don't get duplicates
    temp_dir = program_arguments["directory"]
    program_arguments["directory"] = False

    # Get the list of Tasks not called by a Profile,
    # and a list of Projects without Profiles/Tasks
    process_unique_situations(
        projects_with_no_tasks,
        projects_without_profiles,
        found_tasks,
        single_project_name,
        single_profile_name,
        single_task_name,
    )

    # Restore the directory setting for the final directory of Totals
    program_arguments["directory"] = temp_dir

    # Display the trailer stuff, after Projects/Profiles/Tasks/Scenes
    display_back_matter(
        program_arguments,
        single_project_name,
        single_profile_name,
        single_task_name,
        single_project_found,
        single_profile_found,
        single_task_found,
    )

    # Save our runtime settings for next time.
    _, _ = save_restore_args(PrimeItems.program_arguments, PrimeItems.colors_to_use, True)

    # Rerun this program if "Rerun" was selected from GUI
    # First get the filename as a string.
    if program_arguments["rerun"]:
        do_rerun()
    # Just a "run".  Clean up and exit.
    else:
        clean_up_memory()

    return 0
