"""Tests for the Windows drive listing used by the local file picker."""

from __future__ import annotations

import os
import platform

import pytest
from maptasker.src.gui import getfile


def test_windows_drives_needs_no_pywin32():
    """Listing drives must never import pywin32, which MapTasker does not install."""
    source = open(getfile.__file__, encoding="utf-8").read()
    assert "win32api" not in source


def test_windows_drives_uses_listdrives(monkeypatch: pytest.MonkeyPatch):
    """Python 3.12+ lists drives with os.listdrives()."""
    monkeypatch.setattr(getfile.sys, "platform", "win32")
    monkeypatch.setattr(os, "listdrives", lambda: ["C:\\", "D:\\"], raising=False)
    assert getfile.windows_drives() == ["C:\\", "D:\\"]


def test_windows_drives_on_windows():
    """On a real Windows machine, at least one drive root is found."""
    if platform.system() != "Windows":
        return
    drives = getfile.windows_drives()
    assert drives
    assert all(d.endswith(":\\") for d in drives)


def test_windows_drives_are_none_anywhere_else(monkeypatch: pytest.MonkeyPatch):
    """Drives are a Windows idea: no other platform has drive roots to list."""
    monkeypatch.setattr(getfile.sys, "platform", "darwin")
    assert getfile.windows_drives() == []
