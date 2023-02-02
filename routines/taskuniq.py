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
import routines.tasks as tasks
from config import *  # Configuration info

import routines.outputl as build_output
from routines.sysconst import FONT_TO_USE


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
            f'<hr><font color={trailing_comments_color}"{FONT_TO_USE}<em>Projects Without Tasks...</em>',
        )
        for item in projects_with_no_tasks:
            build_output.my_output(
                colormap, program_args, output_list, 4, f"Project {item} has no Tasks"
            )

    # List all Projects without Profiles
    if projects_without_profiles:
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            0,
            f'<hr><font color={trailing_comments_color}"{FONT_TO_USE}<em>Projects Without Profiles...</em>',
        )
        for item in projects_without_profiles:
            build_output.my_output(
                colormap,
                program_args,
                output_list,
                4,
                f"Project {item} has no Profiles",
            )
    return


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

    # See if we didn't find our task
    for task_id in all_tasker_items["all_tasks"]:  # Get a/next Task
        if found_items[
            "single_task_found"
        ]:  # If we just processed a single task only, then bail out.
            break

        # if program_args['debug'] and task_id == '98':
        #     logger.debug(f'No Profile =========================={task_id}====================================')

        if (
            task_id not in found_tasks_list
        ):  # We have a solo Task not associated to any Profile
            have_heading, specific_task = tasks.process_solo_task_with_no_profile(
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
                f"<font color={unknown_task_color}>There are a total of "
                f"{unnamed_task_count} unnamed Tasks not associated with a Profile!",
            )

    if task_name is True:
        build_output.my_output(
            colormap, program_args, output_list, 3, ""
        )  # Close Task list

    build_output.my_output(
        colormap, program_args, output_list, 3, ""
    )  # Close out the list
    return
