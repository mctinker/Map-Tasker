"""Get XML from Android Device, driven the way a user drives it, against a phone that answers (tests/faketasker.py).

The panel is built on a real NiceGUI page and its buttons are pressed.  What is faked is only the window around it
(the message line, the pulldowns' refresh) and the phone, which is a real server: the address typed into the field is
the one the requests go to, the files listed are the ones the helper Task wrote, and the backup that arrives is the
file the loader then reads.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from maptasker.src.core import maputil2
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.device import devicefiles, devicetask
from maptasker.src.gui import guiutils_android, userintr_android, userintr_loading
from nicegui import ui

from tests.doubles import required
from tests.faketasker import FakeTasker
from tests.nicegui_harness import click, found, open_page, settled

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

_BACKUP = (Path(__file__).parent / "data" / "synthetic_backup.xml").read_bytes()
_FILES = (
    "MAPTASKER-FILES 1\nFILES\n/storage/emulated/0/Tasker/backup.xml|~|/storage/emulated/0/Tasker/other.xml\n"
    "MAPTASKER-END\n"
)


class Window:
    """What the Android handlers need of the main window: a message line, the panel's slot, and the fields' names."""

    handlers: userintr_android.AndroidEventHandlers

    def __init__(self, handlers_hub: Any) -> None:
        self.state = PrimeItems
        self.messages: list[tuple[str, str]] = []
        self.menus_refreshed = 0
        self.android_file = ""
        self.android_ipaddr = ""
        self.android_port = ""
        self.list_files = False
        self.file = ""
        self.android_container: ui.element | None = None
        self.event_handlers = handlers_hub

    def display_message_box(self, message: str, colour: str) -> None:
        self.messages.append((message, colour))


@pytest.fixture
def phone(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeTasker]:
    monkeypatch.setattr(maputil2, "AUTH_KEY_RETRY_SECONDS", 0)
    monkeypatch.setattr(maputil2, "_UPLOAD_SETTLE_SECONDS", 0)
    monkeypatch.setattr(devicetask, "RESULT_POLL_SECONDS", 0)
    maputil2._auth_keys.clear()
    fake = FakeTasker().up()
    fake.files["/Tasker/backup.xml"] = _BACKUP
    fake.files["/Tasker/other.xml"] = _BACKUP
    yield fake
    fake.down()
    maputil2._auth_keys.clear()


@pytest.fixture
def window(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loaded: None) -> Window:
    """The window, in a working folder of its own (a fetched backup is written to the current directory)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        guiutils_android, "save_restore_args", lambda args, colors, to_save=False, **_kw: (args, colors)
    )
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    PrimeItems.slash = "/"
    PrimeItems.backup_fetch_path = ""

    hub: Any = SimpleNamespace(state=PrimeItems)
    gui = Window(SimpleNamespace(query_event=lambda *_a: None))
    hub.gui = gui
    handlers = userintr_android.AndroidEventHandlers(hub)
    loading = userintr_loading.LoadingEventHandlers(hub) if hasattr(userintr_loading, "LoadingEventHandlers") else None
    gui.event_handlers.android = handlers
    gui.event_handlers.loading = SimpleNamespace(
        file_selected_event=lambda name: loading.file_selected_event(name) if loading else None
    )
    hub.loading = SimpleNamespace(select_single_item_export=lambda _name: None)

    def refresh(_gui: Any, **_options: Any) -> None:
        gui.menus_refreshed += 1

    monkeypatch.setattr(userintr_android, "update_tasker_object_menus", refresh)
    monkeypatch.setattr(userintr_loading, "update_tasker_object_menus", refresh)
    monkeypatch.setattr(userintr_android, "clear_tasker_data", lambda state: None)
    monkeypatch.setattr(userintr_loading, "clear_tasker_data", lambda state: None)
    gui.handlers = handlers
    return gui


def _fill(user: Any, phone: FakeTasker, path: str) -> None:
    ip, port, location = found(user, ui.input)[:3]
    ip.value, port.value, location.value = phone.address, phone.port, path


