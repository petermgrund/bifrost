import { BifrostElement, html, nothing, api, btn, field, spinner, statusLine,
         iconYes, iconNo, emptyRow } from './core.js';

const API = '/evidence/api';
const SHOW = 60;
const STARS = [['birth', 'Birth'], ['marriage', 'Marriage'], ['death', 'Death'],
               ['burial', 'Burial'], ['parents', 'Parents']];

const link = (url, text) => (url
  ? html`<a href=${url} target="_blank" rel="noopener" class="link">${text}</a>`
  : html`${text}`);

const pre = (text) => html`<p class="pre">${text}</p>`;

class EvidencePage extends BifrostElement {
  static properties = {
    config: { state: true },
    tab: { state: true },
    people: { state: true },
    q: { state: true },
    person: { state: true },
    claim: { state: true },
    audits: { state: true },
    busy: { state: true },
    error: { state: true },
  };

  constructor() {
    super();
    this.config = null;
    this.tab = 'proof';
    this.people = null;
    this.q = '';
    this.person = null;
    this.claim = null;
    this.audits = null;
    this.busy = '';
    this.error = '';
  }

  connectedCallback() {
    super.connectedCallback();
    this.loadConfig();
  }

  async loadConfig() {
    try {
      this.config = await api(`${API}/config`);
      if (this.config.enabled) this.loadPeople();
    } catch (e) {
      this.config = { enabled: false, error: e.message };
    }
  }

  async run(label, fn) {
    this.busy = label; this.error = '';
    try { await fn(); } catch (e) { this.error = e.message; } finally { this.busy = ''; }
  }

  loadPeople(refresh = false) {
    return this.run('people', async () => {
      this.people = (await api(`${API}/people${refresh ? '?refresh=true' : ''}`)).people;
    });
  }

  openPerson(gid, refresh = false) {
    return this.run('person', async () => {
      this.claim = null;
      this.person = await api(`${API}/person/${gid}${refresh ? '?refresh=true' : ''}`);
    });
  }

  openClaim(id, refresh = false) {
    return this.run('claim', async () => {
      this.claim = await api(`${API}/claim/${encodeURIComponent(id)}${refresh ? '?refresh=true' : ''}`);
    });
  }

  loadAudits(refresh = false) {
    return this.run('audits', async () => {
      this.audits = await api(`${API}/audits${refresh ? '?refresh=true' : ''}`);
    });
  }

  refresh() {
    if (this.tab === 'audits') return this.loadAudits(true);
    const gid = this.person?.gramps_id;
    const id = this.claim?.id;
    return this.loadPeople(true)
      .then(() => gid && this.openPerson(gid))
      .then(() => id && this.openClaim(id));
  }

  setTab(tab) {
    this.tab = tab;
    if (tab === 'audits' && !this.audits) this.loadAudits();
  }

  // ---- people and claims

  get matches() {
    const q = this.q.trim().toLowerCase();
    const all = this.people || [];
    const hits = q ? all.filter((p) => p.name.toLowerCase().includes(q) || (p.gramps_id || '').toLowerCase() === q) : all;
    return hits.slice(0, SHOW);
  }

  renderPeople() {
    if (this.people === null) return spinner;
    const hits = this.matches;
    return html`
      ${field('Name or ID', this.q, (e) => { this.q = e.target.value; }, { small: true })}
      <ul class="list border round scroll capped ev-people">
        ${hits.map((p) => html`<li class="wave ${this.person?.gramps_id === p.gramps_id ? 'fill' : ''}"
            @click=${() => this.openPerson(p.gramps_id)}>
          <div class="max"><div>${p.name}</div>
            <div class="small-text secondary-text">${p.gramps_id}${p.years ? ` · ${p.years}` : ''}</div></div>
        </li>`)}
        ${hits.length ? nothing : html`<li class="secondary-text">No one matches</li>`}
      </ul>
      ${this.people.length > SHOW && hits.length === SHOW
        ? html`<p class="small-text secondary-text">First ${SHOW} of ${this.people.length}. Type to narrow.</p>` : nothing}`;
  }

