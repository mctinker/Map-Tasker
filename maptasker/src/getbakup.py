#! /usr/bin/env python3

#                                                                                      #
# getbakup: get the backup file directly from the Android device                       #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import os.path
from os import getcwd

from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger


# We've read in the xml backup file.  Now save it for processing.
def write_out_backup_file(file_contents: bin) -> None:
    """
    We've read in the xml backup file.  Now save it for processing.

        :param file_contents: binary contents of backup xml file
        :return: Nothing
    """
    # Store the output in the current directory
    my_output_dir = getcwd()
    if my_output_dir is None:
        error_handler(
            "MapTasker canceled.  An error occurred in getbakup.  Program canceled.",
            2,
        )

    # We must get just the file name and type since we will be using this to save it to our local path.
    # This is the file we will do all of our processing against...the local file fetched from the Android device.
    # Get position of the last "/" in path/file
    name_location = PrimeItems.program_arguments["android_file"].rfind(PrimeItems.slash) + 1
    # Get the name of the file
    my_file_name = PrimeItems.program_arguments["android_file"][name_location:]

    # Convert the binary code to string
    output_lines = file_contents.decode("utf-8")

    # Set up the backup file full path
    the_backup_file = PrimeItems.program_arguments["android_file"]
    put_message = f"Fetching backup file {my_file_name}: {the_backup_file}"
    logger.debug(put_message)

    # If backup.xml already exists, delete it first
    if os.path.isfile(my_file_name):
        os.remove(my_file_name)

    # Open output file
    with open(my_file_name, "w") as out_file:
        # Write out each line
        for item in output_lines:
            item.rstrip()  # Get rid of trailing blanks
            out_file.write(item)

    # Set flag to identify that backup file was fetched from Android device
    PrimeItems.program_arguments["fetched_backup_from_android"] = True


# Return the substring after the last occurance of a specific character in a string
def substring_after_last(string: str, char: chr) -> str:
    """
    Return the substring after the last occurance of a specific character in a string
        Args:
            string (str): The string to search for the substring
            char (chr): The character to find (the last occurance of)

        Returns:
            str: The substring in string after the last occurance of char
    """
    index = string.rfind(char)
    return "" if index == -1 else string[index + 1 :]


# Set up to fetch the Tasker backup xml file from the Android device running
def get_backup_file() -> str:
    """
    Set up to fetch the Tasker backup xml file from the Android device running
    the Tasker server

        :return: The name of the backup file (e.g. backup.xml)
    """
    from maptasker.src.maputils import http_request

    # If ruinning from the GUI, then we have already gotten the file. Just return the name on the local drive.add
    if PrimeItems.program_arguments["gui"]:
        return substring_after_last(PrimeItems.program_arguments["android_file"], "/")

    # Get the contents of the file from the Android device.
    return_code, file_contents = http_request(
        PrimeItems.program_arguments["android_ipaddr"],
        PrimeItems.program_arguments["android_port"],
        PrimeItems.program_arguments["android_file"],
        "file",
        "?download=1",
    )

    if return_code != 0:
        if PrimeItems.program_arguments["gui"]:
            PrimeItems.error_code = return_code
            return None
        error_handler(str(file_contents), 8)

    # Write the XML file to local storage.
    write_out_backup_file(file_contents)

    return substring_after_last(PrimeItems.program_arguments["android_file"], "/")
