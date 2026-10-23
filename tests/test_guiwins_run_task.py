"""The Run Task On Android dialog: where to run it, the two parameters, and what a run came to.

What running a Task on the device involves is devicetask's.  Here it is the dialog: the warning that the Task
really runs, the extra sentence for a name Tasker's server cannot look up, the refusal to run without an address,
the notice when the editor holds changes the device has not seen, the Run button that says it is running, and
the three outcomes shown under it -- a return value laid out as JSON, a Task that returned nothing, a Task that
could not be run.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core.primitem import RunState
from maptasker.src.device import devicetask
from maptasker.src.gui import guiwins_taskedit
from nicegui import ui

from tests.nicegui_harness import all_elements, button, click, found, inputs, label_texts, open_page

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> Any:
    record = SimpleNamespace(
        remembered=[], ran=[], result=devicetask.TaskRunResult(ok=True, output="", error="", seconds=1.25), pending=None
    )
    monkeypatch.setattr(guiwins_taskedit, "android_address_defaults", lambda gui: ("192.168.1.9", "1821"))
    monkeypatch.setattr(
        guiwins_taskedit, "remember_android_address", lambda gui, ip, port: record.remembered.append((ip, port))
    )
    monkeypatch.setattr(guiwins_taskedit, "remember_android_address_fields", lambda *a: None)

    async def io_bound(function: Any, *args: object, **kwargs: object) -> object:
        record.ran.append(args)
        return record.result

    monkeypatch.setattr(guiwins_taskedit.run, "io_bound", io_bound)
    record.window = SimpleNamespace(state=RunState())
    return record


def _dialog(record: Any, name: str = "Wake Up") -> Callable[[], None]:
    def page() -> None:
        guiwins_taskedit.build_run_task_on_android_dialog(record.window, name, record.pending)

    return page


@pytest.mark.asyncio
async def test_the_dialog_names_the_task_and_warns_that_it_really_runs(run: Any) -> None:
    async with open_page(_dialog(run)) as user:
        labels = label_texts(user)
        assert "Run Task On Android: Wake Up" in labels
        assert any(text.startswith("The Task really runs:") for text in labels)
        assert any(text.startswith("Watch your Android device: expect one or more prompts") for text in labels)
        assert not any("small helper Task" in text for text in labels)


@pytest.mark.asyncio
async def test_a_name_the_server_cannot_look_up_says_it_goes_through_a_helper(run: Any) -> None:
    async with open_page(_dialog(run, "Cost ($) + tax?")) as user:
        assert any(
            "small helper Task" in text and devicetask.RUN_TASK_HELPER_NAME in text for text in label_texts(user)
        )


@pytest.mark.asyncio
async def test_run_without_an_address_asks_for_one_and_runs_nothing(run: Any) -> None:
    async with open_page(_dialog(run)) as user:
        inputs(user)["Android IP Address"].value = ""
        await click(user, "Run")
        assert user.notify.contains("Enter the Android device's IP Address and Port.")
        assert run.ran == []


@pytest.mark.asyncio
async def test_a_run_hands_over_the_address_the_task_and_both_parameters(run: Any) -> None:
    async with open_page(_dialog(run)) as user:
        fields = inputs(user)
        fields["%par1 (optional)"].value = "one"
        fields["%par2 (optional)"].value = "two"
        await click(user, "Run")
        assert run.ran == [("192.168.1.9", "1821", "Wake Up", "one", "two")]
        assert run.remembered == [("192.168.1.9", "1821")]
        assert button(user, "Run").enabled, "Run is put back so it can be pressed again with other parameters"


@pytest.mark.asyncio
async def test_a_task_that_returned_json_shows_it_laid_out(run: Any) -> None:
    run.result = devicetask.TaskRunResult(ok=True, output='{"a": 1}', error="", seconds=2.0)
    async with open_page(_dialog(run)) as user:
        await click(user, "Run")
        labels = label_texts(user)
        assert "Task finished in 2.0s." in labels
        assert "Return value:" in labels
        (code,) = [e for e in all_elements(user) if isinstance(e, ui.code)]
        assert code.content == '{\n  "a": 1\n}'


@pytest.mark.asyncio
async def test_a_task_that_returned_nothing_says_so(run: Any) -> None:
    async with open_page(_dialog(run)) as user:
        await click(user, "Run")
        assert "The Task did not return a value." in label_texts(user)


@pytest.mark.asyncio
async def test_a_task_that_could_not_be_run_says_why_and_a_later_run_replaces_it(run: Any) -> None:
    run.result = devicetask.TaskRunResult(ok=False, output="", error="No such Task on the device.", seconds=0.1)
    async with open_page(_dialog(run)) as user:
        await click(user, "Run")
        assert "The Task could not be run." in label_texts(user)
        assert "No such Task on the device." in label_texts(user)
        run.result = devicetask.TaskRunResult(ok=True, output="", error="", seconds=0.5)
        await click(user, "Run")
        assert "The Task could not be run." not in label_texts(user), "each run fills the result area afresh"


@pytest.mark.asyncio
async def test_a_wait_that_was_cancelled_shows_no_result(run: Any) -> None:
    run.result = None
    async with open_page(_dialog(run)) as user:
        await click(user, "Run")
        assert not any(text.startswith("Task finished") for text in label_texts(user))
        assert button(user, "Run").enabled


@pytest.mark.asyncio
async def test_unsaved_edits_are_warned_about_but_the_run_still_goes_ahead(run: Any) -> None:
    run.pending = lambda: True
    async with open_page(_dialog(run)) as user:
        await click(user, "Run")
        assert user.notify.contains("This Task has unsaved edits.")
        assert run.ran, "the device simply runs the version it already has"


@pytest.mark.asyncio
async def test_with_no_unsaved_edits_there_is_no_warning(run: Any) -> None:
    run.pending = lambda: False
    async with open_page(_dialog(run)) as user:
        await click(user, "Run")
        assert not user.notify.contains("unsaved edits")


@pytest.mark.asyncio
async def test_close_closes_the_dialog(run: Any) -> None:
    async with open_page(_dialog(run)) as user:
        await click(user, "Close")
        (dialog,) = found(user, ui.dialog)
        assert not dialog.value
