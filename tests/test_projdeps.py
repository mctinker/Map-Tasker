"""The Project dependency graph (projdeps): which Projects use Tasks, Scenes and globals that live in other Projects.

The fixture is four Projects with every shape the rules care about:

  Home        uses Utilities three ways (a Perform Task, a Profile's Entry Task, a Scene button's Task), a Scene in
              Media, a Task name that Utilities AND Media both have, and the global %Alarm; and performs a Task of
              its own that shares a name with nothing, which must not look like a use of anything.
  Utilities   provides those, and in turn uses Media: a loop.
  Media       shows the Scene, and uses Utilities back.
  Lonely      touches nothing outside itself.

What is checked is mostly what is NOT drawn: a call that stays inside a Project, a name that two Projects both have,
a variable the reader sets itself, and an object that no Project owns.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from maptasker.src.core.mapjump import SCENE, TASK, VARIABLE, text_report
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.edit import sessundo
from maptasker.src.mapops import projdeps

from tests.test_maprefac import _load

SET = "547"
FLASH = "548"
PERFORM_TASK = "130"
SHOW_SCENE = "47"


def _action(code: str, *args: str) -> str:
    strings = "".join(f'<Str sr="arg{number}" ve="3">{text}</Str>' for number, text in enumerate(args))
    return f'<Action sr="act0" ve="7"><code>{code}</code>{strings}</Action>'


def _task(task_id: str, name: str, *actions: str) -> str:
    numbered = "".join(action.replace("act0", f"act{number}") for number, action in enumerate(actions))
    return f'<Task sr="task{task_id}" ve="2"><id>{task_id}</id><nme>{name}</nme>{numbered}</Task>'


def _perform(name: str) -> str:
    return _action(PERFORM_TASK, name)


def _project(name: str, pids: str, tids: str, scenes: str = "") -> str:
    safe = "".join(character for character in name if character.isalnum())
    return (
        f'<Project sr="proj{safe}" ve="2"><name>{name}</name><pids>{pids}</pids><tids>{tids}</tids>'
        f"<scenes>{scenes}</scenes></Project>"
    )


# Task ids
#   10 Morning (Home)   performs 'Setup' (Utilities), 'Local' (Home's own) and shows Scene 'Panel' (Media)
#   11 Evening (Home)   performs 'Shared' (Utilities AND Media), flashes %Alarm; sets and reads its own %Mine
#   12 Local (Home)
#   20 Setup (Utilities), 21 Boot (Utilities)  run by Home's Profile, 22 Chime (Utilities)  run by Scene 'Panel'
#   23 Shared (Utilities)   24 Report (Utilities)  performs 'Show' (Media), 25 Alarmer (Utilities)  sets %Alarm
#   30 Show (Media)         performs 'Setup' (Utilities),  31 Shared (Media)
#   40 Solo (Lonely)        performs 'Solo Helper' (Lonely)   41 Solo Helper (Lonely)
#   99 Orphan               in no Project at all, and performs 'Setup'
_XML = (
    '<TaskerData sr="" dvi="1" tv="6.3.13">'
    + _project("Home", "100", "10,11,12")
    + _project("Utilities", "", "20,21,22,23,24,25")
    + _project("Media", "", "30,31", "Panel")
    + _project("Lonely", "", "40,41")
    + '<Profile sr="prof100" ve="2"><id>100</id><nme>Boot Profile</nme><mid0>21</mid0></Profile>'
    + _task("10", "Morning", _perform("Setup"), _perform("Local"), _action(SHOW_SCENE, "Panel"))
    + _task(
        "11",
        "Evening",
        _perform("Shared"),
        _action(FLASH, "alarm is %Alarm"),
        _action(SET, "%Mine", "1"),
        _action(FLASH, "mine is %Mine"),
    )
    + _task("12", "Local", _action(FLASH, "local"))
    + _task("20", "Setup", _action(FLASH, "setup"))
    + _task("21", "Boot", _action(FLASH, "boot"))
    + _task("22", "Chime", _action(FLASH, "chime"))
    + _task("23", "Shared", _action(FLASH, "shared by utilities"))
    + _task("24", "Report", _perform("Show"))
    + _task("25", "Alarmer", _action(SET, "%Alarm", "7"))
    + _task("30", "Show", _perform("Setup"))
    + _task("31", "Shared", _action(FLASH, "shared by media"))
    + _task("40", "Solo", _perform("Solo Helper"))
    + _task("41", "Solo Helper", _action(FLASH, "helper"))
    + _task("99", "Orphan", _perform("Setup"))
    + '<Scene sr="scenePanel"><nme>Panel</nme><RectElement sr="elements0"><clickTask>22</clickTask></RectElement></Scene>'
    + "</TaskerData>"
)


@pytest.fixture
def graph() -> Iterator[projdeps.ProjectGraph]:
    """The fixture configuration and the graph read from it."""
    sessundo.clear(PrimeItems)
    _load(_XML)
    yield projdeps.build_graph(PrimeItems)
    sessundo.clear(PrimeItems)


def _used(graph: projdeps.ProjectGraph, user: str, provider: str) -> set[tuple[str, str]]:
    """What `user` takes from `provider`, as (kind, name) pairs."""
    edge = graph.edges.get((user, provider))
    return {(link.kind, link.used) for link in edge.links} if edge else set()


def test_a_project_is_joined_to_each_project_it_takes_something_from(graph: projdeps.ProjectGraph) -> None:
    assert _used(graph, "Home", "Utilities") >= {(TASK, "Setup"), (TASK, "Boot"), (VARIABLE, "%Alarm")}
    assert _used(graph, "Home", "Media") >= {(SCENE, "Panel")}


def test_a_profiles_task_and_a_scene_buttons_task_count_as_uses(graph: projdeps.ProjectGraph) -> None:
    home = {link.used: link.verb for link in graph.edges[("Home", "Utilities")].links}
    media = {link.used: link.verb for link in graph.edges[("Media", "Utilities")].links}

    assert home["Boot"] == "runs"  # Home's Profile
    assert media["Chime"] == "runs"  # Media's Scene 'Panel', one of whose buttons runs it


def test_a_scene_buttons_task_is_a_use_by_the_scene_s_own_project(graph: projdeps.ProjectGraph) -> None:
    """Scene 'Panel' is Media's, so it is Media that needs Chime from Utilities -- not Home, which merely shows it."""
    assert (TASK, "Chime") in _used(graph, "Media", "Utilities")


