import { SyncPage } from './sync-page.js';

class SyncCheckPage extends SyncPage {
  get apiBase() { return '/sync/api'; }
  get jobName() { return 'sync.check'; }
  get itemColLabel() { return 'Document, photo or file'; }
  get scanHeading() { return 'Check sync status with Gramps'; }
  get groups() { return [['create', 'Create'], ['update', 'Update'], ['replace', 'Replace']]; }
  isPrimary(e) { return e.entity === 'doc' || e.entity === 'media' || e.entity === 'file'; }
}
customElements.define('sync-check-page', SyncCheckPage);
