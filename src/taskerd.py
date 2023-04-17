#! /usr/bin/env python3
import defusedxml
from defusedxml.ElementTree import parse

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


# ###############################################################################################
# Convert list of xml to dictionary
# ###############################################################################################
def move_xml_to_table(all_xml, is_scene: bool):
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
def get_the_xml_data(filename):
    logger.info("entry")
    # Import xml
    try:
        tree = parse(filename)
    except defusedxml.ElementTree.ParseError:
        error_msg = f"Error parsing {filename}"
        print(error_msg)
        logger.debug(error_msg)
        exit(1)

    root = tree.getroot()

    all_services = root.findall("Setting")
    all_projects = root.findall("Project")
    all_profiles_list = root.findall("Profile")
    all_scenes_list = root.findall("Scene")
    all_tasks_list = root.findall("Task")

    # We now have what we need as lists.  Now move some into dictionaries
    all_profiles = move_xml_to_table(all_profiles_list, False)
    all_tasks = move_xml_to_table(all_tasks_list, False)
    all_scenes = move_xml_to_table(all_scenes_list, True)

    # Return all data in a dictionary for easier access
    all_tasker_items = {
        "all_projects": all_projects,
        "all_profiles": all_profiles,
        "all_scenes": all_scenes,
        "all_tasks": all_tasks,
        "all_services": all_services,
    }
    logger.info("exit")
    return tree, root, all_tasker_items
