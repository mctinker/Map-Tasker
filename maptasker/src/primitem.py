"""Prime items which are used throughout MapTasker (globals)."""

#! /usr/bin/env python3

#                                                                                      #
# primitem = intialize PrimeItems which are used throughout MapTasker (globals).       #
#                                                                                      #
# complete source code of licensed works and modifications which include larger works  #
# using a licensed work under the same license. Copyright and license notices must be  #
# preserved. Contributors provide an express grant of patent rights.                   #
#                                                                                      #
# Primary Items = global variables used throughout MapTasker
#
# PrimeItems is an instance of RunState, which holds the attributes listed below.  Code that
# has been converted takes a RunState as a parameter (the Project, Profile, Task, Scene and Action
# output, mapjump, and the Diagram code so far) and so can be run against one of its own; code that has not still reads the
# PrimeItems instance, which a real run passes in.  See RunState.
#
# Set up an initial empty dictionary of primary items used throughout this project
#  xml_tree = main xml element of our Tasker xml tree
#  xml_root = root xml element of our Tasker xml tree
#  program_arguments = runtime arguments entered by user and parsed: a ProgramArguments.
#    See initparg.py for every argument, its type and its default.
#  colors_to_use = colors to use in the output
#  tasker_root_elements = root elements for all Projects/Profiles/Tasks/Scenes
#  output_lines = class for all lines added to output thus far
#  found_named_items = names/found-flags for single (if any) Project/Profile/Task/Scene
#  file_to_get = file object/name of Tasker backup file to read and parse
#  grand_totals = Total count of Projects/Profiles/Named Tasks Unnamed Task etc.
#  task_count_for_profile = number of Tasks in the specific Profile for Project
#    being processed
#  named_task_count_total = number of named Tasks for Project being processed
#  task_count_unnamed = number of unnamed Tasks for Project being processed
#  task_count_no_profile = number of Profiles in Project being processed.
#  directory_items = if displaying a directory then this is a dictionary of items
#    for the directory
#  name_list = list of names of Projects/Profiles/Tasks/Scenes found thus far
#  displaying_named_tasks_not_in_profile = True if we are displaying False if not
#  mono_fonts = the font pulldown's choices, {font name: label shown}
#  grand_totals = used for trcaking number of Projects/Profiles/Tasks/Scenes
#  tasker_root_elements points to our root xml for Projects/Profiles/Tasks/Scenes
#  directories = points to our directory items if we are displaying a directory
#  variables = Tasker variables.
#  current_project = current Project being processed
#  last_run = date of last run (set by restore_settings)
#  slash = backslash for Windows or forward slash for OS X and Linux.
#
#   return
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from maptasker.src import caches
from maptasker.src.initparg import ArgumentFields, ProgramArguments
from maptasker.src.sysconst import (
    ANTHROPIC_MODELS,
    DEEPSEEK_MODELS,
    GEMINI_MODELS,
    LLAMA_MODELS,
    NOW_TIME,
    OPENAI_MODELS,
    VIEW_LIMIT_DEFAULT,
)

if TYPE_CHECKING:
    from maptasker.src.runcfg import RunConfig

# The single-named-item selectors: display only this one Project, or Profile, or Task,
# or Scene.  Each entry maps the program_arguments key holding the requested name to its
# found_named_items flag and the label used in messages.  Adding a fifth single item
# starts here -- found_named_items and its reset are both built off this tuple, and
# get_single_item_requested/get_single_item_not_found/is_single_item_found below walk it.
SINGLE_ITEM_SELECTORS = (
    ("single_project_name", "single_project_found", "Project"),
    ("single_profile_name", "single_profile_found", "Profile"),
    ("single_task_name", "single_task_found", "Task"),
    ("single_scene_name", "single_scene_found", "Scene"),
)


def initial_found_named_items() -> dict:
    """
    Build a fresh found_named_items dictionary, every flag False.

    Returns:
        dict: {"single_project_found": False, ...} -- one entry per single item.
    """
    return {found_key: False for _, found_key, _ in SINGLE_ITEM_SELECTORS}


