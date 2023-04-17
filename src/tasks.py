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

import maptasker.src.outputl as build_output
from maptasker.src.xmldata import tag_in_type
from maptasker.src.kidapp import get_kid_app
from maptasker.src.priority import get_priority
from maptasker.src.getids import get_ids
from maptasker.src.sysconst import UNKNOWN_TASK_NAME
from maptasker.src.sysconst import NO_PROJECT
from maptasker.src.sysconst import logger

from maptasker.src.shellsort import shell_sort


# #######################################################################################
# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
# #######################################################################################
def get_actions(
    current_task: defusedxml.ElementTree.XML, colormap: dict, prog_args: dict
) -> list:
    """
    Return a list of Task's actions for the given Task
        :param current_task: xml element of the Task we are getting actions for
        :param colormap: colors to use in output
        :param prog_args: runtime arguments
        :return: list of Task 'action' output lines
    """
    tasklist = []

    try:
        task_actions = current_task.findall("Action")
    except defusedxml.DefusedXmlException:
        print("tasks.py current Task:", current_task)
        error_msg = "Error: No action found!!!"
        print(error_msg)
        logger.debug(error_msg)
        return []
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
                child, action, True, colormap, "t", prog_args
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
            action_evaluate.build_action(
                colormap, tasklist, task_code, child, indentation, indentation_amount
            )
            if (
                ">If" in task_code or ">Else" in task_code or ">For" in task_code
            ):  # Do we indent?
                indentation += 1
                indentation_amount = f"{indentation_amount}&nbsp;&nbsp;&nbsp;&nbsp;"

    return tasklist


# #######################################################################################
# Get the name of the task given the Task ID
# return the Task's element and the Task's name
# #######################################################################################
def get_task_name(
    the_task_id: str,
    tasks_that_have_been_found: list,
    task_output_lines: list,
    task_type: str,
    all_tasks: dict,
) -> tuple[defusedxml.ElementTree.XML, str]:
    """
    Get the name of the task given the Task ID
        :param the_task_id: the Task's ID (e.g. '47')
        :param tasks_that_have_been_found: list of Tasks found so far
        :param task_output_lines: list of Tasks
        :param task_type: Type of Task (Entry, Exit, Scene)
        :param all_tasks: all Tasks in xml
        :return: Task's xml element, Task's name
    """
    if the_task_id.isdigit():
        task = all_tasks[the_task_id]
        tasks_that_have_been_found.append(the_task_id)
        extra = f"&nbsp;&nbsp;Task ID: {the_task_id}"
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
        except Exception as e:
            task_name = UNKNOWN_TASK_NAME
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
    the_task_id: str, projects_with_no_tasks: list, all_projects: dict
) -> tuple[str, defusedxml.ElementTree]:
    """
    Find the Project belonging to the Task id passed in
        :param the_task_id: the ID of the Task
        :param projects_with_no_tasks: list of Projects that do not have any Tasks
        :param all_projects: all Tasker Projects
        :return: name of the Project that belongs to this task and the Project xml element
    """
    proj_name = NO_PROJECT
    project = None
    if all_projects is not None:
        # Go through each Project
        for project in all_projects:
            proj_name = project.find("name").text
            task_ids = get_ids(
                False, {}, {}, [], project, proj_name, projects_with_no_tasks
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
    our_task_name: str,
    output_list: list,
    project_name: str,
    profile_name: str,
    heading: str,
    found_items: dict,
    task_list: list,
    our_task_element: defusedxml.ElementTree.XML,
    list_of_found_tasks: list,
    all_tasker_items: dict,
    colormap: dict,
    program_args: dict,
) -> None:
    """
    Process a single Task only
        :param our_task_name: name of the Task to process
        :param output_list: where the output line goes for Task
        :param project_name: name of the Project Task belongs to
        :param profile_name: name of the Profile the Task belongs to
        :param heading: the heading, if any
        :param found_items: single name for Project/Profile/Task
        :param task_list: list of Tasks
        :param our_task_element: the xml element for this Task
        :param list_of_found_tasks: all Tasks processed so far
        :param all_tasker_items: all Projects/Profiles/Tasks/Scenes
        :param colormap: colors to use in output
        :param program_args: runtime arguments
    """
    # Do NOT move this import.  Otherwise, will get recursion error
    from maptasker.src.proclist import process_list

    logger.debug(
        f'tasks single task name:{program_args["single_task_name"]} our Task'
        f' name:{our_task_name}'
    )
    if program_args["single_task_name"] == our_task_name:
        # We have the single Task we are looking for
        found_items["single_task_found"] = True

        # Clear output list
        build_output.refresh_our_output(
            True,
            output_list,
            project_name,
            profile_name,
            heading,
            colormap,
            program_args,
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
            "Task:",
            output_list,
            temporary_task_list,
            our_task_element,
            list_of_found_tasks,
            program_args,
            colormap,
            all_tasker_items,
        )
    elif (
        len(task_list) > 1
    ):  # If multiple Tasks in this Profile, just get the one we want
        for task_item in task_list:
            if program_args["single_task_name"] in task_item:
                build_output.my_output(
                    colormap, program_args, output_list, 1, ""
                )  # Start Task list
                task_list = [task_item]
                process_list(
                    "Task:",
                    output_list,
                    task_list,
                    our_task_element,
                    list_of_found_tasks,
                    program_args,
                    colormap,
                    all_tasker_items,
                )
                # build_output.my_output(
                #     colormap, program_args, output_list, 3, ""
                # )  # End Task list
                break


