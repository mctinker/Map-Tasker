
            function mtRevealAncestors(element) {
                // A line the interactive Diagram view has folded away or filtered out is
                // hidden outright, and scrolling to something with no box is scrolling to
                // nowhere -- so ask that view to open it back up first.  The hook is absent
                // on every other page and on a Diagram with no model behind it, which is why
                // it is asked for rather than called (see diagintr.interaction_js).
                if (window.mtDiagramReveal) window.mtDiagramReveal(element);
                for (let node = element; node; node = node.parentElement) {
                    if (getComputedStyle(node).contentVisibility === "auto") {
                        node.style.contentVisibility = "visible";
                    }
                }
            }
