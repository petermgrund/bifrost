import { html, nothing, post, btn, field, spinner, statusLine } from './core.js';
import { SyncPage } from './sync-page.js';

class PlacesLinksPage extends SyncPage {
  static properties = {
    linkId: { state: true },
    linkRef: { state: true },
    linking: { state: true },
    linkResult: { state: true },
  };

  constructor() {
    super();
    this.linkId = '';
    this.linkRef = '';
    this.linking = false;
    this.linkResult = null;
  }

  get apiBase() { return '/places/api/links'; }
  get jobName() { return 'places.links'; }
  get itemColLabel() { return 'Gramps place'; }
  get lastColLabel() { return 'Place object'; }
  get scanHeading() { return 'Scan Gramps places for missing OpenStreetMap links or coordinates'; }
  get primaryEntity() { return 'place'; }

  async link() {
    const gramps_id = this.linkId.trim().toUpperCase();
    const relation = this.linkRef.trim();
    if (!gramps_id || !relation || this.linking) return;
    this.linking = true;
    this.linkResult = null;
    try {
      const r = await post('/places/api/set-relation', { gramps_id, relation });
      this.linkResult = { kind: 'ok', body: `${r.name} (${r.gramps_id}) linked to ${r.osm_type} ${r.osm_id}`
        + (r.coordinates ? `, coordinates ${r.coordinates}` : '') + (r.replaced ? `, was ${r.replaced}` : '') };
      this.linkRef = '';
    } catch (e) {
      this.linkResult = { kind: 'error', body: e.message };
    } finally {
      this.linking = false;
    }
  }

  render() {
    return html`
      ${super.render()}
      <div class="medium-space"></div>
      <h6 class="small">Link a place by hand</h6>
      <nav class="wrap">
        ${field('Gramps place ID', this.linkId, (e) => (this.linkId = e.target.value),
          { mono: true, upper: true, width: 'small' })}
        ${field('OSM relation or URL', this.linkRef, (e) => (this.linkRef = e.target.value),
          { width: 'medium', onEnter: () => this.link() })}
        ${btn(this.linking ? 'Linking...' : 'Link',
          this.linking || !this.linkId.trim() || !this.linkRef.trim(), () => this.link())}
        ${this.linking ? spinner : nothing}
      </nav>
      ${this.linkResult ? html`<p>${statusLine(this.linkResult.kind, this.linkResult.body)}</p>` : nothing}`;
  }
}
customElements.define('places-links-page', PlacesLinksPage);

class PlacesPage extends SyncPage {
  get apiBase() { return '/places/api'; }
  get jobName() { return 'places.boundaries'; }
  get itemColLabel() { return 'Gramps place'; }
  get lastColLabel() { return 'Place object'; }
  get scanHeading() { return 'Scan Gramps places for missing boundaries'; }
  get disabledText() { return 'No boundaries directory configured (places.boundaries_dir)'; }
  get primaryEntity() { return 'place'; }
}
customElements.define('places-page', PlacesPage);
