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

This module builds the whole Diagram and writes it out; the pieces it is built from are:

    diagrecord   noting where each object lands, for jumping to it from a report
    diagprint    printing the Tasks, Scenes and Profile boxes
    diagarrows   the arrows between boxes
    diagclean    tidying what the arrows leave behind
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from maptasker.src.core.mapjump import PROFILE, PROJECT, Target

# Avoid circular import error: guiwins has the proper import statement for configure_progress_bar,
# the function, of which, is in guiutil2.
# from maptasker.src.gui.guiwins import configure_progress_bar
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.core.outdir import output_path
from maptasker.src.core.primitem import DIAGRAM_ATTRIBUTES, reset_attributes
from maptasker.src.core.sysconst import (
    DIAGRAM_FILE,
    MY_VERSION,
    NOW_TIME,
    FormatLine,
    logger,
)
from maptasker.src.mapgen import diagintr
from maptasker.src.mapgen.diagarrows import compute_diagram_connector_groups, draw_arrows_to_called_task
from maptasker.src.mapgen.diagclean import (
    add_blanks_above_called_tasks,
    check_limit,
    cleanup_diagram,
    mark_tasks_not_found,
)
from maptasker.src.mapgen.diagcnst import (
    bar,
    blank,
    box_line,
)
from maptasker.src.mapgen.diagprint import (
    build_profile_box,
    do_tasks_with_no_profile,
    print_all_scenes,
    print_all_tasks,
)
from maptasker.src.mapgen.diagrecord import (
    BOX_WALL,
    flush_boxes,
    flush_tasks,
    keep_object_seeds_before,
    note_box,
    place_in_line,
    record_at_row,
    remap_call_edges,
    remap_object_seeds,
)
from maptasker.src.mapgen.diagutil import (
    add_output_line,
    build_call_table,
    fix_duplicate_up_down_locations,
    print_box,
    remove_icon,
)

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig


# If Task line has any "Task Call" Task actions, fill it with arrows.
def handle_calls(output_lines: list, progress: dict, config: RunConfig, state: RunState) -> list:
    """
    Handle calls in output lines from parsing
    Args:
        output_lines: output lines from parsing in one line
        progress: progress bar dictionary
        config: the run's settings
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
    state.diagram_connector_seeds = []
    # One entry per call drawn, keyed by the index the seeds refer to it by: {caller_row,
    # called_row, caller_name, called_name, project}, rows in output_lines' own numbering
    # here and remapped onto the rendered file's alongside the seeds.  Keyed rather than a
    # plain list because a remap DROPS the calls whose lines no longer exist, and a seed
    # already holding index 7 must not be left pointing at whatever slid into that slot.
    state.diagram_call_edges = {}

    # Go through the output and add blanks above the called tasks, one for each caller.
    output_lines = add_blanks_above_called_tasks(output_lines, state=state)

    # Recaluate progress bar size.
    progress["max_data"] = len(output_lines)
    progress["tenth_increment"] = progress["max_data"] // 10

    # Identify called Tasks that don't exist and add blank lines for called/caller Tasks.
    mark_tasks_not_found(output_lines)

    # Create the table of caller/called Tasks and their pointers.
    call_table = build_call_table(output_lines, config=config)

    # Check if we have exceeded our maximum size limit.  Over it, this hands back only the
    # connectors that fit and the line to cut the diagram at once they have been drawn.
    cut_at, call_table = check_limit(call_table, output_lines, progress, config, state=state)

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
            connector["up_down_location"], connector, output_lines, called_task_lookup, config, state=state
        )

    # Now clean up the mess we made.
    output_lines = cleanup_diagram(output_lines, progress)

    # Finally, if the view limit cut this diagram short, drop everything past the cut -- now that
    # the arrows are drawn and cleanup_diagram (which only ever rewrites lines in place, never
    # adds or removes any) has left the line numbering exactly as check_limit saw it.
    if cut_at is not None:
        del output_lines[cut_at:]
        keep_object_seeds_before(cut_at, state=state)

    return output_lines


# Process all Profiles and their Tasks for the given Project
def print_profiles_and_tasks(project_name: str, profiles: dict, config: RunConfig, state: RunState) -> None:
    """
    Prints profiles and tasks from a project.

    Args:
        project_name: Name of the project.
        profiles: Dictionary of profiles and associated tasks.
        config: the run's settings.

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
                profile, profile_counter, output_profile_lines, output_task_lines, print_tasks, config, state=state
            )
            # Note where this Profile was drawn.  Here rather than inside build_profile_box,
            # because that one also draws the "No Profile" box that do_tasks_with_no_profile
            # asks it for -- a heading, not an object, and nothing to be taken to.
            #
            # By name, since that is all the network map holds: outline.py keys a Project's
            # Profiles by name, so two Profiles of one name in one Project already share a
            # single box in the drawing.  One box, one anchor -- there is no second position
            # for an id to tell apart.
            owner = state.tasker_root_elements["all_profiles_by_name"].get(profile)
            if owner:
                note_box(
                    Target(kind=PROFILE, key=owner["id"], name=profile, project=project_name),
                    f"{BOX_WALL} {profile}",
                    state,
                )

            # Go through the Profile's Tasks
            found_tasks = print_all_tasks(
                tasks, position_for_anchor, output_task_lines, print_tasks, found_tasks, state=state
            )

            # Print the Scenes: 6 columns
        else:
            print_scenes = True
            scenes = tasks

    # Determine if this Project has Tasks not assoctiated with any Profiles
    output_profile_lines, output_task_lines = do_tasks_with_no_profile(
        project_name, output_profile_lines, output_task_lines, found_tasks, profile_counter, config, state=state
    )

    # Print any remaining Profile boxes and their associated Tasks
    if output_profile_lines[0] != filler:
        flush_boxes(output_profile_lines, state=state)
        if output_task_lines:
            flush_tasks(output_task_lines, state=state)

    # Map the Scenes
    if print_scenes:
        print_all_scenes(scenes, config, state=state)

    # Add a blank line
    add_output_line(" ", state=state)


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


