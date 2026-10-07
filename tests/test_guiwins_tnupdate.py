"""The TaskerNet Updates dialog: link a share, see what its author changed, take it a piece at a time.

What a link, an alignment and a take do is test_tnupdate's.  What is tested here is the dialog
around them: that a pasted address is read before anything is asked of the network, that a link
is compared with the object it is attached to as soon as it is made, that nothing is applied
unseen, and that a network that is not there says so in the list rather than emptying it.

The network is never touched: the two functions that ask TaskerNet are replaced.  The dialog is
the real one, on a page of NiceGUI's in-process user simulation.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import pytest
from maptasker.src import guiwins_tnupdate, tnupdate
from maptasker.src.primitem import PrimeItems
from nicegui import context, core, ui
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_notify import UserNotify
from nicegui.testing.user_simulation import user_simulation

from tests.test_tnupdate import _V2, LINK, _info, _live, _runtime, _share  # noqa: F401  (_runtime is the fixture)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path

    from nicegui.testing.user import User

_built: dict = {}


@pytest.fixture(autouse=True)
def _network(monkeypatch: pytest.MonkeyPatch, _runtime: None) -> None:  # noqa: F811, PT019
    """TaskerNet replaced by two answers the tests set: what is published, and what it says."""
    _built.clear()
    _built.update(rebuilt=0, saved=0, save_answer=False, asked=[], published=1_700_000_000_000, xml=_V2, offline=False)

    def fetch_info(ref: tnupdate.ShareRef) -> tnupdate.ShareInfo:
        _built["asked"].append(ref.share_id)
        if _built["offline"]:
            message = "Could not reach TaskerNet (ConnectError).  Check the connection and try again."
            raise tnupdate.TaskerNetOfflineError(message)
        return _info(_built["published"])

    monkeypatch.setattr(tnupdate, "fetch_info", fetch_info)
    monkeypatch.setattr(tnupdate, "fetch_xml", lambda _ref: _built["xml"])


def _page() -> None:
    async def rebuild() -> None:
        _built["rebuilt"] += 1

    async def save() -> bool:
        _built["saved"] += 1
        return _built["save_answer"]

    def jump(_target: object) -> Callable:
        return lambda *_args: None

    _built["dialog"] = guiwins_tnupdate.build_tnupdate_dialog(jump, rebuild, save, PrimeItems)
    if _built["dialog"] is not None:
        _built["dialog"].open()


@contextlib.asynccontextmanager
async def _open() -> AsyncIterator[User]:
    try:
        async with user_simulation(root=_page) as user:
            await user.open("/")
            yield user
    finally:
        if core.app.is_started:
            await core.app.stop()


def _buttons(user: User, label: str) -> list[ui.button]:
    return [element for element in user.find(kind=ui.button).elements if element.text == label]


def _only(user: User, label: str) -> ui.button:
    (button,) = _buttons(user, label)
    return button


def _press(user: User, button: ui.button) -> None:
    UserInteraction(user, {button}, None).click()


def _labels(user: User) -> list[str]:
    return [element.text for element in user.find(kind=ui.label).elements]


async def _until(condition: Callable[[], object]) -> None:
    """Wait, up to two seconds, for something the dialog does on a timer or off the event loop."""
    for _ in range(40):
        if condition():
            return
        await asyncio.sleep(0.05)
    msg = "it did not happen"
    raise AssertionError(msg)


def _seed(*, seen: int = 1_600_000_000_000, latest: int = 0, baseline: bool = True) -> tnupdate.Link:
    """A link already made and accepted at an older version, as the dialog finds it on opening."""
    book = tnupdate.default_book()
    link = book.add("Project", "Pack", LINK)
    link.seen_ms, link.latest_ms = seen, latest
    if baseline:
        book.save_baseline(link, _share())
    book.save()
    return link


def _book() -> tnupdate.LinkBook:
    return tnupdate.default_book()


# ##################################################################################
# Opening
# ##################################################################################
@pytest.mark.asyncio
async def test_with_nothing_loaded_there_is_no_dialog_and_a_message() -> None:
    PrimeItems.tasker_root_elements = {"all_tasks": {}, "all_projects": {}}
    async with _open() as user:
        assert _built["dialog"] is None
        assert user.notify.contains("No XML file has been loaded.  Get an XML file first.")


@pytest.mark.asyncio
async def test_with_no_links_it_says_so_and_asks_taskernet_nothing() -> None:
    async with _open() as user:
        await user.should_see("No shares are linked yet.")
        assert _built["asked"] == []


@pytest.mark.asyncio
async def test_it_says_up_front_what_is_sent_and_that_an_update_is_someone_elses_automation() -> None:
    async with _open() as user:
        await user.should_see("no part of your configuration")
        await user.should_see("someone else's automation")


# ##################################################################################
# Linking
# ##################################################################################
@pytest.mark.asyncio
async def test_a_pasted_address_is_read_before_anything_is_asked_of_the_network() -> None:
    async with _open() as user:
        (box,) = user.find(kind=ui.input).elements
        link_button = _only(user, "Link")
        assert not link_button.enabled

        box.set_value("https://example.com/not-taskernet")
        assert not link_button.enabled
        assert any("not a TaskerNet share link" in label for label in _labels(user))

        box.set_value(LINK)
        assert link_button.enabled
        (pick,) = user.find(kind=ui.select).elements
        assert pick.value == "Pack", "the object of that name is already chosen"
        assert _built["asked"] == []


@pytest.mark.asyncio
async def test_linking_compares_the_share_with_your_copy_straight_away_and_makes_the_link_current() -> None:
    _built["xml"] = _share()
    async with _open() as user:
        (box,) = user.find(kind=ui.input).elements
        box.set_value(LINK)
        _press(user, _only(user, "Link"))

        await _until(lambda: _book().links and next(iter(_book().links.values())).seen_ms)
        await user.should_see("Linked.")
        link = _book().links[("Project", "Pack")]
        assert link.seen_ms == link.latest_ms == _built["published"], "taken to be at what is published now"
        assert _book().baseline(link) == _share(), "and kept, so the next update can be told from the rest"
        await user.should_see("Your copy matches it.")


@pytest.mark.asyncio
async def test_a_link_to_a_kind_that_does_not_match_the_object_is_refused() -> None:
    async with _open() as user:
        (box,) = user.find(kind=ui.input).elements
        box.set_value(LINK.replace("Project", "Task"))
        (pick,) = user.find(kind=ui.select).elements
        assert "Morning" in pick.options, "a Task link offers Tasks, not Projects"
        assert "Pack" not in pick.options


# ##################################################################################
# Checking
# ##################################################################################
@pytest.mark.asyncio
async def test_opening_looks_for_newer_versions_and_says_which_link_has_one() -> None:
    _seed()
    _built["published"] = 1_700_000_000_000
    async with _open() as user:
        await user.should_see("Newer version published")
        assert _built["asked"] == ["Project:Pack"]


@pytest.mark.asyncio
async def test_a_link_checked_a_moment_ago_is_not_asked_again_on_opening() -> None:
    link = _seed(latest=1_600_000_000_000)
    link.checked = tnupdate.clock.now().isoformat()
    _book().links[link.key] = link
    _book().save()

    async with _open() as user:
        await user.should_see("Up to date")
        assert _built["asked"] == []


@pytest.mark.asyncio
async def test_check_now_asks_even_so_and_says_when_everything_is_current() -> None:
    link = _seed(seen=1_700_000_000_000, latest=1_700_000_000_000)
    link.checked = tnupdate.clock.now().isoformat()
    _book().save()
    async with _open() as user:
        _press(user, _only(user, "Check Now"))

        await _until(lambda: user.notify.contains("Everything linked is up to date."))
        assert _built["asked"] == ["Project:Pack"]


@pytest.mark.asyncio
async def test_when_taskernet_cannot_be_reached_the_list_says_so_and_keeps_the_link() -> None:
    _seed()
    _built["offline"] = True
    async with _open() as user:
        await user.should_see("Could not reach TaskerNet")
        assert ("Project", "Pack") in _book().links
        assert _only(user, "Review").enabled, "it can be tried again"


# ##################################################################################
# Reviewing and taking
# ##################################################################################
async def _review_the_update(user: User) -> None:
    await user.should_see("Newer version published")
    _press(user, _only(user, "Review"))
    await user.should_see("The author changed")


@pytest.mark.asyncio
async def test_review_lists_what_the_author_changed_and_nothing_else() -> None:
    _seed()
    async with _open() as user:
        await _review_the_update(user)

        # Morning, the anonymous Task, Helper (renamed) and Dawn were changed; Brand New is new.
        assert len(_buttons(user, "Take this")) == 5
        assert any("TASK-NEW" == label for label in _labels(user))
        assert any(label.startswith("Removed by the author") and "Dusk" in label for label in _labels(user))


@pytest.mark.asyncio
async def test_take_this_draws_a_preview_and_changes_nothing() -> None:
    _seed()
    before = _live("all_tasks")["20"]["xml"].findtext("Action/Str")
    async with _open() as user:
        await _review_the_update(user)
        assert not _only(user, "Apply").enabled

        _press(user, _buttons(user, "Take this")[0])

        assert "Preview -- nothing has changed yet" in _labels(user)
        assert _only(user, "Apply").enabled
    assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == before
    assert _built["rebuilt"] == 0


@pytest.mark.asyncio
async def test_apply_takes_the_preview_on_screen_and_turns_its_button_green() -> None:
    _seed()
    async with _open() as user:
        await _review_the_update(user)
        morning = next(button for button in _buttons(user, "Take this") if "Morning" in _row_text(user, button))
        _press(user, morning)
        _press(user, _only(user, "Apply"))

        await _until(lambda: _built["rebuilt"] == 1)
        assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello there"
        assert _live("all_tasks")["21"]["xml"].findtext("nme") == "Helper", "nothing else was touched"
        assert not _only(user, "Apply").enabled, "the preview is spent"
        # The row taken stays on screen with a button that is greyed out; the other four are still to take.
        assert [button.enabled for button in _buttons(user, "Take this")].count(True) == 4


def _row_text(user: User, button: ui.button) -> str:
    """The text of the row a 'Take this' button sits in."""
    row = button.parent_slot.parent
    return " ".join(element.text for element in row.descendants() if isinstance(element, ui.label | ui.link))


@pytest.mark.asyncio
async def test_mark_as_up_to_date_moves_the_accepted_version_forward() -> None:
    _seed()
    async with _open() as user:
        await _review_the_update(user)
        assert _book().links[("Project", "Pack")].status == tnupdate.UPDATE

        _press(user, _only(user, "Mark As Up To Date"))

        await _until(lambda: user.notify.contains("Marked as up to date."))
        saved = _book().links[("Project", "Pack")]
        assert saved.seen_ms == _built["published"]
        assert saved.status == tnupdate.CURRENT
        assert _book().baseline(saved) == _V2, "the next update is compared with this one"


@pytest.mark.asyncio
async def test_unlinking_forgets_the_link_and_its_baseline_and_touches_nothing_else() -> None:
    _seed()
    tasks = {key: entry["xml"].findtext("nme") for key, entry in _live("all_tasks").items()}
    async with _open() as user:
        await user.should_see("Pack")
        _press(user, _only(user, "Unlink"))

        await user.should_see("No shares are linked yet.")
    assert _book().links == {}
    assert {key: entry["xml"].findtext("nme") for key, entry in _live("all_tasks").items()} == tasks


@pytest.mark.asyncio
async def test_a_link_whose_object_is_not_loaded_cannot_be_reviewed() -> None:
    book = _book()
    book.add("Project", "Gone", LINK.replace("Pack", "Gone"))
    async with _open() as user:
        await user.should_see("Not in the configuration that is loaded.")
        assert not _only(user, "Review").enabled


@pytest.mark.asyncio
async def test_a_review_that_fails_says_why_even_though_its_own_button_was_redrawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The row's Review button is deleted when the list of links is redrawn, and the failure message follows.

    Pressing it with nothing readable to compare crashed with "The parent element this slot belongs
    to has been deleted", because the notification was raised from the button that no longer existed.
    """
    _seed()
    _built["xml"] = "this is not tasker xml"
    reached: list[str] = []
    recorder = UserNotify.__call__

    def notify_as_nicegui_does(self: UserNotify, message: str, **kwargs: object) -> None:
        # The first thing the real ui.notify does, and the line that raised: the client of the slot it runs in.
        reached.append(str(context.client.id))
        recorder(self, message, **kwargs)

    monkeypatch.setattr(UserNotify, "__call__", notify_as_nicegui_does)
    async with _open() as user:
        await user.should_see("Newer version published")
        _press(user, _only(user, "Review"))

        await _until(lambda: user.notify.contains("not valid Tasker XML"))
        assert reached, "the notification was raised, and from a context that still exists"
        assert "not valid Tasker XML" in _book().links[("Project", "Pack")].problem


