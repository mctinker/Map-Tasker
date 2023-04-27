#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# Error: Process Errors                                                                      #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #
from maptasker.src.sysconst import logger


def error_handler(error_message: str, exit_code: int) -> None:
    """
    Error handler: print and log the error.  Exit with error code if provided
        :param error_message:
        :param exit_code:
    """
    # Add our heading to more easily identify the problem
    final_error_message = f"MapTasker error: {error_message}"

    # Print it out for the user
    print(final_error_message)
    # Log it as well
    logger.debug(final_error_message)
    if exit_code > 0:
        exit(exit_code)
