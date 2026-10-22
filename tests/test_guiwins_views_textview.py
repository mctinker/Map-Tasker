"""The Map, Diagram, Misc and Task Flow text view (guiwins_views.NiceGuiTextView), built on NiceGUI's user simulation.

The html it shows is made elsewhere and the helpers that prepare it are test_guiwins_views_text's.  This is the view itself:
the toolbar each kind of view gets, the progress banner that stands in until the last piece has arrived, the way the Map's
file is read and streamed in pieces (and what happens when there is no file), the jump a clicked finding asks for once the
content is there, the scope badge that says when a Diagram is out of date, and the small controls -- wrap, scroll, export, and
the Diagram's Profiles Per Line.  The browser's half is replaced by a record of the scripts it would have been sent.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core import mapjump
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.core.sysconst import DIAGRAM_FILE
from maptasker.src.gui import guiwins_views
from maptasker.src.gui.guiwins_views import NiceGuiTextView
from maptasker.src.mapgen import diagintr, mapexport
from nicegui import core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from tests.test_mapfind import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from nicegui.testing.user import User

_built: dict = {}


class _Response:
    """What ui.run_javascript hands back: awaitable like the real one, and fine to leave unawaited."""

    def __init__(self, answer: object) -> None:
        self.answer = answer

    def __await__(self) -> object:
        if isinstance(self.answer, Exception):
            raise self.answer
        yield from ()
        return self.answer


@pytest.fixture(autouse=True)
def _configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The configuration loaded, an output folder of its own, and the browser replaced by a record."""
    monkeypatch.chdir(tmp_path)
    _load(_FIXTURE_XML)
    PrimeItems.program_arguments.font = "Courier New"
    # PrimeItems outlives every test, so what these tests set is put back, and what other tests have left on it
    # (a Diagram model, say, from test_diagram_anchors) is cleared for them.
    for name, value in (
        ("view_limit_msg", ""),
        ("diagram_limit_msg", ""),
        ("diagram_connectors", {}),
        ("diagram_model", {}),
        ("taskflow_rows", []),
        ("colors_to_use", {"background_color": "White"}),
    ):
        monkeypatch.setattr(PrimeItems, name, value, raising=False)
    _built.clear()
    _built.update(view=None, gui=None, scripts=[], answer=True, rebuilt=[], profiles=[], cleared=[], tmp=tmp_path)

    def run_javascript(code: str, *_a: object, **_k: object) -> _Response:
        _built["scripts"].append(code)
        return _Response(_built["answer"])

    monkeypatch.setattr(ui, "run_javascript", run_javascript)


def _gui(**extra: object) -> SimpleNamespace:
    async def view_event(view_type: str) -> None:
        _built["rebuilt"].append(view_type)

    async def profiles_per_line_event(value: int) -> None:
        _built["profiles"].append(value)

    handlers = SimpleNamespace(
        clear_event=lambda: _built["cleared"].append(True),
        view_event=view_event,
        profiles_per_line_event=profiles_per_line_event,
    )
    return SimpleNamespace(
        state=PrimeItems,
        dark_mode=False,
        profiles_per_line=3,
        event_handlers=handlers,
        content_container=ui.column(),
        **extra,
    )


def _make(title: str, data: object, **kwargs: object) -> Callable[[], None]:
    def page() -> None:
        _built["gui"] = _gui()
        _built["view"] = NiceGuiTextView(_built["gui"], title, data, **kwargs)

    return page


@contextlib.asynccontextmanager
async def _open(page: Callable[[], None], *, settled: bool = True) -> AsyncIterator[User]:
    try:
        async with user_simulation(root=page) as user:
            await user.open("/")
            if settled:
                await _built["view"]._task
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _all(user: User, kind: type) -> list:
    return sorted((e for e in user.client.elements.values() if isinstance(e, kind)), key=lambda e: e.id)


def _button(user: User, text: str) -> ui.button:
    found = [e for e in _all(user, ui.button) if e.text == text]
    assert found, f"no button {text!r}"
    return found[0]


def _click(user: User, element: ui.element) -> None:
    UserInteraction(user, {element}, None).click()


def _texts(user: User) -> list[str]:
    return [e.text for e in _all(user, ui.label)]


def _write(name: str, text: str) -> None:
    (_built["tmp"] / name).write_text(text, encoding="utf-8")


