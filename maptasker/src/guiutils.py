"""Utilities used by GUI (NiceGUI Version)"""

import contextlib
import os
import tkinter as tk
from collections.abc import Callable
from tkinter import font as tkfont
from typing import TYPE_CHECKING

import defusedxml
from nicegui import ui

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
from maptasker.src.lineout import LineOut
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputils import restart_program_subprocess
from maptasker.src.primitem import PrimeItems
from maptasker.src.profiles import get_profile_tasks
from maptasker.src.proginit import get_data_and_output_intro
from maptasker.src.sysconst import ARGUMENT_NAMES, ERROR_FILE, MODEL_GROUPS, UNNAMED_ITEM, logger

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui


# ==========================================
# 1. NOTIFICATIONS & FEEDBACK
# ==========================================
def output_label(view_instance: object, text: str) -> None:
    """
    Replaces the old status label updates.
    Displays a toast notification to the user in the browser.
    """
    logger.info(f"GUI Message: {text}")
    # Determine message type based on keywords for color-coding
    msg_type = "negative" if "error" in text.lower() or "could not" in text.lower() else "positive"

    ui.notify(text, type=msg_type, position="bottom-right", timeout=3000)


def display_no_xml_message(gui_instance: object) -> None:
    """Displays an error if no XML is loaded."""
    ui.notify("No XML data loaded! Please Get XML from Android or Local drive first.", type="warning", position="top")


# ==========================================
# 2. DYNAMIC COMPONENT UPDATERS
# ==========================================
def display_model_pulldown(gui_instance: "MyGui", tab: object = None) -> None:
    """
    Updates or creates the AI model dropdown.
    In NiceGUI, we update the existing `ui.select` options instead of destroying/recreating widgets.
    """
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
        has_all = bool(gui_instance.ai_apikey and gui_instance.ai_model and gui_instance.ai_prompt)
        gui_instance.analysis_button.props(f"color={'green' if has_all else 'red'}")


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

    # Get rid of previous data
    # delete_old_pulldown_menus(self)

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

    # Display the object pulldowns in 'Analyze' tab
    self.ai_project_optionmenu, self.ai_profile_optionmenu, self.ai_task_optionmenu = display_object_pulldowns(
        self,
        self.tab_analyze,
        projects_to_display,
        profiles_to_display,
        tasks_to_display,
        self.event_handlers.single_project_name_event,
        self.event_handlers.single_profile_name_event,
        self.event_handlers.single_task_name_event,
    )

    # Display the object pulldowns in 'Specific Name' tab
    if not projects_to_display:  # If no Projects to display
        projects_to_display = [translate_string("None")]
    (
        self.specific_project_optionmenu,
        self.specific_profile_optionmenu,
        self.specific_task_optionmenu,
    ) = display_object_pulldowns(
        self,
        self.tab_specific_name,
        projects_to_display,
        profiles_to_display,
        tasks_to_display,
        self.event_handlers.single_project_name_event,
        self.event_handlers.single_profile_name_event,
        self.event_handlers.single_task_name_event,
    )
    return True


