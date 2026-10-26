"""diagprint: printing the Diagram's Tasks, Scenes and Profile boxes.

add_quotes and flatten_with_quotes turn a Task's lines into the quoted form the Diagram shows; the print_all_*
functions walk the Tasks and Scenes of a Project and write each with its call arrows left to diagarrows."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from maptasker.src.core.elemvals import get_ids
from maptasker.src.core.mapjump import SCENE, TASK, Target
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.sysconst import SCENE_TASK_TYPES, UNNAMED_ITEM
from maptasker.src.core.xmldata import tag_in_type
from maptasker.src.mapgen.diagcnst import angle, blank, line_left_arrow, line_right_arrow, task_delimeter
from maptasker.src.mapgen.diagrecord import BOX_WALL, flush_boxes, flush_tasks, note_box, note_task
from maptasker.src.mapgen.diagutil import add_output_line, build_box, include_heading

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig


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


def _real_task_name(task_name: str) -> str:
    """The Task's own name, in case it has a Screen element 'click' name associated with it."""
    position = task_name.find(":")
    real_task_name = task_name.split("&nbsp;", maxsplit=1)[0]
    if position != -1 and "," in task_name:
        scene_task_type_to_check = task_name.split(",")[1].split(":", maxsplit=1)[0][1:]
        for scene_task_type in SCENE_TASK_TYPES.values():
            if scene_task_type == scene_task_type_to_check:
                temp = task_name.find(":")
                if temp != -1:
                    real_task_name = task_name[temp + 2 :]
                break
    return real_task_name


def _add_blank_lines_for_calls(output_task_lines: list, prime_task: dict | None, state: RunState) -> None:
    """Add a blank line afterwards for each called Task (one per task name) for yet-to-be-populated connectors."""
    if prime_task is None:
        return
    with contextlib.suppress(KeyError):
        for calls_task in prime_task["call_tasks"]:
            output_task_lines.append("")

            # Keep track of all Tasks being called
            the_task = calls_task
            if state.called_task_tracker:
                if the_task in state.called_task_tracker:
                    state.called_task_tracker[the_task]["total_number"] += 1
                else:
                    state.called_task_tracker[the_task] = {
                        "total_number": 1,
                        "counter": 0,
                    }
            else:
                state.called_task_tracker[the_task] = {
                    "total_number": 1,
                    "counter": 0,
                }


def _interject_upward_bars(output_task_lines: list, last_upward_bar: list) -> None:
    """Interject the "|" for previous Tasks under Profile."""
    for bar_char in last_upward_bar:
        for line_num, line in enumerate(output_task_lines):
            if len(line) > bar_char and not line[bar_char]:
                output_task_lines[line_num] = f"{line[:bar_char]}│{line[bar_char:]}"
            if len(line) <= bar_char:
                output_task_lines[line_num] = f"{line.ljust(bar_char)}│"


def add_quotes(
    output_task_lines: list,
    last_upward_bar: list,
    task: dict,
    task_type: str,
    called_by_tasks: str,
    position_for_anchor: int,
    found_tasks: list,
    state: RunState,
) -> tuple[list, list, list]:
    """
    Add quotes to called Tasks.

    Args:
        output_task_lines (list): List of output lines to add to.
        last_upward_bar (int): The position of the last upward | in the output.
        task (dict): Task details: xml element, name, etc.
        task_type (str): Entry or Exit
        called_by_tasks (str): The "[Called by ...]" text for this Task, or "".
        position_for_anchor (int): Location of the anchor point for the Task.
        found_tasks (list): List of Tasks found so far.

    Returns:
        tuple: Tuple containing the updated found_tasks, last_upward_bar, and output_task_lines.
    """
    call_tasks = ""
    task_name = task["name"]

    real_task_name = _real_task_name(task_name)

    # Get the primary task pointer for this task.
    try:
        prime_task = state.tasker_root_elements["all_tasks_by_name"][real_task_name]
    except KeyError:
        prime_task = None

    with contextlib.suppress(KeyError):
        if prime_task is not None and prime_task["call_tasks"] is not None:
            # Flatten list of called tasks and surround each with a quote.
            call_tasks = f" [Calls {line_right_arrow} {flatten_with_quotes(prime_task['call_tasks'])}]"

    # We are still accumulating outlines for Profiles.
    # Build lines for the Profile's Tasks as well.
    line = f"{blank * position_for_anchor}{angle}{task_name}{task_type}{called_by_tasks}{call_tasks}"
    last_upward_bar.append(position_for_anchor)
    # Note where this Task is being drawn, against the buffer rather than the output: these
    # lines are appended to the diagram later, and only then is the row known (see
    # flush_tasks).
    #
    # The id comes from the Task's own element, NOT from prime_task -- which was looked up
    # by name, and all_tasks_by_name keeps one entry per name (taskerd.py), so two Tasks
    # called 'Backup' both resolve to whichever of them the table kept.  Both are drawn
    # here, on lines of their own, and taking the id from the element is what lets a jump
    # tell them apart; going through the name table would file the second one's line under
    # the first one's id and land every click on the first.
    task_id = task["xml"].findtext("id") if task.get("xml") is not None else ""
    if task_id:
        note_task(
            len(output_task_lines),
            Target(kind=TASK, key=task_id, name=real_task_name),
            f"{angle}{task_name}",
            state,
        )
    output_task_lines.append(line)
    if task_name not in found_tasks:
        found_tasks.append(task_name)

    _add_blank_lines_for_calls(output_task_lines, prime_task, state)

    _interject_upward_bars(output_task_lines, last_upward_bar)

    return found_tasks, last_upward_bar, output_task_lines