def test_a_call_that_stays_inside_a_project_is_not_a_line(graph: projdeps.ProjectGraph) -> None:
    assert not [key for key in graph.edges if key[0] == key[1]]
    assert ("Home", "Home") not in graph.edges
    assert graph.uses("Lonely") == []


def test_a_name_two_projects_have_is_a_use_of_both_and_the_sole_provider_of_neither(
    graph: projdeps.ProjectGraph,
) -> None:
    to_utilities = [link for link in graph.edges[("Home", "Utilities")].links if link.used == "Shared"]
    to_media = [link for link in graph.edges[("Home", "Media")].links if link.used == "Shared"]

    assert len(to_utilities) == 1
    assert len(to_media) == 1
    assert not to_utilities[0].sole
    assert not to_media[0].sole


def test_a_task_name_the_project_has_itself_is_not_a_use_of_the_other_project(graph: projdeps.ProjectGraph) -> None:
    """Media and Utilities both have 'Shared'; Media performing it stays inside Media."""
    assert ("Media", "Utilities") not in graph.edges or "Shared" not in {
        link.used for link in graph.edges[("Media", "Utilities")].links
    }


def test_a_global_is_a_use_of_the_project_that_sets_it(graph: projdeps.ProjectGraph) -> None:
    (link,) = [link for link in graph.edges[("Home", "Utilities")].links if link.kind == VARIABLE]

    assert link.used == "%Alarm"
    assert link.verb == "reads"
    assert link.sole, "Utilities is the only Project that sets it"
    assert link.user.kind == TASK


def test_a_global_the_reader_sets_itself_is_not_a_use(graph: projdeps.ProjectGraph) -> None:
    named = {link.used for edge in graph.edges.values() for link in edge.links}

    assert "%Mine" not in named


def test_an_object_in_no_project_makes_no_line(graph: projdeps.ProjectGraph) -> None:
    assert not [link for edge in graph.edges.values() for link in edge.links if link.user.key == "99"]


def test_projects_that_need_each_other_are_a_loop(graph: projdeps.ProjectGraph) -> None:
    assert graph.loops == [["Media", "Utilities"]]
    assert graph.standing("Media") == projdeps.IN_A_LOOP
    assert graph.standing("Utilities") == projdeps.IN_A_LOOP
    assert graph.standing("Home") == projdeps.NEEDS_OTHERS
    assert graph.standing("Lonely") == projdeps.SELF_CONTAINED


def test_what_a_project_needs_is_everything_it_reaches(graph: projdeps.ProjectGraph) -> None:
    assert graph.needs("Home") == ["Media", "Utilities"]
    assert graph.needs("Lonely") == []
    assert graph.needed_by("Utilities") == ["Home", "Media"]


def test_deleting_a_project_breaks_only_what_nothing_else_provides(graph: projdeps.ProjectGraph) -> None:
    broken = {(link.user_project, link.used) for link in graph.would_break("Utilities")}

    assert ("Home", "Setup") in broken
    assert ("Home", "%Alarm") in broken
    assert ("Home", "Shared") not in broken, "Media has a 'Shared' too"
    assert all(link.sole for link in graph.would_break("Utilities"))


def test_nothing_is_broken_by_deleting_a_project_nobody_uses(graph: projdeps.ProjectGraph) -> None:
    assert graph.would_break("Home") == []
    assert graph.used_by("Home") == []


