"""MAPTASKER_FAKE_VERSION makes MapTasker take itself to be an older version, so the update check can be tried."""

from __future__ import annotations

import importlib.metadata

import pytest
from maptasker.src.core.sysconst import FAKE_VERSION_VARIABLE, running_version


def test_with_nothing_set_the_installed_version_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FAKE_VERSION_VARIABLE, raising=False)

    assert running_version() == importlib.metadata.version("maptasker")


def test_the_variable_replaces_the_installed_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FAKE_VERSION_VARIABLE, " 1.2.3 ")

    assert running_version() == "1.2.3"


def test_an_empty_variable_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FAKE_VERSION_VARIABLE, "  ")

    assert running_version() == importlib.metadata.version("maptasker")
