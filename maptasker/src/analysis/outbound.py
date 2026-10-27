"""outbound: every address, number and command the configuration reaches outside itself with."""

#! /usr/bin/env python3

#                                                                                       #
# outbound: list the actions that send something beyond the phone -- a web request, an  #
#           SMS or email, a call, a shell command, a root command, an Intent, a plugin  #
#           that goes online -- and say where each one goes, by Project.                #
#                                                                                       #
# The Health Check answers "is a password written into an action".  This answers the   #
# question that comes before it, and the one a person asks before installing somebody   #
# else's Project: what does this configuration DO to the outside world, and to whom?   #
# A backup you did not write is a program with access to your SMS, your phone calls and #
# a root shell, and until now the only way to know what it contacted was to read it.    #
#                                                                                       #
# Same contract as healthck.py, taskflow.py and piiscan.py: everything here reads       #
# PrimeItems.tasker_root_elements and nothing else -- no GUI, no output_lines, no       #
# device.  It runs the moment an XML file is loaded and is testable on its own.         #
#                                                                                       #
# piiscan feeds it twice.  A key pasted into an address is the commonest leak there is, #
# and an inventory is exactly the kind of file that gets attached to a forum post, so   #
# every address and command printed here goes through piiscan first -- the host and the #
# path stay, the key becomes [REDACTED:API-KEY] -- and an action that carries a         #
# credential is flagged by the same rules the Health Check uses, so the two reports     #
# cannot disagree about what a credential is.                                            #
#                                                                                       #
# What this cannot see, said in the report itself because an inventory is trusted to be #
# complete:                                                                             #
#                                                                                       #
#   * Which actions are really outbound is a table of Tasker's action codes (_KINDS).   #
#     An action that does something to the outside and is not on it is not listed.      #
#   * An address built from a variable ('%server/path') is decided on the device.  It is #
#     listed with the address as written and flagged, never guessed at.                  #
#   * A plugin's own settings are a bundle only the plugin understands.  Plugins on the #
#     list are named, and any address written in their settings is found as text; where  #
#     they go otherwise is theirs to say.                                                #
#   * Profile conditions, Scene elements and Tasker's own preferences are not read.      #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis.plugchk import item_name
from maptasker.src.core import clock, piiscan
from maptasker.src.core.actiont import lookup_values
from maptasker.src.core.mapjump import PROJECT, TASK, Row, Target, actions_in_map_order, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import MY_VERSION, OUTBOUND_FILE, logger

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# ##################################################################################
# What counts as reaching outside, and how each kind is read.
# ##################################################################################
WEB = "Web"
MESSAGE = "Message"
CALL = "Call"
SHELL = "Shell"
ROOT = "Root"
INTENT = "Intent"
PLUGIN = "Plugin"
# Not a kind of action but a kind of finding: an address written into an action that does not
# itself go online -- a Variable Set holding the server a later request will use.
ADDRESS = "Address"

# In the order the report prints them, and the words it uses.
CATEGORY_TITLES: dict[str, str] = {
    WEB: "Web requests and downloads",
    MESSAGE: "Messages (SMS, MMS, email)",
    CALL: "Phone calls",
    SHELL: "Shell commands",
    ROOT: "Root commands",
    INTENT: "Intents",
    PLUGIN: "Plugin actions that go online",
}

# Why an action needs a look.  Printed as written, so each reads as a sentence fragment.
FLAG_PLAIN_HTTP = "plain http, so what it sends is not encrypted"
FLAG_VARIABLE_ADDRESS = "the address is built from a variable, so where it goes is decided on the device"
FLAG_ROOT = "runs as root"
FLAG_ROOT_VARIABLE = "may run as root: whether it does is decided by a variable"
FLAG_CREDENTIAL = "carries a credential"

_ROOT_ARGUMENT = "arg2"
_SHIZUKU_ARGUMENT = "arg8"
_INTENT_TARGET_ARGUMENT = "arg9"


@dataclass(frozen=True)
class Kind:
    """How one action code is read: what sort of outbound it is, and which arguments say where.

    'fields' are the argument ids whose text is the destination.  'joined' is for the HTTP Get,
    Post and Head actions, whose Server:Port and Path are one address written in two boxes.
    """

    category: str
    fields: tuple[str, ...] = ()
    joined: bool = False


