/* Reprocess section — one flat stanza, no cards:
   • Find mixed-width documents: measure every multi-page PDF tagged 'doc'
     (POST /reprocess/api/scan, read-only), tick the ones to fix, and batch
     them to the widest/narrowest width (POST /reprocess/api/batch). Each
     rebuilt PDF is posted as a NEW VERSION of the same document — the
     current file stays in the version history; Gramps follows on the next
     version sync. */
import { BifrostElement, html, nothing, post, summarize, spinner, btn, chip, checkbox, statusLine } from './core.js';

class ReprocessPage extends BifrostElement {
  static properties = {
    scan: { state: true },          // scan payload | null
    sel: { state: true },           // Set of selected doc_ids
    batchMode: { state: true },     // 'widest' | 'narrowest'
    batchOutcome: { state: true },  // {doc_id: {kind, text}} | null
    findResult: { state: true },    // {kind, body} | null
    busy: { state: true },          // '' | 'scan' | 'batch'
  };

  constructor() {
    super();
    this.scan = null;
    this.sel = new Set();
    this.batchMode = 'widest';
    this.batchOutcome = null;
    this.findResult = null;
    this.busy = '';
  }

  async runScan() {
    if (this.busy) return;
    this.busy = 'scan'; this.scan = null; this.batchOutcome = null; this.findResult = null;
    try {
      const r = await post('/reprocess/api/scan', {});
      this.scan = r;
      this.sel = new Set(r.rows.map((x) => x.doc_id)); // everything ticked by default
      if (r.errors?.length) {
        this.findResult = { kind: 'error',
          body: `${r.errors.length} document(s) could not be measured: ${r.errors.map((e) => `#${e.doc_id} (${e.error})`).join('; ')}` };
      }
    } catch (e) {
      this.findResult = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  toggleSel(id) {
    if (this.busy) return;
    const s = new Set(this.sel);
    s.has(id) ? s.delete(id) : s.add(id);
    this.sel = s;
  }

  toggleAll() {
    if (this.busy || !this.scan) return;
    const all = this.scan.rows.map((r) => r.doc_id);
    this.sel = this.sel.size === all.length ? new Set() : new Set(all);
  }

  setBatchMode(mode) {
    if (!this.busy) this.batchMode = mode;
  }

  async runBatch() {
    if (this.busy || !this.sel.size) return;
    this.busy = 'batch'; this.findResult = null; this.batchOutcome = null;
    const doc_ids = this.scan.rows.map((r) => r.doc_id).filter((id) => this.sel.has(id));
    try {
      const r = await post('/reprocess/api/batch', { doc_ids, mode: this.batchMode });
      const c = r.events.find((e) => e.kind === 'summary')?.data;
      const out = {};
      for (const e of r.events) {
        if (e.kind === 'error' && e.source_id) out[e.source_id] = { kind: 'error', text: e.detail };
        if (e.kind !== 'item' || e.entity !== 'doc') continue;
        out[e.source_id] = e.action === 'failed' ? { kind: 'error', text: e.detail }
          : e.action === 'skipped' ? { kind: 'info', text: 'nothing to upload' }
          : { kind: 'ok', text: 'uploaded' };
      }
      this.batchOutcome = out;
      this.sel = new Set();
      this.findResult = { kind: c?.errors ? 'error' : 'ok',
        body: `${summarize(c, true)}; consumption begun; wait 60s to resync to Gramps.` };
    } catch (e) {
      this.findResult = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  render() {
    const rows = this.scan?.rows || [];
    const n = this.sel.size;
    return html`
      <h6 class="small">Find mixed-width documents</h6>
      <nav class="wrap">
        ${btn(this.busy === 'scan' ? 'Scanning…' : 'Scan', !!this.busy, () => this.runScan())}
        ${this.busy === 'scan'
          ? statusLine('busy', `Scanning...`)
          : nothing}
        ${this.scan ? statusLine('info',
          `${rows.length} have mixed page widths.`) : nothing}
      </nav>
      ${this.scan && rows.length ? html`
        <div class="scroll capped capped-width">
          <table>
            <thead><tr>
              <th>${checkbox(n === rows.length && rows.length > 0, () => this.toggleAll(),
                { indeterminate: n > 0 && n < rows.length, disabled: !!this.busy })}</th>
              <th>Document</th>
              <th>ID</th>
              <th>Pages</th>
              ${this.batchOutcome ? html`<th>Result</th>` : nothing}
            </tr></thead>
            <tbody>${rows.map((r) => html`<tr>
              <td>${checkbox(this.sel.has(r.doc_id), () => this.toggleSel(r.doc_id),
                { disabled: !!this.busy })}</td>
              <td>${r.title}</td>
              <td>#${r.doc_id}</td>
              <td>${r.pages}</td>
              ${this.batchOutcome ? html`<td class="small-text">
                ${this.batchOutcome[r.doc_id]
                  ? statusLine(this.batchOutcome[r.doc_id].kind, this.batchOutcome[r.doc_id].text)
                  : ''}</td>` : nothing}
            </tr>`)}</tbody>
          </table>
        </div>
        <div class="space"></div>
        <nav class="wrap">
          ${chip('Widest page', this.batchMode === 'widest', () => this.setBatchMode('widest'))}
          ${chip('Narrowest page', this.batchMode === 'narrowest', () => this.setBatchMode('narrowest'))}
          ${btn(this.busy === 'batch' ? 'Reprocessing…' : `Reprocess ${n} document${n === 1 ? '' : 's'}`,
            !!this.busy || !n, () => this.runBatch())}
          ${this.busy === 'batch' ? spinner : nothing}
        </nav>` : nothing}
      ${this.findResult ? html`<p>${statusLine(this.findResult.kind, this.findResult.body)}</p>` : nothing}`;
  }
}
customElements.define('reprocess-page', ReprocessPage);
