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
    'nme',
    'widthLand',
]


def get_geometry(scene_element: defusedxml.ElementTree.XML) -> tuple[str, str]:
    """
    Get the Scene's geometry
        :param scene_element: xml element of the Scene <Scene sr="scene...
        :return: width and height
    """
    height = width = "none"
    height = scene_element.find("heightPort")
    if height is not None:
        height = height.text
    width = scene_element.find("widthPort")
    if width is not None:
        width = width.text
    return width, height


def get_scene_elements(
    primary_items: dict,
    child: defusedxml.ElementTree,
) -> None:
    """
    Go through Scene's <xxxElement> tags and output them
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param child: pointer to '<xxxElement' Scene xml statement
        :return: nothing
    """
    element_type = child.tag.split('Element')
    # First string is the name of the element
    name_xml_element = child.find('Str')
    # Get the element's geometry
    geometry_xml_element = child.find('geom').text
    geometry = geometry_xml_element.split(",")
    element_name = name_xml_element.text
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items["colors_to_use"],
            "scene_color",
            "",
            (
                f"&nbsp;&nbsp;&nbsp;Element: {element_type[0]} named"
                f" {element_name} ...with geometry"
                f" {geometry[0]}x{geometry[1]} {geometry[2]}x{geometry[3]}"
            ),
            True,
        ),
    )

    # Check to see if this Scene has a layout Scene, and deal with it if so.
    if sub_scene := child.find("Scene"):
        sub_scene_element = sub_scene.find("Scene")
        width, height = get_geometry(sub_scene_element)
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            format_html(
                primary_items["colors_to_use"],
                "scene_color",
                "",
                (
                    "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Element has an item 'Layout'"
                    f" (Scene) with width/height {width} X {height}"
                ),
                True,
            ),
        )
    return


def process_scene(
    primary_items: dict,
    my_scene: str,
    tasks_found: list[str],
) -> None:
    """
    Process the Project's Scene(s), one at a time
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param my_scene: name of Scene to process
        :param tasks_found: list of Tasks found so far
        :return:
    """
    # This import statement must reside here to avoid an error
    from maptasker.src.proclist import process_list

    # Get the Scene's geometry and display it
    height, width = get_geometry(
        primary_items["tasker_root_elements"]["all_scenes"][my_scene]
    )
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items["colors_to_use"],
            "scene_color",
            "",
            f"&nbsp;Width/Height: {width} X {height}<br>",
            True,
        ),
    )

    # Go through all the children of the Scene looking for width/height and 'click' Tasks
    for child in primary_items["tasker_root_elements"]["all_scenes"][my_scene]:
        if child.tag in SCENE_TAGS_TO_IGNORE:
            continue
        # End of "xxxElement"?
        if child.tag == "PropertiesElement":
            primary_items["output_lines"].output_lines.append("<br>")

        elif tag_in_type(child.tag, True):  # xxxElement?
            # Display the Element details
            if primary_items["program_arguments"]['display_detail_level'] == 3:
                get_scene_elements(primary_items, child)
            for sub_child in child:  # Go through Element sub-items
                # Task-Click (<xxxClick>, <xxxTask>, etc.) associated with this Scene's element?
                if tag_in_type(sub_child.tag, False):
                    # Start Scene's Task list
                    temp_task_list = [sub_child.text]
                    # Check for valid Task ID
                    if '-' not in temp_task_list[0]:
                        primary_items["output_lines"].add_line_to_output(
                            primary_items, 1, ""
                        )
                        task_element, name_of_task = tasks.get_task_name(
                            primary_items,
                            sub_child.text,
                            tasks_found,
                            temp_task_list,
                            "",
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
                            primary_items,
                            task_type,
                            temp_task_list,
                            task_element,
                            tasks_found,
                        )
                        # Start a list
                        primary_items["output_lines"].add_line_to_output(
                            primary_items, 1, ""
                        )
                    else:
                        break
                elif sub_child.tag == "Str":
                    break

    # If we are doing twisties, then we need to close the unordered list.
    #  (see lineout format_line, where we add a <ul> for this "Scene:" special case)
    if primary_items["program_arguments"]["twisty"]:
        primary_items["output_lines"].add_line_to_output(primary_items, 3, "")

    return


# #############################################################################################
# Go through all Scenes for Project, get their detail and output it
# #############################################################################################
def process_project_scenes(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    our_task_element: defusedxml.ElementTree.XML,
    found_tasks: list,
) -> None:
    """
    Go through all Scenes for Project, get their detail and output it
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param project: xml element of Project we are processing
        :param our_task_element: xml element pointing to our Task
        :param found_tasks: list of Tasks found so far
        :return: nada
    """
    scene_names = None
    primary_items["scene_count"] = 0
    with contextlib.suppress(Exception):
        scene_names = project.find("scenes").text
    if scene_names is not None:
        scene_list = scene_names.split(",")

        # If last line in output has an end underline, then it must have been
        # for the list of Tasks not found in any Profile...and it has to be removed
        # to avoid a double end underline casing mis-alignment of Scene: statements in output
        if primary_items["output_lines"].output_lines[-1] == "</ul>":
            primary_items["output_lines"].add_line_to_output(primary_items, 1, "")

        if scene_list[0]:
            primary_items["scene_count"] = len(scene_list)
            # # If we have Scene(s), process it/them
            process_list(
                primary_items,
                "Scene:",
                scene_list,
                our_task_element,
                found_tasks,
            )

            # Force a line break
            primary_items["output_lines"].add_line_to_output(primary_items, 4, "")

    return
