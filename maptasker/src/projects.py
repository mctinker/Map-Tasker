#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# project: process the project passed in                                               #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

import defusedxml.ElementTree  # Need for type hints

from maptasker.src import tasks
from maptasker.src.dirout import add_directory_item
from maptasker.src.format import format_html
from maptasker.src.getids import get_ids
from maptasker.src.globalvr import output_variables
from maptasker.src.kidapp import get_kid_app
from maptasker.src.nameattr import add_name_attribute
from maptasker.src.primitem import PrimeItems
from maptasker.src.profiles import process_profiles
from maptasker.src.property import get_properties
from maptasker.src.scenes import process_project_scenes
from maptasker.src.share import share
from maptasker.src.sysconst import FormatLine
from maptasker.src.taskflag import get_priority
from maptasker.src.twisty import add_twisty, remove_twisty


# ##################################################################################
# process_projects: go through all Projects Profiles...and output them
# ##################################################################################
def process_projects_and_their_profiles(
    found_tasks: list,
    projects_without_profiles: list,
) -> list:
    """
    Go through all Projects, process them and their Profiles and Tasks
    (and add to our output list)
        :param found_tasks: list of Tasks found thus far
        :param projects_without_profiles: list of Projects that don't have any Profiles
        :return: list of Tasks found thus far, with duplicates removed
    """
    our_task_element = ""

    process_projects(
        projects_without_profiles,
        found_tasks,
        our_task_element,
    )
    PrimeItems.output_lines.add_line_to_output(
        3,
        "",
        FormatLine.dont_format_line,
    )  # Close Project list

    # Return a list of Tasks found thus far with duplicates remove
    # Reference: https://www.pythonmorsels.com/deduplicate-lists/
    return list(dict.fromkeys(found_tasks).keys())


# ################################################################################
# Identify and format launcher Task for Project
# ################################################################################
def get_launcher_task(project: defusedxml.ElementTree.XML) -> str:
    """
    If Project has a launcher Task, get it and format it for output
        :param project: xml element of Project we are processing
        :return: information related to launcher Task
    """
    launcher_task_info = ""
    share_element = project.find("Share")
    if share_element is not None:
        launcher_task_element = share_element.find("t")
        if launcher_task_element is not None and launcher_task_element.text is not None:
            launcher_task_info = format_html(
                "launcher_task_color",
                "",
                f"[Launcher Task: {launcher_task_element.text}] ",
                True,
            )
    return launcher_task_info


# ##################################################################################
# Add heading for Tasks that are not in any Profile
# ##################################################################################
def task_not_in_profile_heading(project_name: str):
    """
    Add heading for Tasks that are not in any Profile
        Args:

            project_name (str): Name of the Project we are doing.
    """
    # Format the output line
    output_line = "&nbsp;&nbsp;&nbsp;The following Tasks in Project" f" {project_name} are not in any Profile..."

    # Force a line break before the header
    PrimeItems.output_lines.add_line_to_output(5, "<br>", FormatLine.dont_format_line)

    # Add the "twisty" to hide the Task details
    if PrimeItems.program_arguments["twisty"]:
        add_twisty(
            "task_color",
            output_line,
        )

    # Not doing twisty
    else:
        # Just put out the line with a linebreak
        PrimeItems.output_lines.add_line_to_output(
            0,
            f"<br>{output_line}",
            ["", "task_color", FormatLine.add_end_span],
        )

    # Start an unordered list
    PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)


# ##################################################################################
# Process all of the Tasks in this Project
# ##################################################################################
def do_tasks_in_project(
    task_ids: list,
    project_name: str,
    found_tasks: list,
    output_the_heading: bool,
    have_tasks_not_in_profile: bool,
) -> bool:
    """
    Process all of the Tasks in this Project
        Args:

            task_ids (list): List of Tasks in the Project
            project_name (str): Name of the Project
            found_tasks (list): List of the Tasks found so far
            output_the_heading (bool): True if we need to output the Project heading
            have_tasks_not_in_profile (bool): Trues if there are Tasks not in the current Profile

            return: True if we have Tasks not in any Profile
    """
    for the_id in task_ids:
        PrimeItems.named_task_count_total = len(task_ids)
        # We have a Task in Project that has yet to be output?
        if the_id not in found_tasks and (
            not PrimeItems.found_named_items["single_profile_found"]
            and not PrimeItems.found_named_items["single_task_found"]
        ):
            # Flag that we have Tasks that are not in any Profile, and bump the count\
            have_tasks_not_in_profile = True
            PrimeItems.task_count_no_profile = PrimeItems.task_count_no_profile + 1
            # We have a Project's Task that has not yet been output
            our_task_element, our_task_name = tasks.get_task_name(
                the_id,
                found_tasks,
                [],
                "",
            )
            # We have to remove this Task from found Tasks since it was added
            # by get_task_name
            found_tasks.remove(the_id)

            # Only print the Task header if there are Tasks not found in any Profile,
            # and we are not looking for a single item
            if (
                output_the_heading
                and task_ids
                and not (PrimeItems.found_named_items["single_profile_found"])
                and not (PrimeItems.found_named_items["single_task_found"])
            ):
                task_not_in_profile_heading(project_name)

                output_the_heading = False

            # Format the output line
            task_output_lines = [
                f"{our_task_name}&nbsp;&nbsp;&nbsp;<em>(Not referenced by any Profile in Project"
                f" {project_name})</em>",
            ]

            # Output the Task (we don't care about the returned value)
            our_task = PrimeItems.tasker_root_elements["all_tasks"][the_id]
            tasks.output_task_list(
                [our_task],
                project_name,
                "",
                task_output_lines,
                found_tasks,
                True,
            )

    return have_tasks_not_in_profile


