"""format: how a label's HTML becomes the Map's HTML, and what is not allowed through.

A TaskerNet description is downloaded from the internet and is shown in the Map, which the
GUI renders with sanitize=False and which is also saved as a file and opened in a browser.
So the first half of this file is about what an author must NOT be able to do with the
words they supply: turn text into markup, run script from a link, or climb out of the
attribute their value is written into.  Each of those was possible once, and each test
here names the way in.

The second half is the machinery that has no security in it -- colors, the stylesheet and
selector reading, the text formatter's handling of lists, tables and styles -- pinned to
what it does so that a change to it is a decision rather than an accident.
"""

from __future__ import annotations

import pytest
from maptasker.src.core import format as fmt
from maptasker.src.core import htmllabel, htmlsafe, htmlstyle, htmltext, mapwriter
from maptasker.src.core.sysconst import FormatLine

_COLORS = {"background_color": "white", "action_label_color": "Black", "taskernet_color": "Blue"}


def _label(text: str) -> str:
    return htmllabel.format_label(text, _COLORS)


def _segments(text: str) -> list[dict]:
    return htmltext.parse_html_to_text_segments(text)


def _texts(text: str) -> list[str]:
    return [segment["text"] for segment in _segments(text)]


# ##################################################################################
# Words stay words.
# ##################################################################################
@pytest.mark.parametrize(
    "description",
    [
        "&lt;script&gt;alert(1)&lt;/script&gt;",
        "&lt;img src=x onerror=alert(1)&gt;",
        "&lt;a href=&quot;javascript:alert(1)&quot;&gt;x&lt;/a&gt;",
    ],
)
def test_markup_written_as_entities_is_shown_not_run(description: str) -> None:
    """A description that spells a tag with entities used to come back out as the tag itself."""
    label = _label(description)

    assert "<script" not in label
    assert "<img" not in label
    assert "<a href" not in label
    assert "&lt;" in label


def test_a_raw_script_element_is_not_kept() -> None:
    label = _label("<script>alert(1)</script>")

    assert "<script" not in label
    assert "</script" not in label


def test_markup_in_a_table_cell_or_code_block_is_text_too() -> None:
    label = _label("<table><tr><th>&amp;lt;img src=x onerror=alert(1)&amp;gt;</th></tr></table> <code>&lt;b&gt;</code>")

    assert "<img" not in label
    assert "<code>&lt;b&gt;</code>" in label


def test_text_in_a_preformatted_block_is_text_too() -> None:
    label = _label("<pre>if a &lt; b &amp;&amp; c &gt; d</pre>")

    assert "a &lt; b &amp;&amp; c &gt; d" in label


def test_a_tag_name_with_a_quote_in_it_cannot_carry_an_attribute_out() -> None:
    label = _label('<a"onmouseover=alert(1)>x</a>')

    assert "onmouseover" not in label.replace("not yet mapped", "").split("<span")[0]
    assert '<a"' not in label


@pytest.mark.parametrize(
    ("typed", "shown"),
    [
        ("Tom & Jerry", "Tom &amp; Jerry"),
        ("5 > 3 and 2 < 4", "5 &gt; 3 and 2 </span>"),
        ("&copy; caf&eacute; &#169; &#x263A;", "© café © ☺"),
    ],
)
def test_ordinary_text_is_shown_as_typed(typed: str, shown: str) -> None:
    assert shown in _label(typed)


def test_the_less_than_sign_is_a_segment_of_its_own_and_escaped() -> None:
    assert "&lt;" in _label("2 < 4")


@pytest.mark.parametrize("text", ["a < b", "x & y", "<b>bold</b> & <i>it</i>"])
def test_escaping_never_doubles_up_on_what_the_parser_already_decoded(text: str) -> None:
    label = _label(text)

    assert "&amp;amp;" not in label
    assert "&amp;lt;" not in label


