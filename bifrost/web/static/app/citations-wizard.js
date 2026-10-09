import { BifrostElement, html, nothing, api, post, statusLine } from './core.js';
import {
  RECORDS, recordById, newDraft, draftFromExample, buildOutputs, exampleLabel, setVariant, nextCitationDraft,
  runChecks, plain, hasGap, yearOf, loadState, saveState, recordGroups, sourceRows, referenceRows, citationRows,
  noteRows, outputRows, exampleNote, copyAllText, repositoryName, paperlessMatch, restoreDraft, REFERENCE_VALUES,
  LEVELS, CHAPTERS, CHAPTER_CODE, GUIDE,
} from '/static/citations/citations.js';

const API = '/citations/api';
const STEPS = ['Document', 'Record type', 'Source', 'Citation', 'Note', 'Create'];
const [DOC, TYPE, SOURCE, CITATION, NOTE, CREATE] = STEPS.keys();
const WIZARD_KEY = 'bifrost-citations';
const SOURCE_KEYS = ['title', 'author', 'abbrev', 'pubinfo', 'callNumber'];
const FIELD_NAMES = { title: 'Title', author: 'Author', abbrev: 'Abbrev', pubinfo: 'Pubinfo', callNumber: 'Call number',
  page: 'Page', frn: 'FRN', srn: 'SRN', plTitle: 'Paperless title' };
const SELECTS = { plDoctype: 'document_type', plDateMeaning: 'date_meaning', plCorrespondent: 'correspondent' };
const store = (() => { try { return globalThis.localStorage; } catch { return null; } })();
const squash = (s) => String(s ?? '').replace(/\s+/g, ' ').trim().toLowerCase();
const same = (a, b) => squash(a) === squash(b);
const today = () => new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
const blank = html`<span class="cw-blank">(blank)</span>`;
const COLS = html`<colgroup><col class="cw-c-label"><col><col class="cw-c-rule"><col class="cw-c-acts"></colgroup>`;

function display(text, needle = '') {
  return String(text ?? '').split(/(⟦[^⟧]*⟧|⟪[^⟫]*⟫)/).map((part) => {
    if (part.startsWith('⟦')) return html`<span class="cw-gap">${part.slice(1, -1)}</span>`;
    if (part.startsWith('⟪')) return html`<span class="cw-slot">${part.slice(1, -1)}</span>`;
    if (!needle || !part.includes(needle)) return part;
    return part.split(needle).flatMap((piece, i) => (i ? [html`<mark class="cw-hit">${needle}</mark>`, piece] : [piece]));
  });
}

function errText(e) {
  const m = String(e?.message ?? e).match(/^\d+: ([\s\S]*)$/);
  if (!m) return String(e?.message ?? e);
  try { return JSON.parse(m[1]).detail || m[1]; } catch { return m[1]; }
}

function readWizard() {
  try { return JSON.parse(store?.getItem(WIZARD_KEY) ?? 'null') || {}; } catch { return {}; }
}

function writeWizard(value) {
  try { store?.setItem(WIZARD_KEY, JSON.stringify(value)); return true; } catch { return false; }
}

function grampsRows(s) {
  const refs = s.repositories || [];
  return [['Title', s.title], ['Author', s.author], ['Abbrev', s.abbrev], ['Pubinfo', s.pubinfo],
    ['Repository', refs.map((r) => r.name).filter(Boolean).join('; ')],
    ['Call number', refs.map((r) => r.call_number).filter(Boolean).join('; ')]];
}

class CitationsWizard extends BifrostElement {
  static properties = {
    ctx: { state: true }, loadError: { state: true }, step: { state: true }, doc: { state: true },
    docQ: { state: true }, docHits: { state: true }, srcQ: { state: true }, busy: { state: true },
    msg: { state: true }, result: { state: true }, editing: { state: true }, pop: { state: true },
    clearArmed: { state: true }, focus: { state: true },
  };

  constructor() {
    super();
    this.gen = loadState(store, recordById) || { current: RECORDS[0].id, drafts: {}, filter: '' };
    const w = readWizard();
    this.step = Number.isInteger(w.step) ? Math.min(Math.max(w.step, DOC), CREATE) : DOC;
    this.docId = w.docId || null;
    this.gsrc = ['new', 'existing'].includes(w.gsrc?.mode) ? w.gsrc : { mode: 'auto' };
    this.repo = ['none', 'existing'].includes(w.repo?.mode) ? w.repo : { mode: 'auto' };
    this.scanPick = w.scanPick || {};
    this.fileScan = w.fileScan === true;
    this.result = w.result || null;
    this.basis = w.basis || null;
    this.ctx = null;
    this.loadError = '';
    this.doc = null;
    this.docQ = '';
    this.docHits = [];
    this.srcQ = '';
    this.busy = false;
    this.msg = null;
    this.editing = '';
    this.pop = null;
    this.clearArmed = false;
    this.focus = '';
    this._seq = 0;
    this._pressing = false;
    this._queue = [];
  }

  connectedCallback() {
    super.connectedCallback();
    this._down = () => { clearTimeout(this._pressEnd); this._pressing = true; };
    this._up = (e) => { clearTimeout(this._pressEnd); this._pressEnd = setTimeout(() => this.endPress(), e.pointerType === 'mouse' ? 0 : 1000); };
    this._end = () => this.endPress();
    this._scroll = () => { if (this.pop) this.pop = null; };
    document.addEventListener('pointerdown', this._down, true);
    document.addEventListener('pointerup', this._up, true);
    document.addEventListener('pointercancel', this._end, true);
    document.addEventListener('click', this._end, true);
    window.addEventListener('scroll', this._scroll, true);
    this.load();
    this.searchDocs();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener('pointerdown', this._down, true);
    document.removeEventListener('pointerup', this._up, true);
    document.removeEventListener('pointercancel', this._end, true);
    document.removeEventListener('click', this._end, true);
    window.removeEventListener('scroll', this._scroll, true);
  }

