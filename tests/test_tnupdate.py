"""MapTasker TaskerNet update (tnupdate) Unit Tests

Three things are easy to get visibly right and invisibly wrong here, and the tests are arranged
around them.

THE ADDRESS AND THE NETWORK.  A link is typed by the user and the answer comes from a stranger,
so what is refused matters as much as what is accepted: a link to another site, an answer far
larger than a share, a gzip that inflates to gigabytes.  The network is never touched -- the one
function that opens a connection is replaced, or httpx is given a canned transport.

THE IDS.  Tasker renumbers every Task and Profile when it imports a share, so compared as
published nothing in the share would match anything in the configuration.  The tests build a
share whose ids share nothing with the local copy's and check that each object is still found
-- including a Task with no name at all, which is only recognisable by the Profile that runs it.

THE AUTHOR'S CHANGES.  What is offered is what the author changed between two PUBLISHED versions,
not everything that differs from the local copy.  So the checks are about what is NOT offered as
much as what is: an object the author left alone, an object of yours outside the linked Project,
and the enabled state of a Profile, which belongs to the user and survives taking the author's
version of it.
"""

from __future__ import annotations

import base64
import gzip
import json
import re
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from maptasker.src.core import clock
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.initparg import ProgramArguments
from maptasker.src.core.primitem import PrimeItems, initial_tasker_root_elements
from maptasker.src.edit import sessundo
from maptasker.src.mapgen import taskerd
from maptasker.src.mapgen.lineout import LineOut
from maptasker.src.mapops import maprestore, tnupdate

USER = "AS35m8ne7oO4s+aDx/wlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn"
LINK = (
    "https://taskernet.com/shares/?user=AS35m8ne7oO4s%2BaDx%2FwlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn"
    "&id=Project%3APack"
)

# ##################################################################################
# The configuration open now.  Its ids (20-22, 100-101) share nothing with the share's (5-12),
# which is the whole point: that is what an import does.
#
#   Project Pack     Profiles Dawn (runs the anonymous Task 22) and Dusk (runs Morning).
#                    Tasks Morning, Helper, and the anonymous one.
#   Project Other    Task Elsewhere -- belongs to something else, and must never be offered.
#
# Dawn is enabled here (flags 10, no <limit>): the importer switched it on.
# ##################################################################################
_LOCAL_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Pack</name><pids>100,101</pids><tids>20,21</tids></Project>
  <Project sr="proj1" ve="2"><name>Other</name><tids>50</tids></Project>
  <Profile sr="prof100" ve="2"><cdate>1</cdate><flags>10</flags><id>100</id><mid0>22</mid0><nme>Dawn</nme>
    <Time sr="con0"><fh>6</fh></Time></Profile>
  <Profile sr="prof101" ve="2"><cdate>1</cdate><flags>10</flags><id>101</id><mid0>20</mid0><nme>Dusk</nme>
    <Time sr="con0"><fh>18</fh></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Helper</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">helping</Str></Action></Task>
  <Task sr="task22" ve="2"><id>22</id>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">anon</Str></Action></Task>
  <Task sr="task50" ve="2"><id>50</id><nme>Elsewhere</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">not mine</Str></Action></Task>
</TaskerData>
"""


def _share(*, dawn_hour: str = "6", morning: str = "hello", anon: str = "anon", helper: str = "Helper") -> str:
    """The share as the author's Tasker wrote it: its own ids, Profiles shipped disabled and collapsed."""
    return f"""<TaskerData sr="" dvi="1" tv="6.2.0-beta">
  <Project sr="proj0" ve="2"><name>Pack</name><pids>5,6</pids><tids>7,8</tids></Project>
  <Profile sr="prof5" ve="2"><cdate>1</cdate><clp>true</clp><flags>8</flags><id>5</id><limit>true</limit>
    <mid0>9</mid0><nme>Dawn</nme><Time sr="con0"><fh>{dawn_hour}</fh></Time></Profile>
  <Profile sr="prof6" ve="2"><cdate>1</cdate><clp>true</clp><flags>8</flags><id>6</id><limit>true</limit>
    <mid0>7</mid0><nme>Dusk</nme><Time sr="con0"><fh>18</fh></Time></Profile>
  <Task sr="task7" ve="2"><id>7</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">{morning}</Str></Action></Task>
  <Task sr="task8" ve="2"><id>8</id><nme>{helper}</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">helping</Str></Action></Task>
  <Task sr="task9" ve="2"><id>9</id>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">{anon}</Str></Action></Task>
</TaskerData>
"""


# The author's next version: Morning and the anonymous Task edited, Dawn's time moved, Helper
# renamed (same id), a Task added, and the Dusk Profile dropped.
_V2 = """<TaskerData sr="" dvi="1" tv="6.2.0-beta">
  <Project sr="proj0" ve="2"><name>Pack</name><pids>5</pids><tids>7,8,12</tids></Project>
  <Profile sr="prof5" ve="2"><cdate>1</cdate><clp>true</clp><flags>8</flags><id>5</id><limit>true</limit>
    <mid0>9</mid0><nme>Dawn</nme><Time sr="con0"><fh>7</fh></Time></Profile>
  <Task sr="task7" ve="2"><id>7</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello there</Str></Action></Task>
  <Task sr="task8" ve="2"><id>8</id><nme>Assistant</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">helping</Str></Action></Task>
  <Task sr="task9" ve="2"><id>9</id>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">anon v2</Str></Action></Task>
  <Task sr="task12" ve="2"><id>12</id><nme>Brand New</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">new</Str></Action></Task>
</TaskerData>
"""


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _load_local(tmp_path: Path, xml: str) -> None:
    """Load `xml` as the configuration open now, the way MapTasker loads one."""
    with open(_write(tmp_path, "local.xml", xml), encoding="utf-8") as handle:
        PrimeItems.file_to_get = handle
        PrimeItems.tasker_root_elements = initial_tasker_root_elements()
        taskerd.get_the_xml_data(state=PrimeItems)


