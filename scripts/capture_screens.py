#!/usr/bin/env python3
"""Capture a PNG of every MapTasker screen into ./screens.

Usage (from the project root):

    uv run --no-project --with playwright python scripts/capture_screens.py
    uv run --no-project --with playwright python scripts/capture_screens.py --only main edit_task
    uv run --no-project --with playwright python scripts/capture_screens.py --list
    uv run --no-project --with playwright python scripts/capture_screens.py --inspect --only edit_task

Any Python that has `playwright` installed will do.  It drives the Google Chrome already on this
machine (channel="chrome"), so no browser has to be downloaded.

Options worth knowing: --scale 2 for retina-sharp images; --output DIR; --inspect prints the labels
that can be clicked on a screen (what to put in a Screen's `clicks`); --root DIR runs MapTasker from
another checkout -- `git archive HEAD maptasker tests/data | tar -x -C DIR` -- when this tree is in the
middle of an edit and does not import.

Adding a screen: add a Screen to SCREENS.  Most are `handler("<event>", select={...})` -- the same
call the button makes -- plus `clicks` for anything opened from inside a dialog.

How it works
------------
This one file is two programs.

  * The *driver* (the default) starts the *server* as a child process, opens Chrome with
    Playwright, visits `/capture/<screen>` for each screen in SCREENS and saves what it sees.
  * The *server* (`--serve`) is MapTasker's own start-up -- `mapit_all()` -- with one extra page
    registered, `/capture/<screen>`.  That page builds the real MyGui, loads the synthetic
    backup, runs the screen's setup (select a Task, press Edit, ...) and says it is ready.

The server runs isolated from your own data, which matters more than it sounds:

  * a scratch working directory -- MyGui reads and writes MapTasker_Settings.toml in the current
    directory;
  * a scratch HOME -- reports (Health Check, Variable Xref ...) are written to ~/Documents/MapTasker;
  * a do-nothing keyring -- MapTasker keeps your AI API keys in the system keychain, and the API Key
    dialog shows them in plain text.  A capture must never be able to read, show or change them.

The only backup it ever loads is tests/data/synthetic_backup.xml -- never anything from XML/.
`--serve` refuses to start unless that isolation is in place.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The tree MapTasker is run from.  Normally this one; --root points it at another checkout (a
# `git archive` of a commit, say, when this tree is in the middle of an edit and does not import).
RUN_ROOT = PROJECT_ROOT
DEFAULT_OUTPUT = PROJECT_ROOT / "screens"
VIEWPORT = {"width": 1440, "height": 1300}
# Toasts ("Settings restored.", "View Limit set to 10000." ...) pile up over the window as it builds.
HIDE_TOASTS = ".q-notifications { display: none !important; }"
READY_ATTRIBUTE = "captureReady"
ISOLATION_FLAG = "MAPTASKER_CAPTURE_ISOLATED"
NULL_KEYRING = "keyring.backends.null.Keyring"
BACKUP_VARIABLE = "MAPTASKER_CAPTURE_BACKUP"


@dataclass
class Screen:
    """One screen to photograph.

    name:    the PNG's file name (without .png) and the argument to --only.
    setup:   runs on the server, inside the page, after the window is built and the backup is
             loaded.  It receives the MyGui.  May be async.
    clicks:  texts for the driver to click, in order, once the page is ready -- for dialogs that
             open from inside another dialog.
    scroll_to: text of an element to scroll to the top of the window, for the views that are drawn
             below the controls (Tree, Misc).
    url:     a path to visit once the setup is done, for screens that are pages of their own (the
             Map and Diagram pop-outs).  The server keeps what the setup built.
    settle:  seconds to wait after the last step, for animations and streamed content.
    """

    name: str
    setup: Callable[[object], Awaitable[None] | None] | None = None
    clicks: list[str] = field(default_factory=list)
    scroll_to: str = ""
    url: str = ""
    settle: float = 0.8


SYNTHETIC_BACKUP = RUN_ROOT / "tests" / "data" / "synthetic_backup.xml"  # replaced by serve() with the scratch copy


# ################################################################################
# Server side
# ################################################################################
def select_item(gui: object, kind: str, name: str) -> None:
    """Select a Project/Profile/Task/Scene exactly as picking it from the pulldown does.

    The pulldown itself is moved too, the way select_single_item_export does it: the handler
    stores the selection but leaves the widget it came from to show it.
    """
    from maptasker.src.guiutils import select_pulldown_option

    gui.event_handlers.process_single_name_event(kind, name)
    optionmenu = getattr(gui, f"specific_{kind.lower()}_optionmenu", None)
    if optionmenu is not None:
        gui.is_updating = True
        try:
            select_pulldown_option(optionmenu, name)
            optionmenu.update()
        finally:
            gui.is_updating = False


def load_backup(gui: object) -> None:
    """Load the synthetic backup the way 'Get Local XML File' does, once a file is picked."""
    from maptasker.src.guiutils import (
        clear_single_item_view_names,
        reset_single_item_pulldowns,
        update_tasker_object_menus,
    )
    from maptasker.src.maputils import clear_tasker_data
    from maptasker.src.primitem import PrimeItems

    PrimeItems.file_to_get = str(SYNTHETIC_BACKUP)
    clear_tasker_data(state=PrimeItems)
    clear_single_item_view_names(gui)
    reset_single_item_pulldowns(gui)
    gui.current_file_display_message = False
    update_tasker_object_menus(gui, get_data=True, reset_single_names=True)


def nothing(_gui: object) -> None:
    """The window as it opens, with the synthetic backup loaded."""


def handler(name: str, *args: object, select: dict[str, str] | None = None) -> Callable[[object], object]:
    """A setup that selects what `select` names ({"Task": "Remind Me"}), then calls
    gui.event_handlers.<name>(*args) -- the same call the button makes."""

    def setup(gui: object) -> object:
        for kind, item in (select or {}).items():
            select_item(gui, kind, item)
        return getattr(gui.event_handlers, name)(*args)

    return setup


def helper_tasks(_gui: object) -> None:
    from maptasker.src.guiwins import build_helper_tasks_dialog

    build_helper_tasks_dialog(
        ["MapTasker Open Profile v1", "MapTasker Open Task v1"],
        ["MapTasker Open Profile v2", "MapTasker Open Task v2"],
        "192.168.0.210:1821",
    )


def helpers_in_the_way(_gui: object) -> None:
    from maptasker.src.guiwins import build_helpers_in_the_way_dialog

    build_helpers_in_the_way_dialog(
        ["MapTasker Open Profile v1", "MapTasker Open Task v1"], "192.168.0.210:1821", project_exists=True
    )


def overwrite_confirm(_gui: object) -> None:
    from maptasker.src.guiwins import build_overwrite_confirm_dialog

    build_overwrite_confirm_dialog("/Users/you/Documents/MapTasker/Remind Me.tsk.xml", lambda: None)


def round_trip_failed(_gui: object) -> None:
    from maptasker.src.guiwins import build_round_trip_report_dialog
    from maptasker.src.roundtrip import RoundTripReport

    build_round_trip_report_dialog(RoundTripReport(error="sample problem, shown for this screenshot"))


PROJECT = {"Project": "Reminders"}
PROFILE = {"Profile": "Morning Reminder"}
TASK = {"Task": "Remind Me"}
SCENE = {"Scene": "Reminder List"}


def edit_dialog_screens(
    key: str,
    kind: str,
    opener: str,
    select: dict[str, str],
    *,
    delete: str,
    properties: str = "Add Properties",
) -> list[Screen]:
    """The screens every Edit dialog has in common: what its Properties, Rename, Delete and
    Save to Android buttons open."""
    return [
        Screen(f"edit_{key}_properties", handler(opener, select=select), clicks=[properties]),
        Screen(f"edit_{key}_rename", handler(opener, select=select), clicks=["Rename"]),
        Screen(f"edit_{key}_delete", handler(opener, select=select), clicks=[delete], settle=1.2),
        Screen(f"edit_{key}_save_to_android", handler(opener, select=select), clicks=["Save To Android"]),
    ]


SCREENS: dict[str, Screen] = {
    s.name: s
    for s in [
        # ---- The main window ------------------------------------------------------------
        Screen("main", nothing),
        Screen("main_colors_tab", nothing, clicks=["Colors"]),
        Screen("main_analyze_tab", nothing, clicks=["Analyze"]),
        Screen("main_debug_tab", nothing, clicks=["Debug"]),
        Screen("main_project_selected", lambda gui: select_item(gui, "Project", "Reminders")),
        Screen("main_profile_selected", lambda gui: select_item(gui, "Profile", "Morning Reminder")),
        Screen("main_task_selected", lambda gui: select_item(gui, "Task", "Remind Me")),
        Screen("main_scene_selected", lambda gui: select_item(gui, "Scene", "Reminder List")),
        Screen("main_android_panel", nothing, clicks=["Get XML from Android Device"]),
        # ---- Help ------------------------------------------------------------------------
        Screen("help_display", handler("query_event", "help")),
        Screen("help_view_limit", handler("query_event", "viewlimit")),
        Screen("help_views", handler("query_event", "view")),
        Screen("help_ai_analyze", handler("query_event", "ai")),
        Screen("help_android", handler("query_event", "android")),
        Screen("help_list_files", handler("query_event", "listfile")),
        Screen("help_api_key", handler("query_event", "apikey")),
        Screen("whats_new", handler("whatsnew_event")),
        # ---- Editors ---------------------------------------------------------------------
        Screen("add_project", handler("open_add_project_dialog_event")),
        Screen("edit_project", handler("open_edit_project_dialog_event", select=PROJECT)),
        Screen("add_profile", handler("open_add_profile_dialog_event", select=PROJECT)),
        Screen("edit_profile", handler("open_edit_profile_dialog_event", select=PROFILE)),
        Screen("add_task", handler("open_add_task_dialog_event", select=PROJECT)),
        Screen("edit_task", handler("open_edit_task_dialog_event", select=TASK)),
        Screen("add_scene_type", handler("open_add_scene_dialog_event", select=PROJECT)),
        Screen("edit_scene", handler("open_edit_scene_dialog_event", select=SCENE)),
        Screen("run_task_on_android", handler("open_run_task_on_android_dialog_event", select=TASK)),
        # ---- Reports and tools -----------------------------------------------------------
        Screen("health_check_options", handler("health_check_event")),
        Screen("changes_since", handler("timeline_event")),
        Screen("refactor", handler("refactor_event")),
        Screen("fix_findings", handler("fix_findings_event")),
        Screen("restore_from_history", handler("restore_history_event")),
        Screen("what_fires_when", handler("fire_simulator_event")),
        Screen("variable_xref", handler("variable_xref_event"), scroll_to="Misc View"),
        Screen("task_flow", handler("task_flow_event", select=TASK), scroll_to="Misc View"),
        Screen("tree_view", handler("view_event", "tree"), scroll_to="Tree View"),
        # ---- Inside the Edit Task dialog -------------------------------------------------
        *edit_dialog_screens("task", "Task", "open_edit_task_dialog_event", TASK, delete="Delete Task"),
        Screen("edit_task_action_open", handler("open_edit_task_dialog_event", select=TASK), clicks=["0: Flash"]),
        Screen("edit_task_add_action", handler("open_edit_task_dialog_event", select=TASK), clicks=["Wait (Task)"]),
        Screen(
            "edit_task_app_not_listed", handler("open_edit_task_dialog_event", select=TASK), clicks=["App not listed?"]
        ),
        Screen("add_task_properties", handler("open_add_task_dialog_event", select=PROJECT), clicks=["Add Properties"]),
        # ---- Inside the Edit Project / Profile / Scene dialogs ----------------------------
        *edit_dialog_screens("project", "Project", "open_edit_project_dialog_event", PROJECT, delete="Delete Project"),
        *edit_dialog_screens("profile", "Profile", "open_edit_profile_dialog_event", PROFILE, delete="Delete Profile"),
        Screen(
            "edit_profile_condition_open", handler("open_edit_profile_dialog_event", select=PROFILE), clicks=["0: Time"]
        ),
        Screen("edit_profile_add_task", handler("open_edit_profile_dialog_event", select=PROFILE), clicks=["Add Task"]),
        Screen(
            "edit_profile_condition_types",
            handler("open_edit_profile_dialog_event", select=PROFILE),
            clicks=["css=.q-field:has-text('Condition Type')"],
        ),
        Screen("add_project_properties", handler("open_add_project_dialog_event"), clicks=["Add Properties"]),
        Screen(
            "add_profile_properties",
            handler("open_add_profile_dialog_event", select=PROJECT),
            clicks=["Add Properties"],
        ),
        *edit_dialog_screens(
            "scene", "Scene", "open_edit_scene_dialog_event", SCENE, delete="Delete Scene", properties="Edit Properties"
        ),
        Screen(
            "edit_scene_preview", handler("open_edit_scene_dialog_event", select=SCENE), clicks=["Preview"], settle=2
        ),
        Screen("edit_scene_add_component", handler("open_edit_scene_dialog_event", select=SCENE), clicks=["Add"]),
        Screen(
            "edit_scene_properties_panel",
            handler("open_edit_scene_dialog_event", select=SCENE),
            clicks=["Scene Properties"],
        ),
        # ---- Add Scene: the Legacy designer and the four Version 2 templates ---------------
        Screen("add_scene_legacy", handler("open_add_scene_dialog_event", select=PROJECT), clicks=["Legacy Scene"]),
        Screen(
            "add_scene_v2_empty", handler("open_add_scene_dialog_event", select=PROJECT), clicks=["Empty"], settle=1.5
        ),
        Screen(
            "add_scene_v2_titled_dialog",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Titled dialog"],
            settle=1.5,
        ),
        Screen(
            "add_scene_v2_dialog_buttons",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Dialog with buttons"],
            settle=1.5,
        ),
        Screen(
            "add_scene_v2_full_screen",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Full screen"],
            settle=1.5,
        ),
        # ---- The main window's other dialogs -----------------------------------------------
        Screen("api_keys", nothing, clicks=["Analyze", "Show/Edit API Key(s)"]),
        Screen("ai_prompt", nothing, clicks=["Analyze", "Change Prompt"]),
        Screen("debug_log", nothing, clicks=["Debug", "Display Log"]),
        Screen("color_picker", nothing, clicks=["Colors", "css=.q-btn:has(i:text('colorize'))"]),
        Screen("file_picker", nothing, clicks=["Get Local XML File"]),
        Screen("compare_files_picker", nothing, clicks=["Compare Files"]),
        Screen("edit_history", nothing, clicks=["Edit History"]),
        # ---- Reports, once run -------------------------------------------------------------
        Screen("health_check_report", handler("health_check_event"), clicks=["Run"], settle=2, scroll_to="Misc View"),
        Screen(
            "changes_since_report", handler("timeline_event"), clicks=["Show Changes"], settle=2, scroll_to="Misc View"
        ),
        # ---- The pop-out windows -----------------------------------------------------------
        Screen("map_view", handler("view_event", "map"), url="/popout/map?goto=&scope=", settle=3),
        Screen(
            "map_view_one_project",
            handler("view_event", "map", select=PROJECT),
            url="/popout/map?goto=&scope=Reminders",
            settle=3,
        ),
        Screen("diagram_view", handler("view_event", "diagram"), url="/popout/diagram?built_for=", settle=3),
        Screen("task_flow_view", handler("task_flow_event", select=TASK), url="/popout/flow", settle=3),
        Screen(
            "map_find_replace",
            handler("view_event", "map"),
            url="/popout/map?goto=&scope=",
            clicks=["Find/Replace"],
            settle=3,
        ),
        Screen(
            "map_replace_tab",
            handler("view_event", "map"),
            url="/popout/map?goto=&scope=",
            clicks=["Find/Replace", "Replace"],
            settle=3,
        ),
        Screen("map_export", handler("view_event", "map"), url="/popout/map?goto=&scope=", clicks=["Export"], settle=3),
        # ---- Scene property tabs and the designers' own dialogs -----------------------------
        Screen(
            "edit_scene_properties_actions",
            handler("open_edit_scene_dialog_event", select=SCENE),
            clicks=["Edit Properties", "Actions"],
        ),
        Screen(
            "edit_scene_properties_event",
            handler("open_edit_scene_dialog_event", select=SCENE),
            clicks=["Edit Properties", "Event"],
        ),
        Screen(
            "add_scene_legacy_add_element",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Legacy Scene", "Add"],
        ),
        Screen(
            "add_scene_legacy_properties",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Legacy Scene", "Add Properties"],
        ),
        Screen(
            "add_scene_v2_add_component",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Titled dialog", "Add"],
            settle=1.5,
        ),
        Screen(
            "add_scene_v2_show_when",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Titled dialog", "css=.q-btn:has(i:text('playlist_add'))"],
            settle=1.5,
        ),
        Screen(
            "add_scene_v2_modifiers",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Titled dialog", "Modifiers (2)"],
            settle=1.5,
        ),
        Screen(
            "add_scene_v2_preview",
            handler("open_add_scene_dialog_event", select=PROJECT),
            clicks=["Titled dialog", "Preview"],
            settle=2,
        ),
        # ---- Task editing prompts ----------------------------------------------------------
        Screen("edit_task_if_variant", handler("open_edit_task_dialog_event", select=TASK), clicks=["If (Task)"]),
        Screen(
            "edit_task_action_condition", handler("open_edit_task_dialog_event", select=TASK), clicks=["0: Flash", "If"]
        ),
        # ---- Dialogs that normally need an Android device, shown with sample values --------
        Screen("helper_tasks", helper_tasks),
        Screen("helpers_in_the_way", helpers_in_the_way),
        Screen("overwrite_confirm", overwrite_confirm),
        Screen("round_trip_failed", round_trip_failed),
    ]
}


def serve(port: int, root: Path) -> int:
    """Run MapTasker, from the tree at `root`, with the capture page added.  Blocks until the
    driver stops it."""
    if os.environ.get(ISOLATION_FLAG) != "1":
        sys.exit("--serve is internal: run the script without it, so the server starts isolated from your own data.")
    global SYNTHETIC_BACKUP  # noqa: PLW0603
    SYNTHETIC_BACKUP = Path(os.environ[BACKUP_VARIABLE])
    sys.path.insert(0, str(root))

    from maptasker.src.mapit import mapit_all
    from maptasker.src.primitem import PrimeItems
    from nicegui import ui

    real_run = ui.run

    def run_without_browser(*args: object, **kwargs: object) -> None:
        # rungui asks for show=True (open the user's browser) and for the first free port.
        kwargs.update(show=False, port=port)
        real_run(*args, **kwargs)

    ui.run = run_without_browser

    # The Map and Diagram buttons open a pop-out window; here the driver visits that page itself.
    from maptasker.src import userintr

    userintr._open_popout_window = lambda *_args, **_kwargs: None  # noqa: SLF001

    @ui.page("/capture/{name}")
    async def capture(name: str) -> None:
        from maptasker.src.userintr import MyGui

        screen = SCREENS[name]
        gui = MyGui(PrimeItems)
        await ui.context.client.connected()
        load_backup(gui)
        if screen.setup:
            result = screen.setup(gui)
            if asyncio.iscoroutine(result):
                await result
        await ui.run_javascript(f"document.body.dataset.{READY_ATTRIBUTE} = '1'")

    # Belt and braces: the environment was set by the driver, but check what actually took effect.
    import keyring

    if type(keyring.get_keyring()).__module__ != "keyring.backends.null":
        sys.exit("The system keyring is reachable; refusing to run where API keys could be read.")
    if not Path.home().resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
        sys.exit("HOME is not a scratch directory; refusing to run where real reports could be written.")

    sys.argv = ["maptasker"]
    return mapit_all()


# ################################################################################
# Driver side
# ################################################################################
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def server_python() -> str:
    """The interpreter that has MapTasker's dependencies: the project's own venv if there is one."""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def wait_for_server(port: int, process: subprocess.Popen, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            msg = f"The MapTasker server exited early with code {process.returncode}."
            raise RuntimeError(msg)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.3)
    msg = "The MapTasker server did not come up."
    raise RuntimeError(msg)


def click(page: object, text: str) -> None:
    """Click the control labelled `text` -- inside the topmost open dialog if there is one, so a
    "Delete" or "Cancel" under the dialog is never the one pressed.  "css=..." is a selector."""
    if text.startswith("css="):
        page.locator(text[4:]).first.click(timeout=10_000)
        return
    dialogs = page.locator(".q-dialog")
    scope = dialogs.last if dialogs.count() else page
    scope.get_by_text(text, exact=True).first.click(timeout=10_000)


def settle(page: object, screen: Screen) -> None:
    """Everything between the screen being ready and the picture: scroll, calm the pointer, wait."""
    if screen.scroll_to:
        page.get_by_text(screen.scroll_to, exact=True).first.evaluate("el => el.scrollIntoView({block: 'start'})")
    page.mouse.move(0, 0)  # no tooltip from the last click
    page.wait_for_timeout(int(screen.settle * 1000))


def inspect_labels(page: object) -> None:
    """Print what can be clicked on the page, topmost dialog first -- for writing a Screen's clicks."""
    dialogs = page.locator(".q-dialog")
    scope = dialogs.last if dialogs.count() else page.locator("body")
    labels = scope.evaluate(
        r"""el => [...el.querySelectorAll('.q-btn, .q-tab, .q-checkbox, .q-toggle, .q-expansion-item__container > .q-item, .q-field')]
              .filter(e => e.offsetParent !== null)
              .map(e => (e.className.match(/q-(btn|tab|checkbox|toggle|item|field)/) || [''])[0].slice(2) + ': '
                        + (e.innerText || e.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim())"""
    )
    print("\n".join(f"    {label}" for label in labels))