  renderStars(stars) {
    return html`<div class="small-text secondary-text ev-stars">
      ${STARS.map(([k, label]) => html`<span title=${label}>${stars[k] >= 1 ? '★' : stars[k] > 0 ? '⯪' : '☆'} ${label}</span>`)}
    </div>`;
  }

  renderClaims() {
    const p = this.person;
    if (!p) return nothing;
    return html`
      <div class="medium-space"></div>
      <nav class="no-space">
        <div class="max"><h6 class="small">${link(p.url, p.name)}</h6>
          <div class="small-text secondary-text">${p.gramps_id}${p.years ? ` · ${p.years}` : ''} · ${p.citations} citation${p.citations === 1 ? '' : 's'}</div></div>
      </nav>
      ${this.renderStars(p.stars)}
      <ul class="list border round ev-claims">
        ${p.claims.map((c) => html`<li class="wave ${this.claim?.id === c.id ? 'fill' : ''}" @click=${() => this.openClaim(c.id)}>
          <div class="max">
            <div>${c.title}${c.when?.date ? html` <span class="secondary-text">${c.when.date}</span>` : nothing}</div>
            <div class="small-text secondary-text">
              ${c.citations ? `${c.rows_complete}/${c.citations} row${c.citations === 1 ? '' : 's'} complete` : 'no citation'}
              ${c.report ? ' · report' : ''}${c.needs_review?.length ? ' · review' : ''}
              ${c.status.map((s) => html` <span class="chip tiny">${s}</span>`)}
            </div>
          </div>
          ${c.citations ? (c.complete ? iconYes : iconNo) : nothing}
        </li>`)}
      </ul>`;
  }

  // ---- the proof of one claim

  renderRow(r) {
    const chips = r.cited_for.flatMap((row) => row.words.map((w) => html`<span class="chip tiny ${r.matched.includes(w) ? 'fill' : ''}">${w}</span>`));
    const ev = r.evidence_for_claim.length
      ? r.evidence_for_claim.map((e) => html`<div><b>${e.cls}</b>${e.why ? html`; ${e.why}` : nothing}</div>`)
      : html`<span class="secondary-text">${r.needs_evidence ? 'needed' : '—'}</span>`;
    const bad = r.evidence.filter((e) => !e.ok).map((e) => html`<div class="error-text">${e.raw}</div>`);
    const others = r.attachments.length - 1;
    return html`<tr>
      <td>
        <div>${link(r.url, r.gramps_id)} ${r.reference}</div>
        <div class="small-text secondary-text">${r.source.type ? `${r.source.type} · ` : ''}${r.media ? `${r.media} media` : 'no media'}${others > 0 ? ` · also attached to ${others} other${others === 1 ? '' : 's'}` : ''}</div>
      </td>
      <td>${r.confidence_label}</td>
      <td>${chips.length ? chips : html`<span class="secondary-text">none</span>`}</td>
      <td>${ev}${bad}</td>
      <td>${r.complete ? iconYes : html`<span title=${r.missing.join('; ')}>${iconNo}</span>`}</td>
    </tr>`;
  }

