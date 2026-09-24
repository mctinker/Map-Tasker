"""The Map's html says what it means: tags that close, and nothing invented.

The Map used to lean on a browser's error recovery.  An action and a Profile were each
written as a "<div " left open so that the line's own "<span class=..." would be taken for
part of the div's attribute list; an end-of-label marker was written as "<data-flag=...>",
which is not an element at all; spans were opened and closed by a dozen different places
that could not see each other's work, so end tags closing nothing and spans left open ran
into the thousands.  All of it rendered, because a browser is forgiving -- and everything
that reads the Map rather than displaying it (the Markdown, JSON and PDF exports, and
anyone opening the saved file in another tool) had to be just as forgiving.

What is checked here is that the markup now says what the browser was inferring, and that
the same thing is drawn either way.
"""

from __future__ import annotations

import io

import pytest
from maptasker.src.initparg import ProgramArguments
from maptasker.src.colrmode import set_color_mode
from maptasker.src.format import SpanBalancer, format_label
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems


def balanced(*pieces: str) -> str:
    """Write the pieces through a balancer and hand back what reached the file."""
    out_file = io.StringIO()
    balancer = SpanBalancer(out_file)
    for piece in pieces:
        balancer.write(piece)
    balancer.finish()
    return out_file.getvalue()


# ##################################################################################
# SpanBalancer -- what the browser would have made of it, written down
# ##################################################################################
def test_markup_that_already_balances_is_written_as_it_stands() -> None:
    """Nothing is added to or taken from html that closes what it opens."""
    html = '<div id="a" class="action_color actiontab">01: <span class="action_name_color">If</span></div>'
    assert balanced(html) == html


def test_an_end_tag_that_closes_nothing_is_dropped() -> None:
    """The browser ignores it, so the file has no reason to carry it."""
    html = '<div>08: <span class="action_name_color">End If</span></span></div>'
    assert balanced(html) == '<div>08: <span class="action_name_color">End If</span></div>'


def test_a_span_left_open_is_closed_where_its_block_ends() -> None:
    """Exactly where the browser closes it: before the end tag of the block holding it."""
    assert balanced('<div><span class="action_color">args</div>') == '<div><span class="action_color">args</span></div>'


def test_spans_are_closed_innermost_first() -> None:
    """Two left open inside one block close in the order that keeps them nested."""
    html = '<div><span class="a">one<span class="b">two</div>'
    assert balanced(html) == '<div><span class="a">one<span class="b">two</span></span></div>'


def test_a_gap_is_counted_across_the_pieces_it_was_written_in() -> None:
    """The Map is written a piece at a time, and a span may be opened in one and closed in the next."""
    assert balanced('<div><span class="a">x', "y</span></div>") == '<div><span class="a">xy</span></div>'


def test_what_is_still_open_at_the_end_of_the_file_is_closed() -> None:
    """A run that ends mid-span (the view limit does) still leaves a closed document."""
    assert balanced('<span class="a">one') == '<span class="a">one</span>'


def test_a_less_than_sign_in_the_text_is_text() -> None:
    """A condition reading "%x < %y" is not a tag, and must not throw the count off."""
    html = '<div><span class="a"> (%st_attr_value < %lowbat)</span></span></div>'
    assert balanced(html) == '<div><span class="a"> (%st_attr_value < %lowbat)</span></div>'


def test_a_quoted_angle_bracket_does_not_end_a_tag() -> None:
    """A tooltip's own text may hold a ">"; the tag it sits in ends at the real one."""
    html = '<div><span class="hover-tooltip" data-tooltip="Profiles: a > b">Project:</span></div>'
    assert balanced(html) == html


# ##################################################################################
# lineout -- the <div> an action and a Profile are drawn in
# ##################################################################################
@pytest.fixture
def line_out() -> LineOut:
    """A LineOut to call the line builders on."""
    return LineOut()


def test_an_action_becomes_a_div_carrying_its_colour_and_indent(line_out: LineOut) -> None:
    """The class the browser used to take out of the swallowed span is now the div's own."""
    element = 'id="mt-task-18-a1" <span class="action_color actiontab">01:</span> <span class="x">If</span>'
    assert line_out.line_div(element) == (
        '<div id="mt-task-18-a1" class="action_color actiontab">01: <span class="x">If</span></div>'
    )


def test_the_anchor_stays_in_front_of_the_class(line_out: LineOut) -> None:
    """mapexport reads an action's number from what follows its class attribute."""
    element = '<span class="action_color actiontab">02:</span> rest'
    assert line_out.line_div(element).startswith('<div class="action_color actiontab">02:')


