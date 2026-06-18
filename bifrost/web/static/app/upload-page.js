import { BifrostElement, html, nothing, api, post, iconYes, iconPending } from './core.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const EMPTY_FORM = () => ({
  title: '', date: '', document_type: null, correspondent: null, tags: [],
  date_meaning: null, date_qualifier: null, family_group: null,
  source_url: '', source_url_access: null,
});

/* Full intake wizard: ingest a Paperless doc (or pick an existing one), edit its
   metadata beside a live preview (house-style autofill), mint a Gramps media
   object, then compose a citation and attach it to an event — all in one page. */
class UploadPage extends BifrostElement {
  static properties = {
    step: { state: true },          // start | edit | cite
    startMode: { state: true },     // upload | existing
    ocrOnUpload: { state: true },
    busy: { state: true }, error: { state: true }, progress: { state: true },
    docId: { state: true }, kind: { state: true },
    options: { state: true }, form: { state: true },
    transcript: { state: true }, hasTranscript: { state: true },
    savedFields: { state: true },
    candidates: { state: true }, candQuery: { state: true },
    media: { state: true },
    citeStep: { state: true },      // describe | review
    dump: { state: true }, draft: { state: true }, matched: { state: true },
    saved: { state: true },
    events: { state: true }, eventQuery: { state: true }, eventSel: { state: true },
  };

  constructor() {
    super();
    this.step = 'start'; this.startMode = 'upload'; this.ocrOnUpload = true;
    this.busy = false; this.error = ''; this.progress = '';
    this.docId = null; this.kind = 'other';
    this.options = null; this.form = EMPTY_FORM();
    this.transcript = ''; this.hasTranscript = false; this.savedFields = false;
    this.candidates = null; this.candQuery = '';
    this.media = null;
    this.citeStep = 'describe'; this.dump = ''; this.draft = null;
    this.matched = null; this.saved = null;
    this.events = null; this.eventQuery = ''; this.eventSel = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadOptions();
  }

  async loadOptions() {
    try { this.options = await api('/upload/api/options'); }
    catch (e) { this.error = `options: ${e.message}`; }
  }

  // ---- option lookups ----
  selLabel(key, id) {
    const o = (this.options?.selects?.[key] || []).find((x) => x.id === id);
    return o ? o.label : '';
  }
  corrName(id) { return (this.options?.correspondents || []).find((c) => c.id === id)?.name || ''; }
  docTypeName(id) { return (this.options?.document_types || []).find((d) => d.id === id)?.name || ''; }
  tagName(id) { return (this.options?.tags || []).find((t) => t.id === id)?.name || `#${id}`; }

  // ================= start: upload =================
  async handleFile(file) {
    if (!file) return;
    this.error = ''; this.busy = true;
    try {
      this.progress = 'Uploading…';
      const resp = await fetch(
        `/upload/api/ingest?filename=${encodeURIComponent(file.name)}&ocr=${this.ocrOnUpload ? 1 : 0}`,
        { method: 'POST', headers: { 'Content-Type': file.type || 'application/octet-stream' }, body: file });
      if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
      const { task } = await resp.json();
      this.progress = 'Consuming…';
      const docId = await this.pollConsume(task);
      if (this.ocrOnUpload) {
        this.progress = 'Transcribing…';
        const r = await post(`/upload/api/ocr/${docId}`, {});
        this.transcript = r.transcript || '';
      }
      await this.enterEdit(docId);
    } catch (e) { this.error = e.message; }
    finally { this.busy = false; this.progress = ''; }
  }

  async pollConsume(task) {
    // Paperless consume runs its own OCR (ocrmypdf); a multi-page scan on the
    // Pi's ARM CPU can take several minutes. Poll generously, show elapsed time,
    // and on timeout point at the recoverable path rather than failing hard.
    const deadline = Date.now() + 12 * 60 * 1000;
    let waited = 0;
    while (Date.now() < deadline) {
      const s = await api(`/upload/api/ingest-status?task=${encodeURIComponent(task)}`);
      if (s.status === 'SUCCESS' && s.doc_id) return s.doc_id;
      if (s.status === 'FAILURE') throw new Error(s.error || 'Paperless rejected the file');
      await sleep(2500);
      waited += 2500;
      this.progress = `Paperless is processing the document — OCR can take a few minutes on the Pi… (${Math.round(waited / 1000)}s)`;
    }
    throw new Error('Paperless is still processing this document. It will finish in '
      + 'the background — once it does, reopen Upload, choose "Pick existing '
      + 'document", and select it. Don’t re-upload the same file (Paperless flags duplicates).');
  }

