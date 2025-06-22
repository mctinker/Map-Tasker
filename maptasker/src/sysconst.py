#! /usr/bin/env python3
"""
Module containing action runner logic.
"""

#                                                                                      #
# sysconst: System constants                                                           #
#                                                                                      #
from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import Enum

import darkdetect

# Global constants
UNNAMED_ITEM = "(Unnamed)"

VERSION = "8.0.4"
MY_VERSION = f"MapTasker version {VERSION}"

MY_LICENSE = "MIT License"
NO_PROJECT = "-none found."
UNNAMED_ITEM = "Unnamed"
TASK_NAME_MAX_LENGTH = 35
COUNTER_FILE = ".MapTasker_RunCount.txt"
OLD_ARGUMENTS_FILE = ".MapTasker_arguments.json"
ARGUMENTS_FILE = "MapTasker_Settings.toml"
FONT_FAMILY = ";font-family:"
CHANGELOG_FILE = ".maptasker_changelog.txt"
CHANGELOG_JSON_FILE = "maptasker_changelog.json"
CHANGELOG_JSON_URL = "https://raw.githubusercontent.com/mctinker/Map-Tasker/Master/maptasker_changelog.json"
KEYFILE = ".maptasker.pkl"
ERROR_FILE = ".maptasker_error.txt"
ANALYSIS_FILE = "MapTasker_Analysis.txt"
DIAGRAM_FILE = "MapTasker_Map.txt"
SYSTEM_SETTINGS_FILE = ".MapTasker_Settings.pkl"

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
    "Unnamed Tasks": "unknown_task_color",
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
    "UnnamedTask": "'unnamed' Tasks",
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
    "ai_apikey_window_position": "API Key Options Window Position",
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
    "guiview": "Use GUI Map",
    "highlight": "Highlight Names",
    "indent": "Indentation Amount",
    "italicize": "Italicize Names",
    "list_unnamed_items": "List Unnamed Items",
    "view_limit": "View Limit",
    "map_window_position": "Last Map Window Position",
    "outline": "Display Configuration Outline",
    "preferences": "Display Tasker Preferences",
    "pretty": "Display Prettier Output",
    "progressbar_window_position": "Last Progressbar Window Position",
    "rerun": "ReRun Program",
    "runtime": "Display Runtime Arguments/Settings",
    "single_profile_name": "Single Profile Name",
    "single_project_name": "Single Project Name",
    "single_task_name": "Single Task Name",
    "tab_to_use": "Tab To Use",
    "task_action_warning_limit": "Task Action Warning Limit",
    "taskernet": "Display TaskerNet Info",
    "tree_window_position": "Last Tree Window Position",
    "twisty": "Hide Task Details under Twisty",
    "underline": "Underline Names",
    "window_position": "Last Window Position",
}

# Window positions etc. that are to be pickled
SYSTEM_ARGUMENTS = [
    "window_position",
    "tree_window_position",
    "diagram_window_position",
    "color_window_position",
    "ai_popup_window_position",
    "ai_analysis_window_position",
    "ai_apikey_window_position",
    "map_window_position",
    "progressbar_window_position",
    "guiview",
    "doing_diagram",
    "rerun",
]

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
pattern13 = (
    r",(?=\S)"  # matches any comma followed by a non-blank character.  e.g. now is,the time, for (catches is,the)
)
# pattern14 = r"(;Configuration Parameter\(s\):)(.*?)<\\"  # Match everything after the label until a '<'
pattern14 = r"(;Configuration Parameter\(s\):)(.*?)<span>"
pattern15 = re.compile("\n")
RE_FONT = re.compile(r"</font>")

clean = re.compile("<.*?>")

