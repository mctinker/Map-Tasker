"""Editor event handlers: the Task, Profile, Scene and Project editors and the Object Properties form.

Split out of userintr.py the same way userintr_android.py and userintr_ai.py were.
EditorEventHandlers is a group of MapTaskerEventHandlers (gui.event_handlers.editors) that holds
every name the dialogs are wired to -- Add, Edit, Rename, Delete, Ok, Save and Save To Current
File for each kind of object, the action and condition editors inside them, and Object Properties.

The four editors moved together because they share their helpers, which are now modules of their own:
userintr_fields reads a dialog's fields back (task_arg_values, profile_condition_values,
apply_scene_field_values), and userintr_finish puts a new object into the loaded configuration
(finish_new_task and its siblings) and reselects an object after a rename (select_renamed_item).
The Save To Android handlers in userintr_android import the field readers from userintr_fields.

The handlers are written one kind to a module -- userintr_editors_task, _project, _scene and _profile,
over what they share in userintr_editors_base -- and this class is the four of them put together, so
everything is still reached as hub.editors.

The dialogs themselves are built in guiwins and its guiwins_* modules, and the edits are made
to the XML by taskedit, profedit, sceneedit and projedit.  This is what the dialogs' buttons do.
"""

from __future__ import annotations

from maptasker.src.gui.userintr_editors_profile import ProfileEditorHandlers
from maptasker.src.gui.userintr_editors_project import ProjectEditorHandlers
from maptasker.src.gui.userintr_editors_scene import SceneEditorHandlers
from maptasker.src.gui.userintr_editors_task import TaskEditorHandlers


class EditorEventHandlers(TaskEditorHandlers, ProjectEditorHandlers, SceneEditorHandlers, ProfileEditorHandlers):
    """The editor handlers: reached as hub.editors; self.hub is the rest of the window's handlers, self.gui the window."""
