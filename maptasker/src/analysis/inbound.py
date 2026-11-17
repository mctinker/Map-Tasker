"""inbound: everything that can start a Task from outside, and whether anything checks who sent it."""

#! /usr/bin/env python3

#                                                                                       #
# inbound: list the Profiles that wait for something from outside -- a web request to   #
#          Tasker's own server, an Intent, a Command, a share, a text message, a message #
#          from a plugin -- say who can send each one, which Tasks it starts, and       #
#          whether anything looks at who the sender is before they run.                 #
#                                                                                       #
# outbound.py answers "what does this configuration reach out and do".  This is its     #
# mirror: what can reach IN and make the configuration do something.  The two questions #
# are asked for the same reason -- a backup you did not write, or one you wrote long ago, #
# is a program, and the first thing to know about a program is what it will do for       #
# whoever asks.  An HTTP Request event on a port that answers anyone on the Wi-Fi, whose  #
# Task runs a root command, is worth knowing about before it is installed.                #
#                                                                                       #
# Same contract as outbound.py, healthck.py and taskflow.py: everything here reads        #
# PrimeItems.tasker_root_elements and nothing else -- no GUI, no output_lines, no         #
# device.  It runs the moment an XML file is loaded and is testable on its own.           #
#                                                                                       #
# THE ANSWER TO "DOES ANYTHING CHECK WHO SENT IT", in every line, is one of three:        #
#                                                                                       #
#   FILTERED  the trigger itself only accepts some senders: a Received Text from one      #
#             number, a Received Share from one app.                                      #
#   CHECKED   the Task it starts, or one that Task performs, tests something the sender    #
#             supplied -- a header, a body, a command's parameter -- in an If.             #
#   OPEN      neither: whoever can send it, runs it.                                       #
#                                                                                       #
# What this cannot see, said in the report itself because "nothing found" gets trusted:    #
#                                                                                       #
#   * Which events are inbound is a table of Tasker's event codes (_TRIGGERS).  An event     #
#     that something outside can send and is not on it is not listed.                        #
#   * CHECKED means an If looks at what came in.  It does not mean the check is a good one:   #
#     a test of a header that anyone can set is not authentication.  Read it.                 #
#   * Intent Received puts each extra in a variable named after it, so a Task that checks a    #
#     token extra is not told apart from one that checks anything else; only the variables     #
#     Tasker names itself are recognized, and a Task that tests other things is said to.        #
#   * Whether a phone accepts actions from other devices, runs Tasks for other apps, or which   #
#     interface its web server listens on, is a Tasker setting.  Only 'Allow External Access'   #
#     is in the backup, and it is reported; the rest is not.                                    #
#   * Scene elements, widgets, Tasker's own preferences and anything that starts a Task by       #
#     a means other than a Profile event are not read.                                          #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis import outbound
from maptasker.src.analysis.plugchk import item_name
from maptasker.src.core import clock
from maptasker.src.core.mapjump import PROFILE, PROJECT, TASK, Row, Target, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import INBOUND_FILE, MY_VERSION, logger

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# ##################################################################################
# What counts as coming in, and how each kind is read.
# ##################################################################################
WEB = "Web"
INTENT = "Intent"
COMMAND = "Command"
SHARE = "Share"
TEXT = "Text"
REMOTE = "Remote"
PLUGIN = "Plugin"

# In the order the report prints them, and the words it uses.
CATEGORY_TITLES: dict[str, str] = {
    WEB: "Web server requests (HTTP Request)",
    INTENT: "Intents received",
    COMMAND: "Commands received",
    SHARE: "Shares received",
    TEXT: "Text messages received",
    REMOTE: "Remote actions",
    PLUGIN: "Plugin events that take a message in",
}

# Whether anything looks at who sent it.
FILTERED = "FILTERED"
CHECKED = "CHECKED"
OPEN = "OPEN"
# A broadcast only the Android system itself may send is not an entrance anyone else can use.
SYSTEM = "SYSTEM"

FLAG_ANY_NETWORK = "anything that can reach the phone on this port can start it, on any network"
FLAG_ON_WIFI = "anyone on the Wi-Fi network can start it"
FLAG_ANY_APP = "any app on the phone can send it"
FLAG_VARIABLE_ACTION = "the Intent action is built from a variable, so what it listens for is decided on the device"

