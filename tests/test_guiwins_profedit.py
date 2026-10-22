"""The Edit Profile and Add Profile dialogs (guiwins_profedit): what they draw, and what a press does.

The model underneath -- what an edit writes, what it refuses -- is test_profedit's.  These build the
real dialogs on a page of NiceGUI's in-process user simulation, over the same fixture Profiles, and
press what a user would press.  The window they belong to is replaced by a recorder, so what is
asserted is the dialog's half of the bargain: that each condition type gets the fields its XML calls
for, that a button reports the right event with the right Profile and arguments, and that the two
sections which redraw themselves (the Entry/Exit Tasks and the conditions) redraw from the Profile
as it now stands without losing what was typed into them.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import profedit
from maptasker.src.gui import guiwins_profedit
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_mapswap import _load
from tests.test_profedit import _XML

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from nicegui.testing.user import User

_built: dict = {}


class _Recorder:
    """Stands in for the window's event handlers: every attribute is a function that records its call.

    A handler group (editors, android ...) is this same recorder, so the call is recorded by its name alone."""

    _GROUPS = frozenset({"ai", "android", "carry", "editors", "loading", "prebuild", "reports", "settings"})

    def __init__(self, calls: list[tuple]) -> None:
        self._calls = calls

    def __getattr__(self, name: str) -> Any:
        if name in self._GROUPS:
            return self

        def record(*args: object) -> None:
            self._calls.append((name, *args))

        return record


@pytest.fixture(autouse=True)
def _configuration() -> AsyncIterator[None]:
    """The fixture backup loaded, and a fresh record of what the dialog reported."""
    _load(_XML)
    _built.clear()
    _built.update(calls=[], dialog=None, edited=None, field_refs={})
    yield


def _gui() -> SimpleNamespace:
    """The window as far as these dialogs use it: the run's state and the event handlers."""
    return SimpleNamespace(state=PrimeItems, event_handlers=_Recorder(_built["calls"]))


def _edit_page() -> None:
    edited = profedit.load_profile_for_edit(_built["profile"], state=PrimeItems)
    _built["edited"] = edited
    guiwins_profedit.build_edit_profile_dialog(_gui(), edited)


def _add_page() -> None:
    created = profedit.create_new_profile("", state=PrimeItems)
    _built["edited"] = created
    guiwins_profedit.build_add_profile_dialog(_gui(), created, _built.get("project", ""))


@contextlib.asynccontextmanager
async def _open(page: Callable[[], None], profile: str = "", project: str = "") -> AsyncIterator[User]:
    _built.update(profile=profile, project=project)
    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _buttons(user: User) -> dict[str, ui.button]:
    return {element.text: element for element in user.find(kind=ui.button).elements}


def _all(user: User, label: str) -> list[ui.button]:
    """Every button with this label, in the order they were drawn (a set of elements has no order)."""
    return sorted((e for e in user.find(kind=ui.button).elements if e.text == label), key=lambda e: e.id)


