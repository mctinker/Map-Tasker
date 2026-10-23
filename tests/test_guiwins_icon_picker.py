"""The icon picker, the Pick buttons beside App and Icon fields, and the fetch offered where an empty inventory refuses.

The inventory is appinv's.  Here it is the pieces of the Action editor that sit on it: the glyph each icon is drawn
by, the picker that replaces what an Icon field holds (or clears it), the two refusals that a fetch from the device
can lift -- and only those two -- and the re-asking of an action's arguments once a fetch has changed the answer.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from maptasker.src.core import appinv
from maptasker.src.core.primitem import RunState
from maptasker.src.edit import taskedit_model
from maptasker.src.gui import guiwins_taskedit
from nicegui import ui

from tests.nicegui_harness import click, found, label_texts, open_page

if TYPE_CHECKING:
    from collections.abc import Callable


_ICONS = [
    appinv.IconRef("builtin", "mw_action_home"),
    appinv.IconRef("builtin", "hd_action_zzz_unknown"),
    appinv.IconRef("pack", "ic_one", "com.pack.icons"),
    appinv.IconRef("app", "", "com.whatsapp", "com.whatsapp.Home"),
    appinv.IconRef("var", "%icon"),
]


@pytest.fixture
def icons(monkeypatch: pytest.MonkeyPatch) -> Any:
    record = SimpleNamespace(entries=list(_ICONS), fetched=[])
    monkeypatch.setattr(appinv, "icons", lambda state: list(record.entries))
    monkeypatch.setattr(appinv, "material_icon_names", lambda: ["home", "star"])
    record.window = SimpleNamespace(state=RunState())
    return record


# ##################################################################################
# Which glyph an icon is drawn by
# ##################################################################################
@pytest.mark.parametrize(
    ("icon", "glyph"),
    [
        (appinv.IconRef("builtin", "mw_action_home"), "home"),
        (appinv.IconRef("builtin", "mw_navigation_not_in_the_font"), "not_in_the_font"),
        (appinv.IconRef("builtin", "hd_action_star"), "star"),
        (appinv.IconRef("builtin", "hl_action_not_a_known_ligature"), "image"),
        (appinv.IconRef("builtin", "plain"), "image"),
        (appinv.IconRef("pack", "x", "pkg"), "extension"),
        (appinv.IconRef("app", "", "pkg", "cls"), "android"),
        (appinv.IconRef("var", "%v"), "percent"),
        (appinv.IconRef("weird", "w"), "image"),
    ],
)
def test_each_icon_is_drawn_by_its_own_glyph_a_lookalike_or_one_for_its_kind(
    icons: Any, icon: appinv.IconRef, glyph: str
) -> None:
    assert guiwins_taskedit._tasker_icon_glyph(icon) == glyph


# ##################################################################################
# The picker
# ##################################################################################
def _picker(icons: Any, value: str = "old") -> tuple[Callable[[], None], list[ui.input]]:
    made: list[ui.input] = []

    def page() -> None:
        field = ui.input(value=value)
        made.append(field)
        guiwins_taskedit._build_tasker_icon_picker_dialog(field, icons.window)

    return page, made


@pytest.mark.asyncio
async def test_every_icon_is_offered_with_its_kind_and_picking_replaces_the_field(icons: Any) -> None:
    page, made = _picker(icons)
    async with open_page(page) as user:
        labels = label_texts(user)
        assert {"builtin", "pack", "app", "var"} <= set(labels)
        await click(user, "App: com.whatsapp")
        assert made[0].value == appinv.format_icon_value(_ICONS[3])
        (dialog,) = found(user, ui.dialog)
        assert not dialog.value


@pytest.mark.asyncio
async def test_no_icon_clears_the_field_and_cancel_leaves_it(icons: Any) -> None:
    page, made = _picker(icons)
    async with open_page(page) as user:
        await click(user, "Cancel")
        assert made[0].value == "old"
    page, made = _picker(icons)
    async with open_page(page) as user:
        await click(user, "No Icon")
        assert made[0].value == ""


@pytest.mark.asyncio
async def test_the_icon_search_matches_the_display_name_or_the_reference_and_says_when_nothing_does(icons: Any) -> None:
    page, _made = _picker(icons)
    async with open_page(page) as user:
        (box,) = [e for e in found(user, ui.input) if "Search" in str(e.props.get("placeholder", ""))]
        box.value = "whatsapp"
        await asyncio.sleep(0.05)
        assert "App: com.whatsapp" in [b.text for b in found(user, ui.button)]
        assert "ic_one  (icons)" not in [b.text for b in found(user, ui.button)]
        box.value = "zzzzzz"
        await asyncio.sleep(0.05)
        assert "Nothing here." in label_texts(user)


@pytest.mark.asyncio
async def test_a_long_icon_list_is_cut_and_the_count_said(icons: Any) -> None:
    icons.entries = [
        appinv.IconRef("builtin", f"mw_icon{n:04d}") for n in range(guiwins_taskedit._PICKER_ROW_LIMIT + 7)
    ]
    page, _made = _picker(icons)
    async with open_page(page) as user:
        assert any(text.startswith("More matches than can be shown") and "(207)" in text for text in label_texts(user))


@pytest.mark.asyncio
async def test_icon_not_listed_fetches_for_icons_and_reopens(icons: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(gui: object, on_fetched: Callable[[], None], for_icons: bool = False) -> None:
        icons.fetched.append(for_icons)

    monkeypatch.setattr(guiwins_taskedit, "_build_fetch_apps_dialog", fetch)
    page, _made = _picker(icons)
    async with open_page(page) as user:
        await click(user, "Icon not listed?")
        assert icons.fetched == [True]


# ##################################################################################
# The fields with a Pick button
# ##################################################################################
def _arg(name: str = "Icon", value: str = "mw_star") -> taskedit_model.EditableArg:
    return taskedit_model.EditableArg(
        arg_id="arg1",
        arg_name=name,
        widget_kind="icon_picker",
        backing_tag="Img",
        is_var=False,
        element=None,
        current_value=value,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("renderer", "opens"),
    [("_render_app_arg_field", "Pick an Application"), ("_render_icon_arg_field", "Pick an icon")],
)
async def test_an_app_or_icon_field_holds_the_value_and_its_pick_button_opens_its_picker(
    icons: Any, monkeypatch: pytest.MonkeyPatch, renderer: str, opens: str
) -> None:
    monkeypatch.setattr(appinv, "apps", lambda state: [])
    refs: dict[str, ui.input] = {}

    def page() -> None:
        getattr(guiwins_taskedit, renderer)(icons.window, _arg(), "k", refs)

    async with open_page(page) as user:
        assert refs["k"].value == "mw_star"
        await click(user, "Pick")
        assert opens in label_texts(user)


@pytest.mark.asyncio
async def test_a_value_handed_in_overrides_the_arguments_own(icons: Any) -> None:
    refs: dict[str, ui.input] = {}

    def page() -> None:
        guiwins_taskedit._render_icon_arg_field(icons.window, _arg(), "k", refs, value="typed")

    async with open_page(page):
        assert refs["k"].value == "typed"


# ##################################################################################
# The refusals a fetch can lift
# ##################################################################################
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "button"),
    [(taskedit_model.NO_APPS_REASON, "App not listed?"), (taskedit_model.NO_ICONS_REASON, "Icon not listed?")],
)
async def test_the_two_empty_inventory_refusals_carry_a_fetch_button_worded_for_what_is_missing(
    icons: Any, reason: str, button: str
) -> None:
    def page() -> None:
        guiwins_taskedit._render_addability_reason(icons.window, reason, lambda: None)

    async with open_page(page) as user:
        assert reason in label_texts(user)
        assert button in [b.text for b in found(user, ui.button)]


@pytest.mark.asyncio
async def test_any_other_refusal_is_only_a_statement_with_no_way_out(icons: Any) -> None:
    def page() -> None:
        guiwins_taskedit._render_readonly_note(icons.window, "This argument is not editable.", lambda: None)

    async with open_page(page) as user:
        assert "This argument is not editable." in label_texts(user)
        assert [b.text for b in found(user, ui.button)] == []


@pytest.mark.asyncio
async def test_the_fetch_button_opens_the_fetch_dialog_for_the_right_kind(
    icons: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[bool] = []

    async def fetch(gui: object, on_fetched: Callable[[], None], for_icons: bool = False) -> None:
        calls.append(for_icons)

    monkeypatch.setattr(guiwins_taskedit, "_build_fetch_apps_dialog", fetch)

    def page() -> None:
        guiwins_taskedit._render_readonly_note(icons.window, taskedit_model.NO_ICONS_REASON, lambda: None)

    async with open_page(page) as user:
        await click(user, "Icon not listed?")
        assert calls == [True]


def test_after_a_fetch_the_actions_arguments_are_asked_again_and_then_redrawn(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    monkeypatch.setattr(
        guiwins_taskedit.taskedit_args, "reclassify_action_args", lambda action, state: order.append("reclassified")
    )
    state = RunState()

    guiwins_taskedit._after_inventory_fetch(lambda: order.append("redrawn"), MagicMock(), state)()

    assert order == ["reclassified", "redrawn"], "redrawing alone would leave the field grey with a stale reason"


def test_after_a_fetch_a_conditions_arguments_are_asked_again_and_then_redrawn(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    monkeypatch.setattr(
        guiwins_taskedit.profedit, "reclassify_condition_args", lambda condition, state: order.append("reclassified")
    )

    guiwins_taskedit._after_condition_fetch(lambda: order.append("redrawn"), MagicMock(), RunState())()

    assert order == ["reclassified", "redrawn"]
