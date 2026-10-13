"""readiness: what a configuration needs on somebody else's phone."""

#! /usr/bin/env python3

#                                                                                       #
# readiness: the other half of "Redact secrets".  Redacting answers "what must not leave #
#            with this file?"; this answers "what must be on the phone it arrives on?" -- #
#            the plugins and apps it uses, the special access it needs (root, ADB Wi-Fi,  #
#            Write Secure Settings, ...), the variables Tasker will ask the importer      #
#            about, and how new a Tasker it needs.                                        #
#                                                                                       #
# It reads the EXPORT, not the loaded backup.  check_project() renders the very          #
# <TaskerData> document "Export Project" would write and reads that, so the answer is     #
# about exactly what the recipient receives: the Project's own Profiles, Tasks and Scenes #
# and the Tasks its Scenes fire, and not the rest of the backup it was taken from.  A     #
# Task the export deliberately does not bundle (see projedit.render_standalone_project_xml #
# on Perform Task) is not counted, which is the right answer -- it is not in the file.    #
#                                                                                       #
# The facts come from three places:                                                      #
#                                                                                       #
#   the file itself  plugins (plugset.plugin_package), apps (appinv), the variables       #
#                    flagged "Configure on Import" (<pvci>), and any "Use Root"-style     #
#                    switch an action has turned on.                                      #
#   readiness.json   what each action, event and state needs, and which Tasker release   #
#                    introduced it.  Data, not code, and built from Tasker's own release  #
#                    notes -- see the _comment in the file.                               #
#   actionc          the names of those actions, and which argument is which.             #
#                                                                                       #
# What this cannot do, said plainly because a "ready" answer gets trusted:               #
#                                                                                       #
#   * It is a floor.  An action readiness.json has no entry for is not known to need     #
#     nothing -- it is just not known.  The table covers the access Tasker cannot ask for #
#     itself; ordinary runtime permissions (location, SMS, contacts) are left to Tasker,  #
#     which lists them when a Project is imported.                                        #
#   * The minimum Tasker version is the newest release among the items the table knows     #
#     the release of.  Something newer that is not in the table does not raise it.       #
#   * A plugin's own requirements -- an account, a subscription, a license -- are the      #
#     plugin's business and are not visible in the file.                                  #
#   * Whether the recipient already HAS any of it is not checked.  This lists the needs;   #
#     plugchk checks plugins against a phone whose app list has been fetched.            #
#                                                                                       #
# Nothing here prints a variable's value, so a default that holds a key cannot be        #
# leaked by the report that is meant to be pasted into a forum post.                     #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING

import defusedxml.ElementTree as DefusedET

from maptasker.src.analysis.plugchk import item_name
from maptasker.src.core import appinv
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.objprops import VARIABLE_TYPES
from maptasker.src.core.plugset import plugin_package
from maptasker.src.edit import projedit, sceneedit

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

READINESS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "json", "readiness.json"),
)

# How many of the places using something a line names before "and N more".
_PLACES_NAMED = 4

# Tasker itself, which is not something the recipient has to install.
_TASKER_PACKAGES = ("net.dinglisch.android.tasker",)

# The top-level elements of a <TaskerData> document that own actions, conditions or variables,
# and the child that holds each one's name (a Project's is <name>, the others' is <nme>).
_OWNERS = {"Project": "name", "Profile": "nme", "Task": "nme", "Scene": "nme"}

# The Profile children that are conditions with a code, and the suffix actionc keys them by.
_CONDITIONS = {"Event": "e", "State": "s"}

_DIGITS = re.compile(r"\d+")


# ##################################################################################
# The data.
# ##################################################################################
@cache
def _table() -> dict:
    """readiness.json, read the first time it is wanted."""
    with open(READINESS_FILE, encoding="utf-8") as file:
        return json.load(file)


def version_key(version: str) -> tuple[int, ...]:
    """A release number as something that sorts: "6.3.12" -> (6, 3, 12), "6.7.6-beta" -> (6, 7, 6)."""
    return tuple(int(part) for part in _DIGITS.findall(version))


def _label(access_id: str) -> str:
    """What the data file calls one kind of access."""
    return _table()["access"][access_id]["label"]


def _how(access_id: str) -> str:
    """What the recipient has to do to have one kind of access."""
    return _table()["access"][access_id]["how"]


# ##################################################################################
# The answer.
# ##################################################################################
@dataclass(frozen=True)
class PluginNeed:
    """One plugin the configuration uses, and what in it uses the plugin."""

    package: str
    used_by: tuple[str, ...]


@dataclass(frozen=True)
class AppNeed:
    """One app the configuration names, by package, with the label the file gives it."""

    package: str
    label: str
    used_by: tuple[str, ...]


