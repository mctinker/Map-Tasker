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
import time
import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to build/serialize
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

import requests
from requests.exceptions import ConnectionError, InvalidSchema, Timeout

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import MY_VERSION, NOW_TIME, logger, logging
from maptasker.src.translator import T

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
    response = None

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

    # Test "response is not None", never "if response": requests.Response.__bool__ returns
    # .ok, so a Response carrying any status >= 400 is falsy.  Truth-testing it would make
    # the 404 branch below unreachable and would send every error status to the generic
    # message at the bottom.
    if response is None:
        return 8, f"Request failed for url: {url} ...no response from the Android device."

    # Check the response status code.  200 is good!
    if response.status_code == 200:
        # Return the contents of the file.
        return 0, response.content

    if response.status_code == 404:
        return 6, "File " + file_location + " not found."

    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )


def file_exists_on_android(ip_address: str, ip_port: str, device_path: str) -> bool | None:
    """Whether a file already sits at device_path on the Android device.

    Answers the question http_upload_request cannot: /upload silently overwrites
    whatever is already at its destination and reports 200 either way (see its
    docstring), so the only way to know a save would clobber something is to read
    the path back first. Uses the same plain 'file' GET the post-upload verify
    does, which needs no auth key.

    Deliberately tri-state rather than a plain bool -- the three outcomes are
    genuinely different and the caller must not conflate them:
        True  -- 200, a file is there and would be overwritten
        False -- 404, nothing there, safe to write
        None  -- any other failure (device unreachable, timeout, server error);
                 existence is *unknown*, so callers should not claim the path is
                 free. Returning False here would silently skip the overwrite
                 prompt on exactly the flaky-connection case where a user most
                 wants it; the caller decides whether to proceed or warn.
    """
    return_code, _ = http_request(ip_address, ip_port, device_path, "file", "")
    if return_code == 0:
        return True
    if return_code == 6:  # 404 -- not found
        return False
    return None


# Tasker's /api/auth does not answer deterministically: on a device that is set up
# correctly and reachable, it still returns 403 {"authorized": false} for roughly half
# of all requests, then authorizes the very next identical request.  Measured against a
# real device, a single retry was always enough, so 3 attempts leaves margin without
# making a genuinely-unreachable device wait long.  Without this, every save-to-Android
# was a coin flip that failed before the import was ever attempted -- which is why the
# import-level fallbacks (taskedit.save_task_to_android_directory and friends) could
# never help: there was no request to retry, only a key that was never obtained.
AUTH_KEY_MAX_ATTEMPTS = 3
AUTH_KEY_RETRY_SECONDS = 0.5


def _request_android_auth_key(url: str) -> tuple[int, str, bool]:
    """Make a single GET /api/auth attempt.

    Returns (return_code, key_or_error_message, retryable), where 'retryable' marks the
    failures that a further identical attempt could plausibly resolve -- see the
    AUTH_KEY_MAX_ATTEMPTS comment above.  A malformed URL or a well-formed response that
    simply has no key in it will never change, so those are reported immediately.
    """
    error_message = ""
    retryable = True
    response = None

    with suppress_stdout():
        try:
            response = requests.get(url, timeout=8)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
            retryable = False  # a bad URL is a bad URL, no matter how often we ask
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to reach Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error."
        except Exception as e:  # noqa: BLE001
            error_message = f"Request failed for url: {url}, error: {e} ."

    if error_message:
        logger.debug(error_message)
        return 8, error_message, retryable

    # "response is not None", never "if response" -- see the note in http_request(): a
    # Response with any status >= 400 is falsy, so truth-testing it reported every real
    # HTTP error as the useless "status code no response".
    if response is None:
        return 8, f"Request failed for url: {url} ...no response from the Android device.", True

    # Parse the body before checking the status.  Tasker answers an unauthorized device
    # with 403 *and* a perfectly clear {"authorized": false} payload, so reading the body
    # first lets us report why the connection was refused instead of a bare status code.
    try:
        auth_object = response.json()
    except ValueError:
        auth_object = None

    # "is False", not "not ...": only an explicit {"authorized": false} means the device
    # refused us.  A body that merely lacks the field (e.g. the "{}" of a 500) must fall
    # through to the status check below rather than be misreported as a refusal.
    if auth_object is not None and auth_object.get("authorized") is False:
        return (
            8,
            (
                "Android device did not authorize this connection.  Approve MapTasker's "
                "connection request on the device, and confirm Tasker's HTTP server allows external access."
            ),
            True,  # the intermittent case this whole retry loop exists for
        )

    if response.status_code != 200:
        return 8, f"Request failed for url: {url} ...with status code {response.status_code}", True

    if auth_object is None:
        return 8, f"Auth response from {url} was not valid JSON: {response.content!r}", False

    key = auth_object.get("key", "")
    if not key:
        return 8, "Auth response did not include an API key.", False
    return 0, key, False


