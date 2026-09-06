"""The impact panel every Delete confirmation dialog puts up before anything is deleted.

One panel rather than four, for the reason the analysis behind it is one module rather than
four: what a delete reaches is a question about the configuration, not about which editor
happens to be asking.  The four dialogs -- guiwins.build_delete_project_dialog and
build_delete_scene_dialog, guiwins_profedit.build_delete_profile_dialog and
guiwins_taskedit.build_delete_task_dialog -- each used to work out their own counts and
word their own sentence about them; all four now call this instead and get the same
answer in the same shape.

It imports nothing from guiwins, so all three dialog modules can import it at the top of
their own files without closing the loop guiwins_taskedit's header describes.  Its one call
into guiwins -- the page-level subscription behind a clicked row -- is made inside the
function that needs it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src import impact, mapjump
from maptasker.src.maputil2 import translate_string

if TYPE_CHECKING:
    from maptasker.src.userintr import MyGui

# How the one-line answer is coloured.  Red only when something will actually be left
# pointing at nothing: a delete that breaks nothing should not be dressed as a warning, or
# the colour stops meaning anything on the delete that does.
_CLEAN_CLASSES = "mt-2 text-sm text-green-700 dark:text-green-400"
_CHANGES_CLASSES = "mt-2 text-sm font-semibold text-amber-700 dark:text-amber-400"
_BREAKS_CLASSES = "mt-2 text-sm font-semibold text-red-600 dark:text-red-400"

# The list is capped and scrolls rather than growing the dialog.  Measured against a real
# backup: deleting one much-called helper Task leaves 55 places dangling, and a dialog that
# tall pushes its own Cancel and Delete buttons off the screen.
_LIST_CLASSES = "w-full max-h-64 overflow-auto border rounded p-2 mt-2"

# How long the click wiring will wait for the browser to have the panel, and how often it
# looks.  Five seconds, which is far longer than it takes and costs nothing when it is not
# needed -- the poll stops the moment the listener is on (see wire_impact_clicks).
_WIRE_ATTEMPTS = 50
_WIRE_INTERVAL_MS = 100


def _summary_classes(analysis: impact.Impact) -> str:
    """What colour this analysis's one-line answer is."""
    if analysis.breaks:
        return _BREAKS_CLASSES
    return _CHANGES_CLASSES if analysis.consequences else _CLEAN_CLASSES


def wire_impact_clicks(self: MyGui, container: ui.element) -> None:
    """Make the impact rows under this container take the user to the place they name.

    The same wiring the report views use (guiwins.enable_finding_clicks), pointed at a
    dialog instead of a scroll area: mapjump.click_wiring_js installs ONE delegated
    listener on whatever container it is given, and the Python subscription that acts on
    what it emits belongs to the page, which the dialog is on.

    Delegated is what makes it worth exposing.  build_impact_panel wires the container it
    draws into, which is all a one-panel dialog needs; the Project dialog draws two panels
    into a tab panel each, and Quasar does not put a tab's content in the DOM until that
    tab is first looked at -- so a listener installed per panel would find nothing to
    attach to and every row on the unopened tab would be dead.  That dialog therefore wraps
    both panels in an element of its own and wires THAT, which catches a click on a row
    whenever the row appears.

    Installed by polling rather than in one shot, which is the difference between this and
    the report views' version and was found by measuring rather than by reasoning: a report
    view is wired into a page that is already on screen, while a dialog is wired while it is
    still being built.  Its elements have not reached the browser at that point, and a Quasar
    dialog does not mount its contents until it is opened in any case -- so a single
    getElementById finds nothing, installs the listener on nothing, and every row in the
    panel is left looking clickable and doing nothing.  The poll stops the moment the
    listener is on, and gives up after a few seconds rather than spinning forever.

    register_finding_clicks is called for the page that never went through
    initialize_screen; on the main window it has already happened and the call is a no-op.
    """
    from maptasker.src.guiwins import register_finding_clicks  # noqa: PLC0415

    register_finding_clicks(self)
    element_id = json.dumps(f"c{container.id}")
    # click_wiring_js is written as a function body -- it returns early when the container
    # is not there yet, and again when it has already been wired -- so calling it on every
    # attempt is safe, and its own guard is what the poll below tests for having finished.
    wiring = mapjump.click_wiring_js(f"c{container.id}")
    ui.timer(
        0.1,
        lambda: ui.run_javascript(f"""
            const install = () => {{ {wiring} }};
            let attempts = 0;
            const attempt = () => {{
                install();
                const panel = document.getElementById({element_id});
                if ((!panel || !panel.dataset.mtFindingClicks) && attempts++ < {_WIRE_ATTEMPTS}) {{
                    setTimeout(attempt, {_WIRE_INTERVAL_MS});
                }}
            }};
            attempt();
        """),
        once=True,
    )


def build_impact_panel(
    self: MyGui,
    kind: str,
    name: str,
    *,
    keep_contents: bool = True,
    wire: bool = True,
) -> None:
    """Draw "what breaks if I delete this" into the confirmation dialog being built.

    'kind' is one of mapjump's PROJECT/PROFILE/TASK/SCENE and 'name' the displayed name --
    the pair the delete itself is about to be called with.  keep_contents is the Project
    dialog's two buttons; every other dialog leaves it alone.

    Three parts, in the order somebody reads them: what the delete takes and leaves, the
    one-line answer, and then the places themselves.  The places are a report rendered by
    mapjump, exactly as the Health Check's are, so each line is clickable and goes to that
    action, Scene element or Profile in the Map view -- which is the point of running the
    scan before the delete rather than discovering the same list afterwards.

    The analysis is run here, while the confirmation is being put up, rather than when the
    editor opened: the editor may have been open a while, and the counts this replaces were
    read at this moment for exactly that reason.

    wire=False leaves the clicks to the caller -- for the Project dialog, which draws two
    of these and has to wire an ancestor of both (see wire_impact_clicks).
    """
    analysis = impact.analyze_delete(kind, name, keep_contents=keep_contents)

    for sentence in analysis.goes:
        ui.label(translate_string(sentence)).classes("mt-1")

    ui.label(translate_string(analysis.summary())).classes(_summary_classes(analysis))

    rows = impact.consequence_rows(analysis)
    if not rows:
        return

    container = ui.element("div").classes(_LIST_CLASSES)
    with container:
        # sanitize=False for the reason NiceGuiTextView gives: the browser's sanitizer
        # strips the data-* attribute each clickable row is identified by, which would
        # leave the rows looking clickable and doing nothing.  mapjump.html_report has
        # already escaped every name in them.
        ui.html(
            f"<pre style='white-space: pre-wrap; font-size: 0.8rem; margin: 0;'>{mapjump.html_report(rows)}</pre>",
            sanitize=False,
        )
    ui.label(
        translate_string("Click any line above to see that place in the Map view."),
    ).classes("text-xs text-gray-500 italic mt-1")
    if wire:
        wire_impact_clicks(self, container)
