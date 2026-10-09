
        const container = document.getElementById(__CONTAINER_ID__);
        if (!container || container.dataset.mtFindingClicks) return;
        container.dataset.mtFindingClicks = "1";

        const jump = (event) => {
            const row = event.target.closest('[data-mt-target]');
            if (!row) return;
            event.preventDefault();
            __RAISE_MAP_WINDOW__;
            emitEvent('mt_jump', { target: row.dataset.mtTarget });
        };
        container.addEventListener('click', jump);
        // Enter and Space, so a row reached by tabbing behaves like the control it says
        // it is.  Space would otherwise scroll the report out from under the user.
        container.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') jump(event);
        });
    