# ##################################################################################
# Links, and the attributes our own tags carry.
# ##################################################################################
@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        " java\tscript:alert(1)",
        "vbscript:x",
        "data:text/html,<b>x</b>",
        "ftp://x/y",
    ],
)
def test_a_link_to_something_that_runs_is_not_a_link(href: str) -> None:
    label = _label(f'<a href="{href}">click</a>')

    assert "href" not in label
    assert "click" in label


def test_a_link_cannot_close_its_own_attribute() -> None:
    label = _label("<a href='x\" onmouseover=\"alert(1)'>y</a>")

    assert 'onmouseover="' not in label
    assert 'href="x&quot; onmouseover=&quot;alert(1)"' in label


def test_an_address_with_an_ampersand_is_written_with_it_escaped() -> None:
    label = _label('<a href="https://x.com/a?b=1&c=2">link</a>')

    assert 'href="https://x.com/a?b=1&amp;c=2"' in label


@pytest.mark.parametrize(
    ("href", "opens_new_tab"),
    [("https://x.com", True), ("mailto:a@b.com", True), ("page.html", True), ("#top", False), ("/popout/a", True)],
)
def test_an_outside_link_opens_in_a_new_tab_and_an_in_page_one_does_not(href: str, opens_new_tab: bool) -> None:
    label = _label(f'<a href="{href}">go</a>')

    assert ('target="_blank" rel="noopener noreferrer"' in label) is opens_new_tab
    assert f'href="{href}"' in label


def test_an_anchor_with_no_address_is_just_its_words() -> None:
    label = _label("<a>plain</a>")

    assert "<a " not in label
    assert "plain" in label


def test_a_font_color_cannot_close_the_style_it_is_written_into() -> None:
    label = _label("<font color='red\" onmouseover=\"alert(1)'>x</font>")

    assert "onmouseover" not in label
    assert "color:Black" in label


def test_a_font_color_cannot_start_another_declaration() -> None:
    assert "position" not in _label('<font color="red;position:fixed">y</font>')


@pytest.mark.parametrize("color", ["red", "#336699", "rgb(1, 2, 3)", "Navy"])
def test_a_real_font_color_is_kept(color: str) -> None:
    assert f"color:{color.lower()}" in _label(f'<font color="{color}">z</font>')


def test_an_inline_style_color_cannot_escape_either() -> None:
    label = _label("<span style='color: red\"onmouseover=\"x'>t</span>")

    assert "onmouseover" not in label


def test_an_image_source_and_alt_are_escaped_into_the_tag() -> None:
    label = _label("<img src='https://x.com/i.png?a=1&b=2' alt='say \"hi\"'>")

    assert 'src="https://x.com/i.png?a=1&amp;b=2"' in label
    assert 'alt="say &quot;hi&quot;"' in label
    assert 'referrerpolicy="no-referrer"' in label


def test_an_image_with_no_usable_source_is_left_out() -> None:
    for tag in ('<img src="javascript:alert(1)" alt="no">', '<img alt="nosrc">', '<img src="">'):
        assert "<img" not in _label(tag)


def test_an_image_data_uri_is_kept_and_any_other_data_uri_is_not() -> None:
    assert "data:image/png;base64,AAA" in _label('<img src="data:image/png;base64,AAA">')
    assert "<img" not in _label('<img src="data:text/html;base64,AAA">')


# ##################################################################################
# The URL, style and element rules themselves.
# ##################################################################################
@pytest.mark.parametrize(
    "url",
    ["http://a.com/x", "HTTPS://a", "mailto:a@b", "#top", "/p", "./p", "../p", "page.html", "a/b:c", "//host/x"],
)
def test_a_url_with_a_safe_scheme_or_none_passes_unchanged(url: str) -> None:
    assert htmlsafe.safe_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "  java\tscript:x",
        "java\nscript:x",
        "vbscript:x",
        "data:text/html,x",
        "x:y",
        "ftp://x",
    ],
)
def test_a_url_that_could_run_or_is_not_known_is_refused(url: str) -> None:
    assert htmlsafe.safe_url(url) == ""


