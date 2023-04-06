#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# project: process the project passed in                                                     #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import xml.etree.ElementTree  # Need for type hints

from maptasker.src.outputl import my_output
from maptasker.src.outputl import refresh_our_output
from maptasker.src.profiles import process_profiles
from maptasker.src.share import share
from maptasker.src.kidapp import get_kid_app
from maptasker.src.priority import get_priority
from maptasker.src.getids import get_ids
from maptasker.src.scenes import process_project_scenes
import maptasker.src.tasks as tasks
from maptasker.src.sysconst import NO_PROFILE
from maptasker.src.sysconst import FONT_TO_USE


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_projects_and_their_profiles(
    output_list: list,
    found_tasks: list,
    projects_without_profiles: list,
    program_args: dict,
    found_items: dict,
    heading: str,
    colormap: dict,
    all_tasker_items: dict,
) -> list:
    """
    Go through all Projects, process them and their Profiles and Tasks (and add to our output list)
        :param output_list: list of output lines generated thus far
        :param found_tasks: list of Tasks found thus far
        :param projects_without_profiles: list of Projects that don't have any Profiles
        :param program_args: runtime arguments
        :param found_items: if searching for a single Project/Profile/Task, name of single item
        :param heading: heading printed
        :param colormap: colors to use in output
        :param all_tasker_items: all Project/Profile/Task/Scene/Preference Tasker xml elements
        :return: list of Tasks found thus far, with duplicates removed
    """
    our_task_element = ""

    process_projects(
        found_items,
        output_list,
        heading,
        projects_without_profiles,
        found_tasks,
        our_task_element,
        colormap,
        program_args,
        all_tasker_items,
    )
    my_output(colormap, program_args, output_list, 3, "")  # Close Project list

    # Return a list of Tasks found thus far with duplicates remove
    # Reference: https://www.pythonmorsels.com/deduplicate-lists/
    return list(dict.fromkeys(found_tasks).keys())


def get_launcher_task(
    project: xml.etree, colormap: dict, project_color_html: str
) -> str:
    """
    If Project has a launcher Task, get it
        :param project: xml element of Project we are processing
        :param colormap: colors to use in output
        :param project_color_html: html to use that defines the color
        :return: information related to launcher Task
    """
    launcher_task_info = ""
    share_element = project.find("Share")
    if share_element is not None:
        launcher_task_element = share_element.find("t")
        if launcher_task_element is not None and launcher_task_element.text is not None:
            launcher_task_info = (
                '</span><span style="color:'
                + colormap["launcher_task_color"]
                + FONT_TO_USE
                + f'>[Launcher Task: {launcher_task_element.text}]</span> '
                + project_color_html
            )
    return launcher_task_info


# #############################################################################################
# Process all Tasks in Project that are not referenced by a Profile
# #############################################################################################
def tasks_not_in_profiles(
    task_ids: list,
    found_tasks: list,
    output_list: list,
    project_name: str,
    colormap: dict,
    program_args: dict,
    heading: str,
    all_tasker_items: dict,
    found_items: dict,
) -> None:
    """
    Process all Tasks in Project that are not referenced by a Profile
        :param task_ids: List of Task IDs
        :param found_tasks: list of Tasks found thus far
        :param output_list: output lines generated thus far onto which we will append more
        :param project_name: name of current Project
        :param colormap: colors to use in output
        :param program_args: runtime arguments
        :param heading: current heading
        :param all_tasker_items: all Projects/Profiles/Tasks/Scenes
        :param found_items: single item name for Project/Profile/Task
        :return: none
    """

    output_the_heading = (
        True  # Flag that we have to first put out the "not found" heading
    )

    # Go through all Tasks for this Project
    for the_id in task_ids:
        # We have a Task in Project that has yet to be output?
        if the_id not in found_tasks and (
            # not found_items["single_project_found"]
            not found_items["single_profile_found"]
            and not found_items["single_task_found"]
        ):
            # We have a Project's Task that has not yet been output
            our_task_element, our_task_name = tasks.get_task_name(
                the_id, found_tasks, [], "", all_tasker_items['all_tasks']
            )
            # We have to remove this Task from found Tasks since it was added by get_task_name
            found_tasks.remove(the_id)

            # Only print the Task header if there are Tasks not found in any Profile, and we are not looking for a single item
            if (
                output_the_heading
                and task_ids
                and not (found_items["single_profile_found"])
                and not (found_items["single_task_found"])
            ):
                my_output(
                    colormap,
                    program_args,
                    output_list,
                    4,
                    (
                        '<br><span'
                        f' style="color:{colormap["task_color"]};font-family:'
                        f'{program_args["font_to_use"]}>&nbsp;&nbsp;&nbsp;The'
                        f' following Tasks in Project {project_name} are not in any'
                        ' Profile...</span><br>'
                    ),
                )
                my_output(colormap, program_args, output_list, 1, "")
                output_the_heading = False

                # Format the output line
            task_list = [
                f"{our_task_name} <em>(Not referenced by any Profile in Project"
                f" {project_name})</em>"
            ]

            # Output the Task (we don't care about the returned value)
            kaka = tasks.output_task(
                output_list,
                our_task_name,
                our_task_element,
                task_list,
                project_name,
                NO_PROFILE,
                found_tasks,
                heading,
                colormap,
                program_args,
                all_tasker_items,
                found_items,
                True,
            )
    # Force a line break
    my_output(colormap, program_args, output_list, 4, "")
    return


