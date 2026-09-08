"""MapTasker secrets/PII scan and redacted-export Unit Tests

piiscan is one detector with two callers -- the Health Check, which says what is in a
configuration, and the Redact option on the standalone exports, which takes the same things
out.  These tests are shaped around that: the rule tests below pin what each rule does and,
just as importantly, what it declines to do, and the last group asserts the property that
makes the pair worth having -- that what the scan REPORTS is what the redactor REMOVES.

The false negatives are as deliberate as the hits and are asserted as such.  A rule that
fires on a Tasker variable reference would be telling the user off for having already done
the right thing, and a redactor that rewrote a name would produce a file that imports and
then quietly does nothing.  Both are easy to break by "improving" a pattern, and neither
would show up in a test that only checked that secrets are found.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest
from maptasker.src import mapjump, piiscan, taskerd
from maptasker.src.colrmode import set_color_mode
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.lineout import LineOut
from maptasker.src.mapjump import TASK, Target
from maptasker.src.primitem import PrimeItems
from maptasker.src.share import share

# One of everything, with its clean counterpart alongside it.
#
#   Task 20 'Leaky'     act0  HTTP Auth with a real Password and Username -> SECRET-CREDENTIAL
#                       act1  the same, filled in with variables          -> nothing (indirection)
#                       act2  an Authorization header with a bearer token -> SECRET-TOKEN
#                       act3  Perform Task naming a Task whose NAME is an email -> nothing
#                       act4  a plugin bundle holding an email address     -> PII-EMAIL
#   Task 21 'bob@example.com'  a Task whose name is an email.  Reported nowhere and, above
#                       all, never rewritten -- act3 above finds it by that name.
#   Profile 10 'Home'   a Loc carrying real coordinates -> PII-LOCATION
#   Profile 11 'Blank'  a Loc that was created and never filled in -> nothing
#   Scene 'Panel'       a label holding a phone number -> PII-PHONE
#   %ApiKey             a global variable holding an OpenAI key -> SECRET-API-KEY
#   %Indirect           a global variable holding a variable reference -> nothing
#   Setting lcD         Tasker's own lock code, set -> SECRET-CREDENTIAL
#   Setting scrnOff     an ordinary preference -> nothing
_LEAKY_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Home</name>
    <pids>10,11</pids>
    <tids>20,21</tids>
  </Project>
  <Profile sr="prof10" ve="2">
    <id>10</id>
    <nme>Home</nme>
    <mid0>20</mid0>
    <Loc sr="con0">
      <cname>Home</cname>
      <lat>-3.1112782955169678</lat>
      <long>-60.006805419921875</long>
      <rad>30.0</rad>
    </Loc>
  </Profile>
  <Profile sr="prof11" ve="2">
    <id>11</id>
    <nme>Blank</nme>
    <mid0>21</mid0>
    <Loc sr="con0">
      <cname>Unset</cname>
      <lat>0.0</lat>
      <long>0.0</long>
      <rad>30.0</rad>
    </Loc>
  </Profile>
  <Task sr="task20">
    <id>20</id>
    <nme>Leaky</nme>
    <Action sr="act0" ve="7">
      <code>351</code>
      <Str sr="arg9" ve="3">simon</Str>
      <Str sr="arg10" ve="3">correct-horse-battery</Str>
    </Action>
    <Action sr="act1" ve="7">
      <code>351</code>
      <Str sr="arg9" ve="3">%MyUser</Str>
      <Str sr="arg10" ve="3">%MyPass</Str>
    </Action>
    <Action sr="act2" ve="7">
      <code>339</code>
      <Str sr="arg6" ve="3">Authorization: Bearer abcdefghij0123456789KLMNOP</Str>
    </Action>
    <Action sr="act3" ve="7">
      <code>130</code>
      <Str sr="arg0" ve="3">bob@example.com</Str>
    </Action>
    <Action sr="act4" ve="7">
      <code>1000</code>
      <Bundle sr="arg0">
        <Vals sr="val">
          <recipient>alice@example.org</recipient>
        </Vals>
      </Bundle>
    </Action>
  </Task>
  <Task sr="task21">
    <id>21</id>
    <nme>bob@example.com</nme>
    <Action sr="act0" ve="7"><code>548</code></Action>
  </Task>
  <Scene sr="scenePanel">
    <nme>Panel</nme>
    <TextElement sr="tel0">
      <geom sr="geom"><height>50</height></geom>
      <Str sr="arg0" ve="3">Call the office on +14155550123</Str>
    </TextElement>
  </Scene>
  <Variable sr="vars0">
    <n>%ApiKey</n>
    <v>sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789</v>
  </Variable>
  <Variable sr="vars1">
    <n>%Indirect</n>
    <v>%ApiKey</v>
  </Variable>
  <Setting sr="prefs0">
    <n>lcD</n>
    <t>s</t>
    <v>4815</v>
  </Setting>
  <Setting sr="prefs1">
    <n>scrnOff</n>
    <t>b</t>
    <v>true</v>
  </Setting>
</TaskerData>
"""


