import { BifrostElement, html, nothing, api, post, btn, field, spinner, statusLine, searchField } from './core.js';

class FacesPage extends BifrostElement {
  static properties = {
    links: { state: true },
    grampsUrl: { state: true },
    accounts: { state: true },
    gPeople: { state: true },
    iPeople: { state: true },
    query: { state: true },
    filter: { state: true },
    open: { state: true },
    dialogOpen: { state: true },
    selG: { state: true },
    selI: { state: true },
    qG: { state: true },
    qI: { state: true },
    hiG: { state: true },
    hiI: { state: true },
    label: { state: true },
    labelDraft: { state: true },
    busy: { state: true },
    result: { state: true },
  };

  constructor() {
    super();
    this.links = null;
    this.grampsUrl = '';
    this.accounts = [];
    this.gPeople = [];
    this.iPeople = [];
    this.query = '';
    this.filter = 'all';
    this.open = null;
    this.dialogOpen = false;
    this.selG = '';
    this.selI = '';
    this.qG = '';
    this.qI = '';
    this.hiG = -1;
    this.hiI = -1;
    this.label = '';
    this.labelDraft = '';
    this.busy = '';
    this.result = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  updated() {
    // the dialogOpen check matters: close() fires its event a task later, so
    // without it a render in between would re-open the dialog we just closed
    const dlg = this.renderRoot.querySelector('dialog');
    if (this.dialogOpen && dlg && !dlg.open) dlg.showModal();
  }

  async load(refresh = false) {
    this.busy = 'load';
    this.result = null;
    try {
      const q = refresh ? '?refresh=1' : '';
      const [linksResp, gPeople, iPeople] = await Promise.all([
        api('/faces/api/links'),
        api(`/faces/api/gramps-people${q}`),
        api(`/faces/api/immich-people${q}`),
      ]);
      this.links = linksResp.faces;
      this.grampsUrl = linksResp.gramps_url || '';
      this.accounts = linksResp.accounts || [];
      this.gPeople = gPeople;
      this.iPeople = iPeople;
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  refresh() {
    this.query = '';
    this.filter = 'all';
    this.open = null;
    this.load(true);
  }

  acctIndex(label) {
    const i = this.accounts.indexOf(label);
    return i < 0 ? this.accounts.length : i;
  }

  orderedLinks(group) {
    return [...group.links].sort(
      (a, b) => this.acctIndex(a.account_label) - this.acctIndex(b.account_label));
  }

  // hovering a thumbnail is the whole attribution: "Ada Berg (fh)"
  who(link) {
    if (!link.resolved) return 'deleted Immich person';
    return `${link.person_name || '(unnamed)'} (${link.account_label})`;
  }

  storedLabel(g) {
    return g.links.map((l) => l.label).find((x) => x) || '';
  }

  gPerson(handle) {
    return this.gPeople.find((x) => x.handle === handle) || null;
  }

  personName(handle) {
    return this.gPerson(handle)?.name || handle;
  }

  // an unnamed Immich cluster has nothing to match a Gramps person on, so it
  // is neither offered in the dialog nor listed as a backlog card
  get named() {
    return this.iPeople.filter((p) => !p.is_hidden && p.name.trim());
  }

  get backlog() {
    const linked = new Set(this.links.flatMap((g) => g.links.map((l) => l.immich_person_id)));
    return this.named.filter((p) => !linked.has(p.id));
  }

  get broken() {
    return this.links.filter((g) => g.links.some((l) => !l.resolved));
  }

  get sorted() {
    return [...this.links].sort((a, b) => this.personName(a.gramps_handle)
      .localeCompare(this.personName(b.gramps_handle), undefined, { sensitivity: 'base' }));
  }

  matches(g, q) {
    const p = this.gPerson(g.gramps_handle);
    return [this.personName(g.gramps_handle), p?.gramps_id || '', g.label || '',
      ...g.links.map((l) => l.person_name || '')]
      .join(' ').toLowerCase().includes(q);
  }

  // groups arrive sorted by display name, so consecutive runs are the buckets
  letters(groups) {
    const out = [];
    for (const g of groups) {
      const letter = (this.personName(g.gramps_handle)[0] || '?').toUpperCase();
      const last = out[out.length - 1];
      if (last && last.letter === letter) last.groups.push(g);
      else out.push({ letter, groups: [g] });
    }
    return out;
  }

  setQuery(v) { this.query = v; this.open = null; }
  setFilter(k) { this.filter = k; this.open = null; }
  toggle(handle) {
    const opening = this.open !== handle;
    this.open = opening ? handle : null;
    if (opening) {
      this.labelDraft = this.storedLabel(
        this.links.find((g) => g.gramps_handle === handle));
    }
  }

  // one POST per link: set_link replaces per account, so both rows end up
  // carrying the new label without disturbing each other
  async saveLabel(g) {
    const label = this.labelDraft.trim();
    const targets = this.orderedLinks(g).filter((l) => l.resolved);
    if (!targets.length) return;
    this.busy = 'link';
    this.result = null;
    try {
      let r = null;
      for (const l of targets) {
        r = await post('/faces/api/links', {
          gramps_handle: g.gramps_handle,
          immich_person_id: l.immich_person_id,
          label,
        });
      }
      this.links = r.faces;
      this.grampsUrl = r.gramps_url || '';
      this.accounts = r.accounts || this.accounts;
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  openDialog(immichId = '') {
    this.selI = immichId;
    this.qI = this.named.find((p) => p.id === immichId)?.name || '';
    this.selG = '';
    this.qG = '';
    this.hiI = -1;
    this.hiG = -1;
    this.label = '';
    this.result = null;
    this.dialogOpen = true;
  }

  resetDialog() {
    this.dialogOpen = false;
    this.selI = '';
    this.selG = '';
    this.qI = '';
    this.qG = '';
    this.label = '';
    this.result = null;
  }

  // reset directly rather than waiting on the close event: it is dispatched
  // from a queued task, and a missed one would leave the dialog unopenable
  closeDialog() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg?.open) dlg.close();
    this.resetDialog();
  }

  // Dismissal needs a press AND a release on the backdrop. A coordinate test
  // alone is not enough: the backdrop and the dialog's own padding are the
  // same element, and picking from a native select popup (or activating by
  // keyboard) reports a click at 0,0, which reads as "outside the dialog" and
  // tore the dialog down mid-edit. Requiring the press to have started on the
  // backdrop also stops a drag that ends outside from dismissing.
  pressScrim(e) {
    this._onScrim = e.target === e.currentTarget;
  }

  scrimClick(e) {
    if (!this._onScrim || e.target !== e.currentTarget || e.detail === 0) return;
    const r = e.currentTarget.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right
      || e.clientY < r.top || e.clientY > r.bottom) this.closeDialog();
  }

  async addLink() {
    if (!this.selG || !this.selI) return;
    this.busy = 'link';
    this.result = null;
    let ok = false;
    try {
      const r = await post('/faces/api/links', {
        gramps_handle: this.selG,
        immich_person_id: this.selI,
        label: this.label.trim(),
      });
      this.links = r.faces;
      this.grampsUrl = r.gramps_url || '';
      this.accounts = r.accounts || this.accounts;
      ok = true;
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
    if (ok) this.closeDialog();
  }

  async removeLink(handle) {
    this.busy = 'link';
    this.result = null;
    try {
      const r = await api(`/faces/api/links/${handle}`, { method: 'DELETE' });
      this.links = r.faces;
      this.grampsUrl = r.gramps_url || '';
      this.accounts = r.accounts || this.accounts;
      this.open = null;
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  chipBtn(label, count, key) {
    return html`<button class="chip ${this.filter === key ? 'fill' : ''}"
      ?disabled=${this.busy !== ''} @click=${() => this.setFilter(key)}>
      <span>${label}</span><span class="mono faces-count">${count}</span></button>`;
  }

  renderBar(counts) {
    return html`<div class="faces-bar">
      <nav class="wrap">
        ${btn(html`<i>add</i><span>Add link</span>`, this.busy !== '', () => this.openDialog())}
        <div class="field border small prefix no-margin faces-search">
          <i>search</i>
          <input type="text" placeholder="Search name, label or Gramps ID"
            .value=${this.query} @input=${(e) => this.setQuery(e.target.value)}>
        </div>
        <div class="faces-spacer"></div>
        ${btn(html`<i>refresh</i><span>Refresh</span>`, this.busy !== '',
          () => this.refresh(), 'border')}
      </nav>
      <nav class="wrap">
        ${this.chipBtn('All linked', counts.all, 'all')}
        ${this.chipBtn('Unlinked in Immich', counts.unlinked, 'unlinked')}
        ${this.chipBtn('Broken links', counts.broken, 'broken')}
      </nav>
    </div>`;
  }

  detail(g, ordered) {
    const p = this.gPerson(g.gramps_handle);
    const stored = this.storedLabel(g);
    const editable = ordered.some((l) => l.resolved);
    return html`<div class="faces-detail" @click=${(e) => e.stopPropagation()}>
      ${ordered.some((l) => !l.resolved)
        ? html`<div class="error-text">a link points at a deleted Immich person</div>` : nothing}
      <div class="faces-label-row">
        ${field('Label', this.labelDraft, (e) => (this.labelDraft = e.target.value),
    { small: true })}
        ${btn('Save', this.busy !== '' || !editable || this.labelDraft.trim() === stored,
    () => this.saveLabel(g), 'border')}
      </div>
      <div class="faces-actions">
        ${this.grampsUrl && p ? html`<a class="link" href="${this.grampsUrl}/person/${p.gramps_id}"
          target="_blank" rel="noopener">Open in Gramps</a>` : nothing}
        <div class="faces-spacer"></div>
        <button class="faces-remove" ?disabled=${this.busy !== ''}
          @click=${() => this.removeLink(g.gramps_handle)}>
          <i class="small">link_off</i>
          <span>${ordered.length > 1 ? 'Remove both links' : 'Remove link'}</span></button>
      </div>
    </div>`;
  }

  card(g) {
    const ordered = this.orderedLinks(g);
    const resolved = ordered.filter((l) => l.resolved);
    const pics = resolved.length ? resolved : [ordered[0]];
    const isOpen = this.open === g.gramps_handle;
    return html`<article class="border no-margin faces-card ${isOpen ? 'open' : ''}"
      @click=${() => this.toggle(g.gramps_handle)}>
      <div class="faces-head">
        <div class="faces-thumbs">${pics.map((l) => html`<img
          class="face-thumb acct-${this.acctIndex(l.account_label)}" loading="lazy" alt=""
          title=${this.who(l)}
          src="/faces/api/person-thumbnail/${l.immich_person_id}">`)}</div>
        <div class="faces-name">
          <div class="faces-title">${this.personName(g.gramps_handle)}</div>
          <div class="mono faces-sub">${this.gPerson(g.gramps_handle)?.gramps_id || ''}</div>
        </div>
        <i class="faces-chev">expand_more</i>
      </div>
      ${isOpen ? this.detail(g, ordered) : nothing}
    </article>`;
  }

  backlogCard(p) {
    return html`<article class="border no-margin faces-card"
      @click=${() => this.openDialog(p.id)}>
      <div class="faces-head">
        <div class="faces-thumbs"><img class="face-thumb acct-${this.acctIndex(p.account_label)}"
          loading="lazy" alt="" title=${`${p.name} (${p.account_label})`}
          src="/faces/api/person-thumbnail/${p.id}"></div>
        <div class="faces-name">
          <div class="faces-title">${p.name}</div>
          <div class="faces-sub">Link to a Gramps person</div>
        </div>
        <i class="faces-chev">add_link</i>
      </div>
    </article>`;
  }

  renderEmpty(q) {
    const msg = q ? html`No people match &ldquo;${q}&rdquo;`
      : this.filter === 'broken' ? 'No broken links'
        : this.filter === 'unlinked' ? 'Every named Immich person is linked'
          : 'No links yet';
    return html`<div class="faces-empty"><i>search_off</i><span>${msg}</span></div>`;
  }

  immichMatches() {
    const q = this.qI.trim().toLowerCase();
    return this.named.filter((p) => !q || p.name.toLowerCase().includes(q)).slice(0, 10)
      .map((p) => ({ id: p.id, label: p.name, sub: p.account_label,
        thumb: `/faces/api/person-thumbnail/${p.id}`, icon: 'face' }));
  }

  grampsMatches() {
    const q = this.qG.trim().toLowerCase();
    return this.gPeople
      .filter((p) => !q || p.name.toLowerCase().includes(q) || p.gramps_id.toLowerCase().includes(q))
      .slice(0, 10)
      .map((p) => ({ id: p.handle, label: p.name, sub: p.gramps_id, mono: true, icon: 'person' }));
  }

  pickImmich(it) { this.selI = it.id; this.qI = it.label; this.hiI = -1; }
  pickGramps(it) { this.selG = it.id; this.qG = it.label; this.hiG = -1; }

  renderDialog() {
    const iItems = this.immichMatches();
    const gItems = this.grampsMatches();
    const move = (key, n) => (d) => { if (n) this[key] = (this[key] + d + n) % n; };
    return html`
      <dialog class="faces-dialog" @mousedown=${(e) => this.pressScrim(e)}
        @click=${(e) => this.scrimClick(e)}
        @cancel=${() => this.resetDialog()} @close=${() => this.resetDialog()}>
        <h5 class="small">Link a face</h5>
        <div class="faces-fields">
          ${searchField({
    placeholder: 'Immich person', value: this.qI, items: iItems, active: this.hiI, icon: 'face',
    onInput: (e) => { this.qI = e.target.value; this.selI = ''; this.hiI = -1; },
    onPick: (it) => this.pickImmich(it),
    onEnter: () => { if (this.hiI >= 0 && this.hiI < iItems.length) this.pickImmich(iItems[this.hiI]); },
    onMove: move('hiI', iItems.length), empty: 'No named Immich person matches',
  })}
          ${searchField({
    placeholder: 'Gramps person: name or ID', value: this.qG, items: gItems, active: this.hiG, icon: 'person',
    onInput: (e) => { this.qG = e.target.value; this.selG = ''; this.hiG = -1; },
    onPick: (it) => this.pickGramps(it),
    onEnter: () => { if (this.hiG >= 0 && this.hiG < gItems.length) this.pickGramps(gItems[this.hiG]); },
    onMove: move('hiG', gItems.length), empty: 'No Gramps person matches',
  })}
          ${field('Label (optional)', this.label, (e) => (this.label = e.target.value),
    { small: true })}
        </div>
        ${this.result ? html`<p>${statusLine(this.result.kind, this.result.body)}</p>` : nothing}
        <nav class="right-align">
          ${btn('Cancel', this.busy !== '', () => this.closeDialog(), 'border')}
          ${btn('Link', this.busy !== '' || !this.selG || !this.selI, () => this.addLink())}
        </nav>
      </dialog>`;
  }

  render() {
    if (this.links === null) {
      return html`<p>${this.result ? statusLine(this.result.kind, this.result.body) : spinner}</p>`;
    }
    const q = this.query.trim().toLowerCase();
    const backlog = this.backlog;
    const counts = { all: this.links.length, unlinked: backlog.length, broken: this.broken.length };
    const showBacklog = this.filter === 'unlinked';
    const base = this.filter === 'broken' ? this.broken : this.sorted;
    const groups = q ? base.filter((g) => this.matches(g, q)) : base;
    const people = q ? backlog.filter((p) => p.name.toLowerCase().includes(q)) : backlog;
    const [heading, n] = showBacklog
      ? ['Immich people with no Gramps link', people.length]
      : ['Linked people', groups.length];
    return html`
      ${this.renderBar(counts)}
      <div class="faces-group">
        <h6 class="small">${heading}</h6>
        <span class="mono small-text secondary-text">${n}</span>
      </div>
      ${!n ? this.renderEmpty(q)
    : showBacklog
      ? html`<div class="faces-grid">${people.map((p) => this.backlogCard(p))}</div>`
      : this.letters(groups).map((b) => html`
            <div class="faces-letter"><span class="mono">${b.letter}</span>
              <span class="rule"></span></div>
            <div class="faces-grid">${b.groups.map((g) => this.card(g))}</div>`)}
      ${this.result && !this.dialogOpen
    ? html`<p>${statusLine(this.result.kind, this.result.body)}</p>` : nothing}
      ${this.dialogOpen ? this.renderDialog() : nothing}`;
  }
}
customElements.define('faces-page', FacesPage);
