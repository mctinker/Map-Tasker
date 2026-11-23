"""versiondisplay: what 'maptasker -v' says -- the banner, the version and the licence -- with nothing else loaded."""

#! /usr/bin/env python3

#                                                                                        #
# versiondisplay: the version banner, kept apart from the rest of the program.           #
#                                                                                        #
# Asking for the version should not cost what starting MapTasker costs.  Everything this   #
# module needs is small -- the console, the banner's colours and animation -- and none of  #
# it is the GUI, the argument parser or the Tasker analysis, which are what take half a    #
# second to import.  main.py therefore reaches for this module first when the only thing   #
# asked is '-v', and leaves the rest unimported (see maptasker.main).                      #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
from __future__ import annotations

import contextlib
import ctypes
import sys
from typing import Any

import darkdetect  # pyright: ignore[reportMissingTypeStubs]  (no stubs are published for it)

from maptasker.src.core import console
from maptasker.src.core.clip import clip_figure
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.sysconst import MY_LICENSE, MY_VERSION, Colors

# Add some pazaazz to the version identifier
_BANNER_PROBE = "█╗"  # A full block and a box corner: what the banner is drawn with.


def stream_can_show_the_banner() -> bool:
    """Whether the terminal's encoding can write the banner's block characters.

    A Windows console in a legacy code page (cp1252, or cp437 over a pipe) cannot, and printing them raises
    UnicodeEncodeError -- so asking for the version produced a traceback, or in a window that closes at once, nothing.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        _BANNER_PROBE.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


_STD_OUTPUT_HANDLE = -11
_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def enable_ansi_on_windows() -> None:
    """Have a Windows console act on the colour and cursor codes the banner is written with.

    Python does not switch virtual-terminal processing on by itself, so a console that has not had it switched on shows
    the codes as text.  Does nothing anywhere else, and nothing where the output is not a console (a pipe has no mode
    to set), and cannot fail the run: the banner is decoration.
    """
    if sys.platform != "win32":
        return
    windll: Any = getattr(ctypes, "windll", None)
    if windll is None:
        return
    with contextlib.suppress(OSError, AttributeError):
        handle = windll.kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        if windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            windll.kernel32.SetConsoleMode(handle, mode.value | _VIRTUAL_TERMINAL_PROCESSING)


def display_version() -> None:
    """
    Display the version of the program.

    This function prints the program version and license information to the console.
    It also displays an ASCII art header with the program name.

    Parameters:
        None

    Returns:
        None
    """
    header = f"""

    {Colors.Purple}


███╗   ███╗ █████╗ ██████╗     ████████╗ █████╗ ███████╗██╗  ██╗███████╗██████╗
████╗ ████║██╔══██╗██╔══██╗    ╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗
██╔████╔██║███████║██████╔╝       ██║   ███████║███████╗█████╔╝ █████╗  ██████╔╝
██║╚██╔╝██║██╔══██║██╔═══╝        ██║   ██╔══██║╚════██║██╔═██╗ ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║██║  ██║██║            ██║   ██║  ██║███████║██║  ██╗███████╗██║  ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝            ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

"""
    color_to_use = Colors.Yellow if darkdetect.isDark() else Colors.Blue
    enable_ansi_on_windows()
    # The banner and the animation are decoration and the version is the point: where the terminal cannot show them
    # (see stream_can_show_the_banner) or is not a terminal at all (a pipe, a redirect), the version is still said.
    can_draw = stream_can_show_the_banner()
    if can_draw:
        console.say(header)
    console.say(f"{color_to_use}{MY_VERSION}, under license {MY_LICENSE}\033[0m")
    console.say("")
    if can_draw and bool(getattr(sys.stdout, "isatty", lambda: False)()):
        clip_figure("castles", False)
    raise MapTaskerError(exit_code=0)
