"""diagarrows: the arrows between the Diagram's boxes.

Finding the cells a call's connector can run through, grouping them into connectors, and drawing the
down-and-up arrows from a calling Task to the Task it calls.  diagclean tidies what is left."""

from __future__ import annotations

from bisect import bisect_left
from typing import TYPE_CHECKING

from maptasker.src.core.error import rutroh_error
from maptasker.src.core.maputils import find_all_positions
from maptasker.src.core.sysconst import logger
from maptasker.src.mapgen.diagcnst import (
    CONNECTOR_DIRECTIONS,
    bar,
    blank,
    left_arrow,
    left_arrow_corner_down,
    right_arrow,
    right_arrow_corner_down,
    straight_line,
    task_delimeter,
)
from maptasker.src.mapgen.diagutil import icon_spans

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState
    from maptasker.src.core.runcfg import RunConfig


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


def bracket_list_end(text: str) -> int:
    """Where the bracketed list that `text` is the inside of ends: the position of its closing "]".

    A called Task's own name can end in a bracketed word (e.g. "Disable State [Write/Refresh]"),
    so the list ends at the first "]" that has no "[" before it, not at the first "]".

    Args:
        text (str): the line from just past the list's opening "[" and its "Calls ──▶ " or
            "Called by ◄── " marker.

    Returns:
        int: the position of the closing "]", or -1 if the list is never closed.
    """
    depth = 0
    for position, char in enumerate(text):
        if char == "[":
            depth += 1
        elif char == "]":
            if depth == 0:
                return position
            depth -= 1
    return -1


def get_index_setup(s: str, called_task_name: str) -> tuple[list, list] | None:
    """
    Parse the 'calls' string and return a tuple of substrings and positions

    Args:
        s (str): The string to parse
        called_task_name (str): The name of the task being called

    Returns:
        tuple | None: A tuple of two values. The first value is a list of substrings
            extracted from the string, and the second value is a list of positions
            of the called task name in the string.  None if the string has no
            "Calls" list to look in.

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
        return None

    # Extract the relevant substring after "Calls ──▶ "
    list_end = bracket_list_end(s[start_search:])
    temp_line = (s[start_search : start_search + list_end] if list_end != -1 else s[start_search:]).strip()

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
    setup = get_index_setup(s, called_task_name)
    if setup is None:  # No "Calls" list in this line, so the called Task is nowhere in it.
        return -1
    substrings, positions = setup

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


# How many blank cells of interruption a straight run can bridge over before giving up and
# treating the run as genuinely ended.  Foreign connector characters are bridged without limit.
_MAX_BRIDGE = 4


def _reachable_neighbors(lines: list, r: int, c: int, max_bridge: int = _MAX_BRIDGE) -> list:
    """The connector cells the one at (r, c) joins to, looking past what interrupts a straight run.

    See compute_diagram_connector_groups() for why a run needs bridging at all.
    """
    found = []
    for dr, dc in CONNECTOR_DIRECTIONS[lines[r][c]]:
        nr, nc = r + dr, c + dc
        blanks = 0
        while 0 <= nr < len(lines) and 0 <= nc < len(lines[nr]):
            nchar = lines[nr][nc]
            if nchar in CONNECTOR_DIRECTIONS and (-dr, -dc) in CONNECTOR_DIRECTIONS[nchar]:
                found.append((nr, nc))
                break
            # Not a continuation -- keep looking past it only if it's something a real,
            # unrelated line (box border, task text, ...) would never sit on top of.
            if nchar == " ":
                # Only blanks count against the limit.  A long run can cross a whole
                # bundle of other connectors' bars standing shoulder to shoulder (dozens
                # of them where a busy Task is called from many places); counting those
                # too cut the run in two at the bundle, leaving the half that reaches
                # the called Task a stub with no caller and nothing to jump to.
                blanks += 1
                if blanks > max_bridge:
                    break
            elif nchar not in CONNECTOR_DIRECTIONS:
                break
            nr, nc = nr + dr, nc + dc
    return found


def _grow_connector(lines: list, seed_cell: tuple[int, int], visited: set) -> list[tuple[int, int]]:
    """Every cell of the connector the seed lies on, found by flood fill; the cells are added to `visited`."""
    # Flood-fill this connector's connected cells, following only the directions each
    # character actually continues the path in.
    cells = []
    stack = [seed_cell]
    visited.add(seed_cell)
    while stack:
        r, c = stack.pop()
        cells.append((r, c))
        for nr, nc in _reachable_neighbors(lines, r, c):
            if (nr, nc) in visited:
                continue
            visited.add((nr, nc))
            stack.append((nr, nc))
    return cells


def _cells_to_ranges(cells: list[tuple[int, int]]) -> list[tuple[int, int, int]]:
    """A connector's cells compacted into per-row (line_num, col_start, col_end) ranges."""
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
    return ranges