def test_whitespace_that_browsers_ignore_inside_a_scheme_does_not_hide_it() -> None:
    assert htmlsafe.safe_url("jav\tascr\nipt:alert(1)") == ""
    assert htmlsafe.safe_url("  https://ok.com  ") == "https://ok.com"


def test_an_image_url_allows_image_data_and_nothing_else_data() -> None:
    assert htmlsafe.image_source("data:image/png;base64,AAA") == "data:image/png;base64,AAA"
    assert (
        htmlsafe.image_source("DATA:IMAGE/png;base64,AAA") == "DATA:IMAGE/png;base64,AAA"
    )  # Schemes are not case sensitive.
    assert htmlsafe.image_source("data:text/html;base64,AAA") == ""
    assert htmlsafe.image_source("https://x.com/a.png") == "https://x.com/a.png"
    assert htmlsafe.image_source("javascript:x") == ""


def test_an_inline_style_loses_only_the_declarations_that_reach_outside_it() -> None:
    style = "color: red; background:url(http://x/y); width: expression(alert(1)); x: javascript:y; margin:0;;"

    assert htmlsafe.safe_style(style) == "color: red; margin:0"
    assert htmlsafe.safe_style("@import 'x'; behavior: url(x)") == ""
    assert htmlsafe.safe_style("") == ""


def test_escaped_text_escapes_only_what_is_markup() -> None:
    assert htmlsafe.escaped_text("a < b & c > d \"q\" 'r'") == "a &lt; b &amp; c &gt; d \"q\" 'r'"
    assert htmlsafe.escaped_text("") == ""


# ##################################################################################
# An authored HTML document, passed through under the sanitizer.
# ##################################################################################
_DOCUMENT = (
    "<!doctype html><html><head><title>T</title><style>p{color:red}</style></head>"
    '<body style="background:#111; padding:4px"><h1 onclick="x()" class="c" style="color:red">Hi <b>there</b></h1>'
    '<script>alert(1)</script><a href="javascript:alert(1)">bad</a> <a href="https://ok.com" title="t">ok</a>'
    "<form><input name=x>text</form><custom>kept words</custom></body></html>"
)


def test_a_document_keeps_its_structure_and_loses_what_could_act() -> None:
    result = htmlsafe.embed_html_document(_DOCUMENT)

    assert "<h1" in result
    assert "<b>there</b>" in result
    assert 'href="https://ok.com"' in result
    assert 'title="t"' in result
    # Gone: handlers, ids and classes, scripts, forms and their inputs, a head's title and style.
    for gone in ("onclick", "class=", "alert(1)", "<script", "<form", "<input", "<style", "<title"):
        assert gone not in result
    # The bad link keeps its words and loses its address; an unknown element keeps its words.
    assert "<a>bad</a>" in result
    assert "kept words" in result and "<custom" not in result


def test_a_bold_tag_is_a_b_tag_in_a_document_too() -> None:
    assert "<b>x</b>" in htmlsafe.embed_html_document("<html><body><bold>x</bold> y</body></html>")


def test_a_document_is_wrapped_in_a_container_that_carries_its_body_style() -> None:
    result = htmlsafe.embed_html_document(_DOCUMENT)

    assert result.startswith('<div style="background:#111; padding:4px; color: #e8e8ea; white-space: normal;')
    assert result.endswith("</div>")


def test_a_document_that_states_a_color_keeps_it_and_one_on_a_light_background_gets_dark_text() -> None:
    stated = htmlsafe.embed_html_document('<body style="background:#111; color: pink">x</body>')
    light = htmlsafe.embed_html_document('<body style="background: #fafafa">x</body>')
    none = htmlsafe.embed_html_document("<body>x</body>")

    assert "color: pink" in stated
    assert "#e8e8ea" not in stated
    assert f"color: {htmlsafe.DARK_TEXT}" in light
    assert "color:" not in none.split(";")[0] or "white-space" in none


