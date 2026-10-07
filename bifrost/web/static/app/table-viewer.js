import { svg } from 'lit';
import { BifrostElement, html, nothing, api, post, spinner } from './core.js';
import * as G from './table-geom.js';

const API = '/tables/api';
const HEAD_H = 52;
const GUTTER_W = 44;
const MAX_SCALE = 8;
const HISTORY = 100;
const STEPS = [1, 2, 5, 10, 20, 50, 100];

const LANGS = [['orig', 'Original'], ['trans', 'Translation'], ['both', 'Both']];
const LANG_KEY = 'bifrost-tables-lang';

const uid = () => Math.random().toString(36).slice(2, 10);
const pad = (n) => String(n).padStart(2, '0');
const editable = (t) => t?.matches?.('input, textarea, select, [contenteditable]');
const stop = (e) => e.stopPropagation();

// api() errors read '409: {"detail": ...}'; show the sentence the server wrote
function why(e) {
  const m = /^\d{3}: (.*)$/s.exec(e?.message || '');
  if (m) {
    try {
      const detail = JSON.parse(m[1]).detail;
      if (typeof detail === 'string') return detail;
    } catch { }
  }
  return e?.message || String(e);
}

function when(iso) {
  const d = new Date(`${iso}Z`);
  return Number.isNaN(d.getTime()) ? ''
    : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function savedLang() {
  try {
    const v = localStorage.getItem(LANG_KEY);
    return LANGS.some(([id]) => id === v) ? v : 'orig';
  } catch {
    return 'orig';
  }
}

class TableViewer extends BifrostElement {
  static properties = {
    doc: { type: Number },
    info: { state: true },
    page: { state: true },
    grid: { state: true },
    loadError: { state: true },
    imgSize: { state: true },
    imgError: { state: true },
    view: { state: true },
    vp: { state: true },
    mode: { state: true },
    tool: { state: true },
    hover: { state: true },
    cur: { state: true },
    sel: { state: true },
    draft: { state: true },
    lang: { state: true },
    notes: { state: true },
    noteHover: { state: true },
    noteEdit: { state: true },
    placing: { state: true },
    picked: { state: true },
    renaming: { state: true },
    renameDraft: { state: true },
    drawRect: { state: true },
    linesDraft: { state: true },
    pointer: { state: true },
    busy: { state: true },
    saveError: { state: true },
    conflict: { state: true },
    toast: { state: true },
    dlg: { state: true },
    copyList: { state: true },
  };

  constructor() {
    super();
    this.page = Math.max(1, parseInt(new URLSearchParams(location.search).get('page'), 10) || 1);
    this.info = null;
    this.grid = null;
    this.rev = 0;
    this.loadError = '';
    this.imgSize = null;
    this.imgError = '';
    this.view = { s: 1, tx: 0, ty: 0 };
    this.vp = [0, 0];
    this.mode = 'view';
    this.tool = 'select';
    this.hover = null;
    this.cur = null;
    this.sel = new Set();
    this.anchor = null;
    this.draft = null;
    this.field = 'orig';
    this.lang = savedLang();
    this.notes = [];
    this.noteHover = null;
    this.noteEdit = null;
    this.placing = false;
    this.picked = null;
    this.renaming = null;
    this.renameDraft = { name: '', trans: '' };
    this.renameField = 'name';
    this.drawRect = null;
    this.linesDraft = null;
    this.pointer = '';
    this.busy = '';
    this.saveError = '';
    this.conflict = false;
    this.toast = null;
    this.dlg = null;
    this.copyList = [];
    this.past = [];
    this.future = [];
    this.gesture = null;
    this.dirty = false;
    this.chain = Promise.resolve();
    this.onKey = (e) => this.key(e);
    this.onHide = () => this.flushNow();
    this.onHash = () => this.lineFromHash();
  }

  connectedCallback() {
    super.connectedCallback();
    document.addEventListener('keydown', this.onKey);
    addEventListener('pagehide', this.onHide);
    addEventListener('hashchange', this.onHash);
    this.load();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener('keydown', this.onKey);
    removeEventListener('pagehide', this.onHide);
    removeEventListener('hashchange', this.onHash);
    this.resizer?.disconnect();
    clearTimeout(this.saveTimer);
    clearTimeout(this.toastTimer);
  }

  get gridUrl() { return `${API}/doc/${this.doc}/page/${this.page}`; }
  get viewport() { return this.querySelector('.tbl-viewport'); }

  // ---- loading

  async load() {
    try {
      this.info = await api(`${API}/doc/${this.doc}`);
    } catch (e) {
      this.loadError = why(e);
      return;
    }
    if (this.info.pages && this.page > this.info.pages) this.page = 1;
    await this.loadPage();
  }

  async loadPage() {
    Object.assign(this, {
      grid: null, rev: 0, past: [], future: [], hover: null, cur: null, sel: new Set(), anchor: null,
      draft: null, picked: null, renaming: null, linesDraft: null, imgSize: null, imgError: '',
      conflict: false, saveError: '', tool: 'select', notes: [], noteHover: null, noteEdit: null,
      placing: false,
    });
    try {
      const [r, notes] = await Promise.all([api(this.gridUrl), api(`${this.gridUrl}/notes`)]);
      this.grid = r.grid;
      this.rev = r.rev;
      this.notes = notes;
    } catch (e) {
      this.loadError = why(e);
      return;
    }
    this.mode = this.grid || this.notes.length ? 'view' : 'layout';
    if (this.imgSize) this.fit();
    this.lineFromHash();
  }

  async goPage(n) {
    if (n < 1 || n > this.info.pages || n === this.page) return;
    this.commitEdit();
    await Promise.all([this.flush(), this.saveNote()]);
    this.page = n;
    const url = new URL(location.href);
    url.searchParams.set('page', n);
    url.hash = '';
    history.replaceState(null, '', url);
    await this.loadPage();
  }

  imgLoaded(e) {
    this.imgSize = [e.target.naturalWidth, e.target.naturalHeight];
    this.fit();
    this.lineFromHash();
  }

  updated(changed) {
    const vp = this.viewport;
    if (vp && !this.resizer) {
      this.resizer = new ResizeObserver(([entry]) => {
        const { width, height } = entry.contentRect;
        this.vp = [width, height];
        if (this.wantFit) {
          this.fit();
          this.lineFromHash();
        }
      });
      this.resizer.observe(vp);
    }
    const editKey = this.draft && this.cur ? `${this.cur.row}:${this.cur.col}` : null;
    if (editKey !== this.editKey) {
      this.editKey = editKey;
      if (editKey) this.focusEditor();
    }
    if (changed.has('renaming') && this.renaming !== null) {
      const input = this.querySelector(`.tbl-rename input[data-field="${this.renameField}"]`);
      input?.focus();
      input?.select();
    }
    const openNote = this.noteEdit ? this.noteEdit.id ?? 'new' : null;
    if (openNote !== this.openNote) {
      this.openNote = openNote;
      const box = this.querySelector('.tbl-note-edit textarea');
      box?.focus();
      box?.setSelectionRange(box.value.length, box.value.length);
    }
    const dlg = this.querySelector('dialog.tbl-dialog');
    if (dlg && this.dlg && !dlg.open) dlg.showModal();
    else if (dlg && !this.dlg && dlg.open) dlg.close();
  }

  focusEditor() {
    const input = this.querySelector(`.tbl-editor input[data-field="${this.field}"]`)
      || this.querySelector('.tbl-editor input');
    if (!input) return;
    input.focus();
    if (this.typed) input.setSelectionRange(input.value.length, input.value.length);
    else input.select();
    this.typed = false;
  }

  // ---- coordinates

  toNorm([x, y]) {
    const { s, tx, ty } = this.view;
    const [w, h] = this.imgSize;
    return [(x - tx) / (s * w), (y - ty) / (s * h)];
  }

  toScreen([x, y]) {
    const { s, tx, ty } = this.view;
    const [w, h] = this.imgSize;
    return [tx + x * w * s, ty + y * h * s];
  }

  screenPoint(e) {
    const r = this.viewport.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  get inset() { return this.grid ? [GUTTER_W, HEAD_H] : [0, 0]; }

  fitScale() {
    const [w, h] = this.imgSize;
    const [left, top] = this.inset;
    return Math.min((this.vp[0] - left - 16) / w, (this.vp[1] - top - 16) / h);
  }

  fit() {
    this.wantFit = !this.imgSize || !this.vp[0];
    if (this.wantFit) return;
    const [w, h] = this.imgSize;
    const [left, top] = this.inset;
    const s = this.fitScale();
    this.view = { s, tx: left + (this.vp[0] - left - w * s) / 2, ty: top + (this.vp[1] - top - h * s) / 2 };
  }

  zoomAt(factor, [x, y]) {
    const { s, tx, ty } = this.view;
    const ns = G.clamp(s * factor, Math.min(1, this.fitScale()) / 2, MAX_SCALE);
    const k = ns / s;
    this.view = { s: ns, tx: x - (x - tx) * k, ty: y - (y - ty) * k };
  }

  zoomCenter(factor) {
    this.zoomAt(factor, [this.vp[0] / 2, this.vp[1] / 2]);
  }

  panBy(dx, dy) {
    this.view = { ...this.view, tx: this.view.tx + dx, ty: this.view.ty + dy };
  }

  cellBox(row, col) {
    const P = G.points(this.grid);
    const pts = [P[row][col], P[row][col + 1], P[row + 1][col + 1], P[row + 1][col]].map((p) => this.toScreen(p));
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    return { l: Math.min(...xs), r: Math.max(...xs), t: Math.min(...ys), b: Math.max(...ys) };
  }

  ensureVisible(row, col) {
    if (!this.imgSize || !this.vp[0]) return;
    const b = this.cellBox(row, col);
    const [vw, vh] = this.vp;
    const left = GUTTER_W + 8;
    const top = HEAD_H + 8;
    const bottom = vh - 80;
    let dx = 0;
    let dy = 0;
    if (b.l < left) dx = left - b.l;
    else if (b.r > vw - 8) dx = Math.max(vw - 8 - b.r, left - b.l);
    if (b.t < top) dy = top - b.t;
    else if (b.b > bottom) dy = Math.max(bottom - b.b, top - b.t);
    if (dx || dy) this.panBy(dx, dy);
  }

  colXs() {
    const g = this.grid;
    const P = G.points(g);
    const m = g.rows.length;
    const [w, h] = this.imgSize;
    const { s, tx, ty } = this.view;
    const y = (this.vp[1] / 2 - ty) / (s * h);
    return P[0].map((top, k) => {
      const bot = P[m][k];
      return tx + G.xAt(top, bot, G.clamp(y, Math.min(top[1], bot[1]), Math.max(top[1], bot[1]))) * w * s;
    });
  }

  rowYs() {
    const g = this.grid;
    const P = G.points(g);
    const n = g.cols.length;
    const [w, h] = this.imgSize;
    const { s, tx, ty } = this.view;
    const x = (this.vp[0] / 2 - tx) / (s * w);
    return P.map((edge) => {
      const [a, b] = [edge[0], edge[n]];
      return ty + G.yAt(a, b, G.clamp(x, Math.min(a[0], b[0]), Math.max(a[0], b[0]))) * h * s;
    });
  }

  // ---- history and saving

  snapshot() { return JSON.stringify(this.grid); }

  commit(next) {
    if (this.busy) return;
    this.past.push(this.snapshot());
    if (this.past.length > HISTORY) this.past.shift();
    this.future = [];
    this.grid = next;
    this.queueSave();
  }

  beginEdit() { this.before = this.snapshot(); }

  endEdit() {
    if (this.before !== undefined && this.before !== this.snapshot()) {
      this.past.push(this.before);
      if (this.past.length > HISTORY) this.past.shift();
      this.future = [];
      this.queueSave();
      this.requestUpdate();
    }
    this.before = undefined;
  }

  undo() { this.travel('past', 'future'); }
  redo() { this.travel('future', 'past'); }

  travel(from, to) {
    this.commitEdit();
    if (!this[from].length || this.busy) return;
    this[to].push(this.snapshot());
    this.grid = JSON.parse(this[from].pop());
    this.picked = null;
    this.renaming = null;
    const g = this.grid;
    if (!g || (this.cur && (this.cur.row >= g.rows.length || this.cur.col >= g.cols.length))) this.cur = null;
    this.hover = null;
    this.queueSave();
  }

  queueSave() {
    this.dirty = true;
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.flush(), 600);
  }

  flush() {
    clearTimeout(this.saveTimer);
    this.chain = this.chain.then(() => this.save());
    return this.chain;
  }

  async save() {
    if (!this.dirty || this.conflict) return;
    this.dirty = false;
    const body = JSON.stringify({ grid: this.grid, rev: this.rev });
    try {
      this.rev = (await api(this.gridUrl, { method: 'PUT', body })).rev;
      this.saveError = '';
    } catch (e) {
      this.saveError = why(e);
      if (e.message.startsWith('409')) this.conflict = true;
      else {
        this.dirty = true;
        this.saveTimer = setTimeout(() => this.flush(), 5000);
      }
    }
  }

  flushNow() {
    if (!this.dirty || this.conflict) return;
    this.dirty = false;
    fetch(this.gridUrl, {
      method: 'PUT', keepalive: true, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grid: this.grid, rev: this.rev }),
    });
  }

  say(msg, failed = false) {
    this.toast = { msg, failed };
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => { this.toast = null; }, failed ? 9000 : 4000);
  }

  // ---- values

  value(row, col, key = 'cells') {
    const g = this.grid;
    return g[key]?.[g.rows[row].id]?.[g.cols[col].id] || '';
  }

  setCell(row, col, vals) {
    const g = this.grid;
    const rid = g.rows[row].id;
    const cid = g.cols[col].id;
    let next = g;
    for (const [key, text] of [['cells', vals.orig], ['trans', vals.trans]]) {
      if (text === undefined) continue;
      const t = text.trim();
      const map = next[key] || {};
      if ((map[rid]?.[cid] || '') === t) continue;
      const out = { ...map };
      const row = { ...(out[rid] || {}) };
      if (t) row[cid] = t;
      else delete row[cid];
      if (Object.keys(row).length) out[rid] = row;
      else delete out[rid];
      next = { ...next, [key]: out };
    }
    if (next !== g) this.commit(next);
  }

  get fields() { return this.lang === 'both' ? ['orig', 'trans'] : [this.lang]; }

  startEdit(text) {
    if (!this.cur || this.busy) return;
    const { row, col } = this.cur;
    this.field = this.fields[0];
    this.typed = text !== undefined;
    const draft = { orig: this.value(row, col), trans: this.value(row, col, 'trans') };
    if (this.typed) draft[this.field] = text;
    this.draft = draft;
  }

  commitEdit() {
    if (!this.draft || !this.cur) return;
    const draft = this.draft;
    this.draft = null;
    this.setCell(this.cur.row, this.cur.col, Object.fromEntries(this.fields.map((f) => [f, draft[f]])));
  }

  step({ row, col }, dr, dc, wrap) {
    const g = this.grid;
    let r = row + dr;
    let c = col + dc;
    if (wrap && c >= g.cols.length) { c = 0; r++; }
    if (wrap && c < 0) { c = g.cols.length - 1; r--; }
    if (r < 0 || r >= g.rows.length || c < 0 || c >= g.cols.length) return null;
    return { row: r, col: c };
  }

  moveTo(next) {
    this.cur = next;
    this.selectRows([next.row]);
    this.ensureVisible(next.row, next.col);
  }

  editorKey(e, field) {
    if (e.isComposing) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      this.draft = null;
      return;
    }
    const inside = this.lang === 'both' && e.key === 'Tab' && (field === 'orig') !== e.shiftKey;
    if ((e.key !== 'Enter' && e.key !== 'Tab') || inside) return;
    e.preventDefault();
    const back = e.shiftKey ? -1 : 1;
    const next = e.key === 'Enter' ? this.step(this.cur, back, 0, false) : this.step(this.cur, 0, back, true);
    this.commitEdit();
    if (!next) return;
    this.moveTo(next);
    this.field = e.key === 'Tab' && this.lang === 'both' ? (e.shiftKey ? 'trans' : 'orig') : field;
    this.draft = { orig: this.value(next.row, next.col), trans: this.value(next.row, next.col, 'trans') };
  }

  editorOut(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) this.commitEdit();
  }

  selectRows(js) {
    const g = this.grid;
    this.sel = new Set(js.map((j) => g.rows[j].id));
    this.anchor = js.length ? js[js.length - 1] : null;
    this.syncHash();
  }

  pickRow(j, e) {
    const g = this.grid;
    const id = g.rows[j].id;
    if (e.shiftKey && this.anchor !== null) {
      const [a, b] = [Math.min(this.anchor, j), Math.max(this.anchor, j)];
      this.sel = new Set(g.rows.slice(a, b + 1).map((r) => r.id));
      this.syncHash();
    } else if (e.metaKey || e.ctrlKey) {
      const s = new Set(this.sel);
      if (s.has(id)) s.delete(id);
      else s.add(id);
      this.sel = s;
      this.anchor = j;
      this.syncHash();
    } else this.selectRows([j]);
  }

  clearRows() {
    const g = this.grid;
    const keys = this.fields.map((f) => (f === 'orig' ? 'cells' : 'trans'));
    if (![...this.sel].some((id) => keys.some((k) => g[k]?.[id]))) return;
    const next = { ...g };
    for (const k of keys) {
      next[k] = { ...(g[k] || {}) };
      for (const id of this.sel) delete next[k][id];
    }
    this.commit(next);
  }

  groupOf(j) {
    const g = this.grid;
    const filled = (k) => !!g.cells[g.rows[k].id];
    if (!g?.group_col || !filled(j)) return null;
    const starts = (k) => !!g.cells[g.rows[k].id]?.[g.group_col];
    let a = j;
    while (a > 0 && !starts(a) && filled(a - 1)) a--;
    let b = j + 1;
    while (b < g.rows.length && !starts(b) && filled(b)) b++;
    if (!starts(a) && !g.rows.some((_, k) => starts(k))) return null;
    return [a, b];
  }

  syncHash() {
    const g = this.grid;
    const j = g ? g.rows.findIndex((r) => this.sel.has(r.id)) : -1;
    const url = new URL(location.href);
    url.hash = j >= 0 ? `line=${g.first_line + j}` : '';
    history.replaceState(null, '', url);
  }

  lineFromHash() {
    const m = /line=(-?\d+)/.exec(location.hash);
    const g = this.grid;
    if (!m || !g || !this.imgSize) return;
    const j = Number(m[1]) - g.first_line;
    if (j < 0 || j >= g.rows.length) return;
    this.cur = { row: j, col: 0 };
    this.selectRows([j]);
    this.ensureVisible(j, 0);
  }

  async transcribe() {
    if (this.busy) return;
    this.commitEdit();
    this.busy = 'transcribe';
    try {
      await this.flush();
      if (this.conflict) return;
      const rows = this.sel.size ? this.grid.rows.filter((r) => this.sel.has(r.id)).map((r) => r.id) : null;
      const r = await post(`${this.gridUrl}/transcribe`, { rows });
      if (r.filled) {
        this.past.push(this.snapshot());
        this.future = [];
        this.grid = r.grid;
      }
      this.rev = r.rev;
      const msg = r.filled ? `Filled ${r.filled} cell${r.filled === 1 ? '' : 's'}` : 'No cells filled';
      this.say(r.errors.length ? `${msg}. ${r.errors.join('; ')}` : msg, r.errors.length > 0);
    } catch (e) {
      this.say(why(e), true);
    } finally {
      this.busy = '';
    }
  }

  setLang(lang) {
    this.commitEdit();
    this.commitRename();
    this.lang = lang;
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch { }
  }

  colNames(c) {
    if (this.lang === 'orig') return [c.name, ''];
    if (this.lang === 'trans') return [c.trans || c.name, ''];
    return [c.name, c.trans && c.trans !== c.name ? c.trans : ''];
  }

  tipLines(row, col) {
    const c = this.grid.cols[col];
    const [v, t] = [this.value(row, col), this.value(row, col, 'trans')];
    const lines = this.lang === 'orig' ? [[c.name, v]]
      : this.lang === 'trans' ? [[c.trans || c.name, t || v]]
        : [[c.name, v], ...(t ? [[c.trans || c.name, t]] : [])];
    return lines.filter(([name, value]) => name || value);
  }

  // ---- notes

  noteAt(sp) {
    if (this.mode !== 'view' || !this.imgSize) return null;
    let best = null;
    let bestD = 10;
    for (const n of this.notes) {
      const [x, y] = this.toScreen([n.x, n.y]);
      const d = Math.hypot(x - sp[0], y - sp[1]);
      if (d <= bestD) { best = n; bestD = d; }
    }
    return best;
  }

  placeAt(sp) {
    const [x, y] = this.toNorm(sp);
    this.placing = false;
    if (x >= 0 && x <= 1 && y >= 0 && y <= 1) this.noteEdit = { id: null, x, y, text: '' };
  }

  async saveNote() {
    const ne = this.noteEdit;
    if (!ne) return;
    this.noteEdit = null;
    const text = ne.text.trim();
    const old = this.notes.find((n) => n.id === ne.id);
    if (!text || text === old?.text) return;
    try {
      if (old) this.swapNote(await api(`${API}/notes/${ne.id}`, { method: 'PATCH', body: JSON.stringify({ text }) }));
      else this.notes = [...this.notes, await post(`${this.gridUrl}/notes`, { x: ne.x, y: ne.y, text })];
    } catch (e) {
      this.say(why(e), true);
    }
  }

  async moveNote({ id, x, y }) {
    try {
      this.swapNote(await api(`${API}/notes/${id}`, { method: 'PATCH', body: JSON.stringify({ x, y }) }));
    } catch (e) {
      this.say(why(e), true);
    }
  }

  async deleteNote(id) {
    this.noteEdit = null;
    try {
      await api(`${API}/notes/${id}`, { method: 'DELETE' });
      this.notes = this.notes.filter((n) => n.id !== id);
    } catch (e) {
      this.say(why(e), true);
    }
  }

  swapNote(note) {
    this.notes = this.notes.map((n) => (n.id === note.id ? note : n));
  }

  noteKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      this.noteEdit = null;
    } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      this.saveNote();
    }
  }

  noteOut(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) this.saveNote();
  }

  // ---- layout

  addLine(kind, i, p) {
    const g = this.grid;
    const pos = G.split(g, kind, i, p);
    if (kind === 'col') {
      const cols = [...g.cols];
      cols.splice(i + 1, 0, { id: uid(), name: '', u: pos });
      this.grid = { ...g, cols };
    } else {
      const rows = [...g.rows];
      rows.splice(i + 1, 0, { id: uid(), v: pos });
      this.grid = { ...g, rows };
    }
    return i + 1;
  }

  deletePicked() {
    const { kind, k } = this.picked;
    const g = this.grid;
    const list = kind === 'col' ? g.cols : g.rows;
    if (k < 1 || k >= list.length) return;
    const [gone, keep] = [list[k], list[k - 1]];
    const rest = list.filter((_, i) => i !== k);
    const mergeCols = (map = {}) => Object.fromEntries(Object.entries(map).map(([rid, vals]) => {
      const out = { ...vals };
      if (out[gone.id] && !out[keep.id]) out[keep.id] = out[gone.id];
      delete out[gone.id];
      return [rid, out];
    }).filter(([, vals]) => Object.keys(vals).length));
    const mergeRows = (map = {}) => {
      if (!map[gone.id]) return map;
      const out = { ...map, [keep.id]: { ...map[gone.id], ...(map[keep.id] || {}) } };
      delete out[gone.id];
      return out;
    };
    const merge = kind === 'col' ? mergeCols : mergeRows;
    if (kind === 'col') {
      rest[k - 1] = { ...keep, name: keep.name || gone.name, trans: keep.trans || gone.trans || '' };
    }
    this.picked = null;
    this.commit({
      ...g, cells: merge(g.cells), trans: merge(g.trans), [kind === 'col' ? 'cols' : 'rows']: rest,
      group_col: kind === 'col' && g.group_col === gone.id ? keep.id : g.group_col,
    });
  }

  distribute(n) {
    const g = this.grid;
    const count = G.clamp(Math.round(Number(n)) || 0, 1, 400);
    this.linesDraft = null;
    if (count === g.rows.length && g.rows.every((r, i) => r.v[0] === i / count && r.v[1] === i / count)) return;
    const rows = Array.from({ length: count }, (_, i) => ({ id: g.rows[i]?.id || uid(), v: [i / count, i / count] }));
    const ids = new Set(rows.map((r) => r.id));
    const keep = (map = {}) => Object.fromEntries(Object.entries(map).filter(([rid]) => ids.has(rid)));
    this.commit({ ...g, rows, cells: keep(g.cells), trans: keep(g.trans) });
  }

  setFirstLine(raw) {
    const g = this.grid;
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n) || n === g.first_line) return;
    this.commit({ ...g, first_line: G.clamp(n, -99999, 99999) });
  }

  startRename(i, field = 'name') {
    if (this.renaming !== null) this.commitRename();
    const c = this.grid.cols[i];
    this.renameField = field;
    this.renameDraft = { name: c.name, trans: c.trans || '' };
    this.renaming = i;
    this.ensureColVisible(i);
  }

  commitRename() {
    const i = this.renaming;
    if (i === null) return;
    this.renaming = null;
    const g = this.grid;
    const tidy = (t) => t.replace(/\s+/g, ' ').trim();
    const [name, trans] = [tidy(this.renameDraft.name), tidy(this.renameDraft.trans)];
    const c = g?.cols[i];
    if (c && (c.name !== name || (c.trans || '') !== trans)) {
      this.commit({ ...g, cols: g.cols.map((x, k) => (k === i ? { ...x, name, trans } : x)) });
    }
  }

  renameKey(e, field) {
    if (e.isComposing) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      this.renaming = null;
      return;
    }
    const inside = e.key === 'Tab' && (field === 'name') !== e.shiftKey;
    if ((e.key !== 'Enter' && e.key !== 'Tab') || inside) return;
    e.preventDefault();
    const next = this.renaming + (e.shiftKey ? -1 : 1);
    this.commitRename();
    if (e.key === 'Tab' && next >= 0 && next < this.grid.cols.length) {
      this.startRename(next, e.shiftKey ? 'trans' : 'name');
    }
  }

  renameOut(e) {
    if (!e.currentTarget.contains(e.relatedTarget)) this.commitRename();
  }

  toggleGroup(i) {
    const g = this.grid;
    const id = g.cols[i].id;
    this.commit({ ...g, group_col: g.group_col === id ? null : id });
  }

  ensureColVisible(i) {
    const xs = this.colXs();
    const [l, r] = [xs[i], xs[i + 1]];
    if (l < GUTTER_W + 8) this.panBy(GUTTER_W + 8 - l, 0);
    else if (r > this.vp[0] - 8) this.panBy(Math.max(this.vp[0] - 8 - r, GUTTER_W + 8 - l), 0);
  }

  hitLayout(sp) {
    const g = this.grid;
    const P = G.points(g);
    const m = g.rows.length;
    const n = g.cols.length;
    const S = (p) => this.toScreen(p);
    const away = (p) => Math.hypot(p[0] - sp[0], p[1] - sp[1]);
    let best = null;
    let bestD = Infinity;
    const offer = (d, limit, bias, hit) => {
      if (d <= limit && d - bias < bestD) { best = hit; bestD = d - bias; }
    };
    g.frame.forEach((c, i) => offer(away(S(c)), 12, 6, { kind: 'corner', i }));
    for (let k = 1; k < n; k++) {
      const [a, b] = [S(P[0][k]), S(P[m][k])];
      offer(away(a), 9, 3, { kind: 'col', k, end: 0 });
      offer(away(b), 9, 3, { kind: 'col', k, end: 1 });
      offer(G.distToSeg(sp, a, b), 5, 0, { kind: 'col', k, end: -1 });
    }
    for (let j = 1; j < m; j++) {
      const [a, b] = [S(P[j][0]), S(P[j][n])];
      offer(away(a), 9, 3, { kind: 'row', k: j, end: 0 });
      offer(away(b), 9, 3, { kind: 'row', k: j, end: 1 });
      offer(G.distToSeg(sp, a, b), 5, 0, { kind: 'row', k: j, end: -1 });
    }
    const F = g.frame.map(S);
    for (let i = 0; i < 4; i++) offer(G.distToSeg(sp, F[i], F[(i + 1) % 4]), 6, -1, { kind: 'edge', i });
    return best;
  }

  layoutCursor(sp) {
    if (!this.grid) return 'crosshair';
    const hit = this.hitLayout(sp);
    if (hit) {
      if (hit.kind === 'corner' || hit.kind === 'edge' || hit.end >= 0) return 'move';
      return hit.kind === 'col' ? 'ew-resize' : 'ns-resize';
    }
    if (this.tool !== 'select' && G.locate(this.grid, this.toNorm(sp))) return 'crosshair';
    return 'grab';
  }

  dragTo(sp) {
    const { hit, p0, frame0 } = this.gesture;
    const g = this.grid;
    const p = this.toNorm(sp);
    if (hit.kind === 'corner') {
      this.grid = { ...g, frame: g.frame.map((c, i) => (i === hit.i ? G.clamp01(p) : c)) };
    } else if (hit.kind === 'edge') {
      const [dx, dy] = [p[0] - p0[0], p[1] - p0[1]];
      const ends = [hit.i, (hit.i + 1) % 4];
      this.grid = {
        ...g,
        frame: frame0.map((c, i) => (ends.includes(i) ? G.clamp01([c[0] + dx, c[1] + dy]) : c)),
      };
    } else {
      const pos = hit.end < 0 ? G.slide(g, hit.kind, hit.k, p) : G.pivot(g, hit.kind, hit.k, hit.end, p);
      this.grid = hit.kind === 'col'
        ? { ...g, cols: g.cols.map((c, i) => (i === hit.k ? { ...c, u: pos } : c)) }
        : { ...g, rows: g.rows.map((r, j) => (j === hit.k ? { ...r, v: pos } : r)) };
    }
  }

  endDraw() {
    const r = this.drawRect;
    this.drawRect = null;
    if (!r) return;
    const [x0, x1] = [r[0][0], r[1][0]].sort((a, b) => a - b);
    const [y0, y1] = [r[0][1], r[1][1]].sort((a, b) => a - b);
    if (x1 - x0 < 0.01 || y1 - y0 < 0.01) return;
    this.commit({
      frame: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
      cols: [{ id: uid(), name: '', u: [0, 0] }],
      rows: [{ id: uid(), v: [0, 0] }],
      first_line: 1,
      group_col: null,
      cells: {},
    });
    this.tool = 'col';
  }

  async openCopy() {
    try {
      const r = await api(`${API}/list`);
      this.copyList = r.items.filter((t) => t.table && !(t.doc_id === this.doc && t.page === this.page));
      this.dlg = 'copy';
    } catch (e) {
      this.say(why(e), true);
    }
  }

  async copyFrom(t) {
    this.dlg = null;
    try {
      const src = (await api(`${API}/doc/${t.doc_id}/page/${t.page}`)).grid;
      if (!src) return;
      this.commit({ ...src, frame: this.grid?.frame || src.frame, cells: {}, trans: {} });
      this.tool = 'select';
    } catch (e) {
      this.say(why(e), true);
    }
  }

  setMode(mode) {
    if (mode === this.mode) return;
    this.commitEdit();
    this.commitRename();
    this.saveNote();
    this.mode = mode;
    this.hover = null;
    this.noteHover = null;
    this.placing = false;
    this.picked = null;
    this.pointer = '';
  }

  // ---- pointer and keys

  onDown(e) {
    if ((e.button !== 0 && e.button !== 1) || !this.imgSize) return;
    this.viewport.setPointerCapture(e.pointerId);
    const sp = this.screenPoint(e);
    this.gesture = { start: sp, last: sp, moved: false, kind: 'pan' };
    this.commitEdit();
    this.commitRename();
    this.saveNote();
    if (e.button === 1 || this.busy) return;
    if (this.mode === 'view') {
      const note = this.noteAt(sp);
      if (note) Object.assign(this.gesture, { kind: 'note', note });
      else this.gesture.kind = this.placing ? 'place' : 'click';
      return;
    }
    const g = this.grid;
    const p = this.toNorm(sp);
    if (!g) {
      Object.assign(this.gesture, { kind: 'draw', origin: G.clamp01(p) });
      return;
    }
    const hit = this.hitLayout(sp);
    if (hit) {
      this.beginEdit();
      Object.assign(this.gesture, { kind: 'drag', hit, p0: p, frame0: g.frame });
      this.picked = hit.kind === 'col' || hit.kind === 'row' ? { kind: hit.kind, k: hit.k } : null;
      return;
    }
    const at = G.locate(g, p);
    if (at && this.tool !== 'select') {
      this.beginEdit();
      const k = this.addLine(this.tool, this.tool === 'col' ? at.col : at.row, p);
      Object.assign(this.gesture, { kind: 'drag', hit: { kind: this.tool, k, end: -1 } });
      this.picked = { kind: this.tool, k };
      return;
    }
    this.picked = null;
  }

  onMove(e) {
    if (!this.imgSize) return;
    const sp = this.screenPoint(e);
    const gs = this.gesture;
    if (!gs) {
      this.hoverAt(sp);
      return;
    }
    const [dx, dy] = [sp[0] - gs.last[0], sp[1] - gs.last[1]];
    gs.last = sp;
    if (!gs.moved && Math.hypot(sp[0] - gs.start[0], sp[1] - gs.start[1]) > 3) gs.moved = true;
    if (gs.kind === 'drag') this.dragTo(sp);
    else if (gs.kind === 'draw') this.drawRect = [gs.origin, G.clamp01(this.toNorm(sp))];
    else if (gs.kind === 'note') {
      if (!gs.moved) return;
      const [x, y] = G.clamp01(this.toNorm(sp));
      gs.note = { ...gs.note, x, y };
      this.swapNote(gs.note);
      this.noteHover = null;
    } else if (gs.moved) {
      this.panBy(dx, dy);
      this.pointer = 'grabbing';
    }
  }

  onUp(e, cancelled = false) {
    const gs = this.gesture;
    this.gesture = null;
    if (!gs) return;
    if (gs.kind === 'click' && !gs.moved && !cancelled) this.clickAt(gs.start, e);
    else if (gs.kind === 'place' && !gs.moved && !cancelled) this.placeAt(gs.start);
    else if (gs.kind === 'note' && !cancelled) {
      if (gs.moved) this.moveNote(gs.note);
      else this.noteEdit = { ...gs.note };
    } else if (gs.kind === 'drag') this.endEdit();
    else if (gs.kind === 'draw') this.endDraw();
    this.pointer = '';
    if (!cancelled) this.hoverAt(this.screenPoint(e));
  }

  clickAt(sp, e) {
    const at = this.grid && !this.overChrome(sp) ? G.locate(this.grid, this.toNorm(sp)) : null;
    if (!at) {
      this.cur = null;
      this.selectRows([]);
      return;
    }
    this.cur = at;
    this.pickRow(at.row, e);
  }

  overChrome([x, y]) { return !!this.grid && (x < GUTTER_W || y < HEAD_H); }

  focusCell() { return this.draft ? this.cur : this.hover ?? this.cur; }

  hoverAt(sp) {
    if (this.mode === 'layout') {
      this.pointer = this.layoutCursor(sp);
      return;
    }
    const note = this.noteAt(sp);
    this.noteHover = note?.id ?? null;
    this.pointer = note ? 'pointer' : this.placing ? 'crosshair' : '';
    const at = !note && this.grid && !this.overChrome(sp) ? G.locate(this.grid, this.toNorm(sp)) : null;
    if (at?.row !== this.hover?.row || at?.col !== this.hover?.col) this.hover = at;
  }

  onWheel(e) {
    if (!this.imgSize) return;
    e.preventDefault();
    const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? this.vp[1] : 1;
    const sp = this.screenPoint(e);
    if (e.ctrlKey || e.metaKey) this.zoomAt(Math.exp(-G.clamp(e.deltaY * unit, -60, 60) * 0.01), sp);
    else this.panBy(-e.deltaX * unit, -e.deltaY * unit);
    if (!this.gesture) this.hoverAt(sp);
  }

  onDouble(e) {
    const sp = this.screenPoint(e);
    if (this.mode !== 'view' || !this.cur || this.overChrome(sp) || this.noteAt(sp) || this.noteEdit) return;
    this.startEdit();
  }

  key(e) {
    if (this.dlg) return;
    if (e.key === 'Escape' && this.placing) {
      this.placing = false;
      this.pointer = '';
      return;
    }
    const k = e.key;
    const mod = e.metaKey || e.ctrlKey;
    if (mod && !e.altKey && (k === 'z' || k === 'Z' || k === 'y')) {
      if (editable(e.target)) return;
      e.preventDefault();
      if (k === 'y' || e.shiftKey) this.redo();
      else this.undo();
      return;
    }
    if (editable(e.target) || !this.grid || this.busy) return;
    if ((k === 'Enter' || k === ' ') && e.target.closest?.('button, a, summary')) return;
    if (this.mode === 'layout') {
      this.layoutKey(e);
      return;
    }
    if (mod && k === 'a') {
      e.preventDefault();
      this.selectRows(this.grid.rows.map((_, j) => j));
      return;
    }
    if (mod || e.altKey) return;
    const arrows = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    if (k === 'Escape') {
      this.cur = null;
      this.selectRows([]);
    } else if (!this.cur) {
      if (k in arrows) {
        e.preventDefault();
        this.moveTo({ row: 0, col: 0 });
      }
    } else if (k in arrows || k === 'Tab') {
      e.preventDefault();
      const next = k === 'Tab' ? this.step(this.cur, 0, e.shiftKey ? -1 : 1, true)
        : this.step(this.cur, ...arrows[k], false);
      if (next) this.moveTo(next);
    } else if (k === 'Enter' || k === 'F2') {
      e.preventDefault();
      this.startEdit();
    } else if (k === 'Backspace' || k === 'Delete') {
      e.preventDefault();
      this.setCell(this.cur.row, this.cur.col, Object.fromEntries(this.fields.map((f) => [f, ''])));
    } else if (k.length === 1) {
      e.preventDefault();
      this.startEdit(k);
    }
  }

  layoutKey(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const tools = { v: 'select', c: 'col', r: 'row' };
    const k = e.key.toLowerCase();
    if (k in tools) this.tool = tools[k];
    else if ((e.key === 'Delete' || e.key === 'Backspace') && this.picked) {
      e.preventDefault();
      this.deletePicked();
    } else if (e.key === 'Escape') this.picked = null;
  }

  // ---- rendering

  render() {
    if (this.loadError) return html`<p class="error-text">${this.loadError}</p>`;
    if (!this.info) return html`<p>${spinner}</p>`;
    const i = this.info;
    return html`
      ${this.renderBar()}
      ${this.mode === 'layout' ? this.renderLayoutBar() : nothing}
      <div class="tbl-viewport ${this.mode}" style="cursor:${this.pointer || 'default'}"
        @pointerdown=${(e) => this.onDown(e)} @pointermove=${(e) => this.onMove(e)}
        @pointerup=${(e) => this.onUp(e)} @pointercancel=${(e) => this.onUp(e, true)}
        @pointerleave=${() => { if (!this.gesture) { this.hover = null; this.noteHover = null; } }}
        @dblclick=${(e) => this.onDouble(e)}
        @wheel=${{ handleEvent: (e) => this.onWheel(e), passive: false }}>
        ${i.error ? html`<p class="error-text tbl-msg">${i.error}</p>` : html`
          <div class="tbl-stage" style="transform:translate(${this.view.tx}px,${this.view.ty}px) scale(${this.view.s});
            visibility:${this.imgSize ? 'visible' : 'hidden'}">
            <img src="${this.gridUrl}/image?v=${i.version}" alt="" draggable="false"
              @load=${(e) => this.imgLoaded(e)}
              @error=${() => { this.imgError = 'The page image could not be loaded'; }}>
            ${this.imgSize ? this.renderSvg() : nothing}
          </div>
          ${this.imgError ? html`<p class="error-text tbl-msg">${this.imgError}</p>`
            : this.imgSize ? nothing : html`<div class="tbl-msg">${spinner}</div>`}
          ${this.grid && this.imgSize && this.vp[0] ? html`
            ${this.renderHead()}
            ${this.renderGutter()}
            <div class="tbl-corner"></div>
            ${this.renderTip()}
            ${this.renderEditor()}
            ${this.renderRename()}` : nothing}
          ${this.imgSize && this.vp[0] ? html`${this.renderNoteTip()}${this.renderNoteEditor()}` : nothing}`}
      </div>
      ${this.renderDialog()}
      <div class="snackbar ${this.toast ? 'active' : ''} ${this.toast?.failed ? 'error' : ''}"
        role="status" aria-live="polite">
        ${this.toast ? html`<i>${this.toast.failed ? 'error' : 'check_circle'}</i>
          <span class="max">${this.toast.msg}</span>` : nothing}
      </div>`;
  }

  iconBtn(icon, label, onClick, disabled = false) {
    return html`<button class="circle transparent" aria-label=${label} title=${label}
      ?disabled=${disabled} @click=${onClick}><i>${icon}</i></button>`;
  }

  renderBar() {
    const i = this.info;
    const g = this.grid;
    const busy = this.busy === 'transcribe';
    const rows = this.sel.size;
    return html`<nav class="tbl-bar">
      <h6 class="small tbl-title max">${i.title}</h6>
      ${i.pages > 1 ? html`<nav class="tbl-pages">
        ${this.iconBtn('chevron_left', 'Previous page', () => this.goPage(this.page - 1), this.page <= 1)}
        <span class="small-text">${this.page} / ${i.pages}</span>
        ${this.iconBtn('chevron_right', 'Next page', () => this.goPage(this.page + 1), this.page >= i.pages)}
      </nav>` : nothing}
      ${this.saveError ? html`<span class="error-text small-text tbl-save-error"><i class="small">error</i>
        ${this.saveError}</span>` : nothing}
      <nav class="group connected">
        <button class="${this.mode === 'view' ? 'active' : ''}" ?disabled=${!!this.busy}
          @click=${() => this.setMode('view')}><i>visibility</i><span>View</span></button>
        <button class="${this.mode === 'layout' ? 'active' : ''}" ?disabled=${!!this.busy}
          @click=${() => this.setMode('layout')}><i>grid_on</i><span>Layout</span></button>
      </nav>
      ${g ? html`<nav class="group connected">${LANGS.map(([id, label]) => html`<button
        class="${this.lang === id ? 'active' : ''}" @click=${() => this.setLang(id)}>${label}</button>`)}</nav>` : nothing}
      ${this.mode === 'view' && this.imgSize ? html`<button class="${this.placing ? '' : 'border'}"
        aria-pressed=${this.placing ? 'true' : 'false'} @click=${() => { this.placing = !this.placing; }}>
        <i>add_comment</i><span>Note</span></button>` : nothing}
      <nav class="tbl-icons">
        ${this.iconBtn('undo', 'Undo', () => this.undo(), !this.past.length || !!this.busy)}
        ${this.iconBtn('redo', 'Redo', () => this.redo(), !this.future.length || !!this.busy)}
        ${this.iconBtn('zoom_out', 'Zoom out', () => this.zoomCenter(1 / 1.25), !this.imgSize)}
        ${this.iconBtn('fit_screen', 'Fit', () => this.fit(), !this.imgSize)}
        ${this.iconBtn('zoom_in', 'Zoom in', () => this.zoomCenter(1.25), !this.imgSize)}
      </nav>
      ${g && i.transcribe ? html`<button class="border" ?disabled=${!!this.busy || this.conflict}
        @click=${() => this.transcribe()}>
        ${busy ? html`<progress class="circle small"></progress>` : html`<i>auto_awesome</i>`}
        <span>${busy ? 'Transcribing…' : rows ? `Transcribe ${rows} line${rows === 1 ? '' : 's'}` : 'Transcribe'}</span>
      </button>` : nothing}
      ${g && rows && this.mode === 'view' ? html`<button class="border" ?disabled=${!!this.busy}
        @click=${() => this.clearRows()}><i>backspace</i><span>Clear</span></button>` : nothing}
      ${g && this.rev ? html`<a class="button circle transparent" href="${this.gridUrl}/export.csv" download
        aria-label="Download CSV" title="Download CSV"><i>download</i></a>` : nothing}
      ${i.paperless_url ? html`<a class="button circle transparent" href=${i.paperless_url} target="_blank"
        rel="noopener" aria-label="Open in Paperless" title="Open in Paperless"><i>open_in_new</i></a>` : nothing}
    </nav>`;
  }

  renderLayoutBar() {
    const g = this.grid;
    const tool = (id, icon, label, keyName) => html`<button class="${this.tool === id ? 'active' : ''}"
      ?disabled=${!g} title="${label} (${keyName})" @click=${() => { this.tool = id; }}>
      <i>${icon}</i><span>${label}</span></button>`;
    const empty = !g || !Object.keys(g.cells).length;
    return html`<nav class="tbl-bar tbl-layout">
      <nav class="group connected">
        ${tool('select', 'arrow_selector_tool', 'Select', 'V')}
        ${tool('col', 'view_column', 'Column', 'C')}
        ${tool('row', 'table_rows', 'Row', 'R')}
      </nav>
      ${g ? html`
        <div class="field label border small no-margin tbl-num">
          <input type="number" placeholder=" " .value=${String(g.first_line)}
            @change=${(e) => this.setFirstLine(e.target.value)}
            @keydown=${(e) => { if (e.key === 'Enter') this.setFirstLine(e.target.value); }}>
          <label>First line</label>
        </div>
        <div class="field label border small no-margin tbl-num">
          <input type="number" min="1" max="400" placeholder=" " .value=${String(this.linesDraft ?? g.rows.length)}
            @input=${(e) => { this.linesDraft = e.target.value; }}
            @keydown=${(e) => { if (e.key === 'Enter') this.distribute(e.target.value); }}>
          <label>Lines</label>
        </div>
        <button class="border" @click=${() => this.distribute(this.linesDraft ?? g.rows.length)}>
          <i>format_line_spacing</i><span>Distribute</span></button>
        ${this.picked ? html`<button class="border" @click=${() => this.deletePicked()}>
          <i>delete</i><span>Delete line</span></button>` : nothing}` : nothing}
      <div class="max"></div>
      ${empty ? html`<button class="border" @click=${() => this.openCopy()}>
        <i>content_copy</i><span>Copy layout</span></button>` : nothing}
      ${g ? html`<button class="border error-text" @click=${() => { this.dlg = 'delete'; }}>
        <i>delete_forever</i><span>Delete table</span></button>` : nothing}
    </nav>`;
  }

  renderSvg() {
    const [w, h] = this.imgSize;
    const px = 1 / this.view.s;
    const g = this.grid;
    const xy = (p) => `${p[0] * w},${p[1] * h}`;
    const poly = (pts, cls, sw = 0) => svg`<polygon class=${cls} points=${pts.map(xy).join(' ')}
      stroke-width=${sw * px}></polygon>`;
    const out = [];
    if (this.drawRect) {
      const [[x0, y0], [x1, y1]] = this.drawRect;
      out.push(poly([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], 't-draw', 1.5));
    }
    if (g) out.push(this.mode === 'view' ? this.viewMarks(poly) : this.layoutMarks(poly, xy, px));
    if (this.mode === 'view') out.push(this.noteMarks(px));
    return html`<svg class="tbl-svg" width=${w} height=${h} viewBox="0 0 ${w} ${h}">${out}</svg>`;
  }

  noteMarks(px) {
    const [w, h] = this.imgSize;
    const ne = this.noteEdit;
    const dot = (n, on) => svg`<circle class="t-note ${on ? 'on' : ''}" cx=${n.x * w} cy=${n.y * h}
      r=${(on ? 8 : 6.5) * px} stroke-width=${2 * px}></circle>`;
    const marks = this.notes.map((n) => dot(n, n.id === this.noteHover || n.id === ne?.id));
    if (ne && !ne.id) marks.push(dot(ne, true));
    return marks;
  }

  viewMarks(poly) {
    const g = this.grid;
    const P = G.points(g);
    const n = g.cols.length;
    const band = (j) => [P[j][0], P[j][n], P[j + 1][n], P[j + 1][0]];
    const cell = (j, i) => [P[j][i], P[j][i + 1], P[j + 1][i + 1], P[j + 1][i]];
    const out = [];
    const focus = this.focusCell()?.row;
    const group = focus === undefined ? null : this.groupOf(focus);
    if (group) for (let j = group[0]; j < group[1]; j++) out.push(poly(band(j), 't-group'));
    g.rows.forEach((r, j) => { if (this.sel.has(r.id)) out.push(poly(band(j), 't-sel')); });
    if (this.hover) {
      out.push(poly(band(this.hover.row), 't-hover'));
      out.push(poly(cell(this.hover.row, this.hover.col), 't-cell', 2));
    }
    if (this.cur) out.push(poly(cell(this.cur.row, this.cur.col), 't-cursor', 2.5));
    return out;
  }

  layoutMarks(poly, xy, px) {
    const g = this.grid;
    const P = G.points(g);
    const m = g.rows.length;
    const n = g.cols.length;
    const pk = this.picked;
    const line = (a, b, cls, sw) => {
      const [x1, y1] = xy(a).split(',');
      const [x2, y2] = xy(b).split(',');
      return svg`<line class=${cls} x1=${x1} y1=${y1} x2=${x2} y2=${y2} stroke-width=${sw * px}></line>`;
    };
    const dot = (p, r, cls) => {
      const [cx, cy] = xy(p).split(',');
      return svg`<circle class=${cls} cx=${cx} cy=${cy} r=${r * px} stroke-width=${1.5 * px}></circle>`;
    };
    const out = [poly(g.frame, 't-frame', 2)];
    for (let k = 1; k < n; k++) {
      const on = pk?.kind === 'col' && pk.k === k;
      out.push(line(P[0][k], P[m][k], `t-col ${on ? 't-picked' : ''}`, on ? 3 : 1.5));
    }
    for (let j = 1; j < m; j++) {
      const on = pk?.kind === 'row' && pk.k === j;
      out.push(line(P[j][0], P[j][n], `t-row ${on ? 't-picked' : ''}`, on ? 3 : 1));
    }
    for (let k = 1; k < n; k++) out.push(dot(P[0][k], 3.5, 't-end'), dot(P[m][k], 3.5, 't-end'));
    for (let j = 1; j < m; j++) out.push(dot(P[j][0], 3.5, 't-end'), dot(P[j][n], 3.5, 't-end'));
    for (const c of g.frame) out.push(dot(c, 6, 't-handle'));
    return out;
  }

  renderHead() {
    const g = this.grid;
    const xs = this.colXs();
    const hot = this.mode === 'view' ? this.focusCell()?.col : this.renaming;
    return html`<div class="tbl-head" @pointerdown=${stop}>
      ${g.cols.map((c, i) => {
        const [l, r] = [xs[i], xs[i + 1]];
        if (r <= GUTTER_W || l >= this.vp[0] || r - l < 3) return nothing;
        const [top, sub] = this.colNames(c);
        return html`<div class="tbl-col ${i === hot ? 'hot' : ''}" style="left:${l}px;width:${r - l}px"
          title=${[c.name, c.trans].filter(Boolean).join(' / ') || nothing}
          @click=${() => { if (this.mode === 'layout') this.startRename(i); }}>
          <span>${top}</span>${sub ? html`<span class="tbl-sub">${sub}</span>` : nothing}</div>`;
      })}
    </div>`;
  }

  renderGutter() {
    const g = this.grid;
    const ys = this.rowYs();
    const hot = this.mode === 'view' ? this.focusCell()?.row : null;
    const minH = Math.min(...ys.slice(1).map((y, j) => y - ys[j]));
    const every = STEPS.find((s) => s * minH >= 12) || 200;
    return html`<div class="tbl-gutter" @pointerdown=${stop}>
      ${g.rows.map((r, j) => {
        const [t, b] = [ys[j], ys[j + 1]];
        if (b <= HEAD_H || t >= this.vp[1]) return nothing;
        const label = g.first_line + j;
        const on = this.sel.has(r.id);
        const show = j === hot || on || label % every === 0;
        return html`<div class="tbl-line ${j === hot ? 'hot' : ''} ${on ? 'sel' : ''}"
          style="top:${t}px;height:${b - t}px"
          @click=${(e) => { if (this.mode === 'view') { this.cur = null; this.pickRow(j, e); } }}>
          ${show ? html`<span>${label}</span>` : nothing}</div>`;
      })}
    </div>`;
  }

  renderTip() {
    if (this.mode !== 'view' || !this.hover || this.draft || this.placing || this.gesture?.moved) return nothing;
    const { row, col } = this.hover;
    const lines = this.tipLines(row, col);
    if (!lines.length) return nothing;
    const b = this.cellBox(row, col);
    const flip = b.r + 12 + 280 > this.vp[0];
    const x = flip ? `right:${this.vp[0] - b.l + 12}px` : `left:${b.r + 12}px`;
    return html`<div class="tbl-tip ${flip ? 'flip' : ''}" style="${x};top:${(b.t + b.b) / 2}px">
      ${lines.map(([name, value], i) => html`<div class=${i ? 'tbl-sub' : ''}>${name
        ? html`<span>${name}${value ? ': ' : ''}</span>` : nothing}${value ? html`<strong>${value}</strong>` : nothing}</div>`)}
    </div>`;
  }

  renderNoteTip() {
    if (this.mode !== 'view' || this.noteEdit || this.gesture?.moved) return nothing;
    const n = this.notes.find((x) => x.id === this.noteHover);
    if (!n) return nothing;
    const [x, y] = this.toScreen([n.x, n.y]);
    const flip = x + 14 + 320 > this.vp[0];
    const pos = flip ? `right:${this.vp[0] - x + 14}px` : `left:${x + 14}px`;
    return html`<div class="tbl-tip tbl-note-tip ${flip ? 'flip' : ''}" style="${pos};top:${y}px">
      <div class="tbl-note-text">${n.text}</div>
    </div>`;
  }

  renderNoteEditor() {
    const ne = this.noteEdit;
    if (!ne || this.mode !== 'view') return nothing;
    const [x, y] = this.toScreen([ne.x, ne.y]);
    const width = Math.min(300, this.vp[0] - 16);
    const left = x + 16 + width < this.vp[0] ? x + 16 : Math.max(8, x - 16 - width);
    const top = G.clamp(y - 24, 8, Math.max(8, this.vp[1] - 190));
    const keep = (e) => e.preventDefault();
    return html`<div class="tbl-pop tbl-note-edit" style="left:${left}px;top:${top}px;width:${width}px"
      @pointerdown=${stop} @dblclick=${stop} @wheel=${stop} @focusout=${(e) => this.noteOut(e)}>
      <div class="field textarea border small no-margin">
        <textarea rows="4" .value=${ne.text} @input=${(e) => { ne.text = e.target.value; }}
          @keydown=${(e) => this.noteKey(e)}></textarea>
      </div>
      <nav class="no-margin">
        <span class="max small-text secondary-text">${ne.id ? when(ne.updated_at) : ''}</span>
        ${ne.id ? html`<button class="circle transparent" aria-label="Delete note" title="Delete note"
          @mousedown=${keep} @click=${() => this.deleteNote(ne.id)}><i>delete</i></button>` : nothing}
        <button @mousedown=${keep} @click=${() => this.saveNote()}>Done</button>
      </nav>
    </div>`;
  }

  renderEditor() {
    if (!this.draft || !this.cur || this.mode !== 'view') return nothing;
    const { row, col } = this.cur;
    const b = this.cellBox(row, col);
    const fields = this.fields;
    const width = Math.min(Math.max(b.r - b.l, 240), this.vp[0] - 16);
    const height = fields.length * 56 + 12;
    const left = G.clamp(b.l, 8, this.vp[0] - width - 8);
    const top = b.b + height + 8 < this.vp[1] ? b.b + 6 : Math.max(HEAD_H + 4, b.t - height - 6);
    const c = this.grid.cols[col];
    const label = (f) => (f === 'orig' ? c.name || `Column ${col + 1}` : c.trans || 'Translation');
    return html`<div class="tbl-pop tbl-editor" style="left:${left}px;top:${top}px;width:${width}px"
      @pointerdown=${stop} @dblclick=${stop} @wheel=${stop} @focusout=${(e) => this.editorOut(e)}>
      ${fields.map((f) => html`<div class="field label border small no-margin">
        <input type="text" placeholder=" " data-field=${f} .value=${this.draft[f]}
          @input=${(e) => { this.draft[f] = e.target.value; }}
          @keydown=${(e) => this.editorKey(e, f)}>
        <label>${label(f)} · ${this.grid.first_line + row}</label>
      </div>`)}
    </div>`;
  }

  renderRename() {
    const i = this.renaming;
    if (i === null || this.mode !== 'layout') return nothing;
    const g = this.grid;
    const xs = this.colXs();
    const width = 280;
    const left = G.clamp(xs[i], GUTTER_W + 4, this.vp[0] - width - 8);
    const group = g.group_col === g.cols[i].id;
    const input = (field, label) => html`<div class="field label border small no-margin">
      <input type="text" placeholder=" " data-field=${field} .value=${this.renameDraft[field]}
        @input=${(e) => { this.renameDraft[field] = e.target.value; }}
        @keydown=${(e) => this.renameKey(e, field)}>
      <label>${label}</label>
    </div>`;
    return html`<div class="tbl-pop tbl-rename" style="left:${left}px;top:${HEAD_H + 6}px;width:${width}px"
      @pointerdown=${stop} @dblclick=${stop} @wheel=${stop} @focusout=${(e) => this.renameOut(e)}>
      <div class="tbl-rename-fields">
        ${input('name', `Column ${i + 1}`)}
        ${input('trans', 'Translation')}
      </div>
      <button class="circle ${group ? 'fill' : 'transparent'}" aria-pressed=${group ? 'true' : 'false'}
        title="Household" aria-label="Household" @mousedown=${(e) => e.preventDefault()}
        @click=${() => this.toggleGroup(i)}><i>family_restroom</i></button>
    </div>`;
  }

  renderDialog() {
    let body = nothing;
    if (this.dlg === 'delete') {
      body = html`<h5>Delete this table?</h5>
        <nav class="right-align">
          <button class="border" @click=${() => { this.dlg = null; }}>Cancel</button>
          <button class="error" @click=${() => { this.dlg = null; this.picked = null; this.commit(null); this.tool = 'select'; }}>
            Delete</button>
        </nav>`;
    } else if (this.dlg === 'copy') {
      body = html`<h5>Copy layout</h5>
        ${this.copyList.length ? html`<ul class="list tbl-copy-list">
          ${this.copyList.map((t) => html`<li class="wave" @click=${() => this.copyFrom(t)}>
            <img class="tbl-thumb" src="${API}/thumb/${t.doc_id}" alt="" loading="lazy">
            <div class="max">
              <div>${t.title || `#${t.doc_id}`}</div>
              <div class="small-text secondary-text">Page ${t.page} · ${t.columns} column${t.columns === 1 ? '' : 's'}
                · ${t.lines} line${t.lines === 1 ? '' : 's'}</div>
            </div>
          </li>`)}
        </ul>` : html`<p class="secondary-text">No other tables</p>`}
        <nav class="right-align">
          <button class="border" @click=${() => { this.dlg = null; }}>Cancel</button>
        </nav>`;
    }
    return html`<dialog class="tbl-dialog" @close=${() => { this.dlg = null; }}>${body}</dialog>`;
  }
}
customElements.define('table-viewer', TableViewer);