@pytest.mark.asyncio
async def test_the_panel_fetches_the_backup_the_user_typed_the_path_of(phone: FakeTasker, window: Window) -> None:
    def build() -> None:
        window.android_container = ui.column()
        window.handlers.get_xml_from_android_event()

    async with open_page(build) as user:
        _fill(user, phone, "/Tasker/backup.xml")

        await click(user, "Click Here to Set XML Details")
        await settled(
            lambda: window.messages
        )  # a request on a worker thread: slower than a tenth of a second on Windows

    assert (window.android_ipaddr, window.android_port, window.android_file) == (
        phone.address,
        phone.port,
        "/Tasker/backup.xml",
    )
    assert Path("backup.xml").read_bytes() == _BACKUP, "the file that arrived is the file the loader reads"
    assert window.messages[-1][1] == "Green"
    assert window.menus_refreshed == 1


def _panel(window: Window):
    def build() -> None:
        window.android_container = ui.column()
        window.handlers.get_xml_from_android_event()

    return build


def _texts(user: Any) -> list[str]:
    return [element.text for element in found(user, ui.label)]


@pytest.mark.asyncio
async def test_listing_the_phones_files_offers_them_and_the_one_picked_is_fetched(
    phone: FakeTasker, window: Window
) -> None:
    phone.writes(devicefiles.FILE_LIST_TASK_NAME, "/Tasker/maptasker_files.txt", _FILES, installed=False)

    async with open_page(_panel(window)) as user:
        _fill(user, phone, "")
        await click(user, "List XML Files")
        for _ in range(100):  # the listing is a real request on a worker thread: wait for the picker, not for a guess
            if found(user, ui.select):
                break
            await asyncio.sleep(0.1)
        picker = found(user, ui.select)[0]

        assert picker.options == ["/Tasker/backup.xml", "/Tasker/other.xml"]
        picker.value = "/Tasker/backup.xml"
        for _ in range(100):
            if Path("backup.xml").exists() and window.menus_refreshed:
                break
            await asyncio.sleep(0.1)

    assert Path("backup.xml").read_bytes() == _BACKUP
    assert window.android_file == "/Tasker/backup.xml"
    assert window.menus_refreshed == 1
    assert [colour for _message, colour in window.messages] == ["Green", "Green"]


@pytest.mark.asyncio
async def test_a_phone_that_is_not_there_is_reported_and_nothing_is_fetched(phone: FakeTasker, window: Window) -> None:
    async with open_page(_panel(window)) as user:
        _fill(user, phone, "/Tasker/backup.xml")
        phone.down()

        await click(user, "Click Here to Set XML Details")
        await settled(lambda: window.messages)

    assert "unreachable" in window.messages[-1][0]
    assert window.messages[-1][1] == "Red"
    assert not Path("backup.xml").exists()
    assert window.menus_refreshed == 0


@pytest.mark.asyncio
async def test_a_file_the_phone_does_not_have_is_reported_in_red(phone: FakeTasker, window: Window) -> None:
    async with open_page(_panel(window)) as user:
        _fill(user, phone, "/Tasker/missing.xml")

        await click(user, "Click Here to Set XML Details")
        await settled(lambda: window.messages)

    assert window.messages and window.messages[-1][1] == "Red"
    assert "not found" in window.messages[-1][0]
    assert window.menus_refreshed == 0


@pytest.mark.asyncio
async def test_a_file_that_is_not_a_tasker_backup_is_reported_in_red(phone: FakeTasker, window: Window) -> None:
    phone.files["/Tasker/notes.xml"] = b"<notes><note>hello</note></notes>"

    async with open_page(_panel(window)) as user:
        _fill(user, phone, "/Tasker/notes.xml")

        await click(user, "Click Here to Set XML Details")
        await settled(lambda: window.messages)

    assert any("not valid Tasker XML" in message for message, _colour in window.messages)
    assert all(colour == "Red" for _message, colour in window.messages)
    assert window.menus_refreshed == 0


