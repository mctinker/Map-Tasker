#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# mapit: Main Program                                                                        #
#            Read the Tasker backup file to build a visual map of its configuration:         #
#            Projects, Profiles, Tasks, Scenes                                               #
#                                                                                            #
# mapitall: Kick-off function                                                                #
#                                                                                            #
# Requirements                                                                               #
#      1- Python version 3.10 or higher                                                      #
#      2- Your Tasker backup.xml file, uploaded to your MAC                                  #
#                                                                                            #
# Note: This should work on PC OS's other than a MAC, but it has not been tested             #
#       on any other platform.                                                               #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# Reference: https://github.com/Taskomater/Tasker-XML-Info                                   #
#                                                                                            #
# ########################################################################################## #

import contextlib
import sys
import webbrowser  # To be removed in Python 10.13 (2023?)
from os import getcwd

import maptasker.src.proginit as initialize
import maptasker.src.projects as projects
import maptasker.src.taskuniq as special_tasks
from maptasker.src.caveats import display_caveats
from maptasker.src.prefers import get_preferences
from maptasker.src.error import error_handler
from maptasker.src.sysconst import logger
from maptasker.src.sysconst import debug_out
from maptasker.src.lineout import LineOut


# import os
# print('Path:', os.getcwd())
# print('__file__={0:<35} | __name__={1:<25} | __package__={2:<25}'.format(__file__,__name__,str(__package__)))


# #######################################################################################
# Clean up our memory hogs
# #######################################################################################
def clean_up_memory(
    primary_items: dict,
) -> None:
    """
    Clean up our memory hogs
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
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
    return


# #######################################################################################
# write_out_the_file: we have a list of output lines.  Write them out.
# #######################################################################################
def write_out_the_file(primary_items, my_output_dir: str, my_file_name: str) -> None:
    """
    write_out_the_file: we have a list of output lines.  Write them out.
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param my_output_dir: directory to output to
        :param my_file_name: name of file to use
        :return: nothing
    """
    logger.info(f"Function Entry: write_out_the_file dir:{my_output_dir}")
    with open(my_output_dir + my_file_name, "w") as out_file:
        for num, item in enumerate(primary_items["output_lines"].output_lines):
            # If item is a list, then get the actual output line
            if type(item) is list:
                item = item[1]
            item.rstrip()  # Get rid of trailing blanks
            if (
                num > 3
                and item[:5] == "</ul>"
                and (
                    primary_items["output_lines"].output_lines[num - 1][:5] == "</ul>"
                    and primary_items["output_lines"].output_lines[num - 2][:5]
                    == "</ul>"
                    and primary_items["output_lines"].output_lines[num + 1][:4]
                    == "<br>"
                )
            ):
                continue

            # Change "Action: nn ..." to Action nn: ..." (i.e. move the colon)
            action_position = item.find("Action: ")
            if action_position != -1:
                action_number_list = item[action_position + 8 :].split(" ")
                action_number = action_number_list[0]
                temp = (
                    item[:action_position]
                    + action_number
                    + ":"
                    + item[action_position + 8 + len(action_number) :]
                )
                output_line = temp
            else:
                output_line = item
            # Get rid of extraneous html code that somehow got in to the output
            output_line = output_line.replace("</span></span>", "</span>")
            output_line = output_line.replace("</p></p>", "</p>")
            # Write the actual final line out as html
            out_file.write(output_line)
            if debug_out:
                logger.debug(f"kaka:{output_line}")
    logger.info("Function Exit: write_out_the_file")
    return


# ###############################################################################################
# Cleanup memory and let user know there was no match found for Task/Profile
# ###############################################################################################
def clean_up_and_exit(
    primary_items: dict,
    name: str,
    profile_or_task_name: str,
) -> None:
    """
    Cleanup memory and let user know there was no match found for Task/Profile/Project
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
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


##############################################################################################################
#                                                                                                            #
#   Main Program Starts Here                                                                                 #
#                                                                                                            #
##############################################################################################################
'''
-The function 'mapit_all' is the main function of the MapTasker program, which maps the Tasker environment and generates an HTML output file.



- The function initializes local variables and other necessary stuff.

- It gets colors to use, runtime arguments, found items, and heading by calling the 'start_up' function from the 'proginit' module.

- It prompts the user to locate the Tasker backup XML file to use to map the Tasker environment.

- It opens and reads the file by calling the 'open_and_get_backup_xml_file' function from the 'proginit' module.

- It gets all the XML data by calling the 'get_the_xml_data' function from the 'taskerd' module.

- It checks for a valid Tasker backup XML file.

- It processes Tasker preferences and displays them if the 'display_preferences' argument is True.

- It processes all projects and their profiles by calling the 'process_projects_and_their_profiles' function from the 'projects' module.

- If a specific project or profile is requested but not found, it exits the program by calling the 'clean_up_and_exit' function.

- It looks for tasks that are not referenced by profiles and displays a total count.

- It lists any projects without tasks and projects without profiles.

- If a specific task is requested but not found, it exits the program by calling the 'clean_up_and_exit' function.

- It outputs caveats if the 'display_detail_level' argument is greater than or equal to 3.

- It adds HTML complete code to the output.

- It generates the actual output file and stores it in the current directory.

- It cleans up memory by calling the 'clean_up_memory' function.

- It displays the final output by opening the output file in the default browser.

- It returns the exit code of the program.
'''


