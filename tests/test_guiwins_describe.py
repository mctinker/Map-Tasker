"""The two ways the TaskerNet Description editor helps fill itself in: Insert Requirements and Draft with AI.

Insert Requirements puts what an object needs on another phone into the box as a block that a second press replaces.
Draft with AI asks the model chosen on the Analyze tab, and what is tested is the dialog's side of it: that what will be
sent can be read, word for word, before anything is sent; that a draft replaces the author's words but never the
requirements block, and can be taken back; and that a question can be given up on, fails in words, or is refused when
there is nothing to describe.  The model is a function standing in, and the dialog is the real one on a page of
NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from maptasker.src.analysis import mapask
from maptasker.src.core import tndesc
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiwins_describe, guiwins_tndesc
from maptasker.src.gui.userintr import MapTaskerEventHandlers
from maptasker.src.mapops import mapdescribe
from nicegui import ui

from tests.nicegui_harness import button, click, found, open_page
from tests.test_mapdescribe import _XML, element
from tests.test_mapswap import _load

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from nicegui.testing.user import User

SETTINGS = mapask.ModelSettings(mapask.OPENAI, "gpt-test", "key")


@pytest.fixture(autouse=True)
def _configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    _load(_XML)
    PrimeItems.colors_to_use = set_color_mode("light")
    monkeypatch.setattr(guiwins_describe.mapask, "model_settings", lambda *_a, **_k: SETTINGS)


def _gui() -> MagicMock:
    window = MagicMock()
    window.state = PrimeItems
    window.event_handlers = MapTaskerEventHandlers(window)
    return window


def _open(kind: str = "Project", table: str = "all_projects", name: str = "Morning Routine") -> Callable[[], None]:
    target: Element = element(table, name)

    def page() -> None:
        guiwins_tndesc.build_taskernet_description_dialog(_gui(), kind, target, name)

    return page


def _box(user: User) -> ui.textarea:
    (box,) = found(user, ui.textarea)
    return box


def _fake_draft(monkeypatch: pytest.MonkeyPatch, html: str, notes: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """Have the draft come back as `html`; the list records (facts text, the author's words) it was asked with."""
    asked: list[tuple[str, str]] = []

    async def draft(facts: mapdescribe.Facts, current: str, _settings: mapask.ModelSettings) -> mapdescribe.Described:
        asked.append((facts.text, current))
        return mapdescribe.Described(html, notes)

    monkeypatch.setattr(guiwins_describe.mapdescribe, "draft_description", draft)
    return asked


# ##################################################################################
# Insert Requirements
# ##################################################################################
@pytest.mark.asyncio
async def test_insert_requirements_adds_the_block_at_the_end() -> None:
    async with open_page(_open()) as user:
        _box(user).set_value("What it does.")
        await click(user, "Insert Requirements")

        text = str(_box(user).value)
        assert text.startswith("What it does.\n\n")
        assert tndesc.REQUIREMENTS_START in text and text.endswith(tndesc.REQUIREMENTS_END)
        assert user.notify.contains("Requirements added at the end.")
        assert tndesc.check(text) == []


@pytest.mark.asyncio
async def test_pressing_it_again_replaces_the_block_instead_of_adding_a_second() -> None:
    async with open_page(_open()) as user:
        await click(user, "Insert Requirements")
        _box(user).set_value(str(_box(user).value) + "\n\nWritten after.")
        await click(user, "Insert Requirements")

        text = str(_box(user).value)
        assert text.count(tndesc.REQUIREMENTS_START) == 1
        assert text.endswith("Written after.")
        assert user.notify.contains("Requirements brought up to date.")


@pytest.mark.asyncio
async def test_it_reads_the_object_the_editor_is_open_over() -> None:
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1" ve="2"><id>1</id><nme>Enter</nme>'
        '<Action sr="act0" ve="7"><code>375</code></Action></Task></TaskerData>'
    )
    async with open_page(_open("Task", "all_tasks", "Enter")) as user:
        await click(user, "Insert Requirements")

        text = str(_box(user).value)
        assert "<b>Special access</b>" in text
        assert "ADB Wi-Fi" in text
        assert "ADB Wifi in Task 'Enter'" in text


# ##################################################################################
# What will be sent
# ##################################################################################
@pytest.mark.asyncio
async def test_what_will_be_sent_is_the_message_word_for_word_and_is_read_when_opened() -> None:
    async with open_page(_open()) as user:
        _box(user).set_value("My own words.")
        (box,) = found(user, ui.expansion)
        box.set_value(True)

        facts = mapdescribe.gather("Project", element("all_projects", "Morning Routine"), "Morning Routine", PrimeItems)
        _system, expected = mapdescribe.build_prompt(facts, "My own words.")
        shown = [label.text for label in found(user, ui.label) if "<facts>" in label.text]
        assert shown == [expected]


