import { BifrostElement, html, nothing, api, post, btn, spinner, statusLine,
         iconYes, iconNo } from './core.js';
import { applySeed, cacheSeed } from './theme.js';

class ConfigPage extends BifrostElement {
  static properties = {
    status: { state: true },
    busy: { state: true },
    error: { state: true },
    seed: { state: true },
    savedSeed: { state: true },
    defaultSeed: { state: true },
    savingTheme: { state: true },
    themeResult: { state: true },
  };

  constructor() {
    super();
    this.status = null;
    this.busy = false;
    this.error = '';
    this.seed = '';
    this.savedSeed = '';
    this.defaultSeed = '';
    this.savingTheme = false;
    this.themeResult = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    this.busy = true;
    this.error = '';
    try {
      const [status, theme] = await Promise.all([
        api('/config/api/status'),
        api('/config/api/theme'),
      ]);
      this.status = status;
      this.seed = theme.seed;
      this.savedSeed = theme.seed;
      this.defaultSeed = theme.default;
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
  }

  previewSeed(seed) {
    this.seed = seed;
    this.themeResult = null;
    applySeed(seed, this.defaultSeed);
  }

  async saveSeed() {
    this.savingTheme = true;
    this.themeResult = null;
    try {
      const r = await post('/config/api/theme', { seed: this.seed });
      this.savedSeed = r.seed;
      this.seed = r.seed;
      this.defaultSeed = r.default;
      cacheSeed(r.seed, r.default);
      await applySeed(r.seed, r.default);
      this.themeResult = { kind: 'ok', body: 'Saved' };
    } catch (e) {
      this.themeResult = { kind: 'error', body: e.message };
    } finally {
      this.savingTheme = false;
    }
  }

  renderTheme() {
    const seed = this.seed || this.defaultSeed;
    return html`
      <h6 class="small">Color scheme</h6>
      <nav class="wrap left-align">
        <input type="color" class="seed-input" .value=${seed}
          @input=${(e) => this.previewSeed(e.target.value)}>
        <span class="mono">${seed}</span>
        ${btn(this.savingTheme ? 'Saving...' : 'Save',
          this.savingTheme || seed === this.savedSeed, () => this.saveSeed())}
        ${btn('Reset to default', this.savingTheme || seed === this.defaultSeed,
          () => this.previewSeed(this.defaultSeed), 'border')}
        ${this.savingTheme ? spinner : nothing}
        ${this.themeResult ? statusLine(this.themeResult.kind, this.themeResult.body) : nothing}
      </nav>`;
  }

  render() {
    if (!this.status) {
      return html`<p>${this.error ? statusLine('error', this.error) : spinner}</p>`;
    }
    const s = this.status;
    return html`
      <h6 class="small">Connected services</h6>
      <div class="scroll capped-width">
        <table>
          <tbody>
            ${s.services.map((svc) => html`<tr>
              <td>${svc.ok ? iconYes : iconNo}</td>
              <td>${svc.name}</td>
              <td class="${svc.ok ? 'secondary-text' : 'error-text'}">${svc.detail}</td>
            </tr>`)}
          </tbody>
        </table>
      </div>
      <div class="space"></div>
      <nav class="wrap">
        ${btn(this.busy ? 'Checking...' : 'Re-check', this.busy, () => this.load(), 'border')}
        ${this.busy ? spinner : nothing}
        ${this.error ? statusLine('error', this.error) : nothing}
      </nav>
      <div class="large-space"></div>
      ${this.renderTheme()}
      <div class="large-space"></div>
      <h6 class="small">This instance</h6>
      <table class="capped-width">
        <tbody>
          <tr><td>Version</td><td class="mono small-text">${s.version}</td></tr>
          <tr><td>Config file</td><td class="mono small-text">${s.config_path}</td></tr>
          <tr><td>Database</td><td class="mono small-text">${s.database}</td></tr>
        </tbody>
      </table>`;
  }
}
customElements.define('config-page', ConfigPage);
