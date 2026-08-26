import '/static/vendor/marked.min.js';
import { unsafeHTML } from 'lit';
import { BifrostElement, html, nothing, api, post, btn, chip, spinner, statusLine } from './core.js';

const DRAFT_KEY = 'bifrost-style-draft';
const WRAP_KEY = 'bifrost-style-wrap';
const PV_KEY = 'bifrost-style-preview';

function splitRow(line) {
  let s = line.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|') && !s.endsWith('\\|')) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
}

const isSeparator = (line) => {
  const cells = splitRow(line);
  return cells.length > 0 && cells.every((c) => /^:?-+:?$/.test(c));
};


function findTable(text, caret) {
  const lines = text.split('\n');
  let idx = text.slice(0, caret).split('\n').length - 1;
  const isRow = (i) => i >= 0 && i < lines.length && /^\s*\|/.test(lines[i]);
  if (!isRow(idx)) return null;
  let start = idx, end = idx;
  while (isRow(start - 1)) start -= 1;
  while (isRow(end + 1)) end += 1;
  if (end - start < 1 || !isSeparator(lines[start + 1])) return null;

  const head = splitRow(lines[start]);
  const align = splitRow(lines[start + 1]).map((c) =>
    c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : 'left');
  const rows = [];
  for (let i = start + 2; i <= end; i += 1) rows.push(splitRow(lines[i]));

  const cols = Math.max(head.length, align.length, 1, ...rows.map((r) => r.length));
  while (head.length < cols) head.push('');
  while (align.length < cols) align.push('left');
  rows.forEach((r) => { while (r.length < cols) r.push(''); });
  return { start, end, head, align, rows };
}


function serializeTable(t) {
  const esc = (c) => (c ?? '').replace(/\|/g, '\\|');
  const widths = t.head.map((h, c) =>
    Math.max(3, esc(h).length, ...t.rows.map((r) => esc(r[c]).length)));
  const row = (cells) =>
    '| ' + cells.map((x, c) => esc(x).padEnd(widths[c])).join(' | ') + ' |';
  const sep = '| ' + t.align.map((a, c) => {
    const w = widths[c];
    if (a === 'center') return ':' + '-'.repeat(Math.max(1, w - 2)) + ':';
    if (a === 'right') return '-'.repeat(w - 1) + ':';
    return '-'.repeat(w);
  }).join(' | ') + ' |';
  return [row(t.head), sep, ...t.rows.map(row)];
}

class StylePage extends BifrostElement {
  static properties = {
    text: { state: true },
    pvText: { state: true },
    baseMtime: { state: true },
    dirty: { state: true },
    busy: { state: true },
    result: { state: true },
    wrap: { state: true },
    showPreview: { state: true },
    tbl: { state: true },
  };

