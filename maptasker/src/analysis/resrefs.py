"""resrefs: the files, folders, images, sounds, Scenes and apps a configuration's actions refer to -- and which are gone."""

#! /usr/bin/env python3

#                                                                                        #
# resrefs: what a configuration points at outside itself, and what the last check of the  #
#          phone said about it.                                                           #
#                                                                                        #
# A Task that opens a file, plays a sound, shows a Scene or launches an app does not say  #
# so loudly when the thing is gone.  Tasker skips the action, or fails it with an error  #
# the Task may be set to ignore, and a configuration restored onto a new phone -- or one  #
# whose files were tidied up a year ago -- runs with holes in it and nothing says where.  #
# The backup names every one of these; whether they are THERE is a fact about a phone.   #
#                                                                                        #
# So this is two halves with a store between them (see resstore):                         #
#                                                                                        #
#   this module   reads the configuration for what it refers to (collect), and reads the   #
#                 stored answers for what the phone said (missing, lint_problems).        #
#   deviceresource   asks the phone, and writes the answers down.                         #
#                                                                                        #
# Same contract as healthck.py and plugchk.py: reads PrimeItems.tasker_root_elements and    #
# the stored answers, never contacts anything -- so the Health Check does not wait on the  #
# network, and says when the answers it is using were given.                              #
#                                                                                        #
# WHAT IS COLLECTED, AND WHY IT IS A HAND-KEPT TABLE                                        #
#                                                                                        #
# Tasker's published action table says an argument is a file (spec 'f'), but not whether  #
# the file must EXIST: Write File, Record Audio and Copy File's destination take a path   #
# for something about to be made, and calling those missing would be wrong every time.     #
# So _ARGUMENTS names, by action code, only the inputs: arguments the action reads, plays, #
# opens, shows or launches, and that fail or do nothing when absent.                       #
#                                                                                        #
# WHAT IS NOT CHECKED, AND IS SAID SO                                                       #
#                                                                                        #
# A value that holds a %variable, a wildcard, or a web or content address cannot be asked  #
# of a file system; it is listed as not checked, with the reason, rather than dropped.      #
# A ringtone is chosen by title on one phone and by URI on another, and an icon may be one  #
# of Tasker's built-ins: neither is a path, and neither is guessed at.  Scene elements'     #
# own images and a plugin's files are inside payloads this module does not read.            #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from maptasker.src.analysis import plugchk
from maptasker.src.core import appinv, clock, resstore
from maptasker.src.core.actionc import action_codes
from maptasker.src.core.mapjump import PROFILE, TASK, Row, Target, actions_in_map_order, text_report
from maptasker.src.core.maputils import append_to_filename
from maptasker.src.core.outdir import output_path
from maptasker.src.core.sysconst import RESOURCES_FILE, logger

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from maptasker.src.core.primitem import RunState

# What a reference is to.
FILE = "file"
FOLDER = "folder"
PATH = "file or folder"
IMAGE = "image"
SOUND = "sound"
SCENE = "Scene"
APP = "app"

# What is actually asked, which is coarser: a path exists or it does not, whatever it was meant to be.
ASK_PATH = "path"
ASK_APP = "app"
ASK_SCENE = "scene"
_ASKED = {
    FILE: ASK_PATH,
    FOLDER: ASK_PATH,
    PATH: ASK_PATH,
    IMAGE: ASK_PATH,
    SOUND: ASK_PATH,
    SCENE: ASK_SCENE,
    APP: ASK_APP,
}

WARNING = "WARNING"
MISSING = "RESOURCE-MISSING"
TAGS = frozenset({MISSING})

# How many of the places using a missing resource its finding names before "and N more".
_PLACES_NAMED = 5

# ##################################################################################
# Which arguments are inputs.  Action code -> argument id -> what it refers to.
# ##################################################################################

