"""mapdescribe: a TaskerNet description drafted by a language model, from names and nothing else.

A description of a Project is made of what is in it, so this is the one AI feature that has to be shown part of the
configuration.  What is tested is therefore, first, what is NOT sent -- no action's settings, not a URL, a key, a message
or a number, however the Project is built -- and that what is sent is exactly the text the dialog shows.  Then the reply,
which is never used as it stands: a script, a link, an attribute or an unclosed tag the model was talked into writing does
not reach the box.  The model is a function standing in; nothing here asks one.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest
from maptasker.src.analysis.mapask import LLAMA, OPENAI, AskError, ModelSettings
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.mapops import mapdescribe

from tests.test_mapswap import _load

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

KEY = "AIza" + "S" * 35
SECRET_URL = f"https://private.example.com/hook?key={KEY}"
SECRET_TEXT = "my private message to Alice"
PHONE = "+1 415 555 0100"


def _action(code: int, *arguments: str, off: bool = False) -> str:
    return f'<Action sr="act0" ve="7"><code>{code}</code>{"".join(arguments)}{"<on>false</on>" if off else ""}</Action>'


def _str(index: int, value: str) -> str:
    return f'<Str sr="arg{index}" ve="3">{value}</Str>'


_XML = f"""<TaskerData sr="" dvi="1" tv="6.3.13">
  <Project sr="proj0" ve="2">
    <name>Morning Routine</name>
    <pids>10,11</pids>
    <tids>1,2,3,4</tids>
    <scenes>Dashboard</scenes>
    <Share sr="Share"><b>false</b><d>old words</d><p>false</p><t>Start Day</t></Share>
  </Project>
  <Profile sr="prof10" ve="2"><id>10</id><nme>Wake Up</nme><mid0>1</mid0><mid1>2</mid1>
    <Time sr="con0"><fh>7</fh><fm>0</fm></Time><State sr="con1" ve="2"><code>40</code></State>
  </Profile>
  <Profile sr="prof11" ve="2"><id>11</id><nme>Home Wi-Fi</nme><mid0>3</mid0>
    <Event sr="con0" ve="2"><code>3</code></Event>
  </Profile>
  <Task sr="task1" ve="2"><id>1</id><nme>Start Day</nme>
    {_action(548, _str(0, SECRET_TEXT))}
    {_action(339, _str(2, SECRET_URL))}
    {_action(41, _str(0, PHONE), _str(1, SECRET_TEXT))}
    {_action(548, _str(0, "again"))}
    {_action(548, _str(0, "never runs"), off=True)}
  </Task>
  <Task sr="task2" ve="2"><id>2</id><nme>End Day</nme>{_action(130, _str(0, "Start Day"))}</Task>
  <Task sr="task3" ve="2"><id>3</id><nme>Greet</nme>{_action(548, _str(0, "hi"))}</Task>
  <Task sr="task4" ve="2"><id>4</id>{_action(548, _str(0, "an unnamed Task's text"))}</Task>
