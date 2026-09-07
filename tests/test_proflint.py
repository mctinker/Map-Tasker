"""MapTasker Profile Conflict and Battery Lint Unit Tests

Every check in proflint.py is a pure function over the lookup tables
taskerd.get_the_xml_data builds, so these tests build those tables from a small XML
fixture rather than loading a backup or standing up the GUI -- the same way
tests/test_healthck.py and tests/test_taskflow.py do.

The fixture (_LINT_XML) carries one instance of every problem proflint reports, and
beside each one the innocent version of the same shape: two Profiles that share a
trigger and agree, a Wait that is not in a loop, a Run Shell whose timeout is set, a
Task that waits but has collision handling.  Both halves matter.  Every rule in this
module is a judgement about behaviour rather than a broken reference, so the way it
fails is by firing on a configuration that is perfectly reasonable -- and only the
negative half of each test can catch that.

The lint is asserted through proflint.lint_problems() rather than through the health
check report, so a failure names the rule rather than a line of formatted text.  One
test at the end goes the other way and checks that healthck really does fold these in,
because a rule that works and is never printed is not a feature.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import proflint, taskerd
from maptasker.src.healthck import run_health_check
from maptasker.src.mapjump import text_report
from maptasker.src.primitem import PrimeItems

# One Project holding, for each rule, the offending object and the sound one beside it.
#
#   Profile 10 'Lights On'   State 'Display State' -- same trigger as Profile 11.  Entry
#                            Task 30 sets WiFi On.
#   Profile 11 'Lights Off'  the same State.  Entry Task 31 sets WiFi Off -> PROFILE-CONFLICT
#   Profile 12 'Echo A'      Event 208 -- same trigger as Profile 13.  Entry Task 32 sets
#   Profile 13 'Echo B'      WiFi On, and so does Task 33: agreeing, so the pair is
#                            PROFILE-DUPLICATE-TRIGGER and NOT a conflict.
#   Profile 14 'Silent'      no condition at all -> PROFILE-NEVER-FIRES
#   Profile 15 'Both Ways'   the same State twice, one of them inverted -> PROFILE-NEVER-FIRES
#   Profile 16 'Two Values'  a State whose ConditionList ANDs %Mode = a with %Mode = b
#                            -> PROFILE-NEVER-FIRES
#   Profile 17 'Or Values'   the identical pair joined with Or instead -> NOT reported
#   Profile 18 'Leap'        Day: the 31st, of February -> PROFILE-NEVER-FIRES
#   Profile 19 'Near Wifi'   State 'Wifi Near' -> ALWAYS-ON-MONITOR
#   Profile 20 'Where'       a Loc condition -> ALWAYS-ON-MONITOR
#   Profile 21 'Every 2'     Time repeating every 2 minutes -> FREQUENT-TRIGGER
#   Profile 22 'Every 20'    Time repeating every 20 minutes -> NOT reported
#   Profile 23 'Off Duty'    disabled, and watches 'Wifi Near' -> NOT reported: a Profile
#                            that is switched off is not monitoring anything
#   Profile 24 'Conditional' same trigger as Profile 25, but its Task sets WiFi inside an
#   Profile 25 'Unconditional'  If -> a duplicate trigger, NOT a conflict
#   Profile 26 'Poller'      runs Task 36, which is the polling/collision case
#   Task 30/31               the conflicting pair above
#   Task 34 'Shell'          two Run Shell actions: one with no timeout -> NO-TIMEOUT,
#                            one with a timeout of 10 -> NOT reported
#   Task 35 'Straight Wait'  a Wait outside any loop, and a disabled Wait inside a For
#                            -> neither is a POLLING-LOOP
#   Task 36 'Spin'           a Wait of 2 seconds inside a For -> POLLING-LOOP, and it is
#                            run by Profile 26 with no <rty> -> MISSING-COLLISION
#   Task 37 'Goto Spin'      a Wait and a backwards Goto over it -> POLLING-LOOP.  Nothing
#                            triggers it, so no MISSING-COLLISION.
#   Task 38 'Careful'        the same loop as Task 36, run by Profile 26's exit link, but
#                            with <rty>1</rty> -> NOT a MISSING-COLLISION
#   Task 39 'Tracker'        turns GPS on, and nothing in the file turns it off
#                            -> ALWAYS-ON-MONITOR.  Its second action is a Get Location
#                            with 'Keep Tracking' ticked AND no timeout, which is one
#                            action that has to raise two different findings.
_LINT_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26</pids>
    <tids>30,31,32,33,34,35,36,37,38,39</tids>
  </Project>
  <Profile sr="prof10" ve="2">
    <id>10</id><nme>Lights On</nme><mid0>30</mid0>
    <State sr="con0" ve="2"><code>123</code></State>
  </Profile>
  <Profile sr="prof11" ve="2">
    <id>11</id><nme>Lights Off</nme><mid0>31</mid0>
    <State sr="con0" ve="2"><code>123</code></State>
  </Profile>
  <Profile sr="prof12" ve="2">
    <id>12</id><nme>Echo A</nme><mid0>32</mid0>
    <Event sr="con0" ve="2"><code>208</code><pri>1</pri></Event>
  </Profile>
  <Profile sr="prof13" ve="2">
    <id>13</id><nme>Echo B</nme><mid0>33</mid0>
    <Event sr="con0" ve="2"><code>208</code><pri>7</pri></Event>
  </Profile>
  <Profile sr="prof14" ve="2">
    <id>14</id><nme>Silent</nme><mid0>32</mid0>
  </Profile>
  <Profile sr="prof15" ve="2">
    <id>15</id><nme>Both Ways</nme><mid0>32</mid0>
    <State sr="con0" ve="2"><code>110</code></State>
    <State sr="con1" ve="2"><code>110</code><pin>true</pin></State>
  </Profile>
  <Profile sr="prof16" ve="2">
    <id>16</id><nme>Two Values</nme><mid0>32</mid0>
    <State sr="con0" ve="2">
      <code>165</code>
      <ConditionList sr="if">
        <bool0>And</bool0>
        <Condition sr="c0" ve="3"><lhs>%Mode</lhs><op>2</op><rhs>a</rhs></Condition>
        <Condition sr="c1" ve="3"><lhs>%Mode</lhs><op>2</op><rhs>b</rhs></Condition>
      </ConditionList>
    </State>
  </Profile>
  <Profile sr="prof17" ve="2">
    <id>17</id><nme>Or Values</nme><mid0>32</mid0>
    <State sr="con0" ve="2">
      <code>165</code>
      <ConditionList sr="if">
        <bool0>Or</bool0>
        <Condition sr="c0" ve="3"><lhs>%Mode</lhs><op>2</op><rhs>a</rhs></Condition>
        <Condition sr="c1" ve="3"><lhs>%Mode</lhs><op>2</op><rhs>b</rhs></Condition>
      </ConditionList>
    </State>
  </Profile>
  <Profile sr="prof18" ve="2">
    <id>18</id><nme>Leap</nme><mid0>32</mid0>
    <Day sr="con0"><mday0>31</mday0><mnth0>1</mnth0></Day>
  </Profile>
  <Profile sr="prof19" ve="2">
    <id>19</id><nme>Near Wifi</nme><mid0>32</mid0>
    <State sr="con0" ve="2"><code>170</code></State>
  </Profile>
  <Profile sr="prof20" ve="2">
    <id>20</id><nme>Where</nme><mid0>32</mid0>
    <Loc sr="con0" ve="2"><lat>51.5</lat><long>-0.12</long><rad>150</rad></Loc>
  </Profile>
  <Profile sr="prof21" ve="2">
    <id>21</id><nme>Every 2</nme><mid0>32</mid0>
    <Time sr="con0"><fh>-1</fh><fm>-1</fm><rep>2</rep><repval>2</repval><th>-1</th><tm>-1</tm></Time>
  </Profile>
  <Profile sr="prof22" ve="2">
    <id>22</id><nme>Every 20</nme><mid0>32</mid0>
    <Time sr="con0"><fh>-1</fh><fm>-1</fm><rep>2</rep><repval>20</repval><th>-1</th><tm>-1</tm></Time>
  </Profile>
  <Profile sr="prof23" ve="2">
    <id>23</id><nme>Off Duty</nme><limit>true</limit><mid0>32</mid0>
    <State sr="con0" ve="2"><code>170</code></State>
  </Profile>
  <Profile sr="prof24" ve="2">
    <id>24</id><nme>Conditional</nme><mid0>40</mid0>
    <State sr="con0" ve="2"><code>140</code></State>
  </Profile>
  <Profile sr="prof25" ve="2">
    <id>25</id><nme>Unconditional</nme><mid0>41</mid0>
    <State sr="con0" ve="2"><code>140</code></State>
  </Profile>
  <Profile sr="prof26" ve="2">
    <id>26</id><nme>Poller</nme><mid0>36</mid0><mid1>38</mid1>
    <Event sr="con0" ve="2"><code>461</code></Event>
  </Profile>
  <Task sr="task30"><id>30</id><nme>Wifi On</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="1"/></Action>
  </Task>
  <Task sr="task31"><id>31</id><nme>Wifi Off</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="0"/></Action>
  </Task>
  <Task sr="task32"><id>32</id><nme>Agree A</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="1"/></Action>
  </Task>
  <Task sr="task33"><id>33</id><nme>Agree B</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="1"/></Action>
  </Task>
  <Task sr="task34"><id>34</id><nme>Shell</nme>
    <Action sr="act0" ve="7"><code>123</code><Str sr="arg0">ls</Str><Int sr="arg1" val="0"/></Action>
    <Action sr="act1" ve="7"><code>123</code><Str sr="arg0">ls</Str><Int sr="arg1" val="10"/></Action>
  </Task>
  <Task sr="task35"><id>35</id><nme>Straight Wait</nme>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action>
    <Action sr="act1" ve="7"><code>39</code><Str sr="arg0">%i</Str><Str sr="arg1">1:3</Str></Action>
    <Action sr="act2" ve="7"><code>30</code><on/><Int sr="arg1" val="5"/></Action>
    <Action sr="act3" ve="7"><code>40</code></Action>
  </Task>
  <Task sr="task36"><id>36</id><nme>Spin</nme>
    <Action sr="act0" ve="7"><code>39</code><Str sr="arg0">%i</Str><Str sr="arg1">1:50</Str></Action>
    <Action sr="act1" ve="7"><code>30</code><Int sr="arg1" val="2"/></Action>
    <Action sr="act2" ve="7"><code>40</code></Action>
  </Task>
  <Task sr="task37"><id>37</id><nme>Goto Spin</nme>
    <Action sr="act0" ve="7"><code>547</code><Str sr="arg0">%n</Str><Str sr="arg1">1</Str></Action>
    <Action sr="act1" ve="7"><code>30</code><Int sr="arg1" val="3"/></Action>
    <Action sr="act2" ve="7"><code>135</code><Int sr="arg0" val="0"/><Int sr="arg1" val="1"/><Str sr="arg2"/></Action>
  </Task>
  <Task sr="task38"><id>38</id><nme>Careful</nme><rty>1</rty>
    <Action sr="act0" ve="7"><code>39</code><Str sr="arg0">%i</Str><Str sr="arg1">1:50</Str></Action>
    <Action sr="act1" ve="7"><code>30</code><Int sr="arg1" val="2"/></Action>
    <Action sr="act2" ve="7"><code>40</code></Action>
  </Task>
  <Task sr="task39"><id>39</id><nme>Tracker</nme>
    <Action sr="act0" ve="7"><code>332</code><Int sr="arg0" val="1"/></Action>
    <Action sr="act1" ve="7"><code>902</code><Int sr="arg0" val="1"/><Int sr="arg1" val="0"/>
      <Int sr="arg2" val="0"/><Int sr="arg3" val="1"/></Action>
  </Task>
  <Task sr="task40"><id>40</id><nme>Maybe Wifi</nme>
    <Action sr="act0" ve="7"><code>37</code><ConditionList sr="if">
      <Condition sr="c0" ve="3"><lhs>%x</lhs><op>2</op><rhs>1</rhs></Condition></ConditionList></Action>
    <Action sr="act1" ve="7"><code>425</code><Int sr="arg0" val="0"/></Action>
    <Action sr="act2" ve="7"><code>38</code></Action>
  </Task>
  <Task sr="task41"><id>41</id><nme>Always Wifi</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="1"/></Action>
  </Task>
</TaskerData>
"""


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
    tables["all_profiles_by_name"] = {
        profile["name"]: {"xml": profile["xml"], "id": key} for key, profile in tables["all_profiles"].items()
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items() if task["name"]
    }
    PrimeItems.tasker_root_elements = tables


