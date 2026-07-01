/* Transcribe = turn document images into text/notes (Gemini OCR), plus the
   transcription-note maintenance tasks.

   All work runs through the existing /sync/api/* endpoints:
   OCR via /sync/api/ocr/apply, resync via /sync/api/paperless/resync-media,
   rewrite-all via /sync/api/paperless/apply {transcriptions_only,force}. */
import { BifrostElement, html, nothing, api, post, summarize, tabsBar, chip, switchEl } from './core.js';
import { icon } from './sync-page.js';

const TABS = [
  { key: 'transcribe', label: 'Transcribe' },
  { key: 'history', label: 'History' },
  { key: 'settings', label: 'Settings' },
];
const wandIcon = icon(html`<path d="M5 3v4M3 5h4M6 17v4m-2-2h4"/><path d="M13 4 9 20l5-3 5 3-3-13z"/>`, 18);
const checkCircle = html`<svg width="28" height="28" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/><path d="m8 12 3 3 5-6"/></svg>`;

class TranscribePage extends BifrostElement {
  static properties = {
    tab: { state: true },
    mode: { state: true },        // single | batch
    phase: { state: true },       // idle | running | applied
    running: { state: true },
    applied: { state: true },
    error: { state: true },
    config: { state: true },
    pending: { state: true },
    ui: { state: true },
    resyncMsg: { state: true },
    rewriteMsg: { state: true },
  };

  constructor() {
    super();
    this.tab = 'transcribe';
    this.mode = 'batch';
    this.phase = 'idle';
    this.running = false;
    this.applied = null;
    this.error = '';
    this.config = null;
    this.pending = null;
    this.ui = {};
    this.resyncMsg = '';
    this.rewriteMsg = '';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    try { this.config = await api('/transcribe/api/config'); } catch (e) { this.config = { _error: e.message }; }
    try { this.pending = (await api('/sync/api/ocr/pending')).count; } catch { this.pending = null; }
  }

  get docId() { return this.renderRoot.querySelector('#docid')?.value.trim() || ''; }
  get resyncId() { return this.renderRoot.querySelector('#resyncid')?.value.trim() || ''; }
  uiGet(k, d) { return this.ui[k] === undefined ? d : this.ui[k]; }
  setUi(k, v) { this.ui = { ...this.ui, [k]: v }; }

  async runOcr() {
    const body = {};
    if (this.mode === 'single') {
      const id = parseInt(this.docId, 10);
      if (!id) { this.error = 'Enter a Paperless document ID.'; return; }
      body.single_doc_id = id;
    }
    this.error = ''; this.running = true; this.phase = 'running';
    try {
      this.applied = await post('/sync/api/ocr/apply', body);
      this.phase = 'applied';
    } catch (e) {
      this.error = e.message; this.phase = 'idle';
    } finally {
      this.running = false;
    }
  }

  async resync() {
    const media_id = this.resyncId;
    if (!media_id) { this.resyncMsg = 'Enter a media ID.'; return; }
    this.resyncMsg = 'Resyncing…';
    try {
      const r = await post('/sync/api/paperless/resync-media', { media_id, apply: true });
      const c = r.events.find((e) => e.kind === 'summary')?.data;
      this.resyncMsg = `${r.media_id} → #${r.doc_id} · ${summarize(c, true) || 'no change'}`;
    } catch (e) { this.resyncMsg = e.message; }
  }

  async rewriteAll() {
    this.rewriteMsg = 'Rewriting…';
    try {
      const r = await post('/sync/api/paperless/apply', { transcriptions_only: true, force_transcriptions: true });
      const c = r.events.find((e) => e.kind === 'summary')?.data;
      this.rewriteMsg = summarize(c, true) || 'No changes';
    } catch (e) { this.rewriteMsg = e.message; }
  }

  captionFor(tab) {
    return tab === 'transcribe' ? 'Run the transcription, then it is written back to Gramps.'
      : tab === 'history' ? 'A log of past OCR operations.'
      : 'Defaults applied to every OCR run.';
  }

  render() {
    return html`
      <h5>Transcribe</h5>
      <p class="hint">Run Gemini OCR over a document and write the text back as a Gramps Transcription note.</p>

      ${tabsBar(TABS, this.tab, (t) => { this.tab = t; })}
      <p class="hint">${this.captionFor(this.tab)}</p>

      ${this.error ? html`<article class="border error-text">${this.error}</article>` : nothing}

      ${this.tab === 'transcribe' ? this.renderTranscribe()
        : this.tab === 'history' ? this.renderHistory()
        : this.renderSettings()}`;
  }

  renderTranscribe() {
    if (this.phase === 'running') return this.renderRunning();
    if (this.phase === 'applied') return this.renderApplied();
    return html`${this.renderIdle()}${this.renderMaintenance()}`;
  }

