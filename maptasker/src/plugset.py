"""plugset: what a plugin action or condition was set up to do, in words."""

#! /usr/bin/env python3

#                                                                                       #
# plugset: read a third-party plugin's <Bundle> the way the plugin itself would, for    #
#          the four plugins Tasker users reach for most -- AutoTools, AutoInput, Join   #
#          and Home Assistant -- and say which plugin an action or condition belongs    #
#          to at all.                                                                   #
#                                                                                       #
# Every other plugin is shown the way it always was: one "Name=value" line per field    #
# (actargs.get_plugin_settings).  That is honest, and for the four here it is also      #
# close to unreadable.  Three things make it so, and each is undone below:              #
#                                                                                       #
#   * Newer plugins -- everything built on joaomgcd's TaskerPluginLibrary, which is all #
#     three of his here and the Home Assistant one -- do not keep their settings as     #
#     fields.  They keep them as ONE field, 'parameters', holding a JSON document, and  #
#     say so in net.dinglisch.android.tasker.JSON_ENCODED_KEYS.  Shown as a field, a    #
#     Join push is one line of braces with the text buried in the middle of it.        #
#   * Older ones keep choices as numbers.  AutoInput's "ActionType=16" is Android's    #
#     own constant for a click, and "GlobalAction=1" is Android's for Back.             #
#   * Every one of them carries plumbing -- plugininstanceid, plugintypeid, the         #
#     generatedValues the library keeps for itself, Home Assistant's server id -- and  #
#     a switch that is simply off, written out in full, twenty to a Sort Arrays action. #
#                                                                                       #
# Nothing here writes a bundle.  Changing a plugin's settings still happens in the      #
# plugin, on the device: a plugin checks its own bundle when Tasker hands it over, and  #
# an edit it did not make itself is one it is entitled to reject.                       #
#                                                                                       #
# Deliberately dependency-free (the standard library and nothing of this package), so  #
# actargs, taskedit and the health check can all import it without a cycle.            #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

# A Locale/Tasker-plugin payload carries a BLURB: the plugin's own summary of how it is
# configured.  Its presence is what marks a <Bundle> as a third-party plugin's, rather than
# the 'Output Variables' hint a built-in action carries (see taskedit.BLURB_TAG).
BLURB_TAG = "com.twofortyfouram.locale.intent.extra.BLURB"

# Where a plugin Action, Event or State names the plugin: <Bundle sr="arg0"> is its
# settings, <Str sr="arg1"> its package and <Str sr="arg2"> the screen that configures it.
# The same three slots on every one of the ~440 plugin items in this repo's reference
# backup, whichever of the three kinds it was.
PACKAGE_ARGUMENT = "arg1"

# The <Vals> entries that belong to Tasker and the plugin FRAMEWORK rather than to the
# plugin's own configuration: the blurb, the list of fields Tasker may substitute a
# variable into, the "subbundled" flag, and the rest of the locale-plugin plumbing.  Left
# out because none of them is a setting the user made -- they are how the two programs talk
# to each other -- and on this repo's reference backup they are two thirds of everything a
# <Vals> holds.
BUNDLE_HOUSEKEEPING = ("net.dinglisch.android.tasker.", "com.twofortyfouram.locale.")

# Every value in a <Vals> is written twice: the value, and a "<name>-type" beside it saying
# what Java class it is.  The class is the plugin's business, not the reader's.
BUNDLE_TYPE_SUFFIX = "-type"

# What Tasker writes for a plugin field the user never filled in.
BUNDLE_UNSET = "<null>"

# The framework's own list of the fields that hold JSON rather than a value (space
# separated -- "parameters" on every TaskerPluginLibrary plugin).
_JSON_ENCODED_KEYS = "net.dinglisch.android.tasker.JSON_ENCODED_KEYS"
# The one such field there is, for a bundle written before the framework listed it.
_PARAMETERS = "parameters"

# Fields every TaskerPluginLibrary plugin writes for its own bookkeeping.
_PLUMBING = frozenset({"plugininstanceid", "plugintypeid", "generatedValues"})

# A rendered list or object is cut to this.  An AutoTools Web Screen carries the whole of
# the HTML it injects, and one line of the Map is not the place to read it.
_LONGEST_VALUE = 300

