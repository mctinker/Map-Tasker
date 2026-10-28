"""MapTasker TaskerNet description (tndesc) Unit Tests

A description is <Share><d> on a Project, Profile or Task.  What is tested is that it is written the way Tasker
writes it (the same children, in the same place among the object's own), that clearing one puts the object back as
it was, that an existing <Share>'s tags and flags are never disturbed, that every toolbar button writes what its
tooltip says, and that the HTML check says what is wrong with a description and stays quiet about what is not.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from maptasker.src.core import tndesc

SAMPLES = Path(__file__).parent.parent / "XML"


def tool_for(key: str) -> tndesc.Tool:
    """The toolbar tool with this key."""
    return next(tool for tool in tndesc.TOOLS if tool.key == key)


def element(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def children(parent: ET.Element) -> list[str]:
    return [child.tag for child in parent]


_TASK = "<Task sr='task1'><cdate>1</cdate><id>5</id><nme>T</nme><pri>100</pri><Action sr='act0'><code>1</code></Action></Task>"
_PROJECT = "<Project sr='proj0'><name>P</name><pids>1</pids><tids>2</tids><Kid sr='Kid'/><Img sr='Img'/><ProfileVariable sr='v'/></Project>"


# ##################################################################################
# The element.
# ##################################################################################
def test_a_description_is_added_after_the_lowercase_children_and_before_the_actions() -> None:
    task = element(_TASK)

    tndesc.set_description(task, "Does a thing")

    assert children(task) == ["cdate", "id", "nme", "pri", "Share", "Action"]
    share = task.find("Share")
    assert share is not None
    assert share.attrib == {"sr": "Share"}
    assert [(child.tag, child.text) for child in share] == [
        ("b", "false"),
        ("d", "Does a thing"),
        ("p", "false"),
        ("t", ""),
    ]
    assert tndesc.description_of(task) == "Does a thing"


def test_on_a_project_it_goes_after_kid_and_before_img_and_the_variables() -> None:
    project = element(_PROJECT)

    tndesc.set_description(project, "x")

    assert children(project) == ["name", "pids", "tids", "Kid", "Share", "Img", "ProfileVariable"]


def test_an_existing_share_keeps_its_tags_and_flags_when_the_description_changes() -> None:
    task = element(
        "<Task><id>1</id><Share sr='Share'><b>true</b><d>old</d><g>Basics,Apps</g><p>true</p><t>HTTP</t></Share></Task>"
    )

    tndesc.set_description(task, "new <b>text</b>")

    share = task.find("Share")
    assert share is not None
    assert [(child.tag, child.text) for child in share] == [
        ("b", "true"),
        ("d", "new <b>text</b>"),
        ("g", "Basics,Apps"),
        ("p", "true"),
        ("t", "HTTP"),
    ]


def test_clearing_a_description_puts_the_object_back_as_it_was() -> None:
    task = element(_TASK)
    before = ET.tostring(task)
    tndesc.set_description(task, "something")

    tndesc.set_description(task, "   \n ")

    assert ET.tostring(task) == before


def test_clearing_a_description_keeps_a_share_that_still_says_something() -> None:
    task = element(
        "<Task><id>1</id><Share sr='Share'><b>false</b><d>old</d><g>Basics</g><p>false</p><t></t></Share></Task>"
    )

    tndesc.set_description(task, "")

    share = task.find("Share")
    assert share is not None
    assert share.findtext("d") == ""
    assert share.findtext("g") == "Basics"
    assert tndesc.has_description(task) is False


def test_clearing_an_object_that_has_no_description_changes_nothing() -> None:
    task = element(_TASK)
    before = ET.tostring(task)

    tndesc.set_description(task, "")

    assert ET.tostring(task) == before


def test_line_ends_are_stored_as_tasker_writes_them() -> None:
    task = element(_TASK)

    tndesc.set_description(task, "a\r\nb\rc")

    assert tndesc.description_of(task) == "a\nb\nc"


def test_markup_survives_the_xml_round_trip() -> None:
    task = element(_TASK)
    text = 'Call <a href="https://x.example.com/?a=1&b=2">here</a> & <br/> there'

    tndesc.set_description(task, text)
    reread = ET.fromstring(ET.tostring(task))

    assert tndesc.description_of(reread) == text


def test_mirror_share_makes_one_element_match_the_other_in_both_directions() -> None:
    source = element(_PROJECT)
    target = element(_PROJECT)
    tndesc.set_description(source, "hello")

    tndesc.mirror_share(source, target)
    assert ET.tostring(target) == ET.tostring(source)

    tndesc.set_description(source, "")
    tndesc.mirror_share(source, target)
    assert target.find("Share") is None


def test_a_description_is_never_taken_for_an_object_with_nothing() -> None:
    assert tndesc.has_description(element(_TASK)) is False
    assert tndesc.description_of(element(_TASK)) == ""


# ##################################################################################
# The toolbar.
# ##################################################################################
def test_a_selection_is_wrapped_and_stays_selected() -> None:
    edit = tndesc.apply_tool("make this loud", 5, 9, tool_for("bold"))

    assert edit.text == "make <b>this</b> loud"
    assert edit.text[edit.start : edit.end] == "this"


def test_with_nothing_selected_the_placeholder_is_put_in_and_selected() -> None:
    edit = tndesc.apply_tool("ab", 1, 1, tool_for("italic"))

    assert edit.text == "a<i>italic text</i>b"
    assert edit.text[edit.start : edit.end] == "italic text"


def test_a_tool_with_nothing_to_close_is_set_down_after_the_selection() -> None:
    edit = tndesc.apply_tool("one two", 0, 3, tool_for("break"))

    assert edit.text == "one<br/> two"
    assert edit.start == edit.end == len("one<br/>")


def test_a_link_uses_the_address_given_and_a_placeholder_when_there_is_none() -> None:
    link = tool_for("link")

    given = tndesc.apply_tool("see docs", 4, 8, link, address=" https://example.com/a?b=1 ")
    none = tndesc.apply_tool("x", 0, 1, link)

    assert given.text == 'see <a href="https://example.com/a?b=1">docs</a>'
    assert none.text == '<a href="https://">x</a>'


def test_an_address_cannot_break_out_of_its_attribute() -> None:
    image = tool_for("image")

    edit = tndesc.apply_tool("", 0, 0, image, address='x" onerror="alert(1)')

    assert 'onerror="' not in edit.text
    assert tndesc.check(edit.text) == []


def test_a_color_is_the_one_chosen() -> None:
    color = tool_for("color")

    assert tndesc.apply_tool("hi", 0, 2, color, color="blue").text == '<font color="blue">hi</font>'


def test_choosing_another_color_for_colored_text_changes_it_instead_of_nesting() -> None:
    color = tool_for("color")
    text = '<font color="red">hi</font>'

    edit = tndesc.apply_tool(text, 18, 20, color, color="blue")

    assert edit.text == '<font color="blue">hi</font>'
    assert text[18:20] == "hi"
    assert edit.text[edit.start : edit.end] == "hi"


def test_a_heading_tool_is_any_of_the_six_and_falls_back_to_a_sensible_one() -> None:
    assert tndesc.apply_tool("t", 0, 1, tndesc.heading_tool("h2")).text == "<h2>t</h2>"
    assert tndesc.apply_tool("t", 0, 1, tndesc.heading_tool("nonsense")).text == "<h3>t</h3>"


def test_a_stale_selection_is_clamped_to_the_text() -> None:
    edit = tndesc.apply_tool("ab", 50, 99, tool_for("bold"))

    assert edit.text == "ab<b>bold text</b>"


@pytest.mark.parametrize("tool", tndesc.TOOLS, ids=lambda tool: tool.key)
def test_every_button_writes_markup_that_checks_clean(tool: tndesc.Tool) -> None:
    edit = tndesc.apply_tool("some text", 0, 4, tool, address="https://example.com", color="red")

    assert tndesc.check(edit.text) == [], edit.text
    assert tool.tooltip and tool.icon and tool.label


def test_line_breaks_are_added_once_and_only_where_a_line_does_not_already_end_a_tag() -> None:
    once = tndesc.add_line_breaks("one\ntwo<br/>\nthree\nfour")

    assert once == "one<br/>\ntwo<br/>\nthree<br/>\nfour"
    assert tndesc.add_line_breaks(once) == once
    assert tndesc.add_line_breaks("single line") == "single line"


# ##################################################################################
# The check.
# ##################################################################################
def messages(text: str) -> list[str]:
    return [issue.message for issue in tndesc.check(text)]


def test_plain_text_and_sound_html_check_clean() -> None:
    assert tndesc.check("Just words,\n\nand more words.") == []
    assert (
        tndesc.check("<p>Hi <b>there</b></p><ul><li>one<li>two</ul><br/><img src='https://x.example.com/a.png'/></img>")
        == []
    )


def test_an_unclosed_tag_is_named() -> None:
    assert messages("<b>never ends") == ["<b> is never closed."]
    assert messages("<b><i>x</b>") == ["<i> is never closed."]


def test_a_closing_tag_with_no_opener_is_named_but_a_stray_optional_one_is_let_go() -> None:
    assert messages("x</b>") == ["</b> closes nothing: there is no <b> before it."]
    assert messages("x</p>") == []


def test_script_and_event_handlers_and_javascript_links_are_warnings() -> None:
    found = tndesc.check('<script>x()</script><a href="javascript:go()" onclick="x()">y</a>')

    assert {issue.severity for issue in found} == {tndesc.WARNING}
    text = " ".join(issue.message for issue in found)
    assert "<script>" in text
    assert "onclick" in text
    assert "not a link to a web page" in text


def test_a_taskernet_share_link_is_not_flagged() -> None:
    link = '<a href="taskershare://AS35m8nuYE%3D/Project%3AVoice%20Command">Import it</a>'

    assert tndesc.check(link) == []


def test_a_tag_nobody_else_uses_is_information_not_a_warning() -> None:
    (issue,) = tndesc.check("<blink>hi</blink>")

    assert issue.severity == tndesc.INFO
    assert "<blink>" in issue.message


def test_an_image_stored_in_the_description_is_flagged_only_when_it_is_not_small() -> None:
    small = '<img src="data:image/png;base64,AAAA"/>'
    large = f'<img src="data:image/png;base64,{"A" * 25_000}"/>'

    assert tndesc.check(small) == []
    (issue,) = tndesc.check(large)
    assert issue.severity == tndesc.WARNING
    assert "small images" in issue.message


def test_the_same_problem_many_times_is_one_finding_and_many_findings_are_capped() -> None:
    assert len(tndesc.check("<script></script>" * 40)) == 1

    shown = tndesc.check("".join(f"<x{n}/>" for n in range(30)))
    assert len(shown) == 9
    assert shown[-1].message == "...and 22 more."


def test_page_wrapper_tags_are_not_complained_about_or_left_open() -> None:
    assert tndesc.check("<html><head></head><body><p>hi</p></body></html>") == []
    assert tndesc.check("<html><body><p>hi") == []


# ##################################################################################
# The sample backups.
# ##################################################################################
def _sample_descriptions() -> list[str]:
    found: list[str] = []
    for path in sorted(SAMPLES.glob("*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        found.extend(d.text for d in root.iter("d") if d.text)
    return found


@pytest.mark.skipif(not SAMPLES.is_dir(), reason="no sample backups here")
def test_what_real_shares_say_is_read_back_unchanged_and_almost_never_flagged() -> None:
    texts = _sample_descriptions()
    assert texts, "the sample backups hold descriptions"

    for text in texts[:300]:
        task = element(_TASK)
        tndesc.set_description(task, text)
        assert tndesc.description_of(ET.fromstring(ET.tostring(task))) == _normalised(text)

    warned = sum(any(i.severity == tndesc.WARNING for i in tndesc.check(text)) for text in texts)
    assert warned / len(texts) < 0.15, "a check that cries wolf on real shares teaches people to ignore it"


def _normalised(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
