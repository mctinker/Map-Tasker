"""The App, icon and Run-on-Android pickers and dialogs the Edit Task and Add Task windows open."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from nicegui import run, ui

from maptasker.src.core import appinv
from maptasker.src.core.maputil2 import tasker_name_matchable, translate_string
from maptasker.src.device import deviceinv, devicetask
from maptasker.src.edit import (
    profedit,
    taskedit_args,
    taskedit_model,
)
from maptasker.src.gui.guiutils_android import (
    android_address_defaults,
    remember_android_address,
    remember_android_address_fields,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState
    from maptasker.src.gui.userintr import MyGui


# How many rows either pick-from-the-inventory dialog draws at once.  A real backup
# harvests ~50 Applications and ~140 icons (see appinv.py), but a large configuration
# holds more, and the list is rebuilt on every keystroke of the search box -- the same
# reasoning behind _ICON_PREVIEW_LIMIT, which the Scene designer's own picker uses.
_PICKER_ROW_LIMIT = 200


# Tasker's own icons are named <set>_<category>_<name> -- "mw_action_info_outline" -- and the
# artwork is inside the Tasker app on the phone, so it cannot be drawn here.  What can be is
# the Material glyph of the same name, which is what 'mw' (Material) icons are and a close
# stand-in for the Holo 'hd'/'hl' ones.  Anything else gets a glyph for its kind, so every
# row still has a picture to tell it from the next.
_TASKER_ICON_SETS = ("mw", "hd", "hl")


_ICON_KIND_GLYPHS = {"builtin": "image", "pack": "extension", "app": "android", "var": "percent"}


_ICON_GLYPH_STYLE = "font-size: 24px;"


def _tasker_icon_glyph(icon: appinv.IconRef) -> str:
    """The Material icon name to draw one icon by -- its own for a 'mw_' built-in, a
    look-alike for an 'hd_'/'hl_' one, and a generic glyph for its kind otherwise.
    """
    if icon.kind == "builtin":
        parts = icon.name.split("_", 2)
        if len(parts) == 3 and parts[0] in _TASKER_ICON_SETS:
            candidate = parts[2]
            # 'mw' is Material by definition.  The look-alike sets are only trusted when the
            # name is one the font is known to hold: an unknown ligature is drawn as its own
            # text, which is worse than a generic glyph.
            if parts[0] == "mw" or candidate in appinv.material_icon_names():
                return candidate
    return _ICON_KIND_GLYPHS.get(icon.kind, "image")


def _picker_search_input(on_change: Callable[[str], None], placeholder: str) -> ui.input:
    """The search box both pickers below open with."""
    search_input = (
        ui.input(placeholder=translate_string(placeholder), on_change=lambda e: on_change(str(e.value or "")))
        .props("outlined dense clearable autofocus")
        .classes("w-full mt-2")
    )
    with search_input.add_slot("prepend"):
        ui.icon("search")
    return search_input


async def build_fetch_apps_dialog(gui: MyGui, on_fetched: Callable[[], None], for_icons: bool = False) -> None:
    """Ask an Android device for the full list of installed Applications.

    Offered from inside the Application pickers rather than from the sidebar, because
    inside them is where the gap is felt: the list holds what this configuration already
    names, and the moment a user notices the app they want is missing is the moment they
    are looking at it.

    Prompts for the device the same way every other Save To Android does
    (build_save_to_android_dialog), defaults from the same remembered address, and writes
    the address back on success so the next one is pre-filled.

    Lists the devices already fetched, each with a Forget button.  on_fetched runs after a
    successful fetch, and also on Cancel when a device was forgotten, since either one
    changes the list the caller is showing.

    The fetch itself installs a helper Task on the device, runs it, and waits for the file
    it writes -- seconds, not milliseconds -- so it goes through run.io_bound and the
    button says what it is doing while it happens.  See deviceinv.fetch_apps_from_device.

    for_icons says the user came here wanting icons rather than Applications, which changes
    what this says and nothing about what it does.  It is the same fetch either way: an
    app's own icon is its package plus its launcher activity, so the Application list is an
    icon list too (appinv._merged_with_device_icons).  Saying so is the point -- a dialog
    headed "Fetch Applications" in answer to "there are no icons" looks like the wrong
    button, and the two kinds of icon the fetch cannot bring back have to be said out loud
    rather than left to be discovered in the picker afterwards.

    Deliberately does NOT pre-flight with guiutils_android.ping_android_device, which every other
    Android dialog here does.  That probe used to be disqualifying -- it was a GET on the
    'maplist' route, served by the 'MapTasker List' TaskerNet profile rather than by the
    HTTP Server Example project, so a user who had the server running but had never
    imported that profile failed it despite needing nothing it tested.  The probe no longer
    depends on that profile (nothing does), but skipping it is still the better answer
    here: this fetch's own first step is a GET /api/auth against the very API it goes on to
    use, which is both the right thing to test and the thing whose failure message is worth
    showing.
    """
    _FetchAppsDialog(gui, on_fetched, for_icons).build()


class _FetchAppsDialog:
    """The Fetch Applications (or Icons) From Android Device dialog.

    A class rather than closures because the device list, the Fetch button and its progress row are
    all redrawn from several handlers, and "a device was forgotten" has to outlive each of them.
    """

    def __init__(self, gui: MyGui, on_fetched: Callable[[], None], for_icons: bool) -> None:
        """
        Args:
            gui: The application window, which holds the run's state and the remembered address.
            on_fetched: Called when the list of applications has changed, by a fetch or a forget.
            for_icons: Whether the user came for icons rather than Applications; see build_fetch_apps_dialog.
        """
        self.gui = gui
        self.on_fetched = on_fetched
        self.for_icons = for_icons
        self.forgot = False
        self.dialog: ui.dialog
        self.device_rows: ui.column
        self.ip_field: ui.input
        self.port_field: ui.input
        self.progress_row: ui.row
        self.fetch_button: ui.button

    def build(self) -> None:
        """Draw the dialog and open it."""
        default_ip, default_port = android_address_defaults(self.gui)

        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("min-w-[460px] p-6"):
            self._build_explanation()

            # Each list already fetched, with a way to drop it.  A device is filed under the
            # address it answered on, so a phone that has moved address is a second entry here,
            # and the first one's list -- apps since uninstalled and all -- stays in the pickers
            # and in the Health Check's plugin check until it is forgotten (appinv.forget_device).
            self.device_rows = ui.column().classes("w-full gap-0 mt-1")
            self.show_devices()

            self.ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full")
            self.port_field = ui.input(translate_string("Port"), value=default_port).classes("w-full")
            remember_android_address_fields(self.gui, self.ip_field, self.port_field, self.dialog)

            self._build_progress_row()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(translate_string("Cancel"), on_click=self.cancel).props("outline")
                self.fetch_button = ui.button(translate_string("Fetch"), on_click=self.fetch).classes("bg-blue-600")
                self.fetch_button.tooltip(
                    translate_string("Fetch the full list of installed Applications from the Android device."),
                )

        self.dialog.open()

    def _build_explanation(self) -> None:
        """The heading and what the fetch will do, including what to expect on the phone."""
        title = "Fetch Icons From Android Device" if self.for_icons else "Fetch Applications From Android Device"
        ui.label(translate_string(title)).classes("text-lg font-bold text-blue-600")
        if self.for_icons:
            ui.label(
                translate_string(
                    "Icons come from the same place Applications do: Tasker identifies an application's "
                    "own icon by its package and launcher activity, so every application found on the "
                    "device becomes an icon you can pick.\n\n"
                    "Tasker's own built-in icons cannot be fetched -- they live inside Tasker itself -- "
                    "and neither can the icons inside an icon pack, which have to be typed by name.",
                ),
            ).classes("text-sm text-gray-500 italic whitespace-pre-wrap")
        # The Task's name comes from deviceinv rather than being spelled out here: it is
        # versioned, and backing out deviceinv.PAIR_LABELS_ON_DEVICE changes which version
        # gets installed.  A hardcoded name would go on naming the wrong one.
        ui.label(
            translate_string(
                f"MapTasker will install a small Task named '{deviceinv.HELPER_TASK_NAME}' on the device, run "
                "it to list every installed application, and read the answer back.  Tasker must be running, "
                "with the 'HTTP Server Example' and 'Tasker HTTP API' projects active -- the same requirement 'Save to Android' has.",
            ),
        ).classes("text-sm text-gray-500 italic")
        # The two things that make a working fetch look like a broken one.  Both are said
        # here, before the button is pressed, and again on screen while it runs (see
        # progress_label): a prompt nobody knows to expect is a prompt nobody answers, and a
        # wait nobody was warned about is a wait people give up on.
        ui.label(
            translate_string(
                "Watch your Android device: Tasker will ask you to authorize the connection, and the "
                "fetch cannot go on until you accept.  Allow 30 seconds or more once you have -- longer "
                "on a device with several hundred applications, since each one's name is looked up "
                "individually.",
            ),
        ).classes("text-sm text-amber-700 dark:text-amber-500 mt-2")

    def _build_progress_row(self) -> None:
        """The spinner and message shown while the fetch runs, hidden until it starts.

        The button going grey and saying 'Fetching...' is not enough on its own: what the user
        has to do next is happening on the phone, not here, and nothing on this screen would
        otherwise say to go and look at it.
        """
        self.progress_row = ui.row().classes("w-full items-center gap-2 mt-3")
        self.progress_row.set_visibility(False)
        with self.progress_row:
            ui.spinner(size="sm")
            ui.label(
                translate_string(
                    "Waiting on the Android device -- accept the authorization prompt there if one "
                    "appears.  This can take 30 seconds or more.",
                ),
            ).classes("text-sm text-amber-700 dark:text-amber-500")

    def forget(self, device: str) -> None:
        """Drop one device's list of applications, and redraw the list of devices."""
        error = appinv.forget_device(device)
        self.forgot = True
        # Tell the user before redrawing: this runs in the Forget button's click handler, and redrawing the list
        # deletes that button -- and with it the place a notification is sent from.
        if error:
            ui.notify(f"{translate_string('Forgotten for now, but could not be saved:')} {error}", type="warning")
        else:
            ui.notify(f"{translate_string('Forgot the applications fetched from')} {device}", type="info")
        self.show_devices()

    def show_devices(self) -> None:
        """Draw a row for each device already fetched from, with its Forget button."""
        self.device_rows.clear()
        with self.device_rows:
            for device, when, count in appinv.fetched_devices():
                with ui.row().classes("w-full items-center justify-between no-wrap"):
                    ui.label(f"{device}: {count} {translate_string('applications, fetched')} {when}").classes(
                        "text-xs text-gray-500",
                    )
                    forget_button = ui.button(
                        translate_string("Forget"),
                        on_click=lambda _event, device=device: self.forget(device),
                    ).props("flat dense no-caps color=negative")
                    forget_button.tooltip(
                        translate_string(
                            "Remove this device's list of applications.  Do this for a device you no longer "
                            "use, or an old address of this one, so apps that are not installed any more stop "
                            "being offered and counted as installed.",
                        ),
                    )

    async def fetch(self) -> None:
        """Ask the device for its applications, reporting what happens."""
        gui = self.gui
        ip_address = str(self.ip_field.value or "").strip()
        ip_port = str(self.port_field.value or "").strip()
        remember_android_address(gui, ip_address, ip_port)

        self.fetch_button.set_text(translate_string("Fetching..."))
        self.fetch_button.set_enabled(False)
        self.progress_row.set_visibility(True)
        try:
            fetched = await run.io_bound(deviceinv.fetch_apps_from_device, ip_address, ip_port, state=gui.state)
        finally:
            self.fetch_button.set_text(translate_string("Fetch"))
            self.fetch_button.set_enabled(True)
            self.progress_row.set_visibility(False)

        # None rather than a pair: nicegui answers that when the wait is cancelled or the
        # app is stopping (see nicegui.run._run).  The fetch itself is finished or will
        # finish; there is just no page left to report it to.
        if fetched is None:
            return
        return_code, message = fetched
        if return_code != 0:
            ui.notify(message, type="negative", timeout=8000)
            return

        # Remembered for next time, same as the Get XML and Save To Android dialogs do.
        gui.android_ipaddr = ip_address
        gui.android_port = ip_port
        ui.notify(message, type="positive", timeout=6000)
        self.dialog.close()
        self.on_fetched()

    def cancel(self) -> None:
        """Close without fetching -- but a forgotten device has changed the list all the same."""
        self.dialog.close()
        if self.forgot:
            self.on_fetched()