def _load(xml_text: str) -> ET.Element:
    """Build the PrimeItems lookup tables from XML text, the way taskerd does from a file.

    test_healthck._load, plus all_services: this module is the one that reads Tasker's own
    preferences, and a backup carries them.
    """
    root = ET.fromstring(xml_text)  # noqa: S314  (fixture text, defined in this file)
    PrimeItems.file_to_get = "fixture.xml"
    PrimeItems.xml_root = root
    PrimeItems.program_arguments = {"task_action_warning_limit": 100}
    PrimeItems.tasker_root_elements = {
        "all_projects": taskerd.move_xml_to_table(root.findall("Project"), False, "name"),
        "all_profiles": taskerd.move_xml_to_table(root.findall("Profile"), True, "nme"),
        "all_tasks": taskerd.move_xml_to_table(root.findall("Task"), True, "nme"),
        "all_scenes": taskerd.move_xml_to_table(root.findall("Scene"), False, "nme"),
        "all_services": root.findall("Setting"),
        "all_profiles_by_name": {},
        "all_tasks_by_name": {},
    }
    return root


@pytest.fixture
def loaded() -> ET.Element:
    """The leaky configuration, loaded."""
    return _load(_LEAKY_XML)


@pytest.fixture
def problems(loaded: ET.Element) -> list[piiscan.Problem]:
    """Everything the scan finds in it."""
    return piiscan.lint_problems()


def _where(problem: piiscan.Problem) -> str:
    """A finding's location as the report prints it."""
    return problem.where if isinstance(problem.where, str) else problem.where.label


def _tagged(problems: list[piiscan.Problem], tag: str) -> list[str]:
    """The locations of every finding carrying one tag."""
    return sorted(_where(problem) for problem in problems if problem.tag == tag)


# ##################################################################################
# The detector, one rule at a time.
# ##################################################################################
@pytest.mark.parametrize(
    ("value", "tag"),
    [
        ("AKIAIOSFODNN7EXAMPLE", "SECRET-API-KEY"),
        ("AIzaSyD0123456789abcdefghijklmnopqrstuv", "SECRET-API-KEY"),
        ("sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789", "SECRET-API-KEY"),
        ("sk_live_0123456789abcdefghij", "SECRET-API-KEY"),
        ("xoxb-0123456789-abcdefghijkl", "SECRET-TOKEN"),
        ("ghp_0123456789abcdefghijklmnopqrstuvwxyzAB", "SECRET-TOKEN"),
        ("123456789:AAHqwertyuiopasdfghjklzxcvbnm123456", "SECRET-TOKEN"),
        ("Authorization: Bearer abcdefghij0123456789KLMNOP", "SECRET-TOKEN"),
        ("api_key=0123456789abcdef", "SECRET-API-KEY"),
        ("password: correct-horse", "SECRET-PASSWORD"),
        ("https://simon:hunter2@example.com/feed", "SECRET-PASSWORD"),
        ("mail it to alice@example.org please", "PII-EMAIL"),
        ("+14155550123", "PII-PHONE"),
        ("(415) 555-0123", "PII-PHONE"),
        ("-3.1112782,-60.0068054", "PII-LOCATION"),
    ],
)
def test_each_rule_finds_its_own(value: str, tag: str) -> None:
    """Every rule fires on the thing it is for."""
    assert [finding.rule.tag for finding in piiscan.find_in_text(value)] == [tag]


