"""MapTasker Outline Unit Tests

The outline pass records which Tasks each Task calls (Perform Task), and the Diagram draws
one connector per call it finds there.  A Task shared by several Profiles is handed to that
pass once per Profile, so it must be scanned once, not once per Profile.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from maptasker.src import outline, profiles, taskerd
from maptasker.src.primitem import PrimeItems

# Three Profiles share 'Caller', which performs 'Callee' exactly once.
_SHARED_TASK_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Profile sr="prof10" ve="2"><id>10</id><mid0>20</mid0><nme>One</nme></Profile>
  <Profile sr="prof11" ve="2"><id>11</id><mid0>20</mid0><nme>Two</nme></Profile>
  <Profile sr="prof12" ve="2"><id>12</id><mid0>20</mid0><nme>Three</nme></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Caller</nme>
    <Action sr="act0"><code>130</code><Str sr="arg0">Callee</Str></Action>
  </Task>
  <Task sr="task21" ve="2"><id>21</id><nme>Callee</nme><Action sr="act0"><code>548</code></Action></Task>
</TaskerData>"""


@pytest.mark.parametrize("indent", [4, 0])
def test_a_task_shared_by_several_profiles_calls_once(monkeypatch: pytest.MonkeyPatch, indent: int) -> None:
    """Each Profile's copy of the Task carries a decorated name; all of them are one Task."""
    root = ET.fromstring(_SHARED_TASK_XML)  # noqa: S314  (fixture text, defined in this file)
    tables = {
        "all_projects": {},
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": {},
        "all_services": [],
    }
    tables["all_tasks_by_name"] = {task["name"]: {"xml": task["xml"], "id": key} for key, task in tables["all_tasks"].items()}
    monkeypatch.setattr(PrimeItems, "xml_root", root)
    monkeypatch.setattr(PrimeItems, "tasker_root_elements", tables)
    monkeypatch.setattr(PrimeItems, "outline_tasks_mapped", [], raising=False)  # Created by do_the_outline.
    monkeypatch.setattr(
        PrimeItems,
        "program_arguments",
        {
            "debug": False,
            "display_detail_level": 3,
            "indent": indent,
            "single_profile_name": "",
            "single_task_name": "",
        },
    )

    for profile in tables["all_profiles"].values():
        the_tasks = profiles.get_profile_tasks(profile["xml"], [], [])
        outline.get_perform_task_actions(the_tasks)

    assert tables["all_tasks_by_name"]["Caller"]["call_tasks"] == ["Callee"]
    assert tables["all_tasks_by_name"]["Callee"]["called_by"] == ["Caller"]
