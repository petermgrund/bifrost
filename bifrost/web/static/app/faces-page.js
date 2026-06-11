import { BifrostElement, html, nothing, api, post } from './core.js';

class FacesPage extends BifrostElement {
  static properties = {
    tab: { state: true },
    gramps: { state: true },
    immich: { state: true },
    links: { state: true },
    listing: { state: true },
    selGramps: { state: true },
    selImmich: { state: true },
    photoFilter: { state: true },
    photoQuery: { state: true },
    grampsQuery: { state: true },
    immichQuery: { state: true },
    openAsset: { state: true },
    busy: { state: true },
  };

  constructor() {
    super();
    this.tab = 'photos';
    this.gramps = [];
    this.immich = [];
    this.links = [];
    this.listing = { photos: [], pending_total: 0 };
    this.selGramps = null;
    this.selImmich = null;
    this.photoFilter = 'all';
    this.photoQuery = '';
    this.grampsQuery = '';
    this.immichQuery = '';
    this.openAsset = null;
    this.busy = false;
  }

  connectedCallback() {
    super.connectedCallback();
    const f = new URLSearchParams(location.search).get('filter');
    if (['pending', 'manual', 'unlinked'].includes(f)) this.photoFilter = f;
    this.load();
  }

  async load(refresh = false) {
    const r = refresh ? '?refresh=1' : '';
    try {
      [this.gramps, this.immich, this.links] = await Promise.all([
        api(`/faces/api/gramps-people${r}`),
        api(`/faces/api/immich-people${r}`),
        api(`/faces/api/links`),
      ]);
      this.listing = await api(`/faces/api/photos${r}`);
    } catch (e) {
      this.listing = { photos: [], pending_total: 0, error: e.message };
    }
  }

  get linkByHandle() {
    return Object.fromEntries(this.links.map((l) => [l.gramps_handle, l]));
  }
  get linkByImmich() {
    return Object.fromEntries(this.links.map((l) => [l.immich_person_id, l]));
  }
  get openPhoto() {
    return this.listing.photos.find((p) => p.asset_id === this.openAsset);
  }

  /* ---- links ---- */
  async createLink() {
    if (!this.selGramps || !this.selImmich) return;
    this.links = await post('/faces/api/links', {
      gramps_handle: this.selGramps,
      immich_person_id: this.selImmich,
      label: this.renderRoot.querySelector('#link-label')?.value || null,
    });
    this.selGramps = this.selImmich = null;
    await this.load();
  }
  async unlink(handle) {
    this.links = await api(`/faces/api/links/${handle}`, { method: 'DELETE' });
    await this.load();
  }

  /* ---- faces ---- */
  async applyFace(face, pad) {
    try {
      const result = await post('/faces/api/face', {
        gramps_handle: face.gramps_handle,
        asset_id: this.openAsset,
        pad,
      });
      Object.assign(face, result);
      const p = this.openPhoto;
      p.pending_count = p.faces.filter((f) => ['pending', 'outdated'].includes(f.status)).length;
      this.listing = {
        ...this.listing,
        pending_total: this.listing.photos.reduce((n, x) => n + x.pending_count, 0),
      };
    } catch (e) {
      alert(e.message);
    }
  }
  async applyPending() {
    this.busy = true;
    try {
      await post('/faces/api/apply-pending', {});
      await this.load(true);
    } finally {
      this.busy = false;
    }
  }

  /* ---- render ---- */
  render() {
    return html`
      <div class="pagehead">
        <h1>Faces</h1>
        <div class="tabs">
          <button class="tab ${this.tab === 'photos' ? 'active' : ''}"
            @click=${() => (this.tab = 'photos')}>Photos</button>
          <button class="tab ${this.tab === 'people' ? 'active' : ''}"
            @click=${() => (this.tab = 'people')}>People</button>
        </div>
        <span class="spacer"></span>
        ${this.listing.pending_total
          ? html`<button class="primary" ?disabled=${this.busy} @click=${this.applyPending}>
              ${this.busy ? 'Applying…' : `Apply pending (${this.listing.pending_total})`}</button>`
          : nothing}
        <button @click=${() => this.load(true)}>Refresh</button>
      </div>
      ${this.tab === 'photos' ? this.renderPhotos() : this.renderPeople()}
      ${this.openAsset ? this.renderDetail() : nothing}
    `;
  }

