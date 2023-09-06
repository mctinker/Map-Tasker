#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# outline: Output an outline of the Tasker configuration                               #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import contextlib
from maptasker.src.frmthtml import format_html
from maptasker.src.getids import get_ids
from maptasker.src.sysconst import NO_PROFILE, UNKNOWN_TASK_NAME
from maptasker.src.profiles import get_profile_tasks

blank = "&nbsp;"
list_of_found_tasks = []


def outline_the_configuration(primary_items: dict) -> None:
    line = "─"
    arrow = f"├{line*3}▶"
    arrow1 = f"├{line*5}▶"
    elbow = f"└{line*5}▶"

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

    for project in primary_items["tasker_root_elements"]["all_projects"]:
        # Get the Project name formatted for the directory hotlink (with +++s)
        project_name = project.find("name").text
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
            # Delete the <ul> inserted by get_ids for Profile
            primary_items["output_lines"].delete_last_line(primary_items)
            for item in profile_ids:
                profile = primary_items["tasker_root_elements"]["all_profiles"][item]
                try:
                    profile_name = profile.find("nme").text  # Get Profile's name
                except AttributeError:  # no Profile name
                    profile_name = NO_PROFILE

                profile_line = f"{blank*5}{arrow}{blank*2}Profile: {profile_name}"
                primary_items["output_lines"].add_line_to_output(
                    primary_items,
                    0,
                    format_html(primary_items, "profile_color", "", profile_line, True),
                )

                # Get Tasks for this Profile and output them
                task_list = []  # Profile's Tasks will be filled in here
                our_task_element, our_task_name = get_profile_tasks(
                    primary_items,
                    profile,
                    list_of_found_tasks,
                    task_list,
                )
                # Go through list of Tasks for Profile
                arrow_to_use = arrow1
                for task_line in task_list:
                    if task_line == task_list[-1]:
                        arrow_to_use = arrow_to_use.replace("├", "└")
                    # Get just the name
                    task_line = task_line.split("<<<")
                    task_line = f"{blank*5}{arrow_to_use}{blank*2}Task: {task_line[0]}"
                    primary_items["output_lines"].add_line_to_output(
                        primary_items,
                        0,
                        format_html(primary_items, "task_color", "", task_line, True),
                    )

            # Get the Scenes for this Project
            scene_names = ""
            with contextlib.suppress(Exception):
                scene_names = project.find("scenes").text
            if scene_names != "":
                scene_list = scene_names.split(",")
                arrow_to_use = arrow
                for scene in scene_list:
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

        # No Profiles for Project
        else:
            # End ordered list since lineout.py added a <ul> for Project
            primary_items["output_lines"].add_line_to_output(primary_items, 3, "")
