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
from routines import actione as action_evaluate

import routines.outputl as build_output
from routines.xmldata import tag_in_type
from routines.sysconst import *
from config import *  # Configuration info

# from proclist import process_list
from routines.shellsort import shell_sort


# #######################################################################################
# Navigate through Task's Actions and identify each
# Return a list of Task's actions for the given Task
# #######################################################################################
def get_actions(current_task, colormap, display_detail_level):
    tasklist = []

    try:
        task_actions = current_task.findall("Action")
    except Exception as e:
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
            # if create_dictionary:  # Are we creating a dictionary for Actions?
            #     process_action_codes.build_action_code(child, action, 't')
            task_code = action_evaluate.get_action_code(
                child, action, True, colormap, "t", display_detail_level
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
                "</span>End If" in task_code
                or "</span>Else" in task_code
                or "</span>End For" in task_code
            ):  # Do we un-indent?
                indentation -= 1
                length_indent = len(indentation_amount)
                indentation_amount = indentation_amount[24:length_indent]
            action_evaluate.build_action(
                tasklist, task_code, child, indentation, indentation_amount
            )
            if (
                "</span>If" in task_code
                or "</span>Else" in task_code
                or "</span>For" in task_code
            ):  # Do we indent?
                indentation += 1
                indentation_amount = f"{indentation_amount}&nbsp;&nbsp;&nbsp;&nbsp;"
    return tasklist


# #######################################################################################
# Get the name of the task given the Task ID
# return the Task's element and the Task's name
# #######################################################################################
def get_task_name(
    the_task_id, tasks_that_have_been_found, the_task_list, task_type, all_tasks: dict
):
    task = all_tasks[the_task_id]
    tasks_that_have_been_found.append(the_task_id)
    extra = f"&nbsp;&nbsp;Task ID: {the_task_id}"
    try:
        task_name = task.find("nme").text
        if task_type == "Exit":
            the_task_list.append(
                f"{task_name}&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task{extra}"
            )

        else:
            the_task_list.append(
                f"{task_name}&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task{extra}"
            )

    except Exception as e:
        task_name = UNKNOWN_TASK_NAME
        if task_type == "Exit":
            the_task_list.append(
                f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;&nbsp;&nbsp;<<< Exit Task{extra}"
            )

        else:
            the_task_list.append(
                f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;&nbsp;&nbsp;<<< Entry Task{extra}"
            )

    return task, task_name


# #######################################################################################
# Find the Project belonging to the Task id passed in
# #######################################################################################
def get_project_for_solo_task(the_task_id, projects_with_no_tasks, all_projects):
    proj_name = NO_PROJECT
    for project in all_projects:
        proj_name = project.find("name").text
        try:
            proj_tasks = project.find("tids").text
        except Exception as e:  # Project has no Tasks
            if proj_name not in projects_with_no_tasks:
                projects_with_no_tasks.append(proj_name)
            proj_name = NO_PROJECT
            continue
        list_of_tasks = proj_tasks.split(",")
        if the_task_id in list_of_tasks:
            return proj_name, project
    return proj_name, project


# #######################################################################################
# Identify whether the Task passed in is part of a Scene: True = yes, False = no
# #######################################################################################
def task_in_scene(the_task_id, all_scenes):
    for scene in all_scenes:
        for child in all_scenes[scene]:  # Go through sub-elements in the Scene element
            if tag_in_type(child.tag, True):
                for subchild in child:  # Go through xxxxElement sub-items
                    if tag_in_type(subchild.tag, False):
                        if (
                            the_task_id == subchild.text
                        ):  # Is this Task in this specific Scene (child)?
                            return True
                    elif child.tag == "Str":  # Passed any click Task
                        break
                    else:
                        continue
    return False


# #######################################################################################
# Process a single Task that does not belong to any Profile
# #######################################################################################
def process_solo_task_with_no_profile(
    output_list,
    task_id,
    found_tasks,
    program_args,
    found_items,
    unnamed_task_count,
    have_heading: bool,
    projects_with_no_tasks,
    heading,
    colormap,
    all_tasker_items,
):
    the_task_name = ""
    unknown_task, specific_task = False, False

    # Get the Project this Task is under.
    project_name, the_project = get_project_for_solo_task(
        task_id, projects_with_no_tasks, all_tasker_items["all_projects"]
    )

    # At this point, we've found the Project this Task belongs to, or it doesn't belong to any Task
    if not have_heading:
        build_output.my_output(
            colormap, program_args, output_list, 0, "<hr>"
        )  # blank line
        build_output.my_output(
            colormap,
            program_args,
            output_list,
            0,
            (
                f'<font color="{trailing_comments_color}"'
                + program_args["font_to_use"]
                + "Tasks that are not called by any Profile..."
            ),
        )
        build_output.my_output(
            colormap, program_args, output_list, 1, ""
        )  # Start Task list
        have_heading = True

    # Get the Task's name
    task_element, task_name = get_task_name(
        task_id, found_tasks, [], "", all_tasker_items["all_tasks"]
    )
    if task_name == UNKNOWN_TASK_NAME:
        task_name = f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;Task ID: {task_id}"
        if task_in_scene(task_id, all_tasker_items["all_scenes"]):
            return have_heading, specific_task  # Ignore it if it is in a Scene
        unknown_task = True
        unnamed_task_count += 1
    else:
        the_task_name = task_name

    if not unknown_task and project_name != NO_PROJECT:
        if program_args["debug"]:
            task_name += f" with Task ID {task_id} ...in Project {project_name} <em>No Profile</em>"
        else:
            task_name += f" ...in Project {project_name} <em>No Profile</em>"

    # Output the (possible unknown) Task's details
    if (
        not unknown_task or program_args["display_detail_level"] > 0
    ):  # Only list named Tasks or if details are wanted
        task_list = [task_name]

        # We have the Tasks.  Now let's output them.
        specific_task = output_task(
            output_list,
            the_task_name,
            task_element,
            task_list,
            project_name,
            "None",
            [],
            heading,
            colormap,
            program_args,
            all_tasker_items,
            found_items,
        )
    return have_heading, specific_task


# #######################################################################################
# output_task: we have a Task and need to generate the output
# #######################################################################################
def output_task(
    output_list,
    our_task_name,
    our_task_element,
    task_list,
    project_name,
    profile_name,
    list_of_found_tasks,
    heading,
    colormap,
    program_args,
    all_tasker_items,
    found_items,
):
    # Do NOT move this import.  Otherwise, will get recursion error
    from routines.proclist import process_list

    if (
        our_task_name != "" and program_args["single_task_name"]
    ):  # Are we mapping just a single Task?
        if program_args["single_task_name"] == our_task_name:
            # We have the single Task we are looking for
            found_items["single_task_found"] = True

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
                    build_output.my_output(
                        colormap, program_args, output_list, 3, ""
                    )  # End Task list
                    break
        return True  # Call it quits on Task...we have the one we want
    elif task_list:
        build_output.my_output(
            colormap, program_args, output_list, 1, ""
        )  # Start Task list
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
        build_output.my_output(
            colormap, program_args, output_list, 3, ""
        )  # End Task list

    return False  # Normal Task...continue processing them
