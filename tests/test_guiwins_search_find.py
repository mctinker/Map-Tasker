"""The Find half of the Find/Replace dialog (guiwins_search): what it asks, what it shows, what it keeps.

What a query answers is test_mapfind's.  These open the real dialog from a stand-in view over the same
fixture configuration, on a page of NiceGUI's in-process user simulation, and use it as a person would:
pick from the boxes, press Find, follow a row, save the list, ask the AI model in plain words.  What is
asserted is the dialog's part -- that the boxes build the query they show, that the list on screen is
the list that is saved, that following a row docks the dialog rather than throwing the list away, and
that reopening it comes back to the last question asked.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from nicegui import ui

from maptasker.src import guiwins_search, mapask, mapfind
from maptasker.src.mapjump import TASK
from maptasker.src.primitem import PrimeItems
from tests.search_dialog import built, by_text, click, field, labels, links, open_dialog, press_find, select
from tests.test_mapfind import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from pathlib import Path

    from nicegui.testing.user import User

@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture configuration, a working directory of its own, and jumps recorded rather than made."""
    monkeypatch.chdir(tmp_path)
    _load(_FIXTURE_XML)
    built.clear()
    built.update(view=None, jumps=[], title="Map")

    async def go_to_target(gui: object, target: object, *, prefer_diagram: bool = False) -> None:
        built["jumps"].append((target, prefer_diagram))

    monkeypatch.setattr(guiwins_search, "go_to_target", go_to_target)


def _summary(user: User) -> str:
    (line,) = [text for text in labels(user) if " found for: " in text]
    return line


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_find_says_so_and_opens_nothing() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    async with open_dialog() as user:
        assert user.notify.contains("No XML file has been loaded.  Get an XML file first.")
        assert built["view"]._find_dialog is None


@pytest.mark.asyncio
async def test_the_dialog_is_titled_with_the_view_and_offers_a_box_per_facet() -> None:
    async with open_dialog("Map") as user:
        assert "Find in Map" in labels(user)
        for facet in mapfind.FACETS:
            assert select(user, mapfind.FACET_LABELS[facet])
        assert field(user, "Text (name, label or argument)")
        assert select(user, "Narrow to Project").value == ""


@pytest.mark.asyncio
async def test_each_box_offers_only_what_the_configuration_uses() -> None:
    index = mapfind.build_index(state=PrimeItems)
    async with open_dialog() as user:
        for facet in mapfind.FACETS:
            offered = set(select(user, mapfind.FACET_LABELS[facet]).options)
            assert offered == {choice.value for choice in index.choices(facet)}
        projects = select(user, "Narrow to Project").options
        assert set(projects) == {"", "Home", "Away"}


@pytest.mark.asyncio
async def test_a_single_item_selection_is_stated_and_hides_the_project_box() -> None:
    PrimeItems.program_arguments.single_project_name = "Home"
    async with open_dialog() as user:
        assert any(text.startswith("Limited to") for text in labels(user))
        assert not select(user, "Narrow to Project").visible


@pytest.mark.asyncio
async def test_with_everything_in_scope_there_is_no_limit_notice() -> None:
    async with open_dialog() as user:
        assert not any(text.startswith("Limited to") for text in labels(user))
        assert select(user, "Narrow to Project").visible


# ##################################################################################
# Finding
# ##################################################################################
@pytest.mark.asyncio
async def test_find_with_every_box_empty_asks_for_a_choice_and_lists_nothing() -> None:
    async with open_dialog() as user:
        press_find(user)
        assert user.notify.contains("Choose an action, a trigger, an app, a Scene or some text.")
        assert links(user) == []


@pytest.mark.asyncio
async def test_find_by_action_lists_the_tasks_and_says_how_many_it_found() -> None:
    index = mapfind.build_index(state=PrimeItems)
    action = next(c.value for c in index.choices(mapfind.ACTION) if "HTTP" in c.label)
    expected, total = mapfind.run_query(index, mapfind.Query(action=action))
    async with open_dialog() as user:
        select(user, "Task action").value = action
        press_find(user)
        assert len(links(user)) == len(expected) == total
        assert _summary(user).startswith(f"{total} found for")
        # The Project each answer belongs to heads its group.
        assert "Project 'Home'" in labels(user)
        assert "Project 'Away'" in labels(user)


