#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# taskuniq: deal with unique Tasks                                                     #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from typing import List, Union

import defusedxml.ElementTree

import maptasker.src.tasks as tasks
from maptasker.src.sysconst import NO_PROJECT, UNKNOWN_TASK_NAME, FormatLine
from maptasker.src.twisty import add_twisty, remove_twisty


# ##################################################################################
# Output Projects Without Tasks and Projects Without Profiles
# ##################################################################################
def process_missing_tasks_and_profiles(
    primary_items: dict,
    projects_with_no_tasks: Union[List[str], List],
    projects_without_profiles: List[str],
) -> None:
    """
    Output Projects Without Tasks and Projects Without Profiles
        :param primary_items: a dictionary containing program runtime arguments, colors to use in output,
          all Tasker xml root elements, and a list of all output lines.
        :param projects_with_no_tasks: root xml entry for list of Projects with no Tasks
        :param projects_without_profiles: root xml entry for list of Projects with no Profiles
        :return: nothing
    """

    # List Projects with no Tasks
    if (
        len(projects_with_no_tasks) > 0
        and not primary_items["found_named_items"]["single_task_found"]
    ):
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            1,
            "<hr><em>Projects Without Tasks...</em><br>",
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )

        for item in projects_with_no_tasks:
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                f"Project {item} has no <em>Named</em> Tasks",
                ["", "trailing_comments_color", FormatLine.add_end_span],
            )
        # End list
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, "<br>", FormatLine.dont_format_line
        )

    # List all Projects without Profiles
    if projects_without_profiles:
        # Add heading
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            1,
            "<em>Projects Without Profiles...</em><br>",
            ["<br>", "trailing_comments_color", FormatLine.add_end_span],
        )
        for item in projects_without_profiles:
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                f"- Project {item} has no Profiles",
                ["", "trailing_comments_color", FormatLine.add_end_span],
            )
        # End list
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, "<br>", FormatLine.dont_format_line
        )
    return


# ##################################################################################
# Add heading to output for named Tasks not in any Profile
# ##################################################################################
def add_heading(primary_items: dict, save_twisty: bool) -> bool:
    """
    Add a header to the output for the solo Tasks
        :param primary_items:  Program registry.  See primitem.py for details.
        :param save_twisty: flag to indicate whether or not we are doing the twisty/hidden Tasks
        :return: True...flag that the heading has been created/output
    """

    # Start a list and add a ruler-line across page
    primary_items["output_lines"].add_line_to_output(
        primary_items, 1, "<hr>", FormatLine.dont_format_line
    )
    text_line = "Named Tasks that are not called by any Profile..."

    # Add a twisty, if doing twisties, to hide the line
    if save_twisty:
        add_twisty(primary_items, "trailing_comments_color", text_line)

    # Add the header
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        1,
        text_line,
        ["", "trailing_comments_color", FormatLine.add_end_span],
    )
    primary_items["displaying_named_tasks_not_in_profile"] = True
    primary_items["output_lines"].add_line_to_output(
        primary_items, 1, "", FormatLine.dont_format_line
    )  # Start Task list
    return True


