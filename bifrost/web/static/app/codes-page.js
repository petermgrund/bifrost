import { BifrostElement, html, nothing, api, post, btn, field, spinner, statusLine, emptyRow } from './core.js';

const PAGE_SIZE = 25;
const API = '/codes/api';

const FILTERS = [
  ['all', 'All'], ['in use', 'In use'], ['withdrawn', 'Withdrawn'], ['attention', 'Needs attention'],
];
const STATUS_CHIP = {
  'in use': ['primary-container', 'In use'],
  withdrawn: ['surface-variant', 'Withdrawn'],
};
const TYPES = { image: 'Image', document: 'Document' };

const pad = (n) => String(n).padStart(2, '0');

function local(iso) {
  if (!iso) return null;
  const d = new Date(/(Z|[+-]\d\d:\d\d)$/.test(iso) ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function day(iso) {
  const d = local(iso);
  return d ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` : '';
}

function minute(iso) {
  const d = local(iso);
  return d ? `${day(iso)} ${pad(d.getHours())}:${pad(d.getMinutes())}` : '';
}

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

const chip = (label, on, onClick) => html`<button class="chip ${on ? 'fill' : ''}"
  aria-pressed=${on ? 'true' : 'false'} @click=${onClick}>${label}</button>`;

const bare = (v) => v.replace(/[\s-]+/g, '').toUpperCase();

class CodesPage extends BifrostElement {
  static properties = {
    data: { state: true },
    loadError: { state: true },
    q: { state: true },
    filter: { state: true },
    page: { state: true },
    toast: { state: true },
    dlg: { state: true },
    target: { state: true },
    reason: { state: true },
    touched: { state: true },
    formError: { state: true },
    saving: { state: true },
    thumbGone: { state: true },
  };

  constructor() {
    super();
    this.data = null;
    this.loadError = '';
    this.q = '';
    this.filter = 'all';
    this.page = 0;
    this.toast = null;
    this.dlg = null;
    this.target = null;
    this.reason = '';
    this.touched = false;
    this.formError = '';
    this.saving = false;
    this.thumbGone = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._toastTimer);
  }

  async load() {
    try {
      this.data = await api(`${API}/list`);
      this.loadError = '';
    } catch (e) {
      this.loadError = why(e);
    }
  }

  say(msg, failed = false) {
    this.toast = { msg, failed };
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { this.toast = null; }, failed ? 8000 : 5000);
  }

  get items() { return this.data?.items || []; }

  matchesQuery(r, q) {
    if (!q) return true;
    const code = bare(q);
    if (code && r.code.includes(code)) return true;
    const hay = [r.title, r.withdrawn_reason, ...r.paperless.map((d) => d.id), ...r.immich.map((a) => a.id)];
    return hay.some((v) => v && String(v).toLowerCase().includes(q));
  }

  matchesFilter(r, f) {
    if (f === 'all') return true;
    if (f === 'attention') return Boolean(r.attention);
    return r.status === f;
  }

  setQuery(v) { this.q = v; this.page = 0; }
  setFilter(f) { this.filter = f; this.page = 0; }

  open(dlg, r) {
    this.dlg = dlg;
    this.target = r;
    this.reason = '';
    this.touched = false;
    this.formError = '';
    this.thumbGone = false;
  }

  closeDialog() {
    if (this.saving) return;
    this.dlg = null;
    this.target = null;
    this.formError = '';
  }

  updated(changed) {
    const dlg = this.querySelector('dialog.codes-dialog');
    if (!dlg) return;
    const focusFirst = () => (dlg.querySelector('[autofocus]')
      || dlg.querySelector('input[type="text"]'))?.focus();
    if (this.dlg && !dlg.open) {
      dlg.showModal();
      focusFirst();
    } else if (!this.dlg && dlg.open) {
      dlg.close();
    }
  }

  async submitWithdraw() {
    const { code } = this.target;
    this.touched = true;
    if (!this.reason.trim() || this.saving) return;
    this.saving = true;
    this.formError = '';
    try {
      await post(`${API}/${encodeURIComponent(code)}/withdraw`, { reason: this.reason });
      this.saving = false;
      this.closeDialog();
      this.say(`${code} withdrawn`);
      this.load();
    } catch (e) {
      this.formError = why(e);
    } finally {
      this.saving = false;
    }
  }

  render() {
    return html`
      ${this.renderToolbar()}
      ${this.renderList()}
      <dialog class="codes-dialog" aria-labelledby="codes-dialog-title"
        @cancel=${(e) => { if (this.saving) e.preventDefault(); }}
        @close=${() => { if (this.dlg) this.closeDialog(); }}>
        ${this.dlg === 'details' ? this.renderDetails()
          : this.dlg === 'withdraw' ? this.renderWithdrawForm() : nothing}
      </dialog>
      <div class="snackbar ${this.toast ? 'active' : ''} ${this.toast?.failed ? 'error' : ''}"
        role="status" aria-live="polite">
        ${this.toast ? html`<i>${this.toast.failed ? 'error' : 'check_circle'}</i>
          <span class="max">${this.toast.msg}</span>` : nothing}
      </div>`;
  }

  renderToolbar() {
    const q = this.q.trim().toLowerCase();
    const shown = this.items.filter((r) => this.matchesQuery(r, q));
    const n = (f) => shown.filter((r) => this.matchesFilter(r, f)).length;
    return html`
      <nav class="wrap">
        <div class="field prefix border small no-margin max">
          <i>search</i>
          <input type="text" placeholder="Search codes"
            aria-label="Search codes" .value=${this.q} @input=${(e) => this.setQuery(e.target.value)}>
        </div>
      </nav>
      <div class="space"></div>
      <nav class="wrap">
        ${FILTERS.map(([f, label]) => chip(html`<span>${label}</span><span class="mono">${n(f)}</span>`,
          this.filter === f, () => this.setFilter(f)))}
      </nav>`;
  }

  renderList() {
    if (!this.data) {
      return html`<p>${this.loadError ? statusLine('error', this.loadError) : spinner}</p>`;
    }
    const q = this.q.trim().toLowerCase();
    const rows = this.items.filter((r) => this.matchesQuery(r, q) && this.matchesFilter(r, this.filter));
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    const page = Math.min(this.page, pages - 1);
    const first = page * PAGE_SIZE;
    return html`
      ${this.loadError ? html`<p>${statusLine('error', this.loadError)}</p>` : nothing}
      ${this.data.gramps === 'unknown' ? html`<p>${statusLine('error',
        `Gramps could not be read. (${this.data.gramps_error || 'no answer'})`)}</p>` : nothing}
      <div class="space"></div>
      <div class="scroll">
        <table class="sync-table codes-table">
          <colgroup>
            <col class="col-code"><col class="col-status"><col>
            <col class="col-updated"><col class="col-actions">
          </colgroup>
          <thead><tr>
            <th>Code</th>
            <th>Status</th>
            <th>Title or file name</th>
            <th>Last updated</th>
            <th>Actions</th>
          </tr></thead>
          <tbody>
            ${rows.length ? rows.slice(first, first + PAGE_SIZE).map((r) => this.row(r))
              : emptyRow(5, this.items.length ? 'No codes match' : 'No codes yet')}
          </tbody>
        </table>
      </div>
      ${pages > 1 ? html`<nav class="pager">
        <button class="circle transparent" ?disabled=${page === 0}
          @click=${() => { this.page = page - 1; }} aria-label="Previous page"><i>chevron_left</i></button>
        <span class="pager-count">${first + 1}-${Math.min(first + PAGE_SIZE, rows.length)} of ${rows.length}</span>
        <button class="circle transparent" ?disabled=${page >= pages - 1}
          @click=${() => { this.page = page + 1; }} aria-label="Next page"><i>chevron_right</i></button>
      </nav>` : nothing}`;
  }

  row(r) {
    const [cls, label] = STATUS_CHIP[r.status] || ['', r.status];
    const act = (icon, tip, name, onClick) => html`<button class="circle transparent small"
        aria-label=${name} @click=${onClick}>
        <i>${icon}</i><div class="tooltip left">${tip}</div></button>`;
    return html`<tr>
      <td class="mono">${r.code}</td>
      <td>
        <span class="chip small ${cls}">${label}</span>
        ${r.attention ? html`<i class="error-text" title=${r.attention} aria-label=${r.attention}>error</i>`
          : nothing}
      </td>
      <td title=${r.title || nothing}>${r.title || html`<span class="secondary-text">No title</span>`}</td>
      <td class="small-text" title=${minute(r.updated) || nothing}>${day(r.updated)}</td>
      <td><div class="codes-actions">
        ${act('info', 'Details', `Details of ${r.code}`, () => this.open('details', r))}
        ${r.status === 'withdrawn' ? html`<span></span>`
          : act('block', 'Withdraw', `Withdraw ${r.code}`, () => this.open('withdraw', r))}
      </div></td>
    </tr>`;
  }

  facts(r) {
    const rows = [
      r.type && ['Type', TYPES[r.type]],
      (r.type || r.title) && ['Title', r.title || 'No title'],
      r.paperless.length && ['Paperless', r.paperless.map((d, i) => html`${i ? ', ' : ''}${d.url
        ? html`<a class="link" href=${d.url} target="_blank" rel="noopener">${d.id}</a>` : d.id}`)],
      r.gramps_url && ['Gramps', html`<a class="link mono" href=${r.gramps_url} target="_blank" rel="noopener">${r.code}</a>`],
      r.withdrawn && ['Withdrawn', `${r.withdrawn}${r.withdrawn_reason ? `: ${r.withdrawn_reason}` : ''}`],
    ].filter(Boolean);
    return html`
      ${rows.length ? html`<table>
        <tbody>
          ${rows.map(([k, v]) => html`<tr><td class="min secondary-text">${k}</td><td>${v}</td></tr>`)}
        </tbody>
      </table>` : nothing}
      ${r.attention ? html`<p>${statusLine('error', r.attention)}</p>` : nothing}`;
  }

  renderDetails() {
    const r = this.target;
    return html`
      <div class="codes-head">
        <div class="max">
          <h5 id="codes-dialog-title"><span class="mono">${r.code}</span></h5>
          ${this.facts(r)}
        </div>
        ${r.gramps && !this.thumbGone ? html`<img class="codes-thumb" alt=""
          src="${API}/${encodeURIComponent(r.code)}/thumbnail"
          @error=${() => { this.thumbGone = true; }}>` : nothing}
      </div>
      <nav class="right-align">
        <button autofocus @click=${() => this.closeDialog()}>Close</button>
      </nav>`;
  }

  renderWithdrawForm() {
    const r = this.target;
    const reasonError = this.touched && !this.reason.trim() ? 'Give a reason' : '';
    const submit = () => this.submitWithdraw();
    return html`
      <h5 id="codes-dialog-title">Withdraw <span class="mono">${r.code}</span>?</h5>
      ${field('Reason', this.reason, (e) => { this.reason = e.target.value; this.formError = ''; },
        { placeholder: ' ', error: reasonError, onEnter: submit })}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Cancel', this.saving, () => this.closeDialog(), 'border')}
        ${btn(this.saving ? 'Withdrawing...' : 'Withdraw', this.saving, submit, 'error')}
      </nav>`;
  }
}
customElements.define('codes-page', CodesPage);
