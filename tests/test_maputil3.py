"""maputil3 Unit Tests

import_optional hands back a library from the "ai" extra, or None with one message saying how
to install it.  What matters most is what it must never do: run pip (or uv) behind the
user's back.  Every test here fails if anything tries to start a process.
"""

from __future__ import annotations

import subprocess
import sys
import types

import pytest
from maptasker.src import maputil3


@pytest.fixture(autouse=True)
def _no_installs_and_fresh_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if a process is started, and forget which packages were already reported."""

    def _refuse(*args: object, **kwargs: object) -> None:
        pytest.fail(f"import_optional must never start a process: {args!r}")

    for name in ("run", "check_call", "check_output", "Popen", "call"):
        monkeypatch.setattr(subprocess, name, _refuse)
    monkeypatch.setattr(maputil3, "_reported_missing", set())


def test_returns_an_installed_module() -> None:
    assert maputil3.import_optional("json", "json") is sys.modules["json"]


def test_a_missing_package_gives_none_and_one_message(capsys: pytest.CaptureFixture[str]) -> None:
    assert maputil3.import_optional("not-a-real-package", "not_a_real_package") is None

    message = capsys.readouterr().err
    assert "not-a-real-package" in message
    assert maputil3.AI_EXTRA_INSTALL_COMMAND in message


def test_the_same_missing_package_is_reported_only_once(capsys: pytest.CaptureFixture[str]) -> None:
    for _ in range(3):
        assert maputil3.import_optional("not-a-real-package", "not_a_real_package") is None

    assert capsys.readouterr().err.count("not-a-real-package") == 1


def test_a_missing_submodule_is_reported_as_missing(capsys: pytest.CaptureFixture[str]) -> None:
    # 'google.genai': the parent may be there (or not) -- either way it is "not installed".
    assert maputil3.import_optional("no-such-dist", "json.no_such_submodule") is None

    assert maputil3.AI_EXTRA_INSTALL_COMMAND in capsys.readouterr().err


def test_a_library_that_fails_inside_its_own_imports_is_not_called_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Installed but broken (one of its own dependencies is gone): don't send the user to install it again."""
    broken = types.ModuleType("broken_lib")

    def _import(path: str) -> types.ModuleType:
        raise ModuleNotFoundError("No module named 'its_dependency'", name="its_dependency")

    monkeypatch.setitem(sys.modules, "broken_lib", broken)
    monkeypatch.setattr(maputil3.importlib, "import_module", _import)

    assert maputil3.import_optional("broken-lib", "broken_lib") is None

    message = capsys.readouterr().err
    assert "could not be loaded" in message
    assert maputil3.AI_EXTRA_INSTALL_COMMAND not in message
