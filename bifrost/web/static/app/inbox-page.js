import { BifrostElement, html, api, summarize } from './core.js';

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

const isvg = (paths) => html`<svg width="20" height="20" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
const ICON = {
  ocr: isvg(html`<path d="M4 6h16M4 12h16M4 18h10"/>`),
  paperless: isvg(html`<path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z"/><path d="M14 3v4h4"/>`),
  immich: isvg(html`<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.4"/><path d="m4 18 5-5 4 4 2-2 4 4"/>`),
  faces: isvg(html`<circle cx="12" cy="12" r="9"/><path d="M9 10h.01M15 10h.01"/><path d="M8.5 14.5a4.5 4.5 0 0 0 7 0"/>`),
  citations: isvg(html`<path d="M5 16V6a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H9l-4 4z"/><path d="M9 9h6M9 12h4"/>`),
  places: isvg(html`<path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>`),
};

/* The six pipelines shown as status cards; n comes from /api/inbox attention. */
const PIPELINES = [
  { key: 'ocr', label: 'OCR (Transcribe)', icon: 'ocr', href: '/transcribe', runs: ['ocr.gemini', 'upload.ocr'],
    idle: 'Idle. No documents waiting to transcribe.',
    active: (n) => `${n} document${n === 1 ? '' : 's'} tagged for OCR.`, action: 'Transcribe' },
  { key: 'paperless', label: 'Paperless → Gramps', icon: 'paperless', href: '/sync', runs: ['sync.paperless'],
    idle: 'Up to date. No tagged documents to sync.',
    active: (n) => `${n} document${n === 1 ? '' : 's'} ready to sync into Gramps.`, action: 'Review' },
  { key: 'immich', label: 'Immich → Gramps', icon: 'immich', href: '/sync', runs: ['sync.immich'],
    idle: 'Up to date. No new photos to import.',
    active: (n) => `${n} photo${n === 1 ? '' : 's'} ready to sync into Gramps.`, action: 'Review' },
  { key: 'faces', label: 'Faces', icon: 'faces', href: '/faces', runs: ['faces'],
    idle: 'All detected faces are linked.',
    active: (n) => `${n} detected face${n === 1 ? '' : 's'} waiting to be linked.`, action: 'Link faces' },
  { key: 'citations', label: 'Citations', icon: 'citations', href: '/citations', runs: ['citations'],
    idle: 'Every event has a supporting citation.',
    active: (n) => `${n} event${n === 1 ? '' : 's'} still have no citation.`, action: 'Add citations' },
  { key: 'places', label: 'Places boundaries', icon: 'places', href: '/places', runs: ['places.boundaries'],
    idle: 'All places have an OpenStreetMap overlay.',
    active: (n) => `${n} place${n === 1 ? '' : 's'} missing an OpenStreetMap overlay.`, action: 'Generate' },
];

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

  lastRun(prefixes) {
    const r = (this.data.runs || []).find((x) => prefixes.some((pre) => (x.job || '').startsWith(pre)));
    return r ? relTime(r.started_at) : '—';
  }

  pipelineCard(p) {
    const att = (this.data.attention || []).find((a) => a.key === p.key);
    const n = att ? att.n : null;
    const status = n === null ? 'error' : n > 0 ? 'warn' : 'ok';
    const text = n === null ? 'Status unavailable — service unreachable.'
      : n > 0 ? p.active(n) : p.idle;
    const actionable = n > 0;
    return html`<div class="bf-card" style="gap:var(--bf-space-3)">
      <div style="display:flex;align-items:flex-start;gap:var(--bf-space-3)">
        <span style="flex:none;width:40px;height:40px;border-radius:var(--bf-shape-sm);background:var(--bf-surface-container-high);color:var(--bf-on-surface-variant);display:flex;align-items:center;justify-content:center">${ICON[p.icon]}</span>
        <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:1px">
          <div style="font:var(--bf-title-medium);color:var(--bf-on-surface)">${p.label}</div>
          <div style="font:var(--bf-body-small);color:var(--bf-on-surface-variant)">last run ${this.lastRun(p.runs)}</div>
        </div>
        <span class="bf-dot bf-dot--${status}" style="margin-top:6px"></span>
      </div>
      <div style="font:var(--bf-body-medium);color:var(--bf-on-surface);min-height:40px">${text}</div>
      <div class="bf-actions">
        <a class="bf-btn ${actionable ? 'bf-btn--filled' : 'bf-btn--text'} bf-btn--sm" href=${p.href}>${actionable ? p.action : 'Open'}</a>
      </div>
    </div>`;
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
        <button class="bf-btn bf-btn--filled bf-btn--sm" @click=${() => this.load(true)}>Retry</button></div>`;
    }
    const errs = this.data.errors || [];
    const runs = this.data.runs || [];
    return html`<div class="bf-page">
      <div class="bf-page__head" style="flex-direction:row;align-items:flex-end;gap:var(--bf-space-4)">
        <div style="flex:1">
          <h1 class="bf-page__title">Overview</h1>
          <p class="bf-page__desc">Where each pipeline stands, and what ran recently.</p>
        </div>
        <span style="display:inline-flex;align-items:center;gap:8px;font:var(--bf-body-small);color:var(--bf-on-surface-variant)">
          <span class="bf-dot bf-dot--${errs.length ? 'warn' : 'ok'}"></span>${errs.length
            ? `${errs.length} service${errs.length === 1 ? '' : 's'} unavailable` : 'All services reachable'}</span>
        <button class="bf-btn bf-btn--text bf-btn--sm" ?disabled=${this.loading}
          @click=${() => this.load(true)}>${this.loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>

      <div style="display:flex;flex-direction:column;gap:var(--bf-space-3)">
        <div style="font:var(--bf-title-medium);color:var(--bf-on-surface)">Pipeline status</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:var(--bf-space-4)">
          ${PIPELINES.map((p) => this.pipelineCard(p))}
        </div>
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
