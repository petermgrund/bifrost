import { get, qs } from './api.svelte.js';

export const store = $state({ config: null, error: '', people: null, places: null, media: null, mediaError: '' });

export async function loadMedia() {
  try {
    store.media = (await get('/media/api/list')).items;
    store.mediaError = '';
  } catch (e) {
    store.mediaError = e.message;
    store.media ??= [];
  }
}

export async function init() {
  try {
    store.config = await get('/api/config');
  } catch (e) {
    store.config = {};
    store.error = e.message;
    return;
  }
  loadMedia();
  if (!store.config.immich) return;
  get('/photos/api/people').then((p) => (store.people = p)).catch(() => (store.people = []));
  get('/photos/api/places').then((p) => (store.places = p)).catch(() => (store.places = []));
}

export async function searchAssets(q, skip = new Set()) {
  const r = await get(`/photos/api/search?${qs({ mode: 'recent', q, page: 1 })}`);
  return r.items.filter((i) => !skip.has(i.asset_id));
}

const listeners = new Set();

export function onRecord(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function recordChanged(rec, replacing = null) {
  for (const fn of listeners) fn(rec, replacing);
}
