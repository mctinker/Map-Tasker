"""One run's read-only configuration, as an immutable value rather than a global."""

#! /usr/bin/env python3

#                                                                                      #
# runcfg: RunConfig -- the colors and runtime arguments for a single run, frozen.       #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# Why this exists
# ---------------
# PrimeItems (primitem.py) is one process-wide object holding everything: the parsed
# XML, the output lines being accumulated, running counters -- and the run's *settings*.
# The settings half is different in kind from the rest: it is decided once, before any
# mapping starts, and then only read.  Mixing it in with the accumulators is what forces
# every test of core logic to stand up and tear down a global, and what stops two maps
# being built in one process without bleeding into each other.
#
# RunConfig is that settings half, pulled out and frozen:
#
#   * it is a value -- construct one, hand it to a function, and the function's answer
#     depends on nothing else, so a test can build the config it wants and skip the
#     global entirely;
#   * it cannot be written to, so a function that is handed one cannot quietly change
#     the run's settings for everybody else;
#   * two of them can exist at once, which is what "process two maps in one process"
#     needs.
#
# What has NOT moved: the mutable accumulators (output_lines, grand_totals,
# tasker_root_elements, the diagram records, ...) all stay on PrimeItems.  This module
# is deliberately only the read-only half.
#
# How it fits the code that has not been converted yet
# ----------------------------------------------------
# PrimeItems.program_arguments / PrimeItems.colors_to_use remain the live store that
# un-converted code reads and that the GUI and settings file write.  current_config()
# takes a snapshot of that store; converted code takes a RunConfig parameter and never
# looks at the global again.  The intended shape of a conversion is therefore:
#
#     config = current_config()          # once, at the top of a subsystem
#     do_the_work(config)                # threaded down from there as a parameter
#
# A snapshot is a copy: mutating PrimeItems.program_arguments afterwards does not change
# a RunConfig already handed out, which is the point.  Where a *scope* genuinely needs a
# different setting -- the handful of places that used to save a value, overwrite it, and
# put it back -- use overridden_config(), which does that dance correctly and restores on
# the way out even if the block raises.
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field, fields, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

from maptasker.src.config import ANDROID_FILE, ANDROID_IPADDR, ANDROID_PORT, OUTPUT_FONT
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import DIAGRAM_PROFILES_PER_LINE, NOTIFY_TIMEOUT_DEFAULT, VIEW_LIMIT_DEFAULT

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

