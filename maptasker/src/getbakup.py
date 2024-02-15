#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# getbakup: get the backup file directly from the Android device                       #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from __future__ import annotations

import os.path
from os import getcwd

import requests
from requests.exceptions import ConnectionError, ConnectTimeout, InvalidSchema

from maptasker.src.error import error_handler
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger


# ##################################################################################
# We've read in the xml backup file.  Now save it for processing.
# ##################################################################################
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
            "MapTasker cancelled.  An error occurred in getbakup.  Program cancelled.",
            2,
        )

    # We are going to save the file as...
    # Get position of the last "/" in path/file
    name_location = PrimeItems.program_arguments["android_file"].rfind("/") + 1
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


# ##################################################################################
# Issue HTTP Request to get the backup xml file from the Android device.
# ##################################################################################
def request_file(ip_addr: str, port_number: str, file_location: str) -> tuple[int, object]:
    """
    Issue HTTP Request to get the backup xml file from the Android device.
    Tasker's HTTP Server Example must be installed for this to work:
    https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example
        :param backup_file_http: the port to use for the Android device's Tasker server
        :param backup_file_location: location of
        :return: return code, response: eitherr text string with error message or the
        contents of the backup file
    """
    # Create the URL to request the backup xml file from the Android device running the
    # Tasker server.
    # Something like: 192.168.0.210:1821/file/path/to/backup.xml?download=1
    http = "http://" if "http://" not in ip_addr else ""
    url = f"{http}{ip_addr}:{port_number}/file{file_location}?download=1"

    # Make the request.
    try:
        response = requests.get(url, timeout=10)
    except InvalidSchema:
        return (
            8,
            f"Request failed for url: {url} .  Invalid url!",
        )
    except ConnectionError:
        return (
            8,
            f"Request failed for url: {url} .  Connection error!",
        )
    except ConnectTimeout:
        return (
            8,
            f"Request failed for url: {url} .  Timeout error!",
        )

    # Check the response status code.
    if response.status_code == 200:
        # Return the contents of the file.
        return 0, response.content
    if response.status_code == 404:
        return 6, f"File '{file_location}' not found."
    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )


# ##################################################################################
# Return the substring after the last occurance of a specific character in a string
# ##################################################################################
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


# ##################################################################################
# Set up to fetch the Tasker backup xml file from the Android device running
# ##################################################################################
def get_backup_file() -> str:
    """
    Set up to fetch the Tasker backup xml file from the Android device running
    the Tasker server

        :return: The name of the backup file (e.g. backup.xml)
    """
    # Get the contents of the file.
    return_code, file_contents = request_file(
        PrimeItems.program_arguments["android_ipaddr"],
        PrimeItems.program_arguments["android_port"],
        PrimeItems.program_arguments["android_file"],
    )

    if return_code != 0:
        if PrimeItems.program_arguments["gui"]:
            PrimeItems.error_code = return_code
            return None
        error_handler(str(file_contents), 8)

    # Process the backup file
    write_out_backup_file(file_contents)

    return substring_after_last(PrimeItems.program_arguments["android_file"], "/")
