/* Places section — look up one place by Gramps ID; a dialog shows its OSM
   link and boundary status with the set-relation / generate actions. The
   place list still loads once behind the scenes (lookups + missing count),
   plus a bulk 'Generate missing' run. */
import { BifrostElement, html, nothing, api, post, iconYes, iconNo, iconNa, btn, spinner, field, summarize, statusLine } from './core.js';

class PlacesPage extends BifrostElement {
  static properties = {
    rows: { state: true },
    loadError: { state: true },
    grampsUrl: { state: true },
    placeId: { state: true },
    popup: { state: true },      // the looked-up place row, or null
    editingOsm: { state: true }, // the popup's OSM cell is in edit mode
    busy: { state: true },       // handle currently generating, or 'all'
    result: { state: true },     // {kind, body} | null
    failures: { state: true },   // [{gramps_id, title, detail}] from last bulk run
  };

  constructor() {
    super();
    this.rows = null;
    this.loadError = '';
    this.grampsUrl = '';
    this.placeId = '';
    this.popup = null;
    this.editingOsm = false;
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
      if (this.popup) {
        this.popup = this.rows.find((p) => p.handle === this.popup.handle) || null;
      }
    } catch (e) {
      this.loadError = e.message;
    }
  }

  lookup() {
    const id = this.placeId.trim().toUpperCase();
    if (!id) return;
    const row = (this.rows || []).find((r) => r.gramps_id.toUpperCase() === id);
    if (!row) {
      this.result = { kind: 'error', body: `No place '${id}'` };
      return;
    }
    this.result = null;
    this.editingOsm = false;
    this.popup = row;
  }

  closePopup() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg?.open) dlg.close();          // fires @close, which clears the state
    else { this.popup = null; this.result = null; }
  }

  /* The dialog must sit in the browser's top layer (showModal) — rendered
     inline it would be clipped to the section expander's content box. */
  updated() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg && !dlg.open) dlg.showModal();
  }

  async addRelation(row, value, replace = false) {
    if (!value.trim()) return;
    // Enter fires keydown AND change on a modified input — the guard makes
    // the second, concurrent call for the same row a no-op.
    this.relBusy ??= new Set();
    if (this.relBusy.has(row.handle)) return;
    this.relBusy.add(row.handle);
    this.result = null;
    try {
      await post('/places/api/set-relation', { handle: row.handle, relation: value, replace });
      await this.load(true);
      this.editingOsm = false;
      if (replace) {
        this.result = { kind: 'ok', body: 'OSM link updated — regenerate the boundary to match.' };
      }
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
    const missing = this.rows.filter((r) => r.osm_id && !r.has_boundary).length;
    return html`
      <nav class="wrap">
        ${field('Gramps place ID', this.placeId, (e) => (this.placeId = e.target.value),
          { mono: true, upper: true, width: 'small', onEnter: () => this.lookup() })}
        ${btn('Look up', false, () => this.lookup())}
        ${btn('Refresh', false, () => this.load(true), 'border')}
        <div class="max"></div>
        ${missing ? btn(
          this.busy === 'all' ? 'Generating…' : `Generate missing (${missing})`,
          !!this.busy, () => this.generateMissing()) : nothing}
        ${this.busy === 'all' ? spinner : nothing}
      </nav>
      ${!this.popup && this.result ? html`<p>${statusLine(this.result.kind, this.result.body)}</p>` : nothing}
      ${this.loadError ? html`<p>${statusLine('error', `Reload failed — shown data may be stale: ${this.loadError}`)}</p>` : nothing}
      ${this.failures.length ? html`
        <div class="large-space"></div>
        <h6 class="small">Failed (${this.failures.length})</h6>
        <table>
          <tbody>${this.failures.map((f) => html`<tr>
            <td class="mono small-text">${f.gramps_id}</td><td>${f.title}</td>
            <td class="small-text error-text">${f.detail}</td></tr>`)}</tbody>
        </table>` : nothing}
      ${this.popup ? this.renderPopup(this.popup) : nothing}`;
  }

  renderPopup(r) {
    return html`
      <dialog @close=${() => { this.popup = null; this.result = null; this.editingOsm = false; }}>
        <nav>
          <h5 class="max small">${this.grampsUrl
            ? html`<a class="link" href="${this.grampsUrl}/place/${r.gramps_id}" target="_blank" rel="noopener">${r.name}</a>`
            : r.name}</h5>
          <button class="circle transparent" @click=${() => this.closePopup()} aria-label="Close">
            <i>close</i></button>
        </nav>
        <table>
          <tbody>
            <tr>
              <td class="secondary-text">ID</td>
              <td class="mono">${r.gramps_id}</td>
            </tr>
            <tr>
              <td class="secondary-text">OSM</td>
              <td>${!r.osm_id || this.editingOsm
                ? html`<nav class="wrap">
                    ${field('OSM relation or URL', this.editingOsm ? `${r.osm_type}/${r.osm_id}` : '', () => {}, {
                      small: true, width: 'small',
                      onEnter: (e) => this.addRelation(r, e.target.value, this.editingOsm),
                      onChange: (e) => this.addRelation(r, e.target.value, this.editingOsm),
                    })}
                    ${this.editingOsm ? html`<button class="small"
                      @click=${() => (this.editingOsm = false)}>Cancel</button>` : nothing}
                  </nav>`
                : html`<nav class="wrap">
                    <a class="link" href="https://www.openstreetmap.org/${r.osm_type}/${r.osm_id}" target="_blank" rel="noopener">${r.osm_type} ${r.osm_id}</a>
                    <button class="small" @click=${() => (this.editingOsm = true)}>Edit</button>
                  </nav>`}</td>
            </tr>
            <tr>
              <td class="secondary-text">Boundary</td>
              <td>${!r.osm_id ? html`${iconNa}`
                : r.has_boundary ? html`${iconYes} present`
                : html`${iconNo} <span class="error-text">missing</span>`}</td>
            </tr>
          </tbody>
        </table>
        ${this.result ? html`<p>${statusLine(this.result.kind, this.result.body)}</p>` : nothing}
        <div class="space"></div>
        <nav>
          ${r.osm_id ? btn(
            this.busy === r.handle ? 'Generating…' : r.has_boundary ? 'Regenerate' : 'Generate',
            !!this.busy, () => this.generate(r, r.has_boundary)) : nothing}
          ${this.busy === r.handle ? spinner : nothing}
          ${btn('Close', false, () => this.closePopup())}
        </nav>
      </dialog>`;
  }
}
customElements.define('places-page', PlacesPage);
