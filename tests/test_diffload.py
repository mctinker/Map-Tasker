"""MapTasker Comparison Loader Unit Tests

diffload.py exists to parse a second XML file without disturbing the one MapTasker has
loaded, so almost every test here is the same shape: record the whole of PrimeItems that
the load could reach, run an isolated load, and assert nothing moved.

The failure cases matter more than the success case.  A comparison against a file that
loads is easy; the ways this can go wrong -- a corrupt file taking the program down with
sys.exit, a stale error file greeting the user at next startup, the other file's Profiles
landing in the live directory list, the user's own backup being rewritten on disk -- all
happen on the paths a happy-path test never reaches.
"""

from __future__ import annotations

import os

import pytest
from maptasker.src import diffload, taskerd
from maptasker.src.lineout import LineOut
from maptasker.src.primitem import PrimeItems, initial_tasker_root_elements
from maptasker.src.sysconst import ERROR_FILE

_GOOD_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Project sr="proj0" ve="2"><cdate>1</cdate><id>1</id><name>Loaded</name>
    <pids>10</pids><tids>20</tids></Project>
  <Profile sr="prof10" ve="2"><cdate>1</cdate><id>10</id><nme>Wake</nme><mid0>20</mid0>
    <Time sr="if0"><fh>7</fh></Time></Profile>
  <Task sr="task20" ve="2"><cdate>1</cdate><id>20</id><nme>Runner</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Running</Str></Action></Task>
  <Variable sr="vars0"><n>%loaded</n><v>yes</v></Variable>
</TaskerData>
"""

_OTHER_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Project sr="proj0" ve="2"><cdate>1</cdate><id>2</id><name>Other</name>
    <pids>11</pids><tids>21</tids></Project>
  <Profile sr="prof11" ve="2"><cdate>1</cdate><id>11</id><nme>Sleep</nme><mid0>21</mid0>
    <Time sr="if0"><fh>23</fh></Time></Profile>
  <Task sr="task21" ve="2"><cdate>1</cdate><id>21</id><nme>Winder</nme>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">Winding</Str></Action></Task>
  <Variable sr="vars0"><n>%other</n><v>indeed</v></Variable>
</TaskerData>
"""

# A Profile with no <nme> at all.  taskerd names it from its conditions, and that pass --
# profiles.conditions_to_name -- writes the derived name back through
# PrimeItems.tasker_root_elements rather than returning it.  That write-back is the whole
# reason this module swaps the global instead of building tables locally, so the fixture
# that exercises it is not optional.
_UNNAMED_PROFILE_XML = """<TaskerData sr="" dvi="1" tv="6.5.6">
  <Profile sr="prof30" ve="2"><cdate>1</cdate><id>30</id><mid0>21</mid0>
    <Time sr="if0"><fh>6</fh></Time></Profile>
</TaskerData>
"""

_MALFORMED_XML = "<TaskerData><Project><name>Unclosed</name>"
_NOT_TASKER_XML = "<SomethingElse><Project><name>Wrong root</name></Project></SomethingElse>"