# ##################################################################################
# The toolbar
# ##################################################################################
@pytest.mark.asyncio
async def test_a_map_gets_search_find_export_and_the_view_controls() -> None:
    async with _open(_make("Map View", {})) as user:
        buttons = {b.text for b in _all(user, ui.button)}
        assert {"Search", "Clear", "Find/Replace", "Export", "Top", "Bottom", "Toggle Wrap"} <= buttons
        assert "Map View" in _texts(user)


@pytest.mark.asyncio
async def test_the_map_shows_the_view_limit_message_when_it_was_cut_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "view_limit_msg", "Showing the first 1000 lines.")
    async with _open(_make("Map View", {})) as user:
        assert "Showing the first 1000 lines." in _texts(user)


@pytest.mark.asyncio
async def test_a_misc_view_has_no_find_or_export() -> None:
    async with _open(_make("Misc View", ["a", "b"])) as user:
        buttons = {b.text for b in _all(user, ui.button)}
        assert {"Search", "Top", "Bottom"} <= buttons
        assert not {"Find/Replace", "Export"} & buttons


@pytest.mark.asyncio
async def test_a_diagram_adds_profiles_per_line_its_own_tools_and_the_scope_badge() -> None:
    async with _open(_make("Diagram View", [], built_for="Project 'Home'")) as user:
        selects = {s.props.get("label"): s for s in _all(user, ui.select)}
        assert selects["Profiles Per Line"].value == "3"
        icons = {b.props.get("icon") for b in _all(user, ui.button)}
        assert {"zoom_in", "zoom_out", "unfold_less", "unfold_more", "restart_alt", "help_outline"} <= icons
        assert "Find/Replace" in {b.text for b in _all(user, ui.button)}
        assert "Drawn for Project 'Home'" in _texts(user)


@pytest.mark.asyncio
async def test_the_clear_button_is_the_windows_clear() -> None:
    async with _open(_make("Map View", {})) as user:
        _click(user, _button(user, "Clear"))
        assert _built["cleared"] == [True]


@pytest.mark.asyncio
async def test_the_view_is_the_windows_current_view_and_wraps_by_kind() -> None:
    async with _open(_make("Map View", {})):
        assert _built["gui"].textview is _built["view"]
        assert _built["view"].wrap_enabled is True
    async with _open(_make("Diagram View", [])):
        assert _built["view"].wrap_enabled is False, "a diagram is drawn on a grid and must not wrap"
    async with _open(_make("Task Flow", [])):
        assert _built["view"].wrap_enabled is False


@pytest.mark.asyncio
async def test_toggling_wrap_swaps_the_classes_and_says_which_way_it_went() -> None:
    async with _open(_make("Map View", {})) as user:
        view = _built["view"]
        assert "whitespace-pre-wrap" in view.scroll_area.classes
        _click(user, _button(user, "Toggle Wrap"))
        assert view.wrap_enabled is False
        assert "whitespace-pre" in view.scroll_area.classes and "whitespace-pre-wrap" not in view.scroll_area.classes
        assert user.notify.contains("Word wrap disabled for Map View.")
        _click(user, _button(user, "Toggle Wrap"))
        assert user.notify.contains("Word wrap enabled for Map View.")


@pytest.mark.asyncio
async def test_a_map_is_painted_in_the_background_colour_the_run_chose() -> None:
    async with _open(_make("Map View", {})):
        assert "background-color" in _built["view"].scroll_area._style


@pytest.mark.asyncio
async def test_a_popped_out_view_builds_into_the_container_it_was_given() -> None:
    def page() -> None:
        _built["gui"] = _gui()
        container = ui.column()
        _built["container"] = container
        _built["view"] = NiceGuiTextView(_built["gui"], "Misc View", ["x"], container=container)

    async with _open(page):
        assert _built["container"] in _built["view"].scroll_area.ancestors()
        assert "h-screen" in _built["container"].classes


# ##################################################################################
# Content that is not a file: Misc and Task Flow
# ##################################################################################
@pytest.mark.asyncio
async def test_a_misc_view_shows_its_lines_and_takes_the_progress_banner_down() -> None:
    async with _open(_make("Misc View", ["first", "second"])) as user:
        html = [e for e in _all(user, ui.html)]
        assert len(html) == 1 and "first\nsecond" in html[0].content
        assert _built["view"]._content_token == 1
        assert "Building the view.  Please stand by ..." not in _texts(user)


