#! /usr/bin/env python3
"""Error handling module for MapTasker."""

import logging
from typing import NoReturn

from maptasker.src import console
from maptasker.src.mtexcept import MapTaskerError
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ERROR_FILE, Colors, logger


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


def close_logfile() -> None:
    """Close the log file(s)"""
    # The FileHandler lives on the ROOT logger, not on "MapTasker": maputil2.setup_logging() installs
    # it via logging.basicConfig(), and our logger simply propagates up to it.  Iterating
    # logger.handlers here would walk an empty list and close nothing at all.
    for target in (logger, logging.root):
        for handler in target.handlers[:]:  # Iterate over a copy to avoid issues during modification
            handler.close()  # Close the stream associated with the handler
            target.removeHandler(handler)  # Remove the handler from the logger


def exit_program(return_code: int = 0) -> NoReturn:
    """Stop the run, from anywhere, without stopping the interpreter.

    This used to be close_logfile() followed by sys.exit(), and every caller below it in
    this package inherited that: a Task name that did not match, a missing output
    directory, a corrupt XML file: each ended the process outright.

    That is only ever right when MapTasker is the whole program.  It no longer always is.
    The same functions run underneath a NiceGUI event loop, where SystemExit raised in a
    `run.io_bound` worker takes the server down instead of the one build that failed, and
    under pytest, where it ends the test session instead of the test.  diffload even had
    to force "gui" on solely to steer taskerd's error path away from here.

    So this raises MapTaskerError, which is an ordinary Exception and can therefore be
    caught, and mapit.mapit_all -- the top of the process -- turns it back into an exit
    status.  Callers need no change: control still leaves at the call, and the code still
    travels with it.

    Args:
        return_code: the status the process should end on if nothing catches this.  0 is
            a normal, deliberate shutdown and is raised just the same, because the point
            is to stop unwinding, not to report a failure.

    Raises:
        MapTaskerError: always.  This function has no normal return.
    """
    close_logfile()
    raise MapTaskerError(exit_code=return_code)
