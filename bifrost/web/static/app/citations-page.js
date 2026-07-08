/* Citation generator — look up one media by Gramps ID; the generator flow
   (describe → review → save) runs in a modal, like the Places dialog. The
   free-text dump is the one composing path (LLM); 'Write manually' is the
   no-LLM fallback. */
import { BifrostElement, html, nothing, api, post, btn, spinner, field, statusLine } from './core.js';

class CitationsPage extends BifrostElement {
  static properties = {
    step: { state: true },          // describe | review (inside the modal)
    ctx: { state: true },           // types, sources, repositories, llm
    mediaId: { state: true },
    pick: { state: true },          // { media, source, repository }; modal open when media set
    draft: { state: true },         // composed/edited draft
    busy: { state: true },
    error: { state: true },
    loadError: { state: true },
    saved: { state: true },
    dump: { state: true },
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
    this.error = '';
    this.loadError = '';
    this.saved = null;
    this.dump = '';
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
    this.dump = '';
    this.matched = null;
  }

  closeModal() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg?.open) dlg.close();          // fires @close, which resets the flow
    else this.reset();
  }

  /* The dialog must sit in the browser's top layer (showModal) — rendered
     inline it would be clipped to the section expander's content box. */
  updated() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg && !dlg.open) dlg.showModal();
  }

  /* ---- lookup / compose / save ---- */
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
        dump: this.dump,
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

  /* ---- render ---- */
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
        ${btn(lookingUp ? 'Looking up…' : 'Look up', lookingUp, () => this.lookupMedia())}
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
          <h5 class="max small">${m.title}</h5>
          <button class="circle transparent" @click=${() => this.closeModal()} aria-label="Close">
            <i>close</i></button>
        </nav>
        <p class="mono small-text">${m.gramps_id}</p>
        ${this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}
        ${this.saved ? this.renderSaved()
          : this.step === 'review' ? this.renderReview()
          : this.renderDescribe()}
      </dialog>`;
  }

  renderDescribe() {
    return html`
      ${field('Enter info about record',
        this.dump, (e) => (this.dump = e.target.value), { rows: 7 })}
      <nav>
        ${this.ctx.llm ? btn(this.busy ? 'Composing…' : 'Compose citation',
          this.busy || !this.dump.trim(), () => this.composeDump()) : nothing}
        ${btn('Write manually', this.busy, () => this.manualDraft())}
        ${this.busy ? spinner : nothing}
      </nav>`;
  }

  renderSaved() {
    return html`
      <p>${statusLine('ok', 'Saved to Gramps.')}</p>
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
