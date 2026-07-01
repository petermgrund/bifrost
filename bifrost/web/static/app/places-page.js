import { BifrostElement, html, nothing, api, post, iconYes, iconNo, iconNa, btn, spinner, chip, field } from './core.js';

class PlacesPage extends BifrostElement {
  static properties = {
    rows: { state: true },
    grampsUrl: { state: true },
    query: { state: true },
    filter: { state: true },     // all | relation | missing
    busy: { state: true },       // handle currently generating, or 'all'
    status: { state: true },
    failures: { state: true },   // [{gramps_id, title, detail}] from last bulk run
  };

  constructor() {
    super();
    this.rows = null;
    this.grampsUrl = '';
    this.query = '';
    this.filter = 'relation';
    this.busy = null;
    this.status = '';
    this.failures = [];
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load(refresh = false) {
    const r = await api(`/places/api/list${refresh ? '?refresh=1' : ''}`);
    this.rows = r.places;
    this.grampsUrl = r.gramps_url;
  }

  async addRelation(row, value) {
    if (!value.trim()) return;
    this.status = '';
    try {
      await post('/places/api/set-relation', { handle: row.handle, relation: value });
      await this.load(true);
    } catch (e) {
      this.status = `${row.gramps_id}: ${e.message}`;
    }
  }

  async generate(row, force) {
    this.busy = row.handle;
    this.status = '';
    try {
      await post('/places/api/generate', { handle: row.handle, force });
      await this.load(true);
    } catch (e) {
      this.status = `${row.gramps_id}: ${e.message}`;
    } finally {
      this.busy = null;
    }
  }

  async generateMissing() {
    this.busy = 'all';
    this.status = 'Generating…';
    this.failures = [];
    try {
      const r = await post('/places/api/generate-missing', {});
      const c = (r.events.find((e) => e.kind === 'summary') || {}).data || {};
      this.failures = r.events
        .filter((e) => e.kind === 'item' && e.action === 'failed')
        .map((e) => ({ gramps_id: e.gramps_id, title: e.title, detail: e.detail }));
      this.status = `Generated ${c.generated || 0}` +
        (c.errors ? `, ${c.errors} failed` : '');
      await this.load(true);
    } catch (e) {
      this.status = e.message;
    } finally {
      this.busy = null;
    }
  }

  render() {
    if (!this.rows) return html`<h5>Places</h5><p class="hint">Loading…</p>`;
    const q = this.query.toLowerCase();
    const filtered = this.rows
      .filter((r) => !q || r.name.toLowerCase().includes(q) || r.gramps_id.toLowerCase().includes(q))
      .filter((r) =>
        this.filter === 'all' ||
        (this.filter === 'relation' && r.osm_id) ||
        (this.filter === 'missing' && r.osm_id && !r.has_boundary));
    const missing = this.rows.filter((r) => r.osm_id && !r.has_boundary).length;
    return html`
      <div class="row">
        <h5 class="max">Places</h5>
        ${missing ? btn('filled',
          this.busy === 'all' ? 'Generating…' : `Generate missing (${missing})`,
          !!this.busy, () => this.generateMissing()) : nothing}
        ${this.busy === 'all' ? spinner : nothing}
        ${btn('outlined', 'Refresh', false, () => this.load(true))}
      </div>
      <p class="hint">OSM boundary polygons for the Gramps place minimap.</p>
      <div class="row wrap">
        ${field('Search places…', this.query, (e) => (this.query = e.target.value), { type: 'search', style: 'max-width:16rem' })}
        ${chip('With OSM link', this.filter === 'relation', () => (this.filter = 'relation'))}
        ${chip('Missing boundary', this.filter === 'missing', () => (this.filter = 'missing'))}
        ${chip('All places', this.filter === 'all', () => (this.filter = 'all'))}
        <span class="hint">${filtered.length} shown</span>
        ${this.status ? html`<span class="hint action-failed">${this.status}</span>` : nothing}
      </div>
      <table class="stripes">
        <thead><tr><th>id</th><th>place</th><th>OSM</th><th>boundary</th><th></th></tr></thead>
        <tbody>${filtered.map((r) => html`<tr>
          <td class="hint mono">${r.gramps_id}</td>
          <td>${this.grampsUrl
            ? html`<a class="link" href="${this.grampsUrl}/place/${r.gramps_id}" target="_blank">${r.name}</a>`
            : r.name}</td>
          <td class="hint">${r.osm_id
            ? html`<a class="link" href="https://www.openstreetmap.org/${r.osm_type}/${r.osm_id}" target="_blank">${r.osm_type} ${r.osm_id}</a>`
            : html`<div class="field border small" style="max-width:14rem">
                <input placeholder="relation/way id or URL"
                  @keydown=${(e) => { if (e.key === 'Enter') this.addRelation(r, e.target.value); }}
                  @change=${(e) => this.addRelation(r, e.target.value)}>
              </div>`}</td>
          <td title=${!r.osm_id ? 'no OSM link yet' : r.has_boundary ? 'boundary present' : 'no boundary — generate'}>
            ${!r.osm_id ? iconNa : r.has_boundary ? iconYes : iconNo}</td>
          <td>${r.osm_id ? html`<button class="transparent primary-text small" ?disabled=${!!this.busy}
            @click=${() => this.generate(r, r.has_boundary)}>
            ${this.busy === r.handle ? '…' : r.has_boundary ? 'Regenerate' : 'Generate'}</button>` : nothing}</td>
        </tr>`)}</tbody>
      </table>
      ${this.failures.length ? html`<h6 class="action-failed">Failed (${this.failures.length})</h6>
        <table class="stripes">
          <tbody>${this.failures.map((f) => html`<tr>
            <td class="hint mono">${f.gramps_id}</td><td>${f.title}</td>
            <td class="hint action-failed">${f.detail}</td></tr>`)}</tbody>
        </table>` : nothing}`;
  }
}
customElements.define('places-page', PlacesPage);
