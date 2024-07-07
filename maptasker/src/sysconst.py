"""Module containing action runner logic."""

#! /usr/bin/env python3

#                                                                                      #
# sysconst: System constants                                                           #
#                                                                                      #
from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import Enum
from typing import ClassVar

import darkdetect

# Global constants
UNKNOWN_TASK_NAME = "Unnamed/Anonymous."

VERSION = "4.2.0"
MY_VERSION = f"MapTasker version {VERSION}"

MY_LICENSE = "MIT License"
NO_PROJECT = "-none found."
COUNTER_FILE = ".MapTasker_RunCount.txt"
OLD_ARGUMENTS_FILE = ".MapTasker_arguments.json"
ARGUMENTS_FILE = "MapTasker_Settings.toml"
FONT_FAMILY = ";font-family:"
NO_PROFILE = "None or unnamed!"
CHANGELOG_FILE = ".maptasker_changelog.txt"
CHANGELOG_JSON_FILE = "maptasker_changelog.json"
CHANGELOG_JSON_URL = "https://raw.githubusercontent.com/mctinker/Map-Tasker/Master/maptasker_changelog.json"
KEYFILE = ".maptasker.key"
ERROR_FILE = ".maptasker_error.txt"
ANALYSIS_FILE = "MapTasker_Analysis.txt"
DIAGRAM_FILE = "MapTasker_Map.txt"

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

# Runtime argument names/keywords that are used throughout the program and meant to be saved.
ARGUMENT_NAMES = {
    "ai_analysis_window_position": "Last Ai Analysis Window Position",
    "ai_analyze": "Analyze AI",
    "ai_apikey": "AI Api Key",
    "ai_model": "AI Model",
    "ai_popup_window_position": "Last Ai Popup Window Position",
    "ai_prompt": "AI Prompt",
    "android_file": "Android Backup File location on Android device",
    "android_ipaddr": "Android IP Address",
    "android_port": "Android Port Number",
    "appearance_mode": "Appearance Mode",
    "bold": "Bold Names",
    "color_window_position": "Last Color Window Position",
    "conditions": "Display Project/Profile/Task Conditions",
    "debug": "Debug Mode",
    "diagram_window_position": "Last Diagram Window Position",
    "directory": "Display Directory",
    "display_detail_level": "Display Level",
    "file": "Get backup file named",
    "font": "Font To Use",
    "gui": "GUI Mode",
    "highlight": "Highlight Names",
    "indent": "Indentation Amount",
    "italicize": "Italicize Names",
    "mapgui": "Use GUI Map",
    "map_window_position": "Last Map Window Position",
    "outline": "Display Configuration Outline",
    "preferences": "Display Tasker Preferences",
    "pretty": "Display Prettier Output",
    "rerun": "ReRun Program",
    "runtime": "Display Runtime Arguments/Settings",
    "single_profile_name": "Single Profile Name",
    "single_project_name": "Single Project Name",
    "single_task_name": "Single Task Name",
    "taskernet": "Display TaskerNet Info",
    "tree_window_position": "Last Tree Window Position",
    "twisty": "Hide Task Details under Twisty",
    "underline": "Underline Names",
    "window_position": "Last Window Position",
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
pattern12 = re.compile(r"[%]\w+")  # matches any word-constituent character.
pattern13 = r",(?=\S)"  # matches any comma folowed by a nonblank charatcer.  e.g. now is,the time, for (catches is,the)
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
DISPLAY_DETAIL_LEVEL_all_variables: int = 4
DISPLAY_DETAIL_LEVEL_everything: int = 5

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

OPENAI_MODELS = ["gpt-3.5-turbo", "gpt-4o", "gpt-4", "gpt-4-turbo"]
LLAMA_MODELS = [
    "llama2",
    "llama3",
    "mistral",
    "gemma",
    "codegemma",
    "phi3",
    "deepseek-coder",
    "qwen",
    "codellama",
    "aya",
]
