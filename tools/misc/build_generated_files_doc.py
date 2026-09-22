#! /usr/bin/env python3

#                                                                                      #
# build_generated_files_doc: build the "Generated Output Files" reference page          #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
"""Generate the MapTasker generated-output-files reference page.

Every file MapTasker writes is named in the source, and almost all of them are named
in one place: the constants at the top of 'sysconst.py'.  Keeping a second,
hand-written list of them in a markdown page means the page is wrong the day a
command starts saving something new -- which is how 'maptasker_projects.txt' came to
be documented long after the code had renamed it.  So this reads the names straight
out of the source with the ``ast`` module and writes the page from what it finds.
Nothing is imported and no GUI is started, so it runs anywhere the source tree does.

Four things are discovered, none of them by guessing at text:

* the filename constants in 'sysconst.py', with the comment above each one -- that
  comment is the author's own explanation and is used as the description when the
  table below has nothing better to say;
* which of those constants get a date and time stamped into them, by following
  'maputils.append_to_filename' back to its callers, including the one level of
  indirection used by 'diffload.write_comparison_report' and 'taskflow._write';
* the '_..._WRITE_PATH' constants in 'deviceinv.py', which are the files MapTasker
  has Tasker write on the Android device;
* filename literals anywhere else in the source -- 'MapTasker.html' and the debug
  log are written where they are used rather than declared in 'sysconst.py'.

What the source cannot say is what a file is *for*, so that prose lives in
DESCRIPTIONS below, keyed by filename.  A file found in the source with no entry
there is still listed -- an undocumented output file is exactly what the reader
needs to be told about -- but it is marked on the page and reported at the end of
the run, so the gap is a list to work through rather than a silent omission.

XML is out of scope, as are the compressed XML snapshots in the Timeline folder:
see EXCLUDED_SUFFIXES.

It lives in 'tools/misc' and finds the source, and writes the page, wherever it is
run from::

    python tools/misc/build_generated_files_doc.py           # write the page
    python tools/misc/build_generated_files_doc.py --stats   # ... and report what it found
    python tools/misc/build_generated_files_doc.py --check   # don't write; fail if stale
    python tools/misc/build_generated_files_doc.py --print   # write nothing, show the page

'--check' rebuilds the page in memory and compares it with the one on disk, exiting
non-zero if they differ.  That is the form for a CI job: it fails when someone adds
an output file and does not rerun this.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ##################################################################################
# Configuration
# ##################################################################################
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
SOURCE_DIR = PROJECT_ROOT / "maptasker" / "src"
SYSCONST = SOURCE_DIR / "sysconst.py"
DEVICE_MODULE = SOURCE_DIR / "deviceinv.py"
OUTPUT_PAGE = HERE / "generated_output_files.md"

# The helper that turns 'MapTasker_Find.txt' into 'MapTasker_Find_date_time.txt', and
# the suffix it is given here to show that on the page.
STAMP_HELPER = "append_to_filename"
STAMP_SUFFIX = "_date_time"

# XML is excluded, as is the Timeline folder's '.xml.gz', which is XML in a coat.
EXCLUDED_SUFFIXES = (".xml", ".xml.gz")

# What counts as a filename when a bare string literal is found in the source.  Narrow
# on purpose: 'maptasker' in some prose sentence is not a file, and a suffix this does
# not list is not picked up at all, so a new kind of output file has to be added here
# before it can appear on the page.
FILENAME_SUFFIXES = (".txt", ".html", ".json", ".toml", ".log", ".pkl", ".md", ".pdf")

# Where the files go.  Spelled out once here because the page repeats it in every row.
CURRENT = "Current folder"
CONFIG = "Settings folder"
DEVICE = "Android device, 'Tasker/'"

# The order sections appear on the page, and the note under each heading.
SECTIONS: list[tuple[str, str]] = [
    ("Views", "The map and the diagram themselves, and what the 'Export' button writes."),
    ("Reports", "One per command that saves its results.  Each is stamped with the date and time it was written, so a run never overwrites the one before it."),
    ("Settings and remembered state", "What MapTasker carries from one run to the next.  Deleting any of these costs you the setting, not the configuration."),
    ("Folders", "Written beside the files above, in the current folder."),
    ("Android", "Written on the device by the Tasker helper Tasks, and read back by MapTasker over the HTTP API."),
    ("Diagnostics", "Only written when something is being looked into."),
]

# ##################################################################################
# What the source cannot say: what each file is for.
#
# 'section' places the file on the page; 'produced_by' is the command or the runtime
# option that writes it; 'note' is the description.  A file with no entry here is
# still listed, under UNDESCRIBED_SECTION, and reported at the end of the run.
# ##################################################################################
UNDESCRIBED_SECTION = "Reports"
UNDESCRIBED_NOTE = "_Not yet described -- see build_generated_files_doc.py._"

DESCRIPTIONS: dict[str, dict[str, str]] = {
    # -- Views ---------------------------------------------------------------------
    "MapTasker.html": {
        "section": "Views",
        "location": CURRENT,
        "produced_by": "Every run that displays the map",
        "note": "The mapping of your Tasker configuration.  It is opened in your default browser as a new tab.",
    },
    "MapTasker_Map.txt": {
        "section": "Views",
        "location": CURRENT,
        "produced_by": "The Diagram view, or the '-outline' runtime option",
        "note": "A textual diagram of the configuration, displayed in your default text editor.  Turn text wrapping off and use a monospace font when viewing it, or the columns will not line up.",
    },
    "MapTasker_Map_Export": {
        "section": "Views",
        "location": CURRENT,
        "produced_by": "Map view > Export",
        "note": "The Map view exported as Markdown, JSON or PDF, one file per format.",
    },
    "MapTasker_Diagram_Export": {
        "section": "Views",
        "location": CURRENT,
        "produced_by": "Diagram view > Export",
        "note": "The Diagram view exported as Markdown, JSON or PDF, one file per format.",
    },
    # -- Reports -------------------------------------------------------------------
    "MapTasker_HealthCheck.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Health Check'",
        "note": "What the check found wrong with the configuration.",
    },
    "MapTasker_Fix.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Fix Findings'",
        "note": "What the repairs changed.  Kept apart from the Health Check report because that one says what is wrong and this one says what was done about it.",
    },
    "MapTasker_Find.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Find' > 'Save Results'",
        "note": "The saved results of a search.",
    },
    "MapTasker_Replace.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Find' > 'Replace'",
        "note": "The preview of a replacement: what would change, before anything does.",
    },
    "MapTasker_Refactor.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Refactor'",
        "note": "The preview a refactoring operation was applied from, or declined.",
    },
    "MapTasker_Analysis.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Run (AI) Analysis'",
        "note": "The analysis the AI model returned for your configuration.",
    },
    "MapTasker_Compare.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Compare Files'",
        "note": "What differs between two configurations.",
    },
    "MapTasker_Timeline.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Timeline'",
        "note": "What has changed in your own configuration since an earlier snapshot.  It is the comparison report under another name, so that 'what changed since Tuesday' does not land on top of a comparison of two separate files.",
    },
    "MapTasker_VarXref.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Variables Xref'",
        "note": "Every variable, and everywhere it is set and read.",
    },
    "MapTasker_TaskFlow.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Task Flow'",
        "note": "Every Task's If/Else/For/Goto structure, linted.",
    },
    "MapTasker_Flowchart.txt": {
        "section": "Reports",
        "location": CURRENT,
        "produced_by": "'Task Flow'",
        "note": "The flowchart drawn for a single Task.",
    },
    # -- Settings and remembered state ----------------------------------------------
    "MapTasker_Settings.toml": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "Every run",
        "note": "Your saved program settings.  You can edit it, but do not change a field's format -- an integer turned into a text string, say.  Incorrect values are ignored.",
    },
    "MapTasker_Apps.json": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "'App not listed?'",
        "note": "The Application list fetched from the device, kept between runs and keyed by device.  Nothing is lost if you delete it; it is fetched again.",
    },
    "MapTasker_API_Keys.json": {
        "section": "Settings and remembered state",
        "location": CONFIG,
        "produced_by": "Saving an AI API key",
        "note": "Only written on a machine with no system password store.  Otherwise the keys go to the Keychain on macOS, Credential Manager on Windows, and GNOME Keyring or KWallet on Linux, and this file is never created.",
    },
    ".MapTasker_RunCount.txt": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "Every run",
        "note": "How many times MapTasker has been run.  Hidden.",
    },
    ".maptasker_last_run.txt": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "Every run",
        "note": "The date of the last run, so that a once-a-day check happens once a day.  Hidden.",
    },
    ".maptasker_changelog.txt": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "The version check",
        "note": "The change log fetched for a newer version, kept so it can be shown without fetching it again.  Hidden.",
    },
    ".maptasker.pkl": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "Older versions only",
        "note": "Where the AI API keys used to be kept.  It is no longer written; a leftover one is moved into the system password store and removed.  Hidden.",
    },
    ".MapTasker_Settings.pkl": {
        "section": "Settings and remembered state",
        "location": CURRENT,
        "produced_by": "Older versions only",
        "note": "A second settings file that never held anything.  It is no longer written, and a leftover one is deleted unopened.  Hidden.",
    },
    # -- Folders ---------------------------------------------------------------------
    "MapTasker_Backups": {
        "section": "Folders",
        "location": CURRENT,
        "produced_by": "Any save that would overwrite a file",
        "note": "A copy of a file taken just before a save would overwrite it, with only the ten newest kept per file.  Nothing is copied if there is nothing at the target path.  Old copies are removed for you, and you can delete single copies or the whole folder at any time without breaking anything -- it is recreated the next time a save needs it.",
    },
    "MapTasker_Timeline": {
        "section": "Folders",
        "location": CURRENT,
        "produced_by": "'Timeline'",
        "note": "The history of your configuration, used to track what has changed.  The thirty most recent differing configurations are kept, each one compressed.",
    },
    # -- Android ----------------------------------------------------------------------
    "maptasker_apps.txt": {
        "section": "Android",
        "location": DEVICE,
        "produced_by": "'MapTasker Get Apps'",
        "note": "The device's installed applications: package, name and activity.",
    },
    "maptasker_files.txt": {
        "section": "Android",
        "location": DEVICE,
        "produced_by": "'MapTasker List Files'",
        "note": "The files on the device.",
    },
    "maptasker_objects.txt": {
        "section": "Android",
        "location": DEVICE,
        "produced_by": "'MapTasker List Tasker Objects'",
        "note": "Every Project, Profile, Scene and Task in one run.  Projects have no HTTP endpoint of their own, so this is the only way to get them.",
    },
    "maptasker_import.txt": {
        "section": "Android",
        "location": DEVICE,
        "produced_by": "'Import Into Tasker'",
        "note": "What the import did, handed back so MapTasker can report it.",
    },
    "maptasker_idcheck.txt": {
        "section": "Android",
        "location": DEVICE,
        "produced_by": "'Import Into Tasker'",
        "note": "The result of checking ids after an import.",
    },
    "maptasker_launch_tasker.txt": {
        "section": "Android",
        "location": DEVICE,
        "produced_by": "'Open Tasker'",
        "note": "The result of asking the device to open Tasker.",
    },
    # -- Diagnostics --------------------------------------------------------------------
    "maptasker_debug.log": {
        "section": "Diagnostics",
        "location": CURRENT,
        "produced_by": "The '-debug' runtime option",
        "note": "A trace log for program debugging.  It is only created with '-debug', and a runtime error tells you to look here.",
    },
    ".maptasker_error.txt": {
        "section": "Diagnostics",
        "location": CURRENT,
        "produced_by": "A failed parse",
        "note": "How a parse failed, written so the window that asked for it can report the error rather than lose it.  Hidden, and removed once it has been read.",
    },
}


# ##################################################################################
# Discovery
# ##################################################################################
@dataclass
class OutputFile:
    """One file, or folder, that MapTasker writes."""

    name: str
    section: str = UNDESCRIBED_SECTION
    location: str = CURRENT
    produced_by: str = "--"
    note: str = ""
    constant: str = ""
    module: str = ""
    stamped: bool = False
    extensions: tuple[str, ...] = ()

    @property
    def displayed_name(self) -> str:
        """The name as the reader will meet it on disk.

        Returns:
            str: the name, with the date-and-time stamp shown where one is inserted and
                the alternative extensions spelled out where a stem is written several ways.
        """
        if self.extensions:
            return f"{self.name}.{'/'.join(self.extensions)}"
        if not self.stamped:
            return self.name
        stem, _, suffix = self.name.rpartition(".")
        return f"{stem}{STAMP_SUFFIX}.{suffix}" if stem else f"{self.name}{STAMP_SUFFIX}"


@dataclass
class Discovery:
    """Everything the source had to say, before the descriptions are merged in."""

    constants: dict[str, str] = field(default_factory=dict)  # constant -> filename
    comments: dict[str, str] = field(default_factory=dict)  # constant -> comment above it
    stamped: set[str] = field(default_factory=set)  # constants given a date/time stamp
    modules: dict[str, str] = field(default_factory=dict)  # constant -> module that writes it
    literals: dict[str, str] = field(default_factory=dict)  # filename -> module it is named in
    device: dict[str, str] = field(default_factory=dict)  # filename -> constant in deviceinv
    folders: dict[str, str] = field(default_factory=dict)  # folder name -> module that makes it


def is_excluded(name: str) -> bool:
    """Is this one of the file types the page leaves out?

    Args:
        name (str): the filename.

    Returns:
        bool: True if it is excluded.
    """
    return name.lower().endswith(EXCLUDED_SUFFIXES)


def looks_like_a_filename(value: str) -> bool:
    """Is this string literal one of MapTasker's own output files?

    Args:
        value (str): the string literal found in the source.

    Returns:
        bool: True if it names a file this page should carry.
    """
    if "/" in value or "\\" in value or " " in value:
        return False
    if not value.lower().lstrip(".").startswith("maptasker"):
        return False
    return value.lower().endswith(FILENAME_SUFFIXES) and not is_excluded(value)


def read_comment_above(lines: list[str], line_number: int) -> str:
    """Collect the comment block sitting directly above a constant.

    Args:
        lines (list[str]): the module's lines.
        line_number (int): the 1-based line the constant is assigned on.

    Returns:
        str: the comment as one paragraph, or "" if there is no comment above it.
    """
    collected: list[str] = []
    index = line_number - 2  # -1 for 0-based, -1 again for the line above
    while index >= 0 and lines[index].lstrip().startswith("#"):
        collected.append(lines[index].lstrip().lstrip("#").strip())
        index -= 1
    return " ".join(reversed(collected)).strip()


def discover_constants(discovery: Discovery) -> None:
    """Find the filename constants in 'sysconst.py', with the comment above each.

    Args:
        discovery (Discovery): collected here.
    """
    source = SYSCONST.read_text(encoding="utf-8")
    lines = source.splitlines()
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        value = node.value.value
        if not isinstance(value, str):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            # A stem such as MAP_EXPORT_FILE has no suffix of its own; the formats are
            # added where it is written.  Take it on the name, not on the value.
            named_file = target.id.endswith(("_FILE", "_FOLDER"))
            if not named_file or is_excluded(value):
                continue
            discovery.constants[target.id] = value
            comment = read_comment_above(lines, node.lineno)
            if comment:
                discovery.comments[target.id] = comment


def modules() -> list[Path]:
    """Every module the program is made of.

    Returns:
        list[Path]: the source files, sorted.
    """
    return sorted(SOURCE_DIR.glob("*.py"))


def discover_stamped(discovery: Discovery) -> None:
    """Work out which files get a date and time stamped into their name.

    A constant handed straight to 'append_to_filename' is the easy case.  The rest
    reach it through a function of their own -- 'write_comparison_report(report,
    base_name)' and 'taskflow._write(rows, file_name, ...)' -- so any function that
    passes one of its own parameters to the helper is noted, and its callers are then
    read for the constant they pass in that position.

    Args:
        discovery (Discovery): collected here.
    """
    # function name -> the parameters it stamps, by position and by keyword
    stamping: dict[str, set[int | str]] = {}
    trees: dict[Path, ast.Module] = {}

    for path in modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        trees[path] = tree
        for function in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            parameters = [a.arg for a in function.args.args + function.args.kwonlyargs]
            # The defaults, so 'base_name: str = COMPARE_FILE' is picked up on its own.
            defaults = dict(
                zip(
                    parameters[len(parameters) - len(function.args.defaults) :],
                    function.args.defaults,
                    strict=False,
                ),
            )
            for call in [n for n in ast.walk(function) if isinstance(n, ast.Call)]:
                if not isinstance(call.func, ast.Name) or call.func.id != STAMP_HELPER:
                    continue
                if not call.args or not isinstance(call.args[0], ast.Name):
                    continue
                stamped_name = call.args[0].id
                if stamped_name in discovery.constants:
                    discovery.stamped.add(stamped_name)
                    discovery.modules.setdefault(stamped_name, path.stem)
                elif stamped_name in parameters:
                    position = parameters.index(stamped_name)
                    stamping.setdefault(function.name, set()).update({position, stamped_name})
                    default = defaults.get(stamped_name)
                    if isinstance(default, ast.Name) and default.id in discovery.constants:
                        discovery.stamped.add(default.id)
                        discovery.modules.setdefault(default.id, path.stem)

    # Second pass: whoever calls those functions, with a constant in a stamped position.
    for path, tree in trees.items():
        for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
            name = call.func.id if isinstance(call.func, ast.Name) else getattr(call.func, "attr", "")
            stamped_positions = stamping.get(name)
            if not stamped_positions:
                continue
            for position, argument in enumerate(call.args):
                if position in stamped_positions and isinstance(argument, ast.Name) and argument.id in discovery.constants:
                    discovery.stamped.add(argument.id)
                    discovery.modules.setdefault(argument.id, path.stem)
            for keyword in call.keywords:
                if keyword.arg in stamped_positions and isinstance(keyword.value, ast.Name) and keyword.value.id in discovery.constants:
                    discovery.stamped.add(keyword.value.id)
                    discovery.modules.setdefault(keyword.value.id, path.stem)


def discover_literals(discovery: Discovery) -> None:
    """Find output files named by a bare string literal rather than by a constant.

    Args:
        discovery (Discovery): collected here.
    """
    for path in modules():
        if path == SYSCONST:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and looks_like_a_filename(node.value):
                discovery.literals.setdefault(node.value, path.stem)
    # sysconst names the debug log itself, in lower case and outside the _FILE convention.
    for node in ast.walk(ast.parse(SYSCONST.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and looks_like_a_filename(node.value):
            discovery.literals.setdefault(node.value, SYSCONST.stem)


def discover_folders(discovery: Discovery) -> None:
    """Find the folders MapTasker makes beside its files.

    They are named where they are used rather than in 'sysconst.py' -- BACKUP_FOLDER in
    'presave.py', HISTORY_FOLDER in 'timeline.py' -- so the convention to follow is the
    constant's name, not its module.

    Args:
        discovery (Discovery): collected here.
    """
    for path in modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            value = node.value.value
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not isinstance(value, str) or not any(t.endswith("_FOLDER") for t in targets):
                continue
            if value.lower().startswith("maptasker") and not value.lower().endswith(FILENAME_SUFFIXES):
                discovery.folders.setdefault(value, path.stem)


def discover_device_files(discovery: Discovery) -> None:
    """Find the files the helper Tasks write on the Android device.

    Args:
        discovery (Discovery): collected here.
    """
    for node in ast.walk(ast.parse(DEVICE_MODULE.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        value = node.value.value
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not isinstance(value, str) or not any(t.endswith("_WRITE_PATH") for t in targets):
            continue
        name = value.rsplit("/", 1)[-1]
        if not is_excluded(name):
            discovery.device.setdefault(name, targets[0])


def discover() -> Discovery:
    """Read the source.

    Returns:
        Discovery: everything found.
    """
    discovery = Discovery()
    discover_constants(discovery)
    discover_stamped(discovery)
    discover_literals(discovery)
    discover_folders(discovery)
    discover_device_files(discovery)
    return discovery


# ##################################################################################
# Merge
# ##################################################################################
def collect(discovery: Discovery) -> tuple[list[OutputFile], list[str]]:
    """Turn what was found into the rows of the page.

    Args:
        discovery (Discovery): what the source said.

    Returns:
        tuple[list[OutputFile], list[str]]: the files, and the names that have no
            description yet.
    """
    files: dict[str, OutputFile] = {}

    def add(name: str, **attributes: object) -> OutputFile:
        entry = files.setdefault(name, OutputFile(name=name))
        for attribute, value in attributes.items():
            if value:
                setattr(entry, attribute, value)
        return entry

    for constant, name in discovery.constants.items():
        add(
            name,
            constant=constant,
            stamped=constant in discovery.stamped,
            module=discovery.modules.get(constant, ""),
            note=discovery.comments.get(constant, ""),
        )
    for name, module in discovery.literals.items():
        add(name, module=module)
    for name, constant in discovery.device.items():
        add(name, constant=constant, module=DEVICE_MODULE.stem)
    for name, module in discovery.folders.items():
        add(name, module=module)

    # The two export stems are written once per format; the formats come from the page's
    # own description rather than from a constant, since mapexport builds the name.
    for stem in ("MapTasker_Map_Export", "MapTasker_Diagram_Export"):
        if stem in files:
            files[stem].extensions = ("md", "json", "pdf")

    undescribed: list[str] = []
    for name, entry in files.items():
        described = DESCRIPTIONS.get(name)
        if described is None:
            undescribed.append(name)
            entry.note = entry.note or UNDESCRIBED_NOTE
            continue
        entry.section = described["section"]
        entry.location = described["location"]
        entry.produced_by = described["produced_by"]
        entry.note = described["note"]

    return sorted(files.values(), key=lambda f: f.displayed_name.lower()), sorted(undescribed)


# ##################################################################################
# The page
# ##################################################################################
def escape(text: str) -> str:
    """Make a description safe to drop into a table cell.

    Args:
        text (str): the description.

    Returns:
        str: the description with anything that would end the cell early taken out.
    """
    return text.replace("|", "\\|").replace("\n", " ").strip()


def build_page(files: list[OutputFile]) -> str:
    """Write the markdown.

    Args:
        files (list[OutputFile]): every file to be listed.

    Returns:
        str: the page.
    """
    out: list[str] = [
        "# Generated Output Files",
        "",
        "The files MapTasker writes, and what each one is for.  XML files are not listed.",
        "",
        "'Current folder' is the folder MapTasker was started from.  'Settings folder' is the",
        "one the operating system sets aside for this user's settings: `Library/Application",
        "Support` on macOS, `APPDATA` on Windows, `XDG_CONFIG_HOME` or `.config` on Linux.",
        "",
        "> Generated by `tools/misc/build_generated_files_doc.py` from the source.  Run it",
        "> again rather than editing this page by hand.",
        "",
    ]

    for section, blurb in SECTIONS:
        in_section = [f for f in files if f.section == section]
        if not in_section:
            continue
        out += [f"## {section}", "", blurb, "", "| File | Written to | Produced by | What it holds |", "| :--- | :--- | :--- | :--- |"]
        out += [
            f"| `{f.displayed_name}` | {f.location} | {escape(f.produced_by)} | {escape(f.note)} |"
            for f in in_section
        ]
        out.append("")

    out += [
        "## Tasker helper Tasks",
        "",
        "Not files, but the other half of the Android story: each helper Task is added to",
        "Tasker through the HTTP API the first time you use the feature that needs it, and",
        "only if a Task of that name is not already there.  The 'vx' is a version, such as",
        "'v2'.  They are what write the files in the Android table above.",
        "",
        "| Task | What it does |",
        "| :--- | :--- |",
        "| `MapTasker Get Apps vx` | Gets the device's installed apps -- package, name, activity -- and matches each app name to its own package. |",
        "| `MapTasker List Files vx` | Lists the files on the device.  It replaces the old 'MapTasker List' TaskerNet Profile. |",
        "| `MapTasker List Tasker Objects vx` | Lists all Projects, Profiles, Scenes and Tasks in one run. |",
        "| `MapTasker Backup For ID Check vx` | Runs Tasker's Data Backup so ids can be checked after an import.  The backup is only held in memory and is deleted from the device. |",
        "| `MapTasker Import Profile vx` | Imports a staged Profile into Tasker's configuration. |",
        "| `MapTasker Run Task vx` | Runs one of your Tasks by name and returns what it returned, passing %par1 and %par2 through.  'Run On Android' uses it for names Tasker's HTTP server cannot look up, such as '$Taskaroo'. |",
        "| `MapTasker Open Tasker vx` | Opens Tasker, without handing it a file. |",
        "",
        "Each import route has a pair, one that opens the file and one that sends an intent:",
        "`MapTasker Open Profile vx` / `MapTasker Send Profile vx`, and the same for Project,",
        "Scene and Task.",
        "",
    ]
    return "\n".join(out)


# ##################################################################################
# Run it
# ##################################################################################
def main() -> int:
    """Build the page.

    Returns:
        int: 0, or 1 if '--check' found the page on disk out of date.
    """
    parser = argparse.ArgumentParser(description="Build the MapTasker generated-output-files reference page.")
    parser.add_argument("--stats", action="store_true", help="report what was found in the source")
    parser.add_argument("--check", action="store_true", help="write nothing; fail if the page on disk is out of date")
    parser.add_argument("--print", dest="to_stdout", action="store_true", help="write nothing; print the page")
    arguments = parser.parse_args()

    if not SYSCONST.is_file():
        print(f"Cannot find the source at {SOURCE_DIR}", file=sys.stderr)
        return 1

    discovery = discover()
    files, undescribed = collect(discovery)
    page = build_page(files)

    if arguments.to_stdout:
        print(page)
    elif arguments.check:
        current = OUTPUT_PAGE.read_text(encoding="utf-8") if OUTPUT_PAGE.is_file() else ""
        if current != page:
            print(f"{OUTPUT_PAGE.name} is out of date.  Run: python tools/misc/build_generated_files_doc.py", file=sys.stderr)
            return 1
        print(f"{OUTPUT_PAGE.name} is up to date.")
    else:
        OUTPUT_PAGE.write_text(page, encoding="utf-8")
        print(f"Wrote {OUTPUT_PAGE.relative_to(PROJECT_ROOT)} -- {len(files)} files.")

    if arguments.stats:
        print(f"\n  constants in sysconst.py : {len(discovery.constants)}")
        print(f"  date/time stamped        : {len(discovery.stamped)}")
        print(f"  named by a literal       : {len(discovery.literals)}")
        print(f"  written on the device    : {len(discovery.device)}")
        print(f"  folders                  : {len(discovery.folders)}")
        for section, _ in SECTIONS:
            print(f"  {section:<25}: {len([f for f in files if f.section == section])}")

    if undescribed:
        print(f"\n{len(undescribed)} file(s) found in the source with no description in DESCRIPTIONS:", file=sys.stderr)
        for name in undescribed:
            print(f"  {name}", file=sys.stderr)

    # Anything described but no longer written is the other half of the same gap.
    stale = sorted(set(DESCRIPTIONS) - {f.name for f in files})
    if stale:
        print(f"\n{len(stale)} description(s) for files the source no longer names:", file=sys.stderr)
        for name in stale:
            print(f"  {name}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
