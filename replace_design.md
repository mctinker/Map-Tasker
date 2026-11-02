# Replace is a tab in the Find dialog — design note

Status: built (guiwins_search.py).  This is the design the module's `caller_sketch()` carried as
prose until the code existed; it moved here so the GUI-free `mapops/mapswap.py` could shed it.
The text below is the original proposal: it speaks of what the dialog "grows" and names `find_event`
in its old home, where the built version is `guiwins_search.py`'s Find dialog and `build_replace_tab`.

Replace is a second TAB inside the existing Find dialog, not a dialog of its own.

find_event (guiwins.py ~8962) currently opens one ui.dialog holding one ui.card of
pickers.  It grows a ui.tabs()/ui.tab_panels() pair -- "Find" and "Replace" -- and the
Replace panel is built from the same `index` the Find panel already built:

    index = mapfind.build_index()          # unchanged, still per-open, still shared
    with ui.dialog() as dialog, ui.card()...:
        with ui.tabs() as tabs:
            find_tab = ui.tab(translate_string("Find"))
            replace_tab = ui.tab(translate_string("Replace"))
        with ui.tab_panels(tabs, value=find_tab):
            ...the existing pickers, unchanged...
            ...the Replace panel...

THREE THINGS THIS BUYS, which is why it is a tab rather than a dialog:

The index is built once for both.  find_event's own docstring explains why it is
rebuilt on every open and not cached on the view -- 60ms, and a cached one keeps
offering an action of a Task that has been deleted.  A separate Replace dialog would
pay that a second time and, worse, could be opened alongside a Find holding an index
from before an edit.  One dialog, one index, one answer about what is in the file.

The source pulldown is the Find dialog's action pulldown, unchanged.  Same entries,
same counts, built from index.choices(mapfind.ACTION) -- so "Flash (37)" means the
same thing on both tabs, and the count doubles as the number of actions a swap would
touch before any preview is run.

Find becomes the way into Replace.  The natural move is to look for something, see
the 37 places it is, and then decide to change them; switching tabs keeps the
Project narrowing and the action already chosen, so that is one click rather than
re-entering the query in a second window.

THE PROBLEM THE TAB CREATES, AND WHAT IT COSTS TO FIX

jump_to closes the dialog before jumping, and must -- the dialog is modal, so a jump
behind it scrolls a view the user cannot see.  On the Find tab that is free: the query
is remembered on the view (self.find_query) and pressing Find again returns to the
same list.  On the Replace tab it destroys the Plan, and a Plan cannot be remembered
the way a Query can: its Sites hold live elements, and holding them across a dialog
that may have been reopened after another edit is precisely the stale-handle bug
apply()'s BLOCKED_DETACHED check exists to catch.

So the view remembers the INPUTS, not the Plan:

    self.replace_inputs: tuple[str, str, str] | None    # old key, new key, project

and reopening the dialog restores the fields and rebuilds the Plan from scratch.  That
is a second plan() -- one pass over the file, the same order as a Find -- and it is
worth paying every time, because it makes the rule below true by construction rather
than by the dialog remembering to enforce it.

THE RULE THE WHOLE DESIGN IS ARRANGED AROUND

The Replace button is disabled until a preview exists for the values currently in the
fields, and changing any field clears the preview and disables it again.  A user
cannot apply a plan they have not seen, because there is no path through the widgets
that reaches apply() without report_rows() having been drawn first.  Everything else
here -- the separate plan()/apply(), the unticked RESET rows, the skips pinned above
the changes -- is a way of making sure that what they saw was the truth.

Two smaller things the tab inherits for free: from_diagram, so a Replace run from the
Diagram previews with Diagram-preferred jumps exactly as a Find does, and
translate_string on every label, since the Replace panel is new user-facing text and
the rest of this dialog is already translated.