@pytest.fixture
def problems() -> list:
    """Every behavioural problem in the fixture."""
    _load(_LINT_XML)
    return proflint.lint_problems()


def _where(problems: list, tag: str) -> list[str]:
    """The location line of every finding of one tag, which is what the assertions match."""
    return sorted(problem.where.label for problem in problems if problem.tag == tag)


def _detail(problems: list, tag: str) -> str:
    """Every detail line of one tag run together, for asserting on what a finding SAYS."""
    return " ".join(problem.detail for problem in problems if problem.tag == tag)


# ##################################################################################
# Profiles that fight, and Profiles that can never fire.
# ##################################################################################
def test_conflicting_profiles(problems: list) -> None:
    """Two Profiles on one trigger whose Tasks set the same switch opposite ways."""
    assert _where(problems, "PROFILE-CONFLICT") == ["Project 'Home' > Profile 'Lights On' (id 10)"]
    detail = _detail(problems, "PROFILE-CONFLICT")
    assert "Profile 'Lights Off' (id 11)" in detail
    # Both halves of the disagreement named, and named as Tasker names the setting.
    assert "sets WiFi On" in detail
    assert "sets it Off" in detail


def test_agreeing_profiles_are_not_a_conflict(problems: list) -> None:
    """Sharing a trigger is only a conflict when the Tasks disagree.

    Profiles 12 and 13 watch one Event and both switch Wi-Fi on.  Reporting that as a
    conflict is the failure this rule is most likely to have, because the grouping half of
    it has already succeeded by the time the comparison runs.
    """
    assert "Echo A" not in _detail(problems, "PROFILE-CONFLICT")
    assert "Project 'Home' > Profile 'Echo A' (id 12)" in _where(problems, "PROFILE-DUPLICATE-TRIGGER")


