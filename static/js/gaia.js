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

        tabs.addEventListener('click', function (event) {
            var item = event.target.closest('.segment__item');
            if (!item || !tabs.contains(item)) return;
            event.preventDefault();

            activateItem(tabs, item);
            var name = item.getAttribute('data-category-name');
            cards.forEach(function (card) {
                card.hidden = card.getAttribute('data-category') !== name;
            });
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
            var duration = parseInt(toast.getAttribute('data-toast-duration'), 10) || 4000;
            dismissToast(toast, duration);
        });
    }

    function showBagToast(toast) {
        if (!toast || toast.kind !== 'added') return;
        var el = document.createElement('div');
        el.className = 'toast toast--added';
        el.setAttribute('role', 'status');
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

        document.body.appendChild(el);
        dismissToast(el, 4000);
    }

    function initBagForms() {
        document.addEventListener('submit', function (event) {
            var form = event.target;
            if (!form.matches('form[action*="/bag/"]')) return;

            event.preventDefault();
            var drawer = document.getElementById('bag-drawer');

            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function (response) {
                return response.ok ? response.json() : null;
            }).then(function (data) {
                if (!data) return;
                var panel = document.querySelector('.bag-drawer__panel');
                if (panel && data.drawer) panel.innerHTML = data.drawer;
                if (data.open && drawer && !drawer.open) drawer.showModal();
                showBagToast(data.toast);
            }).catch(function () {
                form.submit();
            });
        });
    }

    function init() {
        initCategoryTabs();
        initListingTabs();
        initFilterToggle();
        initGallery();
        initBagDrawer();
        initBagForms();
        initToasts();
        initDrawerSearch(initHeaderSearch());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
