# ########################################################################################## #
#                                                                                            #
# sysconst: System constants                                                                 #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from config import *
from config import logging

# Global constants
UNKNOWN_TASK_NAME = "Unnamed/Anonymous."
MY_VERSION = "MapTasker version 1.2.0"
MY_LICENSE = "GNU GENERAL PUBLIC LICENSE (Version 3, 29 June 2007)"
NO_PROJECT = "-none found."
COUNTER_FILE = ".MapTasker_RunCount.txt"
ARGUMENTS_FILE = ".arguments.txt"
FONT_TO_USE = f"<font face={OUTPUT_FONT}>"
NO_PROFILE = "None or unnamed!"
HELP_FILE = "https://github.com/mctinker/MapTasker/blob/Version-1.1.1/Help.md"
#  List of color arguments and their names
TYPES_OF_COLOR_NAMES = {
    "Projects": "project_color",
    "Profiles": "profile_color",
    "Tasks": "task_color",
    "(Task) Actions": "action_color",
    "Disabled Profiles": "disabled_profile_color",
    "UnknownTask": "unknown_task_color",
    "DisabledAction": "disabled_action_color",
    "Action Conditions": "action_condition_color",
    "Profile Conditions": "profile_condition_color",
    "Launcher Task": "launcher_task_color",
    "Background": "background_color",
    "Scenes": "scene_color",
    "Bullets": "bullet_color",
    "Action Labels": "action_label_color",
    "Action Names": "action_name_color",
    "TaskerNet Information": "taskernet_color",
}

TYPES_OF_COLORS = {
    "Project": "Projects",
    "Profile": "Profiles",
    "Task": "Tasks",
    "Action": "Task 'actions'",
    "DisabledProfile": "'disabled' Profiles",
    "UnknownTask": "'unknown' Tasks",
    "DisabledAction": "disabled Task 'actions'",
    "ActionCondition": "Task action 'conditions'",
    "ProfileCondition": "Profile 'conditions'",
    "LauncherTask": "Profile's 'launcher' Task",
    "Background": "output background",
    "Scene": "Scenes",
    "Bullet": "list bullets",
    "ActionLabel": "Task action 'labels'",
    "ActionName": "Task action 'names'",
    "TaskerNetInfo": "TaskerNet 'information'",
}

logger = logging.getLogger("MapTasker")
debug_out = False  # Prints the line to be added to the output
debug_program = False