def _format_task_output(output: str) -> str:
    """A Task's return value as the Run dialog shows it: JSON laid out, anything else as it came."""
    try:
        parsed = json.loads(output)
    except ValueError:
        return output
    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    return output


def build_run_task_on_android_dialog(
    gui: MyGui,
    task_name: str,
    has_pending_edits: Callable[[], bool] | None = None,
) -> None:
    """Run a Task on the Android device and show what it returned, or why it did not.

    Opened from the Edit Task dialog and from the Map's 'Run On Android' button.  The Task
    runs as Tasker on the device has it -- nothing from the loaded configuration or an open
    editor is sent -- so has_pending_edits, when given, is asked at Run time and a warning
    shown if the editor holds changes the device has not seen.

    The dialog stays open after a run, success or failure, so the Task can be run again with
    different %par1/%par2 values without re-entering the address.  The run itself waits for
    the Task to finish, so it goes through run.io_bound -- see devicetask.run_task_for_result.
    """
    _RunTaskOnAndroidDialog(gui, task_name, has_pending_edits).build()


class _RunTaskOnAndroidDialog:
    """The Run Task On Android dialog: its fields, the Run button, and where a run's outcome is shown."""

    def __init__(self, gui: MyGui, task_name: str, has_pending_edits: Callable[[], bool] | None) -> None:
        """
        Args:
            gui: The application window, which holds the run's state and the remembered address.
            task_name: The Task to run on the device.
            has_pending_edits: Asked at Run time whether the editor holds changes the device has not seen.
        """
        self.gui = gui
        self.task_name = task_name
        self.has_pending_edits = has_pending_edits
        self.dialog: ui.dialog
        self.ip_field: ui.input
        self.port_field: ui.input
        self.par1_field: ui.input
        self.par2_field: ui.input
        self.progress_row: ui.row
        self.result_column: ui.column
        self.run_button: ui.button

    def build(self) -> None:
        """Draw the dialog and open it."""
        default_ip, default_port = android_address_defaults(self.gui)

        with ui.dialog() as self.dialog, ui.card().classes("min-w-[520px] max-w-[900px] w-full p-6"):
            self._build_explanation()

            with ui.row().classes("w-full gap-4"):
                self.ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("flex-1")
                self.port_field = ui.input(translate_string("Port"), value=default_port).classes("w-32")
            remember_android_address_fields(self.gui, self.ip_field, self.port_field, self.dialog)
            with ui.row().classes("w-full gap-4"):
                self.par1_field = ui.input(translate_string("%par1 (optional)")).classes("flex-1")
                self.par2_field = ui.input(translate_string("%par2 (optional)")).classes("flex-1")

            self.progress_row = ui.row().classes("w-full items-center gap-2 mt-3")
            self.progress_row.set_visibility(False)
            with self.progress_row:
                ui.spinner(size="sm")
                ui.label(
                    translate_string(
                        "Running on the Android device -- accept the authorization prompt there if one appears.",
                    ),
                ).classes("text-sm text-amber-700 dark:text-amber-500")

            # Built empty and hidden; each run fills it with that run's outcome.
            self.result_column = ui.column().classes("w-full gap-1 mt-3")
            self.result_column.set_visibility(False)

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button(translate_string("Close"), on_click=self.dialog.close).props("outline")
                self.run_button = ui.button(translate_string("Run"), on_click=self.run_task).classes("bg-blue-600")

        self.dialog.open()

    def _build_explanation(self) -> None:
        """The heading, what a run does, and what to expect on the phone."""
        ui.label(f"{translate_string('Run Task On Android')}: {self.task_name}").classes(
            "text-lg font-bold text-blue-600",
        )
        ui.label(
            translate_string(
                "Runs the Task as Tasker on the Android device has it now, waits for it to finish, and "
                "shows what it returned.  Edits not yet sent with 'Save To Android' are not part of the "
                "run.  Tasker must be running, with the 'HTTP Server Example' and 'Tasker HTTP API' projects active.",
            ),
        ).classes("text-sm text-gray-500 italic")
        if not tasker_name_matchable(self.task_name):
            ui.label(
                translate_string(
                    f"Tasker's HTTP server cannot look up a name holding characters such as $ ( ) + or ?, so "
                    f"this Task is run through a small helper Task, '{devicetask.RUN_TASK_HELPER_NAME}', which "
                    "MapTasker installs on the device the first time.",
                ),
            ).classes("text-sm text-gray-500 italic mt-1")
        ui.label(
            translate_string(
                "The Task really runs: anything it does on the device -- messages, settings, files -- "
                "happens for real.",
            ),
        ).classes("text-sm text-amber-700 dark:text-amber-500 mt-1")
        # Tasker asks per request rather than once (see guiutils_android.notify_watch_android_device), and a
        # run can take several -- a lookup, a helper install, the run itself -- so say to expect more
        # than one, in the words the device shows, before Run is pressed.
        ui.label(
            translate_string(
                "Watch your Android device: expect one or more prompts from Tasker reading 'Tasker API "
                "Authorize request from python-requests...'.  Accept each one, or the run fails.",
            ),
        ).classes("text-sm text-amber-700 dark:text-amber-500 mt-1")

    def show_result(self, result: devicetask.TaskRunResult) -> None:
        """Show what a run came to: its return value, or why there is none."""
        self.result_column.clear()
        with self.result_column:
            if result.ok:
                ui.label(
                    f"{translate_string('Task finished in')} {result.seconds:.1f}s.",
                ).classes("text-sm font-bold text-green-700 dark:text-green-500")
                if result.output:
                    ui.label(translate_string("Return value:")).classes("text-xs text-gray-500")
                    ui.code(_format_task_output(result.output), language="text").classes(
                        "w-full max-h-80 overflow-auto",
                    )
                else:
                    ui.label(translate_string("The Task did not return a value.")).classes(
                        "text-sm text-gray-500 italic",
                    )
            else:
                ui.label(translate_string("The Task could not be run.")).classes(
                    "text-sm font-bold text-red-600",
                )
                ui.label(result.error).classes("text-sm text-red-600 whitespace-pre-wrap")
        self.result_column.set_visibility(True)

    async def run_task(self) -> None:
        """Run the Task on the device, and show what it returned."""
        gui = self.gui
        ip_address = str(self.ip_field.value or "").strip()
        ip_port = str(self.port_field.value or "").strip()
        if not ip_address or not ip_port:
            ui.notify(translate_string("Enter the Android device's IP Address and Port."), type="warning")
            return
        remember_android_address(gui, ip_address, ip_port)
        if self.has_pending_edits is not None and self.has_pending_edits():
            ui.notify(
                translate_string(
                    "This Task has unsaved edits.  The device runs the version it already has -- "
                    "use 'Save To Android' first to run the edited one.",
                ),
                type="warning",
            )

        self.run_button.set_text(translate_string("Running..."))
        self.run_button.set_enabled(False)
        self.progress_row.set_visibility(True)
        self.result_column.set_visibility(False)
        try:
            result = await run.io_bound(
                devicetask.run_task_for_result,
                ip_address,
                ip_port,
                self.task_name,
                str(self.par1_field.value or ""),
                str(self.par2_field.value or ""),
                state=gui.state,
            )
        finally:
            self.run_button.set_text(translate_string("Run"))
            self.run_button.set_enabled(True)
            self.progress_row.set_visibility(False)
        # None is nicegui's answer for a cancelled wait or an app that is stopping (see
        # nicegui.run._run), not a run of the Task: the Task ran on the device regardless,
        # and only the page that would show what it returned has gone.
        if result is None:
            return
        self.show_result(result)


