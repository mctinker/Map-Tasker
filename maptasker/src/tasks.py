#! /usr/bin/env python3
"""Process Tasks"""

#                                                                                      #
# tasks: Process Tasks                                                                 #
#                                                                                      #
from __future__ import annotations

import re

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actione as action_evaluate
import maptasker.src.taskflag as task_flags
from maptasker.src.error import error_handler
from maptasker.src.format import format_html
from maptasker.src.getids import get_ids
from maptasker.src.kidapp import get_kid_app
from maptasker.src.primitem import PrimeItems
from maptasker.src.shelsort import shell_sort
from maptasker.src.sysconst import (
    UNNAMED_ITEM,
    DISPLAY_DETAIL_LEVEL_all_tasks,
    FormatLine,
    logger,
    pattern14,
)
from maptasker.src.xmldata import tag_in_type

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
        print("tasks.py current Task:", current_task)
        error_handler("Error: No action found!!!", 0)
        return []

    if not task_actions:
        return []

    shell_sort(task_actions, True, False)

    indentation = 0
    indentation_amount = ""
    pretty_mode = PrimeItems.program_arguments.get("pretty")

    for action in task_actions:
        child = action.find("code")
        task_code = action_evaluate.get_action_code(child, action, True, "t")

        if any(token in task_code for token in [">End If", ">Else", ">End For"]):
            indentation = max(indentation - 1, 0)
            indentation_amount = indentation_amount[: -(indent_size * 6)]

        # If pretty text, then reformat it.
        if "Configuration Parameter(s):" in task_code and pretty_mode:
            task_code = reformat_html(task_code)

        action_evaluate.build_action(
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
    line_left_arrow = "&#11013;"
    display_level = PrimeItems.program_arguments["display_detail_level"]
    indent = blank * PrimeItems.program_arguments["indent"]

    def append_task_line(name: str, task_type: str) -> None:
        suffix = f"{indent}{line_left_arrow} {task_type} Task{extra}" if display_level > 0 else indent
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


# Identify whether the Task passed in is part of a Scene: True = yes, False = no
def task_in_scene(the_task_id: str, all_scenes: dict) -> bool:
    """
    Identify whether the Task passed in is part of a Scene: True = yes, False = no
        :param the_task_id: the id of the Task to check against
        :param all_scenes: all Scenes in Tasker configuration
        :return: True if Task is part of a Scene, False otherwise
    """
    # Go through each Scene
    for value in all_scenes.values():
        for child in value["xml"]:  # Go through sub-elements in the Scene element
            if tag_in_type(child.tag, True):
                for subchild in child:  # Go through xxxxElement sub-items
                    # Is this Task in this specific Scene (child)?
                    if tag_in_type(subchild.tag, False) and the_task_id == subchild.text:
                        return True
                    if child.tag == "Str":  # Passed any click Task
                        break

    return False


# We're processing a single task only
# Optimized
def do_single_task(
    our_task_name: str,
    project_name: str,
    profile_name: str,
    task_list: list,
    our_task_element: defusedxml.ElementTree,
    list_of_found_tasks: list,
) -> None:
    """
    Process a single Task only.

    Args:
        our_task_name (str): The name of the Task to be processed.
        project_name (str): The name of the Project the Task belongs to.
        profile_name (str): The name of the Profile the Task belongs to.
        task_list (list): A list of Tasks.
        our_task_element (defusedxml.ElementTree): The XML element for this Task.
        list_of_found_tasks (list): A list of all Tasks processed so far.

    Returns:
        None
    """
    # This import must reside here to avoid circular error.
    from maptasker.src.proclist import process_list

    logger.debug(
        f"Comparing task name:{PrimeItems.program_arguments['single_task_name']} to our Task name:{our_task_name}",
    )

    if PrimeItems.program_arguments.get("single_task_name") == our_task_name:
        PrimeItems.found_named_items.update(
            {
                "single_task_found": True,
                "single_project_found": True,
                "single_profile_found": True,
            },
        )

        save_project, save_profile = (
            PrimeItems.program_arguments["single_project_name"],
            PrimeItems.program_arguments["single_profile_name"],
        )
        PrimeItems.program_arguments.update(
            {
                "single_project_name": project_name,
                "single_profile_name": profile_name or UNNAMED_ITEM,
            },
        )

        PrimeItems.output_lines.refresh_our_output(True, project_name, profile_name)

        temporary_task_list = (
            [item for item in task_list if our_task_name == item[: len(our_task_name)]] if task_list else task_list
        )

        if PrimeItems.program_arguments.get("pretty") and temporary_task_list:
            temporary_task_list[0] = temporary_task_list[0].replace("[", "<br>[")

        process_list(
            "Task:",
            temporary_task_list,
            our_task_element,
            list_of_found_tasks,
        )

        PrimeItems.program_arguments.update(
            {"single_project_name": save_project, "single_profile_name": save_profile},
        )
    else:
        PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)

        if PrimeItems.program_arguments.get("pretty") and "[" not in our_task_name:
            task_list[0] = task_list[0].replace(
                "[",
                f"<br>{'&nbsp;' * len(our_task_name)}[",
            )

        process_list("Task:", task_list, our_task_element, list_of_found_tasks)
        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# Search image xml element for key and return title=value
