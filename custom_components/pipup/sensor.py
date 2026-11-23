"""Sensors for PiPup: popups on screen, and the last popup received."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PipupConfigEntry
from .entity import PipupEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PipupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    async_add_entities([PipupPopupCountSensor(entry), PipupLastPopupSensor(entry)])


class PipupPopupCountSensor(PipupEntity, SensorEntity):
    """How many popups are on screen."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry, "popups")

    @property
    def native_value(self) -> int | None:
        """The count, or None while the TV is unreachable."""
        count = self.status.get("count")
        return count if self.coordinator.online and isinstance(count, int) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Each popup on screen (id, position, media, duration, elapsed), in stack order."""
        popups = self.status.get("popups")
        return {"popups": popups if isinstance(popups, list) else None}


class PipupLastPopupSensor(PipupEntity, SensorEntity):
    """The id of the last popup the TV received; its other details are attributes.

    Useful to check what an automation actually sent. The app never reports popup text or URLs here.
    """

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry, "last_popup")

    @property
    def _last(self) -> dict[str, Any]:
        last = self.status.get("lastPopup")
        return last if isinstance(last, dict) else {}

    @property
    def native_value(self) -> str | None:
        """The popup's id (the app assigns one when the caller gave none)."""
        return self._last.get("id")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Position, media type, duration, buttons, tts/sound flags."""
        last = self._last
        return {
            key: last.get(key)
            for key in ("position", "media", "duration", "buttons", "tts", "sound")
        }
