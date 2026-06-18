import { BifrostElement, html } from './core.js';
import './sync-panels.js';

/* Transcribe = turn document images into text/notes (Gemini OCR), plus the
   transcription-note maintenance tasks. Distinct from Sync (which moves media
   into Gramps). All use the /sync/api/* endpoints under the hood. */
class TranscribePage extends BifrostElement {
  render() {
    return html`
      <h1>Transcribe</h1>
      <sync-panel source="ocr" label="Gemini OCR → Paperless"
        blurb="Documents you tag are transcribed by Gemini and written into the same Paperless document's text (in place) and tagged for transcription, so the next Gramps sync turns it into a note automatically. Preview is free; Apply calls Gemini."></sync-panel>

      <h2>Maintenance</h2>
      <resync-panel></resync-panel>
      <sync-panel source="paperless" label="Rewrite all transcription notes" maintenance
        blurb="Re-writes every transcription note from current Paperless content, ignoring change hashes."
        .body=${{ transcriptions_only: true, force_transcriptions: true }}></sync-panel>
    `;
  }
}
customElements.define('transcribe-page', TranscribePage);
