/* Shared Lit base + helpers for Bifrost pages. UI controls are BeerCSS
   (vendored in static/vendor/) — plain elements + classes, no web-component
   framework beyond Lit itself. */
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

/* ---- BeerCSS control helpers ----
   btn keeps the old (variant, label, disabled, onClick) shape the pages
   already use: filled = default BeerCSS button, outlined = .border,
   text = .transparent. */
export function btn(variant, label, disabled, onClick) {
  const cls = variant === 'filled' ? '' : variant === 'text' ? 'transparent primary-text' : 'border';
  return html`<button class="${cls}" ?disabled=${disabled} @click=${onClick}>${label}</button>`;
}
export const spinner = html`<progress class="circle small"></progress>`;

export const chip = (label, on, onClick) =>
  html`<button class="chip ${on ? 'fill' : ''}" @click=${onClick}>${label}</button>`;

export const switchEl = (on, onChange) =>
  html`<label class="switch"><input type="checkbox" ?checked=${on}
    @change=${(e) => onChange(e.target.checked)}><span></span></label>`;

/* Text field: BeerCSS .field.label.border wrapping an input (or textarea when
   opts.rows is set). Label floats; opts: {type, rows, mono, style, onEnter}. */
export function field(label, value, onInput, opts = {}) {
  const input = opts.rows
    ? html`<textarea rows=${opts.rows} .value=${value ?? ''} @input=${onInput}></textarea>`
    : html`<input type=${opts.type || 'text'} class="${opts.mono ? 'mono' : ''}"
        .value=${value ?? ''} @input=${onInput}
        @keydown=${(e) => { if (e.key === 'Enter' && opts.onEnter) opts.onEnter(e); }}>`;
  return html`<div class="field label border ${opts.rows ? 'textarea' : ''}"
    style=${opts.style || nothing}>${input}<label>${label}</label></div>`;
}

/* Tab bar: BeerCSS .tabs. `pick` gets the tab key. */
export const tabsBar = (tabs, active, pick) =>
  html`<div class="tabs left-align">${tabs.map((t) =>
    html`<a class="${t.key === active ? 'active' : ''}" @click=${() => pick(t.key)}>${t.label}</a>`)}</div>`;

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
  tx_created: ['add', 'added', 'transcription'],
  tx_updated: ['rewrite', 'rewrote', 'transcription'],
  transcribed: ['transcribe', 'transcribed', 'document'],
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

/* Small inline SVG status icons — visually unambiguous (shape + color),
   unlike glyph checkmarks/dashes. */
export const iconYes = html`<svg class="icon yes" viewBox="0 0 16 16" width="15" height="15" aria-label="yes">
  <path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
export const iconNo = html`<svg class="icon no" viewBox="0 0 16 16" width="15" height="15" aria-label="no">
  <path d="M4 4 L12 12 M12 4 L4 12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`;
/* Third state: in-progress / pending / reserved / not-applicable — a hollow ring,
   a shape distinct from check and cross (not just a colour). */
export const iconPending = html`<svg class="icon pend" viewBox="0 0 16 16" width="15" height="15" aria-label="pending">
  <circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>`;
/* n/a — a dash, for "not applicable yet" (distinct from a real failure). */
export const iconNa = html`<svg class="icon na" viewBox="0 0 16 16" width="15" height="15" aria-label="n/a">
  <path d="M4 8 L12 8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`;
/* Half-filled ring — "partway there": used for an id that's been physically
   assigned (written on a photo) but not yet minted in Gramps. Shape sits between
   the hollow ring (reserved) and the check (minted). */
export const iconHalf = html`<svg class="icon half" viewBox="0 0 16 16" width="15" height="15" aria-label="assigned">
  <circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" stroke-width="2.2"/>
  <path d="M8 3.6 A4.4 4.4 0 0 1 8 12.4 Z" fill="currentColor"/></svg>`;

/* Map a run/status string to a shape+colour icon. ok→check, error/failed→cross,
   else (running/pending)→ring. */
export function statusIcon(status) {
  if (status === 'ok' || status === 'done') return iconYes;
  if (status === 'error' || status === 'failed' || status === 'interrupted') return iconNo;
  return iconPending;
}
