// Segmented tabs on the home and listing pages: a sliding pill marks the active
// tab and the content underneath fades in.
(function (Gaia) {
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

    Gaia.register(function () {
        initAnimatedTabs();
        initCategoryTabs();
        initListingTabs();
    });
})(window.Gaia);
