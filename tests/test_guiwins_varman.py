"""MapTasker Variable Manager window (guiwins_varman) Unit Tests

mapvars is tested on its own; what is tested here is the window over it: that the table shows what mapvars says, that
choosing a row enables the buttons and lists where the variable is used, that each change goes through a preview and
applies only what was previewed, and that reading from and pushing to the phone do what they say and nothing more.

The phone is a stand-in at the two functions the window calls (livevars.fetch_live_values and livevars.set_global),
whose own behaviour is tests/test_livevars.py's.
"""

from __future__ import annotations

import asyncio
import contextlib
import types
from typing import TYPE_CHECKING, Any, cast

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiwins_varman, livevars
from maptasker.src.mapops import mapvars
from nicegui import core, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.shared_fixtures import _load_local
from tests.test_mapvars import _XML

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

pytestmark = pytest.mark.usefixtures("_runtime")

_built: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _patient_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give should_see four seconds: the phone calls run on a worker thread and answer on a later pass of the loop."""
    original = User.should_see

    async def should_see(self: User, *args: Any, retries: int = 40, **kwargs: Any) -> None:
        await original(self, *args, retries=retries, **kwargs)

    monkeypatch.setattr(User, "should_see", should_see)
    # What remembering an address does is the address helpers' own business, and it writes the settings file.
    monkeypatch.setattr(guiwins_varman, "remember_android_address", lambda *_args: None)
    monkeypatch.setattr(guiwins_varman, "remember_android_address_fields", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(guiwins_varman, "android_address_defaults", lambda _gui: ("192.168.0.210", "1821"))


def _page() -> None:
    async def save() -> bool:
        _built["saved"] = _built.get("saved", 0) + 1
        return True

    def jump(_target: object) -> Callable:
        return lambda *_args: None

    gui = types.SimpleNamespace(state=PrimeItems)
    manager = guiwins_varman.VariableManager(gui, jump, save, PrimeItems)  # type: ignore[arg-type]
    _built["manager"] = manager
    manager.build().open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _load(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)


def _buttons(user: User, label: str) -> list[ui.button]:
    return [element for element in user.find(kind=ui.button).elements if element.text == label]


def _only(user: User, label: str) -> ui.button:
    (button,) = _buttons(user, label)
    return button


def _newest(user: User, label: str) -> ui.button:
    """The enabled button of this name made last: the dialog's, not the window's own of the same name."""
    return max((b for b in _buttons(user, label) if b.enabled), key=lambda button: button.id)


def _press(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _table(user: User) -> ui.table:
    (table,) = user.find(kind=ui.table).elements
    return table


async def _until(condition: Callable[[], object]) -> None:
    for _ in range(60):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


# ##################################################################################
# The window
# ##################################################################################
@pytest.mark.asyncio
async def test_the_window_lists_every_global_and_counts_the_marks(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        rows = _table(user).rows
        summary = next(text for text in _labels(user) if "global variables" in text)

    assert {row["name"] for row in rows} >= {"%Mode", "%Orphan", "%Wanted", "%Spare"}
    assert "is set but never read" in summary
    assert "unused" in summary


@pytest.mark.asyncio
async def test_a_declared_variable_shows_its_value_and_type_and_an_undeclared_one_shows_neither(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        by_name = {row["name"]: row for row in _table(user).rows}

    assert (by_name["%Count"]["value"], by_name["%Count"]["type"]) == ("12", "Number")
    assert (by_name["%Flag"]["value"], by_name["%Flag"]["type"]) == ("true", "True/False")
    assert by_name["%Json"]["type"] == "JSON"
    assert (by_name["%Orphan"]["value"], by_name["%Orphan"]["type"]) == ("", "")


@pytest.mark.asyncio
async def test_the_marks_are_in_words(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        by_name = {row["name"]: row for row in _table(user).rows}

    assert by_name["%Orphan"]["flag"] == "Is set but never read"
    assert by_name["%Wanted"]["flag"] == "Is read but never set"
    assert by_name["%Spare"]["flag"] == "Unused"
    assert by_name["%Mode"]["flag"] == ""


def _filter(user: User, flag: str) -> ui.button:
    """The button that limits the table to one mark -- found by the mark it was made for, not by its changing label."""
    return _built["manager"].filter_buttons[flag]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        (mapvars.NEVER_READ, {"%Orphan", "%Logged"}),
        (mapvars.NEVER_SET, {"%Wanted"}),
        (mapvars.UNUSED, {"%Spare", "%Flag", "%Json"}),
    ],
)
async def test_each_filter_button_shows_only_its_own_kind(tmp_path: Path, flag: str, expected: set[str]) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        every = len(_table(user).rows)
        _press(user, _filter(user, flag))
        shown = {row["name"] for row in _table(user).rows}

    assert expected <= shown
    assert len(shown) < every
    assert "%Mode" not in shown
    assert {row["flag"] for row in _table(user).rows} <= {guiwins_varman._flag_words()[flag]}


@pytest.mark.asyncio
async def test_pressing_the_filter_in_force_or_show_all_brings_back_every_variable(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        every = len(_table(user).rows)
        _press(user, _filter(user, mapvars.NEVER_SET))
        assert len(_table(user).rows) < every
        _press(user, _filter(user, mapvars.NEVER_SET))
        assert len(_table(user).rows) == every, "the same button again lifts the limit"
        _press(user, _filter(user, mapvars.UNUSED))
        _press(user, _filter(user, ""))
        assert len(_table(user).rows) == every, "Show All lifts it too"


@pytest.mark.asyncio
async def test_the_filter_buttons_say_how_many_each_will_show(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        every = len(_table(user).rows)
        texts = {flag: button.text for flag, button in _built["manager"].filter_buttons.items()}

    assert texts[""] == f"Show All ({every})"
    assert texts[mapvars.NEVER_READ] == "Is set but never read (2)"
    assert texts[mapvars.NEVER_SET] == "Is read but never set (1)"


@pytest.mark.asyncio
async def test_the_button_in_force_is_filled_in_and_the_others_are_outlined(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _filter(user, mapvars.UNUSED))
        outlined = {flag: "outline" in button.props for flag, button in _built["manager"].filter_buttons.items()}

    assert outlined[mapvars.UNUSED] is False
    assert outlined[""] is True
    assert outlined[mapvars.NEVER_READ] is True


@pytest.mark.asyncio
async def test_the_buttons_wait_for_a_variable_to_be_chosen(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        names = ("Rename", "Change Value", "Delete", "Send To Phone")
        before = [_only(user, name).enabled for name in names]
        _built["manager"].choose(_built["manager"].rows[0])
        after = [_only(user, name).enabled for name in names]

    assert before == [False] * 4
    assert after == [True] * 4


@pytest.mark.asyncio
async def test_a_chosen_variable_lists_where_it_is_set_and_read(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Mode"))
        links = [element.text for element in user.find(kind=ui.link).elements]

    assert any(text.startswith("set") and "Task 'Writer'" in text for text in links)
    assert any(text.startswith("read") and "Task 'Reader'" in text for text in links)


# ##################################################################################
# Changes, through their previews
# ##################################################################################
def _held(name: str) -> str | None:
    root = PrimeItems.xml_root
    assert root is not None
    return next((e.findtext("v") or "" for e in root.findall("Variable") if e.findtext("n") == name), None)


@pytest.mark.asyncio
async def test_changing_a_value_previews_then_applies_and_the_table_follows(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Count"))
        _press(user, _only(user, "Change Value"))
        await user.should_see("Change Value: %Count")
        (box,) = [e for e in user.find(kind=ui.textarea).elements if e.label == "Value"]
        box.value = "99"
        _press(user, _only(user, "Preview"))
        await user.should_see("ready to apply")
        assert _held("%Count") == "12", "a preview changes nothing"
        _press(user, _only(user, "Apply"))
        await _until(lambda: _held("%Count") == "99")
        await _until(lambda: next(r for r in _table(user).rows if r["name"] == "%Count")["value"] == "99")


@pytest.mark.asyncio
async def test_a_value_of_the_wrong_type_cannot_be_applied(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Count"))
        _press(user, _only(user, "Change Value"))
        await user.should_see("Change Value: %Count")
        (box,) = [e for e in user.find(kind=ui.textarea).elements if e.label == "Value"]
        box.value = "twelve"
        _press(user, _only(user, "Preview"))
        await user.should_see("cannot be done")
        assert not _only(user, "Apply").enabled

    assert _held("%Count") == "12"


@pytest.mark.asyncio
async def test_deleting_previews_then_removes_the_entry(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Spare"))
        _press(user, _only(user, "Delete"))
        await user.should_see("Delete %Spare")
        _press(user, _only(user, "Preview"))
        await user.should_see("ready to apply")
        assert _held("%Spare") == "x"
        _press(user, _newest(user, "Delete"))
        await _until(lambda: _held("%Spare") is None)


@pytest.mark.asyncio
async def test_renaming_previews_then_rewrites_every_use(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Mode"))
        _press(user, _only(user, "Rename"))
        await user.should_see("Rename %Mode")
        (box,) = [e for e in user.find(kind=ui.input).elements if e.label == "New name"]
        box.value = "%Phase"
        _press(user, _only(user, "Preview"))
        await user.should_see("ready to apply")
        _press(user, _newest(user, "Rename"))
        await _until(lambda: _held("%Phase") == "night")
        await _until(lambda: any(r["name"] == "%Phase" for r in _table(user).rows))


# ##################################################################################
# The phone
# ##################################################################################
@pytest.mark.asyncio
async def test_reading_from_the_phone_fills_its_column_and_says_which_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _load(tmp_path)
    live = livevars.LiveValues("192.168.0.210:1821", {"%Mode": "evening", "%Count": "12"})
    monkeypatch.setattr(livevars, "fetch_live_values", lambda _ip, _port: (0, "", live))

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Get From Phone"))
        await user.should_see("Reads the current value")
        _press(user, _only(user, "Get Values"))
        await _until(lambda: next(r for r in _table(user).rows if r["name"] == "%Mode")["phone"])
        by_name = {row["name"]: row for row in _table(user).rows}

    assert "evening" in by_name["%Mode"]["phone"]
    assert "differs from the file" in by_name["%Mode"]["phone"]
    assert "differs" not in by_name["%Count"]["phone"]
    assert by_name["%Spare"]["phone"] == "not found on the phone"


@pytest.mark.asyncio
async def test_a_failed_read_leaves_the_table_as_it_was(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _load(tmp_path)
    monkeypatch.setattr(livevars, "fetch_live_values", lambda _ip, _port: (8, "Unable to reach it.", None))

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Get From Phone"))
        await user.should_see("Reads the current value")
        _press(user, _only(user, "Get Values"))
        await asyncio.sleep(0.5)
        assert all(not row["phone"] for row in _table(user).rows)
        assert _built["manager"].live is None


@pytest.mark.asyncio
async def test_pushing_sends_the_value_typed_for_the_chosen_variable_and_shows_what_the_phone_now_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _load(tmp_path)
    sent: list[tuple[str, str, str, str]] = []

    def set_global(ip: str, port: str, name: str, value: str) -> tuple[int, str]:
        sent.append((ip, port, name, value))
        return 0, f"{name} is now set."

    monkeypatch.setattr(livevars, "set_global", set_global)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Mode"))
        _press(user, _only(user, "Send To Phone"))
        await user.should_see("Send To Phone: %Mode")
        (box,) = [e for e in user.find(kind=ui.textarea).elements if e.label == "Value"]
        box.value = "dawn"
        _press(user, _only(user, "Send Value"))
        await _until(lambda: sent)
        await _until(lambda: "dawn" in next(r for r in _table(user).rows if r["name"] == "%Mode")["phone"])

    assert sent == [("192.168.0.210", "1821", "%Mode", "dawn")]
    assert _held("%Mode") == "night", "pushing changes the phone and not the file"


@pytest.mark.asyncio
async def test_a_push_the_phone_refused_shows_nothing_as_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _load(tmp_path)
    monkeypatch.setattr(livevars, "set_global", lambda *_args: (8, "refused"))

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.choose(next(row for row in manager.rows if row.name == "%Mode"))
        _press(user, _only(user, "Send To Phone"))
        await user.should_see("Send To Phone: %Mode")
        _press(user, _only(user, "Send Value"))
        await asyncio.sleep(0.5)
        assert manager.live is None


@pytest.mark.asyncio
async def test_saving_asks_the_window_to_save(tmp_path: Path) -> None:
    _load(tmp_path)
    _built["saved"] = 0

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Save To Current File"))
        await _until(lambda: _built["saved"] == 1)


@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_window() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}, "all_projects": {}, "all_profiles": {}, "all_scenes": {}}
    built: dict[str, Any] = {}

    def page() -> None:
        built["dialog"] = guiwins_varman.build_variable_manager(
            cast("Any", types.SimpleNamespace(state=PrimeItems)),
            cast("Any", lambda _target: lambda: None),
            cast("Any", lambda: None),
            PrimeItems,
        )

    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
    finally:
        if core.app.is_started:
            await core.app.stop()

    assert built["dialog"] is None


# ##################################################################################
# Several at once
# ##################################################################################
def _tick(manager: Any, *names: str) -> None:
    """Tick these rows in the table the way a click would: by reporting what is selected now."""
    picked = [row for row in manager.table.rows if row["name"] in names]
    manager.chose(types.SimpleNamespace(selection=picked))


@pytest.mark.asyncio
async def test_with_several_ticked_only_delete_can_be_pressed(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        _tick(manager, "%Spare", "%Flag")
        state = {name: button.enabled for name, button in manager.buttons.items()}
        heading = manager.uses_heading.text

    assert state == {"rename": False, "change": False, "push": False, "delete": True, "unpush": True}
    assert heading == "2 global variables"


@pytest.mark.asyncio
async def test_ticking_one_enables_all_four_and_none_disables_them(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        _tick(manager, "%Spare")
        one = [button.enabled for button in manager.buttons.values()]
        _tick(manager)
        none = [button.enabled for button in manager.buttons.values()]

    assert one == [True] * 5
    assert none == [False] * 5


@pytest.mark.asyncio
async def test_several_are_deleted_through_one_preview_and_one_undo(tmp_path: Path) -> None:
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        _tick(manager, "%Spare", "%Flag", "%Json")
        _press(user, _only(user, "Delete"))
        await user.should_see("Delete 3 global variables")
        _press(user, _only(user, "Preview"))
        await user.should_see("ready to apply")
        assert [_held(n) for n in ("%Spare", "%Flag", "%Json")] == ["x", "true", '{"a": 1}'], (
            "a preview changes nothing"
        )
        _press(user, _newest(user, "Delete"))
        await _until(lambda: _held("%Spare") is None)
        assert _held("%Flag") is None
        assert _held("%Json") is None
        await _until(lambda: not {"%Spare", "%Flag", "%Json"} & {r["name"] for r in _table(user).rows})
        names = {r["name"] for r in _table(user).rows}

    assert "%Mode" in names
    assert manager.picked == [], "what was ticked is gone, so nothing stays ticked"


@pytest.mark.asyncio
async def test_a_filter_then_select_all_shown_deletes_exactly_those(tmp_path: Path) -> None:
    """The use this is for: show the unused ones, tick them all, delete them."""
    _load(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.limit_to(mapvars.UNUSED)
        shown = [row["name"] for row in _table(user).rows]
        _tick(manager, *shown)
        assert len(manager.picked) == len(shown)
        _press(user, _only(user, "Delete"))
        await user.should_see(f"Delete {len(shown)} global variables")
        _press(user, _only(user, "Preview"))
        await user.should_see("ready to apply")
        _press(user, _newest(user, "Delete"))
        await _until(lambda: all(_held(name) is None for name in shown))

    assert _held("%Mode") == "night"


@pytest.mark.asyncio
async def test_ticked_variables_are_removed_from_the_phone_and_shown_as_gone_from_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _load(tmp_path)
    sent: list[str] = []

    def delete_global(_ip: str, _port: str, name: str) -> tuple[int, str]:
        sent.append(name)
        return 0, f"{name} is no longer there."

    monkeypatch.setattr(livevars, "delete_global", delete_global)

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.live = livevars.LiveValues("x:1", {"%Mode": "evening", "%Count": "12", "%Spare": "x"})
        manager.refresh()
        _tick(manager, "%Mode", "%Count")
        _press(user, _only(user, "Delete On Phone"))
        await user.should_see("Delete On Phone: 2 global variables")
        _press(user, _newest(user, "Delete On Phone"))
        await _until(lambda: sorted(sent) == ["%Count", "%Mode"])
        await _until(lambda: "%Mode" not in manager.live.values)
        by_name = {row["name"]: row for row in _table(user).rows}

    assert by_name["%Mode"]["phone"] == "not found on the phone"
    assert by_name["%Count"]["phone"] == "not found on the phone"
    assert "x" in by_name["%Spare"]["phone"], "what was not ticked is untouched"
    assert _held("%Mode") == "night", "removing it from the phone does not touch the file"


@pytest.mark.asyncio
async def test_a_variable_the_phone_would_not_remove_stays_shown_as_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _load(tmp_path)
    monkeypatch.setattr(livevars, "delete_global", lambda *_args: (8, "still holds it"))

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        manager.live = livevars.LiveValues("x:1", {"%Mode": "evening"})
        manager.refresh()
        _tick(manager, "%Mode")
        _press(user, _only(user, "Delete On Phone"))
        await user.should_see("Delete On Phone: %Mode")
        _press(user, _newest(user, "Delete On Phone"))
        await asyncio.sleep(0.5)

    assert manager.live.values == {"%Mode": "evening"}


@pytest.mark.asyncio
async def test_nothing_is_sent_to_the_phone_until_the_dialogs_button_is_pressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _load(tmp_path)
    sent: list[str] = []
    monkeypatch.setattr(livevars, "delete_global", lambda _ip, _port, name: (sent.append(name) or 0, ""))

    async with _open() as user:
        await user.should_see("Variable Manager")
        manager = _built["manager"]
        _tick(manager, "%Mode")
        _press(user, _only(user, "Delete On Phone"))
        await user.should_see("Delete On Phone: %Mode")
        await asyncio.sleep(0.3)

    assert sent == []


# ##################################################################################
# Fix Scope
# ##################################################################################
def _scope_page(tmp_path: Path) -> None:
    from tests.test_scopecheck import _XML as scope_xml

    _load_local(tmp_path, scope_xml)


def _fixer_rows(user: User) -> list[dict[str, Any]]:
    """The rows of the Fix Scope window's table: the newest table on the page."""
    tables = user.find(kind=ui.table).elements
    return max(tables, key=lambda table: table.id).rows


