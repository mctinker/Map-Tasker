"""Utilities used by GUI (NiceGUI Version)"""

import contextlib
import os
from datetime import date
from typing import TYPE_CHECKING

import defusedxml
from nicegui import app, run, ui

# Keep your existing logic imports (e.g., from maptasker.src.aiutils import ...)
from maptasker.src.aiutils import (
    get_anthropic_models,
    get_api_key,
    get_deepseek_models,
    get_gemini_models,
    get_llama_models,
    get_openai_models,
    is_valid_ai_config,
)
from maptasker.src.colrmode import set_color_mode
from maptasker.src.error import rutroh_error
from maptasker.src.getids import get_ids
from maptasker.src.getputer import save_restore_args
from maptasker.src.guiutil2 import get_changelog_file
from maptasker.src.lineout import LineOut
from maptasker.src.maputil2 import http_request, translate_string
from maptasker.src.maputil3 import validate_xml_file
from maptasker.src.maputils import get_pypi_version, restart_program_subprocess
from maptasker.src.primitem import PrimeItems
from maptasker.src.profiles import get_profile_tasks
from maptasker.src.proginit import get_data_and_output_intro
from maptasker.src.sysconst import (
    ANALYSIS_FILE,
    ARGUMENT_NAMES,
    CHANGELOG_FILE,
    CHANGELOG_URL,
    ERROR_FILE,
    LLAMA_MODELS,
    MODEL_GROUPS,
    NOW_TIME,
    UNNAMED_ITEM,
    VERSION,
    logger,
)

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


# ==========================================
# 2. DYNAMIC COMPONENT UPDATERS
# ==========================================
def update_analysis_button_color(gui: "MyGui") -> None:
    """Colors the 'Run Analysis' button green when either:
      - a prompt, AI model, and API key are all set, or
      - a prompt and a LLAMA_MODELS model are set with no API key (local Llama models run
        without one).
    Red otherwise. "None" is the dropdown's own placeholder for "nothing selected", so it counts
    as not having a model even though it's a non-empty string.
    """
    has_key = bool(getattr(gui, "ai_apikey", None))
    has_model = bool(getattr(gui, "ai_model", None)) and gui.ai_model != "None"
    has_prompt = bool(getattr(gui, "ai_prompt", None))
    is_llama_model = has_model and gui.ai_model in LLAMA_MODELS

    ready = (has_key and has_model and has_prompt) or (has_prompt and is_llama_model and not has_key)
    gui.analysis_button.props(f"color={'green' if ready else 'red'}")


def display_model_pulldown(gui_arg: any, *args: dict, **kwargs) -> None:  # noqa: ANN003, ARG001
    """Displays the AI model selection dropdown list.

    Normalizes `gui_arg` whether it's passed a direct MyGui instance,
    a NiceGUI event object, or a MapTaskerEventHandlers instance.
    """
    # 1. Normalize the argument to find the true MyGui instance context
    if hasattr(gui_arg, "gui") and gui_arg.gui.__class__.__name__ == "MyGui":
        gui_instance = gui_arg.gui
    elif hasattr(gui_arg, "client") or hasattr(gui_arg, "sender"):
        # It's a NiceGUI UI Event object; try to fetch from PrimeItems or a cross-reference
        gui_instance = getattr(PrimeItems, "mygui", gui_arg)
    else:
        gui_instance = gui_arg

    # 2. Safety Fallback validation check
    if gui_instance.__class__.__name__ != "MyGui":
        logger.error(f"display_model_pulldown received an invalid GUI context object: {type(gui_arg)}")
        return

    # Add the list of models.  If this is a request for an extended list, then get the extended list.
    if gui_instance.ai_model_extended_list and not gui_instance.initialization:
        if gui_instance.displaying_extended_list is not None and gui_instance.displaying_extended_list:
            return  # Return if we are already displaying it.
        # Destroy the old window if it is last to be displayed and get the extended list...only if we are not in the
        # middle of setting/changing the language.
        if not PrimeItems.language_set:
            with contextlib.suppress(AttributeError):
                gui_instance.ai_model_option.destroy()
            display_models = get_extended_ai_model_list()
            gui_instance.displaying_extended_list = True
        else:
            # Not a request to build the extended, or we are in the middle of changing the language.
            with contextlib.suppress(AttributeError):
                gui_instance.ai_model_option.destroy()
            display_models = sorted(
                model for name, models in MODEL_GROUPS.items() for model in prefix_and_sort(models, name)
            )

    # Just display the pre-defined model names.
    else:
        if gui_instance.displaying_extended_list is not None and not gui_instance.displaying_extended_list:
            return  # Return if we are already displaying it.
        # Destroy the old window if it is last to be displayed.
        if gui_instance.displaying_extended_list is not None:
            with contextlib.suppress(AttributeError):
                gui_instance.ai_model_option.destroy()
        display_models = sorted(
            model for name, models in MODEL_GROUPS.items() for model in prefix_and_sort(models, name)
        )
        gui_instance.displaying_extended_list = False

    # If the select dropdown already exists on the GUI instance, just update its options
    if hasattr(gui_instance, "ai_model_option") and gui_instance.ai_model_option:
        gui_instance.ai_model_option.options = display_models
        gui_instance.ai_model_option.update()
    else:
        # Otherwise, if we are building it for the first time
        current_model = [PrimeItems.program_arguments.get("ai_model", "None")]
        if not current_model or current_model not in display_models:
            current_model = ["None"]
        gui_instance.ai_model_option = ui.select(
            options=display_models,
            value=current_model,
            label="AI Model",
            on_change=gui_instance.event_handlers.ai_model_selected_event,
        ).classes("w-64")

        # Updates NiceGUI visual rendering colors reactively
        update_analysis_button_color(gui_instance)


def prefix_and_sort(strings: list[str], name: str) -> list[str]:
    """
    Prefixes each string in a list with a given name and returns the modified list sorted.

    Args:
        strings: A list of strings.
        name: The name to prefix each string with.

    Returns:
        A new list of strings with each original string prefixed by `name`, sorted alphabetically.
    """

    prefixed_strings = [f"{name}: {s}" for s in strings]
    prefixed_strings.sort()
    return prefixed_strings


