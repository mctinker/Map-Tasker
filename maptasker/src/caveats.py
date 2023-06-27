#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# caveats: display program caveats                                                           #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

from maptasker.src.frmthtml import format_html


def display_caveats(primary_items: dict) -> None:
    """
    Output the program caveats at the very end
    Inputs:
    - primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
    Outputs:
    - None
    """

    caveat1 = format_html(
        primary_items["colors_to_use"],
        "trailing_comments_color",
        "",
        "CAVEATS:<br>",
        False,
    )
    caveat3 = (
        "- This has only been tested on my own backup.xml file."
        "  For problems, report them on https://github.com/mctinker/Map-Tasker/issues ."
    )
    caveat4 = (
        '- Tasks that are identified as "Unnamed/Anonymous" have no name and are'
        ' considered Anonymous.\n'
    )
    caveat6 = (
        '- All attempts are made to retain embedded HTML (e.g. color=...>") in Tasker'
        ' fields, but is stripped out of Action labels and TaskerNet comments.'
    )
    primary_items["output_lines"].add_line_to_output(primary_items, 0, "<hr>")  # line
    primary_items["output_lines"].add_line_to_output(
        primary_items, 1, caveat1
    )  # caveat
    if (
        primary_items["program_arguments"]["display_detail_level"] > 0
    ):  # Caveat about Actions
        caveat2 = (
            "- Most but not all Task actions have been mapped and will display as such."
            "  Likewise for Profile conditions and Plug-ins.\n"
        )
        primary_items["output_lines"].add_line_to_output(
            primary_items, 4, caveat2
        )  # caveat
    primary_items["output_lines"].add_line_to_output(
        primary_items, 4, caveat3
    )  # caveat
    primary_items["output_lines"].add_line_to_output(
        primary_items, 4, caveat4
    )  # caveat
    if (
        primary_items["program_arguments"]["display_detail_level"] == 0
    ):  # Caveat about -d0 option and 1st Action for unnamed Tasks
        caveat5 = (
            '- For option -d0, Tasks that are identified as "Unnamed/Anonymous" will'
            ' have their first Action only listed....\n  just like Tasker does.\n'
        )
        primary_items["output_lines"].add_line_to_output(
            primary_items, 4, caveat5
        )  # caveat
    primary_items["output_lines"].add_line_to_output(
        primary_items, 4, f"{caveat6}</span>"
    )
    return
