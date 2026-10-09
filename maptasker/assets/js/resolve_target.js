
            function mtJumpTarget(anchor) {
                if (!anchor || !anchor.classList.contains(__ANCHOR_CLASS__)) return anchor;
                let target = anchor.nextElementSibling;
                while (target && !target.textContent.trim()) {
                    target = target.nextElementSibling;
                }
                return target || anchor.parentElement;
            }
