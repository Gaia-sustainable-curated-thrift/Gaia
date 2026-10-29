/* Chat: inbox & room */
(function () {
    'use strict';

    var POLL_ROOM_MS = 3000;
    var POLL_INBOX_MS = 15000;

    // Format waktu & harga
    function startOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    function daysAgo(date) {
        return Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
    }

    function clock(date) {
        return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    }

    function inboxTime(iso) {
        var date = new Date(iso);
        var days = daysAgo(date);
        if (days <= 0) return clock(date);
        if (days === 1) return 'Yesterday';
        if (days < 7) return date.toLocaleDateString('en-US', { weekday: 'short' });
        return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    }

    function dayLabel(iso) {
        var date = new Date(iso);
        var days = daysAgo(date);
        if (days <= 0) return 'Today';
        if (days === 1) return 'Yesterday';
        return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    function rupiah(value) {
        return 'Rp' + Number(value).toLocaleString('id-ID');
    }

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function localizeTimes(root) {
        root.querySelectorAll('[data-chat-time="inbox"]').forEach(function (node) {
            node.textContent = inboxTime(node.getAttribute('datetime'));
        });
    }

    // Inbox
    function initInbox(inbox) {
        var form = inbox.querySelector('[data-chat-filters]');
        var search = inbox.querySelector('[data-chat-search]');
        var list = inbox.querySelector('[data-chat-list]');
        var skeleton = inbox.querySelector('[data-chat-skeleton]');
        var roomBase = window.location.pathname.replace(/\/$/, '') + '/';
        var filter = new URLSearchParams(window.location.search).get('filter') || 'all';
        var debounce;

        function query() {
            var params = new URLSearchParams();
            if (search.value.trim()) params.set('q', search.value.trim());
            if (filter === 'unread') params.set('filter', 'unread');
            return params.toString();
        }

        function renderRow(row) {
            var item = el('li');
            var link = el('a', 'chat-row' + (row.unread ? ' is-unread' : ''));
            link.href = roomBase + row.id + '/';
            link.appendChild(el('span', 'chat-avatar chat-avatar--' + row.kind, row.initials));
            var body = el('span', 'chat-row__body');
            body.appendChild(el('span', 'chat-row__title', row.title));
            body.appendChild(el('span', 'chat-row__preview', row.preview || 'Belum ada pesan'));
            link.appendChild(body);
            var meta = el('span', 'chat-row__meta');
            var time = el('time', null, inboxTime(row.last_at));
            time.setAttribute('datetime', row.last_at);
            meta.appendChild(time);
            if (row.unread) {
                var badge = el('span', 'chat-badge', row.unread);
                badge.setAttribute('aria-label', row.unread + ' belum dibaca');
                meta.appendChild(badge);
            }
            link.appendChild(meta);
            item.appendChild(link);
            return item;
        }

        function load(showSkeleton) {
            if (showSkeleton) {
                list.replaceChildren();
                for (var i = 0; i < 4; i++) list.appendChild(skeleton.content.cloneNode(true));
            }
            var qs = query();
            history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
            fetch(inbox.dataset.api + (qs ? '?' + qs : ''), { credentials: 'same-origin' })
                .then(function (response) { return response.ok ? response.json() : null; })
                .then(function (data) {
                    if (!data) return;
                    list.replaceChildren();
                    if (!data.conversations.length) {
                        list.appendChild(el('li', 'chat-list__empty', 'Tidak ada percakapan yang cocok.'));
                        return;
                    }
                    data.conversations.forEach(function (row) { list.appendChild(renderRow(row)); });
                });
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            if (event.submitter && event.submitter.name === 'filter') {
                filter = event.submitter.value;
                form.querySelectorAll('.chat-pill').forEach(function (pill) {
                    var active = pill === event.submitter;
                    pill.classList.toggle('is-active', active);
                    pill.setAttribute('aria-pressed', active ? 'true' : 'false');
                });
            }
            load(true);
        });

        search.addEventListener('input', function () {
            clearTimeout(debounce);
            debounce = setTimeout(function () { load(true); }, 300);
        });

        localizeTimes(inbox);
        setInterval(function () {
            if (!document.hidden && document.activeElement !== search) load(false);
        }, POLL_INBOX_MS);
    }

    // Room
    function initRoom(room) {
        var thread = room.querySelector('[data-chat-thread]');
        var emptyNote = room.querySelector('[data-chat-empty]');
        var composer = room.querySelector('[data-chat-composer]');
        var input = room.querySelector('[data-chat-input]');
        var sendButton = composer.querySelector('.chat-send');
        var errorBox = room.querySelector('[data-chat-error]');
        var attachToggle = room.querySelector('[data-chat-attach-toggle]');
        var attachMenu = room.querySelector('[data-chat-attach-menu]');
        var imageInput = room.querySelector('[data-chat-image]');
        var offerDialog = room.querySelector('[data-chat-offer-dialog]');
        var csrf = composer.querySelector('[name=csrfmiddlewaretoken]').value;
        var canAnswerOffer = room.dataset.canAnswerOffer === 'true';
        var nodes = {};
        var lastId = 0;
        var lastDay = null;

        function nearBottom() {
            return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 120;
        }

        function scrollToBottom() {
            thread.scrollTop = thread.scrollHeight;
        }

        function showError(text) {
            errorBox.textContent = text || '';
            errorBox.hidden = !text;
        }

        function statusLabel(message) {
            if (!message.mine) return clock(new Date(message.created_at));
            return clock(new Date(message.created_at)) + (message.read ? ' ✓✓ Read' : ' ✓ Sent');
        }

        function offerCard(message) {
            var card = el('div', 'chat-offer');
            card.appendChild(el('span', null, message.mine ? 'Penawaran kamu' : 'Penawaran dari ' + message.sender));
            card.appendChild(el('strong', null, rupiah(message.offer_price)));
            var status = message.offer_status;
            var labels = { pending: 'Menunggu jawaban seller', accepted: 'Penawaran diterima', declined: 'Penawaran ditolak' };
            card.appendChild(el('span', 'chat-offer__status chat-offer__status--' + status, labels[status] || ''));
            if (status === 'pending' && canAnswerOffer && !message.mine) {
                var actions = el('div', 'chat-offer__actions');
                [['decline', 'Tolak', ' chat-button--outline'], ['accept', 'Terima', '']].forEach(function (option) {
                    var button = el('button', 'chat-button' + option[2], option[1]);
                    button.type = 'button';
                    button.dataset.offerAction = option[0];
                    button.dataset.offerId = message.id;
                    actions.appendChild(button);
                });
                card.appendChild(actions);
            }
            return card;
        }

        function productCard(product) {
            var card = el('a', 'chat-product-card');
            card.href = product.url;
            var thumb = el('span', 'chat-product-card__thumb');
            if (product.image) {
                var img = el('img');
                img.src = product.image;
                img.alt = '';
                thumb.appendChild(img);
            }
            card.appendChild(thumb);
            var info = el('span', 'chat-product-card__info');
            info.appendChild(el('strong', null, product.title));
            info.appendChild(el('span', null, rupiah(product.price)));
            card.appendChild(info);
            return card;
        }

        function buildMessage(message) {
            if (message.kind === 'system') return el('p', 'chat-system', message.body);

            var wrap = el('div', 'chat-msg ' + (message.mine ? 'chat-msg--mine' : 'chat-msg--theirs'));
            if (message.deleted) wrap.classList.add('is-deleted');
            if (message.kind === 'offer') {
                wrap.appendChild(offerCard(message));
            } else if (message.kind === 'product' && message.product) {
                wrap.appendChild(productCard(message.product));
            } else {
                var bubble = el('div', 'chat-bubble', message.kind === 'image' ? null : message.body);
                if (message.kind === 'image' && message.image) {
                    var img = el('img');
                    img.src = message.image;
                    img.alt = 'Photo from ' + message.sender;
                    bubble.appendChild(img);
                }
                wrap.appendChild(bubble);
            }
            wrap.appendChild(el('span', 'chat-msg__meta', statusLabel(message)));
            return wrap;
        }

        function append(message) {
            if (nodes[message.id]) return;
            var day = dayLabel(message.created_at);
            if (day !== lastDay) {
                thread.appendChild(el('p', 'chat-day', day));
                lastDay = day;
            }
            var node = buildMessage(message);
            nodes[message.id] = { node: node, message: message };
            thread.appendChild(node);
            lastId = Math.max(lastId, message.id);
            emptyNote.hidden = true;
        }

        function replace(message) {
            var entry = nodes[message.id];
            if (!entry) return;
            var node = buildMessage(message);
            entry.node.replaceWith(node);
            nodes[message.id] = { node: node, message: message };
        }

        function markReadUpTo(id) {
            Object.keys(nodes).forEach(function (key) {
                var entry = nodes[key];
                if (entry.message.mine && !entry.message.read && entry.message.id <= id) {
                    entry.message.read = true;
                    replace(entry.message);
                }
            });
        }

        function post(url, data) {
            data.append('csrfmiddlewaretoken', csrf);
            return fetch(url, { method: 'POST', body: data, credentials: 'same-origin' })
                .then(function (response) {
                    return response.json().then(function (body) {
                        if (!response.ok) throw new Error(body.error || 'Pesan gagal dikirim.');
                        return body;
                    });
                });
        }

        function send(data) {
            showError('');
            sendButton.disabled = true;
            return post(room.dataset.messagesUrl, data)
                .then(function (body) {
                    append(body.message);
                    scrollToBottom();
                })
                .catch(function (error) { showError(error.message); })
                .finally(function () { sendButton.disabled = false; });
        }

        function poll() {
            if (document.hidden) return;
            fetch(room.dataset.messagesUrl + '?after=' + lastId, { credentials: 'same-origin' })
                .then(function (response) { return response.ok ? response.json() : null; })
                .then(function (data) {
                    if (!data) return;
                    var stick = nearBottom();
                    data.messages.forEach(append);
                    data.offers.forEach(function (offer) {
                        var entry = nodes[offer.id];
                        if (entry && entry.message.offer_status !== offer.offer_status) replace(offer);
                    });
                    markReadUpTo(data.last_read_id);
                    if (stick && data.messages.length) scrollToBottom();
                });
        }

        JSON.parse(document.getElementById('chat-initial').textContent).forEach(append);
        scrollToBottom();
        setInterval(poll, POLL_ROOM_MS);

        composer.addEventListener('submit', function (event) {
            event.preventDefault();
            var body = input.value.trim();
            if (!body) return;
            var data = new FormData();
            data.append('kind', 'text');
            data.append('body', body);
            send(data).then(function () {
                if (errorBox.hidden) input.value = '';
                input.focus();
            });
        });

        attachToggle.addEventListener('click', function () {
            var open = attachMenu.hidden;
            attachMenu.hidden = !open;
            attachToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });

        document.addEventListener('click', function (event) {
            if (!attachMenu.hidden && !event.target.closest('.chat-attach')) {
                attachMenu.hidden = true;
                attachToggle.setAttribute('aria-expanded', 'false');
            }
        });

        imageInput.addEventListener('change', function () {
            if (!imageInput.files.length) return;
            var data = new FormData();
            data.append('kind', 'image');
            data.append('image', imageInput.files[0]);
            attachMenu.hidden = true;
            send(data).then(function () { imageInput.value = ''; });
        });

        if (offerDialog) {
            var offerForm = offerDialog.querySelector('[data-chat-offer-form]');
            room.querySelector('[data-chat-offer-open]').addEventListener('click', function () {
                attachMenu.hidden = true;
                offerDialog.showModal();
            });
            offerDialog.querySelector('[data-chat-offer-cancel]').addEventListener('click', function () {
                offerDialog.close();
            });
            offerForm.addEventListener('submit', function (event) {
                event.preventDefault();
                var data = new FormData();
                data.append('kind', 'offer');
                data.append('offer_price', offerForm.elements.offer_price.value);
                offerDialog.close();
                send(data).then(function () { offerForm.reset(); });
            });
        }

        thread.addEventListener('click', function (event) {
            var button = event.target.closest('[data-offer-action]');
            if (!button) return;
            var data = new FormData();
            data.append('action', button.dataset.offerAction);
            var url = room.dataset.offerUrl.replace(/0\/$/, button.dataset.offerId + '/');
            button.disabled = true;
            post(url, data)
                .then(function (body) { replace(body.message); })
                .catch(function (error) {
                    button.disabled = false;
                    showError(error.message);
                });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var inbox = document.querySelector('[data-chat-inbox]');
        var room = document.querySelector('[data-chat-room]');
        if (inbox) initInbox(inbox);
        if (room) initRoom(room);
    });
})();
