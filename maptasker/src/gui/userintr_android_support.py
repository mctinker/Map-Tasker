"""What the Android handlers lean on: asking Tasker what it already has, the overwrite and Verify questions, listing the phone's files, and the offer to Tasker's import screen and its report."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nicegui import run, ui

from maptasker.src.core import presave
from maptasker.src.core.maputil2 import (
    http_request,
    suppress_logged,
    translate_string,
)
from maptasker.src.core.sysconst import logger
from maptasker.src.device import devicecheck, devicefiles, deviceoffer, deviceverify
from maptasker.src.gui.guiutils_android import (
    clear_android_buttons,
)
from maptasker.src.gui.guiwins import build_round_trip_report_dialog
from maptasker.src.mapgen.getbakup import validate_xml_file

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nicegui.client import Client

    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit import (
        roundtrip,
    )
    from maptasker.src.gui.userintr import MyGui
    from maptasker.src.gui.userintr_group import HandlerGroup


async def what_tasker_already_has(
    ip_address: str,
    ip_port: str,
    render_xml: Callable[[], str | bytes],
    consequence: str,
    state: RunState,
    *,
    check_ids: bool = False,
) -> list[str]:
    """The lines a save's prompt adds for what Tasker already has -- [] when there is nothing to say.

    Called by all six device write paths (the five Save To Android handlers and
    _offer_into_tasker, which the three Import Into Tasker buttons share), right after their
    file-existence read, so one prompt answers every question.  The names come from the very
    document being sent -- see devicecheck.names_in_export -- rendered once more for the purpose;
    a render that raises leaves the save to report it.

    `consequence` is added only when something IS there, because it describes what happens to
    those objects; a check that merely could not run has nothing to say about them.

    check_ids is the panel's "Check IDs" box.  Ticked, the device makes a fresh backup and both
    questions are answered from it (devicecheck.check_against_device_backup) -- names included, so
    Projects need no helper of their own.  A backup that cannot be had is said so, and the names
    are then asked for the ordinary way, since that answer is still worth having.
    """
    try:
        xml = render_xml()
    except ValueError:
        return []
    sent = devicecheck.names_in_export(xml)
    if not any(sent.values()):
        return []

    check = None
    id_lines: list[str] = []
    if check_ids:
        ui.notify("Taking a fresh backup on the device to check IDs -- this can take a little while.", type="info")
        checked = await run.io_bound(devicecheck.check_against_device_backup, ip_address, ip_port, xml, state=state)
        check, findings, problem = checked
        id_lines = [f"Could not check IDs: {problem}"] if problem else devicecheck.describe_id_findings(findings)

    if check is None:
        if sent.get("Project"):
            # Seconds rather than one request, and a MapTasker Task put on the phone the first time
            # -- worth saying before it happens rather than leaving the button looking stuck.
            ui.notify(
                "Checking which Projects, Profiles, Scenes and Tasks Tasker already has -- "
                "a small MapTasker Task runs on the device for this.",
                type="info",
            )
        check = await run.io_bound(devicecheck.check_tasker_for_existing, ip_address, ip_port, sent, state=state)

    name_lines = devicecheck.describe_tasker_check(check)
    if any(check.present.values()):
        name_lines.append(consequence)
    return [*name_lines, *id_lines]


# What a prompt says after naming what Tasker already has, by how the objects would get there.
API_IMPORT_CONSEQUENCE = (
    "Tasker's import refuses a Task whose name it already has, and does not replace it: delete or rename the one on "
    "the device first, or save a file instead."
)
FILE_WRITE_CONSEQUENCE = "This only writes the file -- nothing in Tasker changes until it is imported."
IMPORT_SCREEN_CONSEQUENCE = "Tasker's import screen will ask whether to replace them."


@dataclass(frozen=True)
class FileSave:
    """What differs between saving a Task, a Scene, a Profile and a Project as a file on the device.

    Everything else about those four saves is the same, and is AndroidEventHandlers._save_file_to_device.
    """

    subject: str  # "Task", "Scene", "Profile" or "Project": how the success message reads
    device_path: str  # where /upload will put it
    verify: Callable[[], roundtrip.RoundTripReport]  # the Verify box's check
    render: Callable[[], str | bytes]  # the XML it would write, to ask Tasker what it already has
    save: Callable[..., Any]  # uploads and reads back; run on a worker thread
    before_address: tuple[Any, ...]  # what `save` is given ahead of the device's address ...
    after_address: tuple[Any, ...] = ()  # ... and after it
    after_saved: Callable[[], None] | None = None  # what to keep in the loaded configuration once it is there
    consequence: str = FILE_WRITE_CONSEQUENCE  # what the prompt says happens to what Tasker already has
    # Says how it went, instead of the plain "saved": (ip address, port, where it landed, the note about the
    # copy it replaced) -> False to leave the dialogs open.  The Task import uses it to wait for Tasker.
    report: Callable[[str, str, str, str], Awaitable[bool]] | None = None


def check_ids_ticked(android_field_refs: dict[str, Any]) -> bool:
    """The Save To Android panel's "Check IDs" box -- see guiwins.android_device_fields."""
    checkbox = android_field_refs.get("check_ids")
    return bool(checkbox is not None and checkbox.value)