def _render_variable_entry(on_variable: Callable[[str], None], button_text: str) -> None:
    """A row for naming a Tasker variable instead of an installed application.

    An <appPkg> is legitimately a variable -- this repo's own backup has eleven of them,
    including '%app_package(%ld_selected_index)' -- and until now the only way to say so was
    to close the picker and type into the field behind it.  The field is still there and
    still works; this just means the picker no longer has to be got out of the way first.

    Validation is appinv.is_variable_reference: a leading '%' and something after it, and
    nothing more, since what follows the '%' can be an array index or a function call and is
    Tasker's business rather than this tool's.
    """
    variable_input = ui.input(placeholder=translate_string("%variable_name")).props("outlined dense").classes("flex-1")

    def use_variable() -> None:
        text = str(variable_input.value or "").strip()
        if not appinv.is_variable_reference(text):
            ui.notify(
                translate_string("A variable name has to start with '%' -- for example %app_package."),
                type="warning",
            )
            return
        on_variable(text)
        variable_input.set_value("")

    variable_input.on("keydown.enter", use_variable)
    ui.button(translate_string(button_text), on_click=use_variable).props("flat dense color=primary")


class _AppPicker:
    """The Pick an Application dialog: the ticks, the search, and what goes back into the field.

    Held in a class rather than closures because everything it does reads or changes the same
    handful of things -- what is ticked, what the field holds that is not in the inventory,
    what has been typed in the search box -- and each of the handlers is then a method that says
    so.
    """

    def __init__(self, field: ui.input, gui: MyGui) -> None:
        """Read the inventory and what the field already holds; nothing is drawn until build()."""
        self.field = field
        self.gui = gui
        self.entries = appinv.apps(state=gui.state)
        known_packages = {entry.pkg for entry in self.entries}
        current = [token.strip() for token in str(field.value or "").split(",") if token.strip()]
        self.unknown = [token for token in current if token not in known_packages]
        self.chosen = {token for token in current if token in known_packages}
        self.search_text = ""

    def build(self) -> None:
        """Draw the dialog and open it."""
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
            ui.label(translate_string("Pick an Application")).classes("text-lg font-bold text-blue-600")
            ui.label(
                translate_string(
                    "The Applications named somewhere in the loaded configuration.  Tick every one this "
                    "argument should match.  Anything already in the field that isn't listed stays.",
                ),
            ).classes("text-sm text-gray-500 italic")

            # What is in the field but not in the list -- a package typed by hand, or a variable.
            # Shown because 'anything else stays' is a promise the user cannot otherwise check,
            # and because it is the only feedback that adding a variable below took effect.
            self.unlisted_label = ui.label("").classes("text-xs text-blue-600 mt-1")

            _picker_search_input(self.search_changed, "Search Applications")
            self.results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
            self.render()
            self.show_unlisted()

            with ui.row().classes("w-full items-center gap-2 mt-2"):
                ui.label(translate_string("Or a Tasker variable:")).classes("text-xs text-gray-500")
                _render_variable_entry(self.add_variable, "Add")

            with ui.row().classes("w-full justify-between items-center gap-2 mt-3"):
                _render_fetch_apps_button(self.fetch_then_reopen)
                with ui.row().classes("gap-2"):
                    ui.button(translate_string("Cancel"), on_click=self.dialog.close).props("flat")
                    ui.button(translate_string("Use Selected"), on_click=self.use_selected).props("color=primary")

        self.dialog.open()

    def show_unlisted(self) -> None:
        """Say what the field holds that the list does not."""
        self.unlisted_label.set_text(
            f"{translate_string('Also in this field')}: {', '.join(self.unknown)}" if self.unknown else "",
        )

    def toggle(self, package: str, ticked: bool) -> None:
        """Tick or untick one package."""
        if ticked:
            self.chosen.add(package)
        else:
            self.chosen.discard(package)

    def render(self) -> None:
        """Fill the list with the applications that match the search."""
        self.results.clear()
        text = self.search_text.strip().lower()
        visible = [
            entry for entry in self.entries if not text or text in entry.pkg.lower() or text in entry.label.lower()
        ]
        with self.results:
            if not visible:
                ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                return
            for entry in visible[:_PICKER_ROW_LIMIT]:
                ui.checkbox(
                    entry.display,
                    value=entry.pkg in self.chosen,
                    on_change=lambda e, pkg=entry.pkg: self.toggle(pkg, bool(e.value)),
                ).props("dense")
            if len(visible) > _PICKER_ROW_LIMIT:
                ui.label(
                    f"{translate_string('More matches than can be shown -- narrow the search.')} ({len(visible)})",
                ).classes("text-xs italic text-gray-500 mt-1")

    def search_changed(self, value: str) -> None:
        """Narrow the list to what was typed."""
        self.search_text = value
        self.render()

    def add_variable(self, name: str) -> None:
        """Keep a Tasker variable in the field alongside the ticked applications."""
        if name not in self.unknown:
            self.unknown.append(name)
        self.show_unlisted()

    def apply_selection(self) -> None:
        """Write the ticks back into the field."""
        # Inventory order for the picked ones, so the field reads the same way twice
        # running; the unrecognised ones first, where they were.
        self.field.set_value(
            ", ".join(self.unknown + [entry.pkg for entry in self.entries if entry.pkg in self.chosen])
        )

    def use_selected(self) -> None:
        """Use Selected: apply the ticks and close."""
        self.apply_selection()
        self.dialog.close()

    async def fetch_then_reopen(self) -> None:
        """Fetch the application list from the device, then reopen this picker over the new inventory."""
        # The ticks are written into the field before reopening, and the fresh dialog
        # reads its ticks back out of the field -- so a fetch part-way through choosing
        # apps does not throw away what has been chosen so far.
        self.apply_selection()
        self.dialog.close()
        await build_fetch_apps_dialog(self.gui, lambda: _build_app_picker_dialog(self.field, self.gui))


