/* Shared Lit base + the Bifrost UI kit. Controls are BeerCSS (vendored in
   static/vendor/) — plain elements + classes, no web-component framework
   beyond Lit itself (docs: github.com/beercss/beercss/tree/main/docs).

   Bifrost is ONE page — a stack of <details> section expanders
   (bifrost-app.js) in the Gramps-Web settings style. Each section is a
   switchboard panel between Gramps Web and one outside service (Paperless,
   Gemini, OSM…), and every panel is built from the same materials so the
   same idea always looks the same:

   STANZA   h6.small heading (wrapped in a <nav> with right-aligned
            small-text meta when there's a count) → one-line <p> intro →
            one <nav class="wrap"> control row (field → chip → btn →
            statusLine) → data. NO <article> cards — the expander is the
            only container.
   INPUTS   field() is the only text input, including inside table cells —
            never bespoke input markup. Widths via opts.width tokens
            (small/medium/large → the BeerCSS *-width helpers); id inputs
            via opts {mono, upper}.
   BUSY     a running job disables its button, swaps the label to a gerund
            ('Applying…'), and appends `spinner` in the same row; a
            standalone wait renders statusLine('busy', …). Every submit has
            a busy guard — no double fires.
   RESULTS  every outcome renders through statusLine(): green check for
            done, red cross for failure, plain secondary text for notices —
            never bare text, never an icon-font glyph. Run counters become
            prose via summarize().
   TABLES   plain <table>, sentence-case headers, emptyRow() when nothing
            matches. Ids in .mono. Row actions are button.small with a
            gerund label while busy.
   FILTERS  chips carry their counts ('Create 12'); add an 'N shown' count
            only when a search field narrows further.
   LINKS    inline mentions are a.link (target=_blank rel=noopener); the one
            primary action after a run may be an <a class="button">.
   SPACING  BeerCSS helpers only (space, large-space, scroll [+ .capped],
            left-padding) — no inline styles beyond the bifrost.css glue.
   BUTTONS  all through btn() — one uniform filled style, no color/variant
            mixing; order conveys emphasis. Colors via text helpers
            (green-text, error-text, secondary-text). The text font is
            BeerCSS's --font (never override); mono only for ids/codes. */
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

/* ---- BeerCSS control helpers ----
   btn: the ONE button style app-wide — the default filled BeerCSS button.
   Emphasis comes from position (primary action first), never from color. */
export function btn(label, disabled, onClick) {
  return html`<button ?disabled=${disabled} @click=${onClick}>${label}</button>`;
}
export const spinner = html`<progress class="circle small"></progress>`;

export const chip = (label, on, onClick) =>
  html`<button class="chip ${on ? 'fill' : ''}" @click=${onClick}>${label}</button>`;

const WIDTH = { small: 'small-width', medium: 'medium-width', large: 'large-width' };

/* Text field: BeerCSS .field.label.fill (the filled look, per the Gramps Web
   style guide) wrapping an input (or textarea when opts.rows is set). Label
   floats; opts: {type, rows, mono, upper, width: small|medium|large, small,
   onEnter, onChange}. */
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
  return html`<div class="field label fill ${opts.rows ? 'textarea' : ''}
      ${opts.small ? 'small no-margin' : ''} ${WIDTH[opts.width] || ''}">
    ${input}<label>${label}</label></div>`;
}

/* Components render into light DOM so the global stylesheet themes them and
   existing class names keep working — no per-component style porting. */
export class BifrostElement extends LitElement {
  createRenderRoot() {
    return this;
  }
}

/* Terse one-line summary of a run's counters. No filler: only the actions
   that happened, joined plainly. [verb, past verb, noun, plural noun?]. */
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

/* Empty-state row for a table body: emptyRow(colspan, 'No items…'). */
export const emptyRow = (cols, msg) =>
  html`<tr><td colspan=${cols} class="secondary-text">${msg}</td></tr>`;