@pytest.fixture(autouse=True)
def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A believable runtime with the local configuration loaded the way MapTasker loads one."""
    monkeypatch.chdir(tmp_path)
    sessundo.clear(PrimeItems)
    PrimeItems.program_arguments = ProgramArguments(
        gui=True, debug=False, directory=False, pretty=False, display_detail_level=3, file="", language="English"
    )
    PrimeItems.error_code = 0
    PrimeItems.error_msg = ""
    PrimeItems.directory_items = {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []}
    PrimeItems.output_lines = LineOut()
    PrimeItems.colors_to_use = set_color_mode("light")
    specs_file = Path(__file__).parent.parent / "maptasker" / "assets" / "json" / "arg_specs.json"
    specs = json.loads(specs_file.read_text(encoding="utf-8"))
    specs[str(len(specs))] = "ConditionList"
    PrimeItems.tasker_arg_specs = specs
    _load_local(tmp_path, _LOCAL_XML)
    yield
    sessundo.clear(PrimeItems)


def _link(kind: str = "Project", name: str = "Pack", share: str = LINK) -> tnupdate.Link:
    return tnupdate.Link(kind=kind, name=name, link=share)


def _info(when: int = 1_700_000_000_000) -> tnupdate.ShareInfo:
    return tnupdate.ShareInfo(published_ms=when, name="Pack", description="", views=0, downloads=0)


def _review(xml: str, accepted: str | None = None, link: tnupdate.Link | None = None) -> tnupdate.Review:
    link = link or _link()
    scope = tnupdate.local_scope(link, PrimeItems)
    assert scope is not None
    held, problem = tnupdate.assemble(link, _info(), xml, scope, PrimeItems, accepted)
    assert held is not None, problem
    return held


def _offered(held: tnupdate.Review) -> set[tuple[str, str, str]]:
    return {(c.kind, c.key, c.action) for c in held.offer.candidates}


def _live(table: str) -> dict:
    return PrimeItems.tasker_root_elements[table]


# ##################################################################################
# The address.
# ##################################################################################


def test_a_share_link_is_read_and_respelled_the_way_taskernet_spells_it() -> None:
    ref = tnupdate.parse_link(LINK)

    assert (ref.user, ref.share_id, ref.kind, ref.name) == (USER, "Project:Pack", "Project", "Pack")
    assert ref.link == LINK


def test_a_name_with_spaces_round_trips() -> None:
    ref = tnupdate.parse_link(
        f"https://taskernet.com/shares/?user={USER.replace('+', '%2B').replace('/', '%2F')}&id=Task%3AMy+Task+2"
    )

    assert ref.name == "My Task 2"
    assert tnupdate.parse_link(ref.link) == ref


def test_a_plus_in_the_user_that_was_not_escaped_is_put_back() -> None:
    """A '+' read as a space would name a different publisher, and the share would not be found."""
    ref = tnupdate.parse_link(f"https://taskernet.com/shares/?user={USER}&id=Scene%3AX")

    assert ref.user == USER


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not a link",
        "https://evil.example.com/shares/?user=abc&id=Project%3AX",
        "https://taskernet.com.evil.example/shares/?user=abc&id=Project%3AX",
        "ftp://taskernet.com/shares/?user=abc&id=Project%3AX",
        "https://taskernet.com/shares/?id=Project%3AX",
        "https://taskernet.com/shares/?user=abc",
        "https://taskernet.com/shares/?user=abc&id=Widget%3AX",
        "https://taskernet.com/shares/?user=abc&id=Project",
    ],
)
def test_anything_that_is_not_a_share_on_taskernet_is_refused(text: str) -> None:
    with pytest.raises(tnupdate.TaskerNetError):
        tnupdate.parse_link(text)


# ##################################################################################
# Asking TaskerNet.
# ##################################################################################


def _pack(xml: str, scheme: str = "taskerproject://") -> str:
    return scheme + base64.b64encode(gzip.compress(xml.encode("utf-8"))).decode("ascii")


def test_share_data_is_unpacked() -> None:
    assert tnupdate.decode_share_data(_pack("<TaskerData/>")) == "<TaskerData/>"
    assert tnupdate.decode_share_data(_pack("<TaskerData/>", "taskerprofile://")) == "<TaskerData/>"


@pytest.mark.parametrize(
    "payload", ["", "<TaskerData/>", "https://x/", "taskerproject://!!!not base64!!!", "taskerproject://aGVsbG8="]
)
def test_share_data_that_is_not_gzipped_tasker_data_is_refused(payload: str) -> None:
    with pytest.raises(tnupdate.TaskerNetError):
        tnupdate.decode_share_data(payload)


def test_a_share_that_inflates_past_the_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A few kilobytes of gzip can be gigabytes of text, and the text comes from a stranger."""
    monkeypatch.setattr(tnupdate, "_XML_LIMIT", 1000)

    with pytest.raises(tnupdate.TaskerNetError, match="larger"):
        tnupdate.decode_share_data(_pack("<a>" + "x" * 5000 + "</a>"))


def _serve(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    """Make httpx.Client talk to `handler` instead of the network; return the requests it saw."""
    seen: list[httpx.Request] = []
    real = httpx.Client

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(
        tnupdate.httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(answer), **kwargs)
    )
    return seen


