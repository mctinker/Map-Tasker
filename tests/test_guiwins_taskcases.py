"""The Task Tests dialog, the Save As Test dialog, and the Task Stepper's part in them.

What a test pins and how it is compared is test_taskcases'.  What is tested here is what is on screen and what the
buttons do: that every saved test is run when the dialog opens, that a failure says in words what moved, that the new
result can be kept and a test deleted, that the Stepper's run can be saved with only what was ticked, and that a run
which could not be decided is not offered.  Each dialog is the real one, on a page of NiceGUI's simulated user.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

import pytest
from maptasker.src.analysis import taskcases, taskstep
from maptasker.src.core.primitem import PrimeItems
from maptasker.src.gui import guiwins_taskcases, guiwins_taskstep
from nicegui import ui

from tests.nicegui_harness import button, click, found, inputs, label_texts, open_page, press
from tests.shared_fixtures import _load_local
from tests.test_taskstep import _xml, else_, end_if, flash, if_, set_

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from nicegui.testing.user import User

pytestmark = pytest.mark.usefixtures("_runtime")

_CHECKER = (
    if_("%n", 7, "3"),
    set_("%r", "big"),
    flash("big %n"),
    else_(),
    set_("%r", "small"),
    end_if(),
)


def _load(tmp_path: Path, *actions: str) -> None:
    _load_local(tmp_path, _xml(Checker=actions or _CHECKER, Other=(flash("hello"),)))


def _case(name: str = "big", n: str = "5", *, pins: taskcases.Pins | None = None) -> taskcases.Case:
    """A case made from the Checker as it is loaded now, run with %n = n."""
    setup = taskcases.Setup(variables={"n": n})
    trace = taskstep.step_task("Checker", PrimeItems, setup.options(PrimeItems))
    assert trace is not None
    return taskcases.capture(name, "Checker", setup, trace, pins)


def _keep(*cases: taskcases.Case, after_edit: bool = True) -> None:
    """Write these cases to the file the dialogs read, in the current directory."""
    assert taskcases.save_book(taskcases.CaseBook(cases=list(cases), after_edit=after_edit)) == ""


def _saved() -> taskcases.CaseBook:
    return taskcases.load_book()[0]


def _break_the_checker() -> None:
    """Edit Checker so 'big' no longer comes out big: the condition now wants a number over 9."""
    element = PrimeItems.tasker_root_elements["all_tasks_by_name"]["Checker"]["xml"]
    for node in element.iter("Condition"):
        node.find("rhs").text = "9"  # type: ignore[union-attr]


_refresh: list[Callable[[], None]] = []


def _tests_page(opened: list[taskcases.Case] | None = None) -> Callable[[], None]:
    def page() -> None:
        def jump(_target: object) -> Callable:
            return lambda *_args: None

        dialog, refresh = guiwins_taskcases.build_taskcases_dialog(
            cast("Callable", jump), (opened.append if opened is not None else lambda _case: None), PrimeItems
        )
        _refresh[:] = [refresh]
        dialog.open()

    return page


# ##################################################################################
# Opening it
# ##################################################################################
@pytest.mark.asyncio
async def test_with_no_tests_it_says_how_to_make_one(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_tests_page()) as user:
        texts = label_texts(user)

        assert "There are no tests yet." in texts
        assert "Step a Task in the Task Stepper and press 'Save As Test'." in texts


@pytest.mark.asyncio
async def test_every_saved_test_is_run_when_it_opens(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("good"), _case("also good", n="9"))

    async with open_page(_tests_page()) as user:
        texts = label_texts(user)

        assert "2 tests: 2 passed, 0 failed, 0 not in this file" in texts
        assert texts.count("PASSED") == 2
        assert "good" in texts and "also good" in texts
        assert [link.text for link in found(user, ui.link)] == ["Task 'Checker'", "Task 'Checker'"]


@pytest.mark.asyncio
async def test_a_test_that_no_longer_passes_says_what_moved(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        texts = label_texts(user)

        assert "1 test: 0 passed, 1 failed, 0 not in this file" in texts
        assert "FAILED" in texts
        assert "%r is 'small', where it was expected to be 'big'." in texts
        assert any(line.startswith("What it does no longer happens: 'Flash: ") for line in texts)


@pytest.mark.asyncio
async def test_a_test_for_a_task_that_is_not_here_is_counted_apart(tmp_path: Path) -> None:
    _load(tmp_path)
    elsewhere = taskcases.Case(name="elsewhere", task="Nowhere")
    _keep(_case("here"), elsewhere)

    async with open_page(_tests_page()) as user:
        texts = label_texts(user)

        assert "2 tests: 1 passed, 0 failed, 1 not in this file" in texts
        assert "NOT HERE" in texts


@pytest.mark.asyncio
async def test_entries_that_could_not_be_read_are_said(tmp_path: Path) -> None:
    _load(tmp_path)
    (tmp_path / "MapTasker_TaskTests.json").write_text('{"cases": [{"name": "ok", "task": "Checker"}, "junk"]}')

    async with open_page(_tests_page()) as user:
        assert any("entries in the saved tests could not be read" in text for text in label_texts(user))


# ##################################################################################
# What the buttons do
# ##################################################################################
def _hover_text(element: ui.element) -> str:
    """The text of the tooltip attached to this element, or "" when it has none."""
    return " ".join(child.text for child in element.default_slot.children if isinstance(child, ui.tooltip))


@pytest.mark.asyncio
async def test_run_all_and_run_say_what_they_do_when_hovered(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))

    async with open_page(_tests_page()) as user:
        run_all = _hover_text(button(user, "Run All"))
        run_one = _hover_text(button(user, "Run"))

    assert "every saved test" in run_all and "Nothing is run on your phone" in run_all
    assert "just this test" in run_one and "without running the others" in run_one


# ##################################################################################
# A run says so, even when it comes out as it did before
# ##################################################################################
@pytest.mark.asyncio
async def test_run_all_says_what_it_ran_even_when_nothing_changed(tmp_path: Path) -> None:
    """The complaint: pressing Run All changed nothing on screen, so it looked as if nothing had happened."""
    _load(tmp_path)
    _keep(_case("one"), _case("two"))

    async with open_page(_tests_page()) as user:
        before = label_texts(user)

        await click(user, "Run All")

        assert "Ran 2 tests: 2 passed, 0 failed, 0 not in this file." in user.notify.messages
        assert [text for text in label_texts(user) if text.startswith("Ran at ")] == ["Ran at " + _stamp(user)] * 2
        assert any(text.startswith("Last run ") for text in label_texts(user))
        assert [t for t in before if t == "PASSED"] == ["PASSED", "PASSED"]


def _stamp(user: User) -> str:
    """The time of day the dialog says its last run was."""
    (last,) = [text for text in label_texts(user) if text.startswith("Last run ")]
    return last.removeprefix("Last run ")


@pytest.mark.asyncio
async def test_run_says_how_that_test_came_out(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("steady"))

    async with open_page(_tests_page()) as user:
        await click(user, "Run")

        assert "'steady' passed." in user.notify.messages


@pytest.mark.asyncio
async def test_run_on_a_test_that_fails_says_what_is_different(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        await click(user, "Run")

        assert "'big' does not pass: %r is 'small', where it was expected to be 'big'." in user.notify.messages


@pytest.mark.asyncio
async def test_run_on_a_test_whose_task_is_not_here_says_so(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(taskcases.Case(name="elsewhere", task="Nowhere"))

    async with open_page(_tests_page()) as user:
        await click(user, "Run")

        assert "'elsewhere': Task 'Nowhere' is not in the file that is open." in user.notify.messages


@pytest.mark.asyncio
async def test_a_single_run_stamps_only_that_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _load(tmp_path)
    _keep(_case("one"), _case("two"))
    moments = iter(datetime(2026, 10, 27, 10, 0, second) for second in range(0, 60, 5))
    monkeypatch.setattr(guiwins_taskcases.clock, "now", lambda: next(moments))

    async with open_page(_tests_page()) as user:
        assert sorted(text for text in label_texts(user) if text.startswith("Ran at ")) == ["Ran at 10:00:00"] * 2
        first = sorted((b for b in found(user, ui.button) if b.text == "Run"), key=lambda b: b.id)[0]

        await press(user, first)

        assert sorted(text for text in label_texts(user) if text.startswith("Ran at ")) == [
            "Ran at 10:00:00",
            "Ran at 10:00:05",
        ]
        assert "Last run 10:00:05" in label_texts(user)


@pytest.mark.asyncio
@pytest.mark.parametrize(("failing", "said"), [(False, "'big' passed."), (True, "Kept the new result of 'big'.")])
async def test_a_row_button_speaks_before_the_list_is_redrawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: bool, said: str
) -> None:
    """Redrawing the list deletes the button that was pressed; a toast made from a deleted button's handler raises.

    This is what made Run and Keep New Result look dead in the real window, where a handler's context is its
    button's -- the simulated page is more forgiving -- so what is pinned is the order: what is to be said has
    been said by the time the list is drawn again.
    """
    _load(tmp_path)
    _keep(_case("big"))
    if failing:
        _break_the_checker()
    draws: list[list[str]] = []
    draw = guiwins_taskcases._Tests.draw

    async with open_page(_tests_page()) as user:

        def spy(tests: guiwins_taskcases._Tests) -> None:
            draws.append(list(user.notify.messages))
            draw(tests)

        pressed = button(user, "Keep New Result" if failing else "Run")
        monkeypatch.setattr(guiwins_taskcases._Tests, "draw", spy)

        await press(user, pressed)

    assert draws, "the list was not drawn again"
    assert said in draws[-1], f"{said!r} was not said until after the list was redrawn: {draws[-1]}"


@pytest.mark.asyncio
async def test_the_open_dialog_is_brought_up_to_date_when_asked(tmp_path: Path) -> None:
    """After an edit made while it is open: the window calls the second thing build_taskcases_dialog returned."""
    _load(tmp_path)
    _keep(_case("big"))

    async with open_page(_tests_page()) as user:
        assert "PASSED" in label_texts(user)

        _break_the_checker()
        _refresh[0]()

        assert "FAILED" in label_texts(user)
        assert "PASSED" not in label_texts(user)


@pytest.mark.asyncio
async def test_keep_new_result_says_it_kept_it(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        await click(user, "Keep New Result")

        assert "Kept the new result of 'big'." in user.notify.messages


@pytest.mark.asyncio
async def test_run_all_runs_them_again_after_the_task_was_put_right(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        assert "FAILED" in label_texts(user)
        _load(tmp_path)  # put back as it was

        await click(user, "Run All")

        assert "PASSED" in label_texts(user)
        assert "FAILED" not in label_texts(user)


@pytest.mark.asyncio
async def test_run_runs_that_one(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        _load(tmp_path)

        await click(user, "Run")

        assert "PASSED" in label_texts(user)


@pytest.mark.asyncio
async def test_keep_new_result_saves_the_run_as_it_is_now(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        await click(user, "Keep New Result")

        assert "PASSED" in label_texts(user)
        assert "FAILED" not in label_texts(user)
        assert not [b for b in found(user, ui.button) if b.text == "Keep New Result"]
    assert _saved().get("big").expected.variables == {"r": "small"}  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_keep_new_result_keeps_the_note_and_what_was_pinned(tmp_path: Path) -> None:
    _load(tmp_path)
    case = _case("big", pins=taskcases.Pins(effects=False))
    case.note = "the happy path"
    _keep(case)
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        await click(user, "Keep New Result")

    kept = _saved().get("big")
    assert kept is not None
    assert kept.note == "the happy path"
    assert kept.expected.effects is None, "it did not pin what it does before, so it does not now"


@pytest.mark.asyncio
async def test_keep_new_result_is_only_offered_for_a_failure(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"))

    async with open_page(_tests_page()) as user:
        assert not [b for b in found(user, ui.button) if b.text == "Keep New Result"]


@pytest.mark.asyncio
async def test_delete_drops_the_test_from_the_list_and_the_file(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("one"), _case("two"))

    async with open_page(_tests_page()) as user:
        # In the order they were drawn, which is the order of the rows: the page does not return them in one.
        delete = sorted((b for b in found(user, ui.button) if b.props.get("icon") == "delete"), key=lambda b: b.id)
        assert len(delete) == 2

        await press(user, delete[0])

        assert "one" not in label_texts(user)
        assert "two" in label_texts(user)
    assert [case.name for case in _saved().cases] == ["two"]


# ##################################################################################
# Delete All
# ##################################################################################
@pytest.mark.asyncio
async def test_delete_all_is_greyed_out_when_there_is_nothing_to_delete(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_tests_page()) as user:
        assert not button(user, "Delete All").enabled


@pytest.mark.asyncio
async def test_delete_all_says_what_it_does_when_hovered(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("one"))

    async with open_page(_tests_page()) as user:
        hover = _hover_text(button(user, "Delete All"))

    assert "every test listed here" in hover and "cannot be undone" in hover
    assert "The Tasks themselves are not touched" in hover


@pytest.mark.asyncio
async def test_delete_all_asks_first_and_deletes_nothing_until_told_to(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("one"), _case("two"))

    async with open_page(_tests_page()) as user:
        assert button(user, "Delete All").enabled

        await press(user, button(user, "Delete All"))

        assert "Delete all 2 tests?  This cannot be undone." in label_texts(user)
        assert {b.text for b in found(user, ui.button) if b.text in ("Delete", "Cancel")} == {"Delete", "Cancel"}
    assert [case.name for case in _saved().cases] == ["one", "two"]


@pytest.mark.asyncio
async def test_cancelling_delete_all_keeps_every_test(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("one"), _case("two"))

    async with open_page(_tests_page()) as user:
        await press(user, button(user, "Delete All"))

        await click(user, "Cancel")

        assert "one" in label_texts(user) and "two" in label_texts(user)
        assert button(user, "Delete All").enabled
    assert [case.name for case in _saved().cases] == ["one", "two"]


@pytest.mark.asyncio
async def test_confirming_delete_all_removes_every_test_listed_and_says_so(tmp_path: Path) -> None:
    _load(tmp_path)
    elsewhere = taskcases.Case(name="elsewhere", task="Nowhere")
    _keep(_case("one"), _case("two"), elsewhere, after_edit=False)

    async with open_page(_tests_page()) as user:
        assert "3 tests: 2 passed, 0 failed, 1 not in this file" in label_texts(user)
        await press(user, button(user, "Delete All"))

        await click(user, "Delete")

        assert "Deleted 3 tests." in user.notify.messages
        texts = label_texts(user)
        assert "There are no tests yet." in texts
        assert not any(text in texts for text in ("one", "two", "elsewhere"))
        assert not [text for text in texts if text.startswith(("Last run", "Ran at"))]
        assert not button(user, "Delete All").enabled
    book = _saved()
    assert book.cases == []
    assert book.after_edit is False, "only the tests are deleted, not the setting"


@pytest.mark.asyncio
async def test_delete_all_of_one_test_says_test_not_tests(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("only"))

    async with open_page(_tests_page()) as user:
        await press(user, button(user, "Delete All"))
        assert "Delete all 1 test?  This cannot be undone." in label_texts(user)

        await click(user, "Delete")

        assert "Deleted 1 test." in user.notify.messages


@pytest.mark.asyncio
async def test_step_opens_that_test_in_the_stepper(tmp_path: Path) -> None:
    _load(tmp_path)
    case = _case("big")
    _keep(case)
    opened: list[taskcases.Case] = []

    async with open_page(_tests_page(opened)) as user:
        await click(user, "Step")

    assert [found_case.name for found_case in opened] == ["big"]


@pytest.mark.asyncio
async def test_the_after_edit_box_is_remembered(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("big"), after_edit=True)

    async with open_page(_tests_page()) as user:
        (box,) = [c for c in found(user, ui.checkbox) if c.text == "Run all the tests after every edit"]
        assert box.value is True

        box.value = False

    assert _saved().after_edit is False


@pytest.mark.asyncio
async def test_save_report_writes_the_results_to_the_output_folder(tmp_path: Path) -> None:
    _load(tmp_path)
    PrimeItems.program_arguments.output_directory = str(tmp_path)
    _keep(_case("big"))
    _break_the_checker()

    async with open_page(_tests_page()) as user:
        await click(user, "Save Report")

        assert any(message.startswith("Report saved as") for message in user.notify.messages)
    text = (tmp_path / "MapTasker_TaskTests.txt").read_text(encoding="utf-8")
    assert "Task tests: 1 run -- 0 passed, 1 failed, 0 not in this file." in text
    assert "[FAILED] big" in text


# ##################################################################################
# The sentences
# ##################################################################################
def test_the_summary_counts_each_kind(tmp_path: Path) -> None:
    _load(tmp_path)
    book = taskcases.CaseBook(cases=[_case("a"), taskcases.Case(name="b", task="Nowhere")])

    assert guiwins_taskcases.summary_text(taskcases.run_all(book, PrimeItems)) == (
        "2 tests: 1 passed, 0 failed, 1 not in this file"
    )
    assert guiwins_taskcases.summary_text([]) == "There are no tests yet."


def test_the_notice_after_an_edit_names_the_first_few_failures_and_counts_the_rest(tmp_path: Path) -> None:
    _load(tmp_path)
    book = taskcases.CaseBook(cases=[_case(f"case {number}") for number in range(5)] + [_case("fine")])
    _break_the_checker()
    results = taskcases.run_all(book, PrimeItems)

    notice = guiwins_taskcases.notice_after_edit(results)

    assert notice.startswith(
        "6 of 6 Task tests no longer behave the way they did when you saved them: 'case 0', 'case 1', 'case 2' and 3 more."
    )
    assert notice.endswith("Open Task Tests to see what changed.")


def test_there_is_no_notice_when_everything_passes_or_is_not_here(tmp_path: Path) -> None:
    _load(tmp_path)
    book = taskcases.CaseBook(cases=[_case("fine"), taskcases.Case(name="b", task="Nowhere")])

    assert guiwins_taskcases.notice_after_edit(taskcases.run_all(book, PrimeItems)) == ""


# ##################################################################################
# Save As Test
# ##################################################################################
def _save_page(task: str = "Checker", n: str = "5", *, want: str = "") -> Callable[[], None]:
    def page() -> None:
        setup = taskcases.Setup(variables={"n": n} if n else {})
        trace = taskstep.step_task(task, PrimeItems, setup.options(PrimeItems))
        assert trace is not None
        guiwins_taskcases.ask_to_save_test(task, setup, trace)

    return page


@pytest.mark.asyncio
async def test_save_offers_a_name_and_every_variable_the_task_changed(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_save_page()) as user:
        assert inputs(user)["Name of the test"].value == "Checker test"
        assert any(c.text.startswith("%r = 'big'") for c in found(user, ui.checkbox))
        assert [c.value for c in found(user, ui.checkbox) if c.text == "What it shows, says and sends"] == [True]
        assert [c.value for c in found(user, ui.checkbox) if c.text == "The route it took"] == [False]


@pytest.mark.asyncio
async def test_saving_keeps_the_run_under_the_name_and_says_so(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_save_page()) as user:
        inputs(user)["Name of the test"].value = "five is big"
        inputs(user)["Note (optional)"].value = "boundary"

        await click(user, "Save")

        assert any("'five is big' saved." in message for message in user.notify.messages)
    case = _saved().get("five is big")
    assert case is not None
    assert (case.task, case.note) == ("Checker", "boundary")
    assert case.setup.variables == {"n": "5"}
    assert case.expected.variables == {"r": "big"}
    assert case.expected.effects is not None and case.expected.path is None


@pytest.mark.asyncio
async def test_only_what_is_ticked_is_kept(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_save_page()) as user:
        (variable,) = [c for c in found(user, ui.checkbox) if c.text.startswith("%r = ")]
        variable.value = False
        (effects,) = [c for c in found(user, ui.checkbox) if c.text == "What it shows, says and sends"]
        effects.value = False
        (route,) = [c for c in found(user, ui.checkbox) if c.text == "The route it took"]
        route.value = True

        await click(user, "Save")

    case = _saved().cases[0]
    assert case.expected.variables == {}
    assert case.expected.effects is None
    assert case.expected.path == ["1:taken"]


@pytest.mark.asyncio
async def test_saving_under_a_name_that_is_taken_replaces_it_and_says_so(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("Checker test", n="1"))

    async with open_page(_save_page()) as user:
        inputs(user)["Name of the test"].value = "Checker test"

        await click(user, "Save")

        assert any("'Checker test' replaced." in message for message in user.notify.messages)
    assert len(_saved().cases) == 1
    assert _saved().cases[0].setup.variables == {"n": "5"}


@pytest.mark.asyncio
async def test_the_name_offered_is_one_nothing_has(tmp_path: Path) -> None:
    _load(tmp_path)
    _keep(_case("Checker test"))

    async with open_page(_save_page()) as user:
        assert inputs(user)["Name of the test"].value == "Checker test 2"


@pytest.mark.asyncio
async def test_a_test_with_no_name_is_not_saved(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_save_page()) as user:
        inputs(user)["Name of the test"].value = "   "

        await click(user, "Save")

        assert any("Give the test a name." in message for message in user.notify.messages)
    assert _saved().cases == []


@pytest.mark.asyncio
async def test_cancel_saves_nothing(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_save_page()) as user:
        await click(user, "Cancel")

    assert _saved().cases == []


@pytest.mark.asyncio
async def test_a_run_that_needed_a_value_is_not_offered_for_saving(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_save_page(n="")) as user:
        assert any("The walk stopped because it needed a value" in message for message in user.notify.messages)
        assert not found(user, ui.input)
    assert _saved().cases == []


# ##################################################################################
# The Stepper
# ##################################################################################
def _stepper_page(case: taskcases.Case | None = None) -> Callable[[], None]:
    def page() -> None:
        def jump(_target: object) -> Callable:
            return lambda *_args: None

        dialog = guiwins_taskstep.build_taskstep_dialog(cast("Callable", jump), PrimeItems, "Checker", case)
        assert dialog is not None
        dialog.open()

    return page


@pytest.mark.asyncio
async def test_save_as_test_is_not_there_until_something_has_been_stepped(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_stepper_page()) as user:
        assert not button(user, "Save As Test").enabled

        _fill_starting(user, "%n = 5")
        await click(user, "Step")

        assert button(user, "Save As Test").enabled


def _fill_starting(user: User, text: str) -> None:
    (box,) = [e for e in found(user, ui.textarea) if str(e.props.get("label", "")).startswith("Starting variables")]
    box.value = text


@pytest.mark.asyncio
async def test_saving_from_the_stepper_keeps_what_was_typed_and_walked(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_stepper_page()) as user:
        _fill_starting(user, "%n = 7")
        await click(user, "Step")

        await click(user, "Save As Test")
        await click(user, "Save")

    case = _saved().cases[0]
    assert (case.task, case.setup.variables) == ("Checker", {"n": "7"})
    assert case.setup.policy == taskstep.POLICY_STOP and case.setup.follow_calls is True
    assert case.expected.variables == {"r": "big"}


@pytest.mark.asyncio
async def test_the_stepper_saves_the_run_on_screen_not_the_boxes_since(tmp_path: Path) -> None:
    """The values typed after Step was pressed are not what was walked."""
    _load(tmp_path)

    async with open_page(_stepper_page()) as user:
        _fill_starting(user, "%n = 7")
        await click(user, "Step")
        _fill_starting(user, "%n = 1")

        await click(user, "Save As Test")
        await click(user, "Save")

    assert _saved().cases[0].setup.variables == {"n": "7"}


@pytest.mark.asyncio
async def test_a_stepper_that_cannot_be_decided_does_not_offer_to_save(tmp_path: Path) -> None:
    _load(tmp_path)

    async with open_page(_stepper_page()) as user:
        await click(user, "Step")  # %n has no value, and the policy is to stop

        await click(user, "Save As Test")

        assert any("needed a value" in message for message in user.notify.messages)
    assert _saved().cases == []


@pytest.mark.asyncio
async def test_a_stepper_opened_on_a_test_has_its_values_in_the_boxes(tmp_path: Path) -> None:
    _load(tmp_path)
    case = _case("big", n="7")
    case.setup.policy = taskstep.POLICY_UNSET
    case.setup.follow_calls = False
    case.setup.use_globals = False
    case.setup.assumed = {2: {"x": "1"}}

    async with open_page(_stepper_page(case)) as user:
        boxes = {str(e.props.get("label", "")).split(" (")[0]: e.value for e in found(user, ui.textarea)}

        assert boxes["Starting variables"] == "%n = 7"
        assert boxes["What an action that is not simulated leaves"] == "2: %x = 1"
        assert [c.value for c in found(user, ui.checkbox) if c.text == "Follow Perform Task"] == [False]
        assert [c.value for c in found(user, ui.checkbox) if c.text == "Use the globals saved in the backup"] == [False]
