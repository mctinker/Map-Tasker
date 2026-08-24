"""mapjump: what a reported object is, and how to find it again in the Map or Diagram view."""

#! /usr/bin/env python3

#                                                                                      #
# mapjump: the identity of an object a report points at, the anchor that identity gets  #
#          in the generated Map, and the browser-side jump to it.                       #
#                                                                                      #
# Two reports name objects: healthck's findings and varxref's references.  Both used to #
# describe an object only in prose ("Project 'Home' > Task 'Wake Up' (id 118)"), which  #
# reads well and can be sorted, but cannot be clicked: prose cannot tell two Tasks of   #
# the same name apart -- which is the very thing DUPLICATE-NAME exists to report -- and #
# an unnamed Task has no name to go on at all.                                          #
#                                                                                      #
# Target below carries the identity alongside the prose.  Target.label reproduces what  #
# the two reports printed before this module existed, character for character, so the   #
# saved reports are unchanged; Target.anchor is the same identity as an HTML id, which  #
# is what the Map view is given so a click can land on it.                              #
#                                                                                      #
# Identity is by id wherever Tasker has one (Task, Profile) and by name only where it   #
# does not -- Tasker keys Projects and Scenes by name itself, so there is nothing else   #
# to use.                                                                               #
#                                                                                       #
# No GUI imports here.  healthck and varxref both promise to read nothing but            #
# PrimeItems.tasker_root_elements and to be testable without standing up a GUI, and      #
# they import this; the JavaScript below is inert text as far as this module is          #
# concerned, handed to guiwins to run.                                                   #
#                                                                                       #
# MIT License   Refer to https://opensource.org/license/mit                             #
#
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from html import escape
from urllib.parse import quote, unquote

from maptasker.src.primitem import PrimeItems, get_single_item_requested
from maptasker.src.sysconst import (
    DISPLAY_DETAIL_LEVEL_all_parameters,
    DISPLAY_DETAIL_LEVEL_everything,
)

# What kind of thing a Target names.  Deliberately not an Enum: these are written into
# HTML ids and into the token that crosses into the browser and back, so they are strings
# in both directions anyway, and an Enum would only add a conversion at each boundary.
PROJECT = "project"
PROFILE = "profile"
TASK = "task"
SCENE = "scene"
VARIABLE = "variable"

# How each kind is named in a report.  "Task" covers an action too -- an action is not a
# thing of its own here, it is a position inside a Task (see Target.action), which is
# exactly how both reports word it: "Task 'Wake Up' (id 118) action 4".
_KIND_LABELS = {
    PROJECT: "Project",
    PROFILE: "Profile",
    TASK: "Task",
    SCENE: "Scene",
    VARIABLE: "Variable",
}

# Kinds Tasker itself keys by id.  Everything else is keyed by name, and saying so in one
# place is what keeps Target.label from printing "(id Home)" for a Project.
_KEYED_BY_ID = frozenset({PROFILE, TASK})

# The class every anchor emitted into the Map carries.  It marks an element as a marker
# rather than content: the jump highlights the element the anchor precedes, not the
# (empty, invisible) anchor itself -- see jump_js below.  A variable's row carries the id
# without this class, which is how jump_js tells "this marks the thing" from "this IS the
# thing" (see anchor_attribute for the other way an id gets written).
ANCHOR_CLASS = "mt-anchor"

# The class the jump puts on whatever it lands on.  Styled in guiwins.inject_shared_head_styles.
HIGHLIGHT_CLASS = "mt-jump-target"

# How many colon-separated fields Target.token writes.  Named so that adding one cannot be
# done without the reader that counts them being updated in the same breath.
_TOKEN_FIELDS = 5


