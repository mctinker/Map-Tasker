"""tnupdate: has the author of a TaskerNet share published a newer version of it?"""

#! /usr/bin/env python3

#                                                                                        #
# tnupdate: keep a Project, Profile, Task or Scene linked to the TaskerNet share it came  #
#           from, notice when the author publishes a newer version, and work out what     #
#           taking it would change.                                                       #
#                                                                                        #
# WHY A LINK HAS TO BE SAVED HERE                                                         #
#                                                                                        #
# A Tasker backup does not say where anything came from.  The <Share> element an imported  #
# object keeps holds only its description, categories and tags (<d>, <g>, <t>, <b>, <p>);  #
# there is no share id, user or version in it.  So the only way to know which TaskerNet    #
# share an object came from is to be told, and this module remembers what it was told in  #
# a small file beside the configuration history (see LinkBook).                           #
#                                                                                        #
# WHAT IS ASKED OF TASKERNET, AND WHAT IS NOT                                             #
#                                                                                        #
# TaskerNet has no documented API.  The share web page is a small client that reads two    #
# unauthenticated JSON endpoints under taskernet.com/_ah/api/datashare/v1/, and those two   #
# are all this uses -- the same two requests a browser makes to show the page to somebody   #
# who is not signed in:                                                                    #
#                                                                                        #
#   shares/<user>/<id>      what is published: its publish date, name and description.     #
#                           This is all a routine "is there something newer?" check asks.  #
#   sharedata/<user>/<id>   the share itself, as taskerproject:// (or taskerprofile:// and  #
#                           so on) followed by base64 of gzipped Tasker XML.  Asked for     #
#                           only when the user presses Review.                             #
#                                                                                        #
# Neither request carries anything of the user's: the share's address is the only thing    #
# that leaves the machine.  The page's own view and download counters are never switched   #
# on (countView, countDownload), so checking does not inflate the author's numbers.  The   #
# endpoints are undocumented and can change without notice; every failure is reported in   #
# words rather than raised, and none of it can damage the configuration.                   #
#                                                                                        #
# WHY THE SHARE'S IDS ARE REWRITTEN BEFORE ANYTHING IS COMPARED                           #
#                                                                                        #
# Tasker renumbers every Task and Profile when it imports a share, so the share's "File     #
# List" is Profile 312 and the importer's is Profile 780.  xmldiff identifies objects by    #
# id, so compared as published the two would have nothing in common and every object would #
# be reported removed and added.  align_share gives each of the share's objects the id of   #
# the object of the same name in the linked item, which is the one change that lets the     #
# existing Compare and Restore From History machinery -- xmldiff, maprestore, maprefac --   #
# do the rest.  Taking an update is therefore a restore from the share, one object at a    #
# time, previewed first, and one press of Undo: see maprestore's header for why it is never #
# a merge.                                                                                 #
#                                                                                        #
# WHAT IS OFFERED: THE AUTHOR'S CHANGES, NOT EVERY DIFFERENCE                              #
#                                                                                        #
# Set beside your copy, a share differs in ways nobody chose: Tasker rewrites a Profile on   #
# import (it drops <limit> and <clp>, and flips a bit of <flags>), and a newer Tasker adds   #
# default arguments an older one did not write.  Offering every one of those would bury the  #
# change the author actually made.  So when the version you last accepted is on file          #
# (LinkBook.save_baseline), the two published versions are compared with each other -- both   #
# written by the author's own Tasker, with the author's own stable ids -- and only objects    #
# that comparison says the author changed are offered.  What is taken is the author's latest  #
# version of the object, except that your Profile's enabled/disabled state is kept, since     #
# that is yours.  Without a baseline, everything that differs is listed and the dialog says   #
# why that list is longer.                                                                  #
#                                                                                        #
# WHAT THIS CANNOT TELL YOU, SAID PLAINLY                                                 #
#                                                                                        #
#   * "Newer version published" is decided by the publish date alone.                        #
#   * A change you made to an object the author also changed is overwritten by taking it --   #
#     which the preview shows -- and one press of Undo puts it back.                          #
#   * Objects are matched by name, then by what a matched Profile runs.  A Profile with no    #
#     name cannot be matched, and a Task the author renames is followed only if you had      #
#     accepted an earlier version.                                                          #
#   * Your own rename of the linked item is not treated as the author's: the share's top    #
#     object is given the name yours has.                                                    #
#                                                                                        #
# No GUI import.  Reads PrimeItems.tasker_root_elements and the network, writes only the    #
# link file; the dialog is guiwins_tnupdate.                                              #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                              #
#
from __future__ import annotations

import base64
import binascii
import contextlib
import gzip
import hashlib
import json
import os
import re
import tempfile
import zlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import parse_qs, quote, urlparse
from xml.etree.ElementTree import Element, tostring

import defusedxml.ElementTree as DefusedET
import httpx

from maptasker.src import clock, diffload, maprestore, sessundo, timeline, xmldiff
from maptasker.src.sysconst import MY_VERSION, logger
from maptasker.src.xmldiff import Configuration

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.primitem import RunState

# The four kinds of thing TaskerNet shares, as it spells them at the front of a share's id.
PROJECT, PROFILE, TASK, SCENE = "Project", "Profile", "Task", "Scene"
KINDS = (PROJECT, PROFILE, TASK, SCENE)

# The only places a share's address may point.  A link is typed or pasted by the user, and
# something that merely looks like one must not make MapTasker contact another site.
_HOSTS = frozenset({"taskernet.com", "www.taskernet.com"})
_API_ROOT = "https://taskernet.com/_ah/api/datashare/v1/"
_SHARE_PAGE = "https://taskernet.com/shares/"

# Seconds to wait for TaskerNet, and the most of an answer that is read.  A share is a few
# hundred kilobytes at most in practice (the Http Server Example, one of the larger, is 17 KB
# of JSON for 153 KB of XML); the limits are for a server that answers with something else.
_TIMEOUT_SECONDS = 20.0
_INFO_LIMIT = 4 * 1024 * 1024
_DATA_LIMIT = 48 * 1024 * 1024
_XML_LIMIT = 128 * 1024 * 1024

