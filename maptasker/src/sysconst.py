#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# sysconst: System constants                                                           #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import logging
import re

# Global constants
UNKNOWN_TASK_NAME = "Unnamed/Anonymous."
MY_VERSION = "MapTasker version 2.2.0"
MY_LICENSE = "GNU GENERAL PUBLIC LICENSE (Version 3, 29 June 2007)"
NO_PROJECT = "-none found."
COUNTER_FILE = ".MapTasker_RunCount.txt"
ARGUMENTS_FILE = ".MapTasker_arguments.json"
FONT_FAMILY = ";font-family:"
NO_PROFILE = "None or unnamed!"

#  List of color arguments and their names
#  Two different key/value structures in one:
#    1- Used as lookup for color selection in GUI.  E.g. key=Disabled Profiles
#    2- Used as color lookup from runtime parameters.  E.g. DisabledProfile (must follow #1)
#       Only needed for keys that are different between case #1 and case #2
TYPES_OF_COLOR_NAMES = {
    "Projects": "project_color",
    "Project": "project_color",
    "Profiles": "profile_color",
    "Profile": "profile_color",
    "Tasks": "task_color",
    "Task": "task_color",
    "(Task) Actions": "action_color",
    "Action": "action_color",
    "Disabled Profiles": "disabled_profile_color",
    "DisabledProfile": "disabled_profile_color",
    "UnknownTask": "unknown_task_color",
    "DisabledAction": "disabled_action_color",
    "Action Conditions": "action_condition_color",
    "ActionCondition": "action_condition_color",
    "Profile Conditions": "profile_condition_color",
    "ProfileCondition": "profile_condition_color",
    "Launcher Task": "launcher_task_color",
    "LauncherTask": "launcher_task_color",
    "Background": "background_color",
    "Scenes": "scene_color",
    "Scene": "scene_color",
    "Bullets": "bullet_color",
    "Bullet": "bullet_color",
    "Action Labels": "action_label_color",
    "ActionLabel": "action_label_color",
    "Action Names": "action_name_color",
    "ActionName": "action_name_color",
    "TaskerNet Information": "taskernet_color",
    "TaskerNetInfo": "taskernet_color",
    "Tasker Preferences": "preferences_color",
    "Preferences": "preferences_color",
    "Trailing Comments": "trailing_comments_color",
    "TrailingComments": "trailing_comments_color",
    "Highlight": "highlight_color",
    "Heading": "heading_color",
}

# Used to parse arguments
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
    "LauncherTask": "Project's 'launcher' Task",
    "Background": "output background",
    "Scene": "Scenes",
    "Bullet": "list bullets",
    "ActionLabel": "Task action 'labels'",
    "ActionName": "Task action 'names'",
    "TaskerNetInfo": "TaskerNet 'information'",
    "Preferences": "Tasker 'preferences'",
    "TrailingComments": "Trailing Comments",
    "Highlight": "Highlight",
    "Heading": "Heading",
}

# Runtime argument names/keywords that are used throughout the program
ARGUMENT_NAMES = {
    "appearance_mode": "Appearance Mode",
    "backup_file_http": "HTTP Backup File URL",
    "backup_file_location": "Local Backup File Location",
    "bold": "Bold Names",
    "debug": "Debug Mode",
    "directory": "Display Directory",
    "display_detail_level": "Display Level",
    "preferences": "Display Tasker Preferences",
    "conditions": "Display Project/Profile/Task Conditions",
    "taskernet": "Display TaskerNet Info",
    "fetched_backup_from_android": "Fetched backup from Android device",
    "file": "Get backup file named",
    "font": "Font To Use",
    "gui": "GUI Mode",
    "highlight": "Highlight Names",
    "indent": "Indentation Amount",
    "italicize": "Italicize Names",
    "rerun": "ReRun Program",
    "restore": "Restore Settings",
    "runtime": "Display Runtime Arguments/Settings",
    "save": "Save Settings",
    "single_profile_name": "Single Profile Name",
    "single_project_name": "Single Project Name",
    "single_task_name": "Single Task Name",
    "twisty": "Hide Task Details under Twisty",
    "underline": "Underline Names",
}

logger = logging.getLogger("MapTasker")
debug_out = False  # Prints the line to be added to the output
DEBUG_PROGRAM = False
debug_file = "maptasker_debug.log"
debug_file = "maptasker_debug.log"

pattern0 = re.compile(",,")
pattern1 = re.compile(",  ,")
pattern2 = re.compile(" ,")
pattern3 = re.compile("<")
pattern4 = re.compile(">")

pattern5 = re.compile("<ul>")
pattern6 = re.compile("</ul>")
pattern7 = re.compile("<li")
pattern8 = re.compile("<br>")
pattern9 = re.compile("</span></span>")
pattern10 = re.compile("</p></p>")
