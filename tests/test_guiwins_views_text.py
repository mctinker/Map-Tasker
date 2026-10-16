"""The text views' own logic (guiwins_views): preparing the Map for the browser, wrapping the Diagram, the fallback renderers.

None of this needs a browser.  What the Map's html becomes on its way into the view, how a twenty-megabyte Map is cut into pieces
that render as one, how a Diagram line is wrapped around its connectors and names, and how the fallback view turns the Map's
in-memory lines into safe html are all functions of a string.  They are also where a mistake does the most damage and shows the
least: a stray newline is a blank line in a view of fifty thousand, a cut in the wrong place leaves a colour open down the rest of
the page, and an unescaped < in a Task's name is a hole in the page.  So what is asserted is the output, character for character
where that is the point, and the properties that must hold for any input where it is not.
"""

from __future__ import annotations

import inspect
import re
from types import SimpleNamespace

import pytest

from maptasker.src.gui import guiwins_views
from maptasker.src.mapgen import diagintr
from maptasker.src.gui.guiwins_views import (
    HTML_OPTIMIZE_PATTERN,
    _compress_blank_lines,
    _connectors_by_line,
    _diagram_spans,
    _escape_html_text,
    _escape_text_except_html,
    _fallback_lines_html,
    _fallback_map_html,
    _is_css_line,
    _StyleCollector,
    _wrap_diagram_line,
    optimize_html,
    scope_badge_text,
    split_for_streaming,
    view_theme_colors,
)


def _optimized(html: str) -> str:
    return HTML_OPTIMIZE_PATTERN.sub(optimize_html, html)


# ##################################################################################
# Preparing the Map's html
# ##################################################################################
def test_a_newline_touching_a_tag_is_the_files_formatting_and_goes() -> None:
    assert _optimized("<div>one</div>\n<div>two</div>\n") == "<div>one</div><div>two</div>"
    assert _optimized("<br>\n<span>x</span>") == "<br><span>x</span>"
    assert _optimized("<b>text</b>  \r\n<i>next</i>") == "<b>text</b><i>next</i>"
    # Only the newline goes: spaces that follow it are the Map's own indentation.
    assert _optimized("<b>text</b>\r\n  <i>next</i>") == "<b>text</b>  <i>next</i>"


def test_a_newline_with_text_on_both_sides_is_the_authors_and_stays_as_one_line_break() -> None:
    assert _optimized("first line\nsecond line") == "first line\nsecond line"
    assert _optimized("first\n\n\nsecond") == "first\nsecond", "a run of written newlines is the one break they asked for"


def test_the_two_headings_are_swapped_for_the_smaller_ones_the_view_uses() -> None:
    assert _optimized("<h2>MapTasker</h2>") == '<a id="the_top"></a><h5>MapTasker</h5>'
    directory = '<h2><span class="normtab"></span>Directory</h2>'
    assert _optimized(directory) == '<h6><span class="normtab"></span>Directory</h6>'
    assert _optimized("<h2>Something else</h2>") == "<h2>Something else</h2>"


# ##################################################################################
# Cutting the Map into pieces
# ##################################################################################
def _text(html: str) -> str:
    """What a browser would show of this html: its text with the tags taken out."""
    return re.sub(r"<[^>]+>", "", html)


def _balanced(piece: str) -> bool:
    """Every element a piece opens, it closes (void elements and the frame aside)."""
    stack: list[str] = []
    for closing, name, self_closing in guiwins_views.HTML_ELEMENT.findall(piece):
        name = name.lower()
        if name in guiwins_views.VOID_ELEMENTS or name in guiwins_views.FRAME_ELEMENTS or self_closing:
            continue
        if closing:
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        else:
            if stack and stack[-1] == "p" and name in guiwins_views.CLOSE_AN_OPEN_PARAGRAPH:
                stack.pop()  # a browser closes an open paragraph when a block starts
            stack.append(name)
    return not stack


def test_a_map_smaller_than_the_budget_is_one_piece_untouched() -> None:
    html = "<div><span style='color:red'>a</span></div>"
    assert split_for_streaming(html, budget=10_000) == [html]
    assert split_for_streaming("") == []


def test_cutting_keeps_every_piece_balanced_and_every_character_of_text_in_order() -> None:
    html = "".join(
        f"<div class='row'><span style='color: red;'>line {n} </span><b>bold {n}</b><br></div>" for n in range(400)
    )
    pieces = split_for_streaming(html, budget=2_000)

    assert len(pieces) > 5
    assert all(_balanced(piece) for piece in pieces)
    assert "".join(_text(piece) for piece in pieces) == _text(html), "they render as it, which is what must hold"


