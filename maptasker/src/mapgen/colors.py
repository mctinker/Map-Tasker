#! /usr/bin/env python3

#                                                                                      #
# colors: get and set the program colors                                               #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
"""colors: get and set the program colors."""

import json
import os
import string
from functools import cache

from maptasker.src.core import console
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import RunState
from maptasker.src.core.sysconst import TYPES_OF_COLOR_NAMES, logger

# The named colors, by family, are data: assets/json/color_names.json.  Resolved off this file
# rather than the working directory, which proginit changes (see actionc._JSON_DIR).
COLOR_NAMES_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "color_names.json"),
)
# Not a name but a description of what else is accepted; it is listed last by '-ch', and
# (as it always has been) is itself accepted as a color.
ANY_COLOR = ["hex value.  Example 'db29ff'"]


@cache
def color_names() -> dict[str, list[str]]:
    """The named colors by family -- {"Red": ["IndianRed", ...], ...} -- read the first time they are wanted."""
    with open(COLOR_NAMES_FILE, encoding="utf-8") as file:
        return json.load(file)


# Given a list [x,y,z] , print as x y z
def print_list(title: str, parse_items: list[str]) -> None:
    """
    Given a list [x,y,z] , print as x y z
        :param title: the heading to output
        :param parse_items: a list of items separated by commas
        :return: nothing
    """
    line_out = ""
    seperator = ", "
    list_length = len(parse_items) - 1
    if title:
        console.say(title)
    for item in parse_items:
        if parse_items.index(item) == list_length:  # Last item in list?
            seperator = ""
        line_out = f"{line_out}{item}{seperator}"
    console.say(line_out)


# Validate the color name provided.  If color name is 'h', simply display all the colors
def validate_color(the_color: str) -> bool:
    """
    Validate the color name provided.
        If color name is 'h', simply display all the colors and exit.
        IF the color passed in is hexidecimal, simply return True
        Else return the color if it is valid
        param: the_color: the color as a hexidecimal number, "h" for help, or
            a color name
        :rtype: object: True if a hexadecimal color was provided, or the color name
    """
    families = color_names()

    if the_color != "h":
        all_colors = [name for names in families.values() for name in names] + ANY_COLOR
        logger.debug(the_color in all_colors)
        #  Test for hexdigits
        if all(c in string.hexdigits for c in the_color):
            return True
        # Return True/False based on whether it is in our named colors
        return the_color in all_colors
    for family, names in families.items():
        print_list(f"\n{family} color names:", names)
    print_list("\nAny color:", ANY_COLOR)
    # The colour list IS the run when "-ch" is given: there is nothing else to do once it
    # is on screen.  Raised rather than exit()ed so the GUI and the test suite survive
    # somebody asking for it; mapit_all turns it into a clean exit.
    raise MapTaskerError(exit_code=0)


# Get the runtime option for a color change and set it
def get_and_set_the_color(the_arg: str, state: RunState) -> None:
    """
    Get the runtime option for a color change and set it
        :param the_arg: the color runtime argument (e.g. "cProfile=Blue" or
            "cProfile Blue")
        :return: nothing
    """
    the_color_option = the_arg[2:].split("=")
    color_type = the_color_option[0]
    if len(the_color_option) < 2:  # Do we have the second parameter?
        message = f"{the_arg} has an invalid 'color'.  See the help (-ch)!"
        raise MapTaskerError(message, 7)
    if color_type not in TYPES_OF_COLOR_NAMES:
        message = f"{color_type} is an invalid type for 'color'.  See the help (-h)!"
        raise MapTaskerError(message, 7)
    desired_color = the_color_option[1]
    logger.debug(f" desired_color:{desired_color}")
    if validate_color(desired_color):  # If the color provided is valid...
        # match color_type:
        state.colors_to_use[TYPES_OF_COLOR_NAMES[color_type]] = desired_color
    else:
        message = f"MapTasker...invalid color specified: {desired_color} for 'c{the_color_option[0]}'!"
        raise MapTaskerError(message, 7)