  endPress() {
    clearTimeout(this._pressEnd);
    if (!this._pressing) return;
    this._pressing = false;
    setTimeout(() => {
      if (this._pressing) return;
      const queued = this._queue;
      this._queue = [];
      queued.forEach((fn) => fn());
    }, 0);
  }

  later(fn) {
    if (this._pressing) this._queue.push(fn);
    else fn();
  }

  async load() {
    try {
      this.ctx = await api(`${API}/context`);
    } catch (e) {
      this.loadError = errText(e);
    }
    if (!this.docId) { this.step = DOC; return; }
    try {
      this.doc = await api(`${API}/doc/${this.docId}`);
    } catch {
      this.docId = null;
      this.step = DOC;
      this.save();
    }
  }

  get type() { return recordById(this.gen.current); }

  get draft() { return (this.gen.drafts[this.gen.current] ||= newDraft(this.type)); }

  save() {
    saveState(store, this.gen);
    writeWizard({ step: this.step, docId: this.doc?.id ?? this.docId, gsrc: this.gsrc, repo: this.repo,
      scanPick: this.scanPick, fileScan: this.fileScan, result: this.result, basis: this.basis });
  }

  changed() {
    this.save();
    this.requestUpdate();
  }

  edited() {
    this.result = null;
    this.changed();
  }

  go(step) {
    if (step < DOC || step > CREATE || (step > DOC && !this.doc)) return;
    this.step = step;
    this.editing = '';
    this.focus = '';
    this.pop = null;
    this.save();
    window.scrollTo({ top: 0 });
  }

  say(kind, text) {
    this.msg = [kind, text];
    clearTimeout(this._msgTimer);
    if (kind === 'ok') this._msgTimer = setTimeout(() => { this.msg = null; }, 2000);
  }

  queueDocs(q) {
    this.docQ = q;
    clearTimeout(this._docTimer);
    this._docTimer = setTimeout(() => this.searchDocs(), 250);
  }

  async searchDocs() {
    const seq = ++this._seq;
    let hits = [];
    try {
      hits = await api(`${API}/documents?q=${encodeURIComponent(this.docQ.trim())}`);
    } catch {
      hits = [];
    }
    if (seq === this._seq) this.docHits = hits;
  }

  async pickDoc(id) {
    this.say('busy', 'Opening the document');
    try {
      this.doc = await api(`${API}/doc/${id}`);
    } catch (e) {
      this.say('error', errText(e));
      return;
    }
    this.msg = null;
    this.docId = id;
    this.scanPick = {};
    this.fileScan = false;
    this.result = null;
    this.basis = null;
    if (this.doc.citations.length) this.startFrom(this.doc.citations[0]);
    else {
      this.applyDoc();
      this.changed();
    }
  }

  startFrom(c) {
    this.basis = c.handle;
    const kept = c.draft && recordById(c.draft.type);
    const source = (this.ctx?.sources || []).find((s) => s.handle === c.source_handle);
    if (kept) {
      this.gen.current = kept.id;
      this.gen.drafts[kept.id] = restoreDraft(kept, c.draft.draft);
      if (source) this.gsrc = { mode: 'existing', handle: source.handle };
    } else {
      const known = recordById(source?.remembered?.type || '');
      if (known) this.gen.current = known.id;
      this.gen.drafts[this.gen.current] = newDraft(this.type);
      this.applyDoc();
      if (source) this.pickSource(source);
      if (Number.isInteger(c.confidence) && LEVELS[4 - c.confidence]) this.draft.confidence = LEVELS[4 - c.confidence];
    }
    this.repo = { mode: 'auto' };
    this.editing = '';
    this.edited();
  }

  applyDoc() {
    if (!this.doc) return;
    const v = this.draft.values;
    v.url = this.doc.source_url || '';
    v.eventYear = yearOf(this.doc.created) || v.eventYear;
  }

  selectType(id) {
    if (!recordById(id) || id === this.gen.current) return;
    this.gen.current = id;
    this.editing = '';
    this.gsrc = { mode: 'auto' };
    this.repo = { mode: 'auto' };
    this.applyDoc();
    this.edited();
  }

  loadExample(index) {
    const claim = this.type.examples[index];
    if (!claim) return;
    this.gen.drafts[this.gen.current] = draftFromExample(this.type, claim);
    this.edited();
  }

  clear() {
    if (!this.clearArmed) {
      this.clearArmed = true;
      clearTimeout(this._clearTimer);
      this._clearTimer = setTimeout(() => { this.clearArmed = false; }, 3000);
      return;
    }
    this.clearArmed = false;
    this.gen.drafts[this.gen.current] = newDraft(this.type);
    this.gsrc = { mode: 'auto' };
    this.repo = { mode: 'auto' };
    this.applyDoc();
    this.edited();
  }

  setPath(path, value) {
    const d = this.draft;
    if (path === 'variant') setVariant(this.type, d, value);
    else {
      const [head, key] = path.split('.');
      if (key === undefined) d[head] = value;
      else d[head][key] = value;
    }
    d.example = '';
    this.edited();
  }