  constructor() {
    super();
    this.text = null;
    this.pvText = '';
    this.baseMtime = 0;
    this.dirty = false;
    this.busy = false;
    this.result = null;
    this.wrap = localStorage.getItem(WRAP_KEY) !== '0';
    this.showPreview = localStorage.getItem(PV_KEY) !== '0';
    this.tbl = null;
    this._draftTimer = 0;
    this._pvTimer = 0;
    this._pvSrc = null;
    this._pvHtml = '';
    this._warnUnsaved = (e) => {
      if (this.dirty) e.preventDefault();
    };
    this._onKey = (e) => {
      if (e.key === 'Escape' && this.tbl) { this.tbl = null; return; }
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!this.tbl) this.save();
      }
    };
  }

  connectedCallback() {
    super.connectedCallback();
    addEventListener('beforeunload', this._warnUnsaved);
    addEventListener('keydown', this._onKey);
    this.load();
  }

  disconnectedCallback() {
    removeEventListener('beforeunload', this._warnUnsaved);
    removeEventListener('keydown', this._onKey);
    clearTimeout(this._draftTimer);
    clearTimeout(this._pvTimer);
    super.disconnectedCallback();
  }

  readDraft() {
    try { return JSON.parse(localStorage.getItem(DRAFT_KEY)); } catch { return null; }
  }

  queueDraft() {
    clearTimeout(this._draftTimer);
    this._draftTimer = setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(
          { text: this.text, baseMtime: this.baseMtime, at: Date.now() }));
      } catch { }
    }, 600);
  }

  clearDraft() {
    clearTimeout(this._draftTimer);
    localStorage.removeItem(DRAFT_KEY);
  }

  queuePreview() {
    clearTimeout(this._pvTimer);
    this._pvTimer = setTimeout(() => { this.pvText = this.text; }, 350);
  }

  setText(text) {
    this.text = text;
    this.pvText = text;
  }

  toggleWrap() {
    this.wrap = !this.wrap;
    localStorage.setItem(WRAP_KEY, this.wrap ? '1' : '0');
  }

  togglePreview() {
    this.showPreview = !this.showPreview;
    localStorage.setItem(PV_KEY, this.showPreview ? '1' : '0');
  }

  async load() {
    this.result = null;
    this.busy = true;
    try {
      const r = await api('/style/api/doc');
      this.setText(r.text);
      this.baseMtime = r.mtime;
      this.dirty = false;
      if (r.exists === false) {
        this.dirty = true;
        this.result = { kind: 'info',
          body: 'No citation style doc exists yet. Edit this starter and save it.' };
      }

      const d = this.readDraft();
      if (d && typeof d.text === 'string' && d.text !== r.text) {
        const when = new Date(d.at).toLocaleString();
        const discard = btn('Discard draft', false,
          () => { this.clearDraft(); this.load(); }, 'small');
        if (d.baseMtime === r.mtime) {
          this.setText(d.text);
          this.dirty = true;
          this.result = { kind: 'info',
            body: html`Restored an unsaved draft from ${when}. ${discard}` };
        } else {
          this.result = { kind: 'error',
            body: html`Found unsaved draft from ${when}, but the file changed on
              disk. ${btn('Load draft', false, () => {
                this.setText(d.text); this.dirty = true; this.result = null;
              }, 'small')} ${discard}` };
        }
      } else if (d) {
        this.clearDraft();
      }
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = false;
    }
  }

  async save() {
    if (this.busy || this.text === null || !this.dirty) return;
    this.result = null;
    this.busy = true;
    try {
      const r = await post('/style/api/doc', { text: this.text, base_mtime: this.baseMtime });
      this.baseMtime = r.mtime;
      this.dirty = false;
      this.clearDraft();
      this.result = r.unchanged
        ? { kind: 'info', body: 'No changes to save.' }
        : r.created
        ? { kind: 'ok', body: `Created (${(r.size / 1024).toFixed(0)} kB).` }
        : { kind: 'ok', body: `Saved` };
    } catch (e) {
      this.result = e.message.startsWith('409')
        ? { kind: 'error', body: html`Changed on disk since it was loaded. Your edit was NOT
            saved but it is kept as a draft. ${btn('Reload', false, () => this.load(), 'small')}` }
        : { kind: 'error', body: e.message };
    } finally {
      this.busy = false;
    }
  }

  get outline() {
    const out = [];
    let line = 0;
    for (const ln of (this.pvText ?? '').split('\n')) {
      const m = /^(#{1,2}) (.+)$/.exec(ln);
      if (m) out.push({ line, label: (m[1] === '##' ? '   ' : '') + m[2] });
      line += 1;
    }
    return out;
  }

  scrollToLine(ta, line) {
    const all = this.text.split('\n');
    const offset = line === 0 ? 0 : all.slice(0, line).join('\n').length + 1;
    ta.focus();
    ta.setSelectionRange(offset, offset);
    if (this.wrap) {
      ta.scrollTop = Math.max(0, (line / all.length) * (ta.scrollHeight - ta.clientHeight) - 40);
    } else {
      const lineHeight = parseFloat(getComputedStyle(ta).lineHeight) || 20;
      ta.scrollTop = Math.max(0, line * lineHeight - 2 * lineHeight);
    }
  }

  jump(e) {
    const raw = e.target.value;
    e.target.value = '';
    if (raw === '') return;
    const ta = this.querySelector('textarea');
    if (ta) this.scrollToLine(ta, Number(raw));
  }

  openTable() {
    const ta = this.querySelector('textarea');
    if (!ta) return;
    const t = findTable(this.text, ta.selectionStart);
    if (!t) {
      this.result = { kind: 'info', body: 'Click inside a pipe table then edit table.' };
      return;
    }
    this.result = null;
    this.tbl = t;
  }

  addRow() {
    this.tbl.rows.push(Array(this.tbl.head.length).fill(''));
    this.tbl = { ...this.tbl };
  }

  delRow(i) {
    this.tbl.rows.splice(i, 1);
    this.tbl = { ...this.tbl };
  }

  addCol() {
    this.tbl.head.push('');
    this.tbl.align.push('left');
    this.tbl.rows.forEach((r) => r.push(''));
    this.tbl = { ...this.tbl };
  }

  delCol(c) {
    if (this.tbl.head.length <= 1) return;
    this.tbl.head.splice(c, 1);
    this.tbl.align.splice(c, 1);
    this.tbl.rows.forEach((r) => r.splice(c, 1));
    this.tbl = { ...this.tbl };
  }

  applyTable() {
    const t = this.tbl;
    const lines = this.text.split('\n');
    lines.splice(t.start, t.end - t.start + 1, ...serializeTable(t));
    this.setText(lines.join('\n'));
    this.dirty = true;
    this.queueDraft();
    this.tbl = null;
    this.updateComplete.then(() => {
      const ta = this.querySelector('textarea');
      if (ta) this.scrollToLine(ta, t.start);
    });
  }

  renderTableDialog() {
    const t = this.tbl;
    return html`
      <div class="overlay active" @click=${() => (this.tbl = null)}></div>
      <dialog class="active style-table-dialog">
        <h6 class="small">Edit table <span class="small-text secondary-text">
          lines ${t.start + 1}-${t.end + 1}</span></h6>
        <div class="scroll">
          <table class="border">
            <thead>
              <tr>
                ${t.head.map((h, c) => html`<th>
                  <nav class="no-space">
                    <input .value=${h} @input=${(e) => { t.head[c] = e.target.value; }}>
                    <button class="transparent circle small" title="Delete column"
                      ?disabled=${t.head.length <= 1} @click=${() => this.delCol(c)}>
                      <i class="small">close</i>
                    </button>
                  </nav>
                </th>`)}
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${t.rows.map((r, ri) => html`<tr>
                ${r.map((cell, c) => html`<td>
                  <input .value=${cell} @input=${(e) => { r[c] = e.target.value; }}>
                </td>`)}
                <td><button class="transparent circle small" title="Delete row"
                  @click=${() => this.delRow(ri)}><i class="small">delete</i></button></td>
              </tr>`)}
            </tbody>
          </table>
        </div>
        <nav class="wrap">
          ${btn('Add row', false, () => this.addRow(), 'border')}
          ${btn('Add column', false, () => this.addCol(), 'border')}
          <div class="max"></div>
          ${btn('Cancel', false, () => (this.tbl = null), 'border')}
          ${btn('Apply', false, () => this.applyTable())}
        </nav>
      </dialog>`;
  }

  get previewHtml() {
    if (this._pvSrc !== this.pvText) {
      this._pvSrc = this.pvText;
      this._pvHtml = marked.parse(this.pvText);
    }
    return this._pvHtml;
  }

  render() {
    if (this.text === null) {
      return html`<p>${this.result ? statusLine(this.result.kind, this.result.body) : spinner}</p>`;
    }
    return html`
      <nav class="wrap">
        <div class="field label suffix small no-margin small-width">
          <select @change=${(e) => this.jump(e)}>
            <option value="" selected></option>
            ${this.outline.map((h) => html`<option value=${h.line}>${h.label}</option>`)}
          </select>
          <label>Jump to section</label>
          <i>arrow_drop_down</i>
        </div>
        ${btn('Edit table', false, () => this.openTable(), 'border small-round')}
        ${chip('Wrap', this.wrap, () => this.toggleWrap())}
        ${chip('Preview', this.showPreview, () => this.togglePreview())}
        ${btn(this.busy ? 'Saving…' : 'Save', this.busy || !this.dirty, () => this.save())}
        ${this.busy ? spinner : nothing}
        ${this.result ? statusLine(this.result.kind, this.result.body)
          : this.dirty ? html`<span class="secondary-text">Unsaved changes</span>`
          : nothing}
      </nav>
      <div class="grid style-split">
        <div class="s12 ${this.showPreview ? 'l6' : ''}">
          <div class="field textarea border style-editor ${this.wrap ? 'wrap' : ''}">
            <textarea class="mono" rows="24" spellcheck="false" .value=${this.text}
              @input=${(e) => {
                this.text = e.target.value;
                this.dirty = true;
                this.result = null;
                this.queueDraft();
                this.queuePreview();
              }}></textarea>
          </div>
        </div>
        ${this.showPreview ? html`<div class="s12 l6">
          <article class="style-preview">${unsafeHTML(this.previewHtml)}</article>
        </div>` : nothing}
      </div>
      ${this.tbl ? this.renderTableDialog() : nothing}`;
  }
}
customElements.define('style-page', StylePage);
