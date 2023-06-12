#! /usr/bin/env python3

# ########################################################################################## #
#                                                                                            #
# getbakup: get the backup file directly from the Android device                             #
#                                                                                            #
# GNU General Public License v3.0                                                            #
# Permissions of this strong copyleft license are conditioned on making available            #
# complete source code of licensed works and modifications, which include larger works       #
# using a licensed work, under the same license. Copyright and license notices must be       #
# preserved. Contributors provide an express grant of patent rights.                         #
#                                                                                            #
# ########################################################################################## #

import requests
from os import getcwd
import os.path

from requests.exceptions import InvalidSchema

from maptasker.src.error import error_handler
from maptasker.src.sysconst import logger


def write_out_backup_file(primary_items: dict, file_contents: bin) -> None:
    """
    We've read in the xml backup file.  Now save it for processing.
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :param file_contents: binary contents of backup xml file
        :return: Nothing
    """
    # Store the output in the current directory
    my_output_dir = getcwd()
    if my_output_dir is None:
        error_handler(
            "MapTasker cancelled.  An error occurred in getbakup.  Program cancelled.",
            2,
        )

    # We are going to save the file as...
    # Get position of the last "/" in path/file
    name_location = (
        primary_items["program_arguments"]["backup_file_location"].rfind("/") + 1
    )
    # Get the name of the file
    my_file_name = primary_items["program_arguments"]["backup_file_location"][
        name_location:
    ]

    # Convert the binary code to string
    output_lines = file_contents.decode("utf-8")

    # Set up the backup file full path
    the_backup_file = primary_items["program_arguments"]["backup_file_location"]
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
    primary_items["program_arguments"]["fetched_backup_from_android"] = True

    return


def request_file(
    backup_file_http: str, backup_file_location: str
) -> tuple[int, object]:
    """
    Issue HTTP Request to get the backup xml file from the Android device.
    Tasker's HTTP Server Example must be installed for this to work:
    https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example
        :param backup_file_http: the port to use for the Android device's Tasker server
        :param backup_file_location: location of
        :return: return code, response: eitherr text string with error message or the contrents of the backup file
    """
    # Create the URL to request the backup xml file from the Android device running the Tasker server.
    url = f"{backup_file_http}/file{backup_file_location}?download=1"

    # Make the request.
    try:
        response = requests.get(url)
    except InvalidSchema:
        return (
            8,
            f"Request failed for url: {url}.  Invalid url!",
        )

    # Check the response status code.
    if response.status_code == 200:
        # Return the contents of the file.
        return 0, response.content
    elif response.status_code == 404:
        return 6, f"File '{backup_file_location}' not found."
    else:
        return (
            8,
            f"Request failed for url: {url} ...with status code {response.status_code}",
        )


def get_backup_file(primary_items: dict) -> None:
    """
    Set up to fetch the Tasker backup xml file from the Android device running the Tasker server
        :param primary_items: dictionary of the primary items used throughout the module.  See mapit.py for details
        :return nothing
    """
    # Get the contents of the file.
    return_code, file_contents = request_file(
        primary_items["program_arguments"]["backup_file_http"],
        primary_items["program_arguments"]["backup_file_location"],
    )

    if return_code != 0:
        error_handler(str(file_contents), 8)

    # Process the backup file
    write_out_backup_file(primary_items, file_contents)