def display_object_pulldowns(
    self: "MyGui",
    container: ui.element,
    projects_to_display: list,
    profiles_to_display: list,
    tasks_to_display: list,
    project_name_event: Callable,
    profile_name_event: Callable,
    task_name_event: Callable,
) -> tuple:
    """
    Updates the pulldown menus for selecting projects, profiles, and tasks.
    """

    # If the container is tab_specific_name, we just update the options for the widgets we created in guiwins.py
    if container == self.tab_specific_name:
        if hasattr(self, "specific_project_optionmenu") and self.specific_project_optionmenu:
            # 1. Assign the new lists to the options attributes
            self.specific_project_optionmenu.options = projects_to_display
            self.specific_profile_optionmenu.options = profiles_to_display
            self.specific_task_optionmenu.options = tasks_to_display

            # 2. Attach the event listeners using NiceGUI's .on() method
            # We clear existing listeners first to prevent duplicates if this function is called multiple times
            self.specific_project_optionmenu.clear()
            self.specific_project_optionmenu.on(
                "update:model-value",
                lambda e: project_name_event(e.args) if e.args else None,
            )

            self.specific_profile_optionmenu.clear()
            self.specific_profile_optionmenu.on(
                "update:model-value",
                lambda e: profile_name_event(e.args) if e.args else None,
            )

            self.specific_task_optionmenu.clear()
            self.specific_task_optionmenu.on(
                "update:model-value",
                lambda e: task_name_event(e.args) if e.args else None,
            )

            # 3. CRITICAL: Tell the browser to re-render the widgets with the new options
            self.specific_project_optionmenu.update()
            self.specific_profile_optionmenu.update()
            self.specific_task_optionmenu.update()

        return self.specific_project_optionmenu, self.specific_profile_optionmenu, self.specific_task_optionmenu

    project_option = profile_option = task_option = None

    # 'with container:' tells NiceGUI to draw everything inside this specific UI block
    with container:
        # Make sure there is something to display
        if not projects_to_display and not profiles_to_display and not tasks_to_display:
            self.current_object_label = ui.label("No Projects, Profiles or Tasks to display!").classes(
                "text-red-500 font-bold mt-4",
            )

        # Okay, we have some actual data to display
        else:
            # Display all of the Projects for selection.
            self.select_project_label = ui.label("Select Project to process:").classes("mt-2 text-sm font-semibold")
            project_option = ui.select(
                options=projects_to_display,
                on_change=lambda e: project_name_event(e.value) if e.value else None,
            ).classes("w-full max-w-sm")

            # Display all of the Profiles for selection.
            self.select_profile_label = ui.label("Select Profile to process:").classes("mt-4 text-sm font-semibold")
            profile_option = ui.select(
                options=profiles_to_display,
                on_change=lambda e: profile_name_event(e.value) if e.value else None,
            ).classes("w-full max-w-sm")

            # Display all of the Tasks for selection.
            self.task_label = ui.label("Select Task to process:").classes("mt-4 text-sm font-semibold")
            task_option = ui.select(
                options=tasks_to_display,
                on_change=lambda e: task_name_event(e.value) if e.value else None,
            ).classes("w-full max-w-sm")

    return project_option, profile_option, task_option


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
        tasks_to_display = ["No tasks found"]
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


# Delete old pulldown menus since the older selected items could be longer than the new,
# and both will appear.
def delete_old_pulldown_menus(self: object) -> None:
    """Delete old pulldown menus if they exist."""
    for attr in (
        "specific_project_optionmenu",
        "specific_profile_optionmenu",
        "specific_task_optionmenu",
        "ai_project_optionmenu",
        "ai_profile_optionmenu",
        "ai_task_optionmenu",
        "single_label",
        "select_project_label",
        "select_profile_label",
        "task_label",
    ):
        widget = getattr(self, attr, None)
        if widget:
            with contextlib.suppress(Exception):
                widget.delete()  # NiceGUI uses .delete() to remove widgets.
            # Best practice: clear the reference so your logic knows it's gone
            setattr(self, attr, None)


