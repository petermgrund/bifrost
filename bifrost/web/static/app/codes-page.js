import { BifrostElement, html, nothing, api, post, btn, field, selectField,
         spinner, statusLine, emptyRow } from './core.js';

const PAGE_SIZE = 25;
const API = '/codes/api';

const FILTERS = [
  ['all', 'All'], ['reserved', 'Reserved'], ['penciled', 'Penciled'],
  ['in use', 'In use'], ['withdrawn', 'Withdrawn'], ['attention', 'Needs attention'],
];
const STATUS_CHIP = {
  reserved: ['', 'Reserved'],
  penciled: ['secondary-container', 'Penciled'],
  'in use': ['primary-container', 'In use'],
  withdrawn: ['surface-variant', 'Withdrawn'],
};
const PENCIL_HELP = 'Pencil the code on the item: on the back of a photograph, on a document’s folder, '
  + 'or inside the back cover of an album or scrapbook. Never on an album page.';
const COUNTS = Array.from({ length: 20 }, (_, i) => i + 1);

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

function blankForm(mode = 'mint') {
  return { mode, code: '', note: '', notes: '', count: 1, reason: '', instance: '' };
}

const TYPES = { image: ['Image', 'Immich'], document: ['Document', 'Paperless'] };

class CodesPage extends BifrostElement {
  static properties = {
    data: { state: true },
    loadError: { state: true },
    q: { state: true },
    filter: { state: true },
    page: { state: true },
    busy: { state: true },
    toast: { state: true },
    dlg: { state: true },
    target: { state: true },
    form: { state: true },
    touched: { state: true },
    formError: { state: true },
    saving: { state: true },
    minted: { state: true },
    copied: { state: true },
    adding: { state: true },
    thumbGone: { state: true },
    mintNotes: { state: true },
  };

  constructor() {
    super();
    this.data = null;
    this.loadError = '';
    this.q = '';
    this.filter = 'all';
    this.page = 0;
    this.busy = '';
    this.toast = null;     // { msg, failed } for the snackbar
    this.dlg = null;       // 'new' | 'edit' | 'withdraw'
    this.target = null;    // the row being edited or withdrawn
    this.form = blankForm();
    this.touched = false;
    this.formError = '';
    this.saving = false;
    this.minted = null;    // rows of the codes just minted or claimed
    this.copied = '';
    this.adding = false;
    this.thumbGone = false;
    this.mintNotes = {};
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
    const bare = q.replace(/[\s-]+/g, '').toUpperCase();
    if (bare && r.code.includes(bare)) return true;
    const hay = [r.note, r.title, r.notes, r.withdrawn_reason,
      ...r.paperless.map((d) => d.id), ...r.immich.map((a) => a.id), ...r.scans,
      ...r.instances.filter((i) => i.id).map((i) => i.text)];
    return hay.some((v) => v && String(v).toLowerCase().includes(q));
  }

  matchesFilter(r, f) {
    if (f === 'all') return true;
    if (f === 'attention') return Boolean(r.attention);
    return r.status === f;
  }

  setQuery(v) { this.q = v; this.page = 0; }
  setFilter(f) { this.filter = f; this.page = 0; }

  // ---- row actions

  async pencil(code, fromDialog = false) {
    this.busy = code;
    try {
      const r = await post(`${API}/${encodeURIComponent(code)}/penciled`);
      if (fromDialog && this.minted) {
        this.minted = this.minted.map((m) => (m.code === code ? r.item : m));
      } else {
        this.say(`${code} marked penciled`);
      }
      await this.load();
    } catch (e) {
      if (fromDialog) this.formError = why(e);
      else this.say(why(e), true);
    } finally {
      this.busy = '';
    }
  }

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

  openNew() {
    this.form = blankForm();
    this.target = null;
    this.minted = null;
    this.mintNotes = {};
    this.touched = false;
    this.formError = '';
    this.dlg = 'new';
  }

  openEdit(r) {
    this.target = r;
    this.form = { ...blankForm(), note: r.note || '', notes: r.notes || '' };
    this.touched = false;
    this.formError = '';
    this.thumbGone = false;
    this.dlg = 'edit';
  }

