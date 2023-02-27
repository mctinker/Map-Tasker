#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# priority: Get Profile/Task priority                                                        #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import xml.etree.ElementTree  # Need for type hints


def get_priority(element: xml.etree, event: bool) -> str:
    """
Get any associated priority for the Task/Profile
    :param element: root element to search for
    :param event: True if this is for an 'Event' condition, False if not
    :return: the priority or none
    """

    priority_element = element.find("pri")
    if priority_element is None:
        return ""
    elif event:
        return f'Priority:{priority_element.text}'
    else:
        return f'<br>&nbsp;&nbsp;&nbsp;[Priority: {priority_element.text}]'