def display_selected_object_labels(self: "MyGui") -> None:
    """
    Display the current settings for Ai
    """
    # 1. Data Resolution (Kept identical to your original logic)
    if not self.ai_model:
        all_models = {
            "OpenAI": PrimeItems.ai["openai_models"],
            "anthropic": PrimeItems.ai["anthropic_models"],
            "LLAMA": PrimeItems.ai["llama_models"],
            "DeepSeek": PrimeItems.ai["deepseek_models"],
            "Gemini": PrimeItems.ai["gemini_models"],
        }
        for ai, models in all_models.items():
            if self.ai_model in models:
                self.ai_model = ai
                break

    if not self.ai_apikey:
        self.ai_apikey = get_api_key()

    key_to_display = "N/A" if getattr(self, "ai_name", "") == "LLAMA" else "Unset" if not self.ai_apikey else "Set"
    model_to_display = self.ai_model if self.ai_model else "None"

    none_translated = translate_string("None")
    project_to_display = self.single_project_name if self.single_project_name else none_translated
    profile_to_display = self.single_profile_name if self.single_profile_name else none_translated
    task_to_display = self.single_task_name if self.single_task_name else none_translated

    # 2. Render the "Analyze" Tab
    # Assuming self.tab_analyze is the ui.tab_panel("Analyze") you created elsewhere
    with self.tab_analyze:
        # Instead of `delete_ai_labels(self)`, we just clear the container.
        self.tab_analyze.clear()

        # Display Model & Key
        ui.label(f"{getattr(self, 'ai_name', '')} API Key: {key_to_display}, Model: {model_to_display}").classes(
            "text-sm mt-4",
        )

        # Update Pulldown
        if getattr(self, "ai_model_option", None):
            # In NiceGUI, ui.select uses `.value` instead of `.set()`
            self.ai_model_option.value = [model_to_display]
        else:
            display_model_pulldown(self, 50)

        # Display Targets
        translation_proj = translate_string("Project to Analyze:")
        ui.label(f"{translation_proj} {project_to_display}").classes("text-sm mt-2")

        translation_prof = translate_string("Profile to Analyze:")
        ui.label(f"{translation_prof} {profile_to_display}").classes("text-sm mt-4")

        translation_task = translate_string("Task to Analyze:")
        ui.label(f"{translation_task} {task_to_display}").classes("text-sm mt-2")

        # Display Prompt
        display_prompt = translate_string(self.ai_prompt)
        prompt_title = translate_string("Prompt:")

        # Web browsers handle text wrapping automatically!
        # We use Tailwind classes to limit width (max-w-md) and force wrapping (whitespace-pre-wrap).
        ui.label(f"{prompt_title} '{display_prompt}'").classes(
            "text-base mt-4 max-w-md whitespace-pre-wrap break-words",
        )

    # 3. Render the "Specific Name" Tab
    # Assuming self.tab_specific_name is your ui.tab_panel("Specific Name")
    with self.tab_specific_name:
        all_objects = translate_string("Display all Projects, Profiles, and Tasks.")
        name_to_display = self.specific_name_msg if getattr(self, "specific_name_msg", None) else all_objects

        # Just update the text of the existing label rather than recreating it
        if hasattr(self, "specific_name_msg_label") and self.specific_name_msg_label:
            self.specific_name_msg_label.text = name_to_display
        else:
            with self.tab_specific_name:
                self.specific_name_msg_label = ui.label(name_to_display).classes("text-xs ml-2 mt-2 text-left")


# ==========================================
# 3. PROGRESS BAR MANAGEMENT
# ==========================================
def display_progress_bar(progress_dict: dict, is_instance_method: bool = False) -> None:
    """
    Updates the value of an existing NiceGUI linear_progress element.
    """
    if not progress_dict or "progress_widget" not in progress_dict:
        return

    # Calculate the percentage (0.0 to 1.0)
    current = progress_dict.get("progress_counter", 0)
    maximum = progress_dict.get("max_data", 1)

    # Update the NiceGUI element directly
    percentage = min(current / maximum, 1.0)
    progress_dict["progress_widget"].value = percentage


def kill_the_progress_bar(progress_dict: dict, remove_windows: bool = True) -> None:
    """
    Closes the progress bar dialog.
    """
    if progress_dict and "dialog" in progress_dict:
        progress_dict["dialog"].close()


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

    # Save the settings
    temp_args = {value: getattr(self, value) for value in ARGUMENT_NAMES}
    _, _ = save_restore_args(temp_args, self.color_lookup, to_save=True)

    # ReRun via a new process, which will load and run the new program/version.
    # Note: this current process will not return after this call, but simply be killed.
    restart_program_subprocess()