# #######################################################################################
# output_task: we have a Task and need to generate the output
# #######################################################################################
def output_task(
    output_list: list,
    our_task_name: str,
    our_task_element: defusedxml.ElementTree.XML,
    task_list: list,
    project_name: str,
    profile_name: str,
    list_of_found_tasks: list,
    heading: str,
    colormap: dict,
    program_args: dict,
    all_tasker_items: dict,
    found_items: dict,
    do_extra: bool,
) -> bool:
    """
    We have a single Task or a list of Tasks.  Output it/them.
        :param output_list: list of output lines generated thus far
        :param our_task_name: name of Task
        :param our_task_element: Task xml element
        :param task_list: Task list
        :param project_name: name of current Project
        :param profile_name: name of current Profile
        :param list_of_found_tasks: list of Tasks found so far
        :param heading: current heading
        :param colormap: colors to use in output
        :param program_args: runtime arguments
        :param all_tasker_items: all Projects/Profiles/Tasks/Scenes
        :param found_items: single Project/Profile/Task to search for
        :param do_extra: flag to do/output extra Task stuff
        :return: True if we are searching for a single Task and found it.  Otherwise, False
    """
    # Do NOT move this import.  Otherwise, will get recursion error
    from maptasker.src.proclist import process_list

    # See if there is a Kid app and/or Priority
    if do_extra and program_args["display_detail_level"] == 3:
        if kid_app_info := get_kid_app(our_task_element):
            task_list[0] = f'{task_list[0]} {kid_app_info}'
        if priority := get_priority(our_task_element, False):
            task_list[0] = f'{task_list[0]} {priority}'

    # Looking for a single Task?
    if our_task_name != "" and program_args["single_task_name"]:
        do_single_task(
            our_task_name,
            output_list,
            project_name,
            profile_name,
            heading,
            found_items,
            task_list,
            our_task_element,
            list_of_found_tasks,
            all_tasker_items,
            colormap,
            program_args,
        )
        return True  # Call it quits on Task...we have the one we want
    elif task_list:
        # Start a list
        build_output.my_output(colormap, program_args, output_list, 1, "")
        # Process the list of Task(s)
        process_list(
            "Task:",
            output_list,
            task_list,
            our_task_element,
            list_of_found_tasks,
            program_args,
            colormap,
            all_tasker_items,
        )
        # End Task list
        build_output.my_output(colormap, program_args, output_list, 3, "")

    return False  # Normal Task...continue processing them
