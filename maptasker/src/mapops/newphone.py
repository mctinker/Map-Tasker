"""newphone: the checklist for setting up a new phone from a backup, and the ticks that remember how far you got."""

#! /usr/bin/env python3

#                                                                                        #
# newphone: restoring a backup puts the Projects, Profiles and Tasks on the new phone and  #
#           nothing around them.  The plugins and apps they call are not installed, the     #
#           access they rely on (Write Secure Settings, Accessibility, ...) has not been    #
#           granted, the global variables may need typing back in, and the Profiles are     #
#           only worth anything once they are switched on.  This turns that into a job      #
#           with an end: one list, in the order you would do it, that you tick off.         #
#                                                                                        #
# It is readiness.py's answer arranged for somebody doing the migration rather than         #
# somebody about to share a file:                                                         #
#                                                                                        #
#   Plugins, apps    readiness.check_tree over the WHOLE backup (readiness reads one          #
#                    export; here the export is everything).  Each is crossed against the     #
#                    app list fetched from the new phone, the way plugchk does, and the        #
#                    ones that phone does not have are flagged.  With no list fetched nothing   #
#                    is flagged, and the report says so rather than leaving every item looking   #
#                    as though it had been checked.                                              #
#   Special access   readiness's access needs, each with the commands for a computer where        #
#                    readiness.json has them, so they can be copied rather than retyped.          #
#   Variables        mapvars' table: the globals the Variables tab holds a value for, with       #
#                    that value, for typing back in.                                              #
#   Profiles         the ones the backup has switched on, which are the ones to check are on      #
#                    again; a Profile the backup has switched off is left off the list on          #
#                    purpose.                                                                     #
#                                                                                        #
# WHERE THE TICKS LIVE                                                                    #
#                                                                                        #
# In MapTasker_NewPhone.json in the current directory, beside the notes and the settings --   #
# never in the backup, which Tasker would carry onto the phone.  Each tick is a key naming     #
# the thing ("plugin:com.joaomgcd.autoshare", "profile:Morning"), so it survives reloading the  #
# file and a re-fetch of the phone's app list, and is not tied to one backup: a migration is a   #
# one-off job, and "Clear ticks" starts the next.  A tick for something no longer in the file    #
# is kept and simply never shown.                                                              #
#                                                                                        #
# What the list cannot know, said because a finished checklist gets trusted: it is a floor,        #
# for the reasons readiness.LIMITATIONS gives, and "installed" means "on the app list last          #
# fetched", not "installed now".                                                             #
#                                                                                        #
# No GUI here: the window is guiwins_newphone.                                              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

import contextlib
import json
import os
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from maptasker.src.core import appinv, clock
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import NEWPHONE_FILE, NEWPHONE_REPORT_FILE, logger
from maptasker.src.mapops import mapvars, readiness
from maptasker.src.mapops.maprefac_model import display_project, profile_target

if TYPE_CHECKING:
    from maptasker.src.core.mapjump import Target
    from maptasker.src.core.primitem import RunState

# The kinds of group, in the order a phone is set up in: install, grant, type in, switch on.
PLUGINS = "plugins"
APPS = "apps"
ACCESS = "access"
VARIABLES = "variables"
PROFILES = "profiles"
KINDS = (PLUGINS, APPS, ACCESS, VARIABLES, PROFILES)

# Whether the phone has a plugin or app, by the app list fetched from it.  "" is "not known": no list was asked.
HAVE = "have"
MISSING = "missing"
UNKNOWN = ""

# The version of the ticks file's layout.
FORMAT_VERSION = 1

_TITLES = {
    PLUGINS: "Plugins to install",
    APPS: "Apps to install",
    ACCESS: "Special access to grant",
    VARIABLES: "Global variables to enter",
    PROFILES: "Profiles to enable",
}
_EMPTY = {
    PLUGINS: "No plugins are used.",
    APPS: "No apps are named.",
    ACCESS: "No special access found.",
    VARIABLES: "No global variable holds a value.",
    PROFILES: "No Profile is switched on.",
}


# ##################################################################################
# The answer.
# ##################################################################################
@dataclass(frozen=True)
class Item:
    """One thing to do on the new phone.

    'key' is what a tick is remembered under.  'status' is HAVE, MISSING or UNKNOWN for a plugin or app, and
    UNKNOWN for everything else.  'commands' are typed on a computer, one per entry; 'value' is a variable's value
    from the backup.  'target' is where a click goes in the Map, where there is somewhere.
    """

    key: str
    text: str
    detail: str = ""
    status: str = UNKNOWN
    commands: tuple[str, ...] = ()
    value: str = ""
    target: Target | None = None