def reset_primeitems_single_names() -> None:
    """
    Reset the prime items related to single names.
    """
    PrimeItems.found_named_items = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }
    PrimeItems.directory_items = {
        "current_item": "",
        "projects": [],
        "profiles": [],
        "tasks": [],
        "scenes": [],
    }
    PrimeItems.program_arguments["single_project_name"] = ""
    PrimeItems.program_arguments["single_profile_name"] = ""
    PrimeItems.program_arguments["single_task_name"] = ""
    PrimeItems.found_named_items = {
        "single_project_found": False,
        "single_profile_found": False,
        "single_task_found": False,
    }


def display_current_file(self: "MyGui", file_name: str) -> None:
    """
    A function to display the current file as a label in the GUI.
    """
    # 1. Cleaner File Path Parsing
    # Python's built-in os.path.basename handles slashes (both / and \) automatically
    clean_file_name = os.path.basename(file_name)

    # 2. Translation Logic (Kept identical)
    text = "Current File"
    text = PrimeItems._(text) if hasattr(PrimeItems, "_") else text
    full_display_text = f"{text}: {clean_file_name}"

    # 3. The NiceGUI Way: Update text rather than destroying and recreating the element
    if getattr(self, "current_file_label", None):
        # If the label already exists, just change its text property!
        self.current_file_label.text = full_display_text
    else:
        # If this is the first time running, create the label.
        # .classes("ml-4 text-left") replaces padx=20 and sticky="w"
        self.current_file_label = ui.label(full_display_text).classes("ml-4 text-left")

    # 4. Update other UI elements (Kept identical)
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

    return get_data_and_output_intro(False)


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
    self.get_backup_button = self.display_backup_button(
        "Get XML from Android Device",
        "#246FB6",
        "#6563ff",
        self.event_handlers.get_xml_from_android_event,
    )


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

    self.ai_project_optionmenu.value = self.single_project_name
    self.specific_profile_optionmenu.value = defaults["profile"]
    self.ai_profile_optionmenu.value = defaults["profile"]
    self.specific_task_optionmenu.value = defaults["task"]
    self.ai_task_optionmenu.value = defaults["task"]
    # self.update() is removed because NiceGUI automatically updates the UI on value changes.