_SERVER_AND_PATH = ("arg0", "arg1")

# Task action code -> how to read it.  Keyed by the code Tasker writes, as actionc.py is.
_KINDS: dict[str, Kind] = {
    # ---- The web ---------------------------------------------------------------------
    "339": Kind(WEB, ("arg2",)),  # HTTP Request
    "118": Kind(WEB, _SERVER_AND_PATH, joined=True),  # HTTP Get
    "116": Kind(WEB, _SERVER_AND_PATH, joined=True),  # HTTP Post
    "117": Kind(WEB, _SERVER_AND_PATH, joined=True),  # HTTP Head
    "104": Kind(WEB, ("arg0",)),  # Browse URL
    "351": Kind(WEB, ("arg4", "arg5")),  # HTTP Auth: the two endpoints
    "320": Kind(WEB, ("arg0",)),  # Ping
    "321": Kind(WEB),  # GD Upload: Google Drive, wherever the account says
    "326": Kind(WEB),  # GD Download
    # ---- Messages --------------------------------------------------------------------
    "41": Kind(MESSAGE, ("arg0",)),  # Send SMS
    "42": Kind(MESSAGE, ("arg0",)),  # Send Data SMS
    "250": Kind(MESSAGE, ("arg0",)),  # Compose SMS
    "111": Kind(MESSAGE, ("arg0",)),  # Compose MMS
    "125": Kind(MESSAGE, ("arg0",)),  # Compose Email
    # ---- Calls -----------------------------------------------------------------------
    "90": Kind(CALL, ("arg0",)),  # Call
    "97": Kind(CALL, ("arg1",)),  # Call Divert: where the calls are sent
    # ---- The device itself -----------------------------------------------------------
    "123": Kind(SHELL, ("arg0",)),  # Run Shell; becomes ROOT when Use Root is on
    "877": Kind(INTENT),  # Send Intent
}

# Plugins that, by what they are, go online or run commands.  A short list on purpose: a plugin
# is on it because its job is the outside world, not because it might touch it.
_PLUGIN_CODES = (
    "122375409",  # AutoWeb Web Services
    "1339291165",  # AutoWeb Download
    "171109731",  # AutoWeb Authentication
    "1188666028",  # AM UDP Client
    "1887951895",  # AutoMail Send
    "1494192574",  # AutoMail Get
    "1283066927",  # HA Call Service
    "1820222394",  # HA Set WebSocket Connection
    "146456536",  # HA send message back
    "1502263066",  # FolderSync
    "553",  # SMS Backup+
    "502807688",  # AutoAppsHub SendCommand
    "1138588429",  # Join Send Query
    "488837120",  # ADB Shell Command
    "1955641090",  # ADB Shell Toggle Permission
    "338313797",  # ADB Shell Install APK
    "940160580",  # AutoShare
)
_KINDS.update(dict.fromkeys(_PLUGIN_CODES, Kind(PLUGIN)))

# An address in free text: a scheme Tasker's own actions and the common plugins speak, then
# everything up to the first thing that cannot be part of one.
_ADDRESS_IN_TEXT = re.compile(
    r"\b(?:https?|ftps?|sftp|wss?|ssh|smb|rtsp|mqtts?|tcp|udp)://[^\s'\"<>)\]]+",
    re.IGNORECASE,
)
_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://")
# The schemes that go over a network.  'whatsapp://send', 'file://%par1' and 'market://details' are
# addresses of a kind and none has a host: they are the phone talking to one of its own apps.
_NETWORK_SCHEMES = frozenset(
    {"http", "https", "ftp", "ftps", "sftp", "ws", "wss", "ssh", "smb", "rtsp", "mqtt", "mqtts", "tcp", "udp"}
)
# ...and the ones written without '//', which a "host:port" would otherwise be mistaken for.
_OPAQUE_SCHEME = re.compile(r"^(?:tel|mailto|sms|smsto|geo|sip|package|market):", re.IGNORECASE)
_PLAIN_HTTP = "http://"

# Names that mean "this network, not the internet".  A request to the router is a different
# thing from a request to a server in another country, and the report says which.
_LOCAL_SUFFIXES = (".local", ".lan", ".home", ".internal", ".home.arpa")
_LOCAL_HOSTS = ("localhost",)

_SHOWN_LENGTH = 110


