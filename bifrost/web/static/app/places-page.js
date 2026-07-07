/* Places section — one management table: every Gramps place, its OSM link,
   and whether a boundary polygon exists; link + generate inline per row,
   plus a bulk 'Generate missing' run. */
import { BifrostElement, html, nothing, api, post, iconYes, iconNo, iconNa, btn, spinner, chip, field, summarize, emptyRow, statusLine } from './core.js';

class PlacesPage extends BifrostElement {
  static properties = {
    rows: { state: true },
    loadError: { state: true },
    grampsUrl: { state: true },
    query: { state: true },
    filter: { state: true },     // all | relation | missing
    busy: { state: true },       // handle currently generating, or 'all'
    result: { state: true },     // {kind, body} | null
    failures: { state: true },   // [{gramps_id, title, detail}] from last bulk run
  };

  constructor() {
    super();
    this.rows = null;
    this.loadError = '';
    this.grampsUrl = '';
    this.query = '';
    this.filter = 'relation';
    this.busy = null;
    this.result = null;
    this.failures = [];
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load(refresh = false) {
    this.loadError = '';
    try {
      const r = await api(`/places/api/list${refresh ? '?refresh=1' : ''}`);
      this.rows = r.places;
      this.grampsUrl = r.gramps_url;
    } catch (e) {
      this.loadError = e.message;
    }
  }

  async addRelation(row, value) {
    if (!value.trim()) return;
    // Enter fires keydown AND change on a modified input — the guard makes
    // the second, concurrent call for the same row a no-op.
    this.relBusy ??= new Set();
    if (this.relBusy.has(row.handle)) return;
    this.relBusy.add(row.handle);
    this.result = null;
    try {
      await post('/places/api/set-relation', { handle: row.handle, relation: value });
      await this.load(true);
    } catch (e) {
      this.result = { kind: 'error', body: `${row.gramps_id}: ${e.message}` };
    } finally {
      this.relBusy.delete(row.handle);
    }
  }

  async generate(row, force) {
    this.busy = row.handle;
    this.result = null;
    try {
      await post('/places/api/generate', { handle: row.handle, force });
      await this.load(true);
    } catch (e) {
      this.result = { kind: 'error', body: `${row.gramps_id}: ${e.message}` };
    } finally {
      this.busy = null;
    }
  }

  async generateMissing() {
    this.busy = 'all';
    this.result = null;
    this.failures = [];
    try {
      const r = await post('/places/api/generate-missing', {});
      const c = (r.events.find((e) => e.kind === 'summary') || {}).data || {};
      this.failures = r.events
        .filter((e) => e.kind === 'item' && e.action === 'failed')
        .map((e) => ({ gramps_id: e.gramps_id, title: e.title, detail: e.detail }));
      this.result = { kind: c.errors ? 'error' : 'ok', body: summarize(c, true) };
      await this.load(true);
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = null;
    }
  }

  render() {
    if (this.loadError && !this.rows) {
      return html`
        <p>${statusLine('error', this.loadError)}</p>
        <nav>${btn('Retry', false, () => this.load())}</nav>`;
    }
    if (!this.rows) return html`<progress class="circle"></progress>`;
    const q = this.query.toLowerCase();
    const filtered = this.rows
      .filter((r) => !q || r.name.toLowerCase().includes(q) || r.gramps_id.toLowerCase().includes(q))
      .filter((r) =>
        this.filter === 'all' ||
        (this.filter === 'relation' && r.osm_id) ||
        (this.filter === 'missing' && r.osm_id && !r.has_boundary));
    const linked = this.rows.filter((r) => r.osm_id).length;
    const missing = this.rows.filter((r) => r.osm_id && !r.has_boundary).length;
    return html`
      <nav>
        <div class="max"></div>
        ${missing ? btn(
          this.busy === 'all' ? 'Generating…' : `Generate missing (${missing})`,
          !!this.busy, () => this.generateMissing()) : nothing}
        ${this.busy === 'all' ? spinner : nothing}
        ${btn('Refresh', false, () => this.load(true))}
        ${this.result ? statusLine(this.result.kind, this.result.body) : nothing}
      </nav>
      ${this.loadError ? html`<p>${statusLine('error', `Reload failed — the table may be stale: ${this.loadError}`)}</p>` : nothing}

      <nav class="wrap">
        ${field('Search places…', this.query, (e) => (this.query = e.target.value), { type: 'search', width: 'small' })}
        ${chip(`With OSM link ${linked}`, this.filter === 'relation', () => (this.filter = 'relation'))}
        ${chip(`Missing boundary ${missing}`, this.filter === 'missing', () => (this.filter = 'missing'))}
        ${chip(`All places ${this.rows.length}`, this.filter === 'all', () => (this.filter = 'all'))}
        <span class="small-text">${filtered.length} shown</span>
      </nav>
      <table>
        <thead><tr><th>ID</th><th>Place</th><th>OSM</th><th>Boundary</th><th></th></tr></thead>
        <tbody>${filtered.length ? filtered.map((r) => html`<tr>
          <td class="mono small-text">${r.gramps_id}</td>
          <td>${this.grampsUrl
            ? html`<a class="link" href="${this.grampsUrl}/place/${r.gramps_id}" target="_blank" rel="noopener">${r.name}</a>`
            : r.name}</td>
          <td>${r.osm_id
            ? html`<a class="link small-text" href="https://www.openstreetmap.org/${r.osm_type}/${r.osm_id}" target="_blank" rel="noopener">${r.osm_type} ${r.osm_id}</a>`
            : field('OSM relation or URL', '', () => {}, {
                small: true, width: 'small',
                onEnter: (e) => this.addRelation(r, e.target.value),
                onChange: (e) => this.addRelation(r, e.target.value),
              })}</td>
          <td title=${!r.osm_id ? 'no OSM link yet' : r.has_boundary ? 'boundary present' : 'no boundary — generate'}>
            ${!r.osm_id ? iconNa : r.has_boundary ? iconYes : iconNo}</td>
          <td>${r.osm_id ? html`<button class="small" ?disabled=${!!this.busy}
            @click=${() => this.generate(r, r.has_boundary)}>
            ${this.busy === r.handle ? 'Generating…' : r.has_boundary ? 'Regenerate' : 'Generate'}</button>` : nothing}</td>
        </tr>`) : emptyRow(5, 'No places match this filter.')}</tbody>
      </table>
      ${this.failures.length ? html`
        <div class="large-space"></div>
        <h6 class="small">Failed (${this.failures.length})</h6>
        <table>
          <tbody>${this.failures.map((f) => html`<tr>
            <td class="mono small-text">${f.gramps_id}</td><td>${f.title}</td>
            <td class="small-text error-text">${f.detail}</td></tr>`)}</tbody>
        </table>` : nothing}`;
  }
}
customElements.define('places-page', PlacesPage);