@dataclass(frozen=True)
class Target:
    """One object a report points at, in a form the Map view can find again.

    Frozen because a Target is an identity, not a workspace: at_action() and with_text()
    return new ones rather than mutating a shared record, which is what lets a Task's
    Target be built once per Task and then have per-action Targets derived from it inside
    the loop over its actions.
    """

    kind: str
    # The Task/Profile id, or the Project/Scene/variable name -- see _KEYED_BY_ID.
    key: str
    name: str = ""  # display name; "" when the object has none
    project: str = ""  # owning Project's name; "" when no Project owns it
    action: int = 0  # 1-based action number, when the target is a position inside a Task
    within: str = ""  # a place with no anchor of its own: "entry Task", "component 'Send'"
    scope_id: str = ""  # varxref's scope: a Task id, "scene:<name>" or "profile:<id>"

    @property
    def anchor(self) -> str:
        """The HTML id this object carries in the generated Map.

        Names are percent-encoded because an HTML id may not hold a space and a Tasker
        name routinely does; the encoding is reversible, so an anchor can be read back
        into the name it came from when debugging a jump that went nowhere.

        An action number only refines a Task's anchor.  A Scene's inline anonymous task
        also has actions (see healthck's scene walk), but the Map gives those no anchor
        of their own, so the Scene's own anchor is returned rather than one that is
        guaranteed to match nothing -- the same rule the reports follow when they decline
        to link to an object that is not in the file.
        """
        base = f"mt-{self.kind}-{quote(self.key, safe='')}"
        return f"{base}-a{self.action}" if self.action and self.kind == TASK else base

    @property
    def label(self) -> str:
        """This object's name as the reports print it.

        The whole of healthck's and varxref's old _describe/_in_project pair, plus the
        suffixes their callers used to append by hand.  Order matters and is theirs:
        the place inside the object ("anonymous Task") comes before the position inside
        that place ("action 4").
        """
        identifier = self.key if self.kind in _KEYED_BY_ID else ""
        phrase = in_project(describe(_KIND_LABELS[self.kind], self.name, identifier), self.project)
        if self.within:
            phrase = f"{phrase} {self.within}"
        return f"{phrase} action {self.action}" if self.action else phrase

    def at_action(self, number: int) -> Target:
        """This object, at one of its actions."""
        return replace(self, action=number)

    def with_text(self, text: str) -> Target:
        """This object, at a place inside it that the Map gives no anchor of its own."""
        return replace(self, within=text)

    def token(self) -> str:
        """This target as one string, for crossing into the browser and back.

        What a jump needs travels, and nothing else: the kind and key say what to look for,
        the action number refines it, the name is what a search fallback would type into the
        box, and the owning Project is which Map has to be built to contain any of it (see
        scope_for).

        The Project is here because it is load-bearing, not prose.  It was left out at
        first, on the grounds that the report had already printed it -- and the jump then
        rebuilt the whole configuration every time, because the Target that came back from
        the browser had no Project on it to narrow to.  'within' really is prose ("entry
        Task", "component 'Send'") and really is left out.
        """
        return ":".join(
            (
                self.kind,
                quote(self.key, safe=""),
                str(self.action),
                quote(self.name, safe=""),
                quote(self.project, safe=""),
            ),
        )

    @classmethod
    def from_token(cls, token: str) -> Target | None:
        """The Target a token came from, or None if it is not one.

        Partial by design -- a token carries identity, not prose -- so the result is
        good for finding the object and no good for re-printing the finding.
        None rather than an exception: the token arrives from the browser, and a report
        rendered by an older run of MapTasker is a stale click, not a program error.
        """
        parts = token.split(":")
        if len(parts) != _TOKEN_FIELDS or parts[0] not in _KIND_LABELS:
            return None
        kind, key, action, name, project = parts
        return cls(
            kind=kind,
            key=unquote(key),
            name=unquote(name),
            project=unquote(project),
            action=int(action or 0),
        )


def describe(kind: str, name: str, identifier: str = "") -> str:
    """An object's name for a report: Task 'Wake Up' (id 118), or Task (id 118) [unnamed].

    Shared by healthck and varxref, which each carried their own copy of this.  Also
    called directly, rather than through a Target, where what is being described is a
    NAME rather than an object -- healthck's DUPLICATE-NAME heading names the name that
    several Tasks share, and no one Task is the subject of it.
    """
    if name:
        return f"{kind} '{name}'" + (f" (id {identifier})" if identifier else "")
    return f"{kind} (id {identifier}) [unnamed]" if identifier else f"{kind} [unnamed]"


def in_project(where: str, project_name: str | None) -> str:
    """Put the owning Project in front of an object's name, when a Project owns it.

    Every location in both reports reads the same way because of this -- "Project 'Home' >
    Task 'Wake Up' (id 118)" -- which is what lets a report be sorted by location and come
    out grouped by Project.

    Silent when nothing owns the object, rather than saying so: a Task in no Project is
    ordinary (Tasker keeps unassigned Tasks in its own Tasks tab), and a location is the
    wrong place to raise it.  Where that fact actually matters -- an unreferenced Task
    someone may be about to delete -- healthck says so in the finding's detail instead.
    """
    return f"Project '{project_name}' > {where}" if project_name else where


def minimum_detail_level(target: Target) -> int:
    """The lowest detail level at which the Map SHOWS what a finding about this is about.

    Not merely the level at which the object has an anchor -- landing on a line that does
    not say the thing is no better than not landing at all.  Every figure below was
    measured against a real backup rather than read off the option's description:

      Projects, Profiles          any level.  The finding is about the object itself, and
                                  its own line is on the Map from level 0.
      Tasks and their actions     DISPLAY_DETAIL_LEVEL_all_parameters.  Actions appear one
                                  level below that, but bare: "03: Perform Task", with no
                                  sign of WHICH Task it performs -- which is the whole of a
                                  BROKEN-PERFORM-TASK finding.  At this level the same line
                                  reads "03: Perform Task Name=Fetch Windspeed".
      Scenes                      DISPLAY_DETAIL_LEVEL_everything.  A Scene's elements are
                                  drawn from level 2, but their properties -- the
                                  "Text=%Charging %Battery" a variable finding is pointing
                                  at -- only at the top level.  A finding about a Scene is
                                  always about something inside it, so a bare
                                  "Scene: Launcher" answers nothing.
      Variables                   DISPLAY_DETAIL_LEVEL_everything.  The two variable tables
                                  are gated a level below, but the top level walks more of
                                  the file, so globalvr collects more variables to list.

    A floor, never a ceiling: a user already higher keeps what they have.  The cost of the
    higher floors is small now that a jump narrows the Map to one Project -- for the Project
    in the example above, level 3 is 1,144 lines against 979 at level 2.
    """
    if target.kind in (VARIABLE, SCENE):
        return DISPLAY_DETAIL_LEVEL_everything
    if target.kind == TASK:
        return DISPLAY_DETAIL_LEVEL_all_parameters
    return 0