@dataclass(frozen=True)
class AccessNeed:
    """One thing the phone has to be able to do.

    'any_of' is the ids of the kinds of access that would each do it -- one entry for a need
    with a single answer, several where Tasker accepts any of them.  'used_by' is what needs
    this outright; 'also_meets' is what accepts it among other things and so is satisfied by it
    without needing it -- see _Tally.needs.
    """

    any_of: tuple[str, ...]
    used_by: tuple[str, ...]
    also_meets: tuple[str, ...] = ()

    @property
    def labels(self) -> tuple[str, ...]:
        """The names of the alternatives, as the data file spells them."""
        return tuple(_label(access_id) for access_id in self.any_of)


@dataclass(frozen=True)
class PromptNeed:
    """One variable Tasker asks the importer to fill in -- never its value, only whether it has one."""

    owner: str
    variable: str
    label: str
    prompt: str
    type_label: str
    has_default: bool


@dataclass(frozen=True)
class VersionNeed:
    """The oldest Tasker the configuration is known to run on, and which items say so."""

    version: str
    because: tuple[str, ...]


@dataclass(frozen=True)
class Line:
    """One entry in a section: what it is, who uses it, and how the recipient deals with it."""

    text: str
    used_by: str = ""
    setup: str = ""


@dataclass(frozen=True)
class Section:
    """One heading of the report and its entries.  'empty' is what to say when there are none."""

    title: str
    lines: tuple[Line, ...]
    empty: str


@dataclass
class Readiness:
    """Everything the check found, in the shape the dialog and the text export both read."""

    scope: str = ""
    written_by: str = ""
    plugins: list[PluginNeed] = field(default_factory=list)
    apps: list[AppNeed] = field(default_factory=list)
    access: list[AccessNeed] = field(default_factory=list)
    prompts: list[PromptNeed] = field(default_factory=list)
    minimum: VersionNeed | None = None

    @property
    def needs_nothing(self) -> bool:
        """Whether the check found no plugin, app, access or prompt -- which is not "needs nothing"."""
        return not (self.plugins or self.apps or self.access or self.prompts)

    def sections(self) -> list[Section]:
        """The report, as headings with entries under them, in the order somebody sets a phone up."""
        return [
            self._version_section(),
            Section(
                "Plugins",
                tuple(Line(need.package, _places(need.used_by)) for need in self.plugins),
                "No plugins are used.",
            ),
            Section(
                "Apps",
                tuple(Line(_app_text(need), _places(need.used_by)) for need in self.apps),
                "No apps are named.",
            ),
            Section("Special access", tuple(_access_line(need) for need in self.access), "No special access found."),
            Section(
                "Variables Tasker will ask about",
                tuple(_prompt_line(need) for need in self.prompts),
                "No variable is set to be configured on import.",
            ),
        ]

    def _version_section(self) -> Section:
        """The Tasker version heading: the minimum, when one is known, and what wrote the file."""
        lines = []
        if self.minimum is not None:
            lines.append(
                Line(f"Tasker {self.minimum.version} or newer", f"Needed for: {', '.join(self.minimum.because)}"),
            )
        if self.written_by:
            lines.append(Line(f"This file was written by Tasker {self.written_by}."))
        return Section(
            "Tasker version", tuple(lines), "No action, event or state here is known to need a recent Tasker."
        )

    def as_text(self) -> str:
        """The report as plain text, for pasting into a forum post or a TaskerNet description."""
        out = [f"What {self.scope} needs on another phone" if self.scope else "What this needs on another phone", ""]
        for section in self.sections():
            out.append(section.title)
            if not section.lines:
                out.append(f"  {section.empty}")
            for line in section.lines:
                out.append(f"  - {line.text}")
                if line.used_by:
                    out.append(f"      {line.used_by}")
                if line.setup:
                    out.append(f"      {line.setup}")
            out.append("")
        out.append(LIMITATIONS)
        return "\n".join(out).rstrip() + "\n"


# What every report ends with, said once.  See the header on why a "ready" answer needs it.
LIMITATIONS = (
    "Built from what is in the file.  An action this list does not know is not known to need nothing, "
    "ordinary permissions such as location or SMS are left to Tasker to ask for on import, and a "
    "plugin's own account or license is not visible here."
)


def _named(places: tuple[str, ...]) -> str:
    """ "a; b; c; and 2 more" -- the first few places, then a count of the rest."""
    left = len(places) - _PLACES_NAMED
    return f"{'; '.join(places[:_PLACES_NAMED])}{f'; and {left} more' if left > 0 else ''}"


def _places(used_by: tuple[str, ...]) -> str:
    """ "Used by: a; b; c; and 2 more" """
    return f"Used by: {_named(used_by)}"


def _access_places(need: AccessNeed) -> str:
    """Who needs this access, and who merely accepts it among others."""
    needed = f"Needed by: {_named(need.used_by)}"
    return f"{needed}.  Also met by it: {_named(need.also_meets)}" if need.also_meets else needed


