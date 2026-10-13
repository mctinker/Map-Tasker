"""The "Check readiness" button and the dialog behind it, for the exports that leave the user's hands.

It sits beside "Redact secrets" in the Edit Project and Edit Scene dialogs, because the two
answer the two halves of one question before a file is shared: redaction says what must not
go with it, and this says what must be on the phone it arrives on.  The answer comes from
readiness.py, which reads the very document the export would write -- so what the dialog lists
is what the recipient would receive.

It imports nothing from guiwins, for guiwins_impact's reason: both editor dialogs call it, and
a module they both import at the top of their own files cannot import either of them back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from maptasker.src.core.maputil2 import translate_string
from maptasker.src.gui.guiwins_editor import build_redact_checkbox
from maptasker.src.mapops import readiness

if TYPE_CHECKING:
    from collections.abc import Callable

    from maptasker.src.core.primitem import RunState

_CARD_CLASSES = "min-w-[500px] max-w-[800px] w-full p-6"
_BODY_CLASSES = "w-full max-h-[60vh] overflow-auto"
_HEADING_CLASSES = "mt-3 font-bold text-blue-600"
_PLACES_CLASSES = "text-sm text-gray-600 dark:text-gray-400"
_EMPTY_CLASSES = "text-sm italic text-gray-500"
_LIMITS_CLASSES = "mt-3 text-xs text-gray-500"


def build_readiness_dialog(report: readiness.Readiness) -> None:
    """Show what a configuration needs on another phone, with a button to copy it as text.

    The sections are drawn from Readiness.sections(), the same structure the copied text is
    written from, so the dialog and what gets pasted into a forum post cannot disagree.
    """
    with ui.dialog() as dialog, ui.card().classes(_CARD_CLASSES):
        ui.label(f"{translate_string('Readiness')}: {report.scope}").classes("text-xl font-bold text-blue-600")
        ui.label(translate_string("What this needs on the phone that receives it.")).classes(_PLACES_CLASSES)

        with ui.column().classes(_BODY_CLASSES + " gap-0"):
            for section in report.sections():
                ui.label(translate_string(section.title)).classes(_HEADING_CLASSES)
                if not section.lines:
                    ui.label(translate_string(section.empty)).classes(_EMPTY_CLASSES)
                for line in section.lines:
                    ui.label(line.text).classes("mt-1 font-semibold")
                    if line.used_by:
                        ui.label(line.used_by).classes(_PLACES_CLASSES)
                    if line.setup:
                        ui.label(line.setup).classes(_PLACES_CLASSES)
            ui.label(readiness.LIMITATIONS).classes(_LIMITS_CLASSES)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button(translate_string("Copy as text"), on_click=lambda: _copy(report)).props("outline")
            ui.button(translate_string("Close"), on_click=dialog.close).classes("bg-blue-600")
    dialog.open()


def _copy(report: readiness.Readiness) -> None:
    """Put the text report on the clipboard and say so."""
    ui.clipboard.write(report.as_text())
    ui.notify(translate_string("Copied."), type="positive")


def build_readiness_button(check: Callable[[], readiness.Readiness]) -> ui.button:
    """The "Check readiness" button under an export's Save-as path.

    'check' runs readiness.check_project or check_scene for the name being edited.
    A name that has since gone raises ValueError exactly as the export would, and is said in the
    same way rather than left as a traceback.
    """

    def _run() -> None:
        try:
            report = check()
        except ValueError as error:
            ui.notify(str(error), type="negative")
            return
        build_readiness_dialog(report)

    button = ui.button(translate_string("Check readiness"), on_click=_run).props("outline").classes("mt-1")
    with button:
        ui.tooltip(
            translate_string(
                "Before you share this export: lists the plugins and apps it uses, the special access "
                "it needs (root, ADB Wi-Fi, Write Secure Settings and the like), the variables Tasker "
                "will ask the importer about, and the oldest Tasker it is known to run on.\n\n"
                "Built from what is in the file, so it is a minimum rather than a guarantee.",
            ),
        ).style("white-space: pre-wrap")
    return button


def build_share_checks(
    field_refs: dict,
    redact_key: str,
    check: Callable[..., readiness.Readiness],
    name: str,
    state: RunState,
) -> None:
    """The two checks to make before an export leaves the user's hands, on one row under "Save as".

    The "Redact secrets" tick-box (what must not go with the file) and the "Check readiness"
    button (what must be on the phone it arrives on).  One call, so the Project and Scene dialogs
    cannot drift into laying them out differently.  'check' is readiness.check_project or
    check_scene, run for 'name' when the button is pressed.
    """
    with ui.row().classes("w-full items-center gap-4"):
        build_redact_checkbox(field_refs, redact_key)
        build_readiness_button(lambda: check(name, state=state))
