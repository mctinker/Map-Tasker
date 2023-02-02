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
import routines.outputl as build_output
from config import *


def display_caveats(output_list: list[str], program_args: dict, colormap: dict) -> None:
    """output the program caveats

    Parameters: list into which all output has been added, the program runtime arguments,
                the dictionary of colors to use

    Returns: the count of the number of times the program has been called

    """
    caveat1 = (
        f'<span style = "color:{trailing_comments_color}"'
        + program_args["font_to_use"]
        + "</span>CAVEATS:\n"
    )
    caveat3 = (
        "- This has only been tested on my own backup.xml file."
        "  For problems, report them on https://github.com/mctinker/MapTasker."
    )
    caveat4 = '- Tasks that are identified as "Unnamed/Anonymous" have no name and are considered Anonymous.\n'
    caveat6 = '- Task labels that have embedded HTML "<color=...>" will result in the remaining label displayed in that same color.'
    build_output.my_output(colormap, program_args, output_list, 0, "<hr>")  # line
    build_output.my_output(colormap, program_args, output_list, 4, caveat1)  # caveat
    if program_args["display_detail_level"] > 0:  # Caveat about Actions
        caveat2 = "- Most but not all Task actions have been mapped and will display as such.  Likewise for Profile conditions.\n"
        build_output.my_output(
            colormap, program_args, output_list, 4, caveat2
        )  # caveat
    build_output.my_output(colormap, program_args, output_list, 4, caveat3)  # caveat
    build_output.my_output(colormap, program_args, output_list, 4, caveat4)  # caveat
    if (
        program_args["display_detail_level"] == 0
    ):  # Caveat about -d0 option and 1sat Action for unnamed Tasks
        caveat5 = (
            '- For option -d0, Tasks that are identified as "Unnamed/Anonymous" will have their first Task only listed....\n'
            "  just like Tasker does.\n"
        )
        build_output.my_output(
            colormap, program_args, output_list, 4, caveat5
        )  # caveat
    build_output.my_output(colormap, program_args, output_list, 4, caveat6)  # caveat
    return
