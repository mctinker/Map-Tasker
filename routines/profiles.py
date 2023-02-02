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
import xml.etree.ElementTree  # Need for type hints

import routines.tasks as tasks
from routines import condition as condition
from routines.outputl import my_output
from routines.outputl import refresh_our_output
from routines.share import share
from routines.sysconst import NO_PROFILE


# #######################################################################################
# Get a specific Profile's Tasks (maximum of two:entry and exit)
# #######################################################################################
def get_profile_tasks(
    the_profile: xml.etree,
    found_tasks_list: list,
    task_list_output: list,
    program_args: dict,
    all_tasks: dict,
    found_items: dict,
) -> tuple[xml.etree, str]:
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
                task_id, found_tasks_list, task_list_output, task_type, all_tasks
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
    project: xml.etree,
    profile: xml.etree,
    output_list: list,
    program_args: dict,
    colormap: dict,
) -> tuple:
    # Set up html to use
    profile_color_html = (
        '<span style = "color:'
        + colormap["profile_color"]
        + '"</span>'
        + program_args["font_to_use"]
    )
    disabled_profile_html = (
        ' <span style = "color:'
        + colormap["disabled_profile_color"]
        + '"</span>[DISABLED] '
    )
    launcher_task_html = (
        ' <span style = "color:'
        + colormap["launcher_task_color"]
        + '"</span>[Launcher Task] '
        + profile_color_html
    )
    condition_color_html = (
        ' <span style = "color:' + colormap["profile_condition_color"] + '"</span>'
    )
    profile_condition = ""

    # Look for disabled Profile
    limit = profile.find("limit")  # Is the Profile disabled?
    if limit is not None and limit.text == "true":
        disabled = disabled_profile_html
    else:
        disabled = ""
    launcher_xml = project.find(
        "ProfileVariable"
    )  # Is there a Launcher Task with this Project?
    launcher = launcher_task_html if launcher_xml is not None else ""
    profile_name = ""
    if program_args["display_profile_conditions"]:
        profile_condition = condition.parse_profile_condition(
            profile, colormap, program_args
        )  # Get the Profile's condition
        if profile_condition:
            profile_name = f"{condition_color_html} ({profile_condition}) {profile_name}{launcher}{disabled}"

    # Start formulating the Profile output line
    try:
        profile_name = profile.find("nme").text + profile_name  # Get Profile's name
    except Exception as e:  # no Profile name
        if program_args["display_profile_conditions"]:
            profile_condition = condition.parse_profile_condition(
                profile, colormap, program_args
            )  # Get the Profile's condition
            if profile_condition:
                profile_name = (
                    NO_PROFILE
                    + condition_color_html
                    + " ("
                    + profile_condition
                    + ") "
                    + profile_color_html
                    + launcher
                    + disabled
                )
            else:
                profile_name = profile_name + NO_PROFILE + launcher + disabled
        else:
            profile_name = profile_name + NO_PROFILE + launcher + disabled
    if program_args["debug"]:
        profile_id = profile.find("id").text
        profile_name = f"{profile_name} ID:{profile_id}"
    # Output the Profile line
    my_output(
        colormap,
        program_args,
        output_list,
        2,
        f"{profile_color_html}Profile: {profile_name}",
    )
    return limit, launcher, profile_condition, profile_name


# #######################################################################################
# process_projects: go through all Projects Profiles...and output them
# #######################################################################################
def process_profiles(
    output_list: list,
    project: xml.etree,
    project_name: str,
    profile_ids: list,
    list_of_found_tasks: list,
    program_args: dict,
    heading: str,
    colormap: dict,
    all_tasker_items: dict,
    found_items: dict,
) -> object:
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
                refresh_our_output(
                    False,
                    output_list,
                    project_name,
                    "",
                    heading,
                    colormap,
                    program_args,
                )
            except Exception as e:  # no Profile name...go to next Profile ID
                continue
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
        limit, launcher, profile_condition, profile_name = build_profile_line(
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
        )
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
