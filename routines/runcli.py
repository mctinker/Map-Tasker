# ########################################################################################## #
#                                                                                            #
# runcli: process command line interface arguments for MapTasker                            #
#                                                                                            #
# Add the following statement (without quotes) to your Terminal Shell configuration file     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                          #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                           #
#  "export TK_SILENCE_DEPRECATION = 1"                                                       #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
import sys

from routines import progargss as arg_support
from routines.colors import get_and_set_the_color
from routines.colors import validate_color
from config import *
from routines.rungui import process_gui


# #######################################################################################
# Get the program arguments (e.g. python maptasker.py -x)
# #######################################################################################
# Command line parameters
def process_cli(colormap):

    display_detail_level, single_task_name, single_profile_name, single_project_name = (
        1,
        "",
        "",
        "",
    )
    display_profile_conditions, debug = False, False

    args = sys.argv

    argument_precedence = " argument has precedence over "
    for arg in args:
        if arg == "mapTasker.py":
            continue
        logger.debug(f"arg:{arg} checking argument:{arg[:2]}")
        match arg[:2]:
            case "-v":  # Version
                print(MY_VERSION)
                print(MY_LICENSE)
                sys.exit()
            case "-h":  # Help
                arg_support.display_the_help()
            case "-d":  # Display detail level
                display_detail_level, debug = arg_support.get_detail_level(
                    arg, display_detail_level, debug
                )
            case "-g":  # GUI
                gui = True

                (
                    display_detail_level,
                    display_profile_conditions,
                    single_project_name,
                    single_profile_name,
                    single_task_name,
                    debug,
                ) = process_gui(colormap, True)
            case "-t":  # Task name
                if arg[1:6] == "task=":
                    if not single_profile_name:
                        single_task_name = arg[6:]
                    else:
                        print('"-profile"', f'{argument_precedence}"-task=".')
                else:
                    arg_support.report_bad_argument(arg)
            case "-c":  # Color
                if arg[:3] == "-ch":
                    validate_color("h")
                elif arg[:2] == "-c":
                    get_and_set_the_color(arg, colormap)
                else:
                    arg_support.report_bad_argument(arg)
            case "-p":  # This could be a Profile name, Project name, or Profile condition
                (
                    single_task_name,
                    single_profile_name,
                    single_project_name,
                    display_profile_conditions,
                ) = arg_support.get_dashp_specifics(
                    arg,
                    single_task_name,
                    single_profile_name,
                    single_project_name,
                    display_profile_conditions,
                    argument_precedence,
                )
            case _:
                if "maptasker" not in arg and "MapTasker" not in arg:
                    arg_support.report_bad_argument(arg)

    return (
        display_detail_level,
        display_profile_conditions,
        single_project_name,
        single_profile_name,
        single_task_name,
        debug,
    )