def test_conditional_setting_is_not_a_conflict(problems: list) -> None:
    """A setting made inside an If is not one the Task always makes.

    Profiles 24 and 25 share a trigger, and their Tasks name opposite Wi-Fi settings -- but
    one of them is inside an If, so whether the two ever disagree depends on a condition
    this file cannot evaluate.  That is a configuration, not a conflict.
    """
    assert "Conditional" not in _detail(problems, "PROFILE-CONFLICT")
    assert "Project 'Home' > Profile 'Conditional' (id 24)" in _where(problems, "PROFILE-DUPLICATE-TRIGGER")


def test_event_priority_does_not_split_a_trigger(problems: list) -> None:
    """Two Profiles watching one Event are a pair whatever priority each was given.

    Profiles 12 and 13 differ only in <pri>.  If that went into the signature they would
    fall into two groups of one and nothing would be reported at all -- which is a silent
    failure, so it is asserted rather than assumed.
    """
    duplicates = _detail(problems, "PROFILE-DUPLICATE-TRIGGER")
    assert "Profile 'Echo B' (id 13)" in duplicates


def test_profile_with_no_condition(problems: list) -> None:
    """A Profile carrying no condition element has nothing to become active on."""
    assert "Project 'Home' > Profile 'Silent' (id 14)" in _where(problems, "PROFILE-NEVER-FIRES")
    assert "no condition at all" in _detail(problems, "PROFILE-NEVER-FIRES")


