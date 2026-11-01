"""The file picker: what it lists, where it stops climbing, and how a choice is handed back."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from maptasker.src.gui import getfile
from maptasker.src.gui.getfile import LocalFilePicker
from nicegui import events, ui

from tests.nicegui_harness import open_page


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "Zebra").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta.xml").write_text("<x/>")
    (tmp_path / "Apple.xml").write_text("<x/>")
    (tmp_path / ".hidden.xml").write_text("<x/>")
    return tmp_path


class _Picker(LocalFilePicker):
    """The picker, with what it is asked to hand back collected in a list instead of resolving the dialog."""

    chosen: list[list[str]]


def _event(args: dict[str, Any]) -> events.GenericEventArguments:
    return cast("events.GenericEventArguments", SimpleNamespace(args=args))


async def _picker(directory: Path, **options: Any) -> _Picker:
    """A picker built on a page, with what it hands back collected rather than awaited."""
    built: list[_Picker] = []

    def build() -> None:
        picker = _Picker(str(directory), **options)
        picker.chosen = []
        picker.submit = picker.chosen.append  # type: ignore[method-assign]
        built.append(picker)

    async with open_page(build):
        return built[0]
    raise AssertionError


def _names(picker: _Picker) -> list[str]:
    return [row["name"] for row in picker.grid.options["rowData"]]


@pytest.mark.asyncio
async def test_folders_come_first_then_files_each_in_name_order_and_hidden_ones_are_left_out(folder: Path) -> None:
    picker = await _picker(folder)

    assert _names(picker) == ["📁 <strong>alpha</strong>", "📁 <strong>Zebra</strong>", "Apple.xml", "beta.xml"]


@pytest.mark.asyncio
async def test_hidden_files_are_listed_when_asked_for(folder: Path) -> None:
    picker = await _picker(folder, show_hidden_files=True)

    assert ".hidden.xml" in _names(picker)


@pytest.mark.asyncio
async def test_there_is_no_way_up_from_where_it_started_unless_a_higher_limit_is_given(folder: Path) -> None:
    picker = await _picker(folder)

    assert "📁 <strong>..</strong>" not in _names(picker)


@pytest.mark.asyncio
async def test_opening_a_folder_shows_its_contents_and_a_way_back_up(folder: Path) -> None:
    (folder / "alpha" / "inner.xml").write_text("<x/>")
    picker = await _picker(folder)

    picker.handle_double_click(_event({"data": {"path": str(folder / "alpha")}}))

    assert _names(picker) == ["📁 <strong>..</strong>", "inner.xml"]
    assert picker.grid.options["rowData"][0]["path"] == str(folder)
    assert picker.chosen == []


@pytest.mark.asyncio
async def test_a_file_double_clicked_is_the_choice(folder: Path) -> None:
    picker = await _picker(folder)

    picker.handle_double_click(_event({"data": {"path": str(folder / "beta.xml")}}))

    assert picker.chosen == [[str(folder / "beta.xml")]]


@pytest.mark.asyncio
async def test_ok_hands_back_every_row_selected(folder: Path) -> None:
    picker = await _picker(folder, multiple=True)

    async def selected() -> list[dict[str, str]]:
        return [{"path": str(folder / "beta.xml")}, {"path": str(folder / "Apple.xml")}]

    picker.grid.get_selected_rows = selected  # type: ignore[method-assign]
    await picker._handle_ok()

    assert picker.chosen == [[str(folder / "beta.xml"), str(folder / "Apple.xml")]]


@pytest.mark.asyncio
async def test_with_no_limit_at_all_the_way_up_is_there_until_the_top(folder: Path) -> None:
    picker = await _picker(folder, upper_limit=None)

    assert _names(picker)[0] == "📁 <strong>..</strong>"


@pytest.mark.asyncio
async def test_a_higher_limit_lets_it_climb_to_that_limit_and_no_further(folder: Path) -> None:
    picker = await _picker(folder / "alpha", upper_limit=str(folder))

    assert _names(picker) == ["📁 <strong>..</strong>"]
    picker.handle_double_click(_event({"data": {"path": str(folder)}}))
    assert "📁 <strong>..</strong>" not in _names(picker)


def test_windows_drives_are_read_from_the_bitmask_when_python_cannot_list_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delattr(getfile.os, "listdrives", raising=False)
    kernel = SimpleNamespace(GetLogicalDrives=lambda: 0b1101)  # C, A and D... bits 0, 2 and 3
    monkeypatch.setattr(getfile.ctypes, "windll", SimpleNamespace(kernel32=kernel), raising=False)

    assert getfile.windows_drives() == ["A:\\", "C:\\", "D:\\"]


@pytest.mark.asyncio
async def test_on_windows_a_toggle_picks_the_drive(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(getfile.platform, "system", lambda: "Windows")
    monkeypatch.setattr(getfile, "windows_drives", lambda: [str(folder.anchor), str(folder)])
    picker = await _picker(folder)

    assert isinstance(picker.drives_toggle, ui.toggle)
    picker.drives_toggle.value = str(folder)
    picker.update_drive()

    assert picker.path == folder


@pytest.mark.asyncio
async def test_on_windows_with_no_drives_there_is_no_toggle(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(getfile.platform, "system", lambda: "Windows")
    monkeypatch.setattr(getfile, "windows_drives", list)

    picker = await _picker(folder)

    assert not hasattr(picker, "drives_toggle")
