// The page-side half of the Map/Diagram/Misc view search (see TextViewSearch.search_event in
// guiwins_search.py): crawls the text of the rendered view, highlights every occurrence of
// the search term, and answers with where each one is.
//
// It is run through client.run_javascript as the body of a function, so it ends in `return`.
// Before it is sent, guiwins_search.search_crawl_js replaces the four double-underscore
// placeholders below with the id of the view's scroll area, the (lowercased, JSON-encoded) search term, the
// term's length and the view's content token.

const outerContainer = document.getElementById("c__SCROLL_AREA_ID__");
// Shape every return the same way: the Python side reads .get() off this, so
// handing back a bare list here would swap the timeout for an AttributeError.
if (!outerContainer) return { results: [], totalMatches: 0, truncated: false };

const container = outerContainer.querySelector('.q-scrollarea__content') || outerContainer;

const searchTerm = __SEARCH_TERM__;
const termLength = __TERM_LENGTH__;
// Identifies the content in the view (see _mark_content_ready); 0 while it is
// still streaming in, in which case nothing may be cached about it.
const contentToken = __CONTENT_TOKEN__;

// 1. Purge previous search highlights completely across Shadow boundaries.
//    Used only when there is no usable cached index -- it swaps each highlight
//    for a brand-new text node, which is exactly what the cached index cannot
//    survive (it holds references to the nodes themselves). The cached path
//    below unwraps the very same spans without that.
function clearPreviousHighlights(root) {
    const highlights = root.querySelectorAll ? root.querySelectorAll('.search-highlight') : [];
    highlights.forEach(el => {
        const textNode = document.createTextNode(el.textContent);
        el.parentNode.replaceChild(textNode, el);
    });
    const children = root.querySelectorAll ? root.querySelectorAll('*') : [];
    children.forEach(child => {
        if (child.shadowRoot) {
            clearPreviousHighlights(child.shadowRoot);
        }
    });
}

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
//    (joined by literal "\n", relying on white-space:pre to render them as
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
function buildIndex() {
    const textNodes = [];  // { node, start }
    let fullText = '';

    function collectTextNodes(node) {
        if (node.shadowRoot) {
            collectTextNodes(node.shadowRoot);
        }

        if (node.nodeType === 3) {
            if (node.parentNode &&
                node.parentNode.tagName !== 'SCRIPT' &&
                node.parentNode.tagName !== 'STYLE') {
                textNodes.push({ node, start: fullText.length });
                fullText += node.nodeValue;
            }
        } else if (node.nodeType === 1 && node.tagName === 'BR') {
            // The Diagram view is plain text with literal "\n" line breaks, but the
            // Map/Misc/Tree views are real HTML that marks line breaks with <br>
            // elements instead -- treat each one as a line break in the transcript
            // too, so line numbers/text line up correctly there as well.
            fullText += '\n';
        }

        // Snapshot into a static array so later DOM mutations (done in the
        // second pass below) can never feed back into this traversal.
        if (node.childNodes && node.childNodes.length) {
            for (const child of Array.from(node.childNodes)) {
                collectTextNodes(child);
            }
        }
    }

    collectTextNodes(container);

    // Map a global offset into fullText -> 0-based line number, via the offset of
    // every line start (binary search since a large diagram can have many lines).
    const lineStarts = [0];
    for (let i = 0; i < fullText.length; i++) {
        if (fullText[i] === '\n') lineStarts.push(i + 1);
    }
    return { token: contentToken, textNodes, fullText, lineStarts, highlights: [] };
}

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
if (cache && contentToken > 0 && cache.token === contentToken) {
    for (const span of cache.highlights) {
        if (span.parentNode && span.firstChild) {
            span.parentNode.replaceChild(span.firstChild, span);
        }
    }
    cache.highlights = [];
    usedCachedIndex = true;
    // A highlight the index has no record of means something outside this routine
    // rewrote the text nodes, so the index can no longer be trusted to match them.
    if (container.querySelector('.search-highlight')) {
        clearPreviousHighlights(container);
        cache = buildIndex();
        usedCachedIndex = false;
    }
} else {
    clearPreviousHighlights(container);
    cache = buildIndex();
}
// Keep nothing while the content is still streaming in: the index would describe
// a document that is only partly there.
container.__mtSearchIndex = contentToken > 0 ? cache : null;

