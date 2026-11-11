import { BifrostElement, html, nothing, api, btn, spinner, statusLine, iconYes, iconNo } from './core.js';

class ConfigPage extends BifrostElement {
  static properties = {
    status: { state: true },
    busy: { state: true },
    error: { state: true },
  };

  constructor() {
    super();
    this.status = null;
    this.busy = false;
    this.error = '';
  }

  connectedCallback() {
    super.connectedCallback();
    this.load();
  }

  async load() {
    this.busy = true;
    this.error = '';
    try {
      this.status = await api('/config/api/status');
    } catch (e) {
      this.error = e.message;
    } finally {
      this.busy = false;
    }
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
      <h6 class="small">This instance</h6>
      <table class="capped-width">
        <tbody>
          <tr><td>Version</td><td class="mono small-text">${s.version}</td></tr>
          <tr><td>Config file</td><td class="mono small-text">${s.config_path}</td></tr>
        </tbody>
      </table>`;
  }
}
customElements.define('config-page', ConfigPage);
