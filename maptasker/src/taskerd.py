#! /usr/bin/env python3

import defusedxml.cElementTree as ET

# ########################################################################################## #
#                                                                                            #
# taskerd: get Tasker data from backup xml                                                   #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from maptasker.src.sysconst import logger
from maptasker.src.error import error_handler


# ###############################################################################################
# Convert list of xml to dictionary
# ###############################################################################################
def move_xml_to_table(all_xml: list, is_scene: bool) -> dict:
    """
    Given a list of Profile/Task/Scene elements, find each name and store the element and name in a dictionary
        :param all_xml: the head xml element for Profile/Task/Scene
        :param is_scene: True if this is for a Scene
        :return: dictionary that we created
    """
    new_table = {}
    key_to_find = "nme" if is_scene else "id"
    for item in all_xml:
        item_id = item.find(key_to_find).text
        new_table[item_id] = item
    all_xml.clear()  # Ok, we're done with the list
    return new_table


# ###############################################################################################
# Load all of the Projects, Profiles and Tasks into a format we can easily navigate through
# ###############################################################################################
def get_the_xml_data(primary_items: dict) -> dict:
    """
    Load all the Projects, Profiles and Tasks into a format we can easily navigate through
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :return: primary_items
    """

    logger.info("entry")
    # Import xml
    file_to_parse = primary_items["program_arguments"]["file"]
    try:
        primary_items["xml_tree"] = ET.parse(primary_items["file_to_get"])
    except ET.ParseError:  # Parsing error
        error_handler(
            f"Error in taskerd parsing {file_to_parse}", 1
        )  # Error out and exit
    except Exception:  # any other error
        error_handler(f"Parsing error in taskerd {file_to_parse}", 1)

    primary_items["xml_root"] = primary_items["xml_tree"].getroot()

    all_services = primary_items["xml_root"].findall("Setting")
    all_projects = primary_items["xml_root"].findall("Project")
    all_profiles_list = primary_items["xml_root"].findall("Profile")
    all_scenes_list = primary_items["xml_root"].findall("Scene")
    all_tasks_list = primary_items["xml_root"].findall("Task")

    # We now have what we need as lists.  Now move some into dictionaries
    all_profiles = move_xml_to_table(all_profiles_list, False)
    all_tasks = move_xml_to_table(all_tasks_list, False)
    all_scenes = move_xml_to_table(all_scenes_list, True)

    # Return all data in a dictionary for easier access
    primary_items["tasker_root_elements"] = {
        "all_projects": all_projects,
        "all_profiles": all_profiles,
        "all_scenes": all_scenes,
        "all_tasks": all_tasks,
        "all_services": all_services,
    }
    logger.info("exit")
    return primary_items
