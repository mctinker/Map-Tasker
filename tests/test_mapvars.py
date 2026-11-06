"""MapTasker Variable Manager (mapvars) Unit Tests

mapvars is the table of global variables and the plans that change one.  What it counts is varxref's, so the counts
are not retested here; what is tested is what mapvars adds: which variables are in the table and which are marked,
what type a value looks like, and that each change -- rename, value, delete -- is a plan that previews, applies as
one Undo, and says no when it should.

Each mark is here with the variable that earns it and the one that looks similar and does not: a variable that is
set and also read, a declared one that something sets, a local that is not a global at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.gui import livevars
from maptasker.src.mapops import maprefac, mapvars

from tests.shared_fixtures import _load_local

pytestmark = pytest.mark.usefixtures("_runtime")


def _act(code: str, *arguments: str) -> str:
    return f'<Action sr="act{{}}" ve="7"><code>{code}</code>{"".join(arguments)}</Action>'


def _s(index: int, value: str) -> str:
    return f'<Str sr="arg{index}" ve="3">{value}</Str>'


def _i(index: int, value: int) -> str:
    return f'<Int sr="arg{index}" val="{value}"/>'


def set_(name: str, value: str) -> str:
    return _act("547", _s(0, name), _s(1, value), _i(2, 0), _i(3, 0), _i(4, 0), _i(5, 3))


def flash(text: str) -> str:
    return _act("548", _s(0, text), _i(1, 0), _i(2, 0))


def _task(task_id: int, name: str, *actions: str) -> str:
    numbered = "".join(action.replace("act{}", f"act{index}") for index, action in enumerate(actions))
    return f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme>{numbered}</Task>'


def _variable(number: int, name: str, value: str) -> str:
    return f'<Variable sr="vars{number}"><n>{name}</n><v>{value}</v></Variable>'


# The configuration:
#   %Mode     declared, set by Writer and read by Reader         -> no mark
#   %Count    declared 12, only ever read by Reader              -> not marked: it is declared, so it has a value
#   %Spare    declared, used nowhere                              -> UNUSED
#   %Orphan   not declared, set by Writer, never read            -> SET-NEVER-READ
#   %Wanted   not declared, read by Reader, never set            -> READ-NEVER-SET
#   %Logged   declared, set by Writer, never read                -> SET-NEVER-READ (and declared)
#   %temp     lower case: a local, not in the table
_XML = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  {_variable(0, "%Mode", "night")}
  {_variable(1, "%Count", "12")}
  {_variable(2, "%Flag", "true")}
  {_variable(3, "%Json", '{"a": 1}')}
  {_variable(4, "%Spare", "x")}
  {_variable(5, "%Logged", "yes")}
  {
    _task(
        1,
        "Writer",
        set_("%Mode", "day"),
        set_("%Orphan", "1"),
        set_("%Logged", "no"),
        set_("%temp", "3"),
    )
}
  {_task(2, "Reader", flash("Mode is %Mode"), flash("Count %Count"), flash("Missing %Wanted"), flash("t %temp"))}
</TaskerData>"""


@pytest.fixture
def rows(tmp_path: Path) -> dict[str, mapvars.Row]:
    _load_local(tmp_path, _XML)
    return {row.name: row for row in mapvars.build_rows(PrimeItems)}


# ##################################################################################
# Which variables are in the table, and the marks
# ##################################################################################
def test_every_global_is_in_the_table_declared_or_not(rows: dict[str, mapvars.Row]) -> None:
    assert {"%Mode", "%Count", "%Flag", "%Json", "%Spare", "%Logged", "%Orphan", "%Wanted"} <= set(rows)


def test_a_local_is_not_a_global(rows: dict[str, mapvars.Row]) -> None:
    assert "%temp" not in rows


