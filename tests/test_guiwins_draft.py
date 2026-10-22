"""The Add Task dialog's "Draft with AI" row: a description in, unsaved actions out.

What a draft IS is test_mapdraft's.  What is tested here is the dialog around it: that the
draft lands in the dialog's own working copy and nowhere else, that what was left out of it
is on screen beside it, that a question the dialog no longer wants is taken back, and that
nothing is asked of the model with no description or no model chosen.

The real dialog, on a page of NiceGUI's in-process user simulation; the model is a function.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.analysis import mapask
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import taskedit
from maptasker.src.gui import guiwins_draft, guiwins_taskedit
from maptasker.src.mapops import mapdraft
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_mapswap import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

_SETTINGS = mapask.ModelSettings(mapask.ANTHROPIC, "claude-sonnet-5", "test-key")
_built: dict = {}


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture backup loaded, an AI model chosen, and a model that has not been asked."""
    _load(_FIXTURE_XML)
    _built.clear()
    _built.update(asked=[], draft=mapdraft.Draft("", ()), settings_error=None, wait=None)
    monkeypatch.setattr(guiwins_draft.mapask, "model_settings", _model_settings)
    monkeypatch.setattr(guiwins_draft.mapdraft, "draft_task", _draft_task)


def _model_settings(*_: object, **__: object) -> mapask.ModelSettings:
    if _built["settings_error"]:
        raise mapask.AskError(_built["settings_error"])
    return _SETTINGS


async def _draft_task(description: str, settings: mapask.ModelSettings, state: object) -> mapdraft.Draft:
    _built["asked"].append(description)
    if _built["wait"] is not None:
        try:
            await _built["wait"]()
        except asyncio.CancelledError:
            _built["cancelled"] = True
            raise
    return _built["draft"]


def _page() -> None:
    gui = MagicMock()
    gui.state = PrimeItems
    gui.indent = 4
    gui.event_handlers.editors.add_action_to_new_task_event.side_effect = lambda task, key, pos: (
        taskedit.add_action_to_task(task, key, pos, state=PrimeItems).act_number
    )
    task = taskedit.create_new_task("", "100", state=PrimeItems)
    _built["task"] = task
    guiwins_taskedit.build_add_task_dialog(gui, task)


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, label: str) -> ui.button:
    (button,) = [element for element in user.find(kind=ui.button).elements if element.text == label]
    return button


def _shown(user: User, label: str) -> bool:
    """Whether a button of this label is on screen: the finder looks only at what is visible."""
    return any(element.text == label for element in user.find(kind=ui.button).elements)


def _press(user: User, label: str) -> None:
    UserInteraction(user, {_button(user, label)}, None).click()


def _description(user: User) -> ui.input:
    return next(
        element for element in user.find(kind=ui.input).elements if element._props.get("label") == "Draft with AI"
    )


def _name(user: User) -> ui.input:
    return next(element for element in user.find(kind=ui.input).elements if element._props.get("label") == "Task Name")


def _listed(user: User) -> list[str]:
    """The headers of the actions in the Task, as the list shows them (none, before there are any)."""
    try:
        elements = user.find(kind=ui.expansion).elements
    except AssertionError:
        return []
    return [str(element._props.get("label", "")) for element in elements]


def _notes(user: User) -> str:
    return next(
        element.text
        for element in user.find(kind=ui.label).elements
        if "border-orange-400" in " ".join(element._classes)
    )


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(40):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


@pytest.mark.asyncio
async def test_a_draft_is_added_to_the_dialogs_task_unsaved() -> None:
    _built["draft"] = mapdraft.Draft(
        "Say hello",
        (
            mapdraft.DraftStep("548t", "greet", {"0": "Hello"}),
            mapdraft.DraftStep("30t", "", {"1": "5"}),
        ),
    )
    async with _open() as user:
        _description(user).value = "say hello then wait five seconds"
        _press(user, "Draft")
        await _until(lambda: len(_listed(user)) == 2)

        assert _built["asked"] == ["say hello then wait five seconds"]
        # By the number each header starts with: the finder does not promise an order.
        listed = {int(header.split(": ")[0]): header.split(": ")[1].split("  ")[0] for header in _listed(user)}
        assert listed == {0: "Flash", 1: "Wait"}
        # The first drafted action is the one the list highlights, as for one added by hand.
        assert sum("just added" in header for header in _listed(user)) == 1
        assert next(header for header in _listed(user) if header.startswith("0:")).endswith("just added")
        assert _name(user).value == "Say hello"

        task = _built["task"]
        assert [action.action_name for action in task.actions] == ["Flash", "Wait"]
        assert task.actions[0].action_element.find("Str[@sr='arg0']").text == "Hello"
        # Nothing was kept: the Task is the dialog's copy, and no table has it.
        assert task.task_id not in PrimeItems.tasker_root_elements["all_tasks"]
        assert "Say hello" not in PrimeItems.tasker_root_elements["all_tasks_by_name"]
        assert any("Nothing is saved" in message for message in user.notify.messages)