  renderPhotos() {
    const q = this.photoQuery.toLowerCase();
    const rows = this.listing.photos
      .filter((p) => !q || p.title.toLowerCase().includes(q))
      .filter((p) =>
        this.photoFilter === 'all' ||
        (this.photoFilter === 'pending' && p.pending_count > 0) ||
        (this.photoFilter === 'manual' && p.is_manual) ||
        (this.photoFilter === 'unlinked' && p.faces.some((f) => f.status === 'unlinked')));
    const chip = (f, label) => html`<button
      class="chip ${this.photoFilter === f ? 'active' : ''}"
      @click=${() => (this.photoFilter = f)}>${label}</button>`;
    return html`
      <div class="toolbar">
        <input type="search" placeholder="Search photos…"
          .value=${this.photoQuery} @input=${(e) => (this.photoQuery = e.target.value)}>
        ${chip('all', 'All')}${chip('pending', 'Needs attention')}${chip('unlinked', 'No person link')}${chip('manual', 'Manual')}
      </div>
      <div class="photo-grid">
        ${rows.length ? rows.map((p) => this.photoCard(p))
          : html`<div class="hint">No photos.</div>`}
      </div>`;
  }

  photoCard(p) {
    return html`<div class="photo-card ${p.synced ? '' : 'unsynced'}"
      @click=${() => this.openDetail(p.asset_id)}>
      <img loading="lazy" src="/faces/api/thumb/asset/${p.asset_id}" alt="">
      <div class="body">
        <div class="title" title=${p.title}>${p.title}</div>
        <div class="meta">
          ${p.gramps_id || ''}
          ${p.pending_count ? html`<span class="badge">${p.pending_count} pending</span>` : nothing}
          ${p.synced ? nothing : html`<span class="badge unlinked">not in Gramps</span>`}
        </div>
      </div>
    </div>`;
  }

  openDetail(assetId) {
    this.openAsset = assetId;
  }

  renderDetail() {
    const p = this.openPhoto;
    if (!p) return nothing;
    const boxes = p.faces.filter((f) => f.status !== 'unlinked').map((f) => {
      const r = f.current_rect || f.expected_rect;
      if (!r) return nothing;
      return html`<div class="facebox ${f.status === 'applied' ? '' : 'pending'}"
        style="left:${r[0]}%;top:${r[1]}%;width:${r[2] - r[0]}%;height:${r[3] - r[1]}%">
        <span>${f.label || f.immich_name}</span></div>`;
    });
    return html`<div class="overlay" @click=${(e) => { if (e.currentTarget === e.target) this.openAsset = null; }}>
      <div class="detail-card">
        <div class="detail-head">
          <strong>${p.title}</strong>
          <span class="hint">${p.synced ? p.gramps_id : 'not in Gramps'}</span>
          <span class="spacer"></span>
          <button @click=${() => (this.openAsset = null)}>✕</button>
        </div>
        ${p.is_manual ? html`<div class="alert">A face here was drawn manually in Immich; default pad is 0%.</div>` : nothing}
        <div class="detail-body">
          <div class="imgwrap">
            <img src="/faces/api/thumb/asset/${p.asset_id}?size=preview" alt="">${boxes}
          </div>
          <div class="facelist">${p.faces.map((f) => this.faceRow(f)) }
            ${p.faces.length ? nothing : html`<div class="hint">No identified faces.</div>`}
          </div>
        </div>
      </div>
    </div>`;
  }