@pytest.mark.asyncio
async def test_a_listing_that_fails_is_reported_in_red_and_leaves_no_picker(phone: FakeTasker, window: Window) -> None:
    phone.writes(devicefiles.FILE_LIST_TASK_NAME, "/Tasker/maptasker_files.txt", "garbage\n", installed=False)
    devicefiles._FILE_LIST_POLL_ATTEMPTS, saved = 2, devicefiles._FILE_LIST_POLL_ATTEMPTS
    try:
        async with open_page(_panel(window)) as user:
            _fill(user, phone, "")
            await click(user, "List XML Files")
            assert found(user, ui.select) == []
    finally:
        devicefiles._FILE_LIST_POLL_ATTEMPTS = saved

    assert window.messages[-1][1] == "Red"


@pytest.mark.asyncio
async def test_cancelling_the_panel_puts_it_away(phone: FakeTasker, window: Window) -> None:
    async with open_page(_panel(window)) as user:
        await click(user, "Cancel Entry")

        assert found(user, ui.input) == []


# ##################################################################################
# The helper Tasks on the phone
# ##################################################################################
@pytest.mark.asyncio
async def test_the_helper_tasks_the_phone_holds_are_listed_stale_and_current(phone: FakeTasker, window: Window) -> None:
    phone.tasks |= {"MapTasker List Files v0", devicefiles.FILE_LIST_TASK_NAME, "My Own Task"}

    async with open_page(_panel(window)) as user:
        _fill(user, phone, "")
        await click(user, "List Helper Tasks")
        await settled(lambda: "MapTasker List Files v0" in _texts(user))  # listed by a worker thread
        shown = _texts(user)

    assert "MapTasker List Files v0" in shown
    assert devicefiles.FILE_LIST_TASK_NAME in shown
    assert "My Own Task" not in shown, "the user's own Tasks are none of its business"


@pytest.mark.asyncio
async def test_listing_helpers_on_a_phone_that_is_not_there_says_so(phone: FakeTasker, window: Window) -> None:
    async with open_page(_panel(window)) as user:
        _fill(user, phone, "")
        phone.down()
        await click(user, "List Helper Tasks")

        assert user.notify.messages


@pytest.mark.asyncio
async def test_the_helper_project_is_staged_for_import_and_waited_for(
    phone: FakeTasker, window: Window, monkeypatch: pytest.MonkeyPatch
) -> None:
    from maptasker.src.device import deviceverify

    monkeypatch.setattr(deviceverify, "RESULT_POLL_SECONDS", 0)
    monkeypatch.setattr(deviceverify, "MANUAL_IMPORT_POLL_ATTEMPTS", 3)
    phone.imports_uploads_ending.append("MapTasker.prj.xml")

    async with open_page(_panel(window)) as user:
        _fill(user, phone, "")
        await click(user, "Put Helper Tasks in 'MapTasker' Project")
        await __import__("asyncio").sleep(0.3)

        assert any("is now in Tasker" in text for text in user.notify.messages)

    assert "/Tasker/projects/MapTasker.prj.xml" in phone.files
    assert devicefiles.FILE_LIST_TASK_NAME in phone.tasks


@pytest.mark.asyncio
async def test_a_helper_already_on_the_phone_blocks_the_project_and_names_it(phone: FakeTasker, window: Window) -> None:
    phone.tasks.add(devicefiles.FILE_LIST_TASK_NAME)

    async with open_page(_panel(window)) as user:
        _fill(user, phone, "")
        await click(user, "Put Helper Tasks in 'MapTasker' Project")

        assert devicefiles.FILE_LIST_TASK_NAME in _texts(user)

    assert "/Tasker/projects/MapTasker.prj.xml" not in phone.files, "nothing was written for Tasker to reject"


# ##################################################################################
# Importing into Tasker, and saving a file on the phone
# ##################################################################################
import asyncio

from maptasker.src.device import deviceoffer, deviceverify
from maptasker.src.edit import roundtrip

_PROFILE = b"<TaskerData><Profile sr='prof1'><id>1</id><nme>Morning</nme></Profile></TaskerData>"