@pytest.mark.parametrize(
    "value",
    [
        # A variable reference is the FIX, not the leak -- reporting one would be telling the
        # user off for having taken the secret out of the file already.
        "Authorization: Bearer %Token",
        "api_key=%MyKey",
        "password: %MyPass",
        # Tasker stamps a millisecond epoch date on everything.  None of them is a phone
        # number, and a rule that said so would fire on every object in every backup.
        "1699265143465",
        "cdate 1786121691586 mdate 1786121691999",
        # Two numbers that are not a place: out of range, and not precise enough.
        "99.5000,-200.12345",
        "2800.0,1752.0",
        # A version string is not an API key, and an ordinary sentence is not a password.
        "6.3.13",
        "the password is in the drawer",
    ],
)
def test_what_the_rules_decline(value: str) -> None:
    """The false positives that would make the report unreadable, asserted as absent."""
    assert piiscan.find_in_text(value) == []


def test_redaction_keeps_the_setting_and_drops_the_value() -> None:
    """A keyword rule replaces what the keyword introduced, not the keyword.

    'api_key=[REDACTED:API-KEY]' still reads as the setting it is; losing the name along
    with the value would make a redacted export harder to put back together than it needs
    to be.
    """
    redacted, found = piiscan.redact_in_text("GET /v1?api_key=0123456789abcdef&page=2")
    assert redacted == "GET /v1?api_key=[REDACTED:API-KEY]&page=2"
    assert len(found) == 1


def test_the_longest_match_wins() -> None:
    """A vendor key inside a generic assignment is reported once, as the vendor's.

    The rules overlap on purpose -- 'api_key=AIza...' matches both -- and counting it twice
    would double the size of a finding that is one problem.
    """
    found = piiscan.find_in_text("api_key=AIzaSyD0123456789abcdefghijklmnopqrstuv")
    assert [finding.rule.tag for finding in found] == ["SECRET-API-KEY"]
    assert found[0].text.startswith("AIza")


# ##################################################################################
# The scan over a whole configuration.
# ##################################################################################
def test_a_password_is_found_by_its_field_not_its_shape(problems: list[piiscan.Problem]) -> None:
    """'correct-horse-battery' is an ordinary string.  What gives it away is the box it is in.

    This is the finding no pattern can make, and the reason the module reads actionc.py's
    field names at all.
    """
    assert _tagged(problems, "SECRET-CREDENTIAL") == [
        "Project 'Home' > Task 'Leaky' (id 20) action 1",
        "Project 'Home' > Task 'Leaky' (id 20) action 1",
        "Tasker preferences in this backup",
    ]


def test_a_field_holding_a_variable_is_left_alone(problems: list[piiscan.Problem]) -> None:
    """The second HTTP Auth is filled in with variables, which is the user having done it right.

    Both of its fields, not just the password: a Username that reads %MyUser is no more a
    leak than the password beside it.
    """
    assert not [problem for problem in problems if "action 2" in _where(problem)]


def test_a_global_variables_value_is_read(problems: list[piiscan.Problem]) -> None:
    """The likeliest hiding place of all: the key was moved into a variable, and the backup
    stored what the variable held."""
    assert _tagged(problems, "SECRET-API-KEY") == ["Variable '%ApiKey'"]


def test_a_location_condition_is_a_place(problems: list[piiscan.Problem]) -> None:
    """A filled-in Loc is somebody's address; an empty one is a condition half-built."""
    assert _tagged(problems, "PII-LOCATION") == ["Project 'Home' > Profile 'Home' (id 10)"]


def test_a_scene_is_read_whole(problems: list[piiscan.Problem]) -> None:
    """A Scene's text is scanned, and a finding names the Scene rather than the button."""
    assert _tagged(problems, "PII-PHONE") == ["Scene 'Panel'"]


def test_a_name_is_never_a_finding(problems: list[piiscan.Problem]) -> None:
    """Task 21 is called bob@example.com, and so is the Perform Task that runs it.

    Neither is reported, because neither can be redacted: rewriting one half of that pair
    breaks the link and rewriting both changes what the user called their Task.  A finding
    the redactor will not act on is a promise the feature cannot keep.
    """
    assert _tagged(problems, "PII-EMAIL") == ["Project 'Home' > Task 'Leaky' (id 20) action 5"]


