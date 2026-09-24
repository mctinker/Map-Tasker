"""Intialize command line interface/runtime arguments for MapTasker"""

#! /usr/bin/env python3

#                                                                                      #
# initparg: intialize command line interface/runtime arguments for MapTasker           #
#                                                                                      #
# ArgumentFields is the one place every runtime argument is declared: its name, its
# type, its default and what it is for.  Two classes are built on it:
#
#   * ProgramArguments -- the live, changeable settings.  PrimeItems.program_arguments
#     holds one.
#   * RunConfig (runcfg.py) -- a frozen snapshot of the same fields, plus the colors.
#
# Both get every field from here, so a setting added here exists in both.
#
# It used to be a plain dictionary, and a plain dictionary cannot tell a setting from a
# typo: program_arguments.get("veiw_limit") returned None, and
# program_arguments["ai_analysis"] = False quietly added a key that nothing ever read.
# As a slotted dataclass both are now errors -- reading or writing an attribute that is
# not declared here raises AttributeError, and editors can complete the names.
#
# Most code uses plain attribute access (program_arguments.view_limit).  The few places
# whose setting name is computed at run time -- the settings file, the GUI copying its
# widgets across, the single-item selectors -- use program_arguments[name], which is
# just as strict: an unknown name raises KeyError, reading or writing.
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, ClassVar

from maptasker.src.config import ANDROID_FILE, ANDROID_IPADDR, ANDROID_PORT, DEFAULT_DISPLAY_DETAIL_LEVEL, OUTPUT_FONT
from maptasker.src.sysconst import DIAGRAM_PROFILES_PER_LINE, NOTIFY_TIMEOUT_DEFAULT, VIEW_LIMIT_DEFAULT, logger

if TYPE_CHECKING:
    from collections.abc import ItemsView, Iterable, Iterator, Mapping


@dataclass(slots=True)
class ArgumentFields:
    """
    The runtime arguments: every option the command line, the GUI and the settings file
    can set, with its default -- and read access to them.

    Not used on its own: ProgramArguments adds changing them, RunConfig freezes them.
    Slotted, like both of those, so an attribute that is not declared here can be neither
    read nor written.
    """

    # --- What to show ----------------------------------------------------------------
    display_detail_level: int = DEFAULT_DISPLAY_DETAIL_LEVEL  # How much Task/Profile detail to display, 0-5
    conditions: bool = False  # Display Profile and Task conditions
    directory: bool = False  # Display the directory of hyperlinks
    list_unnamed_items: bool = False  # List unnamed items in the directory
    preferences: bool = False  # Display Tasker's preferences
    runtime: bool = False  # Display the runtime arguments/settings
    taskernet: bool = False  # Display TaskerNet information
    twisty: bool = False  # Add clickable "▶︎" twisties for Task details
    pretty: bool = False  # Pretty up the output (uses many more lines)
    view_limit: int = VIEW_LIMIT_DEFAULT  # Map view line limit
    task_action_warning_limit: int = 100  # Task action count that triggers a warning

    # --- How to draw it --------------------------------------------------------------
    appearance_mode: str = "system"  # "system", "dark" or "light"
    font: str = OUTPUT_FONT  # Font to use in the output
    bold: bool = False  # Names in bold
    highlight: bool = False  # Names highlighted
    italicize: bool = False  # Names italicized
    underline: bool = False  # Names underlined
    indent: int = 4  # Indentation for if/then/else nesting
    icon_alignement: bool = True  # Align the Diagram view with icons
    profiles_per_line: int = DIAGRAM_PROFILES_PER_LINE  # Diagram Profiles per line
    language: str = "English"  # Language for the output and GUI

    # --- The one item to show, if the user asked for just one ------------------------
    single_profile_name: str = ""
    single_project_name: str = ""
    single_scene_name: str = ""
    single_task_name: str = ""

    # --- Where the XML comes from ----------------------------------------------------
    file: str = ""  # The backup file to re-use, if re-running
    android_file: str = ANDROID_FILE  # File location on the Android device
    android_ipaddr: str = ANDROID_IPADDR  # IP address of the Android device
    android_port: str = ANDROID_PORT  # Port of the Android device
    android_last_ipaddr: str = ""  # IP address last entered in any Android dialog
    android_last_port: str = ""  # Port last entered in any Android dialog
    android_check_ids: bool = False  # Save To Android: check IDs against a fresh device backup first
    android_verify: bool = False  # Save To Android: read the XML back before sending it
    fetched_backup_from_android: bool = False  # XML came off an Android device
    local_xml_directory: str = ""  # Where the last local XML file came from ("" = home)

    # --- AI analysis -----------------------------------------------------------------
    ai_analyze: bool = False  # Do AI processing
    ai_apikey: str = field(default="", repr=False)  # AI API key -- kept out of repr() and so out of logs
    ai_model: str = ""  # AI model
    ai_model_extended_list: bool = False  # Offer the extended list of AI models
    ai_name: str = ""  # AI name
    ai_prompt: str = ""  # AI prompt

    # --- What the Health Check reports -----------------------------------------------
    # The categories the user unticked in the Health Check panel, by tag.  Stored as what
    # to LEAVE OUT so a category added in a later release arrives reported rather than
    # silently hidden -- see healthck.CATEGORIES.
    health_check_skip: list[str] = field(default_factory=list)

    # --- GUI window behavior ---------------------------------------------------------
    close_tabs_on_exit: bool = False  # Close the browser tabs when MapTasker exits
    open_view_in_new_window: bool = False  # Open the Map/Diagram/Tree view in a new window

    # --- How we were invoked ---------------------------------------------------------
    gui: bool = False  # Use the GUI for the runtime and color options
    guiview: bool = False  # Use the GUI to get the view (Map, Diagram, Tree)
    doing_diagram: bool = False  # Use the GUI to get the diagram view
    rerun: bool = False  # This is a GUI re-run
    reset: bool = False  # Reset settings to their default values
    debug: bool = False  # Run in debug mode (create a log file)
    tab_to_use: str | None = None  # Default GUI tab to start on
    notify_timeout: int = NOTIFY_TIMEOUT_DEFAULT  # How long a notification stays up (ms)

    # Every argument name, in declaration order, and the same as a set for the name
    # checks below.  Filled in below the class, once the fields exist, so a check is a set
    # lookup rather than a walk of dataclasses.fields() on every access.
    NAMES: ClassVar[tuple[str, ...]] = ()
    NAME_SET: ClassVar[frozenset[str]] = frozenset()

    # ---------------------------------------------------------------------------------
    # Access by a name computed at run time.  Strict: an unknown name is a KeyError, never
    # a silent None.  Use attribute access wherever the name is written out in the code.
    # ---------------------------------------------------------------------------------
    @classmethod
    def _check(cls, name: object) -> str:
        """
        Return name if it is a runtime argument, else raise KeyError.

            Args:
                name: the argument name.

            Returns:
                str: the name, unchanged.

            Raises:
                KeyError: if name is not a runtime argument.
        """
        if name not in cls.NAME_SET:
            msg = f"{name!r} is not a runtime argument (see initparg.ArgumentFields)"
            raise KeyError(msg)
        return name

    def __getitem__(self, name: str) -> object:
        """Return the argument called name.  KeyError if there is no such argument."""
        return getattr(self, self._check(name))

    def __contains__(self, name: object) -> bool:
        """True if name is a runtime argument (every one always has a value)."""
        return name in self.NAME_SET

    def __iter__(self) -> Iterator[str]:
        """Iterate over the argument names, in declaration order."""
        return iter(self.NAMES)

    def __len__(self) -> int:
        """The number of runtime arguments."""
        return len(self.NAMES)

    def keys(self) -> tuple[str, ...]:
        """The argument names.  With __getitem__, this makes dict(args) and {**args} work."""
        return self.NAMES

    def items(self) -> ItemsView[str, object]:
        """(name, value) for every argument, in declaration order."""
        return self.as_dict().items()

    # ---------------------------------------------------------------------------------
    # Conversion
    # ---------------------------------------------------------------------------------
    def as_dict(self) -> dict[str, object]:
        """
        Return the arguments as a plain dictionary -- the shape the settings file is
        written from.  A copy, lists included: changing it does not change self.
        """
        arguments = {}
        for name in self.NAMES:
            value = getattr(self, name)
            arguments[name] = list(value) if isinstance(value, list) else value
        return arguments