_FILE_ARGUMENTS: dict[str, dict[str, str]] = {
    "111": {"3": FILE},  # Compose MMS, Attachment
    "404": {"0": FILE},  # Copy File, From
    "405": {"0": FOLDER},  # Copy Dir, From
    "400": {"0": PATH},  # Move, From
    "475": {"0": FILE},  # GZip
    "476": {"0": FILE},  # GUnzip
    "420": {"0": FILE},  # Zip, the file to add
    "422": {"0": FILE},  # UnZip
    "446": {"1": PATH},  # Get Files/Folders Properties, Path
    "131": {"0": FILE},  # JavaScript, Path
    "412": {"0": FOLDER},  # List Files, Directory
    "900": {"0": FOLDER},  # Browse Files, Directory
    "102": {"0": FILE},  # Open File
    "376": {"0": FILE},  # Share File
    "415": {"0": FILE},  # Read Line
    "416": {"0": FILE},  # Read Paragraph
    "417": {"0": FILE},  # Read File
    "776": {"0": FILE},  # Read Binary
    "445": {"0": SOUND},  # Music Play, File
    "447": {"0": FOLDER},  # Music Play Dir, Directory
    "523": {"9": SOUND},  # Notify, Sound File
    "538": {"4": SOUND},  # Notify Sound, Sound File
}

_IMAGE_ARGUMENTS: dict[str, dict[str, str]] = {
    "414": {"1": IMAGE},  # Get Pixel Colors, Image
    "15": {"5": IMAGE},  # Lock, Background Image
    "551": {"1": IMAGE},  # Menu, Background Image
    "550": {"2": IMAGE},  # Popup, Background Image
    "552": {"5": IMAGE},  # Popup Task Buttons, Background Image
    "595": {"4": IMAGE},  # Variable Query, Background Image
    "109": {"1": IMAGE},  # Set Wallpaper, Image
    "105": {"2": IMAGE},  # Set Clipboard, Image
    "377": {"8": IMAGE},  # Text/Image Dialog, Image
    "548": {"4": IMAGE},  # Flash, Icon
    "188": {"0": IMAGE},  # Load Image, Source
    "66": {"2": IMAGE},  # Element Image, Image
    "60": {"8": IMAGE},  # Element Add GeoMarker, Icon
    "523": {"2": IMAGE},  # Notify, Icon
    "525": {"2": IMAGE},  # Notify LED, Icon
    "536": {"2": IMAGE},  # Notify Vibrate, Icon
    "538": {"2": IMAGE},  # Notify Sound, Icon
    "157": {"1": IMAGE},  # Quick Setting Add, Icon
    "138": {"0": IMAGE},  # Set Tasker Icon
    "152": {"1": IMAGE},  # Set Widget Icon
    "413": {"3": IMAGE},  # Request Add Tile, Icon
    "162": {"7": IMAGE},  # Set up Quick Setting Tile, Icon
}

# Every Scene an action acts on (Create/Show/Hide/Destroy/Test Scene and the Element actions, all of which take
# the Scene's name as their first argument), and the layouts that name one.
_SCENE_ACTIONS = (
    "46",
    "47",
    "48",
    "49",
    "143",
    "195",
    "194",
    "50",
    "51",
    "53",
    "54",
    "55",
    "56",
    "57",
    "58",
    "60",
    "63",
    "64",
    "65",
    "66",
    "67",
    "68",
    "69",
    "71",
    "73",
    "612",
)
_SCENE_ARGUMENTS: dict[str, dict[str, str]] = {code: {"0": SCENE} for code in _SCENE_ACTIONS} | {
    "941": {"1": SCENE},  # HTML Popup, Layout
    "15": {"6": SCENE},  # Lock, Layout
    "551": {"2": SCENE},  # Menu, Layout
    "550": {"3": SCENE},  # Popup, Layout
    "552": {"6": SCENE},  # Popup Task Buttons, Layout
    "595": {"5": SCENE},  # Variable Query, Layout
}

# Apps: the <App> pickers, and the package named as plain text.
_APP_ARGUMENTS: dict[str, dict[str, str]] = {
    "20": {"0": APP},  # Launch App
    "18": {"0": APP},  # Kill App
    "104": {"1": APP},  # Browse URL
    "379": {"2": APP},  # Device Admin/Owner
    "443": {"2": APP},  # Media Control
    "173": {"1": APP},  # Network Access
    "252": {"0": APP},  # Set SMS App
    "216": {"0": APP},  # App Settings
    "352": {"4": APP},  # Get Network Data Usage
    "25": {"1": APP},  # Go Home
}


