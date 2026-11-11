import { BifrostElement, html, nothing } from './core.js';
import './sync-check-page.js';
import './reprocess-page.js';
import './codes-page.js';

const SECTIONS = [
  { id: 'sync', title: 'Sync', desc: 'Check Paperless docs, Immich photos and faces against Gramps',
    body: html`<sync-check-page></sync-check-page>` },
  { id: 'photos', title: 'Photos', desc: 'Curate Immich photos for Gramps',
    body: html`<a class="button" href="/photos"><span>Open Photos</span></a>` },
  { id: 'codes', title: 'Codes', desc: 'Manage PID codes',
    body: html`<codes-page></codes-page>` },
  { id: 'other', title: 'Other tools', desc: 'Other tools for managing your data',
    body: html`<reprocess-page></reprocess-page>` },
];

class BifrostApp extends BifrostElement {
  static properties = {
    opened: { state: true },
  };

  constructor() {
    super();
    const h = window.location.hash.slice(1);
    this.opened = new Set(SECTIONS.some((s) => s.id === h) ? [h] : []);
  }

  toggle(e, id) {
    if (e.target.open) {
      this.opened = new Set([id]);
      history.replaceState(null, '', '#' + id);
    }
  }

  render() {
    return html`${SECTIONS.map((s) => html`
      <details id="sec-${s.id}" ?open=${this.opened.has(s.id)}
        @toggle=${(e) => this.toggle(e, s.id)}>
        <summary class="none">
          <nav>
            <i class="chev">chevron_right</i>
            <div class="max">
              <h5 class="small">${s.title}</h5>
              <div class="small-text secondary-text">${s.desc}</div>
            </div>
          </nav>
        </summary>
        ${this.opened.has(s.id) ? html`<div class="section-body">${s.body}</div>` : nothing}
      </details>
      <div class="large-space"></div>`)}`;
  }
}
customElements.define('bifrost-app', BifrostApp);