# What a share's data starts with: "taskerproject://", "taskerprofile://", ...
_DATA_SCHEME = re.compile(r"^tasker[a-z]+://", re.IGNORECASE)

# An up-to-date check is repeated no sooner than this, so opening the dialog twice in a minute
# is one trip to TaskerNet rather than two.
RECHECK_AFTER_SECONDS = 6 * 60 * 60

# How a link stands, in the words the dialog draws.  UNREVIEWED is a link whose share has
# never been set beside the copy, so there is no version to say anything is newer than.
UNCHECKED = "unchecked"
UNREVIEWED = "unreviewed"
CURRENT = "current"
UPDATE = "update"

# The remembered links, in the same place as the configuration history: both are the
# program's own remembered state rather than output (see outdir), and both are about the
# configuration files the user has loaded.  A folder of baselines sits beside the file.
LINKS_FILE = "taskernet_links.json"
BASELINES_FOLDER = "taskernet_baselines"
_LINKS_VERSION = 1


class TaskerNetError(Exception):
    """Something a person can act on: a bad link, a share that is gone, a file that is not Tasker XML."""


class TaskerNetOfflineError(TaskerNetError):
    """TaskerNet could not be reached at all -- offline, timed out, or answering with something else."""


# ##################################################################################
# A share's address.
# ##################################################################################


class ShareRef(NamedTuple):
    """Which share: the publisher's id, the share's own id ("Project:Name"), and the two halves of that."""

    user: str
    share_id: str
    kind: str
    name: str

    @property
    def link(self) -> str:
        """The share's page address, in the canonical spelling TaskerNet itself produces."""
        return f"{_SHARE_PAGE}?user={quote(self.user, safe='')}&id={quote(self.share_id, safe='').replace('%20', '+')}"


def parse_link(text: str) -> ShareRef:
    """The share a TaskerNet link names.  Raises TaskerNetError, in plain words, if it is not one.

    Takes the address as the Export > As Link button in Tasker gives it:
    https://taskernet.com/shares/?user=AS35...&id=Project%3AName.  Anything else -- another
    site, a share with no user, a kind TaskerNet does not have -- is refused rather than guessed at.
    """
    try:
        parts = urlparse((text or "").strip())
    except ValueError as error:
        message = f"That does not look like a TaskerNet link ({error})."
        raise TaskerNetError(message) from error
    if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in _HOSTS:
        message = "That is not a TaskerNet share link.  It should start with https://taskernet.com/shares/?user=..."
        raise TaskerNetError(message)

    query = parse_qs(parts.query)
    # A publisher's id is base64, so it has no spaces -- but a '+' that was not escaped as %2B is
    # read back as one, and putting it back is what the id was.
    user = (query.get("user") or [""])[0].replace(" ", "+")
    share_id = (query.get("id") or [""])[0]
    kind, _, name = share_id.partition(":")
    if not user or not name:
        message = (
            "That TaskerNet link does not name a particular share.  Open the share's own page "
            "(the one with its Import button) and copy that address."
        )
        raise TaskerNetError(message)
    if kind not in KINDS:
        message = f"TaskerNet shares a Project, Profile, Task or Scene; this link is for a '{kind}'."
        raise TaskerNetError(message)
    return ShareRef(user, share_id, kind, name)


# ##################################################################################
# Asking TaskerNet.
# ##################################################################################


class ShareInfo(NamedTuple):
    """What TaskerNet says is published: when, under what name, and how it has been received."""

    published_ms: int
    name: str
    description: str
    views: int
    downloads: int


def _endpoint(what: str, ref: ShareRef) -> str:
    """One of the two datashare URLs for a share.  Both fields are escaped whole, '/' and '+' included."""
    return f"{_API_ROOT}{what}/{quote(ref.user, safe='')}/{quote(ref.share_id, safe='')}?a=0"


def _get_json(url: str, limit: int) -> dict:
    """GET `url` and return its JSON object.  The single place this module touches the network.

    No redirects are followed: the answer is either on taskernet.com or it is not an answer.
    A response is read in pieces and refused past `limit` rather than read whole.  Everything
    that goes wrong comes back as a TaskerNetError, and `TaskerNetOfflineError` where the cause
    is the connection rather than the share, so a caller can stop asking after the first.
    """
    headers = {"User-Agent": f"MapTasker/{MY_VERSION}", "Accept": "application/json"}
    body = bytearray()
    try:
        with (
            httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=False, headers=headers) as client,
            client.stream("GET", url) as response,
        ):
            status = response.status_code
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > limit:
                    message = "TaskerNet sent back far more than a share can be, so it was not read."
                    raise TaskerNetError(message)
    except httpx.HTTPError as error:
        message = f"Could not reach TaskerNet ({type(error).__name__}).  Check the connection and try again."
        raise TaskerNetOfflineError(message) from error

    if status == httpx.codes.NOT_FOUND:
        message = "TaskerNet has no share at that link.  It may have been deleted, made private, or renamed."
        raise TaskerNetError(message)
    if status != httpx.codes.OK:
        message = f"TaskerNet answered with an error (HTTP {status})."
        raise TaskerNetOfflineError(message)
    try:
        answer = json.loads(bytes(body))
    except ValueError as error:
        message = "TaskerNet answered with something other than a share."
        raise TaskerNetOfflineError(message) from error
    if not isinstance(answer, dict):
        message = "TaskerNet answered with something other than a share."
        raise TaskerNetOfflineError(message)
    return answer


def fetch_public_page(token: str = "") -> dict:
    """One page of TaskerNet's public listing: {'shares': [...12...], 'pageToken': ...}.  `token` is the last page's.

    The listing can only be paged through; it has no search.  See tnfind for what is done with it.
    """
    url = f"{_API_ROOT}shares/public?a=0" + (f"&pageToken={quote(token, safe='')}" if token else "")
    return _get_json(url, _INFO_LIMIT)


