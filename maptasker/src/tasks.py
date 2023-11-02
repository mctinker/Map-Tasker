#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# tasks: Process Tasks                                                                 #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import defusedxml.ElementTree  # Need for type hints

import maptasker.src.actione as action_evaluate
import maptasker.src.taskflag as task_flags
from maptasker.src.error import error_handler
from maptasker.src.format import format_html
from maptasker.src.getids import get_ids
from maptasker.src.kidapp import get_kid_app
from maptasker.src.proclist import process_list
from maptasker.src.shellsort import shell_sort
from maptasker.src.sysconst import UNKNOWN_TASK_NAME, FormatLine, logger
from maptasker.src.xmldata import tag_in_type

blank = "&nbsp;"


# ##################################################################################
# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
# ##################################################################################
def get_actions(
    primary_items: dict,
    current_task: defusedxml.ElementTree.XML,
) -> list:
    """
    Return a list of Task's actions for the given Task
        :param primary_items:  Program registry.  See primitem.py for details.
        :param current_task: xml element of the Task we are getting actions for
        :return: list of Task 'action' output lines
    """
    tasklist = []
    blanks = f'{"&nbsp;" * primary_items["program_arguments"]["indent"]}'

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

        # Now go through each Action to start processing it.
        for action in task_actions:
            child = action.find("code")  # Get the <code> element
            # Get the Action code ( <code> )
            task_code = action_evaluate.get_action_code(
                primary_items,
                child,
                action,
                True,
                "t",
            )
            logger.debug(
                f'Task ID:{str(action.attrib["sr"])} Code:{child.text} task_code:{task_code}Action attr:{str(action.attrib)}'
            )

            # Calculate the amount of indention required
            if (
                ">End If" in task_code
                or ">Else" in task_code
                or ">End For" in task_code
            ):  # Do we un-indent?
                indentation -= 1
                length_indent = len(indentation_amount)
                # Total indentation = 6 characters (&nbsp;) times the indent argument
                total_indentation = int(
                    f'{primary_items["program_arguments"]["indent"]*6}'
                )
                indentation_amount = indentation_amount[total_indentation:length_indent]
            tasklist = action_evaluate.build_action(
                primary_items,
                tasklist,
                task_code,
                child,
                indentation,
                indentation_amount,
            )
            #  Indent the line if this is a condition
            if (
                ">If" in task_code or ">Else" in task_code or ">For<" in task_code
            ):  # Do we indent?
                indentation += 1
                indentation_amount = f"{indentation_amount}{blanks}"

    return tasklist


# ##################################################################################
# Determine if the Task is an Entry or Exit Task.
# ##################################################################################
def extry_or_exit_task(
    primary_items: dict,
    task_output_lines: list,
    task_name: str,
    task_type: str,
    extra: str,
    duplicate_task: bool,
) -> tuple[list, str]:
    """_summary_
    Determine if this is an "Entry" or "Exit" Task and add the appropriate text to the
    Task's output lines.
        Args:
            primary_items (dict):Program registry.  See primitem.py for details.
            task_output_lines (list): List of output lines for this Task
            task_name (str): Name of this Task.
            task_type (str): Type of this Task: Entry or Exit
            extra (str): Extra text to add to the end of the Task's output line
            duplicate_task (bool): Is this a duplicate Task? True if it is.

        Returns:
            typle: task_output_lines and task_name
    """
    # Determine if this is an "Entry" or "Exit" Task
    if task_name:
        # Don't add the entry/exit text if display level = 0
        if primary_items["program_arguments"]["display_detail_level"] > 0:
            if task_type == "Exit":
                task_output_lines.append(f"{task_name}{blank*4}<<< Exit Task{extra}")

            else:
                task_output_lines.append(f"{task_name}{blank*4}<<< Entry Task{extra}")
        else:
            task_output_lines.append(f"{task_name}{blank*4}")
    else:
        task_name = UNKNOWN_TASK_NAME
        # Count this as an unnamed Task if it hasn't yet been counted and it
        # is a normal Task
        if not duplicate_task and task_type in {"Entry", "Exit"}:
            primary_items["task_count_unnamed"] = (
                primary_items["task_count_unnamed"] + 1
            )
        blanks = f'{blank * primary_items["program_arguments"]["indent"]}'
        # Don't add the entry/exit text if display level = 0
        if primary_items["program_arguments"]["display_detail_level"] > 0:
            if task_type == "Exit":
                task_output_lines.append(
                    f"{UNKNOWN_TASK_NAME}{blanks}<<< Exit Task{extra}"
                )

            else:
                task_output_lines.append(
                    f"{UNKNOWN_TASK_NAME}{blanks}<<< Entry Task{extra}"
                )
        else:
            task_output_lines.append(f"{UNKNOWN_TASK_NAME}{blanks}")

    return task_output_lines, task_name