def get_extended_ai_model_list() -> list:
    """Retrieves and compiles an extended list of available AI models from various providers.

    This function fetches models from OpenAI, Anthropic, and Gemini (assuming respective
    API keys are configured or default lists are available). It groups these models
    by their provider, applies a prefix and sorts them within their groups,
    and then consolidates them into a single, sorted list.

    The process involves:
    1. Attempting to retrieve API keys (though the result is not directly used here).
    2. Fetching available models from OpenAI.
    3. Fetching available models from Anthropic.
    4. Fetching available models from Gemini.
    5. Organizing these models into a dictionary, keyed by provider name.
    6. Iterating through each provider's models, applying 'prefix_and_sort'
       (which is expected to add a provider-specific prefix and sort them).
    7. Consolidating all processed models into a single list.
    8. Performing a final sort on the entire consolidated list.

    Returns:
        list: A sorted list of strings, where each string represents an AI model,
              potentially prefixed with its provider name (e.g., "OpenAI/gpt-4o",
              "Anthropic/claude-3-opus-20240229", "Gemini/gemini-pro").
              Returns an empty list if no models are retrieved.
    """
    _ = get_api_key()
    PrimeItems.ai["openai_models"] = get_openai_models()
    PrimeItems.ai["anthropic_models"] = get_anthropic_models()
    PrimeItems.ai["gemini_models"] = get_gemini_models()
    PrimeItems.ai["llama_models"] = get_llama_models()
    PrimeItems.ai["deepseek_models"] = get_deepseek_models()

    # Define the models
    extended_model_groups = {
        "OpenAI": PrimeItems.ai["openai_models"],
        "Anthropic": PrimeItems.ai["anthropic_models"],
        "Gemini": PrimeItems.ai["gemini_models"],
        "LLAMA": PrimeItems.ai["llama_models"],
        "DeepSeek": PrimeItems.ai["deepseek_models"],
    }
    # all_models = openai_models + anthropic_models + gemini_models

    # Create an empty list to store the display models
    display_models = []

    # Iterate through the items in extended_model_groups
    for name, models in extended_model_groups.items():
        # Apply prefix_and_sort to the current group of models
        sorted_models_with_prefix = prefix_and_sort(models, name)

        # Extend the display_models list with the processed models
        display_models.extend(sorted_models_with_prefix)

    # Finally, sort the entire list of display models
    return sorted(display_models)


def update_tasker_object_menus(self: "MyGui", get_data: bool = False, reset_single_names: bool = False) -> None:
    """
    Updates the Project, Profile, and Task dropdowns in the 'Specific Name' tab.
    """
    if get_data:
        if reset_single_names:
            self.single_project_name = ""
            self.single_profile_name = ""
            self.single_task_name = ""
        return_code = list_tasker_objects(self)
        if not return_code:
            return

    # Update the Project/Profile/Task pulldown option menus.

    # Update the text labels
    display_selected_object_labels(self)


# Provide a pulldown list for the selection of a Profile name
def list_tasker_objects(self) -> bool:  # noqa: ANN001
    """
    Lists the projects, profiles and tasks available in the XML file.  The list for each will appear in a pulldown option list.

    This function checks if the XML file has already been loaded. If not, it loads the XML file and builds the tree data.
    Then, it goes through each project and retrieves all the profile names and tasks.
    The profile names and tasks are cleaned up by removing the "Profile: (Unnamed)" and "Task: ...(Unnamed)" entries.
    If there are no profiles or tasks found, a message box is displayed and the function returns False.
    The profile names and tasks are then sorted alphabetically and duplicates are removed.
    The profile names are displayed in a label for selection, and the corresponding tasks are displayed in another label for selection.

    Returns:
        bool: True if the XML file has Profiles or Tasks, False otherwise.
    """

    # Do we already have the XML?
    # If we don't have any data, get it.
    if not self.load_xml():
        return False

    # Get all of the Tasker objects: Projects/Profiles/Tasks/Scenes
    return_code, projects_to_display, profiles_to_display, tasks_to_display = get_tasker_objects(self)
    if not return_code:
        return False

    # Translate "No Profile"
    # Note: Do NOT translate "None" here since 'display_object_pulldowns' will translate it again.
    none_translated = "None"
    noprofile_translated = translate_string("No Profile")
    # Make alphabetical
    if projects_to_display:
        projects_to_display.sort()
        projects_to_display.insert(0, none_translated)
    if profiles_to_display:
        # Filter out dummy profiles created for Tasks with no Profile.
        profiles = [profile for profile in profiles_to_display if profile != noprofile_translated]
        profiles_to_display = profiles
        profiles_to_display.sort()
        profiles_to_display.insert(0, none_translated)
    tasks_to_display.insert(0, none_translated)

    # Display the object pulldowns in 'Specific Name' tab
    if not projects_to_display:  # If no Projects to display
        projects_to_display = [translate_string("None")]
    (
        self.specific_project_optionmenu,
        self.specific_profile_optionmenu,
        self.specific_task_optionmenu,
    ) = display_object_pulldowns(
        self,
        projects_to_display,
        profiles_to_display,
        tasks_to_display,
    )
    return True


def display_object_pulldowns(
    self: "MyGui",
    projects_to_display: list,
    profiles_to_display: list,
    tasks_to_display: list,
) -> tuple:
    """
    Updates the pulldown menus for selecting projects, profiles, and tasks.
    """

    # Just update the options for the widgets we created in guiwins.py
    if hasattr(self, "specific_project_optionmenu") and self.specific_project_optionmenu:
        # 1. Assign the new lists to the options attributes safely
        self.specific_project_optionmenu.options = projects_to_display
        self.specific_profile_optionmenu.options = profiles_to_display
        self.specific_task_optionmenu.options = tasks_to_display

        # 2. FIX: REMOVED .clear() AND .on() LOOPS HERE!
        # The event listeners are already bound via 'on_change=' during initialization.
        # No changes to event listeners means NO CONSOLE WARNINGS.

        # 3. Tell the browser to re-render the options lists cleanly
        self.specific_project_optionmenu.update()
        self.specific_profile_optionmenu.update()
        self.specific_task_optionmenu.update()

    return self.specific_project_optionmenu, self.specific_profile_optionmenu, self.specific_task_optionmenu