@pytest.mark.asyncio
async def test_the_requirements_block_is_not_part_of_what_is_sent() -> None:
    async with open_page(_open()) as user:
        await click(user, "Insert Requirements")
        _box(user).set_value("Words.\n\n" + str(_box(user).value))
        (box,) = found(user, ui.expansion)
        box.set_value(True)

        shown = next(label.text for label in found(user, ui.label) if "<facts>" in label.text)
        assert "Words." in shown
        assert tndesc.REQUIREMENTS_HEADING not in shown


@pytest.mark.asyncio
async def test_the_row_says_what_is_sent_and_that_nothing_is_until_the_button() -> None:
    async with open_page(_open()) as user:
        said = " ".join(label.text for label in found(user, ui.label))

        assert "never an action's settings" in said
        assert "Nothing is sent until you press Draft with AI" in said


# ##################################################################################
# Draft with AI
# ##################################################################################
@pytest.mark.asyncio
async def test_a_draft_replaces_what_is_in_the_box_and_says_what_was_taken_out(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _fake_draft(monkeypatch, "<p>Starts your day.</p>", ("Taken out of the reply: a.",))
    async with open_page(_open()) as user:
        _box(user).set_value("old words")
        await click(user, "Draft with AI")

        assert str(_box(user).value) == "<p>Starts your day.</p>"
        assert asked and asked[0][1] == "old words"
        assert "Taken out of the reply: a." in [label.text for label in found(user, ui.label)]
        assert user.notify.contains("Drafted.")


@pytest.mark.asyncio
async def test_the_requirements_block_is_kept_and_never_sent_to_be_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _fake_draft(monkeypatch, "<p>New prose.</p>")
    async with open_page(_open()) as user:
        await click(user, "Insert Requirements")
        block = tndesc.split_requirements(str(_box(user).value))[1]
        _box(user).set_value(f"Old prose.\n\n{block}")
        await click(user, "Draft with AI")

        text = str(_box(user).value)
        assert text == f"<p>New prose.</p>\n\n{block}"
        assert asked[0][1] == "Old prose.", "the model is given the author's words and not the block"


@pytest.mark.asyncio
async def test_undo_draft_puts_back_exactly_what_was_there(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_draft(monkeypatch, "<p>Drafted.</p>")
    async with open_page(_open()) as user:
        _box(user).set_value("Written by hand.")
        assert not [b for b in found(user, ui.button) if b.text == "Undo Draft"]
        await click(user, "Draft with AI")
        assert str(_box(user).value) == "<p>Drafted.</p>"

        await click(user, "Undo Draft")

        assert str(_box(user).value) == "Written by hand."
        assert not [b for b in found(user, ui.button) if b.text == "Undo Draft"]


@pytest.mark.asyncio
async def test_a_model_that_cannot_be_asked_is_said_and_the_box_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> mapask.ModelSettings:
        raise mapask.AskError("No AI model is selected.  Choose one on the Analyze tab first.")

    monkeypatch.setattr(guiwins_describe.mapask, "model_settings", refuse)
    async with open_page(_open()) as user:
        _box(user).set_value("Mine.")
        await click(user, "Draft with AI")

        assert str(_box(user).value) == "Mine."
        assert user.notify.contains("No AI model is selected.")


@pytest.mark.asyncio
async def test_a_failed_question_is_said_in_words_and_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> mapdescribe.Described:
        raise mapask.AskError("OpenAI (gpt-test) could not be asked: no network")

    monkeypatch.setattr(guiwins_describe.mapdescribe, "draft_description", fail)
    async with open_page(_open()) as user:
        _box(user).set_value("Mine.")
        await click(user, "Draft with AI")

        assert str(_box(user).value) == "Mine."
        assert user.notify.contains("no network")
        assert not [b for b in found(user, ui.button) if b.text == "Undo Draft"]


@pytest.mark.asyncio
async def test_an_object_with_nothing_in_it_is_refused_in_words(monkeypatch: pytest.MonkeyPatch) -> None:
    empty = (
        '<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1" ve="2"><id>1</id><nme>Blank</nme></Task></TaskerData>'
    )
    _load(empty)
    async with open_page(_open("Task", "all_tasks", "Blank")) as user:
        await click(user, "Draft with AI")

        assert user.notify.contains("nothing in this Task yet to describe")
        assert str(_box(user).value) == ""


@pytest.mark.asyncio
async def test_a_question_can_be_given_up_on_and_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()

    async def never(*_args: object, **_kwargs: object) -> mapdescribe.Described:
        started.set()
        await asyncio.sleep(60)
        raise AssertionError("not reached")

    monkeypatch.setattr(guiwins_describe.mapdescribe, "draft_description", never)
    async with open_page(_open()) as user:
        _box(user).set_value("Mine.")
        asking = asyncio.create_task(user_press(user, "Draft with AI"))
        await asyncio.wait_for(started.wait(), 5)
        assert button(user, "Stop").visible

        await click(user, "Stop")
        await asking

        assert str(_box(user).value) == "Mine."
        assert user.notify.contains("The request to the AI model was cancelled.")


async def user_press(user: User, text: str) -> None:
    await click(user, text)
