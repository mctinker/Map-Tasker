#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# outline: Output the Tasker configuration in outline format                           #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import contextlib

import defusedxml.ElementTree  # Need for type hints

from maptasker.src.frmthtml import format_html
from maptasker.src.getids import get_ids
from maptasker.src.profiles import get_profile_tasks
from maptasker.src.sysconst import NO_PROFILE

blank = "&nbsp;"
list_of_found_tasks = []
line = "─"
arrow = f"├{line*3}▶"


# ##################################################################################
# Outline the Scenes under the Project
# ##################################################################################
def outline_scenes(primary_items: dict, project: defusedxml.ElementTree) -> None:
    """_summary_
    Outline the Scenes under the Project
        Args:
            primary_items (dict): program registry.  See primitem.py for details.
            project (defusedxml.ElementTree): xml element tree of the project.
    """

    scene_names = ""
    with contextlib.suppress(Exception):
        scene_names = project.find("scenes").text
    if scene_names != "":
        scene_list = scene_names.split(",")
        arrow_to_use = arrow
        for scene in scene_list:
            # If last Scene for Project, put an elbow in instead of full bracket
            if scene == scene_list[-1]:
                arrow_to_use = arrow_to_use.replace("├", "└")
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                0,
                format_html(
                    primary_items,
                    "scene_color",
                    "",
                    f"{blank*5}{arrow_to_use}{blank*2}Scene: {scene}",
                    True,
                ),
            )


# ##################################################################################
# Given a Project, outline it's Profiles, Tasks and Scenes
# ##################################################################################
def outline_profiles_tasks_scenes(
    primary_items: dict,
    project: defusedxml.ElementTree,
    project_name: str,
    profile_ids: list,
) -> None:
    """_summary_
    Given a Project, outline it's Profiles, Tasks and Scenes
        Args:
            primary_items (dict): program registry.  See primitem.py for details.
            project (defusedxml.ElementTree): The xml head element for the Project we are processing
            project_name (str): name of the Project we are currently outlining
            profile_ids (list): liost of Profiles under this Project
    """

    arrow1 = f"├{line*5}▶"
    # elbow = f"└{line*5}▶"
    # Delete the <ul> inserted by get_ids for Profile
    primary_items["output_lines"].delete_last_line(primary_items)
    for item in profile_ids:
        # Get the Profile element
        profile = primary_items["tasker_root_elements"]["all_profiles"][item][0]
        # Get the Profile name
        if not (
            profile_name := primary_items["tasker_root_elements"]["all_profiles"][item][
                1
            ]
        ):
            profile_name = NO_PROFILE

        profile_line = f"{blank*5}{arrow}{blank*2}Profile: {profile_name}"
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            0,
            format_html(primary_items, "profile_color", "", profile_line, True),
        )

        # Get Tasks for this Profile and output them
        task_output_line = []  # Profile's Tasks will be filled in here

        _ = get_profile_tasks(
            primary_items,
            profile,
            list_of_found_tasks,
            task_output_line,
        )

        # Go through list of Tasks for Profile
        arrow_to_use = arrow1
        # Go through Task's output lines and add arrows as appropriate
        for task_line in task_output_line:
            # If last Task for Profile, put an elbow in instead of full bracket
            if task_line == task_output_line[-1]:
                arrow_to_use = arrow_to_use.replace("├", "└")
            # Get just the name
            task_line = task_line.split("&nbsp;")
            task_line = f"{blank*5}{arrow_to_use}{blank*2}Task: {task_line[0]}"
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                0,
                format_html(primary_items, "task_color", "", task_line, True),
            )

    # Get the Scenes for this Project
    outline_scenes(primary_items, project)


# ##################################################################################
# Start outline beginning with the Projects
# ##################################################################################
def do_the_outline(primary_items: dict) -> None:
    """_summary_
    Start outline beginning with the Projects
        Args:
            primary_items (dict): program registry.  See primitem.py for details.
    """

    for project_item in primary_items["tasker_root_elements"]["all_projects"]:
        # Get the Project XML element
        project = primary_items["tasker_root_elements"]["all_projects"][project_item][0]
        # Get the Project name formatted for the directory hotlink (with +++s)
        project_name = project_item
        # Format Project name
        format_html(
            primary_items,
            "project_color",
            "",
            f"Project: {project_name}",
            True,
        )
        # Output the final Project text
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            0,
            format_html(
                primary_items,
                "project_color",
                "",
                f"{blank*3}Project: {project_name}",
                True,
            ),
        )

        # Get the Profile IDs for this Project and process them
        # True if we have Profiles for this Project
        if profile_ids := get_ids(primary_items, True, project, project_name, []):
            outline_profiles_tasks_scenes(
                primary_items, project, project_name, profile_ids
            )

        # No Profiles for Project
        else:
            # End ordered list since lineout.py added a <ul> for Project
            primary_items["output_lines"].add_line_to_output(primary_items, 3, "")


# ##################################################################################
# Outline the Tasker Configuration
# ##################################################################################
def outline_the_configuration(primary_items: dict) -> None:
    # Start with a ruler line
    primary_items["output_lines"].add_line_to_output(primary_items, 1, "<hr>")

    # Output the directory link
    if primary_items["program_arguments"]["directory"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            5,
            '<a id="configuration_outline"></a>',
        )
    # Output the header
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        0,
        format_html(
            primary_items,
            "trailing_comments_color",
            "",
            "<em>Configuration Outline</em>",
            True,
        ),
    )

    # Go do it!
    do_the_outline(primary_items)

    # End the list
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        3,
        "",
    )
