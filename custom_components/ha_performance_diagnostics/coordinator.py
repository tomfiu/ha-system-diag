"""Data coordinator for HA Performance Diagnostics."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DB_SIZE_WARN_MB,
    CONF_SCAN_INTERVAL,
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
    DEFAULT_STATE_CHANGE_THRESHOLD,
    DOMAIN,
)
from .diagnostics import (
    async_get_db_health,
    async_get_integration_timing,
    async_get_state_change_analysis,
    async_get_system_metrics,
    async_scan_automation_antipatterns,
    calculate_health_score,
    generate_recommendations,
)

_LOGGER = logging.getLogger(__name__)


class HAPerfDiagCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to gather all performance diagnostic data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self._previous_data: dict[str, Any] | None = None

        # Read config values
        options = {**config_entry.data, **config_entry.options}
        scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._state_change_threshold = options.get(
            CONF_STATE_CHANGE_THRESHOLD, DEFAULT_STATE_CHANGE_THRESHOLD
        )
        self._config = options

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all diagnostic data."""
        results = await asyncio.gather(
            async_get_system_metrics(self.hass),
            async_get_db_health(self.hass),
            async_get_state_change_analysis(
                self.hass, self._state_change_threshold
            ),
            async_get_integration_timing(self.hass),
            return_exceptions=True,
        )

        data: dict[str, Any] = {}

        # Process results, using previous data as fallback on errors
        keys = [DATA_SYSTEM, DATA_DB, DATA_STATE_CHANGES, DATA_INTEGRATIONS]
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                _LOGGER.warning(
                    "Error collecting %s data: %s", key, result
                )
                if self._previous_data and key in self._previous_data:
                    data[key] = self._previous_data[key]
                else:
                    data[key] = {}
            else:
                data[key] = result

        # Automation scan depends on state change data for top entities
        top_entities = data.get(DATA_STATE_CHANGES, {}).get("top_entities", [])
        try:
            data[DATA_ANTIPATTERNS] = await async_scan_automation_antipatterns(
                self.hass, top_entities
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error scanning automation antipatterns: %s", err)
            if self._previous_data and DATA_ANTIPATTERNS in self._previous_data:
                data[DATA_ANTIPATTERNS] = self._previous_data[DATA_ANTIPATTERNS]
            else:
                data[DATA_ANTIPATTERNS] = []

        # Compute health score and recommendations
        data[DATA_HEALTH_SCORE] = calculate_health_score(data, self._config)
        data[DATA_RECOMMENDATIONS] = generate_recommendations(data, self._config)

        self._previous_data = data
        return data
