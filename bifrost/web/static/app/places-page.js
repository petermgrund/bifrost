import { html, api, btn, field, progressLine, searchMenu } from './core.js';
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

class PlacesManualPage extends SyncPage {
  static properties = {
    placeList: { state: true },
    placeQ: { state: true },
    placePick: { state: true },
    hiP: { state: true },
    menuOpen: { state: true },
    linkRef: { state: true },
  };

  constructor() {
    super();
    this.placeList = null;
    this.placeQ = '';
    this.placePick = null;
    this.hiP = -1;
    this.menuOpen = false;
    this.linkRef = '';
  }

  get apiBase() { return '/places/api/manual'; }
  get jobName() { return 'places.manual'; }
  get itemColLabel() { return 'Gramps place'; }
  get lastColLabel() { return 'Place object'; }
  get scanHeading() { return 'Link places manually'; }
  get primaryEntity() { return 'place'; }
  previewBody() { return { gramps_id: this.placePick?.id, relation: this.linkRef.trim() }; }

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

  runAnother() {
    super.runAnother();
    this.placePick = null;
    this.linkRef = '';
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
      .map(({ p }) => ({ id: p.gramps_id, name: p.name, label: p.hierarchy.join(', ') || p.name,
        sub: p.gramps_id, mono: true }));
  }

  pickPlace(it) {
    this.placePick = it;
    this.placeQ = '';
    this.hiP = -1;
    this.menuOpen = false;
  }

  renderEmpty() {
    const items = this.placeMatches();
    const ready = !!this.placePick && !!this.linkRef.trim();
    return html`
      <h6 class="small">${this.scanHeading}</h6>
      <nav class="wrap">
        ${this.running ? progressLine(this.progress) : html`
          ${searchMenu({
    label: this.placePick ? this.placePick.name : 'Select place', icon: 'place',
    value: this.placeQ, items, active: this.hiP, open: this.menuOpen,
    onToggle: () => { this.menuOpen = !this.menuOpen; }, onClose: () => { this.menuOpen = false; },
    onInput: (e) => { this.placeQ = e.target.value; this.hiP = -1; },
    onPick: (it) => this.pickPlace(it),
    onEnter: () => { if (this.hiP >= 0 && this.hiP < items.length) this.pickPlace(items[this.hiP]); },
    onMove: (d) => { if (items.length) this.hiP = (this.hiP + d + items.length) % items.length; },
    empty: !this.placeQ.trim() ? '' : this.placeList ? 'No Gramps place matches' : 'Loading places...',
  })}
          ${field('OSM relation or URL', this.linkRef, (e) => (this.linkRef = e.target.value),
            { width: 'medium', onEnter: () => { if (ready) this.runPreview(); } })}
          ${btn('Scan', !ready, () => this.runPreview())}`}
      </nav>`;
  }
}
customElements.define('places-manual-page', PlacesManualPage);
