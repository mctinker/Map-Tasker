"""The "Check readiness" button in the Edit Project dialog (GUI) Unit Tests

Built for real, the way test_gui_window builds the window: the actual Edit Project dialog, opened
inside NiceGUI's in-process user simulation, with the real button pressed.  What is asserted is
that the button is where the Redact tick-box is, that pressing it shows the report readiness.py
computed from the export, and that the report can be put on the clipboard.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import projedit
from maptasker.src.gui import guiwins
from maptasker.src.mapgen import taskerd
from maptasker.src.mapops import readiness
from nicegui import ui

from tests.test_gui_window import _button, _click, _open_window, fresh_session  # noqa: F401

pytestmark = pytest.mark.asyncio

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <id>f19b5151-01b6-46f6-8cd5-b3bc1fe0b486</id>
    <name>Home</name>
    <tids>20</tids>
  </Project>
  <Task sr="task20">
    <id>20</id>
    <nme>Opener</nme>
    <Action sr="act0" ve="7"><code>379</code></Action>
    <Action sr="act1" ve="7"><code>375</code></Action>
  </Task>
</TaskerData>
"""


def _load_configuration() -> None:
    root = ET.fromstring(_XML)
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file, encoding="utf-8") as handle:
        PrimeItems.tasker_arg_specs = json.load(handle)
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


async def _open_edit_project(user, gui) -> None:
    """The Edit Project dialog for 'Home', built the way Edit Project builds it."""
    _load_configuration()
    edited = projedit.load_project_for_edit("Home", state=gui.state)
    with user.client:
        guiwins.build_edit_project_dialog(gui, edited)


async def test_the_button_sits_with_the_redact_box_in_the_project_dialog() -> None:
    """Both halves of the question asked before sharing, side by side."""
    async with _open_window() as (user, gui):
        await _open_edit_project(user, gui)

        await user.should_see(kind=ui.checkbox, content="Redact secrets")
        _button(user, "Check readiness")


async def test_pressing_it_shows_what_the_project_needs() -> None:
    async with _open_window() as (user, gui):
        await _open_edit_project(user, gui)

        _click(user, _button(user, "Check readiness"))

        await user.should_see("Readiness: Project 'Home'")
        await user.should_see("Tasker 6.3.12 or newer")
        await user.should_see("ADB Wi-Fi")
        await user.should_see("Device Admin/Owner")
        await user.should_see("Variables Tasker will ask about")


async def test_the_dialog_can_copy_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    copied: list[str] = []
    monkeypatch.setattr(ui.clipboard, "write", copied.append)

    async with _open_window() as (user, gui):
        await _open_edit_project(user, gui)
        _click(user, _button(user, "Check readiness"))
        await user.should_see("Copy as text")

        _click(user, _button(user, "Copy as text"))

    assert copied == [readiness.check_project("Home", state=PrimeItems).as_text()]


async def test_a_project_that_has_gone_is_said_not_raised() -> None:
    async with _open_window() as (user, gui):
        await _open_edit_project(user, gui)
        del PrimeItems.tasker_root_elements["all_projects"]["Home"]

        _click(user, _button(user, "Check readiness"))

        assert user.notify.contains("no longer exists")
