const menuToggle = document.querySelector('[data-menu-toggle]');
const menu = document.getElementById('header-menu');
menuToggle?.addEventListener('click', () => {
  menu.hidden = !menu.hidden;
  menuToggle.setAttribute('aria-expanded', String(!menu.hidden));
});
document.addEventListener('click', (event) => {
  if (menu && !menu.hidden && !menu.contains(event.target) && !menuToggle.contains(event.target)) {
    menu.hidden = true;
    menuToggle.setAttribute('aria-expanded', 'false');
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && menu && !menu.hidden) {
    menu.hidden = true;
    menuToggle.setAttribute('aria-expanded', 'false');
    menuToggle.focus();
  }
});
const logoutDialog = document.getElementById('logout-dialog');
document.querySelectorAll('[data-logout]').forEach(button => button.addEventListener('click', () => logoutDialog.showModal()));
document.querySelector('[data-close-dialog]')?.addEventListener('click', () => logoutDialog.close());
logoutDialog?.addEventListener('click', event => {
  if (event.target === logoutDialog) {
    const bounds = logoutDialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) logoutDialog.close();
  }
});
document.querySelectorAll('.field').forEach(field => {
  const input = field.querySelector('input');
  const errors = field.querySelector('.field-errors');
  if (input && errors) {
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', errors.id);
  }
});