# ##################################################################################
# Get the name of the task given the Task ID
# return the Task's element and the Task's name
# ##################################################################################
def get_task_name(
    primary_items,
    the_task_id: str,
    tasks_that_have_been_found: list,
    task_output_lines: list,
    task_type: str,
) -> tuple[defusedxml.ElementTree.XML, str]:
    """
    Get the name of the task given the Task ID.
    Add to the output line if this is an Entry or xit Task.
        :param primary_items:  Program registry.  See primitem.py for details.
        :param the_task_id: the Task's ID (e.g. '47')
        :param tasks_that_have_been_found: list of Tasks found so far
        :param task_output_lines: list of Tasks
        :param task_type: Type of Task (Entry, Exit, Scene)
        :return: Task's xml element, Task's name
    """

    if the_task_id.isdigit():
        task = primary_items["tasker_root_elements"]["all_tasks"][the_task_id]["xml"]
        task_name = primary_items["tasker_root_elements"]["all_tasks"][the_task_id][
            "name"
        ]
        duplicate_task = False
        if the_task_id not in tasks_that_have_been_found:
            tasks_that_have_been_found.append(the_task_id)
        else:
            duplicate_task = True
        if primary_items["program_arguments"]["debug"]:
            extra = f"&nbsp;&nbsp;Task ID: {the_task_id}"
        else:
            extra = ""

        # Determine if this is an "Entry" or "Exit" Task
        task_output_lines, task_name = extry_or_exit_task(
            primary_items,
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


# ##################################################################################
# Find the Project belonging to the Task id passed in
# ##################################################################################
def get_project_for_solo_task(
    primary_items: dict,
    the_task_id: str,
    projects_with_no_tasks: list,
) -> tuple[str, defusedxml.ElementTree.XML]:
    """
    Find the Project belonging to the Task id passed in
    :param primary_items: dictionary of the primary items used throughout the module. See primitem.py for details
    :param the_task_id: the ID of the Task
    :param projects_with_no_tasks: list of Projects that do not have any Tasks
    :return: name of the Project that belongs to this task and the Project xml element
    """
    NO_PROJECT = "No Project"
    project_name = NO_PROJECT
    project_element = None

    all_projects = primary_items["tasker_root_elements"]["all_projects"]
    if all_projects is not None:
        for project in all_projects:
            project_element = primary_items["tasker_root_elements"]["all_projects"][
                project
            ]["xml"]
            project_name = primary_items["tasker_root_elements"]["all_projects"][
                project
            ]["name"]
            task_ids = get_ids(
                primary_items,
                False,
                project_element,
                project_name,
                projects_with_no_tasks,
            )
            if the_task_id in task_ids:
                return project_name, project_element

    return project_name, project_element


# ##################################################################################
# Identify whether the Task passed in is part of a Scene: True = yes, False = no
# ##################################################################################
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
                    if (
                        tag_in_type(subchild.tag, False)
                        and the_task_id == subchild.text
                    ):
                        return True
                    elif child.tag == "Str":  # Passed any click Task
                        break
                    else:
                        continue
    return False


# ##################################################################################
# We're processing a single task only
# ##################################################################################
def do_single_task(
    primary_items: dict,
    our_task_name: str,
    project_name: str,
    profile_name: str,
    task_list: list,
    our_task_element: defusedxml.ElementTree.XML,
    list_of_found_tasks: list,
) -> None:
    """
    Process a single Task only
        :param primary_items:  Program registry.  See primitem.py for details.
        :param our_task_name: name of Task we are to process
        :param project_name: name of the Project Task belongs to
        :param profile_name: name of the Profile the Task belongs to
        :param task_list: list of Tasks
        :param our_task_element: the xml element for this Task
        :param list_of_found_tasks: all Tasks processed so far
    """

    logger.debug(
        "tasks single task"
        f' name:{primary_items["program_arguments"]["single_task_name"]} our Task'
        f" name:{our_task_name}"
    )

    # Doing a specific Task...
    if (
        primary_items["program_arguments"]["single_task_name"]
        and primary_items["program_arguments"]["single_task_name"] == our_task_name
    ):
        # We have the single Task we are looking for
        primary_items["found_named_items"]["single_task_found"] = True

        # Clear output list
        primary_items["output_lines"].refresh_our_output(
            primary_items,
            True,
            project_name,
            profile_name,
        )

        # Go get the Task's details if we have a Task list
        #  Note: we need to save the task_list since process_list will alter it.
        temporary_task_list = []
        if task_list:
            the_task_name_length = len(our_task_name)
            temporary_task_list = [
                item
                for item in task_list
                if our_task_name == item[:the_task_name_length]
            ]
        else:
            temporary_task_list = task_list
        # Go process the Task/Task list
        process_list(
            primary_items,
            "Task:",
            temporary_task_list,
            our_task_element,
            list_of_found_tasks,
        )

    # If multiple Tasks in this Profile, just get the one we want
    else:
        primary_items["output_lines"].add_line_to_output(
            primary_items, 1, "", FormatLine.dont_format_line
        )
        # Process the task(s)
        process_list(
            primary_items,
            "Task:",
            task_list,
            our_task_element,
            list_of_found_tasks,
        )
        # End Task list
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, "", FormatLine.dont_format_line
        )


