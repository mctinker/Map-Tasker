"""Assign Default Colors"""

#! /usr/bin/env python3

#                                                                                      #
# colrmode: set the program colors based on color mode: dark or light                  #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
from __future__ import annotations

from typing import TYPE_CHECKING, cast

import darkdetect  # pyright: ignore[reportMissingTypeStubs]  (no stubs are published for it)

from maptasker.src.core.htmlsafe import css_color, is_dark_color

if TYPE_CHECKING:
    from collections.abc import Mapping


def set_color_mode(appearance_mode: str) -> dict[str, str]:
    """
    Given the color mode to use (dark or light), set the colors appropriately
       :param appearance_mode: color mode: dark or light
       :return new colormap of colors to use in the output
    """
    # Deal with "System" color mode
    mode = ("dark" if darkdetect.isDark() else "light") if appearance_mode == "system" else appearance_mode

    # Now set the colors to use based on the appearance mode
    if mode == "dark":
        return {
            "project_color": "White",
            "profile_color": "Aqua",
            "disabled_profile_color": "Red",
            "launcher_task_color": "GreenYellow",
            "task_color": "Yellow",
            "unknown_task_color": "Red",
            "scene_color": "Lime",
            "action_name_color": "Gold",
            "action_color": "DarkOrange",
            "action_label_color": "Magenta",
            "action_condition_color": "PapayaWhip",
            "disabled_action_color": "Crimson",
            "profile_condition_color": "LightGrey",
            "background_color": "222623",
            "trailing_comments_color": "PeachPuff",
            "taskernet_color": "LightPink",
            "preferences_color": "PeachPuff",
            "highlight_color": "DarkTurquoise",
            "heading_color": "LimeGreen",
        }

    return {
        "project_color": "Black",
        "profile_color": "DarkBlue",
        "disabled_profile_color": "DarkRed",
        "launcher_task_color": "LawnGreen",
        "task_color": "DarkGreen",
        "unknown_task_color": "MediumVioletRed",
        "scene_color": "Purple",
        "action_color": "DarkSlateGray",
        "action_name_color": "Indigo",
        "action_label_color": "MediumOrchid",
        "action_condition_color": "Brown",
        "disabled_action_color": "IndianRed",
        "profile_condition_color": "DarkSlateGray",
        "background_color": "Lavender",
        "trailing_comments_color": "Tomato",
        "taskernet_color": "RoyalBlue",
        "preferences_color": "DodgerBlue",
        "highlight_color": "Yellow",
        "heading_color": "DarkSlateGray",
    }


# What the settings file's [colors_to_use] means: the colours the user chose, laid over the palette of the
# appearance mode the file was saved in -- and nothing else.  Saving writes only the colours that differ from that
# palette (color_overrides); reading lays what the file holds over it (effective_colors).  So the section is empty
# for someone who never changed a colour, a palette written by an older version is simply a long list of overrides,
# and a colour the file does not mention is the mode's own rather than anything made up for it.
def _mode_of(appearance_mode: object) -> str:
    """The appearance mode to take a palette from: the one given, or "system" (the default) when there is none."""
    return appearance_mode if isinstance(appearance_mode, str) and appearance_mode else "system"


def _named_colors(colors: object) -> dict[str, str]:
    """The entries of `colors` that are a colour named by text: what a hand-edited file or a crash can spoil is dropped.

    "msg" is how a settings file that could not be read is reported (getputer.corrupted_file); it is not a colour.
    """
    if not isinstance(colors, dict):
        return {}
    entries = cast("dict[object, object]", colors)
    return {
        name: value
        for name, value in entries.items()
        if isinstance(name, str) and isinstance(value, str) and value and name != "msg"
    }


def effective_colors(saved: object, appearance_mode: object) -> dict[str, str]:
    """The colours in force: the appearance mode's palette, with the colours saved for it laid over it."""
    return {**set_color_mode(_mode_of(appearance_mode)), **_named_colors(saved)}


def chosen_background(colors: Mapping[str, str] | object, appearance_mode: object) -> str:
    """The Background colour the user chose, as CSS wants it, or "" when they have not chosen one.

    "Background" is the colour of the output (the Map, and every other view) and the palette gives it a default of
    its own -- Lavender in light mode.  The window around the output has always had its own colours, and painting
    it with the palette's default would change how everyone's window looks without anyone having asked.  So only a
    Background that differs from the palette's is the user's choice, and only that reaches the window.
    """
    return css_color(color_overrides(colors, appearance_mode).get("background_color", ""))


def text_on(background: str, fallback: str) -> str:
    """The text colour for a window painted `background`: white on a dark colour, black on a light one.

    `fallback` is what to use when the background is not a colour this can judge, which is also the case for the
    window's own colours (the caller already knows which way round those go).
    """
    if not background:
        return fallback
    return "#ffffff" if is_dark_color(background) else "#000000"


def color_overrides(colors: Mapping[str, str] | object, appearance_mode: object) -> dict[str, str]:
    """The colours that differ from the appearance mode's palette, which is all the settings file keeps of them.

    Whatever a caller holds -- the whole palette, only the colours the user changed, nothing -- saves the same file
    when it comes to the same colours, since the entries that equal the palette are not written.
    """
    palette = set_color_mode(_mode_of(appearance_mode))
    return {name: value for name, value in sorted(_named_colors(colors).items()) if palette.get(name) != value}
