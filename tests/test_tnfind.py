"""MapTasker TaskerNet share finder (tnfind) Unit Tests

Finding the share behind a Project is a guess, and what is tested is how the guess is kept honest.

A NAME NOMINATES; CONTENT DECIDES.  Names repeat across publishers, so the tests that matter are the
ones where a share has the right name and the wrong content -- which must not be linked -- and where
two shares both have the right name and plausible content -- which must not be decided between.

THE LISTING IS SLOW AND SOMEONE ELSE'S.  It is read a page at a time, so the tests cover stopping part-way,
TaskerNet going away part-way, a listing cut short being read again rather than trusted for a week, and
one that is whole being reused.

Nothing touches the network: the two calls that do (a page of the listing, a share's XML) are replaced, as
are the share's publish date, and the configuration is the one test_tnupdate builds.
"""

from __future__ import annotations

import json
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from maptasker.src.core import clock
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapops import tnfind, tnupdate

from tests.shared_fixtures import _LOCAL_XML, _load_local
from tests.test_tnupdate import _share

pytestmark = pytest.mark.usefixtures("_runtime")

PUBLISHER = "AS35m8ne7oO4s+aDx/wlzjdFTfVMWstg1ay5AkpiNdrLoSXEZdFfw1IpXiyJCVLNW0yn"


def _ref(kind: str, name: str, user: str = PUBLISHER) -> tnupdate.ShareRef:
    return tnupdate.ShareRef(user, f"{kind}:{name}", kind, name)


def _entry(kind: str, name: str, downloads: int = 100, user: str = PUBLISHER) -> tnfind.CatalogueEntry:
    return tnfind.CatalogueEntry(_ref(kind, name, user), downloads)


def _listed(kind: str, name: str, downloads: int = 100, user: str = PUBLISHER) -> dict:
    return {"url": _ref(kind, name, user).link, "downloads": downloads}


# Same name as the Project, nothing else in common.
_STRANGER = """<TaskerData sr="" dvi="1" tv="6.2.0-beta">
  <Project sr="proj0" ve="2"><name>Pack</name><pids>1</pids><tids>2</tids></Project>
  <Profile sr="prof1" ve="2"><id>1</id><mid0>2</mid0><nme>Tides</nme><Time sr="con0"><fh>3</fh></Time></Profile>
  <Task sr="task2" ve="2"><id>2</id><nme>Ferry</nme>
    <Action sr="act0" ve="7"><code>523</code><Str sr="arg0" ve="3">Boat leaves</Str><Str sr="arg1" ve="3">at noon</Str></Action></Task>
</TaskerData>
"""

# Half of it is the Project's own content, half is not.
_HALF = (
    _share()
    .replace(">anon<", ">somebody else's<")
    .replace(">helping<", ">another helper<")
    .replace(">Dusk<", ">Twilight<")
    .replace("<fh>18</fh>", "<fh>20</fh>")
)


def _book(tmp_path: Path) -> tnupdate.LinkBook:
    return tnupdate.LinkBook(tmp_path / "links.json")


def _no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tnfind, "_PAGE_DELAY_SECONDS", 0)


# ##################################################################################
# Signatures and scores.
# ##################################################################################


def test_what_differs_between_two_copies_of_one_thing_is_left_out_of_its_signature() -> None:
    import defusedxml.ElementTree as ET

    first = ET.fromstring(
        '<Task><id>1</id><cdate>5</cdate><nme>A</nme><Action><code>548</code><Str sr="arg0">hi</Str></Action></Task>'
    )
    other = ET.fromstring(
        '<Task><id>9</id><cdate>7</cdate><nme>A</nme><Action><code>548</code><Str sr="arg0">hi</Str></Action></Task>'
    )

    assert tnfind.signature([first]) == tnfind.signature([other])
    assert "nme=A" in tnfind.signature([first])
    assert "code=548" in tnfind.signature([first])


