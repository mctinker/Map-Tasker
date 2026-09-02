"""Round-trip regression tests for the edit path (roundtrip.py) Unit Tests

WHAT THIS FILE IS GUARDING

The edit path now writes XML back into people's live Tasker configurations.  Every one of
those writes is the same two steps -- serialize an in-memory element, hand the text to the
device -- and neither step reports a value that did not survive it.  The upload answers 200.
The readback compares the bytes that were sent against the bytes that landed, and they match,
because both are already wrong.  The user finds out in Tasker, later, in a Task that has
quietly stopped doing what it did.

So: parse -> render -> re-parse, and assert the objects that nobody edited come back
identical.  That is the cheapest possible guard against corrupting a backup, and it is what
these tests assert about all four export renderers at once.

THE ONE THAT IS NOT HYPOTHETICAL

test_a_carriage_return_in_a_name_is_caught is the reason the fixed-point check exists.
ElementTree escapes \\r inside an ATTRIBUTE value (as &#13;) and not inside element TEXT,
and every XML parser normalizes a bare \\r in text to \\n -- so a carriage return anywhere in
a Task's name or an Action's argument is silently rewritten the moment the file is read
back, with nothing anywhere in the save path noticing.  A user who pastes multi-line text
copied off a Windows machine into an Action hits exactly this.

WHAT IS DELIBERATELY NOT ASSERTED

That a rendered export is byte-identical to what Tasker itself would write.  That is
test_project_export.py's and test_single_item_export.py's job, against measured sample data.
This file only asserts that whatever this program renders, it can read back unchanged --
which is a property it must have regardless of what the right output turns out to be.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from maptasker.src import profedit, projedit, roundtrip, taskedit, taskerd, userintr
from maptasker.src.primitem import PrimeItems

# One Project owning one Profile, that Profile's Entry Task, a Scene the Project declares,
# and the Task that Scene's button fires.  Small, but it is every relationship the four
# renderers bundle by: <pids>, <mid0>, <scenes>, <tids> and a Scene element's <clickTask>.
#
# 'Opener' carries a trailing space inside <nme> and an <Action> argument holding a tab and
# a newline on purpose.  Those are the values a comparison that normalizes whitespace would
# lose, and losing them is indistinguishable from the corruption this is looking for.
_FIXTURE_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
\t<dmetric>2800.0,1752.0</dmetric>
\t<Profile sr="prof100" ve="2">
\t\t<id>100</id>
\t\t<mid0>20</mid0>
\t\t<nme>Watching</nme>
\t</Profile>
\t<Project sr="proj7" ve="2">
\t\t<cdate>1700000000000</cdate>
\t\t<id>f19b5151-01b6-46f6-8cd5-b3bc1fe0b486</id>
\t\t<mdate>1786121691586</mdate>
\t\t<name>Home</name>
\t\t<pids>100</pids>
\t\t<scenes>Dialog</scenes>
\t\t<tids>20</tids>
\t</Project>
\t<Scene sr="scene0">
\t\t<nme>Dialog</nme>
\t\t<RectElement sr="rect0">
\t\t\t<clickTask>30</clickTask>
\t\t</RectElement>
\t</Scene>
\t<Task sr="task20">
\t\t<id>20</id>
\t\t<nme>Opener </nme>
\t\t<pri>100</pri>
\t\t<Action sr="act0" ve="7">
\t\t\t<code>547</code>
\t\t\t<Str sr="arg1" ve="3">line one
line two\tafter a tab</Str>
\t\t</Action>
\t</Task>
\t<Task sr="task30">
\t\t<id>30</id>
\t\t<nme>Tapped</nme>
\t</Task>
</TaskerData>
"""


@pytest.fixture(autouse=True)
def loaded() -> None:
    """The PrimeItems tables, built from the fixture the way taskerd builds them from a file."""
    root = ET.fromstring(_FIXTURE_XML)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100, "language": "English"}
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": [],
    }


