import { BifrostElement, html, nothing, api, post, mdBtn, mdSpinner } from './core.js';

const shuffle = (arr) => {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

/* Citation generator: media → source → details → review/save.
   Or event mode: cycle uncited events → compose a citation for the event
   (media optional) → review/save; the citation auto-attaches to the event. */
class CitationsPage extends BifrostElement {
  static properties = {
    mode: { state: true },          // media | event
    step: { state: true },          // event | media | describe | details | review
    ctx: { state: true },           // types, sources, repositories, llm
    media: { state: true },         // media listing
    mediaQuery: { state: true },
    originFilter: { state: true },
    pick: { state: true },          // { media, source, repository, recordType, event }
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
    eventQueue: { state: true },    // shuffled light uncited-event list
    eventPos: { state: true },
    event: { state: true },         // current event detail
    eventBusy: { state: true },
    reviewFrom: { state: true },    // step to return to from review's Back
  };

  constructor() {
    super();
    this.mode = 'media';
    this.step = 'media';
    this.ctx = null;
    this.media = [];
    this.mediaQuery = '';
    this.originFilter = 'paperless';
    this.pick = { media: null, source: null, repository: null, recordType: null, event: null };
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
    this.eventQueue = null;
    this.eventPos = 0;
    this.event = null;
    this.eventBusy = false;
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
    this.step = this.mode === 'event' ? 'event' : 'media';
    this.pick = { media: null, source: null, repository: null, recordType: null, event: null };
    this.fields = {};
    this.draft = null;
    this.error = '';
    this.saved = null;
    this.dump = '';
    this.matched = null;
    this.wizard = false;
  }

  /* ---- event-cite mode ---- */
  async enterEventMode() {
    this.mode = 'event';
    this.reset();
    if (!this.eventQueue) {
      this.eventBusy = true;
      try {
        const evs = await api('/citations/api/uncited-events');
        this.eventQueue = shuffle(evs);
        this.eventPos = 0;
        await this.loadEvent();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.eventBusy = false;
      }
    }
  }

  enterMediaMode() {
    this.mode = 'media';
    this.reset();
  }

  async loadEvent() {
    const row = this.eventQueue?.[this.eventPos];
    if (!row) { this.event = null; return; }
    this.eventBusy = true;
    this.event = null;
    try {
      this.event = await api(`/citations/api/event/${row.handle}`);
    } catch (e) {
      this.error = e.message;
    } finally {
      this.eventBusy = false;
    }
  }

  nextEvent() {
    if (!this.eventQueue?.length) return;
    this.eventPos = (this.eventPos + 1) % this.eventQueue.length;
    this.loadEvent();
  }

  dropCurrentEvent() {
    // remove the just-cited event from the queue so counts stay honest
    if (!this.eventQueue) return;
    this.eventQueue = this.eventQueue.filter((_, i) => i !== this.eventPos);
    if (this.eventPos >= this.eventQueue.length) this.eventPos = 0;
  }

  startCitingEvent(media) {
    // The event is the subject (its facts feed the composer as event_context);
    // the dump is for describing the SOURCE, media is an optional attachment.
    this.pick = { ...this.pick, media: media || null, event: this.event,
      source: null, repository: null, recordType: null };
    this.dump = '';
    this.matched = null;
    this.draft = null;
    this.error = '';
    this.step = 'describe';
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
        event_context: this.pick.event?.context || null,
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
        event_context: this.pick.event?.context || null,
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
        event_handle: this.pick.event?.handle || null,
      });
      if (this.pick.event) this.dropCurrentEvent();
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  /* ---- render ---- */
  render() {
    if (!this.ctx) return html`<h1>Citations</h1><div class="hint">${this.error || 'Loading…'}</div>`;
    const first = this.mode === 'event' ? 'event' : 'media';
    const steps = [first, 'describe', 'details', 'review'];
    const atStart = this.step === first;
    return html`
      <div class="pagehead">
        <h1>Citations</h1>
        <div class="tabs">
          ${steps.map((s, i) => html`<md-text-button class="tab ${this.step === s ? 'active' : ''}"
            ?disabled=${steps.indexOf(this.step) < i}
            @click=${() => { if (steps.indexOf(this.step) > i) this.step = s; }}>
            ${i + 1}. ${s}</md-text-button>`)}
        </div>
        <span class="spacer"></span>
        ${!atStart ? mdBtn('outlined', 'Start over', false, this.reset) : nothing}
      </div>
      <div class="toolbar">
        <md-chip-set>
          <md-filter-chip label="Cite media" ?selected=${this.mode === 'media'}
            @click=${this.enterMediaMode}></md-filter-chip>
          <md-filter-chip label="Cite uncited events" ?selected=${this.mode === 'event'}
            @click=${this.enterEventMode}></md-filter-chip>
        </md-chip-set>
      </div>
      ${this.error ? html`<div class="alert">${this.error}</div>` : nothing}
      ${{
        event: () => this.renderEvent(),
        media: () => this.renderMedia(),
        describe: () => this.renderDescribe(),
        details: () => this.renderDetails(),
        review: () => this.renderReview(),
      }[this.step]()}
    `;
  }

  renderEvent() {
    if (this.eventBusy && !this.event) return html`<div class="hint">Loading…</div>`;
    if (!this.eventQueue) return html`<div class="hint">Loading…</div>`;
    if (!this.eventQueue.length) {
      return html`<div class="syncpanel"><h2>All events cited</h2>
        <p class="hint">No events are missing a citation. Nice.</p></div>`;
    }
    const e = this.event;
    const pos = `${this.eventPos + 1} of ${this.eventQueue.length} uncited`;
    return html`
      <div class="toolbar">
        <span class="hint">${pos}</span>
        <span class="spacer"></span>
        ${mdBtn('outlined', 'Skip — next random ↻', false, () => this.nextEvent())}
      </div>
      ${!e ? html`<div class="hint">Loading event…</div>` : html`
        <div class="syncpanel">
          <h2>${e.summary || e.type}</h2>
          <p class="hint">
            ${e.type}${e.date ? html` · ${e.date}` : nothing}${e.place ? html` · ${e.place}` : nothing}
            · <a href="${this.ctx.gramps_url || ''}/event/${e.gramps_id}" target="_blank">${e.gramps_id}</a>
          </p>
          ${e.participants.length ? html`<p class="hint">People:
            ${e.participants.map((p, i) => html`${i ? ', ' : ''}${p.name}${p.life}${p.role && p.role !== 'Primary' ? ` (${p.role.toLowerCase()})` : ''}`)}</p>` : nothing}
          <div class="toolbar">
            ${mdBtn('filled', 'Create citation for this event →', false, () => this.startCitingEvent(null))}
          </div>
        </div>
        ${e.media.length ? html`
          <p class="hint">…or start from a related media object (it'll be attached to the citation too):</p>
          <div class="cardlist" style="max-height:40vh">
            ${e.media.map((m) => html`<div class="card" @click=${() => this.startCitingEvent(m)}>
              <span class="cid">${m.gramps_id}</span>
              <span class="name">${m.title}</span>
              ${m.cited ? html`<span class="badge unlinked">cited</span>` : nothing}
            </div>`)}
          </div>` : nothing}`}`;
  }

  renderMedia() {
    const q = this.mediaQuery.toLowerCase();
    const rows = this.media
      .filter((m) => m.origin === this.originFilter)
      .filter((m) => !q || m.title.toLowerCase().includes(q)
        || m.gramps_id.toLowerCase().includes(q)).slice(0, 80);
    const chip = (f, label) => html`<md-filter-chip label=${label}
      ?selected=${this.originFilter === f}
      @click=${() => (this.originFilter = f)}></md-filter-chip>`;
    return html`
      <div class="toolbar">
        <md-outlined-text-field label="Search media…" type="search" .value=${this.mediaQuery}
          @input=${(e) => (this.mediaQuery = e.target.value)}></md-outlined-text-field>
        <md-chip-set>${chip('paperless', 'Paperless')}${chip('immich', 'Immich')}</md-chip-set>
        <span class="hint">${rows.length} shown</span>
      </div>
      <div class="cardlist" style="max-height:60vh">
        ${rows.map((m) => html`<div class="card"
          @click=${() => { this.pick = { ...this.pick, media: m }; this.step = 'describe'; }}>
          <span class="cid">${m.gramps_id}</span>
          <span class="name">${m.title}</span>
          ${m.cited ? html`<span class="badge unlinked">cited</span>` : nothing}
        </div>`)}
      </div>`;
  }

  citingLine() {
    const ev = this.pick.event, m = this.pick.media;
    if (!ev && !m) return nothing;
    return html`<p class="hint">Citing:
      ${ev ? html`event <strong>${ev.summary || ev.type}</strong>` : nothing}
      ${ev && m ? ' from ' : nothing}
      ${m ? html`media <strong>${m.title}</strong>` : (ev ? nothing : '')}</p>`;
  }

  eventFacts() {
    const e = this.pick.event;
    if (!e) return nothing;
    return html`<div class="eventfacts">
      ${e.context.split('\n').map((line) => html`<div>${line}</div>`)}
      <div class="hint">These facts are sent to the composer automatically.</div>
    </div>`;
  }

  renderDescribe() {
    const ev = this.pick.event;
    return html`
      ${this.citingLine()}
      ${this.eventFacts()}
      <div class="syncpanel">
        <h2>Describe the ${ev ? 'source record' : 'record'}</h2>
        <md-outlined-text-field type="textarea" rows="7" label=${ev
          ? 'Describe the record that evidences this event: what it is (census, parish register, certificate…), the archive or website, page/entry numbers, the URL you found it at. The event facts above are already included.'
          : "Dump everything you know: what the record is, who's in it, dates, page/entry numbers, archive references, the URL you found it at…"}
          .value=${this.dump} @input=${(e) => (this.dump = e.target.value)}></md-outlined-text-field>
        <div class="toolbar">
          ${this.ctx.llm ? mdBtn('filled', this.busy ? 'Composing…' : 'Compose citation',
            this.busy || (!this.dump.trim() && !ev), this.composeDump) : nothing}
          ${mdBtn('outlined', this.wizard ? 'Hide' : 'Structured wizard', false,
            () => (this.wizard = !this.wizard))}
          ${this.busy ? mdSpinner : nothing}
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
      ${this.citingLine()}
      <h2>Existing source</h2>
      <div class="toolbar">
        <md-outlined-text-field label="Search sources…" type="search" .value=${this.sourceQuery}
          @input=${(e) => (this.sourceQuery = e.target.value)}></md-outlined-text-field>
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
            <md-text-button @click=${() => {
              this.pick = { ...this.pick, source: null, recordType: t };
              this.step = 'details';
            }}>${t.label}</md-text-button>`)}`)}
      </div>`;
  }

  renderDetails() {
    const t = this.pick.recordType;
    const src = this.pick.source;
    if (!t && !src) {
      // reached with nothing selected (e.g. Back from a dump-composed draft)
      return html`<p class="hint">Nothing to fill in here — this citation was
        composed from a description.</p>
        <div class="toolbar">
          ${mdBtn('outlined', 'Back to describe', false, () => (this.step = 'describe'))}
          ${this.draft ? mdBtn('filled', 'Back to review', false, () => (this.step = 'review')) : nothing}
        </div>`;
    }
    const fieldRow = (key, label, req, hint) => html`
      <label class="fieldrow">
        <span>${label}${req ? ' *' : ''}</span>
        <md-outlined-text-field .value=${this.fields[key] || ''} placeholder=${hint || ''}
          @input=${(e) => (this.fields = { ...this.fields, [key]: e.target.value })}></md-outlined-text-field>
      </label>`;
    return html`
      ${this.citingLine()}
      <p class="hint">${src ? html`→ ${src.abbrev || src.title}` : html`→ new ${t.label}`}</p>
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
          ? mdBtn('filled', this.busy ? 'Composing…' : 'Compose citation', this.busy, this.compose)
          : nothing}
        ${mdBtn('outlined', 'Write manually', false, this.manualDraft)}
        ${this.busy ? mdSpinner : nothing}
      </div>`;
  }

  renderReview() {
    if (this.saved) {
      return html`<div class="syncpanel">
        <h2>Saved</h2>
        <table class="results">
          ${Object.entries(this.saved).map(([k, v]) => html`<tr><td>${k}</td><td>${v}</td></tr>`)}
        </table>
        <div class="toolbar">
          ${this.mode === 'event'
            ? mdBtn('filled', 'Next event →', false, () => { this.reset(); this.loadEvent(); })
            : mdBtn('filled', 'New citation', false, this.reset)}
        </div>
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
      ? html`<md-outlined-text-field type="textarea" rows="4" .value=${obj[key] || ''}
          @input=${(e) => { obj[key] = e.target.value; }}></md-outlined-text-field>`
      : html`<md-outlined-text-field .value=${String(obj[key] ?? '')}
          @input=${(e) => { obj[key] = e.target.value; }}></md-outlined-text-field>`;
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
        </div>
        <div class="syncpanel"><h2>Notes</h2>
          <label class="fieldrow"><span>First reference</span>${bind(d.notes, 'first_reference', true)}</label>
          <label class="fieldrow"><span>Short reference</span>${bind(d.notes, 'short_reference', true)}</label>
          <label class="fieldrow"><span>Abstract</span>${bind(d.notes, 'abstract', true)}</label>
        </div>
      </div>
      <div class="toolbar">
        ${mdBtn('filled', this.busy ? 'Saving…' : 'Save to Gramps', this.busy, this.save)}
        ${mdBtn('outlined', 'Back', false, () => (this.step = this.reviewFrom || 'details'))}
        ${this.busy ? mdSpinner : nothing}
      </div>`;
  }
}

customElements.define('citations-page', CitationsPage);
