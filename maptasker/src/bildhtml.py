"""bildhtml: Build / generate the html output file"""

import contextlib
import gc
import os
import webbrowser

import maptasker.src.taskuniq as special_tasks
from maptasker.src import caches, console, mapcache, outdir, projects
from maptasker.src.caveats import display_caveats
from maptasker.src.dirout import output_directory, unreachable_anchors
from maptasker.src.error import error_handler, exit_program, rutroh_error
from maptasker.src.format import MapWriter, format_line
from maptasker.src.getputer import save_restore_args
from maptasker.src.globalvr import get_variables, output_variables
from maptasker.src.initparg import initialize_runtime_arguments
from maptasker.src.maputil2 import translate_string
from maptasker.src.maputils import (
    clear_tasker_data,
    display_task_warnings,
    restart_program_subprocess,
)
from maptasker.src.mtexcept import MapTaskerError
from maptasker.src.primitem import (
    PrimeItems,
    PrimeItemsReset,
    get_single_item_not_found,
    is_single_item_found,
)
from maptasker.src.runcfg import RunConfig, current_config, overridden_config
from maptasker.src.sysconst import (
    NORMAL_TAB,
    Colors,
    DISPLAY_DETAIL_LEVEL_all_tasks,
    DISPLAY_DETAIL_LEVEL_all_variables,
    FormatLine,
    debug_out,
    logger,
)

# Where display_back_matter wrote the Map, for build_html to record once the run is done
# with the settings.  "" when this run has not written one.
_map_just_written: caches.Slot[str] = caches.Slot("bildhtml.map_just_written", "")


