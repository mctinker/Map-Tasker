#! /usr/bin/env python3
#                                                                                      #
# diagram: Output a diagram/map of the Tasker configuration.                           #
#                                                                                      #
# Traverse our network map and print out everything in connected boxes.                #
#                                                                                      #

"""
This code is somewhat of a mess.  It is overly complex, but I wanted to develop my own
diagramming app rather than rely on yet-another-dependency such as that for
'diagram' and 'graphviz' which would do a so-so job.
"""

from __future__ import annotations

import contextlib
import gc
import os
import re
from bisect import bisect_left
from typing import TYPE_CHECKING

from maptasker.src import diagintr
from maptasker.src.diagcnst import (
    CONNECTOR_DIRECTIONS,
    angle,
    angle_elbow,
    bar,
    blank,
    box_line,
    left_arrow,
    left_arrow_corner_down,
    left_arrow_corner_up,
    line_left_arrow,
    line_right_arrow,
    right_arrow,
    right_arrow_corner_down,
    right_arrow_corner_up,
    straight_line,
    task_delimeter,
)
from maptasker.src.diagutil import (
    add_output_line,
    build_box,
    build_call_table,
    delete_hanging_bars,
    find_nth,
    fix_duplicate_up_down_locations,
    include_heading,
    print_3_lines,
    print_all,
    print_box,
    remove_icon,
)
from maptasker.src.error import rutroh_error
from maptasker.src.getids import get_ids
from maptasker.src.mapjump import PROFILE, PROJECT, SCENE, TASK, Target

# Avoid circular import error: guiwins has the proper import statement for configure_progress_bar,
# the function, of which, is in guiutil2.
# from maptasker.src.guiwins import configure_progress_bar
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputils import find_all_positions
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    DIAGRAM_FILE,
    DIAGRAM_PROFILES_PER_LINE,
    MY_VERSION,
    NOW_TIME,
    SCENE_TASK_TYPES,
    UNNAMED_ITEM,
    FormatLine,
    logger,
)
from maptasker.src.xmldata import tag_in_type

if TYPE_CHECKING:
    import defusedxml.ElementTree

try:
    profiles_per_line = PrimeItems.program_arguments["profiles_per_line"]
except (AttributeError, KeyError):
    PrimeItems.program_arguments["profiles_per_line"] = DIAGRAM_PROFILES_PER_LINE


# ##################################################################################
# Where each object ends up in the drawn diagram.
# ##################################################################################
# The Diagram used to be the one view a report finding could not be taken to.  The Map
# carries a mapjump anchor on every Project, Profile, Task and action (see
# mapjump.anchor_html), and an id is all a jump needs; the Diagram is plain text, so there
# is nothing to put an id on.  Matching the text an object is DRAWN as gets close, and is
# still the fallback, but it cannot tell two Tasks of the same name apart -- and naming a
# Task twice is ordinary in Tasker.
#
# So the position is recorded as the diagram is built, and travels with it: {anchor id:
# (line, column, length)} in PrimeItems.diagram_anchors, in the coordinates of the file the
# Diagram view renders.  Column and length are in UTF-16 code units, which is what a
# browser counts in -- a Task name holding an emoji is one character to Python and two to
# JavaScript, and a column that disagreed with the browser by one per emoji would highlight
# the wrong span of a line it had otherwise found perfectly.
#
# Recording a position is not as simple as noting len(netmap_output), because a box is not
# written when it is built.  Profile and Scene boxes accumulate across a three-line buffer
# -- six or eight of them side by side -- and Task lines accumulate in a list of their own;
# both are appended to the output later, and a box's row is only known then.  So an object
# is NOTED against its buffer as it is drawn, and the notes are resolved to rows when that
# buffer is flushed (see _flush_boxes and _flush_tasks).
#
# Everything after that is a remap.  Four steps move a row between being noted and being
# rendered, and each is applied here in the same breath as the connector seeds' own
# remapping, which goes through the last two of them:
#
#   add_blanks_above_called_tasks   inserts the blank lines the call arrows are drawn into
#   the view limit's cut            drops everything past the line the diagram stops at
#   build_network_map's bar sweep   drops the lines left holding nothing but '|'
#   network_map's file write        inserts the spacers written between Projects
#
# A missing anchor is ordinary rather than an error: a Diagram built for one Project has no
# line for anything outside it, and one built by a MapTasker older than this has no
# anchors at all.  Both fall back to the text match -- see mapjump.diagram_jump_js.
# ##################################################################################
# What a box is closed with, for extending a located name to the whole box it sits in.
_BOX_WALL = "\u2551"

# Objects noted against the three-line box buffer, waiting for it to be flushed.  Always
# the middle line of the three, which is the only one a name is written on.
_pending_boxes: list[tuple[Target, str]] = []

# Objects noted against the Task-line buffer: (index in that buffer, target, snippet).
_pending_tasks: list[tuple[int, Target, str]] = []


def _note_box(target: Target, snippet: str) -> None:
    """Record that this object has just been drawn into the box buffer's middle line."""
    _pending_boxes.append((target, snippet))


def _note_task(index: int, target: Target, snippet: str) -> None:
    """Record that this Task has just been drawn as line `index` of the Task buffer."""
    _pending_tasks.append((index, target, snippet))


def _record(row: int, target: Target, snippet: str) -> None:
    """Fix one noted object at a row of netmap_output.

    Two records, because two questions are being asked and they have different answers.

    WHERE A JUMP LANDS is diagram_object_seeds, and there first sighting wins, exactly as
    mapjump.anchor_html decides it for the Map: the Diagram draws a Task once per Profile
    that runs it and again under any Scene that fires it, and a jump should land on the
    Task's own line under its Profile rather than on whichever copy happened to be written
    last.

    WHAT IS CLICKABLE is diagram_object_placements, and there every drawing counts.  These
    used to be the same record, and the copies simply went unrecorded -- so the second and
    later drawings of a Task were drawn as plain text: not clickable, not lit up by a chain
    running through them, and invisible to the call edges that happened to point at one.
    The first one worked, which is what made it look like a rule rather than a gap.

    The Target is kept alongside, in a table of its own.  The position moves -- four
    separate passes remap it before the diagram is written -- and the identity does not, so
    the two are held apart: the positions are remapped over and over, while the identity is
    written once and only read at the end, when the interactive Diagram view's node model is
    assembled (see diagintr.build_model).
    """
    seeds = PrimeItems.diagram_object_seeds
    if target.anchor not in seeds:
        seeds[target.anchor] = (row, snippet)
        PrimeItems.diagram_object_targets[target.anchor] = target
    PrimeItems.diagram_object_placements.append((target.anchor, row, snippet))


def _flush_boxes(output_lines: list) -> None:
    """Append a finished row of boxes, and fix every box noted into it at its line.

    print_3_lines by another name.  The row is taken before the append rather than after,
    since it is the append that makes it a row at all.
    """
    row = len(PrimeItems.netmap_output) + 1  # The middle of the three lines.
    print_3_lines(output_lines)
    for target, snippet in _pending_boxes:
        _record(row, target, snippet)
    _pending_boxes.clear()


def _flush_tasks(output_lines: list) -> None:
    """Append a finished run of Task lines, and fix every Task noted into it at its line."""
    base = len(PrimeItems.netmap_output)
    print_all(output_lines)
    for index, target, snippet in _pending_tasks:
        _record(base + index, target, snippet)
    _pending_tasks.clear()


def _remap_object_seeds(old_to_new: dict[int, int]) -> None:
    """Move every recorded object to where its line has just moved to.

    A row with no entry in the map is a row that no longer exists -- cut off at the view
    limit, or swept away as a bar-only line -- and the object on it is dropped rather than
    left pointing at whatever ended up there instead.
    """
    PrimeItems.diagram_object_seeds = {
        anchor: (old_to_new[row], snippet)
        for anchor, (row, snippet) in PrimeItems.diagram_object_seeds.items()
        if row in old_to_new
    }
    PrimeItems.diagram_object_placements = [
        (anchor, old_to_new[row], snippet)
        for anchor, row, snippet in PrimeItems.diagram_object_placements
        if row in old_to_new
    ]


def _remap_call_edges(old_to_new: dict[int, int]) -> None:
    """Move every recorded call to where the two Task lines it joins have just moved to.

    The same journey the object seeds make, and made in the same breath as theirs so the
    two cannot drift apart -- an edge whose rows no longer agree with the anchors on them
    is an edge that would highlight the wrong Tasks.  An edge losing either end (cut off at
    the view limit, or swept away with a bar-only line) is dropped whole: half a call is
    not a link in a chain.
    """
    PrimeItems.diagram_call_edges = {
        index: {**edge, "caller_row": old_to_new[edge["caller_row"]], "called_row": old_to_new[edge["called_row"]]}
        for index, edge in PrimeItems.diagram_call_edges.items()
        if edge["caller_row"] in old_to_new and edge["called_row"] in old_to_new
    }


def _keep_object_seeds_before(cut: int) -> None:
    """Drop every object drawn past the line the view limit cut the diagram at.

    Those lines are about to be deleted outright, and an object still pointing into them
    would be a jump into whatever the file ends with.
    """
    PrimeItems.diagram_object_seeds = {
        anchor: placement for anchor, placement in PrimeItems.diagram_object_seeds.items() if placement[0] < cut
    }
    PrimeItems.diagram_object_placements = [
        placement for placement in PrimeItems.diagram_object_placements if placement[1] < cut
    ]


def _utf16_length(text: str) -> int:
    """How many UTF-16 code units this text is -- how the browser counts a string index.

    Python indexes by code point, JavaScript by UTF-16 code unit, and the two differ by one
    for every astral character: an emoji in a Task name (Tasker allows them, and real
    configurations use them) is one to Python and two to the browser.  Converting here is
    what lets the browser take the column as given rather than searching for the name again.
    """
    return len(text.encode("utf-16-le")) // 2