  faceRow(f) {
    if (f.status === 'unlinked') {
      return html`<div class="facerow">
        <img src="/faces/api/thumb/person/${f.immich_person_id}" alt="">
        <div class="who"><div>${f.immich_name}</div><div class="hint">not linked</div></div>
        <button class="linkjump" @click=${() => {
          this.openAsset = null; this.tab = 'people'; this.selImmich = f.immich_person_id;
        }}>Link…</button></div>`;
    }
    const padPct = Math.round(f.pad * 100);
    const statusTxt = {
      applied: 'applied', pending: 'pending', outdated: 'box moved',
      differs: 'manual — apply deliberately',
    }[f.status];
    return html`<div class="facerow s-${f.status}">
      <img src="/faces/api/thumb/person/${f.immich_person_id}" alt="">
      <div class="who"><div>${f.label || f.immich_name}</div><div class="hint">${statusTxt}</div></div>
      <div class="padctl">
        <input type="range" min="0" max="50" step="5" .value=${String(padPct)}
          @input=${(e) => (e.target.nextElementSibling.textContent = `${e.target.value}%`)}
          @change=${(e) => this.applyFace(f, Number(e.target.value) / 100)}>
        <span class="padval">${padPct}%</span>
        ${f.status === 'applied' ? nothing
          : html`<button class="applyone" @click=${() => this.applyFace(f, f.pad)}>Apply</button>`}
      </div></div>`;
  }

  async saveLabel(link, label) {
    this.links = await post('/faces/api/links', {
      gramps_handle: link.gramps_handle,
      immich_person_id: link.immich_person_id,
      label: label.trim() || null,
    });
  }

  renderPeople() {
    const byHandle = Object.fromEntries(this.gramps.map((p) => [p.handle, p]));
    const byId = Object.fromEntries(this.immich.map((p) => [p.id, p]));
    const rows = this.links
      .map((l) => ({ ...l, g: byHandle[l.gramps_handle], i: byId[l.immich_person_id] }))
      .sort((a, b) => (a.g?.name || '').localeCompare(b.g?.name || ''));
    return html`
      <h2>Linked people <span class="hint">(${rows.length})</span></h2>
      <table class="results people-table">
        <tr><th></th><th>Gramps person</th><th>Immich person</th><th>Label</th><th></th></tr>
        ${rows.map((l) => html`<tr>
          <td><img class="avatar" loading="lazy" src="/faces/api/thumb/person/${l.immich_person_id}" alt=""></td>
          <td>${l.g?.name || l.gramps_handle}</td>
          <td class="hint">${l.i?.name || '(unnamed)'}</td>
          <td><input type="text" .value=${l.label || ''} placeholder="—"
            @change=${(e) => this.saveLabel(l, e.target.value)}></td>
          <td><button class="unlink" @click=${() => this.unlink(l.gramps_handle)}>unlink</button></td>
        </tr>`)}
      </table>

      <h2>Link a new pair</h2>
      ${this.renderLinkPanes()}`;
  }

  renderLinkPanes() {
    const gq = this.grampsQuery.toLowerCase();
    const iq = this.immichQuery.toLowerCase();
    const lh = this.linkByHandle, li = this.linkByImmich;
    const both = this.selGramps && this.selImmich;
    return html`
      <div class="panes">
        <div class="pane">
          <input type="search" placeholder="Search Gramps people…"
            @input=${(e) => (this.grampsQuery = e.target.value)}>
          <div class="cardlist">
            ${this.gramps
              .filter((p) => !lh[p.handle])
              .filter((p) => !gq || p.name.toLowerCase().includes(gq))
              .map((p) => html`<div class="card ${this.selGramps === p.handle ? 'selected' : ''}"
                @click=${() => (this.selGramps = this.selGramps === p.handle ? null : p.handle)}>
                <span class="name">${p.name}</span>
              </div>`)}
          </div>
        </div>
        <div class="pane-mid">
          <input type="text" id="link-label" placeholder="Label (optional)">
          <button class="primary" ?disabled=${!both} @click=${this.createLink}>Link pair</button>
        </div>
        <div class="pane">
          <input type="search" placeholder="Search Immich people…"
            @input=${(e) => (this.immichQuery = e.target.value)}>
          <div class="cardlist">
            ${this.immich
              .filter((p) => !li[p.id])
              .filter((p) => !iq || (p.name || '').toLowerCase().includes(iq))
              .map((p) => html`<div class="card ${this.selImmich === p.id ? 'selected' : ''}"
                @click=${() => (this.selImmich = this.selImmich === p.id ? null : p.id)}>
                <img loading="lazy" src="/faces/api/thumb/person/${p.id}" alt="">
                <span class="name">${p.name || '(unnamed)'}</span>
              </div>`)}
          </div>
        </div>
      </div>`;
  }
}

customElements.define('faces-page', FacesPage);
