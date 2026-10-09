
        (() => {
            try { window.focus(); } catch (error) {}
            if (!window.name) return true;
            try {
                if (window.opener && !window.opener.closed) {
                    window.opener.open('', window.name);
                    return true;
                }
            } catch (error) {}
            try { window.open('', window.name); } catch (error) {}
            return true;
        })();
    