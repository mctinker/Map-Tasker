"""Talking to the Android device from the window: the address it was last given, whether it answers, and the notice that a phone prompt is coming."""

import contextlib
from typing import TYPE_CHECKING

from nicegui import run, ui

# Keep your existing logic imports (e.g., from maptasker.src.core.aiutils import ...)
from maptasker.src.core import devicewait
from maptasker.src.core.getputer import save_restore_args
from maptasker.src.core.maputil2 import http_request, suppress_logged, translate_string
from maptasker.src.core.sysconst import (
    logger,
)
from maptasker.src.gui.guistate import remember_setting

if TYPE_CHECKING:
    from collections.abc import Generator

    from maptasker.src.gui.userintr import MyGui


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
        "set_xml_details_button",
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
            with suppress_logged("Deleting a GUI widget"):
                widget.delete()  # NiceGUI uses .delete() instead of .destroy()

            # Clear the reference so your object state stays clean
            setattr(self, attr, None)


# The heads-up every 'Save To Android' write and 'Import Into Tasker' import puts on
# screen before it starts talking to the device.
def notify_watch_android_device() -> None:
    """Warns the user to look at their Android device before a Save To Android /
    Import Into Tasker transfer begins.

    Tasker's HTTP Server Example does not authorize a client once and remember it:
    the connection prompt comes up on the phone per request, so a single save --
    which reads the target path, may write a safety copy, then uploads or imports --
    puts several of them up in a row.  Nothing on this end can suppress them, and a
    prompt left untapped simply times out and fails the save with a connection
    error that looks like the device is unreachable.  So the one useful thing to do
    is say plainly, up front, that the device needs watching.

    No timeout of its own: how long it stays up is the user's 'Notification Duration'
    setting, which guiwins.install_notification_timeout applies to every ui.notify that
    does not name one (and which adds a close button on 'Until dismissed').  This is
    exactly the message someone would set a long duration for, so it must not be one of
    the calls that overrides them.

    Raised only by the eight Save To Android / Import Into Tasker handlers, the writes
    where a missed prompt loses work.  The read-only Android paths (Get XML, the
    helper-Task listing) do not raise it.
    """
    ui.notify(
        translate_string(
            "Watch your Android device: Tasker will ask you to authorize the connection several times.",
        ),
        type="warning",
        multi_line=True,
    )


# Where every Android connection dialog opens when nothing has been entered yet.
DEFAULT_ANDROID_IPADDR = "192.168.0.210"


DEFAULT_ANDROID_PORT = "1821"


def android_address_defaults(gui: "MyGui") -> tuple[str, str]:
    """The (IP address, port) an Android connection dialog should open with.

    The last address entered in ANY of them -- Get XML, Save To Android, Fetch Applications --
    comes first, since that is the one kept across sessions (see remember_android_address).
    android_ipaddr/android_port are only the fallback: they describe where the loaded XML came
    from, so loading a local file empties them, and a settings file written before the
    remembered address existed has only those.
    """
    ipaddr = (
        getattr(gui, "android_last_ipaddr", "")
        or getattr(gui, "android_ipaddr", "")
        or gui.state.program_arguments.android_last_ipaddr
        or DEFAULT_ANDROID_IPADDR
    )
    port = (
        getattr(gui, "android_last_port", "")
        or getattr(gui, "android_port", "")
        or gui.state.program_arguments.android_last_port
        or DEFAULT_ANDROID_PORT
    )
    return str(ipaddr), str(port)


def remember_android_address(gui: "MyGui", ipaddr: str, port: str) -> None:
    """Keep the Android address just entered, for the next dialog and the next session.

    Kept apart from android_ipaddr/android_port on purpose.  Those double as "the loaded XML
    came from the device" -- load_xml re-fetches whenever android_ipaddr is set, and picking
    a local file clears all three -- so the address the user typed could not survive in them.

    Written to the GUI (what the next dialog opens with, and what exiting copies back over
    program_arguments), to program_arguments (what the settings file is written from), and to
    the settings file now rather than at exit, for the reason remember_android_panel_option
    gives: a session that ends any other way never reaches the exit save.  Only written when
    something changed, so a repeated save to the same device does not rewrite the file.
    """
    ipaddr = str(ipaddr or "").strip()
    port = str(port or "").strip()
    if not ipaddr:
        return
    unchanged = (
        getattr(gui, "android_last_ipaddr", "") == ipaddr
        and getattr(gui, "android_last_port", "") == port
        and gui.state.program_arguments.android_last_ipaddr == ipaddr
        and gui.state.program_arguments.android_last_port == port
    )
    remember_setting(gui, "android_last_ipaddr", ipaddr)
    remember_setting(gui, "android_last_port", port)
    if unchanged:
        return
    save_restore_args(gui.state.program_arguments, gui.state.colors_to_use, to_save=True, state=gui.state)


