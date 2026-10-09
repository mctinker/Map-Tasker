
                const outerContainer = document.getElementById("c__SCROLL_AREA_ID__");
                if (!outerContainer || outerContainer.dataset.connectorClickWired) return;
                outerContainer.dataset.connectorClickWired = "1";
                const connectorTasks = __CONNECTOR_TASKS__;
__REVEAL_ANCESTORS_JS__

                // Quasar's own q-scroll-area styling sets "contain: strict" on outerContainer,
                // which creates a new containing block for position:fixed descendants -- a button
                // appended inside it would be clipped to and positioned relative to the scroll
                // area's box instead of the viewport. Appending to document.body avoids that, at
                // the cost of needing to clean up by hand: remove any leftover buttons from a
                // previous Diagram view load first (clear()-ing the view's container doesn't touch
                // elements parented directly under body).
                document.querySelectorAll(".connector-jump-button").forEach((el) => el.remove());

                // The Task this end of a connector belongs to: of the Tasks the connector's
                // calls join, the one drawn on the line nearest the end that was jumped to
                // (a Task run by two Profiles is drawn more than once, so the nearest
                // drawing, not just the first).
                function endTaskElement(end, id) {
                    const endLine = end.closest(".mt-dline");
                    if (!endLine) return null;
                    const row = parseInt(endLine.dataset.line, 10);
                    let best = null;
                    let bestGap = Infinity;
                    (connectorTasks[id] || []).forEach((anchor) => {
                        outerContainer.querySelectorAll('.mt-dnode[data-anchor="' + anchor + '"]').forEach((el) => {
                            const line = el.closest(".mt-dline");
                            const gap = line ? Math.abs(parseInt(line.dataset.line, 10) - row) : Infinity;
                            if (gap < bestGap) {
                                best = el;
                                bestGap = gap;
                            }
                        });
                    });
                    return best;
                }

                // The red rectangle round the Tasks a clicked connector joins.  Each Task is
                // marked where it is drawn nearest either end of the connector: one run by
                // two Profiles is drawn twice, and only one of the two is what this
                // connector is joined to.  An outline, so no column moves (see the CSS).
                function boxConnectorTasks(matches, id) {
                    const rows = [matches[0], matches[matches.length - 1]].map((el) => {
                        const line = el.closest(".mt-dline");
                        return line ? parseInt(line.dataset.line, 10) : NaN;
                    });
                    (connectorTasks[id] || []).forEach((anchor) => {
                        let best = null;
                        let bestGap = Infinity;
                        outerContainer.querySelectorAll('.mt-dnode[data-anchor="' + anchor + '"]').forEach((el) => {
                            const line = el.closest(".mt-dline");
                            if (!line) return;
                            const at = parseInt(line.dataset.line, 10);
                            const gap = Math.min(...rows.map((row) => Math.abs(row - at)));
                            if (gap < bestGap) {
                                best = el;
                                bestGap = gap;
                            }
                        });
                        if (best) best.classList.add("connector-task-box");
                    });
                }

                // Scrolls sideways, only if need be, until that Task's name is on screen.
                // Called once a jump has put the connector's line in view and pinned the
                // diagram back to column 1, so a Task already in view leaves it there.
                function revealEndTask(end, id) {
                    const task = endTaskElement(end, id);
                    if (!task) return;
                    mtRevealAncestors(task);
                    for (let a = task.parentElement; a; a = a.parentElement) {
                        if (a.scrollWidth <= a.clientWidth) continue;
                        const view = a.getBoundingClientRect();
                        const name = task.getBoundingClientRect();
                        if (name.left >= view.left && name.right <= view.right) continue;
                        // The name's left edge a sixth of the way in, so the "└─" that
                        // introduces it and a little of what is around it show too.
                        a.scrollLeft += name.left - view.left - view.width / 6;
                    }
                }

                function makeJumpButton(label, bottomOffset) {
                    const btn = document.createElement("button");
                    btn.textContent = label;
                    btn.className = "connector-jump-button";
                    btn.style.bottom = bottomOffset + "px";
                    btn.addEventListener("click", (event) => {
                        event.stopPropagation();
                        const target = btn._jumpTarget;
                        if (target) {
                            // A chunk currently skipped by content-visibility: auto (see
                            // process_data()'s chunking) never got laid out, so its descendants'
                            // getBoundingClientRect() is meaningless and scrollIntoView() would
                            // land in the wrong place. Force that chunk to lay out for real first
                            // -- it's the one we're about to scroll to anyway, so there's no
                            // wasted work, and leaving it visible afterward is harmless.
                            mtRevealAncestors(target);
                            // Instant, not smooth: the jump can cover tens of thousands of pixels
                            // on a large diagram, where an animated scroll would be slow to land
                            // and distracting rather than helpful.
                            //
                            // Vertical placement only. Centering horizontally on the connector
                            // (inline: "center") parked a wide diagram mid-line, so the user
                            // landed on the right line but somewhere out in the middle of it;
                            // "nearest" keeps scrollIntoView from moving sideways on its own and
                            // the loop below then pins every scrollable ancestor back to column 1.
                            target.scrollIntoView({block: "center", inline: "nearest", behavior: "auto"});
                            for (let a = target.parentElement; a; a = a.parentElement) {
                                if (a.scrollWidth > a.clientWidth) {
                                    a.scrollLeft = 0;
                                }
                            }
                            if (document.scrollingElement) {
                                document.scrollingElement.scrollLeft = 0;
                            }
                            revealEndTask(target, btn._connectorId);
                            // Don't wait for the resulting "scroll" event to re-check visibility --
                            // it fires asynchronously, and updateJumpButtons is hoisted so it's
                            // already safe to call here even though it's defined further down.
                            updateJumpButtons();
                        }
                    });
                    document.body.appendChild(btn);
                    return btn;
                }
                const jumpEndBtn = makeJumpButton("Jump to End", 16);
                const jumpStartBtn = makeJumpButton("Jump to Start", 60);

                function isElementVisible(el, container) {
                    // Vertical only, matching what the jump actually does: it scrolls to the
                    // connector's line and then resets to column 1, so a target sitting off to
                    // the right is not something the button can help with -- testing for it
                    // would leave the button showing forever on a wide diagram. A connector's
                    // run can also be taller than the container, in which case requiring it to
                    // fit entirely inside can never be satisfied even right after a successful
                    // jump; its midpoint landing inside is a better proxy for "you're there".
                    const er = el.getBoundingClientRect();
                    const cr = container.getBoundingClientRect();
                    const midY = er.top + er.height / 2;
                    return midY >= cr.top && midY <= cr.bottom;
                }

                function positionJumpButtons() {
                    const rect = outerContainer.getBoundingClientRect();
                    const viewportWidth = document.documentElement.clientWidth;
                    const rightPx = Math.max(8, viewportWidth - rect.right + 16);
                    jumpEndBtn.style.right = rightPx + "px";
                    jumpStartBtn.style.right = rightPx + "px";
                }
                positionJumpButtons();
                window.addEventListener("resize", positionJumpButtons);

                function updateJumpButtons() {
                    if (jumpEndBtn._jumpTarget && document.body.contains(jumpEndBtn._jumpTarget)
                        && !isElementVisible(jumpEndBtn._jumpTarget, outerContainer)) {
                        jumpEndBtn.style.display = "block";
                    } else {
                        jumpEndBtn.style.display = "none";
                    }
                    if (jumpStartBtn._jumpTarget && document.body.contains(jumpStartBtn._jumpTarget)
                        && !isElementVisible(jumpStartBtn._jumpTarget, outerContainer)) {
                        jumpStartBtn.style.display = "block";
                    } else {
                        jumpStartBtn.style.display = "none";
                    }
                }

                const scroller = outerContainer.querySelector(".q-scrollarea__container") || outerContainer;
                scroller.addEventListener("scroll", updateJumpButtons);

                outerContainer.addEventListener("click", (event) => {
                    const target = event.target.closest(".connector");
                    outerContainer.querySelectorAll(".connector-highlight").forEach((el) => {
                        el.classList.remove("connector-highlight");
                    });
                    outerContainer.querySelectorAll(".connector-task-box").forEach((el) => {
                        el.classList.remove("connector-task-box");
                    });
                    jumpEndBtn._jumpTarget = null;
                    jumpStartBtn._jumpTarget = null;
                    if (target) {
                        const id = target.dataset.connectorId;
                        const matches = outerContainer.querySelectorAll(`.connector[data-connector-id="${id}"]`);
                        matches.forEach((el) => {
                            el.classList.add("connector-highlight");
                        });
                        if (matches.length > 0) {
                            jumpStartBtn._jumpTarget = matches[0];
                            jumpEndBtn._jumpTarget = matches[matches.length - 1];
                            boxConnectorTasks(matches, id);
                            jumpStartBtn._connectorId = id;
                            jumpEndBtn._connectorId = id;
                        }
                    }
                    updateJumpButtons();
                });
            