/* Shared Lit base + helpers for Bifrost pages. */
import { LitElement, html, css, nothing } from 'lit';

export { html, css, nothing };

export async function api(path, opts = {}) {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
}

export const post = (path, body) =>
  api(path, { method: 'POST', body: JSON.stringify(body || {}) });

/* Components render into light DOM so the global stylesheet themes them and
   existing class names keep working — no per-component style porting. */
export class BifrostElement extends LitElement {
  createRenderRoot() {
    return this;
  }
}

/* Terse one-line summary of a sync run's counters. No filler: only the
   actions that happened, joined plainly. */
const ACTION_WORDS = {
  created: ['create', 'created', 'item'],
  versions_updated: ['update', 'updated', 'version'],
  titles_updated: ['update', 'updated', 'title'],
  dates_updated: ['set', 'set', 'date'],
  descs_updated: ['update', 'updated', 'description'],
  faces_linked: ['link', 'linked', 'face'],
  places_linked: ['link', 'linked', 'place'],
  tx_created: ['add', 'added', 'transcription'],
  tx_updated: ['rewrite', 'rewrote', 'transcription'],
};
const QUIET = new Set(['skipped', 'tx_skipped', 'baselined', 'errors']);

export function summarize(counts, applied) {
  if (!counts) return '';
  const parts = [];
  for (const [key, n] of Object.entries(counts)) {
    if (!n || QUIET.has(key)) continue;
    const w = ACTION_WORDS[key];
    if (w) parts.push(`${applied ? w[1] : w[0]} ${n} ${w[2]}${n === 1 ? '' : 's'}`);
  }
  const errs = counts.errors ? ` · ${counts.errors} error${counts.errors === 1 ? '' : 's'}` : '';
  if (!parts.length) return (applied ? 'No changes' : 'In sync') + errs;
  const verb = parts.join(', ');
  return verb.charAt(0).toUpperCase() + verb.slice(1) + errs;
}

export const hasWork = (counts) =>
  counts && Object.entries(counts).some(([k, v]) => !QUIET.has(k) && v > 0);
