import { SyncPage } from './sync-page.js';

class ReprocessPage extends SyncPage {
  get apiBase() { return '/reprocess/api'; }
  get jobName() { return 'reprocess.widths'; }
  get itemColLabel() { return 'Paperless document'; }
  get lastColLabel() { return 'Pages'; }
  get scanHeading() { return 'Scan Paperless for mixed-width documents'; }

  lastCol(r) { return r.data.pages ?? ' '; }
}
customElements.define('reprocess-page', ReprocessPage);
