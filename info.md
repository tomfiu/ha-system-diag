# HA Performance Diagnostics

Automatically identify what's making your Home Assistant slow. This integration creates diagnostic sensors that monitor CPU usage, RAM, database size, entity state change frequency, integration timing, and automation anti-patterns — then surfaces actionable recommendations to fix the issues.

## What You Get

- **16 sensors** covering system health, noisy entities, slow integrations, and more
- **Health Score** (0–100) that summarizes your system's performance at a glance
- **Recommendations** with specific, copy-paste YAML fixes
- **Custom Lovelace card** with Overview, Top Offenders, and Recommendations tabs

## Quick Start

1. Install via HACS
2. Restart Home Assistant
3. Add the integration: **Settings → Devices & Services → Add Integration → HA Performance Diagnostics**
4. Add the card to your dashboard: **Edit Dashboard → Add Card → Custom: HA Performance Diagnostics**

## Sensors Created

- `sensor.hapd_cpu_load` — CPU usage percentage
- `sensor.hapd_ram_used` — RAM usage percentage
- `sensor.hapd_db_size` — Database size in MB
- `sensor.hapd_recorder_queue` — Recorder event queue depth
- `sensor.hapd_top_entity_1/2/3` — Noisiest entities by state changes per hour
- `sensor.hapd_slowest_integration_1/2/3` — Slowest integrations by update time
- `sensor.hapd_health_score` — Overall health score (0–100)
- `sensor.hapd_recommendations` — Actionable fix recommendations

Zero configuration required — install and go!
