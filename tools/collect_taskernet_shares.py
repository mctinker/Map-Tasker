#!/usr/bin/env python3
"""Collect the TaskerNet shares announced as "[Project Share]" on r/tasker and merge them into numbered Tasker XML files.

Three steps, each of which can be run again safely:

  1. Search r/tasker for posts whose title starts with "[Project Share]" and pull the TaskerNet link out of
     each (the post itself, or failing that the author's own comments).  Only posts newer than the last run's
     are looked at -- the first run goes back a year, and --days N goes back N days whatever is already there.
  2. Download each share's Tasker XML into NewXML/ -- one file per share.  A share already there is kept.
  3. Merge everything in NewXML/ into Tasker backups of 7 Projects each -- XML/newxml1.xml, newxml2.xml, ... --
     renumbering Task and Profile ids so shares that each started at "Task 1" do not collide.  A lone Profile,
     Task or Scene share goes in whichever file it falls in.

Standard library only.

HOW REDDIT IS READ
Reddit answers its JSON API with 403 to anything without an API key, but still serves the public RSS
search feed to a browser-like User-Agent.  RSS is rate limited (429), so requests are spaced out and a
429 is waited out rather than retried at once.  Search is Reddit's own and can miss a post; a link that
never turns up can be given on the command line with --link.

HOW TASKERNET IS READ
A share page is a small client over two unauthenticated JSON endpoints under
taskernet.com/_ah/api/datashare/v1/.  `sharedata` answers with taskerproject:// (or taskerprofile://, ...)
followed by base64 of gzipped Tasker XML -- the same thing the Import button reads.  The download counter
is never switched on, so collecting does not inflate an author's numbers.  The endpoints are undocumented
and may change; see maptasker/src/mapops/tnupdate.py, which uses the same two.

Shares are other people's work.  Collect them for your own reference and respect their authors' terms.

Usage:
    python3 tools/collect_taskernet_shares.py
    python3 tools/collect_taskernet_shares.py --combine-only
    python3 tools/collect_taskernet_shares.py --days 90 --refresh
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

with contextlib.suppress(ImportError):
    import defusedxml.ElementTree as DefusedET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOWNLOAD_DIR = ROOT / "NewXML"
DEFAULT_OUTPUT = ROOT / "XML" / "newxml.xml"
MANIFEST_NAME = "_sources.json"
CHECKED_NAME = "_checked.json"  # {"checked_through": when the newest post already dealt with was made}
DEFAULT_DAYS = 365  # how far back a first run looks

SUBREDDIT = "tasker"
TITLE_PREFIX = "[project share]"
# Reddit refuses an obviously scripted User-Agent; an ordinary browser's is let through.
REDDIT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TASKERNET_UA = "MapTasker-ShareCollector/1.0"
SEARCH_QUERIES = ('"[Project Share]"', "title:project share")
MAX_SEARCH_PAGES = 15

API_ROOT = "https://taskernet.com/_ah/api/datashare/v1/"
TASKERNET_HOSTS = frozenset({"taskernet.com", "www.taskernet.com"})
SHARE_KINDS = {"Project": "prj", "Profile": "prf", "Task": "tsk", "Scene": "scn"}
DATA_SCHEME = re.compile(r"^tasker[a-z]+://", re.IGNORECASE)
LINK_PATTERN = re.compile(r"https?://(?:www\.)?taskernet\.com/shares/?\?[^\s\"'<>)\]]+", re.IGNORECASE)
MAX_XML_BYTES = 128 * 1024 * 1024
TIMEOUT = 30

ATOM = "{http://www.w3.org/2005/Atom}"


class Post:
    """One Reddit post: where it is, what it is called, and the share links found so far."""

    def __init__(self, post_id: str, title: str, url: str, posted: datetime, author: str, content: str) -> None:
        self.post_id = post_id
        self.title = title
        self.url = url
        self.posted = posted
        self.author = author
        self.links = find_share_links(content)


# ##################################################################################
# Reddit.
# ##################################################################################


def http_get(url: str, user_agent: str, *, retries: int = 5) -> bytes:
    """GET `url`, waiting out a 429 (for as long as the server says, else 30s, 60s, ...).  Other failures raise."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})  # noqa: S310 -- https URLs only
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == retries:
                raise
            wait = int(error.headers.get("Retry-After") or 0) or 30 * 2**attempt
            print(f"  rate limited; waiting {wait}s", flush=True)
            time.sleep(wait)
    message = f"Could not get {url}"
    raise RuntimeError(message)


