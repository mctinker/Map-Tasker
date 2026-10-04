"""The two kinds of Scene behind one interface (scenemodel), and the analyses that use it.

What is asserted is what each kind yields to the analyses -- text that may name a variable, and the
Tasks a Scene runs -- and, through varxref and healthck, that an analysis built on the interface
gives the same answer for a Legacy Scene and a Version 2 one wherever the two say the same thing.

The fixture holds one Scene of each kind with the same intent: a label reading a variable, an input
bound to another, and a button that runs a Task -- and, for each, a Task that is not in the file,
one that is, one that cannot be checked (a variable for a name; an anonymous inline Task) -- so each
branch of the walk has a case that takes it and a case that does not.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from maptasker.src import healthck, scenemodel, sceneedit, taskerd, varxref
from maptasker.src.initparg import ProgramArguments
from maptasker.src.mapjump import SCENE, Target
from maptasker.src.primitem import PrimeItems

_ARG_SPECS = Path(__file__).resolve().parent.parent / "maptasker" / "assets" / "json" / "arg_specs.json"

_LEGACY = """
  <Scene sr="sceneOld Panel">
    <nme>Old Panel</nme>
    <widthPort>600</widthPort><heightPort>800</heightPort><widthLand>-1</widthLand><heightLand>-1</heightLand>
    <TextElement sr="elements0">
      <Str sr="arg0" ve="3">Heading</Str>
      <Str sr="arg1" ve="3">Hello %Who</Str>
    </TextElement>
    <EditTextElement sr="elements1">
      <Str sr="arg0" ve="3">Name</Str>
      <Str sr="arg1" ve="3">%Form</Str>
    </EditTextElement>
    <ButtonElement sr="elements2">
      <Str sr="arg0" ve="3">OK</Str>
      <Str sr="arg1" ve="3">Go</Str>
      <clickTask>{ok}</clickTask>
    </ButtonElement>
    <ButtonElement sr="elements3">
      <Str sr="arg0" ve="3">Broken</Str>
      <clickTask>999</clickTask>
    </ButtonElement>
    <ButtonElement sr="elements4">
      <Str sr="arg0" ve="3">Inline</Str>
      <clickTask>-5</clickTask>
    </ButtonElement>
    <ButtonElement sr="elements5">
      <Str sr="arg0" ve="3">Unbound</Str>
      <clickTask></clickTask>
    </ButtonElement>
  </Scene>"""

_V2_LAYOUT = {
    "name": "New Panel",
    "root": {
        "type": "Column",
        "id": "root",
        "children": [
            {"type": "Text", "id": "heading", "text": "Hello %Who"},
            {"type": "TextInput", "id": "name", "value": "%Form"},
            {
                "type": "Button",
                "id": "ok",
                "eventHandlers": {
                    "handlers": [
                        {
                            "events": [{"type": "click"}],
                            "actions": [
                                {"type": "RunTask", "task": "Do It"},
                                {"type": "RunTask", "task": "Missing Task"},
                                {"type": "RunTask", "task": "Menu %Which"},
                                {"type": "SetVariable", "variable": "x", "value": "1"},
                            ],
                        },
                    ],
                },
            },
        ],
    },
}

_BACKUP = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><tids>7</tids><scenes>Old Panel,New Panel</scenes></Project>
  <Task sr="task7" ve="2"><id>7</id><nme>Do It</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">done</Str></Action>
  </Task>
""" + _LEGACY.format(ok="7") + """
  <Scene sr="sceneNew Panel"><nme>New Panel</nme>
    <widthPort>-1</widthPort><heightPort>-1</heightPort><widthLand>-1</widthLand><heightLand>-1</heightLand>
  </Scene>
</TaskerData>
"""


def _scene(name: str) -> ET.Element:
    return PrimeItems.tasker_root_elements["all_scenes"][name]["xml"]