async def _in_a_page(window: Window, work: Callable[[ui.dialog, ui.dialog], Awaitable[None]]) -> AsyncIterator[Any]:
    """Run `work(android_dialog, parent_dialog)` inside a page, as a button's handler would, and return the user."""
    finished = asyncio.Event()

    def build() -> None:
        android, parent = ui.dialog(), ui.dialog()

        async def go() -> None:
            try:
                await work(android, parent)
            finally:
                finished.set()

        ui.button("go", on_click=go)

    async with open_page(build) as user:
        await click(user, "go")
        await asyncio.wait_for(finished.wait(), 10)
        yield user


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """The overwrite prompts put up, each with the callback that 'Yes' would run."""
    prompts: list[dict[str, Any]] = []
    monkeypatch.setattr(
        userintr_android,
        "build_overwrite_confirm_dialog",
        lambda what, on_confirm, **options: prompts.append({"what": what, "yes": on_confirm, **options}),
    )
    return prompts


@pytest.fixture
def tasker_asked_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def nothing(*_a: Any, **_k: Any) -> list[str]:
        return []

    monkeypatch.setattr(userintr_android, "what_tasker_already_has", nothing)


@pytest.fixture
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deviceverify, "RESULT_POLL_SECONDS", 0)
    monkeypatch.setattr(deviceoffer, "_OPEN_POLL_ATTEMPTS", 2)
    monkeypatch.setattr(deviceverify, "CONFIRM_POLL_ATTEMPTS", 2)


def _into_tasker(phone: FakeTasker, android: ui.dialog, parent: ui.dialog, kept: list[str]):
    return userintr_android.IntoTaskerOffer(
        xml_bytes=_PROFILE,
        object_name="Morning",
        confirm_names=["Morning"],
        route=deviceoffer.OPEN_FILE_ROUTE,
        ip_address=phone.address,
        ip_port=phone.port,
        android_dialog=android,
        parent_dialog=parent,
        keep_edit=lambda: kept.append("kept"),
    )


@pytest.mark.asyncio
async def test_a_profile_is_imported_into_tasker_and_the_user_is_told_when_it_arrives(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, quick: None
) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    kept: list[str] = []

    async for user in _in_a_page(
        window, lambda a, p: window.handlers._offer_into_tasker(_into_tasker(phone, a, p, kept))
    ):
        assert any("is now in Tasker" in text for text in user.notify.messages)

    assert asked == [], "nothing was at the path, so there was nothing to ask"
    assert kept == ["kept"], "the edit is kept once the screen is up on the phone"
    assert phone.files["/Tasker/profiles/Morning.prf.xml"] == _PROFILE
    assert (window.android_ipaddr, window.android_port) == (phone.address, phone.port)


@pytest.mark.asyncio
async def test_a_profile_file_already_on_the_phone_is_asked_about_and_kept_when_confirmed(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, quick: None
) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    phone.files["/Tasker/profiles/Morning.prf.xml"] = b"<TaskerData>the old one</TaskerData>"
    kept: list[str] = []

    async for _user in _in_a_page(
        window, lambda a, p: window.handlers._offer_into_tasker(_into_tasker(phone, a, p, kept))
    ):
        pass

    assert [prompt["what"] for prompt in asked] == ["'/Tasker/profiles/Morning.prf.xml' on the Android device"]
    assert kept == [], "nothing was sent until the user said yes"
    assert phone.files["/Tasker/profiles/Morning.prf.xml"] == b"<TaskerData>the old one</TaskerData>"


@pytest.mark.asyncio
async def test_saying_yes_to_the_overwrite_sends_it_and_keeps_a_copy_of_the_old_one(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, quick: None
) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    phone.files["/Tasker/profiles/Morning.prf.xml"] = b"<TaskerData>the old one</TaskerData>"
    kept: list[str] = []

    def build() -> None:
        android, parent = ui.dialog(), ui.dialog()
        offer = _into_tasker(phone, android, parent, kept)

        async def go() -> None:
            await window.handlers._offer_into_tasker(offer)

        ui.button("go", on_click=go)

    async with open_page(build) as user:
        await click(user, "go")
        await asyncio.sleep(0.5)
        asked[0]["yes"]()
        await asyncio.sleep(1)

    assert phone.files["/Tasker/profiles/Morning.prf.xml"] == _PROFILE
    assert kept == ["kept"]
    assert any(
        path.read_bytes() == b"<TaskerData>the old one</TaskerData>" for path in Path.cwd().rglob("*") if path.is_file()
    ), "the file it replaced is kept on this computer"


