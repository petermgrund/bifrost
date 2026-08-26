import ui from '/static/vendor/beer.min.js';

export const SEED_KEY = 'bifrost-theme-seed';
export const DEFAULT_KEY = 'bifrost-theme-default';

export function cacheSeed(seed, fallback) {
  try {
    localStorage.setItem(SEED_KEY, seed);
    localStorage.setItem(DEFAULT_KEY, fallback);
  } catch { }
}

export async function applySeed(seed, fallback) {
  if (!seed || seed === fallback) {
    document.body.removeAttribute('style');
    return;
  }
  await ui('theme', seed);
  ui('mode', document.body.classList.contains('dark') ? 'dark' : 'light');
}

function cached() {
  return [localStorage.getItem(SEED_KEY), localStorage.getItem(DEFAULT_KEY)];
}

window.__bifrostReapplyTheme = () => {
  const [seed, fallback] = cached();
  applySeed(seed, fallback);
};

(async () => {
  const [seed, fallback] = cached();
  if (seed) applySeed(seed, fallback);
  try {
    const r = await fetch('/config/api/theme').then((x) => x.json());
    cacheSeed(r.seed, r.default);
    if (r.seed !== seed) await applySeed(r.seed, r.default);
  } catch {
  }
})();
