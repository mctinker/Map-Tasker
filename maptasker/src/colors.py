#! /usr/bin/env python3

#                                                                                      #
# colors: get and set the program colors                                               #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
import string

from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import TYPES_OF_COLOR_NAMES, logger


# Given a list [x,y,z] , print as x y z
def print_list(title: str, parse_items: list) -> None:
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
        print(title)
    for item in parse_items:
        if parse_items.index(item) == list_length:  # Last item in list?
            seperator = ""
        line_out = f"{line_out}{item}{seperator}"
    print(line_out)


# Validate the color name provided.  If color name is 'h', simply display all the colors
def validate_color(the_color: str) -> object:
    """
    Validate the color name provided.
        If color name is 'h', simply display all the colors and exit.
        IF the color passed in is hexidecimal, simply return True
        Else return the color if it is valid
        param: the_color: the color as a hexidecimal number, "h" for help, or
            a color name
        :rtype: object: True if a hexadecimal color was provided, or the color name
    """
    red_color_names = [
        "IndianRed",
        "LightCoral",
        "Salmon",
        "DarkSalmon",
        "LightSalmon",
        "Crimson",
        "Red",
        "FireBrick",
        "DarkRed",
    ]
    pink_color_names = [
        "Pink",
        "LightPink",
        "HotPink",
        "DeepPink",
        "MediumVioletRed",
        "PaleVioletRed",
    ]
    orange_color_names = [
        "LightSalmon",
        "Coral",
        "Tomato",
        "OrangeRed",
        "DarkOrange",
        "Orange",
    ]
    yellow_color_names = [
        "Gold",
        "Yellow",
        "LightYellow",
        "LemonChiffon",
        "LightGoldenrodYellow",
        "PapayaWhip",
        "Moccasin",
        "PeachPuff",
        "PaleGoldenrod",
        "Khaki",
        "DarkKhaki",
    ]
    purple_color_names = [
        "Lavender",
        "Thistle",
        "Plum",
        "Violet",
        "Orchid",
        "Fuchsia",
        "Magenta",
        "MediumOrchid",
        "MediumPurple",
        "RebeccaPurple",
        "BlueViolet",
        "DarkViolet",
        "DarkOrchid",
        "DarkMagenta",
        "Purple",
        "Indigo",
        "SlateBlue",
        "DarkSlateBlue",
        "MediumSlateBlue",
    ]
    green_color_names = [
        "GreenYellow",
        "Chartreuse",
        "LawnGreen",
        "Lime",
        "LimeGreen",
        "PaleGreen",
        "LightGreen",
        "MediumSpringGreen",
        "SpringGreen",
        "MediumSeaGreen",
        "SeaGreen",
        "ForestGreen",
        "Green",
        "DarkGreen",
        "YellowGreen",
        "OliveDrab",
        "Olive",
        "DarkOliveGreen",
        "MediumAquamarine",
        "DarkSeaGreen",
        "LightSeaGreen",
        "DarkCyan",
        "Teal",
    ]
    blue_color_names = [
        "Aqua",
        "Cyan",
        "LightCyan",
        "PaleTurquoise",
        "Aquamarine",
        "Turquoise",
        "MediumTurquoise",
        "DarkTurquoise",
        "CadetBlue",
        "SteelBlue",
        "LightSteelBlue",
        "PowderBlue",
        "LightBlue",
        "SkyBlue",
        "LightSkyBlue",
        "DeepSkyBlue",
        "DodgerBlue",
        "CornflowerBlue",
        "MediumSlateBlue",
        "RoyalBlue",
        "Blue",
        "MediumBlue",
        "DarkBlue",
        "Navy",
        "MidnightBlue",
    ]
    brown_color_names = [
        "Cornsilk",
        "BlanchedAlmond",
        "Bisque",
        "NavajoWhite",
        "Wheat",
        "BurlyWood",
        "Tan",
        "RosyBrown",
        "SandyBrown",
        "Goldenrod",
        "DarkGoldenrod",
        "Peru",
        "Chocolate",
        "SaddleBrown",
        "Sienna",
        "Brown",
        "Maroon",
    ]
    white_color_names = [
        "White",
        "Snow",
        "HoneyDew",
        "MintCream",
        "Azure",
        "AliceBlue",
        "GhostWhite",
        "WhiteSmoke",
        "SeaShell",
        "Beige",
        "OldLace",
        "FloralWhite",
        "Ivory",
        "AntiqueWhite",
        "Linen",
        "LavenderBlush",
        "MistyRose",
    ]
    gray_color_names = [
        "Gainsboro",
        "LightGray",
        "Silver",
        "DarkGray",
        "Gray",
        "DimGray",
        "LightSlateGray",
        "SlateGray",
        "DarkSlateGray",
        "Black",
    ]
    any_color = ["hex value.  Example 'db29ff'"]

    all_colors = (
        red_color_names
        + pink_color_names
        + orange_color_names
        + yellow_color_names
        + purple_color_names
        + green_color_names
        + blue_color_names
        + brown_color_names
        + white_color_names
        + gray_color_names
        + any_color
    )

    if the_color != "h":
        logger.debug(the_color in all_colors)
        #  Test for hexdigits
        if all(c in string.hexdigits for c in the_color):
            return True
        # Return True/False based on whether it is in our named colors
        return the_color in all_colors
    print_list("\nRed color names:", red_color_names)
    print_list("\nPink color names:", pink_color_names)
    print_list("\nOrange color names:", orange_color_names)
    print_list("\nYellow color names:", yellow_color_names)
    print_list("\nPurple color names:", purple_color_names)
    print_list("\nGreen color names:", green_color_names)
    print_list("\nBlue color names:", blue_color_names)
    print_list("\nBrown color names:", brown_color_names)
    print_list("\nWhite color names:", white_color_names)
    print_list("\nGray color names:", gray_color_names)
    print_list("\nAny color:", any_color)
    exit(0)


# Get the runtime option for a color change and set it
def get_and_set_the_color(the_arg: str) -> None:
    """
    Get the runtime option for a color change and set it
        :param the_arg: the color runtime argument (e.g. "cProfile=Blue" or
            "cProfile Blue")
        :return: nothing
    """
    the_color_option = the_arg[2:].split("=")
    color_type = the_color_option[0]
    if len(the_color_option) < 2:  # Do we have the second parameter?
        error_handler(f"{the_arg} has an invalid 'color'.  See the help (-ch)!", 7)
    if color_type not in TYPES_OF_COLOR_NAMES:
        error_handler(
            (f"{color_type} is an invalid type for 'color'.  See the help (-h)!  Exit code 7"),
            7,
        )
    desired_color = the_color_option[1]
    logger.debug(f" desired_color:{desired_color}")
    if validate_color(desired_color):  # If the color provided is valid...
        # match color_type:
        PrimeItems.colors_to_use[TYPES_OF_COLOR_NAMES[color_type]] = desired_color
    else:
        error_handler(
            (f"MapTasker...invalid color specified: {desired_color} for 'c{the_color_option[0]}'!"),
            7,
        )