def build_html(file_to_get: str) -> int:
    """Builds and generates the final HTML output file for MapTasker.

    This function builds the html output file for MapTasker.

    Args:
        file_to_get (str): The path or filename of the Tasker configuration
            file to read. If empty, the function returns early.

    Returns:
        int: Returns 0 upon successful processing or if no file is provided.
            If a pre-existing error state is detected, it will terminate the
            program using the current error code.

    Side Effects:
        - Prints debug messages to stdout if debug mode is active.
        - Calls `exit_program` directly if `PrimeItems.error_code` is greater than 0.
        - Updates `PrimeItems.file_to_get` with the provided `file_to_get` value.
        - Gathers Tasker variables globally if the display detail level warrants it.
        - Modifies global states via `projects.process_projects_and_their_profiles`
          and `final_processing`.
        - Clears the global `PrimeItems.output_lines` queue multiple times.
        - Persists runtime settings and color configurations to disk via `save_restore_args`.
        - Triggers a full program relaunch (`do_rerun()`) if the `rerun` argument
          flag remains active at the end of execution.
    """
    # Let the userr know we are in debug mode.
    console.debug(">>>  MapTasker is in debug mode.  <<<")

    if PrimeItems.error_code > 0:
        # We have a error.  Spit it out and exit.
        exit_program(PrimeItems.error_code)

    if PrimeItems.xml_root is None:
        # Code 6 is "nothing to read".  Raised rather than sys.exit()ed because this runs
        # inside a run.io_bound worker when the GUI is driving: view_event catches it and
        # says so in the window (see MapTaskerEventHandlers.view_event).
        message = "MapTasker: No file to read in."
        console.debug(f">>>  {message}  Exiting.  <<<")
        raise MapTaskerError(message, exit_code=6)

    # Set up file to read if it is passed in (via rerun)
    if file_to_get:
        PrimeItems.file_to_get = file_to_get

    # The Map that would come out of the work below may already be sitting on disk from
    # earlier in this session -- closing the view and opening it again, coming back from
    # the Diagram, and every report finding that builds a Map purely so it can jump to a
    # line in it.  If neither the configuration nor a single setting has changed since it
    # was written, that file IS this build's answer, and building it again would cost the
    # user the longest wait in the program to arrive at the same bytes.
    #
    # Not while analyzing with AI: that path does not want the file, it wants the output
    # lines in memory, and those are produced by doing the work.
    building_from = mapcache.digests()
    doing_ai_analysis = PrimeItems.program_arguments.ai_analyze
    if not doing_ai_analysis and mapcache.is_current(
        outdir.output_path("MapTasker.html"),
        building_from,
    ):
        PrimeItems.map_output_line_count = mapcache.output_lines()
        logger.debug("build_html: the Map on disk is current; it was not built again.")
        return 0

    # Get all Tasker variables.  The configuration digest goes with them so that the
    # where-used counts survive a rebuild that only changed how the Map is displayed.
    if PrimeItems.program_arguments.display_detail_level >= DISPLAY_DETAIL_LEVEL_all_variables:
        get_variables(building_from[0])

    # Process all Projects and their Profiles
    found_tasks = []
    projects_without_profiles = []
    projects_with_no_tasks = []
    # The settings are read once here and handed down.  single_project_name and
    # single_profile_name are the exceptions, which projects.py reads live (see its header).
    found_tasks = projects.process_projects_and_their_profiles(
        found_tasks,
        projects_without_profiles,
        current_config(),
        PrimeItems,
    )

    # Do special handling: wrap up back matter and print the output.
    final_processing(found_tasks, projects_without_profiles, projects_with_no_tasks)

    # Save our runtime settings for next time.  Make sure we don't save the rerun state as True
    # The live dictionaries, not a RunConfig snapshot: save_arguments edits what it is
    # given (hiding the API key, resetting the transient arguments, clearing a single
    # Project name that was only set because a single Task was asked for) and the rest of
    # the run expects to see those edits.
    #
    # Not for a headless run: a command-line export was asked to build something, not to
    # change the settings the GUI keeps, and its own arguments (the detail level it was
    # given, the file it was pointed at) would replace whatever the person last chose there.
    if not PrimeItems.headless:
        with overridden_config(rerun=False):
            _, _ = save_restore_args(
                PrimeItems.program_arguments,
                PrimeItems.colors_to_use,
                to_save=True,
            )

    # Take a note of what the Map just written was built from, so that asking for the same
    # one again is answered with that file rather than by building it a second time.  Last,
    # after the settings have been saved: saving edits them, and the note has to describe
    # the settings as the next run will find them, not as they were mid-build.
    if _map_just_written.value and not doing_ai_analysis:
        mapcache.remember(_map_just_written.value, PrimeItems.map_output_line_count, building_from)
        _map_just_written.value = ""

    # Rerun this program if "Rerun" was selected from GUI
    # First get the filename as a string.
    if PrimeItems.program_arguments.rerun:
        do_rerun()

    return 0


# Re-launch our program via the "rerun" feature.
def restart_program() -> None:
    # Restart our program
    # sys.executable = the path of the python interpreter and use it to execute ourselves again.
    """Restarts the program.
    Parameters:
        - None
    Returns:
        - None
    Processing Logic:
        - Call ourselves and exit after the last call."""

    restart_program_subprocess()
    exit_program(0)  # This should never be called.


# Handle "rerun" request
def do_rerun() -> None:
    """
    Re-runs the program with a new file
    Args:
        None: No arguments required
    Returns:
        None: Function does not return anything
    Re-runs the program with a new file by:
    - Freeing up memory
    - Rerunning the program with the new file
    """

    # Get rid of everything.
    clean_up_memory()

    # Now do it!  Rerun the program.
    restart_program()