def _app_text(need: AppNeed) -> str:
    """An app as the recipient would look for it: its label and its package."""
    return f"{need.label} ({need.package})" if need.label and need.label != need.package else need.package


def _access_line(need: AccessNeed) -> Line:
    """One special-access entry: the access, or the choice of them, and how to set each up."""
    if len(need.any_of) == 1:
        return Line(need.labels[0], _access_places(need), _how(need.any_of[0]))
    choice = f"{', '.join(need.labels[:-1])} or {need.labels[-1]} (any one of them)"
    setup = "  ".join(f"{_label(access_id)}: {_how(access_id)}" for access_id in need.any_of)
    return Line(choice, _access_places(need), setup)


def _prompt_line(need: PromptNeed) -> Line:
    """One import-time variable: its name, what it is asked as, and whether it comes filled in."""
    shown = f"{need.variable} ({need.label})" if need.label and need.label != need.variable else need.variable
    asked = f"Asked as: {need.prompt}" if need.prompt else "No prompt text is set"
    default = "comes with a default value" if need.has_default else "has no default"
    return Line(shown, f"{need.owner}.  {need.type_label}; {default}.  {asked}")


# ##################################################################################
# Reading the tree.
# ##################################################################################
class _Tally:
    """What has been found so far, and the ways of adding to it.

    Aggregated as it arrives, for piiscan's reason: forty Kill App actions are one line with
    forty places on it, not forty lines.
    """

    def __init__(self) -> None:
        self.plugins: dict[str, list[str]] = {}
        self.apps: dict[str, tuple[str, list[str]]] = {}
        self.access: dict[frozenset[str], list[str]] = {}
        self.also_met: dict[frozenset[str], list[str]] = {}
        self.access_order: dict[frozenset[str], tuple[str, ...]] = {}
        self.since: dict[str, list[str]] = {}
        self.prompts: list[PromptNeed] = []

    @staticmethod
    def _remember(places: list[str], place: str) -> None:
        """Add a place once, keeping the order places were found in."""
        if place not in places:
            places.append(place)

    def plugin(self, package: str, place: str) -> None:
        """Record a use of a plugin."""
        self._remember(self.plugins.setdefault(package, []), place)

    def app(self, package: str, label: str, place: str) -> None:
        """Record a use of an app, keeping the first label the file gave it."""
        known_label, places = self.apps.setdefault(package, (label, []))
        if label and not known_label:
            self.apps[package] = (label, places)
        self._remember(places, place)

    def need(self, spec: str, place: str) -> None:
        """Record a requirement written as 'a|b|c' (any one of them), as the data file spells it."""
        ids = tuple(spec.split("|"))
        self._remember(self.access.setdefault(frozenset(ids), []), place)
        self.access_order.setdefault(frozenset(ids), ids)

    def release(self, version: str, name: str) -> None:
        """Record an item that came in with a particular Tasker release."""
        self._remember(self.since.setdefault(version, []), name)

    def needs(self) -> list[AccessNeed]:
        """The access found, with a need that a stricter one already covers folded into it.

        Kill App needs root, ADB Wi-Fi, Device Owner or Shizuku -- and if something else in
        the same file needs root outright, the phone has root, so the first is met by it and
        a line of its own would only suggest the recipient has a choice they do not have.  The
        places are kept, on the line that survives, as places it also satisfies rather than
        places that need it -- Custom Setting can use Write Secure Settings, so listing it under
        Root as a user of root would say something it does not.
        """
        found = dict(self.access)
        for narrow in list(found):
            if narrow not in found:
                continue
            for wide in list(found):
                if narrow < wide and wide in found:
                    for place in found.pop(wide):
                        self._remember(self.also_met.setdefault(narrow, []), place)
        return [
            AccessNeed(self.access_order[ids], tuple(places), tuple(self.also_met.get(ids, ())))
            for ids, places in found.items()
        ]


def _name_of(owner: Element) -> str:
    """The name of a top-level Project, Profile, Task or Scene element."""
    return (owner.findtext(_OWNERS[owner.tag]) or "").strip()


def _place(owner: Element) -> str:
    """ "Task 'Morning'" -- where something is, as the Map calls it."""
    return f"{owner.tag} '{_name_of(owner)}'"


def _int_argument(element: Element, argument: str) -> int | None:
    """The integer an <Int sr="argN" val="..."/> holds, or None when it is a variable or not there."""
    for child in element:
        if child.tag == "Int" and child.attrib.get("sr") == argument:
            try:
                return int(child.attrib["val"])
            except (KeyError, ValueError):
                return None
    return None


def _argument_ids(key: str) -> dict[str, str]:
    """{lowercased argument name: "argN"} for one action code."""
    entry = action_codes.get(key)
    if entry is None:
        return {}
    return {argument.arg_name.lower(): f"arg{argument.arg_id}" for argument in entry.args if argument.arg_name}