def fetch_info(ref: ShareRef) -> ShareInfo:
    """What is published at `ref` -- its publish date above all.  One small request; no XML."""
    answer = _get_json(_endpoint("shares", ref), _INFO_LIMIT)
    info = answer.get("info")
    info = info if isinstance(info, dict) else {}
    stats = info.get("stats")
    stats = stats if isinstance(stats, dict) else {}
    try:
        published = int(info.get("date") or 0)
    except (TypeError, ValueError):
        published = 0
    return ShareInfo(
        published_ms=published,
        name=str(info.get("name") or ref.name),
        description=str(info.get("description") or ""),
        views=int(stats.get("views") or 0),
        downloads=int(stats.get("downloads") or 0),
    )


def fetch_xml(ref: ShareRef) -> str:
    """The share's Tasker XML, as published.  Asked for only when the user reviews an update."""
    answer = _get_json(_endpoint("sharedata", ref), _DATA_LIMIT)
    return decode_share_data(str(answer.get("shareData") or ""))


def decode_share_data(payload: str) -> str:
    """Tasker XML out of a share's data: 'taskerproject://' + base64(gzip(XML)).

    The inflated size is capped, because a few kilobytes of gzip can expand to gigabytes and the
    text comes from a stranger.  Raises TaskerNetError for anything that is not what it should be.
    """
    scheme = _DATA_SCHEME.match(payload)
    if scheme is None:
        message = "What TaskerNet sent is not a Tasker share."
        raise TaskerNetError(message)
    try:
        packed = base64.b64decode(payload[scheme.end() :], validate=False)
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        text = inflater.decompress(packed, _XML_LIMIT + 1)
    except (binascii.Error, zlib.error, ValueError) as error:
        message = "What TaskerNet sent could not be unpacked."
        raise TaskerNetError(message) from error
    if len(text) > _XML_LIMIT or inflater.unconsumed_tail:
        message = "The share is larger than MapTasker will unpack."
        raise TaskerNetError(message)
    return text.decode("utf-8", errors="replace")


# ##################################################################################
# The remembered links.
# ##################################################################################


@dataclass
class Link:
    """One local object tied to one TaskerNet share, and what is known of the share since.

    `kind` and `name` are the LOCAL object -- what the user's configuration calls it, which
    need not be what the author does.  `seen_ms` is the publish date of the version the user
    has accepted as theirs: the date current when they linked it, moved forward when they take
    an update or say they are up to date.  `latest_ms` is the newest date TaskerNet has
    reported, and `checked` is when it said so.
    """

    kind: str
    name: str
    link: str
    seen_ms: int = 0
    latest_ms: int = 0
    checked: str = ""
    share_name: str = ""
    # Why the last check failed, or "" -- kept so the list can say so without asking again.
    problem: str = ""
    # Found by tnfind from the share's content rather than pasted by the user.
    auto: bool = False

    @property
    def ref(self) -> ShareRef:
        """The share this points at.  Raises TaskerNetError if the saved address no longer parses."""
        return parse_link(self.link)

    @property
    def key(self) -> tuple[str, str]:
        """What identifies a link: the local object it is attached to."""
        return (self.kind, self.name)

    @property
    def status(self) -> str:
        """UPDATE when TaskerNet has published after the version accepted, CURRENT once checked, else UNCHECKED."""
        if not self.latest_ms:
            return UNCHECKED
        if not self.seen_ms:
            return UNREVIEWED
        return UPDATE if self.latest_ms > self.seen_ms else CURRENT

    @property
    def due(self) -> bool:
        """Whether the last check is old enough to be worth repeating."""
        if not self.checked:
            return True
        try:
            then = datetime.fromisoformat(self.checked)
        except ValueError:
            return True
        return (clock.now() - then).total_seconds() > RECHECK_AFTER_SECONDS


class LinkBook:
    """The links, kept in one small JSON file.  Reads it once, writes it whole and atomically.

    A file that cannot be read is set aside rather than overwritten by the next save: the links
    in it were typed in by hand, and losing them to a half-written file is worse than losing
    the feature for a moment.
    """

    def __init__(self, path: Path | None) -> None:
        """`path` is None when there is nowhere to keep the file; links then live for this run only."""
        self.path = path
        self.links: dict[tuple[str, str], Link] = {}
        self.load()

    def load(self) -> None:
        """Read the file, if there is one.  Never raises."""
        self.links = {}
        if self.path is None or not self.path.is_file():
            return
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            fields = Link.__dataclass_fields__
            for item in saved.get("links", []):
                link = Link(**{key: value for key, value in item.items() if key in fields})
                self.links[link.key] = link
        except (OSError, ValueError, TypeError, AttributeError) as error:
            logger.error(f"TaskerNet links could not be read: {error}")
            self.links = {}
            with contextlib.suppress(OSError):
                self.path.replace(self.path.with_suffix(".unreadable"))

    def save(self) -> bool:
        """Write every link.  False, and logged, when it cannot be -- a failed save is not a failed check."""
        if self.path is None:
            return False
        text = json.dumps({"version": _LINKS_VERSION, "links": [asdict(link) for link in self.ordered()]}, indent=1)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write(text)
            Path(temporary).replace(self.path)
        except OSError as error:
            logger.error(f"TaskerNet links could not be saved: {error}")
            return False
        return True

    def ordered(self) -> list[Link]:
        """The links in a steady order -- kind, then name -- so the list does not shuffle between checks."""
        return sorted(self.links.values(), key=lambda link: (KINDS.index(link.kind), link.name.lower()))

    def add(self, kind: str, name: str, share: str) -> Link:
        """Attach the share at address `share` to the local `kind` called `name`, replacing any link it had.

        The publish date is not known yet, so the new link starts unchecked; the caller checks it
        straight away, which is what sets the version the user is taken to be on.
        """
        ref = parse_link(share)
        if ref.kind != kind:
            message = f"That link is for a {ref.kind} but this is a {kind}.  A link has to match the kind of thing it is attached to."
            raise TaskerNetError(message)
        link = Link(kind=kind, name=name, link=ref.link, share_name=ref.name)
        self.links[link.key] = link
        self.save()
        return link

    def remove(self, link: Link) -> None:
        """Forget a link and its baseline.  Nothing about the object it was attached to changes."""
        self.links.pop(link.key, None)
        path = self._baseline_path(link)
        if path is not None:
            with contextlib.suppress(OSError):
                path.unlink()
        self.save()

    def _baseline_path(self, link: Link) -> Path | None:
        """Where the version accepted for this link is kept, named for the link so no name needs escaping."""
        if self.path is None:
            return None
        digest = hashlib.sha256(f"{link.kind}\n{link.name}".encode()).hexdigest()[:20]
        return self.path.parent / BASELINES_FOLDER / f"{digest}.xml.gz"

    def save_baseline(self, link: Link, xml_text: str) -> bool:
        """Keep the share as the author published it, as the version the user has accepted.  False if it cannot be."""
        path = self._baseline_path(link)
        if path is None:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(xml_text.encode("utf-8")))
        except OSError as error:
            logger.error(f"TaskerNet baseline could not be saved: {error}")
            return False
        return True

    def baseline(self, link: Link) -> str | None:
        """The version last accepted, or None when there is none -- never kept, or no longer readable."""
        path = self._baseline_path(link)
        if path is None or not path.is_file():
            return None
        try:
            return gzip.decompress(path.read_bytes()).decode("utf-8")
        except (OSError, EOFError, zlib.error, UnicodeDecodeError) as error:
            logger.error(f"TaskerNet baseline could not be read: {error}")
            return None