# Get all Projects, Profiles and Tasks to display
def get_tasker_objects(self) -> tuple:  # noqa: ANN001
    """
    Retrieves the projects, profiles, and tasks available in the XML file.

    Returns:
        tuple: A tuple containing the following:
            - bool: True if the XML file has Profiles or Tasks, False otherwise.
            - list: A list of project names.
            - list: A list of profile names to display.
            - list: A list of task names to display.
    """
    projects_to_display = []
    profiles = []
    tasks = []
    # Build the tree of Tasker objects
    tree_data = self.build_the_tree()
    # If no tree data, then we don't have any Projects.  Just get the Profiles and Tasks.
    if not tree_data:
        profiles = [value["name"] for value in PrimeItems.tasker_root_elements["all_profiles"].values()]
        # tasks = [value["name"] for value in PrimeItems.tasker_root_elements["all_tasks"].values()]
    # We have the Tasker objects.  Collect all Projects, Profiles and Tasks from the tree data.
    else:
        for project in tree_data:
            projects_to_display.append(project["name"])
            for profile in project["children"]:
                with contextlib.suppress(TypeError):
                    profiles.append(profile["name"])
                    tasks.extend(profile["children"])

    # Clean up the object lists by removing anonymous or missing objects.
    if self.list_unnamed_items:
        profiles_to_display = profiles
    else:
        profiles_to_display = [profile for profile in profiles if UNNAMED_ITEM not in profile]
    if not projects_to_display:
        projects_to_display = [translate_string("No projects found")]
    if not profiles_to_display:
        profiles_to_display = [translate_string("No profiles found")]

    # Build list of Task names to display in the GUI pulldown.
    tasks_to_display = list(PrimeItems.tasker_root_elements["all_tasks_by_name"])

    # Check for no tasks.
    if not tasks_to_display:
        tasks_to_display = [translate_string("No tasks found")]
    else:
        if not self.list_unnamed_items:
            # Remove unnamed Tasks from the list.
            new_task_list = []
            for task in tasks_to_display:
                if UNNAMED_ITEM in task:
                    continue
                # If the task is not in the list of tasks, add it to the new list.
                new_task_list.append(task)
            # Remove duplicates and sort the list.
            tasks_to_display = list(set(new_task_list))
        tasks_to_display.sort()

    return True, projects_to_display, profiles_to_display, tasks_to_display


def display_selected_object_labels(self: "MyGui") -> None:
    """
    Display the current settings for Ai with absolute value-matching fixes for NiceGUI.
    """
    if not self.ai_apikey:
        self.ai_apikey = get_api_key()

    key_to_display = "N/A" if getattr(self, "ai_name", "") == "LLAMA" else "Unset" if not self.ai_apikey else "Set"

    # 1. Resolve the true display value for the model dropdown
    model_to_display = "None"
    if self.ai_model:
        # If the dropdown widget exists, look for the choice that ends with our active model
        if getattr(self, "ai_model_option", None) and self.ai_model_option.options:
            matching_option = next((opt for opt in self.ai_model_option.options if opt.endswith(self.ai_model)), None)
            model_to_display = matching_option or self.ai_model
        else:
            model_to_display = self.ai_model

    none_translated = translate_string("None")
    project_to_display = self.single_project_name if self.single_project_name else none_translated
    profile_to_display = self.single_profile_name if self.single_profile_name else none_translated
    task_to_display = self.single_task_name if self.single_task_name else none_translated
    if project_to_display is not None and project_to_display != "None":
        self.currently_selected_label.set_text("Current Project selection: " + project_to_display)
    elif profile_to_display is not None and profile_to_display != "None":
        self.currently_selected_label.set_text("Current Profile selection: " + profile_to_display)
    elif task_to_display is not None and task_to_display != "None":
        self.currently_selected_label.set_text("Current Task selection: " + task_to_display)

    # 2. Render the "Analyze" Tab panel context natively
    with self.tab_analyze:
        # Clear the container frame so elements don't stack up iteratively
        self.tab_analyze.clear()
        self.ai_project_label = None
        self.ai_profile_label = None
        self.ai_task_label = None

        # Display Model & Key tracking summaries
        # Use the raw model string or cleaned display model cleanly
        short_model_name = self.ai_model if self.ai_model else "None"
        self.ai_apikey_and_model_lbl = ui.label(
            f"{getattr(self, 'ai_name', '')} API Key: {key_to_display}, Model: {short_model_name}",
        ).classes(
            "text-sm mt-4",
        )

        # 3. FIX: Safely assign the value selection back to NiceGUI dropdown tree context
        # NiceGUI dropdown values are single primitives (string), not arrays like legacy wrappers!
        if getattr(self, "ai_model_option", None):
            try:
                self.is_updating = True  # Engage state lock protection
                self.ai_model_option.value = model_to_display
                self.ai_model_option.update()  # Push stream frame instantly
            finally:
                self.is_updating = False
        else:
            display_model_pulldown(self)

        # Display Targets selections
        translation_proj = translate_string("Project to Analyze:")
        self.ai_project_label = ui.label(f"{translation_proj} {project_to_display}").classes("text-sm mt-1")

        translation_prof = translate_string("Profile to Analyze:")
        self.ai_profile_label = ui.label(f"{translation_prof} {profile_to_display}").classes("text-sm mt-1")

        translation_task = translate_string("Task to Analyze:")
        self.ai_task_label = ui.label(f"{translation_task} {task_to_display}").classes("text-sm mt-1")

        # Display Prompt configurations
        display_prompt = translate_string(self.ai_prompt)
        prompt_title = translate_string("Prompt:")

        ui.label(f"{prompt_title} '{display_prompt}'").classes(
            "text-base mt-4 max-w-md whitespace-pre-wrap break-words",
        )
        self.tab_analyze.update()  # Force NiceGUI to re-render the tab context immediately

    # 4. Render Specific Name Tab labels tracking sync
    with self.tab_specific_name:
        # The following displays the selected Project/Profile/Task in the 'Specific Name' tab,
        # below the pulldown lists.  It is in addition to the 'Current (object) selection' above the pulldowns.
        all_objects_text = translate_string("Display all Projects, Profiles, and Tasks.")
        name_to_display = self.specific_name_msg if getattr(self, "specific_name_msg", None) else all_objects_text

        if hasattr(self, "specific_name_msg_label") and self.specific_name_msg_label:
            self.specific_name_msg_label.text = name_to_display
        else:
            with self.tab_specific_name:
                self.specific_name_msg_label = ui.label(name_to_display).classes("text-xs ml-2 mt-2 text-left")
        self.tab_specific_name.update()  # Force NiceGUI to re-render the tab context immediately

    ui.update()  # Ensure the entire GUI context is refreshed after updates


# ==========================================
# 4. PURE LOGIC FUNCTIONS (Unchanged)
# ==========================================
def get_taskid_from_unnamed_task(unnamed_task: str) -> str:
    """
    Extracts the task ID from an unnamed task string.

    Args:
        unnamed_task (str): The unnamed task string.

    Returns:
        str: The extracted task ID.
    """
    # Extract the task ID from the unnamed task string
    position = unnamed_task.rfind(".")
    if position != -1:
        return unnamed_task[position + 1 :].split(" (Unnamed)", maxsplit=1)[0]

    rutroh_error(f"Error.  Missing period for task ID in Taask name: '{unnamed_task}'")
    return unnamed_task.split(".")[1].strip()


