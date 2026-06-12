import { BifrostElement, html, nothing, api } from './core.js';

const COLS = [
  ['Person', 'people'], ['Family', 'families'], ['Event', 'events'],
  ['Place', 'places'], ['Citation', 'citations'], ['Source', 'sources'],
  ['Note', 'notes'], ['Media', 'media'], ['Other', 'other'],
];

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

class ActivityPage extends BifrostElement {
  static properties = {
    data: { state: true },
    action: { state: true },   // added | edited | deleted
  };

  constructor() {
    super();
    this.data = null;
    this.action = 'added';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    this.data = null;
    this.data = await api('/activity/api/weekly');
  }

  render() {
    if (!this.data) return html`<h1>Activity</h1><div class="hint">Loading…</div>`;
    const chip = (a, label) => html`<button class="chip ${this.action === a ? 'active' : ''}"
      @click=${() => (this.action = a)}>${label}</button>`;
    const cell = (n) => (n ? n : '');
    let year = null;
    return html`
      <div class="pagehead">
        <h1>Activity</h1>
        <span class="spacer"></span>
        <button @click=${() => this.load()}>Refresh</button>
      </div>
      <p class="hint">Distinct objects per week from the Gramps transaction log.</p>
      <div class="toolbar">
        ${chip('added', 'Added')}${chip('edited', 'Edited')}${chip('deleted', 'Deleted')}
      </div>
      <table class="results">
        <tr><th>week</th>${COLS.map(([, label]) => html`<th>${label}</th>`)}<th>total</th></tr>
        ${this.data.weeks.map((w) => {
          const c = w.actions[this.action] || {};
          const y = w.week.slice(0, 4);
          const label = y !== year ? `${weekLabel(w.week)}, ${y}` : weekLabel(w.week);
          year = y;
          return html`<tr>
            <td class="hint">${label}</td>
            ${COLS.map(([cls]) => html`<td>${cell(c[cls])}</td>`)}
            <td><strong>${cell(c.total)}</strong></td>
          </tr>`;
        })}
      </table>`;
  }
}
customElements.define('activity-page', ActivityPage);
