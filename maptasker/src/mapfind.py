"""mapfind: faceted search over the loaded configuration, rather than over rendered text."""

#! /usr/bin/env python3

#                                                                                       #
# mapfind: ask the loaded configuration a question, instead of scanning what was drawn.  #
#                                                                                        #
# The Search box in the Map and Diagram views searches the RENDERED OUTPUT: it crawls    #
# the text nodes of the view and highlights every place a string appears.  That is the   #
# right tool for "where does the word Spotify occur", and the wrong one for every        #
# question a large configuration actually raises -- "which Tasks perform an HTTP         #
# Request", "which Profiles are triggered by a Wifi state", "what touches the Launcher   #
# Scene".  Three things stand in the way of asking those of the rendered text:           #
#                                                                                        #
#   It can only match what was DRAWN.  An action's name is on the Map at detail level 2  #
#   and up and nowhere else, and a Diagram carries no actions at all, so the same        #
#   question gets a different answer -- or none -- depending on settings that have        #
#   nothing to do with it.                                                                #
#                                                                                        #
#   It cannot tell a match's KIND apart.  Searching "Spotify" finds the Profile that      #
#   waits for it, the Task that launches it, a variable holding its package name and any  #
#   Task whose name merely mentions it, in one undifferentiated list of line numbers.     #
#                                                                                        #
#   It cannot COMBINE.  "Profiles triggered by a Time that run a Task doing an HTTP       #
#   Request" is not a string, so it is not a search anybody can type.                     #
#                                                                                        #
# So this reads the XML instead.  Same contract as healthck.py and varxref.py:            #
# everything here reads PrimeItems.tasker_root_elements and nothing else, no GUI import,  #
# and the answers do not depend on what has been rendered, on the detail level, or on     #
# whether a Map has been run at all.  Identity comes from mapjump, so a result is         #
# clickable in exactly the way a health check finding is -- which is the whole point of   #
# returning a LIST of objects rather than highlighting text in place.                     #
#                                                                                        #
# What a query means                                                                     #
# ------------------                                                                     #
# Five facets, each of which may be left blank: action, trigger, app, scene, text -- plus #
# a Project the whole query can be narrowed to.  Two rules decide the result, and both    #
# are worth stating because between them they are the whole design:                       #
#                                                                                        #
#   1. Facets are ANDed, and a facet a kind of object cannot satisfy excludes that kind.  #
#      A Task has no trigger, so naming a trigger removes every Task from the answer.     #
#      This is what makes a single facet behave like the plain question it is ("app       #
#      Spotify" -> every Profile and every Task that names it) while combinations         #
#      narrow rather than blur.                                                            #
#                                                                                        #
#   2. A Profile also satisfies the action, app and scene facets through the Tasks it     #
#      runs, because a Profile's actions ARE its Tasks' actions -- there is nowhere else  #
#      for them to be.  Without this rule, trigger + action is a contradiction and        #
#      always answers nothing; with it, that pair asks the most useful question in the    #
#      whole feature.  To keep the same object from being reported twice over, an object  #
#      is only listed when it satisfies at least one facet ITSELF: "action X" alone       #
#      answers with Tasks, not with every Profile that happens to run one of them.        #
#                                                                                        #
# What it does not cover, so that a zero is never mistaken for an answer: the anonymous   #
# Tasks that live inside a Scene (healthck and varxref reach those through sceneedit;     #
# this does not yet), and any reference a configuration builds at run time -- an app or   #
# a Scene named through a %variable is indexed under the variable's own text, because     #
# that is all there is to go on.                                                          #
#                                                                                        #
# MIT License   Refer to https://opensource.org/license/mit                               #
#
from __future__ import annotations

import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from maptasker.src.actionc import action_codes
from maptasker.src.mapjump import (
    PROFILE,
    PROJECT,
    SCENE,
    TASK,
    Row,
    Scope,
    Target,
    actions_in_map_order,
    current_scope,
    describe,
    text_report,
)
from maptasker.src.maputils import append_to_filename
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import FIND_FILE, logger

if TYPE_CHECKING:
    import defusedxml.ElementTree  # Need for type hints

