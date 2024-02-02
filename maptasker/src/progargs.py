"""Process runtime program arguments"""

#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# progargs: process program runtime arguments for MapTasker                            #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #

from maptasker.src.config import GUI
from maptasker.src.primitem import PrimeItems
from maptasker.src.runcli import process_cli
from maptasker.src.rungui import process_gui
from maptasker.src.sysconst import DEBUG_PROGRAM


# ##################################################################################
# Get the program arguments (e.g. python mapit.py -x)
# ##################################################################################
def get_program_arguments() -> None:
    # Are we using the GUI?
    """
    Process program arguments from GUI or CLI.
    Args:
        GUI: Whether GUI is being used
        DEBUG_PROGRAM: Whether program is in debug mode
    Returns:
        None: No return value
    - Parse GUI for program arguments and colors if GUI is being used
    - Parse command line if no GUI
    - Override debug argument to True if in debug mode"""
    if GUI:
        PrimeItems.program_arguments["gui"] = True

    # Process the command line runtime options
    process_cli()

    # Do GUI processing if GUI is being used
    if GUI:
        process_gui(True)

    # Are we in development mode?  If so, override debug argument
    if DEBUG_PROGRAM:
        PrimeItems.program_arguments["debug"] = True
