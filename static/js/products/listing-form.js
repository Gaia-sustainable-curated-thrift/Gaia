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
            var TRASH = '<svg class="icon" aria-hidden="true" focusable="false"><use href="#icon-trash"></use></svg>';

            // Satu daftar untuk semua foto, sesuai urutan tampil. Foto pertama adalah cover.
            // Foto yang sudah tersimpan memakai tile dari server; foto baru dibuatkan tile sendiri.
            // Dengan satu daftar, foto lama dan baru bisa dihapus dan diurutkan dengan cara yang sama.
            var items = Array.prototype.map.call(photos.querySelectorAll('[data-existing-photo]'), function (tile) {
                return {
                    kind: 'existing',
                    id: tile.getAttribute('data-photo-id'),
                    tile: tile,
                    button: tile.querySelector('[data-remove-existing]'),
                    removed: false
                };
            });
            var orderField = document.createElement('input');
            orderField.type = 'hidden';
            orderField.name = 'photo_order';
            form.appendChild(orderField);

            // Foto yang ditandai dihapus masih tampil (pudar) supaya bisa dibatalkan, tapi tidak dihitung.
            var keptItems = function () {
                return items.filter(function (item) { return !item.removed; });
            };

            // Yang dikirim form: id foto lama yang dibuang, file baru (urut sesuai tampilan), dan
            // urutan akhir semua foto yang dipertahankan (e<id> = foto lama, n<k> = file baru ke-k).
            var syncForm = function () {
                var files = new DataTransfer();
                items.forEach(function (item) {
                    if (item.kind === 'new') files.items.add(item.file);
                });
                input.files = files.files;

                form.querySelectorAll('[data-removed-marker]').forEach(function (marker) { marker.remove(); });
                items.forEach(function (item) {
                    if (item.kind !== 'existing' || !item.removed) return;
                    var marker = document.createElement('input');
                    marker.type = 'hidden';
                    marker.name = 'remove_photos';
                    marker.value = item.id;
                    marker.setAttribute('data-removed-marker', item.id);
                    form.appendChild(marker);
                });

                var newIndex = 0;
                orderField.value = keptItems().map(function (item) {
                    return item.kind === 'existing' ? 'e' + item.id : 'n' + (newIndex++);
                }).join(',');
            };

            // Susun ulang tile sesuai daftar, pindahkan pill Cover ke foto pertama, lalu sinkronkan form.
            var render = function () {
                items.forEach(function (item, index) {
                    photos.insertBefore(item.tile, addTile);
                    item.tile.setAttribute('aria-label', 'Photo ' + (index + 1) + ' of ' + items.length +
                        '. Use the left and right arrow keys to change the order. The first photo is the cover.');
                });
                photos.querySelectorAll('.sell-photo__cover').forEach(function (pill) { pill.remove(); });
                var first = keptItems()[0];
                if (first) {
                    var pill = document.createElement('span');
                    pill.className = 'sell-photo__cover';
                    pill.textContent = 'Cover';
                    first.tile.appendChild(pill);
                }
                var full = keptItems().length >= MAX_PHOTOS;
                addTile.hidden = full;
                addTile.style.display = full ? 'none' : '';
                syncForm();
            };

            var moveItem = function (item, target, after) {
                items.splice(items.indexOf(item), 1);
                items.splice(items.indexOf(target) + (after ? 1 : 0), 0, item);
                render();
            };

            // Drag foto ke kiri untuk menjadikannya cover (atau ke mana pun untuk mengurutkan).
            // Mouse mulai drag setelah bergeser sedikit; layar sentuh perlu ditahan sebentar supaya
            // scroll halaman tetap normal. Penanda garis menunjukkan tempat jatuhnya.
            var attachReorder = function (item) {
                var tile = item.tile;
                tile.tabIndex = 0;
                tile.setAttribute('role', 'group');

                tile.addEventListener('pointerdown', function (down) {
                    if (down.button !== 0 || down.target.closest('button')) return;
                    var touch = down.pointerType === 'touch';
                    var dragging = false;
                    var timer = null;
                    var target = null;
                    var after = false;

                    var clearMarks = function () {
                        photos.querySelectorAll('.drop-before, .drop-after').forEach(function (el) {
                            el.classList.remove('drop-before', 'drop-after');
                        });
                    };
                    var blockScroll = function (event) { if (dragging) event.preventDefault(); };
                    var begin = function () {
                        dragging = true;
                        tile.classList.add('is-dragging');
                        try { tile.setPointerCapture(down.pointerId); } catch (error) { /* tidak wajib */ }
                    };
                    var onMove = function (move) {
                        var dx = move.clientX - down.clientX;
                        var dy = move.clientY - down.clientY;
                        if (!dragging) {
                            if (Math.hypot(dx, dy) <= (touch ? 10 : 6)) return;
                            if (touch) { finish(false); return; }  // jari bergerak sebelum ditahan: itu scroll
                            begin();
                        }
                        move.preventDefault();
                        tile.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
                        // Tempat jatuh: di sebelah tile yang pusatnya paling dekat dengan pointer.
                        var nearest = Infinity;
                        target = null;
                        items.forEach(function (other) {
                            if (other === item) return;
                            var box = other.tile.getBoundingClientRect();
                            var centerX = box.left + box.width / 2;
                            var distance = Math.hypot(move.clientX - centerX, move.clientY - (box.top + box.height / 2));
                            if (distance < nearest) {
                                nearest = distance;
                                target = other;
                                after = move.clientX >= centerX;
                            }
                        });
                        clearMarks();
                        if (target) target.tile.classList.add(after ? 'drop-after' : 'drop-before');
                    };
                    var finish = function (apply) {
                        window.clearTimeout(timer);
                        document.removeEventListener('pointermove', onMove);
                        document.removeEventListener('pointerup', onUp);
                        document.removeEventListener('pointercancel', onCancel);
                        document.removeEventListener('touchmove', blockScroll);
                        var moved = dragging && apply && target;
                        tile.classList.remove('is-dragging');
                        tile.style.transform = '';
                        clearMarks();
                        dragging = false;
                        if (moved) moveItem(item, target, after);
                    };
                    var onUp = function () { finish(true); };
                    var onCancel = function () { finish(false); };

                    document.addEventListener('pointermove', onMove);
                    document.addEventListener('pointerup', onUp);
                    document.addEventListener('pointercancel', onCancel);
                    document.addEventListener('touchmove', blockScroll, { passive: false });
                    if (touch) timer = window.setTimeout(begin, 300);
                });

                // Untuk keyboard: panah kiri/kanan saat tile difokuskan menggeser foto.
                tile.addEventListener('keydown', function (event) {
                    if (event.target !== tile || (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight')) return;
                    var neighbour = items[items.indexOf(item) + (event.key === 'ArrowLeft' ? -1 : 1)];
                    if (!neighbour) return;
                    event.preventDefault();
                    moveItem(item, neighbour, event.key === 'ArrowRight');
                    tile.focus();
                });
            };

            // Tombol tong sampah di foto yang sudah tersimpan: tandai (pudar) dan kirim id-nya bersama
            // form; server menghapusnya saat Save. Ditekan lagi berarti dibatalkan.
            items.forEach(function (item) {
                attachReorder(item);
                item.button.addEventListener('click', function () {
                    if (item.removed && keptItems().length >= MAX_PHOTOS) {
                        Gaia.showToast({ kind: 'error', text: 'A listing can have maximum 5 photos.' });
                        return;
                    }
                    item.removed = !item.removed;
                    item.tile.classList.toggle('is-removed', item.removed);
                    item.button.setAttribute('aria-pressed', item.removed ? 'true' : 'false');
                    item.button.setAttribute(
                        'aria-label',
                        item.button.getAttribute('aria-label').replace(/^(Remove|Restore)/, item.removed ? 'Restore' : 'Remove')
                    );
                    item.button.querySelector('use').setAttribute('href', item.removed ? '#icon-plus' : '#icon-trash');
                    render();
                });
            });

            // Foto baru (belum tersimpan): tile dengan pratinjau dan tombol hapus sendiri.
            var addNewPhoto = function (file) {
                var tile = document.createElement('div');
                tile.className = 'sell-photo';

                var img = document.createElement('img');
                img.alt = '';
                img.draggable = false;
                var reader = new FileReader();
                reader.onload = function (e) { img.src = e.target.result; };
                reader.readAsDataURL(file);

                var remove = document.createElement('button');
                remove.type = 'button';
                remove.className = 'sell-photo__remove';
                remove.setAttribute('aria-label', 'Remove photo');
                remove.innerHTML = TRASH;

                tile.appendChild(img);
                tile.appendChild(remove);

                var item = { kind: 'new', file: file, tile: tile };
                remove.addEventListener('click', function () {
                    items.splice(items.indexOf(item), 1);
                    tile.remove();
                    render();
                });
                attachReorder(item);
                items.push(item);
            };

            input.addEventListener('change', function () {
                Array.prototype.forEach.call(input.files, function (file) {
                    if (keptItems().length < MAX_PHOTOS) addNewPhoto(file);
                });
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
