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
import ipaddress
import json
import socket
import subprocess
import sys

import requests

# from maptasker.src.primitem import PrimeItems


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
    subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", packageversion])  # noqa: S603


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
