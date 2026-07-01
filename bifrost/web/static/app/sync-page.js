/* Shared base for the source-sync pages (today: Paperless → Gramps; an
   ArchivesSpace source will slot in here later). BeerCSS markup throughout.

   Tabs: Preview · History · Settings.
   Preview: empty → results (real /sync/api/<source>/preview events) → applied.
   History: intentionally empty for now.
   Settings: accordion populated from /sync/api/<source>/config (read-only wiring).

   Subclasses supply the source name, copy, the empty-state icon, and the
   Settings sections. */
import { BifrostElement, html, nothing, api, post, summarize, tabsBar, chip, switchEl, field, spinner } from './core.js';

// Same safe alphabet the id generator and backend enforce for manual ids.
const MANUAL_RE = /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/;
const TABS = [
  { key: 'preview', label: 'Preview' },
  { key: 'history', label: 'History' },
  { key: 'settings', label: 'Settings' },
];

/* ---- small inline icons (stroke, currentColor) ---- */
export const icon = (inner, size = 18, sw = 2) => html`<svg width=${size} height=${size}
  viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width=${sw}
  stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
export const playIcon = icon(html`<path d="m6 4 14 8-14 8z"/>`, 18);
const checkCircle = html`<svg width="28" height="28" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/></svg>`;

export class SyncPage extends BifrostElement {
  static properties = {
    tab: { state: true },
    phase: { state: true },          // empty | results | applied
    running: { state: true },
    result: { state: true },         // preview payload
    applied: { state: true },        // applied payload
    filter: { state: true },
    manualMode: { state: true },
    ui: { state: true },             // misc settings toggles/segments
    config: { state: true },
    error: { state: true },
  };

  constructor() {
    super();
    this.tab = 'preview';
    this.phase = 'empty';
    this.running = false;
    this.result = null;
    this.applied = null;
    this.filter = 'all';
    this.manualMode = false;
    this.ui = {};
    this.config = null;
    this.error = '';
  }

  /* ---- subclass surface (overridden) ---- */
  get source() { return 'paperless'; }
  get heading() { return ''; }
  get sub() { return ''; }
  get itemColLabel() { return 'Item'; }
  get emptyTags() { return html``; }
  get emptyIcon() { return nothing; }
  captionFor(tab) { return ''; }
  settingsSections(/* config */) { return []; }

  connectedCallback() {
    super.connectedCallback();
    this.loadConfig();
  }

  async loadConfig() {
    try { this.config = await api(`/sync/api/${this.source}/config`); }
    catch (e) { this.config = { _error: e.message }; }
  }

  /* ---- preview / apply ---- */
  async runPreview() {
    this.running = true; this.error = ''; this.applied = null;
    try {
      this.result = await post(`/sync/api/${this.source}/preview`, {});
      this.phase = 'results';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
    }
  }

  collectManualIds() {
    const out = {};
    for (const el of this.renderRoot.querySelectorAll('input.idinput')) {
      const v = el.value.trim();
      if (v) out[el.dataset.sid] = v;
    }
    return out;
  }

  async apply() {
    this.running = true; this.error = '';
    try {
      const body = this.manualMode ? { manual_ids: this.collectManualIds() } : {};
      this.applied = await post(`/sync/api/${this.source}/apply`, body);
      this.phase = 'applied';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
    }
  }

  rerun() { this.phase = 'empty'; this.result = null; this.filter = 'all'; this.manualMode = false; }
  runAnother() { this.applied = null; this.rerun(); }

  exportPreview() {
    if (!this.result) return;
    const blob = new Blob([JSON.stringify(this.result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${this.source}-preview.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ---- derive rows from preview events ---- */
  get items() { return (this.result?.events || []).filter((e) => e.kind === 'item'); }
  get counts() { return (this.result?.events || []).find((e) => e.kind === 'summary')?.data || {}; }

  groupOf(action) {
    if (action === 'would_create' || action === 'created') return 'create';
    if (action === 'would_update' || action === 'updated') return 'update';
    if (action === 'failed') return 'error';
    return 'skip';
  }

  render() {
    return html`
      <h5>${this.heading}</h5>
      <p class="hint">${this.sub}</p>

      ${tabsBar(TABS, this.tab, (t) => { this.tab = t; })}
      <p class="hint">${this.captionFor(this.tab)}</p>

      ${this.error ? html`<article class="border error-text">${this.error}</article>` : nothing}

      ${this.tab === 'preview' ? this.renderPreview()
        : this.tab === 'history' ? this.renderHistory()
        : this.renderSettings()}`;
  }

  /* ---- PREVIEW ---- */
  renderPreview() {
    if (this.running && this.phase === 'empty') return this.renderRunning('Scanning…');
    if (this.phase === 'applied') return this.renderApplied();
    if (this.phase === 'results') return this.renderResults();
    return this.renderEmpty();
  }

  renderRunning(label) {
    return html`<article class="border center-align large-padding">
      <progress class="circle"></progress>
      <h6>${label}</h6>
      <p class="hint">Comparing the source against your Gramps media.</p>
    </article>`;
  }

  renderEmpty() {
    return html`<article class="border">
      <h6>Dry-run preview</h6>
      <p class="hint">See exactly which items would become Gramps media before anything is written.</p>
      <div class="center-align large-padding">
        ${this.emptyIcon}
        <p><b>No preview yet</b></p>
        <p class="hint">${this.emptyTags}</p>
        <button ?disabled=${this.running} @click=${() => this.runPreview()}>
          ${playIcon}<span>Run preview</span></button>
      </div>
    </article>`;
  }

  renderResults() {
    const items = this.items;
    const c = { create: 0, update: 0, skip: 0, error: 0 };
    for (const e of items) c[this.groupOf(e.action)]++;
    const writable = c.create + c.update;
    const shown = this.filter === 'all' ? items : items.filter((e) => this.groupOf(e.action) === this.filter);

    return html`<article class="border">
      <h6>Dry-run preview</h6>
      <p class="hint">Nothing is written until you apply.</p>

      <div class="row wrap">
        ${chip(`All ${items.length}`, this.filter === 'all', () => { this.filter = 'all'; })}
        ${chip(`Create ${c.create}`, this.filter === 'create', () => { this.filter = 'create'; })}
        ${chip(`Update ${c.update}`, this.filter === 'update', () => { this.filter = 'update'; })}
        ${chip(`Skip ${c.skip}`, this.filter === 'skip', () => { this.filter = 'skip'; })}
        ${c.error ? chip(`Failed ${c.error}`, this.filter === 'error', () => { this.filter = 'error'; }) : nothing}
      </div>

      <table class="stripes">
        <thead><tr>
          <th style="width:104px">Action</th>
          <th>${this.itemColLabel}</th>
          <th style="width:220px">Media object</th>
          <th style="width:200px">Detail</th>
        </tr></thead>
        <tbody>
          ${shown.length ? shown.map((e) => this.row(e)) : html`<tr><td colspan="4" class="hint">No items in this filter.</td></tr>`}
        </tbody>
      </table>

      <p class="hint">${writable} change${writable === 1 ? '' : 's'} ready · ${c.skip} skipped${c.error ? ` · ${c.error} failed` : ''}.</p>

      <div class="row">
        <div class="max">
          <b>Manual ID assignment</b>
          <div class="hint">${this.manualMode
            ? 'Type a 6-char id (safe alphabet) for any new item; blanks get an auto id.'
            : 'New media get an auto-generated random-6 id.'}</div>
        </div>
        ${switchEl(this.manualMode, (on) => { this.manualMode = on; })}
      </div>

      <div class="row">
        <button ?disabled=${this.running || !writable}
          @click=${() => this.apply()}>${this.running ? 'Applying…' : `Apply ${writable} change${writable === 1 ? '' : 's'}`}</button>
        <button class="border" ?disabled=${this.running} @click=${() => this.rerun()}>Re-run preview</button>
        <button class="transparent primary-text" @click=${() => this.exportPreview()}>Export preview</button>
      </div>
    </article>`;
  }

  row(e) {
    const g = this.groupOf(e.action);
    const PILL = { create: ['pill--create', 'Create'], update: ['pill--update', 'Update'],
      skip: ['pill--skip', 'Skip'], error: ['pill--error', 'Failed'] }[g];
    const canManual = this.manualMode && g === 'create' && e.source_id;
    return html`<tr>
      <td><span class="pill ${PILL[0]}">${PILL[1]}</span></td>
      <td>${e.title || e.source_id || '—'}</td>
      <td class="hint">${canManual ? html`<input class="idinput mono" type="text" maxlength="6"
            placeholder="auto" spellcheck="false" data-sid=${e.source_id}
            @input=${(ev) => {
              const v = ev.target.value.toUpperCase(); ev.target.value = v;
              ev.target.classList.toggle('invalid', !!v && !MANUAL_RE.test(v));
            }}>`
        : (e.gramps_id || '—')}</td>
      <td class="hint">${e.detail || ''}</td>
    </tr>`;
  }

  renderApplied() {
    const summary = summarize(this.applied?.events?.find((e) => e.kind === 'summary')?.data, true);
    return html`<article class="border">
      <div class="row top-align">
        <span class="action-created">${checkCircle}</span>
        <div class="max">
          <h6>Applied to Gramps</h6>
          <p class="hint">${summary || 'Done.'}</p>
          <div class="row">
            ${this.config?.gramps_public_url ? html`<a class="button border"
              href=${this.config.gramps_public_url} target="_blank" rel="noopener">Open in Gramps Web</a>` : nothing}
            <button class="transparent primary-text" @click=${() => this.runAnother()}>Run another preview</button>
          </div>
        </div>
      </div>
    </article>`;
  }

  /* ---- HISTORY (intentionally empty for now) ---- */
  renderHistory() {
    return html`<article class="border">
      <h6>Recent runs</h6>
      <p class="hint">Every ${this.heading} run, newest first.</p>
      <div class="center-align large-padding">
        ${icon(html`<path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/>`, 34, 1.5)}
        <p><b>No history yet</b></p>
        <p class="hint">Run history will appear here once it's wired up.</p>
      </div>
    </article>`;
  }

  /* ---- SETTINGS (accordion populated from config) ---- */
  renderSettings() {
    if (!this.config) return html`<article class="border"><p class="hint">Loading settings…</p></article>`;
    if (this.config._error) return html`<article class="border error-text">
      Couldn't load settings: ${this.config._error}</article>`;
    return html`${this.settingsSections(this.config).map((s) => html`
      <details class="border round">
        <summary class="padding">
          <b>${s.title}</b>
          <div class="hint">${s.desc}</div>
        </summary>
        <div class="padding">${s.body}</div>
      </details>`)}`;
  }

  /* ---- settings helpers for subclasses ---- */
  uiGet(key, def) { return this.ui[key] === undefined ? def : this.ui[key]; }
  setUi(key, val) { this.ui = { ...this.ui, [key]: val }; }

  field(label, value, opts = {}) {
    return field(label, value, () => {}, { style: opts.max ? `max-width:${opts.max}` : '', mono: opts.mono });
  }

  switchRow(title, desc, key, on) {
    return html`<div class="row">
      <div class="max">
        <b>${title}</b>
        <div class="hint">${desc}</div>
      </div>
      ${switchEl(this.uiGet(key, on), (v) => this.setUi(key, v))}
    </div>`;
  }

  idModeSegment(key = 'idMode') {
    const mine = this.uiGet(key, false);
    return html`<div class="row">
      ${chip('Random-6 (auto)', !mine, () => this.setUi(key, false))}
      ${chip('Pre-assigned random-6', mine, () => this.setUi(key, true))}
    </div>`;
  }
}
