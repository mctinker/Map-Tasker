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
    return subprocess.run(  # noqa: S603
        [sys.executable, "-X", "warn_default_encoding", "-c", prelude + textwrap.dedent(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=120,
    )


def test_appending_xml_keeps_non_ascii_names_intact(tmp_path: Path) -> None:
    """append_files copies one XML file onto another: a Tasker name must come through unchanged."""
    body = f"<Task>{_NON_ASCII}</Task>\n"
    header = '<?xml version = "1.0" encoding = "UTF-8" standalone = "no" ?>\n'
    (tmp_path / "in.xml").write_text(body, encoding="utf-8")
    (tmp_path / "out.xml").write_text(header, encoding="utf-8")
    result = _run_checked(
        """
        from maptasker.src.xmldata import append_files
        append_files("in.xml", "out.xml")
        """,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out.xml").read_text(encoding="utf-8") == header + body


def test_the_run_counter_and_first_run_marker_use_an_explicit_encoding(tmp_path: Path) -> None:
    result = _run_checked(
        """
        from maptasker.src import proginit
        from maptasker.src.guiutils import is_first_run_today
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
        from maptasker.src.primitem import PrimeItems
        from maptasker.src.valcodes import debug_print
        PrimeItems.program_arguments.debug = True
        debug_print({_NON_ASCII!r})
        """,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert _NON_ASCII in (tmp_path / "buildit.log").read_text(encoding="utf-8")
