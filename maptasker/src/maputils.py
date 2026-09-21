"""General Utilities"""

#! /usr/bin/env python3

#                                                                                      #
# maputils: General utilities used by program.                                         #
#                                                                                      #
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)  # Import ZoneInfoNotFoundError for specific error handling

import requests

from maptasker.src import clock, console
from maptasker.src.error import rutroh_error
from maptasker.src.format import format_html
from maptasker.src.getids import get_ids
from maptasker.src.mapjump import TASK, Target
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems, clear_single_items
from maptasker.src.sysconst import HOTLINK_STYLE, FormatLine, logger


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
        logger.debug(f"Invalid IP address: {address}")
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


# The commands our own install puts in the environment's script directory.  Reinstalling
# MapTasker overwrites them, which is the step that fails on Windows while one of them is
# the very process doing the upgrading (see move_locked_scripts_aside).
CONSOLE_SCRIPTS = ("maptasker.exe",)
# What a moved-aside script is renamed to.  It stays locked until we exit, so it is cleared
# away on the next upgrade rather than during this one.
STASHED_SCRIPT_SUFFIX = ".mtold"


def move_locked_scripts_aside() -> list[tuple[Path, Path]]:
    """Rename our console scripts so the installer has a free name to write them to.

    Windows will not let anything overwrite a running .exe, so reinstalling while MapTasker
    was started from its own 'maptasker' command dies with 'WinError 32 ... being used by
    another process' and nothing is upgraded at all.  Windows does allow a running .exe to
    be *renamed*, which is the standard way out: move it out of the way first and the
    installer writes a fresh one beside it, while this process keeps running from the file
    it already has open.

    Does nothing anywhere else -- every other platform happily replaces a running program's
    file.

    :return: the (original, renamed) pairs, so a failed install can put them back.
    """
    if sys.platform != "win32":
        return []

    script_dir = Path(sys.executable).parent  # ...\venv\Scripts, where python.exe lives
    moved = []
    for name in CONSOLE_SCRIPTS:
        script = script_dir / name
        if not script.is_file():
            continue
        stashed = script.with_name(f"{name}{STASHED_SCRIPT_SUFFIX}")
        # Left over from an earlier upgrade: by now nothing is running from it.
        with contextlib.suppress(OSError):
            stashed.unlink(missing_ok=True)
        try:
            script.rename(stashed)
        except OSError as e:
            # Out of our hands: let the installer run and report whatever it hits.
            logger.debug(f"Unable to move {script} aside before upgrading: {e}")
            continue
        moved.append((script, stashed))
    return moved


def restore_locked_scripts(moved: list[tuple[Path, Path]]) -> None:
    """Put back the console scripts move_locked_scripts_aside renamed, after a failed install.

    A script the installer did manage to write is left alone -- that one is the new version.

    :param moved: the (original, renamed) pairs returned by move_locked_scripts_aside.
    """
    for script, stashed in moved:
        if script.exists():
            continue
        with contextlib.suppress(OSError):
            stashed.rename(script)


# Auto Update our code
def update_maptasker() -> tuple[bool, str]:
    """Update this package using uv if available, otherwise fall back to pip.

    :return: (True, "") when the install succeeded, otherwise (False, what the installer
        said went wrong).  The caller must not restart into a version that was never
        installed, so a failure has to be reported rather than assumed away.
    """
    version = get_pypi_version()  # Assuming this is defined elsewhere in your code
    packageversion = "maptasker" + version

    # 1. Check if 'uv' is installed and available on the system
    if shutil.which("uv"):
        # Build the command for uv
        # uv uses the syntax: uv pip install <package>
        # --python: uv installs into the environment it discovers (VIRTUAL_ENV, or a .venv in
        # the current directory), and neither is necessarily ours -- MapTasker started from
        # its own 'maptasker' command runs without VIRTUAL_ENV set.  Naming our interpreter
        # upgrades the copy we are actually running, rather than failing for want of an
        # environment or quietly upgrading somebody else's.
        command = ["uv", "pip", "install", "--python", sys.executable, packageversion, "--upgrade"]
        console.say("Updating with uv...")
    else:
        # Build the fallback command for pip
        command = [sys.executable, "-m", "pip", "install", packageversion, "--upgrade"]
        console.say("Updating with pip...")

    # 2. Execute the chosen command, keeping what it said in case it fails.  errors="replace"
    # because an installer's progress output is not necessarily in the console's encoding,
    # and a failed upgrade must not turn into a crash while reading the complaint about it.
    moved = move_locked_scripts_aside()
    try:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace", check=False)  # noqa: S603
    except OSError as e:
        restore_locked_scripts(moved)
        return False, str(e)

    if result.returncode == 0:
        return True, ""

    restore_locked_scripts(moved)
    complaint = (result.stderr or "").strip() or (result.stdout or "").strip()
    return False, complaint or f"the installer stopped with return code {result.returncode}"


