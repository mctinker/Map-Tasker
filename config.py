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
    profile_color = "LightPink"
    disabled_profile_color = "Red"
    launcher_task_color = "Chartreuse"
    task_color = "PapayaWhip"
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
else:  # White background with dark text colors
    project_color = "Black"  # Refer to the following for valid names: https://htmlcolorcodes.com/color-names/
    profile_color = "Blue"
    disabled_profile_color = "DarkRed"
    launcher_task_color = "LawnGreen"
    task_color = "Green"
    unknown_task_color = "MediumVioletRed"
    scene_color = "Purple"
    bullet_color = "DarkSlateGray"
    action_color = "CornflowerBlue"
    action_name_color = "Indigo"
    action_label_color = "MediumOrchid"
    action_condition_color = "Brown"
    disabled_action_color = "IndianRed"
    profile_condition_color = "DarkSlateGray"
    background_color = "Lavender"
    trailing_comments_color = "Tomato"
# ####################################################################################################
#  END User-modifiable global constants
# ####################################################################################################

# ######################## DO NOT MODIFY ANYTHING BELOW THIS LINE ######################################

logger = logging.getLogger("MapTasker")
debug_out = False  # Prints the line to be added to the output

# Global constants
UNKNOWN_TASK_NAME = "Unnamed/Anonymous."
MY_VERSION = "MapTasker version 1.1.0"
MY_LICENSE = "GNU GENERAL PUBLIC LICENSE (Version 3, 29 June 2007)"
NO_PROJECT = "-none found."
COUNTER_FILE = ".MapTasker_RunCount.txt"
FONT_TO_USE = f"<font face={OUTPUT_FONT}>"
NO_PROFILE = "None or unnamed!"
HELP_FILE = "https://github.com/mctinker/MapTasker/blob/Version-1.1.0/help.md"