# ##################################################################################
# Process a single Task that does not belong to any Profile
# This function is called recursively
# ##################################################################################
def process_solo_task_with_no_profile(
    primary_items: dict,
    task_id: str,
    found_tasks: list,
    task_count: int,
    have_heading: bool,
    projects_with_no_tasks: list,
    save_twisty: bool,
) -> tuple[int, defusedxml.ElementTree.XML, int]:
    """
    Process a single Task that does not belong to any Profile
        :param primary_items:  Program registry.  See primitem.py for details.
        :param task_id: the ID of the Task being displayed
        :param found_tasks: list of Tasks that we have found
        :param task_count: count of the unnamed Tasks
        :param have_heading: whether we have the heading
        :param projects_with_no_tasks: list of Projects without Tasks
        :param save_twisty: whether we are displaying twisty to Hide Task details
        :return: heading flag, xml element for this Task, and total count of unnamed Tasks
    """
    unknown_task, specific_task = False, False

    # Get the Project this Task is under.
    project_name, the_project = tasks.get_project_for_solo_task(
        primary_items,
        task_id,
        projects_with_no_tasks,
    )

    # Get the Task's name
    task_element, task_name = tasks.get_task_name(
        primary_items, task_id, found_tasks, [], ""
    )
    if task_name == UNKNOWN_TASK_NAME:
        task_name = f"{UNKNOWN_TASK_NAME}&nbsp;&nbsp;Task ID: {task_id}"
        # Ignore it if it is in a Scene
        if tasks.task_in_scene(
            task_id, primary_items["tasker_root_elements"]["all_scenes"]
        ):
            return have_heading, specific_task, task_count
        unknown_task = True
    # else:
    #     the_task_name = task_name
    task_count += 1

    # At this point, we've found the Project this Task belongs to,
    # or it doesn't belong to any Profile
    if (
        not have_heading
        and primary_items["program_arguments"]["display_detail_level"] > 2
    ):
        # Add the heading to the output
        have_heading = add_heading(
            primary_items,
            save_twisty,
        )
    if not unknown_task and project_name != NO_PROJECT:
        if primary_items["program_arguments"]["debug"]:
            task_name += (
                f" with Task ID: {task_id} ...in Project {project_name}&nbsp;&nbsp;> <em>No"
                " Profile</em>"
            )
        else:
            task_name += (
                f" ...in Project {project_name}&nbsp;&nbsp;> <em>No Profile</em>"
            )

    # Output the Task's details
    if (not unknown_task) and (
        primary_items["program_arguments"]["display_detail_level"] > 2
    ):  # Only list named Tasks or if details are wanted
        task_output_lines = [task_name]

        # We have the Tasks.  Now let's output them.
        our_task = primary_items["tasker_root_elements"]["all_tasks"][task_id]
        specific_task = tasks.output_task_list(
            primary_items,
            [our_task],
            project_name,
            "",
            task_output_lines,
            found_tasks,
            False,
        )

    return have_heading, specific_task, task_count


# ##################################################################################
# process_tasks: go through all tasks and output them
# ##################################################################################
def process_tasks_not_called_by_profile(
    primary_items: dict,
    projects_with_no_tasks: List,
    found_tasks_list: List[str],
) -> None:
    """
    Go through all tasks and output them
        :param primary_items:  Program registry.  See primitem.py for details.
        :param projects_with_no_tasks: list of Project xml roots for which there are no Tasks
        :param found_tasks_list: list of all Tasks found so far
        :return: nothing
    """
    task_count = 0
    task_name = ""
    have_heading = False
    # We only need twisty for top level, starting with the heading
    save_twisty = primary_items["program_arguments"]["twisty"]
    primary_items["program_arguments"]["twisty"] = False

    # Go through all Tasks, one at a time, and see if this one is not in it (not found)
    for task_id in primary_items["tasker_root_elements"]["all_tasks"]:
        # If we just processed a single task only, then bail out.
        if primary_items["found_named_items"]["single_task_found"]:
            break

        # We have a solo Task not associated to any Profile
        if task_id not in found_tasks_list:
            have_heading, specific_task, task_count = process_solo_task_with_no_profile(
                primary_items,
                task_id,
                found_tasks_list,
                task_count,
                have_heading,
                projects_with_no_tasks,
                save_twisty,
            )
            if specific_task:
                break

    # End the twisty hidden Task list
    if save_twisty:
        remove_twisty(primary_items)

    # Provide spacing and end list if we have Tasks
    if task_count > 0:
        if primary_items["program_arguments"]["display_detail_level"] > 0:
            primary_items["output_lines"].add_line_to_output(
                primary_items, 0, "", FormatLine.dont_format_line
            )  # blank line
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, "", FormatLine.dont_format_line
        )  # Close Task list

    if task_name is True:
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, "", FormatLine.dont_format_line
        )  # Close Task list

    primary_items["output_lines"].add_line_to_output(
        primary_items, 3, "", FormatLine.dont_format_line
    )  # Close out the list
    return
