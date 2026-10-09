import { BifrostElement, html, nothing, api, searchField, spinner, statusLine, btn } from './core.js';

const API = '/tables/api';
const PINPOINT = /^[A-Z0-9]{4,8}(?:\.P\d+)?(?:\.L\d+(?:-\d+)?(?:\.C\d+)?|\.C\d+|(?<=\.P\d+))$/;
const PAGE_SIZE = 10;

function contents(t) {
  if (!t.table) return t.notes === 1 ? 'this note' : 'these notes';
  return t.notes ? 'this table and its notes' : 'this table';
}

class TablesPage extends BifrostElement {
  static properties = {
    items: { state: true },
    loadError: { state: true },
    q: { state: true },
    results: { state: true },
    hi: { state: true },
    doomed: { state: true },
    deleting: { state: true },
    page: { state: true },
  };

  constructor() {
    super();
    this.items = null;
    this.loadError = '';
    this.q = '';
    this.results = [];
    this.hi = -1;
    this.doomed = null;
    this.deleting = false;
    this.page = 0;
    this._seq = 0;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
    this.search();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._timer);
  }

  async load() {
    try {
      this.items = (await api(`${API}/list`)).items;
      this.loadError = '';
    } catch (e) {
      this.loadError = e.message;
    }
  }

  queueSearch(q) {
    this.q = q;
    this.hi = -1;
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.search(), 250);
  }

  async search() {
    const seq = ++this._seq;
    let found = [];
    try {
      found = await api(`${API}/documents?q=${encodeURIComponent(this.q.trim())}`);
    } catch {
      found = [];
    }
    if (seq === this._seq) this.results = found;
  }

  open(id, page = 1) {
    location.href = `/tables/${id}${page > 1 ? `?page=${page}` : ''}`;
  }

  pick(it) {
    if (it.pinpoint) location.href = `/tables/at/${encodeURIComponent(it.pinpoint)}`;
    else this.open(it.id);
  }

  render() {
    const typed = this.q.replace(/\s+/g, '').toUpperCase();
    const items = [
      ...(PINPOINT.test(typed) ? [{ pinpoint: typed, label: typed, icon: 'location_on', mono: true }] : []),
      ...this.results.map((d) => ({
        id: d.id, label: d.title, thumb: `${API}/thumb/${d.id}`,
        sub: [d.pid, d.created?.slice(0, 10)].filter(Boolean).join(' · '),
      })),
    ];
    return html`
      <nav class="wrap">
        ${searchField({
    placeholder: 'Open a Paperless document', value: this.q, items, active: this.hi, width: 'large',
    onInput: (e) => this.queueSearch(e.target.value),
    onPick: (it) => this.pick(it),
    onEnter: () => {
      const it = items[this.hi] ?? (items[0]?.pinpoint || items.length === 1 ? items[0] : null);
      if (it) this.pick(it);
    },
    onMove: (d) => { if (items.length) this.hi = (this.hi + d + items.length) % items.length; },
    empty: 'No matches',
  })}
      </nav>
      ${this.renderList()}`;
  }

  row(t) {
    return html`<tr @click=${() => this.open(t.doc_id, t.page)}>
      <td class="mono">${t.pid}</td>
      <td title=${t.title || nothing}><div class="tables-doc">
        <span>${t.title || `#${t.doc_id}`}</span>
        ${t.page > 1 ? html`<span class="secondary-text">page ${t.page}</span>` : nothing}
      </div></td>
      <td><button class="circle transparent small" title="Delete" aria-label="Delete"
        @click=${(e) => { e.stopPropagation(); this.doomed = t; }}><i>delete</i></button></td>
    </tr>`;
  }

  renderList() {
    if (this.loadError) return html`<p>${statusLine('error', this.loadError)}</p>`;
    if (!this.items) return html`<p>${spinner}</p>`;
    if (!this.items.length) return nothing;
    const pages = Math.ceil(this.items.length / PAGE_SIZE);
    const page = Math.min(this.page, pages - 1);
    const first = page * PAGE_SIZE;
    const rows = this.items.slice(first, first + PAGE_SIZE);
    const padRows = pages > 1 ? PAGE_SIZE - rows.length : 0;
    return html`<div class="space"></div>
    <div class="scroll">
      <table class="sync-table tables-table">
        <colgroup><col class="col-pid"><col><col class="col-delete"></colgroup>
        <thead><tr>
          <th>Gramps ID</th>
          <th>Paperless document</th>
          <th></th>
        </tr></thead>
        <tbody>
          ${rows.map((t) => this.row(t))}
          ${Array.from({ length: padRows }, () => html`<tr class="pad"><td colspan="3">&nbsp;</td></tr>`)}
        </tbody>
      </table>
    </div>
    ${pages > 1 ? html`<nav class="pager">
      <button class="circle transparent" ?disabled=${page === 0}
        @click=${() => { this.page = page - 1; }} aria-label="Previous page"><i>chevron_left</i></button>
      <span class="pager-count">${first + 1}-${Math.min(first + PAGE_SIZE, this.items.length)} of ${this.items.length}</span>
      <button class="circle transparent" ?disabled=${page >= pages - 1}
        @click=${() => { this.page = page + 1; }} aria-label="Next page"><i>chevron_right</i></button>
    </nav>` : nothing}
    <dialog class="tbl-dialog" @close=${() => { this.doomed = null; }}>
      ${this.doomed ? html`<h5>Delete ${contents(this.doomed)}?</h5>
        <p>${this.doomed.title || `#${this.doomed.doc_id}`}${this.doomed.page > 1 ? `, page ${this.doomed.page}` : ''}</p>
        <nav class="right-align">
          ${btn('Cancel', this.deleting, () => { this.doomed = null; }, 'border')}
          ${btn(this.deleting ? 'Deleting...' : 'Delete', this.deleting, () => this.deleteTable(), 'error')}
        </nav>` : nothing}
    </dialog>`;
  }

  updated() {
    const dlg = this.querySelector('dialog.tbl-dialog');
    if (dlg && this.doomed && !dlg.open) dlg.showModal();
    else if (dlg && !this.doomed && dlg.open) dlg.close();
  }

  async deleteTable() {
    const t = this.doomed;
    this.deleting = true;
    try {
      await api(`${API}/doc/${t.doc_id}/page/${t.page}`, { method: 'DELETE' });
      this.doomed = null;
      await this.load();
    } catch (e) {
      this.loadError = e.message;
      this.doomed = null;
    } finally {
      this.deleting = false;
    }
  }
}
customElements.define('tables-page', TablesPage);