  // ================= start: existing =================
  async loadCandidates(refresh = false) {
    this.error = '';
    try {
      this.candidates = await api(`/upload/api/documents${refresh ? '?refresh=true' : ''}`);
    } catch (e) { this.error = `documents: ${e.message}`; }
  }

  async pickExisting(docId) {
    this.error = ''; this.busy = true;
    try { await this.enterEdit(docId); }
    catch (e) { this.error = e.message; }
    finally { this.busy = false; }
  }

  // ================= shared: enter edit =================
  async enterEdit(docId) {
    const d = await api(`/upload/api/doc/${docId}`);
    this.docId = docId;
    this.form = { ...EMPTY_FORM(), ...d.form };
    this.kind = d.kind;
    this.hasTranscript = d.has_transcript;
    if (d.transcript) this.transcript = d.transcript;
    this.savedFields = false;
    this.step = 'edit';
  }

  // ================= edit actions =================
  async runOcr() {
    this.error = ''; this.busy = true; this.progress = 'Transcribing…';
    try {
      const r = await post(`/upload/api/ocr/${this.docId}`, {});
      this.transcript = r.transcript || '';
      this.hasTranscript = (r.chars || 0) > 0;
      if (r.errors?.length && !this.hasTranscript) this.error = r.errors.join('; ');
    } catch (e) { this.error = e.message; }
    finally { this.busy = false; this.progress = ''; }
  }

  async autofillForm() {
    this.error = ''; this.busy = true; this.progress = 'Asking the model…';
    try {
      const r = await post(`/upload/api/autofill/${this.docId}`, {});
      this.form = { ...this.form, ...(r.guesses || {}) };
      this.savedFields = false;
    } catch (e) { this.error = e.message; }
    finally { this.busy = false; this.progress = ''; }
  }

  async saveFields() {
    await post(`/upload/api/fields/${this.docId}`, this.form);
    this.savedFields = true;
  }

  async createMedia() {
    this.error = ''; this.busy = true; this.progress = 'Saving metadata…';
    try {
      await this.saveFields();
      this.progress = 'Creating Gramps media…';
      this.media = await post(`/upload/api/to-gramps/${this.docId}`, {});
      this.step = 'cite'; this.citeStep = 'describe';
    } catch (e) { this.error = e.message; }
    finally { this.busy = false; this.progress = ''; }
  }

  setField(key, value) { this.form = { ...this.form, [key]: value }; }
  toggleTag(id) {
    const has = this.form.tags.includes(id);
    this.setField('tags', has ? this.form.tags.filter((t) => t !== id) : [...this.form.tags, id]);
  }

  // ================= cite actions =================
  includeTranscript() {
    const parts = [];
    if (this.dump.trim()) parts.push(this.dump.trim());
    const meta = this.metaSummary();
    if (meta) parts.push(meta);
    if (this.transcript) parts.push(`OCR TRANSCRIPT:\n${this.transcript}`);
    this.dump = parts.join('\n\n');
  }

  metaSummary() {
    const f = this.form; const lines = [];
    if (f.title) lines.push(`Title: ${f.title}`);
    if (f.date) {
      const q = this.selLabel('date_qualifier', f.date_qualifier);
      const m = this.selLabel('date_meaning', f.date_meaning);
      const tag = [q, m].filter(Boolean).join(', ');
      lines.push(`Date: ${f.date}${tag ? ` (${tag})` : ''}`);
    }
    if (f.correspondent) lines.push(`Provider: ${this.corrName(f.correspondent)}`);
    if (f.document_type) lines.push(`Document type: ${this.docTypeName(f.document_type)}`);
    if (f.source_url) {
      const acc = this.selLabel('source_url_access', f.source_url_access);
      lines.push(`Source URL: ${f.source_url}${acc ? ` (${acc})` : ''}`);
    }
    return lines.length ? `RECORD METADATA:\n${lines.join('\n')}` : '';
  }