def _click(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _press(user: User, label: str) -> None:
    _click(user, _buttons(user)[label])


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


def _calls(name: str) -> list[tuple]:
    return [call for call in _built["calls"] if call[0] == name]


def _pickers(user: User) -> list[ui.select]:
    """The Entry and Exit Task pickers, in that order."""
    found = (e for e in user.find(kind=ui.select).elements if e.props.get("label") == "Choose a Task")
    return sorted(found, key=lambda e: e.id)


def _select(user: User, label: str) -> ui.select:
    """The select with this label, shown or not -- user.find only sees what is on screen."""
    (found,) = (e for e in user.client.elements.values() if isinstance(e, ui.select) and e.props.get("label") == label)
    return found


def _inputs(user: User) -> dict[str, ui.input]:
    return {element.props.get("label"): element for element in user.find(kind=ui.input).elements}


# ##################################################################################
# The chrome: Edit and Add
# ##################################################################################
@pytest.mark.asyncio
async def test_edit_is_titled_with_the_profile_and_its_name_is_read_only() -> None:
    async with _open(_edit_page, "Morning") as user:
        assert "Edit Profile: Morning" in _labels(user)
        name = _inputs(user)["Profile Name"]
        assert name.value == "Morning"
        assert "readonly" in name.props
        assert _inputs(user)["Save as"].value == profedit.default_save_path("Morning", PrimeItems)


@pytest.mark.asyncio
async def test_each_edit_button_reports_its_event_with_this_profile() -> None:
    async with _open(_edit_page, "Morning") as user:
        edited = _built["edited"]
        for label, event in (
            ("Delete Profile", "delete_profile_event"),
            ("Rename", "rename_profile_event"),
            ("Ok", "keep_edited_profile_event"),
            ("Save To Current File", "save_edited_profile_to_current_file_event"),
            ("Save To Android", "open_save_profile_to_android_dialog_event"),
            ("Export Profile", "save_edited_profile_event"),
        ):
            _built["calls"].clear()
            _press(user, label)
            ((_name, profile, *_rest),) = _calls(event)
            assert profile is edited, label


@pytest.mark.asyncio
async def test_cancel_closes_the_edit_dialog_without_reporting_anything() -> None:
    async with _open(_edit_page, "Morning") as user:
        dialog = next(iter(user.find(kind=ui.card).elements)).parent_slot.parent
        dialog.open()
        _press(user, "Cancel")
        assert dialog.value is False
        assert _built["calls"] == []


@pytest.mark.asyncio
async def test_add_starts_with_an_empty_name_and_says_which_project_it_adds_to() -> None:
    async with _open(_add_page, project="Home") as user:
        assert "Add Profile" in _labels(user)
        assert "Adding to Project: Home" in _labels(user)
        assert _inputs(user)["Profile Name"].value == ""


@pytest.mark.asyncio
async def test_add_without_a_project_does_not_name_one() -> None:
    async with _open(_add_page) as user:
        assert not [text for text in _labels(user) if text.startswith("Adding to Project")]


@pytest.mark.asyncio
async def test_typing_a_name_in_add_follows_through_to_the_save_path() -> None:
    async with _open(_add_page) as user:
        fields = _inputs(user)
        fields["Profile Name"].value = "Evening"
        assert fields["Save as"].value == profedit.default_save_path("Evening", PrimeItems)


@pytest.mark.asyncio
async def test_a_save_path_the_user_changed_is_not_overwritten_by_the_name() -> None:
    async with _open(_add_page) as user:
        fields = _inputs(user)
        fields["Save as"].value = "/somewhere/mine.prf.xml"
        fields["Profile Name"].value = "Evening"
        assert fields["Save as"].value == "/somewhere/mine.prf.xml"


@pytest.mark.asyncio
async def test_each_add_button_reports_its_event_with_the_new_profile() -> None:
    async with _open(_add_page, project="Home") as user:
        created = _built["edited"]
        for label, event in (
            ("Ok", "keep_new_profile_event"),
            ("Save To Current File", "save_new_profile_to_current_file_event"),
            ("Save To Android", "open_save_profile_to_android_dialog_event"),
        ):
            _built["calls"].clear()
            _press(user, label)
            ((_name, profile, *_rest),) = _calls(event)
            assert profile is created, label


# ##################################################################################
# Entry/Exit Tasks
# ##################################################################################
@pytest.mark.asyncio
async def test_linked_tasks_are_shown_by_name_with_an_unlink_button_for_each() -> None:
    async with _open(_edit_page, "Morning") as user:
        labels = _labels(user)
        assert {"Entry Task:", "Exit Task:", "Entry", "Exit"} <= set(labels)
        assert len(_all(user, "Unlink")) == 2


@pytest.mark.asyncio
async def test_a_profile_with_no_tasks_offers_a_picker_per_task_and_none_to_unlink() -> None:
    async with _open(_edit_page, "Triggers") as user:
        assert "Unlink" not in _buttons(user)
        pickers = _pickers(user)
        assert len(pickers) == 2
        assert sorted(pickers[0].options) == ["Entry", "Exit", "Other"]


@pytest.mark.asyncio
async def test_link_reports_the_picked_task_and_unlink_reports_the_link_type() -> None:
    async with _open(_edit_page, "Triggers") as user:
        _pickers(user)[0].value = "Other"
        _click(user, _all(user, "Link")[0])
        ((_name, profile, link_type, task_name),) = _calls("link_task_to_profile_event")
        assert (profile, link_type, task_name) == (_built["edited"], "Entry", "Other")

    async with _open(_edit_page, "Morning") as user:
        _click(user, _all(user, "Unlink")[0])
        assert _calls("unlink_task_from_profile_event")[0][2] == "Entry"


@pytest.mark.asyncio
async def test_add_task_beside_a_picker_asks_for_a_new_task_to_link_as_that_type() -> None:
    async with _open(_edit_page, "Triggers") as user:
        _click(user, _all(user, "Add Task")[1])
        ((_name, profile, link_type, redraw),) = _calls("open_add_task_for_profile_link_event")
        assert (profile, link_type) == (_built["edited"], "Exit")
        assert callable(redraw)


# ##################################################################################
# Conditions
# ##################################################################################
@pytest.mark.asyncio
async def test_a_profile_without_conditions_says_so() -> None:
    async with _open(_add_page) as user:
        assert "No conditions on this Profile." in _labels(user)


@pytest.fixture
def field_refs(monkeypatch: pytest.MonkeyPatch) -> dict:
    """The dict of widgets the dialog under test registers its fields in, which it keeps to itself."""
    seen: dict = {}
    original = guiwins_profedit._ProfileEditorBody.__init__

    def spy(self: object, gui: object, edited_profile: object, refs: dict, parent: object) -> None:
        seen.update(refs=refs)
        original(self, gui, edited_profile, refs, parent)

    monkeypatch.setattr(guiwins_profedit._ProfileEditorBody, "__init__", spy)
    return seen


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "indexes"),
    [("Morning", (0,)), ("Weekdays", (0,)), ("Apps", (0,)), ("Where", (0,)), ("Triggers", (0, 1))],
)
async def test_every_condition_type_draws_fields_registered_under_its_own_index(
    profile: str,
    indexes: tuple[int, ...],
    field_refs: dict,
) -> None:
    async with _open(_edit_page, profile):
        keys = [key for key in field_refs["refs"] if key.startswith("cond")]
        for index in indexes:
            assert any(key.startswith(f"cond{index}_") for key in keys), (profile, index)


