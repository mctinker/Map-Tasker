"""retire: the plugins a configuration uses that Tasker now does itself."""

#! /usr/bin/env python3

#                                                                                        #
# retire: the Plugin Retirement Advisor.                                                 #
#                                                                                        #
# Tasker has been taking over what plugins used to be needed for: version 5.9 opens another  #
# app's launcher shortcut and reads the next alarm itself, 6.4 runs actions on your other      #
# devices.  A configuration written years ago still calls the plugin, so it still needs the      #
# plugin installed, kept up to date and given its permissions, for something Tasker can do          #
# with nothing added.  This lists the plugins the loaded configuration uses that have such a      #
# built-in, says which one and since which Tasker version, and where the plugin is used.            #
#                                                                                        #
# Two tables do the work.  plugchk finds the plugins a configuration uses (the package each      #
# plugin action, event and state records), and compat.json holds each built-in action, event       #
# and state with the version that introduced it.  The missing piece is plugin_builtins.json,         #
# the short list of which plugin each built-in takes over from.  It names a built-in by its key        #
# in compat.json rather than by name, so the name and the version are written down in one place.      #
#                                                                                        #
# WHAT IT SAYS, in every line:                                                          #
#                                                                                        #
#   REPLACED        the plugin's job is now Tasker's: nothing it did is lost by moving over.     #
#   PARTLY-REPLACED the built-in does some of what the plugin does and the plugin does more, so   #
#                   whether it can go depends on what you use it for -- the lines below it say      #
#                   which of its actions are used where.                                            #
#                                                                                        #
# WHAT IT CANNOT DO, said plainly because "nothing found" gets trusted:                   #
#                                                                                        #
#   * It is a short list on purpose.  A pairing is in it only where the plugin's author or Tasker's   #
#     release notes say Tasker took the job over; a built-in that merely looks like a plugin's       #
#     feature is not.  A plugin that is not on it may well have a built-in nobody wrote down.        #
#   * It changes nothing.  Swapping a plugin action for the built-in means setting the new action's    #
#     fields by hand: the two do not take the same arguments, and a plugin's bundle is not one         #
#     MapTasker may rewrite.                                                                       #
#   * The Tasker version it compares with is the one that wrote the backup.  That is the Tasker the   #
#     file was last saved by, which is usually the one on the phone, and is not a promise.            #
#                                                                                        #
# Read-only: nothing here changes the configuration.                                       #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Any

from maptasker.src.analysis.plugchk import Use, plugin_uses
from maptasker.src.core import clock
from maptasker.src.core.mapjump import Row, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import RETIRE_FILE, logger
from maptasker.src.mapops import compat
from maptasker.src.mapops.readiness import version_key

if TYPE_CHECKING:
    from maptasker.src.core.primitem import RunState

TABLE_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "plugin_builtins.json"),
)

# A sentence in a report is broken at this width, indented under its plugin, so a line is never wider than a window.
_WIDTH = 96
_INDENT = " " * 6

# How much of the plugin the built-in covers.  The data file's own words, and what a finding is tagged with.
REPLACES = "replaces"
OVERLAPS = "overlaps"
REPLACED = "REPLACED"
PARTLY_REPLACED = "PARTLY-REPLACED"
_TAGS = {REPLACES: REPLACED, OVERLAPS: PARTLY_REPLACED}


# ##################################################################################
# The table.
# ##################################################################################


@dataclass(frozen=True)
class Replacement:
    """One built-in action, event or state that takes over from a plugin, and when Tasker got it."""

    key: str  # the compat.json key
    label: str  # 'Action Shortcut'
    since: str  # the first Tasker version announced to have it
    released: str = ""  # the release the notes put it in, when a beta had it earlier; "" otherwise


