"""Process Tasks"""

#! /usr/bin/env python3

#                                                                                      #
# tasks: Process Tasks                                                                 #
#                                                                                      #
from __future__ import annotations

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actione as action_evaluate
import maptasker.src.taskflag as task_flags
from maptasker.src.error import error_handler
from maptasker.src.format import format_html
from maptasker.src.getids import get_ids
from maptasker.src.kidapp import get_kid_app
from maptasker.src.primitem import PrimeItems
from maptasker.src.shelsort import shell_sort
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, DISPLAY_DETAIL_LEVEL_all_tasks, FormatLine, logger
from maptasker.src.xmldata import tag_in_type

blank = "&nbsp;"


# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
def get_actions(
    current_task: defusedxml.ElementTree.XML,
) -> list:
    """
    Get the actions for a task
    Args:
        current_task: defusedxml.ElementTree.XML - The XML element of the current task
    Returns:
        list - The list of actions for the task
    Processing Logic:
        1. Get all <Action> elements from the current task
        2. Sort the actions by their "sr" attribute to get them in proper order
        3. Iterate through each action and get its code
        4. Build the action and add indentation if it is a conditional statement
        5. Return the list of actions
    """
    tasklist = []
    blanks = f'{"&nbsp;" * PrimeItems.program_arguments["indent"]}'

    # Get the Task's Actions (<Action> elements)
    try:
        task_actions = current_task.findall("Action")
    except defusedxml.DefusedXmlException:
        print("tasks.py current Task:", current_task)
        error_handler("Error: No action found!!!", 0)
        return []

    # Process the Actions
    if task_actions:
        indentation_amount = ""
        indentation = 0
        # Task's Action statements can be out-of-order, and we need them in
        # proper-order/sequence.
        # sort the Task's Actions by attrib sr (e.g. sr='act0', act1, act2, etc.)
        # to get them in true order.
        if len(task_actions) > 0:
            shell_sort(task_actions, True, False)

        # Now go through each Action to start processing it.  They are in "argn" "n" order.
        for action in task_actions:
            child = action.find("code")  # Get the <code> element
            # Get the Action code ( <code> ).  task_code will be returned with the formatted task action output line.
            task_code = action_evaluate.get_action_code(
                child,
                action,
                True,
                "t",
            )
            # Log the Task action.
            # logger.debug(
            #     f'Task ID:{str(action.attrib["sr"])} Code:{child.text} task_code:{task_code}Action attr:{str(action.attrib)}'
            # )

            # Calculate the amount of indention required
            if ">End If" in task_code or ">Else" in task_code or ">End For" in task_code:  # Do we un-indent?
                indentation -= 1
                length_indent = len(indentation_amount)
                # Total indentation = 6 characters (&nbsp;) times the indent argument
                total_indentation = int(f'{PrimeItems.program_arguments["indent"]*6}')
                indentation_amount = indentation_amount[total_indentation:length_indent]

            # Make it pretty
            if "Configuration Parameter(s):" in task_code and PrimeItems.program_arguments["pretty"]:
                number_of_blanks = task_code.find(":")
                task_code = task_code.replace(",", f"<br>{blank*(number_of_blanks-70)}")  # Back out the "<span..."
                if "Configuration Parameter(s):\n," in task_code:
                    task_code = task_code.replace("Configuration Parameter(s):\n,", "Configuration Parameter(s):\n")

            # Build the output line.
            tasklist = action_evaluate.build_action(
                tasklist,
                task_code,
                child,
                indentation,
                indentation_amount,
            )

            #  Indent the line if this is a condition
            if ">If" in task_code or ">Else" in task_code or ">For<" in task_code:  # Do we indent?
                indentation += 1
                indentation_amount = f"{indentation_amount}{blanks}"

    return tasklist


