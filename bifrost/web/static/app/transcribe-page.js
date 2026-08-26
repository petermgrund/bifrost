import { BifrostElement, html, nothing, api, post, summarize, spinner, btn, field, statusLine,
         iconYes, iconNo } from './core.js';

class TranscribePage extends BifrostElement {
  static properties = {
    ocrId: { state: true },
    ocrBusy: { state: true },
    ocrResult: { state: true },
    resyncId: { state: true },
    resyncBusy: { state: true },
    resyncResult: { state: true },
    pending: { state: true },
    looking: { state: true },
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
    this.pending = null;
    this.looking = false;
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
          target="_blank" rel="noopener"> Open in Gramps</a>` : nothing;
  }

  updated() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg && !dlg.open) dlg.showModal();
  }

  async lookupOcr() {
    if (this.ocrBusy || this.looking) return;
    const media_id = this.ocrId.trim();
    if (!media_id) { this.ocrResult = { kind: 'error', body: 'Enter a Gramps media ID.' }; return; }
    this.ocrResult = null; this.looking = true;
    try {
      this.pending = await api(`/transcribe/api/lookup/${encodeURIComponent(media_id)}`);
    } catch (e) {
      this.ocrResult = { kind: 'error', body: e.message };
    } finally {
      this.looking = false;
    }
  }

  closeConfirm() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg?.open) dlg.close();
    else this.pending = null;
  }

  async runOcr() {
    if (this.ocrBusy) return;
    const media_id = (this.pending?.media_id || this.ocrId).trim();
    this.closeConfirm();
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
          { mono: true, upper: true, width: 'small', onEnter: () => this.lookupOcr() })}
        ${btn(this.ocrBusy ? 'Transcribing...' : this.looking ? 'Looking up...' : 'Run',
          this.ocrBusy || this.looking, () => this.lookupOcr())}
        ${this.ocrBusy || this.looking ? spinner : nothing}
      </nav>
      ${this.pending ? this.renderConfirm() : nothing}
      ${this.ocrResult ? html`<p>${statusLine(this.ocrResult.kind, this.ocrResult.body)}</p>` : nothing}

      <div class="large-space"></div>
      <h6 class="small">Resync one note</h6>
      <nav class="wrap">
        ${field('Gramps media ID', this.resyncId, (e) => (this.resyncId = e.target.value),
          { mono: true, upper: true, width: 'small', onEnter: () => this.resync() })}
        ${btn(this.resyncBusy ? 'Resyncing...' : 'Resync', this.resyncBusy, () => this.resync())}
        ${this.resyncBusy ? spinner : nothing}
        ${this.resyncResult ? statusLine(this.resyncResult.kind, this.resyncResult.body) : nothing}
      </nav>

      <div class="large-space"></div>
      <h6 class="small">Resync all notes</h6>
      <nav class="wrap">
        ${btn('Resync all notes', true, () => this.resyncAll())}
      </nav>`;
  }

  renderConfirm() {
    const p = this.pending;
    return html`
      <dialog @close=${() => (this.pending = null)}>
        <h5 class="small">Transcribe this document?</h5>
        <table><tbody>
          <tr><td>Gramps media</td>
            <td>${p.media_title || '(untitled)'} <span class="mono">${p.media_id}</span></td></tr>
          <tr><td>Paperless doc</td>
            <td>${p.doc_title || '(untitled)'} <span class="mono">#${p.doc_id}</span></td></tr>
          <tr><td>Current text</td><td>${p.chars} characters</td></tr>
          <tr><td>OCR tag</td><td>${p.ocr_tagged
            ? html`${iconYes} ${p.ocr_tag}`
            : html`${iconNo} <span class="error-text">not tagged
                '${p.ocr_tag || '(no ocr_tag configured)'}' in Paperless</span>`}</td></tr>
        </tbody></table>
        <p class="small-text secondary-text">This will replace the document's
          text in Paperless and syncs the transcription note to Gramps.</p>
        <nav>
          ${btn('Transcribe', !p.ocr_tagged, () => this.runOcr())}
          ${btn('Cancel', false, () => this.closeConfirm(), 'border')}
        </nav>
      </dialog>`;
  }
}
customElements.define('transcribe-page', TranscribePage);
