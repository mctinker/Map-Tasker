#! /usr/bin/env python3

#                                                                                      #
# caveats: display program caveats                                                     #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #

from maptasker.src.format import format_html
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


def display_caveats() -> None:
    """
    Output the program caveats at the very end
    Inputs:
    - None
    Outputs:
    - None
    """

    caveats = [
        format_html(
            "trailing_comments_color",
            "",
            "CAVEATS:<br>",
            False,
        ),
        (
            "- This has only been tested on my own backup.xml file."
            "  For problems, report them on https://github.com/mctinker/Map-Tasker/issues .\n"
        ),
        ('- Tasks that are identified as "Unnamed/Anonymous" have no name and are considered Anonymous.\n'),
        (
            '- All attempts are made to retain embedded HTML (e.g. color=...>") in Tasker'
            " fields, but is stripped out of Action labels and TaskerNet comments.\n"
        ),
    ]

    # Let 'em know about Google API key
    if PrimeItems.program_arguments["preferences"]:
        caveats.append(
            "- Your Google API key is displayed in the Tasker preferences!\n",
        )

    if PrimeItems.program_arguments["display_detail_level"] > 0:  # Caveat about Actions
        caveats.append(
            "- Most but not all Task actions have been mapped and will display as such."
            "  Likewise for Profile conditions and Plug-ins.\n",
        )

    if (
        PrimeItems.program_arguments["display_detail_level"] == 0
    ):  # Caveat about -d0 option and 1st Action for unnamed Tasks
        caveats.append(
            '- For option -d0, Tasks that are identified as "Unnamed/Anonymous" will'
            " have their first Action only listed....\n  just like Tasker does.\n",
        )

    if PrimeItems.program_arguments["display_detail_level"] > 2:  # Caveat about labels being stripped of html
        caveats.extend(("- Task labels have been stripped of all html to avoid output formatting issues.\n",))

    if (
        PrimeItems.program_arguments["display_detail_level"] == 4
    ):  # Caveat about -d0 option and 1st Action for unnamed Tasks
        caveats.extend(
            (
                "- Inactive variables are global variables used in a Task which has not been run/used.\n",
                "- Unreference variables are global variables that may have been used in the past, but are no longer referenced and can be deleted.\n",
            ),
        )
    # Start the output
    PrimeItems.output_lines.add_line_to_output(0, "<hr>", FormatLine.dont_format_line)

    # Output all caveats
    for caveat in caveats:
        PrimeItems.output_lines.add_line_to_output(
            0,
            caveat,
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )
