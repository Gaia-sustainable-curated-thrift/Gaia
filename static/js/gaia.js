(function () {
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
    }

    function initCategoryTabs() {
        var tabs = document.querySelector('[data-category-tabs]');
        if (!tabs) return;
        var groups = document.querySelectorAll('[data-category-group]');

        tabs.addEventListener('click', function (event) {
            var item = event.target.closest('.segment__item');
            if (!item || !tabs.contains(item)) return;
            event.preventDefault();

            activateItem(tabs, item);
            var slug = item.getAttribute('data-gender');
            groups.forEach(function (group) {
                group.hidden = group.getAttribute('data-gender') !== slug;
            });
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

            activateItem(tabs, item);
            var name = item.getAttribute('data-category-name');
            cards.forEach(function (card) {
                card.hidden = card.getAttribute('data-category') !== name;
            });
            if (empty) {
                empty.hidden = Array.prototype.some.call(cards, function (card) { return !card.hidden; });
            }
        });
    }

    function initFilterToggle() {
        var toggle = document.querySelector('[data-filter-toggle]');
        var body = document.querySelector('[data-filter-body]');
        if (!toggle || !body) return;

        toggle.addEventListener('click', function () {
            var collapsed = body.toggleAttribute('hidden');
            toggle.setAttribute('aria-expanded', String(!collapsed));
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

        input.readOnly = false;
        input.setAttribute('aria-label', 'Search');

        var form = document.createElement('form');
        form.className = 'search-form';
        form.method = 'get';
        form.action = url;
        form.setAttribute('role', 'search');
        form.appendChild(input);
        box.appendChild(form);
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
                if (full) main.src = full;
            });
        });
    }

    function initBagDrawer() {
        var drawer = document.getElementById('bag-drawer');
        var toggles = document.querySelectorAll('[data-bag-toggle]');
        if (!drawer || !toggles.length) return;

        toggles.forEach(function (toggle) {
            toggle.addEventListener('click', function () {
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

    function showBagToast(toast) {
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
            icon.innerHTML = '<svg class="icon" aria-hidden="true" focusable="false"><use href="#icon-bag"></use></svg>';
            el.appendChild(icon);
        }

        var drawer = document.getElementById('bag-drawer');
        (drawer && drawer.open ? drawer : document.body).appendChild(el);
        dismissToast(el, 4000);
    }

    function initBagForms() {
        var requestPending = false;
        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.matches('form[action*="/bag/"]')) return;
            if (typeof window.fetch !== 'function') return;

            event.preventDefault();
            if (requestPending) return;
            requestPending = true;
            form.setAttribute('aria-busy', 'true');
            var button = form.querySelector('button[type="submit"]');
            if (button) button.disabled = true;
            var drawer = document.getElementById('bag-drawer');

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
                    badge.textContent = data.bag_count;
                    badge.hidden = data.bag_count === 0;
                });
                document.querySelectorAll('[data-bag-toggle]').forEach(function (toggle) {
                    toggle.setAttribute('aria-label', 'Shopping bag, ' + data.bag_count + ' items');
                });
                if (data.open && drawer && !drawer.open) drawer.showModal();
                showBagToast(data.toast);
            }).catch(function () {
                // A failed response may follow a successful POST; do not replay it.
                showBagToast({ kind: 'error', text: 'Could not update your bag. Please try again.' });
            }).finally(function () {
                requestPending = false;
                form.removeAttribute('aria-busy');
                if (button) button.disabled = false;
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
            var chosen = [];

            var syncInput = function () {
                var dt = new DataTransfer();
                chosen.forEach(function (file) { dt.items.add(file); });
                input.files = dt.files;
            };

            var render = function () {
                photos.querySelectorAll('.sell-photo').forEach(function (node) { node.remove(); });
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

                    if (index === 0) {
                        var cover = document.createElement('span');
                        cover.className = 'sell-photo__cover';
                        cover.textContent = 'Cover';
                        tile.appendChild(cover);
                    }
                    photos.insertBefore(tile, addTile);
                });
                var full = chosen.length >= MAX_PHOTOS;
                addTile.hidden = full;
                addTile.style.display = full ? 'none' : '';
            };

            input.addEventListener('change', function () {
                Array.prototype.forEach.call(input.files, function (file) {
                    if (chosen.length < MAX_PHOTOS) chosen.push(file);
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

    function init() {
        initCategoryTabs();
        initListingTabs();
        initFilterToggle();
        initGallery();
        initBagDrawer();
        initBagForms();
        initSellForm();
        initToasts();
        initDrawerSearch(initHeaderSearch());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
