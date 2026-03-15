"""Diagnostics data collection for HA Performance Diagnostics."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_DB_SIZE_WARN_MB,
    CONF_STATE_CHANGE_THRESHOLD,
    DEFAULT_DB_SIZE_WARN_MB,
    DEFAULT_STATE_CHANGE_THRESHOLD,
    HEALTH_ANTIPATTERN_DEDUCTION,
    HEALTH_CPU_HIGH,
    HEALTH_CPU_HIGH_DEDUCTION,
    HEALTH_CPU_MEDIUM,
    HEALTH_CPU_MEDIUM_DEDUCTION,
    HEALTH_DB_HIGH_DEDUCTION,
    HEALTH_DB_MEDIUM_DEDUCTION,
    HEALTH_DB_MEDIUM_FACTOR,
    HEALTH_NOISY_ENTITY_DEDUCTION,
    HEALTH_RECORDER_QUEUE_DEDUCTION,
    HEALTH_RECORDER_QUEUE_THRESHOLD,
    HEALTH_SLOW_INTEGRATION_DEDUCTION,
    HEALTH_SLOW_INTEGRATION_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

# Try to import psutil; fall back to /proc parsing
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ---------------------------------------------------------------------------
# 1. System Metrics
# ---------------------------------------------------------------------------


def _get_system_metrics_sync() -> dict[str, Any]:
    """Collect system metrics (runs in executor)."""
    if HAS_PSUTIL:
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": round(cpu_percent, 1),
            "ram_percent": round(mem.percent, 1),
            "ram_used_mb": round(mem.used / (1024 * 1024), 1),
            "ram_total_mb": round(mem.total / (1024 * 1024), 1),
        }

    # Fallback: parse /proc
    cpu_percent = _parse_proc_cpu()
    ram_info = _parse_proc_meminfo()
    return {
        "cpu_percent": cpu_percent,
        "ram_percent": ram_info.get("percent", 0),
        "ram_used_mb": ram_info.get("used_mb", 0),
        "ram_total_mb": ram_info.get("total_mb", 0),
    }


def _parse_proc_cpu() -> float:
    """Parse CPU usage from /proc/stat."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        idle = int(parts[4])
        total = sum(int(p) for p in parts[1:])
        if total == 0:
            return 0.0
        return round((1 - idle / total) * 100, 1)
    except (OSError, IndexError, ValueError):
        return 0.0


def _parse_proc_meminfo() -> dict[str, float]:
    """Parse memory info from /proc/meminfo."""
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts[0] in ("MemTotal:", "MemAvailable:", "MemFree:"):
                    info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used = total - available
        total_mb = round(total / 1024, 1)
        used_mb = round(used / 1024, 1)
        percent = round((used / total) * 100, 1) if total > 0 else 0.0
        return {"total_mb": total_mb, "used_mb": used_mb, "percent": percent}
    except (OSError, ValueError):
        return {"total_mb": 0, "used_mb": 0, "percent": 0}


async def async_get_system_metrics(hass: HomeAssistant) -> dict[str, Any]:
    """Collect system metrics."""
    return await hass.async_add_executor_job(_get_system_metrics_sync)


# ---------------------------------------------------------------------------
# 2. Top CPU Processes
# ---------------------------------------------------------------------------


def _get_top_processes_sync() -> list[dict[str, Any]]:
    """Collect top processes by CPU usage (runs in executor)."""
    if not HAS_PSUTIL:
        return []

    procs = []
    try:
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                procs.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"] or "unknown",
                        "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                        "memory_percent": round(info["memory_percent"] or 0.0, 1),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    procs.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return procs[:5]


async def async_get_top_cpu_processes(hass: HomeAssistant) -> dict[str, Any]:
    """Collect top CPU-consuming processes."""
    try:
        processes = await hass.async_add_executor_job(_get_top_processes_sync)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not collect top CPU processes")
        processes = []
    return {"processes": processes}


# ---------------------------------------------------------------------------
# 4. DB Health  (formerly 2)
# ---------------------------------------------------------------------------


def _get_db_size(db_path: str) -> float | None:
    """Get database file size in MB."""
    try:
        return round(os.path.getsize(db_path) / (1024 * 1024), 1)
    except OSError:
        return None


def _run_integrity_check(db_path: str) -> bool:
    """Run PRAGMA integrity_check on the SQLite database."""
    try:
        import sqlite3

        conn = sqlite3.connect(db_path, timeout=2)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()
        return result is not None and result[0] == "ok"
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Database integrity check failed", exc_info=True)
        return False


