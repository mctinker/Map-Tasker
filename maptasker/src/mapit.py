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


# #################################################################################### #
#                                                                                      #
# mapit: Main Program                                                                  #
#            Read the Tasker backup file to build a visual map of its configuration:   #
#            Projects, Profiles, Tasks, Scenes                                         #
#                                                                                      #
# mapitall: Kick-off function                                                          #
#                                                                                      #
# Requirements                                                                         #
#      1- Python version 3.10 or higher                                                #
#      2- Your Tasker backup.xml file, uploaded to your MAC                            #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# Reference: https://github.com/Taskomater/Tasker-XML-Info                             #
#                                                                                      #
# #################################################################################### #

import contextlib
import gc
import sys
import webbrowser  # To be removed in Python 10.13 (2023?)
from os import getcwd

import maptasker.src.proginit as initialize
import maptasker.src.projects as projects
import maptasker.src.taskuniq as special_tasks
from maptasker.src.caveats import display_caveats
from maptasker.src.dirout import output_directory
from maptasker.src.error import error_handler
from maptasker.src.format import format_line
from maptasker.src.lineout import LineOut
from maptasker.src.outline import outline_the_configuration
from maptasker.src.primitem import initialize_primary_items
from maptasker.src.sysconst import Colors, FormatLine, debug_file, debug_out, logger
from maptasker.src.variables import get_variables, output_variables

# import os
# print('Path:', os.getcwd())
# print(
#     "__file__={0:<35} | __name__={1:<25} | __package__={2:<25}".format(
#         __file__, __name__, str(__package__)
#     )
# )
# print(sys.argv)

# This is the one-and-only global variable needed for a special circumstance:
#   ...program crash
#   print(sys.version)  # Which Python are we using today?

crash_debug = False


# ##################################################################################
# Handle program error gracefully if not in debug mode
# ##################################################################################
def on_crash(exctype, value, traceback):
    # Display the crash report if in debug mode
    if crash_debug:
        # sys.__excepthook__ is the default excepthook that prints the stack trace
        # So we use it directly if we want to see it
        sys.__excepthook__(exctype, value, traceback)
        print("MapTasker encountered a runtime error!  Error in maptasker_debug.log")
    # Give the user a more graceful error message.
    else:
        # Instead of the stack trace, we print an error message to stderr
        print("\nMapTasker encountered a runtime error!", file=sys.stderr)
        # print("Exception type:", exctype, " value:", value)
        print(f"The error log can be found in {debug_file}.")
        print(
            "Go to https://github.com/mctinker/Map-Tasker/issues \
            to report the problem.\n",
            file=sys.stderr,
        )
        # Redirect print to a debug log
        with open(debug_file, "w") as log:
            # sys.stdout = log
            sys.stderr = log
            sys.__excepthook__(exctype, value, traceback)


# ##################################################################################
# Clean up our memory hogs
# ##################################################################################
def clean_up_memory(
    primary_items: dict,
) -> None:
    """
    Clean up our memory hogs
        :param primary_items:  Program registry.  See primitem.py for details.
        :return:
    """
    for elem in primary_items["xml_tree"].iter():
        elem.clear()
    primary_items["tasker_root_elements"]["all_projects"].clear()
    primary_items["tasker_root_elements"]["all_profiles"].clear()
    primary_items["tasker_root_elements"]["all_tasks"].clear()
    primary_items["tasker_root_elements"]["all_scenes"].clear()
    primary_items["xml_root"].clear()
    primary_items["output_lines"].output_lines.clear()
    gc.collect
    return


# ##################################################################################
# write_out_the_file: we have a list of output lines.  Write them out.
# ##################################################################################
def write_out_the_file(primary_items, my_output_dir: str, my_file_name: str) -> None:
    """
    write_out_the_file: we have a list of output lines.  Write them out.
        :param primary_items:  Program registry.  See primitem.py for details.
        :param my_output_dir: directory to output to
        :param my_file_name: name of file to use
        :return: nothing
    """
    logger.info(f"Function Entry: write_out_the_file dir:{my_output_dir}")
    with open(f"{my_output_dir}{my_file_name}", "w") as out_file:
        # Output the rest that is in our output queue
        for num, item in enumerate(primary_items["output_lines"].output_lines):
            # Check to see if this is where the direcory is to go.
            # Output dirreectory if so.
            if "maptasker_directory" in item:
                # Temporaily save our output lines
                temp_lines_out = primary_items["output_lines"].output_lines
                primary_items[
                    "output_lines"
                ].output_lines = []  # Create a new output queue

                # Do the direcory output
                if primary_items["program_arguments"]["directory"]:
                    output_directory(primary_items)
                # Output the directory line
                for output_line in primary_items["output_lines"].output_lines:
                    out_file.write(output_line)
                # Restore our regular output
                primary_items["output_lines"].output_lines = temp_lines_out
                continue

            # Format the output line
            # logger.info(item)
            output_line = format_line(primary_items["output_lines"], num, item)
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
    return


