#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# project: process the project passed in                                                     #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.tasks as tasks
from maptasker.src.frmthtml import format_html
from maptasker.src.getids import get_ids
from maptasker.src.kidapp import get_kid_app
from maptasker.src.profiles import process_profiles
from maptasker.src.scenes import process_project_scenes
from maptasker.src.share import share
from maptasker.src.sysconst import NO_PROFILE
from maptasker.src.taskflag import get_priority
from maptasker.src.twisty import add_twisty
from maptasker.src.twisty import remove_twisty


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_projects_and_their_profiles(
    primary_items: dict,
    found_tasks: list,
    projects_without_profiles: list,
) -> list:
    """
    Go through all Projects, process them and their Profiles and Tasks (and add to our output list)
        :param primary_items: a dictionary containing program runtime arguments, colors to use in output,
      all Tasker xml root elements, and a list of all output lines.
        :param found_tasks: list of Tasks found thus far
        :param projects_without_profiles: list of Projects that don't have any Profiles
        :return: list of Tasks found thus far, with duplicates removed
    """
    our_task_element = ""

    process_projects(
        primary_items,
        projects_without_profiles,
        found_tasks,
        our_task_element,
    )
    primary_items["output_lines"].add_line_to_output(
        primary_items, 3, ""
    )  # Close Project list

    # Return a list of Tasks found thus far with duplicates remove
    # Reference: https://www.pythonmorsels.com/deduplicate-lists/
    return list(dict.fromkeys(found_tasks).keys())


def get_launcher_task(primary_items, project: defusedxml.ElementTree.XML) -> str:
    """
    If Project has a launcher Task, get it
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param project: xml element of Project we are processing
        :return: information related to launcher Task
    """
    launcher_task_info = ""
    share_element = project.find("Share")
    if share_element is not None:
        launcher_task_element = share_element.find("t")
        if launcher_task_element is not None and launcher_task_element.text is not None:
            launcher_task_info = format_html(
                primary_items["colors_to_use"],
                "launcher_task_color",
                "",
                f"[Launcher Task: {launcher_task_element.text}] ",
                True,
            )
    return launcher_task_info


# #############################################################################################
# Process all Tasks in Project that are not referenced by a Profile
# #############################################################################################
def tasks_not_in_profiles(
    primary_items: dict,
    task_ids: list,
    found_tasks: list,
    project_name: str,
) -> None:
    """
    Process all Tasks in Project that are not referenced by a Profile
        :param primary_items: a dictionary containing program runtime arguments, colors to use in output,
            all Tasker xml root elements, and a list of all output lines.
        :param task_ids: List of Task IDs
        :param found_tasks: list of Tasks found thus far
        :param project_name: name of current Project
        :return: none
    """

    # Flag that we have to first put out the "not found" heading
    output_the_heading = True
    have_tasks_not_in_profile = False

    # Go through all Tasks for this Project
    for the_id in task_ids:
        primary_items["named_task_count_total"] = len(task_ids)
        # We have a Task in Project that has yet to be output?
        if the_id not in found_tasks and (
            # not found_items["single_project_found"]
            not primary_items["found_named_items"]["single_profile_found"]
            and not primary_items["found_named_items"]["single_task_found"]
        ):
            # Flag that we have Taks that are not in any Profile, and bump the count
            have_tasks_not_in_profile = True
            primary_items["task_count_no_profile"] = (
                primary_items["task_count_no_profile"] + 1
            )
            # We have a Project's Task that has not yet been output
            our_task_element, our_task_name = tasks.get_task_name(
                primary_items,
                the_id,
                found_tasks,
                [],
                "",
            )
            # We have to remove this Task from found Tasks since it was added by get_task_name
            found_tasks.remove(the_id)

            # Only print the Task header if there are Tasks not found in any Profile, and we are not looking for a
            # single item
            if (
                output_the_heading
                and task_ids
                and not (primary_items["found_named_items"]["single_profile_found"])
                and not (primary_items["found_named_items"]["single_task_found"])
            ):
                # Format the output line
                output_line = (
                    "&nbsp;&nbsp;&nbsp;The following Tasks in Project"
                    f" {project_name} are not in any Profile..."
                )

                # Add the "twisty" to hide the Task details
                if primary_items["program_arguments"]["twisty"]:
                    add_twisty(
                        primary_items,
                        "task_color",
                        output_line,
                    )
                primary_items["output_lines"].add_line_to_output(
                    primary_items,
                    4,
                    format_html(
                        primary_items["colors_to_use"],
                        "task_color",
                        "",
                        output_line,
                        True,
                    ),
                )
                primary_items["output_lines"].add_line_to_output(primary_items, 1, "")
                output_the_heading = False

            # Format the output line
            task_list = [
                f"{our_task_name} <em>(Not referenced by any Profile in Project"
                f" {project_name})</em>"
            ]

            # Output the Task (we don't care about the returned value)
            _ = tasks.output_task(
                primary_items,
                our_task_name,
                our_task_element,
                task_list,
                project_name,
                NO_PROFILE,
                found_tasks,
                True,
            )

    # End the twisty hidden lines if we have Tasks not in any Profile
    if primary_items["program_arguments"]["twisty"]:
        if have_tasks_not_in_profile:
            remove_twisty(primary_items)
        # Add additional </ul> if no Tasks not in any Profile
        else:
            primary_items["output_lines"].add_line_to_output(primary_items, 3, "&nbsp;")

    # Force a line break
    primary_items["output_lines"].add_line_to_output(primary_items, 4, "")
    return


