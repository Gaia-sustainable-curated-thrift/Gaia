// Core GAIA script, loaded on every page: navbar search, the shopping bag (navbar
// badge, drawer and every add-to-bag button), toasts, the scroll-away navbar and the
// shared product-card effects. Page features live in their own files under
// static/js/products/ and plug in through Gaia.register().
(function () {
    var modules = [];
    var ready = false;

    function validateSearch(form, input) {
        input.required = true;
        input.pattern = '.*\\S.*';
        input.addEventListener('input', function () { input.setCustomValidity(''); });
        input.addEventListener('invalid', function () {
            if (!input.value.trim()) input.setCustomValidity('Enter a search term.');
        });
        form.addEventListener('submit', function (event) {
            input.value = input.value.trim();
            if (!input.value) {
                event.preventDefault();
                input.setCustomValidity('Enter a search term.');
                input.reportValidity();
            }
        });
    }

    function initHeaderSearch() {
        var display = document.querySelector('[data-search]');
        if (!display) return null;

        var url = display.getAttribute('data-search-url');
        var placeholder = display.querySelector('span');
        var text = placeholder ? placeholder.textContent : 'Search';

        var input = document.createElement('input');
        input.type = 'search';
        input.name = 'q';
        input.placeholder = text;
        input.setAttribute('aria-label', 'Search');
        input.value = new URLSearchParams(window.location.search).get('q') || '';

        var form = document.createElement('form');
        form.className = 'search-form';
        form.method = 'get';
        form.action = url;
        form.setAttribute('role', 'search');
        form.appendChild(input);

        if (placeholder) placeholder.remove();
        display.appendChild(form);
        validateSearch(form, input);
        var mobileToggle = document.querySelector('[data-mobile-search-toggle]');
        if (mobileToggle) {
            mobileToggle.addEventListener('click', function () {
                var open = display.classList.toggle('is-search-open');
                mobileToggle.setAttribute('aria-expanded', String(open));
                if (open) input.focus();
            });
            input.addEventListener('keydown', function (event) {
                if (event.key === 'Escape') {
                    display.classList.remove('is-search-open');
                    mobileToggle.setAttribute('aria-expanded', 'false');
                    mobileToggle.focus();
                }
            });
        }
        return url;
    }

    function initDrawerSearch(url) {
        var box = document.querySelector('.site-drawer-search');
        if (!box || !url) return;

        var input = box.querySelector('input');
        if (!input) return;

        var form = box.querySelector('form');
        if (!form) return;
        input.value = new URLSearchParams(window.location.search).get('q') || '';
        validateSearch(form, input);
    }

    function initBagDrawer() {
        var drawer = document.getElementById('bag-drawer');
        var toggles = document.querySelectorAll('[data-bag-toggle]');
        if (!drawer || !toggles.length) return;

        toggles.forEach(function (toggle) {
            toggle.addEventListener('click', function () {
                var sidebar = document.getElementById('site-drawer');
                if (sidebar && sidebar.open) sidebar.close();
                if (!drawer.open) drawer.showModal();
            });
        });

        drawer.addEventListener('click', function (event) {
            if (event.target === drawer) drawer.close();
        });

        if (drawer.hasAttribute('data-bag-open') && !drawer.open) {
            drawer.showModal();
        }
    }

    function dismissToast(toast, duration) {
        window.setTimeout(function () {
            toast.classList.add('is-leaving');
            window.setTimeout(function () { toast.remove(); }, 300);
        }, duration);
    }

    function initToasts() {
        document.querySelectorAll('[data-toast]').forEach(function (toast) {
            var drawer = document.getElementById('bag-drawer');
            if (drawer && drawer.open) drawer.appendChild(toast);
            var duration = parseInt(toast.getAttribute('data-toast-duration'), 10) || 4000;
            dismissToast(toast, duration);
        });
    }

    function showToast(toast) {
        document.querySelectorAll('.toast[data-toast]').forEach(function (existing) { existing.remove(); });
        if (!toast || (toast.kind !== 'added' && toast.kind !== 'error')) return;
        var el = document.createElement('div');
        el.className = 'toast toast--' + toast.kind;
        el.setAttribute('role', toast.kind === 'error' ? 'alert' : 'status');
        el.setAttribute('data-toast', '');
        el.setAttribute('data-toast-duration', '4000');

        var text = document.createElement('span');
        text.className = 'toast__text';
        text.textContent = toast.text;
        el.appendChild(text);

        if (toast.icon) {
            var icon = document.createElement('span');
            icon.className = 'toast__icon';
            var iconName = toast.icon === 'heart' ? 'heart' : 'bag';
            icon.innerHTML = '<svg class="icon" aria-hidden="true" focusable="false"><use href="#icon-' + iconName + '"></use></svg>';
            el.appendChild(icon);
        }

        // With the bag open, show the toast inside the panel above the summary so it
        // never covers the checkout button or spills outside the drawer.
        var drawer = document.getElementById('bag-drawer');
        var panel = drawer && drawer.open ? drawer.querySelector('.bag-drawer__panel') : null;
        if (panel) {
            el.classList.add('toast--in-drawer');
            panel.insertBefore(el, panel.querySelector('.bag-drawer__summary'));
        } else {
            document.body.appendChild(el);
        }
        dismissToast(el, 4000);
    }

    function prefersReducedMotion() {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    // Restart a one-shot CSS animation class (bag badge bump, icon pop).
    function replayClass(el, name) {
        if (!el || prefersReducedMotion()) return;
        el.classList.remove(name);
        void el.offsetWidth;
        el.classList.add(name);
        el.addEventListener('animationend', function done() {
            el.classList.remove(name);
            el.removeEventListener('animationend', done);
        });
    }

    // A copy of the product photo flies from where it was added into the navbar bag.
    function flyToBag(source) {
        if (!source || prefersReducedMotion() || !document.body.animate) return;
        var target = document.querySelector('.gaia-navbar .nav-bag');
        var from = source.getBoundingClientRect();
        if (!from.width || !from.height) return;
        var navbar = document.querySelector('.gaia-navbar');
        var navHidden = navbar && navbar.classList.contains('is-nav-scrolled') && !navbar.classList.contains('is-nav-revealed');
        var to = target && !navHidden ? target.getBoundingClientRect() : { left: window.innerWidth - 56, top: 16, width: 40, height: 40 };
        var size = Math.min(from.width, from.height, 160);
        var ghost = source.cloneNode(false);
        ghost.removeAttribute('style');
        ghost.removeAttribute('loading');
        ghost.className = 'fly-to-bag';
        ghost.setAttribute('aria-hidden', 'true');
        ghost.style.left = (from.left + (from.width - size) / 2) + 'px';
        ghost.style.top = (from.top + (from.height - size) / 2) + 'px';
        ghost.style.width = size + 'px';
        ghost.style.height = size + 'px';
        document.body.appendChild(ghost);
        var dx = to.left + to.width / 2 - (from.left + from.width / 2);
        var dy = to.top + to.height / 2 - (from.top + from.height / 2);
        var flight = ghost.animate([
            { transform: 'translate(0, 0) scale(1)', opacity: 1 },
            { transform: 'translate(' + dx * 0.55 + 'px, ' + (dy * 0.35 - 60) + 'px) scale(0.55)', opacity: 1, offset: 0.55 },
            { transform: 'translate(' + dx + 'px, ' + dy + 'px) scale(0.12)', opacity: 0.2 }
        ], { duration: 720, easing: 'cubic-bezier(0.5, 0, 0.2, 1)' });
        flight.onfinish = flight.oncancel = function () { ghost.remove(); };
        // Backup cleanup in case the finish event never fires (e.g. a background tab).
        window.setTimeout(function () { ghost.remove(); }, 1000);
    }

    // Every add-to-bag button on the page mirrors whether its listing is in the bag;
    // pressing an added one removes it again.
    function setBagButton(form, inBag) {
        var button = form.querySelector('button[type="submit"]');
        var label = form.querySelector('[data-bag-label]');
        var changed = button && button.classList.contains('is-active') !== inBag;
        form.action = form.getAttribute(inBag ? 'data-remove-url' : 'data-add-url');
        if (changed) replayClass(button, 'is-popping');
        if (button) {
            button.classList.toggle('is-active', inBag);
            button.setAttribute('aria-pressed', inBag ? 'true' : 'false');
            var icon = button.querySelector('use');
            if (icon) icon.setAttribute('href', inBag ? '#icon-check' : '#icon-bag');
        }
        if (label) label.textContent = inBag ? 'Added to bag' : 'Add to bag';
    }

    function syncBagButtons(slugs) {
        document.querySelectorAll('[data-bag-form]').forEach(function (form) {
            setBagButton(form, slugs.indexOf(form.getAttribute('data-bag-form')) !== -1);
        });
    }

    function bagFormsFor(slug) {
        return Array.prototype.filter.call(document.querySelectorAll('[data-bag-form]'), function (form) {
            return form.getAttribute('data-bag-form') === slug;
        });
    }

    function setBagCount(count) {
        document.querySelectorAll('[data-bag-count]').forEach(function (badge) {
            var changed = badge.textContent.trim() !== String(count);
            badge.textContent = count;
            badge.hidden = count === 0;
            if (changed && !badge.hidden) replayClass(badge, 'is-bumping');
        });
        document.querySelectorAll('[data-bag-toggle]').forEach(function (toggle) {
            toggle.setAttribute('aria-label', 'Shopping bag, ' + count + ' item' + (count === 1 ? '' : 's'));
        });
    }

    function currentBagCount() {
        var badge = document.querySelector('[data-bag-count]');
        var count = badge ? parseInt(badge.textContent, 10) : 0;
        return isNaN(count) ? 0 : count;
    }

    function initBagForms() {
        var requestPending = false;
        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.matches('form[action]') || !/\/bag\/(add|remove|set|undo)\//.test(new URL(form.action).pathname)) return;
            if (typeof window.fetch !== 'function') return;

            event.preventDefault();
            if (requestPending) return;
            requestPending = true;
            form.setAttribute('aria-busy', 'true');
            var button = form.querySelector('button[type="submit"]');
            if (button) button.disabled = true;
            var drawer = document.getElementById('bag-drawer');
            var url = form.action;
            var body = new FormData(form);
            var adding = /\/bag\/add\//.test(new URL(url).pathname);
            var card = form.closest('.product-card');
            var photo = card ? card.querySelector('.product-card__media img') : document.querySelector('[data-gallery-main]');

            // Optimistic UI: an add/remove toggle flips (and the badge moves) straight
            // away; the server's answer then confirms it, or the change is rolled back.
            var slug = form.getAttribute('data-bag-form');
            var revert = null;
            if (slug) {
                var previousCount = currentBagCount();
                bagFormsFor(slug).forEach(function (other) { setBagButton(other, adding); });
                setBagCount(Math.max(0, previousCount + (adding ? 1 : -1)));
                if (adding) flyToBag(photo);
                revert = function () {
                    bagFormsFor(slug).forEach(function (other) { setBagButton(other, !adding); });
                    setBagCount(previousCount);
                };
            }

            fetch(url, {
                method: 'POST',
                body: body,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function (response) {
                return response.json();
            }).then(function (data) {
                // Rate-limited (429) responses carry only a toast explaining why.
                if (data && data.ok === false && data.toast && typeof data.bag_count !== 'number') {
                    if (revert) revert();
                    showToast(data.toast);
                    return;
                }
                if (!data || typeof data.bag_count !== 'number' || typeof data.ok !== 'boolean') {
                    throw new Error('Invalid bag response');
                }
                var panel = document.querySelector('.bag-drawer__panel');
                if (panel && data.drawer) panel.innerHTML = data.drawer;
                setBagCount(data.bag_count);
                if (Array.isArray(data.bag_slugs)) syncBagButtons(data.bag_slugs);
                if (data.open && drawer && !drawer.open) drawer.showModal();
                showToast(data.toast);
            }).catch(function () {
                // A failed response may follow a successful POST; do not replay it.
                if (revert) revert();
                showToast({ kind: 'error', text: 'Could not update your bag. Please try again.' });
            }).finally(function () {
                requestPending = false;
                form.removeAttribute('aria-busy');
                if (button) button.disabled = false;
            });
        });
    }

    // Show a shimmer behind product photos until they have loaded.
    function initPhotoShimmer(root) {
        (root || document).querySelectorAll('.product-card__media img, .pdp-main-image img').forEach(function (img) {
            if (img.complete) return;
            var frame = img.parentElement;
            frame.classList.add('is-loading');
            function done() { frame.classList.remove('is-loading'); }
            img.addEventListener('load', done, { once: true });
            img.addEventListener('error', done, { once: true });
        });
    }

    // Product cards fade up the first time they enter the viewport. Cards already on
    // screen at load are left alone so nothing above the fold flickers.
    function initCardReveal() {
        if (!('IntersectionObserver' in window) || prefersReducedMotion()) return;
        var cards = document.querySelectorAll('.product-card');
        if (!cards.length) return;
        var observer = new IntersectionObserver(function (entries) {
            var index = 0;
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.style.setProperty('--reveal-delay', Math.min(index++, 4) * 60 + 'ms');
                entry.target.classList.add('is-revealed');
                observer.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -8% 0px' });
        cards.forEach(function (card) {
            var box = card.getBoundingClientRect();
            if (card.hidden || box.top < window.innerHeight) return;
            card.setAttribute('data-reveal', '');
            observer.observe(card);
        });
    }

    function initScrollNavbar() {
        var navbar = document.querySelector('.gaia-navbar');
        if (!navbar) return;

        var revealDelay = 180;
        var leaveDelay = 120;
        var revealTimer;
        var hideTimer;
        var overNavbar = false;
        var overEdge = false;
        var scrolled = false;
        var framePending = false;
        var lastScrollY = window.scrollY;
        var threshold;

        // An invisible strip along the top of the screen brings the navbar back on hover.
        var edge = document.createElement('button');
        edge.type = 'button';
        edge.className = 'nav-reveal-edge';
        edge.setAttribute('aria-label', 'Show navigation');
        edge.setAttribute('aria-expanded', 'false');
        if (!navbar.id) navbar.id = 'site-navbar';
        edge.setAttribute('aria-controls', navbar.id);
        edge.hidden = true;
        document.body.appendChild(edge);
        navbar.setAttribute('data-scroll-nav', '');

        function reveal() {
            window.clearTimeout(hideTimer);
            if (!scrolled) return;
            navbar.classList.add('is-nav-revealed');
            edge.setAttribute('aria-expanded', 'true');
        }

        function hide() {
            if (overNavbar || overEdge || navbar.contains(document.activeElement) || document.activeElement === edge) return;
            navbar.classList.remove('is-nav-revealed');
            edge.setAttribute('aria-expanded', 'false');
        }

        function hideWhenOutside() {
            window.clearTimeout(hideTimer);
            hideTimer = window.setTimeout(hide, leaveDelay);
        }

        function measure() {
            threshold = navbar.offsetHeight + parseFloat(window.getComputedStyle(navbar).marginTop || 0);
        }

        function update() {
            framePending = false;
            var y = window.scrollY;
            var delta = y - lastScrollY;
            lastScrollY = y;
            var next = y > threshold;
            if (next !== scrolled) {
                scrolled = next;
                window.clearTimeout(revealTimer);
                window.clearTimeout(hideTimer);
                navbar.classList.toggle('is-nav-scrolled', scrolled);
                navbar.classList.remove('is-nav-revealed');
                edge.hidden = !scrolled;
                edge.setAttribute('aria-expanded', 'false');
                if (scrolled && (overNavbar || navbar.contains(document.activeElement))) reveal();
                return;
            }
            // Scrolling back up brings the navbar back, which is the only way on touch screens.
            if (scrolled && delta < -8) reveal();
            else if (scrolled && delta > 8) hide();
        }

        edge.addEventListener('pointerenter', function (event) {
            if (event.pointerType === 'touch') return;
            overEdge = true;
            window.clearTimeout(hideTimer);
            window.clearTimeout(revealTimer);
            revealTimer = window.setTimeout(reveal, revealDelay);
        });
        edge.addEventListener('pointerleave', function () {
            overEdge = false;
            window.clearTimeout(revealTimer);
            hideWhenOutside();
        });
        edge.addEventListener('click', reveal);
        edge.addEventListener('focus', reveal);
        navbar.addEventListener('pointerenter', function (event) {
            if (event.pointerType === 'touch') return;
            overNavbar = true;
            window.clearTimeout(hideTimer);
        });
        navbar.addEventListener('pointerleave', function () {
            overNavbar = false;
            hideWhenOutside();
        });
        navbar.addEventListener('focusin', reveal);
        navbar.addEventListener('focusout', hideWhenOutside);
        edge.addEventListener('blur', hideWhenOutside);
        document.addEventListener('pointerdown', function (event) {
            if (!navbar.contains(event.target) && event.target !== edge) {
                if (document.activeElement === edge) edge.blur();
                hideWhenOutside();
            }
        });
        window.addEventListener('scroll', function () {
            if (!framePending) {
                framePending = true;
                window.requestAnimationFrame(update);
            }
        }, { passive: true });
        window.addEventListener('resize', function () { measure(); update(); });
        if (window.ResizeObserver) new ResizeObserver(function () { measure(); update(); }).observe(navbar);
        measure();
        update();
    }

    // Shared helpers and the hook page modules use to run once the DOM is ready.
    window.Gaia = {
        // Deferred page scripts may load after the core has already started, so a
        // module registered late runs straight away.
        register: function (init) {
            if (ready) init();
            else modules.push(init);
        },
        prefersReducedMotion: prefersReducedMotion,
        replayClass: replayClass,
        showToast: showToast
    };

    function init() {
        initBagDrawer();
        initBagForms();
        initToasts();
        initDrawerSearch(initHeaderSearch());
        initScrollNavbar();
        initCardReveal();
        initPhotoShimmer();
        // HTMX swaps in new search results; their photos need the loading shimmer too.
        document.body.addEventListener('htmx:afterSettle', function () { initPhotoShimmer(); });
        ready = true;
        modules.forEach(function (run) { run(); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
