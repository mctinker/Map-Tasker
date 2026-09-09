#! /usr/bin/env python3
"""Error handling module for MapTasker."""

from maptasker.src import console
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ERROR_FILE, Colors, logger


def error_handler(error_message: str, exit_code: int) -> None:
    """
    Error handler: print and log the error.  Exit with error code if provided
        :param error_message: text of error to print and log
        :param exit_code: error code to exit with
    """
    from maptasker.src.maputils import exit_program  # noqa: PLC0415

    # Add our heading to more easily identify the problem
    if exit_code in {0, 99}:
        final_error_message = f"{Colors.Green}{error_message}"
    # Warning?
    elif exit_code == 100:
        final_error_message = f"{Colors.Yellow}{error_message}"
    else:
        final_error_message = f"{Colors.Red}MapTasker error: {error_message}"

    # Process an error?
    if exit_code > 0 and exit_code < 100:
        # Show it on the terminal only where there is a user watching one: in GUI mode the
        # message goes to the window instead (just below).  Either way it is recorded --
        # console.error logs what it shows, and logger.debug covers the quiet case.
        if (
            PrimeItems.program_arguments
            and PrimeItems.program_arguments["debug"]
            and not PrimeItems.program_arguments["gui"]
        ) or exit_code == 5:
            console.error(final_error_message)
        else:
            logger.debug(final_error_message)

        # If coming from GUI, set error info. and return to GUI.
        if PrimeItems.program_arguments and PrimeItems.program_arguments["gui"]:
            # Write the rror to file for use by userinter (e.g. on rerun), so userintr can display error on entry.
            with open(ERROR_FILE, "w") as error_file:
                error_file.write(f"{error_message}\n")
                error_file.write(f"{exit_code}\n")
            # Set error info. for GUI to display.
            PrimeItems.error_code = exit_code
            PrimeItems.error_msg = error_message
            return
        # Not coming from GUI.  Stop the run, carrying the code with it.
        exit_program(exit_code)

    # If exit code is 100, then the user closed the window
    elif exit_code == 100:
        console.say(final_error_message)
        exit_program(0)

    # return code 0
    else:
        console.say(final_error_message)
        return


def rutroh_error(message: str) -> None:
    """
    Prints or logs an error message.
    Args:
        message (str): The error message to print
    Returns:
        None: Does not return anything
    """
    console.debug(f"Rutroh! {message}")
