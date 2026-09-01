"""Scene Properties tests -- Tasker's "Scene Properties Edit" screen, tab for tab.

Its user guide divides the screen into UI, Actions and Event, and Event into Key, Home Tap
and Tab Tap.  Tasker's file format names none of it that way, so what most of this file
asserts is THE MAPPING between the two, and the mapping was derived by measurement against
the 538 <PropertiesElement>s in XML/ rather than read anywhere -- same spirit as
test_objprops.py, and the same reason: each of these is a way to lose a user's data quietly.

The three that were not obvious, all settled by the sample data:

  * <urlMatch> is the KEYS FILTER, not a URL.  Its values are "back" (64), "back/home" (12),
    "Back;Home" and "Back" -- the guide's slash-separated key list.
  * <itemselectedTask> is TAB TAP on a Scene's properties and the unrelated "Item Selected"
    on a Spinner.  Every sample whose Tab Labels are set has one, and all 15 are on an
    Activity -- which is exactly what the guide says Tab Tap needs.
  * <stopEvent> is written as the word "true" in all 75 samples that have one and is simply
    ABSENT in the other 12.  There is no <stopEvent>false</stopEvent> anywhere, so off has
    to be stored as absence -- and a filter emptied by turning it off has to go too, or
    ticking and unticking a box would leave litter in a file that had none.  A filter that
    was ALREADY empty is a different thing and must be left alone; $Simon.xml has one, and
    the round-trip test over every sample <PropertiesElement> is what turned that case up.

The rendering tests build the real forms and walk the widget tree, because a mapping that is
right in sceneedit and wired up wrongly in guiwins is still wrong on screen.  The Task half
is tested at the seam the Event tabs use: resolving the bound Task BY ID (an unnamed Task's
displayed name is one taskerd invents from its first action), and applying only the action
edits, never the Name -- which is why taskedit.apply_action_edits_to_task exists beside
apply_edits_to_task.
"""

from __future__ import annotations

import copy
import glob
import json
import os
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import sceneedit, taskedit
from maptasker.src.primitem import PrimeItems

# A Legacy Scene shaped the way the sample data shapes one: arguments in order, a keyTask
# ahead of them, and a LinkClickFilter last.  Transcribed from XML/Smart Reminders.prj.xml.
_SCENE_XML = """<Scene sr="Reminder">
  <cdate>1671835573104</cdate>
  <heightLand>-1</heightLand>
  <heightPort>-1</heightPort>
  <nme>Reminder</nme>
  <widthLand>-1</widthLand>
  <widthPort>-1</widthPort>
  <PropertiesElement sr="props">
    <keyTask>268</keyTask>
    <Int sr="arg0" val="2" />
    <Int sr="arg1" val="2" />
    <Str sr="arg2" ve="3">%backgroundcolor</Str>
    <Int sr="arg3" val="0" />
    <Str sr="arg4" ve="3">Smart Reminders</Str>
    <Str sr="arg5" ve="3" />
    <Img sr="arg6" ve="2" />
    <Str sr="arg7" ve="3" />
    <LinkClickFilter sr="filter0">
      <stopEvent>true</stopEvent>
      <urlMatch>back/home</urlMatch>
    </LinkClickFilter>
  </PropertiesElement>
</Scene>"""

# The same Scene with no filter at all -- the state 12 of the 87 samples are in, and the one
# a freshly added <PropertiesElement> starts in.
_SCENE_XML_NO_FILTER = """<Scene sr="Plain">
  <nme>Plain</nme>
  <PropertiesElement sr="props">
    <Int sr="arg0" val="0" />
    <Str sr="arg2" ve="3">#FF000000</Str>
  </PropertiesElement>
</Scene>"""


def _properties(scene_xml: str) -> ET.Element:
    """The <PropertiesElement> of a Scene given as text."""
    return ET.fromstring(scene_xml).find("PropertiesElement")  # noqa: S314


# ==========================================
# 1. READING STOP EVENT
# ==========================================
def test_the_word_true_is_what_reads_as_on():
    assert sceneedit.legacy_stop_event(_properties(_SCENE_XML)) is True


def test_no_filter_at_all_reads_as_off():
    assert sceneedit.legacy_stop_event(_properties(_SCENE_XML_NO_FILTER)) is False


def test_a_filter_with_no_stop_event_reads_as_off():
    """6 of the 87 sample filters carry a <urlMatch> and no <stopEvent>."""
    properties = _properties(_SCENE_XML)
    link_filter = properties.find("LinkClickFilter")
    link_filter.remove(link_filter.find("stopEvent"))
    assert sceneedit.legacy_stop_event(properties) is False


def test_a_hand_written_false_reads_as_off():
    """Tasker never writes it, but a hand-edited file can -- and "false" must not read as
    on just because the element is present."""
    properties = _properties(_SCENE_XML)
    properties.find("LinkClickFilter/stopEvent").text = "false"
    assert sceneedit.legacy_stop_event(properties) is False


# ==========================================
# 2. WRITING STOP EVENT
# ==========================================
def test_ticking_it_on_a_scene_with_no_filter_builds_the_one_tasker_writes():
    properties = _properties(_SCENE_XML_NO_FILTER)
    sceneedit.legacy_set_stop_event(properties, enabled=True)

    link_filter = properties.find("LinkClickFilter")
    assert link_filter is not None
    assert link_filter.attrib == {"sr": "filter0"}
    assert link_filter.findtext("stopEvent") == "true"
    # Last child, which is where all 87 samples keep it -- after the Str/Int/Img arguments.
    assert list(properties)[-1] is link_filter
    assert sceneedit.legacy_stop_event(properties) is True


def test_unticking_takes_the_whole_filter_away_again():
    """Tick, untick, and the XML has to be what it was -- otherwise a look at the checkbox
    leaves an empty element behind in a file that never had one."""
    properties = _properties(_SCENE_XML_NO_FILTER)
    before = ET.tostring(properties)

    sceneedit.legacy_set_stop_event(properties, enabled=True)
    sceneedit.legacy_set_stop_event(properties, enabled=False)

    assert ET.tostring(properties) == before
    assert properties.find("LinkClickFilter") is None


def test_unticking_keeps_a_filter_that_still_says_which_keys():
    """<urlMatch> is a separate setting this checkbox does not own, so the filter stays."""
    properties = _properties(_SCENE_XML)
    sceneedit.legacy_set_stop_event(properties, enabled=False)

    link_filter = properties.find("LinkClickFilter")
    assert link_filter is not None
    assert link_filter.find("stopEvent") is None
    assert link_filter.findtext("urlMatch") == "back/home"


def test_an_already_empty_filter_is_left_where_it_is():
    """$Simon.xml carries a <LinkClickFilter sr="filter0" /> with nothing in it, on a Scene
    whose Stop Event is off.  Turning off what is already off must not delete it: a no-op
    has no business removing an element the user never touched.
    """
    properties = _properties(_SCENE_XML)
    link_filter = properties.find("LinkClickFilter")
    link_filter.remove(link_filter.find("stopEvent"))
    link_filter.remove(link_filter.find("urlMatch"))
    before = ET.tostring(properties)

    sceneedit.legacy_set_stop_event(properties, enabled=False)

    assert ET.tostring(properties) == before
    assert properties.find("LinkClickFilter") is not None


def test_off_is_stored_as_absence_never_as_the_word_false():
    properties = _properties(_SCENE_XML)
    sceneedit.legacy_set_stop_event(properties, enabled=False)
    assert b"false" not in ET.tostring(properties)


def test_stop_event_goes_ahead_of_the_url_match():
    """The order every sample filter is in."""
    properties = _properties(_SCENE_XML)
    link_filter = properties.find("LinkClickFilter")
    link_filter.remove(link_filter.find("stopEvent"))

    sceneedit.legacy_set_stop_event(properties, enabled=True)

    assert [child.tag for child in properties.find("LinkClickFilter")] == ["stopEvent", "urlMatch"]


def test_ticking_what_is_already_ticked_changes_nothing():
    properties = _properties(_SCENE_XML)
    before = ET.tostring(properties)
    sceneedit.legacy_set_stop_event(properties, enabled=True)
    assert ET.tostring(properties) == before


def test_unticking_what_was_never_ticked_changes_nothing():
    properties = _properties(_SCENE_XML_NO_FILTER)
    before = ET.tostring(properties)
    sceneedit.legacy_set_stop_event(properties, enabled=False)
    assert ET.tostring(properties) == before