# write_out_the_file: we have a list of output lines.  Write them out.
def write_out_the_file(my_output_dir: str, my_file_name: str) -> None:
    """
    write_out_the_file: we have a list of output lines.  Write them out.
        :param my_output_dir: directory to output to
        :param my_file_name: name of file to use
        :return: nothing
    """
    logger.info(f"Function Entry: write_out_the_file dir:{my_output_dir}")
    output_file = f"{my_output_dir}{my_file_name}"
    # Clear any stale message from a previous run -- only set again below if this run also hits the limit.
    PrimeItems.view_limit_msg = ""
    with open(output_file, "w", encoding="utf-8") as out_file:
        # Everything below writes through this rather than straight to the file, because
        # this is the only point that sees the whole document: it is the only place that
        # sees one gap between sections whole, and so the only place that can keep the
        # blank lines in it down to what a reader wants, and the only place that knows
        # which <span>s are open, and so the only place that can write them down the way
        # the browser reads them.  Both rules, one pass over the html (see MapWriter).
        map_file = MapWriter(out_file)
        # Output the rest that is in our output queue
        _output_directory = output_directory  # Localize for speed
        _format_line = format_line  # Localize for speed
        config = current_config()  # Settings for this write -- read once, outside the loop
        for num, item in enumerate(PrimeItems.output_lines.output_lines):
            # This is a temporary workaround to the GUI terminating prematurely due to output size.
            if num > PrimeItems.view_limit:
                msg_text = f"{translate_string('MapTasker: view limit reached, stopping output to file:  output')}={len(PrimeItems.output_lines.output_lines)}, {translate_string('hardstop view limit')}={PrimeItems.view_limit}"
                # print(msg_text)
                # Breaking out mid-loop can leave something the last item opened still
                # unclosed (a <span> deliberately left open by format_html(end_span=False)
                # for a later item to close, or an in-progress <table>/<tr>/<td>/<details>
                # from the "too many actions" twisty -- see this function's own <details>
                # handling below). Left unclosed, the browser's own auto-close-at-EOF
                # behavior can end up laying the message out inside an unconstrained table,
                # which ignores the container's width regardless of word wrap. Closing tags
                # with no matching open tag are simply ignored, so it's safe to always close
                # all of them here before starting a fresh, guaranteed-clean block for the
                # message -- wrapped so it always wraps/constrains to the container's width
                # without hardcoding white-space, so it still respects the Toggle Wrap setting
                # like every other line.
                map_file.write(
                    "</span></td></tr></table></details>"
                    f'<div style="max-width: 100%; overflow-wrap: anywhere; word-break: break-word;">{msg_text}</div>'
                    "</body></html>",
                )
                logger.info(msg_text)
                PrimeItems.view_limit_msg = (
                    msg_text  # Read by the Map view's message field (see guiwins_views.NiceGuiTextView).
                )
                break  # Don't output more than the view limit

            # Check to see if this is where the directory is to go in the Output directory.
            # if so, output_directory will create it's own list of output lines.
            if "maptasker_directory" in item:
                # Temporarily save our output lines
                temp_lines_out = PrimeItems.output_lines.output_lines
                # Work out which of the directory's targets the view limit drops before
                # swapping the output queue out: an entry whose target never makes it
                # into the file is listed as plain text rather than as a hyperlink that
                # would take the user nowhere.
                dropped_anchors = unreachable_anchors(temp_lines_out, PrimeItems.view_limit)
                PrimeItems.output_lines.output_lines = []  # Create a new output queue

                # Do the directory output
                if config.directory:
                    _output_directory(config, dropped_anchors)
                # Output the directory line
                for output_line in PrimeItems.output_lines.output_lines:
                    map_file.write(output_line)
                # Restore our regular output
                PrimeItems.output_lines.output_lines = temp_lines_out
                continue

            # Format the output line
            # logger.info(item)
            output_line = _format_line(item)
            # Continue if we are to ignore this output line.
            if not output_line:
                continue

            # Parse twisty <details>...yield result
            with contextlib.suppress(ValueError):
                details_position = output_line.index("<details>")
                map_file.write(f" {output_line[:details_position]}")
                map_file.write("<details>\r")
                output_line = f"    {output_line[details_position + 9 :]}"

            # Write the actual final line out as html
            if output_line.strip():  # Write out if not blank
                logger.info(f"Writing: {output_line}")
                map_file.write(output_line)
            if debug_out:
                logger.debug(f"mapit output line:{output_line}")
                logger.info("Function Exit: write_out_the_file")

        map_file.finish()  # Close anything the output left open
        os.fsync(out_file)  # Force write to disk


