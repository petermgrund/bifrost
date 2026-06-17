import { BifrostElement, html, nothing, api, post, iconYes, iconPending, iconHalf } from './core.js';

/* Mint random-6 media ids ahead of time, reserve them, and track which were
   actually minted. Reserved ids are excluded from the sync auto-generator but
   accepted as manual ids at sync time. See docs/MEDIA_ID_SCHEME.md. */
class IdgenPage extends BifrostElement {
  static properties = {
    rows: { state: true },        // all reservations
    generated: { state: true },   // ids from the last Generate click (highlighted)
    count: { state: true },
    filter: { state: true },      // all | reserved | minted
    busy: { state: true },
    status: { state: true },
  };

  constructor() {
    super();
    this.rows = null;
    this.generated = [];
    this.count = 5;
    this.filter = 'all';
    this.busy = false;
    this.status = '';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    const r = await api('/idgen/api/list');
    this.rows = r.ids;
  }

  async generate() {
    this.busy = true;
    this.status = '';
    try {
      const r = await post('/idgen/api/generate', { count: this.count });
      this.generated = r.generated;
      this.rows = r.ids;
    } catch (e) {
      this.status = e.message;
    } finally {
      this.busy = false;
    }
  }

  async release(id) {
    this.status = '';
    try {
      const r = await post('/idgen/api/release', { gramps_id: id });
      this.rows = r.ids;
      this.generated = this.generated.filter((g) => g !== id);
    } catch (e) {
      this.status = `${id}: ${e.message}`;
    }
  }

  // assigned = "I've labelled a photo with this id" — an intermediate step
  // before the sync actually mints it into Gramps.
  async setAssigned(id, on) {
    this.status = '';
    try {
      const r = await post(`/idgen/api/${on ? 'assign' : 'unassign'}`, { gramps_id: id });
      this.rows = r.ids;
    } catch (e) {
      this.status = `${id}: ${e.message}`;
    }
  }

  copy(text) {
    navigator.clipboard?.writeText(text);
    this.status = `copied ${text}`;
  }

  // Three-state lifecycle: reserved → assigned (written on a photo) → minted
  // (created in Gramps). `assigned` is only ever true while still un-minted.
  state(r) { return r.minted ? 'minted' : r.assigned ? 'assigned' : 'reserved'; }

  render() {
    if (!this.rows) return html`<h1>IDs</h1><div class="hint">Loading…</div>`;
    const minted = this.rows.filter((r) => r.minted).length;
    const assigned = this.rows.filter((r) => r.assigned).length;
    const reserved = this.rows.length - minted - assigned;
    const shown = this.rows.filter((r) =>
      this.filter === 'all' || this.filter === this.state(r));
    const chip = (f, label) => html`<button class="chip ${this.filter === f ? 'active' : ''}"
      @click=${() => (this.filter = f)}>${label}</button>`;
    return html`
      <div class="pagehead">
        <h1>IDs</h1>
        <span class="spacer"></span>
        <span class="hint">${reserved} reserved · ${assigned} assigned · ${minted} minted</span>
      </div>
      <p class="hint">Random-6 media ids minted ahead of time — write them on photo
        versos or name files. Reserved ids are never auto-assigned by a sync, but
        you can type one in as a manual id on the Sync preview. Mark an id
        <b>assigned</b> once you've labelled a photo with it; it becomes
        <b>minted</b> when a sync actually creates it in Gramps.</p>
      <details class="scheme">
        <summary class="hint">Copy / verso naming scheme</summary>
        <table class="results">
          <tr><th>name</th><th>meaning</th></tr>
          <tr><td><code>VGRN54</code></td><td>the copy on Gramps Web (canonical)</td></tr>
          <tr><td><code>VGRN54_o</code></td><td>original — only when the Gramps copy is edited</td></tr>
          <tr><td><code>VGRN54_c##</code></td><td>crop / derived from the full image (files only)</td></tr>
          <tr><td><code>VGRN54_d##</code></td><td>duplicate of the full image (incl. extra physical prints)</td></tr>
          <tr><td><code>VGRN54_v##</code></td><td>scan of the verso (back) of a physical print (files only)</td></tr>
          <tr><td><code>VGRN54_a##</code></td><td>AI-edited (files only)</td></tr>
        </table>
        <p class="hint">Verso: base id for the canonical print, <code>_d##</code> for
          extra physical copies. <code>##</code> = 2 chars from the same safe alphabet.</p>
      </details>
      <div class="toolbar">
        <label class="hint">Generate
          <input type="number" min="1" max="50" .value=${String(this.count)}
            style="width:4rem"
            @input=${(e) => (this.count = parseInt(e.target.value, 10) || 1)}></label>
        <button class="primary" ?disabled=${this.busy} @click=${this.generate}>
          ${this.busy ? 'Generating…' : 'Generate'}</button>
        ${this.status ? html`<span class="hint">${this.status}</span>` : nothing}
      </div>

      ${this.generated.length ? html`<div class="idgrid">
        ${this.generated.map((id) => html`<button class="idchip" title="copy"
          @click=${() => this.copy(id)}>${id}</button>`)}
      </div>` : nothing}

      <div class="toolbar">
        ${chip('all', 'All')}${chip('reserved', 'Reserved')}${chip('assigned', 'Assigned')}${chip('minted', 'Minted')}
        <span class="hint">${shown.length} shown</span>
      </div>
      <table class="results">
        <tr><th>id</th><th>status</th><th>minted as</th><th>generated</th><th></th></tr>
        ${shown.map((r) => this.row(r))}
      </table>`;
  }

  row(r) {
    const s = this.state(r);
    const STATUS = {
      reserved: [iconPending, 'reserved', 'hint'],
      assigned: [iconHalf, 'assigned', 'action-assigned'],
      minted: [iconYes, 'minted', 'action-created'],
    }[s];
    return html`<tr>
      <td><button class="idlink" @click=${() => this.copy(r.gramps_id)}
        title="copy">${r.gramps_id}</button></td>
      <td class="${STATUS[2]}">${STATUS[0]} ${STATUS[1]}</td>
      <td class="hint">${r.minted && r.source_system
        ? `${r.source_system}${r.source_title ? ` · ${r.source_title}` : ''}` : ''}</td>
      <td class="hint">${(r.created_at || '').slice(0, 10)}</td>
      <td>${s === 'minted' ? nothing : html`
        ${s === 'reserved'
          ? html`<button class="applyone" title="Mark as written on a photo"
              @click=${() => this.setAssigned(r.gramps_id, true)}>Assign</button>`
          : html`<button class="applyone" title="Back to reserved"
              @click=${() => this.setAssigned(r.gramps_id, false)}>Unassign</button>`}
        <button class="applyone" @click=${() => this.release(r.gramps_id)}>Release</button>`}</td>
    </tr>`;
  }
}
customElements.define('idgen-page', IdgenPage);
