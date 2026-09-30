"""Font discovery survives a system it cannot read, and does not hide its own bugs.

The outer guard around finding the font files used to catch every exception, so a bug in
the discovery code looked exactly like a machine with no fonts.  It now catches what an
unreadable system actually raises.
"""

from __future__ import annotations

import pytest

from maptasker.src import mapfonts


def _discovery_that_raises(monkeypatch, error: BaseException) -> None:
    """Make every platform's font discovery raise the given error."""

    def raise_it(*_args) -> list:
        raise error

    for name in ("_windows_font_files", "_linux_font_files", "_scan_font_dirs"):
        monkeypatch.setattr(mapfonts, name, raise_it)


def test_an_unreadable_font_directory_means_no_fonts(monkeypatch) -> None:
    _discovery_that_raises(monkeypatch, PermissionError("no access to the font directory"))
    assert mapfonts._font_files() == []


def test_fc_list_output_in_the_wrong_encoding_means_no_fonts(monkeypatch) -> None:
    _discovery_that_raises(monkeypatch, UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
    assert mapfonts._font_files() == []


def test_a_bug_in_font_discovery_is_not_mistaken_for_no_fonts(monkeypatch) -> None:
    _discovery_that_raises(monkeypatch, TypeError("a bug"))
    with pytest.raises(TypeError):
        mapfonts._font_files()