# ##################################################################################
# Process all Tasks in Project that are not referenced by a Profile
# ##################################################################################
def tasks_not_in_profiles(
    task_ids: list,
    found_tasks: list,
    project_name: str,
) -> bool:
    """
    Process all Tasks in Project that are not referenced by a Profile
        :param task_ids: List of Task IDs
        :param found_tasks: list of Tasks found thus far
        :param project_name: name of current Project
        :return: boolean: True=we have Tasks not in the Profile, False: there are no
                            Tasks not in Profile
    """

    # Flag that we have to first put out the "not found" heading
    output_the_heading = True
    have_tasks_not_in_profile = False

    # Go through all Tasks for this Project
    have_tasks_not_in_profile = do_tasks_in_project(
        task_ids,
        project_name,
        found_tasks,
        output_the_heading,
        have_tasks_not_in_profile,
    )

    # End the twisty hidden lines if we have Tasks not in any Profile
    if PrimeItems.program_arguments["twisty"]:
        if have_tasks_not_in_profile:
            remove_twisty()
        # Add additional </ul> if no Tasks not in any Profile
        else:
            PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)

    # Force a line break
    PrimeItems.output_lines.add_line_to_output(0, "", FormatLine.dont_format_line)
    return have_tasks_not_in_profile


# ##################################################################################
# Add extra info to Project output line as appropriate and then output it.
# ##################################################################################
def get_extra_and_output_project(
    project: defusedxml.ElementTree.XML,
    project_name: str,
    launcher_task_info: str,
) -> bool:
    """
    Add extra info to Project output line as appropriate and then output it.

        :param project: Project xml element
        :param project_name: name of Project
        :param launcher_task_info: details about (any) launcher Task
        :return: True if we are looking for a single Project and this isn't it.
        False otherwise.
    """
    blank = "&nbsp;"

    # See if there is a Kid app and get the Project's priority,
    # only if display level is max
    kid_app_info = priority = ""
    if PrimeItems.program_arguments["display_detail_level"] > 2:
        kid_app_info = get_kid_app(project)
        if kid_app_info:
            kid_app_info = format_html("project_color", "", kid_app_info, True)
        priority = get_priority(project, False)

    # Make the Project name bold, italcize and/or highlighted if requested
    project_name_altered = add_name_attribute(project_name)

    # Get the name in a format with proper HTML code wrapped around it
    project_name_details = format_html(
        "project_color",
        "",
        f"Project: {project_name_altered}",
        True,
    )

    # Set up the final Project output line and add a "Go to top" hyperlink
    final_project_line = f"{project_name_details} {launcher_task_info}{priority}{kid_app_info}"
    if len(final_project_line) < 70:
        final_project_line = f"{final_project_line}{blank * 20}<a href='#'>Go to top</a>"
    else:
        final_project_line = f"{final_project_line}{blank * 5}<a href='#'>Go to top</a>"

    # Are we looking for a specific Project?
    if PrimeItems.program_arguments["single_project_name"]:
        if project_name != PrimeItems.program_arguments["single_project_name"]:
            return True
        # We found our single Project
        PrimeItems.found_named_items["single_project_found"] = True
        # Clear the output and just put out our Project.
        PrimeItems.output_lines.refresh_our_output(
            False,
            project_name,
            "",
        )

    # Not looking for single Project.  Go ahead and output it.
    else:
        # Output the final Project text
        PrimeItems.output_lines.add_line_to_output(
            2,
            final_project_line,
            FormatLine.dont_format_line,
        )
    return False


# ##################################################################################
# Initialize out grand total counters
# ##################################################################################
def setup_summary_counts() -> int:
    """
    Initialize summary counters for the Project
        :return: zero
    """
    # Set up Project counters for summary line
    PrimeItems.task_count_for_profile = 0
    PrimeItems.scene_count = 0
    PrimeItems.named_task_count_total = 0
    PrimeItems.task_count_unnamed = 0
    PrimeItems.task_count_no_profile = 0
    return 0


