import { BifrostElement, html, nothing, api } from './core.js';

class InboxPage extends BifrostElement {
  static properties = { cards: { state: true }, runs: { state: true } };
  constructor() {
    super();
    this.cards = null;
    this.runs = [];
  }
  connectedCallback() {
    super.connectedCallback();
    this.load();
  }
  async load() {
    const [listing, runs, paperless, uncited] = await Promise.all([
      api('/faces/api/photos'),
      api('/api/runs?limit=8'),
      api('/sync/api/paperless/pending').catch(() => ({ count: 0 })),
      api('/citations/api/media?uncited=true').catch(() => []),
    ]);
    const faces = listing.photos.flatMap((p) => p.faces);
    this.cards = [
      { n: paperless.count, label: 'documents to sync', href: '/sync' },
      { n: listing.photos.filter((p) => !p.synced).length, label: 'photos to sync', href: '/sync' },
      { n: listing.pending_total, label: 'faces pending', href: '/faces' },
      { n: faces.filter((f) => f.status === 'unlinked').length, label: 'unlinked faces', href: '/faces' },
      { n: uncited.length, label: 'media without citations', href: '/citations' },
    ];
    this.runs = runs;
  }
  render() {
    if (!this.cards) return html`<h1>Inbox</h1><div class="hint">Loading…</div>`;
    return html`
      <h1>Inbox</h1>
      <div class="inbox-grid">
        ${this.cards.map((c) => html`<a class="inbox-card ${c.n ? '' : 'done'}" href=${c.href}>
          <span class="count">${c.n}</span>
          <span class="label">${c.label}</span>
        </a>`)}
      </div>
      <h2>Recent runs</h2>
      ${this.runs.length ? html`<table class="results">
        <tr><th>#</th><th>job</th><th>status</th><th>when</th></tr>
        ${this.runs.map((r) => html`<tr>
          <td>${r.id}</td><td>${r.job}</td>
          <td class="${r.status === 'ok' ? 'action-created' : 'action-failed'}">${r.status}</td>
          <td class="hint">${r.started_at}</td></tr>`)}
      </table>` : html`<div class="hint">No runs yet.</div>`}
    `;
  }
}
customElements.define('inbox-page', InboxPage);