@pytest.mark.asyncio
async def test_a_misc_view_given_text_rather_than_lines_shows_it_as_it_is() -> None:
    async with _open(_make("Misc View", "just text")) as user:
        assert "just text" in _all(user, ui.html)[0].content


@pytest.mark.asyncio
async def test_a_task_flow_view_shows_the_report_built_from_its_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PrimeItems, "taskflow_rows", ["row"])
    monkeypatch.setattr(mapjump, "html_report", lambda rows: f"report of {rows}")
    async with _open(_make("Task Flow", [])) as user:
        assert "report of ['row']" in _all(user, ui.html)[0].content


@pytest.mark.asyncio
async def test_a_report_with_clickable_findings_has_them_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    wired = []
    monkeypatch.setattr(guiwins_views, "enable_finding_clicks", lambda view: wired.append(view))
    async with _open(_make("Misc View", [f'<span class="{mapjump.FINDING_CLASS}">x</span>'])):
        assert wired == [_built["view"]]


@pytest.mark.asyncio
async def test_a_report_with_no_findings_wires_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    wired = []
    monkeypatch.setattr(guiwins_views, "enable_finding_clicks", lambda view: wired.append(view))
    async with _open(_make("Misc View", ["plain"])):
        assert wired == []


@pytest.mark.asyncio
async def test_the_progress_banner_is_up_until_the_content_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = asyncio.Event()
    original = NiceGuiTextView.process_data

    async def held(self: NiceGuiTextView, data: object) -> None:
        await gate.wait()
        await original(self, data)

    monkeypatch.setattr(NiceGuiTextView, "process_data", held)
    async with _open(_make("Misc View", ["x"]), settled=False) as user:
        view = _built["view"]
        assert "Building the view.  Please stand by ..." in _texts(user)
        view._set_loading_text("Building the view ... 40%")
        assert "Building the view ... 40%" in _texts(user)
        gate.set()
        await view._task
        assert "Building the view ... 40%" not in _texts(user)
        view._hide_loading()  # safe with no banner
        view._set_loading_text("ignored")


@pytest.mark.asyncio
async def test_marking_the_content_ready_gives_it_a_fresh_token_and_forgets_the_remembered_search() -> None:
    async with _open(_make("Misc View", ["x"])):
        view = _built["view"]
        view._last_search = ("a", [], 0, False)
        before = view._content_token
        view._mark_content_ready()
        assert view._content_token == before + 1
        assert view._last_search is None


# ##################################################################################
# The Map's file
# ##################################################################################
_MAP_HTML = (
    '<span class="normtab"></span><!doctype html>\n'
    "<html><head><style>body { font-family: 'Courier Prime', monospace; }</style></head><body>\n"
    "<h2>MapTasker</h2>\n"
    + "".join(f"<div><span style='color:red'>Task {n}</span><br></div>\n" for n in range(40))
    + "</body></html>\n"
)


@pytest.mark.asyncio
async def test_the_maps_file_is_read_optimized_and_streamed_into_the_view() -> None:
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {})) as user:
        chunks = _all(user, ui.html)
        assert chunks, "the file's content is in the page"
        shown = "".join(chunk.content for chunk in chunks)
        assert "Task 39" in shown
        assert '<a id="the_top"></a><h5>MapTasker</h5>' in shown, "the heading is swapped for the view's"
        assert all(chunk._style.get("content-visibility") == "auto" for chunk in chunks)
        assert _built["view"]._content_token == 1


@pytest.mark.asyncio
async def test_the_view_takes_the_font_the_file_was_built_with() -> None:
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {})):
        assert "Courier Prime" in _built["view"].scroll_area._style["font-family"]


@pytest.mark.asyncio
async def test_a_file_that_names_no_font_leaves_the_runs_own() -> None:
    _write("MapTasker.html", "<div>no style here</div>")
    async with _open(_make("Map View", {})):
        assert "Courier New" in _built["view"].scroll_area._style["font-family"]


def test_the_first_font_named_in_a_text_is_found_and_stripped_of_quotes() -> None:
    finder = NiceGuiTextView.extract_first_font_name
    assert finder(None, "a { font-family : 'Fira Code', monospace; }") == "Fira Code"
    assert finder(None, 'font-family: "Menlo"; x') == "Menlo"
    assert finder(None, "nothing") == "Font name not found"