@pytest.mark.asyncio
async def test_the_weekday_buttons_tick_all_none_or_the_odd_days(field_refs: dict) -> None:
    async with _open(_edit_page, "Weekdays") as user:
        days = [field_refs["refs"][profedit.condition_field_key(0, f"wday{n}")] for n in range(1, 8)]
        assert [box.value for box in days] == [False, True, True, False, False, False, False]

        _click(user, _all(user, "All")[0])
        assert all(box.value for box in days)
        _click(user, _all(user, "None")[0])
        assert not any(box.value for box in days)
        _click(user, _all(user, "Odd")[0])
        assert [box.value for box in days] == [True, False, True, False, True, False, True]


@pytest.mark.asyncio
async def test_add_condition_reports_the_type_picked() -> None:
    async with _open(_edit_page, "Weekdays") as user:
        _select(user, "Condition Type").value = "Time"
        _click(user, _all(user, "Add Condition")[0])
        ((_name, profile, cond_type),) = _calls("add_condition_to_profile_event")
        assert (profile, cond_type) == (_built["edited"], "Time")


@pytest.mark.asyncio
async def test_add_condition_for_an_event_or_state_reports_the_code_picked() -> None:
    async with _open(_edit_page, "Weekdays") as user:
        by_label = {name: _select(user, name) for name in ("Condition Type", "Event Type", "State Type")}
        event_key = next(iter(by_label["Event Type"].options))
        state_key = next(iter(by_label["State Type"].options))

        by_label["Condition Type"].value = "Event"
        by_label["Event Type"].value = event_key
        _click(user, _all(user, "Add Condition")[0])
        assert _calls("add_event_condition_to_profile_event")[0][2] == event_key

        # Adding redraws the whole section, so the pickers above are gone: ask for the new ones.
        _select(user, "Condition Type").value = "State"
        _select(user, "State Type").value = state_key
        _click(user, _all(user, "Add Condition")[0])
        assert _calls("add_state_condition_to_profile_event")[0][2] == state_key