def _write(tmp_path, name: str, text: str) -> str:
    """Put fixture XML on disk and hand back its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _load_as_current(path: str) -> None:
    """Load a file the way MapTasker does, so PrimeItems holds a real configuration.

    Goes through taskerd.get_the_xml_data rather than building the tables by hand: these
    tests are about what happens to a genuinely loaded configuration, and a hand-built
    one would not have been through the same passes.
    """
    with open(path) as handle:  # noqa: PTH123, SIM115
        PrimeItems.file_to_get = handle
        PrimeItems.tasker_root_elements = initial_tasker_root_elements()
        assert taskerd.get_the_xml_data() == 0


def _snapshot() -> dict:
    """Everything an isolated load could reach, captured by identity where it matters."""
    return {
        "file_to_get": PrimeItems.file_to_get,
        "file_to_use": PrimeItems.file_to_use,
        "xml_tree": PrimeItems.xml_tree,
        "xml_root": PrimeItems.xml_root,
        "tasker_root_elements": PrimeItems.tasker_root_elements,
        "error_code": PrimeItems.error_code,
        "error_msg": PrimeItems.error_msg,
        "directory_items": PrimeItems.directory_items,
        "gui": PrimeItems.program_arguments.get("gui"),
        "directory": PrimeItems.program_arguments.get("directory"),
    }


@pytest.fixture(autouse=True)
def _runtime(tmp_path, monkeypatch):
    """A believable runtime: a loaded configuration, and a working directory of our own.

    chdir matters -- error_handler writes ERROR_FILE into the current directory, and
    these tests assert on whether it is there afterwards.
    """
    monkeypatch.chdir(tmp_path)
    PrimeItems.program_arguments = {
        "gui": True,
        "debug": False,
        "directory": False,
        "pretty": False,
        "display_detail_level": 3,
        "file": "",
    }
    PrimeItems.error_code = 0
    PrimeItems.error_msg = ""
    PrimeItems.directory_items = {"current_item": "", "projects": [], "profiles": [], "tasks": [], "scenes": []}
    # A real LineOut, the way guiutils/mapit build one once a map has been rendered.  The
    # "not yet built" state is None, and has its own test below.
    PrimeItems.output_lines = LineOut()
    _load_as_current(_write(tmp_path, "loaded.xml", _GOOD_XML))


# ##################################################################################
# The success case, and the round trip that is the whole point of the module.
# ##################################################################################
def test_the_other_file_is_actually_parsed(tmp_path) -> None:
    """The returned Configuration holds the OTHER file's objects, not the loaded one's."""
    other = _write(tmp_path, "other.xml", _OTHER_XML)
    configuration, message = diffload.load_for_comparison(other)

    assert message == ""
    assert configuration is not None
    assert configuration.path == other
    assert list(configuration.tables["all_projects"]) == ["Other"]
    assert configuration.tables["all_tasks"]["21"]["name"] == "Winder"
    assert configuration.root.findtext("Variable/n") == "%other"


def test_the_loaded_configuration_is_untouched(tmp_path) -> None:
    """Nothing about the loaded configuration moves -- same objects, not merely equal ones.

    Identity rather than equality on purpose: handing the rest of the program a table
    that merely looks right, while every element in it belongs to a different tree, is
    exactly the failure this module exists to prevent, and == would not see it.
    """
    before = _snapshot()
    diffload.load_for_comparison(_write(tmp_path, "other.xml", _OTHER_XML))
    after = _snapshot()

    for name, value in before.items():
        assert after[name] is value, f"PrimeItems.{name} was not restored"
    assert list(PrimeItems.tasker_root_elements["all_projects"]) == ["Loaded"]
    assert PrimeItems.tasker_root_elements["all_tasks"]["20"]["name"] == "Runner"


def test_a_derived_profile_name_lands_on_the_other_file_not_the_loaded_one(tmp_path) -> None:
    """The write-back that makes the whole swap necessary, tested end to end.

    profiles.conditions_to_name writes an unnamed Profile's derived name into
    PrimeItems.tasker_root_elements directly.  The name must come out on the returned
    Configuration and must not have gone anywhere near the loaded tables.
    """
    other = _write(tmp_path, "unnamed.xml", _UNNAMED_PROFILE_XML)
    configuration, message = diffload.load_for_comparison(other)

    assert message == ""
    assert configuration.tables["all_profiles"]["30"]["name"]
    assert "30" not in PrimeItems.tasker_root_elements["all_profiles"]
    assert list(PrimeItems.tasker_root_elements["all_profiles"]) == ["10"]


# ##################################################################################
# The failure cases.
# ##################################################################################
def test_a_malformed_file_reports_and_does_not_exit(tmp_path) -> None:
    """A corrupt comparison file must never take the program down.

    taskerd hands a parse failure to error_handler, which outside GUI mode ends in
    exit_program -> sys.exit.  This test runs with "gui" False precisely so that a
    regression there shows up as the test process dying rather than as a quiet pass, and
    asserts the flag was put back afterwards.
    """
    PrimeItems.program_arguments["gui"] = False
    before = _snapshot()

    configuration, message = diffload.load_for_comparison(_write(tmp_path, "bad.xml", _MALFORMED_XML))

    assert configuration is None
    assert "bad.xml" in message
    assert PrimeItems.program_arguments["gui"] is False
    for name, value in before.items():
        assert _snapshot()[name] is value, f"PrimeItems.{name} was not restored after a bad file"


def test_a_non_tasker_file_is_named_as_such(tmp_path) -> None:
    """Valid XML that is not a Tasker backup gets its own message, not "invalid XML"."""
    configuration, message = diffload.load_for_comparison(_write(tmp_path, "other.xml", _NOT_TASKER_XML))
    assert configuration is None
    assert "not a valid Tasker backup file" in message or "not a Tasker backup file" in message


def test_a_missing_file_reports_rather_than_raises(tmp_path) -> None:
    """A file that is not there is a message, not an exception out of the button handler.

    And it says the file could not be READ.  Routing it through the parse verdicts would
    call a file that is not there "not valid XML", sending the user off to inspect the
    contents of something they have not got.
    """
    before = _snapshot()
    configuration, message = diffload.load_for_comparison(str(tmp_path / "nowhere.xml"))

    assert configuration is None
    assert "nowhere.xml could not be read" in message
    assert "not valid XML" not in message
    for name, value in before.items():
        assert _snapshot()[name] is value


@pytest.mark.parametrize(
    ("name", "text"),
    [("bad.xml", _MALFORMED_XML), ("other.xml", _NOT_TASKER_XML), ("nowhere.xml", None)],
)
def test_a_failure_message_never_shows_the_temporary_copy(tmp_path, name: str, text: str | None) -> None:
    """The user is told the file they chose, never the scratch copy that was parsed.

    taskerd's error text embeds the path it was handed, which is the temporary copy.  A
    message naming something under the system temp directory tells the user nothing and
    reads as a bug in MapTasker rather than a problem with their file.
    """
    path = _write(tmp_path, name, text) if text is not None else str(tmp_path / name)
    _, message = diffload.load_for_comparison(path)

    # The scratch marker, not the temp directory: pytest's own tmp_path lives under the
    # temp directory too, so the user's real file legitimately has that prefix.
    assert name in message
    assert "MapTasker_compare_" not in message
    assert str(tmp_path) in message or message.count(name) >= 1


def test_no_file_chosen(tmp_path) -> None:
    """Cancelling the file picker hands back an empty path, and is not an error state."""
    configuration, message = diffload.load_for_comparison("")
    assert configuration is None
    assert "No file was chosen" in message


def test_an_exception_inside_the_window_still_restores(tmp_path) -> None:
    """The restore is in a finally, and that is not decoration.

    Raising through the context manager is also the case that would trip a generator
    with more than one yield in it, which an earlier draft of this module had.
    """
    before = _snapshot()
    with pytest.raises(RuntimeError, match="boom"):  # noqa: PT012
        with diffload._parsed_in_isolation(_write(tmp_path, "other.xml", _OTHER_XML)):
            raise RuntimeError("boom")

    for name, value in before.items():
        assert _snapshot()[name] is value, f"PrimeItems.{name} was not restored after an exception"


# ##################################################################################
# The side effects that would outlive the comparison.
# ##################################################################################
def test_the_user_file_is_never_the_one_parsed(tmp_path, monkeypatch) -> None:
    """A copy is parsed, never the file the user picked.

    get_the_xml_data calls xmldata.rewrite_xml on a UnicodeDecodeError, and rewrite_xml
    removes and renames the file it is given -- it replaces the file on disk.  A
    comparison that rewrote one of the two backups it was asked to compare would destroy
    the thing the user opened it to check.  Asserted by watching which path the parse is
    handed, rather than by contriving an encoding error, so it holds for every path into
    rewrite_xml rather than the one a fixture can reach.
    """
    other = _write(tmp_path, "other.xml", _OTHER_XML)
    parsed_paths = []
    real_get_the_xml_data = diffload.get_the_xml_data

    def spy() -> int:
        parsed_paths.append(PrimeItems.file_to_get.name)
        return real_get_the_xml_data()

    monkeypatch.setattr(diffload, "get_the_xml_data", spy)
    configuration, message = diffload.load_for_comparison(other)

    assert message == ""
    assert configuration is not None
    assert parsed_paths and parsed_paths[0] != other
    assert "other.xml" in parsed_paths[0], "the copy should still name the file it came from"
    # And the copy does not outlive the comparison.
    assert not os.path.exists(parsed_paths[0])


def test_the_original_file_is_left_byte_for_byte(tmp_path) -> None:
    """The obvious companion to the test above, stated in the terms the user cares about."""
    other = _write(tmp_path, "other.xml", _OTHER_XML)
    before = (tmp_path / "other.xml").read_bytes()
    diffload.load_for_comparison(other)
    assert (tmp_path / "other.xml").read_bytes() == before


def test_a_bad_file_leaves_no_error_file_behind(tmp_path) -> None:
    """With "gui" forced True, a failed parse writes ERROR_FILE -- which userintr reads at
    startup to show an error from a previous session.

    Left there, a comparison file that would not load would greet the user at next launch
    as though their own configuration had failed to load.
    """
    assert not os.path.exists(ERROR_FILE)
    diffload.load_for_comparison(_write(tmp_path, "bad.xml", _MALFORMED_XML))
    assert not os.path.exists(ERROR_FILE)


def test_a_pre_existing_error_file_survives(tmp_path) -> None:
    """A real error waiting to be shown is not collateral damage of a comparison."""
    with open(ERROR_FILE, "wb") as error_file:  # noqa: PTH123
        error_file.write(b"a real error\n1\n")

    diffload.load_for_comparison(_write(tmp_path, "bad.xml", _MALFORMED_XML))

    with open(ERROR_FILE, "rb") as error_file:  # noqa: PTH123
        assert error_file.read() == b"a real error\n1\n"


def test_the_directory_list_is_not_polluted(tmp_path) -> None:
    """With "directory" on, conditions_to_name appends every unnamed Profile it names to
    PrimeItems.directory_items -- which belongs to the map of the loaded file.

    The flag is forced off for the duration; the deep-copy restore is the backstop, and
    this asserts the pair of them together.
    """
    PrimeItems.program_arguments["directory"] = True
    PrimeItems.directory_items["profiles"] = ["already here"]

    diffload.load_for_comparison(_write(tmp_path, "unnamed.xml", _UNNAMED_PROFILE_XML))

    assert PrimeItems.directory_items["profiles"] == ["already here"]
    assert PrimeItems.program_arguments["directory"] is True


def test_output_lines_are_not_polluted(tmp_path) -> None:
    """A failed parse appends to the running output, which belongs to the loaded file's map."""
    PrimeItems.output_lines.output_lines = ["the loaded file's map"]
    diffload.load_for_comparison(_write(tmp_path, "bad.xml", _MALFORMED_XML))
    assert PrimeItems.output_lines.output_lines == ["the loaded file's map"]


