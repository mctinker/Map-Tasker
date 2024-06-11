#! /usr/bin/env python3
"""special debug code for MapTasker

Returns:
    _type_: _description_
"""

#                                                                                      #
# debug: special debug code for MapTasker                                              #
#                                                                                      #
import sys

from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import (
    ARGUMENT_NAMES,
    TYPES_OF_COLOR_NAMES,
    FormatLine,
    logger,
)


def output_debug_line(begin_or_end: str) -> None:
    """
    Put out a line that identifies the following output as DEBUG

        :param begin_or_end: text identiying the beginning or end of debug
    """
    arrow = ">"
    PrimeItems.output_lines.add_line_to_output(
        0,
        f"Runtime Settings {begin_or_end} {arrow * 80}",
        ["", "disabled_profile_color", FormatLine.add_end_span],
    )


# Format a text line to a specific width by filling in blank spaces with periods.
def format_line_debug(text: str, width: int) -> str:
    """Format text line to given width by filling with periods"""

    formatted = text

    if len(text) < width:
        formatted += "." * (width - len(text))

    return formatted[:width]


# ################################################################################
# Display the program arguments and colors to use in output for debug purposes
# ################################################################################
def display_debug_info() -> None:
    """
    Output our runtime arguments
    """

    # Add blank line
    PrimeItems.output_lines.add_line_to_output(0, "", FormatLine.dont_format_line)

    # Identify the output as debug stuff
    output_debug_line("Start")
    if PrimeItems.program_arguments["debug"]:
        PrimeItems.output_lines.add_line_to_output(
            0,
            f"sys.argv (runtime arguments):{sys.argv!s}",
            ["", "disabled_profile_color", FormatLine.add_end_span],
        )

    # Copy our dictionary of runtime arguments and sort it alphabetically
    mydict = ARGUMENT_NAMES.copy()
    mykeys = sorted(mydict.keys())
    mydict = {i: mydict[i] for i in mykeys}

    # Go through dictionary of arguments and output each one.
    for key, value in mydict.items():
        try:
            line_formatted_to_length = format_line_debug(ARGUMENT_NAMES[key], 40)
            value = PrimeItems.program_arguments[key]  # noqa: PLW2901
            if value is None or value == "":
                value = "None"  # noqa: PLW2901
            # Set color for value
            color_to_use = "unknown_task_color" if not value or value == "None" else "heading_color"
            PrimeItems.output_lines.add_line_to_output(
                0,
                f"{line_formatted_to_length}: {value}",
                ["", color_to_use, FormatLine.add_end_span],
            )
        except KeyError:  # noqa: PERF203
            msg = f"{ARGUMENT_NAMES[key]}: Error...not found!"
            PrimeItems.output_lines.add_line_to_output(
                0,
                msg,
                ["", "heading_color", FormatLine.add_end_span],
            )
            logger.debug(f"MapTasker Error ... {msg}")
    PrimeItems.output_lines.add_line_to_output(0, "", FormatLine.dont_format_line)

    # Do colors to use in output

    # Get our color names by reversing the lookup dictionary
    color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
    # Go through each color
    for key, value in PrimeItems.colors_to_use.items():
        # Highlight background color.  Otherwise it won't be visible
        if key == "background_color":
            value = f"<mark>{value} (highlighted for visibility)</mark>"  # noqa: PLW2901
        # Convert the name of the color to the color
        the_color = format_html(
            key,
            "",
            value,
            True,
        )

        # Add the line formatted with HTML
        color_set_to_width = format_line_debug(f"Color for {color_names[key]} set to", 40)
        PrimeItems.output_lines.add_line_to_output(
            0,
            f"{ color_set_to_width}{the_color}",
            ["", "heading_color", FormatLine.add_end_span],
        )

    # Get a total count of action_code entries in our dictionary.
    # from maptasker.src.actionc import action_codes
    # num = sum(1 for key, value in action_codes.items())
    # PrimeItems.output_lines.add_line_to_output(
    #
    #             0,
    #             format_html(
    #                 color_to_use,
    #                 "",
    #                 f"Number of Task Action codes = {num}",
    #                 True,
    #             ),
    #         )

    # Finalize debug info
    output_debug_line("End")
    PrimeItems.output_lines.add_line_to_output(
        0,
        "",
        FormatLine.dont_format_line,
    )


# Argument not found in dictionary
def not_in_dictionary(condition_type: str, code: str) -> None:
    """
    Handle condition if Action/Event/State code not found in our dictionary (actionc.py)
        Args:
            condition_type (str): name of condition: Action, State, Event
            code (str): the xml code"""
    logger.debug(
        f"Error action code {code} not in the dictionary!",
    )
    if PrimeItems.program_arguments["debug"]:
        print(f"{condition_type} code {code} not found in actionc!")
