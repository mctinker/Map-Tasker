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
from maptasker.src.frmthtml import format_html
from maptasker.src.sysconst import ARGUMENT_NAMES, TYPES_OF_COLOR_NAMES, logger


def output_debug_line(primary_items: dict, begin_or_end: str) -> None:
    """
    Put out a line that identifies the following output as DEBUG
        :param primary_items:  program registry.  See mapit.py for details.
        :param begin_or_end: text identiying the beginning or end of debug
    """
    arrow = ">"
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items,
            "Red",
            "",
            f"Runtime Settings {begin_or_end} {arrow * 80}",
            True,
        ),
    )


# ################################################################################
# Display the program arguments and colors to use in output for debug purposes
# ################################################################################
def display_debug_info(primary_items: dict) -> None:
    """
    Output our runtime arguments
        :param primary_items:  program registry.  See mapit.py for details.
    """
    
    # Identify the output as debug stuff
    output_debug_line(primary_items, "Start")
    if primary_items["program_arguments"]["debug"]:
        primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items,
            "Red",
            "",
            f"sys.argv (runtime arguments):{str(sys.argv)}",
            True,
        ),
    )

    # Copy our dictionary of runtime arguments and sort it alphabetically
    mydict = ARGUMENT_NAMES.copy()
    myKeys = sorted(mydict.keys())
    mydict = {i: mydict[i] for i in myKeys}

    # Go through dictionary of arguments and output each one.
    for key, value in mydict.items():
        try:
            value = primary_items["program_arguments"][key]
            if value is None or value == "":
                value = "None"
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                format_html(
                    primary_items,
                    "heading_color",
                    "",
                    f"{ARGUMENT_NAMES[key]}: {value}",
                    True,
                ),
            )
        except KeyError:
            msg = f"{ARGUMENT_NAMES[key]}: Error...not found!"
            primary_items["output_lines"].add_line_to_output(
                primary_items,
                4,
                format_html(
                    primary_items,
                    "heading_color",
                    "",
                    msg,
                    True,
                ),
            )
            logger.debug(f"MapTasker Error ... {msg}")
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        "",
    )

    # Do colors to use in putput

    # Get our color names by reversing the lookup dictionary
    color_names = {v: k for k, v in TYPES_OF_COLOR_NAMES.items()}
    # Go through each color
    for key, value in primary_items["colors_to_use"].items():
        # Highlight background color.  Otherwise it won't be visible
        if key == "background_color":
            value = f'<mark>{value} (highlighted for visibility)</mark>'
        # Convert the namee of the color to the color
        the_color = format_html(
            primary_items,
            key,
            "",
            value,
            True,
        )

        # Add the line formatted with HTML
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            format_html(
                primary_items,
                "heading_color",
                "",
                f"Color for {color_names[key]} set to {the_color}",
                True,
            ),
        )
    output_debug_line(primary_items, "End")
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        "",
    )


# ##################################################################################
# Argument not found in dictionary
# ##################################################################################
def not_in_dictionary(primary_items: dict, type: str, code: str) -> None:
    """_summary_
    Handle condition if Action/Event/State code not found in our dictionary (actionc.py)
        Args:
            :param primary_items:  Program registry.  See mapit.py for details.
            type (str): name of condition: Action, State, Event
            code (str): the xml code
    """
    logger.debug(
        f"Error action code {code} not in the dictionary!",
    )
    if primary_items["program_arguments"]["debug"]:
        print(f"{type} code {code} not found in actionc!")
    return
