/* Shared base for the source-sync sections (today: Paperless → Gramps; an
   ArchivesSpace source will slot in here later). Flat BeerCSS content inside
   the section expander: empty → results (real /sync/api/<source>/preview
   events) → applied. Configuration lives in config.yaml, not in the UI. */
import { BifrostElement, html, nothing, api, post, summarize, btn, chip, spinner, emptyRow, statusLine } from './core.js';

export class SyncPage extends BifrostElement {
  static properties = {
    phase: { state: true },          // empty | results | applied
    running: { state: true },
    result: { state: true },         // preview payload
    applied: { state: true },        // applied payload
    filter: { state: true },
    config: { state: true },         // read-only; used for the Gramps link
    error: { state: true },
  };

  constructor() {
    super();
    this.phase = 'empty';
    this.running = false;
    this.result = null;
    this.applied = null;
    this.filter = 'all';
    this.config = null;
    this.error = '';
  }

  /* ---- subclass surface (overridden) ---- */
  get source() { return 'paperless'; }
  get itemColLabel() { return 'Item'; }

  connectedCallback() {
    super.connectedCallback();
    this.loadConfig();
  }

  async loadConfig() {
    try { this.config = await api(`/sync/api/${this.source}/config`); }
    catch { this.config = null; }
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

  async apply() {
    this.running = true; this.error = '';
    try {
      this.applied = await post(`/sync/api/${this.source}/apply`, {});
      this.phase = 'applied';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
    }
  }

  rerun() { this.phase = 'empty'; this.result = null; this.filter = 'all'; }
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

  groupOf(action) {
    if (action === 'would_create' || action === 'created') return 'create';
    if (action === 'would_update' || action === 'updated') return 'update';
    if (action === 'failed') return 'error';
    return 'skip';
  }

  render() {
    return html`
      ${this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}
      ${this.running && this.phase === 'empty' ? this.renderRunning()
        : this.phase === 'applied' ? this.renderApplied()
        : this.phase === 'results' ? this.renderResults()
        : this.renderEmpty()}`;
  }

  renderRunning() {
    return html`<p>${statusLine('busy', 'Scanning — comparing the source against your Gramps media…')}</p>`;
  }

  renderEmpty() {
    return html`
      <p>Preview what a sync would change. Nothing is written until you apply.</p>
      <nav>
        ${btn('Run preview', this.running, () => this.runPreview())}
      </nav>`;
  }

  renderResults() {
    const items = this.items;
    const c = { create: 0, update: 0, skip: 0, error: 0 };
    for (const e of items) c[this.groupOf(e.action)]++;
    const writable = c.create + c.update;
    const shown = this.filter === 'all' ? items : items.filter((e) => this.groupOf(e.action) === this.filter);

    return html`
      <p>${writable} change${writable === 1 ? '' : 's'} ready · ${c.skip} skipped${c.error ? ` · ${c.error} failed` : ''}. Nothing is written until you apply.</p>

      <nav class="wrap">
        ${chip(`All ${items.length}`, this.filter === 'all', () => { this.filter = 'all'; })}
        ${chip(`Create ${c.create}`, this.filter === 'create', () => { this.filter = 'create'; })}
        ${chip(`Update ${c.update}`, this.filter === 'update', () => { this.filter = 'update'; })}
        ${chip(`Skip ${c.skip}`, this.filter === 'skip', () => { this.filter = 'skip'; })}
        ${c.error ? chip(`Failed ${c.error}`, this.filter === 'error', () => { this.filter = 'error'; }) : nothing}
      </nav>

      <table>
        <thead><tr>
          <th>Action</th>
          <th>${this.itemColLabel}</th>
          <th>Media object</th>
          <th>Detail</th>
        </tr></thead>
        <tbody>
          ${shown.length ? shown.map((e) => this.row(e)) : emptyRow(4, 'No items in this filter.')}
        </tbody>
      </table>

      <div class="large-space"></div>
      <nav>
        ${btn(this.running ? 'Applying…' : `Apply ${writable} change${writable === 1 ? '' : 's'}`,
          this.running || !writable, () => this.apply())}
        ${btn('Re-run preview', this.running, () => this.rerun())}
        ${btn('Export preview', false, () => this.exportPreview())}
        ${this.running ? spinner : nothing}
      </nav>`;
  }

  row(e) {
    const g = this.groupOf(e.action);
    const CHIP = { create: ['green', 'Create'], update: ['primary-container', 'Update'],
      skip: ['', 'Skip'], error: ['error', 'Failed'] }[g];
    return html`<tr>
      <td><span class="chip small ${CHIP[0]}">${CHIP[1]}</span></td>
      <td>${e.title || e.source_id || '—'}</td>
      <td><span class="mono small-text">${e.gramps_id || '—'}</span></td>
      <td class="small-text">${e.detail || ''}</td>
    </tr>`;
  }

  renderApplied() {
    const summary = summarize(this.applied?.events?.find((e) => e.kind === 'summary')?.data, true);
    return html`
      <p>${statusLine('ok', `Applied to Gramps — ${summary || 'done.'}`)}</p>
      <nav>
        ${this.config?.gramps_public_url ? html`<a class="button"
          href=${this.config.gramps_public_url} target="_blank" rel="noopener">Open in Gramps Web</a>` : nothing}
        ${btn('Run another preview', false, () => this.runAnother())}
      </nav>`;
  }
}
