"""Buttons for PiPup: wake the screen, dismiss every popup."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PipupConfigEntry
from .api import PipupError, PipupNotSupportedError
from .entity import PipupEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PipupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    async_add_entities([PipupWakeButton(entry), PipupDismissButton(entry)])


class PipupWakeButton(PipupEntity, ButtonEntity):
    """Turn the TV screen on and end the screensaver."""

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the button."""
        super().__init__(entry, "wake")

    async def async_press(self) -> None:
        """Wake the screen; fail loudly when the app is too old or the screen stayed off."""
        try:
            reached = await self.coordinator.client.async_power_on()
        except PipupNotSupportedError as err:
            raise HomeAssistantError(
                "Waking the screen needs PiPup 0.4.0 or newer on the TV"
            ) from err
        except PipupError as err:
            raise HomeAssistantError(str(err)) from err
        if reached is False:
            raise HomeAssistantError(
                "The TV accepted the request, but its screen did not come on"
            )
        if not self.coordinator.push_active:
            await self.coordinator.async_request_refresh()


class PipupDismissButton(PipupEntity, ButtonEntity):
    """Close every popup on the TV."""

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the button."""
        super().__init__(entry, "dismiss")

    async def async_press(self) -> None:
        """Dismiss all popups."""
        try:
            await self.coordinator.client.async_cancel()
        except PipupError as err:
            raise HomeAssistantError(str(err)) from err
        if not self.coordinator.push_active:
            await self.coordinator.async_request_refresh()