def get_image(image: defusedxml.ElementTree, title: str, key: str) -> str:
    """Returns:
        - str: Returns a string.
    Parameters:
        - image (defusedxml.ElementTree): An XML element tree.
        - title (str): The title of the image.
        - key (str): The key to search for in the XML element tree.
    Processing Logic:
        - Finds the element with the given key.
        - If the element is not found, returns an empty string.
        - If the element's text contains a period, splits the text at the last period and returns the second part.
        - If the text is empty, returns an empty string.
        - Otherwise, returns a string containing the title and text."""
    element = image.find(key)
    if element is None:
        return ""
    text = element.text
    if "." in text:
        text = text.rsplit(".", 1)[1]
    return f"{title}={text} " if text else ""


# If Task has an icon, get and format it in the Task output line.
def get_icon_info(the_task: defusedxml.ElementTree) -> str:
    """
    Gets icon information from the task XML.
    Args:
        the_task: defusedxml.ElementTree: The task XML tree
    Returns:
        str: Formatted icon information text wrapped in brackets
    - Finds the <Img> element from the task
    - Extracts the icon name, package and class from the <Img> attributes
    - Concatenates them together with a space separator and strips trailing spaces
    - Returns the concatenated text wrapped in [Icon Info()] brackets
    """
    image = the_task.find("Img")
    if image is None:
        return ""
    icon_name = get_image(image, "name", "nme")
    icon_pkg = get_image(image, "pkg", "pkg")
    icon_cls = get_image(image, "class", "cls")
    text = f"{icon_pkg}{icon_cls}{icon_name}"
    text = text.rstrip(" ")

    return f"[Icon Info({text})]"


# Get additional information for this Task
# Optimized
def get_extra_details(
    our_task_element: defusedxml.ElementTree,
    task_output_lines: list,
) -> tuple:
    """
    Get additional information for this Task.

    Args:
        our_task_element (xml): The Task head XML element.
        task_output_lines (list): List of Task's output line(s).

    Returns:
        tuple (str, str, str, str, str): The extra details as strings.
    """
    extra_details = {
        "kid_app_info": get_kid_app(our_task_element),
        "priority": task_flags.get_priority(our_task_element, False),
        "collision": task_flags.get_collision(our_task_element),
        "stay_awake": task_flags.get_awake(our_task_element),
        "icon_info": get_icon_info(our_task_element),
    }

    # Process 'kid_app_info' separately if it exists
    if extra_details["kid_app_info"]:
        extra_details["kid_app_info"] = format_html(
            "task_color",
            "",
            extra_details["kid_app_info"],
            True,
        )

    # Append non-empty details to the first line of task_output_lines
    task_output_lines[0] += " " + " ".join(filter(None, extra_details.values()))

    return tuple(extra_details.values())


# Given a list of tasks, output them.
# Optimized
def output_task_list(
    list_of_tasks: list,
    project_name: str,
    profile_name: str,
    task_output_lines: str,
    list_of_found_tasks: list,
    do_extra: bool,
) -> bool:
    """
    Given a list of tasks, output them.  The list of tasks is a list of tuples.
        The first element is the Task name, the second is the Task element.
        Args:

            list_of_tasks (list): list of Tasks to output.
            project_name (str): name of the owning Projeect
            profile_name (str): name of the owning Profile
            task_output_lines (str): the output lines for the Tasks
            list_of_found_tasks (list): list of Tasks found so far
            do_extra (bool): True to output extra info.
        Returns:
            bool: True if we found a single Task we are looking for"""
    for count, task_item in enumerate(list_of_tasks):
        # If we are coming in without a Task name, then we are only doing a single Task and we need to plug in
        # the Task name.
        task_output_lines[count] = f"{task_item['name']}&nbsp;&nbsp;"

        # fmt: off
        # task_output_lines[count] = task_output_lines[count] or f"{task_item['name']}&nbsp;&nbsp;"
        # fmt: on

        # Doing extra details?
        if (do_extra and PrimeItems.program_arguments["display_detail_level"] > DISPLAY_DETAIL_LEVEL_all_tasks):
            # Get the extra details for this Task
            extra_details = get_extra_details(
                task_item["xml"],
                [task_output_lines[count]],
            )
            # Tack on the extra info since [task_output_lines[count]] it is immutable
            task_output_lines[count] += " ".join(filter(None, extra_details))

        do_single_task(
            task_item["name"],
            project_name,
            profile_name,
            [task_output_lines[count]],
            task_item["xml"],
            list_of_found_tasks,
        )

        # If only doing a single Task and we found/did it, then we are done
        if PrimeItems.program_arguments.get("single_task_name") == task_item["name"]:
            PrimeItems.found_named_items["single_task_found"] = True
            return True

    return False
