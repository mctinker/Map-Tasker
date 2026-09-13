"""API key storage (apikeys) Unit Tests

apikeys keeps the AI API keys in the system password store through 'keyring', or in an
owner-only file where there is no store to use.  Every test here puts a password store of
its own in place -- an in-memory one, or keyring's own 'fail' backend standing in for a
machine with no store -- and points both the fallback file and the working directory (where
the old '.maptasker.pkl' was written) at a temporary directory.  Nothing touches the real
Keychain, and nothing is left behind.
"""

from __future__ import annotations

import json
import os
import pickle
import stat
import sys
from pathlib import Path

import keyring.core
import pytest
from keyring.backend import KeyringBackend
from keyring.backends import fail
from keyring.errors import PasswordDeleteError
from maptasker.src import aiutils, apikeys
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import LEGACY_KEYFILE


class MemoryKeyring(KeyringBackend):
    """A password store that lives in a dictionary."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.entries: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.entries.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.entries[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if self.entries.pop((service, username), None) is None:
            raise PasswordDeleteError(username)


@pytest.fixture
def key_file(tmp_path: Path) -> Path:
    """Where the fallback file goes for this test."""
    return tmp_path / "config" / "MapTasker_API_Keys.json"


@pytest.fixture(autouse=True)
def store(tmp_path: Path, key_file: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryKeyring:
    """An empty in-memory password store, a private fallback file and working directory, no keys read yet."""
    backend = MemoryKeyring()
    monkeypatch.setattr(keyring.core, "_keyring_backend", backend)
    monkeypatch.setattr(apikeys, "fallback_file", lambda: key_file)
    monkeypatch.chdir(tmp_path)
    apikeys._stored_keys.cache_clear()
    yield backend
    apikeys._stored_keys.cache_clear()


@pytest.fixture
def no_store(store: MemoryKeyring, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine with no password store: every keyring call raises NoKeyringError."""
    monkeypatch.setattr(keyring.core, "_keyring_backend", fail.Keyring())


def _no_keys(**keys: str) -> dict[str, str]:
    """Every saved key "", but for the ones given."""
    return dict.fromkeys(apikeys.API_KEY_NAMES, "") | keys


def _old_key_file(contents: object) -> Path:
    """Write an old-style '.maptasker.pkl' to the working directory."""
    legacy_file = Path(LEGACY_KEYFILE)
    legacy_file.write_bytes(pickle.dumps(contents))
    return legacy_file


# ##################################################################################
# Saving and reading back.
# ##################################################################################
def test_keys_are_saved_to_the_password_store_and_nowhere_else(store: MemoryKeyring, key_file: Path) -> None:
    """With a store to use, each key is an entry of its own there, and no file is written."""
    saved = apikeys.save_api_keys({"openai_key": "sk-openai", "anthropic_key": "sk-ant", "model": "gpt-5"})

    assert saved is True
    assert store.entries == {
        (apikeys.SERVICE_NAME, "openai_key"): "sk-openai",
        (apikeys.SERVICE_NAME, "anthropic_key"): "sk-ant",
    }
    assert not key_file.exists()
    assert apikeys.load_api_keys() == _no_keys(openai_key="sk-openai", anthropic_key="sk-ant")


def test_a_cleared_key_is_removed_from_the_store(store: MemoryKeyring) -> None:
    """Saving a key as "" deletes its entry rather than leaving the old one behind."""
    apikeys.save_api_keys({"openai_key": "sk-openai", "gemini_key": "AIza-gemini"})
    apikeys.save_api_keys({"openai_key": "sk-openai", "gemini_key": ""})

    assert (apikeys.SERVICE_NAME, "gemini_key") not in store.entries
    assert apikeys.load_api_keys() == _no_keys(openai_key="sk-openai")


@pytest.mark.usefixtures("no_store")
def test_with_no_password_store_the_keys_go_to_an_owner_only_file(key_file: Path) -> None:
    """The fallback file is written whole, readable by its owner alone, and read back."""
    saved = apikeys.save_api_keys({"deepseek_key": "sk-deepseek"})

    assert saved is False
    assert json.loads(key_file.read_text(encoding="utf-8")) == _no_keys(deepseek_key="sk-deepseek")
    if sys.platform != "win32":  # Windows has no owner-only mode bits; %APPDATA% is per-user instead.
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert not list(key_file.parent.glob("*.tmp"))
    assert apikeys.load_api_keys() == _no_keys(deepseek_key="sk-deepseek")


