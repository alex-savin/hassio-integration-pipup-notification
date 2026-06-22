"""Connectivity sensor for PiPup."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PipupConfigEntry
from .const import DOMAIN
from .coordinator import PipupCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PipupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the connectivity sensor."""
    async_add_entities([PipupConnectivitySensor(entry)])


class PipupConnectivitySensor(CoordinatorEntity[PipupCoordinator], BinarySensorEntity):
    """Reflects whether the PiPup server is reachable."""

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_registry_enabled_default = True

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the sensor."""
        super().__init__(entry.runtime_data.coordinator)
        self._attr_unique_id = f"{entry.entry_id}_connectivity"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def is_on(self) -> bool:
        """Return True when the server answered the last status poll."""
        return self.coordinator.online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a few useful fields from the status snapshot."""
        data = self.coordinator.data or {}
        return {
            "version": data.get("version"),
            "active": data.get("active"),
            "count": data.get("count"),
            "auth_enabled": data.get("authEnabled"),
        }
