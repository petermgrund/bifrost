import { SyncPage } from './sync-page.js';

class AncestryLinksPage extends SyncPage {
  get apiBase() { return '/ancestry/api/links'; }
  get jobName() { return 'ancestry.links'; }
  get itemColLabel() { return 'Paperless document'; }
  get lastColLabel() { return 'Citation'; }
  get scanHeading() { return 'Scan Paperless for Ancestry records to attach to their Gramps citations'; }
  get disabledText() { return 'Needs sync.paperless.source_url_field_id and gramps_id_field_id'; }
  get primaryEntity() { return 'citation'; }
  get groups() { return [['update', 'Attach']]; }
}
customElements.define('ancestry-links-page', AncestryLinksPage);
