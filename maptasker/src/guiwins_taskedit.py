"""The Task editor: the Edit/Add/Delete Task dialogs and the action editor behind them.

Split out of guiwins.py, which had grown to 14,500 lines.  This is everything an Action is
edited through -- _build_task_action_editor and the field widgets it dispatches to, the
Application and Tasker-icon pickers those fields open, and the condition/If-variant dialogs
an Action's own logic is built with.

The Profile editor reuses the argument fields here (a Profile's state and event conditions
are built out of the same <Arg> shapes an Action is), so guiwins_profedit imports from this
module; nothing here imports from there.

Its three calls back into guiwins -- editor_state, PendingChangesBanner and the Properties
button -- are made inside the functions that need them, because guiwins imports this module
at the top of its own file and a module-level import here would close the loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import run, ui

from maptasker.src import deviceinv, objprops, profedit, taskedit
from maptasker.src.maputil2 import translate_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.userintr import MyGui


def _refresh_position_options(
    edited_task: taskedit.EditableTask,
    position_select: ui.select,
    position_labels: dict[str, int | None],
) -> None:
    """Rebuilds an Add/Edit Task dialog's "Position" dropdown from the task's
    current actions -- called after every Add/Copy/Move/Delete/Remove, since
    act_numbers and names shift and stale labels would insert at the wrong
    spot. Keeps the user's current choice if it still exists, else falls back
    to "At the End". position_labels maps each label to the act_number to
    insert at (None for "At the End") -- see build_edit_task_dialog's note on
    why that map is kept out-of-band.
    """
    position_labels.clear()
    options = []
    for action in edited_task.actions:
        before_label = f"Before {action.act_number}: {action.action_name}"
        after_label = f"After {action.act_number}: {action.action_name}"
        position_labels[before_label] = action.act_number
        position_labels[after_label] = action.act_number + 1
        options.extend((before_label, after_label))
    options.append("At the End")
    position_labels["At the End"] = None
    previous = position_select.value
    position_select.set_options(options, value=previous if previous in options else "At the End")


def _action_indent_spaces(self: MyGui) -> int:
    """The user's "If/Then/Else Indentation Amount" setting as an int (default
    4) -- the same amount the Map view indents If blocks by. Restored settings
    can hold it as a string, hence the coercion.
    """
    try:
        return int(getattr(self, "indent", 4) or 4)
    except (TypeError, ValueError):
        return 4


def _dropdown_current_label(arg: taskedit.EditableArg) -> str:
    """The option to preselect for a dropdown arg: current_value is the index
    into dropdown_options (If Operator, Int lookups -- every dropdown in this
    codebase).
    """
    options = arg.dropdown_options or []
    try:
        return options[int(arg.current_value)]
    except (ValueError, IndexError):
        return options[0] if options else ""


def _render_task_name_field(
    _self: MyGui,
    _action: taskedit.EditableAction,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
) -> None:
    """Renders the 'Perform Task' action's Name field: an ordinary text input
    the user can key any string into, plus a companion "Pick a Task" dropdown
    that -- when an option is chosen -- overwrites the text input with that
    Task's name. Either/or: whichever the user touches last is what's saved,
    since Save only ever reads the text input's own field_refs entry (this
    dropdown is deliberately never added to field_refs, so _task_arg_values
    can't see it).

    A plain ui.select with Quasar's "new-value-mode" was tried first so a
    single widget could both pick and free-type, but it only accepts a typed
    value when the user presses Enter -- clicking away (the far more likely
    action) silently reverts the field to its first option, which is exactly
    the "grabs the first task" bug this two-widget design avoids entirely.
    """
    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")

    task_names = taskedit.get_all_task_names()
    if not task_names:
        return

    def fill_in_picked_task(e: ui.event) -> None:
        if e.value:
            field_refs[key].value = e.value

    ui.select(
        task_names,
        label=translate_string("Pick a Task"),
        with_input=True,
        on_change=fill_in_picked_task,
    ).classes("flex-1").props("dense").tooltip(translate_string("Pick a Task which will be called by this action."))


# How many rows either pick-from-the-inventory dialog draws at once.  A real backup
# harvests ~50 Applications and ~140 icons (see deviceinv.py), but a large configuration
# holds more, and the list is rebuilt on every keystroke of the search box -- the same
# reasoning behind _ICON_PREVIEW_LIMIT, which the Scene designer's own picker uses.
_PICKER_ROW_LIMIT = 200


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


async def _build_fetch_apps_dialog(gui: MyGui, on_fetched: Callable[[], None], for_icons: bool = False) -> None:
    """Ask an Android device for the full list of installed Applications.

    Offered from inside the Application pickers rather than from the sidebar, because
    inside them is where the gap is felt: the list holds what this configuration already
    names, and the moment a user notices the app they want is missing is the moment they
    are looking at it.

    Prompts for the device the same way every other Save To Android does
    (build_save_to_android_dialog), defaults from the same remembered address, and writes
    the address back on success so the next one is pre-filled.

    The fetch itself installs a helper Task on the device, runs it, and waits for the file
    it writes -- seconds, not milliseconds -- so it goes through run.io_bound and the
    button says what it is doing while it happens.  See deviceinv.fetch_apps_from_device.

    for_icons says the user came here wanting icons rather than Applications, which changes
    what this says and nothing about what it does.  It is the same fetch either way: an
    app's own icon is its package plus its launcher activity, so the Application list is an
    icon list too (deviceinv._merged_with_device_icons).  Saying so is the point -- a dialog
    headed "Fetch Applications" in answer to "there are no icons" looks like the wrong
    button, and the two kinds of icon the fetch cannot bring back have to be said out loud
    rather than left to be discovered in the picker afterwards.

    Deliberately does NOT pre-flight with guiutils.ping_android_device, which every other
    Android dialog here does.  That probe used to be disqualifying -- it was a GET on the
    'maplist' route, served by the 'MapTasker List' TaskerNet profile rather than by the
    HTTP Server Example project, so a user who had the server running but had never
    imported that profile failed it despite needing nothing it tested.  The probe no longer
    depends on that profile (nothing does), but skipping it is still the better answer
    here: this fetch's own first step is a GET /api/auth against the very API it goes on to
    use, which is both the right thing to test and the thing whose failure message is worth
    showing.
    """
    default_ip = getattr(gui, "android_ipaddr", "") or "192.168.0.210"
    default_port = getattr(gui, "android_port", "") or "1821"

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[460px] p-6"):
        title = "Fetch Icons From Android Device" if for_icons else "Fetch Applications From Android Device"
        ui.label(translate_string(title)).classes("text-lg font-bold text-blue-600")
        if for_icons:
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
                "with the 'HTTP Server Example' project active -- the same requirement 'Save to Android' has.",
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

        for device, when, count in deviceinv.fetched_devices():
            ui.label(f"{device}: {count} {translate_string('applications, fetched')} {when}").classes(
                "text-xs text-gray-500 mt-1",
            )

        ip_field = ui.input(translate_string("Android IP Address"), value=default_ip).classes("w-full")
        port_field = ui.input(translate_string("Port"), value=default_port).classes("w-full")

        # Hidden until the fetch starts.  The button going grey and saying 'Fetching...' is
        # not enough on its own: what the user has to do next is happening on the phone, not
        # here, and nothing on this screen would otherwise say to go and look at it.
        progress_row = ui.row().classes("w-full items-center gap-2 mt-3")
        progress_row.set_visibility(False)
        with progress_row:
            ui.spinner(size="sm")
            ui.label(
                translate_string(
                    "Waiting on the Android device -- accept the authorization prompt there if one "
                    "appears.  This can take 30 seconds or more.",
                ),
            ).classes("text-sm text-amber-700 dark:text-amber-500")

        async def fetch() -> None:
            ip_address = str(ip_field.value or "").strip()
            ip_port = str(port_field.value or "").strip()

            fetch_button.set_text(translate_string("Fetching..."))
            fetch_button.set_enabled(False)
            progress_row.set_visibility(True)
            try:
                return_code, message = await run.io_bound(deviceinv.fetch_apps_from_device, ip_address, ip_port)
            finally:
                fetch_button.set_text(translate_string("Fetch"))
                fetch_button.set_enabled(True)
                progress_row.set_visibility(False)

            if return_code != 0:
                ui.notify(message, type="negative", timeout=8000)
                return

            # Remembered for next time, same as the Get XML and Save To Android dialogs do.
            gui.android_ipaddr = ip_address
            gui.android_port = ip_port
            ui.notify(message, type="positive", timeout=6000)
            dialog.close()
            on_fetched()

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            fetch_button = ui.button(translate_string("Fetch"), on_click=fetch).classes("bg-blue-600")
            fetch_button.tooltip(
                translate_string("Fetch the full list of installed Applications from the Android device."),
            )

    dialog.open()


def _render_variable_entry(on_variable: Callable[[str], None], button_text: str) -> None:
    """A row for naming a Tasker variable instead of an installed application.

    An <appPkg> is legitimately a variable -- this repo's own backup has eleven of them,
    including '%app_package(%ld_selected_index)' -- and until now the only way to say so was
    to close the picker and type into the field behind it.  The field is still there and
    still works; this just means the picker no longer has to be got out of the way first.

    Validation is deviceinv.is_variable_reference: a leading '%' and something after it, and
    nothing more, since what follows the '%' can be an array index or a function call and is
    Tasker's business rather than this tool's.
    """
    variable_input = ui.input(placeholder=translate_string("%variable_name")).props("outlined dense").classes("flex-1")

    def use_variable() -> None:
        text = str(variable_input.value or "").strip()
        if not deviceinv.is_variable_reference(text):
            ui.notify(
                translate_string("A variable name has to start with '%' -- for example %app_package."),
                type="warning",
            )
            return
        on_variable(text)
        variable_input.set_value("")

    variable_input.on("keydown.enter", use_variable)
    ui.button(translate_string(button_text), on_click=use_variable).props("flat dense color=primary")


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
    entries = deviceinv.apps()
    known_packages = {entry.pkg for entry in entries}
    current = [token.strip() for token in str(field.value or "").split(",") if token.strip()]
    unknown = [token for token in current if token not in known_packages]
    chosen = {token for token in current if token in known_packages}
    search = {"text": ""}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[560px] max-w-[760px] p-6"):
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
        unlisted_label = ui.label("").classes("text-xs text-blue-600 mt-1")

        def show_unlisted() -> None:
            unlisted_label.set_text(
                f"{translate_string('Also in this field')}: {', '.join(unknown)}" if unknown else "",
            )

        def toggle(package: str, ticked: bool) -> None:
            if ticked:
                chosen.add(package)
            else:
                chosen.discard(package)

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
                    ui.checkbox(
                        entry.display,
                        value=entry.pkg in chosen,
                        on_change=lambda e, pkg=entry.pkg: toggle(pkg, bool(e.value)),
                    ).props("dense")
                if len(visible) > _PICKER_ROW_LIMIT:
                    ui.label(
                        f"{translate_string('More matches than can be shown -- narrow the search.')} ({len(visible)})",
                    ).classes("text-xs italic text-gray-500 mt-1")

        def search_changed(value: str) -> None:
            search["text"] = value
            render()

        _picker_search_input(search_changed, "Search Applications")
        results = ui.column().classes("w-full gap-0 mt-2 max-h-96 overflow-auto")
        render()
        show_unlisted()

        def add_variable(name: str) -> None:
            if name not in unknown:
                unknown.append(name)
            show_unlisted()

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.label(translate_string("Or a Tasker variable:")).classes("text-xs text-gray-500")
            _render_variable_entry(add_variable, "Add")

        def apply_selection() -> None:
            # Inventory order for the picked ones, so the field reads the same way twice
            # running; the unrecognised ones first, where they were.
            field.set_value(", ".join(unknown + [entry.pkg for entry in entries if entry.pkg in chosen]))

        def use_selected() -> None:
            apply_selection()
            dialog.close()

        async def fetch_then_reopen() -> None:
            # The ticks are written into the field before reopening, and the fresh dialog
            # reads its ticks back out of the field -- so a fetch part-way through choosing
            # apps does not throw away what has been chosen so far.
            apply_selection()
            dialog.close()
            await _build_fetch_apps_dialog(gui, lambda: _build_app_picker_dialog(field, gui))

        with ui.row().classes("w-full justify-between items-center gap-2 mt-3"):
            _render_fetch_apps_button(fetch_then_reopen)
            with ui.row().classes("gap-2"):
                ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")
                ui.button(translate_string("Use Selected"), on_click=use_selected).props("color=primary")

    dialog.open()


def _render_fetch_apps_button(on_click: Callable[[], object], for_icons: bool = False) -> None:
    """The 'Not listed?' button the Application and icon pickers carry, in the same place
    in each.

    Worded as the question the user is actually asking at that moment.  A button labelled
    'Fetch' would be answering a question they have not thought to ask yet -- the list in
    front of them looks complete until the one app they want turns out not to be in it.

    The icon wording asks the icon question, but the button does the same thing: see
    _build_fetch_apps_dialog's for_icons.
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


