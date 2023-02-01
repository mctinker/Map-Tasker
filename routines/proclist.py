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

from config import *
from routines.outputl import my_output
from routines.scenes import get_scene_details_and_output
from routines.taskactn import get_task_actions_and_output
from routines.sysconst import *


# #######################################################################################
# Process Task/Scene text/line item: call recursively for Tasks within Scenes
# #######################################################################################
def process_list(
    list_type: str,
    output_list: list,
    the_list: list,
    the_task: xml.etree.ElementTree,
    tasks_found: list,
    program_args: dict,
    colormap: dict,
    all_tasker_items: dict,
) -> None:
    # Go through all Tasks in the list
    for my_count, the_item in enumerate(the_list):
        temp_item = ""
        temp_list = ""
        if program_args["debug"]:
            logger.debug(
                f"process_list  the_item:{str(the_item)} the_list:{the_list} list_type:{list_type}"
            )
        elif "⎯Task:" in list_type:
            temp_item = the_item
            temp_list = list_type
            the_item = ""
            id_loc = list_type.find("ID:")
            if id_loc != -1:
                list_type = list_type[:id_loc]
        my_output(
            colormap, program_args, output_list, 2, f"{list_type}&nbsp;{the_item}"
        )
        if temp_item:  # Put the_item back with the 'ID: nnn' portion included.
            the_item = temp_item
            list_type = temp_list

        # Output Actions for this Task if displaying detail and/or Task is unknown
        # Do we get the Task's Actions?
        if ("Task:" in list_type and UNKNOWN_TASK_NAME in the_item) or (
            "Task:" in list_type
        ):
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

        elif (
            list_type == "Scene:" and program_args["display_detail_level"] > 1
        ):  # We have a Scene: get its actions
            get_scene_details_and_output(
                the_list,
                output_list,
                tasks_found,
                program_args,
                colormap,
                all_tasker_items,
            )

    return
