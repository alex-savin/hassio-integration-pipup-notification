"""The PiPup integration — pop-up notifications on Android TV."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import logging

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import PipupClient, PipupError
from .callbacks import async_handle_callback_webhook, drop_entry_tokens
from .const import (
    CONF_CALLBACK_WEBHOOK_ID,
    CONF_PUSH_WEBHOOK_ID,
    DOMAIN,
    ISSUE_OVERLAY_PERMISSION,
    MANUFACTURER,
    MODEL,
    PLATFORMS,
)
from .coordinator import PipupCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class PipupRuntimeData:
    """Objects shared across the platforms of a config entry."""

    client: PipupClient
    coordinator: PipupCoordinator


type PipupConfigEntry = ConfigEntry[PipupRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Nothing to set up globally; services are entity services registered by the platforms."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PipupConfigEntry) -> bool:
    """Set up PiPup from a config entry."""
    # Mint the webhook ids once and keep them: the TV holds the push URL in its own settings, so it
    # must stay valid across Home Assistant restarts.
    missing = {
        key: webhook.async_generate_id()
        for key in (CONF_PUSH_WEBHOOK_ID, CONF_CALLBACK_WEBHOOK_ID)
        if not entry.data.get(key)
    }
    if missing:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **missing})

    client = PipupClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN),
    )
    # Create the device before the first status read, so that read can fill in its version and model.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=MODEL,
        configuration_url=client.base_url,
    )

    coordinator = PipupCoordinator(hass, entry, client)
    entry.runtime_data = PipupRuntimeData(client=client, coordinator=coordinator)

    coordinator.async_register_push_webhook()
    webhook.async_register(
        hass,
        DOMAIN,
        f"PiPup {entry.title} buttons",
        entry.data[CONF_CALLBACK_WEBHOOK_ID],
        partial(async_handle_callback_webhook, entry_id=entry.entry_id),
        local_only=True,
        allowed_methods=["POST"],
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PipupConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.coordinator.async_unregister_push_webhook()
        webhook.async_unregister(hass, entry.data[CONF_CALLBACK_WEBHOOK_ID])
        drop_entry_tokens(hass, entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: PipupConfigEntry) -> None:
    """The TV was removed from Home Assistant: stop it pushing to a webhook that no longer exists."""
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_OVERLAY_PERMISSION}_{entry.entry_id}")
    client = PipupClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_TOKEN),
    )
    try:
        await client.async_set_push("")
    except PipupError as err:
        _LOGGER.debug("Could not turn off pushing on %s: %s", client.base_url, err)