def display_current_file(self: "MyGui", file_name: str) -> None:
    """
    A function to display the current file as a label in the GUI toolbar row.
    """
    # 1. Cleaner File Path Parsing
    clean_file_name = os.path.basename(file_name)

    # 2. Translation Logic
    text = "Current File"
    text = PrimeItems._(text) if hasattr(PrimeItems, "_") else text
    full_display_text = f"{text}: {clean_file_name}"

    # 3. NICEGUI TARGET FIX:
    # Check both potential property names to maintain alignment with initialize_screen
    label_widget = getattr(self, "current_file", None) or getattr(self, "current_file_label", None)

    if label_widget:
        # If the label already exists in the toolbar, simply alter its reactive text property!
        label_widget.text = full_display_text
        # Ensure both variable names reference the exact same widget on the instance
        self.current_file = label_widget
        self.current_file_label = label_widget
    else:
        # Fallback safeguard: If it doesn't exist yet, force creation INSIDE the toolbar container
        toolbar = getattr(self, "gui_view_toolbar", None)
        if toolbar:
            with toolbar:
                self.current_file_label = ui.label(full_display_text).classes("text-gray-500 italic ml-4")
                self.current_file = self.current_file_label
        else:
            # Absolute fallback if called before screen layout renders
            self.current_file_label = ui.label(full_display_text).classes("ml-4 text-left")
            self.current_file = self.current_file_label

    # 4. Update other UI elements
    update_tasker_object_menus(self, get_data=False, reset_single_names=False)


# Get the XML data and setup Primeitems
def get_xml(debug: bool, appearance_mode: str) -> int:
    """ "Returns the tasker root xml items from the backup xml file based on the given debug and appearance mode parameters."
    Parameters:
        debug (bool): Indicates whether the program is in debug mode or not.
        appearance_mode (str): Specifies the color mode to be used.
    Returns:
        int: The return code from getting the xml file.
    Processing Logic:
        - Initialize temporary PrimaryItems object.
        - Set file_to_get variable based on debug mode.
        - Set program_arguments variable for debug mode.
        - Set colors_to_use variable based on appearance mode.
        - Initialize output_lines variable.
        - Return data and output intro."""

    if not PrimeItems.program_arguments["debug"]:
        PrimeItems.program_arguments["debug"] = debug
    PrimeItems.program_arguments["gui"] = True
    PrimeItems.colors_to_use = set_color_mode(appearance_mode)
    PrimeItems.output_lines = LineOut()

    return get_data_and_output_intro(True)


# Clear all buttons associated with fetching the backup file from Android device
def clear_android_buttons(self: "MyGui") -> None:
    """
    Clears android device configuration UI elements and displays the backup button.
    """
    # 1. Group all the base elements you want to delete
    elements_to_delete = [
        "ip_entry",
        "port_entry",
        "file_entry",
        "ip_label",
        "port_label",
        "file_label",
        "get_backup_button",
        "cancel_entry_button",
        "list_files_button",
        "label_or",
        "filelist_label",
        "filelist_option",
        "list_files_query_button",
    ]

    # 2. Conditionally add elements based on the first_time flag
    # (Using getattr as a safeguard in case first_time hasn't been initialized yet)
    if not getattr(self, "first_time", True):
        elements_to_delete.append("upgrade_button")

    # 3. Iterate and delete efficiently
    for attr in elements_to_delete:
        widget = getattr(self, attr, None)
        if widget:
            with contextlib.suppress(Exception):
                widget.delete()  # NiceGUI uses .delete() instead of .destroy()

            # Clear the reference so your object state stays clean
            setattr(self, attr, None)

    # 4. Recreate the backup button
    # (Note: Ensure display_backup_button is also updated for NiceGUI,
    # particularly how it handles the Hex color codes)
    # Re-enter the row it originally lived in (see _create_file_and_message_buttons_section in
    # guiwins.py) -- display_backup_button() builds the button with no container of its own, so
    # without this it would attach to whatever the default slot is during this event callback
    # instead of staying under "File Operations".
    with self.android_button_row:
        self.get_backup_button = self.display_backup_button(
            "Get XML from Android Device",
            "#246FB6",
            "#6563ff",
            self.event_handlers.get_xml_from_android_event,
        )

    # The "?" button (self.android_query_button, see _create_file_and_message_buttons_section in
    # guiwins.py) is never deleted above, so re-creating get_backup_button just appended it after
    # the "?" button -- move() with no args re-appends an element to the end of its current
    # parent, putting the "?" button back on the right where it started.
    if getattr(self, "android_query_button", None):
        self.android_query_button.move()


# Build a list of Profiles that are under the given project, and all of their (Tasks) children.
def build_profiles(
    root: dict,
    profile_ids: list,
    project: defusedxml.ElementTree,
) -> list:
    """Parameters:
        - root (dict): Dictionary containing all profiles and their tasks.
        - profile_ids (list): List of profile IDs to be processed.
        - project (defusedxml.ElementTree): The project xml element.
    Returns:
        - list: List of dictionaries containing profile names and their corresponding tasks.
    Processing Logic:
        - Get all profiles from root dictionary.
        - Create an empty list to store profile names and tasks.
        - Loop through each profile ID in the provided list.
        - Get the tasks for the current profile.
        - If tasks are found, create a list to store task names.
        - Loop through each task and add its name to the task list.
        - If no tasks are found, add a default message to the task list.
        - Get the name of the current profile.
        - If no name is found, add a default message to the profile name.
        - Combine the profile name and task list into a dictionary and add it to the profile list.
        - Return the profile list."""
    profiles = root["all_profiles"]
    profile_list = []
    found_tasks = []
    profile_head = translate_string("Profile: ")
    task_head = translate_string("Task: ")
    unnamed_task_head = translate_string("Unnamed Task")
    _get_profile_tasks = get_profile_tasks  # Localize for speed
    for profile in profile_ids:
        # Get the Profile's Tasks
        PrimeItems.task_count_unnamed = 0  # Avoid an error in get_profile_tasks
        if the_tasks := _get_profile_tasks(profiles[profile]["xml"], [], []):
            task_list = []
            # Process each Task.  Tasks are simply a flat list of names.
            for task in the_tasks:
                if task["name"] == "":
                    task_list.append(f"{task_head}{unnamed_task_head}")
                else:
                    task_list.append(f"{task_head}{task['name']}")
                    found_tasks.append(task["name"])  # Keep track of found tasks
        else:
            task_list = [translate_string("No Profile Tasks Found")]

        # Get the Profile name.
        profile_name = f"{profile_head}{profiles[profile]['name']}"

        # Combine the Profile with it's Tasks
        profile_list.append({"name": profile_name, "children": task_list})

    # Now add tasks that are not found in any Profile that belong to the Project
    no_profile_tasks = []
    task_ids = get_ids(
        False,
        PrimeItems.tasker_root_elements["all_projects"][project]["xml"],
        project,
        [],
    )
    for task_id in task_ids:
        if root["all_tasks"][task_id]["name"] not in found_tasks:
            no_profile_tasks.append(root["all_tasks"][task_id]["name"])  # noqa: PERF401
    if no_profile_tasks:
        profile_list.append({"name": translate_string("No Profile"), "children": no_profile_tasks})

    return profile_list


