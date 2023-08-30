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

from maptasker.src.frmthtml import format_html
from maptasker.src.getids import get_ids
from maptasker.src.sysconst import NO_PROFILE

blank = "&nbsp;"


def outline_the_configuration(primary_items: dict) -> None:
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
            5,
            format_html(
                primary_items,
                "project_color",
                "",
                f"Project: {project_name}<br>",
                True,
            ),
        )

        # Get the Profile IDs for this Project and process them
        # True if we have Profiles for this Project
        if profile_ids := get_ids(primary_items, True, project, project_name, []):
            for item in profile_ids:
                profile = primary_items["tasker_root_elements"]["all_profiles"][item]
                try:
                    profile_name = profile.find("nme").text  # Get Profile's name
                except AttributeError:  # no Profile name
                    profile_name = NO_PROFILE

                profile_line = f"{blank*5}{profile_name}<br>"
                primary_items["output_lines"].add_line_to_output(
                    primary_items,
                    5,
                    profile_line,
                )
