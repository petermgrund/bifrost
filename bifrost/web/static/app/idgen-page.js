import { BifrostElement, html, nothing, api, post, iconYes, iconPending, iconHalf, btn, spinner, chip, field } from './core.js';

/* Mint random-6 media ids ahead of time, reserve them, and track which were
   actually minted. Reserved ids are excluded from the sync auto-generator but
   accepted as manual ids at sync time. See docs/MEDIA_ID_SCHEME.md. */
class IdgenPage extends BifrostElement {
  static properties = {
    rows: { state: true },        // all reservations
    generated: { state: true },   // ids from the last Generate click (highlighted)
    count: { state: true },
    note: { state: true },        // optional note applied to the generated batch
    filter: { state: true },      // all | reserved | minted
    busy: { state: true },
    status: { state: true },
    scans: { state: true },       // a-series register overview
    sCount: { state: true },
    sContainer: { state: true },
    sNote: { state: true },
    sBusy: { state: true },
    sRegistered: { state: true }, // scan numbers from the last Register click
  };

  constructor() {
    super();
    this.rows = null;
    this.generated = [];
    this.count = 5;
    this.note = '';
    this.filter = 'all';
    this.busy = false;
    this.status = '';
    this.scans = null;
    this.sCount = 1;
    this.sContainer = '';
    this.sNote = '';
    this.sBusy = false;
    this.sRegistered = [];
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    const [r, s] = await Promise.all([api('/idgen/api/list'), api('/idgen/api/scans')]);
    this.rows = r.ids;
    this.scans = s;
  }

  async generate() {
    this.busy = true;
    this.status = '';
    try {
      const r = await post('/idgen/api/generate', { count: this.count, note: this.note || null });
      this.generated = r.generated;
      this.rows = r.ids;
    } catch (e) {
      this.status = e.message;
    } finally {
      this.busy = false;
    }
  }