@pytest.mark.asyncio
async def test_an_import_the_phone_cannot_perform_is_reported_and_keeps_nothing(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, quick: None
) -> None:
    kept: list[str] = []
    phone.down()

    async for _user in _in_a_page(
        window, lambda a, p: window.handlers._offer_into_tasker(_into_tasker(phone, a, p, kept))
    ):
        pass

    assert kept == []


def _file_save(phone: FakeTasker, saved: list[str], **overrides: Any):
    def save(ip_address: str, ip_port: str, **_keywords: Any) -> tuple[int, str]:
        code, message = maputil2.http_upload_request(ip_address, ip_port, "Tasker/tasks", "Opener.tsk.xml", b"<x/>")
        if code == 0:
            saved.append("saved")
        return code, "/Tasker/tasks/Opener.tsk.xml" if code == 0 else message

    spec = {
        "subject": "Task",
        "device_path": "/Tasker/tasks/Opener.tsk.xml",
        "verify": lambda: roundtrip.RoundTripReport(),
        "render": lambda: "<TaskerData/>",
        "save": save,
        "before_address": (),
        "after_saved": lambda: saved.append("kept"),
    }
    return userintr_android.FileSave(**{**spec, **overrides})


def _refs(phone: FakeTasker) -> dict[str, Any]:
    return {
        "ip_address": SimpleNamespace(value=phone.address),
        "ip_port": SimpleNamespace(value=phone.port),
        "verify": SimpleNamespace(value=False),
    }


@pytest.mark.asyncio
async def test_a_new_file_is_saved_on_the_phone_without_asking(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    saved: list[str] = []

    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers._save_file_to_device(_file_save(phone, saved), _refs(phone), a, p),
    ):
        assert any("saved to Android device" in text for text in user.notify.messages)

    assert asked == []
    assert saved == ["saved", "kept"]
    assert phone.files["/Tasker/tasks/Opener.tsk.xml"] == b"<x/>"


