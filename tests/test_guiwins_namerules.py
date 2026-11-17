"""The Naming Rules window (guiwins_namerules): the rules, the breaches drawn for the file, and renaming with a preview.

What the rules find is test_namerules'.  What is tested here is the window over it: that it opens with the saved
rules, that Check keeps them and lists what breaks them as links that jump, that Apply stays off until a preview
exists for what is ticked and goes off again when the ticks change, and that applying renames and tells the caller.
The window is the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core.mapjump import Target
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_namerules
from maptasker.src.mapops import namerules
from maptasker.src.mapops.namerules import Rules
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.nicegui_harness import idle
from tests.shared_fixtures import _load_local
from tests.test_taskstep import flash

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("_runtime")

_built: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _configuration_loaded(_runtime: Any, tmp_path: Path) -> Any:
    """Two Tasks, 'Wake Up' and 'Z Sync', loaded, with an empty undo history and no rules saved."""
    _built.clear()
    _built.update(jumps=[], refreshed=0, saved=0, save_answer=True)
    sessundo.clear(PrimeItems)
    tasks = "".join(
        f'<Task sr="task{number}" ve="2"><id>{number}</id><nme>{name}</nme>{flash("x").replace("act{}", "act0")}</Task>'
        for number, name in ((1, "Wake Up"), (2, "Z Sync"))
    )
    project = '<Project sr="proj0" ve="2"><name>Home</name><tids>1,2</tids></Project>'
    _load_local(tmp_path, f'<TaskerData sr="" dvi="1" tv="6.3.13">{project}{tasks}</TaskerData>')
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    def jump(target: Target) -> Callable[[], Any]:
        async def go() -> None:
            _built["jumps"].append(target)

        return go

    async def refresh() -> None:
        _built["refreshed"] += 1

    async def save() -> bool:
        _built["saved"] += 1
        return _built["save_answer"]

    window = guiwins_namerules.NamingRulesWindow(jump, refresh, save, PrimeItems)
    _built["window"] = window
    window.build().open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _press(user: User, label: str) -> None:
    UserInteraction(user, {b for b in user.find(kind=ui.button).elements if b.text == label}, None).click()


def _shown(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _window() -> guiwins_namerules.NamingRulesWindow:
    return _built["window"]


@pytest.mark.asyncio
async def test_it_opens_with_the_rules_that_were_saved(tmp_path: Path) -> None:
    namerules.save(Rules(task_prefix="Z ", max_task_length=40))

    async with _open():
        assert _window().fields["task_prefix"].value == "Z "
        assert _window().fields["max_task_length"].value == 40


@pytest.mark.asyncio
async def test_check_keeps_the_rules_and_lists_what_breaks_them_as_links_that_jump() -> None:
    async with _open() as user:
        _window().fields["task_prefix"].set_value("Z ")

        _press(user, "Check")
        await idle()

        assert namerules.load().task_prefix == "Z ", "a trailing space is part of the prefix"
        link = next(element for element in user.find(kind=ui.link).elements if "Wake Up" in element.text)
        UserInteraction(user, {link}, None).click()
        await idle()
        assert [target.key for target in _built["jumps"]] == ["1"]
        assert not any("Z Sync" in element.text for element in user.find(kind=ui.link).elements)


@pytest.mark.asyncio
async def test_with_no_rule_set_check_says_so() -> None:
    async with _open() as user:
        _press(user, "Check")

        assert user.notify.contains("No rule has been set")


@pytest.mark.asyncio
async def test_apply_is_off_until_a_preview_exists_and_off_again_when_the_ticks_change() -> None:
    async with _open() as user:
        _window().fields["task_prefix"].set_value("Z ")
        _press(user, "Check")
        window = _window()
        assert not window.apply_button.enabled

        window.table.selected = list(window.table.rows)
        _press(user, "Preview")
        assert window.apply_button.enabled

        window.table.selected = []
        window.invalidate()
        assert not window.apply_button.enabled


@pytest.mark.asyncio
async def test_preview_with_nothing_ticked_asks_for_a_tick_and_changes_nothing() -> None:
    async with _open() as user:
        _window().fields["task_prefix"].set_value("Z ")
        _press(user, "Check")

        _press(user, "Preview")

        assert user.notify.contains("Tick the names to change first")
        assert PrimeItems.tasker_root_elements["all_tasks"]["1"]["name"] == "Wake Up"


@pytest.mark.asyncio
async def test_apply_renames_what_was_previewed_and_tells_the_caller() -> None:
    async with _open() as user:
        _window().fields["task_prefix"].set_value("Z ")
        _press(user, "Check")
        window = _window()
        window.table.selected = list(window.table.rows)
        _press(user, "Preview")

        _press(user, "Apply")
        await idle()

        assert PrimeItems.tasker_root_elements["all_tasks"]["1"]["name"] == "Z Wake Up"
        assert _built["refreshed"] == 1
        assert window.breaches == [], "the check is run again, and nothing breaks the rule now"


@pytest.mark.asyncio
async def test_clear_rules_turns_every_rule_off() -> None:
    namerules.save(Rules(task_prefix="Z ", no_default_names=True, label_after=5))

    async with _open() as user:
        _press(user, "Clear Rules")

        assert _window().read_rules() == Rules()


@pytest.mark.asyncio
async def test_save_report_says_where_the_report_went(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(namerules, "write_report", lambda rows, state: "/out/MapTasker_NamingRules.txt")
    async with _open() as user:
        _press(user, "Save Report")

        assert user.notify.contains("Report saved as")


@pytest.mark.asyncio
async def test_close_closes_the_window() -> None:
    async with _open() as user:
        dialog = _window().dialog
        assert dialog.value

        _press(user, "Close")

        assert not dialog.value


@pytest.mark.asyncio
async def test_save_to_current_file_saves_and_reads_the_file_against_the_rules_again() -> None:
    async with _open() as user:
        _window().fields["task_prefix"].set_value("Z ")
        _press(user, "Check")
        assert len(_window().breaches) == 1
        PrimeItems.tasker_root_elements["all_tasks"]["1"]["xml"].find("nme").text = "Z Wake Up"

        _press(user, "Save To Current File")
        await idle()

        assert _built["saved"] == 1
        assert _window().breaches == [], "what the window holds is read again after the save"


@pytest.mark.asyncio
async def test_save_that_did_not_happen_leaves_the_window_as_it_was() -> None:
    _built["save_answer"] = False
    async with _open() as user:
        _window().fields["task_prefix"].set_value("Z ")
        _press(user, "Check")
        held = _window().breaches

        _press(user, "Save To Current File")
        await idle()

        assert _built["saved"] == 1
        assert _window().breaches is held
