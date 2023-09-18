#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# caveats: display program caveats                                                     #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

from maptasker.src.frmthtml import format_html


def display_caveats(primary_items: dict) -> None:
    """
    Output the program caveats at the very end
    Inputs:
    - primary_items: Primary items used throughout the module.  See primitem.py for details
    Outputs:
    - None
    """

    caveats = [
        format_html(
            primary_items,
            "trailing_comments_color",
            "",
            "CAVEATS:<br>",
            False,
        ),
        (
            "- This has only been tested on my own backup.xml file."
            "  For problems, report them on https://github.com/mctinker/Map-Tasker/issues .\n"
        ),
        (
            '- Tasks that are identified as "Unnamed/Anonymous" have no name and are'
            " considered Anonymous.\n"
        ),
        (
            '- All attempts are made to retain embedded HTML (e.g. color=...>") in Tasker'
            " fields, but is stripped out of Action labels and TaskerNet comments.\n"
        ),
    ]

    # Let 'em know about Google API key
    if primary_items["program_arguments"]["preferences"]:
        caveats.append(
            "- Your Google API key is displayed in the Tasker preferences!\n",
        )

    if (
        primary_items["program_arguments"]["display_detail_level"] > 0
    ):  # Caveat about Actions
        caveats.append(
            "- Most but not all Task actions have been mapped and will display as such."
            "  Likewise for Profile conditions and Plug-ins.\n"
        )

    if (
        primary_items["program_arguments"]["display_detail_level"] == 0
    ):  # Caveat about -d0 option and 1st Action for unnamed Tasks
        caveats.append(
            '- For option -d0, Tasks that are identified as "Unnamed/Anonymous" will'
            " have their first Action only listed....\n  just like Tasker does.\n"
        )

    # Start the output
    primary_items["output_lines"].add_line_to_output(primary_items, 0, "<hr>")  # line

    # Output all caveats
    for caveat in caveats:
        primary_items["output_lines"].add_line_to_output(primary_items, 0, caveat)

    return