def default_book() -> LinkBook:
    """The links kept beside the configuration history, or links for this run only if that cannot be made."""
    folder = timeline.history_folder(create=True)
    return LinkBook(folder / LINKS_FILE if folder is not None else None)


# ##################################################################################
# Checking.
# ##################################################################################


def check_link(link: Link) -> bool:
    """Ask TaskerNet what is published for one link and record the answer.  True if it could be asked.

    One small request, and nothing is downloaded: the publish date is all an "is there something
    newer?" question needs.  Which version the user has is not touched -- that is set when they
    review and accept one (see accept).
    """
    try:
        info = fetch_info(link.ref)
    except TaskerNetError as error:
        link.problem = str(error)
        return False
    link.problem = ""
    link.latest_ms = info.published_ms
    link.share_name = info.name or link.share_name
    link.checked = clock.now().isoformat()
    return True


def check_all(book: LinkBook, *, only_due: bool = False, check: Callable[[Link], bool] = check_link) -> int:
    """Check every link; return how many have a newer version waiting.

    The first failure to REACH TaskerNet stops the run -- the rest would each wait out the
    timeout to say the same thing.  A share that is merely gone, or a link that no longer
    parses, is that link's own problem and the rest are still checked.
    """
    for link in book.ordered():
        if only_due and not link.due:
            continue
        if not check(link) and "Could not reach" in link.problem:
            break
    book.save()
    return sum(1 for link in book.links.values() if link.status == UPDATE)


def describe_date(milliseconds: int) -> str:
    """A publish date as the user reads dates elsewhere in MapTasker: 07-Oct-2026 15:38."""
    if not milliseconds:
        return "unknown"
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).astimezone().strftime("%d-%b-%Y %H:%M")


# ##################################################################################
# Finding what the link is attached to, here.
# ##################################################################################

# A Profile's links to the Tasks it runs.  Tasker writes mid0 (Entry) and mid1 (Exit); the
# pattern takes any number so a Task link written under a future Tasker is renumbered too.
_TASK_LINK_TAG = re.compile(r"^mid\d+$")


def _entry_of(table: dict, key: str) -> dict | None:
    """One table's entry for `key`, or None."""
    entry = table.get(key)
    return entry if isinstance(entry, dict) else None


def _id_list(element: Element, tag: str) -> list[str]:
    """A Project's comma-separated <pids>/<tids>/<scenes>."""
    return [item.strip() for item in (element.findtext(tag) or "").split(",") if item.strip()]


def _scope_tables(link: Link, tables: dict) -> dict | None:
    """The slice of the loaded configuration this link is about, shaped like the tables it comes from.

    A Project is itself, its Profiles, its Tasks and its Scenes.  A Profile is itself and the
    Tasks it runs.  A Task or a Scene is just itself.  The entries are the live ones, shared
    rather than copied: this slice is only ever read from (xmldiff and maprestore.candidates), and
    what it is compared with is the share, so every other Project's objects must not be in it
    or they would all read as "yours only".  None when the linked object is not in the configuration.
    """
    scope: dict = {"all_projects": {}, "all_profiles": {}, "all_tasks": {}, "all_scenes": {}}
    projects, profiles = tables.get("all_projects", {}), tables.get("all_profiles", {})
    tasks, scenes = tables.get("all_tasks", {}), tables.get("all_scenes", {})

    def take(into: str, table: dict, keys: list[str]) -> None:
        for key in keys:
            entry = _entry_of(table, key)
            if entry is not None:
                scope[into][key] = entry

    if link.kind == PROJECT:
        project = _entry_of(projects, link.name)
        if project is None:
            return None
        scope["all_projects"][link.name] = project
        take("all_profiles", profiles, _id_list(project["xml"], "pids"))
        # <tids> lists the Project's NAMED Tasks.  The Tasks its Profiles run are usually
        # anonymous -- no name at all -- and are in no list, only in the Profile's own links.
        take("all_tasks", tasks, [*_id_list(project["xml"], "tids"), *_run_by(scope["all_profiles"])])
        take("all_scenes", scenes, _id_list(project["xml"], "scenes"))
    elif link.kind == PROFILE:
        profile_id = _id_by_name(profiles, link.name)
        if profile_id is None:
            return None
        scope["all_profiles"][profile_id] = profiles[profile_id]
        take("all_tasks", tasks, _run_by(scope["all_profiles"]))
    elif link.kind == TASK:
        task_id = _id_by_name(tasks, link.name)
        if task_id is None:
            return None
        scope["all_tasks"][task_id] = tasks[task_id]
    else:
        scene = _entry_of(scenes, link.name)
        if scene is None:
            return None
        scope["all_scenes"][link.name] = scene
    return scope