def capture_all(names: list[str], output: Path, scale: float, root: Path, inspect: bool = False) -> int:
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    port = free_port()
    workdir = Path(tempfile.mkdtemp(prefix="maptasker_capture_"))
    log_path = workdir / "server.log"
    home = workdir / "home"
    for folder in ("Desktop", "Documents", "Downloads"):
        (home / folder).mkdir(parents=True)
    # The backup lives in the scratch home, so the paths the reports print are not the real tree's.
    backup = home / "Documents" / "synthetic_backup.xml"
    shutil.copyfile(root / "tests" / "data" / "synthetic_backup.xml", backup)
    # Isolated from the user's own data -- see the module docstring.
    environment = {
        **{
            key: value
            for key, value in os.environ.items()
            if key not in ("XDG_CONFIG_HOME", "APPDATA")
            and not any(word in key.upper() for word in ("KEY", "TOKEN", "SECRET"))
        },
        "HOME": str(home),
        "PYTHON_KEYRING_BACKEND": NULL_KEYRING,
        ISOLATION_FLAG: "1",
        BACKUP_VARIABLE: str(backup),
    }
    failures: list[str] = []

    with log_path.open("w") as log:
        server = subprocess.Popen(  # noqa: S603
            [server_python(), str(Path(__file__).resolve()), "--serve", "--port", str(port), "--root", str(root)],
            cwd=workdir,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    try:
        try:
            wait_for_server(port, server)
        except RuntimeError as error:
            tail = "".join(log_path.read_text(errors="replace").splitlines(keepends=True)[-25:])
            print(f"{error}\n--- end of the server's log ---\n{tail}")
            return 1
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport=VIEWPORT, device_scale_factor=scale)
            for name in names:
                screen = SCREENS[name]
                page = context.new_page()
                try:
                    page.goto(f"http://127.0.0.1:{port}/capture/{name}")
                    page.wait_for_function(f"document.body.dataset.{READY_ATTRIBUTE} === '1'", timeout=30_000)
                    page.add_style_tag(content=HIDE_TOASTS)
                    if screen.url:
                        page.goto(f"http://127.0.0.1:{port}{screen.url}")
                    for text in screen.clicks:
                        click(page, text)
                    settle(page, screen)
                    if inspect:
                        print(f"  {name}:")
                        inspect_labels(page)
                        continue
                    target = output / f"{name}.png"
                    page.screenshot(path=str(target))
                    print(f"  ok    {target.name}")
                except Exception as error:  # noqa: BLE001 - report it and carry on with the rest
                    failures.append(name)
                    print(f"  FAIL  {name}: {str(error).splitlines()[0]}")
                finally:
                    page.close()
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        if failures:
            print(f"\nServer log kept at {log_path}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    print(f"\n{len(names) - len(failures)} of {len(names)} screens saved to {output}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a PNG of every MapTasker screen.")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--root", type=Path, default=PROJECT_ROOT, help="run MapTasker from this checkout instead of this one"
    )
    parser.add_argument("--only", nargs="+", metavar="SCREEN", help="capture just these screens")
    parser.add_argument("--inspect", action="store_true", help="print each screen's clickable labels instead of saving")
    parser.add_argument("--list", action="store_true", help="list the screens and exit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="where the PNGs go (default: ./screens)")
    parser.add_argument("--scale", type=float, default=1.0, help="device pixel ratio; 2 for retina-sharp images")
    args = parser.parse_args()

    if args.serve:
        return serve(args.port, args.root.resolve())
    if args.list:
        print("\n".join(SCREENS))
        return 0

    names = args.only or list(SCREENS)
    unknown = [name for name in names if name not in SCREENS]
    if unknown:
        parser.error(f"unknown screen(s): {', '.join(unknown)}; try --list")
    return capture_all(names, args.output, args.scale, args.root.resolve(), args.inspect)


if __name__ == "__main__":
    sys.exit(main())