def test_info_is_read_and_the_counters_are_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "info": {
            "date": "1684778035414",
            "name": "Pack",
            "description": "<p>d</p>",
            "stats": {"views": 3, "downloads": 2},
        }
    }
    seen = _serve(monkeypatch, lambda _: httpx.Response(200, json=body))

    info = tnupdate.fetch_info(tnupdate.parse_link(LINK))

    assert info == tnupdate.ShareInfo(1684778035414, "Pack", "<p>d</p>", 3, 2)
    url = str(seen[0].url)
    assert url.startswith("https://taskernet.com/_ah/api/datashare/v1/shares/")
    assert "countView" not in url
    assert "countDownload" not in url
    assert seen[0].headers["user-agent"].startswith("MapTasker/")


def test_info_with_fields_missing_is_still_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, lambda _: httpx.Response(200, json={"info": {}}))

    info = tnupdate.fetch_info(tnupdate.parse_link(LINK))

    assert (info.published_ms, info.name) == (0, "Pack")


def test_xml_is_fetched_from_the_data_endpoint_and_unpacked(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _serve(monkeypatch, lambda _: httpx.Response(200, json={"shareData": _pack("<TaskerData/>")}))

    assert tnupdate.fetch_xml(tnupdate.parse_link(LINK)) == "<TaskerData/>"
    assert "/sharedata/" in str(seen[0].url)


@pytest.mark.parametrize(
    ("response", "offline", "words"),
    [
        (httpx.Response(404, json={"error": {}}), False, "no share"),
        (httpx.Response(500, text="oops"), True, "HTTP 500"),
        (httpx.Response(200, text="<html>not json</html>"), True, "other than a share"),
        (httpx.Response(200, json=["a", "list"]), True, "other than a share"),
        (httpx.Response(302, headers={"location": "https://evil.example.com/"}), True, "HTTP 302"),
    ],
)
def test_every_way_an_answer_can_be_wrong_is_a_message(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, offline: bool, words: str
) -> None:
    """A missing share is the share's problem; the rest say TaskerNet could not be relied on."""
    seen = _serve(monkeypatch, lambda _: response)

    with pytest.raises(tnupdate.TaskerNetError, match=words) as error:
        tnupdate.fetch_info(tnupdate.parse_link(LINK))

    assert isinstance(error.value, tnupdate.TaskerNetOfflineError) is offline
    assert len(seen) == 1, "a redirect must not be followed"


def test_a_connection_that_fails_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        message = "no route"
        raise httpx.ConnectError(message, request=request)

    _serve(monkeypatch, refuse)

    with pytest.raises(tnupdate.TaskerNetOfflineError, match="Could not reach TaskerNet"):
        tnupdate.fetch_info(tnupdate.parse_link(LINK))


def test_an_answer_past_the_limit_is_not_read_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tnupdate, "_INFO_LIMIT", 100)
    _serve(monkeypatch, lambda _: httpx.Response(200, content=b"x" * 1000))

    with pytest.raises(tnupdate.TaskerNetError, match="far more"):
        tnupdate.fetch_info(tnupdate.parse_link(LINK))


# ##################################################################################
# The remembered links.
# ##################################################################################


