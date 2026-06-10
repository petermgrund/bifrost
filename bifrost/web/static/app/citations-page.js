import { BifrostElement, html, nothing, api, post } from './core.js';

/* Citation generator: media → source → details → review/save. */
class CitationsPage extends BifrostElement {
  static properties = {
    step: { state: true },          // media | source | details | review
    ctx: { state: true },           // types, sources, repositories, llm
    media: { state: true },         // media listing
    mediaQuery: { state: true },
    uncitedOnly: { state: true },
    pick: { state: true },          // { media, source, repository, recordType }
    fields: { state: true },        // entered field values
    draft: { state: true },         // composed/edited draft
    busy: { state: true },
    error: { state: true },
    saved: { state: true },
    sourceQuery: { state: true },
    dump: { state: true },
    matched: { state: true },
    wizard: { state: true },
    repoQuery: { state: true },
  };

  constructor() {
    super();
    this.step = 'media';
    this.ctx = null;
    this.media = [];
    this.mediaQuery = '';
    this.uncitedOnly = true;
    this.pick = { media: null, source: null, repository: null, recordType: null };
    this.fields = {};
    this.draft = null;
    this.busy = false;
    this.error = '';
    this.saved = null;
    this.sourceQuery = '';
    this.dump = '';
    this.matched = null;
    this.wizard = false;
    this.repoQuery = '';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    try {
      [this.ctx, this.media] = await Promise.all([
        api('/citations/api/context'),
        api(`/citations/api/media?uncited=${this.uncitedOnly}`),
      ]);
    } catch (e) {
      this.error = e.message;
    }
  }

  async toggleUncited(v) {
    this.uncitedOnly = v;
    this.media = await api(`/citations/api/media?uncited=${v}`);
  }

  reset() {
    this.step = 'media';
    this.pick = { media: null, source: null, repository: null, recordType: null };
    this.fields = {};
    this.draft = null;
    this.error = '';
    this.saved = null;
    this.dump = '';
    this.matched = null;
    this.wizard = false;
  }