  async loadEvents(refresh = false) {
    try { this.events = await api(`/upload/api/events${refresh ? '?refresh=true' : ''}`); }
    catch (e) { this.error = `events: ${e.message}`; }
  }

  async selectEvent(handle) {
    this.error = '';
    try { this.eventSel = await api(`/citations/api/event/${handle}`); }
    catch (e) { this.error = `event: ${e.message}`; }
  }

  async composeDump() {
    this.error = ''; this.busy = true; this.progress = 'Composing…';
    try {
      const r = await post('/citations/api/compose-dump', {
        dump: this.dump, media_handle: this.media.media_handle,
        event_context: this.eventSel?.context || null,
      });
      this.draft = r.draft;
      this.matched = { source: r.matched_source, repository: r.matched_repository };
      this.citeStep = 'review';
    } catch (e) { this.error = e.message; }
    finally { this.busy = false; this.progress = ''; }
  }

  async saveCitation() {
    this.error = ''; this.busy = true; this.progress = 'Saving to Gramps…';
    try {
      this.saved = await post('/citations/api/save', {
        draft: this.draft,
        media_handle: this.media.media_handle,
        source_handle: this.matched?.source?.handle || null,
        repository_handle: this.matched?.repository?.handle || null,
        event_handle: this.eventSel?.handle || null,
      });
    } catch (e) { this.error = e.message; }
    finally { this.busy = false; this.progress = ''; }
  }

  resetAll() {
    Object.assign(this, {
      step: 'start', docId: null, form: EMPTY_FORM(), transcript: '',
      hasTranscript: false, savedFields: false, media: null, dump: '',
      draft: null, matched: null, saved: null, eventSel: null, citeStep: 'describe',
    });
    this.requestUpdate();
  }

  // ================= render =================
  render() {
    const steps = [['start', 'Start'], ['edit', 'Edit'], ['cite', 'Citation']];
    const idx = steps.findIndex((s) => s[0] === this.step);
    return html`
      <div class="pagehead">
        <h1>Upload</h1>
        <div class="tabs">
          ${steps.map(([k, label], i) => html`<button class="tab ${this.step === k ? 'active' : ''}"
            ?disabled=${i > idx} @click=${() => { if (i < idx) this.step = k; }}>${i + 1}. ${label}</button>`)}
        </div>
      </div>
      ${this.error ? html`<div class="alert">${this.error}</div>` : nothing}
      ${this.busy ? html`<p class="hint">${this.progress || 'Working…'}</p>` : nothing}
      ${this.step === 'start' ? this.renderStart()
        : this.step === 'edit' ? this.renderEdit()
        : this.renderCite()}`;
  }

  // ---- start ----
  renderStart() {
    const tab = (m, label) => html`<button class="tab ${this.startMode === m ? 'active' : ''}"
      @click=${() => { this.startMode = m; if (m === 'existing' && !this.candidates) this.loadCandidates(); }}>${label}</button>`;
    return html`
      <div class="tabs" style="margin-bottom:1.1rem">${tab('upload', 'Upload new file')}${tab('existing', 'Pick existing document')}</div>
      ${this.startMode === 'upload' ? this.renderDrop() : this.renderExisting()}`;
  }

  renderDrop() {
    return html`
      <div class="dropzone" @dragover=${(e) => { e.preventDefault(); e.currentTarget.classList.add('over'); }}
        @dragleave=${(e) => e.currentTarget.classList.remove('over')}
        @drop=${(e) => { e.preventDefault(); e.currentTarget.classList.remove('over'); this.handleFile(e.dataTransfer.files[0]); }}
        @click=${() => this.renderRoot.querySelector('#fileinput').click()}>
        <input id="fileinput" type="file" hidden
          @change=${(e) => this.handleFile(e.target.files[0])}>
        <p><b>Drop a file here</b> or click to choose</p>
        <p class="hint">PDF or image — goes straight into the Paperless ingest pipeline.</p>
      </div>
      <label class="opt" style="margin-top:.7rem">
        <input type="checkbox" .checked=${this.ocrOnUpload}
          @change=${(e) => (this.ocrOnUpload = e.target.checked)}>
        Run Gemini OCR right after ingesting <span class="hint">(enables house-style autofill)</span>
      </label>`;
  }