@dataclass(frozen=True)
class Entry:
    """One plugin the table knows has a built-in, and what the built-in is."""

    package: str
    plugin: str
    coverage: str  # REPLACES or OVERLAPS
    note: str
    source: str  # where the pairing comes from
    replacements: tuple[Replacement, ...]

    @property
    def tag(self) -> str:
        """REPLACED or PARTLY-REPLACED."""
        return _TAGS[self.coverage]

    @property
    def needs(self) -> str:
        """The newest Tasker version among the built-ins: the one that has all of them."""
        return max((each.since for each in self.replacements), key=version_key)


@cache
def _table() -> dict[str, Any]:
    """plugin_builtins.json, read the first time it is wanted."""
    with open(TABLE_FILE, encoding="utf-8") as file:
        return json.load(file)


def _replacement(key: str) -> Replacement:
    """The built-in compat.json has under this key.  A key it lacks is an error in the data, and the test says so."""
    for item in compat.items():
        if item.key == key:
            return Replacement(key, f"{item.kind.capitalize()} {item.name}", item.since, item.released)
    msg = f"plugin_builtins.json names {key}, which compat.json does not have"
    raise KeyError(msg)


def entries() -> list[Entry]:
    """Every plugin in the table, in the order the data file has them."""
    return [
        Entry(
            row["package"],
            row["plugin"],
            row["coverage"],
            row["note"],
            row["source"],
            tuple(_replacement(key) for key in row["builtins"]),
        )
        for row in _table()["plugins"]
    ]


# ##################################################################################
# The advice.
# ##################################################################################


@dataclass(frozen=True)
class Advice:
    """One plugin the configuration uses that Tasker has a built-in for."""

    entry: Entry
    uses: tuple[Use, ...]
    # Whether the Tasker that wrote the backup already has every built-in; None when the file does not say.
    ready: bool | None


@dataclass
class Retirement:
    """What the advisor found in the loaded configuration."""

    written_by: str  # the Tasker the file says wrote it, or ""
    plugins_used: int = 0  # how many different plugins the configuration uses at all
    advice: list[Advice] = field(default_factory=list[Advice])
    known: int = 0  # how many plugins the table knows

    @property
    def is_clean(self) -> bool:
        """Whether no plugin in the file has a built-in."""
        return not self.advice


def advise(state: RunState) -> Retirement:
    """Set the plugins the loaded configuration uses against the table of those Tasker has taken over.

    The plugins Tasker fully replaces come first, since those are the ones that can simply go, then the partly replaced;
    within each, the one used in the most places.  Safe with nothing loaded: there is no plugin, so there is no advice.
    """
    known = entries()
    result = Retirement(written_by=compat.written_by(state), known=len(known))
    if not state.backup_loaded:
        return result
    used = plugin_uses(state)
    result.plugins_used = len(used)
    for entry in known:
        uses = used.get(entry.package)
        if not uses:
            continue
        ready = None if not result.written_by else version_key(result.written_by) >= version_key(entry.needs)
        result.advice.append(Advice(entry, tuple(uses), ready))
    result.advice.sort(key=lambda each: (each.entry.coverage != REPLACES, -len(each.uses), each.entry.plugin))
    return result


@dataclass(frozen=True)
class TableRow:
    """One line of the reference table: a plugin Tasker has taken over from, and how."""

    plugin: str
    package: str
    covers: str  # 'Replaced' or 'Partly replaced'
    replaced_by: str  # 'Action Shortcut'; several joined with a comma
    since: str  # the newest version among them
    note: str
    used: int | None  # in how many places the loaded file uses the plugin; None when nothing is loaded
    source: str  # where the pairing comes from


def table(state: RunState) -> list[TableRow]:
    """Every plugin the table knows, with how much of the loaded file uses it.  Worth reading with no file open."""
    used = plugin_uses(state) if state.backup_loaded else {}
    return [
        TableRow(
            entry.plugin,
            entry.package,
            "Replaced" if entry.coverage == REPLACES else "Partly replaced",
            ", ".join(each.label for each in entry.replacements),
            entry.needs,
            entry.note,
            len(used.get(entry.package, ())) if state.backup_loaded else None,
            entry.source,
        )
        for entry in entries()
    ]