icon_pattern = re.compile(
    r"[\U0001F300-\U0001F5FF]|"  # Emoticons, Transport & Map Symbols
    r"[\U0001F600-\U0001F64F]|"  # Emoticons
    r"[\U0001F680-\U0001F6FF]|"  # Transport & Map Symbols
    r"[\U0001F700-\U0001F77F]|"  # Alchemical Symbols
    r"[\U0001F780-\U0001F7FF]|"  # Geometric Shapes Extended
    r"[\U0001F800-\U0001F8FF]|"  # Supplemental Arrows-C
    r"[\U0001F900-\U0001F9FF]|"  # Supplemental Symbols and Pictographs
    r"[\U0001FA00-\U0001FA6F]|"  # Chess Symbols
    r"[\U0001FA70-\U0001FAFF]"  # Symbols and Pictographs Extended-A
    r"[\u4E00-\u9FFF]",  # CJK Unified Ideographs (Simplified Chinese)
)


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

    dont_format_line = []  # noqa: RUF012
    add_end_span = True
    dont_add_end_span = False


# Definitions for defining the output display level.
# Used for calls to addline (lineout.py).  Reference as DISPLAY_DETAIL_LEVEL_summary.value

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
TABLE_BACKGROUND_COLOR = "DarkSteelBlue" if darkdetect.isDark() else "PaleTurquois"
TABLE_BORDER_COLOR = "DarkSlateGrey" if darkdetect.isDark() else "LightGrey"
TABLE_BORDER = f"\n<style> table, td, th {{ padding: 5px; border: 2px solid {TABLE_BORDER_COLOR}; border-radius: 3px; background-color: {TABLE_BACKGROUND_COLOR}; text-align: center;}} </style>"

NOW_TIME = datetime.now()  # noqa: DTZ005

OPENAI_MODELS = [
    "gpt-3.5-turbo",
    "gpt-4o",
    "gpt-4o-latest",
    "gpt-4o-mini",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4.5-preview",
    "o1",
    "o1-mini",
    "o1-pro",
    "o3",
    "o3-mini",
    "04-mini",
]
LLAMA_MODELS = [
    "aya",
    "codegemma",
    "codellama",
    "deepseek-coder",
    "deepseek-coder-v2",
    "deepseek-r1",
    # "deepseek-v3",  # This model is huge!
    "exaone-deep",
    "gemma",
    "gemma2",
    "gemma3",
    "llama2",
    "llama3",
    "llama3.1",
    "llama3.2",
    "llama3.3",
    "mistral",
    "mistral-nemo",
    "phi3",
    "phi4",
    "phi4-mini",
    "qwen",
    "qwen2",
    "qwen2.5-coder",
    "qwen2.5",
    "tinyllama",
]
CLAUDE_MODELS = [
    "claude-3-7-sonnet-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-opus-latest",
    "claude-3-sonnet-20240229",
    "claude-3-sonnet-20240229",
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
]
DEEPSEEK_MODELS = [
    "deepseek-chat",
    "deepseek-reasoner",
]
GEMINI_MODELS = [
    # TODO 1.5 going away in Sept. 24th 2025
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.5-pro",
]
MODEL_GROUPS = {
    "OpenAI": OPENAI_MODELS,
    "Claude": CLAUDE_MODELS,
    "LLAMA": LLAMA_MODELS,
    "DeepSeek": DEEPSEEK_MODELS,
    "Gemini": GEMINI_MODELS,
}

# DFefine the number of Profiles per line in the Diagram view.  Default = 6.
DIAGRAM_PROFILES_PER_LINE = 6

# Number of spaces to substitute &nbsp; for <blanktab> CSS in the output. [spaces, 'pixels']
SPACE_COUNT1 = [16, "155"]
SPACE_COUNT2 = [25, "160"]
SPACE_COUNT3 = [50, "200"]

SCENE_TASK_TYPES = {
    "checkchangeTask": "Check Change",
    "clickTask": "TAP",
    "focuschangeTask": "Focus Change",
    "itemselectedTask": "Item Selected",
    "keyTask": "Key",
    "linkclickTask": "Link",
    "longclickTask": "LONG TAP",
    "mapclickTask": "Map",
    "maplongclickTask": "Long Map",
    "pageloadedTask": "Page Load",
    "strokeTask": "STROKE",
    "valueselectedTask": "Value Selected",
    "videoTask": "Video",
    "itemclickTask": "ITEM TAP",
    "itemlongclickTask": "ITEM LONG TAP",
}

# GUI Tab Names
TAB_NAMES = ["Specific Name", "Colors", "Analyze", "Debug"]