def test_links_survive_a_restart(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    link = book.add("Project", "Pack", LINK)
    link.seen_ms, link.latest_ms = 5, 9
    book.save()

    again = tnupdate.LinkBook(tmp_path / "links.json").links[("Project", "Pack")]

    assert (again.link, again.seen_ms, again.latest_ms, again.share_name) == (LINK, 5, 9, "Pack")


def test_a_link_has_to_match_the_kind_it_is_attached_to(tmp_path: Path) -> None:
    with pytest.raises(tnupdate.TaskerNetError, match="Project"):
        tnupdate.LinkBook(tmp_path / "links.json").add("Task", "Pack", LINK)


def test_an_unreadable_file_is_set_aside_not_overwritten(tmp_path: Path) -> None:
    """The links were typed in by hand; the next save must not destroy the only copy of them."""
    path = tmp_path / "links.json"
    path.write_text("{ not json", encoding="utf-8")

    book = tnupdate.LinkBook(path)
    book.add("Project", "Pack", LINK)

    assert (tmp_path / "links.unreadable").read_text(encoding="utf-8") == "{ not json"
    assert list(tnupdate.LinkBook(path).links) == [("Project", "Pack")]


def test_unknown_fields_in_the_file_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "links.json"
    path.write_text(
        json.dumps({"links": [{"kind": "Task", "name": "T", "link": LINK, "from_a_newer_version": 1}]}),
        encoding="utf-8",
    )

    assert ("Task", "T") in tnupdate.LinkBook(path).links


def test_a_book_with_nowhere_to_live_still_works_for_the_run() -> None:
    book = tnupdate.LinkBook(None)

    book.add("Project", "Pack", LINK)

    assert not book.save()
    assert len(book.links) == 1
    assert book.baseline(book.links[("Project", "Pack")]) is None


def test_the_accepted_version_is_kept_and_forgotten_with_its_link(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    link = book.add("Project", "Pack", LINK)

    assert book.baseline(link) is None
    assert book.save_baseline(link, "<TaskerData>é</TaskerData>")
    assert book.baseline(link) == "<TaskerData>é</TaskerData>"
    book.remove(link)

    assert book.baseline(link) is None
    assert not list((tmp_path / tnupdate.BASELINES_FOLDER).glob("*"))


def test_a_damaged_baseline_is_no_baseline(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    link = book.add("Project", "Pack", LINK)
    book.save_baseline(link, "<x/>")
    for stored in (tmp_path / tnupdate.BASELINES_FOLDER).glob("*"):
        stored.write_bytes(b"not gzip")

    assert book.baseline(link) is None


def test_the_links_are_listed_in_a_steady_order(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    for kind, name in (("Task", "b"), ("Project", "z"), ("Task", "A"), ("Scene", "s"), ("Project", "m")):
        book.links[(kind, name)] = tnupdate.Link(kind, name, LINK)

    assert [(link.kind, link.name) for link in book.ordered()] == [
        ("Project", "m"),
        ("Project", "z"),
        ("Task", "A"),
        ("Task", "b"),
        ("Scene", "s"),
    ]


# ##################################################################################
# Checking.
# ##################################################################################


def test_a_link_goes_from_unchecked_to_unreviewed_to_current_to_update() -> None:
    link = _link()
    assert link.status == tnupdate.UNCHECKED

    link.latest_ms = 100
    assert link.status == tnupdate.UNREVIEWED

    link.seen_ms = 100
    assert link.status == tnupdate.CURRENT

    link.latest_ms = 101
    assert link.status == tnupdate.UPDATE


def test_a_check_records_what_is_published_and_leaves_the_accepted_version_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tnupdate, "fetch_info", lambda _: _info(500))
    link = _link()
    link.seen_ms, link.problem = 100, "old"

    assert tnupdate.check_link(link)

    assert (link.latest_ms, link.seen_ms, link.problem, link.status) == (500, 100, "", tnupdate.UPDATE)
    assert link.checked


def test_a_failed_check_says_why_and_keeps_what_was_known(monkeypatch: pytest.MonkeyPatch) -> None:
    def gone(_: object) -> None:
        message = "TaskerNet has no share at that link."
        raise tnupdate.TaskerNetError(message)

    monkeypatch.setattr(tnupdate, "fetch_info", gone)
    link = _link()
    link.latest_ms = 7

    assert not tnupdate.check_link(link)
    assert (link.problem, link.latest_ms) == ("TaskerNet has no share at that link.", 7)


def test_the_first_unreachable_check_ends_the_run_but_a_missing_share_does_not(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    for name in ("a", "b", "c"):
        book.add("Task", name, LINK.replace("Project", "Task"))
    asked: list[str] = []

    def check(link: tnupdate.Link) -> bool:
        asked.append(link.name)
        link.problem = "TaskerNet has no share at that link." if link.name == "a" else "Could not reach TaskerNet (x)."
        return False

    tnupdate.check_all(book, check=check)

    assert asked == ["a", "b"], "a missing share is its own problem; the first unreachable answer ends the run"


def test_checking_counts_the_links_with_something_newer(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    for name, seen, _latest in (("a", 1, 2), ("b", 2, 2), ("c", 1, 5)):
        book.add("Task", name, LINK.replace("Project", "Task")).seen_ms = seen

    def check(link: tnupdate.Link) -> bool:
        link.latest_ms = {"a": 2, "b": 2, "c": 5}[link.name]
        return True

    assert tnupdate.check_all(book, check=check) == 2
    assert tnupdate.LinkBook(tmp_path / "links.json").links[("Task", "c")].latest_ms == 5, "the answers are saved"


def test_only_links_not_checked_lately_are_due(tmp_path: Path) -> None:
    link = _link()
    assert link.due

    link.checked = clock.now().isoformat()
    assert not link.due

    link.checked = (clock.now() - timedelta(seconds=tnupdate.RECHECK_AFTER_SECONDS + 60)).isoformat()
    assert link.due

    link.checked = "garbage"
    assert link.due


def test_a_publish_date_reads_as_a_date_and_zero_as_unknown() -> None:
    assert tnupdate.describe_date(0) == "unknown"
    assert tnupdate.describe_date(1_700_000_000_000).startswith("1")  # 14-Nov or 15-Nov-2023 by timezone


# ##################################################################################
# What the link is attached to.
# ##################################################################################


def test_a_project_is_itself_and_everything_its_profiles_run() -> None:
    """Including the anonymous Task, which is in no list -- only in Dawn's own link to it."""
    scope = tnupdate.local_scope(_link(), PrimeItems)

    assert scope is not None
    assert set(scope.tables["all_projects"]) == {"Pack"}
    assert set(scope.tables["all_profiles"]) == {"100", "101"}
    assert set(scope.tables["all_tasks"]) == {"20", "21", "22"}
    assert "50" not in scope.tables["all_tasks"], "another Project's Task is not part of this one"


def test_a_profile_is_itself_and_the_tasks_it_runs() -> None:
    scope = tnupdate.local_scope(_link("Profile", "Dawn", LINK.replace("Project", "Profile")), PrimeItems)

    assert scope is not None
    assert set(scope.tables["all_profiles"]) == {"100"}
    assert set(scope.tables["all_tasks"]) == {"22"}


def test_a_task_is_itself_alone() -> None:
    scope = tnupdate.local_scope(_link("Task", "Morning", LINK.replace("Project", "Task")), PrimeItems)

    assert scope is not None
    assert set(scope.tables["all_tasks"]) == {"20"}
    assert not scope.tables["all_profiles"]


@pytest.mark.parametrize(
    ("kind", "name"), [("Project", "Nope"), ("Profile", "Nope"), ("Task", "Nope"), ("Scene", "Nope")]
)
def test_a_link_to_something_that_is_not_loaded_has_no_scope(kind: str, name: str) -> None:
    assert tnupdate.local_scope(_link(kind, name), PrimeItems) is None


# ##################################################################################
# Giving the share the ids the local copy has.
# ##################################################################################


def _aligned_ids(
    xml: str, link: tnupdate.Link | None = None, earlier: tnupdate.Aligned | None = None
) -> tnupdate.Aligned:
    link = link or _link()
    scope = tnupdate.local_scope(link, PrimeItems)
    return tnupdate.align_share(xml, link, scope, PrimeItems, earlier)


def test_each_object_takes_the_id_of_the_one_with_its_name_and_the_anonymous_task_follows_its_profile() -> None:
    aligned = _aligned_ids(_share())

    assert aligned.profiles == {"5": "100", "6": "101"}
    assert aligned.tasks == {"7": "20", "8": "21", "9": "22"}, (
        "the unnamed Task is found through the Profile that runs it"
    )
    assert "<id>100</id>" in aligned.xml
    assert "<mid0>22</mid0>" in aligned.xml, "the Profile's link follows the renumbering"
    assert "<pids>100,101</pids>" in aligned.xml
    assert "<tids>20,21</tids>" in aligned.xml


def test_objects_you_do_not_have_are_numbered_above_every_id_in_the_configuration() -> None:
    aligned = _aligned_ids(_V2)

    assert aligned.tasks["12"] not in _live("all_tasks")
    assert int(aligned.tasks["12"]) > 101
    assert "Brand New" in aligned.xml


def test_two_objects_of_one_name_do_not_both_become_the_same_one_of_yours() -> None:
    twin = _share().replace(
        '<Task sr="task9"', '<Task sr="taskx" ve="2"><id>13</id><nme>Morning</nme></Task>\n  <Task sr="task9"'
    )

    aligned = _aligned_ids(twin)

    assert aligned.tasks["7"] == "20"
    assert aligned.tasks["13"] != "20"


def test_your_profiles_enabled_state_is_kept_not_the_shares() -> None:
    """The share ships Profiles disabled and collapsed; yours are on.  Taking one must not turn it off."""
    aligned = _aligned_ids(_share())

    assert "<limit>" not in aligned.xml
    assert "<clp>" not in aligned.xml
    assert aligned.xml.count("<flags>10</flags>") == 2


def test_a_share_with_no_flags_at_all_matches_a_profile_you_enabled() -> None:
    """The real 'Flip To Shhh': the share has no <flags>, and the copy Tasker saved has 2."""
    share = _share().replace("<flags>8</flags>", "")

    aligned = _aligned_ids(share)

    # Only the enabled bit is yours to keep; the 8 your copy also has is not the share's to inherit.
    assert aligned.xml.count("<flags>2</flags>") == 2


def test_an_empty_argument_your_tasker_added_is_not_reported_as_the_authors_change() -> None:
    """Task 'Flip To Shh Setup' has an empty fifth argument the older Tasker that wrote the share did not."""
    _live("all_tasks")["20"]["xml"].find("Action").append(
        _live("all_tasks")["20"]["xml"].makeelement("Str", {"sr": "arg1", "ve": "3"})
    )

    held = _review(_share())

    assert held.identical, held.report
    assert ("Task", "20", maprestore.REVERT) not in _offered(held)


def test_an_empty_argument_your_tasker_added_to_a_condition_is_not_the_authors_change() -> None:
    """The real Http Server Example: every Event condition has an empty arg6 in the copy Tasker saved."""
    dawn = _live("all_profiles")["100"]["xml"]
    time = dawn.find("Time")
    time.set("sr", "con0")
    time.append(dawn.makeelement("Str", {"sr": "arg1", "ve": "3"}))
    share = _share().replace('<Time sr="con0">', '<Time sr="con0">', 2)

    held = _review(share)

    assert ("Profile", "100", maprestore.REVERT) not in _offered(held), held.report


def test_an_empty_argument_is_not_added_to_an_action_that_is_a_different_action() -> None:
    """When the author has changed which action sits at a position, nothing of yours is carried across."""
    mine = _live("all_tasks")["20"]["xml"]
    mine.find("Action").append(mine.makeelement("Str", {"sr": "arg1", "ve": "3"}))
    mine.find("Action/code").text = "523"

    aligned = _aligned_ids(_share())

    assert 'sr="arg1"' not in aligned.xml


def test_a_disabled_profile_keeps_its_settings_in_tasker_s_order() -> None:
    """The real 'Simple Chat Bot': disabled on both sides, and reported 'Changed.' for putting <limit> before <id>.

    Tasker writes a Profile's own fields alphabetically.  Taking yours out and putting it back at the
    index it has in YOUR list -- when the share's list is a different length -- put it in the wrong
    place, and the two Profiles differed in the order of their settings and in nothing else.
    """
    dawn = _live("all_profiles")["100"]["xml"]
    limit = type(dawn)("limit")
    limit.text = "true"
    dawn.insert([child.tag for child in dawn].index("id") + 1, limit)

    held = _review(_share())

    assert ("Profile", "100", maprestore.REVERT) not in {(c.kind, c.key, c.action) for c in held.everything}, (
        held.report
    )
    xml = _aligned_ids(_share()).xml
    assert xml.index("<id>100</id>") < xml.index("<limit>true</limit>")


def test_a_field_yours_has_and_the_share_lacks_goes_in_alphabetical_order() -> None:
    dawn = _live("all_profiles")["100"]["xml"]
    limit = type(dawn)("limit")
    limit.text = "true"
    dawn.insert([child.tag for child in dawn].index("id") + 1, limit)
    share = _share().replace("<limit>true</limit>", "")

    xml = _aligned_ids(share).xml
    first = xml[: xml.index("<Time")]

    order = [first.index(tag) for tag in ("<flags>", "<id>100</id>", "<limit>", "<mid0>")]
    assert order == sorted(order)


def test_a_profile_you_disabled_stays_disabled() -> None:
    dawn = _live("all_profiles")["100"]["xml"]
    dawn.find("flags").text = "8"
    # The element class the loaded tree is built from, which is not necessarily the stdlib's.
    limit = type(dawn)("limit")
    limit.text = "true"
    dawn.insert(2, limit)

    aligned = _aligned_ids(_share())

    assert aligned.xml.count("<limit>true</limit>") == 1
    assert aligned.xml.count("<flags>8</flags>") == 1


def test_a_top_object_you_renamed_is_still_the_same_object() -> None:
    """Your own rename is not the author's: the share's Project is given the name yours has."""
    _live("all_projects")["Pack"]["xml"].find("name").text = "My Pack"
    _live("all_projects")["My Pack"] = _live("all_projects").pop("Pack")
    link = _link("Project", "My Pack")

    aligned = _aligned_ids(_share(), link)

    assert "<name>My Pack</name>" in aligned.xml


def test_what_an_earlier_version_matched_stays_matched_when_the_author_renames_it() -> None:
    earlier = _aligned_ids(_share())

    followed = _aligned_ids(_V2, earlier=earlier)
    forgotten = _aligned_ids(_V2)

    assert followed.tasks["8"] == "21", "'Helper' became 'Assistant', and is still your Helper"
    assert forgotten.tasks["8"] != "21", "with nothing to go on, a new name is a new object"


# A Project whose one Profile has no name, and whose Entry Task has none either -- the commonest
# shape of a small share, and one with nothing to match by name.  The 'sr' attributes say the id
# they were written with, as Tasker writes them.
_SOLO_LOCAL = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Solo</name><pids>30</pids><tids>31</tids></Project>
  <Profile sr="prof30" ve="2"><cdate>1</cdate><flags>10</flags><id>30</id><mid0>32</mid0>
    <Time sr="con0"><fh>6</fh></Time></Profile>
  <Task sr="task31" ve="2"><id>31</id><nme>Setup</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">setup</Str></Action></Task>
  <Task sr="task32" ve="2"><id>32</id>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">entry</Str></Action></Task>
</TaskerData>
"""
_SOLO_SHARE = """<TaskerData sr="" dvi="1" tv="6.2.0-beta">
  <Project sr="proj0" ve="2"><name>Solo</name><pids>7</pids><tids>9</tids></Project>
  <Profile sr="prof7" ve="2"><cdate>1</cdate><clp>true</clp><flags>8</flags><id>7</id><limit>true</limit><mid0>8</mid0>
    <Time sr="con0"><fh>6</fh></Time></Profile>
  <Task sr="task8" ve="2"><id>8</id>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">entry</Str></Action></Task>
  <Task sr="task9" ve="2"><id>9</id><nme>Setup</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">setup</Str></Action></Task>
</TaskerData>
"""


def test_an_unnamed_profile_and_its_unnamed_task_are_matched_and_the_result_still_loads(tmp_path: Path) -> None:
    """The real 'Flip To Shhh' shape: a renumbered object whose 'sr' still said its old id made the loader fail.

    A Profile with no name is named from its conditions through the id in its 'sr' attribute, so
    renumbering it and leaving 'sr' alone raised a KeyError on the old id -- and Review said only
    that the file 'could not be read'.
    """
    _load_local(tmp_path, _SOLO_LOCAL)
    link = _link("Project", "Solo")

    held = _review(_SOLO_SHARE, link=link)

    aligned = _aligned_ids(_SOLO_SHARE, link)
    assert aligned.profiles == {"7": "30"}, "the one unnamed Profile on each side is the same Profile"
    assert aligned.tasks == {"8": "32", "9": "31"}, "and its unnamed Task is found through it"
    assert 'sr="prof30"' in aligned.xml
    assert 'sr="task32"' in aligned.xml
    assert held.identical, held.report


def test_two_unnamed_profiles_are_not_guessed_between(tmp_path: Path) -> None:
    """With more than one on a side there is nothing to choose between them, so none is paired."""
    twin = _SOLO_LOCAL.replace("</Profile>", '</Profile>\n  <Profile sr="prof33" ve="2"><id>33</id></Profile>', 1)
    twin = twin.replace("<pids>30</pids>", "<pids>30,33</pids>")
    _load_local(tmp_path, twin)

    aligned = _aligned_ids(_SOLO_SHARE, _link("Project", "Solo"))

    assert aligned.profiles["7"] not in {"30", "33"}


def test_a_named_profile_the_author_replaced_is_not_taken_for_yours(tmp_path: Path) -> None:
    """Dropping one named Profile and adding another looks the same as renaming one, and is not paired."""
    _load_local(tmp_path, _SOLO_LOCAL.replace("<id>30</id>", "<id>30</id><nme>Mine</nme>"))
    share = _SOLO_SHARE.replace("<id>7</id>", "<id>7</id><nme>Theirs</nme>")

    aligned = _aligned_ids(share, _link("Project", "Solo"))

    assert aligned.profiles["7"] != "30"


@pytest.mark.parametrize("text", ["<TaskerData>", "not xml at all", "<Other/>"])
def test_text_that_is_not_a_tasker_share_is_refused(text: str) -> None:
    with pytest.raises(tnupdate.TaskerNetError):
        _aligned_ids(text)


def test_xml_that_tries_to_expand_entities_is_refused() -> None:
    """The share comes from a stranger, so it is read with defusedxml, not the stdlib parser."""
    bomb = '<!DOCTYPE d [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><TaskerData>&b;</TaskerData>'

    with pytest.raises(tnupdate.TaskerNetError):
        _aligned_ids(bomb)


# ##################################################################################
# What is offered.
# ##################################################################################


def test_without_an_accepted_version_everything_that_differs_is_offered_and_import_noise_is_not() -> None:
    held = _review(_V2)

    assert held.author is None
    assert ("Task", "20", maprestore.REVERT) in _offered(held)
    assert ("Profile", "100", maprestore.REVERT) in _offered(held)
    # The one thing identical to yours -- Dusk's Task link aside -- is not a difference at all.
    assert all(key != "50" for _, key, _ in _offered(held)), "another Project's Task is never offered"


def test_a_share_that_matches_your_copy_differs_in_nothing_despite_every_id_being_different() -> None:
    held = _review(_share())

    assert held.identical, held.report
    assert not held.offer.candidates


def test_with_an_accepted_version_only_the_authors_changes_are_offered() -> None:
    held = _review(_V2, accepted=_share())

    offered = _offered(held)
    assert ("Task", "20", maprestore.REVERT) in offered, "Morning was edited"
    assert ("Task", "22", maprestore.REVERT) in offered, "the anonymous Task was edited"
    assert ("Task", "21", maprestore.REVERT) in offered, "Helper was renamed Assistant, and is still your Helper"
    assert ("Profile", "100", maprestore.REVERT) in offered, "Dawn's time moved"
    assert ("Profile", "101", maprestore.REVERT) not in offered, "Dusk was dropped, which is reported, not offered"
    new_tasks = {key for kind, key, action in offered if (kind, action) == ("Task", maprestore.BRING_BACK)}
    assert len(new_tasks) == 1, "Brand New"
    assert held.author is not None
    assert any("Dusk" in line for line in held.author.removed)


def test_the_differences_that_are_not_the_authors_stay_reachable() -> None:
    """Filtering to the author's changes must not make the other differences vanish."""
    _live("all_tasks")["20"]["xml"].find("Action/Str").text = "my own words"

    held = _review(_share(), accepted=_share())

    assert not held.offer.candidates, "nothing the author did"
    assert ("Task", "20", maprestore.REVERT) in {(c.kind, c.key, c.action) for c in held.everything}


def test_an_object_the_author_left_alone_is_not_offered_even_if_you_edited_it() -> None:
    """Your own edit of something the author never touched is not for the author's version to overwrite."""
    _live("all_tasks")["20"]["xml"].find("Action/Str").text = "my own words"
    unchanged = _V2.replace("hello there", "hello")

    held = _review(unchanged, accepted=_share())

    assert ("Task", "20", maprestore.REVERT) not in _offered(held)


def test_when_the_authors_two_versions_are_the_same_nothing_is_offered() -> None:
    held = _review(_share(), accepted=_share())

    assert held.author is not None
    assert held.author.nothing
    assert not held.offer.candidates


def test_an_accepted_version_that_cannot_be_read_falls_back_to_everything_that_differs() -> None:
    held = _review(_V2, accepted="<TaskerData")

    assert held.author is None
    assert held.offer.candidates


# ##################################################################################
# Taking an update.
# ##################################################################################


def _take(held: tnupdate.Review, kind: str, key: str) -> None:
    candidate = next(c for c in held.offer.candidates if (c.kind, c.key) == (kind, key))
    plan = maprestore.plan_restore(candidate, held.shared, held.from_when, state=PrimeItems)
    assert plan.can_apply, [block.explanation for block in plan.blocks]
    assert maprestore.restore(plan, state=PrimeItems) == (True, [])


def test_taking_a_task_puts_the_authors_version_in_the_place_of_yours() -> None:
    held = _review(_V2, accepted=_share())

    _take(held, "Task", "20")

    assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello there"
    assert _live("all_tasks")["20"]["xml"].findtext("id") == "20", "it keeps the id Tasker on the device knows it by"
    assert _live("all_tasks")["21"]["xml"].findtext("nme") == "Helper", "nothing else was touched"


def test_taking_the_anonymous_task_changes_that_task_and_does_not_add_another() -> None:
    held = _review(_V2, accepted=_share())
    before = set(_live("all_tasks"))

    _take(held, "Task", "22")

    assert _live("all_tasks")["22"]["xml"].findtext("Action/Str") == "anon v2"
    assert set(_live("all_tasks")) == before


def test_taking_a_profile_keeps_it_switched_on() -> None:
    held = _review(_V2, accepted=_share())

    _take(held, "Profile", "100")

    dawn = _live("all_profiles")["100"]["xml"]
    assert dawn.findtext("Time/fh") == "7", "the author's change came across"
    assert dawn.find("limit") is None
    assert dawn.find("clp") is None
    assert dawn.findtext("flags") == "10"
    assert dawn.findtext("mid0") == "22", "and it still runs your anonymous Task"


def test_taking_one_object_leaves_the_rest_to_be_taken_or_not() -> None:
    held = _review(_V2, accepted=_share())

    _take(held, "Task", "20")
    after = tnupdate.rescan(held, PrimeItems)

    assert after is not None
    assert ("Task", "20", maprestore.REVERT) not in _offered(after)
    assert ("Task", "22", maprestore.REVERT) in _offered(after), "each is taken on its own, from its own preview"


def test_taking_an_update_is_one_press_of_undo() -> None:
    held = _review(_V2, accepted=_share())
    _take(held, "Task", "20")
    assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello there"

    assert sessundo.undo(state=PrimeItems)

    assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello"


def test_a_new_task_from_the_author_is_added_to_the_project() -> None:
    held = _review(_V2, accepted=_share())
    new_key = next(c.key for c in held.offer.candidates if c.action == maprestore.BRING_BACK)

    _take(held, "Task", new_key)

    names = {entry["name"] for entry in _live("all_tasks").values()}
    assert "Brand New" in names
    tids = (_live("all_projects")["Pack"]["xml"].findtext("tids") or "").split(",")
    assert any(_live("all_tasks")[t]["name"] == "Brand New" for t in tids if t in _live("all_tasks"))


def test_the_review_is_gone_when_the_object_it_was_about_is() -> None:
    held = _review(_V2, accepted=_share())
    _live("all_projects").pop("Pack")

    assert tnupdate.rescan(held, PrimeItems) is None


# ##################################################################################
# Accepting, and the review end to end.
# ##################################################################################


def test_accepting_moves_the_version_forward_and_keeps_it_as_the_next_baseline(tmp_path: Path) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    link = book.add("Project", "Pack", LINK)
    held = _review(_V2, link=link)
    held.xml_text = _V2
    held.info = _info(1234)

    tnupdate.accept(book, held)

    assert link.seen_ms == 1234
    assert book.baseline(link) == _V2
    assert tnupdate.LinkBook(tmp_path / "links.json").links[("Project", "Pack")].seen_ms == 1234


def test_review_fetches_both_halves_and_brings_the_link_up_to_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    book = tnupdate.LinkBook(tmp_path / "links.json")
    link = book.add("Project", "Pack", LINK)
    book.save_baseline(link, _share())
    monkeypatch.setattr(tnupdate, "fetch_info", lambda _: _info(777))
    monkeypatch.setattr(tnupdate, "fetch_xml", lambda _: _V2)

    held, problem = tnupdate.review(link, PrimeItems, book)

    assert held is not None, problem
    assert (link.latest_ms, link.problem) == (777, "")
    assert held.author is not None
    assert held.offer.candidates


def test_review_says_why_when_it_cannot_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(_: object) -> None:
        message = "Could not reach TaskerNet (ConnectError).  Check the connection and try again."
        raise tnupdate.TaskerNetOfflineError(message)

    monkeypatch.setattr(tnupdate, "fetch_info", offline)

    held, problem = tnupdate.review(_link(), PrimeItems)

    assert held is None
    assert "Could not reach" in problem


def test_review_of_something_not_loaded_does_not_go_to_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tnupdate, "fetch_info", lambda _: pytest.fail("the network was asked"))

    held, problem = tnupdate.review(_link("Project", "Nope"), PrimeItems)

    assert held is None
    assert "not in the configuration" in problem


def test_a_review_leaves_the_loaded_configuration_exactly_as_it_was() -> None:
    before = {name: (id(entry["xml"]), entry["name"]) for name, entry in _live("all_tasks").items()}
    tables = PrimeItems.tasker_root_elements

    _review(_V2, accepted=_share())

    assert PrimeItems.tasker_root_elements is tables
    assert {name: (id(entry["xml"]), entry["name"]) for name, entry in _live("all_tasks").items()} == before


# ##################################################################################
# Accepting the whole of a version.
# ##################################################################################


def test_accepting_takes_every_change_in_one_go_and_in_one_undo() -> None:
    held = _review(_V2, accepted=_share())
    changes = list(held.offer.candidates)
    assert len(changes) == 5

    taken = tnupdate.accept_changes(changes, held, PrimeItems)

    assert (taken.done, taken.skipped) == (5, [])
    tasks = {entry["name"]: entry["xml"] for entry in _live("all_tasks").values()}
    assert tasks["Morning"].findtext("Action/Str") == "hello there"
    assert tasks["Assistant"].findtext("id") == "21", "the renamed Task is still yours, renamed"
    assert tasks["Brand New"] is not None
    assert _live("all_profiles")["100"]["xml"].findtext("Time/fh") == "7"
    assert _live("all_profiles")["100"]["xml"].findtext("flags") == "10", "still switched on"

    assert sessundo.undo(state=PrimeItems), "one press"

    names = {entry["name"] for entry in _live("all_tasks").values()}
    assert "Brand New" not in names
    assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello"
    assert _live("all_profiles")["100"]["xml"].findtext("Time/fh") == "6"
    assert _live("all_tasks")["21"]["xml"].findtext("nme") == "Helper"


def test_a_change_that_cannot_be_made_is_skipped_and_named_and_the_rest_still_go_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held = _review(_V2, accepted=_share())
    real = maprestore.restore

    def refuse_morning(plan: object, state: object) -> tuple[bool, list[str]]:
        if "Morning" in plan.what:
            return False, ["Something stands in the way."]
        return real(plan, state=state)

    monkeypatch.setattr(tnupdate.maprestore, "restore", refuse_morning)

    taken = tnupdate.accept_changes(list(held.offer.candidates), held, PrimeItems)

    assert taken.done == 4
    assert len(taken.skipped) == 1
    assert "Morning" in taken.skipped[0]
    assert "Something stands in the way." in taken.skipped[0]
    assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello"
    assert _live("all_tasks")["22"]["xml"].findtext("Action/Str") == "anon v2"


def test_a_profile_is_linked_to_a_task_that_came_in_with_it() -> None:
    """Each is planned against what the one before left, so a new Profile finds its new Task by name."""
    share = _share().replace(
        "</TaskerData>",
        """<Task sr="task30" ve="2"><id>30</id><nme>Fresh Task</nme>
      <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">fresh</Str></Action></Task>
    <Profile sr="prof31" ve="2"><id>31</id><mid0>30</mid0><nme>Fresh Profile</nme><Time sr="con0"><fh>9</fh></Time></Profile>
    </TaskerData>""",
    )
    held = _review(share, accepted=_share())
    assert {c.kind for c in held.offer.candidates} == {"Task", "Profile"}

    taken = tnupdate.accept_changes(list(held.offer.candidates), held, PrimeItems)

    assert taken.skipped == []
    profile = next(entry["xml"] for entry in _live("all_profiles").values() if entry["name"] == "Fresh Profile")
    entry = _live("all_tasks")[profile.findtext("mid0")]
    assert entry["name"] == "Fresh Task"


def test_a_last_checked_time_is_shown_as_the_other_dates_are() -> None:
    assert tnupdate.describe_checked("2026-10-07T15:38:00+00:00") != ""
    assert re.fullmatch(r"\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}", tnupdate.describe_checked("2026-10-07T15:38:00+00:00"))


@pytest.mark.parametrize("checked", ["", "yesterday-ish"])
def test_a_link_never_checked_or_with_an_unreadable_time_has_no_date(checked: str) -> None:
    assert tnupdate.describe_checked(checked) == ""