async def async_get_db_health(hass: HomeAssistant) -> dict[str, Any]:
    """Collect database health metrics."""
    db_path = hass.config.path("home-assistant_v2.db")
    db_size_mb = await hass.async_add_executor_job(_get_db_size, db_path)

    if db_size_mb is None:
        _LOGGER.warning("Database file not found at %s", db_path)
        return {
            "db_size_mb": None,
            "integrity_ok": None,
            "recorder_queue_size": None,
        }

    # Run integrity check with timeout
    try:
        integrity_ok = await asyncio.wait_for(
            hass.async_add_executor_job(_run_integrity_check, db_path),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        _LOGGER.warning("Database integrity check timed out")
        integrity_ok = None

    # Get recorder queue size
    recorder_queue_size = None
    try:
        from homeassistant.components.recorder import get_instance

        recorder = get_instance(hass)
        if hasattr(recorder, "backlog"):
            recorder_queue_size = recorder.backlog
        elif hasattr(recorder, "queue") and hasattr(recorder.queue, "qsize"):
            recorder_queue_size = recorder.queue.qsize()
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not get recorder queue size")

    return {
        "db_size_mb": db_size_mb,
        "integrity_ok": integrity_ok,
        "recorder_queue_size": recorder_queue_size or 0,
    }


# ---------------------------------------------------------------------------
# 3. State Change Analysis
# ---------------------------------------------------------------------------


def _query_state_changes(db_path: str) -> list[dict[str, Any]]:
    """Query state changes from the recorder database."""
    import sqlite3

    one_hour_ago = time.time() - 3600

    try:
        conn = sqlite3.connect(db_path, timeout=2)
    except sqlite3.OperationalError:
        _LOGGER.warning("Could not open database at %s", db_path)
        return [], 0

    try:
        # Try new schema with states_meta table first
        cursor = conn.execute(
            """
            SELECT sm.entity_id, COUNT(*) as change_count
            FROM states s
            INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
            WHERE s.last_updated_ts >= ?
            GROUP BY sm.entity_id
            ORDER BY change_count DESC
            LIMIT 20
            """,
            (one_hour_ago,),
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        # Fall back to old schema
        try:
            cursor = conn.execute(
                """
                SELECT entity_id, COUNT(*) as change_count
                FROM states
                WHERE last_updated_ts >= ?
                GROUP BY entity_id
                ORDER BY change_count DESC
                LIMIT 20
                """,
                (one_hour_ago,),
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            _LOGGER.warning("Could not query state changes from database")
            rows = []
    finally:
        conn.close()

    total_changes = sum(row[1] for row in rows)
    return [{"entity_id": row[0], "changes_per_hour": row[1]} for row in rows], total_changes


async def async_get_state_change_analysis(hass: HomeAssistant, threshold: int) -> dict[str, Any]:
    """Analyze state changes in the past hour."""
    db_path = hass.config.path("home-assistant_v2.db")

    try:
        result = await asyncio.wait_for(
            hass.async_add_executor_job(_query_state_changes, db_path),
            timeout=2.0,
        )
        entities, total_changes = result
    except (asyncio.TimeoutError, Exception) as err:  # noqa: BLE001
        _LOGGER.warning("State change query failed: %s", err)
        return {
            "top_entities": [],
            "total_changes": 0,
            "entity_count": 0,
            "data_window_minutes": 0,
        }

    # Enrich top entities with friendly names and domain info
    top_entities = []
    for entity_data in entities[:3]:
        entity_id = entity_data["entity_id"]
        state = hass.states.get(entity_id)
        friendly_name = entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
        integration = None

        if state:
            friendly_name = state.attributes.get("friendly_name", entity_id)

        # Try to get integration from entity registry
        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(hass)
            entry = registry.async_get(entity_id)
            if entry and entry.platform:
                integration = entry.platform
        except Exception:  # noqa: BLE001
            pass

        top_entities.append(
            {
                "entity_id": entity_id,
                "friendly_name": friendly_name,
                "changes_per_hour": entity_data["changes_per_hour"],
                "domain": domain,
                "integration": integration,
                "exceeds_threshold": entity_data["changes_per_hour"] > threshold,
            }
        )

    entity_count = len(hass.states.async_all()) if hass.states else 0

    return {
        "top_entities": top_entities,
        "total_changes": total_changes,
        "entity_count": entity_count,
        "data_window_minutes": 60,
    }


# ---------------------------------------------------------------------------
# 4. Integration Timing
# ---------------------------------------------------------------------------


async def async_get_integration_timing(hass: HomeAssistant) -> dict[str, Any]:
    """Collect integration setup/update timing data."""
    setup_times: dict[str, float] = {}

    # Try to get setup times from hass.data
    for key in ("setup_times", "setup_time"):
        if key in hass.data and isinstance(hass.data[key], dict):
            setup_times = hass.data[key]
            break

    # Also check for integration setup durations
    if not setup_times and "integrations" in hass.data:
        integrations = hass.data["integrations"]
        if isinstance(integrations, dict):
            for name, data in integrations.items():
                if isinstance(data, dict) and "setup_duration" in data:
                    setup_times[name] = data["setup_duration"]

    # Count loaded integrations
    integration_count = 0
    try:
        config_entries = hass.config_entries.async_entries()
        domains = {entry.domain for entry in config_entries}
        integration_count = len(domains)
    except Exception:  # noqa: BLE001
        integration_count = len(setup_times)

    # Sort by duration and take top 3
    sorted_integrations = sorted(setup_times.items(), key=lambda x: x[1], reverse=True)[:3]

    # Get entity counts per integration
    try:
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(hass)
        all_entities = registry.entities
    except Exception:  # noqa: BLE001
        all_entities = {}

    slowest = []
    for integration_name, duration_ms in sorted_integrations:
        entity_count = 0
        try:
            entity_count = sum(
                1
                for entity in all_entities.values()
                if hasattr(entity, "platform") and entity.platform == integration_name
            )
        except Exception:  # noqa: BLE001
            pass

        slowest.append(
            {
                "integration": integration_name,
                "avg_update_ms": round(duration_ms * 1000, 1)
                if duration_ms < 100
                else round(duration_ms, 1),
                "last_error": None,
                "entity_count": entity_count,
            }
        )

    return {
        "slowest": slowest,
        "integration_count": integration_count or len(setup_times),
    }


# ---------------------------------------------------------------------------
# 5. Automation Anti-Pattern Scanner
# ---------------------------------------------------------------------------


async def async_scan_automation_antipatterns(
    hass: HomeAssistant,
    top_entities: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Scan automations for known anti-patterns."""
    antipatterns: list[dict[str, Any]] = []
    top_entity_ids = set()
    if top_entities:
        top_entity_ids = {e["entity_id"] for e in top_entities if e.get("exceeds_threshold")}

    automation_states = hass.states.async_all("automation")

    for auto_state in automation_states:
        auto_id = auto_state.entity_id
        auto_attrs = auto_state.attributes

        # Try to get automation config
        config = None
        if "automation_config" in hass.data:
            configs = hass.data["automation_config"]
            if isinstance(configs, dict):
                config = configs.get(auto_id)
            elif isinstance(configs, list):
                for cfg in configs:
                    if isinstance(cfg, dict) and cfg.get("id") == auto_attrs.get("id"):
                        config = cfg
                        break

        if config is None:
            continue

        triggers = config.get("trigger", config.get("triggers", []))
        if not isinstance(triggers, list):
            triggers = [triggers]

        conditions = config.get("condition", config.get("conditions", []))
        if not isinstance(conditions, list):
            conditions = [conditions] if conditions else []

        actions = config.get("action", config.get("actions", []))
        if not isinstance(actions, list):
            actions = [actions] if actions else []

        friendly_name = auto_attrs.get("friendly_name", auto_id)

        # Pattern 1: No conditions + state trigger on high-frequency entity
        if not conditions:
            for trigger in triggers:
                if not isinstance(trigger, dict):
                    continue
                trigger_platform = trigger.get("platform", trigger.get("trigger", ""))
                trigger_entity = trigger.get("entity_id", "")
                if trigger_platform == "state" and trigger_entity in top_entity_ids:
                    antipatterns.append(
                        {
                            "pattern": "noisy_trigger_no_condition",
                            "automation_id": auto_id,
                            "severity": "warning",
                            "description": (
                                f"'{friendly_name}' triggers on state changes of "
                                f"'{trigger_entity}' without conditions. "
                                f"This entity has high state change frequency."
                            ),
                            "recommendation": (
                                "Add conditions to filter unnecessary triggers, "
                                "or reduce the entity's polling interval."
                            ),
                        }
                    )

        # Pattern 2: Automation chains (action triggers another automation)
        for action in actions:
            if not isinstance(action, dict):
                continue
            service = action.get("service", action.get("action", ""))
            if service in ("automation.trigger", "automation.turn_on"):
                target = action.get("target", {})
                target_entity = action.get("entity_id", "")
                if isinstance(target, dict):
                    target_entity = target.get("entity_id", target_entity)
                antipatterns.append(
                    {
                        "pattern": "automation_chain",
                        "automation_id": auto_id,
                        "severity": "info",
                        "description": (
                            f"'{friendly_name}' triggers another automation "
                            f"'{target_entity}'. Chained automations can be "
                            f"hard to debug and may cause cascading issues."
                        ),
                        "recommendation": (
                            "Consider combining the automations into a single "
                            "automation with multiple actions."
                        ),
                    }
                )

        # Pattern 3: HA start trigger with long action sequences
        for trigger in triggers:
            if not isinstance(trigger, dict):
                continue
            trigger_platform = trigger.get("platform", trigger.get("trigger", ""))
            event_type = trigger.get("event_type", trigger.get("event", ""))
            if trigger_platform == "homeassistant" or (
                trigger_platform == "event" and event_type == "homeassistant_start"
            ):
                if len(actions) > 5:
                    antipatterns.append(
                        {
                            "pattern": "startup_overload",
                            "automation_id": auto_id,
                            "severity": "info",
                            "description": (
                                f"'{friendly_name}' runs {len(actions)} actions "
                                f"at HA startup. This may delay startup completion."
                            ),
                            "recommendation": (
                                "Split into smaller automations or add delays "
                                "between action groups to reduce startup load."
                            ),
                        }
                    )
                break

    return antipatterns


# ---------------------------------------------------------------------------
# 6. Health Score
# ---------------------------------------------------------------------------


def calculate_health_score(
    data: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> int:
    """Calculate the health score (0-100)."""
    config = config or {}
    db_size_warn = config.get(CONF_DB_SIZE_WARN_MB, DEFAULT_DB_SIZE_WARN_MB)
    state_change_threshold = config.get(CONF_STATE_CHANGE_THRESHOLD, DEFAULT_STATE_CHANGE_THRESHOLD)

    score = 100

    # CPU deductions
    system = data.get("system", {})
    cpu = system.get("cpu_percent", 0)
    if cpu > HEALTH_CPU_HIGH:
        score -= HEALTH_CPU_HIGH_DEDUCTION
    elif cpu > HEALTH_CPU_MEDIUM:
        score -= HEALTH_CPU_MEDIUM_DEDUCTION

    # DB size deductions
    db = data.get("db", {})
    db_size = db.get("db_size_mb")
    if db_size is not None:
        if db_size > db_size_warn:
            score -= HEALTH_DB_HIGH_DEDUCTION
        elif db_size > db_size_warn * HEALTH_DB_MEDIUM_FACTOR:
            score -= HEALTH_DB_MEDIUM_DEDUCTION

    # Noisy entity deduction
    state_changes = data.get("state_changes", {})
    top_entities = state_changes.get("top_entities", [])
    if any(e.get("changes_per_hour", 0) > state_change_threshold for e in top_entities):
        score -= HEALTH_NOISY_ENTITY_DEDUCTION

    # Recorder queue deduction
    queue_size = db.get("recorder_queue_size", 0) or 0
    if queue_size > HEALTH_RECORDER_QUEUE_THRESHOLD:
        score -= HEALTH_RECORDER_QUEUE_DEDUCTION

    # Slow integration deduction
    integrations = data.get("integrations", {})
    slowest = integrations.get("slowest", [])
    if any(i.get("avg_update_ms", 0) > HEALTH_SLOW_INTEGRATION_THRESHOLD for i in slowest):
        score -= HEALTH_SLOW_INTEGRATION_DEDUCTION

    # Antipattern deductions
    antipatterns = data.get("antipatterns", [])
    score -= HEALTH_ANTIPATTERN_DEDUCTION * len(antipatterns)

    return max(0, score)


# ---------------------------------------------------------------------------
# 7. Recommendations
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def generate_recommendations(
    data: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate actionable recommendations based on diagnostic data."""
    config = config or {}
    db_size_warn = config.get(CONF_DB_SIZE_WARN_MB, DEFAULT_DB_SIZE_WARN_MB)
    state_change_threshold = config.get(CONF_STATE_CHANGE_THRESHOLD, DEFAULT_STATE_CHANGE_THRESHOLD)

    recommendations: list[dict[str, Any]] = []

    # DB size recommendations
    db = data.get("db", {})
    db_size = db.get("db_size_mb")
    if db_size is not None:
        if db_size > db_size_warn:
            recommendations.append(
                {
                    "id": "db_size_critical",
                    "severity": "error",
                    "title": f"Database size is {db_size:.0f} MB",
                    "detail": (
                        f"The database is {db_size:.0f} MB, exceeding the "
                        f"{db_size_warn} MB warning threshold."
                    ),
                    "fix": (
                        "Run a recorder purge and reduce purge_keep_days in "
                        "configuration.yaml:\n"
                        "recorder:\n"
                        "  purge_keep_days: 5"
                    ),
                }
            )
        elif db_size > db_size_warn * HEALTH_DB_MEDIUM_FACTOR:
            recommendations.append(
                {
                    "id": "db_size_warning",
                    "severity": "warning",
                    "title": f"Database size approaching limit ({db_size:.0f} MB)",
                    "detail": (
                        f"The database is {db_size:.0f} MB, approaching the "
                        f"{db_size_warn} MB warning threshold."
                    ),
                    "fix": (
                        "Consider reducing purge_keep_days or excluding "
                        "high-frequency entities from the recorder."
                    ),
                }
            )

    # Integrity check
    if db.get("integrity_ok") is False:
        recommendations.append(
            {
                "id": "db_integrity",
                "severity": "error",
                "title": "Database integrity check failed",
                "detail": "The SQLite database failed its integrity check.",
                "fix": (
                    "Back up your database, then consider running a repair or "
                    "starting fresh with a new database."
                ),
            }
        )

    # Recorder queue
    queue_size = db.get("recorder_queue_size", 0) or 0
    if queue_size > HEALTH_RECORDER_QUEUE_THRESHOLD:
        recommendations.append(
            {
                "id": "recorder_queue",
                "severity": "warning",
                "title": f"Recorder queue backlog: {queue_size} events",
                "detail": (
                    f"The recorder has {queue_size} events queued, indicating "
                    f"it cannot keep up with state changes."
                ),
                "fix": (
                    "Exclude noisy entities from the recorder or increase "
                    "commit_interval:\n"
                    "recorder:\n"
                    "  commit_interval: 2"
                ),
            }
        )

    # CPU
    system = data.get("system", {})
    cpu = system.get("cpu_percent", 0)
    if cpu > HEALTH_CPU_HIGH:
        recommendations.append(
            {
                "id": "cpu_high",
                "severity": "warning",
                "title": f"High CPU usage: {cpu}%",
                "detail": f"CPU load is at {cpu}%, which may cause slowdowns.",
                "fix": (
                    "Check for runaway integrations or automations. Consider "
                    "reducing polling intervals for resource-intensive integrations."
                ),
            }
        )

    # Noisy entities
    state_changes = data.get("state_changes", {})
    for entity in state_changes.get("top_entities", []):
        if entity.get("changes_per_hour", 0) > state_change_threshold:
            recommendations.append(
                {
                    "id": "noisy_entity",
                    "severity": "warning",
                    "title": "Entity firing too frequently",
                    "detail": (
                        f"{entity['entity_id']} changed "
                        f"{entity['changes_per_hour']} times in the last hour."
                    ),
                    "fix": (
                        "Add this entity to recorder exclude list, or reduce "
                        "polling interval:\n"
                        "recorder:\n"
                        "  exclude:\n"
                        "    entities:\n"
                        f"      - {entity['entity_id']}"
                    ),
                }
            )

    # Slow integrations
    integrations = data.get("integrations", {})
    for integration in integrations.get("slowest", []):
        if integration.get("avg_update_ms", 0) > HEALTH_SLOW_INTEGRATION_THRESHOLD:
            recommendations.append(
                {
                    "id": "slow_integration",
                    "severity": "warning",
                    "title": (
                        f"Slow integration: {integration['integration']} "
                        f"({integration['avg_update_ms']}ms)"
                    ),
                    "detail": (
                        f"The {integration['integration']} integration takes "
                        f"{integration['avg_update_ms']}ms on average."
                    ),
                    "fix": (
                        "Check for network issues or consider increasing the "
                        "integration's scan interval."
                    ),
                }
            )

    # Antipatterns
    for antipattern in data.get("antipatterns", []):
        recommendations.append(
            {
                "id": f"antipattern_{antipattern['pattern']}",
                "severity": antipattern.get("severity", "info"),
                "title": antipattern["description"].split(".")[0],
                "detail": antipattern["description"],
                "fix": antipattern.get("recommendation", ""),
            }
        )

    # Integration count info
    integration_count = integrations.get("integration_count", 0)
    if integration_count > 15:
        recommendations.append(
            {
                "id": "many_integrations",
                "severity": "info",
                "title": f"{integration_count} integrations loaded",
                "detail": (
                    f"You have {integration_count} integrations loaded. "
                    f"Each adds overhead to your system."
                ),
                "fix": ("Review your integrations and disable any that are not actively used."),
            }
        )

    # Sort by severity
    recommendations.sort(key=lambda r: _SEVERITY_ORDER.get(r["severity"], 99))

    return recommendations
