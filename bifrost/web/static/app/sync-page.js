import { BifrostElement, html, nothing, api, post, summarize, btn, chip, checkbox, spinner, emptyRow, statusLine, progressLine } from './core.js';

const PAGE_SIZE = 10;

export class SyncPage extends BifrostElement {
  static properties = {
    phase: { state: true },
    running: { state: true },
    progress: { state: true },
    result: { state: true },
    selected: { state: true },
    applied: { state: true },
    filter: { state: true },
    page: { state: true },
    config: { state: true },
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
    this.page = 0;
    this.config = null;
    this.error = '';
  }

  get source() { return 'paperless'; }
  get apiBase() { return `/sync/api/${this.source}`; }
  get jobName() { return `sync.${this.source}`; }
  get itemColLabel() { return 'Item'; }
  get lastColLabel() { return 'Media object'; }
  get scanHeading() { return 'Scan Paperless for new or changed objects'; }
  get primaryEntity() { return 'doc'; }
  lastCol(r) { return r.gramps_id || ' '; }
  applyBody() { return { selected: [...this.selected] }; }
  renderApplyExtras() { return nothing; }

  connectedCallback() {
    super.connectedCallback();
    this.loadConfig();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.stopProgress();
  }

  startProgress(job) {
    this._runId = null;
    this._progressTimer = setInterval(async () => {
      try {
        const { runs } = await api('/api/runs/active');
        const mine = runs.filter((r) => r.job === job);
        if (this._runId === null && mine.length) {
          this._runId = Math.max(...mine.map((r) => r.run_id));
        }
        this.progress = mine.find((r) => r.run_id === this._runId) || null;
      } catch { }
    }, 750);
  }

  stopProgress() {
    clearInterval(this._progressTimer);
    this._progressTimer = null;
    this._runId = null;
    this.progress = null;
  }

  async loadConfig() {
    try { this.config = await api(`${this.apiBase}/config`); }
    catch { this.config = null; }
  }