  renderExisting() {
    if (!this.candidates) return html`<p class="hint">Loading documents…</p>`;
    const q = this.candQuery.trim().toLowerCase();
    const shown = !q ? this.candidates : this.candidates.filter((d) =>
      (d.title || '').toLowerCase().includes(q) || String(d.id) === q
      || this.corrName(d.correspondent).toLowerCase().includes(q));
    return html`
      <p class="hint">Documents not yet in Gramps (no Gramps ID). Already-synced docs are hidden so they can't be duplicated.</p>
      <div class="toolbar">
        <input type="search" placeholder="Search title / id / provider…" .value=${this.candQuery}
          @input=${(e) => (this.candQuery = e.target.value)} style="max-width:22rem">
        <button @click=${() => this.loadCandidates(true)}>Refresh</button>
        <span class="hint">${shown.length} shown</span>
      </div>
      <div class="cardlist" style="max-height:60vh">
        ${shown.map((d) => html`<div class="card" @click=${() => this.pickExisting(d.id)}>
          <span class="name">${d.title}</span>
          <span class="meta">${d.created || ''}${d.correspondent ? ` · ${this.corrName(d.correspondent)}` : ''}
            ${d.tags.map((t) => html`<span class="badge unlinked">${this.tagName(t)}</span>`)}</span>
        </div>`)}
      </div>`;
  }

  // ---- edit ----
  renderEdit() {
    return html`<div class="detail-body">
      <div>${this.renderForm()}</div>
      <div class="previewpane">${this.renderPreview()}</div>
    </div>`;
  }

  renderPreview() {
    const src = `/upload/api/preview/${this.docId}`;
    if (this.kind === 'image') return html`<img src=${src} alt="preview">`;
    return html`<iframe src=${src} title="document preview"></iframe>`;
  }

  selectRow(label, key, items, { numeric = false, labelKey = 'label' } = {}) {
    // Use ?selected per-option, NOT .value on the <select>: Lit commits the
    // select's property binding before its <option> children exist, so .value
    // would be dropped on first paint and a prefilled value would show blank.
    const cur = String(this.form[key] ?? '');
    return html`<label class="fieldrow"><span>${label}</span>
      <select @change=${(e) => {
        const v = e.target.value;
        this.setField(key, !v ? null : numeric ? parseInt(v, 10) : v);
      }}>
        <option value="" ?selected=${cur === ''}>— none —</option>
        ${items.map((o) => html`<option value=${String(o.id)}
          ?selected=${cur === String(o.id)}>${o[labelKey] || o.name}</option>`)}
      </select></label>`;
  }

