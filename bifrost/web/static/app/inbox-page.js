import { BifrostElement, html, api, summarize, mdBtn } from './core.js';

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

  runRow(r) {
    const [dot, label] = r.status === 'ok' ? ['ok', 'Done']
      : r.status === 'error' ? ['error', 'Failed'] : ['warn', r.status || '—'];
    return html`<tr>
      <td>${jobLabel(r.job)}</td>
      <td class="bf-muted">${runResult(r)}</td>
      <td><span style="display:inline-flex;align-items:center;gap:8px"><span class="bf-dot bf-dot--${dot}"></span>${label}</span></td>
      <td class="bf-muted">${relTime(r.started_at)}</td>
    </tr>`;
  }

  render() {
    if (this.loading && !this.data) {
      return html`<div class="bf-state bf-state--loading"><div class="bf-spinner"></div>
        <div class="bf-state__desc">Loading…</div></div>`;
    }
    if (this.error && !this.data) {
      return html`<div class="bf-state bf-state--error">
        <div class="bf-state__title">Couldn't load the home page</div>
        <div class="bf-state__desc">${this.error}</div>
        ${mdBtn('filled', 'Retry', false, () => this.load(true))}</div>`;
    }
    const errs = this.data.errors || [];
    const runs = this.data.runs || [];
    return html`<div class="bf-page">
      <div class="bf-page__head" style="flex-direction:row;align-items:flex-end;gap:var(--bf-space-4)">
        <div style="flex:1">
          <h1 class="bf-page__title">Overview</h1>
          <p class="bf-page__desc">What ran recently.</p>
        </div>
        <span style="display:inline-flex;align-items:center;gap:8px;font:var(--bf-body-small);color:var(--bf-on-surface-variant)">
          <span class="bf-dot bf-dot--${errs.length ? 'warn' : 'ok'}"></span>${errs.length
            ? `${errs.length} service${errs.length === 1 ? '' : 's'} unavailable` : 'All services reachable'}</span>
        <md-text-button ?disabled=${this.loading}
          @click=${() => this.load(true)}>${this.loading ? 'Refreshing…' : 'Refresh'}</md-text-button>
      </div>

      <div class="bf-card">
        <div class="bf-card__head">
          <div class="bf-card__title">Recent runs</div>
          <div class="bf-card__desc">The last operations across every pipeline.</div>
        </div>
        ${runs.length ? html`<table class="bf-table">
          <thead><tr><th style="width:175px">Pipeline</th><th>Result</th>
            <th style="width:120px">Status</th><th style="width:110px">When</th></tr></thead>
          <tbody>${runs.map((r) => this.runRow(r))}</tbody>
        </table>` : html`<div class="bf-summary">No runs yet.</div>`}
      </div>
    </div>`;
  }
}
customElements.define('inbox-page', InboxPage);