# What starting a Task can do that is worth naming in a line about who may start it: these are the
# categories outbound.py reads, the ones that act on the phone or on other people rather than ask a server.
_DANGEROUS = (outbound.ROOT, outbound.SHELL, outbound.MESSAGE, outbound.CALL)

_NOT_SET = ("", "<null>")
_PERFORM_TASK = "130"
# How many Perform Tasks deep a Task's checks and consequences are followed.
_CALL_DEPTH = 4
# Another Profile condition alongside the event: it must hold for the event to start anything.
_OTHER_CONTEXTS = frozenset({"State", "Time", "Day", "Loc", "App"})
_SYSTEM_ACTION_PREFIXES = ("android.", "com.android.")
_SHOWN_LENGTH = 90


@dataclass(frozen=True)
class Trigger:
    """How one event code is read: who can send it, and what in it narrows the senders.

    'sender_args' are the argument ids of the event that, when filled in, accept only some senders.
    'sender_keys' are the same for a plugin, whose settings are named fields in a bundle.  'incoming'
    are the variables, lower case and as a prefix, that carry what the sender supplied: an If that
    names one of them is looking at the sender's input.
    """

    category: str
    reach: str
    sender_args: tuple[str, ...] = ()
    sender_keys: tuple[str, ...] = ()
    incoming: tuple[str, ...] = ()
    filter_noun: str = ""  # what the filter is on: 'sender', 'app'


# Event code -> how to read it.  Keyed by the code Tasker writes, as actionc.py is.
_TRIGGERS: dict[str, Trigger] = {
    "2089": Trigger(  # HTTP Request: Tasker is the web server
        WEB,
        "anything that can reach this phone's web server",
        incoming=("%http_request_headers", "%http_request_body", "%http_request_multipart"),
    ),
    "599": Trigger(  # Intent Received
        INTENT,
        "any app on this phone",
        incoming=("%evtprm", "%intent_data"),
    ),
    "2091": Trigger(  # Command
        COMMAND,
        "whatever sends Tasker a Command",
        incoming=("%command_param", "%command_text"),
    ),
    "2101": Trigger(  # Received Share
        SHARE,
        "any app that shares to Tasker",
        sender_args=("arg1",),
        incoming=("%rs_",),
        filter_noun="app",
    ),
    "7": Trigger(  # Received Text: SMS, MMS and others
        TEXT,
        "anyone who can text this phone",
        sender_args=("arg1",),
        incoming=("%smsr", "%mmsr", "%evtprm"),
        filter_noun="sender",
    ),
    "8": Trigger(  # Received Data SMS
        TEXT,
        "anyone who can send this phone a data SMS",
        incoming=("%smsr", "%evtprm"),
    ),
    "2100": Trigger(  # Remote Action Token Changed
        REMOTE,
        "Tasker itself, when the token other devices use to run actions here is replaced",
    ),
    "18927444": Trigger(  # AutoApps Command
        PLUGIN,
        "AutoApps commands: the apps and devices you have linked, and anything that can post to your AutoApps address",
        incoming=("%evtprm", "%command"),
    ),
    "1861978578": Trigger(  # AutoWear Command / Command Filter
        PLUGIN,
        "a command sent from a linked watch or from AutoApps",
        incoming=("%evtprm", "%command"),
    ),
    "1668911626": Trigger(  # Join (receive a push)
        PLUGIN,
        "any device signed in to your Join account, and anything with your Join API key",
        incoming=("%evtprm", "%gcm", "%push"),
    ),
    "580953799": Trigger(  # AutoShare Command
        PLUGIN,
        "any app that shares to AutoShare",
        sender_keys=("configsender",),
        incoming=("%evtprm", "%as"),
        filter_noun="sender",
    ),
    "1133159835": Trigger(  # AutoShare Process Text
        PLUGIN,
        "any app that shares text to AutoShare",
        incoming=("%evtprm", "%as"),
    ),
}