# Print the specific Task.
def output_the_task(
    print_tasks: bool,
    found_tasks: list,
    task: dict,
    output_task_lines: list,
    last_upward_bar: list,
    task_labels: tuple[str, str],
    position_for_anchor: int,
    state: RunState,
) -> tuple[list, list, list]:
    """
    Add the Task to the output list.
        Args:
            print_tasks (bool): True if we are printing Tasks.
            found_tasks (list): List of Tasks found so far.
            task (dict): Task details: xml element, name, etc.
            output_task_lines (list): List of output lines to add to.
            last_upward_bar (list): Position of last upward | in the output.
            task_labels (tuple[str, str]): Entry or Exit, and the "[Called by ...]" text for this Task (or "").
            position_for_anchor (int): Location of the anchor point for the Task.

        Returns:
            tuple[list, list, list]: found_tasks, last_upward_bar, output_task_lines
    """
    task_type, called_by_tasks = task_labels
    # We have a full row of Profiles.  Print the Tasks out.
    if print_tasks:
        if output_task_lines:
            flush_tasks(output_task_lines, state=state)
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
        state=state,
    )

    return found_tasks, last_upward_bar, output_task_lines


# Process all Tasks in the Profile
def print_all_tasks(
    tasks: list[dict],
    position_for_anchor: int,
    output_task_lines: list,
    print_tasks: bool,
    found_tasks: list,
    state: RunState,
) -> list:
    """
    Process all Tasks in the Profile.

    Args:
        tasks (list[dict]): the Tasks in the Profile
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
        task_name = state.tasker_root_elements["all_tasks_by_name"][tname]
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
            (task_type, called_by_tasks),
            position_for_anchor,
            state=state,
        )

    return found_tasks


def process_scene_tasks(
    scene: str,
    position_for_anchor: int,
    task_list: list,
    state: RunState,
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
    scene_xml = state.tasker_root_elements["all_scenes"].get(scene, {}).get("xml", [])
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
            task_info = state.tasker_root_elements["all_tasks"].get(task_id)
            if not task_info:
                continue

            task = {
                "xml": task_info["xml"],
                "name": f"Element '{element_name}', {SCENE_TASK_TYPES[sub_element_tag]}: {task_info['name']}",
            }

            # Store the task
            task_list.append([task, position_for_anchor])

    if output_task_lines:
        flush_tasks(output_task_lines, state=state)

    return task_list, output_task_lines


# Process all Scenes in the Project, 8 Scenes to a row.
def print_all_scenes(scenes: list, config: RunConfig, state: RunState) -> None:
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
    add_output_line(" ", state=state)

    # Do all of the Scenes for the given Project
    for scene in scenes:
        scene_counter += 1
        if scene_counter > 8:
            # We have 8 columns.  Print them out and reset.
            include_heading(f"{blank * 7}{scenes_translated}", output_scene_lines)
            flush_boxes(output_scene_lines, state=state)
            scene_counter = 1
            output_scene_lines = [filler, filler, filler]

        # Start/continue building our outlines
        output_scene_lines, position_for_anchor = build_box(scene, output_scene_lines, config=config)
        # Noted after the box is built, and after any flush above it, so the note belongs to
        # the buffer this Scene actually went into rather than to the row before it.
        note_box(Target(kind=SCENE, key=scene, name=scene), f"{BOX_WALL} {scene}", state)

        # Process Scene's Tasks
        task_list, output_task_lines = process_scene_tasks(scene, position_for_anchor + 15, task_list, state=state)

    # Print any remaining Scenes
    include_heading(f"{blank * 7}{scenes_translated}", output_scene_lines)
    flush_boxes(output_scene_lines, state=state)

    # Print out the Scenes' Tasks
    for task in task_list:
        # Output the Task
        _found_tasks, _last_upward_bar, output_task_lines = output_the_task(
            True, [], task[0], output_task_lines, [], ("", ""), task[1], state=state
        )
    if task_list:
        flush_tasks(output_task_lines, state=state)


# Process Tasks not in any Profile
def do_tasks_with_no_profile(
    project_name: str,
    output_profile_lines: list,
    output_task_lines: list,
    found_tasks: list,
    profile_counter: int,
    config: RunConfig,
    state: RunState,
) -> tuple[list, list]:
    """
    Process Tasks not in any Profile
    Args:
        project_name: Project name in one line
        output_profile_lines: Output profile lines in one line
        output_task_lines: Output task lines in one line
        found_tasks: Found tasks list in one line
        profile_counter: Profile counter in one line
        config: the run's settings
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

    project_root = state.tasker_root_elements["all_projects"][project_name]["xml"]
    tasks_not_in_profile = []

    # Get all task IDs for this Project.
    project_task_ids = get_ids(False, project_root, project_name, [])

    # Go through each Task ID and see if it is in found_tasks.
    for task in project_task_ids:
        if state.tasker_root_elements["all_tasks"][task]["name"] not in found_tasks:
            profile = "No Profile"
            print_tasks = False
            the_task = state.tasker_root_elements["all_tasks"][task]
            if the_task not in tasks_not_in_profile:
                tasks_not_in_profile.append(the_task)

    # Ok, do we have any Tasks that are not in any Profile?  If so, output them.
    # if not PrimeItems.program_arguments.single_profile_name and tasks_not_in_profile:
    # Build profile box
    if tasks_not_in_profile:
        (
            output_profile_lines,
            output_task_lines,
            position_for_anchor,
            print_tasks,
            profile_counter,
        ) = build_profile_box(
            profile, profile_counter, output_profile_lines, output_task_lines, print_tasks, config, state=state
        )

        # Print tasks not in any profile
        print_tasks = False
        _ = print_all_tasks(
            tasks_not_in_profile, position_for_anchor, output_task_lines, print_tasks, found_tasks, state=state
        )

    return output_profile_lines, output_task_lines