def build_network_map(data: dict, progress: dict, config: RunConfig, state: RunState) -> None:
    """
    Builds a network map from project and profile data
    """
    project_text = translate_string("Project:") if config.language not in ("Arabic", "English") else "Project:"

    total_projects = len(data)

    for idx, (project, profiles) in enumerate(data.items(), start=1):
        # Update progress tracking increments safely
        if "progress_bar" in progress:
            # Update the progress percentage label text dynamically
            progress["status_label"].set_text(f"Mapping Project {idx} of {total_projects}: {project}")
            # Calculate fractional float between 0.0 and 1.0
            progress["progress_bar"].set_value(idx / total_projects)

        # Print Project as a box.  The row is the middle of the three print_box writes.
        row = len(state.netmap_output) + 1
        print_box(project, project_text, 1, config=config, state=state)
        record_at_row(
            row, Target(kind=PROJECT, key=project, name=project), f"{BOX_WALL} {project_text} {project}", state=state
        )
        # Print all of the Project's Profiles and their Tasks
        print_profiles_and_tasks(project, profiles, config, state=state)

    # Process task relational arrow connectors
    if "status_label" in progress:
        progress["status_label"].set_text("Drawing call relationship arrows...")

    state.netmap_output = handle_calls(state.netmap_output, progress, config, state=state)

    # Remove lines that only contain bars ( | ). This shifts every subsequent line number, so
    # remap the GUI Diagram view's connector seeds (see draw_arrows_to_called_task()) along with it.
    old_to_new_row = {}
    new_row = 0
    for old_row, removal_line in enumerate(state.netmap_output):
        if all(char in (bar, " ", "\\") for char in removal_line):
            continue
        old_to_new_row[old_row] = new_row
        new_row += 1
    state.diagram_connector_seeds = [
        (old_to_new_row[row], col, call) for row, col, call in state.diagram_connector_seeds if row in old_to_new_row
    ]
    remap_call_edges(old_to_new_row, state=state)
    remap_object_seeds(old_to_new_row, state=state)
    state.netmap_output = remove_empty_strings(state.netmap_output)

    # Translate the output lines if needed
    if config.language not in ("English", "Arabic"):
        trans = {
            "no_proj": ("No Project", translate_string("No Project")),
            "calls": ("[Calls", f"[{translate_string('Calls')}"),
            "called": ("[Called by", f"[{translate_string('Called by')}"),
            "entry": (" (entry)", f" {translate_string('(entry)')}"),
            "exit": (" (exit)", f" {translate_string('(exit)')}"),
            "notfound": (" (Not Found!)", f" {translate_string('(Not Found!)')}"),
        }

        output_list = state.netmap_output

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
def _write_diagram_file(config: RunConfig, state: RunState) -> tuple[list[str], dict[int, int]]:
    """Write the diagram to its file.

    Returns:
        The exact lines as they were written, and how each netmap_output index maps to its
        final line number.
    """
    output_dir = output_path(DIAGRAM_FILE, state=state)
    first_project = True
    project_translated = translate_string("Project:") if config.language not in ("Arabic", "English") else "Project:"
    # Collect the exact lines as they're written to DIAGRAM_FILE (spacer lines included, icons
    # trimmed), so PrimeItems.diagram_connectors can be computed directly from what the GUI
    # Diagram view will actually display -- see compute_diagram_connector_groups(). Track how
    # the netmap_output index (num) maps to the final line number too, since the spacer lines
    # written between projects shift every subsequent line -- needed to keep the connector
    # seeds (recorded in netmap_output's coordinates) in sync with final_lines.
    final_lines = []
    netmap_to_file_line = {}
    with open(str(output_dir), "w", encoding="utf-8") as mapfile:
        for num, line in enumerate(state.netmap_output):
            if (
                not first_project
                and box_line in line
                and num + 1 < len(state.netmap_output)
                and project_translated in state.netmap_output[num + 1]
            ):
                if bar in state.netmap_output[num - 1]:
                    spacer = "".join(char if char == bar else " " for char in state.netmap_output[num + 1]) + "\n"
                else:
                    spacer = "\n"
                mapfile.write(spacer)
                mapfile.write(spacer)
                final_lines.append(spacer.rstrip("\n"))
                final_lines.append(spacer.rstrip("\n"))
            if project_translated in line:
                first_project = False

            netmap_to_file_line[num] = len(final_lines)
            written = remove_icon(line)
            mapfile.write(f"{written}\n")
            # A handful of netmap_output entries (e.g. the header hint) carry an embedded "\n"
            # of their own, which becomes two physical lines once written -- split the same way
            # here so final_lines stays row-for-row aligned with the file.
            final_lines.extend(written.split("\n"))

        # Say so in the diagram itself when it was cut short at the view limit (check_limit),
        # the way the Map view's file carries its own limit message -- the file is read on its
        # own as often as it is displayed in the GUI, and a diagram that simply stops has no
        # other way of telling the reader that there was more.  Written after the loop so it
        # cannot disturb the netmap_output-to-file line mapping the connectors rely on.
        if state.diagram_limit_msg:
            mapfile.write(f"\n{state.diagram_limit_msg}\n")
            final_lines.extend(["", state.diagram_limit_msg])
        mapfile.close()
    return final_lines, netmap_to_file_line


