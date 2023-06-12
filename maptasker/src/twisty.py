#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# twisty: add special twisty to output                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from maptasker.src.frmthtml import format_html


def add_twisty(primary_items, output_color_name, line_to_output):
    # Add the "twisty" to hide the Task details
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        format_html(
            primary_items["colors_to_use"],
            output_color_name,
            "",
            f"<br><details><summary>{line_to_output}</summary>",
            True,
        ),
    )
    return
