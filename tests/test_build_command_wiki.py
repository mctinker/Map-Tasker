"""The Command Reference generator (tools/misc/build_command_wiki.py) Unit Tests

The generator reads the GUI source with the `ast` module and works out, for every button, which dialog it opens.  What went
wrong with it was not a wrong answer but a different one each run: a helper that draws every Add and Edit button is called
with a different handler each time, the generator gave each button ALL the handlers, and it took whichever dialog it found
first from a set -- so which dialog every Add button "opened" depended on the order Python happened to iterate the set in,
and the page came out with a different number of entries from one run to the next.

So what is tested is the two things that fix it: a button gets the handler its OWN call passed, and where a choice does have
to be made it is made the same way every time.  The source is a few lines written into a temporary folder.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "misc" / "build_command_wiki.py"

_SOURCE = """
from nicegui import ui


def _object_button(label, on_click):
    ui.button(label, on_click=on_click).tooltip("Adds one.")


def build_add_project_dialog():
    with ui.dialog() as dialog, ui.card():
        ui.button("Project Name Ok").tooltip("Confirms.")


def build_add_task_dialog():
    with ui.dialog() as dialog, ui.card():
        ui.button("Task Name Ok").tooltip("Confirms.")


def build_other_dialog():
    with ui.dialog() as dialog, ui.card():
        ui.button("Other Ok").tooltip("Confirms.")


class Handlers:
    def open_add_project_dialog_event(self):
        build_add_project_dialog()

    def open_add_task_dialog_event(self):
        build_add_task_dialog()


def initialize_screen(self):
    _object_button("Add Project", on_click=self.event_handlers.open_add_project_dialog_event)
    _object_button("Add Task", on_click=self.event_handlers.open_add_task_dialog_event)
    ui.button("Both", on_click=lambda: (build_other_dialog(), build_add_project_dialog())).tooltip("Does two.")
"""


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    sys.path.insert(0, str(_TOOL.parent))
    spec = importlib.util.spec_from_file_location("build_command_wiki_under_test", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def model(tool: ModuleType, tmp_path: Path):
    (tmp_path / "guiwins.py").write_text(_SOURCE, encoding="utf-8")
    return tool.CommandModel(tmp_path, set(tool.COMMAND_KINDS))


def _opens(model, label: str) -> str | None:
    (widget,) = [w for function in model.funcs.values() for w in function.widgets if w.label == label]
    return widget.opens


def test_a_button_opens_the_dialog_its_own_handler_opens(model) -> None:
    """Both Add buttons are drawn by one helper; each takes the handler its own call passed."""
    assert _opens(model, "Add Project") == "guiwins.py:build_add_project_dialog"
    assert _opens(model, "Add Task") == "guiwins.py:build_add_task_dialog"


def test_a_button_is_given_only_the_handlers_its_own_call_passed(model) -> None:
    (task,) = [w for f in model.funcs.values() for w in f.widgets if w.label == "Add Task"]

    assert task.handlers == ("open_add_task_dialog_event",)


def test_where_one_button_reaches_two_dialogs_the_choice_does_not_depend_on_set_order(model) -> None:
    """A lambda calling two builders is a real ambiguity; it is settled by name, not by whichever came out of a set first."""
    first = _opens(model, "Both")

    assert first == "guiwins.py:build_add_project_dialog"


_PROBE = """
import importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("tool", sys.argv[2])
tool = importlib.util.module_from_spec(spec)
sys.modules["tool"] = tool
spec.loader.exec_module(tool)
model = tool.CommandModel(Path(sys.argv[3]), set(tool.COMMAND_KINDS))
print(json.dumps(sorted((w.label, w.opens) for f in model.funcs.values() for w in f.widgets)))
"""


@pytest.mark.parametrize("seeds", [("0", "1"), ("2", "3"), ("4", "5")])
def test_what_every_button_opens_is_the_same_whatever_the_hash_seed(seeds: tuple[str, str], tmp_path: Path) -> None:
    """The same source gives the same answer under different hash seeds -- the failure was that it did not."""
    (tmp_path / "guiwins.py").write_text(_SOURCE, encoding="utf-8")
    answers = []
    for seed in seeds:
        run = subprocess.run(
            [sys.executable, "-c", _PROBE, str(_TOOL.parent), str(_TOOL), str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        answers.append(run.stdout)

    assert answers[0] == answers[1]
    assert "build_add_project_dialog" in answers[0]