# ##################################################################################
# Output the grand total counters for this Project
# ##################################################################################
def summary_counts(project_name: str, profile_count: int) -> None:
    """
    Output Project's summary counts

        :param project_name: name of the Project
        :param profile_count: number of Profiles under this Project
    """
    # Get counts for f-strings
    task_count_for_profile = PrimeItems.task_count_for_profile
    named_task_count_total = PrimeItems.named_task_count_total
    task_count_unnamed = PrimeItems.task_count_unnamed
    task_count_no_profile = PrimeItems.task_count_no_profile
    scene_count = PrimeItems.scene_count

    # Accumulate totals for final tally
    PrimeItems.grand_totals["projects"] += 1
    PrimeItems.grand_totals["profiles"] += profile_count
    PrimeItems.grand_totals["unnamed_tasks"] += task_count_unnamed
    PrimeItems.grand_totals["named_tasks"] += named_task_count_total
    PrimeItems.grand_totals["scenes"] += scene_count

    # If doing twisties,  prior line is a <ul> and line before that a </ul>,
    # delete the <ul> since there are one too many
    if (
        PrimeItems.program_arguments["twisty"]
        and PrimeItems.output_lines.output_lines[-1][:4] == "<ul>"
        and PrimeItems.output_lines.output_lines[-2][:5] == "</ul>"
    ):
        PrimeItems.output_lines.delete_last_line()

    # Output the summary line with counts
    PrimeItems.output_lines.add_line_to_output(
        5,
        (
            f"Project {project_name} has a total of {profile_count} Profiles,"
            f" {task_count_for_profile}  Tasks called by Profiles,"
            f" {task_count_unnamed} unnamed Tasks, {task_count_no_profile} Tasks"
            f" not in any Profile, {named_task_count_total} named Tasks out of"
            f" {task_count_unnamed + named_task_count_total} total Tasks,"
            f" and {scene_count} Scenes<br><br>"
        ),
        ["", "project_color", FormatLine.add_end_span],
    )


# ##################################################################################
# Output the remaining components related to the Project
# ##################################################################################
def finish_up(
    project: defusedxml.ElementTree.XML,
    project_name: str,
    found_tasks: list,
    our_task_element: defusedxml.ElementTree.XML,
    profile_count: int,
) -> None:
    """
    Output the remaining components related to the Project
        :param project: Project XML element
        :param project_name: name of the Project
        :param found_tasks: list of all Tasks found so far
        :param our_task_element: current Task xml; element
        :param profile_count: count of Profiles in this Project
        :return: nothin
    """

    tasks_not_in_profile = have_scenes = False
    task_ids = []

    # Close Profile list
    PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)

    # Process any Tasks in Project not associated with any Profile
    task_ids = get_ids(False, project, project_name, [])
    tasks_not_in_profile = tasks_not_in_profiles(
        task_ids,
        found_tasks,
        project_name,
    )

    # Find the Scenes for this Project <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    # ...only if not doing a single Task
    have_scenes = process_project_scenes(
        project,
        our_task_element,
        found_tasks,
    )

    # If we don't have Scenes or Tasks that are not in any Profile
    # then start a new ordered list
    if not tasks_not_in_profile and not have_scenes:
        PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)

    # Output the Project's variables
    if PrimeItems.program_arguments["display_detail_level"] == 4:
        output_variables("Project Global Variables", project)

    # Output the Project summary line
    summary_counts(project_name, profile_count)

    # If we are not inserting the twisties, then close the unordered list
    # Twisties screw with the indentation, as well as not having Scenes
    if not PrimeItems.program_arguments["twisty"] and (
        PrimeItems.program_arguments["display_detail_level"] > 0 or not have_scenes
    ):
        PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)  # Close Profile list

    return


# ##################################################################################
# Helper functions to process_projects function, below
# ##################################################################################
# Return the flags for single-task-found and single-profile-found
def is_single_task_or_profile_found() -> bool:
    return PrimeItems.found_named_items["single_task_found"] or PrimeItems.found_named_items["single_profile_found"]


def get_profile_ids(
    project: defusedxml.ElementTree.XML,
    project_name: str,
    projects_without_profiles: list,
) -> list:
    return get_ids(True, project, project_name, projects_without_profiles)


# Return True if we are doing a single Profile and it was not found, False otherwise
def is_single_profile_not_found() -> bool:
    return (
        PrimeItems.program_arguments["single_profile_name"] and not PrimeItems.found_named_items["single_profile_found"]
    )


def add_no_profiles_line_to_output():
    PrimeItems.output_lines.add_line_to_output(
        5,
        "<em>Project has no Profiles</em>",
        ["", "profile_color", FormatLine.add_end_span],
    )