def overwrite_prompt_options(exists: bool | None, tasker_lines: list[str]) -> dict[str, Any]:
    """build_overwrite_confirm_dialog's keyword arguments for a device write: the file's own
    answer, plus Tasker's lines only when there are some -- a prompt with none is the file
    prompt exactly as it always was.
    """
    options: dict[str, Any] = {"unknown": exists is None}
    if tasker_lines:
        options.update(file_absent=exists is False, tasker_lines=tasker_lines)
    return options


def round_trip_verified(
    android_field_refs: dict[str, Any],
    verifier: Callable[[], roundtrip.RoundTripReport],
) -> bool:
    """The Save To Android panel's "Verify" checkbox, answered.  False stops the save.

    Called by all eight Save To Android / Import Into Tasker handlers, at the same point in
    each: after the dialog's edits have been applied (there is nothing meaningful to render
    before that) and BEFORE ping_android_device, so a document that fails never reaches the
    device at all -- not even the reachability probe.  What it checks and why is
    roundtrip.py's header.

    Unticked is the old behaviour exactly: no render, no parse, no message.  `verifier` is a
    callable rather than a report so that stays true -- the check costs nothing when it is
    not wanted, including the second render it would otherwise do to produce one.

    A pass is worth saying out loud.  A user who ticked this did so because they wanted to
    be told, and "Verified: 5 objects came back identical" ahead of the save's own success
    message is the difference between a check that ran and a checkbox that did nothing.
    """
    checkbox = android_field_refs.get("verify")
    if checkbox is None or not checkbox.value:
        return True

    report = verifier()
    if report.ok:
        ui.notify(report.summary(), type="positive")
        return True

    logger.error(f"Save To Android refused by Verify: {report.summary()}")
    ui.notify(report.summary(), type="negative")
    build_round_trip_report_dialog(report)
    return False


async def _validate_chosen_file(
    self: MyGui,
    android_ipaddr: str,
    android_port: str,
    android_file: str,
) -> tuple[int, str, str, str]:
    """Fetch the file the user named from the device and check its XML.  Return code 0 if it is good, else 1.

    Every request goes to run.io_bound, so the GUI stays responsive; a request cancelled with the
    page raises CancelledError (see the note at the top of userintr_android.py) and ends the call.
    """
    failed = 1, android_ipaddr, android_port, android_file
    fetched = await run.io_bound(
        http_request,
        android_ipaddr,
        android_port,
        android_file,
        "file",
        "?download=1",
    )
    return_code, _ = fetched
    if return_code != 0:
        return failed

    # Validate the XML syntax structure
    self.state.program_arguments.gui = True
    validated = await run.io_bound(validate_xml_file, android_ipaddr, android_port, android_file, state=self.state)
    return_code, error_message = validated
    if return_code != 0:
        self.display_message_box(error_message, "Red")
        return failed
    if self.state.backup_fetch_path:
        self.display_message_box(
            f"{translate_string('Backup file saved to')} {self.state.backup_fetch_path}",
            "Green",
        )
    return 0, android_ipaddr, android_port, android_file


def _mount_file_picker(self: MyGui, filelist: list[str]) -> None:
    """Draw the dropdown of the device's XML files, and a Cancel Entry button that puts it away again."""
    # Clean slate the container before rendering the picker options
    if hasattr(self, "android_container") and self.android_container:
        self.android_container.clear()
        self.android_container.classes(remove="hidden")
    else:
        # Fallback placeholder if no container container is declared
        self.android_container = ui.column().classes("w-full gap-2 p-2")

    # Mount the native interactive picking layout inside the container tree context
    with self.android_container:
        ui.separator().classes("my-2")

        self.filelist_label = (
            ui.label(translate_string("Select XML From Android Device:"))
            .classes(
                "text-xs font-bold text-purple-600 mt-1 self-start",
            )
            .tooltip(
                translate_string(
                    "This will reach out to your Android device to list the available XML files belonging to Tasker.",
                ),
            )
        )

        # OptionMenu transforms to a reactive NiceGUI ui.select dropdown
        self.filelist_option = ui.select(
            options=filelist,
            label=translate_string("Available Android Backups"),
            on_change=lambda e: self.event_handlers.loading.file_selected_event(e.value),
        ).classes("w-full q-mt-none")

        # Flat modern action button to easily close the selection panel
        ui.button(
            translate_string("Cancel Entry"),
            on_click=lambda: (self.android_container.clear(), self.android_container.classes(add="hidden")),
        ).classes("text-xs w-full mt-2").props("outline color=negative dense")


