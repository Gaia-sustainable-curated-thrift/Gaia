const searchToggle = document.querySelector('[data-search-toggle]');
const search = document.getElementById('landing-search');

searchToggle.addEventListener('click', () => {
    const expanded = search.classList.toggle('is-open');
    searchToggle.setAttribute('aria-expanded', String(expanded));
    searchToggle.setAttribute('aria-label', expanded ? 'Hide search' : 'Show search');
    if (expanded) search.querySelector('input').focus();
});

document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && search.classList.contains('is-open')) {
        search.classList.remove('is-open');
        searchToggle.setAttribute('aria-expanded', 'false');
        searchToggle.setAttribute('aria-label', 'Show search');
        searchToggle.focus();
    }
});