@pytest.mark.asyncio
async def test_narrowing_to_a_project_leaves_the_other_out() -> None:
    index = mapfind.build_index(state=PrimeItems)
    action = next(c.value for c in index.choices(mapfind.ACTION) if "HTTP" in c.label)
    async with open_dialog() as user:
        select(user, "Task action").value = action
        select(user, "Narrow to Project").value = "Away"
        press_find(user)
        assert "Project 'Away'" in labels(user)
        assert "Project 'Home'" not in labels(user)


@pytest.mark.asyncio
async def test_find_by_text_and_a_question_that_nothing_answers() -> None:
    async with open_dialog() as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        assert len(links(user)) == 1

        field(user, "Text (name, label or argument)").value = "zzz-nothing-has-this"
        press_find(user)
        assert "Nothing in the loaded configuration answers this." in labels(user)
        assert links(user) == []


@pytest.mark.asyncio
async def test_the_last_question_is_remembered_on_the_view_and_refilled_on_reopening() -> None:
    async with open_dialog() as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        remembered = built["view"]._find_query
        assert remembered.text == "quietly"

        click(user, by_text(user, "Find")[0])
        # The old dialog is taken down and a fresh one comes up already holding the question.
        assert field(user, "Text (name, label or argument)").value == "quietly"
        assert _summary(user).startswith("1 found for")


# ##################################################################################
# Following a row
# ##################################################################################
@pytest.mark.asyncio
async def test_following_a_row_goes_to_its_object_and_docks_the_dialog_rather_than_closing_it() -> None:
    async with open_dialog() as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        dialog = built["view"]._find_dialog
        assert "seamless" not in dialog.props

        row = links(user)[0]
        click(user, row)
        await asyncio.sleep(0.1)

        ((target, prefer_diagram),) = built["jumps"]
        assert (target.kind, target.name) == (TASK, "Quiet")
        assert prefer_diagram is False
        assert "seamless" in dialog.props
        assert dialog.value is True
        # (Not looked up again through the user: a link's click is a navigation to its '#' to the simulation.)
        assert not row.is_deleted, "the list the row came from is still there"


@pytest.mark.asyncio
async def test_a_find_from_the_diagram_asks_to_be_shown_in_the_diagram() -> None:
    async with open_dialog("Diagram") as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        click(user, links(user)[0])
        await asyncio.sleep(0.1)
        assert built["jumps"][0][1] is True


# ##################################################################################
# Saving the list
# ##################################################################################
@pytest.mark.asyncio
async def test_save_before_any_find_asks_for_one_first() -> None:
    async with open_dialog() as user:
        click(user, by_text(user, "Save Results")[0])
        assert user.notify.contains("Run a Find first.")


@pytest.mark.asyncio
async def test_save_writes_the_list_on_screen_and_names_the_file(tmp_path: Path) -> None:
    async with open_dialog() as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        click(user, by_text(user, "Save Results")[0])
        assert user.notify.contains("Find results saved as")
        written = [p for p in tmp_path.rglob("*") if p.is_file() and "Find" in p.name]
        assert written, "a Find report should have been written"
        assert "Quiet" in written[0].read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_a_save_that_fails_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapfind, "write_find_report", lambda *_a, **_k: "")
    async with open_dialog() as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        click(user, by_text(user, "Save Results")[0])
        assert user.notify.contains("Find results could not be saved.")


# ##################################################################################
# Closing
# ##################################################################################
@pytest.mark.asyncio
async def test_close_hides_the_dialog_and_the_next_find_replaces_it() -> None:
    async with open_dialog() as user:
        view = built["view"]
        first = view._find_dialog
        click(user, by_text(user, "Close")[0])
        assert first.value is False

        click(user, by_text(user, "Find")[0])
        assert view._find_dialog is not first
        assert first.is_deleted, "a fresh dialog is built per press, so the old one is taken down, not stacked"


