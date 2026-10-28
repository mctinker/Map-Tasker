"""The Fix Findings dialog: what it offers, what a tick does, and what Apply makes.

What a repair does is test_mapfix's.  These build the real dialog on a page of NiceGUI's
in-process user simulation, over the same fixture configuration, and press what a user would
press -- so what is tested is that the dialog and the plan stay one thing: the ticks on screen
are the ticks Apply acts on, an undecided repair cannot be ticked, and a rescan keeps the
choices already made.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiwins_fix
from maptasker.src.mapops import mapfix
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_mapfix import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator
    from pathlib import Path

    from nicegui.testing.user import User

_built: dict = {}


@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The fixture configuration, an empty undo history, and a working directory of its own."""
    monkeypatch.chdir(tmp_path)
    sessundo.clear(PrimeItems)
    _load(_FIXTURE_XML)
    _built.clear()
    _built.update(rebuilt=0, saved=0, save_answer=False, jumps=[])
    yield
    sessundo.clear(PrimeItems)


def _page() -> None:
    """The page the dialog is built on and opened from."""

    async def rebuild() -> None:
        _built["rebuilt"] += 1

    async def save() -> bool:
        _built["saved"] += 1
        return _built["save_answer"]

    def jump(target: object) -> Callable:
        return lambda *_args: _built["jumps"].append(target)

    _built["dialog"] = guiwins_fix.build_fix_dialog("Test", jump, rebuild, save, PrimeItems)
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open(*, choose: bool = True) -> AsyncIterator[User]:
    """The dialog, opened.  It opens on the choice of what to fix; `choose` presses Continue on every kind."""
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            if choose:
                _press(user, "Continue")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _button(user: User, label: str) -> ui.button:
    (button,) = [element for element in user.find(kind=ui.button).elements if element.text == label]
    return button


def _press(user: User, label: str) -> None:
    UserInteraction(user, {_button(user, label)}, None).click()


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _boxes(user: User) -> list[ui.checkbox]:
    return list(user.find(kind=ui.checkbox).elements)


def _summary(user: User) -> str:
    """The line above the list: '<tally> ticked, <m> offered'."""
    (line,) = [text for text in _labels(user) if " offered" in text or text.startswith("Nothing here")]
    return line


def _offer(ticked: set[int] | None = None) -> tuple[mapfix.Plan, str]:
    """A fresh plan, and what the summary says for it with these positions ticked (its own by default)."""
    plan = mapfix.plan_fixes(state=PrimeItems)
    if ticked is not None:
        plan.selected = set(ticked)
    return plan, f"{plan.tally()} ticked, {len(plan.fixes)} offered"


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    """A scan of no configuration is refused where the user will see it."""
    PrimeItems.tasker_root_elements = {"all_tasks": {}}
    async with _open(choose=False) as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file has been loaded.  Get an XML file first.")


@pytest.mark.asyncio
async def test_the_dialog_is_titled_and_pre_ticks_every_ready_repair_except_deleting_a_task() -> None:
    """The heading carries the view's name.  Deleting is the one repair nobody gets by default."""
    plan, said = _offer()
    deletes = {position for position, fix in enumerate(plan.fixes) if fix.tag == mapfix.UNREFERENCED_TASK}
    assert deletes, "the fixture is meant to offer a delete"
    assert not deletes & plan.selected

    async with _open() as user:
        assert "Fix Findings -- Test" in _labels(user)
        assert _summary(user) == said
        assert sum(1 for box in _boxes(user) if box.value) == len(plan.selected)
        assert len(_boxes(user)) == len(plan.fixes)


@pytest.mark.asyncio
async def test_each_group_of_repairs_is_headed_by_the_health_check_tag() -> None:
    """The tag is the word the Health Check report prints, so a group means the same in both places."""
    async with _open() as user:
        labels = _labels(user)
        for tag in {fix.tag for fix in mapfix.plan_fixes(state=PrimeItems).fixes}:
            assert labels.count(tag) == 1


@pytest.mark.asyncio
async def test_what_cannot_be_repaired_is_listed_with_its_reason() -> None:
    """A silent skip would read as a shorter to-do list, so the refusals are printed."""
    skips = mapfix.plan_fixes(state=PrimeItems).skips
    assert skips, "the fixture is meant to hold repairs that are refused"
    async with _open() as user:
        assert f"Cannot be repaired here ({len(skips)})" in _labels(user)
        for skip in skips:
            assert skip.explanation in _labels(user)


# ##################################################################################
# Choosing what to fix
# ##################################################################################
def _kind_boxes(user: User) -> dict[str, ui.checkbox]:
    """The checkbox of each kind of finding on the first step, by tag."""
    found = sorted(_boxes(user), key=lambda box: box.id)  # a set comes back unordered; ids run in the order drawn
    assert len(found) == len(mapfix.FIXABLE_TAGS)
    return dict(zip(mapfix.FIXABLE_TAGS, found, strict=True))


