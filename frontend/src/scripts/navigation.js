const header = document.querySelector('.site-header-shell');
const menu = document.getElementById('siteMenu');
const toggle = document.getElementById('menuToggle');
const compact = window.matchMedia('(max-width: 1200px)');
const background = [document.querySelector('main'), document.querySelector('footer')];
let open = false;

function setOpen(next, restoreFocus = false) {
  open = next && compact.matches;
  menu.classList.toggle('is-open', open);
  toggle.setAttribute('aria-expanded', String(open));
  toggle.setAttribute('aria-label', open ? 'Uždaryti meniu' : 'Atidaryti meniu');
  document.documentElement.classList.toggle('nav-open', open);
  for (const element of background) element.inert = open;
  if (restoreFocus) toggle.focus();
}

toggle.addEventListener('click', () => {
  setOpen(!open);
  if (open) menu.querySelector('.view-button').focus();
});

// Release the content before a view's own handler moves focus into it.
menu.addEventListener('click', event => {
  if (open && event.target.closest('button, a')) setOpen(false);
}, true);

header.addEventListener('keydown', event => {
  if (!open) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    setOpen(false, true);
  } else if (event.key === 'Tab') {
    const items = [...header.querySelectorAll('a[href], button:not([disabled])')]
      .filter(element => element.getClientRects().length);
    const first = items[0];
    const last = items.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});

compact.addEventListener('change', () => {
  const focused = document.activeElement;
  setOpen(false);
  if (compact.matches && menu.contains(focused)) toggle.focus();
  if (!compact.matches && focused === toggle) menu.querySelector('.view-button[aria-current="page"]')?.focus();
});
