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
from typing import TYPE_CHECKING, Any

from nicegui import core, ui

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.getputer import save_restore_args
from maptasker.src.guiwins import NiceGuiTextView, inject_shared_head_styles
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputils import exit_program
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES, logger

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


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


# The single-item selection the running session is on.  Mutually exclusive -- at most one is
# ever set -- and each is mirrored on the MyGui instance as single_<x>_name.
SELECTION_KEYS = (
    "single_project_name",
    "single_profile_name",
    "single_task_name",
    "single_scene_name",
)


def live_selection() -> tuple[str, str]:
    """The (item type, name) the running session currently has selected, or ("", "").

    Read out of PrimeItems.program_arguments rather than off the MyGui instance, because
    that is the copy which survives the instance being replaced on a rebuild.  item_type
    comes back as "Project"/"Profile"/"Task"/"Scene" -- the vocabulary process_name_event
    and the specific_<x>_optionmenu attribute names both use.
    """
    for key in SELECTION_KEYS:
        name = PrimeItems.program_arguments.get(key, "")
        if name and name != "None":
            return key.removeprefix("single_").removesuffix("_name").capitalize(), name
    return "", ""


def reapply_selection(gui: MyGui, item_type: str, name: str) -> None:
    """Put a rebuilt window back on the selection the session was already using.

    Rebuilding the UI -- for a page reload, or because a second window opened -- constructs
    a fresh MyGui, and that re-runs the settings-file restore over PrimeItems.program_arguments.
    So any selection made since the last save was silently discarded: opening a second tab,
    or an accidental refresh, dropped the current Project/Profile/Task/Scene out from under
    the running session and brought the new window up on a stale one, or none at all.
    map_tasker_root captures it before the rebuild and hands it back here afterwards.

    Goes through process_name_event -- the same path a user picking the name by hand takes --
    so the pulldown, the "Display only ..." label and program_arguments all end up consistent,
    rather than this setting each of them itself and drifting from that path later.

    Guarded because a name that no longer resolves (its Project deleted from another window,
    say) must not stop the window from finishing its build; losing the selection is a far
    smaller problem than a half-built GUI.
    """
    if not item_type:
        return
    with contextlib.suppress(Exception):
        gui.event_handlers.process_name_event(item_type, name)


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


# Get the colors to use.
def do_colors(user_input: MyGui) -> dict:
    """Sets color mode and processes colors.
    Parameters:
        - user_input (dict): User input dictionary containing appearance mode and color lookup.
    Returns:
        - colormap (dict): Dictionary of colors after processing.
    Processing Logic:
        - Set color mode based on user input.
        - Process color lookup if provided.
        - Set flag for GUI usage."""

    # Appearance change: Dark or Light mode?
    colormap = set_color_mode(user_input.appearance_mode)

    # Process the colors
    color_lookup = getattr(user_input, "color_lookup", None)
    if color_lookup is not None and color_lookup:
        for key, value in color_lookup.items():
            colormap[key] = value

    PrimeItems.program_arguments["gui"] = True  # Set flag to indicate we are using GUI

    return colormap


def get_first_text_entry(data: dict) -> str:
    """
    Get the first data element, looking for the text command (i.e. checkbox label)

    Args:
        data (dict): The sio data dictionary containing GUI state information.

    Returns:
        str: The text value of the first entry if available, otherwise an empty string.
    """
    # 1. Determine if data is a dictionary
    if isinstance(data, dict) and data:
        # 2. Get the first value in the dictionary
        first_value = next(iter(data.values()))

        # 3. Check if the first value is also a dict and contains 'text'
        if isinstance(first_value, dict) and "text" in first_value:
            return first_value["text"]

    return ""


def capture_gui_state(user_input: MyGui, data: dict) -> None:
    """Capture the current state of the GUI and save it to PrimeItems.
    Parameters:
        - user_input (MyGui): The user input object containing GUI state.
        - data (dict): The data dictionary containing GUI state information.
    """
    # Check to see if it is a specific entry:
    if data and "Prettier" in get_first_text_entry(data):
        PrimeItems.program_arguments["pretty"] = user_input.pretty

    # Do the entire enchillada if it is not a specific entry:
    else:
        for value in ARGUMENT_NAMES:
            with contextlib.suppress(AttributeError):
                PrimeItems.program_arguments[value] = getattr(user_input, value)
                logger.info(
                    f"GUI arg: {value} set to: {PrimeItems.program_arguments[value]}",
                )
        PrimeItems.program_arguments["display_detail_level"] = int(
            PrimeItems.program_arguments["display_detail_level"],
        )
        PrimeItems.program_arguments["indent"] = int(PrimeItems.program_arguments.get("indent", 4))
        # Update colors based on the current MyGui instance
        PrimeItems.colors_to_use = do_colors(user_input)


# Get the program arguments from GUI
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

    # Keep this here to avoid circular import.  We only need to import MyGui if we are using the GUI,
    # and this is the only place we need it.
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

    # 2b. Pop-out page for the Map and Diagram views, opened in their own browser window/tab
    # (see MapTaskerEventHandlers.view_event in userintr.py) so they no longer replace the
    # main window's content. Reuses the single shared MyGui instance (PrimeItems.mygui) rather
    # than building a new one, since this is a single-user, single-server-process desktop app.
    @ui.page("/popout/{view_type}")
    def popout_view(view_type: str) -> None:
        gui = PrimeItems.mygui
        if gui is None or view_type not in ("map", "diagram"):
            ui.label(
                "No data available. Please generate this view from the main MapTasker window first.",
            ).classes("text-red-500 text-lg m-8")
            return

        window_title = f"{view_type.capitalize()} View"
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

        popout_container = ui.column().classes("w-full h-screen")
        gui.textview = NiceGuiTextView(
            gui,
            title=window_title,
            the_data={} if view_type == "map" else [],
            container=popout_container,
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
    print("MapTasker GUI closed. Cleaning up...")

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
