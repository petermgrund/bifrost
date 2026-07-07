/* Bifrost is ONE page (styled after Gramps Web's settings page): a stack of
   <details> expanders, each with a bold title + one-line description in the
   summary and a section component inside. Deep-link with #section — /sync etc.
   redirect here. Sections mount lazily on first open so a page load doesn't
   fan out API calls. */
import { BifrostElement, html, nothing } from './core.js';
import './paperless-sync-page.js';
import './transcribe-page.js';
import './citations-page.js';
import './places-page.js';

const SECTIONS = [
  { id: 'sync', title: 'Sync', desc: 'Create a Gramps media object from a Paperless document',
    body: html`<paperless-sync-page></paperless-sync-page>` },
  { id: 'transcribe', title: 'Transcribe', desc: 'Gemini OCR for a Paperless document',
    body: html`<transcribe-page></transcribe-page>` },
  { id: 'citations', title: 'Citations', desc: 'Generate Gramps citations from Paperless document',
    body: html`<citations-page></citations-page>` },
  { id: 'places', title: 'Places', desc: 'Generate a boundary polygon for a place on a Gramps map',
    body: html`<places-page></places-page>` },
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
      this.opened = new Set([...this.opened, id]);
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
