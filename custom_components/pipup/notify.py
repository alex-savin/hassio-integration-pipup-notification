"""Notify platform for PiPup.

Exposes:

* a standard ``notify`` entity (``notify.send_message`` with title + message),
* ``pipup.send``, an entity service that maps every PiPup field (media, cameras, TTS, styling,
  positions…) onto the device's ``/notify`` API, and
* ``pipup.dismiss``, which closes one popup by id or all of them.
"""

from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError, get_url

from . import PipupConfigEntry
from .api import PipupError
from .callbacks import issue_token
from .camera_media import async_camera_media
from .const import (
    CAMERA_MODE_MJPEG,
    CAMERA_MODES,
    CONF_CALLBACK_WEBHOOK_ID,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .payload import UnsupportedByApp, build_payload, check_supported

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND = "send"
SERVICE_DISMISS = "dismiss"

_COLOR = cv.string
_UNIT = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))

_GRID_TILE = vol.Any(
    cv.string,
    vol.Schema(
        {
            vol.Required(vol.Any("uri", "whep_uri", "url")): cv.string,
            vol.Optional("label"): cv.string,
            vol.Optional(vol.Any("poster", "poster_uri")): cv.string,
        }
    ),
)

SEND_SCHEMA = {
    vol.Optional("title"): cv.string,
    vol.Optional("message"): cv.string,
    vol.Optional("duration"): vol.Coerce(int),
    vol.Optional("position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
    vol.Optional("fullscreen"): cv.boolean,
    vol.Optional("opacity"): _UNIT,
    vol.Optional("tts"): cv.string,
    vol.Optional("tts_language"): cv.string,
    vol.Optional("sound"): cv.string,
    vol.Optional("sound_volume"): _UNIT,
    vol.Optional("dismiss_screensaver"): cv.boolean,
    # Media: one of these.
    vol.Optional("camera_entity"): cv.entity_domain("camera"),
    vol.Optional("camera_mode"): vol.In(CAMERA_MODES),
    vol.Optional("image_uri"): cv.string,
    vol.Optional("video_uri"): cv.string,
    vol.Optional("web_uri"): cv.string,
    vol.Optional("whep_uri"): cv.string,
    vol.Optional("grid"): vol.All(cv.ensure_list, [_GRID_TILE], vol.Length(min=1, max=9)),
    # Media options.
    vol.Optional("poster_uri"): cv.string,
    vol.Optional("poster_mode"): vol.In(["fit", "fill", "stretch", "center"]),
    vol.Optional("media_width"): vol.Coerce(int),
    vol.Optional("media_height"): vol.Coerce(int),
    vol.Optional("web_height"): vol.Coerce(int),
    vol.Optional("muted"): cv.boolean,
    vol.Optional("buffer_ms"): vol.All(vol.Coerce(int), vol.Range(min=100, max=10000)),
    vol.Optional("decoder"): vol.In(["auto", "hardware", "software"]),
    vol.Optional("grid_columns"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
    vol.Optional("grid_labels"): cv.boolean,
    # Look.
    vol.Optional("background_color"): _COLOR,
    vol.Optional("title_color"): _COLOR,
    vol.Optional("title_size"): vol.Coerce(float),
    vol.Optional("message_color"): _COLOR,
    vol.Optional("message_size"): vol.Coerce(float),
    vol.Optional("corner_radius"): vol.Coerce(int),
    vol.Optional("border_color"): _COLOR,
    vol.Optional("border_width"): vol.Coerce(int),
    vol.Optional("icon_uri"): cv.string,
    vol.Optional("show_progress"): cv.boolean,
    vol.Optional("urgency"): vol.In(["info", "warning", "critical"]),
    vol.Optional("media_position"): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
    vol.Optional("title_alignment"): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
    vol.Optional("message_alignment"): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
    vol.Optional("animation_type"): vol.In(["none", "fade", "slide", "scale"]),
    vol.Optional("animation_duration"): vol.Coerce(int),
    vol.Optional("animation_exit"): cv.boolean,
    # Behaviour.
    vol.Optional("id"): cv.string,
    vol.Optional("replace"): cv.boolean,
    vol.Optional("callback"): cv.string,
    vol.Optional("buttons"): vol.All(
        cv.ensure_list,
        [{vol.Required("id"): cv.string, vol.Required("label"): cv.string}],
        vol.Length(max=3),
    ),
    vol.Optional("button_color"): _COLOR,
    vol.Optional("button_text_color"): _COLOR,
}

DISMISS_SCHEMA = {vol.Optional("id"): cv.string}

_MEDIA_FIELDS = ("camera_entity", "image_uri", "video_uri", "web_uri", "whep_uri", "grid")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PipupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PiPup notify entity and register its services."""
    async_add_entities([PipupNotifyEntity(entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_SEND, SEND_SCHEMA, "async_send")
    platform.async_register_entity_service(SERVICE_DISMISS, DISMISS_SCHEMA, "async_dismiss")


class PipupNotifyEntity(NotifyEntity):
    """A PiPup TV as a Home Assistant notify target."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: PipupConfigEntry) -> None:
        """Initialise the entity."""
        self._entry = entry
        self._client = entry.runtime_data.client
        self._coordinator = entry.runtime_data.coordinator
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
        await self._call(self._client.async_notify(payload))

    async def async_send(self, **data: Any) -> None:
        """Send a rich notification from the ``pipup.send`` service."""
        if sum(1 for key in _MEDIA_FIELDS if data.get(key)) > 1:
            raise ServiceValidationError(
                "Give at most one of camera_entity, image_uri, video_uri, web_uri, whep_uri, grid"
            )

        snapshot = None
        if camera := data.pop("camera_entity", None):
            mode = data.pop("camera_mode", CAMERA_MODE_MJPEG)
            media = await async_camera_media(self.hass, camera, mode, data.get("duration"))
            snapshot = media.snapshot
            if media.web_uri:
                data["web_uri"] = media.web_uri
                data.setdefault("muted", True)
            if media.video_uri:
                data["video_uri"] = media.video_uri
            if media.poster_uri:
                data.setdefault("poster_uri", media.poster_uri)
        else:
            data.pop("camera_mode", None)

        payload = build_payload(data)
        try:
            check_supported(payload, (self._coordinator.data or {}).get("version"))
        except UnsupportedByApp as err:
            raise ServiceValidationError(str(err)) from err

        if payload.get("buttons") and not payload.get("callback"):
            self._attach_callback(payload, data.get("duration"))

        if snapshot is not None:
            if payload.pop("buttons", None):
                _LOGGER.warning(
                    "Buttons are not available with camera_mode snapshot (the image is uploaded, "
                    "and uploads carry only plain fields); sending the popup without them"
                )
                payload.pop("callback", None)
            await self._call(
                self._client.async_notify_image(
                    payload, snapshot, width=data.get("media_width")
                )
            )
        else:
            await self._call(self._client.async_notify(payload))

    async def async_dismiss(self, id: str | None = None) -> None:  # noqa: A002 - service field name
        """Close one popup by id, or every popup on screen."""
        await self._call(self._client.async_cancel(id))

    def _attach_callback(self, payload: dict[str, Any], duration: int | None) -> None:
        """Point the popup's callback at this TV's button webhook with a token for this popup only.

        A popup without an id gets one here, so the token can be bound to it.
        """
        try:
            base = get_url(self.hass, allow_external=False, prefer_external=False)
        except NoURLAvailableError:
            _LOGGER.warning(
                "Home Assistant has no internal URL, so button presses on %s cannot be reported",
                self._entry.title,
            )
            return
        popup_id = payload.setdefault("id", f"ha-{uuid.uuid4().hex[:12]}")
        device = self.device_entry
        token = issue_token(
            self.hass,
            entry_id=self._entry.entry_id,
            device_id=device.id if device else None,
            popup_id=popup_id,
            buttons=payload["buttons"],
            duration=duration,
        )
        path = webhook.async_generate_path(self._entry.data[CONF_CALLBACK_WEBHOOK_ID])
        payload["callback"] = f"{base}{path}?token={token}"

    async def _call(self, request: Any) -> Any:
        """Run one request to the TV, turning its errors into Home Assistant errors."""
        try:
            result = await request
        except PipupError as err:
            raise HomeAssistantError(f"{self._entry.title}: {err}") from err
        if not self._coordinator.push_active:
            await self._coordinator.async_request_refresh()
        return result
