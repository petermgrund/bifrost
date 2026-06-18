import { BifrostElement, html } from './core.js';
import './sync-panels.js';

/* Sync = move media INTO Gramps. Transcription/OCR lives on the Transcribe page. */
class SyncPage extends BifrostElement {
  render() {
    return html`
      <h1>Sync</h1>
      <sync-panel source="paperless" label="Paperless → Gramps"
        blurb="Tagged documents become Gramps media; versions, titles, dates and transcriptions stay current."></sync-panel>
      <sync-panel source="immich" label="Immich → Gramps"
        blurb="Tagged photos become Gramps media, with dates, places, descriptions and faces."></sync-panel>
    `;
  }
}
customElements.define('sync-page', SyncPage);
