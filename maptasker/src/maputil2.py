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
from functools import lru_cache

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


# A #hex colour as CSS accepts one: three, six or eight digits behind a "#".  Eight is
# included because Tasker writes them (#AARRGGBB, alpha first -- see sceneview.tasker_colour,
# which is the one place that ordering is untangled); this only says the value is a colour,
# not which way round to read it.
HEX_COLOUR = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$", re.IGNORECASE)


@lru_cache(maxsize=1)
def html_colour_names() -> frozenset[str]:
    """The colour names CSS knows, lowercased -- "red", "rebeccapurple", all 148 of them.

    Taken from Pillow's own table rather than written out here, because that table IS the
    CSS/X11 list a browser uses and a hand-copied one is a list that can quietly be wrong.
    Pillow is already a hard dependency (see pyproject.toml, and format.py, which parses
    colours with it).
    """
    from PIL import ImageColor  # noqa: PLC0415

    return frozenset(ImageColor.colormap)


# How Tasker writes an icon reference, in the three forms its Scenes actually carry:
#   icon:Close                                    -- a Material icon by name
#   symbol:cloud_upload;weight:600;opsz:24        -- a Material Symbol, plus how to draw it
#   content://...taskerm.iconprovider//app/<pkg>  -- an installed app's own icon
_TASKER_ICON_PREFIXES = ("icon:", "symbol:")
_TASKER_ICON_CONTENT = "content://"


def tasker_icon_name(value: str) -> str:
    """What an icon reference is *called*, for showing to someone: "Close", "cloud_upload",
    "com.android.vending".

    Everything dropped here says how to find or draw the icon rather than which icon it is --
    the scheme in front, the ";weight:600;opsz:24" that styles a Symbol, the provider URI
    around a package name.  Anything not in one of those forms (a %variable, a plain name)
    comes back as it went in.
    """
    name = value.strip()
    if name.startswith(_TASKER_ICON_CONTENT):
        return next((part for part in reversed(name.split("/")) if part), name)
    for prefix in _TASKER_ICON_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :].split(";", 1)[0]
    return name


def is_html_colour(text: str) -> bool:
    """Whether this is a colour a browser will take: one of the CSS colour names, or a #hex
    value.  Case doesn't matter -- CSS doesn't care, and neither does Tasker.

    Says nothing about empty (that is "not set", which is a caller's decision to make) or
    about a %variable (whose value isn't known here).
    """
    value = text.strip()
    return bool(value) and (value.lower() in html_colour_names() or bool(HEX_COLOUR.match(value)))


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
#
# Public because it is the only description of this naming scheme anywhere: diffload
# reads it the other way round, to work out which file a "Save To Current File" copy was
# made FROM, so that "Compare with the original" needs no file picker.  A second copy of
# this pattern living over there would be free to drift away from the one that writes the
# names.
TIMESTAMP_SUFFIX_RE = re.compile(r"_\d{8}_\d{6}$")