def actions_in_map_order(task_element: object) -> list:
    """A Task's actions in the order the Map numbers them.

    NOT document order.  Tasker writes a Task's actions as act0, act1, act10, act11, act12,
    act13, act14, act2, act3 ... -- sorted as text, not as numbers -- and findall("Action")
    hands them back exactly that way.  The Map sorts them numerically on that same attribute
    before printing them (tasks.get_actions, via shelsort.shell_sort with
    do_arguments=True), so the eighth element in the file can be the third action on screen.

    Anything counting actions has to count them the way the Map does, or it reports a number
    the user cannot find: a broken Perform Task at act2 was reported as "action 8", and its
    jump highlighted whatever really was eighth.  That is a wrong answer in the report's own
    prose, not only in the jump.

    Sorted with a key that matches shell_sort's comparison on well-formed data.  An action
    whose sr is missing or not a number cannot be placed by it -- shell_sort gives up on
    those too -- so they keep their document order at the end rather than raising.
    """

    def position(item: tuple[int, object]) -> tuple[int, int, int]:
        index, action = item
        suffix = str(getattr(action, "attrib", {}).get("sr", ""))[3:]
        return (0, int(suffix), index) if suffix.isdigit() else (1, 0, index)

    return [action for _, action in sorted(enumerate(task_element.findall("Action")), key=position)]


def scope_for(target: Target) -> str:
    """The Project a Map has to be narrowed to for this object to be in it, or "" for all.

    One function so the two sides of a jump cannot disagree: the check for whether a Map
    already on screen can be reused, and the rebuild that runs when none can.  If they
    answered differently, a click would either rebuild a Map it already had or reuse one
    that shows the wrong thing.

    "" where there is no Project to narrow to -- an orphan Profile, a Scene no Project
    lists, a Task filed under none, and variables, which the Map indexes per Project but
    the cross-reference does not attribute to one.
    """
    return target.key if target.kind == PROJECT else target.project


def exists(target: Target) -> bool:
    """Whether the object a Target names is still in the loaded configuration.

    A report is a snapshot.  Between running one and clicking a line of it, the Task it
    names can have been renamed, moved or deleted in the editor -- so a jump asks this
    first and says what happened rather than scrolling to nothing.

    Variables are exempt: PrimeItems.variables is filled in while the Map is BUILT
    (globalvr.get_variables), so before the first Map run of a session it is empty, and
    answering "no such variable" then would be wrong for every one of them.
    """
    tables = {
        PROJECT: "all_projects",
        PROFILE: "all_profiles",
        TASK: "all_tasks",
        SCENE: "all_scenes",
    }
    table = tables.get(target.kind)
    return True if table is None else target.key in PrimeItems.tasker_root_elements[table]


# ##################################################################################
# Scope: which objects a scan is allowed to look at.
#
# The app has a "display only this one" selector -- one Project, or Profile, or Task, or
# Scene (primitem.SINGLE_ITEM_SELECTORS).  When it is set, the Map on screen is that one
# object, and a Find that answered with hits from the other 82 Projects would be
# answering a question about something the user cannot see.  A Replace doing the same
# would be worse: it would change them.
#
# Lives here rather than in mapfind or varxref because both need it and neither may
# import the other -- the same reason the location helpers moved here.  It is a question
# about which objects contain which, which is a question about identity.
# ##################################################################################
@dataclass(frozen=True)
class Scope:
    """The objects a scan may look at, as the set of keys of each kind.

    Keys, not Targets: a scan tests membership once per object as it walks the tables, and
    the tables are keyed the way Target.key is -- Projects and Scenes by name, Profiles and
    Tasks by id.

    An empty Scope (label "") means everything, and `allows` short-circuits on it, so the
    unscoped case costs one attribute read per object rather than four set lookups.
    """

    label: str = ""  # "Project" / "Profile" / "Task" / "Scene"; "" for the whole file
    name: str = ""
    projects: frozenset[str] = frozenset()
    profiles: frozenset[str] = frozenset()
    tasks: frozenset[str] = frozenset()
    scenes: frozenset[str] = frozenset()

    @property
    def is_everything(self) -> bool:
        """Whether this scope excludes nothing."""
        return not self.label

    @property
    def phrase(self) -> str:
        """'Task 'Wake Up'' -- how a report names what it was limited to."""
        return f"{self.label} '{self.name}'" if self.label else ""

    def allows(self, kind: str, key: str) -> bool:
        """Whether an object of this kind and key is inside the scope."""
        if self.is_everything:
            return True
        return key in {
            PROJECT: self.projects,
            PROFILE: self.profiles,
            TASK: self.tasks,
            SCENE: self.scenes,
        }.get(kind, frozenset())


def _members(project_element: object, tag: str) -> list[str]:
    """A Project's comma-separated member list -- its Profile ids, Task ids or Scene names."""
    child = project_element.find(tag)
    raw = (child.text or "").strip() if child is not None else ""
    return [piece.strip() for piece in raw.split(",") if piece.strip()]