def is_single_project_or_profile_or_task_found() -> bool:
    return (
        PrimeItems.found_named_items["single_project_found"]
        or PrimeItems.found_named_items["single_profile_found"]
        or PrimeItems.found_named_items["single_task_found"]
    )


def add_close_project_list_line_to_output():
    PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# ################################################################################
# Get this Project's details and output them
# ################################################################################
def get_profile_details_and_output(project: str, project_name: str) -> tuple[bool, int, str, bool]:
    """
    Get this Project's details and output them
        Args:
            project_name (str): name of the project

        Returns:
            tuple[bool, int, bool]: True if this is a Task or Profile we want,
                profile count, True if we have the single Project we want.
    """
    # Initialize Project's total counts to zeroes.
    profile_count = setup_summary_counts()

    # Bail if we are doing a single Task/Profile and it was found
    if is_single_task_or_profile_found():
        return True, profile_count, False

    # If doing a directory, save the project name for it
    if PrimeItems.program_arguments["directory"]:
        add_directory_item("projects", project_name)

    # Get any Project launch details
    launcher_task_info = get_launcher_task(project)

    # Check for extra details to include.
    # This comes back as True if we have the specific Project we are looking for.
    have_project_wanted = get_extra_and_output_project(project, project_name, launcher_task_info)

    # Process Project Properties
    if PrimeItems.program_arguments["display_detail_level"] > 2:
        get_properties(
            project,
            "project_color",
        )

    # Process TaskerNet details if requested
    if PrimeItems.program_arguments["taskernet"]:
        share(project)

    return False, profile_count, have_project_wanted


# ################################################################################
# Process all of the Profiles for this Project
# ################################################################################
def process_project_profiles(
    project: defusedxml.ElementTree,
    project_name: str,
    projects_without_profiles: list,
    found_tasks: list,
    our_task_element: defusedxml.ElementTree,
    profile_count: int,
) -> tuple[bool, defusedxml.ElementTree.XML, int]:
    """
    Process all of the Profiles for this Project
        Args:
            project (defusedxml.ElementTree): XML element for the Project we are doing
            project_name (str): Name of the Project we are doing
            projects_without_profiles (list): List of Project XML elements that have
                    no Profiles
            found_tasks (list): list of Tasks found so far
            our_task_element(defusedxml.ElementTree): effectivewly empty for Projects,
                    but needed for Profile processing further down the chain of code
            profile_count(int): count of the number of Profiles for this Project

        Returns:
            tuple[bool, defusedxml.ElementTree.XML, int]: True if no Profiles found,
                False otherwise; our Task XML element, count of Profiles in Project
    """
    # Get the Profile IDs for this Project and process them
    # True if we have Profiles for this Project
    if profile_ids := get_profile_ids(project, project_name, projects_without_profiles):
        profile_count = len(profile_ids)
        our_task_element = process_profiles(project, project_name, profile_ids, found_tasks)

        # Are we searching for a single Profile and it wasn't found (result=True)?
        if is_single_profile_not_found():
            return True, our_task_element, profile_count

    else:
        # Add a line saying "No Profiles Found"
        add_no_profiles_line_to_output()

    return False, our_task_element, profile_count


# ##################################################################################
# Go through all the Projects, get their detail and output it
# ##################################################################################
def process_projects(
    projects_without_profiles: list,
    found_tasks: list,
    our_task_element: defusedxml.ElementTree.XML,
) -> list:
    """
    Go through all the Projects, get their detail and output it

        :param projects_without_profiles: list of Projects with no Profiles
        :param found_tasks: list of Tasks found
        :param our_task_element: xml element of our Task
        :return: nothing
    """

    # Get all variables from XML first.

    # Go through each Project in backup file
    for project_name in PrimeItems.tasker_root_elements["all_projects"]:
        # Point to the Project XML element <Project sr=...>
        project = PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"]

        # Keep track of the Project being processed
        PrimeItems.current_project = PrimeItems.tasker_root_elements["all_projects"][project_name]

        # Get the Project line item details and output them
        (
            single_task_or_profile_found,
            profile_count,
            have_project_wanted,
        ) = get_profile_details_and_output(project, project_name)

        # If we are searching for a specific Project and we found it, then bail out
        # ...but stay in loop to process all the Profiles for this Project
        if have_project_wanted:
            continue

        # Process all of the Profiles for this Project
        (
            single_profile_not_found,
            our_task_element,
            profile_count,
        ) = process_project_profiles(
            project,
            project_name,
            projects_without_profiles,
            found_tasks,
            our_task_element,
            profile_count,
        )

        # Finish the output for this Project
        finish_up(
            project,
            project_name,
            found_tasks,
            our_task_element,
            profile_count,
        )

        # If we are doing a single item and it was found, return the Tasks list
        if is_single_project_or_profile_or_task_found():
            add_close_project_list_line_to_output()
            return found_tasks

    return []