  /* ---- compose / save ---- */
  async compose() {
    this.busy = true;
    this.error = '';
    try {
      this.draft = await post('/citations/api/compose', {
        record_type: this.pick.recordType?.key || null,
        fields: this.fields,
        media_handle: this.pick.media?.handle || null,
        source_handle: this.pick.source?.handle || null,
      });
      this.step = 'review';
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
      citation: { page: '', date: null, confidence: 2 },
      notes: { first_reference: '', short_reference: '', source_list_entry: '' },
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
    if (!this.ctx) return html`<h1>Citations</h1><div class="hint">${this.error || 'Loading…'}</div>`;
    const steps = ['media', 'describe', 'details', 'review'];
    return html`
      <div class="pagehead">
        <h1>Citations</h1>
        <div class="tabs">
          ${steps.map((s, i) => html`<button class="tab ${this.step === s ? 'active' : ''}"
            ?disabled=${steps.indexOf(this.step) < i}
            @click=${() => { if (steps.indexOf(this.step) > i) this.step = s; }}>
            ${i + 1}. ${s}</button>`)}
        </div>
        <span class="spacer"></span>
        ${this.step !== 'media' ? html`<button @click=${this.reset}>Start over</button>` : nothing}
      </div>
      ${this.error ? html`<div class="alert">${this.error}</div>` : nothing}
      ${{
        media: () => this.renderMedia(),
        describe: () => this.renderDescribe(),
        details: () => this.renderDetails(),
        review: () => this.renderReview(),
      }[this.step]()}
    `;
  }

  renderMedia() {
    const q = this.mediaQuery.toLowerCase();
    const rows = this.media.filter((m) => !q || m.title.toLowerCase().includes(q)
      || m.gramps_id.toLowerCase().includes(q)).slice(0, 80);
    return html`
      <div class="toolbar">
        <input type="search" placeholder="Search media…" .value=${this.mediaQuery}
          @input=${(e) => (this.mediaQuery = e.target.value)}>
        <button class="chip ${this.uncitedOnly ? 'active' : ''}"
          @click=${() => this.toggleUncited(true)}>Uncited</button>
        <button class="chip ${this.uncitedOnly ? '' : 'active'}"
          @click=${() => this.toggleUncited(false)}>All</button>
        <span class="hint">${rows.length} shown</span>
      </div>
      <div class="cardlist" style="max-height:60vh">
        ${rows.map((m) => html`<div class="card"
          @click=${() => { this.pick = { ...this.pick, media: m }; this.step = 'describe'; }}>
          <span class="name">${m.title}</span>
          <span class="meta">${m.gramps_id} · ${m.origin}</span>
          ${m.cited ? html`<span class="badge unlinked">cited</span>` : nothing}
        </div>`)}
      </div>`;
  }

  renderDescribe() {
    return html`
      <p class="hint">Citing: <strong>${this.pick.media?.title}</strong></p>
      <div class="syncpanel">
        <h2>Describe the record</h2>
        <textarea rows="7" placeholder="Dump everything you know: what the record is, who's in it, dates, page/entry numbers, archive references, the URL you found it at…"
          .value=${this.dump} @input=${(e) => (this.dump = e.target.value)}></textarea>
        <div class="toolbar">
          ${this.ctx.llm ? html`<button class="primary" ?disabled=${this.busy || !this.dump.trim()}
            @click=${this.composeDump}>${this.busy ? 'Composing…' : 'Compose citation'}</button>` : nothing}
          <button @click=${() => (this.wizard = !this.wizard)}>
            ${this.wizard ? 'Hide' : 'Structured wizard'}</button>
        </div>
        <p class="hint">Matches an existing source when one fits; drafts a new one when none does.</p>
      </div>
      ${this.wizard ? this.renderWizard() : nothing}`;
  }

  renderWizard() {
    const q = this.sourceQuery.toLowerCase();
    const matches = this.ctx.sources.filter((s) =>
      !q || s.title.toLowerCase().includes(q) || s.abbrev.toLowerCase().includes(q)).slice(0, 30);
    return html`
      <p class="hint">Citing: <strong>${this.pick.media?.title}</strong></p>
      <h2>Existing source</h2>
      <div class="toolbar">
        <input type="search" placeholder="Search sources…" .value=${this.sourceQuery}
          @input=${(e) => (this.sourceQuery = e.target.value)}>
      </div>
      <div class="cardlist" style="max-height:38vh">
        ${matches.map((s) => html`<div class="card"
          @click=${() => { this.pick = { ...this.pick, source: s, recordType: null }; this.step = 'details'; }}>
          <span class="name">${s.title}</span>
          <span class="meta">${s.gramps_id}</span>
        </div>`)}
      </div>
      <h2>…or a new source</h2>
      <div class="toolbar" style="flex-wrap:wrap">
        ${Object.entries(this.ctx.groups).map(([gk, glabel]) => html`
          <div style="width:100%"><span class="hint">${glabel}</span></div>
          ${this.ctx.types.filter((t) => t.group === gk).map((t) => html`
            <button class="chip" @click=${() => {
              this.pick = { ...this.pick, source: null, recordType: t };
              this.step = 'details';
            }}>${t.label}</button>`)}`)}
      </div>`;
  }

  renderDetails() {
    const t = this.pick.recordType;
    const src = this.pick.source;
    const fieldRow = (key, label, req, hint) => html`
      <label class="fieldrow">
        <span>${label}${req ? ' *' : ''}</span>
        <input type="text" .value=${this.fields[key] || ''} placeholder=${hint || ''}
          @input=${(e) => (this.fields = { ...this.fields, [key]: e.target.value })}>
      </label>`;
    return html`
      <p class="hint">Citing: <strong>${this.pick.media?.title}</strong>
        ${src ? html` → ${src.abbrev || src.title}` : html` → new ${t.label}`}</p>
      <div class="fieldform">
        ${src ? html`
          ${fieldRow('locator', 'Locator within the source (page, entry, dwelling…)', true)}
          ${fieldRow('person', 'Person(s) / item of interest', true)}
          ${fieldRow('event_date', 'Date of the record entry', false)}
          ${fieldRow('extra', 'Anything else relevant', false)}
        ` : t.fields.map((f) => fieldRow(f.key, f.label, f.req, f.hint))}
      </div>
      <div class="toolbar">
        ${this.ctx.llm
          ? html`<button class="primary" ?disabled=${this.busy} @click=${this.compose}>
              ${this.busy ? 'Composing…' : 'Compose citation'}</button>`
          : nothing}
        <button @click=${this.manualDraft}>Write manually</button>
      </div>`;
  }

  renderReview() {
    if (this.saved) {
      return html`<div class="syncpanel">
        <h2>Saved</h2>
        <table class="results">
          ${Object.entries(this.saved).map(([k, v]) => html`<tr><td>${k}</td><td>${v}</td></tr>`)}
        </table>
        <div class="toolbar"><button class="primary" @click=${this.reset}>New citation</button></div>
      </div>`;
    }
    const d = this.draft;
    const m = this.matched;
    const matchedBanner = m && (m.source || m.repository)
      ? html`<p class="hint">${m.source
          ? html`Using existing source <strong>${m.source.gramps_id}</strong> — ${m.source.title}`
          : html`New source in existing repository <strong>${m.repository.gramps_id}</strong> — ${m.repository.name}`}</p>`
      : nothing;
    const bind = (obj, key, multiline = false) => multiline
      ? html`<textarea rows="4" .value=${obj[key] || ''}
          @input=${(e) => { obj[key] = e.target.value; }}></textarea>`
      : html`<input type="text" .value=${String(obj[key] ?? '')}
          @input=${(e) => { obj[key] = e.target.value; }}>`;
    return html`
      ${matchedBanner}
      ${d.quality ? html`<p class="hint">${d.quality.source_type} source ·
        ${d.quality.information_type.toLowerCase()} information ·
        ${d.quality.evidence_type.toLowerCase()} evidence — ${d.quality.note}</p>` : nothing}
      <div class="reviewgrid">
        ${d.repository ? html`<div class="syncpanel"><h2>New repository</h2>
          <label class="fieldrow"><span>Name</span>${bind(d.repository, 'name')}</label>
          <label class="fieldrow"><span>Type</span>${bind(d.repository, 'type')}</label>
          <label class="fieldrow"><span>URL</span>${bind(d.repository, 'url')}</label>
          <label class="fieldrow"><span>Call number</span>${bind(d, 'call_number')}</label>
        </div>` : nothing}
        ${d.source ? html`<div class="syncpanel"><h2>New source</h2>
          <label class="fieldrow"><span>Title</span>${bind(d.source, 'title')}</label>
          <label class="fieldrow"><span>Author</span>${bind(d.source, 'author')}</label>
          <label class="fieldrow"><span>Pub. info</span>${bind(d.source, 'pubinfo')}</label>
          <label class="fieldrow"><span>Abbreviation</span>${bind(d.source, 'abbrev')}</label>
        </div>` : nothing}
        <div class="syncpanel"><h2>Citation</h2>
          <label class="fieldrow"><span>Page / locator</span>${bind(d.citation, 'page')}</label>
          <label class="fieldrow"><span>Confidence (0–4)</span>${bind(d.citation, 'confidence')}</label>
          <label class="fieldrow"><span>Date</span>
            <input type="text" .value=${d.citation.date
              ? `${d.citation.date.day}.${d.citation.date.month}.${d.citation.date.year}` : ''}
              placeholder="d.m.yyyy or blank"
              @input=${(e) => {
                const m = e.target.value.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                d.citation.date = m
                  ? { day: +m[1], month: +m[2], year: +m[3] }
                  : (e.target.value.trim() ? d.citation.date : null);
              }}>
          </label>
        </div>
        <div class="syncpanel"><h2>Notes</h2>
          <label class="fieldrow"><span>First reference</span>${bind(d.notes, 'first_reference', true)}</label>
          <label class="fieldrow"><span>Short reference</span>${bind(d.notes, 'short_reference', true)}</label>
          <label class="fieldrow"><span>Source list entry</span>${bind(d.notes, 'source_list_entry', true)}</label>
        </div>
      </div>
      <div class="toolbar">
        <button class="primary" ?disabled=${this.busy} @click=${this.save}>
          ${this.busy ? 'Saving…' : 'Save to Gramps'}</button>
        <button @click=${() => (this.step = 'details')}>Back</button>
      </div>`;
  }
}

customElements.define('citations-page', CitationsPage);