  renderIdle() {
    return html`<article class="border">
      <h6>Choose what to transcribe</h6>
      <p class="hint">Run OCR on a single Paperless document, or on every document carrying the OCR tag.</p>

      <div class="row">
        ${chip('Single document', this.mode === 'single', () => { this.mode = 'single'; })}
        ${chip('Tagged batch', this.mode === 'batch', () => { this.mode = 'batch'; })}
      </div>

      ${this.mode === 'single' ? html`
        <div class="field label border" style="max-width:460px">
          <input id="docid" type="number" inputmode="numeric"
            @keydown=${(e) => { if (e.key === 'Enter') this.runOcr(); }}>
          <label>Paperless document ID</label>
        </div>
        <p class="hint">Gemini reads the document's page image and writes a Transcription note back to Gramps.</p>
        <div class="row">
          <button ?disabled=${this.running} @click=${() => this.runOcr()}>${wandIcon}<span>Run OCR</span></button>
        </div>`
      : html`
        <div class="row">
          <span class="hint">OCR tag</span>
          <span class="chip small"><i>sell</i><span>${this.config?.ocr_tag || 'Gemini OCR'}</span></span>
        </div>
        <p>
          ${this.pending == null ? html`Checking how many documents carry this tag…`
            : html`<strong>${this.pending} document${this.pending === 1 ? '' : 's'}</strong> in Paperless await OCR under this tag.`}
        </p>
        <div class="row">
          <button ?disabled=${this.running || this.pending === 0} @click=${() => this.runOcr()}>
            ${wandIcon}<span>Run OCR${this.pending ? ` on ${this.pending} document${this.pending === 1 ? '' : 's'}` : ''}</span></button>
        </div>`}
    </article>`;
  }

  renderMaintenance() {
    return html`
      <h6>Maintenance</h6>
      <div class="grid">
        <article class="s12 m6 border">
          <b>Resync a transcription</b>
          <p class="hint">Re-pull the latest text for one media object into its Gramps note.</p>
          <div class="field label border" style="max-width:260px">
            <input id="resyncid" class="mono" style="text-transform:uppercase"
              @keydown=${(e) => { if (e.key === 'Enter') this.resync(); }}>
            <label>Media ID</label>
          </div>
          <button class="border small" @click=${() => this.resync()}>Resync</button>
          ${this.resyncMsg ? html`<p class="hint">${this.resyncMsg}</p>` : nothing}
        </article>
        <article class="s12 m6 border">
          <b>Rewrite all notes</b>
          <p class="hint">Rebuild every Transcription note from the current document text.</p>
          <button class="border small" @click=${() => this.rewriteAll()}>Rewrite all notes</button>
          ${this.rewriteMsg ? html`<p class="hint">${this.rewriteMsg}</p>` : nothing}
        </article>
      </div>`;
  }

  renderRunning() {
    return html`<article class="border center-align large-padding">
      <progress class="circle"></progress>
      <h6>Transcribing with Gemini…</h6>
      <p class="hint">Reading the page image. This can take a little while for multi-page documents.</p>
    </article>`;
  }

  renderApplied() {
    const c = this.applied?.events?.find((e) => e.kind === 'summary')?.data;
    const errs = (this.applied?.events || []).filter((e) => e.kind === 'error');
    return html`<article class="border">
      <div class="row top-align">
        <span class="${errs.length ? 'action-failed' : 'action-created'}">${checkCircle}</span>
        <div class="max">
          <h6>${errs.length ? 'Finished with errors' : 'Transcription written'}</h6>
          <p class="hint">${summarize(c, true) || (errs.length ? errs[0].detail : 'Done.')}</p>
          <div class="row">
            ${this.config?.gramps_public_url ? html`<a class="button border"
              href=${this.config.gramps_public_url} target="_blank" rel="noopener">Open in Gramps Web</a>` : nothing}
            <button class="transparent primary-text"
              @click=${() => { this.phase = 'idle'; this.applied = null; }}>Transcribe another</button>
          </div>
        </div>
      </div>
    </article>`;
  }

  renderHistory() {
    return html`<article class="border">
      <h6>Recent runs</h6>
      <p class="hint">Every OCR run, newest first.</p>
      <div class="center-align large-padding">
        ${icon(html`<path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/>`, 34, 1.5)}
        <p><b>No history yet</b></p>
        <p class="hint">Run history will appear here once it's wired up.</p>
      </div>
    </article>`;
  }

  renderSettings() {
    if (!this.config) return html`<article class="border"><p class="hint">Loading settings…</p></article>`;
    if (this.config._error) return html`<article class="border error-text">
      Couldn't load settings: ${this.config._error}</article>`;
    const c = this.config;
    const models = [...new Set([c.model, 'gemini-3-flash-preview', 'gemini-3-pro'].filter(Boolean))];
    const sections = [
      { key: 'model', title: 'OCR model', desc: 'Which Gemini model reads your documents.',
        body: html`<div class="field label border" style="max-width:360px">
          <select>${models.map((m) => html`<option ?selected=${m === c.model}>${m}</option>`)}</select>
          <label>Model</label>
        </div>` },
      { key: 'tag', title: 'Tag & write-back',
        desc: 'The Paperless tag for batch OCR, and writing the text back into the document.',
        body: html`
          <div class="field label border" style="max-width:280px">
            <input .value=${c.ocr_tag ?? ''}>
            <label>Batch OCR tag</label>
          </div>
          <div class="row">
            <div class="max">
              <b>Write text back into the Paperless document</b>
              <div class="hint">In-place, so it shows in Paperless search and flows on to the Gramps note.</div>
            </div>
            ${switchEl(this.uiGet('writeback', true), (v) => this.setUi('writeback', v))}
          </div>` },
      { key: 'style', title: 'House style',
        desc: 'The master document Gemini follows for formatting and conventions.',
        body: html`<div class="field label border" style="max-width:420px">
          <input class="mono" .value=${c.house_style_path ?? ''}>
          <label>House-style master</label>
        </div>` },
    ];
    return html`${sections.map((s) => html`
      <details class="border round">
        <summary class="padding">
          <b>${s.title}</b>
          <div class="hint">${s.desc}</div>
        </summary>
        <div class="padding">${s.body}</div>
      </details>`)}`;
  }
}
customElements.define('transcribe-page', TranscribePage);