# Build the Profile box.
def build_profile_box(
    profile: str,
    profile_counter: int,
    output_profile_lines: list,
    output_task_lines: list,
    print_tasks: bool,
    config: RunConfig,
    state: RunState,
) -> tuple[list, list, int, bool, int]:
    """
    Builds a profile box for a given profile
    Args:
        profile: The Profile's name, to put in the box
        profile_counter: Counter for profile columns
        output_profile_lines: Running list of profile box lines
        output_task_lines: Running list of task lines
        print_tasks: Flag for printing tasks
        config: the run's settings (profiles_per_line)
    Returns:
        output_profile_lines, output_task_lines, position_for_anchor, print_tasks, profile_counter: Updated outputs
    Processing Logic:
       1. Check if profile_counter exceeds column limit
       2. If so, print current columns and reset counters
       3. Add profile to running profile box outline
       4. Return updated outputs
    """

    filler = f"{blank * 8}"
    profile_counter += 1
    # Only print the lines if we are at the profiles-per-line value.
    if profile_counter > config.profiles_per_line:
        flush_boxes(output_profile_lines, state=state)
        profile_counter = 1
        print_tasks = True
        output_profile_lines = [filler, filler, filler]

        # Do Tasks under previous Profile.
        if output_task_lines:
            # Print the Task lines associated with these 6 Profiles.
            flush_tasks(output_task_lines, state=state)
            output_task_lines = []
    else:
        print_tasks = False

    # Start/continue building our Profile outlines
    output_profile_lines, position_for_anchor = build_box(profile, output_profile_lines, config=config)
    return (
        output_profile_lines,
        output_task_lines,
        position_for_anchor,
        print_tasks,
        profile_counter,
    )