# The next two are functions rather than module-level constants on purpose: each caller
# needs its *own* dictionary (and, for directory_items, its own lists), since these get
# mutated in place -- appended to and cleared -- throughout a run.  A shared constant
# would alias every "reset" back onto the same object.
def initial_grand_totals() -> dict:
    """
    Build a fresh grand_totals dictionary, every count zero.

    Returns:
        dict: the running Project/Profile/Task/Scene counts for a run.
    """
    return {
        "projects": 0,
        "profiles": 0,
        "unnamed_tasks": 0,
        "named_tasks": 0,
        "scenes": 0,
    }


def initial_directory_items() -> dict:
    """
    Build a fresh directory_items dictionary, every hyperlink list empty.

    Returns:
        dict: the per-item-type directory hyperlink lists for a run.
    """
    return {
        "current_item": "",
        "projects": [],
        "profiles": [],
        "tasks": [],
        "scenes": [],
    }


def initial_tasker_root_elements() -> dict:
    """
    Build an empty tasker_root_elements dictionary -- no Tasker objects loaded.

    This is the "nothing loaded yet" shape.  taskerd.get_the_xml_data builds the same
    set of keys with the parsed XML in them, so a key added here needs adding there too
    (tests/test_primitem.py checks that the two agree).

    Returns:
        dict: the root xml element tables for all Projects/Profiles/Tasks/Scenes.
    """
    return {
        "all_projects": {},
        "all_profiles": {},
        "all_profiles_by_name": {},
        "all_scenes": {},
        "all_tasks": {},
        "all_tasks_by_name": {},
        "all_services": [],
    }