# ##################################################################################
# The report.
# ##################################################################################


def _since(each: Replacement) -> str:
    """'Action Shortcut, since Tasker 5.9.0' -- and, where a beta had it first, when it was released."""
    earlier = f" (a beta; released in {each.released})" if each.released else ""
    return f"{each.label}, since Tasker {each.since}{earlier}"


def _ready_text(advice: Advice, written_by: str) -> str:
    """Whether the Tasker that wrote the backup has the built-in, in a sentence."""
    needs = advice.entry.needs
    if advice.ready is None:
        return f"It needs Tasker {needs} or later.  The file does not say which Tasker wrote it."
    if advice.ready:
        return f"The backup was written by Tasker {written_by}, which already has it."
    return (
        f"It needs Tasker {needs} or later; the backup was written by Tasker {written_by}, which does not have it yet."
    )


def _distinct(uses: tuple[Use, ...]) -> str:
    """What the plugin is used for here: the names of its actions, events and states, each once, with how often."""
    counts: dict[str, int] = {}
    for use in uses:
        counts[use.name] = counts.get(use.name, 0) + 1
    return ", ".join(f"{name} x{count}" if count > 1 else name for name, count in sorted(counts.items()))


def _sentence(text: str) -> list[Row]:
    """A sentence as report rows, broken into lines under the plugin it is about."""
    lines = textwrap.wrap(text, _WIDTH, initial_indent=_INDENT, subsequent_indent=_INDENT, break_on_hyphens=False)
    return [Row(line) for line in lines]


def _advice_rows(advice: Advice, written_by: str) -> list[Row]:
    """One plugin: what it is, what replaces it and since when, what the built-in does, and where it is used."""
    entry = advice.entry
    rows = [
        Row(f"  {entry.tag}  {entry.plugin} ({entry.package})"),
        *(Row(f"      Tasker's {_since(each)}") for each in entry.replacements),
        *_sentence(entry.note),
        *_sentence(_ready_text(advice, written_by)),
        *_sentence(f"The file uses it for: {_distinct(advice.uses)}"),
    ]
    count = len(advice.uses)
    rows.append(Row(f"      Used in {count} place{'' if count == 1 else 's'}:"))
    rows.extend(Row(f"        {use.where.label} ({use.name})", use.where) for use in advice.uses)
    return rows


def report_rows(result: Retirement, *, loaded: bool = True) -> list[Row]:
    """The result as a report: what the file is, then each plugin with its built-in, where it is used and where to go."""
    rows = [Row("PLUGIN RETIREMENT ADVISOR")]
    if not loaded:
        return [*rows, Row("No XML file has been loaded.  Get an XML file first.")]
    rows.append(
        Row(
            f"Written by Tasker {result.written_by}"
            if result.written_by
            else "The file does not say which Tasker wrote it.",
        ),
    )
    plural = "" if result.plugins_used == 1 else "s"
    rows.append(
        Row(
            f"It uses {result.plugins_used} plugin{plural}.  The table knows {result.known} that Tasker has taken over."
        )
    )
    rows.append(Row(""))
    if result.is_clean:
        rows.append(Row("None of them has a built-in in Tasker that is known to do its job."))
        rows.append(Row("The table is short on purpose: a plugin that is not on it may still have one."))
        return rows
    rows.append(Row(f"TASKER NOW DOES THIS ITSELF ({len(result.advice)})"))
    for advice in result.advice:
        rows.extend(_advice_rows(advice, result.written_by))
    return rows


def write_report(rows: list[Row], state: RunState) -> str:
    """Save the report as text, the way the other reports are saved.  Returns the file's path, or "" if it could not be."""
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(RETIRE_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"The plugin retirement report could not be written: {error}")
        return ""
    return file_path