  async runPreview() {
    this.running = true; this.error = ''; this.applied = null;
    this.startProgress(`${this.jobName}.preview`);
    try {
      this.result = await post(`${this.apiBase}/preview`, {});
      this.selected = new Set(this.items.filter((e) => this.isActionable(e)).map((e) => this.keyOf(e)));
      this.page = 0;
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
    this.startProgress(this.jobName);
    try {
      this.applied = await post(`${this.apiBase}/apply`, this.applyBody());
      const summary = this.applied.events?.find((e) => e.kind === 'summary')?.data || {};
      if (summary.errors) this.phase = 'applied';
      else this.runAnother();
    } catch (e) {
      this.error = e.message;
    } finally {
      this.running = false;
      this.stopProgress();
    }
  }

  cancel() { this.phase = 'empty'; this.result = null; this.filter = 'all'; this.page = 0; this.selected = new Set(); }
  setFilter(f) { this.filter = f; this.page = 0; }
  runAnother() { this.applied = null; this.cancel(); }

  get items() { return (this.result?.events || []).filter((e) => e.kind === 'item'); }
  get scanErrors() { return (this.result?.events || []).filter((e) => e.kind === 'error'); }

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
                   gramps_id: e.gramps_id, cols: e.data?.cols || {}, detail: e.detail || '',
                   data: e.data || {} });
        continue;
      }
      let r = byDoc.get(e.source_id);
      if (!r) {
        r = { group: 'update', keys: [], title: e.title || e.source_id,
              gramps_id: e.gramps_id, cols: {}, detail: '', data: {} };
        byDoc.set(e.source_id, r);
        out.push(r);
      }
      if (e.entity === this.primaryEntity && this.groupOf(e.action) === 'create') r.group = 'create';
      r.keys.push(this.keyOf(e));
      Object.assign(r.cols, e.data?.cols);
      r.data = { ...r.data, ...(e.data || {}) };
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
      ${this.phase === 'applied' ? this.renderApplied()
        : this.phase === 'results' ? this.renderResults()
        : this.renderEmpty()}`;
  }

  renderEmpty() {
    if (this.config && this.config.enabled === false) {
      return html`
        <h6 class="small">${this.scanHeading}</h6>
        <p class="secondary-text">Sync is disabled</p>`;
    }
    const p = this.progress;
    return html`
      <h6 class="small">${this.scanHeading}</h6>
      <nav>
        ${this.running
          ? progressLine(p)
          : btn('Scan', false, () => this.runPreview())}
      </nav>`;
  }

  renderResults() {
    const rows = this.rows;
    const c = { create: 0, update: 0, skip: 0, error: 0 };
    for (const r of rows) c[r.group]++;
    const shown = this.filter === 'all' ? rows : rows.filter((r) => r.group === this.filter);
    const pages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
    const page = Math.min(this.page, pages - 1);
    const first = page * PAGE_SIZE;
    const pageRows = shown.slice(first, first + PAGE_SIZE);
    const padRows = pages > 1 ? PAGE_SIZE - pageRows.length : 0;
    const selectable = shown.filter((r) => r.keys.length);
    const onCount = selectable.filter((r) => this.rowOn(r)).length;
    const allOn = selectable.length > 0 && onCount === selectable.length;
    const nSel = rows.filter((r) => this.rowOn(r)).length;

    return html`
      ${this.scanErrors.map((e) => html`<p>${statusLine('error', e.detail)}</p>`)}
      <nav class="wrap">
        ${chip(`All ${rows.length}`, this.filter === 'all', () => this.setFilter('all'))}
        ${chip(`Create ${c.create}`, this.filter === 'create', () => this.setFilter('create'))}
        ${chip(`Update ${c.update}`, this.filter === 'update', () => this.setFilter('update'))}
        ${c.error ? chip(`Failed ${c.error}`, this.filter === 'error', () => this.setFilter('error')) : nothing}
      </nav>

      <div class="scroll capped capped-width">
        <table class="sync-table">
          <colgroup><col class="col-check"><col class="col-action"><col><col class="col-media"></colgroup>
          <thead><tr>
            <th>${checkbox(allOn, () => this.toggleShown(selectable, !allOn),
              { indeterminate: onCount > 0 && !allOn, disabled: this.running })}</th>
            <th>Action</th>
            <th>${this.itemColLabel}</th>
            <th>${this.lastColLabel}</th>
          </tr></thead>
          <tbody>
            ${pageRows.length ? pageRows.map((r) => this.row(r)) : emptyRow(4, 'No items')}
            ${Array.from({ length: padRows }, () => html`<tr class="pad"><td colspan="4">&nbsp;</td></tr>`)}
          </tbody>
        </table>
      </div>
      ${pages > 1 ? html`<nav class="pager">
        <button class="circle transparent" ?disabled=${page === 0}
          @click=${() => { this.page = page - 1; }} aria-label="Previous page"><i>chevron_left</i></button>
        <span class="pager-count">${first + 1}-${Math.min(first + PAGE_SIZE, shown.length)} of ${shown.length}</span>
        <button class="circle transparent" ?disabled=${page >= pages - 1}
          @click=${() => { this.page = page + 1; }} aria-label="Next page"><i>chevron_right</i></button>
      </nav>` : nothing}

      <div class="large-space"></div>
      <nav class="wrap">
        ${this.renderApplyExtras()}
        ${btn(this.running ? 'Applying...' : `Apply ${nSel} change${nSel === 1 ? '' : 's'}`,
          this.running || !nSel, () => this.apply())}
        ${btn('Cancel', this.running, () => this.cancel(), 'border')}
        ${this.running ? spinner : nothing}
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
      <td title=${r.title || ''}>${r.title || ' '}</td>
      <td>${this.lastCol(r)}</td>
    </tr>`;
  }

  renderApplied() {
    const summary = summarize(this.applied?.events?.find((e) => e.kind === 'summary')?.data, true);
    const failed = (this.applied?.events || []).filter((e) => e.action === 'failed');
    return html`
      <h6 class="small">${this.scanHeading}</h6>
      <p>${statusLine('error', summary || 'Finished with errors')}</p>
      ${failed.length ? html`<div class="scroll capped capped-width">
        <table><tbody>${failed.map((e) => html`<tr>
          <td>${e.title || e.source_id || ''}</td>
          <td class="mono">${e.gramps_id || ''}</td>
          <td class="small-text error-text">${e.detail || ''}</td>
        </tr>`)}</tbody></table></div>
        <div class="space"></div>` : nothing}
      <nav>${btn('Back to scan', false, () => this.runAnother())}</nav>`;
  }
}
