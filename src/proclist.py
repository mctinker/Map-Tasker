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
import xml.etree.ElementTree  # Need for type hints

from maptasker.src.outputl import my_output

from maptasker.src.taskactn import get_task_actions_and_output
from maptasker.src.sysconst import logger
from maptasker.src.sysconst import UNKNOWN_TASK_NAME


# #######################################################################################
# Process Task/Scene text/line item: call recursively for Tasks within Scenes
# #######################################################################################
def process_list(
    list_type: str,
    output_list: list,
    the_list: list,
    the_task: xml.etree,
    tasks_found: list,
    program_args: dict,
    colormap: dict,
    all_tasker_items: dict,
) -> None:
    """
    Process Task/Scene text/line item: call recursively for Tasks within Scenes
        :param list_type: Task or Scene
        :param output_list: list of output lines
        :param the_list: list of Task names tro process
        :param the_task: Task/Scene xml element
        :param tasks_found: list of Tasks found so far
        :param program_args: dictionary of runtime arguments
        :param colormap: dictionary of colors to use
        :param all_tasker_items: dictionary of all Tasker Projects/Profiles/Tasks/Scenes
        :return:
    """

    # This import must stay here to avoid error
    from maptasker.src.scenes import process_scene

    # Go through all Tasks in the list
    for my_count, the_item in enumerate(the_list):
        temp_item = ""
        temp_list = ""
        if program_args["debug"]:  # Add Task ID if in debug mode
            logger.debug(
                "process_list "
                f" the_item:{str(the_item)} the_list:{the_list} list_type:{list_type}"
            )
        elif "⎯Task:" in list_type:
            temp_item = the_item
            temp_list = list_type
            the_item = ""
            id_loc = list_type.find("ID:")
            if id_loc != -1:
                list_type = list_type[:id_loc]

        # Add this Task to the output
        my_output(
            colormap, program_args, output_list, 2, f"{list_type}&nbsp;{the_item}"
        )
        if temp_item:  # Put the_item back with the 'ID: nnn' portion included.
            the_item = temp_item
            list_type = temp_list

        # Output Actions for this Task if displaying detail and/or Task is unknown
        #   and not part of output for Tasks with no Profile(s)
        # Do we get the Task's Actions?
        if (
            (the_task and "Task:" in list_type and UNKNOWN_TASK_NAME in the_item)
            or ("Task:" in list_type)
        ) and "<em>No Profile" not in the_item:
            get_task_actions_and_output(
                the_task,
                output_list,
                program_args,
                list_type,
                the_item,
                tasks_found,
                colormap,
                all_tasker_items["all_tasks"],
            )
        elif list_type == "Scene:" and program_args["display_detail_level"] > 1:
            # We have a Scene: process it
            process_scene(
                the_item,
                output_list,
                tasks_found,
                program_args,
                colormap,
                all_tasker_items,
            )

    return
