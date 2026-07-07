/* Citation generator: media → describe → review/save. The free-text dump is
   the one composing path (LLM); 'Write manually' is the no-LLM fallback. */
import { BifrostElement, html, nothing, api, post, btn, spinner, chip, field, statusLine } from './core.js';

class CitationsPage extends BifrostElement {
  static properties = {
    step: { state: true },          // media | describe | review
    ctx: { state: true },           // types, sources, repositories, llm
    media: { state: true },         // media listing
    mediaQuery: { state: true },
    originFilter: { state: true },  // paperless | other
    pick: { state: true },          // { media, source, repository }
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
    this.step = 'media';
    this.ctx = null;
    this.media = [];
    this.mediaQuery = '';
    this.originFilter = 'paperless';
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
      [this.ctx, this.media] = await Promise.all([
        api('/citations/api/context'),
        api('/citations/api/media'),
      ]);
    } catch (e) {
      this.loadError = e.message;
    }
  }

  reset() {
    this.step = 'media';
    this.pick = { media: null, source: null, repository: null };
    this.draft = null;
    this.error = '';
    this.saved = null;
    this.dump = '';
    this.matched = null;
  }

  /* ---- compose / save ---- */
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
    const steps = ['media', 'describe', 'review'];
    const atStart = this.step === 'media';
    const n = steps.indexOf(this.step) + 1;
    return html`
      <nav>
        <span class="small-text max">step ${n} of ${steps.length} — ${this.step}</span>
        ${!atStart ? btn('Start over', false, () => this.reset()) : nothing}
      </nav>
      ${this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}
      ${{
        media: () => this.renderMedia(),
        describe: () => this.renderDescribe(),
        review: () => this.renderReview(),
      }[this.step]()}
    `;
  }

  renderMedia() {
    const q = this.mediaQuery.toLowerCase();
    const isPaperless = (m) => m.origin === 'paperless';
    const inFilter = (m) => (this.originFilter === 'paperless' ? isPaperless(m) : !isPaperless(m));
    const rows = this.media
      .filter(inFilter)
      .filter((m) => !q || m.title.toLowerCase().includes(q)
        || m.gramps_id.toLowerCase().includes(q)).slice(0, 80);
    const nPaperless = this.media.filter(isPaperless).length;
    return html`<div>
      <h6 class="small">Pick the media to cite</h6>
      <nav class="wrap">
        ${field('Search media…', this.mediaQuery, (e) => (this.mediaQuery = e.target.value), { type: 'search', width: 'small' })}
        ${chip(`Paperless ${nPaperless}`, this.originFilter === 'paperless', () => (this.originFilter = 'paperless'))}
        ${chip(`Other ${this.media.length - nPaperless}`, this.originFilter === 'other', () => (this.originFilter = 'other'))}
        <span class="small-text">${rows.length} shown</span>
      </nav>
      ${rows.length ? html`
        <div class="scroll capped">
          <ul class="list">
            ${rows.map((m) => html`
              <li class="wave"
                @click=${() => { this.pick = { ...this.pick, media: m }; this.step = 'describe'; }}>
                <span class="mono small-text">${m.gramps_id}</span>
                <div class="max">${m.title}</div>
                ${m.cited ? html`<span class="chip small">cited</span>` : nothing}
              </li>`)}
          </ul>
        </div>` : html`<p class="secondary-text">No media match.</p>`}
    </div>`;
  }

  citingLine() {
    const m = this.pick.media;
    if (!m) return nothing;
    return html`<p class="small-text">Citing: media <strong>${m.title}</strong></p>`;
  }

  renderDescribe() {
    return html`<div>
      <h6 class="small">Describe the record</h6>
      ${this.citingLine()}
      ${field('Dump everything you know: what the record is, who\'s in it, dates, page/entry numbers, archive references, the URL you found it at…',
        this.dump, (e) => (this.dump = e.target.value), { rows: 7 })}
      <p class="small-text">Matches an existing source when one fits; drafts a new one when none does.</p>
      <nav>
        ${this.ctx.llm ? btn(this.busy ? 'Composing…' : 'Compose citation',
          this.busy || !this.dump.trim(), () => this.composeDump()) : nothing}
        ${btn('Write manually', this.busy, () => this.manualDraft())}
        ${btn('Back', this.busy, () => (this.step = 'media'))}
        ${this.busy ? spinner : nothing}
      </nav>
    </div>`;
  }

  renderReview() {
    if (this.saved) {
      return html`<div>
        <p>${statusLine('ok', 'Saved to Gramps.')}</p>
        <table>
          <tbody>${Object.entries(this.saved).map(([k, v]) => html`<tr><td>${k}</td><td>${v}</td></tr>`)}</tbody>
        </table>
        <nav>
          ${btn('New citation', false, () => this.reset())}
        </nav>
      </div>`;
    }
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