@dataclass
class Entry:
    """One Profile event something outside can send, and everything the report says about it."""

    where: Target
    category: str
    what: str
    detail: str
    reach: str
    guard: str
    guard_detail: str
    runs: list[Target] = field(default_factory=list[Target])
    effects: list[str] = field(default_factory=list[str])
    limits: list[str] = field(default_factory=list[str])
    flags: list[str] = field(default_factory=list[str])
    enabled: bool = True

    @property
    def effects_dangerous(self) -> list[str]:
        """What the Tasks it starts do that acts on the phone or on other people: root, shell, messages, calls."""
        return [kind for kind in self.effects if kind in _DANGEROUS]

    @property
    def needs_a_look(self) -> bool:
        """Whether this is one to read -- flagged, and actually listening."""
        return self.enabled and bool(self.flags)


@dataclass
class ExternalAccess:
    """Tasker's 'Allow External Access' setting: whether other apps may run your Tasks by name."""

    known: bool = False
    allowed: bool = False


# ##################################################################################
# Reading one event.
# ##################################################################################
def _arguments(element: Element) -> dict[str, str]:
    """{"argN": what the element holds there}, for text arguments and numbers alike."""
    found: dict[str, str] = {}
    for child in element:
        argument = str(child.attrib.get("sr", ""))
        if not argument.startswith("arg") or child.tag == "Bundle":
            continue
        found[argument] = (child.attrib.get("val") or "") if child.tag == "Int" else (child.text or "").strip()
    return found


def _bundle_fields(element: Element) -> dict[str, str]:
    """{field: value} of a plugin event's own settings, from its <Bundle><Vals>."""
    vals = element.find("Bundle/Vals")
    return {} if vals is None else {child.tag: (child.text or "").strip() for child in vals}