# ##################################################################################
# Cleanup memory and let user know there was no match found for Task/Profile
# ##################################################################################
def clean_up_and_exit(
    primary_items: dict,
    name: str,
    profile_or_task_name: str,
) -> None:
    """
    Cleanup memory and let user know there was no match found for Task/Profile/Project
        :param primary_items:  Program registry.  See primitem.py for details.
        :param name: the name to add to the log/print output
        :param profile_or_task_name: name of the Profile or Task to clean
    """

    # Clear our current list of output lines.
    primary_items["output_lines"].output_lines.clear()
    # Spit out the error
    error_handler(f'{name} "{profile_or_task_name}" not found!!', 0)
    # Clean up all memory
    clean_up_memory(primary_items)
    # Exit with code "item" not found.
    sys.exit(5)


# ##################################################################################
# Output grand totals
# ##################################################################################
def output_grand_totals(primary_items: dict) -> None:
    """
    Output the grand totals of Projects/Profiles/Tasks/Scenes
        :param primary_items:  Program registry.  See primitem.py for details.
    """
    grand_total_projects = primary_items["grand_totals"]["projects"]
    grand_total_profiles = primary_items["grand_totals"]["profiles"]
    grand_total_unnamed_tasks = primary_items["grand_totals"]["unnamed_tasks"]
    grand_total_named_tasks = primary_items["grand_totals"]["named_tasks"]
    grand_total_scenes = primary_items["grand_totals"]["scenes"]
    # If doing a directory, then add id to hyperlink to.
    if primary_items["program_arguments"]["directory"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            5,
            '<a id="grand_totals"></a>',
            FormatLine.dont_format_line,
        )

    total_number = "Total number of "
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        1,
        (
            f"<br>{total_number}Projects: {grand_total_projects}<br>{total_number}Profiles:  {grand_total_profiles}<br>{total_number}Tasks:"
            f" {grand_total_unnamed_tasks + grand_total_named_tasks} ({grand_total_unnamed_tasks} unnamed,"
            f" {grand_total_named_tasks} named)<br>{total_number}Scenes:"
            f" {grand_total_scenes}<br><br>"
        ),
        ["", "trailing_comments_color", FormatLine.add_end_span],
    )
    primary_items["output_lines"].add_line_to_output(
        primary_items, 3, "", FormatLine.dont_format_line
    )


# ##################################################################################
# Set up the major variables used within this program, and set up crash routine
# ##################################################################################
def initialize_everything(file_to_get: str) -> dict:
    """
    Set up all the variables and logic in case program craps out
        :param file_to_get: file name to get
        :return: dictionary of primary items used throughout project, and empty staring
    """
    # Initialize primary_items
    primary_items = initialize_primary_items(file_to_get)
    # We have to initialize output_lines here. Otherwise, we'll lose the output class
    # with the upcoming call to start_up.
    primary_items["output_lines"] = LineOut()

    # Get colors to use, runtime arguments etc...all of our primary items we need
    # throughout
    primary_items = initialize.start_up(primary_items)

    # Set up to catch all crashes gracefully
    if sys.excepthook == sys.excepthook:
        global crash_debug
        if primary_items["program_arguments"]["debug"]:
            crash_debug = True
        sys.excepthook = on_crash

    # If debugging, force an ESC so that the full command/path is not displayed in
    #   VsCode terminal window.
    # if primary_items["program_arguments"]["debug"]:
    #     print("\033c")

    return primary_items, [], [], []


# ##################################################################################
# If not doing a single named item, then output unique Project/Profile situations
# ##################################################################################
def process_unique_situations(
    primary_items,
    projects_with_no_tasks,
    projects_without_profiles,
    found_tasks,
    single_project_name,
    single_profile_name,
    single_task_name,
):
    # Don't do anything if we are looking for a specific named item
    if single_task_name or single_project_name or single_profile_name:
        return

    # Get and output all Tasks not called by any Profile
    special_tasks.process_tasks_not_called_by_profile(
        primary_items,
        projects_with_no_tasks,
        found_tasks,
    )

    # Get and output all Projects that don't have any Tasks or Profiles
    special_tasks.process_missing_tasks_and_profiles(
        primary_items,
        projects_with_no_tasks,
        projects_without_profiles,
    )
    return


# ##################################################################################
# Display the output in the default web browser
# ##################################################################################
def display_output(primary_items, my_output_dir: str, my_file_name: str) -> None:
    """_summary_

    Args:
        my_output_dir (str): The direectory to our current file path.
        my_file_name (str): The name of the file to open.
    """
    logger.debug("MapTasker program ended normally")
    try:
        webbrowser.open(f"file://{my_output_dir}{my_file_name}", new=2)
    except webbrowser.Error:
        error_handler(
            "Error: Failed to open output in browser: your browser is not supported.", 1
        )
    print("")

    # If doing the outline, let 'em know about the map file.
    map_text = (
        "The Configuration Map was saved as MapTasker_Map.txt.  "
        if primary_items["program_arguments"]["outline"]
        else ""
    )

    print(
        f"{Colors.Green}You can find 'MapTasker.html' in the current folder.  {map_text}Program end."
    )
    print("")


