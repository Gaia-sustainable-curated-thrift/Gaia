(function () {
    function moveTabIndicator(tabs, item) {
        if (!item || !tabs.hasAttribute('data-animated-tabs')) return;
        var track = tabs.getBoundingClientRect();
        var bounds = item.getBoundingClientRect();
        tabs.style.setProperty('--tab-left', (bounds.left - track.left) + 'px');
        tabs.style.setProperty('--tab-top', (bounds.top - track.top) + 'px');
        tabs.style.setProperty('--tab-width', bounds.width + 'px');
        tabs.style.setProperty('--tab-height', bounds.height + 'px');
    }

    function initAnimatedTabs() {
        document.querySelectorAll('[data-category-tabs], [data-listing-tabs]').forEach(function (tabs) {
            tabs.setAttribute('data-animated-tabs', '');
            function measure() { moveTabIndicator(tabs, tabs.querySelector('.is-active')); }
            measure();
            // Enable the slide only after the first placement so the pill doesn't fly in on load.
            window.requestAnimationFrame(function () {
                window.requestAnimationFrame(function () { tabs.setAttribute('data-tabs-ready', ''); });
            });
            if (window.ResizeObserver) new ResizeObserver(measure).observe(tabs);
            else window.addEventListener('resize', measure);
            if (document.fonts) document.fonts.ready.then(measure);
        });
    }

    var tabContentAnimations = new WeakMap();
    function animateTabContent(nodes) {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        nodes.forEach(function (node) {
            var previous = tabContentAnimations.get(node);
            if (previous) previous.cancel();
            if (node.hidden || !node.animate) return;
            tabContentAnimations.set(node, node.animate([
                { opacity: 0, transform: 'translateY(6px)' },
                { opacity: 1, transform: 'translateY(0)' }
            ], { duration: 220, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }));
        });
    }

    function activateItem(tabs, item) {
        tabs.querySelectorAll('.segment__item').forEach(function (tab) {
            var isActive = tab === item;
            tab.classList.toggle('is-active', isActive);
            if (isActive) {
                tab.setAttribute('aria-current', 'true');
            } else {
                tab.removeAttribute('aria-current');
            }
        });
        moveTabIndicator(tabs, item);
    }

    function initCategoryTabs() {
        var tabs = document.querySelector('[data-category-tabs]');
        if (!tabs) return;
        var groups = document.querySelectorAll('[data-category-group]');

        tabs.addEventListener('click', function (event) {
            var item = event.target.closest('.segment__item');
            if (!item || !tabs.contains(item)) return;
            event.preventDefault();
            if (item.classList.contains('is-active')) return;

            activateItem(tabs, item);
            var slug = item.getAttribute('data-gender');
            groups.forEach(function (group) {
                group.hidden = group.getAttribute('data-gender') !== slug;
            });
            animateTabContent(groups);
        });
    }

    function initListingTabs() {
        var tabs = document.querySelector('[data-listing-tabs]');
        if (!tabs) return;
        var cards = document.querySelectorAll('.product-card[data-category]');
        var empty = document.querySelector('[data-listing-empty]');

        tabs.addEventListener('click', function (event) {
            var item = event.target.closest('.segment__item');
            if (!item || !tabs.contains(item)) return;
            event.preventDefault();
            if (item.classList.contains('is-active')) return;

            activateItem(tabs, item);
            var name = item.getAttribute('data-category-name');
            cards.forEach(function (card) {
                card.hidden = card.getAttribute('data-category') !== name;
            });
            if (empty) {
                empty.hidden = Array.prototype.some.call(cards, function (card) { return !card.hidden; });
            }
            animateTabContent(Array.prototype.slice.call(cards).concat(empty ? [empty] : []));
        });
    }

    function initFilterToggle() {
        var toggle = document.querySelector('[data-filter-toggle]');
        var body = document.querySelector('[data-filter-body]');
        if (!toggle || !body) return;

        toggle.addEventListener('click', function () {
            var collapsed = body.toggleAttribute('hidden');
            toggle.setAttribute('aria-expanded', String(!collapsed));
            if (!collapsed && body.animate && !prefersReducedMotion()) {
                body.animate([{ opacity: 0, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'none' }],
                    { duration: 220, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
            }
        });
    }

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

    function initGallery() {
        var gallery = document.querySelector('[data-gallery]');
        if (!gallery) return;
        var main = gallery.querySelector('[data-gallery-main]');
        var thumbs = gallery.querySelectorAll('[data-gallery-thumb]');
        if (!main || !thumbs.length) return;

        thumbs.forEach(function (thumb) {
            thumb.addEventListener('click', function () {
                thumbs.forEach(function (other) {
                    other.classList.toggle('is-active', other === thumb);
                });
                var full = thumb.getAttribute('data-full');
                if (!full || main.getAttribute('src') === full) return;
                main.src = full;
                if (main.animate && !prefersReducedMotion()) {
                    main.animate([{ opacity: 0.35, transform: 'scale(1.02)' }, { opacity: 1, transform: 'scale(1)' }],
                        { duration: 260, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' });
                }
            });
        });
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

    // Every add-to-bag button on the page mirrors whether its listing is in the bag;
    // pressing an added one removes it again.
    function syncBagButtons(slugs) {
        document.querySelectorAll('[data-bag-form]').forEach(function (form) {
            var inBag = slugs.indexOf(form.getAttribute('data-bag-form')) !== -1;
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
        });
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
            var adding = /\/bag\/add\//.test(new URL(form.action).pathname);
            var card = form.closest('.product-card');
            var photo = card ? card.querySelector('.product-card__media img') : document.querySelector('[data-gallery-main]');

            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function (response) {
                return response.json();
            }).then(function (data) {
                if (!data || typeof data.bag_count !== 'number' || typeof data.ok !== 'boolean') {
                    throw new Error('Invalid bag response');
                }
                var panel = document.querySelector('.bag-drawer__panel');
                if (panel && data.drawer) panel.innerHTML = data.drawer;
                document.querySelectorAll('[data-bag-count]').forEach(function (badge) {
                    var changed = badge.textContent.trim() !== String(data.bag_count);
                    badge.textContent = data.bag_count;
                    badge.hidden = data.bag_count === 0;
                    if (changed && !badge.hidden) replayClass(badge, 'is-bumping');
                });
                document.querySelectorAll('[data-bag-toggle]').forEach(function (toggle) {
                    toggle.setAttribute('aria-label', 'Shopping bag, ' + data.bag_count + ' item' + (data.bag_count === 1 ? '' : 's'));
                });
                if (Array.isArray(data.bag_slugs)) syncBagButtons(data.bag_slugs);
                if (adding && data.ok && !data.open) flyToBag(photo);
                if (data.open && drawer && !drawer.open) drawer.showModal();
                showToast(data.toast);
            }).catch(function () {
                // A failed response may follow a successful POST; do not replay it.
                showToast({ kind: 'error', text: 'Could not update your bag. Please try again.' });
            }).finally(function () {
                requestPending = false;
                form.removeAttribute('aria-busy');
                if (button) button.disabled = false;
            });
        });
    }

    function initWishlistForms() {
        document.querySelectorAll('[data-wishlist-form]').forEach(function (form) {
            var button = form.querySelector('button[type="submit"]');
            var label = button.querySelector('[data-wishlist-label]');
            var saved = button.classList.contains('is-saved');
            var pending = false;
            var navigating = false;

            form.addEventListener('submit', function (event) {
                if (typeof window.fetch !== 'function') return;
                event.preventDefault();
                if (pending) return;
                pending = true;
                button.disabled = true;
                label.textContent = saved ? 'Menghapus…' : 'Menyimpan…';
                form.setAttribute('aria-busy', 'true');

                fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin'
                }).then(function (response) {
                    if (response.status === 403 || response.status === 404) {
                        showToast({ kind: 'error', text: response.status === 403
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
                        if (saved !== data.saved) replayClass(button, 'is-popping');
                        if (!saved && data.saved) heartBurst(button);
                        saved = data.saved;
                        button.classList.toggle('is-saved', saved);
                        button.setAttribute('aria-pressed', saved ? 'true' : 'false');
                        // Same pressed look as the bag button: outline plus a check mark.
                        var icon = button.querySelector('use');
                        if (icon) icon.setAttribute('href', saved ? '#icon-check' : '#icon-heart');
                        form.action = form.getAttribute(saved ? 'data-remove-url' : 'data-add-url');
                        document.querySelectorAll('[data-wishlist-count]').forEach(function (count) {
                            count.textContent = data.saved_count + (data.saved_count === 1
                                ? ' person has saved this' : ' people have saved this');
                        });
                        showToast(data.toast);
                    } else {
                        throw new Error('Invalid wishlist response');
                    }
                }).catch(function () {
                    showToast({ kind: 'error', text: 'Could not update your wishlist. Please try again.' });
                }).finally(function () {
                    if (!navigating) {
                        pending = false;
                        button.disabled = false;
                        label.textContent = saved ? 'Saved to wishlist' : 'Save to wishlist';
                        form.removeAttribute('aria-busy');
                    }
                });
            });
        });
    }

    function initSellForm() {
        var form = document.querySelector('[data-sell-form]');
        if (!form) return;

        var photos = form.querySelector('[data-photos]');
        var addTile = form.querySelector('[data-photo-add]');
        var input = form.querySelector('[data-photo-input]');
        if (photos && addTile && input) {
            var MAX_PHOTOS = 5;
            var existingCount = photos.querySelectorAll('[data-existing-photo]').length;
            var chosen = [];

            var syncInput = function () {
                var dt = new DataTransfer();
                chosen.forEach(function (file) { dt.items.add(file); });
                input.files = dt.files;
            };

            var render = function () {
                photos.querySelectorAll('.sell-photo:not([data-existing-photo])').forEach(function (node) { node.remove(); });
                chosen.forEach(function (file, index) {
                    var tile = document.createElement('div');
                    tile.className = 'sell-photo';

                    var img = document.createElement('img');
                    img.alt = '';
                    var reader = new FileReader();
                    reader.onload = function (e) { img.src = e.target.result; };
                    reader.readAsDataURL(file);

                    var remove = document.createElement('button');
                    remove.type = 'button';
                    remove.className = 'sell-photo__remove';
                    remove.setAttribute('aria-label', 'Remove photo');
                    remove.innerHTML = '<svg class="icon" aria-hidden="true" focusable="false"><use href="#icon-trash"></use></svg>';
                    remove.addEventListener('click', function () {
                        chosen.splice(index, 1);
                        syncInput();
                        render();
                    });

                    tile.appendChild(img);
                    tile.appendChild(remove);

                    if (index === 0 && existingCount === 0) {
                        var cover = document.createElement('span');
                        cover.className = 'sell-photo__cover';
                        cover.textContent = 'Cover';
                        tile.appendChild(cover);
                    }
                    photos.insertBefore(tile, addTile);
                });
                var full = chosen.length + existingCount >= MAX_PHOTOS;
                addTile.hidden = full;
                addTile.style.display = full ? 'none' : '';
            };

            input.addEventListener('change', function () {
                Array.prototype.forEach.call(input.files, function (file) {
                    if (chosen.length + existingCount < MAX_PHOTOS) chosen.push(file);
                });
                syncInput();
                render();
            });

            render();
        }

        var dropdown = form.querySelector('[data-sell-dropdown]');
        if (dropdown) {
            var toggle = dropdown.querySelector('[data-sell-toggle]');
            var menu = dropdown.querySelector('[data-sell-menu]');
            var display = dropdown.querySelector('[data-sell-display]');
            var valueInput = dropdown.querySelector('[data-sell-value]');
            var parentInput = dropdown.querySelector('[data-sell-parent]');

            function closeMenu() {
                menu.hidden = true;
                toggle.setAttribute('aria-expanded', 'false');
            }

            toggle.addEventListener('click', function (event) {
                event.stopPropagation();
                var open = menu.hidden;
                menu.hidden = !open;
                toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });

            dropdown.querySelectorAll('[data-sell-option]').forEach(function (option) {
                option.addEventListener('click', function () {
                    dropdown.querySelectorAll('.is-active').forEach(function (el) { el.classList.remove('is-active'); });
                    option.classList.add('is-active');
                    display.textContent = option.getAttribute('data-label');
                    valueInput.value = option.getAttribute('data-value');
                    parentInput.value = option.getAttribute('data-parent');
                    toggle.classList.add('is-set');
                    closeMenu();
                });
            });

            document.addEventListener('click', function (event) {
                if (!dropdown.contains(event.target)) closeMenu();
            });
        }

        var price = form.querySelector('[data-price-input]');
        if (price) {
            var formatPrice = function () {
                var digits = price.value.replace(/\D/g, '');
                price.value = digits ? Number(digits).toLocaleString('id-ID') : '';
            };
            price.addEventListener('input', formatPrice);
            formatPrice();
        }
    }

    function initListingSubmit() {
        var form = document.querySelector('[data-sell-form]');
        if (!form) return;
        var errors = document.querySelector('[data-listing-errors]');
        var status = form.querySelector('[data-listing-status]');
        var button = form.querySelector('.sell-submit');
        var originalLabel = button.textContent;
        var submitting = false;
        var navigating = false;

        function clearErrors() {
            errors.textContent = '';
            errors.hidden = true;
            form.querySelectorAll('[aria-invalid]').forEach(function (control) {
                control.removeAttribute('aria-invalid');
                control.removeAttribute('aria-describedby');
            });
        }

        function showErrors(messages) {
            clearErrors();
            Object.keys(messages).forEach(function (field) {
                messages[field].forEach(function (message) {
                    var item = document.createElement('li');
                    item.textContent = message;
                    errors.appendChild(item);
                });
            });
            form.querySelectorAll('[name]').forEach(function (control) {
                if (messages[control.name]) {
                    control.setAttribute('aria-invalid', 'true');
                    control.setAttribute('aria-describedby', 'listing-errors');
                }
            });
            if (messages.category) {
                var categoryToggle = form.querySelector('[data-sell-toggle]');
                categoryToggle.setAttribute('aria-invalid', 'true');
                categoryToggle.setAttribute('aria-describedby', 'listing-errors');
            }
            errors.hidden = false;
            errors.focus();
        }

        form.addEventListener('submit', function (event) {
            if (typeof window.fetch !== 'function') return;
            event.preventDefault();
            if (submitting) return;
            submitting = true;
            clearErrors();
            form.setAttribute('aria-busy', 'true');
            button.disabled = true;
            button.textContent = 'Menyimpan…';
            status.textContent = 'Menyimpan…';

            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function (response) {
                if (response.redirected) {
                    var target = new URL(response.url, window.location.href);
                    if (target.origin !== window.location.origin) throw new Error('Unexpected redirect');
                    navigating = true;
                    window.location.assign(target.href);
                    return null;
                }
                if (response.status === 403 || response.status === 404) {
                    showErrors({ __all__: [response.status === 403
                        ? 'Sesi tidak valid atau akses ditolak. Muat ulang halaman sebelum mencoba lagi.'
                        : 'Listing tidak ditemukan atau Anda tidak memiliki akses.'] });
                    return null;
                }
                return response.json();
            }).then(function (data) {
                if (!data) return;
                if (data.ok && typeof data.redirect_url === 'string') {
                    var target = new URL(data.redirect_url, window.location.href);
                    if (target.origin !== window.location.origin) throw new Error('Unexpected redirect');
                    status.textContent = data.message || 'Listing tersimpan.';
                    navigating = true;
                    window.location.assign(target.href);
                } else if (data.ok === false && data.errors && typeof data.errors === 'object') {
                    showErrors(data.errors);
                } else {
                    throw new Error('Invalid listing response');
                }
            }).catch(function () {
                // Do not replay a POST whose result is unknown.
                showErrors({ __all__: ['Penyimpanan belum dapat dikonfirmasi. Periksa katalog sebelum mencoba lagi.'] });
            }).finally(function () {
                if (!navigating) {
                    submitting = false;
                    form.removeAttribute('aria-busy');
                    button.disabled = false;
                    button.textContent = originalLabel;
                    status.textContent = '';
                }
            });
        });
    }

    function initListingDelete() {
        document.querySelectorAll('[data-delete-listing]').forEach(function (toggle) {
            var dialog = document.getElementById(toggle.getAttribute('aria-controls'));
            if (!dialog) return;
            toggle.addEventListener('click', function () {
                if (!dialog.open) dialog.showModal();
                toggle.setAttribute('aria-expanded', 'true');
            });
            dialog.addEventListener('close', function () { toggle.setAttribute('aria-expanded', 'false'); });
            dialog.addEventListener('click', function (event) {
                if (event.target !== dialog) return;
                var bounds = dialog.getBoundingClientRect();
                if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
            });
        });
    }

    // The homepage sell banner plays its entrance the first time it scrolls into view.
    function initSellBanner() {
        var banner = document.querySelector('[data-sell-banner]');
        if (!banner || !('IntersectionObserver' in window) || prefersReducedMotion()) return;
        if (banner.getBoundingClientRect().top < window.innerHeight) return;
        banner.setAttribute('data-animate', '');
        var observer = new IntersectionObserver(function (entries) {
            if (!entries[0].isIntersecting) return;
            banner.classList.add('is-visible');
            observer.disconnect();
        }, { threshold: 0.35 });
        observer.observe(banner);
    }

    // Homepage: section headings, discover cards and category circles reveal as they
    // scroll in, the hero jackets drift with a light parallax, and discover cards tilt.
    function initHomeMotion() {
        var home = document.querySelector('.homepage-main');
        if (!home || prefersReducedMotion()) return;

        if ('IntersectionObserver' in window) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;
                    entry.target.classList.add('is-revealed');
                    observer.unobserve(entry.target);
                });
            }, { rootMargin: '0px 0px -10% 0px' });
            [
                '.section-head', '.section-title-center',
                '.discover-card', '.category-circle'
            ].forEach(function (selector) {
                var group = home.querySelectorAll(selector);
                Array.prototype.forEach.call(group, function (node, index) {
                    if (node.getBoundingClientRect().top < window.innerHeight && !node.closest('[hidden]')) return;
                    node.style.setProperty('--reveal-delay', (index % 4) * 90 + 'ms');
                    node.setAttribute('data-reveal-item', '');
                    observer.observe(node);
                });
            });
        }

        var media = home.querySelector('.hero-banner__media');
        if (media) {
            var pending = false;
            window.addEventListener('scroll', function () {
                if (pending) return;
                pending = true;
                window.requestAnimationFrame(function () {
                    pending = false;
                    var y = Math.min(window.scrollY, 700);
                    media.style.setProperty('--hero-shift', (y * 0.12).toFixed(1) + 'px');
                });
            }, { passive: true });
        }

        if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
        home.querySelectorAll('.discover-card').forEach(function (card) {
            card.addEventListener('pointermove', function (event) {
                var box = card.getBoundingClientRect();
                var x = (event.clientX - box.left) / box.width - 0.5;
                var y = (event.clientY - box.top) / box.height - 0.5;
                card.classList.add('is-tilting');
                card.style.setProperty('--tilt-x', (x * 8).toFixed(2) + 'deg');
                card.style.setProperty('--tilt-y', (-y * 8).toFixed(2) + 'deg');
            });
            card.addEventListener('pointerleave', function () {
                card.classList.remove('is-tilting');
                card.style.setProperty('--tilt-x', '0deg');
                card.style.setProperty('--tilt-y', '0deg');
            });
        });
    }

    // Hovering the detail photo zooms in around the cursor (mouse and trackpad only).
    function initPhotoZoom() {
        var frame = document.querySelector('.pdp-main-image');
        var photo = frame && frame.querySelector('[data-gallery-main]');
        if (!photo || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
        frame.setAttribute('data-zoomable', '');
        frame.addEventListener('pointermove', function (event) {
            var box = frame.getBoundingClientRect();
            frame.style.setProperty('--zoom-x', ((event.clientX - box.left) / box.width * 100) + '%');
            frame.style.setProperty('--zoom-y', ((event.clientY - box.top) / box.height * 100) + '%');
        });
        frame.addEventListener('pointerenter', function () { frame.classList.add('is-zooming'); });
        frame.addEventListener('pointerleave', function () { frame.classList.remove('is-zooming'); });
    }

    // Show a shimmer behind product photos until they have loaded.
    function initPhotoShimmer() {
        document.querySelectorAll('.product-card__media img, .pdp-main-image img').forEach(function (img) {
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

    // Only the card that was clicked shares a name with the detail photo, so the
    // morph happens between a card and its detail page and nowhere else.
    function cardPhotoFor(path) {
        var link = document.querySelector('.product-card__media[href="' + path + '"]');
        return link && link.querySelector('img');
    }

    window.addEventListener('pageswap', function (event) {
        if (!event.viewTransition || !event.activation || !event.activation.entry) return;
        var photo = cardPhotoFor(new URL(event.activation.entry.url).pathname);
        if (!photo) return;
        var current = document.querySelector('[data-gallery-main]');
        if (current) current.style.viewTransitionName = 'none';
        photo.style.viewTransitionName = 'product-photo';
    });

    window.addEventListener('pagereveal', function (event) {
        if (!event.viewTransition || !window.navigation || !navigation.activation || !navigation.activation.from) return;
        var photo = cardPhotoFor(new URL(navigation.activation.from.url).pathname);
        if (!photo) return;
        var current = document.querySelector('[data-gallery-main]');
        if (current) current.style.viewTransitionName = 'none';
        photo.style.viewTransitionName = 'product-photo';
        event.viewTransition.finished.finally(function () {
            photo.style.viewTransitionName = '';
            if (current) current.style.viewTransitionName = 'product-photo';
        });
    });

    function init() {
        initAnimatedTabs();
        initCategoryTabs();
        initListingTabs();
        initFilterToggle();
        initGallery();
        initBagDrawer();
        initBagForms();
        initWishlistForms();
        initSellForm();
        initListingSubmit();
        initListingDelete();
        initToasts();
        initDrawerSearch(initHeaderSearch());
        initScrollNavbar();
        initCardReveal();
        initPhotoZoom();
        initPhotoShimmer();
        initSellBanner();
        initHomeMotion();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