# ##################################################################################
# Search image xml element for key and return title=value
# ##################################################################################
def get_image(image, title, key):
    element = image.find(key)
    if element is None:
        return ""
    text = element.text
    if "." in text:
        text = text.rsplit(".", 1)[1]
    return f"{title}={text} " if text else ""


# ##################################################################################
# If Task has an icon, get and format it in the Task output line.
# ##################################################################################
def get_icon_info(primary_items, the_task):
    image = the_task.find("Img")
    if image is None:
        return ""
    icon_name = get_image(image, "name", "nme")
    icon_pkg = get_image(image, "pkg", "pkg")
    icon_cls = get_image(image, "class", "cls")
    text = f"{icon_pkg}{icon_cls}{icon_name}"
    text = text.rstrip(" ")

    return f"[Icon Info({text})]"


# ##################################################################################
# Get additional information for this Task
# ##################################################################################
def get_extra_details(
    primary_items: dict,
    our_task_element: defusedxml.ElementTree,
    task_output_lines: list,
) -> tuple:
    """_summary_
    Get additional information for this Task
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            our_task_elelemtn(xml): our Task head xml element.
            task_output_lines (list): list of Task's output line(s)

        Returns:
            _tuple (str, str, str, str): the extra stuff as strings
    """
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
    if icon_info := get_icon_info(primary_items, our_task_element):
        task_output_lines[0] = f"{task_output_lines[0]} {icon_info}"

    return kid_app_info, priority, collision, stay_awake, icon_info


# ##################################################################################
# Given a list of tasks, output them.
# ##################################################################################
def output_task_list(
    primary_items: dict,
    list_of_tasks: list,
    project_name: str,
    profile_name: str,
    task_output_lines: str,
    list_of_found_tasks: list,
    do_extra: bool,
) -> None:
    """_summary_
    Given a list of tasks, output them.  The list of tasks is a list of tuples.
        The first element is the Task name, the second is the Task element.
        Args:
            primary_items (dict): Program registry.  See primitem.py for details.
            list_of_tasks (list): list of Tasks to output.
            project_name (str): name of the owning Projeect
            profile_name (str): name of the owning Profile
            task_output_lines (str): the output lines for the Tasks
            list_of_found_tasks (list): list of Tasks found so far
            do_extra (bool): True to output extra info.
    """
    for count, task_item in enumerate(list_of_tasks):
        # Doing extra details?
        if do_extra and primary_items["program_arguments"]["display_detail_level"] > 2:
            # Get the extra details for this Task
            (
                kid_app_info,
                priority,
                collision,
                stay_awake,
                icon_info,
            ) = get_extra_details(
                primary_items,
                task_item["xml"],
                [task_output_lines[count]],
            )
            # Tack on the extra info since [task_output_lines[count]] is immutable
            task_output_lines[
                count
            ] = f"{task_output_lines[count]} {kid_app_info}{priority}{collision}{stay_awake}{blank*2}{icon_info}"

        do_single_task(
            primary_items,
            task_item["name"],
            project_name,
            profile_name,
            [task_output_lines[count]],
            task_item["xml"],
            list_of_found_tasks,
        )

        # If only doing a single Task and we found/did it, then we are done
        if (
            primary_items["program_arguments"]["single_task_name"]
            and primary_items["program_arguments"]["single_task_name"]
            == task_item["name"]
        ):
            return True

    return False
