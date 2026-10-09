
            const outerContainer = document.getElementById("c__SCROLL_AREA_ID__");
            if (!outerContainer) return;
            const scroller = outerContainer.querySelector(".q-scrollarea__container") || outerContainer;
            let attempts = 0;
            const toBottom = () => {
                // Deliberately past the end: the browser clamps this to scrollHeight minus the
                // visible height, which is exactly the bottom, without having to measure either.
                scroller.scrollTop = scroller.scrollHeight;
                // Eight frames is ~130ms at 60fps -- long enough for the last chunks to render
                // and settle, short enough to still read as an instant jump.
                if (++attempts < 8) {
                    requestAnimationFrame(toBottom);
                }
            };
            toBottom();
        