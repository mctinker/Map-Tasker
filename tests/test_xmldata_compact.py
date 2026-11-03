"""Compact Tasker backups: attributes written with no whitespace between them.

Tasker 6.7.6-beta writes <TaskerData sr=""dvi="1"tv="6.7.6-beta">, which strict XML
parsers reject as "not well-formed (invalid token)" and MapTasker reported as invalid XML.
"""

from __future__ import annotations

import defusedxml.ElementTree as ET
import pytest
from maptasker.src.core import xmldata
from maptasker.src.core.xmldata import parse_tasker_xml, separate_attributes

from tests.doubles import required

COMPACT = (
    b'<TaskerData sr=""dvi="1"tv="6.7.6-beta">'
    b'<Task sr="task7"><id>7</id><nme>Say "a"b="c"</nme>'
    b'<Action sr="act0"ve="7"><code>548</code><Str sr="arg0"ve="3">hi</Str>'
    b'<Int sr="arg1"val="0"/></Action></Task></TaskerData>'
)


def test_separate_attributes_touches_only_tags() -> None:
    """Spaces go between attributes inside tags, never into text content."""
    fixed = separate_attributes(COMPACT)
    assert fixed.startswith(b'<TaskerData sr="" dvi="1" tv="6.7.6-beta">')
    assert b'<Int sr="arg1" val="0"/>' in fixed
    # Text content that merely looks like attributes is left alone.
    assert b'<nme>Say "a"b="c"</nme>' in fixed


def test_parse_compact_backup(tmp_path) -> None:
    """A compact backup loads, and the file on disk is left unchanged."""
    backup = tmp_path / "compact.xml"
    backup.write_bytes(COMPACT)
    root = parse_tasker_xml(str(backup)).getroot()
    assert required(root).tag == "TaskerData"
    assert required(root).attrib == {"sr": "", "dvi": "1", "tv": "6.7.6-beta"}
    assert required(required(root).find("Task/Action/Int")).attrib == {"sr": "arg1", "val": "0"}
    # The user's file is not rewritten.
    assert backup.read_bytes() == COMPACT


def test_parse_still_rejects_broken_xml(tmp_path) -> None:
    """Genuinely malformed XML is still reported as a parse error."""
    backup = tmp_path / "broken.xml"
    backup.write_bytes(b'<TaskerData sr=""><Task></TaskerData>')
    with pytest.raises(ET.ParseError):
        parse_tasker_xml(str(backup))


# ##################################################################################
# A string argument with an element inside it
# ##################################################################################
def test_a_string_that_holds_an_element_has_no_text_of_its_own() -> None:
    """A damaged file can leave a <Str> unclosed, so the next Task lands inside it.

    What the element then holds as text is the indentation the file happens to have, and a configuration saved and
    loaded again has different indentation -- so the action read differently the second time (the fuzz of the
    round trip drew it: "Flash Text=Alarm checked" before the save, "... Position=<spaces>" after).
    """
    before = ET.fromstring('<Action><Str sr="arg13" ve="3"><Task sr="task107"/></Str></Action>')
    after = ET.fromstring('<Action><Str sr="arg13" ve="3">\n\t\t\t\t<Task sr="task107"/>\n\t\t\t</Str></Action>')

    assert xmldata.extract_string(before, "arg13", "Position=") == ""
    assert xmldata.extract_string(after, "arg13", "Position=") == ""


def test_a_string_of_only_spaces_is_still_a_value() -> None:
    action = ET.fromstring('<Action><Str sr="arg0" ve="3">   </Str></Action>')

    assert xmldata.extract_string(action, "arg0", "Text=") == "Text=   "