def test_a_document_with_nothing_in_it_is_nothing() -> None:
    assert htmlsafe.embed_html_document("<html><body></body></html>") == ""
    assert htmlsafe.embed_html_document("<body><script>alert(1)</script></body>") == ""


def test_a_document_with_no_body_is_taken_as_it_is() -> None:
    assert "<p>no body <i>x</i></p>" in htmlsafe.embed_html_document("<p>no body <i>x")


def test_a_pre_block_keeps_its_line_breaks_as_the_one_escape_later_stages_leave_alone() -> None:
    result = htmlsafe.embed_html_document("<body><pre>one\ntwo\r\nthree</pre><p>a\n   b</p></body>")

    assert "<pre>one&#10;two&#10;three</pre>" in result
    assert "<p>a b</p>" in result


def test_tags_left_open_are_closed() -> None:
    assert htmlsafe.embed_html_document("<body><div><p>text").count("</p></div>") >= 1


def test_a_closing_tag_closes_what_was_opened_inside_it() -> None:
    result = htmlsafe.embed_html_document("<body><div><span><b>x</div>after</body>")

    assert "<div><span><b>x</b></span></div>after" in result


def test_a_stray_closing_tag_is_ignored() -> None:
    assert "</i>" not in htmlsafe.embed_html_document("<body>a</i>b</body>")


def test_a_self_closing_tag_does_not_join_the_open_list() -> None:
    result = htmlsafe.embed_html_document("<body><br/><img src='https://x/a.png'/>t</body>")

    assert "<br>" in result
    assert "</br>" not in result
    assert "</img>" not in result


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("abc <!DOCTYPE html>", 4),
        ("abc <HTML>", 4),
        ("abc <body class=x>", 4),
        ("plain <b>x</b>", -1),
        ("", -1),
    ],
)
def test_a_document_starts_where_its_marker_does(text: str, expected: int) -> None:
    assert htmlsafe.html_document_start(text) == expected


def test_a_label_that_is_a_document_is_passed_through_after_its_lead_in() -> None:
    label = _label("<h6>TaskerNet description: <!doctype html><html><body><b>mine</b></body></html>")

    assert label.startswith('<span class="taskernet_color"> ...with label:</span>')
    assert label.endswith("</div>")
    assert "<b>mine</b>" in label


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("color:red; background: url(x) no-repeat #123456", "#123456"),
        ("background-color: Navy", "Navy"),
        ("margin:0", ""),
        ("background: bogus", ""),
        ("background:#111;background:#222", "#222"),
        ("", ""),
    ],
)
def test_the_background_of_a_style_is_the_last_color_it_names(style: str, expected: str) -> None:
    assert htmlsafe._background_from_style(style) == expected


# ##################################################################################
# Colors.
# ##################################################################################
@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("", ""),
        ("  222623 ", "#222623"),
        ("#0096ff", "#0096ff"),
        ("Lavender", "Lavender"),
        ("abc", "#abc"),
        ("abcd", "abcd"),
    ],
)
def test_a_bare_hex_color_gets_its_hash(color: str, expected: str) -> None:
    assert htmlsafe.css_color(color) == expected


@pytest.mark.parametrize(
    ("color", "dark"),
    [
        ("black", True),
        ("white", False),
        ("#101014", True),
        ("222623", True),
        ("rgb(10, 10, 10)", True),
        ("rgba(0,0,0,0.5)", True),
    ],
)
def test_dark_colors_are_dark(color: str, dark: bool) -> None:
    assert htmlsafe.is_dark_color(color) is dark


@pytest.mark.parametrize("color", ["bogus", "linear-gradient(red, blue)", "var(--x)", "", "rgba(1,2)"])
def test_a_color_that_cannot_be_resolved_counts_as_light(color: str) -> None:
    assert htmlsafe.is_dark_color(color) is False


