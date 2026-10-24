import { BifrostElement, html, nothing, api, post, btn, field, selectField,
         spinner, statusLine, emptyRow } from './core.js';

const PAGE_SIZE = 25;
const API = '/codes/api';

const FILTERS = [
  ['all', 'All'], ['reserved', 'Reserved'], ['in use', 'In use'],
  ['withdrawn', 'Withdrawn'], ['attention', 'Needs attention'],
];
const STATUS_CHIP = {
  reserved: ['', 'Reserved'],
  'in use': ['primary-container', 'In use'],
  withdrawn: ['surface-variant', 'Withdrawn'],
};
const COUNTS = Array.from({ length: 20 }, (_, i) => i + 1);
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

const chip = (label, on, onClick) => html`<button class="chip ${on ? 'fill' : ''}"
  aria-pressed=${on ? 'true' : 'false'} @click=${onClick}>${label}</button>`;

const bare = (v) => v.replace(/[\s-]+/g, '').toUpperCase();

function blankForm(mode = 'mint') {
  return { mode, code: '', count: 1, reason: '', superseded_by: '' };
}

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
    form: { state: true },
    touched: { state: true },
    formError: { state: true },
    saving: { state: true },
    minted: { state: true },
    copied: { state: true },
    thumbGone: { state: true },
  };

  constructor() {
    super();
    this.data = null;
    this.loadError = '';
    this.q = '';
    this.filter = 'all';
    this.page = 0;
    this.toast = null;     // { msg, failed } for the snackbar
    this.dlg = null;       // 'new' | 'details' | 'withdraw' | 'delete'
    this.target = null;    // the row the dialog is about
    this.form = blankForm();
    this.touched = false;
    this.formError = '';
    this.saving = false;
    this.minted = null;    // rows of the codes just minted or claimed
    this.copied = '';
    this.thumbGone = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._toastTimer);
    clearTimeout(this._copiedTimer);
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

  // ---- list

  get items() { return this.data?.items || []; }

  matchesQuery(r, q) {
    if (!q) return true;
    const code = bare(q);
    if (code && r.code.includes(code)) return true;
    const hay = [r.title, r.withdrawn_reason, r.superseded_by,
      ...r.paperless.map((d) => d.id), ...r.immich.map((a) => a.id)];
    return hay.some((v) => v && String(v).toLowerCase().includes(q));
  }

  matchesFilter(r, f) {
    if (f === 'all') return true;
    if (f === 'attention') return Boolean(r.attention);
    return r.status === f;
  }

  setQuery(v) { this.q = v; this.page = 0; }
  setFilter(f) { this.filter = f; this.page = 0; }

  async copy(code) {
    let ok = false;
    try {
      await navigator.clipboard.writeText(code);
      ok = true;
    } catch { }
    if (!ok) {
      // plain http on the LAN has no async clipboard; select a hidden field inside the open dialog
      const box = this.querySelector('dialog[open]') || document.body;
      const ta = Object.assign(document.createElement('textarea'), { value: code, readOnly: true });
      ta.setAttribute('aria-hidden', 'true');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      const back = document.activeElement;
      box.append(ta);
      ta.focus();
      ta.select();
      try { ok = document.execCommand('copy'); } catch { }
      ta.remove();
      back?.focus();
    }
    this.copied = ok ? code : '';
    if (!ok) this.formError = `Could not copy ${code}. Select it and copy by hand.`;
    clearTimeout(this._copiedTimer);
    this._copiedTimer = setTimeout(() => { this.copied = ''; }, 2500);
  }

  // ---- dialogs

  open(dlg, r = null, form = blankForm()) {
    this.dlg = dlg;
    this.target = r;
    this.form = form;
    this.minted = null;
    this.touched = false;
    this.formError = '';
    this.thumbGone = false;
  }

  openNew() { this.open('new'); }
  openDetails(r) { this.open('details', r, { ...blankForm(), superseded_by: r.superseded_by || '' }); }
  openWithdraw(r) { this.open('withdraw', r); }
  openDelete(r) { this.open('delete', r); }

  openCode(code) {
    const r = this.items.find((x) => x.code === code);
    if (r) this.openDetails(r);
  }

  closeDialog() {
    if (this.saving) return;
    this.dlg = null;
    this.target = null;
    this.minted = null;
    this.formError = '';
  }

  setForm(patch) { this.form = { ...this.form, ...patch }; this.formError = ''; }

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
    } else if (this.dlg && changed.has('minted')) {
      focusFirst();
    }
  }

  async submitNew() {
    const f = this.form;
    const claim = f.mode === 'claim';
    const count = claim ? 1 : Number(f.count) || 1;
    this.touched = true;
    if ((claim && !f.code.trim()) || this.saving) return;
    this.saving = true;
    this.formError = '';
    try {
      const r = claim
        ? await post(`${API}/claim`, { code: f.code })
        : await post(`${API}/mint`, { count });
      this.minted = r.items;
      this.load();
    } catch (e) {
      this.formError = why(e);
    } finally {
      this.saving = false;
    }
  }

  async change(done, request) {
    if (this.saving) return;
    this.saving = true;
    this.formError = '';
    try {
      await request();
      this.saving = false;
      this.closeDialog();
      this.say(done);
      this.load();
    } catch (e) {
      this.formError = why(e);
    } finally {
      this.saving = false;
    }
  }

  get supersedeDirty() {
    const r = this.target;
    return r?.status === 'withdrawn' && bare(this.form.superseded_by) !== (r.superseded_by || '');
  }

  submitSupersede() {
    const { code } = this.target;
    if (!this.supersedeDirty) return;
    this.change(`Saved ${code}`, () => api(`${API}/${encodeURIComponent(code)}`, {
      method: 'PATCH', body: JSON.stringify({ superseded_by: this.form.superseded_by }),
    }));
  }

  submitWithdraw() {
    const { code } = this.target;
    this.touched = true;
    if (!this.form.reason.trim()) return;
    this.change(`${code} withdrawn`, () => post(`${API}/${encodeURIComponent(code)}/withdraw`,
      { reason: this.form.reason, superseded_by: this.form.superseded_by }));
  }

  submitDelete() {
    const { code } = this.target;
    this.change(`${code} deleted`, () => api(`${API}/${encodeURIComponent(code)}`, { method: 'DELETE' }));
  }

  // ---- rendering

  render() {
    return html`
      ${this.renderToolbar()}
      ${this.renderList()}
      <dialog class="codes-dialog" aria-labelledby="codes-dialog-title"
        @cancel=${(e) => { if (this.saving) e.preventDefault(); }}
        @close=${() => { if (this.dlg) this.closeDialog(); }}>
        ${this.dlg === 'new' ? (this.minted ? this.renderMinted() : this.renderNewForm())
          : this.dlg === 'details' ? this.renderDetails()
            : this.dlg === 'withdraw' ? this.renderWithdrawForm()
              : this.dlg === 'delete' ? this.renderDeleteForm() : nothing}
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
        <button @click=${() => this.openNew()}><i>add</i><span>New code</span></button>
        <a class="button border" href="${API}/export.csv" download><i>download</i><span>Download CSV</span></a>
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
    return html`<tr>
      <td class="mono">${r.code}</td>
      <td>
        <span class="chip small ${cls}">${label}</span>
        ${r.attention ? html`<i class="error-text" title=${r.attention} aria-label=${r.attention}>error</i>`
          : nothing}
      </td>
      <td title=${r.title || nothing}>${r.title || html`<span class="secondary-text">No title</span>`}</td>
      <td class="small-text" title=${minute(r.updated) || nothing}>${day(r.updated)}</td>
      <td>${this.actions(r)}</td>
    </tr>`;
  }

  actions(r) {
    if (!r.in_ledger) return nothing;
    const act = (icon, tip, name, onClick) => html`<button class="circle transparent small"
        aria-label=${name} @click=${onClick}>
        <i>${icon}</i><div class="tooltip left">${tip}</div></button>`;
    return html`<div class="codes-actions">
      ${act('info', 'Details', `Details of ${r.code}`, () => this.openDetails(r))}
      ${r.status === 'withdrawn' ? html`<span></span>`
        : act('block', 'Withdraw', `Withdraw ${r.code}`, () => this.openWithdraw(r))}
    </div>`;
  }

  codeLink(c) {
    return html`<a class="link mono" href="#" @click=${(e) => { e.preventDefault(); this.openCode(c); }}>${c}</a>`;
  }

  facts(r) {
    const rows = [
      r.type && ['Type', TYPES[r.type]],
      (r.type || r.title) && ['Title', r.title || 'No title'],
      r.withdrawn_reason && ['Withdrawn', r.withdrawn_reason],
      r.superseded_by && ['Superseded by', this.codeLink(r.superseded_by)],
      r.supersedes.length && ['Supersedes', r.supersedes.map((c, i) => html`${i ? ', ' : ''}${this.codeLink(c)}`)],
    ].filter(Boolean);
    return html`
      ${rows.length ? html`<table>
        <tbody>
          ${rows.map(([k, v]) => html`<tr><td class="min secondary-text">${k}</td><td>${v}</td></tr>`)}
        </tbody>
      </table>` : nothing}
      ${r.attention ? html`<p>${statusLine('error', r.attention)}</p>` : nothing}`;
  }

  history(r) {
    if (!r.history.length) return nothing;
    return html`
      <h6 class="small">History</h6>
      <table>
        <tbody>
          ${r.history.map((e) => html`<tr>
            <td class="min small-text secondary-text">${minute(e.at)}</td>
            <td>${e.what}${e.detail ? html`<span class="secondary-text">: ${e.detail}</span>` : nothing}</td>
          </tr>`)}
        </tbody>
      </table>`;
  }

  renderNewForm() {
    const f = this.form;
    const claim = f.mode === 'claim';
    const count = Number(f.count) || 1;
    const codeError = claim && this.touched && !f.code.trim() ? 'Type the code as written' : '';
    const submit = () => this.submitNew();
    return html`
      <h5 id="codes-dialog-title">New code</h5>
      <nav class="wrap">
        ${chip('Mint a new code', !claim, () => this.setForm({ mode: 'mint' }))}
        ${chip('I already wrote a code', claim, () => this.setForm({ mode: 'claim' }))}
      </nav>
      <div class="space"></div>
      ${claim
        ? field('Code as written', f.code, (e) => this.setForm({ code: e.target.value }),
          { mono: true, upper: true, placeholder: ' ', error: codeError, onEnter: submit })
        : selectField('How many codes', count, COUNTS,
          (e) => this.setForm({ count: Number(e.target.value) }))}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Cancel', this.saving, () => this.closeDialog(), 'border')}
        ${btn(this.saving ? 'Saving...' : claim ? 'Add to the ledger'
          : count > 1 ? `Mint ${count} codes` : 'Mint code', this.saving, submit)}
      </nav>`;
  }

  renderMinted() {
    const list = this.minted || [];
    return html`
      <h5 id="codes-dialog-title">${list.length === 1 ? 'Your new code' : `Your ${list.length} new codes`}</h5>
      ${list.map((m) => html`
        <nav class="wrap">
          <h3 class="mono max" aria-label=${m.code.split('').join(' ')}>${m.code}</h3>
          <button class="circle transparent" aria-label="Copy ${m.code}" @click=${() => this.copy(m.code)}>
            <i>${this.copied === m.code ? 'check' : 'content_copy'}</i></button>
          ${this.copied === m.code ? html`<span class="small-text" role="status">Copied</span>` : nothing}
        </nav>`)}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Mint more', false, () => this.openNew(), 'border')}
        <button autofocus @click=${() => this.closeDialog()}>Done</button>
      </nav>`;
  }

  renderDetails() {
    const r = this.target;
    const withdrawn = r.status === 'withdrawn';
    const dirty = this.supersedeDirty;
    return html`
      <div class="codes-head">
        <div class="max">
          <h5 id="codes-dialog-title"><span class="mono">${r.code}</span></h5>
          ${this.facts(r)}
          ${withdrawn ? field('Superseded by', this.form.superseded_by,
            (e) => this.setForm({ superseded_by: e.target.value }),
            { mono: true, upper: true, placeholder: ' ', onEnter: () => this.submitSupersede() }) : nothing}
        </div>
        ${r.gramps && !this.thumbGone ? html`<img class="codes-thumb" alt=""
          src="${API}/${encodeURIComponent(r.code)}/thumbnail"
          @error=${() => { this.thumbGone = true; }}>` : nothing}
      </div>
      ${this.history(r)}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav>
        ${r.deletable ? btn('Delete', this.saving, () => this.openDelete(r), 'border error-text') : nothing}
        <div class="max"></div>
        ${withdrawn ? html`
          ${btn(dirty ? 'Cancel' : 'Close', this.saving, () => this.closeDialog(), 'border')}
          ${btn(this.saving ? 'Saving...' : 'Save', this.saving || !dirty, () => this.submitSupersede())}`
          : html`<button autofocus @click=${() => this.closeDialog()}>Close</button>`}
      </nav>`;
  }

  renderDeleteForm() {
    const r = this.target;
    return html`
      <h5 id="codes-dialog-title">Delete <span class="mono">${r.code}</span>?</h5>
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Cancel', this.saving, () => this.openDetails(r), 'border')}
        ${btn(this.saving ? 'Deleting...' : 'Delete', this.saving, () => this.submitDelete(), 'error')}
      </nav>`;
  }

  renderWithdrawForm() {
    const r = this.target;
    const reasonError = this.touched && !this.form.reason.trim() ? 'Give a reason' : '';
    const submit = () => this.submitWithdraw();
    return html`
      <h5 id="codes-dialog-title">Withdraw <span class="mono">${r.code}</span>?</h5>
      ${r.status === 'in use' ? html`<p>${statusLine('error',
        'This code is in use so no changes will affect Gramps, Paperless or Immich.')}</p>` : nothing}
      ${field('Reason', this.form.reason, (e) => this.setForm({ reason: e.target.value }),
        { placeholder: ' ', error: reasonError, onEnter: submit })}
      ${field('Superseded by', this.form.superseded_by, (e) => this.setForm({ superseded_by: e.target.value }),
        { mono: true, upper: true, placeholder: ' ', onEnter: submit })}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Cancel', this.saving, () => this.closeDialog(), 'border')}
        ${btn(this.saving ? 'Withdrawing...' : 'Withdraw', this.saving, submit, 'error')}
      </nav>`;
  }
}
customElements.define('codes-page', CodesPage);