def _place(line: str, snippet: str, boxed: bool, start: int = 0) -> tuple[int, int]:
    """Where in this rendered line the object's name sits: (column, length), browser-counted.

    (0, 0) when the name cannot be found on the line after all, which the Diagram view
    reads as "the whole line" -- the line is still the right one to be taken to, and
    highlighting all of it says so more honestly than highlighting nothing.  Reachable
    because remove_icon rubs out a blank next to an arrow to keep a line with an icon in it
    aligned, which can fall inside a name.

    A box's name is extended to the wall that closes it, so a Profile jumped to is
    highlighted as the box the eye reads it as rather than as bare text inside one.

    'start' is where to begin looking, in code points, and is how a line holding the same
    name twice gives up both of them.  Two Profiles drawn side by side can run the very same
    Task, which puts "└─ Wear Location Menu" on the line twice; searching from the front
    each time would answer with the first one for both, and the two would be handed to the
    view as one span drawn over itself.
    """
    at = line.find(snippet, start)
    if at < 0:
        return (0, 0)
    end = at + len(snippet)
    if boxed:
        closing = line.find(_BOX_WALL, end)
        if closing != -1:
            end = closing + 1
    return (_utf16_length(line[:at]), _utf16_length(line[at:end]))


def flatten_with_quotes(string_list: list) -> str:
    """
    Given a list of strings, return a single string with all strings
    quoted and separated by commas.

    Args:
        string_list (list): List of strings to flatten with quotes.

    Returns:
        str: Flattened string with all strings quoted and separated
            by commas.
    """
    return ", ".join([f"{task_delimeter}{s}{task_delimeter}" for s in string_list])


def add_quotes(
    output_task_lines: list,
    last_upward_bar: int,
    task: dict,
    task_type: str,
    called_by_tasks: list,
    position_for_anchor: int,
    found_tasks: list,
) -> tuple:
    """
    Add quotes to called Tasks.

    Args:
        output_task_lines (list): List of output lines to add to.
        last_upward_bar (int): The position of the last upward | in the output.
        task (dict): Task details: xml element, name, etc.
        task_type (str): Entry or Exit
        called_by_tasks (list): List of Tasks this Task is called by.
        position_for_anchor (int): Location of the anchor point for the Task.
        found_tasks (list): List of Tasks found so far.

    Returns:
        tuple: Tuple containing the updated output_task_lines, last_upward_bar, and found_tasks.
    """
    call_tasks = ""
    task_name = task["name"]

    # Correct the name in case it has a Screen element 'click' name associated with it.
    position = task_name.find(":")
    real_task_name = task_name.split("&nbsp;")[0]
    if position != -1 and "," in task_name:
        scene_task_type_to_check = task_name.split(",")[1].split(":")[0][1:]
        for scene_task_type in SCENE_TASK_TYPES.values():
            if scene_task_type == scene_task_type_to_check:
                temp = task_name.find(":")
                if temp != -1:
                    real_task_name = task_name[temp + 2 :]
                break

    # Get the primary task pointer for this task.
    try:
        prime_task = PrimeItems.tasker_root_elements["all_tasks_by_name"][real_task_name]
    except KeyError:
        prime_task = None

    with contextlib.suppress(KeyError):
        if prime_task["call_tasks"] is not None:
            # Flatten list of called tasks and surround each with a quote.
            call_tasks = f" [Calls {line_right_arrow} {flatten_with_quotes(prime_task['call_tasks'])}]"

    # We are still accumulating outlines for Profiles.
    # Build lines for the Profile's Tasks as well.
    line = f"{blank * position_for_anchor}{angle}{task_name}{task_type}{called_by_tasks}{call_tasks}"
    last_upward_bar.append(position_for_anchor)
    # Note where this Task is being drawn, against the buffer rather than the output: these
    # lines are appended to the diagram later, and only then is the row known (see
    # _flush_tasks).
    #
    # The id comes from the Task's own element, NOT from prime_task -- which was looked up
    # by name, and all_tasks_by_name keeps one entry per name (taskerd.py), so two Tasks
    # called 'Backup' both resolve to whichever of them the table kept.  Both are drawn
    # here, on lines of their own, and taking the id from the element is what lets a jump
    # tell them apart; going through the name table would file the second one's line under
    # the first one's id and land every click on the first.
    task_id = task["xml"].findtext("id") if task.get("xml") is not None else ""
    if task_id:
        _note_task(
            len(output_task_lines),
            Target(kind=TASK, key=task_id, name=real_task_name),
            f"{angle}{task_name}",
        )
    output_task_lines.append(line)
    if task_name not in found_tasks:
        found_tasks.append(task_name)

    # Add a blank line afterwards for each called Task (one per task name) for yet-to-be-populated connectors.
    with contextlib.suppress(KeyError):
        for calls_task in prime_task["call_tasks"]:
            output_task_lines.append("")

            # Keep track of all Tasks being called
            the_task = calls_task
            if PrimeItems.called_task_tracker:
                if the_task in PrimeItems.called_task_tracker:
                    PrimeItems.called_task_tracker[the_task]["total_number"] += 1
                else:
                    PrimeItems.called_task_tracker[the_task] = {
                        "total_number": 1,
                        "counter": 0,
                    }
            else:
                PrimeItems.called_task_tracker[the_task] = {
                    "total_number": 1,
                    "counter": 0,
                }

    # Interject the "|" for previous Tasks under Profile
    for bar_char in last_upward_bar:
        for line_num, line in enumerate(output_task_lines):
            if len(line) > bar_char and not line[bar_char]:
                output_task_lines[line_num] = f"{line[:bar_char]}│{line[bar_char:]}"
            if len(line) <= bar_char:
                output_task_lines[line_num] = f"{line.ljust(bar_char)}│"

    return found_tasks, last_upward_bar, output_task_lines


# Print the specific Task.
def output_the_task(
    print_tasks: bool,
    found_tasks: list,
    task: dict,
    output_task_lines: list,
    last_upward_bar: list,
    task_type: str,
    called_by_tasks: list,
    position_for_anchor: int,
) -> tuple[bool, int]:
    """
    Add the Task to the output list.
        Args:
            print_tasks (bool): True if we are printing Tasks.
            found_tasks (list): List of Tasks found so far.
            task (dict): Task details: xml element, name, etc.
            output_task_lines (list): List of output lines to add to.
            last_upward_bar (list): Position of last upward | in the output.
            task_type (str): Entry or Exit
            called_by_tasks (list): List of Tasks this Task is called by.
            position_for_anchor (int): Location of the anchor point for the Task.

        Returns:
            tuple[bool, int]: found_tasks, last_upward_bar
    """
    # We have a full row of Profiles.  Print the Tasks out.
    if print_tasks:
        if output_task_lines:
            _flush_tasks(output_task_lines)
            output_task_lines = []
        last_upward_bar = []

    # Add quotes to called Tasks.
    found_tasks, last_upward_bar, output_task_lines = add_quotes(
        output_task_lines,
        last_upward_bar,
        task,
        task_type,
        called_by_tasks,
        position_for_anchor,
        found_tasks,
    )

    return found_tasks, last_upward_bar, output_task_lines


# Process all Tasks in the Profile
def print_all_tasks(
    tasks: defusedxml.ElementTree,
    position_for_anchor: int,
    output_task_lines: list,
    print_tasks: bool,
    found_tasks: list,
) -> list:
    """
    Process all Tasks in the Profile.

    Args:
        tasks (defusedxml.ElementTree): the Tasks in the Profile
        position_for_anchor (int): the position of the anchor point for the Task
        output_task_lines (list): the output lines for the Tasks
        print_tasks (bool): True if we are printing Tasks
        found_tasks (list): a list of Tasks found so far
        diagram (dict): the diagram dictionary of all data

    Returns:
        list: the list of Tasks found
    """
    # Keep track of the "|" bars in the output lines.
    last_upward_bar = []
    tasks_length = len(tasks)
    line_left_arrow_ascii = "&#11013;"
    line_right_arrow_ascii = "&#11157;"

    # Now process each Task in the Profile.
    for num, task in enumerate(tasks):
        if UNNAMED_ITEM in task["name"]:
            continue
        # Determine if this is an entry/exit combo.
        task_type = (" (entry)" if num == 0 else " (exit)") if tasks_length == 2 else ""

        # See if this Task is called by anyone else.  If so, add it to our list
        called_by_tasks = ""

        # First we must find our real Task element that matches this "task".
        # Strip the extra stuff out of the task name
        tname = task["name"].split("&nbsp;")[0]
        if line_left_arrow_ascii in tname:
            tname = tname.split(line_left_arrow_ascii)[0].strip()
        elif line_right_arrow_ascii in tname:
            tname = tname.split(line_right_arrow_ascii)[0].strip()
        task["name"] = tname

        # Is it in the master list of all Task names in the XML?
        task_name = PrimeItems.tasker_root_elements["all_tasks_by_name"][tname]
        if task_name:
            prime_task = task_name
            # Now see if this Task has any "called_by" Tasks.
            with contextlib.suppress(KeyError):
                called_by_tasks = f" [Called by {line_left_arrow} {flatten_with_quotes(prime_task['called_by'])}]"

        # We have a full row of Profiles.  Print the Tasks out.
        found_tasks, last_upward_bar, output_task_lines = output_the_task(
            print_tasks,
            found_tasks,
            task,
            output_task_lines,
            last_upward_bar,
            task_type,
            called_by_tasks,
            position_for_anchor,
        )

    return found_tasks


def process_scene_tasks(
    scene: str,
    position_for_anchor: int,
    task_list: list,
) -> tuple:
    """
    Process a Scene's Tasks.

    Args:
        scene (str): The Scene name to process.
        position_for_anchor (int): The position of the anchor point for the Task.
        task_list (list): List of tasks to add to.

    Returns:
        tuple: (task_list, output_task_lines)
    """
    output_task_lines = []

    # Retrieve XML elements inside the scene
    scene_xml = PrimeItems.tasker_root_elements["all_scenes"].get(scene, {}).get("xml", [])
    # Go through the scene elements, looking for "xxxElement"
    for sub_scene in scene_xml:
        sub_scene_tag = sub_scene.tag

        if not tag_in_type(sub_scene_tag, True):
            if sub_scene_tag in {"Str", "Int"}:
                break
            continue  # Skip elements that are not relevant

        # Retrieve element name if available
        element_name = sub_scene_tag
        arg0_element = sub_scene.find("./Str[@sr='arg0']")
        if arg0_element is not None:
            element_name = arg0_element.text or element_name

        # Go through the "xxxElement" sub-elements looking for a "xxxTask"
        for sub_element in sub_scene:
            sub_element_tag = sub_element.tag

            if sub_element_tag == "PropertiesElement":
                break  # No need to continue if we hit arguments

            if not tag_in_type(sub_element_tag, False):
                continue

            task_id = sub_element.text
            if not task_id or task_id.startswith("-"):
                continue  # Skip invalid or fake tasks

            # Retrieve task information
            task_info = PrimeItems.tasker_root_elements["all_tasks"].get(task_id)
            if not task_info:
                continue

            task = {
                "xml": task_info["xml"],
                "name": f"Element '{element_name}', {SCENE_TASK_TYPES[sub_element_tag]}: {task_info['name']}",
            }

            # Store the task
            task_list.append([task, position_for_anchor])

    if output_task_lines:
        _flush_tasks(output_task_lines)

    return task_list, output_task_lines