# Determine if the Task is an Entry or Exit Task.
def extry_or_exit_task(
    task_output_lines: list,
    task_name: str,
    task_type: str,
    extra: str,
    duplicate_task: bool,
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

        Returns:
            tuple: task_output_lines and task_name
    """
    line_left_arrow = "&#11013;"
    # Determine if this is an "Entry" or "Exit" Task
    if task_name:
        # Don't add the entry/exit text if display level = 0
        if PrimeItems.program_arguments["display_detail_level"] > 0:
            if task_type == "Exit":
                task_output_lines.append(f"{task_name}{blank*4}{line_left_arrow} Exit Task{extra}")

            else:
                task_output_lines.append(f"{task_name}{blank*4}{line_left_arrow} Entry Task{extra}")
        else:
            task_output_lines.append(f"{task_name}{blank*4}")
    else:
        task_name = UNKNOWN_TASK_NAME
        # Count this as an unnamed Task if it hasn't yet been counted and it
        # is a normal Task
        if not duplicate_task and task_type in {"Entry", "Exit"}:
            PrimeItems.task_count_unnamed = PrimeItems.task_count_unnamed + 1
        blanks = f'{blank * PrimeItems.program_arguments["indent"]}'
        # Don't add the entry/exit text if display level = 0
        if PrimeItems.program_arguments["display_detail_level"] > 0:
            if task_type == "Exit":
                task_output_lines.append(f"{UNKNOWN_TASK_NAME}{blanks}{line_left_arrow} Exit Task{extra}")

            else:
                task_output_lines.append(f"{UNKNOWN_TASK_NAME}{blanks}{line_left_arrow} Entry Task{extra}")
        else:
            task_output_lines.append(f"{UNKNOWN_TASK_NAME}{blanks}")

    return task_output_lines, task_name


# Get the name of the task given the Task ID
# return the Task's element and the Task's name
def get_task_name(
    the_task_id: str,
    tasks_that_have_been_found: list,
    task_output_lines: list,
    task_type: str,
) -> tuple[defusedxml.ElementTree.XML, str]:
    """
    Get the name of the task given the Task ID.
    Add to the output line if this is an Entry or xit Task.

        :param the_task_id: the Task's ID (e.g. '47')
        :param tasks_that_have_been_found: list of Tasks found so far
        :param task_output_lines: list of Tasks
        :param task_type: Type of Task (Entry, Exit, Scene)
        :return: Task's xml element, Task's name
    """

    if the_task_id.isdigit():
        task = PrimeItems.tasker_root_elements["all_tasks"][the_task_id]["xml"]
        task_name = PrimeItems.tasker_root_elements["all_tasks"][the_task_id]["name"]
        duplicate_task = False
        if the_task_id not in tasks_that_have_been_found:
            tasks_that_have_been_found.append(the_task_id)
        else:
            duplicate_task = True
        extra = f"&nbsp;&nbsp;Task ID: {the_task_id}" if PrimeItems.program_arguments["debug"] else ""

        # Determine if this is an "Entry" or "Exit" Task
        task_output_lines, task_name = extry_or_exit_task(
            task_output_lines,
            task_name,
            task_type,
            extra,
            duplicate_task,
        )

    else:
        task = None
        task_name = ""

    return task, task_name


# Find the Project belonging to the Task id passed in
def get_project_for_solo_task(
    the_task_id: str,
    projects_with_no_tasks: list,
) -> tuple[str, defusedxml.ElementTree.XML]:
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
def do_single_task(
    our_task_name: str,
    project_name: str,
    profile_name: str,
    task_list: list,
    our_task_element: defusedxml.ElementTree.XML,
    list_of_found_tasks: list,
) -> None:
    """
    Process a single Task only.

    Args:
        our_task_name (str): The name of the Task to be processed.
        project_name (str): The name of the Project the Task belongs to.
        profile_name (str): The name of the Profile the Task belongs to.
        task_list (list): A list of Tasks.
        our_task_element (defusedxml.ElementTree.XML): The XML element for this Task.
        list_of_found_tasks (list): A list of all Tasks processed so far.

    Returns:
        None

    This function processes a single Task only. It first checks if the Task name matches
    the single Task name specified in the program arguments. If it does, it sets the
    "single_task_found", "single_project_found", and "single_profile_found" flags to True,
    and updates the program arguments with the project and profile names. It then clears
    the output list. If a Task list is provided, it filters the list to include only the
    Tasks that start with the same name as the single Task. If the Task list is empty, it
    sets the temporary task list to an empty list. It then processes the Task/Task list by
    calling the process_list function. If multiple Tasks are present in the Profile, it
    adds a line to the output, filters the Task list to include only the single Task, and
    processes the Task by calling the process_list function.
    """
    # This import must reside here to avoid circular error.
    from maptasker.src.proclist import process_list

    """
    Process a single Task only

        :param our_task_name: name of Task we are to process
        :param project_name: name of the Project Task belongs to
        :param profile_name: name of the Profile the Task belongs to
        :param task_list: list of Tasks
        :param our_task_element: the xml element for this Task
        :param list_of_found_tasks: all Tasks processed so far
    """

    logger.debug(
        "tasks single task"
        f' name:{PrimeItems.program_arguments["single_task_name"]} our Task'
        f" name:{our_task_name}",
    )

    # Doing a specific Task...
    if (
        PrimeItems.program_arguments["single_task_name"]
        and PrimeItems.program_arguments["single_task_name"] == our_task_name
    ):
        # We have the single Task we are looking for
        # Set all the "found" items so that everyone bails out of their loops.
        PrimeItems.found_named_items["single_task_found"] = True
        PrimeItems.found_named_items["single_project_found"] = True
        PrimeItems.found_named_items["single_profile_found"] = True
        save_project = PrimeItems.program_arguments["single_project_name"]
        PrimeItems.program_arguments["single_project_name"] = project_name
        save_profile = PrimeItems.program_arguments["single_profile_name"]
        PrimeItems.program_arguments["single_profile_name"] = profile_name

        # Clear output list
        PrimeItems.output_lines.refresh_our_output(
            True,
            project_name,
            profile_name,
        )

        # Go get the Task's details if we have a Task list
        #  Note: we need to save the task_list since process_list will alter it.
        temporary_task_list = []
        if task_list:
            the_task_name_length = len(our_task_name)
            temporary_task_list = [item for item in task_list if our_task_name == item[:the_task_name_length]]
        else:
            temporary_task_list = task_list

        # Make the line pretty
        if PrimeItems.program_arguments["pretty"]:
            temporary_task_list[0] = temporary_task_list[0].replace("[", "<br>[")

        # Go process the Task/Task list
        process_list(
            "Task:",
            temporary_task_list,
            our_task_element,
            list_of_found_tasks,
        )

        # Restore our saved project and profile
        PrimeItems.program_arguments["single_project_name"] = save_project
        PrimeItems.program_arguments["single_profile_name"] = save_profile

    # If multiple Tasks in this Profile, just get the one we want
    else:
        PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)

        # Make the line pretty
        if PrimeItems.program_arguments["pretty"]:
            blanks = f'{"&nbsp;" * len(our_task_name)}'
            task_list[0] = task_list[0].replace("[", f"<br>{blanks}[")

        # Process the task(s)
        process_list(
            "Task:",
            task_list,
            our_task_element,
            list_of_found_tasks,
        )
        # End Task list
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
def get_extra_details(
    our_task_element: defusedxml.ElementTree,
    task_output_lines: list,
) -> tuple:
    """
    Get additional information for this Task
        Args:

            our_task_elelemtn(xml): our Task head xml element.
            task_output_lines (list): list of Task's output line(s)

        Returns:
            _tuple (str, str, str, str): the extra stuff as strings"""
    # KID App info
    if kid_app_info := get_kid_app(our_task_element):
        kid_app_info = format_html("task_color", "", kid_app_info, True)
        task_output_lines[0] = f"{task_output_lines[0]} {kid_app_info}"

    # Task priority
    if priority := task_flags.get_priority(our_task_element, False):
        task_output_lines[0] = f"{task_output_lines[0]} {priority}"

    # Collision flags
    if collision := task_flags.get_collision(our_task_element):
        task_output_lines[0] = f"{task_output_lines[0]} {collision}"

    # Task stay-awake flag
    if stay_awake := task_flags.get_awake(our_task_element):
        task_output_lines[0] = f"{task_output_lines[0]} {stay_awake}"

    # Task icon info, if any.
    if icon_info := get_icon_info(our_task_element):
        task_output_lines[0] = f"{task_output_lines[0]} {icon_info}"

    return kid_app_info, priority, collision, stay_awake, icon_info


# Given a list of tasks, output them.
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
            bool: True if we found a Task"""
    for count, task_item in enumerate(list_of_tasks):
        # If we are coming in without a Task name, then we are only doing a single Task and we need to plug in
        # the Task name.
        if task_output_lines[count] == " ":
            task_output_lines[count] = f'{task_item["name"]}&nbsp;&nbsp;'

        # Doing extra details?
        if do_extra and PrimeItems.program_arguments["display_detail_level"] > DISPLAY_DETAIL_LEVEL_all_tasks:
            # Get the extra details for this Task
            (
                kid_app_info,
                priority,
                collision,
                stay_awake,
                icon_info,
            ) = get_extra_details(
                task_item["xml"],
                [task_output_lines[count]],
            )
            # Tack on the extra info since [task_output_lines[count]] it is immutable
            task_output_lines[count] = (
                f"{task_output_lines[count]} {kid_app_info}{priority}{collision}{stay_awake}{blank*2}{icon_info}"
            )

        do_single_task(
            task_item["name"],
            project_name,
            profile_name,
            [task_output_lines[count]],
            task_item["xml"],
            list_of_found_tasks,
        )

        # If only doing a single Task and we found/did it, then we are done
        if (
            PrimeItems.program_arguments["single_task_name"]
            and PrimeItems.program_arguments["single_task_name"] == task_item["name"]
        ):
            PrimeItems.found_named_items["single_task_found"] = True
            return True

    return False