# A value this short is only taken to be in the blurb beside its own label (see _Blurb):
# "1" and "on" are in every blurb, and leaving them out would hide real settings.
_SHORTEST_REPEAT = 3


@dataclass(frozen=True)
class Decoded:
    """A plugin's settings, read.

    lines is (label, value) pairs, in the order the plugin's own screen would show them.
    keep_blurb says whether the blurb is still worth printing above them: for most plugins
    it is the plugin's own sentence about what the action does, and it leads; for Home
    Assistant it is nothing but the same fields again ("dataJson: {}"), so it is dropped.
    """

    lines: tuple[tuple[str, str], ...]
    keep_blurb: bool = True


# ##################################################################################
# Which plugin an action or condition belongs to.
# ##################################################################################
def is_plugin(element: Element) -> bool:
    """Whether an Action, Event or State is a third-party plugin's.

    The blurb test taskedit.needs_tasker_configuration makes, on the <Bundle> Tasker writes
    directly under the item -- a condition's own <Bundle>, not one somewhere below it.
    """
    bundle = element.find("Bundle")
    vals = bundle.find("Vals") if bundle is not None else None
    return vals is not None and vals.find(BLURB_TAG) is not None


def plugin_package(element: Element) -> str:
    """The package of the plugin an Action, Event or State belongs to, or "" if it is not one."""
    if not is_plugin(element):
        return ""
    for child in element.findall("Str"):
        if child.attrib.get("sr") == PACKAGE_ARGUMENT:
            return (child.text or "").strip()
    return ""


# ##################################################################################
# Reading a bundle.
# ##################################################################################
def _fields(vals: Element) -> dict[str, str]:
    """The plugin's own fields in a <Vals>, by name, with the framework's taken out."""
    fields: dict[str, str] = {}
    for child in vals:
        tag = child.tag
        if tag.endswith(BUNDLE_TYPE_SUFFIX) or tag.startswith(BUNDLE_HOUSEKEEPING):
            continue
        fields[tag] = (child.text or "").strip()
    return fields


def _json_keys(vals: Element) -> set[str]:
    """The fields the framework says hold JSON."""
    listed = (vals.findtext(_JSON_ENCODED_KEYS) or "").split()
    return set(listed) | {_PARAMETERS}


def _parsed(text: str) -> dict | None:
    """A JSON field's document, or None if it is not one."""
    if not text.startswith("{"):
        return None
    try:
        document = json.loads(text)
    except ValueError:
        return None
    return document if isinstance(document, dict) else None


# A list a plugin keeps in one field is written in Tasker's own encoding for one:
# <StringArray sr=""><_array_Fields0>first</_array_Fields0>...</StringArray>.
_STRING_ARRAY = "<StringArray"
_STRING_ARRAY_ITEM = re.compile(r"<_array_[^>]*>(.*?)</_array_", re.DOTALL)

_WORD_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def humanize(name: str) -> str:
    """A field's name as a label: "pushDevices" is "Push Devices", "_action" is "Action".

    Split on the case changes and underscores the plugins' authors use, and each word given
    a capital -- but an all-capitals word (URL, ID) left as it is written.
    """
    words = [word for part in name.strip("_").split("_") for word in _WORD_BREAK.split(part) if word]
    return " ".join(word if word.isupper() else word[:1].upper() + word[1:] for word in words)


def _shown(value: object) -> str:
    """One value as the Map prints it, or "" for a value that says nothing.

    A switch that is off, an empty string and an empty list are all what the plugin writes
    for a setting the user left alone, so none of them is shown.
    """
    if value is None or value is False:
        return ""
    if value is True:
        return "true"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(_STRING_ARRAY):
            return ", ".join(item.strip() for item in _STRING_ARRAY_ITEM.findall(text) if item.strip())
        return "" if text in ("", BUNDLE_UNSET, "false") else text
    if isinstance(value, list) and value and not any(isinstance(item, (dict, list)) for item in value):
        return ", ".join(text for text in (_shown(item) for item in value) if text)
    rendered = json.dumps(value, separators=(",", ":"), ensure_ascii=False) if value else ""
    return rendered if len(rendered) <= _LONGEST_VALUE else f"{rendered[: _LONGEST_VALUE - 3]}..."