# Process all Scenes in the Project, 8 Scenes to a row.
def print_all_scenes(scenes: list) -> None:
    """
        Prints all scenes in a project, 8 Scenes to a row.

        Args:
    .
            scenes: List of scenes to print.

        Returns:
            None: Prints scenes to console.

        - Loops through each scene and prints scene number and outline.
        - Prints scenes in columns of 6 before resetting.
        - Includes header before each new column of scenes.
        - Prints any remaining scenes after loop.
    """
    # Set up for Scenes
    filler = f"{blank * 2}"
    scene_counter = 0
    output_scene_lines = [filler, filler, filler]
    scenes_translated = translate_string("Scenes:")
    task_list = []
    # Empty line to start
    add_output_line(" ")

    # Do all of the Scenes for the given Project
    for scene in scenes:
        scene_counter += 1
        if scene_counter > 8:
            # We have 8 columns.  Print them out and reset.
            include_heading(f"{blank * 7}{scenes_translated}", output_scene_lines)
            _flush_boxes(output_scene_lines)
            scene_counter = 1
            output_scene_lines = [filler, filler, filler]

        # Start/continue building our outlines
        output_scene_lines, position_for_anchor = build_box(scene, output_scene_lines)
        # Noted after the box is built, and after any flush above it, so the note belongs to
        # the buffer this Scene actually went into rather than to the row before it.
        _note_box(Target(kind=SCENE, key=scene, name=scene), f"{_BOX_WALL} {scene}")

        # Process Scene's Tasks
        task_list, output_task_lines = process_scene_tasks(
            scene,
            position_for_anchor + 15,
            task_list,
        )

    # Print any remaining Scenes
    include_heading(f"{blank * 7}{scenes_translated}", output_scene_lines)
    _flush_boxes(output_scene_lines)

    # Print out the Scenes' Tasks
    for task in task_list:
        # Output the Task
        _found_tasks, _last_upward_bar, output_task_lines = output_the_task(
            True,
            [],
            task[0],
            output_task_lines,
            task[1] + 15,
            "",
            "",
            task[1],
        )
    if task_list:
        _flush_tasks(output_task_lines)


# Process Tasks not in any Profile
def do_tasks_with_no_profile(
    project_name: str,
    output_profile_lines: list,
    output_task_lines: list,
    found_tasks: list,
    profile_counter: int,
) -> tuple:
    """
    Process Tasks not in any Profile
    Args:
        project_name: Project name in one line
        output_profile_lines: Output profile lines in one line
        output_task_lines: Output task lines in one line
        found_tasks: Found tasks list in one line
        profile_counter: Profile counter in one line
    Returns:
        output_profile_lines, output_task_lines: Updated output lines in one line
    Processing Logic:
        - Get task IDs not in any profile
        - Build profile box for tasks not in any profile
        - Print tasks not in any profile
    """
    # If no Project, just return
    if project_name == "No Project":
        return output_profile_lines, output_task_lines

    project_root = PrimeItems.tasker_root_elements["all_projects"][project_name]["xml"]
    tasks_not_in_profile = []

    # Get all task IDs for this Project.
    project_task_ids = get_ids(False, project_root, project_name, [])

    # Go through each Task ID and see if it is in found_tasks.
    for task in project_task_ids:
        if PrimeItems.tasker_root_elements["all_tasks"][task]["name"] not in found_tasks:
            profile = "No Profile"
            print_tasks = False
            the_task = PrimeItems.tasker_root_elements["all_tasks"][task]
            if the_task not in tasks_not_in_profile:
                tasks_not_in_profile.append(the_task)

    # Ok, do we have any Tasks that are not in any Profile?  If so, output them.
    # if not PrimeItems.program_arguments["single_profile_name"] and tasks_not_in_profile:
    # Build profile box
    if tasks_not_in_profile:
        (
            output_profile_lines,
            output_task_lines,
            position_for_anchor,
            print_tasks,
            profile_counter,
        ) = build_profile_box(
            profile,
            profile_counter,
            output_profile_lines,
            output_task_lines,
            print_tasks,
        )

        # Print tasks not in any profile
        print_tasks = False
        _ = print_all_tasks(
            tasks_not_in_profile,
            position_for_anchor,
            output_task_lines,
            print_tasks,
            found_tasks,
        )

    return output_profile_lines, output_task_lines


# Fill the designated line with arrows starting at the specified position.
def fill_line_with_arrows(
    line: str,
    arrow: str,
    line_length: int,
    call_task_position: int,
) -> str:
    """
    Fills spaces in a line with left/right arrows up to a specified position.
    Args:
        line: String to fill with arrows
        arrow: Arrow character to use for filling
        line_length: Desired length of output line
        call_task_position: Position to fill arrows up to
    Returns:
        output: String with spaces filled with arrows up to call_task_position
    Processing Logic:
        - Pad input line with spaces to specified line_length
        - Initialize output string with padded line up to call_task_position
        - Iterate through padded_line from call_task_position + 1 to end
        - Add arrow to output if character is a space
        - Otherwise add character from padded_line
    """

    # Pad input string with spaces to specified length
    padded_line = line.ljust(line_length)

    # Initialize output string
    output = padded_line[:call_task_position]

    # Fill spaces between call task position and end with left/right arrows
    len_padding = len(padded_line)
    if len_padding > call_task_position + 1:
        for i in range(call_task_position + 1, len_padding):
            # Only do arrow if first or last position.
            if (
                (i == call_task_position + 1 or i == len_padding)
                and padded_line[i] == " "
                and bar not in padded_line[i]
            ):
                output += arrow
            # If not first or last position, and character is a space, add straight line.
            elif padded_line[i] == " " and bar not in padded_line[i]:
                output += straight_line
            # Just add the padding character (spaces and bars)
            else:
                output += padded_line[i]
    else:
        output = padded_line

    return output


def extract_with_subset(str1: str, str2: str) -> list:
    # Split both strings by commas
    """
    Extracts parts from str2 that are also in str1 (split by commas).
    If a part of str2 matches a subset of str1, add the full subset as one element.
    Otherwise, add the current part of str2.
    Args:
        str1 (str): String with parts to subset
        str2 (str): String with parts to extract
    Returns:
        list: List of parts extracted from str2 with subsets of str1
    Processing Logic:
        - Split both strings by commas
        - Iterate through the parts of str2
        - Check if a slice from the current position matches the subset parts
        - If a match, add the full subset as one element
        - Otherwise, add the current part
    """
    parts = str2.split(",")
    parts = [item[1:] if item.startswith(" ") else item for item in parts]  # Remove leading spaces
    subset_parts = str1.split(",")
    subset_parts = [item[1:] if item.startswith(" ") else item for item in subset_parts]  # Remove leading spaces

    # Initialize an empty list for the result
    result = []
    i = 0

    # Iterate through the parts of str2
    while i < len(parts):
        # Check if a slice from the current position matches the subset parts
        if parts[i : i + len(subset_parts)] == subset_parts:
            # Add the full subset as one element
            result.append(str1)
            # Skip over the matched subset parts
            i += len(subset_parts)
        else:
            # Otherwise, just add the current part
            result.append(parts[i])
            i += 1

    return result


def get_index_setup(s: str, called_task_name: str) -> tuple:
    """
    Parse the 'calls' string and return a tuple of substrings and positions

    Args:
        s (str): The string to parse
        called_task_name (str): The name of the task being called

    Returns:
        tuple: A tuple of two values. The first value is a list of substrings
            extracted from the string, and the second value is a list of positions
            of the called task name in the string.

    Processing Logic:
        - Split the string into substrings based on the task delimeter
        - Cleanup the results
        - Find all positions of the called task name beyond the "Calls -->"
    """
    comma = ","
    search_marker = "Calls ──▶ "
    # Get a list of called tasks from the string
    start_search = s.find(search_marker) + 9
    # Early exit if the marker is not found
    if start_search == -1 + len(search_marker):
        return -1

    # Extract the relevant substring after "Calls ──▶ "
    temp_line = s[start_search:].split("]", maxsplit=1)[0].strip()
    close_bracket_pos = temp_line.find("]")
    if close_bracket_pos != -1:
        temp_line = temp_line[:close_bracket_pos]

    # Figure out how we are going to parse the 'calls' string
    delimiter = task_delimeter if task_delimeter in s else comma
    # Deal with commas in the called task name
    if delimiter == comma and comma in called_task_name:
        substrings = extract_with_subset(called_task_name, temp_line)
    else:
        # Split the string into substrings based on the task delimeter.
        temp_list = temp_line.split(delimiter)
        # Cleanup the results.
        temp_list = [item[1:] if item.startswith(" ") else item for item in temp_list]  # Remove leading spaces
        substrings = []
        for item in temp_list:
            item_to_add = item[1:] if item.startswith(" ") else item
            if item_to_add and item_to_add not in ("]", ", "):
                substrings.append(item_to_add)

    # Find all positions of the called task name beyond the "Calls -->".
    string_without_delimiters = s.replace(task_delimeter, "") if delimiter == task_delimeter else s
    start_search = string_without_delimiters.find("Calls ──▶ ") + 9
    positions = find_all_positions(
        string_without_delimiters,
        called_task_name,
        start_search,
    )

    return substrings, positions


