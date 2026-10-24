import { SyncPage } from './sync-page.js';

class PlacesLinksPage extends SyncPage {
  get apiBase() { return '/places/api/links'; }
  get jobName() { return 'places.links'; }
  get itemColLabel() { return 'Gramps place'; }
  get lastColLabel() { return 'Place object'; }
  get scanHeading() { return 'Scan Gramps places for missing OpenStreetMap links or coordinates'; }
  get primaryEntity() { return 'place'; }
}
customElements.define('places-links-page', PlacesLinksPage);