def _display_geometry(lines: list) -> tuple[list, list, list]:
    """Lay the lines out by the screen columns their characters are drawn in.

    An icon, or a Chinese/Japanese/Korean character, is one character but two columns wide, and
    remove_icon has taken blanks out of the lines to make up for that.  Connectors that line up on
    screen therefore sit at different character positions on a row with one in it and a row
    without, and a flood fill by character position loses the connector at that row.

    Args:
        lines: the finished Diagram lines.

    Returns:
        tuple[list, list, list]: the lines with each wide character spread over the two cells it is
        drawn in, and for each line the character that each cell is, and the cell each character starts at.
    """
    display_lines, cell_to_char, char_to_cell = [], [], []
    for line in lines:
        spans = dict(icon_spans(line))
        cells, chars, starts = [], [], []
        position = 0
        while position < len(line):
            end = spans.get(position)
            if end is None:
                starts.append(len(cells))
                cells.append(line[position])
                chars.append(position)
                position += 1
                continue
            # The whole icon is one wide character: two cells, the second one not a blank.
            starts.extend([len(cells)] * (end - position))
            cells.extend([line[position], "\x00"])
            chars.extend([position, position])
            position = end
        display_lines.append("".join(cells))
        cell_to_char.append(chars)
        char_to_cell.append(starts)
    return display_lines, cell_to_char, char_to_cell


def compute_diagram_connector_groups(lines: list, seeds: list, state: RunState) -> dict:
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
    visited: set = set()
    groups: dict = {}
    group_of_cell: dict = {}
    calls_by_group: dict = {}
    group_id = 0

    # Connectors are followed by the columns they are drawn in, and put back into character
    # positions at the end, which is what the view slices the lines by.
    cells_by_line, cell_to_char, char_to_cell = _display_geometry(lines)

    for row, col, call_index in seeds:
        seed_cell = find_diagram_connector_seed_cell(lines, row, col)
        if seed_cell is None:
            continue
        seed_cell = (row, char_to_cell[row][seed_cell[1]])
        # A seed landing on a connector already grown from an earlier seed adds its call to
        # that group rather than being discarded: three seeds are dropped per call, and two
        # calls whose runs touch share the one group.
        if seed_cell in visited:
            existing = group_of_cell.get(seed_cell)
            if existing is not None and call_index not in calls_by_group[existing]:
                calls_by_group[existing].append(call_index)
            continue

        cells = _grow_connector(cells_by_line, seed_cell, visited)
        groups[group_id] = cells
        calls_by_group[group_id] = [call_index]
        for cell in cells:
            group_of_cell[cell] = group_id
        group_id += 1

    # Compact each group's cells into per-row (line_num, col_start, col_end) ranges.
    ranges_by_group = {
        gid: _cells_to_ranges([(row, cell_to_char[row][cell]) for row, cell in cells]) for gid, cells in groups.items()
    }

    state.diagram_connector_calls = calls_by_group
    return ranges_by_group


# Add up and down arrows to the connection points.
def add_down_and_up_arrows(connectors: dict, output_lines: list, config: RunConfig, state: RunState) -> tuple[int, int]:
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
        config: the run's settings (debug)
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
    state.diagram_connector_seeds.append((line_to_modify, called_task_position, connectors["call_index"]))

    # Add left arrows to called Task line.  First find next available blank line.
    line_to_modify1 = called_line_num - called_line_index
    line_count = 0
    while output_lines[line_to_modify1] and output_lines[line_to_modify1][caller_task_position] != " ":
        line_to_modify1 -= 1
        line_count += 1
        if line_count > 20:
            if config.debug:
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
    state.diagram_connector_seeds.append((line_to_modify1, caller_task_position, connectors["call_index"]))

    # Return the top-most modified output line hnumber.
    return line_to_modify, line_to_modify1


