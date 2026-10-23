"""The smaller dialogs: Health Check's panel, the helper-Task reports, Overwrite, Changes Since, Rename and Delete Project.

Each is opened in a simulated window and driven the way a person does -- read the labels, tick a box, press
a button -- so what is asserted is what is on screen and what the dialog hands back, not how it is built.
The reports the dialogs sit in front of are healthck's, timeline's and projedit's, with tests of their own.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
from maptasker.src.analysis import healthck
from maptasker.src.core import appinv, clock, timeline
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import guiwins_dialogs
from nicegui import ui

from tests.nicegui_harness import all_elements, click, dialogs, found, label_texts, open_page

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui.testing.user import User


# ##################################################################################
# What the plugin check is compared against
# ##################################################################################
def test_with_no_app_list_fetched_it_says_plugins_cannot_be_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(appinv, "fetched_devices", list)

    assert "No app list has been fetched" in guiwins_dialogs._app_list_status()


def test_one_fetched_list_is_named_with_its_date_and_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(appinv, "fetched_devices", lambda: [("Pixel 9", "2026-10-01", 312)])

    status = guiwins_dialogs._app_list_status()

    assert status == "Plugins are checked against the app list from Pixel 9: 312 applications, fetched 2026-10-01"


def test_several_fetched_lists_are_listed_one_to_a_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(appinv, "fetched_devices", lambda: [("Pixel", "2026-10-01", 3), ("Tablet", "2026-09-01", 4)])

    lines = guiwins_dialogs._app_list_status().splitlines()

    assert lines[0] == "Plugins are checked against the app lists from:"
    assert lines[1].startswith("Pixel: 3") and lines[2].startswith("Tablet: 4")


# ##################################################################################
# Health Check's panel
# ##################################################################################
@pytest.fixture
def health(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    record = SimpleNamespace(run=[], save=[], refreshed=[])
    monkeypatch.setattr(appinv, "fetched_devices", list)

    async def fetch(gui: object, done: Callable[[], None]) -> None:
        record.refreshed.append(gui)
        done()

    monkeypatch.setattr(guiwins_dialogs, "_build_fetch_apps_dialog", fetch)
    return record


def _health_page(record: SimpleNamespace, skipped: list[str] | None = None) -> Callable[[], None]:
    state = RunState()
    state.program_arguments.health_check_skip = skipped or []

    def page() -> None:
        guiwins_dialogs.build_health_check_dialog(
            lambda skip: record.run.append(skip), lambda skip: record.save.append(skip), cast("Any", "window"), state
        )

    return page


def _boxes(user: User) -> list[ui.checkbox]:
    return list(found(user, ui.checkbox))


def _tag_of(box: ui.checkbox) -> str:
    """The category a checkbox stands for: the first label in the row it sits in."""
    assert box.parent_slot is not None
    row = box.parent_slot.parent
    return next(e.text for e in row.descendants() if isinstance(e, ui.label))


def _box_for(user: User, tag: str) -> ui.checkbox:
    (box,) = [b for b in _boxes(user) if _tag_of(b) == tag]
    return box


@pytest.mark.asyncio
async def test_every_category_starts_ticked_so_the_default_reports_everything(health: SimpleNamespace) -> None:
    async with open_page(_health_page(health)) as user:
        boxes = _boxes(user)
        assert len(boxes) == len(healthck.CATEGORIES)
        assert all(box.value for box in boxes)


@pytest.mark.asyncio
async def test_categories_left_out_last_time_come_back_unticked(health: SimpleNamespace) -> None:
    first = healthck.CATEGORIES[0].tag
    async with open_page(_health_page(health, [first])) as user:
        assert _box_for(user, first).value is False
        assert all(box.value for box in _boxes(user) if _tag_of(box) != first)


@pytest.mark.asyncio
async def test_unticking_one_box_saves_the_choice_as_it_is_made(health: SimpleNamespace) -> None:
    async with open_page(_health_page(health)) as user:
        _box_for(user, healthck.CATEGORIES[2].tag).value = False
        await asyncio.sleep(0.1)
        assert health.save == [[healthck.CATEGORIES[2].tag]]


@pytest.mark.asyncio
async def test_deselect_all_saves_once_not_once_per_box(health: SimpleNamespace) -> None:
    async with open_page(_health_page(health)) as user:
        await click(user, "Deselect All")
        assert len(health.save) == 1
        assert len(health.save[0]) == len(healthck.CATEGORIES)
        assert not any(box.value for box in _boxes(user))
        await click(user, "Select All")
        assert health.save[-1] == []
        assert all(box.value for box in _boxes(user))


@pytest.mark.asyncio
async def test_run_closes_the_panel_and_hands_over_what_is_unticked(health: SimpleNamespace) -> None:
    async with open_page(_health_page(health)) as user:
        _box_for(user, healthck.CATEGORIES[0].tag).value = False
        await asyncio.sleep(0.1)
        await click(user, "Run")
        assert health.run == [[healthck.CATEGORIES[0].tag]]
        assert not dialogs(user)[0].value


@pytest.mark.asyncio
async def test_cancel_closes_the_panel_without_running(health: SimpleNamespace) -> None:
    async with open_page(_health_page(health)) as user:
        await click(user, "Cancel")
        assert health.run == []
        assert not dialogs(user)[0].value


@pytest.mark.asyncio
async def test_refresh_app_list_fetches_and_then_restates_what_the_check_uses(
    health: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with open_page(_health_page(health)) as user:
        assert any("No app list has been fetched" in text for text in label_texts(user))
        monkeypatch.setattr(appinv, "fetched_devices", lambda: [("Pixel", "2026-10-01", 5)])
        await click(user, "Refresh App List")
        assert health.refreshed == ["window"]
        assert any("Pixel: 5 applications" in text for text in label_texts(user))


# ##################################################################################
# The helper Tasks left on the device
# ##################################################################################
@pytest.mark.asyncio
async def test_stale_helpers_are_named_and_the_current_ones_marked_as_in_use() -> None:
    async with open_page(
        lambda: guiwins_dialogs.build_helper_tasks_dialog(["Old v1", "Old v2"], ["Now v3"], "Pixel")
    ) as user:
        labels = label_texts(user)
        assert "On Pixel" in labels
        assert any(text.startswith("2 left over from an earlier version") for text in labels)
        assert {"Old v1", "Old v2", "Now v3"} <= set(labels)
        assert "In use -- leave these alone:" in labels
        await click(user, "Close")
        assert not dialogs(user)[0].value


@pytest.mark.asyncio
async def test_with_nothing_stale_it_says_nothing_is_left_over() -> None:
    async with open_page(lambda: guiwins_dialogs.build_helper_tasks_dialog([], [], "Pixel")) as user:
        assert "Nothing left over -- every MapTasker Task on the device is in use." in label_texts(user)
        assert "In use -- leave these alone:" not in label_texts(user)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("project_exists", "advice"),
    [
        (True, "Tasker already has a 'MapTasker' Project."),
        (None, "Delete them in Tasker -- or delete the 'MapTasker' Project"),
        (False, "Delete them from Tasker's Tasks tab"),
    ],
)
async def test_the_advice_for_helpers_in_the_way_depends_on_whether_the_project_is_there(
    project_exists: bool | None, advice: str
) -> None:
    def page() -> None:
        guiwins_dialogs.build_helpers_in_the_way_dialog(["Helper A"], "Pixel", project_exists)

    async with open_page(page) as user:
        labels = label_texts(user)
        assert "Helper A" in labels
        assert any(text.startswith(advice) for text in labels)
        await click(user, "Close")
        assert not dialogs(user)[0].value


# ##################################################################################
# Overwrite
# ##################################################################################
def _overwrite_page(**options: Any) -> tuple[Callable[[], None], list[str]]:
    confirmed: list[str] = []

    def page() -> None:
        guiwins_dialogs.build_overwrite_confirm_dialog("/Tasker/x.prf.xml", lambda: confirmed.append("yes"), **options)

    return page, confirmed


@pytest.mark.asyncio
async def test_overwrite_says_the_file_will_be_replaced_and_waits_for_the_answer() -> None:
    page, confirmed = _overwrite_page()
    async with open_page(page) as user:
        assert "Already exists" in label_texts(user)
        assert "/Tasker/x.prf.xml already exists and will be replaced." in label_texts(user)
        assert confirmed == []
        await click(user, "Overwrite")
        assert confirmed == ["yes"]
        assert not dialogs(user)[0].value


@pytest.mark.asyncio
async def test_overwrite_cancel_writes_nothing() -> None:
    page, confirmed = _overwrite_page()
    async with open_page(page) as user:
        await click(user, "Cancel")
        assert confirmed == []
        assert not dialogs(user)[0].value


@pytest.mark.asyncio
async def test_a_destination_that_could_not_be_checked_says_saving_may_overwrite() -> None:
    page, _confirmed = _overwrite_page(unknown=True)
    async with open_page(page) as user:
        assert "Could not check destination" in label_texts(user)
        assert any("Saving may overwrite it." in text for text in label_texts(user))


@pytest.mark.asyncio
async def test_a_prompt_raised_by_tasker_alone_offers_continue_and_names_what_tasker_has() -> None:
    page, confirmed = _overwrite_page(file_absent=True, tasker_lines=["Profile 'A' is already in Tasker."])
    async with open_page(page) as user:
        assert "Already in Tasker" in label_texts(user)
        assert "Profile 'A' is already in Tasker." in label_texts(user)
        assert not any("will be replaced" in text for text in label_texts(user))
        await click(user, "Continue")
        assert confirmed == ["yes"]


@pytest.mark.asyncio
async def test_a_confirmation_that_is_a_coroutine_is_run_to_the_end() -> None:
    finished: list[str] = []

    async def write() -> None:
        await asyncio.sleep(0)
        finished.append("written")

    async with open_page(lambda: guiwins_dialogs.build_overwrite_confirm_dialog("f", write)) as user:
        await click(user, "Overwrite")
        assert finished == ["written"]


# ##################################################################################
# Changes Since
# ##################################################################################
@pytest.mark.asyncio
async def test_changes_since_hands_over_the_period_chosen_and_closes_first() -> None:
    chosen: list[tuple[str, date | None]] = []

    async def on_choose(period: str, on_date: date | None) -> None:
        chosen.append((period, on_date))

    async with open_page(lambda: guiwins_dialogs.build_changes_since_dialog(on_choose)) as user:
        (select,) = found(user, ui.select)
        assert select.value == timeline.THIS_WEEK
        await click(user, "Show Changes")
        assert chosen == [(timeline.THIS_WEEK, None)]
        assert not dialogs(user)[0].value


@pytest.mark.asyncio
async def test_changes_since_cancel_asks_for_nothing() -> None:
    chosen: list[object] = []

    async def on_choose(period: str, on_date: date | None) -> None:
        chosen.append(period)

    async with open_page(lambda: guiwins_dialogs.build_changes_since_dialog(on_choose)) as user:
        await click(user, "Cancel")
        assert chosen == []


@pytest.mark.asyncio
async def test_a_specific_date_must_be_picked_and_must_have_happened() -> None:
    chosen: list[tuple[str, date | None]] = []

    async def on_choose(period: str, on_date: date | None) -> None:
        chosen.append((period, on_date))

    async with open_page(lambda: guiwins_dialogs.build_changes_since_dialog(on_choose)) as user:
        notified = user.notify.messages
        (select,) = found(user, ui.select)
        (picker,) = [e for e in all_elements(user) if isinstance(e, ui.date)]
        select.value = timeline.ON_DATE
        picker.value = None

        await click(user, "Show Changes")
        assert notified == ["Choose a date first."]

        picker.value = (clock.now().date() + timedelta(days=2)).isoformat()
        await click(user, "Show Changes")
        assert notified[-1].startswith("That date is in the future")
        assert chosen == []

        picker.value = "2026-01-15"
        await click(user, "Show Changes")
        assert chosen == [(timeline.ON_DATE, date(2026, 1, 15))]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026-03-04", date(2026, 3, 4)), ("", None), (None, None), ("not-a-date", None), (20260304, None)],
)
def test_the_picked_date_is_a_date_or_nothing(value: object, expected: date | None) -> None:
    assert guiwins_dialogs._parse_picked_date(value) == expected


# ##################################################################################
# Rename
# ##################################################################################
@pytest.mark.asyncio
async def test_rename_offers_the_current_name_and_hands_the_typed_one_over_trimmed() -> None:
    renamed: list[str] = []

    def on_rename(name: str, dialog: ui.dialog) -> None:
        renamed.append(name)

    def page() -> None:
        guiwins_dialogs.build_rename_dialog(MagicMock(), "Task", "Old Name", on_rename)

    async with open_page(page) as user:
        assert "Rename Task 'Old Name'" in label_texts(user)
        (field,) = found(user, ui.input)
        assert field.value == "Old Name"
        field.value = "  New Name  "
        await click(user, "Rename")
        assert renamed == ["New Name"]
        assert dialogs(user)[0].value, "closing is left to the handler, so a refused name keeps the prompt up"


@pytest.mark.asyncio
async def test_rename_cancel_closes_only_the_prompt() -> None:
    renamed: list[str] = []

    def page() -> None:
        guiwins_dialogs.build_rename_dialog(MagicMock(), "Profile", "P", lambda name, dialog: renamed.append(name))

    async with open_page(page) as user:
        await click(user, "Cancel")
        assert renamed == []
        assert not dialogs(user)[0].value


# ##################################################################################
# Delete Project
# ##################################################################################
@pytest.mark.asyncio
async def test_delete_project_offers_both_ways_and_hands_each_to_the_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    panels: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        guiwins_dialogs,
        "build_impact_panel",
        lambda gui, kind, name, keep_contents, wire: panels.append((name, keep_contents)),
    )
    monkeypatch.setattr(guiwins_dialogs, "wire_impact_clicks", lambda gui, area: None)
    editors = MagicMock()
    window = SimpleNamespace(event_handlers=SimpleNamespace(editors=editors))
    parent = MagicMock()

    def page() -> None:
        guiwins_dialogs.build_delete_project_dialog(window, SimpleNamespace(project_name="Home"), parent)  # type: ignore[arg-type]

    async with open_page(page) as user:
        assert "Delete Project 'Home'" in label_texts(user)
        assert panels == [("Home", True), ("Home", False)], "each choice is analysed on its own"
        await click(user, "Keep Contents")
        await click(user, "Delete Contents")
        editors.keep_contents_delete_project_event.assert_called_once()
        assert editors.keep_contents_delete_project_event.call_args.args[0] == "Home"
        editors.delete_contents_delete_project_event.assert_called_once()
        assert editors.delete_contents_delete_project_event.call_args.args[2] is parent
        await click(user, "Cancel")
        assert not dialogs(user)[0].value
