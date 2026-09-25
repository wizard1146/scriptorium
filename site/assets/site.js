// Mobile sidebar toggle. Nothing else: the site works without JavaScript except search.
document.querySelector('.site-header__menu-button')?.addEventListener('click', e => {
  const open = document.body.classList.toggle('sidebar-open');
  e.currentTarget.setAttribute('aria-expanded', open);
});
