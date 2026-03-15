"""Tests for the automation anti-pattern scanner."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.ha_performance_diagnostics.diagnostics import (
    async_scan_automation_antipatterns,
)


def _make_automation_state(entity_id, friendly_name, auto_id="test_id"):
    """Create a mock automation state."""
    state = MagicMock()
    state.entity_id = entity_id
    state.attributes = {
        "friendly_name": friendly_name,
        "id": auto_id,
    }
    return state


def _make_hass(automations, configs):
    """Create a mock hass with automation states and configs."""
    hass = MagicMock()
    hass.states.async_all.return_value = automations
    hass.data = {"automation_config": configs}
    return hass


class TestNoConditionStateTrigger:
    """Test detection of state triggers without conditions on noisy entities."""

    @pytest.mark.asyncio
    async def test_detects_noisy_trigger_no_condition(self):
        """Flag automation with state trigger on noisy entity and no conditions."""
        auto = _make_automation_state("automation.test_auto", "Test Automation", "test_auto")
        config = {
            "automation.test_auto": {
                "trigger": [{"platform": "state", "entity_id": "sensor.outdoor_temp"}],
                "condition": [],
                "action": [{"service": "light.turn_on", "entity_id": "light.test"}],
            }
        }
        hass = _make_hass([auto], config)
        top_entities = [
            {
                "entity_id": "sensor.outdoor_temp",
                "changes_per_hour": 142,
                "exceeds_threshold": True,
            }
        ]

        results = await async_scan_automation_antipatterns(hass, top_entities)

        assert len(results) == 1
        assert results[0]["pattern"] == "noisy_trigger_no_condition"
        assert results[0]["severity"] == "warning"
        assert "sensor.outdoor_temp" in results[0]["description"]

    @pytest.mark.asyncio
    async def test_ignores_trigger_with_conditions(self):
        """Don't flag if automation has conditions."""
        auto = _make_automation_state("automation.test_auto", "Test Automation", "test_auto")
        config = {
            "automation.test_auto": {
                "trigger": [{"platform": "state", "entity_id": "sensor.outdoor_temp"}],
                "condition": [{"condition": "time", "after": "08:00"}],
                "action": [{"service": "light.turn_on"}],
            }
        }
        hass = _make_hass([auto], config)
        top_entities = [
            {
                "entity_id": "sensor.outdoor_temp",
                "changes_per_hour": 142,
                "exceeds_threshold": True,
            }
        ]

        results = await async_scan_automation_antipatterns(hass, top_entities)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_ignores_non_noisy_entity(self):
        """Don't flag if entity is not noisy."""
        auto = _make_automation_state("automation.test_auto", "Test Automation", "test_auto")
        config = {
            "automation.test_auto": {
                "trigger": [{"platform": "state", "entity_id": "sensor.quiet_entity"}],
                "condition": [],
                "action": [{"service": "light.turn_on"}],
            }
        }
        hass = _make_hass([auto], config)
        top_entities = [
            {
                "entity_id": "sensor.outdoor_temp",
                "changes_per_hour": 142,
                "exceeds_threshold": True,
            }
        ]

        results = await async_scan_automation_antipatterns(hass, top_entities)
        assert len(results) == 0


class TestAutomationChains:
    """Test detection of automation chains."""

    @pytest.mark.asyncio
    async def test_detects_automation_trigger_chain(self):
        """Flag automation that triggers another automation."""
        auto = _make_automation_state("automation.chain_start", "Chain Start", "chain_start")
        config = {
            "automation.chain_start": {
                "trigger": [{"platform": "state", "entity_id": "sensor.test"}],
                "condition": [],
                "action": [
                    {
                        "service": "automation.trigger",
                        "entity_id": "automation.chain_end",
                    }
                ],
            }
        }
        hass = _make_hass([auto], config)

        results = await async_scan_automation_antipatterns(hass)
        assert len(results) == 1
        assert results[0]["pattern"] == "automation_chain"
        assert results[0]["severity"] == "info"

    @pytest.mark.asyncio
    async def test_detects_automation_turn_on_chain(self):
        """Flag automation.turn_on as a chain too."""
        auto = _make_automation_state("automation.chain_start", "Chain Start", "chain_start")
        config = {
            "automation.chain_start": {
                "trigger": [{"platform": "time", "at": "08:00"}],
                "condition": [],
                "action": [
                    {
                        "service": "automation.turn_on",
                        "entity_id": "automation.other",
                    }
                ],
            }
        }
        hass = _make_hass([auto], config)

        results = await async_scan_automation_antipatterns(hass)
        assert len(results) == 1
        assert results[0]["pattern"] == "automation_chain"


class TestStartupOverload:
    """Test detection of startup overload."""

    @pytest.mark.asyncio
    async def test_detects_startup_with_many_actions(self):
        """Flag HA start trigger with >5 actions."""
        auto = _make_automation_state("automation.startup", "Startup Tasks", "startup")
        config = {
            "automation.startup": {
                "trigger": [{"platform": "homeassistant", "event": "start"}],
                "condition": [],
                "action": [
                    {"service": "light.turn_on", "entity_id": f"light.test_{i}"} for i in range(8)
                ],
            }
        }
        hass = _make_hass([auto], config)

        results = await async_scan_automation_antipatterns(hass)
        assert len(results) == 1
        assert results[0]["pattern"] == "startup_overload"
        assert "8 actions" in results[0]["description"]

    @pytest.mark.asyncio
    async def test_ignores_startup_with_few_actions(self):
        """Don't flag startup with <= 5 actions."""
        auto = _make_automation_state("automation.startup", "Startup Tasks", "startup")
        config = {
            "automation.startup": {
                "trigger": [{"platform": "homeassistant", "event": "start"}],
                "condition": [],
                "action": [
                    {"service": "light.turn_on", "entity_id": "light.test_1"},
                    {"service": "light.turn_on", "entity_id": "light.test_2"},
                ],
            }
        }
        hass = _make_hass([auto], config)

        results = await async_scan_automation_antipatterns(hass)
        assert len(results) == 0


class TestCleanAutomations:
    """Test that clean automations produce no findings."""

    @pytest.mark.asyncio
    async def test_no_automations(self):
        """No automations returns empty list."""
        hass = _make_hass([], {})
        results = await async_scan_automation_antipatterns(hass)
        assert results == []

    @pytest.mark.asyncio
    async def test_clean_automation_no_findings(self):
        """Well-structured automation produces no findings."""
        auto = _make_automation_state("automation.clean", "Clean Automation", "clean")
        config = {
            "automation.clean": {
                "trigger": [{"platform": "time", "at": "08:00:00"}],
                "condition": [
                    {"condition": "state", "entity_id": "input_boolean.test", "state": "on"}
                ],
                "action": [{"service": "light.turn_on", "entity_id": "light.kitchen"}],
            }
        }
        hass = _make_hass([auto], config)

        results = await async_scan_automation_antipatterns(hass)
        assert results == []

    @pytest.mark.asyncio
    async def test_missing_config_handled(self):
        """Automation without config data is skipped gracefully."""
        auto = _make_automation_state("automation.no_config", "No Config", "no_config")
        hass = _make_hass([auto], {})

        results = await async_scan_automation_antipatterns(hass)
        assert results == []
