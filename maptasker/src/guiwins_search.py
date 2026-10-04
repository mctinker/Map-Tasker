"""Search, Find and Replace for the Map, Diagram and Misc views.

Split out of guiwins.py, with the views themselves going to guiwins_views.py.  Three
related tools, all reached from a view's toolbar:

  * Search -- a string, highlighted wherever the rendered view shows it (search_event).
  * Find -- a question put to the loaded configuration rather than to the page, answered
    with a list of objects (find_event, _FindDialog).
  * Replace -- the Find dialog's second tab: change one thing everywhere it appears,
    previewed first (_ReplaceTab).

The view's half of all three is TextViewSearch, a mixin NiceGuiTextView inherits, so every
method stays where the toolbar buttons look for it (view.search_event, view.find_event).
It declares the attributes it needs the view to provide, which is also the whole of what
the Find and Replace classes may touch on a view.

Below guiwins_views and above guiwins_nav: a result is taken to its object by
guiwins_nav.go_to_target, and guiwins_views imports this module to build its view class.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING

from nicegui import context, ui

from maptasker.src import mapask, mapfind, mapjump, mapswap, varxref
from maptasker.src.guiwins_nav import go_to_target
from maptasker.src.maputil2 import translate_string
from maptasker.src.primitem import PrimeItems
from maptasker.src.sysconst import logger

if TYPE_CHECKING:
    import collections
    from collections.abc import Callable, Coroutine

    from maptasker.src.userintr import MyGui


# How much of a Replace preview's non-list matter is drawn before it is summarized.  A
# rename of a variable a plugin produces can skip hundreds of places for the same reason,
# and a list of hundreds of identical explanations pushes the changes off the screen --
# which is the half the user has to read.
_REPLACE_SKIP_LIMIT = 20


# Errors from one apply are notifications, and a notification per failed site would bury
# the screen.  The rest are in the log; this is the "something went wrong, and here is the
# shape of it" cap.
_REPLACE_ERROR_LIMIT = 5


# How long to wait for the browser to finish a view search (see search_event).  NiceGUI's
# own default is 1 second, which is a reasonable wait for a one-line snippet but far too
# short for the search crawl: it walks every text node of the rendered view, and a Map or
# Diagram of a large Tasker configuration is tens of thousands of lines.
SEARCH_JAVASCRIPT_TIMEOUT = 60.0


def search_jump_js(target_id: str) -> str:
    """JavaScript that takes a view to one clicked search result and marks it as the current one.

    Lifted out of the results dialog that builds it (see _report_search_results) so that
    what it does can be stated in one place and tested.  A search hit is not an object in
    the configuration -- it is a run of characters on a line -- which is why this lives here
    rather than beside mapjump's jumps to Projects, Profiles, Tasks and Scenes.

    Instant, not smooth, exactly as those are: a match can be forty thousand pixels from
    where the reader is, and an animated scroll over that distance is slow to land and
    distracting rather than helpful.  Landing at the top of the view rather than the middle
    is this one's own choice and deliberate -- a search result is read forwards from the
    line that matched.
    """
    return f"""
{mapjump.REVEAL_ANCESTORS_JS}
        // Restore any previously-clicked match back to the standard highlight color before
        // marking the newly-clicked one, so only the match the user just jumped to stands out.
        document.querySelectorAll('.search-highlight-active').forEach(el => {{
            el.classList.remove('search-highlight-active');
            el.style.backgroundColor = '#ffd941';
            el.style.color = '#000000';
        }});
        const el = document.getElementById("{target_id}");
        if (el) {{
            // As in the Diagram connector jump buttons: a chunk skipped by
            // content-visibility: auto was never laid out, so scrollIntoView() on a
            // descendant of it lands in the wrong place until it's forced to render.
            mtRevealAncestors(el);
            el.classList.add('search-highlight-active');
            el.style.backgroundColor = '#ff5722';
            el.style.color = '#ffffff';
            el.scrollIntoView({{ behavior: 'auto', block: 'start' }});
        }}
    """


class TextViewSearch:
    """The Search, Find and Replace half of NiceGuiTextView, which inherits it.

    A mixin rather than an object of its own so that these stay methods of the view: the
    toolbar binds its buttons to view.search_event and view.find_event, and the dialogs
    remember what they were last asked on the view (see NiceGuiTextView.__init__).

    The annotations are what it needs the view to provide.  NiceGuiTextView sets every one
    of them; they are declared here, not assigned, so that nothing about the view changes by
    being split in two.
    """

    master_gui: MyGui
    title: str
    scroll_area: ui.scroll_area
    search_input: ui.input
    _content_token: int
    _last_search: tuple[str, list, int, bool] | None
    _find_query: mapfind.Query | None
    _find_ask: asyncio.Task | None
    _find_dialog: ui.dialog | None
    _replace_inputs: tuple | None
    _replace_ticks: collections.Counter | None

    def invalidate_search_cache(self) -> None:
        """Drops the cached search results, without touching the browser-side text index.

        Called when the highlights the cached results point at are removed from the page
        (the "Clear" button, see clear_event in userintr.py). The results are only reusable
        while their highlight spans are still in the DOM -- each cached row's click handler
        jumps to one by element id.
        """
        self._last_search = None

    def search_event(self) -> None:
        """Search for the input text inside the text views and display a clickable results popup."""
        query = self.search_input.value.strip()
        if not query:
            ui.notify(translate_string("Please enter a search term."), type="warning")
            return

        client = context.client

        # Cached results: re-running the search that is already showing costs nothing but
        # rebuilding the dialog. Deliberately a single entry rather than a query -> results
        # map: only the most recent search's highlight spans are still in the page (each
        # search unwraps the previous one's, as does "Clear"), and every row in the dialog
        # jumps to its match by element id -- so results held for any earlier query would
        # come back with rows that quietly jump nowhere.
        cached = self._last_search
        if cached and self._content_token > 0 and cached[0] == query.lower():
            _, found_items, total_matches, was_truncated = cached
            with self.scroll_area:
                self._report_search_results(query, found_items, total_matches, was_truncated, client)
            return

        # Upgraded JavaScript engine targeting Quasar content nodes and penetrating Shadow Roots
        js_code = f"""
            const outerContainer = document.getElementById("c{self.scroll_area.id}");
            // Shape every return the same way: the Python side reads .get() off this, so
            // handing back a bare list here would swap the timeout for an AttributeError.
            if (!outerContainer) return {{ results: [], totalMatches: 0, truncated: false }};

            const container = outerContainer.querySelector('.q-scrollarea__content') || outerContainer;

            const searchTerm = {json.dumps(query.lower())};
            const termLength = {len(query)};
            // Identifies the content in the view (see _mark_content_ready); 0 while it is
            // still streaming in, in which case nothing may be cached about it.
            const contentToken = {self._content_token};

            // 1. Purge previous search highlights completely across Shadow boundaries.
            //    Used only when there is no usable cached index -- it swaps each highlight
            //    for a brand-new text node, which is exactly what the cached index cannot
            //    survive (it holds references to the nodes themselves). The cached path
            //    below unwraps the very same spans without that.
            function clearPreviousHighlights(root) {{
                const highlights = root.querySelectorAll ? root.querySelectorAll('.search-highlight') : [];
                highlights.forEach(el => {{
                    const textNode = document.createTextNode(el.textContent);
                    el.parentNode.replaceChild(textNode, el);
                }});
                const children = root.querySelectorAll ? root.querySelectorAll('*') : [];
                children.forEach(child => {{
                    if (child.shadowRoot) {{
                        clearPreviousHighlights(child.shadowRoot);
                    }}
                }});
            }}

            const results = [];

            // 2. Recursive text node crawler that only COLLECTS matches (no DOM mutation).
            //    Mutating the DOM (e.g. via surroundContents) while iterating a live
            //    childNodes list causes the newly-inserted split nodes to be picked
            //    back up by the same in-progress loop. On large documents with a
            //    common search term this spirals into extremely expensive (sometimes
            //    effectively endless) work and hangs/crashes the browser tab before
            //    a response is ever sent back to Python. So: collect first, mutate later.
            //
            //    The Map/Diagram/Misc views stream many lines into one element per CHUNK
            //    (joined by literal "\\n", relying on white-space:pre to render them as
            //    separate visual lines -- see process_data() in guiwins.py), not one
            //    element per line. That means a match's immediate parentNode is a whole
            //    chunk (or, in the Diagram view, sometimes just a connector <span>
            //    covering a few characters), not a single line -- so parent.textContent
            //    can't be used to recover "the line the match is on". Instead, build a
            //    linear transcript of the whole container's text up front, recording
            //    each text node's starting offset within it, so each match's line number
            //    and line text can be derived from where its offset falls between
            //    newlines in that transcript.
            //
            //    This whole crawl -- the traversal, the transcript, and the line map built
            //    from it -- depends only on the content of the view, not on what is being
            //    searched for, so it is cached on the container and reused by every later
            //    search of the same content (see the index resolution below).
            function buildIndex() {{
                const textNodes = [];  // {{ node, start }}
                let fullText = '';

                function collectTextNodes(node) {{
                    if (node.shadowRoot) {{
                        collectTextNodes(node.shadowRoot);
                    }}

                    if (node.nodeType === 3) {{
                        if (node.parentNode &&
                            node.parentNode.tagName !== 'SCRIPT' &&
                            node.parentNode.tagName !== 'STYLE') {{
                            textNodes.push({{ node, start: fullText.length }});
                            fullText += node.nodeValue;
                        }}
                    }} else if (node.nodeType === 1 && node.tagName === 'BR') {{
                        // The Diagram view is plain text with literal "\\n" line breaks, but the
                        // Map/Misc/Tree views are real HTML that marks line breaks with <br>
                        // elements instead -- treat each one as a line break in the transcript
                        // too, so line numbers/text line up correctly there as well.
                        fullText += '\\n';
                    }}

                    // Snapshot into a static array so later DOM mutations (done in the
                    // second pass below) can never feed back into this traversal.
                    if (node.childNodes && node.childNodes.length) {{
                        for (const child of Array.from(node.childNodes)) {{
                            collectTextNodes(child);
                        }}
                    }}
                }}

                collectTextNodes(container);

                // Map a global offset into fullText -> 0-based line number, via the offset of
                // every line start (binary search since a large diagram can have many lines).
                const lineStarts = [0];
                for (let i = 0; i < fullText.length; i++) {{
                    if (fullText[i] === '\\n') lineStarts.push(i + 1);
                }}
                return {{ token: contentToken, textNodes, fullText, lineStarts, highlights: [] }};
            }}

            // 3. Resolve the index: reuse the one cached on this container when it was built
            //    against the content that is in it now, otherwise build a fresh one.
            //
            //    What makes this awkward is that highlighting mutates the very nodes the
            //    index points at -- surroundContents() splits a matched text node into
            //    prefix / match / tail -- so a cached index would never survive even its own
            //    first use. Rather than discard it, each search unwraps the spans the previous
            //    one left behind (keeping each match's own text node, unlike the wholesale
            //    purge above, which swaps in new ones) and patches the split entries back into
            //    the index as it makes them, further down. fullText and the line map need no
            //    patching at all: splitting a text node changes no characters.
            let cache = container.__mtSearchIndex;
            let usedCachedIndex = false;
            if (cache && contentToken > 0 && cache.token === contentToken) {{
                for (const span of cache.highlights) {{
                    if (span.parentNode && span.firstChild) {{
                        span.parentNode.replaceChild(span.firstChild, span);
                    }}
                }}
                cache.highlights = [];
                usedCachedIndex = true;
                // A highlight the index has no record of means something outside this routine
                // rewrote the text nodes, so the index can no longer be trusted to match them.
                if (container.querySelector('.search-highlight')) {{
                    clearPreviousHighlights(container);
                    cache = buildIndex();
                    usedCachedIndex = false;
                }}
            }} else {{
                clearPreviousHighlights(container);
                cache = buildIndex();
            }}
            // Keep nothing while the content is still streaming in: the index would describe
            // a document that is only partly there.
            container.__mtSearchIndex = contentToken > 0 ? cache : null;

            const textNodes = cache.textNodes;
            const fullText = cache.fullText;
            const lineStarts = cache.lineStarts;

            function lineNumberForOffset(offset) {{
                let lo = 0, hi = lineStarts.length - 1;
                while (lo < hi) {{
                    const mid = (lo + hi + 1) >> 1;
                    if (lineStarts[mid] <= offset) lo = mid; else hi = mid - 1;
                }}
                return lo;
            }}
            function lineTextForOffset(offset) {{
                const ln = lineNumberForOffset(offset);
                const start = lineStarts[ln];
                const end = ln + 1 < lineStarts.length ? lineStarts[ln + 1] - 1 : fullText.length;
                return fullText.substring(start, end);
            }}

            // 4. Find every occurrence of the term.
            //
            //    This searches the transcript rather than each text node in turn. Scanning
            //    node by node can only ever report the FIRST hit inside any one node, and a
            //    node is not a line: the views stream whole chunks into one element, so in
            //    the Diagram view a single text node routinely holds 150 lines. A term
            //    appearing ten times in a chunk was reported once. The transcript has no
            //    such boundaries, and the cached per-node start offsets map any position in
            //    it back to the node (and offset within it) that has to be wrapped.
            //
            //    Lowercasing the transcript is cached with it -- it depends only on the
            //    content, and it is ~1.5MB of string work on a large Map view.
            function transcriptLower() {{
                if (cache.lowerText === undefined) {{
                    const lower = cache.fullText.toLowerCase();
                    // A handful of characters (e.g. U+0130) lowercase to a different number
                    // of characters, which would shift every offset after them. Rare enough
                    // to detect and step around rather than try to track.
                    cache.lowerText = lower.length === cache.fullText.length ? lower : null;
                }}
                return cache.lowerText;
            }}

            const matches = [];  // {{ pos, index, globalOffset }} -- pos is the index slot to patch
            let spanningSkipped = 0;
            const lowerText = transcriptLower();
            if (lowerText === null) {{
                // Fallback: the transcript's offsets can't be trusted for this content, so
                // take the old per-node scan (first hit in each node) rather than risk
                // wrapping the wrong characters.
                for (let pos = 0; pos < textNodes.length; pos++) {{
                    const entry = textNodes[pos];
                    const value = entry.node.nodeValue;
                    if (!value) continue;
                    const index = value.toLowerCase().indexOf(searchTerm);
                    if (index !== -1) {{
                        matches.push({{ pos, index, globalOffset: entry.start + index }});
                    }}
                }}
            }} else {{
                // Occurrences come out in ascending order, so the index slot for each one can
                // be found by walking a cursor forward instead of searching from scratch.
                let cursor = 0;
                let from = 0;
                for (;;) {{
                    const at = lowerText.indexOf(searchTerm, from);
                    if (at === -1) break;
                    from = at + termLength;

                    while (cursor + 1 < textNodes.length && textNodes[cursor + 1].start <= at) cursor++;
                    const entry = textNodes[cursor];
                    const index = at - entry.start;
                    const value = entry.node.nodeValue;
                    // Skip a match that isn't wholly inside one text node -- it either straddles
                    // two of them (the views split lines across elements for colouring and for
                    // the Diagram's connectors) or crosses one of the newlines the transcript
                    // synthesises for <br>, which exist in no text node at all. A Range over
                    // that can't be wrapped in a single span, so there would be nothing to
                    // highlight or jump to. The per-node scan this replaces could not find
                    // them either, so nothing that used to be reported has been lost.
                    if (index < 0 || !value || index + termLength > value.length) {{
                        spanningSkipped++;
                        continue;
                    }}
                    matches.push({{ pos: cursor, index, globalOffset: at }});
                }}
            }}

            // Cap the number of matches we actually highlight/report. A broad
            // search term (e.g. "Task") against a large rendered document could
            // otherwise still produce thousands of DOM mutations in the pass
            // below, which is slow and unnecessary for a human skimming results.
            const MAX_MATCHES = 200;
            const truncated = matches.length > MAX_MATCHES;
            const matchesToShow = truncated ? matches.slice(0, MAX_MATCHES) : matches;

            // 5. Second pass: now that traversal is fully finished, apply the highlight to
            //    each collected match. Every match's text node is still valid because no
            //    mutation happened during collection.
            //
            //    Matches are grouped by the text node holding them, because one node can now
            //    hold many of them, and wrapping one splits that node: the original keeps
            //    only the text BEFORE the match. Each group is therefore wrapped back to
            //    front, so that every match still to be handled sits at its original offset
            //    in the (progressively shortened) original node. Ids and result rows still
            //    follow document order, via each match's rank in the ascending list.
            const byNode = new Map();  // index slot -> its matches, ascending
            matchesToShow.forEach((match, rank) => {{
                match.rank = rank;
                const group = byNode.get(match.pos);
                if (group) {{ group.push(match); }} else {{ byNode.set(match.pos, [match]); }}
            }});

            const repairs = new Map();  // index slot -> the entries that now replace it
            for (const [pos, group] of byNode) {{
                const entry = textNodes[pos];
                // Entries for the pieces split off this node, kept in document order.
                const pieces = [];
                for (let i = group.length - 1; i >= 0; i--) {{
                    const match = group[i];
                    const span = document.createElement('span');
                    span.className = 'search-highlight';
                    span.id = "search_target_" + (match.rank + 1);
                    span.style.backgroundColor = '#ffd941';
                    span.style.color = '#000000';
                    span.style.fontWeight = 'bold';
                    span.style.display = 'inline';

                    const range = document.createRange();
                    range.setStart(entry.node, match.index);
                    range.setEnd(entry.node, match.index + termLength);
                    range.surroundContents(span);
                    cache.highlights.push(span);

                    // Patch the index for the split just made. The span's own text node holds
                    // the match and the remainder follows it as a new sibling text node --
                    // and both offsets into fullText are already known, so nothing needs
                    // re-crawling. fullText itself is untouched: splitting a text node
                    // changes no characters.
                    const added = [];
                    if (span.firstChild) {{
                        added.push({{ node: span.firstChild, start: entry.start + match.index }});
                    }}
                    const tail = span.nextSibling;
                    if (tail && tail.nodeType === 3) {{
                        added.push({{ node: tail, start: entry.start + match.index + termLength }});
                    }}
                    pieces.unshift(...added);
                }}
                repairs.set(pos, [entry, ...pieces]);
            }}

            for (const match of matchesToShow) {{
                results.push({{
                    elementId: "search_target_" + (match.rank + 1),
                    text: lineTextForOffset(match.globalOffset).trim().substring(0, 100),
                    lineNumber: lineNumberForOffset(match.globalOffset) + 1,
                }});
            }}

            if (container.__mtSearchIndex && repairs.size) {{
                const rebuilt = [];
                for (let pos = 0; pos < textNodes.length; pos++) {{
                    const replacements = repairs.get(pos);
                    if (replacements) {{
                        for (const entry of replacements) rebuilt.push(entry);
                    }} else {{
                        rebuilt.push(textNodes[pos]);
                    }}
                }}
                cache.textNodes = rebuilt;
            }}

            return {{
                results: results,
                totalMatches: matches.length,
                truncated: truncated,
                cachedIndex: usedCachedIndex,
                spanningSkipped: spanningSkipped,
            }};
        """

        async def execute_search() -> None:
            with self.scroll_area:
                # Await the execution of our DOM analyzer script block.
                #
                # Two things this has to survive.  First, the crawl takes as long as it
                # takes -- hence SEARCH_JAVASCRIPT_TIMEOUT rather than NiceGUI's 1-second
                # default, which a Map view of any size blows straight through.  Second,
                # this coroutine is fired off with create_task() and never awaited, so an
                # exception escaping it isn't merely unreported: asyncio prints a bare
                # "Task exception was never retrieved" traceback to the console and the
                # user is left with a search that silently never answers.  Say what
                # happened in the window instead.
                try:
                    search_result = await client.run_javascript(js_code, timeout=SEARCH_JAVASCRIPT_TIMEOUT)
                except TimeoutError:
                    logger.debug(f"guiwins search timed out after {SEARCH_JAVASCRIPT_TIMEOUT} seconds: '{query}'")
                    # The script may or may not have got as far as rearranging the highlights
                    # before it stopped answering, so nothing about this search is reusable.
                    self._last_search = None
                    ui.notify(
                        translate_string(
                            "The search did not finish. The view may be too large, or the browser is busy.",
                        ),
                        type="negative",
                    )
                    return
                found_items = search_result.get("results", [])
                total_matches = search_result.get("totalMatches", len(found_items))
                was_truncated = search_result.get("truncated", False)
                logger.debug(
                    f"guiwins search '{query}': {total_matches} matches, "
                    f"reused text index: {search_result.get('cachedIndex', False)}, "
                    f"unwrappable matches skipped: {search_result.get('spanningSkipped', 0)}",
                )

                # These highlights are now the ones in the page, so this is the one search
                # whose results can be handed back without re-running anything (see above).
                if self._content_token > 0:
                    self._last_search = (query.lower(), found_items, total_matches, was_truncated)

                self._report_search_results(query, found_items, total_matches, was_truncated, client)

        self._search = asyncio.create_task(execute_search())

    def _report_search_results(
        self,
        query: str,
        found_items: list,
        total_matches: int,
        was_truncated: bool,
        client: object,
    ) -> None:
        """Announces a set of search results and builds the clickable results dialog for them.

        Shared by a freshly-run search and a cached one so that re-running the search already
        on screen is indistinguishable from the first run.
        """
        if not found_items:
            ui.notify(f"No matches found for: '{query}'", type="negative")
            return  # Debugging output

        if was_truncated:
            ui.notify(
                f"Showing first {len(found_items)} of {total_matches} matches for: '{query}'",
                type="warning",
            )

        # 3. Create the interactive Search Results Modal Popup Window
        with ui.dialog() as results_dialog, ui.card().classes("w-[750px] max-w-full p-6"):
            header_text = (
                f"Search Results for '{query}' ({len(found_items)} of {total_matches} matches)"
                if was_truncated
                else f"Search Results for '{query}' ({len(found_items)} matches)"
            )
            ui.label(header_text).classes(
                "text-lg font-bold text-blue-600 mb-2",
            )
            ui.label(
                translate_string("Click on a row index line number to jump directly to that match block placement:"),
            ).classes("text-xs text-gray-500 italic mb-4")

            # Create a clear scroll area container for the results rows list matching the active theme font
            with ui.scroll_area().classes(  # noqa: SIM117
                "w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded",
            ):
                with ui.column().classes("w-full gap-1"):
                    for item in found_items:
                        # Localized function referencing the cross-linked runtime element reference
                        def make_jump_callback(target_id: str = item["elementId"]) -> None:
                            return lambda: (
                                results_dialog.close(),
                                client.run_javascript(search_jump_js(target_id)),
                            )

                        with ui.row().classes(
                            "w-full items-center py-1 border-b dark:border-gray-700 hover:bg-blue-50 dark:hover:bg-blue-950 px-2 rounded transition-colors",
                        ):
                            # Active click hotlink index line label
                            ui.link(f"Line #{item['lineNumber']}", "#").on(
                                "click",
                                make_jump_callback(),
                            ).classes(
                                "text-blue-600 dark:text-blue-400 font-bold font-mono text-sm mr-4 shrink-0 decoration-dotted hover:underline",
                            )
                            # Text context content preview box
                            ui.label(item["text"]).classes(
                                "text-sm font-mono truncate text-gray-800 dark:text-gray-200",
                            )

            # Footer window management close control
            with ui.row().classes("w-full justify-end mt-4"):
                ui.button(translate_string("Close Results Window"), on_click=results_dialog.close).classes(
                    "bg-red-500 text-white px-4",
                )

        results_dialog.open()

    def _build_replace_tab(
        self,
        dialog: ui.dialog,
        index: mapfind.FindIndex,
        jump_to: Callable,
        replace_panel: ui.tab_panel,
    ) -> bool:
        """Build the Find dialog's Replace tab into `replace_panel`.

        Takes the four things it shares with the Find half and nothing else: the dialog to
        close on success, the mapfind index both pulldowns are built from, the jump handler
        a preview row's link uses, and the panel to build into.

        `self` is used only to remember the inputs on the view (see _replace_inputs), which
        is what lets a preview survive a click on one of its own rows.

        Returns whether it restored a previous Replace, so the caller can open the dialog
        on this tab rather than on Find when it did.
        """
        return _ReplaceTab(self, dialog, index, jump_to, replace_panel).restore_previous()

    def _dismiss_find_dialog(self) -> None:
        """Take down the Find/Replace dialog this view has up, if it still has one.

        Deleted rather than closed: a fresh dialog is built per press of Find/Replace, so
        the one being replaced has nothing left to hold, and a closed-but-undeleted dialog
        is exactly the page-growing stack the "hide" handler exists to prevent.

        A dialog whose page has gone away raises rather than answering.  That is one more
        dialog already gone, not an error to report.
        """
        # Its question to the AI model goes with it.  Deleting a dialog raises no "hide", so
        # the dialog's own dispose() is not there to cancel it.
        self._cancel_find_ask()
        dialog = self._find_dialog
        self._find_dialog = None
        if dialog is not None:
            with contextlib.suppress(Exception):
                dialog.delete()

    def _cancel_find_ask(self) -> None:
        """Cancel the question the Find dialog has out with an AI model, if it has one.

        For when an answer would have nowhere to go or nobody waiting for it: the dialog
        closed or replaced, or the question cleared with its 'X'.  mapask asks every provider
        through its async client, so cancelling the task drops the request where it waits
        instead of letting it run on to a reply nobody will read.
        """
        task = self._find_ask
        self._find_ask = None
        if task is not None and not task.done():
            task.cancel()

    def find_event(self) -> None:
        """Open this view's Find dialog: ask the configuration a question, not the page.

        The faceted counterpart to search_event, and the reason both exist.  Search crawls
        the rendered text and highlights every occurrence of a string in place, which
        answers "where does this word appear" and nothing else.  This asks the loaded XML
        for objects -- Tasks that perform an action, Profiles a context triggers, anything
        naming an app or a Scene -- and answers with a list of them, each row a click away
        from the object itself.  On a configuration of 200 Projects that is the difference
        between a Map that can be read and one that can be navigated.

        The index is rebuilt every time this opens rather than cached on the view.  It is
        a single pass over the XML (60ms on an 840-Task backup, against 1.5ms for a query),
        and the configuration underneath can have been edited since the last Find -- a
        cached index would keep offering an action of a Task that has been deleted, and
        keep hiding one just added.
        """
        if not PrimeItems.tasker_root_elements["all_tasks"]:
            ui.notify(translate_string("No XML file has been loaded.  Get an XML file first."), type="warning")
            return

        # Whatever this view still has up goes first.  Ordinarily nothing does -- the
        # dialog opens modal, so the button that reaches here cannot be pressed while one
        # is on screen -- but a dialog that has docked itself (see _FindDialog.dock) is not
        # modal, and building a second one over it would leave the first in the page, still
        # holding its own results list.
        self._dismiss_find_dialog()

        dialog = _FindDialog(self).dialog
        # Held on the view for as long as it is on screen: this one may outlive the click
        # that dismissed it in every previous version -- a docked dialog stays up until the
        # user closes it -- and the next press of Find/Replace has to be able to find it.
        self._find_dialog = dialog
        dialog.open()


class _FindDialog:
    """The Find/Replace dialog, built for one press of Find/Replace -- see
    NiceGuiTextView.find_event.

    Holds the dialog and the Find tab's fields and results, so that every handler can reach
    them.  The Replace tab is _ReplaceTab's.
    """

    def __init__(self, view: TextViewSearch) -> None:
        self.view = view
        self.index = mapfind.build_index(state=PrimeItems)
        # A Find run from the Diagram shows its answers in the Diagram where it can (see
        # go_to_target).  Decided here, from the view the button was pressed on, rather
        # than from whatever view happens to be frontmost when a row is clicked.
        self.from_diagram = self.view.title.startswith("Diagram")

        # `persistent`, by the rule in guiwins.py's DIALOGS & POPUPS note: a dialog that
        # holds work in progress or asks for a decision leaves on a button and nothing
        # else.  Find alone did not qualify -- a query is cheap to retype and a stray
        # click cost nothing -- but the Replace tab put both on the same card.  A preview
        # is work in progress (a hundred rows, each individually ticked or unticked, and
        # the plan is discarded with the dialog rather than remembered), and Replace is a
        # decision.  Without this, a click anywhere on the backdrop throws that away
        # silently, and the pulldowns are the worst of it: choosing from one means
        # clicking a popup that Quasar renders OUTSIDE the card, so the click that picks
        # a variable can be the click that closes the dialog.
        with ui.dialog().props("persistent") as self.dialog, ui.card().classes("w-[900px] max-w-full p-6") as self.card:
            # Whether this dialog has moved out of the middle of the screen and become a
            # panel at the right edge.  Set by the first row that is followed and never
            # unset -- once the user is going back and forth between the list and the view,
            # that is what they are doing until they close it.
            self.docked = {"yes": False}

            ui.label(
                f"{translate_string('Find in')} {self.view.title}",
            ).classes("text-lg font-bold text-blue-600")

            # Both tabs read and write only what the app is displaying, so the dialog says
            # which that is.  Stated up front rather than left to be inferred from a short
            # answer: "no matches" and "no matches in this one Task" look identical, and
            # the second is the one that sends somebody looking for a bug.
            if not self.index.scope.is_everything:
                ui.label(
                    f"{translate_string('Limited to')} {self.index.scope.phrase} "
                    f"-- {translate_string('clear the single-item selection to reach the whole configuration')}.",
                ).classes(
                    "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1 mb-1",
                )
            # Find and Replace share this dialog, and share the index behind it.  Two
            # reasons beyond tidiness, both in find_event's own terms: the index is
            # rebuilt per open rather than cached (see find_event) and a separate Replace
            # dialog would pay that a second time, or worse, hold one from before an
            # edit; and the natural move is to look for something, see the 37 places it
            # is, and then decide to change them -- which is a tab switch rather than a
            # second window and a re-entered query.
            with ui.tabs().classes("w-full") as tabs:
                find_tab = ui.tab(translate_string("Find"))
                replace_tab = ui.tab(translate_string("Replace"))
            # shrink-0 is what lets this dialog scroll.  Quasar caps a dialog's card at the
            # window's height and scrolls it, but the card is a flex column and the tab panels
            # hide their own overflow -- so instead of overflowing the card they were squeezed
            # to fit inside it, and everything below the cut (the rest of the results, the
            # Find and Save buttons) was clipped off with no scrollbar anywhere.  Worst once
            # docked, where the narrower card wraps the pulldowns onto more rows.
            with ui.tab_panels(tabs, value=find_tab).classes("w-full shrink-0"):
                find_panel = ui.tab_panel(find_tab)
                replace_panel = ui.tab_panel(replace_tab)

            with find_panel:
                self._build_find_tab()

            # The Replace tab is built by its own method rather than inline.  It is the
            # larger half of this dialog and shares only the index, the panel and the jump
            # with the Find half -- which is exactly the seam, so that is where it is cut.
            restored_replace = self.view._build_replace_tab(self.dialog, self.index, self.jump_to, replace_panel)

            with ui.row().classes("w-full justify-end mt-4 gap-2"):
                ui.button(translate_string("Close"), on_click=self.dialog.close).classes("bg-red-500 text-white px-4")

            # A fresh dialog is built per press, so the one being replaced is disposed of
            # rather than left in the page: this is a control the user reaches for over and
            # over while narrowing a search, and a stack of dead dialogs (each holding a
            # results list of up to 500 rows) is a page that grows all afternoon.
            #
            # The view is told as well, so that _dismiss_find_dialog does not later go
            # looking for one that has already taken itself down.  A dialog that docks
            # itself never gets here at all -- it is still open, and the view's handle on
            # it is what the next press disposes of.
            self.dialog.on("hide", self.dispose)

            # Come back to the question that was last asked, rather than to a blank dialog.
            # A result row's click no longer costs the list -- the dialog docks instead of
            # closing (see dock) -- but the Close button does, and the next press of Find is
            # nearly always the same query with one more row to look at.
            # Whichever half the user was last using is the one to open on.
            if restored_replace:
                tabs.set_value(replace_tab)

            previous = self.view._find_query
            if previous is not None:
                self.fill(previous)
                self.show(previous)

    def _build_find_tab(self) -> None:
        """The Find tab: the query fields, the results list, and the Find and Save buttons."""
        ui.label(
            translate_string(
                "Each box narrows the answer, and they combine: a trigger and an action together "
                "find the Profiles that trigger that way AND run a Task that does that. Every entry "
                "offered is one this configuration actually uses, and the number beside it is how "
                "many places carry it.",
            ),
        ).classes("text-xs text-gray-500 italic mb-3")

        self._build_query_fields()

        self.summary = ui.label("").classes("text-sm font-bold mt-3")
        self.results_area = ui.scroll_area().classes(
            "w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded",
        )
        # What the last Find produced, so "Save Results" writes exactly the list on
        # screen rather than re-running a query the user may have edited since.
        self.produced: dict = {"query": None, "hits": [], "total": 0}

        self.ask_button.on_click(self.ask)
        self.question_input.on("keydown.enter", self.ask)
        # The box's own 'X' takes the question back, and a question taken back is not
        # one to keep the model working on.
        self.question_input.on("clear", self.view._cancel_find_ask)

        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            ui.button(translate_string("Find"), on_click=self.run).classes("bg-blue-600 text-white px-4")
            ui.button(translate_string("Save Results"), on_click=self.save).classes(
                "bg-blue-600 text-white px-4",
            )

    def _build_query_fields(self) -> None:
        """The question for the AI, and the boxes a query is picked in."""
        # A question in plain words, for someone who knows what they are looking for
        # but not which of the boxes below says it.  The AI model selected on the
        # Analyze tab only fills those boxes in (see mapask): the answer is still the
        # query they hold, run exactly as if it had been picked by hand, and left in
        # them to be read and changed.
        with ui.row().classes("w-full items-center gap-2 mb-2"):
            self.question_input = (
                ui.input(
                    label=translate_string("Ask in plain words"),
                    placeholder=translate_string("e.g. every Profile that fires on wifi at home"),
                )
                .classes("flex-1")
                .props("dense clearable")
            )
            self.ask_button = ui.button(translate_string("Ask AI")).classes("bg-blue-600 text-white px-4")
        # What the model offered that could not be used, or said it could not express.
        # Kept on screen beside the query rather than in a notification, because it
        # qualifies the answer below for as long as that answer is up.
        self.ask_notes = ui.label("").classes(
            "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1 mb-1 "
            "whitespace-pre-line",
        )
        self.ask_notes.set_visibility(False)

        self.pickers = {}
        with ui.row().classes("w-full items-center gap-2"):
            for facet in mapfind.FACETS:
                choices = self.index.choices(facet)
                self.pickers[facet] = (
                    ui.select(
                        {choice.value: choice.label for choice in choices},
                        label=translate_string(mapfind.FACET_LABELS[facet]),
                        with_input=True,
                        clearable=True,
                    )
                    .classes("flex-1 min-w-[180px]")
                    .props("dense")
                )

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            self.text_input = (
                ui.input(label=translate_string("Text (name, label or argument)"))
                .classes("flex-1")
                .props("dense clearable")
            )
            # Hidden when a single Project/Profile/Task/Scene is selected, because the
            # scope has already done the narrowing and this can then only mislead.
            # "Every Project" is the option that goes wrong: with one Task selected it
            # is the ONLY entry and means that Task, and with one Project selected it
            # and that Project's own entry mean the same thing.  Either way the label
            # promises the whole configuration and delivers a corner of it.  Left at ""
            # rather than removed, so the query still reads a value and no code below
            # has to care whether the widget is on screen.
            self.project_select = (
                ui.select(
                    {"": translate_string("Every Project")} | {name: name for name in self.index.projects},
                    value="",
                    label=translate_string("Narrow to Project"),
                    with_input=True,
                )
                .classes("w-64")
                .props("dense")
            )
            self.project_select.set_visibility(self.index.scope.is_everything)

    def dock(self) -> None:
        """Get this dialog out of the view's way instead of taking it down.

        What following one of the rows does now.  It used to close the dialog, and
        had to: a modal dialog sits in the middle of the screen with a backdrop over
        the rest, so the jump behind it scrolled a view the user could not see.  The
        cost was paid on the Replace tab above all -- going to look at one of forty
        places about to change meant pressing Find/Replace again, for every one of
        them, to get the preview back.

        `seamless` is what makes closing unnecessary: it drops the backdrop and the
        body-scroll lock, so the view behind is visible, scrollable and clickable
        while this stays up.  `position=right` pins the dialog to the edge and out
        of the column the Map is read down.  Both are Quasar props on the dialog as
        it stands and both are reactive, so it moves without being rebuilt -- which
        is the point: rebuilding it is what would throw away the preview, the tick
        boxes and the query this exists to keep.
        """
        if self.docked["yes"]:
            return
        self.docked["yes"] = True
        self.dialog.props(add="seamless position=right")
        # Narrower than the 900px it opens at, because it is now sharing the screen
        # with the view it just sent the user to, and being able to read that view
        # is the whole reason it moved.
        self.card.classes(remove="w-[900px] p-6", add="w-[620px] p-4")

    def jump_to(self, target: mapjump.Target) -> Callable[[], Coroutine]:
        """One result row's click: dock the list to the right, then go to the object.

        Docked rather than closed (see dock), so the list the row came from is
        still there when the user has finished looking -- which is what a Find
        and a Replace preview are both for: a list of places, walked one at a
        time.  Shared by both tabs, and the reason the Replace half is handed
        this rather than writing its own.

        The jump runs inside the VIEW's slot rather than the dialog's, which is
        not decoration: everything it does afterwards -- ui.notify above all --
        resolves its client through whatever slot is active, and the dialog's
        goes away with the dialog.  Left in the dialog's, the first notification
        raised "The parent element this slot belongs to has been deleted" from
        inside NiceGUI and the jump died there, silently.  It survives a docked
        dialog, which is not deleted, but it did not survive the close this used
        to do and would not survive the Close button landing mid-jump either.
        The same re-entry, for the same reason, as
        _enable_connector_highlighting's.
        """

        async def go() -> None:
            self.dock()
            with self.view.scroll_area:
                await go_to_target(self.view.master_gui, target, prefer_diagram=self.from_diagram)

        return go

    def show(self, query: mapfind.Query) -> None:
        """Run the query and draw its answer."""
        self.view._find_query = query
        self.produced.update(query=query, hits=[], total=0)
        self.results_area.clear()
        if query.is_empty:
            self.summary.set_text("")
            ui.notify(
                translate_string("Choose an action, a trigger, an app, a Scene or some text."),
                type="warning",
            )
            return

        hits, total = mapfind.run_query(self.index, query)
        self.produced.update(hits=hits, total=total)
        self.summary.set_text(
            (
                f"{len(hits)} {translate_string('of')} {total} {translate_string('found for')}: {query.phrase()}"
                if total > len(hits)
                else f"{total} {translate_string('found for')}: {query.phrase()}"
            ),
        )

        with self.results_area, ui.column().classes("w-full gap-1"):
            if not hits:
                ui.label(
                    translate_string("Nothing in the loaded configuration answers this."),
                ).classes("text-sm text-gray-500 italic")
                return
            project = None
            for hit in hits:
                if hit.project != project:
                    project = hit.project
                    ui.label(
                        (
                            f"{translate_string('Project')} '{project}'"
                            if project
                            else translate_string("In no Project")
                        ),
                    ).classes("text-xs font-bold text-orange-500 mt-2")
                with ui.row().classes(
                    "w-full items-baseline py-1 border-b dark:border-gray-700 hover:bg-blue-50 "
                    "dark:hover:bg-blue-950 px-2 rounded transition-colors",
                ):
                    # Two handlers on the one click, and the browser-side one
                    # is not decoration: it raises the Map view the jump is
                    # about to land in, which a browser only permits while the
                    # click's user activation is still alive -- and it has
                    # lapsed by the time jump_to runs (see
                    # mapjump.raise_map_window_js).  It ends in emit(), which
                    # is what carries the click on to jump_to.
                    ui.link(hit.where, "#").on(
                        "click",
                        self.jump_to(hit.target),
                        js_handler=mapjump.find_result_click_js(
                            mapjump.diagram_anchor(hit.target) if self.from_diagram else "",
                        ),
                    ).classes(
                        "text-blue-600 dark:text-blue-400 font-mono text-sm shrink-0 decoration-dotted hover:underline",
                    )
                    if hit.detail:
                        ui.label(hit.detail).classes("text-xs text-gray-500 dark:text-gray-400 truncate")

    def run(self) -> None:
        """The Find button: build the query out of the widgets and answer it."""
        self.show(
            mapfind.Query(
                action=self.pickers[mapfind.ACTION].value or "",
                trigger=self.pickers[mapfind.TRIGGER].value or "",
                app=self.pickers[mapfind.APP].value or "",
                scene=self.pickers[mapfind.SCENE_FACET].value or "",
                text=self.text_input.value or "",
                project=self.project_select.value or "",
            ),
        )

    def save(self) -> None:
        """Write the list on screen to a file, as the other reports do.

        The same Rows the results list is drawn from, so the file and the screen
        cannot disagree -- and every location line in it stays clickable if the
        saved report is ever opened in the Misc view.
        """
        query = self.produced["query"]
        if query is None:
            ui.notify(translate_string("Run a Find first."), type="warning")
            return
        rows = mapfind.report_rows(query, self.produced["hits"], self.produced["total"], self.index)
        file_name = mapfind.write_find_report(rows)
        if file_name:
            ui.notify(f"{translate_string('Find results saved as')} {file_name}", type="positive")
        else:
            ui.notify(translate_string("Find results could not be saved."), type="negative")

    def fill(self, query: mapfind.Query) -> None:
        """Put a query into the boxes it would have been picked from."""
        self.pickers[mapfind.ACTION].set_value(query.action or None)
        self.pickers[mapfind.TRIGGER].set_value(query.trigger or None)
        self.pickers[mapfind.APP].set_value(query.app or None)
        self.pickers[mapfind.SCENE_FACET].set_value(query.scene or None)
        self.text_input.set_value(query.text)
        self.project_select.set_value(query.project)

    async def ask(self) -> None:
        """The Ask AI button: have the selected model write the query, then run it.

        Every value in the reply has been checked against these pulldowns' own
        entries before any of it is used (mapask.parse_reply), so what goes into
        the boxes is always something they offer.  What the model offered that
        this configuration does not use, or said it could not express, is shown
        above them: a half-translated question answers with fewer objects than
        were asked for, and must not look like a right answer.
        """
        question = (self.question_input.value or "").strip()
        if not question:
            ui.notify(translate_string("Type a question first."), type="warning")
            return
        gui = self.view.master_gui
        try:
            settings = mapask.model_settings(getattr(gui, "ai_name", ""), getattr(gui, "ai_model", ""))
        except mapask.AskError as error:
            ui.notify(str(error), type="warning", multi_line=True)
            return

        self.ask_notes.set_visibility(False)
        # One question at a time: pressing Ask again replaces the one still out.
        self.view._cancel_find_ask()
        # A task of its own rather than a plain await, so that closing the dialog
        # or clearing the question can cancel it (_cancel_find_ask).  Every
        # provider is asked through its async client, so cancelling drops the
        # connection rather than leaving a request running for a reply nobody
        # is going to read.
        task = asyncio.create_task(mapask.translate(question, self.index, settings))
        self.view._find_ask = task
        self.ask_button.props(add="loading")
        try:
            translation = await task
        except asyncio.CancelledError:
            # This handler being cancelled itself is not ours to swallow.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
            # Cleared, or replaced by a newer question.  A dialog that was closed
            # has nowhere left to say so, and needs no telling.
            if not getattr(self.dialog, "is_deleted", False):
                ui.notify(translate_string("The question to the AI model was cancelled."), type="info")
            return
        except mapask.AskError as error:
            ui.notify(str(error), type="negative", multi_line=True)
            return
        finally:
            if self.view._find_ask is task:
                self.view._find_ask = None
            if not getattr(self.dialog, "is_deleted", False):
                self.ask_button.props(remove="loading")
        # Closed while the model was thinking: there is nothing left to fill in.
        if getattr(self.dialog, "is_deleted", False):
            return

        notes = []
        if translation.unknown:
            notes.append(
                f"{translate_string('Left out, as this configuration does not use it')}: "
                f"{', '.join(translation.unknown)}",
            )
        if translation.surplus:
            notes.append(
                f"{translate_string('Left out, as each box holds one value')}: {', '.join(translation.surplus)}",
            )
        if translation.unexpressed:
            notes.append(f"{translate_string('Not expressible as a search')}: {translation.unexpressed}")
        self.ask_notes.set_text("\n".join(notes))
        self.ask_notes.set_visibility(bool(notes))

        if translation.query.is_empty:
            # Not handed to show(), whose warning is about boxes left empty by hand.
            # The previous answer goes too: left up, it would read as this one's.
            self.produced.update(query=None, hits=[], total=0)
            self.summary.set_text("")
            self.results_area.clear()
            ui.notify(
                translate_string(
                    "The question could not be turned into a search.  Try naming an action, "
                    "a trigger, an app or a Scene.",
                ),
                type="warning",
                multi_line=True,
            )
            return
        self.fill(translation.query)
        self.show(translation.query)

    def dispose(self) -> None:
        """Forget this dialog and take it out of the page, and its question to the AI with it."""
        if self.view._find_dialog is self.dialog:
            self.view._find_dialog = None
            # Only this dialog's own: a question still out belongs to the dialog the
            # view holds, and one that has already been replaced was cancelled then.
            self.view._cancel_find_ask()
        self.dialog.delete()


class _ReplaceTab:
    """The Find dialog's Replace tab -- see NiceGuiTextView._build_replace_tab.

    Holds the tab's fields and the preview on screen, so that every handler can reach them.
    """

    def __init__(
        self,
        view: TextViewSearch,
        dialog: ui.dialog,
        index: mapfind.FindIndex,
        jump_to: Callable,
        replace_panel: ui.tab_panel,
    ) -> None:
        self.view = view
        self.dialog = dialog
        self.index = index
        self.jump_to = jump_to
        # ##################################################################
        # The Replace tab.
        #
        # Everything below is arranged around one rule: the Replace button is
        # disabled until a preview exists for the values CURRENTLY in the fields,
        # and touching any field clears the preview and disables it again.  There
        # is then no path through these widgets that reaches mapswap.apply without
        # the user having seen mapswap.report_rows first -- which is the whole
        # design, made structural rather than left to the dialog to remember.
        # ##################################################################
        with replace_panel:
            # Built when the Replace tab is first used, not when the dialog opens.
            # It is a second full scan of the XML on top of the one mapfind just
            # did, and most presses of Find never come here at all.
            self.held: dict = {"variables": None, "plan": None, "inputs": None}

            ui.label(
                translate_string(
                    "Change one thing everywhere it appears. Nothing is altered until you press "
                    "Preview and then Replace, and every change is one Undo away afterwards.",
                ),
            ).classes("text-xs text-gray-500 italic mb-3")

            self.mode = ui.toggle(
                {
                    "action": translate_string("Task action"),
                    "argument": translate_string("Action argument"),
                    "condition": translate_string("Profile condition"),
                    "variable": translate_string("Variable name"),
                },
                value="action",
            ).props("dense")

            self._build_action_row()
            self._build_argument_row()
            self._build_condition_row()
            self._build_variable_row()

            self.replace_summary = ui.label("").classes("text-sm font-bold mt-3")
            self.replace_area = ui.scroll_area().classes(
                "w-full h-[45vh] border p-2 bg-gray-50 dark:bg-gray-900 rounded",
            )

        with replace_panel, ui.row().classes("w-full justify-end mt-4 gap-2"):
            ui.button(translate_string("Preview"), on_click=self.preview).classes("bg-blue-600 text-white px-4")
            self.replace_button = ui.button(translate_string("Replace"), on_click=self.do_replace).classes(
                "bg-orange-600 text-white px-4",
            )
            self.replace_button.disable()
            ui.button(translate_string("Save Preview"), on_click=self.save_replace).classes(
                "bg-blue-600 text-white px-4",
            )

        self.source_select.set_options({key: label for key, label, _count in mapswap.source_choices(self.index)})
        self.source_select.on_value_change(lambda: (self.fill_targets(), self.invalidate()))
        self.arg_action_select.on_value_change(lambda: (self.fill_arguments(), self.invalidate()))
        self.condition_select.on_value_change(lambda: (self.fill_condition_targets(), self.invalidate()))
        for widget in (
            self.target_select,
            self.swap_project,
            self.condition_target_select,
            self.condition_project,
            self.variable_select,
            self.new_name_input,
            self.arg_select,
            self.arg_match_input,
            self.arg_value_input,
            self.arg_project,
            self.arg_substitute,
            self.arg_add_missing,
        ):
            widget.on_value_change(self.invalidate)
        self.mode.on_value_change(self.switch_mode)

    def _build_action_row(self) -> None:
        """The fields for replacing one Task action with another."""
        # -- action mode --------------------------------------------------
        with ui.row().classes("w-full items-center gap-2 mt-2") as self.action_row:
            self.source_select = (
                ui.select({}, label=translate_string("Replace this action"), with_input=True)
                .classes("flex-1 min-w-[220px]")
                .props("dense")
            )
            self.target_select = (
                ui.select({}, label=translate_string("...with this one"), with_input=True)
                .classes("flex-1 min-w-[260px]")
                .props("dense")
            )
            # Hidden under a scope, for the reason the Find tab's own gives.
            self.swap_project = (
                ui.select(
                    {"": translate_string("Every Project")} | {name: name for name in self.index.projects},
                    value="",
                    label=translate_string("Narrow to Project"),
                    with_input=True,
                )
                .classes("w-56")
                .props("dense")
            )
            self.swap_project.set_visibility(self.index.scope.is_everything)

    def _build_argument_row(self) -> None:
        """The fields for rewriting one argument of an action."""
        # -- argument mode ------------------------------------------------
        # Two rows, because this mode asks for four things and a fifth switch: which
        # action, which of its arguments, which of those actions (by what the argument
        # says now), and what to put there.  One row of five widgets would wrap into an
        # unreadable line on the width this dialog is pinned to.
        with ui.column().classes("w-full gap-2 mt-2") as self.argument_row:
            with ui.row().classes("w-full items-center gap-2"):
                self.arg_action_select = (
                    ui.select({}, label=translate_string("In this action"), with_input=True)
                    .classes("flex-1 min-w-[220px]")
                    .props("dense")
                )
                self.arg_select = (
                    ui.select({}, label=translate_string("...replace this argument"), with_input=True)
                    .classes("flex-1 min-w-[240px]")
                    .props("dense")
                )
                self.arg_project = (
                    ui.select(
                        {"": translate_string("Every Project")} | {name: name for name in self.index.projects},
                        value="",
                        label=translate_string("Narrow to Project"),
                        with_input=True,
                    )
                    .classes("w-56")
                    .props("dense")
                )
                self.arg_project.set_visibility(self.index.scope.is_everything)
            with ui.row().classes("w-full items-center gap-2"):
                self.arg_match_input = (
                    ui.input(label=translate_string("Only where the value contains (optional)"))
                    .classes("flex-1 min-w-[240px]")
                    .props("dense clearable")
                )
                self.arg_value_input = (
                    ui.input(label=translate_string("...and put this there"))
                    .classes("flex-1 min-w-[240px]")
                    .props("dense clearable")
                )
                # Off means the argument is SET to the new value; on means only the
                # matched text inside it changes.  Both are things people mean by
                # "replace", and which one they meant cannot be guessed from the two
                # boxes above -- so it is asked, in the one place where the answer is
                # visible while the values are being typed.
                self.arg_substitute = ui.checkbox(translate_string("Only the matching text")).props("dense")
                # Tasker leaves out an argument nobody ever set, so this is what makes
                # "give every Flash a Timeout" reach the Flashes that have none.  Off
                # by default: adding an argument to a hundred actions is a bigger thing
                # than editing the ones that already have it, and the preview marks
                # every row that is an addition rather than a change.
                self.arg_add_missing = ui.checkbox(translate_string("Add it where missing")).props("dense")
        self.argument_row.set_visibility(False)

    def _build_condition_row(self) -> None:
        """The fields for replacing one kind of Profile condition with another."""
        # -- condition mode -----------------------------------------------
        # Two pulldowns and a Project, the same shape as the action mode -- and for the
        # same reason: a Profile condition is replaced by KIND, and both halves of that
        # are a choice, one out of what the file holds and one out of what Tasker
        # offers.  Nothing else is asked, because there is nothing else to ask: a
        # condition's settings are its own and do not survive becoming another kind.
        with ui.row().classes("w-full items-center gap-2 mt-2") as self.condition_row:
            self.condition_select = (
                ui.select({}, label=translate_string("Replace this Profile condition"), with_input=True)
                .classes("flex-1 min-w-[240px]")
                .props("dense")
            )
            self.condition_target_select = (
                ui.select({}, label=translate_string("...with this one"), with_input=True)
                .classes("flex-1 min-w-[260px]")
                .props("dense")
            )
            self.condition_project = (
                ui.select(
                    {"": translate_string("Every Project")} | {name: name for name in self.index.projects},
                    value="",
                    label=translate_string("Narrow to Project"),
                    with_input=True,
                )
                .classes("w-56")
                .props("dense")
            )
            self.condition_project.set_visibility(self.index.scope.is_everything)
        self.condition_row.set_visibility(False)

    def _build_variable_row(self) -> None:
        """The fields for renaming a variable."""
        # -- variable mode ------------------------------------------------
        with ui.row().classes("w-full items-center gap-2 mt-2") as self.variable_row:
            self.variable_select = (
                ui.select({}, label=translate_string("Rename this variable"), with_input=True)
                .classes("flex-1 min-w-[320px]")
                .props("dense")
            )
            # A text box with suggestions, NOT a select.  Both jobs have to work here:
            # renaming to a name nothing uses yet, and replacing every use with a
            # variable that already exists ("everywhere this Task says %app_name, say
            # %app_package").  A select with new_value_mode looks like it does both and
            # does the first badly -- a typed name is only committed on Enter, and is
            # thrown away on blur, so the ordinary act of typing a name and reaching for
            # the button loses it.  An input always keeps what was typed, and
            # autocomplete offers the existing variables without ever standing between
            # the user and a name they are inventing.
            self.new_name_input = (
                ui.input(label=translate_string("...to this name"))
                .classes("flex-1 min-w-[260px]")
                .props("dense clearable")
            )
        self.variable_row.set_visibility(False)

    def restore_previous(self) -> bool:
        """Put back the Replace that was last set up, and return whether there was one."""
        # Come back to the Replace that was last set up, rather than to empty fields.
        #
        # Following a preview row no longer costs the preview -- the dialog docks to the
        # right edge and stays up (see _FindDialog.dock) -- but everything else that takes
        # this dialog down still ends the same way, and the Close button is pressed between
        # a preview and the decision it leads to often enough to be worth coming back from.
        #
        # The INPUTS were what was remembered, and the plan is rebuilt from them here.
        # That is a second pass over the file, and it is worth paying every time: it makes
        # "the Replace button is only ever enabled for a preview the user is looking at"
        # true by construction rather than by this dialog remembering to enforce it.  A
        # Plan could not be remembered in its place anyway -- its Sites hold live elements,
        # and holding those across a reopen is the stale-handle case apply()'s own
        # attachment check exists to catch.
        previous = self.view._replace_inputs
        if previous is None:
            return False

        # Taken BEFORE a single widget is touched.  Every set_value below fires
        # on_value_change, which runs invalidate, which clears the remembered ticks --
        # so reading them afterwards would always find nothing, and the restore would
        # silently do half its job.
        remembered = self.view._replace_ticks

        kind = previous[0]
        self.mode.set_value(kind)
        self.switch_mode()
        if kind == "argument":
            _, action, arg_id, new_value, match, project, substitute, add_missing = previous
            self.arg_action_select.set_value(action or None)
            # Stocked before the argument is chosen, for the reason fill_targets is called
            # here: a select silently drops a value that is not among its options.
            self.fill_arguments()
            self.arg_select.set_value(arg_id or None)
            self.arg_value_input.set_value(new_value)
            self.arg_match_input.set_value(match)
            self.arg_project.set_value(project or "")
            self.arg_substitute.set_value(substitute)
            self.arg_add_missing.set_value(add_missing)
        elif kind == "action":
            _, first, second, third = previous
            self.source_select.set_value(first or None)
            self.fill_targets()
            self.target_select.set_value(second or None)
            self.swap_project.set_value(third or "")
        elif kind == "condition":
            _, first, second, third = previous
            self.condition_select.set_value(first or None)
            # Stocked before the target is chosen, for the reason fill_targets is called
            # here: a select silently drops a value that is not among its options.
            self.fill_condition_targets()
            self.condition_target_select.set_value(second or None)
            self.condition_project.set_value(third or "")
        else:
            _, first, second, third = previous
            choices = self.held.get("variable_choices") or []
            position = next(
                (at for at, (name, owner, _label) in enumerate(choices) if (name, owner) == (first, second)),
                None,
            )
            self.variable_select.set_value(position)
            self.new_name_input.set_value(third)

        # Only when the fields came back intact.  Re-planning is also what notices that an
        # object the old plan pointed at has been deleted since -- which is the case the
        # remembered ticks are matched by identity rather than by position to survive.
        if self.current_inputs() == previous:
            self.build_preview(remembered)
        return True

    def current_inputs(self) -> tuple:
        """What the Replace fields say right now, in the form the plan is built from.

        One tuple per mode, of whatever length that mode needs.  It is compared whole
        (against the inputs the preview on screen was built from) and unpacked by the
        branch that built it, so the four shapes never meet.
        """
        if self.mode.value == "action":
            return (
                "action",
                self.source_select.value or "",
                self.target_select.value or "",
                self.swap_project.value or "",
            )
        if self.mode.value == "argument":
            return (
                "argument",
                self.arg_action_select.value or "",
                self.arg_select.value or "",
                self.arg_value_input.value or "",
                (self.arg_match_input.value or "").strip(),
                self.arg_project.value or "",
                bool(self.arg_substitute.value),
                bool(self.arg_add_missing.value),
            )
        if self.mode.value == "condition":
            return (
                "condition",
                self.condition_select.value or "",
                self.condition_target_select.value or "",
                self.condition_project.value or "",
            )
        # Integer keys into a parallel list, because a select's option keys are
        # serialized to the browser and a variable's identity is the PAIR (name,
        # owner) -- there is no JSON key for a tuple, and flattening the two into
        # one string would need an escape for a separator that a Task name may
        # legitimately contain.  The owner may be mapswap.EVERY_INSTANCE, which is
        # the entry meaning "every instance of this name", and passes straight
        # through to plan_variable_rename as it stands.
        choices = self.held.get("variable_choices") or []
        position = self.variable_select.value
        if isinstance(position, int) and 0 <= position < len(choices):
            name, owner = choices[position][0], choices[position][1]
        else:
            name, owner = "", ""
        return ("variable", name, owner, (self.new_name_input.value or "").strip())

    def variable_index(self) -> varxref.VariableIndex:
        """The variable cross-reference, built once per dialog and then held."""
        if self.held["variables"] is None:
            # Scoped, unlike varxref's other callers: a rename WRITES, and what it may
            # write to is what the app is displaying.  See build_index's own note on
            # why whole-file is the default there and this is the exception.
            self.held["variables"] = varxref.build_index(mapjump.current_scope(state=PrimeItems), state=PrimeItems)
        return self.held["variables"]

    def invalidate(self) -> None:
        """A field changed, so whatever is on screen is no longer what would happen.

        Clearing the plan rather than re-running it: re-planning on every keystroke
        of a variable name would scan the file per character, and a preview that
        refreshed itself under the user would make the Replace button's meaning
        depend on when they looked at it.
        """
        if self.held["plan"] is not None:
            self.held["plan"] = None
            self.held["inputs"] = None
            self.replace_area.clear()
            self.replace_summary.set_text("")
        # The ticks go with the preview.  They describe changes to a question that is
        # no longer the one on screen, and carrying them into the next preview would
        # tick rows the user never looked at.
        self.view._replace_ticks = None
        self.replace_button.disable()

    def fill_targets(self) -> None:
        """Re-stock the target pulldown for the chosen source action.

        Every candidate is labelled with what choosing it would cost -- what
        carries over and what does not -- so that nothing in this list is a
        surprise, and the pairs that keep the most sit at the top.  Blocked
        targets stay in the list with their reason as the label: a user who
        cannot find an action learns nothing, one who reads why learns the
        answer to the question they were about to ask.
        """
        source = self.source_select.value
        if not source:
            self.target_select.set_options({})
            return
        self.target_select.set_options(
            {key: label for key, label, _fidelity in mapswap.fidelity_choices(source, state=PrimeItems)},
            value=None,
        )

    def fill_arguments(self) -> None:
        """Re-stock the argument pulldown for the chosen action.

        Every argument is listed, including the ones this cannot write: an App or an
        Icon is a picker's subtree rather than a typed value, and a user who cannot
        find the argument learns nothing while one who reads why learns the answer.
        The refusal rides in the label; the planner says it again in the preview, since
        the pulldown is not where the decision is finally made.
        """
        action = self.arg_action_select.value
        if not action:
            self.arg_select.set_options({})
            return
        self.arg_select.set_options(
            {arg_id: label for arg_id, label, _refusal in mapswap.argument_choices(action, state=PrimeItems)},
            value=None,
        )

    def fill_condition_targets(self) -> None:
        """Re-stock the target pulldown for the chosen Profile condition.

        Every kind Tasker can watch for is in the list, labelled with what choosing it
        would do -- 'a fresh, empty Day', or the reason a plugin's condition cannot be
        built at all.  Same courtesy fill_targets pays a blocked action target, and the
        same reason: a user who cannot find a condition learns nothing, one who reads
        why learns the answer to the question they were about to ask.
        """
        source = self.condition_select.value
        if not source:
            self.condition_target_select.set_options({})
            return
        self.condition_target_select.set_options(
            {key: label for key, label, _fidelity in mapswap.condition_targets(source, state=PrimeItems)},
            value=None,
        )

    def switch_mode(self) -> None:
        """Show one mode's fields, hide the others', and drop any preview."""
        self.action_row.set_visibility(self.mode.value == "action")
        self.argument_row.set_visibility(self.mode.value == "argument")
        self.condition_row.set_visibility(self.mode.value == "condition")
        self.variable_row.set_visibility(self.mode.value == "variable")
        if self.mode.value == "argument" and not self.arg_action_select.options:
            self.arg_action_select.set_options(
                {key: label for key, label, _count in mapswap.source_choices(self.index)},
            )
        if self.mode.value == "condition" and not self.condition_select.options:
            self.condition_select.set_options(
                {key: label for key, label, _count in mapswap.condition_choices(self.index)},
            )
        if self.mode.value == "variable" and not self.held.get("variable_choices"):
            choices = mapswap.variable_choices(self.variable_index())
            self.held["variable_choices"] = choices
            self.variable_select.set_options(
                {position: label for position, (_name, _owner, label) in enumerate(choices)},
            )
            # The same variables offered as completions on the target box: a rename
            # target is only ever a name, so two locals sharing one in different Tasks
            # are the same string to write.  Sorted rather than ranked by use like the
            # source list -- this one is looked up, not browsed.
            self.new_name_input.set_autocomplete(sorted({name for name, _owner, _label in choices}))
        self.invalidate()

    def ticker(self, plan: mapswap.Plan, position: int) -> Callable:
        """One preview row's tick box: put this change in or out of what Replace applies.

        A factory rather than a lambda built in the loop, for the usual reason: a
        lambda would close over the loop variable and every box would end up
        ticking the last row.
        """

        def ticked(event: object) -> None:
            if getattr(event, "value", False):
                plan.selected.add(position)
            else:
                plan.selected.discard(position)
            # Recorded as it happens rather than on the way out: the way out is a click
            # on one of these rows, which closes the dialog from inside that row's own
            # handler, so there is no later moment reliably reached.
            self.remember_ticks()

        return ticked

    def draw(self, plan: mapswap.Plan) -> None:
        """Draw the plan: warnings, then what cannot be changed, then what can.

        Skips before changes because they are the part the user must read and the
        part they will not scroll back up for.  Every location is a link, because
        the only way to judge "should this one change" is to go and look at it.
        """
        self.replace_area.clear()
        self.replace_summary.set_text(f"{plan.what} -- {plan.tally()}")

        with self.replace_area, ui.column().classes("w-full gap-1"):
            for warning in plan.warnings:
                ui.label(warning).classes(
                    "text-xs text-orange-600 dark:text-orange-400 border-l-4 border-orange-400 pl-2 py-1",
                )

            if plan.skips:
                ui.label(
                    f"{translate_string('Cannot be changed')} ({len(plan.skips)})",
                ).classes("text-xs font-bold text-red-500 mt-2")
                for skip in plan.skips[:_REPLACE_SKIP_LIMIT]:
                    with ui.row().classes("w-full items-baseline gap-2 pl-2"):
                        ui.link(skip.where.label, "#").on("click", self.jump_to(skip.where)).classes(
                            "text-blue-600 dark:text-blue-400 font-mono text-xs shrink-0 "
                            "decoration-dotted hover:underline",
                        )
                        ui.label(skip.explanation).classes("text-xs text-gray-500 truncate")
                if len(plan.skips) > _REPLACE_SKIP_LIMIT:
                    ui.label(
                        f"...{len(plan.skips) - _REPLACE_SKIP_LIMIT} {translate_string('more')}",
                    ).classes("text-xs text-gray-500 italic pl-2")

            if not plan.changes:
                ui.label(
                    translate_string("Nothing here would change."),
                ).classes("text-sm text-gray-500 italic mt-2")
                return

            project = None
            for position, change in enumerate(plan.changes):
                if change.site.where.project != project:
                    project = change.site.where.project
                    ui.label(
                        (
                            f"{translate_string('Project')} '{project}'"
                            if project
                            else translate_string("In no Project")
                        ),
                    ).classes("text-xs font-bold text-orange-500 mt-2")
                with ui.row().classes(
                    "w-full items-baseline py-1 border-b dark:border-gray-700 px-2 rounded",
                ):
                    ui.checkbox(
                        value=position in plan.selected,
                        on_change=self.ticker(plan, position),
                    ).props("dense")
                    ui.link(change.site.where.label, "#").on("click", self.jump_to(change.site.where)).classes(
                        "text-blue-600 dark:text-blue-400 font-mono text-sm shrink-0 decoration-dotted hover:underline",
                    )
                with ui.row().classes("w-full items-baseline pl-10 pb-1"):
                    ui.label(f"{change.before}  →  {change.after}").classes(
                        "text-xs text-gray-600 dark:text-gray-300 font-mono truncate",
                    )
                    if change.note:
                        ui.label(change.note).classes("text-xs text-orange-600 dark:text-orange-400 truncate")

    def remember_ticks(self) -> None:
        """Keep the current tick boxes on the view, ready for the next reopen."""
        plan = self.held["plan"]
        self.view._replace_ticks = plan.ticked_identities() if plan is not None else None

    def build_preview(self, restore: collections.Counter | None = None) -> None:
        """Build the plan for whatever the fields say, and show it.

        `restore` re-applies the tick boxes from a previous preview of the same
        question -- the way back from following one of its own rows.  Applied after the
        plan is built and before it is drawn, so what appears on screen is what the
        user left, defaults and all.

        One branch per mode to BUILD the plan, and one tail for all four to show it:
        what a preview is -- held, drawn, ticked, and the only thing the Replace button
        can act on -- is the same whatever question produced it, and a mode with its own
        copy of that tail is a mode that can drift out of step with the rule.
        """
        inputs = self.current_inputs()
        kind = inputs[0]

        if kind == "action":
            _, source, target, project = inputs
            if not source or not target:
                ui.notify(
                    translate_string("Choose an action to replace, and one to replace it with."),
                    type="warning",
                )
                return
            plan = mapswap.plan_action_swap(source, target, project, state=PrimeItems)
        elif kind == "argument":
            _, action, arg_id, new_value, match, project, substitute, add_missing = inputs
            if not action or not arg_id:
                ui.notify(
                    translate_string("Choose an action, and which of its arguments to replace."),
                    type="warning",
                )
                return
            plan = mapswap.plan_argument_replace(
                action, arg_id, new_value, match, project, substitute, add_missing, state=PrimeItems
            )
            if plan.is_empty and not plan.skips and not plan.warnings:
                # Said out loud rather than left to an empty list: "nothing holds that
                # value" and "they all hold the new one already" look identical on
                # screen and mean opposite things.
                ui.notify(
                    translate_string("Nothing in scope has that argument to change."),
                    type="warning",
                )
        elif kind == "condition":
            _, source, target, project = inputs
            if not source or not target:
                ui.notify(
                    translate_string("Choose a Profile condition to replace, and one to replace it with."),
                    type="warning",
                )
                return
            plan = mapswap.plan_condition_replace(source, target, project, state=PrimeItems)
        else:
            _, name, owner, new_name = inputs
            if not name or not new_name:
                ui.notify(translate_string("Choose a variable, and type the new name."), type="warning")
                return
            plan = mapswap.plan_variable_rename(self.variable_index(), name, owner, new_name, state=PrimeItems)

        if restore is not None:
            plan.restore_ticks(restore)

        self.held.update(plan=plan, inputs=inputs)
        self.view._replace_inputs = inputs
        self.draw(plan)
        self.remember_ticks()
        if plan.changes:
            self.replace_button.enable()
        else:
            self.replace_button.disable()

    def preview(self) -> None:
        """The Preview button: a fresh look at the question, tick boxes at their defaults."""
        self.build_preview()

    async def rebuild_after_replace(self) -> None:
        """Redraw the view the Replace was launched from, so it shows what just changed.

        The view on screen was rendered from the configuration as it stood BEFORE the
        apply, and every one of these edits is a content change -- an action becomes a
        different action, a variable reads by a different name -- so what the user is
        looking at the moment the dialog closes is, line for line, the thing they just
        replaced.  Leaving that until the next press of Map View invites them to run
        the same Replace again on a preview that says it is still there.

        Whichever view asked, not always the Map: a Replace started from the Diagram
        leaves that just as stale, and rebuilding a Map over it would answer a question
        about one view by switching the user to another.  The view type comes off the
        title, which is what view_event built it from ("Map View", "Diagram View").

        Run through view_event -- the same call the Map/Diagram/Tree buttons make -- so
        the rebuild honours whatever the user currently has selected, including the
        single-item selection the Replace was scoped to.  No overrides: this is the
        view they already had, rebuilt, not a different one.
        """
        handlers = getattr(self.view.master_gui, "event_handlers", None)
        if handlers is None:
            ui.notify(
                translate_string("The change is applied.  Press Map View to see it."),
                type="info",
                position="top",
            )
            return

        view_type = (self.view.title.split() or ["Map"])[0].lower()
        if view_type not in ("map", "diagram", "tree"):
            view_type = "map"
        await handlers.view_event(view_type)

    async def do_replace(self) -> None:
        """The Replace button.  Only ever applies the plan on screen.

        Re-checks that the plan matches the fields even though every field
        invalidates it: the button is the last point at which this is cheap to
        verify, and the cost of the check being wrong is a configuration changed
        in a way nobody previewed.
        """
        plan = self.held["plan"]
        if plan is None or self.held["inputs"] != self.current_inputs():
            ui.notify(translate_string("Press Preview first."), type="warning")
            self.invalidate()
            return
        if not plan.selected:
            ui.notify(translate_string("Nothing is ticked."), type="warning")
            return

        changed, errors = mapswap.apply(plan, state=PrimeItems)
        for message in errors[:_REPLACE_ERROR_LIMIT]:
            ui.notify(message, type="negative")
        if changed:
            ui.notify(
                f"{changed} {translate_string('changed')}. {translate_string('Undo is available.')}",
                type="positive",
            )
            # The variable index this dialog holds describes the file as it was, so
            # it is dropped rather than refreshed -- rebuilding here would hand back a
            # preview of a plan that has already been applied.  The remembered ticks go
            # with it: they belong to a plan there is no longer any reason to restore.
            self.held.update(variables=None, variable_choices=None, plan=None, inputs=None)
            self.view._replace_inputs = None
            self.view._replace_ticks = None
            self.replace_button.disable()
            self.dialog.close()

            # Rebuilt inside the VIEW's slot, not the dialog's.  Closing the dialog
            # deletes it, and anything that resolves its client through a deleted slot
            # dies there silently -- the same re-entry, for the same reason, as
            # jump_to's.  The pulldowns are deliberately NOT refreshed: no Project,
            # Profile, Task or Scene was added or removed, so every option in them
            # still resolves.
            with self.view.scroll_area:
                await self.rebuild_after_replace()
        else:
            ui.notify(translate_string("Nothing was changed."), type="warning")

    def save_replace(self) -> None:
        """Write the preview to a file, ticks and all.

        Worth having for the plan the user did NOT apply as much as the one they
        did: a hundred-row preview is a work list, and which rows they decided to
        leave does not survive closing the dialog otherwise.
        """
        plan = self.held["plan"]
        if plan is None:
            ui.notify(translate_string("Press Preview first."), type="warning")
            return
        file_name = mapswap.write_swap_report(mapswap.report_rows(plan))
        if file_name:
            ui.notify(f"{translate_string('Replace preview saved as')} {file_name}", type="positive")
        else:
            ui.notify(translate_string("Replace preview could not be saved."), type="negative")