def phone_wait_line(ip_address: str, ip_port: str, route: str = "api/tasks", *, named: bool = False) -> str:
    """A sentence saying a request to this phone can take a while, with how long it will be waited for; "" if not."""
    wait = devicewait.long_wait(ip_address, ip_port, route, named=named)
    if wait is None:
        return ""
    return (
        f"  {translate_string('The phone can take a while to answer this, with a large configuration or when busy.')}"
        f" ({translate_string('waiting up to')} {wait:g} {translate_string('seconds')})"
    )


@contextlib.contextmanager
def waiting_for_phone(
    ip_address: str, ip_port: str, route: str = "api/tasks", *, named: bool = False
) -> "Generator[None]":
    """Put a status line on screen while the phone is asked something it will take a while over.

    So that a long wait is not taken for a hang: nothing is shown when the wait will be short.  The line is taken
    down when the block ends, however it ends.
    """
    line = phone_wait_line(ip_address, ip_port, route, named=named)
    notice = (
        ui.notification(line.strip(), type="ongoing", spinner=True, timeout=None, multi_line=True) if line else None
    )
    try:
        yield
    finally:
        if notice is not None and not getattr(notice, "is_deleted", False):
            with suppress_logged("Dismissing the waiting notice"):
                notice.dismiss()


def remember_android_address_fields(
    gui: "MyGui",
    ip_field: ui.input,
    port_field: ui.input,
    dialog: ui.dialog | None = None,
) -> None:
    """Keep an address typed into an Android dialog even when nothing is done with it.

    Without this the address was only kept once a Run, Fetch, Get XML or Save had used it, so
    changing it and then pressing Close or Cancel lost it.  Kept when either field loses focus --
    which clicking Close does first -- and, for a dialog, when it closes by any means, since
    Escape or a click outside it closes without taking the focus away first.  An empty address
    is ignored (see remember_android_address), so clearing the field does not wipe the saved one.

    Call while the fields are being built: a listener added to an element the browser already
    holds makes NiceGUI rebuild it (see guiwins_nav.register_finding_clicks).
    """

    def keep() -> None:
        remember_android_address(gui, ip_field.value or "", port_field.value or "")

    ip_field.on("blur", lambda _: keep())
    port_field.on("blur", lambda _: keep())
    if dialog is not None:
        dialog.on_value_change(lambda event: None if event.value else keep())


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
        # No try here: http_request already turns every way the device can fail to answer --
        # refused, timed out, unreachable -- into a return code.
        #
        # A plain GET on the 'file' route, which the HTTP Server Example project serves
        # itself and which needs no API key (so this cannot make the device prompt).
        #
        # It used to be a GET on 'maplist', a route that project does NOT serve: it
        # came from the separate 'MapTasker List' Profile the user had to import from
        # TaskerNet and keep enabled.  So this probe -- the gate in front of every
        # Android feature -- failed for anyone who had the server running perfectly
        # well but had never imported that Profile.  Nothing needs it any more (see
        # devicefiles.fetch_file_list_from_device), and the probe should not either.
        return_code, _ = http_request(ipaddr, port, "/Tasker", "file", "")
        # 0 is a 200 and 6 is a 404 -- either way the server answered, which is the
        # whole question here.  Anything else is a connection failure, a timeout or a
        # server error, and none of those mean 'reachable'.
        return return_code in (0, 6)

    # Show a brief non-blocking notification toast to show progress
    ui.notify(f"Connecting to Android device at {ipaddr}:{port}...", type="info", timeout=1200)

    try:
        # 2. Hand off the logic block to NiceGUI's asynchronous thread executor
        device_is_reachable = await run.io_bound(raw_tasker_probe)

        if device_is_reachable:
            return True

    except Exception as e:
        # Deliberately broad: reported to the user in the window rather than raised, since
        # this gates every Android feature.  An unreachable device never gets here (it is a
        # return code, above), so whatever did is a bug -- and its traceback is logged.
        logger.exception("Pinging the Android device failed")
        self.display_message_box(f"Ping execution failure: {e!s}", "Red")
        return False

    # Handle connectivity breakdown state safely
    error_msg = (
        f"{translate_string('Error')}: {translate_string('Android device at')} {ipaddr}:{port} "
        f"{translate_string('is unreachable')}. {translate_string('Check your IP/Port and verify the Tasker HTTP server is running')}."
    )
    self.display_message_box(error_msg, "Red")
    return False
