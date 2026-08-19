#! /usr/bin/env python3
"""
Module containing system constants for MapTasker.
"""

#                                                                                      #
# sysconst: System constants                                                           #
#                                                                                      #
from __future__ import annotations

import importlib.metadata
import logging
import re
from datetime import datetime
from enum import Enum

import darkdetect

# Global constants
UNNAMED_ITEM = "(Unnamed)"
VERSION = importlib.metadata.version("maptasker")
MY_VERSION = f"MapTasker version {VERSION}"

MY_LICENSE = "MIT License"
NO_PROJECT = "-none found."
UNNAMED_ITEM = "Unnamed"
TASK_NAME_MAX_LENGTH = 35
COUNTER_FILE = ".MapTasker_RunCount.txt"
ARGUMENTS_FILE = "MapTasker_Settings.toml"
FONT_FAMILY = ";font-family:"
CHANGELOG_FILE = ".maptasker_changelog.txt"
CHANGELOG_URL = "https://raw.githubusercontent.com/mctinker/Map-Tasker/Master/Changelog.md"
KEYFILE = ".maptasker.pkl"
ERROR_FILE = ".maptasker_error.txt"
ANALYSIS_FILE = "MapTasker_Analysis.txt"
HEALTHCHECK_FILE = "MapTasker_HealthCheck.txt"
COMPARE_FILE = "MapTasker_Compare.txt"
VARXREF_FILE = "MapTasker_VarXref.txt"
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
    "ai_analyze": "Analyze AI",
    "ai_apikey": "AI Api Key",
    "ai_model": "AI Model",
    "ai_model_extended_list": "AI Model Extended List",
    "ai_name": "Name of the AI",
    "ai_prompt": "AI Prompt",
    "android_file": "Android Backup File location on Android device",
    "android_ipaddr": "Android IP Address",
    "android_port": "Android Port Number",
    "appearance_mode": "Appearance Mode",
    "bold": "Bold Names",
    "close_tabs_on_exit": "Close Tabs on Exit",
    "open_view_in_new_window": "Open View In New Window",
    "conditions": "Display Project/Profile/Task Conditions",
    "debug": "Debug Mode",
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
    "local_xml_directory": "Default Directory For 'Get Local XML File'",
    "notify_timeout": "Notification Duration",
    "view_limit": "View Limit",
    "preferences": "Display Tasker Preferences",
    "pretty": "Display Prettier Output",
    "profiles_per_line": "Profiles per Line in Diagram View",
    "rerun": "ReRun Program",
    "runtime": "Display Runtime Arguments/Settings",
    "single_profile_name": "Single Profile Name",
    "single_project_name": "Single Project Name",
    "single_scene_name": "Single Scene Name",
    "single_task_name": "Single Task Name",
    "tab_to_use": "Tab To Use",
    "task_action_warning_limit": "Task Action Warning Limit",
    "taskernet": "Display TaskerNet Info",
    "twisty": "Hide Task Details under Twisty",
    "underline": "Underline Names",
    "language": "Language",
}

# Window positions etc. that are to be pickled
SYSTEM_ARGUMENTS = []

# The 'Specific Name' tab's summary line when no single Project/Profile/Task/Scene is being
# filtered on.  Shared so the message built when a selection is cleared and the one shown
# when the tab is redrawn can't drift apart.
ALL_OBJECTS_MESSAGE = "Display all Projects, Profiles, Tasks, and Scenes."

# Arguments that describe what THIS run is doing rather than what the user prefers.  They
# are saved (they are in ARGUMENT_NAMES) but always as the value below, and are forced back
# to it on restore: carrying one into the next session makes the program believe it is in
# the middle of something it is not.  'ai_analyze' is the case in point -- left true, every
# later run thinks an AI analysis is under way and, for instance, stamps "Ai Analysis Run"
# on the output heading (see frontmtr).
TRANSIENT_ARGUMENTS = {"ai_analyze": False}

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