# ==========================================
# 3. THE BACKSTOP: EVERY SAMPLE PROPERTIES ELEMENT
# ==========================================
def _sample_properties_elements() -> list[ET.Element]:
    """Every <PropertiesElement> in the sample backups, deep-copied so a test can write."""
    found = []
    for path in sorted(glob.glob("XML/*.xml")):
        try:
            root = ET.parse(path).getroot()  # noqa: S314
        except ET.ParseError:
            continue
        found.extend(copy.deepcopy(element) for element in root.iter("PropertiesElement"))
    return found


def test_setting_stop_event_to_what_it_already_is_leaves_every_sample_byte_identical():
    """Read it, write the same value back, and the XML must not move -- over all 538 sample
    <PropertiesElement>s, filter or no filter, stopEvent or no stopEvent.
    """
    samples = _sample_properties_elements()
    if not samples:
        pytest.skip("no sample XML available")

    for properties in samples:
        before = ET.tostring(properties)
        sceneedit.legacy_set_stop_event(properties, enabled=sceneedit.legacy_stop_event(properties))
        assert ET.tostring(properties) == before


def _normalized(element: ET.Element) -> bytes:
    """The element as it would actually be written out.

    Every save path re-indents with ET.indent(root, space="\t") before writing
    (taskedit/profedit/projedit/sceneedit/maputil2 all do), so the source file's own
    whitespace is not part of what is stored -- and a filter that is removed and rebuilt
    cannot carry the original's .text/.tail back with it.  Comparing the indented form is
    therefore comparing what lands in the file.
    """
    copied = copy.deepcopy(element)
    ET.indent(copied, space="\t")
    return ET.tostring(copied)


def test_every_sample_stop_event_survives_a_round_trip_through_off_and_on():
    """Turning it off and back on has to rebuild what was there, for the samples that had
    one -- the filter, its sr, and its <urlMatch> alongside.
    """
    samples = [p for p in _sample_properties_elements() if sceneedit.legacy_stop_event(p)]
    if not samples:
        pytest.skip("no sample XML available")

    for properties in samples:
        before = _normalized(properties)
        sceneedit.legacy_set_stop_event(properties, enabled=False)
        sceneedit.legacy_set_stop_event(properties, enabled=True)
        assert _normalized(properties) == before


# ==========================================
# 4. THE KEY TASK: RESOLVED BY ID, EDITED WITHOUT ITS NAME
# ==========================================
_TASK_XML = """<Task sr="task268">
  <id>268</id>
  <nme>Key Handler</nme>
  <pri>50</pri>
  <Action sr="act0" ve="7">
    <code>548</code>
    <Str sr="arg0" ve="3">hello</Str>
    <Int sr="arg1" val="0" />
  </Action>
</Task>"""

# The same Task with no <nme> -- taskerd gives one of these a made-up display name built
# from its first action, which is exactly the name that must never be written back.
_UNNAMED_TASK_XML = _TASK_XML.replace("  <nme>Key Handler</nme>\n", "")


def _load_arg_specs() -> dict:
    """The arg_type -> category table proginit builds at startup.

    Every one of these Task tests needs it and none of them goes through proginit: without
    it every argument falls to the "unknown category" branch of build_editable_args and
    reads as readonly, so an apply would appear to do nothing.  Same loader as
    test_mapswap._load, including proginit's own appended ConditionList entry.
    """
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file, encoding="utf-8") as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"
    return specs


@pytest.fixture
def loaded_tasks():
    """Put two Tasks in the live tables, the way a loaded backup would."""
    saved = dict(PrimeItems.tasker_root_elements)
    saved_specs = dict(PrimeItems.tasker_arg_specs)
    PrimeItems.tasker_arg_specs = _load_arg_specs()
    named = ET.fromstring(_TASK_XML)  # noqa: S314
    unnamed = ET.fromstring(_UNNAMED_TASK_XML)  # noqa: S314
    PrimeItems.tasker_root_elements["all_tasks"] = {
        "268": {"xml": named, "name": "Key Handler"},
        "269": {"xml": unnamed, "name": "Flash hello.269 (Unnamed)"},
    }
    PrimeItems.tasker_root_elements["all_tasks_by_name"] = {
        "Key Handler": {"xml": named, "id": "268"},
        "Flash hello.269 (Unnamed)": {"xml": unnamed, "id": "269"},
    }
    yield
    PrimeItems.tasker_root_elements.clear()
    PrimeItems.tasker_root_elements.update(saved)
    PrimeItems.tasker_arg_specs = saved_specs


def test_the_bound_task_is_found_by_the_id_the_binding_holds(loaded_tasks):
    edited = taskedit.load_task_for_edit_by_id("268")
    assert edited is not None
    assert edited.task_id == "268"
    assert edited.task_element.findtext("nme") == "Key Handler"
    assert len(edited.actions) == 1


def test_an_unnamed_task_is_still_reachable_by_id(loaded_tasks):
    """The case load_task_for_edit cannot do anything useful with: there is no real name to
    resolve, only the display name taskerd invented.
    """
    edited = taskedit.load_task_for_edit_by_id("269")
    assert edited is not None
    assert edited.task_element.find("nme") is None


def test_editing_the_loaded_task_does_not_touch_the_live_one(loaded_tasks):
    """Same contract as load_task_for_edit -- a deep copy, so nothing lands until an
    explicit apply."""
    edited = taskedit.load_task_for_edit_by_id("268")
    edited.task_element.find("nme").text = "Something Else"
    assert PrimeItems.tasker_root_elements["all_tasks"]["268"]["xml"].findtext("nme") == "Key Handler"


def test_a_binding_pointing_at_a_task_that_is_not_here_resolves_to_nothing(loaded_tasks):
    assert taskedit.load_task_for_edit_by_id("9999") is None


def test_applying_action_edits_leaves_the_task_name_alone(loaded_tasks):
    """The KEY tab shows no Name field, so applying from it must not write one -- and must
    not fail for want of one either, which is what apply_edits_to_task would do here.
    """
    edited = taskedit.load_task_for_edit_by_id("269")
    key = taskedit.arg_key(edited.actions[0].act_number, "0")

    errors = taskedit.apply_action_edits_to_task(edited, {key: "goodbye"})

    assert errors == []
    assert edited.task_element.find("nme") is None
    assert edited.task_element.find("Action/Str[@sr='arg0']").text == "goodbye"


def test_applying_action_edits_writes_the_argument_and_the_label(loaded_tasks):
    edited = taskedit.load_task_for_edit_by_id("268")
    act_number = edited.actions[0].act_number

    errors = taskedit.apply_action_edits_to_task(
        edited,
        {
            taskedit.arg_key(act_number, "0"): "goodbye",
            taskedit.label_key(act_number): "say it",
        },
    )

    assert errors == []
    assert edited.task_element.find("Action/Str[@sr='arg0']").text == "goodbye"
    assert taskedit.get_action_label(edited.actions[0]) == "say it"
    # Untouched by an action-only apply.
    assert edited.task_element.findtext("nme") == "Key Handler"
    assert edited.task_element.findtext("pri") == "50"


# ==========================================
# 5. THE SCENE PROPERTIES SCREEN, RENDERED
# ==========================================
def _load_sample_backup(path: str) -> ET.Element:
    """Build the PrimeItems lookup tables from a sample file, the way taskerd does.

    Same shape as test_mapswap._load, against a real backup rather than fixture text --
    the Event tabs resolve their Task through these tables, so a hand-built stub would not
    exercise the lookup that matters.
    """
    from maptasker.src import taskerd  # noqa: PLC0415

    root = ET.parse(path).getroot()  # noqa: S314  (this repo's own sample data)
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100, "language": "English"}
    PrimeItems.tasker_arg_specs = _load_arg_specs()
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items()
    }
    PrimeItems.tasker_root_elements.update(tables)
    return root


def _descendants(element):
    """Every widget under this one, itself included."""
    yield element
    for child in element.default_slot.children:
        yield from _descendants(child)


def _render(gui, target, render, *args):
    """Build one piece of the Scene Properties screen and hand back its container.

    The throwaway Client is not optional.  NiceGUI conjures one up on its own only while no
    Client exists at all, and by the time the whole suite has run one does, so a bare
    ui.column() here fails with "the slot stack for this task is empty" -- but only when
    this file is not run alone, which is the worst way for it to fail.
    """
    ui = pytest.importorskip("nicegui").ui
    from nicegui.client import Client  # noqa: PLC0415
    from nicegui.page import page  # noqa: PLC0415

    with Client(page("/")):
        container = ui.column()
        with container:
            render(gui, target, *args)
    return container


