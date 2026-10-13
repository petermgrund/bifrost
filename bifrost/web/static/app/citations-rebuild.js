import { BifrostElement, html, nothing, api, post, spinner, statusLine } from './core.js';
import { loadRecordTypes } from './record-registry.js';
import { SHIPPED, RECORDS, recordById, buildOutputs, restoreDraft, typeAtVersion, plain, hasGap, GUIDE } from '/static/citations/citations.js';

const API = '/citations/api';
const TAG = 'General form';
const TEXT_FIELDS = [['page', 'Page'], ['frn', 'FRN'], ['srn', 'SRN']];
const WIZARD_ATTRIBUTES = ['Subject', 'Record', 'Household', 'Which entry', 'Source says', 'Evidence', 'Record type', 'Guide'];
const LEGACY_BEFORE = '2026-10-13';

function errText(e) {
  const m = String(e?.message ?? e).match(/^\d+: ([\s\S]*)$/);
  if (!m) return String(e?.message ?? e);
  try { return JSON.parse(m[1]).detail || m[1]; } catch { return m[1]; }
}

const sameList = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** The record types as they were at the saved versions the citations were made with, by "id@version". */
async function typesThen(items) {
  const wanted = new Map();
  for (const item of items) {
    const id = item.draft?.type, version = item.draft?.draft?.typeVersion;
    if (!id || typeof version !== 'number' || (recordById(id)?.version || 0) === version) continue;
    if (!wanted.has(id)) wanted.set(id, new Set());
    wanted.get(id).add(version);
  }
  const then = new Map();
  await Promise.all([...wanted].map(async ([id, versions]) => {
    const rows = (await api(`${API}/types/${encodeURIComponent(id)}/versions`)).versions;
    for (const version of versions) {
      const row = rows.find((r) => r.version === version);
      const type = row ? typeAtVersion(SHIPPED, id, row.definition, row.kind) : typeAtVersion(SHIPPED, id, null, 'shipped');
      if (type) then.set(`${id}@${version}`, type);
    }
  }));
  return then;
}

/**
 * What the current rules would change on one citation (A15): a field still as the record type built it then takes
 * the new text; a field that differs from both was edited by hand and stays. A General form citation can be rebuilt
 * under the record type chosen for it (A14).
 */
function plan(item, then, retype = '') {
  const saved = item.draft?.draft || {};
  const id = item.draft?.type || '';
  const built = recordById(id);
  const type = retype ? recordById(retype) : built;
  if (!type) return { item, state: 'gone', retype };
  const base = built || SHIPPED.find((t) => t.id === id) || type;
  const version = saved.typeVersion;
  const was = typeof version !== 'number' ? SHIPPED.find((t) => t.id === id) || base
    : version === (base.version || 0) ? base : then.get(`${id}@${version}`) || base;
  const draft = restoreDraft(type, saved);
  const legacy = !saved.guide || saved.guide < LEGACY_BEFORE;
  const before = buildOutputs(was, restoreDraft(was, saved), { legacy });
  const now = buildOutputs(type, draft);
  const changes = {}, kept = [];
  for (const [key, label] of TEXT_FIELDS) {
    const have = item[key], want = plain(now[key]);
    if (have === want) continue;
    if (have === plain(before[key])) {
      if (hasGap(now[key])) return { item, type, state: 'input', missing: label, retype };
      changes[key] = want;
    } else kept.push([label, have]);
  }
  const attributes = [...now.attributes, ['Guide', GUIDE.changed]];
  const haveAttributes = item.attributes.filter(([name]) => WIZARD_ATTRIBUTES.includes(name));
  if (!sameList(haveAttributes, attributes)) changes.attributes = attributes;
  const tagged = Boolean(type.tag);
  if (item.tags.includes(TAG) !== tagged) changes.tagged = tagged;
  const state = Object.keys(changes).length ? 'change' : kept.length ? 'kept' : 'current';
  return { item, type, draft, saved, changes, kept, state, retype };
}

const STATE = {
  change: ['primary-container', 'Will change'],
  current: ['', 'Up to date'],
  kept: ['secondary-container', 'Hand edit kept'],
  input: ['error', 'Needs input'],
  gone: ['surface-variant', 'Record type removed'],
};

class CitationsRebuild extends BifrostElement {
  static properties = {
    plans: { state: true },
    gramps: { state: true },
    busy: { state: true },
    msg: { state: true },
  };

  constructor() {
    super();
    this.plans = null;
    this.gramps = '';
    this.then = new Map();
    this.retype = {};
    this.busy = '';
    this.msg = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    if (registryError) {
      this.plans = [];
      this.msg = ['error', registryError];
      return;
    }
    try {
      const got = await api(`${API}/rebuild`);
      this.then = await typesThen(got.items);
      this.gramps = got.gramps_url || '';
      this.plans = got.items.map((item) => plan(item, this.then, this.retype[item.handle]));
      this.msg = null;
    } catch (e) {
      this.plans = [];
      this.msg = ['error', errText(e)];
    }
  }