async def _offer_file_list(
    self: MyGui,
    android_ipaddr: str,
    android_port: str,
    android_file: str,
) -> tuple[int, str, str, str]:
    """List the device's XML files in a dropdown and suspend the fetch until one is picked (return code 2)."""
    clear_android_buttons(self)

    ui.notify(
        translate_string("Listing the XML files on the Android device..."),
        type="info",
        timeout=1500,
    )
    listed = await run.io_bound(
        devicefiles.get_list_of_files, android_ipaddr, android_port, devicefiles.FILE_LIST_DIRECTORY, state=self.state
    )
    return_code, filelist = listed
    if return_code != 0 or not isinstance(filelist, list):
        self.display_message_box(str(filelist), "Red")
        return 1, android_ipaddr, android_port, android_file

    _mount_file_picker(self, filelist)

    # Save connection details to state
    self.android_ipaddr = android_ipaddr
    self.android_port = android_port

    # Return status code 2 to indicate layout suspension until user selects a file item.
    return (2, "", "", "")


async def validate_or_filelist_xml(
    self: MyGui,
    android_ipaddr: str,
    android_port: str,
    android_file: str,
) -> tuple[int, str, str, str]:
    """
    Validates an XML file on an Android device or generates a NiceGUI dropdown
    selection list if no file or an explicit 'list files' action is requested.

    Asynchronous because the file listing is no longer a single quick GET: it installs
    (once) and runs a helper Task on the device and waits for the file that Task writes,
    which takes seconds.  Every request to the device goes to run.io_bound so the GUI stays
    responsive while it happens; everything else here builds widgets and must stay on this thread.
    """
    # 1. If a file is specified and we aren't explicitly listing files, validate it
    if len(android_file) != 0 and android_file != "" and not self.list_files:
        return await _validate_chosen_file(self, android_ipaddr, android_port, android_file)

    # 2. File location not provided or "List Files" requested.
    # Fetch the directory catalog and present a NiceGUI ui.select component.
    return await _offer_file_list(self, android_ipaddr, android_port, android_file)


@dataclass
class IntoTaskerOffer:
    """What AndroidEventHandlers._offer_into_tasker is asked to put in front of Tasker.

    Everything the three Import Into Tasker buttons do once their own validation is past is
    the same: they differ in what they render, what confirms it and what they have to keep
    afterwards, and in nothing else.  This is those differences, set out as fields.
    """

    xml_bytes: bytes  # the rendered Profile, Project or Scene
    object_name: str  # what it is called, and so the name its staged file is written under
    # What is asked about at the route's own endpoint to confirm the import: /api/scenes for a
    # Scene, /api/profiles for a Profile and -- since there is no /api/projects -- for the
    # Profiles a Project brings with it.
    confirm_names: list[str]
    route: deviceoffer.OfferRoute
    ip_address: str
    ip_port: str
    android_dialog: ui.dialog
    parent_dialog: ui.dialog
    # What to keep once the screen is up on the phone: registering an edited Profile into the
    # loaded configuration, and nothing at all for a Project or a Scene, both of which are
    # exported from the live tree by name (a Scene's edits are already in it by the time this
    # runs) and so have nothing left to register.
    keep_edit: Callable[[], None]
    # What the user does if Tasker is not in the "Open with..." chooser, in their own terms
    # ("import it with Tasker's 'Scenes > Import One Scene'").  Every kind has such a step --
    # the file is in Tasker's own folder under its own name precisely so that it does -- but
    # only a Scene has one worth spelling out, since its import is several menus deep.
    by_hand: str = ""
    # How long to keep asking whether the import arrived; 0 leaves deviceverify.await_import's
    # own default, which suits an import screen already in front of the user.  A Scene passes
    # a longer one: its user has a file picker to work through.
    attempts: int = 0
    # The panel's "Check IDs" box, passed on to what_tasker_already_has.
    check_ids: bool = False