def _live(table: str, key: str) -> ET.Element:
    """One element straight out of the loaded tables -- what a renderer copies from."""
    return PrimeItems.tasker_root_elements[table][key]["xml"]


def _editable_task(task_id: str) -> taskedit.EditableTask:
    """An Edit Task dialog's working model over a live Task, with no edits made to it."""
    return taskedit.EditableTask(task_id=task_id, task_element=_live("all_tasks", task_id))


def _editable_profile(profile_id: str) -> profedit.EditableProfile:
    """An Edit Profile dialog's working model over a live Profile, with no edits made."""
    return profedit.EditableProfile(
        profile_id=profile_id,
        profile_element=_live("all_profiles", profile_id),
        entry_task_id="20",
    )


# ==========================================
# The four exports, unedited: everything must come back exactly as it went out.
# ==========================================
def test_a_task_export_round_trips() -> None:
    """The simplest case, and the one every other export contains: one Task, deep-copied
    into a TaskerData wrapper and serialized.  Nothing about it may change."""
    report = roundtrip.verify_task(_editable_task("20"))

    assert report.ok, report.detail()
    assert report.checked == ("Task '20'",)


def test_a_profile_export_round_trips_with_its_linked_task() -> None:
    """A Profile is not meaningful to Tasker without the Task it points at, so the export
    bundles one it did not edit -- exactly the "untouched object" this file is named for."""
    report = roundtrip.verify_profile(_editable_profile("100"))

    assert report.ok, report.detail()
    assert set(report.checked) == {"Profile '100'", "Task '20'"}


def test_a_project_export_round_trips_with_everything_it_carries() -> None:
    """The widest one: a Project export bundles its Profiles, its Scenes, the Tasks those
    Profiles fire, the Tasks its Scenes' buttons fire, and <dmetric>.  Not one of them is
    the object being edited, and every one of them is written into a live configuration."""
    report = roundtrip.verify_project("Home")

    assert report.ok, report.detail()
    assert set(report.checked) == {"dmetric", "Profile '100'", "Scene 'Dialog'", "Task '20'", "Task '30'"}


def test_a_scene_export_round_trips_with_the_tasks_its_buttons_fire() -> None:
    """A Scene's <clickTask> is an id and nothing else, so the export carries the Task too
    -- another object the user never opened, going onto their device."""
    report = roundtrip.verify_scene("Dialog")

    assert report.ok, report.detail()
    assert set(report.checked) == {"dmetric", "Scene 'Dialog'", "Task '30'"}


# ==========================================
# The exemption, and its exact size.
# ==========================================
def test_only_the_exported_project_is_exempt_from_comparison() -> None:
    """render_standalone_project_xml rewrites the exported Project on purpose -- sr to
    "proj0", <pids> ahead of <tids>, a synthesized identity -- all of which Tasker's
    importer requires.  So it cannot be compared against the live element, and the report
    has to SAY it was not compared rather than counting it as verified."""
    report = roundtrip.verify_project("Home")

    assert report.exempt == ("Project 'Home'",)
    assert "Project 'Home'" not in report.checked
    assert any("Project 'Home'" in line for line in report.detail())


def test_the_exempt_project_is_still_renumbered() -> None:
    """The exemption is real, not defensive: without it this export fails check 2 outright,
    because sr="proj7" in the backup becomes sr="proj0" in the export.  Asserting the
    rewrite happens is what keeps the exemption honest -- if the renumber were ever dropped,
    this test says so instead of the exemption silently covering for it."""
    exported = ET.fromstring(projedit.render_standalone_project_xml("Home"))  # noqa: S314

    assert _live("all_projects", "Home").get("sr") == "proj7"
    assert exported.find("Project").get("sr") == "proj0"


