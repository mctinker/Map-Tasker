"""Error handling module for MapTasker."""

#! /usr/bin/env python3
import sys

# #################################################################################### #
#                                                                                      #
# Error: Process Errors                                                                #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import Colors, logger


def error_handler(error_message: str, exit_code: int) -> None:
    """
    Error handler: print and log the error.  Exit with error code if provided
        :param error_message: text of error to print and log
        :param exit_code: error code to exit with
    """
    # Add our heading to more easily identify the problem
    if exit_code in {0, 99}:
        final_error_message = f"{Colors.Green}{error_message}"
    # Warning?
    elif exit_code > 100:
        final_error_message = f"{Colors.Yellow}{error_message}"
    else:
        final_error_message = f"{Colors.Red}MapTasker error: {error_message}"

    # Process an error?
    if exit_code > 0:
        logger.critical(final_error_message)
        if PrimeItems.program_arguments and PrimeItems.program_arguments["debug"]:
            print(final_error_message)

        # If coming from GUI, set error info. and return to GUI.
        if PrimeItems.program_arguments and PrimeItems.program_arguments["gui"]:
            PrimeItems.error_code = exit_code
            PrimeItems.error_msg = error_message
            return
        # Not coming from GUI...just print error.
        print(final_error_message)
        sys.exit(exit_code)

    # return code 0
    else:
        print(final_error_message)
        logger.info(final_error_message)
        return
