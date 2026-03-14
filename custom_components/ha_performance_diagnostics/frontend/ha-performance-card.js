/**
 * HA Performance Diagnostics Card
 * Custom Lovelace card for Home Assistant performance monitoring.
 */

const SENSOR_IDS = {
  cpuLoad: "sensor.hapd_cpu_load",
  ramUsed: "sensor.hapd_ram_used",
  dbSize: "sensor.hapd_db_size",
  recorderQueue: "sensor.hapd_recorder_queue",
  topEntity1: "sensor.hapd_top_entity_1",
  topEntity2: "sensor.hapd_top_entity_2",
  topEntity3: "sensor.hapd_top_entity_3",
  totalStateChanges: "sensor.hapd_total_state_changes",
  entityCount: "sensor.hapd_entity_count",
  slowestIntegration1: "sensor.hapd_slowest_integration_1",
  slowestIntegration2: "sensor.hapd_slowest_integration_2",
  slowestIntegration3: "sensor.hapd_slowest_integration_3",
  integrationCount: "sensor.hapd_integration_count",
  healthScore: "sensor.hapd_health_score",
  recommendations: "sensor.hapd_recommendations",
};

class HaPerformanceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._activeTab = "overview";
  }

  static getConfigElement() {
    return document.createElement("ha-performance-card-editor");
  }

  static getStubConfig() {
    return {
      title: "HA Performance",
      show_score: true,
      default_tab: "overview",
      theme: "auto",
    };
  }

  setConfig(config) {
    this._config = {
      title: config.title || "HA Performance",
      show_score: config.show_score !== false,
      default_tab: config.default_tab || "overview",
      theme: config.theme || "auto",
    };
    this._activeTab = this._config.default_tab;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _getState(sensorId) {
    if (!this._hass || !this._hass.states[sensorId]) return null;
    return this._hass.states[sensorId];
  }

  _getVal(sensorId) {
    const state = this._getState(sensorId);
    if (!state || state.state === "unavailable" || state.state === "unknown")
      return null;
    return state.state;
  }

  _getStatusIcon(value, warnThreshold, critThreshold) {
    const num = parseFloat(value);
    if (isNaN(num)) return { icon: "\u2753", cls: "unknown" };
    if (num >= critThreshold) return { icon: "\uD83D\uDD34", cls: "critical" };
    if (num >= warnThreshold) return { icon: "\uD83D\uDFE1", cls: "warn" };
    return { icon: "\uD83D\uDFE2", cls: "ok" };
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;

    const healthScore = this._getVal(SENSOR_IDS.healthScore);
    const recCount = this._getVal(SENSOR_IDS.recommendations);

    this.shadowRoot.innerHTML = `
      <style>${this._getStyles()}</style>
      <ha-card>
        <div class="card-header">
          <span class="title">${this._config.title}</span>
          ${
            this._config.show_score && healthScore !== null
              ? `<span class="health-badge ${this._getScoreClass(healthScore)}">
                   ${healthScore} / 100
                   ${recCount && parseInt(recCount) > 0 ? `&nbsp;&bull;&nbsp;${recCount} issue${parseInt(recCount) !== 1 ? "s" : ""}` : ""}
                 </span>`
              : ""
          }
        </div>
        <div class="tabs">
          <button class="tab ${this._activeTab === "overview" ? "active" : ""}" data-tab="overview">Overview</button>
          <button class="tab ${this._activeTab === "offenders" ? "active" : ""}" data-tab="offenders">Top Offenders</button>
          <button class="tab ${this._activeTab === "recommendations" ? "active" : ""}" data-tab="recommendations">Recommendations</button>
        </div>
        <div class="tab-content">
          ${this._renderActiveTab()}
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        this._activeTab = e.target.dataset.tab;
        this._render();
      });
    });

    // Copy fix button handlers
    this.shadowRoot.querySelectorAll(".copy-fix-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const fix = e.target.dataset.fix;
        if (fix) {
          navigator.clipboard.writeText(fix).then(() => {
            e.target.textContent = "Copied!";
            setTimeout(() => (e.target.textContent = "Copy Fix"), 1500);
          });
        }
      });
    });
  }

  _getScoreClass(score) {
    const s = parseInt(score);
    if (s >= 80) return "score-good";
    if (s >= 50) return "score-warn";
    return "score-critical";
  }

  _renderActiveTab() {
    switch (this._activeTab) {
      case "overview":
        return this._renderOverview();
      case "offenders":
        return this._renderOffenders();
      case "recommendations":
        return this._renderRecommendations();
      default:
        return this._renderOverview();
    }
  }

  _renderOverview() {
    const cpu = this._getVal(SENSOR_IDS.cpuLoad);
    const ram = this._getVal(SENSOR_IDS.ramUsed);
    const db = this._getVal(SENSOR_IDS.dbSize);
    const queue = this._getVal(SENSOR_IDS.recorderQueue);

    const cpuStatus = this._getStatusIcon(cpu, 30, 50);
    const ramStatus = this._getStatusIcon(ram, 70, 90);
    const dbStatus = this._getStatusIcon(db, 750, 1000);
    const queueStatus = this._getStatusIcon(queue, 200, 500);

    return `
      <div class="metrics-grid">
        <div class="metric-card ${cpuStatus.cls}">
          <div class="metric-label">CPU</div>
          <div class="metric-value">${cpu !== null ? cpu + "%" : "N/A"}</div>
          <div class="metric-status">${cpuStatus.icon}</div>
        </div>
        <div class="metric-card ${ramStatus.cls}">
          <div class="metric-label">RAM</div>
          <div class="metric-value">${ram !== null ? ram + "%" : "N/A"}</div>
          <div class="metric-status">${ramStatus.icon}</div>
        </div>
        <div class="metric-card ${dbStatus.cls}">
          <div class="metric-label">DB</div>
          <div class="metric-value">${db !== null ? db + " MB" : "N/A"}</div>
          <div class="metric-status">${dbStatus.icon}</div>
        </div>
        <div class="metric-card ${queueStatus.cls}">
          <div class="metric-label">Recorder</div>
          <div class="metric-value">${queue !== null ? queue + " queued" : "N/A"}</div>
          <div class="metric-status">${queueStatus.icon}</div>
        </div>
      </div>
    `;
  }

  _renderOffenders() {
    const entitySensors = [
      SENSOR_IDS.topEntity1,
      SENSOR_IDS.topEntity2,
      SENSOR_IDS.topEntity3,
    ];
    const integrationSensors = [
      SENSOR_IDS.slowestIntegration1,
      SENSOR_IDS.slowestIntegration2,
      SENSOR_IDS.slowestIntegration3,
    ];

    let entitiesHtml = '<div class="offender-section"><h3>Noisiest Entities</h3><div class="offender-list">';
    entitySensors.forEach((sensorId, i) => {
      const state = this._getState(sensorId);
      if (!state || state.state === "unavailable" || state.state === "unknown" || state.state === null) return;
      const attrs = state.attributes || {};
      const entityId = attrs.entity_id || "Unknown";
      const changes = state.state;
      const warn = attrs.exceeds_threshold;
      entitiesHtml += `
        <div class="offender-row">
          <span class="offender-rank">${i + 1}.</span>
          <span class="offender-name" title="${entityId}">${entityId}</span>
          <span class="offender-value">${changes}/hr</span>
          <span class="offender-icon">${warn ? "\u26A0\uFE0F" : "\u2714\uFE0F"}</span>
        </div>
      `;
    });
    entitiesHtml += "</div></div>";

    let integrationsHtml = '<div class="offender-section"><h3>Slowest Integrations</h3><div class="offender-list">';
    integrationSensors.forEach((sensorId, i) => {
      const state = this._getState(sensorId);
      if (!state || state.state === "unavailable" || state.state === "unknown" || state.state === null) return;
      const attrs = state.attributes || {};
      const name = attrs.integration || "Unknown";
      const ms = state.state;
      const warn = parseFloat(ms) > 1000;
      const mid = parseFloat(ms) > 500;
      entitiesHtml;
      integrationsHtml += `
        <div class="offender-row">
          <span class="offender-rank">${i + 1}.</span>
          <span class="offender-name">${name}</span>
          <span class="offender-value">${ms}ms</span>
          <span class="offender-icon">${warn ? "\u26A0\uFE0F" : mid ? "\uD83D\uDFE1" : "\u2714\uFE0F"}</span>
        </div>
      `;
    });
    integrationsHtml += "</div></div>";

    return `<div class="offenders-grid">${entitiesHtml}${integrationsHtml}</div>`;
  }

  _renderRecommendations() {
    const recState = this._getState(SENSOR_IDS.recommendations);
    if (!recState) return '<div class="empty">No data available</div>';

    const recommendations = recState.attributes?.recommendations || [];
    if (recommendations.length === 0) {
      return '<div class="empty good-msg">No issues found. Your system is healthy!</div>';
    }

    const severityIcons = {
      error: "\u26D4",
      warning: "\u26A0\uFE0F",
      info: "\u2139\uFE0F",
    };

    let html = '<div class="recommendations-list">';
    recommendations.forEach((rec) => {
      const icon = severityIcons[rec.severity] || "\u2139\uFE0F";
      const escapedFix = (rec.fix || "").replace(/"/g, "&quot;");
      html += `
        <div class="recommendation ${rec.severity}">
          <div class="rec-header">
            <span class="rec-icon">${icon}</span>
            <span class="rec-severity">[${rec.severity}]</span>
            <span class="rec-title">${rec.title || ""}</span>
          </div>
          <div class="rec-detail">${rec.detail || ""}</div>
          ${
            rec.fix
              ? `<div class="rec-fix">
                   <button class="copy-fix-btn" data-fix="${escapedFix}">Copy Fix</button>
                 </div>`
              : ""
          }
        </div>
      `;
    });
    html += "</div>";
    return html;
  }

  _getStyles() {
    return `
      :host {
        --hapd-ok: #4caf50;
        --hapd-warn: #ff9800;
        --hapd-critical: #f44336;
        --hapd-info: #2196f3;
      }
      ha-card {
        padding: 0;
        overflow: hidden;
      }
      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 16px 8px;
      }
      .title {
        font-size: 1.1em;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .health-badge {
        font-size: 0.85em;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 12px;
        color: white;
      }
      .score-good { background: var(--hapd-ok); }
      .score-warn { background: var(--hapd-warn); }
      .score-critical { background: var(--hapd-critical); }

      .tabs {
        display: flex;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        padding: 0 8px;
      }
      .tab {
        flex: 1;
        padding: 10px 8px;
        border: none;
        background: none;
        cursor: pointer;
        font-size: 0.85em;
        color: var(--secondary-text-color);
        border-bottom: 2px solid transparent;
        transition: all 0.2s;
      }
      .tab:hover {
        color: var(--primary-text-color);
      }
      .tab.active {
        color: var(--primary-color);
        border-bottom-color: var(--primary-color);
        font-weight: 500;
      }

      .tab-content {
        padding: 16px;
        min-height: 120px;
      }

      /* Overview tab */
      .metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr 1fr;
        gap: 12px;
      }
      .metric-card {
        text-align: center;
        padding: 12px 8px;
        border-radius: 8px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
      }
      .metric-label {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        margin-bottom: 4px;
      }
      .metric-value {
        font-size: 1.1em;
        font-weight: 600;
        color: var(--primary-text-color);
        margin-bottom: 4px;
      }
      .metric-status {
        font-size: 0.9em;
      }

      /* Offenders tab */
      .offenders-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }
      .offender-section h3 {
        font-size: 0.9em;
        font-weight: 500;
        margin: 0 0 8px 0;
        color: var(--primary-text-color);
      }
      .offender-row {
        display: flex;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        font-size: 0.85em;
      }
      .offender-row:last-child { border-bottom: none; }
      .offender-rank {
        width: 20px;
        color: var(--secondary-text-color);
      }
      .offender-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--primary-text-color);
      }
      .offender-value {
        margin: 0 8px;
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .offender-icon { font-size: 0.9em; }

      /* Recommendations tab */
      .recommendations-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .recommendation {
        padding: 12px;
        border-radius: 8px;
        border-left: 4px solid;
      }
      .recommendation.error {
        border-left-color: var(--hapd-critical);
        background: rgba(244, 67, 54, 0.05);
      }
      .recommendation.warning {
        border-left-color: var(--hapd-warn);
        background: rgba(255, 152, 0, 0.05);
      }
      .recommendation.info {
        border-left-color: var(--hapd-info);
        background: rgba(33, 150, 243, 0.05);
      }
      .rec-header {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 4px;
      }
      .rec-severity {
        font-size: 0.75em;
        font-weight: 600;
        text-transform: uppercase;
        color: var(--secondary-text-color);
      }
      .rec-title {
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .rec-detail {
        font-size: 0.85em;
        color: var(--secondary-text-color);
        margin-bottom: 6px;
      }
      .rec-fix {
        display: flex;
        justify-content: flex-end;
      }
      .copy-fix-btn {
        padding: 4px 12px;
        font-size: 0.8em;
        border: 1px solid var(--divider-color, #ccc);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        color: var(--primary-color);
        cursor: pointer;
        transition: background 0.2s;
      }
      .copy-fix-btn:hover {
        background: var(--primary-color);
        color: white;
      }

      .empty {
        text-align: center;
        padding: 24px;
        color: var(--secondary-text-color);
        font-style: italic;
      }
      .good-msg {
        color: var(--hapd-ok);
        font-style: normal;
        font-weight: 500;
      }

      @media (max-width: 500px) {
        .metrics-grid {
          grid-template-columns: 1fr 1fr;
        }
        .offenders-grid {
          grid-template-columns: 1fr;
        }
      }
    `;
  }
}

customElements.define("ha-performance-card", HaPerformanceCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ha-performance-card",
  name: "HA Performance Diagnostics",
  description: "Identify what's making your Home Assistant slow.",
});