def parse_xml(data: bytes | str) -> ET.Element:
    """Parse XML that came from the internet, with defusedxml when it is there."""
    if "DefusedET" in globals():
        return DefusedET.fromstring(data)
    return ET.fromstring(data)  # noqa: S314


def find_share_links(text: str) -> list[str]:
    """Every TaskerNet share address in `text` (HTML or plain), canonical and in order, without repeats."""
    found: dict[str, None] = {}
    for match in LINK_PATTERN.findall(html.unescape(text or "")):
        ref = parse_share_link(match.rstrip(".,;:!?"))
        if ref:
            found[share_link(*ref)] = None
    return list(found)


def parse_share_link(link: str) -> tuple[str, str] | None:
    """(user, share id) of a TaskerNet share address, or None if it is not one."""
    parts = urlparse(link)
    if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in TASKERNET_HOSTS:
        return None
    query = parse_qs(parts.query)
    # A '+' left unescaped in the publisher's id is read back as a space; the id has no spaces.
    user = (query.get("user") or [""])[0].replace(" ", "+")
    share_id = (query.get("id") or [""])[0]
    kind, _, name = share_id.partition(":")
    if not user or not name or kind not in SHARE_KINDS:
        return None
    return user, share_id


def share_link(user: str, share_id: str) -> str:
    """The share's page address, as TaskerNet itself spells it."""
    return (
        f"https://taskernet.com/shares/?user={quote(user, safe='')}&id={quote(share_id, safe='').replace('%20', '+')}"
    )


def read_feed(url: str) -> list[ET.Element]:
    """The <entry> elements of a Reddit Atom feed."""
    return parse_xml(http_get(url, REDDIT_UA)).findall(f"{ATOM}entry")


def entry_to_post(entry: ET.Element) -> Post | None:
    """A Post from a feed entry, or None if it is not one that has a date and a title."""
    text = lambda tag: (entry.findtext(f"{ATOM}{tag}") or "").strip()
    stamp = text("updated") or text("published")
    link = entry.find(f"{ATOM}link")
    if not stamp or not text("title"):
        return None
    return Post(
        post_id=text("id"),
        title=text("title"),
        url=link.get("href", "") if link is not None else "",
        posted=datetime.fromisoformat(stamp),
        author=(entry.findtext(f"{ATOM}author/{ATOM}name") or "").strip(),
        content=text("content"),
    )


def search_posts(query: str, cutoff: datetime, delay: float) -> list[Post]:
    """Posts in the subreddit matching `query`, newest first, back to `cutoff`, whose title starts as a share does."""
    posts: list[Post] = []
    after = ""
    for _ in range(MAX_SEARCH_PAGES):
        params = {"q": query, "restrict_sr": "1", "sort": "new", "t": "year", "limit": "100"}
        if after:
            params["after"] = after
        entries = read_feed(f"https://www.reddit.com/r/{SUBREDDIT}/search.rss?{urlencode(params)}")
        page = [post for post in map(entry_to_post, entries) if post]
        if not page:
            break
        posts += [post for post in page if post.posted >= cutoff and post.title.lower().startswith(TITLE_PREFIX)]
        after = page[-1].post_id
        if page[-1].posted < cutoff:
            break
        time.sleep(delay)
    return posts


def author_comment_links(post: Post, delay: float) -> list[str]:
    """TaskerNet links the post's author gave in a comment -- where a share often goes when the post is just a pitch."""
    time.sleep(delay)
    short_id = post.post_id.removeprefix("t3_")
    links: list[str] = []
    for entry in read_feed(f"https://www.reddit.com/comments/{short_id}.rss?limit=100"):
        author = (entry.findtext(f"{ATOM}author/{ATOM}name") or "").strip()
        if author and author == post.author:
            links += find_share_links(entry.findtext(f"{ATOM}content") or "")
    return list(dict.fromkeys(links))


