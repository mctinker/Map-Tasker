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
import contextlib

import defusedxml.ElementTree  # Need for type hints
import maptasker.src.tasks as tasks
from maptasker.src.outputl import my_output
from maptasker.src.xmldata import tag_in_type
from maptasker.src.proclist import process_list
from maptasker.src.frmthtml import format_html

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
SCENE_TAGS_TO_IGNORE = [
    'cdate',
    'edate',
    'heightLand',
    'heightPort',
    'nme',
    'widthLand',
    'widthPort',
]


def get_scene_elements(
    child: defusedxml.ElementTree.XML,
    colormap: dict,
    program_args: dict,
    output_list: list,
) -> None:
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
    my_output(
        colormap,
        program_args,
        output_list,
        4,
        format_html(
            colormap,
            "scene_color",
            "",
            f"&nbsp;&nbsp;&nbsp;Element: {element_type[0]} named {element_name}",
            True,
        ),
    )

    return


def process_scene(
    my_scene: str,
    output_list: list[str],
    tasks_found: list[str],
    program_args: dict,
    colormap: dict,
    all_tasker_items: dict,
) -> None:
    """
    Process the Project's Scene(s), one at a time
        :param my_scene: name of Scene to process
        :param output_list: list of output lines
        :param tasks_found: list of Tasks found so far
        :param program_args: dictionary of runtime arguments
        :param colormap: dictionary of colors to use
        :param all_tasker_items: dictionary of Tasker Projects/Profiles/Tasks/Scenes
        :return:
    """
    # This import statement must reside here to avoid an error
    from maptasker.src.proclist import process_list

    # Go through all the children of the Scene looking for 'click' Tasks
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
                    temp_task_list = [sub_child.text]
                    # Check for valid Task ID
                    if '-' not in temp_task_list[0]:
                        my_output(colormap, program_args, output_list, 1, "")
                        task_element, name_of_task = tasks.get_task_name(
                            sub_child.text,
                            tasks_found,
                            temp_task_list,
                            "",
                            all_tasker_items["all_tasks"],
                        )
                        # reset to task name since get_task_name changes its value
                        temp_task_list = [sub_child.text]
                        extra = "&nbsp;&nbsp;ID:"
                        task_type = (
                            "&nbsp;&#45;&#45;Task:"
                            f" {SCENE_TASK_TYPES[sub_child.tag]}{extra}"
                        )
                        # process the Scene's Task
                        process_list(
                            task_type,
                            output_list,
                            temp_task_list,
                            task_element,
                            tasks_found,
                            program_args,
                            colormap,
                            all_tasker_items,
                        )
                        my_output(colormap, program_args, output_list, 1, "")
                    else:
                        break
                elif sub_child.tag == "Str":
                    break
    return


# #############################################################################################
# Go through all Scenes for Project, get their detail and output it
# #############################################################################################
def process_project_scenes(
    project: defusedxml.ElementTree.XML,
    colormap: dict,
    program_args: dict,
    output_list: list,
    our_task_element: defusedxml.ElementTree.XML,
    found_tasks: list,
    all_tasker_items: dict,
) -> None:
    """
    Go through all Scenes for Project, get their detail and output it
        :param project: xml element of Project we are processing
        :param colormap: colors to use in output
        :param program_args: runtime arguments
        :param output_list: list of output lines created thus far
        :param our_task_element: xml element pointing to our Task
        :param found_tasks: list of Tasks found so far
        :param all_tasker_items: all Projects/Profiles/Tasks/Scenes
        :return: nada
    """
    scene_names = None
    with contextlib.suppress(Exception):
        scene_names = project.find("scenes").text
    if scene_names is not None:
        scene_list = scene_names.split(",")

        # If last line in output has an end underline, then it must have been
        # for the list of Tasks not found in any Profile...and it has to be removed
        # to avoid a double end underline casing mis-alignment of Scene: statements in output
        if output_list[-1] == "</ul>":
            my_output(colormap, program_args, output_list, 1, "")
        # if output_list(len(output_list)-1)[]
        if scene_list[0]:
            process_list(
                "Scene:",
                output_list,
                scene_list,
                our_task_element,
                found_tasks,
                program_args,
                colormap,
                all_tasker_items,
            )
            # Force a line break
            my_output(colormap, program_args, output_list, 4, "")
    return
