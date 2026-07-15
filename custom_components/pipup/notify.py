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
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import PipupConfigEntry
from .const import (
    CALLBACK_PATH,
    DATA_CALLBACK_TOKENS,
    DOMAIN,
    FIELD_MAP,
    MANUFACTURER,
    MODEL,
)

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
    vol.Optional("id"): cv.string,
    vol.Optional("urgency"): vol.In(["info", "warning", "critical"]),
    vol.Optional("muted"): cv.boolean,
    vol.Optional("buttons"): vol.All(
        cv.ensure_list,
        [{vol.Required("id"): cv.string, vol.Required("label"): cv.string}],
        vol.Length(max=3),
    ),
    vol.Optional("button_color"): cv.string,
    vol.Optional("button_text_color"): cv.string,
    vol.Optional("media_position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
    vol.Optional("title_alignment"): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
    vol.Optional("message_alignment"): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
    vol.Optional("animation_type"): vol.In(["none", "fade", "slide", "scale"]),
    vol.Optional("animation_duration"): vol.Coerce(int),
    vol.Optional("animation_exit"): cv.boolean,
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

    if (buttons := data.get("buttons")) is not None:
        payload["buttons"] = buttons

    width = data.get("media_width")
    muted = data.get("muted")
    if (uri := data.get("image_uri")) is not None:
        image: dict[str, Any] = {"uri": uri}
        if width is not None:
            image["width"] = width
        payload["media"] = {"image": image}
    elif (uri := data.get("video_uri")) is not None:
        video: dict[str, Any] = {"uri": uri}
        if width is not None:
            video["width"] = width
        if muted is not None:
            video["muted"] = muted
        payload["media"] = {"video": video}
    elif (uri := data.get("web_uri")) is not None:
        web: dict[str, Any] = {"uri": uri}
        if width is not None:
            web["width"] = width
        if (height := data.get("web_height")) is not None:
            web["height"] = height
        if muted is not None:
            web["muted"] = muted
        payload["media"] = {"web": web}

    return payload


class PipupNotifyEntity(NotifyEntity):
    """A PiPup TV as a Home Assistant notify target."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the entity."""
        self._client = entry.runtime_data.client
        self._entry_id = entry.entry_id
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
        payload = build_payload(kwargs)
        # So button presses reach Home Assistant with no manual setup: when a popup has buttons and
        # the caller didn't set their own callback, point it at our per-TV callback endpoint. The
        # view then fires a ``pipup_button`` event (see http.py).
        if payload.get("buttons") and not payload.get("callback"):
            if (callback_url := self._callback_url()) is not None:
                payload["callback"] = callback_url
        await self._client.async_notify(payload)

    def _callback_url(self) -> str | None:
        """The LAN-reachable, token-carrying callback URL for this TV, or None if unavailable."""
        token = self.hass.data.get(DATA_CALLBACK_TOKENS, {}).get(self._entry_id)
        if not token:
            return None
        try:
            base = get_url(self.hass, prefer_external=False, allow_internal=True)
        except NoURLAvailableError:
            return None
        return f"{base}{CALLBACK_PATH}/{self._entry_id}?token={token}"
