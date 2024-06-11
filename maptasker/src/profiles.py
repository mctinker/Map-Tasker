"""Handle Profile"""

#! /usr/bin/env python3

#                                                                                      #
# profiles: process Profiles for given project                                         #
#                                                                                      #
from __future__ import annotations

from typing import TYPE_CHECKING

from maptasker.src import condition, tasks
from maptasker.src.dirout import add_directory_item

# from maptasker.src.kidapp import get_kid_app
from maptasker.src.format import format_html
from maptasker.src.nameattr import add_name_attribute
from maptasker.src.primitem import PrimeItems
from maptasker.src.property import get_properties
from maptasker.src.share import share
from maptasker.src.sysconst import DISABLED, NO_PROFILE, FormatLine

if TYPE_CHECKING:
    import defusedxml.ElementTree


# Get a specific Profile's Tasks (maximum of two:entry and exit)
def get_profile_tasks(
    the_profile: defusedxml.ElementTree.XML,
    found_tasks_list: list,
    task_output_line: list,
) -> list:
    """
    Get the task element and task name from the profile.

    This function iterates over the XML elements in the profile and extracts
    the task element and task name.
    It counts the task under the profile if it hasn't been counted before.
    It also checks if a single task name is specified and sets a flag if
    the task name matches.

    Args:

        the_profile (defusedxml.ElementTree.XML): The XML profile element.
        found_tasks_list (list): A list of found tasks.
        task_output_line (list): A list of task output lines.

    Returns:
        list: a list containing the task element and name
    """
    keys_we_dont_want = ["cdate", "edate", "flags", "id", "limit"]
    the_task_element, the_task_name = "", ""
    list_of_tasks = []

    for child in the_profile:
        if child.tag in keys_we_dont_want:
            continue
        if "mid" in child.tag:
            # Assume Entry Task, unless tag = 'mid1'...then Exit Task
            task_type = "Entry"
            if child.tag == "mid1":
                task_type = "Exit"
            task_id = child.text
            # Count Task under Profile if it hasn't yet been counted
            if task_id not in found_tasks_list:
                PrimeItems.task_count_for_profile = PrimeItems.task_count_for_profile + 1
            the_task_element, the_task_name = tasks.get_task_name(
                task_id,
                found_tasks_list,
                task_output_line,
                task_type,
            )
            # Add this Task to our list of Tasks processed thus far.
            list_of_tasks.append({"xml": the_task_element, "name": the_task_name})
            if (
                PrimeItems.program_arguments["single_task_name"]
                and PrimeItems.program_arguments["single_task_name"] == the_task_name
            ):
                PrimeItems.found_named_items["single_task_found"] = True
                break
        # If hit Profile's name, we've passed all the Task ids.
        elif child.tag == "nme":
            break
    return list_of_tasks


# Get a specific Profile's name
def get_profile_name(
    profile: defusedxml.ElementTree,
) -> tuple[str, str]:
    """
    Get a specific Profile's name

        :param profile: xml element pointing to the Profile
        :return: Profile name with appropriate html and the profile name itself
    """
    # If we don't have the name, then set it to 'No Profile'
    profile_id = profile.attrib.get("sr")
    profile_id = profile_id[4:]
    if not (the_profile_name := PrimeItems.tasker_root_elements["all_profiles"][profile_id]["name"]):
        the_profile_name = NO_PROFILE

    # Make the Project name bold, italicize, underline and/or highlighted if requested
    altered_profile_name = add_name_attribute(the_profile_name)

    # Add html color and font for Profile name
    profile_name_with_html = format_html(
        "profile_color",
        "",
        f"Profile: {altered_profile_name} ",
        True,
    )

    # If we are debugging, add the Profile ID
    if PrimeItems.program_arguments["debug"]:
        profile_id = profile.find("id").text
        profile_name_with_html = f"{profile_name_with_html} "
        f'{format_html("Red", "", f"ID:{profile_id}", True)}'
    return profile_name_with_html, the_profile_name


