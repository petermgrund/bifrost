import { html, nothing, post, summarize, btn, statusLine } from './core.js';
import { SyncPage } from './sync-page.js';

const SHOW_RESYNC_ALL = false;

class TranscribePage extends SyncPage {
  static properties = {
    resyncBusy: { state: true },
    resyncResult: { state: true },
  };

  constructor() {
    super();
    this.resyncBusy = false;
    this.resyncResult = null;
  }

  get apiBase() { return '/transcribe/api'; }
  get jobName() { return 'transcribe.ocr'; }
  get itemColLabel() { return 'Paperless document'; }
  get scanHeading() { return 'Scan Paperless for documents to transcribe'; }
  get disabledText() { return 'No OCR tag configured (sync.paperless.ocr_tag)'; }
  get groups() { return [['create', 'Create'], ['replace', 'Replace']]; }
  get preselect() { return false; }

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
      ${super.render()}
      ${SHOW_RESYNC_ALL ? html`
        <div class="large-space"></div>
        <h6 class="small">Resync all notes</h6>
        <nav class="wrap">
          ${btn('Resync all notes', this.resyncBusy, () => this.resyncAll())}
        </nav>
        ${this.resyncResult ? html`<p>${statusLine(this.resyncResult.kind, this.resyncResult.body)}</p>` : nothing}` : nothing}`;
  }
}
customElements.define('transcribe-page', TranscribePage);
