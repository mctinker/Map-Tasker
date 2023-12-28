"""Prime items which are used throughout MapTasker (globals)."""
#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# primitem = intialize PrimeItems which are used throughout MapTasker (globals).       #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications which include larger works  #
# using a licensed work under the same license. Copyright and license notices must be  #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #


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
#  ordered_list_count = count of number of <ul> we currently have in output queue
#  name_list = list of names of Projects/Profiles/Tasks/Scenes found thus far
#  displaying_named_tasks_not_in_profile = True if we are displaying False if not
#  mono_fonts = dictionary of monospace fonts from TkInter
#  grand_totals = used for trcaking number of Projects/Profiles/Tasks/Scenes
#  tasker_root_elements points to our root xml for Projects/Profiles/Tasks/Scenes
#  directories = points to our directory items if we are displaying a directory
#  variables = Tasker variables.
#  current_project = current Project being processed
#  tkroot = root for Tkinter (can only get it once)
#
#   return
from __future__ import annotations

from typing import ClassVar


class PrimeItems:
    """PrimeItems class contains global variables used throughout MapTasker"""

    xml_tree = None
    xml_root = None
    program_arguments: ClassVar = {}
    colors_to_use: ClassVar = {}
    output_lines = None
    file_to_get = ""
    task_count_for_profile = 0
    unordered_list_count = 0
    displaying_named_tasks_not_in_profile = False
    mono_fonts: ClassVar = {}
    found_named_items: ClassVar = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }
    grand_totals: ClassVar = {
        "projects": 0,
        "profiles": 0,
        "unnamed_tasks": 0,
        "named_tasks": 0,
        "scenes": 0,
    }
    directory_items: ClassVar = {
        "current_item": "",
        "projects": [],
        "profiles": [],
        "tasks": [],
        "scenes": [],
    }
    tasker_root_elements: ClassVar = {
        "all_projects": [],
        "all_profiles": {},
        "all_scenes": {},
        "all_tasks": {},
        "all_services": [],
    }
    scene_countgrand_totals: ClassVar = {
        "projects": 0,
        "profiles": 0,
        "unnamed_tasks": 0,
        "named_tasks": 0,
        "scenes": 0,
    }
    directories: ClassVar = []
    variables: ClassVar = {}
    current_project = ""
    error_code = 0
    error_msg = ""
    tkroot = None


# ##################################################################################
# Reset all values
# ##################################################################################
class PrimeItemsReset:
    """Re-initialize all values in PrimeItems class"""

    def __init__(self) -> None:  # noqa: ANN101
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
            "all_services": [],
        }
        PrimeItems.scene_countgrand_totals = {
            "projects": 0,
            "profiles": 0,
            "unnamed_tasks": 0,
            "named_tasks": 0,
            "scenes": 0,
        }
        PrimeItems.directories = []
        PrimeItems.xml_tree = None
        PrimeItems.xml_root = None
        PrimeItems.program_arguments = {}
        PrimeItems.colors_to_use = {}
        PrimeItems.output_lines = None
        PrimeItems.file_to_get = ""
        PrimeItems.task_count_for_profile = 0
        PrimeItems.unordered_list_count = 0
        PrimeItems.displaying_named_tasks_not_in_profile = False
        PrimeItems.mono_fonts = {}
        PrimeItems.directories = []
        PrimeItems.variables = {}
        PrimeItems.current_project = ""
        PrimeItems.error_code = 0
        PrimeItems.error_msg = ""
