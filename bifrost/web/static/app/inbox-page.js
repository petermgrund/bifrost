/* Home — pending work across every surface, a tree snapshot, recent runs.
   One tolerant /api/inbox call; a down service shows as "unavailable". */
import { BifrostElement, html, nothing, api, statusIcon } from './core.js';

const SNAPSHOT = [
  ['people', 'People'], ['events', 'Events'], ['places', 'Places'],
  ['citations', 'Citations'], ['media', 'Media'], ['sources', 'Sources'],
];

class InboxPage extends BifrostElement {
  static properties = {
    data: { state: true },
    busy: { state: true },
    error: { state: true },
  };

  constructor() {
    super();
    this.data = null;
    this.busy = false;
    this.error = '';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load(refresh = false) {
    this.busy = true;
    try {
      this.data = await api(`/api/inbox${refresh ? '?refresh=1' : ''}`);
      this.error = '';
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  render() {
    if (!this.data) {
      return html`<h5>Home</h5>
        <p class="hint">${this.error || 'Loading…'}</p>
        ${!this.error ? html`<progress class="circle"></progress>` : nothing}`;
    }
    const d = this.data;
    return html`
      <div class="row">
        <h5 class="max">Home</h5>
        <button class="border" ?disabled=${this.busy} @click=${() => this.load(true)}>
          <i>refresh</i><span>${this.busy ? 'Refreshing…' : 'Refresh'}</span></button>
      </div>
      ${this.error ? html`<p class="error-text">${this.error}</p>` : nothing}

      <div class="grid">
        ${SNAPSHOT.map(([key, label]) => html`
          <article class="s6 m4 l2 border center-align">
            <h4>${d.snapshot?.[key] ?? '—'}</h4>
            <div class="hint">${label}</div>
          </article>`)}
      </div>

      <h6>Needs attention</h6>
      <article class="border no-padding">
        ${(d.attention || []).map((it, i) => html`
          ${i ? html`<div class="divider"></div>` : nothing}
          <a class="row padding wave" href=${it.href}>
            <div class="max">${it.label}</div>
            ${it.n === null
              ? html`<span class="hint">unavailable</span>`
              : html`<span class="chip small ${it.n ? 'fill' : ''}">${it.n}</span>`}
            <i>chevron_right</i>
          </a>`)}
      </article>

      <h6>Recent runs</h6>
      <article class="border">
        ${(d.runs || []).length ? html`
          <table class="stripes">
            <thead><tr><th></th><th>Job</th><th>Started</th><th>Summary</th></tr></thead>
            <tbody>${d.runs.map((r) => html`<tr>
              <td>${statusIcon(r.status)}</td>
              <td class="mono">${r.job}</td>
              <td class="hint">${(r.started_at || '').slice(0, 16).replace('T', ' ')}</td>
              <td class="hint">${r.summary || ''}</td>
            </tr>`)}</tbody>
          </table>`
        : html`<p class="hint">No runs yet.</p>`}
      </article>`;
  }
}
customElements.define('inbox-page', InboxPage);