def test_the_span_that_gave_up_its_class_takes_its_end_tag_with_it(line_out: LineOut) -> None:
    """Only its own end tag: one that closes a span nested inside it stays where it is."""
    element = '<span class="profile_color proftab"><span class="hover-tooltip">Profile:</span> name</span> after'
    assert line_out.line_div(element) == (
        '<div class="profile_color proftab"><span class="hover-tooltip">Profile:</span> name after</div>'
    )


def test_a_line_with_no_opening_span_is_still_given_a_div(line_out: LineOut) -> None:
    """Nothing in the Map takes this branch, but it must not invent markup if anything does."""
    assert line_out.line_div("plain text") == "<div>plain text</div>"


def test_a_tab_is_added_to_the_line_s_colour(line_out: LineOut) -> None:
    """The indent rides along with the color class it is added to."""
    assert line_out.add_tab("proftab", '<span class="profile_color">x') == '<span class="profile_color proftab">x'


def test_a_project_is_separated_from_what_came_before_it(line_out: LineOut) -> None:
    """A Project heading starts something new, so a blank line goes in front of it."""
    PrimeItems.program_arguments = ProgramArguments(directory=False)
    PrimeItems.directory_items = {"current_item": ""}
    assert line_out.handle_project('<span class="project_color">Project:</span> <em>Home</em>').startswith("<br>")


def test_a_projects_properties_line_is_not_separated_from_the_project(line_out: LineOut) -> None:
    """It belongs to the Project above it, and brings a line break of its own.

    Both breaks together drew two blank lines between "Project: Home" and its
    "Project: Properties..." line, where the Profile's and the Task's have one.
    """
    PrimeItems.program_arguments = ProgramArguments(directory=False)
    PrimeItems.directory_items = {"current_item": ""}
    properties = '<span class="project_color"><br>Project: Properties...Comment:x<br></span>'
    assert not line_out.handle_project(properties).startswith("<br>")


def test_a_line_that_has_no_colour_to_tab_is_left_alone(line_out: LineOut) -> None:
    """It used to be spliced at find()'s -1, which wrote the line out twice over.

    A Project's or Profile's TaskerNet description arrives here already tabbed, so there is
    no 'class="..._color"' left to add a tab to -- and the splice put a mangled copy of the
    whole line into the Map, which is why such a description was drawn twice.
    """
    already_tabbed = '<span class="taskernet_color projtab"></span><div class="text-box">Description</div><br>'
    assert line_out.add_tab("proftab", already_tabbed) == already_tabbed


# ##################################################################################
# format_label -- a label's own html, drawn without knotting the Map's
# ##################################################################################
@pytest.fixture
def _colors() -> None:
    """format_label reads real colors out of colors_to_use."""
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.program_arguments = ProgramArguments(pretty=False, debug=False, display_detail_level=3)


@pytest.mark.usefixtures("_colors")
def test_a_list_in_a_label_keeps_its_tags_outside_the_colour_spans() -> None:
    """A <li> inside one span and its </li> inside the next crosses the tags around it."""
    label = format_label("<ul><li>first</li><li>second</li></ul>")
    assert "<ul>" in label
    assert "<li>" in label
    assert '<span style="color:' not in label.split("<li>")[0].split("<ul>")[-1]
    for fragment in ("<span><li>", "<li></span>", "<span></li>"):
        assert fragment not in label


@pytest.mark.usefixtures("_colors")
def test_a_small_left_open_in_a_description_is_closed_inside_its_box() -> None:
    """A browser reopens an unclosed <small> after the box, shrinking the rest of the Map."""
    label = format_label("<h6>TaskerNet description: Version 2<br><small>by someone")
    assert label.endswith("</small></p></div>")


@pytest.mark.usefixtures("_colors")
def test_a_table_left_open_in_a_description_is_closed_inside_its_box() -> None:
    """An open <table> swallows the box's </div>, pulling what follows into the table."""
    label = format_label("<h6>TaskerNet description: <table><tr><td>cell</td>")
    assert label.endswith("</td></tr></table></p></div>")


@pytest.mark.usefixtures("_colors")
def test_markup_the_author_closed_is_not_closed_again() -> None:
    """Only what is still open gets an end tag."""
    label = format_label("<h6>TaskerNet description: <small>fine print</small> and <big>more</big>")
    assert label.count("</small>") == 1
    assert label.count("</big>") == 1