# How long the version check waits on PyPI: the same as the timezone lookup above, since both
# are conveniences MapTasker works without.
PYPI_TIMEOUT_SECONDS = 5


# Get the version of our code out on Pypi
def get_pypi_version() -> str:
    """Get the PyPi version of this package."""
    url = "https://pypi.org/pypi/maptasker/json"
    try:
        # Bounded, so an unreachable PyPI cannot hold up whoever asked for long.  The daily
        # check asks from a worker thread (guiutils.check_new_version).
        version = "==" + requests.get(url, timeout=PYPI_TIMEOUT_SECONDS).json()["info"]["version"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        # The connection failing or timing out; a reply that is not JSON; JSON that is not
        # PyPI's shape.
        logger.debug("Unable to get version from PYPI!")
        version = ""
    return version


# If we have set the single Project name due to a single Task or Profile name, then reset it.
def reset_named_objects() -> None:
    """_summary_
    Reset the single Project name if it was set due to a single Task or Profile name.
    Parameters:
        None
    Returns:
        None
    """
    # Check in name hierarchy: Task then Profile.  Whichever was asked for is kept, and every
    # other selection -- the Project it set among them -- is cleared.
    for kept in ("single_task_name", "single_profile_name"):
        if PrimeItems.program_arguments[kept]:
            clear_single_items(keep=kept)
            return


# Count the number of consecutive occurrences of a substring within a main string.
def count_consecutive_substr(main_str: str, substr: str) -> int:
    """
    Count the maximum consecutive occurrences of 'substr' inside 'main_str'.
    Highly optimized: performs a single linear scan with no repeated .find() calls.
    """
    if not main_str or not substr:
        return 0

    sub_len = len(substr)
    max_count = 0
    count = 0

    i = 0
    end = len(main_str)

    while i <= end - sub_len:
        # Direct substring match without slicing
        if main_str.startswith(substr, i):
            count += 1
            i += sub_len
        else:
            max_count = max(max_count, count)
            count = 0
            i += 1

    return max(max_count, count)


def pretty(d: dict, indent: int = 0) -> None:
    """
    Print out a dictionary in a human-readable format.

    Args:
        d: The dictionary to print.
        indent: The number of tabs to indent the output with.
    """
    _pretty = pretty
    for key, value in d.items():
        console.debug("\t" * indent + str(key))
        if isinstance(value, dict):
            _pretty(value, indent + 1)
        else:
            console.debug("\t" * (indent + 1) + str(value))


def find_all_positions(string: str, substring: str, start_position: int = 0) -> list:
    """
    Finds all positions of a substring in a string.

    Args:
        string (str): The string to search in.
        substring (str): The substring to search for.
        start_position (int, optional): The position to start the search from. Defaults to 0.

    Returns:
        list: A list of all positions of the substring in the string.
    """

    positions = []
    start = start_position
    while True:
        pos = string.find(substring, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1  # Continue search from the next character
    return positions


def display_task_warnings() -> None:
    """
    Output any warnings for tasks with too many actions.

    This function goes through the list of tasks with too many actions
    and adds them to the output list.  It then outputs all the warnings.
    """
    task_translated = translate_string("Task")
    has_translated = translate_string("has")
    actions_translated = translate_string("actions")
    warnings = [
        format_html(
            "trailing_comments_color",
            "",
            f"\n{translate_string('Tasks With Too Many Actions (Limit is')} {PrimeItems.program_arguments['task_action_warning_limit']})...",
            False,
        ),
    ]
    # Go through the warnings and add to our output list.
    for task_name, value in PrimeItems.task_action_warnings.items():
        # Build the hotlink to the Task, aimed at the anchor mapjump gives every Task by
        # its id rather than at the directory's anchor for its name.
        #
        # With the directory on, an unnamed Task is deliberately left out of it (dirout.
        # add_directory_item), and the name-keyed anchor goes with it -- so every warning
        # about an unnamed Task pointed at an anchor that was never written, and clicking
        # it did nothing.  On this repo's reference backup that was 19 of the 84 warnings.
        #
        # The id-keyed anchor is emitted for every Task whatever the settings (see
        # mapjump.anchor_html), and it identifies the Task rather than its name, so it
        # also reaches the right one of two Tasks that share a name.
        target = Target(TASK, value["id"], task_name)
        # Build the hyperelink reference.  The explicit color/underline is needed because this
        # link sits inside a "trailing_comments_color" span -- see sysconst.HOTLINK_STYLE for
        # why an unstyled <a> disappears into its surroundings in the Map view.
        href = f'<a href=#{target.anchor} style="{HOTLINK_STYLE}">{task_name}</a>'

        # Add the warning to the list.
        warnings.append(f"{task_translated} {href} {has_translated} {value['count']} {actions_translated}")

    # Start the output
    PrimeItems.output_lines.add_line_to_output(0, "<hr>", FormatLine.dont_format_line)

    # Output all Task warning lines
    for warning in warnings:
        # Add the line to the output.
        PrimeItems.output_lines.add_line_to_output(
            0,
            warning,
            ["", "trailing_comments_color", FormatLine.add_end_span],
        )


def fix_hyperlink_name(name: str) -> str:
    """
    Fix the hyperlink name so it doesn't screw up the html output.

    A name is the user's own text, and it goes into an attribute -- the id of an anchor,
    and the hyperlink that looks for it.  Every character that can end that attribute
    early has to go, or the tag stops where the name does and the rest of it is drawn in
    the Map as text, with everything below it laid out as though the tag were still open:

        <   >   a Task called "System >> Say Response", or an unnamed one named after an
                action, such as "If %new_val > %limit"
        "       an unnamed Task named after an Anchor action: 'Anchor "NOTE: ..."'

    The same name is escaped for both sides of the link, so the two go on matching -- a
    browser reads "&gt;" and "&quot;" in an attribute as the characters they stand for.

    Args:
        name (str): The name to fix.

    Returns:
        str: The fixed name.
    """
    return (
        name.replace(" ", "_").replace(">", "&gt;").replace("<", "&lt;").replace('"', "&quot;")
    )


def get_value_if_match(
    data: dict,
    match_key: str,
    match_value: str,
    return_key: str,
) -> str | None:
    """
    Retrieve a specific value from a dictionary if another value matches a given string.

    Parameters:
    - data (dict): The dictionary to search.
    - match_key (str): The key to check for the match.
    - match_value (str): The value to match against.
    - return_key (str): The key whose value to return if a match is found.

    Returns:
    - The value associated with return_key if a match is found, else None.
    """
    for key, item in data.items():
        if item[match_key] == match_value:
            return item[return_key], key
    return None, None


# Clear all Tasker XML data from memory so we start anew.
def clear_tasker_data() -> None:
    """
    Empty every table of the loaded backup's Projects, Profiles, Tasks, Scenes and Services.

    Each table in PrimeItems.tasker_root_elements is emptied where it stands, whatever tables
    there are.  This used to name them one at a time, and named five of the seven: the
    Profiles by name and the Services went on holding the previous backup's objects.
    """
    for table in PrimeItems.tasker_root_elements.values():
        table.clear()


def count_unique_substring(string_list: list, substring: str) -> int:
    """
    Counts the number of strings in a list that contain a given substring,
    assuming each string has at most one instance of the substring.

    Args:
      string_list: A list of strings to search within.
      substring: The substring to count.

    Returns:
      An integer representing the number of strings containing the substring.
    """
    count = 0
    for text in string_list:
        if substring in text:
            count += 1
    return count


# Find the owning Profile given a Task name
def find_owning_profile(task_name: str) -> str:
    """
    Find the owning Profile given a Task name.

    This function takes a Task name as input and searches for the corresponding Task ID in the `PrimeItems.tasker_root_elements["all_tasks"]` dictionary. It then iterates over the `PrimeItems.tasker_root_elements["all_profiles"]` dictionary to find the Profile that contains the Task ID. If a matching Profile is found, its name is returned. If no matching Profile is found, an empty string is returned.

    Parameters:
        task_name (str): The name of the Task.

    Returns:
        str: The name of the owning Profile, or an empty string if no matching Profile is found.
    """
    tid = next(
        (k for k, v in PrimeItems.tasker_root_elements["all_tasks"].items() if v["name"] == task_name),
        "",
    )

    # Find the owning Profile
    if tid:
        for profile_value in PrimeItems.tasker_root_elements["all_profiles"].values():
            for mid_key in ["mid0", "mid1"]:
                mid = profile_value["xml"].find(mid_key)
                if mid is not None and mid.text == tid:
                    return profile_value["name"]

    return ""


# Find owning Project given a Task name
def find_owning_project_for_task(task_name: str) -> str:
    """
    Find the owning Project given a Task name.

    A Task belongs to a Project in one of two ways, and both have to be tried: it is
    listed directly in the Project's <tids> (what the GUI's Add Task does -- see
    profedit.add_task_to_project), or it is reached through the Profile that runs it as
    an Entry/Exit Task, in which case the Project owns the *Profile*.  The direct listing
    goes first because it is the definitive one; the Profile route is the fallback.

    Args:
        task_name (str): The Task name.

    Returns:
        str: The owning Project name, or an empty string if not found.
    """
    task_id = next(
        (k for k, v in PrimeItems.tasker_root_elements["all_tasks"].items() if v["name"] == task_name),
        "",
    )
    if task_id:
        for project_name, project_value in PrimeItems.tasker_root_elements["all_projects"].items():
            if task_id in get_ids(False, project_value["xml"], project_name, []):
                return project_name

    # Not attached to a Project directly -- go by whichever Profile runs it.
    profile_name = find_owning_profile(task_name)
    return find_owning_project(profile_name) if profile_name else ""


# Find owning Project given a Profile name
def find_owning_project(profile_name: str) -> str:
    """
    Find the owning Project given a Profile name.

    Args:
        self: The instance of the class.
        profile_name (str): The Profile name.

    Returns:
        str: The owning Project name, or an empty string if not found.
    """
    profile_dict = PrimeItems.tasker_root_elements["all_profiles"]
    profile_id = {v["name"]: k for k, v in profile_dict.items()}.get(profile_name)

    if profile_id:
        _get_ids = get_ids
        for project_name, project_value in PrimeItems.tasker_root_elements["all_projects"].items():
            if profile_id in _get_ids(True, project_value["xml"], project_name, []):
                return project_name
    return ""


# Find owning Project given a Scene name
def find_owning_project_for_scene(scene_name: str) -> str:
    """
    Find the owning Project given a Scene name.

    Scenes are not in a Project's <pids>/<tids> the way Profiles and Tasks are, so this
    can't go through get_ids like find_owning_project/find_owning_profile do.  Instead a
    Project lists its Scenes by *name* in its <scenes> element, as a comma-separated
    list (see scenes.process_project_scenes).

    Args:
        scene_name (str): The Scene name.

    Returns:
        str: The owning Project name, or an empty string if no Project lists this Scene.
    """
    for project_name, project_value in PrimeItems.tasker_root_elements["all_projects"].items():
        scenes = project_value["xml"].find("scenes")
        # Split on the comma rather than testing "in scenes.text": a plain substring test
        # matches Scene "Main" against a Project that only owns "MainMenu".
        if scenes is not None and scenes.text and scene_name in scenes.text.split(","):
            return project_name
    return ""


def append_to_filename(original_filename_with_type: str, text_to_append: str) -> str:
    """
    Appends a text string to the filename part of a given filename, preserving the file type.

    Args:
        original_filename_with_type (str): The original filename including its extension (e.g., "document.pdf").
        text_to_append (str): The text string to append to the filename (e.g., "_new").

    Returns:
        str: The new filename with the text appended, or None if the input is invalid.
    """
    if not isinstance(original_filename_with_type, str) or not isinstance(
        text_to_append,
        str,
    ):
        logger.error(
            "Error: Both original_filename_with_type and text_to_append must be strings.",
        )
        return None

    # Use os.path.splitext to separate the filename and its extension
    filename_without_extension, file_extension = os.path.splitext(
        original_filename_with_type,
    )

    # Append the text to the filename
    new_filename_without_extension = filename_without_extension + text_to_append

    # Combine the new filename with the original extension
    return new_filename_without_extension + file_extension


def get_timezone_from_ip() -> str:
    """
    Attempts to determine the current timezone using IP geolocation via ipinfo.io.
    Requires an internet connection.

    Returns:
        str: The IANA timezone name (e.g., 'America/Mexico_City'), or None if not found.
    """
    try:
        # Send a request to ipinfo.io to get IP details (including timezone)
        # This will query your public IP
        response = requests.get("https://ipinfo.io/json", timeout=5)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        timezone_name = data.get("timezone")
        if timezone_name:
            logger.info(f"Discovered timezone via IP: {timezone_name}")
            return timezone_name
        logger.debug("Timezone information not found in IP geolocation data.")
        return None  # noqa: TRY300
    except requests.exceptions.RequestException as e:
        logger.debug(f"Error connecting to geolocation service or getting data: {e}")
        return None
    except (ValueError, AttributeError) as e:
        # The request itself is covered above.  This is the response being something other
        # than the JSON object this expects: .json() raises ValueError, and .get() on a
        # decoded list rather than a dict raises AttributeError.
        logger.debug(f"An unexpected error occurred during IP geolocation: {e}")
        return None


def get_current_local_time_auto_timezone() -> datetime:
    """
    Attempts to get the current local time by first discovering the timezone
    via IP geolocation. Works with Python 3.9+.
    """
    timezone_string = get_timezone_from_ip()

    if timezone_string:
        try:
            local_tz = ZoneInfo(timezone_string)
            now_aware = datetime.now(local_tz)
            logger.info(f"\nAutomatically determined current local time: {now_aware}")
            logger.info(f"Timezone info: {now_aware.tzinfo}")
            logger.info(f"Offset from UTC: {now_aware.utcoffset()}")
            return now_aware  # noqa: TRY300
        except ZoneInfoNotFoundError:
            logger.debug(
                f"Error: Discovered timezone '{timezone_string}' is not recognized by zoneinfo.",
            )
            return clock.now()
        except ValueError as e:
            # ZoneInfo rejects a key that is not a well-formed name with ValueError, and
            # raises ZoneInfoNotFoundError (caught above) for one that simply is not there.
            logger.debug(f"Error creating timezone-aware datetime: {e}")
            return clock.now()
    else:
        logger.debug(
            "\nCould not determine timezone automatically. Falling back to the system's local time.",
        )
        now_local = clock.now()
        logger.debug(f"Current local datetime: {now_local}")
        return now_local


def rename_file(old_file_path: str, new_file_path: str) -> bool:
    """
    Renames a file from an old path to a new path.

    Args:
        old_file_path (str): The current path/name of the file.
        new_file_path (str): The desired new path/name for the file.

    Returns:
        bool: True if the file was successfully renamed, False otherwise.
    """
    if not isinstance(old_file_path, str) or not isinstance(new_file_path, str):
        rutroh_error("Error: Both old_file_path and new_file_path must be strings.")
        return False

    try:
        # Check if the old file exists before attempting to rename
        if not os.path.exists(old_file_path):
            rutroh_error(f"Error: The file '{old_file_path}' does not exist.")
            return False

        os.rename(old_file_path, new_file_path)
        rutroh_error(f"File '{old_file_path}' successfully renamed to '{new_file_path}'.")

        return True  # noqa: TRY300
    except OSError as e:
        rutroh_error(f"Error renaming file: {e}")
        return False


def restart_program_subprocess() -> None:
    """
    Restarts the current program by spawning a new process and exiting the old one.
    This is often more reliable on Windows.
    NOTE: This is a duplicate of 'rurun_process' in mapit.py, to avoid circular import error.
    """
    # Get the absolute path of the current script file
    # This is more robust than relying directly on sys.argv[0]
    script_path = os.path.abspath(__file__)
    script_path = script_path.replace(f"src{PrimeItems.slash}maputils.py", "main.py")

    # Prepare the arguments for the new process
    # The first argument is the Python interpreter
    # The second is the absolute path to the script
    # The rest are any original command-line arguments (excluding the script name itself)
    new_process_args = [sys.executable, script_path, *sys.argv[1:]]

    subprocess.Popen(new_process_args)  # noqa: S603
    console.say("Restarting program.  Please stand by...")
    time.sleep(0.2)

    # If we're inside a running event loop (e.g. this was triggered from a NiceGUI
    # button click), sys.exit() only raises SystemExit inside that task, which crashes
    # the loop/uvicorn server with a messy traceback instead of cleanly ending the process.
    # NiceGUI's core.stop_and_exit() is built for exactly this: it runs shutdown
    # handlers/atexit callbacks and then hard-exits via os._exit().
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        sys.exit(0)  # Not in an event loop: plain, clean exit.
    else:
        from nicegui.core import stop_and_exit  # noqa: PLC0415

        # stop_and_exit() blocks on asyncio.run_coroutine_threadsafe(...).result(),
        # which needs the event loop's own thread free to run the scheduled coroutine.
        # Calling it directly from here (already on the loop's thread, inside this
        # button-click handler) deadlocks that wait for a full 30s, during which the
        # old process still holds the port that the freshly-spawned new process is
        # trying to bind to. NiceGUI itself always calls stop_and_exit() from a
        # separate thread (see nicegui/server.py) for this exact reason.
        threading.Thread(target=stop_and_exit, daemon=True).start()


def make_hex_color(color_string: str) -> str:
    """
    Validates a string input to determine if it's a color name or a hex code.

    - If it's a valid 6-digit hex code (with or without a leading '#'), it returns
      the 6 digits prefixed with a '#'.
    - If it's a valid 3-digit hex code, it returns the 3 digits without the '#'.
    - Otherwise, the original string is returned, assuming it's a color name.

    Args:
        color_string: The string representing the color (e.g., 'green', '00ff20', '#33aaff').

    Returns:
        The validated color string (e.g., '#00ff20', 'f00', 'green').
    """
    # Remove leading/trailing whitespace and convert to lowercase for consistent checking
    color_input = color_string.strip().lower()

    # Define the regular expression pattern for a hex color code
    # This pattern matches: #?([0-9a-f]{3}|[0-9a-f]{6})
    hex_pattern = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$")

    match = hex_pattern.match(color_input)

    if match:
        # The captured hex value (3 or 6 chars) is in group(1)
        hex_value = match.group(1)

        # --- MODIFICATION START ---
        if len(hex_value) == 6:
            # If it's a 6-digit code, return it with the '#' prefix
            return f"#{hex_value}"
        # This handles the 3-digit hex codes
        # If it's a 3-digit code, return it without the '#' prefix
        return hex_value
        # --- MODIFICATION END ---
    # If it's not a hex code, we assume it's a color name and return the original string.
    return color_string.strip()


# def live_translate_text(text: str) -> str:
#     """
#     Translates text using live translation if enabled.
#     Args:
#         text: The text to be translated.
#     Returns:
#         translated text if live translation is enabled, otherwise the original text.
#     """
#     target = PrimeItems.program_arguments["language"]
#     if target == "English":
#         return text
#     if target == "Traditional Chinese":
#         target_lang = "chinese (traditional)"
#     elif target == "Simplified Chinese":
#         target_lang = "chinese (simplified)"
#     else:
#         target_lang = PrimeItems.languages[target]

#     return GoogleTranslator(source="auto", target=target_lang).translate(text)