def set_tasker_object_names(self: object) -> None:
    """Set names to display in pulldown menus based on current tasker object names."""
    # Translate the default values if possible
    none_text = PrimeItems._("None") if hasattr(PrimeItems, "_") else "None"
    display_only_text = "Display only"
    display_only_text = PrimeItems._(display_only_text) if hasattr(PrimeItems, "_") else display_only_text

    defaults = {
        "project": self.single_project_name if self.single_project_name else none_text,
        "profile": self.single_profile_name if self.single_profile_name else none_text,
        "task": self.single_task_name if self.single_task_name else none_text,
        "display_only": f"{display_only_text} ",
    }

    # Map attribute presence to corresponding function
    handlers = (
        (self.single_project_name, _set_single_project_name),
        (self.single_profile_name, _set_single_profile_name),
        (self.single_task_name, _set_single_task_name),
    )

    # Go through handlers and call the appropriate function for a single named item
    for attr_value, func in handlers:
        if attr_value:
            # We have a single-named item. Set values and return
            func(self, defaults)
            return

    # No single item selected. Set the defaults.
    _set_default_names(self, defaults)


def _set_single_project_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single project name is available."""
    text = f"{defaults['display_only']}{translate_string('Project')}"
    self.specific_name_msg = f"{text} '{self.single_project_name}'"
    try:
        # NiceGUI uses .value instead of .set()
        self.specific_project_optionmenu.value = self.single_project_name
    except AttributeError:
        return

    self.specific_profile_optionmenu.value = defaults["profile"]
    self.specific_task_optionmenu.value = defaults["task"]


def _set_single_profile_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single profile name is available."""
    # Note: Fixed a missing opening single quote before the profile name from the original code
    self.specific_name_msg = f"{defaults['display_only']}{translate_string('Profile')} '{self.single_profile_name}'"
    try:
        self.specific_profile_optionmenu.value = self.single_profile_name
    except AttributeError:
        return

    self.specific_project_optionmenu.value = defaults["project"]
    self.specific_task_optionmenu.value = defaults["task"]


