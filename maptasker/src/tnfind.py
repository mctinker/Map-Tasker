"""tnfind: find the TaskerNet shares the Projects, Profiles and Tasks you already have came from."""

#! /usr/bin/env python3

#                                                                                        #
# tnfind: link what is already in the configuration to its TaskerNet share, without the  #
#         user having to find and paste each address.                                    #
#                                                                                        #
# WHAT TASKERNET WILL AND WILL NOT TELL US                                                #
#                                                                                        #
# TaskerNet cannot be searched by name.  Its public listing can only be paged through, 12  #
# shares at a time (shares/public, with a pageToken), each with its name, kind, address     #
# and download count; the only filter is by tag.  So finding a share for a name means      #
# having the listing, and this crawls it -- slowly, with a Stop, and once: the answer is    #
# kept (taskernet_catalogue.json, beside the saved links) and reused for a week.           #
#                                                                                        #
# A NAME IS NOT AN IDENTITY                                                               #
#                                                                                        #
# Names repeat across publishers.  Among the first 720 shares in the listing, "Weather",    #
# "Telegram", "Apps" and "WiFi Connect" were each shared by more than one author.  Linking   #
# on a name would attach a Project to a stranger's share of the same name and then offer     #
# the stranger's changes as updates to it.  So a name only NOMINATES a share; what decides   #
# is the share's content, set beside yours:                                                #
#                                                                                        #
#   signature   every value an object holds -- action codes and arguments, conditions, names  #
#               -- as a set, leaving out what differs between any two copies of one thing:     #
#               ids, dates, links by id, flags.                                            #
#   score       how much of the two sets they share (Jaccard).  An imported copy scores       #
#               near 1 -- measured on three real shares, 0.9 or better -- and a different     #
#               share of the same name scores near 0.                                        #
#                                                                                        #
# A STRONG match is linked automatically.  A POSSIBLE one (same name, some of the content)   #
# is listed for the user to tick.  Anything lower is counted and left alone.  Two strong      #
# matches from different publishers within a hair of each other -- a fork -- are not          #
# decided between: both are listed as possible, since choosing for the user is exactly the   #
# wrong guess to make quietly.                                                            #
#                                                                                        #
# WHAT A LINK MADE THIS WAY MEANS                                                         #
#                                                                                        #
# The same as one made by hand: the version published now is taken to be the one the user    #
# has (see tnupdate.accept), and kept as the baseline later updates are compared with.  It   #
# is marked `auto` so the dialog can say it was found and not typed, and Unlink takes it     #
# away like any other.                                                                    #
#                                                                                        #
# WHAT LEAVES THE MACHINE                                                                 #
#                                                                                        #
# Requests to taskernet.com for the public listing and for each candidate share -- the      #
# same two public endpoints tnupdate uses.  Nothing of the user's is sent, and nothing is     #
# read from their configuration but names, which stay here.                                 #
#                                                                                        #
# No GUI import.  Reads PrimeItems.tasker_root_elements; writes the link file and the        #
# catalogue; the dialog is guiwins_tnfind.                                                 #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import defusedxml.ElementTree as DefusedET

from maptasker.src import clock, timeline, tnupdate
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    import threading
    from collections.abc import Callable, Iterable
    from xml.etree.ElementTree import Element

    from maptasker.src.primitem import RunState

CATALOGUE_FILE = "taskernet_catalogue.json"
_CATALOGUE_VERSION = 1

# The listing is reused this long.  New shares appear all the time, but a name already linked or
# already matched does not change, and a user who wants the new ones presses 'fetch again'.
CATALOGUE_MAX_AGE_DAYS = 7

# Be a polite client: a pause between pages, and a ceiling on how many are read.  3000 pages is
# 36,000 shares, several times what the listing held when this was written.
_PAGE_DELAY_SECONDS = 0.2
_MAX_PAGES = 3000

# The most shares of one name that are downloaded to check, most-downloaded first, and the most
# downloaded in one scan altogether.  A name like "Setup" nominates dozens of unrelated shares;
# the popular ones are the likeliest to be what was imported.
_MAX_CANDIDATES_PER_OBJECT = 5
_MAX_DOWNLOADS = 200

# What a score has to be.  See the header; the thresholds sit well clear of the measured extremes.
STRONG_SCORE = 0.75
POSSIBLE_SCORE = 0.35
# A share with fewer values than this is too small to be sure of: a one-action Task shares most
# of its values with any other one-action Task.  It can still be a POSSIBLE match.
_MIN_VALUES = 4
# Two strong scores closer than this are a fork, not a winner.
_TIE = 0.05