def current_scope() -> Scope:
    """What the app is displaying, as a Scope -- everything, when nothing single is chosen.

    What each kind pulls in is what the Map itself shows for that selection:

      Project   the Project, and the Profiles, Tasks and Scenes it lists.
      Profile   the Profile and the Tasks it runs.  Not its Project: the user asked for
                one Profile, and a Project is not inside a Profile.
      Task      that Task alone.
      Scene     that Scene alone.  Its inline anonymous Tasks travel with it, since they
                live inside the <Scene> and have no entry in all_tasks to be excluded by.

    A selection naming something that is not in the loaded file gives an EMPTY scope
    rather than a full one -- nothing matches, which is the honest answer, where falling
    back to everything would quietly widen a Replace to the whole configuration.
    """
    label, name = get_single_item_requested()
    if not label:
        return Scope()

    roots = PrimeItems.tasker_root_elements
    if label == "Project":
        project = (roots.get("all_projects") or {}).get(name)
        if project is None:
            return Scope(label, name)
        element = project["xml"]
        return Scope(
            label,
            name,
            projects=frozenset({name}),
            profiles=frozenset(_members(element, "pids")),
            tasks=frozenset(_members(element, "tids")),
            scenes=frozenset(_members(element, "scenes")),
        )

    if label == "Profile":
        # Profiles are keyed by id in the tables and chosen by NAME in the pulldown.
        for profile_id, profile in (roots.get("all_profiles") or {}).items():
            if profile.get("name") == name:
                # mid0/mid1 are the entry and exit Tasks.  Read from the element rather
                # than from any cached list, so a Task attached since the Map was drawn
                # is in scope as much as one that was there when it was.
                task_ids = {
                    (child.text or "").strip()
                    for child in profile["xml"]
                    if child.tag in ("mid0", "mid1") and (child.text or "").strip()
                }
                return Scope(label, name, profiles=frozenset({profile_id}), tasks=frozenset(task_ids))
        return Scope(label, name)

    if label == "Task":
        ids = {task_id for task_id, task in (roots.get("all_tasks") or {}).items() if task.get("name") == name}
        return Scope(label, name, tasks=frozenset(ids))

    if label == "Scene":
        return Scope(label, name, scenes=frozenset({name}))

    return Scope()


# ##################################################################################
# Reports: one line of a report, rendered as text for the file and HTML for the GUI.
# ##################################################################################
# The class every clickable line of a rendered report carries.
FINDING_CLASS = "mt-finding"


@dataclass
class Row:
    """One line of a report, and what clicking it should go to.

    The reports are written twice over -- as the plain text that is saved to a file, and
    as the HTML that is shown in the GUI -- and the two must say the same thing.  Building
    a list of these instead of a list of strings is what keeps them from drifting: the
    text is written once, and each renderer below decides only how to wrap it.
    """

    text: str
    target: Target | None = None
    # For a line that names more than one thing -- two spellings of a near-duplicate
    # variable, the several Tasks sharing a name -- the line broken into (text, target)
    # pieces that join back into `text`.  Built by of_pieces below rather than by hand, so
    # the two can never disagree.
    pieces: list[tuple[str, Target | None]] = field(default_factory=list)

    @classmethod
    def of_pieces(cls, pieces: list[tuple[str, Target | None]]) -> Row:
        """A line assembled from parts, each of which may point somewhere of its own."""
        return cls("".join(text for text, _ in pieces), None, list(pieces))


def text_report(rows: list[Row]) -> str:
    """The report as the plain text that gets saved.  Byte for byte what it always was."""
    return "\n".join(row.text for row in rows)


def _clickable(text: str, target: Target | None) -> str:
    """One piece of a rendered report: wrapped when it points somewhere, escaped either way.

    role/tabindex rather than an <a href>: this is not a link to anywhere, it is a control
    that asks the Map view to move, and a real href would offer a "copy link address" that
    leads nowhere.  Both are what make it reachable by keyboard -- see click_wiring_js.
    """
    if target is None:
        return escape(text)
    return (
        f'<span class="{FINDING_CLASS}" data-mt-target="{escape(target.token())}"'
        f' role="link" tabindex="0">{escape(text)}</span>'
    )


def html_report(rows: list[Row]) -> str:
    """The report as HTML, with every row that has a target made clickable.

    Escaped here, once, rather than by the caller: NiceGuiTextView drops this straight
    into a <pre> with sanitize=False, so a Tasker name holding '<', '>' or '&' would
    otherwise be read as markup rather than shown as the name it is.  Doing it per row
    is what lets the wrappers be added at all -- escaping the finished HTML would escape
    them too.

    A row broken into pieces has each piece wrapped separately; otherwise the whole line
    is one control.
    """
    return "\n".join(
        (
            "".join(_clickable(text, target) for text, target in row.pieces)
            if row.pieces
            else _clickable(row.text, row.target)
        )
        for row in rows
    )


def click_wiring_js(container_id: str) -> str:
    """JavaScript that makes the rendered rows of a report clickable.

    One delegated listener on the container rather than a handler per row: a health check
    of a large configuration runs to hundreds of findings, and this way the count does not
    matter.  The guard makes it safe to call again for the same container -- a second
    listener would emit every click twice, and the jump would run twice over.
    """
    return f"""
        const container = document.getElementById({json.dumps(container_id)});
        if (!container || container.dataset.mtFindingClicks) return;
        container.dataset.mtFindingClicks = "1";

        const jump = (event) => {{
            const row = event.target.closest('[data-mt-target]');
            if (!row) return;
            event.preventDefault();
            emitEvent('mt_jump', {{ target: row.dataset.mtTarget }});
        }};
        container.addEventListener('click', jump);
        // Enter and Space, so a row reached by tabbing behaves like the control it says
        // it is.  Space would otherwise scroll the report out from under the user.
        container.addEventListener('keydown', (event) => {{
            if (event.key === 'Enter' || event.key === ' ') jump(event);
        }});
    """


