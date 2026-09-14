"""appinv: the Applications and icons an edit is allowed to choose from.

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
    module exists to unblock (see deviceinv.fetch_apps_from_device, which hands what the
    device returned to _store_fetched_apps here).  The result is cached per device in
    MapTasker_Apps.json, and nothing is ever fetched unless the user asks.

Without a fetch, the inventory is what you already automate, not everything installed.  An
app referenced nowhere in the backup and never fetched will not be in the list -- so the
pickers built on this never *replace* typing a value, they only save you from having to
(see guiwins_taskedit's _render_app_arg_field, and _build_icon_field, which took the same
stance for Scenes first).

A fetch asks the device for Applications, and that is an icon fetch as well: Tasker names
an app's own icon by its package and its launcher activity, which is exactly what comes
back, so every fetched Application also stands as an 'app' icon (see
_merged_with_device_icons).  The other two icon kinds cannot be fetched at all -- Tasker's
built-in names live inside its own APK and 'List Apps' does not report them, and an icon
pack's contents are not enumerable remotely, the pack itself being detectable only as an
installed app -- so those two stay harvested-or-typed.  See app_icon_fetch_design.md's
"icon gap".

This was deviceinv's whole purpose until the work on the device grew up around it; that work
now has deviceinv to itself.  Deliberately dependency-light: PrimeItems, sysconst,
editcommon's set_child_text and the standard library, nothing else.  taskedit, profedit and
sceneedit import this, so anything this imported from them would be a cycle.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    import defusedxml.ElementTree

from maptasker.src.editcommon import set_child_text as _set_child_text
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
        return (
            f"{_ICON_APP_PREFIX}{icon.pkg}{_ICON_APP_SEPARATOR}{icon.cls}"
            if icon.cls
            else (f"{_ICON_APP_PREFIX}{icon.pkg}")
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

    return _sorted_apps(known_apps.values()), _sorted_icons(known_icons.values())


def _sorted_icons(icons: Iterable[IconRef]) -> list[IconRef]:
    """Icons in the order a picker should open on.

    Built-ins first, then packs, then app icons, then variables: the order they are likely
    to be wanted in, and it keeps the ~250 built-in names of a real backup from being
    interleaved with app icons -- which matters more since a fetch can add one per
    installed application, hundreds of them, all of the one kind.
    """
    kind_order = {"builtin": 0, "pack": 1, "app": 2, "var": 3}
    return sorted(icons, key=lambda icon: (kind_order.get(icon.kind, 9), icon.display.lower()))


def _ensure_harvested() -> None:
    global _harvested_from, _built_at_cache_stamp, _apps, _apps_by_package, _icons, _generation  # noqa: PLW0603

    _ensure_cache_loaded()
    root = getattr(PrimeItems, "xml_root", None)
    if root is _harvested_from and _cache_stamp == _built_at_cache_stamp:
        return

    _apps, _icons = _harvest(root)
    _apps = _merged_with_device_apps(_apps)
    _icons = _merged_with_device_icons(_icons)
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


def _merged_with_device_icons(harvested: list[IconRef]) -> list[IconRef]:
    """Fold the fetched Applications' own icons in with the harvested icons.

    An 'app' icon is a package plus a launcher activity and nothing else, so the fetched
    Application list is already a list of icons -- which is what makes 'get the icons from
    the device' answerable at all, and it is the same fetch, the same helper Task and the
    same cache as the Application list (see the module docstring's note on the icon gap for
    the two kinds this cannot reach).

    A package the harvest already has an 'app' icon for is left as the harvest had it: that
    one came out of a file Tasker itself wrote, so its <cls> is right, where a fetched
    launcher activity is whatever 'List Apps' reported.  Same precedence, same reason, as
    _merged_with_device_apps.
    """
    if not _device_apps:
        return harvested

    known = {(icon.kind, icon.name, icon.pkg, icon.cls): icon for icon in harvested}
    harvested_packages = {icon.pkg for icon in harvested if icon.kind == "app"}
    for entry in _device_apps:
        if not entry.pkg or entry.pkg in harvested_packages:
            continue
        icon = IconRef(kind="app", pkg=entry.pkg, cls=entry.cls)
        known.setdefault((icon.kind, icon.name, icon.pkg, icon.cls), icon)
    return _sorted_icons(known.values())


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
    getputer.py applies to a damaged settings file -- carry on with the defaults rather
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
