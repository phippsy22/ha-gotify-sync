# Gotify Notifications for Home Assistant

A custom Home Assistant integration that streams notifications from a [Gotify](https://gotify.net/) server in real-time via WebSocket, with REST fallback for reliability. Includes a custom Lovelace card for viewing and filtering notifications.

[![HACS Validation](https://github.com/phippsy22/ha-gotify-sync/actions/workflows/validate.yaml/badge.svg)](https://github.com/phippsy22/ha-gotify-sync/actions/workflows/validate.yaml)

## Features

- **Real-time streaming** — WebSocket connection to Gotify for instant notification delivery
- **Automatic reconnection** — exponential backoff with REST catch-up for missed messages
- **Persistent storage** — notifications survive HA restarts
- **Custom Lovelace card** — filter by app, priority, and time range
- **HA events** — every notification fires `gotify_notification_received` for use in automations
- **Multi-server support** — connect to multiple Gotify instances

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/phippsy22/ha-gotify-sync` with category **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

1. Copy `custom_components/gotify_notifications/` to your HA `custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Integrations → Add Integration**
2. Search for **Gotify Notifications**
3. Enter your Gotify server URL and a **client token** (starts with `C`)
4. The Lovelace card is registered automatically

### Getting a Gotify Client Token

1. Log into your Gotify web UI
2. Go to **Clients** and click **Create Client**
3. Copy the generated token (it starts with `C`)

## Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.gotify_notifications` | Sensor | Total notification count with message data in attributes |
| `sensor.gotify_<app_name>` | Sensor | Per-app notification count (one per Gotify application) |
| `binary_sensor.gotify_connection` | Binary Sensor | WebSocket connection health (`on` = connected) |

## Lovelace Card

The card is auto-registered when the integration loads (storage-mode dashboards). Add it to any view:

```yaml
type: custom:gotify-notification-card
title: Notifications
max_items: 20
show_app_icons: true
filters:
  apps: []            # empty = all apps, or ["Backup", "Uptime Kuma"]
  min_priority: 0     # 0-10, show messages with priority >= this value
  time_range: "24h"   # "1h", "24h", "7d", "30d", "all"
compact: false        # compact mode for smaller panels
```

### YAML-Mode Dashboards

If your Lovelace is in YAML mode, manually add the resource:

```yaml
resources:
  - url: /gotify-notification-card/gotify-notification-card.js
    type: module
```

### Priority Colors

| Priority | Color | Level |
|---|---|---|
| 0–3 | Green | Low |
| 4–6 | Yellow | Medium |
| 7–8 | Orange | High |
| 9–10 | Red | Critical |

## Automations

Every incoming notification fires a `gotify_notification_received` event:

```yaml
automation:
  - alias: "Alert on critical Gotify notification"
    trigger:
      - platform: event
        event_type: gotify_notification_received
        event_data:
          priority: 9
    action:
      - service: notify.mobile_app
        data:
          title: "{{ trigger.event.data.title }}"
          message: "{{ trigger.event.data.message }}"
```

You can filter on any field: `app_name`, `priority`, `appid`, `title`, etc.

## Options

After setup, click **Configure** on the integration to adjust:

| Option | Default | Description |
|---|---|---|
| Max stored messages | 500 | Total messages kept in memory (50–2000) |
| Max sensor messages | 50 | Messages included in sensor attributes (10–200) |
| REST poll interval | 300s | Fallback polling interval in seconds (60–3600) |

## Development

### Local Gotify for Testing

```bash
docker compose up -d
# Creates a Gotify instance at http://localhost:8888
# Default login: admin / admin
```

Then create a client + app in the Gotify UI and send test messages:

```bash
./scripts/send_test_messages.sh <APP_TOKEN>
```

### Running Tests

```bash
pip install -r requirements_test.txt
pytest tests/ -v
```

## License

[MIT](LICENSE)