# ##################################################################################
# Anchors in the generated Map.
# ##################################################################################
def anchor_html(target: Target) -> str:
    """The empty anchor element that marks this object's place in the Map output.

    Emitted whatever the settings, unlike the directory's own anchors
    (lineout.add_directory_link), which appear only when the "directory" option is on and
    are keyed by name.  A health check has to be able to reach an object whether or not
    the user asked for a directory, and has to reach the right one of two Tasks sharing a
    name, so this is a second, id-keyed set of anchors rather than a change to those.  The
    "mt-" prefix keeps the two namespaces from ever colliding.

    "" for an object already anchored in this run.  The Map lists a Task once per Profile
    that runs it, so a shared Task is written several times over -- and an id may appear in
    a document only once.  The first sighting keeps the anchor and the rest go without, so
    a jump lands on the Task's first appearance rather than on whichever of several
    identical ids the browser happened to settle on.
    """
    anchor_id = target.anchor
    if anchor_id in PrimeItems.emitted_anchors:
        return ""
    PrimeItems.emitted_anchors.add(anchor_id)
    return f'<a id="{anchor_id}" class="{ANCHOR_CLASS}"></a>'


def anchor_attribute(target: Target) -> str:
    """This object's anchor as a bare id="..." attribute, for a line with no room for an element.

    Task actions are anchored this way and nothing else is.  lineout.handle_action wraps
    each action in a deliberately unclosed '<div ' and lets the browser fold the following
    '<span class="action_color actiontab"' into that div's own attribute list -- which is
    how the div ends up carrying the action's colour and indentation.  An <a> element
    written into that gap is swallowed the same way and never becomes an element at all;
    worse, it hands the div its own class and hides every action line.  An id, being an
    attribute already, is absorbed exactly as intended: the div keeps its colour and gains
    the id, and the jump lands on the div, which is the whole action line.

    Returns a trailing space with the attribute, and "" for an object already anchored in
    this run -- see anchor_html for why.
    """
    anchor_id = target.anchor
    if anchor_id in PrimeItems.emitted_anchors:
        return ""
    PrimeItems.emitted_anchors.add(anchor_id)
    return f'id="{anchor_id}" '


# ##################################################################################
# The browser side.
# ##################################################################################
# Reveal an element that a chunk skipped by "content-visibility: auto" never laid out.
#
# NiceGuiTextView.process_data streams the Map/Diagram into chunks marked
# content-visibility: auto so the browser can skip layout and paint for the parts that are
# off screen.  The saving is real and worth keeping, but an element inside a skipped chunk
# has no position yet, so scrollIntoView() on it lands somewhere else entirely.  Forcing
# the chunk visible first is the fix, and it is needed by every jump in the app -- this
# one, the search results dialog, and the Diagram's connector jump buttons -- which is why
# it is defined once here instead of a third time in guiwins.
REVEAL_ANCESTORS_JS = """
            function mtRevealAncestors(element) {
                // A line the interactive Diagram view has folded away or filtered out is
                // hidden outright, and scrolling to something with no box is scrolling to
                // nowhere -- so ask that view to open it back up first.  The hook is absent
                // on every other page and on a Diagram with no model behind it, which is why
                // it is asked for rather than called (see diagintr.interaction_js).
                if (window.mtDiagramReveal) window.mtDiagramReveal(element);
                for (let node = element; node; node = node.parentElement) {
                    if (getComputedStyle(node).contentVisibility === "auto") {
                        node.style.contentVisibility = "visible";
                    }
                }
            }
"""


def bring_to_front_js() -> str:
    """JavaScript that raises the window it runs in, for a jump that landed in another one.

    A jump answered by a view already on screen used to be silent from the user's side.  The
    Map really did scroll to the object -- but the Map is a window of its own, and clicking
    an object in the Diagram left the Diagram in front, so the answer sat in a window nobody
    was looking at.  It only appeared once the user thought to switch tabs, which reads as
    the click having done nothing.  The first click of a session was the exception and hid
    the problem: no Map exists yet, so it goes the long way round through
    rebuild_map_for_jump, and window.open() raises the new window on the way past.

    Three ways of asking, because raising a window is a thing browsers restrict rather than
    a thing they simply do, and which one is allowed depends on who is asking.  Each is
    tried and none is required to work:

      window.focus()                        the direct request, granted least often.
      window.opener.open('', window.name)   asking the window that OPENED this one to raise
                                            it, which is the case browsers are most willing
                                            to allow -- and the same call _open_popout_window
                                            already relies on to re-navigate a named popout
                                            from a server-pushed script.
      window.open('', window.name)          the same lookup, from here, for a window with no
                                            opener left to ask (one the user reloaded, or
                                            reached by its URL).

    The empty URL matters in the last two: opening a name that already exists with no URL
    finds that window and navigates nowhere, so the view is raised without being rebuilt.
    A name that exists is a precondition, not a hope -- this only ever runs in a window that
    was opened under one (see _open_popout_window), and the guard on window.name is what
    keeps it from conjuring a blank popup if that ever stops being true.
    """
    return """
        (() => {
            try { window.focus(); } catch (error) {}
            if (!window.name) return true;
            try {
                if (window.opener && !window.opener.closed) {
                    window.opener.open('', window.name);
                    return true;
                }
            } catch (error) {}
            try { window.open('', window.name); } catch (error) {}
            return true;
        })();
    """


