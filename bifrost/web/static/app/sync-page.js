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

  startProgress(job) {
    this._progressTimer = setInterval(async () => {
      try {
        const { runs } = await api('/api/runs/active');
        this.progress = runs.find((r) => r.job === job) || null;
      } catch { /*  just leaves the spinner */ }
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

  async runPreview() {
    this.running = true; this.error = ''; this.applied = null;
    this.startProgress(`sync.${this.source}.preview`);
    try {
      this.result = await post(`/sync/api/${this.source}/preview`, {});
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
      setTimeout(() => window.location.reload(), 2000);
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
      this.stopProgress();
    }
  }

  cancel() { this.phase = 'empty'; this.result = null; this.filter = 'all'; this.selected = new Set(); }
  runAnother() { this.applied = null; this.cancel(); }

  get items() { return (this.result?.events || []).filter((e) => e.kind === 'item'); }

  groupOf(action) {
    if (action === 'would_create' || action === 'created') return 'create';
    if (action === 'would_update' || action === 'updated') return 'update';
    if (action === 'failed') return 'error';
    return 'skip';
  }

  keyOf(e) { return `${e.entity}:${e.source_id}`; }
  isActionable(e) { const g = this.groupOf(e.action); return g === 'create' || g === 'update'; }

  get rows() {
    const out = [];
    const byDoc = new Map();
    for (const e of this.items) {
      if (!this.isActionable(e)) {
        out.push({ group: this.groupOf(e.action), keys: [], title: e.title || e.source_id,
                   gramps_id: e.gramps_id, cols: e.data?.cols || {}, detail: e.detail || '' });
        continue;
      }
      let r = byDoc.get(e.source_id);
      if (!r) {
        r = { group: 'update', keys: [], title: e.title || e.source_id,
              gramps_id: e.gramps_id, cols: {}, detail: '' };
        byDoc.set(e.source_id, r);
        out.push(r);
      }
      if (e.entity === 'doc' && this.groupOf(e.action) === 'create') r.group = 'create';
      r.keys.push(this.keyOf(e));
      Object.assign(r.cols, e.data?.cols);
      if (e.gramps_id) r.gramps_id = e.gramps_id;
      if (e.detail) r.detail = r.detail ? `${r.detail}; ${e.detail}` : e.detail;
    }
    return out;
  }

  rowOn(r) { return r.keys.length > 0 && r.keys.every((k) => this.selected.has(k)); }

  toggleRow(r) {
    if (this.running) return;
    const s = new Set(this.selected);
    const on = this.rowOn(r);
    for (const k of r.keys) on ? s.delete(k) : s.add(k);
    this.selected = s;
  }

  toggleShown(rows, on) {
    if (this.running) return;
    const s = new Set(this.selected);
    for (const r of rows) for (const k of r.keys) on ? s.add(k) : s.delete(k);
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
    return html`<p>${progressLine(p?.done || 0, p?.total, p?.percent)}</p>`;
  }

  renderEmpty() {
    return html`
      <h6 class="small">Scan Paperless for new or changed objects</h6>
      <nav>
        ${btn('Scan', this.running, () => this.runPreview())}
      </nav>`;
  }

  renderResults() {
    const rows = this.rows;
    const c = { create: 0, update: 0, skip: 0, error: 0 };
    for (const r of rows) c[r.group]++;
    const shown = this.filter === 'all' ? rows : rows.filter((r) => r.group === this.filter);
    const selectable = shown.filter((r) => r.keys.length);
    const onCount = selectable.filter((r) => this.rowOn(r)).length;
    const allOn = selectable.length > 0 && onCount === selectable.length;
    const nSel = rows.filter((r) => this.rowOn(r)).length;

    return html`
      <nav class="wrap">
        ${chip(`All ${rows.length}`, this.filter === 'all', () => { this.filter = 'all'; })}
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
            ${shown.length ? shown.map((r) => this.row(r)) : emptyRow(4, 'No items')}
          </tbody>
        </table>
      </div>

      <div class="large-space"></div>
      <nav>
        ${btn(this.running ? 'Applying...' : `Apply ${nSel} change${nSel === 1 ? '' : 's'}`,
          this.running || !nSel, () => this.apply())}
        ${btn('Cancel', this.running, () => this.cancel(), 'error')}
        ${this.running ? progressLine(this.progress?.done || 0, this.progress?.total, this.progress?.percent) : nothing}
      </nav>`;
  }

  placeTip(ev) {
    const tip = ev.currentTarget.querySelector('.tooltip');
    if (!tip) return;
    const chip = ev.currentTarget.getBoundingClientRect();
    const top = Math.min(Math.max(chip.top + chip.height / 2 - tip.offsetHeight / 2, 8),
      window.innerHeight - tip.offsetHeight - 8);
    tip.style.top = `${top}px`;
    tip.style.left = `${Math.min(chip.right + 8, window.innerWidth - tip.offsetWidth - 8)}px`;
  }

  row(r) {
    const CHIP = { create: ['green', 'Create'], update: ['primary-container', 'Update'],
      skip: ['', 'Skip'], error: ['error', 'Failed'] }[r.group];
    const tip = Object.entries(r.cols).map(([k, v]) => `${k}: ${v}`);
    if (r.detail) tip.push(r.detail);
    return html`<tr>
      <td>${r.keys.length
        ? checkbox(this.rowOn(r), () => this.toggleRow(r), { disabled: this.running })
        : nothing}</td>
      <td><span class="chip small ${CHIP[0]}" @pointerenter=${this.placeTip}>${CHIP[1]}
        ${tip.length ? html`<div class="tooltip no-space max">
          ${tip.map((t) => html`<div>${t}</div>`)}</div>` : nothing}
      </span></td>
      <td>${r.title || '—'}</td>
      <td>${r.gramps_id || '—'}</td>
    </tr>`;
  }

  renderApplied() {
    const summary = summarize(this.applied?.events?.find((e) => e.kind === 'summary')?.data, true);
    return html`
      <p>${statusLine('ok', `${summary || 'done.'}`)}</p>
      <nav>
        ${this.config?.gramps_public_url ? html`<a class="button"
          href=${this.config.gramps_public_url} target="_blank" rel="noopener">Open</a>` : nothing}
        ${btn('Run another preview', false, () => this.runAnother())}
      </nav>`;
  }
}