# The facets, as the ids the GUI keys its pulldowns by.  Strings rather than an Enum for
# the same reason mapjump's kinds are: they are read straight out of a Query built from
# selection widgets, and an Enum would only add a conversion at that boundary.
ACTION = "action"
TRIGGER = "trigger"
APP = "app"
SCENE_FACET = "scene"
TEXT = "text"

# Every facet, in the order the dialog offers them.
FACETS = (ACTION, TRIGGER, APP, SCENE_FACET)

# How each facet reads in the dialog and in the saved report.
FACET_LABELS = {
    ACTION: "Task action",
    TRIGGER: "Profile trigger",
    APP: "App",
    SCENE_FACET: "Scene",
    TEXT: "Text",
}

# How many results are handed back.  The same bargain the text search strikes at 200:
# a list nobody can read is not a better answer than a list that says how much it left
# out.  Higher than the text search's limit because these are objects rather than string
# occurrences -- there are far fewer of them, and each one is worth a row.
RESULT_LIMIT = 500

# Which of a Profile's children are contexts that TRIGGER it, as opposed to its own
# bookkeeping.  Tag-driven rather than a list of everything to ignore (varxref takes the
# other approach for the same XML, and pays for it whenever Tasker adds a child element):
# a context is one of these six and nothing else is.
_TIME_CONTEXTS = ("Time", "Day", "Loc")
_CODED_CONTEXTS = {"Event": "e", "State": "s"}
_APP_CONTEXT = "App"

# How a Time/Day/Location context reads as a facet value.  These carry no code, so unlike
# an Event or a State there is nothing finer to offer than the kind itself.
_PLAIN_TRIGGER_LABELS = {
    "Time": "Time",
    "Day": "Day",
    "Loc": "Location",
    _APP_CONTEXT: "Application",
}

# Create Scene, Show Scene, Hide Scene, Destroy Scene: the four whose Scene argument
# actionc.py labels "Name" rather than "Scene Name", so the derivation below cannot find
# them.  healthck's own four, repeated rather than imported -- importing them would make a
# search depend on the health check module, and the two are deliberately independent.
_SCENE_LIFECYCLE_CODES = {"46": "0", "47": "0", "48": "0", "49": "0"}


@dataclass(frozen=True)
class Choice:
    """One value a facet's pulldown offers, and how many places in the file carry it.

    The count is not decoration.  A pulldown built from Tasker's whole action table would
    run to 900 entries, nearly all of which match nothing in the file in front of the
    user; these are built from the configuration itself, so every entry offered leads
    somewhere and the count says how far.
    """

    value: str
    count: int

    @property
    def label(self) -> str:
        """The entry as the pulldown shows it: the value, then how many carry it."""
        return f"{self.value}  ({self.count})"


@dataclass(frozen=True)
class Query:
    """One question, as the dialog's five fields and its Project narrowing.

    Frozen, and empty-string rather than None for an unused facet, so that a Query can be
    built straight from the widgets' values and compared, logged or re-run as one value.
    """

    action: str = ""
    trigger: str = ""
    app: str = ""
    scene: str = ""
    text: str = ""
    project: str = ""

    @property
    def is_empty(self) -> bool:
        """Whether nothing at all was asked -- a Project on its own is a filter, not a question."""
        return not any((self.action, self.trigger, self.app, self.scene, self.text.strip()))

    def phrase(self) -> str:
        """The query as one line of prose, for the results header and the saved report."""
        parts = [
            f"{FACET_LABELS[facet]} '{value}'"
            for facet, value in (
                (ACTION, self.action),
                (TRIGGER, self.trigger),
                (APP, self.app),
                (SCENE_FACET, self.scene),
                (TEXT, self.text.strip()),
            )
            if value
        ]
        phrase = " and ".join(parts) if parts else "everything"
        return f"{phrase} in Project '{self.project}'" if self.project else phrase


