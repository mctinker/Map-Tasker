"""guiwins_dialogs: the smaller confirmation and report dialogs.

Health Check, the helper Tasks left on the device, Overwrite confirmation, Changes Since, Rename, Delete Project, and
the unsaved-deletion warning."""

from __future__ import annotations

import inspect
from datetime import date
from typing import TYPE_CHECKING, Any

from nicegui import ui

from maptasker.src.analysis import healthck
from maptasker.src.core import appinv, clock, timeline
from maptasker.src.core.mapjump import PROJECT
from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.guiwins_impact import build_impact_panel, wire_impact_clicks
from maptasker.src.gui.guiwins_taskedit import _build_fetch_apps_dialog

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Sequence

    from maptasker.src.core.primitem import RunState
    from maptasker.src.edit import projedit
    from maptasker.src.gui.userintr import MyGui


def _app_list_status() -> str:
    """What the plugin check will be compared against, for the Health Check panel.

    One line per fetched device, dated, because the date is the thing to judge it by: a
    plugin installed since then is reported missing, and one uninstalled since is not.
    """
    devices = appinv.fetched_devices()
    if not devices:
        return translate_string(
            "No app list has been fetched from the device, so plugins cannot be checked for being installed.",
        )
    lines = [f"{device}: {count} {translate_string('applications, fetched')} {when}" for device, when, count in devices]
    heading = translate_string(
        "Plugins are checked against the app list from"
        if len(lines) == 1
        else "Plugins are checked against the app lists from"
    )
    return f"{heading} {lines[0]}" if len(lines) == 1 else "\n".join([f"{heading}:", *lines])


def _fill_health_check_categories(
    boxes: dict[str, ui.checkbox],
    skip: set[str],
    box_changed: Callable[[], None],
) -> None:
    """The Health Check panel's scrolling list of categories, a checkbox each; `boxes` is filled by tag."""
    # Scrolled rather than fitted: the list is forty-five entries and grows with every
    # check added, and a dialog taller than the window is one whose buttons cannot be
    # reached.  The headings are just headings -- a group is not itself a choice, so
    # there is nothing here that can be ticked but does not correspond to a finding.
    with ui.scroll_area().classes("w-full h-[420px] mt-2 border rounded"):
        group = ""
        for category in healthck.CATEGORIES:
            if category.group != group:
                group = category.group
                ui.label(translate_string(group)).classes("font-bold text-sm mt-3 mb-1")
            with ui.row().classes("items-center gap-2 ml-2 no-wrap"):
                boxes[category.tag] = ui.checkbox(
                    value=category.tag not in skip,
                    on_change=box_changed,
                ).props("dense")
                with ui.column().classes("gap-0"):
                    ui.label(category.tag).classes("font-mono text-xs")
                    ui.label(translate_string(category.what)).classes("text-xs text-gray-500")


def _build_app_list_status_row(gui: MyGui) -> None:
    """The panel's line saying what the plugins are checked against, with the button that refreshes it."""

    async def refresh_apps() -> None:
        """Fetch the app list from the device, then say what the plugins will be checked against."""
        await _build_fetch_apps_dialog(gui, show_app_status)

    def show_app_status() -> None:
        app_status.set_text(_app_list_status())

    with ui.row().classes("w-full items-center justify-between gap-2 mt-3 no-wrap"):
        app_status = ui.label(_app_list_status()).classes("text-xs text-gray-500 whitespace-pre-line")
        refresh_button = ui.button(
            translate_string("Refresh App List"),
            icon="cloud_download",
            on_click=refresh_apps,
        ).props("flat dense color=primary no-caps")
        refresh_button.tooltip(
            translate_string(
                "Fetch the list of installed applications from your Android device, so the check for "
                "plugins that are not installed is up to date.",
            ),
        )


