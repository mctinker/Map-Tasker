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


def align_text(text: str, column: int) -> str:
    """
    Aligns the given text so that its first non-&nbsp; character starts at the specified column.

    :param text: The input string where '&nbsp;' is treated as a space.
    :param column: The desired starting column for the first non-&nbsp; character.
    :return: The aligned string.
    """
    nbsp = "&nbsp;"
    stripped_text = text.lstrip(nbsp)  # Remove leading '&nbsp;' characters
    leading_spaces = (len(text) - len(stripped_text)) // len(
        nbsp,
    )  # Count '&nbsp;' as spaces
    adjusted_column = max(0, column - leading_spaces)  # Ensure non-negative padding

    return (nbsp * adjusted_column) + text  # Adjust spacing to align correctly
