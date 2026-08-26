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


# Auth keys already obtained this session, by device.  The same idea as userintr's own
# self.android_auth_key -- every request to the api/* endpoints needs one, and fetching a
# fresh one prompts on the device -- kept here rather than reached for on the GUI because
# the pickers that trigger a fetch are module-level functions with no MyGui to hand.
_auth_keys: dict[str, str] = {}


def run_task_on_android(ip_address: str, ip_port: str, task_name: str, auth_key: str) -> tuple[int, str]:
    """Run an existing Task on the device, via the Tasker HTTP API's POST /api/tasks
    (Params/Body: task object; Response: the Task's return value).

    Returns (0, "") or (return_code, error_message).  Return code 9 is passed through
    unchanged so the caller can tell a rejected key apart from everything else and retry
    with a fresh one, exactly as taskedit.save_task_to_android does.
    """
    from maptasker.src.maputil2 import http_post_request  # noqa: PLC0415

    return_code, response = http_post_request(
        ip_address,
        ip_port,
        "",
        "api/tasks",
        "",
        json.dumps({"name": task_name}).encode("utf-8"),
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

    return_code, result, used_key = taskedit.save_task_to_android(
        built,
        ip_address,
        ip_port,
        task_name,
        auth_key,
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
) -> tuple[int, str, str]:
    """Run task_name, and if the device rejects the key it was given, get a fresh one and
    try once more.

    Returns (return_code, message, key_used) -- the key so the caller can carry the
    refreshed one forward.  Return code 9 is 'key rejected', the same signal
    taskedit.save_task_to_android retries on.
    """
    from maptasker.src.maputil2 import get_android_auth_key  # noqa: PLC0415

    return_code, message = run_task_on_android(ip_address, ip_port, task_name, auth_key)
    if return_code != 9:
        return return_code, message, auth_key

    return_code, refreshed = get_android_auth_key(ip_address, ip_port)
    if return_code != 0:
        return return_code, refreshed, auth_key
    _auth_keys[_device_key(ip_address, ip_port)] = refreshed

    return_code, message = run_task_on_android(ip_address, ip_port, task_name, refreshed)
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