def build_health_check_dialog(
    on_run: Callable[[list[str]], None],
    on_save: Callable[[list[str]], None],
    gui: MyGui,
    state: RunState,
) -> None:
    """Ask which categories of finding the Health Check should report, then run it.

    A panel rather than a settings screen because the answer is a property of the QUESTION
    being asked, not of the program: the check reports forty-five kinds of thing, and a
    user chasing one broken Perform Task does not want to read two hundred findings about
    variables that are set and never read.  Every box starts ticked, so the default is
    still "tell me everything" and nothing is quietly left out of a report unless somebody
    chose to leave it out.

    What is remembered between sessions is the UNTICKED set (program_arguments
    ["health_check_skip"]).  Storing it that way round is what lets a category added in a
    later release arrive already ticked -- see healthck.CATEGORIES.

    on_run is handed the list to leave out when Run is pressed.  on_save is handed it every
    time a choice changes -- one box, or all of them through Select All or Deselect All --
    so what is ticked is never lost to a Cancel or an exit.  The caller does the running and
    the saving: this module builds windows and knows nothing about what a health check is.

    'Refresh App List' is here because PLUGIN-NOT-INSTALLED is only as current as the list
    it is checked against, and the only other way to fetch one is from inside an editor's
    Application picker.  It opens the same fetch dialog those do, over this panel, and the
    panel stays open so Run is one click away once the list is in.
    """
    skip = set(state.program_arguments.health_check_skip or [])
    boxes: dict[str, ui.checkbox] = {}
    # Select All and Deselect All set every box in turn, and each of those would otherwise
    # save the settings file on its own: forty-five writes for one click.
    setting_all = False

    def skipped() -> list[str]:
        """The categories currently unticked."""
        return [tag for tag, box in boxes.items() if not box.value]

    def box_changed() -> None:
        """Remember a single box being ticked or unticked, as it happens."""
        if not setting_all:
            on_save(skipped())

    def set_all(ticked: bool) -> None:
        """Tick or untick every category at once, and remember that with a single save."""
        nonlocal setting_all
        setting_all = True
        try:
            for box in boxes.values():
                box.value = ticked
        finally:
            setting_all = False
        on_save(skipped())

    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[520px] max-w-[720px] w-full p-6"):
        ui.label(translate_string("Health Check")).classes("text-lg font-bold text-blue-600")
        ui.label(translate_string("Report these categories:")).classes("text-sm text-gray-500")

        _fill_health_check_categories(boxes, skip, box_changed)

        def run() -> None:
            """Close the panel, then run the check for whatever is still ticked."""
            dialog.close()
            on_run(skipped())

        _build_app_list_status_row(gui)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=dialog.close).props("outline")
            ui.button(translate_string("Select All"), on_click=lambda: set_all(True)).props("outline")
            ui.button(translate_string("Deselect All"), on_click=lambda: set_all(False)).props("outline")
            ui.button(translate_string("Run"), on_click=run).classes("bg-blue-600")

    dialog.open()


def build_helper_tasks_dialog(stale: list[str], current: list[str], device: str) -> None:
    """Shows which of this program's own helper Tasks are dead on the Android device.

    A LIST, NOT A BUTTON, and that is the whole design: nothing here can delete them.  The
    Tasker HTTP Server Example has no route for deleting a Task -- its Task endpoints are GET
    (list) and POST (run), and its only DELETE removes a file from storage, which a Task in
    Tasker's configuration is not.  So this does the part that can be done: names them
    exactly, so the user works down a list in Tasker instead of guessing which
    'MapTasker Open Profile v2' is safe to remove.

    Why there are any: a helper's name carries a version because its BODY changes between
    releases and Tasker's api/import adds rather than replaces (see
    devicetask.install_task_on_android), so the previous one is left behind, running fine and
    doing the wrong thing if it were ever used.  Nothing breaks while they sit there; they
    are clutter in a list the user owns.

    The current ones are shown too, and not as a footnote: this dialog is read next to
    Tasker's own Task list, and 'delete everything starting with MapTasker' is exactly the
    conclusion it must not invite.
    """
    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[420px] max-w-[680px] w-full p-6"):
        ui.label(translate_string("MapTasker Helper Tasks")).classes("text-lg font-bold text-blue-600")
        ui.label(f"{translate_string('On')} {device}").classes("text-xs text-gray-500")

        if stale:
            ui.label(
                f"{len(stale)} {translate_string('left over from an earlier version -- safe to delete in Tasker:')}",
            ).classes("mt-3 font-bold text-orange-600")
            with ui.column().classes("gap-0 mt-1"):
                for name in stale:
                    ui.label(name).classes("font-mono text-sm break-all")
            ui.label(
                translate_string(
                    "Delete them from Tasker's Tasks tab -- long-press one, then Delete.  Nothing here can "
                    "do it: Tasker's HTTP API has no way to delete a Task.  To make the next cleanup a single "
                    "delete, put the helper Tasks in the 'MapTasker' Project from the Android panel.",
                ),
            ).classes("text-xs text-gray-500 italic mt-2")
        else:
            ui.label(translate_string("Nothing left over -- every MapTasker Task on the device is in use.")).classes(
                "mt-3 text-green-600",
            )

        if current:
            ui.label(translate_string("In use -- leave these alone:")).classes("mt-4 font-bold")
            with ui.column().classes("gap-0 mt-1"):
                for name in current:
                    ui.label(name).classes("font-mono text-sm text-gray-500 break-all")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("outline")

    dialog.open()