@pytest.mark.asyncio
async def test_a_large_map_is_streamed_in_several_pieces(monkeypatch: pytest.MonkeyPatch) -> None:
    original = guiwins_views.split_for_streaming
    monkeypatch.setattr(guiwins_views, "split_for_streaming", lambda html: original(html, budget=600))
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {})) as user:
        pieces = _all(user, ui.html)
        assert len(pieces) > 2
        shown = "".join(re.sub(r"<[^>]+>", "", piece.content) for piece in pieces)
        assert all(f"Task {n}" in shown for n in range(40)), "every line arrives, in however many pieces"


@pytest.mark.asyncio
async def test_once_the_map_is_in_place_its_own_links_are_made_to_land_on_what_they_name() -> None:
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {})):
        assert any("mtLinksWired" in script for script in _built["scripts"])


@pytest.mark.asyncio
async def test_a_browser_that_will_not_take_the_link_script_does_not_stop_the_view() -> None:
    _built["answer"] = TimeoutError()
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {})):
        assert _built["view"]._content_token == 1


# ----- the file is missing ---------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_with_no_file_the_map_is_shown_from_the_lines_held_in_memory() -> None:
    data = {0: {"text": ["Project: ", "Home"], "color": ["red", "blue"]}, 1: {"text": ["a < b"], "color": []}}
    async with _open(_make("Map View", data)) as user:
        shown = "".join(chunk.content for chunk in _all(user, ui.html))
        assert "<span style='color: red;'>Project: </span>" in shown
        assert "a &lt; b" in shown
        assert _built["view"]._content_token == 1, "and the view finishes rather than hanging on its banner"
        assert "Building the view.  Please stand by ..." not in _texts(user)


@pytest.mark.asyncio
async def test_with_no_file_a_list_view_is_shown_a_line_at_a_time() -> None:
    async with _open(_make("Diagram View", ["one", "", "two"])) as user:
        shown = "".join(chunk.content for chunk in _all(user, ui.html))
        assert "<div>one</div>" in shown and "<div>two</div>" in shown


# ##################################################################################
# The Diagram's file
# ##################################################################################
_DIAGRAM_LINES = "\n".join(f"line {n} of the diagram" for n in range(400))


@pytest.mark.asyncio
async def test_a_diagram_is_wrapped_a_hundred_and_fifty_lines_to_the_piece() -> None:
    _write(DIAGRAM_FILE, _DIAGRAM_LINES)
    async with _open(_make("Diagram View", [])) as user:
        chunks = _all(user, ui.html)
        assert [chunk.props.get("data-lines") for chunk in chunks] == ["150", "150", "100"]
        assert '<span class="mt-dline" data-line="0"' in chunks[0].content or diagintr.LINE_CLASS in chunks[0].content
        assert "Click on connector to highlight" not in _texts(user), "no connectors, nothing to click"


@pytest.mark.asyncio
async def test_the_header_line_the_diagram_file_starts_with_is_not_drawn() -> None:
    _write(DIAGRAM_FILE, '<span class="normtab"></span><!doctype html>\nreal line one\nreal line two')
    async with _open(_make("Diagram View", [])) as user:
        (chunk,) = _all(user, ui.html)
        assert chunk.props.get("data-lines") == "2"
        assert "doctype" not in chunk.content and "real line one" in chunk.content


@pytest.mark.asyncio
async def test_a_diagram_with_connectors_wires_their_highlighting_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    _write(DIAGRAM_FILE, _DIAGRAM_LINES)
    monkeypatch.setattr(PrimeItems, "diagram_connectors", {1: [(2, 0, 3)]})
    async with _open(_make("Diagram View", [])) as user:
        assert "Click on connector to highlight" in _texts(user)
        assert any("connector-highlight" in script for script in _built["scripts"])


@pytest.mark.asyncio
async def test_a_diagram_with_names_to_click_wires_the_interaction_and_says_how_to_use_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = {"nodes": [{"col": 0, "len": 4, "anchor": "a", "index": 0, "kind": "task"}], "folds": {}}
    monkeypatch.setattr(diagintr, "model", lambda state: model)
    monkeypatch.setattr(diagintr, "nodes_by_line", lambda m: {2: m["nodes"]})
    monkeypatch.setattr(diagintr, "folds_by_line", lambda m: {})
    monkeypatch.setattr(diagintr, "interaction_js", lambda *args: "INTERACTION_JS")
    registered = []
    monkeypatch.setattr(guiwins_views, "register_finding_clicks", lambda gui: registered.append(gui))
    _write(DIAGRAM_FILE, _DIAGRAM_LINES)
    async with _open(_make("Diagram View", [])) as user:
        assert "INTERACTION_JS" in _built["scripts"]
        assert registered == [_built["gui"]]
        assert any(text.startswith("Click a name for its Map entry") for text in _texts(user))