def _shown(text: str) -> str:
    """Text as the report prints it: one line, and no longer than a line's worth."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first if len(first) <= _SHOWN_LENGTH else f"{first[: _SHOWN_LENGTH - 3]}..."


def _is_system_action(action: str) -> bool:
    """Whether an Intent action is one only Android itself sends, such as android.net.wifi.RSSI_CHANGED."""
    return action.startswith(_SYSTEM_ACTION_PREFIXES)


def _detail(code: str, arguments: dict[str, str], fields: dict[str, str]) -> str:
    """What the event listens for, in the words the Map would use."""
    if code == "2089":
        port = arguments.get("arg1") or "?"
        method = arguments.get("arg2") or "any method"
        path = arguments.get("arg3") or "any path"
        return f"port {port}, {method} {path}"
    if code == "599":
        parts = [arguments.get("arg0") or "any action"]
        if arguments.get("arg3"):
            parts.append(f"scheme {arguments['arg3']}")
        if arguments.get("arg4"):
            parts.append(f"type {arguments['arg4']}")
        return ", ".join(parts)
    if code == "2091":
        return f"component {arguments['arg1']}" if arguments.get("arg1") else "any command"
    if code in {"7", "8"}:
        return f"from {arguments['arg1']}" if arguments.get("arg1") else "from anyone"
    if code == "2101":
        return f"from {arguments['arg1']}" if arguments.get("arg1") else "from any app"
    command = fields.get("Command") or fields.get("configcommand") or ""
    return f"command {command}" if command not in _NOT_SET else ""


def _limits(code: str, arguments: dict[str, str]) -> list[str]:
    """What narrows who can reach an event without naming the sender: the network it listens on."""
    if code != "2089":
        return []
    limits: list[str] = []
    if arguments.get("arg6") == "1":
        limits.append("Wi-Fi only")
    if arguments.get("arg7"):
        limits.append(f"network {arguments['arg7']}")
    return limits


def _filter_text(trigger: Trigger, arguments: dict[str, str], fields: dict[str, str]) -> str:
    """The filter the event puts on its senders, as 'sender +1 415 555 0100', or "" when it has none."""
    for name in trigger.sender_args:
        if arguments.get(name, "") not in _NOT_SET:
            return f"{trigger.filter_noun} {_shown(arguments[name])}"
    for key in trigger.sender_keys:
        if fields.get(key, "") not in _NOT_SET:
            return f"{trigger.filter_noun} {_shown(fields[key])}"
    return ""


# ##################################################################################
# Reading the Tasks an event starts.
# ##################################################################################
class _Tasks:
    """The Tasks of one configuration, and what each does and tests -- worked out once per Task."""

    def __init__(self, state: RunState) -> None:
        self.tasks = state.tasker_root_elements["all_tasks"]
        self.by_name: dict[str, str] = {}
        for task_id, task in self.tasks.items():
            self.by_name.setdefault(task["name"], task_id)
        self.owners = _owners("tids", state)
        # {task id: the categories of what it reaches outside with}, for what is enabled.
        self.effects: dict[str, set[str]] = {}
        for use in outbound.outbound_uses(state):
            if use.enabled and use.category != outbound.ADDRESS:
                self.effects.setdefault(use.where.key, set()).add(use.category)

    def target(self, task_id: str) -> Target:
        """Where a Task is, for a click."""
        return Target(TASK, task_id, self.tasks[task_id]["name"], self.owners.get(task_id, ""))

    def reached(self, task_id: str, seen: set[str] | None = None, depth: int = 0) -> list[str]:
        """The Task and the Tasks it performs, a few levels down, each once, in the order met."""
        seen = set() if seen is None else seen
        if task_id not in self.tasks or task_id in seen or depth > _CALL_DEPTH:
            return []
        seen.add(task_id)
        found = [task_id]
        for action in self.tasks[task_id]["xml"].findall("Action"):
            if (action.findtext("code") or "").strip() != _PERFORM_TASK:
                continue
            name = _arguments(action).get("arg0", "")
            called = self.by_name.get(name)
            if called:
                found += self.reached(called, seen, depth + 1)
        return found

    def conditions(self, task_ids: list[str]) -> list[str]:
        """The text of every If and per-action condition in these Tasks, lower case, one entry per side."""
        text: list[str] = []
        for task_id in task_ids:
            for condition in self.tasks[task_id]["xml"].iter("Condition"):
                text += [(condition.findtext("lhs") or "").lower(), (condition.findtext("rhs") or "").lower()]
        return text

    def handed_over(self, task_ids: list[str], trigger: Trigger) -> tuple[str, str]:
        """(the incoming variable, the Task it is passed to) when a Perform Task hands what was sent to another Task.

        The usual way to check a sender is a Task of its own -- 'Authorize' -- given the request's headers as a
        parameter and answering through a variable.  The If that tests the answer looks at that variable, not at
        anything the sender supplied, so this is the only trace of the check there is.
        """
        for task_id in task_ids:
            for action in self.tasks[task_id]["xml"].findall("Action"):
                if (action.findtext("code") or "").strip() != _PERFORM_TASK:
                    continue
                arguments = _arguments(action)
                called = arguments.get("arg0", "")
                for name, value in arguments.items():
                    variable = _first_incoming(trigger, value.lower())
                    if name != "arg0" and variable and called:
                        return variable, called
        return "", ""

    def kinds(self, task_ids: list[str]) -> list[str]:
        """What these Tasks do to the outside world, in outbound.py's own order."""
        done: set[str] = set()
        for task_id in task_ids:
            done |= self.effects.get(task_id, set())
        return [category for category in outbound.CATEGORY_TITLES if category in done]


