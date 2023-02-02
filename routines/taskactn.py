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

import routines.tasks as tasks
from routines.outputl import my_output
from routines.sysconst import *


# #######################################################################################
# For this specific Task, get its Actions and output the Task and Actions
# #######################################################################################
def get_task_actions_and_output(
    the_task: xml.etree.ElementTree,
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
        temp = ["x", the_item] if "⎯Task:" in list_type else the_item.split("ID: ")
        if len(temp) > 1:
            the_task, kaka = tasks.get_task_name(
                temp[1], tasks_found, [temp[1]], "", all_tasks
            )
        if alist := tasks.get_actions(the_task, colormap, program_args):
            my_output(colormap, program_args, output_list, 1, "")  # Start Action list
            action_count = 1
            output_list_of_actions(
                colormap, program_args, output_list, action_count, alist, the_item
            )
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