def _run_by(profiles: dict) -> list[str]:
    """The ids of the Tasks these Profiles run -- their Entry and Exit links."""
    return [
        child.text.strip()
        for entry in profiles.values()
        for child in entry["xml"]
        if _TASK_LINK_TAG.match(child.tag) and child.text and child.text.strip()
    ]


def _id_by_name(table: dict, name: str) -> str | None:
    """The key of the entry called `name` in an id-keyed table, or None.  The first, should two share a name."""
    return next((key for key, entry in table.items() if isinstance(entry, dict) and entry.get("name") == name), None)


def scope_of(kind: str, name: str, tables: dict) -> dict | None:
    """The tables of what the configuration holds of one object -- see _scope_tables.  None if it is not there."""
    return _scope_tables(Link(kind, name, ""), tables)


def local_names(kind: str, state: RunState) -> list[str]:
    """The names of everything of `kind` in the loaded configuration, for choosing what a link is attached to."""
    table = state.tasker_root_elements.get(
        {PROJECT: "all_projects", PROFILE: "all_profiles", TASK: "all_tasks", SCENE: "all_scenes"}[kind], {}
    )
    if kind in (PROJECT, SCENE):
        return sorted(table, key=str.lower)
    return sorted(
        {entry["name"] for entry in table.values() if isinstance(entry, dict) and entry.get("name")}, key=str.lower
    )


def local_scope(link: Link, state: RunState) -> Configuration | None:
    """What the loaded configuration holds of the linked object, as one side of a comparison.  None if it is gone."""
    tables = _scope_tables(link, state.tasker_root_elements)
    if tables is None:
        return None
    return Configuration(path="your copy", tables=tables, root=None, when=None)


# ##################################################################################
# Giving the share the ids the local copy has.
# ##################################################################################

# What Tasker does to a Profile on import, and the user does afterwards, rather than what the
# author wrote: a share ships its Profiles disabled (<limit>true</limit>) and collapsed
# (<clp>), and the importer enables them, which Tasker records by dropping both and setting
# bit 2 of <flags>.  Measured on a real import: all 16 Profiles of the Http Server Example went
# flags 8 -> 10 with <limit> and <clp> gone.  Your Profile's state is yours, so it is kept.
_STATE_TAGS = ("limit", "clp")
_ENABLED_BIT = 2


@dataclass
class Aligned:
    """The share's XML numbered as your copy is, and how its own ids map to those numbers.

    `profiles` and `tasks` map the id the author's Tasker gave an object to the id it has
    here.  The author's ids are stable from one version of a share to the next, so these are
    how a change found between two published versions is found again in your configuration.
    """

    xml: str
    profiles: dict[str, str] = field(default_factory=dict)
    tasks: dict[str, str] = field(default_factory=dict)

    def yours(self, kind: str, key: str) -> str:
        """The id (or, for a Scene, the name) of `kind` in your configuration that the share's `key` is."""
        return {PROFILE: self.profiles, TASK: self.tasks}.get(kind, {}).get(key, key)


def _rename_top(root: Element, link: Link, share_name: str) -> None:
    """Give the share's own top object the name the local one has, so the two are the same object.

    A Project is found by being the only one, a Profile, Task or Scene by the name the share is
    published under -- falling back to the first of its kind, since a share published as
    'Tidy Up' whose Task is called 'Tidy up' is still that Task.
    """
    tag, name_tag = {PROJECT: ("Project", "name"), PROFILE: ("Profile", "nme")}.get(link.kind, (link.kind, "nme"))
    elements = root.findall(tag)
    top = next((el for el in elements if (el.findtext(name_tag) or "").strip() == share_name), None)
    top = top if top is not None else (elements[0] if elements else None)
    if top is None:
        return
    name = top.find(name_tag)
    if name is None:
        name = Element(name_tag)
        top.append(name)
    name.text = link.name


def _names_to_ids(table: dict) -> dict[str, str]:
    """name -> id for an id-keyed table, the first of any two that share a name."""
    names: dict[str, str] = {}
    for key, entry in table.items():
        if isinstance(entry, dict) and entry.get("name"):
            names.setdefault(entry["name"], key)
    return names


def _renumber(
    root: Element,
    tag: str,
    local: dict[str, str],
    fresh: Callable[[], str],
    paired: dict[str, str] | None = None,
) -> dict[str, str]:
    """Give each `tag` element the id of the local one it is, or an unused id.  Returns old -> new.

    "It is" means, in order: `paired` (what is already known of it -- the Task a matched Profile
    runs on both sides, which is how an anonymous Task with no name to match is recognised, or
    the id an earlier version of the share was matched to), then the same name.  An id is handed
    out once: two of the share's objects on one of yours would merge them, so a second object of
    the same name is treated as new.
    """
    paired = paired or {}
    mapping: dict[str, str] = {}
    claimed: set[str] = set(paired.values())
    for element in root.findall(tag):
        id_element = element.find("id")
        if id_element is None:
            continue
        old = (id_element.text or "").strip()
        wanted = local.get((element.findtext("nme") or "").strip())
        if old in paired:
            new = paired[old]
        elif wanted is not None and wanted not in claimed:
            new = wanted
        else:
            new = fresh()
        claimed.add(new)
        mapping[old] = new
        id_element.text = new
        _follow_id_in_sr(element, tag, new)
    return mapping