def _merged(*tables: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """The tables as one: action code -> argument id -> what it refers to."""
    merged: dict[str, dict[str, str]] = {}
    for table in tables:
        for code, arguments in table.items():
            merged.setdefault(code, {}).update(arguments)
    return merged


_ARGUMENTS = _merged(_FILE_ARGUMENTS, _IMAGE_ARGUMENTS, _SCENE_ARGUMENTS, _APP_ARGUMENTS)

# Image and sound arguments are often a name rather than a path -- one of Tasker's own icons, a ringtone's
# title.  Only a value that looks like a path or a file name is taken to be one.
_FILE_NAME = re.compile(r"\.[A-Za-z0-9]{2,5}$")
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]+://")
_PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")

# ##################################################################################
# What is found.
# ##################################################################################


@dataclass(frozen=True)
class Reference:
    """One place an action or Profile refers to something: what, as written, and where."""

    kind: str
    value: str
    where: Target
    used_by: str  # "Launch App", "Profile App context"
    argument: str = ""  # "File", "Package/App Name"

    @property
    def question(self) -> resstore.Question:
        """What would be asked of a phone: (what sort of thing, its name)."""
        return _ASKED[self.kind], self.value


@dataclass(frozen=True)
class Skipped:
    """A reference that cannot be asked about, and why."""

    kind: str
    value: str
    where: Target
    reason: str


@dataclass
class References:
    """Everything collect() found: what can be asked about, and what cannot."""

    found: list[Reference] = field(default_factory=list[Reference])
    skipped: list[Skipped] = field(default_factory=list[Skipped])

    def questions(self) -> dict[resstore.Question, list[Reference]]:
        """{question: every place that asks it}, in the order first met."""
        asked: dict[resstore.Question, list[Reference]] = {}
        for reference in self.found:
            asked.setdefault(reference.question, []).append(reference)
        return asked


def _owners(kind: str, state: RunState) -> dict[str, str]:
    """{member id: owning Project name} for one of a Project's lists (see plugchk._owners)."""
    owners: dict[str, str] = {}
    for project_name, project in state.tasker_root_elements["all_projects"].items():
        for member in (item.strip() for item in (project["xml"].findtext(kind) or "").split(",")):
            if member:
                owners[member] = project_name
    return owners


def _text(element: Element) -> str:
    """An argument's value, whichever element holds it."""
    if element.tag == "Int":
        return (element.findtext("var") or element.attrib.get("val", "")).strip()
    return (element.text or "").strip()


def _argument_element(action: Element, arg_id: str) -> Element | None:
    """The element holding one argument of an action, by its sr="argN"."""
    wanted = f"arg{arg_id}"
    return next((child for child in action if child.attrib.get("sr") == wanted), None)


def _argument_name(code: str, arg_id: str) -> str:
    """What Tasker calls an argument -- "File", "Package/App Name" -- or "" if it does not say."""
    entry = action_codes.get(f"{code}t")
    if entry is None:
        return ""
    return next((arg.arg_name for arg in entry.args if arg.arg_id == arg_id), "")


def _judge(kind: str, value: str) -> tuple[str, str]:
    """Whether a value can be asked about: ("ask", the value to ask), ("skip", why not) or ("ignore", "").

    "ignore" is for a value that was never a path to begin with -- a Tasker icon's name, a ringtone's title --
    which is not worth listing as unchecked because there was never anything to check.
    """
    if not value:
        return "ignore", ""
    if "%" in value:
        return "skip", "it is built from a variable, whose value is only known when the action runs"
    if kind == SCENE:
        return "ask", value
    if kind == APP:
        return ("ask", value) if _PACKAGE.fullmatch(value) else ("ignore", "")
    if value.startswith("file://"):
        value = value.removeprefix("file://")
    if _URI.match(value):
        return "skip", "it is a web or content address, not a file on the phone"
    if "*" in value or "?" in value:
        return "skip", "it contains a wildcard"
    if kind in (IMAGE, SOUND) and "/" not in value and not _FILE_NAME.search(value):
        return "ignore", ""
    return "ask", value


def _values(element: Element, kind: str) -> list[tuple[str, str]]:
    """[(kind, value)] an argument element names.  An <App> may name several; an <Img> may be an app's icon."""
    if element.tag == "App":
        return [(APP, entry.pkg) for entry in appinv.read_app_element(element)]
    if element.tag == "Img":
        icon = appinv.read_icon_element(element)
        if icon is None:
            return []
        if icon.kind == "var":
            return [(kind, icon.name)]
        if icon.kind in ("app", "pack"):
            return [(APP, icon.pkg)]
        # A built-in icon is a name; a file is a path.
        return [(kind, icon.name)]
    return [(kind, _text(element))]


