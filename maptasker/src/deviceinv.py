#! /usr/bin/env python3
"""deviceinv: the Applications and icons an edit is allowed to choose from.

Tasker stores an Application as a package name, a display label and an activity class,
and an icon as a name (a Tasker built-in), a name plus an icon pack, an installed app's
launcher activity, or a %variable.  Neither is a value this tool can invent, which is why
every argument declaring one was refused outright -- arg_specs.json categories 'App' (2)
and 'Icon' (4) sit outside taskedit._SAFE_CATEGORIES, so classify_action_addability turned
away 22 Task actions and Profile Events on their account alone.

They are not unknowable, though.  Two sources fill the inventory, and they are merged:

  * The loaded configuration, always.  Every <App> and every <Img> already in the backup is
    a correctly-spelled triple or icon reference that this user actually uses, and
    harvesting those needs no device, no network and no particular Tasker version.

  * The Android device, when asked.  Tasker has a built-in 'List Apps' action, so a small
    helper Task can enumerate every installed package, label and launcher activity and
    write them to a file this program already knows how to read back -- and MapTasker
    builds and installs that helper Task itself, out of the very Add-Task machinery this
    module exists to unblock (see fetch_apps_from_device).  The result is cached per device
    in MapTasker_Apps.json, and nothing is ever fetched unless the user asks.

Without a fetch, the inventory is what you already automate, not everything installed.  An
app referenced nowhere in the backup and never fetched will not be in the list -- so the
pickers built on this never *replace* typing a value, they only save you from having to
(see guiwins.py's _render_app_arg_field, and _build_icon_field, which took the same stance
for Scenes first).

Only Applications are fetched.  Tasker's built-in icon names live inside its own APK and
'List Apps' does not report them, so icons stay harvest-only -- see
app_icon_fetch_design.md's "icon gap".

Deliberately dependency-light: PrimeItems and the standard library, nothing else.  taskedit
imports this; anything this imported from taskedit or profedit would be a cycle.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    import defusedxml.ElementTree

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import APPS_CACHE_FILE, logger

# An App *condition*'s per-entry tags: cls0/label0/pkg0, cls1/label1/pkg1, ... (see
# profedit.get_app_entries, which edits them).  An App *argument* spells the same three
# fields differently -- see _APP_ARG_TAGS -- so both shapes are read here.
_APP_CONDITION_TAG_RE = re.compile(r"^(cls|label|pkg)(\d+)$")
# An App argument's three children, and the AppEntry field each one holds.  Their values
# are parallel comma-joined lists when the argument names more than one app, e.g.
# <appPkg>com.whatsapp, com.whatsapp.w4b</appPkg> alongside a two-entry <label>.
_APP_ARG_TAGS = (("appPkg", "pkg"), ("appClass", "cls"), ("label", "label"))
# How Tasker joins those lists.  Read back with a strip, since the backups in this repo
# write ", " and nothing guarantees the space.
_APP_LIST_JOINER = ", "

# The children an <Img> uses, by icon kind -- everything else it carries (<tint>, most
# often) belongs to whoever wrote it and is left alone by write_icon_element.
_ICON_TAGS = ("nme", "pkg", "cls", "var")
# Icon packs are installed apps whose package starts with this; Tasker names the icon
# within the pack in <nme>.  The names inside a pack cannot be enumerated remotely, which
# is why a 'pack' icon stays typed unless it was harvested -- see the module docstring.
ICON_PACK_PREFIX = "net.dinglisch.android.ipack."
# How a picked icon is written into (and read back out of) a single text field.  A bare
# name is a Tasker built-in, '%x' is a variable, 'name@pack.package' is an icon pack's,
# and 'app:package[/activity.class]' is an installed app's own icon.  Round-trips: see
# tests/test_deviceinv.py.
_ICON_PACK_SEPARATOR = "@"
_ICON_APP_PREFIX = "app:"
_ICON_APP_SEPARATOR = "/"


@dataclass(frozen=True)
class AppEntry:
    """One Application, as Tasker identifies one: package name, display label, activity
    class.  The package is the identity -- it is what profedit._validate_app_entries has
    always insisted on, and the only one of the three that is never blank in practice.
    """

    pkg: str
    label: str = ""
    cls: str = ""

    @property
    def display(self) -> str:
        """How a picker names it: the label with the package after it, since two apps can
        share a label ('Camera') and the package is what tells them apart.
        """
        return f"{self.label}  ({self.pkg})" if self.label and self.label != self.pkg else self.pkg


@dataclass(frozen=True)
class IconRef:
    """One icon reference, in whichever of Tasker's four forms it takes.

    kind is 'builtin' (<nme> alone), 'pack' (<nme> plus an icon pack's <pkg>), 'app'
    (an installed app's <pkg>, usually with its launcher <cls>) or 'var' (a %variable in
    <var>).  The unused fields are blank rather than absent so the four forms compare and
    sort as one kind of thing.
    """

    kind: str
    name: str = ""
    pkg: str = ""
    cls: str = ""

    @property
    def display(self) -> str:
        """How a picker names it -- the icon's own name for the two name-bearing kinds,
        and the app or the variable for the other two.
        """
        if self.kind == "pack":
            return f"{self.name}  ({self.pkg.removeprefix(ICON_PACK_PREFIX)})"
        if self.kind == "app":
            return f"App: {self.pkg}"
        return self.name


# ==========================================
# Reading and writing the XML
# ==========================================


def _child_text(element: defusedxml.ElementTree.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _set_child_text(parent: defusedxml.ElementTree.Element, tag: str, text: str) -> None:
    """Set (creating if need be) one child's text.  Builds a new child with the parent's
    own class rather than ETW.SubElement: the tree being edited is parsed by defusedxml,
    and .append() enforces an exact type match, so a stdlib-class child would be refused
    (the same reasoning as profedit._set_child_text and taskedit's own).
    """
    child = parent.find(tag)
    if child is None:
        child = type(parent)(tag)
        parent.append(child)
    child.text = text


def _remove_children(parent: defusedxml.ElementTree.Element, tags: tuple[str, ...]) -> None:
    for child in [c for c in parent if c.tag in tags]:
        parent.remove(child)


def read_app_element(element: defusedxml.ElementTree.Element) -> list[AppEntry]:
    """The apps an <App> *argument* names, in order -- its three parallel comma-joined
    lists unzipped back into triples.

    Ragged lists are tolerated rather than rejected: the package list decides how many
    apps there are (it is the identity), and a label or class the other lists run out of
    comes back blank.  Backups do contain <App> elements with an <appPkg> and no <label>.
    """
    fields = {field: _child_text(element, tag).split(",") for tag, field in _APP_ARG_TAGS}
    packages = [value.strip() for value in fields["pkg"]]

    entries = []
    for index, package in enumerate(packages):
        if not package:
            continue
        entries.append(
            AppEntry(
                pkg=package,
                label=fields["label"][index].strip() if index < len(fields["label"]) else "",
                cls=fields["cls"][index].strip() if index < len(fields["cls"]) else "",
            ),
        )
    return entries


def write_app_element(element: defusedxml.ElementTree.Element, entries: list[AppEntry]) -> None:
    """Rewrite an <App> argument's three lists from a set of entries.  All three are
    always written, even when every label or class in them is blank, so that a list left
    behind by a previous value can't survive alongside a shorter new one and re-pair the
    wrong label with the wrong package.
    """
    for tag, field in _APP_ARG_TAGS:
        _set_child_text(element, tag, _APP_LIST_JOINER.join(getattr(entry, field) for entry in entries))


def read_app_condition_entries(element: defusedxml.ElementTree.Element) -> list[AppEntry]:
    """The apps an <App> *condition* names -- the indexed clsN/labelN/pkgN form.  Read
    only for harvesting; profedit.get_app_entries owns editing them.
    """
    indexed: dict[int, dict[str, str]] = {}
    for child in element:
        match = _APP_CONDITION_TAG_RE.match(child.tag)
        if match:
            indexed.setdefault(int(match.group(2)), {})[match.group(1)] = (child.text or "").strip()
    return [
        AppEntry(pkg=fields.get("pkg", ""), label=fields.get("label", ""), cls=fields.get("cls", ""))
        for _, fields in sorted(indexed.items())
        if fields.get("pkg")
    ]


def read_icon_element(element: defusedxml.ElementTree.Element) -> IconRef | None:
    """The icon an <Img> points at, or None if it points at nothing.

    A <var> wins over everything else: an <Img> that carries one is resolved on the phone,
    whatever else was left in the element beside it.
    """
    variable = _child_text(element, "var")
    if variable:
        return IconRef(kind="var", name=variable)

    name = _child_text(element, "nme")
    package = _child_text(element, "pkg")
    activity_class = _child_text(element, "cls")

    if name:
        return IconRef(kind="pack", name=name, pkg=package) if package else IconRef(kind="builtin", name=name)
    if package:
        return IconRef(kind="app", pkg=package, cls=activity_class)
    return None


def write_icon_element(element: defusedxml.ElementTree.Element, icon: IconRef | None) -> None:
    """Rewrite an <Img> to point at one icon.  Every child this module knows about is
    cleared first, so switching an icon from an app's to a built-in cannot leave the old
    <pkg> behind to be read back as an icon pack.  Anything else in there -- <tint> above
    all -- is not touched: it is the user's, and it outlives a change of icon.
    """
    _remove_children(element, _ICON_TAGS)
    if icon is None:
        return
    if icon.kind == "var":
        _set_child_text(element, "var", icon.name)
        return
    if icon.kind == "app":
        _set_child_text(element, "pkg", icon.pkg)
        if icon.cls:
            _set_child_text(element, "cls", icon.cls)
        return
    _set_child_text(element, "nme", icon.name)
    if icon.kind == "pack" and icon.pkg:
        _set_child_text(element, "pkg", icon.pkg)


# ==========================================
# The value a text field holds
# ==========================================


# What marks a package field as holding a Tasker variable rather than a package name.
VARIABLE_PREFIX = "%"


def is_variable_reference(text: str) -> bool:
    """Whether a package field holds a variable rather than a package name.

    The whole test is a leading '%' and something after it, deliberately.  A stricter rule
    would reject values Tasker itself writes: this repo's own backup carries
    '%app_package(%ld_selected_index)' and '%App(%par1)' in <appPkg>, which are an array
    index and a function call, not the plain name a variable-name pattern would allow.  What
    is on the far side of the '%' is Tasker's business, not this tool's.
    """
    text = text.strip()
    return text.startswith(VARIABLE_PREFIX) and len(text) > len(VARIABLE_PREFIX)


def variable_app_entry(name: str) -> AppEntry:
    """One App entry that names a variable instead of an installed app.

    Label the same as the package, class empty -- not invented, but copied from what Tasker
    writes: every variable-valued <App> in this repo's backup has <label> repeating the
    <appPkg> text and no <appClass> at all.  Which is also what resolve_app already produces
    for any package it does not recognise, so a variable typed straight into the field and
    one picked through the GUI come out identical.
    """
    name = name.strip()
    return AppEntry(pkg=name, label=name, cls="")


def format_app_value(entries: list[AppEntry]) -> str:
    """What an App argument's field shows: the package names, comma-joined.

    The packages rather than the labels, because the package is what Tasker matches on and
    what a %variable is typed into (backups in this repo hold <appPkg>%app_package</appPkg>).
    Labels and classes are re-attached on the way back by parse_app_value.
    """
    return _APP_LIST_JOINER.join(entry.pkg for entry in entries)


def parse_app_value(text: str) -> list[AppEntry]:
    """Turn what the field holds back into entries, re-attaching each package's label and
    class from the inventory.

    A package the inventory has never heard of -- typed by hand, or a %variable -- keeps
    its own text as its label and gets no class.  Tasker matches on the package, so that
    is a working App; an action that launches a specific activity (Launch App) will want
    its class, which is exactly what picking from the list rather than typing gives you.
    """
    return [resolve_app(token.strip()) for token in text.split(",") if token.strip()]


def format_icon_value(icon: IconRef | None) -> str:
    """What an Icon argument's field shows -- see _ICON_APP_PREFIX for the spelling."""
    if icon is None:
        return ""
    if icon.kind == "var":
        return icon.name
    if icon.kind == "pack":
        return f"{icon.name}{_ICON_PACK_SEPARATOR}{icon.pkg}"
    if icon.kind == "app":
        return f"{_ICON_APP_PREFIX}{icon.pkg}{_ICON_APP_SEPARATOR}{icon.cls}" if icon.cls else (
            f"{_ICON_APP_PREFIX}{icon.pkg}"
        )
    return icon.name


def parse_icon_value(text: str) -> IconRef | None:
    """Read a field's text back as an icon reference.  Blank is None -- an <Img> with
    nothing in it, which is what an action with no icon set has always had.
    """
    text = text.strip()
    if not text:
        return None
    if text.startswith("%"):
        return IconRef(kind="var", name=text)
    if text.startswith(_ICON_APP_PREFIX):
        package, _, activity_class = text.removeprefix(_ICON_APP_PREFIX).partition(_ICON_APP_SEPARATOR)
        return IconRef(kind="app", pkg=package.strip(), cls=activity_class.strip())
    if _ICON_PACK_SEPARATOR in text:
        name, _, package = text.partition(_ICON_PACK_SEPARATOR)
        return IconRef(kind="pack", name=name.strip(), pkg=package.strip())
    return IconRef(kind="builtin", name=text)


# ==========================================
# The inventory itself
# ==========================================

# The tree the current inventory was built from, compared by identity: loading another
# backup replaces PrimeItems.xml_root with a new object.  The sentinel (rather than None)
# makes the first call harvest even when nothing is loaded, so 'no configuration' is a
# harvested empty inventory rather than a permanently-deferred one.
_NOT_HARVESTED = object()
_harvested_from: object = _NOT_HARVESTED
# The other input, which moves independently of the tree: a fetch lands new Applications
# without any backup being reloaded.  _cache_stamp is bumped by whatever changes the
# fetched list; the inventory is rebuilt when the stamp it was built under falls behind.
_cache_stamp = 0
_built_at_cache_stamp = -1
_device_apps: list[AppEntry] = []
_cache_loaded = False
_apps: list[AppEntry] = []
_apps_by_package: dict[str, AppEntry] = {}
_icons: list[IconRef] = []
_generation = 0


def generation() -> int:
    """Bumped every time the inventory is rebuilt.

    Addability depends on the inventory (see taskedit.classify_action_addability), and
    list_addable_actions memoizes addability on the grounds that its inputs are static for
    the process lifetime.  That stopped being true here, so the memo carries the generation
    it was built under and rebuilds when this moves.  Without it, loading a configuration
    would leave 'Launch App' greyed out with a stale reason until restart.
    """
    _ensure_harvested()
    return _generation


def apps() -> list[AppEntry]:
    """Every Application the inventory knows, by label."""
    _ensure_harvested()
    return _apps


def icons() -> list[IconRef]:
    """Every icon the inventory knows, built-ins first."""
    _ensure_harvested()
    return _icons


def have_apps() -> bool:
    """Whether an App-typed argument can be offered for editing at all.  Empty inventory,
    empty picker, nothing to type into it from -- so the argument stays read-only, exactly
    as it was before this module existed.
    """
    return bool(apps())


def have_icons() -> bool:
    """The Icon counterpart of have_apps()."""
    return bool(icons())


def resolve_app(package: str) -> AppEntry:
    """The inventory's entry for a package, or a bare entry carrying just the package.

    A variable is answered by the convention rather than by the inventory (see
    variable_app_entry).  It has to be: a configuration can carry <appPkg>%app_package</appPkg>
    with no <label> beside it, and resolving through the harvest would then hand back a blank
    label -- so the same variable would come out labelled when picked in the Profile App
    condition, which builds its entry directly, and unlabelled when typed into an argument
    field, which comes through here.  One answer, and it is the one Tasker writes.
    """
    if is_variable_reference(package):
        return variable_app_entry(package)
    _ensure_harvested()
    return _apps_by_package.get(package, AppEntry(pkg=package, label=package))


def _merge_app(known: dict[str, AppEntry], entry: AppEntry) -> None:
    """Keep the most complete triple seen for a package.

    The same app is named in a dozen places in a backup and not always in full -- one
    action has its class, another only its package.  Filling the blanks in from whichever
    occurrence has them means picking it once gets a complete triple, rather than whichever
    partial one happened to be encountered first.
    """
    existing = known.get(entry.pkg)
    if existing is None:
        known[entry.pkg] = entry
        return
    known[entry.pkg] = AppEntry(
        pkg=entry.pkg,
        label=existing.label or entry.label,
        cls=existing.cls or entry.cls,
    )


def _sorted_apps(entries: Iterable[AppEntry]) -> list[AppEntry]:
    """Applications in the order a picker should open on: by label, then by package.

    Variable-valued packages (<appPkg>%app_package</appPkg> and friends -- real, and in this
    repo's own backup) sort last rather than first: '%' leads the alphabet, and a picker
    that opens on a screen of variables buries the apps it exists to offer.
    """
    return sorted(
        entries,
        key=lambda entry: (entry.pkg.startswith("%"), (entry.label or entry.pkg).lower(), entry.pkg),
    )


def _harvest(root: defusedxml.ElementTree.Element | None) -> tuple[list[AppEntry], list[IconRef]]:
    """Walk a whole configuration for its <App> and <Img> elements.

    Every one of them, wherever it sits -- a Task action's argument, a Profile's App
    condition, a Task's own icon, a Scene element's.  An icon that is good enough for a
    Scene button is good enough for a Notify, and the point of the harvest is breadth.
    """
    known_apps: dict[str, AppEntry] = {}
    known_icons: dict[tuple[str, str, str, str], IconRef] = {}
    if root is None:
        return [], []

    for element in root.iter("App"):
        for entry in read_app_element(element) + read_app_condition_entries(element):
            _merge_app(known_apps, entry)

    for element in root.iter("Img"):
        icon = read_icon_element(element)
        if icon is not None:
            known_icons[(icon.kind, icon.name, icon.pkg, icon.cls)] = icon
        # An app's icon names an app, so it stocks the app list too -- with its launcher
        # class, which is the field hardest to come by.
        if icon is not None and icon.kind == "app":
            _merge_app(known_apps, AppEntry(pkg=icon.pkg, cls=icon.cls))

    apps_sorted = _sorted_apps(known_apps.values())
    # Built-ins first, then packs, then app icons, then variables: the order they are
    # likely to be wanted in, and it keeps the ~250 built-in names of a real backup from
    # being interleaved with a handful of app icons.
    kind_order = {"builtin": 0, "pack": 1, "app": 2, "var": 3}
    icons_sorted = sorted(
        known_icons.values(),
        key=lambda icon: (kind_order.get(icon.kind, 9), icon.display.lower()),
    )
    return apps_sorted, icons_sorted


def _ensure_harvested() -> None:
    global _harvested_from, _built_at_cache_stamp, _apps, _apps_by_package, _icons, _generation  # noqa: PLW0603

    _ensure_cache_loaded()
    root = getattr(PrimeItems, "xml_root", None)
    if root is _harvested_from and _cache_stamp == _built_at_cache_stamp:
        return

    _apps, _icons = _harvest(root)
    _apps = _merged_with_device_apps(_apps)
    _apps_by_package = {entry.pkg: entry for entry in _apps}
    _harvested_from = root
    _built_at_cache_stamp = _cache_stamp
    _generation += 1


def _merged_with_device_apps(harvested: list[AppEntry]) -> list[AppEntry]:
    """Fold the fetched Applications in with the harvested ones.

    Merged rather than concatenated or preferred: the two sources are good at different
    fields.  A fetch knows every installed package, but its label and launcher activity are
    whatever 'List Apps' reported and may not have lined up (see parse_device_payload).  The
    harvest knows only the apps this configuration names, but every one of its triples came
    out of a file Tasker itself wrote, so its label and class are exactly right.  Taking the
    harvested value where there is one, and the fetched value otherwise, gives each package
    the best field available from either.
    """
    if not _device_apps:
        return harvested

    known: dict[str, AppEntry] = {}
    for entry in list(harvested) + _device_apps:
        _merge_app(known, entry)
    return _sorted_apps(known.values())


# ==========================================
# Fetching the list from the Android device
# ==========================================

# The helper Task MapTasker installs on the device to do the enumerating, and the file it
# writes.  The name carries a version because the Task is installed once and left there: a
# later MapTasker that needs a different Task installs it under a different name rather
# than trying to decide whether the one already on the device is the one it meant.  An
# orphaned older one is harmless and can be deleted in Tasker.
#
# ---------------------------------------------------------------------------------------
# THE ONE SWITCH.  Set this to False and every difference below reverts together: the helper
# Task goes back to its v1 name and its v1 shape (three bulk 'List Apps' calls), the poll
# budget goes back to 30 seconds, and nothing else in this module or above it changes.  The
# payload format is deliberately identical either way, so parse_device_payload, the cache,
# the pickers and the tests are all untouched by the choice.  It is read at import, not per
# call: flip it and restart.
#
# Why it exists: 'List Apps' answers Package, App and Activity as three independent lists,
# and measured against a real device they do NOT line up -- the first fetch came back
# '(package names only)', which is parse_device_payload discarding a label list of the wrong
# length rather than mislabelling every app with its neighbour's name.  Pairing each label
# to its own package with 'Test App' costs one on-device iteration per installed app, which
# is the part that might prove too cumbersome in practice; hence a switch rather than a
# rewrite.  Activities are NOT paired: 'Test App' has no activity type to ask for (see
# actiont.lookup_values["344"]), so those stay on the bulk call and stay length-checked.
# ---------------------------------------------------------------------------------------
PAIR_LABELS_ON_DEVICE = True

_HELPER_TASK_BULK = "MapTasker Get Apps v1"
_HELPER_TASK_PAIRED = "MapTasker Get Apps v2"
# Versioned because the Task is installed once and left on the device: a different shape gets
# a different name rather than this having to decide whether the one already there is the one
# it meant (see _install_helper_task).  Backing the switch out therefore goes back to using
# v1, which is still sitting on the device from before; v2 is left behind and can be deleted
# in Tasker.
HELPER_TASK_NAME = _HELPER_TASK_PAIRED if PAIR_LABELS_ON_DEVICE else _HELPER_TASK_BULK
# Where the helper writes its answer, and where this reads it back from.  Tasker's Write
# File resolves a relative path against the device's storage root, and the HTTP server's
# 'file' route is rooted at the same place (see guiutils.get_list_of_files, which strips
# '/storage/emulated/0' off the paths it lists for exactly this reason), so these two are
# the same file spelled the two ways each end wants it.
_DEVICE_RESULT_WRITE_PATH = "Tasker/maptasker_apps.txt"
_DEVICE_RESULT_READ_PATH = "/Tasker/maptasker_apps.txt"

# The payload the helper writes.  A header line, then one 'section name' line followed by
# one line holding that whole section joined together, then a terminator.
#
# One line per section rather than one line per app so that nothing depends on a newline
# surviving a trip through Tasker's Str argument and back -- and _PAYLOAD_JOINER rather
# than a comma because app labels contain commas ('Bonza, Jigsaw') and package names do
# not contain this.
_PAYLOAD_HEADER = "MAPTASKER-APPS 1"
_PAYLOAD_TERMINATOR = "MAPTASKER-END"
_PAYLOAD_JOINER = "|~|"
_PAYLOAD_PACKAGES = "PACKAGES"
_PAYLOAD_LABELS = "LABELS"
_PAYLOAD_ACTIVITIES = "ACTIVITIES"
_PAYLOAD_SECTIONS = (_PAYLOAD_PACKAGES, _PAYLOAD_LABELS, _PAYLOAD_ACTIVITIES)

# actionc.py keys for the three actions the helper Task is built out of, and the arguments
# each one needs set.  All three are 'addable' by taskedit's own classifier (every argument
# is an Int, a Str or a checkbox), which is what lets the Task be synthesized rather than
# shipped as a blob of XML.
# The file a helper Task is told to work on, written the way Tasker reads it: %par1, filled
# in at run time by run_task_on_android (see it for where that arrives from).  Every helper
# that handles one object's file uses this in place of a literal path, which is what lets the
# staged file carry the object's own name instead of one baked-in filename shared by every
# import.
_STAGE_PATH_PARAMETER = "%par1"
# The characters Tasker names are free to contain and filenames are not.  The same
# substitution profedit.sanitize_filename and projedit.sanitize_filename make -- spelled
# again rather than imported, because importing either module would be a cycle (see the
# module docstring), and held to theirs by a test the way the folder names are.
_ILLEGAL_IN_FILENAME = re.compile(r'[\\/:*?"<>|]')

_LIST_APPS_ACTION = "815t"  # arg0 Type (dropdown), arg1 Match, arg2 Store Result In
_VARIABLE_JOIN_ACTION = "592t"  # arg0 Name, arg1 Joiner, arg2 Delete Parts
_WRITE_FILE_ACTION = "410t"  # arg0 File, arg1 Text, arg2 Append, arg3 Add Newline
# Used only when PAIR_LABELS_ON_DEVICE is on.
_FOR_ACTION = "39t"  # arg0 Variable, arg1 Items, arg2 Structure Output
_END_FOR_ACTION = "40t"  # no arguments
_TEST_APP_ACTION = "344t"  # arg0 Type (dropdown), arg1 Data, arg2 Store Result In
_VARIABLE_SET_ACTION = "547t"  # arg0 Name, arg1 To, ... arg4 Append
# 'Test App' asks one question about one package.  'App Name' is the only one of its twelve
# types that is any use here -- there is no 'launcher activity' among them, which is why the
# activity list cannot be paired the same way.  See actiont.lookup_values["344"].
_TEST_APP_NAME_TYPE = "App Name"
# The 'Type' dropdown's options, by the label apply_arg_values writes back (it stores the
# option's index, and finds it by matching the label) -- see actiont.lookup_values["815"].
_LIST_APPS_PACKAGE = "Package"
_LIST_APPS_LABEL = "App"
_LIST_APPS_ACTIVITY = "Activity"
# Where each 'List Apps' run puts its answer.  Named for MapTasker so a helper Task running
# on someone's device cannot collide with a variable of their own.
_PACKAGES_VARIABLE = "%mtapps_pkg"
_LABELS_VARIABLE = "%mtapps_lbl"
_ACTIVITIES_VARIABLE = "%mtapps_cls"
# The loop's own two locals, when pairing.  Lowercase, so Tasker scopes them to one run of
# the Task and no state can survive into the next fetch.
_LOOP_PACKAGE_VARIABLE = "%mtapp"
_LOOP_LABEL_VARIABLE = "%mtapp_name"

# How long to wait for the helper Task to finish and its file to appear.  Three bulk
# 'List Apps' calls are seconds rather than milliseconds on a real device, and 30 seconds
# leaves room for a slow one without leaving the user staring at a spinner over a device
# that is never going to answer.  Pairing labels adds an on-device iteration per installed
# app -- a few hundred of them -- so that budget is raised rather than the fetch timing out
# on a device that is working perfectly well, just slowly.
_RESULT_POLL_SECONDS = 2.0
_RESULT_POLL_ATTEMPTS = 60 if PAIR_LABELS_ON_DEVICE else 15


def parse_device_payload(text: str) -> tuple[list[AppEntry], str]:
    """Read the helper Task's file back into Applications.

    Returns (entries, error_message); a non-empty error means the payload was not one this
    understands and nothing should be cached from it.

    **The alignment question this is built around** (app_icon_fetch_design.md §3): it is not
    established that 'List Apps' returns Package, App and Activity in the same order, and it
    cannot be established without a real device.  So the package list is authoritative -- it
    is the identity, and it is the field Tasker matches on -- and a label or activity list
    is used ONLY if it has exactly as many entries.  A list of a different length is
    discarded rather than zipped: mislabelling every app is far worse than labelling none,
    because a wrong label looks right.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _PAYLOAD_HEADER:
        return [], "The file the Android device wrote is not a MapTasker application list."
    if not any(line.strip() == _PAYLOAD_TERMINATOR for line in lines):
        return [], "The Android device's application list is incomplete -- the Task may still be running."

    sections: dict[str, list[str]] = {}
    for index, line in enumerate(lines):
        name = line.strip()
        if name in _PAYLOAD_SECTIONS and index + 1 < len(lines):
            sections[name] = _split_payload_section(lines[index + 1])

    packages = sections.get(_PAYLOAD_PACKAGES, [])
    if not any(packages):
        return [], "The Android device reported no applications."

    labels = sections.get(_PAYLOAD_LABELS, [])
    activities = sections.get(_PAYLOAD_ACTIVITIES, [])
    if len(labels) != len(packages):
        logger.info(f"Android app labels ({len(labels)}) do not line up with packages ({len(packages)}); ignoring.")
        labels = []
    if len(activities) != len(packages):
        logger.info(f"Android app activities ({len(activities)}) do not line up with packages; ignoring.")
        activities = []

    entries = []
    for index, package in enumerate(packages):
        if not package:
            continue
        entries.append(
            AppEntry(
                pkg=package,
                label=labels[index] if labels else "",
                cls=activities[index] if activities else "",
            ),
        )
    return entries, ""


def _split_payload_section(line: str, unset_prefix: str = "%mtapps_") -> list[str]:
    """One section's joined line, back into its parts.

    Args:
        unset_prefix: what an unset variable of this section's kind is spelled with --
            '%mtapps_' for the Applications payload, '%lfp_' for the file list.

    A section whose variable was never set comes back as the literal '%mtapps_pkg' -- that
    is what Tasker writes for a variable with no value -- so a line that is just one of
    those is an empty section, not an app called '%mtapps_pkg'.  Positions are otherwise
    kept exactly as they came, blanks included: the three sections are matched up by index,
    so dropping an empty one here would shift every label after it onto the wrong app.
    """
    line = line.strip()
    if not line or line.startswith(unset_prefix):
        return []
    parts = [part.strip() for part in line.split(_PAYLOAD_JOINER)]
    # One trailing empty is the append loop's signature, not an app -- see
    # _add_paired_label_actions.  Dropped here rather than there because a bulk-joined line
    # never has one, so this costs the other path nothing and keeps the two formats
    # identical (which is what makes PAIR_LABELS_ON_DEVICE reversible without a parser
    # change).  Only ONE, and only at the end: any other blank is a real position, and
    # removing it would shift every entry after it onto the wrong package.
    if parts and not parts[-1]:
        parts.pop()
    return parts


def _add_paired_label_actions(add: Callable[[str, dict[str, str]], str]) -> str:
    """The loop that gives every package its own label.  Returns "" or an error message.

    Built because 'List Apps' does not answer Package and App in the same order -- measured,
    not assumed: the first real fetch came back '(package names only)', which is
    parse_device_payload refusing to zip two lists of different lengths.  Asking 'Test App'
    for one package's name at a time pairs them by construction, so no order has to be
    trusted.

    The cost is one on-device iteration per installed app, which is why the whole thing is
    behind PAIR_LABELS_ON_DEVICE.

    Three details that are not obvious:

      * The label variable is seeded with the package before 'Test App' overwrites it, so a
        lookup that fails leaves the package name as the label rather than the literal text
        '%mtapp_name'.  Tasker writes an unset variable out as its own name.
      * Each label is appended WITH a trailing joiner, because Tasker has no 'join with a
        separator between' in an append.  That leaves one empty part at the end of the line,
        which _split_payload_section drops -- and a bulk-joined line has no trailing joiner,
        so that drop is a no-op on the other path.
      * It iterates '%mtapps_pkg()', the array, which is why build_helper_task runs this
        before joining the packages into a string.
    """
    return (
        # Start from empty: the appends below build this line up one label at a time.
        add(_VARIABLE_SET_ACTION, {"0": _LABELS_VARIABLE, "1": "", "4": "0"})
        or add(_FOR_ACTION, {"0": _LOOP_PACKAGE_VARIABLE, "1": f"{_PACKAGES_VARIABLE}()", "2": "0"})
        or add(_VARIABLE_SET_ACTION, {"0": _LOOP_LABEL_VARIABLE, "1": _LOOP_PACKAGE_VARIABLE, "4": "0"})
        or add(
            _TEST_APP_ACTION,
            {"0": _TEST_APP_NAME_TYPE, "1": _LOOP_PACKAGE_VARIABLE, "2": _LOOP_LABEL_VARIABLE},
        )
        or add(
            _VARIABLE_SET_ACTION,
            {"0": _LABELS_VARIABLE, "1": f"{_LOOP_LABEL_VARIABLE}{_PAYLOAD_JOINER}", "4": "1"},
        )
        or add(_END_FOR_ACTION, {})
    )


def build_helper_task(task_name: str = HELPER_TASK_NAME):  # noqa: ANN201
    """Build the helper Task, out of taskedit's own Add-Task machinery.

    Returns an EditableTask, or an error message string if it could not be built (the same
    either/or taskedit.create_new_task itself uses).

    Synthesized rather than shipped as a blob of XML on purpose.  Every action it needs --
    'List Apps', 'Variable Join', 'Write File' -- is one taskedit already classifies as
    addable, so this is the same code path an ordinary user's Add Task takes, and the Task
    stays correct if an argument definition in actionc.py is ever corrected.  It also means
    there is no second copy of Tasker's XML shape to keep in step with the first.

    Imported lazily because taskedit imports this module: the cycle is real, and this is the
    same way taskedit.save_task_to_android reaches back into maputil2.
    """
    from maptasker.src import taskedit  # noqa: PLC0415

    edited_task = taskedit.create_new_task(task_name, "100")
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}

    def add(action_key: str, args: dict[str, str]) -> str:
        action = taskedit.add_action_to_task(edited_task, action_key)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit.arg_key(action.act_number, arg_id)] = value
        return ""

    # 'Store Result In' produces an array (%v1, %v2, ...); 'Variable Join' collapses it into
    # the one variable a 'Write File' can write.  The two are kept apart here because the
    # order matters when pairing: the loop iterates the packages ARRAY, so it has to run
    # before that array is collapsed into a single string.
    def list_apps(list_type: str, variable: str) -> str:
        return add(_LIST_APPS_ACTION, {"0": list_type, "1": "", "2": variable})

    def join(variable: str) -> str:
        return add(_VARIABLE_JOIN_ACTION, {"0": variable, "1": _PAYLOAD_JOINER, "2": "0"})

    error = list_apps(_LIST_APPS_PACKAGE, _PACKAGES_VARIABLE)
    if error:
        return error

    if PAIR_LABELS_ON_DEVICE:
        error = _add_paired_label_actions(add)
        if error:
            return error

    error = join(_PACKAGES_VARIABLE)
    if error:
        return error

    if not PAIR_LABELS_ON_DEVICE:
        error = list_apps(_LIST_APPS_LABEL, _LABELS_VARIABLE) or join(_LABELS_VARIABLE)
        if error:
            return error

    # Activities are asked for in bulk whether or not labels are paired -- 'Test App' has no
    # activity type to ask for, so there is nothing to pair them with.  They stay subject to
    # parse_device_payload's length check, and are dropped when they fail it.
    error = list_apps(_LIST_APPS_ACTIVITY, _ACTIVITIES_VARIABLE) or join(_ACTIVITIES_VARIABLE)
    if error:
        return error

    # Then the file, a line at a time.  The first write truncates and every later one
    # appends, so a re-run replaces the previous answer rather than growing it.
    payload_lines = (
        _PAYLOAD_HEADER,
        _PAYLOAD_PACKAGES,
        _PACKAGES_VARIABLE,
        _PAYLOAD_LABELS,
        _LABELS_VARIABLE,
        _PAYLOAD_ACTIVITIES,
        _ACTIVITIES_VARIABLE,
        _PAYLOAD_TERMINATOR,
    )
    for index, text in enumerate(payload_lines):
        error = add(
            _WRITE_FILE_ACTION,
            {"0": _DEVICE_RESULT_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if error:
            return error

    errors = taskedit.apply_edits_to_task(edited_task, task_name, "100", values)
    if errors:
        return errors[0]
    return edited_task


def _device_key(ip_address: str, ip_port: str) -> str:
    """How one Android device is named in the cache and in messages."""
    return f"{ip_address.strip()}:{ip_port.strip()}"


def staged_paths(location: str, object_name: str, extension: str, fallback: str) -> tuple[str, str, str]:
    """Where one object's file goes on the device: (filename, read path, absolute path).

    Three spellings of one place, because the three ends want different ones: POST /upload
    takes a folder and a filename separately, the 'file' GET route wants a path from the
    storage root, and Tasker's own actions want an absolute one (see _DEVICE_RESULT_WRITE_PATH
    for the same split).

    The name is the OBJECT'S OWN -- 'My Profile.prf.xml', not 'maptasker_import.prf.xml'.
    That is the whole point: the staged file sits in the folder the user browses, so it has
    to be the file they are looking for.  A fixed name meant a Profile that reached the
    device and could not be found there, and -- since every import wrote the same path -- a
    second import silently replacing the first one's file.  It also means that when the
    handoff to Tasker fails, what is waiting in Tasker's own import browser is a file with
    the right name on it, which is exactly how the Scene route already works.

    fallback is what an object whose name is nothing but illegal characters falls back to,
    mirroring each editor's own sanitize_filename.  Two names can still sanitize onto one
    path ('Wake: Up' and 'Wake_ Up'), which is the collision the file-save buttons prompt
    about; here the caller takes a safety copy instead.
    """
    filename = f"{_ILLEGAL_IN_FILENAME.sub('_', object_name).strip() or fallback}.{extension}"
    return filename, f"/{location}/{filename}", f"/storage/emulated/0/{location}/{filename}"


# Auth keys already obtained this session, by device.  The same idea as userintr's own
# self.android_auth_key -- every request to the api/* endpoints needs one, and fetching a
# fresh one prompts on the device -- kept here rather than reached for on the GUI because
# the pickers that trigger a fetch are module-level functions with no MyGui to hand.
_auth_keys: dict[str, str] = {}


def run_task_on_android(
    ip_address: str,
    ip_port: str,
    task_name: str,
    auth_key: str,
    par1: str = "",
) -> tuple[int, str]:
    """Run an existing Task on the device, via the Tasker HTTP API's POST /api/tasks
    (Params/Body: task object; Response: the Task's return value).

    Returns (0, "") or (return_code, error_message).  Return code 9 is passed through
    unchanged so the caller can tell a rejected key apart from everything else and retry
    with a fresh one, exactly as taskedit.save_task_to_android does.

    par1 ARRIVES IN THE TASK AS %par1, and this is not a guess -- it is read off the HTTP
    Server Example's own handler in this repo's sample backup (XML/backup.xml), the same way
    the 'Import Data' route was derived.  Profile 'POST Task' (prof1079) runs task1077,
    whose act17 is:

        code 547  'Variable Set'  %par1 = %http_request_body.par1   IF %http_request_body.par1 is set

    -- act18 does the same for %par2, and act19 is a JavaScriptlet doing setLocal() for
    every key of a 'variables' object in the body.  The Perform Task that then runs the
    named Task (act22/act25, code 130) has Local Variable Passthrough on (arg6=1) limited to
    '!%http_request*/%return/%tasks' -- everything EXCEPT those -- so %par1 is passed
    straight through to the Task being run.

    That is what makes a per-object staged path possible.  The helper Tasks used to bake
    their file path in at install time because 'POST /api/tasks carries a Task name and
    nothing else', which was simply wrong: it carries whatever the body carries.  Sent only
    when non-empty, so a Task with no path to be told about is called exactly as before.
    """
    from maptasker.src.maputil2 import http_post_request  # noqa: PLC0415

    body: dict[str, str] = {"name": task_name}
    if par1:
        body["par1"] = par1

    return_code, response = http_post_request(
        ip_address,
        ip_port,
        "",
        "api/tasks",
        "",
        json.dumps(body).encode("utf-8"),
        auth_key,
        content_type="application/json",
    )
    if return_code != 0:
        return return_code, str(response)
    return 0, ""


def _install_task_on_android(
    ip_address: str,
    ip_port: str,
    auth_key: str,
    task_name: str,
    builder: Callable[[], object],
) -> tuple[int, str]:
    """Put one of MapTasker's helper Tasks on the device, if it isn't there already.

    Args:
        task_name: what the Task is called on the device, version and all.
        builder: builds it -- build_helper_task or build_file_list_task -- returning an
            EditableTask, or a string if it could not be built.

    Checked before importing rather than importing every time: Tasker's api/import does not
    replace a Task of the same name, it adds another one, so a fetch that re-imported
    unconditionally would leave a growing pile of identical Tasks in the user's
    configuration.  That is also why every helper Task name carries a version.
    """
    from maptasker.src import taskedit  # noqa: PLC0415

    if taskedit.verify_task_on_android(ip_address, ip_port, task_name, auth_key):
        return 0, ""

    built = builder()
    if isinstance(built, str):
        return 8, built

    # via_file=False: a helper Task is MapTasker's own plumbing, and an ordinary import
    # leaves a .tsk.xml behind in /Tasker/tasks -- a folder the user browses for their own
    # Tasks.  'MapTasker Send Profile v1.tsk.xml' sitting in it is litter they did not ask
    # for and would have to recognize before deleting.
    return_code, result, used_key = taskedit.save_task_to_android(
        built,
        ip_address,
        ip_port,
        task_name,
        auth_key,
        via_file=False,
    )
    if return_code != 0:
        return return_code, str(result)
    if used_key:
        _auth_keys[_device_key(ip_address, ip_port)] = used_key

    # api/import answering 200 is not evidence Tasker committed the Task -- the same
    # reservation save_task_to_android_directory exists for.
    if not taskedit.verify_task_on_android(ip_address, ip_port, task_name, used_key or auth_key):
        return 8, (
            f"'{task_name}' was sent to the device but Tasker did not report it afterwards.  "
            "Tasker 6.2 or higher is required, and Tasker must be running."
        )
    return 0, ""


def _ensure_auth_key(ip_address: str, ip_port: str) -> tuple[int, str]:
    """This device's API key -- the one already cached for this session, or a fresh one.

    Returns (0, key) or (return_code, error_message).  Fetching a fresh one prompts on the
    device, which is why the cache exists and why both fetches go through here.
    """
    from maptasker.src.maputil2 import get_android_auth_key  # noqa: PLC0415

    key = _device_key(ip_address, ip_port)
    if auth_key := _auth_keys.get(key, ""):
        return 0, auth_key

    return_code, auth_key = get_android_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key
    _auth_keys[key] = auth_key
    return 0, auth_key


def _run_task_refreshing_key(
    ip_address: str,
    ip_port: str,
    task_name: str,
    auth_key: str,
    par1: str = "",
) -> tuple[int, str, str]:
    """Run task_name, and if the device rejects the key it was given, get a fresh one and
    try once more.

    Returns (return_code, message, key_used) -- the key so the caller can carry the
    refreshed one forward.  Return code 9 is 'key rejected', the same signal
    taskedit.save_task_to_android retries on.

    par1 goes with both attempts, not just the first: a retry that dropped the path would
    run the helper against an unset %par1 -- see run_task_on_android.
    """
    from maptasker.src.maputil2 import get_android_auth_key  # noqa: PLC0415

    return_code, message = run_task_on_android(ip_address, ip_port, task_name, auth_key, par1)
    if return_code != 9:
        return return_code, message, auth_key

    return_code, refreshed = get_android_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, refreshed, auth_key
    _auth_keys[_device_key(ip_address, ip_port)] = refreshed

    return_code, message = run_task_on_android(ip_address, ip_port, task_name, refreshed, par1)
    return return_code, message, refreshed


def _poll_for_result(
    ip_address: str,
    ip_port: str,
    read_path: str = _DEVICE_RESULT_READ_PATH,
    attempts: int = _RESULT_POLL_ATTEMPTS,
    subject: str = "application list",
) -> tuple[str, str]:
    """Wait for a helper Task's file to appear, whole.  Returns (text, error_message).

    Args:
        read_path: the file to wait for, spelled the way the 'file' route wants it.
        attempts: how many polls before giving up -- each one _RESULT_POLL_SECONDS apart.
        subject: what the file holds, for the error messages ("application list").

    'Whole' is the reason this polls on content rather than on existence: the Task writes
    the file a line at a time, so it exists and is readable long before it is finished, and
    a read that lands in the middle of that would report a truncated list as a complete
    one.  The terminator line is what says it is done -- and it is the same terminator for
    every helper Task, which is what lets one poller serve them all.
    """
    from maptasker.src.maputil2 import http_request  # noqa: PLC0415

    last_error = f"The Android device did not produce {'an' if subject[0] in 'aeiou' else 'a'} {subject}."
    for attempt in range(attempts):
        return_code, response = http_request(ip_address, ip_port, read_path, "file", "?download=1")
        if return_code == 0:
            text = response.decode("utf-8", errors="replace") if isinstance(response, bytes) else str(response)
            if any(line.strip() == _PAYLOAD_TERMINATOR for line in text.splitlines()):
                return text, ""
            last_error = f"The Android device's {subject} never finished being written."
        elif return_code != 6:  # 6 is 'not there yet', which is the normal case while waiting.
            last_error = str(response)

        if attempt < attempts - 1:
            time.sleep(_RESULT_POLL_SECONDS)

    return "", last_error


def fetch_apps_from_device(ip_address: str, ip_port: str) -> tuple[int, str]:
    """Fetch the full list of installed Applications from an Android device and cache it.

    The whole exchange, in order: get an API key, put the helper Task on the device if it
    isn't there, delete any previous answer, run the Task, wait for the file, read it,
    parse it, cache it.  Returns (0, a sentence saying what was fetched) or
    (return_code, an error message fit to show the user).

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2 or
    higher -- the same requirements 'Save to Android' already has.

    Blocking, deliberately: it sleeps between polls, and the file it is waiting for takes
    seconds to appear.  Callers on the GUI thread must hand it to run.io_bound, the way
    guiutils.ping_android_device does with its own probe.
    """
    from maptasker.src.maputil2 import http_delete_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."

    key = _device_key(ip_address, ip_port)
    return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = _install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        HELPER_TASK_NAME,
        build_helper_task,
    )
    if return_code != 0:
        return return_code, message
    auth_key = _auth_keys.get(key, auth_key)

    # Clear the previous answer out of the way BEFORE running anything -- see
    # maputil2.http_delete_request for why this is not optional.  Its own failure is not
    # fatal: the terminator check in _poll_for_result is a second line of defence, and a
    # device that refuses the delete may still run the Task perfectly well.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _DEVICE_RESULT_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_DEVICE_RESULT_READ_PATH} before fetching: {delete_error}")

    # A rejected cached key is retried once with a fresh one -- see
    # _run_task_refreshing_key, which is where that dance now lives.
    return_code, message, auth_key = _run_task_refreshing_key(ip_address, ip_port, HELPER_TASK_NAME, auth_key)
    if return_code != 0:
        return return_code, message

    text, error = _poll_for_result(ip_address, ip_port)
    if error:
        return 8, error

    entries, error = parse_device_payload(text)
    if error:
        return 8, error

    cache_error = _store_fetched_apps(key, entries)
    labelled = sum(1 for entry in entries if entry.label)
    summary = f"{len(entries)} applications fetched from {key}"
    summary += f" ({labelled} with names)." if labelled else " (package names only)."
    if cache_error:
        summary += f"  They could not be saved for next time: {cache_error}"
    return 0, summary


# ==========================================
# Listing the device's XML files
# ==========================================

# Listing the XML files on a device used to be a GET on the 'maplist' route, which is not
# part of the HTTP Server Example project at all: it is served by a separate 'MapTasker
# List' Profile the user had to find on TaskerNet, import by hand, and remember to leave
# enabled.  That was MapTasker's second manual setup step, it failed with a timeout that
# named no cause, and its Profile hardcodes port 1821 in its HTTP Request event -- so a
# device whose server runs anywhere else could not be made to work at all.
#
# The listing is done by a helper Task instead, installed, run and read back exactly the
# way the Applications fetch above does it (fetch_apps_from_device), over endpoints the
# HTTP Server Example itself provides.  Nothing has to be imported by hand, and there is
# no Profile to leave enabled.
#
# Why a Task and not a Profile: Tasker's HTTP API can import a *Task* (POST /api/import),
# and that is all it can import.  POST /api/profiles only sets the enabled/active status
# of a Profile that already exists, and the /upload route just drops a .prf.xml file on
# the device's storage without Tasker ever reading it (see profedit.save_profile_to_android,
# whose docstring is explicit about that).  So installing the old Profile automatically was
# never on the table; doing its job with a Task is.
FILE_LIST_TASK_NAME = "MapTasker List Files v1"
# The directory listed, and the one the Task is BUILT with -- Tasker's 'List Files' takes
# its path as an argument, so the path is baked into the Task at install time rather than
# passed per run (POST /api/tasks carries a task name, and nothing else).  The Task is
# installed once and left there, so changing this means bumping the version in
# FILE_LIST_TASK_NAME, the same contract HELPER_TASK_NAME documents.  Every caller asks for
# this one directory (see guiutils.get_list_of_files).
FILE_LIST_DIRECTORY = "/storage/emulated/0/Tasker"
# Where the helper writes its answer and where this reads it back -- the same file spelled
# the two ways each end wants it, for the reason _DEVICE_RESULT_WRITE_PATH explains.
_FILE_LIST_WRITE_PATH = "Tasker/maptasker_files.txt"
_FILE_LIST_READ_PATH = "/Tasker/maptasker_files.txt"

# The payload, in the same shape as the Applications one -- header, section name, the
# section on one line, terminator -- so _poll_for_result's terminator check and
# _split_payload_section serve both.  Its own header, though: reading one as the other
# would be a silent misparse rather than an error.
_FILE_PAYLOAD_HEADER = "MAPTASKER-FILES 1"
_PAYLOAD_FILES = "FILES"

# 'List Files' (actionc '446t', "Get Files/Folders Properties") and the arguments it needs.
# arg0 is its Output Variables bundle, which the synthesizer fills in on its own.
_LIST_FILES_ACTION = "446t"  # arg1 Path, arg2 Type, arg3 Name/Path Filter, arg4 Other
#                              Filters, arg5 Recurse, arg6 Sort
_LIST_FILES_TYPE = "Files"  # Files, not folders.
_LIST_FILES_MATCH = "*xml"  # What MapTasker can actually open.
_LIST_FILES_OTHER = "NotEmpty"  # A zero-byte .xml is nothing anyone wants offered.
# Recurse, because the XML lives in Tasker's subdirectories (configs/user, tasks,
# profiles, scenes), not in the directory itself.
_LIST_FILES_RECURSE = "1"
# 'List Files' answers into a fixed set of %lfp_* array variables rather than into a
# 'Store Result In' of our choosing -- see the Output Variables the action declares.  The
# full paths are the only one of them this needs.
_FILE_PATHS_VARIABLE = "%lfp_full_path"
# What Tasker writes for that variable when the listing found nothing: an unset variable
# comes out as its own name.  Passed to _split_payload_section so an empty listing reads
# as empty rather than as one file called '%lfp_full_path'.
_LIST_FILES_UNSET_PREFIX = "%lfp_"

# One 'List Files' call over a directory of XML is quick -- nothing like the per-app
# iteration the Applications fetch can do -- so the shorter of the two budgets is plenty.
_FILE_LIST_POLL_ATTEMPTS = 15


def build_file_list_task(task_name: str = FILE_LIST_TASK_NAME, directory: str = FILE_LIST_DIRECTORY):  # noqa: ANN201
    """Build the file-listing helper Task.  Returns an EditableTask, or an error message.

    Three actions: 'List Files' over `directory`, 'Variable Join' to collapse the array of
    paths it produces into one string, and 'Write File' to put that where the 'file' route
    can read it.  Synthesized out of taskedit's own Add-Task machinery for the reasons
    build_helper_task gives -- all three are actions taskedit already classifies as
    addable, so this is the path an ordinary user's Add Task takes.

    The old 'MapTasker List' Profile merged the paths with a per-file count and joined
    them with commas, which left guiutils.get_list_of_files chopping three characters off
    the end of every entry and splitting on a character that can legitimately appear in a
    file name.  This writes the paths and nothing else, joined with _PAYLOAD_JOINER.
    """
    from maptasker.src import taskedit  # noqa: PLC0415

    edited_task = taskedit.create_new_task(task_name, "100")
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}

    def add(action_key: str, args: dict[str, str]) -> str:
        action = taskedit.add_action_to_task(edited_task, action_key)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit.arg_key(action.act_number, arg_id)] = value
        return ""

    error = add(
        _LIST_FILES_ACTION,
        {
            "1": directory,
            "2": _LIST_FILES_TYPE,
            "3": _LIST_FILES_MATCH,
            "4": _LIST_FILES_OTHER,
            "5": _LIST_FILES_RECURSE,
        },
    )
    if error:
        return error

    error = add(_VARIABLE_JOIN_ACTION, {"0": _FILE_PATHS_VARIABLE, "1": _PAYLOAD_JOINER, "2": "0"})
    if error:
        return error

    # The first write truncates and the rest append, so a re-run replaces the previous
    # answer rather than growing it -- and the terminator only lands once the paths are
    # already on disk, which is what makes _poll_for_result's check mean something.
    payload_lines = (_FILE_PAYLOAD_HEADER, _PAYLOAD_FILES, _FILE_PATHS_VARIABLE, _PAYLOAD_TERMINATOR)
    for index, text in enumerate(payload_lines):
        error = add(
            _WRITE_FILE_ACTION,
            {"0": _FILE_LIST_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if error:
            return error

    errors = taskedit.apply_edits_to_task(edited_task, task_name, "100", values)
    if errors:
        return errors[0]
    return edited_task


def parse_file_list_payload(text: str) -> tuple[list[str], str]:
    """Read the file-listing Task's file back into a list of paths.

    Returns (paths, error_message); a non-empty error means the payload was not one this
    understands and nothing should be believed from it.  The paths come back exactly as
    Tasker reported them -- absolute, storage root and all -- since it is the caller that
    knows how it wants them spelled (see guiutils.get_list_of_files).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FILE_PAYLOAD_HEADER:
        return [], "The file the Android device wrote is not a MapTasker file list."
    if not any(line.strip() == _PAYLOAD_TERMINATOR for line in lines):
        return [], "The Android device's file list is incomplete -- the Task may still be running."

    paths: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() == _PAYLOAD_FILES and index + 1 < len(lines):
            paths = _split_payload_section(lines[index + 1], _LIST_FILES_UNSET_PREFIX)
            break

    paths = [path for path in paths if path]
    if not paths:
        return [], f"No XML files were found on the Android device under {FILE_LIST_DIRECTORY}."
    return paths, ""


def fetch_file_list_from_device(
    ip_address: str,
    ip_port: str,
    directory: str = FILE_LIST_DIRECTORY,
) -> tuple[int, list[str] | str]:
    """Fetch the list of XML files on an Android device.

    The same exchange fetch_apps_from_device runs, for a different Task: get an API key,
    install the Task if it isn't there, delete any previous answer, run it, wait for the
    file, read it, parse it.  Nothing is cached -- a file list goes stale the moment the
    user saves a backup, and it costs one Task run to ask again.

    Returns (0, paths) or (return_code, error_message) -- the same two-shaped answer
    guiutils.get_list_of_files has always handed its own callers.

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2
    or higher.  It does NOT require the 'MapTasker List' Profile, which is the point.

    Blocking, deliberately: it sleeps between polls.  Callers on the GUI thread must hand
    it to run.io_bound, as guiutils.validate_or_filelist_xml's own caller does.
    """
    from maptasker.src.maputil2 import http_delete_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."

    key = _device_key(ip_address, ip_port)
    return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = _install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        FILE_LIST_TASK_NAME,
        lambda: build_file_list_task(FILE_LIST_TASK_NAME, directory),
    )
    if return_code != 0:
        return return_code, message
    auth_key = _auth_keys.get(key, auth_key)

    # Clear the previous answer BEFORE running anything: a listing is asked for repeatedly
    # within one session, so a stale file here is the normal case rather than the rare one,
    # and reading one would report the files as they were several backups ago.  A failed
    # delete is not fatal -- _poll_for_result's terminator check is the second line of
    # defence -- for the reasons the Applications fetch gives.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _FILE_LIST_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_FILE_LIST_READ_PATH} before listing: {delete_error}")

    return_code, message, auth_key = _run_task_refreshing_key(ip_address, ip_port, FILE_LIST_TASK_NAME, auth_key)
    if return_code != 0:
        return return_code, message

    text, error = _poll_for_result(
        ip_address,
        ip_port,
        _FILE_LIST_READ_PATH,
        _FILE_LIST_POLL_ATTEMPTS,
        "file list",
    )
    if error:
        return 8, error

    paths, error = parse_file_list_payload(text)
    if error:
        return 8, error
    return 0, paths


# ==========================================
# Importing a Profile into Tasker's live configuration
# ==========================================
#
# PROTOTYPE.  The central question it exists to answer is not answered yet, and the wrong
# answer destroys a configuration.  Read this before pointing it at a device you care about.
#
# Tasker's HTTP API cannot import a Profile.  POST /api/import takes a Task and nothing
# else, POST /api/profiles only flips enabled/active on a Profile that already exists, and
# /upload drops a .prf.xml on storage that Tasker never reads (see
# profedit.save_profile_to_android, whose docstring is explicit about it).  That is where
# 'Save Profile To Android' has stopped.
#
# But /api/import is not a Tasker feature.  It is a Task in the HTTP Server Example
# project, and the step in it that does the importing is an ordinary action anyone can put
# in a Task of their own.  Taken apart from this repo's own sample backup, the Profile
# 'POST Import' (prof491) runs task473, whose act13 is:
#
#     code 153  'Import Data'   arg0 Type=0   arg1 Source=0   arg2 = %http_request_body
#
# Type is a dropdown, and its two options are ["Task", "Configuration"] --
# actiont.lookup_values["153"].  api/import hardcodes 0.  So the endpoint is Task-only
# because that Task was written that way, not because Tasker can only import Tasks.
#
# This does what api/import does with Type set to the other option: stage the .prf.xml on
# the device, then run a helper Task that reads it back and hands it to 'Import Data'.
#
# WHAT IS NOT KNOWN, AND WHY THE CALLER HAS TO SAY SO OUT LOUD
#
# What 'Configuration' means to Tasker when it is handed a standalone .prf.xml.  A merge --
# the Profile is added and everything else is left alone -- is what this is for.  A replace
# -- the configuration becomes that one file's contents, and the user's other several
# hundred Profiles stop existing -- is the other possibility, and nothing in Tasker's
# documentation rules it out.  It cannot be settled from here, only by running it against a
# device whose configuration is expendable.
#
# Hence acknowledged_risk.  There is no safe default for a question nobody has answered, so
# the caller states that it accepts the answer it might get.  Until it IS answered, nothing
# in the GUI should call this -- see import_profile_to_device's own note.
#
# Two smaller unknowns, both harmless beside that one:
#
#   * Source (arg1).  actiont.lookup_values["153a"] is a one-entry placeholder, ["Source"],
#     so this codebase does not know what that dropdown's options are called.  0 is what the
#     shipped api/import Task sends and is what this sends; _IMPORT_SOURCE_INDEX is there so
#     another value can be tried without editing the builder (see build_import_profile_task
#     on why that one argument does not go through apply_edits_to_task).
#   * Duplicates.  api/import ADDS a Task whose name is already taken rather than replacing
#     it -- see _install_task_on_android, which is built around that.  If Configuration
#     behaves the same way, importing a Profile that is already on the device leaves two of
#     them.  Refused up front unless allow_existing says otherwise.
# v3 since 2026-08-30, when the staged file stopped being one fixed 'maptasker_import.prf.xml'
# and started carrying the Profile's own name.  THE VERSION IN THE NAME IS LOAD-BEARING: what
# this Task reads is part of its body, _install_task_on_android installs only what is not
# already there, and a device still holding v1 or v2 would go on reading the old fixed path
# forever -- silently, since those Tasks run and write their answer file either way.  A new
# name is a new Task.
IMPORT_PROFILE_TASK_NAME = "MapTasker Import Profile v3"
# Where the .prf.xml is staged for the helper to read.  Tasker's own Profile folder, the same
# one the offer routes stage into and the same one profedit.ANDROID_PROFILE_LOCATION writes
# to -- see _PROFILE_STAGE_LOCATION's comment in the offer-routes section for the report
# behind that, which applies here exactly as it does there: a file staged in /Tasker is one
# the user cannot find in the folder they browse.  Defined at this point in the file rather
# than beside its siblings because this is the first of the two sections to need it.
_PROFILE_STAGE_LOCATION = "Tasker/profiles"
_PROFILE_EXTENSION = "prf.xml"
# Where the helper says it got to, read back the same way every other helper's answer is.
_IMPORT_RESULT_WRITE_PATH = "Tasker/maptasker_import.txt"
_IMPORT_RESULT_READ_PATH = "/Tasker/maptasker_import.txt"
# Its own header, so reading one helper's answer as another's is an error rather than a
# silent misparse -- the reason _FILE_PAYLOAD_HEADER has one too.  The terminator is shared,
# because _poll_for_result's completeness check is shared.
_IMPORT_PAYLOAD_HEADER = "MAPTASKER-IMPORT 1"
_IMPORT_PAYLOAD_STAGED = "STAGED"

_READ_FILE_ACTION = "417t"  # arg0 File, arg1 To Var, arg2 Structure Output
_IMPORT_DATA_ACTION = "153t"  # arg0 Type (dropdown), arg1 Source (dropdown), arg2 Variable
_IMPORT_DATA_TYPE_LOOKUP = "153"  # actiont.lookup_values key for that Type dropdown
# The Type option this is all for, by the label apply_arg_values matches on (it stores the
# option's index and finds it by label) -- the same contract _LIST_APPS_PACKAGE documents.
IMPORT_TYPE_CONFIGURATION = "Configuration"  # index 1
IMPORT_TYPE_TASK = "Task"  # index 0 -- what api/import itself sends; here to test against
_IMPORT_SOURCE_INDEX = "0"
# Where the .prf.xml lands on the device between being uploaded and being imported.  Named
# for MapTasker so it cannot collide with a variable of the user's own, as the Applications
# helper's are.
_IMPORT_XML_VARIABLE = "%mtimport_xml"
# One file read and one import: seconds, not the minutes an Applications fetch can take.
_IMPORT_POLL_ATTEMPTS = 15


def _import_task_name(import_type: str, source_index: str) -> str:
    """The name this helper is installed under, for a given pair of settings.

    It has to change whenever the Task's BODY changes, because _install_task_on_android
    installs by name and skips a name that is already there -- the same contract
    HELPER_TASK_NAME documents with its version suffix.  Both of this Task's settings are
    baked into its actions at install time, so a run that changed one and kept the name
    would quietly re-run the Task built with the other, and the prototype would be
    measuring the previous experiment.

    The default pair keeps the plain name; anything else is spelled out, so a device that
    has been experimented on shows which Task is which in Tasker's own list.
    """
    if import_type == IMPORT_TYPE_CONFIGURATION and source_index == _IMPORT_SOURCE_INDEX:
        return IMPORT_PROFILE_TASK_NAME
    return f"{IMPORT_PROFILE_TASK_NAME} [{import_type}/{source_index}]"


def build_import_profile_task(
    task_name: str = IMPORT_PROFILE_TASK_NAME,
    import_type: str = IMPORT_TYPE_CONFIGURATION,
    source_index: str = _IMPORT_SOURCE_INDEX,
):  # noqa: ANN201
    """Build the Profile-importing helper Task.  Returns an EditableTask, or an error message.

    Three kinds of action: 'Read File' to pull the staged .prf.xml into a variable, 'Import
    Data' to hand that variable to Tasker, and 'Write File' to record that it got that far.
    Synthesized out of taskedit's own Add-Task machinery for the reasons build_helper_task
    gives -- all three are addable (every argument is an Int, a Str or a checkbox), so this
    is the path an ordinary user's Add Task takes.

    The Write Files are the entire verification story, and they work only because 'Import
    Data' can fail (action_codes["153t"].canfail is True) and a failed action stops the
    Task: nothing after it runs, the terminator never lands, and _poll_for_result reports a
    timeout rather than a success that did not happen.  POST /api/tasks answering 200 says
    only that the Task was started, which is why it is not evidence of anything on its own.
    """
    from maptasker.src import taskedit  # noqa: PLC0415
    from maptasker.src.actiont import lookup_values  # noqa: PLC0415

    # Checked rather than trusted because the failure would be silent and would be the
    # wrong import: apply_arg_values resolves a dropdown by matching the label against its
    # options and falls back to index 0 for anything it does not recognize -- and index 0
    # of this particular dropdown is 'Task'.  A typo would quietly import the Profile XML
    # as a Task instead of saying so.
    type_options = lookup_values.get(_IMPORT_DATA_TYPE_LOOKUP, [])
    if import_type not in type_options:
        return f"'{import_type}' is not an 'Import Data' type.  Expected one of: {', '.join(type_options)}."

    edited_task = taskedit.create_new_task(task_name, "100")
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}

    def add(action_key: str, args: dict[str, str]):  # noqa: ANN202
        """Append one action and stage its argument values.  Returns the action, or an
        error message -- unlike build_helper_task's `add`, which only ever needs the error,
        because one of the actions here has an argument that cannot be set through
        apply_edits_to_task (see below).
        """
        action = taskedit.add_action_to_task(edited_task, action_key)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit.arg_key(action.act_number, arg_id)] = value
        return action

    # Structure Output off (arg2): the .prf.xml is wanted verbatim, as the bytes that were
    # uploaded.  Letting Tasker parse it into %mtimport_xml.<something> would hand 'Import
    # Data' a structure rather than the document.
    #
    # The file READ is %par1, handed over when the Task is run rather than baked in here, so
    # one installed Task serves every Profile and each one keeps its own name on the device
    # -- see run_task_on_android and staged_paths.
    read_action = add(_READ_FILE_ACTION, {"0": _STAGE_PATH_PARAMETER, "1": _IMPORT_XML_VARIABLE, "2": "0"})
    if isinstance(read_action, str):
        return read_action

    import_action = add(_IMPORT_DATA_ACTION, {"0": import_type, "2": _IMPORT_XML_VARIABLE})
    if isinstance(import_action, str):
        return import_action

    # Only after the import, and only if it did not fail -- see this function's docstring.
    # %par1 again, so the answer file records the file this run was actually about rather
    # than a path that was true when the Task was installed.
    payload_lines = (_IMPORT_PAYLOAD_HEADER, _IMPORT_PAYLOAD_STAGED, _STAGE_PATH_PARAMETER, _PAYLOAD_TERMINATOR)
    for index, text in enumerate(payload_lines):
        written = add(
            _WRITE_FILE_ACTION,
            {"0": _IMPORT_RESULT_WRITE_PATH, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if isinstance(written, str):
            return written

    errors = taskedit.apply_edits_to_task(edited_task, task_name, "100", values)
    if errors:
        return errors[0]

    # Source (arg1) is set on the element directly, which no other argument in any helper
    # Task does.  apply_arg_values resolves a dropdown by matching the label against its
    # options, and lookup_values["153a"] is the one-entry placeholder ["Source"] -- so the
    # only value reachable through that path is 0.  0 is the right default (it is what the
    # shipped api/import Task sends), but a prototype whose whole job is to answer open
    # questions should not be the one making one of them unaskable.  Written after
    # apply_edits_to_task, not before, so it cannot be overwritten by it.
    source_element = import_action.action_element.find("Int[@sr='arg1']")
    if source_element is None:
        return "'Import Data' has no Source argument -- actionc.py's definition of '153t' has changed."
    source_element.set("val", source_index)

    return edited_task


def verify_profile_on_android(ip_address: str, ip_port: str, profile_name: str, auth_key: str) -> bool:
    """Whether Tasker reports a Profile of this name, via GET /api/profiles?name=<name>
    (Response: profile objects -- a JSON array of {"name", "enabled", "active"}).

    The Profile counterpart of taskedit.verify_task_on_android, and it earns its keep for
    the same reason: the run request's own 200 is not evidence that anything was committed.
    It is also the ONLY reading available here -- unlike a Task import, there is no second
    endpoint to fall back on -- which is what makes it the pre-check for a duplicate as
    well as the confirmation afterwards.

    Returns True only on a successful GET that lists at least one Profile of that name; a
    request that failed is False, i.e. 'not confirmed', never 'confirmed absent'.
    """
    from urllib.parse import quote  # noqa: PLC0415

    from maptasker.src.maputil2 import http_request  # noqa: PLC0415

    return_code, response = http_request(
        ip_address.strip(),
        ip_port.strip(),
        "",
        "api/profiles",
        f"?name={quote(profile_name)}",
        auth_key,
    )
    if return_code != 0:
        return False

    try:
        profiles = json.loads(response)
    except (ValueError, TypeError):
        return False

    return any(isinstance(profile, dict) and profile.get("name") == profile_name for profile in profiles)


# The return code both Profile routes use for "Tasker already has one of these".  Its own
# code rather than the generic 8 because it is the one failure a caller can do something
# about without the user retyping anything -- the GUI turns it into a confirm-and-retry (see
# userintr.import_profile_into_tasker_event) -- and matching on the message text to find it
# would break the first time the wording is improved.  6 and 9 are already spoken for
# (maputil2's 'not there' and 'key rejected'); 7 was free.
DUPLICATE_PROFILE_CODE = 7


def _refuse_duplicate_profile(
    ip_address: str,
    ip_port: str,
    profile_name: str,
    auth_key: str,
    allow_existing: bool,
) -> str:
    """The duplicate check the HEADLESS route makes before anything is uploaded or run.
    Returns a refusal to hand the user, or "" to go ahead.

    Not used by the routes that go through Tasker's import screen, and deliberately so:
    measured on a real device, Tasker asks the user itself whether to replace a Profile it
    already has.  Checking first there would be a second prompt in front of a better one --
    and a wrong one, since it would warn about a duplicate Tasker is about to offer to
    replace.

    'Import Data' shows nothing and asks nothing.  Tasker's api/import ADDS a Task whose
    name is taken rather than replacing it (see _install_task_on_android) and there is no
    reason yet to think a headless Profile import differs -- so on that route a duplicate
    would appear silently, and both copies would be live at once.  Hence this survives, for
    the one route that has no screen to do the asking.
    """
    if allow_existing or not verify_profile_on_android(ip_address, ip_port, profile_name, auth_key):
        return ""
    return (
        f"Tasker already has a Profile named '{profile_name}'.  Importing may add a second one rather "
        "than replace it.  Rename this Profile, delete that one on the device, or pass allow_existing=True."
    )


def _stage_profile_xml(
    ip_address: str,
    ip_port: str,
    profile_xml: bytes,
    profile_name: str,
) -> tuple[int, str]:
    """Put the .prf.xml where a helper Task can reach it, under the Profile's OWN name.
    Returns (0, its absolute path on the device) or (code, message).

    Shared by both routes -- they differ only in what they do with the file once it is
    there, so a change to where or how it is staged has one place to happen.

    The path comes back rather than being a constant because it is per-Profile now and the
    caller has to hand it to the helper Task at run time -- see staged_paths and
    run_task_on_android.

    Read back and compared byte for byte, because /upload answers 200 whatever it wrote
    (see maputil2.http_upload_request): it does not validate the location, it creates
    missing folders silently, and it reports nothing at the HTTP layer.  A half-written
    .prf.xml would not fail loudly here -- it would be handed to Tasker.
    save_profile_to_android reads its own upload back for exactly this reason.
    """
    from maptasker.src.maputil2 import http_upload_request, read_back_uploaded_file  # noqa: PLC0415

    filename, read_path, task_path = staged_paths(
        _PROFILE_STAGE_LOCATION,
        profile_name,
        _PROFILE_EXTENSION,
        "profile",
    )

    return_code, response = http_upload_request(ip_address, ip_port, _PROFILE_STAGE_LOCATION, filename, profile_xml)
    if return_code != 0:
        return return_code, str(response)

    # Retried rather than trusted -- the write and the read are two unrelated Tasker Tasks,
    # and a write still settling answers 404 to a read that arrives too soon.  A single
    # un-retried GET here used to fail an import whose file was on the device a moment
    # later; see maputil2.read_back_uploaded_file, which every other upload in this program
    # already goes through.
    verify_code, verify_content = read_back_uploaded_file(ip_address, ip_port, read_path, profile_xml)
    if verify_code != 0:
        return 8, str(verify_content)
    return 0, task_path


def _validate_import_request(
    profile_xml: bytes,
    profile_name: str,
    ip_address: str,
    ip_port: str,
) -> str:
    """What both routes need before they are worth starting.  Returns "" or a message."""
    if not ip_address or not ip_port:
        return "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."
    if not profile_name:
        return "A Profile name is needed."
    if not profile_xml:
        return "There is no Profile XML to import."
    return ""


def import_profile_to_device(  # noqa: PLR0911
    profile_xml: bytes,
    profile_name: str,
    ip_address: str,
    ip_port: str,
    acknowledged_risk: bool = False,
    allow_existing: bool = False,
    import_type: str = IMPORT_TYPE_CONFIGURATION,
    source_index: str = _IMPORT_SOURCE_INDEX,
) -> tuple[int, str]:
    """Put a Profile into Tasker's live configuration on the device.  PROTOTYPE -- read the
    section comment above before calling this, and do not call it from the GUI until the
    merge-or-replace question it describes has been answered against an expendable device.

    Args:
        profile_xml: the standalone .prf.xml, as bytes -- profedit.render_standalone_profile_xml
            encoded UTF-8, i.e. exactly what save_profile_to_android uploads today.
        acknowledged_risk: the caller stating it accepts an import whose effect on the rest
            of the configuration is not established.  False refuses without touching the
            device.
        allow_existing: proceed even though Tasker already reports a Profile of this name.
            False refuses, because a Configuration import may well add a second one rather
            than replace the first.
        import_type, source_index: the two open questions, as arguments.  Changing either
            installs a differently-NAMED helper Task -- see _import_task_name -- so one
            experiment cannot be run with the Task another one left behind.

    The exchange, in order: get an API key, refuse if the Profile is already there, install
    the helper Task if it isn't, clear the last answer, upload the .prf.xml and read it back
    to confirm it landed whole, run the Task, wait for its answer, then ask Tasker whether
    the Profile exists.  Returns (0, a sentence saying what happened) or (return_code, an
    error message fit to show the user).

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2 or
    higher -- 'Save to Android' already requires both.

    Blocking, deliberately, exactly as fetch_apps_from_device is: it sleeps between polls.
    A caller on the GUI thread must hand it to run.io_bound.
    """
    from maptasker.src.maputil2 import http_delete_request  # noqa: PLC0415

    if not acknowledged_risk:
        return 8, (
            "Refusing to import: what Tasker does to the rest of the configuration when it is handed a "
            "Profile as a 'Configuration' import has not been established.  Test it against a device whose "
            "configuration is expendable, and pass acknowledged_risk=True once you know."
        )

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    profile_name = profile_name.strip()
    if refusal := _validate_import_request(profile_xml, profile_name, ip_address, ip_port):
        return 8, refusal

    key = _device_key(ip_address, ip_port)
    return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    # Before anything is uploaded or run: a name Tasker already knows.  Checked here rather
    # than left to the import because the import may not object -- see the duplicates note
    # in the section comment above.
    if refusal := _refuse_duplicate_profile(ip_address, ip_port, profile_name, auth_key, allow_existing):
        return DUPLICATE_PROFILE_CODE, refusal

    # Named for the settings it is built with, not just for the job it does -- see
    # _import_task_name for why a shared name would make the prototype lie.
    task_name = _import_task_name(import_type, source_index)
    return_code, message = _install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        task_name,
        lambda: build_import_profile_task(task_name, import_type, source_index),
    )
    if return_code != 0:
        return return_code, message
    auth_key = _auth_keys.get(key, auth_key)

    # Clear the last answer first, for the reason fetch_apps_from_device gives: a stale one
    # left in place would be read as this run's.  Its own failure is not fatal.
    delete_code, delete_error = http_delete_request(ip_address, ip_port, _IMPORT_RESULT_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_IMPORT_RESULT_READ_PATH} before importing: {delete_error}")

    return_code, message = _stage_profile_xml(ip_address, ip_port, profile_xml, profile_name)
    if return_code != 0:
        return return_code, message
    stage_task_path = message

    # The staged path goes over WITH the run, as %par1 -- one installed helper, a different
    # file each time.  See run_task_on_android.
    return_code, message, auth_key = _run_task_refreshing_key(
        ip_address,
        ip_port,
        task_name,
        auth_key,
        stage_task_path,
    )
    if return_code != 0:
        return return_code, message

    text, error = _poll_for_result(
        ip_address,
        ip_port,
        _IMPORT_RESULT_READ_PATH,
        _IMPORT_POLL_ATTEMPTS,
        "import result",
    )
    if error:
        # No answer means 'Import Data' failed and stopped the Task, or the Task never ran.
        # Either way nothing was imported, which is the one thing worth saying plainly.
        return 8, f"{error}  Tasker's 'Import Data' most likely refused the Profile XML."
    if not text.splitlines() or text.splitlines()[0].strip() != _IMPORT_PAYLOAD_HEADER:
        return 8, "The file the Android device wrote is not a MapTasker import result."

    # The helper got past 'Import Data' without failing.  That is not the same as Tasker
    # having committed a Profile, which is what this asks.
    if not verify_profile_on_android(ip_address, ip_port, profile_name, auth_key):
        return 8, (
            f"'{profile_name}' was imported without error, but Tasker does not report a Profile of that name "
            "afterwards.  Check Tasker on the device before importing it again."
        )

    return 0, f"'{profile_name}' was imported into Tasker on {key}."


# ==========================================
# Offering a Profile or a Project to Tasker's own import screen
# ==========================================
#
# The Import Data route above hands the XML to Tasker headlessly, and is unproven.  This one
# hands the staged file to Android, which gives it to whatever registered for Tasker's file
# types -- Tasker's ordinary import screen, the one that comes up when a .prf.xml or a
# .prj.xml is opened from a file manager.  The user taps Import.
#
# CONFIRMED ON A REAL DEVICE (2026-08-27) for a Profile: the screen came up, the Profile
# imported, and Tasker offered to REPLACE a Profile it already had rather than adding a
# second.  That last part is why nothing here refuses a duplicate -- Tasker asks better than
# this could.
#
# WHY BOTH ROUTES EXIST
#
#   Import Data     headless -- but what 'Configuration' does to the REST of the
#                   configuration is not established, and the bad answer is unrecoverable.
#   Open File       one tap on the device -- but the semantics are Tasker's own documented
#                   import.  Nothing else in the configuration is at stake, so there is no
#                   acknowledged_risk gate on this one.
#
# So this is the one to reach for, and the one the GUI is built on -- see
# userintr.import_profile_into_tasker_event and import_project_into_tasker_event.
# SEND_INTENT_* stays as the fallback for a device where implicit resolution does not land
# on Tasker, not as a second candidate still being chosen between.
#
# WHAT THE ANSWER FILE PROVES, WHICH IS LESS THAN THE OTHER ROUTE'S
#
# 'Open File' fires an intent and returns; it does not wait for the person to decide.  So
# the Write Files after it run immediately, and the terminator means *the import screen was
# asked for*, not that anything was imported.  That is why this is two phases: the run is
# confirmed by the payload, and the import is confirmed separately by asking Tasker what it
# now has (await_import), for as long as it takes someone to pick up the phone.
#
# CONFIRMING A PROJECT, WHICH THE HTTP API CANNOT DO DIRECTLY
#
# There is no /api/projects.  Tasker's HTTP API can report Profiles, Tasks, Scenes and
# Globals by name, and that is the whole list -- so 'is this Project there now' is not a
# question that can be asked.
#
# What can be asked is whether the Profiles the Project OWNS are there, and a Project import
# brings its Profiles with it (projedit.render_standalone_project_xml bundles them).  So
# both kinds confirm the same way, through one list of Profile names: one name for a Profile
# import, its <pids> resolved to names for a Project import.  A Project with no Profiles at
# all has nothing to ask about and is simply unconfirmable, which is reported rather than
# guessed at.
#
# TaskerNet reaches the same screen via taskernet.com/shares/?user=...&id=Profile%3A<name>,
# and is not used: that URL only exists for a share PUBLISHED to Google's TaskerNet, so
# pushing a locally-edited Profile back to the user's own phone would mean publishing it to
# a third party first.  The local file reaches the same screen with nothing leaving the
# machine.  ('Browse URL' would also have been unbuildable here without an Applications
# fetch first -- its Package/App Name argument is category 'App', so
# classify_action_addability refuses it while the inventory is empty.  'Open File' takes a
# path and a mime type and nothing else.)
# The two endpoints an import can be confirmed against.  Tasker's HTTP API reports Profiles,
# Tasks, Scenes and Globals by name; a Project has no endpoint of its own, which is why a
# Project import is confirmed through the Profiles it brings (see offer_to_tasker).
PROFILES_ENDPOINT = "api/profiles"
SCENES_ENDPOINT = "api/scenes"
# The same shape -- a JSON array of objects with a "name" -- so verify_names_on_android
# serves it too (it answers {"name":..., "running":...}; see taskedit.verify_task_on_android,
# which asks it the same question one name at a time).
TASKS_ENDPOINT = "api/tasks"

_OPEN_FILE_ACTION = "102t"  # arg0 File, arg1 Mime Type
_SEND_INTENT_ACTION = "877t"  # arg0 Action, arg1 Cat, arg2 Mime Type, arg3 Data,
#                               arg4-6 Extra, arg7 Package, arg8 Class, arg9 Target
# The mime type an explicit Send Intent carries.  It has a named component to be delivered
# to, so the type is not doing any matching -- it is what the receiver reads to know what it
# was handed.
_SEND_INTENT_MIME_TYPE = "text/xml"
# ...and the OPEN WITH route deliberately carries NONE.  This is the one that matters, and it
# is reasoned rather than measured, so here is the reasoning in full.
#
# 'Open File' fires an implicit ACTION_VIEW, which is what produces Android's "Open with..."
# chooser -- the same list a file manager puts up when you long-press a file.  It used to
# send 'text/xml', on the argument that with no mime type Android has only the extension to
# go on and neither '.prf.xml' nor '.prj.xml' is one it knows.  That argument is about
# Android INFERRING a type, and inferring one is not what has to happen here.  What has to
# happen is Tasker's own intent-filter matching.
#
# An app that claims a file extension writes a filter with a scheme and a pathPattern
# ('.*\\.prf\\.xml') and NO android:mimeType.  Android's rule for those is unforgiving: a
# filter that declares no mimeType matches only an intent that carries no type.  So an
# ACTION_VIEW carrying 'text/xml' cannot match it, however right the path is -- and it is
# then matched only against filters that DO declare a type, which is every text/xml viewer on
# the device.  That is exactly what was seen on 2026-08-28: a chooser of seven apps with
# Tasker not among them.  Seven text/xml handlers is what asking for text/xml gets.
#
# Sending no type puts the extension filters back in the running, which is where Tasker is.
# It cannot be confirmed from here -- Tasker's manifest is not in this repo and the only
# proof is a device -- so if the chooser still comes up without Tasker in it, this is the
# line that was wrong, and the file is in Tasker's own folder under its own name to be
# imported by hand either way.
_OPEN_WITH_MIME_TYPE = ""
_OPEN_PAYLOAD_OFFERED = "OFFERED"
# Firing an intent is immediate; this is a timeout on the device answering at all.
_OPEN_POLL_ATTEMPTS = 15
# How long to keep asking Tasker whether the import turned up -- times _RESULT_POLL_SECONDS,
# so two minutes.  This one is waiting on a person, not on a device: they have to notice the
# screen, read it and tap Import.  Long enough not to give up on someone who put the phone
# down, short enough that a caller that never taps is not left hanging forever.
_CONFIRM_POLL_ATTEMPTS = 60
# And five minutes for a Scene, which is not one tap.  Its user has to open the Scenes tab,
# find 'Import One Scene' in a menu, work a file picker and pick the right file -- so the
# two minutes that suit an import screen already in front of them would time out on someone
# who is doing exactly what they were asked to do, and say the import had not happened.
MANUAL_IMPORT_POLL_ATTEMPTS = 150

# --- 'Send Intent', for when implicit resolution does not find Tasker -------------------
#
# 'Open File' asks Android to find something that handles the file, and trusts it to land on
# Tasker.  If it does not -- nothing registered for 'text/xml', or a chooser comes up and
# Tasker is not in it -- this says where to send it instead: ACTION_VIEW at Tasker's own
# activity, explicitly.
#
# MEASURED, 2026-08-28, and the reason this route is no longer only a fallback: a '.scn.xml'
# offered through 'Open File' brings up a chooser with no Tasker in it, while the identical
# offer of a '.prf.xml' lands on Tasker's import screen.  Same mime type, same action, same
# staged directory -- so what Tasker matches on is the EXTENSION in its manifest, and it
# claims Profile, Project and Task files but not Scene files.  No mime type fixes that; a
# Scene has to be addressed rather than advertised.
#
# NAMING THE PACKAGE IS NOT ENOUGH TO ADDRESS IT.  An intent with a package but no class is
# still resolved against that package's intent-filters -- exactly the matching that just
# failed -- so a Scene sent that way would fail the same way, silently.  Naming the class
# (arg8) makes the intent EXPLICIT, and an explicit intent skips filter matching altogether
# and is delivered to that activity whatever its manifest claims.
#
# The shape is not invented.  Every ACTION_VIEW 'Send Intent' in this repo's real backups
# uses Cat=None and Target=Activity, and the ones aimed at a particular app name it in
# Package (arg7) -- e.g. 'google.navigation:q=%address' at com.google.android.apps.maps.
#
# THE ONE WAY THIS CAN FAIL THAT 'Open File' CANNOT: the Data field has to be a URI, and the
# only URI available from here is 'file://'.  Since Android 7 an app that puts a file:// URI
# into an outgoing intent gets a FileUriExposedException -- which is precisely what 'Open
# File' exists to avoid, since it can hand out a content:// URI from Tasker's own
# FileProvider and this cannot.  Whether Tasker's 'Send Intent' converts it or passes it
# straight through is not established here.
_VIEW_ACTION = "android.intent.action.VIEW"
# Both dropdowns by the label apply_arg_values matches on -- see actiont.lookup_values
# ["877"] and ["877a"], and the real backups above, which agree on both.
_INTENT_CATEGORY_NONE = "None"
_INTENT_TARGET_ACTIVITY = "Activity"
_TASKER_PACKAGE = "net.dinglisch.android.taskerm"
# Tasker's main activity, and the component an explicit ACTION_VIEW is delivered to.  Not
# guessed: Tasker writes this class itself, in the two places a backup records a component
# -- an <Img> naming Tasker's own launcher icon (<cls> beside <pkg>), and an Application
# event's <appClass> beside its <appPkg>.  It is the launcher activity, so it is exported
# and an outside intent can start it; it is also what an implicitly-resolved '.prf.xml'
# reaches today, so a Scene sent here arrives where a working Profile import arrives.
_TASKER_MAIN_ACTIVITY = "net.dinglisch.android.taskerm.Tasker"
# Where MapTasker's own bookkeeping goes -- the answer files every helper Task writes, and
# nothing else.  Not a staging folder: the file being imported goes in Tasker's own folder
# for its kind (below), and a '.txt' of ours dropped among the user's Profiles would be
# litter in a place they browse.
_BOOKKEEPING_LOCATION = "Tasker"
# Where each kind's XML is staged for Tasker to be handed.  Tasker's own folders, not a
# scratch corner of /Tasker: the user goes looking there for the file that is being imported
# -- reported, for a Profile that was nowhere to be found in /Tasker/profiles -- and if the
# handoff fails (an Android that will not resolve the file to Tasker, which is now measured
# on a real device) that folder is where Tasker's own import browses.  The same strings
# profedit.ANDROID_PROFILE_LOCATION, projedit.ANDROID_PROJECT_LOCATION and
# sceneedit.ANDROID_SCENE_LOCATION use for the file-write button, held together by a test
# rather than by an import, since those modules import from this one's callers.
#
# The Profile folder is _PROFILE_STAGE_LOCATION, defined up in the Import Data section
# because that route stages into it too -- one folder per kind across BOTH routes, so a
# Profile on its way into Tasker is in the same place whichever way it was sent.
_PROJECT_STAGE_LOCATION = "Tasker/projects"
# Tasker's own Scene folder, the one its 'Scenes > Import One Scene' browses, and its Task
# folder, the one the Task import leaves its copy in.  Both are staging locations now that
# all four kinds go through the same offer -- and both are the same strings
# sceneedit.ANDROID_SCENE_LOCATION and taskedit.ANDROID_TASK_LOCATION use for the file-write
# buttons, held to them by a test rather than by an import for the reason above.
_SCENE_LOCATION = "Tasker/scenes"
_TASK_STAGE_LOCATION = "Tasker/tasks"


def _add_result_writes(
    add: Callable[[str, dict[str, str]], str],
    write_path: str,
    header: str,
    stage_path: str,
) -> str:
    """The four 'Write File' actions every offer Task ends with.  Returns "" or an error.

    The first write truncates and the rest append, so a re-run replaces the previous answer
    rather than growing it -- and the terminator lands last, which is what makes
    _poll_for_result's completeness check mean anything.

    Note what these are worth on this route, which is less than in build_import_profile_task:
    the action before them does not block on the user's decision, so they run whether or not
    anything is ever imported.  They confirm the Task ran and the intent went out.  Whether
    an import arrived is await_import's question, not this file's.
    """
    for index, text in enumerate((header, _OPEN_PAYLOAD_OFFERED, stage_path, _PAYLOAD_TERMINATOR)):
        error = add(
            _WRITE_FILE_ACTION,
            {"0": write_path, "1": text, "2": "0" if index == 0 else "1", "3": "1"},
        )
        if error:
            return error
    return ""


def _new_offer_task(task_name: str):  # noqa: ANN202
    """An empty Task plus the `add` helper both offer builders use.

    Returns (edited_task, add, values) or an error message string.  Synthesized out of
    taskedit's own Add-Task machinery for the reasons build_helper_task gives -- every
    action involved is one taskedit already classifies as addable, so this is the path an
    ordinary user's Add Task takes.
    """
    from maptasker.src import taskedit  # noqa: PLC0415

    edited_task = taskedit.create_new_task(task_name, "100")
    if isinstance(edited_task, str):
        return edited_task

    values: dict[str, str] = {}

    def add(action_key: str, args: dict[str, str]) -> str:
        action = taskedit.add_action_to_task(edited_task, action_key)
        if isinstance(action, list):
            return action[0] if action else f"'{action_key}' could not be added."
        for arg_id, value in args.items():
            values[taskedit.arg_key(action.act_number, arg_id)] = value
        return ""

    return edited_task, add, values


def _finish_offer_task(edited_task, task_name: str, values: dict[str, str]):  # noqa: ANN001, ANN202
    """Apply the staged argument values.  Returns the EditableTask or an error message."""
    from maptasker.src import taskedit  # noqa: PLC0415

    errors = taskedit.apply_edits_to_task(edited_task, task_name, "100", values)
    return errors[0] if errors else edited_task


def build_open_file_task(
    task_name: str,
    stage_path: str = _STAGE_PATH_PARAMETER,
    result_write_path: str = "",
    header: str = "",
    mime_type: str = _OPEN_WITH_MIME_TYPE,
):  # noqa: ANN201
    """Build the Task that puts Android's "Open with..." chooser up for the staged file.

    'Open File' on the staged path, then the four writes that say it ran.

    THIS IS THE "OPEN WITH..." ROUTE, and it is the one the GUI uses.  An implicit
    ACTION_VIEW is exactly what a file manager fires when you long-press a file and pick
    'Open with' -- Android puts up the chooser, the user picks Tasker, and Tasker's ordinary
    import screen comes up on a file it was handed the way it expects to be handed one.
    Nothing here decides what handles it, which is the point: the alternative is guessing
    what Android will resolve to and being wrong silently (see build_send_intent_task, and
    _OPEN_WITH_MIME_TYPE for why this sends no mime type at all).

    The staged path defaults to %par1 -- handed over with the run rather than baked in at
    install time.  It used to be baked in, on the belief that 'POST /api/tasks carries a
    Task name and nothing else'; it carries whatever the body carries, and the HTTP Server
    Example's own handler unpacks par1 into %par1 (see run_task_on_android for where that is
    read off).  That is what lets one installed Task open a file named after the Profile it
    belongs to, instead of every import sharing one filename.
    """
    built = _new_offer_task(task_name)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(_OPEN_FILE_ACTION, {"0": stage_path, "1": mime_type}) or _add_result_writes(
        add,
        result_write_path,
        header,
        stage_path,
    )
    if error:
        return error
    return _finish_offer_task(edited_task, task_name, values)


def build_send_intent_task(
    task_name: str,
    stage_path: str = _STAGE_PATH_PARAMETER,
    result_write_path: str = "",
    header: str = "",
    mime_type: str = _SEND_INTENT_MIME_TYPE,
    package: str = _TASKER_PACKAGE,
    activity_class: str = _TASKER_MAIN_ACTIVITY,
):  # noqa: ANN201
    """Build the Task that sends Tasker an explicit ACTION_VIEW for the staged file.

    The same job build_open_file_task does, addressed rather than broadcast -- see the
    section comment above for when that matters and for the file:// caveat that comes with
    it, and build_open_file_task for why the path is %par1 rather than a literal.  Its
    answer file means exactly what that one's does.

    Package AND class, not package alone: with only a package this is still matched against
    Tasker's intent-filters, which is the matching that fails for a Scene.  Both together
    make it an explicit component intent, which is delivered without matching anything --
    the whole reason this route can reach Tasker where 'Open File' cannot.
    """
    built = _new_offer_task(task_name)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(
        _SEND_INTENT_ACTION,
        {
            "0": _VIEW_ACTION,
            "1": _INTENT_CATEGORY_NONE,
            "2": mime_type,
            "3": f"file://{stage_path}",
            "7": package,
            "8": activity_class,
            "9": _INTENT_TARGET_ACTIVITY,
        },
    ) or _add_result_writes(add, result_write_path, header, stage_path)
    if error:
        return error
    return _finish_offer_task(edited_task, task_name, values)


@dataclass(frozen=True)
class OfferRoute:
    """One way of putting one kind of thing in front of Tasker's import screen.

    Two dimensions, and they multiply: WHAT is being imported (a Profile, a Project) decides
    the staged file's extension -- which is what tells Tasker what it is looking at -- and
    HOW the screen is opened (Open File, Send Intent) decides the action in the helper Task.
    Every combination is otherwise identical, so they are data handed to one orchestrator
    rather than four copies of it.

    Separate answer files and headers per combination are not incidental: reading one
    route's payload as another's has to be an error rather than a silent misparse, the same
    reason _FILE_PAYLOAD_HEADER differs from _PAYLOAD_HEADER.

    THE STAGED FILE IS NOT PART OF THE ROUTE, because it is not fixed any more.  It is named
    after the object being imported and worked out per call by staged_file_paths, then handed
    to the helper Task as %par1 at run time -- see run_task_on_android.  A route describes
    how Tasker is asked; the object decides what it is asked about.
    """

    label: str  # "Profile" / "Project" / "Scene" -- how this reads in a message to the user
    confirm_endpoint: str  # where an import of this kind can be asked about afterwards
    task_name: str
    builder: Callable[[], object]
    stage_location: str
    extension: str  # 'prf.xml' / 'prj.xml' -- what tells Tasker what it is looking at
    read_path: str
    header: str
    # A sentence for a handoff that did not land, with one '{path}' in it for the file it
    # was about.  A template rather than a finished string, since that file is per-object.
    failure_hint: str

    def staged_file_paths(self, object_name: str) -> tuple[str, str, str]:
        """(filename, read path, absolute path) for this object's staged file -- see
        staged_paths, which this is the per-route spelling of."""
        return staged_paths(self.stage_location, object_name, self.extension, self.label.lower())


def _build_offer_routes(
    label: str,
    extension: str,
    confirm_endpoint: str,
    stage_location: str,
) -> tuple[OfferRoute, OfferRoute]:
    """The Open File and Send Intent routes for one kind of thing, from its name and the
    extension Tasker recognizes it by.

    A factory rather than eight hand-written constants: every one of those fields is derived
    from these arguments, and the way a hand-written set goes wrong is one of them not being
    -- a Project route left pointing at the Profile route's answer file would read a stale
    Profile import as its own success.

    ONLY A PROFILE AND A PROJECT, which is not an oversight: a Scene cannot be handed to
    Tasker by intent at all (measured four ways -- see the section comment above), so it
    does not go through here.  userintr.import_scene_into_tasker_event uploads it under its
    own name and opens Tasker instead.

    THE STAGED FILE CARRIES THE OBJECT'S OWN NAME, and it did not used to.  It was one fixed
    'maptasker_import.<ext>' per kind, on the reasoning that the path had to be baked into
    the helper Task at install time because 'POST /api/tasks carries a name and nothing
    else'.  That premise was wrong -- the body carries par1, and the HTTP Server Example's
    own handler unpacks it into %par1 for the Task it runs (read off the sample backup; see
    run_task_on_android).  So one installed Task now serves every object, and the file in
    the folder is the file the user is looking for.

    What that premise cost, and why this is a fix rather than a polish: a Profile sent to the
    device could not be found in /Tasker/profiles under its own name, a second import
    silently overwrote the first one's staged file, and when the handoff to Tasker failed --
    which it does, on a device that will not resolve the file to Tasker -- what was left for
    the user to import by hand was a file called 'maptasker_import.prf.xml' with no way to
    tell which Profile it held.

    stage_location is the folder that file goes in.  The ANSWER file does not follow it --
    those are MapTasker's bookkeeping, and .txt files dropped among the user's Profiles would
    be litter in a place they browse.
    """
    key = label.lower()

    def route(verb: str, builder, hint: str) -> OfferRoute:  # noqa: ANN001
        # v4 since 2026-08-30, when the Open route stopped sending a mime type (see
        # _OPEN_WITH_MIME_TYPE); v3 was the same day, when the staged path stopped being
        # baked in and became %par1.  THE VERSION IN THE NAME IS LOAD-BEARING, and this is
        # what it is for: what the Task opens and what it opens it AS are both part of its
        # body, and _install_task_on_android installs only what is not already there -- so a
        # device holding 'MapTasker Open Profile v3' would go on asking for text/xml forever,
        # silently, since that Task runs fine and writes its answer file either way.  A new
        # name is a new Task.
        task_name = f"MapTasker {verb} {label} v4"
        write_path = f"{_BOOKKEEPING_LOCATION}/maptasker_{verb.lower()}_{key}.txt"
        header = f"MAPTASKER-{verb.upper()}-{label.upper()} 1"
        return OfferRoute(
            label=label,
            confirm_endpoint=confirm_endpoint,
            task_name=task_name,
            # No path handed to the builder: it builds with %par1 and is told the real one
            # when it is run.
            builder=lambda: builder(task_name, _STAGE_PATH_PARAMETER, write_path, header),
            stage_location=stage_location,
            extension=extension,
            read_path=f"/{write_path}",
            header=header,
            failure_hint=hint,
        )

    return (
        route("Open", build_open_file_task, "Tasker could not open {path} for import."),
        route(
            "Send",
            build_send_intent_task,
            "Tasker refused an ACTION_VIEW for file://{path}.  A file:// URI in an outgoing "
            "intent is rejected on Android 7 and later; try the Open File route instead.",
        ),
    )


OPEN_FILE_ROUTE, SEND_INTENT_ROUTE = _build_offer_routes(
    "Profile",
    "prf.xml",
    PROFILES_ENDPOINT,
    stage_location=_PROFILE_STAGE_LOCATION,
)
# A Project has no endpoint of its own, so it is confirmed through the Profiles it brings --
# see open_project_on_device.
OPEN_PROJECT_ROUTE, SEND_INTENT_PROJECT_ROUTE = _build_offer_routes(
    "Project",
    "prj.xml",
    PROFILES_ENDPOINT,
    stage_location=_PROJECT_STAGE_LOCATION,
)
# A Scene HAS routes now, and it did not before.  Every way of handing Tasker a '.scn.xml'
# had been tried and measured failing (see the section comment below), so a Scene was merely
# uploaded and Tasker opened, with the import left entirely to the user.  What had not been
# tried is an implicit ACTION_VIEW carrying NO mime type -- the "Open with..." a file manager
# fires -- and that is a different attempt from either of the measured ones: the implicit try
# asked for 'text/xml' and got a chooser of text/xml apps, and the explicit try bypassed
# matching altogether.  See _OPEN_WITH_MIME_TYPE.
#
# It is offered on that reasoning, not on a measurement, and it costs nothing if it is wrong:
# the file is already in /Tasker/scenes under the Scene's own name, and the message still
# tells the user how to import it by hand.  That instruction is what this route used to be.
OPEN_SCENE_ROUTE, SEND_INTENT_SCENE_ROUTE = _build_offer_routes(
    "Scene",
    "scn.xml",
    SCENES_ENDPOINT,
    stage_location=_SCENE_LOCATION,
)
# And a Task, which reaches Tasker headlessly through api/import and needs none of this --
# taskedit.save_task_to_android is the route that works.  This is what is left when that has
# been tried twice and Tasker still does not report the Task: the file is in /Tasker/tasks,
# and the user can be handed the same chooser rather than told it did not work.  See
# userintr's Task import.
OPEN_TASK_ROUTE, SEND_INTENT_TASK_ROUTE = _build_offer_routes(
    "Task",
    "tsk.xml",
    TASKS_ENDPOINT,
    stage_location=_TASK_STAGE_LOCATION,
)
# Every route there is, in one place, so anything that has to reason about all of them cannot
# be left behind by a new kind being added -- current_helper_task_names above all, where
# missing one would mean reporting a Task that is in use as dead and inviting the user to
# delete it.
ALL_OFFER_ROUTES = (
    OPEN_FILE_ROUTE,
    SEND_INTENT_ROUTE,
    OPEN_PROJECT_ROUTE,
    SEND_INTENT_PROJECT_ROUTE,
    OPEN_SCENE_ROUTE,
    SEND_INTENT_SCENE_ROUTE,
    OPEN_TASK_ROUTE,
    SEND_INTENT_TASK_ROUTE,
)


# --- Bringing Tasker up, with nothing handed to it ---------------------------------------
#
# MEASURED, 2026-08-28: with a Scene staged in /Tasker/scenes and an explicit ACTION_VIEW at
# Tasker's own activity, Tasker comes up, makes a visible attempt at an import, and imports
# nothing.  The same file, picked by hand through Tasker's 'Scenes > Import One Scene',
# imports correctly -- so the XML is right and it is the HANDOFF that Tasker will not
# complete.  For a while that was read as ending the intent story for Scenes, and this was
# what a Scene got instead: Tasker merely opened, the import left entirely to the user.
#
# It is no longer what the GUI does.  What those measurements did NOT try is an implicit VIEW
# carrying no mime type at all -- Android's "Open with..." -- and a Scene goes through that
# now like every other kind (see OPEN_SCENE_ROUTE and _OPEN_WITH_MIME_TYPE).  This is kept
# because it still works and still might be wanted: it is the one thing that can be done for
# a device where nothing can be handed over at all, and deleting a tested capability on the
# strength of a reasoned improvement would be the wrong way round.
#
# ACTION_MAIN rather than ACTION_VIEW: there is no file to hand over any more, and a VIEW
# with no data is not a launch.  MAIN at an explicit component is what launching an app IS.
_MAIN_ACTION = "android.intent.action.MAIN"
LAUNCH_TASKER_TASK_NAME = "MapTasker Open Tasker v1"
_LAUNCH_WRITE_PATH = "Tasker/maptasker_launch_tasker.txt"
_LAUNCH_READ_PATH = f"/{_LAUNCH_WRITE_PATH}"
_LAUNCH_HEADER = "MAPTASKER-LAUNCH-TASKER 1"


def build_launch_tasker_task(task_name: str = LAUNCH_TASKER_TASK_NAME):  # noqa: ANN201
    """Build the Task that brings Tasker to the foreground.  Returns an EditableTask, or an
    error message string, like every other builder here.

    'Send Intent' again, so this needs no application inventory -- 'Launch App' takes an
    App-category argument, and taskedit.classify_action_addability refuses those while the
    inventory is empty, which it is on a machine that has never fetched one.
    """
    built = _new_offer_task(task_name)
    if isinstance(built, str):
        return built
    edited_task, add, values = built

    error = add(
        _SEND_INTENT_ACTION,
        {
            "0": _MAIN_ACTION,
            "1": _INTENT_CATEGORY_NONE,
            "7": _TASKER_PACKAGE,
            "8": _TASKER_MAIN_ACTIVITY,
            "9": _INTENT_TARGET_ACTIVITY,
        },
    ) or _add_result_writes(add, _LAUNCH_WRITE_PATH, _LAUNCH_HEADER, f"/{_SCENE_LOCATION}")
    if error:
        return error
    return _finish_offer_task(edited_task, task_name, values)


def open_tasker_on_device(ip_address: str, ip_port: str) -> tuple[int, str]:
    """Bring Tasker to the foreground on the device.  (0, "") or (return_code, message).

    NOT CALLED BY THE GUI any more -- see the section comment above.  Every import kind now
    gets Android's "Open with..." chooser instead, which puts Tasker's import screen one tap
    away rather than dropping the user into Tasker with nothing selected.  Kept for a device
    that will not take a handoff at all.

    The same exchange every helper Task goes through -- key, install if absent, clear the
    last answer, run, wait for the answer file -- with nothing handed over and nothing to
    confirm afterwards.  Whether Tasker is in front of the user is not a thing the HTTP API
    can be asked; the answer file says only that the Task ran and the intent went out.

    Blocking, like everything else here: a caller on the GUI thread must use run.io_bound.
    """
    from maptasker.src.maputil2 import http_delete_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    return_code, message = _install_task_on_android(
        ip_address,
        ip_port,
        auth_key,
        LAUNCH_TASKER_TASK_NAME,
        build_launch_tasker_task,
    )
    if return_code != 0:
        return return_code, message
    auth_key = _auth_keys.get(_device_key(ip_address, ip_port), auth_key)

    delete_code, delete_error = http_delete_request(ip_address, ip_port, _LAUNCH_READ_PATH, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {_LAUNCH_READ_PATH} before opening Tasker: {delete_error}")

    return_code, message, auth_key = _run_task_refreshing_key(ip_address, ip_port, LAUNCH_TASKER_TASK_NAME, auth_key)
    if return_code != 0:
        return return_code, message

    text, error = _poll_for_result(ip_address, ip_port, _LAUNCH_READ_PATH, _OPEN_POLL_ATTEMPTS, "launch result")
    if error:
        return 8, error
    if not text.splitlines() or text.splitlines()[0].strip() != _LAUNCH_HEADER:
        return 8, "The file the Android device wrote is not a MapTasker launch result."
    return 0, ""


def verify_names_on_android(
    ip_address: str,
    ip_port: str,
    endpoint: str,
    names: list[str],
    auth_key: str,
) -> set[str] | None:
    """Which of these names Tasker reports at this endpoint, via GET <endpoint>?name=...&name=...
    None if the device could not be asked.

    Serves api/profiles and api/scenes alike: both answer a JSON array of objects with a
    "name", and both document 'name' as repeatable -- so this is one request however many
    names it is given, which matters for a Project, where the list is every Profile the
    Project owns and the answer is wanted repeatedly while someone finds their phone.

    None is not an empty set.  'Could not ask' and 'none of them are there' lead to opposite
    conclusions everywhere this is used.
    """
    from urllib.parse import quote  # noqa: PLC0415

    from maptasker.src.maputil2 import http_request  # noqa: PLC0415

    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        return set()

    query = "?" + "&".join(f"name={quote(name)}" for name in names)
    return_code, response = http_request(ip_address.strip(), ip_port.strip(), "", endpoint, query, auth_key)
    if return_code != 0:
        return None

    try:
        reported = json.loads(response)
    except (ValueError, TypeError):
        return None
    if not isinstance(reported, list):
        return None

    found = {entry.get("name") for entry in reported if isinstance(entry, dict)}
    return {name for name in names if name in found}


def verify_profiles_on_android(
    ip_address: str,
    ip_port: str,
    profile_names: list[str],
    auth_key: str,
) -> set[str] | None:
    """Which of these Profile names Tasker reports.  The api/profiles form of
    verify_names_on_android, kept because most callers only ever ask about Profiles.
    """
    return verify_names_on_android(ip_address, ip_port, PROFILES_ENDPOINT, profile_names, auth_key)


def verify_profile_on_android(ip_address: str, ip_port: str, profile_name: str, auth_key: str) -> bool:
    """Whether Tasker reports a Profile of this name.

    The single-name form of verify_profiles_on_android, and the Profile counterpart of
    taskedit.verify_task_on_android.  It earns its keep for the same reason: a request's own
    200 is not evidence that anything was committed.

    Returns True only on a successful GET that lists the Profile; a request that failed is
    False, i.e. 'not confirmed', never 'confirmed absent'.  Callers that need to tell those
    two apart must use the plural form, which answers None for the second.
    """
    present = verify_profiles_on_android(ip_address, ip_port, [profile_name], auth_key)
    return bool(present) and profile_name in present


def import_is_confirmable(
    ip_address: str,
    ip_port: str,
    names: list[str],
    endpoint: str = PROFILES_ENDPOINT,
) -> bool | None:
    """Whether an import of these Profiles could be told apart from doing nothing.
    True, False, or None if the device could not be asked.

    This is not a gate.  An import is confirmed by asking Tasker what it now has, and that
    question only means something when the answer was 'no' beforehand: a Profile that was
    already there answers 'yes' whether the user tapped Import, tapped Replace, or walked
    away -- Tasker replaces in that case, and a replacement leaves the name, the count and
    the enabled state exactly as they were.  So a caller has to know which case it is in
    before it offers, and report the two differently rather than claim a success it cannot
    see (see userintr.import_profile_into_tasker_event).

    An empty list is False, not True: a Project that owns no Profiles gives nothing to ask
    about, and 'no questions asked' must not read as 'confirmed'.

    None is kept apart from False for the same reason it is in verify_profiles_on_android --
    though every caller so far treats them alike, since neither can be confirmed and
    guessing the other way is what turns an unconfirmable import into a reported success.
    """
    names = [name.strip() for name in names if name and name.strip()]
    if not names:
        return False

    return_code, auth_key = _ensure_auth_key(ip_address.strip(), ip_port.strip())
    if return_code != 0:
        return None

    present = verify_names_on_android(ip_address, ip_port, endpoint, names, auth_key)
    if present is None:
        return None
    return not present


def await_import(
    ip_address: str,
    ip_port: str,
    names: list[str],
    subject: str,
    endpoint: str = PROFILES_ENDPOINT,
    auth_key: str = "",
    attempts: int = _CONFIRM_POLL_ATTEMPTS,
    staged_at: str = "",
) -> tuple[int, str]:
    """Wait for every one of these Profiles to appear in Tasker, and say whether they did.

    staged_at is where the file is sitting on the device, added to the giving-up message so
    the user can finish the import by hand out of Tasker's own browser.  Worth saying only
    because the file carries the object's own name now -- see _build_offer_routes.

    Phase two of the offer: the import screen is up on the device and this is waiting for
    someone to tap Import.  Returns (0, a sentence) once Tasker reports them all, or (8, a
    message) when the attempts run out.

    ALL of them, not any: a Project import that brought in half its Profiles is not a
    Project import that worked, and reporting the first arrival as success would race the
    device's own writing.  For a Profile import the list is one name and the distinction
    does not arise.

    Running out is NOT an error in the usual sense -- the likeliest cause is that the user
    declined the import, or has not got to their phone yet -- so the message says that
    rather than blaming the device.

    Blocking: it sleeps between polls, the same way _poll_for_result does, and a caller on
    the GUI thread must hand it to run.io_bound.
    """
    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    wanted = {name.strip() for name in names if name and name.strip()}

    if not auth_key:
        return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
        if return_code != 0:
            return return_code, auth_key

    for attempt in range(attempts):
        present = verify_names_on_android(ip_address, ip_port, endpoint, sorted(wanted), auth_key)
        if present is not None and wanted <= present:
            return 0, f"{subject} is now in Tasker on {_device_key(ip_address, ip_port)}."
        if attempt < attempts - 1:
            time.sleep(_RESULT_POLL_SECONDS)

    waiting = f"  The file is on the device at {staged_at} and can still be imported by hand." if staged_at else ""
    return 8, (
        f"Tasker has not reported {subject}.  The import screen was opened on the device -- it may still "
        f"be waiting to be confirmed, or the import may have been declined.{waiting}"
    )


def _stage_xml(
    ip_address: str,
    ip_port: str,
    xml_bytes: bytes,
    object_name: str,
    route: OfferRoute,
) -> tuple[int, str]:
    """Put the rendered XML where this route's helper Task can reach it, under the object's
    own name.  Returns (0, its absolute path on the device) or (code, message).

    That path is what the caller hands the helper Task as %par1, so it comes back rather than
    being a constant on the route -- see OfferRoute and run_task_on_android.

    NOTHING IS READ FIRST, and that is not an oversight about clobbering.  The staged file is
    the user's own now -- this writes exactly where the 'Save As File' button writes, so an
    import of 'Morning' replaces a 'Morning.prf.xml' they saved by hand -- but the caller has
    already read that path to ask them about it, and it hands the bytes it got to
    presave.save_android_safety_copy itself.  Reading here as well would be a second GET of
    a path just read: another round trip, another chance for the two answers to disagree,
    and another 'File doesn't exist' flash on the phone for one save (see
    maputil2.read_android_file).  One read answers both questions, up there.

    Read back and compared byte for byte, because /upload answers 200 whatever it wrote (see
    maputil2.http_upload_request): it does not validate the location, it creates missing
    folders silently, and it reports nothing at the HTTP layer.  A half-written file would
    not fail loudly here -- it would be handed to Tasker.  save_profile_to_android reads its
    own upload back for exactly this reason.
    """
    from maptasker.src.maputil2 import http_upload_request, read_back_uploaded_file  # noqa: PLC0415

    filename, read_path, task_path = route.staged_file_paths(object_name)

    return_code, response = http_upload_request(ip_address, ip_port, route.stage_location, filename, xml_bytes)
    if return_code != 0:
        return return_code, str(response)

    # Retried rather than trusted -- see maputil2.read_back_uploaded_file for the write that
    # is still settling when this arrives.
    verify_code, verify_content = read_back_uploaded_file(ip_address, ip_port, read_path, xml_bytes)
    if verify_code != 0:
        return 8, str(verify_content)
    return 0, task_path


def offer_to_tasker(  # noqa: PLR0911
    xml_bytes: bytes,
    object_name: str,
    confirm_names: list[str],
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    route: OfferRoute = OPEN_FILE_ROUTE,
) -> tuple[int, str]:
    """Offer a Profile, a Project or a Scene to Tasker's own import screen on the device.

    Args:
        xml_bytes: the standalone XML -- profedit.render_standalone_profile_xml or
            projedit.render_standalone_project_xml, encoded UTF-8, i.e. exactly what the
            file-writing Save To Android uploads today.
        object_name: what it is called, for the messages.
        confirm_names: the names an import of this would put in Tasker, asked about at the
            route's own confirm_endpoint -- its own name for a Profile or a Scene, and for a
            Project every Profile it owns, since there is no /api/projects to ask about the
            Project itself.  See the section comment.
        wait_for_confirmation: keep asking Tasker whether they turned up, for about two
            minutes (await_import).  False returns as soon as the screen has been asked for,
            which is what a GUI wanting to poll on its own should pass -- the return message
            then says the import is still pending, and must not be shown as a completed
            save.  True skips the wait when it could not mean anything and says so instead:
            see import_is_confirmable.
        route: which kind, and how the screen is asked for.  OPEN_FILE_ROUTE and
            OPEN_PROJECT_ROUTE let Android find the handler; the SEND_INTENT_* pair address
            Tasker explicitly.  Prefer the first -- see the section comment for the file://
            URI only the second can trip over.

    Unlike import_profile_to_device this has no acknowledged_risk gate, and no duplicate
    check either.  It puts nothing at stake but the one Profile or Project: Android is
    handed a file, Tasker shows the user what it is about to import -- including, measured
    on a real device, an offer to replace something it already has -- and the semantics from
    there are Tasker's own documented ones.  Refusing a name Tasker already knows would only
    put a worse prompt in front of a better one.

    The exchange: get an API key, install the helper Task if it isn't there, clear the last
    answer, stage the XML, run the Task, confirm it ran, and then -- if asked, and if the
    answer would mean anything -- wait for the import to appear.  Returns (0, a sentence
    saying what happened and what the user still has to do) or (return_code, an error
    message).

    Requires the Tasker HTTP Server Example project running on the device and Tasker 6.2 or
    higher.  Blocking, deliberately; a caller on the GUI thread must use run.io_bound.
    """
    from maptasker.src.maputil2 import http_delete_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    object_name = object_name.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'."
    if not object_name:
        return 8, f"A {route.label} name is needed."
    if not xml_bytes:
        return 8, f"There is no {route.label} XML to import."

    subject = f"{route.label} '{object_name}'"
    key = _device_key(ip_address, ip_port)
    return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key

    # Asked BEFORE the import, because afterwards the answer is worthless -- see
    # import_is_confirmable.  Nothing is gated on it; it only decides what can be said at
    # the end.
    wanted = [name.strip() for name in confirm_names if name and name.strip()]
    present_before = verify_names_on_android(ip_address, ip_port, route.confirm_endpoint, wanted, auth_key)
    confirmable = bool(wanted) and present_before == set()

    return_code, message = _install_task_on_android(ip_address, ip_port, auth_key, route.task_name, route.builder)
    if return_code != 0:
        return return_code, message
    auth_key = _auth_keys.get(key, auth_key)

    delete_code, delete_error = http_delete_request(ip_address, ip_port, route.read_path, auth_key)
    if delete_code != 0:
        logger.info(f"Could not clear {route.read_path} before offering: {delete_error}")

    return_code, message = _stage_xml(ip_address, ip_port, xml_bytes, object_name, route)
    if return_code != 0:
        return return_code, message
    stage_task_path = message
    # Where the file actually is, said in every message from here on.  A handoff that fails
    # leaves the user to import it themselves out of Tasker's own browser, and that is only
    # possible if they are told which file -- the whole reason it carries the object's name.
    landed = f"  It is on the device at {stage_task_path}."

    # The path goes over WITH the run, as %par1, rather than having been baked into the Task
    # when it was installed -- see run_task_on_android.
    return_code, message, auth_key = _run_task_refreshing_key(
        ip_address,
        ip_port,
        route.task_name,
        auth_key,
        stage_task_path,
    )
    if return_code != 0:
        return return_code, message

    text, error = _poll_for_result(ip_address, ip_port, route.read_path, _OPEN_POLL_ATTEMPTS, "import result")
    if error:
        return 8, f"{error}  {route.failure_hint.format(path=stage_task_path)}"
    if not text.splitlines() or text.splitlines()[0].strip() != route.header:
        return 8, "The file the Android device wrote is not a MapTasker import result."

    if not wait_for_confirmation:
        return 0, (
            f"{subject} was sent to {key} and Tasker's import screen was opened.  "
            f"It is not imported until it is confirmed on the device.{landed}"
        )

    # Waiting for something that is already there would 'confirm' the import the instant it
    # was asked, whatever the user goes on to tap -- including Cancel.  So it is not asked.
    if not confirmable:
        return 0, (
            f"{subject} was sent to {key} and Tasker's import screen was opened.  Tasker already has what "
            "this would import and will offer to replace it; whether that was confirmed cannot be seen "
            f"from here.{landed}"
        )

    return await_import(
        ip_address,
        ip_port,
        wanted,
        subject,
        route.confirm_endpoint,
        auth_key,
        _CONFIRM_POLL_ATTEMPTS,
        stage_task_path,
    )


def open_profile_on_device(
    profile_xml: bytes,
    profile_name: str,
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    route: OfferRoute = OPEN_FILE_ROUTE,
) -> tuple[int, str]:
    """Offer one Profile to Tasker's import screen.  See offer_to_tasker, which does the work.

    A Profile confirms by its own name -- the list of one that offer_to_tasker's general
    case collapses to.
    """
    return offer_to_tasker(
        profile_xml,
        profile_name,
        [profile_name.strip()],
        ip_address,
        ip_port,
        wait_for_confirmation,
        route,
    )


def open_project_on_device(
    project_xml: bytes,
    project_name: str,
    profile_names: list[str],
    ip_address: str,
    ip_port: str,
    wait_for_confirmation: bool = True,
    route: OfferRoute = OPEN_PROJECT_ROUTE,
) -> tuple[int, str]:
    """Offer one Project -- and every Profile and Task it owns -- to Tasker's import screen.

    profile_names is the Project's own Profiles, which the caller reads off the live tree
    (projedit.project_profile_names).  They are what the import is confirmed by, because
    there is no /api/projects to ask about the Project itself; see the section comment.
    """
    return offer_to_tasker(
        project_xml,
        project_name,
        profile_names,
        ip_address,
        ip_port,
        wait_for_confirmation,
        route,
    )


# ==========================================
# The helper Tasks this program leaves on the device
# ==========================================
#
# Every helper is installed by name and never replaced: Tasker's api/import ADDS a Task whose
# name is taken rather than replacing it, so _install_task_on_android installs only what is
# not already there.  That is what makes the version suffixes load-bearing -- a changed body
# needs a changed name or the old Task goes on running -- and it is also what leaves the
# previous one behind forever.  A device that has been through several MapTasker releases
# accumulates 'MapTasker Open Profile v1', 'v2', 'v3' beside the one in use.
#
# NOTHING HERE DELETES THEM, because nothing can.  The Tasker HTTP Server Example has no
# route for it: its Task endpoints are GET /api/tasks (list) and POST /api/tasks (run), and
# its only DELETE is /api/file/*, which removes a file from storage -- a helper Task is in
# Tasker's configuration, not a file.  No Tasker action deletes a Tasker object either.  So
# the honest thing this CAN do is say exactly which ones are dead, by name, so the user can
# delete them in Tasker in one pass instead of guessing.

# What every one of this program's helper Tasks is called at the front, and the only thing
# separating them from the user's own Tasks in a list of several hundred.
HELPER_TASK_PREFIX = "MapTasker "


def current_helper_task_names() -> set[str]:
    """Every helper Task name THIS build installs -- the ones that must not be deleted.

    Derived from the routes and the standalone helpers rather than written out, because a
    hand-kept list is exactly the thing that goes stale: a version bump that updated the
    constant and not the list would report the Task now in use as dead, and the user would
    delete the working one.
    """
    names = {route.task_name for route in ALL_OFFER_ROUTES}
    return names | {
        IMPORT_PROFILE_TASK_NAME,
        FILE_LIST_TASK_NAME,
        LAUNCH_TASKER_TASK_NAME,
        HELPER_TASK_NAME,
    }


def classify_helper_tasks(task_names: Iterable[str]) -> tuple[list[str], list[str]]:
    """Split every name on the device into (this program's current helpers, its leftovers).

    Anything not starting with HELPER_TASK_PREFIX is the user's own and is not this
    program's business to have an opinion about, so it appears in neither list.

    The prototype's experiment variants ('MapTasker Import Profile v3 [Task/0]' -- see
    _import_task_name) count as current when they carry the current version, since they are
    that build's Task with one setting changed rather than an older build's.  Sorted, because
    this is read by a person working down a list in Tasker.
    """
    current = current_helper_task_names()
    ours = {name.strip() for name in task_names if name and name.strip().startswith(HELPER_TASK_PREFIX)}
    live = {name for name in ours if name in current or any(name.startswith(f"{one} [") for one in current)}
    return sorted(live), sorted(ours - live)


def fetch_task_names_from_device(ip_address: str, ip_port: str) -> tuple[int, str, list[str]]:
    """Every Task Tasker knows about, by name.  (0, "", names) or (return_code, message, []).

    GET /api/tasks with NO name filter, which is the whole list: the server example's handler
    matches 'name=' out of the request path and, when there is none, sets its working list to
    every Task Tasker reports (act7/act9 of the 'GET Tasks' Task -- read off the sample
    backup, the same way everything else about that server was).  The response is the same
    JSON array of {"name":..., "running":...} that verify_names_on_android reads a filtered
    version of.

    Blocking, like every other call here; a caller on the GUI thread must use run.io_bound.
    """
    from maptasker.src.maputil2 import http_request  # noqa: PLC0415

    ip_address = ip_address.strip()
    ip_port = ip_port.strip()
    if not ip_address or not ip_port:
        return 8, "An Android IP address and port are needed.  Set them under 'Get XML from Android Device'.", []

    return_code, auth_key = _ensure_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, auth_key, []

    return_code, response = http_request(ip_address, ip_port, "", TASKS_ENDPOINT, "", auth_key)
    if return_code != 0:
        return return_code, str(response), []

    try:
        reported = json.loads(response)
    except (ValueError, TypeError):
        return 8, "The device's Task list was not readable as JSON.", []
    if not isinstance(reported, list):
        return 8, "The device's Task list was not the list of Tasks it should be.", []

    return 0, "", [entry.get("name", "") for entry in reported if isinstance(entry, dict)]


def stale_helper_tasks_on_device(ip_address: str, ip_port: str) -> tuple[int, str, list[str], list[str]]:
    """(0, "", stale, current) for one device, or (return_code, message, [], []).

    The two lists together are the whole answer a user needs: which of this program's Tasks
    to delete in Tasker, and which to leave alone.  Reported rather than acted on -- see the
    section comment for why deleting them from here is not possible.
    """
    return_code, message, names = fetch_task_names_from_device(ip_address, ip_port)
    if return_code != 0:
        return return_code, message, [], []
    current, stale = classify_helper_tasks(names)
    return 0, "", stale, current


# ==========================================
# The cache
# ==========================================


def cache_path() -> str:
    """Where the fetched lists are kept -- beside MapTasker_Settings.toml, in the current
    directory, which is where getputer.save_restore_args writes that one too.
    """
    return os.path.join(os.getcwd(), APPS_CACHE_FILE)


def read_cache() -> dict:
    """The cache file, or an empty one.

    A missing or damaged file is not an error and is not reported: it means 'nothing has
    been fetched', which is a state the program is built to work in anyway.  Same reasoning
    getputer.py applies to a damaged settings pickle -- carry on with the defaults rather
    than refuse to run.
    """
    try:
        with open(cache_path(), encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
    except (OSError, ValueError) as error:
        logger.debug(f"No usable {APPS_CACHE_FILE}: {error}")
        return {}
    return cache if isinstance(cache, dict) else {}


def _write_cache(cache: dict) -> str:
    """Save the cache.  Returns "" or a message saying why it could not be saved -- the
    caller reports that as a footnote to a successful fetch rather than as a failure: the
    apps are in the inventory either way, they just will not be there next time.
    """
    try:
        with open(cache_path(), "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, indent=2)
    except OSError as error:
        logger.error(f"Could not write {cache_path()}: {error}")
        return str(error)
    return ""


def fetched_devices() -> list[tuple[str, str, int]]:
    """(device, when it was fetched, how many apps) for each device in the cache.

    Shown beside the fetch button.  A list fetched six months ago, quietly missing an app
    installed since, is the one failure mode a user has no way of diagnosing on their own,
    so the date is on screen rather than in the file.
    """
    return [
        (key, str(record.get("fetched", "")), len(record.get("apps", [])))
        for key, record in sorted(read_cache().get("devices", {}).items())
    ]


def _store_fetched_apps(device: str, entries: list[AppEntry]) -> str:
    """Record one device's fetched Applications, replacing whatever it reported last time.

    Replaced rather than merged, for that device: a merge would keep an app the user has
    since uninstalled in the list forever, and the device has just been asked what is
    actually installed.  Other devices' records are left alone.

    The in-memory inventory is updated whether or not the file could be written, so a
    read-only directory costs the user next session's head start and nothing more.
    """
    cache = read_cache()
    devices = cache.setdefault("devices", {})
    if not isinstance(devices, dict):
        devices = {}
        cache["devices"] = devices
    devices[device] = {
        "fetched": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # noqa: DTZ005
        "apps": [{"pkg": entry.pkg, "label": entry.label, "cls": entry.cls} for entry in entries],
    }
    error = _write_cache(cache)
    _adopt_cache(cache)
    return error


def _adopt_cache(cache: dict) -> None:
    """Rebuild the fetched half of the inventory from a cache dict, and mark it changed."""
    global _device_apps, _cache_loaded, _cache_stamp  # noqa: PLW0603

    known: dict[str, AppEntry] = {}
    devices = cache.get("devices", {})
    if isinstance(devices, dict):
        for record in devices.values():
            for app in record.get("apps", []) if isinstance(record, dict) else []:
                package = str(app.get("pkg", "")).strip() if isinstance(app, dict) else ""
                if package:
                    _merge_app(
                        known,
                        AppEntry(pkg=package, label=str(app.get("label", "")), cls=str(app.get("cls", ""))),
                    )

    _device_apps = _sorted_apps(known.values())
    _cache_loaded = True
    _cache_stamp += 1


def _ensure_cache_loaded() -> None:
    if not _cache_loaded:
        _adopt_cache(read_cache())