def test_a_colour_opened_on_one_line_and_closed_several_later_is_restated_across_a_cut() -> None:
    html = "<span style='color: red;'>" + "".join(f"<div>row {n}</div>" for n in range(200)) + "</span><p>after</p>"
    pieces = split_for_streaming(html, budget=500)
    assert len(pieces) > 2
    assert all(_balanced(piece) for piece in pieces)
    assert all(piece.startswith("<span style='color: red;'>") or n == 0 for n, piece in enumerate(pieces[:-1]))
    assert pieces[1].startswith("<span style='color: red;'>"), "the next piece opens what the cut closed"


def test_an_id_stays_with_the_element_it_opened_on_and_is_dropped_where_that_element_is_restated() -> None:
    html = '<div id="anchor_1">' + "".join(f"<p>paragraph {n}</p>" for n in range(300)) + "</div>"
    pieces = split_for_streaming(html, budget=600)
    joined = "".join(pieces)
    assert joined.count('id="anchor_1"') == 1, "an anchor names one place in the document"
    assert len(pieces) > 2


def test_an_open_paragraph_is_closed_by_the_block_that_follows_it_as_a_browser_would() -> None:
    """A TaskerNet description writes <p> and leaves it to the next block: it must not be re-stated at every cut."""
    html = "<p>a TaskerNet description" + "<div>block</div>" * 200 + "<p>next</p>"
    pieces = split_for_streaming(html, budget=300)
    assert len(pieces) > 2
    assert all(_balanced(piece) for piece in pieces)
    assert all("<p>" not in piece for piece in pieces[1:-1]), "the paragraph was closed by the first block"


def test_void_elements_and_self_closing_tags_are_never_left_open() -> None:
    html = "<div>" + "<br><img src='x.png'><hr/>" * 300 + "</div>"
    assert all(_balanced(piece) for piece in split_for_streaming(html, budget=400))


def test_the_pages_own_frame_is_not_restated() -> None:
    html = "<html><head><style>x{}</style></head><body>" + "<div>row</div>" * 500 + "</body></html>"
    pieces = split_for_streaming(html, budget=500)
    assert all(not piece.startswith("<body") for piece in pieces[1:])


# ##################################################################################
# The Diagram's lines
# ##################################################################################
def test_text_is_escaped_for_html_with_the_ampersand_first() -> None:
    assert _escape_html_text("a < b && c > d") == "a &lt; b &amp;&amp; c &gt; d"
    assert _escape_html_text("&lt;") == "&amp;lt;", "already-escaped text is escaped again, not trusted"


def test_connectors_are_inverted_from_by_id_to_by_line() -> None:
    state = SimpleNamespace(diagram_connectors={7: [(3, 0, 5), (4, 0, 5)], 9: [(3, 6, 9)]})
    assert _connectors_by_line(state) == {3: [(0, 5, 7), (6, 9, 9)], 4: [(0, 5, 7)]}
    assert _connectors_by_line(SimpleNamespace()) == {}


_NODE = {"col": 3, "len": 6, "anchor": "task_1", "index": 4, "kind": "task"}


def test_a_name_is_wrapped_in_a_clickable_node_span() -> None:
    spans = _diagram_spans(0, "└─ Backup", {}, {0: [_NODE]})
    assert [(start, end) for start, end, _ in spans] == [(3, 9)]
    opening = spans[0][2]
    assert f'class="{diagintr.NODE_CLASS}"' in opening
    assert 'data-anchor="task_1"' in opening and 'data-node="4"' in opening and 'data-kind="task"' in opening


def test_a_connector_that_runs_into_a_name_is_clipped_so_the_name_keeps_its_click_target() -> None:
    line = "└─ Backup"
    spans = _diagram_spans(0, line, {0: [(0, 6, 11)]}, {0: [_NODE]})
    covered = sorted((start, end) for start, end, _ in spans)
    assert covered == [(0, 3), (3, 9)], "the connector gives up the characters the name needs"
    assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(covered, covered[1:], strict=False))


def test_a_connector_split_by_a_name_in_its_middle_keeps_both_halves() -> None:
    line = "─── Name ───"
    node = {"col": 4, "len": 4, "anchor": "a", "index": 0, "kind": "profile"}
    spans = _diagram_spans(0, line, {0: [(0, len(line), 1)]}, {0: [node]})
    assert sorted((start, end) for start, end, _ in spans) == [(0, 4), (4, 8), (8, len(line))]