# Get an API key from the Tasker HTTP API (GET /api/auth), needed to authenticate
# every other request against it -- see http_post_request's auth_key param.
def get_android_auth_key(ip_address: str, ip_port: str) -> tuple[int, str]:
    """
    GET /api/auth from the Tasker HTTP API to obtain the API key used to
    authenticate subsequent requests. Tasker responds with a JSON auth object:
    {"key": "...", "authorized": true|false}. The key is sent back as a raw
    'Authorization' header value (no "Bearer " prefix) on later requests.

    Retries up to AUTH_KEY_MAX_ATTEMPTS times, because Tasker refuses authorization
    intermittently even when everything is configured correctly -- see that constant's
    comment.  The last failure's message is what the caller gets.
        :param ip_address: IP address of the Android device
        :param ip_port: port the Tasker HTTP API is listening on
        :return: return code (0 on success), and either the API key or an error message
    """
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/api/auth"

    return_code, result, retryable = 8, "", False
    for attempt in range(1, AUTH_KEY_MAX_ATTEMPTS + 1):
        return_code, result, retryable = _request_android_auth_key(url)
        if return_code == 0:
            if attempt > 1:
                logger.info(f"Android auth key obtained on attempt {attempt} of {AUTH_KEY_MAX_ATTEMPTS}.")
            return return_code, result
        if not retryable:
            break
        if attempt < AUTH_KEY_MAX_ATTEMPTS:
            logger.debug(f"Android auth attempt {attempt} of {AUTH_KEY_MAX_ATTEMPTS} failed: {result}  Retrying.")
            time.sleep(AUTH_KEY_RETRY_SECONDS)

    return return_code, result


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
    headers = {"Authorization": auth_key} if auth_key else None

    # Make the request.
    error_message = ""
    response = None

    with suppress_stdout():  # Suppress any errors (system IMK)
        try:
            response = requests.post(url, data=file_content, headers=headers, timeout=15)
        except InvalidSchema:
            error_message = f"Request failed for url: {url} .  Invalid url!"
        except ConnectionError:
            error_message = f"Request failed for url: {url} .  Connection error! Unable to post XML to Android device."
        except Timeout:
            error_message = f"Request failed for url: {url} .  Timeout error.  Perhaps Tasker server is not active or the Project 'HTTP Server Example' has not been imported into Tasker on the Android device!"
        except Exception as e:  # noqa: BLE001
            error_message = f"Request failed for url: {url}, error: {e} ."

    # If we have an error message, return as error.
    if error_message:
        logger.debug(error_message)
        return 8, error_message

    # Test "response is not None", never "if response": requests.Response.__bool__ returns
    # .ok, so a Response carrying any status >= 400 is falsy.  Truth-testing it made both
    # branches below unreachable -- 401 never produced return code 9, which silently
    # disabled the retry-with-a-fresh-key logic in taskedit.save_task_to_android and
    # profedit.save_profile_to_android that depends on seeing that 9.
    if response is None:
        return 8, f"Request failed for url: {url} ...no response from the Android device."

    # Check the response status code.  200 is good!
    if response.status_code == 200:
        return 0, response.content

    if response.status_code == 401:
        # Distinct code (not the generic 8) so callers holding a cached auth_key
        # can tell "key was rejected" apart from other failures and retry with a
        # freshly-fetched key (see taskedit.save_task_to_android).
        return 9, "Android device rejected the API key (401 Unauthorized)."

    if response.status_code == 404:
        return 6, "Directory " + file_location + " not found."

    return (
        8,
        f"Request failed for url: {url} ...with status code {response.status_code}",
    )


