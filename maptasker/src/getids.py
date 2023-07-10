#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# getids: Look for Profile / Task IDs in head_xml_element  <pids> <tids> xml elements        #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import defusedxml.ElementTree  # Need for type hints


def get_ids(
    primary_items: dict,
    doing_head_xml_element: bool,
    head_xml_element: defusedxml.ElementTree.XML,
    head_xml_element_name: str,
    head_xml_elements_without_profiles: list,
) -> list:
    """
    Find either head_xml_element 'pids' (Profile IDs) or 'tids' (Task IDs)
    :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
    :param doing_head_xml_element: True if this is searching for head_xml_element IDs
    :param head_xml_element: head_xml_element xml element
    :param head_xml_element_name: name of head_xml_element
    :param head_xml_elements_without_profiles: list of elements without ids
    :return:
    """
    # Get Profiles
    found_ids = ""
    if doing_head_xml_element:
        found_ids = ""
        ids_to_find = 'pids'
        primary_items["output_lines"].add_line_to_output(
            primary_items, 1, ""
        )  # Start Profile list
    else:
        ids_to_find = 'tids'
    try:
        # Get a list of the Profiles for this head_xml_element
        found_ids = head_xml_element.find(ids_to_find).text
    except AttributeError:  # head_xml_element has no Profiles
        if head_xml_element_name not in head_xml_elements_without_profiles:
            head_xml_elements_without_profiles.append(head_xml_element_name)

    return found_ids.split(",") if found_ids != "" else []