# Draw arrows to called Task from Task doing the calling.
def _line_with_arrow(line: str, up_down_location: int, use_arrow: str) -> str:
    """One output line with `use_arrow` put at `up_down_location`, bars and delimiters kept in line.

    Args:
        line (str): the line as it stands, task delimiters and all.
        up_down_location (int): the column the arrow goes in.
        use_arrow (str): the up, down, corner, bar or straight-line character to draw there.

    Returns:
        str: the line with the arrow in it.
    """
    # If there are bars inside of up_down_location, then we need to leave them there.
    temp_line = line.replace(task_delimeter, "")
    temp_line = temp_line.ljust(up_down_location)
    front_line = temp_line[:up_down_location]
    # Adjust bars if there are task delimeters in the line.
    # Some lines still have delimeters.  We need to fix the bars beyond the delimeters so they align properly
    # ith the bars above them.
    delimeters = find_all_positions(line, task_delimeter)
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
    return f"{front_line}{use_arrow}{back_line}"


def _record_call_edge(connector: dict, state: RunState) -> int:
    """Record the call this connector is about to be drawn for, and return its index.

    Recorded before any of it is drawn: the two Task lines it joins are known here and nowhere
    further down, and every seed dropped later carries this index so the finished connector can
    be traced back to it.
    """
    call_index = len(state.diagram_call_edges)
    state.diagram_call_edges[call_index] = {
        "caller_row": connector["caller_line_num"],
        "called_row": connector["called_line_num"],
        "caller_name": connector.get("caller_task_name", ""),
        "called_name": connector["called_task_name"],
        "project": connector.get("project_name", ""),
    }
    return call_index


def draw_arrows_to_called_task(
    up_down_location: int,
    connector: dict,
    output_lines: list,
    called_task_lookup: dict,
    config: RunConfig,
    state: RunState,
) -> dict:
    """
    Draw arrows to called Task from Task doing the calling.
        Args:
            up_down_location (int): Position on line where the up or down arrow should be drawn.
            connector (dict): The call table connector being drawn.
            output_task_lines (list): List of all output lines.
            called_task_lookup (dict): Dictionary of called task tracker.
            config (RunConfig): the run's settings.

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
    state.called_task_tracker[called_task_name]["counter"] += 1

    call_index = _record_call_edge(connector, state)

    # Add up and down arrows to the connection points.
    connectors = {
        "caller_line_index": caller_line_index,
        "caller_line_num": caller_line_num,
        "caller_task_position": caller_task_position,
        "called_line_index": state.called_task_tracker[called_task_name]["counter"],
        "called_line_num": called_line_num,
        "called_task_position": called_task_position,
        "up_down_location": up_down_location,
    }
    connectors["call_index"] = call_index
    line_to_modify, line_to_modify1 = add_down_and_up_arrows(connectors, output_lines, config, state=state)

    # Fill called line with left arrows.  Figure out if we are top-down or bottom-up,
    # and assign start_line and line_count accordingly.
    if called_line_num > caller_line_num:
        start_line = line_to_modify
        # Take into account the index of the current "calls ->" called Task
        line_count -= line_to_modify - (caller_line_num - state.called_task_tracker[called_task_name]["counter"])
    else:
        # Find the first free line above the called Task
        start_line = line_to_modify1
        line_count = line_to_modify - start_line

    # Record a seed for the GUI's click-to-highlight feature: output_lines[start_line] always gets
    # upper_corner_arrow (a non-bar connector character) at up_down_location below, in the loop's
    # x == 0 case, so this cell is guaranteed to survive remove_empty_strings() (which only drops
    # lines that are nothing but bar/space/backslash). See compute_diagram_connector_groups().
    state.diagram_connector_seeds.append((start_line, up_down_location, call_index))

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
        output_lines[start_line + x] = _line_with_arrow(output_lines[start_line + x], up_down_location, use_arrow)

    return called_task_lookup
