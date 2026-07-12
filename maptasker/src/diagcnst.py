"""Diagram Constants"""

#! /usr/bin/env python3
#                                                                                      #
# diagram: Output a diagram/map of the Tasker configuration.                           #
#                                                                                      #
# Traverse our network map and print out everything in connected boxes.                #
#                                                                                      #
bar = "│"
box_line = "═"
blank = " "
straight_line = "─"
line_right_arrow = f"{straight_line*2}▶"
line_left_arrow = f"◄{straight_line*2}"
down_arrow = "▼"
up_arrow = "▲"
left_arrow = "◄"
right_arrow = "►"
task_delimeter = "¥"
angle = "└─ "
angle_elbow = "└"

right_arrow_corner_down = "╰"
right_arrow_corner_up = "╯"
left_arrow_corner_down = "╭"
left_arrow_corner_up = "╮"

# Every character a Diagram-view connector (the lines joining a "calls" Task to its
# "called by" Task) can be made of, and which side(s) of each character continue the
# connector's path -- (row, col) deltas -- for identifying a connector's full shape
# directly from the rendered text. See diagram.compute_diagram_connector_groups().
#
# Ordinary tree/outline hierarchy guide lines are drawn with these same characters (e.g.
# "│"), so character identity alone can't tell a "calls" connector apart from one of
# those -- but direction can: a straight run only ever continues left/right or up/down,
# and only a corner character legitimately turns between the two. That keeps an outer
# connector's horizontal line from being mistaken for a join with an unrelated vertical
# guide line it happens to pass right next to.
_UP, _DOWN, _LEFT, _RIGHT = (-1, 0), (1, 0), (0, -1), (0, 1)
CONNECTOR_DIRECTIONS = {
    straight_line: {_LEFT, _RIGHT},
    bar: {_UP, _DOWN},
    # Arrowheads are only ever drawn at the start/end of one straight run of a connector's
    # path, but the path itself can continue past them (via a corner) toward the other
    # Task -- so for connectivity purposes they behave like a plain straight_line/bar.
    right_arrow: {_LEFT, _RIGHT},
    left_arrow: {_LEFT, _RIGHT},
    down_arrow: {_UP, _DOWN},
    up_arrow: {_UP, _DOWN},
    right_arrow_corner_down: {_UP, _RIGHT},
    right_arrow_corner_up: {_UP, _LEFT},
    left_arrow_corner_down: {_DOWN, _RIGHT},
    left_arrow_corner_up: {_DOWN, _LEFT},
}
CONNECTOR_CHARS = frozenset(CONNECTOR_DIRECTIONS)