def _owners(kind: str, state: RunState) -> dict[str, str]:
    """{member id: owning Project name} for one of a Project's lists (see plugchk._owners)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _profile_is_on(profile: Element) -> bool:
    """Whether a Profile is enabled: <limit>true</limit> is how Tasker records one that is not (see firesim)."""
    return (profile.findtext("limit") or "").strip() != "true"


def _first_incoming(trigger: Trigger, text: str) -> str:
    """The first variable in lower-case text that carries what the sender supplied, whole, or "" when there is none."""
    for prefix in trigger.incoming:
        position = text.find(prefix)
        if position >= 0:
            end = position + len(prefix)
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            return text[position:end]
    return ""


def _checked_variable(trigger: Trigger, conditions: list[str]) -> str:
    """The first incoming variable an If looks at, as written, or "" when none does."""
    for text in conditions:
        variable = _first_incoming(trigger, text)
        if variable:
            return variable
    return ""


# ##################################################################################
# Putting an event together.
# ##################################################################################
def _guard(
    trigger: Trigger,
    event_filter: str,
    tasks: _Tasks,
    reached: list[str],
    *,
    system: bool,
) -> tuple[str, str]:
    """(FILTERED / CHECKED / OPEN / SYSTEM, what says so) for one event."""
    if system:
        return SYSTEM, "only the Android system sends this broadcast"
    if event_filter:
        return FILTERED, f"the event only accepts {event_filter}"
    conditions = tasks.conditions(reached)
    variable = _checked_variable(trigger, conditions)
    if variable:
        return CHECKED, f"an If looks at {variable} before it acts"
    variable, called = tasks.handed_over(reached, trigger)
    if variable:
        return CHECKED, f"{variable} is handed to Task '{called}' to examine"
    if any(conditions):
        return OPEN, "nothing checks who sends it (the Task tests other things, but none of what was sent)"
    return OPEN, "nothing checks who sends it"


def _flags_for(entry: Entry, code: str, arguments: dict[str, str], *, variable_action: bool) -> list[str]:
    """Why an entry is worth a look: who can start it with nothing in the way, and what that would run."""
    if entry.guard != OPEN:
        return []
    flags: list[str] = []
    if code == "2089":
        flags.append(FLAG_ON_WIFI if arguments.get("arg6") == "1" else FLAG_ANY_NETWORK)
    if code == "599" and not variable_action and entry.effects_dangerous:
        flags.append(FLAG_ANY_APP)
    if variable_action:
        flags.append(FLAG_VARIABLE_ACTION)
    if entry.effects_dangerous:
        words = ", ".join(kind.lower() for kind in entry.effects_dangerous)
        flags.append(f"the Task it starts can run {words} actions, and nothing checks who asked")
    return flags


def _entry_for(
    code: str,
    event: Element,
    where: Target,
    run_ids: list[str],
    tasks: _Tasks,
) -> Entry:
    """The Entry one Profile event makes."""
    trigger = _TRIGGERS[code]
    arguments = _arguments(event)
    fields = _bundle_fields(event)
    action = arguments.get("arg0", "")
    variable_action = code == "599" and "%" in action
    system = code == "599" and _is_system_action(action)
    reached: list[str] = []
    for run_id in run_ids:
        reached += [task_id for task_id in tasks.reached(run_id) if task_id not in reached]
    guard, guard_detail = _guard(
        trigger,
        _filter_text(trigger, arguments, fields),
        tasks,
        reached,
        system=system,
    )
    reach = "the Android system" if system else trigger.reach
    entry = Entry(
        where=where,
        category=trigger.category,
        what=item_name(code, "e"),
        detail=_detail(code, arguments, fields),
        reach=reach,
        guard=guard,
        guard_detail=guard_detail,
        runs=[tasks.target(task_id) for task_id in run_ids if task_id in tasks.tasks],
        effects=tasks.kinds(reached),
        limits=_limits(code, arguments),
    )
    entry.flags = _flags_for(entry, code, arguments, variable_action=variable_action)
    return entry


def inbound_entries(state: RunState) -> list[Entry]:
    """Every Profile event in the loaded configuration that something outside can send.

    In the order the Profiles are in the file.  Safe to call with nothing loaded: an empty list.
    """
    root = state.tasker_root_elements
    tasks = _Tasks(state)
    owners = _owners("pids", state)
    entries: list[Entry] = []
    for profile_id, profile in root["all_profiles"].items():
        project = owners.get(profile_id, "")
        where = Target(PROFILE, profile_id, profile["name"], project)
        element: Element = profile["xml"]
        run_ids = [
            (child.text or "").strip() for child in element if child.tag == "mid0" and (child.text or "").strip()
        ]
        others = sum(child.tag in _OTHER_CONTEXTS for child in element)
        for event in element.findall("Event"):
            code = (event.findtext("code") or "").strip()
            if code not in _TRIGGERS:
                continue
            entry = _entry_for(code, event, where, run_ids, tasks)
            entry.enabled = _profile_is_on(element)
            if others:
                entry.limits.append(f"only while {others} other condition{'' if others == 1 else 's'} hold")
            entries.append(entry)
    return entries


def external_access(state: RunState) -> ExternalAccess:
    """Tasker's 'Allow External Access' setting as the backup records it: whether other apps may run Tasks by name."""
    for setting in state.tasker_root_elements.get("all_services", []):
        if (setting.findtext("n") or "").strip() == "aExt":
            return ExternalAccess(known=True, allowed=(setting.findtext("v") or "").strip().lower() == "true")
    return ExternalAccess()


