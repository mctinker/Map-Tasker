"""MapTasker Task Flow (control-flow) Unit Tests

taskflow.py reads nothing but the lookup tables taskerd.get_the_xml_data builds, so these
tests build those tables from a small XML fixture rather than loading a backup or standing
up the GUI -- the same arrangement, and for the same reasons, as test_healthck.py.

The fixture holds one Task per defect the check reports, and beside each one a Task that
is the sound version of it.  Both halves matter: a check that reported every Task would
pass any test that only looked at the broken ones.

The Tasks that must stay SILENT are the point of most of this file.  A control-flow check
earns its keep by being trustworthy about a Task that is fine -- a Stop guarded by a
condition, a Stop inside an If, a Goto whose label is built from a variable -- because a
false "nothing can reach this" invites somebody to delete an action that runs every day.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import taskerd, taskflow
from maptasker.src.mapjump import text_report
from maptasker.src.primitem import PrimeItems

# ##################################################################################
# The fixture, assembled from these pieces so the shape of each Task is readable.
# ##################################################################################
_IF = '<Action sr="act{n}"><code>37</code><ConditionList sr="if"><Condition sr="c0"><lhs>%a</lhs><op>0</op><rhs>1</rhs></Condition></ConditionList></Action>'
_ELSE = '<Action sr="act{n}"><code>43</code></Action>'
_END_IF = '<Action sr="act{n}"><code>38</code></Action>'
_FOR = '<Action sr="act{n}"><code>39</code><Str sr="arg0">%item</Str><Str sr="arg1">%list</Str></Action>'
_END_FOR = '<Action sr="act{n}"><code>40</code></Action>'
_FLASH = '<Action sr="act{n}"><code>548</code><Str sr="arg0">hi</Str></Action>'
_STOP = '<Action sr="act{n}"><code>137</code><Int sr="arg0" val="0"/></Action>'
_STOP_IF = '<Action sr="act{n}"><code>137</code><Int sr="arg0" val="0"/><ConditionList sr="if"><Condition sr="c0"><lhs>%b</lhs><op>0</op><rhs>2</rhs></Condition></ConditionList></Action>'
_STOP_OFF = '<Action sr="act{n}"><code>137</code><on/><Int sr="arg0" val="0"/></Action>'
_LABELLED = '<Action sr="act{n}"><code>548</code><label>{label}</label><Str sr="arg0">hi</Str></Action>'
_GOTO_LABEL = '<Action sr="act{n}"><code>135</code><Int sr="arg0" val="1"/><Int sr="arg1" val="0"/><Str sr="arg2">{label}</Str></Action>'
# The same jump, taken only sometimes.  An UNCONDITIONAL Goto strands whatever it jumps
# over -- correctly, and the check says so -- so a fixture that means "this Task is fine"
# has to use this one.
_GOTO_LABEL_IF = '<Action sr="act{n}"><code>135</code><Int sr="arg0" val="1"/><Int sr="arg1" val="0"/><Str sr="arg2">{label}</Str><ConditionList sr="if"><Condition sr="c0"><lhs>%c</lhs><op>0</op><rhs>3</rhs></Condition></ConditionList></Action>'
_GOTO_NUMBER = '<Action sr="act{n}"><code>135</code><Int sr="arg0" val="0"/><Int sr="arg1" val="{number}"/><Str sr="arg2"/></Action>'
_GOTO_TOP = (
    '<Action sr="act{n}"><code>135</code><Int sr="arg0" val="2"/><Int sr="arg1" val="0"/><Str sr="arg2"/></Action>'
)


def _task(task_id: str, name: str, *actions: str) -> str:
    """One <Task>, its actions numbered in order so map order is document order."""
    numbered = "".join(action.format(n=index, label="", number="") for index, action in enumerate(actions))
    return f'<Task sr="task{task_id}"><id>{task_id}</id><nme>{name}</nme>{numbered}</Task>'


def _numbered(*actions: str) -> str:
    """Actions already carrying their own {label}/{number}, numbered in order."""
    return "".join(action.format(n=index) for index, action in enumerate(actions))


_TASKS = "".join(
    [
        # --- sound, and must stay silent ------------------------------------------
        _task("100", "Sound", _IF, _FLASH, _ELSE, _FLASH, _END_IF, _FOR, _FLASH, _END_FOR),
        f'<Task sr="task101"><id>101</id><nme>Sound Jump</nme>{_numbered(_GOTO_LABEL_IF.replace("{label}", "here"), _FLASH, _LABELLED.replace("{label}", "here"))}</Task>',
        _task("102", "Guarded Stop", _FLASH, _STOP_IF, _FLASH),
        _task("103", "Stop Inside If", _IF, _STOP, _END_IF, _FLASH),
        _task("104", "Disabled Stop", _FLASH, _STOP_OFF, _FLASH),
        f'<Task sr="task105"><id>105</id><nme>Variable Goto</nme>{_numbered(_GOTO_LABEL.replace("{label}", "%Where"), _FLASH)}</Task>',
        f'<Task sr="task106"><id>106</id><nme>Jumped Over Stop</nme>{_numbered(_GOTO_LABEL_IF.replace("{label}", "landing"), _STOP, _LABELLED.replace("{label}", "landing"))}</Task>',
        # --- one defect each ------------------------------------------------------
        _task("200", "Open If", _FLASH, _IF, _FLASH),
        _task("201", "Open For", _FLASH, _FOR, _FLASH),
        _task("202", "Stray End If", _FLASH, _END_IF),
        _task("203", "Stray End For", _FLASH, _END_FOR),
        _task("204", "Crossed Blocks", _IF, _FLASH, _END_FOR),
        _task("205", "Lost Else", _FLASH, _ELSE, _FLASH),
        f'<Task sr="task206"><id>206</id><nme>Lost Goto</nme>{_numbered(_FLASH, _GOTO_LABEL.replace("{label}", "nowhere"))}</Task>',
        f'<Task sr="task207"><id>207</id><nme>Bad Number</nme>{_numbered(_FLASH, _GOTO_NUMBER.replace("{number}", "99"))}</Task>',
        f'<Task sr="task208"><id>208</id><nme>Twin Labels</nme>{_numbered(_GOTO_LABEL.replace("{label}", "twin"), _LABELLED.replace("{label}", "twin"), _LABELLED.replace("{label}", "twin"))}</Task>',
        _task("209", "After Stop", _FLASH, _STOP, _FLASH, _FLASH),
        _task("210", "Loose Goto", _FLASH, _GOTO_TOP),
    ],
)

# One Project owns the sound Tasks and none of the broken ones, so that a finding's
# location line has to be built two different ways -- "Project 'Flow' > Task ..." and a
# bare "Task ..." -- which is the half of the report that a wrong Project map breaks.
_FLOW_XML = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Flow</name>
    <tids>100,101,102,103,104,105,106</tids>
  </Project>
  {_TASKS}
</TaskerData>"""


