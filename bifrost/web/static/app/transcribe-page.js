import { BifrostElement, html, nothing, api, post, summarize, spinner, btn, field, statusLine } from './core.js';

class TranscribePage extends BifrostElement {
  static properties = {
    ocrId: { state: true },
    ocrBusy: { state: true },
    ocrResult: { state: true },      // {kind, body} | null
    resyncId: { state: true },
    resyncBusy: { state: true },
    resyncResult: { state: true },
    rewriteBusy: { state: true },
    rewriteResult: { state: true },
    config: { state: true },
  };

  constructor() {
    super();
    this.ocrId = '';
    this.ocrBusy = false;
    this.ocrResult = null;
    this.resyncId = '';
    this.resyncBusy = false;
    this.resyncResult = null;
    this.rewriteBusy = false;
    this.rewriteResult = null;
    this.config = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadConfig();
  }

  async loadConfig() {
    try { this.config = await api('/transcribe/api/config'); } catch { this.config = null; }
  }

  grampsLink(id) {
    return this.config?.gramps_public_url
      ? html`<a class="link" href="${this.config.gramps_public_url}/media/${id}"
          target="_blank" rel="noopener">open in Gramps</a>` : nothing;
  }

  async runOcr() {
    if (this.ocrBusy) return;
    const media_id = this.ocrId.trim();
    if (!media_id) { this.ocrResult = { kind: 'error', body: 'Enter a Gramps media ID.' }; return; }
    this.ocrResult = null; this.ocrBusy = true;
    try {
      const r = await post('/transcribe/api/run', { media_id });
      const ocrC = r.ocr_events.find((e) => e.kind === 'summary')?.data;
      const txC = r.tx_events.find((e) => e.kind === 'summary')?.data;
      const errs = (ocrC?.errors || 0) + (txC?.errors || 0);
      this.ocrResult = { kind: errs ? 'error' : 'ok', body: html`${r.media_id}
        ${summarize(ocrC, true)}, ${summarize(txC, true)}${this.grampsLink(media_id)}` };
    } catch (e) {
      this.ocrResult = { kind: 'error', body: e.message };
    } finally {
      this.ocrBusy = false;
    }
  }

  async resync() {
    if (this.resyncBusy) return;
    const media_id = this.resyncId.trim();
    if (!media_id) { this.resyncResult = { kind: 'error', body: 'Enter a media ID.' }; return; }
    this.resyncResult = null; this.resyncBusy = true;
    try {
      const r = await post('/sync/api/paperless/resync-media', { media_id, apply: true });
      const c = r.events.find((e) => e.kind === 'summary')?.data;
      this.resyncResult = { kind: c?.errors ? 'error' : 'ok',
        body: `${r.media_id} is saved as #${r.doc_id}, ${summarize(c, true) || 'no change'}` };
    } catch (e) {
      this.resyncResult = { kind: 'error', body: e.message };
    } finally {
      this.resyncBusy = false;
    }
  }

  async resyncAll() {
    if (this.resyncBusy) return;
    this.resyncResult = null; this.resyncBusy = true;
    try {
      const r = await post('/sync/api/paperless/apply', { transcriptions_only: true, force_transcriptions: true });
      const c = r.events.find((e) => e.kind === 'summary')?.data;
      this.resyncResult = { kind: c?.errors ? 'error' : 'ok', body: summarize(c, true) || 'No changes' };
    } catch (e) {
      this.resyncResult = { kind: 'error', body: e.message };
    } finally {
      this.resyncBusy = false;
    }
  }

  render() {
    return html`
      <h6 class="small">Run OCR on a Paperless doc</h6>
      <nav class="wrap">
        ${field('Gramps media ID', this.ocrId, (e) => (this.ocrId = e.target.value),
          { mono: true, upper: true, width: 'small', onEnter: () => this.runOcr() })}
        ${btn(this.ocrBusy ? 'Transcribing…' : 'Run', this.ocrBusy, () => this.runOcr())}
        ${this.ocrBusy ? spinner : nothing}
      </nav>
      ${this.ocrResult ? html`<p>${statusLine(this.ocrResult.kind, this.ocrResult.body)}</p>` : nothing}

      <div class="large-space"></div>
      <h6 class="small">Resync one note</h6>
      <nav class="wrap">
        ${field('Gramps media ID', this.resyncId, (e) => (this.resyncId = e.target.value),
          { mono: true, upper: true, width: 'small', onEnter: () => this.resync() })}
        ${btn(this.resyncBusy ? 'Resyncing…' : 'Resync', this.resyncBusy, () => this.resync())}
        ${this.resyncBusy ? spinner : nothing}
        ${this.resyncResult ? statusLine(this.resyncResult.kind, this.resyncResult.body) : nothing}
      </nav>

      <div class="large-space"></div>
      <h6 class="small">Resync all notes</h6>
      <nav class="wrap">
        ${btn('Resync all notes', true, () => this.resyncAll())}
      </nav>`;
  }
}
customElements.define('transcribe-page', TranscribePage);