def _applies(row: dict, element: Element) -> bool:
    """Whether a table row's 'when' holds -- every argument it names has one of the values listed."""
    return all(_int_argument(element, argument) in values for argument, values in row.get("when", {}).items())


def _scan_item(tally: _Tally, owner: Element, element: Element, suffix: str) -> None:
    """One Task action, or one Profile's Event or State."""
    code = (element.findtext("code") or "").strip()
    if not code:
        return
    key = f"{code}{suffix}"
    name = item_name(code, suffix)
    place = f"{name} in {_place(owner)}"

    package = plugin_package(element)
    if package:
        tally.plugin(package, place)
        return

    row = _table()["items"].get(key, {})
    if "since" in row:
        tally.release(row["since"], name)
    if _applies(row, element):
        for spec in row.get("needs", ()):
            tally.need(spec, place)

    # The switch rule: Use Root, Use Shizuku and Use Tasker Settings, wherever an action has them.
    names = _argument_ids(key)
    for argument_name, access_id in _table()["by_argument"].items():
        argument = names.get(argument_name)
        if argument is not None and _int_argument(element, argument) == 1:
            tally.need(access_id, place)


def _scan_apps(tally: _Tally, owner: Element) -> None:
    """Every app an <App> argument or condition anywhere under this element names."""
    for element in owner.iter("App"):
        for entry in appinv.read_app_element(element) + appinv.read_app_condition_entries(element):
            if appinv.is_variable_reference(entry.pkg) or entry.pkg.startswith(_TASKER_PACKAGES):
                continue
            tally.app(entry.pkg, entry.label, _place(owner))


def _scan_prompts(tally: _Tally, owner: Element) -> None:
    """The variables a Project, Profile or Task asks the importer about.

    <pvci> is "Configure on Import", the box property.py reports.  Only an explicit "false"
    switches it off there and here, and only a variable that has the tag at all is counted:
    every <ProfileVariable> in the sample backups carries one, so its absence is not a
    prompt.
    """
    for variable in owner.findall("ProfileVariable"):
        configure = variable.findtext("pvci")
        if configure is None or configure.strip().lower() == "false":
            continue
        type_code = (variable.findtext("pvt") or "").strip()
        tally.prompts.append(
            PromptNeed(
                owner=_place(owner),
                variable=(variable.findtext("pvn") or "").strip(),
                label=(variable.findtext("pvdn") or "").strip(),
                prompt=(variable.findtext("pvd") or "").strip(),
                type_label=VARIABLE_TYPES.get(type_code, type_code),
                has_default=bool((variable.findtext("pvv") or "").strip()),
            ),
        )


def check_tree(root: Element, scope: str = "") -> Readiness:
    """What the <TaskerData> document needs on the phone that imports it.

    Args:
        root: the document, as an export writes it.
        scope: how the report names what was checked, e.g. "Project 'Home'".
    """
    tally = _Tally()
    for owner in root:
        if owner.tag not in _OWNERS:
            continue
        _scan_apps(tally, owner)
        _scan_prompts(tally, owner)
        if owner.tag == "Profile":
            for condition in owner:
                if condition.tag in _CONDITIONS:
                    _scan_item(tally, owner, condition, _CONDITIONS[condition.tag])
        else:
            for action in owner.iter("Action"):
                _scan_item(tally, owner, action, "t")

    result = Readiness(scope=scope, written_by=root.attrib.get("tv", ""))
    result.plugins = [PluginNeed(package, tuple(places)) for package, places in sorted(tally.plugins.items())]
    result.apps = [AppNeed(package, label, tuple(places)) for package, (label, places) in sorted(tally.apps.items())]
    result.access = sorted(tally.needs(), key=lambda need: need.labels)
    result.prompts = tally.prompts
    if tally.since:
        newest = max(tally.since, key=version_key)
        result.minimum = VersionNeed(newest, tuple(tally.since[newest]))
    return result


# ##################################################################################
# The entry points: what each export would write.
# ##################################################################################
def check_project(project_name: str, state: RunState) -> Readiness:
    """What exporting this Project would hand over, and what the phone receiving it needs.

    Raises ValueError if the Project is not loaded, as the export does.
    """
    rendered = projedit.render_standalone_project_xml(project_name, state=state)
    return check_tree(DefusedET.fromstring(rendered), f"Project '{project_name}'")


def check_scene(scene_name: str, state: RunState) -> Readiness:
    """The same for a Scene export.  Raises ValueError if the Scene is not loaded."""
    rendered = sceneedit.render_standalone_scene_xml(scene_name, state=state)
    return check_tree(DefusedET.fromstring(rendered), f"Scene '{scene_name}'")
