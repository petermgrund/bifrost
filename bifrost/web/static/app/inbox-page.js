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

// key, label, sparkline colour class (matches bifrost.css .c-*)
const SNAP = [
  ['people', 'People', 'person'], ['events', 'Events', 'event'],
  ['places', 'Places', 'place'], ['citations', 'Citations', 'citation'],
  ['media', 'Media', 'media'], ['sources', 'Sources', 'source'],
];

/* Min/max-scaled mini sparkline (growth shows even when counts barely move). */
function sparkline(vals, cls) {
  if (!vals || vals.length < 2) return nothing;
  const w = 6, padY = 4, H = 34;
  const width = (vals.length - 1) * w + 6;
  const max = Math.max(...vals), min = Math.min(...vals);
  const span = Math.max(1, max - min);
  const y = (v) => padY + (H - 2 * padY) * (1 - (v - min) / span);
  const pts = vals.map((v, i) => `${3 + i * w},${y(v).toFixed(1)}`).join(' ');
  const lastX = 3 + (vals.length - 1) * w;
  return html`<svg class="snapspark" viewBox="0 0 ${width} ${H}" height=${H}
    preserveAspectRatio="none">
    <polyline points=${pts} class="c-${cls}"/>
    <path d="M ${lastX} ${y(vals[vals.length - 1]).toFixed(1)} l .01 0" class="endcap c-${cls}"/>
  </svg>`;
}

/* "▲ +N this week" / "▼ −N" / "steady" from the last two weekly points. */
function deltaBadge(vals) {
  if (!vals || vals.length < 2) return nothing;
  const d = vals[vals.length - 1] - vals[vals.length - 2];
  if (d > 0) return html`<span class="snapdelta up">▲ +${d} this wk</span>`;
  if (d < 0) return html`<span class="snapdelta down">▼ ${d} this wk</span>`;
  return html`<span class="snapdelta">steady</span>`;
}

class InboxPage extends BifrostElement {
  static properties = {
    data: { state: true }, error: { state: true }, loading: { state: true },
    trends: { state: true },
  };
  constructor() {
    super();
    this.data = null; this.error = ''; this.loading = false; this.trends = null;
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
    // Trends are a progressive enhancement: cards render instantly with live
    // counts; sparklines/deltas fill in when the (cached) history returns.
    this.loadTrends(refresh);
  }
  async loadTrends(refresh = false) {
    try {
      this.trends = await api(`/api/inbox/trends${refresh ? '?refresh=true' : ''}`);
    } catch { /* leave counts-only */ }
  }
  renderSnapshot() {
    const snap = (this.data && this.data.snapshot) || {};
    const cards = SNAP.filter(([k]) => snap[k] != null);
    if (!cards.length) return nothing;
    const tr = this.trends;
    return html`<h2>Snapshot</h2>
      <div class="snapgrid">
        ${cards.map(([key, label, cls]) => {
          const series = tr && tr.series ? tr.series[key] : null;
          return html`<a class="snapcard" href="/activity"
            title="${label} over time — open Activity">
            <div class="snaptop">
              <span class="snaplabel">${label}</span>
              <span class="snapval">${snap[key]}</span>
            </div>
            ${sparkline(series, cls)}
            <div class="snapfoot">
              ${deltaBadge(series)}
              ${key === 'events' && tr && tr.coverage_pct != null
                ? html`<span class="snapcov">${tr.coverage_pct}% cited</span>` : nothing}
            </div>
          </a>`;
        })}
      </div>`;
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

      ${this.renderSnapshot()}

      <h2>Recent runs</h2>
      ${runs.length ? html`<table class="results">
        <tr><th></th><th>job</th><th>result</th><th>when</th></tr>
        ${runs.map((r) => html`<tr>
          <td>${statusIcon(r.status)}</td>
          <td>${r.job}</td>
          <td class="hint">${runResult(r)}</td>
          <td class="hint">${relTime(r.started_at)}</td>
        </tr>`)}
      </table>` : html`<p class="hint">No runs yet.</p>`}
    `;
  }
}
customElements.define('inbox-page', InboxPage);