# An empty colors table, shared by every RunConfig built without colors.  Read-only, so
# there is no aliasing hazard in sharing one -- which is the whole reason the equivalent
# tables on PrimeItems have to be rebuilt by a function for each run.
NO_COLORS: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class RunConfig:
    """
    The settings for one run: the colors to draw with, and the runtime arguments the
    user asked for.  Frozen -- derive a changed copy with with_changes() instead of
    assigning.

    The argument fields mirror initparg.initialize_runtime_arguments() exactly, one
    field per key, with the same defaults; test_runcfg.py fails if the two drift apart.
    Field access is therefore checked -- config.display_detail_level is a typo away from
    an AttributeError, where program_arguments["dispaly_detail_level"] was a silent
    KeyError at best and a silently-ignored write at worst.
    """

    # --- What to show ----------------------------------------------------------------
    display_detail_level: int = 4  # How much Task/Profile detail to display, 0-5
    conditions: bool = False  # Display Profile and Task conditions
    directory: bool = False  # Display the directory of hyperlinks
    list_unnamed_items: bool = False  # List unnamed items in the directory
    preferences: bool = False  # Display Tasker's preferences
    runtime: bool = False  # Display the runtime arguments/settings
    taskernet: bool = False  # Display TaskerNet information
    twisty: bool = False  # Add clickable "▶︎" twisties for Task details
    pretty: bool = False  # Pretty up the output (uses many more lines)
    view_limit: int = VIEW_LIMIT_DEFAULT  # Map view line limit
    task_action_warning_limit: int = 100  # Task action count that triggers a warning

    # --- How to draw it --------------------------------------------------------------
    appearance_mode: str = "system"  # "system", "dark" or "light"
    font: str = OUTPUT_FONT  # Font to use in the output
    bold: bool = False  # Names in bold
    highlight: bool = False  # Names highlighted
    italicize: bool = False  # Names italicized
    underline: bool = False  # Names underlined
    indent: int = 4  # Indentation for if/then/else nesting
    icon_alignement: bool = True  # Align the Diagram view with icons
    profiles_per_line: int = DIAGRAM_PROFILES_PER_LINE  # Diagram Profiles per line
    language: str = "English"  # Language for the output and GUI

    # --- The one item to show, if the user asked for just one ------------------------
    single_profile_name: str = ""
    single_project_name: str = ""
    single_scene_name: str = ""
    single_task_name: str = ""

    # --- Where the XML comes from ----------------------------------------------------
    file: str = ""  # The backup file to re-use, if re-running
    android_file: str = ANDROID_FILE  # File location on the Android device
    android_ipaddr: str = ANDROID_IPADDR  # IP address of the Android device
    android_port: str = ANDROID_PORT  # Port of the Android device
    fetched_backup_from_android: bool = False  # XML came off an Android device
    local_xml_directory: str = ""  # Where the last local XML file came from

    # --- AI analysis -----------------------------------------------------------------
    ai_analyze: bool = False  # Do AI processing
    ai_apikey: str = ""  # AI API key
    ai_model: str = ""  # AI model
    ai_name: str = ""  # AI name
    ai_prompt: str = ""  # AI prompt

    # --- How we were invoked ---------------------------------------------------------
    gui: bool = False  # Use the GUI for the runtime and color options
    guiview: bool = False  # Use the GUI to get the view (Map, Diagram, Tree)
    doing_diagram: bool = False  # Use the GUI to get the diagram view
    rerun: bool = False  # This is a GUI re-run
    reset: bool = False  # Reset settings to their default values
    debug: bool = False  # Run in debug mode (create a log file)
    tab_to_use: str | None = None  # Default GUI tab to start on
    notify_timeout: int = NOTIFY_TIMEOUT_DEFAULT  # How long a notification stays up (ms)

    # --- The colors ------------------------------------------------------------------
    # A read-only {color argument name: color} table -- "project_color": "White" and so
    # on, as built by colrmode.set_color_mode.  Kept as a mapping rather than a field per
    # color because the user can add color arguments of their own from the command line.
    # (A mapping is not hashable, so neither is a RunConfig; compare them with == .)
    #
    # default_factory rather than `= NO_COLORS`, and NOT a tidy-up to undo: on Python 3.11
    # dataclasses rejects any default whose type is unhashable, and MappingProxyType only
    # became hashable in 3.12.  Written the obvious way, this line raises ValueError while
    # the class is being built -- so `import maptasker` fails outright on the oldest Python
    # the project supports (pyproject: requires-python = ">=3.11"), before anything runs.
    colors: Mapping[str, str] = field(default_factory=lambda: NO_COLORS)

    # The argument field names, in declaration order, with "colors" left out: everything
    # here corresponds one-for-one to a program_arguments key.  Filled in just below the
    # class, once the fields exist, and then never again -- as_arguments() and get() run
    # per call and should not be walking dataclasses.fields() each time.
    ARGUMENT_NAMES: ClassVar[tuple[str, ...]] = ()

    def __post_init__(self) -> None:
        """
        Take the colors table over: copy it, and make the copy read-only.

        Copying is what stops the dictionary that was passed in from staying a back door
        into a frozen config; making it read-only is what stops code that is handed the
        config from writing through it.  Done here rather than in the constructors so it
        holds however a RunConfig was built -- including by dataclasses.replace.
        """
        object.__setattr__(self, "colors", MappingProxyType(dict(self.colors or {})))

    # ---------------------------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------------------------
    @classmethod
    def from_dicts(
        cls,
        program_arguments: Mapping[str, Any] | None,
        colors_to_use: Mapping[str, str] | None = None,
    ) -> RunConfig:
        """
        Build a RunConfig from the two dictionaries the rest of the program still uses.

        Keys we do not know about are dropped rather than raising: settings files written
        by older versions of MapTasker carry arguments that no longer exist, and the
        program has always been expected to start anyway.  Missing keys take the field's
        default, which is the same default initparg would have given them.

            Args:
                program_arguments: the runtime arguments, or None for all defaults.
                colors_to_use: the colors table, or None for no colors.

            Returns:
                RunConfig: the frozen configuration.
        """
        known = {name: value for name, value in (program_arguments or {}).items() if name in cls.ARGUMENT_NAMES}
        return cls(**known, colors=colors_to_use or {})

    def with_changes(self, **overrides: Any) -> RunConfig:  # noqa: ANN401
        """
        Return a copy of this configuration with some settings changed.

        The frozen equivalent of assigning to program_arguments: the original is left
        alone, so a caller that was handed this config still sees what it was handed.

            Args:
                **overrides: the fields to change, by name.

            Returns:
                RunConfig: a new configuration.

            Raises:
                TypeError: if a name is not a configuration field -- the typo that
                    program_arguments["..."] = ... would have accepted silently.
        """
        return replace(self, **overrides)

    # ---------------------------------------------------------------------------------
    # Access
    # ---------------------------------------------------------------------------------
    def get(self, name: str, default: Any = None) -> Any:  # noqa: ANN401
        """
        Return one setting by name, for the few callers whose key is computed rather
        than written out -- primitem's single-item selectors, for one.  Prefer plain
        attribute access everywhere else: it is checked, and this is not.

            Args:
                name (str): the setting's name.
                default: what to return if there is no such setting.

            Returns:
                the setting's value, or default.
        """
        return getattr(self, name, default) if name in self.ARGUMENT_NAMES else default

    def color(self, name: str, default: str = "") -> str:
        """
        Return one color by its argument name, e.g. "project_color".

            Args:
                name (str): the color argument name.
                default (str): what to return if that color is not set.

            Returns:
                str: the color to use.
        """
        return self.colors.get(name, default) or default

    # ---------------------------------------------------------------------------------
    # Interop with the dictionaries the un-converted code still reads
    # ---------------------------------------------------------------------------------
    def as_arguments(self) -> dict[str, Any]:
        """
        Return the runtime arguments as a plain dictionary -- the shape
        PrimeItems.program_arguments has, and the shape the settings file is written
        from.

            Returns:
                dict: a fresh, mutable copy of the arguments.
        """
        return {name: getattr(self, name) for name in self.ARGUMENT_NAMES}

    def as_colors(self) -> dict[str, str]:
        """
        Return the colors as a plain dictionary.

            Returns:
                dict: a fresh, mutable copy of the colors table.
        """
        return dict(self.colors)

    def apply(self) -> None:
        """
        Write this configuration back onto PrimeItems, for the code that has not been
        converted to take a config parameter.

        This is the one direction that is not pure, and it exists only as long as the
        globals do.  Nothing that has been given a RunConfig should need to call it.
        """
        PrimeItems.program_arguments = self.as_arguments()
        PrimeItems.colors_to_use = self.as_colors()