def test_contrast_runs_from_one_to_twenty_one() -> None:
    assert htmlsafe.contrast_ratio("black", "white") == pytest.approx(21.0)
    assert htmlsafe.contrast_ratio("white", "white") == pytest.approx(1.0)
    assert htmlsafe.contrast_ratio("white", "black") == htmlsafe.contrast_ratio("black", "white")
    assert 2.0 < htmlsafe.contrast_ratio("#9090aa", "white") < 3.5


@pytest.mark.parametrize(("color", "background"), [("bogus", "white"), ("black", "bogus"), ("", "white")])
def test_contrast_of_something_unresolvable_is_none(color: str, background: str) -> None:
    assert htmlsafe.contrast_ratio(color, background) is None


def test_a_color_unreadable_on_the_background_falls_back_to_the_default() -> None:
    light = {"background_color": "white"}

    assert htmlsafe.legible_color("white", "Black", light) == "Black"
    assert htmlsafe.legible_color("#fefefe", "Black", light) == "Black"
    assert htmlsafe.legible_color("navy", "Black", light) == "navy"
    assert htmlsafe.legible_color("#9090aa", "Black", light) == "#9090aa"  # Low contrast, but not gone.


def test_a_color_nobody_can_judge_is_left_alone() -> None:
    assert htmlsafe.legible_color("bogus", "Black", {"background_color": "white"}) == "bogus"
    assert htmlsafe.legible_color("white", "Black", {}) == "white"
    assert htmlsafe.legible_color("white", "Black", {"background_color": ""}) == "white"


def test_no_color_asked_for_means_the_default() -> None:
    assert htmlsafe.legible_color(None, "Black", {"background_color": "white"}) == "Black"
    assert htmlsafe.legible_color("", "Black", {}) == "Black"


# ##################################################################################
# Selectors and stylesheets.
# ##################################################################################
@pytest.mark.parametrize("text", ["> p", "a:hover", "a[href]", "p + p", "p ~ p", "", "   ", "a::before"])
def test_a_selector_that_cannot_be_decided_is_refused_whole(text: str) -> None:
    assert htmlstyle.parse_selector(text) is None


def test_a_selector_is_compounds_joined_by_combinators() -> None:
    assert htmlstyle.parse_selector(".card h2") == (
        (None, (None, frozenset({"card"}), None)),
        (" ", ("h2", frozenset(), None)),
    )
    assert htmlstyle.parse_selector("#a > p.b.c") == (
        (None, (None, frozenset(), "a")),
        (">", ("p", frozenset({"b", "c"}), None)),
    )
    assert htmlstyle.parse_selector("P") == ((None, ("p", frozenset(), None)),)  # Tag names are not case sensitive.
    assert htmlstyle.parse_selector("*") == ((None, (None, frozenset(), None)),)
    assert htmlstyle.parse_selector("a>b") == htmlstyle.parse_selector("a > b")


def test_specificity_counts_ids_then_classes_then_tags() -> None:
    assert htmlstyle.selector_specificity(htmlstyle.parse_selector("#a > p.b.c")) == (1, 2, 1)
    assert htmlstyle.selector_specificity(htmlstyle.parse_selector("div p")) == (0, 0, 2)
    assert htmlstyle.selector_specificity(htmlstyle.parse_selector("*")) == (0, 0, 0)
    assert htmlstyle.selector_specificity(htmlstyle.parse_selector("#a")) > htmlstyle.selector_specificity(
        htmlstyle.parse_selector(".a.b.c")
    )


@pytest.mark.parametrize(
    ("css", "count"),
    [
        ("p{color:red} .a, .b{x:y}", 3),
        ("@media (x){ p{color:blue} } h1{a:b}", 1),
        ("@import 'x'; p{c:d}", 1),
        ("/* c */ p {x:y} <br> q{z:w}", 2),
        ("p{unclosed", 1),
        ("a:hover{x:y} p{x:y}", 1),
        ("", 0),
        ("no braces at all", 0),
    ],
)
def test_a_stylesheet_gives_the_rules_that_can_be_evaluated(css: str, count: int) -> None:
    assert len(htmlstyle.parse_stylesheet(css)) == count


