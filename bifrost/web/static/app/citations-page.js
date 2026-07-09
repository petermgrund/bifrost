import { BifrostElement, html, nothing, api, post, btn, spinner, field, statusLine } from './core.js';

class CitationsPage extends BifrostElement {
  static properties = {
    step: { state: true },          // describe | review
    ctx: { state: true },           // types, sources, repositories, llm
    mediaId: { state: true },
    pick: { state: true },          // { media, source, repository }; modal open when media set
    draft: { state: true },         // composed/edited draft
    busy: { state: true },
    pulling: { state: true },       // transcript fetch in flight
    error: { state: true },
    loadError: { state: true },
    saved: { state: true },
    subject: { state: true },       // what the citation represents (required)
    transcript: { state: true },
    urls: { state: true },
    extra: { state: true },         // catch-all
    matched: { state: true },
  };

  constructor() {
    super();
    this.step = 'describe';
    this.ctx = null;
    this.mediaId = '';
    this.pick = { media: null, source: null, repository: null };
    this.draft = null;
    this.busy = false;
    this.pulling = false;
    this.error = '';
    this.loadError = '';
    this.saved = null;
    this.subject = '';
    this.transcript = '';
    this.urls = '';
    this.extra = '';
    this.pl = null;
    this.matched = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    this.loadError = '';
    try {
      this.ctx = await api('/citations/api/context');
    } catch (e) {
      this.loadError = e.message;
    }
  }

  reset() {
    this.step = 'describe';
    this.pick = { media: null, source: null, repository: null };
    this.draft = null;
    this.error = '';
    this.saved = null;
    this.subject = '';
    this.transcript = '';
    this.urls = '';
    this.extra = '';
    this.pl = null;
    this.matched = null;
  }