def test_similarity_is_one_for_the_same_zero_for_nothing_shared() -> None:
    assert tnfind.similarity({"a", "b"}, {"a", "b"}) == 1.0
    assert tnfind.similarity({"a"}, {"b"}) == 0.0
    assert tnfind.similarity(set(), set()) == 0.0
    assert tnfind.similarity({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_the_share_of_a_project_scores_high_against_that_project_despite_every_id_being_different() -> None:
    match = tnfind.score_share("Project", "Pack", _entry("Project", "Pack"), _share(), PrimeItems)

    assert match.score >= tnfind.STRONG_SCORE
    assert match.strong


def test_a_share_with_the_same_name_and_different_content_scores_low() -> None:
    match = tnfind.score_share("Project", "Pack", _entry("Project", "Pack"), _STRANGER, PrimeItems)

    assert match.score < tnfind.POSSIBLE_SCORE
    assert not match.strong


def test_a_share_with_some_of_the_content_is_in_between() -> None:
    match = tnfind.score_share("Project", "Pack", _entry("Project", "Pack"), _HALF, PrimeItems)

    assert tnfind.POSSIBLE_SCORE <= match.score < tnfind.STRONG_SCORE


def test_a_share_too_small_to_be_sure_of_is_never_strong() -> None:
    """A one-action Task shares most of its values with any other one-action Task."""
    tiny = '<TaskerData sr=""><Task sr="t"><id>1</id><nme>Morning</nme></Task></TaskerData>'
    match = tnfind.score_share("Task", "Morning", _entry("Task", "Morning"), tiny, PrimeItems)

    assert not match.strong


def test_a_share_that_is_not_xml_scores_nothing() -> None:
    assert tnfind.score_share("Project", "Pack", _entry("Project", "Pack"), "<not xml", PrimeItems).score == 0.0


# ##################################################################################
# The listing.
# ##################################################################################


def _pages(monkeypatch: pytest.MonkeyPatch, pages: list[dict | Exception]) -> list[str]:
    """Replace the listing with canned pages; return the tokens it was asked for."""
    asked: list[str] = []
    queue = list(pages)

    def page(token: str = "") -> dict:
        asked.append(token)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(tnupdate, "fetch_public_page", page)
    return asked


def test_the_listing_is_read_to_its_end_and_each_page_asked_for_by_the_last_ones_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_delay(monkeypatch)
    asked = _pages(
        monkeypatch,
        [
            {"shares": [_listed("Project", "A", 5), _listed("Task", "B", 9)], "pageToken": "t 1+/"},
            {"shares": [_listed("Scene", "C")], "pageToken": "t2"},
            {"shares": [_listed("Profile", "D")]},
        ],
    )

    catalogue = tnfind.crawl_catalogue(tnfind.Progress(), threading.Event())

    assert asked == ["", "t 1+/", "t2"]
    assert catalogue.complete
    assert {(e.ref.kind, e.ref.name) for e in catalogue.entries} == {
        ("Project", "A"),
        ("Task", "B"),
        ("Scene", "C"),
        ("Profile", "D"),
    }


def test_a_share_listed_twice_is_one_and_one_that_is_not_a_share_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_delay(monkeypatch)
    _pages(
        monkeypatch,
        [
            {
                "shares": [
                    _listed("Project", "A", 1),
                    _listed("Project", "A", 7),
                    {"url": "https://elsewhere.example/x"},
                    {},
                    {"url": None},
                ]
            }
        ],
    )

    catalogue = tnfind.crawl_catalogue(tnfind.Progress(), threading.Event())

    assert [(e.ref.name, e.downloads) for e in catalogue.entries] == [("A", 7)]


def test_a_token_that_does_not_move_ends_the_crawl_rather_than_looping_forever(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_delay(monkeypatch)
    asked = _pages(
        monkeypatch,
        [{"shares": [], "pageToken": "same"}, {"shares": [], "pageToken": "same"}, AssertionError("asked again")],
    )

    catalogue = tnfind.crawl_catalogue(tnfind.Progress(), threading.Event())

    assert catalogue.complete
    assert asked == ["", "same"]


def test_taskernet_going_away_part_way_keeps_what_was_read_and_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_delay(monkeypatch)
    _pages(
        monkeypatch,
        [
            {"shares": [_listed("Project", "A")], "pageToken": "t"},
            tnupdate.TaskerNetOfflineError("Could not reach TaskerNet (ConnectError)."),
        ],
    )

    catalogue = tnfind.crawl_catalogue(tnfind.Progress(), threading.Event())

    assert len(catalogue.entries) == 1
    assert not catalogue.complete
    assert "Could not reach" in catalogue.problem


def test_stop_ends_the_crawl_between_pages_with_what_it_has(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_delay(monkeypatch)
    stop = threading.Event()
    asked: list[str] = []

    def page(token: str = "") -> dict:
        asked.append(token)
        stop.set()
        return {"shares": [_listed("Project", "A")], "pageToken": "more"}

    monkeypatch.setattr(tnupdate, "fetch_public_page", page)

    catalogue = tnfind.crawl_catalogue(tnfind.Progress(), stop)

    assert len(asked) == 1
    assert len(catalogue.entries) == 1
    assert not catalogue.complete


def test_progress_says_where_the_crawl_has_got_to(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_delay(monkeypatch)
    _pages(monkeypatch, [{"shares": [_listed("Project", "A")]}])
    progress = tnfind.Progress()

    tnfind.crawl_catalogue(progress, threading.Event())

    assert "page 1" in progress.text
    assert "1 shares" in progress.text


def test_the_listing_is_kept_and_read_back(tmp_path: Path) -> None:
    path = tmp_path / "cat.json"
    catalogue = tnfind.Catalogue(
        [_entry("Project", "A", 5), _entry("Task", "B: x", 9)], clock.now().isoformat(), complete=True
    )

    assert tnfind.save_catalogue(catalogue, path)
    again = tnfind.load_catalogue(path)

    assert again is not None
    assert again.complete
    assert [(e.ref.kind, e.ref.name, e.downloads) for e in again.entries] == [("Project", "A", 5), ("Task", "B: x", 9)]
    assert 0 <= again.age_days < 1


@pytest.mark.parametrize("text", ["{ not json", '{"shares": [["u"]]}', '{"shares": [["u", "NoColon", 1]]}', "[]"])
def test_a_listing_that_cannot_be_read_is_none_not_an_error(tmp_path: Path, text: str) -> None:
    path = tmp_path / "cat.json"
    path.write_text(text, encoding="utf-8")

    assert tnfind.load_catalogue(path) is None


def test_with_nowhere_to_keep_it_the_listing_is_simply_not_kept() -> None:
    assert not tnfind.save_catalogue(tnfind.Catalogue(), None)
    assert tnfind.load_catalogue(None) is None


def test_the_listing_is_grouped_by_kind_and_lower_case_name_most_downloaded_first() -> None:
    catalogue = tnfind.Catalogue(
        [_entry("Project", "Weather", 5, "u1"), _entry("Project", "WEATHER", 50, "u2"), _entry("Task", "Weather", 9)]
    )

    grouped = catalogue.by_name()

    assert [e.downloads for e in grouped[("Project", "weather")]] == [50, 5]
    assert [e.downloads for e in grouped[("Task", "weather")]] == [9]


def test_a_listing_never_read_is_infinitely_old() -> None:
    assert tnfind.Catalogue().age_days == float("inf")


# ##################################################################################
# What there is to look for.
# ##################################################################################


def test_every_object_with_a_public_share_of_its_name_is_a_candidate_and_names_match_regardless_of_case(
    tmp_path: Path,
) -> None:
    catalogue = tnfind.Catalogue(
        [_entry("Project", "pack"), _entry("Task", "MORNING"), _entry("Task", "Nothing Of Yours")]
    )

    found = tnfind.candidates(PrimeItems, _book(tmp_path), catalogue)

    assert [(c.kind, c.name) for c in found] == [("Project", "Pack"), ("Task", "Morning")]


def test_a_kind_must_match_as_well_as_a_name(tmp_path: Path) -> None:
    found = tnfind.candidates(
        PrimeItems, _book(tmp_path), tnfind.Catalogue([_entry("Task", "Pack"), _entry("Scene", "Pack")])
    )

    assert found == []


def test_an_object_already_linked_is_not_looked_for_again(tmp_path: Path) -> None:
    book = _book(tmp_path)
    book.add("Project", "Pack", _ref("Project", "Pack").link)

    found = tnfind.candidates(PrimeItems, book, tnfind.Catalogue([_entry("Project", "Pack")]))

    assert found == []


def test_a_profile_with_no_name_of_its_own_has_nothing_to_match_by(tmp_path: Path) -> None:
    _load_local(tmp_path, _LOCAL_XML.replace("<nme>Dawn</nme>", ""))

    found = tnfind.candidates(
        PrimeItems, _book(tmp_path), tnfind.Catalogue([_entry("Profile", "Dawn"), _entry("Profile", "Unnamed")])
    )

    assert found == []


def test_only_the_most_downloaded_shares_of_one_name_are_checked(tmp_path: Path) -> None:
    catalogue = tnfind.Catalogue([_entry("Project", "Pack", n, f"u{n}") for n in range(1, 12)])

    (candidate,) = tnfind.candidates(PrimeItems, _book(tmp_path), catalogue)

    assert [e.downloads for e in candidate.entries] == [11, 10, 9, 8, 7]


def test_projects_come_first(tmp_path: Path) -> None:
    catalogue = tnfind.Catalogue([_entry("Task", "Morning"), _entry("Project", "Pack")])

    assert [c.kind for c in tnfind.candidates(PrimeItems, _book(tmp_path), catalogue)] == ["Project", "Task"]


# ##################################################################################
# The scan.
# ##################################################################################


def _scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entries: list[tnfind.CatalogueEntry],
    shares: dict[str, str],
    *,
    book: tnupdate.LinkBook | None = None,
    stop: threading.Event | None = None,
    published: int = 1_700_000_000_000,
) -> tuple[tnfind.ScanResult, tnupdate.LinkBook, list[str]]:
    """Scan with a listing already kept, shares served from `shares` (by share id), and a publish date."""
    book = book or _book(tmp_path)
    path = tmp_path / "cat.json"
    tnfind.save_catalogue(tnfind.Catalogue(entries, clock.now().isoformat(), complete=True), path)
    fetched: list[str] = []

    def fetch(ref: tnupdate.ShareRef) -> str:
        fetched.append(f"{ref.user[:4]}:{ref.share_id}")
        return shares[f"{ref.user[:4]}:{ref.share_id}"]

    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(published, ref.name, "", 0, 0))
    result = tnfind.scan(
        PrimeItems,
        book,
        refresh=False,
        progress=tnfind.Progress(),
        stop=stop or threading.Event(),
        path=path,
        fetch=fetch,
    )
    return result, book, fetched


def _key(entry: tnfind.CatalogueEntry) -> str:
    return f"{entry.ref.user[:4]}:{entry.ref.share_id}"


def test_a_share_whose_content_agrees_is_linked_with_the_version_published_now_and_kept_as_the_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack = _entry("Project", "Pack")

    result, book, _ = _scan(tmp_path, monkeypatch, [pack], {_key(pack): _share()})

    assert [m.name for m in result.linked] == ["Pack"]
    link = book.links[("Project", "Pack")]
    assert link.auto
    assert link.link == pack.ref.link
    assert link.seen_ms == link.latest_ms == 1_700_000_000_000
    assert book.baseline(link) == _share(), "so the next update is compared with this version"
    assert tnupdate.LinkBook(tmp_path / "links.json").links[("Project", "Pack")].auto, (
        "and it is remembered as found, not typed"
    )


def test_a_share_of_the_same_name_with_different_content_is_not_linked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole reason a name is not enough."""
    stranger = _entry("Project", "Pack", user="OTHERuser")

    result, book, fetched = _scan(tmp_path, monkeypatch, [stranger], {_key(stranger): _STRANGER})

    assert (result.linked, result.possible, result.different) == ([], [], 1)
    assert book.links == {}
    assert fetched == [_key(stranger)], "it was looked at"


def test_the_right_share_wins_over_a_more_downloaded_stranger_of_the_same_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stranger = _entry("Project", "Pack", downloads=99999, user="OTHERuser")
    genuine = _entry("Project", "Pack", downloads=10)

    result, book, _ = _scan(
        tmp_path, monkeypatch, [stranger, genuine], {_key(stranger): _STRANGER, _key(genuine): _share()}
    )

    assert book.links[("Project", "Pack")].link == genuine.ref.link
    assert len(result.linked) == 1


def test_two_publishers_whose_shares_both_agree_are_not_decided_between(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fork.  Picking one is the wrong guess to make quietly."""
    first = _entry("Project", "Pack", user="AAAAuser")
    second = _entry("Project", "Pack", user="BBBBuser")

    result, book, _ = _scan(tmp_path, monkeypatch, [first, second], {_key(first): _share(), _key(second): _share()})

    assert result.linked == []
    assert book.links == {}
    assert len(result.possible) == 2


def test_a_share_with_some_of_the_content_is_offered_not_linked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    half = _entry("Project", "Pack")

    result, book, _ = _scan(tmp_path, monkeypatch, [half], {_key(half): _HALF})

    assert result.linked == []
    assert [m.name for m in result.possible] == ["Pack"]
    assert book.links == {}


def test_a_project_linked_in_full_leaves_its_own_members_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Its Profiles and Tasks are in the share just linked; a separate share of 'Morning' adds nothing."""
    pack = _entry("Project", "Pack")
    morning = _entry("Task", "Morning")

    result, book, fetched = _scan(
        tmp_path, monkeypatch, [pack, morning], {_key(pack): _share(), _key(morning): "<TaskerData/>"}
    )

    assert set(book.links) == {("Project", "Pack")}
    assert fetched == [_key(pack)], "the Task's share was not even downloaded"
    assert result.checked == 1


def test_objects_outside_a_linked_project_are_still_looked_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = _entry("Project", "Pack")
    elsewhere = _entry("Task", "Elsewhere")

    _, _, fetched = _scan(
        tmp_path, monkeypatch, [pack, elsewhere], {_key(pack): _share(), _key(elsewhere): "<TaskerData/>"}
    )

    assert _key(elsewhere) in fetched


def test_a_share_that_cannot_be_downloaded_is_skipped_and_the_rest_go_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gone = _entry("Project", "Pack", downloads=500, user="GONEuser")
    genuine = _entry("Project", "Pack", downloads=5)
    shares = {_key(genuine): _share()}
    book = _book(tmp_path)
    tnfind.save_catalogue(
        tnfind.Catalogue([gone, genuine], clock.now().isoformat(), complete=True), tmp_path / "cat.json"
    )

    def fetch(ref: tnupdate.ShareRef) -> str:
        if ref.user == "GONEuser":
            message = "TaskerNet has no share at that link."
            raise tnupdate.TaskerNetError(message)
        return shares[_key(genuine)]

    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(1, ref.name, "", 0, 0))
    result = tnfind.scan(
        PrimeItems,
        book,
        refresh=False,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=tmp_path / "cat.json",
        fetch=fetch,
    )

    assert [m.ref.user for m in result.linked] == [PUBLISHER]


def test_an_object_already_linked_is_left_exactly_as_it_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = _book(tmp_path)
    mine = book.add("Project", "Pack", _ref("Project", "Pack", "MINEuser").link)
    mine.seen_ms = 42
    pack = _entry("Project", "Pack")

    result, book, fetched = _scan(tmp_path, monkeypatch, [pack], {_key(pack): _share()}, book=book)

    assert result.linked == [] and fetched == []
    assert book.links[("Project", "Pack")].link == mine.link
    assert book.links[("Project", "Pack")].seen_ms == 42


def test_stop_ends_the_scan_and_keeps_what_it_had_linked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = _entry("Project", "Pack")
    elsewhere = _entry("Task", "Elsewhere")
    stop = threading.Event()
    shares = {_key(pack): _share(), _key(elsewhere): "<TaskerData/>"}
    book = _book(tmp_path)
    tnfind.save_catalogue(
        tnfind.Catalogue([pack, elsewhere], clock.now().isoformat(), complete=True), tmp_path / "cat.json"
    )

    def fetch(ref: tnupdate.ShareRef) -> str:
        stop.set()  # stopped while the first is being read
        return shares[_key(tnfind.CatalogueEntry(ref, 0))]

    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(1, ref.name, "", 0, 0))
    result = tnfind.scan(
        PrimeItems, book, refresh=False, progress=tnfind.Progress(), stop=stop, path=tmp_path / "cat.json", fetch=fetch
    )

    assert result.stopped
    assert [m.name for m in result.linked] == ["Pack"], "what was found before the stop stays found"
    assert ("Task", "Elsewhere") not in book.links


def test_there_is_a_ceiling_on_how_many_shares_one_scan_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tnfind, "_MAX_DOWNLOADS", 1)
    first = _entry("Project", "Pack", 9, "AAAAuser")
    second = _entry("Project", "Pack", 8, "BBBBuser")

    result, _, fetched = _scan(tmp_path, monkeypatch, [first, second], {_key(first): _STRANGER, _key(second): _share()})

    assert len(fetched) == 1
    assert "downloads" in result.problem


# ----------------------------------------------------------------------------------
# Where the listing comes from.
# ----------------------------------------------------------------------------------


def test_a_listing_read_to_its_end_lately_is_reused_without_asking_taskernet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tnupdate, "fetch_public_page", lambda token="": pytest.fail("the listing was read again"))
    pack = _entry("Project", "Pack")

    result, _, _ = _scan(tmp_path, monkeypatch, [pack], {_key(pack): _share()})

    assert result.catalogue_complete
    assert len(result.linked) == 1


def test_a_listing_cut_short_is_read_again_not_trusted_for_a_week(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_delay(monkeypatch)
    path = tmp_path / "cat.json"
    tnfind.save_catalogue(tnfind.Catalogue([_entry("Project", "Pack")], clock.now().isoformat(), complete=False), path)
    asked = _pages(monkeypatch, [{"shares": [_listed("Task", "Other")]}])

    tnfind.scan(
        PrimeItems,
        _book(tmp_path),
        refresh=False,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=path,
        fetch=lambda _ref: "",
    )

    assert asked == [""]


def test_an_old_listing_and_one_the_user_asked_to_replace_are_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_delay(monkeypatch)
    path = tmp_path / "cat.json"
    old = (clock.now() - timedelta(days=tnfind.CATALOGUE_MAX_AGE_DAYS + 1)).isoformat()
    tnfind.save_catalogue(tnfind.Catalogue([_entry("Project", "Pack")], old, complete=True), path)
    asked = _pages(monkeypatch, [{"shares": [_listed("Task", "Other")]}, {"shares": [_listed("Task", "Other")]}])

    tnfind.scan(
        PrimeItems,
        _book(tmp_path),
        refresh=False,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=path,
        fetch=lambda _ref: "",
    )
    tnfind.save_catalogue(tnfind.Catalogue([_entry("Project", "Pack")], clock.now().isoformat(), complete=True), path)
    tnfind.scan(
        PrimeItems,
        _book(tmp_path),
        refresh=True,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=path,
        fetch=lambda _ref: "",
    )

    assert asked == ["", ""]


def test_when_taskernet_cannot_be_reached_and_nothing_is_kept_nothing_is_linked_and_the_reason_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_delay(monkeypatch)
    _pages(monkeypatch, [tnupdate.TaskerNetOfflineError("Could not reach TaskerNet (ConnectError).")])

    result = tnfind.scan(
        PrimeItems,
        _book(tmp_path),
        refresh=False,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=tmp_path / "cat.json",
    )

    assert result.linked == [] and result.catalogue_size == 0
    assert "Could not reach" in result.problem


def test_when_taskernet_stops_answering_the_kept_listing_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_delay(monkeypatch)
    path = tmp_path / "cat.json"
    old = (clock.now() - timedelta(days=30)).isoformat()
    pack = _entry("Project", "Pack")
    tnfind.save_catalogue(tnfind.Catalogue([pack], old, complete=True), path)
    _pages(monkeypatch, [tnupdate.TaskerNetOfflineError("Could not reach TaskerNet (ConnectError).")])
    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(1, ref.name, "", 0, 0))

    result = tnfind.scan(
        PrimeItems,
        _book(tmp_path),
        refresh=False,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=path,
        fetch=lambda _ref: _share(),
    )

    assert [m.name for m in result.linked] == ["Pack"]


# ##################################################################################
# Linking.
# ##################################################################################


def test_a_link_made_when_taskernet_will_not_give_the_date_is_unreviewed_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_ref: object) -> None:
        message = "Could not reach TaskerNet (ConnectError)."
        raise tnupdate.TaskerNetOfflineError(message)

    monkeypatch.setattr(tnupdate, "fetch_info", refuse)
    match = tnfind.Match("Project", "Pack", _ref("Project", "Pack"), 0.9, 1, _share())

    link = tnfind.link_match(_book(tmp_path), match, auto=True)

    assert link.status == tnupdate.UNCHECKED
    assert "Could not reach" in link.problem
    assert link.seen_ms == 0, "so the first Review sets the version"


def test_a_link_chosen_by_the_user_is_not_marked_as_found_automatically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(5, ref.name, "", 0, 0))
    match = tnfind.Match("Project", "Pack", _ref("Project", "Pack"), 0.5, 1, _share())

    assert not tnfind.link_match(_book(tmp_path), match, auto=False).auto


def test_links_saved_before_this_existed_still_load(tmp_path: Path) -> None:
    path = tmp_path / "links.json"
    path.write_text(
        json.dumps({"links": [{"kind": "Task", "name": "T", "link": _ref("Task", "T").link}]}), encoding="utf-8"
    )

    assert tnupdate.LinkBook(path).links[("Task", "T")].auto is False


def test_a_possible_match_carries_the_date_its_share_was_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    half = _entry("Project", "Pack")

    result, _, _ = _scan(tmp_path, monkeypatch, [half], {_key(half): _HALF}, published=1_700_000_000_000)

    assert [m.published_ms for m in result.possible] == [1_700_000_000_000]


def test_a_linked_match_carries_it_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = _entry("Project", "Pack")

    result, _, _ = _scan(tmp_path, monkeypatch, [pack], {_key(pack): _share()}, published=1_650_000_000_000)

    assert [m.published_ms for m in result.linked] == [1_650_000_000_000]


def test_a_possible_match_whose_date_taskernet_will_not_give_is_still_offered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    half = _entry("Project", "Pack")
    book = _book(tmp_path)
    tnfind.save_catalogue(tnfind.Catalogue([half], clock.now().isoformat(), complete=True), tmp_path / "cat.json")

    def refuse(_ref: object) -> None:
        message = "Could not reach TaskerNet (ConnectError)."
        raise tnupdate.TaskerNetOfflineError(message)

    monkeypatch.setattr(tnupdate, "fetch_info", refuse)
    result = tnfind.scan(
        PrimeItems,
        book,
        refresh=False,
        progress=tnfind.Progress(),
        stop=threading.Event(),
        path=tmp_path / "cat.json",
        fetch=lambda _ref: _HALF,
    )

    assert [(m.name, m.published_ms) for m in result.possible] == [("Pack", 0)]


# ----------------------------------------------------------------------------------
# Stopping.
# ----------------------------------------------------------------------------------


def test_stopping_while_the_list_is_read_still_compares_what_was_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop ends the READING.  What had been read is set beside what you have, and what agrees is linked."""
    _no_delay(monkeypatch)
    stop = threading.Event()
    pack = _entry("Project", "Pack")

    def page(token: str = "") -> dict:
        stop.set()  # pressed while the first page is being read
        return {"shares": [_listed("Project", "Pack")], "pageToken": "more"}

    monkeypatch.setattr(tnupdate, "fetch_public_page", page)
    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(1, ref.name, "", 0, 0))
    book = _book(tmp_path)
    progress = tnfind.Progress()

    result = tnfind.scan(
        PrimeItems,
        book,
        refresh=True,
        progress=progress,
        stop=stop,
        path=tmp_path / "cat.json",
        fetch=lambda _ref: _share(),
    )

    assert result.listing_stopped
    assert not result.catalogue_complete
    assert [m.name for m in result.linked] == ["Pack"], "compared against the part that was read"
    assert not result.stopped, "the comparing was not stopped"
    assert not stop.is_set(), "so a second press can stop that too"
    assert progress.phase == tnfind.COMPARING
    assert pack.ref.user  # the share compared was the one read


def test_a_second_stop_ends_the_comparing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_delay(monkeypatch)
    stop = threading.Event()
    calls = {"pages": 0, "fetched": 0}

    def page(token: str = "") -> dict:
        calls["pages"] += 1
        stop.set()
        return {"shares": [_listed("Project", "Pack"), _listed("Task", "Elsewhere")], "pageToken": "more"}

    def fetch(_ref: object) -> str:
        calls["fetched"] += 1
        stop.set()  # the second Stop, during the comparing
        return _share()

    monkeypatch.setattr(tnupdate, "fetch_public_page", page)
    monkeypatch.setattr(tnupdate, "fetch_info", lambda ref: tnupdate.ShareInfo(1, ref.name, "", 0, 0))

    result = tnfind.scan(
        PrimeItems,
        _book(tmp_path),
        refresh=True,
        progress=tnfind.Progress(),
        stop=stop,
        path=tmp_path / "cat.json",
        fetch=fetch,
    )

    assert result.listing_stopped
    assert result.stopped
    assert calls["fetched"] == 1, "the Task's share was never fetched"


def test_stopping_before_anything_was_read_has_nothing_to_compare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = threading.Event()
    stop.set()
    monkeypatch.setattr(tnupdate, "fetch_public_page", lambda token="": pytest.fail("a page was read after Stop"))

    result = tnfind.scan(
        PrimeItems, _book(tmp_path), refresh=True, progress=tnfind.Progress(), stop=stop, path=tmp_path / "cat.json"
    )

    assert result.stopped
    assert not result.listing_stopped
    assert (result.linked, result.possible, result.catalogue_size) == ([], [], 0)