class RunState:
    """Everything one run holds: the loaded backup, the output being built, the counters.

    PrimeItems, below, is the one the program runs on.  A function that is handed a RunState
    reads and writes only that, so it can be exercised -- or two runs kept apart -- without
    the global: build a RunState() and pass it in.  What a function has not been converted to
    take as a parameter still reads PrimeItems, so a fresh RunState is only a complete run
    for code that has been.

    Every attribute is set per instance, in __init__, so no two RunStates share a dict, list
    or set.
    """

    def __init__(self) -> None:
        """Give this instance its own copy of every attribute, at its declared default."""

        self.ai = {
            "do_ai": False,
            "ai_name": "",
            "model": "",
            "output_lines": [],  # Saved output results if doing an AI run.
            "api_key": "",
            "openai_key": "",
            "anthropic_key": "",
            "deepseek_key": "",
            "gemini_key": "",
            "openai_models": OPENAI_MODELS,
            "anthropic_models": ANTHROPIC_MODELS,
            "deepseek_models": DEEPSEEK_MODELS,
            "gemini_models": GEMINI_MODELS,
            "llama_models": LLAMA_MODELS,
        }
        self.xml_tree = None
        self.xml_root = None
        self.program_arguments: ProgramArguments = ProgramArguments()
        self.colors_to_use: dict = {}
        self.output_lines = None
        self.file_to_get = ""
        self.file_to_use = ""
        self.task_count_for_profile = 0
        self.displaying_named_tasks_not_in_profile = False
        self.error_code = 0
        self.error_msg = ""
        # Whether the GUI adds "with return code N" to error_msg.  False for an error whose code
        # says nothing to the user (a library that is not installed); see error.error_handler.
        self.error_show_code = True
        self.view_limit_msg = (
            ""  # Set by bildhtml.write_out_the_file when output hits view_limit; read by the Map view's message field.
        )
        # The Diagram view's equivalent: set by diagram.check_limit when the diagram is cut short at
        # the view limit, read by the Diagram view's message field.  Kept separate from
        # view_limit_msg so a truncated Map cannot leave its message showing on an untruncated
        # Diagram (the two views are built from separate runs).
        self.diagram_limit_msg = ""
        # How many output lines went into the Map now on disk.  Set by bildhtml wherever that
        # file comes from -- the build that wrote it, or mapcache when an unchanged Map is
        # shown again -- and read by the GUI to say whether the view limit cut it short.  The
        # count cannot be taken from output_lines at that point: those are emptied after every
        # build, and a Map that was not rebuilt never filled them in the first place.
        self.map_output_line_count = 0
        self.found_named_items: dict = initial_found_named_items()
        self.grand_totals: dict = initial_grand_totals()
        self.directory_items: dict = initial_directory_items()
        # Every mapjump anchor id written into the Map so far this run.  An id may appear in a
        # document only once, and a Task listed by two Profiles (or by a Profile and again in
        # "Tasks not in any Profile") is output twice -- so the second sighting is written
        # without an anchor and a jump lands on the Task's first appearance.  Emptied wherever
        # directory_items is, and for the same reason: both describe one run's output, and
        # refresh_our_output throws that output away and starts it again mid-run.
        self.emitted_anchors: set = set()
        # Where each object ended up in the Diagram that was last built: {mapjump anchor id:
        # (line, column, length)}, in the coordinates of the rendered diagram file, with column
        # and length counted in UTF-16 code units so the browser can use them as given.  Filled
        # by diagram.network_map; read by mapjump.diagram_placement so a Find result or a report
        # finding can be taken to the Diagram as precisely as it is taken to the Map.  Empty
        # until a Diagram has been built, which is the same thing as "no Diagram to jump into".
        self.diagram_anchors: dict = {}
        # The same, mid-build and before the positions are final: {anchor: (row, drawn text)}
        # in netmap_output's own line numbering.  Lives on PrimeItems rather than in diagram.py
        # only so that it is emptied wherever the rest of a run's output is.
        self.diagram_object_seeds: dict = {}
        # Which object each of those anchors IS: {anchor: mapjump.Target}.  Held apart from the
        # positions because a position is remapped four times before the diagram is written and
        # an identity never is -- see diagram._record.  Read once, when the interactive Diagram
        # view's model is assembled, and emptied straight afterwards.
        self.diagram_object_targets: dict = {}
        # Every drawing of every object, not just the first: [(anchor, row, drawn text)] while
        # the diagram is being built, and [(anchor, line, column, length)] once it is written.
        # diagram_anchors above answers "where does a jump to this object land"; this answers
        # "which pieces of the drawing ARE this object", which is a different question wherever
        # the Diagram draws one twice -- a Task run by two Profiles, or fired by a Scene as well.
        self.diagram_object_placements: list = []
        # Every call the Diagram drew a connector for: {call index: {caller_row, called_row,
        # caller_name, called_name, project}}, in the rendered file's line numbering by the time
        # the diagram is finished.  The call index is what each connector seed carries, which is
        # how a run of box-drawing characters is traced back to the two Tasks it joins.
        self.diagram_call_edges: dict = {}
        # Which calls each finished connector belongs to: {connector group id: [call index, ...]}.
        # Filled by diagram.compute_diagram_connector_groups, as the other half of the same fact.
        self.diagram_connector_calls: dict = {}
        # The whole of what the interactive Diagram view acts on -- nodes, foldable Project
        # regions and call edges, all in the rendered file's coordinates.  Assembled by
        # diagintr.build_model once the diagram is written; read by the view when it renders.
        self.diagram_model: dict = {}
        # The flowchart of the one Task the user last asked for, as mapjump Rows -- see
        # taskflow.flowchart.  Held here rather than handed to the view because the Task Flow
        # view opens in its own browser window, and a popped-out page is built from a URL and
        # is passed nothing (see rungui.popout_view, which reaches the Diagram's file the same
        # way).  Emptied by a reset, with the rest of a run's state, because it describes a
        # configuration that is about to be replaced -- but not when a Diagram is drawn, which
        # leaves the flowchart as it was (it is not in DIAGRAM_ATTRIBUTES).
        self.taskflow_rows: list = []
        self.tasker_root_elements: dict = initial_tasker_root_elements()
        # The highest Task/Profile id in the file as it was loaded, set by taskerd.get_the_xml_data.
        # New ids are kept well above it -- see taskedit.NEW_OBJECT_ID_HEADROOM.  0 = nothing loaded.
        self.loaded_highest_object_id = 0
        self.directories: list = []
        self.variables: dict = {}
        self.current_project = ""
        self.last_run = NOW_TIME
        self.mono_fonts: dict = {}
        self.slash = "/"
        self.task_action_warnings: dict = {}
        self.task_count_unnamed = 0
        self.task_count_no_profile = 0
        self.named_task_count_total = 0
        # Scenes in the Project being processed (scenes.py), for that Project's totals line.
        self.scene_count = 0
        # The HTML heading at the top of the Map (frontmtr.py).
        self.heading = ""
        # How many output lines the Map is cut off at (bildhtml.write_out_the_file).  The GUI sets
        # it from its own view limit before every build.
        self.view_limit = VIEW_LIMIT_DEFAULT
        # The limit given on this run's command line (-view_limit), or None when it was not.  Held
        # apart from the runtime arguments because the settings restore replaces those wholesale,
        # and the GUI seeds its own View Limit from it once, at startup (userintr.MyGui).
        self.cli_view_limit = None
        # The Diagram as it is being drawn: its lines, how often each called Task is drawn, and where
        # each connector between them starts -- all emptied by diagram.py before it draws.
        self.netmap_output: list = []
        self.called_task_tracker: dict = {}
        self.diagram_connector_seeds: list = []
        # The finished connectors the Diagram view draws: {connector id: its ranges} (see guiwins).
        self.diagram_connectors: dict = {}
        # The Tasks already written into the Outline (outline.py), so that each is written once.
        self.outline_tasks_mapped: list = []
        # True on Windows; set at startup, together with slash (proginit).
        self.windows_system = False
        self.tasker_arg_specs: dict = {}
        self.tasker_category_descriptions: dict = {}
        self.tasker_event_codes: dict = {}
        self.tasker_state_codes: dict = {}
        self.trace: bool = False
        self.languages: dict[str, str] = {
            "English": "en",
            "Spanish": "es",
            "German": "de",
            "Simplified Chinese": "zh_CN",
            "Traditional Chinese": "zh_TW",
            "Hindi": "hi",
            "French": "fr",
            "Portuguese": "pt",
            "Japanese": "ja",
            "Russian": "ru",
            "Korean": "ko",
            "Arabic": "ar",
            "Bengali": "bn",
            "Urdu": "ur",
            "Indonesian": "in",
            "Swahili": "sw",
            "Marathi": "mr",
            "Telugu": "te",
            "Turkish": "tr",
            "Tamil": "ta",
            "Vietnamese": "vi",
            "Italian": "it",
            "Ukrainian": "uk",
            "Polish": "pl",
            "Dutch": "nl",
            "Thai": "th",
            "Gujarati": "gu",
            "Persian": "fa",
            "Swedish": "sv",
            "Danish": "da",
            "Finish": "fi",
            "Norwegian": "no",
            "Greek": "el",
            "Czech": "cs",
        }
        self.languages_translated: dict[str, str] = {}
        self.language_set: bool = False
        # appearance_translated: ClassVar[dict[str, str]] = {}
        self.mygui = None
        # True for a run with no person at the keyboard: a command-line report or export (see
        # clireports).  Such a run must not open the finished Map in a web browser, and must not
        # rewrite the settings file the GUI keeps -- what it was asked to do is not a change of
        # settings.
        self.headless: bool = False


