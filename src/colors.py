#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# colors: get and set the program colors                                                     #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import string
from maptasker.src.sysconst import TYPES_OF_COLORS
from maptasker.src.sysconst import logger


# #######################################################################################
# Given a list [x,y,z] , print as x y z
# #######################################################################################
def print_list(list_title, the_list):
    line_out = ""
    seperator = ", "
    list_length = len(the_list) - 1
    if list_title:
        print(list_title)
    for item in the_list:
        if the_list.index(item) == list_length:  # Last item in list?
            seperator = ""
        line_out = line_out + item + seperator
    print(line_out)
    return


# #######################################################################################
# Validate the color name provided.  If color name is 'h', simply display all the colors
# #######################################################################################
def validate_color(the_color):
    red_color_names = [
        "IndianRed",
        "LightCoral",
        "Salmon",
        "DarkSalmon",
        "LightSalmon",
        "Crimson",
        "Red",
        "FireBrick",
        "DarkRed",
    ]
    pink_color_names = [
        "Pink",
        "LightPink",
        "HotPink",
        "DeepPink",
        "MediumVioletRed",
        "PaleVioletRed",
    ]
    orange_color_names = [
        "LightSalmon",
        "Coral",
        "Tomato",
        "OrangeRed",
        "DarkOrange",
        "Orange",
    ]
    yellow_color_names = [
        "Gold",
        "Yellow",
        "LightYellow",
        "LemonChiffon",
        "LightGoldenrodYellow",
        "PapayaWhip",
        "Moccasin",
        "PeachPuff",
        "PaleGoldenrod",
        "Khaki",
        "DarkKhaki",
    ]
    purple_color_names = [
        "Lavender",
        "Thistle",
        "Plum",
        "Violet",
        "Orchid",
        "Fuchsia",
        "Magenta",
        "MediumOrchid",
        "MediumPurple",
        "RebeccaPurple",
        "BlueViolet",
        "DarkViolet",
        "DarkOrchid",
        "DarkMagenta",
        "Purple",
        "Indigo",
        "SlateBlue",
        "DarkSlateBlue",
        "MediumSlateBlue",
    ]
    green_color_names = [
        "GreenYellow",
        "Chartreuse",
        "LawnGreen",
        "Lime",
        "LimeGreen",
        "PaleGreen",
        "LightGreen",
        "MediumSpringGreen",
        "SpringGreen",
        "MediumSeaGreen",
        "SeaGreen",
        "ForestGreen",
        "Green",
        "DarkGreen",
        "YellowGreen",
        "OliveDrab",
        "Olive",
        "DarkOliveGreen",
        "MediumAquamarine",
        "DarkSeaGreen",
        "LightSeaGreen",
        "DarkCyan",
        "Teal",
    ]
    blue_color_names = [
        "Aqua",
        "Cyan",
        "LightCyan",
        "PaleTurquoise",
        "Aquamarine",
        "Turquoise",
        "MediumTurquoise",
        "DarkTurquoise",
        "CadetBlue",
        "SteelBlue",
        "LightSteelBlue",
        "PowderBlue",
        "LightBlue",
        "SkyBlue",
        "LightSkyBlue",
        "DeepSkyBlue",
        "DodgerBlue",
        "CornflowerBlue",
        "MediumSlateBlue",
        "RoyalBlue",
        "Blue",
        "MediumBlue",
        "DarkBlue",
        "Navy",
        "MidnightBlue",
    ]
    brown_color_names = [
        "Cornsilk",
        "BlanchedAlmond",
        "Bisque",
        "NavajoWhite",
        "Wheat",
        "BurlyWood",
        "Tan",
        "RosyBrown",
        "SandyBrown",
        "Goldenrod",
        "DarkGoldenrod",
        "Peru",
        "Chocolate",
        "SaddleBrown",
        "Sienna",
        "Brown",
        "Maroon",
    ]
    white_color_names = [
        "White",
        "Snow",
        "HoneyDew",
        "MintCream",
        "Azure",
        "AliceBlue",
        "GhostWhite",
        "WhiteSmoke",
        "SeaShell",
        "Beige",
        "OldLace",
        "FloralWhite",
        "Ivory",
        "AntiqueWhite",
        "Linen",
        "LavenderBlush",
        "MistyRose",
    ]
    gray_color_names = [
        "Gainsboro",
        "LightGray",
        "Silver",
        "DarkGray",
        "Gray",
        "DimGray",
        "LightSlateGray",
        "SlateGray",
        "DarkSlateGray",
        "Black",
    ]
    any_color = ["hex value.  Example 'db29ff'"]

    all_colors = (
        red_color_names
        + pink_color_names
        + orange_color_names
        + yellow_color_names
        + purple_color_names
        + green_color_names
        + blue_color_names
        + brown_color_names
        + white_color_names
        + gray_color_names
        + any_color
    )

    if the_color != "h":
        logger.debug(the_color in all_colors)
        #  Test for hexdigits
        if all(c in string.hexdigits for c in the_color):
            return True
        # Return True/False based on whether it is in our named colors
        return the_color in all_colors
    print_list("\nRed color names:", red_color_names)
    print_list("\nPink color names:", pink_color_names)
    print_list("\nOrange color names:", orange_color_names)
    print_list("\nYellow color names:", yellow_color_names)
    print_list("\nPurple color names:", purple_color_names)
    print_list("\nGreen color names:", green_color_names)
    print_list("\nBlue color names:", blue_color_names)
    print_list("\nBrown color names:", brown_color_names)
    print_list("\nWhite color names:", white_color_names)
    print_list("\nGray color names:", gray_color_names)
    print_list("\nAny color:", any_color)
    exit(0)


