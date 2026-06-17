import { BifrostElement, html, nothing, post, summarize, hasWork, iconYes, iconNo } from './core.js';

const GROUPS = [
  ['doc', 'Documents'], ['media', 'Media'], ['note', 'Transcriptions'],
  ['face', 'Faces'], ['place', 'Places'],
];

// Same media-id shape the generator and backend enforce.
const MANUAL_RE = /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{6}$/;

/* One sync panel: preview -> review -> apply. Source + optional fixed body. */
class SyncPanel extends BifrostElement {
  static properties = {
    label: {}, source: {}, body: { type: Object }, blurb: {}, maintenance: { type: Boolean },
    result: { state: true }, status: { state: true }, canApply: { state: true }, running: { state: true },
    manualMode: { state: true },
  };
  constructor() {
    super();
    this.body = {}; this.maintenance = false;
    this.result = null; this.status = ''; this.canApply = false; this.running = false;
    this.manualMode = false;
  }

  // Read manual id inputs straight from the DOM (avoids per-keystroke re-render).
  collectManualIds() {
    const out = {};
    for (const el of this.renderRoot.querySelectorAll('input.manualid')) {
      const v = el.value.trim();
      if (v) out[el.dataset.sid] = v;
    }
    return out;
  }

  async run(apply) {
    this.running = true;
    this.status = apply ? 'Applying…' : 'Previewing…';
    if (!apply) this.result = null;
    try {
      const body = (apply && this.manualMode)
        ? { ...this.body, manual_ids: this.collectManualIds() } : this.body;
      const payload = await post(`/sync/api/${this.source}/${apply ? 'apply' : 'preview'}`, body);
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
    const isPreview = this.result && !this.result.error && !this.result.apply;
    return html`<section class="syncpanel ${this.maintenance ? 'maintenance' : ''}">
      <h2>${this.label}</h2>
      ${this.blurb ? html`<p class="hint">${this.blurb}</p>` : nothing}
      <div class="toolbar">
        <button class="${this.canApply ? '' : 'primary'}" ?disabled=${this.running}
          @click=${() => this.run(false)}>Preview</button>
        <button class="${this.canApply ? 'primary' : ''}" ?disabled=${!this.canApply || this.running}
          @click=${() => this.run(true)}>Apply</button>
        ${!this.maintenance && this.source !== 'ocr' ? html`<label class="hint manualtoggle">
          <input type="checkbox" .checked=${this.manualMode}
            @change=${(e) => (this.manualMode = e.target.checked)}>
          Assign my own Gramps IDs</label>` : nothing}
        ${this.status ? html`<span class="hint">${this.status}</span>` : nothing}
      </div>
      ${this.manualMode && isPreview ? html`<p class="hint">Type a 6-char id (safe
        alphabet) for any new item; blanks get an auto id. A taken id is rejected on
        apply and that item is skipped.</p>` : nothing}
      ${this.result ? renderResult(this.result, this.manualMode && isPreview) : nothing}
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

function manualCell(e) {
  // Validity is shown by an icon (shape + colour), not just a red border.
  return html`<span class="manualwrap">
    <input class="manualid" type="text" maxlength="6" placeholder="auto"
      data-sid=${e.source_id} spellcheck="false"
      @input=${(ev) => {
        const v = ev.target.value.toUpperCase();
        ev.target.value = v;
        const has = !!v, ok = MANUAL_RE.test(v);
        ev.target.classList.toggle('invalid', has && !ok);
        const w = ev.target.parentElement;
        w.classList.toggle('valid', has && ok);
        w.classList.toggle('bad', has && !ok);
      }}>${iconYes}${iconNo}</span>`;
}

function renderResult(payload, manual = false) {
  if (payload.error) return html`<div class="results"><div class="action-failed">${payload.error}</div></div>`;
  const items = payload.events.filter((e) => e.kind === 'item');
  const errors = payload.events.filter((e) => e.kind === 'error');
  const counts = (payload.events.find((e) => e.kind === 'summary') || {}).data;
  return html`<div class="results">
    ${GROUPS.map(([entity, label]) => {
      const rows = items.filter((e) => e.entity === entity);
      if (!rows.length) return nothing;
      // structured columns: union of cols keys across the group's rows,
      // in first-seen order; plain detail column only as fallback
      const colKeys = [...new Set(rows.flatMap((e) => Object.keys(e.data?.cols || {})))];
      // Show the detail column whenever ANY row has a detail (e.g. a failed
      // row's reason), even alongside rows that have structured columns.
      const hasDetail = rows.some((e) => e.detail);
      // Only media/doc rows mint a media id; faces/notes/places never do.
      const mintsId = entity === 'media' || entity === 'doc';
      const showManual = manual && mintsId && rows.some((e) => e.action === 'would_create' && e.source_id);
      return html`<h3>${label} <span class="hint">(${rows.length})</span></h3>
        <table class="results">
          <tr><th>action</th><th>what</th>
            ${showManual ? html`<th>my id</th>` : nothing}
            ${colKeys.map((k) => html`<th>${k}</th>`)}
            ${hasDetail ? html`<th>detail</th>` : nothing}</tr>
          ${rows.map((e) => {
            const canManual = showManual && e.action === 'would_create' && e.source_id;
            return html`<tr>
            <td class="action-${e.action}">${e.action.replace('_', ' ')}</td>
            <td>${e.title || e.source_id}${e.gramps_id && !canManual
              ? html` <span class="hint">${e.gramps_id}</span>` : nothing}</td>
            ${showManual ? html`<td>${canManual ? manualCell(e) : nothing}</td>` : nothing}
            ${colKeys.map((k) => html`<td class="hint">${e.data?.cols?.[k] ?? ''}</td>`)}
            ${hasDetail ? html`<td class="hint">${e.detail || ''}</td>` : nothing}</tr>`;
          })}
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
      <sync-panel source="ocr" label="Gemini OCR → Paperless"
        blurb="Documents you tag are transcribed by Gemini and written into the same Paperless document's text (in place) and tagged for transcription, so the next Gramps sync turns it into a note automatically. Preview is free; Apply calls Gemini."></sync-panel>
      <resync-panel></resync-panel>
      <sync-panel source="paperless" label="Rewrite all transcription notes" maintenance
        blurb="Re-writes every transcription note from current Paperless content, ignoring change hashes."
        .body=${{ transcriptions_only: true, force_transcriptions: true }}></sync-panel>
    `;
  }
}
customElements.define('sync-page', SyncPage);
