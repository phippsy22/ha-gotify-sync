/**
 * Gotify Notification Card for Home Assistant
 * A LitElement-based Lovelace card that displays Gotify notifications
 * with filtering by app, priority, and time range.
 */

const LitElement = Object.getPrototypeOf(
  customElements.get("ha-panel-lovelace")
);
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const PRIORITY_COLORS = {
  low: "var(--success-color, #4caf50)",
  medium: "var(--warning-color, #ff9800)",
  high: "var(--error-color, #f44336)",
  critical: "var(--error-color, #d32f2f)",
};

const TIME_RANGES = [
  { value: "1h", label: "1h" },
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "all", label: "All" },
];

function getPriorityLevel(priority) {
  if (priority <= 3) return "low";
  if (priority <= 6) return "medium";
  if (priority <= 8) return "high";
  return "critical";
}

function getRelativeTime(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return date.toLocaleDateString();
}

class GotifyNotificationCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _messages: { type: Array },
      _apps: { type: Object },
      _serverUrl: { type: String },
      _loading: { type: Boolean },
      _showFilters: { type: Boolean },
      _activeFilters: { type: Object },
      _expandedMessages: { type: Object },
    };
  }

  constructor() {
    super();
    this._messages = [];
    this._apps = {};
    this._serverUrl = "";
    this._loading = true;
    this._showFilters = false;
    this._activeFilters = {};
    this._expandedMessages = {};
    this._eventUnsub = null;
    this._initialized = false;
  }

  setConfig(config) {
    this.config = {
      title: "Notifications",
      max_items: 20,
      show_app_icons: true,
      compact: false,
      filters: {
        apps: [],
        min_priority: 0,
        time_range: "24h",
      },
      ...config,
    };
    this._activeFilters = { ...this.config.filters };
  }

  static getConfigElement() {
    return document.createElement("gotify-notification-card-editor");
  }

  static getStubConfig() {
    return {
      title: "Notifications",
      max_items: 20,
      show_app_icons: true,
      filters: { apps: [], min_priority: 0, time_range: "24h" },
    };
  }

  updated(changedProps) {
    super.updated?.(changedProps);
    if (changedProps.has("hass") && this.hass && !this._initialized) {
      this._initialized = true;
      this._fetchMessages();
      this._subscribeToEvents();
    }
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.hass && this._initialized) {
      // Re-attached to DOM: refresh data and re-subscribe (unsub was cleared on disconnect)
      this._fetchMessages();
      this._subscribeToEvents();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._eventUnsub) {
      this._eventUnsub();
      this._eventUnsub = null;
    }
  }

  _subscribeToEvents() {
    if (!this.hass) return;
    if (this._eventUnsub) return;
    this.hass.connection.subscribeEvents((event) => {
      // Append the new message to the top of the list
      const msg = event.data;
      if (msg && msg.id) {
        this._messages = [msg, ...this._messages].slice(
          0,
          this.config.max_items
        );
        this.requestUpdate();
      }
    }, "gotify_notification_received").then((unsub) => {
      this._eventUnsub = unsub;
    });
  }

  async _fetchMessages() {
    if (!this.hass) return;
    this._loading = true;

    try {
      const filters = {
        ...this._activeFilters,
        limit: this.config.max_items,
      };

      // Convert app names to IDs if needed
      if (
        filters.apps &&
        filters.apps.length > 0 &&
        typeof filters.apps[0] === "string"
      ) {
        const appNameToId = {};
        for (const [id, app] of Object.entries(this._apps)) {
          appNameToId[app.name] = parseInt(id);
        }
        filters.apps = filters.apps
          .map((name) => appNameToId[name])
          .filter((id) => id !== undefined);
      }

      const result = await this.hass.callWS({
        type: "gotify_notifications/get_messages",
        filters: filters,
      });

      this._messages = result.messages || [];
      this._apps = result.apps || {};
      this._serverUrl = result.server_url || "";
    } catch (err) {
      console.error("Gotify card: failed to fetch messages", err);
      this._messages = [];
    }

    this._loading = false;
  }

  _toggleFilters() {
    this._showFilters = !this._showFilters;
  }

  _toggleExpand(msgId) {
    this._expandedMessages = {
      ...this._expandedMessages,
      [msgId]: !this._expandedMessages[msgId],
    };
  }

  _onTimeRangeChange(range) {
    this._activeFilters = { ...this._activeFilters, time_range: range };
    this._fetchMessages();
  }

  _onPriorityChange(e) {
    this._activeFilters = {
      ...this._activeFilters,
      min_priority: parseInt(e.target.value),
    };
    this._fetchMessages();
  }

  _onAppToggle(appId) {
    const current = this._activeFilters.apps || [];
    const id = parseInt(appId);
    const updated = current.includes(id)
      ? current.filter((a) => a !== id)
      : [...current, id];
    this._activeFilters = { ...this._activeFilters, apps: updated };
    this._fetchMessages();
  }

  _getAppIcon(appId) {
    const app = this._apps[appId];
    if (app && app.image_url && this.config.show_app_icons) {
      return html`<img
        class="app-icon"
        src="${app.image_url}"
        alt="${app.name}"
        @error=${(e) => {
          e.target.style.display = "none";
          e.target.nextElementSibling.style.display = "flex";
        }}
      />`;
    }
    return "";
  }

  _getAppName(msg) {
    const app = this._apps[msg.appid];
    return app ? app.name : msg.app_name || `App ${msg.appid}`;
  }

  _getLetterAvatar(appId) {
    const app = this._apps[appId];
    const name = app ? app.name : `${appId}`;
    const letter = name.charAt(0).toUpperCase();
    const colors = [
      "#e91e63",
      "#9c27b0",
      "#673ab7",
      "#3f51b5",
      "#2196f3",
      "#009688",
      "#4caf50",
      "#ff9800",
    ];
    const color = colors[appId % colors.length];
    return html`<div class="letter-avatar" style="background: ${color}">
      ${letter}
    </div>`;
  }

  render() {
    return html`
      <ha-card>
        <div class="card-header">
          <span class="title">${this.config.title}</span>
          <ha-icon-button
            class="filter-toggle"
            @click=${this._toggleFilters}
          >
            <ha-icon icon="mdi:filter-variant"></ha-icon>
          </ha-icon-button>
        </div>

        ${this._showFilters ? this._renderFilters() : ""}

        <div class="card-content">
          ${this._loading
            ? html`<div class="loading">Loading...</div>`
            : this._messages.length === 0
              ? this._renderEmpty()
              : this._messages.map((msg) => this._renderMessage(msg))}
        </div>
      </ha-card>
    `;
  }

  _renderFilters() {
    return html`
      <div class="filters">
        <div class="filter-row">
          <span class="filter-label">Time:</span>
          <div class="time-buttons">
            ${TIME_RANGES.map(
              (tr) => html`
                <button
                  class="time-btn ${this._activeFilters.time_range === tr.value
                    ? "active"
                    : ""}"
                  @click=${() => this._onTimeRangeChange(tr.value)}
                >
                  ${tr.label}
                </button>
              `
            )}
          </div>
        </div>

        <div class="filter-row">
          <span class="filter-label">Min priority:</span>
          <input
            type="range"
            min="0"
            max="10"
            .value=${String(this._activeFilters.min_priority || 0)}
            @change=${this._onPriorityChange}
          />
          <span class="priority-value"
            >${this._activeFilters.min_priority || 0}</span
          >
        </div>

        ${Object.keys(this._apps).length > 0
          ? html`
              <div class="filter-row apps-filter">
                <span class="filter-label">Apps:</span>
                <div class="app-chips">
                  ${Object.entries(this._apps).map(
                    ([id, app]) => html`
                      <button
                        class="app-chip ${(
                          this._activeFilters.apps || []
                        ).includes(parseInt(id))
                          ? "active"
                          : ""}"
                        @click=${() => this._onAppToggle(id)}
                      >
                        ${app.name}
                      </button>
                    `
                  )}
                </div>
              </div>
            `
          : ""}
      </div>
    `;
  }

  _renderEmpty() {
    const timeLabel =
      this._activeFilters.time_range === "all"
        ? ""
        : ` in the last ${this._activeFilters.time_range}`;
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:bell-off-outline"></ha-icon>
        <p>No notifications${timeLabel}</p>
      </div>
    `;
  }

  _renderMessage(msg) {
    const level = getPriorityLevel(msg.priority || 0);
    const expanded = this._expandedMessages[msg.id];
    const appName = this._getAppName(msg);

    return html`
      <div
        class="notification ${this.config.compact ? "compact" : ""}"
        style="border-left-color: ${PRIORITY_COLORS[level]}"
        @click=${() => this._toggleExpand(msg.id)}
      >
        <div class="notif-header">
          <div class="notif-left">
            ${this.config.show_app_icons
              ? html`
                  <div class="icon-wrapper">
                    ${this._getAppIcon(msg.appid)}
                    ${this._getLetterAvatar(msg.appid)}
                  </div>
                `
              : ""}
            <span class="app-badge">${appName}</span>
          </div>
          <span class="timestamp">${getRelativeTime(msg.date)}</span>
        </div>

        ${msg.title
          ? html`<div class="notif-title">${msg.title}</div>`
          : ""}

        <div class="notif-body ${expanded ? "expanded" : ""}">
          ${msg.message}
        </div>

        ${expanded && msg.extras && Object.keys(msg.extras).length > 0
          ? html`
              <div class="extras">
                ${Object.entries(msg.extras).map(
                  ([key, val]) => html`
                    <div class="extra-item">
                      <span class="extra-key">${key}:</span>
                      <span class="extra-value"
                        >${JSON.stringify(val)}</span
                      >
                    </div>
                  `
                )}
              </div>
            `
          : ""}
      </div>
    `;
  }

  static get styles() {
    return css`
      :host {
        --gotify-spacing: 12px;
        --gotify-radius: 8px;
      }

      ha-card {
        overflow: hidden;
      }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 16px 0;
      }

      .title {
        font-size: 1.1em;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .filter-toggle {
        --mdc-icon-button-size: 36px;
        color: var(--secondary-text-color);
      }

      .filters {
        padding: 8px 16px;
        border-bottom: 1px solid var(--divider-color);
      }

      .filter-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }

      .filter-label {
        font-size: 0.85em;
        color: var(--secondary-text-color);
        min-width: 80px;
      }

      .time-buttons {
        display: flex;
        gap: 4px;
      }

      .time-btn {
        border: 1px solid var(--divider-color);
        background: transparent;
        color: var(--primary-text-color);
        padding: 4px 10px;
        border-radius: 14px;
        cursor: pointer;
        font-size: 0.8em;
      }

      .time-btn.active {
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
        border-color: var(--primary-color);
      }

      input[type="range"] {
        flex: 1;
        max-width: 150px;
      }

      .priority-value {
        font-size: 0.85em;
        color: var(--secondary-text-color);
        min-width: 20px;
      }

      .app-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }

      .app-chip {
        border: 1px solid var(--divider-color);
        background: transparent;
        color: var(--primary-text-color);
        padding: 3px 10px;
        border-radius: 14px;
        cursor: pointer;
        font-size: 0.8em;
      }

      .app-chip.active {
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
        border-color: var(--primary-color);
      }

      .card-content {
        padding: 8px 16px 16px;
        max-height: 500px;
        overflow-y: auto;
      }

      .loading,
      .empty-state {
        text-align: center;
        padding: 24px;
        color: var(--secondary-text-color);
      }

      .empty-state ha-icon {
        --mdc-icon-size: 48px;
        margin-bottom: 8px;
        display: block;
      }

      .notification {
        border-left: 3px solid var(--divider-color);
        padding: 10px var(--gotify-spacing);
        margin-bottom: 8px;
        border-radius: 0 var(--gotify-radius) var(--gotify-radius) 0;
        background: var(--card-background-color, var(--ha-card-background));
        cursor: pointer;
        transition: background 0.2s;
      }

      .notification:hover {
        background: var(--secondary-background-color);
      }

      .notification.compact {
        padding: 6px 8px;
        margin-bottom: 4px;
      }

      .notif-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
      }

      .notif-left {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .icon-wrapper {
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .app-icon {
        width: 24px;
        height: 24px;
        border-radius: 4px;
        object-fit: cover;
      }

      .letter-avatar {
        width: 24px;
        height: 24px;
        border-radius: 4px;
        color: white;
        font-size: 12px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .app-badge {
        font-size: 0.75em;
        padding: 2px 8px;
        border-radius: 10px;
        background: var(--primary-color);
        color: var(--text-primary-color, #fff);
        font-weight: 500;
      }

      .timestamp {
        font-size: 0.75em;
        color: var(--secondary-text-color);
        white-space: nowrap;
      }

      .notif-title {
        font-weight: 600;
        font-size: 0.9em;
        margin-bottom: 2px;
        color: var(--primary-text-color);
      }

      .notif-body {
        font-size: 0.85em;
        color: var(--secondary-text-color);
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .notif-body.expanded {
        -webkit-line-clamp: unset;
        overflow: visible;
      }

      .extras {
        margin-top: 8px;
        padding: 8px;
        background: var(--secondary-background-color);
        border-radius: var(--gotify-radius);
        font-size: 0.8em;
      }

      .extra-item {
        margin-bottom: 2px;
      }

      .extra-key {
        color: var(--secondary-text-color);
        font-family: monospace;
      }

      .extra-value {
        color: var(--primary-text-color);
        font-family: monospace;
      }
    `;
  }
}

customElements.define("gotify-notification-card", GotifyNotificationCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "gotify-notification-card",
  name: "Gotify Notification Card",
  description:
    "Display Gotify notifications with filtering by app, priority, and time range",
  preview: true,
});