def _note(result: References, where: Target, used_by: str, argument: str, kind: str, value: str) -> None:
    """Sort one found value into what can be asked and what cannot."""
    verdict, text = _judge(kind, value)
    if verdict == "ask":
        result.found.append(Reference(kind, text, where, used_by, argument))
    elif verdict == "skip":
        result.skipped.append(Skipped(kind, value, where, text))


def _action_references(result: References, action: Element, where: Target) -> None:
    """Every reference one action makes."""
    code = action.findtext("code") or ""
    arguments = _ARGUMENTS.get(code)
    if not arguments:
        return
    used_by = plugchk.item_name(code, "t")
    for arg_id, kind in arguments.items():
        element = _argument_element(action, arg_id)
        if element is None:
            continue
        name = _argument_name(code, arg_id)
        for found_kind, value in _values(element, kind):
            _note(result, where, used_by, name, found_kind, value)


def _profile_references(result: References, state: RunState) -> None:
    """The apps a Profile's Application contexts name."""
    owners = _owners("pids", state=state)
    for profile_id, profile in state.tasker_root_elements["all_profiles"].items():
        where = Target(PROFILE, profile_id, profile["name"], owners.get(profile_id, ""))
        for context in profile["xml"]:
            if context.tag != "App":
                continue
            for entry in appinv.read_app_condition_entries(context):
                _note(result, where.with_text("App context"), "Application context", "App", APP, entry.pkg)


def collect(state: RunState) -> References:
    """Everything the Tasks and Profiles refer to that can be looked for on a phone, and what cannot.

    Task actions in the order the Map numbers them, then Profile Application contexts.  A Scene element's inline
    Task is not walked, for plugchk's reason: the Map gives those actions no anchor to jump to.  Safe to call
    with nothing loaded.
    """
    result = References()
    root = state.tasker_root_elements
    if not root:
        return result

    owners = _owners("tids", state=state)
    for task_id, task in root["all_tasks"].items():
        where = Target(TASK, task_id, task["name"], owners.get(task_id, ""))
        for number, action in enumerate(actions_in_map_order(task["xml"]), start=1):
            _action_references(result, action, where.at_action(number))
    _profile_references(result, state=state)
    return result


# ##################################################################################
# What the phone said.
# ##################################################################################


@dataclass(frozen=True)
class Gone:
    """One thing that was asked about and is not there: every place that uses it, and who said so."""

    question: resstore.Question
    uses: list[Reference]
    said_by: dict[str, str]  # {device: when it was checked}


def missing(references: References, answers: resstore.Answers | None = None) -> list[Gone]:
    """What the configuration refers to that no device which was asked has.

    Reported only when every device that answered the question said no: the backup does not say which phone it
    came from, and a file on the tablet checked last month may be exactly where this configuration runs.  A
    question no device has answered is not missing, it is unchecked (see unchecked).
    """
    known = resstore.answers() if answers is None else answers
    gone: list[Gone] = []
    for question, uses in references.questions().items():
        replies = {device: (when, found[question]) for device, (when, found) in known.items() if question in found}
        if replies and not any(present for _, present in replies.values()):
            gone.append(Gone(question, uses, {device: when for device, (when, _) in replies.items()}))
    return gone


def unchecked(references: References, answers: resstore.Answers | None = None) -> int:
    """How many distinct things the configuration refers to that no device has been asked about."""
    known = resstore.answers() if answers is None else answers
    return sum(1 for question in references.questions() if not any(question in found for _, found in known.values()))


def describe(kind: str, value: str) -> str:
    """A reference as a sentence names it: "file '/sdcard/x.png'", "Scene 'Panel'", "app com.example"."""
    return f"{kind} {value}" if kind == APP else f"{kind} '{value}'"


def _detail(gone: Gone) -> list[tuple[str, Target | None]]:
    """The finding's detail line: who said it was not there, and where it is used."""
    said = ", ".join(f"{device} on {when}" if when else device for device, when in gone.said_by.items())
    count = len(gone.uses)
    things = "the one place that uses it" if count == 1 else f"all {count} places that use it"
    pieces: list[tuple[str, Target | None]] = [
        (f"Not on {said}, so {things} will not find it when run: ", None),
    ]
    for position, use in enumerate(gone.uses[:_PLACES_NAMED]):
        if position:
            pieces.append(("; ", None))
        pieces.append((f"{use.where.label} ({use.used_by})", use.where))
    left = count - _PLACES_NAMED
    pieces.append((f"; and {left} more." if left > 0 else ".", None))
    return pieces


