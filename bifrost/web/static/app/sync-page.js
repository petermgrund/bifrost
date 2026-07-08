/* Shared base for the source-sync sections (today: Paperless → Gramps; an
   ArchivesSpace source will slot in here later). Flat BeerCSS content inside
   the section expander: empty → results (real /sync/api/<source>/preview
   events) → applied. Configuration lives in config.yaml, not in the UI. */
import { BifrostElement, html, nothing, api, post, summarize, btn, chip, checkbox, spinner, emptyRow, statusLine, progressLine } from './core.js';

export class SyncPage extends BifrostElement {
  static properties = {
    phase: { state: true },          // empty | results | applied
    running: { state: true },
    progress: { state: true },       // live {detail, done, total} while running
    result: { state: true },         // preview payload
    selected: { state: true },       // Set of "entity:source_id" row keys to apply
    applied: { state: true },        // applied payload
    filter: { state: true },
    config: { state: true },         // read-only; used for the Gramps link
    error: { state: true },
  };

  constructor() {
    super();
    this.phase = 'empty';
    this.running = false;
    this.progress = null;
    this.result = null;
    this.selected = new Set();
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

  disconnectedCallback() {
    super.disconnectedCallback();
    this.stopProgress();
  }

  /* ---- live progress: poll the run registry while a POST is in flight ---- */
  startProgress(job) {
    this._progressTimer = setInterval(async () => {
      try {
        const { runs } = await api('/api/runs/active');
        this.progress = runs.find((r) => r.job === job) || null;
      } catch { /* a missed poll just leaves the plain spinner */ }
    }, 750);
  }

  stopProgress() {
    clearInterval(this._progressTimer);
    this._progressTimer = null;
    this.progress = null;
  }

  async loadConfig() {
    try { this.config = await api(`/sync/api/${this.source}/config`); }
    catch { this.config = null; }
  }

  /* ---- preview / apply ---- */
  async runPreview() {
    this.running = true; this.error = ''; this.applied = null;
    this.startProgress(`sync.${this.source}.preview`);
    try {
      this.result = await post(`/sync/api/${this.source}/preview`, {});
      // everything ticked by default; failed rows aren't applicable
      this.selected = new Set(this.items.filter((e) => this.isActionable(e)).map((e) => this.keyOf(e)));
      this.phase = 'results';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
      this.stopProgress();
    }
  }

  async apply() {
    this.running = true; this.error = '';
    this.startProgress(`sync.${this.source}`);
    try {
      this.applied = await post(`/sync/api/${this.source}/apply`, { selected: [...this.selected] });
      this.phase = 'applied';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
      this.stopProgress();
    }
  }

  /* Cancel discards the preview and returns to the empty state — the run
     itself already finished server-side (preview is one blocking POST). */
  cancel() { this.phase = 'empty'; this.result = null; this.filter = 'all'; this.selected = new Set(); }
  runAnother() { this.applied = null; this.cancel(); }

  /* ---- derive rows from preview events ---- */
  get items() { return (this.result?.events || []).filter((e) => e.kind === 'item'); }

  groupOf(action) {
    if (action === 'would_create' || action === 'created') return 'create';
    if (action === 'would_update' || action === 'updated') return 'update';
    if (action === 'failed') return 'error';
    return 'skip';
  }

  /* ---- row selection (applied rows are chosen individually) ---- */
  keyOf(e) { return `${e.entity}:${e.source_id}`; }
  isActionable(e) { const g = this.groupOf(e.action); return g === 'create' || g === 'update'; }

  toggleRow(key) {
    if (this.running) return;
    const s = new Set(this.selected);
    s.has(key) ? s.delete(key) : s.add(key);
    this.selected = s;
  }

  toggleShown(rows, on) {
    if (this.running) return;
    const s = new Set(this.selected);
    for (const r of rows) on ? s.add(this.keyOf(r)) : s.delete(this.keyOf(r));
    this.selected = s;
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
    const p = this.progress;
    return html`<p>${progressLine(p?.detail || 'Scanning...', p?.done || 0, p?.total, p?.percent)}</p>`;
  }

  renderEmpty() {
    return html`
      <nav>
        ${btn('Run', this.running, () => this.runPreview())}
      </nav>`;
  }

  renderResults() {
    const items = this.items;
    const c = { create: 0, update: 0, skip: 0, error: 0 };
    for (const e of items) c[this.groupOf(e.action)]++;
    const shown = this.filter === 'all' ? items : items.filter((e) => this.groupOf(e.action) === this.filter);
    const selectable = shown.filter((e) => this.isActionable(e));
    const onCount = selectable.filter((e) => this.selected.has(this.keyOf(e))).length;
    const allOn = selectable.length > 0 && onCount === selectable.length;
    const nSel = this.selected.size;

    return html`
      <nav class="wrap">
        ${chip(`All ${items.length}`, this.filter === 'all', () => { this.filter = 'all'; })}
        ${chip(`Create ${c.create}`, this.filter === 'create', () => { this.filter = 'create'; })}
        ${chip(`Update ${c.update}`, this.filter === 'update', () => { this.filter = 'update'; })}
        ${c.error ? chip(`Failed ${c.error}`, this.filter === 'error', () => { this.filter = 'error'; }) : nothing}
      </nav>

      <div class="scroll capped capped-width">
        <table>
          <thead><tr>
            <th>${checkbox(allOn, () => this.toggleShown(selectable, !allOn),
              { indeterminate: onCount > 0 && !allOn, disabled: this.running })}</th>
            <th>Action</th>
            <th>${this.itemColLabel}</th>
            <th>Media object</th>
          </tr></thead>
          <tbody>
            ${shown.length ? shown.map((e) => this.row(e)) : emptyRow(4, 'No items')}
          </tbody>
        </table>
      </div>

      <div class="large-space"></div>
      <nav>
        ${btn(this.running ? 'Applying…' : `Apply ${nSel} change${nSel === 1 ? '' : 's'}`,
          this.running || !nSel, () => this.apply())}
        ${btn('Cancel', this.running, () => this.cancel(), 'error')}
        ${this.running ? (this.progress?.total
          ? statusLine('busy', `${this.progress.detail} · ${this.progress.done} of ${this.progress.total}`)
          : spinner) : nothing}
      </nav>`;
  }

  row(e) {
    const g = this.groupOf(e.action);
    const CHIP = { create: ['green', 'Create'], update: ['primary-container', 'Update'],
      skip: ['', 'Skip'], error: ['error', 'Failed'] }[g];
    // What the change IS lives in the event's cols (+ detail for failures);
    // surfaced as a hover tooltip on the chip. .right keeps it inside the
    // capped scroll container, which clips a top-positioned tooltip.
    const tip = Object.entries(e.data?.cols || {}).map(([k, v]) => `${k}: ${v}`);
    if (e.detail) tip.push(e.detail);
    const key = this.keyOf(e);
    return html`<tr>
      <td>${this.isActionable(e)
        ? checkbox(this.selected.has(key), () => this.toggleRow(key), { disabled: this.running })
        : nothing}</td>
      <td><span class="chip small ${CHIP[0]}">${CHIP[1]}
        ${tip.length ? html`<div class="tooltip right max">
          ${tip.map((t) => html`<div>${t}</div>`)}</div>` : nothing}
      </span></td>
      <td>${e.title || e.source_id || '—'}</td>
      <td>${e.gramps_id || '—'}</td>
    </tr>`;
  }

  renderApplied() {
    const summary = summarize(this.applied?.events?.find((e) => e.kind === 'summary')?.data, true);
    return html`
      <p>${statusLine('ok', `${summary || 'done.'}`)}</p>
      <nav>
        ${this.config?.gramps_public_url ? html`<a class="button"
          href=${this.config.gramps_public_url} target="_blank" rel="noopener">Open in Gramps</a>` : nothing}
        ${btn('Run another preview', false, () => this.runAnother())}
      </nav>`;
  }
}