# #############################################################################################
# Add extra info to Project output line as appropriate and then output it.
# #############################################################################################
def get_extra_and_output_project(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    project_name: str,
    launcher_task_info: str,
) -> bool:
    """
    Add extra info to Project output line as appropriate and then output it.
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param project: Project xml element
        :param project_name: name of Project
        :param launcher_task_info: details about (any) launcher Task
        :return: True if we are looking for a single Project and this isn't it.  False otherwise.
    """
    blank = "&nbsp;"

    # See if there is a Kid app and get the Project's priority
    kid_app_info = priority = ""
    if primary_items["program_arguments"]["display_detail_level"] == 3:
        kid_app_info = get_kid_app(project)
        if kid_app_info:
            kid_app_info = format_html(
                primary_items["colors_to_use"], "project_color", "", kid_app_info, True
            )
        priority = get_priority(project, False)

    # Get the name in a format with proper HTML code wrapped around it
    project_name_details = format_html(
        primary_items["colors_to_use"],
        "project_color",
        "",
        f"Project: {project_name}",
        True,
    )

    # Set up the final Project output line and add a "Go to top" hyperlink
    final_project_line = (
        f"{project_name_details} {launcher_task_info}{priority}{kid_app_info}"
    )
    if len(final_project_line) < 70:
        final_project_line = (
            f"{final_project_line}{blank * 20}<a href='#'>Go to top</a>"
        )
    else:
        final_project_line = f"{final_project_line}{blank * 5}<a href='#'>Go to top</a>"

    # Are we looking for a specific Project?
    if primary_items["program_arguments"]["single_project_name"]:
        if project_name != primary_items["program_arguments"]["single_project_name"]:
            return True
        # We found our single Project
        primary_items["found_named_items"]["single_project_found"] = True
        primary_items["output_lines"].refresh_our_output(
            primary_items,
            False,
            final_project_line,
            "",
        )
    else:
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            2,
            final_project_line,
        )
    return False


def setup_summary_counts(primary_items: dict) -> int:
    """
    Initialize summary counters for the Project
        :param primary_items:
        :return:
    """
    # Set up Project counters for summary line
    primary_items["task_count_for_profile"] = 0
    primary_items["scene_count"] = 0
    primary_items["named_task_count_total"] = 0
    primary_items["task_count_unnamed"] = 0
    primary_items["task_count_no_profile"] = 0
    return 0


def summary_counts(primary_items: dict, project_name: str, profile_count: int) -> None:
    """
    Output Project's summary counts
        :param primary_items:
        :param project_name:
        :param profile_count:
    """
    # Get counts for f-strings
    task_count_for_profile = primary_items["task_count_for_profile"]
    named_task_count_total = primary_items["named_task_count_total"]
    task_count_unnamed = primary_items["task_count_unnamed"]
    task_count_no_profile = primary_items["task_count_no_profile"]
    scene_count = primary_items["scene_count"]

    # Accumulate totals for final tally
    primary_items["grand_totals"]["projects"] = (
        primary_items["grand_totals"]["projects"] + 1
    )
    primary_items["grand_totals"]["profiles"] = (
        primary_items["grand_totals"]["profiles"] + profile_count
    )
    primary_items["grand_totals"]["unnamed_tasks"] = (
        primary_items["grand_totals"]["unnamed_tasks"] + task_count_unnamed
    )
    primary_items["grand_totals"]["named_tasks"] = (
        primary_items["grand_totals"]["named_tasks"] + named_task_count_total
    )
    primary_items["grand_totals"]["scenes"] = (
        primary_items["grand_totals"]["scenes"] + scene_count
    )
    # Output the summary line with counts
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        format_html(
            primary_items["colors_to_use"],
            "project_color",
            "",
            (
                f"Project {project_name} has a total of {profile_count} Profiles,"
                f" {task_count_for_profile}  Tasks called by Profiles,"
                f" {task_count_unnamed} unnamed Tasks, {task_count_no_profile} Tasks"
                f" not in any Profile, {named_task_count_total} named Tasks out of"
                f" {task_count_unnamed + named_task_count_total} total Tasks,"
                f" and {scene_count} Scenes<br><br>"
            ),
            True,
        ),
    )


