#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# scenes: Process the Tasker Scene passed as input                                     #
#                                                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import contextlib

import defusedxml.ElementTree  # Need for type hints

import maptasker.src.tasks as tasks
from maptasker.src.dirout import add_directory_item
from maptasker.src.proclist import process_list
from maptasker.src.sysconst import FormatLine
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
SCENE_TAGS_TO_IGNORE = [
    "cdate",
    "edate",
    "heightLand",
    "nme",
    "widthLand",
]


# ##################################################################################
# Get the Scene's geometry
# ##################################################################################
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


# ##################################################################################
# Get the Scene's elements
# ##################################################################################
def get_scene_elements(
    primary_items: dict,
    child: defusedxml.ElementTree,
) -> None:
    """
    Go through Scene's <xxxElement> tags and output them
        :param primary_items:  Program registry.  See primitem.py for details.
        :param child: pointer to '<xxxElement' Scene xml statement
        :return: nothing
    """
    element_type = child.tag.split("Element")
    # First string is the name of the element
    name_xml_element = child.find("Str")
    # Get the element's geometry
    geometry_xml_element = child.find("geom").text
    geometry = geometry_xml_element.split(",")
    element_name = name_xml_element.text
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        (
            f"&nbsp;&nbsp;&nbsp;Element: {element_type[0]} named"
            f" {element_name} ...with geometry"
            f" {geometry[0]}x{geometry[1]} {geometry[2]}x{geometry[3]}"
        ),
        ["", "scene_color", FormatLine.add_end_span],
    )

    # Check to see if this Scene has a layout Scene, and deal with it if so.
    if sub_scene := child.find("Scene"):
        sub_scene_element = sub_scene.find("Scene")
        width, height = get_geometry(sub_scene_element)
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            (
                "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Element has an item 'Layout'"
                f" (Scene) with width/height {width} X {height}"
            ),
            ["", "scene_color", FormatLine.add_end_span],
        )
    return


def get_width_and_height(
    primary_items: dict,
    scene: defusedxml.ElementTree,
    tasks_found: defusedxml.ElementTree,
) -> None:
    """
    Go through Scene to obtain it's height and width and output.

    Args:
        primary_items (dict): Program registry.  See primitem.py for details.
        scene (defusedxml.ElementTree): Scene xml element to trundle through.
        tasks_found (defusedxml.ElementTree): List of Tasks found so far.

    Returns:
        Nothing
    """
    for child in scene:
        if child.tag in SCENE_TAGS_TO_IGNORE:
            continue
        # End of "xxxElement"?
        if (
            child.tag == "PropertiesElement"
            and primary_items["program_arguments"]["display_detail_level"] != 2
        ):
            primary_items["output_lines"].output_lines.append("<br>")

        elif tag_in_type(child.tag, True):  # xxxElement?
            # Display the Element details
            if primary_items["program_arguments"]["display_detail_level"] > 2:
                get_scene_elements(primary_items, child)

            # Look for Tasks associated with this element
            for sub_child in child:  # Go through Element sub-items
                # Task-Click (<xxxClick>, <xxxTask>, etc.) associated with this
                #  Scene's element?
                if tag_in_type(sub_child.tag, False):
                    # Start Scene's Task list
                    temp_task_list = [sub_child.text]
                    if "-" in temp_task_list[0]:
                        break
                    # Start a list
                    primary_items["output_lines"].add_line_to_output(
                        primary_items, 1, "", FormatLine.dont_format_line
                    )
                    # Get the name of Task
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

                elif sub_child.tag == "Str":
                    break


# ##################################################################################
# Process the Scene
# ##################################################################################
def process_scene(
    primary_items: dict,
    my_scene: str,
    tasks_found: list[str],
) -> None:
    """
    Process the Project's Scene(s), one at a time
        :param primary_items:  Program registry.  See primitem.py for details.
        :param my_scene: name of Scene to process
        :param tasks_found: list of Tasks found so far
        :return:
    """

    scene = primary_items["tasker_root_elements"]["all_scenes"][my_scene]["xml"]
    # Get the Scene's geometry and display it
    height, width = get_geometry(scene)
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        f"&nbsp;Width/Height: {width} X {height}<br>",
        ["", "scene_color", FormatLine.add_end_span],
    )

    # Handle directory hyperlink
    if primary_items["program_arguments"]["directory"]:
        add_directory_item(primary_items, "scenes", my_scene)

    # Go through all the children of the Scene looking for width/height
    # and 'click' Tasks
    get_width_and_height(primary_items, scene, tasks_found)

    # If we are doing twisties, then we need to close the unordered list.
    #  (see lineout format_line, where we add a <ul> for this "Scene:" special case)
    if primary_items["program_arguments"]["twisty"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items, 3, "", FormatLine.dont_format_line
        )

    return


# ##################################################################################
# Go through all Scenes for Project, get their detail and output it
# ##################################################################################
def process_project_scenes(
    primary_items: dict,
    project: defusedxml.ElementTree.XML,
    our_task_element: defusedxml.ElementTree.XML,
    found_tasks: list,
) -> bool:
    """
    Go through all Scenes for Project, get their detail and output it
        :param primary_items:  Program registry.  See primitem.py for details.
        :param project: xml element of Project we are processing
        :param our_task_element: xml element pointing to our Task
        :param found_tasks: list of Tasks found so far
        :return: True if a Scene was output, False if not
    """
    scene_names = None
    primary_items["scene_count"] = 0
    with contextlib.suppress(Exception):
        scene_names = project.find("scenes").text
    if scene_names is not None:
        scene_list = scene_names.split(",")

        # If 2nd and 3rd last output lines are </ul>, then there is one too many.
        # Counter by adding a new line for the Scene.
        if (
            primary_items["output_lines"].output_lines[-2][:5] == "</ul>"
            and primary_items["output_lines"].output_lines[-3][:5] == "</ul>"
        ):
            primary_items["output_lines"].add_line_to_output(
                primary_items, 1, "", FormatLine.dont_format_line
            )

        # If last line in output has an end-ordered-list, then it must have been
        # for the list of Tasks not found in any Profile...and it has to be removed
        # to avoid a double end underline causing mis-alignment of Scene:
        #   statements in output
        if primary_items["output_lines"].output_lines[-1] == "</ul>":
            primary_items["output_lines"].delete_last_line(primary_items)

        # If we have at least one Scene, process it
        if scene_list[0]:
            primary_items["scene_count"] = len(scene_list)
            process_list(
                primary_items,
                "Scene:",
                scene_list,
                our_task_element,
                found_tasks,
            )

            # Force a line break
            primary_items["output_lines"].add_line_to_output(
                primary_items, 4, "", FormatLine.dont_format_line
            )

            if primary_items["program_arguments"]["display_detail_level"] == 0:
                # End list if displaying level 0
                primary_items["output_lines"].add_line_to_output(
                    primary_items, 3, "", FormatLine.dont_format_line
                )

    return bool(scene_names)