def jump_js(anchor_id: str) -> str:
    """JavaScript that scrolls the Map view to an anchor and highlights what it marks.

    Returns a script that does nothing at all when the anchor is not on the page: a Map
    built for a single Project, cut short at the view limit, or generated before this
    object existed simply has no such id, and the caller decides what to do about that
    (rebuild, or fall back to a text search).  Reporting "not found" back to Python is the
    caller's business too -- hence the boolean this evaluates to.

    What gets highlighted is the element the anchor MARKS, not the anchor: object anchors
    are empty and invisible, and sit immediately before the line they belong to, so the
    next element is the Project/Profile/Task/Scene line itself.  A variable's id is on its
    own table row instead, because a row is a real element already and an empty anchor
    inside a <table> would not survive the browser's table fix-up.
    """
    # "return" at the top level, and an IIFE inside it: ui.run_javascript() compiles what it
    # is given as the body of a function, so a bare expression's value never comes back --
    # only an explicit return does.  The same shape the search JS in guiwins uses.
    return f"""
        return (() => {{
{REVEAL_ANCESTORS_JS}
            const anchor = document.getElementById({json.dumps(anchor_id)});
            if (!anchor) return false;
            mtRevealAncestors(anchor);

            // With the "twisty" option on, a Task's line and everything under it sit inside
            // a collapsed <details> (see twisty.add_twisty).  Scrolling to something the
            // browser is not displaying does nothing at all, so open every one of them on
            // the way down first -- the user asked to be taken here.
            for (let box = anchor.closest('details'); box; box = box.parentElement?.closest('details')) {{
                box.open = true;
            }}

            // An empty marker highlights what follows it; anything else (a variable's own
            // table row) IS the target.
            //
            // "What follows it" is the next element with something in it, not simply the
            // next element: the output pipeline puts a <br>, and sometimes an empty
            // wrapper, between an anchor and the line it belongs to (see
            // lineout.handle_project and handle_profile).  Highlighting a line break draws
            // an outline around nothing, which reads as the jump having failed.
            let target = anchor;
            if (anchor.classList.contains({ANCHOR_CLASS!r})) {{
                target = anchor.nextElementSibling;
                while (target && !target.textContent.trim()) {{
                    target = target.nextElementSibling;
                }}
                target = target || anchor.parentElement;
            }}
            if (!target) return false;

            document.querySelectorAll('.{HIGHLIGHT_CLASS}').forEach(
                (element) => element.classList.remove('{HIGHLIGHT_CLASS}'),
            );
            mtRevealAncestors(target);
            target.classList.add('{HIGHLIGHT_CLASS}');
            // Instant, not smooth -- the same choice the Diagram's jumps make, and for one
            // more reason besides theirs.
            //
            // Theirs: a jump crosses tens of thousands of pixels on a large output, where an
            // animated scroll is slow to land and distracting rather than helpful.
            //
            // And: a smooth scroll is an animation, and an animation does not run on a page
            // the browser is not displaying.  This jump is delivered the moment the Map has
            // finished streaming in, which is precisely when its window may not be the one in
            // front -- a popout the browser opened behind, or one the user has clicked away
            // from while it built.  The animation then never starts, never recovers, and
            // leaves a Map sitting at the top with the object highlighted 40,000 pixels down
            // where nobody will see it.  Setting the position outright works either way.
            target.scrollIntoView({{ behavior: 'auto', block: 'center' }});
            return true;
        }})();
    """


# ##################################################################################
# The Diagram view.
# ##################################################################################
# The Diagram has no anchors and cannot be given any: it is plain text whose line numbers
# must line up 1:1 with PrimeItems.diagram_connectors (see guiwins' process_data), so an id
# written into it would be a line of the diagram.
#
# What it has instead is a record of where each object was DRAWN -- see diagram.py's note
# above flatten_with_quotes, and diagram_placement below.  That is the primary way in, and
# it is as exact as the Map's anchors: it tells two Tasks of one name apart, because it
# knows which line each was drawn on rather than what either was called.
#
# The text match below is the fallback for when there is no record: a Diagram built for one
# Project holds nothing outside it, one cut short at the view limit stops before the rest,
# and one built by a MapTasker older than this recorded nothing at all.  It is weaker, and
# is treated as such -- it lands on the first copy of a duplicated name, and it has nothing
# to offer for a Task action, since the Diagram draws no actions.
#
# The forms below are diagram.py's own, and are the whole of what it draws an object as:
#
#   Project    ║ Project: Home ║          print_box(project, "Project:", 1)
#   Profile    ║ Wake Up ║               build_box via build_profile_box
#   Scene      ║ Launcher ║              build_box via print_all_scenes, after "Scenes:"
#   Task       └─ Wake Up                add_quotes, then " (entry)"/" [Calls ..." etc.
#
# A Profile and a Scene are drawn identically, which is why both patterns are offered for
# either and the first match on the page wins -- the alternative, guessing, would be no
# more accurate and would fail outright where the guess was wrong.
def _diagram_project_prefix() -> str:
    """How the Diagram labels a Project box, in whatever language it was drawn in.

    diagram.build_network_map's own rule, repeated rather than imported: importing
    diagram here would pull the whole output pipeline into a module healthck and varxref
    rely on being able to import without one.  The language check is theirs too -- English
    and Arabic are left untranslated there, so translating here would look for a label the
    Diagram never wrote.
    """
    from maptasker.src.maputil2 import translate_string  # noqa: PLC0415  GUI-free, but only needed here

    if PrimeItems.program_arguments.get("language", "English") in ("Arabic", "English"):
        return "Project: "
    return f"{translate_string('Project:')} "