# What an object's 'sr' attribute is built from: "prof17", "task13".  Tasker writes the id into it,
# and so does the loader read it back -- a Profile without a name is named from its conditions
# through that id -- so an object renumbered and left with the old 'sr' fails to load at all.
_SR_PREFIX = {"Profile": "prof", "Task": "task"}


def _follow_id_in_sr(element: Element, tag: str, new_id: str) -> None:
    """Make an object's 'sr' say the id it now has, if it said its id before."""
    prefix = _SR_PREFIX.get(tag, "")
    if prefix and element.get("sr", "").startswith(prefix):
        element.set("sr", f"{prefix}{new_id}")


def _unnamed_pair(root: Element, scope: Configuration) -> dict[str, str]:
    """share Profile id -> your Profile id, for the one Profile with no name on each side, if each has just one.

    A Profile with no <nme> is named by Tasker from its conditions, so there is no name to match
    it by.  When exactly one of the share's and exactly one of yours has none, they are taken to
    be the same Profile; with more than one on either side there is nothing to choose between
    them, and they are left unmatched rather than guessed at.  A NAMED Profile is never paired
    this way: one the author dropped and one they added would look the same.
    """
    shared = [el for el in root.findall("Profile") if not (el.findtext("nme") or "").strip()]
    yours = [
        key for key, entry in scope.tables["all_profiles"].items() if not (entry["xml"].findtext("nme") or "").strip()
    ]
    if len(shared) != 1 or len(yours) != 1:
        return {}
    return {(shared[0].findtext("id") or "").strip(): yours[0]}


def _paired_tasks(root: Element, scope: Configuration) -> dict[str, str]:
    """share Task id -> your Task id, for each Task a matched Profile runs on both sides.

    Run after the Profiles are renumbered, so a share Profile's <id> is already the id of the
    Profile of yours it is.  Its Entry and Exit links are then the Tasks to pair.
    """
    yours = scope.tables["all_profiles"]
    pairs: dict[str, str] = {}
    for profile in root.findall("Profile"):
        mine = yours.get((profile.findtext("id") or "").strip())
        if mine is None:
            continue
        for link in profile:
            theirs = (link.text or "").strip()
            ours = mine["xml"].find(link.tag) if theirs and _TASK_LINK_TAG.match(link.tag) else None
            if ours is not None and (ours.text or "").strip():
                pairs[theirs] = (ours.text or "").strip()
    return pairs


def _relink(root: Element, profiles: dict[str, str], tasks: dict[str, str]) -> None:
    """Point everything that names a Profile or Task by id at the new ids: Project lists and Profile links."""
    for project in root.findall("Project"):
        for tag, mapping in (("pids", profiles), ("tids", tasks)):
            element = project.find(tag)
            if element is not None and element.text:
                element.text = ",".join(mapping.get(item, item) for item in _id_list(project, tag))
    for profile in root.findall("Profile"):
        for child in profile:
            if _TASK_LINK_TAG.match(child.tag) and child.text:
                child.text = tasks.get(child.text.strip(), child.text.strip())


def _insert_in_order(profile: Element, new: Element) -> None:
    """Put `new` among a Profile's own fields where Tasker writes it: alphabetical, ahead of the conditions.

    Tasker writes cdate, clp, cldm, edate, flags, id, limit, mid0, nme, pri and then the conditions
    (<Event sr="con0">...).  A field put anywhere else makes the Profile differ from yours in the order
    of its settings and nothing else, which is what a compare then reports as a bare "Changed."
    """
    position = len(profile)
    for index, child in enumerate(profile):
        if child.get("sr", "").startswith("con") or child.tag.lower() > new.tag.lower():
            position = index
            break
    profile.insert(position, new)


def _keep_your_state(profile: Element, yours: Element) -> None:
    """Give the share's Profile the enabled state, collapse state and enabled flag yours has."""
    for tag in _STATE_TAGS:
        shared, mine = profile.find(tag), yours.find(tag)
        if mine is None and shared is not None:
            profile.remove(shared)
        elif mine is not None and shared is not None:
            shared.text = mine.text
        elif mine is not None:
            kept = Element(tag)
            kept.text = mine.text
            _insert_in_order(profile, kept)
    flags, your_flags = profile.find("flags"), yours.find("flags")
    if your_flags is None:
        return
    if flags is None:
        # A share with no <flags> at all (it is 0) is the same as one with 0, once yours has the bit set.
        flags = Element("flags")
        flags.text = "0"
        _insert_in_order(profile, flags)
    try:
        flags.text = str((int(flags.text or 0) & ~_ENABLED_BIT) | (int(your_flags.text or 0) & _ENABLED_BIT))
    except ValueError:
        return
    if flags.text == "0" and (your_flags.text or "").strip() in ("", "0"):
        profile.remove(flags)


def _is_empty_argument(element: Element) -> bool:
    """An action argument with nothing in it: no text, no value, no children, and named 'argN'."""
    return (
        element.get("sr", "").startswith("arg")
        and not (element.text or "").strip()
        and "val" not in element.attrib
        and len(element) == 0
    )


def _adopt_empty_arguments(task: Element, yours: Element) -> None:
    """Give each of the share's actions (and, below, conditions) the empty arguments yours has and it lacks.

    A newer Tasker writes an empty argument for each one an older Tasker did not know -- Task
    'Flip To Shh Setup' has an empty fifth argument on its first action in a copy saved by Tasker
    6.x that the share, written by 5.14, does not.  Nothing the author wrote differs, so it is not
    reported as if it did.  Only actions in the same place with the same code are paired: when the
    author has added or removed an action the positions no longer line up, and nothing is guessed.
    """
    for action, mine in zip(task.findall("Action"), yours.findall("Action"), strict=False):
        _adopt_empty_arguments_of(action, mine)