# The run state the program runs on.  Everything that has not been given a RunState of its own
# reads and writes this one -- it is what "PrimeItems.x" has always meant.
PrimeItems = RunState()

# What a reset leaves alone: the session's own settings and the look-up tables loaded once for
# it, as opposed to the state of one run over one backup.  Everything else on PrimeItems is
# per-run, and PrimeItemsReset puts it back to exactly what the class body above says -- so a
# new attribute is reset unless it is named here.
SESSION_ATTRIBUTES = frozenset(
    {
        "languages",  # the language pulldown's choices
        "languages_translated",  # ...and their names in the language in use (translator)
        "language_set",  # whether the GUI has switched language yet
        "last_run",  # when MapTasker last ran, from the settings file
        "mygui",  # the running GUI
        "headless",  # whether this is a command-line report or export, set once at startup (clireports)
        "slash",  # the OS's path separator, set at startup (proginit)
        "windows_system",  # likewise
        "tasker_arg_specs",  # Tasker's action argument specs, loaded once (actionc.load_arg_specs)
        "tasker_category_descriptions",  # likewise
        "tasker_event_codes",  # Tasker's event and state codes, fetched once (valcodes)
        "tasker_state_codes",  # likewise
        "trace",  # debug tracing, switched on once (guiutil2)
        "view_limit",  # set by the GUI just before a build, which a reset must not undo
        "cli_view_limit",  # what this run's command line asked for, which outlives any one run
    },
)

