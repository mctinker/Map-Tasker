#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# debug: special debug code for MapTasker                                              #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import sys

from maptasker.src.format import format_html
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    TYPES_OF_COLOR_NAMES,
    FormatLine,
    logger,
)


def output_debug_line(primary_items: dict, begin_or_end: str) -> None:
    """
    Put out a line that identifies the following output as DEBUG
        :param primary_items:  Program registry.  See primitem.py for details.
        :param begin_or_end: text identiying the beginning or end of debug
    """
    arrow = ">"
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        f"Runtime Settings {begin_or_end} {arrow * 80}",
        ["", "disabled_profile_color", FormatLine.add_end_span],
    )


# ##################################################################################
# Format a text line to a specific width by filling in blank spaces with periods.
# ##################################################################################
def format_line(text: str, width: int) -> str:
    """Format text line to given width by filling with periods"""

    formatted = text

    if len(text) < width:
        formatted += "." * (width - len(text))

    return formatted[:width]


# ################################################################################
# Display the program arguments and colors to use in output for debug purposes
# ################################################################################
def display_debug_info(primary_items: dict) -> None:
    """
    Output our runtime arguments
        :param primary_items:  Program registry.  See primitem.py for details.
    """

    # Add blank line
    primary_items["output_lines"].add_line_to_output(
        primary_items, 4, "", FormatLine.dont_format_line
    )

    # Identify the output as debug stuff
    output_debug_line(primary_items, "Start")
    if primary_items["program_arguments"]["debug"]:
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            f"sys.argv (runtime arguments):{str(sys.argv)}",
            ["", "disabled_profile_color", FormatLine.add_end_span],
        )

    # Copy our dictionary of runtime arguments and sort it alphabetically
    mydict = ARGUMENT_NAMES.copy()
    myKeys = sorted(mydict.keys())
    mydict = {i: mydict[i] for i in myKeys}

    # Go through dictionary of arguments and output each one.
    for key, value in mydict.items():
        try:
            line_formatted_to_length = format_line(ARGUMENT_NAMES[key], 40)
            value = primary_items["program_arguments"][key]
            if value is None or value == "":
                value = "None"
            # Set color for value
            if not value or value == "None":
                color_to_use = "unknown_task_color"
            else:
                color_to_use = "heading_color"
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                f"{line_formatted_to_length}: {value}",
                ["", color_to_use, FormatLine.add_end_span],
            )
        except KeyError:
            msg = f"{ARGUMENT_NAMES[key]}: Error...not found!"
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                msg,
                ["", "heading_color", FormatLine.add_end_span],
            )
            logger.debug(f"MapTasker Error ... {msg}")
    primary_items["output_lines"].add_line_to_output(
        primary_items, 4, "", FormatLine.dont_format_line
    )

    # Do colors to use in output

    # Get our color names by reversing the lookup dictionary
    color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
    # Go through each color
    for key, value in primary_items["colors_to_use"].items():
        # Highlight background color.  Otherwise it won't be visible
        if key == "background_color":
            value = f"<mark>{value} (highlighted for visibility)</mark>"
        # Convert the name of the color to the color
        the_color = format_html(
            primary_items,
            key,
            "",
            value,
            True,
        )

        # Add the line formatted with HTML
        color_set_to_width = format_line(f"Color for {color_names[key]} set to", 40)
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            f"{ color_set_to_width}{the_color}",
            ["", "heading_color", FormatLine.add_end_span],
        )

    # Get a total count of action_code entries in our dictionary.
    # from maptasker.src.actionc import action_codes
    # num = sum(1 for key, value in action_codes.items())
    # primary_items["output_lines"].add_line_to_output(
    #     primary_items,
    #             4,
    #             format_html(
    #                 primary_items,
    #                 color_to_use,
    #                 "",
    #                 f"Number of Task Action codes = {num}",
    #                 True,
    #             ),
    #         )

    # Finalize debug info
    output_debug_line(primary_items, "End")
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        "",
        FormatLine.dont_format_line,
    )


# ##################################################################################
# Argument not found in dictionary
# ##################################################################################
def not_in_dictionary(primary_items: dict, type: str, code: str) -> None:
    """_summary_
    Handle condition if Action/Event/State code not found in our dictionary (actionc.py)
        Args:
            :param primary_items:  Program registry.  See primitem.py for details.
            type (str): name of condition: Action, State, Event
            code (str): the xml code
    """
    logger.debug(
        f"Error action code {code} not in the dictionary!",
    )
    if primary_items["program_arguments"]["debug"]:
        print(f"{type} code {code} not found in actionc!")
    return
