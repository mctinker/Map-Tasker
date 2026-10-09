
__REVEAL_ANCESTORS_JS__
        // Restore any previously-clicked match back to the standard highlight color before
        // marking the newly-clicked one, so only the match the user just jumped to stands out.
        document.querySelectorAll('.search-highlight-active').forEach(el => {
            el.classList.remove('search-highlight-active');
            el.style.backgroundColor = '#ffd941';
            el.style.color = '#000000';
        });
        const el = document.getElementById("__TARGET_ID__");
        if (el) {
            // As in the Diagram connector jump buttons: a chunk skipped by
            // content-visibility: auto was never laid out, so scrollIntoView() on a
            // descendant of it lands in the wrong place until it's forced to render.
            mtRevealAncestors(el);
            el.classList.add('search-highlight-active');
            el.style.backgroundColor = '#ff5722';
            el.style.color = '#ffffff';
            el.scrollIntoView({ behavior: 'auto', block: 'start' });
        }
    