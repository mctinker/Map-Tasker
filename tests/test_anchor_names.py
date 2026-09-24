"""A name the user chose goes into an anchor without breaking the markup around it.

The Map turns the name of a Project, Profile, Task or Scene into the id of an anchor and
into the hyperlink that looks for it.  A name is the user's own text, and Tasker users
really do write "System >> Say Response"; an unnamed Task is named after its first
action, which is regularly something like "If %new_val > %limit".

Written into an attribute as it stands, that ">" ends the tag where it sits.  The rest of
the name and its closing quote are then drawn in the Map as text, and every line after it
is laid out as though that tag were still open -- which is what was reported in Project
'Advanced Auto Brightness 3.0', where 22 anchors in one configuration were affected.

So each of the three places that builds one of these anchors is checked here, and so is
the thing that makes the fix worth having: that the hyperlink and the anchor it looks for
still say the same thing afterwards.
"""

from __future__ import annotations

import pytest
from maptasker.src.dirout import add_directory_item
from maptasker.src.maputils import fix_hyperlink_name
from maptasker.src.primitem import PrimeItems
from maptasker.src.proclist import add_task_hyperlink

# Real shapes, both taken from the configuration that turned this up.
NAME_WITH_ANGLE_BRACKET = "System >> Say Response"
UNNAMED_TASK_NAME = "If %new_val > %aab_zone1end.922 (Unnamed)"


def written(output_lines: object) -> str:
    """Everything put out so far, as one piece of html."""
    return "".join(line[1] if isinstance(line, list) else str(line) for line in output_lines.output_lines)


@pytest.fixture(autouse=True)
def _runtime(monkeypatch) -> None:
    """Enough of a run for the two writers below, and the directory turned on."""
    from maptasker.src.colrmode import set_color_mode  # noqa: PLC0415
    from maptasker.src.initparg import initialize_runtime_arguments  # noqa: PLC0415
    from maptasker.src.lineout import LineOut  # noqa: PLC0415

    # The real set of runtime arguments, with only what these tests care about changed:
    # picking keys by hand here just means chasing a KeyError for each one the writers
    # happen to read.
    arguments = initialize_runtime_arguments()
    arguments.update({"directory": True, "list_unnamed_items": True})
    monkeypatch.setattr(PrimeItems, "program_arguments", arguments)
    monkeypatch.setattr(PrimeItems, "colors_to_use", set_color_mode("dark"))
    monkeypatch.setattr(PrimeItems, "output_lines", LineOut())
    monkeypatch.setattr(
        PrimeItems,
        "directory_items",
        {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []},
    )


def test_a_task_name_with_an_angle_bracket_does_not_end_its_own_tag() -> None:
    """The reported fault: the id attribute was cut short and the rest became text."""
    add_task_hyperlink(NAME_WITH_ANGLE_BRACKET, display_name=True, blank="&nbsp;")

    html = written(PrimeItems.output_lines)
    # Where the browser would decide the tag ends: at the first ">" after it opens.
    opening_tag = html[html.index("<a id=") : html.index(">", html.index("<a id=")) + 1]

    assert opening_tag == '<a id="tasks_System_&gt;&gt;_Say_Response">', (
        f"the tag the browser sees is not the whole anchor: {opening_tag}"
    )


def test_an_unnamed_task_named_after_an_if_is_safe_too() -> None:
    """Unnamed Tasks take the text of their first action, comparisons and all."""
    add_task_hyperlink(UNNAMED_TASK_NAME, display_name=True, blank="&nbsp;")

    html = written(PrimeItems.output_lines)
    assert 'id="tasks_If_%new_val_&gt;_%aab_zone1end.922_(Unnamed)"' in html


def test_the_directory_anchor_is_escaped() -> None:
    """The directory builds the anchor AND the hyperlink from one name."""
    add_directory_item("tasks", NAME_WITH_ANGLE_BRACKET)

    assert PrimeItems.directory_items["current_item"] == "tasks_System_&gt;&gt;_Say_Response"
    assert PrimeItems.directory_items["tasks"][0][0] == "System_&gt;&gt;_Say_Response"


def test_the_hyperlink_and_the_anchor_still_agree() -> None:
    """The point of the whole thing: the link has to find what it points at.

    The directory's hyperlink is built from the name held in directory_items, and the
    anchor from the name written beside it, so the two have to survive escaping alike --
    a browser reads "&gt;" in both as the same character.
    """
    add_directory_item("tasks", NAME_WITH_ANGLE_BRACKET)
    add_task_hyperlink(NAME_WITH_ANGLE_BRACKET, display_name=True, blank="&nbsp;")

    href_name = PrimeItems.directory_items["tasks"][0][0]
    assert f'id="tasks_{href_name}"' in written(PrimeItems.output_lines)


def test_a_name_with_nothing_to_escape_is_left_as_it_was() -> None:
    """Spaces still become underscores, and nothing else is touched."""
    add_task_hyperlink("Wake Up", display_name=True, blank="&nbsp;")

    assert 'id="tasks_Wake_Up"' in written(PrimeItems.output_lines)


def test_the_helper_escapes_both_brackets() -> None:
    """Named directly, since three callers now depend on exactly this."""
    assert fix_hyperlink_name("a <b> c") == "a_&lt;b&gt;_c"


def test_a_name_with_a_double_quote_does_not_end_its_own_attribute() -> None:
    """An unnamed Task named after an Anchor action carries the action's quoted text."""
    add_task_hyperlink('Anchor "NOTE: read me".705 (Unnamed)', display_name=True, blank="&nbsp;")

    html = written(PrimeItems.output_lines)
    opening_tag = html[html.index("<a id=") : html.index(">", html.index("<a id=")) + 1]

    assert opening_tag == '<a id="tasks_Anchor_&quot;NOTE:_read_me&quot;.705_(Unnamed)">', (
        f"the tag the browser sees is not the whole anchor: {opening_tag}"
    )


# ##################################################################################
# The 'Tasks With Too Many Actions' list at the foot of the Map.
# ##################################################################################
def test_a_warning_points_at_the_task_by_id(monkeypatch) -> None:
    """Those hotlinks go to the anchor every Task has, not to the one only some have.

    A named Task gets a name-keyed anchor from the directory; an unnamed one does not,
    because the directory leaves unnamed items out -- so a warning about an unnamed Task
    used to point at an anchor that was never written.  The id-keyed anchor is there
    whatever the settings.
    """
    from maptasker.src.maputils import display_task_warnings  # noqa: PLC0415

    PrimeItems.program_arguments.task_action_warning_limit = 28
    monkeypatch.setattr(
        PrimeItems,
        "task_action_warnings",
        {
            "Wake Up": {"count": 40, "id": "118"},
            "If %new_val > %limit.922 (Unnamed)": {"count": 33, "id": "922"},
        },
    )

    display_task_warnings()

    html = written(PrimeItems.output_lines)
    assert "href=#mt-task-118" in html, "a named Task's warning does not point at its own anchor"
    assert "href=#mt-task-922" in html, "an unnamed Task's warning does not point at its own anchor"
    assert "href=#tasks_" not in html, "a warning still points at the directory's name-keyed anchor"
