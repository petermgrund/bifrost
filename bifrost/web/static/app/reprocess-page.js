import { html, chip } from './core.js';
import { SyncPage } from './sync-page.js';

class ReprocessPage extends SyncPage {
  static properties = { mode: { state: true } };

  constructor() {
    super();
    this.mode = 'widest';
  }

  get apiBase() { return '/reprocess/api'; }
  get jobName() { return 'reprocess.widths'; }
  get itemColLabel() { return 'Paperless document'; }
  get lastColLabel() { return 'Pages'; }
  get scanHeading() { return 'Scan Paperless for mixed-width documents'; }

  lastCol(r) { return r.data.pages ?? ' '; }
  applyBody() { return { selected: [...this.selected], mode: this.mode }; }

  setMode(mode) { if (!this.running) this.mode = mode; }

  renderApplyExtras() {
    return html`
      ${chip('Widest page', this.mode === 'widest', () => this.setMode('widest'))}
      ${chip('Narrowest page', this.mode === 'narrowest', () => this.setMode('narrowest'))}`;
  }
}
customElements.define('reprocess-page', ReprocessPage);
