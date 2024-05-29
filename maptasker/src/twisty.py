#! /usr/bin/env python3

#                                                                                      #
# twisty: add special twisty to output                                                 #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FormatLine


def add_twisty(output_color_name: str, line_to_output: str) -> None:
    """
    Add the necessary html to hide the follow-on text under a twisty ►

        :param output_color_name: name of the color to insert into the html
        :param line_to_output: text line to output into the html
        :return: nothing.  Add formatted html with the twisty magic
    """
    # Add the "twisty" to hide the Task details
    PrimeItems.output_lines.add_line_to_output(
        5,
        f"\n<span class='tasktab'><details><summary>{line_to_output}</summary>\r",
        # f"\n<details><summary><span class='tasktab'>{line_to_output}</span></summary>\r",
        ["", output_color_name, FormatLine.add_end_span],
    )


def remove_twisty() -> None:
    """
    Add the html element to stop the hidden items..so the follow-up stuff is not hidden

        :return: nothing.  The output line is modified to include "</details>"
    """
    PrimeItems.output_lines.output_lines[-1] = "</details></span><br>\n"