def diagram_patterns(target: Target) -> list[str]:
    """The text this object is drawn as in the Diagram, likeliest form first.

    Empty for an object the Diagram has no line for -- an unnamed Task, which the Diagram
    draws under a derived name this cannot reconstruct, and a variable, which it does not
    draw at all.  The caller turns that into "the Diagram has no line for this" rather
    than into a search that quietly matches something else.
    """
    name = target.name.strip()
    if not name or target.kind == VARIABLE:
        return []
    if target.kind == PROJECT:
        return [f"║ {_diagram_project_prefix()}{name} ║"]
    if target.kind == TASK:
        # The trailing space is what keeps "Test1" from landing on "Test13": every Task
        # line diagram.py writes continues past the name, with a type marker, a call
        # annotation or the padding that carries the connector bars.
        return [f"└─ {name} ", f"└─ {name}"]
    return [f"║ {name} ║"]


def diagram_placement(target: Target) -> tuple[int, int, int] | None:
    """Where the Diagram that was last built drew this object: (line, column, length).

    None when it did not draw it -- a Diagram narrowed to one Project, one cut short at the
    view limit, one built before this version recorded anything, or no Diagram at all.  The
    caller falls back to matching the drawn text, which is what this replaced.

    An action is answered by its Task's own line.  The Diagram draws no actions, so a Find
    result pointing at "action 5 of Task 118" has nowhere finer to land than Task 118 --
    and landing there is the right answer rather than a failure to be reported.
    """
    anchors = getattr(PrimeItems, "diagram_anchors", None)
    if not anchors:
        return None
    return anchors.get(replace(target, action=0).anchor)


def diagram_anchor(target: Target) -> str:
    """The id this object's name carries in an interactive Diagram, or "".

    The same normalisation diagram_placement makes: the Diagram draws no actions, so an
    action's Target is answered by the Task that holds it.  Kept beside it so the element
    looked up and the line fallen back to can never be two different objects.
    """
    return replace(target, action=0).anchor if target.kind != VARIABLE else ""