def _set_single_task_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single task name is available."""
    self.specific_name_msg = f"{defaults['display_only']}{translate_string('Task')} '{self.single_task_name}'"
    try:
        self.specific_task_optionmenu.value = self.single_task_name
    except AttributeError:
        return

    self.specific_project_optionmenu.value = defaults["project"]
    self.specific_profile_optionmenu.value = defaults["profile"]


def _set_default_names(self: object, defaults: dict) -> None:
    """Handles setting names when no specific name is available."""
    self.specific_name_msg = ""
    try:
        none_text = PrimeItems._("None") if hasattr(PrimeItems, "_") else "None"
        project_text = defaults["project"]
        profile_text = defaults["profile"]
        task_text = defaults["task"]

        self.specific_project_optionmenu.value = project_text

        # NiceGUI updates available options by changing the .options list directly
        if not PrimeItems.tasker_root_elements.get("all_projects"):
            self.specific_project_optionmenu.options = [none_text]
            self.specific_project_optionmenu.value = none_text

        if not PrimeItems.tasker_root_elements.get("all_profiles"):
            self.specific_profile_optionmenu.options = [none_text]
            self.specific_profile_optionmenu.value = none_text

        if not PrimeItems.tasker_root_elements.get("all_tasks"):
            self.specific_task_optionmenu.options = [none_text]
            self.specific_task_optionmenu.value = none_text

        self.specific_profile_optionmenu.value = profile_text
        self.specific_task_optionmenu.value = task_text
    except AttributeError:
        pass


def display_analyze_button(self: "MyGui", _row: int, first_time: bool) -> None:
    """
    Display or update the 'Analyze' button for the AI API key.
    """
    # Make sure Ai model is blank if value is "None"
    if self.ai_model == "None":
        self.ai_model = ""

    # Highlight the button if we have everything to run the Analysis.
    if is_valid_ai_config(self) and (self.single_task_name or self.single_profile_name or self.single_project_name):
        # Make it pink
        bg_color = "#f55dff"
        text_color = "#FFFFFF"
    else:
        # Otherwise, use the default blue.
        bg_color = "#246FB6"
        text_color = "#FFFFFF"

    # Define the exact CSS string to apply
    # We include the border color here since it was defined in your original add_button
    css_style = f"background-color: {bg_color}; color: {text_color}; border: 2px solid #6563ff;"

    # If first time (or the button doesn't exist yet), create it.
    if first_time or not getattr(self, "ai_analyze_button", None):
        pass
        # Assuming self.tab_analyze is the ui.tab_panel("Analyze") container
        # with self.tab_analyze:
        # self.ai_analyze_button = (
        #     ui
        #     .button("Run Analysis", on_click=self.event_handlers.ai_analyze_event)
        #     .style(css_style)
        #     .classes("mx-auto mt-4 px-8 py-2 font-bold")
        # )
        # mx-auto centers it (like sticky="n")
        # px-8 py-2 adds horizontal and vertical padding (like padx=50, pady=(10,10))

    else:
        # Not first time, just reconfigure the colors of the existing button.
        # Calling .style() on an existing NiceGUI element instantly updates its CSS!
        self.ai_analyze_button.style(css_style)


# Make sure the single named item exists...that it is a valid name
def valid_item(
    self: object,
    the_name: str,
    element_name: str,
    debug: bool,
    appearance_mode: str,
) -> bool:
    """
    Checks if an item name is valid
    Args:
        the_name: String - Name to check
        element_name: String - Element type being checked
        debug: boolean - GUI debug mode True or False
        appearance_mode: String - Light/Dark/System
    Returns:
        Boolean - Whether the name is valid
    Processing Logic:
    - Initialize temporary primary items object
    - Get backup xml data and root elements
    - Match element type and get corresponding root element
    - Check if item name exists by going through all names in root element
    """
    if the_name == "None" or the_name == translate_string("None"):
        return True
    # Set our file to get the file from the local drive since it had previously been pulled from the Android device.
    # Setting PrimeItems.program_arguments["file"] will be used in get_xml() and won't prompt for file if it exists.
    filename_location = self.android_file.rfind(PrimeItems.slash) + 1
    if filename_location != 0:
        PrimeItems.program_arguments["file"] = self.android_file[filename_location:]
    elif self.file:
        PrimeItems.program_arguments["file"] = self.file
    else:
        _ = self.prompt_and_get_file(self.debug, self.appearance_mode)

    # Get the XML data only if it hasn't been loaded yet
    if (
        not PrimeItems.tasker_root_elements["all_projects"]
        and not PrimeItems.tasker_root_elements["all_profiles"]
        and not PrimeItems.tasker_root_elements["all_tasks"]
    ):
        PrimeItems.program_arguments["directory"] = self.directory
        PrimeItems.program_arguments["list_unnamed_items"] = self.list_unnamed_items
        return_code = get_xml(debug, appearance_mode)

        # Did we get an error reading the backup file?
        if return_code > 0:
            if return_code == 6:
                PrimeItems.error_msg = "Cancel button pressed."
            PrimeItems.error_code = 0
            return False

    # Set up for name checking
    # Find the specific item and get it's root element
    root_element_choices = {
        "Project": PrimeItems.tasker_root_elements["all_projects"],
        "Profile": PrimeItems.tasker_root_elements["all_profiles"],
        "Task": PrimeItems.tasker_root_elements["all_tasks"],
    }
    root_element = root_element_choices[element_name]

    # Special case if Task.
    if root_element == PrimeItems.tasker_root_elements["all_tasks"] and UNNAMED_ITEM in the_name:
        task_id = get_taskid_from_unnamed_task(the_name)
        return task_id in root_element

    # See if the item exists by going through all names.  Get rtid of "Project: " or "Profile: " portion of name.
    colon = the_name.find(":")
    if colon != -1:
        the_name = the_name[colon + 1 :].lstrip()
    return any(root_element[item]["name"] == the_name for item in root_element)


_LOGO_URL_PATH = "/assets_logos"
_logo_static_files_mounted = False


def add_logo(self: "MyGui", logo_name: str) -> None:
    """
    Add a logo to the screen dynamically via NiceGUI.

    Instead of grid coordinates, layouts are handled naturally inside their parent panels
    (the sidebar drawer, the tab panel, etc.).
    """
    global _logo_static_files_mounted  # noqa: PLW0603

    # 1. Determine the path to the assets directory and serve it over HTTP.
    # Browsers refuse to load "file://" URLs referenced from a page served over
    # "http://", so ui.image() needs a URL NiceGUI actually serves -- mount the
    # assets directory once (subsequent calls, e.g. once per flag, are no-ops).
    abspath = os.path.abspath(__file__)
    assets_dir = os.path.dirname(abspath).replace("src", "assets")
    if not _logo_static_files_mounted:
        app.add_static_files(_LOGO_URL_PATH, assets_dir)
        _logo_static_files_mounted = True

    doing_flag = logo_name.startswith("flag")

    if doing_flag:
        language = logo_name.split("flag_")[1]
        img_src = f"{_LOGO_URL_PATH}/icons/{language}.png"
        size_classes = "w-[25px] h-[16px]"
        # parent = self.gui_left_drawer  # <--- FIX: Point to NiceGUI left drawer element
        parent = self.language_label
    elif logo_name == "maptasker":
        light_src = f"{_LOGO_URL_PATH}/maptasker_logo_light.png"
        dark_src = f"{_LOGO_URL_PATH}/maptasker_logo_dark.png"
        size_classes = "w-[190px] h-[50px]"
        parent = self.gui_left_drawer  # <--- FIX: Point to NiceGUI left drawer element
    elif logo_name == "coffee":
        img_src = f"{_LOGO_URL_PATH}/bmc-logo-no-background.png"
        size_classes = "w-[36px] h-[54px]"
        parent = self.gui_debug_panel  # tab_debug is the tab button, not its content panel
    else:
        if "rutroh_error" in globals():
            rutroh_error("Invalid logo type")
        return

    # 2. Render the images using NiceGUI context rules
    with parent:  # <--- This will now succeed perfectly!
        try:
            # MapTasker requires handling an explicit dark mode swap swap over the web
            if logo_name == "maptasker":
                # Render the light version (hidden when dark class is applied to html)
                ui.image(light_src).classes(f"{size_classes} block dark:hidden object-contain")
                # Render the dark version (hidden by default, shown when dark class is applied)
                ui.image(dark_src).classes(f"{size_classes} hidden dark:block object-contain")
            else:
                # Flags and Coffee do not change based on dark mode status
                ui.image(img_src).classes(f"{size_classes} object-contain")

        except Exception as e:  # noqa: BLE001
            if "rutroh_error" in globals():
                rutroh_error(f"Error displaying {logo_name} logo: {e}")

        # 3. Handle the structural coffee button appending
        if logo_name == "coffee":
            with ui.row().classes("items-center gap-2 mt-2"):
                self.coffee_button = ui.button(
                    translate_string("Buy Me A Coffee"),
                    on_click=self.event_handlers.coffee_event,
                ).classes("bg-blue-600 text-white font-bold")


def set_ai_key(self: object, model: str) -> None:
    """
    Set the API key for the AI service based on the selected model.

    Args:
        self (object): The instance of the class.
        model (str): The model name for which to set the API key.

    Returns:
        None
    """
    # Set the appropriate API key based on the model chosen.  This doesn't apply to llama (no apikey).
    model_keys = {
        **dict.fromkeys(PrimeItems.ai["openai_models"], "openai_key"),
        **dict.fromkeys(PrimeItems.ai["anthropic_models"], "anthropic_key"),
        **dict.fromkeys(PrimeItems.ai["deepseek_models"], "deepseek_key"),
        **dict.fromkeys(PrimeItems.ai["gemini_models"], "gemini_key"),
    }
    ai_to_get = model_keys.get(model, "")
    if not ai_to_get:
        return False
    self.ai_apikey = PrimeItems.ai.get(ai_to_get)

    # If we didn't find the key, then see if we are using the extended list and need to get the key.
    if not self.ai_apikey and self.ai_model_extended_list:
        self.ai_apikey = get_api_key()
        # Try again using the updated model list.
        self.ai_apikey = PrimeItems.ai.get(model_keys.get(model, ""), "")

    return bool(self.ai_apikey)


# Display startup messages which are a carryover from the last run.
def display_error_file_and_ai_response(self) -> None:  # noqa: ANN001
    """
        Displays messages from the last run.
    #
        This function checks if there are any carryover error messages from the last run (rerun).
        If there are, it reads the error message from the file specified by the `ERROR_FILE` constant and handles
        potential missing modules. If the error message contains the string "Ai Response", it displays the
        error message in a new toplevel window and displays a message box indicating that the analysis response
        is in a separate window and saved as `ANALYSIS_FILE`. If the error message contains newline characters,
        it breaks the message up into multiple lines and displays each line in a message box. If the error message
        does not contain newline characters, it displays the error message in a message box. After displaying the
        error message, it removes the error file to prevent it from being displayed again.

        If there is an error message from other routines, it displays the error message in a message box with the return code.

        Parameters:
        - None

        Returns:
        - None
    """
    from maptasker.src.userintr import MyGui  # noqa: PLC0415

    logger.info("Displaying messages from last run.")
    gui = self if isinstance(self, MyGui) else self.gui

    analysis_response = ""
    error_msg = ""

    # Handle Ai Response and display it
    if os.path.isfile(ANALYSIS_FILE):
        with open(ANALYSIS_FILE) as analysis_file:
            analysis_response = analysis_file.read()
            gui.display_ai_response(analysis_response)

    # See if we have any error messages from the AI analysis.
    elif os.path.isfile(ERROR_FILE):
        with open(ERROR_FILE) as error_file:
            error_msg = error_file.read()

            # Some other message.  Just display it in the message box and break it up if needed.
            if "\n" in error_msg:
                messages = error_msg.split("\n")
                for message_line in messages:
                    gui.display_message_box(message_line, "Red")
            else:
                gui.display_message_box(error_msg, "Red")

    # Get rid of any error message so we don't display it again.
    try:
        os.remove(ERROR_FILE)
    except PermissionError:
        # If the error file is locked up by us, then just rename the file.
        print(f"Unable to delete the error file: {ERROR_FILE}.  You must delete it manually!")
    except FileNotFoundError:
        pass

    # Display any error message from other rountines
    if PrimeItems.error_msg:
        gui.display_message_box(
            f"{PrimeItems.error_msg} with return code {PrimeItems.error_code}.",
            "Red",
        )

    if hasattr(gui, "tab_to_use") and hasattr(gui, "main_tabs_container"):
        gui.main_tabs_container.set_value = gui.tab_to_use


# Write out the changelog defined in guiutils after updating the app from pypi.
def create_changelog() -> None:
    """Create changelog file."""
    changes = get_changelog_file(CHANGELOG_URL, "##", 11)
    with open(CHANGELOG_FILE, "w") as changelog_file:
        for change in changes:
            changelog_file.write(f"{change}\n")


# Reload the program
def reload_gui(self: object) -> None:
    """
    Reload the GUI by running a new process with the new program/version.

    This function reloads the GUI by running a new process using the `os.execl` function.
    The new process will load and run the new program/version.

    Note:
        - This function will cause an OS error, 'python[35833:461355] Task policy set failed: 4 ((os/kern) invalid argument)'.
        - The current process will not return after this call, but will simply be killed.

    Parameters:
        *args (list): A variable-length argument list of command-line arguments to be passed to the new process.

    Returns:
        None
    """
    # Save the last-used tab
    self.tab_to_use = self.gui_main_tabs_container.value.label if hasattr(self, "gui_main_tabs_container") else None

    # Save the settings
    temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}
    _, _ = save_restore_args(temp_args, self.color_lookup, to_save=True)

    # ReRun via a new process, which will load and run the new program/version.
    # Note: this current process will not return after this call, but simply be killed.
    restart_program_subprocess()


# Ping the Android evice to make sure it is reachable.
async def ping_android_device(self: "MyGui", ipaddr: str, port: str) -> bool:
    """
    Asynchronously checks if the target Android device and Tasker server are reachable.

    Instead of a generic ping or raw socket connect, this utilizes the app's native
    'http_request' functionality inside a background thread pool to ensure total accuracy.
    """

    # 1. Define the internal network check using your app's true HTTP handshake logic.
    # This executes inside a worker thread pool, keeping NiceGUI's loop operational.
    def raw_tasker_probe() -> bool:
        try:
            # We execute a minimal 'maplist' directory poll on the standard directory.
            # If the Tasker server is running, this function will cleanly complete.
            return_code, _ = http_request(
                ipaddr,
                port,
                "/storage/emulated/0/Tasker",
                "maplist",
                "?xml",
            )
            # return_code == 0 means a flawless connection was made!
            return return_code == 0  # noqa: TRY300
        except Exception:  # noqa: BLE001
            return False

    # Show a brief non-blocking notification toast to show progress
    ui.notify(f"Connecting to Android device at {ipaddr}:{port}...", type="info", timeout=1200)

    try:
        # 2. Hand off the logic block to NiceGUI's asynchronous thread executor
        device_is_reachable = await run.io_bound(raw_tasker_probe)

        if device_is_reachable:
            return True

        # Handle connectivity breakdown state safely
        error_msg = (
            f"{translate_string('Error')}: {translate_string('Android device at')} {ipaddr}:{port} "
            f"{translate_string('is unreachable')}. {translate_string('Check your IP/Port and verify the Tasker HTTP server is running')}."
        )
        self.display_message_box(error_msg, "Red")
        return False  # noqa: TRY300

    except Exception as e:  # noqa: BLE001
        self.display_message_box(f"Ping execution failure: {e!s}", "Red")
        return False


def validate_or_filelist_xml(
    self: "MyGui",
    android_ipaddr: str,
    android_port: str,
    android_file: str,
) -> tuple[int, str, str, str]:
    """
    Validates an XML file on an Android device or generates a NiceGUI dropdown
    selection list if no file or an explicit 'list files' action is requested.
    """
    # 1. If a file is specified and we aren't explicitly listing files, validate it
    if len(android_file) != 0 and android_file != "" and not self.list_files:
        return_code, _ = http_request(
            android_ipaddr,
            android_port,
            android_file,
            "file",
            "?download=1",
        )

        # Validate the XML syntax structure
        if return_code == 0:
            PrimeItems.program_arguments["gui"] = True
            return_code, error_message = validate_xml_file(
                android_ipaddr,
                android_port,
                android_file,
            )
            if return_code != 0:
                self.display_message_box(error_message, "Red")
                return 1, android_ipaddr, android_port, android_file
        else:
            return 1, android_ipaddr, android_port, android_file

    # 2. File location not provided or "List Files" requested.
    # Fetch the directory catalog and present a NiceGUI ui.select component.
    else:
        clear_android_buttons(self)

        return_code, filelist = get_list_of_files(
            android_ipaddr,
            android_port,
            "/storage/emulated/0/Tasker",
        )
        if return_code != 0:
            self.display_message_box(filelist, "Red")
            return 1, android_ipaddr, android_port, android_file

        # Clean slate the container before rendering the picker options
        if hasattr(self, "android_container") and self.android_container:
            self.android_container.clear()
            self.android_container.classes(remove="hidden")
        else:
            # Fallback placeholder if no container container is declared
            self.android_container = ui.column().classes("w-full gap-2 p-2")

        # Mount the native interactive picking layout inside the container tree context
        with self.android_container:
            ui.separator().classes("my-2")

            self.filelist_label = ui.label(translate_string("Select XML From Android Device:")).classes(
                "text-xs font-bold text-purple-600 mt-1 self-start",
            )

            # Custom Tkinter OptionMenu transforms to a reactive NiceGUI ui.select dropdown
            self.filelist_option = ui.select(
                options=filelist,
                label=translate_string("Available Android Backups"),
                on_change=lambda e: self.event_handlers.file_selected_event(e.value),
            ).classes("w-full q-mt-none")

            # Flat modern action button to easily close the selection panel
            ui.button(
                translate_string("Cancel Entry"),
                on_click=lambda: (self.android_container.clear(), self.android_container.classes(add="hidden")),
            ).classes("text-xs w-full mt-2").props("outline color=negative dense")

        # Save connection details to state
        self.android_ipaddr = android_ipaddr
        self.android_port = android_port

        # Return status code 2 to indicate layout suspension until user selects a file item.
        return (2, "", "", "")

    # All checks passed successfully
    return 0, android_ipaddr, android_port, android_file


# List the XML files on the Android device
def get_list_of_files(ip_address: str, ip_port: str, file_location: str) -> tuple:
    """Get list of files from given IP address.
    Parameters:
        - ip_address (str): IP address to connect to.
        - ip_port (str): Port number to connect to.
        - file_location (str): Location of the file to retrieve.
    Returns:
        - tuple: Return code and list of file locations.
    Processing Logic:
        - Retrieve file contents using http_request.
        - If return code is 0, split the decoded string into a list and return.
        - Otherwise, return error with empty string."""

    # Get the contents of the file.
    return_code, file_contents = http_request(
        ip_address,
        ip_port,
        file_location,
        "maplist",
        "?xml",
    )

    # If good return code, get the list of XML file locations into a list and return.
    if return_code == 0:
        decoded_string = (file_contents.decode("utf-8")).split(",")
        # Strip off the count field
        for num, item in enumerate(decoded_string):
            temp_item = item[:-3]  # Drop last 3 characters
            decoded_string[num] = temp_item.replace("/storage/emulated/0", "")
        # Remove items that are in the trash
        final_list = [item for item in decoded_string if ".Trash" not in item]
        return 0, final_list

    # Otherwise, return error
    return return_code, file_contents


# Read the change log file, add it to the messages to be displayed and then remove it.
def check_for_changelog(self) -> None:  # noqa: ANN001
    """Function to check for a changelog file and add its contents to a message if the current version is correct.
    Parameters:
        - self (object): The object that the function is being called on.
    Returns:
        - None: The function does not return anything, but updates the message attribute of the object.
    Processing Logic:
        - Check if the changelog file exists.
        - If it exists, prepare to display changes and remove the file so we only display the changes once.
    Note: The changelog file is created immediately after the program is updated (userintr upgrade_event)
    """
    logger.info("Checking for changelog file.")

    # # TODO Test changelog before posting to PyPi.  Comment it out after testing.
    # self.message = "\n".join(get_changelog_file(CHANGELOG_URL, "##", 11))
    # return
    # # TODO END Test

    self.message = "\n\n"
    if os.path.isfile(CHANGELOG_FILE):
        with open(CHANGELOG_FILE) as changelog_file:
            for line in changelog_file:
                self.message = f"{self.message}{line}"
        os.remove(CHANGELOG_FILE)


# Get Pypi version and return True if it is newer than our current version.
def is_new_version() -> bool:
    """
    Check if the new version is available
    Args:
        self: The class instance
    Returns:
        bool: True if new version is available, False if not"""
    # Check if newer version of our code is available on Pypi.
    pypi_version_code = get_pypi_version()
    if pypi_version_code:
        pypi_version = pypi_version_code.split("==")[1]
        PrimeItems.last_run = NOW_TIME  # Update last run to now since we are doing the check.
        return is_version_greater(VERSION, pypi_version)
    return False


def check_new_version(self: "MyGui") -> None:
    """Check if a new version is available and dynamically populate
    the upgrade container slot inside the right sidebar.
    """
    if not is_first_run_today():
        logger.info("Not the first run today. Skipping new version check.")
        return

    # Set test_button to True for development testing, False for production.
    test_button = False
    if is_new_version() or test_button:
        # 1. Clear out any stale visual elements and unhide the sidebar placeholder slot
        self.upgrade_container.clear()
        self.upgrade_container.classes(remove="hidden")

        # 2. Render the interactive upgrade controls directly inside the target container context
        with self.upgrade_container:
            ui.label(translate_string("Update Available!")).classes(
                "text-sm font-bold text-green-600 dark:text-green-400 mt-2",
            )

            # 'Upgrade to Latest Version' Button
            self.upgrade_button = (
                ui
                .button(translate_string("Upgrade to Latest Version"), on_click=self.event_handlers.upgrade_event)
                .style("background-color: #79ff94; color: #6563ff;")
                .classes("w-full font-bold text-xs py-2")
            )

            # 'What's New' Button
            self.whats_new_button = (
                ui
                .button(translate_string("What's New?"), on_click=self.event_handlers.whatsnew_event)
                .style("background-color: #246FB6; border-color: #79ff94; border-width: 1px; color: white;")
                .classes("w-full text-xs")
            )
            ui.update()  # Force NiceGUI to update the UI immediately

        self.message = self.message + "\n\n" + translate_string("A new version of MapTasker is available.")


def is_first_run_today(filename: str = ".maptasker_last_run.txt") -> bool:
    """Checks if this is the first time the function has been executed today.

    Saves the current date to a file. If the file doesn't exist or contains
    a older date, it returns True. Otherwise, it returns False.
    """
    # 1. Get today's date as a string (YYYY-MM-DD)
    today_str = str(date.today())  # noqa: DTZ011

    # 2. Check if the tracking file exists
    if os.path.exists(filename):
        with open(filename) as file:
            last_run_str = file.read().strip()

        # If the date in the file matches today, it's NOT the first run
        if last_run_str == today_str:
            return False

    # 3. If file doesn't exist OR the date is old, update the file and return True
    with open(filename, "w") as file:
        file.write(today_str)

    return True


# Compare two versions and return True if version2 is greater than version1.
def is_version_greater(version1: str, version2: str) -> bool:
    """
    This function checks if version2 is greater than version1.

    Args:
        version1: A string representing the first version in the format "major.minor.patch".
        version2: A string representing the second version in the format "major.minor.patch".

    Returns:
        True if version2 is greater than version1, False otherwise.
    """

    # Split the versions by "."
    if "b" in version2 or "b" in version1:
        # Ignore beta versions for now.  We don't want to offer an update to a beta version.
        return False
    v1_parts = [int(x) for x in version1.split(".")]
    v2_parts = [int(x) for x in version2.split(".")]

    # Iterate through each part of the version
    for i in range(min(len(v1_parts), len(v2_parts))):
        if v1_parts[i] < v2_parts[i]:
            return True
        if v1_parts[i] > v2_parts[i]:
            return False

    # If all parts are equal, check length
    return len(v2_parts) > len(v1_parts)
