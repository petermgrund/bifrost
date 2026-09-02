import { html, nothing, api, post, btn, field, spinner, statusLine, searchMenu } from './core.js';
import { SyncPage } from './sync-page.js';

class PlacesLinksPage extends SyncPage {
  static properties = {
    placeList: { state: true },
    placeQ: { state: true },
    placePick: { state: true },
    hiP: { state: true },
    menuOpen: { state: true },
    linkRef: { state: true },
    linking: { state: true },
    linkError: { state: true },
  };

  constructor() {
    super();
    this.placeList = null;
    this.placeQ = '';
    this.placePick = null;
    this.hiP = -1;
    this.menuOpen = false;
    this.linkRef = '';
    this.linking = false;
    this.linkError = '';
  }

  get apiBase() { return '/places/api/links'; }
  get jobName() { return 'places.links'; }
  get itemColLabel() { return 'Gramps place'; }
  get lastColLabel() { return 'Place object'; }
  get scanHeading() { return 'Scan Gramps places for missing OpenStreetMap links or coordinates'; }
  get primaryEntity() { return 'place'; }

  connectedCallback() {
    super.connectedCallback();
    this.loadPlaces();
  }

  async loadPlaces() {
    try {
      this.placeList = await api('/places/api/list');
    } catch {
      this.placeList = [];
    }
  }

  async apply() {
    await super.apply();
    this.loadPlaces();
  }

  placeMatches() {
    const q = this.placeQ.trim().toLowerCase();
    if (!q) return [];
    const rank = (p) => {
      const name = p.name.toLowerCase();
      if (name.startsWith(q)) return 0;
      if (name.includes(q) || p.gramps_id.toLowerCase().includes(q)) return 1;
      if (p.hierarchy.join(', ').toLowerCase().includes(q)) return 2;
      return -1;
    };
    return (this.placeList || [])
      .map((p) => ({ p, r: rank(p) }))
      .filter((x) => x.r >= 0)
      .sort((a, b) => a.r - b.r)
      .slice(0, 3)
      .map(({ p }) => ({ id: p.gramps_id, label: p.hierarchy.join(', ') || p.name,
        sub: p.gramps_id, mono: true }));
  }

  pickPlace(it) {
    this.placePick = it;
    this.placeQ = '';
    this.hiP = -1;
    this.menuOpen = false;
    this.linkError = '';
  }

  async link() {
    const gramps_id = this.placePick?.id;
    const relation = this.linkRef.trim();
    if (!gramps_id || !relation || this.linking) return;
    this.linking = true;
    this.linkError = '';
    try {
      const r = await post('/places/api/set-relation', { gramps_id, relation });
      if (r.boundary_error) {
        this.linkError = `${r.name} (${r.gramps_id}) is linked but its boundary wasn't fetched: `
          + `${r.boundary_error}. Retry later.`;
      }
      this.placePick = null;
      this.linkRef = '';
      this.loadPlaces();
    } catch (e) {
      this.linkError = e.message;
    } finally {
      this.linking = false;
    }
  }

  render() {
    const items = this.placeMatches();
    return html`
      ${super.render()}
      <div class="medium-space"></div>
      <h6 class="small">Link a place by hand</h6>
      <div class="chosen-media">
        ${this.placePick ? html`
          <div>
            <div>${this.placePick.label}</div>
            <div class="small-text secondary-text mono">${this.placePick.sub}</div>
          </div>` : nothing}
      </div>
      <nav class="wrap">
        ${searchMenu({
    label: 'Select', icon: 'add_link',
    value: this.placeQ, items, active: this.hiP, open: this.menuOpen,
    onToggle: () => { this.menuOpen = !this.menuOpen; }, onClose: () => { this.menuOpen = false; },
    onInput: (e) => { this.placeQ = e.target.value; this.hiP = -1; },
    onPick: (it) => this.pickPlace(it),
    onEnter: () => { if (this.hiP >= 0 && this.hiP < items.length) this.pickPlace(items[this.hiP]); },
    onMove: (d) => { if (items.length) this.hiP = (this.hiP + d + items.length) % items.length; },
    empty: !this.placeQ.trim() ? '' : this.placeList ? 'No Gramps place matches' : 'Loading places...',
  })}
        ${field('OSM relation or URL', this.linkRef, (e) => (this.linkRef = e.target.value),
          { width: 'medium', onEnter: () => this.link() })}
        ${btn(this.linking ? 'Linking...' : 'Link',
          this.linking || !this.placePick || !this.linkRef.trim(), () => this.link())}
        ${this.linking ? spinner : nothing}
      </nav>
      ${this.linkError ? html`<p>${statusLine('error', this.linkError)}</p>` : nothing}`;
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
