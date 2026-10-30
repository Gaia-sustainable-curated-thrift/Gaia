// Homepage motion: hero parallax, section reveals, discover tilt and the sell banner.
(function (Gaia) {
    var prefersReducedMotion = Gaia.prefersReducedMotion;

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

    Gaia.register(function () {
        initSellBanner();
        initHomeMotion();
    });
})(window.Gaia);