# ##################################################################################
# The report.
# ##################################################################################
_REPORT_WIDTH = 78
_NO_PROJECT = ""


def _current_xml_file(state: RunState) -> str:
    """The path of the XML file being read (see outbound._current_xml_file)."""
    file_to_get = state.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) and path else "(unknown)"


def _heading(title: str) -> list[Row]:
    return [Row(title), Row("-" * _REPORT_WIDTH)]


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _summary_rows(listening: list[Entry]) -> list[Row]:
    """One line per kind of trigger: how many, and how many of them anyone at all can send."""
    rows = _heading("SUMMARY")
    for category, title in CATEGORY_TITLES.items():
        mine = [entry for entry in listening if entry.category == category]
        if not mine:
            continue
        open_ones = sum(entry.guard == OPEN for entry in mine)
        rows.append(Row(f"  {title:<38}{_plural(len(mine), 'trigger'):>12}   {open_ones} open"))
    return [*rows, Row("")]


def _look_rows(listening: list[Entry]) -> list[Row]:
    """The triggers with something flagged on them, each with where it is and why."""
    flagged = [entry for entry in listening if entry.needs_a_look]
    if not flagged:
        return []
    rows = _heading(f"NEEDS A LOOK -- {_plural(len(flagged), 'trigger')}")
    for entry in flagged:
        rows += [
            Row(f"  {entry.where.label}", entry.where),
            Row(f"      {entry.what}: {entry.detail}"),
            Row(f"      Why: {'; '.join(entry.flags)}."),
        ]
    return [*rows, Row("")]


def _guard_sentence(entry: Entry) -> str:
    return f"{entry.guard} -- {entry.guard_detail}"


def _entry_rows(entry: Entry) -> list[Row]:
    off = "   (turned off)" if not entry.enabled else ""
    limits = f"   [{', '.join(entry.limits)}]" if entry.limits else ""
    rows = [
        Row(f"      {entry.what}: {entry.detail}{limits}{off}", entry.where),
        Row(f"        From: {entry.reach}"),
        Row(f"        {_guard_sentence(entry)}"),
    ]
    if entry.runs:
        names = ", ".join(f"'{run.name}'" for run in entry.runs)
        can = f"; it can do: {', '.join(kind.lower() for kind in entry.effects)}" if entry.effects else ""
        rows.append(Row(f"        Starts Task {names}{can}", entry.runs[0].at_action(0)))
    else:
        rows.append(Row("        Starts no Task"))
    return rows


def _by_project(entries: list[Entry]) -> dict[str, dict[str, list[Entry]]]:
    """{Project name: {Profile id: its entries}}, Projects by name and the Profiles that have none last."""
    grouped: dict[str, dict[str, list[Entry]]] = {}
    for entry in entries:
        grouped.setdefault(entry.where.project, {}).setdefault(entry.where.key, []).append(entry)
    ordered = sorted(grouped, key=lambda name: (name == _NO_PROJECT, name.casefold()))
    return {name: grouped[name] for name in ordered}


def _project_rows(entries: list[Entry]) -> list[Row]:
    """Everything, Project by Project and Profile by Profile -- the answer to "what can start this Project"."""
    if not entries:
        return []
    rows = _heading("BY PROJECT")
    for project, profiles in _by_project(entries).items():
        count = sum(len(items) for items in profiles.values())
        if project == _NO_PROJECT:
            rows.append(Row(f"Not in any Project   ({_plural(count, 'trigger')})"))
        else:
            rows.append(Row(f"Project '{project}'   ({_plural(count, 'trigger')})", Target(PROJECT, project, project)))
        for items in profiles.values():
            rows.append(Row(f"    Profile '{items[0].where.name}'", items[0].where))
            for entry in items:
                rows.extend(_entry_rows(entry))
        rows.append(Row(""))
    return rows


