"""Library code reports a failure by raising MapTaskerError; it does not end the run itself.

error_handler and exit_program used to be called from deep in the code, which made every failure path
end the process (or the test session) from wherever it happened and left the entry points no say in what
to show.  They are gone: error.record_error / error.report_error are the edges' own tools, and everything
else raises.  This keeps it that way -- a source file may not bring either name back, nor call sys.exit
or exit() outside the entry points that really are the top of the process.
"""

from __future__ import annotations

import ast
import pathlib

_SOURCE = pathlib.Path(__file__).resolve().parent.parent / "maptasker"

_GONE = {"error_handler", "exit_program"}

# Where ending the process is the right thing to do: the top of one, and the restart, which has just
# started its replacement and has nothing left to go back to.
_MAY_EXIT = {"maptasker/main.py", "maptasker/src/mapit.py", "maptasker/src/core/maputils.py"}


def _calls_and_names(path: pathlib.Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _GONE:
            found.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute) and node.attr in _GONE:
            found.append((node.lineno, node.attr))
        elif isinstance(node, ast.alias) and node.name in _GONE:
            found.append((node.lineno, node.name))
        elif isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Name) and node.func.id in {"exit", "quit"})
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "exit"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
            )
        ):
            found.append((node.lineno, "exit"))
    return found


def test_no_module_ends_the_run_from_deep_in_the_code() -> None:
    offenders: list[str] = []
    for path in sorted(_SOURCE.rglob("*.py")):
        relative = path.relative_to(_SOURCE.parent).as_posix()
        if relative in _MAY_EXIT:
            continue
        offenders.extend(f"{relative}:{line}: {name}" for line, name in _calls_and_names(path))
    assert not offenders, "raise MapTaskerError instead:\n" + "\n".join(offenders)
