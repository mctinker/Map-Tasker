"""Fuzz the backup parser: whatever is in the file, the run ends in an answer and never in a traceback.

MapTasker reads files it did not write -- a backup from any Tasker version, copied over a bad connection, saved by an
editor in another encoding, half-written when the phone died -- and every other test here starts from a well-formed one.
These tests start from a well-formed one too and then spoil it, in the ways such a file really is spoiled:

  * the tree: an element dropped, an attribute missing or holding something that is not what it should, text that is not
    a number where a number is read, an element repeated, renamed, emptied or moved under another one;
  * the encoding: UTF-16, Latin-1, a byte-order mark, a declaration that says one encoding over bytes in another;
  * the bytes: cut short, a slice missing, junk written into the middle of it.

The contract being checked is the one MapTaskerError exists for.  A library module that cannot carry on raises it, and the
entry point turns it into a message and an exit code.  So:

  * loading raises MapTaskerError or nothing -- never a KeyError, an AttributeError, a UnicodeError or a ParseError;
  * a command-line report, which loads and then builds the Map or the Diagram, returns one of the exit codes the command
    line documents -- it does not raise.

Hypothesis picks the spoilage and, when something breaks, shrinks it to the smallest file that still does and prints how
to replay it.  A crash it finds is fixed in the code and then pinned in REGRESSIONS below, so it stays fixed.

A backup that names something the file does not hold -- a Project listing a Task that is not there -- is not an error here.
Health Check exists to report exactly that (BROKEN-TID-REF and its kin), so the Map and the Diagram leave the missing
thing out and carry on.

MAPTASKER_FUZZ_SCALE=20 runs twenty times as many examples, for a long run before a release.  MAPTASKER_FUZZ_BACKUP=path
adds a backup of your own to the ones that are spoiled -- the repository holds nobody's configuration, so only you can
point the fuzz at a real one.  A real backup is large and each example builds from it, so give it a fractional scale
(MAPTASKER_FUZZ_SCALE=0.05).
"""

from __future__ import annotations

import contextlib
import copy
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st
from maptasker.src import clireports
from maptasker.src.core import timeline
from maptasker.src.core.actionc import load_arg_specs
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.mtexcept import MapTaskerError
from maptasker.src.core.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.mapgen import taskerd
from maptasker.src.mapgen.lineout import LineOut
from maptasker.src.mapgen.mapexport import DIAGRAM, MAP

from tests.shared_fixtures import _LOCAL_XML

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_SYNTHETIC = (Path(__file__).parent / "data" / "synthetic_backup.xml").read_bytes()

# The codes the command line documents (clireports.build_parser's epilog).  A report that returns any other number has
# found a way to end that nobody described.
DOCUMENTED_EXIT_CODES = frozenset({0, 1, 2, 3, 6, 7, 10, 11})

SCALE = float(os.environ.get("MAPTASKER_FUZZ_SCALE", "1"))
_YOURS = os.environ.get("MAPTASKER_FUZZ_BACKUP")
BASES = [_SYNTHETIC, _LOCAL_XML.encode("utf-8"), *([Path(_YOURS).read_bytes()] if _YOURS else [])]


def _fuzz(examples: int) -> settings:
    """The settings for one fuzz test: no deadline (a Diagram takes what it takes), nothing written to .hypothesis."""
    return settings(
        max_examples=max(1, int(examples * SCALE)),
        deadline=None,
        database=None,
        print_blob=True,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow, HealthCheck.data_too_large],
    )


# ##################################################################################
# Spoiling the tree
# ##################################################################################
# What a hand-edited, mis-converted or newer-Tasker value looks like where a number, a name or a list was expected.
JUNK = st.one_of(
    st.sampled_from(
        [
            "",
            " ",
            "\t\n",
            "0",
            "-1",
            "99999999999999999999999999",
            "1e400",
            "nan",
            "abc",
            "1,2,,3",
            ",",
            "null",
            "None",
            "%var",
            "%var(%i)",
            "<>&\"'",
            "&amp;amp;",
            "\N{RIGHT-TO-LEFT OVERRIDE}",
            "\u0000",
            "😀",
            "日本語",
            "a" * 5000,
            "\\",
            "/",
            "{}",
        ]
    ),
    # Text with no control characters (the sampled values above have the ones worth trying): XML cannot hold them, and
    # a file with one in it is refused at the first read, which is one case and not a thousand.
    st.text(alphabet=st.characters(exclude_categories=["Cc", "Cs"]), max_size=20),
)
TAGS = st.sampled_from(
    ["Task", "Profile", "Project", "Scene", "Action", "code", "id", "nme", "Str", "Int", "x", "TaskerData"]
)
ATTRIBUTES = st.sampled_from(["sr", "ve", "dvi", "tv", "val", "type", "name"])
INDEX = st.integers(min_value=0, max_value=10**6)

