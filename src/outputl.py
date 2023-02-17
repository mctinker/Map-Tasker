#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# outputl: generate the output for a line                                                    #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import xml.etree.ElementTree  # Need for type hints

from maptasker.src.sysconst import FONT_TO_USE
from maptasker.src.sysconst import UNKNOWN_TASK_NAME
from maptasker.src.sysconst import debug_out
from maptasker.src.sysconst import logger
import maptasker.src.actione as action_evaluate


# #######################################################################################
# We're only doing a single Task or Profile.  Clear the Output and start over.
# #######################################################################################
def refresh_our_output(
    include_the_profile: bool,
    output_list: list,
    project_name: str,
    profile_name: str,
    heading: str,
    colormap: dict,
    program_args: dict,
) -> None:
    output_list.clear()
    my_output(colormap, program_args, output_list, 0, FONT_TO_USE + heading)
    my_output(colormap, program_args, output_list, 1, "")  # Start Project list
    my_output(colormap, program_args, output_list, 2, f"Project: {project_name}")
    if include_the_profile:
        my_output(colormap, program_args, output_list, 1, "")  # Start Profile list
        my_output(colormap, program_args, output_list, 2, f"Profile: {profile_name}")
        my_output(colormap, program_args, output_list, 1, "")  # Start Project list
    return


# #############################################################################################
# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
# #############################################################################################
def ulify_list_item(element: xml.etree, colormap: dict, font_to_use: str) -> str:
    list_color = '<li style="color:'

    if element[:7] == "Project":  # Project ========================
        return (
            list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["project_color"]
            + '">'
            + element
            + "</span></li>\n"
        )
    elif element[:7] == "Profile":  # Profile ========================
        return (
            list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["profile_color"]
            + '">'
            + element
            + "</span></li>\n"
        )
    elif (
        element[:5] == "Task:" or "⎯Task:" in element
    ):  # Task or Scene's Task ========================
        return (
            list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["unknown_task_color"]
            + ';">'
            + font_to_use
            + element
            + "</span></li>\n"
            if UNKNOWN_TASK_NAME in element
            else list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["task_color"]
            + '">'
            + font_to_use
            + element
            + "</span></li>\n"
        )
    elif element[:6] == "Scene:":  # Scene
        return (
            list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["scene_color"]
            + '">'
            + element
            + "</span></li>\n"
        )
    elif "Action:" in element:  # Action
        if (
            "Action: ..." in element
        ):  # If this is continued from the previous line, indicate so and ensure proper font
            if element[11:] == "":
                return ""
            tmp = action_evaluate.cleanup_the_result(
                element.replace("Action: ...", "&nbsp;&nbsp;continued >>> ")
            )
            element = tmp
        return (
            list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["action_color"]
            + '">'
            + font_to_use
            + "</font></b>"
            + element
            + "</span></li>\n"
        )
    elif "Label for" in element:  # Action
        return (
            list_color
            + colormap['bullet_color']
            + '" ><span style="color:'
            + colormap["action_color"]
            + '">'
            + element
            + "</span></li>\n"
        )
    elif "TaskerNet " in element:  # TaskerNet
        return (
            '<p style="margin-left:20px; margin-right:50px;">'
            # + "<p>"
            + '<span style="color:'
            + colormap["taskernet_color"]
            + '">'
            + element
            + "</span></p>\n"
            + '<span style="color:'
            + colormap["taskernet_color"]
            + '">'
        )
    else:  # Must be additional item
        return f"<li>{element}" + "</li>\n"


# #############################################################################################
# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
# #############################################################################################
def ulify(element, lvl, colormap, font_to_use):
    # list lvl: 0=heading 1=start list 2=Task/Profile/Scene 3=end list 4=special Task
    string = ""
    match lvl:
        case 0:
            # Heading..............................lvl 0 = heading, 4 = sub-heading
            string = f"<b>{element}" + "</b><br>\n"
        case 1:  # lvl=1 >>> Start list
            string = f"<ul>{element}" + "\n"
        case 2:  # lvl=2 >>> List item
            string = ulify_list_item(element, colormap, font_to_use)
        case 3:  # lvl=3 >>> End list
            string = "</ul>"
        case 4:  # lvl=4 >>> Heading or plain text line
            string = element + "<br>\n"
    return string


# #############################################################################################
# Write line of output
# #############################################################################################
def my_output(colormap, program_args, output_list, list_level, out_string):
    if (
        "Task ID:" in out_string and program_args["debug"] is False
    ):  # Drop ID: nnn since we don't need it anymore
        temp_element = out_string.split("Task ID:")
        out_string = temp_element[0]
    output_list.append(
        ulify(out_string, list_level, colormap, program_args["font_to_use"])
    )
    # Log the generated output if in special debug mode
    if debug_out:
        debug_msg = "out_string:", ulify(
            out_string, list_level, colormap, program_args["font_to_use"]
        )
        logger.debug(debug_msg)
    return
