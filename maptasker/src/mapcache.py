"""mapcache: don't build the Map again when nothing it is built from has changed."""

#! /usr/bin/env python3

#                                                                                       #
# mapcache: recognise a Map that has already been built, and let it stand.              #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
# WHY THIS EXISTS
#
# Building the Map for a large configuration is the longest wait in the program -- every
# Project, Profile, Task, Scene and Task action turned into html, tens of thousands of
# lines of it -- and a session spends much of its time asking for that same Map over and
# over.  Closing the window and opening it again, going to the Diagram and coming back,
# and above all clicking a Health Check or Variable Cross-Reference finding, which builds
# a Map for no other reason than to jump to a line in it.  Nothing about the
# configuration has changed in any of those cases, and the work is done again anyway.
#
# So: remember what the Map on disk was built from, and if that is still exactly what
# would be built now, show the one that is already there.
#
# HOW IT KNOWS, AND WHY IT IS NOT A GUESS
#
# Two digests, both taken from the real thing rather than from anything that has to be
# kept up to date by hand:
#
#   THE CONFIGURATION -- every tag, every attribute and every piece of text of every
#   Project, Profile, Task and Scene the Map draws from, plus the parts of the file that
#   are not one of those (the global variables it lists, Tasker's own preferences).  Any
#   edit anywhere in the loaded configuration changes it.  That is the whole point of
#   hashing the content instead of trusting a "something changed" flag: a flag has to be
#   set by every writer, and the one writer that forgets leaves a Map on screen that does
#   not match the configuration it claims to show.  There is nothing to forget here.
#
#   THE SETTINGS -- the whole of program_arguments and the whole colour table, not a
#   chosen few.  A setting nobody thought of when this was written can only ever cause a
#   rebuild that was not needed, which costs time; leaving one out could show the user a
#   Map that does not match what they asked for, which is a bug.  The list is therefore
#   not curated.
#
# WHAT IT DELIBERATELY DOES NOT DO
#
# It does not survive the program.  The record is held in memory, so the first Map of
# every session is always built from scratch, and a MapTasker.html left over from a
# previous session is never trusted -- nothing here has to reason about whether the file
# on disk came from this configuration or last week's.
#
# It also gives up rather than think: if the file it remembers is not there any more, or
# has been written to since, it says no and the Map is built again.
#
import hashlib
import os
from typing import TYPE_CHECKING

from maptasker.src.primitem import PrimeItems

if TYPE_CHECKING:
    import defusedxml.ElementTree

# The four tables hold these, so walking the root's children as well would hash every one
# of them twice -- on a large configuration that is the whole cost of this doubled.
OBJECT_TAGS = frozenset({"Project", "Profile", "Task", "Scene"})

# The tables the Map draws its objects from, in the order it draws them.
OBJECT_TABLES = ("all_projects", "all_profiles", "all_tasks", "all_scenes")

# Keeps one value's end from reading as the next one's beginning: a tag "ab" followed by
# text "c" must not hash the same as a tag "a" followed by text "bc".
SEPARATOR = b"\x00"
SEPARATOR_TEXT = "\x00"

# What the Map now on disk was built from: (configuration digest, settings digest, file
# path, the file's size and modification time, how many output lines went into it).
_remembered: tuple | None = None


def _absorb(digest: object, element: "defusedxml.ElementTree.Element | None") -> None:
    """Fold one xml element, and everything inside it, into the digest.

    Gathered into one string per element and hashed in a single go rather than fed to the
    digest piece by piece.  A configuration holds a few hundred thousand of those pieces,
    and handing each one to the digest separately costs half as long again as joining
    them first.  An element's attributes go in as the dictionary's own repr for the same
    reason: written out by name and value they are three operations each.
    """
    if element is None:
        return
    parts = []
    append = parts.append
    for node in element.iter():
        append(node.tag)
        if node.text:
            append(node.text)
        if node.attrib:
            append(repr(node.attrib))
    digest.update(SEPARATOR_TEXT.join(parts).encode())
    digest.update(SEPARATOR)


def configuration_digest() -> str:
    """What the loaded configuration is, as the Map sees it.

    Taken from the object tables rather than from the xml root because those are what the
    Map is generated from -- an element the tables hold is drawn whether or not the tree
    still has it, and the digest has to follow the drawing.
    """
    digest = hashlib.blake2b(digest_size=16)
    tables = PrimeItems.tasker_root_elements or {}
    for table_name in OBJECT_TABLES:
        digest.update(table_name.encode())
        digest.update(SEPARATOR)
        # In the table's own order, which is the order the Map draws them in: two
        # configurations holding the same objects in a different order are two different
        # Maps.
        for key, record in (tables.get(table_name) or {}).items():
            digest.update(str(key).encode())
            digest.update(SEPARATOR)
            digest.update(str(record.get("name", "")).encode())
            digest.update(SEPARATOR)
            _absorb(digest, record.get("xml"))

    # Everything in the file that is not one of those objects: the global variables the
    # Map lists and Tasker's own preferences, both of which it can be asked to display.
    for child in PrimeItems.xml_root if PrimeItems.xml_root is not None else ():
        if child.tag not in OBJECT_TAGS:
            _absorb(digest, child)

    return digest.hexdigest()


def settings_digest() -> str:
    """What was asked for: every runtime setting and every colour, left uncurated."""
    digest = hashlib.blake2b(digest_size=16)
    for name, value in sorted(PrimeItems.program_arguments.items()):
        digest.update(f"{name}={value!r}".encode())
        digest.update(SEPARATOR)
    colors = PrimeItems.colors_to_use
    for name, value in sorted((colors or {}).items()) if isinstance(colors, dict) else ():
        digest.update(f"{name}={value!r}".encode())
        digest.update(SEPARATOR)
    return digest.hexdigest()


def digests() -> tuple[str, str]:
    """What a Map built right now would be built from: (configuration, settings).

    Taken at the START of a build and remembered as that build's answer, because a build
    is not quite a bystander to either of them.  The first Map of a session settles the
    configuration as it goes -- an unnamed Profile is given the name Tasker would show
    for it, an unnamed Task the name of its first action -- and finishes by saving the
    settings, which edits them in passing.  A Map remembered against the state it left
    behind would be handed back for a request whose inputs are not the ones that produced
    it, and the second Map of a session really does differ from the first because of it.
    Against the state it started from, a hit means what it says: nothing that went into
    this file has changed since.
    """
    return (configuration_digest(), settings_digest())


def _file_identity(path: str) -> tuple | None:
    """The file's size and modification time, or None if it is not there."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (status.st_size, status.st_mtime_ns)


def remember(path: str, output_lines: int, built_from: tuple[str, str]) -> None:
    """Record that the Map at `path` was built from `built_from` (see digests())."""
    identity = _file_identity(path)
    if identity is None:  # It was not written after all; nothing to stand on.
        forget()
        return
    global _remembered  # noqa: PLW0603
    _remembered = (built_from[0], built_from[1], path, identity, output_lines)


def is_current(path: str, wanted: tuple[str, str]) -> bool:
    """Is the Map at `path` the one that building `wanted` would produce?"""
    if _remembered is None:
        return False
    configuration, settings, remembered_path, identity, _ = _remembered
    return path == remembered_path and (configuration, settings) == wanted and _file_identity(path) == identity


def output_lines() -> int:
    """How many output lines went into the Map being reused (0 when nothing is held)."""
    return _remembered[4] if _remembered else 0


def forget() -> None:
    """Drop the record, so the next Map is built from scratch."""
    global _remembered  # noqa: PLW0603
    _remembered = None
