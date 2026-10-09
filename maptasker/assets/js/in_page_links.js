
            (() => {
                const container = document.getElementById("c__SCROLL_AREA_ID__");
                if (!container || container.dataset.mtLinksWired) return;
                container.dataset.mtLinksWired = "1";
__REVEAL_ANCESTORS_JS__
__RESOLVE_TARGET_JS__
                container.addEventListener("click", (event) => {
                    const link = event.target.closest('a[href^="#"]');
                    if (!link || !container.contains(link)) return;
                    const name = decodeURIComponent(link.getAttribute("href").slice(1));
                    const anchor = name ? document.getElementById(name) : null;
                    if (!anchor) return;   // Nothing of that name here: leave the browser to it.
                    // The anchor is often an empty marker with no box of its own, so what
                    // gets scrolled to is the line it stands in front of (see mtJumpTarget).
                    mtRevealAncestors(anchor);
                    const target = mtJumpTarget(anchor);
                    if (!target) return;
                    event.preventDefault();
                    mtRevealAncestors(target);
                    // With the "twisty" option on, the target can be inside a collapsed
                    // <details>, and scrolling to something not being displayed does nothing.
                    for (let box = target.closest("details"); box; box = box.parentElement?.closest("details")) {
                        box.open = true;
                    }
                    target.scrollIntoView({ behavior: "auto", block: "start" });
                });
            })()
            