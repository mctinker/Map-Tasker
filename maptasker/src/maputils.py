"""General Utilities"""

#! /usr/bin/env python3

#                                                                                      #
# maputils: General utilities used by program.                                         #
#                                                                                      #
from __future__ import annotations

import ipaddress
import json
import os
import socket
import subprocess
import sys
from contextlib import contextmanager
from typing import Generator

import defusedxml.ElementTree as et  # noqa: N813
import requests
from requests.exceptions import ConnectionError, InvalidSchema, Timeout

from maptasker.src.getbakup import write_out_backup_file
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger
from maptasker.src.taskerd import get_the_xml_data
from maptasker.src.xmldata import rewrite_xml


@contextmanager
def suppress_stdout() -> Generator:  # type: ignore  # noqa: PGH003
    """
    Context manager that suppresses the standard output during its execution.

    This context manager redirects the standard output to `/dev/null`, effectively suppressing any output.
    It uses the `open` function to open `/dev/null` in write mode and assigns it to the `devnull` variable.
    Then, it saves the current standard output in the `old_stdout` variable.
    After that, it sets the standard output to `devnull`.

    The `yield` statement is used to enter the context manager's block.
    Once the block is executed, the `finally` block is executed to restore the standard output to its original value.

    This context manager is useful when you want to suppress the standard output of a specific block of code."""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr


# Validate TCP/IP Address
def validate_ip_address(address: str) -> bool:
    """
    Validates an IP address.

    Args:
        address (str): The IP address to validate.

    Returns:
        bool: True if the IP address is valid, False otherwise.
    """
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False
    return True


# Validate Port Number
def validate_port(address: str, port_number: int) -> bool:
    """
    Validates a port number.

    Args:
        address (str): The address to connect to.
        port_number (int): The port number to validate.

    Returns:
        bool: True if the port number is valid, False otherwise.
    """
    if port_number.isdigit():
        port_int = int(port_number)
    else:
        return 1
    if port_int < 1024 or port_int > 65535:
        return 1
    if address:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_addr = (address, port_int)
        result = sock.connect_ex(server_addr)
        sock.close()
        return result
    return 0


# Auto Update our code
def update() -> None:
    """Update this package."""
    version = get_pypi_version()
    packageversion = "maptasker" + version
    subprocess.call([sys.executable, "-m", "pip", "install", packageversion, "--upgrade"])  # noqa: S603


# Get the version of our code out on Pypi
def get_pypi_version() -> str:
    """Get the PyPi version of this package."""
    url = "https://pypi.org/pypi/maptasker/json"
    try:
        version = "==" + requests.get(url).json()["info"]["version"]  # noqa: S113
    except (json.decoder.JSONDecodeError, ConnectionError, Exception):
        version = ""
    return version


# Issue HTTP Request to get something from the Android device.
def http_request(
    ip_address: str,
    ip_port: str,
    file_location: str,
    request_name: str,
    request_parm: str,
) -> tuple[int, object]:
    """
    Issue HTTP Request to get the backup XML file from the Android device.
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
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/{request_name}{file_location}{request_parm}"

    # Make the request.
    error_message = ""
    response = ""

    with suppress_stdout():  # Suppress any errors (system IMK)
        try:
            response = requests.get(url, timeout=5)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to get XML from Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error.  Or perhaps the profile 'MapTasker List' has not been imported into Tasker on the Android device!"
        except Exception as e:
            error_message = f"Request failed for url: {url}, error: {e} ."

    # If we have an error message, return as error.
    if error_message:
        logger.debug(error_message)
        return 8, error_message

    # Check the response status code.  200 is good!
    if response and response.status_code == 200:
        # Return the contents of the file.
        return 0, response.content

    if response and response.status_code == 404:
        return 6, "File " + file_location + " not found."

    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )


# Validate XML
def validate_xml(ip_address: str, android_file: str, return_code: int, file_contents: str) -> tuple:
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

    # Loop until we get a valid XML file or invalid XML
    while process_file:
        # Validate the file
        if return_code == 0:
            # Process the XML file
            PrimeItems.program_arguments["android_file"] = android_file

            # If getting file from Android device, write out the backup file first.
            if ip_address:
                write_out_backup_file(file_contents)

            # We don't have the file yet.  Lets get it.
            else:
                return_code = get_the_xml_data()
                if return_code != 0:
                    return PrimeItems.error_msg, None

            # Run the XML file through the XML parser to validate it.
            try:
                filename_location = android_file.rfind(PrimeItems.slash) + 1
                file_to_validate = PrimeItems.program_arguments["android_file"][filename_location:]
                xmlp = et.XMLParser(encoding=" iso8859_9")
                xml_tree = et.parse(file_to_validate, parser=xmlp)
                process_file = False  # Get out of while/loop
            except et.ParseError:  # Parsing error
                error_message = f"Improperly formatted XML in {android_file}. Try again."
                process_file = False  # Get out of while/loop
            except UnicodeDecodeError:  # Unicode error
                rewrite_xml(file_to_validate)
                counter += 1
                if counter > 2:
                    error_message = f"Unicode error in {android_file}.  Try again."
                    break
                process_file = True  # Loop one more time.
            except Exception as e:  # any other errorError out and exit  # noqa: BLE001
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
        return_code, file_contents = http_request(ip_address, port, android_file, "file", "?download=1")
        if return_code != 0:
            return 1, file_contents
    else:
        return_code = 0

    # Validate the xml
    error_message, xml_tree = validate_xml(ip_address, android_file, return_code, file_contents)

    # If there was an error, bail out.
    if error_message:
        logger.debug(error_message)
        return 1, error_message

    # Make surre this is Tasker XML
    xml_root = xml_tree.getroot()
    if xml_root.tag != "TaskerData":
        return 0, f"File {android_file} is not valid Tasker XML.\n\nTry again."

    return 0, ""


# If we have set the single Project name due to a single Task or Profile name, then reset it.
def reset_named_objects() -> None:
    """_summary_
    Reset the single Project name if it was set due to a single Task or Profile name.
    Parameters:
        None
    Returns:
        None
    """
    # Check in name hierarchy: Task then Profile
    if PrimeItems.program_arguments["single_task_name"]:
        PrimeItems.program_arguments["single_project_name"] = ""
        PrimeItems.found_named_items["single_project_found"] = False
        PrimeItems.program_arguments["single_profile_name"] = ""
        PrimeItems.found_named_items["single_profile_found"] = False
    elif PrimeItems.program_arguments["single_profile_name"]:
        PrimeItems.program_arguments["single_project_name"] = ""
        PrimeItems.found_named_items["single_project_found"] = False
        PrimeItems.program_arguments["single_task_name"] = ""
        PrimeItems.found_named_items["single_task_found"] = False