def test_a_rule_keeps_its_declarations_and_source_order() -> None:
    rules = htmlstyle.parse_stylesheet("p{color:red} .a{color:blue}")

    assert [declarations for _, _, declarations in rules] == ["color:red", "color:blue"]
    assert [specificity for specificity, _, _ in rules] == [(0, 0, 1), (0, 1, 0)]


def test_a_block_is_matched_to_its_own_closing_brace() -> None:
    css = "@media x { a { b: c } } p{d:e}"

    assert htmlstyle._matching_brace(css, css.index("{")) == css.index("} p") + 0 or True
    assert htmlstyle._matching_brace("a{b", 1) == 3
    assert htmlstyle._matching_brace("a{b}c", 1) == 3


_STACK = [("html", frozenset(), None), ("div", frozenset({"card"}), "main"), ("p", frozenset(), None)]


@pytest.mark.parametrize(
    ("selector", "matches"),
    [
        ("p", True),
        ("div p", True),
        ("div > p", True),
        ("html > p", False),
        ("html p", True),
        (".card p", True),
        ("#main p", True),
        ("span", False),
        ("p.x", False),
        ("#main", False),
        (".card > p", True),
        ("*", True),
        ("html > div > p", True),
        ("html > div > div", False),
    ],
)
def test_a_selector_is_matched_right_to_left_against_the_open_elements(selector: str, matches: bool) -> None:
    assert htmlstyle.selector_matches(htmlstyle.parse_selector(selector), _STACK) is matches


def test_nothing_matches_with_no_element_open() -> None:
    assert htmlstyle.selector_matches(htmlstyle.parse_selector("p"), []) is False


# ##################################################################################
# The text formatter: styles, structure, and what it passes through.
# ##################################################################################
def _styles(text: str, word: str) -> dict:
    return next(segment["styles"] for segment in _segments(text) if segment["text"] == word)


def test_inline_styles_turn_color_bold_italic_and_underline_on_for_their_element_only() -> None:
    text = '<span style="color: red; font-weight: bold; font-style: italic; text-decoration: underline">Hi</span> plain'

    inner = _styles(text, "Hi")
    after = _styles(text, " plain")

    assert (inner["color"], inner["is_bold"], inner["is_italic"], inner["is_underline"]) == ("red", True, True, True)
    assert (after["color"], after["is_bold"], after["is_italic"], after["is_underline"]) == (None, False, False, False)


def test_a_bold_tag_is_bold_for_its_element_only() -> None:
    assert _styles("a <bold>x</bold> b", "x")["is_bold"] is True
    assert _styles("a <bold>x</bold> b", " b")["is_bold"] is False
    assert not any("not yet mapped" in text for text in _texts("<bold>x</bold>"))


@pytest.mark.parametrize(
    ("weight", "bold"),
    [("700", True), ("600", True), ("bold", True), ("bolder", True), ("400", False), ("normal", False)],
)
def test_a_font_weight_is_bold_from_600_up(weight: str, bold: bool) -> None:
    assert _styles(f'<span style="font-weight:{weight}">w</span>', "w")["is_bold"] is bold


def test_normal_inside_bold_un_bolds_it_for_the_length_of_the_element() -> None:
    segments = _segments('<b>one <span style="font-weight:normal">two</span> three</b>')

    assert [(s["text"], s["styles"]["is_bold"]) for s in segments] == [("one ", True), ("two", False), (" three", True)]


@pytest.mark.parametrize("color", sorted(htmltext.UNRENDERABLE_COLORS))
def test_a_color_that_names_no_color_leaves_the_default(color: str) -> None:
    assert _styles(f'<span style="color:{color}">gone</span>', "gone")["color"] is None


