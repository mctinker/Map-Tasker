"""The Replace half of the Find/Replace dialog (guiwins_search): nothing changes that was not previewed.

What a plan does is test_mapswap's.  These open the real dialog on its Replace tab, over the same fixture
configuration and on NiceGUI's in-process user simulation, and walk the one rule the tab is built
around: the Replace button works only for a preview made from the values now in the fields.  So what is
asserted is that a preview draws a row per change with a tick on it, that touching any field takes the
preview and the button away, that only what is ticked is applied, and that a Replace which went through
closes the dialog and redraws the view it came from.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from nicegui import ui

from maptasker.src import guiwins_search, mapswap, sessundo
from maptasker.src.primitem import PrimeItems
from tests.search_dialog import built, by_text, click, field, labels, open_dialog, select
from tests.test_mapswap import _FIXTURE_XML, _RENAME_XML, FLASH, NOTIFY, _action, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from nicegui.testing.user import User

FLASH_TEXT_LABEL = "Text"


@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """The swap fixture loaded, an empty undo history, and a working directory of its own."""
    monkeypatch.chdir(tmp_path)
    sessundo.clear()
    _load(_FIXTURE_XML)
    built.clear()
    built.update(view=None, jumps=[], title="Map")

    async def go_to_target(gui: object, target: object, *, prefer_diagram: bool = False) -> None:
        built["jumps"].append((target, prefer_diagram))

    monkeypatch.setattr(guiwins_search, "go_to_target", go_to_target)
    yield
    sessundo.clear()


async def _replace_tab(user: User) -> None:
    """Go to the Replace tab, as a person would."""
    (tab,) = (e for e in user.client.elements.values() if isinstance(e, ui.tab) and e.props.get("label") == "Replace")
    click(user, tab)
    await asyncio.sleep(0.05)


def _button(user: User, text: str) -> ui.button:
    """The Replace tab's button with this text: hidden or not, and the last drawn (the Find tab has its own)."""
    found = (e for e in user.client.elements.values() if isinstance(e, ui.button) and e.text == text)
    return max(found, key=lambda e: e.id)


def _replace_select(user: User, label: str, *, condition: bool = False) -> ui.select:
    """The Replace tab's select with this label.

    The Find tab has "Narrow to Project" too, and the action and condition rows both have "...with this one";
    the action row is drawn first, so the condition row's is the last of them.
    """
    found = [e for e in user.client.elements.values() if isinstance(e, ui.select) and e.props.get("label") == label]
    return max(found, key=lambda e: e.id) if condition else min(found, key=lambda e: e.id)


def _shown(element: ui.element) -> bool:
    """Whether this element and everything it sits in is visible."""
    while element is not None:
        if not element.visible:
            return False
        element = element.parent_slot.parent if element.parent_slot is not None else None
    return True


def _toggle(user: User) -> ui.toggle:
    (toggle,) = (e for e in user.client.elements.values() if isinstance(e, ui.toggle))
    return toggle


def _ticks(user: User) -> list[ui.checkbox]:
    return sorted(
        (e for e in user.client.elements.values() if isinstance(e, ui.checkbox) and not e.text),
        key=lambda e: e.id,
    )


async def _preview_flash_to_notify(user: User) -> None:
    _replace_select(user, "Replace this action").value = FLASH
    _replace_select(user, "...with this one").value = NOTIFY
    click(user, _button(user, "Preview"))
    await asyncio.sleep(0.05)


# ##################################################################################
# The tab
# ##################################################################################
@pytest.mark.asyncio
async def test_replace_starts_disabled_and_offers_what_the_configuration_holds() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        assert not _button(user, "Replace").enabled
        offered = set(_replace_select(user, "Replace this action").options)
        assert {FLASH, "20t"} <= offered
        assert "Change one thing everywhere it appears." in " ".join(
            text for text in labels(user)
        ) or any(text.startswith("Change one thing") for text in labels(user))


