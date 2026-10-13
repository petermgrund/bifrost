import { BifrostElement, html, nothing, api, field, spinner, statusLine } from './core.js';

const API = '/inbox/api';
const PAGE_SIZE = 10;
const OPEN = new Set(['processing', 'filed', 'transcribing']);
const STATE = {
  processing: ['', 'Processing'],
  filed: ['surface-variant', 'In Paperless'],
  synced: ['primary-container', 'In Gramps'],
  transcribing: ['secondary-container', 'Transcribing'],
  failed: ['error', 'Failed'],
};
const blank = () => ({ link: '', collection: '', reference: '', page: '', image: '', title: '', note: '', files: [], pasted: '' });

function errText(e) {
  const m = String(e?.message ?? e).match(/^\d+: ([\s\S]*)$/);
  if (!m) return String(e?.message ?? e);
  try { return JSON.parse(m[1]).detail || m[1]; } catch { return m[1]; }
}

function imageParts(text) {
  const m = /^\s*(\d+)\s*(?:(?:of|\/)\s*(\d+))?\s*$/i.exec(text || '');
  return m ? { image: m[1], images: m[2] || '' } : { image: (text || '').trim(), images: '' };
}

function lastPart(collection) {
  return (collection || '').split(' › ').pop().trim();
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

class CaptureInbox extends BifrostElement {
  static properties = {
    card: { state: true },
    transcribe: { state: true },
    canTranscribe: { state: true },
    titleFocus: { state: true },
    saving: { state: true },
    msg: { state: true },
    items: { state: true },
    older: { state: true },
    page: { state: true },
    loadError: { state: true },
    dragging: { state: true },
  };

  constructor() {
    super();
    this.card = blank();
    this.transcribe = false;
    this.canTranscribe = false;
    this.titleFocus = false;
    this.saving = false;
    this.msg = null;
    this.items = null;
    this.older = false;
    this.page = 0;
    this.loadError = '';
    this.dragging = false;
    this._seq = 0;
    this._paste = (e) => this.onPaste(e);
    this._keys = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); this.save(); }
    };
    this._over = (e) => {
      if (![...(e.dataTransfer?.types || [])].includes('Files')) return;
      e.preventDefault();
      this.dragging = true;
    };
    this._leave = (e) => { if (!e.relatedTarget) this.dragging = false; };
    this._drop = (e) => {
      if (!e.dataTransfer?.files?.length) return;
      e.preventDefault();
      this.dragging = false;
      this.addFiles(e.dataTransfer.files);
    };
  }

  connectedCallback() {
    super.connectedCallback();
    document.addEventListener('paste', this._paste);
    document.addEventListener('keydown', this._keys);
    document.addEventListener('dragover', this._over);
    document.addEventListener('dragleave', this._leave);
    document.addEventListener('drop', this._drop);
    api(`${API}/config`).then((c) => { this.canTranscribe = !!c.transcribe; }).catch(() => {});
    this.load();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener('paste', this._paste);
    document.removeEventListener('keydown', this._keys);
    document.removeEventListener('dragover', this._over);
    document.removeEventListener('dragleave', this._leave);
    document.removeEventListener('drop', this._drop);
    clearTimeout(this._poll);
    clearTimeout(this._msgTimer);
  }

  say(kind, text) {
    this.msg = [kind, text];
    clearTimeout(this._msgTimer);
    if (kind === 'ok') this._msgTimer = setTimeout(() => { this.msg = null; }, 2000);
  }

  set(key, value) {
    this.card = { ...this.card, [key]: value };
  }

  onPaste(e) {
    const files = [...(e.clipboardData?.files || [])];
    if (files.length) {
      e.preventDefault();
      this.addFiles(files);
      return;
    }
    const target = e.target.closest?.('input, textarea, [contenteditable]');
    const key = target?.closest('[data-clip]')?.dataset.clip;
    if (target && !key) return;
    const text = e.clipboardData?.getData('text/plain') || '';
    if (!text.trim()) return;
    e.preventDefault();
    this.readClip(text, key);
  }

  async pasteButton() {
    const board = navigator.clipboard;
    if (!board?.read && !board?.readText) { this.say('error', 'Press ⌘V to paste'); return; }
    try {
      if (board.read) {
        const files = [];
        let text = '';
        for (const item of await board.read()) {
          const type = item.types.find((t) => t.startsWith('image/'));
          if (type) files.push(new File([await item.getType(type)], `pasted.${type.split('/')[1]}`, { type }));
          else if (item.types.includes('text/plain')) text += await (await item.getType('text/plain')).text();
        }
        if (files.length) this.addFiles(files);
        if (text.trim()) await this.readClip(text);
      } else {
        const text = await board.readText();
        if (text.trim()) await this.readClip(text);
      }
    } catch {
      this.say('error', 'Press ⌘V to paste');
    }
  }

  async readClip(text, into = '') {
    let found = {};
    try {
      found = await api(`${API}/read`, { method: 'POST', body: JSON.stringify({ text }) });
    } catch (e) {
      this.say('error', errText(e));
      return;
    }
    const card = { ...this.card, pasted: [this.card.pasted, text.trim()].filter(Boolean).join('\n\n') };
    for (const key of ['link', 'collection', 'reference', 'page']) if (found[key]) card[key] = found[key];
    if (found.image) card.image = found.images ? `${found.image} of ${found.images}` : found.image;
    if (into && !found[into]) card[into] = text.trim();
    this.card = card;
    this.msg = null;
  }

  addFiles(list) {
    for (const file of [...list]) {
      const key = `${Date.now()}-${Math.random()}`;
      this.set('files', [...this.card.files, { key, name: file.name || 'pasted', uploading: true }]);
      this.upload(file, key);
    }
  }

  async upload(file, key) {
    let got = null;
    let error = '';
    try {
      const resp = await fetch(`${API}/files?name=${encodeURIComponent(file.name || '')}`, { method: 'POST', body: file });
      if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
      got = await resp.json();
    } catch (e) {
      error = errText(e);
    }
    this.set('files', this.card.files.map((f) => (f.key === key ? { ...f, ...(got || {}), uploading: false, error } : f)));
  }

  removeFile(key) {
    const f = this.card.files.find((x) => x.key === key);
    if (f?.file) api(`${API}/files/${f.file}`, { method: 'DELETE' }).catch(() => {});
    this.set('files', this.card.files.filter((x) => x.key !== key));
  }

  get ready() {
    const files = this.card.files;
    return files.length > 0 && files.every((f) => f.file && !f.uploading);
  }

  get fallbackTitle() {
    const { image } = imageParts(this.card.image);
    const page = this.card.page.trim();
    const spot = page ? `page ${page}` : image ? `image ${image}` : '';
    const title = [lastPart(this.card.collection), spot].filter(Boolean).join(', ')
      || (this.card.files[0]?.name || '').replace(/\.[^.]+$/, '');
    return title ? title[0].toUpperCase() + title.slice(1) : '';
  }

  async save() {
    if (this.saving) return;
    if (!this.card.files.length) { this.say('error', 'Add a file'); return; }
    if (!this.ready) return;
    const c = this.card;
    const { image, images } = imageParts(c.image);
    this.saving = true;
    try {
      const row = await api(`${API}/captures`, {
        method: 'POST',
        body: JSON.stringify({
          files: c.files.map((f) => f.file), title: c.title, link: c.link, note: c.note, pasted: c.pasted,
          transcribe: this.transcribe && this.canTranscribe,
          details: { collection: c.collection, reference: c.reference, page: c.page, image, images },
        }),
      });
      this.card = blank();
      this.msg = null;
      this.items = [row, ...(this.items || []).filter((r) => r.key !== row.key)];
      this.page = 0;
      this.schedule();
    } catch (e) {
      this.say('error', errText(e));
    } finally {
      this.saving = false;
    }
  }

  async load() {
    const seq = ++this._seq;
    try {
      const { items } = await api(`${API}/captures${this.older ? '?older=true' : ''}`);
      if (seq !== this._seq) return;
      this.items = items;
      this.loadError = '';
    } catch (e) {
      if (seq === this._seq) this.loadError = errText(e);
    }
    this.schedule();
  }

  schedule() {
    clearTimeout(this._poll);
    if ((this.items || []).some((r) => OPEN.has(r.state))) this._poll = setTimeout(() => this.load(), 3000);
  }

  showOlder(on) {
    this.older = on;
    this.page = 0;
    this.load();
  }

  async drop(r) {
    try {
      if (r.older) await api(`${API}/hidden/${r.doc_id}`, { method: 'POST' });
      else await api(`${API}/captures/${r.id}`, { method: 'DELETE' });
      this.items = this.items.filter((x) => x.key !== r.key);
    } catch (e) {
      this.loadError = errText(e);
    }
  }

  render() {
    return html`${this.renderCard()}<div class="large-space"></div>${this.renderList()}`;
  }

  clipField(label, key, opts = {}) {
    return html`<div data-clip=${key}>${field(label, this.card[key], (e) => this.set(key, e.target.value), opts)}</div>`;
  }

  titleField() {
    return html`<div class="field label fill">
      <input type="text" .value=${this.card.title} placeholder=${this.titleFocus ? this.fallbackTitle : ''}
        @input=${(e) => this.set('title', e.target.value)}
        @focus=${() => { this.titleFocus = true; }} @blur=${() => { this.titleFocus = false; }}>
      <label>Title</label>
    </div>`;
  }

  fileChip(f) {
    const icon = f.error ? 'error' : f.mime === 'application/pdf' ? 'picture_as_pdf' : 'image';
    return html`<span class="chip inbox-file ${f.error ? 'error' : ''}" title=${f.error || f.name}>
      ${f.uploading ? spinner : html`<i>${icon}</i>`}
      <span>${f.name}</span>
      <button class="transparent circle" aria-label="Remove ${f.name}" @click=${() => this.removeFile(f.key)}><i>close</i></button>
    </span>`;
  }

  renderCard() {
    const c = this.card;
    const pages = c.files.reduce((n, f) => n + (f.pages || 0), 0);
    return html`<article class="border inbox-card ${this.dragging ? 'dragging' : ''}">
      <nav class="wrap">
        <button class="border" @click=${() => this.pasteButton()}><i>content_paste</i><span>Paste</span></button>
        <button class="border" @click=${() => this.querySelector('input.inbox-pick').click()}>
          <i>attach_file</i><span>Add files</span></button>
        <input class="inbox-pick" type="file" multiple accept="image/*,application/pdf" hidden
          @change=${(e) => { this.addFiles(e.target.files); e.target.value = ''; }}>
      </nav>
      <div class="space"></div>
      <div class="grid inbox-fields">
        <div class="s12">${this.clipField('Link', 'link')}</div>
        <div class="s12">${this.clipField('Collection', 'collection')}</div>
        <div class="s12 m6">${this.clipField('Reference', 'reference')}</div>
        <div class="s6 m3">${this.clipField('Page', 'page')}</div>
        <div class="s6 m3">${this.clipField('Image', 'image')}</div>
        <div class="s12">${this.titleField()}</div>
        <div class="s12">${field('Note', c.note, (e) => this.set('note', e.target.value), { rows: 2 })}</div>
      </div>
      ${c.files.length ? html`<nav class="wrap inbox-files">
        ${c.files.map((f) => this.fileChip(f))}
        ${pages > 1 ? html`<span class="secondary-text">${plural(pages, 'page')}</span>` : nothing}
      </nav>` : nothing}
      <nav class="inbox-save">
        <div class="max">${this.saving ? spinner : this.msg ? statusLine(...this.msg) : nothing}</div>
        ${this.canTranscribe ? html`<label class="switch"><input type="checkbox" .checked=${this.transcribe}
          @change=${(e) => { this.transcribe = e.target.checked; }}><span>Transcribe</span></label>` : nothing}
        <button ?disabled=${!this.ready || this.saving} @click=${() => this.save()}>Save</button>
      </nav>
    </article>`;
  }

  where(r) {
    const d = r.details || {};
    const image = d.image ? `image ${d.image}${d.images ? ` of ${d.images}` : ''}` : '';
    const page = d.page ? `page ${d.page}` : '';
    return [lastPart(d.collection), page, image, r.pid].filter(Boolean).join(' · ');
  }

  thumb(r) {
    if (!r.doc_id) return html`<i class="secondary-text">hourglass_empty</i>`;
    const fallback = (e) => e.target.replaceWith(Object.assign(document.createElement('i'),
      { textContent: 'description', className: 'secondary-text' }));
    return html`<img class="inbox-thumb" src="${API}/thumb/${r.doc_id}" alt="" loading="lazy" @error=${fallback}>`;
  }

  row(r) {
    const [cls, label] = STATE[r.state] || ['', r.state];
    return html`<tr>
      <td>${this.thumb(r)}</td>
      <td title=${r.title}>
        <div class="inbox-title">${r.title}</div>
        <div class="small-text ${r.error ? 'error-text' : 'secondary-text'} inbox-sub">${r.error || this.where(r)}</div>
      </td>
      <td>${r.older ? nothing : html`<span class="chip small ${cls}">${label}</span>`}</td>
      <td><nav class="no-space inbox-actions">
        ${r.pid ? html`<a class="button border small" href="/citations?doc=${r.doc_id}">Cite</a>`
          : html`<button class="border small" disabled>Cite</button>`}
        <button class="circle transparent small" title="Remove" aria-label="Remove" @click=${() => this.drop(r)}>
          <i>close</i></button>
      </nav></td>
    </tr>`;
  }

  renderList() {
    if (this.loadError) return html`<p>${statusLine('error', this.loadError)}</p>`;
    if (!this.items) return html`<p>${spinner}</p>`;
    const items = this.items;
    const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
    const page = Math.min(this.page, pages - 1);
    const first = page * PAGE_SIZE;
    const rows = items.slice(first, first + PAGE_SIZE);
    const padRows = pages > 1 ? PAGE_SIZE - rows.length : 0;
    return html`<nav class="inbox-head">
        <div class="max"></div>
        <label class="switch"><input type="checkbox" .checked=${this.older}
          @change=${(e) => this.showOlder(e.target.checked)}><span>Older documents</span></label>
      </nav>
      ${items.length ? html`<div class="scroll">
        <table class="sync-table inbox-table">
          <colgroup><col class="col-thumb"><col><col class="col-state"><col class="col-actions"></colgroup>
          <tbody>
            ${rows.map((r) => this.row(r))}
            ${Array.from({ length: padRows }, () => html`<tr class="pad"><td colspan="4">&nbsp;</td></tr>`)}
          </tbody>
        </table>
      </div>` : nothing}
      ${pages > 1 ? html`<nav class="pager">
        <button class="circle transparent" ?disabled=${page === 0}
          @click=${() => { this.page = page - 1; }} aria-label="Previous page"><i>chevron_left</i></button>
        <span class="pager-count">${first + 1}-${Math.min(first + PAGE_SIZE, items.length)} of ${items.length}</span>
        <button class="circle transparent" ?disabled=${page >= pages - 1}
          @click=${() => { this.page = page + 1; }} aria-label="Next page"><i>chevron_right</i></button>
      </nav>` : nothing}`;
  }
}
customElements.define('capture-inbox', CaptureInbox);
