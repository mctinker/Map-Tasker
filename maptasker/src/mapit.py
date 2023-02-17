#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# MapTasker: Main Program                                                                    #
#            Read the Tasker backup file to build a visual map of its configuration:         #
#            Projects, Profiles, Tasks, Scenes                                               #
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

import atexit
import sys
import webbrowser  # To be removed in Python 10.13 (2023?)
import xml.etree.ElementTree  # Need for type hints
from json import dumps, loads  # For write and read counter
from os import getcwd
from pathlib import Path
from tkinter import messagebox
from typing import List, Dict

import maptasker.src.outputl as build_output
import maptasker.src.proginit as initialize
import maptasker.src.projects as projects
import maptasker.src.taskuniq as special_tasks
from maptasker.src.caveats import display_caveats
from maptasker.src.sysconst import COUNTER_FILE
from maptasker.src.sysconst import logger
from maptasker.src.taskerd import get_the_xml_data


# import os
# print('Path:', os.getcwd())
# print('__file__={0:<35} | __name__={1:<25} | __package__={2:<25}'.format(__file__,__name__,str(__package__)))


# #############################################################################################
# Use a counter to determine if this is the first time run.
#  If first time only, then provide a user prompt to locate the backup file
# #############################################################################################
def read_counter():
    """Read the program counter

    Parameters: none

    Returns: the count of the number of times the program has been called

    """
    return (
        loads(open(COUNTER_FILE, "r").read()) + 1
        if Path.exists(Path(COUNTER_FILE).resolve())
        else 0
    )


def write_counter():
    """Write the program counter

    Parameters: none

    Returns: none

    """
    with open(COUNTER_FILE, "w") as f:
        f.write(dumps(run_counter))
    return


run_counter = read_counter()
atexit.register(write_counter)


# #######################################################################################
# Clean up our memory hogs
# #######################################################################################
def clean_up_memory(
    tree: xml.etree.ElementTree.ElementTree,
    root: xml.etree.ElementTree.Element,
    output_list: List[str],
    all_tasker_items: Dict[str, List[xml.etree.ElementTree.Element]],
) -> None:
    """
    Free up memory
    :rtype: None
    """
    for elem in tree.iter():
        elem.clear()
    all_tasker_items["all_projects"].clear()
    all_tasker_items["all_profiles"].clear()
    all_tasker_items["all_tasks"].clear()
    all_tasker_items["all_scenes"].clear()
    root.clear()
    output_list.clear()
    return


# #######################################################################################
# write_out_the_file: we have a list of output lines.  Write them out.
# #######################################################################################
def write_out_the_file(
    output_list: List[str], my_output_dir: str, my_file_name: str
) -> None:
    """
    Write out the final html
    :rtype: None
    """
    logger.info(f"Function Entry: write_out_the_file dir:{my_output_dir}")
    with open(my_output_dir + my_file_name, "w") as out_file:
        for item in output_list:
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
            out_file.write(output_line)
    logger.info("Function Exit: write_out_the_file")
    return


# ###############################################################################################
# Cleanup memory and let user know there was no match found for Task/Profile
# ###############################################################################################
def clean_up_and_exit(
    name: str,
    profile_or_task_name: str,
    tree: xml.etree,
    root: xml.etree,
    output_list: list,
    all_tasker_items: dict,
) -> None:
    """
    clear memory and exit due to error
    :rtype: exit 5
    """
    output_list.clear()
    error_message = f"{name} {profile_or_task_name} not found!!"
    print(error_message)
    logger.debug(error_message)
    clean_up_memory(tree, root, output_list, all_tasker_items)
    sys.exit(5)


