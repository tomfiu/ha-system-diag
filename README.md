# HA Performance Diagnostics

A Home Assistant custom integration that automatically identifies the root cause of slowdowns by surfacing CPU hogs, noisy entities, oversized databases, and runaway automations — all from a single dashboard card.

## Features

- **Zero-config setup** — install and go with sensible defaults
- **16 diagnostic sensors** covering CPU, RAM, database, entity activity, integration timing, and more
- **Health Score** (0–100) with automatic deductions for detected issues
- **Actionable recommendations** with copy-paste YAML fixes
- **Automation anti-pattern scanner** that flags common performance pitfalls
- **Custom Lovelace card** with 3 tabs: Overview, Top Offenders, and Recommendations
- **Lightweight** — designed to not make the problem worse

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations**
3. Click the three dots menu → **Custom repositories**
4. Add this repository URL and select **Integration** as the category
5. Search for "HA Performance Diagnostics" and install
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/ha_performance_diagnostics` directory to your `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "HA Performance Diagnostics"
3. Accept defaults or adjust:
   - **Scan interval**: How often data refreshes (default: 300 seconds)
   - **Slow query threshold**: DB query time to flag as slow (default: 500ms)
   - **State change threshold**: Changes/hour to flag an entity as noisy (default: 60)
   - **DB size warning**: Database size in MB to trigger a warning (default: 1000)

## Lovelace Card

Add the custom card to your dashboard:

```yaml
type: custom:ha-performance-card
title: HA Performance
show_score: true
default_tab: overview
theme: auto
```

Or use the visual editor: **Edit Dashboard → Add Card → Custom: HA Performance Diagnostics**

### Card Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | "HA Performance" | Card title |
| `show_score` | boolean | true | Show health score badge |
| `default_tab` | string | "overview" | Default tab: `overview`, `offenders`, or `recommendations` |
| `theme` | string | "auto" | Theme: `auto`, `light`, or `dark` |

## Sensors

All sensors are prefixed `sensor.hapd_` and grouped under device "HA Performance Diagnostics".

### System

| Entity ID | Name | Unit |
|-----------|------|------|
| `sensor.hapd_cpu_load` | CPU Load | % |
| `sensor.hapd_ram_used` | RAM Used | % |
| `sensor.hapd_db_size` | DB Size | MB |
| `sensor.hapd_recorder_queue` | Recorder Queue Depth | events |

### Entity Activity

| Entity ID | Name | Unit |
|-----------|------|------|
| `sensor.hapd_top_entity_1` | Noisiest Entity #1 | changes/hr |
| `sensor.hapd_top_entity_2` | Noisiest Entity #2 | changes/hr |
| `sensor.hapd_top_entity_3` | Noisiest Entity #3 | changes/hr |
| `sensor.hapd_total_state_changes` | Total State Changes (1h) | changes |
| `sensor.hapd_entity_count` | Total Tracked Entities | entities |

### Integrations

| Entity ID | Name | Unit |
|-----------|------|------|
| `sensor.hapd_slowest_integration_1` | Slowest Integration #1 | ms |
| `sensor.hapd_slowest_integration_2` | Slowest Integration #2 | ms |
| `sensor.hapd_slowest_integration_3` | Slowest Integration #3 | ms |
| `sensor.hapd_integration_count` | Loaded Integration Count | — |

### Summary

| Entity ID | Name | Description |
|-----------|------|-------------|
| `sensor.hapd_health_score` | HA Health Score | 0–100 computed score |
| `sensor.hapd_recommendations` | Recommendations | Count of active recommendations (full list in attributes) |

## Health Score

The health score starts at 100 and deducts points for detected issues:

| Condition | Deduction |
|-----------|-----------|
| CPU load > 50% | -20 |
| CPU load > 30% | -10 |
| DB size exceeds warning threshold | -20 |
| DB size > 75% of warning threshold | -10 |
| Any entity exceeds state change threshold | -15 |
| Recorder queue > 500 events | -10 |
| Any integration > 1000ms avg update | -10 |
| Per automation anti-pattern found | -5 |

## Troubleshooting

| Issue | Behavior |
|-------|----------|
| Recorder not loaded | DB/state-change sensors show `unavailable` |
| Database file not found | `sensor.hapd_db_size` → `unavailable` |
| `psutil` not available | Falls back to `/proc/stat` parsing |
| Query takes too long (>2s) | Retains previous values, logs warning |

## License

MIT
