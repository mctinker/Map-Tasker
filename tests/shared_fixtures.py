"""Fixtures several test modules share.

A fixture used by tests in more than one module lives here, and conftest.py registers this module as a
plugin, so every test can ask for it by name.  They used to be defined in the first module that needed
one and imported into the others, which is a name the importing module never uses (F401) and then a
parameter that shadows it (F811) -- a `# noqa` on each.

Nothing here applies on its own: a module that wants one of the ones that set up a run for every test in
it says so with `pytestmark = pytest.mark.usefixtures("name")`.
"""

from __future__ import annotations

import copy
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from maptasker.src.core import appinv, caches, primitem
from maptasker.src.core.colrmode import set_color_mode
from maptasker.src.core.initparg import ProgramArguments, initialize_runtime_arguments
from maptasker.src.core.primitem import PrimeItems, initial_tasker_root_elements
from maptasker.src.edit import sessundo
from maptasker.src.gui import guiutils, guiwins
from maptasker.src.mapgen import taskerd
from maptasker.src.mapgen.lineout import LineOut

from tests.test_mapswap import _FIXTURE_XML, _load

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """test_mapswap's fixture backup, loaded: its Tasks are Noisy, Opener and Quiet.

    With a small, known list of fetched Applications, kept in a cache file of its own.  What is
    addable follows the Application and icon inventory (Notify, one of the common actions, has an
    icon argument), and the inventory includes whatever MapTasker_Apps.json sits in the current
    directory -- so without this, the catalog these tests read was the maintainer's phone locally
    and an empty one on a CI checkout, and the same test passed in one place and failed in the other.
    """
    cache = tmp_path / "MapTasker_Apps.json"
    cache.write_text(json.dumps({"devices": {"test:1821": {"apps": [{"pkg": "com.test.app", "label": "Test"}]}}}))
    monkeypatch.setattr(appinv, "cache_path", lambda: str(cache))
    caches.clear_all()
    _load(_FIXTURE_XML)


# ##################################################################################
# The configuration open now.  Its ids (20-22, 100-101) share nothing with the share's (5-12),
# which is the whole point: that is what an import does.
#
#   Project Pack     Profiles Dawn (runs the anonymous Task 22) and Dusk (runs Morning).
#                    Tasks Morning, Helper, and the anonymous one.
#   Project Other    Task Elsewhere -- belongs to something else, and must never be offered.
#
# Dawn is enabled here (flags 10, no <limit>): the importer switched it on.
# ##################################################################################
_LOCAL_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Pack</name><pids>100,101</pids><tids>20,21</tids></Project>
  <Project sr="proj1" ve="2"><name>Other</name><tids>50</tids></Project>
  <Profile sr="prof100" ve="2"><cdate>1</cdate><flags>10</flags><id>100</id><mid0>22</mid0><nme>Dawn</nme>
    <Time sr="con0"><fh>6</fh></Time></Profile>
  <Profile sr="prof101" ve="2"><cdate>1</cdate><flags>10</flags><id>101</id><mid0>20</mid0><nme>Dusk</nme>
    <Time sr="con0"><fh>18</fh></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action></Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Helper</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">helping</Str></Action></Task>
  <Task sr="task22" ve="2"><id>22</id>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">anon</Str></Action></Task>
  <Task sr="task50" ve="2"><id>50</id><nme>Elsewhere</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">not mine</Str></Action></Task>
</TaskerData>
"""


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _load_local(tmp_path: Path, xml: str) -> None:
    """Load `xml` as the configuration open now, the way MapTasker loads one."""
    with open(_write(tmp_path, "local.xml", xml), encoding="utf-8") as handle:
        PrimeItems.file_to_get = handle
        PrimeItems.tasker_root_elements = initial_tasker_root_elements()
        taskerd.get_the_xml_data(state=PrimeItems)


@pytest.fixture
def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A believable runtime with the local configuration loaded the way MapTasker loads one."""
    monkeypatch.chdir(tmp_path)
    sessundo.clear(PrimeItems)
    PrimeItems.program_arguments = ProgramArguments(
        gui=True, debug=False, directory=False, pretty=False, display_detail_level=3, file="", language="English"
    )
    PrimeItems.error_code = 0
    PrimeItems.error_msg = ""
    PrimeItems.directory_items = {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []}
    PrimeItems.output_lines = LineOut(state=PrimeItems)
    PrimeItems.colors_to_use = set_color_mode("light")
    specs_file = Path(__file__).parent.parent / "maptasker" / "assets" / "json" / "arg_specs.json"
    specs = json.loads(specs_file.read_text(encoding="utf-8"))
    specs[str(len(specs))] = "ConditionList"
    PrimeItems.tasker_arg_specs = specs
    _load_local(tmp_path, _LOCAL_XML)
    yield
    sessundo.clear(PrimeItems)


