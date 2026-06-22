"""The PiPup integration — pop-up notifications on Android TV."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PipupClient
from .const import PLATFORMS
from .coordinator import PipupCoordinator


@dataclass
class PipupRuntimeData:
    """Objects shared across the platforms of a config entry."""

    client: PipupClient
    coordinator: PipupCoordinator


type PipupConfigEntry = ConfigEntry[PipupRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: PipupConfigEntry) -> bool:
    """Set up PiPup from a config entry."""
    client = PipupClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN),
    )
    coordinator = PipupCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = PipupRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PipupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
