#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# taskuniq: deal with unique Tasks                                                           #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from typing import List, Union

import maptasker.src.outputl as build_output
import maptasker.src.tasks as tasks
from maptasker.src.frmthtml import format_html
from maptasker.src.sysconst import NO_PROJECT
from maptasker.src.sysconst import UNKNOWN_TASK_NAME


# ###############################################################################################
# Output Projects Without Tasks and Projects Without Profiles
# ###############################################################################################
def process_missing_tasks_and_profiles(
    output_list: List[str],
    projects_with_no_tasks: Union[List[str], List],
    projects_without_profiles: List[str],
    found_items: dict,
    colormap: dict,
    program_args: dict,
) -> None:
    # List Projects with no Tasks
    if len(projects_with_no_tasks) > 0 and not found_items["single_task_found"]:
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            0,
            format_html(
                colormap,
                "trailing_comments_color",
                "",
                "<hr><em>Projects Without Tasks...</em>",
                True,
            ),
        )

        for item in projects_with_no_tasks:
            build_output.my_output(
                colormap,
                program_args,
                output_list,
                4,
                format_html(
                    colormap,
                    "trailing_comments_color",
                    "",
                    f"Project {item} has no <em>Named</em> Tasks",
                    True,
                ),
            )

    # List all Projects without Profiles
    if projects_without_profiles:
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            0,
            format_html(
                colormap,
                "trailing_comments_color",
                "<br>",
                "<em>Projects Without Profiles...</em>",
                True,
            ),
        )
        for item in projects_without_profiles:
            build_output.my_output(
                colormap,
                program_args,
                output_list,
                4,
                format_html(
                    colormap,
                    "trailing_comments_color",
                    "",
                    f">Project {item} has no Profiles",
                    True,
                ),
            )
    return


# #######################################################################################
# Process a single Task that does not belong to any Profile
# #######################################################################################
def process_solo_task_with_no_profile(
    output_list,
    task_id,
    found_tasks,
    program_args,
    found_items,
    unnamed_task_count,
    have_heading: bool,
    projects_with_no_tasks,
    heading,
    colormap,
    all_tasker_items,
):
    the_task_name = ""
    unknown_task, specific_task = False, False

    # Get the Project this Task is under.
    project_name, the_project = tasks.get_project_for_solo_task(
        task_id, projects_with_no_tasks, all_tasker_items["all_projects"]
    )

    # Get the Task's name
    task_element, task_name = tasks.get_task_name(
        task_id, found_tasks, [], "", all_tasker_items["all_tasks"]
    )
    if task_name == UNKNOWN_TASK_NAME:
        task_name = f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;Task ID: {task_id}"
        # Ignore it if it is in a Scene
        if tasks.task_in_scene(task_id, all_tasker_items["all_scenes"]):
            return have_heading, specific_task, unnamed_task_count
        unknown_task = True
    else:
        the_task_name = task_name
    unnamed_task_count += 1

    # At this point, we've found the Project this Task belongs to, or it doesn't belong to any Task
    if not have_heading:
        build_output.my_output(
            colormap, program_args, output_list, 0, "<hr>"
        )  # blank line
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            0,
            format_html(
                colormap,
                "trailing_comments_color",
                "",
                "Tasks that are not called by any Profile...",
                True,
            ),
        )
        build_output.my_output(
            colormap, program_args, output_list, 1, ""
        )  # Start Task list
        have_heading = True

    if not unknown_task and project_name != NO_PROJECT:
        if program_args["debug"]:
            task_name += (
                f" with Task ID: {task_id} ...in Project {project_name} <em>No"
                " Profile</em>"
            )
        else:
            task_name += f" ...in Project {project_name} <em>No Profile</em>"

    # Output the (possible unknown) Task's details
    if (not unknown_task) or (
        program_args["display_detail_level"] == 3
    ):  # Only list named Tasks or if details are wanted
        task_list = [task_name]

        # We have the Tasks.  Now let's output them.
        specific_task = tasks.output_task(
            output_list,
            the_task_name,
            task_element,
            task_list,
            project_name,
            "None",
            [],
            heading,
            colormap,
            program_args,
            all_tasker_items,
            found_items,
            False,
        )
    return have_heading, specific_task, unnamed_task_count


# #######################################################################################
# process_tasks: go through all tasks and output them
# #######################################################################################
def process_tasks_not_called_by_profile(
    output_list: List[str],
    projects_with_no_tasks: List,
    found_tasks_list: List[str],
    program_args: dict,
    found_items: dict,
    heading: str,
    colormap: dict,
    all_tasker_items: dict,
) -> None:
    unnamed_task_count = 0
    task_name = ""
    have_heading = False

    # Go through all Tasks and see if this one is not in it (not found)
    for task_id in all_tasker_items["all_tasks"]:  # Get a/next Task
        if found_items[
            "single_task_found"
        ]:  # If we just processed a single task only, then bail out.
            break

        # if program_args['debug'] and task_id == '98':
        #     logger.debug(f'No Profile =========================={task_id}====================================')

        # We have a solo Task not associated to any Profile
        if task_id not in found_tasks_list:
            have_heading, specific_task, unnamed_task_count = (
                process_solo_task_with_no_profile(
                    output_list,
                    task_id,
                    found_tasks_list,
                    program_args,
                    found_items,
                    unnamed_task_count,
                    have_heading,
                    projects_with_no_tasks,
                    heading,
                    colormap,
                    all_tasker_items,
                )
            )
            if specific_task:
                break

    # Provide total number of unnamed Tasks
    if unnamed_task_count > 0:
        if program_args["display_detail_level"] > 0:
            build_output.my_output(colormap, program_args, output_list, 0, "")  # line
        build_output.my_output(
            colormap, program_args, output_list, 3, ""
        )  # Close Task list
        # If we don't have a single Task only, display total count of unnamed Tasks
        if (
            not found_items["single_task_found"]
            and program_args["display_detail_level"] != 0
        ):
            build_output.my_output(
                colormap,
                program_args,
                output_list,
                0,
                format_html(
                    colormap,
                    "unknown_task_color",
                    "",
                    (
                        f"There are a total of {unnamed_task_count} unnamed Tasks not"
                        " associated with a Profile!"
                    ),
                    True,
                ),
            )

    if task_name is True:
        build_output.my_output(
            colormap, program_args, output_list, 3, ""
        )  # Close Task list

    build_output.my_output(
        colormap, program_args, output_list, 3, ""
    )  # Close out the list
    return
