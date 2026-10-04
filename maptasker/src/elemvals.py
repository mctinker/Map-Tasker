"""Pull the values MapTasker reports out of a Tasker XML element."""

#! /usr/bin/env python3

#                                                                                      #
# elemvals: Read values out of Profile / Task / Project xml elements:                  #
#           the Profile/Task IDs, the Kid Application details, and the Task flags      #
#           (priority, collision, stay awake)                                          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState


def get_ids(
    doing_head_xml_element: bool,
    head_xml_element: Element,
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


def get_kid_app(element: Element, state: RunState) -> str:
    """
    Get any associated Kid Application info and return it
        :param element: root element to search for <Kid>
        :return: the Kid App info
    """
    blank = "&nbsp;"
    kid_features = kid_plugins = ""
    four_spaces = "&nbsp;&nbsp;&nbsp;&nbsp;"
    if element is None:
        return ""
    kid_element = element.find("Kid")
    if kid_element is None:
        return ""

    kid_package = kid_element.find("pkg").text
    kid_version = kid_element.find("vnme").text
    kid_target = kid_element.find("vTarg").text
    num_feature = num_plugin = 0

    for item in kid_element:  # Get any special features
        if "feat" in item.tag:
            kid_features = f" {kid_features}{num_feature + 1}={item.text}, "
            num_feature += 1
        elif "mplug" in item.tag:
            kid_plugins = f" {kid_plugins}{num_plugin + 1}={item.text}, "
            num_plugin += 1
    if kid_features:
        kid_features = f"<br>{four_spaces}Features:{kid_features[: len(kid_features) - 2]}"
    if kid_plugins:
        kid_plugins = f"<br>{four_spaces}Plugins:{kid_plugins[: len(kid_plugins) - 2]}"

    kid_app_info = (
        f"<br>&nbsp;&nbsp;&nbsp;[Kid App Package:{kid_package}, Version"
        f" Name:{kid_version}, Target Android"
        f" Version:{kid_target} {kid_features} {kid_plugins}]"
    )

    if state.program_arguments.pretty:
        number_of_blanks = kid_app_info.find("Package:") - 4
        kid_app_info = kid_app_info.replace(",", f"<br>{blank * number_of_blanks}")

    return kid_app_info


def get_priority(element: Element, event: bool) -> str:
    """
    Get any associated priority for the Task/Profile
        :param element: root element to search for
        :param event: True if this is for an 'Event' condition, False if not
        :return: the priority or none
    """
    if element is None:
        return ""
    priority_element = element.find("pri")
    if priority_element is None:
        return ""
    if event:
        return f" Priority:{priority_element.text}"
    return f"&nbsp;&nbsp;[Priority: {priority_element.text}]"


def get_collision(element: Element) -> str:
    """
    Get any Task collision setting
        :param element: root element to search for
        :return: the collision setting as text or blank
    """
    if element is None:
        return ""
    collision_element = element.find("rty")
    # No collision tag = default = Abort Task on collision (we'll leave it blank)
    if collision_element is None:
        return ""
    collision_flag = collision_element.text or ""
    if collision_flag == "1":
        collision_text = "Abort Existing Task"
    elif collision_flag == "2":
        collision_text = "Run both together"
    else:
        collision_text = "Abort New Task"

    return f"&nbsp;&nbsp;[Collision: {collision_text}]"


def get_awake(element: Element) -> str:
    """
    Get any Task Stay Awake (Keep Device Awake) setting
        :param element: root element to search for
        :return: the stay awake setting as text or blank
    """
    if element is None:
        return ""
    awake_element = element.find("stayawake")
    return "" if awake_element is None else "&nbsp;&nbsp;[Keep Device Awake]"