def _load(xml_text: str) -> None:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file."""
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100}
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }
    # taskflow itself never touches the by-name tables, but the Health Check that folds its
    # findings in does -- and that fold is one of the things asserted here.
    tables["all_profiles_by_name"] = {
        profile["name"]: {"xml": profile["xml"], "id": key} for key, profile in tables["all_profiles"].items()
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items() if task["name"]
    }
    PrimeItems.tasker_root_elements = tables


def _findings_for(report_text: str, tag: str) -> list[str]:
    """The '[TAG]  where' lines of one tag, which is what the assertions match against."""
    return [line for line in report_text.splitlines() if line.startswith(f"[{tag}]")]


@pytest.fixture
def report() -> str:
    """The whole-configuration control-flow report for the fixture."""
    _load(_FLOW_XML)
    rows, _ = taskflow.run_task_flow_check()
    return text_report(rows)


@pytest.fixture
def counts() -> dict:
    """The severity counts for the fixture."""
    _load(_FLOW_XML)
    _, totals = taskflow.run_task_flow_check()
    return totals


def _flow(name: str) -> taskflow.Flow:
    """One Task of the fixture, analysed."""
    _load(_FLOW_XML)
    task_id = next(key for key, task in PrimeItems.tasker_root_elements["all_tasks"].items() if task["name"] == name)
    return taskflow.analyze_task_flow(task_id)


# ##################################################################################
# Blocks that do not pair up -- every one of these is an ERROR.
# ##################################################################################
def test_if_without_end_if(report: str) -> None:
    """An 'If' the Task never closes."""
    findings = _findings_for(report, "FLOW-IF-WITHOUT-END-IF")
    assert findings == ["[FLOW-IF-WITHOUT-END-IF]  Task 'Open If' (id 200) action 2"]


def test_for_without_end_for(report: str) -> None:
    """A 'For' the Task never closes -- the loop half of the same check."""
    findings = _findings_for(report, "FLOW-FOR-WITHOUT-END-FOR")
    assert findings == ["[FLOW-FOR-WITHOUT-END-FOR]  Task 'Open For' (id 201) action 2"]


def test_end_if_without_if(report: str) -> None:
    """An 'End If' with nothing open above it."""
    findings = _findings_for(report, "FLOW-END-IF-WITHOUT-IF")
    assert findings == ["[FLOW-END-IF-WITHOUT-IF]  Task 'Stray End If' (id 202) action 2"]


def test_end_for_without_for(report: str) -> None:
    """An 'End For' with nothing open above it."""
    findings = _findings_for(report, "FLOW-END-FOR-WITHOUT-FOR")
    assert findings == ["[FLOW-END-FOR-WITHOUT-FOR]  Task 'Stray End For' (id 203) action 2"]


def test_mismatched_block_is_reported_once(report: str) -> None:
    """An 'End For' closing an 'If' is one finding, not three.

    The closer is allowed to close the block it does not match, deliberately: leaving the
    If open would add an IF-WITHOUT-END-IF and then strand everything below it, when there
    is only one thing to go and fix.
    """
    assert _findings_for(report, "FLOW-MISMATCHED-BLOCK") == [
        "[FLOW-MISMATCHED-BLOCK]  Task 'Crossed Blocks' (id 204) action 3",
    ]
    assert "Crossed Blocks" not in "\n".join(_findings_for(report, "FLOW-IF-WITHOUT-END-IF"))
    assert "Crossed Blocks" not in "\n".join(_findings_for(report, "FLOW-UNREACHABLE"))


def test_else_without_if(report: str) -> None:
    """An 'Else' with no 'If' open above it."""
    assert _findings_for(report, "FLOW-ELSE-WITHOUT-IF") == [
        "[FLOW-ELSE-WITHOUT-IF]  Task 'Lost Else' (id 205) action 2",
    ]


def test_balanced_task_is_silent(report: str) -> None:
    """The Task whose blocks all pair up is not mentioned anywhere in the report."""
    assert "'Sound'" not in report


# ##################################################################################
# Gotos that land nowhere.
# ##################################################################################
def test_goto_missing_label(report: str) -> None:
    """A Goto naming a label no action in the Task carries.

    The finding names the label being jumped TO, not the Goto's own label -- they are
    different fields, and printing the wrong one leaves a report saying "jumps to label ''".
    """
    findings = _findings_for(report, "FLOW-GOTO-MISSING-LABEL")
    assert findings == ["[FLOW-GOTO-MISSING-LABEL]  Task 'Lost Goto' (id 206) action 2"]
    assert "jumps to label 'nowhere'" in report


def test_goto_bad_number(report: str) -> None:
    """A Goto to an action number the Task does not have."""
    assert _findings_for(report, "FLOW-GOTO-BAD-NUMBER") == [
        "[FLOW-GOTO-BAD-NUMBER]  Task 'Bad Number' (id 207) action 2",
    ]
    assert "jumps to action 99, and this Task has 2" in report


def test_goto_outside_its_block(report: str) -> None:
    """A 'Goto top of loop' with no 'For' around it."""
    assert _findings_for(report, "FLOW-GOTO-OUTSIDE-FOR") == [
        "[FLOW-GOTO-OUTSIDE-FOR]  Task 'Loose Goto' (id 210) action 2",
    ]


def test_duplicate_label_is_reported_at_the_goto(report: str) -> None:
    """Two actions sharing a label are reported only once a Goto names it.

    A Tasker label doubles as an action's comment, so duplicates are ordinary; what is not
    ordinary is a jump to one, where Tasker silently takes the first.
    """
    findings = _findings_for(report, "FLOW-DUPLICATE-LABEL")
    assert findings == ["[FLOW-DUPLICATE-LABEL]  Task 'Twin Labels' (id 208) action 1"]
    assert "actions 2, 3 all carry" in report


def test_goto_holding_a_variable_is_not_reported(report: str) -> None:
    """A label built from a variable is decided on the device, so it is left alone.

    The one false positive that would make the whole report untrustworthy: this Task runs
    perfectly, and nothing here can know where the jump goes.
    """
    assert "Variable Goto" not in report


# ##################################################################################
# Reachability.
# ##################################################################################
def test_unreachable_after_stop(report: str) -> None:
    """Everything below an unconditional Stop, reported as one range rather than one each."""
    findings = _findings_for(report, "FLOW-UNREACHABLE")
    assert findings == ["[FLOW-UNREACHABLE]  Task 'After Stop' (id 209) action 3"]
    assert "Nothing can reach actions 3-4" in report
    assert "action 2 ('Stop') ends the flow above it" in report


def test_conditional_stop_does_not_strand_what_follows(report: str) -> None:
    """A Stop that only sometimes fires leaves the rest of the Task reachable."""
    assert "Guarded Stop" not in report


def test_stop_inside_an_if_does_not_strand_what_follows(report: str) -> None:
    """A Stop in a branch is a Stop that may not be taken, so the End If still falls through."""
    assert "Stop Inside If" not in report


def test_disabled_stop_does_not_strand_what_follows(report: str) -> None:
    """Tasker steps straight over a disabled action, so it cannot end anything."""
    assert "Disabled Stop" not in report


def test_a_label_jumped_to_is_reachable(report: str) -> None:
    """An action below a Stop is reachable when a Goto above jumps to it."""
    assert "Jumped Over Stop" not in report


def test_unresolvable_jump_suspends_the_reachability_check() -> None:
    """A Task holding a Goto nothing can resolve gets no unreachable findings at all.

    Built as its own fixture rather than added to the shared one: the point is that the
    SAME Task shape which would otherwise be reported goes unreported once an unknown jump
    is in it, and that only reads as a test if both shapes are in front of the reader.
    """
    stranded = _load_one(
        '<Task sr="task300"><id>300</id><nme>Plain</nme>' + _numbered(_FLASH, _STOP, _FLASH) + "</Task>"
    )
    assert any(problem.tag == "FLOW-UNREACHABLE" for problem in stranded.problems)

    unknown = _load_one(
        '<Task sr="task301"><id>301</id><nme>Unknown</nme>'
        + _numbered(_GOTO_LABEL.replace("{label}", "%Where"), _STOP, _FLASH)
        + "</Task>",
    )
    assert not [problem for problem in unknown.problems if problem.tag == "FLOW-UNREACHABLE"]


def _load_one(task_xml: str) -> taskflow.Flow:
    """Analyse a configuration holding exactly one Task."""
    _load(f'<TaskerData sr="" dvi="1" tv="6.3.13">{task_xml}</TaskerData>')
    task_id = next(iter(PrimeItems.tasker_root_elements["all_tasks"]))
    return taskflow.analyze_task_flow(task_id)


# ##################################################################################
# The report itself.
# ##################################################################################
def test_counts_match_the_findings(report: str, counts: dict) -> None:
    """The header's tally is the number of findings actually printed."""
    printed = [line for line in report.splitlines() if line.startswith("[FLOW-")]
    assert counts[taskflow.ERROR] + counts[taskflow.WARNING] == len(printed)
    assert f"{counts[taskflow.ERROR]} Errors, {counts[taskflow.WARNING]} Warnings" in report