const textNodes = cache.textNodes;
const fullText = cache.fullText;
const lineStarts = cache.lineStarts;

function lineNumberForOffset(offset) {
    let lo = 0, hi = lineStarts.length - 1;
    while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (lineStarts[mid] <= offset) lo = mid; else hi = mid - 1;
    }
    return lo;
}
function lineTextForOffset(offset) {
    const ln = lineNumberForOffset(offset);
    const start = lineStarts[ln];
    const end = ln + 1 < lineStarts.length ? lineStarts[ln + 1] - 1 : fullText.length;
    return fullText.substring(start, end);
}

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
function transcriptLower() {
    if (cache.lowerText === undefined) {
        const lower = cache.fullText.toLowerCase();
        // A handful of characters (e.g. U+0130) lowercase to a different number
        // of characters, which would shift every offset after them. Rare enough
        // to detect and step around rather than try to track.
        cache.lowerText = lower.length === cache.fullText.length ? lower : null;
    }
    return cache.lowerText;
}

const matches = [];  // { pos, index, globalOffset } -- pos is the index slot to patch
let spanningSkipped = 0;
const lowerText = transcriptLower();
if (lowerText === null) {
    // Fallback: the transcript's offsets can't be trusted for this content, so
    // take the old per-node scan (first hit in each node) rather than risk
    // wrapping the wrong characters.
    for (let pos = 0; pos < textNodes.length; pos++) {
        const entry = textNodes[pos];
        const value = entry.node.nodeValue;
        if (!value) continue;
        const index = value.toLowerCase().indexOf(searchTerm);
        if (index !== -1) {
            matches.push({ pos, index, globalOffset: entry.start + index });
        }
    }
} else {
    // Occurrences come out in ascending order, so the index slot for each one can
    // be found by walking a cursor forward instead of searching from scratch.
    let cursor = 0;
    let from = 0;
    for (;;) {
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
        if (index < 0 || !value || index + termLength > value.length) {
            spanningSkipped++;
            continue;
        }
        matches.push({ pos: cursor, index, globalOffset: at });
    }
}

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
matchesToShow.forEach((match, rank) => {
    match.rank = rank;
    const group = byNode.get(match.pos);
    if (group) { group.push(match); } else { byNode.set(match.pos, [match]); }
});

const repairs = new Map();  // index slot -> the entries that now replace it
for (const [pos, group] of byNode) {
    const entry = textNodes[pos];
    // Entries for the pieces split off this node, kept in document order.
    const pieces = [];
    for (let i = group.length - 1; i >= 0; i--) {
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
        if (span.firstChild) {
            added.push({ node: span.firstChild, start: entry.start + match.index });
        }
        const tail = span.nextSibling;
        if (tail && tail.nodeType === 3) {
            added.push({ node: tail, start: entry.start + match.index + termLength });
        }
        pieces.unshift(...added);
    }
    repairs.set(pos, [entry, ...pieces]);
}

for (const match of matchesToShow) {
    results.push({
        elementId: "search_target_" + (match.rank + 1),
        text: lineTextForOffset(match.globalOffset).trim().substring(0, 100),
        lineNumber: lineNumberForOffset(match.globalOffset) + 1,
    });
}

if (container.__mtSearchIndex && repairs.size) {
    const rebuilt = [];
    for (let pos = 0; pos < textNodes.length; pos++) {
        const replacements = repairs.get(pos);
        if (replacements) {
            for (const entry of replacements) rebuilt.push(entry);
        } else {
            rebuilt.push(textNodes[pos]);
        }
    }
    cache.textNodes = rebuilt;
}

return {
    results: results,
    totalMatches: matches.length,
    truncated: truncated,
    cachedIndex: usedCachedIndex,
    spanningSkipped: spanningSkipped,
};
