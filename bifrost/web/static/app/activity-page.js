import { BifrostElement, html, nothing, api, post } from './core.js';
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
    cov: { state: true },       // [{week, total, c0, c1, c2}]
    thisWeek: { state: true },  // current-week detail
    grampsUrl: { state: true },
    view: { state: true },      // dash | week
    action: { state: true },    // added | edited | deleted
    hidden: { state: true },    // Set of toggled-off classes
    selected: { state: true },  // selected week iso
    tip: { state: true },       // {x, y, week, kind} hover tooltip
    llm: { state: true },       // Anthropic key configured
    interp: { state: true },    // LLM weekly interpretation text
    interpBusy: { state: true },
  };

  constructor() {
    super();
    this.weeks = null;
    this.cov = [];
    this.totals = [];
    this.thisWeek = null;
    this.grampsUrl = '';
    this.view = 'dash';
    this.action = 'added';
    this.hidden = new Set();
    this.selected = null;
    this.tip = null;
    this.llm = false;
    this.interp = null;
    this.interpBusy = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load(refresh = false) {
    this.weeks = null;
    const r = await api(`/activity/api/weekly${refresh ? '?refresh=1' : ''}`);
    this.cov = r.coverage || [];
    this.totals = r.totals || [];
    this.thisWeek = r.this_week;
    this.grampsUrl = r.gramps_url || '';
    this.llm = !!r.llm;
    this.interp = null;
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

  // --- main chart ---

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

  // --- citation-coverage chart: events by citation count, % stacked ---

  covChart() {
    const C = this.cov;
    if (!C.length) return nothing;
    const slot = Math.max(16, Math.min(44, Math.floor(860 / C.length)));
    const barW = Math.max(8, slot - 6);
    const padL = 38, padT = 8, plotH = 120, padB = 22;
    const width = padL + slot * C.length + 8;
    const height = padT + plotH + padB;
    const y = (pct) => padT + plotH - (pct / 100) * plotH;

    const grid = [25, 50, 75, 100].map((v) => svg`
      <line x1=${padL} x2=${width - 4} y1=${y(v)} y2=${y(v)} class="grid"/>
      ${v % 50 === 0 ? svg`<text x=${padL - 5} y=${y(v) + 3.5} class="tick" text-anchor="end">${v}%</text>` : nothing}`);

    let prevMonth = null;
    const bars = C.map((c, i) => {
      const x = padL + i * slot;
      const segs = [];
      let acc = 0;                                  // stack bottom-up: 2+ , 1 , 0
      for (const [key, cls] of [['c2', 'cov2'], ['c1', 'cov1'], ['c0', 'cov0']]) {
        const pct = c.total ? (c[key] / c.total) * 100 : 0;
        if (pct > 0) {
          segs.push(svg`<rect x=${x} y=${y(acc + pct)} width=${barW}
            height=${Math.max(1, (pct / 100) * plotH)} class="seg ${cls}"/>`);
        }
        acc += pct;
      }
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
        ${segs}
        ${label}
      </g>`;
    });

    const cur = C[C.length - 1];
    return html`<p class="hint">Share of events by citation count, week by week —
        now ${cur.c0} uncited · ${cur.c1} with one · ${cur.c2} with 2+ (of ${cur.total}).</p>
      <div class="chart-wrap">
        <svg class="chart" viewBox="0 0 ${width} ${height}" width=${width} height=${height}>
          ${grid}${bars}
        </svg>
      </div>
      <div class="legend">
        <span class="legitem"><span class="dot cov0"></span>uncited</span>
        <span class="legitem"><span class="dot cov1"></span>1 citation</span>
        <span class="legitem"><span class="dot cov2"></span>2+ citations</span>
      </div>`;
  }

  // --- database size over time: one sparkline per class ---

  sparkGrid() {
    const T = this.totals;
    if (!T.length) return nothing;
    const classes = CLASSES.filter((c) => c !== 'Other');
    const w = 8, padY = 5, H = 56;
    const width = (T.length - 1) * w + 8;
    return html`<div class="sparkgrid">
        ${classes.map((cls) => {
          const vals = T.map((t) => t.counts[cls] || 0);
          const max = Math.max(1, ...vals);
          const y = (v) => padY + (H - 2 * padY) * (1 - v / max);
          const pts = vals.map((v, i) => `${4 + i * w},${y(v).toFixed(1)}`).join(' ');
          const last = vals[vals.length - 1];
          return html`<div class="spark">
            <div class="head"><span class="dot c-${cls.toLowerCase()}"></span>${LABELS[cls]}
              <span class="now">${last}</span></div>
            <svg viewBox="0 0 ${width} ${H}" preserveAspectRatio="none" height="${H}"
              @mouseleave=${() => (this.tip = null)}>
              <polyline points=${pts} class="c-${cls.toLowerCase()}"/>
              <path d="M ${4 + (vals.length - 1) * w} ${y(last).toFixed(1)} l .01 0"
                class="endcap c-${cls.toLowerCase()}"/>
              ${T.map((t, i) => svg`<rect x=${i * w} y="0" width=${w} height=${H} class="hit"
                @mousemove=${(e) => (this.tip = { x: e.clientX, y: e.clientY, week: t.week, kind: 'tot', cls })}/>`)}
            </svg>
          </div>`;
        })}
      </div>`;
  }

  tooltip() {
    if (!this.tip) return nothing;
    const pos = `left:${this.tip.x + 14}px; top:${this.tip.y + 10}px`;
    if (this.tip.kind === 'day') {
      const d = (this.thisWeek?.days || []).find((x) => x.day === this.tip.week);
      if (!d) return nothing;
      return html`<div class="chart-tip" style=${pos}>
        <div class="tiphead">${d.day}</div>
        <div><span class="dot act-added"></span>added ${d.added}</div>
        <div><span class="dot act-edited"></span>edited ${d.edited}</div>
        <div><span class="dot act-deleted"></span>deleted ${d.deleted}</div>
      </div>`;
    }
    if (this.tip.kind === 'tot') {
      const t = this.totals.find((x) => x.week === this.tip.week);
      if (!t) return nothing;
      const cls = this.tip.cls;
      return html`<div class="chart-tip" style=${pos}>
        <div class="tiphead">${weekLabel(t.week)}</div>
        <div><span class="dot c-${cls.toLowerCase()}"></span>${t.counts[cls] || 0} ${LABELS[cls]}</div>
      </div>`;
    }
    if (this.tip.kind === 'cov') {
      const c = this.cov.find((x) => x.week === this.tip.week);
      if (!c) return nothing;
      const pct = (n) => (c.total ? Math.round((100 * n) / c.total) : 0);
      return html`<div class="chart-tip" style=${pos}>
        <div class="tiphead">${weekLabel(c.week)} · ${c.total} events</div>
        <div><span class="dot cov0"></span>uncited ${c.c0} (${pct(c.c0)}%)</div>
        <div><span class="dot cov1"></span>1 citation ${c.c1} (${pct(c.c1)}%)</div>
        <div><span class="dot cov2"></span>2+ citations ${c.c2} (${pct(c.c2)}%)</div>
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

  // --- "This week" view: week-over-week analytics ---

  wTotal(w, action) {
    return w ? CLASSES.reduce((n, c) => n + this.count(w, action, c), 0) : 0;
  }

  dayChart(tw) {
    if (!tw.days.some((d) => d.added || d.edited || d.deleted)) return nothing;
    const slot = 92, barW = 56, padL = 34, padT = 10, plotH = 130, padB = 22;
    const width = padL + slot * 7 + 8;
    const height = padT + plotH + padB;
    const max = Math.max(1, ...tw.days.map((d) => d.added + d.edited + d.deleted));
    const yMax = Math.ceil(max / 4) * 4;
    const y = (n) => padT + plotH - (n / yMax) * plotH;
    const grid = [0.5, 1].map((f) => {
      const v = Math.round(yMax * f);
      return svg`<line x1=${padL} x2=${width - 4} y1=${y(v)} y2=${y(v)} class="grid"/>
        <text x=${padL - 5} y=${y(v) + 3.5} class="tick" text-anchor="end">${v}</text>`;
    });
    const bars = tw.days.map((d, i) => {
      const x = padL + i * slot + (slot - barW) / 2;
      const segs = [];
      let acc = 0;
      for (const [key, cls] of [['added', 'act-added'], ['edited', 'act-edited'], ['deleted', 'act-deleted']]) {
        if (!d[key]) continue;
        segs.push(svg`<rect x=${x} y=${y(acc + d[key])} width=${barW}
          height=${Math.max(1, y(acc) - y(acc + d[key]))} class="seg ${cls}"/>`);
        acc += d[key];
      }
      return svg`<g class="bar"
          @mousemove=${(e) => (this.tip = { x: e.clientX, y: e.clientY, week: d.day, kind: 'day' })}
          @mouseleave=${() => (this.tip = null)}>
        <rect x=${x - 4} y=${padT} width=${barW + 8} height=${plotH + 4} class="hit"/>
        ${segs}
        <text x=${x} y=${height - 7} class="tick">${d.day}</text>
      </g>`;
    });
    return html`<h2>By day</h2>
      <div class="chart-wrap">
        <svg class="chart" viewBox="0 0 ${width} ${height}" width=${width} height=${height}>
          ${grid}${bars}
        </svg>
      </div>
      <div class="legend">
        <span class="legitem"><span class="dot act-added"></span>added</span>
        <span class="legitem"><span class="dot act-edited"></span>edited</span>
        <span class="legitem"><span class="dot act-deleted"></span>deleted</span>
      </div>`;
  }

  classCompare(cur, prev) {
    const touched = (w, cls) => ['added', 'edited', 'deleted']
      .reduce((n, a) => n + (w ? this.count(w, a, cls) : 0), 0);
    const rows = CLASSES
      .map((cls) => ({ cls, now: touched(cur, cls), was: touched(prev, cls) }))
      .filter((r) => r.now || r.was);
    if (!rows.length) return nothing;
    const max = Math.max(...rows.map((r) => Math.max(r.now, r.was)));
    const bar = (v, cssCls) => html`<div class="cmpbar">
      <div class="fill ${cssCls}" style="width:${(100 * v) / max}%"></div>
      <span class="num">${v || ''}</span></div>`;
    return html`<h2>By type <span class="hint">this week vs last</span></h2>
      <div class="cmp">
        ${rows.map((r) => html`<div class="cmprow">
          <span class="clabel"><span class="dot c-${r.cls.toLowerCase()}"></span>${LABELS[r.cls]}</span>
          <div class="cmpbars">${bar(r.now, `c-${r.cls.toLowerCase()}`)}${bar(r.was, 'was')}</div>
        </div>`)}
      </div>`;
  }

  insights(tw, cur, prev) {
    const out = [];
    const tot = (w) => ['added', 'edited', 'deleted'].reduce((n, a) => n + this.wTotal(w, a), 0);
    const now = tot(cur), was = tot(prev);
    if (now && was) {
      const pct = Math.round((100 * (now - was)) / was);
      out.push(`${now} objects touched — ${pct >= 0 ? 'up' : 'down'} ${Math.abs(pct)}% on last week (${was}).`);
    } else if (now) {
      out.push(`${now} objects touched; last week had no activity.`);
    }
    const busiest = [...tw.days].sort((a, b) =>
      (b.added + b.edited + b.deleted) - (a.added + a.edited + a.deleted))[0];
    if (busiest && (busiest.added + busiest.edited + busiest.deleted)) {
      out.push(`Busiest day: ${busiest.day} (${busiest.added + busiest.edited + busiest.deleted} objects).`);
    }
    const touched = (w, cls) => ['added', 'edited', 'deleted']
      .reduce((n, a) => n + (w ? this.count(w, a, cls) : 0), 0);
    const top = CLASSES.map((cls) => ({ cls, n: touched(cur, cls) }))
      .sort((a, b) => b.n - a.n)[0];
    if (top && top.n) out.push(`Most attention: ${LABELS[top.cls]} (${top.n}).`);
    const c = this.cov[this.cov.length - 1], p = this.cov[this.cov.length - 2];
    if (c && p) {
      if (c.c0 !== p.c0) out.push(`Uncited events ${p.c0} → ${c.c0}.`);
      if (c.c2 > p.c2) out.push(`${c.c2 - p.c2} more event${c.c2 - p.c2 === 1 ? '' : 's'} reached 2+ citations.`);
    }
    const t = this.totals[this.totals.length - 1], tp = this.totals[this.totals.length - 2];
    if (t && tp) {
      const sum = (x) => Object.values(x.counts).reduce((a, b) => a + b, 0);
      const d = sum(t) - sum(tp);
      if (d) out.push(`Database ${d > 0 ? 'grew' : 'shrank'} by ${Math.abs(d)} objects net.`);
    }
    return out.length ? html`<ul class="insights">${out.map((s) => html`<li>${s}</li>`)}</ul>` : nothing;
  }

  async interpret() {
    this.interpBusy = true;
    this.requestUpdate();
    try {
      const r = await post('/activity/api/interpret', {});
      this.interp = r.text;
    } catch (e) {
      this.interp = `Failed: ${e.message}`;
    } finally {
      this.interpBusy = false;
      this.requestUpdate();
    }
  }

  weekView() {
    const tw = this.thisWeek;
    if (!tw) return html`<p class="hint">No data.</p>`;
    const W = this.weeks;
    const cur = W.find((w) => w.week === tw.week);
    const prevIso = (() => {
      const d = new Date(`${tw.week}T00:00:00`);
      d.setDate(d.getDate() - 7);
      return isoDate(d);
    })();
    const prev = W.find((w) => w.week === prevIso);
    const delta = (n, p) => {
      const d = n - p;
      return html`<div class="delta">${d > 0 ? '+' : ''}${d} vs last week</div>`;
    };
    const card = (action) => {
      const n = this.wTotal(cur, action), p = this.wTotal(prev, action);
      return html`<div class="stat"><div class="value">${n}</div>
        <div class="label">${action}</div>${delta(n, p)}</div>`;
    };
    const c = this.cov[this.cov.length - 1], p = this.cov[this.cov.length - 2];
    return html`
      <h2>${weekLabel(tw.week)}, ${tw.week.slice(0, 4)}
        <span class="hint">vs ${weekLabel(prevIso)}</span></h2>
      <div class="stats">
        ${card('added')}${card('edited')}${card('deleted')}
        ${c ? html`<div class="stat"><div class="value">${c.c0}</div>
          <div class="label">uncited events</div>${p ? delta(c.c0, p.c0) : nothing}</div>` : nothing}
      </div>
      ${this.insights(tw, cur, prev)}
      ${this.llm ? html`<div class="interpwrap">
        ${this.interp
          ? html`<p class="interp">${this.interp}</p>`
          : html`<button ?disabled=${this.interpBusy} @click=${() => this.interpret()}>
              ${this.interpBusy ? 'Interpreting…' : 'Interpret this week'}</button>`}
      </div>` : nothing}
      ${this.dayChart(tw)}
      ${this.classCompare(cur, prev)}`;
  }

  render() {
    if (!this.weeks) return html`<h1>Activity</h1><div class="hint">Loading…</div>`;
    const viewtab = (v, label) => html`<button class="chip ${this.view === v ? 'active' : ''}"
      @click=${() => (this.view = v)}>${label}</button>`;
    const chip = (a, label) => html`<button class="chip ${this.action === a ? 'active' : ''}"
      @click=${() => (this.action = a)}>${label}</button>`;
    return html`
      <div class="pagehead">
        <h1>Activity</h1>
        <span class="spacer"></span>
        <button @click=${() => this.load(true)}>Refresh</button>
      </div>
      <div class="toolbar">
        ${viewtab('dash', 'Dashboard')}${viewtab('cov', 'Event citations')}${viewtab('db', 'Database')}${viewtab('week', 'This week')}
      </div>
      ${this.view === 'week' ? this.weekView()
        : this.view === 'db' ? this.sparkGrid()
        : this.view === 'cov' ? this.covChart()
        : html`
        <div class="toolbar">
          ${chip('added', 'Added')}${chip('edited', 'Edited')}${chip('deleted', 'Deleted')}
        </div>
        ${this.stats()}
        ${this.chart()}
        <div class="legend">
          ${CLASSES.map((c) => html`<button class="legitem ${this.hidden.has(c) ? 'off' : ''}"
            @click=${() => this.toggleClass(c)}>
            <span class="dot c-${c.toLowerCase()}"></span>${LABELS[c]}</button>`)}
        </div>`}
      ${this.tooltip()}`;
  }
}
customElements.define('activity-page', ActivityPage);