@pytest.fixture(autouse=True)
def _loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixture backup, in the tables the analyses read -- with the V2 layout encoded as Tasker does.

    Every attribute goes through monkeypatch so that it is put back afterwards.  Other test modules
    leave their configuration behind and a few of them read what an earlier one left, so a module
    that overwrote it for good would break whichever of those ran next.
    """
    root = ET.fromstring(_BACKUP)  # noqa: S314  (fixture text, defined in this file)
    sceneedit.encode_v2_layout(root.find("Scene[@sr='sceneNew Panel']"), _V2_LAYOUT)
    specs = json.loads(_ARG_SPECS.read_text(encoding="utf-8"))
    specs[str(len(specs))] = "ConditionList"
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }
    tables["all_profiles_by_name"] = {p["name"]: {"xml": p["xml"], "id": k} for k, p in tables["all_profiles"].items()}
    tables["all_tasks_by_name"] = {
        t["name"]: {"xml": t["xml"], "id": k} for k, t in tables["all_tasks"].items() if t["name"]
    }
    for name, value in {
        "file_to_get": "fixture.xml",
        "xml_root": root,
        "xml_tree": ET.ElementTree(root),
        "program_arguments": ProgramArguments(task_action_warning_limit=100, language="English"),
        "tasker_arg_specs": specs,
        "tasker_root_elements": tables,
    }.items():
        monkeypatch.setattr(PrimeItems, name, value)


def _place(name: str) -> Target:
    return Target(SCENE, name, name)


# ##################################################################################
# Which model
# ##################################################################################
def test_a_scene_is_given_the_model_of_its_own_kind() -> None:
    """Told apart by <lj>, the way sceneedit.is_v2_scene decides it."""
    assert scenemodel.model_of(_scene("Old Panel")).name == sceneedit.SCENE_VERSION_LEGACY
    assert scenemodel.model_of(_scene("New Panel")).name == sceneedit.SCENE_VERSION_V2


@pytest.mark.parametrize("name", ["Old Panel", "New Panel"])
def test_both_models_satisfy_the_same_interface(name: str) -> None:
    """The point of the interface: a caller can walk either without knowing which it holds."""
    model = scenemodel.model_of(_scene(name))
    assert list(model.text_sites(_scene(name), _place(name)))
    assert list(model.task_bindings(_scene(name)))


# ##################################################################################
# Text that may name a variable
# ##################################################################################
def _texts(name: str) -> dict[str, scenemodel.TextSite]:
    sites = scenemodel.model_of(_scene(name)).text_sites(_scene(name), _place(name))
    return {site.text: site for site in sites if "%" in site.text}


@pytest.mark.parametrize("name", ["Old Panel", "New Panel"])
def test_each_kind_yields_the_text_that_reads_a_variable_and_the_input_that_binds_one(name: str) -> None:
    """The label reads %Who; the input's value is two-way on %Form -- in both kinds."""
    sites = _texts(name)
    assert {"Hello %Who", "%Form"} <= set(sites)
    assert sites["Hello %Who"].two_way is False
    assert sites["%Form"].two_way is True


def test_only_a_version_2_scene_has_event_handler_actions_to_read() -> None:
    """A V2 handler's actions are text too -- a RunTask naming %Which reads it -- and a Legacy element has no such thing."""
    assert "Menu %Which" in _texts("New Panel")
    assert not _texts("New Panel")["Menu %Which"].two_way
    assert "Menu %Which" not in _texts("Old Panel")


def test_a_legacy_site_names_its_element_and_points_at_the_argument_holding_the_text() -> None:
    """The detail is what the report prints; the element is what a rewrite changes."""
    site = _texts("Old Panel")["%Form"]
    assert site.detail == "EditText 'Name' value (two-way)"
    assert site.element is not None
    assert site.element.text == "%Form"
    assert site.path == ()


def test_a_version_2_site_is_addressed_by_component_path_and_property() -> None:
    """The text is inside gzipped JSON, so an element would address nothing: the path and key do."""
    site = _texts("New Panel")["%Form"]
    assert site.detail == "component 'TextInput 'name'' value"
    assert site.element is _scene("New Panel")
    assert site.path[1] == "value"