@pytest.fixture
def sample_backup():
    """A loaded backup, put back exactly as it was afterwards."""
    saved = dict(PrimeItems.tasker_root_elements)
    saved_specs = dict(PrimeItems.tasker_arg_specs)
    saved_args = dict(PrimeItems.program_arguments)
    yield _load_sample_backup
    PrimeItems.tasker_root_elements.clear()
    PrimeItems.tasker_root_elements.update(saved)
    PrimeItems.tasker_arg_specs = saved_specs
    PrimeItems.program_arguments = saved_args


@pytest.fixture
def stub_gui():
    """Enough of a MyGui for the forms: they read .indent and hold .event_handlers in a
    lambda that no test presses.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    gui = MagicMock()
    gui.indent = 4
    return gui


def _scene_with(root: ET.Element, predicate) -> ET.Element:
    """The first sample Scene whose <PropertiesElement> satisfies `predicate`."""
    for scene in root.iter("Scene"):
        properties = scene.find("PropertiesElement")
        if properties is not None and predicate(properties):
            return properties
    return None


@pytest.fixture
def key_event_tab(sample_backup, stub_gui):
    """The Event tab's Key panel, over the first sample Scene that fires a key Task."""
    from maptasker.src import guiwins  # noqa: PLC0415

    root = sample_backup("XML/Smart Reminders.prj.xml")
    properties = _scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None)
    if properties is None:
        pytest.skip("no sample Scene with a key Task")

    key_event = sceneedit.LEGACY_SCENE_EVENTS[0]
    container = _render(stub_gui, properties, guiwins._render_scene_event, key_event, lambda: None)
    return container, properties, pytest.importorskip("nicegui").ui


def test_the_screen_has_taskers_own_three_tabs(sample_backup, stub_gui):
    """UI, Actions and Event, in the guide's order -- and named in English whatever the
    labels are translated to, since the selected-tab bookkeeping is keyed on the name.
    """
    ui = pytest.importorskip("nicegui").ui
    from unittest.mock import MagicMock  # noqa: PLC0415

    from maptasker.src import guiwins  # noqa: PLC0415

    root = sample_backup("XML/Smart Reminders.prj.xml")
    scene = next(s for s in root.iter("Scene") if s.find("PropertiesElement") is not None)
    edited = MagicMock()
    edited.scene_element = scene
    edited.scene_name = scene.findtext("nme", "")

    opened = []
    original_open = ui.dialog.open
    ui.dialog.open = lambda self: opened.append(self)
    try:
        _render(stub_gui, edited, lambda gui, target: guiwins._build_scene_properties_dialog(gui, target, {}))
    finally:
        ui.dialog.open = original_open

    names = [tab._props.get("name") for tab in _descendants(opened[-1]) if isinstance(tab, ui.tab)]
    assert names[:3] == ["UI", "Actions", "Event"]
    assert names[3:] == [event.label for event in sceneedit.LEGACY_SCENE_EVENTS] == ["Key", "Home Tap", "Tab Tap"]


def test_the_key_panel_offers_the_keys_filter_and_stop_event(key_event_tab):
    """The guide's two filter controls, both stored in the same <LinkClickFilter>."""
    container, properties, ui = key_event_tab

    keys = [e for e in _descendants(container) if isinstance(e, ui.input) and e._props.get("label") == "Keys"]
    assert len(keys) == 1
    assert keys[0].value == sceneedit.legacy_key_filter(properties)

    boxes = [e for e in _descendants(container) if isinstance(e, ui.checkbox) and e.text == "Stop Event"]
    assert len(boxes) == 1
    assert boxes[0].value is sceneedit.legacy_stop_event(properties)


def test_both_key_filter_controls_write_through_as_the_rest_of_the_dialog_does(key_event_tab):
    """No Ok to press: the Scene Properties dialog writes to the Scene copy as it is typed."""
    container, properties, ui = key_event_tab
    keys = next(e for e in _descendants(container) if isinstance(e, ui.input) and e._props.get("label") == "Keys")
    box = next(e for e in _descendants(container) if isinstance(e, ui.checkbox) and e.text == "Stop Event")

    keys.value = "back/78/a"
    assert sceneedit.legacy_key_filter(properties) == "back/78/a"
    box.value = False
    assert sceneedit.legacy_stop_event(properties) is False
    box.value = True
    assert sceneedit.legacy_stop_event(properties) is True


def test_the_key_panel_documents_the_variables_the_guide_lists(key_event_tab):
    container, _properties, ui = key_event_tab
    text = " ".join(e.text for e in _descendants(container) if isinstance(e, ui.label))
    assert "%key_code" in text
    assert "%key_name" in text


def test_the_bound_tasks_actions_are_listed_below_it(key_event_tab):
    """The bound Task's actions, in the editor the Edit Task dialog is made of."""
    container, properties, ui = key_event_tab
    expected = taskedit.load_task_for_edit_by_id(properties.findtext(sceneedit.LEGACY_KEY_TASK_TAG))

    headers = [e._props.get("label", "") for e in _descendants(container) if isinstance(e, ui.expansion)]

    assert len(headers) == len(expected.actions)
    for action, header in zip(expected.actions, headers, strict=True):
        assert header.strip().startswith(f"{action.act_number}: {action.action_name}")


def test_the_action_picker_comes_with_it(key_event_tab):
    """_build_task_action_editor renders the Edit Task dialog's own "Add an action" search,
    which is what "added in the same fashion" means here.
    """
    container, _properties, ui = key_event_tab
    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Add an action" in labels
    assert any(label.startswith("Actions of the") for label in labels)


def test_an_event_with_no_task_says_so_and_still_offers_the_filter(sample_backup, stub_gui):
    """Swallowing the Back key without running anything is a real thing to want, so the
    panel must not go blank just because nothing is bound.
    """
    from maptasker.src import guiwins  # noqa: PLC0415

    ui = pytest.importorskip("nicegui").ui
    root = sample_backup("XML/Smart Reminders.prj.xml")
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None))
    properties.remove(properties.find(sceneedit.LEGACY_KEY_TASK_TAG))

    container = _render(
        stub_gui,
        properties,
        guiwins._render_scene_event,
        sceneedit.LEGACY_SCENE_EVENTS[0],
        lambda: None,
    )

    assert [e for e in _descendants(container) if isinstance(e, ui.checkbox) and e.text == "Stop Event"]
    shown = [e.value for e in _descendants(container) if isinstance(e, ui.input) and e._props.get("label") is None]
    assert shown[0] == "Nothing -- this event fires no Task."


def test_an_event_the_scene_type_rules_out_still_shows_what_is_bound(sample_backup, stub_gui):
    """A Scene switched away from Activity keeps its <iconclickTask>, and hiding a binding
    the file holds is how an editor comes to disagree with the file.  It is shown with the
    reason it no longer applies.
    """
    from maptasker.src import guiwins  # noqa: PLC0415

    ui = pytest.importorskip("nicegui").ui
    root = sample_backup("XML/Smart Reminders.prj.xml")
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None))
    properties.find(f"Int[@sr='arg{sceneedit.LEGACY_PROPERTY_TYPE_ARG}']").set(
        "val",
        sceneedit.LEGACY_SCENE_TYPE_OVERLAY,
    )
    home_tap = sceneedit.LEGACY_SCENE_EVENTS[1]
    sceneedit.legacy_set_task_binding(properties, home_tap.tag, properties.findtext(sceneedit.LEGACY_KEY_TASK_TAG))

    container = _render(stub_gui, properties, guiwins._render_scene_event, home_tap, lambda: None)

    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Available only for Activity scenes." in labels
    # ...and the binding is still on screen: its Task's actions are listed.
    assert [e for e in _descendants(container) if isinstance(e, ui.expansion)]


# ==========================================
# 5b. THE ACTIONS TAB
# ==========================================
@pytest.fixture
def actions_tab(sample_backup, stub_gui):
    """The Actions tab over the first sample Scene that has action bar items."""
    from maptasker.src import guiwins  # noqa: PLC0415

    root = sample_backup("XML/backup_full.xml")
    properties = _scene_with(root, lambda p: p.find(sceneedit.LEGACY_ACTION_ITEM_TAG) is not None)
    if properties is None:
        pytest.skip("no sample Scene with action bar items")
    properties = copy.deepcopy(properties)

    container = _render(stub_gui, properties, guiwins._render_scene_actions_tab, lambda: None)
    return container, properties, pytest.importorskip("nicegui").ui


