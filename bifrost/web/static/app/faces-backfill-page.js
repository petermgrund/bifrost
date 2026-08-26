import { BifrostElement, html, nothing, post, btn, spinner, statusLine, summarize } from './core.js';

// Face backfill: the follow-up after new links are made in the Faces section,
// since the Immich sync's update pass checks title/date/file drift, not faces.
class FacesBackfillPage extends BifrostElement {
  static properties = {
    busy: { state: true },
    result: { state: true },
    runEvents: { state: true },
    applied: { state: true },
  };

  constructor() {
    super();
    this.busy = '';
    this.result = null;
    this.runEvents = null;
    this.applied = false;
  }

  async run(apply) {
    this.busy = apply ? 'apply' : 'preview';
    this.result = null;
    this.runEvents = null;
    try {
      const r = await post('/faces/api/apply', { apply });
      this.runEvents = r.events;
      this.applied = apply;
      // the run reports "no person links yet" as an error event, not a throw
      const err = r.events.find((e) => e.kind === 'error');
      const summary = r.events.find((e) => e.kind === 'summary');
      this.result = err ? { kind: 'error', body: err.detail }
        : summary ? { kind: 'ok', body: summarize(summary.data, apply) }
          : { kind: 'error', body: 'no summary event' };
    } catch (e) {
      this.result = { kind: 'error', body: e.message };
    } finally {
      this.busy = '';
    }
  }

  renderRunItems() {
    const rows = this.runEvents.filter((e) => e.kind === 'item');
    if (!rows.length) return nothing;
    return html`<div class="scroll"><table class="cap-width">
      <thead><tr><th>Person</th><th>Media</th><th>Action</th><th></th></tr></thead>
      <tbody>${rows.map((e) => html`<tr>
        <td>${e.title || ''}</td>
        <td class="mono">${e.gramps_id || e.source_id || ''}</td>
        <td>${e.action}${this.applied ? '' : ' (preview)'}</td>
        <td class="small-text secondary-text">${e.detail || ''}</td>
      </tr>`)}</tbody>
    </table></div>`;
  }

  render() {
    return html`
      <h6 class="small">Backfill faces onto synced Gramps media</h6>
      <nav class="wrap">
        ${btn(this.busy === 'preview' ? 'Scanning…' : 'Preview face backfill',
    this.busy !== '', () => this.run(false), 'border')}
        ${btn(this.busy === 'apply' ? 'Applying…' : 'Apply faces',
    this.busy !== '', () => this.run(true))}
        ${this.busy ? spinner : nothing}
        ${this.result ? statusLine(this.result.kind, this.result.body) : nothing}
      </nav>
      ${this.runEvents ? this.renderRunItems() : nothing}`;
  }
}
customElements.define('faces-backfill-page', FacesBackfillPage);