@dataclass
class Use:
    """One action that reaches outside, and everything the report says about it."""

    where: Target
    category: str
    what: str
    detail: str
    hosts: list[str] = field(default_factory=list[str])
    flags: list[str] = field(default_factory=list[str])
    enabled: bool = True

    @property
    def needs_a_look(self) -> bool:
        """Whether this is one to read -- flagged, and actually going to run."""
        return self.enabled and bool(self.flags)


# ##################################################################################
# Reading one action.
# ##################################################################################
def _arguments(action: Element) -> dict[str, str]:
    """{"argN": what the action holds there}, for text arguments and for numbers alike.

    A number is Tasker's <Int val="1"/>; one set from a variable is <Int><var>%x</var></Int>,
    and gives the variable's name, which is how a caller can tell the two apart.
    """
    found: dict[str, str] = {}
    for child in action:
        argument = str(child.attrib.get("sr", ""))
        if not argument.startswith("arg"):
            continue
        if child.tag == "Int":
            found[argument] = child.attrib.get("val") or (child.findtext("var") or "").strip()
        else:
            found[argument] = (child.text or "").strip()
    return found


def _shown(text: str) -> str:
    """Text as the report prints it: first line only, credentials replaced, kept to one line's worth."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    safe = piiscan.redact_credentials_in_text(first)
    return safe if len(safe) <= _SHOWN_LENGTH else f"{safe[: _SHOWN_LENGTH - 3]}..."


def _authority(address: str) -> str:
    """The part of an address that names where it goes: 'user@host:port', or "" for an address that goes nowhere.

    "" for a scheme that is not a network one -- see _NETWORK_SCHEMES -- so the same words that
    keep a 'whatsapp://send' out of the host list keep it from being flagged as unknowable.
    An address with no scheme at all is a Server:Port, which is how HTTP Get is written.
    """
    text = address.strip()
    if _OPAQUE_SCHEME.match(text):
        return ""
    scheme = _SCHEME.match(text)
    if scheme and scheme.group(1).lower() not in _NETWORK_SCHEMES:
        return ""
    remainder = text[scheme.end() :] if scheme else text
    return re.split(r"[/?#]", remainder, maxsplit=1)[0].rsplit("@", 1)[-1]


def host_of(address: str) -> str:
    """The host an address goes to, lower case -- or "" when it is not known until the device runs it.

    "" for a variable anywhere in the host part ('%server/x', 'api.%env.com'), for nothing at
    all, and for an address that is not a network one.  A variable in the path is fine:
    'https://api.example.com/%id' still goes to api.example.com.
    """
    authority = _authority(address)
    host = authority[1:].split("]")[0] if authority.startswith("[") else authority.split(":")[0]
    return "" if not host or "%" in host else host.lower()


def is_local(host: str) -> bool:
    """Whether a host is on the user's own network, or is the device itself."""
    if host in _LOCAL_HOSTS or host.endswith(_LOCAL_SUFFIXES):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def _address_flags(address: str) -> list[str]:
    """What is worth a look about one address: that it is unencrypted, or that nobody can say where it goes."""
    host = host_of(address)
    if host:
        unencrypted = address.strip().lower().startswith(_PLAIN_HTTP) and not is_local(host)
        return [FLAG_PLAIN_HTTP] if unencrypted else []
    return [FLAG_VARIABLE_ADDRESS] if "%" in _authority(address) else []


def _web_addresses(kind: Kind, arguments: dict[str, str]) -> list[str]:
    """The addresses a web action goes to, as written."""
    values = [arguments.get(name, "") for name in kind.fields]
    if kind.joined:
        server, path = values
        return [f"{server.rstrip('/')}/{path.lstrip('/')}" if server and path else server or path]
    return [value for value in values if value]


def _addresses_in(action: Element) -> list[str]:
    """Every address written anywhere in an action's text, in order, each once."""
    found: list[str] = []
    for element in action.iter():
        if element is action or element.tag == "label":
            continue
        for match in _ADDRESS_IN_TEXT.findall(element.text or ""):
            if match not in found:
                found.append(match)
    return found


def _tidy_hosts(addresses: list[str]) -> tuple[list[str], list[str]]:
    """(the hosts those addresses reach, the flags they earn), each once."""
    hosts: list[str] = []
    flags: list[str] = []
    for address in addresses:
        host = host_of(address)
        if host and host not in hosts:
            hosts.append(host)
        flags.extend(flag for flag in _address_flags(address) if flag not in flags)
    return hosts, flags