def diagram_jump_js(
    container_id: str,
    patterns: list[str],
    placement: tuple[int, int, int] | None = None,
    anchor: str = "",
) -> str:
    """JavaScript that scrolls the Diagram view to an object and highlights it.

    Three ways of finding it, tried in that order.

    The anchor, when the Diagram on screen is an interactive one: every object's name is
    wrapped in an element carrying its id, so this is a lookup and the answer is exact.

    Then the two that came before it, and the difference between them is the difference
    between "a Task called Backup" and "THIS Task called Backup".

    With a placement, the line was recorded as the diagram was drawn (see diagram.py's
    note above flatten_with_quotes) and is followed exactly: the walk counts newlines to
    the line and UTF-16 code units across it, which is what the recorded column was
    measured in.  Two Tasks of the same name land on their own lines, and a Task drawn
    several times lands on the first drawing, as it does in the Map.

    Without one, the drawn text is matched instead -- the fallback for a Diagram that does
    not hold this object, or that was built by a version of MapTasker with no seeds in it.
    A name can appear in more than one place, so the first is taken.

    Evaluates to false when neither finds anything, which is the caller's cue to build a
    Map instead.
    """
    return f"""
        return (() => {{
{REVEAL_ANCESTORS_JS}
            const container = document.getElementById({json.dumps(container_id)});
            if (!container) return false;
            const patterns = {json.dumps(patterns)};
            const placement = {json.dumps(list(placement) if placement else None)};
            const anchor = {json.dumps(anchor)};
            if (!patterns.length && !placement && !anchor) return false;

            // Any highlight left by a previous jump goes first, in both views' shared class,
            // so only the object just asked for is marked.
            document.querySelectorAll('.{HIGHLIGHT_CLASS}').forEach(
                (element) => element.classList.remove('{HIGHLIGHT_CLASS}'),
            );

            const walker = () => document.createTreeWalker(container, NodeFilter.SHOW_TEXT);

            // The recorded line, as a node and an offset into it.
            //
            // The interactive Diagram view gives every line an element of its own carrying
            // its number (see diagintr), so the line is asked for directly and only the
            // column is counted -- across that one line's text nodes, which a connector or
            // an object name splits it into.
            //
            // The walk below is what this did before there were line elements, and is kept
            // for a Diagram rendered without them.  It cannot simply be used for both: the
            // newline that ends a line now sits in a hidden element of its own, so counting
            // newlines through the text nodes arrives at column 0 of the wanted line already
            // standing at the END of the previous line's newline node -- the right position,
            // in a node with no line text left in it to highlight.
            function seekWithinLine(lineElement, column) {{
                const crawl = document.createTreeWalker(lineElement, NodeFilter.SHOW_TEXT);
                for (let node = crawl.nextNode(); node; node = crawl.nextNode()) {{
                    const text = node.nodeValue;
                    const ends = text.indexOf("\\n");
                    const usable = ends === -1 ? text.length : ends;
                    if (column < usable || (column === usable && ends !== -1)) {{
                        return {{ node: node, offset: column }};
                    }}
                    column -= usable;
                    // The line ends in this node and the column is past the end of it, so it
                    // is not a column on this line at all.
                    if (ends !== -1) return null;
                }}
                return null;
            }}

            function seek(lineNumber, column) {{
                const lineElement = container.querySelector('[data-line="' + lineNumber + '"]');
                if (lineElement) return seekWithinLine(lineElement, column);
                let line = 0;
                const crawl = walker();
                for (let node = crawl.nextNode(); node; node = crawl.nextNode()) {{
                    const text = node.nodeValue;
                    if (!text.length) continue;
                    let from = 0;
                    while (from <= text.length) {{
                        if (line === lineNumber) {{
                            const rest = text.indexOf("\\n", from);
                            const end = rest === -1 ? text.length : rest;
                            if (column <= end - from) return {{ node: node, offset: from + column }};
                            column -= end - from;
                            // The line ends in this node and the column is past the end of
                            // it, so it is not a column on this line at all -- walking on
                            // into the next one would answer with a position on the wrong
                            // line, which is worse than not answering.
                            if (rest !== -1) return null;
                            break;   // The line continues in the next node.
                        }}
                        const next = text.indexOf("\\n", from);
                        if (next === -1) break;
                        line += 1;
                        from = next + 1;
                    }}
                }}
                return null;
            }}

            // The fallback: the first line holding one of the forms this object is drawn
            // as, preferring the earlier forms.  One walk, keeping the best so far, since a
            // later pattern matching an earlier line must not beat the first pattern
            // matching a later one -- "Test1" without its trailing space matches the line
            // drawn for "Test13", which is exactly what the ordering is there to settle.
            function search() {{
                let best = null;
                const crawl = walker();
                for (let node = crawl.nextNode(); node; node = crawl.nextNode()) {{
                    const text = node.nodeValue;
                    for (let rank = 0; rank < patterns.length; rank++) {{
                        if (best && best.rank <= rank) break;
                        const at = text.indexOf(patterns[rank]);
                        if (at >= 0) best = {{ rank: rank, node: node, offset: at, length: patterns[rank].length }};
                    }}
                    if (best && best.rank === 0) break;
                }}
                return best;
            }}

            // The interactive Diagram wraps every object's name in an element of its own
            // (see diagintr), and an element is an exact answer: no counting, no clamping,
            // and the whole name rather than as much of it as fits in one text node.  The
            // two below are what this did before there were elements, and remain the answer
            // for a Diagram rendered from a file an older run left on disk.
            if (anchor) {{
                const element = container.querySelector('[data-anchor="' + CSS.escape(anchor) + '"]');
                if (element) {{
                    element.classList.add('{HIGHLIGHT_CLASS}');
                    mtRevealAncestors(element);
                    element.scrollIntoView({{block: 'center', inline: 'nearest', behavior: 'auto'}});
                    for (let box = element.parentElement; box; box = box.parentElement) {{
                        if (box.scrollWidth > box.clientWidth) box.scrollLeft = 0;
                    }}
                    return true;
                }}
            }}

            let found = null;
            if (placement) {{
                const spot = seek(placement[0], placement[1]);
                if (spot) {{
                    // A length of zero is "the name could not be placed on the line after
                    // all" (see diagram._place): the line is still the right one, so all of
                    // it that is in this node is marked rather than nothing at all.
                    const rest = spot.node.nodeValue.indexOf("\\n", spot.offset);
                    const toEnd = (rest === -1 ? spot.node.nodeValue.length : rest) - spot.offset;
                    found = {{ node: spot.node, offset: spot.offset, length: placement[2] || toEnd }};
                }}
            }}
            if (!found) found = search();
            if (!found) return false;

            // Clamped to the node the span starts in.  A name is drawn as one unbroken run
            // of text, so this is the whole of it; the clamp is there for the case where a
            // connector span has split the line between the start and the end, where
            // highlighting the first part of the name is still an answer.
            const end = Math.min(found.offset + found.length, found.node.nodeValue.length);
            const span = document.createElement('span');
            span.className = '{HIGHLIGHT_CLASS}';
            const range = document.createRange();
            range.setStart(found.node, found.offset);
            range.setEnd(found.node, end);
            range.surroundContents(span);
            mtRevealAncestors(span);
            span.scrollIntoView({{block: 'center', inline: 'nearest', behavior: 'auto'}});
            // Back to column 1, as the connector jump buttons do: a wide diagram scrolled
            // sideways puts the reader in the middle of a line.
            for (let box = span.parentElement; box; box = box.parentElement) {{
                if (box.scrollWidth > box.clientWidth) box.scrollLeft = 0;
            }}
            return true;
        }})();
    """