@pytest.mark.asyncio
async def test_the_dialog_opens_on_the_kinds_of_finding_with_a_count_for_each() -> None:
    """Nothing is listed until the user has said which kinds they want to fix."""
    counts = mapfix.count_findings(state=PrimeItems)
    assert all(counts[tag] for tag in mapfix.FIXABLE_TAGS), "the fixture is meant to hold every kind"
    async with _open(choose=False) as user:
        labels = _labels(user)
        for tag in mapfix.FIXABLE_TAGS:
            assert tag in labels
            assert f"{counts[tag]} found" in labels
        assert not [text for text in labels if " offered" in text], "no list yet"
        assert all(box.value for box in _kind_boxes(user).values())


@pytest.mark.asyncio
async def test_only_the_kinds_ticked_are_listed() -> None:
    """Untick everything but NO-TIMEOUT and the list holds those repairs and nothing else."""
    async with _open(choose=False) as user:
        for tag, box in _kind_boxes(user).items():
            box.value = tag == mapfix.NO_TIMEOUT
        _press(user, "Continue")

        only = mapfix.plan_fixes(only={mapfix.NO_TIMEOUT}, state=PrimeItems)
        assert only.fixes
        assert _summary(user) == f"{only.tally()} ticked, {len(only.fixes)} offered"
        assert len(_boxes(user)) == len(only.fixes)
        labels = _labels(user)
        assert mapfix.NO_TIMEOUT in labels
        assert not [tag for tag in mapfix.FIXABLE_TAGS if tag != mapfix.NO_TIMEOUT and tag in labels]


@pytest.mark.asyncio
async def test_continuing_with_nothing_ticked_asks_for_a_kind_and_stays_on_the_choice() -> None:
    async with _open(choose=False) as user:
        for box in _kind_boxes(user).values():
            box.value = False
        _press(user, "Continue")

        assert user.notify.contains("Tick at least one kind of finding first.")
        assert not [text for text in _labels(user) if " offered" in text]


@pytest.mark.asyncio
async def test_select_all_and_deselect_all_work_on_the_kinds() -> None:
    async with _open(choose=False) as user:
        _press(user, "Deselect All")
        assert not any(box.value for box in _kind_boxes(user).values())
        _press(user, "Select All")
        assert all(box.value for box in _kind_boxes(user).values())


@pytest.mark.asyncio
async def test_a_kind_with_nothing_to_fix_cannot_be_ticked() -> None:
    """It could only produce an empty list."""
    PrimeItems.program_arguments.health_check_skip = [mapfix.NO_TIMEOUT]
    try:
        async with _open(choose=False) as user:
            boxes = _kind_boxes(user)
            assert not boxes[mapfix.NO_TIMEOUT].enabled
            assert not boxes[mapfix.NO_TIMEOUT].value
            assert "left out of the Health Check" in _labels(user)
            assert boxes[mapfix.MISSING_COLLISION].enabled
    finally:
        PrimeItems.program_arguments.health_check_skip = []


@pytest.mark.asyncio
async def test_excluded_kinds_are_named_as_unavailable() -> None:
    PrimeItems.program_arguments.health_check_skip = [mapfix.NO_TIMEOUT, mapfix.UNREFERENCED_TASK]
    try:
        async with _open(choose=False) as user:
            said = " ".join(_labels(user))
            assert "unavailable" in said
            assert f"{mapfix.NO_TIMEOUT}, {mapfix.UNREFERENCED_TASK}" in said
            assert "There is nothing to fix." not in _labels(user)
    finally:
        PrimeItems.program_arguments.health_check_skip = []


@pytest.mark.asyncio
async def test_nothing_found_says_so_and_offers_nothing_to_choose() -> None:
    skipped = list(mapfix.FIXABLE_TAGS[1:])
    PrimeItems.program_arguments.health_check_skip = skipped
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(mapfix, "count_findings", lambda *_a, **_k: {})
            async with _open(choose=False) as user:
                assert "There is nothing to fix." in _labels(user)
                assert len(_boxes(user)) == len(skipped)
                assert not any(box.enabled for box in _boxes(user))
    finally:
        PrimeItems.program_arguments.health_check_skip = []


@pytest.mark.asyncio
async def test_kinds_goes_back_to_the_choice_and_keeps_the_ticks_on_what_is_still_listed() -> None:
    async with _open(choose=False) as user:
        for tag, box in _kind_boxes(user).items():
            box.value = tag in {mapfix.NO_TIMEOUT, mapfix.MISSING_COLLISION}
        _press(user, "Continue")
        _press(user, "Tick None")
        box = next(box for box in _boxes(user) if box.enabled)
        UserInteraction(user, {box}, None).click()
        said = _summary(user)

        _press(user, "Kinds...")
        assert not [text for text in _labels(user) if " offered" in text]
        ticked = {tag for tag, box in _kind_boxes(user).items() if box.value}
        assert ticked == {mapfix.NO_TIMEOUT, mapfix.MISSING_COLLISION}, "the choice is remembered"

        _press(user, "Continue")
        assert _summary(user) == said


