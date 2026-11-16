import { onDestroy } from 'svelte';

export async function goto(url) {
  window.location.assign(url);
}

export function afterNavigate(fn) {
  const handler = () => fn({});
  window.addEventListener('hashchange', handler);
  onDestroy(() => window.removeEventListener('hashchange', handler));
}

export function beforeNavigate() {}
