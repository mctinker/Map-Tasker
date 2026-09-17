"""Android event handlers: fetching a backup off the device, Save To Android and Import Into Tasker.

Split out of userintr.py, which had grown past 8,600 lines.  AndroidEventHandlers is a mixin:
MapTaskerEventHandlers inherits it, so every gui.event_handlers.<name> the window wires up
still finds its handler, and a handler here still reaches every other one through self --
_keep_task_in_loaded_config, _keep_profile_in_loaded_config and select_single_item_export
among them.

What these handlers ask the device through lives here as well: the check of what Tasker
already has, the Verify checkbox and the overwrite prompt's options.  A test that stands in
for one of those patches this module, not userintr.

Five helpers come from userintr_editors, because the Task, Profile, Scene and Project editors
share them with these handlers: _task_arg_values, _profile_condition_values,
_link_pending_task_pickers, _apply_scene_field_values and _unapplied_project_edits.  A test that
stands in for one of them patches this module's own name for it.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from nicegui import context, run, ui

from maptasker.src import deviceinv, presave, profedit, projedit, roundtrip, sceneedit, taskedit
from maptasker.src.getbakup import validate_xml_file
from maptasker.src.guiutils import (
    android_address_defaults,
    clear_android_buttons,
    notify_watch_android_device,
    ping_android_device,
    remember_android_address,
    remember_android_address_fields,
    update_tasker_object_menus,
)
from maptasker.src.guiwins import (
    build_helper_tasks_dialog,
    build_overwrite_confirm_dialog,
    build_round_trip_report_dialog,
    build_save_project_to_android_dialog,
    build_save_scene_to_android_dialog,
    build_save_to_android_dialog,
)
from maptasker.src.guiwins_profedit import build_save_profile_to_android_dialog
from maptasker.src.maputil2 import held_auth_key, http_request, read_android_file, translate_string
from maptasker.src.maputils import clear_tasker_data
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger
from maptasker.src.userintr_editors import (
    _apply_scene_field_values,
    _link_pending_task_pickers,
    _profile_condition_values,
    _task_arg_values,
    _unapplied_project_edits,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.userintr import MyGui


# What a prompt says after naming what Tasker already has, by how the objects would get there.
_API_IMPORT_CONSEQUENCE = "Tasker's import adds another Task of the same name beside it rather than replacing it."
_FILE_WRITE_CONSEQUENCE = "This only writes the file -- nothing in Tasker changes until it is imported."
_IMPORT_SCREEN_CONSEQUENCE = "Tasker's import screen will ask whether to replace them."


async def _what_tasker_already_has(
    ip_address: str,
    ip_port: str,
    render_xml: Callable[[], str | bytes],
    consequence: str,
    *,
    check_ids: bool = False,
) -> list[str]:
    """The lines a save's prompt adds for what Tasker already has -- [] when there is nothing to say.

    Called by all six device write paths (the five Save To Android handlers and
    _offer_into_tasker, which the three Import Into Tasker buttons share), right after their
    file-existence read, so one prompt answers every question.  The names come from the very
    document being sent -- see deviceinv.names_in_export -- rendered once more for the purpose;
    a render that raises leaves the save to report it.

    `consequence` is added only when something IS there, because it describes what happens to
    those objects; a check that merely could not run has nothing to say about them.

    check_ids is the panel's "Check IDs" box.  Ticked, the device makes a fresh backup and both
    questions are answered from it (deviceinv.check_against_device_backup) -- names included, so
    Projects need no helper of their own.  A backup that cannot be had is said so, and the names
    are then asked for the ordinary way, since that answer is still worth having.
    """
    try:
        xml = render_xml()
    except ValueError:
        return []
    sent = deviceinv.names_in_export(xml)
    if not any(sent.values()):
        return []

    check = None
    id_lines: list[str] = []
    if check_ids:
        ui.notify("Taking a fresh backup on the device to check IDs -- this can take a little while.", type="info")
        check, findings, problem = await run.io_bound(deviceinv.check_against_device_backup, ip_address, ip_port, xml)
        id_lines = [f"Could not check IDs: {problem}"] if problem else deviceinv.describe_id_findings(findings)

    if check is None:
        if sent.get("Project"):
            # Seconds rather than one request, and a MapTasker Task put on the phone the first time
            # -- worth saying before it happens rather than leaving the button looking stuck.
            ui.notify(
                "Checking which Projects, Profiles, Scenes and Tasks Tasker already has -- "
                "a small MapTasker Task runs on the device for this.",
                type="info",
            )
        check = await run.io_bound(deviceinv.check_tasker_for_existing, ip_address, ip_port, sent)

    name_lines = deviceinv.describe_tasker_check(check)
    if any(check.present.values()):
        name_lines.append(consequence)
    return [*name_lines, *id_lines]


def _check_ids_ticked(android_field_refs: dict) -> bool:
    """The Save To Android panel's "Check IDs" box -- see guiwins._android_device_fields."""
    checkbox = android_field_refs.get("check_ids")
    return bool(checkbox is not None and checkbox.value)


def _overwrite_prompt_options(exists: bool | None, tasker_lines: list[str]) -> dict:
    """build_overwrite_confirm_dialog's keyword arguments for a device write: the file's own
    answer, plus Tasker's lines only when there are some -- a prompt with none is the file
    prompt exactly as it always was.
    """
    options: dict = {"unknown": exists is None}
    if tasker_lines:
        options.update(file_absent=exists is False, tasker_lines=tasker_lines)
    return options


def _round_trip_verified(
    android_field_refs: dict,
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
        return_code, _ = await run.io_bound(
            http_request,
            android_ipaddr,
            android_port,
            android_file,
            "file",
            "?download=1",
        )

        # Validate the XML syntax structure
        if return_code == 0:
            PrimeItems.program_arguments["gui"] = True
            return_code, error_message = await run.io_bound(
                validate_xml_file,
                android_ipaddr,
                android_port,
                android_file,
            )
            if return_code != 0:
                self.display_message_box(error_message, "Red")
                return 1, android_ipaddr, android_port, android_file
        else:
            return 1, android_ipaddr, android_port, android_file

    # 2. File location not provided or "List Files" requested.
    # Fetch the directory catalog and present a NiceGUI ui.select component.
    else:
        clear_android_buttons(self)

        ui.notify(
            translate_string("Listing the XML files on the Android device..."),
            type="info",
            timeout=1500,
        )
        return_code, filelist = await run.io_bound(
            deviceinv.get_list_of_files,
            android_ipaddr,
            android_port,
            deviceinv.FILE_LIST_DIRECTORY,
        )
        if return_code != 0:
            self.display_message_box(filelist, "Red")
            return 1, android_ipaddr, android_port, android_file

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
                on_change=lambda e: self.event_handlers.file_selected_event(e.value),
            ).classes("w-full q-mt-none")

            # Flat modern action button to easily close the selection panel
            ui.button(
                translate_string("Cancel Entry"),
                on_click=lambda: (self.android_container.clear(), self.android_container.classes(add="hidden")),
            ).classes("text-xs w-full mt-2").props("outline color=negative dense")

        # Save connection details to state
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port

        # Return status code 2 to indicate layout suspension until user selects a file item.
        return (2, "", "", "")

    # All checks passed successfully
    return 0, android_ipaddr, android_port, android_file