@pytest.mark.asyncio
async def test_differences_that_are_not_the_authors_are_hidden_but_one_tick_away() -> None:
    """Linking lists every difference from your copy; reviewing again lists only the author's, and says so.

    The two lists answer different questions -- 'how does my copy differ from the share?' and 'what
    did the author change since I accepted it?' -- so the second must not look as if the first
    went away.
    """
    _seed()
    _built["xml"] = _share()
    _live("all_tasks")["20"]["xml"].find("Action/Str").text = "my own words"
    async with _open() as user:
        await user.should_see("Newer version published")
        _press(user, _only(user, "Review"))

        await user.should_see("has published nothing new since the version you accepted")
        assert not _buttons(user, "Take this"), "nothing the author changed"
        assert any("still differ from your copy" in label for label in _labels(user))
        (box,) = user.find(kind=ui.checkbox).elements
        assert box.visible

        box.set_value(True)

        await _until(lambda: _buttons(user, "Take this"))
        assert len(_buttons(user, "Take this")) == 1


@pytest.mark.asyncio
async def test_accept_latest_version_shows_what_it_will_take_then_takes_all_of_it_and_moves_the_version_on() -> None:
    _seed()
    async with _open() as user:
        await _review_the_update(user)
        before = _live("all_tasks")["20"]["xml"].findtext("Action/Str")

        _press(user, _only(user, "Accept Latest Version"))

        assert any("5 change(s)" in label for label in _labels(user)), "what it will take is shown first"
        assert _only(user, "Apply").enabled
        assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == before, "and nothing has been done yet"

        _press(user, _only(user, "Apply"))

        await _until(lambda: _built["rebuilt"] == 1)
        assert _live("all_tasks")["20"]["xml"].findtext("Action/Str") == "hello there"
        assert _live("all_tasks")["22"]["xml"].findtext("Action/Str") == "anon v2"
        saved = _book().links[("Project", "Pack")]
        assert saved.seen_ms == _built["published"], "the version published is now the one you have"
        assert _book().baseline(saved) == _V2


