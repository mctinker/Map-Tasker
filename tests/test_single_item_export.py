"""'Get Local XML File' single-object export selection unit tests.

Tasker exports one Project/Profile/Task/Scene as "<name>.prj|prf|tsk|scn.xml", and such
a file has exactly one thing in it worth looking at.  guiutils.single_item_export_selection
is what turns that into the 'Specific Name' selection the user would otherwise have to
make by hand out of a pulldown holding a single candidate.

The interesting cases are the ones where the file name and the XML disagree: the name a
selection is made with has to be the one inside the XML, since that is what the pulldowns
list and what every filter downstream matches on, and a file on disk can have been
renamed at any point since Tasker wrote it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from maptasker.src.guiutils import single_item_export_selection
from maptasker.src.primitem import PrimeItems, initial_tasker_root_elements
from maptasker.src.userintr import MapTaskerEventHandlers


@pytest.fixture(autouse=True)
def _loaded_export() -> None:
    """A loaded single-Project export, as taskerd would leave PrimeItems.

    Only the four name-keyed tables the function reads are filled in; the tests that
    care about the other item types overwrite them.
    """
    PrimeItems.tasker_root_elements = initial_tasker_root_elements()
    PrimeItems.tasker_root_elements["all_projects"] = {"Home Automation": {}}
    PrimeItems.tasker_root_elements["all_profiles_by_name"] = {"Sunset": {}, "Sunrise": {}}
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {"Lights On": {}, "Lights Off": {}}
    PrimeItems.tasker_root_elements["all_scenes"] = {"Dashboard": {}}


def test_project_export_selects_its_project() -> None:
    """The ordinary case: name in front of ".prj" is the Project's own name."""
    assert single_item_export_selection("/backups/Home Automation.prj.xml") == ("Project", "Home Automation")


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("Sunset.prf.xml", ("Profile", "Sunset")),
        ("Lights On.tsk.xml", ("Task", "Lights On")),
        ("Dashboard.scn.xml", ("Scene", "Dashboard")),
    ],
)
def test_each_export_type_selects_its_own_item(file_name: str, expected: tuple[str, str]) -> None:
    """Every tag picks out its own kind, not just Projects."""
    assert single_item_export_selection(f"/backups/{file_name}") == expected


def test_full_backup_selects_nothing() -> None:
    """An untagged backup holds everything, so it must leave the selection alone --
    this is the file the GUI is used with most of the time."""
    assert single_item_export_selection("/backups/backup.xml") == ("", "")


def test_renamed_export_still_selects_the_only_object_of_its_type() -> None:
    """The file was renamed after export, so its name matches nothing in the XML.  A
    .prj export holds one Project, and that one is still the answer."""
    assert single_item_export_selection("/backups/old copy of home.prj.xml") == ("Project", "Home Automation")


def test_renamed_export_gives_up_when_the_type_is_ambiguous() -> None:
    """Same renaming, but a .tsk export whose file has more than one Task in its tables
    -- nothing identifies which one, so make no selection rather than a wrong one."""
    assert single_item_export_selection("/backups/whatever.tsk.xml") == ("", "")


def test_name_match_beats_the_single_object_fallback() -> None:
    """With two Profiles present, the file name is what tells them apart."""
    assert single_item_export_selection("/backups/Sunrise.prf.xml") == ("Profile", "Sunrise")


def test_case_differences_in_the_file_name_are_tolerated() -> None:
    """macOS and Windows both hand back file names whose case need not match what
    Tasker wrote, and the tag itself may be upper case."""
    assert single_item_export_selection("/backups/SUNSET.PRF.XML") == ("Profile", "Sunset")


def test_tag_in_a_parent_directory_is_ignored() -> None:
    """Only the file's own name is read.  A directory called "prj exports" must not
    make every backup in it look like a Project export."""
    assert single_item_export_selection("/backups/prj exports/backup.xml") == ("", "")


def test_export_of_a_type_the_load_has_none_of_selects_nothing() -> None:
    """A .scn.xml whose Scenes never made it into the tables -- a failed or partial
    load -- must not select a Scene that isn't there."""
    PrimeItems.tasker_root_elements["all_scenes"] = {}
    assert single_item_export_selection("/backups/Dashboard.scn.xml") == ("", "")


@pytest.mark.parametrize("file_path", ["", None])
def test_no_file_selects_nothing(file_path: str | None) -> None:
    """Cancelled picker or an unset PrimeItems.file_to_get."""
    assert single_item_export_selection(file_path) == ("", "")


