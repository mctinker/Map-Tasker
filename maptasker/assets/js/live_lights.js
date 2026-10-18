        return (() => {
            // Given a container, only that one; given none, the whole page -- which is what the monitor
            // asks, so that every window holding an interactive Diagram answers for itself.
            const containerId = __CONTAINER_ID__;
            const container = containerId ? document.getElementById(containerId) : document;
            if (!container) return {nodes: 0, lit: 0};
            // One style element for the page, added the first time: the lights are drawn with a background and
            // a glow, which add nothing to the width of the text, so no column of the diagram moves.
            if (!document.getElementById('mt-live-style')) {
                const style = document.createElement('style');
                style.id = 'mt-live-style';
                style.textContent =
                    '.mt-live-on { background: #2e7d32 !important; color: #fff !important; border-radius: 2px;' +
                    ' box-shadow: 0 0 6px 2px rgba(76, 175, 80, 0.9); }' +
                    '.mt-live-recent { background: rgba(255, 193, 7, 0.45) !important; border-radius: 2px; }';
                document.head.appendChild(style);
            }
            container.querySelectorAll('.mt-live-on, .mt-live-recent').forEach(
                (element) => element.classList.remove('mt-live-on', 'mt-live-recent'),
            );
            const lit = __LIT__;
            let lit_count = 0;
            for (const anchor of Object.keys(lit)) {
                // Every copy: a Task a Profile runs is drawn once under each Profile that runs it.
                const found = container.querySelectorAll('[data-anchor="' + CSS.escape(anchor) + '"]');
                found.forEach((element) => element.classList.add(lit[anchor] === 'on' ? 'mt-live-on' : 'mt-live-recent'));
                if (found.length) lit_count += 1;
            }
            // Scroll to what has just started, so the one that fired is the one on screen: the first of these
            // that this page's Diagram draws, centred.  Nothing scrolls sideways more than it has to.
            for (const anchor of __FOLLOW__) {
                const element = container.querySelector('[data-anchor="' + CSS.escape(anchor) + '"]');
                if (element) {
                    element.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'smooth'});
                    break;
                }
            }
            // How many named objects this page's Diagram has at all, so "no Diagram here" and "a Diagram without
            // these" can be told apart.
            return {nodes: container.querySelectorAll('[data-anchor]').length, lit: lit_count};
        })();
