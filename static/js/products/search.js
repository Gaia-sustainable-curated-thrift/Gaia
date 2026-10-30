// Search page: the collapsible filter panel. Filtering itself is done by HTMX
// attributes on the form (see templates/products/search.html).
(function (Gaia) {
    var prefersReducedMotion = Gaia.prefersReducedMotion;

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

    Gaia.register(function () {
        initFilterToggle();
    });
})(window.Gaia);
