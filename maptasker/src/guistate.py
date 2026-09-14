"""guistate: what the running GUI hands back to the rest of MapTasker.

The GUI's widgets live on MyGui; everything else reads PrimeItems.program_arguments.  This
is the copy between the two -- capture_gui_state, and held_overrides for a build that needs
settings the widgets do not hold -- together with the single-item selection the session is on.

Split out of rungui, which starts the web server and builds MyGui, because userintr needs
these as well: importing them from rungui tied the two modules into a loop.  Nothing here
imports either of them at run time.
"""

#! /usr/bin/env python3

#                                                                                      #
# guistate: copy the GUI's state into program_arguments, and hold overrides            #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from maptasker.src.colrmode import set_color_mode
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import ARGUMENT_NAMES, logger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from maptasker.src.userintr import MyGui


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
    rungui's map_tasker_root captures it before the rebuild and hands it back here afterwards.

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


# Settings one view build needs that the GUI's own widgets do not hold -- see
# MapTaskerEventHandlers.rebuild_map_for_jump, which builds a Map of the Project a clicked
# report finding lives in while the pulldowns still name whatever single item the user was
# looking at.
#
# They are held here, and re-asserted by capture_gui_state below, rather than simply written
# into program_arguments once, because capture_gui_state does not only run where a view build
# calls it: intercepted_sio_emit runs it from NiceGUI's outbox loop for any message that goes
# out while gui.event is set, and view_event sets that flag for the whole of the build.  A
# notification emitted while the Map was being built therefore copied the GUI's own
# single-item selection straight back over the overrides, mid-build, and the Map came out
# showing that item instead of the Project that was clicked -- leaving the finding's anchor
# nowhere in it and the view reporting "Built the Map, but it has no line for ...".
#
# Whether that landed before or after the build had read the values it needed was pure
# timing, which is why it showed on Windows and not on macOS.  Re-asserting them takes the
# timing out of it: for as long as a build holds overrides, no capture can undo them.
_active_overrides: dict = {}


@contextlib.contextmanager
def held_overrides(overrides: dict | None) -> Iterator[None]:
    """Put `overrides` into program_arguments and KEEP them there for the duration of a build.

    The caller still owns putting the original values back afterwards -- this only guarantees
    that nothing quietly reverts them while the build that needs them is still running.

    Nested rather than replaced, and restored to exactly what was held before, so that this
    says nothing about whether builds can overlap; it just cannot be the thing that breaks if
    they ever do.
    """
    global _active_overrides  # noqa: PLW0603
    if not overrides:
        yield
        return
    previous = _active_overrides
    _active_overrides = {**previous, **overrides}
    PrimeItems.program_arguments.update(overrides)
    try:
        yield
    finally:
        _active_overrides = previous


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

    # A build in flight outranks whatever the widgets currently say: its overrides go back on
    # top of everything captured above.  No-op unless one is actually holding some.
    PrimeItems.program_arguments.update(_active_overrides)