def test_profile_holding_a_condition_and_its_inverse(problems: list) -> None:
    """The same State twice, one of them inverted, can never both be true."""
    assert "Project 'Home' > Profile 'Both Ways' (id 15)" in _where(problems, "PROFILE-NEVER-FIRES")
    assert "its exact opposite" in _detail(problems, "PROFILE-NEVER-FIRES")


def test_profile_with_contradictory_conditions(problems: list) -> None:
    """%Mode = a AND %Mode = b cannot be satisfied however the device is set."""
    assert "Project 'Home' > Profile 'Two Values' (id 16)" in _where(problems, "PROFILE-NEVER-FIRES")
    assert "equal both 'a' and 'b'" in _detail(problems, "PROFILE-NEVER-FIRES")


def test_or_conditions_are_left_alone(problems: list) -> None:
    """The same two tests joined with Or are satisfied by either of them.

    The rule stands down on anything but a plain And chain, because Tasker uses Or and its
    suffixed forms to express grouping -- and a list whose shape cannot be read is a list
    that must not be judged.
    """
    assert "Or Values" not in _detail(problems, "PROFILE-NEVER-FIRES")


def test_profile_on_a_date_that_does_not_exist(problems: list) -> None:
    """The 31st of February never comes round."""
    assert "Project 'Home' > Profile 'Leap' (id 18)" in _where(problems, "PROFILE-NEVER-FIRES")
    assert "day of the month that none of the months it names ever reaches" in _detail(problems, "PROFILE-NEVER-FIRES")


