#! /usr/bin/env python3

#                                                                                      #
# taskactn: deal with Task Actions                                                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

from typing import TYPE_CHECKING

import maptasker.src.tasks as tasks
from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine

if TYPE_CHECKING:
    import defusedxml.ElementTree


# Go through list of actions and output them
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
                # First remove one blank if line number is > 99 and < 1000
                temp_action = taction.replace("&nbsp;", "", 1) if action_count > 99 and action_count < 1000 else taction
                #  Output the Action count = line number of action (fill to 2 leading zeros)
                PrimeItems.output_lines.add_line_to_output(
                    2,
                    f"Action: {str(action_count).zfill(2)}</span> {temp_action}",
                    ["", "action_color", FormatLine.dont_add_end_span],
                )
                action_count += 1
            if (
                action_count == 2
                and PrimeItems.program_arguments["display_detail_level"] == 0
                and UNKNOWN_TASK_NAME in the_item
            ):  # Just show first Task if unknown Task
                break
            if PrimeItems.program_arguments["display_detail_level"] == 1 and UNKNOWN_TASK_NAME not in the_item:
                break

    # Close Action list if doing straight print, no twisties
    if not PrimeItems.program_arguments["twisty"]:
        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# For this specific Task, get its Actions and output the Task and Actions
def get_task_actions_and_output(
    the_task: defusedxml.ElementTree.XML,
    list_type: str,
    the_item: str,
    tasks_found: list[str],
) -> None:
    # If Unknown task or displaying more detail, then 'the_task' is not valid, and we have to find it.
    """
    Get task actions and output.
    Args:
        the_task: {Task xml element}: Task xml element
        list_type: {str}: Type of list
        the_item: {str}: Item being displayed
        tasks_found: {list[str]}: Tasks found so far
    Returns:
        None: No return value
    {Processing Logic}:
    1. Check if task is unknown or detail level is high, find task ID
    2. Get task xml element from ID
    3. Get task actions from xml element
    4. Output actions list with formatting
    5. Handle errors if no task found
    """
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
        if the_task is not None:
            # If we have Task Actions, then output them.  The action list is a list of the Action output lines already
            # formatted.
            if alist := tasks.get_actions(the_task):
                # Start a list of Actions
                PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)
                action_count = 1
                output_list_of_actions(action_count, alist, the_item)
                # End list if Scene Task
                if "&#45;&#45;Task:" in list_type:
                    PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
                    if PrimeItems.program_arguments["twisty"]:
                        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
                # End the list of Actions
                PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)
        else:
            error_handler("No Task found!!!", 0)