def _flatten(document: dict, parent: str = "") -> list[tuple[str, str, object]]:
    """[(field, parent, value)] for every leaf of a JSON settings document.

    A plugin's screen groups its settings under headings ("advancedSettings", "textSettings"),
    and the heading is what keeps two of them with the same name apart; it is recorded
    alongside each leaf so the label can use it when it has to (see _Labels).
    """
    leaves: list[tuple[str, str, object]] = []
    for key, value in document.items():
        if key in _PLUMBING:
            continue
        if isinstance(value, dict):
            leaves += _flatten(value, key)
        else:
            leaves.append((key, parent, value))
    return leaves


class _Labels:
    """Hands out labels, keeping any two in one bundle from reading the same."""

    def __init__(self, names: dict[str, str]) -> None:
        self.names = names
        self.used: set[str] = set()

    def __call__(self, key: str, parent: str = "") -> str:
        label = self.names.get(key) or humanize(key)
        if label in self.used and parent:
            heading = humanize(parent).split()
            words = label.split()
            # "Dialog Title Buttons" and "Buttons Top Margin" share the word between them.
            label = " ".join(heading[:-1] if heading and words and heading[-1] == words[0] else heading) + f" {label}"
        self.used.add(label)
        return label


def _normalized(text: str) -> str:
    return " ".join(text.split()).lower()


class _Blurb:
    """What a plugin's blurb already says, so a setting it states is not printed again.

    AutoInput's blurb reads "Type: Text / Value: Date / Nearby Text: , 2022 / Action :
    Click" -- the whole of what the action does -- and repeating each of those as a setting
    underneath doubles the length of the line and says nothing new.

    Matched on the blurb's own "Label: value" lines rather than on any mention of the
    value: a Join push titled "Alarm" is not described by a blurb that happens to contain
    the word.  A switch is only matched with its label, since "true" is on half the lines
    of every blurb; a long value (an AutoInput script, which its blurb spreads over many
    lines) is matched anywhere in it.
    """

    _LONG = 20

    def __init__(self, text: str) -> None:
        self.whole = _normalized(text)
        self.labels: dict[str, set[str]] = {}  # value -> the labels the blurb gives it
        for line in text.splitlines():
            label, colon, value = line.partition(":")
            if colon:
                self.labels.setdefault(_normalized(value), set()).add(_normalized(label))

    def says(self, label: str, value: str) -> bool:
        """Whether the blurb already states this setting.

        A label matches when one ends with the other, since a plugin names a field more
        fully than its blurb does: AutoTools' "toastCornerRadius" is "Corner Radius" there.
        """
        wanted = _normalized(value)
        if not self.whole or not wanted:
            return False
        mine = _normalized(label)
        theirs = self.labels.get(wanted, set())
        if any(other == mine or mine.endswith(f" {other}") or other.endswith(f" {mine}") for other in theirs):
            return True
        if wanted in ("true", "false") or len(wanted) < _SHORTEST_REPEAT:
            return False
        return bool(theirs) or (len(wanted) >= self._LONG and wanted in self.whole)


def _read(
    vals: Element,
    names: dict[str, str],
    *,
    drop: frozenset[str] = frozenset(),
    choices: dict[str, dict[str, str]] | None = None,
    special: Callable[[dict[str, str], _Labels], list[tuple[str, str]]] | None = None,
    blurb: str = "",
) -> list[tuple[str, str]]:
    """The settings in one bundle, as (label, value) pairs.

    names:   field -> label, for the fields humanize would name badly.
    drop:    fields that are plumbing for this plugin in particular.
    choices: field -> {stored value: what it means}, for the ones kept as numbers.  A
             number not in the table is shown as it is written rather than guessed at.
    special: reads the fields that only make sense together (Join's filters, Home
             Assistant's domain and service) and returns their lines; any field it used
             is taken out of the dictionary it is handed.
    """
    fields = {key: value for key, value in _fields(vals).items() if key not in _PLUMBING and key not in drop}
    labels = _Labels(names)
    lines = special(fields, labels) if special else []
    json_keys = _json_keys(vals)
    said = _Blurb(blurb)

    for key, raw in fields.items():
        document = _parsed(raw) if key in json_keys else None
        leaves = _flatten(document) if document is not None else [(key, "", raw)]
        for leaf, parent, value in leaves:
            if leaf in drop:
                continue
            text = _shown(value)
            if not text:
                continue
            if choices and leaf in choices:
                text = choices[leaf].get(text, text)
            label = labels(leaf, parent)
            if said.says(label, text):
                continue
            # A multi-line value (an AutoInput script) would break the one-setting-per-line
            # format everything downstream relies on.
            line = (label, "; ".join(part.strip() for part in text.splitlines() if part.strip()))
            # AutoTools Web Screen keeps its preset twice, once as a field and once in its JSON.
            if line not in lines:
                lines.append(line)
    return lines