def _resolve_object_anchors(final_lines: list[str], netmap_to_file_line: dict[int, int], state: RunState) -> None:
    """Record each object's anchor against the file's own line numbering and the exact span of its name."""
    # The last step for the object seeds: onto the file's own line numbering, and then
    # from "the name is somewhere on this line" to the exact span of it, measured
    # against the line as written.  Resolved here rather than in the browser because
    # this is the only place that holds both the finished line and the name that was
    # drawn into it -- remove_icon has run by now, and a column worked out before it
    # would be a column off by one on every line it touched.
    anchors = {}
    for anchor, (row, snippet) in state.diagram_object_seeds.items():
        file_line = netmap_to_file_line.get(row)
        if file_line is None or file_line >= len(final_lines):
            continue
        anchors[anchor] = (file_line, *place_in_line(final_lines[file_line], snippet, BOX_WALL in snippet))
    state.diagram_anchors = anchors


def _resolve_object_placements(
    final_lines: list[str],
    netmap_to_file_line: dict[int, int],
    state: RunState,
) -> None:
    """Record every OTHER drawing of each object as well, which is what the interactive view makes clickable."""
    # And the same for every OTHER drawing of each object, which is what the interactive
    # view makes clickable (see record_at_row).  Resolved in draw order, keeping a cursor per
    # line: a Task run by two Profiles drawn side by side is written on that line twice,
    # and each drawing has to be given the copy of the name it is actually drawn as
    # rather than both being handed the first.
    placements = []
    claimed: dict[int, int] = {}
    for anchor, row, snippet in state.diagram_object_placements:
        file_line = netmap_to_file_line.get(row)
        if file_line is None or file_line >= len(final_lines):
            continue
        line = final_lines[file_line]
        column, length = place_in_line(line, snippet, BOX_WALL in snippet, claimed.get(file_line, 0))
        if length:
            # In code points, which is what the next search along this line counts in;
            # the column recorded is in UTF-16 units, which is what the browser counts in.
            claimed[file_line] = line.find(snippet, claimed.get(file_line, 0)) + len(snippet)
        placements.append((anchor, file_line, column, length))
    state.diagram_object_placements = placements
    logger.debug(f"diagram: {len(state.diagram_anchors)} object anchors recorded")
    state.diagram_object_seeds = {}


