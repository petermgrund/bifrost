/* Paperless → Gramps sync page. */
import { html } from './core.js';
import { SyncPage, icon } from './sync-page.js';

class PaperlessSyncPage extends SyncPage {
  get source() { return 'paperless'; }
  get heading() { return 'Paperless → Gramps'; }
  get sub() {
    return 'Paperless documents become Gramps media objects w/ metadata and transcription.';
  }
  get itemColLabel() { return 'Paperless document'; }
  get emptyIcon() {
    return icon(html`<path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z"/><path d="M14 3v4h4"/><path d="M9 13h6M9 16h4"/>`, 38, 1.5);
  }
  get emptyTags() {
    const tags = (this.config?.sync_tags || ['doc', 'img']).map((t) => html`<strong>${t}</strong>`);
    const joined = tags.reduce((acc, t, i) => i ? html`${acc} or ${t}` : t, html``);
    return html`Scan documents tagged ${joined} in Paperless and compare them against your Gramps media.`;
  }
  captionFor(tab) {
    return tab === 'preview' ? 'Preview is read-only; click Apply to save.'
      : tab === 'history' ? 'A log of past sync runs.'
      : 'Settings affect future Paperless → Gramps syncs.';
  }

  settingsSections(c) {
    return [
      { key: 'scope', title: 'Sync scope',
        desc: 'Which Paperless documents are imported, and the tags that mark them.',
        body: html`
          <div class="row wrap">${(c.sync_tags || []).map((t) =>
            html`<span class="chip small"><i>sell</i><span>${t}</span></span>`)}</div>
          <div class="grid">
            <div class="s12 m6">${this.field('Paperless public URL', c.public_url)}</div>
            <div class="s12 m6">${this.field('Gramps public URL', c.gramps_public_url)}</div>
          </div>` },
      { key: 'note', title: 'Transcription',
        desc: "How a document's OCR text flows into Gramps as a Transcription note.",
        body: html`
          ${this.switchRow('Attach transcription as a Gramps note', 'Creates or updates a "Transcription" note on the media object.', 'noteOn', true)}
          ${this.field('Transcription tag id', c.transcription_tag_id, { max: '300px' })}` },
      { key: 'version', title: 'Document versions',
        desc: 'Keep Gramps pointed at whichever version you select in Paperless.',
        body: html`
          ${this.switchRow('Auto-repoint when the selected version changes', 'A scheduled job repoints the Gramps media to the version you pick.', 'versionOn', true)}
          <p class="hint"><i>schedule</i> Version repointing runs on the versions_only cron.</p>` },
      { key: 'ids', title: 'Media IDs',
        desc: 'Whether new media get an auto-generated random-6 ID or one you pre-assign.',
        body: this.idModeSegment() },
    ];
  }
}
customElements.define('paperless-sync-page', PaperlessSyncPage);