  closeModal() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg?.open) dlg.close();
    else this.reset();
  }

  updated() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg && !dlg.open) dlg.showModal();
  }

  async lookupMedia() {
    if (this.busy) return;
    const id = this.mediaId.trim();
    if (!id) { this.error = 'Enter a Gramps media ID'; return; }
    this.busy = true;
    this.error = '';
    try {
      const m = await api(`/citations/api/media/${encodeURIComponent(id)}`);
      this.step = 'describe';
      this.pick = { ...this.pick, media: m };
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  async composeDump() {
    this.busy = true;
    this.error = '';
    try {
      const r = await post('/citations/api/compose-dump', {
        subject: this.subject,
        transcript: this.transcript,
        urls: this.urls,
        dump: this.extra,
        media_handle: this.pick.media?.handle || null,
      });
      this.draft = r.draft;
      this.matched = { source: r.matched_source, repository: r.matched_repository };
      this.pick = { ...this.pick,
        source: r.matched_source || null,
        repository: r.matched_repository || null };
      this.step = 'review';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  async pull(prop, plKey, what) {
    if (this.pulling || this.busy) return;
    this.pulling = true;
    this.error = '';
    try {
      this.pl ??= await api(`/citations/api/paperless/${encodeURIComponent(this.pick.media.gramps_id)}`);
      if (this.pl[plKey]) this[prop] = this.pl[plKey];
      else this.error = `No ${what} on Paperless doc #${this.pl.doc_id}`;
    } catch (e) {
      this.error = e.message;
    } finally {
      this.pulling = false;
    }
  }

  manualDraft() {
    this.draft = {
      repository: this.pick.source ? null : { name: '', type: 'Archive', url: '' },
      call_number: '',
      source: this.pick.source ? null : { title: '', author: '', pubinfo: '', abbrev: '' },
      citation: { page: '', confidence: 2 },
      notes: { first_reference: '', short_reference: '', abstract: '' },
      quality: null,
    };
    this.step = 'review';
  }

  async save() {
    this.busy = true;
    this.error = '';
    try {
      this.saved = await post('/citations/api/save', {
        draft: this.draft,
        media_handle: this.pick.media?.handle || null,
        repository_handle: this.pick.repository?.handle || null,
        source_handle: this.pick.source?.handle || null,
      });
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  render() {
    if (this.loadError && !this.ctx) {
      return html`
        <p>${statusLine('error', this.loadError)}</p>
        <nav>${btn('Retry', false, () => this.load())}</nav>`;
    }
    if (!this.ctx) return html`<progress class="circle"></progress>`;
    const lookingUp = this.busy && !this.pick.media;
    return html`
      <nav class="wrap">
        ${field('Gramps media ID', this.mediaId, (e) => (this.mediaId = e.target.value),
          { mono: true, upper: true, width: 'small', onEnter: () => this.lookupMedia() })}
        ${btn(lookingUp ? 'Looking up...' : 'Look up', lookingUp, () => this.lookupMedia())}
        ${lookingUp ? spinner : nothing}
      </nav>
      ${!this.pick.media && this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}
      ${this.pick.media ? this.renderModal() : nothing}`;
  }

  renderModal() {
    const m = this.pick.media;
    return html`
      <dialog class="large" @close=${() => this.reset()}>
        <nav>
          <h5 class="max small">${m.title} (${m.gramps_id})</h5>
          <button class="circle transparent" @click=${() => this.closeModal()} aria-label="Close">
            <i>close</i></button>
        </nav>
        ${this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}
        ${this.saved ? this.renderSaved()
          : this.step === 'review' ? this.renderReview()
          : this.renderDescribe()}
      </dialog>`;
  }

  renderDescribe() {
    const m = this.pick.media;
    const cits = m.citations || [];
    const srcTitles = [...new Set(cits.map((c) => c.source_title).filter(Boolean))];
    const pull = (prop, plKey, what) => (m.paperless_id ? html`<nav class="wrap">
        ${btn(this.pulling ? 'Pulling...' : 'Pull from Paperless',
          this.pulling || this.busy, () => this.pull(prop, plKey, what))}
        ${this.pulling ? spinner : nothing}
      </nav><div class="space"></div>` : nothing);
    return html`
      ${cits.length ? html`<p>Already cited
        ${cits.length === 1 ? 'once' : `${cits.length} times`}${srcTitles.length === 1
          ? html` (${srcTitles[0]})` : nothing}</p>` : nothing}
      ${field('What this citation represents', this.subject,
        (e) => (this.subject = e.target.value), { rows: 2, helper: true })}
      ${field('Transcript', this.transcript,
        (e) => (this.transcript = e.target.value), { rows: 5, helper: true })}
      ${pull('transcript', 'transcript', 'transcript')}
      ${field('URLs', this.urls,
        (e) => (this.urls = e.target.value), { rows: 3, helper: true })}
      ${pull('urls', 'source_url', 'source URL')}
      ${field('Anything else to include', this.extra,
        (e) => (this.extra = e.target.value), { rows: 4, helper: true })}
      ${pull('extra', 'notes', 'notes')}
      <nav>
        ${this.ctx.llm ? btn(this.busy ? 'Composing...' : 'Compose citation',
          this.busy || !this.subject.trim(), () => this.composeDump()) : nothing}
        ${btn('Write manually', this.busy, () => this.manualDraft())}
        ${this.busy ? spinner : nothing}
      </nav>`;
  }

  renderSaved() {
    return html`
      <p>${statusLine('ok', 'Saved to Gramps')}</p>
      <table>
        <tbody>${Object.entries(this.saved).map(([k, v]) => html`<tr><td>${k}</td><td>${v}</td></tr>`)}</tbody>
      </table>
      <nav>
        ${btn('Close', false, () => this.closeModal())}
      </nav>`;
  }

  renderReview() {
    const d = this.draft;
    const m = this.matched;
    const matchedBanner = m && (m.source || m.repository)
      ? html`<p class="small-text">${m.source
          ? html`Using existing source <strong>${m.source.gramps_id}</strong> — ${m.source.title}`
          : html`New source in existing repository <strong>${m.repository.gramps_id}</strong> — ${m.repository.name}`}</p>`
      : nothing;
    const bind = (obj, key, label, multiline = false) =>
      field(label, obj[key], (e) => { obj[key] = e.target.value; }, multiline ? { rows: 4 } : {});
    return html`
      ${matchedBanner}
      ${d.quality ? html`<p class="small-text">${d.quality.source_type} source ·
        ${d.quality.information_type.toLowerCase()} information ·
        ${d.quality.evidence_type.toLowerCase()} evidence — ${d.quality.note}</p>` : nothing}
      <div class="grid">
        ${d.repository ? html`<div class="s12 m6"><h6 class="small">New repository</h6>
          ${bind(d.repository, 'name', 'Name')}
          ${bind(d.repository, 'type', 'Type')}
          ${bind(d.repository, 'url', 'URL')}
          ${bind(d, 'call_number', 'Call number')}
        </div>` : nothing}
        ${d.source ? html`<div class="s12 m6"><h6 class="small">New source</h6>
          ${bind(d.source, 'title', 'Title')}
          ${bind(d.source, 'author', 'Author')}
          ${bind(d.source, 'pubinfo', 'Pub. info')}
          ${bind(d.source, 'abbrev', 'Abbreviation')}
        </div>` : nothing}
        <div class="s12 m6"><h6 class="small">Citation</h6>
          ${bind(d.citation, 'page', 'Page / locator')}
          ${bind(d.citation, 'confidence', 'Confidence (0–4)')}
        </div>
        <div class="s12 m6"><h6 class="small">Notes</h6>
          ${bind(d.notes, 'first_reference', 'First reference', true)}
          ${bind(d.notes, 'short_reference', 'Short reference', true)}
          ${bind(d.notes, 'abstract', 'Abstract', true)}
        </div>
      </div>
      <nav>
        ${btn(this.busy ? 'Saving…' : 'Save to Gramps', this.busy, () => this.save())}
        ${btn('Back', this.busy, () => (this.step = 'describe'))}
        ${this.busy ? spinner : nothing}
      </nav>`;
  }
}

customElements.define('citations-page', CitationsPage);