def _build_app_picker_dialog(field: ui.input, gui: MyGui) -> None:
    """Pick Applications for a field holding package names.

    Multi-select, rather than the replace-on-click of the Scene designer's icon picker
    (_build_icon_dialog): an <App> argument really can name several apps at once --
    backups in this repo carry <appPkg>com.whatsapp, com.whatsapp.w4b</appPkg> -- so
    "and this one too" is an ordinary thing to want here in a way it is not for one
    component's one icon.

    Whatever is already in the field but not in the inventory -- a package typed by hand,
    a %variable -- is kept, and put back at the front.  The picker is a convenience laid
    over the field, never a replacement for it, so it must not be able to quietly delete a
    value merely because it doesn't recognise it.
    """
    _AppPicker(field, gui).build()


def _render_fetch_apps_button(on_click: Callable[[], object], for_icons: bool = False) -> None:
    """The 'Not listed?' button the Application and icon pickers carry, in the same place
    in each.

    Worded as the question the user is actually asking at that moment.  A button labelled
    'Fetch' would be answering a question they have not thought to ask yet -- the list in
    front of them looks complete until the one app they want turns out not to be in it.

    The icon wording asks the icon question, but the button does the same thing: see
    build_fetch_apps_dialog's for_icons.
    """
    fetch_button = ui.button(
        translate_string("Icon not listed?" if for_icons else "App not listed?"),
        icon="cloud_download",
        on_click=on_click,
    ).props("flat dense color=primary")
    with fetch_button:
        ui.tooltip(
            translate_string(
                "Fetch every installed application's own icon from your Android device.  What is "
                "listed now is only the icons this configuration already uses.  Tasker's built-in "
                "icons and the contents of an icon pack cannot be fetched, and are typed by name."
                if for_icons
                else "Fetch the full list of installed applications from your Android device.  "
                "What is listed now is only what this configuration already names.",
            ),
        ).style("white-space: pre-wrap")