def test_every_action_bar_item_gets_a_row(actions_tab):
    container, properties, ui = actions_tab
    items = sceneedit.legacy_action_items(properties)
    headers = [e._props.get("label", "") for e in _descendants(container) if isinstance(e, ui.expansion)]
    assert len(headers) == len(items)
    for item, header in zip(items, headers, strict=True):
        assert header.startswith(f"{item.index}: ")
        assert item.action_name in header


def test_each_row_carries_the_guides_three_controls(actions_tab):
    """"icon button", "label text" and "action button" -- an icon field, a label field, and
    the item's action with its own arguments.
    """
    container, properties, ui = actions_tab
    item = sceneedit.legacy_action_items(properties)[0]
    labelled = {e._props.get("label"): e for e in _descendants(container) if isinstance(e, ui.input)}

    assert labelled["Icon"].value == sceneedit.legacy_action_item_icon(item)
    assert labelled["Label"].value == item.label
    assert item.action_name in " ".join(e.text for e in _descendants(container) if isinstance(e, ui.label))


def test_the_icon_and_label_fields_write_through(actions_tab):
    container, properties, ui = actions_tab
    labelled = {e._props.get("label"): e for e in _descendants(container) if isinstance(e, ui.input)}

    labelled["Label"].value = "Renamed"
    labelled["Icon"].value = "mw_action_alarm"

    item = sceneedit.legacy_action_items(properties)[0]
    assert item.label == "Renamed"
    assert sceneedit.legacy_action_item_icon(item) == "mw_action_alarm"


def test_the_tab_says_where_each_item_will_end_up(actions_tab):
    """Tasker decides main-bar vs overflow from what the item has been given and stores
    nothing about it, so the editor has to say so or the rules are invisible.
    """
    container, properties, ui = actions_tab
    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    for item in sceneedit.legacy_action_items(properties):
        assert item.placement in labels


def test_the_tab_offers_the_plus_button_the_guide_describes(actions_tab):
    container, _properties, ui = actions_tab
    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Add an action bar item" in labels


def test_a_scene_that_is_not_an_activity_is_told_so_but_keeps_its_items(sample_backup, stub_gui):
    """The guide says the Actions tab is Activity-only.  Items already in the file are still
    shown, or an editor would quietly drop them on the next save.
    """
    from maptasker.src import guiwins  # noqa: PLC0415

    ui = pytest.importorskip("nicegui").ui
    root = sample_backup("XML/backup_full.xml")
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_ACTION_ITEM_TAG) is not None))
    properties.find(f"Int[@sr='arg{sceneedit.LEGACY_PROPERTY_TYPE_ARG}']").set(
        "val",
        sceneedit.LEGACY_SCENE_TYPE_DIALOG,
    )

    container = _render(stub_gui, properties, guiwins._render_scene_actions_tab, lambda: None)

    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert any("Activity only" in label for label in labels)
    assert len([e for e in _descendants(container) if isinstance(e, ui.expansion)]) == len(
        sceneedit.legacy_action_items(properties),
    )


# ==========================================
# 6. APPLYING FROM THE TAB
# ==========================================
def test_apply_to_task_puts_the_action_edits_into_the_loaded_configuration(monkeypatch, loaded_tasks):
    """"Apply to Task" is the tab's Ok: the working copy replaces the live one in the Task
    tables, so every view built from them shows the edit.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    from maptasker.src import userintr  # noqa: PLC0415

    notified = []
    monkeypatch.setattr(userintr.ui, "notify", lambda message, **kwargs: notified.append((message, kwargs.get("type"))))

    handlers = userintr.MapTaskerEventHandlers(MagicMock())
    edited = taskedit.load_task_for_edit_by_id("268")
    key = taskedit.arg_key(edited.actions[0].act_number, "0")

    handlers.apply_scene_key_task_event(edited, {key: MagicMock(value="goodbye")})

    live = PrimeItems.tasker_root_elements["all_tasks"]["268"]["xml"]
    assert live.find("Action/Str[@sr='arg0']").text == "goodbye"
    assert notified[-1][1] == "positive"


def test_a_rejected_value_is_reported_and_nothing_is_applied(monkeypatch, loaded_tasks):
    """All-or-nothing, like the Edit Task dialog's Ok: a validation error leaves the loaded
    configuration exactly as it was.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    from maptasker.src import userintr  # noqa: PLC0415

    notified = []
    monkeypatch.setattr(userintr.ui, "notify", lambda message, **kwargs: notified.append((message, kwargs.get("type"))))
    monkeypatch.setattr(taskedit, "apply_action_edits_to_task", lambda *_a, **_k: ["Nope."])
    applied = []
    monkeypatch.setattr(taskedit, "apply_edited_task_to_live_tree", lambda task: applied.append(task))

    handlers = userintr.MapTaskerEventHandlers(MagicMock())
    handlers.apply_scene_key_task_event(taskedit.load_task_for_edit_by_id("268"), {})

    assert applied == []
    assert notified == [("Nope.", "negative")]


# ==========================================
# 7. THE EDITOR THE TWO SURFACES SHARE
# ==========================================
def test_the_edit_task_dialog_still_builds_after_the_editor_was_lifted_out_of_it(monkeypatch):
    """_build_task_action_editor was cut out of build_edit_task_dialog so the KEY tab could
    render the same thing.  This is the guard on that surgery: the dialog it came from has
    to still build, over real Tasks, with every action listed.
    """
    ui = pytest.importorskip("nicegui").ui
    from unittest.mock import MagicMock  # noqa: PLC0415

    from nicegui.client import Client  # noqa: PLC0415
    from nicegui.page import page  # noqa: PLC0415

    from maptasker.src import guiwins  # noqa: PLC0415

    saved = dict(PrimeItems.tasker_root_elements)
    saved_specs = dict(PrimeItems.tasker_arg_specs)
    saved_args = dict(PrimeItems.program_arguments)
    try:
        _load_sample_backup("XML/Smart Reminders.prj.xml")
        # A Task with a real name and something in it -- an empty one would prove nothing.
        named = [
            name
            for name in PrimeItems.tasker_root_elements["all_tasks_by_name"]
            if name and "(Unnamed)" not in name
        ]
        if not named:
            pytest.skip("no named Tasks in the sample backup")

        gui = MagicMock()
        gui.indent = 4
        opened = []
        monkeypatch.setattr(ui.dialog, "open", lambda self: opened.append(self))

        for task_name in named[:5]:
            edited = taskedit.load_task_for_edit(task_name)
            with Client(page("/")):
                guiwins.build_edit_task_dialog(gui, edited)
            headers = [e._props.get("label", "") for e in _descendants(opened[-1]) if isinstance(e, ui.expansion)]
            assert len(headers) == len(edited.actions), task_name
    finally:
        PrimeItems.tasker_root_elements.clear()
        PrimeItems.tasker_root_elements.update(saved)
        PrimeItems.tasker_arg_specs = saved_specs
        PrimeItems.program_arguments = saved_args


# ==========================================
# 8. THE KEYS FILTER
# ==========================================
def test_the_keys_filter_reads_the_slash_separated_list():
    """The guide's Keys field.  It is stored in <urlMatch> -- a tag named for the Web element
    the same <LinkClickFilter> serves elsewhere -- and its sample values are key names.
    """
    assert sceneedit.legacy_key_filter(_properties(_SCENE_XML)) == "back/home"


def test_no_filter_means_every_key_is_handled():
    assert sceneedit.legacy_key_filter(_properties(_SCENE_XML_NO_FILTER)) == ""


def test_setting_the_keys_filter_on_a_scene_with_no_filter_builds_one():
    properties = _properties(_SCENE_XML_NO_FILTER)
    sceneedit.legacy_set_key_filter(properties, "back/78/a")

    link_filter = properties.find("LinkClickFilter")
    assert link_filter.attrib == {"sr": "filter0"}
    assert link_filter.findtext("urlMatch") == "back/78/a"
    assert list(properties)[-1] is link_filter


def test_clearing_the_keys_filter_takes_an_emptied_filter_with_it():
    properties = _properties(_SCENE_XML_NO_FILTER)
    before = ET.tostring(properties)

    sceneedit.legacy_set_key_filter(properties, "back")
    sceneedit.legacy_set_key_filter(properties, "")

    assert ET.tostring(properties) == before


