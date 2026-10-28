"""The Import With Dependencies button's handler: pick a file, read it, open the dialog -- and the ways it stops.

What the dialog does is test_guiwins_carry's and what an import does is test_mapcarry's.  Here it is only
what happens between pressing the button and the dialog opening: that nothing is asked of a configuration
that is not there, that the file already open is not offered back to itself, that a file that will not read
says so instead of opening an empty dialog, and that reading another file waits for a Map being built ahead
of time, whose tables it would otherwise borrow.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maptasker.src.gui import userintr_carry
from maptasker.src.gui.userintr import MapTaskerEventHandlers


def _handlers(*, loaded: bool = True) -> MapTaskerEventHandlers:
    window = MagicMock()
    window.state = SimpleNamespace(
        tasker_root_elements={"all_tasks": {"1": {}} if loaded else {}, "all_projects": {}},
        file_to_get="/work/current.xml",
    )
    window.carry_dialog = None
    handlers = MapTaskerEventHandlers(window)
    handlers.save_whole_configuration = AsyncMock(return_value=True)  # type: ignore[method-assign]
    return handlers


def _patched(
    *, picked: object = ("/other/tablet.xml",), source: object = "SOURCE", problem: str = "", dialog: object = None
):
    """Everything the handler reaches for outside itself: the picker, the reader, the dialog builder."""
    dialog = MagicMock() if dialog is None else dialog
    return (
        patch.object(userintr_carry, "LocalFilePicker", AsyncMock(return_value=picked)),
        patch.object(userintr_carry, "local_xml_start_directory", lambda gui: "/start"),
        patch.object(userintr_carry, "load_for_comparison", MagicMock(return_value=(source, problem))),
        patch.object(userintr_carry, "build_carry_dialog", MagicMock(return_value=dialog)),
        patch.object(userintr_carry, "ui"),
    )


def _message_box(handlers: MapTaskerEventHandlers) -> MagicMock:
    """The window's message box, which is a mock here."""
    return cast("MagicMock", handlers.gui.display_message_box)


async def _press(handlers: MapTaskerEventHandlers, **options: Any) -> SimpleNamespace:
    """Press the button with everything outside the handler patched; return what was patched."""
    picker, start, reader, builder, ui = _patched(**options)  # type: ignore[arg-type]
    with picker as picked, start, reader as read, builder as built, ui:
        await handlers.carry.import_with_dependencies_event()
    return SimpleNamespace(picker=picked, read=read, built=built)


@pytest.mark.asyncio
async def test_with_nothing_loaded_nothing_is_asked() -> None:
    handlers = _handlers(loaded=False)

    seen = await _press(handlers)

    seen.picker.assert_not_awaited()
    message_box = _message_box(handlers)
    message_box.assert_called_once()
    assert "No XML file has been loaded" in message_box.call_args.args[0]


@pytest.mark.asyncio
async def test_backing_out_of_the_picker_opens_nothing() -> None:
    handlers = _handlers()

    seen = await _press(handlers, picked=[])

    seen.read.assert_not_called()
    seen.built.assert_not_called()


@pytest.mark.asyncio
async def test_the_file_already_loaded_is_not_offered_back_to_itself() -> None:
    handlers = _handlers()

    with patch.object(userintr_carry, "loaded_file_path", lambda state: "/work/current.xml"):
        seen = await _press(handlers, picked=("/work/current.xml",))

    seen.read.assert_not_called()
    assert "already loaded" in _message_box(handlers).call_args.args[0]


@pytest.mark.asyncio
async def test_a_file_that_will_not_read_says_why_and_opens_no_dialog() -> None:
    handlers = _handlers()

    seen = await _press(handlers, source=None, problem="tablet.xml is not a Tasker backup file.")

    seen.built.assert_not_called()
    _message_box(handlers).assert_called_once_with("tablet.xml is not a Tasker backup file.", "Red")


@pytest.mark.asyncio
async def test_a_file_that_reads_opens_the_dialog_on_it() -> None:
    handlers = _handlers()
    dialog = MagicMock()

    seen = await _press(handlers, dialog=dialog)

    assert seen.built.call_args.args[0] == "SOURCE"
    dialog.open.assert_called_once()
    assert handlers.gui.carry_dialog is dialog


@pytest.mark.asyncio
async def test_a_dialog_still_up_is_taken_down_first() -> None:
    handlers = _handlers()
    old = MagicMock()
    handlers.gui.carry_dialog = old

    await _press(handlers)

    old.delete.assert_called_once()


@pytest.mark.asyncio
async def test_a_dialog_that_could_not_be_built_is_not_opened_or_remembered() -> None:
    handlers = _handlers()
    nothing = MagicMock()
    picker, start, reader, _builder, ui = _patched()
    with picker, start, reader, ui, patch.object(userintr_carry, "build_carry_dialog", MagicMock(return_value=None)):
        await handlers.carry.import_with_dependencies_event()

    assert handlers.gui.carry_dialog is None
    nothing.open.assert_not_called()


@pytest.mark.asyncio
async def test_another_file_is_not_read_while_a_map_is_being_built_ahead_of_time() -> None:
    """Reading one borrows the program's tables, which a Map being built on another thread is reading."""
    handlers = _handlers()
    release = asyncio.Event()
    order: list[str] = []

    async def prebuilding() -> None:
        await release.wait()
        order.append("the build finished")

    from maptasker.src.gui import userintr_prebuild

    userintr_prebuild._building.task = asyncio.create_task(prebuilding())
    picker, start, reader, builder, ui = _patched()
    try:
        with picker, start, reader as read, builder, ui:
            read.side_effect = lambda *_a, **_k: (order.append("the file was read"), ("SOURCE", ""))[1]
            press = asyncio.create_task(handlers.carry.import_with_dependencies_event())
            await asyncio.sleep(0.02)
            assert order == []
            release.set()
            await press
    finally:
        userintr_prebuild._building.task = None

    assert order == ["the build finished", "the file was read"]