  override(key, value) {
    this.draft.overrides[key] = value;
    this.save();
  }

  commit(key) {
    const o = this.draft.overrides;
    if (this.editing === key) this.editing = '';
    if (!Object.hasOwn(o, key)) return;
    const value = o[key].trim();
    if (value) o[key] = value;
    else delete o[key];
    this.edited();
  }

  reset(key) {
    delete this.draft.overrides[key];
    this.editing = '';
    this.edited();
  }

  async copy(text) {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch { }
    if (!ok) {
      const ta = Object.assign(document.createElement('textarea'), { value: text, readOnly: true });
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      const back = document.activeElement;
      document.body.append(ta);
      ta.select();
      try { ok = document.execCommand('copy'); } catch { }
      ta.remove();
      back?.focus?.();
    }
    if (ok) this.say('ok', 'Copied');
    else this.say('error', 'Copying is blocked here');
  }

  matches(outputs) {
    const title = plain(outputs.title);
    return (this.ctx?.sources || []).filter((s) => same(s.title, title));
  }

  sourceMode(outputs) {
    if (this.gsrc.mode === 'auto') return this.matches(outputs).length ? 'existing' : 'new';
    return this.gsrc.mode;
  }

  chosenSource(outputs) {
    const sources = this.ctx?.sources || [];
    if (this.gsrc.mode === 'existing') return sources.find((s) => s.handle === this.gsrc.handle) || null;
    if (this.gsrc.mode === 'new') return null;
    return this.matches(outputs)[0] || null;
  }

  setSourceMode(mode) {
    const outputs = buildOutputs(this.type, this.draft);
    if (mode === this.sourceMode(outputs)) return;
    this.gsrc = mode === 'new' ? { mode: 'new' } : { mode: 'existing', handle: this.matches(outputs)[0]?.handle || null };
    this.edited();
  }

  pickSource(s) {
    this.gsrc = { mode: 'existing', handle: s.handle };
    const keys = new Set([...this.type.source.map(([key]) => key), ...REFERENCE_VALUES]);
    const call = (s.repositories || []).map((r) => r.call_number).find(Boolean);
    const inputs = { ...(call ? { call } : {}), ...(s.remembered?.inputs || {}) };
    for (const [key, value] of Object.entries(inputs)) {
      if (keys.has(key) && typeof value === 'string') this.draft.values[key] = value;
    }
    this.draft.example = '';
    this.edited();
  }

  repository() {
    const r = this.repo, repos = this.ctx?.repositories || [];
    if (r.mode === 'none') return null;
    if (r.mode === 'existing') return repos.find((x) => x.handle === r.handle) ? { handle: r.handle } : null;
    const name = repositoryName(this.type, this.draft);
    const hit = name && repos.find((x) => same(x.name, name));
    return hit ? { handle: hit.handle } : null;
  }

  scanValues(outputs) {
    const ctx = this.ctx, doc = this.doc, pick = this.scanPick;
    const choose = (key, built, rows, current) =>
      (Object.hasOwn(pick, key) ? pick[key] : paperlessMatch(plain(built), rows) ?? current ?? null);
    const meaning = ctx?.date_meaning;
    return {
      title: plain(outputs.plTitle).trim(),
      document_type: choose('document_type', outputs.plDoctype, ctx?.document_types || [], doc?.document_type),
      correspondent: choose('correspondent', outputs.plCorrespondent, ctx?.correspondents || [], doc?.correspondent),
      date_meaning: meaning
        ? choose('date_meaning', outputs.plDateMeaning, meaning.options.map((o) => ({ id: o.id, name: o.label })), doc?.date_meaning)
        : null,
      source_url: plain(outputs.plSourceUrl).trim(),
    };
  }

  blockers(outputs, source, repo) {
    const out = [];
    const isNew = this.sourceMode(outputs) === 'new';
    if (!this.doc?.media) out.push(`Gramps has no media ${this.doc?.pid || ''}`.trim());
    if (!isNew && !source) out.push('Choose a Gramps source');
    const keys = [...(isNew ? SOURCE_KEYS : []), 'page', 'frn', 'srn', ...(this.fileScan ? ['plTitle'] : [])];
    const gaps = keys.filter((k) => hasGap(outputs[k])).map((k) => FIELD_NAMES[k]);
    if (gaps.length) out.push(`Unfilled parts in: ${gaps.join(', ')}`);
    if (!outputs.confidence) out.push('Choose a confidence level');
    if (isNew && !plain(outputs.title).trim()) out.push('The new Source needs a title');
    if (isNew && plain(outputs.callNumber).trim() && !repo) out.push('A call number needs a Repository');
    return out;
  }

