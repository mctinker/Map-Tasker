#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# action: Task Action functions for MapTasker                                                #
#                                                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import xml.etree.ElementTree  # Need for type hints
import maptasker.src.tasks as tasks
from maptasker.src.outputl import my_output
from maptasker.src.xmldata import tag_in_type


def process_scene(my_scene: xml.etree,
        the_list: list[str],
        output_list: list[str],
        tasks_found: list[str],
        program_args: dict,
        colormap: dict,
        all_tasker_items: dict) -> None:
    """
    We have a Scene.  Now lets grab the information from it and output it

    :param my_scene: pointer to Scene's xml element
    """
    # Go through sub-elements in the Scene element
    from maptasker.src.proclist import process_list

    scene_task_types = {
        "checkchangeTask": "Check Change",
        "clickTask": "TAP",
        "focuschangeTask": "Focus Change",
        "itemselectedTask": "Item Selected",
        "keyTask": "Key",
        "linkclickTask": "Link",
        "longclickTask": "LONG TAP",
        "mapclickTask": "Map",
        "maplongclickTask": "Long Map",
        "pageloadedTask": "Page Load",
        "strokeTask": "STROKE",
        "valueselectedTask": "Value Selected",
        "videoTask": "Video",
    }
    getout = 0
    have_a_scene_task = False

    for child in all_tasker_items["all_scenes"][my_scene]:
        if tag_in_type(child.tag, True):  # xxxElement?
            for sub_child in child:  # Go through Element sub-items
                # Task-click associated with this Scene's element?
                if tag_in_type(sub_child.tag, False):
                    my_output(
                        colormap, program_args, output_list, 1, ""
                    )  # Start Scene's Task list
                    have_a_scene_task = True
                    temp_task_list = [sub_child.text]
                    task_element, name_of_task = tasks.get_task_name(
                        sub_child.text,
                        tasks_found,
                        temp_task_list,
                        "",
                        all_tasker_items["all_tasks"],
                    )
                    # reset to task name since get_task_name changes its value
                    temp_task_list = [
                        sub_child.text
                    ]
                    extra = "&nbsp;&nbsp;ID:"
                    task_type = f"⎯Task: {scene_task_types[sub_child.tag]}{extra}"
                    process_list(
                        task_type,
                        output_list,
                        temp_task_list,
                        task_element,
                        tasks_found,
                        program_args,
                        colormap,
                        all_tasker_items,
                    )  # process the Scene's Task
                    my_output(
                        colormap, program_args, output_list, 3, ""
                    )  # End list
                elif sub_child.tag == "Str":
                    break
            if (
                    have_a_scene_task
            ):  # Add Scene's Tasks to total list of Scene's Tasks
                getout = 2
            else:
                break
        elif child.tag == "Str":
            break
        elif (
                child.tag == "PropertiesElement"
        ):  # Have we gone past the point ofm interest?
            break
        if getout > 0:
            break


# #######################################################################################
# For this specific Scene, get any Tasks it might have and output the details
# #######################################################################################
def get_scene_details_and_output(
        the_list: list[str],
        output_list: list[str],
        tasks_found: list[str],
        program_args: dict,
        colormap: dict,
        all_tasker_items: dict,
) -> None:
    """
    For this specific Scene, get any Tasks it might have and output the details

    :param the_list:  list of Scenes associated with Task/Profile
    :param output_list: our additive output (each line = list element)
    :param tasks_found: list of tasks found
    :param program_args: program runtime argument settings
    :param colormap: colors to use in putput
    :param all_tasker_items: all Project/Profile/Task/Scene xml elements
    """

    # Go through each Scene to find TAP and Long TAP Tasks
    for my_scene in the_list:
        process_scene(my_scene, the_list,
            output_list,
            tasks_found,
            program_args,
            colormap,
            all_tasker_items)
    return
