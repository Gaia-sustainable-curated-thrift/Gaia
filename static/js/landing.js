const menuToggle = document.querySelector('[data-menu-toggle]');
const menu = document.getElementById('landing-menu');
const searchToggle = document.querySelector('[data-search-toggle]');
const search = document.getElementById('landing-search');

function closeMenu() {
    menu.hidden = true;
    menuToggle.setAttribute('aria-expanded', 'false');
}

menuToggle.addEventListener('click', () => {
    menu.hidden = !menu.hidden;
    menuToggle.setAttribute('aria-expanded', String(!menu.hidden));
});

searchToggle.addEventListener('click', () => {
    const expanded = search.classList.toggle('is-open');
    searchToggle.setAttribute('aria-expanded', String(expanded));
    searchToggle.setAttribute('aria-label', expanded ? 'Hide search' : 'Show search');
    if (expanded) search.querySelector('input').focus();
});

document.addEventListener('click', event => {
    if (!menu.hidden && !menu.contains(event.target) && !menuToggle.contains(event.target)) closeMenu();
});

document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (!menu.hidden) {
        closeMenu();
        menuToggle.focus();
    } else if (search.classList.contains('is-open')) {
        search.classList.remove('is-open');
        searchToggle.setAttribute('aria-expanded', 'false');
        searchToggle.setAttribute('aria-label', 'Show search');
        searchToggle.focus();
    }
});
