"""PrimeItems (primitem) Unit Tests

PrimeItems holds MapTasker's run state as class attributes, and PrimeItemsReset puts the
per-run ones back to what the class body declares -- so the class body is the one list of what
there is and what it starts as.  These tests keep that true: everything the program reads or
writes on PrimeItems has to be declared there, and a reset has to put back all of it, as fresh
copies rather than the objects the last run filled, while leaving the session's settings alone.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from maptasker.src import bildhtml, maputils, primitem, taskerd
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.primitem import (
    SESSION_ATTRIBUTES,
    SINGLE_ITEM_SELECTORS,
    PrimeItems,
    PrimeItemsReset,
    initial_directory_items,
    initial_grand_totals,
    initial_tasker_root_elements,
    reset_attributes,
)

# The translation function: installed by translator.set_language and tested for with hasattr,
# so it has to be missing until then and cannot be declared.
_UNDECLARED_ON_PURPOSE = {"_"}


def _declared() -> set[str]:
    return {name for name in vars(PrimeItems) if not name.startswith("__")}


@pytest.fixture
def restore_prime_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put every attribute back after the test, whatever the test did to it."""
    for name in _declared():
        monkeypatch.setattr(PrimeItems, name, getattr(PrimeItems, name))


def test_everything_the_program_uses_on_prime_items_is_declared() -> None:
    """An attribute first created by whichever module assigns it is one no reset knows about,
    and one that is read before that assignment is an AttributeError."""
    package = pathlib.Path(primitem.__file__).parent.parent
    declared = _declared() | _UNDECLARED_ON_PURPOSE
    undeclared = set()
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "PrimeItems":
                name = node.attr
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"setattr", "getattr", "hasattr"}
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "PrimeItems"
                and isinstance(node.args[1], ast.Constant)
            ):
                name = node.args[1].value
            else:
                continue
            if name not in declared:
                undeclared.add(f"{path.relative_to(package)}:{node.lineno}  PrimeItems.{name}")
    assert undeclared == set(), "declare these in the PrimeItems class body:\n" + "\n".join(sorted(undeclared))


def test_every_attribute_is_either_reset_or_kept_for_the_session() -> None:
    """Nothing is in both, nothing is in neither, and the session list names only real attributes."""
    run_defaults = set(primitem._RUN_DEFAULTS)
    assert SESSION_ATTRIBUTES <= _declared()
    assert run_defaults.isdisjoint(SESSION_ATTRIBUTES)
    assert run_defaults | SESSION_ATTRIBUTES == _declared()


@pytest.mark.usefixtures("restore_prime_items")
def test_a_reset_empties_what_a_run_filled_and_keeps_the_session() -> None:
    """Including the attributes the old hand-written reset had missed or never known about."""
    PrimeItems.grand_totals["projects"] = 7  # filled in place, the way a run fills it
    PrimeItems.directory_items["tasks"].append("<a href='#task'>Task</a>")
    PrimeItems.ai["openai_key"] = "sk-left-over"
    PrimeItems.task_count_unnamed = 3  # was never reset
    PrimeItems.named_task_count_total = 4  # was never reset
    PrimeItems.netmap_output = ["║ Wake Up ║"]  # was not declared at all
    PrimeItems.program_arguments = {"debug": True}
    PrimeItems.slash = "\\"
    PrimeItems.tasker_arg_specs = {"548": ["Text"]}
    PrimeItems.view_limit = 25

    PrimeItemsReset()

    assert PrimeItems.grand_totals == initial_grand_totals()
    assert PrimeItems.directory_items == initial_directory_items()
    assert PrimeItems.ai["openai_key"] == ""
    assert PrimeItems.task_count_unnamed == 0
    assert PrimeItems.named_task_count_total == 0
    assert PrimeItems.netmap_output == []
    assert PrimeItems.program_arguments == {}
    # The session's settings are not the run's to throw away.
    assert PrimeItems.slash == "\\"
    assert PrimeItems.tasker_arg_specs == {"548": ["Text"]}
    assert PrimeItems.view_limit == 25


@pytest.mark.usefixtures("restore_prime_items")
def test_each_reset_hands_out_containers_of_its_own() -> None:
    """A reset that handed back the same dict would bring the last run's contents with it."""
    PrimeItemsReset()
    first = PrimeItems.directory_items
    first["tasks"].append("<a href='#task'>Task</a>")

    PrimeItemsReset()

    assert PrimeItems.directory_items is not first
    assert PrimeItems.directory_items["tasks"] == []


@pytest.mark.usefixtures("restore_prime_items")
def test_cleaning_up_after_a_run_leaves_settings_that_can_be_used() -> None:
    """It put the function that builds the default settings where the settings belong, so the
    next thing to read or write a setting failed."""
    bildhtml.clean_up_memory()

    assert PrimeItems.program_arguments == initialize_runtime_arguments()


