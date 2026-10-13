import { BifrostElement, html, nothing, api, statusLine, spinner, searchMenu } from './core.js';
import {
  SHIPPED, CHAPTERS, LEVELS, PLATFORMS, DATE_MEANING, FILTERS, ENGINE_TOKENS, STANDARD_VALUES, TEMPLATE_FIELDS, TEMPLATE_KEYS,
  applyEdits, toDefinition, blankDefinition, buildOutputs, draftFromExample, usualCitedFor, previewInputs, printout, mediaOf, usesToken,
} from '/static/citations/citations.js';

const API = '/citations/api/types';
const STEPS = [['source', 'Source'], ['citation', 'Citation'], ['note', 'Note']];
const OUTPUTS = [['title', 'Title'], ['author', 'Author'], ['abbrev', 'Abbrev'], ['pubinfo', 'Pubinfo'], ['page', 'Page'],
  ['frn', 'FRN'], ['srn', 'SRN'], ['plTitle', 'Paperless title']];
const SAMPLE_KEYS = [['citedFor', 'Cited for'], ['url', 'Image URL'], ['accessed', 'Accessed'], ['eventYear', 'Event year']];
const DEFAULT_KEYS = [['platform', 'Platform', Object.keys(PLATFORMS)], ['archive', 'Archive'], ['custodian', 'Held by'], ['custplace', 'Place']];
const PUBINFO_FORMS = [['', 'Medium and platform'], ['own', 'Own template']];
const STANDARD_PUBINFO = '{pubmedium}, {platform} ({home}).';
const TOKEN_AT = /\{(\w+)(?:\|\w+)?\}/g;
// Field keys the wizard itself reads (the page locators, the call number), and names its own values already use.
const ENGINE_KEYS = new Set(['page', 'image', 'call']);
const RESERVED = new Set([...STANDARD_VALUES, ...ENGINE_TOKENS, 'variant', 'confidence']);

function errText(e) {
  const m = String(e?.message ?? e).match(/^\d+: ([\s\S]*)$/);
  if (!m) return String(e?.message ?? e);
  try { return JSON.parse(m[1]).detail || m[1]; } catch { return m[1]; }
}

const clone = (x) => JSON.parse(JSON.stringify(x));
const slug = (name) => String(name || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'type';
const keyOf = (label) => String(label || '').trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+(.)?/g, (_, c) => (c ? c.toUpperCase() : '')).replace(/^[^a-z]+/, '');

function display(text) {
  return String(text ?? '').split(/(⟦[^⟧]*⟧)/).map((part) => (part.startsWith('⟦')
    ? html`<span class="cw-gap">${part.slice(1, -1)}</span>` : part));
}

class RecordTypes extends BifrostElement {
  static properties = {
    edits: { state: true }, drafts: { state: true }, q: { state: true }, id: { state: true }, work: { state: true },
    variant: { state: true }, busy: { state: true }, msg: { state: true }, armed: { state: true },
    newOpen: { state: true }, newQ: { state: true },
  };

  constructor() {
    super();
    this.edits = null;
    this.drafts = [];
    this.q = '';
    this.id = '';
    this.work = null;
    this.saved = '';
    this.variant = '';
    this.busy = false;
    this.msg = null;
    this.armed = '';
    this.newOpen = false;
    this.newQ = '';
    this.pending = new Map();
    this._field = null;
    this._unload = (e) => { if (this.unsaved().length) e.preventDefault(); };
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('beforeunload', this._unload);
    this.load();
    api('/citations/api/general-drafts').then((got) => { this.drafts = got.drafts; }).catch(() => {});
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('beforeunload', this._unload);
  }

  async load() {
    try {
      this.edits = (await api(API)).types;
    } catch (e) {
      this.edits = [];
      this.msg = ['error', errText(e)];
      return;
    }
    const want = decodeURIComponent(location.hash.slice(1));
    if (want) this.open(want);
  }