def mapit_all(file_to_get: str) -> int:
    """
    The primary code starts here
        :param file_to_get: file name of input backup.xml file or none
        :return: return code (zero or error code)
    """
    # Initialize local variables and other stuff
    output_lines = LineOut()
    found_tasks, projects_without_profiles, projects_with_no_tasks = (
        [],
        [],
        [],
    )

    # Primary Items
    # Set up an initial empty dictionary of primary items used throughout this project
    #  xml_tree: main xml element of our Tasker xml tree
    #  xml_root: root xml element of our Tasker xml tree
    #  program_arguments: runtime arguments entered by user and parsed
    #  colors_to_use: colors to use in the output
    #  tasker_root_elements: root elements for all Projects/Profiles/Tasks/Scenes
    #  output_lines: class for all lines added to output thus far
    #  found_named_items: names/found-flags for single (if any) Project/Profile/Task
    #  file_to_get: file object/name of Tasker backup file to read and parse
    primary_items = {
        "xml_tree": None,
        "xml_root": None,
        "program_arguments": {},
        "colors_to_use": {},
        "tasker_root_elements": {},
        "output_lines": output_lines,
        "found_named_items": {},
        "file_to_get": file_to_get,
    }

    # Get colors to use, runtime arguments etc...all of our primary items we need throughout
    primary_items = initialize.start_up(primary_items)

    #######################################################################################
    # Process Tasker Preferences
    #######################################################################################
    if primary_items["program_arguments"]["display_preferences"]:
        get_preferences(primary_items)

    # #######################################################################################
    # Go through XML and Process all Projects
    # #######################################################################################
    found_tasks = projects.process_projects_and_their_profiles(
        primary_items,
        found_tasks,
        projects_without_profiles,
    )

    # If we were looking for a specific Project and didn't find it, then quit
    if (
        primary_items["program_arguments"]["single_project_name"]
        and not primary_items["found_named_items"]["single_project_found"]
    ):
        clean_up_and_exit(
            primary_items,
            "Project",
            primary_items["program_arguments"]["single_project_name"],
        )
    # If we were looking for a specific Profile and didn't find it, then quit
    if (
        primary_items["program_arguments"]["single_profile_name"]
        and not primary_items["found_named_items"]["single_profile_found"]
    ):
        clean_up_and_exit(
            primary_items,
            "Profile",
            primary_items["program_arguments"]["single_profile_name"],
        )

    # #######################################################################################
    # Now let's look for Tasks that are not referenced by Profiles and display a total count
    # #######################################################################################
    if (
        not primary_items["program_arguments"]["single_task_name"]
        and not primary_items["program_arguments"]["single_project_name"]
        and not primary_items["program_arguments"]["single_profile_name"]
    ):
        special_tasks.process_tasks_not_called_by_profile(
            primary_items,
            projects_with_no_tasks,
            found_tasks,
        )

        # #######################################################################################
        # List any Projects without Tasks and Projects without Profiles
        # #######################################################################################
        special_tasks.process_missing_tasks_and_profiles(
            primary_items,
            projects_with_no_tasks,
            projects_without_profiles,
        )

    # Requested single item but invalid item name provided (i.e. no specific Project/Profile/Task found)?
    if (
        primary_items["program_arguments"]["single_task_name"]
        and not primary_items["found_named_items"]["single_task_found"]
        and (
            not primary_items["program_arguments"]["single_profile_name"]
            or primary_items["found_named_items"]["single_profile_found"]
        )
        and (
            not primary_items["program_arguments"]["single_project_name"]
            or primary_items["found_named_items"]["single_project_found"]
        )
    ):
        clean_up_and_exit(
            primary_items,
            "Task",
            primary_items["program_arguments"]["single_task_name"],
        )

    # #######################################################################################
    # Let's wrap things up...
    # #######################################################################################
    # Output caveats if we are displaying the Actions
    display_caveats(primary_items)

    # Add html complete code
    final_msg = "\n</body>\n</html>"
    primary_items["output_lines"].add_line_to_output(primary_items, 5, final_msg)

    # Okay, lets generate the actual output file.
    # Store the output in the current directory
    my_output_dir = getcwd()
    logger.debug(f"output directory:{my_output_dir}")
    if my_output_dir is None:
        error_handler("MapTasker cancelled.  An error occurred.  Program cancelled.", 0)
        clean_up_memory(primary_items)
        sys.exit(2)

    my_file_name = "/MapTasker.html"
    # Output the generated html
    write_out_the_file(primary_items, my_output_dir, my_file_name)

    # Clean up memory
    clean_up_memory(primary_items)

    # Display final output
    logger.debug("MapTasker program ended normally")
    try:
        webbrowser.open(f"file://{my_output_dir}{my_file_name}", new=2)
    except webbrowser.Error:
        error_handler(
            "Error: Failed to open output in browser: your browser is not supported.", 1
        )

    print("You can find 'MapTasker.html' in the current folder.  Program end.")

    # If in ReRun mode, let's do it all again :o)
    with contextlib.suppress(KeyError):
        if primary_items["program_arguments"]["rerun"]:
            mapit_all(primary_items["file_to_get"].name)
    return 0