class IntoTaskerRun:
    """One Import Into Tasker, from the overwrite question having been answered to the report.

    AndroidEventHandlers._offer_into_tasker asks what is already on the device and, if there is
    anything, puts a prompt in front of the user; what happens next is here.  Holding it
    together lets the prompt's callback and the direct path share it as methods rather than as
    closures over a dozen locals.
    """

    def __init__(
        self,
        handlers: HandlerGroup,
        offer: IntoTaskerOffer,
        device_read_path: str,
        device_path: str,
        already_there: bytes,
    ) -> None:
        """
        Args:
            handlers: The event handlers, for the window and the run's state.
            offer: What is being imported.
            device_read_path: Where on the device a file of this name would be read from.
            device_path: Where the staged file is on the device, as the user would say it.
            already_there: What was already at device_read_path, for the safety copy.
        """
        self.handlers = handlers
        self.offer = offer
        self.device_read_path = device_read_path
        self.device_path = device_path
        self.already_there = already_there
        # Captured by the prompt's path, in the handler's own task; see offer_from_the_prompt.
        self.client: Client

    async def offer_from_the_prompt(self) -> None:
        """run_offer, run from the overwrite prompt's callback, with a slot to build into.

        NOT A WRAPPER FOR THE SAKE OF IT.  nicegui's slot stack is per-asyncio-task
        (nicegui.slot.Slot.get_stack is keyed by task id), so a coroutine started with
        create_task begins with an empty one -- and ui.notify and ui.notification build
        elements, which need a slot.  Every notification in run_offer therefore raised
        'the slot stack for this task is empty' the moment the offer ran from the prompt
        rather than directly, which is exactly what nicegui's own message tells you to
        fix by entering the target explicitly.

        The client is captured out there, in the handler's own task, where there is one.
        Entering it here pushes its slot onto THIS task's stack, and it stays pushed
        across the awaits inside because the whole of run_offer is awaited within the block.
        """
        with self.client:
            await self.run_offer()

    def start_offer(self) -> None:
        """Spawn the offer, and do not lose what it raises.

        A bare create_task drops the exception: asyncio prints "Task exception was
        never retrieved" to the console and the user is left watching an import that
        silently never happens.  Not hypothetical -- that is exactly how the missing
        slot above went unnoticed until someone read their terminal.  The same
        treatment guiwins_nav.report_view_failure gives a view's rendering task.
        """
        asyncio.create_task(self.offer_from_the_prompt()).add_done_callback(report_offer_failure)

    async def run_offer(self) -> None:
        """Everything the offer does once the overwrite question has been answered."""
        offer = self.offer
        self._keep_safety_copy()

        confirmable = await self._import_is_confirmable()
        offered = await self._offer_to_device()
        return_code, message = offered
        if return_code != 0:
            ui.notify(f"Could not import into Tasker: {message}", type="negative")
            return

        # Remember the connection details for next time, same as the Get XML dialog does.
        self.handlers.gui.android_ipaddr = offer.ip_address
        self.handlers.gui.android_port = offer.ip_port

        # Closed before the edit is kept rather than after, so that a failure in keeping it
        # cannot be what leaves the panel on screen.
        offer.android_dialog.close()
        offer.parent_dialog.close()
        offer.keep_edit()

        subject = f"{offer.route.label} '{offer.object_name}'"
        waiting = self._where_the_file_is()

        if confirmable is not True:
            self._report_unconfirmable(subject, waiting)
            return

        await self._report_outcome(subject, waiting)

    def _keep_safety_copy(self) -> None:
        """Keep whatever is already at that path before /upload writes over it.

        The device keeps no versions and has no undo, so this is the only copy of it there
        will ever be, and it is kept on this computer rather than beside the original
        -- see presave.save_android_safety_copy.  The bytes come from the check made before
        the prompt rather than from a second GET, for the reason given there.  A copy that fails
        is reported and the import goes ahead: presave's module comment says why it
        must never block one.
        """
        copied, safety_copy = presave.save_android_safety_copy(self.device_read_path, self.already_there)
        if not copied:
            ui.notify(
                f"Could not copy the file already on the device first: {safety_copy}",
                type="warning",
            )

    async def _import_is_confirmable(self) -> bool | None:
        """Whether Tasker can say afterwards that the import arrived.

        Asked before the offer, not after, because after the import the answer means
        nothing.  None ('could not ask') is treated the same as False: neither can be
        confirmed, and guessing the other way would turn an unconfirmable import into a
        reported success.
        None is this call's own answer for 'could not ask'.  A cancelled wait raises
        CancelledError, as every other await here does, and the import is not offered.
        """
        offer = self.offer
        return await run.io_bound(
            deviceverify.import_is_confirmable,
            offer.ip_address,
            offer.ip_port,
            offer.confirm_names,
            offer.route.confirm_endpoint,
        )

    async def _offer_to_device(self) -> tuple[int, str]:
        """Stage the file and have a helper Task on the device hand it to Tasker.

        Blocking -- it installs a Task, uploads, runs and polls -- so it goes to a worker
        thread, the way every other Android call from the GUI does.
        """
        offer = self.offer
        return await run.io_bound(
            deviceoffer.offer_to_tasker,
            offer.xml_bytes,
            offer.object_name,
            offer.confirm_names,
            offer.ip_address,
            offer.ip_port,
            wait_for_confirmation=False,
            route=offer.route,
            state=self.handlers.state,
        )

    def _where_the_file_is(self) -> str:
        """Where the file actually is, said in every message from here on.

        The staged file carries the object's own name (devicetask.staged_paths), and naming it is
        what makes a handoff Tasker does not complete recoverable: the user finishes the import
        out of Tasker's own browser, which they can only do if they know which file it is.  Same
        reason import_scene_into_tasker_event names its file -- that route is nothing but this
        case.
        """
        if self.offer.by_hand:
            return f"  {self.device_path} is on the device -- if Tasker is not in the chooser, {self.offer.by_hand}."
        return f"  {self.device_path} is on the device and can be imported by hand if it does not."

    def _report_unconfirmable(self, subject: str, waiting: str) -> None:
        """Say the import screen is open, and that whether it was confirmed cannot be seen from here."""
        # No timeout on this one, and nothing to take it down: it is the last thing this
        # will say, it asks the user to go and do something, and there is no outcome
        # coming that could replace it.  Its close button is how it goes.
        ui.notification(
            f"Tasker's import screen is open on {self.offer.ip_address}:{self.offer.ip_port} for {subject}.  "
            "Tasker already has what this would import and will offer to replace it -- confirm on the device.  "
            f"Whether that was confirmed cannot be seen from here.{waiting}",
            type="info",
            timeout=None,
            close_button=True,
            multi_line=True,
        )

    async def _report_outcome(self, subject: str, waiting: str) -> None:
        """Say the import screen is open, wait for Tasker to report what arrived, and report that."""
        offer = self.offer
        # ui.notification rather than ui.notify, for the handle: this one has no timeout
        # because there is no telling how long someone takes to reach their phone, and a
        # message with no timeout and nothing to dismiss it is a box that sits on screen for
        # the rest of the session.  It is a status line for a step in progress, so the
        # outcome below takes it down and replaces it.
        pending = ui.notification(
            f"Tasker's import screen is open on {offer.ip_address}:{offer.ip_port} -- tap Import on the device to finish."
            f"{waiting}",
            type="info",
            timeout=None,
            close_button=True,
            multi_line=True,
        )

        # Runs on with the dialogs gone; all it can do now is report.
        outcome = await run.io_bound(
            deviceverify.await_import,
            offer.ip_address,
            offer.ip_port,
            offer.confirm_names,
            subject,
            offer.route.confirm_endpoint,
            staged_at=self.device_path,
            attempts=offer.attempts or deviceverify.CONFIRM_POLL_ATTEMPTS,
        )
        # Guarded, because this notification is likely to be GONE by now and through no
        # fault of anyone's: it carries a close button, it sits there for up to two minutes
        # while someone walks to their phone, and a client that reloaded in the meantime
        # takes its elements with it.  Dismissing a deleted element makes nicegui log a
        # warning about a bug in the application code -- and the two-minute wait is exactly
        # the window in which the user is most likely to have tidied it away themselves.
        # Checked rather than suppressed: nicegui LOGS that warning instead of raising it,
        # so a suppress around the dismiss never saw it.  Only a deleted element warns -- a
        # deleted client is silently ignored by nicegui -- so is_deleted is the whole check.
        if not getattr(pending, "is_deleted", False):
            with suppress_logged("Dismissing the pending notice"):
                pending.dismiss()
        return_code, message = outcome
        # Not an error in the usual sense: most likely nobody has got to the phone yet, or
        # they declined.  Either way it is the DEVICE this reports on, not the edit here.
        with suppress_logged("Notifying of the device's reply"):
            ui.notify(message, type="positive" if return_code == 0 else "warning")


def report_offer_failure(task: asyncio.Task[None]) -> None:
    """Log whatever the spawned import offer raised, instead of losing it.

    Cancellation is ordinary -- a page that went away while the offer was in flight -- and
    says nothing.  Mirrors guiwins_nav.report_view_failure, which does this for a view's
    rendering task; the two exist separately only because neither module imports the other's
    private helpers.
    """
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("Offering an import to Tasker failed", exc_info=error)
