
        (() => {
            const MAP_WINDOW_PREFIX = __MAP_PREFIX__;

            // The Map window, raised from inside the click that asked for it.
            //
            // Which request actually raises a background TAB was measured in Chrome rather
            // than reasoned about, because the reasoning was wrong twice.  Of everything
            // that looks like it should work, one thing does:
            //
            //   other.focus()          ignored.  A tab cannot be focused by whoever happens
            //                          to hold a handle to it -- that is tab-jacking, and it
            //                          is refused even for a window this one opened.  Asked
            //                          anyway, and asked first, because a view opened as a
            //                          real popup WINDOW rather than a tab is raised by it.
            //   owner.open("", name)   ignored.  Asking the Map's own opener to raise it
            //                          looks like the privileged request and is not one: the
            //                          activation belongs to the window the click happened
            //                          in and does not travel into another window's open().
            //                          It still hands back a live window, so it reads as
            //                          success and swallows anything tried after it.
            //   window.open("", name)  RAISES IT.  The activation is here, the name is
            //                          looked up across the whole family of windows this one
            //                          belongs to, and the empty URL means the Map is brought
            //                          forward without being reloaded -- so it keeps its
            //                          scroll position, and the jump already on its way lands
            //                          in a page that is still the one that was scrolled.
            //
            // So the one that works is asked from here first, and the opener is left as a
            // last resort for a browser that refuses it (open() returns null when a popup is
            // blocked).  None of the three is required to work: the jump itself has already
            // been sent, and a browser that will not raise a window is not a failure to
            // report.
            function raiseWindow(owner, other) {
                let name = "";
                try {
                    name = other.name || "";
                } catch (error) {
                    name = "";
                }
                try {
                    other.focus();
                } catch (error) {}
                if (!name) return true;
                for (const asker of [window, owner]) {
                    try {
                        if (!asker || asker.closed) continue;
                        const raised = asker.open("", name);
                        if (raised) {
                            try {
                                raised.focus();
                            } catch (error) {}
                            return true;
                        }
                    } catch (error) {}
                }
                return true;
            }

            // Only a window that already exists is raised, and it is found by HANDLE rather
            // than by name: a name nothing has claimed would conjure a blank window, and with
            // "Open View In New Window" on the Map's name carries a timestamp nothing here
            // could predict anyway.  The name that raises it is then read back off the handle
            // -- a name that is known to exist, because a live window has it.
            //
            // TWO lists, because which window holds the Map's handle depends on who asked for
            // it.  _open_popout_window registers the new window on whichever client was
            // active when it ran: the main window when the Map button was pressed there, but
            // the view itself when a jump from that view had to build the Map -- go_to_target
            // runs inside the clicked view's slot, so rebuild_map_for_jump's window.open() is
            // that view's.  Own list first, and each list newest first, which is the Map
            // jump_map_view tries first (see its note on several Maps being open at once).
            //
            // When there is no Map open anywhere this does nothing, and the rebuild that
            // follows opens one and raises it on its own.
            for (const source of [window, window.opener]) {
                try {
                    if (!source || source.closed) continue;
                    const popouts = source.mapTaskerPopouts || [];
                    for (let index = popouts.length - 1; index >= 0; index -= 1) {
                        const other = popouts[index];
                        if (other && !other.closed && other !== window
                            && (other.name || "").startsWith(MAP_WINDOW_PREFIX)) {
                            return raiseWindow(source, other);
                        }
                    }
                } catch (error) {
                    // A window that has gone away, or one the browser will not let us touch.
                    // The jump itself is unaffected, so there is nothing to report.
                }
            }
            return false;
        })()
