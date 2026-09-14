"""Import structure Unit Tests

Three ratchets on how the modules in maptasker/src import one another, kept the same way as the
lint backlog in pyproject.toml: each records where things stand, fails on anything new, and is
edited -- downward -- as things improve.

1. No cycle among module-level imports.  There is none, and one would make importing the package
   fail, or work only when its modules happen to be imported in the right order.

2. The imports deferred into functions are a known list.  Most are there because moving them to
   the top of their file would create exactly such a cycle: the module imported already reaches
   back to the one importing it (_BREAKS_A_LOOP).  The rest are kept off the import path on
   purpose, each for the reason given (_KEPT_DEFERRED).  A new deferred import fails here until
   it is added with its reason.  One in _BREAKS_A_LOOP that no longer breaks anything fails too:
   it belongs at the top of its file now, and out of the list.

3. Counting the deferred imports as the dependencies they are, much of the package is still one
   loop.  _LARGEST_LOOP is its size, and it may only shrink.

Only imports of maptasker.src modules count.  Imports under `if TYPE_CHECKING:` never run, so
they are ignored.
"""

from __future__ import annotations

import ast
import pathlib
from collections import defaultdict

import pytest

_SRC = pathlib.Path(__file__).resolve().parent.parent / "maptasker" / "src"

# (importer, imported): deferred because the imported module already imports the importer,
# directly or through others, at module level.
_BREAKS_A_LOOP = {
    ("guiwins_designer_legacy", "guiwins"),
    ("guiwins_impact", "guiwins"),
    ("guiwins_taskedit", "guiwins"),
    ("sessundo", "taskerd"),
    ("timeline", "diffload"),
}

# (importer, imported): deferred for a reason other than a loop.
_KEPT_DEFERRED = {
    ("mapai", "cria"): "cria installs httpx, psutil and ollama the moment it is imported.",
    ("mapask", "cria"): "cria installs httpx, psutil and ollama the moment it is imported.",
    ("sceneedit", "sceneview"): "sceneview brings in the GUI, and sceneedit is otherwise free of it.",
    ("sceneedit", "actionc"): "Kept off the import path, as the notes where it is imported say.",
    ("mapjump", "maputil2"): "Kept GUI-free and off the import path; only one function needs it.",
    ("maputil2", "presave"): "Most of the package imports maputil2, and every one of them would depend on presave.",
    ("sessundo", "maputil2"): "Keeps sessundo out of the middle of the import graph -- see the note at the import.",
    ("proginit", "bldargs"): "Rebuilds the action tables from the network, only when asked; tests patch it there.",
    ("proginit", "bldbndle"): "Rebuilds the action tables from the backup, only when asked; tests patch it there.",
    ("proginit", "valcodes"): "Checks the codes against the network, only when asked; tests patch it there.",
    ("deviceinv", "maputil2"): "Tests patch maputil2.http_upload_request and read_back_uploaded_file for these calls.",
    ("editcommon", "maputil2"): "Tests patch maputil2.http_upload_request and read_back_uploaded_file for these calls.",
    ("guiwins", "guiutils"): "Not yet reviewed: its note gives a circular import that no longer exists.",
    ("guiwins_profedit", "guiwins"): "Not yet reviewed: its docstring gives a circular import that no longer exists.",
    ("rungui", "userintr"): "Loads the GUI modules when the GUI starts: at startup, diagram's import-time default is discarded.",
}

_LARGEST_LOOP = 4


def _import_graphs() -> tuple[dict[str, set[str]], dict[tuple[str, str], list[int]]]:
    """Module-level imports as {importer: {imported}}, and deferred ones as {(importer, imported): [lines]}."""
    modules = {path.stem for path in _SRC.glob("*.py") if path.stem != "__init__"}
    module_level: dict[str, set[str]] = {module: set() for module in modules}
    deferred: dict[tuple[str, str], list[int]] = defaultdict(list)

    def imported(node: ast.AST) -> list[str]:
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "maptasker.src":
                return [alias.name for alias in node.names if alias.name in modules]
            if node.module.startswith("maptasker.src."):
                return [name] if (name := node.module.split(".")[2]) in modules else []
        if isinstance(node, ast.Import):
            return [
                alias.name.split(".")[2]
                for alias in node.names
                if alias.name.startswith("maptasker.src.") and alias.name.split(".")[2] in modules
            ]
        return []

    for module in modules:
        tree = ast.parse((_SRC / f"{module}.py").read_text(encoding="utf-8"))

        def walk(nodes: list[ast.stmt], in_function: bool, module: str = module) -> None:
            for node in nodes:
                if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    continue
                for target in imported(node):
                    if target == module:
                        continue
                    if in_function:
                        deferred[(module, target)].append(node.lineno)
                    else:
                        module_level[module].add(target)
                for field in ("body", "orelse", "finalbody", "handlers"):
                    children = getattr(node, field, None)
                    if isinstance(children, list):
                        walk(children, in_function or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))

        walk(tree.body, in_function=False)
    return module_level, dict(deferred)