def render_full_backup_xml(*, indent: bool = True) -> str:
    """Render the entire in-memory Tasker backup -- every Project, Profile, Task,
    Scene and everything else the loaded file holds -- as one XML string, with every
    edit made this session applied to it.

    This is "what the loaded configuration currently IS", and it has two callers that
    want exactly that and nothing else: write_full_backup_to_current_file below, which
    writes it to a new file, and sessundo, which keeps it as an undo checkpoint.  Both
    have to agree byte for byte on what the configuration is, so there is one renderer
    rather than two -- an undo that restored a slightly different reconciliation than
    the one a save writes would be a worse bug than having no undo.

    `indent` separates the two, and it decides more than whitespace.  ETW.indent MUTATES
    the tree it is given -- it writes .text and .tail on every element in it -- so the
    indented render is the one that has to work on a deep copy.  The un-indented render
    does not, and so it does not take one: it builds a throwaway root that REFERENCES the
    live elements, serializes it, and drops it.  That is the whole difference in cost, and
    on a real 8 MB backup it is most of the time this function takes -- roughly 1.6 of 1.8
    seconds is copying, against about 0.2 to serialize.  A save can afford that once; an
    undo checkpoint, taken on every edit the user commits, cannot.

    So the rule the two branches share: the un-indented render's tree is made of live
    elements and NOTHING may modify it.  Adding a mutation below that runs for both would
    be editing the user's loaded configuration as a side effect of reading it.

    WHY THIS IS A RECONCILIATION AND NOT A SERIALIZE.

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

    This reconciles all four: starting from the original tree (preserving Settings,
    Variables, and anything else this app doesn't track in a table of its own), it
    splices in each all_projects/all_profiles/all_tasks/all_scenes entry's *current*
    element in place of whatever the tree's own matching child holds, appends the ones
    added via Add Project/Add Profile/Add Task/Add Scene that never existed in the
    original file at all, and drops the tree's children that the tables no longer have
    -- which is how a Delete reaches the file.  See the comment on that third case
    below; it was missing, and a deleted item came back on the next load.
    Project is matched by <name> rather than <id> -- unlike all_profiles/
    all_tasks, all_projects is keyed by name, not id
    (taskerd.move_xml_to_table(..., get_id=False, "name")), so matching it by
    <id> the same way would never find an existing Project at all and duplicate
    every one of them into the output on every single save.  Scene is matched by
    <nme>, since a Scene has no <id> at all -- see _element_match_key.

    The caller must have a backup loaded: PrimeItems.xml_root is the tree this
    starts from, and there is nothing to render without one.

    Raises:
        ValueError: if no backup is loaded (PrimeItems.xml_root is None).
    """
    if PrimeItems.xml_root is None:
        msg = "No backup data is currently loaded."
        raise ValueError(msg)

    root = PrimeItems.xml_root
    # The root the render is built on, and its children as a plain list to reconcile.
    #
    # For a file that is one deep copy of the whole tree, which the indent pass is then
    # free to write all over.  For a checkpoint it is a bare root of the same class holding
    # the LIVE children -- no copying at all, and nothing below may modify it.  A bare root
    # rather than the loaded one because appending to that would reorder the user's own
    # tree; its class is read off the tree because the parse is defusedxml's and its
    # Element is not necessarily ETW's (the same reason projedit reads it off there).
    if indent:
        rendered_root = copy.deepcopy(root)
    else:
        rendered_root = type(root)(root.tag, dict(root.attrib))
        rendered_root.text, rendered_root.tail = root.text, root.tail
    children = list(rendered_root) if indent else list(root)

    def _element_id_key(element: ETW.Element) -> str | None:
        # Always the element's own <id> child -- never a table's dict key. all_profiles/
        # all_tasks happen to be keyed by <id> already (stable across a rename -- only
        # <nme> changes), but all_projects is keyed by <name>, which a Rename DOES change.
        # Matching Projects by name broke exactly that case: renaming "Test" to "Zz" left
        # the rendered file's still-"Test"-named child unmatched (orphaned, never removed)
        # while the renamed copy got appended as a *second* Project -- both under different names,
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

    def _element_match_key(element: ETW.Element, tag: str) -> str | None:
        # What identifies this element across the two trees being reconciled.  For
        # Project/Profile/Task that is <id> (see _element_id_key).  A Scene has no <id>
        # at all -- its identity is its name, held in <nme> and, redundantly, in its own
        # sr="scene<name>" attribute (see sceneedit.py's module docstring).
        #
        # Matching a Scene by name is only safe because sceneedit was built around this
        # constraint: projedit/profedit edit a detached deep copy and swap it into the
        # table afterward, which is fine when the match key is <id> (a rename doesn't
        # change it) but would strand a renamed Scene -- the tree's own element would still
        # say the old name, nothing would match, and the save would emit both.
        # sceneedit.apply_edited_scene_to_live_tree therefore copies the edit *onto* the
        # live element rather than swapping objects, and the children this renders are
        # that same live tree's (or copies of it, taken above) -- so both sides always
        # carry the same name by the time this runs.  Change one of those two and this
        # breaks.
        if tag == "Scene":
            return (element.findtext("nme", "") or "").strip() or None
        return _element_id_key(element)

    for tag, table_name in (
        ("Project", "all_projects"),
        ("Profile", "all_profiles"),
        ("Task", "all_tasks"),
        ("Scene", "all_scenes"),
    ):
        # What the lookup tables say this tag's elements are, right now, by match key.
        # Every one of the three outcomes below is decided against this one dictionary:
        # a tree child whose key is in it is REPLACED by the table's version, a key in it
        # that no tree child carries is APPENDED as something newly added, and a tree child
        # whose key is NOT in it has been DELETED and is dropped.
        current_by_key = {}
        # Table entries with no match key at all: never seen in practice -- every
        # Project/Profile/Task in this repo's own sample backup has an <id> and every
        # Scene an <nme> -- but they cannot be matched, so they are carried along as
        # additions rather than risking two different key-less elements colliding on a
        # shared None key.
        keyless_additions = []
        for entry in PrimeItems.tasker_root_elements.get(table_name, {}).values():
            current_element = copy.deepcopy(entry["xml"]) if indent else entry["xml"]
            current_key = _element_match_key(current_element, tag)
            if current_key is None:
                keyless_additions.append(current_element)
            else:
                current_by_key[current_key] = current_element

        # DROPPING IS WHY THIS IS A REBUILT LIST AND NOT AN IN-PLACE PATCH.
        #
        # Until this existed, the reconciliation could only replace a child or add one, so
        # a Delete never reached the file: delete_task/delete_profile/delete_scene take the
        # item out of the lookup tables (which is what makes it disappear from the Map, the
        # Diagram, the Tree and every pulldown) but leave the tree's own child alone, on
        # purpose -- the tree is not what the application reads.  Rendering straight from
        # that tree wrote the deleted item back out, so "delete the Task, Save To Current
        # File" produced a file with the Task still in it, and reloading it brought the
        # Task back.  Silently: nothing in the GUI said the delete had not taken.
        rebuilt = []
        matched_keys = set()
        last_index_of_tag = -1
        for child in children:
            if child.tag != tag:
                rebuilt.append(child)
                continue
            child_key = _element_match_key(child, tag)
            if child_key is None:
                # Unidentifiable, so it cannot be shown to have been deleted either.  Kept:
                # dropping a child on a guess is the one outcome here with no way back.
                rebuilt.append(child)
            elif child_key in current_by_key:
                rebuilt.append(current_by_key[child_key])
                matched_keys.add(child_key)
            else:
                continue  # Deleted from the tables -- and so from the file.
            last_index_of_tag = len(rebuilt) - 1

        for current_key, current_element in current_by_key.items():
            if current_key in matched_keys:
                continue
            # Brand-new Project/Profile/Task/Scene (e.g. from Add Project/Add Profile/Add
            # Task/Add Scene): insert it next to its own kind rather than at the very end
            # of the file, so the top-level <Setting>/<Profile>/<Project>/<Scene>/<Task>/
            # <Variable> grouping that real Tasker backups always use stays intact.
            insert_at = last_index_of_tag + 1 if last_index_of_tag >= 0 else len(rebuilt)
            rebuilt.insert(insert_at, current_element)
            last_index_of_tag = insert_at

        for current_element in keyless_additions:
            insert_at = last_index_of_tag + 1 if last_index_of_tag >= 0 else len(rebuilt)
            rebuilt.insert(insert_at, current_element)
            last_index_of_tag = insert_at

        children = rebuilt

    rendered_root[:] = children

    if indent:
        ETW.indent(rendered_root, space="\t")
    return _XML_DECLARATION + ETW.tostring(rendered_root, encoding="unicode") + "\n"