def test_clearing_the_keys_filter_keeps_a_filter_that_still_stops_the_event():
    """The two controls share one element and neither owns the other."""
    properties = _properties(_SCENE_XML)
    sceneedit.legacy_set_key_filter(properties, "")

    assert sceneedit.legacy_stop_event(properties) is True
    assert properties.find("LinkClickFilter/urlMatch") is None


def test_the_two_key_controls_are_written_in_taskers_order():
    """<stopEvent> then <urlMatch>, whichever is set first -- the order all 72 samples
    carrying both are in."""
    properties = _properties(_SCENE_XML_NO_FILTER)
    sceneedit.legacy_set_key_filter(properties, "back")
    sceneedit.legacy_set_stop_event(properties, enabled=True)

    assert [child.tag for child in properties.find("LinkClickFilter")] == ["stopEvent", "urlMatch"]


def test_setting_the_keys_filter_to_what_it_already_is_leaves_every_sample_byte_identical():
    samples = _sample_properties_elements()
    if not samples:
        pytest.skip("no sample XML available")

    for properties in samples:
        before = ET.tostring(properties)
        sceneedit.legacy_set_key_filter(properties, sceneedit.legacy_key_filter(properties))
        assert ET.tostring(properties) == before


# ==========================================
# 9. WHICH EVENTS TASKER OFFERS
# ==========================================
def _typed(scene_type: str, **args) -> ET.Element:
    """A <PropertiesElement> of the given Property Type, optionally with UI args filled in."""
    properties = _properties(_SCENE_XML_NO_FILTER)
    # _SCENE_XML_NO_FILTER already carries arg0; setting the one that is there is the point,
    # since legacy_scene_type reads the first match and a second would never be seen.
    properties.find(f"Int[@sr='arg{sceneedit.LEGACY_PROPERTY_TYPE_ARG}']").set("val", scene_type)
    for arg_id, value in args.items():
        ET.SubElement(properties, "Str", {"sr": f"arg{arg_id}", "ve": "3"}).text = value
    return properties


_KEY, _HOME_TAP, _TAB_TAP = sceneedit.LEGACY_SCENE_EVENTS


def test_the_three_event_tabs_are_the_guides_three():
    assert [event.label for event in sceneedit.LEGACY_SCENE_EVENTS] == ["Key", "Home Tap", "Tab Tap"]


def test_key_is_for_dialogs_and_activities_only():
    """"Available only for Dialog and Activity scenes." """
    assert sceneedit.legacy_scene_event_availability(_typed(sceneedit.LEGACY_SCENE_TYPE_DIALOG), _KEY) == ""
    assert sceneedit.legacy_scene_event_availability(_typed(sceneedit.LEGACY_SCENE_TYPE_ACTIVITY), _KEY) == ""
    assert (
        sceneedit.legacy_scene_event_availability(_typed(sceneedit.LEGACY_SCENE_TYPE_OVERLAY), _KEY)
        == "Available only for Dialog and Activity scenes."
    )


def test_home_tap_needs_an_activity_and_an_icon():
    """"Available only for Activity scenes and when an Icon has been specified in the UI tab." """
    activity = _typed(sceneedit.LEGACY_SCENE_TYPE_ACTIVITY)
    assert (
        sceneedit.legacy_scene_event_availability(activity, _HOME_TAP)
        == "Available only when Icon has been set in the UI tab."
    )

    icon = ET.SubElement(activity, "Img", {"sr": f"arg{sceneedit.LEGACY_ICON_ARG}", "ve": "2"})
    ET.SubElement(icon, "nme").text = "mw_action_settings"
    assert sceneedit.legacy_scene_event_availability(activity, _HOME_TAP) == ""

    dialog = _typed(sceneedit.LEGACY_SCENE_TYPE_DIALOG)
    assert (
        sceneedit.legacy_scene_event_availability(dialog, _HOME_TAP) == "Available only for Activity scenes."
    )


def test_tab_tap_needs_an_activity_and_tab_labels():
    """"Available only for Activity scenes and when one or more Tab Labels have been
    specified in the UI tab." -- and an empty <Str sr="arg7" /> is not a Tab Label, which is
    what every Scene in the sample data that has none carries.
    """
    activity = _typed(sceneedit.LEGACY_SCENE_TYPE_ACTIVITY, **{sceneedit.LEGACY_TAB_LABELS_ARG: ""})
    assert (
        sceneedit.legacy_scene_event_availability(activity, _TAB_TAP)
        == "Available only when Tab Labels has been set in the UI tab."
    )

    activity.find(f"Str[@sr='arg{sceneedit.LEGACY_TAB_LABELS_ARG}']").text = "Call Log,Truecaller"
    assert sceneedit.legacy_scene_event_availability(activity, _TAB_TAP) == ""


def test_the_events_carry_the_variables_the_guide_lists():
    assert [name for name, _ in _KEY.variables] == ["%key_code", "%key_name"]
    assert [name for name, _ in _TAB_TAP.variables] == ["%tap_index", "%tap_label"]
    assert [name for name, _ in sceneedit.LEGACY_SCENE_EVENT_COMMON_VARIABLES] == ["%scene_name", "%event_type"]


def test_every_sample_event_binding_is_one_the_editor_offers():
    """The mapping this all rests on: the only Task tags on a sample <PropertiesElement> are
    the three Event tabs.  A fourth turning up means the guide has more tabs than this table.
    """
    samples = _sample_properties_elements()
    if not samples:
        pytest.skip("no sample XML available")

    known = {event.tag for event in sceneedit.LEGACY_SCENE_EVENTS}
    seen = {child.tag for properties in samples for child in properties if child.tag.endswith("Task")}
    assert seen <= known, seen - known


def test_tab_tap_is_the_tag_every_sample_with_tab_labels_carries():
    """<itemselectedTask> means "Item Selected" on a Spinner and Tab Tap here.  What settles
    it is the data: every sample whose Tab Labels are set has one, and all of them are on an
    Activity.
    """
    samples = _sample_properties_elements()
    if not samples:
        pytest.skip("no sample XML available")

    with_labels = [
        properties
        for properties in samples
        if (properties.findtext(f"Str[@sr='arg{sceneedit.LEGACY_TAB_LABELS_ARG}']") or "").strip()
    ]
    if not with_labels:
        pytest.skip("no sample Scene sets Tab Labels")

    for properties in with_labels:
        assert properties.find(_TAB_TAP.tag) is not None
        assert sceneedit.legacy_scene_type(properties) == sceneedit.LEGACY_SCENE_TYPE_ACTIVITY


# ==========================================
# 10. THE ACTION BAR ITEMS
# ==========================================
@pytest.fixture
def sample_action_items(sample_backup):
    """A deep copy of the sample <PropertiesElement> with the most action bar items."""
    root = sample_backup("XML/backup_full.xml")
    best = None
    for properties in root.iter("PropertiesElement"):
        count = len(properties.findall(sceneedit.LEGACY_ACTION_ITEM_TAG))
        if count and (best is None or count > len(best.findall(sceneedit.LEGACY_ACTION_ITEM_TAG))):
            best = properties
    if best is None:
        pytest.skip("no sample Scene with action bar items")
    return copy.deepcopy(best)


def test_the_items_read_as_the_guides_three_controls(sample_action_items):
    items = sceneedit.legacy_action_items(sample_action_items)
    assert items
    for index, item in enumerate(items):
        assert item.index == index
        assert item.sr == f"item{index}"
        assert item.action_element is not None


def test_the_placement_follows_taskers_overflow_rules():
    """"just an icon" -> main bar; "icon and label" -> if there is room; "just a label" ->
    overflow.  Tasker stores none of this, so it is derived or it is invisible.
    """
    make = lambda icon, label: sceneedit.LegacyActionItem(  # noqa: E731
        element=None,
        sr="item0",
        index=0,
        label=label,
        icon=icon,
        action_element=None,
        action_name="",
    )
    assert make("star", "").placement == "always in the main bar"
    assert make("star", "Go").placement == "in the main bar if there is room"
    assert make("", "Go").placement == "always in the overflow menu"
    assert make("", "").placement == "nowhere -- give it an icon or a label"


