"""Diagnostics for PiPup (Settings > Devices > the TV > Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import PipupConfigEntry
from .const import CONF_CALLBACK_WEBHOOK_ID, CONF_PUSH_WEBHOOK_ID

# The token unlocks the TV's API; the webhook ids are the secrets in the URLs the TV posts to.
TO_REDACT = {CONF_TOKEN, CONF_PUSH_WEBHOOK_ID, CONF_CALLBACK_WEBHOOK_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PipupConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "online": coordinator.online,
        "push_active": coordinator.push_active,
        "last_update_success": coordinator.last_update_success,
        "status": coordinator.data,
    }
