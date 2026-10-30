(() => {
    const dialog = document.getElementById('my-product-delete-dialog');
    if (!dialog) return;
    const form = dialog.querySelector('[data-product-delete-form]');
    const title = dialog.querySelector('[data-delete-product-name]');
    document.querySelectorAll('[data-product-delete-url]').forEach(button => {
        button.addEventListener('click', () => {
            form.action = button.dataset.productDeleteUrl;
            title.textContent = button.dataset.productTitle;
            dialog.showModal();
        });
    });
    dialog.addEventListener('click', event => {
        if (event.target !== dialog) return;
        const bounds = dialog.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
})();