# Output grand totals
def output_grand_totals() -> None:
    """
    Output the grand totals of Projects/Profiles/Tasks/Scenes
    """
    grand_total_projects = PrimeItems.grand_totals["projects"]
    if PrimeItems.program_arguments.single_project_name or PrimeItems.program_arguments.single_profile_name:
        grand_total_projects = 1
    grand_total_profiles = PrimeItems.grand_totals["profiles"]
    if PrimeItems.program_arguments.single_profile_name:
        grand_total_profiles = 1
    grand_total_unnamed_tasks = PrimeItems.grand_totals["unnamed_tasks"]
    grand_total_named_tasks = PrimeItems.grand_totals["named_tasks"]
    if PrimeItems.program_arguments.single_task_name:
        grand_total_named_tasks = 1
        grand_total_profiles = 1
    grand_total_scenes = PrimeItems.grand_totals["scenes"]
    # A single Scene: the one Scene, under its one owning Project, and no Profiles.
    # (An orphan Scene -- see projects.output_orphan_single_scene -- has no Project.)
    if PrimeItems.program_arguments.single_scene_name:
        grand_total_projects = min(grand_total_projects, 1)
        grand_total_profiles = 0
        grand_total_scenes = 1
    # If doing a directory, then add id to hyperlink to.
    if PrimeItems.program_arguments.directory:
        PrimeItems.output_lines.add_line_to_output(
            5,
            '<a id="grand_totals"></a>',
            FormatLine.dont_format_line,
        )

    total_number = "Total number of "
    PrimeItems.output_lines.add_line_to_output(
        1,
        (
            f"<br><hr>{NORMAL_TAB}Tasker Displayed Totals...<br>{NORMAL_TAB}{total_number}Projects: {grand_total_projects}<br>{NORMAL_TAB}{total_number}Profiles:  {grand_total_profiles}<br>{NORMAL_TAB}{total_number}Tasks:"
            f" {grand_total_unnamed_tasks + grand_total_named_tasks} ({grand_total_unnamed_tasks} unnamed,"
            f" {grand_total_named_tasks} named)<br>{NORMAL_TAB}{total_number}Scenes:"
            f" {grand_total_scenes}<br><br>"
        ),
        ["", "trailing_comments_color", FormatLine.add_end_span],
    )
    PrimeItems.output_lines.add_line_to_output(3, "", FormatLine.dont_format_line)


# Display the output in the default web browser,
def display_output(my_output_dir: str, my_file_name: str) -> None:
    """
    Display the output in the default web browser,
    Args:
        my_output_dir (str): The directory to our current file path.
        my_file_name (str): The name of the file to open.
    """
    logger.debug("MapTasker program ended normally")

    # Only invoke the browser if not doing a Map View from the GUI, and if someone is there to
    # look at it: a command-line report or export (headless) has nobody to show it to.
    if PrimeItems.mygui is None and not PrimeItems.headless and not PrimeItems.program_arguments.ai_analyze:
        try:
            webbrowser.open(
                f"file:{PrimeItems.slash * 2}{my_output_dir}{my_file_name}",
                new=2,
            )
        except webbrowser.Error:
            error_handler(
                "Error: Failed to open output in browser: your browser is not supported.",
                1,
            )