@pytest.mark.asyncio
async def test_the_code_pickers_only_show_for_their_own_condition_type() -> None:
    async with _open(_edit_page, "Weekdays") as user:
        by_label = {name: _select(user, name) for name in ("Condition Type", "Event Type", "State Type")}
        assert not by_label["Event Type"].visible
        assert not by_label["State Type"].visible
        by_label["Condition Type"].value = "Event"
        assert by_label["Event Type"].visible
        assert not by_label["State Type"].visible
        by_label["Condition Type"].value = "State"
        assert by_label["State Type"].visible
        assert not by_label["Event Type"].visible


@pytest.mark.asyncio
async def test_a_code_that_cannot_be_built_from_scratch_is_labelled_and_greyed_out() -> None:
    unsupported = [row for row in profedit.list_addable_states(state=PrimeItems) if not row["addable"]]
    if not unsupported:
        pytest.skip("every State code in the tables is addable")
    async with _open(_edit_page, "Weekdays") as user:
        picker = _select(user, "State Type")
        assert picker.options[unsupported[0]["condition_key"]].endswith("(Not Supported)")


@pytest.mark.asyncio
async def test_delete_condition_reports_its_index_for_each_condition() -> None:
    async with _open(_edit_page, "Triggers") as user:
        deletes = _all(user, "Delete Condition")
        assert len(deletes) == 3
        _click(user, deletes[1])
        ((_name, profile, index),) = _calls("remove_condition_from_profile_event")
        assert (profile, index) == (_built["edited"], 1)


# ##################################################################################
# Save To Android, and Delete
# ##################################################################################
def _android_page() -> None:
    gui = _gui()
    guiwins_profedit.build_save_profile_to_android_dialog(
        gui,
        profedit.load_profile_for_edit("Morning", state=PrimeItems),
        {"name": SimpleNamespace(value="Morning")},
        SimpleNamespace(),
    )


def _delete_page() -> None:
    edited = profedit.load_profile_for_edit("Morning", state=PrimeItems)
    _built["edited"] = edited
    guiwins_profedit.build_delete_profile_dialog(_gui(), edited, SimpleNamespace(name="parent"))


@pytest.mark.asyncio
async def test_the_android_panel_offers_the_device_fields_and_both_ways_to_send() -> None:
    async with _open(_android_page) as user:
        assert "Save Profile To Android Device" in _labels(user)
        assert {"Android IP Address", "Port"} <= set(_inputs(user))
        assert {"Cancel", "Save As File", "Import Into Tasker"} <= set(_buttons(user))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "event"),
    [("Save As File", "save_profile_to_android_event"), ("Import Into Tasker", "import_profile_into_tasker_event")],
)
async def test_each_android_button_reports_the_profile_and_both_sets_of_fields(label: str, event: str) -> None:
    async with _open(_android_page) as user:
        _press(user, label)
        ((_name, profile, name_fields, device_fields, _android, _parent),) = _calls(event)
        assert profile.profile_element.findtext("nme") == "Morning"
        assert name_fields["name"].value == "Morning"
        assert {"ip_address", "ip_port"} <= set(device_fields)


@pytest.mark.asyncio
async def test_delete_confirms_by_name_and_reports_the_name_with_both_dialogs() -> None:
    async with _open(_delete_page) as user:
        assert "Delete Profile 'Morning'" in _labels(user)
        _press(user, "Delete Profile")
        ((_name, profile_name, _confirm, parent),) = _calls("confirm_delete_profile_event")
        assert profile_name == "Morning"
        assert parent.name == "parent"


@pytest.mark.asyncio
async def test_cancel_in_the_delete_dialog_deletes_nothing() -> None:
    async with _open(_delete_page) as user:
        _press(user, "Cancel")
        assert _calls("confirm_delete_profile_event") == []
