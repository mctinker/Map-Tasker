"""The Task Stepper dialog: pick a Task, give it variables, and read the walk.

What the walk does is test_taskstep's.  What is tested here is the dialog around it: that the Task asked for is the one
picked, that Suggest Inputs offers what the Task reads before it sets it, that a line of starting variables that cannot
be read is said and nothing is walked, that the treatment chosen for a missing variable is the one used, and that what is
drawn is what the walk found.  The dialog is the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis import taskstep
from maptasker.src.gui import guiwins_taskstep
from maptasker.src.core.primitem import PrimeItems
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_taskstep import _xml, else_, end_if, if_, set_
from tests.test_taskstep_calls import perform, returning
from tests.test_tnupdate import _load_local, _runtime  # noqa: F401  (_runtime is the fixture)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from nicegui.testing.user import User

_built: dict = {}


def _page() -> None:
    def jump(_target: object) -> Callable:
        return lambda *_args: None

    _built["dialog"] = guiwins_taskstep.build_taskstep_dialog(jump, PrimeItems, _built.get("task", ""))
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


@pytest.fixture(autouse=True)
def _reset() -> None:
    _built.clear()


def _only(user: User, label: str) -> ui.button:
    (button,) = [b for b in user.find(kind=ui.button).elements if b.text == label]
    return button


def _press(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _field(user: User, kind: type, label: str) -> ui.element:
    (element,) = [
        e for e in user.find(kind=kind).elements if getattr(e, "props", {}).get("label", "").startswith(label)
    ]
    return element


_TASKS = _xml(
    Checker=(
        if_("%limit", 7, "3"),
        set_("%r", "big"),
        else_(),
        set_("%r", "small"),
        end_if(),
    ),
    Plain=(set_("%a", "1"),),
)


@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file with Tasks has been loaded.")


@pytest.mark.asyncio
async def test_it_starts_on_the_task_it_was_opened_for_and_otherwise_the_first(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    _built["task"] = "Plain"
    async with _open() as user:
        assert _field(user, ui.select, "Task").value == "Plain"

    _built["task"] = "No Such Task"
    async with _open() as user:
        assert _field(user, ui.select, "Task").value == "Checker"


@pytest.mark.asyncio
async def test_suggest_inputs_lists_what_the_task_reads_before_it_sets_it(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    _built["task"] = "Checker"
    async with _open() as user:
        _press(user, _only(user, "Suggest Inputs"))

        assert _field(user, ui.textarea, "Starting variables").value == "%limit = "


@pytest.mark.asyncio
async def test_step_walks_the_task_with_the_variables_typed_and_draws_what_it_did(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    _built["task"] = "Checker"
    async with _open() as user:
        _field(user, ui.textarea, "Starting variables").set_value("%limit = 5")
        _press(user, _only(user, "Step"))

        await user.should_see("Finished.")
        labels = _labels(user)
        assert any("If 5 > 3 -> true" in label for label in labels)
        assert any("%r = 'big'" in label for label in labels)
        assert any(label.startswith("%r:") and "'big'" in label for label in labels), "what changed is shown"


@pytest.mark.asyncio
async def test_a_condition_on_a_missing_variable_stops_the_walk_and_names_it(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    _built["task"] = "Checker"
    async with _open() as user:
        _press(user, _only(user, "Step"))

        await user.should_see("Needs a value.")
        assert any("Needs a value for: %limit" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_the_treatment_chosen_for_a_missing_variable_is_the_one_used(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    _built["task"] = "Checker"
    async with _open() as user:
        _field(user, ui.select, "When a condition").set_value(taskstep.POLICY_TRUE)
        _press(user, _only(user, "Step"))

        await user.should_see("Finished.")
        assert any("assumed true" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_a_line_of_variables_that_cannot_be_read_is_said_and_nothing_is_walked(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    _built["task"] = "Checker"
    async with _open() as user:
        _field(user, ui.textarea, "Starting variables").set_value("this is not an assignment")
        _press(user, _only(user, "Step"))

        assert user.notify.contains("could not be read")
        assert not any("Finished" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_copy_before_any_walk_says_to_step_first(tmp_path: Path) -> None:
    _load_local(tmp_path, _TASKS)
    async with _open() as user:
        _press(user, _only(user, "Copy As Text"))

        assert user.notify.contains("Press Step first.")


@pytest.mark.asyncio
async def test_the_globals_in_the_backup_are_used_unless_the_box_is_cleared(tmp_path: Path) -> None:
    _load_local(
        tmp_path, _TASKS.replace("</TaskerData>", "<Variable sr='v0'><n>%limit</n><v>9</v></Variable></TaskerData>")
    )
    _built["task"] = "Checker"
    async with _open() as user:
        _press(user, _only(user, "Step"))
        await user.should_see("Finished.")
        assert any("If 9 > 3 -> true" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_with_the_globals_box_cleared_they_are_not_used(tmp_path: Path) -> None:
    _load_local(
        tmp_path, _TASKS.replace("</TaskerData>", "<Variable sr='v0'><n>%limit</n><v>9</v></Variable></TaskerData>")
    )
    _built["task"] = "Checker"
    async with _open() as user:
        (box,) = [b for b in user.find(kind=ui.checkbox).elements if "globals" in b.text]
        box.set_value(False)
        _press(user, _only(user, "Step"))

        await user.should_see("Needs a value.")


_CALLS = _xml(
    Caller=(perform("Callee", "5", into="%answer"), set_("%after", "%answer")),
    Callee=(set_("%x", "%par1"), returning("%x"), set_("%never", "1")),
)


@pytest.mark.asyncio
async def test_a_perform_task_is_walked_into_and_the_walk_says_where(tmp_path: Path) -> None:
    _load_local(tmp_path, _CALLS)
    _built["task"] = "Caller"
    async with _open() as user:
        _press(user, _only(user, "Step"))

        await user.should_see("Finished.")
        labels = _labels(user)
        assert "in Task 'Callee'" in labels
        assert "back in Task 'Caller'" in labels
        assert any("%answer:" in label and "'5'" in label for label in labels)


@pytest.mark.asyncio
async def test_the_actions_a_called_task_never_reached_are_listed_under_its_name(tmp_path: Path) -> None:
    _load_local(tmp_path, _CALLS)
    _built["task"] = "Caller"
    async with _open() as user:
        _press(user, _only(user, "Step"))

        await user.should_see("Never reached in Task 'Callee': 3")


@pytest.mark.asyncio
async def test_with_follow_perform_task_cleared_the_call_is_stepped_over(tmp_path: Path) -> None:
    _load_local(tmp_path, _CALLS)
    _built["task"] = "Caller"
    async with _open() as user:
        (box,) = [b for b in user.find(kind=ui.checkbox).elements if "Perform Task" in b.text]
        assert box.value is True
        box.set_value(False)
        _press(user, _only(user, "Step"))

        await user.should_see("Finished.")
        assert "in Task 'Callee'" not in _labels(user)
        assert any("not entered: following Perform Task is turned off" in label for label in _labels(user))