##############################################################################################################
#                                                                                                            #
#   Main Program Starts Here                                                                                 #
#                                                                                                            #
##############################################################################################################
def mapitall():
    """
    maptaskerodl program
    :rtype: none
    """
    # Initialize local variables and other stuff
    found_tasks, output_list, projects_without_profiles, projects_with_no_tasks = (
        [],
        [],
        [],
        [],
    )
    colormap, program_args, found_items, heading = initialize.start_up()

    # Development only parameters here:
    # program_args["debug"] = True
    # program_args["display_detail_level"] = 3
    # program_args["display_profile_conditions"] = True
    # program_args['display_taskernet'] = False
    # program_args['single_task_name'] = 'Check Upstairs Heat'

    # Prompt user for Tasker's backup.xml file location
    if run_counter < 1:  # Only display message box on first run
        msg = "Locate the Tasker backup xml file to use to map your Tasker environment"
        title = "MapTasker"
        messagebox.showinfo(title, msg)

    # Open and read the file...
    filename = initialize.open_and_get_backup_xml_file(program_args)

    # Go get all the xml data
    tree, root, all_tasker_items = get_the_xml_data(filename)

    # Check for valid Tasker backup.xml file
    if root.tag != "TaskerData":
        error_msg = "You did not select a Tasker backup XML file...exit 2"
        build_output.my_output(colormap, program_args, output_list, 0, error_msg)
        logger.debug(f"{error_msg}exit 3")
        sys.exit(3)
    else:
        heading = f"{heading}    Tasker version: " + root.attrib["tv"]

    # Start the output with heading
    build_output.my_output(colormap, program_args, output_list, 0, heading)
    build_output.my_output(
        colormap, program_args, output_list, 1, ""
    )  # Start Project list

    # #######################################################################################
    # Go through XML and Process all Projects
    # #######################################################################################
    found_tasks = projects.process_projects_and_their_profiles(
        output_list,
        found_tasks,
        projects_without_profiles,
        program_args,
        found_items,
        heading,
        colormap,
        all_tasker_items,
    )

    # If we were looking for a specific Project and didn't find it, then quit
    if program_args["single_project_name"] and not found_items["single_project_found"]:
        clean_up_and_exit(
            "Project",
            program_args["single_project_name"],
            tree,
            root,
            output_list,
            all_tasker_items,
        )
    # If we were looking for a specific Profile and didn't find it, then quit
    if program_args["single_profile_name"] and not found_items["single_profile_found"]:
        clean_up_and_exit(
            "Profile",
            program_args["single_profile_name"],
            tree,
            root,
            output_list,
            all_tasker_items,
        )

    # #######################################################################################
    # Now let's look for Tasks that are not referenced by Profiles and display a total count
    # #######################################################################################
    if (
        not program_args["single_task_name"]
        and not program_args["single_profile_name"]
        and not program_args["single_project_name"]
    ):
        special_tasks.process_tasks_not_called_by_profile(
            output_list,
            projects_with_no_tasks,
            found_tasks,
            program_args,
            found_items,
            heading,
            colormap,
            all_tasker_items,
        )

        # #######################################################################################
        # List any Projects without Tasks and Projects without Profiles
        # #######################################################################################
        special_tasks.process_missing_tasks_and_profiles(
            output_list,
            projects_with_no_tasks,
            projects_without_profiles,
            found_items,
            colormap,
            program_args,
        )

    # Requested single Task but invalid Task name provided (i.e. no specific Project/Profile/Task found)?
    if (
        program_args["single_task_name"]
        and not found_items["single_task_found"]
        and (
            not program_args["single_profile_name"]
            or found_items["single_profile_found"]
        )
        and (
            not program_args["single_project_name"]
            or found_items["single_project_found"]
        )
    ):
        clean_up_and_exit(
            "Task",
            program_args["single_task_name"],
            tree,
            root,
            output_list,
            all_tasker_items,
        )

    # #######################################################################################
    # Let's wrap things up...
    # #######################################################################################
    # Output caveats if we are displaying the Actions
    display_caveats(output_list, program_args, colormap)

    # Add html complete code
    error_msg = "</body>\n</html>"
    build_output.my_output(colormap, program_args, output_list, 0, error_msg)

    # Okay, lets generate the actual output file.
    # Store the output in the current  directory
    my_output_dir = getcwd()
    logger.debug(f"output directory:{my_output_dir}")
    if my_output_dir is None:
        print("MapTasker cancelled.  An error occurred.  Program cancelled.")
        clean_up_memory(tree, root, output_list, all_tasker_items)
        sys.exit(2)

    my_file_name = "/MapTasker.html"
    # Output the generated html
    write_out_the_file(output_list, my_output_dir, my_file_name)

    # Clean up memory
    clean_up_memory(tree, root, output_list, all_tasker_items)

    # Display final output
    logger.debug("MapTasker program ended normally")
    my_rc = 0
    try:
        webbrowser.open(f"file://{my_output_dir}{my_file_name}", new=2)
    except Exception.webrowser.e:
        error_msg = "Failed to open output in browser: your browser is not supported."
        print(error_msg)
        logger.debug(error_msg)
        my_rc = 1
    print("You can find 'MapTasker.html' in the current folder.  Program end.")
    exit(my_rc)


# Main call
# if __name__ == "__main__":
#     maptaskerodl()