# The elements the Map is built out of.  Spoiling one of these is far likelier to matter than spoiling one of the many
# <Int sr="arg7" val="0"/> beside it, so half the operations are aimed at them.
STRUCTURAL = frozenset(
    {
        "Project",
        "Profile",
        "Task",
        "Scene",
        "Action",
        "ListElementItem",
        "PropertiesElement",
        "id",
        "nme",
        "name",
        "code",
        "pids",
        "tids",
        "scenes",
        "mid0",
        "mid1",
        "keyTask",
    }
)


@st.composite
def tree_operations(draw: st.DrawFn) -> tuple[Any, ...]:
    """One way to spoil one element, chosen by position so the same operation fits whatever tree it is applied to."""
    kind = draw(
        st.sampled_from(
            [
                "drop_element",
                "drop_attribute",
                "junk_attribute",
                "junk_text",
                "duplicate",
                "rename",
                "empty",
                "reparent",
            ]
        )
    )
    head = (kind, draw(INDEX), draw(st.booleans()))
    match kind:
        case "junk_attribute":
            return (*head, draw(INDEX), draw(ATTRIBUTES), draw(JUNK))
        case "junk_text":
            return (*head, draw(JUNK))
        case "rename":
            return (*head, draw(TAGS))
        case "drop_attribute" | "reparent":
            return (*head, draw(INDEX))
        case _:
            return head


def _elements_with_parents(root: ET.Element) -> list[tuple[ET.Element, ET.Element | None]]:
    found: list[tuple[ET.Element, ET.Element | None]] = [(root, None)]
    for parent in root.iter():
        found.extend((child, parent) for child in parent)
    return found


def spoil(root: ET.Element, operation: tuple[Any, ...]) -> None:
    """Apply one operation in place.  The root itself is only ever changed, never dropped: a tree needs one."""
    kind, position, focused, *rest = operation
    found = _elements_with_parents(root)
    if focused:
        found = [item for item in found if item[0].tag in STRUCTURAL] or found
    element, parent = found[position % len(found)]
    match kind:
        case "drop_element":
            if parent is not None:
                parent.remove(element)
        case "drop_attribute":
            if element.attrib:
                del element.attrib[sorted(element.attrib)[rest[0] % len(element.attrib)]]
        case "junk_attribute":
            names = sorted(element.attrib) or [rest[1]]
            element.set(names[rest[0] % len(names)] if rest[0] % 2 else rest[1], rest[2])
        case "junk_text":
            element.text = rest[0]
        case "duplicate":
            if parent is not None:
                parent.insert(list(parent).index(element), copy.deepcopy(element))
        case "rename":
            element.tag = rest[0]
        case "empty":
            element.text = None
            element.attrib.clear()
            for child in list(element):
                element.remove(child)
        case "reparent":
            target = found[rest[0] % len(found)][0]
            inside = {id(descendant) for descendant in element.iter()}
            if parent is not None and id(target) not in inside:
                parent.remove(element)
                target.append(element)


# ##################################################################################
# Spoiling the encoding and the bytes
# ##################################################################################
# Weighted toward the ordinary: a file whose encoding is wrong is read as nothing at all, and the fuzz should mostly be
# spent on files that get far enough in for the tree to matter.
DECLARED = st.sampled_from(
    [None] * 3 + ["UTF-8"] * 3 + ["utf-16", "ISO-8859-1", "us-ascii", "shift_jis", "no-such-encoding"]
)
ACTUAL = st.sampled_from(["utf-8"] * 24 + ["utf-8-sig", "utf-16", "utf-16-le", "latin-1", "cp1252", "utf-32"])


