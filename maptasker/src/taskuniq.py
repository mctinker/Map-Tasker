#! /usr/bin/env python3
"""Process Unique Task Situations"""
#                                                                                      #
# taskuniq: deal with unique Tasks                                                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import NO_PROJECT, NORMAL_TAB, FormatLine
from maptasker.src.tasks import (
    get_project_for_solo_task,
    output_task_list,
)
from maptasker.src.twisty import add_twisty, remove_twisty


# Output Projects Without Tasks and Projects Without Profiles
def process_missing_tasks_and_profiles(
    projects_with_no_tasks: list,
    projects_without_profiles: list,
) -> None:
    """
    Output Projects Without Tasks and Projects Without Profiles
        all Tasker xml root elements, and a list of all output lines.
        :param projects_with_no_tasks: root xml entry for list of Projects with no Tasks
        :param projects_without_profiles: root xml entry for list of Projects with no Profiles
        :return: nothing
    """

    # List Projects with no Tasks
    if len(projects_with_no_tasks) > 0 and not PrimeItems.found_named_items["single_task_found"]:
        PrimeItems.output_lines.add_line_to_output(
            1,
            f"{NORMAL_TAB}<hr>{NORMAL_TAB}<em>Projects Without Tasks...</em><br>",
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )

        for item in projects_with_no_tasks:
            PrimeItems.output_lines.add_line_to_output(
                0,
                f"Project {item} has no <em>Named</em> Tasks",
                ["", "trailing_comments_color", FormatLine.add_end_span],
            )
        # End list
        PrimeItems.output_lines.add_line_to_output(
            3,
            "<br>",
            FormatLine.dont_format_line,
        )

    # List all Projects without Profiles
    if projects_without_profiles:
        # Add heading
        PrimeItems.output_lines.add_line_to_output(
            1,
            f"{NORMAL_TAB}<em>Projects Without Profiles...</em><br>",
            ["<br>", "trailing_comments_color", FormatLine.add_end_span],
        )
        for item in projects_without_profiles:
            PrimeItems.output_lines.add_line_to_output(
                0,
                f"- Project '{item}' has no Profiles",
                ["", "trailing_comments_color", FormatLine.add_end_span],
            )
        # End list
        PrimeItems.output_lines.add_line_to_output(
            3,
            "<br>",
            FormatLine.dont_format_line,
        )


# Add heading to output for named Tasks not in any Profile
def add_heading(save_twisty: bool) -> bool:
    """
    Add a header to the output for the solo Tasks

        :param save_twisty: flag to indicate whether or not we are doing the twisty/hidden Tasks
        :return: True...flag that the heading has been created/output
    """

    # Start a list and add a ruler-line across page
    PrimeItems.output_lines.add_line_to_output(1, "<hr>", FormatLine.dont_format_line)
    text_line = f"{NORMAL_TAB}Named Tasks that are not called by any Profile...<br>"

    # Add a twisty, if doing twisties, to hide the line
    if save_twisty:
        add_twisty("trailing_comments_color", text_line)

    # Add the header
    PrimeItems.output_lines.add_line_to_output(
        1,
        text_line,
        ["", "trailing_comments_color", FormatLine.add_end_span],
    )
    PrimeItems.displaying_named_tasks_not_in_profile = True
    PrimeItems.output_lines.add_line_to_output(
        1,
        "",
        FormatLine.dont_format_line,
    )  # Start Task list
    return True


# Process a single Task that does not belong to any Profile
# This function is called recursively
def process_solo_task_with_no_profile(
    task_id: str,
    found_tasks: list,
    task_count: int,
    have_heading: bool,
    projects_with_no_tasks: list,
    save_twisty: bool,
) -> tuple:
    """
    Process a single Task that does not belong to any Profile

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
    project_name, _ = get_project_for_solo_task(
        task_id,
        projects_with_no_tasks,
    )

    # Bump the count of Tasks and get the Task's details
    task_details = ""
    task_count += 1

    # At this point, we've found the Project this Task belongs to,
    # or it doesn't belong to any Profile
    if not have_heading and PrimeItems.program_arguments["display_detail_level"] > 2:
        # Add the heading to the output
        have_heading = add_heading(save_twisty)
    if not unknown_task and project_name != NO_PROJECT:
        if PrimeItems.program_arguments["debug"]:
            task_details += f" with Task ID: {task_id} ...in Project '{project_name}'&nbsp;&nbsp;> <em>No Profile</em>"
        else:
            task_details += f" ...in Project '{project_name}'&nbsp;&nbsp;> <em>No Profile</em>"

    # Output the Task's details
    if (not unknown_task) and (
        PrimeItems.program_arguments["display_detail_level"] > 2
    ):  # Only list named Tasks or if details are wanted.
        task_output_lines = [task_details]  # Return as a list.

        # We have the Tasks.  Now let's output them.
        our_task = PrimeItems.tasker_root_elements["all_tasks"][task_id]
        specific_task = output_task_list(
            [our_task],
            project_name,
            "",
            task_output_lines,
            found_tasks,
            False,
        )

    return have_heading, specific_task, task_count


# process_tasks: go through all tasks and output them
def process_tasks_not_called_by_profile(
    projects_with_no_tasks: list,
    found_tasks_list: list,
) -> None:
    """
    Go through all tasks and output those that are not called by any Profile.
    This is only called if we are not doing a single named item.
        :param projects_with_no_tasks: list of Project xml roots for which there are no Tasks
        :param found_tasks_list: list of all Tasks found so far
        :return: nothing
    """
    task_count = 0
    task_name = ""
    have_heading = False
    # We only need twisty for top level, starting with the heading
    save_twisty = PrimeItems.program_arguments["twisty"]
    PrimeItems.program_arguments["twisty"] = False

    # Go through all Tasks, one at a time, and see if this one is not in it (not found)
    for task_id in PrimeItems.tasker_root_elements["all_tasks"]:
        # If we just processed a single task only, then bail out.
        if PrimeItems.found_named_items["single_task_found"]:
            break

        # We have a solo Task not associated to any Profile
        if task_id not in found_tasks_list:
            # Theoretcally, we should never get here.
            have_heading, specific_task, task_count = process_solo_task_with_no_profile(
                task_id,
                found_tasks_list,
                task_count,
                have_heading,
                projects_with_no_tasks,
                save_twisty,
            )

            if (
                specific_task
                or PrimeItems.program_arguments["single_task_name"]
                == PrimeItems.tasker_root_elements["all_tasks"][task_id]["name"]
            ):
                PrimeItems.found_named_items["single_task_found"] = True
                break

    # End the twisty hidden Task list.  Remove it and restore the setting.
    if save_twisty:
        remove_twisty()
        PrimeItems.program_arguments["twisty"] = save_twisty

    # Provide spacing and end list if we have Tasks
    if task_count > 0:
        if PrimeItems.program_arguments["display_detail_level"] > 0:
            PrimeItems.output_lines.add_line_to_output(
                0,
                "",
                FormatLine.dont_format_line,
            )  # blank line
        PrimeItems.output_lines.add_line_to_output(
            3,
            "",
            FormatLine.dont_format_line,
        )  # Close Task list

    if task_name is True:
        PrimeItems.output_lines.add_line_to_output(
            3,
            "",
            FormatLine.dont_format_line,
        )  # Close Task list

    PrimeItems.output_lines.add_line_to_output(
        3,
        "",
        FormatLine.dont_format_line,
    )  # Close out the list