def finish_up(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    project_name: str,
    found_tasks: list,
    our_task_element: defusedxml.ElementTree.XML,
    profile_count: int,
) -> None:
    """
    Output the remaining components related to the Project
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param project: Project XML element
        :param project_name: name of the Project
        :param found_tasks: list of all Tasks found so far
        :param our_task_element: current Task xml; element
        :param profile_count: count of Profiles in this Project
        :return: nothin
    """
    primary_items["output_lines"].add_line_to_output(
        primary_items, 3, ""
    )  # Close Profile list

    # # See if there are Tasks in Project that have no Profile
    if task_ids := get_ids(primary_items, False, project, project_name, []):
        # Process Tasks in Project that are not referenced by a Profile
        tasks_not_in_profiles(
            primary_items,
            task_ids,
            found_tasks,
            project_name,
        )

    # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    if not primary_items["program_arguments"]["single_task_name"]:
        process_project_scenes(
            primary_items,
            project,
            our_task_element,
            found_tasks,
        )

    # Output the Project summary line
    if primary_items["program_arguments"]["display_detail_level"] != 0:
        summary_counts(primary_items, project_name, profile_count)

    # If we are not inserting the twisties, then close the unordered list
    # Twisties screw with the indentation
    if not primary_items["program_arguments"]["twisty"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, ""
        )  # Close Profile list
    return


# #############################################################################################
# Go through all the Projects, get their detail and output it
# #############################################################################################
def process_projects(
    primary_items: dict,
    projects_without_profiles: list,
    found_tasks: list,
    our_task_element: defusedxml.ElementTree.XML,
) -> list:
    """
    Go through all the Projects, get their detail and output it
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param projects_without_profiles: list of Projects with no Profiles
        :param found_tasks: list of Tasks found
        :param our_task_element: xml element of our Task
        :return: nothing
    """

    # Go through each Project in backup file
    for project in primary_items["tasker_root_elements"]["all_projects"]:
        profile_count = setup_summary_counts(primary_items)

        # Don't bother with another Project if we've done a single Task or Profile only
        if (
            primary_items["found_named_items"]["single_task_found"]
            or primary_items["found_named_items"]["single_profile_found"]
        ):
            break
        # Hyperlink name can not have any embedded blanks.  Substitute a dash for each blank
        project_name = project.find("name").text.replace(" ", "_")
        if primary_items["program_arguments"]["directory"]:
            primary_items[
                "directory_item"
            ] = f"project_{project_name}"  # Save name for directory

        # See if there is a Launcher task
        launcher_task_info = get_launcher_task(primary_items, project)

        # Get some extra details and output the Project information
        if get_extra_and_output_project(
            primary_items,
            project,
            project_name,
            launcher_task_info,
        ):
            continue

        # Process any <Share> information from TaskerNet and output it
        if primary_items["program_arguments"]["display_taskernet"]:
            share(primary_items, project)

        # Get all of the Profile <pid> names (e.g. ["102", "509", ...]
        if profile_ids := get_ids(
            primary_items,
            True,
            project,
            project_name,
            projects_without_profiles,
        ):
            # The number of pids represent the number of Profiles
            profile_count = len(profile_ids)

            our_task_element = process_profiles(
                primary_items,
                project,
                project_name,
                profile_ids,
                found_tasks,
            )

            # Go to next Project if we are looking for a specific Profile and didn't find it.
            if (
                primary_items["program_arguments"]["single_profile_name"]
                and not primary_items["found_named_items"]["single_profile_found"]
            ):
                continue  # On to next Project
        else:
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                5,
                format_html(
                    primary_items["colors_to_use"],
                    "profile_color",
                    "",
                    "<em>Project has no Profiles</em>",
                    True,
                ),
            )

        # Now finish the rest of the output for this Project
        finish_up(
            primary_items,
            project,
            project_name,
            found_tasks,
            our_task_element,
            profile_count,
        )

        if (
            primary_items["found_named_items"]["single_project_found"]
            or primary_items["found_named_items"]["single_profile_found"]
            or primary_items["found_named_items"]["single_task_found"]
        ):
            primary_items["output_lines"].add_line_to_output(
                primary_items, 3, ""
            )  # Close Project list
            return found_tasks

    # If we didn't find the single Project, then say so.
    return []
