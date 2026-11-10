"""Named Tasks that no Profile calls are in the Map's directory.

A Task that no Profile calls and no Project lists is written in its own section at the end of the Map ("Named Tasks that
are not called by any Profile...").  That section used to be written with the directory switched off, so those Tasks
were in the Map but not in the directory.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from maptasker.src import clireports
from maptasker.src.core import timeline
from maptasker.src.core.dirout import output_directory
from maptasker.src.core.primitem import PrimeItems, PrimeItemsReset
from maptasker.src.core.runcfg import current_config

_BACKUP = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><id>p-home</id><pids>100</pids><tids>20,23</tids></Project>
  <Profile sr="prof100" ve="2"><id>100</id><nme>Dawn</nme><mid0>20</mid0>
    <Time sr="con0"><fh>6</fh><fm>0</fm><th>7</th><tm>0</tm></Time></Profile>
  <Task sr="task20" ve="2"><id>20</id><nme>Morning</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action></Task>
  <Task sr="task23" ve="2"><id>23</id><nme>In The Project</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action></Task>
  <Task sr="task30" ve="2"><id>30</id><nme>Called By Nobody</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action></Task>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def _a_clean_run_in_a_scratch_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    yield
    timeline.use_history_folder(None)
    PrimeItemsReset()
    PrimeItems.headless = False


def _build_the_map(tmp_path: Path, *, directory: bool) -> list[str]:
    """Build the Map of the backup above, and return its output lines as text."""
    backup = tmp_path / "backup.xml"
    backup.write_text(_BACKUP, encoding="utf-8")
    options = clireports.build_parser().parse_args(["-export", "map", "-file", str(backup), "-detail", "5"])
    clireports._prepare(options, PrimeItems)
    PrimeItems.program_arguments.update({"directory": directory, "twisty": False, "single_project_name": ""})
    clireports._load_backup(options.file, PrimeItems)
    clireports._build_the_view("map", PrimeItems)
    return [line[1] if isinstance(line, list) else str(line) for line in PrimeItems.output_lines.output_lines]


def test_a_named_task_no_profile_calls_is_in_the_directory(tmp_path: Path) -> None:
    lines = _build_the_map(tmp_path, directory=True)

    assert "Named Tasks that are not called by any Profile" in "".join(lines)
    assert [name for _, name in PrimeItems.directory_items["tasks"]].count("Called By Nobody") == 1

    # ...and the directory, as it is written, links to the anchor that sits on the Task.
    PrimeItems.output_lines.output_lines = []
    output_directory(current_config(state=PrimeItems), set(), state=PrimeItems)
    directory = "".join(PrimeItems.output_lines.output_lines)
    assert re.search(r"""href=["']?#tasks_Called_By_Nobody[\s"'>]""", directory)
    assert "".join(lines).count('id="tasks_Called_By_Nobody"') == 1


def test_the_lines_after_the_uncalled_tasks_carry_no_directory_anchor(tmp_path: Path) -> None:
    """The directory is back off for the Projects-without-Tasks lines, so no Task's anchor is repeated on them."""
    lines = _build_the_map(tmp_path, directory=True)

    anchors = re.findall(r'id="(tasks_[^"]*)"', "".join(lines))
    assert len(anchors) == len(set(anchors))


def test_without_a_directory_nothing_is_added(tmp_path: Path) -> None:
    _build_the_map(tmp_path, directory=False)

    assert PrimeItems.directory_items["tasks"] == []
