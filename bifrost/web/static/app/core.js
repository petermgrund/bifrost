import { LitElement, html, nothing } from 'lit';

export { html, nothing };

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

export function btn(label, disabled, onClick, cls = '') {
  return html`<button class=${cls} ?disabled=${disabled} @click=${onClick}>${label}</button>`;
}
export const spinner = html`<progress class="circle small"></progress>`;

export const chip = (label, on, onClick) =>
  html`<button class="chip ${on ? 'fill' : ''}" @click=${onClick}>${label}</button>`;

export const checkbox = (checked, onChange, opts = {}) => html`
  <label class="checkbox">
    <input type="checkbox" .checked=${checked} .indeterminate=${opts.indeterminate || false}
      ?disabled=${opts.disabled || false} @change=${onChange}><span></span>
  </label>`;

const WIDTH = { small: 'small-width', medium: 'medium-width', large: 'large-width' };

export function field(label, value, onInput, opts = {}) {
  const oninput = (e) => {
    if (opts.upper) {
      const el = e.target;
      const up = el.value.toUpperCase();
      if (up !== el.value) {
        const [s, end] = [el.selectionStart, el.selectionEnd];
        el.value = up;
        el.setSelectionRange(s, end);
      }
    }
    onInput(e);
  };
  const input = opts.rows
    ? html`<textarea rows=${opts.rows} .value=${value ?? ''} @input=${oninput}></textarea>`
    : html`<input type=${opts.type || 'text'} class="${opts.mono ? 'mono' : ''}"
        .value=${value ?? ''} @input=${oninput}
        @change=${(e) => { if (opts.onChange) opts.onChange(e); }}
        @keydown=${(e) => { if (e.key === 'Enter' && opts.onEnter) opts.onEnter(e); }}>`;
  const box = html`<div class="field ${opts.helper ? '' : 'label'} fill ${opts.rows ? 'textarea' : ''}
      ${opts.small ? 'small no-margin' : ''} ${WIDTH[opts.width] || ''}">
    ${input}${opts.helper ? nothing : html`<label>${label}</label>`}</div>`;
  return opts.helper
    ? html`${box}<p class="small-text secondary-text field-helper">${label}</p>`
    : box;
}

export class BifrostElement extends LitElement {
  createRenderRoot() {
    return this;
  }
}

const ACTION_WORDS = {
  created: ['create', 'created', 'item'],
  generated: ['generate', 'generated', 'boundary', 'boundaries'],
  versions_updated: ['update', 'updated', 'version'],
  titles_updated: ['update', 'updated', 'title'],
  dates_updated: ['set', 'set', 'date'],
  descs_updated: ['update', 'updated', 'description'],
  tx_created: ['add', 'added', 'transcription'],
  tx_updated: ['rewrite', 'rewrote', 'transcription'],
  transcribed: ['transcribe', 'transcribed', 'doc'],
  pages_scaled: ['scale', 'scaled', 'page'],
  uploaded: ['upload', 'uploaded', 'new version', 'new versions'],
};
const QUIET = new Set(['skipped', 'tx_skipped', 'baselined', 'errors']);

export function summarize(counts, applied) {
  if (!counts) return '';
  const parts = [];
  for (const [key, n] of Object.entries(counts)) {
    if (!n || QUIET.has(key)) continue;
    const w = ACTION_WORDS[key];
    if (w) parts.push(`${applied ? w[1] : w[0]} ${n} ${n === 1 ? w[2] : w[3] || `${w[2]}s`}`);
  }
  const errs = counts.errors ? ` · ${counts.errors} error${counts.errors === 1 ? '' : 's'}` : '';
  if (!parts.length) return (applied ? 'No changes' : 'In sync') + errs;
  const verb = parts.join(', ');
  return verb.charAt(0).toUpperCase() + verb.slice(1) + errs;
}

/* Small inline SVG status icons — visually unambiguous (shape + color),
   unlike glyph checkmarks/dashes. Colored by BeerCSS text helpers. */
export const iconYes = html`<svg class="green-text" viewBox="0 0 16 16" width="15" height="15" aria-label="yes">
  <path d="M2.5 8.5 L6.5 12.5 L13.5 4" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
export const iconNo = html`<svg class="error-text" viewBox="0 0 16 16" width="15" height="15" aria-label="no">
  <path d="M4 4 L12 12 M12 4 L4 12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`;
/* n/a — a dash, for "not applicable" (distinct from a real failure). */
export const iconNa = html`<svg class="secondary-text" viewBox="0 0 16 16" width="15" height="15" aria-label="n/a">
  <path d="M4 8 L12 8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`;

/* The one status/result line — every job outcome and inline notice renders
   through this so success, failure, and progress always look the same.
   kind: 'ok' | 'error' | 'busy' | 'info'. Drop it inline in a control nav,
   or wrap it in <p> as a stanza's result line. */
export function statusLine(kind, msg) {
  if (!msg) return nothing;
  if (kind === 'busy') return html`<span class="secondary-text">${spinner} ${msg}</span>`;
  if (kind === 'ok') return html`<span>${iconYes} ${msg}</span>`;
  if (kind === 'error') return html`<span class="error-text">${iconNo} ${msg}</span>`;
  return html`<span class="secondary-text">${msg}</span>`;
}

/* Determinate progress for a long job: caption line + BeerCSS linear bar.
   The bar tracks the WHOLE run 0→100 (percent), while the caption shows the
   current stage's counts — one fill, no per-stage restarts. Width-capped in
   bifrost.css to match capped tables; give it a stanza line of its own, not
   a control nav (use the compact busy statusLine there instead). Falls back
   to statusLine('busy') until the run reports a total. */
export function progressLine(done, total, percent) {
  if (!total) return spinner;
  const pct = percent ?? Math.round((100 * done) / total);
  return html`<div class="bar"><div style="width:${pct}%"></div></div>`;
}

/* Empty-state row for a table body: emptyRow(colspan, 'No items…'). */
export const emptyRow = (cols, msg) =>
  html`<tr><td colspan=${cols} class="secondary-text">${msg}</td></tr>`;