def _build_app_entry_picker_dialog(on_pick: Callable[[appinv.AppEntry], None], gui: MyGui) -> None:
    """Pick one Application, handing the whole triple to the caller.

    The single-pick sibling of _build_app_picker_dialog, for the Profile App condition,
    whose entries are three separate fields per app (profedit.get_app_entries) rather than
    one comma-joined list -- so what it needs back is the package, the label *and* the
    class, not just a package name to write into a field.  Filling all three is the point:
    that condition's class field is the one nobody can be expected to know by heart.
    """
    entries = appinv.apps(state=gui.state)
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an Application")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string(
                "The Applications named somewhere in the loaded configuration -- or name a Tasker "
                "variable, which fills the Package and Label fields with it and leaves the Class empty, "
                "the way Tasker writes one.",
            ),
        ).classes("text-sm text-gray-500 italic")

        def pick(entry: appinv.AppEntry) -> None:
            on_pick(entry)
            dialog.close()

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower()
            visible = [
                entry for entry in entries if not text or text in entry.pkg.lower() or text in entry.label.lower()
            ]
            with results:
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                for entry in visible[:_PICKER_ROW_LIMIT]:
                    ui.button(
                        entry.display,
                        on_click=lambda _e=None, chosen=entry: pick(chosen),
                    ).props("flat dense no-caps align=left").classes("w-full")

        def search_changed(value: str) -> None:
            search["text"] = value
            render()

        _picker_search_input(search_changed, "Search Applications")
        results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
        render()

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.label(translate_string("Or a Tasker variable:")).classes("text-xs text-gray-500")
            _render_variable_entry(lambda name: pick(appinv.variable_app_entry(name)), "Use")

        async def fetch_then_reopen() -> None:
            dialog.close()
            await build_fetch_apps_dialog(gui, lambda: _build_app_entry_picker_dialog(on_pick, gui))

        with ui.row().classes("w-full justify-between items-center mt-3"):
            _render_fetch_apps_button(fetch_then_reopen)
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