@pytest.mark.asyncio
async def test_the_limit_message_replaces_the_hint_when_the_diagram_was_cut_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(DIAGRAM_FILE, _DIAGRAM_LINES)
    monkeypatch.setattr(PrimeItems, "diagram_limit_msg", "Only 100 Profiles drawn.")
    async with _open(_make("Diagram View", [])) as user:
        assert "Only 100 Profiles drawn." in _texts(user)


@pytest.mark.asyncio
async def test_the_diagram_toolbar_buttons_send_their_commands_to_this_views_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = []
    monkeypatch.setattr(diagintr, "command_js", lambda root, name, argument: sent.append((name, argument)) or "CMD")
    async with _open(_make("Diagram View", [])) as user:
        for icon in ("zoom_in", "zoom_out", "unfold_less", "unfold_more", "restart_alt"):
            _click(user, next(b for b in _all(user, ui.button) if b.props.get("icon") == icon))
        assert sent == [
            ("zoom", 1.15),
            ("zoom", 1 / 1.15),
            ("collapse-all", None),
            ("expand-all", None),
            ("reset", None),
        ]


@pytest.mark.asyncio
async def test_reloading_the_diagram_starts_the_progress_over_and_streams_it_again() -> None:
    _write(DIAGRAM_FILE, _DIAGRAM_LINES)
    async with _open(_make("Diagram View", [])) as user:
        view = _built["view"]
        first_token = view._content_token
        view._last_search = ("x", [], 0, False)
        view.reload_diagram()
        assert view._content_token == 0 and view._last_search is None
        assert "Building the view.  Please stand by ..." in _texts(user)
        await view._task
        assert view._content_token == first_token + 1
        assert len(_all(user, ui.html)) == 3


# ##################################################################################
# The Diagram's controls
# ##################################################################################
@pytest.mark.asyncio
async def test_changing_profiles_per_line_asks_the_window_to_rebuild_for_the_new_value_only_when_it_differs() -> None:
    async with _open(_make("Diagram View", [])):
        view = _built["view"]
        view._profiles_per_line_selected(SimpleNamespace(value="3"))
        view._profiles_per_line_selected(SimpleNamespace(value="5"))
        view._profiles_per_line_selected(7)
        await asyncio.sleep(0.05)
        assert _built["profiles"] == [5, 7]


# ----- the scope badge ------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_diagram_drawn_for_what_is_still_selected_has_no_stale_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapjump, "current_scope", lambda state: SimpleNamespace(phrase="Project 'Home'"))
    async with _open(_make("Diagram View", [], built_for="Project 'Home'")):
        view = _built["view"]
        assert view.scope_stale_label.visible is False and view.scope_rebuild_button.visible is False


@pytest.mark.asyncio
async def test_a_diagram_whose_selection_has_moved_on_says_so_and_offers_a_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phrase = {"now": "Project 'Home'"}
    monkeypatch.setattr(mapjump, "current_scope", lambda state: SimpleNamespace(phrase=phrase["now"]))
    async with _open(_make("Diagram View", [], built_for="Project 'Home'")) as user:
        view = _built["view"]
        phrase["now"] = "Task 'Wake Up'"
        guiwins_views.refresh_scope_badges(_built["gui"])
        assert view.scope_stale_label.text == "-- now showing Task 'Wake Up'"
        assert view.scope_stale_label.visible and view.scope_rebuild_button.visible

        _click(user, view.scope_rebuild_button)
        await asyncio.sleep(0.05)
        assert _built["rebuilt"] == ["diagram"]


@pytest.mark.asyncio
async def test_rebuild_without_a_window_to_ask_says_to_press_the_button() -> None:
    async with _open(_make("Diagram View", [], built_for="Project 'Away'")) as user:
        view = _built["view"]
        _built["gui"].event_handlers = None
        _click(user, view.scope_rebuild_button)
        await asyncio.sleep(0.05)
        assert user.notify.contains("Press Diagram View to rebuild it.")


