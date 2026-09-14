"""Handler the GUI for MapTasker"""

#! /usr/bin/env python3

#                                                                                      #
# rungui: process GUI for MapTasker                                                    #
#                                                                                      #
# Add the following statement (without quotes) to your Terminal Shell config file.     #
#  (BASH, Fish, etc.) to eliminate the runtime msg:                                    #
#  DEPRECATION WARNING: The system version of Tk is deprecated ...                     #
#  "export TK_SILENCE_DEPRECATION = 1"                                                 #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
import os
import socket
from typing import Any

from nicegui import core, ui

from maptasker.src import console
from maptasker.src.error import error_handler, exit_program
from maptasker.src.getputer import save_restore_args
from maptasker.src.guistate import capture_gui_state, do_colors, live_selection, reapply_selection
from maptasker.src.guiwins import NiceGuiTextView, inject_shared_head_styles, register_finding_clicks
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

# The port ui.run() gets.  DEFAULT_PORT is NiceGUI's own default and stays the port we use
# whenever it is free, so the GUI keeps showing up at the same familiar URL.
DEFAULT_PORT = 8080
LAST_FALLBACK_PORT = 8099


# ################################################################################
# Find a free port for the GUI's web server to listen on
# ################################################################################
def get_open_port(host: str = "127.0.0.1") -> int:
    """Return DEFAULT_PORT if it is free, otherwise the next free port above it.

    Do NOT hand ui.run() port=0 hoping for an OS-assigned port: NiceGUI's ui_run does
    'port = port or 8080', so 0 (falsy) silently becomes 8080 and a second instance dies
    with 'address already in use' before its window ever opens.

    Args:
        host: the interface ui.run() will bind to.  A port is only really free for the
            interface being bound, so test the same one.

    Returns:
        int: a port nothing else is currently listening on.
    """
    for port in range(DEFAULT_PORT, LAST_FALLBACK_PORT + 1):
        with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
            # Actually bind it: asking the OS is the only reliable answer, and binding
            # catches a port blocked by something other than a listener as well.
            test_socket.bind((host, port))
            return port

    # Every candidate is taken.  Hand back the default and let ui.run's OSError handler
    # below report the conflict rather than failing here with a less specific message.
    logger.error(f"No open port found between {DEFAULT_PORT} and {LAST_FALLBACK_PORT}.")
    return DEFAULT_PORT


# ################################################################################
# Convert a value to integere, and if not an integer then use default value
# ################################################################################
def convert_to_integer(value_to_convert: str, default_value: int) -> int:
    """
    Convert a value to integere, and if not an integer then use default value
        Args:
            value_to_convert (str): The string value to convert to an integer
            where_to_put_it (int): Where to place the converted integer
            default_value (int): The default to plug in if the value to convert
                is not an integer
            :return: converted value as integer"""
    try:
        return int(value_to_convert)
    except (ValueError, TypeError):
        return default_value


# Get the program arguments from GUI
# What each popped-out view is called, and the whole list of view types the "/popout/..."
# route will answer for.  The title is no longer derived from the path: "Task Flow" is two
# words, and NiceGuiTextView decides how to render a view by what its title starts with.
POPOUT_TITLES = {"map": "Map View", "diagram": "Diagram View", "flow": "Task Flow View"}


