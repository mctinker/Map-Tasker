#! /usr/bin/env python3
"""
taskactn: deal with Task Actions

MIT License   Refer to https://opensource.org/license/mit
"""

#                                                                                      #
# taskactn: deal with Task Actions                                                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

from typing import TYPE_CHECKING

import maptasker.src.tasks as tasks  # noqa: PLR0402
from maptasker.src.error import error_handler
from maptasker.src.guiutils import get_taskid_from_unnamed_task
from maptasker.src.maputils import (
    count_consecutive_substr,
    count_unique_substring,
    get_value_if_match,
)
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import UNNAMED_ITEM, FormatLine

if TYPE_CHECKING:
    import defusedxml.ElementTree
UNNAMED = " (Unnamed)"


def ensure_argument_alignment(taction: str) -> str:
    """
    Ensure that the arguments of the action are aligned correctly.
    Args:
        taction: {str}: Action text
    Returns:
        str: Correctly aligned action text
    """
    action_breakdown = taction.replace("\n", "<br>").split("<br>")
    if len(action_breakdown) > 1:
        count_of_spaces = count_consecutive_substr(action_breakdown[1], "&nbsp;")
        correct_spacing = "&nbsp;" * count_of_spaces
        for index, arg in enumerate(action_breakdown[2:]):
            # action_breakdown[index + 2] = remove_html_tags(arg.strip(), "")
            action_breakdown[index + 2] = arg.strip()
            if count_consecutive_substr(arg, "&nbsp;") != count_of_spaces:
                action_breakdown[index + 2] = action_breakdown[index + 2].replace(
                    "&nbsp;",
                    "",
                )
                # Handle {DISABLED] task indicator at end of config parameters.
                if action_breakdown[index + 2] == "[&#9940;DISABLED]</span>":
                    correct_spacing = "&nbsp;" * (count_of_spaces - 18)

                # Now add the correct number of spaces to the start of the line
                action_breakdown[index + 2] = f"{correct_spacing}{action_breakdown[index + 2]}"
        # Put it all back together.
        taction = "<br>".join(action_breakdown)
    return taction


# Go through list of actions and output them
def output_list_of_actions(
    action_count: int,
    alist: list,
    the_item: defusedxml.ElementTree,
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
        # 'taction' has the Action text, including all of it's arguments.
        if taction is not None:
            # Optimize spacing if 'pretty' is enabled
            if PrimeItems.program_arguments.get("pretty"):
                updated_action = ensure_argument_alignment(taction)
            else:
                updated_action = taction

            # If Action continued ("...continued"), output it
            if updated_action[:3] == "...":
                PrimeItems.output_lines.add_line_to_output(
                    2,
                    f"Action: {updated_action}",
                    ["", "action_color", FormatLine.dont_add_end_span],
                )
            else:
                # First remove one blank from action number if line number is > 99 and < 1000
                updated_action = (
                    updated_action.replace("&nbsp;", "", 1)
                    if action_count > 99 and action_count < 1000
                    else updated_action
                )

                #  Output the Action count = line number of action (fill to 2 leading zeros)
                PrimeItems.output_lines.add_line_to_output(
                    2,
                    f"Action: {str(action_count).zfill(2)}</span> {updated_action}",
                    ["", "action_color", FormatLine.dont_add_end_span],
                )
                action_count += 1
            if (
                action_count == 2 and PrimeItems.program_arguments["display_detail_level"] == 0 and UNNAMED in the_item
            ):  # Just show first Task if unknown Task
                break
            if PrimeItems.program_arguments["display_detail_level"] == 1 and UNNAMED not in the_item:
                break

    # Close Action list if doing straight print, no twisties
    if not PrimeItems.program_arguments["twisty"]:
        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# For this specific Task, get its Actions and output the Task and Actions
def get_task_actions_and_output(
    the_task: defusedxml.ElementTree,
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
    # If the Task is unnamed or we are doing more detail, find the Task.
    if UNNAMED in the_item or PrimeItems.program_arguments["display_detail_level"] > 0:
        # Get the Task name so that we can get the Task xml element
        # "--Task:" denotes a Task in a Scene which we will handle below
        if UNNAMED in the_item:
            index = the_item.find(UNNAMED)
            task_name = the_item[: index + len(UNNAMED)]
        else:
            temp_id = "x" if "&#45;&#45;Task:" in list_type else the_item.split("Task ID: ")
            task_name = temp_id[0].split("&nbsp;")[0]
        # Find the Task
        the_task, task_id = get_value_if_match(
            PrimeItems.tasker_root_elements["all_tasks"],
            "name",
            task_name,
            "xml",
        )

        # Get the Task name from the ID if it wasn't found above.
        if the_task is None and task_name == "x":
            the_task = PrimeItems.tasker_root_elements["all_tasks"][the_item]["xml"]
            if the_task is None and UNNAMED_ITEM in the_item:
                task_id = get_taskid_from_unnamed_task(the_item)
                the_task = PrimeItems.tasker_root_elements["all_tasks"][task_id]["xml"]
            task_name = PrimeItems.tasker_root_elements["all_tasks"][the_item]["name"]
            task_id = the_item

        # It is a valid Task.  If unknown and it is an Entry or Exit (valid) task, add it to the count of unnamed Tasks.
        elif UNNAMED in the_item and ("Entry Task" in the_item or "Exit" in the_item):
            PrimeItems.task_count_unnamed += 1

        # Keep tabs on the tasks processed so far.
        if task_id not in tasks_found:
            tasks_found.append(task_id)

        # Get Task actions
        if the_task is not None:
            # If we have Task Actions, then output them.  The action list is a list of the Action output lines already
            # formatted.
            if alist := tasks.get_actions(the_task):
                # Track the task and action count if too many actions.
                action_count = len(alist) - count_unique_substring(
                    alist,
                    "...indent=",
                )
                # Add the Task to our warning limit dictionary.
                if (
                    PrimeItems.program_arguments["task_action_warning_limit"] < 100
                    and action_count > PrimeItems.program_arguments["task_action_warning_limit"]
                    and task_name not in PrimeItems.task_action_warnings
                ):
                    PrimeItems.task_action_warnings[task_name] = {
                        "count": action_count,
                        "id": task_id,
                    }

                # Start a list of Actions
                PrimeItems.output_lines.add_line_to_output(
                    1,
                    "",
                    FormatLine.dont_format_line,
                )
                action_count = 1
                output_list_of_actions(action_count, alist, the_item)
                # End list if Scene Task
                if "&#45;&#45;Task:" in list_type:
                    PrimeItems.output_lines.add_line_to_output(
                        3,
                        "",
                        FormatLine.dont_format_line,
                    )
                    if PrimeItems.program_arguments["twisty"]:
                        PrimeItems.output_lines.add_line_to_output(
                            3,
                            "",
                            FormatLine.dont_format_line,
                        )
                # End the list of Actions
                PrimeItems.output_lines.add_line_to_output(
                    3,
                    "",
                    FormatLine.dont_format_line,
                )
        else:
            error_handler("No Task found!!!", 0)