def render_app_entry_pick_button(
    gui: MyGui,
    field_refs: dict[str, ui.input],
    pkg_key: str,
    label_key: str,
    cls_key: str,
) -> None:
    """The 'Pick' button beside one App condition entry's Package/Label/Class fields.

    Writes into the three inputs rather than into the condition, exactly like every other
    field in that dialog: Save reads field_refs, so a picked app is staged and cancellable
    on the same terms as a typed one.  Absent entirely when there is nothing to pick from,
    which leaves the three fields precisely as they were before this existed.
    """
    if not appinv.have_apps(state=gui.state):
        return

    def fill_in(entry: appinv.AppEntry) -> None:
        field_refs[pkg_key].value = entry.pkg
        field_refs[label_key].value = entry.label
        field_refs[cls_key].value = entry.cls

    pick_button = ui.button(
        translate_string("Pick"),
        icon="apps",
        on_click=lambda: _build_app_entry_picker_dialog(fill_in, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(translate_string("Fill all three fields in from the loaded configuration."))


def build_tasker_icon_picker_dialog(field: ui.input, gui: MyGui) -> None:
    """Pick one icon for a field holding an <Img> reference.

    Replaces what the field holds rather than adding to it -- an action has one icon, so a
    second pick is a correction.  'No icon' is offered explicitly: an empty <Img> is what
    an action whose icon was never set has always carried, and it has to stay reachable
    once a picker exists.
    """
    icons = appinv.icons(state=gui.state)
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
        ui.label(translate_string("Pick an icon")).classes("text-lg font-bold text-blue-600")
        ui.label(
            translate_string(
                "The icons used somewhere in the loaded configuration, plus every application's own "
                "icon if you have fetched them from your device.  What you pick replaces what the "
                "field holds.  An icon from an icon pack that isn't listed has to be typed: its "
                "names live inside the pack.",
            ),
        ).classes("text-sm text-gray-500 italic")

        def pick(value: str) -> None:
            field.set_value(value)
            dialog.close()

        def render() -> None:
            results.clear()
            text = search["text"].strip().lower()
            visible = [
                icon
                for icon in icons
                if not text or text in icon.display.lower() or text in appinv.format_icon_value(icon).lower()
            ]
            with results:
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                for icon in visible[:_PICKER_ROW_LIMIT]:
                    reference = appinv.format_icon_value(icon)
                    with ui.row().classes("w-full items-center gap-2 no-wrap"):
                        ui.icon(_tasker_icon_glyph(icon)).style(_ICON_GLYPH_STYLE).classes("text-gray-700")
                        ui.button(
                            icon.display,
                            on_click=lambda _e=None, value=reference: pick(value),
                        ).props("flat dense no-caps align=left").classes("flex-1")
                        # pr-4 keeps the kind clear of the list's own scrollbar, which
                        # otherwise sits on top of it and clips the word.
                        ui.label(icon.kind).classes("text-xs text-gray-500 w-20 text-right pr-4")
                if len(visible) > _PICKER_ROW_LIMIT:
                    ui.label(
                        f"{translate_string('More matches than can be shown -- narrow the search.')} ({len(visible)})",
                    ).classes("text-xs italic text-gray-500 mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value
            render()

        _picker_search_input(search_changed, "Search icons")
        results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
        render()

        async def fetch_then_reopen() -> None:
            # Closed and reopened rather than re-rendered in place, exactly as the
            # Application picker does it: the list is read once, at the top of this
            # function, and a fetch is precisely the thing that makes that reading stale.
            dialog.close()
            await build_fetch_apps_dialog(gui, lambda: build_tasker_icon_picker_dialog(field, gui), for_icons=True)

        with ui.row().classes("w-full justify-between items-center gap-2 mt-3"):
            _render_fetch_apps_button(fetch_then_reopen, for_icons=True)
            with ui.row().classes("gap-2"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")
                temp = ui.button(translate_string("No Icon"), on_click=lambda: pick("")).props("flat color=negative")
                temp.tooltip(translate_string("Clear the field, leaving the action with no icon."))

    dialog.open()


def _render_inventory_fetch(gui: MyGui, reason: str, on_fetched: Callable[[], None]) -> None:
    """The fetch button, for the two refusals a fetch from the device can lift.

    'No Applications were found...' and 'No icons were found...' are the only two things
    the editor says no to that the user can do something about without leaving the dialog,
    and one fetch answers both: the Application list the device sends back is also a list
    of app icons (appinv._merged_with_device_icons).  Every other refusal is a statement
    about the action itself and gets no button, which is why this is an equality test
    against taskedit's two named constants rather than a guess at the wording.

    on_fetched re-draws whatever showed the refusal.  A fetch bumps deviceinv's generation,
    so a re-draw is enough for the caller that re-asks the question -- see
    taskedit_addable.list_addable_actions' memo, and reclassify_action_args for the callers whose
    models were built before the fetch and have to be rebuilt rather than merely redrawn.
    """
    if reason not in (taskedit_model.NO_APPS_REASON, taskedit_model.NO_ICONS_REASON):
        return
    for_icons = reason == taskedit_model.NO_ICONS_REASON

    async def fetch() -> None:
        await build_fetch_apps_dialog(gui, on_fetched, for_icons=for_icons)

    _render_fetch_apps_button(fetch, for_icons=for_icons)


def after_inventory_fetch(
    redraw: Callable[[], None], action: taskedit_model.EditableAction, state: RunState
) -> Callable[[], None]:
    """What to do once a fetch has filled the inventory: re-ask this action's arguments
    what kind of widget they are, and then draw them again.

    Re-drawing alone would not do it.  A read-only App or Icon field is read-only because
    _classify_arg_widget said so when the model was built, and that answer is kept in the
    EditableArg -- so without the rebuild the field would come back grey, still carrying a
    reason that had just stopped being true.
    """

    def refresh() -> None:
        taskedit_args.reclassify_action_args(action, state=state)
        redraw()

    return refresh


def after_condition_fetch(
    redraw: Callable[[], None],
    condition: profedit.EditableCondition,
    state: RunState,
) -> Callable[[], None]:
    """after_inventory_fetch's counterpart for a Profile State/Event condition's arguments."""

    def refresh() -> None:
        profedit.reclassify_condition_args(condition, state=state)
        redraw()

    return refresh


def render_readonly_note(gui: MyGui, note: str, on_fetched: Callable[[], None]) -> None:
    """The italic note beside an argument that cannot be edited -- and, when the note is one
    of the two a fetch can lift, the fetch beside it.

    This is where 'No icons were found in the loaded configuration to choose from.' is most
    often read: not in the Add Action picker, but on a greyed-out Icon field in an action
    that is already there.  Until now it was a dead end wherever it appeared, and the way
    out existed only inside a picker the empty inventory stopped from opening.
    """
    ui.label(note).classes("text-xs text-gray-500 italic")
    _render_inventory_fetch(gui, note, on_fetched)


def render_addability_reason(gui: MyGui, reason: str, on_fetched: Callable[[], None]) -> None:
    """Why an action can't be added -- and, for the one reason that has a way out, the way
    out.

    'No Applications were found in the loaded configuration to choose from' and its icon
    counterpart are the refusals a user can do something about without leaving this dialog,
    and until now each was a dead end in the most literal way: with nothing in the
    inventory, 'Launch App' is not addable, so the picker never opens, so the picker's own
    'not listed?' button -- the thing that would fix it -- could not be reached.  Same
    button, same fetch, offered at the point where the user actually hits the wall.

    on_fetched re-runs whatever drew this row.  A fetch bumps deviceinv's generation, which
    is what makes taskedit_addable.list_addable_actions rebuild rather than answer from its memo,
    so re-running the picker is all it takes for the greyed-out row to turn into a button.
    """
    ui.label(reason).classes("text-xs text-gray-500 italic")
    _render_inventory_fetch(gui, reason, on_fetched)


def render_app_arg_field(
    gui: MyGui,
    arg: taskedit_model.EditableArg,
    key: str,
    field_refs: dict[str, ui.input],
    value: str | None = None,
) -> None:
    """An App argument: an ordinary text input holding the package names, and a button
    that opens the picker beside it.

    Typed into as well as picked from, for the same reason _build_icon_field is: an
    <appPkg> is legitimately a %variable, and the inventory only knows the apps this
    configuration already names.  What is typed is what is saved -- Save reads the text
    input's own field_refs entry and nothing else, and the picker's only power is to write
    into it (the same either/or as _render_task_name_field).
    """
    field_refs[key] = ui.input(
        translate_string(arg.arg_name),
        value=arg.current_value if value is None else value,
    ).classes("flex-1")
    pick_button = ui.button(
        translate_string("Pick"),
        icon="apps",
        on_click=lambda _e=None, f=field_refs[key]: _build_app_picker_dialog(f, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(translate_string("Choose from the Applications named in the loaded configuration."))


def render_icon_arg_field(
    gui: MyGui,
    arg: taskedit_model.EditableArg,
    key: str,
    field_refs: dict[str, ui.input],
    value: str | None = None,
) -> None:
    """An Icon argument: the same two-widget arrangement as render_app_arg_field, holding
    one icon reference -- see appinv.format_icon_value for how each of the four kinds of
    one is spelled into a single field.
    """
    field_refs[key] = ui.input(
        translate_string(arg.arg_name),
        value=arg.current_value if value is None else value,
    ).classes("flex-1")
    pick_button = ui.button(
        translate_string("Pick"),
        icon="image",
        on_click=lambda _e=None, f=field_refs[key]: build_tasker_icon_picker_dialog(f, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(
            translate_string(
                "Choose from the icons used in the loaded configuration, and from your device's "
                "applications if you have fetched them.",
            ),
        )