def _conditions_of(profile: Element) -> dict[str, list[Element]]:
    """A Profile's conditions by type: its children Tasker names 'conN' (<Event sr="con0">, <Time sr="con1">)."""
    grouped: dict[str, list[Element]] = {}
    for child in profile:
        if child.get("sr", "").startswith("con"):
            grouped.setdefault(child.tag, []).append(child)
    return grouped


def _adopt_empty_arguments_of_conditions(profile: Element, yours: Element) -> None:
    """The same for a Profile's conditions, which a newer Tasker also gives empty arguments."""
    mine = _conditions_of(yours)
    for kind, conditions in _conditions_of(profile).items():
        for condition, theirs in zip(conditions, mine.get(kind, []), strict=False):
            _adopt_empty_arguments_of(condition, theirs)


def _adopt_empty_arguments_of(shared: Element, yours: Element) -> None:
    """One action or condition: add the empty arguments yours has and the share's lacks, if both are the same kind."""
    if (shared.findtext("code") or "").strip() != (yours.findtext("code") or "").strip():
        return
    present = {child.get("sr") for child in shared}
    for position, child in enumerate(yours):
        if _is_empty_argument(child) and child.get("sr") not in present:
            shared.insert(min(position, len(shared)), Element(child.tag, dict(child.attrib)))


def _only_yours(mapping: dict[str, str], scope: Configuration, table: str) -> dict[str, str]:
    """The part of an id mapping that points at objects of yours -- not at ids invented for new ones."""
    return {old: new for old, new in mapping.items() if new in scope.tables[table]}


def align_share(
    xml_text: str, link: Link, scope: Configuration, state: RunState, earlier: Aligned | None = None
) -> Aligned:
    """The share's XML with its Tasks and Profiles numbered as the linked item's are.

    Parsed with defusedxml, because this text came from a stranger.  New objects -- ones the
    author added that you do not have -- are numbered above every id in the loaded
    configuration, so they cannot be mistaken for something of yours.  `earlier` is an older
    version of the same share already aligned: what it matched stays matched when the author
    renames it.  Raises TaskerNetError if the text is not a Tasker share.
    """
    try:
        root = DefusedET.fromstring(xml_text)
    except (DefusedET.ParseError, ValueError) as error:
        message = "The share TaskerNet sent is not valid Tasker XML."
        raise TaskerNetError(message) from error
    if root.tag != "TaskerData":
        message = "The share TaskerNet sent is not Tasker XML."
        raise TaskerNetError(message)

    _rename_top(root, link, link.ref.name)
    live = state.tasker_root_elements
    highest = max(
        (int(key) for table in ("all_tasks", "all_profiles") for key in live.get(table, {}) if str(key).isdigit()),
        default=0,
    )
    numbers = count(highest + 1)

    def fresh() -> str:
        return str(next(numbers))

    known_profiles = {
        **_unnamed_pair(root, scope),
        **(_only_yours(earlier.profiles, scope, "all_profiles") if earlier else {}),
    }
    known_tasks = _only_yours(earlier.tasks, scope, "all_tasks") if earlier else {}
    profiles = _renumber(root, "Profile", _names_to_ids(scope.tables["all_profiles"]), fresh, known_profiles)
    paired = {**known_tasks, **_paired_tasks(root, scope)}
    tasks = _renumber(root, "Task", _names_to_ids(scope.tables["all_tasks"]), fresh, paired)
    _relink(root, profiles, tasks)
    for profile in root.findall("Profile"):
        mine = scope.tables["all_profiles"].get((profile.findtext("id") or "").strip())
        if mine is not None:
            _keep_your_state(profile, mine["xml"])
            _adopt_empty_arguments_of_conditions(profile, mine["xml"])
    for task in root.findall("Task"):
        mine = scope.tables["all_tasks"].get((task.findtext("id") or "").strip())
        if mine is not None:
            _adopt_empty_arguments(task, mine["xml"])
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode")
    return Aligned(xml=xml, profiles=profiles, tasks=tasks)


# ##################################################################################
# Reviewing an update.
# ##################################################################################

_AUTHOR_KINDS = (PROFILE, TASK, SCENE)


@dataclass
class AuthorChanges:
    """What the author changed between the version you accepted and the one published now.

    `keys` are the objects of yours that this touches -- (kind, your id or name) -- which is
    what filters the list of things to take.  `removed` are objects the author dropped, which
    are reported and not offered: deleting is done in the object's own Edit dialog.
    """

    report: str
    counts: dict
    keys: frozenset[tuple[str, str]]
    removed: tuple[str, ...] = ()

    @property
    def nothing(self) -> bool:
        """The author's two versions hold the same configuration."""
        return not any(self.counts.values())


@dataclass
class Review:
    """The share set beside the linked item: what differs, and what can be taken one object at a time.

    `author` is None when no accepted version is on file to compare the latest against; the
    list is then everything that differs from your copy, import noise included.
    """

    link: Link
    info: ShareInfo
    shared: Configuration
    offer: maprestore.Offer
    xml_text: str = ""
    report: str = ""
    counts: dict = field(default_factory=dict)
    author: AuthorChanges | None = None
    # Every object that differs from your copy, whoever made the difference.  `offer` holds only
    # the author's changes when there is an accepted version to tell them by; this keeps the rest
    # reachable, since what Tasker rewrote on import and what you edited are differences too.
    everything: list[maprestore.Candidate] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        """Nothing offerable and nothing differs at all -- see AuthorChanges.nothing for the author's side."""
        return not any(self.counts.values())

    @property
    def from_when(self) -> str:
        """How the share is named in a preview: 'TaskerNet share published 07-Oct-2026 15:38'."""
        return f"TaskerNet share published {describe_date(self.info.published_ms)}"