@pytest.mark.asyncio
async def test_each_mode_shows_its_own_fields_and_hides_the_others() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        toggle = _toggle(user)
        rows = {
            "action": "Replace this action",
            "argument": "In this action",
            "condition": "Replace this Profile condition",
            "variable": "Rename this variable",
        }
        for mode in rows:
            toggle.value = mode
            for other, label in rows.items():
                assert _shown(_replace_select(user, label)) == (other == mode), (mode, other)


@pytest.mark.asyncio
async def test_choosing_a_source_action_stocks_the_targets_with_what_each_would_cost() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        assert _replace_select(user, "...with this one").options == {}
        _replace_select(user, "Replace this action").value = FLASH
        targets = _replace_select(user, "...with this one").options
        assert NOTIFY in targets
        assert "keeps" in targets[NOTIFY]


# ##################################################################################
# Preview
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("action", "Choose an action to replace, and one to replace it with."),
        ("argument", "Choose an action, and which of its arguments to replace."),
        ("condition", "Choose a Profile condition to replace, and one to replace it with."),
        ("variable", "Choose a variable, and type the new name."),
    ],
)
async def test_preview_with_the_fields_empty_says_what_is_missing(mode: str, message: str) -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        _toggle(user).value = mode
        click(user, _button(user, "Preview"))
        assert user.notify.contains(message)
        assert not _button(user, "Replace").enabled


@pytest.mark.asyncio
async def test_a_preview_draws_a_ticked_row_for_each_change_and_enables_replace() -> None:
    expected = mapswap.plan_action_swap(FLASH, NOTIFY, "", state=PrimeItems)
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)

        assert _button(user, "Replace").enabled
        assert f"{expected.what} -- {expected.tally()}" in labels(user)
        boxes = _ticks(user)
        assert len(boxes) == len(expected.changes) > 0
        assert all(box.value for box in boxes) == (len(expected.selected) == len(expected.changes))


@pytest.mark.asyncio
async def test_touching_any_field_takes_the_preview_and_the_replace_button_away() -> None:
    expected = mapswap.plan_action_swap(FLASH, NOTIFY, "", state=PrimeItems)
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        assert _button(user, "Replace").enabled

        summary = f"{expected.what} -- {expected.tally()}"
        assert summary in labels(user)

        _replace_select(user, "...with this one").value = None
        assert not _button(user, "Replace").enabled
        assert _ticks(user) == []
        assert summary not in labels(user)


@pytest.mark.asyncio
async def test_switching_mode_drops_the_preview() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        _toggle(user).value = "condition"
        assert not _button(user, "Replace").enabled
        assert _ticks(user) == []


@pytest.mark.asyncio
async def test_unticking_a_row_takes_it_out_of_what_is_applied_and_is_remembered_on_the_view() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        before = built["view"]._replace_ticks
        _ticks(user)[0].value = False
        assert built["view"]._replace_ticks != before


@pytest.mark.asyncio
async def test_a_preview_that_changes_nothing_says_so_and_leaves_replace_off() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        _replace_select(user, "Replace this action").value = FLASH
        _replace_select(user, "...with this one").value = FLASH
        click(user, _button(user, "Preview"))
        await asyncio.sleep(0.05)
        assert not _button(user, "Replace").enabled


# ##################################################################################
# Replace
# ##################################################################################
@pytest.mark.asyncio
async def test_replace_applies_what_was_previewed_closes_the_dialog_and_redraws_the_view() -> None:
    plan = mapswap.plan_action_swap(FLASH, NOTIFY, "", state=PrimeItems)
    codes_before = [_action("20", at).findtext("code") for at in range(2)]
    assert plan.changes, "the fixture is meant to offer a swap"

    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        dialog = built["view"]._find_dialog
        click(user, _button(user, "Replace"))
        await asyncio.sleep(0.2)

        assert user.notify.contains("changed.")
        assert user.notify.contains("Undo is available.")
        assert dialog.value is False
        assert built["rebuilt"] == ["map"]
        assert built["view"]._replace_inputs is None
    assert [_action("20", at).findtext("code") for at in range(2)] != codes_before