# Get the Profile's key attributes: limit, launcher task, run conditions
def build_profile_line(
    project: defusedxml.ElementTree.XML,
    profile: defusedxml.ElementTree.XML,
) -> str:
    """
    Get the Profile's key attributes: limit, launcher task, run conditions and output it

        :param project: the Project xml element
        :param profile: the Profile xml element
        :return: Profile name
    """

    flags = condition_text = ""
    blank = "&nbsp;"

    # Set up HTML to use
    disabled_profile_html = format_html(
        "disabled_profile_color",
        "",
        DISABLED,
        True,
    )
    launcher_task_html = format_html(
        "launcher_task_color",
        "",
        "[Launcher Task]",
        True,
    )

    # Look for disabled Profile
    limit = profile.find("limit")  # Is the Profile disabled?
    disabled = disabled_profile_html if limit is not None and limit.text == "true" else ""

    # Is there a Launcher Task with this Project?
    launcher_xml = project.find("ProfileVariable")
    launcher = launcher_task_html if launcher_xml is not None else ""

    # See if there is a Kid app and/or Priority (FOR FUTURE USE)
    # kid_app_info = ''
    # if program_args["display_detail_level"] > 2:
    #     kid_app_info = get_kid_app(profile)
    #     priority = get_priority(profile, False)

    # Display flags for debug mode
    if PrimeItems.program_arguments["debug"]:
        flags = profile.find("flags")
        flags = format_html("launcher_task_color", "", f" flags: {flags.text}", True) if flags is not None else ""

    # Get the Profile name
    profile_name_with_html, profile_name = get_profile_name(profile)

    # Handle directory hyperlink
    if PrimeItems.program_arguments["directory"]:
        add_directory_item("profiles", profile_name)

    # Get the Profile's conditions
    if PrimeItems.program_arguments["conditions"] or profile_name == "NO_PROFILE":  # noqa: SIM102
        if profile_conditions := condition.parse_profile_condition(profile):
            # Strip pre-existing HTML from conditions, since some condition codes
            # may be same as Actions.
            # And the Actions would have plugged in the action_color HTML.
            # profile_conditions = remove_html_tags(profile_conditions, "")

            # Make the conditions pretty
            if PrimeItems.program_arguments["pretty"]:
                condition_length = profile_conditions.find(":")
                # Add spacing for profile name, condition name and "Profile:"
                profile_conditions = profile_conditions.replace(
                    ",",
                    f"<br>{blank*(len(profile_name)+condition_length+7)}",
                )

            # Add the HTML
            condition_text = format_html(
                "profile_condition_color",
                "",
                f" ({profile_conditions})",
                True,
            )

    # Okay, string it all together
    profile_info = f"{profile_name_with_html} {condition_text} {launcher}{disabled} {flags}"

    # Break it up into separate lines if we are doing pretty output
    if PrimeItems.program_arguments["pretty"]:
        indentation = len(profile_name) + 4
        # Break at comma
        profile_info = profile_info.replace(", ", f"<br>{blank*indentation}")
        # Break at paren
        profile_info = profile_info.replace(" (", f"<br>{blank*indentation}  (")
        # Break at bracket
        profile_info = profile_info.replace(" [", f"<br>{blank*indentation}  [")

    # Output the Profile line
    PrimeItems.output_lines.add_line_to_output(
        2,
        profile_info,
        FormatLine.dont_format_line,
    )
    return profile_name