def lint_problems(state: RunState) -> list[plugchk.Problem]:
    """One finding per thing the configuration refers to and the phone does not have.

    Nothing at all when no device has been checked: with nothing to go on, every file would be "missing", which
    is not what anyone needs told.  healthck says instead that the check did not run (see resources_unchecked).
    Safe to call with nothing loaded.
    """
    answers = resstore.answers()
    if not answers:
        return []
    problems: list[plugchk.Problem] = []
    for gone in missing(collect(state=state), answers):
        sentence = describe(gone.uses[0].kind, gone.question[1])
        problems.append(
            plugchk.Problem(
                WARNING,
                MISSING,
                f"{sentence[0].upper()}{sentence[1:]}",
                gone.uses[0].where,
                _detail(gone),
                [use.where for use in gone.uses[1:]],
            ),
        )
    return problems


def resources_unchecked(state: RunState) -> int:
    """How many distinct things the configuration refers to, when no device has been asked about any of them.

    0 when a check has been made (it ran) or there is nothing to check.  healthck prints a note when this is not
    0, so a report with no RESOURCE-MISSING in it cannot be read as "everything is there" when nothing was asked.
    """
    if resstore.answers():
        return 0
    return len(collect(state=state).questions())


# ##################################################################################
# The report.
# ##################################################################################


def _checked_line(answers: resstore.Answers) -> str:
    """Which devices the answers came from, and when."""
    if not answers:
        return "No device has been checked yet."
    return "Checked against " + ", ".join(
        f"{device} on {when}" if when else device for device, (when, _) in answers.items()
    )


def report_rows(
    references: References, answers: resstore.Answers | None = None, errors: list[str] | None = None
) -> list[Row]:
    """The check as mapjump Rows: what is missing and where it is used, what could not be asked, and what was not.

    Rows rather than a string so the report is clickable in the Map the way a health-check finding is: going to
    look at the action is how you decide whether the file is worth putting back.  Missing first, because it is
    the answer; the things that could not be checked next, because a clean "missing" list is only as good as
    what was asked.
    """
    known = resstore.answers() if answers is None else answers
    gone = missing(references, known)
    asked = references.questions()
    rows: list[Row] = [Row("Missing resources"), Row(_checked_line(known)), Row("")]
    rows.extend(Row(f"  Problem: {error}") for error in errors or [])
    if errors:
        rows.append(Row(""))

    if known:
        present = sum(1 for question in asked if any(found.get(question) for _, found in known.values()))
        rows.append(Row(f"{len(asked)} different things are used; {present} found, {len(gone)} missing."))
        rows.append(Row(""))

    if gone:
        rows.append(Row(f"MISSING ({len(gone)})"))
        for item in gone:
            rows.append(Row(f"  {describe(item.uses[0].kind, item.question[1])}"))
            rows.extend(
                Row(
                    f"      {use.where.label} -- {use.used_by}{f' ({use.argument})' if use.argument else ''}", use.where
                )
                for use in item.uses
            )
        rows.append(Row(""))
    elif known:
        rows.extend((Row("Nothing is missing."), Row("")))

    never = unchecked(references, known)
    if known and never:
        rows.append(Row(f"{never} thing(s) were not answered by any device checked, so are neither found nor missing."))
        rows.append(Row(""))

    if references.skipped:
        rows.append(Row(f"NOT CHECKED ({len(references.skipped)}) -- these cannot be asked of a file system"))
        for skip in references.skipped:
            rows.append(Row(f"  {skip.where.label}", skip.where))
            rows.append(Row(f"      {describe(skip.kind, skip.value)}: {skip.reason}."))
    return rows


def write_report(rows: list[Row], state: RunState) -> str:
    """Save the report as text, the way the other reports are saved.  Returns the file name, or "" on failure."""
    stamp = clock.now().strftime("_%m-%d-%Y_%H-%M-%S")
    file_name = append_to_filename(RESOURCES_FILE, stamp)
    if not file_name:
        return ""
    file_path = output_path(file_name, state=state)
    try:
        with open(file_path, "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Missing Resources report could not be written: {error}")
        return ""
    return file_path
