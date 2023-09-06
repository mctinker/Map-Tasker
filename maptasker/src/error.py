#! /usr/bin/env python3

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
from maptasker.src.sysconst import logger, Colors


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

    # Log and print the error
    logger.critical(final_error_message)
    if exit_code > 0:
        exit(exit_code)