def process_gui(use_gui: bool) -> tuple[dict, dict]:
    # global MyGui
    """Parameters:
        - use_gui (bool): Flag to indicate whether to use GUI or not.
    Returns:
        - tuple[dict, dict]: Tuple containing program arguments and colors to use.
    Processing Logic:
        - Import MyGui if use_gui is True.
        - Set flag to indicate GUI usage.
        - Display GUI and get user input.
        - Initialize runtime arguments if not already set.
        - If user clicks "Exit" button, save settings and exit program.
        - If user closes window, cancel program.
        - If user clicks "Run" button, get input from GUI variables.
        - Set program arguments in dictionary.
        - Convert display_detail_level and indent to integers.
        - Get font from GUI.
        - Return program arguments and colors to use."""
    # CODE STARTS HERE
    logger.info("starting")

    # Imported here rather than at the top so that userintr, and the GUI modules it brings in,
    # load when the GUI starts -- not when rungui is imported, which is at startup, before
    # process_cli replaces program_arguments.  diagram writes a default into program_arguments
    # as it is imported, and at startup that write would be thrown away.
    if use_gui:
        from maptasker.src.userintr import MyGui  # noqa: PLC0415

    PrimeItems.program_arguments["gui"] = True

    # 1. Create a dictionary to hold our UI instance so we can retrieve it after the server closes
    shared_state = {}

    # Create a lock to prevent the browser from building the app multiple times
    app_lock = {"is_built": False}

    # 2. EXPLICITLY define the root page.
    @ui.page("/")
    def map_tasker_root() -> None:
        restart = False
        # What the session is on right now -- captured *before* MyGui() below re-runs the
        # settings restore over the top of it. See reapply_selection.
        carried_type, carried_name = live_selection()

        # Check if this is a page refresh/re-connection
        if app_lock["is_built"]:
            logger.info("Application refreshed or reconnected. Re-initializing user interface context.")
            # print("Application refreshed or reconnected. Re-initializing user interface context.")

            # Optional: Clear out any global data references that should reset on a clean page refresh
            if "user_input" in shared_state:
                restart = True
                del shared_state["user_input"]

        # Safely instantiate or overwrite the UI instance
        shared_state["user_input"] = MyGui()
        # Mark as built so the application tracks that initialization has occurred
        app_lock["is_built"] = True
        if restart:
            # Only after a rebuild: on the very first build there is no live session to
            # carry over, and the settings file is the right source.
            reapply_selection(shared_state["user_input"], carried_type, carried_name)
            # The old "Please re-enter your inputs" wording is no longer true of the thing
            # people actually lost -- the selection now survives -- so say what did happen.
            message = "This window was rebuilt from your saved settings."
            if carried_name:
                message += f" Still showing {carried_type}: {carried_name}."
            ui.notify(message, color="orange", position="bottom")

    # 2b. Pop-out page for the Map, Diagram and Task Flow views, opened in their own browser
    # window/tab (see MapTaskerEventHandlers.view_event in userintr.py) so they no longer replace the
    # main window's content. Reuses the single shared MyGui instance (PrimeItems.mygui) rather
    # than building a new one, since this is a single-user, single-server-process desktop app.
    @ui.page("/popout/{view_type}")
    def popout_view(view_type: str, goto: str = "", scope: str = "", built_for: str = "") -> None:
        """The Map, the Diagram or a Task's flowchart in its own window.

        'goto' is a mapjump token, put on the URL by a clicked report finding that needed a
        Map built for it (see MapTaskerEventHandlers.rebuild_map_for_jump).  It travels on
        the URL rather than being pushed into this window afterwards because this page is
        the only thing that knows when its content has finished streaming in and is
        therefore scrollable.  NiceGUI hands a page function its query parameters, so it
        arrives here as an ordinary argument.

        'scope' is the Project the Map in this window was built for ("" for all of them),
        recorded on the view so a later clicked finding can tell whether this window can
        show what it points at -- see guiwins.jump_map_view.

        'built_for' is the whole of what the app was displaying when this view was drawn --
        "Project 'Home'", "Task 'Wake Up'", "" for the whole configuration -- which is what
        the view's own toolbar says, and what it compares against to tell the user the
        selection has moved on since (see NiceGuiTextView._build_scope_badge).  Distinct
        from 'scope' because that one is a Project NAME and is compared against a jump's
        own; this one is a phrase, and is only ever read by a human.
        """
        gui = PrimeItems.mygui
        # The Task Flow view has nothing on disk to fall back on: its chart lives on
        # PrimeItems and dies with the process.  Reopening this URL in a new session (a
        # restored browser tab, a bookmark) therefore has to say so rather than render an
        # empty page -- which is the same thing this route already says when there is no
        # GUI to reach at all.
        stale = view_type == "flow" and not PrimeItems.taskflow_rows
        if gui is None or stale or view_type not in POPOUT_TITLES:
            ui.label(
                "No data available. Please generate this view from the main MapTasker window first.",
            ).classes("text-red-500 text-lg m-8")
            return

        window_title = POPOUT_TITLES[view_type]
        ui.page_title(f"MapTasker - {window_title}")

        # Each @ui.page is its own independent document, so the main window's CSS (injected
        # once via initialize_screen() -> inject_shared_head_styles()) doesn't carry over here.
        # Without this, the Diagram view's connector click handler still fires but has no
        # .connector-highlight rule to apply, so nothing visibly highlights.
        inject_shared_head_styles()

        # NiceGUI wraps every page's content in a padded ".nicegui-content" div; strip that
        # padding here so the view below can actually reach the browser's full width/height
        # instead of being inset by it.
        ui.query(".nicegui-content").classes(replace="w-full h-screen p-0 m-0 gap-0")

        # While this page is still being BUILT, exactly as initialize_screen does it for the
        # main window, and for the reason register_finding_clicks gives: ui.on subscribes on
        # client.layout, and adding a listener to an element the browser already holds makes
        # NiceGUI throw that element away and let Vue rebuild it -- the whole page's element
        # tree, and the "Event listeners changed after initial definition" warning in the log.
        # The view rendered below registers it too, from its own background task; that call
        # is a no-op once this one has run (see the guard on _FINDING_CLICK_CLIENTS), which
        # is what makes doing it here a fix rather than a duplicate.
        register_finding_clicks(gui)

        popout_container = ui.column().classes("w-full h-screen")
        gui.textview = NiceGuiTextView(
            gui,
            title=window_title,
            # A dict means "this is the Map" to NiceGuiTextView (see its is_map).  Every
            # other popped-out view is handed nothing and finds its own content: the
            # Diagram re-reads its generated file, the Task Flow view reads the rows
            # taskflow left on PrimeItems.
            the_data={} if view_type == "map" else [],
            container=popout_container,
            jump_to=goto,
            map_scope=scope,
            built_for=built_for,
        )

    logger.info("Starting NiceGUI server mainloop")

    # =========================================================================
    # Intercept all interactions with the UI to save MyGui to PrimeItems and shared_state
    # from nicegui import core, ui
    # 1. Save a reference to NiceGUI's core Socket.IO emitter function
    _original_sio_emit = core.sio.emit

    # 2. Define the interception proxy function
    async def intercepted_sio_emit(
        event: ui.Event,
        data: dict | None = None,
        room: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        # Grab your active MyGui instance securely from global state tracking
        my_gui_instance = getattr(PrimeItems, "mygui", None)

        if my_gui_instance:  # noqa: SIM102
            # You have full structural access to your MyGui class properties here!
            # Save program arguments and colors to use in PrimeItems
            if hasattr(my_gui_instance, "event") and my_gui_instance.event:
                my_gui_instance.event = False  # Reset the event flag after processing

                capture_gui_state(my_gui_instance, data)

        # Always forward execution to the original emitter so the browser communicates!
        await _original_sio_emit(event, data=data, room=room, **kwargs)

    # 3. Apply the monkey-patch directly to the core server emitter instance
    core.sio.emit = intercepted_sio_emit

    # 4. Point to the icon directory fore our favicon.
    abspath = os.path.abspath(__file__)
    assets_dir = os.path.dirname(abspath).replace("src", f"assets{PrimeItems.slash}icons")

    # =========================================================================

    # 5. Start the server (This will now properly block without running main() twice)
    try:
        ui.run(
            reload=False,
            host="127.0.0.1",
            # storage_secret="maptasker_gui_storage",  # Only needed if using either app.storage.user or app.storage.browser
            title="MapTasker",
            port=get_open_port(),  # Avoid a port conflict with another instance already running
            dark=None,
            show=True,
            cache_control_directives="no-store, no-cache, must-revalidate",  # Forces immediate network state clears
            reconnect_timeout=10.0,  # Keeps a brief signal blip from clearing out memory singles
            favicon=f"{assets_dir}{PrimeItems.slash}Animated Gear.gif",
        )
    except OSError as e:
        logger.error(f"Error starting GUI: {e}")
        if "Address already in use" in str(e):
            error_handler(
                "Error: Address already in use. Please close any other instances of MapTasker or change the port.",
                100,  # Force an exit.
            )

    logger.info("GUI closed. Cleaning up...")
    console.say("MapTasker GUI closed. Cleaning up...")

    # 4. Retrieve the state created by the web browser session
    user_input = shared_state.get("user_input")

    # If the user closed the window/browser without the UI building
    if not user_input:
        error_handler("Program exited. Goodbye.", 0)
        exit_program(0)

    # Establish our runtime default values if we don't yet have 'em.
    if not PrimeItems.colors_to_use:
        PrimeItems.program_arguments = initialize_runtime_arguments()

    # Move user_input values into our program_arguments dictionary and colors_to_use dictionary
    capture_gui_state(user_input, {})

    # Hide the Ai key so when settings are saved, it isn't written to toml file.
    ai_apikey = getattr(user_input, "ai_apikey", None)
    if ai_apikey is not None and ai_apikey:
        PrimeItems.ai["api_key"] = ai_apikey
        PrimeItems.program_arguments["ai_apikey"] = "HIDDEN"

    # Convert display_detail_level to integer
    PrimeItems.program_arguments["display_detail_level"] = convert_to_integer(
        PrimeItems.program_arguments["display_detail_level"],
        4,
    )
    # Convert indent to integer
    PrimeItems.program_arguments["indent"] = convert_to_integer(
        PrimeItems.program_arguments["indent"],
        4,
    )

    # Save our runtime settings.
    _, _ = save_restore_args(
        PrimeItems.program_arguments,
        PrimeItems.colors_to_use,
        to_save=True,
    )
    # Spit out the message and log it.
    error_handler("Program exited. Goodbye.", 0)

    # Call it quits.
    exit_program(0)

    # Return the program arguments and colors to use.
    return (PrimeItems.program_arguments, do_colors(user_input))
