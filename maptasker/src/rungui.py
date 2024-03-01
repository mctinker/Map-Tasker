#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# rungui: process GUI for MapTasker                                                    #
#                                                                                      #
# Add the following statement (without quotes) to your Terminal Shell config file.     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                    #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                     #
#  "export TK_SILENCE_DEPRECATION = 1"                                                 #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
import contextlib
import sys

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.getputer import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES, logger


# ################################################################################
# Convert a value to integere, and if not an integer then use default value
# ################################################################################
def convert_to_integer(value_to_convert: str, default_value: int) -> int:
    """
    Convert a value to integere, and if not an integer then use default value
        Args:
            value_to_convert (str): The string value to convert to an integer
            where_to_put_it (int): Where to place the converted integer
            default_value (int):The default to plug in if the value to convert
                is not an integer
            :return: converted value as integer"""
    try:
        return int(value_to_convert)
    except (ValueError, TypeError):
        return default_value


# ##################################################################################
# Get the program arguments from GUI
# ##################################################################################
def process_gui(use_gui: bool) -> tuple[dict, dict]:
    """
    Present the GUI and get the runtime details
        :param pi: Primary Items instance
        :param use_gui: flag if usijng the GUI, make sure we import it
        :return: program runtime arguments and colors to use in the output
    """
    # global MyGui
    if use_gui:
        from maptasker.src.userintr import MyGui

    PrimeItems.program_arguments["gui"] = True  # Set flag to indicate we are using GUI

    # Get rid of any previous Tkinter window
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None
    # Display GUI and get the user input
    user_input = MyGui()
    user_input.mainloop()

    # Establish our runtime default values if we don't yet have 'em.
    if not PrimeItems.colors_to_use:
        PrimeItems.program_arguments = initialize_runtime_arguments()

    # If user selected the "Exit" button, call it quits.
    if user_input.exit:
        # Save our runtime settings for next time.
        _, _ = save_restore_args(PrimeItems.program_arguments, PrimeItems.colors_to_use, True)
        # Spit out the message and log it.
        error_handler("Program exited. Goodbye.", 0)
        sys.exit(0)

    # Has the user closed the window?
    if not user_input.go_program and not user_input.rerun:
        error_handler("Program cancelled by user (killed GUI)", 99)

    # 'Run' button hit.  Get all the input from GUI variables
    PrimeItems.program_arguments["gui"] = True
    # Do we already have the file object?
    if value := user_input.file:
        PrimeItems.file_to_get = value if isinstance(value, str) else value.name

    # Get the program arguments and save them in our dictionary
    for value in ARGUMENT_NAMES:
        with contextlib.suppress(AttributeError):
            PrimeItems.program_arguments[value] = getattr(user_input, value)
            logger.info(f"GUI arg: {value} set to: {getattr(user_input, value)}")

    # Convert display_detail_level to integer
    PrimeItems.program_arguments["display_detail_level"] = convert_to_integer(
        PrimeItems.program_arguments["display_detail_level"],
        4,
    )
    # Convert indent to integer
    PrimeItems.program_arguments["indent"] = convert_to_integer(PrimeItems.program_arguments["indent"], 4)
    # Get the font
    if the_font := user_input.font:
        PrimeItems.program_arguments["font"] = the_font

    # Appearance change: Dark or Light mode?
    colormap = set_color_mode(user_input.appearance_mode)

    # Process the colors
    if user_input.color_lookup:
        for key, value in user_input.color_lookup.items():
            colormap[key] = value

    PrimeItems.program_arguments["gui"] = True  # Set flag to indicate we are using GUI

    return (
        PrimeItems.program_arguments,
        colormap,
    )
