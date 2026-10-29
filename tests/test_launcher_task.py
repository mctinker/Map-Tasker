"""A Project's launcher Task: the <Share><t> that names it, the pulldown that sets it, and what an Undo does.

The launcher Task is the one Task a Project's launcher runs.  Tasker keeps it as the Task's NAME in <t>, inside the same <Share> that
holds a TaskerNet description, and MapTasker's Map already prints it on the Project's line.  What is tested is that it is written
where and as Tasker writes it, that setting or clearing it never disturbs the description beside it, that the pulldown offers
exactly the Project's own named Tasks -- and keeps a launcher it does not recognise rather than quietly replacing it -- and that a
pick reaches the live Project at once, with one Undo.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import cast
from unittest.mock import MagicMock

import pytest
from maptasker.src.core import tndesc
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import projedit, sessundo
from maptasker.src.gui import guiwins_project
from maptasker.src.gui.userintr import MapTaskerEventHandlers
from maptasker.src.mapgen import projects
from nicegui import ui

from tests.nicegui_harness import found, open_page
from tests.test_mapswap import _load

_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids></pids>
    <tids>20,21,23,24,25,99</tids>
    <mdate>1</mdate>
    <Img sr="Img"/>
  </Project>
  <Project sr="proj1" ve="2">
    <name>Work</name>
    <tids>22</tids>
    <Share sr="Share"><b>false</b><d>Work stuff</d><g>Basics</g><p>true</p><t>Elsewhere</t></Share>
  </Project>
  <Task sr="task20" ve="2"><id>20</id><nme>zeta</nme></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Alpha</nme></Task>
  <Task sr="task22" ve="2"><id>22</id><nme>Elsewhere</nme></Task>
  <Task sr="task23" ve="2"><id>23</id></Task>
  <Task sr="task24" ve="2"><id>24</id><nme>ALPHA</nme></Task>
  <Task sr="task25" ve="2"><id>25</id><nme>  </nme></Task>
</TaskerData>"""


@pytest.fixture(autouse=True)
def _configuration() -> None:
    _load(_XML)


def project(name: str = "Home") -> ET.Element:
    element = projedit.resolve_project_by_name(name, state=PrimeItems)
    assert element is not None
    return element


def children(element: ET.Element) -> list[str]:
    return [child.tag for child in element]


# ##################################################################################
# The element
# ##################################################################################
def test_a_launcher_task_is_written_into_a_new_share_where_tasker_puts_it() -> None:
    home = project()

    tndesc.set_launcher_task(home, "Alpha")

    assert children(home) == ["name", "pids", "tids", "mdate", "Share", "Img"]
    share = home.find("Share")
    assert share is not None
    assert [(child.tag, child.text) for child in share] == [("b", "false"), ("d", ""), ("p", "false"), ("t", "Alpha")]
    assert tndesc.launcher_task_of(home) == "Alpha"


def test_the_map_prints_the_launcher_task_that_was_set() -> None:
    home = project()

    tndesc.set_launcher_task(home, "Alpha")

    assert "[Launcher Task: Alpha]" in projects.get_launcher_task(home, "Home")


def test_changing_the_launcher_leaves_the_description_the_tags_and_the_flags_alone() -> None:
    work = project("Work")

    tndesc.set_launcher_task(work, "Zeta")

    share = work.find("Share")
    assert share is not None
    assert [(child.tag, child.text) for child in share] == [
        ("b", "false"),
        ("d", "Work stuff"),
        ("g", "Basics"),
        ("p", "true"),
        ("t", "Zeta"),
    ]


def test_taking_the_launcher_away_puts_the_project_back_as_it_was() -> None:
    home = project()
    before = ET.tostring(home)
    tndesc.set_launcher_task(home, "Alpha")

    tndesc.set_launcher_task(home, "")

    assert ET.tostring(home) == before


def test_taking_the_launcher_away_keeps_a_share_that_still_has_a_description() -> None:
    work = project("Work")

    tndesc.set_launcher_task(work, "")

    assert tndesc.launcher_task_of(work) == ""
    assert tndesc.description_of(work) == "Work stuff"
    assert "[Launcher Task" not in projects.get_launcher_task(work, "Work")


def test_clearing_the_description_keeps_the_launcher_and_its_share() -> None:
    home = project()
    tndesc.set_description(home, "About Home")
    tndesc.set_launcher_task(home, "Alpha")

    tndesc.set_description(home, "")

    assert tndesc.launcher_task_of(home) == "Alpha"
    assert home.find("Share") is not None


def test_a_description_added_later_does_not_disturb_the_launcher() -> None:
    home = project()
    tndesc.set_launcher_task(home, "Alpha")

    tndesc.set_description(home, "About Home")

    assert tndesc.launcher_task_of(home) == "Alpha"
    assert tndesc.description_of(home) == "About Home"


def test_a_project_with_no_launcher_says_so() -> None:
    assert tndesc.launcher_task_of(project()) == ""
    assert tndesc.launcher_task_of(ET.fromstring("<Project><Share><d>x</d></Share></Project>")) == ""


