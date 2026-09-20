"""The cap on blank lines in the Map, and what it must not take away.

The Map is written a piece at a time by a great many places, so the gaps between its
sections used to add up to anything: three, four, half a screen of nothing between a
Project and the heading after it.  format.BlankLineLimiter is what every piece of the
file now goes through on its way out, and it keeps any one gap down to MAX_BLANK_LINES.

What it counts is line endings, not <br>s, since the two are not the same -- the first
<br> after some text only ends that text's line, and a heading, a rule or a table has
ended the line it sat on before the next <br> arrives.  Everything that is not a surplus
<br> has to come through untouched, which is most of what is checked here: the file it
writes is also what the Map view, the exports and the PDF are all read back out of.
"""

from __future__ import annotations

import io

from maptasker.src.format import MAX_BLANK_LINES, BlankLineLimiter


def written(*pieces: str, max_blank_lines: int = MAX_BLANK_LINES) -> str:
    """Write the pieces through a limiter and hand back what reached the file."""
    out_file = io.StringIO()
    limiter = BlankLineLimiter(out_file, max_blank_lines)
    for piece in pieces:
        limiter.write(piece)
    return out_file.getvalue()


def test_a_gap_within_the_limit_is_left_alone() -> None:
    """Two blank lines is what the Map is allowed, so nothing is dropped at two."""
    assert written("Task<br>\n<br>\n<br>\nProject") == "Task<br>\n<br>\n<br>\nProject"


def test_a_longer_gap_is_cut_back_to_the_limit() -> None:
    """The fourth <br> onward is what would draw a third blank line."""
    assert written("Task<br><br><br><br><br><br>Project") == "Task<br><br><br>Project"


def test_a_gap_is_counted_across_the_pieces_it_was_written_in() -> None:
    """Nothing writing into the Map can see the <br>s the piece before it left behind."""
    assert written("Task<br>", "<br>", "<br>", "<br>", "Project") == "Task<br><br><br>Project"


def test_text_between_the_breaks_starts_the_gap_again() -> None:
    """Two gaps of two, not one gap of four: there is a line of text between them."""
    html = "Task<br><br><br>Profile<br><br><br>Project"
    assert written(html) == html


def test_spaces_alone_do_not_count_as_a_line_to_see() -> None:
    """A line holding nothing but spacing still reads as blank, so the gap runs on."""
    assert written("Task<br> <br>&nbsp;<br>\n<br>Project") == "Task<br> <br>&nbsp;<br>\nProject"


def test_an_indentation_span_holds_its_line_open() -> None:
    """normtab and its family are inline blocks, so each one is a line of its own."""
    html = '<span class="normtab"></span>Task<br><span class="normtab"></span><br><br><br>Project'
    assert written(html) == html


def test_a_heading_brings_white_space_of_its_own() -> None:
    """A browser sets a blank line's worth around an <h2> with no <br> involved, and
    that white space is one of the two the gap is allowed."""
    assert written("Task</h2><br><br><br>Project") == "Task</h2><br>Project"


def test_a_rule_is_something_to_see_and_the_gap_starts_from_it() -> None:
    """The gap before the rule is left as it is, and the one after starts from the rule --
    which, like a heading, brings white space of its own."""
    assert written("Task<br><br><br><hr><br><br>Project") == "Task<br><br><br><hr><br>Project"


def test_everything_that_is_not_a_surplus_break_comes_through_untouched() -> None:
    """Tags, attributes, entities and newlines are written exactly as they arrived."""
    html = (
        '<span class="task_color tasktab"><a id="tasks_Alert" href="#the_top">Task:</a>'
        "&nbsp;<em>Alert</em></span><br>\n<table><tr><td>1</td></tr></table>\n"
    )
    assert written(html) == html


def test_the_limit_can_be_set_to_something_else() -> None:
    """The cap is a number, not a habit -- one blank line, or none at all."""
    assert written("Task<br><br><br><br>Project", max_blank_lines=1) == "Task<br><br>Project"
    assert written("Task<br><br><br><br>Project", max_blank_lines=0) == "Task<br>Project"


def test_nothing_is_written_for_nothing() -> None:
    """An empty write is not a gap, and reaches the file as nothing at all."""
    assert written("", "Task", "") == "Task"