def _intent_detail(arguments: dict[str, str]) -> tuple[str, list[str]]:
    """The sentence describing a Send Intent, and the addresses its Data field holds."""
    targets = lookup_values.get("877a", [])
    number = arguments.get(_INTENT_TARGET_ARGUMENT, "")
    target = targets[int(number)] if number.isdigit() and int(number) < len(targets) else "Broadcast Receiver"
    parts = [f"{target}: {arguments.get('arg0') or '(no action)'}"]
    data = arguments.get("arg3", "")
    if data:
        parts.append(f"data {data}")
    package = arguments.get("arg7", "")
    if package:
        parts.append(f"package {package}")
    return _shown(", ".join(parts)), [data] if _SCHEME.match(data) or data.startswith("%") else []


def _shell_use(arguments: dict[str, str]) -> tuple[str, str, list[str]]:
    """(category, detail, flags) for a Run Shell: ROOT when Use Root is on, and which way it is run."""
    command = _shown(arguments.get("arg0", ""))
    root = arguments.get(_ROOT_ARGUMENT, "")
    if root == "1":
        category, flags = ROOT, [FLAG_ROOT]
    elif root and root != "0":
        category, flags = SHELL, [FLAG_ROOT_VARIABLE]
    else:
        category, flags = SHELL, []
    if arguments.get(_SHIZUKU_ARGUMENT) == "1":
        command = f"(through Shizuku) {command}"
    return category, command, flags


def _use_for(kind: Kind, action: Element, where: Target, what: str) -> Use:
    """The Use one outbound action makes, with its hosts and what is worth a look about it."""
    arguments = _arguments(action)
    use = Use(where, kind.category, what, "")
    addresses: list[str] = []
    if kind.category == WEB:
        addresses = _web_addresses(kind, arguments)
        use.detail = ", ".join(_shown(address) for address in addresses) or "(Google Drive)"
    elif kind.category == INTENT:
        use.detail, addresses = _intent_detail(arguments)
    elif kind.category == PLUGIN:
        addresses = _addresses_in(action)
        use.detail = ", ".join(_shown(address) for address in addresses) or "(where it goes is set inside the plugin)"
    elif kind.category == SHELL:
        use.category, use.detail, use.flags = _shell_use(arguments)
    else:
        use.detail = ", ".join(_shown(arguments.get(name, "")) for name in kind.fields)
    hosts, flags = _tidy_hosts(addresses)
    use.hosts = hosts
    use.flags.extend(flags)
    credentials = piiscan.credentials_in_action(action)
    if credentials:
        use.flags.append(f"{FLAG_CREDENTIAL} ({', '.join(credentials)})")
    return use


def _written_address(action: Element, where: Target, what: str) -> Use | None:
    """The Use for an action that is not outbound itself but has an address written in it, or None."""
    addresses = _addresses_in(action)
    if not addresses:
        return None
    hosts, _flags = _tidy_hosts(addresses)
    shown = ", ".join(_shown(address) for address in addresses[:3])
    more = len(addresses) - 3
    return Use(where, ADDRESS, what, f"{shown}{f' and {more} more' if more > 0 else ''}", hosts)


def _action_use(action: Element, where: Target) -> Use | None:
    """The Use an action makes, or None if it neither reaches outside nor names an address."""
    code = (action.findtext("code") or "").strip()
    what = item_name(code, "t")
    kind = _KINDS.get(code)
    use = _use_for(kind, action, where, what) if kind else _written_address(action, where, what)
    if use is not None and action.find("on") is not None:
        # <on> present is how Tasker records an action that is turned off -- see taskflow.
        use.enabled = False
    return use


