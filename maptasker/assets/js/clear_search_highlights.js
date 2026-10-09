
                const outerContainer = document.getElementById("c__SCROLL_AREA_ID__");
                if (!outerContainer) return;
                const container = outerContainer.querySelector('.q-scrollarea__content') || outerContainer;

                function clearHighlights(root) {
                    const highlights = root.querySelectorAll ? root.querySelectorAll('.search-highlight') : [];
                    highlights.forEach(el => {
                        const textNode = document.createTextNode(el.textContent);
                        el.parentNode.replaceChild(textNode, el);
                    });
                    const children = root.querySelectorAll ? root.querySelectorAll('*') : [];
                    children.forEach(child => {
                        if (child.shadowRoot) clearHighlights(child.shadowRoot);
                    });
                }

                // Prefer unwrapping the spans search_event recorded, which puts each match's
                // own text node back where the span was. The generic sweep below cannot do
                // that -- it substitutes freshly created text nodes -- and search_event's
                // cached index (see guiwins.py) refers to the nodes themselves, so letting
                // the sweep loose on them means throwing that index away and making the next
                // search crawl the whole view again from scratch.
                const cache = container.__mtSearchIndex;
                if (cache && cache.highlights) {
                    for (const span of cache.highlights) {
                        if (span.parentNode && span.firstChild) {
                            span.parentNode.replaceChild(span.firstChild, span);
                        }
                    }
                    cache.highlights = [];
                }
                if (container.querySelector('.search-highlight')) {
                    clearHighlights(container);
                    container.__mtSearchIndex = null;  // no longer describes these text nodes
                }

                // Also turn off any Diagram-view connector highlighting left by clicking a connector.
                container.querySelectorAll('.connector-highlight').forEach(el => {
                    el.classList.remove('connector-highlight');
                });
                container.querySelectorAll('.connector-task-box').forEach(el => {
                    el.classList.remove('connector-task-box');
                });

                // ...and the outline left on whatever a clicked report finding jumped to
                // (see mapjump.jump_js).  "Clear" means the view is back to how it was
                // rendered, whichever of the three ways something on it came to stand out.
                container.querySelectorAll('.__HIGHLIGHT_CLASS__').forEach(el => {
                    el.classList.remove('__HIGHLIGHT_CLASS__');
                });
            