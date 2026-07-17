/* Immich photos → Gramps sync block (Sync section). Same preview/apply table
   as Paperless; a titled, unsynced photo is a create, a synced photo whose
   gda title/date drifted from Gramps is an update (cols say which fields). */
import { SyncPage } from './sync-page.js';

class ImmichSyncPage extends SyncPage {
  get source() { return 'immich'; }
  get itemColLabel() { return 'Immich photo'; }
  get scanHeading() { return 'Scan Immich photos for new or changed Gramps media'; }
  get primaryEntity() { return 'media'; }
}
customElements.define('immich-sync-page', ImmichSyncPage);
