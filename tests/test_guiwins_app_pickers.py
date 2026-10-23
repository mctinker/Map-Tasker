"""The Application pickers: tick several for an argument, pick one for a Profile's App condition, or name a variable.

The inventory they offer is appinv's.  Here it is the dialogs: what was already in the field and is not in the
list is kept and shown, the search narrows the list, ticks are written back in the inventory's order with the
unlisted ones first, a variable is accepted only if it looks like one, and a fetch part-way through choosing does
not lose the ticks made so far.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core import appinv
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import guiwins_taskedit
from nicegui import ui

from tests.nicegui_harness import all_elements, click, found, label_texts, open_page

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui.testing.user import User


def _search(user: User) -> ui.input:
    (box,) = [e for e in found(user, ui.input) if "Search" in str(e.props.get("placeholder", ""))]
    return box


def _checks(user: User) -> list[ui.checkbox]:
    """Every checkbox on the page -- an empty list when the search leaves none, which user.find would refuse."""
    return [e for e in all_elements(user) if isinstance(e, ui.checkbox)]


_APPS = [
    appinv.AppEntry("com.android.camera", "Camera", "com.android.camera.Main"),
    appinv.AppEntry("com.whatsapp", "WhatsApp", "com.whatsapp.Home"),
    appinv.AppEntry("org.example.notes", "Notes", ""),
]


@pytest.fixture
def apps(monkeypatch: pytest.MonkeyPatch) -> Any:
    record = SimpleNamespace(entries=list(_APPS), fetched=[])
    monkeypatch.setattr(appinv, "apps", lambda state: list(record.entries))
    monkeypatch.setattr(appinv, "have_apps", lambda state: bool(record.entries))
    record.window = SimpleNamespace(state=RunState())
    return record


# ##################################################################################
# Several applications for a field
# ##################################################################################
def _multi(apps: Any, value: str) -> tuple[Callable[[], None], list[ui.input]]:
    made: list[ui.input] = []

    def page() -> None:
        field = ui.input(value=value)
        made.append(field)
        guiwins_taskedit._build_app_picker_dialog(field, apps.window)

    return page, made


@pytest.mark.asyncio
async def test_what_the_field_holds_is_ticked_and_what_the_list_lacks_is_shown_and_kept(apps: Any) -> None:
    page, made = _multi(apps, "com.whatsapp, %app_package, com.old.gone")
    async with open_page(page) as user:
        ticked = {c.text for c in _checks(user) if c.value}
        assert ticked == {"WhatsApp  (com.whatsapp)"}
        assert "Also in this field: %app_package, com.old.gone" in label_texts(user)
        await click(user, "Use Selected")
        assert made[0].value == "%app_package, com.old.gone, com.whatsapp", "unlisted first, where they were"


@pytest.mark.asyncio
async def test_ticking_writes_back_in_inventory_order_not_tick_order(apps: Any) -> None:
    page, made = _multi(apps, "")
    async with open_page(page) as user:
        for box in reversed(_checks(user)):
            box.value = True
        await asyncio.sleep(0.05)
        await click(user, "Use Selected")
        assert made[0].value == "com.android.camera, com.whatsapp, org.example.notes"


@pytest.mark.asyncio
async def test_unticking_removes_the_package_and_cancel_leaves_the_field_alone(apps: Any) -> None:
    page, made = _multi(apps, "com.whatsapp")
    async with open_page(page) as user:
        (box,) = [c for c in _checks(user) if c.value]
        box.value = False
        await asyncio.sleep(0.05)
        await click(user, "Cancel")
        assert made[0].value == "com.whatsapp"
        (dialog,) = found(user, ui.dialog)
        assert not dialog.value


@pytest.mark.asyncio
async def test_the_search_narrows_the_list_by_label_or_package_and_says_when_nothing_matches(apps: Any) -> None:
    page, _made = _multi(apps, "")
    async with open_page(page) as user:
        _search(user).value = "whats"
        await asyncio.sleep(0.05)
        assert [c.text for c in _checks(user)] == ["WhatsApp  (com.whatsapp)"]
        _search(user).value = "example"
        await asyncio.sleep(0.05)
        assert [c.text for c in _checks(user)] == ["Notes  (org.example.notes)"]
        _search(user).value = "zzz"
        await asyncio.sleep(0.05)
        assert _checks(user) == [] and "Nothing here." in label_texts(user)


@pytest.mark.asyncio
async def test_a_long_inventory_is_cut_and_the_count_is_said(apps: Any) -> None:
    apps.entries = [
        appinv.AppEntry(f"pkg.app{n:04d}", f"App {n}") for n in range(guiwins_taskedit._PICKER_ROW_LIMIT + 25)
    ]
    page, _made = _multi(apps, "")
    async with open_page(page) as user:
        assert len(_checks(user)) == guiwins_taskedit._PICKER_ROW_LIMIT
        assert any(text.startswith("More matches than can be shown") and "(225)" in text for text in label_texts(user))


@pytest.mark.asyncio
async def test_a_variable_is_added_to_the_field_and_a_plain_word_is_refused(apps: Any) -> None:
    page, made = _multi(apps, "")
    async with open_page(page) as user:
        (variable,) = [e for e in found(user, ui.input) if e.props.get("placeholder") == "%variable_name"]
        variable.value = "plain"
        await click(user, "Add")
        assert user.notify.contains("A variable name has to start with '%'")
        assert not any(
            text.startswith("Also in this field") and text != "" for text in label_texts(user) if "plain" in text
        )

        variable.value = "%app_package"
        await click(user, "Add")
        assert "Also in this field: %app_package" in label_texts(user)
        assert variable.value == "", "the entry is cleared for the next one"
        await click(user, "Use Selected")
        assert made[0].value == "%app_package"


@pytest.mark.asyncio
async def test_the_same_variable_added_twice_is_listed_once(apps: Any) -> None:
    page, made = _multi(apps, "%x")
    async with open_page(page) as user:
        (variable,) = [e for e in found(user, ui.input) if e.props.get("placeholder") == "%variable_name"]
        variable.value = "%x"
        await click(user, "Add")
        await click(user, "Use Selected")
        assert made[0].value == "%x"


@pytest.mark.asyncio
async def test_not_listed_fetches_keeping_the_ticks_and_reopens_over_the_new_inventory(
    apps: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fetch(gui: object, on_fetched: Callable[[], None]) -> None:
        apps.fetched.append(gui)
        on_fetched()

    monkeypatch.setattr(guiwins_taskedit, "_build_fetch_apps_dialog", fetch)
    page, made = _multi(apps, "com.whatsapp")
    async with open_page(page) as user:
        await click(user, "App not listed?")
        assert apps.fetched == [apps.window]
        assert made[0].value == "com.whatsapp", "the ticks were written into the field before the fetch"
        assert len(found(user, ui.dialog)) >= 1


# ##################################################################################
# One application for a condition
# ##################################################################################
def _single(apps: Any, picked: list[appinv.AppEntry]) -> Callable[[], None]:
    def page() -> None:
        guiwins_taskedit._build_app_entry_picker_dialog(picked.append, apps.window)

    return page


@pytest.mark.asyncio
async def test_picking_one_hands_back_the_whole_triple_and_closes(apps: Any) -> None:
    picked: list[appinv.AppEntry] = []
    async with open_page(_single(apps, picked)) as user:
        await click(user, "WhatsApp  (com.whatsapp)")
        assert picked == [_APPS[1]]
        (dialog,) = found(user, ui.dialog)
        assert not dialog.value


@pytest.mark.asyncio
async def test_the_single_picker_searches_and_cancels(apps: Any) -> None:
    picked: list[appinv.AppEntry] = []
    async with open_page(_single(apps, picked)) as user:
        _search(user).value = "camera"
        await asyncio.sleep(0.05)
        texts = [b.text for b in found(user, ui.button)]
        assert "Camera  (com.android.camera)" in texts and "WhatsApp  (com.whatsapp)" not in texts
        _search(user).value = "zzz"
        await asyncio.sleep(0.05)
        assert "Nothing here." in label_texts(user)
        await click(user, "Cancel")
        assert picked == []


@pytest.mark.asyncio
async def test_a_variable_becomes_an_entry_with_the_variable_as_package_and_label(apps: Any) -> None:
    picked: list[appinv.AppEntry] = []
    async with open_page(_single(apps, picked)) as user:
        (variable,) = [e for e in found(user, ui.input) if e.props.get("placeholder") == "%variable_name"]
        variable.value = "%App(%par1)"
        await click(user, "Use")
        assert picked == [appinv.variable_app_entry("%App(%par1)")]


@pytest.mark.asyncio
async def test_the_pick_button_fills_all_three_fields_from_the_chosen_application(
    apps: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    refs: dict[str, ui.input] = {}

    def page() -> None:
        for key in ("pkg", "label", "cls"):
            refs[key] = ui.input(label=key)
        guiwins_taskedit._render_app_entry_pick_button(apps.window, refs, "pkg", "label", "cls")

    async with open_page(page) as user:
        await click(user, "Pick")
        await click(user, "Camera  (com.android.camera)")
        assert (refs["pkg"].value, refs["label"].value, refs["cls"].value) == (
            "com.android.camera",
            "Camera",
            "com.android.camera.Main",
        )


@pytest.mark.asyncio
async def test_with_no_inventory_there_is_no_pick_button(apps: Any) -> None:
    apps.entries = []

    def page() -> None:
        guiwins_taskedit._render_app_entry_pick_button(apps.window, {}, "p", "l", "c")

    async with open_page(page) as user:
        assert [e for e in all_elements(user) if isinstance(e, ui.button)] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("for_icons", "label"), [(False, "App not listed?"), (True, "Icon not listed?")])
async def test_the_not_listed_button_is_worded_for_what_the_user_is_looking_for(for_icons: bool, label: str) -> None:
    clicked: list[bool] = []

    def page() -> None:
        guiwins_taskedit._render_fetch_apps_button(lambda: clicked.append(True), for_icons)

    async with open_page(page) as user:
        await click(user, label)
        assert clicked == [True]
