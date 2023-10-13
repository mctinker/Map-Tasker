#! /usr/bin/env python3
import sys

import defusedxml.cElementTree as ET

from maptasker.src.error import error_handler

# #################################################################################### #
#                                                                                      #
# taskerd: get Tasker data from backup xml                                             #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.sysconst import FormatLine, logger


# ##################################################################################
# Convert list of xml to dictionary
# ##################################################################################
def move_xml_to_table(all_xml: list, get_id: bool, name_qualifier: str) -> dict:
    """
    Given a list of Profile/Task/Scene elements, find each name and store the element and name in a dictionary.
        :param all_xml: the head xml element for Profile/Task/Scene
        :param get_id: True if we are to get the <id>
        :param ame_qualifier: the qualifier to find the element's name.
        :return: dictionary that we created
    """
    new_table = {}
    for item in all_xml:
        # Get the element name
        try:
            name = item.find(name_qualifier).text
        except AttributeError:
            name = ""
        # Get the Profile/Task identifier: id=number for Profiles and Tasks,
        item_id = item.find("id").text if get_id else name
        new_table[item_id] = {"xml": item, "name": name}

    all_xml.clear()  # Ok, we're done with the list
    return new_table


# ##################################################################################
# Load all of the Projects, Profiles and Tasks into a format we can easily
# navigate through.
# ##################################################################################
def get_the_xml_data(primary_items: dict) -> dict:
    """
    Load all the Projects, Profiles and Tasks into a format we can easily navigate through
        :param primary_items:  Program registry.  See primitem.py for details.
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

    # Get the xml root
    primary_items["xml_root"] = primary_items["xml_tree"].getroot()

    # Check for valid Tasker backup.xml file
    if primary_items["xml_root"].tag != "TaskerData":
        error_msg = "You did not select a Tasker backup XML file...exit 2"
        primary_items["output_lines"].add_line_to_output(
            primary_items, 0, error_msg, FormatLine.dont_format_line
        )
        logger.debug(f"{error_msg}exit 3")
        sys.exit(3)

    all_services = primary_items["xml_root"].findall("Setting")
    all_projects_list = primary_items["xml_root"].findall("Project")
    all_profiles_list = primary_items["xml_root"].findall("Profile")
    all_scenes_list = primary_items["xml_root"].findall("Scene")
    all_tasks_list = primary_items["xml_root"].findall("Task")

    # We now have what we need as lists.  Now move all into dictionaries.
    all_projects = move_xml_to_table(all_projects_list, False, "name")
    all_profiles = move_xml_to_table(all_profiles_list, True, "nme")
    all_tasks = move_xml_to_table(all_tasks_list, True, "nme")
    all_scenes = move_xml_to_table(all_scenes_list, False, "nme")

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
