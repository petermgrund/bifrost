import { BifrostElement, html, nothing, api, searchField, spinner, statusLine } from './core.js';

const API = '/tables/api';
const ADDRESS = /^[A-Z0-9]{4,8}(?:\.P\d+)?(?:\.L\d+(?:-\d+)?(?:\.C\d+)?|\.C\d+|(?<=\.P\d+))$/;
const pad = (n) => String(n).padStart(2, '0');
const count = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function day(iso) {
  const d = new Date(`${iso}Z`);
  return Number.isNaN(d.getTime()) ? '' : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

class TablesPage extends BifrostElement {
  static properties = {
    items: { state: true },
    loadError: { state: true },
    q: { state: true },
    results: { state: true },
    hi: { state: true },
  };

  constructor() {
    super();
    this.items = null;
    this.loadError = '';
    this.q = '';
    this.results = [];
    this.hi = -1;
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
    if (it.address) location.href = `/tables/at/${encodeURIComponent(it.address)}`;
    else this.open(it.id);
  }

  render() {
    const typed = this.q.replace(/\s+/g, '').toUpperCase();
    const items = [
      ...(ADDRESS.test(typed) ? [{ address: typed, label: typed, icon: 'location_on', mono: true }] : []),
      ...this.results.map((d) => ({
        id: d.id, label: d.title, thumb: `${API}/thumb/${d.id}`,
        sub: `#${d.id}${d.created ? ` · ${d.created.slice(0, 10)}` : ''}`,
      })),
    ];
    return html`
      <nav class="wrap">
        ${searchField({
    placeholder: 'Open a Paperless document', value: this.q, items, active: this.hi, width: 'large',
    onInput: (e) => this.queueSearch(e.target.value),
    onPick: (it) => this.pick(it),
    onEnter: () => {
      const it = items[this.hi] ?? (items[0]?.address || items.length === 1 ? items[0] : null);
      if (it) this.pick(it);
    },
    onMove: (d) => { if (items.length) this.hi = (this.hi + d + items.length) % items.length; },
    empty: 'No matches',
  })}
      </nav>
      ${this.renderList()}`;
  }

  facts(t) {
    const parts = t.page > 1 ? [`Page ${t.page}`] : [];
    if (t.table) parts.push(count(t.lines, 'line'), count(t.columns, 'column'), count(t.filled, 'value'));
    if (t.notes) parts.push(count(t.notes, 'note'));
    return parts.join(' · ');
  }

  renderList() {
    if (this.loadError) return html`<p>${statusLine('error', this.loadError)}</p>`;
    if (!this.items) return html`<p>${spinner}</p>`;
    if (!this.items.length) return nothing;
    return html`<ul class="list border tables-list">
      ${this.items.map((t) => html`<li class="wave" @click=${() => this.open(t.doc_id, t.page)}>
        <img class="tbl-thumb" src="${API}/thumb/${t.doc_id}" alt="" loading="lazy">
        <div class="max">
          <div>${t.title || `#${t.doc_id}`}</div>
          <div class="small-text secondary-text">${this.facts(t)}</div>
        </div>
        <span class="small-text secondary-text">${day(t.updated_at)}</span>
      </li>`)}
    </ul>`;
  }
}
customElements.define('tables-page', TablesPage);
