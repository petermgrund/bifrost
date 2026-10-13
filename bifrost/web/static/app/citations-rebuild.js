import { BifrostElement, html, nothing, api, post, spinner, statusLine } from './core.js';
import { recordById, buildOutputs, restoreDraft, plain, hasGap, GUIDE } from '/static/citations/citations.js';

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

/**
 * What the current rules would change on one citation (A15): a field still as the old rules built it takes the new
 * text; a field that differs from both was edited by hand and stays.
 */
function plan(item) {
  const saved = item.draft?.draft || {};
  const type = recordById(item.draft?.type || '');
  if (!type) return { item, state: 'gone' };
  const draft = restoreDraft(type, saved);
  const legacy = !saved.guide || saved.guide < LEGACY_BEFORE;
  const before = buildOutputs(type, draft, { legacy });
  const now = buildOutputs(type, draft);
  const changes = {}, kept = [];
  for (const [key, label] of TEXT_FIELDS) {
    const have = item[key], want = plain(now[key]);
    if (have === want) continue;
    if (have === plain(before[key])) {
      if (hasGap(now[key])) return { item, type, state: 'input', missing: label };
      changes[key] = want;
    } else kept.push([label, have]);
  }
  const attributes = [...now.attributes, ['Guide', GUIDE.changed]];
  const haveAttributes = item.attributes.filter(([name]) => WIZARD_ATTRIBUTES.includes(name));
  if (!sameList(haveAttributes, attributes)) changes.attributes = attributes;
  const tagged = Boolean(type.tag);
  if (item.tags.includes(TAG) !== tagged) changes.tagged = tagged;
  const state = Object.keys(changes).length ? 'change' : kept.length ? 'kept' : 'current';
  return { item, type, draft, saved, changes, kept, state };
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
    this.busy = '';
    this.msg = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    try {
      const got = await api(`${API}/rebuild`);
      this.gramps = got.gramps_url || '';
      this.plans = got.items.map(plan);
      this.msg = null;
    } catch (e) {
      this.plans = [];
      this.msg = ['error', errText(e)];
    }
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
      draft: { type: p.type.id, draft: { ...p.saved, guide: GUIDE.changed } },
    };
  }

  async apply(list) {
    if (this.busy || !list.length) return;
    this.busy = list.length === 1 ? list[0].item.handle : 'all';
    try {
      const got = await post(`${API}/rebuild`, { items: list.map((p) => this.body(p)) });
      this.msg = got.failed.length ? ['error', got.failed.map((f) => f.error).join('; ')] : null;
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
          <div class="small-text secondary-text">${p.type?.name || p.item.draft?.type}</div>
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
customElements.define('citations-rebuild', CitationsRebuild);
