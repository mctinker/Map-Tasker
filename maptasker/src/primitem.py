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
# Set up an initial empty dictionary of primary items used throughout this project
#  xml_tree = main xml element of our Tasker xml tree
#  xml_root = root xml element of our Tasker xml tree
#  program_arguments = runtime arguments entered by user and parsed.
#    See initparg.py for details.
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

from typing import ClassVar

from maptasker.src.sysconst import (
    ANTHROPIC_MODELS,
    DEEPSEEK_MODELS,
    GEMINI_MODELS,
    LLAMA_MODELS,
    NOW_TIME,
    OPENAI_MODELS,
)

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
    set of keys with the parsed XML in them, so a key added here needs adding there too;
    maputils.clear_tasker_data also names a subset of them when emptying the tree
    in place.

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


class PrimeItems:
    """PrimeItems class contains global variables used throughout MapTasker"""

    ai: ClassVar = {
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
    xml_tree = None
    xml_root = None
    program_arguments: ClassVar[dict] = {}
    colors_to_use: ClassVar[dict] = {}
    output_lines: ClassVar = None
    file_to_get = ""
    file_to_use = ""
    task_count_for_profile = 0
    displaying_named_tasks_not_in_profile = False
    error_code = 0
    error_msg = ""
    view_limit_msg = (
        ""  # Set by bildhtml.write_out_the_file when output hits view_limit; read by the Map view's message field.
    )
    # The Diagram view's equivalent: set by diagram.check_limit when the diagram is cut short at
    # the view limit, read by the Diagram view's message field.  Kept separate from
    # view_limit_msg so a truncated Map cannot leave its message showing on an untruncated
    # Diagram (the two views are built from separate runs).
    diagram_limit_msg = ""
    found_named_items: ClassVar[dict] = initial_found_named_items()
    grand_totals: ClassVar[dict] = initial_grand_totals()
    directory_items: ClassVar[dict] = initial_directory_items()
    # Every mapjump anchor id written into the Map so far this run.  An id may appear in a
    # document only once, and a Task listed by two Profiles (or by a Profile and again in
    # "Tasks not in any Profile") is output twice -- so the second sighting is written
    # without an anchor and a jump lands on the Task's first appearance.  Emptied wherever
    # directory_items is, and for the same reason: both describe one run's output, and
    # refresh_our_output throws that output away and starts it again mid-run.
    emitted_anchors: ClassVar[set] = set()
    # Where each object ended up in the Diagram that was last built: {mapjump anchor id:
    # (line, column, length)}, in the coordinates of the rendered diagram file, with column
    # and length counted in UTF-16 code units so the browser can use them as given.  Filled
    # by diagram.network_map; read by mapjump.diagram_placement so a Find result or a report
    # finding can be taken to the Diagram as precisely as it is taken to the Map.  Empty
    # until a Diagram has been built, which is the same thing as "no Diagram to jump into".
    diagram_anchors: ClassVar[dict] = {}
    # The same, mid-build and before the positions are final: {anchor: (row, drawn text)}
    # in netmap_output's own line numbering.  Lives on PrimeItems rather than in diagram.py
    # only so that it is emptied wherever the rest of a run's output is.
    diagram_object_seeds: ClassVar[dict] = {}
    # Which object each of those anchors IS: {anchor: mapjump.Target}.  Held apart from the
    # positions because a position is remapped four times before the diagram is written and
    # an identity never is -- see diagram._record.  Read once, when the interactive Diagram
    # view's model is assembled, and emptied straight afterwards.
    diagram_object_targets: ClassVar[dict] = {}
    # Every drawing of every object, not just the first: [(anchor, row, drawn text)] while
    # the diagram is being built, and [(anchor, line, column, length)] once it is written.
    # diagram_anchors above answers "where does a jump to this object land"; this answers
    # "which pieces of the drawing ARE this object", which is a different question wherever
    # the Diagram draws one twice -- a Task run by two Profiles, or fired by a Scene as well.
    diagram_object_placements: ClassVar[list] = []
    # Every call the Diagram drew a connector for: {call index: {caller_row, called_row,
    # caller_name, called_name, project}}, in the rendered file's line numbering by the time
    # the diagram is finished.  The call index is what each connector seed carries, which is
    # how a run of box-drawing characters is traced back to the two Tasks it joins.
    diagram_call_edges: ClassVar[dict] = {}
    # Which calls each finished connector belongs to: {connector group id: [call index, ...]}.
    # Filled by diagram.compute_diagram_connector_groups, as the other half of the same fact.
    diagram_connector_calls: ClassVar[dict] = {}
    # The whole of what the interactive Diagram view acts on -- nodes, foldable Project
    # regions and call edges, all in the rendered file's coordinates.  Assembled by
    # diagintr.build_model once the diagram is written; read by the view when it renders.
    diagram_model: ClassVar[dict] = {}
    tasker_root_elements: ClassVar[dict] = initial_tasker_root_elements()
    directories: ClassVar[list] = []
    variables: ClassVar[dict] = {}
    current_project = ""
    last_run = NOW_TIME
    mono_fonts: ClassVar[dict] = {}
    slash = "/"
    task_action_warnings: ClassVar[dict] = {}
    task_count_unnamed = 0
    task_count_no_profile = 0
    named_task_count_total = 0
    tasker_action_codes: ClassVar[dict] = {}
    tasker_arg_specs: ClassVar[dict] = {}
    tasker_category_descriptions: ClassVar[dict] = {}
    tasker_event_codes: ClassVar[dict] = {}
    tasker_state_codes: ClassVar[dict] = {}
    trace: ClassVar[bool] = False
    languages: ClassVar[dict[str, str]] = {
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
        "Tamali": "ta",
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
    languages_translated: ClassVar[dict[str, str]] = {}
    language_set: bool = False
    # appearance_translated: ClassVar[dict[str, str]] = {}
    mygui: ClassVar = None


# Reset all values
class PrimeItemsReset:
    """Re-initialize all values in PrimeItems class"""

    def __init__(self) -> None:
        """
        Initialize the PrimeItems class
        Args:
            self: The instance of the class
        Returns:
            None
        Initializes all attributes of the PrimeItems class with empty values or dictionaries:
            - Sets found_named_items flags to False
            - Initializes grand_totals and directory_items dictionaries
            - Initializes tasker_root_elements dictionary
            - Sets other attributes like xml_tree, program_arguments etc to empty values
        """
        PrimeItems.found_named_items = initial_found_named_items()
        PrimeItems.grand_totals = initial_grand_totals()
        PrimeItems.directory_items = initial_directory_items()
        PrimeItems.emitted_anchors = set()
        PrimeItems.diagram_anchors = {}
        PrimeItems.diagram_object_seeds = {}
        PrimeItems.diagram_object_targets = {}
        PrimeItems.diagram_object_placements = []
        PrimeItems.diagram_call_edges = {}
        PrimeItems.diagram_connector_calls = {}
        PrimeItems.diagram_model = {}
        PrimeItems.tasker_root_elements = initial_tasker_root_elements()
        PrimeItems.directories = []
        PrimeItems.xml_tree = None
        PrimeItems.xml_root = None
        PrimeItems.program_arguments = {}
        PrimeItems.colors_to_use = {}
        PrimeItems.output_lines = None
        PrimeItems.file_to_get = ""
        PrimeItems.task_count_for_profile = 0
        PrimeItems.displaying_named_tasks_not_in_profile = False
        PrimeItems.mono_fonts = {}
        PrimeItems.directories = []
        PrimeItems.variables = {}
        PrimeItems.current_project = ""
        PrimeItems.error_code = 0
        PrimeItems.error_msg = ""
        PrimeItems.view_limit_msg = ""
        PrimeItems.diagram_limit_msg = ""
        PrimeItems.ai = {
            "do_ai": False,
            "ai_name": "",
            "model": "",
            "output_lines": [],
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
        PrimeItems.task_action_warnings = {}


# Return the single named item being asked for, if any.
def get_single_item_requested() -> tuple[str, str]:
    """
    Return the single named item the user asked to display, if any.

    Returns:
        tuple[str, str]: (label, name) -- e.g. ("Task", "My Task") -- for whichever
            single_xxx_name is set, or ("", "") if we are displaying everything.
    """
    for name_key, _, label in SINGLE_ITEM_SELECTORS:
        if PrimeItems.program_arguments.get(name_key):
            return label, PrimeItems.program_arguments[name_key]
    return "", ""


# Return the single named item that was asked for but never found, if any.
def get_single_item_not_found() -> tuple[str, str]:
    """
    Return the single named item that was requested but never found while building the
    output.

    Returns:
        tuple[str, str]: (label, name) of the missing item, or ("", "") if nothing is
            missing -- either because no single item was requested, or because the one
            that was requested turned up.
    """
    for name_key, found_key, label in SINGLE_ITEM_SELECTORS:
        name = PrimeItems.program_arguments.get(name_key)
        if name and not PrimeItems.found_named_items.get(found_key):
            return label, name
    return "", ""


# Return True if a single named item was asked for and it was found.
def is_single_item_found() -> bool:
    """
    Return True if a single named item was requested and has been found.

    Returns:
        bool: True if any requested single item's found-flag is set.
    """
    return any(
        PrimeItems.program_arguments.get(name_key) and PrimeItems.found_named_items.get(found_key)
        for name_key, found_key, _ in SINGLE_ITEM_SELECTORS
    )
