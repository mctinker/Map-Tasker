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
from typing import TYPE_CHECKING, Any

from nicegui import core, ui

from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import error_handler
from maptasker.src.getputer import save_restore_args
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputils import exit_program
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES, logger

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


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
def do_colors(user_input: dict) -> dict:
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
    # Chexk to see if it is a specific entry:
    if "Prettier" in get_first_text_entry(data):
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
        PrimeItems.program_arguments["indent"] = int(
            PrimeItems.program_arguments["indent"],
        )
        # Update colors based on the current MyGui instance
        PrimeItems.colors_to_use = do_colors(user_input)


# Get the program arguments from GUI
def process_gui(use_gui: bool) -> tuple[dict, dict]:
    """
    Process the graphical user interface for MapTasker using NiceGUI.

    This function initializes the web-server environment, handles circular imports
    for the GUI layout engine, setups WebSocket interaction logging filters, and blocks
    execution via a local web server loop until the client session disconnects. On server
    termination, it commits active session properties to disk and closes the parent process.

    Args:
        use_gui (bool): Flag indicating whether the graphical interface should be invoked.

    Returns:
        tuple[dict, dict]: Formatted program runtime arguments and colors lookup map
                           (Note: This function completes execution internally via
                           exit_program() and typically does not hit standard returns).

    Processing Logic:
        - Dynamically imports MyGui when use_gui is active to prevent module loops.
        - Clears out vestigial desktop Tkinter window fragments if they exist.
        - Maps a native single-instance root path page target equipped with disconnect
          auto-termination safety hooks.
        - Monkey-patches the core Socket.IO server layer to dynamically filter, log,
          and serialize active visual properties to program state properties during use.
        - Starts the blocking local uvicorn app instance server pool.
        - Extracts the post-session variables block configuration from the browser state tracking cache.
        - Sanitizes input types, filters critical security values (like API keys),
          and dumps configurations down to the backend runtime settings binary save files.
        - Shuts down the backend execution engine via early script termination.
    """
    # CODE STARTS HERE
    logger.info("starting")

    # Keep this here to avoid circular import.  We only need to import MyGui if we are using the GUI,
    # and this is the only place we need it.
    if use_gui:
        from maptasker.src.userintr import MyGui  # noqa: PLC0415

    PrimeItems.program_arguments["gui"] = True

    # Get rid of any previous Tkinter window
    if PrimeItems.tkroot is not None:
        del PrimeItems.tkroot
        PrimeItems.tkroot = None

    # 1. Create a dictionary to hold our UI instance so we can retrieve it after the server closes
    shared_state = {}

    # Create a lock to prevent the browser from building the app multiple times
    app_lock = {"is_built": False}

    # 2. EXPLICITLY define the root page.
    @ui.page("/")
    def map_tasker_root() -> None:

        # If the browser tries to refresh or open a second tab, block it!
        if app_lock["is_built"]:
            ui.label("MapTasker is already running!").classes("text-3xl text-red-600 font-bold m-8")
            ui.label("Please check your other open browser tabs to use the application.").classes("text-lg ml-8")
            return

        print("bingo starting MyGui")
        shared_state["user_input"] = MyGui()

        # Lock the door behind us
        app_lock["is_built"] = True

        # =========================================================================
        # METHOD 1 INTERCEPTION: ACCIDENTAL TAB/BROWSER CLOSE DISCONNECT HOOK
        # =========================================================================
        async def on_client_disconnect() -> None:
            import traceback

            logger.warning("📡 on_client_disconnect was triggered!")
            # Log the current execution frame stack to see what led here
            logger.warning(f"Disconnect Stack:\n{''.join(traceback.format_stack())}")
            logger.info("📡 Browser tab closed by user! Initiating automatic state save...")

            # Grab your active MyGui instance securely from global state tracking
            my_gui_instance = getattr(PrimeItems, "mygui", None)

            if my_gui_instance:
                # Do any special processing here if needed.  Code will then fall-thru the 'ui.run' and exit normally.
                pass

            # Shut down the local NiceGUI web server gracefully instead of leaving it hanging
            # app.shutdown()

        # Connect the event listener callback directly to this active browser page client session
        ui.context.client.on_disconnect(on_client_disconnect)
        # =========================================================================

    # ===================================================================================
    # Intercept all interactions with the UI to save MyGui to PrimeItems and shared_state
    # ===================================================================================
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
        # print("bingo intercepted_sio_emit event:", event, "data:", data, "room:", room, "kwargs:", kwargs)
        # print("bingo")

        if my_gui_instance:  # noqa: SIM102
            # You have full structural access to your MyGui class properties here!
            # Save program arguments and colors to use in PrimeItems
            if hasattr(my_gui_instance, "event") and my_gui_instance.event:
                my_gui_instance.event = False  # Reset the event flag after processing

                capture_gui_state(my_gui_instance, data)

        # Always forward execution to the original emitter so the browser communicates!
        try:
            await _original_sio_emit(event, data=data, room=room, **kwargs)
        except Exception as sio_err:
            logger.error(f"💥 Socket.IO Emitter crashed during event '{event}': {sio_err}")
            import traceback

            logger.error(traceback.format_exc())
            raise sio_err

    # 3. Apply the monkey-patch directly to the core server emitter instance
    core.sio.emit = intercepted_sio_emit
    # =========================================================================

    # 3. Start the server (This will now properly block without running main() twice)
    print("bingo ui.run")
    try:
        ui.run(
            reload=False,
            host="127.0.0.1",
            storage_secret="maptasker_gui_storage",
            title="MapTasker",
            port=0,
            dark=None,
            show=True,
        )
    except SystemExit as se:
        print(f"bingo 🚨 ui.run exited via a hard SystemExit! Code: {se.code}")
        import traceback

        print(traceback.format_exc())
    except Exception as e:
        print(f"bingo 🚨 ui.run crashed due to an unhandled exception: {e!s}")
        import traceback

        print(traceback.format_exc())

    logger.info("GUI closed. Processing arg∑uments...")
    print("bingo gui closed. Processing arguments...")

    # DROP HERE ON EXIT OF GUI.  Now we can retrieve the user input from shared_state and process it.
    # 4. Retrieve the state created by the web browser session
    user_input = shared_state.get("user_input")

    # If the user closed the window/browser without the UI building
    if not user_input:
        error_handler("Program exited. Goodbye.", 0)
        exit_program(0)

    # Establish our runtime default values if we don't yet have 'em.
    if not PrimeItems.colors_to_use:
        PrimeItems.program_arguments = initialize_runtime_arguments()

    # Do we already have the file object?
    if value := user_input.file:
        PrimeItems.file_to_get = value if isinstance(value, str) else value.name

    # Hide the Ai key so when settings are saved, it isn't written to toml file.
    ai_apikey = getattr(user_input, "ai_apikey", None)
    if ai_apikey is not None and ai_apikey:
        PrimeItems.ai["api_key"] = ai_apikey
        PrimeItems.program_arguments["ai_apikey"] = "HIDDEN"

    # Get the program arguments and save them in our dictionary
    for value in ARGUMENT_NAMES:
        with contextlib.suppress(AttributeError):
            PrimeItems.program_arguments[value] = getattr(user_input, value)
            logger.info(
                f"GUI arg: {value} set to: {PrimeItems.program_arguments[value]}",
            )

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
    # Get the font
    if the_font := user_input.font:
        PrimeItems.program_arguments["font"] = the_font

    # Save the runtime settings and exit.
    _, _ = save_restore_args(
        PrimeItems.program_arguments,
        PrimeItems.colors_to_use,
        to_save=True,
    )
    # Spit out the message and log it.
    error_handler("Program exited. Goodbye.", 0)

    # Call it quits.
    exit_program(0)