  get types() { return applyEdits(SHIPPED, this.edits || []); }

  get shippedType() { return SHIPPED.find((t) => t.id === this.id) || null; }

  get edit() { return (this.edits || []).find((e) => e.id === this.id) || null; }

  get isNew() { return Boolean(this.work) && !this.shippedType && !this.edit; }

  get kind() { return this.shippedType ? 'override' : 'custom'; }

  get dirty() { return Boolean(this.work) && JSON.stringify(this.work) !== this.saved; }

  /** The record type being edited, as the wizard would build with it. */
  get working() {
    const edit = { id: this.id, kind: this.kind, definition: this.work };
    return applyEdits(SHIPPED, [edit]).find((t) => t.id === this.id) || null;
  }

  get variantDef() { return this.work?.pageVariants?.find((v) => v.key === this.variant) || null; }

  unsaved() {
    const ids = [...this.pending.keys()].filter((id) => id !== this.id);
    return this.dirty ? [...ids, this.id] : ids;
  }

  freeId(name, except = '') {
    const taken = new Set([...SHIPPED.map((t) => t.id), ...(this.edits || []).map((e) => e.id), ...this.pending.keys()]);
    taken.delete(except);
    const stem = `my-${slug(name)}`;
    let id = stem;
    for (let n = 2; taken.has(id); n++) id = `${stem}-${n}`;
    return id;
  }

  stash() {
    if (!this.work) return;
    if (this.dirty) this.pending.set(this.id, { work: this.work, saved: this.saved, variant: this.variant });
    else this.pending.delete(this.id);
  }

  open(id) {
    const kept = this.pending.get(id);
    let work = kept?.work, saved = kept?.saved ?? '';
    if (!kept) {
      const type = this.types.find((t) => t.id === id);
      const edit = (this.edits || []).find((e) => e.id === id);
      const shipped = SHIPPED.find((t) => t.id === id);
      work = type ? toDefinition(type) : edit?.definition ? clone(edit.definition) : shipped ? toDefinition(shipped) : null;
      saved = JSON.stringify(work);
    }
    this.armed = '';
    this.msg = null;
    this._field = null;
    if (!work) {
      this.id = '';
      this.work = null;
      return;
    }
    this.id = id;
    this.work = work;
    this.saved = saved;
    this.variant = kept?.variant || work.pageVariants?.[0]?.key || '';
    history.replaceState(null, '', `#${encodeURIComponent(id)}`);
  }

  pick(id) {
    if (id === this.id) return;
    this.stash();
    this.open(id);
  }

  startNew(draft = null) {
    this.newOpen = false;
    this.newQ = '';
    this.stash();
    const noun = String(draft?.subject?.noun || '').trim();
    const name = noun ? noun[0].toUpperCase() + noun.slice(1) : 'New record type';
    const id = this.freeId(name);
    this.pending.set(id, { work: blankDefinition(name, draft), saved: '', variant: '' });
    this.open(id);
  }

  copyType() {
    const name = `${this.work.name} (copy)`;
    const work = { ...clone(this.work), name };
    delete work.tag;
    const base = this.shippedType ? this.id : this.work.base;
    if (base) work.base = base;
    this.stash();
    const id = this.freeId(name);
    this.pending.set(id, { work, saved: '', variant: this.variant });
    this.open(id);
  }

  discard() {
    this.pending.delete(this.id);
    if (this.isNew) {
      this.id = '';
      this.work = null;
      history.replaceState(null, '', location.pathname);
      return;
    }
    this.open(this.id);
  }

  async refresh(id) {
    this.edits = (await api(API)).types;
    this.open(id);
  }