@pytest.mark.asyncio
async def test_a_view_that_died_or_has_no_badge_is_skipped_when_the_badges_are_refreshed() -> None:
    async with _open(_make("Map View", {})):
        gui = _built["gui"]

        class Broken:
            scroll_area = _built["view"].scroll_area

            def refresh_scope_badge(self) -> None:
                raise RuntimeError("page went away")

        gui.textviews = [Broken(), _built["view"]]
        guiwins_views.refresh_scope_badges(gui)  # must not raise
        _built["view"].refresh_scope_badge()  # a Map has no badge: nothing to do


# ##################################################################################
# Landing on a clicked finding
# ##################################################################################
@pytest.mark.asyncio
async def test_a_view_built_for_a_clicked_finding_scrolls_to_it_once_the_content_is_there() -> None:
    target = mapjump.Target(kind=mapjump.TASK, key="20", name="Fetcher")
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {}, jump_to=target.token())):
        assert any(target.anchor in script for script in _built["scripts"])
        assert _built["view"].jump_to == "", "one click, delivered once"


@pytest.mark.asyncio
async def test_a_finding_the_map_has_no_line_for_is_said_not_guessed() -> None:
    target = mapjump.Target(kind=mapjump.TASK, key="20", name="Fetcher")
    _built["answer"] = False
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {}, jump_to=target.token())) as user:
        assert user.notify.contains("Built the Map, but it has no line for")


@pytest.mark.asyncio
async def test_a_token_that_is_not_one_delivers_nothing() -> None:
    _write("MapTasker.html", _MAP_HTML)
    async with _open(_make("Map View", {}, jump_to="not-a-token")):
        assert not any("scrollIntoView" in script and "Fetcher" in script for script in _built["scripts"])


# ##################################################################################
# Scrolling, and exporting
# ##################################################################################
@pytest.mark.asyncio
async def test_top_goes_to_the_start_of_both_axes_and_bottom_asks_the_browser_to_go_past_the_end() -> None:
    async with _open(_make("Misc View", ["x"])) as user:
        view = _built["view"]
        scrolls = []
        view.scroll_area.scroll_to = lambda **kwargs: scrolls.append(kwargs)
        _click(user, _button(user, "Top"))
        assert scrolls == [{"percent": 0.0, "axis": "horizontal"}, {"percent": 0.0}]
        scrolls.clear()
        _click(user, _button(user, "Bottom"))
        assert scrolls == [{"percent": 0.0, "axis": "horizontal"}]
        assert any("scrollTop = scroller.scrollHeight" in script for script in _built["scripts"])


@pytest.mark.asyncio
async def test_export_runs_off_the_event_loop_and_says_where_the_file_went(monkeypatch: pytest.MonkeyPatch) -> None:
    called = []

    async def io_bound(function: Callable, *args: object, **kwargs: object) -> str:
        called.append((function, args, kwargs))
        return "/out/Map.md"

    monkeypatch.setattr(guiwins_views.run, "io_bound", io_bound)
    async with _open(_make("Map View", {})) as user:
        with user.client:
            await _built["view"].export_event(mapexport.MAP, "md")
        assert called[0][1] == (mapexport.MAP, "md")
        assert user.notify.contains("Exported to /out/Map.md")


@pytest.mark.asyncio
async def test_an_export_that_cannot_be_made_or_saved_is_reported_and_one_that_returns_nothing_is_quiet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome: dict = {"value": mapexport.ExportError("There is no Map to export.")}

    async def io_bound(function: Callable, *args: object, **kwargs: object) -> object:
        if isinstance(outcome["value"], Exception):
            raise outcome["value"]
        return outcome["value"]

    monkeypatch.setattr(guiwins_views.run, "io_bound", io_bound)
    async with _open(_make("Map View", {})) as user:
        with user.client:
            await _built["view"].export_event(mapexport.MAP, "pdf")
            assert user.notify.contains("There is no Map to export.")
            outcome["value"] = OSError("disk full")
            await _built["view"].export_event(mapexport.MAP, "pdf")
            assert user.notify.contains("The export could not be saved: disk full")
            outcome["value"] = None
            await _built["view"].export_event(mapexport.MAP, "pdf")  # the user cancelled: nothing to say