  renderForm() {
    const o = this.options || { selects: {}, correspondents: [], document_types: [], tags: [] };
    const text = (label, key, type = 'text') => html`<label class="fieldrow"><span>${label}</span>
      <input type=${type} .value=${this.form[key] || ''}
        @input=${(e) => this.setField(key, e.target.value)}></label>`;
    return html`
      <div class="toolbar">
        <button class="primary" ?disabled=${!this.hasTranscript || this.busy}
          title=${this.hasTranscript ? 'Fill the form from the transcript + house style' : 'Run OCR first to enable autofill'}
          @click=${() => this.autofillForm()}>Autofill from house style</button>
        <button ?disabled=${this.busy} @click=${() => this.runOcr()}>
          ${this.hasTranscript ? 'Re-run OCR' : 'Run OCR'}</button>
        <span class="hint">${this.hasTranscript ? html`${iconYes} transcript ready` : html`${iconPending} no transcript`}</span>
      </div>
      <div class="fieldform">
        ${text('Title', 'title')}
        ${text('Date', 'date', 'date')}
        ${this.selectRow('Date meaning', 'date_meaning', o.selects.date_meaning || [])}
        ${this.selectRow('Date qualifier', 'date_qualifier', o.selects.date_qualifier || [])}
        ${this.selectRow('Document type', 'document_type', o.document_types, { numeric: true, labelKey: 'name' })}
        ${this.selectRow('Family group', 'family_group', o.selects.family_group || [])}
        ${this.selectRow('Digital provider', 'correspondent', o.correspondents, { numeric: true, labelKey: 'name' })}
        ${text('Source URL', 'source_url')}
        ${this.selectRow('Source URL access', 'source_url_access', o.selects.source_url_access || [])}
      </div>
      <label class="fieldrow"><span>Tags</span>
        <div class="toolbar" style="margin:.2rem 0">
          ${o.tags.map((t) => html`<button class="chip ${this.form.tags.includes(t.id) ? 'active' : ''}"
            @click=${() => this.toggleTag(t.id)}>${t.name}</button>`)}
        </div>
      </label>
      <div class="toolbar">
        <button ?disabled=${this.busy} @click=${async () => {
          this.busy = true; this.progress = 'Saving…';
          try { await this.saveFields(); } catch (e) { this.error = e.message; }
          finally { this.busy = false; this.progress = ''; }
        }}>Save metadata</button>
        <button class="primary" ?disabled=${this.busy} @click=${() => this.createMedia()}>
          Create Gramps media &amp; continue →</button>
        ${this.savedFields ? html`<span class="hint">${iconYes} saved</span>` : nothing}
      </div>`;
  }

  // ---- cite ----
  renderCite() {
    if (this.saved) return this.renderSaved();
    return html`
      ${this.media ? html`<p class="hint">Gramps media <b>${this.media.gramps_id}</b> — ${this.media.desc}</p>` : nothing}
      ${this.citeStep === 'describe' ? this.renderDescribe() : this.renderReview()}`;
  }

  renderDescribe() {
    return html`
      <section class="syncpanel">
        <h2>Describe the record</h2>
        <p class="hint">What is this record — census, parish register, certificate…? Archive/website, page/entry, URL. The transcript and the metadata you set can be folded in.</p>
        <textarea rows="8" .value=${this.dump}
          @input=${(e) => (this.dump = e.target.value)}></textarea>
        <div class="toolbar">
          <button ?disabled=${!this.transcript} @click=${() => this.includeTranscript()}>Include OCR transcript &amp; metadata</button>
        </div>
      </section>
      ${this.renderEventPicker()}
      <div class="toolbar">
        <button class="primary" ?disabled=${this.busy || (!this.dump.trim() && !this.eventSel)}
          @click=${() => this.composeDump()}>Compose citation</button>
      </div>`;
  }

  renderEventPicker() {
    return html`<section class="syncpanel maintenance">
      <h2>Attach to an event <span class="hint">(optional)</span></h2>
      ${this.eventSel ? html`<p>${iconYes} <b>${this.eventSel.type}</b>${this.eventSel.date ? `, ${this.eventSel.date}` : ''}
        ${this.eventSel.place ? ` · ${this.eventSel.place}` : ''}
        ${this.eventSel.participants?.length ? html`<span class="hint"> — ${this.eventSel.participants.map((p) => p.name).join(', ')}</span>` : nothing}
        <button class="applyone" @click=${() => (this.eventSel = null)}>clear</button></p>` : nothing}
      <div class="toolbar">
        <input type="search" placeholder="Search events: type / date / place / person…" .value=${this.eventQuery}
          @input=${(e) => (this.eventQuery = e.target.value)} @focus=${() => { if (!this.events) this.loadEvents(); }}
          style="max-width:24rem">
        <button @click=${() => this.loadEvents(true)}>Refresh</button>
      </div>
      ${this.renderEventList()}
    </section>`;
  }

