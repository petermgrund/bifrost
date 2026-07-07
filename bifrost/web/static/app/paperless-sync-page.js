/* Paperless → Gramps sync section. */
import { SyncPage } from './sync-page.js';

class PaperlessSyncPage extends SyncPage {
  get source() { return 'paperless'; }
  get itemColLabel() { return 'Paperless document'; }
}
customElements.define('paperless-sync-page', PaperlessSyncPage);