# The per-run defaults, taken from a RunState nothing has touched, and deep-copied on every
# reset because most are dicts and lists a run fills in place: handing the same object out
# twice would bring the last run's contents back with it.
_RUN_DEFAULTS = {name: value for name, value in vars(RunState()).items() if name not in SESSION_ATTRIBUTES}


# Per-run attributes that are reset together part-way through a session, rather than all at
# once.  Each group is written down once, here beside the class that declares its members,
# instead of being spelled out again at every place it is reset.
#
# The output of one Map build: thrown away together when a view is built (userintr.view_event)
# and when a build starts its output again part-way through (lineout.refresh_our_output).
MAP_OUTPUT_ATTRIBUTES = ("directory_items", "emitted_anchors", "grand_totals", "task_action_warnings")
# Everything diagram.network_map records about the Diagram it draws, emptied before it starts
# so that a Diagram cannot inherit the last one's objects -- or, if it fails part-way through,
# the last one's connectors.
DIAGRAM_ATTRIBUTES = (
    "netmap_output",
    "called_task_tracker",
    "diagram_object_seeds",
    "diagram_object_targets",
    "diagram_object_placements",
    "diagram_anchors",
    "diagram_call_edges",
    "diagram_connector_calls",
    "diagram_connector_seeds",
    "diagram_connectors",
    "diagram_model",
)
# The counts behind one Project's summary line (projects.setup_summary_counts).
PROJECT_COUNT_ATTRIBUTES = (
    "task_count_for_profile",
    "scene_count",
    "named_task_count_total",
    "task_count_unnamed",
    "task_count_no_profile",
)
# The backup that is loaded: everything taskerd.get_the_xml_data sets as it parses one (the
# highest object id included), the file it was read from, and the error a failed parse leaves.
# diffload parses a second backup to compare against and puts all of this back afterwards; a
# test keeps the group in step with what taskerd sets.
LOADED_CONFIGURATION_ATTRIBUTES = (
    "file_to_get",
    "file_to_use",
    "xml_tree",
    "xml_root",
    "tasker_root_elements",
    "loaded_highest_object_id",
    "error_code",
    "error_msg",
    "error_show_code",
)


def reset_attributes(*names: str, state: RunState | None = None) -> None:
    """
    Put the named per-run attributes of a RunState back to their declared defaults.

    Each gets a fresh copy of the value RunState's __init__ gives it.

    Args:
        *names (str): attribute names -- usually one of the groups above.  Nothing resets a
            session attribute, so naming one raises KeyError.
        state (RunState | None): the run state to reset, or None for PrimeItems.
    """
    target = PrimeItems if state is None else state
    for name in names:
        setattr(target, name, copy.deepcopy(_RUN_DEFAULTS[name]))


