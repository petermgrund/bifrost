import { SyncPage } from './sync-page.js';

class FacesBackfillPage extends SyncPage {
  get apiBase() { return '/faces/api/backfill'; }
  get jobName() { return 'faces.backfill'; }
  get itemColLabel() { return 'Immich photo'; }
  get scanHeading() { return 'Scan synced Gramps media for missing faces'; }
  get primaryEntity() { return 'face'; }
}
customElements.define('faces-backfill-page', FacesBackfillPage);
