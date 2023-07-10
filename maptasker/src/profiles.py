#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# profiles: process Profiles for given project                                               #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import defusedxml.ElementTree  # Need for type hints

import maptasker.src.condition as condition
import maptasker.src.tasks as tasks

# from maptasker.src.kidapp import get_kid_app
from maptasker.src.frmthtml import format_html
from maptasker.src.xmldata import remove_html_tags

from maptasker.src.share import share
from maptasker.src.sysconst import NO_PROFILE


# #######################################################################################
# Get a specific Profile's Tasks (maximum of two:entry and exit)
# #######################################################################################
def get_profile_tasks(
    primary_items: dict,
    the_profile: defusedxml.ElementTree.XML,
    found_tasks_list: list,
    task_output_line: list,
) -> tuple[defusedxml.ElementTree.XML, str]:
    """
    Get the task element and task name from the profile.

    This function iterates over the XML elements in the profile and extracts the task element and task name.
    It counts the task under the profile if it hasn't been counted before.
    It also checks if a single task name is specified and sets a flag if the task name matches.

    Args:
        primary_items (dict): dictionary of the primary items used throughout the module.  See mapit.py for details
        the_profile (defusedxml.ElementTree.XML): The XML profile element.
        found_tasks_list (list): A list of found tasks.
        task_output_line (list): A list of task output lines.

    Returns:
        tuple[defusedxml.ElementTree.XML, str]: A tuple containing the task element and task name.

    """
    keys_we_dont_want = ["cdate", "edate", "flags", "id"]
    the_task_element, the_task_name = "", ""

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
                primary_items["task_count_for_profile"] = (
                    primary_items["task_count_for_profile"] + 1
                )
            the_task_element, the_task_name = tasks.get_task_name(
                primary_items, task_id, found_tasks_list, task_output_line, task_type
            )
            if (
                primary_items["program_arguments"]["single_task_name"]
                and primary_items["program_arguments"]["single_task_name"]
                == the_task_name
            ):
                primary_items["found_named_items"]["single_task_found"] = True
                break
        # If hit Profile's name, we've passed all the Task ids.
        elif child.tag == "nme":
            break
    return the_task_element, the_task_name


# #######################################################################################
# Get a specific Profile's name
# #######################################################################################
def get_profile_name(
    primary_items: dict,
    profile: defusedxml.ElementTree,
) -> tuple[str, str]:
    """
    Get a specific Profile's name
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param profile: xml element pointing to the Profile
        :return: Profile name with appropriate html and the profile name itself
    """
    try:
        the_profile_name = profile.find("nme").text  # Get Profile's name
    except AttributeError:  # no Profile name
        the_profile_name = NO_PROFILE

    # Add html color and font for Profile name
    profile_name_with_html = format_html(
        primary_items["colors_to_use"],
        "profile_color",
        "",
        f"Profile: {the_profile_name} ",
        True,
    )

    # If we are debugging, add the Profile ID
    if primary_items["program_arguments"]["debug"]:
        profile_id = profile.find("id").text
        profile_name_with_html = f'{profile_name_with_html} {format_html(primary_items["colors_to_use"], "Red", "", f"ID:{profile_id}", True)}'
    return profile_name_with_html, the_profile_name