  renderProof() {
    const c = this.claim;
    if (!c) {
      return html`<p class="secondary-text">${this.person ? 'Pick a claim.' : 'Pick a person, then a claim.'}</p>`;
    }
    const when = [c.when?.date, c.when?.place].filter(Boolean).join(' · ');
    return html`
      <nav class="no-space">
        <div class="max">
          <h6 class="small">${link(c.url, c.title)}</h6>
          <div class="secondary-text">${when}${c.when?.description ? ` · ${c.when.description}` : ''}</div>
        </div>
        ${c.tags.map((t) => html`<span class="chip tiny ${c.status.includes(t) ? 'fill' : ''}">${t}</span>`)}
      </nav>
      <p>${c.complete
        ? statusLine('ok', 'Complete: every row classified, the argument written, nothing changed since')
        : html`${iconNo} <b>${c.missing.length} missing</b><ul class="ev-missing">${c.missing.map((m) => html`<li>${m}</li>`)}</ul>`}</p>
      ${c.needs_review.length ? html`<p class="error-text">Citations ${c.needs_review.join(', ')} changed after the Report note. Review the argument.</p>` : nothing}
      <p class="small-text secondary-text">Words that fit this claim: ${c.fits.join(', ') || 'none'}</p>
      <table class="border ev-rows">
        <thead><tr><th>Citation</th><th>Confidence</th><th>Cited for</th><th>Evidence</th><th></th></tr></thead>
        <tbody>${c.rows.length ? c.rows.map((r) => this.renderRow(r)) : emptyRow(5, 'No citation attached')}</tbody>
      </table>
      ${c.stated.length ? html`
        <h6 class="small">What the records state</h6>
        <ul>${c.stated.map((s) => html`<li><b>${s.citation}</b> (${s.cls}): ${s.why}</li>`)}</ul>` : nothing}
      ${c.rows.some((r) => r.abstract) ? html`
        <details><summary class="link">Abstracts</summary>
          ${c.rows.filter((r) => r.abstract).map((r) => html`<p><b>${r.gramps_id}</b></p>${pre(r.abstract)}`)}
        </details>` : nothing}
      <h6 class="small">Argument</h6>
      ${c.report ? pre(c.report.text) : html`<p class="secondary-text">No Report note. Write one on the ${c.kind === 'event' ? 'event' : c.kind === 'person' || c.kind === 'name' ? 'person' : 'family'} in Gramps Web.</p>`}
      <h6 class="small">To do</h6>
      ${c.todo ? pre(c.todo.text) : html`<p class="secondary-text">No To Do note.</p>`}
      ${c.other_notes.length ? html`<p class="small-text secondary-text">${c.other_notes.length} other note${c.other_notes.length === 1 ? '' : 's'}: ${c.other_notes.map((n) => n.type).join(', ')}</p>` : nothing}`;
  }

  // ---- audits

  renderAudits() {
    const a = this.audits;
    if (!a) return this.busy ? spinner : nothing;
    return html`
      <p class="secondary-text">${a.findings} finding${a.findings === 1 ? '' : 's'} over ${a.citations} citations.
        ${a.tags_missing.length ? html`Status tags not yet in Gramps: ${a.tags_missing.join(', ')}.` : nothing}</p>
      ${a.checks.map((ch) => html`
        <details class="ev-check">
          <summary class="none">
            <nav>
              <span class="badge none ${ch.count ? 'primary' : 'secondary-container'}">${ch.count}</span>
              <div class="max"><b>${ch.title}</b><div class="small-text secondary-text">${ch.why}</div></div>
              <i class="chev">chevron_right</i>
            </nav>
          </summary>
          ${ch.count ? html`<table class="border">
            <tbody>${ch.items.map((it) => html`<tr>
              <td class="ev-id">${link(it.url, it.gramps_id || it.object)}</td>
              <td>${it.title}</td>
              <td class="secondary-text">${it.detail}</td>
            </tr>`)}</tbody>
          </table>` : html`<p class="small-text secondary-text">Nothing found.</p>`}
        </details>`)}`;
  }

  render() {
    if (this.config === null) return spinner;
    if (!this.config.enabled) {
      return html`<p class="secondary-text">${this.config.error ? `Evidence could not load: ${this.config.error}` : 'The Evidence section is off (evidence.enabled).'}</p>`;
    }
    return html`
      <nav class="no-space">
        <div class="tabs max">
          <a class=${this.tab === 'proof' ? 'active' : ''} @click=${() => this.setTab('proof')}>Proof</a>
          <a class=${this.tab === 'audits' ? 'active' : ''} @click=${() => this.setTab('audits')}>Audits</a>
        </div>
        ${btn('Refresh', Boolean(this.busy), () => this.refresh(), 'border small')}
      </nav>
      <div class="small-space"></div>
      ${this.error ? html`<p>${statusLine('error', this.error)}</p>` : nothing}
      ${this.tab === 'proof' ? html`
        <div class="grid">
          <div class="s12 m4 l3">${this.renderPeople()}${this.renderClaims()}</div>
          <div class="s12 m8 l9">${this.busy === 'claim' || this.busy === 'person' ? spinner : this.renderProof()}</div>
        </div>` : this.renderAudits()}`;
  }
}
customElements.define('evidence-page', EvidencePage);