@pytest.mark.asyncio
async def test_fix_scope_lists_what_breaks_the_case_rule(tmp_path: Path) -> None:
    _scope_page(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Fix Scope"))
        await user.should_see("Tasker decides whether a variable is local or global")
        rows = _fixer_rows(user)
        summary = next(text for text in _labels(user) if "same letters as a global" in text.lower() and "," in text)

    assert {row["name"] for row in rows} >= {"%counter", "%mode", "%shared"}
    assert {row["suggestion"] for row in rows if row["name"] == "%mode"} == {"%Mode"}
    assert "in the variables tab, no capital" in summary.lower()


@pytest.mark.asyncio
async def test_choosing_a_finding_says_why_and_enables_the_buttons(tmp_path: Path) -> None:
    _scope_page(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Fix Scope"))
        await user.should_see("Tasker decides whether a variable is local or global")
        fixer = _fixer_of(user)
        before = (fixer.fix_button.enabled, fixer.show_button.enabled)
        fixer.choose(next(i for i in fixer.issues if i.kind == "SCOPE-DECLARED-LOWERCASE"))
        after = (fixer.fix_button.enabled, fixer.show_button.enabled)
        detail = fixer.detail.text

    assert before == (False, False)
    assert after == (True, True)
    assert "Variables tab" in detail


def _fixer_of(user: User) -> Any:
    """The ScopeFixer behind the open window: it is what the Manager's Fix Scope button made."""
    manager = _built["manager"]
    return manager.fixer


@pytest.mark.asyncio
async def test_a_finding_is_fixed_through_a_preview_and_the_lists_follow(tmp_path: Path) -> None:
    _scope_page(tmp_path)

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Fix Scope"))
        await user.should_see("Tasker decides whether a variable is local or global")
        fixer = _fixer_of(user)
        fixer.choose(next(i for i in fixer.issues if i.kind == "SCOPE-DECLARED-LOWERCASE"))
        _press(user, _only(user, "Fix..."))
        await user.should_see("Rename %mode")
        _press(user, _only(user, "Preview"))
        await user.should_see("ready to apply")
        assert _held("%mode") == "day", "a preview changes nothing"
        _press(user, _newest(user, "Fix"))
        await _until(lambda: _held("%Mode") == "day")
        await _until(lambda: "%mode" not in {row["name"] for row in fixer.shown_rows})
        names = {row.name for row in _built["manager"].rows}

    assert "%Mode" in names, "the Variable Manager behind it follows"
    assert _held("%mode") is None


@pytest.mark.asyncio
async def test_a_finding_with_no_suggestion_cannot_be_applied_until_a_name_is_given(tmp_path: Path) -> None:
    xml = (
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        '<Variable sr="vars0"><n>%MyVar</n><v>1</v></Variable><Variable sr="vars1"><n>%Myvar</n><v>2</v></Variable>'
        '<Task sr="task1" ve="2"><id>1</id><nme>Slip</nme>'
        '<Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">%myvar</Str>'
        '<Int sr="arg1" val="0"/><Int sr="arg2" val="0"/></Action></Task></TaskerData>'
    )
    _load_local(tmp_path, xml)

    async with _open() as user:
        await user.should_see("Variable Manager")
        _press(user, _only(user, "Fix Scope"))
        await user.should_see("Tasker decides whether a variable is local or global")
        fixer = _fixer_of(user)
        fixer.choose(fixer.issues[0])
        _press(user, _only(user, "Fix..."))
        await user.should_see("Make global %myvar")
        _press(user, _only(user, "Preview"))
        await user.should_see("cannot be done")
        assert not [button for button in _buttons(user, "Fix") if button.enabled]
