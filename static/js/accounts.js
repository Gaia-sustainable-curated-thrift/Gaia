(() => {
let bindings;
const initialize = () => {
if (bindings) bindings.abort();
bindings = new AbortController();
const options = {signal: bindings.signal};
const logoutDialog = document.getElementById('logout-dialog');
document.querySelectorAll('[data-logout]').forEach(button => button.addEventListener('click', () => logoutDialog?.showModal(), options));
document.querySelector('[data-close-dialog]')?.addEventListener('click', () => logoutDialog?.close(), options);
logoutDialog?.addEventListener('click', event => {
  if (event.target === logoutDialog) {
    const bounds = logoutDialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) logoutDialog.close();
  }
}, options);
document.querySelectorAll('.field').forEach(field => {
  const input = field.querySelector('input');
  const errors = field.querySelector('.field-errors');
  if (input && errors) {
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', errors.id);
  }
});

};
initialize();
document.addEventListener('accounts:updated', initialize);
})();