# ##################################################################################
# The four plugins.
# ##################################################################################
_AUTOTOOLS_NAMES = {
    "Dialog": "Dialog Type",
    "ScreenPreset": "Preset",
    "webscreenPreset": "Preset",
    "webscreenSource": "Source",
    "webscreenCloseOverlayId": "Close Overlay ID",
    "htmlReadUrl": "URL",
    "htmlReadCCSQuery": "CSS Queries",
    "htmlReadVarNames": "Variable Names",
    "toastText": "Text",
    "launcherCommand": "Command",
    "config_RequestDesktopVersion": "Request Desktop Version",
}


def _autotools(vals: Element, blurb: str) -> Decoded:
    return Decoded(tuple(_read(vals, _AUTOTOOLS_NAMES, blurb=blurb)))


# AutoInput keeps its choices as Android's own accessibility constants.  ActionType is an
# AccessibilityNodeInfo action -- 16 is ACTION_CLICK -- except for AutoInput's own -1,
# writing text; GlobalAction is an AccessibilityService GLOBAL_ACTION_*.  FieldSelectionType
# is AutoInput's own, and only the four this repo's backups show in use, each checked
# against the blurb AutoInput wrote beside it, are named.
_AUTOINPUT_CHOICES = {
    "ActionType": {
        "-1": "Write",
        "1": "Focus",
        "4": "Select",
        "16": "Click",
        "32": "Long Click",
        "4096": "Scroll Forward",
        "8192": "Scroll Backward",
        "16384": "Copy",
        "32768": "Paste",
        "65536": "Cut",
    },
    "FieldSelectionType": {"0": "Text", "1": "Id", "2": "Focus", "5": "Point"},
    "GlobalAction": {
        "1": "Back",
        "2": "Home",
        "3": "Recent Apps",
        "4": "Notifications",
        "5": "Quick Settings",
        "6": "Power Dialog",
        "7": "Split Screen",
        "8": "Lock Screen",
        "9": "Screenshot",
    },
    "GestureType": {"0": "Swipe"},
    "screenAction": {"0": "Turn Off"},
}
_AUTOINPUT_NAMES = {
    "ActionType": "Action",
    "FieldSelectionType": "Find By",
    "ActionId": "Value",
    "AppPackage": "App",
    "Regex": "Text Filter",
    "UIUpdateText": "Update Text",
    "UIUpdateFields": "Update Fields",
    "_action": "Actions",
    "notInAutoInput": "Skip While In AutoInput",
    "notInTasker": "Skip While In Tasker",
    "checkMs": "Check Every (ms)",
    "initialPoint": "Start Point",
    "endPoint": "End Point",
    "duration": "Duration (ms)",
    "screenAction": "Screen",
}


def _autoinput(vals: Element, blurb: str) -> Decoded:
    return Decoded(tuple(_read(vals, _AUTOINPUT_NAMES, choices=_AUTOINPUT_CHOICES, blurb=blurb)))


_JOIN_NAMES = {
    "pushDevices": "Devices",
    "url": "URL",
    "find": "Find Device",
    "location": "Send Location",
    "screenshot": "Take Screenshot",
    "imageIconNotification": "Notification Icon",
    "deviceTypeFilter": "Device Types",
    "StartedCatpure": "Start Capture",  # sic: Join's own spelling
    "StoppedCatpure": "Stop Capture",
}
# Join's 'Push Received' event filters on three things, each with the same four switches.
_JOIN_FILTERS = ("Text", "Title", "Url")
_JOIN_FILTER_SWITCHES = (
    ("Regex", "regex"),
    ("Exact", "exact"),
    ("CaseInsensitive", "ignoring case"),
    ("ContainsAll", "contains all"),
)


