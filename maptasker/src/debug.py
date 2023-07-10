#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# debug: special debug code for MapTasker                                                    #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import sys

from maptasker.src.frmthtml import format_html


def output_debug_line(primary_items: dict, begin_or_end: str) -> None:
    """
    Put out a line that identifies the following output as DEBUG
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param begin_or_end: text identiying the beginning or end of debug
    """
    arrow = ">"
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items["colors_to_use"],
            "Red",
            "",
            f"DEBUG {begin_or_end} {arrow * 80}",
            True,
        ),
    )


def display_debug_info(primary_items: dict) -> None:
    """
    Output our runtime arguments
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
    """
    # Identify the output as debug stuff
    output_debug_line(primary_items, "Start")
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        format_html(
            primary_items["colors_to_use"],
            "unknown_task_color",
            "",
            f"sys.argv (runtime arguments):{str(sys.argv)}",
            True,
        ),
    )
    # )
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        '',
    )
    for key, value in primary_items["program_arguments"].items():
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            format_html(
                primary_items["colors_to_use"], "unknown_task_color", "", f"{key}: {value}", True
            ),
        )
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        '',
    )
    for key, value in primary_items["colors_to_use"].items():
        primary_items["output_lines"].add_line_to_output(
            primary_items,
            4,
            format_html(
                primary_items["colors_to_use"],
                "unknown_task_color",
                "",
                f"colormap for {key} set to {value}",
                True,
            ),
        )
    output_debug_line(primary_items, "End")
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        4,
        '',
    )
