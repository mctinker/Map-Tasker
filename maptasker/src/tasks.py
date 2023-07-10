#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# tasks: Process Tasks                                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import defusedxml.ElementTree  # Need for type hints
import maptasker.src.actione as action_evaluate

from maptasker.src.xmldata import tag_in_type
from maptasker.src.kidapp import get_kid_app
from maptasker.src.getids import get_ids
from maptasker.src.sysconst import UNKNOWN_TASK_NAME
from maptasker.src.sysconst import NO_PROJECT
from maptasker.src.sysconst import logger
from maptasker.src.error import error_handler
from maptasker.src.frmthtml import format_html
from maptasker.src.shellsort import shell_sort
import maptasker.src.taskflag as task_flags


# #######################################################################################
# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
# #######################################################################################
def get_actions(
    primary_items: dict,
    current_task: defusedxml.ElementTree.XML,
) -> list:
    """
    Return a list of Task's actions for the given Task
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param current_task: xml element of the Task we are getting actions for
        :return: list of Task 'action' output lines
    """
    tasklist = []

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
        # Task's Action statements can be out-of-order, and we need them in proper-order/sequence
        # sort the Task's Actions by attrib sr (e.g. sr='act0', act1, act2, etc.) to get them in true order
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
                "Task ID:"
                + str(action.attrib["sr"])
                + " Code:"
                + child.text
                + " task_code:"
                + task_code
                + "Action attr:"
                + str(action.attrib)
            )

            # Calculate the amount of indention required
            if (
                ">End If" in task_code
                or ">Else" in task_code
                or ">End For" in task_code
            ):  # Do we un-indent?
                indentation -= 1
                length_indent = len(indentation_amount)
                indentation_amount = indentation_amount[24:length_indent]
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
                indentation_amount = f"{indentation_amount}&nbsp;&nbsp;&nbsp;&nbsp;"

    return tasklist


# #######################################################################################
# Get the name of the task given the Task ID
# return the Task's element and the Task's name
# #######################################################################################
def get_task_name(
    primary_items,
    the_task_id: str,
    tasks_that_have_been_found: list,
    task_output_lines: list,
    task_type: str,
) -> tuple[defusedxml.ElementTree.XML, str]:
    """
    Get the name of the task given the Task ID
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param the_task_id: the Task's ID (e.g. '47')
        :param tasks_that_have_been_found: list of Tasks found so far
        :param task_output_lines: list of Tasks
        :param task_type: Type of Task (Entry, Exit, Scene)
        :return: Task's xml element, Task's name
    """
    if the_task_id.isdigit():
        task = primary_items["tasker_root_elements"]["all_tasks"][the_task_id]
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
        try:
            task_name = task.find("nme").text
            if task_type == "Exit":
                task_output_lines.append(
                    f"{task_name}&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task{extra}"
                )

            else:
                task_output_lines.append(
                    f"{task_name}&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task{extra}"
                )
        except AttributeError:
            task_name = UNKNOWN_TASK_NAME
            # Count this as an unnamed Task if it hasn't yet been counted and it is a normal Task
            if not duplicate_task and task_type in {"Entry", "Exit"}:
                primary_items["task_count_unnamed"] = (
                    primary_items["task_count_unnamed"] + 1
                )
            if task_type == "Exit":
                task_output_lines.append(
                    f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task{extra}"
                )

            else:
                task_output_lines.append(
                    f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task{extra}"
                )
    else:
        task = None
        task_name = ''

    return task, task_name


# #######################################################################################
# Find the Project belonging to the Task id passed in
# #######################################################################################
def get_project_for_solo_task(
    primary_items: dict,
    the_task_id: str,
    projects_with_no_tasks: list,
) -> tuple[str, defusedxml.ElementTree.XML]:
    """
    Find the Project belonging to the Task id passed in
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param the_task_id: the ID of the Task
        :param projects_with_no_tasks: list of Projects that do not have any Tasks
        :return: name of the Project that belongs to this task and the Project xml element
    """
    proj_name = NO_PROJECT
    project = None
    if primary_items["tasker_root_elements"]["all_projects"] is not None:
        # Go through each Project
        for project in primary_items["tasker_root_elements"]["all_projects"]:
            proj_name = project.find("name").text
            task_ids = get_ids(
                primary_items, False, project, proj_name, projects_with_no_tasks
            )
            if the_task_id in task_ids:
                return proj_name, project
    return proj_name, project