def _access_rows(access: ExternalAccess) -> list[Row]:
    """The one inbound setting the backup carries, which is a way in that no Profile shows."""
    rows = _heading("OTHER WAYS IN")
    if not access.known:
        rows.append(Row("  Tasker's 'Allow External Access' setting is not in this file (a single Project,"))
        rows.append(Row("  Profile or Task export does not carry the settings), so it is not known whether"))
        rows.append(Row("  other apps on the phone may run your Tasks by name."))
    elif access.allowed:
        rows.append(Row("  Allow External Access is ON.  Any app on the phone that knows a Task's name may"))
        rows.append(Row("  run it, with nothing to say who asked.  Turn it off in Tasker's Preferences if no"))
        rows.append(Row("  other app needs to start your Tasks."))
    else:
        rows.append(Row("  Allow External Access is off: other apps may not run your Tasks by name."))
    return [*rows, Row("")]


def _limitations() -> list[Row]:
    """The closing note on what the inventory cannot see, for outbound's reason: silence has to be readable."""
    return [
        Row("NOTE ON WHAT IS NOT LISTED"),
        Row("-" * _REPORT_WIDTH),
        Row("Which events count as coming in is a list of Tasker's event codes; an event"),
        Row("something outside can send that is not on it is missed.  CHECKED means an If"),
        Row("looks at what came in, not that the check is a good one: a header anyone can"),
        Row("set is not a password.  An Intent's extras are variables named after them, so"),
        Row("a check on one is not recognized, and the report says when a Task tests other"),
        Row("things instead.  Whether this phone accepts actions from other devices, and"),
        Row("which network its web server answers on, are Tasker settings that are not in"),
        Row("the backup.  Scenes, widgets and anything that starts a Task other than a"),
        Row("Profile event are not read."),
        Row(""),
    ]


def run_inbound_inventory(state: RunState) -> tuple[list[Row], dict[str, int]]:
    """Read every Profile and return (report rows, counts).

    The counts are by category for the triggers that are listening, plus "open" for those nothing
    checks, "flagged" for those worth a look and "total" for all of them.  Rows rather than finished
    text, for outbound's reason: the caller saves them as plain text and shows them as HTML.
    A Profile that is turned off is listed where it sits and counted nowhere.
    """
    entries = inbound_entries(state)
    listening = [entry for entry in entries if entry.enabled and entry.guard != SYSTEM]
    access = external_access(state)

    counts = {category: sum(entry.category == category for entry in listening) for category in CATEGORY_TITLES}
    counts["open"] = sum(entry.guard == OPEN for entry in listening)
    counts["flagged"] = sum(entry.needs_a_look for entry in listening)
    counts["total"] = len(listening)
    counts["external_access"] = int(access.known and access.allowed)

    profiles = state.tasker_root_elements["all_profiles"]
    rows = [
        Row("MapTasker Inbound Inventory"),
        Row("=" * _REPORT_WIDTH),
        Row(f"XML file:    {_current_xml_file(state)}"),
        Row(f"Generated:   {clock.now().strftime('%d-%b-%Y %H:%M:%S')}"),
        Row(f"Version:     {MY_VERSION}"),
        Row(""),
        Row(f"Scanned:     {_plural(len(profiles), 'Profile')}"),
        Row(
            f"Found:       {_plural(counts['total'], 'trigger')} something outside can send, "
            f"{counts['open']} with nothing checking who sends it, {counts['flagged']} worth a look",
        ),
        Row(""),
    ]
    if not entries:
        return [
            *rows,
            Row("Nothing to report -- no Profile waits for a web request, an Intent, a Command,"),
            Row("a share, a text message or a plugin message."),
            Row(""),
            *_access_rows(access),
            *_limitations(),
        ], counts
    body = [
        *_summary_rows(listening),
        *_look_rows(listening),
        *_project_rows(entries),
        *_access_rows(access),
    ]
    return [*rows, *body, *_limitations()], counts


def write_inbound_report(rows: list[Row], state: RunState) -> str:
    """Write the inventory to a timestamped file in the output folder.

    Returns the path written, or "" if the write failed -- named, stamped and handled exactly
    as outbound.write_outbound_report is, and for its reasons.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(INBOUND_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Inbound Inventory could not be written: {error}")
        return ""
    return file_path