# The configuration open now.
#
#   Task 20 'Morning' edited: one Flash gone, a Perform Task 'Helper' added -- so bringing
#   Helper back is bringing back something a call is still waiting for.
#   Task 23 renamed to 'New Name' AND edited -- two xmldiff entries, one revert.
#   Task 30 added, the %Global value changed, Project Gone deleted -- all three differences
#   the list must decline to offer, and count.
_NEWER_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Variable sr="v0"><n>%Global</n><v>2</v></Variable>
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <id>p-home</id>
    <pids>100</pids>
    <tids>20,23,30</tids>
  </Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action>
    <Action sr="act1" ve="7"><code>130</code><Str sr="arg0" ve="3">Helper</Str></Action>
  </Task>
  <Task sr="task23" ve="2"><id>23</id><nme>New Name</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">original</Str></Action>
    <Action sr="act1" ve="7"><code>548</code><Str sr="arg0" ve="3">added later</Str></Action>
  </Task>
  <Task sr="task30" ve="2"><id>30</id><nme>Added</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">new</Str></Action>
  </Task>
</TaskerData>
"""


def _tables(root: ET.Element) -> dict:
    """PrimeItems-shaped tables for one parsed root, the way taskerd builds them."""
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
    return tables


@pytest.fixture
def loaded() -> Iterator[None]:
    """The newer configuration open, with an empty undo history."""
    sessundo.clear(PrimeItems)
    root = ET.fromstring(_NEWER_XML)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.xml_tree = ET.ElementTree(root)
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100, language="English")
    specs_file = os.path.join(os.path.dirname(__file__), "..", "maptasker", "assets", "json", "arg_specs.json")
    with open(specs_file, encoding="utf-8") as handle:
        specs = json.load(handle)
    specs[str(len(specs))] = "ConditionList"
    PrimeItems.tasker_arg_specs = specs
    PrimeItems.tasker_root_elements = _tables(root)
    yield
    sessundo.clear(PrimeItems)


#   Profile 1 'Work Hours'  Time 09:00-17:00 AND Day Mon-Fri, priority 10.  Entry Task 50
#                           turns WiFi Off.
#   Profile 2 'Office'      Wifi Connected to Office/Office-5G.  Entry Task 51 turns WiFi On
#                           -> a SETTING collision with Profile 1 at 10:00 on a weekday.
#   Profile 3 'Low Battery' Battery Level 0-20.  Entry Task 52.
#   Profile 4 'Maps'        App Maps.  Entry Task 52 too -> SAME-TASK with Profile 3;
#                           Task 52 is 'Abort Existing Task'.
#   Profile 5 'Night'       Time 22:00-06:00, which wraps past midnight.
#   Profile 6 'Chime'       Time 08:00-12:00 repeating every 30 minutes.
#   Profile 7 'Notified'    an Event -> never more than possible.
#   Profile 8 'Switched Off' disabled.
#   Profile 9 'Away'        Wifi Connected to Home, inverted.
#   Profile 10 'Sunset'     Time from a variable -> unknown.
_SIM_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>1,2,3,4,5,6,7,8,9,10</pids>
    <tids>50,51,52,53</tids>
  </Project>
  <Profile sr="prof1" ve="2">
    <id>1</id><nme>Work Hours</nme><mid0>50</mid0><pri>10</pri>
    <Time sr="con0"><fh>9</fh><fm>0</fm><th>17</th><tm>0</tm></Time>
    <Day sr="con1"><wday0>2</wday0><wday1>3</wday1><wday2>4</wday2><wday3>5</wday3><wday4>6</wday4></Day>
  </Profile>
  <Profile sr="prof2" ve="2">
    <id>2</id><nme>Office</nme><mid0>51</mid0>
    <State sr="con0" ve="2"><code>160</code><Str sr="arg0" ve="3">Office/Office-5G</Str>
      <Str sr="arg1" ve="3"/><Str sr="arg2" ve="3"/><Int sr="arg3" val="2"/></State>
  </Profile>
  <Profile sr="prof3" ve="2">
    <id>3</id><nme>Low Battery</nme><mid0>52</mid0>
    <State sr="con0" ve="2"><code>140</code><Int sr="arg0" val="0"/><Int sr="arg1" val="20"/></State>
  </Profile>
  <Profile sr="prof4" ve="2">
    <id>4</id><nme>Maps</nme><mid0>52</mid0>
    <App sr="con0" ve="2"><cls0>com.google.android.maps.MapsActivity</cls0><flags>2</flags>
      <label0>Maps</label0><pkg0>com.google.android.apps.maps</pkg0></App>
  </Profile>
  <Profile sr="prof5" ve="2">
    <id>5</id><nme>Night</nme><mid0>53</mid0>
    <Time sr="con0"><fh>22</fh><fm>0</fm><th>6</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof6" ve="2">
    <id>6</id><nme>Chime</nme><mid0>53</mid0>
    <Time sr="con0"><fh>8</fh><fm>0</fm><rep>2</rep><repval>30</repval><th>12</th><tm>0</tm></Time>
  </Profile>
  <Profile sr="prof7" ve="2">
    <id>7</id><nme>Notified</nme><mid0>53</mid0>
    <Event sr="con0" ve="2"><code>461</code></Event>
  </Profile>
  <Profile sr="prof8" ve="2">
    <id>8</id><nme>Switched Off</nme><limit>true</limit><mid0>53</mid0>
    <Time sr="con0"><fh>0</fh><fm>0</fm><th>23</th><tm>59</tm></Time>
  </Profile>
  <Profile sr="prof9" ve="2">
    <id>9</id><nme>Away</nme><mid0>53</mid0>
    <State sr="con0" ve="2"><code>160</code><pin>true</pin><Str sr="arg0" ve="3">Home</Str>
      <Str sr="arg1" ve="3"/><Str sr="arg2" ve="3"/></State>
  </Profile>
  <Profile sr="prof10" ve="2">
    <id>10</id><nme>Sunset</nme><mid0>53</mid0>
    <Time sr="con0"><fromvar>%SunsetTime</fromvar><tovar>%SunriseTime</tovar></Time>
  </Profile>
  <Task sr="task50"><id>50</id><nme>Wifi Off</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="0"/></Action>
  </Task>
  <Task sr="task51"><id>51</id><nme>Wifi On</nme>
    <Action sr="act0" ve="7"><code>425</code><Int sr="arg0" val="1"/></Action>
  </Task>
  <Task sr="task52"><id>52</id><nme>Shared</nme><rty>1</rty>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="5"/></Action>
  </Task>
  <Task sr="task53"><id>53</id><nme>Quiet</nme>
    <Action sr="act0" ve="7"><code>30</code><Int sr="arg1" val="1"/></Action>
  </Task>
</TaskerData>
"""