def test_a_bad_file_before_any_map_has_been_built(tmp_path) -> None:
    """PrimeItems.output_lines is None until a map has been rendered, and a comparison can
    happen before that.

    taskerd's own error path calls PrimeItems.output_lines.add_line_to_output, so in that
    state a malformed file comes back as an AttributeError from inside the error handler
    rather than as a return code.  It still has to reach the user as a message.
    """
    PrimeItems.output_lines = None
    before = _snapshot()

    configuration, message = diffload.load_for_comparison(_write(tmp_path, "bad.xml", _MALFORMED_XML))

    assert configuration is None
    assert message
    for name, value in before.items():
        assert _snapshot()[name] is value, f"PrimeItems.{name} was not restored"


# ##################################################################################
# The current side of the comparison.
# ##################################################################################
def test_current_configuration_describes_the_loaded_file(tmp_path) -> None:
    """The loaded configuration, as one side of a comparison."""
    configuration = diffload.current_configuration()

    assert configuration.path.endswith("loaded.xml")
    assert configuration.tables is PrimeItems.tasker_root_elements
    assert configuration.root is PrimeItems.xml_root
    assert configuration.when is not None


def test_loaded_file_path_handles_a_plain_string() -> None:
    """PrimeItems.file_to_get is sometimes an open file object and sometimes a path.

    getxml_event assigns the path as a plain string; proginit assigns an open file.  Both
    reach this module, so both have to work.
    """
    PrimeItems.file_to_get = "/somewhere/plain.xml"
    assert diffload.loaded_file_path() == "/somewhere/plain.xml"

    PrimeItems.file_to_get = ""
    assert diffload.loaded_file_path() == ""


