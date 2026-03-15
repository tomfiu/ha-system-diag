"""Tests for the data coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_performance_diagnostics.const import (
    CONF_SCAN_INTERVAL,
    DATA_ANTIPATTERNS,
    DATA_DB,
    DATA_HEALTH_SCORE,
    DATA_INTEGRATIONS,
    DATA_RECOMMENDATIONS,
    DATA_STATE_CHANGES,
    DATA_SYSTEM,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.ha_performance_diagnostics.coordinator import (
    HAPerfDiagCoordinator,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry(default_config):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = default_config
    entry.options = {}
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def coordinator(mock_hass, mock_config_entry):
    """Create a coordinator instance."""
    with patch("homeassistant.helpers.frame.report_usage"):
        return HAPerfDiagCoordinator(mock_hass, mock_config_entry)


class TestCoordinatorInit:
    """Test coordinator initialization."""

    def test_default_interval(self, coordinator):
        """Default scan interval is set."""
        assert coordinator.update_interval.total_seconds() == DEFAULT_SCAN_INTERVAL

    def test_custom_interval(self, mock_hass):
        """Custom scan interval from config."""
        entry = MagicMock()
        entry.data = {CONF_SCAN_INTERVAL: 120}
        entry.options = {}
        with patch("homeassistant.helpers.frame.report_usage"):
            coord = HAPerfDiagCoordinator(mock_hass, entry)
        assert coord.update_interval.total_seconds() == 120

    def test_options_override_data(self, mock_hass):
        """Options take precedence over data."""
        entry = MagicMock()
        entry.data = {CONF_SCAN_INTERVAL: 120}
        entry.options = {CONF_SCAN_INTERVAL: 60}
        with patch("homeassistant.helpers.frame.report_usage"):
            coord = HAPerfDiagCoordinator(mock_hass, entry)
        assert coord.update_interval.total_seconds() == 60


class TestCoordinatorUpdate:
    """Test coordinator data update."""

    @pytest.mark.asyncio
    async def test_full_update_cycle(self, coordinator):
        """All data sections are populated."""
        system_data = {"cpu_percent": 25.0, "ram_percent": 50.0}
        db_data = {"db_size_mb": 500.0, "integrity_ok": True, "recorder_queue_size": 5}
        state_data = {
            "top_entities": [],
            "total_changes": 100,
            "entity_count": 50,
            "data_window_minutes": 60,
        }
        integration_data = {"slowest": [], "integration_count": 5}

        with (
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_system_metrics",
                new_callable=AsyncMock,
                return_value=system_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_db_health",
                new_callable=AsyncMock,
                return_value=db_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_state_change_analysis",
                new_callable=AsyncMock,
                return_value=state_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_integration_timing",
                new_callable=AsyncMock,
                return_value=integration_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_scan_automation_antipatterns",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            data = await coordinator._async_update_data()

        assert data[DATA_SYSTEM] == system_data
        assert data[DATA_DB] == db_data
        assert data[DATA_STATE_CHANGES] == state_data
        assert data[DATA_INTEGRATIONS] == integration_data
        assert data[DATA_ANTIPATTERNS] == []
        assert DATA_HEALTH_SCORE in data
        assert DATA_RECOMMENDATIONS in data
        assert isinstance(data[DATA_HEALTH_SCORE], int)
        assert isinstance(data[DATA_RECOMMENDATIONS], list)

    @pytest.mark.asyncio
    async def test_partial_failure_uses_fallback(self, coordinator):
        """Partial failure returns degraded data."""
        db_data = {"db_size_mb": 500.0, "integrity_ok": True, "recorder_queue_size": 5}
        state_data = {
            "top_entities": [],
            "total_changes": 0,
            "entity_count": 0,
            "data_window_minutes": 60,
        }
        integration_data = {"slowest": [], "integration_count": 5}

        with (
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_system_metrics",
                new_callable=AsyncMock,
                side_effect=Exception("CPU read failed"),
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_db_health",
                new_callable=AsyncMock,
                return_value=db_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_state_change_analysis",
                new_callable=AsyncMock,
                return_value=state_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_integration_timing",
                new_callable=AsyncMock,
                return_value=integration_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_scan_automation_antipatterns",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            data = await coordinator._async_update_data()

        # System data should be empty dict (no previous data)
        assert data[DATA_SYSTEM] == {}
        # Other data should be present
        assert data[DATA_DB] == db_data

    @pytest.mark.asyncio
    async def test_previous_data_used_on_failure(self, coordinator):
        """Previous data is used as fallback on failure."""
        system_data = {"cpu_percent": 25.0, "ram_percent": 50.0}
        db_data = {"db_size_mb": 500.0, "integrity_ok": True, "recorder_queue_size": 5}
        state_data = {
            "top_entities": [],
            "total_changes": 0,
            "entity_count": 0,
            "data_window_minutes": 60,
        }
        integration_data = {"slowest": [], "integration_count": 5}

        # First successful run
        with (
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_system_metrics",
                new_callable=AsyncMock,
                return_value=system_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_db_health",
                new_callable=AsyncMock,
                return_value=db_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_state_change_analysis",
                new_callable=AsyncMock,
                return_value=state_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_integration_timing",
                new_callable=AsyncMock,
                return_value=integration_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_scan_automation_antipatterns",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await coordinator._async_update_data()

        # Second run with system failure
        with (
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_system_metrics",
                new_callable=AsyncMock,
                side_effect=Exception("CPU read failed"),
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_db_health",
                new_callable=AsyncMock,
                return_value=db_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_state_change_analysis",
                new_callable=AsyncMock,
                return_value=state_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_get_integration_timing",
                new_callable=AsyncMock,
                return_value=integration_data,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.coordinator.async_scan_automation_antipatterns",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            data = await coordinator._async_update_data()

        # Previous system data should be used
        assert data[DATA_SYSTEM] == system_data
