import { BifrostElement, html, nothing, api, post, btn, field, selectField, spinner, statusLine } from './core.js';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
  'September', 'October', 'November', 'December'];
const DAYS = Array.from({ length: 31 }, (_, i) => String(i + 1));
const DTYPES = ['Regular', 'Before', 'After', 'About', 'Range', 'Span'];
const DQUALS = ['Regular', 'Estimated', 'Calculated'];
const CONF = ['Very Low', 'Low', 'Normal', 'High', 'Very High'];
const REPO_TYPES = ['Archive', 'Library', 'Church', 'Collection', 'Association', 'Web site',
  'Bookstore', 'Cemetery', 'Safe'];
const ORIGIN_ICON = { paperless: 'description', immich: 'image' };
const SAVED_ICON = { repository: 'account_balance', source: 'menu_book', citation: 'format_quote', note: 'notes', event: 'event' };
const MODE_ICONS = { suggested: 'auto_awesome', search: 'search', changed: 'update', recent: 'history', bookmarks: 'bookmarks' };
const MODE_LABELS = { suggested: 'Suggested', search: 'Search', changed: 'Recently changed',
  recent: 'Recently synced', bookmarks: 'Bookmarks' };
const PICKER_TITLES = { media: 'Select a media object', source: 'Select a source', repo: 'Select a repository' };
const thumb = (handle) => (handle ? `/citations/api/thumbnail/${handle}` : null);

function fresh() {
  return {
    media: null, pl: null, drafting: false, drafted: false, suggested: [],
    source: null, newSource: null, repo: null, newRepo: null, titleTouched: false, repoTouched: false,
    page: '', dtype: 'Regular', dquality: 'Regular', year: '', month: '', day: '',
    confidence: 'Normal', n1: '', n2: '', n3: '', priv: false,
    picker: null, mode: 'changed', query: '', hi: -1, saving: false, saved: null, error: '',
  };
}

class CitationsPage extends BifrostElement {
  static properties = {
    s: { state: true },
    ctx: { state: true },
    loadError: { state: true },
    results: { state: true },
    searching: { state: true },
    changed: { state: true },
    recent: { state: true },
    marks: { state: true },
  };

  constructor() {
    super();
    this.s = fresh();
    this.ctx = null;
    this.loadError = '';
    this.results = [];
    this.searching = false;
    this.changed = null;
    this.recent = [];
    this.marks = null;
    this._seq = 0;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  set(patch) { this.s = { ...this.s, ...patch }; }

  async load() {
    this.loadError = '';
    try {
      this.ctx = await api('/citations/api/context');
    } catch (e) {
      this.loadError = e.message;
    }
    this.loadRecent();
  }

  async loadRecent() {
    try { this.recent = await api('/citations/api/recent'); }
    catch { this.recent = []; }
  }

  async loadChanged() {
    if (this.changed) return;
    try { this.changed = await api('/citations/api/media?mode=changed&limit=30'); }
    catch { this.changed = []; }
  }

  async loadMarks() {
    if (this.marks) return;
    try { this.marks = await api('/citations/api/bookmarks'); }
    catch { this.marks = { media: [], sources: [], repositories: [] }; }
  }

  async search() {
    const q = this.s.query.trim();
    const seq = ++this._seq;
    if (!q || this.s.picker !== 'media') { this.results = []; this.searching = false; return; }
    this.searching = true;
    let found = [];
    try { found = await api(`/citations/api/media?q=${encodeURIComponent(q)}`); }
    catch { found = []; }
    if (seq !== this._seq) return;
    this.results = found;
    this.searching = false;
  }

  // ---- picker

  modesFor(kind) {
    const modes = kind === 'source' && this.s.suggested.length ? ['suggested'] : [];
    modes.push('search', 'changed');
    if (kind === 'media') modes.push('recent');
    modes.push('bookmarks');
    return modes;
  }

  openPicker(kind) {
    const modes = this.modesFor(kind);
    this.set({ picker: kind, mode: modes[0] === 'suggested' ? 'suggested' : 'changed', query: '', hi: -1 });
    if (kind === 'media') this.loadChanged();
  }

  closePicker() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (dlg?.open) dlg.close();
    if (this.s.picker) this.set({ picker: null, query: '', hi: -1 });
    this.results = [];
  }