@pytest.mark.asyncio
async def test_a_name_already_typed_is_kept() -> None:
    _built["draft"] = mapdraft.Draft("Drafted name", (mapdraft.DraftStep("548t"),))
    async with _open() as user:
        _name(user).value = "Mine"
        _description(user).value = "flash"
        _press(user, "Draft")
        await _until(lambda: len(_listed(user)) == 1)

        assert _name(user).value == "Mine"


@pytest.mark.asyncio
async def test_a_name_another_task_has_is_not_used_and_is_said() -> None:
    _built["draft"] = mapdraft.Draft("Noisy", (mapdraft.DraftStep("548t"),))
    async with _open() as user:
        _description(user).value = "flash"
        _press(user, "Draft")
        await _until(lambda: len(_listed(user)) == 1)

        assert _name(user).value == ""
        assert "Noisy" in _notes(user)
        assert "already" in _notes(user)


@pytest.mark.asyncio
async def test_what_was_left_out_is_on_screen_beside_the_draft() -> None:
    _built["draft"] = mapdraft.Draft(
        "",
        (mapdraft.DraftStep("548t"),),
        unknown=("Teleport",),
        dropped=("Step 1 (Flash): 'Long' left at its default, because 'maybe' is not true or false.",),
        adjusted=("Added the End If that closes an If.",),
        unexpressed="'When I get home' is a Profile.",
    )
    async with _open() as user:
        _description(user).value = "flash when I get home"
        _press(user, "Draft")
        await _until(lambda: len(_listed(user)) == 1)

        notes = _notes(user)
        for part in ("Teleport", "End If", "'maybe'", "'When I get home' is a Profile."):
            assert part in notes


@pytest.mark.asyncio
async def test_a_draft_with_nothing_in_it_says_so_and_adds_nothing() -> None:
    _built["draft"] = mapdraft.Draft("", (), unknown=("Teleport",), unexpressed="Nothing does that.")
    async with _open() as user:
        _description(user).value = "teleport me"
        _press(user, "Draft")
        await _until(lambda: user.notify.contains("Nothing could be drafted"))

        assert _listed(user) == []
        assert "Teleport" in _notes(user)


@pytest.mark.asyncio
async def test_nothing_is_asked_without_a_description() -> None:
    async with _open() as user:
        _press(user, "Draft")
        await _until(lambda: user.notify.contains("Describe the Task first."))

        assert _built["asked"] == []


@pytest.mark.asyncio
async def test_nothing_is_asked_when_no_model_is_chosen() -> None:
    _built["settings_error"] = "No AI model is selected.  Choose one on the Analyze tab first."
    async with _open() as user:
        _description(user).value = "flash hello"
        _press(user, "Draft")
        await _until(lambda: user.notify.contains("No AI model is selected."))

        assert _built["asked"] == []
        assert _listed(user) == []


@pytest.mark.asyncio
async def test_a_failing_model_is_said_and_adds_nothing() -> None:
    async def failing() -> None:
        message = "invalid x-api-key"
        raise mapask.AskError(message)

    _built["wait"] = failing
    async with _open() as user:
        _description(user).value = "flash hello"
        _press(user, "Draft")
        await _until(lambda: user.notify.contains("invalid x-api-key"))

        assert _listed(user) == []
        assert "loading" not in _button(user, "Draft")._props


@pytest.mark.asyncio
async def test_closing_the_dialog_takes_the_question_back() -> None:
    started = asyncio.Event()

    async def waiting() -> None:
        started.set()
        await asyncio.sleep(3600)

    _built["wait"] = waiting
    async with _open() as user:
        _description(user).value = "flash hello"
        _press(user, "Draft")
        await started.wait()
        assert "loading" in _button(user, "Draft")._props

        _press(user, "Cancel")
        await _until(lambda: _built.get("cancelled"))

        assert _listed(user) == []


@pytest.mark.asyncio
async def test_asking_again_replaces_the_question_still_out() -> None:
    started = asyncio.Event()
    calls = []

    async def waiting() -> None:
        calls.append(1)
        started.set()
        if len(calls) == 1:
            await asyncio.sleep(3600)

    _built["wait"] = waiting
    _built["draft"] = mapdraft.Draft("", (mapdraft.DraftStep("548t"),))
    async with _open() as user:
        _description(user).value = "first"
        _press(user, "Draft")
        await started.wait()
        started.clear()
        _description(user).value = "second"
        _press(user, "Draft")
        await _until(lambda: len(_listed(user)) == 1)

        assert _built["asked"] == ["first", "second"]
        assert _built["cancelled"]


@pytest.mark.asyncio
async def test_a_slow_question_says_so_and_can_be_stopped() -> None:
    started = asyncio.Event()

    async def waiting() -> None:
        started.set()
        await asyncio.sleep(3600)

    _built["wait"] = waiting
    async with _open() as user:
        _description(user).value = "flash hello"
        assert not _shown(user, "Stop")
        _press(user, "Draft")
        await started.wait()

        assert _shown(user, "Stop")
        assert any("Asking Anthropic (claude-sonnet-5)" in label.text for label in user.find(kind=ui.label).elements)

        _press(user, "Stop")
        await _until(lambda: _built.get("cancelled"))
        await _until(lambda: not _shown(user, "Stop"))

        assert _listed(user) == []
        assert "loading" not in _button(user, "Draft")._props
