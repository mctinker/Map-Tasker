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
def get_program_arguments(colormap: dict):
    # Are we using the GUI?
    if GUI:
        (
            prog_args,
            colormap,
        ) = process_gui(True)

    # Command line parameters
    else:
        (
            prog_args,
            colormap,
        ) = process_cli(colormap)

    # Are we in development mode?  If so, override debug argument
    if DEBUG_PROGRAM:
        prog_args["debug"] = True

    return prog_args, colormap