def test_findings_are_clickable(report: str) -> None:
    """Every finding's location line carries the Target the Map view is asked for.

    The report is rendered twice -- saved as text, shown as clickable HTML -- and a finding
    with no Target is one the user cannot follow.
    """
    _load(_FLOW_XML)
    rows, _ = taskflow.run_task_flow_check()
    located = [row for row in rows if row.text.startswith("[FLOW-")]
    assert located
    assert all(row.target is not None and row.target.action for row in located)
    assert report  # the fixture's text form, asserted on by every other test here


def test_clean_configuration_says_so() -> None:
    """A configuration with nothing wrong reads as an answer, not as an empty report."""
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13">' + _task("400", "Fine", _IF, _FLASH, _END_IF) + "</TaskerData>",
    )
    rows, totals = taskflow.run_task_flow_check()
    assert totals == {taskflow.ERROR: 0, taskflow.WARNING: 0}
    assert "Nothing to report" in text_report(rows)


def test_report_is_written_to_a_file(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """The saved file holds the same text the report renders."""
    _load(_FLOW_XML)
    monkeypatch.chdir(tmp_path)
    rows, _ = taskflow.run_task_flow_check()
    file_name = taskflow.write_task_flow_report(rows)
    assert file_name.startswith("MapTasker_TaskFlow")
    with open(os.path.join(os.getcwd(), file_name), encoding="utf-8") as written:
        assert written.read() == text_report(rows)


# ##################################################################################
# The flowchart.
# ##################################################################################
def test_flowchart_indents_what_is_inside_a_block() -> None:
    """A block's contents are drawn one column in, and the block's own lines are not.

    Indentation is the whole of what the chart adds over the Map's flat list, so it is
    worth asserting rather than eyeballing.
    """
    flow = _flow("Sound")
    assert flow.depth == [0, 1, 0, 1, 0, 0, 1, 0]


def test_flowchart_draws_an_arrow_from_a_goto_to_its_target() -> None:
    """The jump gutter joins the Goto's line to the line it lands on, and nothing else."""
    chart = text_report(taskflow.flowchart(_flow("Sound Jump"))).splitlines()
    goto_line = next(line for line in chart if "Goto" in line and "label 'here'" in line)
    landing = next(line for line in chart if "label: here" in line)
    assert goto_line.rstrip().endswith(("╮", "╯"))  # the jump leaves this line for the gutter
    assert "◄" in landing  # and arrives, pointing back into the text


def test_flowchart_marks_what_cannot_be_reached() -> None:
    """An action nothing can arrive at is said so on its own line, not only in the report."""
    chart = text_report(taskflow.flowchart(_flow("After Stop")))
    assert chart.count("[not reached]") == 2


def test_flowchart_lines_point_at_their_own_action() -> None:
    """Clicking a line of the chart goes to that action in the Map, not to the Task.

    The target hangs off a PIECE of the line rather than the whole of it -- only the
    action's text is clickable, so that the spine drawn to its left and the jump gutter
    drawn to its right stay plain (see _chart_row).
    """
    rows = taskflow.flowchart(_flow("Sound"))
    targets = [target for row in rows for _, target in row.pieces if target is not None and target.action]
    assert [target.action for target in targets] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_flowchart_leaves_the_drawing_alone() -> None:
    """The spine and the number column are not part of what a click is offered on."""
    rows = taskflow.flowchart(_flow("Sound"))
    clickable = [row for row in rows if any(target and target.action for _, target in row.pieces)]
    assert clickable
    for row in clickable:
        drawing, action = row.pieces[0]
        assert action is None
        # Drawing and an action number, and no word of the action itself: the clickable
        # piece starts where the text does.
        assert not any(character.isalpha() for character in drawing)
        assert row.text.startswith(drawing)


def test_flowchart_repeats_the_tasks_own_problems() -> None:
    """A chart drawn for a broken Task says what is broken about it, above the drawing."""
    chart = text_report(taskflow.flowchart(_flow("Open If")))
    assert "[FLOW-IF-WITHOUT-END-IF]" in chart
    assert chart.index("[FLOW-IF-WITHOUT-END-IF]") < chart.index("start of Task")


def test_flowchart_of_a_sound_task_says_so() -> None:
    """A Task with nothing wrong gets a chart and a sentence saying there is nothing wrong."""
    chart = text_report(taskflow.flowchart(_flow("Sound")))
    assert "No control-flow problems found in this Task." in chart
    assert "start of Task" in chart


# ##################################################################################
# The Health Check carries these too.
# ##################################################################################
def test_health_check_folds_in_the_control_flow_findings() -> None:
    """A user who never presses "Task Flow" is still told about a block that never closes.

    healthck folds these in the way it folds in the variable cross-reference's suspects.
    The tags travel unchanged, which is what lets one report be searched for FLOW- and
    VAR- alike.
    """
    from maptasker.src.healthck import run_health_check  # noqa: PLC0415  (kept out of this module's imports)

    _load(_FLOW_XML)
    rows, _ = run_health_check()
    health = text_report(rows)
    assert "[FLOW-IF-WITHOUT-END-IF]" in health
    assert "[FLOW-GOTO-MISSING-LABEL]" in health