@dataclass(frozen=True)
class Group:
    """One heading of the checklist and what is under it."""

    kind: str
    items: tuple[Item, ...]

    @property
    def title(self) -> str:
        """What the heading says."""
        return _TITLES[self.kind]

    @property
    def empty(self) -> str:
        """What to say when there is nothing under it."""
        return _EMPTY[self.kind]


@dataclass
class Checklist:
    """The whole list, and what it was checked against."""

    written_by: str = ""
    device: str = ""  # the phone whose fetched app list the plugins and apps were crossed with; "" for none
    fetched: str = ""  # when that list was fetched
    groups: list[Group] = field(default_factory=list[Group])

    def items(self) -> list[Item]:
        """Every item, in the order the groups are shown."""
        return [item for group in self.groups for item in group.items]

    def counts(self, ticks: set[str]) -> tuple[int, int]:
        """(how many are ticked, how many there are)."""
        items = self.items()
        return sum(1 for item in items if item.key in ticks), len(items)

    def missing(self) -> int:
        """How many plugins and apps the checked phone does not have."""
        return sum(1 for item in self.items() if item.status == MISSING)


# ##################################################################################
# The phones whose app list was fetched.
# ##################################################################################
def devices() -> list[str]:
    """The phones an app list has been fetched from, the most recently fetched first."""
    fetched = appinv.fetched_devices()
    return [device for device, _when, _count in sorted(fetched, key=lambda entry: entry[1], reverse=True)]


def default_device() -> str:
    """The phone to check against when none was picked: the one fetched last, or "" when none was."""
    known = devices()
    return known[0] if known else ""


# ##################################################################################
# Building it.
# ##################################################################################
def _status(package: str, installed: frozenset[str] | None) -> str:
    """HAVE or MISSING for a package, or UNKNOWN when there is no list to ask."""
    if installed is None:
        return UNKNOWN
    return HAVE if package in installed else MISSING


def _access_items(result: readiness.Readiness) -> list[Item]:
    """One item per kind of special access, or per choice of them, with the commands that grant it."""
    items: list[Item] = []
    for need in result.access:
        commands = tuple(command for access_id in need.any_of for command in readiness.access_adb(access_id))
        if len(need.any_of) == 1:
            how = readiness.access_how(need.any_of[0])
            text = need.labels[0]
        else:
            how = "  ".join(f"{readiness.access_label(i)}: {readiness.access_how(i)}" for i in need.any_of)
            text = f"{' or '.join(need.labels)} (any one of them)"
        items.append(
            Item(
                key=f"access:{'|'.join(sorted(need.any_of))}",
                text=text,
                detail=f"{readiness.access_places(need)}\n{how}",
                commands=commands,
            ),
        )
    return items


def _variable_items(state: RunState) -> list[Item]:
    """The globals the Variables tab holds a value for, each with that value."""
    return [
        Item(
            key=f"variable:{row.name}",
            text=row.name,
            detail=f"Used in {row.tasks} place{'s' if row.tasks != 1 else ''}."
            if row.tasks
            else "Nothing in the file uses it, so it can be skipped.",
            value=row.value,
        )
        for row in mapvars.build_rows(state)
        if row.declared and row.value.strip()
    ]


def _profile_items(state: RunState) -> list[Item]:
    """The Profiles the backup has switched on, by name."""
    items: list[Item] = []
    profiles: dict[str, Any] = state.tasker_root_elements.get("all_profiles", {})
    for profile_id, profile in profiles.items():
        if (profile["xml"].findtext("limit") or "").strip() == "true":
            continue
        name = (profile.get("name") or "").strip()
        owner = display_project("pids", profile_id, state=state)
        items.append(
            Item(
                key=f"profile:{name or f'id {profile_id}'}",
                text=name or f"(unnamed Profile {profile_id})",
                detail=f"In Project '{owner}'." if owner else "",
                target=profile_target(profile_id, state=state),
            ),
        )
    return sorted(items, key=lambda item: item.text.casefold())


def build(state: RunState, device: str = "") -> Checklist:
    """The checklist for the loaded backup, with the plugins and apps crossed with `device`'s fetched app list.

    Args:
        state: the run state, with a backup loaded.
        device: a phone from devices(); "" to leave the plugins and apps unflagged.

    An empty checklist when nothing is loaded.
    """
    if not state.backup_loaded:
        return Checklist()
    result = readiness.check_tree(state.xml_root, "this backup")
    fetched = appinv.fetched_packages().get(device)
    installed = fetched[1] if fetched is not None else None
    checklist = Checklist(
        written_by=result.written_by,
        device=device if fetched is not None else "",
        fetched=fetched[0] if fetched is not None else "",
    )
    plugins = tuple(
        Item(
            key=f"plugin:{need.package}",
            text=need.package,
            detail=readiness.places_text(need.used_by),
            status=_status(need.package, installed),
        )
        for need in result.plugins
    )
    apps = tuple(
        Item(
            key=f"app:{need.package}",
            text=readiness.app_text(need),
            detail=readiness.places_text(need.used_by),
            status=_status(need.package, installed),
        )
        for need in result.apps
    )
    checklist.groups = [
        Group(PLUGINS, plugins),
        Group(APPS, apps),
        Group(ACCESS, tuple(_access_items(result))),
        Group(VARIABLES, tuple(_variable_items(state))),
        Group(PROFILES, tuple(_profile_items(state))),
    ]
    return checklist