def starting_point(download_dir: Path, days: int | None) -> datetime:
    """Where to start searching: back `days` if asked, else just past the newest post already dealt with.

    "Dealt with" is what _checked.json says, or failing that the newest post any saved share came from.
    A first run, with neither, looks back DEFAULT_DAYS.
    """
    if days is not None:
        return datetime.now(UTC) - timedelta(days=days)
    stamps = []
    with contextlib.suppress(OSError, ValueError, TypeError):
        stamps.append(json.loads((download_dir / CHECKED_NAME).read_text(encoding="utf-8"))["checked_through"])
    with contextlib.suppress(OSError, ValueError, TypeError):
        manifest = json.loads((download_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        stamps += [item["posted"] for item in manifest.values() if item.get("posted")]
    try:
        newest = max(datetime.fromisoformat(stamp) for stamp in stamps)
    except ValueError:  # no stamps at all, or one that is not a date
        return datetime.now(UTC) - timedelta(days=DEFAULT_DAYS)
    return newest + timedelta(seconds=1)


def collect_posts(since: datetime, delay: float) -> list[Post]:
    """Every "[Project Share]" post made since `since`, once each, with the share links found for it."""
    unique: dict[str, Post] = {}
    for query in SEARCH_QUERIES:
        print(f"Searching r/{SUBREDDIT} for {query} ...", flush=True)
        for post in search_posts(query, since, delay):
            unique.setdefault(post.post_id, post)
        time.sleep(delay)
    posts = sorted(unique.values(), key=lambda post: post.posted, reverse=True)
    print(f"Found {len(posts)} new [Project Share] post(s) since {since:%Y-%m-%d %H:%M}.")
    for post in posts:
        if not post.links:
            try:
                post.links = author_comment_links(post, delay)
            except (urllib.error.URLError, ET.ParseError, OSError) as error:
                print(f"  could not read the comments of {post.url}: {error}")
        if not post.links:
            print(f"  no TaskerNet link found: {post.title} ({post.url})")
    return posts


def record_checked(download_dir: Path, posts: list[Post]) -> None:
    """Remember how far the posts have been dealt with, so the next run starts after them.

    Up to the newest post -- but stopping short of the oldest one whose share did not get saved (a
    404, a dropped connection), so that it is tried again rather than left behind.
    """
    if not posts:
        return
    manifest_path = download_dir / MANIFEST_NAME
    saved: set[str] = set()
    if manifest_path.is_file():
        saved = {item["link"] for item in json.loads(manifest_path.read_text(encoding="utf-8")).values()}
    through = max(post.posted for post in posts)
    failed = [post.posted for post in posts if any(link not in saved for link in post.links)]
    if failed:
        through = min(through, min(failed) - timedelta(seconds=1))
    (download_dir / CHECKED_NAME).write_text(json.dumps({"checked_through": through.isoformat()}), encoding="utf-8")


# ##################################################################################
# TaskerNet.
# ##################################################################################


def fetch_share_xml(user: str, share_id: str) -> str:
    """The share's Tasker XML as published.  Raises ValueError for anything that is not a Tasker share."""
    url = f"{API_ROOT}sharedata/{quote(user, safe='')}/{quote(share_id, safe='')}?a=0"
    answer = json.loads(http_get(url, TASKERNET_UA))
    payload = str(answer.get("shareData") or "") if isinstance(answer, dict) else ""
    scheme = DATA_SCHEME.match(payload)
    if scheme is None:
        message = "not a Tasker share"
        raise ValueError(message)
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)  # a few KB of gzip can inflate to GB: cap it
    text = inflater.decompress(base64.b64decode(payload[scheme.end() :]), MAX_XML_BYTES + 1)
    if len(text) > MAX_XML_BYTES or inflater.unconsumed_tail:
        message = "share is too large"
        raise ValueError(message)
    xml_text = text.decode("utf-8", errors="replace")
    parse_xml(xml_text.encode("utf-8"))  # raises ParseError if it is not XML
    return xml_text


def file_name_for(share_id: str, user: str) -> tuple[str, str]:
    """('<name>.prj.xml', '<name> [<user tag>].prj.xml') for 'Project:<name>'; the second is for a name already taken."""
    kind, _, name = share_id.partition(":")
    safe = re.sub(r"[^\w .()+-]+", "_", name).strip(" ._") or "share"
    tag = hashlib.sha1(user.encode()).hexdigest()[:6]  # noqa: S324 -- a label, not security
    return f"{safe[:120]}.{SHARE_KINDS[kind]}.xml", f"{safe[:120]} [{tag}].{SHARE_KINDS[kind]}.xml"


def download_shares(posts: list[Post], extra_links: list[str], out_dir: Path, *, refresh: bool, delay: float) -> None:
    """Save each share's XML under `out_dir` and record where each came from in the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / MANIFEST_NAME
    manifest: dict[str, dict] = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    wanted = {link: post for post in posts for link in post.links}
    wanted.update(dict.fromkeys(extra_links))
    print(f"{len(wanted)} share link(s) to download.")
    for link, post in wanted.items():
        user, share_id = parse_share_link(link) or ("", "")
        if not user:
            continue
        plain, tagged = file_name_for(share_id, user)
        known = next((name for name, item in manifest.items() if item["link"] == link), None)
        name = known or (tagged if (out_dir / plain).exists() else plain)
        if known and (out_dir / known).exists() and not refresh:
            print(f"  have {name}")
            continue
        try:
            (out_dir / name).write_text(fetch_share_xml(user, share_id), encoding="utf-8")
        except (urllib.error.URLError, ValueError, ET.ParseError, OSError) as error:
            print(f"  FAILED {share_id}: {error}")
            continue
        manifest[name] = {
            "link": link,
            "post": post.url if post else "",
            "post_title": post.title if post else "",
            "posted": post.posted.isoformat() if post else "",
        }
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"  saved {name}")
        time.sleep(delay / 2)


# ##################################################################################
# Combining.
# ##################################################################################


class Renumberer:
    """Hands out Task and Profile ids across every share, and rewrites the references to the old ones."""

    def __init__(self) -> None:
        self.next_task = 1
        self.next_profile = 1
        self.next_project = 0

    def renumber(self, root: ET.Element) -> list[ET.Element]:
        """Give one share's Tasks, Profiles and Projects unique ids, and follow them; return its top-level elements."""
        tasks = self._assign(root, "Task", "task")
        profiles = self._assign(root, "Profile", "prof")
        for project in root.findall("Project"):
            project.set("sr", f"proj{self.next_project}")
            self.next_project += 1
            self._remap_list(project.find("pids"), profiles)
            self._remap_list(project.find("tids"), tasks)
        for profile in root.findall("Profile"):
            for child in profile:
                if re.fullmatch(r"mid\d+", child.tag) and (child.text or "").strip() in tasks:
                    child.text = tasks[child.text.strip()]
        self._remap_scene_tasks(root, tasks)
        return list(root)

    @staticmethod
    def _remap_scene_tasks(root: ET.Element, tasks: dict[str, str]) -> None:
        """A Scene runs a Task by id ('<clickTask>1905</clickTask>', '<keyTask>', ...): follow the Task's new id.

        Negative ids and ids that are not Tasks in this share are left as they are.
        """
        for scene in root.findall("Scene"):
            for element in scene.iter():
                if element.tag.endswith("Task") and (element.text or "").strip() in tasks:
                    element.text = tasks[element.text.strip()]

    def _assign(self, root: ET.Element, tag: str, prefix: str) -> dict[str, str]:
        """New id for every `tag` element, as {old id: new id}; sets the <id> child and the sr attribute."""
        mapping: dict[str, str] = {}
        for element in root.findall(tag):
            id_element = element.find("id")
            if id_element is None:
                continue
            attribute = "next_task" if tag == "Task" else "next_profile"
            new_id = str(getattr(self, attribute))
            setattr(self, attribute, int(new_id) + 1)
            mapping[(id_element.text or "").strip()] = new_id
            id_element.text = new_id
            element.set("sr", f"{prefix}{new_id}")
        return mapping

    @staticmethod
    def _remap_list(element: ET.Element | None, mapping: dict[str, str]) -> None:
        """Rewrite a comma list of ids ('<pids>63,64</pids>').  An id that is not in the share is left alone."""
        if element is not None and element.text:
            element.text = ",".join(mapping.get(item.strip(), item.strip()) for item in element.text.split(","))


def version_key(text: str) -> tuple:
    """Sort key for a Tasker version such as '6.7.6-beta': its numbers, then whether it is a final release."""
    numbers = tuple(int(part) for part in re.findall(r"\d+", text.split("-", maxsplit=1)[0]))
    return (numbers, "-" not in text)


def load_shares(source_dir: Path) -> list[tuple[Path, ET.Element]]:
    """Every share saved in `source_dir`, in name order, parsed.  One that is not XML is reported and left out."""
    shares = []
    for path in sorted(p for p in source_dir.glob("*.xml") if not p.name.startswith("_")):
        try:
            shares.append((path, parse_xml(path.read_bytes())))
        except ET.ParseError as error:
            print(f"  skipping {path.name}: {error}")
    return shares


def batch_shares(shares: list[tuple[Path, ET.Element]], projects_per_file: int) -> list[list[tuple[Path, ET.Element]]]:
    """Group shares so each group holds at most `projects_per_file` Projects, keeping the order.

    A share with no Project in it -- a lone Profile, Task or Scene -- adds nothing to the count and
    rides along with the group it falls in.  A share with more Projects than fit gets a group to itself.
    """
    batches: list[list[tuple[Path, ET.Element]]] = []
    projects = 0
    for share in shares:
        count = len(share[1].findall("Project"))
        if not batches or (count and projects and projects + count > projects_per_file):
            batches.append([])
            projects = 0
        batches[-1].append(share)
        projects += count
    return batches


def merge_batch(batch: list[tuple[Path, ET.Element]]) -> ET.Element:
    """One Tasker backup out of a group of shares, with Task and Profile ids numbered afresh from 1."""
    merged = ET.Element("TaskerData", {"sr": "", "dvi": "1", "tv": "0"})
    numberer = Renumberer()
    scene_names: set[str] = set()
    for path, root in batch:
        if version_key(root.get("tv", "0")) > version_key(merged.get("tv", "0")):
            merged.set("tv", root.get("tv", "0"))
        for element in numberer.renumber(root):
            if element.tag == "Scene":
                name = element.get("sr", "")
                if name in scene_names:
                    print(f"  note: a Scene named '{name[5:]}' is in more than one share (in {path.name}).")
                scene_names.add(name)
            merged.append(element)
    merged.text = "\n\t"
    for element in merged:
        element.tail = "\n\t"
    if len(merged):
        merged[-1].tail = "\n"
    return merged


def combine_xml(source_dir: Path, output: Path, projects_per_file: int = 7) -> list[Path]:
    """Merge the shares in `source_dir` into numbered Tasker backups, `projects_per_file` Projects to a file.

    `output` names the first: XML/newxml.xml gives XML/newxml1.xml, XML/newxml2.xml, ...  Numbered files left
    from an earlier, longer run are removed so the set on disk is exactly this run's.  Returns what was written.
    """
    batches = batch_shares(load_shares(source_dir), projects_per_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    written = []
    for number, batch in enumerate(batches, start=1):
        path = output.with_name(f"{output.stem}{number}{output.suffix}")
        path.write_text(ET.tostring(merge_batch(batch), encoding="unicode"), encoding="utf-8")
        ET.parse(path)  # the file must read back
        print(
            f"  {path.name}: {len(batch)} share(s), {sum(len(root.findall('Project')) for _, root in batch)} project(s)"
        )
        written.append(path)
    stale = re.compile(rf"{re.escape(output.stem)}(\d+){re.escape(output.suffix)}")
    for old in output.parent.glob(f"{output.stem}*{output.suffix}"):
        match = stale.fullmatch(old.name)
        if match and int(match.group(1)) > len(written):
            old.unlink()
    return written


# ##################################################################################
# Command line.
# ##################################################################################


def main() -> int:
    """Search, download, combine."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=f"look back this many days, ignoring what is already collected (first run: {DEFAULT_DAYS})",
    )
    parser.add_argument("--download-dir", type=Path, default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="base name: newxml.xml -> newxml1.xml, ...")
    parser.add_argument("--projects-per-file", type=int, default=5, help="Projects in each output file (default 7)")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between Reddit requests (default 3)")
    parser.add_argument("--refresh", action="store_true", help="download shares again even if already saved")
    parser.add_argument("--combine-only", action="store_true", help="skip Reddit and TaskerNet; merge what is saved")
    parser.add_argument("--link", action="append", default=[], help="an extra TaskerNet share link to include")
    args = parser.parse_args()

    if not args.combine_only:
        posts = collect_posts(starting_point(args.download_dir, args.days), args.delay)
        extra = [link for item in args.link for link in find_share_links(item)]
        download_shares(posts, extra, args.download_dir, refresh=args.refresh, delay=args.delay)
        record_checked(args.download_dir, posts)
    written = combine_xml(args.download_dir, args.output, max(1, args.projects_per_file))
    print(f"Wrote {len(written)} file(s) beside {args.output}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