# What is left out of a signature: what is different between two copies of the same thing.
_SIGNATURE_SKIP = re.compile(r"^(id|cdate|edate|mdate|pids|tids|flags|clp|limit|Share|mid\d+)$")

# The kinds of local object that can be matched, each with the table that holds it.
_LOCAL_TABLES = (
    (tnupdate.PROJECT, "all_projects"),
    (tnupdate.PROFILE, "all_profiles"),
    (tnupdate.TASK, "all_tasks"),
    (tnupdate.SCENE, "all_scenes"),
)


# ##################################################################################
# The listing.
# ##################################################################################


class CatalogueEntry(NamedTuple):
    """One public share: where it is, and how often it has been downloaded (a hint to which is genuine)."""

    ref: tnupdate.ShareRef
    downloads: int


@dataclass
class Catalogue:
    """The public listing as far as it has been read.

    `complete` is False when the crawl was stopped or TaskerNet stopped answering part-way: what
    was read is still used, and the dialog says it is a part.  `problem` is why it stopped, if it
    did not simply reach the end.
    """

    entries: list[CatalogueEntry] = field(default_factory=list)
    fetched: str = ""
    complete: bool = False
    problem: str = ""

    @property
    def age_days(self) -> float:
        """How long ago it was read, or infinity when it never was."""
        try:
            return (clock.now() - datetime.fromisoformat(self.fetched)).total_seconds() / 86400
        except ValueError:
            return float("inf")

    def by_name(self) -> dict[tuple[str, str], list[CatalogueEntry]]:
        """Shares by (kind, lower-cased name), most downloaded first."""
        grouped: dict[tuple[str, str], list[CatalogueEntry]] = {}
        for entry in self.entries:
            grouped.setdefault((entry.ref.kind, entry.ref.name.casefold()), []).append(entry)
        for entries in grouped.values():
            entries.sort(key=lambda item: -item.downloads)
        return grouped


def catalogue_path() -> Path | None:
    """Where the listing is kept: beside the saved links.  None when there is nowhere."""
    folder = timeline.history_folder(create=True)
    return folder / CATALOGUE_FILE if folder is not None else None


def load_catalogue(path: Path | None) -> Catalogue | None:
    """The listing kept at `path`, or None if there is none or it cannot be read.  Never raises."""
    if path is None or not path.is_file():
        return None
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        entries = [
            CatalogueEntry(
                tnupdate.ShareRef(user, share_id, share_id.split(":", 1)[0], share_id.split(":", 1)[1]), int(downloads)
            )
            for user, share_id, downloads in saved["shares"]
        ]
        return Catalogue(entries, str(saved.get("fetched", "")), bool(saved.get("complete")))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        logger.error(f"TaskerNet catalogue could not be read: {error}")
        return None


