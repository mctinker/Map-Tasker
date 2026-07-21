#! /usr/bin/env python3
"""
 maputil2: General utilities (NiceGUI Version).

These are functions pulled out of maputils, guiwins and guiutils that would otherwise cause a circular
import error.
"""

import copy
import os
import re
import sys
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

import requests
from requests.exceptions import ConnectionError, InvalidSchema, Timeout

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import MY_VERSION, NOW_TIME, logger, logging
from maptasker.src.translator import T

# Removed tkinter and customtkinter imports!


# ==========================================
# 1. TEXT & DATA PARSING
# ==========================================


def strip_html_tags(text: str) -> str:
    """Removes all HTML tags from a given string.

    Args:
      text: The input string containing HTML tags.

    Returns:
      A string with all HTML tags removed.
    """
    return re.sub(r"<[^>]+>", "", text)


def truncate_string(text: str, max_length: int = 30) -> str:
    """Truncates a string to a specified maximum length.

    Args:
      text: The input string.
      max_length: The maximum number of characters to keep (default is 30).

    Returns:
      The truncated string. If the original string is shorter than or equal to
      max_length, it is returned unchanged. If it's longer, it's truncated and
      an ellipsis (...) is added to the end.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# ==========================================
# 2. LEGACY DESKTOP STUBS
# ==========================================


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


# ==========================================
# 3. ENVIRONMENT & PACKAGE MANAGEMENT
# ==========================================
# Issue HTTP Request to get something from the Android device.
def http_request(
    ip_address: str,
    ip_port: str,
    file_location: str,
    request_name: str,
    request_parm: str,
    auth_key: str = "",
) -> tuple[int, object]:
    """
    Issue HTTP Request to get the backup XML file from the Android device.
    Tasker's HTTP Server Example must be installed for this to work:
    https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn&id=Project%3AHttp+Server+Example
        :param backup_file_http: the port to use for the Android device's Tasker server
        :param backup_file_location: location of
        :param auth_key: API key from get_android_auth_key(), sent as the raw
        'Authorization' header value (no "Bearer " prefix) -- required by the
        newer 'api/*' endpoints (e.g. api/tasks), unused by the plain 'file' one
        :return: return code, response: eitherr text string with error message or the
        contents of the backup file
    """
    # Create the URL to request the backup xml file from the Android device running the
    # Tasker server.
    # Something like: 192.168.0.210:1821/file/path/to/backup.xml?download=1
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/{request_name}{file_location}{request_parm}"
    headers = {"Authorization": auth_key} if auth_key else None

    # Make the request.
    error_message = ""
    response = ""

    with suppress_stdout():  # Suppress any errors (system IMK)
        try:
            response = requests.get(url, headers=headers, timeout=5)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to get XML from Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error.  Or perhaps the profile 'MapTasker List' has not been imported into Tasker on the Android device!"
        except Exception as e:  # noqa: BLE001
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


# Get an API key from the Tasker HTTP API (GET /api/auth), needed to authenticate
# every other request against it -- see http_post_request's auth_key param.
def get_android_auth_key(ip_address: str, ip_port: str) -> tuple[int, str]:
    """
    GET /api/auth from the Tasker HTTP API to obtain the API key used to
    authenticate subsequent requests. Tasker responds with a JSON auth object:
    {"key": "...", "authorized": true|false}. The key is sent back as a raw
    'Authorization' header value (no "Bearer " prefix) on later requests.
        :param ip_address: IP address of the Android device
        :param ip_port: port the Tasker HTTP API is listening on
        :return: return code (0 on success), and either the API key or an error message
    """
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/api/auth"
    print("bingo getting auth key url:", url)

    error_message = ""
    response = ""

    with suppress_stdout():
        try:
            response = requests.get(url, timeout=5)
            print("bingo response:", response, "content:", response.content)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to reach Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error."
        except Exception as e:  # noqa: BLE001
            error_message = f"Request failed for url: {url}, error: {e} ."

    if error_message:
        logger.debug(error_message)
        print("bingo error", error_message)
        return 8, error_message

    if not response or response.status_code != 200:
        status = response.status_code if response else "no response"
        return 8, f"Request failed for url: {url} ...with status code {status}"

    try:
        auth_object = response.json()
    except ValueError:
        return 8, f"Auth response from {url} was not valid JSON: {response.content!r}"

    if not auth_object.get("authorized"):
        return 8, "Android device did not authorize this connection."

    key = auth_object.get("key", "")
    if not key:
        return 8, "Auth response did not include an API key."
    print("bingo auth key=", key)
    return 0, key


# Issue HTTP Request to post/save something to the Android device.
def http_post_request(
    ip_address: str,
    ip_port: str,
    file_location: str,
    request_name: str,
    request_parm: str,
    file_content: bytes,
    auth_key: str = "",
) -> tuple[int, object]:
    """
    Issue HTTP POST request to write a file (e.g. a standalone Task .tsk.xml) to the
    Android device, via the Tasker HTTP API.
        :param ip_address: IP address of the Android device
        :param ip_port: port the Android device's Tasker HTTP API is listening on
        :param file_location: path (directory + filename) to write on the Android device
        :param request_name: the Tasker HTTP API endpoint to target (e.g. "api/import")
        :param request_parm: any additional query string to append to the URL
        :param file_content: raw bytes of the file to post as the request body
        :param auth_key: API key from get_android_auth_key(), sent as the raw
        'Authorization' header value (no "Bearer " prefix)
        :return: return code, response: either a text string with an error message or
        the contents of the response
    """
    # Build the URL the same way http_request() does.
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/{request_name}{file_location}{request_parm}"
    print("bingo url:", url)
    headers = {"Authorization": auth_key} if auth_key else None

    # Make the request.
    error_message = ""
    response = ""

    with suppress_stdout():  # Suppress any errors (system IMK)
        try:
            response = requests.post(url, data=file_content, headers=headers, timeout=10)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to post XML to Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error.  Or perhaps the profile 'MapTasker List' has not been imported into Tasker on the Android device!"
        except Exception as e:  # noqa: BLE001
            error_message = f"Request failed for url: {url}, error: {e} ."

    # If we have an error message, return as error.
    if error_message:
        logger.debug(error_message)
        return 8, error_message

    # Check the response status code.  200 is good!
    if response and response.status_code == 200:
        print("bingo good return code")
        return 0, response.content

    if response and response.status_code == 401:
        # Distinct code (not the generic 8) so callers holding a cached auth_key
        # can tell "key was rejected" apart from other failures and retry with a
        # freshly-fetched key (see taskedit.save_task_to_android).
        return 9, "Android device rejected the API key (401 Unauthorized)."

    if response and response.status_code == 404:
        return 6, "Directory " + file_location + " not found."

    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )


# Log the arguments
def log_startup_values() -> None:
    """
    Log the runtime arguments and color mappings
    """
    setup_logging()  # Get logging going
    logger.info(f"{MY_VERSION} {str(NOW_TIME)}")  # noqa: RUF010
    logger.info(f"sys.argv:{str(sys.argv)}")  # noqa: RUF010
    for key, value in PrimeItems.program_arguments.items():
        logger.info(f"{key}: {value}")
    for key, value in PrimeItems.colors_to_use.items():
        logger.info(f"colormap for {key} set to {value}")


# Set up logging
def setup_logging() -> None:
    """
    Set up the logging: name the file and establish the log type and format
    """
    # Add the date and time to the log filename.
    file_name = f"maptasker_{NOW_TIME.month}-{NOW_TIME.day}-{NOW_TIME.year}_{NOW_TIME.hour}-{NOW_TIME.minute}-{NOW_TIME.second}.log"
    logging.basicConfig(
        filename=file_name,
        filemode="w",
        format="%(asctime)s,%(msecs)d %(levelname)s %(name)s %(funcName)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )
    logger.info(sys.version_info)


def translate_string(text: str, set_language: bool = False) -> str:
    """
    Translates a given string using PrimeItems._ if available. and sets the language if requested.

    Args:
        text: The input string to be translated.
    Returns:
        The translated string if PrimeItems._ is available, otherwise the original string.
    """
    # If we have a language set, then translate the test
    if text:
        if hasattr(PrimeItems, "_"):
            # If we are to set the language, then first translate it and then set it.
            if set_language:
                lang_to_set = PrimeItems._(text) if text not in PrimeItems.languages else text
                T.set_language(lang_to_set)
            return PrimeItems._(text)

        # If this is a language, then set the language and translate the text.
        if text in PrimeItems.languages and set_language:
            T.set_language(text)
            return PrimeItems._(text)
    return text


# ==========================================
# 4. FULL BACKUP WRITE-BACK
# ==========================================
_XML_DECLARATION = '<?xml version = "1.0" encoding = "UTF-8" standalone = "no" ?>\n'


def write_full_backup_to_current_file() -> tuple[bool, str]:
    """Writes the entire current Tasker backup -- every Project, Profile, Task,
    Scene, everything -- out to a brand-new, timestamped copy of whatever file
    it was loaded from (PrimeItems.file_to_get), e.g. backup.xml ->
    backup_20260721_143005.xml, with the current in-memory state -- including
    any Task/Profile edits made through Edit/Add Task/Profile -- applied to
    that copy. Backs the "Save To Current File" button in those dialogs (see
    userintr.py's save_*_to_current_file_event handlers, which then switch the
    app over to the new copy -- see userintr._reload_saved_copy_and_refresh --
    so it becomes "the current file" for any further editing/saving), as
    opposed to their "Save"/"Save Single Task/Profile" button, which exports
    just the one Task/Profile as a standalone file instead.

    The original file is deliberately never opened for writing -- only read,
    via the deep copy below -- so it's left exactly as it was; every "Save To
    Current File" click produces a new, independent snapshot alongside it
    rather than mutating it in place.

    A Project edit (e.g. profedit.add_profile_to_project's <pids> update)
    already lands directly on the live tree -- taskerd.move_xml_to_table never
    deep-copies, so all_projects[name]["xml"] IS the tree's own element, same
    object. Profile and Task edits don't: taskedit.py/profedit.py's own module
    docstrings describe deliberately never touching PrimeItems.xml_tree,
    always working on a deep copy that only gets reconciled into the
    all_profiles/all_tasks lookup tables afterward (see
    apply_edited_profile_to_live_tree/register_new_profile/
    apply_edited_task_to_live_tree/register_new_task) -- so naively
    re-serializing PrimeItems.xml_root as-is would silently omit every
    Task/Profile edit. This reconciles the two: starting from a deep copy of
    the original tree (preserving Scenes, Settings, and anything else this
    app doesn't track in a table of its own), it splices in each
    all_profiles/all_tasks entry's *current* element in place of whatever the
    tree's own same-id child holds (or appends it, for one added via Add
    Task/Add Profile that never existed in the original file at all).

    Returns (True, new_file_path) on success, or (False, error_message) if
    there's no current file to copy from, or the write itself fails.
    """
    file_to_get = PrimeItems.file_to_get
    # PrimeItems.file_to_get is sometimes an open file object (.name is its path) and
    # sometimes just the path itself as a plain string (e.g. getxml_event's own direct
    # assignment, or the self-healing load in userintr.open_add_task_dialog_event/
    # MyGui.__init__) -- getattr(..., "name", file_to_get) handles both, matching the
    # same pattern already used for this ambiguity elsewhere (see userintr.py's
    # check_name error path).
    file_path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    if not file_path or not isinstance(file_path, str):
        return False, "No backup file is currently loaded to save back to."

    if PrimeItems.xml_root is None:
        return False, "No backup data is currently loaded."

    root_copy = copy.deepcopy(PrimeItems.xml_root)

    for tag, table_name in (("Profile", "all_profiles"), ("Task", "all_tasks")):
        existing_by_id = {}
        last_index_of_tag = -1
        for index, child in enumerate(root_copy):
            if child.tag != tag:
                continue
            last_index_of_tag = index
            id_element = child.find("id")
            if id_element is not None and id_element.text:
                existing_by_id[id_element.text] = child

        for item_id, entry in PrimeItems.tasker_root_elements.get(table_name, {}).items():
            current_element = copy.deepcopy(entry["xml"])
            old_element = existing_by_id.get(item_id)
            if old_element is not None:
                index = list(root_copy).index(old_element)
                root_copy.remove(old_element)
                root_copy.insert(index, current_element)
            else:
                # Brand-new Profile/Task (e.g. from Add Profile/Add Task): insert it
                # next to its own kind rather than at the very end of the file, so the
                # top-level <Setting>/<Profile>/<Project>/<Scene>/<Task>/<Variable>
                # grouping that real Tasker backups always use stays intact.
                insert_at = last_index_of_tag + 1 if last_index_of_tag >= 0 else len(root_copy)
                root_copy.insert(insert_at, current_element)
                last_index_of_tag = insert_at

    ETW.indent(root_copy, space="\t")
    xml_text = _XML_DECLARATION + ETW.tostring(root_copy, encoding="unicode") + "\n"

    base_path, extension = os.path.splitext(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
    new_file_path = f"{base_path}_{timestamp}{extension}"

    try:
        with open(new_file_path, "w", encoding="utf-8") as out_file:
            out_file.write(xml_text)
    except OSError as e:
        return False, str(e)

    return True, new_file_path
