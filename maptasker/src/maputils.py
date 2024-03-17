"""General Utilities"""

#! /usr/bin/env python3

# #################################################################################### #
#                                                                                      #
# maputils: General utilities used by program.                                         #
#                                                                                      #
# GNU General Public License v3.0                                                      #
# Permissions of this strong copyleft license are conditioned on making available      #
# complete source code of licensed works and modifications, which include larger works #
# using a licensed work, under the same license. Copyright and license notices must be #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# #################################################################################### #
from __future__ import annotations

import ipaddress
import json
import socket
import subprocess
import sys

import defusedxml.ElementTree as ET
import requests
from requests.exceptions import ConnectionError, InvalidSchema, Timeout

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger
from maptasker.src.xmldata import rewrite_xml


# ##################################################################################
# Validate TCP/IP Address
# ##################################################################################
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


# ##################################################################################
# Validate Port Number
# ##################################################################################
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


# ##################################################################################
# Auto Update our code
# ##################################################################################
def update() -> None:
    """Update this package."""
    version = get_pypi_version()
    packageversion = "maptasker" + version
    subprocess.call([sys.executable, "-m", "pip", "install", packageversion, "--upgrade"])  # noqa: S603


# ##################################################################################
# Get the version of our code out on Pypi
# ##################################################################################
def get_pypi_version() -> str:
    """Get the PyPi version of this package."""
    url = "https://pypi.org/pypi/maptasker/json"
    try:
        version = "==" + requests.get(url).json()["info"]["version"]  # noqa: S113
    except (json.decoder.JSONDecodeError, ConnectionError, Exception):
        version = ""
    return version


# ##################################################################################
# Issue HTTP Request to get something from the Android device.
# ##################################################################################
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
    try:
        response = requests.get(url, timeout=5)
    except InvalidSchema:
        error_message = f"Request failed for url: {url} .  Invalid url!"
    except ConnectionError:
        error_message = f"Request failed for url: {url} .  Connection error!"
    except Timeout:
        error_message = f"Request failed for url: {url} .  Timeout error.\n\nOr perhaps the profile 'MapTasker List' has not been imported into Tasker!"
    except Exception as e:
        error_message = f"Request failed for url: {url} .  Invalid url!"

    # If we have an error message, return as error.
    if error_message:
        logger.debug(error_message)
        return 8, error_message

    # Check the response status code.
    if response and response.status_code == 200:
        # Return the contents of the file.
        return 0, response.content

    if response and response.status_code == 404:
        return 6, "File " + file_location + " not found."

    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )


# ##################################################################################
# Read XML file and validate the XML.
# ##################################################################################
def validate_xml_file(ip_address: str, port: str, android_file: str) -> bool:
    """Validate XML file.
    Parameters:
        - ip_address (str): IP address of the server.
        - port (str): Port number of the server.
        - android_file (str): File name of the Android file.
    Returns:
        - bool: True if the file is valid, False otherwise.
    Processing Logic:
        - Read the file using HTTP request.
        - Run a loop to validate the file.
        - If there is a parsing error, return 1 and an error message.
        - If there is a Unicode error, rewrite the file and exit the loop.
        - If there is any other error, return 1 and an error message.
        - Check if the file is Tasker XML.
        - Return 0 and an empty string if the file is valid."""
    from maptasker.src.getbakup import write_out_backup_file

    # Read the file
    if ip_address:
        return_code, file_contents = http_request(ip_address, port, android_file, "file", "?download=1")
        if return_code != 0:
            return 1, file_contents
    else:
        return_code = 0

    # Run loop since we may have to rerun validation if unicode error
    process_file = True
    error_message = ""
    counter = 0
    while process_file:
        # Validate the file
        if return_code == 0:
            # Process the XML file
            PrimeItems.program_arguments["android_file"] = android_file
            write_out_backup_file(file_contents)

            # Run the XML file through the XML parser to validate it.
            try:
                filename_location = android_file.rfind(PrimeItems.slash) + 1
                file_to_validate = PrimeItems.program_arguments["android_file"][filename_location:]
                xmlp = ET.XMLParser(encoding=" iso8859_9")
                xml_tree = ET.parse(file_to_validate, parser=xmlp)
                process_file = False  # Get out of while/loop
            except ET.ParseError:  # Parsing error
                error_message = f"Improperly formatted XML in {android_file}.\n\nTry again."
                process_file = False  # Get out of while/loop
            except UnicodeDecodeError:  # Unicode error
                rewrite_xml(file_to_validate)
                counter += 1
                if counter > 2:
                    error_message = f"Unicode error in {android_file}.\n\nTry again."
                    break
                process_file = True  # Loop one more time.
            except Exception as e:  # any other errorError out and exit
                error_message = f"XML parsing error {e} in file {android_file}.\n\nTry again."
                process_file = False  # Get out of while/loop

    # If there was an error, bail out.
    if error_message:
        logger.debug(error_message)
        return 1, error_message

    # Make surre this is Tasker XML
    xml_root = xml_tree.getroot()
    if xml_root.tag != "TaskerData":
        return 0, f"File {android_file} is not valid Tasker XML.\n\nTry again."

    return 0, ""
