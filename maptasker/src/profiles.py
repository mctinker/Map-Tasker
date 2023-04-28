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
from maptasker.src.outputl import my_output
from maptasker.src.outputl import refresh_our_output
from maptasker.src.frmthtml import format_html
from maptasker.src.xmldata import remove_html_tags

from maptasker.src.share import share
from maptasker.src.sysconst import NO_PROFILE


# #######################################################################################
# Get a specific Profile's Tasks (maximum of two:entry and exit)
# #######################################################################################
def get_profile_tasks(
    the_profile: defusedxml.ElementTree.XML,
    found_tasks_list: list,
    task_output_line: list,
    program_args: dict,
    all_tasks: dict,
    found_items: dict,
) -> tuple[defusedxml.ElementTree.XML, str]:
    keys_we_dont_want = ["cdate", "edate", "flags", "id"]
    the_task_element, the_task_name = "", ""

    for child in the_profile:
        if child.tag in keys_we_dont_want:
            continue
        if "mid" in child.tag:
            task_type = "Entry"
            if child.tag == "mid1":
                task_type = "Exit"
            task_id = child.text
            the_task_element, the_task_name = tasks.get_task_name(
                task_id, found_tasks_list, task_output_line, task_type, all_tasks
            )
            if (
                program_args["single_task_name"]
                and program_args["single_task_name"] == the_task_name
            ):
                found_items["single_task_found"] = True
                break
        elif (
            child.tag == "nme"
        ):  # If hit Profile's name, we've passed all the Task ids.
            break
    return the_task_element, the_task_name


# #######################################################################################
# Get the Profile's key attributes: limit, launcher task, run conditions
# #######################################################################################
def build_profile_line(
    project: defusedxml.ElementTree.XML,
    profile: defusedxml.ElementTree.XML,
    output_list: list,
    program_args: dict,
    colormap: dict,
) -> str:
    """
    Get the Profile's key attributes: limit, launcher task, run conditions and output it
        :param project: the Project xml element
        :param profile: the Profile xml element
        :param output_list: the list of output lines built thus far
        :param program_args: runtime arguments
        :param colormap: colors to use in output
        :return: Profile name
    """
    flags = condition_text = ""

    # Set up HTML to use
    disabled_profile_html = format_html(
        colormap, "disabled_profile_color", "", "[DISABLED]", True
    )
    launcher_task_html = format_html(
        colormap, "launcher_task_color", "", "[Launcher Task]", True
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
    if program_args["debug"]:
        flags = profile.find("flags")
        if flags is not None:
            flags = format_html(
                colormap, "GreenYellow", "", f" flags: {flags.text}", True
            )
        else:
            flags = ""

    # Get the Profile's conditions
    if program_args["display_profile_conditions"]:
        if profile_conditions := condition.parse_profile_condition(
            profile, colormap, program_args
        ):
            # Strip pre-existing HTML from conmditions, since some condition codes may be same as Actions
            # And the Actions would have plugged in the action_color HTML
            profile_conditions = remove_html_tags(profile_conditions, "")
            condition_text = format_html(
                colormap,
                "profile_condition_color",
                "",
                f" ({profile_conditions})",
                True,
            )

    # Get the Profile name
    try:
        the_profile_name = profile.find("nme").text  # Get Profile's name
    except AttributeError:  # no Profile name
        the_profile_name = NO_PROFILE

    # Add html color and font for Profile name
    profile_name = format_html(
        colormap, "profile_color", "", f"Profile: {the_profile_name} ", True
    )

    # If we are debugging, add the Profile ID
    if program_args["debug"]:
        profile_id = profile.find("id").text
        profile_name = (
            f'{profile_name} {format_html(colormap, "Yellow", "", f"ID:{profile_id}", True)}'
        )

    # Okay, string it all together
    profile_name = f"{profile_name} {condition_text} {launcher}{disabled} {flags}"

    # Output the Profile line
    my_output(
        colormap,
        program_args,
        output_list,
        2,
        profile_name,
    )
    return the_profile_name


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_profiles(
    output_list: list,
    project: defusedxml.ElementTree.XML,
    project_name: str,
    profile_ids: list,
    list_of_found_tasks: list,
    program_args: dict,
    heading: str,
    colormap: dict,
    all_tasker_items: dict,
    found_items: dict,
) -> defusedxml.ElementTree:
    """
    Go through Project's Profiles and output each
        :param output_list: list of each output line generated so far
        :param project: Project to process
        :param project_name: Project's name
        :param profile_ids: list of Profiles in Project
        :param list_of_found_tasks: list of Tasks found
        :param program_args: runtime arguments
        :param heading: the output heading
        :param colormap: the colors to use in ouput
        :param all_tasker_items: all Tasker Projects/Profiles/Tasks/Scenes
        :param found_items: all "found" items (single Project/Profile/Task) name and flag
        :return: xml element of Task
    """
    our_task_element = ""

    # Go through the Profiles found in the Project
    for item in profile_ids:
        profile = all_tasker_items["all_profiles"][item]
        if profile is None:  # If Project has no
            return None
        # Are we searching for a specific Profile?
        if program_args["single_profile_name"]:
            try:
                profile_name = profile.find("nme").text
                if program_args["single_profile_name"] != profile_name:
                    continue  # Not our Profile...go to next Profile ID
                found_items["single_profile_found"] = True
                # Clear the output list to prepare for single Profile only
                refresh_our_output(
                    False,
                    output_list,
                    project_name,
                    "",
                    heading,
                    colormap,
                    program_args,
                )
                # Start Profile list
                my_output(colormap, program_args, output_list, 1, "")
            except AttributeError:  # no Profile name...go to next Profile ID
                continue
        # Get Task xml element and name
        task_list = []  # Profile's Tasks will be filled in here
        our_task_element, our_task_name = get_profile_tasks(
            profile,
            list_of_found_tasks,
            task_list,
            program_args,
            all_tasker_items["all_tasks"],
            found_items,
        )

        # Examine Profile attributes and output Profile line
        profile_name = build_profile_line(
            project, profile, output_list, program_args, colormap
        )

        # Process any <Share> information from TaskerNet
        if program_args["display_taskernet"]:
            share(profile, colormap, program_args, output_list)

        # We have the Tasks for this Profile.  Now let's output them.
        # True = we're looking for a specific Task
        # False = this is a normal Task
        specific_task = tasks.output_task(
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
            True,
        )

        # Get out if doing a specific Task, and it was found
        if (
            specific_task
            and program_args["single_task_name"]
            and found_items["single_task_found"]
            or not specific_task
            and found_items["single_profile_found"]
        ):  # Get out if we've got the Task we're looking for
            break
        elif not specific_task:
            continue

    return our_task_element