# Issue HTTP Request to write a raw file onto the Android device's storage (NOT into
# Tasker's live configuration -- see profedit.save_profile_to_android/
# projedit.save_project_to_android, the only two callers).
def http_upload_request(
    ip_address: str,
    ip_port: str,
    location: str,
    filename: str,
    file_content: bytes,
) -> tuple[int, str]:
    """
    POST file_content to the Tasker HTTP Server Example's /upload endpoint, writing it
    to <location>/<filename> on the device's storage (e.g. location="Tasker/profiles").
    This is the same endpoint the server's own sample page (served at "/") uses for its
    "Select an image"/"Select a video" uploads -- the multipart field's *name* attribute
    is itself the destination filename, not a fixed key like "file".

    Unlike api/import or api/file, /upload takes no Authorization header. It also does
    not validate `location` -- confirmed against a real device: posting to a nonexistent
    nested folder silently creates it, and the endpoint answers 200 "OK" regardless.  A
    return code of 0 here means only that the HTTP round-trip completed; it is not
    evidence the content is well-formed or ended up where intended.  Callers must read
    the file back (see http_request's "file" request_name) to actually confirm the
    write, which is exactly what both current callers do.
        :param ip_address: IP address of the Android device
        :param ip_port: port the Android device's Tasker HTTP server is listening on
        :param location: destination folder on the device, no leading slash (e.g. "Tasker/profiles")
        :param filename: destination filename within that folder
        :param file_content: raw bytes to write
        :return: return code (0 on success), and "" or an error message
    """
    http = "http://" if "http://" not in ip_address else ""
    url = f"{http}{ip_address}:{ip_port}/upload"

    error_message = ""
    response = None

    with suppress_stdout():  # Suppress any errors (system IMK)
        try:
            response = requests.post(
                url,
                params={"location": location},
                files={filename: (filename, file_content, "application/octet-stream")},
                timeout=15,
            )
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
        return 8, error_message

    if response is None:
        return 8, f"Request failed for url: {url} ...no response from the Android device."

    if response.status_code != 200:
        return 8, f"Request failed for url: {url} ...with status code {response.status_code}"

    return 0, ""


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
    # filemode MUST be "a", not "w".  ui.run() (rungui.process_gui) builds uvicorn's Config, whose
    # __init__ calls logging.config.dictConfig().  That starts with _clearExistingHandlers(), which
    # closes every handler already attached -- including the root FileHandler installed below.  A
    # closed FileHandler opened with mode "w" is never reopened: FileHandler.emit() deliberately
    # drops the record rather than truncate the file (CPython issue #42378), so every MapTasker log
    # entry after the GUI starts would silently vanish.  Mode "a" lets the handler reopen itself on
    # the next emit.  The filename above is unique per run (down to the second), so appending never
    # appends to a previous run's log.
    logging.basicConfig(
        filename=file_name,
        filemode="a",
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
# Matches the "_YYYYMMDD_HHMMSS" suffix write_full_backup_to_current_file appends to
# a filename's base (before the extension) -- used to strip a pre-existing one before
# appending the current timestamp, rather than stacking a new suffix on every save.
_TIMESTAMP_SUFFIX_RE = re.compile(r"_\d{8}_\d{6}$")


def write_full_backup_to_current_file() -> tuple[bool, str]:
    """Writes the entire current Tasker backup -- every Project, Profile, Task,
    Scene, everything -- out to a brand-new, timestamped copy of whatever file
    it was loaded from (PrimeItems.file_to_get), e.g. backup.xml ->
    backup_20260721_143005.xml, with the current in-memory state -- including
    any Task/Profile edits made through Edit/Add Task/Profile -- applied to
    that copy. If that file is itself an earlier such copy (its name already
    ends in a "_YYYYMMDD_HHMMSS" this same scheme produced -- see
    _TIMESTAMP_SUFFIX_RE), the new timestamp replaces the old one instead of
    stacking another suffix on top, so repeated saves stay
    backup_20260721_143005.xml -> backup_20260721_150112.xml rather than
    growing a new suffix each time. Backs the "Save To Current File" button in
    those dialogs (see
    userintr.py's save_*_to_current_file_event handlers, which then switch the
    app over to the new copy -- see userintr._reload_saved_copy_and_refresh --
    so it becomes "the current file" for any further editing/saving), as
    opposed to their "Save"/"Export Task/Profile" button, which exports
    just the one Task/Profile as a standalone file instead.

    The original file is deliberately never opened for writing -- only read,
    via the deep copy below -- so it's left exactly as it was; every "Save To
    Current File" click produces a new, independent snapshot alongside it
    rather than mutating it in place.

    An edit to a Project that already existed when the backup was loaded (e.g.
    profedit.add_profile_to_project's <pids> update) lands directly on the live
    tree -- taskerd.move_xml_to_table never deep-copies, so all_projects[name]
    ["xml"] IS the tree's own element, same object -- and needs no reconciling.
    A brand-new Project from Add Project is different: projedit.create_new_project
    builds a standalone element that all_projects only learns about via
    register_new_project, and it is never appended anywhere in PrimeItems.xml_root
    -- so deep-copying the tree, on its own, would silently omit it entirely from
    the saved file (confirmed: the Profile attached to it still saved correctly,
    since Profile reconciliation already existed below, but the Project itself
    vanished -- exactly the "new Project can't be found" symptom this fixes).
    Profile and Task edits have the identical problem in the ordinary (not just
    brand-new) case: taskedit.py/profedit.py's own module docstrings describe
    deliberately never touching PrimeItems.xml_tree, always working on a deep
    copy that only gets reconciled into the all_profiles/all_tasks lookup tables
    afterward (see apply_edited_profile_to_live_tree/register_new_profile/
    apply_edited_task_to_live_tree/register_new_task).

    This reconciles all three: starting from a deep copy of the original tree
    (preserving Scenes, Settings, and anything else this app doesn't track in a
    table of its own), it splices in each all_projects/all_profiles/all_tasks
    entry's *current* element in place of whatever the tree's own matching child
    holds (or appends it, for one added via Add Project/Add Profile/Add Task
    that never existed in the original file at all). Project is matched by
    <name> rather than <id> -- unlike all_profiles/all_tasks, all_projects is
    keyed by name, not id (taskerd.move_xml_to_table(..., get_id=False, "name")),
    so matching it by <id> the same way would never find an existing Project at
    all and duplicate every one of them into the output on every single save.

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

    def _element_id_key(element: ETW.Element) -> str | None:
        # Always the element's own <id> child -- never a table's dict key. all_profiles/
        # all_tasks happen to be keyed by <id> already (stable across a rename -- only
        # <nme> changes), but all_projects is keyed by <name>, which a Rename DOES change.
        # Matching Projects by name broke exactly that case: renaming "Test" to "Zz" left
        # root_copy's still-"Test"-named element unmatched (orphaned, never removed) while
        # the renamed copy got appended as a *second* Project -- both under different names,
        # so the "old name is gone" and "no duplicates" checks both failed even though no id
        # was reused. <id> doesn't change across a Rename (only <name> does), so matching on
        # it correctly finds and replaces the old element for every case: an untouched
        # pre-existing Project/Profile/Task (self-match, effectively a no-op), a renamed one
        # (finds the old element despite the name change), and a brand-new one (id was never
        # seen before, correctly falls through to "append").
        id_element = element.find("id")
        if id_element is None or not id_element.text or not id_element.text.strip():
            return None
        return id_element.text.strip()

    for tag, table_name in (("Project", "all_projects"), ("Profile", "all_profiles"), ("Task", "all_tasks")):
        existing_by_id = {}
        last_index_of_tag = -1
        for index, child in enumerate(root_copy):
            if child.tag != tag:
                continue
            last_index_of_tag = index
            child_id = _element_id_key(child)
            if child_id is not None:
                existing_by_id[child_id] = child

        for entry in PrimeItems.tasker_root_elements.get(table_name, {}).values():
            current_element = copy.deepcopy(entry["xml"])
            current_id = _element_id_key(current_element)
            old_element = existing_by_id.get(current_id) if current_id is not None else None
            if old_element is not None:
                index = list(root_copy).index(old_element)
                root_copy.remove(old_element)
                root_copy.insert(index, current_element)
            else:
                # Brand-new Project/Profile/Task (e.g. from Add Project/Add Profile/
                # Add Task), or one with no <id> at all (never seen in practice --
                # every Project/Profile/Task in this repo's own sample backup has one --
                # but handled the same safe way rather than risking two different
                # id-less elements colliding on a shared None key): insert it next to
                # its own kind rather than at the very end of the file, so the
                # top-level <Setting>/<Profile>/<Project>/<Scene>/<Task>/<Variable>
                # grouping that real Tasker backups always use stays intact.
                insert_at = last_index_of_tag + 1 if last_index_of_tag >= 0 else len(root_copy)
                root_copy.insert(insert_at, current_element)
                last_index_of_tag = insert_at

    ETW.indent(root_copy, space="\t")
    xml_text = _XML_DECLARATION + ETW.tostring(root_copy, encoding="unicode") + "\n"

    base_path, extension = os.path.splitext(file_path)
    # If the file we're copying from is itself an earlier "Save To Current File"
    # copy (i.e. its name already ends in a timestamp this same scheme produced),
    # replace that timestamp instead of appending another one -- otherwise every
    # save would tack on yet another suffix (backup_20260101_120000_20260101_130000...).
    base_path = _TIMESTAMP_SUFFIX_RE.sub("", base_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
    new_file_path = f"{base_path}_{timestamp}{extension}"

    try:
        with open(new_file_path, "w", encoding="utf-8") as out_file:
            out_file.write(xml_text)
    except OSError as e:
        return False, str(e)

    return True, new_file_path