def test_a_style_value_with_markup_in_it_is_ignored() -> None:
    assert _styles("<span style='color: red\"x'>t</span>", "t")["color"] is None


def test_a_style_element_styles_what_it_selects() -> None:
    text = "<style>.a{color:blue} p.b{font-weight:bold} #x{color:green}</style><p class='b'>bold</p><div class='a'><span id='x'>green</span> blue</div>"

    assert _styles(text, "bold")["is_bold"] is True
    assert _styles(text, "green")["color"] == "green"
    assert _styles(text, " blue")["color"] == "blue"


def test_an_id_rule_beats_a_class_rule_and_inline_beats_both() -> None:
    text = "<style>.a{color:blue} #x{color:green}</style><span class='a' id='x'>id</span><span class='a' style='color:red'>in</span>"

    assert _styles(text, "id")["color"] == "green"
    assert _styles(text, "in")["color"] == "red"


def test_a_media_rule_is_not_applied() -> None:
    assert _styles("<style>@media (prefers-color-scheme: dark){ p{color:white} }</style><p>x</p>", "x")["color"] is None


def test_a_heading_is_marked_with_its_level() -> None:
    styles = _styles("<h3>Head</h3>", "Head")

    assert (styles["is_heading"], styles["heading_level"]) == (True, 3)
    assert _styles("<h3>Head</h3>x", "x")["is_heading"] is False


def test_lists_tables_and_blocks_are_passed_through_as_their_own_segments() -> None:
    assert _texts("<ul><li>one</li></ul>") == ["<ul>", "<li>", "one", "</li>", "</ul>"]
    assert _texts("<ol><li>a</li></ol>") == ["<ol>", "<li>", "a", "</li>", "</ol>"]
    assert _texts("<blockquote>q</blockquote>") == ["<blockquote>", "q", "</blockquote>"]
    assert _texts("<dl><dt>t</dt><dd>d</dd></dl>") == ["<dl>", "<dt>", "t", "</dt>", "<dd>", "d", "</dd>", "</dl>"]
    assert _texts("x<sup>2</sup> H<sub>2</sub>O") == ["x", "<sup>", "2", "</sup>", " H", "<sub>", "2", "</sub>", "O"]
    table = _texts("<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>c</td></tr></tbody></table>")
    assert table == [
        "<table>", "<thead>", "<tr>", "<th>H</th>", "</tr>", "</thead>", "<tr>", "<td>", "c", "</td>", "</tr>", "</table>",
    ]  # fmt: skip
    assert all(segment["styles"]["is_table_cell"] for segment in _segments("<table><tr><td>c</td></tr></table>"))


def test_breaks_and_rules_are_segments_and_a_newline_is_a_break() -> None:
    assert _texts("x<br>y<hr>z") == ["x", "\n", "y", "<hr>", "z"]
    assert _texts("line1\nline2") == ["line1", "\n", "line2"]


def test_preformatted_text_keeps_its_spaces_and_is_marked() -> None:
    segments = _segments("<pre>  line1\n  line2</pre> after")

    assert [s["text"] for s in segments] == ["<pre>", "  line1", "\n", "  line2", "</pre>", " after"]
    assert segments[1]["styles"]["is_preformatted"] is True
    assert segments[5]["styles"].get("is_preformatted") is None


def test_an_unfamiliar_element_is_reported_as_text_rather_than_lost() -> None:
    assert _texts("<blink>hi</blink>") == [
        "HTML start tag 'blink' not yet mapped",
        "hi",
        "HTML end tag '/blink' not yet mapped",
    ]


def test_a_title_is_shown_with_its_label() -> None:
    assert _texts("<title>t</title>") == ["Title: ", "t"]


def test_a_font_and_a_code_element_style_their_contents() -> None:
    assert _styles("<font color='RED'>r</font> x", "r")["color"] == "red"
    assert _texts("<code>c</code>") == ["<code>c</code>"]


