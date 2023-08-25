#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# primitem: intialize primary_items, which are used throughout MapTasker               #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.lineout import LineOut


def initialize_primary_items(file_to_get: str) -> dict:

    # Primary Items
    #
    # Set up an initial empty dictionary of primary items used throughout this project
    #  xml_tree: main xml element of our Tasker xml tree
    #  xml_root: root xml element of our Tasker xml tree
    #  program_arguments: runtime arguments entered by user and parsed.
    #    See initparg.py for details.
    #  colors_to_use: colors to use in the output
    #  tasker_root_elements: root elements for all Projects/Profiles/Tasks/Scenes
    #  output_lines: class for all lines added to output thus far
    #  found_named_items: names/found-flags for single (if any) Project/Profile/Task
    #  file_to_get: file object/name of Tasker backup file to read and parse
    #  grand_totals: Total count of Projects/Profiles/Named Tasks, Unnamed Task, etc.
    #  task_count_for_profile: number of Tasks in the specific Profile for Project
    #    being processed
    #  named_task_count_total: number of named Tasks for Project being processed
    #  task_count_unnamed: number of unnamed Tasks for Project being processed
    #  task_count_no_profile: number of Profiles in Project being processed.
    #  directory_items: if displaying a directory then this is a dictionary of items
    #    for the directory
    #  ordered_list_count: count of number of <ul> we currently have in output queue
    #  name_list: list of names of Projects/Profiles/Tasks/Scenes found thus far
    #  displaying_named_tasks_not_in_profile: True if we are displaying, False if not
    #  mono_fonts: dictionary of monospace fonts from TkInter
    #  grand_totals: used for trcaking number of Projects/Profiles/Tasks/Scenes
    #  tasker_root_elements points to our root xml for Projects/Profiles/Tasks/Scenes
    # Return primary_items
    return {
        "xml_tree": None,
        "xml_root": None,
        "program_arguments": {},
        "colors_to_use": {},
        "output_lines": None,
        "file_to_get": file_to_get,
        "task_count_for_Profile": 0,
        "unordered_list_count": 0,
        "displaying_named_tasks_not_in_profile": False,
        "mono_fonts": {},
        "found_named_items": {
            "single_project_found": False,
            "single_profile_found": False,
            "single_task_found": False,
        },
        "grand_totals": {
            "projects": 0,
            "profiles": 0,
            "unnamed_tasks": 0,
            "named_tasks": 0,
            "scenes": 0,
        },
        "directory_items": {
            "current_item": "",
            "projects": [],
            "profiles": [],
            "tasks": [],
            "scenes": [],
        },
        "tasker_root_elements": {
        "all_projects": [],
        "all_profiles": {},
        "all_scenes": {},
        "all_tasks": {},
        "all_services": [],
        }
    }