def get_index_by_middle_char_position(
    s: str,
    middle_char_position: int,
    called_task_name: str,
) -> int:
    # Split the string into substrings based on commas
    """
    Finds and returns the index of a called task based on its middle character position.

    Args:
        s (str): The string containing the task call information.
        middle_char_position (int): The position of the middle character of the called task name.
        called_task_name (str): The name of the called task to find.

    Returns:
        int: The index of the called task if found, otherwise -1.

    In the following example, we need to come up with the index '3', for the third line/index below the 'called_task_name'
    in the 's' string based on the middle_char_position.
    caller_task_name [Called by <-- ..., ...] [Calls --> called_task_name1, called_task_name, called_task_name4]


                                                                                 ╰ (this '3rd' line) result = 3
    """
    # Setup for getting the index.
    substrings, positions = get_index_setup(s, called_task_name)

    # Now get the index of this specific, called task based on it's middle character position...
    # bisect.bisect_left(sorted_list, number) returns the index at which number should be inserted in sorted_list to maintain its order.
    item_index = bisect_left(positions, middle_char_position)
    task_tracker = 0
    # Iterate over the positions found for the called task name.
    for current_position in positions:
        # Iterate through the substrings with their indices
        for index, substring in enumerate(substrings):
            if substring != called_task_name or substring == ", ":
                continue
            # Calculate the ending position for this substring
            end_position = current_position + len(substring)

            # Check if the middle character position falls within this substring's range
            if current_position <= middle_char_position < end_position:
                task_tracker += 1
                if task_tracker == item_index:
                    return index + 1  # Return the index if the position is within the range

    # If the position is out of range, return -1
    return -1


def find_diagram_connector_seed_cell(lines: list, row: int, col: int) -> tuple | None:
    """
    Locate the actual connector character for a recorded (row, col) seed in the final text.

    A seed's row is exact (tracked through every line-count-changing pass), but its column can be
    off by a little on rows where icon-alignment trimming or task_delimeter cleanup shifted
    characters after the seed was recorded -- so search outward from the recorded column, on that
    same row, for the nearest connector character.
    """
    if not (0 <= row < len(lines)):
        return None
    line = lines[row]
    if 0 <= col < len(line) and line[col] in CONNECTOR_DIRECTIONS:
        return (row, col)
    for offset in range(1, 25):
        for c in (col - offset, col + offset):
            if 0 <= c < len(line) and line[c] in CONNECTOR_DIRECTIONS:
                return (row, c)
    return None


def compute_diagram_connector_groups(lines: list, seeds: list) -> dict:
    """
    Identify every Diagram-view connector -- the lines, corners and arrows joining a "calls" Task
    to its "called by" Task -- directly from the final rendered text, growing each one out from a
    seed cell recorded while it was drawn (see draw_arrows_to_called_task()).

    Earlier approaches tried to track every column a connector owns while it was being drawn, but
    several later passes (gap/missing-bar cleanup, icon-alignment trimming, project-spacer
    insertion) rewrite characters on the same lines without updating that bookkeeping, so the
    recorded columns drift out of sync with what's actually on screen. Growing connectors from a
    seed on the finished text instead can't drift, since there's nothing left to happen to it
    afterward -- the seed only needs to land somewhere on the connector, not trace its whole path.

    A plain flood fill by character identity alone doesn't work here either: ordinary tree/outline
    hierarchy guide lines reuse these same box-drawing characters, and an outer connector's
    horizontal run can pass directly alongside an unrelated inner connector's (or a guide line's)
    vertical run. CONNECTOR_DIRECTIONS records which side(s) of each character continue a
    connector's path, so two cells only join if each is actually reaching toward the other (e.g. a
    straight run never reaches sideways into a bar it merely passes next to) -- and growth only
    starts from a known-good seed, so unrelated guide lines never get pulled in at all.

    Two more gaps in a straight run need bridging past the same way:

    - fill_line_with_arrows() only overwrites blank cells, so when one connector's run crosses
      another's, whichever was drawn first is left sitting, untouched, in the middle of the second
      one's straight run (e.g. a foreign down_arrow marking where an unrelated connector's own
      vertical descent ends, stranded mid-dash). That foreign cell doesn't reach back (its own
      directions don't point the right way), which would otherwise split the crossed run in two
      right where a user is likely to click.
    - A vertical descent can also pass behind a multi-line Task description that a text-cleanup
      pass left with genuinely blank cells in the connector's column instead of bar characters
      (nothing to reach back at all, since there's nothing there).

    Either way, what should be one continuous run gets interrupted by a short stretch of cells
    that aren't a continuation themselves -- so a cell that fails the direct check looks a few
    cells further out along the same direction for where its own line resumes, bridging over
    whatever's in between (foreign character or blank) without ever visiting/claiming it, leaving
    any foreign cells free to belong only to their own connector's group.

    Returns a dict of {group_id: [(line_num, col_start, col_end), ...]}, matching the structure the
    GUI Diagram view (guiwins.py) expects in PrimeItems.diagram_connectors.

    Each seed also names the call it was dropped for (see draw_arrows_to_called_task), and
    that travels with the group it grows into: PrimeItems.diagram_connector_calls ends up
    holding {group_id: [call index, ...]}, which is what lets the interactive view follow a
    chain of calls from connector to connector rather than treating each as an unrelated
    run of characters.  A list rather than one index because two calls whose runs touch are
    one group -- geometry decides the groups, and the calls that fall in one all claim it.
    """
    # How many cells of interruption (foreign connector characters and/or blanks) a straight run
    # can bridge over before giving up and treating the run as genuinely ended.
    max_bridge = 4

    def reachable_neighbors(r: int, c: int) -> list:
        found = []
        for dr, dc in CONNECTOR_DIRECTIONS[lines[r][c]]:
            nr, nc = r + dr, c + dc
            for _ in range(max_bridge + 1):
                if not (0 <= nr < len(lines)) or not (0 <= nc < len(lines[nr])):
                    break
                nchar = lines[nr][nc]
                if nchar in CONNECTOR_DIRECTIONS and (-dr, -dc) in CONNECTOR_DIRECTIONS[nchar]:
                    found.append((nr, nc))
                    break
                # Not a continuation -- keep looking past it only if it's something a real,
                # unrelated line (box border, task text, ...) would never sit on top of.
                if nchar not in CONNECTOR_DIRECTIONS and nchar != " ":
                    break
                nr, nc = nr + dr, nc + dc
        return found

    visited: set = set()
    groups: dict = {}
    group_of_cell: dict = {}
    calls_by_group: dict = {}
    group_id = 0

    for row, col, call_index in seeds:
        seed_cell = find_diagram_connector_seed_cell(lines, row, col)
        if seed_cell is None:
            continue
        # A seed landing on a connector already grown from an earlier seed adds its call to
        # that group rather than being discarded: three seeds are dropped per call, and two
        # calls whose runs touch share the one group.
        if seed_cell in visited:
            existing = group_of_cell.get(seed_cell)
            if existing is not None and call_index not in calls_by_group[existing]:
                calls_by_group[existing].append(call_index)
            continue

        # Flood-fill this connector's connected cells, following only the directions each
        # character actually continues the path in.
        cells = []
        stack = [seed_cell]
        visited.add(seed_cell)
        while stack:
            r, c = stack.pop()
            cells.append((r, c))
            for nr, nc in reachable_neighbors(r, c):
                if (nr, nc) in visited:
                    continue
                visited.add((nr, nc))
                stack.append((nr, nc))

        groups[group_id] = cells
        calls_by_group[group_id] = [call_index]
        for cell in cells:
            group_of_cell[cell] = group_id
        group_id += 1

    # Compact each group's cells into per-row (line_num, col_start, col_end) ranges.
    ranges_by_group: dict = {}
    for gid, cells in groups.items():
        by_row: dict = {}
        for r, c in cells:
            by_row.setdefault(r, []).append(c)
        ranges = []
        for r, cols in by_row.items():
            cols.sort()
            start = prev = cols[0]
            for col in cols[1:]:
                if col == prev + 1:
                    prev = col
                    continue
                ranges.append((r, start, prev + 1))
                start = prev = col
            ranges.append((r, start, prev + 1))
        ranges_by_group[gid] = ranges

    PrimeItems.diagram_connector_calls = calls_by_group
    return ranges_by_group


# Add up and down arrows to the connection points.
def add_down_and_up_arrows(connectors: dict, output_lines: list) -> None:
    """
    Adds down and up arrows between caller and called tasks.
    Args:
        connectors (dict): containert for...
            caller_line_index: {Caller task line index in the list}
            caller_line_num: {Caller task line number}
            caller_task_position: {Caller task position}
            called_line_index: {Called task line index}
            called_line_num: {Called task line number}
            called_task_position: {Called task position}
            up_down_location: {Arrow location}
        output_lines: {Output lines list}
    Returns:
        output_lines: {Modified output lines list with arrows added}
    Processing Logic:
        - Add right arrows to caller Task line
        - Add a down arrow
        - Add left arrows to called Task line
        - Add an up arrow
    """
    # Break out the arguments
    caller_line_index = connectors["caller_line_index"]
    caller_line_num = connectors["caller_line_num"]
    caller_task_position = connectors["caller_task_position"]
    called_line_index = connectors["called_line_index"]
    called_line_num = connectors["called_line_num"]
    called_task_position = connectors["called_task_position"]
    up_down_location = connectors["up_down_location"]

    line_to_modify = caller_line_num + caller_line_index

    # Add right arrows to caller Task line (e.g. fill the line with blanks/straight-line to the start position).
    output_lines[line_to_modify] = fill_line_with_arrows(
        output_lines[line_to_modify],
        right_arrow,
        up_down_location,
        called_task_position,
    )

    # Add a down to right elbow under the task being called ([Calls --> ...]).
    output_lines[line_to_modify] = (
        output_lines[line_to_modify][:called_task_position]
        + right_arrow_corner_down
        + output_lines[line_to_modify][called_task_position:]
    )
    # Extra seed for the GUI's click-to-highlight feature, redundant with the one recorded in
    # draw_arrows_to_called_task(): this corner is a second guaranteed-good anchor into the same
    # connector, so the connector still gets a working seed even if one of the two is ever thrown
    # off (e.g. by an unrelated bug in a later cleanup pass). See compute_diagram_connector_groups().
    PrimeItems.diagram_connector_seeds.append((line_to_modify, called_task_position, connectors["call_index"]))

    # Add left arrows to called Task line.  First find next available blank line.
    line_to_modify1 = called_line_num - called_line_index
    line_count = 0
    while output_lines[line_to_modify1] and output_lines[line_to_modify1][caller_task_position] != " ":
        line_to_modify1 -= 1
        line_count += 1
        if line_count > 20:
            if PrimeItems.program_arguments["debug"]:
                rutroh_error(
                    f"Too many iterations trying to find next blank line to modify.  Possible infinite loop.  Line to modify: {line_to_modify1}  Line: {output_lines[line_to_modify1]} Length: {len(output_lines)}",
                )
            else:
                logger.error(
                    f"Unable to find next blank line to modify.  Line to modify: {line_to_modify1}  Line: {output_lines[line_to_modify1]}",
                )
            break
    # line_to_modify1 = called_line_num - called_line_index
    output_lines[line_to_modify1] = fill_line_with_arrows(
        output_lines[line_to_modify1],
        left_arrow,
        up_down_location,
        caller_task_position,
    )
    # Add an left corner down arrow.
    output_lines[line_to_modify1] = (
        output_lines[line_to_modify1][:caller_task_position]
        + left_arrow_corner_down
        + output_lines[line_to_modify1][caller_task_position:]
    )
    # Extra seed -- see the matching comment above for right_arrow_corner_down.
    PrimeItems.diagram_connector_seeds.append((line_to_modify1, caller_task_position, connectors["call_index"]))

    # Return the top-most modified output line hnumber.
    return line_to_modify, line_to_modify1