  async save() {
    if (this.busy || !this.dirty) return;
    const id = this.isNew ? this.freeId(this.work.name, this.id) : this.id;
    this.busy = true;
    try {
      await api(`${API}/${id}`, { method: 'PUT', body: JSON.stringify({ kind: this.kind, definition: this.work }) });
      this.pending.delete(this.id);
      this.pending.delete(id);
      await this.refresh(id);
      this.msg = ['ok', 'Saved'];
    } catch (e) {
      this.msg = ['error', errText(e)];
    } finally {
      this.busy = false;
    }
  }

  async act(action) {
    if (this.busy) return;
    if (this.armed !== action) {
      this.armed = action;
      return;
    }
    if (action === 'delete' && this.isNew) {
      this.discard();
      return;
    }
    this.busy = true;
    try {
      const opts = action === 'delete' ? { method: 'POST', body: JSON.stringify({ kind: this.kind }) } : { method: 'POST' };
      await api(`${API}/${this.id}/${action}`, opts);
      this.pending.delete(this.id);
      await this.refresh(this.id);
    } catch (e) {
      this.msg = ['error', errText(e)];
    } finally {
      this.busy = false;
    }
  }

  async undelete() {
    const edit = this.edit;
    if (this.busy || !edit) return;
    this.busy = true;
    try {
      if (edit.definition && edit.kind !== 'shipped') {
        await api(`${API}/${this.id}`, { method: 'PUT', body: JSON.stringify({ kind: edit.kind, definition: edit.definition }) });
      } else await api(`${API}/${this.id}/restore`, { method: 'POST' });
      await this.refresh(this.id);
    } catch (e) {
      this.msg = ['error', errText(e)];
    } finally {
      this.busy = false;
    }
  }

  /** Downloads the guide's record-type tables as Bifrost holds them. */
  download() {
    const date = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    const href = URL.createObjectURL(new Blob([printout(this.types, date)], { type: 'text/markdown' }));
    Object.assign(document.createElement('a'), { href, download: 'Record types.md' }).click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }

  touch() { this.requestUpdate(); }

  setKey(key, value) {
    this.work[key] = value;
    this.touch();
  }

  setIn(key, sub, value) {
    this.work[key] = { ...(this.work[key] || {}), [sub]: value };
    this.touch();
  }

  /** Where a part lives: the chosen page form when it has its own, else the record type. */
  holder(key) {
    const v = this.variantDef;
    return v && Object.hasOwn(v, key) ? v : this.work;
  }

  setPart(key, value) {
    this.holder(key)[key] = value;
    this.touch();
  }

