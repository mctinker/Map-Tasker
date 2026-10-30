"""The requirements block of a TaskerNet description (readiness.Readiness.as_html and readiness.check_element)

What the Check Readiness report says is tested in test_readiness; here it is the same report written as the block a
description carries, and the ways of reading a Project, Profile or Task for it.  The block has to be safe to paste (a
Task's name is whatever its author typed), made of tags the description editor itself writes, leave out what is empty,
and be found again by the markers tndesc looks for -- and a Profile has to be read with the Tasks it runs.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET

import pytest
from maptasker.src.core import tndesc
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import projedit
from maptasker.src.mapops import readiness

from tests.test_mapswap import _load
from tests.test_readiness import _action, _int, _plugin_action, _task, _variable
from tests.test_readiness import _check as check


def _html(*children: str) -> str:
    return check(*children).as_html()


# ##################################################################################
# The block
# ##################################################################################
def test_the_block_starts_and_ends_with_the_markers_tndesc_finds_it_by() -> None:
    block = _html(_task("Quit", _action(375)))

    assert block.startswith(tndesc.REQUIREMENTS_START)
    assert block.endswith(tndesc.REQUIREMENTS_END)
    assert tndesc.split_requirements(f"Intro.\n\n{block}") == ("Intro.", block)


def test_the_block_is_made_of_tags_the_editor_writes_and_checks_clean() -> None:
    block = _html(
        _task("Click", _plugin_action("com.joaomgcd.autoinput"), _action(375)),
        '<Project sr="proj0"><name>Home</name>' + _variable("%Key", configure="true", prompt="Your key") + "</Project>",
    )

    assert "<b>Variables Tasker will ask about</b>" in block

    assert tndesc.check(block) == []


def test_a_section_with_nothing_in_it_is_left_out_not_printed_as_none() -> None:
    block = _html(_task("Click", _plugin_action("com.joaomgcd.autoinput")))

    assert "<b>Plugins</b>" in block
    assert "<b>Apps</b>" not in block
    assert "<b>Special access</b>" not in block
    assert "No plugins are used" not in block


def test_special_access_says_how_to_set_it_up() -> None:
    block = _html(_task("Shell", _action(123, _int(2, 1))))

    assert "<b>Special access</b>" in block
    assert "Root" in block
    assert "rooted" in block, "the how-to the recipient needs, not just the name of the access"


def test_a_file_that_needs_nothing_says_so_in_a_line_and_still_has_the_fine_print() -> None:
    block = _html(_task("Plain", _action(548)))

    assert "No plugin, app or special access was found in this file." in block
    assert "<b>Plugins</b>" not in block
    assert "not known to need nothing" in block, "'found nothing' is not 'needs nothing', and the block says so"


def test_whatever_an_author_typed_is_escaped() -> None:
    block = _html(_task("&lt;script&gt;x()&lt;/script&gt; &amp; &lt;b&gt;", _plugin_action("com.example.plugin")))

    assert "<script>" not in block
    assert "&lt;script&gt;" in block
    assert "&amp;" in block
    assert tndesc.check(block) == []


def test_the_minimum_tasker_version_is_there_when_one_is_known() -> None:
    block = _html(_task("Quit", _action(375)))  # ADB Wifi came in with Tasker 5.9.2

    assert "<b>Tasker version</b>" in block
    assert "Tasker 5.9.2 or newer" in block


# ##################################################################################
# Reading an element
# ##################################################################################
_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><pids>10</pids><tids>1,2</tids></Project>
  <Profile sr="prof10" ve="2"><id>10</id><nme>At Home</nme><mid0>1</mid0><mid1>2</mid1></Profile>
  <Task sr="task1" ve="2"><id>1</id><nme>Enter</nme><Action sr="act0" ve="7"><code>375</code></Action></Task>
  <Task sr="task2" ve="2"><id>2</id><nme>Leave</nme><Action sr="act0" ve="7"><code>379</code></Action></Task>
</TaskerData>"""


@pytest.fixture
def home() -> None:
    _load(_XML)


def _element(kind: str, name: str):
    tables = {"Project": "all_projects", "Profile": "all_profiles", "Task": "all_tasks"}
    for entry in PrimeItems.tasker_root_elements[tables[kind]].values():
        if entry["name"] == name:
            return entry["xml"]
    raise LookupError(name)


@pytest.mark.usefixtures("home")
def test_a_task_is_read_alone_as_its_own_export_is() -> None:
    report = readiness.check_element("Task", _element("Task", "Enter"), "Enter", PrimeItems)

    assert [need.any_of for need in report.access] == [("adb_wifi",)]
    assert report.scope == "Task 'Enter'"


@pytest.mark.usefixtures("home")
def test_a_profile_is_read_with_the_tasks_it_runs() -> None:
    report = readiness.check_element("Profile", _element("Profile", "At Home"), "At Home", PrimeItems)

    assert {need.any_of for need in report.access} == {("adb_wifi",), ("device_owner",)}, "Enter's and Leave's"


@pytest.mark.usefixtures("home")
def test_a_loaded_project_is_read_as_its_export_would_be() -> None:
    report = readiness.check_element("Project", _element("Project", "Home"), "Home", PrimeItems)

    assert {need.any_of for need in report.access} == {("adb_wifi",), ("device_owner",)}
    assert report.scope == "Project 'Home'"


@pytest.mark.usefixtures("home")
def test_a_project_not_loaded_yet_is_read_from_the_copy_it_is_given() -> None:
    created = projedit.create_new_project("", state=PrimeItems)
    assert not isinstance(created, str)

    report = readiness.check_element("Project", created.project_element, "", PrimeItems)

    assert report.scope == "Project"
    assert report.needs_nothing


@pytest.mark.usefixtures("home")
def test_what_is_read_is_what_is_on_screen_not_what_is_saved() -> None:
    """The editor's working copy may hold an action that has not been kept yet; that is what is described."""
    working = copy.deepcopy(_element("Task", "Enter"))
    working.append(ET.fromstring('<Action sr="act1" ve="7"><code>379</code></Action>'))

    report = readiness.check_element("Task", working, "Enter", PrimeItems)

    assert {need.any_of for need in report.access} == {("adb_wifi",), ("device_owner",)}
    assert [
        need.any_of for need in readiness.check_element("Task", _element("Task", "Enter"), "Enter", PrimeItems).access
    ] == [("adb_wifi",)]
