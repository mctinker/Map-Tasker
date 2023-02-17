#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# progargs: process program runtime arguments for MapTasker                                  #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

from maptasker.src.config import GUI
from maptasker.src.runcli import process_cli
from maptasker.src.rungui import process_gui
from maptasker.src.sysconst import FONT_TO_USE
from maptasker.src.sysconst import DEBUG_PROGRAM


# #######################################################################################
# Get the program arguments (e.g. python mapit.py -x)
# #######################################################################################
def get_program_arguments(colormap: dict):
    # Are we using the GUI?
    if GUI:
        (
            display_detail_level,
            display_profile_conditions,
            display_taskernet,
            single_project_name,
            single_profile_name,
            single_task_name,
            debug,
            colormap,
        ) = process_gui(colormap, True)

    # Command line parameters
    else:
        (
            display_detail_level,
            display_profile_conditions,
            display_taskernet,
            single_project_name,
            single_profile_name,
            single_task_name,
            debug,
            colormap,
        ) = process_cli(colormap)

    # Are we in development mode?  If so, override debug argument
    if DEBUG_PROGRAM:
        debug = True

    return {
        "display_detail_level": display_detail_level,
        "single_task_name": single_task_name,
        "single_profile_name": single_profile_name,
        "single_project_name": single_project_name,
        "display_profile_conditions": display_profile_conditions,
        "display_taskernet": display_taskernet,
        "debug": debug,
        "font_to_use": FONT_TO_USE,
    }, colormap