  async popupCall(code, path, opts = { method: 'POST' }) {
    if (this.adding) return false;
    this.adding = true;
    this.formError = '';
    try {
      await api(`${API}/${encodeURIComponent(code)}${path}`, opts);
      await this.load();
      this.target = this.items.find((r) => r.code === code) || this.target;
      return true;
    } catch (e) {
      this.formError = why(e);
      return false;
    } finally {
      this.adding = false;
    }
  }

  async addInstance(code) {
    const value = this.form.instance.trim();
    if (!value) return;
    const body = JSON.stringify({ value });
    if (await this.popupCall(code, '/instances', { method: 'POST', body })) {
      this.form = { ...this.form, instance: '' };
    }
  }

  removeInstance(code, id) { this.popupCall(code, `/instances/${id}`, { method: 'DELETE' }); }

  crossOut(code, id) { this.popupCall(code, `/pencilings/${id}/cross-out`); }

  openWithdraw(r) {
    this.target = r;
    this.form = blankForm();
    this.touched = false;
    this.formError = '';
    this.dlg = 'withdraw';
  }

  closeDialog() {
    if (this.saving) return;
    const drafts = this.minted ? this.mintDrafts() : [];
    if (drafts.length) {
      this.saveMintNotes(drafts).then((failed) => {
        if (failed.length) this.say(`Notes not saved: ${failed.join('; ')}`, true);
      });
    }
    this.dlg = null;
    this.target = null;
    this.minted = null;
    this.mintNotes = {};
    this.formError = '';
  }

  mintDrafts() { return Object.entries(this.mintNotes).filter(([, text]) => text.trim()); }

  async saveMintNotes(drafts = this.mintDrafts()) {
    const failed = [];
    for (const [code, notes] of drafts) {
      try {
        await api(`${API}/${encodeURIComponent(code)}`, { method: 'PATCH', body: JSON.stringify({ notes }) });
      } catch (e) {
        failed.push(`${code}: ${why(e)}`);
      }
    }
    if (drafts.length) this.load();
    return failed;
  }

  async finishMinted(more = false) {
    if (this.saving) return;
    this.saving = true;
    const failed = await this.saveMintNotes();
    this.saving = false;
    if (failed.length) {
      this.formError = `Notes not saved: ${failed.join('; ')}`;
      return;
    }
    this.mintNotes = {};
    if (more) this.openNew();
    else this.closeDialog();
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
    const body = { note: count === 1 ? f.note : '' };
    try {
      const r = claim
        ? await post(`${API}/claim`, { ...body, code: f.code })
        : await post(`${API}/mint`, { ...body, count });
      this.minted = r.items;
      this.load();
    } catch (e) {
      this.formError = why(e);
    } finally {
      this.saving = false;
    }
  }

  editChanges() {
    const r = this.target;
    const f = this.form;
    const out = {};
    if (r.type) return out;
    if (f.note !== (r.note || '')) out.note = f.note;
    if (f.notes !== (r.notes || '')) out.notes = f.notes;
    return out;
  }

  async submitEdit() {
    const code = this.target.code;
    const changes = this.editChanges();
    if (this.saving || !Object.keys(changes).length) return;
    this.saving = true;
    this.formError = '';
    try {
      await api(`${API}/${encodeURIComponent(code)}`, {
        method: 'PATCH',
        body: JSON.stringify(changes),
      });
      this.saving = false;
      this.closeDialog();
      this.say(`Saved ${code}`);
      this.load();
    } catch (e) {
      this.formError = why(e);
    } finally {
      this.saving = false;
    }
  }

