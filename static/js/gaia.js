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

    function init() {
        initCategoryTabs();
        initListingTabs();
        initFilterToggle();
        initGallery();
        initDrawerSearch(initHeaderSearch());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