class AndroidEventHandlers:
    """The Android handlers MapTaskerEventHandlers inherits: self.gui is the window, and every other
    handler is reached through self, just as it was before these moved here."""

    # ==========================================
    # ANDROID XML BACKUP EVENT HANDLERS
    # ==========================================
    def get_xml_from_android_event(self) -> None:
        """
        Gets Android details from user inside the reactive right drawer container slot.
        Replaces legacy manual CustomTkinter pixel coordinates with automated fluid Flexbox grids.
        """
        gui = self.gui

        # 1. Clear out old entries and unhide the sidebar container panel slot
        gui.android_container.clear()
        gui.android_container.classes(remove="hidden")

        # 2. Extract Fallback Default Values
        android_ipaddr, android_port = android_address_defaults(gui)

        if gui.android_file == "" or gui.android_file is None:
            android_file = "/Tasker/configs/user/backup.xml".replace("/", PrimeItems.slash)
        else:
            android_file = gui.android_file.replace("/", PrimeItems.slash)

        # 3. Mount text input fields and control action items into the view hierarchy
        with gui.android_container:
            ui.label(translate_string("Configure Android Connection:")).classes(
                "text-sm font-bold text-blue-500 mb-1 self-start",
            )

            # Form Fields
            gui.ip_entry = ui.input(label=translate_string("1-TCP/IP Address:"), value=android_ipaddr).classes(
                "w-full q-py-none",
            )
            gui.port_entry = ui.input(label=translate_string("2-Port Number:"), value=android_port).classes(
                "w-full q-py-none",
            )
            remember_android_address_fields(gui, gui.ip_entry, gui.port_entry)
            gui.file_entry = ui.input(label=translate_string("3-File Location:"), value=android_file).classes(
                "w-full q-py-none",
            )

            # Inline Button Row 1 (List XML & Query Help Button)
            with ui.row().classes("w-full items-center justify-between gap-1 mt-2"):
                gui.list_files_button = (
                    ui.button(translate_string("List XML Files"), on_click=gui.event_handlers.list_files_event)
                    .style("background-color: #D62CFF; color: white;")
                    .classes("flex-grow text-xs")
                )

                gui.list_files_query_button = (
                    ui.button("?", on_click=lambda: gui.event_handlers.query_event("listfile"))
                    .style("background-color: #246FB6; color: #ffd941;")
                    .classes("w-10 min-w-[40px] text-xs")
                )

            # Housekeeping, and it lives here because this is where the device's address
            # already is -- see list_helper_tasks_event for what accumulates and why nothing
            # can delete it from this end.
            with ui.row().classes("w-full items-center mt-1"):
                gui.helper_tasks_button = (
                    ui.button(
                        translate_string("List Helper Tasks"),
                        on_click=gui.event_handlers.list_helper_tasks_event,
                    )
                    .props("flat dense color=primary")
                    .classes("flex-grow text-xs")
                )
                with gui.helper_tasks_button:
                    ui.tooltip(
                        translate_string(
                            "Lists the 'MapTasker ...' Tasks this program has installed on the Android "
                            "device, and says which are left over from an earlier version.\n\n"
                            "Each one is installed under a versioned name and never replaced -- Tasker's "
                            "import adds a second Task rather than replacing the first -- so old ones stay "
                            "behind in your Task list.  They do no harm; they are clutter.\n\n"
                            "Delete the ones it names from Tasker's own Tasks tab.  Nothing here can do it "
                            "for you: Tasker's HTTP API has no way to delete a Task.",
                        ),
                    ).style("white-space: pre-wrap")

            # Inline Button Row 2 (.or. Separator and Cancel Action)
            with ui.row().classes("w-full items-center justify-center gap-2 mt-1"):
                gui.label_or = ui.label(translate_string(".or.")).classes("text-xs text-gray-400 italic")

                # Close button clears the contents and re-hides the panel drawer clean
                ui.button(
                    translate_string("Cancel Entry"),
                    on_click=lambda: (
                        gui.android_container.clear(),
                        gui.android_container.classes(add="hidden"),
                    ),
                ).classes("text-xs").props("flat color=negative dense")

            # Master Set XML Backup execution button.
            #
            # Deliberately NOT self.get_backup_button: that name belongs to the "Get XML from
            # Android Device" button in the drawer above (see
            # _create_file_and_message_buttons_section in guiwins.py), which stays on screen the
            # whole time this panel is open. Reusing the name here overwrote the reference to it,
            # so clear_android_buttons() then deleted this button while believing it had deleted
            # that one -- leaving the original in place and adding a second one every time.
            gui.set_xml_details_button = (
                ui.button(
                    translate_string("Click Here to Set XML Details"),
                    on_click=gui.event_handlers.fetch_backup_event,
                )
                .style("background-color: #D62CFF; color: white;")
                .classes("w-full mt-3 font-bold text-xs py-2")
            )

    async def list_files_event(self) -> None:
        """
        List (Android) XML files event updated for NiceGUI.
        Alters the active view tracking text instead of legacy .configure() properties.
        """
        the_view = self.gui  # self maps to MapTaskerEventHandlers, use self.gui to target MyGui

        the_view.list_files = True

        # NiceGUI uses direct text assignment to change the displayed button label
        if hasattr(the_view, "list_files_button") and the_view.list_files_button:
            the_view.list_files_button.set_text(translate_string("List Files Selected"))

        # Trigger the fetch execution routing
        if hasattr(the_view.event_handlers, "fetch_backup_event"):
            # --- CRITICAL FIX: Added 'await' here ---
            await the_view.event_handlers.fetch_backup_event()

    async def list_helper_tasks_event(self) -> None:
        """Report which of this program's own helper Tasks on the device are dead.

        Every helper is installed under a versioned name and never replaced -- Tasker's
        api/import adds rather than replaces, so deviceinv._install_task_on_android installs
        only what is not already there -- which means each release leaves the previous
        generation behind in the user's own Task list.  Nothing breaks; it accumulates.

        A REPORT AND NOT A CLEANUP, because a cleanup is not available: the Tasker HTTP
        Server Example has no route for deleting a Task (GET to list, POST to run, and a
        DELETE that only removes files from storage), and no Tasker action deletes a Tasker
        object.  Naming them exactly is the whole of what can be done from here, and it is
        most of the value -- the alternative is the user guessing which 'MapTasker ...' in a
        list of several hundred Tasks is safe to remove.

        Reads the connection details out of the Get XML panel's own fields, since that is
        where they already are and this is a question about that same device.
        """
        ip_address = self.gui.ip_entry.value if hasattr(self.gui, "ip_entry") and self.gui.ip_entry else ""
        ip_port = self.gui.port_entry.value if hasattr(self.gui, "port_entry") and self.gui.port_entry else ""
        ip_address, ip_port = ip_address.strip(), ip_port.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Blocking -- a key fetch and a GET -- so it goes to a worker thread like every other
        # Android call from the GUI.
        return_code, message, stale, current = await run.io_bound(
            deviceinv.stale_helper_tasks_on_device,
            ip_address,
            ip_port,
        )
        if return_code != 0:
            ui.notify(f"Could not read the device's Task list: {message}", type="negative")
            return

        # Remembered the same way every other successful Android call here remembers it.
        self.gui.android_ipaddr = ip_address
        self.gui.android_port = ip_port

        build_helper_tasks_dialog(stale, current, f"{ip_address}:{ip_port}")

    def open_save_to_android_dialog_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        parent_dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Opens the IP/port prompt for importing this Task into Tasker on the Android device."""
        build_save_to_android_dialog(self.gui, edited_task, field_refs, parent_dialog, on_created)

    async def save_task_to_android_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Validates and applies the parent dialog's field values (same as a local
        Save), pings the Android device to confirm it's reachable (same check
        fetch_backup_event uses), and then imports the edited Task into Tasker on
        the device. The android prompt dialog stays open on any error so the
        user's connection details aren't lost; on success both it and the parent
        Edit/Add Task dialog are closed.

        The IMPORT half of the Save Task To Android dialog; save_task_to_android_file_event
        is the file half, and _apply_task_for_android is the validation both share.  A Task
        is the only kind whose import needs no tap on the device -- api/import is documented
        Task-only, and everything else has to go through Tasker's own import screen.

        on_created, if given, is called with the new Task's id once it's
        registered -- see build_add_task_dialog's on_task_created.
        """
        ok, is_new_task = self._apply_task_for_android(edited_task, field_refs)
        if not ok:
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_task(edited_task)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        task_name = field_refs["name"].value.strip()

        async def _import() -> None:
            # Every request to the device below blocks for seconds, so each one goes to a
            # worker thread; the notifications and the dialogs stay here, on the event loop.
            #
            # The import writes /Tasker/tasks/<name>.tsk.xml and imports THAT, so it
            # clobbers whatever is at that path exactly as 'Save As File' does -- and gets
            # the same safety copy of it, from the same single read of the path.  A copy that
            # fails is reported and the import goes ahead; see presave's module comment for
            # why it must never block one.
            copied, safety_copy = presave.save_android_safety_copy(device_path, already_there)
            if not copied:
                ui.notify(
                    f"Could not copy the file already on the device first: {safety_copy}",
                    type="warning",
                )

            # The key is the one held for this device this session, so a device already asked --
            # by an earlier save, a fetch or an import -- is not prompted again.
            return_code, result = await run.io_bound(
                taskedit.save_task_to_android,
                edited_task,
                ip_address,
                ip_port,
                task_name,
            )
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            self._keep_task_in_loaded_config(edited_task, task_name, is_new_task, on_created)

            # `copied and` matters: on a failure safety_copy holds the reason, not a path.
            replaced = f" The file it replaced was copied to {safety_copy}." if copied and safety_copy else ""
            landed = f" A copy was left on the device at {device_path}.{replaced}"

            # The key the import used -- a fresh one, if the device had rejected the one held.
            # Read, not asked for.
            auth_key = held_auth_key(ip_address, ip_port)

            # api/import's 200 response doesn't guarantee Tasker actually committed the
            # Task, so confirm it is there before declaring success -- by GET /api/tasks, or
            # for a name that cannot find ('$Taskaroo') the object-list helper, since a Task
            # wrongly reported missing would be imported twice.  If that check fails, retry
            # the import once more from the file now sitting in /Tasker/tasks (see
            # taskedit.save_task_to_android_directory's docstring for why a retry, not a
            # different endpoint, is the only fallback that can help).
            if await run.io_bound(deviceinv.confirm_task_on_android, ip_address, ip_port, task_name, auth_key):
                ui.notify(translate_string("Task Uploaded to Tasker") + landed, type="positive")
            else:
                fallback_code, fallback_result = await run.io_bound(
                    taskedit.save_task_to_android_directory,
                    edited_task,
                    ip_address,
                    ip_port,
                    task_name,
                    auth_key,
                )
                if fallback_code == 0:
                    ui.notify(translate_string("Task Uploaded to Tasker.") + landed, type="positive")
                else:
                    # Both api/import attempts are spent, and the .tsk.xml is in /Tasker/tasks
                    # either way -- written and read back before either of them ran.  So the
                    # user gets the same "Open with..." chooser the other three kinds get,
                    # rather than only being told it did not work: Tasker's own import screen
                    # is one tap out of it, on a file that is already there.  This is the
                    # LAST resort, not the route -- api/import needs no tap at all when it
                    # works, which for a Task it usually does.
                    offer_code, offer_result = await run.io_bound(
                        deviceinv.offer_to_tasker,
                        taskedit.render_standalone_task_xml(edited_task).encode("utf-8"),
                        task_name,
                        [task_name],
                        ip_address,
                        ip_port,
                        wait_for_confirmation=False,
                        route=deviceinv.OPEN_TASK_ROUTE,
                    )
                    if offer_code == 0:
                        ui.notify(
                            f"Tasker did not report the Task ({fallback_result}), so it was handed to "
                            f"Android's 'Open with' instead -- pick Tasker to import it.{landed}",
                            type="warning",
                            multi_line=True,
                        )
                    else:
                        ui.notify(
                            f"Unable to upload Task to Tasker: {fallback_result}",
                            type="negative",
                        )

            android_dialog.close()
            parent_dialog.close()

        # Asked here rather than inside taskedit, because it is the same question the file
        # button asks and the user should be asked it once, in one wording, whichever button
        # they pressed -- see save_task_to_android_file_event's identical check, including
        # why the content comes back with the answer.
        device_path = taskedit.android_task_path(task_name)
        exists, already_there = await run.io_bound(read_android_file, ip_address, ip_port, device_path)
        tasker_lines = await _what_tasker_already_has(
            ip_address,
            ip_port,
            lambda: taskedit.render_standalone_task_xml(edited_task),
            _API_IMPORT_CONSEQUENCE,
            check_ids=_check_ids_ticked(android_field_refs),
        )
        if exists is not False or tasker_lines:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _import,
                **_overwrite_prompt_options(exists, tasker_lines),
            )
            return
        await _import()

    def _apply_task_for_android(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
    ) -> tuple[bool, bool]:
        """Validate and apply the parent dialog's fields, the same way a local Save does.

        Returns (ok, is_new_task); ok is False once the errors have already been shown, so
        the caller only has to return.

        Shared by both of the Save Task To Android dialog's buttons, for the reason
        _apply_profile_for_android is shared by the Profile dialog's: they do genuinely
        different things to the device and nothing at all differently to the Task, and a
        second copy would drift into one button validating what the other does not.
        """
        # A brand-new Task (Add Task) was never registered onto the live tree in the first
        # place -- computed before anything below can change task_id, so it stays accurate
        # for the registration step the callers end with.
        is_new_task = edited_task.task_id not in PrimeItems.tasker_root_elements.get("all_tasks", {})

        errors = taskedit.apply_edits_to_task(
            edited_task,
            field_refs["name"].value,
            field_refs["priority"].value,
            _task_arg_values(field_refs),
        )
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return False, False

        if is_new_task and taskedit.task_name_exists(field_refs["name"].value.strip()):
            ui.notify(
                f"A Task named '{field_refs['name'].value.strip()}' already exists in this backup. "
                "Choose a different name.",
                type="negative",
            )
            return False, False

        return True, is_new_task

    async def save_task_to_android_file_event(
        self,
        edited_task: taskedit.EditableTask,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
        on_created: Callable[[str], None] | None = None,
    ) -> None:
        """Write the edited Task onto the device's storage under /Tasker/tasks, as a
        standalone .tsk.xml file.  The Task counterpart of save_profile_to_android_event, and
        the same thing it does for a Profile: a FILE WRITE, not a live import -- unlike this
        dialog's other button, which posts to api/import and puts the Task straight into
        Tasker (see save_task_to_android_event).

        /upload carries no Authorization header, so there is no cached-key handling here the
        way the import path has.  That is the API key only: Tasker still puts its own
        connection-authorization prompt on the device, several times over one save, which is
        what notify_watch_android_device warns about.

        The android prompt dialog stays open on any error, so the user's connection details
        are not lost; on success both it and the parent Edit/Add Task dialog close.
        """
        ok, is_new_task = self._apply_task_for_android(edited_task, field_refs)
        if not ok:
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_task(edited_task)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        task_name = field_refs["name"].value.strip()

        async def _upload() -> None:
            # Keep whatever is already at that path before /upload writes over it -- the
            # device keeps no versions and has no undo, so this is the only copy of it there
            # will ever be.  The bytes come from the existence check above rather than from a
            # second GET: the Tasker HTTP Server Example flashes 'File doesn't exist' on the
            # phone for every miss, so asking twice put two of them on screen for one save.
            # A copy that fails is reported and the save goes ahead -- presave's module
            # comment says why it must never block one.
            copied, safety_copy = presave.save_android_safety_copy(device_path, already_there)
            if not copied:
                ui.notify(
                    f"Could not copy the file already on the device first: {safety_copy}",
                    type="warning",
                )
            # Uploads and reads back, which takes seconds: a worker thread, not the event loop.
            return_code, result = await run.io_bound(
                taskedit.save_task_to_android_file,
                edited_task,
                ip_address,
                ip_port,
                task_name,
            )
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            self._keep_task_in_loaded_config(edited_task, task_name, is_new_task, on_created)

            # `copied and` matters: on a failure safety_copy holds the reason, not a path.
            saved_note = f" The file it replaced was copied to {safety_copy}." if copied and safety_copy else ""
            ui.notify(f"Task saved to Android device at {result}.{saved_note}", type="positive")
            android_dialog.close()
            parent_dialog.close()

        # ONE read of the path, answering both questions the write needs answered: whether
        # anything is there to clobber, and what it holds so it can be kept.  See
        # maputil2.read_android_file for why two reads was worse than one on the device as
        # well as here.  /upload clobbers silently, which is why this is asked at all.
        device_path = taskedit.android_task_path(task_name)
        exists, already_there = await run.io_bound(read_android_file, ip_address, ip_port, device_path)
        tasker_lines = await _what_tasker_already_has(
            ip_address,
            ip_port,
            lambda: taskedit.render_standalone_task_xml(edited_task),
            _FILE_WRITE_CONSEQUENCE,
            check_ids=_check_ids_ticked(android_field_refs),
        )
        if exists is not False or tasker_lines:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _upload,
                **_overwrite_prompt_options(exists, tasker_lines),
            )
            return
        await _upload()

    def open_save_scene_to_android_dialog_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        parent_dialog: ui.dialog,
    ) -> None:
        """Opens the Save Scene To Android prompt, nested inside Edit Scene -- see
        build_save_scene_to_android_dialog.  The Edit Scene dialog's field_refs go
        with it so the upload can apply the edits sitting in them first.
        """
        build_save_scene_to_android_dialog(self.gui, edited_scene, field_refs, parent_dialog)

    async def save_scene_to_android_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Applies the Edit Scene dialog's edits, pings the Android device to confirm
        it's reachable, then writes the Scene onto the device's storage under
        /Tasker/scenes (see sceneedit.save_scene_to_android).

        THE APPLY IS WHAT MAKES THE UPLOAD CARRY THE USER'S WORK.  The upload renders
        the Scene from the live tree (sceneedit.render_standalone_scene_xml takes a
        name, not the dialog's copy), and the dialog edits a deep copy whose V2 layout
        lives in a dict that nothing writes back until a save handler runs.  Without
        this, an element added a moment ago is simply absent from the file that lands
        on the device, with nothing to say so.

        Applying first also means a validation failure stops the upload before the
        device is contacted, rather than after.  Edits stay applied in memory if the
        upload then fails, which is the same state clicking "Ok" first would leave --
        and clicking "Ok" first is exactly what this saves the user from having to do.
        """
        errors = _apply_scene_field_values(edited_scene, field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        sceneedit.apply_edited_scene_to_live_tree(edited_scene.scene_name, edited_scene)

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_scene(edited_scene.scene_name)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        async def _upload() -> None:
            # Keep whatever is already at that path before /upload writes over it.  The
            # device keeps no versions and has no undo, so this is the only copy of it there
            # will ever be; it is kept here rather than left beside the original -- see
            # presave.save_android_safety_copy.  The bytes come from the existence check
            # below rather than from a second GET, because the Tasker HTTP Server Example
            # flashes 'File doesn't exist' on the phone for every miss (its /file handler
            # runs Test File first -- see its file-system Profile), so asking twice put two
            # of them on screen for one save.  A copy that fails is reported and the save
            # goes ahead: presave's module comment says why it must never block one.
            copied, safety_copy = presave.save_android_safety_copy(device_path, already_there)
            if not copied:
                ui.notify(
                    f"Could not copy the file already on the device first: {safety_copy}",
                    type="warning",
                )
            # Uploads and reads back, which takes seconds: a worker thread, not the event loop.
            return_code, result = await run.io_bound(
                sceneedit.save_scene_to_android,
                edited_scene.scene_name,
                ip_address,
                ip_port,
            )
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            # `copied and` matters: on a failure safety_copy holds the reason, not a path.
            saved_note = f" The file it replaced was copied to {safety_copy}." if copied and safety_copy else ""
            ui.notify(f"Scene saved to Android device at {result}.{saved_note}", type="positive")
            android_dialog.close()
            parent_dialog.close()

        # /upload overwrites silently and answers 200 either way, so the only way to know is
        # to read the destination back first -- one read, which answers both what is there
        # and what it holds, so the safety copy above needs no second GET of its own (see
        # maputil2.read_android_file).  None = couldn't tell, which still prompts rather than
        # risking a silent clobber.
        device_path = sceneedit.android_scene_path(edited_scene.scene_name)
        exists, already_there = await run.io_bound(read_android_file, ip_address, ip_port, device_path)
        tasker_lines = await _what_tasker_already_has(
            ip_address,
            ip_port,
            lambda: sceneedit.render_standalone_scene_xml(edited_scene.scene_name),
            _FILE_WRITE_CONSEQUENCE,
            check_ids=_check_ids_ticked(android_field_refs),
        )
        if exists is not False or tasker_lines:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _upload,
                **_overwrite_prompt_options(exists, tasker_lines),
            )
            return
        await _upload()

    def open_save_profile_to_android_dialog_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        parent_dialog: ui.dialog,
    ) -> None:
        """Opens the IP/port prompt for importing this Profile into Tasker on the Android device."""
        build_save_profile_to_android_dialog(self.gui, edited_profile, field_refs, parent_dialog)

    async def save_profile_to_android_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Validates and applies the parent dialog's field values (same as a local
        Save -- see _apply_profile_for_android, shared with this dialog's other
        button), pings the Android device to confirm it's reachable, and then writes
        the edited Profile onto the device's storage under /Tasker/profiles (see
        profedit.save_profile_to_android -- this is a file write, not a live import
        into Tasker, unlike save_task_to_android_event's api/import; /upload needs
        no auth key, so there's no cached-key handling here the way that one has).
        A Profile also needs registering into the live tree (see the is_new_profile
        branch below) -- Tasks don't need the Project-attachment step a Profile does.
        """
        ok, is_new_profile, project_name = self._apply_profile_for_android(edited_profile, field_refs)
        if not ok:
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_profile(edited_profile)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        profile_name = field_refs["name"].value.strip()

        async def _upload() -> None:
            # Keep whatever is already at that path before /upload writes over it.  The
            # device keeps no versions and has no undo, so this is the only copy of it there
            # will ever be; it is kept here rather than left beside the original -- see
            # presave.save_android_safety_copy.  The bytes come from the existence check
            # below rather than from a second GET, because the Tasker HTTP Server Example
            # flashes 'File doesn't exist' on the phone for every miss (its /file handler
            # runs Test File first -- see its file-system Profile), so asking twice put two
            # of them on screen for one save.  A copy that fails is reported and the save
            # goes ahead: presave's module comment says why it must never block one.
            copied, safety_copy = presave.save_android_safety_copy(device_path, already_there)
            if not copied:
                ui.notify(
                    f"Could not copy the file already on the device first: {safety_copy}",
                    type="warning",
                )
            # Uploads and reads back, which takes seconds: a worker thread, not the event loop.
            return_code, result = await run.io_bound(
                profedit.save_profile_to_android,
                edited_profile,
                ip_address,
                ip_port,
                profile_name,
            )
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            self._keep_profile_in_loaded_config(edited_profile, profile_name, is_new_profile, project_name)

            # `copied and` matters: on a failure safety_copy holds the reason, not a path.
            saved_note = f" The file it replaced was copied to {safety_copy}." if copied and safety_copy else ""
            ui.notify(f"Profile saved to Android device at {result}.{saved_note}", type="positive")
            android_dialog.close()
            parent_dialog.close()

        # See save_project_to_android_event's identical check -- /upload clobbers silently,
        # and one read answers both of the questions the write needs answered.
        device_path = profedit.android_profile_path(profile_name)
        exists, already_there = await run.io_bound(read_android_file, ip_address, ip_port, device_path)
        tasker_lines = await _what_tasker_already_has(
            ip_address,
            ip_port,
            lambda: profedit.render_standalone_profile_xml(edited_profile),
            _FILE_WRITE_CONSEQUENCE,
            check_ids=_check_ids_ticked(android_field_refs),
        )
        if exists is not False or tasker_lines:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _upload,
                **_overwrite_prompt_options(exists, tasker_lines),
            )
            return
        await _upload()

    def _apply_profile_for_android(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
    ) -> tuple[bool, bool, str]:
        """Validate and apply the parent dialog's fields, the same way a local Save does.

        Returns (ok, is_new_profile, project_name); ok is False once the errors have already
        been shown, so the caller only has to return.

        Shared by both of the Save Profile To Android dialog's buttons.  They do genuinely
        different things to the device and nothing at all differently to the Profile, so
        this had to be one implementation -- a second copy would drift, and the way it would
        drift is one button validating something the other does not.
        """
        _link_pending_task_pickers(edited_profile, field_refs)
        condition_values = _profile_condition_values(field_refs)

        errors = profedit.apply_edits_to_profile(edited_profile, field_refs["name"].value, condition_values)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return False, False, ""

        # Add Profile's dialog (unlike Edit Profile's) has a "target_project_name"
        # entry -- its presence is how these shared handlers tell a brand-new,
        # not-yet-registered Profile apart from one already in the backup, without
        # threading an extra parameter through every caller.
        is_new_profile = "target_project_name" in field_refs
        project_name = field_refs.get("target_project_name", "") if is_new_profile else ""
        if is_new_profile:
            new_profile_errors = []
            if profedit.profile_name_exists(field_refs["name"].value.strip()):
                new_profile_errors.append(
                    f"A Profile named '{field_refs['name'].value.strip()}' already exists in this backup. "
                    "Choose a different name.",
                )
            if not project_name:
                new_profile_errors.append(
                    "Choose a Project first -- a Profile has to belong to one to show up anywhere in the app.",
                )
            new_profile_errors.extend(profedit.validate_new_profile_requirements(edited_profile))
            if new_profile_errors:
                for error in new_profile_errors:
                    ui.notify(error, type="negative")
                return False, False, ""

        return True, is_new_profile, project_name

    async def import_profile_into_tasker_event(
        self,
        edited_profile: profedit.EditableProfile,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Put the edited Profile in front of Tasker's own import screen on the device.

        The other button in this dialog (save_profile_to_android_event) writes a file to
        /Tasker/profiles that Tasker never reads.  This stages the same XML and has a helper
        Task hand it to Tasker, which brings up Tasker's ordinary import screen -- see
        deviceinv.open_profile_on_device.

        "OPEN WITH...", WHICH IS THE POINT, and that changed back on 2026-08-30.

        The history is worth keeping, because it is what makes the current answer the right
        one rather than a third guess.  OPEN_FILE_ROUTE fires an implicit ACTION_VIEW and
        lets Android find the handler; it was measured working on 2026-08-27 and FAILING the
        next day on the same device -- a chooser of seven apps with Tasker not among them.
        So it was swapped for SEND_INTENT_ROUTE, which names Tasker's package and class
        outright and is delivered with no filter matching at all.  That reaches Tasker (it is
        how a Scene got Tasker to open) but it has to carry a file:// URI, which Android 7
        and later rejects in an outgoing intent -- so on this device neither route imported
        anything, for two entirely different reasons.

        What neither attempt tried is the thing a file manager actually does: an implicit
        VIEW with NO MIME TYPE.  The failing chooser was a chooser of text/xml apps because
        the intent asked for text/xml, and an app that claims '.prf.xml' declares a
        pathPattern and no mimeType -- which Android matches only against intents carrying no
        type.  See deviceinv._OPEN_WITH_MIME_TYPE, which sets out that reasoning and is
        honest that it is reasoning and not a measurement.

        So this is OPEN_FILE_ROUTE again, but not the same route: the user gets Android's
        "Open with..." chooser and picks Tasker themselves, rather than this program
        guessing what the file will resolve to and being wrong silently.  If Tasker is still
        not in that chooser, the file is in /Tasker/profiles under the Profile's own name and
        the message says so -- see the `waiting` line in _offer_into_tasker.

        TWO PHASES, BECAUSE THERE IS A PERSON IN THE MIDDLE

        Opening the screen and importing are not the same event, and 'Open File' returns
        without waiting for the decision.  So this reports the screen being up as soon as it
        is up -- rather than leaving the user watching a spinner while their phone waits for
        them -- and then waits separately for Tasker to actually report the Profile.

        Both dialogs close as soon as the device answers -- once the import screen is up on
        the phone there is nothing left here to do, and a panel that outlives the response
        is a panel the user has to dismiss for no reason.  The confirmation runs on after
        them and reports what the device did.

        The edit is kept in the loaded configuration at that same moment, not held back
        until the confirmation lands.  With the dialogs gone there is no retry surface left,
        so discarding it on a poll that timed out -- and the poll times out for reasons that
        say nothing about the edit, a phone still in a pocket above all -- would be silent
        data loss rather than caution.

        A PROFILE TASKER ALREADY HAS CANNOT BE CONFIRMED AT ALL

        The confirmation is 'does Tasker report a Profile of this name', and for a Profile
        that was already there that is true before the user touches anything -- so waiting
        for it would report success the moment it was asked, Cancel included.  There is no
        second signal to use: Tasker offers to REPLACE in that case (which is why nothing
        refuses a duplicate any more), and a replacement leaves the name, the count and the
        enabled state exactly as they were.

        So that case is not waited on.  It is reported for what it is -- the screen is open,
        Tasker will ask about replacing, MapTasker cannot see the answer -- and the edit is
        kept in the loaded configuration, because the alternative is throwing away the
        user's own edit over a device answer that is never coming.

        THE OVERWRITE IS ASKED ABOUT AND COPIED, and both changed on 2026-08-30.  Neither
        used to be, because what an import overwrote was MapTasker's own
        'maptasker_import.prf.xml' -- a scratch file with nothing of the user's in it and
        nothing to ask about.  The staged file now carries the Profile's own name, which is
        to say it is written to exactly the path 'Save As File' writes, so an import of
        'Morning' lands on a Morning.prf.xml they may have saved by hand.  So it is now the
        same question that button asks, asked in the same words, and answered before anything
        is sent -- see _offer_into_tasker, which does the asking for this and for a Project.
        (import_scene_into_tasker_event asks its own, having always written under the Scene's
        own name and so always having had this exposure.)
        """
        ok, is_new_profile, project_name = self._apply_profile_for_android(edited_profile, field_refs)
        if not ok:
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_profile(edited_profile)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        profile_name = field_refs["name"].value.strip()
        profile_xml = profedit.render_standalone_profile_xml(edited_profile).encode("utf-8")

        await self._offer_into_tasker(
            profile_xml,
            profile_name,
            # A Profile is confirmed by its own name -- the list of one the general case
            # collapses to.  A Project's list is every Profile it owns; see
            # deviceinv.offer_to_tasker.
            [profile_name],
            deviceinv.OPEN_FILE_ROUTE,
            ip_address,
            ip_port,
            android_dialog,
            parent_dialog,
            lambda: self._keep_profile_in_loaded_config(edited_profile, profile_name, is_new_profile, project_name),
            check_ids=_check_ids_ticked(android_field_refs),
        )

    async def _offer_into_tasker(
        self,
        xml_bytes: bytes,
        object_name: str,
        confirm_names: list[str],
        route: deviceinv.OfferRoute,
        ip_address: str,
        ip_port: str,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
        keep_edit: Callable[[], None],
        by_hand: str = "",
        attempts: int = 0,
        check_ids: bool = False,
    ) -> None:
        """Offer a Profile, a Project or a Scene to Android's "Open with..." chooser, and
        report what happened.

        check_ids is the panel's "Check IDs" box, passed on to _what_tasker_already_has.

        by_hand is what the user does if Tasker is not in that chooser, in their own terms
        ("import it with Tasker's 'Scenes > Import One Scene'").  Every kind has such a step
        -- the file is in Tasker's own folder under its own name precisely so that it does --
        but only a Scene has one worth spelling out, since its import is several menus deep.

        attempts is how long to keep asking whether the import arrived; 0 leaves
        deviceinv.await_import's own default, which suits an import screen already in front
        of the user.  A Scene passes a longer one: its user has a file picker to work
        through.

        Everything the three Import Into Tasker buttons do once their own validation is past,
        in one place: they differ in what they render, what confirms it and what they have to
        keep afterwards, and in nothing else.  keep_edit is that last part -- registering an
        edited Profile into the loaded configuration, and nothing at all for a Project or a
        Scene, both of which are exported from the live tree by name (a Scene's edits are
        already in it by the time this runs) and so have nothing left to register.

        confirm_names is asked about at the route's own endpoint: /api/scenes for a Scene,
        /api/profiles for a Profile and -- since there is no /api/projects -- for the
        Profiles a Project brings with it.

        TWO PHASES, BECAUSE THERE IS A PERSON IN THE MIDDLE

        Opening the screen and importing are not the same event, and the helper Task returns
        without waiting for the decision.  So this reports the screen being up as soon as it
        is up -- rather than leaving the user watching a spinner while their phone waits for
        them -- and then waits separately for Tasker to report what arrived.

        Both dialogs close as soon as the device answers.  Once the import screen is up on
        the phone there is nothing left here to do, and a panel that outlives the response is
        a panel the user has to dismiss for no reason.

        The edit is kept at that same moment, not held back until the confirmation lands:
        with the dialogs gone there is no retry surface left, so discarding it on a poll that
        timed out -- and the poll times out for reasons that say nothing about the edit, a
        phone still in a pocket above all -- would be silent data loss rather than caution.

        SOME IMPORTS CANNOT BE CONFIRMED AT ALL

        The confirmation is 'does Tasker report these Profiles', and for ones it already has
        that is true before the user touches anything: Tasker offers to REPLACE in that case,
        and a replacement leaves the name, the count and the enabled state exactly as they
        were.  A Project owning only unnamed Profiles has nothing askable at all (see
        projedit.project_profile_names).  Those are reported for what they are rather than
        waited on -- see deviceinv.import_is_confirmable.
        """
        # ONE READ, TWO ANSWERS: whether anything is already at the path this is about to
        # write, and a copy of it for the safety copy below.  Asking twice is worse than it
        # sounds -- the Tasker HTTP Server Example's /file handler runs 'Test File' and
        # flashes 'File doesn't exist' on the phone for every miss, so a second GET puts a
        # second flash on screen for one import (see maputil2.read_android_file).
        #
        # Worth asking at all only because the staged file is the object's own now: it is
        # written to exactly the path 'Save As File' writes to, so an import of 'Morning'
        # lands on a Morning.prf.xml the user may have saved by hand.  It used to be
        # MapTasker's own 'maptasker_import.prf.xml', a scratch file with nothing of theirs
        # in it and nothing to ask about.  So this is now the same question the file button
        # asks, and they are asked it in the same words whichever button they pressed -- see
        # save_profile_to_android_event's identical check.
        _filename, device_read_path, device_path = route.staged_file_paths(object_name)
        exists, already_there = await run.io_bound(read_android_file, ip_address, ip_port, device_read_path)

        async def _offer() -> None:
            """Everything the offer does once the overwrite question has been answered."""
            # Keep whatever is already at that path before /upload writes over it.  The
            # device keeps no versions and has no undo, so this is the only copy of it there
            # will ever be, and it is kept on this computer rather than beside the original
            # -- see presave.save_android_safety_copy.  The bytes come from the check above
            # rather than from a second GET, for the reason given there.  A copy that fails
            # is reported and the import goes ahead: presave's module comment says why it
            # must never block one.
            copied, safety_copy = presave.save_android_safety_copy(device_read_path, already_there)
            if not copied:
                ui.notify(
                    f"Could not copy the file already on the device first: {safety_copy}",
                    type="warning",
                )

            # Asked before the offer, not after, because after the import the answer means
            # nothing.  None ('could not ask') is treated the same as False: neither can be
            # confirmed, and guessing the other way would turn an unconfirmable import into a
            # reported success.
            confirmable = await run.io_bound(
                deviceinv.import_is_confirmable,
                ip_address,
                ip_port,
                confirm_names,
                route.confirm_endpoint,
            )

            # Blocking -- it installs a Task, uploads, runs and polls -- so it goes to a worker
            # thread, the way every other Android call from the GUI does.
            return_code, message = await run.io_bound(
                deviceinv.offer_to_tasker,
                xml_bytes,
                object_name,
                confirm_names,
                ip_address,
                ip_port,
                wait_for_confirmation=False,
                route=route,
            )
            if return_code != 0:
                ui.notify(f"Could not import into Tasker: {message}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            # Closed before the edit is kept rather than after, so that a failure in keeping it
            # cannot be what leaves the panel on screen.
            android_dialog.close()
            parent_dialog.close()
            keep_edit()

            subject = f"{route.label} '{object_name}'"
            # Where the file actually is, said in every message from here on.  The staged file
            # carries the object's own name (deviceinv.staged_paths), and naming it is what makes
            # a handoff Tasker does not complete recoverable: the user finishes the import out of
            # Tasker's own browser, which they can only do if they know which file it is.  Same
            # reason import_scene_into_tasker_event names its file -- that route is nothing but
            # this case.
            waiting = (
                f"  {device_path} is on the device -- if Tasker is not in the chooser, {by_hand}."
                if by_hand
                else f"  {device_path} is on the device and can be imported by hand if it does not."
            )

            if confirmable is not True:
                # No timeout on this one, and nothing to take it down: it is the last thing this
                # will say, it asks the user to go and do something, and there is no outcome
                # coming that could replace it.  Its close button is how it goes.
                ui.notification(
                    f"Tasker's import screen is open on {ip_address}:{ip_port} for {subject}.  Tasker already "
                    "has what this would import and will offer to replace it -- confirm on the device.  "
                    f"Whether that was confirmed cannot be seen from here.{waiting}",
                    type="info",
                    timeout=None,
                    close_button=True,
                    multi_line=True,
                )
                return

            # ui.notification rather than ui.notify, for the handle: this one has no timeout
            # because there is no telling how long someone takes to reach their phone, and a
            # message with no timeout and nothing to dismiss it is a box that sits on screen for
            # the rest of the session.  It is a status line for a step in progress, so the
            # outcome below takes it down and replaces it.
            pending = ui.notification(
                f"Tasker's import screen is open on {ip_address}:{ip_port} -- tap Import on the device to finish."
                f"{waiting}",
                type="info",
                timeout=None,
                close_button=True,
                multi_line=True,
            )

            # Runs on with the dialogs gone; all it can do now is report.
            return_code, message = await run.io_bound(
                deviceinv.await_import,
                ip_address,
                ip_port,
                confirm_names,
                subject,
                route.confirm_endpoint,
                staged_at=device_path,
                **({"attempts": attempts} if attempts else {}),
            )
            # Guarded, because this notification is likely to be GONE by now and through no
            # fault of anyone's: it carries a close button, it sits there for up to two minutes
            # while someone walks to their phone, and a client that reloaded in the meantime
            # takes its elements with it.  Dismissing a deleted element makes nicegui log a
            # warning about a bug in the application code -- and the two-minute wait is exactly
            # the window in which the user is most likely to have tidied it away themselves.
            with contextlib.suppress(Exception):
                pending.dismiss()
            # Not an error in the usual sense: most likely nobody has got to the phone yet, or
            # they declined.  Either way it is the DEVICE this reports on, not the edit here.
            with contextlib.suppress(Exception):
                ui.notify(message, type="positive" if return_code == 0 else "warning")

        async def _offer_from_the_prompt() -> None:
            """_offer, run from the overwrite prompt's callback, with a slot to build into.

            NOT A WRAPPER FOR THE SAKE OF IT.  nicegui's slot stack is per-asyncio-task
            (nicegui.slot.Slot.get_stack is keyed by task id), so a coroutine started with
            create_task begins with an empty one -- and ui.notify and ui.notification build
            elements, which need a slot.  Every notification in _offer therefore raised
            'the slot stack for this task is empty' the moment the offer ran from the prompt
            rather than directly, which is exactly what nicegui's own message tells you to
            fix by entering the target explicitly.

            The client is captured out there, in the handler's own task, where there is one.
            Entering it here pushes its slot onto THIS task's stack, and it stays pushed
            across the awaits inside because the whole of _offer is awaited within the block.
            """
            with client:
                await _offer()

        tasker_lines = await _what_tasker_already_has(
            ip_address,
            ip_port,
            lambda: xml_bytes,
            _IMPORT_SCREEN_CONSEQUENCE,
            check_ids=check_ids,
        )
        if exists is not False or tasker_lines:
            # Cancel leaves both dialogs open with the edit intact, so nothing is lost by
            # saying no -- the same contract every other overwrite prompt here has.
            # create_task because the prompt's callback is synchronous and the offer is not;
            # the coroutine has nothing left to report back to, having taken over the
            # notifications itself.
            client = context.client

            def _start_offer() -> None:
                """Spawn the offer, and do not lose what it raises.

                A bare create_task drops the exception: asyncio prints "Task exception was
                never retrieved" to the console and the user is left watching an import that
                silently never happens.  Not hypothetical -- that is exactly how the missing
                slot above went unnoticed until someone read their terminal.  The same
                treatment guiwins._report_view_failure gives a view's rendering task.
                """
                asyncio.create_task(_offer_from_the_prompt()).add_done_callback(_report_offer_failure)

            build_overwrite_confirm_dialog(
                f"'{device_read_path}' on the Android device",
                _start_offer,
                **_overwrite_prompt_options(exists, tasker_lines),
            )
            return
        # Awaited in the handler's own task, which already has a slot -- see
        # _offer_from_the_prompt for the case that does not.
        await _offer()

    async def import_scene_into_tasker_event(
        self,
        edited_scene: sceneedit.EditableScene,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Put the Scene -- and every Task its elements fire -- on the device and open
        Android's "Open with..." chooser for it, with Tasker's own 'Scenes > Import One
        Scene' as the fallback the message spells out.

        THE HARDEST OF THE FOUR TO HAND OVER, and the reason the fallback is spelled out
        rather than assumed.  Four things were tried and measured, and none of them imported
        a Scene:

            mime type      identical to the Profile's ('text/xml'), from one shared builder
            extension      '.scn.xml', which Android resolved to a chooser with no Tasker
            explicit intent Tasker's own package AND class -- Tasker opens, imports nothing
            folder         /Tasker/scenes, Tasker's own -- same result

        The same file, picked by hand in Tasker, imports correctly.  So the XML is right and
        it is the handoff Tasker would not complete.  For a while that was read as settling
        it, and this handler did everything up to the handoff and then merely opened Tasker.

        WHAT THOSE FOUR HAVE IN COMMON is that every one of them carried a mime type or named
        a component.  The fifth thing -- an implicit VIEW with NO type, which is what a file
        manager's 'Open with' fires -- is the only one that lets an extension filter match at
        all, and it had not been tried.  See deviceinv._OPEN_WITH_MIME_TYPE, which is honest
        that this is reasoning and not a measurement.  So a Scene is offered like every other
        kind now, and if the chooser comes up without Tasker in it the user is exactly where
        they were before, with the file named and the menu named.

        THE FILE CARRIES THE SCENE'S OWN NAME, because the name is what the user picks out of
        a list on their phone.  This route got there first; the other three have since caught
        up, told which file at run time through %par1 (see deviceinv.run_task_on_android).
        It is the same path 'Save As File' writes, so it asks that button's overwrite question
        and keeps its safety copy -- both of which _offer_into_tasker now does for all of
        them.

        The apply is load-bearing exactly as it is there: the export renders the Scene from
        the LIVE TREE by name, while the dialog edits a deep copy nothing writes back until
        a save handler runs.  Without it, an element added a moment ago is simply absent
        from the file that reaches the phone.  It also means a bad field stops this before
        the device is contacted.
        """
        errors = _apply_scene_field_values(edited_scene, field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        sceneedit.apply_edited_scene_to_live_tree(edited_scene.scene_name, edited_scene)

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_scene(edited_scene.scene_name)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        scene_name = edited_scene.scene_name

        # The same offer the other two kinds get, and a Scene did not have one until
        # 2026-08-30: every measured way of handing Tasker a '.scn.xml' had failed, so this
        # uploaded the file and merely opened Tasker, leaving the whole import to the user.
        # The "Open with..." is a third thing rather than a repeat of either failure -- see
        # deviceinv.OPEN_SCENE_ROUTE and _OPEN_WITH_MIME_TYPE -- and it costs nothing if it
        # is wrong, because the by-hand instruction below is still there.
        #
        # Everything else _offer_into_tasker does a Scene wanted anyway: the overwrite
        # prompt, the safety copy, staging under the Scene's own name, and the two-phase
        # wait.  The bespoke copy of all that is gone.
        await self._offer_into_tasker(
            sceneedit.render_standalone_scene_xml(edited_scene.scene_name).encode("utf-8"),
            edited_scene.scene_name,
            [edited_scene.scene_name],
            deviceinv.OPEN_SCENE_ROUTE,
            ip_address,
            ip_port,
            android_dialog,
            parent_dialog,
            lambda: None,  # the edits are already in the live tree -- see the apply above
            by_hand=(f"import it with Tasker's 'Scenes > Import One Scene' and pick '{edited_scene.scene_name}'"),
            attempts=deviceinv.MANUAL_IMPORT_POLL_ATTEMPTS,
            check_ids=_check_ids_ticked(android_field_refs),
        )

    async def import_project_into_tasker_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Put the Project -- and every Profile and Task in it -- in front of Tasker's own
        import screen on the device.  The Project counterpart of
        import_profile_into_tasker_event; both hand off to _offer_into_tasker.

        Same unapplied-edits guard as save_project_to_android_event, and for the same reason:
        this exports the Project from the LIVE TREE by name, so a field added to the dialog
        without its apply step would be dropped silently from what reaches the phone.  Run
        before the device is contacted.

        Nothing is registered afterwards.  A Project has no separate editable model -- the
        export reads the live tree -- so unlike a Profile there is no edit to keep.

        Confirmation goes through the Project's own Profiles, because Tasker's HTTP API has
        no /api/projects to ask about the Project itself; see projedit.project_profile_names.
        """
        errors = _unapplied_project_edits(field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_project(edited_project.project_name)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        project_name = edited_project.project_name
        project_xml = projedit.render_standalone_project_xml(project_name).encode("utf-8")

        await self._offer_into_tasker(
            project_xml,
            project_name,
            projedit.project_profile_names(project_name),
            # The "Open with..." route, for the reason import_profile_into_tasker_event gives
            # at length: the user picks Tasker out of Android's own chooser rather than this
            # program guessing what a '.prj.xml' resolves to.  A Project has exactly the same
            # exposure to that guess as a Profile, so it makes the same choice.
            deviceinv.OPEN_PROJECT_ROUTE,
            ip_address,
            ip_port,
            android_dialog,
            parent_dialog,
            lambda: None,
            check_ids=_check_ids_ticked(android_field_refs),
        )

    def open_save_project_to_android_dialog_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        parent_dialog: ui.dialog,
    ) -> None:
        """Opens the IP/port prompt for writing this Project onto the Android device.
        The Edit Project dialog's field_refs go with it for the upload's guard -- see
        _unapplied_project_edits.
        """
        build_save_project_to_android_dialog(self.gui, edited_project, field_refs, parent_dialog)

    async def save_project_to_android_event(
        self,
        edited_project: projedit.EditableProject,
        field_refs: dict,
        android_field_refs: dict,
        android_dialog: ui.dialog,
        parent_dialog: ui.dialog,
    ) -> None:
        """Pings the Android device to confirm it's reachable, then writes the
        Project -- every Profile and Task it owns -- onto the device's storage
        under /Tasker/projects (see projedit.save_project_to_android). Unlike
        save_profile_to_android_event, there's no field-edit/apply step first --
        a Project has no separate editable model, and this exports under its
        current, already-applied name, same as save_project_event's local export.

        That "no apply step" is an assertion about the dialog, not a permanent fact
        about Projects, so it is checked rather than assumed: the guard runs before the
        device is contacted, so a field added without its apply fails here instead of
        putting an incomplete Project on the phone.  See _unapplied_project_edits.
        """
        errors = _unapplied_project_edits(field_refs)
        if errors:
            for error in errors:
                ui.notify(error, type="negative")
            return

        ip_address = android_field_refs["ip_address"].value.strip()
        ip_port = android_field_refs["ip_port"].value.strip()
        remember_android_address(self.gui, ip_address, ip_port)

        # The panel's "Verify" checkbox, answered before the device is touched at all:
        # a document that cannot be read back unchanged is refused here rather than
        # written half-way there.  Costs nothing when the box is unticked.
        if not _round_trip_verified(android_field_refs, lambda: roundtrip.verify_project(edited_project.project_name)):
            return

        if not await ping_android_device(self.gui, ip_address, ip_port):
            return

        # Everything from here on is a request the device answers with an authorization
        # prompt of its own -- see guiutils.notify_watch_android_device.
        notify_watch_android_device()

        async def _upload() -> None:
            # Keep whatever is already at that path before /upload writes over it.  The
            # device keeps no versions and has no undo, so this is the only copy of it there
            # will ever be; it is kept here rather than left beside the original -- see
            # presave.save_android_safety_copy.  The bytes come from the existence check
            # below rather than from a second GET, because the Tasker HTTP Server Example
            # flashes 'File doesn't exist' on the phone for every miss (its /file handler
            # runs Test File first -- see its file-system Profile), so asking twice put two
            # of them on screen for one save.  A copy that fails is reported and the save
            # goes ahead: presave's module comment says why it must never block one.
            copied, safety_copy = presave.save_android_safety_copy(device_path, already_there)
            if not copied:
                ui.notify(
                    f"Could not copy the file already on the device first: {safety_copy}",
                    type="warning",
                )
            # Uploads and reads back, which takes seconds: a worker thread, not the event loop.
            return_code, result = await run.io_bound(
                projedit.save_project_to_android,
                edited_project.project_name,
                ip_address,
                ip_port,
            )
            if return_code != 0:
                ui.notify(f"Could not save to Android device: {result}", type="negative")
                return

            # Remember the connection details for next time, same as the Get XML dialog does.
            self.gui.android_ipaddr = ip_address
            self.gui.android_port = ip_port

            # `copied and` matters: on a failure safety_copy holds the reason, not a path.
            saved_note = f" The file it replaced was copied to {safety_copy}." if copied and safety_copy else ""
            ui.notify(f"Project saved to Android device at {result}.{saved_note}", type="positive")
            android_dialog.close()
            parent_dialog.close()

        # /upload overwrites silently and answers 200 either way, so the only way to know is
        # to read the destination back first -- one read, which answers both what is there
        # and what it holds, so the safety copy above needs no second GET of its own (see
        # maputil2.read_android_file).  None = couldn't tell, which still prompts rather than
        # risking a silent clobber.
        device_path = projedit.android_project_path(edited_project.project_name)
        exists, already_there = await run.io_bound(read_android_file, ip_address, ip_port, device_path)
        tasker_lines = await _what_tasker_already_has(
            ip_address,
            ip_port,
            lambda: projedit.render_standalone_project_xml(edited_project.project_name),
            _FILE_WRITE_CONSEQUENCE,
            check_ids=_check_ids_ticked(android_field_refs),
        )
        if exists is not False or tasker_lines:
            build_overwrite_confirm_dialog(
                f"'{device_path}' on the Android device",
                _upload,
                **_overwrite_prompt_options(exists, tasker_lines),
            )
            return
        await _upload()

    async def fetch_backup_event(self) -> None:
        """
        Fetches backup/XML details from NiceGUI user input fields and processes them.

        - Validates IP address, port, and file location using .value properties.
        - Pings the Android device to check reachability.
        - Validates or fetches XML filelist.
        - Updates the UI and internal state based on the fetched details.
        """
        gui = self.gui

        # NICEGUI PARADIGM SHIFT: Replace legacy .get() calls with reactive .value properties
        android_ipaddr = gui.ip_entry.value if hasattr(gui, "ip_entry") and gui.ip_entry else ""
        android_port = gui.port_entry.value if hasattr(gui, "port_entry") and gui.port_entry else ""
        android_file = (
            "" if gui.list_files else (gui.file_entry.value if hasattr(gui, "file_entry") and gui.file_entry else "")
        )

        if hasattr(self, "_validate_input"):
            error_msg = self._validate_input(android_ipaddr, android_port)
            if error_msg:
                gui.display_message_box(error_msg, "Red")
                return

        # Kept whether or not the device answers: the next try, in this session or the next,
        # should start from what was typed rather than from the default.
        remember_android_address(gui, android_ipaddr, android_port)

        # --- Await the async ping function ---
        if not await ping_android_device(gui, android_ipaddr, android_port):
            return

        # Attempt to pull structural backup contents or directory arrays
        # Awaited: listing the device's files installs and runs a helper Task and waits
        # for its answer, which validate_or_filelist_xml hands to run.io_bound.
        return_code, android_ipaddr, android_port, android_file = await validate_or_filelist_xml(
            gui,
            android_ipaddr,
            android_port,
            android_file,
        )

        # Handle structural anomalies gracefully
        if return_code not in (0, 2):
            gui.display_message_box(f"File not found. Return code: {return_code}", "Red")
            return

        # Return code 2 signals that a sub-menu select drop-down tree is actively open waiting for user click feedback
        if return_code == 2:
            return

        # Commit validated settings data properties down to our internal tracking state structures
        if hasattr(self, "_update_internal_state"):
            self._update_internal_state(android_ipaddr, android_port, android_file)
        else:
            gui.android_ipaddr = android_ipaddr
            gui.android_port = android_port
            gui.android_file = android_file

        # A different backup is now the source, so the Project/Profile/Task/Scene picked
        # from the previous one is no longer a meaningful filter, and the pulldowns are
        # still offering the previous file's names.  This branch -- the user typing the
        # file location instead of picking it from 'List XML Files' -- now ends the same
        # way file_selected_event does, with the newly fetched file loaded and its own
        # objects in the pulldowns: reset_single_names=True clears the previous
        # selection on the way through (it is reset_single_item_selection that runs
        # inside), and the fetch has already written the file to the local drive
        # (validate_or_filelist_xml -> validate_xml -> write_out_backup_file), so
        # loading it here reads that local copy rather than going back to the device.
        clear_tasker_data()
        update_tasker_object_menus(gui, get_data=True, reset_single_names=True)

        # And, as on every other path that loads a file, a single-object export selects
        # the one object it holds.
        self.select_single_item_export(android_file)

        # Trigger final visual confirmation UI updates
        if hasattr(self, "_display_backup_summary"):
            self._display_backup_summary()
        else:
            gui.display_message_box(translate_string("Android configuration details matched successfully!"), "Green")


def _report_offer_failure(task: asyncio.Task) -> None:
    """Log whatever the spawned import offer raised, instead of losing it.

    Cancellation is ordinary -- a page that went away while the offer was in flight -- and
    says nothing.  Mirrors guiwins._report_view_failure, which does this for a view's
    rendering task; the two exist separately only because neither module imports the other's
    private helpers.
    """
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("Offering an import to Tasker failed", exc_info=error)
