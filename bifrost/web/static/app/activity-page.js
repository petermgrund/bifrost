import { BifrostElement, html, nothing, api } from './core.js';
import { svg } from 'lit';

const CLASSES = ['Person', 'Family', 'Event', 'Place',
                 'Citation', 'Source', 'Note', 'Media', 'Other'];
const LABELS = { Person: 'people', Family: 'families', Event: 'events',
                 Place: 'places', Citation: 'citations', Source: 'sources',
                 Note: 'notes', Media: 'media', Other: 'other' };

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/* "2026-06-08" (a Monday) → "Jun 8–14" / "Jun 29 – Jul 5" */
function weekLabel(iso) {
  const start = new Date(`${iso}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  const m1 = MONTHS[start.getMonth()], m2 = MONTHS[end.getMonth()];
  return m1 === m2
    ? `${m1} ${start.getDate()}–${end.getDate()}`
    : `${m1} ${start.getDate()} – ${m2} ${end.getDate()}`;
}

/* local-date ISO (toISOString would shift to UTC and skew evening dates) */
function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function mondayOf(d) {
  const x = new Date(d);
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return isoDate(x);
}

class ActivityPage extends BifrostElement {
  static properties = {
    weeks: { state: true },     // chronological, gap weeks filled with zeros
    action: { state: true },    // added | edited | deleted
    hidden: { state: true },    // Set of toggled-off classes
    selected: { state: true },  // selected week iso
    tip: { state: true },       // {x, y, week} hover tooltip
  };

  constructor() {
    super();
    this.weeks = null;
    this.cov = [];
    this.action = 'added';
    this.hidden = new Set();
    this.selected = null;
    this.tip = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load(refresh = false) {
    this.weeks = null;
    const r = await api(`/activity/api/weekly${refresh ? '?refresh=1' : ''}`);
    this.cov = r.coverage || [];
    // chronological + fill empty weeks so the timeline is honest
    const byWeek = new Map(r.weeks.map((w) => [w.week, w.actions]));
    const weeks = [];
    if (r.weeks.length) {
      const first = r.weeks[r.weeks.length - 1].week;
      const last = mondayOf(new Date());
      for (let d = new Date(`${first}T00:00:00`); ;) {
        const iso = isoDate(d);
        weeks.push({ week: iso, actions: byWeek.get(iso) || {} });
        if (iso >= last) break;
        d.setDate(d.getDate() + 7);
      }
    }
    this.weeks = weeks;
    this.selected = weeks.length ? weeks[weeks.length - 1].week : null;
  }

  count(w, action, cls) {
    return (w.actions[action] || {})[cls] || 0;
  }

  visTotal(w, action) {
    return CLASSES.reduce(
      (n, c) => n + (this.hidden.has(c) ? 0 : this.count(w, action, c)), 0);
  }

  toggleClass(cls) {
    const h = new Set(this.hidden);
    h.has(cls) ? h.delete(cls) : h.add(cls);
    this.hidden = h;
  }

  // --- chart ---

  chart() {
    const W = this.weeks;
    const slot = Math.max(16, Math.min(44, Math.floor(860 / W.length)));
    const barW = Math.max(8, slot - 6);
    const padL = 34, padT = 12, plotH = 200, padB = 22;
    const width = padL + slot * W.length + 8;
    const height = padT + plotH + padB;
    const max = Math.max(1, ...W.map((w) => this.visTotal(w, this.action)));
    const yMax = Math.ceil(max / 4) * 4;
    const y = (n) => padT + plotH - (n / yMax) * plotH;

    const grid = [0.25, 0.5, 0.75, 1].map((f) => {
      const v = Math.round(yMax * f);
      return svg`<line x1=${padL} x2=${width - 4} y1=${y(v)} y2=${y(v)} class="grid"/>
        <text x=${padL - 5} y=${y(v) + 3.5} class="tick" text-anchor="end">${v}</text>`;
    });

    let prevMonth = null;
    const bars = W.map((w, i) => {
      const x = padL + i * slot;
      const segs = [];
      let acc = 0;
      for (const cls of CLASSES) {
        if (this.hidden.has(cls)) continue;
        const n = this.count(w, this.action, cls);
        if (!n) continue;
        const y1 = y(acc + n), y2 = y(acc);
        segs.push(svg`<rect x=${x} y=${y1} width=${barW} height=${Math.max(1, y2 - y1)}
          class="seg c-${cls.toLowerCase()}"/>`);
        acc += n;
      }
      const d = new Date(`${w.week}T00:00:00`);
      const m = d.getMonth();
      let label = nothing;
      if (m !== prevMonth) {
        label = svg`<text x=${x} y=${height - 7} class="tick">${MONTHS[m]}${m === 0 || prevMonth === null ? ` ’${String(d.getFullYear()).slice(2)}` : ''}</text>`;
        prevMonth = m;
      }
      return svg`<g class="bar"
          @click=${() => (this.selected = w.week)}
          @mousemove=${(e) => (this.tip = { x: e.clientX, y: e.clientY, week: w.week })}
          @mouseleave=${() => (this.tip = null)}>
        ${w.week === this.selected
          ? svg`<rect x=${x - 2} y=${padT - 4} width=${barW + 4} height=${plotH + 8} class="selband"/>`
          : nothing}
        <rect x=${x - 2} y=${padT} width=${barW + 4} height=${plotH + 4} class="hit"/>
        ${segs}
        ${label}
      </g>`;
    });

    return html`<div class="chart-wrap">
      <svg class="chart" viewBox="0 0 ${width} ${height}" width=${width} height=${height}>
        ${grid}${bars}
      </svg>
    </div>`;
  }

  // --- citation-coverage chart: % of events without a citation, per week ---

  covChart() {
    const C = this.cov;
    if (!C.length) return nothing;
    const slot = Math.max(16, Math.min(44, Math.floor(860 / C.length)));
    const barW = Math.max(8, slot - 6);
    const padL = 34, padT = 8, plotH = 110, padB = 22;
    const width = padL + slot * C.length + 8;
    const height = padT + plotH + padB;
    const y = (pct) => padT + plotH - (pct / 100) * plotH;

    const grid = [25, 50, 75, 100].map((v) => svg`
      <line x1=${padL} x2=${width - 4} y1=${y(v)} y2=${y(v)} class="grid"/>
      ${v % 50 === 0 ? svg`<text x=${padL - 5} y=${y(v) + 3.5} class="tick" text-anchor="end">${v}%</text>` : nothing}`);

    let prevMonth = null;
    const bars = C.map((c, i) => {
      const x = padL + i * slot;
      const d = new Date(`${c.week}T00:00:00`);
      const m = d.getMonth();
      let label = nothing;
      if (m !== prevMonth) {
        label = svg`<text x=${x} y=${height - 7} class="tick">${MONTHS[m]}${m === 0 || prevMonth === null ? ` ’${String(d.getFullYear()).slice(2)}` : ''}</text>`;
        prevMonth = m;
      }
      return svg`<g class="bar"
          @click=${() => (this.selected = c.week)}
          @mousemove=${(e) => (this.tip = { x: e.clientX, y: e.clientY, week: c.week, kind: 'cov' })}
          @mouseleave=${() => (this.tip = null)}>
        ${c.week === this.selected
          ? svg`<rect x=${x - 2} y=${padT - 4} width=${barW + 4} height=${plotH + 8} class="selband"/>`
          : nothing}
        <rect x=${x - 2} y=${padT} width=${barW + 4} height=${plotH + 4} class="hit"/>
        <rect x=${x} y=${y(c.pct)} width=${barW} height=${Math.max(1, (c.pct / 100) * plotH)} class="seg covseg"/>
        ${label}
      </g>`;
    });

    const cur = C[C.length - 1];
    return html`<h2>Events without a citation
        <span class="hint">now ${cur.pct}% (${cur.uncited} of ${cur.total})</span></h2>
      <div class="chart-wrap">
        <svg class="chart" viewBox="0 0 ${width} ${height}" width=${width} height=${height}>
          ${grid}${bars}
        </svg>
      </div>`;
  }

  tooltip() {
    if (!this.tip) return nothing;
    const pos = `left:${this.tip.x + 14}px; top:${this.tip.y + 10}px`;
    if (this.tip.kind === 'cov') {
      const c = this.cov.find((x) => x.week === this.tip.week);
      if (!c) return nothing;
      return html`<div class="chart-tip" style=${pos}>
        <div class="tiphead">${weekLabel(c.week)}</div>
        <div>${c.pct}% uncited · ${c.uncited} of ${c.total} events</div>
      </div>`;
    }
    const w = this.weeks.find((x) => x.week === this.tip.week);
    if (!w) return nothing;
    const rows = CLASSES
      .filter((c) => !this.hidden.has(c) && this.count(w, this.action, c))
      .map((c) => html`<div><span class="dot c-${c.toLowerCase()}"></span>${LABELS[c]} ${this.count(w, this.action, c)}</div>`);
    return html`<div class="chart-tip" style=${pos}>
      <div class="tiphead">${weekLabel(w.week)} · ${this.visTotal(w, this.action)} ${this.action}</div>
      ${rows}
    </div>`;
  }

  // --- stat cards (for the current action, visible classes) ---

  stats() {
    const W = this.weeks;
    const n = W.length;
    const cur = n ? this.visTotal(W[n - 1], this.action) : 0;
    const prev = n > 1 ? this.visTotal(W[n - 2], this.action) : 0;
    const last4 = W.slice(-4).map((w) => this.visTotal(w, this.action));
    const avg = last4.length ? Math.round(last4.reduce((a, b) => a + b, 0) / last4.length) : 0;
    let best = null;
    for (const w of W) {
      const t = this.visTotal(w, this.action);
      if (!best || t > best.t) best = { week: w.week, t };
    }
    const card = (value, label) => html`<div class="stat">
      <div class="value">${value}</div><div class="label">${label}</div></div>`;
    return html`<div class="stats">
      ${card(cur, 'this week')}
      ${card(prev, 'last week')}
      ${card(avg, '4-week avg')}
      ${best && best.t ? card(best.t, `best · ${weekLabel(best.week)}`) : nothing}
    </div>`;
  }

  // --- selected-week detail (all three actions) ---

  detail() {
    const w = this.weeks.find((x) => x.week === this.selected);
    if (!w) return nothing;
    const rows = CLASSES.filter((c) =>
      ['added', 'edited', 'deleted'].some((a) => this.count(w, a, c)));
    const cell = (n) => (n ? n : '');
    return html`<h2>${weekLabel(w.week)}, ${w.week.slice(0, 4)}</h2>
      ${rows.length ? html`<table class="results weekdetail">
        <tr><th></th><th>added</th><th>edited</th><th>deleted</th></tr>
        ${rows.map((c) => html`<tr>
          <td><span class="dot c-${c.toLowerCase()}"></span>${LABELS[c]}</td>
          <td>${cell(this.count(w, 'added', c))}</td>
          <td>${cell(this.count(w, 'edited', c))}</td>
          <td>${cell(this.count(w, 'deleted', c))}</td>
        </tr>`)}
        <tr class="totalrow"><td>total</td>
          ${['added', 'edited', 'deleted'].map((a) => html`<td>${cell(
            CLASSES.reduce((s, c) => s + this.count(w, a, c), 0))}</td>`)}
        </tr>
      </table>` : html`<p class="hint">No activity this week.</p>`}`;
  }

  render() {
    if (!this.weeks) return html`<h1>Activity</h1><div class="hint">Loading…</div>`;
    const chip = (a, label) => html`<button class="chip ${this.action === a ? 'active' : ''}"
      @click=${() => (this.action = a)}>${label}</button>`;
    return html`
      <div class="pagehead">
        <h1>Activity</h1>
        <span class="spacer"></span>
        <button @click=${() => this.load(true)}>Refresh</button>
      </div>
      <div class="toolbar">
        ${chip('added', 'Added')}${chip('edited', 'Edited')}${chip('deleted', 'Deleted')}
      </div>
      ${this.stats()}
      ${this.chart()}
      <div class="legend">
        ${CLASSES.map((c) => html`<button class="legitem ${this.hidden.has(c) ? 'off' : ''}"
          @click=${() => this.toggleClass(c)}>
          <span class="dot c-${c.toLowerCase()}"></span>${LABELS[c]}</button>`)}
      </div>
      ${this.covChart()}
      ${this.detail()}
      ${this.tooltip()}`;
  }
}
customElements.define('activity-page', ActivityPage);
