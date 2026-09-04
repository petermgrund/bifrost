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

let runDepth = 0;
function syncing(delta) {
  runDepth = Math.max(0, runDepth + delta);
  document.body.classList.toggle('syncing', runDepth > 0);
}

export async function post(path, body) {
  let counted = false;
  const grace = setTimeout(() => { counted = true; syncing(1); }, 400);
  try {
    return await api(path, { method: 'POST', body: JSON.stringify(body || {}) });
  } finally {
    clearTimeout(grace);
    if (counted) syncing(-1);
  }
}

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
        placeholder=${opts.placeholder || nothing}
        .value=${value ?? ''} @input=${oninput}
        @change=${(e) => { if (opts.onChange) opts.onChange(e); }}
        @keydown=${(e) => { if (e.key === 'Enter' && opts.onEnter) opts.onEnter(e); }}>`;
  const box = html`<div class="field ${opts.helper ? '' : 'label'} fill ${opts.rows ? 'textarea' : ''}
      ${opts.small ? 'small no-margin' : ''} ${opts.error ? 'invalid' : ''} ${WIDTH[opts.width] || ''}">
    ${input}${opts.helper ? nothing : html`<label>${label}</label>`}
    ${opts.error ? html`<span class="error">${opts.error}</span>` : nothing}</div>`;
  return opts.helper
    ? html`${box}<p class="small-text secondary-text field-helper">${label}</p>`
    : box;
}

function searchKeys(opts) {
  return (e) => {
    if (e.key === 'Enter') { e.preventDefault(); opts.onEnter?.(e); }
    else if (e.key === 'Escape') e.target.blur();
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      opts.onMove?.(e.key === 'ArrowDown' ? 1 : -1);
    }
  };
}

function searchRows({ items, active = -1, onPick, empty = 'No matches' }) {
  const fallback = (e) => e.target.replaceWith(Object.assign(document.createElement('i'), { textContent: 'image' }));
  if (!items.length) return empty ? html`<li class="secondary-text">${empty}</li>` : nothing;
  return items.map((it, i) => html`<li class=${i === active ? 'active' : ''}
      @mousedown=${(e) => { e.preventDefault(); onPick(it); e.currentTarget.closest('menu').querySelector('input')?.blur(); document.activeElement?.blur(); }}>
      ${it.thumb ? html`<img class="circle" src=${it.thumb} alt="" @error=${fallback}>`
        : it.icon ? html`<i>${it.icon}</i>` : nothing}
      <div class="max">
        <div>${it.label}</div>
        ${it.sub ? html`<div class="small-text secondary-text ${it.mono ? 'mono' : ''}">${it.sub}</div>` : nothing}
      </div>
    </li>`);
}

export function selectField(label, value, options, onChange, opts = {}) {
  return html`<div class="field label suffix fill ${opts.small ? 'small no-margin' : ''} ${WIDTH[opts.width] || ''}">
    <select @change=${onChange}>${options.map((o) => {
    const [v, l] = Array.isArray(o) ? o : [o, o];
    return html`<option value=${v} ?selected=${String(v) === String(value)}>${l}</option>`;
  })}</select>
    <label>${label}</label><i>arrow_drop_down</i></div>`;
}

export function searchField(opts) {
  const { placeholder, value, onInput, width = '', icon = 'search' } = opts;
  return html`<div class="field prefix fill no-margin search-field ${WIDTH[width] || ''}">
    <i class="front">${icon}</i>
    <input type="text" placeholder=${placeholder} .value=${value ?? ''} autocomplete="off"
      @input=${onInput} @keydown=${searchKeys(opts)}>
    <menu class="search-results">${searchRows(opts)}</menu>
  </div>`;
}

export function searchMenu(opts) {
  const { label, icon, value, onInput, open = false, onToggle, onClose,
    placeholder = 'Search', cls = 'border' } = opts;
  const toggle = (e) => {
    const opening = !open;
    onToggle?.();
    if (!opening) return;
    const el = e.currentTarget.parentElement;
    const focusInput = () => {
      const input = el.querySelector('input');
      if (input && document.activeElement !== input) input.focus();
    };
    requestAnimationFrame(focusInput);
    for (const ms of [60, 160, 320]) setTimeout(focusInput, ms);
  };
  return html`<div class="search-menu">
    <button class=${cls} @click=${toggle}><i>${icon}</i><span>${label}</span></button>
    <menu class="search-results ${open ? 'active' : ''}">
      <li class="transparent">
        <div class="field prefix small no-margin">
          <i class="front">search</i>
          <input type="text" placeholder=${placeholder} .value=${value ?? ''} autocomplete="off"
            @input=${onInput} @keydown=${searchKeys(opts)} @blur=${() => onClose?.()}>
        </div>
      </li>
      ${searchRows(opts)}
    </menu>
  </div>`;
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
  links_updated: ['re-link', 're-linked', 'photo'],
  linked: ['link', 'linked', 'place'],
  located: ['locate', 'located', 'place'],
  tx_created: ['add', 'added', 'transcription'],
  tx_updated: ['rewrite', 'rewrote', 'transcription'],
  transcribed: ['transcribe', 'transcribed', 'doc'],
  replaced: ['replace', 'replaced', 'transcript'],
  pages_scaled: ['scale', 'scaled', 'page'],
  uploaded: ['upload', 'uploaded', 'new version', 'new versions'],
  id_tags_written: ['write', 'wrote', 'ID tag', 'ID tags'],
  faces_linked: ['link', 'linked', 'face'],
  citations_linked: ['attach', 'attached', 'citation'],
  boxes_added: ['add', 'added', 'face box', 'face boxes'],
};
const QUIET = new Set(['skipped', 'tx_skipped', 'baselined', 'errors', 'unreadable', 'unmatched', 'in_place', 'unsynced']);

export function summarize(counts, applied) {
  if (!counts) return '';
  const parts = [];
  for (const [key, n] of Object.entries(counts)) {
    if (!n || QUIET.has(key)) continue;
    const w = ACTION_WORDS[key];
    if (w) parts.push(`${applied ? w[1] : w[0]} ${n} ${n === 1 ? w[2] : w[3] || `${w[2]}s`}`);
  }
  const errs = counts.errors ? ` (${counts.errors} error${counts.errors === 1 ? '' : 's'})` : '';
  if (!parts.length) return (applied ? 'No changes' : 'In sync') + errs;
  const verb = parts.join(', ');
  return verb.charAt(0).toUpperCase() + verb.slice(1) + errs;
}

export const iconYes = html`<svg viewBox="-1 -1 42 39" width="15" height="15" aria-label="yes">
  <path d="m3,19l10,10l23,-23" fill="none" stroke="#0dba2d" stroke-width="7"/></svg>`;
export const iconNo = html`<svg class="error-text" viewBox="0 0 16 16" width="15" height="15" aria-label="no">
  <path d="M4 4 L12 12 M12 4 L4 12" fill="none" stroke="currentColor" stroke-width="2.4"/></svg>`;
export const iconNa = html`<svg class="secondary-text" viewBox="0 0 16 16" width="15" height="15" aria-label="n/a">
  <path d="M4 8 L12 8" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>`;

export function statusLine(kind, msg) {
  if (!msg) return nothing;
  if (kind === 'busy') return html`<span class="secondary-text">${spinner} ${msg}</span>`;
  if (kind === 'ok') return html`<span>${iconYes} ${msg}</span>`;
  if (kind === 'error') return html`<span class="error-text">${iconNo} ${msg}</span>`;
  return html`<span class="secondary-text">${msg}</span>`;
}

export function progressLine(p) {
  if (!p || !p.total) return spinner;
  const pct = Math.round((100 * (p.done || 0)) / p.total);
  return html`<div class="progress">
    <div class="bands"><div class="band"><div style="width:${pct}%"></div></div></div>
    <div class="band-line">
      <span class="max secondary-text">${p.detail || ''}</span>
      <span class="mono small-text">${p.done}/${p.total}</span>
    </div>
  </div>`;
}

export const emptyRow = (cols, msg) =>
  html`<tr><td colspan=${cols} class="secondary-text">${msg}</td></tr>`;