  /** Puts text into the template last focused, replacing its selection, and leaves the caret at `caret` within it. */
  splice(text, caret = text.length, from = null, to = null) {
    const el = this._field;
    if (!el) return;
    const at = from ?? el.selectionStart ?? el.value.length, end = to ?? el.selectionEnd ?? at;
    this.setPart(el.dataset.key, `${el.value.slice(0, at)}${text}${el.value.slice(end)}`);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(at + caret, at + caret);
    });
  }

  optional() {
    const el = this._field;
    if (!el) return;
    const inner = el.value.slice(el.selectionStart, el.selectionEnd);
    this.splice(`«${inner}»`, inner.length + (inner ? 2 : 1));
  }

  /** Puts a helper on the {token} the caret is in or just after. */
  helper(name) {
    const el = this._field;
    if (!el) return;
    const caret = el.selectionStart ?? 0;
    const hit = [...el.value.matchAll(TOKEN_AT)].find((m) => m.index < caret && caret <= m.index + m[0].length);
    if (!hit) return;
    const token = `{${hit[1]}|${name}}`;
    this.splice(token, token.length, hit.index, hit.index + hit[0].length);
  }

  /** The tokens a template of this type can use: its fields, the values the wizard builds, and those the type computes. */
  tokens(type) {
    const v = this.variantDef;
    const fields = [...(type.source || []), ...((v?.citation || type.citation) || []), ...(type.note || [])].map(([k]) => k).filter(Boolean);
    const standard = STANDARD_VALUES.filter((k) => !fields.includes(k));
    let computed = [];
    if (type.derive) {
      try { computed = Object.keys(type.derive({ ...(this.work.sample || {}) }) || {}); } catch { computed = []; }
    }
    return [['Fields', [...fields, ...standard]], ['Built', ENGINE_TOKENS], ['Computed', computed]].filter(([, keys]) => keys.length);
  }

  // ---------- rendering ----------

  text(label, value, onInput, opts = {}) {
    return html`<div class="field label border small cw-field rt-field ${opts.cls || ''}">
      <input type="text" class=${opts.mono ? 'mono' : ''} .value=${value ?? ''} placeholder=" "
        list=${opts.list ? opts.list : nothing} ?disabled=${opts.disabled || false} autocomplete="off" spellcheck="false"
        @focus=${opts.onFocus} @input=${(e) => onInput?.(e.target.value)} @change=${(e) => opts.onChange?.(e.target.value, e.target)}>
      <label>${label}</label></div>`;
  }

  select(label, value, options, onChange) {
    return html`<div class="field label suffix border small cw-field rt-field"><select @change=${(e) => onChange(e.target.value)}>
      ${options.map(([v, l]) => html`<option value=${v} ?selected=${v === value}>${l}</option>`)}
    </select><label>${label}</label><i>arrow_drop_down</i></div>`;
  }

  newMenu() {
    const q = this.newQ.trim().toLowerCase();
    const label = (d) => [d.draft?.subject?.name, d.draft?.subject?.noun].filter(Boolean).join(' ') || d.draft?.values?.collection || 'General form';
    const items = [{ id: '', label: 'Blank', icon: 'note_add' }, ...this.drafts
      .map((d) => ({ id: d.handle, label: label(d), sub: [d.draft?.values?.collection, d.created_at?.slice(0, 10)].filter(Boolean).join(' · '), icon: 'format_quote', draft: d.draft }))
      .filter((it) => !q || `${it.label} ${it.sub}`.toLowerCase().includes(q))];
    return searchMenu({
      label: 'New', icon: 'add', value: this.newQ, open: this.newOpen, placeholder: 'General form citations', items,
      onInput: (e) => { this.newQ = e.target.value; },
      onToggle: () => { this.newOpen = !this.newOpen; },
      onClose: () => { this.newOpen = false; },
      onPick: (it) => this.startNew(it.draft || null),
      onEnter: () => this.startNew((q && items[1]?.draft) || null),
    });
  }

  list() {
    const q = this.q.trim().toLowerCase();
    const match = (name, group = '') => !q || `${name} ${group}`.toLowerCase().includes(q);
    const unsaved = new Set(this.unsaved());
    const known = new Set([...this.types.map((t) => t.id), ...(this.edits || []).map((e) => e.id)]);
    const fresh = [...this.pending.entries()].filter(([id]) => !known.has(id))
      .map(([id, p]) => ({ id, name: p.work.name, group: p.work.group, chapter: p.work.chapter }));
    if (this.isNew && !this.pending.has(this.id)) fresh.push({ id: this.id, name: this.work.name, group: this.work.group, chapter: this.work.chapter });
    const rows = [...this.types, ...fresh].filter((t) => match(t.name, t.group));
    const deleted = (this.edits || []).filter((e) => e.deleted)
      .map((e) => ({ id: e.id, name: e.definition?.name || SHIPPED.find((t) => t.id === e.id)?.name || e.id }))
      .filter((t) => match(t.name));
    const chip = (t) => (unsaved.has(t.id) ? ['tertiary-container', 'Unsaved'] : t.custom ? ['primary-container', 'Yours']
      : t.edited ? ['secondary-container', 'Edited'] : null);
    const row = (t) => {
      const c = chip(t);
      return html`<li tabindex="0" class=${t.id === this.id ? 'active' : ''} @click=${() => this.pick(t.id)}
        @keydown=${(e) => { if (e.key === 'Enter') this.pick(t.id); }}>
        <div class="max">${t.id === this.id && this.work ? this.work.name : this.pending.get(t.id)?.work.name ?? t.name}</div>
        ${c ? html`<span class="chip small ${c[0]}">${c[1]}</span>` : nothing}</li>`;
    };
    const chapter = (t) => (CHAPTERS[t.chapter] ? t.chapter : 'ge');
    return html`<div class="rt-list">
      <nav class="rt-list-head">
        <div class="field prefix border small no-margin max">
          <i class="front">search</i>
          <input type="text" .value=${this.q} placeholder="Filter" autocomplete="off" @input=${(e) => { this.q = e.target.value; }}>
        </div>
        ${this.newMenu()}
        <button class="circle transparent" title="Printout" aria-label="Printout" @click=${() => this.download()}><i>download</i></button>
      </nav>
      <div class="rt-list-body">
        ${Object.entries(CHAPTERS).map(([code, label]) => {
    const group = rows.filter((t) => chapter(t) === code);
    return group.length ? html`<h6 class="rt-chapter">${label}</h6><ul class="list rt-items">${group.map(row)}</ul>` : nothing;
  })}
        ${deleted.length ? html`<h6 class="rt-chapter">Deleted</h6><ul class="list rt-items">${deleted.map(row)}</ul>` : nothing}
      </div>
    </div>`;
  }

  savedKeys() {
    try {
      const saved = JSON.parse(this.saved || '{}');
      const rows = [saved, ...(saved.pageVariants || [])].flatMap((x) => STEPS.flatMap(([s]) => x[s] || []));
      return new Set(rows.map(([k]) => k));
    } catch {
      return new Set();
    }
  }

  /** Every field key of the type, its page forms' included. */
  allKeys() {
    return [this.work, ...(this.work.pageVariants || [])].flatMap((x) => STEPS.flatMap(([s]) => x[s] || [])).map(([k]) => k);
  }

  /** A key no other field or wizard value uses, from the one wanted. */
  freeKey(wanted, own = '') {
    const base = String(wanted || '').replace(/\W/g, '').replace(/^[^a-zA-Z]+/, '') || 'field';
    const used = new Set(this.allKeys().filter((k) => k && k !== own));
    let key = base;
    for (let n = 2; used.has(key) || RESERVED.has(key); n++) key = `${base}${n}`;
    return key;
  }

  /** Renames a field's key, and its {tokens} in every template, its example and its event date with it. */
  renameKey(old, key) {
    const token = new RegExp(`\\{${old}(\\|\\w+)?\\}`, 'g');
    for (const x of [this.work, ...(this.work.pageVariants || [])]) {
      for (const step of ['source', 'citation', 'note']) if (x[step]) x[step] = x[step].map((r) => (r[0] === old ? [key, ...r.slice(1)] : r));
      for (const k of TEMPLATE_KEYS) if (typeof x[k] === 'string') x[k] = x[k].replace(token, (_, helper) => `{${key}${helper || ''}}`);
      if (x.eventDate === old) x.eventDate = key;
    }
    const sample = this.work.sample || {};
    if (Object.hasOwn(sample, old)) {
      const moved = { ...sample, [key]: sample[old] };
      delete moved[old];
      this.work.sample = moved;
    }
    this.touch();
  }

  fieldRows(step, label) {
    const holder = step === 'citation' ? this.holder('citation') : this.work;
    const rows = holder[step] || [];
    const sample = this.work.sample || {};
    const fixed = this.savedKeys();
    const write = (next) => {
      holder[step] = next;
      this.touch();
    };
    const update = (i, part, value) => write(rows.map((r, j) => (j === i ? Object.assign([...r], { [part]: value }) : r)));
    const labelled = (i, value) => { if (!rows[i][0] && value.trim()) update(i, 0, this.freeKey(keyOf(value))); };
    const rekey = (i, value, el) => {
      const old = rows[i][0], key = this.freeKey(value, old);
      el.value = key;
      if (key === old) return;
      if (old) this.renameKey(old, key);
      else update(i, 0, key);
    };
    return html`<h6 class="cw-h">${label}</h6>
      ${rows.map(([key, lab, hint], i) => html`<div class="rt-row rt-fieldrow">
        ${this.text('Label', lab, (v) => update(i, 1, v), { onChange: (v) => labelled(i, v) })}
        ${this.text('Key', key, null, { mono: true, disabled: fixed.has(key) || ENGINE_KEYS.has(key), onChange: (v, el) => rekey(i, v, el) })}
        ${this.text('Placeholder', hint, (v) => update(i, 2, v))}
        ${this.text('Example', sample[key], (v) => this.setIn('sample', key, v), { disabled: !key })}
        <button class="circle transparent small" aria-label="Remove ${lab}" @click=${() => write(rows.filter((_, j) => j !== i))}><i>close</i></button>
      </div>`)}
      <button class="border small rt-add" @click=${() => write([...rows, ['', '', '']])}><i>add</i><span>Field</span></button>`;
  }

  nounRows(type) {
    const holder = this.holder('nouns');
    const nouns = holder.nouns || [''];
    const usual = this.work.usual || {};
    const write = (next) => {
      holder.nouns = next;
      this.touch();
    };
    // A noun's own usual fact follows it to its new name once the noun is left, unless that name has one already.
    const moved = (value) => {
      const was = this._nounWas;
      if (was === undefined || was === value || !Object.hasOwn(usual, was) || Object.hasOwn(usual, value)) return;
      const next = { ...usual, [value]: usual[was] };
      delete next[was];
      this.setKey('usual', next);
    };
    return html`<h6 class="cw-h">Record nouns</h6>
      <label class="checkbox rt-check"><input type="checkbox" .checked=${Boolean(this.work.freeNoun)}
        @change=${(e) => this.setKey('freeNoun', e.target.checked)}><span>Typed freely</span></label>
      ${nouns.map((noun, i) => html`<div class="rt-row rt-nounrow">
        ${this.text('Record noun', noun, (v) => write(nouns.map((n, j) => (j === i ? v : n))),
    { onFocus: () => { this._nounWas = noun; }, onChange: moved })}
        ${this.text('Usual cited for', type ? usualCitedFor(type, { noun }) : usual[noun], (v) => this.setIn('usual', noun, v))}
        <button class="circle transparent small" aria-label="Remove ${noun}" @click=${() => write(nouns.filter((_, j) => j !== i))}><i>close</i></button>
      </div>`)}
      <button class="border small rt-add" @click=${() => write([...nouns, ''])}><i>add</i><span>Noun</span></button>`;
  }

  area(key, value) {
    return html`<textarea class="rt-area" rows=${['frn', 'frnMicrofilm'].includes(key) ? 3 : 1} data-key=${key} .value=${value ?? ''}
      spellcheck="false" @focus=${(e) => { this._field = e.target; }} @input=${(e) => this.setPart(key, e.target.value)}></textarea>`;
  }

  templates(type) {
    const keep = (e) => e.preventDefault();
    const chips = this.tokens(type).map(([group, keys]) => html`<div class="rt-token-group">
      <span class="small-text secondary-text">${group}</span>
      ${keys.map((k) => html`<button class="chip small rt-token" @mousedown=${keep} @click=${() => this.splice(`{${k}}`)}>${k}</button>`)}</div>`);
    return html`<h6 class="cw-h">Templates</h6>
      <div class="rt-templates"><div class="rt-tokens">${chips}
        <div class="rt-token-group"><span class="small-text secondary-text">Helpers</span>
          <button class="chip small rt-token" @mousedown=${keep} @click=${() => this.optional()}>«…»</button>
          ${Object.keys(FILTERS).map((f) => html`<button class="chip small rt-token" @mousedown=${keep} @click=${() => this.helper(f)}>|${f}</button>`)}
        </div>
      </div>
      ${TEMPLATE_FIELDS.map(([key, label]) => {
    const holder = this.holder(key);
    if (key === 'frnMicrofilm' && holder.frnMicrofilm === undefined) return nothing;
    if (key === 'pubinfo') {
      const own = holder.pubinfo !== null && holder.pubinfo !== undefined;
      return html`<div class="rt-template">
          <div class="rt-template-head"><span>${label}</span>
            <div class="field suffix border small rt-inline"><select @change=${(e) => this.setPart('pubinfo', e.target.value ? STANDARD_PUBINFO : null)}>
              ${PUBINFO_FORMS.map(([v, l]) => html`<option value=${v} ?selected=${v === (own ? 'own' : '')}>${l}</option>`)}
            </select><i>arrow_drop_down</i></div></div>
          ${own ? this.area(key, holder.pubinfo) : nothing}
          ${!own || usesToken(type, 'pubmedium') ? this.mediumRows(type) : nothing}</div>`;
    }
    return html`<div class="rt-template"><div class="rt-template-head"><span>${label}</span></div>${this.area(key, holder[key])}</div>`;
  })}</div>`;
  }

  /** The Pubinfo mediums the wizard offers for this type. */
  mediums(type) {
    return Array.isArray(this.work.media) ? this.work.media : mediaOf(type);
  }

  /** Saves the mediums; the default follows a renamed medium, and falls to the first when it is removed. */
  writeMedia(next, was = null, now = null) {
    const d = this.work.defaults || {};
    const kept = d.pubmedium === was ? now : d.pubmedium;
    const named = next.map((m) => m.trim()).filter(Boolean);
    this.work.media = next;
    this.work.defaults = { ...d, pubmedium: named.includes(kept) ? kept : named[0] || '' };
    this.touch();
  }

  mediumRows(type) {
    const list = this.mediums(type);
    return html`<div class="rt-media">
      ${list.map((m, i) => html`<div class="rt-row rt-mediumrow">
        ${this.text('Medium', m, (v) => this.writeMedia(list.map((x, j) => (j === i ? v : x)), m, v))}
        <button class="circle transparent small" aria-label="Remove ${m}" @click=${() => this.writeMedia(list.filter((_, j) => j !== i), m)}><i>close</i></button>
      </div>`)}
      <button class="border small rt-add" @click=${() => this.writeMedia([...list, ''])}><i>add</i><span>Medium</span></button>
    </div>`;
  }

  defaults(type) {
    const d = this.work.defaults || {};
    const media = this.mediums(type).map((m) => m.trim()).filter(Boolean);
    return html`<h6 class="cw-h">Defaults</h6>
      <div class="rt-grid">
        ${DEFAULT_KEYS.map(([key, label, list]) => html`${this.text(label, d[key], (v) => this.setIn('defaults', key, v), { list: list ? `rt-list-${key}` : '' })}
          ${key === 'platform' ? this.select('Pubinfo medium', d.pubmedium || media[0] || '', media.map((m) => [m, m]), (v) => this.setIn('defaults', 'pubmedium', v)) : nothing}`)}
        ${this.select('Confidence', this.work.confidence || '', [['', '—'], ...LEVELS.map((l) => [l, l])], (v) => this.setKey('confidence', v))}
        ${this.text('Paperless type', this.work.doctype, (v) => this.setKey('doctype', v), { list: 'rt-list-doctype' })}
      </div>
      ${DEFAULT_KEYS.filter(([, , list]) => list).map(([key, , list]) => html`<datalist id="rt-list-${key}">${list.map((o) => html`<option value=${o}></option>`)}</datalist>`)}
      <datalist id="rt-list-doctype">${Object.keys(DATE_MEANING).map((o) => html`<option value=${o}></option>`)}</datalist>`;
  }

  example(type) {
    const s = this.work.sample || {};
    const nouns = this.variantDef?.nouns || type.nouns || [''];
    const noun = previewInputs(type, this.variant).noun;
    return html`<h6 class="cw-h">Example</h6>
      <div class="rt-grid">
        ${this.text(type.subjectLabel || 'Subject', s.name, (v) => this.setIn('sample', 'name', v))}
        ${type.freeNoun ? this.text('Record noun', s.noun, (v) => this.setIn('sample', 'noun', v))
    : this.select('Record noun', noun, nouns.map((n) => [n, n || '—']), (v) => this.setIn('sample', 'noun', v))}
        ${SAMPLE_KEYS.map(([key, label]) => this.text(label, s[key], (v) => this.setIn('sample', key, v), { mono: key === 'url' }))}
      </div>`;
  }

  preview(type) {
    let out;
    try {
      out = buildOutputs(type, draftFromExample(type, { guide: 'Example', inputs: previewInputs(type, this.variant) }));
    } catch (e) {
      return html`<p class="error-text">${errText(e)}</p>`;
    }
    return html`<table class="cw-out rt-out"><tbody>
      ${OUTPUTS.map(([key, label]) => html`<tr><th>${label}</th><td class="cw-val">${display(out[key])}</td></tr>`)}
      <tr><th>Attributes</th><td class="cw-val">${out.attributes.map(([n, v]) => html`<div>${n}: ${v}</div>`)}</td></tr>
    </tbody></table>`;
  }

  editor() {
    if (!this.work) return html`<div class="rt-editor"></div>`;
    const type = this.working;
    const deleted = Boolean(this.edit?.deleted);
    const variants = this.work.pageVariants || [];
    const button = (label, on, cls = 'border') => html`<button class=${cls} ?disabled=${this.busy} @click=${on}>${label}</button>`;
    return html`<div class="rt-editor">
      <nav class="rt-head">
        ${this.text('Name', this.work.name, (v) => this.setKey('name', v), { cls: 'max' })}
        ${deleted ? button('Restore', () => this.undelete(), '') : html`
          <button ?disabled=${!this.dirty || this.busy} @click=${() => this.save()}>Save</button>
          ${this.dirty ? button('Discard', () => this.discard()) : nothing}
          ${this.shippedType && this.edit?.kind === 'override' ? button(this.armed === 'restore' ? 'Click again to restore' : 'Restore', () => this.act('restore')) : nothing}
          ${button('Copy', () => this.copyType())}
          ${button(this.armed === 'delete' ? 'Click again to delete' : 'Delete', () => this.act('delete'))}`}
      </nav>
      <div class="rt-status">${this.busy ? spinner : this.msg ? statusLine(...this.msg) : nothing}</div>
      <div class="rt-cols">
        <div class="rt-form">
          <div class="rt-grid">
            ${this.text('Group', this.work.group, (v) => this.setKey('group', v))}
            ${this.select('Chapter', this.work.chapter, Object.entries(CHAPTERS), (v) => this.setKey('chapter', v))}
            ${variants.length ? this.select('Form', this.variant, variants.map((v) => [v.key, v.label]), (v) => { this.variant = v; this._field = null; }) : nothing}
          </div>
          ${STEPS.map(([step, label]) => this.fieldRows(step, label))}
          ${this.nounRows(type)}
          ${type ? this.templates(type) : nothing}
          ${type ? this.defaults(type) : nothing}
        </div>
        <div class="rt-side">${type ? html`${this.example(type)}<h6 class="cw-h">Preview</h6>${this.preview(type)}` : nothing}</div>
      </div>
    </div>`;
  }

  render() {
    if (!this.edits) return html`<p>${spinner}</p>`;
    return html`<div class="rt-page">${this.list()}${this.editor()}</div>`;
  }
}
customElements.define('record-types', RecordTypes);