# We've displayed Projects etc.. Now display the back matter
def display_back_matter() -> None:
    # Display global variables
    """
    Displays back matter and finalizes HTML output

    Reads the single-named-item state (which Project/Profile/Task/Scene was asked for,
    and which was found) straight off PrimeItems rather than taking it as parameters --
    there are four such items now, and this function already reaches into PrimeItems for
    everything else it needs.

    Returns:
        None

    Processing Logic:
        - Display global variables if detail level is 4
        - Get output directory path
        - Output configuration outline if specified
        - Output grand totals
        - Clean up and exit if single item not found
        - Display program caveats
        - Finalize HTML
        - Write output file
        - Clean up memory
        - Display output file in browser
    """
    program_arguments = PrimeItems.program_arguments
    if program_arguments.display_detail_level >= DISPLAY_DETAIL_LEVEL_all_variables:
        output_variables("Unreferenced Global Variables", "")

    # Get the output directory/folder path -- see outdir.  (dirout's output_directory,
    # imported above, is the Map's hyperlink directory and has nothing to do with this.)
    my_output_dir = str(outdir.output_directory())

    # Output the grand total (Projects/Profiles/Tasks/Scenes)
    output_grand_totals()

    # If doing a single named item and the item was not found, clean up and exit
    missing_label, missing_name = get_single_item_not_found()
    if missing_label:
        if program_arguments.guiview:
            PrimeItems.error_code = 1
            PrimeItems.error_msg = translate_string("Error: Single item specified but not found!  Try again.")
            return
        clean_up_and_exit(missing_label, missing_name)

    # Display warning for Task with too many actions
    if (
        PrimeItems.program_arguments.display_detail_level >= DISPLAY_DETAIL_LEVEL_all_tasks
        and PrimeItems.task_action_warnings
    ):
        display_task_warnings()

    # Display the program caveats
    display_caveats(current_config())

    # Finalize the HTML
    final_msg = "\n</body>\n</html>"
    PrimeItems.output_lines.add_line_to_output(
        5,
        final_msg,
        FormatLine.dont_format_line,
    )

    # If not output directory, cleanup and exit.
    logger.debug(f"output directory:{my_output_dir}")
    if my_output_dir is None:
        error_handler(
            f"{Colors.Yellow}MapTasker canceled.  An error occurred.  Program canceled.",
            0,
        )
        clean_up_memory()
        exit_program(2)

    # Finally, write out all of the output that is queued up.
    my_file_name = f"{PrimeItems.slash}MapTasker.html"
    PrimeItems.map_output_line_count = len(PrimeItems.output_lines.output_lines)
    write_out_the_file(my_output_dir, my_file_name)

    # Where the Map landed, for build_html to take its note of afterwards.  Recorded here
    # rather than acted on here because the note has to be taken once the run is finished
    # with the settings -- saving them is the last thing build_html does, and it edits
    # them on the way through (see the call to save_restore_args).
    _map_just_written.value = f"{my_output_dir}{my_file_name}"

    # Display the final results in the default web browser
    display_output(my_output_dir, my_file_name)


# If not doing a single named item, then output unique Project/Profile situations
def process_unique_situations(
    projects_with_no_tasks: list,
    projects_without_profiles: list,
    found_tasks: list,
    config: RunConfig,
) -> None:
    # Don't do anything if we are looking for a specific named item
    """
    Process unique situations
    Args:
        projects_with_no_tasks: list - List of projects with no tasks
        projects_without_profiles: list - List of projects without profiles
        found_tasks: list - List of found tasks
        config: RunConfig - the run's settings, as they stand for this walk
    Returns:
        None: Does not return anything
    Processing Logic:
        - Check if looking for a specific named item (see is_single_item_found)
        - Get and output tasks not called by any profile
        - Get and output projects that don't have any tasks or profiles
    """
    if is_single_item_found():
        return

    # Get and output all Tasks not called by any Profile
    special_tasks.process_tasks_not_called_by_profile(
        projects_with_no_tasks,
        found_tasks,
        config,
    )

    # Get and output all Projects that don't have any Tasks or Profiles
    special_tasks.process_missing_tasks_and_profiles(
        projects_with_no_tasks,
        projects_without_profiles,
    )
    return


