
        return (() => {
__REVEAL_ANCESTORS_JS__
__RESOLVE_TARGET_JS__
            const anchor = document.getElementById(__ANCHOR_ID__);
            if (!anchor) return false;
            mtRevealAncestors(anchor);

            // With the "twisty" option on, a Task's line and everything under it sit inside
            // a collapsed <details> (see twisty.add_twisty).  Scrolling to something the
            // browser is not displaying does nothing at all, so open every one of them on
            // the way down first -- the user asked to be taken here.
            for (let box = anchor.closest('details'); box; box = box.parentElement?.closest('details')) {
                box.open = true;
            }

            // An empty marker highlights what follows it; anything else (a variable's own
            // table row) IS the target.  Highlighting a line break draws an outline around
            // nothing, which reads as the jump having failed -- see mtJumpTarget.
            const target = mtJumpTarget(anchor);
            if (!target) return false;

            document.querySelectorAll('.__HIGHLIGHT_CLASS__').forEach(
                (element) => element.classList.remove('__HIGHLIGHT_CLASS__'),
            );
            mtRevealAncestors(target);
            target.classList.add('__HIGHLIGHT_CLASS__');
            // Instant, not smooth -- the same choice the Diagram's jumps make, and for one
            // more reason besides theirs.
            //
            // Theirs: a jump crosses tens of thousands of pixels on a large output, where an
            // animated scroll is slow to land and distracting rather than helpful.
            //
            // And: a smooth scroll is an animation, and an animation does not run on a page
            // the browser is not displaying.  This jump is delivered the moment the Map has
            // finished streaming in, which is precisely when its window may not be the one in
            // front -- a popout the browser opened behind, or one the user has clicked away
            // from while it built.  The animation then never starts, never recovers, and
            // leaves a Map sitting at the top with the object highlighted 40,000 pixels down
            // where nobody will see it.  Setting the position outright works either way.
            target.scrollIntoView({ behavior: 'auto', block: 'center' });
            return true;
        })();
    