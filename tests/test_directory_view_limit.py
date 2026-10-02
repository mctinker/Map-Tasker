"""The directory only offers a hotlink to something the reader can actually get to.

A Map bigger than the view limit is written only as far as that limit and stops there
(bildhtml.write_out_the_file).  The directory, though, is built from everything that was
found, so it used to offer hyperlinks to Projects, Profiles, Tasks and Scenes whose
anchors were in the part that never reached the file -- a link that looks live, and does
nothing at all when clicked.

Those entries are now listed as plain text.  What is checked here is which entries get
demoted (only the ones whose anchor is genuinely missing from the written part), that the
rest keep their hyperlinks, and that demoting one does not move it out of alphabetical
order in the table.
"""

from __future__ import annotations

import pytest
from maptasker.src.dirout import do_tasker_element, do_trailing_matters, unreachable_anchors
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems
from maptasker.src.runcfg import RunConfig


def anchor(anchor_id: str) -> str:
    """One output line carrying the anchor a directory entry points at."""
    return f'<a id="{anchor_id}"></a>\n'


@pytest.fixture
def output_lines() -> LineOut:
    """A fresh output queue for the directory to be written into, restored afterwards."""
    saved_lines, saved_items = PrimeItems.output_lines, PrimeItems.directory_items
    PrimeItems.output_lines = LineOut()
    PrimeItems.directory_items = {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []}
    yield PrimeItems.output_lines
    PrimeItems.output_lines, PrimeItems.directory_items = saved_lines, saved_items


def written(output_lines: LineOut) -> str:
    """Everything the directory just added to the output queue, as one string."""
    return "".join(output_lines.output_lines)


# ##################################################################################
# Which anchors the view limit leaves out of the file
# ##################################################################################
def test_nothing_is_dropped_when_the_whole_map_is_written() -> None:
    """An output that fits inside the view limit loses no anchors."""
    lines = [anchor("projects_Home"), "text", anchor("tasks_Wake")]

    assert unreachable_anchors(lines, 100) == set()


def test_an_anchor_past_the_limit_is_dropped() -> None:
    """The limit cuts the file at its line, so anchors below that never reach it."""
    lines = [anchor("projects_Home"), "text", anchor("tasks_Wake"), anchor("scenes_Panel")]

    assert unreachable_anchors(lines, 1) == {"tasks_Wake", "scenes_Panel"}


def test_the_last_line_within_the_limit_still_counts() -> None:
    """write_out_the_file stops *after* the limit's own line, so that line is written."""
    lines = [anchor("projects_Home"), anchor("tasks_Wake"), anchor("scenes_Panel")]

    assert unreachable_anchors(lines, 1) == {"scenes_Panel"}


def test_an_anchor_written_twice_survives_its_later_copy() -> None:
    """A Task listed under two Profiles is anchored where it is first written."""
    lines = [anchor("tasks_Wake"), "text", anchor("tasks_Wake"), anchor("tasks_Sleep")]

    assert unreachable_anchors(lines, 1) == {"tasks_Sleep"}


def test_anchors_nothing_in_the_directory_points_at_are_ignored() -> None:
    """The Map's other anchors (mapjump's "mt-" ids) are no concern of the directory's."""
    lines = [anchor("projects_Home"), anchor("mt-task-20"), anchor("tasks_Wake")]

    assert unreachable_anchors(lines, 0) == {"tasks_Wake"}


# ##################################################################################
# What the directory writes for them
# ##################################################################################
def test_an_entry_within_the_limit_keeps_its_hotlink(output_lines: LineOut) -> None:
    """Nothing changes for the ordinary case: the entry is a link to its anchor."""
    PrimeItems.directory_items["profiles"] = [["Morning", "Morning"]]

    do_tasker_element("profiles", RunConfig(), set(), state=PrimeItems)

    assert "<a href=#profiles_Morning" in written(output_lines)


def test_an_entry_past_the_limit_is_listed_as_plain_text(output_lines: LineOut) -> None:
    """Its anchor is not in the file, so a link to it would go nowhere."""
    PrimeItems.directory_items["profiles"] = [["Morning", "Morning"], ["Evening", "Evening"]]

    do_tasker_element("profiles", RunConfig(), {"profiles_Evening"}, state=PrimeItems)

    output = written(output_lines)
    assert "<a href=#profiles_Morning" in output
    assert "href=#profiles_Evening" not in output
    assert ">Evening<" in output  # Still listed -- just not as a hotlink.


def test_a_demoted_entry_stays_in_alphabetical_order(output_lines: LineOut) -> None:
    """Losing the hyperlink must not move the entry to the end of the table."""
    PrimeItems.directory_items["tasks"] = [["Wake", "Wake"], ["Middle", "Middle"], ["Doze", "Doze"]]

    do_tasker_element("tasks", RunConfig(), {"tasks_Middle"}, state=PrimeItems)

    output = written(output_lines)
    assert output.index("Doze") < output.index("Middle") < output.index("Wake")


def test_a_name_with_a_space_matches_its_anchor(output_lines: LineOut) -> None:
    """The anchor is written with the name's blanks as underscores, and matched that way."""
    PrimeItems.directory_items["profiles"] = [["Get_Up", "Get Up"]]

    do_tasker_element("profiles", RunConfig(), {"profiles_Get_Up"}, state=PrimeItems)

    assert "href=" not in written(output_lines)


def test_trailing_information_is_demoted_the_same_way(output_lines: LineOut) -> None:
    """Grand Totals sits at the very bottom, so it is the first thing a cut loses."""
    do_trailing_matters(RunConfig(display_detail_level=3), {"grand_totals"}, state=PrimeItems)

    output = written(output_lines)
    assert "href=#grand_totals" not in output
    assert "Grand Totals" in output


def test_trailing_information_keeps_its_hotlink_when_it_is_written(output_lines: LineOut) -> None:
    """A Map that fits leaves the trailing entries exactly as they were."""
    do_trailing_matters(RunConfig(display_detail_level=4), set(), state=PrimeItems)

    output = written(output_lines)
    assert "href=#grand_totals" in output
    assert "href=#unreferenced_variables" in output
