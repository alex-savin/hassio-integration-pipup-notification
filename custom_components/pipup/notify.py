"""Notify platform for PiPup.

Exposes two things:

* a standard ``notify`` entity (``notify.send_message`` with title + message), and
* a rich ``pipup.send`` entity service that maps every PiPup field (media, TTS,
  styling, position, …) onto the device's ``/notify`` JSON API.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PipupConfigEntry
from .const import DOMAIN, FIELD_MAP, MANUFACTURER, MODEL

SERVICE_SEND = "send"

SEND_SCHEMA = {
    vol.Optional("title"): cv.string,
    vol.Optional("message"): cv.string,
    vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=4)),
    vol.Optional("tts"): cv.string,
    vol.Optional("sound"): cv.string,
    vol.Optional("image_uri"): cv.string,
    vol.Optional("video_uri"): cv.string,
    vol.Optional("web_uri"): cv.string,
    vol.Optional("media_width"): vol.Coerce(int),
    vol.Optional("web_height"): vol.Coerce(int),
    vol.Optional("background_color"): cv.string,
    vol.Optional("title_color"): cv.string,
    vol.Optional("title_size"): vol.Coerce(float),
    vol.Optional("message_color"): cv.string,
    vol.Optional("message_size"): vol.Coerce(float),
    vol.Optional("corner_radius"): vol.Coerce(int),
    vol.Optional("border_color"): cv.string,
    vol.Optional("border_width"): vol.Coerce(int),
    vol.Optional("icon_uri"): cv.string,
    vol.Optional("show_progress"): cv.boolean,
    vol.Optional("replace"): cv.boolean,
    vol.Optional("callback"): cv.string,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PipupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PiPup notify entity and register the rich service."""
    async_add_entities([PipupNotifyEntity(entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_SEND, SEND_SCHEMA, "async_send")


def build_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Map Home Assistant service fields onto the PiPup ``/notify`` JSON body."""
    payload: dict[str, Any] = {
        FIELD_MAP[key]: value for key, value in data.items() if key in FIELD_MAP
    }

    width = data.get("media_width")
    if (uri := data.get("image_uri")) is not None:
        image: dict[str, Any] = {"uri": uri}
        if width is not None:
            image["width"] = width
        payload["media"] = {"image": image}
    elif (uri := data.get("video_uri")) is not None:
        video: dict[str, Any] = {"uri": uri}
        if width is not None:
            video["width"] = width
        payload["media"] = {"video": video}
    elif (uri := data.get("web_uri")) is not None:
        web: dict[str, Any] = {"uri": uri}
        if width is not None:
            web["width"] = width
        if (height := data.get("web_height")) is not None:
            web["height"] = height
        payload["media"] = {"web": web}

    return payload


class PipupNotifyEntity(NotifyEntity):
    """A PiPup TV as a Home Assistant notify target."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the entity."""
        self._client = entry.runtime_data.client
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=self._client.base_url,
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a simple notification (message + optional title)."""
        payload: dict[str, Any] = {"message": message}
        if title:
            payload["title"] = title
        await self._client.async_notify(payload)

    async def async_send(self, **kwargs: Any) -> None:
        """Send a rich notification from the ``pipup.send`` service."""
        await self._client.async_notify(build_payload(kwargs))