# Styling every <a> we emit has to carry itself, because a link in our output always sits inside a
# color-coded span (e.g. "profile_color", or a TaskerNet description's inline color/decoration) and
# NiceGUI's Map view runs on Tailwind, whose CSS reset is:
#     a { color: inherit; -webkit-text-decoration: inherit; text-decoration: inherit; }
# That hands the anchor the surrounding span's color and its "text-decoration: none", so an
# unstyled link renders identically to the text around it -- still clickable, but with nothing to
# show it is a link. The standalone MapTasker.html file has no Tailwind, so the browser's own link
# styling applies there and the same markup looks fine, which is what makes this easy to miss.
# Shared by the directory hotlinks (dirout.py), the Task warning links (maputils.py) and the links
# embedded in TaskerNet descriptions and Task action labels (format.py).
HOTLINK_STYLE = "color: #3399ff; text-decoration: underline;"

# Set up background color and border for tables
TABLE_BACKGROUND_COLOR = "DarkSteelBlue" if darkdetect.isDark() else "PaleTurquois"
TABLE_BORDER_COLOR = "DarkSlateGrey" if darkdetect.isDark() else "LightGrey"
TABLE_BORDER = f"\n<style> table, td, th {{ padding: 5px; border: 2px solid {TABLE_BORDER_COLOR}; border-radius: 3px; background-color: {TABLE_BACKGROUND_COLOR}; text-align: center;}} </style>"

NOW_TIME = datetime.now()  # noqa: DTZ005

OPENAI_MODELS = [
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.3-Codex",
    "gpt-5.2",
    "gpt-5.2-pro",
    "gpt-5.1",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-pro",
    "gpt-4o",
    "gpt-4o-latest",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o1-mini",
    "o1-pro",
    "o1",
    "o3",
    "o3-pro",
    "o4-mini",
]
LLAMA_MODELS = [
    "aya",
    "codegemma:2b",
    "codellama:latest",
    "deepseek-r1:1.5b",
    # "deepseek-v3",  # This model is huge...404gb!
    # "devstral",     # This model is 14gb!
    "exaone-deep",
    "gemma3:1b",
    "gpt-oss",
    "llama2",
    "llama3.2",
    "llama3.3",
    "minimax-m3",
    "mistral",
    "mistral-nemo",
    "phi3",
    "phi4-mini",
    "qwen3:1:latest",
    "qwen3.5:0.8b",
    "tinyllama",
]
ANTHROPIC_MODELS = [
    "claude-fable-5",
    "claude-haiku-4-5",
    "claude-opus-5",
    "claude-sonnet-5",
]
DEEPSEEK_MODELS = ["deepseek-chat"]
GEMINI_MODELS = [
    "gemini-3.1-pro",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]
MODEL_GROUPS = {
    "OpenAI": OPENAI_MODELS,
    "Anthropic": ANTHROPIC_MODELS,
    "LLAMA": LLAMA_MODELS,
    "DeepSeek": DEEPSEEK_MODELS,
    "Gemini": GEMINI_MODELS,
}

# Define the number of Profiles per line in the Diagram view.  Default = 6.
DIAGRAM_PROFILES_PER_LINE = 6

# How many lines the Map and Diagram views will build before they stop.  Single source of
# truth for the four places that have to agree about it: the runtime-argument defaults, the
# GUI's own initial value, what "Reset Options" restores, and the fallback viewlimit_event
# lands on when it is handed something it cannot parse.
VIEW_LIMIT_DEFAULT = 10000

# How long a GUI notification stays up, in milliseconds; 0 means until dismissed
# Valid values are 0, 1000 (one second), 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, and 10000.
# Must be one of the values in guiwins.NOTIFY_TIMEOUT_CHOICES -- the pulldown has to be able
# to show it.
NOTIFY_TIMEOUT_DEFAULT = 5000

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

# Default GUI Window Dimensions: Width x Height + X_offset + Y_offset (no spaces)
DEFAULT_GUI_WINDOW = "1129x1044+698+145"