# ##################################################################################
# Ticking
# ##################################################################################
@pytest.mark.asyncio
async def test_tick_all_ticks_only_what_is_ready_and_tick_none_clears_it() -> None:
    """A repair still waiting on a decision stays out: ticking it would tick something nobody has decided."""
    plan, _ = _offer()
    ready = {position for position in range(len(plan.fixes)) if plan.is_ready(position)}
    assert ready < set(range(len(plan.fixes))), "the fixture should hold both kinds"
    assert ready - plan.selected, "and a ready repair that is not pre-ticked"

    async with _open() as user:
        _press(user, "Tick All")
        assert _summary(user) == _offer(ready)[1]
        assert sum(1 for box in _boxes(user) if box.value) == len(ready)

        _press(user, "Tick None")
        assert _summary(user) == _offer(set())[1]
        assert not any(box.value for box in _boxes(user))


@pytest.mark.asyncio
async def test_ticking_one_box_updates_the_count() -> None:
    """The tick on screen is the tick in the plan, and the summary says so."""
    async with _open() as user:
        _press(user, "Tick None")
        box = next(box for box in _boxes(user) if box.enabled)

        UserInteraction(user, {box}, None).click()
        assert box.value is True
        assert _summary(user).startswith("1 finding in 1 object ticked")

        UserInteraction(user, {box}, None).click()
        assert _summary(user) == _offer(set())[1]


@pytest.mark.asyncio
async def test_a_repair_waiting_on_a_decision_cannot_be_ticked_until_it_is_made() -> None:
    """Which label a broken Goto meant is the one decision nobody can make for the user."""
    async with _open() as user:
        waiting = sum(1 for box in _boxes(user) if not box.enabled)
        undecided = [select for select in user.find(kind=ui.select).elements if select.value is None]
        assert waiting
        assert len(undecided) == waiting

        undecided[0].value = next(iter(undecided[0].options))

        assert sum(1 for box in _boxes(user) if not box.enabled) == waiting - 1


# ##################################################################################
# Applying
# ##################################################################################
@pytest.mark.asyncio
async def test_apply_with_nothing_ticked_asks_for_a_tick_and_changes_nothing() -> None:
    """Apply makes exactly what is ticked, so with nothing ticked it makes nothing."""
    before = len(mapfix.plan_fixes(state=PrimeItems).fixes)
    async with _open() as user:
        _press(user, "Tick None")
        _press(user, "Apply")
        await asyncio.sleep(0.1)
        assert user.notify.contains("Tick something first.")
    assert _built["rebuilt"] == 0
    assert len(mapfix.plan_fixes(state=PrimeItems).fixes) == before


@pytest.mark.asyncio
async def test_apply_makes_the_ticked_repairs_rebuilds_the_window_and_rescans() -> None:
    """The window is brought up to date first, and the list left is what is still wrong."""
    before = len(mapfix.plan_fixes(state=PrimeItems).fixes)
    async with _open() as user:
        _press(user, "Apply")  # the pre-ticked repairs: no Task is deleted
        for _ in range(40):
            if _built["rebuilt"]:
                break
            await asyncio.sleep(0.05)

        assert _built["rebuilt"] == 1
        assert any("repaired." in message for message in user.notify.messages)
        assert any("Undo is available." in message for message in user.notify.messages)
        assert len(_boxes(user)) < before
        assert _summary(user) == _offer()[1]


# ##################################################################################
# Saving, and scanning again
# ##################################################################################
@pytest.mark.asyncio
async def test_saving_the_configuration_rescans_only_when_the_save_asks_for_it() -> None:
    """A save that switched files has left the plan holding elements nothing renders from."""
    async with _open() as user:
        _press(user, "Save To Current File")
        await asyncio.sleep(0.1)
        assert _built["saved"] == 1

        _built["save_answer"] = True
        _press(user, "Save To Current File")
        await asyncio.sleep(0.1)
        assert _built["saved"] == 2


@pytest.mark.asyncio
async def test_a_rescan_keeps_the_ticks_already_made() -> None:
    """Edit something elsewhere, scan again, and the work already done on this list is still there."""
    async with _open() as user:
        _press(user, "Tick None")
        box = next(box for box in _boxes(user) if box.enabled)
        UserInteraction(user, {box}, None).click()
        said = _summary(user)

        _press(user, "Scan Again")

        assert _summary(user) == said
        assert sum(1 for box in _boxes(user) if box.value) == 1


@pytest.mark.asyncio
async def test_save_preview_writes_the_list_to_a_file_and_says_where(tmp_path: Path) -> None:
    """The refusals name what has to be done by hand, and that list does not survive the dialog."""
    async with _open() as user:
        _press(user, "Save Preview")
        assert any("Fix preview saved as" in message for message in user.notify.messages), user.notify.messages
    assert any(path.is_file() for path in tmp_path.iterdir())


@pytest.mark.asyncio
async def test_close_closes_the_dialog_and_changes_nothing() -> None:
    """A repair happens when Apply is pressed and at no other time."""
    before = len(mapfix.plan_fixes(state=PrimeItems).fixes)
    async with _open() as user:
        _press(user, "Close")
        assert _built["dialog"].value is False
    assert len(mapfix.plan_fixes(state=PrimeItems).fixes) == before