@dataclass(frozen=True)
class Hit:
    """One object the query found, and why it counts as an answer.

    'target' is the identity mapjump jumps to, refined as far as the match goes -- a Task
    found by one of its actions carries that action's number, so the click lands on the
    action line rather than on the Task's heading.  'detail' says which facet matched and
    what it matched on, because a list of object names alone leaves the user to work out
    what a row is doing in the answer.
    """

    target: Target
    detail: str
    # The Project the object sits in, for grouping.  Carried alongside rather than read
    # off the Target: a Project's own Target holds no project (that would print "Project
    # 'Home' > Project 'Home'"), so the Target cannot answer this for every kind.
    project: str = ""

    @property
    def where(self) -> str:
        """The object's location, worded exactly as the health check words its own."""
        return self.target.label


@dataclass
class _Action:
    """One Task action, reduced to what a query can ask about."""

    number: int  # 1-based, in the order the Map numbers them
    name: str  # "Perform Task", or "code 1234" for one Tasker has added since actionc.py
    apps: list[str] = field(default_factory=list)
    scenes: list[str] = field(default_factory=list)
    text: str = ""  # label and argument text, lower cased, for the free-text facet
    code: str = ""  # the raw <code>, for a caller that needs to match on it exactly
    # The element this record was reduced from.  Nothing in this module reads it -- a
    # query tests the reduced facts, which is the point of reducing them -- but mapswap
    # rewrites the actions a query finds, and a second walk written to go and fetch the
    # elements again would be a second definition of "the actions of a Task" to keep in
    # step with this one.  Optional so that a hand-built _Action in a test need not
    # supply it.
    element: defusedxml.ElementTree.Element | None = None


@dataclass
class _Object:
    """One Project/Profile/Task/Scene, with everything the five facets need to test it.

    One record per object rather than a table per facet: a query ANDs its facets over a
    single object, so the object is what the loop wants to hold, and the facet catalogs
    below are counted off these rather than gathered separately (which is what kept the
    pulldowns and the results from ever disagreeing about what is in the file).
    """

    target: Target
    kind: str
    name: str
    project: str
    text: str = ""  # name and everything inside it, lower cased
    actions: list[_Action] = field(default_factory=list)
    triggers: list[tuple[str, str]] = field(default_factory=list)  # (facet value, detail)
    apps: list[str] = field(default_factory=list)  # named by the object itself
    scenes: list[str] = field(default_factory=list)  # named by the object itself
    task_ids: list[str] = field(default_factory=list)  # Profiles: the Tasks they run


