"""State for one PiPup TV: polled from ``/status``, and pushed by the app when it supports that."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import PipupClient, PipupError, PipupNotSupportedError
from .const import (
    APP_VERSION_PUSH,
    CONF_PUSH_WEBHOOK_ID,
    DOMAIN,
    EVENT_PUSH,
    ISSUE_OVERLAY_PERMISSION,
    OVERLAY_PERMISSION_COMMAND,
    SCAN_INTERVAL_SECONDS,
)
from .payload import parse_version

if TYPE_CHECKING:
    from . import PipupConfigEntry

_LOGGER = logging.getLogger(__name__)

# Keys a push adds on top of the /status snapshot; stripped before it becomes coordinator data.
_PUSH_ONLY_KEYS = ("event", "reason", "shownId", "removedId", "updatedId")


class PipupCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keeps the latest ``/status`` of one TV.

    A TV is often switched off, so this never raises ``UpdateFailed``: it flips ``online`` to False
    and keeps the last known data, so the connectivity sensor reflects reachability without the
    device going unavailable.

    When the app supports push (0.4.0+), the integration registers a local-only webhook with the TV.
    Every change then arrives at once, and polling only remains as a heartbeat, because a TV that is
    switched off cannot push that it went away.
    """

    config_entry: PipupConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PipupConfigEntry, client: PipupClient
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client
        self.online = False
        self._push_registered = False  # our webhook is registered in Home Assistant
        self._push_url: str | None = None
        self._push_asserted = False  # the TV accepted our webhook URL since it last came online
        self._last_push_event: str | None = None

    # region polling

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.async_status()
        except PipupError as err:
            if self.online:
                _LOGGER.debug("PiPup %s went offline: %s", self.client.base_url, err)
            self.online = False
            self._push_asserted = False  # re-check the TV's webhook when it is back
            return self.data or {}
        self.online = True
        await self._async_ensure_push(data)
        self._async_apply_side_effects(data)
        return data

    # endregion

    # region push

    @property
    def push_active(self) -> bool:
        """Whether the TV is currently pushing its state to Home Assistant."""
        return self._push_asserted

    async def _async_ensure_push(self, status: dict[str, Any]) -> None:
        """Make sure the TV pushes to our webhook, if it can.

        Re-asserted whenever the TV reports pushing off: an app reinstall or data wipe forgets the URL.
        """
        if not self._push_registered or self._push_url is None:
            return
        push = status.get("push")
        version = parse_version(status.get("version"))
        if not isinstance(push, dict) or (version is not None and version < APP_VERSION_PUSH):
            return
        if push.get("enabled") and self._push_asserted:
            return
        try:
            await self.client.async_set_push(self._push_url)
        except PipupNotSupportedError:
            return
        except PipupError as err:
            _LOGGER.debug("Could not set the push webhook on %s: %s", self.client.base_url, err)
            return
        self._push_asserted = True
        _LOGGER.debug("PiPup %s now pushes its state to Home Assistant", self.client.base_url)

    @callback
    def async_register_push_webhook(self) -> None:
        """Register this TV's push webhook in Home Assistant (not yet on the TV)."""
        entry = self.config_entry
        webhook_id = entry.data.get(CONF_PUSH_WEBHOOK_ID)
        if not webhook_id:
            return
        try:
            base = get_url(self.hass, allow_external=False, prefer_external=False)
        except NoURLAvailableError:
            _LOGGER.warning(
                "Home Assistant has no internal URL, so PiPup %s cannot push its state; "
                "falling back to polling every %s s",
                entry.title,
                SCAN_INTERVAL_SECONDS,
            )
            return
        webhook.async_register(
            self.hass,
            DOMAIN,
            f"PiPup {entry.title} state",
            webhook_id,
            self._async_handle_push,
            local_only=True,
            allowed_methods=["POST"],
        )
        self._push_url = base + webhook.async_generate_path(webhook_id)
        self._push_registered = True

    @callback
    def async_unregister_push_webhook(self) -> None:
        """Remove the push webhook from Home Assistant (the TV keeps the URL until told otherwise)."""
        if self._push_registered:
            webhook.async_unregister(self.hass, self.config_entry.data[CONF_PUSH_WEBHOOK_ID])
            self._push_registered = False

    async def _async_handle_push(
        self, hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        try:
            body = await request.json()
        except ValueError:
            return web.Response(status=400)
        if not isinstance(body, dict):
            return web.Response(status=400)
        # A webhook URL left on a different TV (say, after a factory reset gave this one a new id)
        # must not overwrite this TV's state.
        expected = self.config_entry.unique_id
        if expected and body.get("id") and body["id"] != expected and ":" not in expected:
            _LOGGER.debug("Ignoring a push from PiPup %s on %s's webhook", body.get("id"), expected)
            return web.Response(status=409)

        status = {k: v for k, v in body.items() if k not in _PUSH_ONLY_KEYS}
        self.online = True
        self._push_asserted = True
        self._async_apply_side_effects(status)
        self.async_set_updated_data(status)
        if event := body.get("event"):
            self._async_fire_push_event(event, body)
        return web.Response(status=200)

    @callback
    def _async_fire_push_event(self, event: str, body: dict[str, Any]) -> None:
        self._last_push_event = event
        device = self._device()
        hass_event: dict[str, Any] = {
            "entry_id": self.config_entry.entry_id,
            "device_id": device.id if device else None,
            "event": event,
        }
        popup_id = body.get("shownId") or body.get("removedId") or body.get("updatedId")
        if popup_id:
            hass_event["popup_id"] = popup_id
        if reason := body.get("reason"):
            hass_event["reason"] = reason
        self.hass.bus.async_fire(EVENT_PUSH, hass_event)

    # endregion

    # region side effects of a fresh status

    def _device(self) -> dr.DeviceEntry | None:
        registry = dr.async_get(self.hass)
        identifier = (DOMAIN, self.config_entry.entry_id)
        return next(
            (
                device
                for device in dr.async_entries_for_config_entry(registry, self.config_entry.entry_id)
                if identifier in device.identifiers
            ),
            None,
        )

    @callback
    def _async_apply_side_effects(self, status: dict[str, Any]) -> None:
        """Keep the device registry and the overlay-permission repair issue in step with the TV."""
        self._async_update_device(status)
        self._async_update_overlay_issue(status)

    @callback
    def _async_update_device(self, status: dict[str, Any]) -> None:
        device = self._device()
        if device is None:
            return
        changes: dict[str, Any] = {}
        if (version := status.get("version")) and device.sw_version != version:
            changes["sw_version"] = version
        info = status.get("device")
        model = info.get("model") if isinstance(info, dict) else None
        if model and device.hw_version != model:
            changes["hw_version"] = model
        if changes:
            dr.async_get(self.hass).async_update_device(device.id, **changes)

    @callback
    def _async_update_overlay_issue(self, status: dict[str, Any]) -> None:
        issue_id = f"{ISSUE_OVERLAY_PERMISSION}_{self.config_entry.entry_id}"
        if status.get("overlayPermission") is False:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_OVERLAY_PERMISSION,
                translation_placeholders={
                    "name": self.config_entry.title,
                    "command": OVERLAY_PERMISSION_COMMAND,
                },
            )
        elif "overlayPermission" in status:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    # endregion
