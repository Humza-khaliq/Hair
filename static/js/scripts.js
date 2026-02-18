function toggleNav() {
    const navLinks = document.getElementById('nav-links');
    if (navLinks) {
        navLinks.classList.toggle('active');
    }
}

window.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('page-ready');
});