def test_a_node_that_starts_beyond_the_end_of_the_line_is_ignored() -> None:
    assert _diagram_spans(0, "short", {}, {0: [{"col": 40, "len": 3, "anchor": "a", "index": 0, "kind": "t"}]}) == []


def test_a_line_is_one_element_with_the_text_between_its_spans_escaped() -> None:
    node = {"col": 0, "len": 1, "anchor": "t1", "index": 1, "kind": "task"}
    html = _wrap_diagram_line(5, "x <b> y", {}, {5: [node]}, {})
    assert html.startswith(f'<span class="{diagintr.LINE_CLASS}" data-line="5">')
    assert " &lt;b&gt; y" in html, "text outside the spans is escaped"
    assert '<span class="mt-dnl">\n</span></span>' in html, "the newline stays in the text for the search index, hidden"


def test_a_blank_line_carries_a_zero_width_space_so_it_keeps_its_height() -> None:
    html = _wrap_diagram_line(1, "", {}, {}, {})
    assert "&#8203;" in html


def test_a_line_that_opens_a_fold_says_so() -> None:
    html = _wrap_diagram_line(2, "Project", {}, {}, {2: "proj_1"})
    assert 'data-fold="proj_1" data-fold-state="open"' in html
    assert "data-fold" not in _wrap_diagram_line(3, "Project", {}, {}, {2: "proj_1"})


def test_connector_runs_become_spans_carrying_their_id() -> None:
    html = _wrap_diagram_line(0, "│  │", {0: [(0, 1, 42), (3, 4, 43)]}, {}, {})
    assert 'data-connector-id="42"' in html and 'data-connector-id="43"' in html
    assert html.count('class="connector"') == 2


# ##################################################################################
# The fallback renderers
# ##################################################################################
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (".rule { color: red; }", True),
        ("#id { x: y; }", True),
        ("}", True),
        ("color: red;", True),
        ("a: b; /* trailing */", True),
        ("/* a comment */", False),
        ("A plain line of the Map", False),
        ("Time: 8:00 AM", False),
        ("", False),
    ],
)
def test_a_stray_line_is_recognised_as_css_by_its_shape(text: str, expected: bool) -> None:
    assert _is_css_line(text) is expected


def test_only_the_tags_the_map_uses_survive_escaping_and_the_rest_are_shown_as_text() -> None:
    assert _escape_text_except_html("a <b>bold</b> <table><tr><td>x</td></tr></table>") == (
        "a <b>bold</b> <table><tr><td>x</td></tr></table>"
    )
    assert _escape_text_except_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert _escape_text_except_html("if a < b and b > c") == "if a &lt; b and b &gt; c"
    assert _escape_text_except_html("<iframe src='x'>") == "&lt;iframe src='x'&gt;"
    assert _escape_text_except_html("<A HREF='#x'>link</A>") == "<A HREF='#x'>link</A>", "tag names are matched without case"


def test_a_style_block_arriving_a_line_at_a_time_becomes_one_style_element() -> None:
    built: list[str] = []
    collector = _StyleCollector(built)
    assert collector.consume("<style>") is True
    assert collector.consume(".a { color: red; }") is True
    assert built == [], "not finished until the line that closes it"
    assert collector.consume("</style>") is True
    assert built == ["<style>.a { color: red; }</style>"]
    assert collector.consume("plain content") is False


def test_a_one_line_style_block_and_a_stray_rule_are_each_wrapped() -> None:
    built: list[str] = []
    collector = _StyleCollector(built)
    assert collector.consume("<style>.b{x:y}</style>") is True
    assert collector.consume(".c { margin: 0; }") is True
    assert built == ["<style>.b{x:y}</style>", "<style>.c { margin: 0; }</style>"]


def test_the_map_fallback_makes_a_div_per_line_and_a_span_per_colour() -> None:
    data = {
        0: {"text": ["Project: ", "Home"], "color": ["red", "blue"]},
        1: {"text": ["a < b"], "color": []},
        2: {"text": ["<b>kept</b>"], "color": ["green"]},
    }
    lines = _fallback_map_html(data)
    assert lines[0] == "<div><span style='color: red;'>Project: </span><span style='color: blue;'>Home</span></div>"
    assert lines[1] == "<div><span style='color: inherit;'>a &lt; b</span></div>", "no colour for a segment means inherit"
    assert "<b>kept</b>" in lines[2]