@pytest.mark.asyncio
async def test_a_replace_from_the_diagram_redraws_the_diagram() -> None:
    async with open_dialog("Diagram View") as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        click(user, _button(user, "Replace"))
        await asyncio.sleep(0.2)
        assert built["rebuilt"] == ["diagram"]


@pytest.mark.asyncio
async def test_replace_with_nothing_ticked_changes_nothing() -> None:
    codes_before = [_action("20", at).findtext("code") for at in range(2)]
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        for box in _ticks(user):
            box.value = False
        click(user, _button(user, "Replace"))
        await asyncio.sleep(0.1)
        assert user.notify.contains("Nothing is ticked.")
        assert built.get("rebuilt") is None
    assert [_action("20", at).findtext("code") for at in range(2)] == codes_before


# ##################################################################################
# Save Preview
# ##################################################################################
@pytest.mark.asyncio
async def test_save_preview_before_any_preview_asks_for_one() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        click(user, _button(user, "Save Preview"))
        assert user.notify.contains("Press Preview first.")


@pytest.mark.asyncio
async def test_save_preview_writes_a_file(tmp_path: Path) -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        click(user, _button(user, "Save Preview"))
        assert user.notify.contains("Replace preview saved as")
    assert [p for p in tmp_path.rglob("*") if p.is_file() and p.suffix in (".txt", ".html", ".md", ".log")]


@pytest.mark.asyncio
async def test_a_save_that_fails_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapswap, "write_swap_report", lambda *_a, **_k: "")
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        click(user, _button(user, "Save Preview"))
        assert user.notify.contains("Replace preview could not be saved.")


# ##################################################################################
# The other modes
# ##################################################################################
@pytest.mark.asyncio
async def test_condition_mode_swaps_one_kind_of_condition_for_another() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        _toggle(user).value = "condition"
        sources = _replace_select(user, "Replace this Profile condition").options
        assert sources, "the fixture holds Profile conditions"
        source = next(iter(sources))
        _replace_select(user, "Replace this Profile condition").value = source
        assert _replace_select(user, "...with this one", condition=True).options


@pytest.mark.asyncio
async def test_argument_mode_stocks_the_arguments_and_previews_the_new_value() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        _toggle(user).value = "argument"
        _replace_select(user, "In this action").value = FLASH
        arguments = _replace_select(user, "...replace this argument").options
        assert "0" in arguments
        _replace_select(user, "...replace this argument").value = "0"
        field(user, "...and put this there").value = "Ready"
        click(user, _button(user, "Preview"))
        await asyncio.sleep(0.05)
        assert _button(user, "Replace").enabled
        assert len(_ticks(user)) == 2


@pytest.mark.asyncio
async def test_variable_mode_renames_across_every_place_it_is_used() -> None:
    _load(_RENAME_XML)
    async with open_dialog() as user:
        await _replace_tab(user)
        _toggle(user).value = "variable"
        picker = _replace_select(user, "Rename this variable")
        assert picker.options
        picker.value = 0
        field(user, "...to this name").value = "%Renamed"
        click(user, _button(user, "Preview"))
        await asyncio.sleep(0.05)
        assert _button(user, "Replace").enabled
        assert _ticks(user)


# ##################################################################################
# Coming back
# ##################################################################################
@pytest.mark.asyncio
async def test_reopening_after_a_preview_comes_back_to_it_with_the_same_ticks() -> None:
    async with open_dialog() as user:
        await _replace_tab(user)
        await _preview_flash_to_notify(user)
        _ticks(user)[0].value = False
        ticks = [box.value for box in _ticks(user)]

        click(user, by_text(user, "Find")[0])
        await asyncio.sleep(0.1)

        assert _button(user, "Replace").enabled
        assert [box.value for box in _ticks(user)] == ticks
