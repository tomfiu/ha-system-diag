"""Config flow for HA Performance Diagnostics."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DB_SIZE_WARN_MB,
    CONF_SCAN_INTERVAL,
    CONF_SLOW_QUERY_THRESHOLD,
    CONF_STATE_CHANGE_THRESHOLD,
    DEFAULT_DB_SIZE_WARN_MB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_QUERY_THRESHOLD_MS,
    DEFAULT_STATE_CHANGE_THRESHOLD,
    DOMAIN,
)


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the config/options schema with given defaults."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=60, max=3600)),
            vol.Optional(
                CONF_SLOW_QUERY_THRESHOLD,
                default=defaults.get(
                    CONF_SLOW_QUERY_THRESHOLD, DEFAULT_SLOW_QUERY_THRESHOLD_MS
                ),
            ): vol.All(int, vol.Range(min=100, max=5000)),
            vol.Optional(
                CONF_STATE_CHANGE_THRESHOLD,
                default=defaults.get(
                    CONF_STATE_CHANGE_THRESHOLD, DEFAULT_STATE_CHANGE_THRESHOLD
                ),
            ): vol.All(int, vol.Range(min=10, max=1000)),
            vol.Optional(
                CONF_DB_SIZE_WARN_MB,
                default=defaults.get(CONF_DB_SIZE_WARN_MB, DEFAULT_DB_SIZE_WARN_MB),
            ): vol.All(int, vol.Range(min=100, max=50000)),
        }
    )


class HAPerfDiagConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Performance Diagnostics."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="HA Performance Diagnostics",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return HAPerfDiagOptionsFlow(config_entry)


class HAPerfDiagOptionsFlow(OptionsFlow):
    """Handle options flow for HA Performance Diagnostics."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
        )
