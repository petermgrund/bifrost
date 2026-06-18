import { BifrostElement, html, nothing, api, summarize, statusIcon } from './core.js';

/* Relative, human time from an ISO/space timestamp. */
function relTime(iso) {
  if (!iso) return '';
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T'));
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  const days = Math.floor(s / 86400);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/* A run's stored summary is the JSON of its summary event; turn its counts into
   the same terse line the Sync page uses. */
function runResult(r) {
  if (!r.summary) return r.status === 'ok' ? 'No changes' : '';
  try { return summarize(JSON.parse(r.summary).data, true); } catch { return ''; }
}

/* Plain-English label for an internal job id (e.g. sync.paperless.versions). */
const JOB_LABELS = {
  'sync.paperless': 'Paperless → Gramps',
  'sync.paperless.versions': 'Paperless version sync',
  'sync.paperless.transcriptions': 'Rewrite transcriptions',
  'sync.paperless.resync-media': 'Resync media version',
  'sync.immich': 'Immich → Gramps',
  'ocr.gemini': 'Gemini OCR',
  'upload.ocr': 'Document OCR',
  'upload.to-gramps': 'Create Gramps media',
  'places.boundaries': 'Place boundaries',
  'citations.save': 'Citation created',
  'faces.apply': 'Faces applied',
  'faces.link': 'Face linked',
  'faces.repad': 'Face padding',
};
function jobLabel(job) {
  if (!job) return '';
  const preview = job.endsWith('.preview');
  const base = preview ? job.slice(0, -8) : job;
  const label = JOB_LABELS[base]
    || base.replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return preview ? `${label} (preview)` : label;
}

class InboxPage extends BifrostElement {
  static properties = {
    data: { state: true }, error: { state: true }, loading: { state: true },
  };
  constructor() {
    super();
    this.data = null; this.error = ''; this.loading = false;
  }
  connectedCallback() {
    super.connectedCallback();
    this.load();
  }
  async load(refresh = false) {
    this.loading = true; this.error = '';
    try {
      this.data = await api(`/api/inbox${refresh ? '?refresh=1' : ''}`);
    } catch (e) {
      this.error = e.message;
    } finally {
      this.loading = false;
    }
  }

  render() {
    if (this.loading && !this.data) return html`<h1>Home</h1><div class="hint">Loading…</div>`;
    if (this.error && !this.data) return html`<h1>Home</h1>
      <div class="alert">Couldn't load the home page: ${this.error}</div>
      <button class="primary" @click=${() => this.load(true)}>Retry</button>`;
    const d = this.data;
    const todo = (d.attention || []).filter((a) => a.n === null || a.n > 0);
    const runs = d.runs || [];
    return html`
      <div class="pagehead">
        <h1>Home</h1>
        <span class="spacer"></span>
        <button @click=${() => this.load(true)} ?disabled=${this.loading}>
          ${this.loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>

      <h2>Needs attention</h2>
      ${todo.length ? html`<div class="attn">
        ${todo.map((a) => html`<a class="attn-row" href=${a.href}>
          <span class="attn-n ${a.n === null ? 'na' : ''}">${a.n === null ? '—' : a.n}</span>
          <span class="attn-label">${a.label}${a.n === null
            ? html` <span class="hint">(unavailable)</span>` : nothing}</span>
          <span class="attn-go">→</span>
        </a>`)}
      </div>` : html`<p class="hint">All caught up — nothing pending.</p>`}

      <h2>Recent runs</h2>
      ${runs.length ? html`<table class="results runs-table">
        <tr><th></th><th>Task</th><th>Result</th><th>When</th></tr>
        ${runs.map((r) => html`<tr>
          <td>${statusIcon(r.status)}</td>
          <td>${jobLabel(r.job)}</td>
          <td class="hint">${runResult(r)}</td>
          <td class="hint">${relTime(r.started_at)}</td>
        </tr>`)}
      </table>` : html`<p class="hint">No runs yet.</p>`}
    `;
  }
}
customElements.define('inbox-page', InboxPage);
