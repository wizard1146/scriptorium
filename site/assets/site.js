// Sidebar drawer (phones, < 768px). From 768px up the sidebar is a persistent rail and none of this runs.
// Nothing else on the site needs JavaScript except search.
(() => {
  const openBtn = document.getElementById('nav-open-button');
  const closeBtn = document.getElementById('nav-close-button');
  const backdrop = document.getElementById('site-backdrop');
  const sidebar = document.getElementById('site-sidebar');
  if (!openBtn || !sidebar) return;
  const set = open => {
    document.body.classList.toggle('sidebar-open', open);
    openBtn.setAttribute('aria-expanded', open);
    if (backdrop) backdrop.hidden = !open;
    if (open) closeBtn?.focus(); else if (document.activeElement && sidebar.contains(document.activeElement)) openBtn.focus();
  };
  openBtn.addEventListener('click', () => set(true));
  closeBtn?.addEventListener('click', () => set(false));
  backdrop?.addEventListener('click', () => set(false));
  sidebar.addEventListener('click', e => { if (e.target.closest('.nav-group a')) set(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') set(false); });
  window.matchMedia('(min-width: 48rem)').addEventListener('change', e => { if (e.matches) set(false); });
})();

// Remember the nav's scroll position for the next page (restored by the inline script in template.html).
(() => {
  const nav = document.getElementById('site-nav');
  if (!nav) return;
  const save = () => { try { sessionStorage.setItem('scriptorium-nav-scroll', nav.scrollTop); } catch {} };
  nav.addEventListener('scroll', save, { passive: true });
  addEventListener('pagehide', save);
})();

// The table of contents starts collapsed on phones so it doesn't push the article down the screen.
(() => {
  const toc = document.getElementById('toc');
  if (toc && matchMedia('(max-width: 47.99rem)').matches) toc.removeAttribute('open');
})();
