"""Round-trip verification of the edit path: render, re-parse, compare."""

#! /usr/bin/env python3

#                                                                                      #
# roundtrip: prove that what an edit is about to write can be read back unchanged.      #
#                                                                                      #
# MIT License   Refer to https://opensource.org/license/mit                            #
#
# WHAT THIS IS FOR
#
# Every "Save To Android" and "Import Into Tasker" button ends in the same two steps: an
# in-memory element is serialized to XML text, and that text becomes a file in a live
# Tasker configuration.  Between those two steps sit ElementTree's serializer and, on the
# way back in, Tasker's own parser -- and a value that does not survive the trip is not
# reported by anything.  The upload answers 200, the readback compares the bytes that were
# sent against the bytes that landed (they match, because both are already wrong), and the
# corruption is discovered later, in Tasker, in a Task that no longer does what it did.
#
# This module runs the missing step in between: parse the rendered text back, and compare
# what comes out against what went in.
#
# THE TWO CHECKS, AND WHY BOTH ARE NEEDED
#
# 1. SERIALIZATION IS A FIXED POINT.  render -> parse -> render must reproduce the rendered
#    text exactly.  This is the check that catches what the SERIALIZER and the PARSER do to
#    each other, and it needs to know nothing about Tasker.  The concrete one it was written
#    for: ElementTree escapes \r inside an attribute value (as &#13;) but not inside element
#    text, and every XML parser normalizes a bare \r in text to \n -- so a carriage return
#    anywhere in an Action's text silently becomes a newline the moment the file is read
#    back.  Control characters, lone surrogates and stray entities fail here the same way.
#
# 2. UNTOUCHED OBJECTS COME BACK IDENTICAL.  Every object in the rendered document is
#    compared against the in-memory element it was copied from.  This is the check that
#    catches what THIS PROGRAM does: a deepcopy that aliased instead of copying, an <mdate>
#    restamp that reached an object it was not meant to reach, an sr renumber applied to the
#    wrong element.  Check 1 cannot see any of these -- a faithfully serialized wrong answer
#    is still a fixed point.
#
# WHAT "UNTOUCHED" EXCLUDES, AND WHY IT IS EXACTLY ONE THING
#
# Three of the four renderers only deep-copy: taskedit.render_standalone_task_xml,
# profedit.render_standalone_profile_xml and sceneedit.render_standalone_scene_xml put back
# what they were given, so every object they emit -- including the one being exported -- is
# subject to check 2.
#
# projedit.render_standalone_project_xml is the exception, and deliberately so: it rewrites
# the exported <Project> element's sr to "proj0", may reorder <pids> ahead of <tids>, and
# calls _ensure_project_identity on it.  Each of those is documented at length there, and
# each is a change Tasker's importer requires.  So the exported Project -- and nothing else
# in that document -- is exempt from check 2.  It still goes through check 1.
#
# WHAT A COMPARISON IGNORES
#
# Indentation, and only indentation.  ETW.indent rewrites the text of every element that has
# children and the tail of every element, so those are normalized away; a LEAF element's
# text is compared exactly, trailing spaces and all, because in Tasker's XML that is content.
# Tasker's XML has no mixed content, so there is nothing else a tail could have been.
#
# WHY THIS IS OPT-IN
#
# It re-parses and re-serializes the whole document, which for a Project export means every
# Profile, Scene and Task in it.  That is fractions of a second next to the several seconds
# of device round-trips a save already costs -- but it is the user's configuration, and a
# check that can refuse a save should be a thing the user asked for.  Hence the "Verify"
# checkbox on all four Save To Android panels; see guiwins.build_save_to_android_dialog.
#
# NO GLOBAL STATE IS WRITTEN.  Everything here reads PrimeItems and returns a report, which
# is what lets tests/test_roundtrip.py drive it from XML text alone.
#

from __future__ import annotations

import xml.etree.ElementTree as ETW  # stdlib "ET Write" -- used only to serialize
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET  # noqa: N817

from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    from collections.abc import Iterable

    import defusedxml.ElementTree

    from maptasker.src.profedit import EditableProfile
    from maptasker.src.taskedit import EditableTask

