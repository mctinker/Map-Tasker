#! /usr/bin/env python3
"""Process Tasks"""

#                                                                                      #
# tasks: Process Tasks                                                                 #
#                                                                                      #
from __future__ import annotations

import re

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actione as action_evaluate
from maptasker.src import console
from maptasker.src.error import error_handler, rutroh_error
from maptasker.src.getids import get_ids
from maptasker.src.primitem import PrimeItems
from maptasker.src.shelsort import shell_sort
from maptasker.src.sysconst import (
    UNNAMED_ITEM,
    pattern14,
)

blank = "&nbsp;"


def replace_except_last(the_text: str, target: str, replacement: str) -> str:
    """
    Replace all occurrences of a target string with a replacement string in the given text,
    except for the last occurrence of the target string.

    Args:
        the_text (str): The text in which to perform the replacements.
        target (str): The string to be replaced.
        replacement (str): The string to replace the target with.

    Returns:
        str: The modified text with all but the last occurrence of the target string replaced.
    """
    parts = the_text.rsplit(target, 1)  # Split into two parts from the last occurrence
    return parts[0].replace(target, replacement) + target.join(parts[1:])


def reformat_html(html_string: str) -> str:
    """
    Reformat the given HTML string by modifying the configuration parameters section.

    This function performs the following transformations:
    1. Matches the configuration parameters section and splits the parameters onto new lines.
    2. Adds a specified number of blank spaces before each new line, except the last one.
    3. Replaces commas with new lines followed by a specified number of blank spaces.

    Args:
        html_string (str): The input HTML string to be reformatted.

    Returns:
        str: The reformatted HTML string.
    """

    def replacer(match: re.Match) -> str:
        params = match.group(2).strip().replace(";", "\n")  # Split parameters onto new lines
        return f"{match.group(1)}\n{params}\n<"  # Reinsert the opening '<' tag

    # pattern14 has definition for everything after 'Configuration Parameter(s):'
    reformatted_html = re.sub(pattern14, replacer, html_string, flags=re.DOTALL)
    number_of_blanks = ((reformatted_html.find(":")) // 2) - 20
    if number_of_blanks < 0:
        number_of_blanks = 37
    reformatted_html = replace_except_last(
        reformatted_html,
        "\n",
        f"\n{blank * number_of_blanks}",
    )
    return reformatted_html.replace(",", f"\n{blank * number_of_blanks}")


# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
# Optimized
def get_actions(current_task: defusedxml.ElementTree) -> list:
    """
    Optimized extraction of actions from a task XML element.
    """
    tasklist = []
    indent_size = PrimeItems.program_arguments["indent"]
    blanks = f"{'&nbsp;' * indent_size}"

    try:
        task_actions = current_task.findall("Action")
    except defusedxml.DefusedXmlException:
        console.debug(f"tasks.py current Task: {current_task}")
        error_handler("Error: No action found!!!", 0)
        return []

    if not task_actions:
        return []

    shell_sort(task_actions, True, False)

    indentation = 0
    indentation_amount = ""
    pretty_mode = PrimeItems.program_arguments.get("pretty")
    _get_action_code = action_evaluate.get_action_code
    _reformat_html = reformat_html
    _build_action = action_evaluate.build_action
    for action in task_actions:
        child = action.find("code")
        task_code = _get_action_code(child, action, True, "t")

        if any(token in task_code for token in [">End If", ">Else", ">End For"]):
            indentation = max(indentation - 1, 0)
            indentation_amount = indentation_amount[: -(indent_size * 6)]

        # If pretty text, then reformat it.
        if "Configuration Parameter(s):" in task_code and pretty_mode:
            task_code = _reformat_html(task_code)
        _build_action(
            tasklist,
            task_code,
            child,
            indentation,
            indentation_amount,
        )

        if any(token in task_code for token in [">If", ">Else", ">For<"]):
            indentation += 1
            indentation_amount += blanks

    return tasklist


## Determine if the Task is an Entry or Exit Task.
# Optimized
line_left_arrow = "&#11013;"
line_right_arrow = "&#11157;"


def entry_or_exit_task(
    task_output_lines: list,
    task_name: str,
    task_type: str,
    extra: str,
    duplicate_task: bool,
    the_task_id: str,
) -> tuple[list, str]:
    """
    Determine if this is an "Entry" or "Exit" Task and add the appropriate text to the
    Task's output lines.
        Args:
            task_output_lines (list): List of output lines for this Task
            task_name (str): Name of this Task.
            task_type (str): Type of this Task: Entry or Exit
            extra (str): Extra text to add to the end of the Task's output line
            duplicate_task (bool): Is this a duplicate Task? True if it is.
            the_task_id (str): The Task's ID

        Returns:
            tuple: task_output_lines and task_name
    """
    display_level = PrimeItems.program_arguments["display_detail_level"]
    indent = blank * PrimeItems.program_arguments["indent"]

    def append_task_line(name: str, task_type: str) -> None:
        # Suffix is snot getting carried through to output
        arrow = line_left_arrow if task_type == "Entry" else line_right_arrow
        suffix = f"{indent}{arrow} {task_type} Task{extra}" if display_level > 0 else indent
        task_output_lines.append(f"{name}{suffix}")

    if task_name:
        append_task_line(task_name, task_type)
    else:
        task_name = f"{UNNAMED_ITEM}{the_task_id}"
        PrimeItems.tasker_root_elements["all_tasks"][the_task_id]["name"] = task_name

        if not duplicate_task and task_type in {"Entry", "Exit"}:
            PrimeItems.task_count_unnamed += 1

        append_task_line(task_name, task_type)

    return task_output_lines, task_name


# Get the name of the task given the Task ID
# return the Task's element and the Task's name
# Optimized
def get_task_name(
    the_task_id: str,
    tasks_that_have_been_found: list,
    task_output_lines: list,
    task_type: str,
) -> tuple:
    """
    Get the name of the task given the Task ID.
    Add to the output line if this is an Entry or xit Task.

        :param the_task_id: the Task's ID (e.g. '47')
        :param tasks_that_have_been_found: list of Tasks found so far
        :param task_output_lines: list of Tasks
        :param task_type: Type of Task (Entry, Exit, Scene)
        :return: Task's xml element, Task's name
    """
    # Get the Task info.
    task_info = PrimeItems.tasker_root_elements["all_tasks"].get(the_task_id)
    if not task_info:
        return None, ""
    task, task_name = task_info["xml"], task_info["name"]

    # Determine if this is a duplicate Task.   If not, add it to our list of found Tasks.
    duplicate_task = the_task_id in tasks_that_have_been_found
    if not duplicate_task:
        tasks_that_have_been_found.append(the_task_id)

    # Determine if this is an "Entry" or "Exit" Task
    extra = f"&nbsp;&nbsp;Task ID: {the_task_id}" if PrimeItems.program_arguments["debug"] else ""
    task_output_lines, task_name = entry_or_exit_task(
        task_output_lines,
        task_name,
        task_type,
        extra,
        duplicate_task,
        the_task_id,
    )

    return task, task_name


# Find the Project belonging to the Task id passed in
def get_project_for_solo_task(
    the_task_id: str,
    projects_with_no_tasks: list,
) -> tuple[str, defusedxml.Element]:
    """
    Find the Project belonging to the Task id passed in
    :param the_task_id: the ID of the Task
    :param projects_with_no_tasks: list of Projects that do not have any Tasks
    :return: name of the Project that belongs to this task and the Project xml element
    """
    NO_PROJECT = "No Project"  # noqa: N806
    project_name = NO_PROJECT
    project_element = None

    all_projects = PrimeItems.tasker_root_elements["all_projects"]
    if all_projects is not None:
        for project in all_projects:
            project_element = PrimeItems.tasker_root_elements["all_projects"][project]["xml"]
            project_name = PrimeItems.tasker_root_elements["all_projects"][project]["name"]
            task_ids = get_ids(
                False,
                project_element,
                project_name,
                projects_with_no_tasks,
            )
            if the_task_id in task_ids:
                return project_name, project_element

    return project_name, project_element


def get_taskid_from_unnamed_task(unnamed_task: str) -> str:
    """
    Extracts the task ID from an unnamed task string.

    Args:
        unnamed_task (str): The unnamed task string.

    Returns:
        str: The extracted task ID.
    """
    # Extract the task ID from the unnamed task string
    position = unnamed_task.rfind(".")
    if position != -1:
        return unnamed_task[position + 1 :].split(" (Unnamed)", maxsplit=1)[0]

    rutroh_error(f"Error.  Missing period for task ID in Taask name: '{unnamed_task}'")
    return unnamed_task.split(".")[1].strip()