@pytest.mark.asyncio
async def test_a_file_already_there_is_not_replaced_until_the_user_says_so(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    phone.files["/Tasker/tasks/Opener.tsk.xml"] = b"<old/>"
    saved: list[str] = []

    async for _user in _in_a_page(
        window,
        lambda a, p: window.handlers._save_file_to_device(_file_save(phone, saved), _refs(phone), a, p),
    ):
        pass

    assert len(asked) == 1
    assert phone.files["/Tasker/tasks/Opener.tsk.xml"] == b"<old/>"
    assert saved == []


@pytest.mark.asyncio
async def test_what_tasker_already_has_is_put_in_the_prompt_even_for_a_new_file(
    phone: FakeTasker, window: Window, asked: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def has(*_a: Any, **_k: Any) -> list[str]:
        return ["Tasker already has Task 'Opener'."]

    monkeypatch.setattr(userintr_android, "what_tasker_already_has", has)

    async for _user in _in_a_page(
        window,
        lambda a, p: window.handlers._save_file_to_device(_file_save(phone, []), _refs(phone), a, p),
    ):
        pass

    assert asked[0]["tasker_lines"] == ["Tasker already has Task 'Opener'."]
    assert asked[0]["file_absent"] is True


@pytest.mark.asyncio
async def test_a_save_that_fails_on_the_phone_says_so_and_keeps_nothing(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    saved: list[str] = []
    spec = _file_save(phone, saved, save=lambda *_a, **_k: (8, "the phone said no"))

    async for user in _in_a_page(window, lambda a, p: window.handlers._save_file_to_device(spec, _refs(phone), a, p)):
        assert any("the phone said no" in text for text in user.notify.messages)

    assert saved == []


@pytest.mark.asyncio
async def test_a_document_that_fails_the_verify_check_never_reaches_the_phone(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(userintr_android, "round_trip_verified", lambda _refs, _verify: False)
    saved: list[str] = []

    async for _user in _in_a_page(
        window,
        lambda a, p: window.handlers._save_file_to_device(_file_save(phone, saved), _refs(phone), a, p),
    ):
        pass

    assert phone.requests == []
    assert saved == []


# ##################################################################################
# Saving a Task to the phone: written, imported, confirmed, and the way out when it is not
# ##################################################################################
from maptasker.src.edit import taskedit


def _a_new_task(name: str = "Opener"):
    return taskedit.create_new_task(name, "100", state=PrimeItems)


def _task_refs(name: str = "Opener") -> dict[str, Any]:
    return {"name": SimpleNamespace(value=name), "priority": SimpleNamespace(value="100")}


@pytest.fixture
def kept_tasks(window: Window) -> list[tuple]:
    kept: list[tuple] = []
    window.event_handlers.android.hub.editors = SimpleNamespace(
        keep_task_in_loaded_config=lambda *args: kept.append(args)
    )
    return kept


async def _save_task(window: Window, phone: FakeTasker, edited: Any, name: str = "Opener") -> AsyncIterator[Any]:
    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers.save_task_to_android_event(edited, _task_refs(name), _refs(phone), a, p),
    ):
        yield user


@pytest.mark.asyncio
async def test_a_new_task_is_written_imported_confirmed_and_kept(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    edited = _a_new_task()

    async for user in _save_task(window, phone, edited):
        assert any("Task Uploaded to Tasker" in text for text in user.notify.messages)

    assert asked == []
    assert "/Tasker/tasks/Opener.tsk.xml" in phone.files, "the file the import was made from is left on the phone"
    assert "Opener" in phone.tasks
    assert [(args[1], args[2]) for args in kept_tasks] == [("Opener", True)]


@pytest.mark.asyncio
async def test_a_task_name_the_backup_already_has_is_refused_before_the_phone_is_touched(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    existing = next(iter(PrimeItems.tasker_root_elements["all_tasks_by_name"]))
    edited = _a_new_task("Something Else")
    phone.requests.clear()

    async for user in _save_task(window, phone, edited, name=existing):
        assert any("already exists" in text for text in user.notify.messages)

    assert phone.requests == []
    assert kept_tasks == []


@pytest.mark.asyncio
async def test_an_empty_name_is_refused_with_the_reason(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    async for user in _save_task(window, phone, _a_new_task(), name="  "):
        assert any("cannot be empty" in text for text in user.notify.messages)

    assert phone.requests == []


@pytest.mark.asyncio
async def test_an_import_tasker_does_not_commit_is_tried_once_more_from_the_file_on_the_phone(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    phone.ignored_imports.add("Opener")

    async for user in _save_task(window, phone, _a_new_task()):
        assert any("Task Uploaded to Tasker." in text for text in user.notify.messages)

    imports = phone.seen("POST", "/api/import")
    assert len(imports) == 2, "the import and the retry; the retry is made from the file already on the phone"
    assert phone.seen("GET", "/file/Tasker/tasks/Opener.tsk.xml")


@pytest.mark.asyncio
async def test_a_retry_the_phone_refuses_hands_the_file_to_androids_chooser(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    route = deviceoffer.OPEN_TASK_ROUTE
    phone.ignored_imports.add("Opener")
    phone.import_script = [200, 500]
    phone.user_taps_import(route.task_name, route.read_path, route.header)

    async for user in _save_task(window, phone, _a_new_task()):
        assert any("handed to Android's 'Open with'" in text for text in user.notify.messages)

    assert phone.files["/Tasker/tasks/Opener.tsk.xml"], "and the user can import it by hand from Tasker's own browser"


@pytest.mark.asyncio
async def test_when_every_way_of_importing_fails_the_user_is_told(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    phone.ignored_imports |= {"Opener", deviceoffer.OPEN_TASK_ROUTE.task_name}
    phone.import_script = [200, 500]

    async for user in _save_task(window, phone, _a_new_task()):
        assert any("Unable to upload Task to Tasker" in text for text in user.notify.messages)


@pytest.mark.asyncio
async def test_a_key_the_phone_stops_accepting_is_replaced_during_the_save(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None
) -> None:
    maputil2.auth_key_for(phone.address, phone.port)
    phone.reject_keys = 1

    async for user in _save_task(window, phone, _a_new_task()):
        assert any("Task Uploaded to Tasker" in text for text in user.notify.messages)

    assert len(phone.seen("GET", "/api/auth")) == 2


@pytest.mark.asyncio
async def test_a_task_tasker_already_has_is_said_in_the_prompt(
    phone: FakeTasker, window: Window, asked: list, kept_tasks: list, quick: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real check, not the stub: the names in the document sent are asked of the phone."""
    monkeypatch.setattr(userintr_android, "what_tasker_already_has", _REAL_WHAT_TASKER_ALREADY_HAS)
    phone.tasks.add("Opener")

    async for _user in _save_task(window, phone, _a_new_task()):
        pass

    [prompt] = asked
    assert any("Opener" in line for line in prompt["tasker_lines"])
    assert "/Tasker/tasks/Opener.tsk.xml" not in phone.files, "nothing is written until the user agrees"


_REAL_WHAT_TASKER_ALREADY_HAS = userintr_android.what_tasker_already_has


# ##################################################################################
# Profiles
# ##################################################################################
from maptasker.src.edit import profedit


def _a_profile():
    name = next(iter(PrimeItems.tasker_root_elements["all_profiles_by_name"]))
    return name, required(profedit.load_profile_for_edit(name, state=PrimeItems))


@pytest.fixture
def kept_profiles(window: Window) -> list[tuple]:
    kept: list[tuple] = []
    editors = getattr(window.event_handlers.android.hub, "editors", None) or SimpleNamespace()
    editors.keep_profile_in_loaded_config = lambda *args: kept.append(args)
    window.event_handlers.android.hub.editors = editors
    return kept


def _profile_refs(name: str, edited: Any = None, **extra: Any) -> dict[str, Any]:
    """The dialog's fields as they stand when nothing has been changed: its name, and each Time condition's times."""
    refs: dict[str, Any] = {"name": SimpleNamespace(value=name)}
    for condition in getattr(edited, "conditions", []):
        if condition.cond_type == "Time":
            for field, value in profedit.get_time_field_values(condition).items():
                refs[profedit.condition_field_key(condition.cond_index, field)] = SimpleNamespace(value=value)
    return {**refs, **extra}


@pytest.mark.asyncio
async def test_a_profile_is_saved_as_a_file_on_the_phone(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, kept_profiles: list
) -> None:
    name, edited = _a_profile()

    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers.save_profile_to_android_event(
            edited, _profile_refs(name, edited), _refs(phone), a, p
        ),
    ):
        assert any("saved to Android device" in text for text in user.notify.messages)

    path = profedit.android_profile_path(name)
    assert b"<Profile" in phone.files[path]
    assert [(args[1], args[2]) for args in kept_profiles] == [(name, False)]
    assert phone.profiles == set(), "a file on the phone's storage is not an import into Tasker"


@pytest.mark.asyncio
async def test_a_profile_is_imported_into_tasker_through_its_import_screen(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, kept_profiles: list, quick: None
) -> None:
    route = deviceoffer.OPEN_FILE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    name, edited = _a_profile()

    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers.import_profile_into_tasker_event(
            edited, _profile_refs(name, edited), _refs(phone), a, p
        ),
    ):
        assert any("is now in Tasker" in text for text in user.notify.messages)

    assert name in phone.profiles
    assert [args[1] for args in kept_profiles] == [name]


@pytest.mark.asyncio
async def test_a_profile_with_no_name_is_refused_before_the_phone_is_touched(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, kept_profiles: list
) -> None:
    _name, edited = _a_profile()

    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers.save_profile_to_android_event(
            edited, _profile_refs(" ", edited), _refs(phone), a, p
        ),
    ):
        assert any("cannot be empty" in text for text in user.notify.messages)

    assert phone.requests == [] and kept_profiles == []


@pytest.mark.asyncio
async def test_a_new_profile_must_belong_to_a_project_and_have_a_new_name(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, kept_profiles: list
) -> None:
    name, edited = _a_profile()
    refs = _profile_refs(name, edited, target_project_name="")

    async for user in _in_a_page(
        window, lambda a, p: window.handlers.save_profile_to_android_event(edited, refs, _refs(phone), a, p)
    ):
        assert any("already exists" in text for text in user.notify.messages)
        assert any("Choose a Project first" in text for text in user.notify.messages)

    assert phone.requests == [] and kept_profiles == []


# ##################################################################################
# Projects and Scenes
# ##################################################################################
from maptasker.src.edit import projedit, sceneedit


def _a_project():
    return required(projedit.load_project_for_edit("Home", state=PrimeItems))


def _a_scene(name: str = "Panel"):
    new = sceneedit.create_new_scene(name, state=PrimeItems)
    assert not isinstance(new, str)
    sceneedit.register_new_scene(new, state=PrimeItems)
    return required(sceneedit.load_scene_for_edit(name, state=PrimeItems))


@pytest.mark.asyncio
async def test_a_project_is_saved_as_a_file_with_its_profiles_and_tasks(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    edited = _a_project()

    async for user in _in_a_page(
        window, lambda a, p: window.handlers.save_project_to_android_event(edited, {}, _refs(phone), a, p)
    ):
        assert any("saved to Android device" in text for text in user.notify.messages)

    saved = phone.files[projedit.android_project_path("Home")]
    assert b"<Project" in saved and b"Dawn" in saved and b"Morning" in saved


@pytest.mark.asyncio
async def test_a_project_with_a_field_nobody_applies_is_refused_before_the_phone_is_touched(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    edited = _a_project()

    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers.save_project_to_android_event(
            edited, {"a_new_field": SimpleNamespace(value="x")}, _refs(phone), a, p
        ),
    ):
        assert user.notify.messages

    assert phone.requests == []


@pytest.mark.asyncio
async def test_a_project_is_imported_into_tasker_and_confirmed_by_its_profiles(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, quick: None
) -> None:
    route = deviceoffer.OPEN_PROJECT_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    edited = _a_project()

    async for user in _in_a_page(
        window, lambda a, p: window.handlers.import_project_into_tasker_event(edited, {}, _refs(phone), a, p)
    ):
        assert any("is now in Tasker" in text for text in user.notify.messages)

    assert "Dawn" in phone.profiles
    assert "/Tasker/projects/Home.prj.xml" in phone.files


@pytest.mark.asyncio
async def test_a_scene_is_saved_as_a_file_on_the_phone(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    edited = _a_scene()

    async for user in _in_a_page(
        window, lambda a, p: window.handlers.save_scene_to_android_event(edited, {}, _refs(phone), a, p)
    ):
        assert any("saved to Android device" in text for text in user.notify.messages)

    assert b"<Scene" in phone.files[sceneedit.android_scene_path("Panel")]


@pytest.mark.asyncio
async def test_a_scene_size_that_is_not_a_number_is_refused_before_the_phone_is_touched(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None
) -> None:
    edited = _a_scene()
    key = sceneedit.SCENE_DIMENSION_FIELDS[0][0]

    async for user in _in_a_page(
        window,
        lambda a, p: window.handlers.save_scene_to_android_event(
            edited, {key: SimpleNamespace(value="wide")}, _refs(phone), a, p
        ),
    ):
        assert any("must be a whole number" in text for text in user.notify.messages)

    assert phone.requests == []


@pytest.mark.asyncio
async def test_a_scene_is_imported_through_the_chooser_and_the_file_is_named_for_the_user(
    phone: FakeTasker, window: Window, asked: list, tasker_asked_nothing: None, quick: None
) -> None:
    route = deviceoffer.OPEN_SCENE_ROUTE
    phone.user_taps_import(route.task_name, route.read_path, route.header)
    edited = _a_scene()

    async for user in _in_a_page(
        window, lambda a, p: window.handlers.import_scene_into_tasker_event(edited, {}, _refs(phone), a, p)
    ):
        assert any("is now in Tasker" in text for text in user.notify.messages)

    assert "Panel" in phone.scenes