def test_adding_an_item_builds_one_tasker_would_recognise(sample_action_items):
    added = sceneedit.legacy_add_action_item(sample_action_items, "548t")  # Flash
    assert not isinstance(added, list), added

    items = sceneedit.legacy_action_items(sample_action_items)
    assert items[-1].sr == added.sr
    assert items[-1].action_name == "Flash"
    element = items[-1].element
    assert [child.tag for child in element][:2] == ["label", "Action"]
    assert element.find("Action").get("sr") == "action"
    assert element.find("Action").findtext("code") == "548"


def test_an_action_that_cannot_be_synthesized_is_refused_with_a_reason(sample_action_items):
    """Same rule as Add Task's picker, because it is the same code -- so an action the picker
    greys out cannot slip in by another route.
    """
    from maptasker.src.taskedit import classify_action_addability, list_addable_actions  # noqa: PLC0415

    refused = next(
        (row["action_key"] for row in list_addable_actions() if not row["addable"]),
        None,
    )
    if refused is None:
        pytest.skip("every action is addable in this build")
    before = ET.tostring(sample_action_items)

    result = sceneedit.legacy_add_action_item(sample_action_items, refused)

    assert isinstance(result, list) and result
    assert result[0] == classify_action_addability(refused)[1]
    assert ET.tostring(sample_action_items) == before


def test_items_stay_numbered_in_order_through_every_change(sample_action_items):
    sceneedit.legacy_add_action_item(sample_action_items, "548t")
    order = [item.label for item in sceneedit.legacy_action_items(sample_action_items)]

    sceneedit.legacy_move_action_item(sample_action_items, "item1", 1)
    moved = [item.label for item in sceneedit.legacy_action_items(sample_action_items)]
    assert moved == [order[0], order[2], order[1], *order[3:]]

    sceneedit.legacy_remove_action_item(sample_action_items, "item0")
    remaining = sceneedit.legacy_action_items(sample_action_items)
    assert [item.label for item in remaining] == moved[1:]
    assert [item.sr for item in remaining] == [f"item{i}" for i in range(len(remaining))]


def test_moving_past_either_end_does_nothing(sample_action_items):
    before = [item.label for item in sceneedit.legacy_action_items(sample_action_items)]
    last = f"item{len(before) - 1}"

    sceneedit.legacy_move_action_item(sample_action_items, "item0", -1)
    sceneedit.legacy_move_action_item(sample_action_items, last, 1)

    assert [item.label for item in sceneedit.legacy_action_items(sample_action_items)] == before


def test_the_items_stay_after_everything_else_in_the_element(sample_action_items):
    """Tasker writes the bindings, then the arguments, then the filter, then the items."""
    sceneedit.legacy_add_action_item(sample_action_items, "548t")
    tags = [child.tag for child in sample_action_items]
    first_item = tags.index(sceneedit.LEGACY_ACTION_ITEM_TAG)
    assert set(tags[first_item:]) == {sceneedit.LEGACY_ACTION_ITEM_TAG}


def test_an_items_icon_round_trips_through_the_field(sample_action_items):
    item = sceneedit.legacy_action_items(sample_action_items)[0]

    sceneedit.legacy_set_action_item_icon(item, "mw_action_alarm")
    assert sceneedit.legacy_action_item_icon(sceneedit.legacy_action_items(sample_action_items)[0]) == (
        "mw_action_alarm"
    )


def test_blanking_an_items_icon_removes_the_img_rather_than_emptying_it(sample_action_items):
    """37 of the 42 sample items have no <Img> at all, so absence is how "no icon" is stored
    -- and it is what the guide's "just a label" placement is read from.
    """
    item = sceneedit.legacy_action_items(sample_action_items)[0]
    sceneedit.legacy_set_action_item_icon(item, "mw_action_alarm")

    sceneedit.legacy_set_action_item_icon(item, "")

    assert item.element.find("Img[@sr='icon']") is None
    assert sceneedit.legacy_action_items(sample_action_items)[0].placement in (
        "always in the overflow menu",
        "nowhere -- give it an icon or a label",
    )


def test_an_items_label_is_kept_even_when_blanked(sample_action_items):
    """Every one of the 42 samples has a <label>, and an icon-only item is a real thing."""
    item = sceneedit.legacy_action_items(sample_action_items)[0]
    sceneedit.legacy_set_action_item_label(item, "")
    assert item.element.find("label") is not None
    assert sceneedit.legacy_action_items(sample_action_items)[0].label == ""


# ==========================================
# 11. "PICK A TASK", BUILT LIKE "ADD AN ACTION"
# ==========================================
_PICKER_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0"><name>Alpha</name><tids>1,2</tids></Project>
  <Project sr="proj1"><name>Beta</name><tids>3,2</tids></Project>
  <Task sr="task1"><id>1</id><nme>Wake Up</nme></Task>
  <Task sr="task2"><id>2</id><nme>Shared Setup</nme></Task>
  <Task sr="task3"><id>3</id><nme>beta only</nme></Task>
  <Task sr="task4"><id>4</id><nme>Orphan</nme></Task>
</TaskerData>"""


@pytest.fixture
def picker_tables():
    """Four Tasks across two Projects, one of them owned by both and one by neither."""
    from maptasker.src import taskerd  # noqa: PLC0415

    saved = dict(PrimeItems.tasker_root_elements)
    root = ET.fromstring(_PICKER_XML)  # noqa: S314  (fixture text, defined in this file)
    tables = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
    }
    tables["all_tasks_by_name"] = {
        task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items()
    }
    PrimeItems.tasker_root_elements.update(tables)
    yield
    PrimeItems.tasker_root_elements.clear()
    PrimeItems.tasker_root_elements.update(saved)


def test_every_task_is_listed_once_with_the_project_that_owns_it(picker_tables):
    rows = taskedit.list_pickable_tasks()
    assert [(row["name"], row["project_name"]) for row in rows] == [
        ("beta only", "Beta"),
        ("Orphan", taskedit.NO_PROJECT_NAME),
        ("Shared Setup", "Alpha"),
        ("Wake Up", "Alpha"),
    ]


def test_the_list_is_sorted_the_way_a_reader_expects(picker_tables):
    """Case-insensitively, so "beta only" is not exiled below every capitalised name."""
    names = [row["name"] for row in taskedit.list_pickable_tasks()]
    assert names == sorted(names, key=str.lower)


def test_searching_matches_part_of_a_name_whatever_its_case(picker_tables):
    assert [row["name"] for row in taskedit.search_pickable_tasks("SETUP")] == ["Shared Setup"]
    assert [row["name"] for row in taskedit.search_pickable_tasks("o")] == ["beta only", "Orphan"]


def test_filtering_by_project_narrows_to_that_project(picker_tables):
    assert [row["name"] for row in taskedit.search_pickable_tasks("", "Beta")] == ["beta only"]
    assert [row["name"] for row in taskedit.search_pickable_tasks("", taskedit.NO_PROJECT_NAME)] == ["Orphan"]
    assert len(taskedit.search_pickable_tasks("", "All")) == 4


def test_the_two_filters_apply_together(picker_tables):
    assert [row["name"] for row in taskedit.search_pickable_tasks("shared", "Alpha")] == ["Shared Setup"]
    assert taskedit.search_pickable_tasks("shared", "Beta") == []


def test_the_list_is_live_rather_than_memoized(picker_tables):
    """A Task added through the Add Task dialog has to show up in the picker at once -- which
    is why this one is not cached the way list_addable_actions is.
    """
    before = len(taskedit.list_pickable_tasks())
    PrimeItems.tasker_root_elements["all_tasks_by_name"]["Brand New"] = {"xml": None, "id": "9"}
    assert len(taskedit.list_pickable_tasks()) == before + 1


def _click(button) -> None:
    """Fire a NiceGUI button's click handler, the way the browser would."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    for listener in button._event_listeners.values():
        if listener.type == "click":
            listener.handler(MagicMock())
            return
    raise AssertionError("button has no click handler")


def test_the_event_panel_picks_a_task_the_way_add_an_action_picks_one(key_event_tab):
    """A search box, a filter and a scrolling list of clickable rows -- not a dropdown."""
    container, _properties, ui = key_event_tab

    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Pick a Task" in labels

    searches = [e for e in _descendants(container) if isinstance(e, ui.input)]
    assert "Search Tasks" in [e._props.get("label") for e in searches]

    rows = taskedit.list_pickable_tasks()
    buttons = [
        e._props.get("label")
        for e in _descendants(container)
        if isinstance(e, ui.button) and e._props.get("label")
    ]
    for row in rows:
        assert f"{row['name']} ({row['project_name']})" in buttons


