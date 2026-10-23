"""Drawing a Legacy Scene: every element type the preview knows, in both orientations, and the overlays on top.

Where an element lands is its own <geom>; what it looks like is the arguments Tasker stored.  Here every type is drawn
in a simulated page with the arguments a freshly made one has, so a drawer that cannot cope with its own element
fails here rather than in a user's Scene -- and the things drawn over the canvas (the selection outline and its
handles, an element with no layout in the other orientation, a background that is a variable) are checked for the
cases that show them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest
from maptasker.src.core.primitem import RunState
from maptasker.src.gui import sceneview_legacy
from maptasker.src.gui.sceneview import CanvasEditing, PreviewOptions
from nicegui import ui

from tests.nicegui_harness import all_elements, open_page

if TYPE_CHECKING:
    from collections.abc import Callable

    from nicegui.testing.user import User


def _scene(*elements: str, extra: str = "") -> ET.Element:
    return ET.fromstring(
        f"<Scene sr='scene'><nme>Panel</nme><widthPort>600</widthPort><heightPort>800</heightPort>"
        f"<widthLand>800</widthLand><heightLand>600</heightLand>{extra}{''.join(elements)}</Scene>"
    )


def _element(kind: str, sr: str = "elements0", geom: str = "10,20,200,80,15,25,300,90", args: str = "") -> str:
    return f"<{kind} sr='{sr}'><geom>{geom}</geom><Str sr='arg0'>{kind}</Str>{args}</{kind}>"


def _draw(
    scene: ET.Element, options: PreviewOptions | None = None, editing: CanvasEditing | None = None
) -> Callable[[], None]:
    def page() -> None:
        sceneview_legacy.draw_scene(scene, 600, 800, options or PreviewOptions(), editing, state=RunState())

    return page


def _canvas(user: User) -> ui.element:
    (canvas,) = [e for e in all_elements(user) if "mt-scene-canvas" in e._classes]
    return canvas


def _children(user: User) -> list[ui.element]:
    canvas = _canvas(user)
    return [e for e in all_elements(user) if e.parent_slot is not None and e.parent_slot.parent is canvas]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", sorted(sceneview_legacy._DRAWERS))
@pytest.mark.parametrize("landscape", [False, True])
async def test_every_element_type_draws_a_frame_in_either_orientation(kind: str, landscape: bool) -> None:
    scene = _scene(_element(kind))

    async with open_page(_draw(scene, PreviewOptions(landscape=landscape))) as user:
        assert len(_children(user)) >= 1, f"{kind} left nothing on the canvas"


@pytest.mark.asyncio
async def test_the_canvas_is_the_size_asked_for_and_carries_no_editing_hooks_when_previewing() -> None:
    async with open_page(_draw(_scene(_element("TextElement")))) as user:
        canvas = _canvas(user)
        assert canvas._style["width"] == "600px" and canvas._style["height"] == "800px"
        assert "tabindex" not in str(canvas._props)


@pytest.mark.asyncio
async def test_a_variable_background_is_hatched_not_guessed() -> None:
    scene = _scene(
        _element("RectElement"), extra="<PropertiesElement sr='props'><Str sr='arg2'>%Accent</Str></PropertiesElement>"
    )

    async with open_page(_draw(scene)) as user:
        assert "repeating-linear-gradient" in _canvas(user)._style["background"]


@pytest.mark.asyncio
async def test_editing_publishes_the_selection_and_outlines_each_selected_element_with_handles() -> None:
    scene = _scene(
        _element("TextElement", "elements0"), _element("ButtonElement", "elements1", "300,300,100,50,0,0,10,10")
    )
    editing = CanvasEditing(selected=("elements1",))

    async with open_page(_draw(scene, editing=editing)) as user:
        canvas = _canvas(user)
        assert canvas._props["data-selected"] == "elements1" and canvas._props["tabindex"] == "0"
        handles = [e for e in all_elements(user) if "cursor" in str(getattr(e, "_style", {}))]
        assert len(handles) >= 8, "a single selected element gets all eight resize handles"


@pytest.mark.asyncio
async def test_several_selected_elements_get_outlines_but_no_handles() -> None:
    scene = _scene(
        _element("TextElement", "elements0"), _element("ButtonElement", "elements1", "300,300,100,50,0,0,10,10")
    )
    editing = CanvasEditing(selected=("elements0", "elements1"))

    async with open_page(_draw(scene, editing=editing)) as user:
        assert _canvas(user)._props["data-selected"] == "elements0 elements1"
        handles = [e for e in all_elements(user) if "nwse-resize" in str(getattr(e, "_style", {}))]
        assert handles == [], "a group is dragged, not resized"


@pytest.mark.asyncio
async def test_an_element_with_no_layout_in_this_orientation_is_not_drawn_and_not_outlined() -> None:
    portrait_only = (
        "<TextElement sr='elements0'><geom>10,20,200,80,-1,-1,-1,-1</geom><Str sr='arg0'>x</Str></TextElement>"
    )
    editing = CanvasEditing(selected=("elements0",))

    async with open_page(_draw(_scene(portrait_only), PreviewOptions(landscape=True), editing)) as user:
        assert _children(user) == []


def test_the_unknown_element_kinds_are_left_to_a_placeholder_by_the_dispatcher() -> None:
    assert "TextElement" in sceneview_legacy._DRAWERS and "HologramElement" not in sceneview_legacy._DRAWERS


# ##################################################################################
# What the arguments change
# ##################################################################################
def _texts(user: User) -> list[str]:
    return [str(getattr(e, "text", "") or "") for e in all_elements(user)]


def _icons(user: User) -> list[str]:
    return [str(e._props.get("name", "")) for e in all_elements(user) if isinstance(e, ui.icon)]


def _args(**by_number: str) -> str:
    return "".join(
        f"<Int sr='arg{n}' val='{value}'/>" if value.lstrip("-").isdigit() else f"<Str sr='arg{n}'>{value}</Str>"
        for n, value in sorted((int(k[3:]), v) for k, v in by_number.items())
    )


@pytest.mark.asyncio
async def test_a_plain_text_element_shows_its_text() -> None:
    scene = _scene(_element("TextElement", args=_args(arg1="Good morning")))

    async with open_page(_draw(scene)) as user:
        assert "Good morning" in _texts(user)


@pytest.mark.asyncio
async def test_text_that_is_a_variable_is_marked_as_one_not_resolved() -> None:
    scene = _scene(_element("TextElement", args=_args(arg1="%title")))

    async with open_page(_draw(scene)) as user:
        (label,) = [e for e in all_elements(user) if isinstance(e, ui.label) and e.text == "%title"]
        assert label._style["font-style"] == "italic"


@pytest.mark.asyncio
async def test_html_text_is_drawn_in_a_sandboxed_frame_with_a_badge_rather_than_as_source() -> None:
    scene = _scene(_element("TextElement", args=_args(arg1="&lt;b&gt;bold&lt;/b&gt; words", arg8="2")))

    async with open_page(_draw(scene)) as user:
        (frame,) = [e for e in all_elements(user) if e.tag == "iframe"]
        assert "sandbox" in frame._props and "bold" in frame._props["srcdoc"]
        assert "Content-Security-Policy" in frame._props["srcdoc"]
        assert "HTML" in _texts(user)


@pytest.mark.asyncio
async def test_html_text_with_no_markup_in_it_keeps_the_plain_label_with_stray_tags_stripped() -> None:
    scene = _scene(_element("TextElement", args=_args(arg1="just words", arg8="2")))

    async with open_page(_draw(scene)) as user:
        assert "just words" in _texts(user)
        assert not [e for e in all_elements(user) if e.tag == "iframe"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "checked", "icon"),
    [
        ("CheckBoxElement", "1", "check_box"),
        ("CheckBoxElement", "0", "check_box_outline_blank"),
        ("SwitchElement", "1", "toggle_on"),
        ("SwitchElement", "0", "toggle_off"),
    ],
)
async def test_a_checkbox_or_switch_shows_the_state_it_opens_in(kind: str, checked: str, icon: str) -> None:
    scene = _scene(_element(kind, args=_args(arg1=checked)))

    async with open_page(_draw(scene)) as user:
        assert icon in _icons(user)


@pytest.mark.asyncio
@pytest.mark.parametrize("orientation", ["0", "1"])
async def test_a_slider_puts_its_thumb_where_its_default_falls_and_says_the_range(orientation: str) -> None:
    scene = _scene(_element("SliderElement", args=_args(arg1=orientation, arg2="0", arg3="100", arg4="25")))

    async with open_page(_draw(scene)) as user:
        assert "0 \u2013 100  (25)" in _texts(user)
        thumbs = [e for e in all_elements(user) if "calc(25.0% - 7px)" in str(getattr(e, "_style", {}))]
        assert thumbs


@pytest.mark.asyncio
async def test_a_slider_too_short_for_its_caption_leaves_it_out() -> None:
    scene = _scene(_element("SliderElement", geom="0,0,200,20,0,0,200,20", args=_args(arg2="0", arg3="10", arg4="5")))

    async with open_page(_draw(scene)) as user:
        assert not any("\u2013" in text for text in _texts(user))


@pytest.mark.asyncio
async def test_a_web_element_in_direct_mode_draws_its_own_page_and_in_url_mode_only_reports_it() -> None:
    page = _scene(
        _element("WebElement", args=_args(arg1="2", arg2="&lt;html&gt;&lt;body&gt;hi&lt;/body&gt;&lt;/html&gt;"))
    )
    async with open_page(_draw(page)) as user:
        assert [e for e in all_elements(user) if e.tag == "iframe"]
        assert "HTML" in _texts(user)

    url = _scene(_element("WebElement", args=_args(arg1="0", arg2="https://example.com/\nsecond line")))
    async with open_page(_draw(url)) as user:
        assert not [e for e in all_elements(user) if e.tag == "iframe"]
        assert "https://example.com/" in _texts(user)


@pytest.mark.asyncio
async def test_a_picker_shows_its_default_and_chevrons_only_when_there_is_room() -> None:
    tall = _scene(_element("PickerElement", geom="0,0,100,100,0,0,100,100", args=_args(arg1="0", arg2="9", arg3="4")))
    async with open_page(_draw(tall)) as user:
        assert "4" in _texts(user) and {"expand_less", "expand_more"} <= set(_icons(user))

    short = _scene(_element("PickerElement", geom="0,0,100,40,0,0,100,40", args=_args(arg3="4")))
    async with open_page(_draw(short)) as user:
        assert "expand_less" not in _icons(user)


@pytest.mark.asyncio
async def test_a_list_with_no_row_template_is_a_labelled_box() -> None:
    scene = _scene(_element("ListElement", args=_args(arg1="0")))

    async with open_page(_draw(scene)) as user:
        assert any(text.startswith("List: ") for text in _texts(user))


@pytest.mark.asyncio
async def test_a_spinner_row_template_is_drawn_once_on_its_own_little_canvas() -> None:
    template = (
        "<Scene sr='arg3'><Scene sr='val'><widthPort>100</widthPort><heightPort>30</heightPort>"
        "<TextElement sr='elements0'><geom>0,0,100,30,0,0,100,30</geom><Str sr='arg0'>row</Str>"
        "<Str sr='arg1'>one row</Str></TextElement></Scene></Scene>"
    )
    scene = _scene(_element("SpinnerElement", args=_args(arg1="0") + template))

    async with open_page(_draw(scene)) as user:
        assert "one row" in _texts(user)
