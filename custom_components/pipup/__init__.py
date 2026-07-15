"""The PiPup integration — pop-up notifications on Android TV."""

from __future__ import annotations

from dataclasses import dataclass
import secrets

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PipupClient
from .const import DATA_CALLBACK_TOKENS, PLATFORMS
from .coordinator import PipupCoordinator
from .http import async_register_callback_view


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

    # Register the (shared) endpoint that receives popup button/lifecycle callbacks from the TVs, and
    # mint this entry's secret so only callbacks carrying it (i.e. ones we sent to the TV) are honored.
    async_register_callback_view(hass)
    hass.data.setdefault(DATA_CALLBACK_TOKENS, {})[entry.entry_id] = secrets.token_urlsafe(16)

    entry.runtime_data = PipupRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PipupConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.get(DATA_CALLBACK_TOKENS, {}).pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