def test_the_picker_offers_a_project_filter(key_event_tab):
    """The Task-side counterpart of the action picker's Category dropdown."""
    container, _properties, ui = key_event_tab
    projects = sorted({row["project_name"] for row in taskedit.list_pickable_tasks()})
    options = [e.options for e in _descendants(container) if isinstance(e, ui.select)]
    assert ["All", *projects] in options


def _task_rows_on_screen(container, ui) -> set:
    """The picker's own rows, told apart from the action editor's buttons below it by being
    labelled like a Task rather than like an action.
    """
    every = {f"{row['name']} ({row['project_name']})" for row in taskedit.list_pickable_tasks()}
    return {
        e._props.get("label")
        for e in _descendants(container)
        if isinstance(e, ui.button) and e._props.get("label") in every
    }


def test_typing_in_the_search_box_narrows_the_rows(key_event_tab):
    container, _properties, ui = key_event_tab
    wanted = taskedit.list_pickable_tasks()[0]["name"]

    search = next(
        e for e in _descendants(container) if isinstance(e, ui.input) and e._props.get("label") == "Search Tasks"
    )
    search.value = wanted

    matches = taskedit.search_pickable_tasks(wanted)
    assert 0 < len(matches) < len(taskedit.list_pickable_tasks()), "the search must actually narrow"
    assert _task_rows_on_screen(container, ui) == {
        f"{row['name']} ({row['project_name']})" for row in matches
    }


def test_choosing_a_project_narrows_the_rows(key_event_tab):
    container, _properties, ui = key_event_tab
    project = taskedit.list_pickable_tasks()[0]["project_name"]

    project_select = next(
        e for e in _descendants(container) if isinstance(e, ui.select) and e.options[:1] == ["All"]
    )
    project_select.value = project

    matches = taskedit.search_pickable_tasks("", project)
    everything = taskedit.list_pickable_tasks()
    if len({row["project_name"] for row in everything}) > 1:
        # Only a real narrowing when the sample has more than one Project to narrow to; this
        # one has every Task under "Smart Reminders", where the right answer is all of them.
        assert len(matches) < len(everything)
    assert matches
    assert _task_rows_on_screen(container, ui) == {
        f"{row['name']} ({row['project_name']})" for row in matches
    }


def test_clicking_a_row_binds_that_task_to_the_event(key_event_tab):
    container, properties, ui = key_event_tab
    rerendered = []
    # The panel was built with a no-op rerender; rebuild it with one we can watch.
    from maptasker.src import guiwins  # noqa: PLC0415
    from unittest.mock import MagicMock  # noqa: PLC0415

    gui = MagicMock()
    gui.indent = 4
    with container:
        panel = ui.column()
    with panel:
        guiwins._render_scene_event(
            gui,
            properties,
            sceneedit.LEGACY_SCENE_EVENTS[0],
            lambda: rerendered.append(1),
        )

    wanted = next(
        row for row in taskedit.list_pickable_tasks() if row["task_id"] != properties.findtext("keyTask")
    )
    button = next(
        e
        for e in _descendants(panel)
        if isinstance(e, ui.button)
        and e._props.get("label") == f"{wanted['name']} ({wanted['project_name']})"
    )

    _click(button)

    assert properties.findtext(sceneedit.LEGACY_KEY_TASK_TAG) == wanted["task_id"]
    assert rerendered == [1]


def test_an_anonymous_binding_is_not_offered_a_picker(sample_backup, stub_gui):
    """It cannot be pointed anywhere else without losing it, so there is nothing to pick."""
    from maptasker.src import guiwins  # noqa: PLC0415

    ui = pytest.importorskip("nicegui").ui
    root = sample_backup("XML/Smart Reminders.prj.xml")
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None))
    properties.find(sceneedit.LEGACY_KEY_TASK_TAG).text = "-1"

    container = _render(
        stub_gui,
        properties,
        guiwins._render_scene_event,
        sceneedit.LEGACY_SCENE_EVENTS[0],
        lambda: None,
    )

    assert "Pick a Task" not in [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Search Tasks" not in [
        e._props.get("label") for e in _descendants(container) if isinstance(e, ui.input)
    ]


def test_the_bound_task_is_named_even_when_its_entry_has_no_name(sample_backup, stub_gui):
    """A binding must never read as "Nothing" just because the Task tables carry a blank name
    for it -- what is bound and what it is called are two different questions.
    """
    from maptasker.src import guiwins  # noqa: PLC0415

    ui = pytest.importorskip("nicegui").ui
    root = sample_backup("XML/Smart Reminders.prj.xml")
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None))
    task_id = properties.findtext(sceneedit.LEGACY_KEY_TASK_TAG)
    PrimeItems.tasker_root_elements["all_tasks"][task_id]["name"] = ""

    container = _render(
        stub_gui,
        properties,
        guiwins._render_scene_event,
        sceneedit.LEGACY_SCENE_EVENTS[0],
        lambda: None,
    )

    shown = [e.value for e in _descendants(container) if isinstance(e, ui.input) and e._props.get("label") is None]
    assert shown[0] == f"Task {task_id}"


def test_a_task_with_no_name_is_left_out_of_the_picker(picker_tables):
    """Every caller picks a Task BY NAME, so a nameless row is one that does nothing when it
    is clicked.  taskerd normally invents a display name for exactly this reason.
    """
    PrimeItems.tasker_root_elements["all_tasks_by_name"][""] = {"xml": None, "id": "9"}

    assert "" not in [row["name"] for row in taskedit.list_pickable_tasks()]


# ==========================================
# 12. COMPOSING A NEW TASK UNDER AN EVENT SUB-TAB
# ==========================================
@pytest.fixture
def unbound_event(sample_backup, stub_gui, monkeypatch):
    """A Scene's properties with every event binding removed, and the machinery to render
    one of its Event sub-tabs.

    Returns (render_event, properties, scene_name, pending, notified) where render_event(event)
    builds that sub-tab's panel and hands back its container.
    """
    from maptasker.src import guiwins, userintr  # noqa: PLC0415

    root = sample_backup("XML/Smart Reminders.prj.xml")
    PrimeItems.xml_root = root
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None))
    for event in sceneedit.LEGACY_SCENE_EVENTS:
        bound = properties.find(event.tag)
        if bound is not None:
            properties.remove(bound)

    scene_name = next(
        scene.findtext("nme", "")
        for scene in root.iter("Scene")
        if scene.find("PropertiesElement") is not None
    )

    notified = []
    monkeypatch.setattr(userintr.ui, "notify", lambda m, **k: notified.append((m, k.get("type"))))
    monkeypatch.setattr(guiwins.ui, "notify", lambda m, **k: notified.append((m, k.get("type"))))
    stub_gui.event_handlers = userintr.MapTaskerEventHandlers(stub_gui)

    pending: dict = {}
    rerenders: list = []

    def render_event(event):
        return _render(
            stub_gui,
            properties,
            guiwins._render_scene_event,
            event,
            lambda: rerenders.append(1),
            pending,
            scene_name,
        )

    return render_event, properties, scene_name, pending, notified, rerenders


def _picker_button(container, ui, prefix: str):
    """The action picker's row for the action whose label starts with `prefix`."""
    return next(
        e
        for e in _descendants(container)
        if isinstance(e, ui.button) and (e._props.get("label") or "").startswith(prefix)
    )


@pytest.mark.parametrize("event", sceneedit.LEGACY_SCENE_EVENTS, ids=lambda e: e.label)
def test_every_event_sub_tab_offers_an_action_editor_with_nothing_bound(unbound_event, event):
    """The reported problem: all three sub-tabs said the event fires no Task and stopped
    there, so there was no way to add actions without going out to the Add Task dialog.
    """
    ui = pytest.importorskip("nicegui").ui
    render_event, _properties, scene_name, _pending, _notified, _rerenders = unbound_event

    container = render_event(event)

    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Add an action" in labels
    fields = {e._props.get("label"): e for e in _descendants(container) if isinstance(e, ui.input)}
    assert fields["New Task Name"].value == f"{scene_name} {event.label}"
    assert [e for e in _descendants(container) if isinstance(e, ui.button) and e._props.get("label") == "Create Task"]


