#! /usr/bin/env python3
"""

 maputil3: General and GUI utilities.

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.

"""

import importlib
import shutil
import subprocess
import sys

from maptasker.src.maputil2 import http_request
from maptasker.src.maputils import validate_xml
from maptasker.src.sysconst import logger


def ensure_and_import(pypi_name: str, import_path: str) -> object:
    """
    Determine if a module is available, and if not, install it and then import it.
    Supports standard pip and uv-managed environments.
    Returns None if the module cannot be installed or imported.
    """
    # 1. Attempt to import if already present
    try:
        return importlib.import_module(import_path)
    except ImportError:
        pass

    print(f"MapTasker: --- Package {import_path} not found. Preparing installation... ---")

    # 2. Determine the installer command
    # Check if uv is available and if we are in a uv-managed env or if pip is missing
    has_uv = shutil.which("uv") is not None

    # Try to see if 'pip' module exists in the current sys.executable
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, check=True)
        use_uv = False
    except (subprocess.CalledProcessError, FileNotFoundError):
        use_uv = has_uv  # Use uv if pip failed but uv exists

    # Construct the command
    if use_uv:
        # 'uv pip install' targets the active virtualenv by default
        cmd = ["uv", "pip", "install", pypi_name]
        print(f"MapTasker: --- Using uv to install {pypi_name} ---")
    else:
        cmd = [sys.executable, "-m", "pip", "install", pypi_name]
        print(f"MapTasker: --- Using pip to install {pypi_name} ---")

    # 3. Execution
    try:
        subprocess.check_call(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

        importlib.invalidate_caches()

        # 4. Final Import
        return importlib.import_module(import_path)

    except (subprocess.CalledProcessError, ImportError) as e:
        print(f"MapTasker: --- Failed to provide Package {import_path}: {e} ---")
        return None


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