def save_catalogue(catalogue: Catalogue, path: Path | None) -> bool:
    """Keep the listing.  False, and logged, when it cannot be -- the scan goes on with it in memory."""
    if path is None:
        return False
    text = json.dumps(
        {
            "version": _CATALOGUE_VERSION,
            "fetched": catalogue.fetched,
            "complete": catalogue.complete,
            "shares": [[entry.ref.user, entry.ref.share_id, entry.downloads] for entry in catalogue.entries],
        },
        separators=(",", ":"),
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(text)
        Path(temporary).replace(path)
    except OSError as error:
        logger.error(f"TaskerNet catalogue could not be saved: {error}")
        return False
    return True


LISTING = "listing"
COMPARING = "comparing"


@dataclass
class Progress:
    """What a scan is doing, for the dialog to read from another thread.  Plain attributes: one writer, one reader."""

    text: str = ""
    done: int = 0
    total: int = 0
    # "listing" while TaskerNet's list of shares is being read, "comparing" once it is being set beside yours.
    phase: str = LISTING


def _entries_of(answer: dict) -> list[CatalogueEntry]:
    """The shares in one page of the listing.  One that does not read as a share is skipped, not fatal."""
    found = []
    for share in answer.get("shares") or []:
        try:
            found.append(
                CatalogueEntry(tnupdate.parse_link(str(share.get("url") or "")), int(share.get("downloads") or 0))
            )
        except (tnupdate.TaskerNetError, AttributeError, TypeError, ValueError):
            continue
    return found


def crawl_catalogue(progress: Progress, stop: threading.Event) -> Catalogue:
    """Read the public listing page by page until it ends, is stopped, or TaskerNet stops answering."""
    entries: dict[tuple[str, str], CatalogueEntry] = {}
    catalogue = Catalogue(fetched=clock.now().isoformat())
    token = ""
    for page in range(1, _MAX_PAGES + 1):
        if stop.is_set():
            break
        try:
            answer = tnupdate.fetch_public_page(token)
        except tnupdate.TaskerNetError as error:
            catalogue.problem = str(error)
            break
        for entry in _entries_of(answer):
            entries[(entry.ref.user, entry.ref.share_id)] = entry
        progress.text = f"Reading TaskerNet's list of shares: page {page}, {len(entries)} shares so far..."
        following = str(answer.get("pageToken") or "")
        if not following or following == token:
            catalogue.complete = True
            break
        token = following
        time.sleep(_PAGE_DELAY_SECONDS)
    catalogue.entries = list(entries.values())
    return catalogue


# ##################################################################################
# What the configuration has.
# ##################################################################################


class Candidate(NamedTuple):
    """One local object and the public shares of the same kind and name that might be where it came from."""

    kind: str
    name: str
    entries: list[CatalogueEntry]


def candidates(state: RunState, book: tnupdate.LinkBook, catalogue: Catalogue) -> list[Candidate]:
    """Every Project, Profile, Task and Scene of yours with a public share of the same name, not already linked.

    Projects first, so that a Project linked in full can leave its own members alone (see scan).  An
    object with no name of its own -- Tasker shows an unnamed Profile by its conditions -- has
    nothing to match by and is not here.
    """
    listing = catalogue.by_name()
    found = []
    for kind, table_name in _LOCAL_TABLES:
        for name in _own_names(kind, state.tasker_root_elements.get(table_name, {})):
            if (kind, name) in book.links:
                continue
            entries = listing.get((kind, name.casefold()), [])
            if entries:
                found.append(Candidate(kind, name, entries[:_MAX_CANDIDATES_PER_OBJECT]))
    return found


def _own_names(kind: str, table: dict) -> list[str]:
    """The names objects of one kind were given -- not the ones Tasker makes up for those with none."""
    if kind in (tnupdate.PROJECT, tnupdate.SCENE):
        return sorted(table)
    names = {
        (entry["xml"].findtext("nme") or "").strip()
        for entry in table.values()
        if isinstance(entry, dict) and "xml" in entry
    }
    return sorted(name for name in names if name)


# ##################################################################################
# Does the share match?
# ##################################################################################


def signature(elements: Iterable[Element]) -> set[str]:
    """Every value the elements hold, as 'tag=value', leaving out what two copies of one thing do not share.

    Ids and dates differ between any two copies, and the Project's and Profile's lists of ids and
    links by id differ with them; <flags>, <clp> and <limit> are Tasker's own bookkeeping.  What is
    left is names, action codes and arguments, conditions -- what the object IS.
    """
    values: set[str] = set()

    def walk(node: Element) -> None:
        if _SIGNATURE_SKIP.match(node.tag):
            return
        text = (node.text or "").strip()
        if text:
            values.add(f"{node.tag}={text}")
        if node.get("val"):
            values.add(f"{node.tag}={node.get('val')}")
        for child in node:
            walk(child)

    for element in elements:
        walk(element)
    return values


def similarity(shared: set[str], yours: set[str]) -> float:
    """How much of what either holds, both hold.  1.0 is the same content; 0.0 has nothing in common."""
    union = shared | yours
    return len(shared & yours) / len(union) if union else 0.0


def _share_elements(xml_text: str) -> list[Element]:
    """The objects a share holds, parsed with defusedxml because they come from a stranger."""
    try:
        root = DefusedET.fromstring(xml_text)
    except (DefusedET.ParseError, ValueError):
        return []
    return [child for child in root if child.tag in {"Project", "Profile", "Task", "Scene"}]


def _local_elements(kind: str, name: str, state: RunState) -> list[Element]:
    """What the loaded configuration holds of one object: itself, and what goes with it (see tnupdate.local_scope)."""
    scope = tnupdate.scope_of(kind, name, state.tasker_root_elements)
    if scope is None:
        return []
    return [entry["xml"] for table in scope.values() for entry in table.values()]


@dataclass
class Match:
    """A share that might be where an object came from, and how well its content agrees."""

    kind: str
    name: str
    ref: tnupdate.ShareRef
    score: float
    downloads: int
    xml_text: str = ""
    auto: bool = False
    # When the author published this version, in milliseconds; 0 until asked for, or if TaskerNet will not say.
    # The listing does not carry it, so it costs one small request per match that is going to be shown.
    published_ms: int = 0

    @property
    def strong(self) -> bool:
        """Whether the content agrees well enough to link without asking."""
        return self.score >= STRONG_SCORE


def score_share(kind: str, name: str, entry: CatalogueEntry, xml_text: str, state: RunState) -> Match:
    """Set one share's content beside the object it was nominated for.

    A share too small to be sure of is held under STRONG however well it agrees: see _MIN_VALUES.
    """
    shared = signature(_share_elements(xml_text))
    score = similarity(shared, signature(_local_elements(kind, name, state)))
    if len(shared) < _MIN_VALUES:
        score = min(score, STRONG_SCORE - 0.01)
    return Match(kind, name, entry.ref, round(score, 3), entry.downloads, xml_text)


# ##################################################################################
# The scan.
# ##################################################################################


@dataclass
class ScanResult:
    """What a scan found.  `linked` are already in the book; `possible` are for the user to choose from."""

    linked: list[Match] = field(default_factory=list)
    possible: list[Match] = field(default_factory=list)
    different: int = 0
    checked: int = 0
    catalogue_size: int = 0
    catalogue_complete: bool = False
    catalogue_age_days: float = 0.0
    stopped: bool = False
    # Stop was pressed while the list of shares was being read; what had been read was compared all the same.
    listing_stopped: bool = False
    problem: str = ""


def link_match(book: tnupdate.LinkBook, match: Match, *, auto: bool) -> tnupdate.Link:
    """Link a matched share to the object it matched, the way reviewing it for the first time would.

    The version published now is taken as the one the user has, and the XML already in hand is kept
    as the baseline, so the next update is compared with it.  The publish date is asked for here
    because the listing does not carry it; if TaskerNet will not say, the link is made unreviewed
    and the first Review sets it.
    """
    link = book.add(match.kind, match.name, match.ref.link)
    link.auto = auto
    try:
        info = tnupdate.fetch_info(match.ref)
    except tnupdate.TaskerNetError as error:
        link.problem = str(error)
    else:
        link.latest_ms = link.seen_ms = match.published_ms = info.published_ms
        link.share_name = info.name or link.share_name
        link.checked = clock.now().isoformat()
        if match.xml_text:
            book.save_baseline(link, match.xml_text)
    book.save()
    return link


def _decide(scored: list[Match]) -> tuple[Match | None, list[Match]]:
    """(the one to link, or None; the ones to offer instead) for one object's scored shares, best first."""
    best = scored[0]
    rivals = [other for other in scored[1:] if other.strong and best.score - other.score < _TIE]
    if best.strong and not rivals:
        return best, []
    return None, [match for match in scored if match.score >= POSSIBLE_SCORE]


def scan(
    state: RunState,
    book: tnupdate.LinkBook,
    *,
    refresh: bool,
    progress: Progress,
    stop: threading.Event,
    path: Path | None = None,
    fetch: Callable[[tnupdate.ShareRef], str] | None = None,
) -> ScanResult:
    """Find a share for each object that has a public one of its name, and link those that agree in content.

    Slow -- a crawl the first time, then a download per candidate -- so the dialog runs it on a worker
    thread and watches `progress`.  Safe to run there: it only READS the configuration.  `stop` ends it
    at the next step; what was already linked stays linked.  Pressed while the list of shares is still being
    read, it ends only the reading: what was read so far is compared with what you have, and `stop` is
    cleared so that a second press can end the comparing.
    """
    path = path if path is not None else catalogue_path()
    fetch = fetch or tnupdate.fetch_xml
    result = ScanResult()
    catalogue = _catalogue(path, refresh=refresh, progress=progress, stop=stop)
    result.catalogue_size = len(catalogue.entries)
    result.catalogue_complete = catalogue.complete
    result.catalogue_age_days = catalogue.age_days
    result.problem = catalogue.problem
    if not catalogue.entries:
        result.stopped = stop.is_set()
        return result
    if stop.is_set():
        # Stopped while the list was being read.  That ends the READING, not the scan: what was read is
        # compared with what you have, and a second Stop (the event is cleared for it) ends that too.
        result.listing_stopped = True
        stop.clear()

    progress.phase = COMPARING
    work = candidates(state, book, catalogue)
    progress.total, progress.done = len(work), 0
    if result.listing_stopped:
        progress.text = (
            f"Stopped reading TaskerNet's list; comparing yours with the {len(catalogue.entries)} shares read..."
        )
    downloads = 0
    covered: set[tuple[str, str]] = set()
    for candidate in work:
        if stop.is_set():
            result.stopped = True
            break
        progress.done += 1
        if (candidate.kind, candidate.name) in covered:
            continue
        progress.text = (
            f"Checking {candidate.kind} '{candidate.name}' against TaskerNet ({progress.done} of {progress.total})..."
        )
        scored, spent = _score_all(candidate, state, fetch, _MAX_DOWNLOADS - downloads, stop)
        downloads += spent
        result.checked += 1
        if not scored:
            if not stop.is_set():
                result.problem = result.problem or "Some shares could not be downloaded."
            continue
        _record(candidate, scored, result, book, covered, state)
        if downloads >= _MAX_DOWNLOADS:
            result.problem = f"Stopped after {_MAX_DOWNLOADS} downloads; scan again to continue."
            break
    result.stopped = result.stopped or stop.is_set()
    return result


def _catalogue(path: Path | None, *, refresh: bool, progress: Progress, stop: threading.Event) -> Catalogue:
    """The listing from the file if it is young enough, else read from TaskerNet (and kept)."""
    kept = None if refresh else load_catalogue(path)
    # Only a listing that was read to its end is reused.  One cut short -- stopped, or TaskerNet went away --
    # holds the most-downloaded shares and none of the rest, and keeping it for a week would be
    # keeping the scan from ever finishing.
    if kept is not None and kept.complete and kept.age_days <= CATALOGUE_MAX_AGE_DAYS:
        progress.text = f"Using the list of shares read {kept.age_days:.0f} day(s) ago."
        return kept
    fresh = crawl_catalogue(progress, stop)
    if fresh.entries:
        save_catalogue(fresh, path)
    # A listing cut short is still better than none, and a younger partial one than an older one
    # only if it is larger; either way, what is read is what the scan uses.
    return fresh if fresh.entries or kept is None else kept


def _score_all(
    candidate: Candidate,
    state: RunState,
    fetch: Callable[[tnupdate.ShareRef], str],
    allowance: int,
    stop: threading.Event,
) -> tuple[list[Match], int]:
    """Download and score each share nominated for one object, best score first.  (matches, downloads made)."""
    scored: list[Match] = []
    spent = 0
    for entry in candidate.entries:
        if stop.is_set() or spent >= allowance:
            break
        spent += 1
        try:
            xml_text = fetch(entry.ref)
        except tnupdate.TaskerNetError as error:
            logger.info(f"TaskerNet share {entry.ref.share_id} could not be fetched: {error}")
            continue
        scored.append(score_share(candidate.kind, candidate.name, entry, xml_text, state))
    return sorted(scored, key=lambda match: -match.score), spent


def _record(
    candidate: Candidate,
    scored: list[Match],
    result: ScanResult,
    book: tnupdate.LinkBook,
    covered: set[tuple[str, str]],
    state: RunState,
) -> None:
    """Link the winner, or offer the near ones, or count the object as having nothing that agrees."""
    winner, offered = _decide(scored)
    if winner is not None:
        link_match(book, winner, auto=True)
        winner.auto = True
        result.linked.append(winner)
        if candidate.kind == tnupdate.PROJECT:
            # Its Profiles and Tasks are in the share just linked; separate shares of them add nothing.
            covered.update(_members(candidate.name, state))
    elif offered:
        _date(offered)
        result.possible.extend(offered)
    else:
        result.different += 1


def _date(matches: list[Match]) -> None:
    """Ask TaskerNet when each of these shares was published, so the user choosing between them can see.

    One small request each, and only for the ones that are going to be offered.  A share TaskerNet will not
    describe is left undated rather than dropped: the choice is still the user's.
    """
    for match in matches:
        try:
            match.published_ms = tnupdate.fetch_info(match.ref).published_ms
        except tnupdate.TaskerNetError as error:
            logger.info(f"TaskerNet share {match.ref.share_id} has no date to show: {error}")


def _members(project: str, state: RunState) -> set[tuple[str, str]]:
    """(kind, name) of every named Profile, Task and Scene in a Project."""
    scope = tnupdate.scope_of(tnupdate.PROJECT, project, state.tasker_root_elements)
    if scope is None:
        return set()
    members: set[tuple[str, str]] = set()
    for kind, table_name in _LOCAL_TABLES[1:]:
        for entry in scope[table_name].values():
            name = (entry["xml"].findtext("nme") or "").strip() or (entry["name"] if kind == tnupdate.SCENE else "")
            if name:
                members.add((kind, name))
    return members