def _loops(graph: dict[str, set[str]]) -> list[set[str]]:
    """Every group of modules that import one another round in a circle (strongly connected components)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[set[str]] = []

    def visit(module: str) -> None:
        index[module] = low[module] = len(index)
        stack.append(module)
        on_stack.add(module)
        for target in graph[module]:
            if target not in index:
                visit(target)
                low[module] = min(low[module], low[target])
            elif target in on_stack:
                low[module] = min(low[module], index[target])
        if low[module] == index[module]:
            group = set()
            while True:
                member = stack.pop()
                on_stack.discard(member)
                group.add(member)
                if member == module:
                    break
            if len(group) > 1:
                found.append(group)

    for module in sorted(graph):
        if module not in index:
            visit(module)
    return found


def _reaches(graph: dict[str, set[str]], start: str, goal: str) -> bool:
    seen, todo = set(), [start]
    while todo:
        module = todo.pop()
        if module == goal:
            return True
        for target in graph[module] - seen:
            seen.add(target)
            todo.append(target)
    return False


@pytest.fixture(scope="module")
def graphs() -> tuple[dict[str, set[str]], dict[tuple[str, str], list[int]]]:
    return _import_graphs()


def test_module_level_imports_have_no_cycle(graphs) -> None:
    """A cycle here is a package that can fail to import, depending on which module is imported first."""
    module_level, _ = graphs
    assert _loops(module_level) == []


def test_every_deferred_import_is_on_the_list(graphs) -> None:
    """A new import inside a function is either breaking a loop or kept off the import path for a
    reason -- and either way it belongs on the list with the others, so the list says which."""
    _, deferred = graphs
    listed = _BREAKS_A_LOOP | set(_KEPT_DEFERRED)
    unlisted = sorted(
        f"{importer} -> {target} (lines {lines})"
        for (importer, target), lines in deferred.items()
        if (importer, target) not in listed
    )
    gone = sorted(f"{importer} -> {target}" for importer, target in listed if (importer, target) not in deferred)
    assert not unlisted, "deferred imports that are on neither list:\n" + "\n".join(sorted(unlisted))
    assert not gone, "listed deferred imports that no longer exist -- take them off the list:\n" + "\n".join(gone)


def test_every_loop_breaker_still_breaks_a_loop(graphs) -> None:
    """When the loop an import was deferred for has gone, it can move to the top of its file."""
    module_level, deferred = graphs
    no_longer = sorted(
        f"{importer} -> {target} (lines {deferred[(importer, target)]})"
        for importer, target in _BREAKS_A_LOOP
        if (importer, target) in deferred and not _reaches(module_level, target, importer)
    )
    assert not no_longer, "no longer break a loop -- move them to the top of their files:\n" + "\n".join(no_longer)


def test_the_largest_loop_does_not_grow(graphs) -> None:
    """Counting deferred imports as dependencies, the biggest set of modules that depend on one another."""
    module_level, deferred = graphs
    everything = {module: set(targets) for module, targets in module_level.items()}
    for importer, target in deferred:
        everything[importer].add(target)
    largest = max((len(group) for group in _loops(everything)), default=0)
    assert largest <= _LARGEST_LOOP, f"the largest loop grew to {largest} modules (from {_LARGEST_LOOP})"
    if largest < _LARGEST_LOOP:
        pytest.fail(
            f"the largest loop shrank to {largest} modules -- lower _LARGEST_LOOP to {largest} to keep it there"
        )