def write_full_backup_to_current_file() -> tuple[bool, str]:
    """Writes the entire current Tasker backup -- every Project, Profile, Task,
    Scene, everything -- out to a brand-new, timestamped copy of whatever file
    it was loaded from (PrimeItems.file_to_get), e.g. backup.xml ->
    backup_20260721_143005.xml, with the current in-memory state -- including
    any Task/Profile edits made through Edit/Add Task/Profile -- applied to
    that copy. If that file is itself an earlier such copy (its name already
    ends in a "_YYYYMMDD_HHMMSS" this same scheme produced -- see
    TIMESTAMP_SUFFIX_RE), the new timestamp replaces the old one instead of
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
    via render_full_backup_xml's deep copy -- so it's left exactly as it was;
    every "Save To
    Current File" click produces a new, independent snapshot alongside it
    rather than mutating it in place.

    What actually goes IN the file is render_full_backup_xml's job (above): this
    function is only the naming and the write.  The two were one function until
    session undo needed the same reconciled render without a file to put it in.

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

    try:
        xml_text = render_full_backup_xml()
    except ValueError as e:
        return False, str(e)

    base_path, extension = os.path.splitext(file_path)
    # If the file we're copying from is itself an earlier "Save To Current File"
    # copy (i.e. its name already ends in a timestamp this same scheme produced),
    # replace that timestamp instead of appending another one -- otherwise every
    # save would tack on yet another suffix (backup_20260101_120000_20260101_130000...).
    base_path = TIMESTAMP_SUFFIX_RE.sub("", base_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
    new_file_path = f"{base_path}_{timestamp}{extension}"

    # Normally there is nothing at that name and this does nothing -- the name has this
    # second's timestamp in it.  It matters for the one case that collides: two saves
    # within the same second generate the same name, and the second would overwrite the
    # first without it.  Lazy import to avoid a circular one (mirrors getbakup).
    from maptasker.src.presave import backup_local_file  # noqa: PLC0415

    backup_local_file(new_file_path)

    try:
        with open(new_file_path, "w", encoding="utf-8") as out_file:
            out_file.write(xml_text)
    except OSError as e:
        return False, str(e)

    return True, new_file_path