def test_nothing_loaded_reports_nothing() -> None:
    """Safe to call the moment the app starts, as every other check here is."""
    _load('<TaskerData sr="" dvi="1" tv="6.3.13"></TaskerData>')
    assert piiscan.lint_problems() == []


# ##################################################################################
# The redactor, and the promise it shares with the scan.
# ##################################################################################
def test_the_redactor_removes_what_the_scan_reports(loaded: ET.Element) -> None:
    """The property the whole module exists for.

    The Health Check is how a user decides whether an export needs redacting, so the two
    have to be describing the same file.  A tag on one side and not the other means one of
    them is lying.
    """
    reported = {problem.tag for problem in piiscan.lint_problems()}
    removed = set(piiscan.redact_tree(loaded).counts)
    assert reported == removed


def test_a_redacted_export_keeps_working(loaded: ET.Element) -> None:
    """Nothing that the file uses to refer to itself is rewritten.

    A redacted file that Tasker imports and then does nothing with is worse than no
    redaction at all -- the user has shared it believing it works.
    """
    before = [(element.tag, element.text) for element in loaded.iter() if element.tag in piiscan._REFERENCE_TAGS]  # noqa: SLF001
    piiscan.redact_tree(loaded)
    after = [(element.tag, element.text) for element in loaded.iter() if element.tag in piiscan._REFERENCE_TAGS]  # noqa: SLF001
    assert before == after

    # And the Perform Task that names one of those Tasks still names it.
    performed = [
        child.text
        for action in loaded.iter("Action")
        if action.findtext("code") == "130"
        for child in action
        if child.attrib.get("sr") == "arg0"
    ]
    assert performed == ["bob@example.com"]


def test_the_secrets_are_actually_gone(loaded: ET.Element) -> None:
    """The obvious assertion, made against the serialized file rather than the tree."""
    piiscan.redact_tree(loaded)
    written = ET.tostring(loaded, encoding="unicode")
    assert "sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789" not in written
    assert "correct-horse-battery" not in written
    assert "alice@example.org" not in written
    assert "+14155550123" not in written
    assert "4815" not in written
    assert "[REDACTED:" in written


def test_coordinates_are_zeroed_rather_than_worded(loaded: ET.Element) -> None:
    """Tasker reads a Loc's lat/long as numbers and would refuse a file with words in them.

    Zero rather than a rounded-off version of the real place: rounding still says which
    city.
    """
    piiscan.redact_tree(loaded)
    home = next(profile for profile in loaded.iter("Profile") if profile.findtext("nme") == "Home")
    condition = home.find("Loc")
    assert condition.findtext("lat") == "0.0"
    assert condition.findtext("long") == "0.0"
    # The radius and the condition's own label are not a place and are left as they were.
    assert condition.findtext("rad") == "30.0"


def test_an_untouched_export_is_untouched(loaded: ET.Element) -> None:
    """Redaction is opt-in, and the tests above must not be describing the default.

    Asserted through the renderer's own flag rather than by not calling redact_tree, because
    the default is the thing that could regress.
    """
    from maptasker.src import projedit  # noqa: PLC0415  - imported here to keep the GUI stack out of the rest

    plain = projedit.render_standalone_project_xml("Home")
    assert "[REDACTED:" not in plain
    # The Password in Task 'Leaky', which the export bundles.  Not the global variable's
    # key: a Project export carries the Project's Profiles, Tasks and Scenes, and Tasker's
    # own single-Project export carries neither the backup's global variables nor its
    # preferences -- so those are only ever redacted out of a full-backup save.
    assert "correct-horse-battery" in plain


def test_a_redacted_export_says_so(loaded: ET.Element) -> None:
    """The file carries its own explanation, above the root element.

    Whoever opens it next has no way of knowing it was edited, and an action reading
    [REDACTED:API-KEY] would otherwise look like a bug in the configuration.
    """
    from maptasker.src import projedit  # noqa: PLC0415

    exported = projedit.render_standalone_project_xml("Home", redact=True)
    assert exported.startswith("<!--")
    assert "MapTasker redacted export" in exported
    assert "[REDACTED:" in exported
    assert "correct-horse-battery" not in exported

    # Still a well-formed document, comment and all -- the whole point of a redacted export
    # is that it can be imported by whoever it was shared with.
    ET.fromstring(exported)  # noqa: S314