@pytest.mark.asyncio
async def test_dismissing_deletes_the_dialog_and_forgets_it() -> None:
    async with open_dialog() as user:
        view = built["view"]
        dialog = view._find_dialog
        with user.client:
            view._dismiss_find_dialog()
        assert view._find_dialog is None
        assert dialog.is_deleted


# ##################################################################################
# Ask AI
# ##################################################################################
@pytest.mark.asyncio
async def test_ask_with_no_question_asks_for_one() -> None:
    async with open_dialog() as user:
        click(user, by_text(user, "Ask AI")[0])
        await asyncio.sleep(0.05)
        assert user.notify.contains("Type a question first.")


@pytest.mark.asyncio
async def test_ask_with_no_model_chosen_reports_why(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise mapask.AskError("Choose an AI model on the Analyze tab first.")

    monkeypatch.setattr(mapask, "model_settings", refuse)
    async with open_dialog() as user:
        field(user, "Ask in plain words").value = "wifi at home"
        click(user, by_text(user, "Ask AI")[0])
        await asyncio.sleep(0.05)
        assert user.notify.contains("Choose an AI model on the Analyze tab first.")


@pytest.mark.asyncio
async def test_a_translated_question_fills_the_boxes_and_runs_the_query(monkeypatch: pytest.MonkeyPatch) -> None:
    translation = mapask.Translation(
        query=mapfind.Query(text="quietly"),
        unknown=["a thing nobody uses"],
        surplus=[],
        unexpressed="",
    )

    async def translate(question: str, index: object, settings: object) -> mapask.Translation:
        return translation

    monkeypatch.setattr(mapask, "model_settings", lambda *_a, **_k: object())
    monkeypatch.setattr(mapask, "translate", translate)
    async with open_dialog() as user:
        field(user, "Ask in plain words").value = "anything quiet"
        click(user, by_text(user, "Ask AI")[0])
        await asyncio.sleep(0.1)
        assert field(user, "Text (name, label or argument)").value == "quietly"
        assert len(links(user)) == 1
        notes = [e for e in user.client.elements.values() if isinstance(e, ui.label) and "Left out" in e.text]
        assert notes
        assert "a thing nobody uses" in notes[0].text


@pytest.mark.asyncio
async def test_a_question_that_comes_back_empty_says_so_and_clears_the_list(monkeypatch: pytest.MonkeyPatch) -> None:
    async def translate(question: str, index: object, settings: object) -> mapask.Translation:
        return mapask.Translation(query=mapfind.Query(), unknown=[], surplus=[], unexpressed="")

    monkeypatch.setattr(mapask, "model_settings", lambda *_a, **_k: object())
    monkeypatch.setattr(mapask, "translate", translate)
    async with open_dialog() as user:
        field(user, "Text (name, label or argument)").value = "quietly"
        press_find(user)
        field(user, "Ask in plain words").value = "gibberish"
        click(user, by_text(user, "Ask AI")[0])
        await asyncio.sleep(0.1)
        assert user.notify.contains("The question could not be turned into a search.")
        assert links(user) == []


@pytest.mark.asyncio
async def test_a_model_error_is_reported_and_leaves_the_boxes_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    async def translate(question: str, index: object, settings: object) -> mapask.Translation:
        raise mapask.AskError("The model did not answer.")

    monkeypatch.setattr(mapask, "model_settings", lambda *_a, **_k: object())
    monkeypatch.setattr(mapask, "translate", translate)
    async with open_dialog() as user:
        field(user, "Ask in plain words").value = "anything"
        click(user, by_text(user, "Ask AI")[0])
        await asyncio.sleep(0.1)
        assert user.notify.contains("The model did not answer.")
        assert field(user, "Text (name, label or argument)").value in (None, "")
        assert built["view"]._find_ask is None
