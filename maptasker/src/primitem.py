"""Prime items which are used throughout MapTasker (globals)."""

#! /usr/bin/env python3

#                                                                                      #
# primitem = intialize PrimeItems which are used throughout MapTasker (globals).       #
#                                                                                      #
# complete source code of licensed works and modifications which include larger works  #
# using a licensed work under the same license. Copyright and license notices must be  #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# Primary Items = global variables used throughout MapTasker
#
# Set up an initial empty dictionary of primary items used throughout this project
#  xml_tree = main xml element of our Tasker xml tree
#  xml_root = root xml element of our Tasker xml tree
#  program_arguments = runtime arguments entered by user and parsed.
#    See initparg.py for details.
#  colors_to_use = colors to use in the output
#  tasker_root_elements = root elements for all Projects/Profiles/Tasks/Scenes
#  output_lines = class for all lines added to output thus far
#  found_named_items = names/found-flags for single (if any) Project/Profile/Task
#  file_to_get = file object/name of Tasker backup file to read and parse
#  grand_totals = Total count of Projects/Profiles/Named Tasks Unnamed Task etc.
#  task_count_for_profile = number of Tasks in the specific Profile for Project
#    being processed
#  named_task_count_total = number of named Tasks for Project being processed
#  task_count_unnamed = number of unnamed Tasks for Project being processed
#  task_count_no_profile = number of Profiles in Project being processed.
#  directory_items = if displaying a directory then this is a dictionary of items
#    for the directory
#  name_list = list of names of Projects/Profiles/Tasks/Scenes found thus far
#  displaying_named_tasks_not_in_profile = True if we are displaying False if not
#  mono_fonts = dictionary of monospace fonts from TkInter
#  grand_totals = used for trcaking number of Projects/Profiles/Tasks/Scenes
#  tasker_root_elements points to our root xml for Projects/Profiles/Tasks/Scenes
#  directories = points to our directory items if we are displaying a directory
#  variables = Tasker variables.
#  current_project = current Project being processed
#  tkroot = root for Tkinter (can only get it once)
#  last_run = date of last run (set by restore_settings)
#  slash = backslash for Windows or forward slash for OS X and Linux.
#
#   return
from __future__ import annotations

from typing import ClassVar

from maptasker.src.sysconst import NOW_TIME


class PrimeItems:
    """PrimeItems class contains global variables used throughout MapTasker"""

    ai_analyze = False
    ai: ClassVar = {
        "do_ai": False,
        "model": "",
        "output_lines": [],  # Saved output results if doing an AI run.
        "api_key": "",
        "openai_key": "",
        "claude_key": "",
        "deepseek_key": "",
        "gemini_key": "",
    }
    xml_tree = None
    xml_root = None
    program_arguments: ClassVar[dict] = {}
    colors_to_use: ClassVar[dict] = {}
    output_lines: ClassVar = None
    file_to_get = ""
    file_to_use = ""
    task_count_for_profile = 0
    displaying_named_tasks_not_in_profile = False
    error_code = 0
    error_msg = ""
    mono_fonts: ClassVar = {}
    found_named_items: ClassVar[dict] = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }
    grand_totals: ClassVar[dict] = {
        "projects": 0,
        "profiles": 0,
        "unnamed_tasks": 0,
        "named_tasks": 0,
        "scenes": 0,
    }
    directory_items: ClassVar[dict] = {
        "current_item": "",
        "projects": [],
        "profiles": [],
        "tasks": [],
        "scenes": [],
    }
    tasker_root_elements: ClassVar[dict] = {
        "all_projects": [],
        "all_profiles": {},
        "all_scenes": {},
        "all_tasks": {},
        "all_tasks_by_name": {},
        "all_services": [],
    }
    directories: ClassVar[list] = []
    variables: ClassVar[dict] = {}
    current_project = ""
    tkroot = None
    last_run = NOW_TIME
    slash = "/"
    task_action_warnings: ClassVar[dict] = {}
    tasker_action_codes: ClassVar[dict] = {}
    tasker_arg_specs: ClassVar[dict] = {}
    tasker_category_descriptions: ClassVar[dict] = {}
    tasker_event_codes: ClassVar[dict] = {}
    tasker_state_codes: ClassVar[dict] = {}


# Reset all values
class PrimeItemsReset:
    """Re-initialize all values in PrimeItems class"""

    def __init__(self) -> None:
        """
        Initialize the PrimeItems class
        Args:
            self: The instance of the class
        Returns:
            None
        Initializes all attributes of the PrimeItems class with empty values or dictionaries:
            - Sets found_named_items flags to False
            - Initializes grand_totals and directory_items dictionaries
            - Initializes tasker_root_elements dictionary
            - Sets other attributes like xml_tree, program_arguments etc to empty values
        """
        PrimeItems.found_named_items = {
            "single_project_found": False,
            "single_profile_found": False,
            "single_task_found": False,
        }
        PrimeItems.grand_totals = {
            "projects": 0,
            "profiles": 0,
            "unnamed_tasks": 0,
            "named_tasks": 0,
            "scenes": 0,
        }
        PrimeItems.directory_items = {
            "current_item": "",
            "projects": [],
            "profiles": [],
            "tasks": [],
            "scenes": [],
        }
        PrimeItems.tasker_root_elements = {
            "all_projects": [],
            "all_profiles": {},
            "all_scenes": {},
            "all_tasks": {},
            "all_tasks_by_name": {},
            "all_services": [],
        }
        PrimeItems.directories = []
        PrimeItems.xml_tree = None
        PrimeItems.xml_root = None
        PrimeItems.program_arguments = {}
        PrimeItems.colors_to_use = {}
        PrimeItems.output_lines = None
        PrimeItems.file_to_get = ""
        PrimeItems.task_count_for_profile = 0
        PrimeItems.displaying_named_tasks_not_in_profile = False
        PrimeItems.mono_fonts = {}
        PrimeItems.directories = []
        PrimeItems.variables = {}
        PrimeItems.current_project = ""
        PrimeItems.error_code = 0
        PrimeItems.error_msg = ""
        PrimeItems.tkroot = None
        PrimeItems.ai_analyze = False
        PrimeItems.ai = {
            "do_ai": False,
            "output_lines": [],
            "api_key": "",
            "openai_key": "",
            "claude_key": "",
            "deepseek_key": "",
            "gemini_key": "",
        }
        PrimeItems.task_action_warnings = {}