  async submitWithdraw() {
    const code = this.target.code;
    this.touched = true;
    if (!this.form.reason.trim() || this.saving) return;
    this.saving = true;
    this.formError = '';
    try {
      await post(`${API}/${encodeURIComponent(code)}/withdraw`, { reason: this.form.reason });
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

  // ---- rendering

  render() {
    return html`
      ${this.renderToolbar()}
      ${this.renderList()}
      <dialog class="codes-dialog" aria-labelledby="codes-dialog-title"
        @cancel=${(e) => { if (this.saving) e.preventDefault(); }}
        @close=${() => { if (this.dlg) this.closeDialog(); }}>
        ${this.dlg === 'new' ? (this.minted ? this.renderMinted() : this.renderNewForm())
          : this.dlg === 'edit' ? this.renderEditForm()
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
          <input type="text" placeholder="Search codes and descriptions"
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
        <table class="border codes-table">
          <colgroup>
            <col class="col-code"><col class="col-status"><col>
            <col class="col-updated"><col class="col-actions">
          </colgroup>
          <thead><tr>
            <th>Code</th>
            <th>Status</th>
            <th>Title or file name</th>
            <th>Last updated</th>
            <th><span class="secondary-text">Actions</span></th>
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
        <span class="chip ${cls}">${label}</span>
        ${r.attention ? html`<div class="small-text error-text">${r.attention}</div>` : nothing}
      </td>
      <td>${this.whatItIs(r)}</td>
      <td class="small-text" title=${minute(r.updated) || nothing}>${day(r.updated)}</td>
      <td>${this.actions(r)}</td>
    </tr>`;
  }

  whatItIs(r) {
    const main = r.title || r.note;
    return html`
      ${main ? html`<div>${main}</div>` : html`<span class="secondary-text">No description</span>`}
      ${r.withdrawn_reason
        ? html`<div class="small-text secondary-text">Withdrawn: ${r.withdrawn_reason}</div>` : nothing}`;
  }

  instancesTable(r) {
    const f = this.form;
    const add = () => this.addInstance(r.code);
    return html`
      <h6 class="small">Instances</h6>
      ${r.instances.length ? html`<table>
        <tbody>
          ${r.instances.map((i) => html`<tr>
            <td class="min secondary-text">${i.where}</td>
            <td class="codes-wrap">${i.url
              ? html`<a class="link" href=${i.url} target="_blank" rel="noopener">${i.text}</a>` : i.text}</td>
            <td class="min">${i.id ? html`<button class="circle transparent small"
                aria-label="Remove ${i.text}" ?disabled=${this.adding}
                @click=${() => this.removeInstance(r.code, i.id)}><i>close</i></button>` : nothing}</td>
          </tr>`)}
        </tbody>
      </table>` : html`<p class="secondary-text">None yet</p>`}
      ${r.status === 'withdrawn' ? nothing : html`<nav>
        <div class="field border small no-margin max">
          <input type="url" placeholder="Add a link" aria-label="Add a link"
            .value=${f.instance} @input=${(e) => this.setForm({ instance: e.target.value })}
            @keydown=${(e) => { if (e.key === 'Enter') add(); }}>
        </div>
        ${btn(this.adding ? 'Adding...' : 'Add', this.adding || !f.instance.trim(), add, 'border')}
      </nav>`}`;
  }

  pencilingsTable(r) {
    return html`
      <h6 class="small">Penciled</h6>
      ${r.pencilings.length ? html`<table>
        <tbody>
          ${r.pencilings.map((p) => html`<tr>
            <td class="min secondary-text">#${p.n}</td>
            <td>${p.crossed ? html`<s>${minute(p.at)}</s>` : minute(p.at)}</td>
            <td class="min">${p.crossed ? nothing : html`<button class="circle transparent small"
                aria-label="Cross out penciling #${p.n}" ?disabled=${this.adding}
                @click=${() => this.crossOut(r.code, p.id)}><i>strikethrough_s</i>
                <div class="tooltip left">Cross out</div></button>`}</td>
          </tr>`)}
        </tbody>
      </table>` : html`<p class="secondary-text">Not penciled yet</p>`}
      ${r.status === 'withdrawn' ? nothing : html`<nav>
        ${btn(r.pencilings.length ? 'Pencil again' : 'Mark penciled', this.adding,
          () => this.popupCall(r.code, '/penciled'), 'border')}
      </nav>`}`;
  }

  history(r) {
    if (!r.history.length) return nothing;
    return html`
      <h6 class="small">History</h6>
      <table>
        <tbody>
          ${r.history.map((e) => html`<tr>
            <td class="min small-text secondary-text">${minute(e.at)}</td>
            <td>${e.what}</td>
          </tr>`)}
        </tbody>
      </table>`;
  }

  actions(r) {
    if (!r.in_ledger) return nothing;
    const withdrawn = r.status === 'withdrawn';
    const busy = this.busy === r.code;
    const act = (icon, tip, name, onClick) => html`<button class="circle transparent small"
        aria-label=${name} ?disabled=${busy} @click=${onClick}>
        <i>${icon}</i><div class="tooltip left">${tip}</div></button>`;
    const empty = html`<span></span>`;
    return html`<div class="codes-actions">
      ${!withdrawn && r.type !== 'document' ? act('edit_note', r.penciled ? 'Pencil again' : 'Mark penciled',
        `Mark ${r.code} penciled`, () => this.pencil(r.code)) : empty}
      ${r.type
        ? act('info', 'Details', `Details of ${r.code}`, () => this.openEdit(r))
        : act('edit', 'Edit', `Edit ${r.code}`, () => this.openEdit(r))}
      ${!withdrawn ? act('block', 'Withdraw', `Withdraw ${r.code}`, () => this.openWithdraw(r)) : empty}
    </div>`;
  }

  noteField(label = 'What it is') {
    return field(label, this.form.note, (e) => this.setForm({ note: e.target.value }),
      { placeholder: ' ' });
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
      ${claim || count === 1 ? this.noteField('What it is (optional)') : nothing}
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
      <p>${PENCIL_HELP}</p>
      ${list.map((m) => html`
        <nav class="wrap">
          <h3 class="mono max" aria-label=${m.code.split('').join(' ')}>${m.code}</h3>
          <button class="circle transparent" aria-label="Copy ${m.code}" @click=${() => this.copy(m.code)}>
            <i>${this.copied === m.code ? 'check' : 'content_copy'}</i></button>
          ${this.copied === m.code ? html`<span class="small-text" role="status">Copied</span>` : nothing}
          ${m.penciled
            ? html`<span class="chip secondary-container"><i>check</i><span>Penciled</span></span>`
            : btn(this.busy === m.code ? 'Saving...' : 'Mark penciled', this.busy === m.code,
              () => this.pencil(m.code, true), 'border')}
        </nav>
        ${m.note ? html`<p class="small-text secondary-text">${m.note}</p>` : nothing}
        ${field('Notes (optional)', this.mintNotes[m.code] ?? '',
          (e) => { this.mintNotes = { ...this.mintNotes, [m.code]: e.target.value }; }, { rows: 2 })}`)}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Mint more', this.saving, () => this.finishMinted(true), 'border')}
        <button autofocus ?disabled=${this.saving} @click=${() => this.finishMinted()}>
          ${this.saving ? 'Saving...' : 'Done'}</button>
      </nav>`;
  }

  renderEditForm() {
    const r = this.target;
    const [type] = TYPES[r.type] || [];
    const dirty = Object.keys(this.editChanges()).length > 0;
    return html`
      <div class="codes-head">
        <div class="max">
          <h5 id="codes-dialog-title">${type ? nothing : 'Edit '}<span class="mono">${r.code}</span></h5>
          ${type ? html`<table>
            <tbody>
              <tr><td class="min secondary-text">Type</td><td>${type}</td></tr>
              <tr><td class="min secondary-text">Title</td><td>${r.title || r.note || 'No title'}</td></tr>
            </tbody>
          </table>` : html`
            ${this.noteField()}
            ${field('Notes', this.form.notes, (e) => this.setForm({ notes: e.target.value }), { rows: 3 })}`}
        </div>
        ${r.gramps && !this.thumbGone ? html`<img class="codes-thumb" alt=""
          src="${API}/${encodeURIComponent(r.code)}/thumbnail"
          @error=${() => { this.thumbGone = true; }}>` : nothing}
      </div>
      ${this.instancesTable(r)}
      ${r.type === 'document' ? nothing : this.pencilingsTable(r)}
      ${this.history(r)}
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${type ? html`<button autofocus @click=${() => this.closeDialog()}>Close</button>` : html`
          ${btn(dirty ? 'Cancel' : 'Close', this.saving, () => this.closeDialog(), 'border')}
          ${btn(this.saving ? 'Saving...' : 'Save', this.saving || !dirty, () => this.submitEdit())}`}
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
      ${this.formError ? html`<p>${statusLine('error', this.formError)}</p>` : nothing}
      <nav class="right-align">
        ${btn('Cancel', this.saving, () => this.closeDialog(), 'border')}
        ${btn(this.saving ? 'Withdrawing...' : 'Withdraw', this.saving, submit, 'error')}
      </nav>`;
  }
}
customElements.define('codes-page', CodesPage);