def test_the_notice_is_a_legal_comment() -> None:
    """'--' cannot appear inside an XML comment, and the notice quotes the tag names."""
    notice = piiscan.redact_rendered(ET.fromstring("<TaskerData />"))  # noqa: S314
    assert notice.startswith("<!--")
    assert notice.rstrip().endswith("-->")
    assert "--" not in notice[4:-4]
    assert re.fullmatch(r"<!--.*-->\n", notice, re.DOTALL)


# ##################################################################################
# Where a finding sends the reader
# ##################################################################################
#
# A finding is only worth as much as the place it names.  The TaskerNet description is the
# one property of an object that the Map draws as a block of its own, well below the
# object's own line -- so a finding about what somebody wrote in one has to say so, and
# point there, or the reader arrives at a line with nothing wrong on it and concludes the
# scan is imagining things.  People do leave addresses in these: "email me for the save
# files" is exactly the sort of thing a shared Task's description says.
_SHARED_XML = """<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2"><name>Home</name><tids>30</tids></Project>
  <Task sr="task30">
    <id>30</id>
    <nme>Downloaded</nme>
    <Share sr="Share">
      <d>a clever thing.  email someone@example.com for the save files</d>
      <g>AutoInput,Calendar</g>
    </Share>
    <Action sr="act0" ve="7"><code>548</code><Str sr="arg0" ve="3">hello</Str></Action>
  </Task>
</TaskerData>"""


@pytest.fixture
def shared_problems() -> list[piiscan.Problem]:
    """What the scan finds in a Task carrying a TaskerNet description."""
    _load(_SHARED_XML)
    return piiscan.lint_problems()


def test_an_address_in_a_taskernet_description_says_where_it_is(shared_problems: list) -> None:
    """"This object's own properties" is true of it and no use: it is the wording that made
    a real finding read as a false alarm.
    """
    finding = next(problem for problem in shared_problems if problem.tag == "PII-EMAIL")
    assert "the TaskerNet description" in finding.detail


def test_a_taskernet_finding_points_at_the_description_not_the_task(shared_problems: list) -> None:
    """And the click goes with the words: the description carries an anchor of its own
    (share.description_element_output), which is what this id has to match.
    """
    finding = next(problem for problem in shared_problems if problem.tag == "PII-EMAIL")
    assert finding.where.anchor == "mt-task-30-etaskernet"
    assert mapjump.needs_taskernet(finding.where)


def test_the_map_writes_the_anchor_that_finding_points_at(shared_problems: list) -> None:
    """The other half of the contract.  Held against each other here, in one test, because
    an id written by one side and not the other is a click that goes nowhere.
    """
    finding = next(problem for problem in shared_problems if problem.tag == "PII-EMAIL")
    PrimeItems.program_arguments = initialize_runtime_arguments()
    PrimeItems.program_arguments["taskernet"] = True
    PrimeItems.colors_to_use = set_color_mode("dark")
    PrimeItems.output_lines = LineOut()
    PrimeItems.emitted_anchors = set()

    share(PrimeItems.tasker_root_elements["all_tasks"]["30"]["xml"], "tasktab", Target(TASK, "30"))
    output = "".join(PrimeItems.output_lines.output_lines)

    assert f'<a id="{finding.where.anchor}" class="mt-anchor"' in output
    # And it marks the description, not something above it.
    assert "someone@example.com" in output[output.index(finding.where.anchor) :]


def test_the_other_share_tags_still_belong_to_the_object(shared_problems: list) -> None:
    """Only the description is drawn as a block of its own.  A finding anywhere else in
    the <Share> keeps naming the object, which is where the Map can show it.
    """
    _load(_SHARED_XML.replace("AutoInput,Calendar", "reach me at other@example.com"))
    findings = [problem for problem in piiscan.lint_problems() if problem.tag == "PII-EMAIL"]
    places = {problem.where.anchor for problem in findings}
    assert "mt-task-30" in places
    assert "mt-task-30-etaskernet" in places