# ##################################################################################
# The groups reset part-way through a session.
# ##################################################################################
def _is_prime_items(node: ast.AST, attribute: str | None = None) -> bool:
    """Whether node is PrimeItems.<attribute> (any attribute, if none is given)."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "PrimeItems"
        and attribute in {None, node.attr}
    )


def _taskerd_tree() -> ast.Module:
    return ast.parse(pathlib.Path(taskerd.__file__).read_text(encoding="utf-8"))


def test_every_reset_group_names_only_per_run_attributes() -> None:
    """A group is reset part-way through a session, so a session attribute in one would be thrown
    away there -- and a name that is not an attribute at all would be a KeyError."""
    for group in (
        primitem.MAP_OUTPUT_ATTRIBUTES,
        primitem.DIAGRAM_ATTRIBUTES,
        primitem.PROJECT_COUNT_ATTRIBUTES,
        primitem.LOADED_CONFIGURATION_ATTRIBUTES,
    ):
        assert set(group) <= set(primitem._RUN_DEFAULTS), group


@pytest.mark.usefixtures("restore_prime_items")
def test_resetting_a_group_leaves_everything_else_alone() -> None:
    PrimeItems.grand_totals["projects"] = 7
    PrimeItems.netmap_output = ["║ Wake Up ║"]

    reset_attributes(*primitem.MAP_OUTPUT_ATTRIBUTES)

    assert PrimeItems.grand_totals == initial_grand_totals()
    assert PrimeItems.netmap_output == ["║ Wake Up ║"]
    with pytest.raises(KeyError):
        reset_attributes("slash")  # a session attribute: nothing resets it


def test_loading_a_backup_builds_the_tables_an_empty_one_starts_with() -> None:
    """taskerd builds tasker_root_elements table by table; one added there and not to
    initial_tasker_root_elements (or the other way round) is a table something asks for and
    does not find."""
    built = set()
    for node in ast.walk(_taskerd_tree()):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if _is_prime_items(target, "tasker_root_elements") and isinstance(node.value, ast.Dict):
                built |= {key.value for key in node.value.keys if isinstance(key, ast.Constant)}
            elif (
                isinstance(target, ast.Subscript)
                and _is_prime_items(target.value, "tasker_root_elements")
                and isinstance(target.slice, ast.Constant)
            ):
                built.add(target.slice.value)
    assert built == set(initial_tasker_root_elements())


def test_loading_a_backup_sets_nothing_a_comparison_does_not_put_back() -> None:
    """diffload parses a second backup inside the session and restores
    LOADED_CONFIGURATION_ATTRIBUTES afterwards.  Anything taskerd sets outside that group would
    leak the comparison file into the configuration the user has open."""
    written = set()
    for node in ast.walk(_taskerd_tree()):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            base = target.value if isinstance(target, ast.Subscript) else target
            if _is_prime_items(base):
                written.add(base.attr)
    assert written
    assert written <= set(primitem.LOADED_CONFIGURATION_ATTRIBUTES)


@pytest.mark.usefixtures("restore_prime_items")
def test_clearing_the_loaded_backup_empties_every_table_where_it_stands() -> None:
    PrimeItems.tasker_root_elements = {
        name: {"1": {"name": "Home"}} if isinstance(empty, dict) else ["<Setting/>"]
        for name, empty in initial_tasker_root_elements().items()
    }
    tables = dict(PrimeItems.tasker_root_elements)

    maputils.clear_tasker_data()

    for name, table in tables.items():
        assert PrimeItems.tasker_root_elements[name] is table
        assert not table, name


@pytest.mark.usefixtures("restore_prime_items")
def test_a_single_task_or_profile_keeps_itself_and_clears_the_selection_it_set() -> None:
    """Asking for a Task selects its Project too; before the settings are saved, that Project is
    cleared and the Task is kept.  A Project asked for on its own is left as it is."""
    PrimeItems.program_arguments = dict.fromkeys((name_key for name_key, _, _ in SINGLE_ITEM_SELECTORS), "")
    PrimeItems.program_arguments.update(single_task_name="Opener", single_project_name="Home")
    PrimeItems.found_named_items = {found_key: True for _, found_key, _ in SINGLE_ITEM_SELECTORS}

    maputils.reset_named_objects()

    assert PrimeItems.program_arguments["single_task_name"] == "Opener"
    assert PrimeItems.program_arguments["single_project_name"] == ""
    assert PrimeItems.found_named_items == {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": True,
        "single_scene_found": False,
    }

    PrimeItems.program_arguments.update(single_task_name="", single_project_name="Home")
    maputils.reset_named_objects()
    assert PrimeItems.program_arguments["single_project_name"] == "Home"
