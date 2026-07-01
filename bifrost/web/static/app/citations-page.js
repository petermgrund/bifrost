import { BifrostElement, html, nothing, api, post, btn, spinner, chip, field } from './core.js';

/* Citation generator: media → source → details → review/save. */
class CitationsPage extends BifrostElement {
  static properties = {
    step: { state: true },          // media | describe | details | review
    ctx: { state: true },           // types, sources, repositories, llm
    media: { state: true },         // media listing
    mediaQuery: { state: true },
    originFilter: { state: true },
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
    reviewFrom: { state: true },    // step to return to from review's Back
  };

  constructor() {
    super();
    this.step = 'media';
    this.ctx = null;
    this.media = [];
    this.mediaQuery = '';
    this.originFilter = 'paperless';
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
    this.reviewFrom = 'details';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    try {
      [this.ctx, this.media] = await Promise.all([
        api('/citations/api/context'),
        api('/citations/api/media'),
      ]);
    } catch (e) {
      this.error = e.message;
    }
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
      this.reviewFrom = 'details';
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
      this.reviewFrom = 'describe';
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
    this.reviewFrom = this.step;
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
    if (!this.ctx) return html`<h5>Citations</h5><p class="hint">${this.error || 'Loading…'}</p>`;
    const steps = ['media', 'describe', 'details', 'review'];
    const atStart = this.step === 'media';
    const done = steps.indexOf(this.step);
    return html`
      <div class="row wrap">
        <h5>Citations</h5>
        <div class="tabs left-align max">
          ${steps.map((s, i) => html`<a class="${this.step === s ? 'active' : ''}"
            style=${done < i ? 'pointer-events:none;opacity:.45' : nothing}
            @click=${() => { if (done > i) this.step = s; }}>${i + 1}. ${s}</a>`)}
        </div>
        ${!atStart ? btn('outlined', 'Start over', false, () => this.reset()) : nothing}
      </div>
      ${this.error ? html`<article class="border error-text">${this.error}</article>` : nothing}
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
    const rows = this.media
      .filter((m) => m.origin === this.originFilter)
      .filter((m) => !q || m.title.toLowerCase().includes(q)
        || m.gramps_id.toLowerCase().includes(q)).slice(0, 80);
    return html`
      <div class="row wrap">
        ${field('Search media…', this.mediaQuery, (e) => (this.mediaQuery = e.target.value), { type: 'search', style: 'max-width:16rem' })}
        ${chip('Paperless', this.originFilter === 'paperless', () => (this.originFilter = 'paperless'))}
        ${chip('Photos', this.originFilter === 'immich', () => (this.originFilter = 'immich'))}
        ${chip('Other', this.originFilter === 'other', () => (this.originFilter = 'other'))}
        <span class="hint">${rows.length} shown</span>
      </div>
      <article class="border no-padding scroll" style="max-height:60vh">
        ${rows.map((m, i) => html`
          ${i ? html`<div class="divider"></div>` : nothing}
          <a class="row padding wave"
            @click=${() => { this.pick = { ...this.pick, media: m }; this.step = 'describe'; }}>
            <span class="mono hint">${m.gramps_id}</span>
            <span class="max">${m.title}</span>
            ${m.cited ? html`<span class="chip small">cited</span>` : nothing}
          </a>`)}
      </article>`;
  }

  citingLine() {
    const m = this.pick.media;
    if (!m) return nothing;
    return html`<p class="hint">Citing: media <strong>${m.title}</strong></p>`;
  }

  renderDescribe() {
    return html`
      ${this.citingLine()}
      <article class="border">
        <h6>Describe the record</h6>
        <div class="field textarea label border">
          <textarea rows="7" .value=${this.dump} @input=${(e) => (this.dump = e.target.value)}></textarea>
          <label>Dump everything you know: what the record is, who's in it, dates, page/entry numbers, archive references, the URL you found it at…</label>
        </div>
        <div class="row">
          ${this.ctx.llm ? btn('filled', this.busy ? 'Composing…' : 'Compose citation',
            this.busy || !this.dump.trim(), () => this.composeDump()) : nothing}
          ${btn('outlined', this.wizard ? 'Hide' : 'Structured wizard', false,
            () => (this.wizard = !this.wizard))}
          ${this.busy ? spinner : nothing}
        </div>
        <p class="hint">Matches an existing source when one fits; drafts a new one when none does.</p>
      </article>
      ${this.wizard ? this.renderWizard() : nothing}`;
  }

  renderWizard() {
    const q = this.sourceQuery.toLowerCase();
    const matches = this.ctx.sources.filter((s) =>
      !q || s.title.toLowerCase().includes(q) || s.abbrev.toLowerCase().includes(q)).slice(0, 30);
    return html`
      ${this.citingLine()}
      <h6>Existing source</h6>
      <div class="row">
        ${field('Search sources…', this.sourceQuery, (e) => (this.sourceQuery = e.target.value), { type: 'search', style: 'max-width:16rem' })}
      </div>
      <article class="border no-padding scroll" style="max-height:38vh">
        ${matches.map((s, i) => html`
          ${i ? html`<div class="divider"></div>` : nothing}
          <a class="row padding wave"
            @click=${() => { this.pick = { ...this.pick, source: s, recordType: null }; this.step = 'details'; }}>
            <span class="max">${s.title}</span>
            <span class="hint mono">${s.gramps_id}</span>
          </a>`)}
      </article>
      <h6>…or a new source</h6>
      ${Object.entries(this.ctx.groups).map(([gk, glabel]) => html`
        <p class="hint no-margin">${glabel}</p>
        <div class="row wrap">
          ${this.ctx.types.filter((t) => t.group === gk).map((t) => html`
            <button class="chip" @click=${() => {
              this.pick = { ...this.pick, source: null, recordType: t };
              this.step = 'details';
            }}>${t.label}</button>`)}
        </div>`)}`;
  }

  renderDetails() {
    const t = this.pick.recordType;
    const src = this.pick.source;
    if (!t && !src) {
      // reached with nothing selected (e.g. Back from a dump-composed draft)
      return html`<p class="hint">Nothing to fill in here — this citation was
        composed from a description.</p>
        <div class="row">
          ${btn('outlined', 'Back to describe', false, () => (this.step = 'describe'))}
          ${this.draft ? btn('filled', 'Back to review', false, () => (this.step = 'review')) : nothing}
        </div>`;
    }
    const fieldRow = (key, label, req, hint) =>
      field(`${label}${req ? ' *' : ''}${hint ? ` (${hint})` : ''}`, this.fields[key] || '',
        (e) => (this.fields = { ...this.fields, [key]: e.target.value }));
    return html`
      ${this.citingLine()}
      <p class="hint">${src ? html`→ ${src.abbrev || src.title}` : html`→ new ${t.label}`}</p>
      <article class="border" style="max-width:44rem">
        ${src ? html`
          ${fieldRow('locator', 'Locator within the source (page, entry, dwelling…)', true)}
          ${fieldRow('person', 'Person(s) / item of interest', true)}
          ${fieldRow('event_date', 'Date of the record entry', false)}
          ${fieldRow('extra', 'Anything else relevant', false)}
        ` : t.fields.map((f) => fieldRow(f.key, f.label, f.req, f.hint))}
      </article>
      <div class="row">
        ${this.ctx.llm
          ? btn('filled', this.busy ? 'Composing…' : 'Compose citation', this.busy, () => this.compose())
          : nothing}
        ${btn('outlined', 'Write manually', false, () => this.manualDraft())}
        ${this.busy ? spinner : nothing}
      </div>`;
  }

  renderReview() {
    if (this.saved) {
      return html`<article class="border">
        <h6>Saved</h6>
        <table class="stripes">
          <tbody>${Object.entries(this.saved).map(([k, v]) => html`<tr><td>${k}</td><td>${v}</td></tr>`)}</tbody>
        </table>
        <div class="row">
          ${btn('filled', 'New citation', false, () => this.reset())}
        </div>
      </article>`;
    }
    const d = this.draft;
    const m = this.matched;
    const matchedBanner = m && (m.source || m.repository)
      ? html`<p class="hint">${m.source
          ? html`Using existing source <strong>${m.source.gramps_id}</strong> — ${m.source.title}`
          : html`New source in existing repository <strong>${m.repository.gramps_id}</strong> — ${m.repository.name}`}</p>`
      : nothing;
    const bind = (obj, key, label, multiline = false) => multiline
      ? html`<div class="field textarea label border">
          <textarea rows="4" .value=${obj[key] || ''} @input=${(e) => { obj[key] = e.target.value; }}></textarea>
          <label>${label}</label></div>`
      : html`<div class="field label border">
          <input .value=${String(obj[key] ?? '')} @input=${(e) => { obj[key] = e.target.value; }}>
          <label>${label}</label></div>`;
    return html`
      ${matchedBanner}
      ${d.quality ? html`<p class="hint">${d.quality.source_type} source ·
        ${d.quality.information_type.toLowerCase()} information ·
        ${d.quality.evidence_type.toLowerCase()} evidence — ${d.quality.note}</p>` : nothing}
      <div class="grid">
        ${d.repository ? html`<article class="s12 m6 border"><h6>New repository</h6>
          ${bind(d.repository, 'name', 'Name')}
          ${bind(d.repository, 'type', 'Type')}
          ${bind(d.repository, 'url', 'URL')}
          ${bind(d, 'call_number', 'Call number')}
        </article>` : nothing}
        ${d.source ? html`<article class="s12 m6 border"><h6>New source</h6>
          ${bind(d.source, 'title', 'Title')}
          ${bind(d.source, 'author', 'Author')}
          ${bind(d.source, 'pubinfo', 'Pub. info')}
          ${bind(d.source, 'abbrev', 'Abbreviation')}
        </article>` : nothing}
        <article class="s12 m6 border"><h6>Citation</h6>
          ${bind(d.citation, 'page', 'Page / locator')}
          ${bind(d.citation, 'confidence', 'Confidence (0–4)')}
        </article>
        <article class="s12 m6 border"><h6>Notes</h6>
          ${bind(d.notes, 'first_reference', 'First reference', true)}
          ${bind(d.notes, 'short_reference', 'Short reference', true)}
          ${bind(d.notes, 'abstract', 'Abstract', true)}
        </article>
      </div>
      <div class="row">
        ${btn('filled', this.busy ? 'Saving…' : 'Save to Gramps', this.busy, () => this.save())}
        ${btn('outlined', 'Back', false, () => (this.step = this.reviewFrom || 'details'))}
        ${this.busy ? spinner : nothing}
      </div>`;
  }
}

customElements.define('citations-page', CitationsPage);