# Cleanup memory and let user know there was no match found for Task/Profile
def clean_up_and_exit(
    name: str,
    profile_or_task_name: str,
) -> None:
    """
    Cleanup memory and let user know there was no match found for Task/Profile/Project
        :param name: the name to add to the log/print output
        :param profile_or_task_name: name of the Profile or Task to clean
    """

    # Clear our current list of output lines.
    PrimeItems.output_lines.output_lines.clear()
    # Spit out the error
    error_handler(f'{name} "{profile_or_task_name}" not found!!', 5)
    # Clean up all memory
    clean_up_memory()
    # Exit with code "item" not found.
    exit_program(5)


# Clean up our memory hogs
def clean_up_memory() -> None:
    """
    Clean up our memory hogs
        :return:
    """
    if PrimeItems.xml_tree is not None:
        for elem in PrimeItems.xml_tree.iter():
            elem.clear()
    clear_tasker_data()
    # The directory and the rest of the run's small state go with the reset below.
    if PrimeItems.xml_root is not None:
        PrimeItems.xml_root.clear()
    if PrimeItems.output_lines is not None:
        PrimeItems.output_lines.output_lines.clear()
    # Reset all of our primasry items
    PrimeItemsReset()
    PrimeItems.program_arguments = initialize_runtime_arguments()

    # Tell python to collect the garbage
    gc.collect()


# Check if doing a single item and if not found, then clean up and exit
def check_single_item() -> None:
    """
    Check if doing a single container item (Project or Profile) and if it was not found,
    then clean up and exit.

    Only the container items are checked here, since a miss on one of those means
    nothing at all could be rendered.  A missing single Task is caught later, by
    display_back_matter, once the totals have been output.

    Reads the requested names and found-flags off PrimeItems rather than taking them as
    parameters -- see display_back_matter for the same reasoning.

        Returns:
            None: nothing
    """
    for name_key, found_key, label in (
        ("single_project_name", "single_project_found", "Project"),
        ("single_profile_name", "single_profile_found", "Profile"),
    ):
        name = PrimeItems.program_arguments[name_key]
        if not name or PrimeItems.found_named_items[found_key]:
            continue
        if PrimeItems.program_arguments.gui:
            PrimeItems.error_code = 1
            PrimeItems.error_msg = f"{label} {name} was not found."
            return
        rutroh_error(f"The {label} '{name}' was not found.")
        clean_up_and_exit(label, name)


# Do the cleanup stuff: check for single name, do unique situations, and display
# back matter.
def final_processing(
    found_tasks: list,
    projects_without_profiles: list,
    projects_with_no_tasks: list,
) -> None:
    # Store single item details in local variables
    """
    Processes special handling of found tasks, projects without profiles, and projects with no tasks.

    Args:
        found_tasks: list - List of found tasks
        projects_without_profiles: list - List of projects without profiles
        projects_with_no_tasks: list - List of projects with no tasks
    Returns:
        None

    Processing Logic:
        - Check if only looking for a single Project/Profile/Task/Scene
        - Turn off directory temporarily to avoid duplicates
        - Get list of tasks not called by profiles and projects without profiles/tasks
        - Restore original directory setting
        - Display back matter after processing projects, profiles, tasks, scenes
    """
    # See if we are only looking for a single Project/Profile and it wasn't found
    check_single_item()

    # Turn off the directory temporarily so we don't get duplicates, and put the setting
    # back afterwards for the final directory of Totals.
    with overridden_config(directory=False) as config:
        # Get the list of Tasks not called by a Profile,
        # and a list of Projects without Profiles/Tasks
        process_unique_situations(
            projects_with_no_tasks,
            projects_without_profiles,
            found_tasks,
            config,
        )

    # Display the trailer stuff, after Projects/Profiles/Tasks/Scenes and print the output.
    display_back_matter()