@st.composite
def byte_operations(draw: st.DrawFn) -> tuple[str, float, float, bytes]:
    """One way to spoil the bytes: where (as a fraction of the file), how far, and what is written there."""
    return (
        draw(st.sampled_from(["truncate", "cut", "insert", "overwrite"])),
        draw(st.integers(min_value=20, max_value=1000)) / 1000,
        draw(st.integers(min_value=0, max_value=200)) / 1000,
        draw(st.binary(max_size=8)),
    )


def spoil_bytes(data: bytes, operation: tuple[str, float, float, bytes]) -> bytes:
    """Apply one byte operation: cut the file short, cut a slice out, or write junk in the middle."""
    kind, where, how_far, junk = operation
    start = int(len(data) * where)
    end = min(len(data), start + max(1, int(len(data) * how_far)))
    match kind:
        case "truncate":
            return data[:start]
        case "cut":
            return data[:start] + data[end:]
        case "insert":
            return data[:start] + junk + data[start:]
        case _:
            return data[:start] + junk + data[start + len(junk) :]


class _Backup(bytes):
    """A backup's bytes that print as their first few thousand, so a failure on a real 13 MB file reports in a screenful."""

    def __repr__(self) -> str:
        shown = bytes.__repr__(self[:3000])
        return shown if len(self) <= 3000 else f"{shown} ... ({len(self)} bytes in all)"


@st.composite
def backups(draw: st.DrawFn) -> bytes:
    """A backup's bytes, from a well-formed one spoiled in the tree, in the encoding and in the bytes."""
    base = draw(st.sampled_from(BASES))
    root = ET.fromstring(base)
    for operation in draw(st.lists(tree_operations(), max_size=4)):
        spoil(root, operation)
    text = ET.tostring(root, encoding="unicode")
    declared = draw(DECLARED)
    if declared:
        text = f'<?xml version="1.0" encoding="{declared}"?>\n{text}'
    # errors="replace": a character the encoding cannot hold is still a file somebody could have.
    data = text.encode(draw(ACTUAL), errors="replace")
    # Damage to the bytes, in a quarter of the files: it is refused at the first read more often than not, and the files
    # that get further in are the ones where the tree matters.
    if draw(st.integers(min_value=0, max_value=3)) == 0:
        for operation in draw(st.lists(byte_operations(), min_size=1, max_size=2)):
            data = spoil_bytes(data, operation)
    return _Backup(data)


# ##################################################################################
# Running on it
# ##################################################################################
@contextlib.contextmanager
def a_scratch_run(data: bytes) -> Iterator[Path]:
    """The bytes as a file in a working directory of its own -- where the history, settings and errors would land."""
    here = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="maptasker_fuzz_") as folder:
        os.chdir(folder)
        PrimeItemsReset()
        try:
            path = Path(folder) / "backup.xml"
            path.write_bytes(data)
            yield path
        finally:
            timeline.use_history_folder(None)
            PrimeItemsReset()
            PrimeItems.headless = False
            os.chdir(here)


def _ends_in_a_documented_exit_code(argv: list[str], data: bytes) -> None:
    with a_scratch_run(data) as path:
        code = clireports.run([*argv, "-file", str(path)])
    event(f"exit code {code}")
    assert code in DOCUMENTED_EXIT_CODES, f"the run ended with {code}, which the command line does not document"


def _is_loaded_or_refused(data: bytes) -> None:
    with a_scratch_run(data) as path, path.open(encoding="utf-8", errors="replace") as opened:
        # What a load needs of the run, as test_taskerd sets it up.
        PrimeItems.program_arguments = ProgramArguments(
            debug=False, directory=False, pretty=False, gui=False, display_detail_level=3
        )
        PrimeItems.colors_to_use = set_color_mode("dark")
        PrimeItems.output_lines = LineOut()
        load_arg_specs(state=PrimeItems)
        PrimeItems.file_to_get = opened
        try:
            taskerd.get_the_xml_data(state=PrimeItems)
        except MapTaskerError:
            event("refused with MapTaskerError")
        else:
            event("loaded")


@_fuzz(300)
@given(data=backups())
def test_loading_a_spoiled_backup_raises_nothing_but_maptasker_error(data: bytes) -> None:
    _is_loaded_or_refused(data)


@_fuzz(150)
@given(data=backups())
def test_the_health_check_of_a_spoiled_backup_ends_in_an_exit_code(data: bytes) -> None:
    _ends_in_a_documented_exit_code(["-healthcheck"], data)


