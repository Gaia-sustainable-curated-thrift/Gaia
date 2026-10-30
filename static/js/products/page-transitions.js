// Cross-page photo morph between a product card and its detail page
// (View Transitions API; browsers without it just navigate normally).
(function (Gaia) {
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
})(window.Gaia);
