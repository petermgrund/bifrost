import { BifrostElement, html, nothing, api, post, iconYes, iconNo } from './core.js';

class PlacesPage extends BifrostElement {
  static properties = {
    rows: { state: true },
    grampsUrl: { state: true },
    query: { state: true },
    filter: { state: true },     // all | relation | missing
    busy: { state: true },       // handle currently generating, or 'all'
    status: { state: true },
  };

  constructor() {
    super();
    this.rows = null;
    this.grampsUrl = '';
    this.query = '';
    this.filter = 'relation';
    this.busy = null;
    this.status = '';
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
    try {
      const r = await post('/places/api/generate-missing', {});
      const c = (r.events.find((e) => e.kind === 'summary') || {}).data || {};
      this.status = `Generated ${c.generated || 0}` +
        (c.errors ? `, ${c.errors} error(s)` : '');
      await this.load(true);
    } catch (e) {
      this.status = e.message;
    } finally {
      this.busy = null;
    }
  }

  render() {
    if (!this.rows) return html`<h1>Places</h1><div class="hint">Loading…</div>`;
    const q = this.query.toLowerCase();
    const filtered = this.rows
      .filter((r) => !q || r.name.toLowerCase().includes(q) || r.gramps_id.toLowerCase().includes(q))
      .filter((r) =>
        this.filter === 'all' ||
        (this.filter === 'relation' && r.relation) ||
        (this.filter === 'missing' && r.relation && !r.has_boundary));
    const missing = this.rows.filter((r) => r.relation && !r.has_boundary).length;
    const chip = (f, label) => html`<button class="chip ${this.filter === f ? 'active' : ''}"
      @click=${() => (this.filter = f)}>${label}</button>`;
    return html`
      <div class="pagehead">
        <h1>Places</h1>
        <span class="spacer"></span>
        ${missing ? html`<button class="primary" ?disabled=${this.busy}
          @click=${this.generateMissing}>
          ${this.busy === 'all' ? 'Generating…' : `Generate missing (${missing})`}</button>` : nothing}
        <button @click=${() => this.load(true)}>Refresh</button>
      </div>
      <p class="hint">Boundary polygons from OpenStreetMap relations — the amber
      outlines on the Gramps place minimaps. Add a relation URL to a place in
      Gramps to make it eligible.</p>
      <div class="toolbar">
        <input type="search" placeholder="Search places…" .value=${this.query}
          @input=${(e) => (this.query = e.target.value)}>
        ${chip('relation', 'With OSM relation')}${chip('missing', 'Missing boundary')}${chip('all', 'All places')}
        <span class="hint">${filtered.length} shown</span>
        ${this.status ? html`<span class="hint action-failed">${this.status}</span>` : nothing}
      </div>
      <table class="results">
        <tr><th>id</th><th>place</th><th>OSM relation</th><th>boundary</th><th></th></tr>
        ${filtered.map((r) => html`<tr>
          <td class="hint">${r.gramps_id}</td>
          <td>${this.grampsUrl
            ? html`<a href="${this.grampsUrl}/place/${r.gramps_id}" target="_blank">${r.name}</a>`
            : r.name}</td>
          <td class="hint">${r.relation
            ? html`<a href="https://www.openstreetmap.org/relation/${r.relation}" target="_blank">${r.relation}</a>`
            : html`<input class="relinput" type="text" placeholder="relation id or URL"
                @keydown=${(e) => { if (e.key === 'Enter') this.addRelation(r, e.target.value); }}
                @change=${(e) => this.addRelation(r, e.target.value)}>`}</td>
          <td>${r.has_boundary ? iconYes : iconNo}</td>
          <td>${r.relation ? html`<button class="applyone" ?disabled=${this.busy}
            @click=${() => this.generate(r, r.has_boundary)}>
            ${this.busy === r.handle ? '…' : r.has_boundary ? 'Regenerate' : 'Generate'}</button>` : nothing}</td>
        </tr>`)}
      </table>`;
  }
}
customElements.define('places-page', PlacesPage);