# #######################################################################################
# Get the Profile's key attributes: limit, launcher task, run conditions
# #######################################################################################
def build_profile_line(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    profile: defusedxml.ElementTree.XML,
) -> str:
    """
    Get the Profile's key attributes: limit, launcher task, run conditions and output it
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param project: the Project xml element
        :param profile: the Profile xml element
        :return: Profile name
    """

    flags = condition_text = ""

    # Set up HTML to use
    disabled_profile_html = format_html(
        primary_items["colors_to_use"], "disabled_profile_color", "", "[DISABLED]", True
    )
    launcher_task_html = format_html(
        primary_items["colors_to_use"],
        "launcher_task_color",
        "",
        "[Launcher Task]",
        True,
    )

    # Look for disabled Profile
    limit = profile.find("limit")  # Is the Profile disabled?
    if limit is not None and limit.text == "true":
        disabled = disabled_profile_html
    else:
        disabled = ""

    # Is there a Launcher Task with this Project?
    launcher_xml = project.find("ProfileVariable")
    launcher = launcher_task_html if launcher_xml is not None else ""

    # See if there is a Kid app and/or Priority (FOR FUTURE USE)
    # kid_app_info = ''
    # if program_args["display_detail_level"] == 3:
    #     kid_app_info = get_kid_app(profile)
    #     priority = get_priority(profile, False)

    # Display flags for debug mode
    if primary_items["program_arguments"]["debug"]:
        flags = profile.find("flags")
        if flags is not None:
            flags = format_html(
                primary_items["colors_to_use"],
                "GreenYellow",
                "",
                f" flags: {flags.text}",
                True,
            )
        else:
            flags = ""

    # Get the Profile name
    profile_name_with_html, profile_name = get_profile_name(primary_items, profile)
    primary_items[
        "directory_item"
    ] = f'profile_{profile_name.replace(" ", "_")}'  # Save name for direcctory

    # Get the Profile's conditions
    if (
        primary_items["program_arguments"]["display_profile_conditions"]
        or profile_name == "NO_PROFILE"
    ):
        if profile_conditions := condition.parse_profile_condition(
            primary_items,
            profile,
        ):
            # Strip pre-existing HTML from conmditions, since some condition codes may be same as Actions
            # And the Actions would have plugged in the action_color HTML
            profile_conditions = remove_html_tags(profile_conditions, "")
            condition_text = format_html(
                primary_items["colors_to_use"],
                "profile_condition_color",
                "",
                f" ({profile_conditions})",
                True,
            )

    # Okay, string it all together
    profile_info = (
        f"{profile_name_with_html} {condition_text} {launcher}{disabled} {flags}"
    )

    # Output the Profile line
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        2,
        profile_info,
    )
    return profile_name


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_profiles(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    project_name: str,
    profile_ids: list,
    list_of_found_tasks: list,
) -> defusedxml.ElementTree:
    """
    Go through Project's Profiles and output each
        :param primary_items: a dictionary containing program runtime arguments, colors to use in output,
        all Tasker xml root elements, and a list of all output lines.
        :param project: Project to process
        :param project_name: Project's name
        :param profile_ids: list of Profiles in Project
        :param list_of_found_tasks: list of Tasks found
        :return: xml element of Task
    """

    our_task_element = ""

    # Go through the Profiles found in the Project
    for item in profile_ids:
        profile = primary_items["tasker_root_elements"]["all_profiles"][item]
        if profile is None:  # If Project has no
            return None
        # Are we searching for a specific Profile?
        if primary_items["program_arguments"]["single_profile_name"]:
            try:
                profile_name = profile.find("nme").text
                if (
                    primary_items["program_arguments"]["single_profile_name"]
                    != profile_name
                ):
                    continue  # Not our Profile...go to next Profile ID
                primary_items["found_named_items"]["single_profile_found"] = True
                # Clear the output list to prepare for single Profile only
                primary_items["output_lines"].refresh_our_output(
                    primary_items,
                    False,
                    project_name,
                    "",
                )
                # Start Profile list
                primary_items["output_lines"].add_line_to_output(primary_items, 1, "")
            except AttributeError:  # no Profile name...go to next Profile ID
                continue
        # Get Task xml element and name
        task_list = []  # Profile's Tasks will be filled in here
        our_task_element, our_task_name = get_profile_tasks(
            primary_items,
            profile,
            list_of_found_tasks,
            task_list,
        )

        # Examine Profile attributes and output Profile line
        profile_name = build_profile_line(
            primary_items,
            project,
            profile,
        )

        # Process any <Share> information from TaskerNet
        if primary_items["program_arguments"]["display_taskernet"]:
            share(primary_items, profile)

        # We have the Tasks for this Profile.  Now let's output them.
        # True = we're looking for a specific Task
        # False = this is a normal Task
        specific_task = tasks.output_task(
            primary_items,
            our_task_name,
            our_task_element,
            task_list,
            project_name,
            profile_name,
            list_of_found_tasks,
            True,
        )

        # Get out if doing a specific Task, and it was found
        if (
            specific_task
            and primary_items["program_arguments"]["single_task_name"]
            and primary_items["found_named_items"]["single_task_found"]
            or not specific_task
            and primary_items["found_named_items"]["single_profile_found"]
        ):  # Get out if we've got the Task we're looking for
            break
        elif not specific_task:
            continue

    return our_task_element
