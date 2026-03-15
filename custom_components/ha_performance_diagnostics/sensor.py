"""Sensor platform for HA Performance Diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_DB,
    DATA_HEALTH_SCORE,
    DATA_INTEGRATIONS,
    DATA_RECOMMENDATIONS,
    DATA_STATE_CHANGES,
    DATA_SYSTEM,
    DOMAIN,
)
from .coordinator import HAPerfDiagCoordinator


def _safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict keys."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _get_top_entity(data: dict, index: int) -> Any:
    """Get state value for top entity N."""
    entities = _safe_get(data, DATA_STATE_CHANGES, "top_entities", default=[])
    if index < len(entities):
        return entities[index].get("changes_per_hour")
    return None


def _get_top_entity_attrs(data: dict, index: int) -> dict[str, Any]:
    """Get attributes for top entity N."""
    entities = _safe_get(data, DATA_STATE_CHANGES, "top_entities", default=[])
    if index < len(entities):
        return entities[index]
    return {}


def _get_slowest_integration(data: dict, index: int) -> Any:
    """Get state value for slowest integration N."""
    integrations = _safe_get(data, DATA_INTEGRATIONS, "slowest", default=[])
    if index < len(integrations):
        return integrations[index].get("avg_update_ms")
    return None


def _get_slowest_integration_attrs(data: dict, index: int) -> dict[str, Any]:
    """Get attributes for slowest integration N."""
    integrations = _safe_get(data, DATA_INTEGRATIONS, "slowest", default=[])
    if index < len(integrations):
        return integrations[index]
    return {}


@dataclass(frozen=True, kw_only=True)
class HAPerfDiagSensorEntityDescription(SensorEntityDescription):
    """Describe a HA Performance Diagnostics sensor."""

    value_fn: Callable[[dict], Any]
    attr_fn: Callable[[dict], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[HAPerfDiagSensorEntityDescription, ...] = (
    # System sensors
    HAPerfDiagSensorEntityDescription(
        key="hapd_cpu_load",
        name="CPU Load",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cpu-64-bit",
        value_fn=lambda d: _safe_get(d, DATA_SYSTEM, "cpu_percent"),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_ram_used",
        name="RAM Used",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:memory",
        value_fn=lambda d: _safe_get(d, DATA_SYSTEM, "ram_percent"),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_db_size",
        name="DB Size",
        native_unit_of_measurement="MB",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:database",
        value_fn=lambda d: _safe_get(d, DATA_DB, "db_size_mb"),
        attr_fn=lambda d: {
            "integrity_ok": _safe_get(d, DATA_DB, "integrity_ok"),
        },
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_recorder_queue",
        name="Recorder Queue Depth",
        native_unit_of_measurement="events",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tray-full",
        value_fn=lambda d: _safe_get(d, DATA_DB, "recorder_queue_size"),
    ),
    # Entity activity sensors
    HAPerfDiagSensorEntityDescription(
        key="hapd_top_entity_1",
        name="Noisiest Entity #1",
        native_unit_of_measurement="changes/hr",
        icon="mdi:pulse",
        value_fn=lambda d: _get_top_entity(d, 0),
        attr_fn=lambda d: _get_top_entity_attrs(d, 0),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_top_entity_2",
        name="Noisiest Entity #2",
        native_unit_of_measurement="changes/hr",
        icon="mdi:pulse",
        value_fn=lambda d: _get_top_entity(d, 1),
        attr_fn=lambda d: _get_top_entity_attrs(d, 1),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_top_entity_3",
        name="Noisiest Entity #3",
        native_unit_of_measurement="changes/hr",
        icon="mdi:pulse",
        value_fn=lambda d: _get_top_entity(d, 2),
        attr_fn=lambda d: _get_top_entity_attrs(d, 2),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_total_state_changes",
        name="Total State Changes (1h)",
        native_unit_of_measurement="changes",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        value_fn=lambda d: _safe_get(d, DATA_STATE_CHANGES, "total_changes"),
        attr_fn=lambda d: {
            "data_window_minutes": _safe_get(d, DATA_STATE_CHANGES, "data_window_minutes"),
        },
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_entity_count",
        name="Total Tracked Entities",
        native_unit_of_measurement="entities",
        icon="mdi:format-list-numbered",
        value_fn=lambda d: _safe_get(d, DATA_STATE_CHANGES, "entity_count"),
    ),
    # Integration sensors
    HAPerfDiagSensorEntityDescription(
        key="hapd_slowest_integration_1",
        name="Slowest Integration #1",
        native_unit_of_measurement="ms",
        icon="mdi:timer-alert",
        value_fn=lambda d: _get_slowest_integration(d, 0),
        attr_fn=lambda d: _get_slowest_integration_attrs(d, 0),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_slowest_integration_2",
        name="Slowest Integration #2",
        native_unit_of_measurement="ms",
        icon="mdi:timer-alert",
        value_fn=lambda d: _get_slowest_integration(d, 1),
        attr_fn=lambda d: _get_slowest_integration_attrs(d, 1),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_slowest_integration_3",
        name="Slowest Integration #3",
        native_unit_of_measurement="ms",
        icon="mdi:timer-alert",
        value_fn=lambda d: _get_slowest_integration(d, 2),
        attr_fn=lambda d: _get_slowest_integration_attrs(d, 2),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_integration_count",
        name="Loaded Integration Count",
        icon="mdi:puzzle",
        value_fn=lambda d: _safe_get(d, DATA_INTEGRATIONS, "integration_count"),
    ),
    # Diagnostics summary sensors
    HAPerfDiagSensorEntityDescription(
        key="hapd_health_score",
        name="HA Health Score",
        icon="mdi:heart-pulse",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(DATA_HEALTH_SCORE),
    ),
    HAPerfDiagSensorEntityDescription(
        key="hapd_recommendations",
        name="Recommendations",
        icon="mdi:lightbulb-on",
        value_fn=lambda d: len(d.get(DATA_RECOMMENDATIONS, [])),
        attr_fn=lambda d: {
            "recommendations": d.get(DATA_RECOMMENDATIONS, []),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HA Performance Diagnostics sensors."""
    coordinator: HAPerfDiagCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        HAPerfDiagSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class HAPerfDiagSensor(CoordinatorEntity[HAPerfDiagCoordinator], SensorEntity):
    """Representation of a HA Performance Diagnostics sensor."""

    entity_description: HAPerfDiagSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HAPerfDiagCoordinator,
        description: HAPerfDiagSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info to group all sensors."""
        return {
            "identifiers": {(DOMAIN, DOMAIN)},
            "name": "HA Performance Diagnostics",
            "manufacturer": "HA Performance Diagnostics",
            "model": "Performance Monitor",
            "sw_version": "1.0.0",
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        try:
            return self.entity_description.value_fn(self.coordinator.data)
        except (KeyError, IndexError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.coordinator.data is None or self.entity_description.attr_fn is None:
            return None
        try:
            return self.entity_description.attr_fn(self.coordinator.data)
        except (KeyError, IndexError, TypeError):
            return None
