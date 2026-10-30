// Product detail photos: thumbnails switch the main photo, which zooms under the cursor.
(function (Gaia) {
    var prefersReducedMotion = Gaia.prefersReducedMotion;

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

    Gaia.register(function () {
        initGallery();
        initPhotoZoom();
    });
})(window.Gaia);