# ##################################################################################
# The pieces the GUI event is built out of.
# ##################################################################################
def test_original_of_finds_the_file_a_save_copy_came_from(tmp_path) -> None:
    """"Save To Current File" writes backup_20260721_143005.xml next to backup.xml.

    Both halves stay on disk, which is what makes "what did my own edit change?"
    answerable with no file picker at all.
    """
    original = _write(tmp_path, "backup.xml", _GOOD_XML)
    copy = _write(tmp_path, "backup_20260721_143005.xml", _GOOD_XML)

    assert diffload.original_of(copy) == original


def test_original_of_declines_when_there_is_nothing_to_offer(tmp_path) -> None:
    """No timestamp suffix, or the original since moved away, means no offer.

    Both fall back to the file picker rather than to a path that is not there.
    """
    plain = _write(tmp_path, "backup.xml", _GOOD_XML)
    assert diffload.original_of(plain) == ""
    assert diffload.original_of("") == ""

    # The right shape of name, but nothing next to it.
    orphan = _write(tmp_path, "gone_20260721_143005.xml", _GOOD_XML)
    assert diffload.original_of(orphan) == ""


def test_original_of_uses_the_same_pattern_that_writes_the_names() -> None:
    """The suffix pattern is read from maputil2, not copied.

    A second copy of it over here would be free to drift away from the one that writes
    the file names, and the offer would quietly stop appearing.
    """
    from maptasker.src.maputil2 import TIMESTAMP_SUFFIX_RE  # noqa: PLC0415

    assert TIMESTAMP_SUFFIX_RE.search("_20260721_143005")
    assert not TIMESTAMP_SUFFIX_RE.search("_2026072_143005")


