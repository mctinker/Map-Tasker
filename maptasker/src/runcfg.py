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
from dataclasses import FrozenInstanceError, dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

from maptasker.src.initparg import ArgumentFields, ProgramArguments
from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from maptasker.src.primitem import RunState

# An empty colors table, shared by every RunConfig built without colors.  Read-only, so
# there is no aliasing hazard in sharing one -- which is the whole reason the equivalent
# tables on PrimeItems have to be rebuilt by a function for each run.
NO_COLORS: Mapping[str, str] = MappingProxyType({})


@dataclass(slots=True)
class RunConfig(ArgumentFields):
    """
    The settings for one run: the colors to draw with, and the runtime arguments the
    user asked for.  Frozen -- derive a changed copy with with_changes() instead of
    assigning.

    The argument fields are ArgumentFields' (initparg.py), the same ones ProgramArguments
    has, so they are declared once for both.  Frozen by hand rather than with
    @dataclass(frozen=True), which dataclasses refuse for a class whose base is not
    frozen: __post_init__ seals the instance, and from then on any assignment -- to a
    field or through any method -- raises dataclasses.FrozenInstanceError.
    """

    # --- The colors ------------------------------------------------------------------
    # A read-only {color argument name: color} table -- "project_color": "White" and so
    # on, as built by colrmode.set_color_mode.  Kept as a mapping rather than a field per
    # color because the user can add color arguments of their own from the command line.
    #
    # default_factory rather than `= NO_COLORS`, and NOT a tidy-up to undo: on Python 3.11
    # dataclasses rejects any default whose type is unhashable, and MappingProxyType only
    # became hashable in 3.12.  Written the obvious way, this line raises ValueError while
    # the class is being built -- so `import maptasker` fails outright on the oldest Python
    # the project supports (pyproject: requires-python = ">=3.11"), before anything runs.
    colors: Mapping[str, str] = field(default_factory=lambda: NO_COLORS)

    # Set once __post_init__ has run; see __setattr__.  Not a setting, so kept out of the
    # constructor, the repr and comparisons.
    _sealed: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """
        Take the colors table and the list over, then seal the instance.

        Copying is what stops what was passed in from staying a back door into a frozen
        config; making the colors read-only is what stops code that is handed the config
        from writing through them.  Done here rather than in the constructors so it holds
        however a RunConfig was built -- including by dataclasses.replace.
        """
        object.__setattr__(self, "colors", MappingProxyType(dict(self.colors or {})))
        object.__setattr__(self, "health_check_skip", list(self.health_check_skip))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        """Refuse every assignment once sealed; __init__ runs before that."""
        if getattr(self, "_sealed", False):
            msg = f"cannot assign to field {name!r}"
            raise FrozenInstanceError(msg)
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        """Refuse every deletion."""
        msg = f"cannot delete field {name!r}"
        raise FrozenInstanceError(msg)

    def __deepcopy__(self, memo: dict) -> RunConfig:
        """
        A copy built through the constructor.  The default copy would put the fields
        back one by one after _sealed, and __setattr__ would refuse them.
        """
        return replace(self)

    # ---------------------------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------------------------
    @classmethod
    def from_dicts(
        cls,
        program_arguments: Mapping[str, object] | None,
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
        known = {name: value for name, value in (program_arguments or {}).items() if name in cls.NAME_SET}
        return cls(**known, colors=colors_to_use or {})

    def with_changes(self, **overrides: object) -> RunConfig:
        """
        Return a copy of this configuration with some settings changed.

        The frozen equivalent of assigning to program_arguments: the original is left
        alone, so a caller that was handed this config still sees what it was handed.

            Args:
                **overrides: the fields to change, by name.

            Returns:
                RunConfig: a new configuration.

            Raises:
                TypeError: if a name is not a configuration field.
        """
        return replace(self, **overrides)

    # ---------------------------------------------------------------------------------
    # Access
    # ---------------------------------------------------------------------------------
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
    # Interop with the dictionaries the un-converted code still reads.  The arguments
    # come out through as_dict(), from ArgumentFields.
    # ---------------------------------------------------------------------------------
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
        PrimeItems.program_arguments = ProgramArguments(**self.as_dict())
        PrimeItems.colors_to_use = self.as_colors()


def current_config(state: RunState | None = None) -> RunConfig:
    """
    Snapshot the settings currently on a run state as a RunConfig.

    Call this once, at the top of a subsystem, and pass the result down; the snapshot is
    a copy, so later writes to the state's program_arguments do not reach back into it.

        Args:
            state (RunState | None): the run state to read, or None for PrimeItems.

        Returns:
            RunConfig: the run's settings as they stand right now.
    """
    source = PrimeItems if state is None else state
    return RunConfig.from_dicts(source.program_arguments, source.colors_to_use)


@contextlib.contextmanager
def overridden_config(*, state: RunState | None = None, **overrides: object) -> Iterator[RunConfig]:
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
            state (RunState | None): the run state whose settings are overridden, or None for
                PrimeItems.
            **overrides: the settings to change for the duration of the block.

        Yields:
            RunConfig: the overridden configuration, for a caller ready to take it as a
                parameter rather than read it back off PrimeItems.

        Raises:
            TypeError: if a name is not a configuration field.
    """
    # Build the overridden config first: with_changes rejects an unknown setting name,
    # so a typo fails here rather than quietly adding a key nothing reads.
    target = PrimeItems if state is None else state
    overridden = current_config(target).with_changes(**overrides)
    argument_names = [name for name in overrides if name != "colors"]

    # Remember what was there.
    saved = {name: target.program_arguments[name] for name in argument_names}
    saved_colors = target.colors_to_use

    target.program_arguments.update({name: getattr(overridden, name) for name in argument_names})
    if "colors" in overrides:
        target.colors_to_use = overridden.as_colors()
    try:
        yield overridden
    finally:
        target.program_arguments.update(saved)
        if "colors" in overrides:
            target.colors_to_use = saved_colors