def build_helpers_in_the_way_dialog(present: list[str], device: str, project_exists: bool | None = None) -> None:
    """Names the helper Tasks that must be deleted before the 'MapTasker' Project can be imported.

    Tasker rejects a whole Project with 'Import failed.' if it already has any Task in it (see
    devicehelpers.stage_helper_project), so the file is not even written until these are gone.

    project_exists says whether Tasker already has the 'MapTasker' Project, which changes what
    the user actually does: deleting that one Project takes the Tasks in it with it.  None means
    it could not be asked -- the helper that answers it was not on the device to run -- and then
    the Project is mentioned as a possibility rather than as a fact.
    """
    with ui.dialog().props("persistent") as dialog, ui.card().classes("min-w-[420px] max-w-[680px] w-full p-6"):
        ui.label(translate_string("Delete These Helper Tasks First")).classes("text-lg font-bold text-blue-600")
        ui.label(f"{translate_string('On')} {device}").classes("text-xs text-gray-500")
        ui.label(
            translate_string(
                "Tasker refuses to import a Project that contains a Task it already has, so the 'MapTasker' "
                "Project cannot be imported while these are in Tasker:",
            ),
        ).classes("mt-3")
        with ui.column().classes("gap-0 mt-1"):
            for name in present:
                ui.label(name).classes("font-mono text-sm break-all")
        if project_exists:
            advice = (
                "Tasker already has a 'MapTasker' Project.  Delete that Project -- which deletes the Tasks "
                "in it -- along with any of the Tasks above that are outside it, and then try again."
            )
        elif project_exists is None:
            advice = (
                "Delete them in Tasker -- or delete the 'MapTasker' Project, if they are already in it -- "
                "and then try again."
            )
        else:
            advice = "Delete them from Tasker's Tasks tab -- long-press one, then Delete -- and try again."
        ui.label(translate_string(advice)).classes("text-xs text-gray-500 italic mt-2")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("outline")

    dialog.open()


def build_overwrite_confirm_dialog(
    what_exists: str,
    on_confirm: Callable[[], object],
    *,
    unknown: bool = False,
    file_absent: bool = False,
    tasker_lines: Sequence[str] = (),
) -> None:
    """Confirms overwriting something that is already there, before anything is
    written. Backs every Save/Export path that would otherwise clobber a file
    silently -- the local standalone exports and the Save To Android uploads
    (see the save_* handlers in userintr and userintr_android).

    tasker_lines is what Tasker itself already has of the objects being sent (see
    userintr_android._what_tasker_already_has), shown under the file's own line so a save that both
    replaces a file and re-sends objects Tasker has asks once rather than twice.
    file_absent=True is a prompt raised by those lines alone: there is no file to name and
    nothing here is overwritten, so it says neither and offers Continue, not Overwrite.

    what_exists describes the thing in the user's terms (a full path); on_confirm
    performs the write and is called only if they choose "Overwrite". It may be a
    coroutine function, and is then awaited to the end: a write to the Android device
    hands its requests to a worker thread and has to wait for them. Cancel
    closes this dialog and leaves the parent Edit/Add dialog open, so nothing
    in progress is lost -- same convention as build_delete_project_dialog.

    unknown=True switches the wording for the case where existence could not be
    determined at all (maputil2.read_android_file returning None -- device
    unreachable mid-check). That is deliberately still a prompt rather than a
    silent write: the honest statement is "this might overwrite something", and
    the user is the one who knows whether that matters.
    """
    if file_absent:
        title, body = "Already in Tasker", ""
    else:
        title = "Could not check destination" if unknown else "Already exists"
        body = (
            f"Could not confirm whether {what_exists} already exists. Saving may overwrite it."
            if unknown
            else f"{what_exists} already exists and will be replaced."
        )

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(title).classes("text-lg font-bold text-orange-600")
        if body:
            ui.label(body).classes("mt-1 break-all")
        for line in tasker_lines:
            ui.label(line).classes("mt-2 break-words")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")

            async def _confirm() -> None:
                # Close first: on_confirm may open its own dialog (or close the
                # parent), and leaving this one stacked on top would hide it.
                confirm_dialog.close()
                # Awaited when it is a coroutine.  nicegui runs an async click handler inside
                # the button's slot, so the notifications a save makes still have a place to go.
                result = on_confirm()
                if inspect.isawaitable(result):
                    await result

            ui.button(translate_string("Continue" if file_absent else "Overwrite"), on_click=_confirm).classes(
                "bg-orange-600 text-white",
            )

    confirm_dialog.open()


