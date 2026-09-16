#! /usr/bin/env python3
"""Get/Put XML file"""

#                                                                                      #
# getbakup: get the backup file directly from the Android device                       #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import os.path
from os import getcwd

import defusedxml.ElementTree as ET

from maptasker.src.error import error_handler
from maptasker.src.maputil2 import http_request
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.xmldata import parse_tasker_xml, rewrite_xml


# We've read in the xml backup file.  Now save it for processing.
def write_out_backup_file(file_contents: bin) -> None:
    """
    We've read in the xml backup file.  Now save it for processing.

        :param file_contents: binary contents of XML file
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


# Set up to fetch the Tasker XML file from the Android device running
def get_backup_file() -> str:
    """
    Set up to fetch the Tasker XML file from the Android device running
    the Tasker server

        :return: The name of the backup file (e.g. backup.xml)
    """

    # If running from the GUI, then we have already gotten the file. Just return the name on the local drive.add
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
        logger.debug(f"return_code:{return_code}")
        if PrimeItems.program_arguments["gui"]:
            PrimeItems.error_code = return_code
            return None
        error_handler(str(file_contents), 8)

    # Write the XML file to local storage.
    write_out_backup_file(file_contents)

    return substring_after_last(PrimeItems.program_arguments["android_file"], "/")


# Validate XML
def validate_xml(
    ip_address: str,
    android_file: str,
    return_code: int,
    file_contents: str,
) -> tuple:
    # Run loop since we may have to rerun validation if unicode error
    """Validates an XML file and returns an error message and the parsed XML tree.
    Parameters:
        android_file (str): The path to the XML file to be validated.
        return_code (int): The return code from the validation process.
        file_contents (str): The contents of the XML file.
        ip_address (str): The TCP/IP address of the Android device or blank.
    Returns:
        error_message (str): A message describing any errors encountered during validation.
        xml_tree (ElementTree): The parsed XML tree if validation was successful.
    Processing Logic:
        - Runs a loop to allow for revalidation in case of a unicode error.
        - Sets the process_file flag to False to exit the loop if validation is successful or an error is encountered.
        - If validation is successful, sets the xml_tree variable to the parsed XML tree.
        - If an error is encountered, sets the error_message variable to a descriptive message and exits the loop.
        - If a unicode error is encountered, rewrites the XML file and loops one more time.
        - If any other error is encountered, sets the error_message variable to a descriptive message and exits the loop.
        - Returns the error_message and xml_tree variables."""
    process_file = True
    error_message = ""
    counter = 0
    xml_tree = None
    _write_out_backup_file = write_out_backup_file
    _get_the_xml_data = get_the_xml_data
    _rewrite_xml = rewrite_xml

    # Loop until we get a valid XML file or invalid XML
    while process_file:
        # Validate the file
        if return_code == 0:
            # Process the XML file
            PrimeItems.program_arguments["android_file"] = android_file

            # If getting file from Android device, write out the backup file first.
            if ip_address:
                _write_out_backup_file(file_contents)

            # We don't have the file yet.  Lets get it.
            else:
                return_code = _get_the_xml_data()
                if return_code != 0:
                    return PrimeItems.error_msg, None

            # Run the XML file through the XML parser to validate it.
            try:
                filename_location = android_file.rfind(PrimeItems.slash) + 1
                file_to_validate = PrimeItems.program_arguments["android_file"][filename_location:]
                xml_tree = parse_tasker_xml(file_to_validate, encoding=" iso8859_9")
                process_file = False  # Get out of while/loop
            except ET.ParseError:  # Parsing error
                error_message = f"Improperly formatted XML in {android_file}. Try again."
                process_file = False  # Get out of while/loop
            except UnicodeDecodeError:  # Unicode error
                _rewrite_xml(file_to_validate)
                counter += 1
                if counter > 2:
                    error_message = f"Unicode error in {android_file}.  Try again."
                    break
                process_file = True  # Loop one more time.
            except (OSError, LookupError) as e:
                # What is left once ParseError and UnicodeDecodeError are taken above: the
                # file not being readable, and the hard-coded parser encoding not being a
                # codec this interpreter knows.
                error_message = f"XML parsing error {e} in file {android_file}.\n\nTry again."
                process_file = False  # Get out of while/loop

    return error_message, xml_tree


# Read XML file and validate the XML.
def validate_xml_file(ip_address: str, port: str, android_file: str) -> bool:
    # Read the file
    """Validates an XML file from an Android device.
    Parameters:
        - ip_address (str): IP address of the Android device.
        - port (str): Port number of the Android device.
        - android_file (str): Name of the XML file to be validated.
    Returns:
        - bool: True if the file is valid, False if not.
    Processing Logic:
        - Reads the file from the Android device.
        - Validates the XML file.
        - Checks if the file is Tasker XML.
        - Returns True if the file is valid, False if not."""
    if ip_address:
        return_code, file_contents = http_request(
            ip_address,
            port,
            android_file,
            "file",
            "?download=1",
        )
        if return_code != 0:
            return 1, file_contents
    else:
        return_code = 0

    # Validate the xml
    error_message, xml_tree = validate_xml(
        ip_address,
        android_file,
        return_code,
        file_contents,
    )

    # If there was an error, bail out.
    if error_message:
        logger.debug(error_message)
        return 1, error_message

    # Make surre this is Tasker XML
    xml_root = xml_tree.getroot()
    if xml_root.tag != "TaskerData":
        return 0, f"File {android_file} is not valid Tasker XML.\n\nTry again."

    return 0, ""
