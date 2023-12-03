#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# taskactn: deal with Task Actions                                                     #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import defusedxml.ElementTree  # Need for type hints

import maptasker.src.tasks as tasks
from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine


# ##################################################################################
# Go through list of actions and output them
# ##################################################################################
def output_list_of_actions(
    action_count: int,
    alist: list,
    the_item: defusedxml.ElementTree.XML,
) -> None:
    """
    Output the list of Task Actions

    Parameters:
        :param action_count: count of Task actions
        :param alist: list of task actions
        :param the_item: the specific Task's detailed line

    Returns: the count of the number of times the program has been called
    """

    # Go through all Actions in Task Action list
    for taction in alist:
        if taction is not None:
            # If Action continued ("...continued"), output it
            if taction[:3] == "...":
                PrimeItems.output_lines.add_line_to_output(
                    2,
                    f"Action: {taction}",
                    ["", "action_color", FormatLine.dont_add_end_span],
                )
            else:
                #  Output the Action count = line number of action (fill to 2 leading zeros)
                PrimeItems.output_lines.add_line_to_output(
                    2,
                    f"Action: {str(action_count).zfill(2)}</span> {taction}",
                    ["", "action_color", FormatLine.dont_add_end_span],
                )
                action_count += 1
            if (
                action_count == 2
                and PrimeItems.program_arguments["display_detail_level"] == 0
                and UNKNOWN_TASK_NAME in the_item
            ):  # Just show first Task if unknown Task
                break
            elif PrimeItems.program_arguments["display_detail_level"] == 1 and UNKNOWN_TASK_NAME not in the_item:
                break

    # Close Action list if doing straight print, no twisties
    if not PrimeItems.program_arguments["twisty"]:
        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
    return


# ##################################################################################
# For this specific Task, get its Actions and output the Task and Actions
# ##################################################################################
def get_task_actions_and_output(
    the_task: defusedxml.ElementTree.XML,
    list_type: str,
    the_item: str,
    tasks_found: list[str],
) -> None:
    # If Unknown task or displaying more detail, then 'the_task' is not valid, and we have to find it.
    if UNKNOWN_TASK_NAME in the_item or PrimeItems.program_arguments["display_detail_level"] > 0:
        # Get the Task ID so that we can get the Task xml element
        # "--Task:" denotes a Task in a Scene
        temp_id = "x" if "&#45;&#45;Task:" in list_type else the_item.split("Task ID: ")

        # Get the Task xml element
        if len(temp_id) > 1:
            temp_id[1] = temp_id[1].split(" ", 1)[0]  # ID = 1st word of temp_id[1]
            the_task, _ = tasks.get_task_name(
                temp_id[1],  # Task ID
                tasks_found,  # Tasks found so far
                [temp_id[1]],  # Task's output line
                "",  # Task type
            )

        # Get Task actions
        if the_task:
            # If we have Task Actions, then output them
            if alist := tasks.get_actions(the_task):
                # Start a list of Actions
                PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)
                action_count = 1
                output_list_of_actions(action_count, alist, the_item)
                # End list if Scene Task
                if "&#45;&#45;Task:" in list_type:
                    PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
                    # Add an extra </ul> if doing twisties
                    if PrimeItems.program_arguments["twisty"]:
                        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
                # End the list of Actions
                PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
        else:
            error_handler("No Task found!!!", 0)

    return