# ==========================================
# What the checks actually catch.
# ==========================================
def test_a_carriage_return_in_a_name_is_caught() -> None:
    """The flagship catch, and not a hypothetical: ElementTree writes a bare \\r into
    element text unescaped, and the XML spec has every parser normalize it to \\n on the way
    back in.  So this Task's name arrives on the device as something the user never typed,
    and every existing check in the save path -- the 200, the byte-for-byte readback --
    passes, because they all compare the already-wrong bytes against themselves."""
    _live("all_tasks", "20").find("nme").text = "Open\rer"

    report = roundtrip.verify_task(_editable_task("20"))

    assert not report.ok
    assert not report.fixed_point
    assert report.differences["Task '20'"][0].was == "Open\rer"
    assert report.differences["Task '20'"][0].now == "Open\ner"


def test_a_changed_value_names_the_object_and_the_path() -> None:
    """A report nobody can act on is not much better than no report.  When an object comes
    back different, the message has to say which object, where inside it, and what the two
    values were -- so this asserts the whole triple, not just that something failed."""
    rendered = taskedit.render_standalone_task_xml(_editable_task("20"))

    report = roundtrip.verify_rendered(rendered.replace("<pri>100</pri>", "<pri>50</pri>"))

    (difference,) = report.differences["Task '20'"]
    assert not report.ok
    assert difference.where == "Task/pri[2] text"
    assert (difference.was, difference.now) == ("100", "50")


def test_a_dropped_child_is_caught() -> None:
    """The other shape corruption takes: not a wrong value but a missing element.  Compared
    by position rather than resynchronized, so what is reported is the count -- which is the
    fact that matters when an Action has lost an argument."""
    rendered = taskedit.render_standalone_task_xml(_editable_task("20"))

    report = roundtrip.verify_rendered(rendered.replace("\t\t<pri>100</pri>\n", ""))

    assert not report.ok
    assert any("child elements" in difference.was for difference in report.differences["Task '20'"])


def test_xml_that_will_not_parse_is_reported_as_such() -> None:
    """The worst outcome, and the one worth separating from the others: there is nothing to
    compare against a document that is not XML, so the report says that and stops rather
    than reporting zero differences -- which is what a bare "no mismatches" would say."""
    report = roundtrip.verify_rendered("<TaskerData><Task><nme>unclosed</TaskerData>")

    assert not report.ok
    assert report.error
    assert report.checked == ()


# ==========================================
# What the checks must NOT catch -- the false positives that would make Verify useless.
# ==========================================
def test_meaningful_whitespace_inside_a_value_is_not_a_difference() -> None:
    """'Opener ' has a trailing space and the fixture's <Str> holds a tab and a newline.
    Those are content, and they survive the trip -- a check that normalized them away would
    pass on a save that had genuinely lost them, and one that treated INDENTATION as content
    would fail on every save.  Both halves are asserted here because the fixture carries
    both kinds of whitespace."""
    report = roundtrip.verify_task(_editable_task("20"))

    assert report.ok, report.detail()
    assert _live("all_tasks", "20").findtext("nme") == "Opener "
    assert "\t" in _live("all_tasks", "20").find("Action/Str").text


def test_reindenting_the_export_is_not_a_difference() -> None:
    """The backup a Project was loaded from is indented however Tasker wrote it, and the
    export is re-indented with tabs.  Every object in every export would fail if that
    counted, so the fixed-point check has to compare the export against a re-render of
    ITSELF rather than against the file."""
    compact = ET.fromstring(_FIXTURE_XML.replace("\n\t", "").replace("\n", ""))  # noqa: S314
    PrimeItems.xml_root = compact
    PrimeItems.tasker_root_elements["all_tasks"] = taskerd.move_xml_to_table(compact.findall("Task"), True, "nme")

    report = roundtrip.verify_task(_editable_task("30"))

    assert report.ok, report.detail()


def test_a_brand_new_object_is_compared_against_the_dialog_that_holds_it() -> None:
    """An Add Task's Task is not in the loaded tables until the save succeeds, so there is
    nothing there to compare it against.  Without the override it would be skipped as
    unchecked -- i.e. the one save with no prior version to fall back on would be the one
    save that got no verification."""
    new_task = taskedit.create_new_task("Fresh", "100")
    assert not isinstance(new_task, str), new_task

    report = roundtrip.verify_task(new_task)

    assert report.ok, report.detail()
    assert report.checked == (f"Task '{new_task.task_id}'",)
    assert report.unchecked == ()