# ##################################################################################
# Walking the configuration.
# ##################################################################################
def _task_owners(state: RunState) -> dict[str, str]:
    """{Task id: owning Project name}, as proflint._project_owners does and for its reason."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext("tids") or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def outbound_uses(state: RunState) -> list[Use]:
    """Every action in the loaded configuration that reaches outside, or has an address written in it.

    In Project order and then the order the Map numbers the actions, so a Use's position in
    the list is its position on the screen.  Safe to call with nothing loaded: an empty list.
    """
    owners = _task_owners(state)
    uses: list[Use] = []
    for task_id, task in state.tasker_root_elements["all_tasks"].items():
        base = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        for number, action in enumerate(actions_in_map_order(task["xml"]), start=1):
            use = _action_use(action, base.at_action(number))
            if use is not None:
                uses.append(use)
    return uses


# ##################################################################################
# The report.
# ##################################################################################
_REPORT_WIDTH = 78
_NO_PROJECT = ""


def _current_xml_file(state: RunState) -> str:
    """The path of the XML file being read (see taskflow._current_xml_file)."""
    file_to_get = state.file_to_get
    path = getattr(file_to_get, "name", file_to_get) if file_to_get else ""
    return path if isinstance(path, str) and path else "(unknown)"


def _heading(title: str) -> list[Row]:
    return [Row(title), Row("-" * _REPORT_WIDTH)]


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _summary_rows(running: list[Use]) -> list[Row]:
    """One line per kind of outbound action: how many, and how many hosts they reach."""
    rows = _heading("SUMMARY")
    for category, title in CATEGORY_TITLES.items():
        mine = [use for use in running if use.category == category]
        if not mine:
            continue
        hosts = {host for use in mine for host in use.hosts}
        reach = f"   {_plural(len(hosts), 'host')}" if hosts else ""
        rows.append(Row(f"  {title:<34}{_plural(len(mine), 'action'):>12}{reach}"))
    return [*rows, Row("")]


def _look_rows(running: list[Use]) -> list[Row]:
    """The actions with something flagged on them, each with where it is and why."""
    flagged = [use for use in running if use.needs_a_look]
    if not flagged:
        return []
    rows = _heading(f"NEEDS A LOOK -- {_plural(len(flagged), 'action')}")
    for use in flagged:
        rows += [
            Row(f"  {use.where.label}", use.where),
            Row(f"      {use.what}: {use.detail}"),
            Row(f"      Why: {'; '.join(use.flags)}."),
        ]
    return [*rows, Row("")]


def _host_note(host: str, uses: list[Use]) -> str:
    notes: list[str] = []
    if is_local(host):
        notes.append("your own network")
    if any(FLAG_PLAIN_HTTP in use.flags for use in uses):
        notes.append("plain http")
    return f"  [{', '.join(notes)}]" if notes else ""


def _host_rows(running: list[Use]) -> list[Row]:
    """Every host the configuration goes to, with how many places go there and the first of them."""
    by_host: dict[str, list[Use]] = {}
    for use in running:
        for host in use.hosts:
            by_host.setdefault(host, []).append(use)
    if not by_host:
        return []
    rows = _heading(f"HOSTS CONTACTED -- {len(by_host)}")
    for host, uses in sorted(by_host.items(), key=lambda item: (-len(item[1]), item[0])):
        projects = {use.where.project for use in uses}
        where = f"{_plural(len(uses), 'place')} in {_plural(len(projects), 'Project')}"
        rows.append(Row(f"  {host}   {where}{_host_note(host, uses)}", uses[0].where))
    return [*rows, Row("")]


def _use_row(use: Use) -> Row:
    off = "   (turned off)" if not use.enabled else ""
    why = f"   !! {'; '.join(use.flags)}" if use.flags and use.enabled else ""
    return Row(f"      action {use.where.action}  {use.what}: {use.detail}{why}{off}", use.where)


def _by_project(uses: list[Use]) -> dict[str, dict[str, list[Use]]]:
    """{Project name: {Task id: its uses}}, Projects by name and the Tasks that have none last."""
    grouped: dict[str, dict[str, list[Use]]] = {}
    for use in uses:
        grouped.setdefault(use.where.project, {}).setdefault(use.where.key, []).append(use)
    ordered = sorted(grouped, key=lambda name: (name == _NO_PROJECT, name.casefold()))
    return {name: grouped[name] for name in ordered}


def _project_rows(uses: list[Use]) -> list[Row]:
    """Everything, Project by Project and Task by Task -- the answer to "what does this Project do"."""
    if not uses:
        return []
    rows = _heading("BY PROJECT")
    for project, tasks in _by_project(uses).items():
        count = sum(len(task_uses) for task_uses in tasks.values())
        if project == _NO_PROJECT:
            rows.append(Row(f"Not in any Project   ({_plural(count, 'action')})"))
        else:
            rows.append(Row(f"Project '{project}'   ({_plural(count, 'action')})", Target(PROJECT, project, project)))
        for task_uses in tasks.values():
            first = task_uses[0].where
            rows.append(Row(f"    Task '{first.name}'", first.at_action(0)))
            rows.extend(_use_row(use) for use in task_uses)
        rows.append(Row(""))
    return rows


def _written_rows(written: list[Use]) -> list[Row]:
    """Addresses written into actions that do not themselves go online -- where a later request may be aimed."""
    if not written:
        return []
    rows = _heading(f"ADDRESSES WRITTEN IN OTHER ACTIONS -- {len(written)}")
    rows.append(Row("  Not contacted by these actions themselves, but a Variable Set holding a"))
    rows.append(Row("  server is usually how a later request reaches it."))
    for use in written:
        off = "   (turned off)" if not use.enabled else ""
        rows.append(Row(f"  {use.where.label}: {use.what}: {use.detail}{off}", use.where))
    return [*rows, Row("")]


def _limitations() -> list[Row]:
    """The closing note on what the inventory cannot see, for healthck's reason: silence has to be readable."""
    return [
        Row("NOTE ON WHAT IS NOT LISTED"),
        Row("-" * _REPORT_WIDTH),
        Row("Which actions count as reaching outside is a list of Tasker's action codes; an"),
        Row("action that does something to the outside world and is not on it is missed."),
        Row("An address built from a variable is shown as written and flagged, never guessed"),
        Row("at.  A plugin's own settings are read only for addresses written in them, so"),
        Row("where else a plugin goes is its own business.  Profile conditions, Scenes and"),
        Row("Tasker's own preferences are not read.  Keys and passwords found in an address"),
        Row("or command are replaced in this report, which makes it safer to share than the"),
        Row("backup but not safe without a read: a secret with no recognizable shape is not"),
        Row("found.  Phone numbers and email addresses are destinations and are left in."),
        Row(""),
    ]


