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

from maptasker.src.sysconst import DEBUG_PROGRAM


# #######################################################################################
# Get the program arguments (e.g. python mapit.py -x)
# #######################################################################################
def get_program_arguments(primary_items: dict):
    # Are we using the GUI?
    if GUI:
        (
            primary_items["program_arguments"],
            primary_items["colors_to_use"],
        ) = process_gui(primary_items, True)

    # Command line parameters
    else:
        primary_items = process_cli(primary_items)

    # Are we in development mode?  If so, override debug argument
    if DEBUG_PROGRAM:
        primary_items["program_arguments"]["debug"] = True

    return primary_items
