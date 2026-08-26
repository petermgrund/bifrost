import { SyncPage } from './sync-page.js';

class ImmichSyncPage extends SyncPage {
  get source() { return 'immich'; }
  get itemColLabel() { return 'Immich photo'; }
  get scanHeading() { return 'Scan Immich photos for new or changed Gramps media'; }
  get primaryEntity() { return 'media'; }
}
customElements.define('immich-sync-page', ImmichSyncPage);
