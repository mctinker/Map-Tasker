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

import maptasker.src.actione as action_evaluate
from maptasker.src.debug import debug1
from maptasker.src.sysconst import FONT_TO_USE
from maptasker.src.sysconst import UNKNOWN_TASK_NAME
from maptasker.src.sysconst import debug_out
from maptasker.src.sysconst import logger


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
    # If debugging, put out our runtime arguments first
    if program_args["debug"]:
        debug1(colormap, program_args, output_list)
    my_output(colormap, program_args, output_list, 1, "")  # Start Project list
    my_output(colormap, program_args, output_list, 2, f"Project: {project_name}")
    if include_the_profile:
        my_output(colormap, program_args, output_list, 1, "")  # Start Profile list
        my_output(colormap, program_args, output_list, 2, f"Profile: {profile_name}")
        my_output(colormap, program_args, output_list, 1, "")  # Start Project list
    return


# #############################################################################################
# Generate an updated output line with HTML style details
# Input is a dictionary containing the requirements:
#  color1 - color to user
#  color2 - optional 2nd color to use
#  color3 - optional thrid color to tack onto end of string
#  is_list - boolean: True= is a list HTML element
#  span - boolean: True= requires a <span> element
#  font - font to use
# #############################################################################################
def put_style(style_details: dict) -> str:
    """
    Add appropriate HTML style tags based on parameters in dictionary passed in
        :param style_details: dictionary
        :return: updated output line with style details added
    """
    line_with_style = ""
    if style_details["is_list"]:
        line_with_style = (
            f'<li style="color:{style_details["color1"]}"><span style="color:'
            f'{style_details["color2"]}{style_details["font"]}>'
            f'{style_details["element"]}</span></li>\n'
        )

    elif style_details["is_taskernet"]:
        line_with_style = (
            '<p style="margin-left:20px;margin-right:50px;"><p style="color:'
            f'{style_details["color2"]}{FONT_TO_USE}>'
            f'{style_details["element"]}</p>\n'
            f'<p style="color:{style_details["color1"]}">'
        )
        line_with_style = line_with_style.replace("<span></span>", "")

    return line_with_style


# #############################################################################################
# Generate the output string based on the input XML <code> passed in
# Returns a formatted string for output based on the input codes
# #############################################################################################
def ulify_list_item(element: xml.etree, colormap: dict, font_to_use: str) -> str:
    if element[:7] == "Project":  # Project ========================
        return put_style(
            style_details={
                "is_list": True,
                "color1": colormap['bullet_color'],
                "color2": colormap["project_color"],
                "font": font_to_use,
                "element": element,
            }
        )
    elif element[:7] == "Profile":  # Profile ========================
        return put_style(
            style_details={
                "is_list": True,
                "color1": colormap['bullet_color'],
                "color2": colormap["profile_color"],
                "font": font_to_use,
                "element": element,
            }
        )
    elif (
        element[:5] == "Task:" or "&#45;&#45;Task:" in element
    ):  # Task or Scene's Task ========================
        return (
            put_style(
                style_details={
                    "is_list": True,
                    "color1": colormap['bullet_color'],
                    "color2": colormap["unknown_task_color"],
                    "font": font_to_use,
                    "element": element,
                }
            )
            if UNKNOWN_TASK_NAME in element
            else put_style(
                style_details={
                    "is_list": True,
                    "color1": colormap['bullet_color'],
                    "color2": colormap["task_color"],
                    "font": font_to_use,
                    "element": element,
                }
            )
        )
    elif element[:6] == "Scene:":  # Scene
        return put_style(
            style_details={
                "is_list": True,
                "color1": colormap['bullet_color'],
                "color2": colormap["scene_color"],
                "font": font_to_use,
                "element": element,
            }
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
        return put_style(
            style_details={
                "is_list": True,
                "color1": colormap['bullet_color'],
                "color2": colormap["action_color"],
                "font": font_to_use,
                "element": element,
            }
        )
    elif "Label for" in element:  # Label
        return put_style(
            style_details={
                "is_list": True,
                "color1": colormap['bullet_color'],
                "color2": colormap["action_label_color"],
                "font": font_to_use,
                "element": element,
            }
        )
    elif "TaskerNet " in element:  # TaskerNet
        return put_style(
            style_details={
                "is_list": False,
                "color1": colormap['bullet_color'],
                "color2": colormap["taskernet_color"],
                "font": font_to_use,
                "element": element,
                "is_taskernet": True,
            }
        )
    else:  # Must be additional item
        return f"<li {element}" + "</li>\n"


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
            if element[:6] == "<html>":
                string = f"{element}" + "<br>\n"
            else:
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
