/* Reprocess section — two flat stanzas, no cards:
   • Find mixed-width documents: measure every multi-page PDF tagged 'doc'
     (POST /reprocess/api/scan, read-only), tick the ones to fix, and batch
     them to the widest/narrowest width (POST /reprocess/api/batch).
   • Normalize page widths: one document — preview measures the pages
     (POST /reprocess/api/widths, apply:false) and lists each with its scale
     factor; Upload rebuilds the PDF and posts it as a NEW VERSION of the
     same document (apply:true). The current file stays in the version
     history; Gramps follows on the next version sync. */
import { BifrostElement, html, nothing, api, post, summarize, spinner, btn, chip, field, checkbox, statusLine, emptyRow } from './core.js';

class ReprocessPage extends BifrostElement {
  static properties = {
    scan: { state: true },          // scan payload | null
    sel: { state: true },           // Set of selected doc_ids
    batchMode: { state: true },     // 'widest' | 'narrowest'
    batchOutcome: { state: true },  // {doc_id: {kind, text}} | null
    findResult: { state: true },    // {kind, body} | null
    docRef: { state: true },
    mode: { state: true },          // 'widest' | 'narrowest'
    busy: { state: true },          // '' | 'scan' | 'batch' | 'preview' | 'apply'
    preview: { state: true },       // widths payload (apply:false) | null
    result: { state: true },        // {kind, body} | null
    config: { state: true },
  };

  constructor() {
    super();
    this.scan = null;
    this.sel = new Set();
    this.batchMode = 'widest';
    this.batchOutcome = null;
    this.findResult = null;
    this.docRef = '';
    this.mode = 'widest';
    this.busy = '';
    this.preview = null;
    this.result = null;
    this.config = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadConfig();
  }

  async loadConfig() {
    try { this.config = await api('/reprocess/api/config'); } catch { this.config = null; }
  }

  paperlessLink(docId) {
    return this.config?.public_url
      ? html`<a class="link" href="${this.config.public_url}/documents/${docId}/details"
          target="_blank" rel="noopener">open in Paperless</a>` : nothing;
  }

  /* ---- find + batch stanza ---- */

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

  widthsLabel(r) {
    return r.widths.length <= 3
      ? `${r.widths.join(' · ')} pt`
      : `${r.widths.length} widths · ${r.min_width}–${r.max_width} pt`;
  }

  renderFind() {
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

  /* ---- single-document stanza ---- */

  setMode(mode) {
    if (this.busy || this.mode === mode) return;
    this.mode = mode;
    if (this.preview) this.runPreview(); // re-measure against the new target
  }

  async runPreview() {
    if (this.busy) return;
    const doc_ref = this.docRef.trim();
    if (!doc_ref) {
      this.result = { kind: 'error', body: 'Enter Paperless document ID.' };
      return;
    }
    this.busy = 'preview'; this.result = null; this.preview = null;
    try {
      const r = await post('/reprocess/api/widths', { doc_ref, mode: this.mode, apply: false });
      const err = r.events.find((e) => e.kind === 'error' || e.action === 'failed');
      if (err) this.result = { kind: 'error', body: err.detail };
      else this.preview = r;
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  async upload() {
    if (this.busy || !this.preview) return;
    this.busy = 'apply'; this.result = null;
    try {
      const r = await post('/reprocess/api/widths',
        { doc_ref: this.docRef.trim(), mode: this.mode, apply: true });
      const err = r.events.find((e) => e.kind === 'error' || e.action === 'failed');
      if (err) {
        this.result = { kind: 'error', body: err.detail };
      } else {
        const c = r.events.find((e) => e.kind === 'summary')?.data;
        const done = r.events.find((e) => e.entity === 'doc' && e.action === 'updated');
        this.result = { kind: 'ok',
          body: html`${summarize(c, true)} — ${done?.detail || 'done'}. ${this.paperlessLink(r.doc_id)}` };
        this.preview = null;
      }
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  get pageRows() {
    return (this.preview?.events || []).filter((e) => e.kind === 'item' && e.entity === 'page');
  }

  renderSingle() {
    const started = this.preview?.events?.find((e) => e.kind === 'started');
    const toScale = this.preview?.events?.find((e) => e.kind === 'summary')?.data?.pages_scaled || 0;
    const rows = this.pageRows;
    return html`
      <h6 class="small">Normalize page widths</h6>
      <nav class="wrap">
        ${field('Paperless ID', this.docRef, (e) => (this.docRef = e.target.value),
          { mono: true, upper: true, width: 'small', onEnter: () => this.runPreview() })}
        ${chip('Widest page', this.mode === 'widest', () => this.setMode('widest'))}
        ${chip('Narrowest page', this.mode === 'narrowest', () => this.setMode('narrowest'))}
        ${btn(this.busy === 'preview' ? 'Measuring…' : 'Preview', !!this.busy, () => this.runPreview())}
        ${this.busy === 'preview' ? spinner : nothing}
      </nav>
      ${this.preview ? html`
        <p class="secondary-text">${started?.title}
        <div class="scroll capped capped-width">
          <table>
            <thead><tr><th>Page</th><th>Size</th><th>After</th></tr></thead>
            <tbody>${rows.length ? rows.map((e) => html`<tr>
                <td>${e.title}</td>
                <td class="mono small-text">${e.data?.cols?.size}</td>
                <td class="small-text">${e.data?.cols?.result}</td>
              </tr>`) : emptyRow(3, 'No pages')}</tbody>
          </table>
        </div>
        <div class="space"></div>
        <nav class="wrap">
          ${btn(this.busy === 'apply' ? 'Uploading…' : 'Upload new version',
            !!this.busy || !toScale, () => this.upload())}
          ${this.busy === 'apply' ? spinner : nothing}
          ${toScale
            ? statusLine('info', `${toScale} page${toScale === 1 ? '' : 's'} will be scaled.`)
            : statusLine('info', 'All pages already share same width')}
        </nav>` : nothing}
      ${this.result ? html`<p>${statusLine(this.result.kind, this.result.body)}</p>` : nothing}`;
  }

  render() {
    return html`
      ${this.renderFind()}
      <div class="large-space"></div>
      ${this.renderSingle()}`;
  }
}
customElements.define('reprocess-page', ReprocessPage);