# ##################################################################################
# Battery: monitors that never stop and Profiles on a timer.
# ##################################################################################
def test_always_on_wifi_monitor(problems: list) -> None:
    """A 'Wifi Near' Profile keeps Tasker scanning."""
    where = _where(problems, "ALWAYS-ON-MONITOR")
    assert "Project 'Home' > Profile 'Near Wifi' (id 19)" in where
    assert "keep scanning for Wi-Fi networks" in _detail(problems, "ALWAYS-ON-MONITOR")


def test_always_on_location_profile(problems: list) -> None:
    """A location Profile keeps Tasker asking where the device is."""
    assert "Project 'Home' > Profile 'Where' (id 20)" in _where(problems, "ALWAYS-ON-MONITOR")


def test_disabled_profile_monitors_nothing(problems: list) -> None:
    """Profile 23 watches 'Wifi Near' and is switched off, so it costs nothing.

    healthck already reports it as DISABLED-PROFILE, which is the finding that matters
    about it; a battery warning on a Profile that is not running would be simply wrong.
    """
    assert "Off Duty" not in " ".join(_where(problems, "ALWAYS-ON-MONITOR"))


def test_gps_turned_on_and_never_off(problems: list) -> None:
    """A Task that turns GPS on where nothing in the file ever turns it off."""
    assert "Project 'Home' > Task 'Tracker' (id 39) action 1" in _where(problems, "ALWAYS-ON-MONITOR")
    assert "no 'Stop Location' and no 'GPS Off' in the whole configuration" in _detail(problems, "ALWAYS-ON-MONITOR")


def test_one_action_can_raise_two_findings(problems: list) -> None:
    """A Get Location that keeps tracking AND has no timeout is both of those things.

    The two checks read the same action, and asking them as one chain would let whichever
    was asked first hide the other -- a silent loss, because the finding that survives
    looks perfectly correct on its own.
    """
    assert "Project 'Home' > Task 'Tracker' (id 39) action 2" in _where(problems, "ALWAYS-ON-MONITOR")
    assert "Project 'Home' > Task 'Tracker' (id 39) action 2" in _where(problems, "NO-TIMEOUT")
    assert "with 'Keep Tracking' set" in _detail(problems, "ALWAYS-ON-MONITOR")


