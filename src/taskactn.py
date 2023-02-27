#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# taskactn: deal with Task Actions                                                           #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import xml.etree.ElementTree  # Need for type hints

import maptasker.src.tasks as tasks
from maptasker.src.outputl import my_output
from maptasker.src.sysconst import *


# #######################################################################################
# For this specific Task, get its Actions and output the Task and Actions
# #######################################################################################
def get_task_actions_and_output(
    the_task: xml.etree,
    output_list: list[str],
    program_args: dict,
    list_type: str,
    the_item: str,
    tasks_found: list[str],
    colormap: dict,
    all_tasks: dict,
) -> None:

    # If Unknown task, then 'the_task' is not valid, and we have to find it.
    if UNKNOWN_TASK_NAME in the_item or program_args["display_detail_level"] > 0:
        # Get the Task ID so that we can get the Task xml element
        if "⎯Task:" in list_type:
            temp_id = 'x'
        else:
            temp_id = the_item.split("Task ID: ")
        # Get the Task xml element
        if len(temp_id) > 1:
            temp_id[1] = temp_id[1].split(' ', 1)[0]  # ID = 1st word of temp_id[1]
            the_task, kaka = tasks.get_task_name(
                temp_id[1], tasks_found, [temp_id[1]], "", all_tasks
            )
        # Get Task actions
        if the_task:
            if alist := tasks.get_actions(the_task, colormap, program_args):
                my_output(colormap, program_args, output_list, 1, "")  # Start Action list
                action_count = 1
                output_list_of_actions(
                    colormap, program_args, output_list, action_count, alist, the_item
            )
        else:
            error_msg = 'Error: No Task found!!!'
            logger.debug(error_msg)
            print(error_msg)
    return


# #######################################################################################
# Go through list of actions and output them
# #######################################################################################
def output_list_of_actions(
    colormap: dict,
    program_args: dict,
    output_list: list,
    action_count: int,
    alist: list,
    the_item: xml.etree.ElementTree,
) -> None:
    """output the list of Task Actions

    Parameters:
        :param colormap: dictionary of colors to use
        :param program_args: dictionary of program runtime arguments
        :param output_list: list into which to add the output lines
        :param action_count: count of Task actions
        :param alist: list of task actions
        :param the_item: the specific Task's detailed line

    Returns: the count of the number of times the program has been called

    """
    for taction in alist:
        if taction is not None:
            if "Label for" in taction:
                my_output(colormap, program_args, output_list, 2, taction)
            elif taction[:3] == "...":
                my_output(colormap, program_args, output_list, 2, f"Action: {taction}")
            else:
                my_output(
                    colormap,
                    program_args,
                    output_list,
                    2,
                    f"Action: {str(action_count).zfill(2)} {taction}",
                )
                action_count += 1
            if (
                action_count == 2
                and program_args["display_detail_level"] == 0
                and UNKNOWN_TASK_NAME in the_item
            ):  # Just show first Task if unknown Task
                break
            elif (
                program_args["display_detail_level"] == 1
                and UNKNOWN_TASK_NAME not in the_item
            ):
                break
    my_output(colormap, program_args, output_list, 3, "")  # Close Action list
    return