def _join_filters(fields: dict[str, str], labels: _Labels) -> list[tuple[str, str]]:
    """Join's filters, one line each: "Title Filter=Alarm (regex, ignoring case)".

    Sixteen fields become as many lines as there are filters set, which is usually one;
    a switch belongs to its filter, and read on its own ("FilterTitleRegex=true") it says
    nothing about what is being matched.
    """
    lines = []
    for what in _JOIN_FILTERS:
        base = f"Filter{what}"
        value = fields.pop(base, "")
        switches = [word for suffix, word in _JOIN_FILTER_SWITCHES if fields.pop(f"{base}{suffix}", "") == "true"]
        if value and value != BUNDLE_UNSET:
            shown = f"{value} ({', '.join(switches)})" if switches else value
            lines.append((labels(f"{what}Filter", "") if what != "Url" else "URL Filter", shown))
    return lines


def _join(vals: Element, blurb: str) -> Decoded:
    # A Join Action is named by the blurb ("Join Action: HearingaidMute") and stored as a
    # number that means nothing outside Join; the devices a push goes to are stored as ids
    # and named by the blurb too ("Device: Brave"), whenever Join could name them.
    drop = {"joinAction"}
    if any(line.lower().startswith("device") for line in blurb.splitlines()):
        drop.add("pushDevices")
    return Decoded(tuple(_read(vals, _JOIN_NAMES, drop=frozenset(drop), special=_join_filters, blurb=blurb)))


def _home_assistant_service(fields: dict[str, str], labels: _Labels) -> list[tuple[str, str]]:
    """'Call Service' as Home Assistant itself writes a service: light.turn_on."""
    domain, service = fields.pop("domain", ""), fields.pop("service", "")
    if domain and service:
        return [(labels("service"), f"{domain}.{service}")]
    return [(labels(key), value) for key, value in (("domain", domain), ("service", service)) if value]


_HOME_ASSISTANT_NAMES = {"entityId": "Entity", "dataJson": "Data", "enabled": "WebSocket Enabled"}
# instanceId is which of the plugin's saved servers to use, as an id of its own; 'dummy' is
# the field Test Connection writes because a TaskerPluginLibrary input may not be empty.
_HOME_ASSISTANT_DROP = frozenset({"instanceId", "dummy"})


def _home_assistant(vals: Element, _blurb: str) -> Decoded:
    lines = _read(vals, _HOME_ASSISTANT_NAMES, drop=_HOME_ASSISTANT_DROP, special=_home_assistant_service)
    # "{}" is Call Service with no data, which is most of them.
    return Decoded(tuple(line for line in lines if line[1] != "{}"), keep_blurb=False)


_DECODERS: dict[str, Callable[[Element, str], Decoded]] = {
    "com.joaomgcd.autotools": _autotools,
    "com.joaomgcd.autoinput": _autoinput,
    "com.joaomgcd.join": _join,
    "com.github.db1996.taskerha": _home_assistant,
}

# The plugins decode_settings reads, for the help text and the tests.
DECODED_PACKAGES = frozenset(_DECODERS)


def decode_settings(vals: Element, package: str, blurb: str = "") -> Decoded | None:
    """A known plugin's settings, read; None for any other plugin.

    blurb is the text already being shown for this bundle, so a setting it states is not
    repeated underneath it.
    """
    decoder = _DECODERS.get(package)
    return decoder(vals, blurb) if decoder else None


def settings_summary(element: Element) -> str:
    """One line saying how a plugin Action or condition is set up, or "".

    For the read-only box the Task and Profile editors show in place of a plugin's
    settings, which cannot be edited here.  A plugin this module does not read is summed up
    by its own blurb.
    """
    package = plugin_package(element)
    bundle = element.find("Bundle")
    vals = bundle.find("Vals") if bundle is not None else None
    if not package or vals is None:
        return ""
    blurb = (vals.findtext(BLURB_TAG) or "").strip()
    decoded = decode_settings(vals, package, blurb)
    parts = [" ".join(blurb.split())] if blurb and (decoded is None or decoded.keep_blurb) else []
    if decoded is not None:
        parts += [f"{label}: {value}" for label, value in decoded.lines]
    return "; ".join(parts)
