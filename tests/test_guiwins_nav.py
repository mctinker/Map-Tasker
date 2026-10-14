"""Which windows are still alive, and landing a clicked finding in the Map or Diagram that holds it."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from maptasker.src.core import mapjump
from maptasker.src.gui import guiwins_nav

# ##################################################################################
# What is still alive
# ##################################################################################


class _Element:
    def __init__(self, *, deleted: bool = False, client: object = "alive") -> None:
        self.is_deleted = deleted
        self._client = client

    @property
    def client(self) -> object:
        if self._client is None:
            raise RuntimeError("the client was garbage collected")
        return SimpleNamespace(is_deleted=self._client == "deleted")


def test_nothing_is_not_live() -> None:
    assert guiwins_nav.element_is_live(None) is False


def test_an_element_that_is_there_is_live() -> None:
    assert guiwins_nav.element_is_live(_Element()) is True


def test_a_deleted_element_is_not() -> None:
    assert guiwins_nav.element_is_live(_Element(deleted=True)) is False


def test_an_element_whose_client_has_gone_is_not() -> None:
    assert guiwins_nav.element_is_live(_Element(client=None)) is False


def test_an_element_whose_page_was_deleted_is_not() -> None:
    assert guiwins_nav.element_is_live(_Element(client="deleted")) is False


def test_a_view_is_live_if_its_scroll_area_or_tree_is() -> None:
    assert guiwins_nav.view_is_live(SimpleNamespace(scroll_area=_Element())) is True
    assert guiwins_nav.view_is_live(SimpleNamespace(scroll_area=None, tree=_Element())) is True
    assert guiwins_nav.view_is_live(SimpleNamespace(scroll_area=_Element(deleted=True))) is False
    assert guiwins_nav.view_is_live(None) is False


def _window(*views: object) -> SimpleNamespace:
    return SimpleNamespace(textviews=list(views), textview=False)


def test_views_that_died_are_pruned_when_asked_for() -> None:
    alive, dead = SimpleNamespace(scroll_area=_Element()), SimpleNamespace(scroll_area=_Element(deleted=True))
    window = _window(alive, dead)
    assert guiwins_nav.live_views(window) == [alive]
    assert window.textviews == [alive]


def test_a_window_that_has_shown_no_views_has_none_live() -> None:
    assert guiwins_nav.live_views(SimpleNamespace()) == []


def test_a_new_view_becomes_the_current_one_and_joins_the_rest() -> None:
    first, second = SimpleNamespace(scroll_area=_Element()), SimpleNamespace(scroll_area=_Element())
    window = _window(first)
    guiwins_nav.register_view(window, second)
    assert window.textviews == [first, second]
    assert window.textview is second


def test_forgetting_views_clears_them_all() -> None:
    window = _window(SimpleNamespace(scroll_area=_Element()))
    window.textview = "something"
    guiwins_nav.forget_views(window)
    assert window.textviews == []
    assert window.textview is False


# ##################################################################################
# Landing a jump in the Map
# ##################################################################################
class _Client:
    """A browser page that answers every script with what it was told to, and records them."""

    def __init__(self, answer: object = True, error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.scripts: list[str] = []

    async def run_javascript(self, script: str, timeout: float | None = None) -> object:
        self.scripts.append(script)
        if self.error is not None:
            raise self.error
        return self.answer


def _view(title: str, *, scope: str = "", client: _Client | None = None) -> SimpleNamespace:
    page = client or _Client()
    area = SimpleNamespace(client=page, id=7, is_deleted=False)
    return SimpleNamespace(title=title, map_scope=scope, scroll_area=area)


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch):
    """Make the given views the ones that are open, and record each window brought to the front."""
    raised: list[object] = []
    monkeypatch.setattr(guiwins_nav, "_bring_to_front", raised.append)

    def show(*views: SimpleNamespace) -> SimpleNamespace:
        monkeypatch.setattr(guiwins_nav, "live_views", lambda _gui: list(views))
        return SimpleNamespace(state=SimpleNamespace())

    show.raised = raised
    return show


_TASK = mapjump.Target(mapjump.TASK, "11", name="Wake Up", project="Home")


def test_a_map_built_for_the_right_project_takes_the_jump(windows) -> None:
    view = _view("Map View", scope="Home")
    assert asyncio.run(guiwins_nav.jump_map_view(windows(view), _TASK)) is True
    assert view.scroll_area.client.scripts
    assert windows.raised == [view]


def test_a_map_of_a_different_project_is_passed_over(windows) -> None:
    """A map of the whole file contains everything, and landing in it would never show the user the Project they asked for."""
    view = _view("Map View", scope="")
    assert asyncio.run(guiwins_nav.jump_map_view(windows(view), _TASK)) is False
    assert view.scroll_area.client.scripts == []


def test_a_window_that_is_not_a_map_is_passed_over(windows) -> None:
    view = _view("Diagram View", scope="Home")
    assert asyncio.run(guiwins_nav.jump_map_view(windows(view), _TASK)) is False


def test_the_newest_map_is_tried_first(windows) -> None:
    older, newer = _view("Map View", scope="Home"), _view("Map View", scope="Home")
    asyncio.run(guiwins_nav.jump_map_view(windows(older, newer), _TASK))
    assert newer.scroll_area.client.scripts
    assert older.scroll_area.client.scripts == []


def test_a_map_that_does_not_hold_the_object_hands_over_to_the_next(windows) -> None:
    older, newer = _view("Map View", scope="Home"), _view("Map View", scope="Home", client=_Client(answer=False))
    assert asyncio.run(guiwins_nav.jump_map_view(windows(older, newer), _TASK)) is True
    assert older.scroll_area.client.scripts


@pytest.mark.parametrize("failure", [TimeoutError(), RuntimeError("page gone"), AttributeError("no client")])
def test_a_page_that_goes_away_mid_jump_is_one_more_map_without_the_object(windows, failure: Exception) -> None:
    view = _view("Map View", scope="Home", client=_Client(error=failure))
    assert asyncio.run(guiwins_nav.jump_map_view(windows(view), _TASK)) is False


def test_no_map_open_means_no_jump(windows) -> None:
    assert asyncio.run(guiwins_nav.jump_map_view(windows(), _TASK)) is False


# ##################################################################################
# Landing a jump in the Diagram
# ##################################################################################
@pytest.fixture
def diagram(monkeypatch: pytest.MonkeyPatch):
    """What the Diagram recorded about the object: a placement, patterns to match, an anchor."""
    found = {"placement": (3, 4), "patterns": ["Wake Up"], "anchor": "anchor-11"}
    monkeypatch.setattr(guiwins_nav.mapjump, "diagram_placement", lambda target, state: found["placement"])
    monkeypatch.setattr(guiwins_nav.mapjump, "diagram_patterns", lambda target, state: found["patterns"])
    monkeypatch.setattr(guiwins_nav.mapjump, "diagram_anchor", lambda target: found["anchor"])
    monkeypatch.setattr(guiwins_nav.mapjump, "diagram_jump_js", lambda *args: "script:" + repr(args))
    return found


def test_a_diagram_holding_the_object_takes_the_jump(windows, diagram) -> None:
    view = _view("Diagram View")
    assert asyncio.run(guiwins_nav.jump_diagram_view(windows(view), _TASK)) is True
    assert view.scroll_area.client.scripts[0].startswith("script:")
    assert windows.raised == [view]


def test_an_object_the_diagram_never_drew_is_not_looked_for(windows, diagram) -> None:
    """An unnamed Task or a variable: answered at once rather than matched on something nearby."""
    diagram.update(placement=None, patterns=[], anchor="")
    view = _view("Diagram View")
    assert asyncio.run(guiwins_nav.jump_diagram_view(windows(view), _TASK)) is False
    assert view.scroll_area.client.scripts == []


def test_an_anchor_alone_is_enough_to_go_on(windows, diagram) -> None:
    diagram.update(placement=None, patterns=[])
    view = _view("Diagram View")
    assert asyncio.run(guiwins_nav.jump_diagram_view(windows(view), _TASK)) is True


def test_a_map_is_not_mistaken_for_a_diagram(windows, diagram) -> None:
    view = _view("Map View")
    assert asyncio.run(guiwins_nav.jump_diagram_view(windows(view), _TASK)) is False
    assert view.scroll_area.client.scripts == []


def test_a_diagram_that_does_not_hold_the_object_hands_over_to_the_next(windows, diagram) -> None:
    older, newer = _view("Diagram View"), _view("Diagram View", client=_Client(answer=False))
    assert asyncio.run(guiwins_nav.jump_diagram_view(windows(older, newer), _TASK)) is True


@pytest.mark.parametrize("failure", [TimeoutError(), RuntimeError("page gone"), AttributeError("no client")])
def test_a_diagram_page_that_goes_away_mid_jump_is_passed_over(windows, diagram, failure: Exception) -> None:
    view = _view("Diagram View", client=_Client(error=failure))
    assert asyncio.run(guiwins_nav.jump_diagram_view(windows(view), _TASK)) is False


# ##################################################################################
# A view whose rendering failed
# ##################################################################################
def test_a_rendering_failure_is_logged_not_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(guiwins_nav.logger, "exception", lambda message, **_kw: logged.append(message))

    async def fail() -> None:
        raise RuntimeError("could not draw")

    async def run() -> None:
        task = asyncio.create_task(fail())
        await asyncio.wait([task])
        guiwins_nav._report_view_failure(task)

    asyncio.run(run())
    assert logged


def test_a_cancelled_rendering_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    monkeypatch.setattr(guiwins_nav.logger, "exception", lambda message, **_kw: logged.append(message))

    async def run() -> None:
        task = asyncio.create_task(asyncio.sleep(10))
        task.cancel()
        await asyncio.wait([task])
        guiwins_nav._report_view_failure(task)

    asyncio.run(run())
    assert logged == []
