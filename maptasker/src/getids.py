"""Get Profile or Task IDs from XML"""

#! /usr/bin/env python3

#                                                                                      #
# getids: Look for Profile / Task IDs in head_xml_element  <pids> <tids> xml elements  #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

import defusedxml.ElementTree  # Need for type hints


def get_ids(
    doing_head_xml_element: bool,
    head_xml_element: defusedxml.ElementTree,
    head_xml_element_name: str,
    head_xml_elements_without_profiles: list,
) -> list:
    """
    Find either head_xml_element 'pids' (Profile IDs) or 'tids' (Task IDs)
    :param doing_head_xml_element: True if looking for Profile IDs, False if Task IDs.
    :param head_xml_element: head_xml_element xml element
    :param head_xml_element_name: name of head_xml_element
    :param head_xml_elements_without_profiles: list of elements without ids
    :return: list of found IDs, or empty list if none found
    """

    found_ids = ""
    # Get Profiles by searching for <pids> element.  If not Profile IDs, just get Task IDs via <tids> xml element.
    ids_to_find = "pids" if doing_head_xml_element else "tids"

    # Get the IDs.
    try:
        # Get a list of the Profiles for this head_xml_element
        found_ids = head_xml_element.find(ids_to_find).text
    except AttributeError:  # head_xml_element has no Profile/Task IDs
        if head_xml_element_name not in head_xml_elements_without_profiles:
            head_xml_elements_without_profiles.append(head_xml_element_name)

    return found_ids.split(",") if found_ids != "" else []
