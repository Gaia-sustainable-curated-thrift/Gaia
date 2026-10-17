(() => {
    const drawer = document.getElementById('site-drawer');
    if (!drawer) return;
    const triggers = document.querySelectorAll('[data-menu-toggle]');
    const closeButton = drawer.querySelector('[data-drawer-close]');
    const status = drawer.querySelector('[data-drawer-status]');

    triggers.forEach(trigger => trigger.addEventListener('click', () => {
        if (drawer.open) return;
        status.hidden = true;
        status.textContent = '';
        drawer.showModal();
        document.body.classList.add('site-drawer-open');
        triggers.forEach(button => button.setAttribute('aria-expanded', 'true'));
        closeButton.focus();
    }));

    closeButton.addEventListener('click', () => drawer.close());
    drawer.addEventListener('close', () => {
        document.body.classList.remove('site-drawer-open');
        triggers.forEach(button => button.setAttribute('aria-expanded', 'false'));
    });
    drawer.addEventListener('click', event => {
        if (event.target !== drawer) return;
        const bounds = drawer.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) drawer.close();
    });

    function announce(message) {
        status.hidden = false;
        status.textContent = message;
        status.scrollIntoView({ block: 'nearest' });
    }
    drawer.querySelectorAll('[data-drawer-category]').forEach(button => button.addEventListener('click', () => {
        announce(`${button.dataset.drawerCategory} collection is coming soon. Stay tuned!`);
    }));
    drawer.querySelector('[data-drawer-sell]')?.addEventListener('click', () => {
        announce('Selling on GAIA is coming soon. Stay tuned!');
    });
})();
