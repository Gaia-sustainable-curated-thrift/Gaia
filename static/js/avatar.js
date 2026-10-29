(() => {
    const input = document.querySelector('[data-avatar-input]');
    if (!input) return;
    const preview = document.querySelector('[data-avatar-preview]');
    const fallback = document.querySelector('[data-avatar-fallback]');
    const feedback = document.querySelector('[data-avatar-feedback]');
    const original = preview.getAttribute('src');
    let objectUrl;
    input.setAttribute('aria-describedby', 'avatar-help');
    function resetPreview() {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = null;
        if (original) preview.src = original;
        else preview.removeAttribute('src');
        preview.hidden = !original;
        fallback.hidden = Boolean(original);
    }
    input.addEventListener('change', () => {
        resetPreview();
        feedback.textContent = '';
        input.removeAttribute('aria-invalid');
        const file = input.files[0];
        if (!file) return;
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) {
            feedback.textContent = 'Choose a JPG, PNG or WebP image no larger than 2 MB.';
            input.value = '';
            input.setAttribute('aria-invalid', 'true');
            return;
        }
        objectUrl = URL.createObjectURL(file);
        preview.src = objectUrl;
        preview.hidden = false;
        fallback.hidden = true;
        feedback.textContent = 'New photo selected. Save Changes to apply it.';
    });
    preview.addEventListener('error', () => {
        if (!objectUrl) return;
        resetPreview();
        input.value = '';
        feedback.textContent = 'This image could not be previewed. Choose another photo.';
    });
    window.addEventListener('pagehide', () => { if (objectUrl) URL.revokeObjectURL(objectUrl); });
})();