def test_nothing_is_created_until_the_button_is_pressed(unbound_event):
    """Composing is not creating: until "Create Task" the Task is in no table and no event
    points at it, so the Scene dialog's Cancel discards it the way Add Task's does.
    """
    ui = pytest.importorskip("nicegui").ui
    render_event, properties, _scene_name, pending, _notified, _rerenders = unbound_event
    before = dict(PrimeItems.tasker_root_elements["all_tasks_by_name"])

    container = render_event(sceneedit.LEGACY_SCENE_EVENTS[0])
    _click(_picker_button(container, ui, "Flash ("))

    assert pending[sceneedit.LEGACY_KEY_TASK_TAG].actions
    assert properties.find(sceneedit.LEGACY_KEY_TASK_TAG) is None
    assert PrimeItems.tasker_root_elements["all_tasks_by_name"] == before


def test_actions_added_survive_the_panel_being_rebuilt(unbound_event):
    """The Event panel is rebuilt on every sub-tab switch and every binding change.  A Task
    rebuilt with it would lose every action added so far, which is why the dialog holds it.
    """
    ui = pytest.importorskip("nicegui").ui
    render_event, _properties, _scene_name, pending, _notified, _rerenders = unbound_event
    key = sceneedit.LEGACY_SCENE_EVENTS[0]

    container = render_event(key)
    _click(_picker_button(container, ui, "Flash ("))
    # Walk away to another sub-tab and back, which is a fresh render of both.
    render_event(sceneedit.LEGACY_SCENE_EVENTS[1])
    again = render_event(key)

    assert [action.action_name for action in pending[key.tag].actions] == ["Flash"]
    headers = [e._props.get("label", "") for e in _descendants(again) if isinstance(e, ui.expansion)]
    assert any(header.strip().startswith("0: Flash") for header in headers)


def test_each_sub_tab_composes_its_own_task(unbound_event):
    """Keyed by event tag, so a Key Task and a Tab Tap Task in progress stay apart."""
    ui = pytest.importorskip("nicegui").ui
    render_event, _properties, _scene_name, pending, _notified, _rerenders = unbound_event
    key, _home, tab_tap = sceneedit.LEGACY_SCENE_EVENTS

    _click(_picker_button(render_event(key), ui, "Flash ("))
    _click(_picker_button(render_event(tab_tap), ui, "Variable Set ("))

    assert [action.action_name for action in pending[key.tag].actions] == ["Flash"]
    assert [action.action_name for action in pending[tab_tap.tag].actions] == ["Variable Set"]
    assert pending[key.tag].task_id != pending[tab_tap.tag].task_id


@pytest.mark.parametrize("event", sceneedit.LEGACY_SCENE_EVENTS, ids=lambda e: e.label)
def test_creating_registers_the_task_and_points_the_event_at_it(unbound_event, event):
    ui = pytest.importorskip("nicegui").ui
    render_event, properties, scene_name, pending, notified, rerenders = unbound_event

    container = render_event(event)
    _click(_picker_button(container, ui, "Flash ("))
    _click(next(e for e in _descendants(container) if isinstance(e, ui.button) and e._props.get("label") == "Create Task"))

    new_id = properties.findtext(event.tag)
    assert new_id
    entry = PrimeItems.tasker_root_elements["all_tasks"][new_id]
    assert entry["name"] == f"{scene_name} {event.label}"
    assert [action.findtext("code") for action in entry["xml"].findall("Action")] == ["548"]
    assert notified[-1][1] == "positive"
    # Composed and done with: the next render loads it from the tables like any other binding.
    assert event.tag not in pending
    assert rerenders == [1]


def test_the_new_task_joins_the_project_the_scene_belongs_to(unbound_event):
    """A Task in no Project's <tids> runs but appears in no generated view of any Project."""
    ui = pytest.importorskip("nicegui").ui
    render_event, properties, scene_name, _pending, _notified, _rerenders = unbound_event

    container = render_event(sceneedit.LEGACY_SCENE_EVENTS[0])
    _click(_picker_button(container, ui, "Flash ("))
    _click(next(e for e in _descendants(container) if isinstance(e, ui.button) and e._props.get("label") == "Create Task"))

    owner = sceneedit.project_owning_scene(scene_name)
    assert owner
    project = PrimeItems.tasker_root_elements["all_projects"][owner]["xml"]
    assert properties.findtext(sceneedit.LEGACY_KEY_TASK_TAG) in (project.findtext("tids") or "").split(",")


def test_a_name_another_task_already_has_is_refused_and_nothing_is_lost(unbound_event):
    """Add Task's own conflict rule, because it is Add Task's own code -- and the panel is
    left standing with the composed actions still in it.
    """
    ui = pytest.importorskip("nicegui").ui
    render_event, properties, _scene_name, pending, notified, _rerenders = unbound_event
    key = sceneedit.LEGACY_SCENE_EVENTS[0]

    container = render_event(key)
    _click(_picker_button(container, ui, "Flash ("))
    taken = next(iter(PrimeItems.tasker_root_elements["all_tasks_by_name"]))
    name_field = next(
        e for e in _descendants(container) if isinstance(e, ui.input) and e._props.get("label") == "New Task Name"
    )
    name_field.value = taken

    _click(next(e for e in _descendants(container) if isinstance(e, ui.button) and e._props.get("label") == "Create Task"))

    assert properties.find(key.tag) is None
    assert any("already exists" in message for message, _kind in notified)
    assert [action.action_name for action in pending[key.tag].actions] == ["Flash"]


def test_an_anonymous_binding_gets_no_editor_of_either_kind(sample_backup, stub_gui):
    """It is not in the Task tables, so there is nothing to load, nothing for an Apply to
    write into, and replacing it would destroy the only copy.
    """
    from maptasker.src import guiwins  # noqa: PLC0415

    ui = pytest.importorskip("nicegui").ui
    root = sample_backup("XML/Smart Reminders.prj.xml")
    properties = copy.deepcopy(_scene_with(root, lambda p: p.find(sceneedit.LEGACY_KEY_TASK_TAG) is not None))
    properties.find(sceneedit.LEGACY_KEY_TASK_TAG).text = "-1"

    container = _render(
        stub_gui,
        properties,
        guiwins._render_scene_event,
        sceneedit.LEGACY_SCENE_EVENTS[0],
        lambda: None,
    )

    labels = [e.text for e in _descendants(container) if isinstance(e, ui.label)]
    assert "Add an action" not in labels
    assert not [
        e for e in _descendants(container) if isinstance(e, ui.button) and e._props.get("label") == "Create Task"
    ]


def test_creating_two_tasks_from_two_sub_tabs_keeps_them_apart(unbound_event):
    """Ids are handed out from the Task tables, and a Task in progress is in none of them.
    Without reserving them, both sub-tabs' Tasks get the same id and creating the second
    overwrites the first -- leaving the first event pointing at the other one's actions.
    """
    ui = pytest.importorskip("nicegui").ui
    render_event, properties, _scene_name, _pending, _notified, _rerenders = unbound_event
    key, _home, tab_tap = sceneedit.LEGACY_SCENE_EVENTS

    for event, action in ((key, "Flash ("), (tab_tap, "Variable Set (")):
        container = render_event(event)
        _click(_picker_button(container, ui, action))
        _click(
            next(
                e
                for e in _descendants(container)
                if isinstance(e, ui.button) and e._props.get("label") == "Create Task"
            ),
        )

    key_id = properties.findtext(key.tag)
    tab_id = properties.findtext(tab_tap.tag)
    assert key_id and tab_id and key_id != tab_id

    all_tasks = PrimeItems.tasker_root_elements["all_tasks"]
    assert [a.findtext("code") for a in all_tasks[key_id]["xml"].findall("Action")] == ["548"]
    assert [a.findtext("code") for a in all_tasks[tab_id]["xml"].findall("Action")] == ["547"]


def test_a_reserved_id_is_never_handed_out_again():
    """The unit behind it: next_unique_task_or_profile_id treats a reserved id as taken."""
    saved = dict(PrimeItems.tasker_root_elements)
    try:
        PrimeItems.tasker_root_elements["all_tasks"] = {"10": {}, "11": {}}
        PrimeItems.tasker_root_elements["all_profiles"] = {}
        assert taskedit.next_unique_task_or_profile_id() == 12
        assert taskedit.next_unique_task_or_profile_id({"12"}) == 13
        assert taskedit.next_unique_task_or_profile_id({"12", "13"}) == 14
        # Junk in the reserved set is ignored rather than raising.
        assert taskedit.next_unique_task_or_profile_id({"not-a-number"}) == 12
    finally:
        PrimeItems.tasker_root_elements.clear()
        PrimeItems.tasker_root_elements.update(saved)