# Draw arrows to called Task from Task doing the calling.
def draw_arrows_to_called_task(
    up_down_location: int,
    connector: list,
    output_lines: list,
    called_task_lookup: dict,
) -> None:
    """
    Draw arrows to called Task from Task doing the calling.
        Args:
            up_down_location (int): Position on line where the up or down arrow should be drawn.
            connector (list): List of all call table connectors.
            output_task_lines (list): List of all output lines.
            called_task_lookup (dict): Dictionary of called task tracker.

        Returns:
            None: called_task_lookup
    """
    # Get connectors for caller and called Task.
    # caller_task_name = connector["caller_task_name"]
    caller_line_num = connector["caller_line_num"]
    caller_task_position = connector["caller_task_position"]
    called_task_name = connector["called_task_name"]
    called_line_num = connector["called_line_num"]
    called_task_position = connector["called_task_position"]
    arrow = connector["arrow"]
    upper_corner_arrow = connector["upper_corner_arrow"]
    lower_corner_arrow = connector["lower_corner_arrow"]
    # fill_arrow = connector["fill_arrow"]
    start_line = connector["start_line"]
    line_count = connector["line_count"]

    caller_line_index = get_index_by_middle_char_position(
        output_lines[caller_line_num],
        called_task_position,
        called_task_name,
    )
    if caller_line_index == -1:
        rutroh_error(
            f"Unable to find line index for {called_task_name} in {output_lines[caller_line_num]}",
        )

    # Bump the count of the calls to this task.  This is used to determine the displacement of the bottom connector line number.
    PrimeItems.called_task_tracker[called_task_name]["counter"] += 1

    # The call this connector is about to be drawn for, recorded before any of it is drawn:
    # the two Task lines it joins are known here and nowhere further down, and every seed
    # dropped below carries this index so the finished connector can be traced back to it.
    call_index = len(PrimeItems.diagram_call_edges)
    PrimeItems.diagram_call_edges[call_index] = {
        "caller_row": caller_line_num,
        "called_row": called_line_num,
        "caller_name": connector.get("caller_task_name", ""),
        "called_name": called_task_name,
        "project": connector.get("project_name", ""),
    }

    # Add up and down arrows to the connection points.
    connectors = {
        "caller_line_index": caller_line_index,
        "caller_line_num": caller_line_num,
        "caller_task_position": caller_task_position,
        "called_line_index": PrimeItems.called_task_tracker[called_task_name]["counter"],
        "called_line_num": called_line_num,
        "called_task_position": called_task_position,
        "up_down_location": up_down_location,
    }
    connectors["call_index"] = call_index
    line_to_modify, line_to_modify1 = add_down_and_up_arrows(connectors, output_lines)

    # Fill called line with left arrows.  Figure out if we are top-down or bottom-up,
    # and assign start_line and line_count accordingly.
    if called_line_num > caller_line_num:
        start_line = line_to_modify
        # Take into account the index of the current "calls ->" called Task
        line_count -= line_to_modify - (caller_line_num - PrimeItems.called_task_tracker[called_task_name]["counter"])
    else:
        # Find the first free line above the called Task
        start_line = line_to_modify1
        line_count = line_to_modify - start_line

    # Record a seed for the GUI's click-to-highlight feature: output_lines[start_line] always gets
    # upper_corner_arrow (a non-bar connector character) at up_down_location below, in the loop's
    # x == 0 case, so this cell is guaranteed to survive remove_empty_strings() (which only drops
    # lines that are nothing but bar/space/backslash). See compute_diagram_connector_groups().
    PrimeItems.diagram_connector_seeds.append((start_line, up_down_location, call_index))

    # Now traverse the output list from the calling/called Task to the called/calling Task,
    # inserting a up/down/corner arrow along the way.
    for x in range(line_count + 1):
        # Determine which arrow to use.
        if x == 0:
            use_arrow = upper_corner_arrow
        elif x == line_count:
            use_arrow = lower_corner_arrow
        else:
            use_arrow = arrow
            # Just do the first and last up/down/right/left arrow.
            if x != 1 and x != line_count - 1:
                use_arrow = straight_line if arrow in (left_arrow, right_arrow) else bar

        # Add initial/ending up/down arrow or bar/straight line.

        # If there are bars inside of up_down_location, then we need to leave them there.
        temp_line = output_lines[start_line + x].replace(task_delimeter, "")
        temp_line = temp_line.ljust(up_down_location)
        front_line = temp_line[:up_down_location]
        # Adjust bars if there are task delimeters in the line.
        # Some lines still have delimeters.  We need to fix the bars beyond the delimeters so they align properly
        # ith the bars above them.
        delimeters = find_all_positions(output_lines[start_line + x], task_delimeter)
        if delimeters:
            bars = find_all_positions(temp_line, bar)
            for bar_position in bars:
                if bar_position > delimeters[-1]:  # Only if the bar is beyond the last delimiter.
                    delimeter_length = len(delimeters)
                    temp_line = front_line
                    front_line = (
                        temp_line[:bar_position]
                        + f"{blank * delimeter_length}{bar}"
                        + temp_line[bar_position + delimeter_length + 1 :]
                    )
        # Put it all together.
        back_line = temp_line[up_down_location + 1 :]
        new_line = f"{front_line}{use_arrow}{back_line}"
        output_lines[start_line + x] = new_line

    return called_task_lookup


# Find and flag in the output those called Tasks that don't exist.
def mark_tasks_not_found(output_lines: list) -> None:
    """
    Mark tasks not found in output lines
    Args:
        output_lines: List of output lines to search
    Returns:
        None: Function does not return anything
    - Iterate through each line in output lines
    - Check if line contains "Task not found" string
    - If found, mark line number in a list for later processing
    """
    for caller_line_num, line in enumerate(output_lines):
        if line_right_arrow in line:
            # Get the called Task name.
            start_position = line.index(line_right_arrow) + 4
            called_task_names = line[start_position:].split(", ")

            # Go through list of calls to Tasks from this caller Task.
            track_task_name = []
            for called_task_name in called_task_names:
                # Get the called Task name.
                called_task_name = called_task_name.lstrip()  # noqa: PLW2901
                called_task_name = called_task_name.split("]")  # noqa: PLW2901
                # Track the number of instances of the called Task.
                called_name = called_task_name[0].replace("]", "")
                called_name_no_delimeter = called_name.replace(task_delimeter, "")
                # Add the task name to track it, and get the count of the number of times it appears in the line.
                track_task_name.append(called_name_no_delimeter)
                num_called_task = track_task_name.count(called_name_no_delimeter)

                # Don't bother with variables since we know these won't be found.
                if called_task_name[0][1] == "%":
                    continue

                #  Find the "Called" Task line for the caller Task.
                search_name = f"{angle}{called_name_no_delimeter}"

                # Make sure the called Task exists.
                found_called_task = False
                for check_line in output_lines:
                    if search_name in check_line:
                        found_called_task = True
                        called_task_position = check_line.index(
                            called_name_no_delimeter,
                        )
                        break

                # If Task doesn't exist, mark it as such.
                not_found = " (Not Found!)"
                if not found_called_task:
                    # Find the nth occurance of the called Task
                    called_task_position = find_nth(
                        line,
                        called_name,
                        num_called_task,
                        0,
                    )
                    end_of_called_task_position = called_task_position + len(
                        called_task_name[0],
                    )

                    # Reconstruct the line
                    output_lines[caller_line_num] = (
                        output_lines[caller_line_num][:called_task_position]
                        + called_task_name[0]
                        + not_found
                        + output_lines[caller_line_num][end_of_called_task_position:]
                    )
                    line = output_lines[caller_line_num]  # noqa: PLW2901


def mysizeof(my_dict: list) -> int:
    """
    Calculate the total size of a list in bytes, including the size of all its elements.

    Args:
        my_dict (list): The dictionary to calculate the size of.

    Returns:
        int: The total size of the list in bytes.
    """
    total = 0
    for _, _ in my_dict.items():
        total += 1
    return total


def furthest_connector_line(connector: dict) -> int:
    """The last diagram line a connector touches -- it needs every line between its two ends."""
    return max(connector["caller_line_num"], connector["called_line_num"])


