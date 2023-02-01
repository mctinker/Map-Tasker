# ########################################################################################## #
#                                                                                            #
# config: Configuration file for MapTasker                                                   #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import logging

# Add the following statement to your Terminal Shell configuration file (BASH, Fish, etc.
#  to eliminate the runtime msg: DEPRECATION WARNING: The system version of Tk is deprecated and may be removed...
#  'export TK_SILENCE_DEPRECATION = 1' (without quotes)


# ####################################################################################################
#  START User-modifiable global constants
# ####################################################################################################
CONTINUE_LIMIT = 50  # Define the maximum number of Action lines to continue to avoid runaway for huge binary files
# Monospace fonts work best for if/then/else/end indentation alignment
OUTPUT_FONT = "Courier"  # OS X Default monospace font
# OUTPUT_FONT = 'Roboto Regular'    # Google monospace font
GUI = False  # Graphical User Interface (True) vs. CLI Command Line Interface (False)
DARK_MODE = True  # Light vs Dark Mode
# Set the default colors to use

if DARK_MODE:  # Dark background with light text colors
    project_color = "White"  # Refer to the following for valid names: https://htmlcolorcodes.com/color-names/
    profile_color = "Aqua"
    disabled_profile_color = "Red"
    launcher_task_color = "Chartreuse"
    task_color = "Lavender"
    unknown_task_color = "Red"
    scene_color = "Lime"
    bullet_color = "Black"
    action_name_color = "PaleGoldenrod"
    action_color = "DarkOrange"
    action_label_color = "Magenta"
    action_condition_color = "PapayaWhip"
    disabled_action_color = "Crimson"
    profile_condition_color = "Turquoise"
    background_color = "DarkSlateGray"
    trailing_comments_color = "LightSeaGreen"
    taskernet_color = "LightPink"

else:  # White background with dark text colors
    project_color = "Black"  # Refer to the following for valid names: https://htmlcolorcodes.com/color-names/
    profile_color = "DarkBlue"
    disabled_profile_color = "DarkRed"
    launcher_task_color = "LawnGreen"
    task_color = "DarkGreen"
    unknown_task_color = "MediumVioletRed"
    scene_color = "Purple"
    bullet_color = "DarkSlateGray"
    action_color = "DarkSlateGray"
    action_name_color = "Indigo"
    action_label_color = "MediumOrchid"
    action_condition_color = "Brown"
    disabled_action_color = "IndianRed"
    profile_condition_color = "DarkSlateGray"
    background_color = "Lavender"
    trailing_comments_color = "Tomato"
    taskernet_color = "RoyalBlue"


# ####################################################################################################
#  END User-modifiable global constants
# ####################################################################################################