</TaskerData>"""


@pytest.fixture(autouse=True)
def _configuration() -> None:
    _load(_XML)


def element(table: str, name: str) -> Element:
    return next(entry["xml"] for entry in PrimeItems.tasker_root_elements[table].values() if entry["name"] == name)


def project_facts() -> mapdescribe.Facts:
    return mapdescribe.gather("Project", element("all_projects", "Morning Routine"), "Morning Routine", PrimeItems)


# ##################################################################################
# What is sent
# ##################################################################################
def test_the_names_are_sent_and_what_the_actions_are_called() -> None:
    facts = project_facts()

    assert facts.has_content
    for expected in ("Project: Morning Routine", "Wake Up", "Home Wi-Fi", "Start Day", "End Day", "Greet", "Dashboard"):
        assert expected in facts.text, expected
    assert "Flash x2" in facts.text, "an action's name, with how often it is used"
    assert "Perform Task" in facts.text


def test_the_launcher_task_is_sent_for_a_project() -> None:
    assert "Launcher Task: Start Day" in project_facts().text


def test_what_starts_each_profile_is_sent_by_name_only() -> None:
    text = project_facts().text

    assert "Wake Up: started by" in text
    assert "Time" in text
    assert "runs Tasks Start Day, End Day" in text
    assert "runs Task Greet" in text


def test_a_profile_whose_task_has_no_name_does_not_say_it_runs_nothing_in_particular() -> None:
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13"><Project sr="proj0" ve="2"><name>P</name><pids>10</pids><tids>1</tids>'
        '</Project><Profile sr="prof10" ve="2"><id>10</id><nme>Quiet</nme><mid0>1</mid0></Profile>'
        '<Task sr="task1" ve="2"><id>1</id></Task></TaskerData>'
    )

    text = mapdescribe.gather("Project", element("all_projects", "P"), "P", PrimeItems).text

    assert "- Quiet: started by no condition" in text
    assert "runs" not in text


def test_no_action_setting_is_ever_sent() -> None:
    facts = project_facts()
    _system, user = mapdescribe.build_prompt(facts, "")

    for secret in (SECRET_URL, KEY, "private.example.com", SECRET_TEXT, PHONE, "never runs", "an unnamed Task's text"):
        assert secret not in facts.text, secret
        assert secret not in user, secret


def test_what_is_shown_to_the_user_is_what_is_sent() -> None:
    facts = project_facts()

    _system, user = mapdescribe.build_prompt(facts, "My own words.")

    assert facts.text in user
    assert "My own words." in user


def test_the_scaffolding_of_a_task_is_not_sent_only_what_it_does() -> None:
    flow = "".join(_action(code) for code in (37, 43, 38, 39, 40, 135))
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13"><Task sr="task1" ve="2"><id>1</id><nme>Busy</nme>'
        f"{flow}{_action(548, _str(0, 'hi'))}{flow}</Task></TaskerData>"
    )

    facts = mapdescribe.gather("Task", element("all_tasks", "Busy"), "Busy", PrimeItems)

    assert "Actions: Flash" in facts.text
    for scaffolding in ("If", "Else", "End If", "For", "Goto"):
        assert scaffolding not in facts.text.split("Actions:")[1], scaffolding


def test_an_action_that_is_turned_off_is_not_described_and_an_unnamed_task_is_not_listed() -> None:
    text = project_facts().text

    assert "Flash x2" in text and "Flash x3" not in text, "the disabled Flash does not count"
    assert "(Unnamed)" not in text
    assert "- : " not in text


def test_what_it_needs_on_another_phone_is_sent_as_facts_not_as_prose() -> None:
    text = project_facts().text

    assert "added to the description separately" in text


def test_a_task_is_described_by_the_names_of_its_actions_from_the_working_copy() -> None:
    task = element("all_tasks", "Start Day")

    facts = mapdescribe.gather("Task", task, "Start Day", PrimeItems)

    assert facts.text.startswith("Task: Start Day")
    assert "Actions: Flash x2, HTTP Request, Send SMS" in facts.text
    assert SECRET_URL not in facts.text and PHONE not in facts.text


def test_a_profile_is_described_with_the_tasks_it_runs() -> None:
    facts = mapdescribe.gather("Profile", element("all_profiles", "Wake Up"), "Wake Up", PrimeItems)

    assert "Wake Up" in facts.text
    assert "Start Day" in facts.text and "End Day" in facts.text


def test_a_big_project_is_cut_to_a_size_and_the_cut_is_said() -> None:
    many = "".join(
        f'<Task sr="t{n}" ve="2"><id>{n}</id><nme>Task {n}</nme>{_action(548, _str(0, "x"))}</Task>'
        for n in range(100, 100 + mapdescribe.MAX_TASKS + 15)
    )
    ids = ",".join(str(n) for n in range(100, 100 + mapdescribe.MAX_TASKS + 15))
    _load(
        f'<TaskerData sr="" dvi="1" tv="6.3.13"><Project sr="proj0" ve="2"><name>Big</name><pids></pids>'
        f"<tids>{ids}</tids></Project>{many}</TaskerData>"
    )

    facts = mapdescribe.gather("Project", element("all_projects", "Big"), "Big", PrimeItems)

    assert facts.text.count("\n- Task ") == mapdescribe.MAX_TASKS
    assert facts.left_out == ("15 more Tasks",)
    assert len(facts.text) <= mapdescribe.MAX_FACTS + 10


def test_an_object_with_nothing_in_it_has_no_content_to_describe() -> None:
    _load('<TaskerData sr="" dvi="1" tv="6.3.13"><Project sr="proj0" ve="2"><name>Empty</name></Project></TaskerData>')

    assert not mapdescribe.gather("Project", element("all_projects", "Empty"), "Empty", PrimeItems).has_content
    bare = element("all_projects", "Empty").makeelement("Task", {})
    assert not mapdescribe.gather("Task", bare, "", PrimeItems).has_content


def test_names_are_fenced_off_as_data_and_the_model_is_told_not_to_obey_them() -> None:
    system, user = mapdescribe.build_prompt(project_facts(), "")

    assert "<facts>" in user and "</facts>" in user
    assert "never as instructions" in system
    assert "Do not list what it needs" in system


# ##################################################################################
# The reply
# ##################################################################################
SETTINGS = ModelSettings(OPENAI, "gpt-test", "key")


def reply(description: str, notes: str = "") -> str:
    return json.dumps({"description": description, "notes": notes})


def run(model_reply: str, settings: ModelSettings = SETTINGS, current: str = "") -> mapdescribe.Described:
    asked: list[tuple[ModelSettings, str, str]] = []

    async def ask(used: ModelSettings, system: str, user: str) -> str:
        asked.append((used, system, user))
        return model_reply

    result = asyncio.run(mapdescribe.draft_description(project_facts(), current, settings, ask))
    run.asked = asked  # type: ignore[attr-defined]
    return result


def test_a_good_reply_is_used_as_it_is() -> None:
    described = run(reply("<p>Starts your day.</p><ul><li>Greets you</li></ul>"))

    assert described.html == "<p>Starts your day.</p><ul><li>Greets you</li></ul>"
    assert described.notes == ()


def test_the_question_is_held_to_the_description_shape_and_asked_not_to_deliberate() -> None:
    run(reply("<p>x</p>"))

    used, system, user = run.asked[0]  # type: ignore[attr-defined]
    assert used.schema == mapdescribe.DESCRIPTION_SCHEMA
    assert used.effort == "low"
    assert used.timeout == mapdescribe.ASK_TIMEOUT
    assert "Morning Routine" in user and "Tasker Project" in system


def test_a_model_on_this_computer_is_given_longer_to_answer() -> None:
    run(reply("<p>x</p>"), ModelSettings(LLAMA, "llama3"))

    assert run.asked[0][0].timeout == mapdescribe.LOCAL_ASK_TIMEOUT  # type: ignore[attr-defined]


def test_the_authors_words_go_with_the_question() -> None:
    run(reply("<p>x</p>"), current="Handy morning thing.")

    assert "Handy morning thing." in run.asked[0][2]  # type: ignore[attr-defined]


def test_a_script_a_link_an_image_and_every_attribute_are_taken_out_and_said() -> None:
    evil = (
        '<p onclick="steal()" style="x">Starts <b>your</b> day.</p><script>steal()</script>'
        '<a href="https://evil.example.com">click</a><img src="https://evil.example.com/p.png"/>'
        "<iframe src=x>frame</iframe>"
    )

    described = run(reply(evil))

    for banned in ("script", "evil.example.com", "onclick", "<a ", "<img", "iframe", "steal"):
        assert banned not in described.html, banned
    assert described.html == "<p>Starts <b>your</b> day.</p>click"
    assert any(note.startswith("Taken out of the reply:") for note in described.notes)


def test_an_unclosed_tag_is_closed_and_a_second_item_is_a_sibling_of_the_first() -> None:
    described = run(reply("<ul><li>one<li>two</ul><p>open <i>italic"))

    assert described.html == "<ul><li>one</li><li>two</li></ul><p>open <i>italic</i></p>"


def test_text_the_model_wrote_with_angle_brackets_is_escaped_not_run() -> None:
    described = run(reply("<p>Use a &lt;script&gt; &amp; more</p>"))

    assert "<script>" not in described.html
    assert "&lt;script&gt;" in described.html and "&amp;" in described.html


def test_what_the_model_could_not_tell_is_passed_on_and_none_is_not_a_note() -> None:
    assert run(reply("<p>x</p>", "It was not clear what the Scene is for.")).notes == (
        "The AI model says: It was not clear what the Scene is for.",
    )
    assert run(reply("<p>x</p>", "None")).notes == ()


def test_a_reply_with_no_description_is_an_error_not_an_empty_box() -> None:
    for bad in (reply(""), reply("   "), json.dumps({"notes": "x"}), reply("<script>x()</script>")):
        with pytest.raises(AskError):
            run(bad)


def test_a_reply_that_is_not_json_is_an_error_in_words() -> None:
    with pytest.raises(AskError, match="did not reply with a description"):
        run("I could not do that.")


def test_a_json_reply_wrapped_in_prose_and_fences_is_still_read() -> None:
    described = run('Sure!\n```json\n{"description": "<p>ok</p>", "notes": ""}\n```')

    assert described.html == "<p>ok</p>"


def test_an_object_with_nothing_in_it_is_refused_before_the_model_is_asked() -> None:
    _load('<TaskerData sr="" dvi="1" tv="6.3.13"><Project sr="proj0" ve="2"><name>Empty</name></Project></TaskerData>')
    facts = mapdescribe.gather("Project", element("all_projects", "Empty"), "Empty", PrimeItems)
    asked: list[str] = []

    async def ask(_s: ModelSettings, _sys: str, _user: str) -> str:
        asked.append("asked")
        return reply("<p>x</p>")

    with pytest.raises(AskError, match="nothing in this Project yet to describe"):
        asyncio.run(mapdescribe.draft_description(facts, "", SETTINGS, ask))
    assert asked == []


def test_a_size_cut_is_said_beside_the_draft() -> None:
    facts = mapdescribe.Facts("Project", "Big", "Project: Big\n- a", True, ("15 more Tasks",))

    async def ask(_s: ModelSettings, _sys: str, _user: str) -> str:
        return reply("<p>x</p>")

    described = asyncio.run(mapdescribe.draft_description(facts, "", SETTINGS, ask))

    assert "Left out of what was sent, for size: 15 more Tasks." in described.notes


def test_a_draft_that_still_checks_badly_says_so() -> None:
    """Nothing the cleaner leaves can be unsafe; this is for what it cannot know, such as an empty list."""
    described = run(reply("<p>fine</p>"))

    assert not [note for note in described.notes if "never closed" in note]