# The tag a standalone export wraps everything in, and the indent every renderer uses.
# Both have to match the renderers exactly or check 1 fails on documents that are fine --
# see _reserialize.
TASKERDATA_TAG = "TaskerData"
RENDER_INDENT = "\t"

# The tag each kind of object is found under in a rendered document, paired with the child
# tag that names it.  Profiles and Tasks are keyed by <id> because that is what the live
# tables are keyed by and what <pids>/<tids>/<mid0> point at; Projects and Scenes have no
# <id> in play and are keyed by name, again matching their tables.
_IDENTITY_TAG = {
    "Project": "name",
    "Profile": "id",
    "Task": "id",
    "Scene": "nme",
}

# Objects that are not one of the four kinds but still appear in an export and still have to
# survive it.  <dmetric> is the screen the Scenes were laid out on, copied from the loaded
# backup by both the Project and the Scene renderer -- there is only ever one, so its
# identity key is the empty string.
_SINGLETON_TAGS = ("dmetric",)

# How many differences one object reports before the rest are summarized.  A Task whose
# every action was mangled by the same cause would otherwise bury the other objects, and the
# first few say what the cause is just as well as forty do.
_MAX_DIFFERENCES_PER_OBJECT = 6


@dataclass(frozen=True)
class Difference:
    """One place where a re-parsed object stopped matching what was rendered."""

    where: str  # Path within the object, e.g. "Task/Action[4]/Str[1] text".
    was: str  # What the in-memory element held.
    now: str  # What came back out of the re-parse.

    def __str__(self) -> str:
        return f"{self.where}: was {self.was!r}, came back {self.now!r}"


