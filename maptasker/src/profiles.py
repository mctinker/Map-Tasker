#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# profiles: process Profiles for given project                                         #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import defusedxml.ElementTree  # Need for type hints

import maptasker.src.condition as condition
import maptasker.src.tasks as tasks
from maptasker.src.dirout import add_directory_item

# from maptasker.src.kidapp import get_kid_app
from maptasker.src.frmthtml import format_html
from maptasker.src.nameattr import add_name_attribute
from maptasker.src.property import get_properties
from maptasker.src.share import share
from maptasker.src.sysconst import NO_PROFILE
from maptasker.src.xmldata import remove_html_tags


# ##################################################################################
# Get a specific Profile's Tasks (maximum of two:entry and exit)
# ##################################################################################
def get_profile_tasks(
    primary_items: dict,
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
        :param primary_items:  Program registry.  See primitem.py for details.
        the_profile (defusedxml.ElementTree.XML): The XML profile element.
        found_tasks_list (list): A list of found tasks.
        task_output_line (list): A list of task output lines.

    Returns:
        list: a list containing the task element and name

    """
    keys_we_dont_want = ["cdate", "edate", "flags", "id"]
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
                primary_items["task_count_for_profile"] = (
                    primary_items["task_count_for_profile"] + 1
                )
            the_task_element, the_task_name = tasks.get_task_name(
                primary_items, task_id, found_tasks_list, task_output_line, task_type
            )
            list_of_tasks.append([the_task_element, the_task_name])
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
    return list_of_tasks


# ##################################################################################
# Get a specific Profile's name
# ##################################################################################
def get_profile_name(
    primary_items: dict,
    profile: defusedxml.ElementTree,
) -> tuple[str, str]:
    """
    Get a specific Profile's name
        :param primary_items:  program registry.  See primitem.py for details.
        :param profile: xml element pointing to the Profile
        :return: Profile name with appropriate html and the profile name itself
    """
    # If we don't have the name, then set it to 'No Profile'
    profile_id = profile.attrib.get("sr")
    profile_id = profile_id[4:]
    if not (
        the_profile_name := primary_items["tasker_root_elements"][
            "all_profiles"
        ][profile_id][1]
    ):
        the_profile_name = NO_PROFILE

    # Make the Project name bold, italicize, underline and/or highlighted if requested
    altered_profile_name = add_name_attribute(primary_items, the_profile_name)

    # Add html color and font for Profile name
    profile_name_with_html = format_html(
        primary_items,
        "profile_color",
        "",
        f"Profile: {altered_profile_name} ",
        True,
    )

    # If we are debugging, add the Profile ID
    if primary_items["program_arguments"]["debug"]:
        profile_id = profile.find("id").text
        profile_name_with_html = f"{profile_name_with_html} "
        f'{format_html(primary_items, "Red", "", f"ID:{profile_id}", True)}'
    return profile_name_with_html, the_profile_name


# ##################################################################################
# Get the Profile's key attributes: limit, launcher task, run conditions
# ##################################################################################
def build_profile_line(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    profile: defusedxml.ElementTree.XML,
) -> str:
    """
    Get the Profile's key attributes: limit, launcher task, run conditions and output it
        :param primary_items:  program registry.  See primitem.py for details.
        :param project: the Project xml element
        :param profile: the Profile xml element
        :return: Profile name
    """

    flags = condition_text = ""

    # Set up HTML to use
    disabled_profile_html = format_html(
        primary_items,
        "disabled_profile_color",
        "",
        "[DISABLED]",
        True,
    )
    launcher_task_html = format_html(
        primary_items,
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
                primary_items,
                "GreenYellow",
                "",
                f" flags: {flags.text}",
                True,
            )
        else:
            flags = ""

    # Get the Profile name
    profile_name_with_html, profile_name = get_profile_name(primary_items, profile)

    # Handle directory hyperlink
    if primary_items["program_arguments"]["directory"]:
        add_directory_item(primary_items, "profiles", profile_name)

    # Get the Profile's conditions
    if primary_items["program_arguments"]["conditions"] or profile_name == "NO_PROFILE":
        if profile_conditions := condition.parse_profile_condition(
            primary_items,
            profile,
        ):
            # Strip pre-existing HTML from conmditions, since some condition codes
            # may be same as Actions.
            # And the Actions would have plugged in the action_color HTML.
            profile_conditions = remove_html_tags(profile_conditions, "")
            condition_text = format_html(
                primary_items,
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


# ##################################################################################
# Go through all Projects Profiles...and output them
# ##################################################################################
def process_profiles(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    project_name: str,
    profile_ids: list,
    list_of_found_tasks: list,
) -> defusedxml.ElementTree:
    """
    Go through Project's Profiles and output each
        :param primary_items: a dictionary containing program runtime arguments,
                colors to use in output,
        all Tasker xml root elements, and a list of all output lines.
        :param project: Project to process
        :param project_name: Project's name
        :param profile_ids: list of Profiles in Project
        :param list_of_found_tasks: list of Tasks found
        :return: xml element of Task
    """

    # Go through the Profiles found in the Project
    for item in profile_ids:
        profile = primary_items["tasker_root_elements"]["all_profiles"][item][0]
        if profile is None:  # If Project has no profiles, skip
            return None

        # Are we searching for a specific Profile?
        if primary_items["program_arguments"]["single_profile_name"]:
            if not (
                profile_name := primary_items["tasker_root_elements"]["all_profiles"][
                    item
                ][1]
            ):
                continue

            if (
                primary_items["program_arguments"]["single_profile_name"]
                != profile_name
            ):
                continue  # Not our Profile...go to next Profile ID

            # BINGO! We found the Profile we were looking for!
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
        # Get Task xml element and name
        task_output_lines = []  # Profile's Tasks will be filled in here
        list_of_tasks = get_profile_tasks(
            primary_items,
            profile,
            list_of_found_tasks,
            task_output_lines,
        )

        # Examine Profile attributes and output Profile line
        profile_name = build_profile_line(
            primary_items,
            project,
            profile,
        )

        # Process Project Properties
        if primary_items["program_arguments"]["display_detail_level"] == 3:
            get_properties(
                primary_items, profile, primary_items["colors_to_use"]["profile_color"]
            )

        # Process any <Share> information from TaskerNet
        if primary_items["program_arguments"]["taskernet"]:
            share(primary_items, profile)
            # Add a spacer if detail is 0
            if primary_items["program_arguments"]["display_detail_level"] == 0:
                primary_items["output_lines"].add_line_to_output(primary_items, 0, "")

        # We have the Tasks for this Profile.  Now let's output them.
        # True = we're looking for a specific Task
        # False = this is a normal Task
        if primary_items["program_arguments"]["display_detail_level"] != 0:
            specific_task = tasks.output_task_list(
                primary_items,
                list_of_tasks,
                project_name,
                profile_name,
                task_output_lines,
                list_of_found_tasks,
                True,
            )
            
        else:
            specific_task = False

        # Get out if doing a specific Task, and it was found
        if (
            specific_task
            and primary_items["program_arguments"]["single_task_name"]
            and primary_items["found_named_items"]["single_task_found"]
        ) or (
            not specific_task
            and primary_items["found_named_items"]["single_profile_found"]
        ):  # Get out if we've got the Task we're looking for
            break
        elif not specific_task:
            continue

    return ""