def test_order_by_age_puts_the_older_file_first(tmp_path) -> None:
    """Whichever way round the user picked them, "added" means added in the newer file."""
    from datetime import datetime  # noqa: PLC0415

    from maptasker.src.xmldiff import Configuration  # noqa: PLC0415

    early = Configuration(path="early.xml", tables={}, when=datetime(2026, 1, 1))  # noqa: DTZ001
    late = Configuration(path="late.xml", tables={}, when=datetime(2026, 6, 1))  # noqa: DTZ001

    assert diffload.order_by_age(late, early) == (early, late)
    assert diffload.order_by_age(early, late) == (early, late)


def test_order_by_age_keeps_the_given_order_without_timestamps() -> None:
    """A file fetched from an Android device has no usable local timestamp.

    Guessing is worse than leaving it: the report header names both files either way.
    """
    from maptasker.src.xmldiff import Configuration  # noqa: PLC0415

    first = Configuration(path="a.xml", tables={}, when=None)
    second = Configuration(path="b.xml", tables={}, when=None)

    assert diffload.order_by_age(first, second) == (first, second)
    assert diffload.order_by_age(second, first) == (second, first)


def test_write_comparison_report(tmp_path) -> None:
    """The report is written to a timestamped file in the current directory."""
    file_name = diffload.write_comparison_report("a report\n")

    assert file_name.startswith("MapTasker_Compare_")
    assert file_name.endswith(".txt")
    assert (tmp_path / file_name).read_text(encoding="utf-8") == "a report\n"


def test_the_two_sides_compare(tmp_path) -> None:
    """The point of all of this: two Configurations that xmldiff can actually compare."""
    from maptasker.src.xmldiff import compare  # noqa: PLC0415

    other, message = diffload.load_for_comparison(_write(tmp_path, "other.xml", _OTHER_XML))
    assert message == ""

    report, counts = compare(other, diffload.current_configuration())

    assert "[PROJECT-ADDED]  Project 'Loaded'" in report
    assert "[PROJECT-REMOVED]  Project 'Other'" in report
    assert counts["ADDED"] and counts["REMOVED"]