  async registerScans() {
    this.sBusy = true;
    this.status = '';
    try {
      const r = await post('/idgen/api/scans/register', {
        count: this.sCount, container: this.sContainer || null, note: this.sNote || null });
      this.sRegistered = r.registered;
      this.scans = r;
    } catch (e) {
      this.status = e.message;
    } finally {
      this.sBusy = false;
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
    if (!this.rows) return html`<h5>IDs</h5><p class="hint">Loading…</p>`;
    const minted = this.rows.filter((r) => r.minted).length;
    const assigned = this.rows.filter((r) => r.assigned).length;
    const reserved = this.rows.length - minted - assigned;
    const shown = this.rows.filter((r) =>
      this.filter === 'all' || this.filter === this.state(r));
    return html`
      <div class="row">
        <h5 class="max">IDs</h5>
        <span class="hint">${reserved} reserved · ${assigned} assigned · ${minted} minted</span>
      </div>
      <p class="hint">Random-6 media ids minted ahead of time — write them on photo
        versos or name files. Reserved ids are never auto-assigned by a sync, but
        you can type one in as a manual id on the Sync preview. Mark an id
        <b>assigned</b> once you've labelled a photo with it; it becomes
        <b>minted</b> when a sync actually creates it in Gramps.</p>
      <details class="border round">
        <summary class="padding hint">Copy / verso naming scheme</summary>
        <div class="padding">
          <table>
            <thead><tr><th>name</th><th>meaning</th></tr></thead>
            <tbody>
              <tr><td><code>VGRN54</code></td><td>the copy on Gramps Web (canonical)</td></tr>
              <tr><td><code>VGRN54_o</code></td><td>original — only when the Gramps copy is edited</td></tr>
              <tr><td><code>VGRN54_c##</code></td><td>crop / derived from the full image (files only)</td></tr>
              <tr><td><code>VGRN54_d##</code></td><td>duplicate of the full image (incl. extra physical prints)</td></tr>
              <tr><td><code>VGRN54_v##</code></td><td>scan of the verso (back) of a physical print (files only)</td></tr>
              <tr><td><code>VGRN54_a##</code></td><td>AI-edited (files only)</td></tr>
            </tbody>
          </table>
          <p class="hint">Verso: base id for the canonical print, <code>_d##</code> for
            extra physical copies. <code>##</code> = 01–99, plain decimal (suffixes are
            machine-only filing, never handwritten — SCHEME.md §1).</p>
        </div>
      </details>
      <div class="row wrap">
        ${field('Generate', this.count, (e) => (this.count = parseInt(e.target.value, 10) || 1),
          { type: 'number', style: 'max-width:7rem' })}
        ${field('Note (optional)', this.note, (e) => (this.note = e.target.value), { style: 'max-width:16rem' })}
        ${btn('filled', this.busy ? 'Generating…' : 'Generate', this.busy, () => this.generate())}
        ${this.busy ? spinner : nothing}
        ${this.status ? html`<span class="hint">${this.status}</span>` : nothing}
      </div>

      ${this.generated.length ? html`<div class="row wrap">
        ${this.generated.map((id) => html`<button class="chip fill idchip" title="copy"
          @click=${() => this.copy(id)}>${id}</button>`)}
      </div>` : nothing}

      <div class="row wrap">
        ${chip('All', this.filter === 'all', () => (this.filter = 'all'))}
        ${chip('Reserved', this.filter === 'reserved', () => (this.filter = 'reserved'))}
        ${chip('Assigned', this.filter === 'assigned', () => (this.filter = 'assigned'))}
        ${chip('Minted', this.filter === 'minted', () => (this.filter = 'minted'))}
        <span class="hint">${shown.length} shown</span>
      </div>
      <table class="stripes">
        <thead><tr><th>id</th><th>status</th><th>minted as</th><th>note</th><th>generated</th><th></th></tr></thead>
        <tbody>${shown.map((r) => this.row(r))}</tbody>
      </table>

      ${this.scansSection()}`;
  }

  /* The a-series scan register: one number per capture file, append-only from
     a000101, in scanning order. A log, not a catalog — see SCHEME.md §2. */
  scansSection() {
    if (!this.scans) return nothing;
    const s = this.scans;
    return html`
      <div class="row" style="margin-top:2.5rem">
        <h5 class="max">Scan numbers</h5>
        <span class="hint">next <b class="mono">${s.next}</b> · ${s.total} registered · ${s.linked} linked to ids</span>
      </div>
      <p class="hint">The a-series digitization log. Register a batch when you scan a
        container: every capture file — recto or verso — takes the next number, in
        scanning order. Numbers are never reused; a deleted scan stays a gap. Name the
        files <code>a000277.tif/.jpg</code>; the contact sheet and the ArchivesSpace
        digital objects carry the same numbers.</p>
      <div class="row wrap">
        ${field('Register', this.sCount, (e) => (this.sCount = parseInt(e.target.value, 10) || 1),
          { type: 'number', style: 'max-width:7rem' })}
        ${field('Container (e.g. JGS-B01)', this.sContainer, (e) => (this.sContainer = e.target.value),
          { style: 'max-width:13rem', mono: true })}
        ${field('Note (optional)', this.sNote, (e) => (this.sNote = e.target.value), { style: 'max-width:16rem' })}
        ${btn('filled', this.sBusy ? 'Registering…' : 'Register', this.sBusy, () => this.registerScans())}
        ${this.sBusy ? spinner : nothing}
      </div>
      ${this.sRegistered.length ? html`<p class="hint">Registered
        <b class="mono">${this.sRegistered[0]}</b>${this.sRegistered.length > 1
          ? html` – <b class="mono">${this.sRegistered[this.sRegistered.length - 1]}</b>` : nothing}
        (${this.sRegistered.length})</p>` : nothing}
      <table class="stripes">
        <thead><tr><th>scan</th><th>container</th><th>role</th><th>object id</th><th>note</th></tr></thead>
        <tbody>${s.recent.map((r) => html`<tr>
          <td><code>${r.scan_no}</code></td>
          <td class="hint mono">${r.container || ''}</td>
          <td class="hint">${r.role || ''}</td>
          <td>${r.object_id ? html`<code>${r.object_id}</code>` : ''}</td>
          <td class="hint">${r.note || ''}</td>
        </tr>`)}</tbody>
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
      <td><button class="transparent primary-text idchip small" title="copy"
        @click=${() => this.copy(r.gramps_id)}>${r.gramps_id}</button></td>
      <td class="${STATUS[2]}">${STATUS[0]} ${STATUS[1]}</td>
      <td class="hint">${r.minted && r.source_system
        ? `${r.source_system}${r.source_title ? ` · ${r.source_title}` : ''}` : ''}</td>
      <td class="hint">${r.note || ''}</td>
      <td class="hint">${(r.created_at || '').slice(0, 10)}</td>
      <td>${s === 'minted' ? nothing : html`
        ${s === 'reserved'
          ? html`<button class="transparent primary-text small" title="Mark as written on a photo"
              @click=${() => this.setAssigned(r.gramps_id, true)}>Assign</button>`
          : html`<button class="transparent primary-text small" title="Back to reserved"
              @click=${() => this.setAssigned(r.gramps_id, false)}>Unassign</button>`}
        <button class="transparent primary-text small" @click=${() => this.release(r.gramps_id)}>Release</button>`}</td>
    </tr>`;
  }
}
customElements.define('idgen-page', IdgenPage);