def check_limit(call_table: dict, output_lines: list, _progress_bar: dict) -> None:
    """
    Cut the diagram short at the view limit rather than refusing to draw it at all.

    This used to bail out entirely -- error message, everything thrown away, no diagram -- which
    left a large configuration with nothing to look at.  The Map view has always handled its own
    limit by writing out as much as the limit allows and saying so (bildhtml.write_out_the_file),
    and this now does the same: the diagram is drawn from the top down to the point where the
    limit is reached, and PrimeItems.diagram_limit_msg says how much was left off.

    The call table is what the limit is measured against, since every entry in it is a connector
    that has to be drawn across the diagram -- so the budget is spent in connectors, and the
    diagram is cut at the last line the affordable ones reach.  That keeps the work this limit
    exists to cap capped, while still showing the user the part of the diagram it paid for.

    Args:
        call_table (dict): The caller/called connectors, keyed by an arbitrary unique key.
        output_lines (list): The diagram built so far, one string per line.
        _progress_bar (dict): The progress bar to update.

    Returns:
        tuple: (line to cut the finished diagram at or None to keep all of it, the connectors to
            draw).  The cut is applied by the caller once the arrows are drawn, not here: the
            drawing routines reach a few lines beyond a connector's own two ends (see
            add_down_and_up_arrows), so the lines have to still be there while it works.
    """
    # Only the GUI's views are limited; a command-line run writes the whole thing to a file.
    if not PrimeItems.program_arguments["guiview"]:
        return None, call_table

    # Cleared per run: a diagram that fits must not inherit the message from one that did not.
    PrimeItems.diagram_limit_msg = ""

    # size = mysizeof(call_table)
    # size = getSize(call_table)
    size = mysizeof(call_table) * 67
    view_limit = PrimeItems.program_arguments["view_limit"]
    if size <= view_limit:
        return None, call_table

    # Over the limit.  Work out how many connectors that budget buys, and keep the ones nearest
    # the top of the diagram: a connector is only drawable if both of its ends survive the cut,
    # so ordering by the furthest line each one reaches is what makes the kept set contiguous
    # from the top rather than scattered down a diagram whose lower half has been removed.
    max_connectors = max(1, view_limit // 67)
    by_position = sorted(call_table.items(), key=lambda item: furthest_connector_line(item[1]))
    kept = dict(by_position[:max_connectors])

    # Cut just past the last line the kept connectors need, so none of them is left dangling.
    cut_at = max(furthest_connector_line(connector) for connector in kept.values()) + 1
    total_connectors = mysizeof(call_table)
    lines_dropped = max(0, len(output_lines) - cut_at)

    PrimeItems.diagram_limit_msg = (
        f"{translate_string('MapTasker: view limit reached, diagram truncated')}: "
        f"{translate_string('connectors')}={len(kept)}/{total_connectors}, "
        f"{translate_string('lines dropped')}={lines_dropped}, "
        f"{translate_string('View Limit')}={view_limit}.  "
        f"{translate_string('Select a larger View Limit or a single Project / Profile / Task to see the rest.')}"
    )
    logger.info(PrimeItems.diagram_limit_msg)

    # The connectors being dropped can be a lot of memory on the configurations that get here,
    # and nothing refers to them once this returns.
    gc.collect()

    return cut_at, kept


def cleanup_task_names(output_lines: list, num: int, line: str) -> list:
    """
    Handle special character around Task names.  Remove all quotes and add equivelent spaces after last '].

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.
        line (str): The current line.

    Returns:
        list: The modified list of strings.
    """
    occurences = [i for i, c in enumerate(line) if c == task_delimeter]

    # Add a space beyond last ] for each occurenceof the task delimiter.
    if occurences:
        # Replace task_delimeter only if there are occurrences
        output_lines[num] = output_lines[num].replace(task_delimeter, "")

        # Find call position more efficiently
        call_position = output_lines[num].find(f" [Calls {line_right_arrow}")
        if call_position == -1:
            call_position = output_lines[num].find(f" [Called by {line_left_arrow}")

        if call_position != -1:
            # Find the position of the closing bracket efficiently
            brackets_position = output_lines[num].find("]", call_position + 8)

            if brackets_position != -1:
                # Calculate the number of occurrences and construct the new line
                num_occurences = len(occurences)
                output_lines[num] = (
                    output_lines[num][: brackets_position + 1]
                    + (blank * num_occurences)
                    + output_lines[num][brackets_position + 1 :]
                )
        elif PrimeItems.program_arguments["debug"]:
            print("Rutroh!  Diagram: No call position found in line", num, line)
        else:
            logger.error(
                "Rutroh!  Diagram: No call position found in line %s %s",
                num,
                line,
            )
    return output_lines


def cleanup_dangling_elbows(output_lines: list, num: int) -> list:
    """
    Check for dangling elbows and fix them.

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.

    Returns:
        list: The modified list of strings.
    """
    elbow = output_lines[num].find(left_arrow_corner_up)
    if elbow != -1 and output_lines[num][elbow - 1] == " ":  # Check for dangling elbows
        output_lines[num] = output_lines[num][: elbow - 1] + right_arrow_corner_down + output_lines[num][elbow:]

    elbow = output_lines[num].find(" ───╯")
    if elbow != -1:  # Check for dangling elbows
        output_lines[num] = output_lines[num][:elbow] + left_arrow_corner_down + output_lines[num][elbow + 1 :]
    return output_lines


# Pre-compile the regex pattern outside the function to maximize performance.
# This matches: "straight_line" followed by a space, followed by "straight_line"
# Using a lookahead (?=...) ensures overlapping matches are caught cleanly.
MISSING_BAR_PATTERN = re.compile(f"({re.escape(straight_line)}) (?={re.escape(straight_line)})")


def cleanup_missing_straight_lines(output_lines: list, num: str, line: str) -> list:
    """
    Add missing straight lines in which there is one or more blanks before "╯" or missing bars: "straight_line space straight_line".
    Replace the space with a straight line and replace all single-quotes with a blank.
    If last position is a bracket, just continue.
    Args:
        output_lines (list): List of strings representing the output lines.
        num (str): The current line number.
        line (str): The current line string.
    Returns:
        list: The modified list of strings.

    Optimized version utilizing native string methods and regex to eliminate the while loop.
    """
    # 1. Handle "straight_line space straight_line" pattern using regex
    # Replaces the space with the straight_line variable
    line = MISSING_BAR_PATTERN.sub(rf"\1{straight_line}", line)

    # 2. Handle "space right_arrow_corner_up" pattern using native string replace
    # Equivalent to checking new_string[i] == corner and new_string[i-1] == " "
    line = line.replace(f" {right_arrow_corner_up}", f"{straight_line}{right_arrow_corner_up}")

    # 3. Handle the hardcoded block replace
    line = line.replace("  ─╯", "───╯")

    # 4. If the last position is a bracket, strip out the task_delimeter
    if line.endswith("]"):
        line = line.replace(task_delimeter, "")

    # Save back to the array (ensuring the index is an integer)
    output_lines[int(num)] = line

    return output_lines


def cleanup_missing_bars(output_lines: list, num: int, position: int) -> list:
    """
    Cleanup missing bars in the diagram.

    Args:
        output_lines (list): List of strings representing the output lines.
        num (int): The current line number.
        position (int): The current position in the substring.

    Returns:
        list: The modified list of strings.
    """

    def adjust_position_for_arrow(position: int) -> int:
        """Adjust position if there's a right arrow corner down to the left."""
        if output_lines[num][position - 1] == right_arrow_corner_down:
            return position - 1
        return position

    def insert_bar_if_blank(new_line: str, position: int) -> str:
        """Insert a bar at the position if there are two blank spaces."""
        if new_line[position - 1] == " " and new_line[position] == " ":
            return new_line[:position] + bar + new_line[position + 1 :]
        return new_line

    def process_elbows(previous_line_num: int, position: int) -> int:
        """Handle cases where the current character is an elbow."""
        new_line = output_lines[previous_line_num]
        _insert_bar_if_blank = insert_bar_if_blank
        while output_lines[num][position] == angle_elbow:
            if len(new_line) <= position:
                new_line = new_line.ljust(position + 1, " ")
            if new_line[position] == straight_line or new_line[position] == " ":
                output_lines[previous_line_num] = _insert_bar_if_blank(
                    new_line,
                    position,
                )
                previous_line_num -= 1
                new_line = output_lines[previous_line_num]
            elif new_line[position] == box_line:
                return -1
            else:
                previous_line_num -= 1
                if previous_line_num == -1:
                    break
                new_line = output_lines[previous_line_num]
        return previous_line_num

    previous_line_num = num - 1

    # Backup a position if "╰" is found just before position.
    position = adjust_position_for_arrow(position)

    # Now go through and insert a bars as necessary
    _insert_bar_if_blank = insert_bar_if_blank
    _process_elbows = process_elbows
    while previous_line_num >= 0:
        new_line = output_lines[previous_line_num]

        # Pad line if necessary
        if len(new_line) < position:
            new_line = new_line.ljust(position + 1, " ")

        # Check for blank spaces to insert bar
        if new_line[position - 1] == " " and new_line[position] == " ":
            output_lines[previous_line_num] = _insert_bar_if_blank(new_line, position)
            previous_line_num -= 1
        elif output_lines[num][position] == angle_elbow:
            previous_line_num = _process_elbows(previous_line_num, position)
            if previous_line_num == -1:
                break
        else:
            break

    return output_lines


# Go through the diagram looking for and fixing misc. screwed-up stuff.
def cleanup_diagram(
    output_lines: list,
    progress: dict,
) -> list:
    """
    Cleanup the diagram by adding missing straight lines and replacing spaces.
    """
    total_lines = len(output_lines)

    for num, line in enumerate(output_lines):
        # Add missing straight lines in which there is one or more blanks before "╯".
        output_lines = cleanup_missing_straight_lines(output_lines, num, line)

        # Cleanup Task names.
        output_lines = cleanup_task_names(output_lines, num, line)

        # Cleanup dangling elbow " ╮"
        output_lines = cleanup_dangling_elbows(output_lines, num)

        # Cleanup missing bars above Task angles.
        special_deliminaters = [
            angle_elbow,
            right_arrow_corner_down,
            left_arrow_corner_up,
        ]
        _substr, position = find_first_substring_position(line, special_deliminaters)
        if position != -1 and line[position - 1][0] == " ":
            output_lines = cleanup_missing_bars(output_lines, num, position)

        # OPTIMIZED: Update progress text smoothly during large operations without crashing performance
        if "progress_bar" in progress and num % 50 == 0:
            progress["status_label"].set_text(f"Cleaning layout structures: line {num} / {total_lines}")

    # Delete hanging bars "│" and substitute every arrow with beginning and end arrows only.
    return delete_hanging_bars(output_lines)


def find_first_substring_position(string: str, substrings: list) -> tuple:
    """
    Finds the first occurrence of a substring in a string from a list of substrings.

    Args:
        string (str): The string to search in.
        substrings (list): A list of substrings to search for.

    Returns:
        tuple: A tuple where the first item is the substring found and the second item is the index of the substring found.
        If no substrings are found, the first item is None and the second item is -1.
    """
    for substr in substrings:
        index = string.find(substr)
        if index != -1:  # If the substring is found
            return substr, index
    return None, -1


def add_blanks_above_called_tasks(output_lines: list) -> None:
    # Go through and add blanks above called tasks, one for each caller.
    """
    Goes through the output lines and adds a blank line above each called task line
    for each caller task.  The number of blank lines added is determined by the
    number of times each Task is called.  The new output lines are returned.
    """
    name_stoppers = ["(entry)", "(exit)", "[Called by ", "[Calls "]
    new_output_lines = []
    # Where each line ends up once the blanks have been inserted above it.  Every object
    # recorded while the diagram was drawn is sitting on one of these lines, and this is the
    # first of the four steps that move it (see the note above flatten_with_quotes).
    old_to_new = {}
    for old_row, line in enumerate(output_lines):
        task_line = line.find(angle)
        if task_line != -1:
            # We have a task line.  Now get the Task name.
            _, end_name = find_first_substring_position(line, name_stoppers)
            task_name = line[task_line + 3 : end_name - 1] if end_name != -1 else line[task_line + 3 : len(line) - 1]
            # Do we have a task that has been called by another task?
            # One extra for a blank line between upper and previous called task lower connectors.
            if task_name in PrimeItems.called_task_tracker:
                new_output_lines.extend(
                    [
                        ""
                        for _ in range(
                            PrimeItems.called_task_tracker[task_name]["total_number"] + 2,
                        )
                    ],
                )

        # Add the original line to the new output lines.
        old_to_new[old_row] = len(new_output_lines)
        new_output_lines.append(line)

    output_lines.clear()
    _remap_object_seeds(old_to_new)
    return new_output_lines


# If Task line has any "Task Call" Task actions, fill it with arrows.
def handle_calls(output_lines: list, progress: dict) -> None:
    """
    Handle calls in output lines from parsing
    Args:
        output_lines: output lines from parsing in one line
        progress: progress bar dictionary
    Returns:
        output_lines: output lines with arrows added in one line
    Processing Logic:
    - Identify called Tasks that don't exist
    - Create the table of caller/called Tasks and their pointers
    - Traverse the call table and add arrows to the output lines
    - Remove all icons from the names to ensure arrow alignment
    """
    # Seeds for the GUI Diagram view's click-to-highlight feature -- see
    # draw_arrows_to_called_task() and compute_diagram_connector_groups(). Set this
    # unconditionally up front (rather than further down, past the exceeded_limit early
    # return below) so build_network_map()'s later read of this attribute never sees it
    # missing just because the map was too large to fully draw.
    #
    # Each seed is (row, column, call index): which of the calls below it belongs to, so
    # that the connector grown from it can be named as "Backup calls Restore" rather than
    # as an anonymous run of box-drawing characters.  That is what turns one connector
    # into a link in a call chain the interactive view can follow.
    PrimeItems.diagram_connector_seeds = []
    # One entry per call drawn, keyed by the index the seeds refer to it by: {caller_row,
    # called_row, caller_name, called_name, project}, rows in output_lines' own numbering
    # here and remapped onto the rendered file's alongside the seeds.  Keyed rather than a
    # plain list because a remap DROPS the calls whose lines no longer exist, and a seed
    # already holding index 7 must not be left pointing at whatever slid into that slot.
    PrimeItems.diagram_call_edges = {}

    # Go through the output and add blanks above the called tasks, one for each caller.
    output_lines = add_blanks_above_called_tasks(output_lines)

    # Recaluate progress bar size.
    progress["max_data"] = len(output_lines)
    progress["tenth_increment"] = progress["max_data"] // 10

    # Identify called Tasks that don't exist and add blank lines for called/caller Tasks.
    mark_tasks_not_found(output_lines)

    # Create the table of caller/called Tasks and their pointers.
    call_table = build_call_table(output_lines)

    # Check if we have exceeded our maximum size limit.  Over it, this hands back only the
    # connectors that fit and the line to cut the diagram at once they have been drawn.
    cut_at, call_table = check_limit(
        call_table,
        output_lines,
        progress,
    )

    # Fix overlapping connectors that have the same up/down locations.
    call_table = fix_duplicate_up_down_locations(call_table)
    # Finally, sort it by up/down location (inner locations before outer).
    call_table = dict(
        sorted(call_table.items(), key=lambda item: item[1]["up_down_location"]),
    )

    # Now traverse the call table and add arrows to the output lines.
    called_task_lookup = {}
    for connector in call_table.values():
        called_task_lookup = draw_arrows_to_called_task(
            connector["up_down_location"],
            connector,
            output_lines,
            called_task_lookup,
        )

    # Now clean up the mess we made.
    output_lines = cleanup_diagram(output_lines, progress)

    # Finally, if the view limit cut this diagram short, drop everything past the cut -- now that
    # the arrows are drawn and cleanup_diagram (which only ever rewrites lines in place, never
    # adds or removes any) has left the line numbering exactly as check_limit saw it.
    if cut_at is not None:
        del output_lines[cut_at:]
        _keep_object_seeds_before(cut_at)

    return output_lines


# Build the Profile box.
def build_profile_box(
    profile: defusedxml.ElementTree,
    profile_counter: int,
    output_profile_lines: list,
    output_task_lines: list,
    print_tasks: bool,
) -> tuple:
    """
    Builds a profile box for a given profile
    Args:
        profile: Profile to add to box
        profile_counter: Counter for profile columns
        output_profile_lines: Running list of profile box lines
        output_task_lines: Running list of task lines
        print_tasks: Flag for printing tasks
    Returns:
        output_profile_lines, output_task_lines, print_tasks: Updated outputs
    Processing Logic:
       1. Check if profile_counter exceeds column limit
       2. If so, print current columns and reset counters
       3. Add profile to running profile box outline
       4. Return updated outputs
    """

    filler = f"{blank * 8}"
    profile_counter += 1
    # Only print the lines if we are at the profiles-per-line value.
    if (
        profile_counter > PrimeItems.program_arguments["profiles_per_line"]
    ):  # profiles_per_line defined as global variable
        _flush_boxes(output_profile_lines)
        profile_counter = 1
        print_tasks = True
        output_profile_lines = [filler, filler, filler]

        # Do Tasks under previous Profile.
        if output_task_lines:
            # Print the Task lines associated with these 6 Profiles.
            _flush_tasks(output_task_lines)
            output_task_lines = []
    else:
        print_tasks = False

    # Start/continue building our Profile outlines
    output_profile_lines, position_for_anchor = build_box(profile, output_profile_lines)
    return (
        output_profile_lines,
        output_task_lines,
        position_for_anchor,
        print_tasks,
        profile_counter,
    )


# Process all Profiles and their Tasks for the given Project
def print_profiles_and_tasks(project_name: str, profiles: dict) -> None:
    """
    Prints profiles and tasks from a project.

    Args:
        project_name: Name of the project.
        profiles: Dictionary of profiles and associated tasks.

    Returns:
        None: Prints output to console.

    - Loops through each profile and associated tasks.
    - Builds profile box and task lines for printing.
    - Checks for tasks not associated with any profile.
    - Prints profile boxes, task lines, and scenes.
    """
    filler = f"{blank * 8}"
    # Go through each Profile in the Project
    profile_counter = 0
    print_tasks = print_scenes = False
    output_profile_lines = [filler, filler, filler]
    output_task_lines = []
    found_tasks = []

    # Now output each Profile and it's Tasks.
    for profile, tasks in profiles.items():
        # Process the Profile
        if profile != "Scenes":
            (
                output_profile_lines,
                output_task_lines,
                position_for_anchor,
                print_tasks,
                profile_counter,
            ) = build_profile_box(
                profile,
                profile_counter,
                output_profile_lines,
                output_task_lines,
                print_tasks,
            )
            # Note where this Profile was drawn.  Here rather than inside build_profile_box,
            # because that one also draws the "No Profile" box that do_tasks_with_no_profile
            # asks it for -- a heading, not an object, and nothing to be taken to.
            #
            # By name, since that is all the network map holds: outline.py keys a Project's
            # Profiles by name, so two Profiles of one name in one Project already share a
            # single box in the drawing.  One box, one anchor -- there is no second position
            # for an id to tell apart.
            owner = PrimeItems.tasker_root_elements["all_profiles_by_name"].get(profile)
            if owner:
                _note_box(
                    Target(kind=PROFILE, key=owner["id"], name=profile, project=project_name),
                    f"{_BOX_WALL} {profile}",
                )

            # Go through the Profile's Tasks
            found_tasks = print_all_tasks(
                tasks,
                position_for_anchor,
                output_task_lines,
                print_tasks,
                found_tasks,
            )

            # Print the Scenes: 6 columns
        else:
            print_scenes = True
            scenes = tasks

    # Determine if this Project has Tasks not assoctiated with any Profiles
    output_profile_lines, output_task_lines = do_tasks_with_no_profile(
        project_name,
        output_profile_lines,
        output_task_lines,
        found_tasks,
        profile_counter,
    )

    # Print any remaining Profile boxes and their associated Tasks
    if output_profile_lines[0] != filler:
        _flush_boxes(output_profile_lines)
        if output_task_lines:
            _flush_tasks(output_task_lines)

    # Map the Scenes
    if print_scenes:
        print_all_scenes(scenes)

    # Add a blank line
    add_output_line(" ")


def remove_empty_strings(lst: list) -> list:
    # return [s for s in lst if re.search(r"\w|\W", s) and not all(char == "|" for char in s)]
    """
    Remove empty strings from a list of strings.
    An empty string is a string that either consists entirely of whitespace or is a single bar character.
    """
    return [s for s in lst if not all(char in (bar, " ", "\\") for char in s)]


def replace_maintain_column(line: str, target: str, replacement: str) -> str:
    """
    Replaces target with replacement.
    1. Splits line by '│', '▼', '▲'.
    2. Performs replacement in the text sections.
    3. Pads with spaces if the new text is shorter.
    4. Truncates the text if it is longer than the original section
       (ensuring it never overwrites/moves the special characters).
    """
    if target not in line:
        return line

    # Split by the special characters, keeping them in the list
    parts = re.split(r"([│▼▲])", line)
    length_parts = len(parts)
    new_parts = []

    for part_no, part in enumerate(parts):
        # If this part is one of our special markers, keep it exactly as is
        if part in ["│", "▼", "▲"]:
            new_parts.append(part)
            continue

        # If this is a text section containing our target
        if target in part:
            original_width = len(part)

            # Perform the replacement
            new_content = part.replace(target, replacement)
            current_width = len(new_content)

            # Use the new length if less than original, or if this is the last item in the list=end of line
            if current_width < original_width or part_no == length_parts - 1:
                # Case 1: Translation is shorter. Pad with spaces.
                padding_needed = original_width - current_width
                new_content += " " * padding_needed

            elif current_width > original_width:
                # Case 2: Translation is longer.
                # We strictly truncate to the original width.
                # This ensures the extra characters are "ignored" and do not
                # overwrite the position of the next special character.
                new_content = new_content[:original_width]

            new_parts.append(new_content)
        else:
            # If target is not in this part, keep it unchanged
            new_parts.append(part)

    return "".join(new_parts)


def build_network_map(data: dict, progress: dict) -> None:
    """
    Builds a network map from project and profile data
    """
    project_text = (
        translate_string("Project:")
        if PrimeItems.program_arguments["language"] not in ("Arabic", "English")
        else "Project:"
    )

    total_projects = len(data)

    for idx, (project, profiles) in enumerate(data.items(), start=1):
        # Update progress tracking increments safely
        if "progress_bar" in progress:
            # Update the progress percentage label text dynamically
            progress["status_label"].set_text(f"Mapping Project {idx} of {total_projects}: {project}")
            # Calculate fractional float between 0.0 and 1.0
            progress["progress_bar"].set_value(idx / total_projects)

        # Print Project as a box.  The row is the middle of the three print_box writes.
        row = len(PrimeItems.netmap_output) + 1
        print_box(project, project_text, 1)
        _record(row, Target(kind=PROJECT, key=project, name=project), f"{_BOX_WALL} {project_text} {project}")
        # Print all of the Project's Profiles and their Tasks
        print_profiles_and_tasks(project, profiles)

    # Process task relational arrow connectors
    if "status_label" in progress:
        progress["status_label"].set_text("Drawing call relationship arrows...")

    PrimeItems.netmap_output = handle_calls(PrimeItems.netmap_output, progress)

    # Remove lines that only contain bars ( | ). This shifts every subsequent line number, so
    # remap the GUI Diagram view's connector seeds (see draw_arrows_to_called_task()) along with it.
    old_to_new_row = {}
    new_row = 0
    for old_row, removal_line in enumerate(PrimeItems.netmap_output):
        if all(char in (bar, " ", "\\") for char in removal_line):
            continue
        old_to_new_row[old_row] = new_row
        new_row += 1
    PrimeItems.diagram_connector_seeds = [
        (old_to_new_row[row], col, call)
        for row, col, call in PrimeItems.diagram_connector_seeds
        if row in old_to_new_row
    ]
    _remap_call_edges(old_to_new_row)
    _remap_object_seeds(old_to_new_row)
    PrimeItems.netmap_output = remove_empty_strings(PrimeItems.netmap_output)

    # Translate the output lines if needed
    if PrimeItems.program_arguments["language"] not in ("English", "Arabic"):
        trans = {
            "no_proj": ("No Project", translate_string("No Project")),
            "calls": ("[Calls", f"[{translate_string('Calls')}"),
            "called": ("[Called by", f"[{translate_string('Called by')}"),
            "entry": (" (entry)", f" {translate_string('(entry)')}"),
            "exit": (" (exit)", f" {translate_string('(exit)')}"),
            "notfound": (" (Not Found!)", f" {translate_string('(Not Found!)')}"),
        }

        output_list = PrimeItems.netmap_output

        for i, line in enumerate(output_list):
            if any(key[0] in line for key in trans.values()):
                newline = line
                newline = replace_maintain_column(newline, trans["no_proj"][0], trans["no_proj"][1])
                newline = replace_maintain_column(newline, trans["calls"][0], trans["calls"][1])
                newline = replace_maintain_column(newline, trans["called"][0], trans["called"][1])
                newline = replace_maintain_column(newline, trans["entry"][0], trans["entry"][1])
                newline = replace_maintain_column(newline, trans["exit"][0], trans["exit"][1])
                newline = replace_maintain_column(newline, trans["notfound"][0], trans["notfound"][1])
                output_list[i] = newline


# Print the network map.
def network_map(network: dict) -> None:
    """
    Output a network map of the Tasker configuration.
    """
    progress = {}

    # Start with a ruler line
    PrimeItems.output_lines.add_line_to_output(1, "<hr>", FormatLine.dont_format_line)

    PrimeItems.netmap_output = []
    PrimeItems.called_task_tracker = {}
    # Emptied here rather than where they are first written, so that a second run cannot
    # leave the previous diagram's objects standing in this one's line numbers.
    PrimeItems.diagram_object_seeds = {}
    PrimeItems.diagram_object_targets = {}
    PrimeItems.diagram_object_placements = []
    PrimeItems.diagram_anchors = {}
    PrimeItems.diagram_call_edges = {}
    PrimeItems.diagram_connector_calls = {}
    PrimeItems.diagram_model = {}
    _pending_boxes.clear()
    _pending_tasks.clear()

    # datetime object containing current date and time
    # now = datetime.now()
    dt_string = NOW_TIME.strftime("%B %d, %Y  %H:%M:%S")

    add_output_line(f"{MY_VERSION}{blank * 5}Configuration Map{blank * 5}{dt_string}")
    add_output_line(" ")
    add_output_line(
        translate_string(
            "Display with a monospaced font (e.g. Courier New) for accurate column alignment. And turn off line wrap.\nIcons or Chinese/Korean/Japanese in names can cause minor mis-alignment.",
        ),
    )
    add_output_line(" ")
    add_output_line(" ")

    # Build and print the configuration tracking progress updates asynchronously
    build_network_map(network, progress)

    # Redirect print to a file
    if PrimeItems.netmap_output:
        output_dir = f"{os.getcwd()}{PrimeItems.slash}{DIAGRAM_FILE}"
        first_project = True
        project_translated = (
            translate_string("Project:")
            if PrimeItems.program_arguments["language"] not in ("Arabic", "English")
            else "Project:"
        )
        # Collect the exact lines as they're written to DIAGRAM_FILE (spacer lines included, icons
        # trimmed), so PrimeItems.diagram_connectors can be computed directly from what the GUI
        # Diagram view will actually display -- see compute_diagram_connector_groups(). Track how
        # the netmap_output index (num) maps to the final line number too, since the spacer lines
        # written between projects shift every subsequent line -- needed to keep the connector
        # seeds (recorded in netmap_output's coordinates) in sync with final_lines.
        final_lines = []
        netmap_to_file_line = {}
        with open(str(output_dir), "w", encoding="utf-8") as mapfile:
            for num, line in enumerate(PrimeItems.netmap_output):
                if (
                    not first_project
                    and box_line in line
                    and num + 1 < len(PrimeItems.netmap_output)
                    and project_translated in PrimeItems.netmap_output[num + 1]
                ):
                    if bar in PrimeItems.netmap_output[num - 1]:
                        spacer = (
                            "".join(char if char == bar else " " for char in PrimeItems.netmap_output[num + 1]) + "\n"
                        )
                    else:
                        spacer = "\n"
                    mapfile.write(spacer)
                    mapfile.write(spacer)
                    final_lines.append(spacer.rstrip("\n"))
                    final_lines.append(spacer.rstrip("\n"))
                if project_translated in line:
                    first_project = False

                netmap_to_file_line[num] = len(final_lines)
                line = remove_icon(line)
                mapfile.write(f"{line}\n")
                # A handful of netmap_output entries (e.g. the header hint) carry an embedded "\n"
                # of their own, which becomes two physical lines once written -- split the same way
                # here so final_lines stays row-for-row aligned with the file.
                final_lines.extend(line.split("\n"))

            # Say so in the diagram itself when it was cut short at the view limit (check_limit),
            # the way the Map view's file carries its own limit message -- the file is read on its
            # own as often as it is displayed in the GUI, and a diagram that simply stops has no
            # other way of telling the reader that there was more.  Written after the loop so it
            # cannot disturb the netmap_output-to-file line mapping the connectors rely on.
            if PrimeItems.diagram_limit_msg:
                mapfile.write(f"\n{PrimeItems.diagram_limit_msg}\n")
                final_lines.extend(["", PrimeItems.diagram_limit_msg])
            mapfile.close()

        remapped_seeds = [
            (netmap_to_file_line[row], col, call)
            for row, col, call in PrimeItems.diagram_connector_seeds
            if row in netmap_to_file_line
        ]
        _remap_call_edges(netmap_to_file_line)
        PrimeItems.diagram_connectors = compute_diagram_connector_groups(final_lines, remapped_seeds)

        # The last step for the object seeds: onto the file's own line numbering, and then
        # from "the name is somewhere on this line" to the exact span of it, measured
        # against the line as written.  Resolved here rather than in the browser because
        # this is the only place that holds both the finished line and the name that was
        # drawn into it -- remove_icon has run by now, and a column worked out before it
        # would be a column off by one on every line it touched.
        anchors = {}
        for anchor, (row, snippet) in PrimeItems.diagram_object_seeds.items():
            file_line = netmap_to_file_line.get(row)
            if file_line is None or file_line >= len(final_lines):
                continue
            anchors[anchor] = (file_line, *_place(final_lines[file_line], snippet, _BOX_WALL in snippet))
        PrimeItems.diagram_anchors = anchors

        # And the same for every OTHER drawing of each object, which is what the interactive
        # view makes clickable (see _record).  Resolved in draw order, keeping a cursor per
        # line: a Task run by two Profiles drawn side by side is written on that line twice,
        # and each drawing has to be given the copy of the name it is actually drawn as
        # rather than both being handed the first.
        placements = []
        claimed: dict[int, int] = {}
        for anchor, row, snippet in PrimeItems.diagram_object_placements:
            file_line = netmap_to_file_line.get(row)
            if file_line is None or file_line >= len(final_lines):
                continue
            line = final_lines[file_line]
            column, length = _place(line, snippet, _BOX_WALL in snippet, claimed.get(file_line, 0))
            if length:
                # In code points, which is what the next search along this line counts in;
                # the column recorded is in UTF-16 units, which is what the browser counts in.
                claimed[file_line] = line.find(snippet, claimed.get(file_line, 0)) + len(snippet)
            placements.append((anchor, file_line, column, length))
        PrimeItems.diagram_object_placements = placements
        logger.debug(f"diagram: {len(PrimeItems.diagram_anchors)} object anchors recorded")
        PrimeItems.diagram_object_seeds = {}

        # Everything the interactive Diagram view acts on, assembled now that every position
        # is final -- see diagintr.build_model.  Built here rather than in the view because
        # this is the only place that holds the finished lines, the anchors resolved onto
        # them and the connectors grown from their seeds all at once.
        PrimeItems.diagram_model = diagintr.build_model(final_lines)
        PrimeItems.diagram_object_placements = []
        logger.debug(
            f"diagram: {len(PrimeItems.diagram_model['nodes'])} clickable nodes, "
            f"{len(PrimeItems.diagram_model['regions'])} foldable Projects, "
            f"{len(PrimeItems.diagram_model['edges'])} calls",
        )
        PrimeItems.diagram_object_targets = {}

        # Cleanup
        PrimeItems.netmap_output = []