@dataclass
class FindIndex:
    """Everything in the loaded configuration a query can be asked about.

    Built in one pass and handed back to the caller to hold, because the GUI asks it two
    different things: what to offer in the pulldowns (once, when the dialog opens) and
    what matches (each time Find is pressed).  Rebuilding it per query would re-walk every
    action in the file for every keystroke's worth of impatience.
    """

    objects: list[_Object] = field(default_factory=list)
    by_task_id: dict[str, _Object] = field(default_factory=dict)
    # {facet: {value: how many places carry it}} -- the pulldowns, and nothing else.
    catalog: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    projects: list[str] = field(default_factory=list)
    # What the pass could not resolve, so the report can qualify its own answers rather
    # than let a zero read as "there are none".
    variable_apps: int = 0
    variable_scenes: int = 0
    # What the index was limited to when it was built, so a report can say so rather than
    # let an empty answer read as "there are none in this configuration".
    scope: Scope = field(default_factory=Scope)

    def choices(self, facet: str) -> list[Choice]:
        """A facet's pulldown entries, commonest first and alphabetical within a count.

        Commonest first because the reason to open this dialog on a 200-Project file is
        rarely to look for the one action used once; alphabetical underneath so that two
        values used the same number of times do not swap places between runs.
        """
        counts = self.catalog.get(facet, Counter())
        return [Choice(value, count) for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


# ##################################################################################
# Reading the XML.
# ##################################################################################
def _element_text(element: defusedxml.ElementTree.Element, tag: str) -> str:
    """The text of a child element, stripped, or "" if it is missing or empty."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _split_ids(element: defusedxml.ElementTree.Element, tag: str) -> list[str]:
    """A Project's <pids>/<tids>/<scenes> as a list.

    The filter on empty items matters: Tasker writes an empty list as an empty element,
    and "".split(",") is [""] -- which would claim the Project owns an object whose name
    is the empty string.
    """
    text = _element_text(element, tag)
    return [item.strip() for item in text.split(",") if item.strip()] if text else []


def _project_membership(tag: str) -> dict[str, str]:
    """{member: owning Project name} for one of a Project's comma-separated member lists.

    In one pass, rather than by asking maputils which Project owns each object in turn --
    that walks every Project per question, which on a file with 200 of them is the whole
    scan done over again for every Task in it.
    """
    owners = {}
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        for member in _split_ids(project["xml"], tag):
            owners[member] = project_name
    return owners


def _action_name(code: str) -> str:
    """What Tasker calls the action with this code.

    "code NNN" for one that is not in actionc.py -- a plugin from a release newer than
    the table.  Deliberately still offered as a facet value rather than dropped: an
    unrecognised action is exactly the kind of thing somebody opens this dialog to find,
    and the code is what the Map prints for it too.
    """
    entry = action_codes.get(f"{code}t")
    return entry.name if entry else f"code {code}"


def _trigger_name(tag: str, code: str) -> str:
    """A Profile context as one facet value: "Event: Wifi Connected", "State: ...", "Time"."""
    entry = action_codes.get(f"{code}{_CODED_CONTEXTS[tag]}")
    return f"{tag}: {entry.name if entry else f'code {code}'}"


def _app_labels(element: defusedxml.ElementTree.Element) -> list[str]:
    """Every app an <App> element names, as the label Tasker shows for it.

    Both shapes.  A Task action's App argument holds one app in <label>/<appPkg>; a
    Profile's App context holds any number, numbered <label0>/<pkg0>, <label1>/<pkg1>.
    The label is preferred over the package because that is the name the user chose the
    app by -- 'Maps', not 'com.google.android.apps.maps' -- and the package is the
    fallback for an entry that carries no label at all.

    A name holding a '%variable' is kept rather than dropped: '%LastMusicApp' is a real
    entry in the file and the honest answer to "which apps does this configuration
    reference" is that this one is decided on the device.  _index_action counts those
    separately so the report can say so.
    """
    labels = []
    for child in element:
        if child.tag.startswith("label"):
            text = (child.text or "").strip()
            if text:
                labels.append(text)
    if labels:
        return labels
    # No label at all: the package is at least an identity, and is what Tasker falls back
    # to showing for an app it can no longer resolve to an installed one.
    packages = []
    for child in element:
        if child.tag.startswith(("pkg", "appPkg")):
            text = (child.text or "").strip()
            if text:
                packages.append(text)
    return packages


def _scene_name_args() -> dict[str, str]:
    """{action code: arg id} for every action that names a Scene.

    Derived from the action table rather than listed, so a Scene action added in a later
    Tasker release is covered when actionc.py is regenerated -- the twenty-odd "Element
    ..." actions all declare an argument literally named "Scene Name".  The four
    lifecycle actions that do not are added by hand above.
    """
    codes = dict(_SCENE_LIFECYCLE_CODES)
    for key, action in action_codes.items():
        if not key.endswith("t"):  # 'e'/'s' keys are Profile events and states, not actions.
            continue
        for argument in action.args or ():
            if argument.arg_name == "Scene Name":
                codes[key[:-1]] = argument.arg_id
                break
    return codes


def _string_arguments(action: defusedxml.ElementTree.Element) -> dict[str, str]:
    """{arg id: text} for one action's arguments.

    Matched on the "sr" attribute rather than on child order, which Tasker does not
    guarantee -- the same way taskedit.py, healthck.py and varxref.py each reach an
    argument.  Both shapes an argument can take are read: a text argument is
    <Str sr="argN">, and an argument Tasker expects a number in holds
    <Int sr="argN"><var>%Volume</var></Int> when a variable has been bound to it.
    """
    arguments = {}
    for child in action.findall("Str"):
        sr = child.attrib.get("sr", "")
        if sr.startswith("arg") and child.text:
            arguments[sr[3:]] = child.text
    for child in action.findall("Int"):
        sr = child.attrib.get("sr", "")
        bound = child.find("var")
        if sr.startswith("arg") and bound is not None and bound.text:
            # setdefault, not assignment: an argument is one shape or the other, and the
            # <Str> reading is the one to keep if a file ever carries both.
            arguments.setdefault(sr[3:], bound.text)
    return arguments


# ##################################################################################
# The scan.
# ##################################################################################
def _index_action(
    index: FindIndex,
    action_element: defusedxml.ElementTree.Element,
    number: int,
    scene_args: dict[str, str],
) -> _Action:
    """Reduce one action to the facts the facets test, and count them into the catalogs."""
    code = _element_text(action_element, "code")
    record = _Action(number=number, name=_action_name(code), code=code, element=action_element)
    index.catalog[ACTION][record.name] += 1

    arguments = _string_arguments(action_element)
    for app_element in action_element.findall("App"):
        for label in _app_labels(app_element):
            record.apps.append(label)
            index.catalog[APP][label] += 1
            if "%" in label:
                index.variable_apps += 1

    scene_argument = scene_args.get(code)
    if scene_argument is not None:
        name = (arguments.get(scene_argument) or "").strip()
        if name and "%" in name:
            # Decided on the device, so it names no Scene this scan can resolve.  Counted
            # rather than guessed at, the same way healthck qualifies UNUSED-SCENE.
            index.variable_scenes += 1
        elif name:
            record.scenes.append(name)
            index.catalog[SCENE_FACET][name] += 1

    # The free-text facet searches an action's label and its arguments -- which is what
    # the rendered Map shows of it, so a text query answers what the eye would find, only
    # attributed to the action rather than to a line number.
    pieces = [_element_text(action_element, "label"), record.name, *arguments.values()]
    record.text = " ".join(piece for piece in pieces if piece).lower()
    return record


def _index_tasks(index: FindIndex, project_of_task: dict[str, str], scope: Scope) -> None:
    """Walk every Task and every action in it."""
    scene_args = _scene_name_args()
    for task_id, task in PrimeItems.tasker_root_elements["all_tasks"].items():
        if not scope.allows(TASK, task_id):
            continue
        project = project_of_task.get(task_id, "")
        record = _Object(
            target=Target(kind=TASK, key=task_id, name=task["name"], project=project),
            kind=TASK,
            name=task["name"],
            project=project,
        )
        # actions_in_map_order, not findall order: Tasker writes act0, act1, act10, act11,
        # act2 ... and the Map renumbers them numerically before printing.  A hit reporting
        # "action 8" that the Map calls action 3 is a wrong answer in the report's own prose,
        # never mind in the jump.
        for number, action_element in enumerate(actions_in_map_order(task["xml"]), start=1):
            record.actions.append(_index_action(index, action_element, number, scene_args))
        record.apps = [app for action in record.actions for app in action.apps]
        record.scenes = [scene for action in record.actions for scene in action.scenes]
        record.text = " ".join([task["name"].lower(), *(action.text for action in record.actions)])
        index.objects.append(record)
        index.by_task_id[task_id] = record


def _index_profiles(index: FindIndex, project_of_profile: dict[str, str], scope: Scope) -> None:
    """Walk every Profile: its contexts, the apps they name, and the Tasks it runs."""
    for profile_id, profile in PrimeItems.tasker_root_elements["all_profiles"].items():
        if not scope.allows(PROFILE, profile_id):
            continue
        project = project_of_profile.get(profile_id, "")
        record = _Object(
            target=Target(kind=PROFILE, key=profile_id, name=profile["name"], project=project),
            kind=PROFILE,
            name=profile["name"],
            project=project,
        )
        element = profile["xml"]
        for child in element:
            if child.tag in _CODED_CONTEXTS:
                value = _trigger_name(child.tag, _element_text(child, "code"))
                record.triggers.append((value, value))
                index.catalog[TRIGGER][value] += 1
            elif child.tag in _TIME_CONTEXTS:
                value = _PLAIN_TRIGGER_LABELS[child.tag]
                record.triggers.append((value, value))
                index.catalog[TRIGGER][value] += 1
            elif child.tag == _APP_CONTEXT:
                labels = _app_labels(child)
                value = _PLAIN_TRIGGER_LABELS[_APP_CONTEXT]
                record.triggers.append((value, f"{value}: {', '.join(labels)}" if labels else value))
                index.catalog[TRIGGER][value] += 1
                for label in labels:
                    record.apps.append(label)
                    index.catalog[APP][label] += 1
                    if "%" in label:
                        index.variable_apps += 1

        # <mid0>/<mid1> are the entry and exit Tasks.  Numbered children rather than a
        # list, so they are read by prefix the same way the app labels above are.
        record.task_ids = [
            (child.text or "").strip()
            for child in element
            if child.tag.startswith("mid") and (child.text or "").strip()
        ]
        record.text = " ".join([profile["name"].lower(), *(detail.lower() for _, detail in record.triggers)])
        index.objects.append(record)


def _index_scenes(index: FindIndex, project_of_scene: dict[str, str], scope: Scope) -> None:
    """Walk every Scene.  A Scene answers the Scene facet by BEING the Scene asked for.

    Its elements are read for the free-text facet only -- every <Str> in the Scene, which
    covers an element's label, its text and the Task names its taps fire.  What is NOT
    read here is the inline anonymous Task a Scene element can carry, so an action inside
    one is not found by the action facet; the module comment says so, and the report
    repeats it, so a zero is never mistaken for "there are none".
    """
    for scene_name, scene in PrimeItems.tasker_root_elements["all_scenes"].items():
        if not scope.allows(SCENE, scene_name):
            continue
        project = project_of_scene.get(scene_name, "")
        record = _Object(
            target=Target(kind=SCENE, key=scene_name, name=scene["name"] or scene_name, project=project),
            kind=SCENE,
            name=scene["name"] or scene_name,
            project=project,
            scenes=[scene_name],
        )
        index.catalog[SCENE_FACET][scene_name] += 1
        strings = [child.text for child in scene["xml"].iter() if child.tag == "Str" and child.text]
        record.text = " ".join([scene_name.lower(), *(text.lower() for text in strings)])
        index.objects.append(record)


def _index_projects(index: FindIndex, scope: Scope) -> None:
    """Walk every Project.  A Project answers for the Scenes it lists and for its own name.

    It is deliberately NOT made to answer for everything it contains: on a file with 200
    Projects, a query for an app would otherwise return every Project that has any Task
    mentioning it, which is a list of Projects rather than an answer about the app.  The
    Tasks and Profiles themselves are in the results already.
    """
    for project_name, project in PrimeItems.tasker_root_elements["all_projects"].items():
        if not scope.allows(PROJECT, project_name):
            continue
        index.projects.append(project_name)
        scenes = _split_ids(project["xml"], "scenes")
        index.objects.append(
            _Object(
                target=Target(kind=PROJECT, key=project_name, name=project_name),
                kind=PROJECT,
                name=project_name,
                project=project_name,
                scenes=scenes,
                text=" ".join([project_name.lower(), *(scene.lower() for scene in scenes)]),
            ),
        )


def build_index() -> FindIndex:
    """Read the loaded configuration into everything a query needs, in one pass.

    Limited to what the app is DISPLAYING (mapjump.current_scope): with a single Project,
    Profile, Task or Scene selected, everything outside it is left out of the index
    entirely, rather than filtered out when a query is answered.  That is the difference
    between the pulldowns agreeing with the results and disagreeing with them -- the facet
    catalogs are counted off these same records, so a scoped run offers "Flash  (11)" and
    then finds eleven.

    Safe to call with nothing loaded: the tables are empty, the index is empty, and every
    query over it answers nothing -- but the GUI checks first so it can say why.
    """
    scope = current_scope()
    index = FindIndex(scope=scope)
    _index_projects(index, scope)
    _index_profiles(index, _project_membership("pids"), scope)
    _index_tasks(index, _project_membership("tids"), scope)
    _index_scenes(index, _project_membership("scenes"), scope)
    index.projects.sort(key=str.lower)
    logger.debug(
        f"mapfind index: {len(index.objects)} objects, "
        f"{len(index.catalog[ACTION])} actions, {len(index.catalog[TRIGGER])} triggers, "
        f"{len(index.catalog[APP])} apps, {len(index.catalog[SCENE_FACET])} scenes",
    )
    return index


# ##################################################################################
# Asking the question.
# ##################################################################################
def _action_hit(record: _Object, wanted: str) -> tuple[bool, str, Target]:
    """Whether this object performs the named action, and where the first one is.

    The target comes back refined to that action's number, so the Map jump lands on the
    action's own line rather than on the Task's heading -- which for a Task of 200 actions
    is the difference between an answer and a starting point.
    """
    for action in record.actions:
        if action.name == wanted:
            return True, f"action {action.number}: {action.name}", record.target.at_action(action.number)
    return False, "", record.target


def _matches_directly(record: _Object, query: Query) -> tuple[bool, list[str], Target]:
    """Whether the object itself satisfies every facet named, and how it does so.

    Returns the details in the order the facets were asked, so a row reads the way the
    question was put.  The Target comes back refined by whichever facet could refine it.
    """
    details: list[str] = []
    target = record.target

    if query.action:
        found, detail, target = _action_hit(record, query.action)
        if not found:
            return False, [], record.target
        details.append(detail)

    if query.trigger:
        detail = next((detail for value, detail in record.triggers if value == query.trigger), "")
        if not detail:
            return False, [], record.target
        details.append(detail)

    if query.app:
        if query.app not in record.apps:
            return False, [], record.target
        details.append(f"app: {query.app}")

    if query.scene:
        if query.scene not in record.scenes:
            return False, [], record.target
        details.append("the Scene itself" if record.kind == SCENE else f"Scene: {query.scene}")

    text = query.text.strip().lower()
    if text:
        if text not in record.text:
            return False, [], record.target
        details.append(f"text: '{query.text.strip()}'")

    return True, details, target


def _matches_through_tasks(record: _Object, query: Query, index: FindIndex) -> tuple[bool, list[str]]:
    """Whether the Tasks a Profile runs satisfy the facets the Profile itself cannot.

    Rule 2 of the module comment: a Profile's actions are its Tasks' actions.  Only the
    three facets a Task can answer are climbed -- a Task has no trigger, and the text
    facet is left alone deliberately, since "any Profile one of whose Tasks mentions
    'battery' anywhere" is the vague question this whole module exists to replace.
    """
    details = []
    for facet, value in ((ACTION, query.action), (APP, query.app), (SCENE_FACET, query.scene)):
        if not value:
            continue
        for task_id in record.task_ids:
            task = index.by_task_id.get(task_id)
            if task is None:
                continue
            found = (
                _action_hit(task, value)[0]
                if facet == ACTION
                else (value in task.apps if facet == APP else value in task.scenes)
            )
            if found:
                details.append(f"{describe('Task', task.name, task_id)} -- {FACET_LABELS[facet]} '{value}'")
                break
        else:
            return False, []
    return True, details


def run_query(index: FindIndex, query: Query, limit: int = RESULT_LIMIT) -> tuple[list[Hit], int]:
    """Answer one question.  Returns (the hits to show, how many there were in all).

    Empty for an empty query rather than "everything": a dialog opened and pressed with
    nothing chosen is a slip, and answering it with all 3,000 objects in the file buries
    the dialog that would let the user correct it.
    """
    if query.is_empty:
        return [], 0

    hits: list[Hit] = []
    for record in index.objects:
        if query.project and record.project != query.project:
            continue
        direct, details, target = _matches_directly(record, query)
        if direct:
            hits.append(Hit(target=target, detail="; ".join(details), project=record.project))
            continue
        # Not directly.  A Profile may still qualify through its Tasks -- but only if it
        # answers at least one facet itself, or every Profile in the file would follow its
        # Tasks into an answer about actions (see rule 2).
        if record.kind != PROFILE or not record.triggers:
            continue
        own = Query(trigger=query.trigger, text=query.text, project=query.project)
        if own.is_empty:
            continue
        satisfied, own_details, _ = _matches_directly(record, own)
        if not satisfied:
            continue
        through, task_details = _matches_through_tasks(record, query, index)
        if through and task_details:
            hits.append(
                Hit(
                    target=record.target,
                    detail="; ".join([*own_details, *task_details]),
                    project=record.project,
                ),
            )

    # Grouped by Project and then by kind, so the answer reads like the configuration is
    # organised rather than like the order the tables happen to be in.  _KIND_ORDER puts a
    # Project ahead of the Profiles in it and those ahead of their Tasks.
    hits.sort(key=lambda hit: (hit.project.lower(), _KIND_ORDER.get(hit.target.kind, 9), hit.where.lower()))
    return hits[:limit], len(hits)


# Projects before the Profiles in them, Profiles before their Tasks, Scenes last.
_KIND_ORDER = {PROJECT: 0, PROFILE: 1, TASK: 2, SCENE: 3}


# ##################################################################################
# The report, for saving what the results list shows.
# ##################################################################################
def report_rows(query: Query, hits: list[Hit], total: int, index: FindIndex) -> list[Row]:
    """The results as report rows -- the same Row the health check builds.

    Rows rather than text so the saved file and anything rendered from these are the one
    report, and so every row keeps the Target that makes it clickable.
    """
    when = datetime.now().strftime("%B %d, %Y  %H:%M:%S")  # noqa: DTZ005
    shown = f"{len(hits)} of {total}" if total > len(hits) else str(total)
    rows = [
        Row("MapTasker Find"),
        Row(f"Run {when}"),
        Row(""),
        Row(f"Looking for: {query.phrase()}"),
        Row(f"Found: {shown} object(s)"),
        Row("=" * 100),
        Row(""),
    ]
    project = None
    for hit in hits:
        if hit.project != project:
            leading = [Row("")] if project is not None else []
            project = hit.project
            rows += [*leading, Row(f"Project '{project}'" if project else "In no Project"), Row("-" * 60)]
        rows.append(Row(f"  {hit.where}", hit.target))
        if hit.detail:
            rows.append(Row(f"      {hit.detail}"))
    if not hits:
        rows.append(Row("  Nothing in the loaded configuration answers this."))
    return [*rows, Row(""), *(Row(line) for line in _limitations(index))]


def _limitations(index: FindIndex) -> list[str]:
    """What this scan could not resolve, said in the report rather than left as a zero."""
    notes = [
        "What this search does and does not reach:",
        "  Read from the loaded XML, not from the rendered Map or Diagram -- the answer does",
        "  not change with the detail level or with whether a Map has been run.",
        "  The anonymous Tasks that live inside a Scene are not scanned for actions; a Scene is",
        "  searched by name and by the text of its elements.",
    ]
    # Said first among the qualifications, and said whether or not anything was found: an
    # empty answer from a scoped search means "none in here", and read as "none in this
    # configuration" it is the wrong answer to a question the user did not ask.
    if not index.scope.is_everything:
        notes.insert(
            1,
            f"  Limited to {index.scope.phrase}, which is what the app is displaying.  Nothing outside"
            f" it was searched.",
        )
    if index.variable_apps:
        notes.append(
            f"  {index.variable_apps} app reference(s) name the app through a %variable, so the app is",
        )
        notes.append("  decided on the device and is listed under the variable's own text.")
    if index.variable_scenes:
        notes.append(
            f"  {index.variable_scenes} action(s) name a Scene through a %variable and cannot be attributed",
        )
        notes.append("  to one, so a Scene search may under-report.")
    return notes


def write_find_report(rows: list[Row]) -> str:
    """Write the results to a timestamped file in the current runtime directory.

    Returns the file name written, or "" if the write failed -- the results are on screen
    either way, and a search whose save went wrong is still a search worth showing.
    """
    stamp = datetime.now().strftime("_%m-%d-%Y_%H-%M-%S")  # noqa: DTZ005
    file_name = append_to_filename(FIND_FILE, stamp)
    if not file_name:
        return ""
    try:
        with open(os.path.join(os.getcwd(), file_name), "w", encoding="utf-8") as output_file:
            output_file.write(text_report(rows))
    except OSError as error:
        logger.error(f"Find report could not be written: {error}")
        return ""
    return file_name
