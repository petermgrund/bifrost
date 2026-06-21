import { BifrostElement, html, nothing, api, post, summarize, mdBtn, mdSpinner } from './core.js';

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
    loading: { state: true },
    loaded: { state: true },
    error: { state: true },
    applyResult: { state: true },
    versionSet: { state: true },
    versionsBusy: { state: true },
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
    this.loading = false;
    this.loaded = false;
    this.error = '';
    this.applyResult = null;
    this.versionSet = null;
    this.versionsBusy = false;
  }

  connectedCallback() {
    super.connectedCallback();
    const f = new URLSearchParams(location.search).get('filter');
    if (['pending', 'manual', 'unlinked'].includes(f)) this.photoFilter = f;
    this.load();
  }

  async load(refresh = false) {
    const r = refresh ? '?refresh=1' : '';
    this.loading = true; this.error = '';
    try {
      [this.gramps, this.immich, this.links] = await Promise.all([
        api(`/faces/api/gramps-people${r}`),
        api(`/faces/api/immich-people${r}`),
        api(`/faces/api/links`),
      ]);
      this.listing = await api(`/faces/api/photos${r}`);
    } catch (e) {
      this.error = e.message;
    } finally {
      this.loading = false; this.loaded = true;
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
    this.error = '';
    try {
      this.links = await post('/faces/api/links', {
        gramps_handle: this.selGramps,
        immich_person_id: this.selImmich,
        label: this.renderRoot.querySelector('#link-label')?.value || null,
      });
      this.selGramps = this.selImmich = null;
      await this.load();
    } catch (e) {
      this.error = e.message;
    }
  }
  async unlink(handle) {
    this.error = '';
    try {
      this.links = await api(`/faces/api/links/${handle}`, { method: 'DELETE' });
      await this.load();
    } catch (e) {
      this.error = e.message;
    }
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
      this.error = e.message;
    }
  }
  async applyPending() {
    this.busy = true;
    this.error = '';
    this.applyResult = null;
    try {
      const r = await post('/faces/api/apply-pending', {});
      const counts = (r.events.find((e) => e.kind === 'summary') || {}).data;
      const failed = r.events.filter((e) => e.kind === 'item' && e.action === 'failed');
      this.applyResult = { counts, failed };
      await this.load(true);
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  /* ---- render ---- */
  applyResultBanner() {
    const r = this.applyResult;
    if (!r) return nothing;
    const line = summarize(r.counts, true);
    return html`<div class="applyresult">
      <span>${line}${r.failed && r.failed.length ? ` · ${r.failed.length} failed` : ''}</span>
      ${r.failed && r.failed.length ? html`<ul class="failures">
        ${r.failed.map((f) => html`<li class="hint action-failed">${f.title || f.source_id}: ${f.detail}</li>`)}</ul>` : nothing}
    </div>`;
  }

  render() {
    if (!this.loaded) return html`<h1>Faces</h1><div class="hint">Loading…</div>`;
    return html`
      <div class="pagehead">
        <h1>Faces</h1>
        <span class="spacer"></span>
        ${this.listing.pending_total
          ? mdBtn('filled', this.busy ? 'Applying…' : `Apply pending (${this.listing.pending_total})`,
              this.busy, this.applyPending)
          : nothing}
        ${mdBtn('outlined', this.loading ? 'Refreshing…' : 'Refresh', this.loading, () => this.load(true))}
        ${this.busy || this.loading ? mdSpinner : nothing}
      </div>
      <md-tabs .activeTabIndex=${this.tab === 'people' ? 1 : 0}
        @change=${(e) => (this.tab = e.target.activeTabIndex === 1 ? 'people' : 'photos')}>
        <md-primary-tab>Photos</md-primary-tab>
        <md-primary-tab>People</md-primary-tab>
      </md-tabs>
      ${this.error ? html`<div class="alert">${this.error}</div>` : nothing}
      ${this.applyResultBanner()}
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
    const chip = (f, label) => html`<md-filter-chip label=${label}
      ?selected=${this.photoFilter === f}
      @click=${() => (this.photoFilter = f)}></md-filter-chip>`;
    return html`
      <div class="toolbar">
        <md-outlined-text-field type="search" label="Search photos…"
          .value=${this.photoQuery} @input=${(e) => (this.photoQuery = e.target.value)}></md-outlined-text-field>
        <md-chip-set>
          ${chip('all', 'All')}${chip('pending', 'Needs attention')}${chip('unlinked', 'No person link')}${chip('manual', 'Manual')}
        </md-chip-set>
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
          ${p.version_count > 1 ? html`<span class="badge">v${p.version_count}</span>` : nothing}
          ${p.pending_count ? html`<span class="badge">${p.pending_count} pending</span>` : nothing}
          ${p.synced ? nothing : html`<span class="badge unlinked">not in Gramps</span>`}
        </div>
      </div>
    </div>`;
  }

  openDetail(assetId) {
    this.openAsset = assetId;
    this.versionSet = null;
    this.loadVersions(assetId);
  }

  closeDetail() {
    this.openAsset = null;
    this.versionSet = null;
  }

  /* ---- versions (the VERSIONS strip — docs/IMMICH_VERSIONING.md) ---- */
  async loadVersions(assetId) {
    this.versionsBusy = true;
    try {
      const vs = await api(`/versions/api/by-asset/${assetId}`);
      if (this.openAsset === assetId) this.versionSet = vs;  // ignore if user moved on
    } catch (e) {
      if (this.openAsset === assetId) this.versionSet = { versioned: false, error: e.message };
    } finally {
      this.versionsBusy = false;
    }
  }

  async setDisplayed(memberId) {
    if (!this.versionSet?.stack_id) return;
    this.versionsBusy = true; this.error = '';
    try {
      await post('/versions/api/set-displayed',
        { stack_id: this.versionSet.stack_id, member_id: memberId });
      await this.loadVersions(this.openAsset);  // refresh the strip
      await this.load(true);                     // media path + faces changed
    } catch (e) {
      this.error = e.message;
    } finally {
      this.versionsBusy = false;
    }
  }

  async setRole(member, role) {
    const next = member.role === role ? null : role;  // click the active chip to clear
    try {
      const r = await post('/versions/api/set-role',
        { gramps_id: this.versionSet.gramps_id, asset_id: member.asset_id, role: next });
      member.role = r.role;
      this.requestUpdate();
    } catch (e) {
      this.error = e.message;
    }
  }

  async setVersionLabel(member, label) {
    try {
      const r = await post('/versions/api/set-label',
        { gramps_id: this.versionSet.gramps_id, asset_id: member.asset_id, label });
      member.label = r.label;
    } catch (e) {
      this.error = e.message;
    }
  }

  renderVersions() {
    const vs = this.versionSet;
    if (!vs || !vs.versioned) return nothing;
    if (!vs.managed) {
      const gid = this.openPhoto?.gramps_id || '<id>';
      return html`<div class="version-strip">
        <div class="vhead">Versions</div>
        <div class="vintro">In an Immich stack but not opted in. Tag any member
          <code>Gramps/Base/${gid}</code> in Immich to manage versions here.</div>
      </div>`;
    }
    const ROLES = [['original', 'Original'], ['ai', 'AI'], ['crop', 'Crop'],
                   ['duplicate', 'Duplicate'], ['verso', 'Verso']];
    return html`<div class="version-strip">
      <div class="vhead">Versions <span class="hint">(${vs.members.length})</span> ${this.versionsBusy ? mdSpinner : nothing}</div>
      <div class="vintro">The highlighted version is shown in Gramps; changing it repoints the Gramps media (same id).</div>
      ${vs.members.map((m) => html`
        <div class="vrow ${m.is_displayed ? 'displayed' : ''}">
          <img class="vthumb" loading="lazy" src=${m.thumb_url} alt="">
          <div class="vinfo">
            <div class="vfile">${m.filename || m.asset_id.slice(0, 8)}</div>
            ${m.is_displayed
              ? html`<span class="vtag">● shown in Gramps</span>`
              : mdBtn('filled', 'Set displayed', this.versionsBusy,
                  () => this.setDisplayed(m.asset_id))}
          </div>
          <md-chip-set class="vroles">
            ${ROLES.map(([k, lab]) => html`<md-filter-chip label=${lab}
              ?selected=${m.role === k} @click=${() => this.setRole(m, k)}></md-filter-chip>`)}
          </md-chip-set>
          <md-outlined-text-field class="vnote" label="Note" .value=${m.label || ''}
            @change=${(e) => this.setVersionLabel(m, e.target.value)}></md-outlined-text-field>
        </div>`)}
    </div>`;
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
    return html`<md-dialog class="photo-dialog" open @closed=${() => this.closeDetail()}>
      <span slot="headline">${p.title}
        <span class="hint" style="font-weight:400;font-size:.8rem">${p.synced ? p.gramps_id : 'not in Gramps'}</span>
      </span>
      <div slot="content">
        ${this.renderVersions()}
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
      <div slot="actions">
        <md-text-button @click=${() => this.closeDetail()}>Close</md-text-button>
      </div>
    </md-dialog>`;
  }

  faceRow(f) {
    if (f.status === 'unlinked') {
      return html`<div class="facerow">
        <img src="/faces/api/thumb/person/${f.immich_person_id}" alt="">
        <div class="who"><div>${f.immich_name}</div><div class="hint">not linked</div></div>
        <md-text-button class="linkjump" @click=${() => {
          this.openAsset = null; this.tab = 'people'; this.selImmich = f.immich_person_id;
        }}>Link…</md-text-button></div>`;
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
        <md-slider min="0" max="50" step="5" labeled .value=${padPct}
          @input=${(e) => (e.target.nextElementSibling.textContent = `${e.target.value}%`)}
          @change=${(e) => this.applyFace(f, Number(e.target.value) / 100)}></md-slider>
        <span class="padval">${padPct}%</span>
        ${f.status === 'applied' ? nothing
          : html`<md-text-button class="applyone" @click=${() => this.applyFace(f, f.pad)}>Apply</md-text-button>`}
      </div></div>`;
  }

  async saveLabel(link, label) {
    this.error = '';
    try {
      this.links = await post('/faces/api/links', {
        gramps_handle: link.gramps_handle,
        immich_person_id: link.immich_person_id,
        label: label.trim() || null,
      });
    } catch (e) {
      this.error = e.message;
    }
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
          <td><md-outlined-text-field .value=${l.label || ''} placeholder="—"
            @change=${(e) => this.saveLabel(l, e.target.value)}></md-outlined-text-field></td>
          <td><md-text-button class="unlink" @click=${() => this.unlink(l.gramps_handle)}>unlink</md-text-button></td>
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
          <md-outlined-text-field type="search" label="Search Gramps people…"
            @input=${(e) => (this.grampsQuery = e.target.value)}></md-outlined-text-field>
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
          <md-outlined-text-field id="link-label" label="Label (optional)"></md-outlined-text-field>
          ${mdBtn('filled', 'Link pair', !both, this.createLink)}
        </div>
        <div class="pane">
          <md-outlined-text-field type="search" label="Search Immich people…"
            @input=${(e) => (this.immichQuery = e.target.value)}></md-outlined-text-field>
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
