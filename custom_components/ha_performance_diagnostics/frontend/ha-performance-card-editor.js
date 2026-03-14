/**
 * HA Performance Card Editor
 * Visual configuration editor for the HA Performance Diagnostics card.
 */

class HaPerformanceCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = {
      title: config.title || "HA Performance",
      show_score: config.show_score !== false,
      default_tab: config.default_tab || "overview",
      theme: config.theme || "auto",
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    if (!this.shadowRoot) return;

    this.shadowRoot.innerHTML = `
      <style>
        .editor {
          padding: 16px;
        }
        .field {
          display: flex;
          flex-direction: column;
          margin-bottom: 16px;
        }
        label {
          font-size: 0.85em;
          font-weight: 500;
          margin-bottom: 4px;
          color: var(--primary-text-color);
        }
        input[type="text"],
        select {
          padding: 8px;
          border: 1px solid var(--divider-color, #ccc);
          border-radius: 4px;
          font-size: 0.9em;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color);
        }
        .checkbox-field {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 16px;
        }
        .checkbox-field label {
          margin-bottom: 0;
        }
      </style>
      <div class="editor">
        <div class="field">
          <label for="title">Card Title</label>
          <input type="text" id="title" value="${this._config.title}" />
        </div>
        <div class="checkbox-field">
          <input type="checkbox" id="show_score" ${this._config.show_score ? "checked" : ""} />
          <label for="show_score">Show Health Score</label>
        </div>
        <div class="field">
          <label for="default_tab">Default Tab</label>
          <select id="default_tab">
            <option value="overview" ${this._config.default_tab === "overview" ? "selected" : ""}>Overview</option>
            <option value="offenders" ${this._config.default_tab === "offenders" ? "selected" : ""}>Top Offenders</option>
            <option value="recommendations" ${this._config.default_tab === "recommendations" ? "selected" : ""}>Recommendations</option>
          </select>
        </div>
        <div class="field">
          <label for="theme">Theme</label>
          <select id="theme">
            <option value="auto" ${this._config.theme === "auto" ? "selected" : ""}>Auto</option>
            <option value="light" ${this._config.theme === "light" ? "selected" : ""}>Light</option>
            <option value="dark" ${this._config.theme === "dark" ? "selected" : ""}>Dark</option>
          </select>
        </div>
      </div>
    `;

    // Add event listeners
    this.shadowRoot.getElementById("title").addEventListener("input", (e) => {
      this._updateConfig("title", e.target.value);
    });
    this.shadowRoot
      .getElementById("show_score")
      .addEventListener("change", (e) => {
        this._updateConfig("show_score", e.target.checked);
      });
    this.shadowRoot
      .getElementById("default_tab")
      .addEventListener("change", (e) => {
        this._updateConfig("default_tab", e.target.value);
      });
    this.shadowRoot
      .getElementById("theme")
      .addEventListener("change", (e) => {
        this._updateConfig("theme", e.target.value);
      });
  }

  _updateConfig(key, value) {
    this._config = { ...this._config, [key]: value };
    const event = new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

customElements.define("ha-performance-card-editor", HaPerformanceCardEditor);
