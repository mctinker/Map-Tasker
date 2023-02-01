# ########################################################################################## #
#                                                                                            #
# xmldata: deal with the xml data                                                            #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

# #######################################################################################
# See if the xml tag is one of the predefined types and return result
# #######################################################################################
def tag_in_type(tag: str, flag: bool) -> bool:
    """evaluate the xml tag to see if it is one of our predefined types

    Parameters: the tag to evaluate, and whether this is a Scene or not (which
            determines which list of types to look for)

    Returns: True if tag found, False otherwise

    """
    scene_task_element_types = [
        "ListElement",
        "TextElement",
        "ImageElement",
        "ButtonElement",
        "OvalElement",
        "EditTextElement",
    ]
    scene_task_click_types = [
        "checkchangeTask",
        "clickTask",
        "focuschangeTask",
        "itemselectedTask",
        "keyTask",
        "linkclickTask",
        "longclickTask",
        "mapclickTask",
        "maplongclickTask",
        "pageloadedTask",
        "strokeTask",
        "valueselectedTask",
        "videoTask",
    ]

    return (
        flag
        and tag in scene_task_element_types
        or not flag
        and tag in scene_task_click_types
    )  # Boolean