# ##################################################################################
# The ticks.
# ##################################################################################
@dataclass
class TickBook:
    """The keys that have been ticked.  'unreadable' says why the file could not be read, when it could not."""

    keys: set[str] = field(default_factory=set[str])
    unreadable: str = ""


def ticks_path() -> str:
    """Where the ticks are kept -- in the current directory, beside the notes."""
    return os.path.join(os.getcwd(), NEWPHONE_FILE)


def load_ticks(file_path: str | None = None) -> TickBook:
    """The saved ticks.  None when there is no file; an empty book that says why when it cannot be read."""
    where = file_path or ticks_path()
    try:
        with open(where, encoding="utf-8") as handle:
            data: object = json.load(handle)
    except FileNotFoundError:
        return TickBook()
    except (OSError, ValueError) as error:
        logger.error(f"The new-phone ticks could not be read from {where}: {error}")
        return TickBook(unreadable=str(error))
    raw = cast("dict[str, Any]", data) if isinstance(data, dict) else {}
    ticked = raw.get("ticked")
    keys = {str(key) for key in cast("list[Any]", ticked)} if isinstance(ticked, list) else set[str]()
    return TickBook(keys=keys)


def save_ticks(book: TickBook, file_path: str | None = None) -> str:
    """Write the ticks.  Returns "" or why they could not be saved.

    Written beside the real file and moved into place so a crash leaves them as they were, and a file that could not
    be read is copied to '<name>.unreadable' first, for the reason objnotes.save gives.
    """
    where = file_path or ticks_path()
    temporary = f"{where}.tmp"
    try:
        if book.unreadable and os.path.exists(where):
            shutil.copyfile(where, f"{where}.unreadable")
            book.unreadable = ""
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump({"version": FORMAT_VERSION, "ticked": sorted(book.keys)}, handle, indent=2, ensure_ascii=False)
        os.replace(temporary, where)
    except OSError as error:
        logger.error(f"The new-phone ticks could not be written to {where}: {error}")
        with contextlib.suppress(OSError):
            os.remove(temporary)
        return str(error)
    return ""


# ##################################################################################
# The text.
# ##################################################################################
_STATUS_WORDS = {MISSING: "NOT ON THE PHONE", HAVE: "on the phone"}


def as_text(checklist: Checklist, ticks: set[str], show_values: bool = True) -> str:
    """The checklist as plain text, ticked items marked [x].

    A variable's value is left out unless `show_values`, because a variable can hold a key or a password and this is
    text that gets pasted and saved.
    """
    done, total = checklist.counts(ticks)
    out = ["New-phone checklist", ""]
    if checklist.written_by:
        out.append(f"The backup was written by Tasker {checklist.written_by}.")
    if checklist.device:
        out.append(
            f"Plugins and apps checked against the app list fetched from {checklist.device} on {checklist.fetched}."
        )
    else:
        out.append("No app list was fetched from the new phone, so no plugin or app is checked.")
    out += [f"{done} of {total} done.", ""]
    for group in checklist.groups:
        ticked = sum(1 for item in group.items if item.key in ticks)
        out.append(f"{group.title} ({ticked} of {len(group.items)})")
        if not group.items:
            out.append(f"  {group.empty}")
        for item in group.items:
            mark = "x" if item.key in ticks else " "
            status = f"  -- {_STATUS_WORDS[item.status]}" if item.status in _STATUS_WORDS else ""
            out.append(f"  [{mark}] {item.text}{status}")
            out.extend(f"        {line}" for line in item.detail.splitlines() if line)
            out.extend(f"        $ {command}" for command in item.commands)
            if item.value:
                out.append(f"        Value: {item.value if show_values else '(hidden)'}")
        out.append("")
    out.append(readiness.LIMITATIONS)
    return "\n".join(out).rstrip() + "\n"


def write_report(checklist: Checklist, ticks: set[str], show_values: bool, state: RunState) -> str:
    """Save the checklist as text, the way the other reports are saved.  Returns the file's path, or "" if it could not be."""
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(NEWPHONE_REPORT_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(as_text(checklist, ticks, show_values))
    except OSError as error:
        logger.error(f"The new-phone checklist could not be written: {error}")
        return ""
    return file_path