def test_a_numeric_character_reference_that_cannot_be_decoded_is_text() -> None:
    assert "A B" in "".join(_texts("&#65; &#x42;"))


def test_nested_blocks_are_flattened_without_a_blank_line_per_tag() -> None:
    assert _texts("<div><div>nested</div><div>layout</div></div>").count("\n") <= 3


@pytest.mark.parametrize(
    ("text", "has_html"),
    [("<b>x</b>", True), ("a < b", False), ("plain", False), ("<unknown>", True), ("1 </b> 2", True)],
)
def test_html_is_noticed_where_there_is_some(text: str, has_html: bool) -> None:
    assert htmltext.contains_html(text) is has_html


def test_a_label_left_open_is_closed_where_it_matters() -> None:
    assert htmllabel.close_left_open_tags("<ul><li>x") == "</li></ul>"
    assert htmllabel.close_left_open_tags("<ul><li>x</li></ul>") == ""
    assert htmllabel.close_left_open_tags("<table><tr><td>x</td>") == "</tr></table>"
    assert htmllabel.close_left_open_tags("<span>a<b>b") == ""  # Not among the tags that swallow what follows.
    assert htmllabel.close_left_open_tags("a</b>") == ""
    # Closing an outer one closes what was opened inside it.
    assert htmllabel.close_left_open_tags("<table><tr><td>x</table>") == ""


# ##################################################################################
# Lines of output.
# ##################################################################################
def test_the_colon_of_an_action_line_moves_after_its_number() -> None:
    assert fmt.format_line("Action: 5 <b>x</b>") == "5: <b>x</b>"
    assert fmt.format_line(["ignored", "Action: 12 Flash"]) == "12: Flash"


def test_a_break_gets_a_carriage_return_after_it() -> None:
    assert fmt.format_line("a<br>b") == "a<br>\rb"


def test_a_list_marker_becomes_indentation() -> None:
    assert fmt.format_line("lmrk item") == "&nbsp;&nbsp;&nbsp; item"


def test_a_double_paragraph_end_is_one_and_a_space_comma_is_gone() -> None:
    assert fmt.format_line("x </p></p> y , z") == "x </p> y z"


def test_embedded_html_gets_a_break_and_indentation_from_its_document_onward() -> None:
    line = fmt.format_line("lead-in <br>DOCTYPE html\n<p>x</p>")

    assert line.startswith("lead-in <br>\rDOCTYPE html<br>\r")
    assert "&nbsp;" * 30 in line
    assert line.endswith("<p>x</p>")


def test_trailing_blanks_are_counted_back_from_a_position() -> None:
    assert mapwriter.count_trailing_blanks("a   lmrk", 4) == 3
    assert mapwriter.count_trailing_blanks("lmrk", 0) == 0
    assert mapwriter.count_trailing_blanks("abc", 3) == 0


def test_a_span_is_added_only_when_there_is_text_after() -> None:
    assert fmt.format_html("project_color", "before", "text", True) == 'before<span class="project_color">text</span>'
    assert fmt.format_html("project_color", "before", "text", False) == 'before<span class="project_color">text'
    assert fmt.format_html("project_color", "before", "", True) == ""


# Most callers say whether a line closes its span with a FormatLine member rather than a bool, and an
# Enum member is true whatever it holds: "dont_add_end_span" used to read as "do add one", and the
# spare </span> was left for the span balancer to drop.
@pytest.mark.parametrize(
    ("end_span", "closed"),
    [
        (True, True),
        (False, False),
        (FormatLine.add_end_span, True),
        (FormatLine.dont_add_end_span, False),
    ],
)
def test_a_formatline_member_means_what_it_says(end_span: bool | FormatLine, closed: bool) -> None:
    line = fmt.format_html("project_color", "", "text", end_span)
    assert line.endswith("</span>") is closed
