#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# twisty: add special twisty to output                                                       #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.sysconst import logger, FormatLine


def add_twisty(
    primary_items: dict, output_color_name: str, line_to_output: str
) -> None:
    """
    Add the necessary html to hide the follow-on text under a twisty ►
        :param primary_items:  Program registry.  See primitem.py for details.
        :param output_color_name: name of the color to insert into the html
        :param line_to_output: text line to output into the html
        :return: nothing.  Add formatted html with the twisty magic
    """
    # Add the "twisty" to hide the Task details
    primary_items["output_lines"].add_line_to_output(
        primary_items,
        5,
        f"\n<details><summary>{line_to_output}</summary>\r",
        ["", output_color_name, FormatLine.add_end_span],
    )
    return


def remove_twisty(primary_items: dict) -> None:
    """
    Add the html element to stop the hidden items..so the follow-up stuff is not hidden
        :param primary_items:  Program registry.  See primitem.py for details.
        :return: nothing.  The output line is modified to include "</details>"
    """
    # Replace the last line (</ul>) with </ul></details> to end the twisty/hidden items
    # If our unordered list counter is zero, then only insert the </details>
    if primary_items["unordered_list_count"] == 0:
        primary_items["output_lines"].output_lines[-1] = "</details>\n"
    elif primary_items["unordered_list_count"] > 0:
        primary_items["unordered_list_count"] -= 1
        primary_items["output_lines"].output_lines[-1] = "</ul></details>\n"
        logger.info(
            f'linout twisty counter deducted: {str(primary_items["unordered_list_count"])}'
        )
    else:
        print("Rutroh!")
        import traceback

        traceback.print_tb()
        exit()

    return