def test_a_line_summarises_what_crosses_it(graph: projdeps.ProjectGraph) -> None:
    assert graph.edges[("Home", "Media")].summary == "1 Task, 1 Scene"


def test_every_use_points_at_the_place_that_makes_it(graph: projdeps.ProjectGraph) -> None:
    link = next(link for link in graph.edges[("Home", "Utilities")].links if link.used == "Setup")

    assert link.user.kind == TASK
    assert link.user.key == "10"
    assert link.user.action == 1
    assert link.used_at is not None
    assert link.used_at.key == "20"


def test_the_report_has_a_line_for_every_project_and_a_section_for_each_that_crosses(
    graph: projdeps.ProjectGraph,
) -> None:
    text = text_report(projdeps.report_rows(graph))

    assert "4 Projects" in text
    for name in ("Home", "Utilities", "Media", "Lonely"):
        assert f"  {name}:" in text
    assert "Project 'Home'" in text
    assert "Project 'Lonely'" not in text, "nothing crosses, so there is nothing to detail"


def test_a_project_leaned_on_through_another_says_who_else_is_affected() -> None:
    sessundo.clear(PrimeItems)
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        + _project("Top", "", "1")
        + _project("Middle", "", "2")
        + _project("Bottom", "", "3")
        + _task("1", "Start", _perform("Relay"))
        + _task("2", "Relay", _perform("Base"))
        + _task("3", "Base", _action(FLASH, "x"))
        + "</TaskerData>",
    )
    text = text_report(projdeps.project_rows(projdeps.build_graph(PrimeItems), "Bottom"))

    assert "Used by 1 other Project" in text
    assert "also leaned on by: Top." in text

    top = text_report(projdeps.project_rows(projdeps.build_graph(PrimeItems), "Top"))
    assert "you would need: Middle, Bottom (through Middle)." in top


def test_a_project_nothing_crosses_says_so(graph: projdeps.ProjectGraph) -> None:
    assert "Nothing crosses" in text_report(projdeps.project_rows(graph, "Lonely"))


def test_a_project_that_needs_nothing_says_it_can_be_split_out() -> None:
    sessundo.clear(PrimeItems)
    _load(_XML)
    text = text_report(projdeps.project_rows(projdeps.build_graph(PrimeItems), "Home"))

    assert "Needs 2 other Projects" in text
    assert "To use it on its own you would need: Utilities, Media." in text


def test_the_provider_s_section_says_what_deleting_it_would_leave_dangling(graph: projdeps.ProjectGraph) -> None:
    text = text_report(projdeps.project_rows(graph, "Utilities"))

    assert "Used by 2 other Projects" in text
    assert "would be left with nothing" in text
    assert "performs Task 'Setup'" in text


def test_a_project_used_but_replaceable_says_deleting_it_is_safe() -> None:
    """Media's only use by Home is a name Utilities also has, and the Scene -- delete a Project nobody leans on alone."""
    sessundo.clear(PrimeItems)
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        + _project("A", "", "1")
        + _project("B", "", "2")
        + _project("C", "", "3")
        + _task("1", "Caller", _perform("Dup"))
        + _task("2", "Dup", _action(FLASH, "b"))
        + _task("3", "Dup", _action(FLASH, "c"))
        + "</TaskerData>",
    )
    graph = projdeps.build_graph(PrimeItems)

    assert "Deleting this Project would leave nothing dangling" in text_report(projdeps.project_rows(graph, "B"))


def test_the_graph_is_drawn_as_arrows_labelled_with_what_crosses_and_loops_are_outlined(
    graph: projdeps.ProjectGraph,
) -> None:
    drawing, nodes = projdeps.mermaid(graph)

    assert drawing.startswith("flowchart LR")
    assert '-->|"' in drawing
    assert "Lonely" not in drawing, "a Project with no line to or from it is not drawn"
    assert "stroke:#e53935" in drawing, "the loop is outlined"
    assert sorted(nodes.values()) == ["Home", "Media", "Utilities"], "each node says which Project it is"


def test_a_name_with_a_quote_in_it_cannot_break_the_drawing() -> None:
    sessundo.clear(PrimeItems)
    _load(
        '<TaskerData sr="" dvi="1" tv="6.3.13">'
        + _project("Say &quot;hi&quot; &lt;b&gt;", "", "1")
        + _project("B", "", "2")
        + _task("1", "Caller", _perform("Callee"))
        + _task("2", "Callee", _action(FLASH, "x"))
        + "</TaskerData>",
    )

    drawing, _nodes = projdeps.mermaid(projdeps.build_graph(PrimeItems))

    assert '"hi"' not in drawing
    assert "#quot;hi#quot;" in drawing
    assert "<b>" not in drawing


def test_an_empty_configuration_has_an_empty_graph() -> None:
    sessundo.clear(PrimeItems)
    _load('<TaskerData sr="" dvi="1" tv="6.3.13"></TaskerData>')

    graph = projdeps.build_graph(PrimeItems)

    assert graph.projects == []
    assert graph.edges == {}
    assert graph.loops == []