def build_changes_since_dialog(on_choose: Callable[[str, date | None], Coroutine[Any, Any, None]]) -> None:
    """Asks how far back "Changes Since..." should look, then hands the answer over.

    The periods and what they resolve to are timeline's (see timeline.PERIOD_LABELS and
    cutoff_for) -- this only shows them.  Keeping the vocabulary there is what stops the
    label and the date it means from drifting apart.

    The date picker is built once and hidden, rather than created when the choice lands
    on "Since a specific date...".  A calendar appearing where a pulldown used to be
    resizes the dialog under the pointer; hiding it keeps the dialog one shape.

    on_choose is awaited with the period key and, for that one option, the date -- and
    only once the choice is complete, so it never has to re-check it.  Awaited rather than
    called because producing the report means expanding and re-parsing a snapshot, which is
    megabytes of work that has to go off the event loop.  Cancel calls nothing, the same
    convention as build_overwrite_confirm_dialog.
    """
    options = {key: translate_string(label) for key, label in timeline.PERIOD_LABELS.items()}

    with ui.dialog().props("persistent") as period_dialog, ui.card().classes("min-w-[420px] max-w-[560px] w-full p-6"):
        ui.label(translate_string("Changes Since")).classes("text-lg font-bold")
        ui.label(
            translate_string(
                "Compare what you have open now against your configuration as it stood then.",
            ),
        ).classes("text-sm opacity-70 mt-1")

        period = ui.select(
            options,
            value=timeline.THIS_WEEK,
            label=translate_string("Period"),
        ).classes("w-full mt-3")

        # Quasar's own calendar.  landscape=False keeps it portrait, which fits the
        # dialog's width without the card growing sideways on a narrow drawer.
        date_holder = ui.column().classes("w-full items-center mt-3")
        with date_holder:
            picked_date = ui.date().props("minimal")
        date_holder.bind_visibility_from(period, "value", lambda value: value == timeline.ON_DATE)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=period_dialog.close).props("outline")

            async def _confirm() -> None:
                chosen = period.value
                on_date = None
                if chosen == timeline.ON_DATE:
                    on_date = _parse_picked_date(picked_date.value)
                    if on_date is None:
                        ui.notify(translate_string("Choose a date first."), type="warning")
                        return
                    if on_date > clock.now().date():
                        ui.notify(
                            translate_string("That date is in the future.  Choose a day that has happened."),
                            type="warning",
                        )
                        return
                # Closed before the work starts: the report opens its own view, and
                # leaving this dialog stacked on top would hide it.  Same reasoning as
                # build_overwrite_confirm_dialog's _confirm.
                period_dialog.close()
                await on_choose(chosen, on_date)

            ui.button(translate_string("Show Changes"), on_click=_confirm).classes("bg-teal-600 text-white")

    period_dialog.open()