@pytest.mark.asyncio
async def test_accept_latest_version_with_nothing_to_take_just_marks_the_version() -> None:
    _seed()
    _built["xml"] = _share()
    async with _open() as user:
        await user.should_see("Newer version published")
        _press(user, _only(user, "Review"))
        await user.should_see("has published nothing new")

        _press(user, _only(user, "Accept Latest Version"))

        await _until(lambda: user.notify.contains("Marked as up to date."))
        assert _book().links[("Project", "Pack")].seen_ms == _built["published"]


@pytest.mark.asyncio
async def test_check_now_says_it_is_asking_taskernet_and_takes_the_notice_down_when_it_has_heard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The notice is up for the whole wait and gone after it -- not left on screen for the session."""
    _seed()
    events: list[str] = []

    class Notice:
        def __init__(self, message: str, **kwargs: object) -> None:
            events.append(f"up: {message}")
            self.kwargs = kwargs

        def dismiss(self) -> None:
            events.append("down")

    monkeypatch.setattr(guiwins_tnupdate.ui, "notification", Notice)
    async with _open() as user:
        await user.should_see("Newer version published")
        events.clear()
        _built["asked"].clear()

        _press(user, _only(user, "Check Now"))

        await _until(lambda: "down" in events)
        assert events == ["up: Asking TaskerNet.  Please stand by...", "down"]
        assert _built["asked"] == ["Project:Pack"]


@pytest.mark.asyncio
async def test_the_check_made_as_the_dialog_opens_does_not_put_a_notice_up(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed()
    made: list[str] = []
    monkeypatch.setattr(guiwins_tnupdate.ui, "notification", lambda message, **_: made.append(message))
    async with _open() as user:
        await user.should_see("Newer version published")
    assert made == []