# #############################################################################################
# Add extra info to Project output line as appropriate and then output it.
# #############################################################################################
def get_extra_and_output_project(
    program_args: dict,
    colormap: dict,
    project: xml.etree,
    project_name: str,
    found_items: dict,
    heading: str,
    output_list: list,
    launcher_task_info: str,
) -> bool:
    """
    Add extra info to Project output line as appropriate and then output it.
        :param program_args: runtime arguments
        :param colormap: colors to use in putput
        :param project: Project xml element
        :param project_name: name of Project
        :param found_items: single name for Project/Profile/Task if provided
        :param heading: last output heading
        :param output_list: list of output lines generated thus far
        :param launcher_task_info: details about (any) launcher Task
        :return: True if we are looking for a single Project and this isn't it.  False otherwise.
    """
    # See if there is a Kid app and get the Project's priority
    kid_app_info = priority = ''
    if program_args["display_detail_level"] == 3:
        kid_app_info = get_kid_app(project)
        priority = get_priority(project, False)

    # Are we looking for a specific Project?
    if program_args["single_project_name"]:
        if project_name != program_args["single_project_name"]:
            return True
        # We found our single Project
        found_items["single_project_found"] = True
        refresh_our_output(
            False, output_list, project_name, "", heading, colormap, program_args
        )
    else:
        my_output(
            colormap,
            program_args,
            output_list,
            2,
            f"Project: {project_name} {launcher_task_info}{priority}{kid_app_info}",
        )
    return False


# #############################################################################################
# Go through all the Projects, get their detail and output it
# #############################################################################################
def process_projects(
    found_items: dict,
    output_list: list,
    heading: str,
    projects_without_profiles: list,
    found_tasks: list,
    our_task_element: xml.etree,
    colormap: dict,
    program_args: dict,
    all_tasker_items: dict,
) -> list:
    """
    Go through all the Projects, get their detail and output it
        :param found_items: all items found so far
        :param output_list: list of output lines generated so far
        :param heading: the output heading
        :param projects_without_profiles: list of Projects with no Profiles
        :param found_tasks: list of Tasks found
        :param our_task_element: xml element of our Task
        :param colormap: output colors to use
        :param program_args: runtime arguments
        :param all_tasker_items: all Projects/Profiles/Tasks/Scenes
        :return: list of found Tasks
    """
    # Set up html to use
    project_color_html = (
        '<span style="color:'
        + colormap["project_color"]
        + program_args["font_to_use"]
        + ">"
    )

    for project in all_tasker_items["all_projects"]:
        # Don't bother with another Project if we've done a single Task or Profile only
        if found_items["single_task_found"] or found_items["single_profile_found"]:
            break
        project_name = project.find("name").text

        # See if there is a Launcher task
        launcher_task_info = get_launcher_task(project, colormap, project_color_html)

        # Get some extra details and output the Project information
        if get_extra_and_output_project(
            program_args,
            colormap,
            project,
            project_name,
            found_items,
            heading,
            output_list,
            launcher_task_info,
        ):
            continue

        # Process any <Share> information from TaskerNet
        if program_args["display_taskernet"]:
            share(project, colormap, program_args, output_list)

        if profile_ids := get_ids(
            True,
            program_args,
            colormap,
            output_list,
            project,
            project_name,
            projects_without_profiles,
        ):
            our_task_element = process_profiles(
                output_list,
                project,
                project_name,
                profile_ids,
                found_tasks,
                program_args,
                heading,
                colormap,
                all_tasker_items,
                found_items,
            )

            # Go to next Project if we are looking for a specific Profile and didn't find it.
            if (
                program_args["single_profile_name"]
                and not found_items["single_profile_found"]
            ):
                continue  # On to next Project
        else:
            my_output(
                colormap,
                program_args,
                output_list,
                2,
                (
                    '</span><span style="color:'
                    + colormap["profile_color"]
                    + FONT_TO_USE
                    + '><em>Project has no Profiles</em></span>'
                ),
            )
        my_output(colormap, program_args, output_list, 3, "")  # Close Profile list

        # # See if there are Tasks in Project that have no Profile
        if task_ids := get_ids(False, {}, {}, [], project, project_name, []):
            # Process Tasks in Project that are not referenced by a Profile
            tasks_not_in_profiles(
                task_ids,
                found_tasks,
                output_list,
                project_name,
                colormap,
                program_args,
                heading,
                all_tasker_items,
                found_items,
            )

        # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
        if not program_args["single_task_name"]:
            process_project_scenes(
                project,
                colormap,
                program_args,
                output_list,
                our_task_element,
                found_tasks,
                all_tasker_items,
            )

        my_output(colormap, program_args, output_list, 3, "")  # Close Profile list
        if (
            found_items["single_project_found"]
            or found_items["single_profile_found"]
            or found_items["single_task_found"]
        ):
            my_output(colormap, program_args, output_list, 3, "")  # Close Project list
            return found_tasks

    # If we didn't find the single Project, then say so.
    return []
