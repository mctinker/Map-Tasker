"""The window helpers that face the device and the loaded backup: the reachability check, the panel's widgets, the list of a Project's contents."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiutils
from nicegui import run

from tests.faketasker import FakeTasker
from tests.test_fuzz_backup import _SYNTHETIC
from tests.test_fuzz_roundtrip import a_loaded_backup

if TYPE_CHECKING:
    from collections.abc import Iterator

    from maptasker.src.gui.userintr import MyGui


@pytest.fixture
def phone() -> Iterator[FakeTasker]:
    fake = FakeTasker().up()
    yield fake
    fake.down()


def _gui(window: SimpleNamespace) -> MyGui:
    return cast("MyGui", window)


@pytest.fixture
def window(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """A window that records what it shows, notifications that are only recorded, and run.io_bound called straight."""
    said: list[tuple[str, str]] = []
    notes: list[tuple[str, str]] = []

    async def io_bound(function: Any, *args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs)

    monkeypatch.setattr(run, "io_bound", io_bound)
    monkeypatch.setattr(
        guiutils.ui, "notify", lambda message, **options: notes.append((message, options.get("type", "")))
    )
    return SimpleNamespace(
        display_message_box=lambda message, colour: said.append((message, colour)), said=said, notes=notes
    )


# ##################################################################################
# Is the phone there?
# ##################################################################################
@pytest.mark.asyncio
async def test_a_phone_that_answers_is_reachable_whether_or_not_it_has_the_folder(
    phone: FakeTasker, window: SimpleNamespace
) -> None:
    """Either a 200 or a 404 says the server is there; the probe asks for /Tasker, which the fake does not hold."""
    assert await guiutils.ping_android_device(_gui(window), phone.address, phone.port) is True

    assert window.said == []
    assert phone.seen("GET", "/file/Tasker")
    assert "Connecting to Android device" in window.notes[0][0]


@pytest.mark.asyncio
async def test_a_phone_that_is_not_there_is_called_unreachable_in_red(
    phone: FakeTasker, window: SimpleNamespace
) -> None:
    port = phone.port
    phone.down()

    assert await guiutils.ping_android_device(_gui(window), phone.address, port) is False

    [(message, colour)] = window.said
    assert colour == "Red"
    assert f"{phone.address}:{port}" in message
    assert "unreachable" in message


@pytest.mark.asyncio
async def test_a_probe_cancelled_by_the_page_going_away_says_nothing(
    window: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def cancelled(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(run, "io_bound", cancelled)

    assert await guiutils.ping_android_device(_gui(window), "127.0.0.1", "1") is False
    assert window.said == []


@pytest.mark.asyncio
async def test_a_probe_that_breaks_is_reported_rather_than_raised(
    window: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_a: Any, **_k: Any) -> None:
        msg = "the thread pool is gone"
        raise RuntimeError(msg)

    monkeypatch.setattr(run, "io_bound", broken)

    assert await guiutils.ping_android_device(_gui(window), "127.0.0.1", "1") is False
    assert window.said == [("Ping execution failure: the thread pool is gone", "Red")]


# ##################################################################################
# The Get XML panel's widgets
# ##################################################################################
class _Widget:
    def __init__(self, fail: bool = False) -> None:
        self.deleted = False
        self.fail = fail

    def delete(self) -> None:
        if self.fail:
            msg = "already gone"
            raise RuntimeError(msg)
        self.deleted = True


def test_clearing_the_panel_deletes_each_widget_and_forgets_it() -> None:
    gui = SimpleNamespace(ip_entry=_Widget(), port_entry=_Widget(), filelist_option=_Widget(), first_time=True)
    ip = gui.ip_entry

    guiutils.clear_android_buttons(gui)  # type: ignore[arg-type]

    assert ip.deleted
    assert gui.ip_entry is None and gui.port_entry is None and gui.filelist_option is None


def test_a_widget_that_cannot_be_deleted_does_not_stop_the_others() -> None:
    other = _Widget()
    gui = SimpleNamespace(ip_entry=_Widget(fail=True), port_entry=other, first_time=True)

    guiutils.clear_android_buttons(gui)  # type: ignore[arg-type]

    assert other.deleted


def test_once_the_first_run_is_over_the_upgrade_button_is_cleared_too() -> None:
    upgrade = _Widget()
    gui = SimpleNamespace(upgrade_button=upgrade, first_time=False)

    guiutils.clear_android_buttons(gui)  # type: ignore[arg-type]

    assert upgrade.deleted and gui.upgrade_button is None


# ##################################################################################
# Reading the backup into the window
# ##################################################################################
def test_a_backup_that_cannot_be_read_is_a_return_code_not_an_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_first_time: bool, state: Any) -> None:
        msg = "not a backup"
        raise MapTaskerError(msg, 3)

    monkeypatch.setattr(guiutils, "get_data_and_output_intro", refuse)
    monkeypatch.setattr(guiutils, "record_error", lambda error, state: error.exit_code)
    state = SimpleNamespace(
        program_arguments=SimpleNamespace(debug=False, gui=False), colors_to_use=None, output_lines=None
    )
    monkeypatch.setattr(guiutils, "LineOut", lambda state: "lines")

    assert guiutils.get_xml(True, "dark", state) == 3  # type: ignore[arg-type]
    assert state.program_arguments.debug is True and state.program_arguments.gui is True


def test_a_backup_that_reads_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guiutils, "get_data_and_output_intro", lambda first_time, state: None)
    monkeypatch.setattr(guiutils, "LineOut", lambda state: "lines")
    state = SimpleNamespace(
        program_arguments=SimpleNamespace(debug=True, gui=False), colors_to_use=None, output_lines=None
    )

    assert guiutils.get_xml(False, "light", state) == 0  # type: ignore[arg-type]
    assert state.program_arguments.debug is True, "a run already in debug stays in it"
    assert state.output_lines == "lines"


# ##################################################################################
# The current file's label
# ##################################################################################
def _label_window(**attributes: Any) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(), **attributes)


@pytest.fixture
def menus(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    refreshed: list[dict] = []
    monkeypatch.setattr(guiutils, "update_tasker_object_menus", lambda gui, **kw: refreshed.append(kw))
    return refreshed


def test_the_label_already_in_the_toolbar_is_given_the_files_name(menus: list) -> None:
    label = SimpleNamespace(text="")
    gui = _label_window(current_file=label)

    guiutils.display_current_file(gui, "/home/me/MapTasker/backup.xml")  # type: ignore[arg-type]

    assert label.text == "Current File: backup.xml"
    assert gui.current_file_label is label
    assert menus == [{"get_data": False, "reset_single_names": False}]


def test_no_file_is_said_in_words(menus: list) -> None:
    label = SimpleNamespace(text="")

    guiutils.display_current_file(_label_window(current_file_label=label), "")  # type: ignore[arg-type]

    assert label.text == "No file loaded"


def test_with_no_label_yet_one_is_made_in_the_toolbar(monkeypatch: pytest.MonkeyPatch, menus: list) -> None:
    class Toolbar:
        entered = 0

        def __enter__(self) -> None:
            Toolbar.entered += 1

        def __exit__(self, *_: object) -> None:
            return None

    made: list[str] = []
    monkeypatch.setattr(
        guiutils.ui,
        "label",
        lambda text: made.append(text) or SimpleNamespace(classes=lambda *_a, **_k: f"label:{text}"),
    )
    gui = _label_window(gui_view_toolbar=Toolbar())

    guiutils.display_current_file(gui, "backup.xml")  # type: ignore[arg-type]

    assert made == ["Current File: backup.xml"] and Toolbar.entered == 1
    assert gui.current_file == "label:Current File: backup.xml"


def test_before_the_screen_exists_a_label_is_made_anyway(monkeypatch: pytest.MonkeyPatch, menus: list) -> None:
    monkeypatch.setattr(guiutils.ui, "label", lambda text: SimpleNamespace(classes=lambda *_a, **_k: f"loose:{text}"))
    gui = _label_window()

    guiutils.display_current_file(gui, "backup.xml")  # type: ignore[arg-type]

    assert gui.current_file == "loose:Current File: backup.xml"


# ##################################################################################
# What a Project holds
# ##################################################################################
def test_a_projects_profiles_list_their_tasks_and_the_tasks_in_no_profile_follow() -> None:
    with a_loaded_backup(_SYNTHETIC) as path:
        assert path
        tables = PrimeItems.tasker_root_elements

        rows = guiutils.build_profiles(tables, list(tables["all_profiles"]), "Reminders", state=PrimeItems)

    assert [row["name"] for row in rows] == ["Profile: Morning Reminder", "No Profile"]
    assert rows[0]["children"][0].startswith("Task: Remind Me"), "the Profile's Entry Task"
    assert rows[1]["children"] == ["Remind Me", "Open Reminder List", "Show Chosen Tab"], "the Tasks in no Profile"