  async create() {
    const type = this.type, draft = this.draft, o = buildOutputs(type, draft);
    const isNew = this.sourceMode(o) === 'new';
    const source = isNew ? null : this.chosenSource(o);
    const repo = isNew ? this.repository() : null;
    if (this.busy || this.blockers(o, source, repo).length) return;
    const keys = [...type.source.map(([key]) => key), ...REFERENCE_VALUES];
    const body = {
      doc_id: this.doc.id,
      source: source ? { handle: source.handle } : {
        title: plain(o.title), author: plain(o.author), abbrev: plain(o.abbrev), pubinfo: plain(o.pubinfo),
        call_number: plain(o.callNumber), repository: repo,
      },
      citation: { page: plain(o.page), confidence: o.confidence, frn: plain(o.frn), srn: plain(o.srn) },
      scan: this.fileScan ? this.scanValues(o) : null,
      inputs: { type: type.id, values: Object.fromEntries(keys.map((key) => [key, String(draft.values[key] ?? '').trim()])) },
      draft: { type: type.id, draft: { values: draft.values, subject: draft.subject, confidence: draft.confidence, variant: draft.variant } },
    };
    this.busy = true;
    this.say('busy', 'Creating');
    try {
      this.result = await post(`${API}/create`, body);
    } catch (e) {
      this.busy = false;
      this.say('error', errText(e));
      return;
    }
    this.busy = false;
    this.gsrc = { mode: 'existing', handle: this.result.source.handle };
    this.repo = { mode: 'auto' };
    if (this.result.scan_error) this.say('error', `Paperless: ${this.result.scan_error}`);
    else this.msg = null;
    this.save();
    const [ctx, doc] = await Promise.all([api(`${API}/context`).catch(() => this.ctx),
      api(`${API}/doc/${this.doc.id}`).catch(() => this.doc)]);
    this.ctx = ctx;
    this.doc = doc;
  }

  nextOnSource() {
    this.gen.drafts[this.gen.current] = nextCitationDraft(this.type, this.draft);
    this.result = null;
    this.doc = null;
    this.docId = null;
    this.scanPick = {};
    this.fileScan = false;
    this.go(DOC);
    this.searchDocs();
  }

  againOnDocument() {
    this.draft.overrides = {};
    this.draft.example = '';
    this.basis = this.result?.citation?.handle || this.basis;
    this.result = null;
    this.fileScan = false;
    this.go(CITATION);
  }

  updated(changed) {
    if (changed.has('editing') && this.editing) {
      const box = this.querySelector('textarea.cw-edit');
      if (box) {
        box.focus();
        box.setSelectionRange(box.value.length, box.value.length);
      }
    }
  }

  focusIn(e) {
    const path = e.target?.dataset?.path || '';
    if (path !== this.focus) this.focus = path;
  }

