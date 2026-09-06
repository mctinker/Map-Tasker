"""MapTasker Task action parsing (action) Unit Tests

action.py reads the parts of a Task action that are not the action's own arguments: the
If conditions attached to it, the label the user typed on it, whether it is disabled,
and the app an app-action points at.

Conditions are the substance here.  A Tasker condition is stored as three numbered
fields -- <lhs>, <op>, <rhs> -- where the operator is an integer index into a table that
lives only in this file.  Nothing validates the mapping and nothing downstream could
notice it being wrong: an action displayed as "If %x = 1" when the backup says "not
equal" is a readable, plausible line that inverts what the Task actually does.

Multiple conditions are chained by <boolAnd>/<boolOr> elements that sit BETWEEN the
conditions they join, so the operator for a pair is found at a different index from the
conditions themselves -- which is the part that quietly turns an AND into an OR.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from maptasker.src import action
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems

IF_ACTION = "37"
WAIT_UNTIL = "35"


@pytest.fixture(autouse=True)
def _settings() -> None:
    """The settings and colors the formatting reads."""
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()


def _condition(lhs: str = "%a", op: str = "0", rhs: str = "5", ref: str = "c0") -> ET.Element:
    return ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Condition sr="{ref}"><lhs>{lhs}</lhs><op>{op}</op><rhs>{rhs}</rhs></Condition>',
    )


def _action_with(inner: str, code: str = IF_ACTION) -> ET.Element:
    return ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        f'<Action sr="act0"><code>{code}</code>{inner}</Action>',
    )


# ##################################################################################
# evaluate_condition -- the operator table
# ##################################################################################
@pytest.mark.parametrize(
    ("op", "operator"),
    [
        ("0", " = "),
        ("1", " NEQ "),
        ("2", " ~ "),  # matches
        ("3", " !~ "),  # does not match
        ("4", " ~R "),  # matches regex
        ("5", " !~R "),
        ("6", " < "),
        ("7", " > "),
        ("8", " = "),
        ("9", " != "),
    ],
)
def test_each_comparison_operator_is_mapped(op: str, operator: str) -> None:
    """Every operator is a small integer and every mapping is plausible for every other
    one, so a shifted table produces sensible-looking lines that say the wrong thing --
    "less than" rendered as "greater than" inverts the condition silently.
    """
    assert action.evaluate_condition(_condition(op=op)) == ("%a", operator, "5")


@pytest.mark.parametrize("op", ["12", "13"])
def test_a_set_test_has_nothing_on_its_right(op: str) -> None:
    """"is set" and "not set" test whether a variable exists at all -- there is no second
    operand, and <rhs> holds whatever was last typed into the field.  Showing it turns
    "If %x is set" into "If %x is set 5".
    """
    _, operator, second = action.evaluate_condition(_condition(op=op, rhs="stale"))
    assert "set" in operator
    assert second == ""


def test_an_empty_right_hand_side_is_handled() -> None:
    """Comparing against the empty string is a normal thing to do, and <rhs/> arrives
    with text None rather than "".
    """
    assert action.evaluate_condition(_condition(rhs="")) == ("%a", " = ", "")


def test_angle_brackets_in_a_value_are_escaped() -> None:
    """The comparison value is user text and goes straight into an HTML page.  A value
    containing < or > would otherwise be swallowed by the browser as a tag.
    """
    condition = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        "<Condition sr=\"c0\"><lhs>%a</lhs><op>0</op><rhs>&lt;b&gt;bold</rhs></Condition>",
    )
    assert action.evaluate_condition(condition)[2] == "&lt;b&gt;bold"


# ##################################################################################
# get_conditions -- chaining them together
# ##################################################################################
def test_a_single_condition_reads_as_an_if() -> None:
    conditions = f'<ConditionList sr="if">{ET.tostring(_condition()).decode()}</ConditionList>'
    result = action.get_conditions(_action_with(conditions), IF_ACTION)
    assert result == " (<em>IF</em> %a = 5)"


def test_conditions_are_joined_by_the_boolean_between_them() -> None:
    """The <boolOr> sits between the two conditions it joins, so the boolean for a pair
    is at a different index from the conditions -- see the module note.  AND where the
    backup says OR is a different Task.
    """
    conditions = (
        '<ConditionList sr="if">'
        f"{ET.tostring(_condition()).decode()}"
        "<boolOr>or</boolOr>"
        f'{ET.tostring(_condition(lhs="%b", op="1", rhs="2", ref="c1")).decode()}'
        "</ConditionList>"
    )
    result = action.get_conditions(_action_with(conditions), IF_ACTION)
    assert result == " (<em>IF</em> %a = 5 OR <em>IF</em> %b NEQ 2)"


def test_and_is_not_rendered_as_or() -> None:
    """The other half of the pair, stated separately because reading the boolean list
    with an off-by-one produces one of these two and never an error.
    """
    conditions = (
        '<ConditionList sr="if">'
        f"{ET.tostring(_condition()).decode()}"
        "<boolAnd>and</boolAnd>"
        f'{ET.tostring(_condition(lhs="%b", ref="c1")).decode()}'
        "</ConditionList>"
    )
    assert " AND " in action.get_conditions(_action_with(conditions), IF_ACTION)


def test_wait_until_is_a_loop_not_a_branch() -> None:
    """Wait Until (35) blocks until its condition becomes true -- reading it as an "IF"
    describes an action that skips instead of one that waits.
    """
    conditions = f'<ConditionList sr="if">{ET.tostring(_condition()).decode()}</ConditionList>'
    result = action.get_conditions(_action_with(conditions, WAIT_UNTIL), WAIT_UNTIL)
    assert "<em>UNTIL</em>" in result
    assert "IF" not in result


# ##################################################################################
# The label, disabled flag and remote settings that hang off an action
# ##################################################################################
def test_a_disabled_action_is_marked() -> None:
    """An <on/> element means the user switched the action off.  It is still in the Task
    and still listed, and nothing else on the line distinguishes it from one that runs.
    """
    result = action.get_label_disabled_condition(_action_with("<on/>"))
    assert 'class="disabled_action_color"' in result


def test_an_enabled_action_is_not_marked_disabled() -> None:
    assert "disabled_action_color" not in action.get_label_disabled_condition(_action_with(""))


def test_an_action_label_is_shown() -> None:
    """The label is the note the user typed on the action, and is usually the only thing
    saying why the action is there.
    """
    assert "why this is here" in action.get_label_disabled_condition(
        _action_with("<label>why this is here</label>"),
    )


def test_a_remote_action_says_so() -> None:
    """The action runs on another device.  Reading the line without that is reading it
    as something that happens on this phone.
    """
    result = action.get_label_disabled_condition(_action_with("<remoteDevice>Tablet</remoteDevice>"))
    assert "Remote Device/Execution" in result


def test_a_remote_timeout_is_shown_with_its_value() -> None:
    result = action.get_label_disabled_condition(_action_with("<remoteTimeout>30</remoteTimeout>"))
    assert "Remote Timeout (Seconds): 30" in result


def test_an_action_with_no_code_is_skipped() -> None:
    """Every action has a <code>; one without is a malformed element, and reading on
    would attribute the next action's details to it.
    """
    assert action.get_label_disabled_condition(ET.fromstring('<Action sr="act0"/>')) == ""  # noqa: S314


# ##################################################################################
# The app an app-action points at
# ##################################################################################
def test_app_details_are_labelled() -> None:
    """Three fields that are all dotted identifiers: without the labels the line is three
    indistinguishable strings.
    """
    element = _action_with("<App><appClass>com.a.B</appClass><appPkg>com.a</appPkg><label>MyApp</label></App>")
    assert action.get_app_details(element) == ("Class:com.a.B", "Package:com.a", "App:MyApp")


def test_an_action_with_no_app_returns_empty_fields() -> None:
    """Most actions are not app actions, so this is the common path -- and the caller
    concatenates the three values straight onto the line.
    """
    assert action.get_app_details(_action_with("")) == ("", "", "")


def test_several_apps_are_separated_readably() -> None:
    """An action can name more than one app, and Tasker separates them with a newline --
    which is invisible in HTML, running the names together into one string.
    """
    element = _action_with("<App><appPkg>com.a,\ncom.b</appPkg></App>")
    assert action.get_app_details(element)[1] == "Package:com.a; com.b"


def test_an_empty_app_field_gets_no_label() -> None:
    """A label with nothing after it is worse than nothing on the line."""
    assert action.replace_newline("") == ""


# ##################################################################################
# Argument discovery, for action codes not in the master table
# ##################################################################################
def test_arguments_are_found_and_ordered_by_number() -> None:
    """Arguments are matched to their meanings positionally, so document order is not
    good enough -- sr="argN" is the order, and a backup need not store them sorted.
    """
    element = ET.fromstring(  # noqa: S314  (fixture text, built in this file)
        '<Action sr="act0"><code>1</code><label>L</label>'
        '<Str sr="arg1">b</Str><Int sr="arg0" val="1"/></Action>',
    )
    arguments, types, positions = action.get_args(element, ["label", "code"])
    assert arguments == ["arg0", "arg1"]
    assert types == ["Int", "Str"]
    assert positions == ["0", "1"]


def test_an_action_with_no_arguments_finds_none() -> None:
    """Plenty of actions take none, and the caller checks the list rather than a flag."""
    element = ET.fromstring('<Action sr="act0"><code>1</code><label>L</label></Action>')  # noqa: S314
    assert action.get_args(element, ["label", "code"]) == ([], [], 0)


# ##################################################################################
# The small string helpers the argument lines are assembled with
# ##################################################################################
def test_the_trailing_comma_of_the_last_argument_is_dropped() -> None:
    """Arguments are built with a trailing ", " each so they can be concatenated, which
    leaves the last one ending in a comma with nothing after it.
    """
    assert action.drop_trailing_comma(["a, ", "b, ", "c"]) == ["a, ", "b", "c"]


def test_dropping_a_trailing_comma_from_a_list_without_one_changes_nothing() -> None:
    assert action.drop_trailing_comma(["a", "b"]) == ["a", "b"]


def test_a_set_value_is_shown_with_its_label() -> None:
    """evaluate_action_setting renders one setting: labelled when it carries a value."""
    assert action.evaluate_action_setting([True, "on", "Mode="]) == ["Mode=on"]


def test_an_unset_value_is_shown_as_nothing() -> None:
    """An empty string setting, and a flag that is off, are both left off the line
    entirely rather than shown as an empty field.
    """
    assert action.evaluate_action_setting([True, "", "Mode="], [False, "0", "Enabled"]) == ["", ""]


def test_a_flag_that_is_on_is_named() -> None:
    """A boolean setting stores "1" and has no value worth printing -- the fact that it
    is on IS the value, so the label alone is what goes on the line.
    """
    assert action.evaluate_action_setting([False, "1", "Enabled"]) == ["Enabled"]
