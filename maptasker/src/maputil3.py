#! /usr/bin/env python3
"""maputil3: installing an optional package the moment something needs it (ensure_and_import).

The AI modules use it for the libraries only an analysis needs.  It used to hold the XML file
checks as well; those are in getbakup now, beside the rest of getting a backup file.
"""

import importlib
import shutil
import subprocess
import sys

from maptasker.src import console


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

    console.say(f"MapTasker: --- Package {import_path} not found. Preparing installation... ---")

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
        console.say(f"MapTasker: --- Using uv to install {pypi_name} ---")
    else:
        cmd = [sys.executable, "-m", "pip", "install", pypi_name]
        console.say(f"MapTasker: --- Using pip to install {pypi_name} ---")

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
        console.error(f"MapTasker: --- Failed to provide Package {import_path}: {e} ---")
        return None
