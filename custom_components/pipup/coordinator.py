"""Status polling coordinator for PiPup."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import PipupClient, PipupError
from .const import DOMAIN, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class PipupCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls ``/status``.

    A TV is often switched off, so this never raises ``UpdateFailed`` — it simply
    flips ``online`` to ``False`` and keeps the last known data, which lets the
    connectivity sensor reflect reachability without the device going unavailable.
    """

    def __init__(self, hass: HomeAssistant, client: PipupClient) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client
        self.online = False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_status()
        except PipupError as err:
            self.online = False
            _LOGGER.debug("PiPup status unavailable: %s", err)
            return self.data or {}
        self.online = True
        return data