def test_an_open_file_object_is_read_the_same_as_a_path(tmp_path) -> None:  # noqa: ANN001
    """PrimeItems.file_to_get is a path string when getxml_event first assigns it and an
    open file object once the load has been through it, and the caller passes whichever
    it finds.  Reading str() of a file object instead of its .name would take the tag out
    of the repr's own text and select on a candidate name that is partly Python."""
    export = tmp_path / "Home Automation.prj.xml"
    export.write_text("<TaskerData/>", encoding="utf-8")
    with export.open(encoding="utf-8") as handle:
        assert single_item_export_selection(handle) == ("Project", "Home Automation")


# --- The handler side: what the three "a file was just loaded" paths actually call. ---


@pytest.fixture
def event_handler() -> MapTaskerEventHandlers:
    """A handler over a mock view, with process_single_name_event stubbed out.

    That method is the whole point of the call -- an automatic selection has to go
    through the same route a hand-made one does -- so what these tests check is that it
    is reached, with which arguments, and when it is left alone.
    """
    handler = MapTaskerEventHandlers(MagicMock())
    handler.process_single_name_event = MagicMock()
    return handler


def test_handler_selects_the_exported_object(event_handler: MapTaskerEventHandlers) -> None:
    """'Get Local XML File' and both Android fetch paths all end in this call."""
    event_handler.select_single_item_export("/backups/Home Automation.prj.xml")
    event_handler.process_single_name_event.assert_called_once_with("Project", "Home Automation")


def test_handler_reads_an_android_device_path(event_handler: MapTaskerEventHandlers) -> None:
    """The Android paths hand over the file's location on the device rather than a local
    path.  Only the file's own name is read, so the two are the same job."""
    event_handler.select_single_item_export("/storage/emulated/0/Tasker/configs/user/Sunset.prf.xml")
    event_handler.process_single_name_event.assert_called_once_with("Profile", "Sunset")


def test_handler_leaves_a_full_backup_alone(event_handler: MapTaskerEventHandlers) -> None:
    """The common case, and the one that must not change: a backup selects nothing, so
    the whole configuration is displayed."""
    event_handler.select_single_item_export("/storage/emulated/0/Tasker/configs/user/backup.xml")
    event_handler.process_single_name_event.assert_not_called()


class FakeSelect:
    """Stands in for a NiceGUI ui.select -- the value, the options and update() are all
    select_pulldown_option touches.  Modelled on test_maptasker_gui.py's own FakeSelect."""

    def __init__(self, options: list) -> None:
        self.value = "None"
        self.options = options
        self.updated = False

    def update(self) -> None:
        """Record the redraw the real widget needs to show a programmatic change."""
        self.updated = True


def _handler_with_pulldowns(project_options: list) -> tuple[MapTaskerEventHandlers, FakeSelect]:
    """A handler whose view carries a real-enough Project pulldown."""
    gui = MagicMock()
    gui.is_updating = False
    pulldown = FakeSelect(project_options)
    gui.specific_project_optionmenu = pulldown
    handler = MapTaskerEventHandlers(gui)
    handler.process_single_name_event = MagicMock()
    return handler, pulldown


def test_the_pulldown_itself_shows_the_selection() -> None:
    """The state being right is not enough: process_name_event leaves the selected
    item's own pulldown alone (reset_single_item_pulldowns' except_for), because a user
    picking from it has already set it.  Nothing picked here, so the Project would be
    selected everywhere while its pulldown still read "None"."""
    handler, pulldown = _handler_with_pulldowns(["None", "Project: Home Automation"])
    handler.select_single_item_export("/backups/Home Automation.prj.xml")
    assert pulldown.value == "Project: Home Automation"
    assert pulldown.updated


def test_the_pulldown_is_set_under_the_is_updating_guard() -> None:
    """Assigning .value fires the widget's on_change, which would re-enter
    process_name_event for the selection just made -- and the flag has to be put back
    afterwards, or every later pulldown event is swallowed."""
    handler, pulldown = _handler_with_pulldowns(["None", "Project: Home Automation"])
    seen = []
    original = FakeSelect.update

    def record_flag(self) -> None:  # noqa: ANN001
        seen.append(handler.gui.is_updating)
        original(self)

    FakeSelect.update = record_flag
    try:
        handler.select_single_item_export("/backups/Home Automation.prj.xml")
    finally:
        FakeSelect.update = original

    assert seen == [True]
    assert handler.gui.is_updating is False


def test_a_full_backup_leaves_the_pulldown_alone() -> None:
    """Nothing selected means nothing touched -- the pulldown stays on "None"."""
    handler, pulldown = _handler_with_pulldowns(["None", "Project: Home Automation"])
    handler.select_single_item_export("/backups/backup.xml")
    assert pulldown.value == "None"
    assert not pulldown.updated
