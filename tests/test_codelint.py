"""The code inside JavaScriptlet and Run Shell actions.

Two things were invisible to the Health Check.  A script whose brackets or strings do not
close fails every time it runs, and to every other check it is just an argument.  And a
JavaScriptlet reaches Tasker variables through global('Name'), setGlobal, local() and
setLocal() -- never with a '%' -- so a global read only by a script was reported as never
read, and one set only by a script as never set.

The syntax checks are structural, and the cost of being wrong is a finding somebody
chases for nothing, so most of the cases here are VALID code that is easy to misread: a
regular expression holding a '/', a template literal inside a template literal, a shell
'case', Tasker's own %array(#) inside either.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import codelint, healthck, taskerd, varxref
from maptasker.src.initparg import ProgramArguments
from maptasker.src.primitem import PrimeItems


# ##################################################################################
# JavaScript: well-formed code is left alone
# ##################################################################################
@pytest.mark.parametrize(
    "code",
    [
        "var a = b / c / d;",
        "var r = /[/]+/g.test(s);",
        "if (x) { y = s.replace(/\\/(\\d+)/, '$1'); }",
        "var t = `outer ${ items.map(i => `inner ${i}`).join(',') } end`;",
        "var o = { a: [1, 2], b: { c: 'd' } };",
        '// a comment with ( and " in it\nvar x = 1;',
        "/* a block ( [ { comment */ var x = 1;",
        "var s = 'it\\'s fine';",
        "var n = %Count + 1; var first = '%items(1)'; var many = %items(#);",
        "flash(`Error: ${error}`);",
        "setLocal('result', local('input').split(',').filter(v => v).length);",
        "var p = x % 2;",
    ],
    ids=lambda code: code[:30],
)
def test_well_formed_javascript_is_not_reported(code: str) -> None:
    """Nothing here is wrong, and each is a place a naive bracket count goes astray."""
    assert codelint.js_syntax_problem(code) == ""


@pytest.mark.parametrize(
    ("code", "said"),
    [
        ("if (x) {\n  y = 1;\n", "The '{' opened on line 1 is never closed."),
        ("var a = f(1));", "A ')' on line 1 closes nothing."),
        ("var a = [1, 2);", "A ')' on line 1 closes the '[' opened on line 1."),
        ("var s = 'no end;\nvar t = 1;", "A string opened with ' on line 1 is not closed on that line."),
        ("var x = 1; /* never\nends", "A comment opened on line 1 is never closed."),
        ("var t = `open\nstill open", "A template literal opened on line 1 is never closed."),
    ],
)
def test_malformed_javascript_is_reported_where_it_goes_wrong(code: str, said: str) -> None:
    """The finding names the line, so it can be found in a script typed on a phone."""
    assert codelint.js_syntax_problem(code) == said


# ##################################################################################
# Shell: well-formed commands are left alone
# ##################################################################################
@pytest.mark.parametrize(
    "command",
    [
        "echo 'single (quoted' \"double ) quoted\"",
        'echo "$(date +%s) and ${HOME}"',
        'result="$(echo "nested quotes")"',
        "echo `date`",
        "ls /sdcard # a comment with ' in it",
        "if [ %not_sets(#) -lt 4 ]; then echo few; fi",
        "case $1 in start) echo go;; stop) echo halt;; esac",
        "cat <<EOF\nit's a (here document\nEOF",
        "echo it\\'s escaped",
    ],
    ids=lambda command: command[:30],
)
def test_well_formed_shell_is_not_reported(command: str) -> None:
    """Including the two a bracket count cannot judge, which the check steps aside from."""
    assert codelint.shell_syntax_problem(command) == ""


@pytest.mark.parametrize(
    ("command", "said"),
    [
        ("echo 'never closed", "A single quote opened on line 1 is never closed."),
        ('echo "never closed', "The double quote opened on line 1 is never closed."),
        ("x=$(date", "The '$(' opened on line 1 is never closed."),
        ("echo done)", "A ')' on line 1 closes nothing."),
        ("echo `date", "The backquote opened on line 1 is never closed."),
    ],
)
def test_malformed_shell_is_reported(command: str, said: str) -> None:
    """Each of these fails in the shell before any of the command runs."""
    assert codelint.shell_syntax_problem(command) == said


# ##################################################################################
# JavaScript: the variables a script names
# ##################################################################################
def test_a_script_names_variables_through_taskers_calls() -> None:
    """Reads and writes, globals and locals, with or without a '%', in any quotes."""
    code = "var t = global('Threshold'); setGlobal(\"%Result\", t); setLocal(`out`, local('in'));"
    assert codelint.js_variable_uses(code) == [
        ("%Threshold", False),
        ("%Result", True),
        ("%out", True),
        ("%in", False),
    ]


def test_a_name_held_in_a_script_variable_is_not_guessed_at() -> None:
    """setLocal(name, value) could set anything; nothing is claimed for it."""
    assert codelint.js_variable_uses("var name = 'x'; setLocal(name, 1);") == []


# ##################################################################################
# In a configuration
# ##################################################################################
_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Task sr="task1">
    <id>1</id>
    <nme>Scripted</nme>
    <Action sr="act0" ve="7">
      <code>547</code>
      <Str sr="arg0" ve="3">%Threshold</Str>
      <Str sr="arg1" ve="3">5</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>129</code>
      <Str sr="arg0" ve="3">var t = global('Threshold');
setGlobal('Result', t * 2);</Str>
    </Action>
  </Task>
  <Task sr="task2">
    <id>2</id>
    <nme>Reader</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">%Result</Str>
    </Action>
  </Task>
  <Task sr="task3">
    <id>3</id>
    <nme>Broken</nme>
    <Action sr="act0" ve="7">
      <code>548</code>
      <Str sr="arg0" ve="3">first</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>129</code>
      <Str sr="arg0" ve="3">if (ready) {
  flash('never closed');</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>123</code>
      <Str sr="arg0" ve="3">echo "unterminated</Str>
    </Action>
  </Task>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def _loaded() -> None:
    """Build the PrimeItems tables from the fixture, the way taskerd does from a file."""
    root = ET.fromstring(_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100)
    tables = {
        "all_projects": {},
        "all_profiles": {},
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": {},
        "all_services": [],
        "all_profiles_by_name": {},
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items()
    }
    PrimeItems.tasker_root_elements = tables


def test_a_global_read_only_by_a_script_is_not_reported_as_never_read() -> None:
    """The false finding this was written to remove: %Threshold is read, by global()."""
    subjects = {suspect.subject for suspect in varxref.suspects(varxref.build_index(state=PrimeItems))}
    assert "%Threshold" not in subjects


def test_a_global_set_only_by_a_script_is_not_reported_as_never_set() -> None:
    """The other half: %Result is set, by setGlobal(), and read by the Flash."""
    subjects = {suspect.subject for suspect in varxref.suspects(varxref.build_index(state=PrimeItems))}
    assert "%Result" not in subjects


def test_the_script_is_named_as_where_the_variable_is_used() -> None:
    """The where-used index says the script reads it, so the reader can go and look."""
    entry = varxref.build_index(state=PrimeItems).variables[("%Threshold", "")]
    assert [reference.detail for reference in entry.reads] == ["JavaScriptlet, Code= (script)"]


def test_broken_code_is_reported_at_the_action_that_holds_it() -> None:
    """One finding per broken action, pointing at it by its number in the Task."""
    problems = codelint.lint_problems()
    assert [(problem.tag, problem.where.name, problem.where.action) for problem in problems] == [
        (codelint.JS_SYNTAX, "Broken", 2),
        (codelint.SHELL_SYNTAX, "Broken", 3),
    ]
    assert "line 1 is never closed" in problems[0].detail


def test_the_health_check_carries_the_findings_and_can_leave_them_out() -> None:
    """Folded into the report, and skipped outright when both categories are unticked."""
    tags = {finding.tag for finding in healthck.collect_findings(state=PrimeItems).findings}
    assert {codelint.JS_SYNTAX, codelint.SHELL_SYNTAX} <= tags
    skipped = {finding.tag for finding in healthck.collect_findings(skip=codelint.TAGS, state=PrimeItems).findings}
    assert not skipped & codelint.TAGS