def test_a_save_to_the_store_removes_the_file_an_earlier_save_fell_back_to(
    store: MemoryKeyring,
    key_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once the store can be used again, the keys stop being kept in a file as well."""
    monkeypatch.setattr(keyring.core, "_keyring_backend", fail.Keyring())
    apikeys.save_api_keys({"openai_key": "sk-older"})
    assert key_file.exists()

    monkeypatch.setattr(keyring.core, "_keyring_backend", store)
    assert apikeys.save_api_keys({"openai_key": "sk-newer"}) is True
    assert not key_file.exists()
    assert apikeys.load_api_keys() == _no_keys(openai_key="sk-newer")


def test_when_the_file_is_there_it_is_newer_than_the_store(
    store: MemoryKeyring,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A save that fell back to the file came after anything still in the store."""
    apikeys.save_api_keys({"openai_key": "sk-in-store"})
    monkeypatch.setattr(keyring.core, "_keyring_backend", fail.Keyring())
    apikeys.save_api_keys({"openai_key": "sk-in-file"})
    monkeypatch.setattr(keyring.core, "_keyring_backend", store)

    assert apikeys.load_api_keys() == _no_keys(openai_key="sk-in-file")


# ##################################################################################
# The old '.maptasker.pkl'.
# ##################################################################################
def test_an_old_pickled_key_file_is_moved_over_and_deleted(store: MemoryKeyring) -> None:
    """The old file held all of PrimeItems.ai -- model lists and all -- and may use the old Anthropic key name."""
    legacy_file = _old_key_file(
        {**PrimeItems.ai, "openai_key": "sk-openai", "anthropic_key": "", "claude_key": "sk-ant"}
    )

    assert apikeys.load_api_keys() == _no_keys(openai_key="sk-openai", anthropic_key="sk-ant")
    assert store.entries[(apikeys.SERVICE_NAME, "anthropic_key")] == "sk-ant"
    assert not legacy_file.exists()


def test_moving_an_old_key_file_keeps_keys_saved_since() -> None:
    """A key saved by a newer run wins; the old file only fills in what is missing."""
    apikeys.save_api_keys({"openai_key": "sk-newer"})
    _old_key_file({"openai_key": "sk-older", "gemini_key": "AIza-older"})

    assert apikeys.load_api_keys() == _no_keys(openai_key="sk-newer", gemini_key="AIza-older")


@pytest.mark.usefixtures("no_store")
def test_an_old_key_file_is_moved_to_the_fallback_file_when_there_is_no_store(key_file: Path) -> None:
    """No store is no reason to keep the old pickle around."""
    legacy_file = _old_key_file({"gemini_key": "AIza-gemini"})

    assert apikeys.load_api_keys() == _no_keys(gemini_key="AIza-gemini")
    assert json.loads(key_file.read_text(encoding="utf-8")) == _no_keys(gemini_key="AIza-gemini")
    assert not legacy_file.exists()


def test_the_first_plain_text_key_files_are_moved_too() -> None:
    """Before the pickle, the key file was a single key as text."""
    Path(LEGACY_KEYFILE).write_text("sk-from-text\n", encoding="utf-8")

    assert apikeys.load_api_keys() == _no_keys(api_key="sk-from-text")
    assert not Path(LEGACY_KEYFILE).exists()


class _RunsCodeWhenLoaded:
    """Pickles as a call to os.mkdir -- which an unrestricted pickle.load would make."""

    def __init__(self, target: Path) -> None:
        self.target = target

    def __reduce__(self) -> tuple:
        return (os.mkdir, (str(self.target),))


def test_an_old_key_file_that_would_run_code_is_refused_and_left_alone(store: MemoryKeyring, tmp_path: Path) -> None:
    """Loading it runs nothing, moves nothing, and leaves the file for the user to look at."""
    marker = tmp_path / "code-ran"
    legacy_file = _old_key_file({"openai_key": "sk-openai", "payload": _RunsCodeWhenLoaded(marker)})

    assert apikeys.load_api_keys() == _no_keys()
    assert not marker.exists()
    assert legacy_file.exists()
    assert store.entries == {}


# ##################################################################################
# aiutils.get_api_key, which the rest of MapTasker calls.
# ##################################################################################
def test_get_api_key_copies_the_saved_keys_into_prime_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """The keys land in PrimeItems.ai; nothing else in it is touched."""
    apikeys.save_api_keys({"anthropic_key": "sk-ant", "api_key": "sk-given"})
    monkeypatch.setattr(PrimeItems, "ai", {"anthropic_key": "", "api_key": "", "anthropic_models": ["claude-sonnet-5"]})

    assert aiutils.get_api_key() == "sk-given"
    assert PrimeItems.ai["anthropic_key"] == "sk-ant"
    assert PrimeItems.ai["anthropic_models"] == ["claude-sonnet-5"]


def test_get_api_key_with_nothing_saved_leaves_prime_items_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key typed in this run is not wiped by there being none saved."""
    table = {"openai_key": "sk-typed-this-run"}
    monkeypatch.setattr(PrimeItems, "ai", table)

    assert aiutils.get_api_key() == "None"
    assert table == {"openai_key": "sk-typed-this-run"}