def _parse_picked_date(value: object) -> date | None:
    """ui.date's "YYYY-MM-DD" as a date, or None when nothing usable was picked.

    None rather than an exception for an empty or malformed value: the picker starts
    empty, so "nothing chosen yet" is the ordinary state, not a fault.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_rename_dialog(
    _gui: MyGui,
    item_type: str,
    current_name: str,
    on_rename: Callable[[str, ui.dialog], None],
) -> None:
    """Prompts for a new name for a Project/Profile/Task, opened by the "Rename"
    button in that item's Edit dialog.

    The Edit dialogs' own Name field is read-only (see guiwins_taskedit.build_edit_task_dialog),
    so this prompt is the only place an existing item's name can be typed. That
    makes a rename an explicit, separately-confirmed action instead of a side
    effect of Ok/Save, and it routes every rename through the one path that
    checks the new name doesn't collide with another item's -- see
    taskedit.apply_task_rename/profedit.apply_profile_rename/
    projedit.apply_edits_to_project; Ok/Save's own apply_edits_to_task/
    apply_edits_to_profile deliberately don't look at other items' names, so
    typing into the old editable field could quietly produce two Tasks sharing
    one name.

    on_rename receives the typed name and this dialog, and owns closing it --
    only on success, so a rejected name (empty, or already taken) leaves the
    prompt open with the text still there to fix. Cancel closes just this
    prompt and leaves the parent Edit dialog exactly as it was, same convention
    as build_delete_profile_dialog.
    """
    with ui.dialog().props("persistent") as rename_dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(f"{translate_string('Rename')} {translate_string(item_type)} '{current_name}'").classes(
            "text-lg font-bold text-blue-600",
        )
        name_input = ui.input(translate_string("New name"), value=current_name).classes("w-full")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=rename_dialog.close).props("outline")
            ui.button(
                translate_string("Rename"),
                on_click=lambda: on_rename((name_input.value or "").strip(), rename_dialog),
            ).classes("bg-blue-600")

    rename_dialog.open()


def build_delete_project_dialog(
    self: MyGui,
    edited_project: projedit.EditableProject,
    parent_dialog: ui.dialog,
) -> None:
    """Confirms deletion of a Project, offering a choice for what happens to
    the Profiles/Tasks it owns: moved into "Base" (Keep Contents) or deleted
    along with it (Delete Contents) -- see projedit.delete_project. Shown
    before anything is mutated.

    The only Delete dialog with two buttons, and so the only one that shows two
    analyses: guiwins_impact.build_impact_panel is asked about each choice, because
    the two have genuinely different consequences.  Keeping the contents breaks
    nothing and quietly leaves the Project's Scenes in no Project at all; deleting
    them leaves every Profile OUTSIDE this Project that runs one of its Tasks
    pointing at a Task that is gone (projedit.delete_profiles_and_tasks_of_project
    unlinks nothing).  Neither was said here before, and neither is guessable from
    the button.  Both are read live, as the counts they replace were.
    """
    project_name = edited_project.project_name

    with ui.dialog().props("persistent") as confirm_dialog, ui.card().classes("min-w-[500px] max-w-[700px] w-full p-6"):
        ui.label(f"{translate_string('Delete Project')} '{project_name}'").classes("text-lg font-bold text-red-600")
        # One element around both panels, wired once: a tab's content is not in the DOM
        # until that tab is first opened, so the clicks have to be delegated from an
        # ancestor that is (see guiwins_impact.wire_impact_clicks).
        impact_area = ui.element("div").classes("w-full")
        with impact_area:
            with ui.tabs().classes("w-full mt-2") as choice_tabs:
                keep_tab = ui.tab(translate_string("If you keep the contents"))
                delete_tab = ui.tab(translate_string("If you delete them too"))
            with ui.tab_panels(choice_tabs, value=keep_tab).classes("w-full"):
                with ui.tab_panel(keep_tab):
                    build_impact_panel(self, PROJECT, project_name, keep_contents=True, wire=False)
                with ui.tab_panel(delete_tab):
                    build_impact_panel(self, PROJECT, project_name, keep_contents=False, wire=False)
        wire_impact_clicks(self, impact_area)
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Cancel"), on_click=confirm_dialog.close).props("outline")
            ui.button(
                translate_string("Keep Contents"),
                on_click=lambda: self.event_handlers.editors.keep_contents_delete_project_event(
                    project_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).props("outline")
            ui.button(
                translate_string("Delete Contents"),
                on_click=lambda: self.event_handlers.editors.delete_contents_delete_project_event(
                    project_name,
                    confirm_dialog,
                    parent_dialog,
                ),
            ).classes("bg-red-500 text-white")

    confirm_dialog.open()


def build_unsaved_deletion_dialog(message: str, save_configuration: Callable[[], Coroutine[Any, Any, Any]]) -> None:
    """Says an object was deleted and offers to save, for the Delete Project/Profile/Task/Scene dialogs.

    A delete closes the Edit dialog it was started from -- there is nothing left for that dialog to
    edit -- and that dialog held the only Save To Current File button, so the deletion was in memory
    and nowhere on disk with no way left to put it there.  This is that button's new home.  Closed
    once the save has been made; left up when it was not, so it can be pressed again.

    `save_configuration` is userintr.save_whole_configuration, which reports its own outcome.
    """

    async def save() -> None:
        if await save_configuration():
            dialog.close()

    with ui.dialog() as dialog, ui.card().classes("min-w-[400px] max-w-[600px] w-full p-6"):
        ui.label(message).classes("text-sm")
        ui.label(translate_string("The deletion has not been saved to a file yet.")).classes(
            "text-xs text-gray-500 italic",
        )
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Close"), on_click=dialog.close).props("outline")
            ui.button(translate_string("Save To Current File"), on_click=save).props("outline")
    dialog.open()
