"""apikeys: where the AI API keys are kept between runs."""

#! /usr/bin/env python3
#                                                                                      #
# apikeys: Save and restore the AI API keys                                            #
#                                                                                      #
# The keys are secrets, so they go where the operating system keeps secrets: through
# 'keyring', to the Keychain on macOS, Credential Manager on Windows and the Secret
# Service (GNOME Keyring, KWallet) on a Linux desktop.  A machine with no such store -- a
# headless Linux box, say -- gets a JSON file in the user's own configuration folder
# instead, readable by that user alone.
#
# They used to be pickled, along with the rest of PrimeItems.ai, to '.maptasker.pkl' in
# whichever directory MapTasker was started from: readable by anyone who could read that
# directory, and a file that would run whatever code was put in it the moment it was
# loaded.  One found there is read once, by an unpickler that will not build anything but
# plain data, its keys moved over, and then deleted.
#
# Nothing here touches PrimeItems -- aiutils.get_api_key copies what is loaded into it --
# so this module stays out of the import cycle the GUI modules are in.
from __future__ import annotations

import contextlib
import functools
import io
import json
import os
import pickle
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from maptasker.src.sysconst import API_KEYS_FILE, LEGACY_KEYFILE, logger

if TYPE_CHECKING:
    from collections.abc import Mapping

# The service every key is filed under in the password store.  Each key is an entry of its
# own, named for its PrimeItems.ai slot, since a store holds one string per entry.
SERVICE_NAME = "MapTasker"

# The PrimeItems.ai slots that are saved.  'api_key' is a key handed to a run directly
# rather than through the API key dialog (see rungui); the old pickle saved it along with
# the rest, so it still is.
API_KEY_NAMES = ("openai_key", "anthropic_key", "deepseek_key", "gemini_key", "api_key")

# A pickle written with protocol 2 or later opens with this byte.  The very first key files
# were plain text holding a single key, and those do not.
_PICKLE_PROTOCOL_MARKER = b"\x80"