# ##################################################################################
# What the pulldown offers, and what a pick does
# ##################################################################################
def test_only_the_projects_own_named_tasks_are_offered_once_each_and_in_order() -> None:
    names = projedit.named_tasks_of(project(), state=PrimeItems)

    assert names == ["Alpha", "zeta"], "no unnamed Task, no blank name, no duplicate, no id missing from the file"
    assert projedit.named_tasks_of(project("Work"), state=PrimeItems) == ["Elsewhere"]


def test_a_pick_reaches_the_live_project_and_the_copy_and_one_undo_takes_it_back() -> None:
    edited = projedit.load_project_for_edit("Home", state=PrimeItems)
    assert edited is not None

    projedit.set_project_launcher(edited, "Alpha", state=PrimeItems)

    assert tndesc.launcher_task_of(edited.project_element) == "Alpha"
    assert tndesc.launcher_task_of(project()) == "Alpha"
    assert project().findtext("mdate") != "1", "a modification stamps the Project"

    sessundo.undo(state=PrimeItems)
    assert tndesc.launcher_task_of(project()) == ""
    assert project().find("Share") is None


# ##################################################################################
# The pulldown in Edit Project
# ##################################################################################
def _gui() -> MagicMock:
    window = MagicMock()
    window.state = PrimeItems
    window.event_handlers = MapTaskerEventHandlers(window)
    return window


def _edit(name: str):
    def page() -> None:
        edited = projedit.load_project_for_edit(name, state=PrimeItems)
        assert edited is not None
        guiwins_project.build_edit_project_dialog(_gui(), edited)

    return page


def _options(select: ui.select) -> dict[str, str]:
    """The pulldown's options by value: the Launcher Task one is built from a dict."""
    return cast("dict[str, str]", select.options)


def _launcher(user) -> ui.select:
    (select,) = [s for s in found(user, ui.select) if s.props.get("label") == "Launcher Task"]
    return select


@pytest.mark.asyncio
async def test_the_pulldown_lists_none_and_the_projects_named_tasks() -> None:
    async with open_page(_edit("Home")) as user:
        select = _launcher(user)

        assert list(select.options) == ["", "Alpha", "zeta"]
        assert _options(select)[""] == "(none)"
        assert select.value == ""


@pytest.mark.asyncio
async def test_a_launcher_the_project_already_names_is_what_the_pulldown_starts_on() -> None:
    tndesc.set_launcher_task(project(), "zeta")

    async with open_page(_edit("Home")) as user:
        assert _launcher(user).value == "zeta"


@pytest.mark.asyncio
async def test_a_launcher_that_is_not_one_of_the_projects_tasks_is_shown_as_such_not_replaced() -> None:
    async with open_page(_edit("Work")) as user:
        select = _launcher(user)

        assert select.value == "Elsewhere", "Elsewhere IS a Work Task here, so it is listed plainly"

    tndesc.set_launcher_task(project("Work"), "Gone")
    async with open_page(_edit("Work")) as user:
        select = _launcher(user)

        assert select.value == "Gone"
        assert _options(select)["Gone"].startswith("Gone")
        assert "not one of this Project's Tasks" in _options(select)["Gone"]
        assert tndesc.launcher_task_of(project("Work")) == "Gone", "opening the dialog changes nothing"


@pytest.mark.asyncio
async def test_picking_a_task_sets_it_on_the_live_project_at_once_and_says_so() -> None:
    async with open_page(_edit("Home")) as user:
        _launcher(user).set_value("Alpha")

        assert tndesc.launcher_task_of(project()) == "Alpha"
        assert user.notify.contains("Launcher Task set to 'Alpha'.")


@pytest.mark.asyncio
async def test_picking_none_takes_the_launcher_away() -> None:
    tndesc.set_launcher_task(project(), "zeta")

    async with open_page(_edit("Home")) as user:
        _launcher(user).set_value("")

        assert tndesc.launcher_task_of(project()) == ""
        assert user.notify.contains("Launcher Task removed.")


@pytest.mark.asyncio
async def test_the_pulldown_and_the_description_editor_work_on_one_share() -> None:
    edited_holder: dict[str, projedit.EditableProject] = {}

    def page() -> None:
        edited = projedit.load_project_for_edit("Home", state=PrimeItems)
        assert edited is not None
        edited_holder["project"] = edited
        guiwins_project.build_edit_project_dialog(_gui(), edited)

    async with open_page(page) as user:
        _launcher(user).set_value("Alpha")
        projedit_share = edited_holder["project"].project_element.find("Share")
        assert projedit_share is not None

        tndesc.set_description(edited_holder["project"].project_element, "About Home")
        projedit.apply_share_to_live_tree(edited_holder["project"], state=PrimeItems)

    assert tndesc.launcher_task_of(project()) == "Alpha"
    assert tndesc.description_of(project()) == "About Home"


@pytest.mark.asyncio
async def test_add_project_has_no_launcher_pulldown_because_a_new_project_has_no_tasks() -> None:
    def page() -> None:
        created = projedit.create_new_project("", state=PrimeItems)
        assert not isinstance(created, str)
        guiwins_project.build_add_project_dialog(_gui(), created)

    async with open_page(page) as user:
        assert not [s for s in found(user, ui.select) if s.props.get("label") == "Launcher Task"]