  retypeTo(p, id) {
    this.retype = { ...this.retype, [p.item.handle]: id };
    this.plans = this.plans.map((x) => (x.item.handle === p.item.handle ? plan(x.item, this.then, id) : x));
  }

  retypeField(p) {
    const choices = RECORDS.filter((t) => t.id !== 'general').sort((a, b) => a.name.localeCompare(b.name));
    return html`<div class="field suffix border small rb-retype"><select ?disabled=${Boolean(this.busy)}
      @change=${(e) => this.retypeTo(p, e.target.value)}>
      <option value="" ?selected=${!p.retype}>General form</option>
      ${choices.map((t) => html`<option value=${t.id} ?selected=${t.id === p.retype}>${t.name}</option>`)}
    </select><i>arrow_drop_down</i></div>`;
  }

  body(p) {
    const c = p.changes;
    const text = c.frn !== undefined || c.srn !== undefined;
    return {
      handle: p.item.handle,
      page: c.page ?? null,
      attributes: c.attributes ?? null,
      tagged: c.tagged ?? null,
      note: text ? p.item.note : '',
      frn: text ? c.frn ?? p.item.frn : null,
      srn: text ? c.srn ?? p.item.srn : null,
      draft: { type: p.type.id, draft: { ...p.saved, guide: GUIDE.changed, typeVersion: p.type.version || 0 } },
    };
  }

  async apply(list) {
    if (this.busy || !list.length) return;
    this.busy = list.length === 1 ? list[0].item.handle : 'all';
    try {
      const got = await post(`${API}/rebuild`, { items: list.map((p) => this.body(p)) });
      this.msg = got.failed.length ? ['error', got.failed.map((f) => f.error).join('; ')] : null;
      const failed = new Set(got.failed.map((f) => f.handle));
      this.retype = Object.fromEntries(Object.entries(this.retype).filter(([handle]) => failed.has(handle)));
      await this.load();
    } catch (e) {
      this.msg = ['error', errText(e)];
    } finally {
      this.busy = '';
    }
  }

  change(label, from, to) {
    return html`<div class="rb-change">
      <div class="small-text secondary-text">${label}</div>
      <div class="rb-old">${from || '—'}</div>
      <div class="rb-new">${to}</div>
    </div>`;
  }

  keep(label, text) {
    return html`<div class="rb-change">
      <div class="small-text secondary-text">${label}</div>
      <div class="rb-new">${text} <span class="chip small secondary-container">Kept</span></div>
    </div>`;
  }

  card(p) {
    const [cls, label] = STATE[p.state];
    const c = p.changes || {};
    const link = this.gramps && p.item.gramps_id ? `${this.gramps}/citation/${p.item.gramps_id}` : '';
    const added = c.attributes ? c.attributes.map(([name, value]) => `${name}: ${value}`).join(' · ') : '';
    return html`<article class="border rb-card">
      <nav>
        <div class="max">
          <div>${link ? html`<a class="link" href=${link} target="_blank" rel="noopener">${p.item.gramps_id}</a>` : p.item.gramps_id}
            · ${p.item.source.title || p.item.source.gramps_id}</div>
          ${p.item.draft?.type === 'general' ? this.retypeField(p)
    : html`<div class="small-text secondary-text">${p.type?.name || p.item.draft?.type}</div>`}
        </div>
        <span class="chip small ${cls}">${label}</span>
        ${p.state === 'change' ? html`<button class="border small" ?disabled=${Boolean(this.busy)}
          @click=${() => this.apply([p])}>${this.busy === p.item.handle ? spinner : 'Apply'}</button>` : nothing}
      </nav>
      ${p.state === 'change' ? html`
        ${TEXT_FIELDS.filter(([key]) => c[key] !== undefined).map(([key, name]) => this.change(name, p.item[key], c[key]))}
        ${added ? this.change('Attributes', p.item.attributes.map(([n, v]) => `${n}: ${v}`).join(' · '), added) : nothing}
        ${c.tagged !== undefined ? this.change('Tag', c.tagged ? '' : TAG, c.tagged ? TAG : '—') : nothing}` : nothing}
      ${(p.kept || []).map(([label, text]) => this.keep(label, text))}
      ${p.state === 'input' ? html`<p class="small-text error-text">${p.missing}</p>` : nothing}
    </article>`;
  }

  render() {
    if (!this.plans) return html`<p>${spinner}</p>`;
    const ready = this.plans.filter((p) => p.state === 'change');
    return html`<nav class="rb-head">
        <div class="max">${this.msg ? statusLine(...this.msg) : nothing}</div>
        <button ?disabled=${!ready.length || Boolean(this.busy)} @click=${() => this.apply(ready)}>
          ${this.busy === 'all' ? spinner : `Apply all (${ready.length})`}</button>
      </nav>
      ${this.plans.map((p) => this.card(p))}`;
  }
}
let registryError = '';
try {
  await loadRecordTypes();
} catch (e) {
  registryError = `Record types: ${errText(e)}`;
}
customElements.define('citations-rebuild', CitationsRebuild);