  updated() {
    const dlg = this.renderRoot.querySelector('dialog');
    if (!dlg) return;
    if (this.s.picker && !dlg.open && !dlg.__gwShown) {
      dlg.__gwShown = true;
      dlg.showModal();
      dlg.querySelector('input')?.focus();
      new MutationObserver(() => { if (!dlg.open) this.closePicker(); })
        .observe(dlg, { attributes: true, attributeFilter: ['open'] });
    }
  }

  scrimClick(e) {
    if (e.target !== e.currentTarget || e.detail === 0) return;
    const r = e.currentTarget.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right
      || e.clientY < r.top || e.clientY > r.bottom) this.closePicker();
  }

  setMode(mode) {
    this.set({ mode, hi: -1 });
    if (mode === 'bookmarks') this.loadMarks();
    if (mode === 'changed' && this.s.picker === 'media') this.loadChanged();
  }

  onQuery(e) {
    const query = e.target.value;
    this.set({ query, mode: query.trim() ? 'search' : this.s.mode, hi: -1 });
    if (this.s.picker === 'media') {
      this.searching = Boolean(query.trim());
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this.search(), 250);
    }
  }

  mediaRow(m) {
    return { icon: ORIGIN_ICON[m.origin] || 'attachment', thumb: thumb(m.handle), title: m.title,
      sub: m.gramps_id, mono: true, trailing: m.cited ? `cited ${m.cited}×` : '', payload: m };
  }

  filterQ(list, key) {
    const q = this.s.query.trim().toLowerCase();
    if (!q) return [];
    return list.filter((x) => (x[key] || '').toLowerCase().includes(q)
      || (x.gramps_id || '').toLowerCase().includes(q)).slice(0, 50);
  }

  byChange(list) {
    return [...list].sort((a, b) => (b.change || 0) - (a.change || 0)).slice(0, 50);
  }

  pickerItems() {
    const { picker, mode } = this.s;
    const marks = this.marks || { media: [], sources: [], repositories: [] };
    if (picker === 'media') {
      const list = mode === 'search' ? this.results
        : mode === 'changed' ? (this.changed || [])
          : mode === 'recent' ? this.recent.filter((r) => r.in_gramps) : marks.media;
      return list.map((m) => this.mediaRow(m));
    }
    if (picker === 'source') {
      const all = this.ctx.sources;
      if (mode === 'suggested') {
        return this.s.suggested.map((s) => ({ icon: 'menu_book', title: s.title,
          sub: `${s.gramps_id} · ${s.reason}`, trailing: s.confidence, payload: s }));
      }
      const list = mode === 'search' ? this.filterQ(all, 'title')
        : mode === 'changed' ? this.byChange(all) : marks.sources;
      return list.map((s) => ({ icon: 'menu_book', title: s.title, sub: s.gramps_id, mono: true, payload: s }));
    }
    const all = this.ctx.repositories;
    const list = mode === 'search' ? this.filterQ(all, 'name')
      : mode === 'changed' ? this.byChange(all) : marks.repositories;
    return list.map((r) => ({ icon: 'account_balance', title: r.name, sub: r.gramps_id, mono: true, payload: r }));
  }

  pickerEmpty() {
    const { mode, query, picker } = this.s;
    if (mode === 'search' && !query.trim()) return 'Type to search';
    if (mode === 'search' && picker === 'media' && this.searching) return 'Searching...';
    if (mode === 'changed' && picker === 'media' && !this.changed) return 'Loading...';
    if (mode === 'bookmarks' && !this.marks) return 'Loading...';
    return 'Not found';
  }

  async pick(item) {
    const p = item.payload;
    const kind = this.s.picker;
    this.closePicker();
    if (kind === 'media') {
      await this.chooseMedia(p, item.icon);
    } else if (kind === 'source') {
      this.set({ source: { handle: p.handle, gramps_id: p.gramps_id, title: p.title, suggestedWhy: p.reason || null },
        newSource: null, repo: null, newRepo: null, titleTouched: false, repoTouched: false });
    } else {
      this.set({ repo: { handle: p.handle, gramps_id: p.gramps_id, name: p.name }, newRepo: null, repoTouched: false });
    }
  }

  async chooseMedia(p, icon) {
    try {
      const m = await api(`/citations/api/media/${encodeURIComponent(p.gramps_id)}`);
      this.set({ error: '', pl: null, media: { handle: m.handle, gramps_id: m.gramps_id, title: m.title,
        paperless_id: m.paperless_id, icon, citations: (m.citations || []).length } });
      if (m.paperless_id) this.loadPaperless(m.gramps_id);
    } catch (e) {
      this.set({ error: e.message });
    }
  }

  async loadPaperless(grampsId) {
    let pl;
    try { pl = await api(`/citations/api/paperless/${encodeURIComponent(grampsId)}`); }
    catch (e) { pl = { error: e.message }; }
    if (this.s.media?.gramps_id === grampsId) this.set({ pl });
  }

  get draftable() {
    const pl = this.s.pl;
    return Boolean(this.s.media && pl && !pl.error && (pl.transcript || pl.source_url || pl.notes));
  }

  onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); this.closePicker(); return; }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Enter') return;
    const items = this.pickerItems();
    const n = items.length;
    e.preventDefault();
    if (e.key === 'Enter') {
      if (this.s.hi >= 0 && this.s.hi < n) this.pick(items[this.s.hi]);
    } else if (n) {
      this.set({ hi: (this.s.hi + (e.key === 'ArrowDown' ? 1 : -1) + n) % n });
    }
  }

  // ---- drafting and saving

  async draft() {
    const s = this.s;
    if (!this.draftable || s.drafting) return;
    this.set({ drafting: true, error: '' });
    try {
      const r = await post('/citations/api/compose-dump', { media_handle: s.media.handle,
        transcript: s.pl.transcript || '', urls: s.pl.source_url || '', dump: s.pl.notes || '' });
      const d = r.draft || {};
      const c = d.citation || {};
      const date = c.date || {};
      const notes = d.notes || {};
      const patch = {
        drafting: false, drafted: true, suggested: r.suggested || [],
        page: c.page || '',
        dtype: DTYPES.includes(date.modifier) ? date.modifier : 'Regular',
        dquality: DQUALS.includes(date.quality) ? date.quality : 'Regular',
        year: String(date.year || ''), month: MONTHS.includes(date.month) ? date.month : '',
        day: String(date.day || ''),
        confidence: CONF[c.confidence] || 'Normal',
        n1: notes.first_reference || '', n2: notes.short_reference || '', n3: notes.abstract || '',
      };
      if (patch.suggested.length) {
        const top = patch.suggested[0];
        Object.assign(patch, { source: { handle: top.handle, gramps_id: top.gramps_id, title: top.title,
          suggestedWhy: top.reason }, newSource: null, repo: null, newRepo: null });
      } else if (d.source) {
        const rr = r.matched_repository;
        Object.assign(patch, {
          source: null, titleTouched: false, repoTouched: false,
          newSource: { title: d.source.title || '', author: d.source.author || '',
            pubinfo: d.source.pubinfo || '', abbrev: d.source.abbrev || '', callno: d.call_number || '' },
          repo: rr ? { handle: rr.handle, gramps_id: rr.gramps_id, name: rr.name } : null,
          newRepo: !rr && d.repository ? { name: d.repository.name || '',
            type: REPO_TYPES.includes(d.repository.type) ? d.repository.type : 'Archive',
            url: d.repository.url || '' } : null,
        });
      }
      this.set(patch);
    } catch (e) {
      this.set({ drafting: false, error: e.message });
    }
  }

  get dateError() {
    const { year, month, day } = this.s;
    if (year.trim() && !/^\d{1,4}$/.test(year.trim())) return 'Year must be a number';
    const d = Number(day);
    const m = MONTHS.indexOf(month) + 1;
    if (d && m && d > new Date(Number(year) || 2000, m, 0).getDate()) return 'Day is past the end of the month';
    return '';
  }

  get hasSource() {
    const s = this.s;
    return Boolean(s.source || (s.newSource && s.newSource.title.trim()));
  }

  get newRepoActive() {
    const s = this.s;
    return Boolean(s.newSource && !s.source && s.newRepo);
  }

  get canAdd() {
    return this.hasSource && !this.dateError && !this.s.saving
      && !(this.newRepoActive && !this.s.newRepo.name.trim());
  }

  summary() {
    const s = this.s;
    if (!this.hasSource) return 'Select or create a source to add the citation.';
    const parts = ['1 citation'];
    if (s.newSource && !s.source) parts.push('1 source');
    if (this.newRepoActive && s.newRepo.name.trim()) parts.push('1 repository');
    const n = [s.n1, s.n2, s.n3].filter((x) => x.trim()).length;
    if (n) parts.push(`${n} note${n === 1 ? '' : 's'}`);
    return `Adds ${parts.join(', ')}${s.media ? `; cites ${s.media.gramps_id}` : ''}.`;
  }

  async add() {
    if (!this.canAdd) return;
    const s = this.s;
    const newSource = s.source ? null : s.newSource;
    const draft = {
      repository: newSource && s.newRepo
        ? { name: s.newRepo.name.trim(), type: s.newRepo.type || 'Archive', url: s.newRepo.url || '' } : null,
      call_number: newSource ? newSource.callno : '',
      source: newSource ? { title: newSource.title, author: newSource.author,
        pubinfo: newSource.pubinfo, abbrev: newSource.abbrev } : null,
      citation: { page: s.page, confidence: CONF.indexOf(s.confidence),
        date: { modifier: s.dtype, quality: s.dquality, year: s.year, month: s.month, day: s.day } },
      notes: { first_reference: s.n1, short_reference: s.n2, abstract: s.n3 },
      private: s.priv,
    };
    this.set({ saving: true, error: '' });
    try {
      const r = await post('/citations/api/save', {
        draft,
        media_handle: s.media?.handle || null,
        source_handle: s.source?.handle || null,
        repository_handle: newSource && s.repo ? s.repo.handle : null,
      });
      this.set({ saving: false, saved: r });
      this.changed = null;
      this.marks = null;
      this.loadRecent();
      if (newSource) {
        try { this.ctx = await api('/citations/api/context'); } catch { /* keep the stale catalog */ }
      }
    } catch (e) {
      this.set({ saving: false, error: e.message });
    }
  }

  reset() { this.s = fresh(); }

  // ---- render

  chosen(item, onRemove) {
    const fallback = (e) => e.target.replaceWith(Object.assign(document.createElement('i'), { textContent: item.icon }));
    return html`<div class="chosen-media">${item ? html`
      ${item.thumb ? html`<img class="circle" src=${item.thumb} alt="" @error=${fallback}>` : html`<i>${item.icon}</i>`}
      <div>
        <div>${item.label}</div>
        <div class="small-text secondary-text ${item.mono ? 'mono' : ''}">${item.sub}</div>
      </div>
      <button class="circle transparent small" aria-label="Remove" @click=${onRemove}><i>close</i></button>` : nothing}
    </div>`;
  }

  render() {
    if (this.loadError && !this.ctx) {
      return html`
        <p>${statusLine('error', this.loadError)}</p>
        <nav>${btn('Retry', false, () => this.load())}</nav>`;
    }
    if (!this.ctx) return html`<progress class="circle"></progress>`;
    return html`${this.s.saved ? this.renderSaved() : this.renderForm()}${this.renderPicker()}`;
  }

  renderForm() {
    const s = this.s;
    const ai = this.ctx.llm && this.ctx.house_style !== false;
    const bind = (key) => (e) => this.set({ [key]: e.target.value });
    const dateError = this.dateError;
    return html`
      <h6 class="small">Generate a new citation from an existing Gramps media object</h6>
      ${this.chosen(s.media && { thumb: thumb(s.media.handle), icon: s.media.icon, label: s.media.title, mono: true,
    sub: s.media.paperless_id ? `${s.media.gramps_id} · Paperless #${s.media.paperless_id}` : s.media.gramps_id },
  () => this.set({ media: null, pl: null }))}
      <nav class="wrap">
        ${btn(html`<i>add_link</i><span>Select</span>`, false, () => this.openPicker('media'), 'border')}
      </nav>
      ${s.error ? html`<p>${statusLine('error', s.error)}</p>` : nothing}
      ${ai ? this.renderAiRow() : nothing}
      <div class="medium-space"></div>
      <h6 class="small">Source</h6>
      ${this.chosen(s.source && { icon: 'menu_book', label: s.source.title, mono: !s.source.suggestedWhy,
    sub: s.source.suggestedWhy ? `${s.source.gramps_id} · suggested: ${s.source.suggestedWhy}` : s.source.gramps_id },
  () => this.set({ source: null }))}
      ${s.newSource ? this.renderNewSource() : nothing}
      <nav class="wrap">
        ${btn(html`<i>add</i><span>Create a new source</span>`, Boolean(s.newSource),
    () => this.set({ newSource: { title: '', author: '', pubinfo: '', abbrev: '', callno: '' },
      source: null, newRepo: null, titleTouched: false, repoTouched: false }), 'border')}
        ${btn(html`<i>add_link</i><span>Select</span>`, false, () => this.openPicker('source'), 'border')}
      </nav>
      <div class="medium-space"></div>
      <h6 class="small">Citation</h6>
      ${field('Page', s.page, bind('page'), { width: 'large' })}
      <nav class="wrap">
        ${selectField('Date type', s.dtype, DTYPES, bind('dtype'), { width: 'small' })}
        ${selectField('Date quality', s.dquality, DQUALS, bind('dquality'), { width: 'small' })}
      </nav>
      <nav class="wrap">
        ${field('Year', s.year, bind('year'), { width: 'small', mono: true })}
        ${selectField('Month', s.month, [['', '']].concat(MONTHS), bind('month'), { width: 'small' })}
        ${selectField('Day', s.day, [['', '']].concat(DAYS), bind('day'), { width: 'small' })}
      </nav>
      ${dateError ? html`<p>${statusLine('error', dateError)}</p>` : nothing}
      ${selectField('Confidence', s.confidence, CONF, bind('confidence'), { width: 'small' })}
      <div class="medium-space"></div>
      <h6 class="small">Notes</h6>
      ${field('First reference', s.n1, bind('n1'), { rows: 3, width: 'large' })}
      ${field('Short reference', s.n2, bind('n2'), { width: 'large' })}
      ${field('Abstract', s.n3, bind('n3'), { rows: 3, width: 'large' })}
      <label class="cite-switch">
        <label class="switch"><input type="checkbox" .checked=${s.priv}
          @change=${(e) => this.set({ priv: e.target.checked })}><span></span></label>
        <span>Private</span>
      </label>
      <div class="medium-space"></div>
      <nav class="wrap">
        ${btn(s.saving ? 'Adding...' : 'Add', !this.canAdd, () => this.add())}
        ${btn('Reset', s.saving, () => this.reset(), 'border')}
        ${s.saving ? spinner : nothing}
        <span class="small-text secondary-text">${this.summary()}</span>
      </nav>`;
  }

  renderAiRow() {
    const s = this.s;
    const hint = !s.media ? 'Select a media object first.'
      : !s.media.paperless_id ? 'Only media synced from a Paperless document can be drafted from.'
        : !s.pl ? 'Checking the Paperless document...'
          : s.pl.error ? `Paperless document unavailable: ${s.pl.error}`
            : !this.draftable ? 'The Paperless document has no transcript, source URL or notes to draft from.'
              : s.drafted ? 'Fields below were filled by AI. Change anything before adding.'
                : 'Requires a Paperless transcript';
    return html`<nav class="wrap">
      ${btn(html`<i>auto_awesome</i><span>${s.drafting ? 'Drafting...' : s.drafted ? 'Draft again' : 'Draft with AI'}</span>`,
    s.drafting || !this.draftable, () => this.draft(), 'border')}
      ${s.drafting ? spinner : nothing}
      <span class="small-text secondary-text">${hint}</span>
    </nav>`;
  }

  renderNewSource() {
    const s = this.s;
    const ns = s.newSource;
    const bind = (key) => (e) => this.set({ newSource: { ...this.s.newSource, [key]: e.target.value },
      ...(key === 'title' ? { titleTouched: true } : {}) });
    const titleError = s.titleTouched && !ns.title.trim() ? 'This field is mandatory' : '';
    return html`<article class="border cite-card">
      <nav>
        <h6 class="small max">New source</h6>
        ${btn('Cancel', false, () => this.set({ newSource: null, repo: null, newRepo: null,
    titleTouched: false, repoTouched: false }), 'border small')}
      </nav>
      ${field('Title', ns.title, bind('title'), { width: 'large', error: titleError })}
      ${field('Author', ns.author, bind('author'), { width: 'large' })}
      ${field('Publication info', ns.pubinfo, bind('pubinfo'), { width: 'large' })}
      ${field('Abbreviation', ns.abbrev, bind('abbrev'), { width: 'medium' })}
      <h6 class="small">Repository</h6>
      ${this.chosen(s.repo && { icon: 'account_balance', label: s.repo.name, mono: true, sub: s.repo.gramps_id },
    () => this.set({ repo: null }))}
      ${s.newRepo ? this.renderNewRepo() : nothing}
      <nav class="wrap">
        ${btn(html`<i>add</i><span>Create a new repository</span>`, Boolean(s.newRepo),
    () => this.set({ newRepo: { name: '', type: 'Archive', url: '' }, repo: null, repoTouched: false }), 'border')}
        ${btn(html`<i>add_link</i><span>Select</span>`, false, () => this.openPicker('repo'), 'border')}
      </nav>
      ${field('Call number', ns.callno, bind('callno'), { width: 'medium' })}
    </article>`;
  }

  renderNewRepo() {
    const s = this.s;
    const nr = s.newRepo;
    const bind = (key) => (e) => this.set({ newRepo: { ...this.s.newRepo, [key]: e.target.value },
      ...(key === 'name' ? { repoTouched: true } : {}) });
    const nameError = s.repoTouched && !nr.name.trim() ? 'This field is mandatory' : '';
    return html`<article class="border cite-card">
      <nav>
        <h6 class="small max">New repository</h6>
        ${btn('Cancel', false, () => this.set({ newRepo: null, repoTouched: false }), 'border small')}
      </nav>
      ${field('Name', nr.name, bind('name'), { width: 'large', error: nameError })}
      ${selectField('Type', nr.type, REPO_TYPES, bind('type'), { width: 'small' })}
      ${field('URL', nr.url, bind('url'), { width: 'large' })}
    </article>`;
  }

  renderSaved() {
    const created = this.s.saved?.created || [];
    const url = this.ctx.gramps_url;
    const row = (c, title, sub) => html`<li>
      <i>${SAVED_ICON[c.type] || 'notes'}</i>
      <div class="max"><div>${title}</div><div class="small-text secondary-text">${sub}</div></div>
      ${url ? html`<a class="link" href="${url}/${c.type}/${c.gramps_id}" target="_blank" rel="noopener">Open in Gramps</a>` : nothing}
    </li>`;
    return html`
      <p>${statusLine('ok', 'Saved to Gramps. The media object is now cited.')}</p>
      <ul class="list cite-list">
        ${created.map((c) => row(c,
    c.title || (c.type === 'citation' ? '(no page)' : c.gramps_id),
    c.type === 'citation' ? `${c.gramps_id} · ${c.source_title || ''}`
      : c.type === 'note' ? `${c.gramps_id} · ${c.title === 'Abstract' ? 'abstract note' : 'reference note'}`
        : `${c.gramps_id} · new ${c.type}`))}
      </ul>
      <nav>${btn('New citation', false, () => this.reset())}</nav>`;
  }

  renderPicker() {
    const s = this.s;
    if (!s.picker) return nothing;
    const items = this.pickerItems();
    const fallback = (icon) => (e) => e.target.replaceWith(Object.assign(document.createElement('i'), { textContent: icon }));
    return html`<dialog class="large cite-picker" @close=${() => this.closePicker()}
        @click=${(e) => this.scrimClick(e)} @keydown=${(e) => this.onKey(e)}>
      <nav>
        <h5 class="max small">${PICKER_TITLES[s.picker]}</h5>
        <button class="circle transparent" aria-label="Close" @click=${() => this.closePicker()}><i>close</i></button>
      </nav>
      <div class="field prefix fill no-margin">
        <i>search</i>
        <input type="text" placeholder="Search" .value=${s.query} autocomplete="off" @input=${(e) => this.onQuery(e)}>
      </div>
      <div class="space"></div>
      <nav class="wrap">
        ${this.modesFor(s.picker).map((m) => html`<button class="chip ${m === s.mode ? 'fill' : ''}"
          @click=${() => this.setMode(m)}><i>${MODE_ICONS[m]}</i><span>${MODE_LABELS[m]}</span></button>`)}
      </nav>
      ${s.mode === 'suggested' ? html`<p class="small-text secondary-text">Matched from the Paperless transcript and this media’s existing citations.</p>` : nothing}
      <ul class="list cite-list cite-pick">
        ${items.length ? items.map((it, i) => html`<li class=${i === s.hi ? 'active' : ''} @click=${() => this.pick(it)}>
            ${it.thumb ? html`<img class="circle" src=${it.thumb} alt="" @error=${fallback(it.icon)}>` : html`<i>${it.icon}</i>`}
            <div class="max"><div>${it.title}</div>
              <div class="small-text secondary-text ${it.mono ? 'mono' : ''}">${it.sub}</div></div>
            ${it.trailing ? html`<span class="small-text secondary-text">${it.trailing}</span>` : nothing}
          </li>`) : html`<li class="secondary-text">${this.pickerEmpty()}</li>`}
      </ul>
    </dialog>`;
  }
}

customElements.define('citations-page', CitationsPage);
