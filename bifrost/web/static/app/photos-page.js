import { BifrostElement, html, nothing, api, post, btn, field, selectField, spinner, statusLine, searchMenu } from './core.js';

const MODES = [['recent', 'Recent', 'schedule'], ['tagged', 'Tagged for sync', 'sell'], ['synced', 'In Gramps', 'check_circle']];
const PRECISION = [['exact', 'Exact day'], ['month', 'Month'], ['year', 'Year']];
const MODIFIER = [['regular', 'Regular'], ['about', 'About'], ['before', 'Before'], ['after', 'After']];
const QUALITY = [['regular', 'Regular'], ['estimated', 'Estimated'], ['calculated', 'Calculated']];

function parseDate(text) {
  const m = /^\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?\s*$/.exec(text || '');
  if (!m) return null;
  const mo = m[2] ? m[2].padStart(2, '0') : '01';
  const d = m[3] ? m[3].padStart(2, '0') : '01';
  if (+mo < 1 || +mo > 12 || +d < 1 || +d > 31) return null;
  return { value: `${m[1]}-${mo}-${d}`, precision: m[3] ? 'exact' : m[2] ? 'month' : 'year' };
}

function dateText(d) {
  if (!d) return '';
  return d.precision === 'year' ? d.value.slice(0, 4) : d.precision === 'month' ? d.value.slice(0, 7) : d.value;
}

function grampsDate(d) {
  if (!d) return '';
  const [y, m] = d.value.split('-');
  let prec = d.precision;
  if (d.modifier === 'about' && prec === 'exact') prec = 'month';
  const date = prec === 'year' ? y : prec === 'month' ? `${y}-${m}` : d.value;
  const mod = { before: 'Before ', after: 'After ', about: 'About ' }[d.modifier] || '';
  const qual = { estimated: 'Est. ', calculated: 'Calc. ' }[d.quality] || '';
  return `${qual}${mod}${date}`;
}

function placeItem(p) {
  return { id: p.gramps_id, label: p.hierarchy.join(', ') || p.name, sub: p.gramps_id, mono: true,
    icon: p.known === false ? 'location_off' : p.tagged ? 'location_on' : 'map' };
}

function formFrom(rec) {
  const fresh = !rec.sync.media && !rec.gramps;
  return {
    title: rec.title || '',
    dateText: dateText(rec.date),
    date: rec.date ? { value: rec.date.value, precision: rec.date.precision, modifier: rec.date.modifier, quality: rec.date.quality } : null,
    place: rec.place ? placeItem(rec.place) : null,
    notes: rec.notes || '',
    sync: fresh
      ? { media: true, title: true, date: true, note: false }
      : { media: rec.sync.media, title: rec.sync.title, date: rec.sync.date, note: rec.sync.note },
  };
}

function menuUp(e) {
  const r = e?.currentTarget?.getBoundingClientRect?.();
  if (!r) return false;
  return window.innerHeight - r.bottom < 24 * 16 && r.top > window.innerHeight / 2;
}

function sizeText(m) {
  const dims = m.width ? `${m.width}×${m.height}` : '';
  const mb = m.size ? `${(m.size / 1048576).toFixed(1)} MB` : '';
  return [dims, mb].filter(Boolean).join(' · ');
}

function cardFrom(rec) {
  return { asset_id: rec.asset_id, filename: rec.filename, title: rec.title, date: rec.date?.value || '',
    type: rec.type, thumb: rec.thumb, gramps_id: rec.gramps?.gramps_id || null,
    versions: rec.versions?.members?.length || 1, is_child: false, missing: false };
}

function payload(f) {
  return {
    title: f.title,
    notes: f.notes,
    place_gramps_id: f.place?.id || null,
    date: f.date ? { value: f.date.value, precision: f.date.precision, modifier: f.date.modifier, quality: f.date.quality } : null,
    sync: f.sync,
  };
}

class PhotosPage extends BifrostElement {
  static properties = {
    config: { state: true },
    mode: { state: true },
    q: { state: true },
    qDraft: { state: true },
    person: { state: true },
    people: { state: true },
    personQ: { state: true },
    personOpen: { state: true },
    hiPerson: { state: true },
    items: { state: true },
    nextPage: { state: true },
    loading: { state: true },
    error: { state: true },
    openId: { state: true },
    rec: { state: true },
    form: { state: true },
    recError: { state: true },
    places: { state: true },
    placeQ: { state: true },
    placeOpen: { state: true },
    hiPlace: { state: true },
    busy: { state: true },
    status: { state: true },
    verQ: { state: true },
    verOpen: { state: true },
    hiVer: { state: true },
    verItems: { state: true },
    redraw: { state: true },
    view: { state: true },
    collections: { state: true },
    colOpen: { state: true },
    colName: { state: true },
    colDesc: { state: true },
    colBusy: { state: true },
    colStatus: { state: true },
    newColName: { state: true },
    confirmDelete: { state: true },
    dragId: { state: true },
    colQ: { state: true },
    colMenuOpen: { state: true },
    hiCol: { state: true },
    colItems: { state: true },
    ecQ: { state: true },
    ecOpen: { state: true },
    hiEc: { state: true },
    up: { state: true },
    lightbox: { state: true },
    editLabel: { state: true },
    labelDraft: { state: true },
    albums: { state: true },
    albumQ: { state: true },
    albumOpen: { state: true },
    hiAlbum: { state: true },
  };

  constructor() {
    super();
    this.config = null;
    this.mode = 'recent';
    this.q = '';
    this.qDraft = '';
    this.person = null;
    this.people = null;
    this.personQ = '';
    this.personOpen = false;
    this.hiPerson = -1;
    this.items = [];
    this.nextPage = null;
    this.loading = false;
    this.error = '';
    this.openId = null;
    this.rec = null;
    this.form = null;
    this.recError = '';
    this.places = null;
    this.placeQ = '';
    this.placeOpen = false;
    this.hiPlace = -1;
    this.busy = '';
    this.status = null;
    this.verQ = '';
    this.verOpen = false;
    this.hiVer = -1;
    this.verItems = [];
    this.redraw = true;
    this.view = 'photos';
    this.collections = null;
    this.colOpen = null;
    this.colName = '';
    this.colDesc = '';
    this.colBusy = '';
    this.colStatus = null;
    this.newColName = '';
    this.confirmDelete = false;
    this.dragId = null;
    this.colQ = '';
    this.colMenuOpen = false;
    this.hiCol = -1;
    this.colItems = [];
    this.ecQ = '';
    this.ecOpen = false;
    this.hiEc = -1;
    this.up = {};
    this.lightbox = null;
    this.editLabel = null;
    this.labelDraft = '';
    this.albums = null;
    this.albumQ = '';
    this.albumOpen = false;
    this.hiAlbum = -1;
  }

