"""Search in a Map, Diagram or Misc view (guiwins_search.TextViewSearch.search_event and what follows).

The crawl itself runs in the browser (see test_search_crawl for the script it is built from), so here
the browser's answer is supplied: a stand-in for the page's run_javascript hands back the results the script
would have, or times out, and what is asserted is what the view does with them -- the results window it draws, the
notice it gives instead of one, the jump a row sends back to the page, and the single remembered search that
saves a repeat from crawling the page again.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from maptasker.src.gui import guiwins_search
from nicegui.client import Client

from tests.search_dialog import built, by_text, click, field, labels, links, open_page
from tests.test_mapfind import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from nicegui.testing.user import User

_HITS = [
    {"elementId": "m1", "lineNumber": 12, "text": "HTTP Request to the server"},
    {"elementId": "m2", "lineNumber": 40, "text": "Flash: http done"},
]


@pytest.fixture(autouse=True)
def _browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """The configuration loaded, and the page's JavaScript replaced by a record and a scripted answer."""
    _load(_FIXTURE_XML)
    built.clear()
    built.update(title="Map", scripts=[], answer={"results": list(_HITS), "totalMatches": len(_HITS)}, view=None)

    real = Client.run_javascript

    def run_javascript(self: Client, code: str, *, timeout: float = 1.0) -> object:
        # NiceGUI uses the same call to drive its own widgets (runMethod(...)); those are not the view's scripts.
        if code.startswith("return runMethod"):
            return real(self, code, timeout=timeout)
        # Recorded when called, not when awaited: a row's jump fires its script and never awaits it.
        built["scripts"].append((code, timeout))

        class Answered:
            """Awaitable like the real response, and like it, fine to leave unawaited."""

            def __await__(self) -> object:
                answer = built["answer"]
                if isinstance(answer, Exception):
                    raise answer
                yield from ()
                return answer

        return Answered()

    monkeypatch.setattr(Client, "run_javascript", run_javascript, raising=False)


async def _search(user: User, text: str) -> None:
    field(user, "Search").value = text
    click(user, by_text(user, "Search")[0])
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_an_empty_search_asks_for_a_term_and_crawls_nothing() -> None:
    async with open_page() as user:
        await _search(user, "   ")
        assert user.notify.contains("Please enter a search term.")
        assert built["scripts"] == []


@pytest.mark.asyncio
async def test_a_search_crawls_the_page_with_a_generous_timeout_and_lists_what_it_found() -> None:
    async with open_page() as user:
        view = built["view"]
        await _search(user, "HTTP")

        ((code, timeout),) = built["scripts"]
        assert timeout == guiwins_search.SEARCH_JAVASCRIPT_TIMEOUT
        assert code == guiwins_search.search_crawl_js(view.scroll_area.id, "HTTP", 0)

        assert "Search Results for 'HTTP' (2 matches)" in labels(user)
        assert [link.text for link in links(user)] == ["Line #12", "Line #40"]
        assert "HTTP Request to the server" in labels(user)


@pytest.mark.asyncio
async def test_a_search_with_no_hits_says_so_instead_of_opening_a_window() -> None:
    built["answer"] = {"results": [], "totalMatches": 0}
    async with open_page() as user:
        await _search(user, "zzz")
        assert user.notify.contains("No matches found for: 'zzz'")
        assert links(user) == []


@pytest.mark.asyncio
async def test_a_search_cut_short_says_how_many_of_how_many() -> None:
    built["answer"] = {"results": list(_HITS), "totalMatches": 500, "truncated": True}
    async with open_page() as user:
        await _search(user, "http")
        assert user.notify.contains("Showing first 2 of 500 matches for: 'http'")
        assert "Search Results for 'http' (2 of 500 matches)" in labels(user)


@pytest.mark.asyncio
async def test_a_search_that_times_out_says_so_and_remembers_nothing() -> None:
    built["answer"] = TimeoutError()
    async with open_page() as user:
        built["view"]._content_token = 3
        await _search(user, "http")
        assert user.notify.contains("The search did not finish.")
        assert built["view"]._last_search is None


@pytest.mark.asyncio
async def test_following_a_row_closes_the_window_and_sends_the_jump_to_the_page() -> None:
    async with open_page() as user:
        await _search(user, "http")
        built["scripts"].clear()
        click(user, links(user)[1])
        await asyncio.sleep(0.1)
        assert [code for code, _timeout in built["scripts"]] == [guiwins_search.search_jump_js("m2")]


@pytest.mark.asyncio
async def test_the_same_search_again_is_answered_from_memory_once_the_content_has_settled() -> None:
    async with open_page() as user:
        built["view"]._content_token = 7
        await _search(user, "http")
        assert built["view"]._last_search == ("http", _HITS, 2, False)

        await _search(user, "HTTP")  # the same search, typed another way
        assert len(built["scripts"]) == 1
        assert labels(user).count("Search Results for 'HTTP' (2 matches)") >= 1


@pytest.mark.asyncio
async def test_a_different_search_crawls_again() -> None:
    async with open_page() as user:
        built["view"]._content_token = 7
        await _search(user, "http")
        await _search(user, "flash")
        assert len(built["scripts"]) == 2
        assert built["view"]._last_search[0] == "flash"


@pytest.mark.asyncio
async def test_content_still_streaming_in_is_never_remembered() -> None:
    async with open_page() as user:
        await _search(user, "http")
        assert built["view"]._last_search is None
        await _search(user, "http")
        assert len(built["scripts"]) == 2


@pytest.mark.asyncio
async def test_clearing_the_highlights_forgets_the_remembered_search() -> None:
    async with open_page() as user:
        built["view"]._content_token = 7
        await _search(user, "http")
        built["view"].invalidate_search_cache()
        await _search(user, "http")
        assert len(built["scripts"]) == 2


def test_a_jump_script_names_the_element_it_marks() -> None:
    script = guiwins_search.search_jump_js("m9")
    assert 'document.getElementById("m9")' in script
    assert "search-highlight-active" in script