# Fill in the argument-name list now that the fields exist.  "colors" is the one field
# that is not a program_arguments key.
RunConfig.ARGUMENT_NAMES = tuple(field.name for field in fields(RunConfig) if field.name != "colors")


def current_config() -> RunConfig:
    """
    Snapshot the settings currently on PrimeItems as a RunConfig.

    Call this once, at the top of a subsystem, and pass the result down; the snapshot is
    a copy, so later writes to PrimeItems.program_arguments do not reach back into it.

        Returns:
            RunConfig: the run's settings as they stand right now.
    """
    return RunConfig.from_dicts(PrimeItems.program_arguments, PrimeItems.colors_to_use)


@contextlib.contextmanager
def overridden_config(**overrides: Any) -> Iterator[RunConfig]:  # noqa: ANN401
    """
    Run a block with some settings temporarily changed, then put them back.

    This replaces the save-overwrite-restore dance that a few places do by hand around
    a call -- turning the directory off so it isn't emitted twice, dropping the twisty
    for a nested list.  Doing it here means the restore also happens when the block
    raises, which the hand-written versions did not manage.

    Only the named settings are put back on the way out.  The block is still free to
    change *other* settings and have those changes stick -- which matters, because the
    work these blocks wrap does exactly that (process_unique_situations fills in
    single_project_name as it goes).  Overriding by swapping the whole dictionary would
    have thrown those away.

        Args:
            **overrides: the settings to change for the duration of the block.

        Yields:
            RunConfig: the overridden configuration, for a caller ready to take it as a
                parameter rather than read it back off PrimeItems.

        Raises:
            TypeError: if a name is not a configuration field.
    """
    # Build the overridden config first: with_changes rejects an unknown setting name,
    # so a typo fails here rather than quietly adding a key nothing reads.
    overridden = current_config().with_changes(**overrides)
    argument_names = [name for name in overrides if name != "colors"]

    # Remember what was there, including "it wasn't there at all" -- a test that sets up
    # a partial program_arguments must not come out of this with keys it never had.
    saved = {
        name: PrimeItems.program_arguments[name] for name in argument_names if name in PrimeItems.program_arguments
    }
    absent = [name for name in argument_names if name not in PrimeItems.program_arguments]
    saved_colors = PrimeItems.colors_to_use

    PrimeItems.program_arguments.update({name: getattr(overridden, name) for name in argument_names})
    if "colors" in overrides:
        PrimeItems.colors_to_use = overridden.as_colors()
    try:
        yield overridden
    finally:
        PrimeItems.program_arguments.update(saved)
        for name in absent:
            PrimeItems.program_arguments.pop(name, None)
        if "colors" in overrides:
            PrimeItems.colors_to_use = saved_colors
