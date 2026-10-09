
        (() => {
            const seen = new Set();

            const sweep = (holder) => {
                let popouts;
                try {
                    if (!holder || holder.closed) return;
                    popouts = holder.mapTaskerPopouts || [];
                } catch (error) {
                    return;  // A window gone, or one this page is not allowed to touch.
                }
                for (const other of popouts) {
                    try {
                        if (!other || other === window || seen.has(other)) continue;
                        seen.add(other);
                        sweep(other);   // Whatever IT opened, while it is still open to ask.
                        if (!other.closed) other.close();
                    } catch (error) {}
                }
                try { holder.mapTaskerPopouts = []; } catch (error) {}
            };

            sweep(window);
            try { sweep(window.opener); } catch (error) {}__TAIL__
            return true;
        })();
    