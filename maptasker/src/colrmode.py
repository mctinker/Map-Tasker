#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# colrmode: set the program colors based on color mode: dark or light                  #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import darkdetect


def set_color_mode(appearance_mode: str) -> dict:
    """
    Given the color mode to use (dark or light), set the colors appropriately
       :param appearance_mode: color mode: dark or light
       :return new colormap of colors to use in the output
    """
    # Deal with "System" color mode
    if appearance_mode == "system":
        mode = "dark" if darkdetect.isDark() else "light"
    else:
        mode = appearance_mode

    # Now set the colors to use based on the appearance mode
    if mode == "dark":
        return {
            "project_color": "White",
            "profile_color": "Aqua",
            "disabled_profile_color": "Red",
            "launcher_task_color": "GreenYellow",
            "task_color": "Yellow",
            "unknown_task_color": "Red",
            "scene_color": "Lime",
            "bullet_color": "White",
            "action_name_color": "Gold",
            "action_color": "DarkOrange",
            "action_label_color": "Magenta",
            "action_condition_color": "PapayaWhip",
            "disabled_action_color": "Crimson",
            "profile_condition_color": "Lavender",
            "background_color": "DarkBlue",
            "trailing_comments_color": "PeachPuff",
            "taskernet_color": "LightPink",
            "preferences_color": "PeachPuff",
            "highlight_color": "DarkTurquoise",
            "heading_color": "LimeGreen",
        }
    else:
        return {
            "project_color": "Black",
            "profile_color": "DarkBlue",
            "disabled_profile_color": "DarkRed",
            "launcher_task_color": "LawnGreen",
            "task_color": "DarkGreen",
            "unknown_task_color": "MediumVioletRed",
            "scene_color": "Purple",
            "bullet_color": "Black",
            "action_color": "DarkSlateGray",
            "action_name_color": "Indigo",
            "action_label_color": "MediumOrchid",
            "action_condition_color": "Brown",
            "disabled_action_color": "IndianRed",
            "profile_condition_color": "DarkSlateGray",
            "background_color": "Lavender",
            "trailing_comments_color": "Tomato",
            "taskernet_color": "RoyalBlue",
            "preferences_color": "DodgerBlue",
            "highlight_color": "Yellow",
            "heading_color": "DarkSlateGray",
        }
