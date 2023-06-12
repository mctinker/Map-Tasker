#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# proclist: process list - process a list of line items for Tasks and Scenes                 #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import defusedxml.ElementTree  # Need for type hints

from maptasker.src.taskactn import get_task_actions_and_output
from maptasker.src.sysconst import logger
from maptasker.src.sysconst import UNKNOWN_TASK_NAME
from maptasker.src.twisty import add_twisty


# #######################################################################################
# Process Given a Task/Scene, process it.
# #######################################################################################
def process_item(primary_items, the_item, list_type, the_list, the_task, tasks_found):
    # This import must stay here to avoid error
    from maptasker.src.scenes import process_scene

    temp_item = temp_list = ""
    save_scene_name = ""

    if primary_items["program_arguments"]["debug"]:  # Add Task ID if in debug mode
        logger.debug(
            "process_list "
            f" the_item:{str(the_item)} the_list:{the_list} list_type:{list_type}"
        )

    # Format the output line
    output_line = f"{list_type}&nbsp;{the_item}"

    # Set up the correct color for twisty of needed
    color_to_use = "scene_color" if list_type == "Scene:" else "task_color"

    # If "--Task:" then this is a Task under a Scene.
    # Need to temporarily save the_item since add_line_to_output changes the_item
    if "&#45;&#45;Task:" in list_type:
        temp_item = the_item
        temp_list = list_type
        the_item = ""
        if primary_items["program_arguments"]["debug"]:  # Get the Task ID
            id_loc = list_type.find("ID:")
            if id_loc != -1:
                list_type = f'{list_type}{str(id_loc)}'

    # Add the "twisty" to hide the Task details
    if primary_items["program_arguments"]["twisty"] and "Task:" in list_type:
        # Add the twisty magic
        add_twisty(primary_items, color_to_use, output_line)

    # Add this Task/Scene to the output
    primary_items["output_lines"].add_line_to_output(primary_items, 2, output_line)
    if temp_item:  # Put the_item back with the 'ID: nnn' portion included.
        the_item = temp_item
        list_type = temp_list

    # Output Actions for this Task if Task is unknown
    #   and not part of output for Tasks with no Profile(s)
    # Do we get the Task's Actions?
    if (
        (the_task and "Task:" in list_type and UNKNOWN_TASK_NAME in the_item)
        or ("Task:" in list_type)
    ) and "<em>No Profile" not in the_item:
        get_task_actions_and_output(
            primary_items,
            the_task,
            list_type,
            the_item,
            tasks_found,
        )

        # End the twisty hidden lines if not a Task in a Scene
        if (
            primary_items["program_arguments"]["twisty"]
            and "&#45;&#45;Task:" not in list_type
        ):
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                5,
                "</details>",
            )

    elif (  # Do we have a Scene?
        list_type == "Scene:"
        and primary_items["program_arguments"]["display_detail_level"] > 1
    ):
        # We have a Scene: process its details
        process_scene(
            primary_items,
            the_item,
            tasks_found,
        )

    # End twisty if named Task
    elif primary_items["program_arguments"]["twisty"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            5,
            "</details>",
        )
    return


# #######################################################################################
# Process Task/Scene text/line item: call recursively for Tasks within Scenes
# #######################################################################################
def process_list(
    primary_items: dict,
    list_type: str,
    the_list: list,
    the_task: defusedxml.ElementTree.XML,
    tasks_found: list,
) -> None:
    """
    Process Task/Scene text/line item: call recursively for Tasks within Scenes
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param list_type: Task or Scene
        :param the_list: list of Task names tro process
        :param the_task: Task/Scene xml element
        :param tasks_found: list of Tasks found so far
        :return:
    """

    # Go through all Tasks in the list
    for the_item in the_list:
        process_item(
            primary_items, the_item, list_type, the_list, the_task, tasks_found
        )

    return