def config_directory() -> Path:
    """
    Return MapTasker's folder inside the one the operating system sets aside for this user's settings.

    Returns:
        Path: the folder.  It is not created here.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "MapTasker"


def fallback_file() -> Path:
    """
    Return the file the keys are saved to when there is no password store to save them in.

    Returns:
        Path: the JSON key file in the user's configuration folder.
    """
    return config_directory() / API_KEYS_FILE


def load_api_keys() -> dict[str, str]:
    """
    Return the saved API keys: one entry per API_KEY_NAMES, "" for any that is not saved.

    The store is read once a run, and again only after save_api_keys changes what is in it.
    The GUI asks whether a key is set far more often than that, and asking the Keychain five
    times over each time would be slow -- and, for a Python it has not seen before, would
    ask the user's permission five times over as well.

    Returns:
        dict[str, str]: the keys, as a copy the caller is free to change.
    """
    return dict(_stored_keys())


def save_api_keys(keys: Mapping[str, str]) -> bool:
    """
    Save the API keys, replacing whatever was saved before.  A key that is "" is removed.

    Args:
        keys (Mapping[str, str]): the API_KEY_NAMES entries to keep -- PrimeItems.ai will
            do.  Anything else in it is ignored.

    Returns:
        bool: True if the keys went to the password store, False if there was no store to
            use and they went to fallback_file() instead.

    Raises:
        OSError: there was no store, and the file could not be written either.  Whatever was
            saved before is still there.
    """
    wanted = {name: keys.get(name) or "" for name in API_KEY_NAMES}
    try:
        return _write_store(wanted)
    finally:
        _stored_keys.cache_clear()


@functools.cache
def _stored_keys() -> dict[str, str]:
    """
    Read the saved keys, moving an old '.maptasker.pkl' over first if there is one.

    Returns:
        dict[str, str]: the keys, one entry per API_KEY_NAMES.
    """
    _move_legacy_key_file()
    return _read_store()


def _read_store() -> dict[str, str]:
    """
    Read the keys from wherever the most recent save put them.

    Returns:
        dict[str, str]: the keys, one entry per API_KEY_NAMES.
    """
    # The file only exists while the most recent save was one that could not use the
    # password store -- a save that can use it removes the file -- so when it is there, it
    # is the newer of the two.
    key_file = fallback_file()
    if key_file.exists():
        return _read_key_file(key_file)
    try:
        return {name: keyring.get_password(SERVICE_NAME, name) or "" for name in API_KEY_NAMES}
    except KeyringError as error:
        logger.warning("No API keys read: the password store could not be used (%s).", error)
        return dict.fromkeys(API_KEY_NAMES, "")


def _write_store(wanted: dict[str, str]) -> bool:
    """
    Save the keys to the password store, or to the fallback file if the store can't be used.

    Args:
        wanted (dict[str, str]): every API_KEY_NAMES entry, "" for a key to remove.

    Returns:
        bool: True if they went to the password store, False if they went to the file.
    """
    key_file = fallback_file()
    try:
        for name, value in wanted.items():
            if value:
                keyring.set_password(SERVICE_NAME, name, value)
            else:
                with contextlib.suppress(PasswordDeleteError):  # It was never saved.
                    keyring.delete_password(SERVICE_NAME, name)
    except KeyringError as error:
        logger.warning("Saving the API keys to %s: the password store could not be used (%s).", key_file, error)
        _write_key_file(key_file, wanted)
        return False

    # A file left by an earlier save that could not use the store would otherwise be read in
    # preference to what was just saved -- and go on holding the keys in a file besides.
    try:
        key_file.unlink(missing_ok=True)
    except OSError as error:
        logger.error("The API keys were saved, but the old key file %s could not be removed (%s).", key_file, error)
    return True


def _read_key_file(key_file: Path) -> dict[str, str]:
    """
    Read the keys from the fallback file.

    Args:
        key_file (Path): the file.

    Returns:
        dict[str, str]: the keys, one entry per API_KEY_NAMES -- all "" if it can't be read.
    """
    try:
        contents = json.loads(key_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:  # ValueError covers bad JSON and bad UTF-8 alike.
        logger.error("The API key file %s could not be read (%s).", key_file, error)
        contents = {}
    if not isinstance(contents, dict):
        contents = {}
    return {name: value if isinstance(value := contents.get(name), str) else "" for name in API_KEY_NAMES}


def _write_key_file(key_file: Path, wanted: dict[str, str]) -> None:
    """
    Write the keys to the fallback file, readable by its owner only.

    Written to a temporary file and swapped into place, the way getputer.write_atomically
    writes the settings, so a save that fails partway leaves the previous keys whole.  Not
    that function itself: it carries the old file's permissions over, and this file must be
    owner-only whatever they were.  mkstemp creates it that way.

    Args:
        key_file (Path): the file.
        wanted (dict[str, str]): the keys to write.
    """
    key_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp_fd, temp_name = tempfile.mkstemp(dir=key_file.parent, prefix=f".{key_file.name}.", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            json.dump(wanted, temp_file, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_name, key_file)
    except BaseException:
        # Cleans up and re-raises, swallowing nothing.
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


class _PlainDataUnpickler(pickle.Unpickler):
    """
    An unpickler that refuses to import anything, so it can build nothing but plain data.

    The old key file only ever held dictionaries, lists, strings and booleans, and a pickle
    needs to name no class or function to hold those.  One that does name one -- which is
    how a pickle gets code run as it is loaded -- is refused.
    """

    def find_class(self, module: str, name: str) -> NoReturn:
        """
        Refuse every class and function the pickle names.

        Args:
            module (str): the module the pickle names.
            name (str): the name within it.

        Raises:
            pickle.UnpicklingError: always.
        """
        message = f"it names {module}.{name}, which a key file never holds"
        raise pickle.UnpicklingError(message)


def _move_legacy_key_file() -> None:
    """Move the keys in an old '.maptasker.pkl' in the current directory over, then delete it."""
    legacy_file = Path(LEGACY_KEYFILE)
    if not legacy_file.is_file():
        return
    legacy_keys = _read_legacy_key_file(legacy_file)
    if legacy_keys is None:
        return  # Unreadable.  Left where it is, and logged.

    # Keys saved since, by a run started in some other directory, are newer than these.
    current = _read_store()
    merged = {name: current[name] or legacy_keys[name] for name in API_KEY_NAMES}
    try:
        in_password_store = _write_store(merged)
        legacy_file.unlink()
    except OSError as error:
        logger.error(
            "The API keys in %s could not be moved, so it is left in place (%s).", legacy_file.resolve(), error
        )
        return
    destination = "the password store" if in_password_store else str(fallback_file())
    logger.info("Moved the API keys in %s to %s.", legacy_file.resolve(), destination)


def _read_legacy_key_file(legacy_file: Path) -> dict[str, str] | None:
    """
    Read the keys out of an old '.maptasker.pkl'.

    Args:
        legacy_file (Path): the file.

    Returns:
        dict[str, str] | None: the keys, one entry per API_KEY_NAMES, or None if the file
            could not be read or held anything but plain data.
    """
    try:
        data = legacy_file.read_bytes()
        if data.startswith(_PICKLE_PROTOCOL_MARKER):
            contents = _PlainDataUnpickler(io.BytesIO(data)).load()
        else:
            contents = {"api_key": data.decode("utf-8").strip()}  # The first key files: one key, as text.
    except Exception as error:  # noqa: BLE001  A damaged or hostile pickle fails in any number of ways; all mean "unusable".
        logger.error(
            "The old API key file %s could not be read, so it is left in place (%s).", legacy_file.resolve(), error
        )
        return None
    if not isinstance(contents, dict):
        logger.error("The old API key file %s holds no keys, so it is left in place.", legacy_file.resolve())
        return None

    # 'claude_key' is what the Anthropic key was saved as before it became 'anthropic_key'.
    contents = {**contents, "anthropic_key": contents.get("anthropic_key") or contents.get("claude_key")}
    return {name: value if isinstance(value := contents.get(name), str) else "" for name in API_KEY_NAMES}