def test_css_in_the_maps_lines_becomes_a_style_element_instead_of_text() -> None:
    lines = _fallback_map_html({0: {"text": [".x { color: red; }"], "color": []}, 1: {"text": ["real"], "color": ["red"]}})
    assert lines[0] == "<style>.x { color: red; }</style>"
    assert lines[1].startswith("<div>")


def test_the_other_views_fallback_escapes_each_line_and_keeps_blank_ones_as_spacers() -> None:
    lines = _fallback_lines_html(["plain", "", "a < b", "<br><br>", "line\r\n"])
    assert lines[0] == "<div>plain</div>"
    assert lines[1] == "<div>&nbsp;</div>"
    assert lines[2] == "<div>a &lt; b</div>"
    assert lines[-1] == "<div>line</div>"


def test_the_fallback_drops_the_empty_markers_and_triple_quotes_the_generator_leaves() -> None:
    lines = _fallback_lines_html(['"""text"""', "<div>\n</div>\"\"\"", "<div>  </tr>\n</div>\"\"\""])
    assert lines[0] == "<div>text</div>"


def test_runs_of_blank_lines_in_the_fallback_are_squeezed_to_one() -> None:
    squeezed = _compress_blank_lines("<p>a</p><div></div><div>&nbsp;</div><div> </div><p>b</p>")
    assert squeezed == "<p>a</p><p>b</p>"
    assert _compress_blank_lines("a\n\n\n\nb") == "a\nb"
    assert _compress_blank_lines("a<br><br><br>b") == "a<br>b"
    assert _compress_blank_lines("a<div></div>b") == "a<div></div>b", "a single empty div is left alone"


# ##################################################################################
# The scope badge, and the colours a view paints itself with
# ##################################################################################
def test_a_badge_for_the_whole_configuration_says_so_rather_than_trailing_off() -> None:
    assert scope_badge_text("", "") == ("Drawn for the whole configuration", "")


def test_a_badge_names_the_selection_it_was_drawn_for_and_stays_quiet_while_it_still_applies() -> None:
    assert scope_badge_text("Project 'Home'", "Project 'Home'") == ("Drawn for Project 'Home'", "")


def test_a_selection_that_has_changed_since_is_named_beside_the_old_one() -> None:
    assert scope_badge_text("Project 'Home'", "Task 'Wake Up'") == (
        "Drawn for Project 'Home'",
        "-- now showing Task 'Wake Up'",
    )
    assert scope_badge_text("Project 'Home'", "") == ("Drawn for Project 'Home'", "-- now showing the whole configuration")
    assert scope_badge_text("", "Scene 'Panel'") == ("Drawn for the whole configuration", "-- now showing Scene 'Panel'")


def test_a_view_paints_itself_for_the_mode_the_window_is_in() -> None:
    assert view_theme_colors(SimpleNamespace(dark_mode=False)) == ("#ffffff", "#000000")
    assert view_theme_colors(SimpleNamespace(dark_mode=True)) == ("#1e293b", "#ffffff")
    assert view_theme_colors(SimpleNamespace()) == ("#ffffff", "#000000"), "a switch never touched is light"


def test_the_windows_own_background_wins_over_the_default() -> None:
    window = SimpleNamespace(dark_mode=True, color_lookup={"background": "#123456"})
    assert view_theme_colors(window) == ("#123456", "#ffffff")


def test_an_icon_in_a_diagram_line_is_held_to_two_columns_wide() -> None:
    html = _wrap_diagram_line(0, "Task \U0001f4be <x> \u2699\ufe0f \u2502", {}, {}, {})

    assert '<span class="mt-w">\U0001f4be</span> &lt;x&gt; <span class="mt-w">\u2699\ufe0f</span> \u2502' in html


def test_the_chunks_of_a_text_view_have_no_gap_between_them() -> None:
    """NiceGUI puts a rem between the children of a scroll area, which showed as a blank line every 150 lines."""
    from pathlib import Path

    css = (Path(guiwins_views.__file__).parents[2] / "assets" / "css" / "maptasker.css").read_text(encoding="utf-8")

    assert ".nicegui-scroll-area.mt-textview .q-scrollarea__content {\n    gap: 0;" in css
    assert "mt-textview" in inspect.getsource(guiwins_views.NiceGuiTextView._build_scroll_area)
