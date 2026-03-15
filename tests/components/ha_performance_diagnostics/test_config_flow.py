"""Tests for the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_performance_diagnostics.config_flow import (
    HAPerfDiagConfigFlow,
    HAPerfDiagOptionsFlow,
)
from custom_components.ha_performance_diagnostics.const import (
    CONF_DB_SIZE_WARN_MB,
    CONF_SCAN_INTERVAL,
    CONF_SLOW_QUERY_THRESHOLD,
    CONF_STATE_CHANGE_THRESHOLD,
    DEFAULT_DB_SIZE_WARN_MB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_QUERY_THRESHOLD_MS,
    DEFAULT_STATE_CHANGE_THRESHOLD,
)


@pytest.fixture
def config_flow():
    """Create a config flow instance."""
    flow = HAPerfDiagConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries = MagicMock()
    flow.hass.config_entries.async_entries.return_value = []
    return flow


class TestConfigFlow:
    """Test config flow."""

    @pytest.mark.asyncio
    async def test_user_step_shows_form(self, config_flow):
        """First call shows the form."""
        with (
            patch.object(config_flow, "async_set_unique_id", new_callable=AsyncMock),
            patch.object(config_flow, "_abort_if_unique_id_configured"),
        ):
            result = await config_flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["data_schema"] is not None

    @pytest.mark.asyncio
    async def test_user_step_creates_entry(self, config_flow):
        """Submitting form creates config entry."""
        user_input = {
            CONF_SCAN_INTERVAL: 300,
            CONF_SLOW_QUERY_THRESHOLD: 500,
            CONF_STATE_CHANGE_THRESHOLD: 60,
            CONF_DB_SIZE_WARN_MB: 1000,
        }

        with (
            patch.object(config_flow, "async_set_unique_id", new_callable=AsyncMock),
            patch.object(config_flow, "_abort_if_unique_id_configured"),
        ):
            result = await config_flow.async_step_user(user_input)

        assert result["type"] == "create_entry"
        assert result["title"] == "HA Performance Diagnostics"
        assert result["data"] == user_input

    @pytest.mark.asyncio
    async def test_user_step_with_defaults(self, config_flow):
        """Submitting with defaults works."""
        user_input = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_SLOW_QUERY_THRESHOLD: DEFAULT_SLOW_QUERY_THRESHOLD_MS,
            CONF_STATE_CHANGE_THRESHOLD: DEFAULT_STATE_CHANGE_THRESHOLD,
            CONF_DB_SIZE_WARN_MB: DEFAULT_DB_SIZE_WARN_MB,
        }

        with (
            patch.object(config_flow, "async_set_unique_id", new_callable=AsyncMock),
            patch.object(config_flow, "_abort_if_unique_id_configured"),
        ):
            result = await config_flow.async_step_user(user_input)

        assert result["type"] == "create_entry"


class TestOptionsFlow:
    """Test options flow."""

    @pytest.mark.asyncio
    async def test_options_shows_form(self):
        """Options init shows form with current values."""
        entry = MagicMock()
        entry.data = {
            CONF_SCAN_INTERVAL: 300,
            CONF_SLOW_QUERY_THRESHOLD: 500,
            CONF_STATE_CHANGE_THRESHOLD: 60,
            CONF_DB_SIZE_WARN_MB: 1000,
        }
        entry.options = {}

        flow = HAPerfDiagOptionsFlow(entry)
        result = await flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_creates_entry(self):
        """Submitting options creates entry."""
        entry = MagicMock()
        entry.data = {CONF_SCAN_INTERVAL: 300}
        entry.options = {}

        flow = HAPerfDiagOptionsFlow(entry)
        user_input = {CONF_SCAN_INTERVAL: 120}
        result = await flow.async_step_init(user_input)

        assert result["type"] == "create_entry"
        assert result["data"] == user_input