def review(link: Link, state: RunState, book: LinkBook | None = None) -> tuple[Review | None, str]:
    """Fetch the share and set it beside the linked item.  (review, "") or (None, why not).

    Slow -- a download and two or three parses -- so the dialog runs it off the event loop.  It
    also brings the link up to date with what TaskerNet says, since the answer to "what is
    published?" is the first half of this one.  `book` supplies the version last accepted.
    """
    scope = local_scope(link, state)
    if scope is None:
        return None, f"'{link.name}' is not in the configuration that is loaded, so there is nothing to compare."
    try:
        info = fetch_info(link.ref)
        xml_text = fetch_xml(link.ref)
    except TaskerNetError as error:
        return None, str(error)
    link.latest_ms, link.checked, link.problem = info.published_ms, clock.now().isoformat(), ""
    return assemble(link, info, xml_text, scope, state, book.baseline(link) if book else None)


def assemble(
    link: Link,
    info: ShareInfo,
    xml_text: str,
    scope: Configuration,
    state: RunState,
    accepted_xml: str | None = None,
) -> tuple[Review | None, str]:
    """A Review from the share's text, with no network.  Split from review() so tests need none."""
    earlier = None
    if accepted_xml:
        try:
            earlier = align_share(accepted_xml, link, scope, state)
        except TaskerNetError as error:
            # A baseline that will not read is no baseline: say so in the log, and offer everything that differs.
            logger.error(f"TaskerNet baseline could not be aligned: {error}")
            accepted_xml = None
    try:
        aligned = align_share(xml_text, link, scope, state, earlier)
    except TaskerNetError as error:
        return None, str(error)
    shared, problem = _load(aligned.xml, state)
    if shared is None:
        return None, problem
    shared = shared._replace(path=f"TaskerNet share published {describe_date(info.published_ms)}")

    author = None
    if accepted_xml:
        author, problem = _author_changes(accepted_xml, xml_text, aligned, state)
        if author is None:
            logger.error(f"TaskerNet baseline could not be compared: {problem}")
    return build_review(link, info, shared, scope, state, xml_text, author), ""


def _author_changes(
    accepted_xml: str,
    latest_xml: str,
    aligned: Aligned,
    state: RunState,
) -> tuple[AuthorChanges | None, str]:
    """What the author changed between two published versions, found in the author's own ids."""
    then, problem = _load(accepted_xml, state)
    now, problem = _load(latest_xml, state) if then is not None else (None, problem)
    if then is None or now is None:
        return None, problem
    then, now = then._replace(path="the version you accepted"), now._replace(path="the version published now")
    report, counts = xmldiff.compare(then, now)
    keys, removed = set(), []
    for entry in xmldiff.differences(then, now):
        if entry.kind not in _AUTHOR_KINDS:
            continue
        if entry.category == xmldiff.REMOVED:
            removed.append(entry.where)
        else:
            keys.add((entry.kind, aligned.yours(entry.kind, entry.key)))
    return AuthorChanges(report, counts, frozenset(keys), tuple(removed)), ""


def build_review(
    link: Link,
    info: ShareInfo,
    shared: Configuration,
    scope: Configuration,
    state: RunState,
    xml_text: str = "",
    author: AuthorChanges | None = None,
) -> Review:
    """Compare an already-aligned share with the linked item, offering the author's changes if they are known."""
    report, counts = xmldiff.compare(shared, scope)
    offer = maprestore.candidates(shared, scope, state)
    everything = list(offer.candidates)
    if author is not None:
        offer.candidates = [c for c in offer.candidates if (c.kind, c.key) in author.keys]
    return Review(link, info, shared, offer, xml_text, report, counts, author, everything)


def rescan(held: Review, state: RunState) -> Review | None:
    """The same share against the item as it is NOW -- after something was taken, or edited elsewhere."""
    scope = local_scope(held.link, state)
    if scope is None:
        return None
    return build_review(held.link, held.info, held.shared, scope, state, held.xml_text, held.author)


@dataclass
class Taken:
    """What accepting a version did: how many changes went in, and which could not be made, with why."""

    done: int = 0
    skipped: list[str] = field(default_factory=list)


def accept_changes(candidates: list[maprestore.Candidate], held: Review, state: RunState) -> Taken:
    """Take every one of `candidates` from the share, in order, as ONE change the user can undo.

    The alternative to a 'Take this' per object, for the user who wants the author's version and
    not a choice of its parts.  It is the same restore, repeated: each object is planned against
    the configuration as the one before LEFT it, which is what a single press of 'Take this' on
    each row in turn would do -- a Profile is linked by name to the Task that came in a moment
    earlier -- and not against the configuration as it was when the list was drawn.  Tasks are
    taken before Profiles before Scenes (the candidates' own order) for that reason.

    One that cannot be made -- its plan is blocked, or it fails -- is skipped and said so; it
    does not stop the rest.  The whole of it is one Undo, labelled with the share and the count.
    """
    taken = Taken()
    label = f"Accept TaskerNet version of {held.link.name} ({len(candidates)} changes)"
    with sessundo.undoable(label, state=state):
        for candidate in candidates:
            plan = maprestore.plan_restore(candidate, held.shared, held.from_when, state=state)
            done, errors = maprestore.restore(plan, state=state)
            if done:
                taken.done += 1
            else:
                reason = " ".join(errors) or "it could not be done."
                taken.skipped.append(f"{candidate.where}: {reason}")
    return taken


def accept(book: LinkBook, held: Review) -> None:
    """Take the version reviewed as the one the user has: later checks look for something newer than it.

    The share is kept as the baseline, so the next update is compared with THIS version and
    the author's changes can be told from everything else that differs.
    """
    held.link.seen_ms = held.info.published_ms
    if held.xml_text:
        book.save_baseline(held.link, held.xml_text)
    book.save()


def _load(xml_text: str, state: RunState) -> tuple[Configuration | None, str]:
    """Parse XML text as a second configuration, without disturbing the loaded one (see diffload)."""
    handle, temporary = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(xml_text)
        return diffload.load_for_comparison(temporary, state=state)
    except OSError as error:
        return None, f"The share could not be prepared for comparison.  ({error})"
    finally:
        with contextlib.suppress(OSError):
            Path(temporary).unlink()