@pytest.fixture
def _loaded() -> None:
    """Build the PrimeItems lookup tables from the fixture, the way taskerd does from a file."""
    root = ET.fromstring(_SIM_XML)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = ProgramArguments(task_action_warning_limit=100)
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


# The window the test_gui_window pages build, kept where the test can reach it.
_built: dict = {}


@pytest.fixture
def fresh_session(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """A working directory of its own, a fresh run, nothing loaded -- and everything the window
    changes on the way up put back afterwards, so no other test inherits it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(PrimeItems, "program_arguments", initialize_runtime_arguments())
    for name in primitem.LOADED_CONFIGURATION_ATTRIBUTES:
        monkeypatch.setattr(PrimeItems, name, copy.deepcopy(primitem._RUN_DEFAULTS[name]))
    monkeypatch.setattr(PrimeItems, "slash", "/")
    monkeypatch.setattr(PrimeItems, "mygui", None)
    monkeypatch.setattr(PrimeItems, "colors_to_use", {})
    monkeypatch.setattr(PrimeItems, "language_set", False)
    monkeypatch.setattr(PrimeItems, "languages_translated", dict(PrimeItems.languages_translated))
    monkeypatch.setitem(guiwins._NOTIFY_TIMEOUT, "ms", guiwins._NOTIFY_TIMEOUT["ms"])
    # The daily PyPI check is scheduled only on the day's first run; this is never it.
    monkeypatch.setattr(guiutils, "is_first_run_today", lambda *_args, **_kwargs: False)
    had_translator, translator = hasattr(PrimeItems, "_"), getattr(PrimeItems, "_", None)
    _built.clear()
    yield tmp_path
    if had_translator:
        cast("Any", PrimeItems)._ = translator
    elif hasattr(PrimeItems, "_"):
        del cast("Any", PrimeItems)._
