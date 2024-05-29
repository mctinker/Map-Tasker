#! /usr/bin/env python3

#                                                                                      #
# taskflag: Get Profile/Task fags: priority, collision, stay awake                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import defusedxml.ElementTree  # Need for type hints


def get_priority(element: defusedxml.ElementTree.XML, event: bool) -> str:
    """
    Get any associated priority for the Task/Profile
        :param element: root element to search for
        :param event: True if this is for an 'Event' condition, False if not
        :return: the priority or none
    """

    priority_element = element.find("pri")
    if priority_element is None:
        return ""
    if event:
        return f" Priority:{priority_element.text}"
    return f"&nbsp;&nbsp;[Priority: {priority_element.text}]"


def get_collision(element: defusedxml.ElementTree.XML) -> str:
    """
    Get any Task collision setting
        :param element: root element to search for
        :return: the collision setting as text or blank
    """

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


def get_awake(element: defusedxml.ElementTree.XML) -> str:
    """
    Get any Task Stay Awake (Keep Device Awake) setting
        :param element: root element to search for
        :return: the stay awake setting as text or blank
    """

    awake_element = element.find("stayawake")
    return "" if awake_element is None else "&nbsp;&nbsp;[Keep Device Awake]"