  flip(name, e) { this.up = { ...this.up, [name]: menuUp(e) }; }

  connectedCallback() {
    super.connectedCallback();
    this.init();
  }

  async init() {
    try {
      this.config = await api('/photos/api/config');
    } catch (e) {
      this.config = { enabled: false };
      this.error = e.message;
      return;
    }
    if (!this.config.enabled) return;
    this.load(true);
    api('/photos/api/people').then((p) => { this.people = p; }).catch(() => { this.people = []; });
    api('/photos/api/places').then((p) => { this.places = p; }).catch(() => { this.places = []; });
    this.loadCollections();
  }

  async loadCollections() {
    try { this.collections = await api('/photos/api/collections'); } catch { this.collections = []; }
  }

  setView(v) {
    this.view = v;
    this.colStatus = null;
    if (v === 'collections') this.loadCollections();
  }

  async createCollection(name = this.newColName, description = '') {
    const wanted = (name || '').trim();
    if (!wanted || this.colBusy) return null;
    this.colBusy = 'create';
    try {
      const c = await post('/photos/api/collections', { name: wanted, description });
      this.newColName = '';
      await this.loadCollections();
      return c;
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
      return null;
    } finally {
      this.colBusy = '';
    }
  }

  async openCollection(id) {
    this.colBusy = 'open';
    this.colStatus = null;
    this.confirmDelete = false;
    this.colQ = '';
    this.colItems = [];
    this.colMenuOpen = false;
    try {
      this.colOpen = await api(`/photos/api/collections/${id}`);
      this.colName = this.colOpen.name;
      this.colDesc = this.colOpen.description || '';
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
    } finally {
      this.colBusy = '';
    }
  }

  closeCollection() {
    this.colOpen = null;
    this.colStatus = null;
    this.loadCollections();
  }

  async collectionAction(label, fn, done = '') {
    if (!this.colOpen || this.colBusy) return;
    this.colBusy = label;
    this.colStatus = null;
    try {
      const c = await fn(this.colOpen.id);
      if (c && c.items) {
        this.colOpen = c;
        this.colName = c.name;
        this.colDesc = c.description || '';
      }
      if (done) this.colStatus = { kind: 'ok', msg: done };
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
    } finally {
      this.colBusy = '';
    }
  }

  saveCollection() {
    const name = this.colName.trim();
    if (!name) { this.colStatus = { kind: 'error', msg: 'A collection needs a name' }; return; }
    this.collectionAction('save', (id) => api(`/photos/api/collections/${id}`,
      { method: 'PUT', body: JSON.stringify({ name, description: this.colDesc.trim() }) }), 'Saved');
  }

  async deleteCollection() {
    if (!this.confirmDelete) { this.confirmDelete = true; setTimeout(() => { this.confirmDelete = false; }, 4000); return; }
    const id = this.colOpen.id;
    this.colBusy = 'delete';
    try {
      await api(`/photos/api/collections/${id}`, { method: 'DELETE' });
      this.closeCollection();
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
    } finally {
      this.colBusy = '';
      this.confirmDelete = false;
    }
  }

  addToOpenCollection(it) {
    this.colMenuOpen = false;
    this.colQ = '';
    this.colItems = [];
    this.collectionAction('add', (id) => post(`/photos/api/collections/${id}/items`, { asset_ids: [it.id] }),
      `Added ${it.label}`);
  }

  removeFromOpenCollection(it) {
    this.collectionAction('remove', (id) => api(`/photos/api/collections/${id}/items/${it.asset_id}`, { method: 'DELETE' }));
  }

  async searchForCollection() {
    const q = this.colQ.trim();
    if (!q || !this.colOpen) { this.colItems = []; return; }
    try {
      const r = await api(`/photos/api/search?${new URLSearchParams({ mode: 'recent', q, page: '1' })}`);
      if (this.colQ.trim() !== q) return;
      const have = new Set(this.colOpen.items.map((i) => i.asset_id));
      this.colItems = r.items.filter((i) => !have.has(i.asset_id)).slice(0, 8)
        .map((i) => ({ id: i.asset_id, label: i.title || i.filename, sub: i.gramps_id || i.filename, thumb: i.thumb }));
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
    }
  }

  onCollectionQuery(v) {
    this.colQ = v;
    this.hiCol = -1;
    clearTimeout(this._colTimer);
    this._colTimer = setTimeout(() => this.searchForCollection(), 250);
  }

  onDragStart(e, it) {
    this.dragId = it.asset_id;
    this._orderBefore = this.colOpen.items.map((x) => x.asset_id).join(',');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', it.asset_id);
  }

  onDragOver(e, it) {
    if (!this.dragId || this.dragId === it.asset_id) return;
    e.preventDefault();
    const items = [...this.colOpen.items];
    const from = items.findIndex((x) => x.asset_id === this.dragId);
    const to = items.findIndex((x) => x.asset_id === it.asset_id);
    if (from < 0 || to < 0) return;
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    this.colOpen = { ...this.colOpen, items };
  }

  async finishDrag() {
    if (!this.dragId) return;
    this.dragId = null;
    const ids = this.colOpen.items.map((x) => x.asset_id);
    if (ids.join(',') === this._orderBefore) return;
    try {
      await api(`/photos/api/collections/${this.colOpen.id}/order`,
        { method: 'PUT', body: JSON.stringify({ asset_ids: ids }) });
      this.colStatus = { kind: 'ok', msg: 'Order saved' };
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
    }
  }