def test_the_table_is_sorted_by_name_ignoring_case(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    names = [row.name for row in mapvars.build_rows(PrimeItems)]

    assert names == sorted(names, key=str.casefold)


def test_a_variable_set_and_read_is_not_marked(rows: dict[str, mapvars.Row]) -> None:
    assert rows["%Mode"].flag == ""
    assert (rows["%Mode"].sets, rows["%Mode"].reads) == (1, 1)


def test_set_never_read(rows: dict[str, mapvars.Row]) -> None:
    assert rows["%Orphan"].flag == mapvars.NEVER_READ


def test_a_declared_variable_set_and_never_read_is_marked_too(rows: dict[str, mapvars.Row]) -> None:
    """varxref leaves these out of its own list because they are in the Variables tab; here they are marked."""
    assert rows["%Logged"].declared
    assert rows["%Logged"].flag == mapvars.NEVER_READ


def test_read_never_set(rows: dict[str, mapvars.Row]) -> None:
    assert rows["%Wanted"].flag == mapvars.NEVER_SET


def test_a_declared_variable_that_is_only_read_is_not_read_never_set(rows: dict[str, mapvars.Row]) -> None:
    """It holds a value in the Variables tab, which is a perfectly good way for a variable to get one."""
    assert rows["%Count"].flag == ""


def test_declared_and_used_nowhere_is_unused(rows: dict[str, mapvars.Row]) -> None:
    assert rows["%Spare"].flag == mapvars.UNUSED


def test_the_marks_are_counted(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    counts = mapvars.flag_counts(mapvars.build_rows(PrimeItems))

    assert counts[mapvars.NEVER_READ] == 2
    assert counts[mapvars.NEVER_SET] == 1
    assert counts[mapvars.UNUSED] >= 1


def test_where_a_variable_is_used_is_each_place_once(rows: dict[str, mapvars.Row]) -> None:
    places = rows["%Mode"].uses()

    assert [target.name for target in places] == ["Writer", "Reader"]


def test_the_value_is_what_the_variables_tab_holds(rows: dict[str, mapvars.Row]) -> None:
    assert rows["%Mode"].value == "night"
    assert rows["%Orphan"].value == ""
    assert not rows["%Orphan"].declared


# ##################################################################################
# What the phone says
# ##################################################################################
def test_without_a_phone_nothing_is_said_about_it(rows: dict[str, mapvars.Row]) -> None:
    assert rows["%Mode"].live is None
    assert not rows["%Mode"].differs


def test_with_a_phone_each_variable_is_present_or_absent_and_may_differ(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    live = livevars.LiveValues("x:1", {"%Mode": "evening", "%Count": "12", "%Blank": ""})

    found = {row.name: row for row in mapvars.build_rows(PrimeItems, live)}

    assert found["%Mode"].on_device
    assert found["%Mode"].live == "evening"
    assert found["%Mode"].differs, "the phone holds a different value from the file"
    assert not found["%Count"].differs
    assert not found["%Spare"].on_device
    assert found["%Spare"].live == ""
    assert not found["%Spare"].differs


# ##################################################################################
# Types
# ##################################################################################
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", mapvars.EMPTY),
        ("   ", mapvars.EMPTY),
        ("12", mapvars.NUMBER),
        ("-3.5", mapvars.NUMBER),
        ("1e3", mapvars.NUMBER),
        ("true", mapvars.TRUE_FALSE),
        ("FALSE", mapvars.TRUE_FALSE),
        ('{"a": 1}', mapvars.JSON),
        ("[1, 2]", mapvars.JSON),
        ("{not json", mapvars.TEXT),
        ("twelve", mapvars.TEXT),
        ("12 apples", mapvars.TEXT),
    ],
)
def test_what_a_value_looks_like(value: str, expected: str) -> None:
    assert mapvars.infer_type(value) == expected


@pytest.mark.parametrize(
    ("value_type", "value", "ok"),
    [
        (mapvars.TEXT, "anything at all", True),
        (mapvars.NUMBER, " 42 ", True),
        (mapvars.NUMBER, "twelve", False),
        (mapvars.TRUE_FALSE, "True", True),
        (mapvars.TRUE_FALSE, "yes", False),
        (mapvars.JSON, '{"a": 1}', True),
        (mapvars.JSON, "plain", False),
        (mapvars.JSON, "42", False),
    ],
)
def test_a_value_is_checked_against_the_type_chosen(value_type: str, value: str, ok: bool) -> None:
    assert (mapvars.check_value(value_type, value) == "") is ok


def test_a_typed_value_is_tidied_and_text_is_left_alone() -> None:
    assert mapvars.tidy_value(mapvars.TRUE_FALSE, " True ") == "true"
    assert mapvars.tidy_value(mapvars.NUMBER, " 7 ") == "7"
    assert mapvars.tidy_value(mapvars.TEXT, "  keep my spaces ") == "  keep my spaces "


# ##################################################################################
# Changes
# ##################################################################################
def _held(name: str) -> str | None:
    root = PrimeItems.xml_root
    assert root is not None
    for element in root.findall("Variable"):
        if (element.findtext("n") or "") == name:
            return element.findtext("v") or ""
    return None


def test_a_value_is_changed_and_one_undo_puts_it_back(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_set_value("%Mode", "evening", mapvars.TEXT, PrimeItems)
    assert plan.can_apply
    assert "evening" in plan.steps[0].text
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    assert _held("%Mode") == "evening"
    assert sessundo.undo(PrimeItems)[0]
    assert _held("%Mode") == "night"


def test_a_value_of_the_wrong_type_is_blocked_and_nothing_changes(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_set_value("%Count", "twelve", mapvars.NUMBER, PrimeItems)

    assert plan.is_blocked
    assert plan.blocks[0].reason == "WRONG-TYPE"
    assert not maprefac.apply(plan, state=PrimeItems)[0]
    assert _held("%Count") == "12"


def test_a_global_the_tab_does_not_hold_is_added_when_given_a_value(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_set_value("%Orphan", "7", mapvars.NUMBER, PrimeItems)
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    assert _held("%Orphan") == "7"
    assert "Add %Orphan" in plan.steps[0].text
    assert {row.name: row for row in mapvars.build_rows(PrimeItems)}["%Orphan"].declared


def test_a_name_typed_without_its_percent_is_the_same_variable(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    done, _errors = maprefac.apply(mapvars.plan_set_value("Mode", "dusk", mapvars.TEXT, PrimeItems), state=PrimeItems)

    assert done
    assert _held("%Mode") == "dusk"


def test_a_true_false_value_is_written_in_lower_case(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    maprefac.apply(mapvars.plan_set_value("%Flag", " FALSE ", mapvars.TRUE_FALSE, PrimeItems), state=PrimeItems)

    assert _held("%Flag") == "false"


def test_a_declared_variable_is_deleted_and_one_undo_puts_it_back(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Spare"], PrimeItems)
    assert plan.can_apply
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    assert _held("%Spare") is None
    assert sessundo.undo(PrimeItems)[0]
    assert _held("%Spare") == "x"


def test_deleting_a_variable_that_is_used_warns_and_leaves_the_actions_alone(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Mode"], PrimeItems)

    assert plan.can_apply
    assert any("set in 1 place and read in 1 place" in warning for warning in plan.warnings)
    maprefac.apply(plan, state=PrimeItems)
    assert _held("%Mode") is None
    assert {row.name: row for row in mapvars.build_rows(PrimeItems)}["%Mode"].sets == 1, "the Task still sets it"


def test_a_variable_the_tab_does_not_hold_cannot_be_deleted(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Orphan"], PrimeItems)

    assert plan.is_blocked
    assert plan.blocks[0].reason == "NOT-DECLARED"


def test_a_rename_rewrites_the_uses_and_the_tab_entry(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_rename("%Mode", "%Phase", PrimeItems)
    assert plan.can_apply, [block.explanation for block in plan.blocks]
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    assert _held("%Phase") == "night"
    assert _held("%Mode") is None
    names = {row.name: row for row in mapvars.build_rows(PrimeItems)}
    assert "%Mode" not in names
    assert (names["%Phase"].sets, names["%Phase"].reads) == (1, 1)


def test_a_rename_onto_a_name_already_taken_is_blocked(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_rename("%Mode", "%Count", PrimeItems)

    assert plan.is_blocked


def test_a_plan_left_open_while_the_file_is_reloaded_is_refused(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)
    plan = mapvars.plan_set_value("%Mode", "evening", mapvars.TEXT, PrimeItems)

    _load_local(tmp_path, _XML)

    assert not maprefac.apply(plan, state=PrimeItems)[0]


# ##################################################################################
# Deleting several at once
# ##################################################################################
def test_several_entries_are_deleted_as_one_change_and_one_undo_puts_them_all_back(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Spare", "%Flag", "%Json"], PrimeItems)
    assert plan.can_apply
    assert plan.what == "Delete 3 variables from the Variables tab"
    assert len(plan.steps) == 3
    done, errors = maprefac.apply(plan, state=PrimeItems)

    assert done, errors
    assert [_held(name) for name in ("%Spare", "%Flag", "%Json")] == [None, None, None]
    assert _held("%Mode") == "night", "what was not chosen is left alone"
    assert sessundo.undo(PrimeItems)[0]
    assert [_held(name) for name in ("%Spare", "%Flag", "%Json")] == ["x", "true", '{"a": 1}']


def test_a_name_the_tab_does_not_hold_is_left_out_and_said_so(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Spare", "%Orphan", "%Wanted"], PrimeItems)

    assert plan.can_apply
    assert len(plan.steps) == 1
    assert any("2 of the chosen variables (%Orphan, %Wanted) are not in the Variables tab" in w for w in plan.warnings)
    maprefac.apply(plan, state=PrimeItems)
    assert _held("%Spare") is None


def test_none_of_them_held_is_a_block(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Orphan", "%Wanted"], PrimeItems)

    assert plan.is_blocked
    assert plan.blocks[0].reason == "NOT-DECLARED"
    assert "None of these variables is in the Variables tab" in plan.blocks[0].explanation


def test_the_ones_still_used_are_counted_in_one_warning(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Spare", "%Mode", "%Count"], PrimeItems)

    assert any("2 of these variables (%Mode, %Count) are still set or read by actions" in w for w in plan.warnings)


def test_the_same_name_twice_is_one_deletion(tmp_path: Path) -> None:
    _load_local(tmp_path, _XML)

    plan = mapvars.plan_delete_many(["%Spare", "Spare", "%Spare"], PrimeItems)

    assert len(plan.steps) == 1
    assert plan.what == "Delete %Spare from the Variables tab"
