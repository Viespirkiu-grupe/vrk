const root = document.documentElement;
const toggle = document.getElementById('themeToggle');
const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
let preference = null;
try { preference = localStorage.getItem('vrk-theme'); } catch { /* storage is optional */ }

function applyTheme() {
  const dark = preference ? preference === 'dark' : systemTheme.matches;
  root.dataset.theme = dark ? 'dark' : 'light';
  toggle?.setAttribute('aria-pressed', String(dark));
  toggle?.setAttribute('title', dark ? 'Įjungti šviesią temą' : 'Įjungti tamsią temą');
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#0c0a09' : '#fafaf9');
}

applyTheme();
systemTheme.addEventListener('change', applyTheme);
toggle?.addEventListener('click', () => {
  preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('vrk-theme', preference); } catch { /* storage is optional */ }
  applyTheme();
});

// A keyboard skip is local focus movement, not a person hash route.
document.querySelector('.skip-link')?.addEventListener('click', event => {
  event.preventDefault();
  document.getElementById('workspace')?.focus();
});