@dataclass(frozen=True)
class RoundTripReport:
    """The verdict on one rendered document.

    `error` is set only when the check could not be run at all -- the render raised, or the
    text it produced will not parse.  That is the most serious outcome of the three and is
    reported on its own: there is nothing to compare against a document that is not XML.
    """

    error: str = ""
    fixed_point: bool = True  # Check 1: render -> parse -> render reproduced the text.
    fixed_point_detail: str = ""
    checked: tuple[str, ...] = ()  # "Task 'Lights On'" for each object compared.
    exempt: tuple[str, ...] = ()  # Compared for check 1 only, and why (the Project).
    unchecked: tuple[str, ...] = ()  # In the document with nothing to compare against.
    differences: dict[str, tuple[Difference, ...]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when the document can be written -- nothing was lost or altered."""
        return not self.error and self.fixed_point and not self.differences

    def summary(self) -> str:
        """The one line that goes in a notification."""
        if self.error:
            return f"Verify could not run: {self.error}"
        # Named objects before the whole-document verdict, even though the document verdict
        # is the more fundamental of the two.  A corrupted value fails BOTH checks -- and
        # "Task 'Opener' changed" is something the user can go and look at, where "the XML
        # does not survive being read back" is not.  The document line is still in detail().
        if self.differences:
            changed = len(self.differences)
            objects = "object" if changed == 1 else "objects"
            return f"Verify FAILED: {changed} {objects} changed on the round trip."
        if not self.fixed_point:
            return "Verify FAILED: the XML does not survive being read back."
        counted = len(self.checked)
        objects = "object" if counted == 1 else "objects"
        return f"Verified: {counted} {objects} came back identical."

    def detail(self) -> list[str]:
        """The full account, one line per fact, for the report dialog and the log."""
        if self.error:
            return [self.error]

        lines: list[str] = []
        if not self.fixed_point:
            lines.append("Reading the rendered XML back and writing it out again did not reproduce it:")
            lines.append(f"    {self.fixed_point_detail}")
        for name, differences in self.differences.items():
            lines.append(f"{name} did not come back unchanged:")
            lines.extend(f"    {difference}" for difference in differences)
        if self.exempt:
            lines.append("Not compared (this program rewrites it on purpose):")
            lines.extend(f"    {entry}" for entry in self.exempt)
        if self.unchecked:
            lines.append("Not compared (nothing loaded to compare against):")
            lines.extend(f"    {entry}" for entry in self.unchecked)
        if not lines:
            lines.append(f"Every one of the {len(self.checked)} objects came back identical.")
        return lines


def _identify(element: defusedxml.ElementTree.Element) -> tuple[str, str] | None:
    """The (tag, key) pair that names one object on both sides of a re-parse.

    None for anything that is not an object this can track -- a <Setting>, say, which a
    standalone export never carries.
    """
    tag = element.tag
    if tag in _SINGLETON_TAGS:
        return (tag, "")
    name_tag = _IDENTITY_TAG.get(tag)
    if name_tag is None:
        return None
    found = element.find(name_tag)
    key = (found.text or "").strip() if found is not None else ""
    return (tag, key)


def _describe(identity: tuple[str, str]) -> str:
    """ "Task '134'" -- what a report calls an object."""
    tag, key = identity
    return f"{tag} '{key}'" if key else tag


def live_sources() -> dict[tuple[str, str], defusedxml.ElementTree.Element]:
    """Every object in the loaded configuration, keyed the way _identify keys them.

    This is what the renderers deep-copy out of, so it is what a re-parsed object has to
    match.  Built fresh on each call rather than cached: the tables are rebuilt outright by
    an undo (sessundo._restore) and mutated in place by every edit, so a cache would hand
    back elements from a tree nothing renders from any more.
    """
    tables = PrimeItems.tasker_root_elements or {}
    sources: dict[tuple[str, str], defusedxml.ElementTree.Element] = {}

    for table_name, tag in (
        ("all_projects", "Project"),
        ("all_profiles", "Profile"),
        ("all_tasks", "Task"),
        ("all_scenes", "Scene"),
    ):
        for entry in (tables.get(table_name) or {}).values():
            element = entry.get("xml") if isinstance(entry, dict) else None
            if element is None:
                continue
            # Keyed off the element itself, not off the table key: an unnamed Profile is
            # filed under a name this program derived for it (taskerd.build_tasker_tables),
            # and that name is nowhere in the XML for the re-parse to match on.
            identity = _identify(element)
            if identity is not None and identity[0] == tag:
                sources[identity] = element

    if PrimeItems.xml_root is not None:
        for tag in _SINGLETON_TAGS:
            found = PrimeItems.xml_root.find(tag)
            if found is not None:
                sources[(tag, "")] = found

    return sources


def _own_text(element: defusedxml.ElementTree.Element) -> str:
    """An element's text with the serializer's indentation taken back out.

    ETW.indent only rewrites the text of an element that HAS children, and only when that
    text is whitespace-only -- so that is the only case normalized here.  A leaf's text is
    returned exactly as it stands, spaces and all, because for a leaf it is the value.
    """
    text = element.text or ""
    if len(element) and not text.strip():
        return ""
    return text


def _differences(
    was: defusedxml.ElementTree.Element,
    now: defusedxml.ElementTree.Element,
    path: str,
    found: list[Difference],
) -> None:
    """Walk two elements in step, appending every place they part company.

    Children are matched by position, not by tag: an export that dropped one child or
    inserted one has changed the document, and reporting that as "12 children, came back
    11" is more useful than a resynchronized diff that hides which side moved.  Tails are
    not compared -- they are indentation, and nothing else, in Tasker's XML.
    """
    if len(found) >= _MAX_DIFFERENCES_PER_OBJECT:
        return

    if was.tag != now.tag:
        found.append(Difference(path, f"<{was.tag}>", f"<{now.tag}>"))
        return

    was_attributes = list(was.attrib.items())
    now_attributes = list(now.attrib.items())
    if was_attributes != now_attributes:
        found.append(Difference(f"{path} attributes", str(dict(was_attributes)), str(dict(now_attributes))))

    was_text = _own_text(was)
    now_text = _own_text(now)
    if was_text != now_text:
        found.append(Difference(f"{path} text", was_text, now_text))

    if len(was) != len(now):
        found.append(Difference(path, f"{len(was)} child elements", f"{len(now)} child elements"))

    for index, (was_child, now_child) in enumerate(zip(was, now, strict=False)):
        _differences(was_child, now_child, f"{path}/{now_child.tag}[{index}]", found)
        if len(found) >= _MAX_DIFFERENCES_PER_OBJECT:
            return


def _reserialize(root: defusedxml.ElementTree.Element) -> str:
    """Write a re-parsed document back out the way every renderer writes one.

    Has to match them character for character -- same indent, same lack of an <?xml?>
    declaration, same trailing newline -- or check 1 reports a difference that is this
    function's and not the document's.  See profedit.render_standalone_profile_xml.
    """
    ETW.indent(root, space=RENDER_INDENT)
    return ETW.tostring(root, encoding="unicode") + "\n"


def _first_difference(was: str, now: str) -> str:
    """Where two renderings of the same document first disagree, in readable form.

    The fallback for a check-1 failure that the element walk cannot explain -- attribute
    ORDER, say, which survives a parse but is not something _differences looks at
    separately.  A character offset plus the text either side of it is enough to see it.
    """
    limit = min(len(was), len(now))
    offset = next((index for index in range(limit) if was[index] != now[index]), limit)
    window = 40
    start = max(0, offset - window)
    return (
        f"first differs at character {offset}: "
        f"...{was[start : offset + window]!r} became ...{now[start : offset + window]!r}"
    )


def verify_rendered(
    rendered: str,
    overrides: dict[tuple[str, str], defusedxml.ElementTree.Element] | None = None,
    exempt: Iterable[tuple[str, str]] = (),
) -> RoundTripReport:
    """Run both checks over one rendered standalone export and report what they found.

    `rendered` is exactly the text that is about to be written -- not a re-render of it.

    `overrides` supplies source elements the loaded tables cannot: the working copy an
    Add/Edit dialog holds, which for a brand-new object is not in the tables at all and for
    an edited one is deliberately ahead of them (the live element is not touched until the
    save commits).  Anything not overridden is looked up in live_sources().

    `exempt` names objects to run check 1 over but not check 2 -- the exported <Project>,
    and only it.  See this module's header for why that exemption exists and why it is the
    only one.
    """
    try:
        # ParseError is a SyntaxError; defusedxml's own DefusedXmlException is a ValueError.
        # Both mean the same thing here -- the text that was about to be written is not XML
        # this program would accept back -- so both end the check the same way.
        reparsed = ET.fromstring(rendered)  # noqa: S314  (defusedxml -- the hardened parser)
    except (ET.ParseError, ValueError) as parse_error:
        logger.error(f"Round-trip verify: the rendered XML will not parse: {parse_error}")
        return RoundTripReport(error=f"the XML that was rendered will not parse back in ({parse_error})")

    fixed_point_detail = ""
    rewritten = _reserialize(reparsed)
    if rewritten != rendered:
        fixed_point_detail = _first_difference(rendered, rewritten)
        logger.error(f"Round-trip verify: not a fixed point -- {fixed_point_detail}")

    sources = live_sources()
    sources.update(overrides or {})
    exempted = set(exempt)

    checked: list[str] = []
    exempt_names: list[str] = []
    unchecked: list[str] = []
    differences: dict[str, tuple[Difference, ...]] = {}

    # Only the document's own children: an <Action> inside a Task is compared as part of
    # that Task, and a Scene's elements as part of that Scene.  A standalone export is flat
    # -- every object it carries is a direct child of <TaskerData>.
    for element in reparsed:
        identity = _identify(element)
        if identity is None:
            continue
        name = _describe(identity)
        if identity in exempted:
            exempt_names.append(name)
            continue
        source = sources.get(identity)
        if source is None:
            unchecked.append(name)
            continue
        checked.append(name)
        found: list[Difference] = []
        _differences(source, element, identity[0], found)
        if found:
            differences[name] = tuple(found)
            logger.error(f"Round-trip verify: {name} changed -- {found[0]}")

    return RoundTripReport(
        fixed_point=not fixed_point_detail,
        fixed_point_detail=fixed_point_detail,
        checked=tuple(checked),
        exempt=tuple(exempt_names),
        unchecked=tuple(unchecked),
        differences=differences,
    )


# ==========================================
# The four entry points, one per Save To Android panel.
#
# Each renders exactly what its save is about to send and hands it to verify_rendered with
# the right sources.  They render a SECOND time rather than being given the save's own text
# because the two renders are pure functions of the same unchanged tree -- and doing it here
# keeps every caller down to one line, which is what made wiring all eight handlers up
# without divergence possible.  The imports are local for the same reason every other
# cross-module edit-path import in this program is: taskedit/profedit/projedit/sceneedit
# already form a cycle among themselves (see projedit.render_standalone_project_xml's own
# lazy import of sceneedit).
# ==========================================
def verify_task(edited_task: EditableTask) -> RoundTripReport:
    """The Task about to go to the device, checked against the working copy it renders."""
    from maptasker.src import taskedit  # noqa: PLC0415

    try:
        rendered = taskedit.render_standalone_task_xml(edited_task)
    except (ValueError, AttributeError) as render_error:
        return RoundTripReport(error=f"the Task could not be rendered ({render_error})")

    element = edited_task.task_element
    identity = _identify(element)
    return verify_rendered(rendered, {identity: element} if identity else None)


def verify_profile(edited_profile: EditableProfile) -> RoundTripReport:
    """The Profile about to go to the device, plus the linked Tasks bundled with it.

    Only the Profile is overridden.  Its Entry/Exit Tasks are bundled straight out of the
    live tables (render_standalone_profile_xml deep-copies them there and then), so the
    live elements are the right thing to compare them against -- and them coming back
    unchanged is the whole point of check 2 for a Profile export.
    """
    from maptasker.src import profedit  # noqa: PLC0415

    try:
        rendered = profedit.render_standalone_profile_xml(edited_profile)
    except (ValueError, AttributeError) as render_error:
        return RoundTripReport(error=f"the Profile could not be rendered ({render_error})")

    element = edited_profile.profile_element
    identity = _identify(element)
    return verify_rendered(rendered, {identity: element} if identity else None)


def verify_project(project_name: str) -> RoundTripReport:
    """The Project about to go to the device, and everything it carries.

    No overrides: a Project export renders from the live tables by name, so the live
    elements ARE its sources.  The Project element itself is exempt from check 2 -- see this
    module's header, and projedit.render_standalone_project_xml for what it rewrites.
    """
    from maptasker.src import projedit  # noqa: PLC0415

    try:
        rendered = projedit.render_standalone_project_xml(project_name)
    except (ValueError, AttributeError) as render_error:
        return RoundTripReport(error=f"the Project could not be rendered ({render_error})")

    # The exemption is keyed off the live element's own <name>, not off project_name.  The
    # two are normally the same string, but project_name is the all_projects TABLE KEY -- the
    # name the Project was loaded under -- and a Rename typed but not yet applied leaves the
    # element carrying the other one (see projedit.EditableProject).  Keying off the table
    # key there would exempt an object that is not in the document and compare the exported
    # Project against a live element it was never meant to match.
    entry = (PrimeItems.tasker_root_elements or {}).get("all_projects", {}).get(project_name)
    element = entry.get("xml") if isinstance(entry, dict) else None
    identity = _identify(element) if element is not None else ("Project", project_name)
    return verify_rendered(rendered, exempt=[identity] if identity else ())


def verify_scene(scene_name: str) -> RoundTripReport:
    """The Scene about to go to the device, and the Tasks its elements fire.

    No overrides and no exemptions: the Scene renderer only deep-copies, and the edited
    Scene has already been applied to the live tree by the time a save reads it (see
    sceneedit.apply_edited_scene_to_live_tree), so every object in the document -- the Scene
    included -- has a live element that must match it exactly.
    """
    from maptasker.src import sceneedit  # noqa: PLC0415

    try:
        rendered = sceneedit.render_standalone_scene_xml(scene_name)
    except (ValueError, AttributeError) as render_error:
        return RoundTripReport(error=f"the Scene could not be rendered ({render_error})")

    return verify_rendered(rendered)