@pytest.mark.parametrize("view", [MAP, DIAGRAM])
@_fuzz(200)
@given(data=backups())
def test_building_the_view_of_a_spoiled_backup_ends_in_an_exit_code(view: str, data: bytes) -> None:
    _ends_in_a_documented_exit_code(["-export", view], data)


# ##################################################################################
# Pinned: each crash the fuzz found, as the smallest spoiling that shows it
# ##################################################################################
def _task(root: ET.Element, task_id: str) -> ET.Element:
    return next(task for task in root.findall("Task") if task.findtext("id") == task_id)


def _profile(root: ET.Element) -> ET.Element:
    return root.find("Profile")  # type: ignore[return-value]


def _drop_task(root: ET.Element) -> None:
    root.remove(_task(root, "101"))


def _drop_other_task(root: ET.Element) -> None:
    root.remove(_task(root, "104"))


def _drop_profile(root: ET.Element) -> None:
    root.remove(_profile(root))


def _drop_scene(root: ET.Element) -> None:
    root.remove(root.find("Scene"))  # type: ignore[arg-type]


def _empty_id(root: ET.Element) -> None:
    _profile(root).find("id").text = None  # type: ignore[union-attr]


def _empty_task_id(root: ET.Element) -> None:
    _task(root, "102").find("id").text = None  # type: ignore[union-attr]


def _no_version(root: ET.Element) -> None:
    del root.attrib["tv"]


def _bare_root(root: ET.Element) -> None:
    root.attrib.clear()
    for child in list(root):
        root.remove(child)


def _no_sr(root: ET.Element) -> None:
    del _profile(root).attrib["sr"]


def _sr_disagrees_with_id(root: ET.Element) -> None:
    _profile(root).set("sr", "prof999")


def _profile_runs_a_missing_task(root: ET.Element) -> None:
    _profile(root).find("mid0").text = "999"  # type: ignore[union-attr]


def _unnamed_profile_with_no_id(root: ET.Element) -> None:
    profile = _profile(root)
    profile.remove(profile.find("nme"))  # type: ignore[arg-type]
    profile.remove(profile.find("id"))  # type: ignore[arg-type]


# What each spoils, and the crash it was.  Most are a thing the file names that it does not hold, which Health Check
# reports as a BROKEN-... finding and the Map and the Diagram now leave out.
REGRESSIONS: dict[str, Callable[[ET.Element], None]] = {
    "a Task a Project, a Profile and a Scene all name is missing": _drop_task,
    "a Task a Project lists is missing": _drop_other_task,
    "a Profile a Project lists is missing": _drop_profile,
    "a Scene a Project lists is missing": _drop_scene,
    "a Profile has an empty id": _empty_id,
    "a Task has an empty id": _empty_task_id,
    "the root has no Tasker version": _no_version,
    "the root is bare": _bare_root,
    "a Profile has no sr": _no_sr,
    "a Profile's sr is not its id": _sr_disagrees_with_id,
    "a Profile runs a Task that is not there": _profile_runs_a_missing_task,
    "a Profile has neither a name nor an id": _unnamed_profile_with_no_id,
}

_VIEWS = pytest.mark.parametrize(
    "argv", [["-healthcheck"], ["-export", MAP], ["-export", DIAGRAM]], ids=["health", "map", "diagram"]
)


@_VIEWS
@pytest.mark.parametrize("spoiling", REGRESSIONS.values(), ids=list(REGRESSIONS))
def test_a_crash_the_fuzz_found_stays_fixed(spoiling: Callable[[ET.Element], None], argv: list[str]) -> None:
    root = ET.fromstring(_SYNTHETIC)
    spoiling(root)
    with a_scratch_run(ET.tostring(root)) as path:
        code = clireports.run([*argv, "-file", str(path)])
    assert code in DOCUMENTED_EXIT_CODES


@_VIEWS
def test_the_unspoiled_backup_is_not_refused(argv: list[str]) -> None:
    """The ground the fuzz stands on: with nothing spoiled the file loads and builds, so a pass above means something."""
    with a_scratch_run(_SYNTHETIC) as path:
        code = clireports.run([*argv, "-file", str(path)])
    assert code in {0, 10}
