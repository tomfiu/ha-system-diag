"""HA Performance Diagnostics integration."""

from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import HAPerfDiagCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Performance Diagnostics from a config entry."""
    coordinator = HAPerfDiagCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register frontend card as a static resource and load it in Lovelace
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "ha-performance-card.js")
    if os.path.isfile(frontend_path):
        url = "/hacsfiles/ha-performance-card/ha-performance-card.js"
        try:
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        url,
                        frontend_path,
                        cache_headers=True,
                    )
                ]
            )
        except (ImportError, AttributeError):
            hass.http.register_static_path(
                url,
                frontend_path,
                cache_headers=True,
            )

        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