def test_an_object_with_nothing_to_compare_against_is_reported_not_failed() -> None:
    """A document holding an object the tables have never seen is not evidence of
    corruption -- it is evidence that this check could not speak to it.  Saying so is the
    honest answer; failing the save over it would block a legitimate one."""
    report = roundtrip.verify_rendered(
        '<TaskerData sr="" dvi="1" tv="6.3.13">\n\t<Task sr="task99">\n\t\t<id>99</id>\n\t</Task>\n</TaskerData>\n',
    )

    assert report.ok
    assert report.unchecked == ("Task '99'",)
    assert any("99" in line for line in report.detail())


# ==========================================
# The report itself -- it is what the user sees, so it is worth asserting.
# ==========================================
def test_a_clean_report_counts_what_it_checked() -> None:
    """The success message has to say how much was actually verified.  "Verified" on its
    own is what a check that silently skipped everything would also say."""
    assert roundtrip.verify_project("Home").summary() == "Verified: 5 objects came back identical."


def test_a_failing_report_leads_with_the_failure() -> None:
    """One line, in a notification, next to a save that has just been refused: it has to
    name the count of objects that changed, not the count that passed."""
    _live("all_tasks", "20").find("nme").text = "Open\rer"

    assert roundtrip.verify_profile(_editable_profile("100")).summary() == (
        "Verify FAILED: 1 object changed on the round trip."
    )


# ==========================================
# The checkbox itself -- what the eight Save To Android handlers do with the answer.
# ==========================================
def _panel(*, ticked: bool) -> dict:
    """A Save To Android panel's field refs, with "Verify" in the given state."""
    return {"verify": SimpleNamespace(value=ticked)}


def test_an_unticked_verify_does_not_even_render() -> None:
    """The whole of the old behaviour, kept: an unticked box costs a dict lookup.  The
    verifier is a callable rather than a report precisely so the second render it would do
    never happens -- for a Project export that is every Profile, Scene and Task in it."""
    called = []

    assert userintr._round_trip_verified(_panel(ticked=False), lambda: called.append(1))  # noqa: SLF001
    assert called == []


def test_a_ticked_verify_that_passes_lets_the_save_through_and_says_so() -> None:
    """A user who ticked this wants to be told it ran.  Without the message, a check that
    passed and a checkbox that did nothing look exactly alike."""
    with patch.object(userintr, "ui") as fake_ui:
        verified = userintr._round_trip_verified  # noqa: SLF001
        allowed = verified(_panel(ticked=True), lambda: roundtrip.verify_project("Home"))

    assert allowed
    assert fake_ui.notify.call_args.kwargs["type"] == "positive"


def test_a_ticked_verify_that_fails_stops_the_save_before_the_device_is_touched() -> None:
    """The point of the feature.  False here returns out of the handler ahead of
    ping_android_device, so a failing document reaches neither the upload nor the
    reachability probe -- and the report dialog is what the user is left looking at."""
    _live("all_tasks", "20").find("nme").text = "Open\rer"

    with (
        patch.object(userintr, "ui") as fake_ui,
        patch.object(userintr, "build_round_trip_report_dialog") as fake_dialog,
    ):
        verified = userintr._round_trip_verified  # noqa: SLF001
        allowed = verified(_panel(ticked=True), lambda: roundtrip.verify_task(_editable_task("20")))

    assert not allowed
    assert fake_ui.notify.call_args.kwargs["type"] == "negative"
    assert not fake_dialog.call_args.args[0].ok


def test_a_panel_without_the_checkbox_is_not_a_failure() -> None:
    """Belt and braces for a caller that has not been given the field yet -- an absent
    checkbox reads as unticked, not as a save to refuse."""
    assert userintr._round_trip_verified({}, lambda: roundtrip.verify_project("Home"))  # noqa: SLF001
