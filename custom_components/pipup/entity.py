"""Base entity for PiPup."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PipupConfigEntry
from .const import DOMAIN
from .coordinator import PipupCoordinator


class PipupEntity(CoordinatorEntity[PipupCoordinator]):
    """An entity of one PiPup TV, fed by its coordinator."""

    _attr_has_entity_name = True

    def __init__(self, entry: PipupConfigEntry, key: str) -> None:
        """Initialise the entity; ``key`` is its translation key and unique-id suffix."""
        super().__init__(entry.runtime_data.coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def status(self) -> dict[str, Any]:
        """The TV's latest status, or an empty dict before the first answer."""
        return self.coordinator.data or {}