# #######################################################################################
# Identify whether the Task passed in is part of a Scene: True = yes, False = no
# #######################################################################################
def task_in_scene(the_task_id: str, all_scenes: dict) -> bool:
    """
    Identify whether the Task passed in is part of a Scene: True = yes, False = no
        :param the_task_id: the id of the Task to check against
        :param all_scenes: all Scenes in Tasker configuration
        :return: True if Task is part of a Scene, False otherwise
    """
    # Go through each Scene
    for value in all_scenes.values():
        for child in value:  # Go through sub-elements in the Scene element
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


# #######################################################################################
# We're processing a single task only
# #######################################################################################
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
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param our_task_name: name of Task we are to process
        :param project_name: name of the Project Task belongs to
        :param profile_name: name of the Profile the Task belongs to
        :param task_list: list of Tasks
        :param our_task_element: the xml element for this Task
        :param list_of_found_tasks: all Tasks processed so far
    """
    # Do NOT move this import.  Otherwise, will get recursion error
    from maptasker.src.proclist import process_list

    logger.debug(
        'tasks single task'
        f' name:{primary_items["program_arguments"]["single_task_name"]} our Task'
        f' name:{our_task_name}'
    )
    if primary_items["program_arguments"]["single_task_name"] == our_task_name:
        # We have the single Task we are looking for
        primary_items["found_named_items"]["single_task_found"] = True

        # Clear output list
        primary_items["output_lines"].refresh_our_output(
            primary_items,
            True,
            project_name,
            profile_name,
        )

        # Go get the Task's details
        temporary_task_list = []
        if len(task_list) > 1:  # Make sure task_list has only our found Task
            the_task_name_length = len(our_task_name)
            for item in task_list:
                if our_task_name == item[:the_task_name_length]:
                    temporary_task_list = [item]
                    break
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
    elif (
        len(task_list) > 1
    ):  # If multiple Tasks in this Profile, just get the one we want
        for task_item in task_list:
            if primary_items["program_arguments"]["single_task_name"] in task_item:
                # Start a new line
                primary_items["output_lines"].add_line_to_output(primary_items, 1, "")
                task_list = [task_item]
                # Process the task(s)
                process_list(
                    primary_items,
                    "Task:",
                    task_list,
                    our_task_element,
                    list_of_found_tasks,
                )
                break


# #######################################################################################
# output_task: we have a Task and need to generate the output
# #######################################################################################
def output_task(
    primary_items: dict,
    our_task_name: str,
    our_task_element: defusedxml.ElementTree.XML,
    task_list: list,
    project_name: str,
    profile_name: str,
    list_of_found_tasks: list,
    do_extra: bool,
) -> bool:
    """
    We have a single Task or a list of Tasks.  Output it/them.
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param our_task_name: name of Task
        :param our_task_element: Task xml element
        :param task_list: Task list
        :param project_name: name of current Project
        :param profile_name: name of current Profile
        :param list_of_found_tasks: list of Tasks found so far
        :param do_extra: flag to do/output extra Task stuff
        :return: True if we are searching for a single Task and found it.  Otherwise, False
    """
    # Do NOT move this import.  Otherwise, will get recursion error
    from maptasker.src.proclist import process_list

    # See if there is a Kid app and/or Priority and/or Collision
    if do_extra and primary_items["program_arguments"]["display_detail_level"] == 3:
        if kid_app_info := get_kid_app(our_task_element):
            kid_app_info = format_html(
                primary_items["colors_to_use"], "task_color", "", kid_app_info, True
            )
            task_list[0] = f'{task_list[0]} {kid_app_info}'
        if priority := task_flags.get_priority(our_task_element, False):
            task_list[0] = f'{task_list[0]} {priority}'
        if collision := task_flags.get_collision(our_task_element):
            task_list[0] = f'{task_list[0]} {collision}'
        if stay_awake := task_flags.get_awake(our_task_element):
            task_list[0] = f'{task_list[0]} {stay_awake}'

    # Looking for a single Task?  If so, then process it.
    if our_task_name != "" and primary_items["program_arguments"]["single_task_name"]:
        do_single_task(
            primary_items,
            our_task_name,
            project_name,
            profile_name,
            task_list,
            our_task_element,
            list_of_found_tasks,
        )
        return True  # Call it quits on Task...we have the one we want
    elif task_list:
        # Start a list
        primary_items["output_lines"].add_line_to_output(primary_items, 1, "")
        # Process the list of Task(s)
        process_list(
            primary_items,
            "Task:",
            task_list,
            our_task_element,
            list_of_found_tasks,
        )
        # End Task list
        primary_items["output_lines"].add_line_to_output(primary_items, 3, "")

    return False  # Normal Task...continue processing them