# ##################################################################################
# Output the configuration outline and map
# ##################################################################################
def process_outline(primary_items: dict, my_output_dir: str) -> None:
    from subprocess import run

    """_summary_
    Output the configuration outline and map
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            my_output_dir (str): Our current directory for output.
    """
    # Do the configuration outline and generate the map
    outline_the_configuration(primary_items)

    # Display the map in the first available text editor
    with contextlib.suppress(FileNotFoundError):
        run(["open", "MapTasker_map.txt"])


# ##################################################################################
# Check if doing a single item and if not found, then clean up and exit
# ##################################################################################
def check_single_item(
    primary_items: dict,
    single_project_name: str,
    single_project_found: bool,
    single_profile_name: str,
    single_profile_found: bool,
) -> None:
    """_summary_
    Check if doing a single item and if not found, then clean up and exit
        Args:
            :param primary_items:  Program registry.  See primitem.py for details.
            single_project_name (str): name of single Project to find, or empty
            single_project_found (bool): True if single Project was found
            single_profile_name (str): name of single Profile to find, or empty
            single_profile_found (bool): True if single Profile was found

        Returns:
            None: nothing
    """
    # If only doing a single named Project and didn't find it, clean up and exit
    if single_project_name and not single_project_found:
        clean_up_and_exit(primary_items, "Project", single_project_name)

    # If only doing a single named Profile and didn't find it, clean up and exit
    if single_profile_name and not single_profile_found:
        clean_up_and_exit(primary_items, "Profile", single_profile_name)


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
    # Intialize variables and get the backup xml file
    (
        primary_items,
        found_tasks,
        projects_without_profiles,
        projects_with_no_tasks,
    ) = initialize_everything(file_to_get)

    # Get all Tasker variables
    if primary_items["program_arguments"]["display_detail_level"] == 4:
        get_variables(primary_items)

    # Process all Projects and their Profiles
    found_tasks = projects.process_projects_and_their_profiles(
        primary_items,
        found_tasks,
        projects_without_profiles,
    )

    # Store single item details in local variables
    program_arguments = primary_items["program_arguments"]
    single_project_name = program_arguments["single_project_name"]
    single_profile_name = program_arguments["single_profile_name"]
    single_task_name = program_arguments["single_task_name"]
    single_project_found = primary_items["found_named_items"]["single_project_found"]
    single_profile_found = primary_items["found_named_items"]["single_profile_found"]
    single_task_found = primary_items["found_named_items"]["single_task_found"]

    # See if we are only looking for a single Projcet/Profile/Task
    check_single_item(
        primary_items,
        single_project_name,
        single_project_found,
        single_profile_name,
        single_profile_found,
    )

    # Turn off the directory temporarily so we don't get duplicates
    temp_dir = program_arguments["directory"]
    program_arguments["directory"] = False

    # Get the list of Tasks not called by a Porfile,
    # and a list of Projects without Profiles/Tasks
    process_unique_situations(
        primary_items,
        projects_with_no_tasks,
        projects_without_profiles,
        found_tasks,
        single_project_name,
        single_profile_name,
        single_task_name,
    )

    # Restore the directory setting for the final directory of Totals
    program_arguments["directory"] = temp_dir

    # Display global variables
    if program_arguments["display_detail_level"] == 4:
        output_variables(primary_items, "Unreferenced Global Variables", "")

    # Get the output directory
    my_output_dir = getcwd()

    # Output the Configuration Outline
    if program_arguments["outline"]:
        process_outline(primary_items, my_output_dir)

    # Output the grand total (Projects/Profiles/Tasks/Scenes)
    output_grand_totals(primary_items)

    # If doing a single named item and the item was not found, clean up and exit
    if (
        (single_task_name and not single_task_found)
        and (not single_profile_name or single_profile_found)
        and (not single_project_name or single_project_found)
    ):
        clean_up_and_exit(primary_items, "Task", single_task_name)

    # Display the program caveats
    display_caveats(primary_items)

    # Finalize the HTML
    final_msg = "\n</body>\n</html>"
    primary_items["output_lines"].add_line_to_output(
        primary_items, 5, final_msg, FormatLine.dont_format_line
    )

    #
    logger.debug(f"output directory:{my_output_dir}")
    if my_output_dir is None:
        error_handler(
            f"{Colors.Yellow}MapTasker cancelled.  An error occurred.  Program cancelled.",
            0,
        )
        clean_up_memory(primary_items)
        sys.exit(2)

    # Finally, write out alol of the outp[ut that is queied up
    my_file_name = "/MapTasker.html"
    write_out_the_file(primary_items, my_output_dir, my_file_name)

    # Clean up
    clean_up_memory(primary_items)

    # Display the final results in the default web browser
    display_output(primary_items, my_output_dir, my_file_name)

    # Rerun this program if "Rerun" was slected from GUI
    with contextlib.suppress(KeyError):
        if program_arguments["rerun"]:
            mapit_all(primary_items["file_to_get"].name)
    return 0