def test_frequent_time_trigger(problems: list) -> None:
    """A Profile repeating every two minutes wakes the device 720 times a day."""
    assert _where(problems, "FREQUENT-TRIGGER") == ["Project 'Home' > Profile 'Every 2' (id 21)"]
    assert "720" in _detail(problems, "FREQUENT-TRIGGER")


def test_occasional_time_trigger_is_left_alone(problems: list) -> None:
    """Twenty minutes is a schedule, not a poll."""
    assert "Every 20" not in " ".join(_where(problems, "FREQUENT-TRIGGER"))


# ##################################################################################
# Tasks: polling loops, blocking waits and collisions.
# ##################################################################################
def test_wait_inside_a_for_is_a_polling_loop(problems: list) -> None:
    """A Wait inside a For runs once per lap, which is a poll."""
    where = _where(problems, "POLLING-LOOP")
    assert "Project 'Home' > Task 'Spin' (id 36) action 2" in where
    assert "2 second(s)" in _detail(problems, "POLLING-LOOP")


def test_wait_under_a_backwards_goto_is_a_polling_loop(problems: list) -> None:
    """A Goto aimed at an earlier action is a loop the block matcher cannot see."""
    assert "Project 'Home' > Task 'Goto Spin' (id 37) action 2" in _where(problems, "POLLING-LOOP")


def test_wait_outside_a_loop_is_not_a_polling_loop(problems: list) -> None:
    """A Wait that runs once is a pause, and a disabled one does not run at all.

    Task 35 holds both: a five second Wait before any loop, and a Wait inside a For that
    Tasker will skip because it is disabled.  Either one being reported would make this
    rule fire on most of the Tasks anyone has ever written.
    """
    assert "Straight Wait" not in " ".join(_where(problems, "POLLING-LOOP"))


def test_action_with_no_timeout(problems: list) -> None:
    """A Run Shell set to zero waits for ever, and takes the Task with it."""
    assert "Project 'Home' > Task 'Shell' (id 34) action 1" in _where(problems, "NO-TIMEOUT")
    assert "'Run Shell' has no timeout set" in _detail(problems, "NO-TIMEOUT")


def test_action_with_a_timeout_is_left_alone(problems: list) -> None:
    """The second Run Shell in Task 34 has a timeout of ten seconds, so it is not reported."""
    assert "Project 'Home' > Task 'Shell' (id 34) action 2" not in _where(problems, "NO-TIMEOUT")


def test_long_running_task_with_no_collision_handling(problems: list) -> None:
    """A Task that loops, is triggered by a Profile, and leaves collision handling unset."""
    assert "Project 'Home' > Task 'Spin' (id 36)" in _where(problems, "MISSING-COLLISION")
    assert "silently abandons the new run" in _detail(problems, "MISSING-COLLISION")


def test_collision_handling_set_is_not_reported(problems: list) -> None:
    """Task 38 is the same loop with <rty> set, which is the whole point of the rule."""
    assert "Careful" not in " ".join(_where(problems, "MISSING-COLLISION"))


def test_untriggered_task_has_no_collision_to_miss(problems: list) -> None:
    """Task 37 loops but no Profile starts it, so nothing can arrive while it runs."""
    assert "Goto Spin" not in " ".join(_where(problems, "MISSING-COLLISION"))


# ##################################################################################
# The findings reach the report.
# ##################################################################################
def test_findings_are_folded_into_the_health_check() -> None:
    """A rule that works and is never printed is not a feature.

    Checked through the report text rather than through the finding list because that is
    what the user reads -- and because the closing note is part of the answer: every rule
    here is a judgement about behaviour, and the report has to say so.
    """
    _load(_LINT_XML)
    rows, counts = run_health_check()
    report = text_report(rows)

    for tag in proflint.TAGS:
        assert f"[{tag}]" in report, tag
    assert "NOTE ON BEHAVIOUR FINDINGS" in report
    assert counts["WARNING"] > 0