# Process the Profile passed in.
def do_profile(
    item: defusedxml.ElementTree.XML,
    project: defusedxml.ElementTree.XML,
    project_name: str,
    profile: defusedxml.ElementTree.XML,
    list_of_found_tasks: list,
) -> bool:
    """Function:
        This function searches for a specific Profile and outputs its Tasks.
    Parameters:
        - item (defusedxml.ElementTree.XML): The current item being processed.
        - project (defusedxml.ElementTree.XML): The current project being processed.
        - project_name (str): The name of the current project.
        - profile (defusedxml.ElementTree.XML): The current profile being processed.
        - list_of_found_tasks (list): A list of all found tasks.
    Returns:
        - bool: True if a specific Task is being searched for, False otherwise.
    Processing Logic:
        - Checks if a specific Profile is being searched for.
        - Checks if the current item's name matches the specified Profile name.
        - If a match is found, sets the appropriate flags and clears the output list.
        - Gets the list of Tasks for the current Profile.
        - Outputs the Profile line and its properties.
        - Processes any <Share> information from TaskerNet.
        - Outputs the Tasks for the current Profile.
        - Returns True if a specific Task is being searched for, False otherwise."""
    # Are we searching for a specific Profile?
    if PrimeItems.program_arguments["single_profile_name"]:
        # Make sure this item's name is in our list of profiles.
        if not (profile_name := PrimeItems.tasker_root_elements["all_profiles"][item]["name"]):
            return False  # Not our Profile...go to next Profile ID

        if PrimeItems.program_arguments["single_profile_name"] != profile_name:
            return False  # Not our Profile...go to next Profile ID

            return False  # Not our Profile...go to next Profile ID

        # BINGO! We found the Profile we were looking for!
        # Identify items found.
        PrimeItems.found_named_items["single_profile_found"] = True
        PrimeItems.program_arguments["single_project_name"] = project_name
        PrimeItems.found_named_items["single_project_found"] = True

        # Clear the output list to prepare for single Profile only
        PrimeItems.output_lines.refresh_our_output(
            False,
            project_name,
            "",
        )

        # Start Profile list
        PrimeItems.output_lines.add_line_to_output(1, "", FormatLine.dont_format_line)
    # Get Task xml element and name
    task_output_lines = []  # Profile's Tasks will be filled in here
    list_of_tasks = get_profile_tasks(
        profile,
        list_of_found_tasks,
        task_output_lines,
    )

    # Examine Profile attributes and output Profile line
    profile_name = build_profile_line(
        project,
        profile,
    )

    # Process Profile Properties
    if PrimeItems.program_arguments["display_detail_level"] > 2:
        get_properties("Profile:", profile)

    # Process any <Share> information from TaskerNet
    if PrimeItems.program_arguments["taskernet"]:
        share(profile, "proftab")
        # Add a spacer if detail is 0
        if PrimeItems.program_arguments["display_detail_level"] == 0:
            PrimeItems.output_lines.add_line_to_output(0, "", FormatLine.dont_format_line)

    # We have the Tasks for this Profile.  Now let's output them.
    # Return True = we're looking for a specific Task
    # Return False = this is a normal Task
    return tasks.output_task_list(
        list_of_tasks,
        project_name,
        profile_name,
        task_output_lines,
        list_of_found_tasks,
        True,
    )


# Go through all Projects Profiles...and output them
def process_profiles(
    project: defusedxml.ElementTree.XML,
    project_name: str,
    profile_ids: list,
    list_of_found_tasks: list,
) -> defusedxml.ElementTree:
    """
    Go through Project's Profiles and output each
        all Tasker xml root elements, and a list of all output lines.
        :param project: Project to process
        :param project_name: Project's name
        :param profile_ids: list of Profiles in Project
        :param list_of_found_tasks: list of Tasks found
        :return: xml element of Task
    """

    # Go through the Profiles found in the Project
    for item in profile_ids:
        profile = PrimeItems.tasker_root_elements["all_profiles"][item]["xml"]
        if profile is None:  # If Project has no profiles, skip
            return None
        specific_task = do_profile(item, project, project_name, profile, list_of_found_tasks)

        # Get out if doing a specific Task, and it was found, or not specific task but
        # found speficic Profile.  No need to process any more Profiles.
        if (
            specific_task
            and PrimeItems.program_arguments["single_task_name"]
            and PrimeItems.found_named_items["single_task_found"]
        ) or (
            not specific_task and PrimeItems.found_named_items["single_profile_found"]
        ):  # Get out if we've got the Task we're looking for
            break
        if not specific_task:
            continue

    return ""