  moveItem(it, delta) {
    const items = [...this.colOpen.items];
    const from = items.findIndex((x) => x.asset_id === it.asset_id);
    const to = Math.max(0, Math.min(items.length - 1, from + delta));
    if (from === to) return;
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    this.colOpen = { ...this.colOpen, items };
    this._orderBefore = '';
    this.dragId = it.asset_id;
    this.finishDrag();
  }

  editorCollectionMatches() {
    const q = this.ecQ.trim().toLowerCase();
    const inRec = new Set((this.rec?.collections || []).map((c) => c.id));
    const items = (this.collections || []).filter((c) => !inRec.has(c.id) && (!q || c.name.toLowerCase().includes(q)))
      .slice(0, 6).map((c) => ({ id: c.id, label: c.name, sub: `${c.count} photo${c.count === 1 ? '' : 's'}`, icon: 'collections_bookmark' }));
    if (q && !(this.collections || []).some((c) => c.name.toLowerCase() === q)) {
      items.push({ id: 'new', label: `Create “${this.ecQ.trim()}”`, icon: 'add', name: this.ecQ.trim() });
    }
    return items;
  }

  async addRecToCollection(it) {
    if (!this.rec || this.busy) return;
    this.ecOpen = false;
    this.ecQ = '';
    this.busy = 'collection';
    this.status = { kind: 'busy', msg: 'Adding to the collection' };
    try {
      let id = it.id;
      if (id === 'new') {
        const created = await post('/photos/api/collections', { name: it.name, description: '' });
        id = created.id;
      }
      await post(`/photos/api/collections/${id}/items`, { asset_ids: [this.rec.asset_id] });
      const rec = await api(`/photos/api/photo/${this.rec.asset_id}`);
      this.applyRecord(rec);
      this.loadCollections();
      this.status = { kind: 'ok', msg: 'Added to the collection' };
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  async removeRecFromCollection(c) {
    if (!this.rec || this.busy) return;
    this.busy = 'collection';
    try {
      await api(`/photos/api/collections/${c.id}/items/${this.rec.asset_id}`, { method: 'DELETE' });
      const rec = await api(`/photos/api/photo/${this.rec.asset_id}`);
      this.applyRecord(rec);
      this.loadCollections();
      this.status = { kind: 'ok', msg: `Removed from ${c.name}` };
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  async load(reset = false) {
    const page = reset ? 1 : this.nextPage;
    if (!page) return;
    this.loading = true;
    this.error = '';
    if (reset) { this.items = []; this.nextPage = null; }
    const params = new URLSearchParams({ mode: this.mode, page: String(page) });
    if (this.q) params.set('q', this.q);
    if (this.person) params.set('person', this.person.id);
    try {
      const r = await api(`/photos/api/search?${params}`);
      const seen = new Set(this.items.map((i) => i.asset_id));
      this.items = [...this.items, ...r.items.filter((i) => !seen.has(i.asset_id))];
      this.nextPage = r.nextPage;
    } catch (e) {
      this.error = e.message;
    } finally {
      this.loading = false;
    }
  }

  setMode(m) { this.mode = m; this.load(true); }
  search() { this.q = this.qDraft.trim(); this.load(true); }
  clearSearch() { this.q = ''; this.qDraft = ''; this.load(true); }
  pickPerson(it) { this.person = it; this.personQ = ''; this.hiPerson = -1; this.personOpen = false; this.load(true); }
  clearPerson() { this.person = null; this.load(true); }

  personMatches() {
    const q = this.personQ.trim().toLowerCase();
    return (this.people || []).filter((p) => !q || p.name.toLowerCase().includes(q)).slice(0, 8)
      .map((p) => ({ id: p.id, label: p.name, sub: p.account_label, thumb: p.thumb }));
  }

  placeMatches() {
    const q = this.placeQ.trim().toLowerCase();
    if (!q) return [];
    const rank = (p) => {
      const name = p.name.toLowerCase();
      let r = -1;
      if (name.startsWith(q)) r = 0;
      else if (name.includes(q) || p.gramps_id.toLowerCase().includes(q)) r = 1;
      else if (p.hierarchy.join(', ').toLowerCase().includes(q)) r = 2;
      return r < 0 ? r : r + (p.tagged ? 0 : 3);
    };
    return (this.places || []).map((p) => ({ p, r: rank(p) })).filter((x) => x.r >= 0)
      .sort((a, b) => a.r - b.r).slice(0, 6).map(({ p }) => placeItem(p));
  }

  async openPhoto(id) {
    this.openId = id;
    this.rec = null;
    this.form = null;
    this.recError = '';
    this.status = null;
    this.placeQ = '';
    this.placeOpen = false;
    this.hiPlace = -1;
    this.verQ = '';
    this.verOpen = false;
    this.hiVer = -1;
    this.verItems = [];
    this.lightbox = null;
    this.editLabel = null;
    try {
      const rec = await api(`/photos/api/photo/${id}`);
      if (this.openId !== id) return;
      this.rec = rec;
      this.form = formFrom(rec);
    } catch (e) {
      this.recError = e.message;
    }
  }

  closeEditor() {
    this.openId = null;
    this.rec = null;
    this.form = null;
    this.recError = '';
    this.status = null;
  }

  updated() {
    const dlg = this.renderRoot.querySelector('dialog.photos-editor');
    if (dlg && this.openId && !dlg.open) dlg.showModal();
    const box = this.renderRoot.querySelector('dialog.photos-lightbox');
    if (box && this.lightbox && !box.open) box.showModal();
    if (this.editLabel) {
      const input = this.renderRoot.querySelector('.photos-version-label input');
      if (input && document.activeElement !== input) input.focus();
    }
  }

  startLabel(m) {
    this.editLabel = m.asset_id;
    this.labelDraft = m.label || '';
  }

  async saveLabel(m) {
    if (this.editLabel !== m.asset_id) return;
    const label = this.labelDraft.trim();
    this.editLabel = null;
    if (label === (m.label || '')) return;
    this.busy = 'label';
    try {
      const rec = await api(`/photos/api/photo/${this.rec.asset_id}/versions/${m.asset_id}/label`,
        { method: 'PUT', body: JSON.stringify({ label }) });
      this.applyRecord(rec);
      this.status = { kind: 'ok', msg: label ? 'Version note saved' : 'Version note removed' };
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  async loadAlbums() {
    if (this.albums !== null) return;
    try { this.albums = await api('/photos/api/immich-albums'); } catch (e) { this.albums = []; this.colStatus = { kind: 'error', msg: e.message }; }
  }

  albumMatches() {
    const q = this.albumQ.trim().toLowerCase();
    return (this.albums || []).filter((a) => !q || a.name.toLowerCase().includes(q)).slice(0, 8)
      .map((a) => ({ id: a.id, label: a.name || '(unnamed album)', thumb: a.thumb, icon: 'photo_album',
        sub: `${a.count} photo${a.count === 1 ? '' : 's'} · ${a.account}` }));
  }

  async importAlbum(it) {
    this.albumOpen = false;
    this.albumQ = '';
    if (this.colBusy) return;
    this.colBusy = 'import';
    this.colStatus = { kind: 'busy', msg: `Importing ${it.label}` };
    try {
      const c = await post('/photos/api/collections/import', { album_id: it.id });
      await this.loadCollections();
      this.colOpen = c;
      this.colName = c.name;
      this.colDesc = c.description || '';
      this.colStatus = { kind: 'ok', msg: `Imported ${c.added} photo${c.added === 1 ? '' : 's'} from the Immich album` };
    } catch (e) {
      this.colStatus = { kind: 'error', msg: e.message };
    } finally {
      this.colBusy = '';
    }
  }

  scrimClick(e) {
    const dlg = e.currentTarget;
    if (e.target !== dlg) return;
    const r = dlg.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dlg.close();
  }

  setForm(patch) { this.form = { ...this.form, ...patch }; }

  setDate(text) {
    const parsed = parseDate(text);
    const prev = this.form.date || { modifier: 'regular', quality: 'regular' };
    this.setForm({ dateText: text, date: parsed ? { ...prev, value: parsed.value, precision: parsed.precision } : null });
  }

  setDateField(key, value) {
    if (!this.form.date) return;
    this.setForm({ date: { ...this.form.date, [key]: value } });
  }

  setSync(key, on) { this.setForm({ sync: { ...this.form.sync, [key]: on } }); }

  pickPlace(it) {
    this.setForm({ place: it });
    this.placeQ = '';
    this.hiPlace = -1;
    this.placeOpen = false;
  }

  applyRecord(rec, replacing = null) {
    this.rec = rec;
    this.form = formFrom(rec);
    const old = replacing || rec.asset_id;
    this.openId = rec.asset_id;
    this.items = this.items.map((i) => (i.asset_id === old
      ? { ...i, ...cardFrom(rec) } : i));
  }

  async versionAction(label, fn, done) {
    if (!this.rec || this.busy) return;
    this.busy = label;
    this.status = { kind: 'busy', msg: 'Working in Immich' };
    try {
      const rec = await fn(this.rec.asset_id);
      this.applyRecord(rec);
      this.status = { kind: 'ok', msg: done };
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  async searchVersions() {
    const q = this.verQ.trim();
    if (!q || !this.rec) { this.verItems = []; return; }
    try {
      const r = await api(`/photos/api/search?${new URLSearchParams({ mode: 'recent', q, page: '1' })}`);
      const skip = new Set([this.rec.asset_id, ...(this.rec.versions?.members || []).map((m) => m.asset_id)]);
      if (this.verQ.trim() !== q) return;
      this.verItems = r.items.filter((i) => !skip.has(i.asset_id)).slice(0, 8)
        .map((i) => ({ id: i.asset_id, label: i.title || i.filename,
          sub: i.gramps_id ? `${i.filename} · already ${i.gramps_id}` : i.filename, thumb: i.thumb }));
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    }
  }

  onVersionQuery(v) {
    this.verQ = v;
    this.hiVer = -1;
    clearTimeout(this._verTimer);
    this._verTimer = setTimeout(() => this.searchVersions(), 250);
  }

  addVersion(it) {
    this.verOpen = false;
    this.verQ = '';
    this.verItems = [];
    this.versionAction('version', (id) => post(`/photos/api/photo/${id}/versions`, { asset_id: it.id }),
      'Version added and matched to the main image');
  }

  matchVersion(m) {
    this.versionAction('version', (id) => post(`/photos/api/photo/${id}/versions/${m.asset_id}/match`, {}),
      'Version matched to the main image');
  }

  removeVersion(m) {
    this.versionAction('version', (id) => api(`/photos/api/photo/${id}/versions/${m.asset_id}`, { method: 'DELETE' }),
      'Removed from the versions; its sync and ID tags were cleared');
  }

  async promoteVersion(m) {
    if (!this.rec || this.busy) return;
    this.busy = 'version';
    this.status = { kind: 'busy', msg: 'Changing the main image and syncing' };
    const old = this.rec.asset_id;
    try {
      const r = await post(`/photos/api/photo/${old}/versions/${m.asset_id}/promote`, { redraw_faces: this.redraw });
      this.applyRecord(r.photo, old);
      this.status = { kind: r.summary.errors ? 'error' : 'ok', msg: `Main image changed; ${this.syncSummary(r)}` };
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  async save(andSync = false) {
    if (!this.rec || this.busy) return;
    if (this.form.dateText.trim() && !this.form.date) {
      this.status = { kind: 'error', msg: 'The date is unreadable' };
      return;
    }
    this.busy = andSync ? 'sync' : 'save';
    this.status = { kind: 'busy', msg: 'Saving to Immich' };
    try {
      const rec = await api(`/photos/api/photo/${this.rec.asset_id}`,
        { method: 'PUT', body: JSON.stringify(payload(this.form)) });
      this.applyRecord(rec);
      this.status = { kind: 'ok', msg: 'Saved to Immich' };
      if (andSync) await this.sync();
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  async sync() {
    this.busy = 'sync';
    this.status = { kind: 'busy', msg: 'Syncing to Gramps' };
    try {
      const r = await post(`/photos/api/photo/${this.rec.asset_id}/sync`, {});
      this.applyRecord(r.photo);
      this.status = { kind: r.summary.errors ? 'error' : 'ok', msg: this.syncSummary(r) };
    } catch (e) {
      this.status = { kind: 'error', msg: e.message };
    } finally {
      this.busy = '';
    }
  }

  syncSummary(r) {
    const s = r.summary || {};
    const parts = [];
    if (s.created) parts.push(`created ${s.gramps_id}`);
    for (const e of r.events || []) {
      if (e.action === 'failed') parts.push(e.detail);
      else if (e.entity === 'media' && e.action === 'updated') parts.push(`updated ${Object.keys(e.data?.cols || {}).join(', ')}`);
      else if (e.entity === 'place' && (e.action === 'created' || e.action === 'updated')) parts.push(`place ${e.title}`);
      else if (e.entity === 'note' && (e.action === 'created' || e.action === 'updated')) parts.push(`note ${e.action}`);
    }
    if (s.people_linked?.length) parts.push(`faces ${s.people_linked.join(', ')}`);
    return parts.length ? parts.join('; ') : `${s.gramps_id} is in sync`;
  }

  chipBtn(id, label, icon) {
    return html`<button class="chip ${this.mode === id ? 'fill' : ''}" ?disabled=${this.loading}
      @click=${() => this.setMode(id)}><i>${icon}</i><span>${label}</span></button>`;
  }

  viewChip(id, label, icon) {
    return html`<button class="chip ${this.view === id ? 'fill' : ''}" @click=${() => this.setView(id)}>
      <i>${icon}</i><span>${label}</span></button>`;
  }

  renderBar() {
    const items = this.personMatches();
    if (this.view === 'collections') {
      return html`<nav class="wrap photos-bar">
        ${this.viewChip('photos', 'Photos', 'photo_library')}
        ${this.viewChip('collections', 'Collections', 'collections_bookmark')}
      </nav>`;
    }
    return html`<nav class="wrap photos-bar">
      ${this.viewChip('photos', 'Photos', 'photo_library')}
      ${this.viewChip('collections', 'Collections', 'collections_bookmark')}
      <span class="photos-bar-gap"></span>
      <div class="field prefix small no-margin photos-search">
        <i>search</i>
        <input type="text" placeholder="Search titles and file names" .value=${this.qDraft}
          @input=${(e) => { this.qDraft = e.target.value; }}
          @keydown=${(e) => { if (e.key === 'Enter') this.search(); else if (e.key === 'Escape') this.clearSearch(); }}>
      </div>
      ${this.q ? html`<button class="chip fill" @click=${() => this.clearSearch()}><i>search</i><span>${this.q}</span><i>close</i></button>` : nothing}
      ${MODES.map(([id, label, icon]) => this.chipBtn(id, label, icon))}
      ${this.person
        ? html`<button class="chip fill" @click=${() => this.clearPerson()}><i>face</i><span>${this.person.label}</span><i>close</i></button>`
        : searchMenu({
          label: 'Person', icon: 'face', value: this.personQ, items, active: this.hiPerson, open: this.personOpen,
          cls: 'chip', up: this.up.person,
          onToggle: (e) => { this.personOpen = !this.personOpen; this.flip('person', e); },
          onClose: () => { this.personOpen = false; },
          onInput: (e) => { this.personQ = e.target.value; this.hiPerson = -1; },
          onPick: (it) => this.pickPerson(it),
          onEnter: () => { if (this.hiPerson >= 0 && this.hiPerson < items.length) this.pickPerson(items[this.hiPerson]); },
          onMove: (d) => { if (items.length) this.hiPerson = (this.hiPerson + d + items.length) % items.length; },
          empty: this.people === null ? 'Loading people...' : 'No named person matches',
        })}
    </nav>`;
  }

  card(it, opts = {}) {
    return html`<article class="photo-card no-margin ${opts.dragging ? 'dragging' : ''}"
      draggable=${opts.draggable ? 'true' : nothing}
      @click=${() => this.openPhoto(it.asset_id)}
      @dragstart=${opts.draggable ? (e) => this.onDragStart(e, it) : nothing}
      @dragover=${opts.draggable ? (e) => this.onDragOver(e, it) : nothing}
      @drop=${opts.draggable ? (e) => { e.preventDefault(); this.finishDrag(); } : nothing}
      @dragend=${opts.draggable ? () => this.finishDrag() : nothing}>
      <div class="photo-thumb">
        ${opts.tools || nothing}
        ${it.missing ? html`<i class="photo-missing">broken_image</i>` : html`<img src=${it.thumb} loading="lazy" alt="">`}
        ${it.versions > 1 ? html`<span class="photo-badge"><i>layers</i>${it.versions}</span>` : nothing}
        ${it.type === 'VIDEO' ? html`<span class="photo-badge left"><i>videocam</i></span>` : nothing}
      </div>
      <div class="photo-meta">
        <div class="photo-title" title=${it.filename}>${it.title || it.filename}</div>
        <div class="photo-sub secondary-text">
          ${it.gramps_id ? html`<span class="mono">${it.gramps_id}</span>` : html`<span>Not in Gramps</span>`}
          <span class="mono">${it.date}</span>
        </div>
      </div>
    </article>`;
  }

  renderGrid() {
    if (!this.items.length && !this.loading) {
      const msg = this.q ? html`No photos match &ldquo;${this.q}&rdquo;` : 'No photos here';
      return html`<div class="faces-empty"><i>photo_library</i><span>${msg}</span></div>`;
    }
    return html`<div class="photos-grid">${this.items.map((it) => this.card(it))}</div>
      <nav class="pager">
        ${this.loading ? spinner : this.nextPage ? btn('Load more', false, () => this.load(), 'border') : nothing}
        <span class="small-text secondary-text">${this.items.length} shown</span>
      </nav>`;
  }

  syncBox(key, label) {
    return html`<label class="checkbox"><input type="checkbox" .checked=${this.form.sync[key]}
      @change=${(e) => this.setSync(key, e.target.checked)}><span>${label}</span></label>`;
  }

  renderPlace(f) {
    const items = this.placeMatches();
    return html`<div class="photos-place">
      <div class="chosen-media">
        ${f.place ? html`<i>${f.place.icon}</i>
          <div>
            <div>${f.place.label}</div>
            <div class="small-text secondary-text mono">${f.place.sub}</div>
          </div>
          <button class="circle transparent small" aria-label="Clear place" @click=${() => this.setForm({ place: null })}><i>close</i></button>`
        : html`<span class="secondary-text small-text">No Gramps place</span>`}
      </div>
      ${searchMenu({
        label: f.place ? 'Change place' : 'Choose place', icon: 'add_location',
        value: this.placeQ, items, active: this.hiPlace, open: this.placeOpen, up: this.up.place,
        onToggle: (e) => { this.placeOpen = !this.placeOpen; this.flip('place', e); },
        onClose: () => { this.placeOpen = false; },
        onInput: (e) => { this.placeQ = e.target.value; this.hiPlace = -1; },
        onPick: (it) => this.pickPlace(it),
        onEnter: () => { if (this.hiPlace >= 0 && this.hiPlace < items.length) this.pickPlace(items[this.hiPlace]); },
        onMove: (d) => { if (items.length) this.hiPlace = (this.hiPlace + d + items.length) % items.length; },
        empty: !this.placeQ.trim() ? '' : this.places ? 'No Gramps place matches' : 'Loading places...',
      })}
    </div>`;
  }

  renderPeople(r) {
    if (!r.people.length) return nothing;
    const linked = r.people.filter((p) => p.linked).length;
    return html`<details class="photos-people">
      <summary class="none">
        <i class="chev">chevron_right</i>
        <span class="small-text secondary-text">People (${r.people.length}${linked < r.people.length ? `, ${linked} linked` : ''})</span>
      </summary>
      <div class="photos-people-list">
        ${r.people.map((p) => html`<span class="chip small ${p.linked ? 'fill' : 'border'}"
          title=${p.linked ? 'Linked to a Gramps person' : 'Not linked in Faces'}>
          <i>${p.linked ? 'link' : 'link_off'}</i><span>${p.name || '(unnamed)'}</span></span>`)}
      </div>
    </details>`;
  }

  renderLightbox() {
    const m = this.lightbox;
    if (!m) return nothing;
    return html`<dialog class="photos-lightbox" @close=${() => { this.lightbox = null; }}
        @keydown=${(e) => { if (e.key === 'Escape') { e.stopPropagation(); e.currentTarget.close(); } }}
        @click=${(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
      <img src=${`/photos/api/thumb/${m.asset_id}?size=preview`} alt="">
      <div class="photos-lightbox-caption">
        <span class="max">${m.label ? html`${m.label} <span class="secondary-text">·</span> ` : nothing}<span class="mono">${m.filename}</span>
          <span class="mono secondary-text"> ${sizeText(m)}</span></span>
        <button class="circle transparent" aria-label="Close" @click=${(e) => e.currentTarget.closest('dialog').close()}><i>close</i></button>
      </div>
    </dialog>`;
  }

  versionLabel(m) {
    if (this.editLabel === m.asset_id) {
      return html`<div class="field small no-margin photos-version-label">
        <input type="text" placeholder="Note about this version" .value=${this.labelDraft}
          @input=${(e) => { this.labelDraft = e.target.value; }}
          @keydown=${(e) => { if (e.key === 'Enter') this.saveLabel(m); else if (e.key === 'Escape') { this.editLabel = null; } }}
          @blur=${() => this.saveLabel(m)}></div>`;
    }
    return html`<button class="photos-version-note ${m.label ? '' : 'secondary-text'}" title="Edit the note about this version"
      @click=${() => this.startLabel(m)}><i class="tiny">edit</i><span>${m.label || 'Add a note about this version'}</span></button>`;
  }

  versionRow(m) {
    const drift = m.drift || [];
    return html`<li>
      <img class="small-round photos-version-open" src=${m.thumb} alt="" title="View larger"
        @click=${() => { this.lightbox = m; }}>
      <div class="max">
        <div><span class="photos-version-open" @click=${() => { this.lightbox = m; }}>${m.filename}</span>${m.is_primary ? html` <span class="chip tiny fill">main</span>` : nothing}</div>
        <div class="small-text secondary-text mono">${sizeText(m)}</div>
        ${this.versionLabel(m)}
        ${m.is_primary ? nothing : html`<div class="small-text ${drift.length ? 'error-text' : 'secondary-text'}">
          ${drift.length ? `differs: ${drift.join(', ')}` : 'matches the main image'}</div>`}
      </div>
      ${m.is_primary ? nothing : html`<nav class="photos-version-actions">
        ${drift.length ? btn('Match', !!this.busy, () => this.matchVersion(m), 'border small') : nothing}
        ${btn('Make main', !!this.busy, () => this.promoteVersion(m), 'border small')}
        <button class="circle transparent small" title="Remove from versions" ?disabled=${!!this.busy}
          @click=${() => this.removeVersion(m)}><i>close</i></button>
      </nav>`}
    </li>`;
  }

  renderVersions(r) {
    const v = r.versions;
    const members = v?.members || [];
    const items = this.verItems;
    return html`<div class="photos-versions">
      <nav class="wrap photos-versions-bar">
        <span class="small-text secondary-text">Versions${members.length ? ` (${members.length})` : ''}</span>
        ${searchMenu({
          label: 'Add version', icon: 'library_add', value: this.verQ, items, active: this.hiVer, open: this.verOpen,
          cls: 'border small', placeholder: 'Search titles and file names', up: this.up.version,
          onToggle: (e) => { this.verOpen = !this.verOpen; this.flip('version', e); },
          onClose: () => { this.verOpen = false; },
          onInput: (e) => this.onVersionQuery(e.target.value),
          onPick: (it) => this.addVersion(it),
          onEnter: () => { if (this.hiVer >= 0 && this.hiVer < items.length) this.addVersion(items[this.hiVer]); },
          onMove: (d) => { if (items.length) this.hiVer = (this.hiVer + d + items.length) % items.length; },
          empty: this.verQ.trim() ? 'No unstacked photo matches' : '',
        })}
        ${members.length > 1 ? html`<label class="checkbox"><input type="checkbox" .checked=${this.redraw}
          @change=${(e) => { this.redraw = e.target.checked; }}><span class="small-text">Redraw face boxes when the main image changes</span></label>` : nothing}
      </nav>
      ${v?.error ? html`<p class="error-text small-text">${v.error}</p>` : nothing}
      ${members.length ? html`<ul class="list">${members.map((m) => this.versionRow(m))}</ul>`
        : html`<p class="small-text secondary-text photos-versions-empty">No other versions yet. Add a rescan or a restored copy and they stay together with the same metadata.</p>`}
      ${r.suggestions?.length ? html`<span class="small-text secondary-text">Suggested versions</span>
        <ul class="list">${r.suggestions.map((sg) => html`<li>
          <img class="small-round" src=${sg.thumb} alt="">
          <div class="max">
            <div>${sg.title || sg.filename}</div>
            <div class="small-text secondary-text">${sg.why}${sg.in_stack ? ' · in another stack' : ''}</div>
          </div>
          ${sg.in_stack ? nothing : btn('Add', !!this.busy, () => this.addVersion({ id: sg.asset_id }), 'border small')}
        </li>`)}</ul>` : nothing}
    </div>`;
  }

  colCard(it, i, n) {
    const stop = (fn) => (e) => { e.stopPropagation(); fn(); };
    const tools = html`<nav class="photo-tools" @click=${(e) => e.stopPropagation()}>
      <span class="photo-seq mono">${i + 1}</span>
      <button class="circle transparent tiny" title="Move earlier" ?disabled=${i === 0 || !!this.colBusy}
        @click=${stop(() => this.moveItem(it, -1))}><i>chevron_left</i></button>
      <button class="circle transparent tiny" title="Move later" ?disabled=${i === n - 1 || !!this.colBusy}
        @click=${stop(() => this.moveItem(it, 1))}><i>chevron_right</i></button>
      <button class="circle transparent tiny" title="Remove from collection" ?disabled=${!!this.colBusy}
        @click=${stop(() => this.removeFromOpenCollection(it))}><i>close</i></button>
    </nav>`;
    return this.card(it, { draggable: true, dragging: this.dragId === it.asset_id, tools });
  }

  renderCollectionList() {
    if (this.collections === null) return html`<p>${spinner}</p>`;
    const albums = this.albumMatches();
    return html`<nav class="wrap photos-col-new">
        ${field('New collection', this.newColName, (e) => { this.newColName = e.target.value; },
          { width: 'medium', onEnter: () => this.createCollection() })}
        ${btn('Create', !this.newColName.trim() || !!this.colBusy, () => this.createCollection(), 'border')}
        ${searchMenu({
          label: 'Import Immich album', icon: 'photo_album', value: this.albumQ, items: albums, active: this.hiAlbum,
          open: this.albumOpen, cls: 'border', placeholder: 'Search albums',
          onToggle: (e) => { this.albumOpen = !this.albumOpen; this.flip('album', e); if (this.albumOpen) this.loadAlbums(); },
          onClose: () => { this.albumOpen = false; },
          onInput: (e) => { this.albumQ = e.target.value; this.hiAlbum = -1; },
          onPick: (it) => this.importAlbum(it),
          onEnter: () => { if (this.hiAlbum >= 0 && this.hiAlbum < albums.length) this.importAlbum(albums[this.hiAlbum]); },
          onMove: (d) => { if (albums.length) this.hiAlbum = (this.hiAlbum + d + albums.length) % albums.length; },
          empty: this.albums === null ? 'Loading albums...' : 'No album matches',
        })}
      </nav>
      ${this.colStatus ? html`<p>${statusLine(this.colStatus.kind, this.colStatus.msg)}</p>` : nothing}
      ${this.collections.length ? html`<div class="photos-grid">${this.collections.map((c) => html`
        <article class="photo-card no-margin" @click=${() => this.openCollection(c.id)}>
          <div class="photo-thumb">
            ${c.cover ? html`<img src=${c.cover} loading="lazy" alt="">` : html`<i class="photo-missing">collections_bookmark</i>`}
            <span class="photo-badge"><i>photo_library</i>${c.count}</span>
          </div>
          <div class="photo-meta">
            <div class="photo-title">${c.name}</div>
            <div class="photo-sub secondary-text"><span>${c.description || ' '}</span></div>
          </div>
        </article>`)}</div>`
        : html`<div class="faces-empty"><i>collections_bookmark</i><span>No collections yet. Name one above, then add photos from the editor or from the collection page.</span></div>`}`;
  }

  renderCollection() {
    const c = this.colOpen;
    const items = this.colItems;
    const dirty = this.colName.trim() !== c.name || this.colDesc.trim() !== (c.description || '');
    return html`<nav class="wrap photos-col-head">
        ${btn(html`<i>arrow_back</i><span>Collections</span>`, false, () => this.closeCollection(), 'border')}
        ${field('Name', this.colName, (e) => { this.colName = e.target.value; }, { width: 'medium', onEnter: () => this.saveCollection() })}
        ${field('Description', this.colDesc, (e) => { this.colDesc = e.target.value; }, { width: 'large' })}
        ${btn('Save', !dirty || !!this.colBusy, () => this.saveCollection(), 'border')}
        ${searchMenu({
          label: 'Add photos', icon: 'add_photo_alternate', value: this.colQ, items, active: this.hiCol, open: this.colMenuOpen,
          cls: 'border', placeholder: 'Search titles and file names', up: this.up.album_add,
          onToggle: (e) => { this.colMenuOpen = !this.colMenuOpen; this.flip('album_add', e); },
          onClose: () => { this.colMenuOpen = false; },
          onInput: (e) => this.onCollectionQuery(e.target.value),
          onPick: (it) => this.addToOpenCollection(it),
          onEnter: () => { if (this.hiCol >= 0 && this.hiCol < items.length) this.addToOpenCollection(items[this.hiCol]); },
          onMove: (d) => { if (items.length) this.hiCol = (this.hiCol + d + items.length) % items.length; },
          empty: this.colQ.trim() ? 'No photo matches' : '',
        })}
        <span class="max"></span>
        <button class="border small ${this.confirmDelete ? 'error' : ''}" ?disabled=${!!this.colBusy}
          @click=${() => this.deleteCollection()}>
          <i>delete</i><span>${this.confirmDelete ? 'Click again to delete' : 'Delete'}</span></button>
      </nav>
      <p class="small-text secondary-text photos-col-hint">
        ${c.items.length} photo${c.items.length === 1 ? '' : 's'} in your order. Drag a photo to move it, or use the arrows. Click one to open it.
        ${this.colStatus ? html` ${statusLine(this.colStatus.kind, this.colStatus.msg)}` : nothing}
      </p>
      ${c.items.length ? html`<div class="photos-grid">${c.items.map((it, i) => this.colCard(it, i, c.items.length))}</div>`
        : html`<div class="faces-empty"><i>add_photo_alternate</i><span>Empty. Use Add photos, or Add to collection inside a photo.</span></div>`}`;
  }

  renderEditorCollections(r) {
    const items = this.editorCollectionMatches();
    return html`<div class="photos-editor-cols">
      <span class="small-text secondary-text">Collections</span>
      ${(r.collections || []).map((c) => html`<button class="chip small fill" title="Remove from ${c.name}"
        ?disabled=${!!this.busy} @click=${() => this.removeRecFromCollection(c)}><span>${c.name}</span><i>close</i></button>`)}
      ${searchMenu({
        label: 'Add to collection', icon: 'collections_bookmark', value: this.ecQ, items, active: this.hiEc, open: this.ecOpen,
        cls: 'border small', placeholder: 'Find or name a collection', up: this.up.collection,
        onToggle: (e) => { this.ecOpen = !this.ecOpen; this.flip('collection', e); },
        onClose: () => { this.ecOpen = false; },
        onInput: (e) => { this.ecQ = e.target.value; this.hiEc = -1; },
        onPick: (it) => this.addRecToCollection(it),
        onEnter: () => { if (this.hiEc >= 0 && this.hiEc < items.length) this.addRecToCollection(items[this.hiEc]); },
        onMove: (d) => { if (items.length) this.hiEc = (this.hiEc + d + items.length) % items.length; },
        empty: this.collections === null ? 'Loading collections...' : 'Type a name to create one',
      })}
    </div>`;
  }

  renderRecord(r, f) {
    return html`<div class="photos-editor-body">
      <div class="photos-preview">
        <img src=${r.preview} alt="">
        <div class="photos-links small-text">
          ${r.immich_url ? html`<a class="photos-app-link" href=${r.immich_url} target="_blank" rel="noopener" title="Open in Immich"><img src="/static/vendor/icons/immich.svg" alt="Immich"></a>` : nothing}
          ${r.gramps?.url ? html`<a class="photos-app-link" href=${r.gramps.url} target="_blank" rel="noopener" title="Open in Gramps"><img src="/static/vendor/icons/gramps-web.svg" alt="Gramps"></a>` : nothing}
          <span class="mono secondary-text">${r.gramps ? r.gramps.gramps_id : 'not in Gramps'}</span>
        </div>
        ${this.renderPeople(r)}
        ${this.renderEditorCollections(r)}
      </div>
      <div class="photos-form">
        ${field('Title', f.title, (e) => this.setForm({ title: e.target.value }))}
        <nav class="wrap photos-row">
          ${field('Date', f.dateText, (e) => this.setDate(e.target.value),
            { width: 'small', mono: true, placeholder: 'YYYY, YYYY-MM or YYYY-MM-DD',
              error: f.dateText.trim() && !f.date ? 'Unreadable' : '' })}
          ${selectField('Precision', f.date?.precision || 'exact', PRECISION, (e) => this.setDateField('precision', e.target.value), { width: 'small' })}
          ${selectField('Modifier', f.date?.modifier || 'regular', MODIFIER, (e) => this.setDateField('modifier', e.target.value), { width: 'small' })}
          ${selectField('Quality', f.date?.quality || 'regular', QUALITY, (e) => this.setDateField('quality', e.target.value), { width: 'small' })}
        </nav>
        <p class="small-text secondary-text photos-hint">Gramps date: <span class="mono">${grampsDate(f.date) || '(none)'}</span></p>
        ${this.renderPlace(f)}
        ${field('Notes', f.notes, (e) => this.setForm({ notes: e.target.value }), { rows: 4 })}
        <div class="photos-sync-row">
          <span class="small-text secondary-text">Sync to Gramps</span>
          ${this.syncBox('media', 'media object')}
          ${this.syncBox('title', 'title')}
          ${this.syncBox('date', 'date')}
          ${this.syncBox('note', 'note')}
        </div>
        <nav class="wrap photos-actions">
          ${btn(this.busy === 'save' ? 'Saving...' : 'Save', !!this.busy, () => this.save(false), 'border')}
          ${btn(this.busy === 'sync' ? 'Syncing...' : 'Save and sync', !!this.busy, () => this.save(true))}
          ${this.busy ? spinner : nothing}
        </nav>
        ${this.status ? html`<p class="photos-status">${statusLine(this.status.kind, this.status.msg)}</p>` : nothing}
        ${this.renderVersions(r)}
      </div>
    </div>`;
  }

  renderEditor() {
    if (!this.openId) return nothing;
    const r = this.rec;
    return html`<dialog class="photos-editor" @close=${() => this.closeEditor()} @click=${(e) => this.scrimClick(e)}>
      <nav>
        <h5 class="max small">${r ? (r.title || r.filename) : 'Loading...'}</h5>
        <button class="circle transparent" aria-label="Close" @click=${(e) => e.currentTarget.closest('dialog').close()}><i>close</i></button>
      </nav>
      ${this.recError ? html`<p>${statusLine('error', this.recError)}</p>`
        : !r ? html`<p>${spinner}</p>` : this.renderRecord(r, this.form)}
    </dialog>`;
  }

  render() {
    if (this.config === null) return html`<p>${spinner}</p>`;
    if (!this.config.enabled) {
      return html`<p class="secondary-text">${this.error || 'Immich is not configured (immich.base_url / accounts)'}</p>`;
    }
    const body = this.view === 'collections'
      ? (this.colOpen ? this.renderCollection() : this.renderCollectionList())
      : html`${this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}${this.renderGrid()}`;
    return html`${this.renderBar()}
      ${body}
      ${this.renderEditor()}
      ${this.renderLightbox()}`;
  }
}
customElements.define('photos-page', PhotosPage);
