#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# scenes: Process the Tasker Scene passed as input                                           #
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

SCENE_TASK_TYPES = {
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
    "itemclickTask": "ITEM TAP",
    "itemlongclickTask": "ITEM LONG TAP",
}
SCENE_TAGS_TO_IGNORE = ['cdate', 'edate', 'heightLand', 'heightPort', 'nme', 'widthLand', 'widthPort']


def get_scene_elements(child: xml.etree, colormap: dict, program_args: dict, output_list: list) -> None:
    """
Go through Scene's <xxxElement> tags and output them
    :param child: pointer to '<xxxElement' Scene xml statement
    :param colormap: colors to use
    :param program_args: program runtime arguments
    :param output_list: list of output lines
    :return: nothing
    """
    element_type = child.tag.split('Element')
    name_xml_element = child.find('Str')
    element_name = name_xml_element.text
    output_text = f'<span style="color:{colormap["scene_color"]}">&nbsp;&nbsp;&nbsp;Element: {element_type[0]} named {element_name}'
    my_output(colormap, program_args, output_list, 4, output_text)

    return


def process_scene(my_scene: str,
                  output_list: list[str],
                  tasks_found: list[str],
                  program_args: dict,
                  colormap: dict,
                  all_tasker_items: dict) -> None:
    """

    :param my_scene: name of Scene to process
    :param output_list: list of output lines
    :param tasks_found: list of Tasks found so far
    :param program_args: dictionary of runtime arguments
    :param colormap: dictionary of colors to use
    :param all_tasker_items: dictionary of Tasker Projects/Profiles/Tasks/Scenes
    :return:
    """
    # Go through sub-elements in the Scene element
    from maptasker.src.proclist import process_list

    # Go through all the children of the Scene looking for click Tasks
    for child in all_tasker_items["all_scenes"][my_scene]:
        if child.tag in SCENE_TAGS_TO_IGNORE:
            continue
        if child.tag == "PropertiesElement":
            return
        if tag_in_type(child.tag, True):  # xxxElement?
            # Display the Element details
            if program_args['display_detail_level'] == 3:
                get_scene_elements(child, colormap, program_args, output_list)
            for sub_child in child:  # Go through Element sub-items
                # Task-Click (<xxxClick> or <xxxTask>) associated with this Scene's element?
                if tag_in_type(sub_child.tag, False):
                    # Start Scene's Task list
                    my_output(colormap, program_args, output_list, 1, "")
                    temp_task_list = [sub_child.text]
                    # Check for valid Task ID
                    if '-' not in temp_task_list[0]:
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
                        task_type = f"⎯Task: {SCENE_TASK_TYPES[sub_child.tag]}{extra}"
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
                    else:
                        my_output(
                            colormap, program_args, output_list, 3, ""
                        )  # End list
                        break
                elif sub_child.tag == "Str":
                    break


# #######################################################################################
# For this specific Scene, get any Tasks it might have and output the details
# #######################################################################################
def get_scene_details_and_output(
        my_scene: str,
        output_list: list[str],
        tasks_found: list[str],
        program_args: dict,
        colormap: dict,
        all_tasker_items: dict,
) -> None:
    """
    For this specific Scene, get any Tasks it might have and output the details

    :param my_scene: name of Scenes associated with Task/Profile
    :param output_list: our additive output (each line = list element)
    :param tasks_found: list of tasks found
    :param program_args: program runtime argument settings
    :param colormap: colors to use in putput
    :param all_tasker_items: all Project/Profile/Task/Scene xml elements
    """

    # Go through each Scene to find TAP and Long TAP Tasks
    # for my_scene in the_list:
    process_scene(my_scene,
                  output_list,
                  tasks_found,
                  program_args,
                  colormap,
                  all_tasker_items)
    return
