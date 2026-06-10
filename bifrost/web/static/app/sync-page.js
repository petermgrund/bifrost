import { BifrostElement, html, nothing, post, summarize, hasWork } from './core.js';

const GROUPS = [
  ['doc', 'Documents'], ['media', 'Media'], ['note', 'Transcriptions'],
  ['face', 'Faces'], ['place', 'Places'],
];

/* One sync panel: preview -> review -> apply. Source + optional fixed body. */
class SyncPanel extends BifrostElement {
  static properties = {
    label: {}, source: {}, body: { type: Object }, blurb: {}, maintenance: { type: Boolean },
    result: { state: true }, status: { state: true }, canApply: { state: true }, running: { state: true },
  };
  constructor() {
    super();
    this.body = {}; this.maintenance = false;
    this.result = null; this.status = ''; this.canApply = false; this.running = false;
  }

  async run(apply) {
    this.running = true;
    this.status = apply ? 'Applying…' : 'Previewing…';
    if (!apply) this.result = null;
    try {
      const payload = await post(`/sync/api/${this.source}/${apply ? 'apply' : 'preview'}`, this.body);
      this.result = payload;
      const counts = (payload.events.find((e) => e.kind === 'summary') || {}).data;
      if (apply) {
        this.canApply = false;
        this.status = '';
      } else {
        this.canApply = hasWork(counts);
        this.status = '';
      }
    } catch (e) {
      this.result = { error: e.message };
      this.status = '';
    } finally {
      this.running = false;
    }
  }

  render() {
    return html`<section class="syncpanel ${this.maintenance ? 'maintenance' : ''}">
      <h2>${this.label}</h2>
      ${this.blurb ? html`<p class="hint">${this.blurb}</p>` : nothing}
      <div class="toolbar">
        <button class="${this.canApply ? '' : 'primary'}" ?disabled=${this.running}
          @click=${() => this.run(false)}>Preview</button>
        <button class="${this.canApply ? 'primary' : ''}" ?disabled=${!this.canApply || this.running}
          @click=${() => this.run(true)}>Apply</button>
        ${this.status ? html`<span class="hint">${this.status}</span>` : nothing}
      </div>
      ${this.result ? renderResult(this.result) : nothing}
    </section>`;
  }
}
customElements.define('sync-panel', SyncPanel);

/* Single-object transcription resync — keyed on a typed media id. */
class ResyncPanel extends BifrostElement {
  static properties = {
    result: { state: true }, mapping: { state: true }, canApply: { state: true }, running: { state: true },
  };
  constructor() {
    super();
    this.result = null; this.mapping = ''; this.canApply = false; this.running = false;
  }
  get mediaId() { return this.renderRoot.querySelector('#resync-id')?.value.trim() || ''; }

  async run(apply) {
    const media_id = this.mediaId;
    if (!media_id) { this.mapping = 'Enter a media ID.'; return; }
    this.running = true;
    if (!apply) this.result = null;
    try {
      const payload = await post('/sync/api/paperless/resync-media', { media_id, apply });
      this.result = payload;
      this.mapping = `${payload.media_id} → #${payload.doc_id}`;
      const c = (payload.events.find((e) => e.kind === 'summary') || {}).data || {};
      this.canApply = !apply && (c.tx_created || 0) + (c.tx_updated || 0) > 0;
    } catch (e) {
      this.result = { error: e.message }; this.mapping = ''; this.canApply = false;
    } finally {
      this.running = false;
    }
  }

  render() {
    return html`<section class="syncpanel maintenance">
      <h2>Resync one object's transcription</h2>
      <div class="toolbar">
        <input type="text" id="resync-id" placeholder="Media ID" style="max-width:11rem"
          @input=${() => { this.canApply = false; }}
          @keydown=${(e) => { if (e.key === 'Enter') this.run(false); }}>
        <button class="${this.canApply ? '' : 'primary'}" ?disabled=${this.running}
          @click=${() => this.run(false)}>Preview</button>
        <button class="${this.canApply ? 'primary' : ''}" ?disabled=${!this.canApply || this.running}
          @click=${() => this.run(true)}>Apply</button>
        ${this.mapping ? html`<span class="hint">${this.mapping}</span>` : nothing}
      </div>
      ${this.result ? renderResult(this.result) : nothing}
    </section>`;
  }
}
customElements.define('resync-panel', ResyncPanel);

function renderResult(payload) {
  if (payload.error) return html`<div class="results"><div class="action-failed">${payload.error}</div></div>`;
  const items = payload.events.filter((e) => e.kind === 'item');
  const errors = payload.events.filter((e) => e.kind === 'error');
  const counts = (payload.events.find((e) => e.kind === 'summary') || {}).data;
  return html`<div class="results">
    ${GROUPS.map(([entity, label]) => {
      const rows = items.filter((e) => e.entity === entity);
      if (!rows.length) return nothing;
      return html`<h3>${label} <span class="hint">(${rows.length})</span></h3>
        <table class="results">
          <tr><th>action</th><th>what</th><th>detail</th></tr>
          ${rows.map((e) => html`<tr>
            <td class="action-${e.action}">${e.action.replace('_', ' ')}</td>
            <td>${e.title || e.source_id}${e.gramps_id ? html` <span class="hint">${e.gramps_id}</span>` : nothing}</td>
            <td class="hint">${e.detail || ''}</td></tr>`)}
        </table>`;
    })}
    ${errors.length ? html`<h3 class="action-failed">Errors</h3>${errors.map((e) => html`<div class="action-failed">${e.detail}</div>`)}` : nothing}
    <div class="summary-line">${summarize(counts, payload.apply)}</div>
  </div>`;
}

class SyncPage extends BifrostElement {
  render() {
    return html`
      <h1>Sync</h1>
      <sync-panel source="paperless" label="Paperless → Gramps"
        blurb="Tagged documents become Gramps media; versions, titles, dates and transcriptions stay current."></sync-panel>
      <sync-panel source="immich" label="Immich → Gramps"
        blurb="Tagged photos become Gramps media, with dates, places, descriptions and faces."></sync-panel>
      <resync-panel></resync-panel>
      <sync-panel source="paperless" label="Rewrite all transcription notes" maintenance
        blurb="Re-writes every transcription note from current Paperless content, ignoring change hashes."
        .body=${{ transcriptions_only: true, force_transcriptions: true }}></sync-panel>
    `;
  }
}
customElements.define('sync-page', SyncPage);
