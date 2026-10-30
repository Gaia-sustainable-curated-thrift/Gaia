// Sell / edit listing form: photo picker, category menu, price formatting and
// submitting over fetch with inline validation errors.
(function (Gaia) {
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

    Gaia.register(function () {
        initSellForm();
        initListingSubmit();
    });
})(window.Gaia);