def run_outbound_inventory(state: RunState) -> tuple[list[Row], dict[str, int]]:
    """Read every Task and return (report rows, counts).

    The counts are by category for the actions that will run, plus "flagged" for those worth a
    look and "total" for all of them.  Rows rather than finished text, for healthck's reason:
    the caller saves them as plain text and shows them as HTML, and the two must be one report.
    Actions that are turned off are listed where they sit and counted nowhere -- they do not run.
    """
    uses = outbound_uses(state)
    outbound = [use for use in uses if use.category != ADDRESS]
    written = [use for use in uses if use.category == ADDRESS]
    running = [use for use in outbound if use.enabled]

    counts = {category: sum(use.category == category for use in running) for category in CATEGORY_TITLES}
    counts["flagged"] = sum(use.needs_a_look for use in running)
    counts["total"] = len(running)

    tasks = state.tasker_root_elements["all_tasks"]
    rows = [
        Row("MapTasker Outbound Inventory"),
        Row("=" * _REPORT_WIDTH),
        Row(f"XML file:    {_current_xml_file(state)}"),
        Row(f"Generated:   {clock.now().strftime('%d-%b-%Y %H:%M:%S')}"),
        Row(f"Version:     {MY_VERSION}"),
        Row(""),
        Row(f"Scanned:     {_plural(len(tasks), 'Task')}"),
        Row(f"Found:       {_plural(counts['total'], 'action')} that reach outside, {counts['flagged']} worth a look"),
        Row(""),
    ]
    if not outbound and not written:
        return [
            *rows,
            Row("Nothing to report -- no action sends a request, a message, a call, a command"),
            Row("or an Intent, and no address is written into any action."),
            Row(""),
            *_limitations(),
        ], counts
    body = [
        *_summary_rows(running),
        *_look_rows(running),
        *_host_rows(running),
        *_project_rows(outbound),
        *_written_rows(written),
    ]
    return [*rows, *body, *_limitations()], counts


def write_outbound_report(rows: list[Row], state: RunState) -> str:
    """Write the inventory to a timestamped file in the output folder.

    Returns the path written, or "" if the write failed -- named, stamped and handled exactly
    as taskflow.write_task_flow_report does, and for its reasons.
    """
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(OUTBOUND_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Outbound Inventory could not be written: {error}")
        return ""
    return file_path