# #######################################################################################
# Get the runtime option for a color change and set it
# #######################################################################################
def get_and_set_the_color(the_arg, colormap):
    the_color_option = the_arg[2:].split("=")
    color_type = the_color_option[0]
    if len(the_color_option) < 2:  # Do we have the second parameter?
        handle_error(
            f"{the_arg} has an invalid 'color'.  See the help (-ch)!", " Exit code 7", 7
        )
    if color_type not in TYPES_OF_COLORS:
        handle_error(
            f"{color_type} is an invalid type for 'color'.  See the help (-h)!",
            " Exit code 7",
            7,
        )
    desired_color = the_color_option[1]
    logger.debug(f" desired_color:{desired_color}")
    if validate_color(desired_color):  # If the color provided is valid...
        match color_type:
            case "Project":
                colormap["project_color"] = desired_color
            case "Profile":
                colormap["profile_color"] = desired_color
            case "Task":
                colormap["task_color"] = desired_color
            case "Action":
                colormap["action_color"] = desired_color
            case "DisabledProfile":
                colormap["disabled_profile_color"] = desired_color
            case "UnknownTask":
                colormap["unknown_task_color"] = desired_color
            case "DisabledAction":
                colormap["disabled_action_color"] = desired_color
            case "ActionCondition":
                colormap["action_condition_color"] = desired_color
            case "ActionName":
                colormap["action_name_color"] = desired_color
            case "ProfileCondition":
                colormap["profile_condition_color"] = desired_color
            case "LauncherTask":
                colormap["launcher_task_color"] = desired_color
            case "Background":
                colormap["background_color"] = desired_color
            case "Scene":
                colormap["scene_color"] = desired_color
            case "Bullet":
                colormap["bullet_color"] = desired_color
            case "ActionLabel":
                colormap["action_label_color"] = desired_color
            case "TaskerNetInfo":
                colormap["taskernet_color"] = desired_color
            case "Preferences":
                colormap["preferences_color"] = desired_color
            case _:
                error_msg = f"Invalid name in arg: =cName, where name is:{desired_color} color_type:{color_type}"
                handle_error(error_msg, " exit code 1", 1)
    else:
        error_msg = (
            f"Invalid color specified: {desired_color} for 'c{the_color_option[0]}'!"
        )
        handle_error(error_msg, " exit code 7", 7)
    return


def handle_error(error_msg, arg1, arg2):
    logger.debug(f"{error_msg}{arg1}")
    print(error_msg)
    exit(arg2)
