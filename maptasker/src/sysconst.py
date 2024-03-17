"""Module containing action runner logic."""

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
from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import Enum
from typing import ClassVar

import darkdetect

# Global constants
UNKNOWN_TASK_NAME = "Unnamed/Anonymous."

VERSION = "3.1.5"
MY_VERSION = f"MapTasker version {VERSION}"

MY_LICENSE = "MIT License"
NO_PROJECT = "-none found."
COUNTER_FILE = ".MapTasker_RunCount.txt"
OLD_ARGUMENTS_FILE = ".MapTasker_arguments.json"
ARGUMENTS_FILE = "MapTasker_Settings.toml"
FONT_FAMILY = ";font-family:"
NO_PROFILE = "None or unnamed!"
CHANGELOG_FILE = ".maptasker_changelog.txt"

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
    "android_ipaddr": "Android IP Address",
    "android_file": "Android Backup File location on Android device",
    "android_port": "Android Port Number",
    "appearance_mode": "Appearance Mode",
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
    "outline": "Display Configuration Outline",
    "rerun": "ReRun Program",
    "runtime": "Display Runtime Arguments/Settings",
    "single_profile_name": "Single Profile Name",
    "single_project_name": "Single Project Name",
    "single_task_name": "Single Task Name",
    "twisty": "Hide Task Details under Twisty",
    "underline": "Underline Names",
    "edit": "Edit",
    "edit_type": "Edit Type",
}

# Debug stuff
logger = logging.getLogger("MapTasker")
debug_out = False  # Prints the line to be added to the output
DEBUG_PROGRAM = False
debug_file = "maptasker_debug.log"

# Compiled match patterns reused throughout
pattern0 = re.compile(",,")
pattern1 = re.compile(",  ,")
pattern2 = re.compile(" ,")
pattern3 = re.compile("<")
pattern4 = re.compile(">")

pattern8 = re.compile("<br>")
pattern9 = re.compile("</span></span>")
pattern10 = re.compile("</p></p>")
pattern11 = re.compile(".*[A-Z].*")
pattern12 = re.compile("[%]\w+")  # matches any word-constituent character.   # noqa: W605
RE_FONT = re.compile(r"</font>")

clean = re.compile("<.*?>")


# ASCII Color Definitions
class Colors:
    """Define ANSI color codes for terminal output."""

    White = "\033[0m"
    Yellow = "\033[33m"
    Red = "\033[31m"
    Green = "\033[32m"
    Purple = "\033[35m"
    Blue = "\033[34m"
    BOLD = "\033[1m"


# Used for calls to addline (lineout.py).  Reference as FormatLine.add_end_span.value
class FormatLine(Enum):
    """Definitions for creating an output line in the output list."""

    dont_format_line: ClassVar[list] = []
    add_end_span = True
    dont_add_end_span = False

    """Definitions for defining the output display level."""


DISPLAY_DETAIL_LEVEL_summary: int = 0
DISPLAY_DETAIL_LEVEL_anon_tasks_only: int = 1
DISPLAY_DETAIL_LEVEL_all_tasks: int = 2
DISPLAY_DETAIL_LEVEL_all_parameters: int = 3
DISPLAY_DETAIL_LEVEL_everything: int = 4

# Use the normal tab in output.
NORMAL_TAB = '<span class="normtab"></span>'

# Disabled Profile and Task indicator
DISABLED = " [&#9940;&nbsp;DISABLED]"  # &#9940 = "⛔"

# Set up background color and border for tables
TABLE_BACKGROUND_COLOR = "LightSteelBlue" if darkdetect.isDark() else "DarkTurquoise"
TABLE_BORDER = (
    "\n"
    "<style> \
        table, \
        td, \
        th { \
        padding: 5px; \
        border: 2px solid #1c87c9; \
        border-radius: 3px; \
        background-color: #128198; \
        text-align: center; \
        } \
    </style>"
)


NOW_TIME = datetime.now()  # noqa: DTZ005