def test_a_version_2_scene_that_will_not_decode_yields_nothing() -> None:
    """Guessing at a corrupt layout would invent references."""
    _scene("New Panel").find("lj").text = "not a layout"
    model = scenemodel.model_of(_scene("New Panel"))
    assert list(model.text_sites(_scene("New Panel"), _place("New Panel"))) == []
    assert list(model.task_bindings(_scene("New Panel"))) == []


# ##################################################################################
# The Tasks a Scene runs
# ##################################################################################
def _bindings(name: str) -> list[scenemodel.TaskBinding]:
    return list(scenemodel.model_of(_scene(name)).task_bindings(_scene(name)))


def test_a_legacy_scene_binds_tasks_by_id_and_leaves_out_the_anonymous_and_the_unbound() -> None:
    """An inline Task has nothing to check, and an event with no Task bound is not a binding."""
    bindings = _bindings("Old Panel")
    assert [b.task_id for b in bindings] == ["7", "999"]
    assert all(b.task_name == "" and b.component is False for b in bindings)
    assert bindings[0].referrer == "Button 'OK' TAP"
    assert bindings[0].broken == "Button 'OK' 'TAP' fires Task id 7, which is not in this file."
    assert bindings[1].broken == "Button 'Broken' 'TAP' fires Task id 999, which is not in this file."


def test_a_version_2_scene_binds_tasks_by_name_including_ones_that_cannot_be_checked() -> None:
    """Whether a name holding a variable can be checked is the analysis's policy, so it is yielded."""
    bindings = _bindings("New Panel")
    assert [b.task_name for b in bindings] == ["Do It", "Missing Task", "Menu %Which"]
    assert all(b.task_id == "" and b.component is True for b in bindings)
    assert bindings[0].referrer == "component 'Button 'ok''"
    assert bindings[1].broken == "component 'Button 'ok'' runs Task 'Missing Task', which is not in this file."


# ##################################################################################
# The analyses built on it
# ##################################################################################
def _variables() -> dict[tuple[str, str], varxref.Variable]:
    return varxref.build_index(state=PrimeItems).variables


def test_varxref_records_a_read_and_a_two_way_binding_for_each_kind_alike() -> None:
    """%Who is read once by each Scene; %Form is read AND set once by each."""
    variables = _variables()
    who, form = variables[("%Who", "")], variables[("%Form", "")]
    assert len(who.reads) == 2
    assert len(who.sets) == 0
    assert len(form.sets) == 2
    assert len(form.reads) == 2


def test_varxref_keeps_a_version_2_references_address_and_a_legacy_ones_element() -> None:
    """mapswap rewrites by these: a path into the layout for one, the argument element for the other."""
    form = _variables()[("%Form", "")]
    by_scene = {ref.scope_id: ref for ref in form.sets}
    assert by_scene["scene:New Panel"].path
    assert by_scene["scene:New Panel"].element is _scene("New Panel")
    assert not by_scene["scene:Old Panel"].path
    assert by_scene["scene:Old Panel"].element is not None


def _scene_findings() -> list[healthck.Finding]:
    return [f for f in healthck.collect_findings(state=PrimeItems).findings if f.tag == "BROKEN-SCENE-TASK"]


def test_healthck_reports_the_missing_task_of_each_kind_and_nothing_it_cannot_check() -> None:
    """One broken id and one broken name; the anonymous Task, the unbound event and the variable name are quiet."""
    details = sorted(f.detail for f in _scene_findings())
    assert details == [
        "Button 'Broken' 'TAP' fires Task id 999, which is not in this file.",
        "component 'Button 'ok'' runs Task 'Missing Task', which is not in this file.",
    ]


def test_healthck_counts_both_kinds_of_scene_as_running_the_task_they_name() -> None:
    """Task 7 is run by a Legacy element (by id) and a V2 component (by name) -- both are referrers."""
    index = healthck.ReferenceIndex()
    index.project_of_scene = {"Old Panel": "Home", "New Panel": "Home"}
    healthck._index_scenes(index, state=PrimeItems)  # noqa: SLF001
    kinds = sorted(referrer.kind for referrer in index.task_referrers["7"])
    assert kinds == [healthck.BY_SCENE_COMPONENT, healthck.BY_SCENE_ELEMENT]