def _set_single_profile_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single profile name is available."""
    # Note: Fixed a missing opening single quote before the profile name from the original code
    self.specific_name_msg = f"{defaults['display_only']}{translate_string('Profile')} '{self.single_profile_name}'"

    try:
        self.specific_profile_optionmenu.value = self.single_profile_name
    except AttributeError:
        return

    self.ai_profile_optionmenu.value = self.single_profile_name
    self.ai_project_optionmenu.value = defaults["project"]
    self.specific_project_optionmenu.value = defaults["project"]
    self.specific_task_optionmenu.value = defaults["task"]
    self.ai_task_optionmenu.value = defaults["task"]


def _set_single_task_name(self: object, defaults: dict) -> None:
    """Handles setting names when a single task name is available."""
    self.specific_name_msg = f"{defaults['display_only']}{translate_string('Task')} '{self.single_task_name}'"

    try:
        self.specific_task_optionmenu.value = self.single_task_name
    except AttributeError:
        return

    self.ai_task_optionmenu.value = self.single_task_name
    self.specific_project_optionmenu.value = defaults["project"]
    self.specific_profile_optionmenu.value = defaults["profile"]
    self.ai_project_optionmenu.value = defaults["project"]
    self.ai_profile_optionmenu.value = defaults["profile"]


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
            self.ai_project_optionmenu.options = [none_text]
            self.ai_project_optionmenu.value = none_text

        if not PrimeItems.tasker_root_elements.get("all_profiles"):
            self.specific_profile_optionmenu.options = [none_text]
            self.specific_profile_optionmenu.value = none_text
            self.ai_profile_optionmenu.options = [none_text]
            self.ai_profile_optionmenu.value = none_text

        if not PrimeItems.tasker_root_elements.get("all_tasks"):
            self.specific_task_optionmenu.options = [none_text]
            self.specific_task_optionmenu.value = none_text
            self.ai_task_optionmenu.options = [none_text]
            self.ai_task_optionmenu.value = none_text

        self.specific_profile_optionmenu.value = profile_text
        self.ai_project_optionmenu.value = project_text
        self.ai_profile_optionmenu.value = profile_text
        self.specific_task_optionmenu.value = task_text
        self.ai_task_optionmenu.value = task_text
    except AttributeError:
        pass


from nicegui import ui


def display_analyze_button(self: "MyGui", row: int, first_time: bool) -> None:
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
        # Assuming self.tab_analyze is the ui.tab_panel("Analyze") container
        with self.tab_analyze:
            self.ai_analyze_button = (
                ui
                .button("Run Analysis", on_click=self.event_handlers.ai_analyze_event)
                .style(css_style)
                .classes("mx-auto mt-4 px-8 py-2 font-bold")
            )
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


def add_logo(self: "MyGui", logo_name: str) -> None:
    """
    Add a logo to the screen dynamically via NiceGUI.

    Instead of grid coordinates, layouts are handled naturally inside their parent panels
    (the sidebar drawer, the tab panel, etc.).
    """
    # 1. Determine the path to the assets directory
    abspath = os.path.abspath(__file__)
    assets_dir = os.path.dirname(abspath).replace("src", "assets")

    doing_flag = logo_name.startswith("flag")

    if doing_flag:
        language = logo_name.split("flag_")[1]
        img_src = f"file://{assets_dir}/icons/{language}.png"
        size_classes = "w-[25px] h-[16px]"
        parent = self.left_drawer  # <--- FIX: Point to NiceGUI left drawer element
    elif logo_name == "maptasker":
        light_src = f"file://{assets_dir}/maptasker_logo_light.png"
        dark_src = f"file://{assets_dir}/maptasker_logo_dark.png"
        size_classes = "w-[190px] h-[50px]"
        parent = self.left_drawer  # <--- FIX: Point to NiceGUI left drawer element
    elif logo_name == "coffee":
        img_src = f"file://{assets_dir}/bmc-logo-no-background.png"
        size_classes = "w-[36px] h-[54px]"
        parent = self.tab_debug  # This works because tab_debug is a ui.tab_panel element
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


def get_monospace_fonts() -> list[str]:
    """Queries the OS via Tkinter to retrieve available monospaced fonts."""
    # Create a hidden root window to initialize the font subsystem
    root = tk.Tk()
    root.withdraw()

    mono_fonts = []
    # Get all unique families available on the system
    all_fonts = sorted(set(tkfont.families()))

    for f in all_fonts:
        try:
            # Create a font object and check if it has fixed-width properties
            current_font = tkfont.Font(family=f, size=12)
            if current_font.metrics("fixed"):
                mono_fonts.append(f)
        except Exception as e:  # noqa: BLE001
            rutroh_error(f"Unable to create font object for {f}: {e}")
            continue

    # Clean up the hidden tkinter root instance
    root.destroy()

    # Fallback default values if the system returns an empty list
    if not mono_fonts:
        mono_fonts = ["Courier New", "Courier", "Consolas", "Monospace"]

    return mono_fonts


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
    logger.info("Displaying messages from last run.")
    gui = self.gui
    # See if we have any carryover error messages from last run (rerun).
    if os.path.isfile(ERROR_FILE):
        with open(ERROR_FILE) as error_file:
            error_msg = error_file.read()

            # Handle Ai Response and display it in a new toplevel window
            if "AI Response" in error_msg:
                gui.display_ai_response(error_msg)
                gui.display_message_box(
                    "Analysis response is in a separate Window.",
                    "Turquoise",
                )
                gui.main_tabs_container.set_value = self.tab_to_use

            # Some other message.  Just display it in the message box and break it up if needed.
            elif "\n" in error_msg:
                messages = error_msg.split("\n")
                for message_line in messages:
                    gui.display_message_box(message_line, "Red")
            else:
                gui.display_message_box(error_msg, "Red")
        # Get rid of error message so we don't display it again.
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