def _build_app_entry_picker_dialog(on_pick: Callable[[deviceinv.AppEntry], None], gui: MyGui) -> None:
    """Pick one Application, handing the whole triple to the caller.

    The single-pick sibling of _build_app_picker_dialog, for the Profile App condition,
    whose entries are three separate fields per app (profedit.get_app_entries) rather than
    one comma-joined list -- so what it needs back is the package, the label *and* the
    class, not just a package name to write into a field.  Filling all three is the point:
    that condition's class field is the one nobody can be expected to know by heart.
    """
    entries = deviceinv.apps()
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

        def pick(entry: deviceinv.AppEntry) -> None:
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
            _render_variable_entry(lambda name: pick(deviceinv.variable_app_entry(name)), "Use")

        async def fetch_then_reopen() -> None:
            dialog.close()
            await _build_fetch_apps_dialog(gui, lambda: _build_app_entry_picker_dialog(on_pick, gui))

        with ui.row().classes("w-full justify-between items-center mt-3"):
            _render_fetch_apps_button(fetch_then_reopen)
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("flat")

    dialog.open()


def _render_app_entry_pick_button(
    gui: MyGui,
    field_refs: dict,
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
    if not deviceinv.have_apps():
        return

    def fill_in(entry: deviceinv.AppEntry) -> None:
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


def _build_tasker_icon_picker_dialog(field: ui.input, gui: MyGui) -> None:
    """Pick one icon for a field holding an <Img> reference.

    Replaces what the field holds rather than adding to it -- an action has one icon, so a
    second pick is a correction.  'No icon' is offered explicitly: an empty <Img> is what
    an action whose icon was never set has always carried, and it has to stay reachable
    once a picker exists.
    """
    icons = deviceinv.icons()
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
                if not text or text in icon.display.lower() or text in deviceinv.format_icon_value(icon).lower()
            ]
            with results:
                if not visible:
                    ui.label(translate_string("Nothing here.")).classes("text-sm italic text-gray-500")
                    return
                for icon in visible[:_PICKER_ROW_LIMIT]:
                    reference = deviceinv.format_icon_value(icon)
                    with ui.row().classes("w-full items-center gap-2"):
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
            await _build_fetch_apps_dialog(gui, lambda: _build_tasker_icon_picker_dialog(field, gui), for_icons=True)

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
    of app icons (deviceinv._merged_with_device_icons).  Every other refusal is a statement
    about the action itself and gets no button, which is why this is an equality test
    against taskedit's two named constants rather than a guess at the wording.

    on_fetched re-draws whatever showed the refusal.  A fetch bumps deviceinv's generation,
    so a re-draw is enough for the caller that re-asks the question -- see
    taskedit.list_addable_actions' memo, and reclassify_action_args for the callers whose
    models were built before the fetch and have to be rebuilt rather than merely redrawn.
    """
    if reason not in (taskedit.NO_APPS_REASON, taskedit.NO_ICONS_REASON):
        return
    for_icons = reason == taskedit.NO_ICONS_REASON

    async def fetch() -> None:
        await _build_fetch_apps_dialog(gui, on_fetched, for_icons=for_icons)

    _render_fetch_apps_button(fetch, for_icons=for_icons)


def _after_inventory_fetch(redraw: Callable[[], None], action: taskedit.EditableAction) -> Callable[[], None]:
    """What to do once a fetch has filled the inventory: re-ask this action's arguments
    what kind of widget they are, and then draw them again.

    Re-drawing alone would not do it.  A read-only App or Icon field is read-only because
    _classify_arg_widget said so when the model was built, and that answer is kept in the
    EditableArg -- so without the rebuild the field would come back grey, still carrying a
    reason that had just stopped being true.
    """

    def refresh() -> None:
        taskedit.reclassify_action_args(action)
        redraw()

    return refresh


def _after_condition_fetch(
    redraw: Callable[[], None],
    condition: profedit.EditableCondition,
) -> Callable[[], None]:
    """_after_inventory_fetch's counterpart for a Profile State/Event condition's arguments."""

    def refresh() -> None:
        profedit.reclassify_condition_args(condition)
        redraw()

    return refresh


def _render_readonly_note(gui: MyGui, note: str, on_fetched: Callable[[], None]) -> None:
    """The italic note beside an argument that cannot be edited -- and, when the note is one
    of the two a fetch can lift, the fetch beside it.

    This is where 'No icons were found in the loaded configuration to choose from.' is most
    often read: not in the Add Action picker, but on a greyed-out Icon field in an action
    that is already there.  Until now it was a dead end wherever it appeared, and the way
    out existed only inside a picker the empty inventory stopped from opening.
    """
    ui.label(note).classes("text-xs text-gray-500 italic")
    _render_inventory_fetch(gui, note, on_fetched)


def _render_addability_reason(gui: MyGui, reason: str, on_fetched: Callable[[], None]) -> None:
    """Why an action can't be added -- and, for the one reason that has a way out, the way
    out.

    'No Applications were found in the loaded configuration to choose from' and its icon
    counterpart are the refusals a user can do something about without leaving this dialog,
    and until now each was a dead end in the most literal way: with nothing in the
    inventory, 'Launch App' is not addable, so the picker never opens, so the picker's own
    'not listed?' button -- the thing that would fix it -- could not be reached.  Same
    button, same fetch, offered at the point where the user actually hits the wall.

    on_fetched re-runs whatever drew this row.  A fetch bumps deviceinv's generation, which
    is what makes taskedit.list_addable_actions rebuild rather than answer from its memo,
    so re-running the picker is all it takes for the greyed-out row to turn into a button.
    """
    ui.label(reason).classes("text-xs text-gray-500 italic")
    _render_inventory_fetch(gui, reason, on_fetched)


def _render_app_arg_field(
    gui: MyGui,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
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


def _render_icon_arg_field(
    gui: MyGui,
    arg: taskedit.EditableArg,
    key: str,
    field_refs: dict,
    value: str | None = None,
) -> None:
    """An Icon argument: the same two-widget arrangement as _render_app_arg_field, holding
    one icon reference -- see deviceinv.format_icon_value for how each of the four kinds of
    one is spelled into a single field.
    """
    field_refs[key] = ui.input(
        translate_string(arg.arg_name),
        value=arg.current_value if value is None else value,
    ).classes("flex-1")
    pick_button = ui.button(
        translate_string("Pick"),
        icon="image",
        on_click=lambda _e=None, f=field_refs[key]: _build_tasker_icon_picker_dialog(f, gui),
    ).props("flat dense size=sm")
    with pick_button:
        ui.tooltip(
            translate_string(
                "Choose from the icons used in the loaded configuration, and from your device's "
                "applications if you have fetched them.",
            ),
        )


def build_action_condition_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    act_number: int,
    checkbox: ui.checkbox,
    condition_cache: dict[int, tuple[str, str, str]],
) -> None:
    """Prompts for a per-action If condition (Target/Operator/Value) when the
    action's "If" checkbox is checked -- see _render_action_condition_checkbox.
    Prefills from the values cached by the last uncheck (so toggling off and
    on edits rather than starts over), else from the action's current XML. Ok
    validates and writes the <ConditionList> (dialog stays open on errors);
    Cancel unchecks the checkbox, adding nothing.
    """
    action = next((a for a in edited_task.actions if a.act_number == act_number), None)
    if action is None:
        return

    prefill = condition_cache.get(act_number) or taskedit.get_action_condition_values(action)
    operator_labels = [label for _code, label in taskedit.IF_CONDITION_OPERATORS]

    with ui.dialog().props("persistent") as condition_dialog, ui.card().classes("min-w-[400px] p-6"):
        ui.label(f"If Condition -- {act_number}: {action.action_name}").classes("text-lg font-bold text-blue-600")
        target_input = ui.input(translate_string("Target"), value=prefill[0]).classes("w-full")
        operator_select = ui.select(
            operator_labels,
            value=prefill[1] if prefill[1] in operator_labels else operator_labels[0],
            label=translate_string("Operator"),
        ).classes("w-full")
        value_input = ui.input(translate_string("Value"), value=prefill[2]).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(
                translate_string("Cancel"),
                on_click=lambda: (condition_dialog.close(), checkbox.set_value(False)),
            ).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.set_action_condition_event(
                    edited_task,
                    act_number,
                    target_input,
                    operator_select,
                    value_input,
                    condition_dialog,
                    checkbox,
                ),
            ).classes("bg-blue-600")

    condition_dialog.open()


def _render_action_condition_checkbox(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    action: taskedit.EditableAction,
    condition_cache: dict[int, tuple[str, str, str]],
) -> None:
    """Renders an action's per-action "If" checkbox in the Add/Edit Task action
    lists (every action except the 'If' action itself -- callers skip that).
    Checked state mirrors whether the action currently has a <ConditionList>;
    checking prompts for the condition (build_action_condition_dialog),
    unchecking removes it (stashing its values in condition_cache so a
    re-check prefills them). An action with multiple chained conditions gets a
    read-only note instead -- replacing those from this single-condition
    prompt would silently drop the rest.
    """
    condition_count = taskedit.action_condition_count(action)
    if condition_count > 1:
        ui.label(
            f"Has {condition_count} chained If conditions -- not editable here.",
        ).classes("text-xs text-gray-500 italic")
        return

    target, operator_label, value = taskedit.get_action_condition_values(action)
    text = f"If: {target} {operator_label} {value}".rstrip() if condition_count else "If"
    checkbox = ui.checkbox(text, value=condition_count == 1).props("dense")

    def on_toggle(e: ui.event, act_number: str = action.act_number, cb: ui.checkbox = checkbox) -> None:
        if e.value:
            build_action_condition_dialog(self, edited_task, act_number, cb, condition_cache)
            return
        current = next((a for a in edited_task.actions if a.act_number == act_number), None)
        if current is not None and taskedit.action_has_condition(current):
            condition_cache[act_number] = taskedit.get_action_condition_values(current)
        self.event_handlers.remove_action_condition_event(edited_task, act_number)
        cb.set_text(translate_string("If"))

    checkbox.on_value_change(on_toggle)


def _render_continue_after_error_checkbox(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    action: taskedit.EditableAction,
) -> None:
    """Renders an action's 'Continue Task After Error' checkbox in the Add/Edit
    Task action lists -- only for actions Tasker considers able to fail
    (actionc.py's canfail flag, see taskedit.action_can_fail). Checked writes
    <se>false</se> on the action; unchecking removes the element (Tasker's
    stop-on-error default). Applied immediately, same as the Enabled switch.
    """
    if not taskedit.action_can_fail(action):
        return

    ui.checkbox(
        translate_string("Continue Task After Error"),
        value=taskedit.action_continues_after_error(action),
        on_change=lambda e, n=action.act_number: self.event_handlers.set_action_continue_after_error_event(
            edited_task,
            n,
            e.value,
        ),
    ).props("dense")


def _render_plugin_configuration_warning(element: object, name: str) -> None:
    """Renders the standing "configure this in Tasker" warning on an action's or a
    condition's own panel, for a third-party plugin whose payload this tool can't
    edit -- nothing at all for anything else (see
    taskedit.tasker_configuration_warning). Shown in all three action/condition
    lists (Edit Task, Add Task, Edit Profile's State/Event conditions), whether the
    item was just added from bundle.py or read from the loaded backup.
    """
    warning = taskedit.tasker_configuration_warning(element, name)
    if not warning:
        return

    with ui.row().classes(
        "w-full items-center gap-2 p-2 mb-1 rounded bg-amber-100 dark:bg-amber-900 border border-amber-400",
    ):
        ui.icon("warning").classes("text-amber-700 dark:text-amber-300")
        ui.label(warning).classes("text-xs text-amber-900 dark:text-amber-100")


def build_if_variant_dialog(on_choice: Callable[[str], None]) -> None:
    """Prompts for how much of an If block to insert when the user picks the
    "If" action in an Add/Edit Task action picker: just the "If", "If" plus a
    matching "End If", or a full "If"/"Else"/"End If" skeleton -- see
    taskedit.IF_BLOCK_VARIANTS/add_if_block_to_task. Fires on_choice(variant)
    only when one is clicked; Cancel inserts nothing.
    """
    with ui.dialog().props("persistent") as variant_dialog, ui.card().classes("min-w-[300px] p-6"):
        ui.label(translate_string("Add 'If' Action")).classes("text-lg font-bold text-blue-600")
        ui.label(translate_string("Insert just the 'If', or a complete block?")).classes("text-sm mb-2")
        for variant in taskedit.IF_BLOCK_VARIANTS:
            ui.button(
                variant,
                on_click=lambda v=variant: (variant_dialog.close(), on_choice(v)),
            ).classes("w-full")
        with ui.row().classes("w-full justify-end mt-2"):
            ui.button(translate_string("Cancel"), on_click=variant_dialog.close).props("outline")

    variant_dialog.open()


def _build_task_action_editor(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    field_refs: dict,
    *,
    list_classes: str = "w-full h-96 border rounded p-2",
) -> Callable[[], None]:
    """The Task action editor: an "Add an action" search/filter picker that can insert the
    new action before/after any existing one or at the end, per-action Copy/Move/Delete, an
    Enabled switch, and the values of each action's existing arguments.

    LIFTED OUT OF build_edit_task_dialog, which is still its main caller and whose layout
    it reproduces exactly; the Scene Properties KEY tab renders the same editor over the
    Task a Legacy Scene fires on an event (see _render_scene_event_task_actions), and a copy
    of two hundred lines is not a thing to keep in step by hand.  Everything it builds goes
    into the container that is open when it is called, so a caller places it by calling it
    in the right place.

    WHAT LANDS WHEN.  Adding, copying, moving, deleting, enabling and the If condition are
    written straight onto edited_task -- the working copy -- as they are done.  Argument
    values and labels are NOT: they sit in the widgets recorded in field_refs until
    something reads them back (userintr._task_arg_values) and applies them.  That split is
    the Edit Task dialog's, and every caller inherits it, so each needs its own Ok/Apply.

    field_refs gains one entry per editable argument and label, keyed by taskedit.arg_key/
    label_key, and its "act*" keys are cleared and rebuilt on every re-render -- Copy, Move
    and Delete all renumber the actions, so a stale key would apply a value to the wrong one.

    Returns render_actions, so a caller that changes the Task underneath the editor can
    redraw the list.
    """
    # Last-known per-action If condition values, keyed by act_number -- lets an
    # uncheck/re-check of the "If" checkbox edit instead of starting over.
    condition_cache: dict[int, tuple[str, str, str]] = {}
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})
    # Maps each "Position" dropdown label to the act_number to insert at (None
    # for "At the End") -- kept out-of-band rather than as the ui.select's own
    # value/options dict, since "Before N" and "After N-1" resolve to the exact
    # same act_number and a dict's keys (which NiceGUI's dict-options form uses
    # as the value) must be unique, but the two need to stay distinct, readable
    # menu entries.
    position_labels: dict[str, int | None] = {}

    ui.label(translate_string("Add an action")).classes("text-sm font-bold mt-2")
    with ui.row().classes("w-full gap-4"):
        search_input = ui.input(translate_string("Search actions")).classes("flex-1")
        category_select = ui.select(["All", *category_names], value="All").classes("w-48")
    position_select = (
        ui.select([], label=translate_string("Position"), with_input=True).classes("w-full").props("dense")
    )

    picker_container = ui.column().classes("w-full")
    ui.label(translate_string("Actions in this Task")).classes("text-sm font-bold mt-2")
    actions_container = ui.column().classes("w-full")
    # act_number of the action most recently added in this dialog session --
    # render_actions highlights it so it's easy to spot in a long list.
    last_added_act_number: int | None = None

    def clear_last_added() -> None:
        # Copy/Move/Delete all renumber the list, so a stale act_number here
        # would risk highlighting the wrong action -- drop the highlight
        # instead of letting it follow whatever action inherits the number.
        nonlocal last_added_act_number
        last_added_act_number = None

    def refresh_position_options() -> None:
        _refresh_position_options(edited_task, position_select, position_labels)

    def add_picked_action(action_key: str) -> None:
        nonlocal last_added_act_number
        # "If" gets an extra prompt (just the If, or a whole If/Else/End If
        # block?) before anything is inserted; every other action goes in
        # directly. Position is resolved when the choice lands, not at
        # picker-click time -- same value, and the variant dialog is modal.
        if action_key == taskedit.IF_ACTION_KEY:

            def _add_if_block(variant: str) -> None:
                nonlocal last_added_act_number
                act_number = self.event_handlers.add_if_block_to_edit_task_event(
                    edited_task,
                    variant,
                    position_labels.get(position_select.value),
                )
                if act_number is not None:
                    last_added_act_number = act_number
                render_actions()
                refresh_position_options()

            build_if_variant_dialog(_add_if_block)
            return
        act_number = self.event_handlers.add_action_to_edit_task_event(
            edited_task,
            action_key,
            position_labels.get(position_select.value),
        )
        if act_number is not None:
            last_added_act_number = act_number
        render_actions()
        refresh_position_options()

    def refresh_picker(_e: ui.event | None = None) -> None:
        picker_container.clear()
        rows = taskedit.search_addable_actions(search_input.value, category_select.value)
        with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
            for row in rows:
                if row["addable"]:
                    ui.button(
                        f"{row['name']} ({row['category_name']})",
                        on_click=lambda r=row: add_picked_action(r["action_key"]),
                    ).props("flat align=left dense").classes("w-full justify-start")
                else:
                    with ui.column().classes("w-full gap-0"):
                        ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                        _render_addability_reason(self, row["reason"], refresh_picker)

    search_input.on_value_change(refresh_picker)
    category_select.on_value_change(refresh_picker)

    def render_actions() -> None:
        # Rebuild from scratch -- Copy/Move/Delete all renumber every action, so
        # stale act*_arg* keys must not survive into the next Save.
        for key in [k for k in field_refs if k.startswith("act")]:
            del field_refs[key]
        actions_container.clear()
        with actions_container, ui.scroll_area().classes(list_classes):
            if not edited_task.actions:
                ui.label(translate_string("No actions in this Task.")).classes("text-xs text-gray-500 italic")
            last_position = len(edited_task.actions) - 1
            indent_spaces = _action_indent_spaces(self)
            display_levels = taskedit.action_display_levels(edited_task.actions)
            for action, nest_level in zip(edited_task.actions, display_levels, strict=True):
                # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
                indent_pad = "\u00a0" * (indent_spaces * nest_level)
                is_last_added = action.act_number == last_added_act_number
                header = f"{indent_pad}{action.act_number}: {action.action_name}"
                if is_last_added:
                    header += "  \u2190 just added"
                action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
                if is_last_added:
                    action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
                with action_expansion:
                    with ui.row().classes("w-full items-center gap-2 mb-2"):
                        ui.button(
                            translate_string("Copy"),
                            on_click=lambda n=action.act_number: (
                                clear_last_added(),
                                self.event_handlers.copy_action_in_edit_task_event(edited_task, n),
                                render_actions(),
                                refresh_position_options(),
                            ),
                        ).props("flat color=blue dense")
                        move_to_input = (
                            ui.number(
                                translate_string("Move to #"),
                                value=action.act_number,
                                min=0,
                                max=last_position,
                            )
                            .classes("w-24")
                            .props("dense")
                        )
                        ui.button(
                            translate_string("Move"),
                            on_click=lambda n=action.act_number, target=move_to_input: (
                                clear_last_added(),
                                self.event_handlers.move_action_in_edit_task_event(
                                    edited_task,
                                    n,
                                    int(target.value) if target.value is not None else n,
                                ),
                                render_actions(),
                                refresh_position_options(),
                            ),
                        ).props("flat color=orange dense")
                        ui.button(
                            translate_string("Delete"),
                            on_click=lambda n=action.act_number: (
                                clear_last_added(),
                                self.event_handlers.delete_action_in_edit_task_event(edited_task, n),
                                render_actions(),
                                refresh_position_options(),
                            ),
                        ).props("flat color=red dense")

                    action_enabled_switch = ui.switch(
                        value=taskedit.is_action_enabled(action),
                        on_change=lambda e, n=action.act_number: self.event_handlers.set_action_enabled_event(
                            edited_task,
                            n,
                            e.value,
                        ),
                    ).classes("mb-2")
                    action_enabled_switch.bind_text_from(
                        action_enabled_switch,
                        "value",
                        backward=lambda v: "Enabled" if v else "Disabled",
                    )

                    field_refs[taskedit.label_key(action.act_number)] = ui.input(
                        translate_string("Label"),
                        value=taskedit.get_action_label(action),
                    ).classes("w-full")

                    if action.code != taskedit.IF_ACTION_CODE:
                        _render_action_condition_checkbox(self, edited_task, action, condition_cache)
                    _render_continue_after_error_checkbox(self, edited_task, action)
                    _render_plugin_configuration_warning(action.action_element, action.action_name)

                    if not action.args:
                        ui.label(translate_string("No editable arguments.")).classes("text-xs text-gray-500 italic")
                    for arg in action.args:
                        key = taskedit.arg_key(action.act_number, arg.arg_id)
                        with ui.row().classes("w-full items-center gap-2"):
                            if arg.widget_kind == "checkbox":
                                field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
                            elif arg.widget_kind == "dropdown":
                                options = arg.dropdown_options or []
                                field_refs[key] = ui.select(
                                    options,
                                    value=_dropdown_current_label(arg),
                                    label=arg.arg_name,
                                ).classes(
                                    "flex-1",
                                )
                            elif taskedit.is_perform_task_name_arg(action.code, arg):
                                _render_task_name_field(self, action, arg, key, field_refs)
                            elif arg.widget_kind == "app_picker":
                                _render_app_arg_field(self, arg, key, field_refs)
                            elif arg.widget_kind == "icon_picker":
                                _render_icon_arg_field(self, arg, key, field_refs)
                            elif arg.widget_kind in ("text", "raw_fallback"):
                                field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
                                if arg.readonly_note:
                                    _render_readonly_note(
                                        self,
                                        arg.readonly_note,
                                        _after_inventory_fetch(render_actions, action),
                                    )
                            else:  # readonly
                                ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes("flex-1")
                                if arg.readonly_note:
                                    _render_readonly_note(
                                        self,
                                        arg.readonly_note,
                                        _after_inventory_fetch(render_actions, action),
                                    )

    refresh_picker()
    refresh_position_options()
    render_actions()

    return render_actions


def build_edit_task_dialog(self: MyGui, edited_task: taskedit.EditableTask) -> None:
    """Builds and opens the Edit Task dialog (Phase 1: name/priority; an "Add an
    action" search/filter picker -- the same one Add Task uses -- that can insert
    the new action before/after any existing one or at the end, not just append;
    per-action Copy/Move/Delete; and the values of an action's existing arguments
    -- see taskedit.py for what's editable and why). The Task Name field itself is
    read-only: Rename prompts for a new one and applies it on its own, immediately
    (see build_rename_dialog); Delete Task removes the Task and every reference to
    it (see build_delete_task_dialog).

    Built fresh each call rather than reused, since its content is entirely different
    per Task. Field widgets are kept in a plain dict (matching this file's existing
    ad-hoc widget-ref pattern) and read at Save time rather than using NiceGUI bindings.
    """
    # Imported here rather than at the top of the file: guiwins imports this module, so a
    # module-level import would be a cycle.  See this module's docstring.
    from maptasker.src.guiwins import PendingChangesBanner, _build_properties_button, editor_state  # noqa: PLC0415

    task_name = edited_task.task_element.findtext("nme", "")
    field_refs: dict = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        # Kept as a local (not in field_refs -- _task_arg_values reads .value off
        # every entry there, which a ui.label doesn't have) so Rename can retitle
        # the still-open dialog: see rename_task_event.
        title_label = ui.label(f"{translate_string('Edit Task')}: {task_name}").classes(
            "text-xl font-bold text-blue-600",
        )

        with ui.row().classes("w-full gap-4"):
            # Read-only: an existing Task is renamed only through the Rename
            # button's prompt (guiwins.build_rename_dialog), which is the one path that
            # rejects a name another Task already has. Rename writes the new
            # name back into this field so Ok/Save, which still read it, don't
            # apply the pre-rename name over the top.
            field_refs["name"] = (
                ui.input(translate_string("Task Name"), value=task_name).props("readonly").classes("flex-1")
            )
            field_refs["priority"] = ui.input(
                translate_string("Priority"),
                value=edited_task.task_element.findtext("pri", ""),
            ).classes("w-32")
            # The working copy, not the live element: every Task save path goes through
            # it (apply_edited_task_to_live_tree swaps the whole element into all_tasks,
            # render_standalone_task_xml deep-copies it), so a property written here
            # reaches the live tree, the export and the upload alike -- and Cancel here
            # still discards it.  See objprops.py's module docstring.
            _build_properties_button(self, objprops.KIND_TASK, edited_task.task_element, dialog)

        # The picker and the action list -- see _build_task_action_editor, which this
        # dialog is where they came from.  Nothing here needs its render_actions back:
        # the editor redraws itself on everything that changes the list.
        _build_task_action_editor(self, edited_task, field_refs)

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=taskedit.default_save_path(task_name),
        ).classes("w-full mt-2")

        # Everything a change to this Task can be in is either the working copy's element --
        # every Add/Copy/Move/Delete Action, an action's Enabled switch, its If condition,
        # a Rename -- or a widget in field_refs, which is where the Priority, labels and
        # argument values sit until a save reads them.  See guiwins.editor_state.
        pending_changes = PendingChangesBanner()
        pending_changes.watch(dialog, lambda: editor_state(edited_task.task_element, field_refs))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            delete_task_button = ui.button(
                translate_string("Delete Task"),
                on_click=lambda: self.event_handlers.delete_task_event(edited_task, dialog),
            ).classes("bg-red-500 text-white")
            with delete_task_button:
                ui.tooltip(
                    translate_string(
                        "Deletes this Task and every reference to it: it is removed from the Tasks of every "
                        "Project that owns it, and from any Profile that runs it as its Entry/Exit Task. "
                        "The Profiles themselves are kept.",
                    ),
                )
            rename_task_button = ui.button(
                translate_string("Rename"),
                on_click=lambda: self.event_handlers.rename_task_event(edited_task, field_refs, title_label),
            ).classes("bg-blue-600")
            with rename_task_button:
                ui.tooltip(
                    translate_string(
                        "Prompts for a new name and applies just that to the loaded backup, right now. "
                        "Everything else in this dialog stays pending until Ok/Save, and the dialog stays "
                        "open so you can carry on editing.",
                    ),
                )
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_edited_task_event(edited_task, field_refs, dialog),
            ).props("outline")
            task_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_edited_task_to_current_file_event(
                    edited_task,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with task_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this Task -- "
                        "with this dialog's edits applied, the same ones 'Ok' would keep.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            task_to_android = ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_to_android_dialog_event(
                    edited_task,
                    field_refs,
                    dialog,
                ),
            ).props("outline")
            with task_to_android:
                ui.tooltip(
                    translate_string(
                        "This opens a choice of two: write the Task as a standalone file onto your Android "
                        "device under /Tasker/tasks, or import it straight into Tasker's live "
                        "configuration.\n\n"
                        "The 'Http Server Example' Tasker Project must be installed and active on the Android "
                        "device, with the server running (see the README's Direct XML Retrieval notes), and "
                        "Tasker must be 6.2 or higher.\n\n"
                        "The Android device must be on the same network, and the IP Address and Port must "
                        "match its Tasker server settings.\n\n"
                        "Watch the Android device while either one runs: Tasker asks you to authorize "
                        "the connection several times for one save, and a prompt left untapped fails it.\n\n"
                        "You must exit and restart Tasker to see an imported Task in the Tasker UI.",
                    ),
                ).style("white-space: pre-wrap")
            task_save = ui.button(
                translate_string("Export Task"),
                on_click=lambda: self.event_handlers.save_edited_task_event(edited_task, field_refs, dialog),
            ).classes("bg-blue-600")
            with task_save:
                ui.tooltip(
                    translate_string("This will save the Task directly to your current drive.\n\n"),
                ).style("white-space: pre-wrap")

    dialog.open()


def build_delete_task_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Task. Like guiwins_profedit.build_delete_profile_dialog there is no
    Keep/Delete Contents choice -- a Task owns nothing below it -- but unlike a
    Profile, other things point *at* a Task, so the dialog spells out exactly
    which references go away with it (see taskedit.delete_task): the owning
    Project(s)' Task list, and the Entry/Exit link of any Profile that runs it.

    The reference counts are read live so they can't go stale between opening
    Edit Task and clicking Delete, same as the Profile/Project dialogs' counts.
    """
    task_name = edited_task.task_element.findtext("nme", "")
    project_count, profile_count = taskedit.count_task_references(task_name)

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Delete Task')} '{task_name}'").classes("text-lg font-bold text-red-600")
        ui.label(
            f"{translate_string('It will be removed from')} {project_count} {translate_string('Project(s) and unlinked from')}"
            f" {profile_count} {translate_string('Profile(s) that run it. Those Profiles themselves are kept.')}",
        ).classes("mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Delete Task"),
                on_click=lambda: self.event_handlers.confirm_delete_task_event(
                    task_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_add_task_dialog(
    self: MyGui,
    edited_task: taskedit.EditableTask,
    on_task_created: Callable[[str], None] | None = None,
    target_project_name: str = "",
) -> None:
    """Builds and opens the Add Task dialog: create a new Task, search/filter actions
    by name or category to add to it, edit their synthesized default argument values,
    remove any if needed, then save as a standalone .tsk.xml -- see taskedit.py for
    what's addable and why (roughly 3 in 4 action types; the rest need an App/Icon
    picker or are third-party plugin configs with no generic default, and show up
    greyed out with a reason instead of being clickable).

    Both the action picker and the "added so far" list are rebuilt (not just
    appended to) after every Add/Remove, since removing an action renumbers every
    action after it -- their field_refs keys (which embed act_number) would
    otherwise go stale.

    on_task_created, if given, is called with the new Task's id once Ok/Save/
    Save To Android actually registers it into the live tree -- the hook
    open_add_task_for_profile_link_event uses to link this brand-new Task in
    as a Profile's Entry/Exit Task the moment it exists, without this dialog
    (or its Save/Ok/Save To Android handlers) needing to know anything about
    Profiles itself.

    target_project_name is the single Project the top-level "Add Task" button
    requires be selected before this dialog opens (see
    userintr.open_add_task_dialog_event) -- stored in field_refs (not a widget;
    there's nothing here for the user to change) purely so _finish_new_task can
    read it back and add the new Task's id to that Project's <tids> once it's
    registered. Left "" for open_add_task_for_profile_link_event's nested
    dialog, which doesn't attach to a Project at all.
    """
    # Imported here rather than at the top of the file: guiwins imports this module, so a
    # module-level import would be a cycle.  See this module's docstring.
    from maptasker.src.guiwins import _build_properties_button  # noqa: PLC0415

    field_refs: dict = {"target_project_name": target_project_name}
    category_names = sorted({row["category_name"] for row in taskedit.list_addable_actions()})
    # Same out-of-band Position-label -> act_number map as build_edit_task_dialog's.
    position_labels: dict[str, int | None] = {}
    # Same per-action If condition value cache as build_edit_task_dialog's.
    condition_cache: dict[int, tuple[str, str, str]] = {}

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[500px] max-w-[900px] w-full p-6"):
        ui.label(translate_string("Add Task")).classes("text-xl font-bold text-blue-600")

        last_auto_path = {"value": taskedit.default_save_path("")}

        def sync_save_path(_e: ui.event | None = None) -> None:
            # Keep "Save as" in sync with the Task Name as the user types, so the
            # file actually lands under the name they gave the task -- but only
            # while it still holds what we last auto-computed; if the user has
            # since edited it manually, leave their edit alone. (Can't tell "manual
            # edit" apart via save_path's own on_change: NiceGUI fires that for
            # programmatic value sets too, so it would trip on the very first sync.)
            if field_refs["save_path"].value == last_auto_path["value"]:
                new_path = taskedit.default_save_path(field_refs["name"].value)
                field_refs["save_path"].value = new_path
                last_auto_path["value"] = new_path

        if target_project_name:
            ui.label(f"{translate_string('Adding to Project:')} {target_project_name}").classes(
                "text-sm text-gray-500 italic",
            )

        with ui.row().classes("w-full gap-4"):
            field_refs["name"] = ui.input(translate_string("Task Name"), value="", on_change=sync_save_path).classes(
                "flex-1",
            )
            field_refs["priority"] = ui.input(translate_string("Priority"), value="100").classes("w-32")
            # Safe on a not-yet-registered Task, unlike Add Project's equivalent:
            # register_new_task stores THIS element object in all_tasks rather than a
            # copy of it, and every save path deep-copies it at write time, so properties
            # set before the Task exists are still on it once it does.
            _build_properties_button(self, objprops.KIND_TASK, edited_task.task_element, dialog)

        ui.label(translate_string("Add an action")).classes("text-sm font-bold mt-2")
        with ui.row().classes("w-full gap-4"):
            search_input = ui.input(translate_string("Search actions")).classes("flex-1")
            category_select = ui.select(["All", *category_names], value="All").classes("w-48")
        position_select = (
            ui.select([], label=translate_string("Position"), with_input=True).classes("w-full").props("dense")
        )

        picker_container = ui.column().classes("w-full")
        ui.label(translate_string("Actions in this Task")).classes("text-sm font-bold mt-2")
        added_container = ui.column().classes("w-full")
        # act_number of the action most recently added in this dialog session --
        # render_added_actions highlights it so it's easy to spot in a long list.
        last_added_act_number: int | None = None

        def clear_last_added() -> None:
            # Remove renumbers the list, so a stale act_number here would risk
            # highlighting the wrong action -- drop the highlight instead of
            # letting it follow whatever action inherits the number.
            nonlocal last_added_act_number
            last_added_act_number = None

        def refresh_position_options() -> None:
            _refresh_position_options(edited_task, position_select, position_labels)

        def render_added_actions() -> None:
            # Rebuild from scratch -- a Remove renumbers every action after it, so
            # stale act*_arg* keys must not survive into the next Save.
            for key in [k for k in field_refs if k.startswith("act")]:
                del field_refs[key]
            added_container.clear()
            with added_container:
                if not edited_task.actions:
                    ui.label(translate_string("No actions added yet.")).classes("text-xs text-gray-500 italic")
                indent_spaces = _action_indent_spaces(self)
                display_levels = taskedit.action_display_levels(edited_task.actions)
                for action, nest_level in zip(edited_task.actions, display_levels, strict=True):
                    # Indent with non-breaking spaces -- plain ones collapse in the rendered header.
                    indent_pad = "\u00a0" * (indent_spaces * nest_level)
                    is_last_added = action.act_number == last_added_act_number
                    header = f"{indent_pad}{action.act_number}: {action.action_name}"
                    if is_last_added:
                        header += "  \u2190 just added"
                    action_expansion = ui.expansion(header, value=is_last_added).classes("w-full")
                    if is_last_added:
                        action_expansion.classes("bg-amber-100 dark:bg-amber-900 border-2 border-amber-400 rounded")
                    with action_expansion:
                        field_refs[taskedit.label_key(action.act_number)] = ui.input(
                            translate_string("Label"),
                            value=taskedit.get_action_label(action),
                        ).classes("w-full")
                        if action.code != taskedit.IF_ACTION_CODE:
                            _render_action_condition_checkbox(self, edited_task, action, condition_cache)
                        _render_continue_after_error_checkbox(self, edited_task, action)
                        _render_plugin_configuration_warning(action.action_element, action.action_name)
                        for arg in action.args:
                            key = taskedit.arg_key(action.act_number, arg.arg_id)
                            with ui.row().classes("w-full items-center gap-2"):
                                if arg.widget_kind == "checkbox":
                                    field_refs[key] = ui.checkbox(arg.arg_name, value=arg.current_value == "1")
                                elif arg.widget_kind == "dropdown":
                                    options = arg.dropdown_options or []
                                    field_refs[key] = ui.select(
                                        options,
                                        value=_dropdown_current_label(arg),
                                        label=arg.arg_name,
                                    ).classes("flex-1")
                                elif taskedit.is_perform_task_name_arg(action.code, arg):
                                    _render_task_name_field(self, action, arg, key, field_refs)
                                elif arg.widget_kind == "app_picker":
                                    _render_app_arg_field(self, arg, key, field_refs)
                                elif arg.widget_kind == "icon_picker":
                                    _render_icon_arg_field(self, arg, key, field_refs)
                                elif arg.widget_kind == "readonly":
                                    # A newly-added plugin action's payload (see
                                    # taskedit._synthesize_bundle_arg): not editable here,
                                    # and apply_arg_values skips it, so never a field_ref.
                                    ui.input(arg.arg_name, value=arg.current_value).props("readonly").classes(
                                        "flex-1",
                                    )
                                    if arg.readonly_note:
                                        _render_readonly_note(
                                            self,
                                            arg.readonly_note,
                                            _after_inventory_fetch(render_added_actions, action),
                                        )
                                else:  # "text" or "raw_fallback"
                                    field_refs[key] = ui.input(arg.arg_name, value=arg.current_value).classes("flex-1")
                        ui.button(
                            translate_string("Remove"),
                            on_click=lambda n=action.act_number: (
                                clear_last_added(),
                                self.event_handlers.remove_action_from_new_task_event(edited_task, n),
                                render_added_actions(),
                                refresh_position_options(),
                            ),
                        ).props("flat color=red dense")

        def add_picked_action(action_key: str) -> None:
            nonlocal last_added_act_number
            # Same "If" block prompt and Position handling as
            # build_edit_task_dialog's picker.
            if action_key == taskedit.IF_ACTION_KEY:

                def _add_if_block(variant: str) -> None:
                    nonlocal last_added_act_number
                    act_number = self.event_handlers.add_if_block_to_new_task_event(
                        edited_task,
                        variant,
                        position_labels.get(position_select.value),
                    )
                    if act_number is not None:
                        last_added_act_number = act_number
                    render_added_actions()
                    refresh_position_options()

                build_if_variant_dialog(_add_if_block)
                return
            act_number = self.event_handlers.add_action_to_new_task_event(
                edited_task,
                action_key,
                position_labels.get(position_select.value),
            )
            if act_number is not None:
                last_added_act_number = act_number
            render_added_actions()
            refresh_position_options()

        def refresh_picker(_e: ui.event | None = None) -> None:
            picker_container.clear()
            rows = taskedit.search_addable_actions(search_input.value, category_select.value)
            with picker_container, ui.scroll_area().classes("w-full h-40 border rounded p-2"):
                for row in rows:
                    if row["addable"]:
                        ui.button(
                            f"{row['name']} ({row['category_name']})",
                            on_click=lambda r=row: add_picked_action(r["action_key"]),
                        ).props("flat align=left dense").classes("w-full justify-start")
                    else:
                        with ui.column().classes("w-full gap-0"):
                            ui.label(f"{row['name']} ({row['category_name']})").classes("text-gray-400")
                            _render_addability_reason(self, row["reason"], refresh_picker)

        search_input.on_value_change(refresh_picker)
        category_select.on_value_change(refresh_picker)
        refresh_picker()
        refresh_position_options()
        render_added_actions()

        field_refs["save_path"] = ui.input(
            translate_string("Save as"),
            value=last_auto_path["value"],
        ).classes("w-full mt-2")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(
                translate_string("Ok"),
                on_click=lambda: self.event_handlers.keep_new_task_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            new_task_to_current_file = ui.button(
                translate_string("Save To Current File"),
                on_click=lambda: self.event_handlers.save_new_task_to_current_file_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            with new_task_to_current_file:
                ui.tooltip(
                    translate_string(
                        "Saves the entire backup -- every Project, Profile and Task in it, not just this one -- "
                        "with the new Task added to it, the same way 'Ok' adds it.\n"
                        "It is written to a new, timestamped copy of the file currently loaded: "
                        "backup.xml becomes backup_20260728_143005.xml.\n"
                        "The file you loaded is never written to, so it is left exactly as it was.\n"
                        "The app then switches to the new copy, which becomes the current file for any further "
                        "editing and saving; saving again replaces the timestamp rather than adding a second one.\n"
                        "This writes to this computer only -- nothing is sent to your Android device.",
                    ),
                ).style("white-space: pre-wrap")
            ui.button(
                translate_string("Save To Android"),
                on_click=lambda: self.event_handlers.open_save_to_android_dialog_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).props("outline")
            export_task = ui.button(
                translate_string("Export Task"),
                on_click=lambda: self.event_handlers.save_new_task_event(
                    edited_task,
                    field_refs,
                    dialog,
                    on_created=on_task_created,
                ),
            ).classes("bg-blue-600")
            with export_task:
                ui.tooltip(
                    translate_string(
                        "Exports the Task as XML to a file on your computer.",
                    ),
                ).style("white-space: pre-wrap")

    dialog.open()
