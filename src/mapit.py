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

import sys
import webbrowser  # To be removed in Python 10.13 (2023?)
import defusedxml.ElementTree  # Need for type hints
from os import getcwd
from typing import List, Dict

import maptasker.src.outputl as build_output
import maptasker.src.proginit as initialize
import maptasker.src.projects as projects
import maptasker.src.taskuniq as special_tasks
from maptasker.src.caveats import display_caveats
from maptasker.src.prefers import get_preferences
from maptasker.src.sysconst import logger


# import os
# print('Path:', os.getcwd())
# print('__file__={0:<35} | __name__={1:<25} | __package__={2:<25}'.format(__file__,__name__,str(__package__)))


# #######################################################################################
# Clean up our memory hogs
# #######################################################################################
def clean_up_memory(
    tree: defusedxml.ElementTree.XML,
    root: defusedxml.ElementTree.XML,
    output_list: List[str],
    all_tasker_items: Dict[str, List[defusedxml.ElementTree.XML]],
) -> None:
    """
    Clean up our memory hogs
        :param tree: xml tree to empty
        :param root: root xml that was parsed from backup file
        :param output_list: list of output lines to clear
        :param all_tasker_items: All Projects/Profiles/Tasks/Scenes
        :return:
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
    write_out_the_file: we have a list of output lines.  Write them out.
        :param output_list: list of all output lines generated
        :param my_output_dir: directory to output to
        :param my_file_name: name of file to use
        :return: nothing
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
            output_line = output_line.replace("</span></span>", "</span>")
            output_line = output_line.replace("</p></p>", "</p>")
            out_file.write(output_line)
    logger.info("Function Exit: write_out_the_file")
    return


# ###############################################################################################
# Cleanup memory and let user know there was no match found for Task/Profile
# ###############################################################################################
def clean_up_and_exit(
    name: str,
    profile_or_task_name: str,
    tree: defusedxml.ElementTree.XML,
    root: defusedxml.ElementTree.XML,
    output_list: list,
    all_tasker_items: dict,
) -> None:
    """
    Cleanup memory and let user know there was no match found for Task/Profile
        :param name: the name to add to the log/print output
        :param profile_or_task_name: name of the Profile or Task to clean
        :param tree: xml tree to clear
        :param root: root of xml parsed from file to clear
        :param output_list: list of output lines to empty
        :param all_tasker_items: all Tasker Projects/Profiles/Tasks/Scenes to clear
        :rtype: colors, runtime arguments,
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


def mapit_all() -> int:
    # Initialize local variables and other stuff
    found_tasks, output_list, projects_without_profiles, projects_with_no_tasks = (
        [],
        [],
        [],
        [],
    )

    # Get colors to use, runtime arguments etc.
    (
        colormap,
        program_args,
        found_items,
        heading,
        output_list,
        tree,
        root,
        filename,
        all_tasker_items,
    ) = initialize.start_up(output_list)

    # Development only parameters here:
    # program_args["display_detail_level"] = 3
    # program_args["display_profile_conditions"] = True
    # program_args['display_preferences'] = True
    # program_args['display_taskernet'] = True

    #######################################################################################
    # Process Tasker Preferences
    #######################################################################################
    if program_args["display_preferences"]:
        get_preferences(
            output_list,
            program_args,
            colormap,
            all_tasker_items,
        )

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
        and not program_args["single_project_name"]
        and not program_args["single_profile_name"]
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
        error_msg = "MapTasker cancelled.  An error occurred.  Program cancelled."
        logger.debug(error_msg)
        print(error_msg)
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
    except webbrowser.Error:
        error_msg = (
            "Error: Failed to open output in browser: your browser is not supported."
        )
        print(error_msg)
        logger.debug(error_msg)
        my_rc = 1
    print("You can find 'MapTasker.html' in the current folder.  Program end.")
    return my_rc
