
        return (() => {
__REVEAL_ANCESTORS_JS__
            const container = document.getElementById(__CONTAINER_ID__);
            if (!container) return false;
            const patterns = __PATTERNS__;
            const placement = __PLACEMENT__;
            const anchor = __ANCHOR__;
            if (!patterns.length && !placement && !anchor) return false;

            // Any highlight left by a previous jump goes first, in both views' shared class,
            // so only the object just asked for is marked.
            document.querySelectorAll('.__HIGHLIGHT_CLASS__').forEach(
                (element) => element.classList.remove('__HIGHLIGHT_CLASS__'),
            );

            const walker = () => document.createTreeWalker(container, NodeFilter.SHOW_TEXT);

            // The recorded line, as a node and an offset into it.
            //
            // The interactive Diagram view gives every line an element of its own carrying
            // its number (see diagintr), so the line is asked for directly and only the
            // column is counted -- across that one line's text nodes, which a connector or
            // an object name splits it into.
            //
            // The walk below is what this did before there were line elements, and is kept
            // for a Diagram rendered without them.  It cannot simply be used for both: the
            // newline that ends a line now sits in a hidden element of its own, so counting
            // newlines through the text nodes arrives at column 0 of the wanted line already
            // standing at the END of the previous line's newline node -- the right position,
            // in a node with no line text left in it to highlight.
            function seekWithinLine(lineElement, column) {
                const crawl = document.createTreeWalker(lineElement, NodeFilter.SHOW_TEXT);
                for (let node = crawl.nextNode(); node; node = crawl.nextNode()) {
                    const text = node.nodeValue;
                    const ends = text.indexOf("\n");
                    const usable = ends === -1 ? text.length : ends;
                    if (column < usable || (column === usable && ends !== -1)) {
                        return { node: node, offset: column };
                    }
                    column -= usable;
                    // The line ends in this node and the column is past the end of it, so it
                    // is not a column on this line at all.
                    if (ends !== -1) return null;
                }
                return null;
            }

            function seek(lineNumber, column) {
                const lineElement = container.querySelector('[data-line="' + lineNumber + '"]');
                if (lineElement) return seekWithinLine(lineElement, column);
                let line = 0;
                const crawl = walker();
                for (let node = crawl.nextNode(); node; node = crawl.nextNode()) {
                    const text = node.nodeValue;
                    if (!text.length) continue;
                    let from = 0;
                    while (from <= text.length) {
                        if (line === lineNumber) {
                            const rest = text.indexOf("\n", from);
                            const end = rest === -1 ? text.length : rest;
                            if (column <= end - from) return { node: node, offset: from + column };
                            column -= end - from;
                            // The line ends in this node and the column is past the end of
                            // it, so it is not a column on this line at all -- walking on
                            // into the next one would answer with a position on the wrong
                            // line, which is worse than not answering.
                            if (rest !== -1) return null;
                            break;   // The line continues in the next node.
                        }
                        const next = text.indexOf("\n", from);
                        if (next === -1) break;
                        line += 1;
                        from = next + 1;
                    }
                }
                return null;
            }

            // The fallback: the first line holding one of the forms this object is drawn
            // as, preferring the earlier forms.  One walk, keeping the best so far, since a
            // later pattern matching an earlier line must not beat the first pattern
            // matching a later one -- "Test1" without its trailing space matches the line
            // drawn for "Test13", which is exactly what the ordering is there to settle.
            function search() {
                let best = null;
                const crawl = walker();
                for (let node = crawl.nextNode(); node; node = crawl.nextNode()) {
                    const text = node.nodeValue;
                    for (let rank = 0; rank < patterns.length; rank++) {
                        if (best && best.rank <= rank) break;
                        const at = text.indexOf(patterns[rank]);
                        if (at >= 0) best = { rank: rank, node: node, offset: at, length: patterns[rank].length };
                    }
                    if (best && best.rank === 0) break;
                }
                return best;
            }

            // The interactive Diagram wraps every object's name in an element of its own
            // (see diagintr), and an element is an exact answer: no counting, no clamping,
            // and the whole name rather than as much of it as fits in one text node.  The
            // two below are what this did before there were elements, and remain the answer
            // for a Diagram rendered from a file an older run left on disk.
            if (anchor) {
                const element = container.querySelector('[data-anchor="' + CSS.escape(anchor) + '"]');
                if (element) {
                    element.classList.add('__HIGHLIGHT_CLASS__');
                    mtRevealAncestors(element);
                    element.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'auto'});
                    for (let box = element.parentElement; box; box = box.parentElement) {
                        if (box.scrollWidth > box.clientWidth) box.scrollLeft = 0;
                    }
                    return true;
                }
            }

            let found = null;
            if (placement) {
                const spot = seek(placement[0], placement[1]);
                if (spot) {
                    // A length of zero is "the name could not be placed on the line after
                    // all" (see diagram._place): the line is still the right one, so all of
                    // it that is in this node is marked rather than nothing at all.
                    const rest = spot.node.nodeValue.indexOf("\n", spot.offset);
                    const toEnd = (rest === -1 ? spot.node.nodeValue.length : rest) - spot.offset;
                    found = { node: spot.node, offset: spot.offset, length: placement[2] || toEnd };
                }
            }
            if (!found) found = search();
            if (!found) return false;

            // Clamped to the node the span starts in.  A name is drawn as one unbroken run
            // of text, so this is the whole of it; the clamp is there for the case where a
            // connector span has split the line between the start and the end, where
            // highlighting the first part of the name is still an answer.
            const end = Math.min(found.offset + found.length, found.node.nodeValue.length);
            const span = document.createElement('span');
            span.className = '__HIGHLIGHT_CLASS__';
            const range = document.createRange();
            range.setStart(found.node, found.offset);
            range.setEnd(found.node, end);
            range.surroundContents(span);
            mtRevealAncestors(span);
            span.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'auto'});
            // Back to column 1, as the connector jump buttons do: a wide diagram scrolled
            // sideways puts the reader in the middle of a line.
            for (let box = span.parentElement; box; box = box.parentElement) {
                if (box.scrollWidth > box.clientWidth) box.scrollLeft = 0;
            }
            return true;
        })();
    