def clear_error() -> None:
    """Forget the error the last load or build recorded: error_code, error_msg and error_show_code."""
    reset_attributes("error_code", "error_msg", "error_show_code")


# Reset all values
class PrimeItemsReset:
    """Put every per-run attribute of PrimeItems back to its declared default."""

    def __init__(self) -> None:
        """
        Reset PrimeItems for a new run.

        Every attribute not in SESSION_ATTRIBUTES gets a fresh copy of the value the class body
        gives it.  The class body is the only list: this used to name each attribute a second
        time, by hand, and that copy had drifted from it.  What other modules keep about the
        configuration goes with it (see caches).
        """
        reset_attributes(*_RUN_DEFAULTS)
        caches.clear_all()


# All three helpers below take the settings to read as an optional argument: pass a
# RunConfig (runcfg.py) and the answer depends only on it, which is what lets a caller
# ask "what would this run show?" without the global being set up first.  Left out, they
# read the settings currently on PrimeItems, as they always have.  A RunConfig and a
# ProgramArguments share their fields (ArgumentFields), which is all this needs.
def _settings(config: RunConfig | None) -> ArgumentFields:
    """
    Return the settings to read: the given config, or the ones on PrimeItems.

    Args:
        config (RunConfig | None): the settings to use, or None for the current ones.

    Returns:
        ArgumentFields: the settings -- a RunConfig or a ProgramArguments -- read by attribute.
    """
    return PrimeItems.program_arguments if config is None else config


# Return the single named item being asked for, if any.
def get_single_item_requested(config: RunConfig | None = None) -> tuple[str, str]:
    """
    Return the single named item the user asked to display, if any.

    Args:
        config (RunConfig | None): the settings to read, or None for the current ones.

    Returns:
        tuple[str, str]: (label, name) -- e.g. ("Task", "My Task") -- for whichever
            single_xxx_name is set, or ("", "") if we are displaying everything.
    """
    settings = _settings(config)
    for name_key, _, label in SINGLE_ITEM_SELECTORS:
        if name := getattr(settings, name_key):
            return label, name
    return "", ""


# Return the single named item that was asked for but never found, if any.
def get_single_item_not_found(config: RunConfig | None = None) -> tuple[str, str]:
    """
    Return the single named item that was requested but never found while building the
    output.

    Args:
        config (RunConfig | None): the settings to read, or None for the current ones.

    Returns:
        tuple[str, str]: (label, name) of the missing item, or ("", "") if nothing is
            missing -- either because no single item was requested, or because the one
            that was requested turned up.
    """
    settings = _settings(config)
    for name_key, found_key, label in SINGLE_ITEM_SELECTORS:
        name = getattr(settings, name_key)
        if name and not PrimeItems.found_named_items.get(found_key):
            return label, name
    return "", ""


# Return True if a single named item was asked for and it was found.
def is_single_item_found(config: RunConfig | None = None) -> bool:
    """
    Return True if a single named item was requested and has been found.

    Args:
        config (RunConfig | None): the settings to read, or None for the current ones.

    Returns:
        bool: True if any requested single item's found-flag is set.
    """
    settings = _settings(config)
    return any(
        getattr(settings, name_key) and PrimeItems.found_named_items.get(found_key)
        for name_key, found_key, _ in SINGLE_ITEM_SELECTORS
    )


# Clear the single named item being asked for, or all of them but one.
def clear_single_items(keep: str = "") -> None:
    """
    Clear the single Project/Profile/Task/Scene selection: each name asked for and its found-flag.

    Args:
        keep (str): the program_arguments key of one selection to leave as it is (for
            example "single_task_name"), or "" to clear them all.
    """
    for name_key, found_key, _ in SINGLE_ITEM_SELECTORS:
        if name_key != keep:
            PrimeItems.program_arguments[name_key] = ""
            PrimeItems.found_named_items[found_key] = False
