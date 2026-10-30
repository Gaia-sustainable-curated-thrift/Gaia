// Wishlist button on the detail page, with optimistic updates and a heart burst.
(function (Gaia) {
    var prefersReducedMotion = Gaia.prefersReducedMotion;
    var replayClass = Gaia.replayClass;
    var showToast = Gaia.showToast;

    // A handful of tiny hearts burst out of the wishlist button when an item is saved.
    function heartBurst(button) {
        if (!button || prefersReducedMotion() || !document.body.animate) return;
        var box = button.querySelector('.icon') || button;
        var rect = box.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        for (var i = 0; i < 8; i++) {
            var heart = document.createElement('span');
            heart.className = 'heart-burst';
            heart.setAttribute('aria-hidden', 'true');
            heart.innerHTML = '<svg class="icon" focusable="false"><use href="#icon-heart"></use></svg>';
            heart.style.left = cx + 'px';
            heart.style.top = cy + 'px';
            document.body.appendChild(heart);
            var angle = (Math.PI * 2 * i) / 8 + (Math.random() - 0.5) * 0.4;
            var distance = 34 + Math.random() * 22;
            var spin = (Math.random() - 0.5) * 60;
            var burst = heart.animate([
                { transform: 'translate(-50%, -50%) scale(0.3)', opacity: 1 },
                { transform: 'translate(calc(-50% + ' + Math.cos(angle) * distance + 'px), calc(-50% + ' + Math.sin(angle) * distance + 'px)) scale(1) rotate(' + spin + 'deg)', opacity: 0 }
            ], { duration: 620 + Math.random() * 160, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
            burst.onfinish = burst.oncancel = (function (node) { return function () { node.remove(); }; })(heart);
            window.setTimeout((function (node) { return function () { node.remove(); }; })(heart), 1000);
        }
    }

    function initWishlistForms() {
        document.querySelectorAll('[data-wishlist-form]').forEach(function (form) {
            var button = form.querySelector('button[type="submit"]');
            var label = button.querySelector('[data-wishlist-label]');
            var counters = document.querySelectorAll('[data-wishlist-count]');
            var saved = button.classList.contains('is-saved');
            var pending = false;
            var navigating = false;

            function savedCount() {
                var count = counters.length ? parseInt(counters[0].textContent, 10) : NaN;
                return isNaN(count) ? null : count;
            }

            function render(state, count) {
                button.classList.toggle('is-saved', state);
                button.setAttribute('aria-pressed', state ? 'true' : 'false');
                // Same pressed look as the bag button: outline plus a check mark.
                var icon = button.querySelector('use');
                if (icon) icon.setAttribute('href', state ? '#icon-check' : '#icon-heart');
                label.textContent = state ? 'Saved to wishlist' : 'Save to wishlist';
                form.action = form.getAttribute(state ? 'data-remove-url' : 'data-add-url');
                if (typeof count !== 'number') return;
                counters.forEach(function (node) {
                    node.textContent = count + (count === 1 ? ' person has saved this' : ' people have saved this');
                });
            }

            form.addEventListener('submit', function (event) {
                if (typeof window.fetch !== 'function') return;
                event.preventDefault();
                if (pending) return;
                pending = true;
                form.setAttribute('aria-busy', 'true');

                var url = form.action;
                var body = new FormData(form);
                var before = saved;
                var beforeCount = savedCount();
                // Optimistic UI: show the new state right away, confirm or roll back after.
                var next = !saved;
                render(next, beforeCount === null ? undefined : Math.max(0, beforeCount + (next ? 1 : -1)));
                replayClass(button, 'is-popping');
                if (next) heartBurst(button);

                function rollBack(toast) {
                    render(before, beforeCount === null ? undefined : beforeCount);
                    showToast(toast);
                }

                fetch(url, {
                    method: 'POST',
                    body: body,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin'
                }).then(function (response) {
                    if (response.status === 403 || response.status === 404) {
                        rollBack({ kind: 'error', text: response.status === 403
                            ? 'Your session is no longer valid. Reload this page before trying again.'
                            : 'This listing could not be found.' });
                        return null;
                    }
                    return response.json();
                }).then(function (data) {
                    if (!data) return;
                    if (typeof data.login_url === 'string') {
                        var target = new URL(data.login_url, window.location.href);
                        if (target.origin !== window.location.origin) throw new Error('Unexpected login redirect');
                        navigating = true;
                        window.location.assign(target.href);
                    } else if (data.ok === true && data.toast && typeof data.saved_count === 'number' && typeof data.saved === 'boolean') {
                        saved = data.saved;
                        render(saved, data.saved_count);
                        showToast(data.toast);
                    } else if (data.ok === false && data.toast) {
                        rollBack(data.toast);
                    } else {
                        throw new Error('Invalid wishlist response');
                    }
                }).catch(function () {
                    rollBack({ kind: 'error', text: 'Could not update your wishlist. Please try again.' });
                }).finally(function () {
                    if (!navigating) {
                        pending = false;
                        form.removeAttribute('aria-busy');
                    }
                });
            });
        });
    }

    Gaia.register(function () {
        initWishlistForms();
    });
})(window.Gaia);
