#! /usr/bin/env python3
"""bldbndle unit tests -- the <Bundle> table is rebuilt by merging, not by replacing.

A rebuild reads ONE backup.  Before this was a merge it replaced bundle.py outright, so
every definition that backup did not happen to contain was silently dropped, and a code
it did contain could still come back poorer: get_bundles keeps the first <Bundle> it
meets for a code, and the same code can appear both fully configured and bare in one
file.  That is not hypothetical -- the 07-Sep rebuild returned 2099e without the
RELEVANT_VARIABLES payload the file already had, which is the case test_2099e_regression
pins down with the real xml shape.

The tests are about what SURVIVES a rebuild, because that is how this fails: quietly,
into a generated file nobody reads, and only noticed later when an action synthesized
from bundle.py is missing part of its payload.
"""

from __future__ import annotations

import os
import textwrap

from maptasker.src import bldbndle
from maptasker.src.bldbndle import (
    build_bundles,
    get_bundles,
    load_existing_bundles,
    merge_bundles,
    save_bundles,
)

# A <Bundle> as Tasker really writes it, and the same one stripped to nothing -- the two
# forms of 2099e that the 07-Sep rebuild had to choose between.
FULL_2099 = {
    "Bundle": {
        "sr": "arg0",
        "Vals": {
            "sr": "val",
            "net.dinglisch.android.tasker.RELEVANT_VARIABLES": "&lt;StringArray sr=&quot;&quot;&gt;%uf_failed_attempts&lt;/StringArray&gt;",
            "net.dinglisch.android.tasker.RELEVANT_VARIABLES-type": "[Ljava.lang.String;",
        },
    },
}
BARE_2099 = {"Bundle": {"sr": "arg0", "Vals": {"sr": "val"}}}


def test_a_code_this_backup_lacks_is_kept() -> None:
    """The whole point: a rebuild adds to the table, it does not become the table."""
    merged, notes = merge_bundles({"111t": FULL_2099}, {"222t": BARE_2099})
    assert set(merged) == {"111t", "222t"}
    assert merged["111t"] == FULL_2099
    assert not notes  # Nothing contentious happened, so nothing to report.


def test_a_truncated_redefinition_is_refused() -> None:
    """2099e's actual failure: the backup's copy holds less, so the existing one stays."""
    merged, notes = merge_bundles({"2099e": FULL_2099}, {"2099e": BARE_2099})
    assert merged["2099e"] == FULL_2099
    assert any("2099e" in note and "kept" in note for note in notes), notes


def test_a_fuller_redefinition_is_taken() -> None:
    """The other direction -- a backup that knows more about a code than the file does."""
    merged, notes = merge_bundles({"2099e": BARE_2099}, {"2099e": FULL_2099})
    assert merged["2099e"] == FULL_2099
    assert any("2099e" in note and "fuller" in note for note in notes), notes


def test_an_unchanged_redefinition_is_silent() -> None:
    """Re-running against the same backup should not report anything."""
    merged, notes = merge_bundles({"2099e": FULL_2099}, {"2099e": FULL_2099})
    assert merged == {"2099e": FULL_2099}
    assert not notes


def test_missing_or_unreadable_file_reads_as_empty(tmp_path: os.PathLike) -> None:
    """A first run has no bundle.py, and a corrupt one must not take the build down."""
    assert load_existing_bundles(str(tmp_path / "nope.py")) == {}
    broken = tmp_path / "broken.py"
    broken.write_text("bundles = {this is not python\n", encoding="utf-8")
    assert load_existing_bundles(str(broken)) == {}


def test_save_and_load_round_trip(tmp_path: os.PathLike) -> None:
    """What save_bundles writes is what load_existing_bundles reads back."""
    out = tmp_path / "bundle.py"
    original = {"2099e": FULL_2099, "111t": BARE_2099}
    save_bundles(original, str(out), "backup.xml")
    assert load_existing_bundles(str(out)) == original


# One Event whose <Bundle> is bare, so a rebuild from this xml alone would replace a
# rich 2099e with nothing -- the 07-Sep case, in the file format it really occurs in.
_XML = textwrap.dedent("""\
    <TaskerData>
      <Profile sr="prof1">
        <Event sr="con0" ve="2">
          <code>2099</code>
          <pri>0</pri>
          <Bundle sr="arg0"><Vals sr="val"></Vals></Bundle>
        </Event>
      </Profile>
      <Task sr="task1">
        <Action sr="act0" ve="7">
          <code>888</code>
          <Bundle sr="arg0"><Vals sr="val"><a.b.C>kept</a.b.C></Vals></Bundle>
        </Action>
      </Task>
    </TaskerData>
    """)


def test_2099e_regression(tmp_path: os.PathLike) -> None:
    """End to end: rebuilding from a backup whose 2099e is bare must not strip 2099e.

    This is the bug as it actually happened, driven through build_bundles rather than
    merge_bundles, so the wiring is covered too: an existing bundle.py holding the full
    2099e plus a code this backup has never heard of, rebuilt from an xml whose 2099e is
    empty.  Everything has to survive, and the backup's own new code has to arrive.
    """
    xml_file = tmp_path / "backup.xml"
    xml_file.write_text(_XML, encoding="utf-8")
    out = tmp_path / "bundle.py"
    save_bundles({"2099e": FULL_2099, "555t": BARE_2099}, str(out), "older.xml")

    # The bare 2099e really is what this xml offers -- otherwise the test proves nothing.
    assert get_bundles(str(xml_file))["2099e"] == BARE_2099

    # live_file points nowhere, so this merges with the output file alone rather than
    # dragging in the real maptasker/src/bundle.py.
    rc = build_bundles(xml_file=str(xml_file), output_file=str(out), live_file=str(tmp_path / "none.py"))
    assert rc == 0

    rebuilt = load_existing_bundles(str(out))
    assert rebuilt["2099e"] == FULL_2099, "the rich 2099e was overwritten by the bare one"
    assert "555t" in rebuilt, "a code absent from this backup was dropped"
    assert "888t" in rebuilt, "the backup's own new code was not added"


def test_default_output_is_the_file_the_program_imports(tmp_path: os.PathLike, monkeypatch) -> None:
    """A rebuild lands in maptasker/src/bundle.py, with no copy to make afterwards.

    It used to be written to assets/json and moved across by hand, which is how a
    rebuild that had quietly dropped most of the table could still get installed.
    save_bundles is stubbed so that asserting this does not rewrite the real file.
    """
    xml_file = tmp_path / "backup.xml"
    xml_file.write_text(_XML, encoding="utf-8")
    written = {}

    def _capture(bundles: dict, output_file: str, xml: str) -> None:
        written["path"] = output_file
        written["count"] = len(bundles)

    monkeypatch.setattr(bldbndle, "save_bundles", _capture)
    assert build_bundles(xml_file=str(xml_file)) == 0

    assert written["path"] == os.path.join(os.path.dirname(bldbndle.__file__), "bundle.py")
    assert written["path"].endswith(os.path.join("maptasker", "src", "bundle.py"))
    # It merged with the real table rather than replacing it with this two-bundle xml.
    assert written["count"] > 2