  focusOut(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) this.focus = '';
  }

  marks(outputs, rows) {
    const row = this.focus && rows.find((r) => r.path === this.focus);
    if (!row) return null;
    const [head, key] = row.path.split('.');
    const value = String(row.value ?? '').trim();
    const marked = structuredClone(this.draft);
    marked[head][key] = `⟪${value || row.label}⟫`;
    const shown = buildOutputs(this.type, marked);
    const out = {};
    for (const [k, text] of Object.entries(shown)) {
      if (text !== outputs[k]) out[k] = value ? { text: outputs[k], needle: value } : { text, needle: '' };
    }
    return out;
  }

  showPop(e, ref, field) {
    const box = e.currentTarget.getBoundingClientRect();
    const pins = this.type.pins || {};
    const rows = field ? pins[field] || [] : Object.values(pins).flat().filter(([section]) => section === ref);
    this.pop = { ref, rows, right: box.right, top: box.top, bottom: box.bottom };
  }

  ref(ref, field = '') {
    if (!GUIDE.refs[ref]) return html`<span class="cw-ref plain">${ref}</span>`;
    return html`<span class="cw-ref" tabindex="0" @mouseenter=${(e) => this.showPop(e, ref, field)}
      @focus=${(e) => this.showPop(e, ref, field)} @mouseleave=${() => { this.pop = null; }}
      @blur=${() => { this.pop = null; }}>${ref}</span>`;
  }

  renderPop() {
    const p = this.pop;
    if (!p) return nothing;
    const info = GUIDE.refs[p.ref];
    const name = (info?.title || '').replace(`${p.ref} · `, '') || p.ref;
    const width = Math.min(360, window.innerWidth - 24);
    const left = Math.max(12, Math.min(p.right - width, window.innerWidth - width - 12));
    const below = p.bottom + 260 < window.innerHeight;
    const style = below ? `left:${left}px;top:${p.bottom + 8}px;width:${width}px`
      : `left:${left}px;bottom:${window.innerHeight - p.top + 8}px;width:${width}px`;
    return html`<div class="cw-pop" role="tooltip" style=${style}>
      <div class="cw-pop-head"><span class="cw-pop-title">${name}</span><span class="cw-pop-ref">${p.ref}</span></div>
      ${info?.text ? html`<p>${info.text}</p>` : nothing}
      ${p.rows.map(([section, text]) => {
    const [label, ...rest] = text.split(' | ');
    return html`<div class="cw-pin">
          ${section === p.ref ? nothing : html`<div class="cw-pin-ref">${section}</div>`}
          ${rest.length ? html`<div class="cw-pin-label">${label}</div><div>${rest.join(' · ')}</div>` : html`<div>${text}</div>`}
        </div>`;
  })}
    </div>`;
  }

  input(row) {
    const id = `cw-${row.path.replace(/\./g, '-')}`;
    const set = (e) => this.setPath(row.path, row.kind === 'check' ? e.target.checked : e.target.value);
    const label = html`${row.num ? html`<span class="cw-num">${row.num}</span>` : nothing}${row.label}`;
    if (row.kind === 'check') {
      return html`<label class="checkbox cw-check"><input type="checkbox" .checked=${row.value} @change=${set}><span>${row.label}</span></label>`;
    }
    if (row.kind === 'select') {
      return html`<div class="field label suffix border small cw-field">
        <select id=${id} @change=${set}>${row.options.map(([v, l]) => html`<option value=${v} ?selected=${v === row.value}>${l}</option>`)}</select>
        <label for=${id}>${label}</label><i>arrow_drop_down</i></div>`;
    }
    if (row.kind === 'area') {
      return html`<div class="field label border textarea cw-field">
        <textarea id=${id} data-path=${row.path} rows="3" .value=${row.value} placeholder=${row.placeholder || ' '} @input=${set}></textarea>
        <label for=${id}>${label}</label></div>`;
    }
    const list = row.list?.length ? `${id}-list` : '';
    const isAccessed = row.path === 'values.accessed';
    return html`<div class="cw-line">
      <div class="field label border small cw-field">
        <input id=${id} data-path=${row.path} class=${row.mono ? 'mono' : ''} .value=${row.value} placeholder=${row.placeholder || ' '}
          list=${list || nothing} autocomplete="off" spellcheck="false" @input=${set}>
        <label for=${id}>${label}</label>
      </div>
      ${isAccessed ? html`<button class="border small cw-today" @click=${() => this.setPath(row.path, today())}>Today</button>` : nothing}
      ${list ? html`<datalist id=${list}>${row.list.map((o) => html`<option value=${o}></option>`)}</datalist>` : nothing}
    </div>`;
  }

  formColumn(body) {
    return html`<div class="cw-form" @focusin=${(e) => this.focusIn(e)} @focusout=${(e) => this.focusOut(e)}>${body}</div>`;
  }

  outRow(r, mark) {
    const editing = this.editing === r.key;
    const open = r.editable && !editing;
    const start = () => { if (open) this.editing = r.key; };
    const cell = editing
      ? html`<textarea class="cw-edit" rows=${r.key === 'frn' ? 6 : 2} .value=${r.text} aria-label="Edit ${r.label}"
          @input=${(e) => this.override(r.key, e.target.value)}
          @blur=${() => this.later(() => this.commit(r.key))}
          @keydown=${(e) => { if (e.key === 'Escape') e.target.blur(); }}></textarea>`
      : mark ? display(mark.text, mark.needle) : r.text ? display(r.value) : blank;
    return html`<tr class=${mark ? 'cw-hot' : ''}>
      <th>${r.label}</th>
      <td class="cw-val ${r.edited ? 'edited' : ''} ${open ? 'editable' : ''}" tabindex=${open ? 0 : nothing}
        @click=${start} @keydown=${(e) => { if (open && e.key === 'Enter') { e.preventDefault(); start(); } }}>${cell}</td>
      <td class="cw-rule">${this.ref(r.ref, r.key)}</td>
      <td class="cw-acts">
        ${r.text ? html`<button class="transparent circle small" title="Copy ${r.label}" aria-label="Copy ${r.label}"
          @click=${() => this.copy(r.text)}><i>content_copy</i></button>` : nothing}
        ${r.edited ? html`<button class="transparent circle small" title="Reset ${r.label}" aria-label="Reset ${r.label}"
          @click=${() => this.reset(r.key)}><i>undo</i></button>` : nothing}
      </td>
    </tr>`;
  }

  outTable(groups, extra = {}, marks = null) {
    return html`<table class="cw-out">${COLS}${groups.map((g) => {
      const x = extra[g.name] || {};
      return html`<tbody class=${x.off ? 'cw-off' : ''}>
        <tr class="cw-group"><td colspan="4">${g.name}${x.head ?? nothing}</td></tr>
        ${x.body ?? g.rows.map((r) => x.row?.(r) ?? this.outRow(r, marks?.[r.key]))}
        ${x.tail ?? nothing}
      </tbody>`;
    })}</table>`;
  }

  preview(outputs, names, rows, extra = {}) {
    const marks = this.marks(outputs, rows);
    const skip = this.sourceMode(outputs) === 'existing' ? ['Source'] : [];
    const groups = outputRows(this.type, this.draft, outputs)
      .filter((g) => !skip.includes(g.name))
      .map((g) => ({ ...g, rows: names.includes(g.name) ? g.rows : g.rows.filter((r) => marks?.[r.key]) }))
      .filter((g) => g.rows.length || names.includes(g.name));
    return groups.length ? this.outTable(groups, extra, marks) : nothing;
  }

  gramps(s) {
    return grampsRows(s).map(([label, value]) => html`<tr><th>${label}</th>
      <td class="cw-val">${value || blank}</td><td class="cw-rule"></td><td class="cw-acts"></td></tr>`);
  }

  render() {
    if (this.loadError) return html`<p class="error-text">${this.loadError}</p>`;
    if (!this.ctx) return html`<p>${statusLine('busy', 'Loading')}</p>`;
    const outputs = buildOutputs(this.type, this.draft);
    const body = [this.stepDoc, this.stepType, this.stepSource, this.stepCitation, this.stepNote, this.stepCreate][this.step].call(this, outputs);
    return html`
      <nav class="cw-steps" aria-label="Steps">${STEPS.map((name, i) => html`
        <button class="cw-step ${i === this.step ? 'active' : ''} ${i < this.step ? 'done' : ''}"
          ?disabled=${i > DOC && !this.doc} @click=${() => this.go(i)}>
          <span class="cw-step-n">${i + 1}</span><span class="cw-step-name">${name}</span>
        </button>`)}</nav>
      <section class="cw-body">${body}</section>
      <nav class="cw-foot">
        <button class="border" ?disabled=${this.step === DOC} @click=${() => this.go(this.step - 1)}><i>arrow_back</i><span>Back</span></button>
        <div class="max cw-msg">${this.msg ? statusLine(...this.msg) : nothing}</div>
        ${this.step < CREATE ? html`<button ?disabled=${!this.doc} @click=${() => this.go(this.step + 1)}>
          <span>Next</span><i>arrow_forward</i></button>` : nothing}
      </nav>
      ${this.renderPop()}`;
  }

  stepDoc() {
    const pickKey = (e, id) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.pickDoc(id); } };
    return html`<div class="cw-cols">
      <div class="cw-form">
        <div class="field prefix border small cw-filter">
          <i class="front">search</i>
          <input type="text" .value=${this.docQ} placeholder="Find a Paperless document" autocomplete="off"
            @input=${(e) => this.queueDocs(e.target.value)}>
        </div>
        <ul class="list border cw-docs">${this.docHits.map((d) => html`<li tabindex="0" class=${d.id === this.doc?.id ? 'active' : ''}
            @click=${() => this.pickDoc(d.id)} @keydown=${(e) => pickKey(e, d.id)}>
          <img class="cw-hit-thumb" src="${API}/thumb/${d.id}" alt="" loading="lazy">
          <div class="max">
            <div class="cw-hit-title">${d.title}</div>
            <div class="small-text secondary-text">${[d.pid, d.created?.slice(0, 10)].filter(Boolean).join(' · ')}</div>
          </div>
        </li>`)}</ul>
        ${this.docHits.length ? nothing : html`<p class="secondary-text">No matches</p>`}
      </div>
      <div class="cw-side">${this.doc ? this.docCard() : nothing}</div>
    </div>`;
  }

  docCard() {
    const d = this.doc, { paperless_url: pl, gramps_url: gr } = this.ctx;
    return html`<article class="cw-doc border">
      <img class="cw-thumb" src="${API}/thumb/${d.id}" alt="">
      <div class="max">
        <h6 class="cw-doc-title">${d.title}</h6>
        <div class="cw-meta">
          <span class="mono">${d.pid}</span>
          ${d.created ? html`<span>${d.created.slice(0, 10)}</span>` : nothing}
          ${pl ? html`<a class="link" href="${pl}/documents/${d.id}/details" target="_blank" rel="noopener">Paperless</a>` : nothing}
          ${gr && d.media ? html`<a class="link" href="${gr}/media/${d.media.gramps_id}" target="_blank" rel="noopener">Gramps</a>` : nothing}
        </div>
        ${d.media ? nothing : html`<p class="error-text">Gramps has no media ${d.pid}</p>`}
        ${d.citations.length ? html`<table class="cw-cited cw-bases">${d.citations.map((c) => html`<tr
            class=${c.handle === this.basis ? 'active' : ''} tabindex="0" @click=${() => this.startFrom(c)}
            @keydown=${(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.startFrom(c); } }}>
          <td class="mono">${gr ? html`<a class="link" href="${gr}/citation/${c.gramps_id}" target="_blank" rel="noopener"
            @click=${(e) => e.stopPropagation()}>${c.gramps_id}</a>` : c.gramps_id}</td>
          <td>${c.page}</td><td class="secondary-text">${c.source}</td></tr>`)}</table>` : nothing}
      </div>
    </article>`;
  }

  stepType() {
    const t = this.type, groups = recordGroups(RECORDS, this.gen.filter);
    return html`<div class="cw-cols">
      <div class="cw-form">
        <div class="field prefix border small cw-filter">
          <i class="front">search</i>
          <input type="text" .value=${this.gen.filter} placeholder="Filter record types" autocomplete="off"
            @input=${(e) => { this.gen.filter = e.target.value; this.changed(); }}>
        </div>
        ${groups.map((g) => html`<h6 class="cw-chapter">${g.label}</h6>
          <div class="cw-types">${g.records.map((r) => html`<button class="chip ${r.id === t.id ? 'fill' : ''}"
            title=${r.hint || r.group} @click=${() => this.selectType(r.id)}>${r.name}</button>`)}</div>`)}
        ${groups.length ? nothing : html`<p class="secondary-text">No record type matches</p>`}
      </div>
      <div class="cw-side">
        <article class="border cw-type">
          <h6>${t.name}</h6>
          <div class="secondary-text">${CHAPTERS[t.chapter]} · ${t.group}</div>
          <nav class="cw-type-acts">
            ${t.examples.length ? html`<div class="field suffix border small cw-example">
              <select @change=${(e) => { if (e.target.value !== '') this.loadExample(Number(e.target.value)); e.target.value = ''; }}>
                <option value="">Load guide example</option>
                ${t.examples.map((c, i) => html`<option value=${i}>${exampleLabel(c)}</option>`)}
              </select><i>arrow_drop_down</i></div>` : nothing}
            <button class="border small" @click=${() => this.clear()}>${this.clearArmed ? 'Click again to clear' : 'Clear'}</button>
          </nav>
        </article>
      </div>
    </div>`;
  }

  stepSource(outputs) {
    const t = this.type, d = this.draft, code = CHAPTER_CODE[t.chapter];
    const own = sourceRows(t, d), reference = referenceRows(t, d);
    const isNew = this.sourceMode(outputs) === 'new';
    return html`
      <nav class="group connected cw-mode">
        <button class=${isNew ? 'active' : ''} @click=${() => this.setSourceMode('new')}><i>add</i><span>New source</span></button>
        <button class=${isNew ? '' : 'active'} @click=${() => this.setSourceMode('existing')}><i>menu_book</i><span>Existing source</span></button>
      </nav>
      <div class="cw-cols">
        ${this.formColumn(html`
          <h6 class="cw-h">Source ${this.ref(`${code} §4`)}</h6>
          ${own.map((r) => this.input(r))}
          <h6 class="cw-h">Platform and archive ${this.ref('A10')} ${this.ref('A9')}</h6>
          ${reference.map((r) => this.input(r))}`)}
        <div class="cw-side">
          ${isNew ? nothing : this.sourcePicker(outputs)}
          ${this.preview(outputs, isNew ? ['Source'] : [], [...own, ...reference], isNew ? { Source: { tail: this.repositoryRow() } } : {})}
          ${isNew ? this.titleClash(outputs) : nothing}
        </div>
      </div>`;
  }

  sourcePicker(outputs) {
    const chosen = this.chosenSource(outputs);
    const title = plain(outputs.title);
    const q = squash(this.srcQ);
    const used = (s) => s.remembered?.used_at || '';
    const list = (this.ctx.sources || [])
      .filter((s) => !q || squash(`${s.gramps_id} ${s.title} ${s.abbrev}`).includes(q))
      .sort((a, b) => (same(b.title, title) - same(a.title, title)) || used(b).localeCompare(used(a)) || a.title.localeCompare(b.title))
      .slice(0, 50);
    const pickKey = (e, s) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.pickSource(s); } };
    return html`<div class="field prefix border small cw-filter">
        <i class="front">search</i>
        <input type="text" .value=${this.srcQ} placeholder="Find a Gramps source" autocomplete="off"
          @input=${(e) => { this.srcQ = e.target.value; }}>
      </div>
      <ul class="list border cw-sources">${list.map((s) => html`<li tabindex="0" class=${s.handle === chosen?.handle ? 'active' : ''}
          @click=${() => this.pickSource(s)} @keydown=${(e) => pickKey(e, s)}>
          <span class="mono cw-src-id">${s.gramps_id}</span>
          <div class="max">
            <div class="cw-hit-title">${s.title}</div>
            ${s.abbrev ? html`<div class="small-text secondary-text">${s.abbrev}</div>` : nothing}
          </div>
        </li>`)}</ul>
      ${list.length ? nothing : html`<p class="secondary-text">No matches</p>`}
      ${chosen ? html`<table class="cw-out cw-picked">${COLS}<tbody>
        <tr class="cw-group"><td colspan="4">Source <span class="cw-chip mono">${chosen.gramps_id}</span></td></tr>
        ${this.gramps(chosen)}</tbody></table>` : nothing}`;
  }

  repositoryRow() {
    const value = this.repository()?.handle || '';
    const choose = (e) => {
      this.repo = e.target.value ? { mode: 'existing', handle: e.target.value } : { mode: 'none' };
      this.edited();
    };
    return html`<tr class="cw-row-select"><th>Repository</th><td class="cw-val cw-ctl"><div class="field suffix border small cw-select">
        <select aria-label="Repository" @change=${choose}>
          <option value="" ?selected=${value === ''}>None</option>
          ${(this.ctx.repositories || []).map((r) => html`<option value=${r.handle} ?selected=${value === r.handle}>${r.name}</option>`)}
        </select><i>arrow_drop_down</i></div></td><td class="cw-rule">${this.ref('A9')}</td><td class="cw-acts"></td></tr>`;
  }

  titleClash(outputs) {
    const [match] = this.matches(outputs);
    if (this.gsrc.mode !== 'new' || !match) return nothing;
    return html`<div class="cw-check-line warn cw-clash"><i>warning</i><span>${match.gramps_id} has this title</span>
      <button class="border small" @click=${() => this.pickSource(match)}>Use ${match.gramps_id}</button></div>`;
  }

  stepCitation(outputs) {
    const t = this.type, d = this.draft, code = CHAPTER_CODE[t.chapter];
    const rows = citationRows(t, d);
    return html`<div class="cw-cols">
      ${this.formColumn(html`<h6 class="cw-h">Citation ${this.ref(`${code} §7`)} ${this.ref('A7')}</h6>
        ${rows.map((r) => this.input(r))}`)}
      <div class="cw-side">${this.preview(outputs, ['Citation'], rows)}</div>
    </div>`;
  }

  stepNote(outputs) {
    const t = this.type, d = this.draft;
    const rows = noteRows(t, d);
    return html`<div class="cw-cols">
      ${this.formColumn(html`<h6 class="cw-h">Reference note ${this.ref('A5')}</h6>
        ${rows.map((r) => this.input(r))}`)}
      <div class="cw-side">${this.preview(outputs, ['Citation note'], rows)}</div>
    </div>`;
  }

  scanSelect(r, scan) {
    const key = SELECTS[r.key];
    const ctx = this.ctx;
    const rows = key === 'document_type' ? ctx.document_types : key === 'correspondent' ? ctx.correspondents
      : ctx.date_meaning.options.map((o) => ({ id: o.id, name: o.label }));
    const value = scan[key];
    const set = (e) => {
      const v = e.target.value;
      this.scanPick = { ...this.scanPick, [key]: v === '' ? null : key === 'date_meaning' ? v : Number(v) };
      this.edited();
    };
    return html`<tr class="cw-row-select">
      <th>${r.label}</th>
      <td class="cw-val cw-ctl"><div class="field suffix border small cw-select">
        <select aria-label=${r.label} ?disabled=${!this.fileScan} @change=${set}>
          <option value="" ?selected=${value == null}>None</option>
          ${rows.map((x) => html`<option value=${x.id} ?selected=${String(x.id) === String(value)}>${x.name}</option>`)}
        </select><i>arrow_drop_down</i></div></td>
      <td class="cw-rule">${this.ref(r.ref, r.key)}</td>
      <td class="cw-acts"></td>
    </tr>`;
  }

  stepCreate(outputs) {
    const t = this.type, d = this.draft;
    const isNew = this.sourceMode(outputs) === 'new';
    const source = isNew ? null : this.chosenSource(outputs);
    const repo = isNew ? this.repository() : null;
    const scan = this.scanValues(outputs);
    const blockers = this.blockers(outputs, source, repo);
    const checks = runChecks(t, d, outputs).filter((p) => !['Fill', 'A6'].includes(p.rule));
    const note = exampleNote(t, d, outputs, GUIDE);
    const repoName = repo && this.ctx.repositories.find((r) => r.handle === repo.handle)?.name;
    const [clash] = isNew && this.gsrc.mode === 'new' ? this.matches(outputs) : [];
    const unmatched = [['plDoctype', 'document_type', 'document type'], ['plCorrespondent', 'correspondent', 'correspondent']]
      .filter(([k, key]) => this.fileScan && plain(outputs[k]).trim() && !Object.hasOwn(this.scanPick, key)
        && paperlessMatch(plain(outputs[k]), key === 'document_type' ? this.ctx.document_types : this.ctx.correspondents) == null)
      .map(([k, , what]) => `No Paperless ${what} named ${plain(outputs[k])}`);
    const extra = {
      Source: isNew ? {
        head: html` <span class="cw-chip">New</span>`,
        tail: html`<tr><th>Repository</th><td class="cw-val">${repoName || html`<span class="cw-blank">(none)</span>`}</td>
          <td class="cw-rule">${this.ref('A9')}</td><td class="cw-acts"></td></tr>`,
      } : {
        head: source ? html` <span class="cw-chip mono">${source.gramps_id}</span>` : nothing,
        body: source ? this.gramps(source) : nothing,
      },
      Citation: { head: this.doc?.media ? html` <span class="cw-chip mono">${this.doc.media.gramps_id}</span>` : nothing },
      'Paperless scan': {
        off: !this.fileScan,
        head: html` <label class="checkbox cw-scan-toggle"><input type="checkbox" .checked=${this.fileScan}
          @change=${(e) => { this.fileScan = e.target.checked; this.edited(); }}><span>Update the Paperless document</span></label>`,
        row: (r) => {
          if (r.key === 'plDateMeaning' && !this.ctx.date_meaning) return nothing;
          return SELECTS[r.key] ? this.scanSelect(r, scan) : this.outRow(r);
        },
      },
    };
    const lines = [...blockers.map((m) => ['error', m]), ...checks.map((p) => ['warn', p.message, p.rule]), ...unmatched.map((m) => ['warn', m])];
    return html`<div class="cw-create">
      ${this.result ? this.resultCard() : nothing}
      ${this.outTable(outputRows(t, d, outputs), extra)}
      <div class="cw-checks">
        ${lines.map(([kind, m, rule]) => html`<div class="cw-check-line ${kind}">
          <i>${kind === 'error' ? 'block' : 'warning'}</i>${rule ? html`${this.ref(rule)} ` : nothing}<span>${m}</span></div>`)}
        ${clash ? html`<div class="cw-check-line warn"><i>warning</i><span>${clash.gramps_id} has this title</span>
          <button class="border small" @click=${() => this.pickSource(clash)}>Use ${clash.gramps_id}</button></div>` : nothing}
        ${note ? html`<div class="cw-check-line secondary-text"><i>menu_book</i><span>${note}</span></div>` : nothing}
      </div>
      <nav class="cw-create-acts">
        <button class="border" @click=${() => this.copy(copyAllText(outputs))}><i>content_copy</i><span>Copy all</span></button>
        <div class="max"></div>
        ${this.result ? nothing : html`<button ?disabled=${this.busy || blockers.length > 0} @click=${() => this.create()}>
          <i>add_circle</i><span>Create in Gramps</span></button>`}
      </nav>
    </div>`;
  }

  resultCard() {
    const r = this.result, { gramps_url: gr, paperless_url: pl } = this.ctx;
    const link = (kind, id) => (gr ? html`<a class="link mono" href="${gr}/${kind}/${id}" target="_blank" rel="noopener">${id}</a>` : html`<span class="mono">${id}</span>`);
    return html`<article class="border cw-result">
      <h6>Created</h6>
      <table class="cw-cited">
        ${r.created.map((c) => html`<tr><td>${c.kind[0].toUpperCase() + c.kind.slice(1)}</td><td>${link(c.kind, c.gramps_id)}</td><td>${c.title}</td></tr>`)}
        ${r.created.some((c) => c.kind === 'source') ? nothing : html`<tr><td>Source</td><td>${link('source', r.source.gramps_id)}</td><td>${r.source.title}</td></tr>`}
        ${r.scan ? html`<tr><td>Paperless</td><td>${pl ? html`<a class="link mono" href="${pl}/documents/${r.scan}/details" target="_blank" rel="noopener">#${r.scan}</a>` : html`<span class="mono">#${r.scan}</span>`}</td><td>${this.doc?.title || ''}</td></tr>` : nothing}
      </table>
      ${r.scan_error ? html`<p class="error-text">Paperless: ${r.scan_error}</p>` : nothing}
      <nav class="cw-result-acts">
        <button @click=${() => this.nextOnSource()}><span>Next citation on this Source</span></button>
        <button class="border" @click=${() => this.againOnDocument()}><span>Another citation from this document</span></button>
      </nav>
    </article>`;
  }
}

customElements.define('citations-wizard', CitationsWizard);
