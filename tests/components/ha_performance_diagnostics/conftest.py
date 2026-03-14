"""Fixtures for HA Performance Diagnostics tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.ha_performance_diagnostics.const import (
    CONF_DB_SIZE_WARN_MB,
    CONF_SCAN_INTERVAL,
    CONF_SLOW_QUERY_THRESHOLD,
    CONF_STATE_CHANGE_THRESHOLD,
    DATA_ANTIPATTERNS,
    DATA_DB,
    DATA_HEALTH_SCORE,
    DATA_INTEGRATIONS,
    DATA_RECOMMENDATIONS,
    DATA_STATE_CHANGES,
    DATA_SYSTEM,
    DEFAULT_DB_SIZE_WARN_MB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_QUERY_THRESHOLD_MS,
    DEFAULT_STATE_CHANGE_THRESHOLD,
    DOMAIN,
)


@pytest.fixture
def default_config():
    """Return default config data."""
    return {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_SLOW_QUERY_THRESHOLD: DEFAULT_SLOW_QUERY_THRESHOLD_MS,
        CONF_STATE_CHANGE_THRESHOLD: DEFAULT_STATE_CHANGE_THRESHOLD,
        CONF_DB_SIZE_WARN_MB: DEFAULT_DB_SIZE_WARN_MB,
    }


@pytest.fixture
def sample_coordinator_data():
    """Return a complete sample coordinator data dict."""
    return {
        DATA_SYSTEM: {
            "cpu_percent": 25.0,
            "ram_percent": 55.0,
            "ram_used_mb": 2048.0,
            "ram_total_mb": 4096.0,
        },
        DATA_DB: {
            "db_size_mb": 500.0,
            "integrity_ok": True,
            "recorder_queue_size": 10,
        },
        DATA_STATE_CHANGES: {
            "top_entities": [
                {
                    "entity_id": "sensor.outdoor_temp",
                    "friendly_name": "Outdoor Temperature",
                    "changes_per_hour": 42,
                    "domain": "sensor",
                    "integration": "openweathermap",
                    "exceeds_threshold": False,
                },
                {
                    "entity_id": "binary_sensor.motion",
                    "friendly_name": "Motion Sensor",
                    "changes_per_hour": 30,
                    "domain": "binary_sensor",
                    "integration": "zwave_js",
                    "exceeds_threshold": False,
                },
                {
                    "entity_id": "sensor.power",
                    "friendly_name": "Power Meter",
                    "changes_per_hour": 20,
                    "domain": "sensor",
                    "integration": "shelly",
                    "exceeds_threshold": False,
                },
            ],
            "total_changes": 500,
            "entity_count": 150,
            "data_window_minutes": 60,
        },
        DATA_INTEGRATIONS: {
            "slowest": [
                {
                    "integration": "hacs",
                    "avg_update_ms": 400.0,
                    "last_error": None,
                    "entity_count": 14,
                },
                {
                    "integration": "zwave_js",
                    "avg_update_ms": 200.0,
                    "last_error": None,
                    "entity_count": 30,
                },
            ],
            "integration_count": 10,
        },
        DATA_ANTIPATTERNS: [],
        DATA_HEALTH_SCORE: 100,
        DATA_RECOMMENDATIONS: [],
    }
