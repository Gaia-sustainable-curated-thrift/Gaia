// Delete-listing dialogs, and deleting straight from a product card without a reload.
(function (Gaia) {
    var showToast = Gaia.showToast;

    function initListingDelete(root) {
        (root || document).querySelectorAll('[data-delete-listing]:not([data-delete-ready])').forEach(function (toggle) {
            var dialog = document.getElementById(toggle.getAttribute('aria-controls'));
            if (!dialog) return;
            toggle.setAttribute('data-delete-ready', '');
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

    // Deleting from a product card happens in place: the card fades out at once and
    // comes back with an error toast if the server refuses. The detail page keeps its
    // normal form post, since it has to navigate away anyway.
    function initCardDelete() {
        document.addEventListener('submit', function (event) {
            var form = event.target;
            var dialog = form.closest('.pdp-delete-dialog');
            if (!dialog || form.method !== 'post' || typeof window.fetch !== 'function') return;
            var toggle = document.querySelector('[data-delete-listing][aria-controls="' + dialog.id + '"]');
            var card = toggle && toggle.closest('.product-card');
            if (!card) return;
            event.preventDefault();
            dialog.close();
            card.classList.add('is-removing');

            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            }).then(function (response) {
                return response.json().then(function (data) { return { ok: response.ok, data: data }; });
            }).then(function (result) {
                if (!result.ok || !result.data || result.data.ok !== true) {
                    throw result.data && result.data.toast ? result.data.toast : null;
                }
                window.setTimeout(function () { card.remove(); dialog.remove(); }, 260);
                showToast(result.data.toast);
            }).catch(function (toast) {
                card.classList.remove('is-removing');
                showToast(toast && toast.text ? toast : { kind: 'error', text: 'Could not delete this listing. Please try again.' });
            });
        });
    }

    Gaia.register(function () {
        initListingDelete();
        initCardDelete();
        // HTMX swaps in new search results; wire up the owner cards it brings.
        document.body.addEventListener('htmx:afterSettle', function () { initListingDelete(); });
    });
})(window.Gaia);