  renderEventList() {
    if (!this.events) return html`<p class="hint">Click the search box to load events.</p>`;
    const q = this.eventQuery.trim().toLowerCase();
    if (!q) return html`<p class="hint">${this.events.length} events — type to search.</p>`;
    const shown = this.events.filter((e) =>
      [e.type, e.date, e.place, e.description, e.gramps_id].some((v) => (v || '').toLowerCase().includes(q))
    ).slice(0, 40);
    return html`<div class="cardlist" style="max-height:40vh">
      ${shown.map((e) => html`<div class="card" @click=${() => this.selectEvent(e.handle)}>
        <span class="name">${e.type}${e.date ? `, ${e.date}` : ''}</span>
        <span class="meta">${e.place || ''}${e.description ? ` · ${e.description}` : ''}
          ${e.cited ? html`<span class="badge">cited</span>` : nothing}</span>
      </div>`)}
      ${shown.length === 0 ? html`<p class="hint">No match.</p>` : nothing}
    </div>`;
  }

  renderReview() {
    const d = this.draft || {};
    const bind = (obj, key, multiline = false) => multiline
      ? html`<textarea rows="4" .value=${obj[key] || ''} @input=${(e) => { obj[key] = e.target.value; }}></textarea>`
      : html`<input type="text" .value=${String(obj[key] ?? '')} @input=${(e) => { obj[key] = e.target.value; }}>`;
    const panel = (title, body) => html`<section class="syncpanel"><h2>${title}</h2>${body}</section>`;
    return html`
      ${this.matched?.source ? html`<div class="applyresult">${iconYes} Matched existing source <b>${this.matched.source.gramps_id || ''}</b> — a new citation will be added to it.</div>` : nothing}
      <div class="reviewgrid">
        ${d.repository ? panel('New repository', html`
          <label class="fieldrow"><span>Name</span>${bind(d.repository, 'name')}</label>
          <label class="fieldrow"><span>Type</span>${bind(d.repository, 'type')}</label>
          <label class="fieldrow"><span>URL</span>${bind(d.repository, 'url')}</label>
          <label class="fieldrow"><span>Call number</span>${bind(d, 'call_number')}</label>`) : nothing}
        ${d.source ? panel('New source', html`
          <label class="fieldrow"><span>Title</span>${bind(d.source, 'title')}</label>
          <label class="fieldrow"><span>Author</span>${bind(d.source, 'author')}</label>
          <label class="fieldrow"><span>Pub info</span>${bind(d.source, 'pubinfo')}</label>
          <label class="fieldrow"><span>Abbrev</span>${bind(d.source, 'abbrev')}</label>`) : nothing}
        ${d.citation ? panel('Citation', html`
          <label class="fieldrow"><span>Page / locator</span>${bind(d.citation, 'page', true)}</label>
          <label class="fieldrow"><span>Confidence (0–4)</span>
            <select @change=${(e) => { d.citation.confidence = parseInt(e.target.value, 10); }}>
              ${[0, 1, 2, 3, 4].map((n) => html`<option value=${n}
                ?selected=${Number(d.citation.confidence) === n}>${n}</option>`)}
            </select></label>`) : nothing}
        ${d.notes ? panel('Notes', html`
          <label class="fieldrow"><span>First reference</span>${bind(d.notes, 'first_reference', true)}</label>
          <label class="fieldrow"><span>Short reference</span>${bind(d.notes, 'short_reference', true)}</label>
          <label class="fieldrow"><span>Abstract</span>${bind(d.notes, 'abstract', true)}</label>`) : nothing}
      </div>
      ${this.renderEventPicker()}
      <div class="toolbar">
        <button ?disabled=${this.busy} @click=${() => (this.citeStep = 'describe')}>← Back</button>
        <button class="primary" ?disabled=${this.busy} @click=${() => this.saveCitation()}>Save to Gramps</button>
      </div>`;
  }

  renderSaved() {
    const s = this.saved;
    return html`<section class="syncpanel">
      <h2>${iconYes} Saved to Gramps</h2>
      <table class="results">
        ${Object.entries(s).map(([k, v]) => html`<tr><td class="hint">${k}</td><td>${v}</td></tr>`)}
      </table>
      <div class="toolbar"><button class="primary" @click=${() => this.resetAll()}>Upload another</button></div>
    </section>`;
  }
}
customElements.define('upload-page', UploadPage);
