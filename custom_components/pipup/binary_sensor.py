"""Binary sensors for PiPup: connectivity, screen, popup on screen, overlay permission."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PipupConfigEntry
from .entity import PipupEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PipupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    async_add_entities(
        [
            PipupConnectivitySensor(entry),
            PipupScreenSensor(entry),
            PipupPopupSensor(entry),
            PipupOverlayPermissionSensor(entry),
        ]
    )


class PipupConnectivitySensor(PipupEntity, BinarySensorEntity):
    """Whether the PiPup server is reachable."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry, "connectivity")

    @property
    def is_on(self) -> bool:
        """Return True when the TV answered the last poll or pushed since."""
        return self.coordinator.online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a few useful fields from the status snapshot."""
        data = self.status
        return {
            "version": data.get("version"),
            "active": data.get("active"),
            "count": data.get("count"),
            "auth_enabled": data.get("authEnabled"),
            "push": self.coordinator.push_active,
        }


class _OnlineOnly(PipupEntity, BinarySensorEntity):
    """A sensor that is unknown while the TV is unreachable (its last value would be stale)."""

    _field: str

    @property
    def is_on(self) -> bool | None:
        """Return the field's value, or None while offline or before the app reports it."""
        if not self.coordinator.online:
            return None
        value = self.status.get(self._field)
        return value if isinstance(value, bool) else None


class PipupScreenSensor(_OnlineOnly):
    """Whether the TV screen is on."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _field = "screenOn"

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry, "screen")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Whether the screensaver is showing."""
        return {"screensaver": self.status.get("dreaming")}


class PipupPopupSensor(_OnlineOnly):
    """Whether any popup is on screen."""

    _field = "active"

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry, "popup")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The popups on screen, in stack order."""
        popups = self.status.get("popups")
        return {
            "popup_ids": [p.get("id") for p in popups] if isinstance(popups, list) else None
        }


class PipupOverlayPermissionSensor(PipupEntity, BinarySensorEntity):
    """On when PiPup lacks "display over other apps", so no popup can appear."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry, "overlay_permission")

    @property
    def is_on(self) -> bool | None:
        """Problem when the app reports the permission missing; unknown on apps that don't say."""
        value = self.status.get("overlayPermission")
        return (not value) if isinstance(value, bool) else None