@dataclass(slots=True)
class ProgramArguments(ArgumentFields):
    """
    The live runtime arguments, which the command line, the GUI and the settings file
    change as the session goes on.  Every field is declared in ArgumentFields.
    """

    # ---------------------------------------------------------------------------------
    # Changing a setting by a name computed at run time -- as strict as reading one.
    # ---------------------------------------------------------------------------------
    def __setitem__(self, name: str, value: object) -> None:
        """Set the argument called name.  KeyError if there is no such argument."""
        setattr(self, self._check(name), value)

    def update(self, other: Mapping[str, object] | Iterable[tuple[str, object]] = (), /, **kwargs: object) -> None:
        """
        Set several arguments at once, as dict.update does.

            Raises:
                KeyError: if any name is not a runtime argument.  Nothing is set in that
                    case: the names are all checked before any value is assigned.
        """
        pairs = [*(other.items() if hasattr(other, "items") else other), *kwargs.items()]
        for name, _ in pairs:
            self._check(name)
        for name, value in pairs:
            setattr(self, name, value)

    # ---------------------------------------------------------------------------------
    # Copies and saved settings
    # ---------------------------------------------------------------------------------
    def copy(self) -> ProgramArguments:
        """Return a copy, lists included."""
        return ProgramArguments(**self.as_dict())

    def restore(self, settings: Mapping[str, object]) -> list[str]:
        """
        Take every setting this version knows about from a dictionary -- a settings file
        read back, typically -- and ignore the rest.

        Lenient where everything else here is strict, because a settings file written by
        an older (or newer) MapTasker carries arguments that do not exist in this one, and
        the program has always been expected to start anyway.

            Args:
                settings: {argument name: value}.

            Returns:
                list[str]: the names that were ignored, for the caller to report if it
                    wants to.
        """
        ignored = []
        for name, value in settings.items():
            if name in self.NAME_SET:
                setattr(self, name, value)
            else:
                ignored.append(name)
        if ignored:
            logger.info(f"Ignoring unknown saved setting(s): {', '.join(map(str, ignored))}")
        return ignored

    @classmethod
    def from_dict(cls, settings: Mapping[str, object]) -> ProgramArguments:
        """
        Build a ProgramArguments from a dictionary, defaulting what is missing and
        ignoring what is unknown (see restore).
        """
        arguments = cls()
        arguments.restore(settings)
        return arguments


# Fill in the name tables now that the fields exist.
ArgumentFields.NAMES = tuple(each.name for each in fields(ArgumentFields))
ArgumentFields.NAME_SET = frozenset(ArgumentFields.NAMES)


#######################################################################################
# Initialize Program runtime arguments to default values
# Command line parameters
def initialize_runtime_arguments() -> ProgramArguments:
    """
    Initialize the program's runtime arguments to their defaults.
        :return: a fresh ProgramArguments
    """
    return ProgramArguments()
