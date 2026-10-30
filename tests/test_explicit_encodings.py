"""Files MapTasker reads and writes are opened with an explicit encoding.

An open() with no encoding= uses the platform's default: UTF-8 on a Mac, but cp1252 on Windows.
A non-ASCII Tasker name then comes out garbled or raises there, and never shows on the Mac
the code is written on.  ruff's PLW1514 keeps a new one from being written; these tests run
the code that was fixed and fail if any of it falls back to the platform default.

Python's own "warn_default_encoding" mode raises EncodingWarning for exactly that fallback.
Running it in a subprocess, with the warning made an error for maptasker's modules only,
catches it wherever the platform's default happens to be UTF-8 already.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Every name here is one a Windows machine cannot hold in cp1252.
_NON_ASCII = "Café ☕ – 日本語 – Ünïcode"


def _run_checked(script: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run a script in a clean interpreter where a default-encoding open() in maptasker is an error."""
    prelude = textwrap.dedent(
        """
        import warnings
        warnings.filterwarnings("error", category=EncodingWarning, module=r"maptasker\\..*")
        """,
    )
    env = {"PYTHONPATH": str(_PROJECT_ROOT), "PATH": "", "PYTHONIOENCODING": "utf-8"}
    # Windows cannot initialise Winsock (so "import asyncio" fails) without SYSTEMROOT.
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", "-c", prelude + textwrap.dedent(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=120,
    )


def test_reading_a_backup_keeps_non_ascii_names_intact(tmp_path: Path) -> None:
    """A Tasker name outside ASCII must come through the loader unchanged, whatever the platform's default encoding."""
    (tmp_path / "in.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<TaskerData><Task><nme>{_NON_ASCII}</nme></Task></TaskerData>\n',
        encoding="utf-8",
    )
    result = _run_checked(
        f"""
        from maptasker.src.core.xmldata import parse_tasker_xml
        name = parse_tasker_xml("in.xml").getroot().findtext("Task/nme")
        assert name == {_NON_ASCII!r}, name
        """,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_the_run_counter_and_first_run_marker_use_an_explicit_encoding(tmp_path: Path) -> None:
    result = _run_checked(
        """
        from maptasker.src.mapgen import proginit
        from maptasker.src.gui.guiutils import is_first_run_today
        proginit.write_counter()
        assert proginit.read_counter() >= 0
        assert is_first_run_today() is True
        assert is_first_run_today() is False
        """,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_the_debug_log_keeps_non_ascii_text_intact(tmp_path: Path) -> None:
    result = _run_checked(
        f"""
        from maptasker.src.core.primitem import PrimeItems
        from maptasker.src.core.valcodes import debug_print
        PrimeItems.program_arguments.debug = True
        debug_print({_NON_ASCII!r}, PrimeItems)
        """,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert _NON_ASCII in (tmp_path / "buildit.log").read_text(encoding="utf-8")
