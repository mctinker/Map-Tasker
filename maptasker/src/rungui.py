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

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.sysconst import ARGUMENT_NAMES, logger


def delete_gui(MyGui, user_input):
    # Hide the window
    MyGui.withdraw(user_input)
    # Delete the GUI
    MyGui.quit(user_input)
    del user_input
    del MyGui


# ################################################################################
# Convert a value to integere, and if not an integer then use default value
# ################################################################################
def convert_to_integer(value_to_convert: str, default_value: int) -> int:
    """_summary_
    Convert a value to integere, and if not an integer then use default value
        Args:
            value_to_convert (str): The string value to convert to an integer
            where_to_put_it (int): Where to place the converted integer
            default_value (int):The default to plug in if the value to convert
                is not an integer
            :return: converted value as integer
    """
    try:
        return int(value_to_convert)
    except (ValueError, TypeError):
        return default_value


# ##################################################################################
# Get the program arguments from GUI
# ##################################################################################
def process_gui(primary_items, use_gui: bool) -> tuple[dict, dict]:
    """
    Present the GUI and get the runtime details
        :param primary_items:  Program registry.  See primitem.py for details.
        :param use_gui: flag if usijng the GUI, make sure we import it
        :return: program runtime arguments and colors to use in the output
    """
    global MyGui
    if use_gui:
        from maptasker.src.userintr import MyGui

    # Display GUI and get the user input
    user_input = MyGui()
    user_input.mainloop()

    # If user selected the "Exit" button, call it quits.
    if user_input.exit:
        error_handler("Program exited. Goodbye.", 0)

    # User has either closed the window or hit the 'Run' or 'ReRun' button
    if not user_input.go_program and not user_input.rerun:
        error_handler("Program cancelled be user (killed GUI)", 99)

        # Convert runtime argument default values to a dictionary with default values
    primary_items["program_arguments"] = initialize_runtime_arguments()

    # 'Run' button hit.  Get all the input from GUI variables
    primary_items["program_arguments"]["gui"] = True
    # Do we already have the file object?
    if value := user_input.file:
        primary_items["file_to_get"] = value if isinstance(value, str) else value.name
    # Get the program arguments and save them in our dictionary
    for value in ARGUMENT_NAMES:
        # Special handling for backup file
        if value == "backup_file_http":
            if http_info := getattr(user_input, value):
                primary_items["program_arguments"][value] = f"http://{http_info}"
        else:
            # Get the program arguments from the GUI and save them
            # into our runtime arguments dictonary (of same name)
            with contextlib.suppress(AttributeError):
                primary_items["program_arguments"][value] = getattr(user_input, value)
                logger.info(f"GUI arg: {value} set to: {getattr(user_input, value)}")

    # Convert display_detail_level to integer
    primary_items["program_arguments"]["display_detail_level"] = convert_to_integer(
        primary_items["program_arguments"]["display_detail_level"], 3
    )
    # Convert indent to integer
    primary_items["program_arguments"]["indent"] = convert_to_integer(
        primary_items["program_arguments"]["indent"], 4
    )
    # Get the font
    if the_font := getattr(user_input, "font"):
        primary_items["program_arguments"]["font"] = the_font

    # Appearance change: Dark or Light mode?
    colormap = set_color_mode(user_input.appearance_mode)

    # Process the colors
    if user_input.color_lookup:
        for key, value in user_input.color_lookup.items():
            colormap[key] = value

    # Delete the GUI
    delete_gui(MyGui, user_input)

    return (
        primary_items["program_arguments"],
        colormap,
    )