def _build_diagram_model(final_lines: list[str], state: RunState) -> None:
    """Assemble everything the interactive Diagram view acts on, now that every position is final."""
    # Everything the interactive Diagram view acts on, assembled now that every position
    # is final -- see diagintr.build_model.  Built here rather than in the view because
    # this is the only place that holds the finished lines, the anchors resolved onto
    # them and the connectors grown from their seeds all at once.
    state.diagram_model = diagintr.build_model(final_lines, state=state)
    state.diagram_object_placements = []
    logger.debug(
        f"diagram: {len(state.diagram_model['nodes'])} clickable nodes, "
        f"{len(state.diagram_model['regions'])} foldable Projects, "
        f"{len(state.diagram_model['edges'])} calls",
    )
    state.diagram_object_targets = {}


def network_map(network: dict, config: RunConfig, state: RunState) -> None:
    """
    Output a network map of the Tasker configuration.

    Args:
        network (dict): the Projects, Profiles and Tasks to draw.
        config (RunConfig): the run's settings, threaded down to everything that draws.
    """
    progress = {}

    # Start with a ruler line
    state.output_lines.add_line_to_output(1, "<hr>", FormatLine.dont_format_line)

    # Emptied here rather than where they are first written, so that a second run cannot
    # leave the previous diagram's objects standing in this one's line numbers.
    reset_attributes(*DIAGRAM_ATTRIBUTES, state=state)

    # datetime object containing current date and time
    # now = datetime.now()
    dt_string = NOW_TIME.strftime("%B %d, %Y  %H:%M:%S")

    add_output_line(f"{MY_VERSION}{blank * 5}Configuration Map{blank * 5}{dt_string}", state=state)
    add_output_line(" ", state=state)
    add_output_line(
        translate_string(
            "Display with a monospaced font (e.g. Courier New) for accurate column alignment. And turn off line wrap.",
        ),
        state=state,
    )
    add_output_line(" ", state=state)
    add_output_line(" ", state=state)

    # Build and print the configuration tracking progress updates asynchronously
    build_network_map(network, progress, config, state=state)

    # Redirect print to a file
    if state.netmap_output:
        final_lines, netmap_to_file_line = _write_diagram_file(config, state)

        remapped_seeds = [
            (netmap_to_file_line[row], col, call)
            for row, col, call in state.diagram_connector_seeds
            if row in netmap_to_file_line
        ]
        remap_call_edges(netmap_to_file_line, state=state)
        state.diagram_connectors = compute_diagram_connector_groups(final_lines, remapped_seeds, state=state)

        _resolve_object_anchors(final_lines, netmap_to_file_line, state)
        _resolve_object_placements(final_lines, netmap_to_file_line, state)
        _build_diagram_model(final_lines, state)

        # Cleanup
        state.netmap_output = []
